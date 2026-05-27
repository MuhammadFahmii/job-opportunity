from __future__ import annotations

from urllib.parse import quote_plus

from ..config import settings
from ..schemas import JobPosting


def linkedin_search_urls() -> list[str]:
    urls: list[str] = []
    for keyword in settings.linkedin_keywords:
        q = quote_plus(keyword)
        urls.append(
            "https://www.linkedin.com/jobs/search/"
            f"?keywords={q}&geoId={settings.linkedin_geo_id}&f_TPR=r86400"
        )
    return urls


def fetch_linkedin_jobs() -> list[JobPosting]:
    # Intentionally disabled by default and left as a stub:
    # LinkedIn blocks automated access and may restrict accounts.
    return []
