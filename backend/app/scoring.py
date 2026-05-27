import re

from .cv import cv_keywords
from .schemas import JobPosting


def _norm(text: str | None) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def score_job(job: JobPosting) -> tuple[float, str]:
    cv_terms = cv_keywords()
    title = _norm(job.title)
    desc = _norm(job.description)
    blob = f"{title} {desc}"
    tokens = set(blob.split())
    if not tokens:
        return 0.0, "empty job content"

    overlap = cv_terms.intersection(tokens)
    # Use job token size as denominator so list-page data is still scorable.
    base = len(overlap) / max(min(len(tokens), 40), 1)

    title_bonus = 0.0
    for key in ("analyst", "data", "business", "product", "python", "sql"):
        if key in title:
            title_bonus += 0.08
    score = min(base * 1.1 + title_bonus, 1.0)
    reason = (
        f"overlap={len(overlap)}/{len(tokens)} "
        f"base={base:.3f} title_bonus={title_bonus:.2f}"
    )
    return round(score, 4), reason
