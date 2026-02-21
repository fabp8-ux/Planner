from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class QuotaRule:
    id: str
    pattern: str  # "on" | "everyday" | "weekday" | "weekend" | "custom"
    amount: int
    on_date: Optional[str] = None           # YYYY-MM-DD, for pattern="on"
    start: Optional[str] = None             # YYYY-MM-DD or None
    end: Optional[str] = None               # YYYY-MM-DD or None
    weekdays: Optional[List[int]] = None    # for pattern="custom": 0=Mon..6=Sun


@dataclass
class Item:
    id: str
    name: str
    cost: int = 0               # sessions required (leaf items)
    completed: int = 0          # sessions completed (tracked per item)
    parent_id: Optional[str] = None
    defer: Optional[str] = None # YYYY-MM-DD
    due: Optional[str] = None   # YYYY-MM-DD
    done: bool = False


@dataclass
class Session:
    kind: str      # "completed" | "scheduled" | "projected"
    item_id: str
    day: str       # YYYY-MM-DD
    count: int = 1


@dataclass
class DB:
    quota_rules: List[QuotaRule] = field(default_factory=list)
    items: Dict[str, Item] = field(default_factory=dict)
    queue: List[str] = field(default_factory=list)  # manual priority order
    sessions: List[Session] = field(default_factory=list)

    def to_jsonable(self) -> dict:
        return {
            "quota_rules": [asdict(r) for r in self.quota_rules],
            "items": {k: asdict(v) for k, v in self.items.items()},
            "queue": list(self.queue),
            "sessions": [asdict(s) for s in self.sessions],
        }

    @staticmethod
    def from_jsonable(raw: dict) -> "DB":
        from .models import QuotaRule, Item, Session  # avoid circular import in some tooling
        db = DB()
        db.quota_rules = [QuotaRule(**r) for r in raw.get("quota_rules", [])]
        db.items = {k: Item(**v) for k, v in raw.get("items", {}).items()}
        db.queue = raw.get("queue", [])
        db.sessions = [Session(**s) for s in raw.get("sessions", [])]
        return db
