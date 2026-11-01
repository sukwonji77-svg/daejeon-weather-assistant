import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch, MagicMock
import httpx
from openai import RateLimitError

from fastapi.testclient import TestClient
from google.api_core.exceptions import NotFound
from fastapi import HTTPException

from app.main import app
from app import chat_service


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.rows = json.loads((Path(__file__).resolve().parents[1] / "data/daejeon_temperature_2025.json").read_text(encoding="utf-8"))

    def test_summary_is_injected_with_output_limit_and_no_retries(self):
        api = MagicMock()
        api.responses.create.return_value = SimpleNamespace(
            status="completed", output_text="2025년 평균기온은 13.97℃입니다.",
            usage=SimpleNamespace(input_tokens=500, output_tokens=30, total_tokens=530))
        factory = MagicMock()
        factory.return_value.__enter__.return_value = api
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-only", "OPENAI_MODEL": "gpt-6-luna"}), \
             patch("app.chat_service.OpenAI", factory):
            result = chat_service.generate_reply("평균기온?", [], {"count": 365, "average": 13.97})
        arguments = api.responses.create.call_args.kwargs
        self.assertIn("13.97", arguments["instructions"])
        self.assertEqual(arguments["max_output_tokens"], 600)
        self.assertFalse(arguments["store"])
        self.assertEqual(factory.call_args.kwargs["max_retries"], 0)
        self.assertIn("13.97", result[0])

    def test_new_chat_saves_question_and_reply_after_success(self):
        with patch("app.database.list_records", return_value=self.rows), \
             patch("app.chat_service.enforce_rate_limit"), \
             patch("app.chat_service.generate_reply", return_value=("13.97℃입니다.", "test-model", {})) as generate, \
             patch("app.conversations.create_conversation", return_value={"id": "saved-id"}) as save:
            response = self.client.post("/api/chat", json={"message": "평균기온?"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["conversation_id"], "saved-id")
        self.assertEqual(generate.call_args.args[2]["count"], 365)
        self.assertEqual([m["role"] for m in save.call_args.args[1]], ["user", "assistant"])

    def test_quota_failure_does_not_save_or_retry(self):
        with patch("app.database.list_records", return_value=self.rows), \
             patch("app.chat_service.enforce_rate_limit"), \
             patch("app.chat_service.generate_reply", side_effect=HTTPException(402, "잔액 부족")) as generate, \
             patch("app.conversations.create_conversation") as save:
            response = self.client.post("/api/chat", json={"message": "평균기온?"})
        self.assertEqual(response.status_code, 402)
        generate.assert_called_once()
        save.assert_not_called()

    def test_followup_uses_saved_history_and_revision(self):
        history = [{"role": "user", "content": "평균?"}, {"role": "assistant", "content": "13.97℃"}]
        with patch("app.conversations.get_conversation", return_value={"id": "existing", "revision": 3, "messages": history}), \
             patch("app.database.list_records", return_value=self.rows), \
             patch("app.chat_service.enforce_rate_limit"), \
             patch("app.chat_service.generate_reply", return_value=("31.4℃", "test", {})) as generate, \
             patch("app.conversations.append_exchange", return_value={"id": "existing"}) as append:
            response = self.client.post("/api/chat", json={"message": "최댓값은?", "conversation_id": "existing"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate.call_args.args[1], history)
        self.assertEqual(append.call_args.args[:2], ("existing", 3))

    def test_missing_conversation_does_not_call_gpt(self):
        with patch("app.conversations.get_conversation", side_effect=NotFound("missing")), \
             patch("app.chat_service.generate_reply") as generate:
            response = self.client.post("/api/chat", json={"message": "평균?", "conversation_id": "missing"})
        self.assertEqual(response.status_code, 404)
        generate.assert_not_called()

    def test_invalid_message_and_conversation_order_are_rejected(self):
        self.assertEqual(self.client.post("/api/chat", json={"message": "   "}).status_code, 422)
        self.assertEqual(self.client.post("/api/chat", json={"message": "x" * 2001}).status_code, 422)
        self.assertEqual(self.client.post("/api/conversations", json={"messages": [{"role": "system", "content": "test"}]}).status_code, 422)

    def test_save_failure_returns_reply_without_silently_retrying(self):
        with patch("app.database.list_records", return_value=self.rows), \
             patch("app.chat_service.enforce_rate_limit"), \
             patch("app.chat_service.generate_reply", return_value=("13.97℃", "test", {})) as generate, \
             patch("app.conversations.create_conversation", side_effect=RuntimeError("internal secret")):
            response = self.client.post("/api/chat", json={"message": "평균?"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["reply"], "13.97℃")
        self.assertNotIn("internal secret", response.text)
        generate.assert_called_once()

    def test_billing_and_rate_limit_codes_have_separate_guidance(self):
        for code, expected in [("credit_balance_exhausted", 402), ("insufficient_quota", 402), ("slow_down", 429)]:
            api = MagicMock()
            api.responses.create.side_effect = RateLimitError("not shown", response=httpx.Response(
                429, request=httpx.Request("POST", "https://api.openai.com/v1/responses")), body={"error": {"code": code}})
            factory = MagicMock()
            factory.return_value.__enter__.return_value = api
            with self.subTest(code=code), patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-only"}), \
                 patch("app.chat_service.OpenAI", factory):
                with self.assertRaises(HTTPException) as caught:
                    chat_service.generate_reply("평균?", [], {"count": 365})
                self.assertEqual(caught.exception.status_code, expected)
                api.responses.create.assert_called_once()
