"""인터넷 배포 시 데이터와 유료 GPT 호출을 접속 암호로 보호합니다."""

import os
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

access_header = APIKeyHeader(name="X-App-Token", auto_error=False, scheme_name="접속 암호")


def access_required():
    return bool(os.environ.get("APP_ACCESS_TOKEN")) or os.environ.get("RENDER") == "true"


def require_access(token: str | None = Security(access_header)):
    expected = os.environ.get("APP_ACCESS_TOKEN", "")
    if os.environ.get("RENDER") == "true" and len(expected) < 16:
        raise HTTPException(503, {"code": "access_not_configured", "message": "서버의 접속 암호 설정이 필요합니다."})
    if not expected:
        return
    if not token or not secrets.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(401, {"code": "access_denied", "message": "접속 암호를 확인해 주세요."})
