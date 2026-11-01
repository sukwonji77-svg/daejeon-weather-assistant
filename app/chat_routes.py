from fastapi import APIRouter, Response

from app import conversations
from app.chat_service import chat
from app.data_routes import RecordId, call_database
from app.models import ChatInput, ConversationInput

router = APIRouter(prefix="/api", tags=["AI 채팅과 대화 기록"])


@router.post("/chat", summary="기온 요약 기반 GPT 답변과 대화 자동 저장")
def post_chat(body: ChatInput):
    return chat(body)


@router.post("/conversations", status_code=201, summary="대화 저장 (GPT 호출 없음)")
def create_conversation(body: ConversationInput):
    return call_database(conversations.create_conversation, body.title,
                         [message.model_dump() for message in body.messages])


@router.get("/conversations", summary="이전 대화 목록 (messages 미포함)")
def list_conversations():
    return call_database(conversations.list_conversations)


@router.get("/conversations/{conversation_id}", summary="선택한 대화의 전체 messages 불러오기")
def get_conversation(conversation_id: RecordId):
    return call_database(conversations.get_conversation, conversation_id)


@router.delete("/conversations/{conversation_id}", status_code=204, summary="대화 삭제")
def delete_conversation(conversation_id: RecordId):
    call_database(conversations.delete_conversation, conversation_id)
    return Response(status_code=204)
