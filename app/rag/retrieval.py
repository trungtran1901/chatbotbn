import hashlib
import logging
from typing import List, Optional, Dict
from app.embeddings import embedder
from app.qdrant_store import store
# from app.reranker import reranker
from app.keyword_extractor import extract_keywords

logger = logging.getLogger("rag.retrieval")


def _dedup_hits(hits):
    seen = set()
    result = []
    for h in hits:
        content_hash = h.payload.get("metadata", {}).get("content_hash")
        key = content_hash or h.id
        if key in seen:
            continue
        seen.add(key)
        result.append(h)
    return result


def _block_key(block: Dict) -> str:
    existing = block.get("content_hash")
    if existing:
        return existing
    return hashlib.sha256(block["text"].encode("utf-8")).hexdigest()


def retrieve_blocks(query: str, limit: int = 40, top_n: int = 8) -> List[Dict]:
    try:
        query_vector = embedder.embed_query(query)
    except Exception:
        logger.exception("Loi tao embedding cho cau hoi: %s", query)
        return []

    try:
        vector_hits = store.search(query_vector, query_filter=None, limit=limit)
    except Exception:
        logger.exception("Loi truy van Qdrant (vector search): %s", query)
        vector_hits = []

    keyword_hits = []
    keywords = extract_keywords(query)
    if keywords:
        try:
            keyword_hits = store.keyword_search(keywords, limit=20)
        except Exception:
            logger.exception("Loi truy van Qdrant (keyword search): %s", query)
            keyword_hits = []

    hits = _dedup_hits(list(vector_hits) + list(keyword_hits))
    if not hits:
        logger.warning("Khong tim thay ket qua trong Qdrant cho cau hoi: %s", query)
        return []

    # RERANK TAM THOI DISABLE - truyen thang docs khong qua rerank
    # documents = [h.payload.get("content", "") for h in hits]
    # try:
    #     ranked = reranker.rerank(query, documents, top_n=top_n)
    # except Exception:
    #     logger.exception("Loi goi reranker cho cau hoi: %s", query)
    #     ranked = []
    ranked = []

    if ranked:
        selected = [hits[idx] for idx, _ in ranked if idx < len(hits)]
    else:
        selected = hits[:top_n]

    blocks = []
    for h in selected:
        meta = h.payload.get("metadata", {})
        link = meta.get("source_link", "")
        attachment_url = meta.get("attachment_url", "")
        images = meta.get("images", []) or []

        extra_lines = []
        if meta.get("doc_type") == "pdf" and attachment_url:
            extra_lines.append(f"File PDF đính kèm: {attachment_url}")
        if images:
            extra_lines.append(f"Ảnh trong bài: {', '.join(images)}")
        extra_text = ("\n" + "\n".join(extra_lines)) if extra_lines else ""

        text = (
            f"[Tiêu đề: {meta.get('doc_title', '')} | Ngày: {meta.get('publish_date', '')} | "
            f"Link: {link or 'khong co'}]\n"
            f"{h.payload.get('content', '')}{extra_text}"
        )

        blocks.append({
            "text": text,
            "content_hash": meta.get("content_hash"),
            "source_link": link,
            "attachment_url": attachment_url,
            "images": images,
        })

    return blocks


def render_blocks(blocks: List[Dict]) -> Dict:
    allowed_links = set()
    for b in blocks:
        if b.get("source_link"):
            allowed_links.add(b["source_link"])
        if b.get("attachment_url"):
            allowed_links.add(b["attachment_url"])
        for img in b.get("images", []) or []:
            allowed_links.add(img)

    context_text = "\n\n---\n\n".join(b["text"] for b in blocks)
    return {"context_text": context_text, "allowed_links": allowed_links}


def merge_blocks(new_blocks: List[Dict], cached_blocks: List[Dict], max_total: int = 12) -> List[Dict]:
    merged = []
    seen_keys = set()

    for b in new_blocks:
        key = _block_key(b)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged.append(b)

    for b in cached_blocks:
        if len(merged) >= max_total:
            break
        key = _block_key(b)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged.append(b)

    return merged[:max_total]


def retrieve_context(query: str, limit: int = 40, top_n: int = 8) -> Optional[Dict]:
    blocks = retrieve_blocks(query, limit=limit, top_n=top_n)
    if not blocks:
        return None
    return render_blocks(blocks)