from __future__ import annotations

import json
import os
from typing import Optional

from .models import DB


def default_db_path() -> str:
    # Repo-local by default (works well for Streamlit Community Cloud too).
    return os.path.join(".", "data", "virlite.json")


def resolve_db_path() -> str:
    return os.environ.get("VIRLITE_DB", default_db_path())


def ensure_parent_dir(path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)


def load_db(path: Optional[str] = None) -> DB:
    p = path or resolve_db_path()
    if not os.path.exists(p):
        return DB()
    with open(p, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return DB.from_jsonable(raw)


def save_db(db: DB, path: Optional[str] = None) -> None:
    p = path or resolve_db_path()
    ensure_parent_dir(p)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(db.to_jsonable(), f, ensure_ascii=False, indent=2)
