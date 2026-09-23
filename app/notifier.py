import httpx
from app.config import settings


def send_telegram(text: str, thread_id: int = None):
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {"chat_id": settings.telegram_chat_id, "text": text}
    if thread_id:
        payload["message_thread_id"] = thread_id
    try:
        with httpx.Client(timeout=10) as client:
            client.post(url, json=payload)
    except Exception:
        pass
