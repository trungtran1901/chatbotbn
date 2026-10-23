import logging
from typing import List, Dict
import httpx
from app.config import settings

logger = logging.getLogger("rag.mem0_client")


def _client():
    return httpx.Client(base_url=settings.mem0_service_url, timeout=15)


def add_turn(session_id: str, user_message: str, assistant_message: str, metadata: dict = None):
    """Ghi 1 luot hoi-dap vao Mem0 (OpenMemory) de trich xuat fact dai han."""
    payload = {
        "user_id": session_id,
        "messages": [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message},
        ],
        "metadata": metadata or {},
    }
    try:
        with _client() as client:
            resp = client.post("/api/v1/memories/", json=payload)
            resp.raise_for_status()
    except Exception:
        logger.exception("Loi khi ghi memory cho session %s", session_id)


def search_memories(session_id: str, query: str, limit: int = None) -> List[Dict]:
    """Tim cac memory lien quan toi cau hoi hien tai trong pham vi 1 session."""
    limit = limit or settings.mem0_search_limit
    payload = {
        "user_id": session_id,
        "query": query,
        "limit": limit,
    }
    try:
        with _client() as client:
            resp = client.post("/api/v1/memories/filter", json=payload)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                return data.get("results", data.get("items", []))
            return data or []
    except Exception:
        logger.exception("Loi khi tim memory cho session %s", session_id)
        return []