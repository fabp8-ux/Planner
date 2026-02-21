from __future__ import annotations

import math
from typing import List, Tuple

import streamlit as st

from solver import solve_sudoku, validate_board

SUPPORTED_SIZES = [4, 9, 16]
DEFAULT_SIZE = 9


def cell_key(n: int, r: int, c: int) -> str:
    # include N so changing size doesn't collide with old widget state
    return f"cell_{n}_{r}_{c}"


def base_of(n: int) -> int:
    b = int(math.isqrt(n))
    if b * b != n:
        raise ValueError("Only perfect-square sizes are supported (4, 9, 16, ...).")
    return b


def reset_board(n: int) -> None:
    for r in range(n):
        for c in range(n):
            st.session_state[cell_key(n, r, c)] = ""


def parse_board(n: int) -> Tuple[List[List[int]], List[str]]:
    """
    Read cell widget values from session_state and build an int board.
    Returns (board, errors). Empty string or '0' => 0.
    """
    errors: List[str] = []
    board: List[List[int]] = [[0] * n for _ in range(n)]

    for r in range(n):
        for c in range(n):
            raw = str(st.session_state.get(cell_key(n, r, c), "")).strip()
            if raw == "":
                board[r][c] = 0
                continue

            if not raw.isdigit():
                errors.append(f"Cell ({r+1},{c+1}) is not a number: '{raw}'")
                continue

            v = int(raw)
            if v == 0:
                board[r][c] = 0
            elif 1 <= v <= n:
                board[r][c] = v
            else:
                errors.append(f"Cell ({r+1},{c+1}) out of range: {v} (allowed 1..{n}, or blank/0).")

    return board, errors


def board_to_csv(board: List[List[int]]) -> bytes:
    lines = [",".join(str(v) for v in row) for row in board]
    return ("\n".join(lines) + "\n").encode("utf-8")


def render_board_html(board: List[List[int]], n: int, title: str) -> None:
    """
    Render a clean Sudoku grid with thick subgrid borders using HTML/CSS.
    """
    base = base_of(n)

    html = [f"<div class='sudoku-wrap'><div class='sudoku-title'>{title}</div>"]
    html.append("<table class='sudoku'>")
    for r in range(n):
        html.append("<tr>")
        for c in range(n):
            v = board[r][c]
            cls = []
            if r % base == 0:
                cls.append("top")
            if c % base == 0:
                cls.append("left")
            if (r + 1) % base == 0:
                cls.append("bottom")
            if (c + 1) % base == 0:
                cls.append("right")
            cls_attr = f" class='{' '.join(cls)}'" if cls else ""
            disp = "" if v == 0 else str(v)
            html.append(f"<td{cls_attr}>{disp}</td>")
        html.append("</tr>")
    html.append("</table></div>")

    st.markdown("".join(html), unsafe_allow_html=True)


st.set_page_config(page_title="Sudoku Solver", layout="wide")

st.markdown(
    """
<style>
/* Make inputs larger and centered */
div[data-testid="stTextInput"] input {
    text-align: center;
    font-size: 22px !important;
    height: 2.8rem;
    padding: 0.25rem 0.25rem;
}
div[data-testid="stTextInput"] { margin-bottom: 0rem; }

/* Sudoku HTML output */
.sudoku-wrap { margin-top: 0.5rem; }
.sudoku-title { font-size: 1.05rem; font-weight: 600; margin: 0.5rem 0 0.35rem 0; }
table.sudoku { border-collapse: collapse; }
table.sudoku td {
    width: 2.8rem;
    height: 2.8rem;
    text-align: center;
    vertical-align: middle;
    font-size: 22px;
    border: 1px solid rgba(49, 51, 63, 0.25);
}
table.sudoku td.top { border-top: 3px solid rgba(49, 51, 63, 0.65); }
table.sudoku td.left { border-left: 3px solid rgba(49, 51, 63, 0.65); }
table.sudoku td.bottom { border-bottom: 3px solid rgba(49, 51, 63, 0.65); }
table.sudoku td.right { border-right: 3px solid rgba(49, 51, 63, 0.65); }

/* Spacer columns (visual separation) */
.sudoku-spacer { height: 0.25rem; }
</style>
""",
    unsafe_allow_html=True,
)

st.title("Sudoku Solver")
st.caption("Leave cells blank (or enter 0). Allowed values: 1..N. Click **Solve** to get the solution.")

# ---- Sidebar controls ----
with st.sidebar:
    st.header("Settings")
    if "size" not in st.session_state:
        st.session_state.size = DEFAULT_SIZE

    size = st.selectbox("Grid size", SUPPORTED_SIZES, index=SUPPORTED_SIZES.index(st.session_state.size))

    if size != st.session_state.size:
        st.session_state.size = size
        reset_board(size)

    st.divider()
    if st.button("Reset board", use_container_width=True):
        reset_board(st.session_state.size)

n = int(st.session_state.size)
base = base_of(n)

# ---- Input grid in a form (prevents rerun on every keystroke) ----
st.subheader("Input")

with st.form("sudoku_form", clear_on_submit=False):
    # Build column widths with spacer columns between subgrids
    spacer_w = 0.18
    widths = []
    for g in range(base):
        widths.extend([1.0] * base)
        if g != base - 1:
            widths.append(spacer_w)

    for r in range(n):
        cols = st.columns(widths, gap="small")
        col_idx = 0
        for c in range(n):
            # insert a spacer column after each subgrid block
            if c > 0 and c % base == 0:
                col_idx += 1  # skip spacer column
            with cols[col_idx]:
                key = cell_key(n, r, c)
                if key not in st.session_state:
                    st.session_state[key] = ""
                st.text_input(
                    label="",
                    key=key,
                    label_visibility="collapsed",
                    placeholder="",
                )
            col_idx += 1

        # horizontal spacer between subgrid blocks of rows
        if (r + 1) % base == 0 and (r + 1) != n:
            st.markdown("<div class='sudoku-spacer'></div>", unsafe_allow_html=True)

    colA, colB, colC = st.columns([1, 1, 2])
    validate_clicked = colA.form_submit_button("Validate", use_container_width=True)
    solve_clicked = colB.form_submit_button("Solve", use_container_width=True)
    # third column intentionally empty / for future buttons

# ---- Actions ----
if validate_clicked or solve_clicked:
    board, parse_errors = parse_board(n)
    if parse_errors:
        st.error("Please fix these input issues:")
        st.write("\n".join([f"- {e}" for e in parse_errors]))
    else:
        ok, msg = validate_board(board)
        if not ok:
            st.error(msg)
        else:
            st.success("Board looks valid.")
            render_board_html(board, n, "Current board (preview)")

            if solve_clicked:
                solution = solve_sudoku(board)
                if solution is None:
                    st.error("No solution found (the puzzle may be unsolvable).")
                else:
                    st.success("Solution found ✅")
                    render_board_html(solution, n, "Solution")

                    st.download_button(
                        "Download solution as CSV",
                        data=board_to_csv(solution),
                        file_name=f"sudoku_solution_{n}x{n}.csv",
                        mime="text/csv",
                        use_container_width=False,
                    )
else:
    # Always show a preview (readable) even before submitting
    board, _ = parse_board(n)
    render_board_html(board, n, "Current board (preview)")
