import unittest

from fastapi.testclient import TestClient
from app.main import app


class WebTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_page_and_assets_are_served(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="chat-form"', response.text)
        self.assertIn('id="data-form"', response.text)
        for path in ["/assets/app.js", "/assets/styles.css", "/config.js", "/docs"]:
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.assertEqual(self.client.get("/health").json()["stage"], "web_app")

    def test_only_frontend_files_are_public(self):
        for path in ["/.env", "/app/database.py", "/data/summary.json", "/scripts/configure_openai.py", "/assets/../.env"]:
            self.assertEqual(self.client.get(path).status_code, 404, path)
        self.assertNotIn("OPENAI_API_KEY", self.client.get("/config.js").text)

    def test_cors_restricts_browser_origins(self):
        headers = {"Origin": "http://127.0.0.1:8000", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "Content-Type"}
        response = self.client.options("/api/chat", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://127.0.0.1:8000")
        response = self.client.options("/api/chat", headers={**headers, "Origin": "https://unrelated.example"})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)
