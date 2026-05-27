import json
from pathlib import Path

from pydantic import BaseModel, Field


class ApplicantProfile(BaseModel):
    full_name: str
    email: str
    phone: str
    current_location: str | None = None
    expected_salary: str | None = None
    notice_period: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    default_answers: dict[str, str] = Field(default_factory=dict)


def load_profile(path: Path) -> ApplicantProfile:
    if not path.exists():
        raise FileNotFoundError(f"Applicant profile not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return ApplicantProfile.model_validate(data)
