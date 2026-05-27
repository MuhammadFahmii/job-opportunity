from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime

from .config import settings
from .db import get_conn, now_iso
from .relevance import is_fresh_posted_age, is_relevant_job, is_relevant_record
from .schemas import JobPosting
from .sources.jobstreet import fetch_jobstreet_jobs
from .sources.linkedin import fetch_linkedin_jobs


@dataclass
class RunResult:
    source: str
    fetched: int
    inserted: int
    errors: str | None = None


def _upsert_job(conn, job: JobPosting) -> bool:
    now = now_iso()
    cur = conn.execute(
        """
        INSERT INTO jobs (source, source_job_id, url, title, company, location, posted_age, description, salary, first_seen_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, url) DO UPDATE SET
            title=excluded.title,
            company=excluded.company,
            location=excluded.location,
            posted_age=excluded.posted_age,
            description=excluded.description,
            salary=excluded.salary,
            last_seen_at=excluded.last_seen_at
        """,
        (
            job.source,
            job.source_job_id,
            str(job.url),
            job.title,
            job.company,
            job.location,
            job.posted_age,
            job.description,
            job.salary,
            now,
            now,
        ),
    )
    inserted = cur.rowcount > 0

    job_row = conn.execute(
        "SELECT id FROM jobs WHERE source = ? AND url = ?",
        (job.source, str(job.url)),
    ).fetchone()
    if not job_row:
        return inserted
    job_id = job_row["id"]
    conn.execute(
        """
        INSERT INTO review_status (job_id, status, notes, updated_at)
        VALUES (?, 'new', '', ?)
        ON CONFLICT(job_id) DO NOTHING
        """,
        (job_id, now),
    )
    return inserted


def _run_for_source(source: str, fetcher) -> RunResult:
    started = now_iso()
    run_id = None
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO runs (source, started_at) VALUES (?, ?)", (source, started)
        )
        run_id = cur.lastrowid

    try:
        jobs = fetcher()
        inserted_count = 0
        with get_conn() as conn:
            for job in jobs:
                is_relevant, _ = is_relevant_job(job)
                if not is_relevant:
                    continue
                if _upsert_job(conn, job):
                    inserted_count += 1
            conn.execute(
                "UPDATE runs SET finished_at=?, fetched_count=?, inserted_count=? WHERE id=?",
                (now_iso(), len(jobs), inserted_count, run_id),
            )
        return RunResult(source=source, fetched=len(jobs), inserted=inserted_count)
    except Exception as exc:
        with get_conn() as conn:
            conn.execute(
                "UPDATE runs SET finished_at=?, error=? WHERE id=?",
                (now_iso(), str(exc), run_id),
            )
        return RunResult(source=source, fetched=0, inserted=0, errors=str(exc))


def run_daily_fetch() -> list[RunResult]:
    results: list[RunResult] = []
    if settings.source_jobstreet_enabled:
        results.append(_run_for_source("jobstreet", fetch_jobstreet_jobs))
    if settings.source_linkedin_enabled:
        results.append(_run_for_source("linkedin", fetch_linkedin_jobs))
    export_today_csv()
    return results


def export_today_csv() -> str:
    settings.export_dir.mkdir(parents=True, exist_ok=True)
    filename = datetime.now().strftime("%Y-%m-%d-jobs.csv")
    out = settings.export_dir / filename
    with get_conn() as conn, out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["source", "title", "company", "location", "status", "url"]
        )
        rows = conn.execute(
            """
            SELECT j.source, j.title, j.company, j.location, j.posted_age, j.description, r.status, j.url
            FROM jobs j
            JOIN review_status r ON r.job_id = j.id
            ORDER BY j.last_seen_at DESC
            """
        ).fetchall()
        for row in rows:
            if not is_relevant_record(row["title"], row["description"]):
                continue
            if not is_fresh_posted_age(row["posted_age"]):
                continue
            writer.writerow(
                [
                    row["source"],
                    row["title"],
                    row["company"],
                    row["location"],
                    row["status"],
                    row["url"],
                ]
            )
    return str(out)
