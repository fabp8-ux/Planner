# Sudoku Streamlit Solver

Streamlit-App zum Lösen von Sudoku-Varianten (4×4, 9×9, 16×16).

## Features
- Größe auswählbar
- Eingabe per Grid (leer oder 0 = unbekannt)
- Konfliktprüfung (Zeile/Spalte/Box)
- Lösung per Backtracking + MRV-Heuristik (bitmask-basiert)

## Lokal starten
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## Hinweise
- Für 16×16 werden Zahlen 1..16 genutzt (keine A-F Darstellung).
- Sehr große Größen (z.B. 25×25) sind nicht vorgesehen und können langsam werden.
