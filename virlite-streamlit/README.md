# VIRLite (Streamlit) — a VIR-inspired session planner

This repo is a small, **VIR-inspired** planner implemented in Python with a **Streamlit** UI.

It models:
- **Quota rules**: how many "sessions" you can do per day (weekday/weekend/everyday/custom/on-date)
- **Items**: tasks with `cost` (sessions), optional `defer`/`due`, optional `parent`
- **Queue**: manual priority ordering (items not in the manual queue are ordered by due date)
- **Planning**: create a projected schedule using an **early** or **late** strategy

> ⚠️ This is not the original VIR project. It's an independent, compatible-in-spirit implementation.

## Quickstart

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## Data persistence

By default the app stores data in:

- `./data/virlite.json`

You can override with an env var:

```bash
export VIRLITE_DB=/absolute/path/to/virlite.json
```

## Project structure

- `app.py` — Streamlit UI
- `virlite/engine.py` — planning + quota logic
- `virlite/models.py` — dataclasses
- `virlite/storage.py` — JSON persistence helpers

## Roadmap ideas

- proper recurring items
- per-day item caps
- iCal export
- multi-user auth + DB backend (SQLite/Postgres)
