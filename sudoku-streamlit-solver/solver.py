from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
import math

Board = List[List[int]]  # 0 = empty, values 1..N


@dataclass(frozen=True)
class SudokuSpec:
    n: int          # board size: N x N (e.g., 9)
    base: int       # subgrid size: base x base (e.g., 3)
    full_mask: int  # bits 1..N set


def _spec(n: int) -> SudokuSpec:
    """Validate N and build basic constants."""
    base = int(math.isqrt(n))
    if base * base != n:
        raise ValueError(f"Invalid size: {n}. Only perfect squares are supported (4, 9, 16, ...).")
    # bits 1..N set => (1<<(N+1)) - 2
    full_mask = (1 << (n + 1)) - 2
    return SudokuSpec(n=n, base=base, full_mask=full_mask)


def _box_index(r: int, c: int, base: int) -> int:
    return (r // base) * base + (c // base)


def validate_board(board: Board) -> Tuple[bool, str]:
    """
    Checks:
      - board is N x N
      - values in 0..N
      - no duplicate values in any row/col/box (ignoring 0)
    """
    n = len(board)
    if n == 0 or any(len(row) != n for row in board):
        return False, "Board must be square (N x N)."

    try:
        spec = _spec(n)
    except ValueError as e:
        return False, str(e)

    row_used = [0] * n
    col_used = [0] * n
    box_used = [0] * n

    for r in range(n):
        for c in range(n):
            v = board[r][c]
            if not isinstance(v, int):
                return False, f"Invalid value at ({r+1},{c+1}): {v} (not an integer)."
            if v < 0 or v > n:
                return False, f"Invalid value at ({r+1},{c+1}): {v} (allowed: 0..{n})."
            if v == 0:
                continue

            bit = 1 << v
            b = _box_index(r, c, spec.base)

            if (row_used[r] & bit) or (col_used[c] & bit) or (box_used[b] & bit):
                return False, f"Conflict: value {v} appears twice in a row/column/box (cell {r+1},{c+1})."

            row_used[r] |= bit
            col_used[c] |= bit
            box_used[b] |= bit

    return True, "OK"


def solve_sudoku(board: Board) -> Optional[Board]:
    """
    Solve Sudoku with backtracking + MRV (minimum remaining values) using bitmasks.
    Returns a NEW solved board or None if unsolvable / invalid.
    """
    n = len(board)
    ok, _ = validate_board(board)
    if not ok:
        return None

    spec = _spec(n)
    base = spec.base
    full = spec.full_mask

    # Copy board so we don't mutate caller data
    grid = [row[:] for row in board]

    row_used = [0] * n
    col_used = [0] * n
    box_used = [0] * n
    empties: List[Tuple[int, int]] = []

    # Initialize masks
    for r in range(n):
        for c in range(n):
            v = grid[r][c]
            if v == 0:
                empties.append((r, c))
            else:
                bit = 1 << v
                b = _box_index(r, c, base)
                row_used[r] |= bit
                col_used[c] |= bit
                box_used[b] |= bit

    def candidates_mask(r: int, c: int) -> int:
        b = _box_index(r, c, base)
        used = row_used[r] | col_used[c] | box_used[b]
        return full & ~used

    def dfs() -> bool:
        # Find empty cell with minimum candidates (MRV)
        best_idx = -1
        best_mask = 0
        best_count = 10**9

        for i, (r, c) in enumerate(empties):
            if grid[r][c] != 0:
                continue
            cm = candidates_mask(r, c)
            cnt = cm.bit_count()
            if cnt == 0:
                return False
            if cnt < best_count:
                best_count = cnt
                best_idx = i
                best_mask = cm
                if cnt == 1:
                    break

        if best_idx == -1:
            return True  # solved

        r, c = empties[best_idx]
        b = _box_index(r, c, base)

        cm = best_mask
        while cm:
            lsb = cm & -cm
            v = lsb.bit_length() - 1  # because bit is (1<<v)
            cm ^= lsb

            bit = 1 << v
            # place
            grid[r][c] = v
            row_used[r] |= bit
            col_used[c] |= bit
            box_used[b] |= bit

            if dfs():
                return True

            # undo
            grid[r][c] = 0
            row_used[r] ^= bit
            col_used[c] ^= bit
            box_used[b] ^= bit

        return False

    return grid if dfs() else None
