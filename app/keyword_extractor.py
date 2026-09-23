import re
import unicodedata
from typing import List

STOPWORDS = {
    "la", "gi", "nhu", "the", "nao", "o", "dau", "khi", "cua", "va", "voi",
    "cho", "duoc", "co", "khong", "nhung", "de", "tai", "ve", "trong", "tren",
    "nay", "do", "hay", "hoac", "thi", "ma", "vay", "sao", "bao", "nhieu",
    "cac", "mot", "hai", "ba", "ban", "toi", "minh", "ai", "gioi", "thieu",
    "cho toi", "hay cho", "biet",
}


def strip_diacritics(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = re.sub(r"[\u0300-\u036f]", "", text)
    text = text.replace("đ", "d").replace("Đ", "D")
    return text


def extract_keywords(question: str, max_keywords: int = 6) -> List[str]:
    cleaned = re.sub(r"[^\w\sÀ-ỹ]", " ", question, flags=re.UNICODE)
    tokens = cleaned.split()
    keywords = []
    for t in tokens:
        norm = strip_diacritics(t).lower()
        if len(t) < 3:
            continue
        if norm in STOPWORDS:
            continue
        keywords.append(t)
    seen = set()
    result = []
    for k in keywords:
        key = k.lower()
        if key not in seen:
            seen.add(key)
            result.append(k)
    return result[:max_keywords]