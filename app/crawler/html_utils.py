import re
from bs4 import BeautifulSoup


def extract_body(html: str) -> str:
    match = re.search(r"<body[^>]*>([\s\S]*?)</body>", html, re.IGNORECASE)
    return match.group(1) if match else html


def strip_noise_tags(html: str) -> str:
    pattern = re.compile(
        r"<script[^>]*>([\s\S]*?)</script>|<style[^>]*>([\s\S]*?)</style>|"
        r"<noscript[^>]*>([\s\S]*?)</noscript>|<!--[\s\S]*?-->|"
        r"<iframe[^>]*>([\s\S]*?)</iframe>|<object[^>]*>([\s\S]*?)</object>|"
        r"<embed[^>]*>([\s\S]*?)</embed>|<video[^>]*>([\s\S]*?)</video>|"
        r"<audio[^>]*>([\s\S]*?)</audio>|<svg[^>]*>([\s\S]*?)</svg>",
        re.IGNORECASE,
    )
    return pattern.sub("", html)


def extract_article(html: str):
    cleaned = strip_noise_tags(extract_body(html))
    soup = BeautifulSoup(cleaned, "lxml")

    catalog_tag = soup.select_one("h4.title_tab")
    catalog_title = catalog_tag.get_text(strip=True) if catalog_tag else ""

    title_tag = soup.select_one("h1.title#contentDetailTitleId") or soup.select_one("h1.title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    date_tag = soup.select_one("div.date_time span")
    publish_date = ""
    if date_tag:
        date_text = date_tag.get_text(strip=True)
        date_match = re.search(r"(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})", date_text)
        publish_date = date_match.group(1) if date_match else date_text

    sapo_tag = soup.select_one("div.supdetail#sapoDetailId")
    sapo_text = sapo_tag.get_text(separator="\n", strip=True) if sapo_tag else ""

    content_tag = soup.select_one("div.textdetail#contentDetail")
    content_text = content_tag.get_text(separator="\n", strip=True) if content_tag else ""

    content = "\n".join(filter(None, [sapo_text, content_text]))
    content = re.sub(r"\s{2,}", " ", content).strip()

    search_scope = content_tag or soup

    images = []
    for img in search_scope.find_all("img"):
        src = img.get("src", "")
        if not src or "icon" in src or "logo" in src:
            continue
        if src.startswith("/"):
            src = "https://bacninh.gov.vn" + src
        images.append(src)

    pdf_links = []
    search_areas = [sapo_tag, content_tag]
    for area in search_areas:
        if not area:
            continue
        for a in area.find_all("a", href=True):
            href = a["href"]
            if re.search(r"\.pdf(?:[/?]|$)", href, re.IGNORECASE):
                if href.startswith("/"):
                    href = "https://bacninh.gov.vn" + href
                if href not in pdf_links:
                    pdf_links.append(href)

    return {
        "catalog_title": catalog_title or "Khac",
        "title": title or "Không có tiêu đề",
        "publish_date": publish_date,
        "content": content,
        "images": images,
        "pdf_links": pdf_links,
        "source": "BNP",
    }