from pydantic import BaseModel, HttpUrl


class JobPosting(BaseModel):
    source: str
    source_job_id: str | None = None
    url: HttpUrl
    title: str
    company: str | None = None
    location: str | None = None
    posted_age: str | None = None
    description: str | None = None
    salary: str | None = None


class JobReviewUpdate(BaseModel):
    status: str
    notes: str = ""


class JobApplyResponse(BaseModel):
    attempt_id: int
    status: str
    message: str
    screenshot_path: str | None = None


class JobBatchApplyResponse(BaseModel):
    requested: int
    processed: int
    results: list[JobApplyResponse]


class JobStreetLoginResponse(BaseModel):
    status: str
    message: str
