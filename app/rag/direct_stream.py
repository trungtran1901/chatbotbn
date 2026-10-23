import json
import logging
import httpx
from typing import Iterator
from app.config import settings
from app.rag.mem0_client import search_memories

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
- Có thể dùng phần GHI NHỚ TỪ CÁC LƯỢT HỘI THOẠI TRƯỚC (nếu có) để hiểu ngữ cảnh câu hỏi hiện tại (ví dụ câu hỏi nối tiếp, đại từ thay thế), nhưng KHÔNG lấy dữ kiện/số liệu từ đó nếu nó không xuất hiện lại trong NGUỒN DỮ LIỆU của lượt hỏi hiện tại.
- Nếu người dùng hỏi về văn bản/tài liệu/ảnh đính kèm và đoạn NGUỒN DỮ LIỆU có "File PDF đính kèm" hoặc "Ảnh trong bài", hãy đính kèm đúng link đó trong câu trả lời.
- Cuối câu trả lời, LUÔN liệt kê "Nguồn tham khảo" gồm Tiêu đề và Link của các đoạn đã dùng để trả lời. Nếu Link là "khong co" thì bỏ qua link đó.
- Nếu NGUỒN DỮ LIỆU không chứa thông tin trả lời được câu hỏi, trả lời đúng nguyên văn:
"Tôi không tìm thấy câu trả lời trong các tài nguyên hiện có."
Không kèm phần Nguồn tham khảo trong trường hợp này.
- Viết bằng tiếng Việt, văn phong trung lập, báo chí, trả lời trực tiếp, ngắn gọn."""


def build_messages(session_id: str, user_message: str, raw_question: str):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    memories = search_memories(session_id, raw_question)
    memory_lines = [
        f"- {m.get('memory') or m.get('text') or ''}"
        for m in memories
        if (m.get("memory") or m.get("text"))
    ]
    if memory_lines:
        messages.append({
            "role": "system",
            "content": (
                "GHI NHỚ TỪ CÁC LƯỢT HỘI THOẠI TRƯỚC (chỉ dùng để hiểu ngữ cảnh câu hỏi, "
                "không dùng làm dữ kiện trả lời):\n" + "\n".join(memory_lines)
            ),
        })

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
    messages = build_messages(session_id, user_message, raw_user_input)
    payload = {
        "model": settings.openai_chat_model,
        "messages": messages,
        "stream": True,
    }

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
                        yield token
    except Exception:
        logger.exception("Loi khi goi chat/completions dang stream")
        raise


def chat_completion(session_id: str, user_message: str, raw_user_input: str) -> str:
    messages = build_messages(session_id, user_message, raw_user_input)
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