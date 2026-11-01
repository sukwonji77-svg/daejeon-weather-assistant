"""환경변수로 인증한 Firestore 연결입니다. 비밀 키를 코드에 넣지 않습니다."""

from functools import lru_cache
import json
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
from google.api_core.exceptions import NotFound

PROJECT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_DIR / ".env")


@lru_cache(maxsize=1)
def get_db():
    expected_project = os.environ.get("FIREBASE_PROJECT_ID")
    if not expected_project:
        raise RuntimeError("FIREBASE_PROJECT_ID 환경변수가 필요합니다.")
    if os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON"):
        info = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"])
    else:
        key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not key_path:
            raise RuntimeError("인증 파일 경로 환경변수가 필요합니다.")
        info = json.loads(Path(key_path).read_text(encoding="utf-8-sig"))
    if info.get("type") != "service_account" or info.get("project_id") != expected_project:
        raise RuntimeError("인증 파일의 프로젝트가 설정과 일치하지 않습니다.")
    try:
        app = firebase_admin.get_app("weather")
    except ValueError:
        app = firebase_admin.initialize_app(credentials.Certificate(info),
                                            {"projectId": expected_project}, name="weather")
    return firestore.client(app=app)


def list_records():
    snapshots = get_db().collection("data").stream(retry=None, timeout=20)
    records = [{**doc.to_dict(), "id": doc.id} for doc in snapshots]
    return sorted(records, key=lambda row: (row["date"], row["id"]))


def create_record(data):
    reference = get_db().collection("data").document()
    reference.create(data, retry=None, timeout=20)
    return {**data, "id": reference.id}


def update_record(record_id, data):
    reference = get_db().collection("data").document(record_id)
    # update는 없는 문서를 새로 만들지 않습니다.
    reference.update(data, retry=None, timeout=20)
    return {**data, "id": record_id}


def delete_record(record_id):
    reference = get_db().collection("data").document(record_id)
    if not reference.get(retry=None, timeout=20).exists:
        raise NotFound("Record not found")
    reference.delete(retry=None, timeout=20)
