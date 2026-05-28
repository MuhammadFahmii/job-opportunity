# job-opportunity

FastAPI + Playwright helper to fetch JobStreet listings, score relevance vs your CV, and automate “Easy Apply” flows.

## What’s Done So Far

- Added a repo-level `.gitignore` to exclude build artifacts, caches, Playwright reports, local browser profiles, local DB, exports, `.env`, and PDFs.
- Cleaned generated files from the workspace (venv, `__pycache__`, Playwright/Chromium profile data, screenshots, exports, local DB).
- Improved JobStreet apply automation:
  - Opens JobStreet sign-in first when you click `Auto Fill`.
  - Clicks through multi-step `Continue/Next` flows.
  - Attempts final `Submit application`, and only marks `submitted` after detecting a confirmation.
  - Captures a screenshot and returns a manual/needs-login status when it can’t safely continue.
- Added batch apply endpoint + UI entry point (optional) to iterate through jobs (single-job flow still works).
- Committed and pushed cleaned sources to GitHub.

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

## Use (JobStreet Auto Fill)

1. Open `http://127.0.0.1:8000`
2. Fetch jobs (via `POST /runs/daily` or the UI if you’re using it)
3. Click `Auto Fill` on a JobStreet job
4. Chromium opens on the JobStreet sign-in page
5. Sign in, then the automation continues to the job page and tries:
   - `Easy Apply`
   - `Continue`/`Next` steps
   - `Submit application` (when enabled / possible)

If the flow can’t proceed (needs login, needs manual fields, or submit can’t be confirmed), it returns a non-submitted status and saves a screenshot under `backend/data/apply-screenshots/` (ignored by git).

## Useful Endpoints

- `POST /runs/daily`
- `GET /jobs?limit=100&status=new&source=jobstreet`
- `POST /jobs/{job_id}/apply?auto_submit=false`
- `POST /auth/jobstreet/login`
- `POST /jobs/apply-batch?limit=10&auto_submit=false`

