"""데이터 API: 요청 처리와 실제 저장소 처리를 분리합니다."""

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path as PathParameter, Response
from google.api_core.exceptions import NotFound

from app import database
from app.analysis import summarize
from app.models import DataInput, DataRecord

router = APIRouter(prefix="/api/data", tags=["기온 데이터"])
RecordId = Annotated[str, PathParameter(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")]


def call_database(operation, *args):
    try:
        return operation(*args)
    except NotFound:
        raise HTTPException(status_code=404, detail="해당 데이터가 없습니다.") from None
    except Exception:
        raise HTTPException(status_code=503, detail="Firestore 요청에 실패했습니다. 인증 설정과 인터넷 연결을 확인하세요.") from None


@router.get("/summary", summary="현재 저장된 기온의 분석 결과 조회")
def get_summary():
    result = summarize(call_database(database.list_records))
    source_file = Path(__file__).resolve().parents[1] / "data/summary.json"
    result["source"] = json.loads(source_file.read_text(encoding="utf-8"))["source"]
    return result


@router.get("", response_model=list[DataRecord], summary="기온 데이터 목록 조회")
def get_data():
    return call_database(database.list_records)


@router.post("", response_model=DataRecord, status_code=201, summary="기온 데이터 추가")
def add_data(body: DataInput):
    return call_database(database.create_record, body.model_dump())


@router.put("/{record_id}", response_model=DataRecord, summary="기온 데이터 수정")
def edit_data(record_id: RecordId, body: DataInput):
    return call_database(database.update_record, record_id, body.model_dump())


@router.delete("/{record_id}", status_code=204, summary="기온 데이터 삭제")
def remove_data(record_id: RecordId):
    call_database(database.delete_record, record_id)
    return Response(status_code=204)
