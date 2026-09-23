import uuid
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from app.config import settings


class QdrantStore:
    def __init__(self):
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
        self.collection = settings.qdrant_collection

    def ensure_collection(self, vector_size: int):
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection not in collections:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE),
                hnsw_config=qm.HnswConfigDiff(m=32, ef_construct=200),
            )
            self._create_indexes()
            return
        info = self.client.get_collection(self.collection)
        current_size = info.config.params.vectors.size
        if current_size != vector_size:
            raise ValueError(
                f"Collection '{self.collection}' dang co vector size {current_size}, "
                f"nhung model embedding tra ve {vector_size}. "
                f"Doi ten collection khac trong .env hoac xoa collection cu de tao lai."
            )
        self._create_indexes()

    def _create_indexes(self):
        index_fields = [
            ("metadata.article_id", qm.PayloadSchemaType.KEYWORD),
            ("metadata.catalog_title", qm.PayloadSchemaType.KEYWORD),
            ("metadata.source_link", qm.PayloadSchemaType.KEYWORD),
            ("metadata.doc_title", qm.PayloadSchemaType.TEXT),
            ("content", qm.PayloadSchemaType.TEXT),
        ]
        for field_name, schema_type in index_fields:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field_name,
                    field_schema=schema_type,
                )
            except Exception:
                pass

    def upsert(self, vectors: List[List[float]], payloads: List[Dict[str, Any]]):
        if not vectors:
            return
        self.ensure_collection(len(vectors[0]))
        points = [
            qm.PointStruct(id=str(uuid.uuid4()), vector=vec, payload=payload)
            for vec, payload in zip(vectors, payloads)
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def search(
        self,
        query_vector: List[float],
        query_filter: Optional[qm.Filter] = None,
        limit: int = 30,
    ):
        return self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )

    def keyword_search(self, keywords: List[str], limit: int = 30):
        if not keywords:
            return []
        should = [
            qm.FieldCondition(key="content", match=qm.MatchText(text=kw))
            for kw in keywords
        ]
        query_filter = qm.Filter(should=should)
        results, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        return results


store = QdrantStore()