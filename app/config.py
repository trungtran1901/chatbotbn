from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = "EMPTY"
    openai_base_url: str = "http://localhost:8000/v1"
    openai_chat_model: str = "qwen3-32b"
    openai_stream_timeout: float = 300.0

    qwen_embed_base_url: str = "http://localhost:8001/v1"
    qwen_embed_api_key: str = "EMPTY"
    qwen_embed_model: str = "qwen3-embedding"
    qwen_embed_timeout: float = 120.0

    qwen_rerank_url: str = "http://localhost:8002/rerank"
    qwen_rerank_model: str = "qwen3-reranker"
    qwen_rerank_api_key: str = "EMPTY"
    qwen_rerank_top_n: int = 8
    qwen_rerank_timeout: float = 60.0

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "embeding_vector_v2"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "rag"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    ocr_pdf_url: str = ""
    ocr_pdf_bbox_format: str = "xyxy"
    ocr_img_url: str = ""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_sync_thread_id: int = 0
    telegram_report_thread_id: int = 0

    crawl_base_url: str = "https://bacninh.gov.vn"
    crawl_list_pages: int = 3
    chunk_size: int = 1000
    chunk_overlap: int = 150

    api_host: str = "0.0.0.0"
    api_port: int = 8080

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()