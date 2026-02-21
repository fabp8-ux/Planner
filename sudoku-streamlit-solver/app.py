from __future__ import annotations

import pandas as pd
import streamlit as st

from solver import solve_sudoku, validate_board


SUPPORTED_SIZES = [4, 9, 16]


def _empty_df(n: int) -> pd.DataFrame:
    # Nullable integer dtype allows blank cells (pd.NA)
    df = pd.DataFrame([[pd.NA] * n for _ in range(n)], columns=[str(i) for i in range(1, n + 1)])
    return df.astype("Int64")


def _df_to_board(df: pd.DataFrame, n: int) -> list[list[int]]:
    board: list[list[int]] = []
    for r in range(n):
        row: list[int] = []
        for c in range(n):
            v = df.iat[r, c]
            if pd.isna(v):
                row.append(0)
            else:
                row.append(int(v))
        board.append(row)
    return board


def _board_to_df(board: list[list[int]]) -> pd.DataFrame:
    n = len(board)
    df = pd.DataFrame(board, columns=[str(i) for i in range(1, n + 1)])
    return df


st.set_page_config(page_title="Sudoku Solver", layout="wide")

st.title("Sudoku-Solver (Streamlit)")
st.caption("Leere Felder leer lassen (oder 0). Werte: 1..N.")

# ---- Size selection & session state ----
if "size" not in st.session_state:
    st.session_state.size = 9
if "grid" not in st.session_state:
    st.session_state.grid = _empty_df(st.session_state.size)

left, right = st.columns([1, 2], gap="large")

with left:
    size = st.selectbox("Sudoku-Größe", SUPPORTED_SIZES, index=SUPPORTED_SIZES.index(st.session_state.size))
    if size != st.session_state.size:
        st.session_state.size = size
        st.session_state.grid = _empty_df(size)

    st.markdown("### Aktionen")
    colA, colB = st.columns(2)
    solve_clicked = colA.button("✅ Lösen", use_container_width=True)
    reset_clicked = colB.button("🧹 Reset", use_container_width=True)

    if reset_clicked:
        st.session_state.grid = _empty_df(st.session_state.size)
        st.rerun()

with right:
    n = st.session_state.size

    st.markdown("### Eingabe")
    # Column config with numeric bounds
    col_cfg = {
        str(i): st.column_config.NumberColumn(
            label=str(i),
            min_value=0,   # allow 0, though blank is nicer; 0 will be treated as empty
            max_value=n,
            step=1,
            help=f"Erlaubt: leer/0 oder 1..{n}",
        )
        for i in range(1, n + 1)
    }

    edited = st.data_editor(
        st.session_state.grid,
        use_container_width=True,
        hide_index=True,
        column_config=col_cfg,
        key="grid_editor",
        height=540 if n <= 9 else 620,
    )

    # Persist edited grid
    st.session_state.grid = edited

# ---- Solve ----
if solve_clicked:
    n = st.session_state.size
    board = _df_to_board(st.session_state.grid, n)

    ok, msg = validate_board(board)
    if not ok:
        st.error(msg)
    else:
        solution = solve_sudoku(board)
        if solution is None:
            st.error("Keine Lösung gefunden (Puzzle ist ggf. unlösbar oder inkonsistent).")
        else:
            st.success("Lösung gefunden ✅")
            sol_df = _board_to_df(solution)
            st.markdown("### Lösung")
            st.dataframe(sol_df, use_container_width=True, hide_index=True)

            # Optional: download solution
            csv = sol_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Lösung als CSV herunterladen",
                data=csv,
                file_name=f"sudoku_solution_{n}x{n}.csv",
                mime="text/csv",
            )
