from typing import List


def split_text(text: str, chunk_size: int, chunk_overlap: int, separator: str = ".") -> List[str]:
    if not text:
        return []
    parts = [p.strip() for p in text.split(separator) if p.strip()]
    chunks = []
    current = ""
    for part in parts:
        candidate = f"{current}{separator}{part}" if current else part
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            overlap_text = current[-chunk_overlap:] if chunk_overlap else ""
            current = f"{overlap_text}{separator}{part}".strip()
    if current:
        chunks.append(current.strip())
    return chunks
