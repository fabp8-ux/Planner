from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from .models import DB, Item, QuotaRule


ALL_DIGITS = set(range(1, 10))


def parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def fmt_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def daterange(d0: date, d1: date) -> List[date]:
    out: List[date] = []
    cur = d0
    while cur <= d1:
        out.append(cur)
        cur += timedelta(days=1)
    return out


# -----------------------------
# Quota
# -----------------------------

def rule_applies(rule: QuotaRule, d: date) -> bool:
    if rule.pattern == "on":
        return bool(rule.on_date) and parse_date(rule.on_date) == d

    start = parse_date(rule.start)
    end = parse_date(rule.end)
    if start and d < start:
        return False
    if end and d > end:
        return False

    wd = d.weekday()  # 0=Mon..6=Sun

    if rule.pattern == "everyday":
        return True
    if rule.pattern == "weekday":
        return wd <= 4
    if rule.pattern == "weekend":
        return wd >= 5
    if rule.pattern == "custom":
        return rule.weekdays is not None and wd in set(rule.weekdays)
    return False


def quota_for_day(db: DB, d: date) -> int:
    """
    Later rules override earlier rules (priority = later in list),
    mirroring VIR's "last override wins" idea.
    """
    amt = 0
    matched = False
    for r in db.quota_rules:
        if rule_applies(r, d):
            amt = int(r.amount)
            matched = True
    return amt if matched else 0


# -----------------------------
# Item semantics (parent clamp)
# -----------------------------

def children_of(db: DB, parent_id: str) -> List[Item]:
    return [it for it in db.items.values() if it.parent_id == parent_id]


def clamp_effective_dates(db: DB, item: Item) -> Tuple[Optional[date], Optional[date]]:
    """
    Parent clamp (VIR-like):
    - effective due = min(self.due, parent.due, grandparent.due, ...)
    - effective defer = max(self.defer, parent.defer, grandparent.defer, ...)
    """
    eff_defer = parse_date(item.defer)
    eff_due = parse_date(item.due)

    cur = item
    seen: Set[str] = set()
    while cur.parent_id:
        pid = cur.parent_id
        if pid in seen:
            break
        seen.add(pid)
        p = db.items.get(pid)
        if not p:
            break

        p_defer = parse_date(p.defer)
        p_due = parse_date(p.due)

        if p_due and eff_due:
            eff_due = min(eff_due, p_due)
        elif p_due and not eff_due:
            eff_due = p_due

        if p_defer and eff_defer:
            eff_defer = max(eff_defer, p_defer)
        elif p_defer and not eff_defer:
            eff_defer = p_defer

        cur = p

    return eff_defer, eff_due


def effective_cost(db: DB, item: Item) -> int:
    """
    If item has children: cost is the sum of children's effective costs.
    Otherwise use its own cost.
    """
    kids = children_of(db, item.id)
    if not kids:
        return max(0, int(item.cost))
    return sum(effective_cost(db, k) for k in kids)


def remaining_sessions(db: DB, item: Item) -> int:
    cost = effective_cost(db, item)
    return max(0, cost - int(item.completed))


def is_available_on(db: DB, item: Item, d: date) -> bool:
    if item.done:
        return False
    eff_defer, eff_due = clamp_effective_dates(db, item)
    if eff_defer and d < eff_defer:
        return False
    if eff_due and d > eff_due:
        return False
    return remaining_sessions(db, item) > 0


def get_queue_order(db: DB) -> List[str]:
    """
    Effective priority:
    1) manual queue order (db.queue)
    2) remaining items sorted by effective due date
    """
    existing = set(db.items.keys())
    manual = [iid for iid in db.queue if iid in existing and not db.items[iid].done]
    rest = [iid for iid in existing if iid not in set(manual) and not db.items[iid].done]

    def due_key(iid: str) -> Tuple[int, str]:
        it = db.items[iid]
        _, eff_due = clamp_effective_dates(db, it)
        if eff_due is None:
            return (10_000_000, iid)
        return (eff_due.toordinal(), iid)

    rest.sort(key=due_key)
    return manual + rest


# -----------------------------
# Sessions & planning
# -----------------------------

def used_quota(db: DB, d: date) -> int:
    ds = fmt_date(d)
    used = 0
    for s in db.sessions:
        if s.day == ds and s.kind in ("completed", "scheduled"):
            used += int(s.count)
    return used


def plan_schedule(
    db: DB,
    start_day: date,
    days: int,
    strategy: str = "early",
) -> Tuple[Dict[str, List[Tuple[str, int]]], List[str]]:
    """
    Returns:
      schedule: day -> [(item_id, count), ...] (projected)
      alerts: list[str]
    """
    if days <= 0:
        return {}, []

    horizon = [start_day + timedelta(days=i) for i in range(days)]
    projected: Dict[str, Dict[str, int]] = {fmt_date(d): {} for d in horizon}

    remaining = {iid: remaining_sessions(db, it) for iid, it in db.items.items() if not it.done}
    order = get_queue_order(db)

    if strategy not in ("early", "late"):
        raise ValueError("strategy must be 'early' or 'late'")

    if strategy == "early":
        for d in horizon:
            free = max(0, quota_for_day(db, d) - used_quota(db, d))
            if free == 0:
                continue
            for _ in range(free):
                chosen = None
                for iid in order:
                    if remaining.get(iid, 0) <= 0:
                        continue
                    it = db.items[iid]
                    if is_available_on(db, it, d):
                        chosen = iid
                        break
                if chosen is None:
                    break
                ds = fmt_date(d)
                projected[ds][chosen] = projected[ds].get(chosen, 0) + 1
                remaining[chosen] -= 1

    else:
        free_slots: Dict[str, int] = {}
        for d in horizon:
            free_slots[fmt_date(d)] = max(0, quota_for_day(db, d) - used_quota(db, d))

        for iid in order:
            if remaining.get(iid, 0) <= 0:
                continue
            it = db.items[iid]
            eff_defer, eff_due = clamp_effective_dates(db, it)

            window_start = max(start_day, eff_defer) if eff_defer else start_day
            window_end = min(horizon[-1], eff_due) if eff_due else horizon[-1]
            if window_end < window_start:
                continue

            window_days = daterange(window_start, window_end)
            window_days.reverse()  # late = fill from end backwards

            need = remaining[iid]
            for d in window_days:
                if need <= 0:
                    break
                ds = fmt_date(d)
                take = min(need, free_slots.get(ds, 0))
                if take <= 0:
                    continue
                projected[ds][iid] = projected[ds].get(iid, 0) + take
                free_slots[ds] -= take
                need -= take
            remaining[iid] = need

    schedule_out: Dict[str, List[Tuple[str, int]]] = {}
    for d in horizon:
        ds = fmt_date(d)
        if projected[ds]:
            schedule_out[ds] = sorted(projected[ds].items(), key=lambda x: (-x[1], x[0]))

    alerts: List[str] = []
    for iid, rem in remaining.items():
        if rem <= 0:
            continue
        it = db.items[iid]
        _, eff_due = clamp_effective_dates(db, it)
        if eff_due and start_day <= eff_due <= horizon[-1]:
            alerts.append(f"ALERT: '{it.name}' misses due {fmt_date(eff_due)} by {rem} session(s).")
        elif eff_due is None:
            alerts.append(f"NOTICE: '{it.name}' still has {rem} remaining session(s) (no due).")

    return schedule_out, alerts
