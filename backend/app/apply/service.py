from __future__ import annotations

from dataclasses import dataclass

from ..config import settings
from ..db import get_conn, now_iso
from .jobstreet import run_jobstreet_apply
from .profile import load_profile
from .status import APPLY_FAILED, APPLY_OPENED, APPLY_SUBMITTED, TERMINAL_SUCCESS


@dataclass
class ApplyResult:
    attempt_id: int
    status: str
    message: str
    screenshot_path: str | None = None


@dataclass
class BatchApplyResult:
    requested: int
    processed: int
    results: list[ApplyResult]


def _create_attempt(job_id: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO apply_attempts (job_id, status, message, started_at)
            VALUES (?, ?, '', ?)
            """,
            (job_id, APPLY_OPENED, now_iso()),
        )
        return int(cur.lastrowid)


def _finish_attempt(
    attempt_id: int, status: str, message: str, screenshot_path: str | None
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE apply_attempts
            SET status = ?, message = ?, screenshot_path = ?, finished_at = ?
            WHERE id = ?
            """,
            (status, message, screenshot_path, now_iso(), attempt_id),
        )


def _mark_job_status(job_id: int, status: str, note: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE review_status
            SET status = ?, notes = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (status, note, now_iso(), job_id),
        )


def _load_job(job_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, source, url FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    if not row:
        raise ValueError("Job not found")
    return dict(row)


def list_applyable_job_ids(
    statuses: tuple[str, ...] = ("new",),
    limit: int = 100,
    relevant_only: bool = True,
    fresh_only: bool = True,
) -> list[int]:
    from ..relevance import is_fresh_posted_age, is_relevant_record

    placeholders = ",".join("?" for _ in statuses)
    query = f"""
        SELECT j.id, j.title, j.description, j.posted_age
        FROM jobs j
        JOIN review_status r ON r.job_id = j.id
        WHERE j.source = 'jobstreet'
          AND r.status IN ({placeholders})
        ORDER BY j.last_seen_at DESC
        LIMIT ?
    """
    args: list[object] = [*statuses, limit]
    with get_conn() as conn:
        rows = conn.execute(query, tuple(args)).fetchall()

    job_ids: list[int] = []
    for row in rows:
        item = dict(row)
        if relevant_only and not is_relevant_record(item["title"], item["description"]):
            continue
        if fresh_only and not is_fresh_posted_age(item["posted_age"]):
            continue
        job_ids.append(int(item["id"]))
    return job_ids


def run_apply_for_job(job_id: int, auto_submit: bool = False) -> ApplyResult:
    job = _load_job(job_id)
    attempt_id = _create_attempt(job_id)

    try:
        if job["source"] != "jobstreet":
            raise ValueError("Auto apply currently supports JobStreet only")
        if not settings.cv_path.exists():
            raise ValueError(f"CV file not found: {settings.cv_path}")

        profile = load_profile(settings.applicant_profile_path)
        execution = run_jobstreet_apply(
            job_url=job["url"],
            profile=profile,
            cv_path=settings.cv_path,
            browser_profile_dir=settings.browser_profile_dir,
            screenshots_dir=settings.apply_screenshots_dir,
            headless=settings.apply_headless,
            timeout_sec=settings.apply_timeout_sec,
            auto_submit=auto_submit,
        )
        _finish_attempt(
            attempt_id,
            execution.status,
            execution.message,
            execution.screenshot_path,
        )
        if execution.status in TERMINAL_SUCCESS:
            if execution.status == APPLY_SUBMITTED:
                _mark_job_status(job_id, "applied", "Application auto-submitted.")
            else:
                _mark_job_status(job_id, "saved", "Autofill completed. Review before submit.")
        return ApplyResult(
            attempt_id=attempt_id,
            status=execution.status,
            message=execution.message,
            screenshot_path=execution.screenshot_path,
        )
    except Exception as exc:
        message = str(exc)
        _finish_attempt(attempt_id, APPLY_FAILED, message, None)
        return ApplyResult(
            attempt_id=attempt_id,
            status=APPLY_FAILED,
            message=message,
            screenshot_path=None,
        )


def run_apply_for_jobs(
    job_ids: list[int],
    auto_submit: bool = False,
) -> BatchApplyResult:
    results: list[ApplyResult] = []
    for job_id in job_ids:
        results.append(run_apply_for_job(job_id, auto_submit=auto_submit))
    return BatchApplyResult(
        requested=len(job_ids),
        processed=len(results),
        results=results,
    )
