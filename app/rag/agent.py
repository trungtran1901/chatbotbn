import os
os.environ.setdefault("AGNO_TELEMETRY", "false")

from urllib.parse import quote_plus
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.storage.postgres import PostgresStorage
from app.config import settings

SYSTEM_PROMPT = """Bạn là một trợ lý AI chuyên trả lời câu hỏi dựa trên các đoạn chunk thông tin được cung cấp sẵn trong phần NGUỒN DỮ LIỆU bên dưới.

Mỗi đoạn NGUỒN DỮ LIỆU có định dạng:
[Tiêu đề: ... | Ngày: ... | Link: ...]
nội dung
(có thể kèm dòng "File PDF đính kèm: ..." hoặc "Ảnh trong bài: ...")

Quy tắc bắt buộc:
- CHỈ được dùng thông tin có trong NGUỒN DỮ LIỆU được cung cấp trong tin nhắn của người dùng.
- TUYỆT ĐỐI KHÔNG dùng kiến thức có sẵn của bạn, kể cả khi bạn biết câu trả lời.
- KHÔNG suy diễn, không thêm thông tin ngoài NGUỒN DỮ LIỆU.
- Nếu người dùng hỏi về văn bản/tài liệu/ảnh đính kèm và đoạn NGUỒN DỮ LIỆU có "File PDF đính kèm" hoặc "Ảnh trong bài", hãy đính kèm đúng link đó trong câu trả lời.
- Cuối câu trả lời, LUÔN liệt kê "Nguồn tham khảo" gồm Tiêu đề và Link của các đoạn đã dùng để trả lời. Nếu Link là "khong co" thì bỏ qua link đó.
- Nếu NGUỒN DỮ LIỆU không chứa thông tin trả lời được câu hỏi, trả lời đúng nguyên văn:
"Tôi không tìm thấy câu trả lời trong các tài nguyên hiện có."
Không kèm phần Nguồn tham khảo trong trường hợp này.
- Viết bằng tiếng Việt, văn phong trung lập, báo chí, trả lời trực tiếp, ngắn gọn."""


def build_storage() -> PostgresStorage:
    user = quote_plus(settings.postgres_user)
    password = quote_plus(settings.postgres_password)
    db_url = (
        f"postgresql+psycopg2://{user}:{password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )
    return PostgresStorage(
        table_name="agno_sessions",
        db_url=db_url,
        schema="ragv2",
        auto_upgrade_schema=True,
    )


def build_agent(session_id: str, stream: bool = False) -> Agent:
    model_kwargs = {
        "id": settings.openai_chat_model,
        "api_key": settings.openai_api_key or "EMPTY",
        "base_url": settings.openai_base_url,
    }
    if stream:
        model_kwargs["stream"] = True

    try:
        model = OpenAIChat(**model_kwargs)
    except TypeError:
        model_kwargs.pop("stream", None)
        model = OpenAIChat(**model_kwargs)

    try:
        agent_kwargs = dict(
            model=model,
            instructions=SYSTEM_PROMPT,
            session_id=session_id,
            storage=build_storage(),
            add_history_to_messages=True,
            num_history_runs=6,
            read_chat_history=False,
            markdown=False,
            stream=stream,
            telemetry=False,
        )
        return Agent(**agent_kwargs)
    except TypeError:
        agent_kwargs.pop("telemetry", None)
        return Agent(**agent_kwargs)