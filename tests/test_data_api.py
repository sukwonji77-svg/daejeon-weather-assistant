"""실제 저장소를 변경하지 않고 요청 검증·오류 처리·집계 반영을 검사합니다."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.api_core.exceptions import NotFound

from app.main import app


class DataApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        rows = json.loads((Path(__file__).resolve().parents[1] / "data/daejeon_temperature_2025.json").read_text(encoding="utf-8"))
        self.rows = {r["date"]: {**r, "id": r["date"]} for r in rows}
        self.sample = {**rows[0], "memo": "연습용 복사 - 원본 아님"}

    def test_lifecycle_updates_current_summary_and_preserves_original(self):
        original = self.rows["2025-01-01"].copy()

        def create(data):
            self.rows["practice"] = {**data, "id": "practice"}
            return self.rows["practice"]

        def update(record_id, data):
            self.rows[record_id] = {**data, "id": record_id}
            return self.rows[record_id]

        with patch("app.database.list_records", side_effect=lambda: list(self.rows.values())), \
             patch("app.database.create_record", side_effect=create), \
             patch("app.database.update_record", side_effect=update), \
             patch("app.database.delete_record", side_effect=lambda key: self.rows.pop(key)):
            self.assertEqual(self.client.get("/api/data/summary").json()["count"], 365)
            added = self.client.post("/api/data", json=self.sample)
            self.assertEqual(added.status_code, 201)
            self.assertEqual(added.json()["id"], "practice")
            self.assertEqual(self.client.get("/api/data/summary").json()["count"], 366)
            changed = {**self.sample, "value": self.sample["value"] + 1}
            result = self.client.put("/api/data/practice", json=changed)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["value"], changed["value"])
            before_delete = self.client.get("/api/data/summary").json()
            self.assertNotEqual(before_delete["metrics"]["average"], 13.97)
            result = self.client.delete("/api/data/practice")
            self.assertEqual(result.status_code, 204)
            self.assertEqual(result.content, b"")
            restored = self.client.get("/api/data/summary").json()
            self.assertEqual(restored["count"], 365)
            self.assertEqual(restored["metrics"]["average"], 13.97)
            self.assertEqual(self.rows["2025-01-01"], original)

    def test_invalid_inputs_never_reach_database(self):
        with patch("app.database.create_record") as create:
            for change in [{"date": "2025-02-30"}, {"date": "2025/01/01"},
                           {"value": "cold"}, {"value": True}, {"value": "NaN"},
                           {"memo": "x" * 1001}, {"unexpected": "field"}]:
                with self.subTest(change=change):
                    response = self.client.post("/api/data", json={**self.sample, **change})
                    self.assertEqual(response.status_code, 422)
            create.assert_not_called()

    def test_missing_record_returns_404(self):
        with patch("app.database.update_record", side_effect=NotFound("internal detail")), \
             patch("app.database.delete_record", side_effect=NotFound("internal detail")):
            self.assertEqual(self.client.put("/api/data/missing", json=self.sample).status_code, 404)
            self.assertEqual(self.client.delete("/api/data/missing").status_code, 404)

    def test_backend_failure_does_not_leak_details(self):
        with patch("app.database.create_record", side_effect=RuntimeError("private-key-detail")):
            response = self.client.post("/api/data", json=self.sample)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("private-key-detail", response.text)

    def test_empty_data_has_defined_summary(self):
        with patch("app.database.list_records", return_value=[]):
            summary = self.client.get("/api/data/summary").json()
            self.assertEqual(summary["count"], 0)
            self.assertIsNone(summary["period"])
            self.assertIsNone(summary["trend"])


if __name__ == "__main__":
    unittest.main()
