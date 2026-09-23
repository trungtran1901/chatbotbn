import re
import time
import hashlib
import logging
from datetime import datetime, timezone
from urllib.parse import unquote
import httpx
from app.config import settings
from app.crawler.list_page import fetch_list_page, fetch_page_html, iter_all_pages
from app.crawler.html_utils import extract_article
from app.crawler.splitter import split_text
from app.crawler.ocr import ocr_pdf
from app.http_retry import call_with_retry
from app.embeddings import embedder
from app.qdrant_store import store
from app.db.postgres import (
    upsert_catalog,
    register_document,
    is_link_done,
    mark_link_pending,
    mark_link_status,
)
from app.notifier import send_telegram

logger = logging.getLogger("crawler.pipeline")


def build_text(article: dict) -> str:
    return (
        f"Đăng tải ngày {article['publish_date']} với tiêu đề {article['title']} "
        f"và nội dung bài báo {article['content']}"
    )


def build_pdf_text(article_title: str, publish_date: str, pdf_text: str) -> str:
    return (
        f"Đăng tải ngày {publish_date} với tiêu đề {article_title} "
        f"và nội dung văn bản pdf đính kèm {pdf_text}"
    )


def extract_article_id(link: str) -> str:
    match = re.search(r"/details/(\d+)/", link)
    if match:
        return match.group(1)
    return hashlib.sha256(link.encode("utf-8")).hexdigest()[:16]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_pdf_filename(pdf_url: str) -> str:
    match = re.search(r"([^/]+\.pdf)", pdf_url, re.IGNORECASE)
    if match:
        return unquote(match.group(1))
    return "document.pdf"


def download_bytes(url: str) -> bytes:
    def _download():
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.content
    return call_with_retry(_download)


def embed_and_store(chunks, base_metadata: dict):
    if not chunks:
        return 0
    vectors = embedder.embed_documents(chunks)
    total_chunks = len(chunks)
    payloads = []
    for idx, chunk in enumerate(chunks):
        meta = dict(base_metadata)
        meta["chunk_index"] = idx
        meta["chunk_total"] = total_chunks
        meta["chunk_length"] = len(chunk)
        meta["content_hash"] = content_hash(chunk)
        payloads.append({"content": chunk, "metadata": meta})
    store.upsert(vectors, payloads)
    return total_chunks


def process_pdf_attachments(article, link: str, article_id: str, catalog_title: str, title: str, publish_date: str, crawled_at: str):
    total_inserted = 0
    for pdf_url in article.get("pdf_links", []):
        if is_link_done(pdf_url):
            continue
        mark_link_pending(pdf_url)
        try:
            pdf_bytes = download_bytes(pdf_url)
            pdf_filename = extract_pdf_filename(pdf_url)
            pdf_text = ocr_pdf(pdf_bytes, pdf_filename)
            if not pdf_text:
                mark_link_status(pdf_url, "empty")
                continue

            text = build_pdf_text(title, publish_date, pdf_text)
            chunks = split_text(text, settings.chunk_size, settings.chunk_overlap, separator="--- Page")

            base_metadata = {
                "doc_type": "pdf",
                "doc_title": title,
                "publish_date": publish_date,
                "catalog_title": catalog_title,
                "source_link": link,
                "attachment_url": pdf_url,
                "article_id": article_id,
                "crawled_at": crawled_at,
                "source_domain": settings.crawl_base_url,
            }
            total_inserted += embed_and_store(chunks, base_metadata)
            mark_link_status(pdf_url, "done")
        except Exception as exc:
            logger.exception("Loi xu ly pdf dinh kem: %s", pdf_url)
            mark_link_status(pdf_url, "failed", str(exc))
    return total_inserted


def process_article(link: str, fallback_title: str, fallback_date: str):
    html = fetch_page_html(link)
    article = extract_article(html)

    title = article["title"] or fallback_title
    publish_date = article["publish_date"] or fallback_date or ""
    catalog_title = article["catalog_title"] or "Khac"
    catalog_no_diacritics = catalog_title.lower().replace(" ", "")
    article_id = extract_article_id(link)
    crawled_at = datetime.now(timezone.utc).isoformat()

    upsert_catalog(catalog_title, catalog_no_diacritics)

    text = build_text(article)
    chunks = split_text(text, settings.chunk_size, settings.chunk_overlap, separator=".")

    base_metadata = {
        "doc_type": "txt",
        "doc_title": title,
        "publish_date": publish_date,
        "catalog_title": catalog_title,
        "source_link": link,
        "article_id": article_id,
        "images": article.get("images", []),
        "attachment_pdfs": article.get("pdf_links", []),
        "crawled_at": crawled_at,
        "source_domain": settings.crawl_base_url,
    }

    inserted_chunks = embed_and_store(chunks, base_metadata)

    pdf_inserted = process_pdf_attachments(
        article, link, article_id, catalog_title, title, publish_date, crawled_at
    )

    if inserted_chunks == 0 and pdf_inserted == 0:
        return {"status": "empty", "title": title}

    register_document(catalog_title, title, publish_date, "txt", article["source"], link)
    return {"status": "inserted", "title": title}


def process_link(link: str, fallback_title: str, fallback_date: str):
    if is_link_done(link):
        return "skipped_resume"

    mark_link_pending(link)
    try:
        result = process_article(link, fallback_title, fallback_date)
        mark_link_status(link, "done")
        return result["status"]
    except Exception as exc:
        logger.exception("Loi khi xu ly link: %s", link)
        mark_link_status(link, "failed", str(exc))
        raise


def run_crawl(num_pages: int = None):
    inserted, skipped, errors = [], [], []
    full_crawl = num_pages is None or num_pages == 0

    if full_crawl:
        page_iterator = iter_all_pages(start_page=1)
    else:
        def limited_pages():
            for page in range(1, num_pages + 1):
                try:
                    items = fetch_list_page(page)
                except Exception:
                    logger.exception("Khong the lay trang %s sau khi da thu lai, bo qua trang nay", page)
                    items = []
                yield page, items
        page_iterator = limited_pages()

    for page, items in page_iterator:
        logger.info("Dang xu ly trang %s, %s bai viet", page, len(items))
        for item in items:
            link = item.get("link")
            if not link:
                continue
            try:
                status = process_link(link, item.get("title", ""), item.get("date", ""))
                if status == "inserted":
                    inserted.append(item.get("title"))
                else:
                    skipped.append(item.get("title"))
            except Exception as exc:
                logger.exception("Loi xu ly link, bo qua va tiep tuc: %s", link)
                errors.append({"title": item.get("title"), "link": link, "error": str(exc)})

    report_lines = [
        "Hoàn thành đồng bộ dữ liệu (toàn bộ)" if full_crawl else "Hoàn thành đồng bộ dữ liệu",
        f"Thành công: {len(inserted)} bản ghi",
        f"Bỏ qua (đã tồn tại): {len(skipped)} bản ghi",
        f"Lỗi: {len(errors)} bản ghi",
    ]
    send_telegram("\n".join(report_lines), settings.telegram_report_thread_id)

    return {"inserted": inserted, "skipped": skipped, "errors": errors}