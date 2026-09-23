# Hướng dẫn cài đặt và chạy local

## 1. Yêu cầu

- Python 3.11
- PostgreSQL đang chạy (local hoặc remote)
- Qdrant đang chạy
- Server local chuẩn OpenAI cho chat model (vd: vLLM, Ollama OpenAI-compat, TGI...)
- Server embedding chuẩn OpenAI (qwen3-embedding self-host)
- Server rerank (qwen3-rerank)

## 2. Tạo virtual environment

### Windows (PowerShell)

```powershell
cd agno-rag
python -m venv venv
venv\Scripts\Activate.ps1
```

### Windows (cmd)

```cmd
cd agno-rag
python -m venv venv
venv\Scripts\activate.bat
```

### Linux / macOS

```bash
cd agno-rag
python3 -m venv venv
source venv/bin/activate
```

Kiểm tra đã vào venv (prompt hiện `(venv)`):

```bash
which python
python --version
```

Thoát venv khi cần:

```bash
deactivate
```

## 3. Cài dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Cấu hình biến môi trường

```bash
cp .env.example .env
```

Mở `.env` và chỉnh các giá trị:

```
OPENAI_API_KEY=EMPTY
OPENAI_BASE_URL=http://<ip-server-chat>:<port>/v1
OPENAI_CHAT_MODEL=<ten-model-tren-server-local>

QWEN_EMBED_BASE_URL=http://<ip-server-embed>:<port>/v1
QWEN_EMBED_API_KEY=EMPTY
QWEN_EMBED_MODEL=<ten-model-embedding>

QWEN_RERANK_URL=http://<ip-server-rerank>:<port>/rerank
QWEN_RERANK_MODEL=<ten-model-rerank>

QDRANT_URL=http://<ip-qdrant>:6333
QDRANT_COLLECTION=embeding_vector_v2

POSTGRES_HOST=<ip-postgres>
POSTGRES_PORT=5432
POSTGRES_DB=rag
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

## 5. Khởi tạo database

```bash
psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -f sql/schema.sql
```

Hoặc dùng connection string:

```bash
psql "postgresql://postgres:postgres@localhost:5432/rag" -f sql/schema.sql
```

## 6. Chạy thử crawl dữ liệu (tuỳ chọn)

```bash
python main_crawl.py --pages 2
```

Kết quả insert/skip/error sẽ in ra console và gửi Telegram (nếu đã cấu hình `TELEGRAM_BOT_TOKEN`).

## 7. Chạy API RAG

```bash
python main_api.py
```

Mặc định chạy tại `http://0.0.0.0:8080`.

Test nhanh:

```bash
curl -X POST http://localhost:8080/health
```

```bash
curl -X POST http://localhost:8080/chat/sync \
  -H "Content-Type: application/json" \
  -d '{"chatinput":"Lễ hội Kinh Dương Vương","sessionId":"demo1"}'
```

Test streaming:

```bash
curl -N -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"chatinput":"Lễ hội Kinh Dương Vương","sessionId":"demo1"}'
```

## 8. Chạy crawler theo lịch (background, tuỳ chọn)

```bash
python scheduler.py
```

Mặc định crawl mỗi 6 giờ, và chạy ngay 1 lần khi khởi động.

---

# Hướng dẫn build & deploy bằng Docker

## 1. Yêu cầu

- Docker
- Docker Compose plugin (`docker compose version`)

## 2. Chuẩn bị file môi trường

```bash
cp .env.example .env
```

Chỉnh `.env` giống bước 4 ở phần local, lưu ý:

- `POSTGRES_HOST` để `postgres` (tên service trong `docker-compose.yml`) nếu dùng Postgres do compose tạo.
- Các URL server local (chat/embedding/rerank/Qdrant) phải là IP mà container Docker truy cập được (không dùng `localhost` nếu server đó chạy ngoài Docker network, dùng IP LAN hoặc `host.docker.internal`).

## 3. Build image

```bash
docker compose build
```

## 4. Khởi động toàn bộ hệ thống

```bash
docker compose up -d
```

Service khởi tạo:

- `api`: FastAPI RAG, expose cổng `8080`
- `crawler`: chạy `scheduler.py`, tự crawl định kỳ
- `postgres`: Postgres 16, tự chạy `sql/schema.sql` khi khởi tạo volume lần đầu

## 5. Kiểm tra logs

```bash
docker compose logs -f api
docker compose logs -f crawler
```

## 6. Test API sau khi container chạy

```bash
curl -X POST http://localhost:8080/chat/sync \
  -H "Content-Type: application/json" \
  -d '{"chatinput":"Lễ hội Kinh Dương Vương","sessionId":"demo1"}'
```

## 7. Build lại sau khi sửa code

```bash
docker compose build api crawler
docker compose up -d --force-recreate api crawler
```

## 8. Dừng hệ thống

```bash
docker compose down
```

Xoá luôn dữ liệu Postgres (volume):

```bash
docker compose down -v
```

## 9. Chạy crawl thủ công trong container

```bash
docker compose exec crawler python main_crawl.py --pages 3
```

## 10. Build image độc lập (không dùng compose)

```bash
docker build -t agno-rag:latest .
docker run -d --name agno-rag-api \
  --env-file .env \
  -p 8080:8080 \
  agno-rag:latest
```
