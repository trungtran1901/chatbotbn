import re
import httpx
from app.config import settings


def _clean(text: str) -> str:
    text = text.replace("\r", "").replace("\n", " ").replace("||", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def ocr_pdf(file_bytes: bytes, filename: str) -> str:
    with httpx.Client(timeout=180) as client:
        resp = client.post(
            settings.ocr_pdf_url,
            params={"bbox_format": settings.ocr_pdf_bbox_format, "getContent": "true"},
            files={"file": (filename, file_bytes, "application/pdf")},
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"OCR PDF loi {resp.status_code}: {resp.text[:500]}")
        data = resp.json()

    pages = data.get("pages", [])
    page_texts = []
    for page in pages:
        page_content = (page.get("content") or "").strip()
        if page_content:
            page_index = page.get("page_index", len(page_texts))
            page_texts.append(f"--- Page {page_index + 1} ---\n{page_content}")

    full_text = "\n\n".join(page_texts)
    return _clean(full_text) if full_text else ""


def ocr_image(file_bytes: bytes, filename: str) -> str:
    with httpx.Client(timeout=120) as client:
        resp = client.post(
            settings.ocr_img_url,
            params={"getContent": "true"},
            files={"file": (filename, file_bytes, "image/png")},
        )
        resp.raise_for_status()
        data = resp.json()
    if "pages" in data:
        pages = data.get("pages", [])
        page_texts = [p.get("content", "") for p in pages if p.get("content")]
        return _clean(" ".join(page_texts))
    return _clean(data.get("content", ""))