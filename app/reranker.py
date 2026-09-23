import time
import logging
from typing import List, Tuple
import httpx
from app.config import settings

logger = logging.getLogger("reranker")

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5
BATCH_SIZE = 15


class QwenReranker:
    def __init__(self):
        self.url = settings.qwen_rerank_url.rstrip("/")
        self.model = settings.qwen_rerank_model
        self.top_n = settings.qwen_rerank_top_n
        self.api_key = settings.qwen_rerank_api_key
        self.timeout = settings.qwen_rerank_timeout

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key != "EMPTY":
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _call_api(self, query: str, documents: List[str], top_n: int):
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self.url, headers=self._headers(), json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(f"Rerank loi {resp.status_code}: {resp.text[:300]}")
            return resp.json()

    def _call_batch_with_retry(self, query: str, documents: List[str], top_n: int):
        last_exc = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return self._call_api(query, documents, top_n)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Rerank batch that bai (lan %s/%s, %s docs): %s",
                    attempt, MAX_RETRIES, len(documents), exc,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)
        logger.error("Rerank batch that bai hoan toan, bo qua batch nay: %s", last_exc)
        return None

    def rerank(self, query: str, documents: List[str], top_n: int = None) -> List[Tuple[int, float]]:
        if not documents:
            return []

        top_n = top_n or self.top_n
        all_ranked: List[Tuple[int, float]] = []

        for batch_start in range(0, len(documents), BATCH_SIZE):
            batch_docs = documents[batch_start:batch_start + BATCH_SIZE]
            data = self._call_batch_with_retry(query, batch_docs, min(top_n, len(batch_docs)))
            if not data:
                continue

            results = data.get("results", data.get("data", []))
            for r in results:
                local_idx = r.get("index")
                score = r.get("relevance_score", r.get("score", 0.0))
                if local_idx is not None:
                    global_idx = batch_start + local_idx
                    all_ranked.append((global_idx, score))

        all_ranked.sort(key=lambda x: x[1], reverse=True)
        return all_ranked[:top_n]


reranker = QwenReranker()