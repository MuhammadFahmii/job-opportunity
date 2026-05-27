from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .apply import list_applyable_job_ids, run_apply_for_job, run_apply_for_jobs, run_jobstreet_login
from .config import settings
from .db import get_conn, init_db, now_iso
from .pipeline import export_today_csv, run_daily_fetch
from .relevance import is_fresh_posted_age, is_relevant_record
from .schemas import JobApplyResponse, JobBatchApplyResponse, JobReviewUpdate, JobStreetLoginResponse

app = FastAPI(
    title="Job Opportunity Backend API",
    description=(
        "API for daily job ingestion, CV matching, review workflow, and run tracking.\n\n"
        "Interactive docs:\n"
        "- Swagger UI: `/docs`\n"
        "- ReDoc: `/redoc`"
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1, "displayRequestDuration": True},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/health", tags=["System"])
def health() -> dict:
    return {"status": "ok", "time": now_iso()}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.post("/runs/daily", tags=["Runs"])
def run_daily() -> dict:
    results = run_daily_fetch()
    return {
        "results": [result.__dict__ for result in results],
        "csv": export_today_csv(),
    }


@app.get("/jobs", tags=["Jobs"])
def list_jobs(
    limit: int = 100,
    status: str | None = None,
    source: str | None = None,
    relevant_only: bool = settings.relevant_only_default,
    fresh_only: bool = settings.fresh_only_default,
) -> dict:
    query = """
        SELECT j.id, j.source, j.title, j.company, j.location, j.posted_age, j.description, j.url,
               r.status, r.notes, j.last_seen_at
        FROM jobs j
        JOIN review_status r ON r.job_id = j.id
    """
    where = []
    args = []
    if status:
        where.append("r.status = ?")
        args.append(status)
    if source:
        where.append("j.source = ?")
        args.append(source)
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY j.last_seen_at DESC LIMIT ?"
    args.append(limit)

    with get_conn() as conn:
        rows = conn.execute(query, tuple(args)).fetchall()
    items = [dict(row) for row in rows]
    if relevant_only:
        items = [
            item
            for item in items
            if is_relevant_record(item["title"], item["description"])
        ]
    if fresh_only:
        items = [
            item
            for item in items
            if is_fresh_posted_age(item["posted_age"])
        ]
    return {"items": items[:limit]}


@app.patch("/jobs/{job_id}/review", tags=["Jobs"])
def update_review(job_id: int, payload: JobReviewUpdate) -> dict:
    if payload.status not in {"new", "saved", "applied", "skipped"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    with get_conn() as conn:
        exists = conn.execute("SELECT id FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Job not found")
        conn.execute(
            """
            UPDATE review_status
            SET status = ?, notes = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (payload.status, payload.notes, now_iso(), job_id),
        )
    return {"ok": True}


@app.post("/jobs/{job_id}/apply", tags=["Jobs"], response_model=JobApplyResponse)
def apply_job(job_id: int, auto_submit: bool = False) -> JobApplyResponse:
    result = run_apply_for_job(job_id, auto_submit=auto_submit)
    return JobApplyResponse(
        attempt_id=result.attempt_id,
        status=result.status,
        message=result.message,
        screenshot_path=result.screenshot_path,
    )


@app.post("/jobs/apply-batch", tags=["Jobs"], response_model=JobBatchApplyResponse)
def apply_jobs_batch(
    limit: int = 100,
    status: str = "new",
    include_saved: bool = False,
    relevant_only: bool = settings.relevant_only_default,
    fresh_only: bool = settings.fresh_only_default,
    auto_submit: bool = False,
) -> JobBatchApplyResponse:
    statuses = ("new", "saved") if include_saved else (status,)
    job_ids = list_applyable_job_ids(
        statuses=statuses,
        limit=limit,
        relevant_only=relevant_only,
        fresh_only=fresh_only,
    )
    batch = run_apply_for_jobs(job_ids, auto_submit=auto_submit)
    return JobBatchApplyResponse(
        requested=batch.requested,
        processed=batch.processed,
        results=[
            JobApplyResponse(
                attempt_id=result.attempt_id,
                status=result.status,
                message=result.message,
                screenshot_path=result.screenshot_path,
            )
            for result in batch.results
        ],
    )


@app.post(
    "/auth/jobstreet/login",
    tags=["Auth"],
    response_model=JobStreetLoginResponse,
)
def login_jobstreet(timeout_sec: int = 300) -> JobStreetLoginResponse:
    result = run_jobstreet_login(
        browser_profile_dir=settings.browser_profile_dir,
        headless=settings.apply_headless,
        timeout_sec=timeout_sec,
    )
    return JobStreetLoginResponse(status=result.status, message=result.message)


@app.get("/runs", tags=["Runs"])
def list_runs(limit: int = 20) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return {"items": [dict(row) for row in rows]}
