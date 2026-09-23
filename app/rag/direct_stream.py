import json
import logging
import httpx
from typing import Iterator
from app.config import settings
from app.db.postgres import load_chat_history, save_chat_message

logger = logging.getLogger("rag.direct_chat")

SYSTEM_PROMPT = """Bạn là một trợ lý AI chuyên trả lời câu hỏi dựa trên các đoạn chunk thông tin được cung cấp sẵn trong phần NGUỒN DỮ LIỆU bên dưới.

Mỗi đoạn NGUỒN DỮ LIỆU có định dạng:
[Tiêu đề: ... | Ngày: ... | Link: ...]
nội dung
(có thể kèm dòng "File PDF đính kèm: ..." hoặc "Ảnh trong bài: ...")

Quy tắc bắt buộc:
- CHỈ được dùng thông tin có trong NGUỒN DỮ LIỆU được cung cấp trong tin nhắn của người dùng.
- TUYỆT ĐỐI KHÔNG dùng kiến thức có sẵn của bạn, kể cả khi bạn biết câu trả lời.
- KHÔNG suy diễn, không thêm thông tin ngoài NGUỒN DỮ LIỆU.
- Có thể dùng lịch sử hội thoại trước đó để hiểu ngữ cảnh câu hỏi hiện tại (ví dụ câu hỏi nối tiếp, đại từ thay thế), nhưng KHÔNG lấy dữ kiện/số liệu từ câu trả lời trước nếu nó không xuất hiện lại trong NGUỒN DỮ LIỆU của lượt hỏi hiện tại.
- Nếu người dùng hỏi về văn bản/tài liệu/ảnh đính kèm và đoạn NGUỒN DỮ LIỆU có "File PDF đính kèm" hoặc "Ảnh trong bài", hãy đính kèm đúng link đó trong câu trả lời.
- Cuối câu trả lời, LUÔN liệt kê "Nguồn tham khảo" gồm Tiêu đề và Link của các đoạn đã dùng để trả lời. Nếu Link là "khong co" thì bỏ qua link đó.
- Nếu NGUỒN DỮ LIỆU không chứa thông tin trả lời được câu hỏi, trả lời đúng nguyên văn:
"Tôi không tìm thấy câu trả lời trong các tài nguyên hiện có."
Không kèm phần Nguồn tham khảo trong trường hợp này.
- Viết bằng tiếng Việt, văn phong trung lập, báo chí, trả lời trực tiếp, ngắn gọn."""


def build_messages(session_id: str, user_message: str, history_limit: int = 10):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    history = load_chat_history(session_id, limit=history_limit)
    for row in history:
        messages.append({"role": row["role"], "content": row["content"]})

    messages.append({"role": "user", "content": user_message})
    return messages


def _build_headers():
    headers = {"Content-Type": "application/json"}
    api_key = settings.openai_api_key
    if api_key and api_key != "EMPTY":
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _completions_url() -> str:
    return f"{settings.openai_base_url.rstrip('/')}/chat/completions"


def stream_chat_completion(session_id: str, user_message: str, raw_user_input: str) -> Iterator[str]:
    messages = build_messages(session_id, user_message)
    payload = {
        "model": settings.openai_chat_model,
        "messages": messages,
        "stream": True,
    }

    full_answer = ""
    try:
        with httpx.Client(timeout=settings.openai_stream_timeout) as client:
            with client.stream("POST", _completions_url(), headers=_build_headers(), json=payload) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    token = choices[0].get("delta", {}).get("content", "")
                    if token:
                        full_answer += token
                        yield token
    except Exception:
        logger.exception("Loi khi goi chat/completions dang stream")
        raise
    finally:
        if full_answer:
            save_chat_message(session_id, "user", raw_user_input)
            save_chat_message(session_id, "assistant", full_answer)


def chat_completion(session_id: str, user_message: str) -> str:
    messages = build_messages(session_id, user_message)
    payload = {
        "model": settings.openai_chat_model,
        "messages": messages,
        "stream": False,
    }

    with httpx.Client(timeout=settings.openai_stream_timeout) as client:
        resp = client.post(_completions_url(), headers=_build_headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]["content"]