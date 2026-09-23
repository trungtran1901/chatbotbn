import time
import logging
from typing import List
import httpx
from app.config import settings

logger = logging.getLogger("embeddings")

BATCH_SIZE = 16
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 3


class QwenEmbedder:
    def __init__(self):
        self.base_url = settings.qwen_embed_base_url.rstrip("/")
        self.model = settings.qwen_embed_model
        self.api_key = settings.qwen_embed_api_key
        self.timeout = settings.qwen_embed_timeout

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key != "EMPTY":
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}/v1/embeddings",
                headers=self._headers(),
                json={"model": self.model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()

        if "embeddings" in data:
            return data["embeddings"]
        if "data" in data:
            return [item["embedding"] for item in data["data"]]
        raise ValueError(f"Unsupported embedding response: {data}")

    def _call_with_retry(self, texts: List[str]) -> List[List[float]]:
        last_exc = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return self._call_api(texts)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Embedding request that bai (lan %s/%s): %s",
                    attempt, MAX_RETRIES, exc,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)
        raise last_exc

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        all_vectors = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            vectors = self._call_with_retry(batch)
            all_vectors.extend(vectors)
        return all_vectors

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]


embedder = QwenEmbedder()