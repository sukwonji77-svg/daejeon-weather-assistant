"""날짜, 기온, 메모의 입력 형식을 검증합니다."""

from datetime import date
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DataInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str = Field(description="날짜 (YYYY-MM-DD)")
    value: float = Field(strict=True, allow_inf_nan=False, description="일평균기온 (°C)")
    memo: str = Field(default="", max_length=1000, description="출처 또는 메모")

    @field_validator("date")
    @classmethod
    def valid_date(cls, value):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("날짜는 YYYY-MM-DD 형식이어야 합니다.")
        date.fromisoformat(value)
        return value


class DataRecord(DataInput):
    id: str


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ConversationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(default="새 대화", min_length=1, max_length=100)
    messages: list[Message] = Field(default_factory=list, max_length=100)

    @field_validator("messages")
    @classmethod
    def alternating_messages(cls, messages):
        for index, message in enumerate(messages):
            if message.role != ("user" if index % 2 == 0 else "assistant"):
                raise ValueError("메시지는 사용자와 AI 순서로 번갈아 저장해야 합니다.")
        if len(messages) % 2:
            raise ValueError("저장할 대화는 AI 답변까지 포함해야 합니다.")
        return messages


class ChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=2000, examples=["2025년 대전의 평균기온은 얼마야?"])
    conversation_id: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
