# Agno RAG (thay thế n8n)

## Kiến trúc

- `app/crawler`: crawl danh sách bài viết bacninh.gov.vn, trích xuất nội dung, OCR PDF/ảnh, chunk, embed (qwen3-embedding self-host chuẩn OpenAI), upsert Qdrant, ghi metadata Postgres, chống trùng, báo cáo Telegram.
- `app/rag`: Agent Agno dùng OpenAI chat model, 1 tool `search_documents_tool` gộp: trích từ khoá bằng code (không gọi LLM) -> filter Qdrant -> embed câu hỏi (qwen3-embedding) -> search -> rerank (qwen3-rerank) -> trả context. Chỉ 1 lần gọi LLM cho mỗi câu hỏi (thay vì 2 lần AI Agent như n8n cũ).
- Memory: PostgresStorage của Agno theo `session_id`, tự lưu/lấy lịch sử hội thoại.
- `app/api.py`: FastAPI `/chat` (streaming), `/chat/sync`, `/crawl`.

## Cài đặt

```bash
cp .env.example .env
pip install -r requirements.txt
psql -f sql/schema.sql
python main_crawl.py --pages 3
python main_api.py
```

## Docker

```bash
docker compose up --build
```

## Gọi thử

```bash
curl -X POST http://localhost:8080/chat/sync \
  -H "Content-Type: application/json" \
  -d '{"chatinput":"Lễ hội Kinh Dương Vương","sessionId":"demo"}'
```
