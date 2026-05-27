import re
from functools import lru_cache

from pypdf import PdfReader

from .config import settings


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=1)
def load_cv_text() -> str:
    reader = PdfReader(str(settings.cv_path))
    text = " ".join(page.extract_text() or "" for page in reader.pages)
    return _normalize(text)


def cv_keywords(top_n: int = 120) -> set[str]:
    words = load_cv_text().split()
    filtered = [w for w in words if len(w) > 2]
    # Keep simple frequency-based selection for deterministic behavior.
    counts: dict[str, int] = {}
    for token in filtered:
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return {word for word, _ in ranked[:top_n]}
