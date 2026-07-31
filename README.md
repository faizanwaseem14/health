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

## Running the frontend

```bash
cd frontend
npm install
npm run dev
```

Then open the URL Vite prints (usually http://127.0.0.1:5173/). You should
see a plain "MedVault" placeholder page — no real screens yet, that's
expected for Day 1.

## Project status

This is Day 1: foundation only (project structure, database schema,
authentication wiring, storage wiring). No file upload, OCR, AI extraction,
or results screens exist yet — those come later.
