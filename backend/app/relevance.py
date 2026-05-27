import re

from .config import settings
from .cv import cv_keywords
from .schemas import JobPosting


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _blob(title: str | None, description: str | None) -> str:
    return f"{_normalize(title)} {_normalize(description)}".strip()


def _matches_phrase(text: str, phrases: list[str]) -> list[str]:
    return [phrase for phrase in phrases if phrase in text]


def _matches_cv_terms(text: str) -> list[str]:
    combined = set(settings.relevance_cv_keywords).union(cv_keywords())
    return [term for term in combined if term in text]


def is_relevant_job(job: JobPosting) -> tuple[bool, str]:
    text = _blob(job.title, job.description)
    if not text:
        return False, "empty title/description"

    role_matches = _matches_phrase(text, settings.relevance_role_keywords)
    cv_matches = _matches_cv_terms(text)

    if role_matches:
        reason = f"role={', '.join(role_matches[:3])}"
        if cv_matches:
            reason += f"; cv={', '.join(cv_matches[:4])}"
        return True, reason

    if len(cv_matches) >= 2:
        return True, f"cv={', '.join(cv_matches[:4])}"

    return False, "not web/backend/fullstack/software-engineer related"


def is_relevant_record(title: str | None, description: str | None) -> bool:
    text = _blob(title, description)
    if not text:
        return False
    if _matches_phrase(text, settings.relevance_role_keywords):
        return True
    return len(_matches_cv_terms(text)) >= 2


def is_fresh_posted_age(posted_age: str | None) -> bool:
    if not posted_age:
        return True

    age = posted_age.lower().strip()
    if re.fullmatch(r"\d+\s*h ago", age):
        return True
    if re.fullmatch(r"\d+\s*hours? ago", age):
        return True
    if age in {"1 day ago", "1d ago", "1 day"}:
        return True
    return False
