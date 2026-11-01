"""Firestore 기온 데이터 CRUD와 분석 서버입니다."""

from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os

from app.data_routes import router as data_router
from app.chat_routes import router as chat_router
from app.access import access_required, require_access

app = FastAPI(
    title="대전 기온 분석 AI 비서 - Firestore 연결",
    description="기온 데이터 관리, GPT 분석 답변, Firestore 대화 저장과 불러오기를 제공합니다.",
    version="0.6.0",
)
frontend = Path(__file__).resolve().parents[1] / "frontend"
app.add_middleware(CORSMiddleware,
    allow_origins=[item.strip() for item in os.environ.get("ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",") if item.strip()],
    allow_credentials=False, allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "X-App-Token"])
app.include_router(data_router, dependencies=[Depends(require_access)])
app.include_router(chat_router, dependencies=[Depends(require_access)])
app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")


@app.get("/health", summary="서버 실행 확인")
def home():
    return {"message": "대전 기온 분석 서버가 실행 중입니다.", "docs": "/docs", "stage": "web_app", "access_required": access_required()}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(frontend / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/config.js", include_in_schema=False)
def config():
    return FileResponse(frontend / "config.js", media_type="application/javascript", headers={"Cache-Control": "no-store"})
