import re
import time
import logging
import httpx
from bs4 import BeautifulSoup
from app.config import settings
from app.http_retry import call_with_retry

logger = logging.getLogger("crawler.list_page")


def normalize_date(text: str):
    if not text:
        return None
    m = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", text)
    if not m:
        return None
    day, month, year = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
    return f"{day}-{month}-{year}"


def _fetch_list_page_raw(page: int) -> str:
    url = (
        f"{settings.crawl_base_url}/search"
        f"?p_p_id=searchjournalarticle&p_p_lifecycle=0"
        f"&_searchjournalarticle_keyWord=&cur={page}"
    )
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def fetch_list_page(page: int):
    html = call_with_retry(_fetch_list_page_raw, page)

    soup = BeautifulSoup(html, "lxml")
    items = soup.select(".list-group-item")
    results = []
    for item in items:
        a = item.select_one("a")
        date_span = item.select_one("span.news-description")
        if not a:
            continue
        link = a.get("href", "")
        if link and not link.startswith("http"):
            link = settings.crawl_base_url + link
        results.append(
            {
                "title": a.get_text(strip=True),
                "link": link,
                "date": normalize_date(date_span.get_text(strip=True) if date_span else ""),
            }
        )
    return results


def iter_all_pages(start_page: int = 1, max_pages: int = 100000, delay_seconds: float = 0.3):
    page = start_page
    empty_streak = 0
    while page <= max_pages:
        try:
            items = fetch_list_page(page)
        except Exception:
            logger.exception("Khong the lay trang %s sau khi da thu lai, bo qua trang nay", page)
            items = []
            empty_streak += 1
            if empty_streak >= 3:
                break
            page += 1
            if delay_seconds:
                time.sleep(delay_seconds)
            continue

        if not items:
            empty_streak += 1
            if empty_streak >= 3:
                break
        else:
            empty_streak = 0
            yield page, items
        page += 1
        if delay_seconds:
            time.sleep(delay_seconds)


def fetch_page_html(url: str) -> str:
    def _fetch():
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text
    return call_with_retry(_fetch)