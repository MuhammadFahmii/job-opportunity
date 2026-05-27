from __future__ import annotations

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..config import settings
from ..schemas import JobPosting


def _extract_title(card) -> tuple[str, str]:
    selectors = [
        "a[data-automation='jobTitle']",
        "h3[data-automation='jobTitle'] a",
        "h3 a",
        "a[data-automation='job-list-item-link-overlay']",
    ]
    for selector in selectors:
        el = card.select_one(selector)
        if not el:
            continue
        title = el.get_text(" ", strip=True)
        href = el.get("href", "")
        if title or href:
            return title, href

    for anchor in card.select("a[href]"):
        href = anchor.get("href", "")
        title = anchor.get_text(" ", strip=True)
        if "/job/" in href and title:
            return title, href
    return "", ""


def _is_fresh(posted_age: str | None) -> bool:
    if not posted_age:
        return True
    age = posted_age.lower().strip()
    # Keep past-24h equivalents from human labels.
    if "hour" in age or "h ago" in age:
        return True
    if "1 day" in age or "1d ago" in age:
        return True
    return False


def fetch_jobstreet_jobs(timeout_sec: int = 30) -> list[JobPosting]:
    results: list[JobPosting] = []
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }

    for path in settings.jobstreet_paths:
        url = urljoin(settings.jobstreet_base_url, path)
        resp = session.get(url, headers=headers, timeout=timeout_sec)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        cards = soup.select("article, div[data-job-id], li[data-job-id]")
        for card in cards:
            title, href = _extract_title(card)
            job_url = href if href.startswith("http") else urljoin(settings.jobstreet_base_url, href)
            if not job_url or not title:
                continue

            company = None
            company_el = card.select_one("[data-automation='jobCompany'], a[data-automation='jobCompany']")
            if company_el:
                company = company_el.get_text(" ", strip=True)

            location = None
            location_el = card.select_one("[data-automation='jobLocation']")
            if location_el:
                location = location_el.get_text(" ", strip=True)

            posted_age = None
            age_el = card.select_one("[data-automation='jobListingDate'], time")
            if age_el:
                posted_age = age_el.get_text(" ", strip=True)
            if not _is_fresh(posted_age):
                continue

            salary = None
            salary_el = card.select_one("[data-automation='jobSalary']")
            if salary_el:
                salary = salary_el.get_text(" ", strip=True)

            source_job_id = card.get("data-job-id")
            results.append(
                JobPosting(
                    source="jobstreet",
                    source_job_id=source_job_id,
                    url=job_url,
                    title=title,
                    company=company,
                    location=location,
                    posted_age=posted_age,
                    salary=salary,
                )
            )

    return results
