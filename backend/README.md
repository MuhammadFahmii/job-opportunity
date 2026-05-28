# Backend

Python backend for daily job fetch + CV scoring.

## Setup

```bash
cd backend
python3 -m pip install --user -r requirements.txt
python3 -m playwright install chromium
cp .env.example .env
```

If `python3 -m venv .venv` is available on your machine, you can use a virtualenv instead.

## Run API

```bash
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger UI: `http://localhost:8000/docs`  
ReDoc: `http://localhost:8000/redoc`

## Trigger Daily Fetch

```bash
python -m app.cli
```

Or via API:

```bash
curl -X POST http://localhost:8000/runs/daily
```

## Cron (08:00 WIB Daily)

```cron
0 8 * * * cd /home/heinz/united_tractors/job-opportunity/backend && /usr/bin/python3 -m app.cli >> /home/heinz/united_tractors/job-opportunity/backend/data/cron.log 2>&1
```

## Key Endpoints

- `GET /health`
- `POST /runs/daily`
- `GET /jobs?limit=100&status=new&source=jobstreet`
- `PATCH /jobs/{job_id}/review`
- `GET /runs`
