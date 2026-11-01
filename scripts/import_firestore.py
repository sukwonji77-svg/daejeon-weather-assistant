"""초기 기온 데이터만 저장합니다. 이미 있는 날짜는 덮어쓰지 않습니다."""

import argparse
from datetime import date, timedelta
import json
import math
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
from app.database import get_db, list_records
from app.analysis import summarize


def main(write=False):
    rows = json.loads((PROJECT_DIR / "data/daejeon_temperature_2025.json").read_text(encoding="utf-8"))
    expected = [(date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(365)]
    if [row["date"] for row in rows] != expected:
        raise ValueError("초기 데이터 날짜 검증 실패")
    for row in rows:
        if not isinstance(row["value"], (int, float)) or not math.isfinite(row["value"]):
            raise ValueError("초기 기온 검증 실패")
    current = {row["id"]: row for row in list_records()}
    missing = [row for row in rows if row["date"] not in current]
    print(f"Connected. Existing: {len(current)}, missing seed records: {len(missing)}")
    if missing and not write:
        print("Read-only check. Use --import-data to add missing records.")
        return
    if missing:
        db = get_db()
        batch = db.batch()
        for row in missing:
            batch.create(db.collection("data").document(row["date"]), row)
        batch.commit(retry=None, timeout=30)
        print(f"Added {len(missing)} records. Existing records were preserved.")
    stored = list_records()
    stored_by_id = {row["id"]: row for row in stored}
    identical = sum(all(stored_by_id.get(row["date"], {}).get(k) == v for k, v in row.items()) for row in rows)
    print(f"Stored: {len(stored)}, original records matching: {identical}/365")
    print(f"Average: {summarize(stored)['metrics'].get('average')} C")
    if identical != 365:
        raise ValueError("기존 데이터 중 원본과 다른 항목이 있습니다. 덮어쓰지 않았습니다.")
    print("PASS: Firestore import and read-back verified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import-data", action="store_true")
    args = parser.parse_args()
    try:
        main(args.import_data)
    except Exception as error:
        # 오류 내용에 인증 정보를 포함할 수 있어 유형만 표시합니다.
        print(f"FAIL: {type(error).__name__}. Check Firebase settings and internet access.")
        raise SystemExit(1)
