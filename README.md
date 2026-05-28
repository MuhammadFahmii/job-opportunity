# job-opportunity

FastAPI + Playwright app to fetch JobStreet listings, score relevance vs your CV, and automate “Easy Apply” flows.

## App Flow

1. Fetch jobs: `POST /runs/daily` scrapes JobStreet listing pages (configured in `backend/app/config.py`) into a local SQLite DB.
2. Score + list jobs: `GET /jobs` returns jobs with relevance/scoring derived from your CV + keywords.
3. Apply from UI: open `http://127.0.0.1:8000` and click `Auto Fill` on a JobStreet job.
4. Login-first automation:
   - Chromium opens to JobStreet sign-in (`https://id.jobstreet.com/login`) as the first view.
   - After you sign in, it navigates to the job URL and clicks `Easy Apply`.
   - It clicks through multi-step `Continue/Next` pages.
   - If `auto_submit=true`, it attempts `Submit application` and only returns `submitted` after detecting a confirmation; otherwise it returns a non-submitted status and saves a screenshot.

## What I Implemented / Changed

- Added repo-level `.gitignore` and removed generated artifacts (venv, `__pycache__`, Playwright/Chromium profile, screenshots, exports, local DB, `.env`) so they don’t get committed.
- JobStreet apply improvements:
  - Login page shown first on `Auto Fill`.
  - “Continue/Next” step clicking loop.
  - Final “Submit application” click with confirmation check (prevents false “submitted” results).
  - Screenshot capture + `needs_login` / `needs_manual_input` fallback statuses.
- Batch apply endpoint + UI entry point (optional): `POST /jobs/apply-batch`.

## Prereqs

- Python 3.10+
- Playwright Chromium (installed via Playwright)

## Setup

```bash
cd backend
python3 -m pip install --user -r requirements.txt
python3 -m playwright install chromium
cp .env.example .env
```

## Run

```bash
cd backend
python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- UI: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`

## Useful Endpoints

- `POST /runs/daily`
- `GET /jobs?limit=100&status=new&source=jobstreet`
- `POST /jobs/{job_id}/apply?auto_submit=false`
- `POST /auth/jobstreet/login`
- `POST /jobs/apply-batch?limit=10&auto_submit=false`
