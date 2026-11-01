"""대화 저장과 동시 수정 충돌 처리입니다."""

from datetime import datetime, timezone

from firebase_admin import firestore
from google.api_core.exceptions import NotFound

from app.database import get_db


class ConversationConflict(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def create_conversation(title, messages, **metadata):
    reference = get_db().collection("conversations").document()
    timestamp = now()
    record = {"title": title, "messages": messages, "created_at": timestamp,
              "updated_at": timestamp, "revision": 0, **metadata}
    reference.create(record, retry=None, timeout=20)
    return {**record, "id": reference.id}


def get_conversation(conversation_id):
    snapshot = get_db().collection("conversations").document(conversation_id).get(retry=None, timeout=20)
    if not snapshot.exists:
        raise NotFound("Conversation not found")
    return {**snapshot.to_dict(), "id": snapshot.id}


def list_conversations():
    # 목록에는 messages를 넣지 않습니다. 상세 GET에서 전체 대화를 불러옵니다.
    snapshots = get_db().collection("conversations").select(["title", "created_at", "updated_at"]).stream(retry=None, timeout=20)
    rows = [{**snapshot.to_dict(), "id": snapshot.id} for snapshot in snapshots]
    return sorted(rows, key=lambda row: row.get("updated_at", ""), reverse=True)


def append_exchange(conversation_id, expected_revision, messages, **metadata):
    db = get_db()
    reference = db.collection("conversations").document(conversation_id)

    @firestore.transactional
    def save(transaction):
        snapshot = reference.get(transaction=transaction)
        if not snapshot.exists:
            raise NotFound("Conversation not found")
        existing = snapshot.to_dict()
        if existing.get("revision", 0) != expected_revision:
            raise ConversationConflict()
        changes = {"messages": existing.get("messages", []) + messages,
                   "updated_at": now(), "revision": expected_revision + 1, **metadata}
        transaction.update(reference, changes)
        return {**existing, **changes, "id": conversation_id}

    return save(db.transaction(max_attempts=3))


def delete_conversation(conversation_id):
    get_conversation(conversation_id)
    get_db().collection("conversations").document(conversation_id).delete(retry=None, timeout=20)
