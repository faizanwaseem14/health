# MedVault

A private health-records web app. This repo is a **monorepo**: the backend
and frontend live side by side, in one repo, but run as two separate
programs on your machine.

```
health/
├── backend/    FastAPI (Python) — the API server and database logic
└── frontend/   React + Vite — the web UI (empty scaffold for now)
```

## Running the backend

```bash
cd backend
python3 -m venv .venv          # create an isolated Python environment (once)
source .venv/bin/activate      # activate it (do this every new terminal session)
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/ in your browser. You should see a small
JSON message confirming the server is running.

## Dev tools (backend)

Install once (in addition to the steps above):

```bash
cd backend
pip install -r requirements-dev.txt
```

Then, from `backend/`:

```bash
ruff check .      # lint - finds likely bugs (unused imports, etc.)
black .           # format - auto-fixes code style
pytest            # run the test suite
```

## Database migrations (Alembic)

The database schema (all 13 tables) lives as version-controlled files in
`backend/alembic/versions/`, not as something you build by hand in Neon.

Create the tables in your own Neon database:

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

This reads `DATABASE_URL` from your `backend/.env`, so make sure that's
filled in first (see `SETUP.md`). If it worked, you'll see log lines
ending in `Running upgrade  -> ..., create initial schema`.

Later, whenever a model in `backend/app/models/` changes, generate a new
migration with:

```bash
alembic revision --autogenerate -m "describe the change"
```

Always read the generated file in `alembic/versions/` before running
`alembic upgrade head` - autogenerate is very good but not perfect, and
should be treated as a draft to review, not something to trust blindly.

## Running the frontend

The frontend is the **HealthVault** web app (React + Vite). See
[`frontend/README.md`](frontend/README.md) for full setup steps, including a
Windows-specific walkthrough. Quick version (Mac/Linux):

```bash
cd frontend
cp .env.example .env    # first time only
npm install
npm run dev
```

Then open the URL Vite prints (usually http://127.0.0.1:5173/).

## Project status

Day 1 and Day 2 (backend foundation through AI extraction, the trust chain,
and test-name/unit knowledge) are complete — see `backend/`'s test suite
(275 tests). Day 3 (the HealthVault frontend) is in progress: the app shell,
theme system, and landing page exist; login, upload, and results screens are
still to come.
