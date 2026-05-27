from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "job-opportunity-backend"
    db_path: Path = ROOT_DIR / "backend" / "data" / "jobs.db"
    cv_path: Path = ROOT_DIR / "cv-fahmi.pdf"
    export_dir: Path = ROOT_DIR / "backend" / "exports"
    applicant_profile_path: Path = ROOT_DIR / "backend" / "data" / "applicant_profile.json"
    browser_profile_dir: Path = ROOT_DIR / "backend" / "data" / "browser-profile"
    apply_screenshots_dir: Path = ROOT_DIR / "backend" / "data" / "apply-screenshots"

    timezone: str = "Asia/Jakarta"
    relevant_only_default: bool = True
    fresh_only_default: bool = True

    source_jobstreet_enabled: bool = True
    source_linkedin_enabled: bool = False
    apply_headless: bool = False
    apply_timeout_sec: int = 180

    jobstreet_base_url: str = "https://id.jobstreet.com"
    jobstreet_paths: list[str] = Field(
        default_factory=lambda: [
            "/jobs/in-Jakarta",
            "/software-engineer-jobs/in-Jakarta",
            "/backend-developer-jobs/in-Jakarta",
            "/full-stack-developer-jobs/in-Jakarta",
            "/web-developer-jobs/in-Jakarta",
        ]
    )

    relevance_role_keywords: list[str] = Field(
        default_factory=lambda: [
            "website",
            "web",
            "web developer",
            "software engineer",
            "software developer",
            "backend",
            "backend developer",
            "backend engineer",
            "fullstack",
            "full stack",
            "fullstack developer",
            "full stack developer",
        ]
    )
    relevance_cv_keywords: list[str] = Field(
        default_factory=lambda: [
            "python",
            "django",
            "flask",
            "fastapi",
            "laravel",
            "php",
            "javascript",
            "typescript",
            "react",
            "node",
            "nodejs",
            "sql",
            "mysql",
            "postgresql",
            "api",
            "rest",
            "git",
            "docker",
        ]
    )

    linkedin_geo_id: str = "104370960"
    linkedin_keywords: list[str] = Field(
        default_factory=lambda: ["data analyst", "business analyst"]
    )

    model_config = SettingsConfigDict(env_prefix="JOB_", env_file=".env", extra="ignore")


settings = Settings()
