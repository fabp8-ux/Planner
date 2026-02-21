# Sudoku Streamlit Solver

A clean Streamlit Sudoku solver with a nicer, readable grid UI.

## Features
- Choose size: **4×4**, **9×9**, **16×16**
- Enter givens in a large, easy-to-read grid (blank or `0` = empty)
- Board validation (detects conflicts)
- Solve with backtracking + MRV heuristic (bitmask-based)

## Run locally
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## Notes
- For 16×16, values are `1..16` (not A–F symbols).
- If you want presets (example puzzles) or 16×16 hex-style symbols, extend `app.py`.
