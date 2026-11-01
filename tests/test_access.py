import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_protected_routes_reject_missing_token_before_database_or_gpt(self):
        with patch.dict(os.environ, {"APP_ACCESS_TOKEN": "test-access-password-123", "RENDER": "true"}), \
             patch("app.database.list_records") as read, \
             patch("app.chat_service.generate_reply") as gpt:
            for method, path, body in [
                ("GET", "/api/data", None), ("GET", "/api/data/summary", None),
                ("POST", "/api/data", {"date": "2025-01-01", "value": 1.9}),
                ("PUT", "/api/data/example", {"date": "2025-01-01", "value": 1.9}),
                ("DELETE", "/api/data/example", None), ("POST", "/api/chat", {"message": "평균?"}),
                ("GET", "/api/conversations", None), ("GET", "/api/conversations/example", None),
                ("POST", "/api/conversations", {"title": "test", "messages": []}),
                ("DELETE", "/api/conversations/example", None),
            ]:
                with self.subTest(path=path, method=method):
                    result = self.client.request(method, path, json=body)
                    self.assertEqual(result.status_code, 401)
                    self.assertEqual(result.json()["detail"]["code"], "access_denied")
            read.assert_not_called()
            gpt.assert_not_called()

    def test_correct_password_allows_access_wrong_password_does_not(self):
        with patch.dict(os.environ, {"APP_ACCESS_TOKEN": "test-access-password-123", "RENDER": "true"}), \
             patch("app.database.list_records", return_value=[]) as read:
            self.assertEqual(self.client.get("/api/data", headers={"X-App-Token": "wrong"}).status_code, 401)
            read.assert_not_called()
            self.assertEqual(self.client.get("/api/data", headers={"X-App-Token": "test-access-password-123"}).status_code, 200)
            read.assert_called_once()

    def test_render_without_password_is_closed_to_api_but_health_works(self):
        with patch.dict(os.environ, {"APP_ACCESS_TOKEN": "", "RENDER": "true"}), \
             patch("app.database.list_records") as read:
            self.assertEqual(self.client.get("/api/data").status_code, 503)
            self.assertTrue(self.client.get("/health").json()["access_required"])
            self.assertEqual(self.client.get("/").status_code, 200)
            self.assertEqual(self.client.get("/docs").status_code, 200)
            read.assert_not_called()

    def test_local_practice_without_password_keeps_working(self):
        with patch.dict(os.environ, {"APP_ACCESS_TOKEN": "", "RENDER": ""}), \
             patch("app.database.list_records", return_value=[]):
            self.assertEqual(self.client.get("/api/data").status_code, 200)
            self.assertFalse(self.client.get("/health").json()["access_required"])
