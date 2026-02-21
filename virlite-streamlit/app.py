from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import List, Optional

import pandas as pd
import streamlit as st

from virlite.engine import (
    clamp_effective_dates,
    effective_cost,
    fmt_date,
    parse_date,
    plan_schedule,
    quota_for_day,
    remaining_sessions,
    get_queue_order,
)
from virlite.models import DB, Item, QuotaRule, Session
from virlite.storage import load_db, save_db, resolve_db_path


# -----------------------------
# App setup
# -----------------------------

st.set_page_config(page_title="VIRLite", layout="wide")
st.title("VIRLite — VIR-inspired session planner")

DB_PATH = resolve_db_path()


@st.cache_data(show_spinner=False)
def _load_db_cached(path: str) -> DB:
    # Streamlit cache for faster reloads; we explicitly clear when saving.
    return load_db(path)


def load() -> DB:
    return _load_db_cached(DB_PATH)


def save(db: DB) -> None:
    save_db(db, DB_PATH)
    _load_db_cached.clear()  # force reload on next read


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# -----------------------------
# Sidebar navigation
# -----------------------------

pages = [
    "Overview",
    "Quota",
    "Items",
    "Queue",
    "Sessions",
    "Plan",
]
page = st.sidebar.radio("Navigate", pages)

st.sidebar.caption(f"DB: `{DB_PATH}`")


# -----------------------------
# Helpers for tables
# -----------------------------

def items_df(db: DB) -> pd.DataFrame:
    rows = []
    for iid, it in db.items.items():
        eff_defer, eff_due = clamp_effective_dates(db, it)
        rows.append(
            {
                "id": iid,
                "name": it.name,
                "parent_id": it.parent_id or "",
                "cost": it.cost,
                "effective_cost": effective_cost(db, it),
                "completed": it.completed,
                "remaining": remaining_sessions(db, it),
                "defer": it.defer or "",
                "due": it.due or "",
                "eff_defer": fmt_date(eff_defer) if eff_defer else "",
                "eff_due": fmt_date(eff_due) if eff_due else "",
                "done": it.done,
            }
        )
    if not rows:
        return pd.DataFrame(columns=["id","name","parent_id","cost","effective_cost","completed","remaining","defer","due","eff_defer","eff_due","done"])
    return pd.DataFrame(rows).sort_values(["done", "eff_due", "due", "name"], ascending=[True, True, True, True])


def quota_df(db: DB) -> pd.DataFrame:
    rows = []
    for r in db.quota_rules:
        rows.append(
            {
                "id": r.id,
                "pattern": r.pattern,
                "amount": r.amount,
                "on_date": r.on_date or "",
                "start": r.start or "",
                "end": r.end or "",
                "weekdays": ",".join(str(x) for x in (r.weekdays or [])),
            }
        )
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["id","pattern","amount","on_date","start","end","weekdays"])


def sessions_df(db: DB) -> pd.DataFrame:
    rows = []
    for s in db.sessions:
        name = db.items[s.item_id].name if s.item_id in db.items else s.item_id
        rows.append({"day": s.day, "kind": s.kind, "item_id": s.item_id, "item": name, "count": s.count})
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["day","kind","item_id","item","count"])


# -----------------------------
# Overview
# -----------------------------

db = load()

if page == "Overview":
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Items", len(db.items))
    with c2:
        st.metric("Quota rules", len(db.quota_rules))
    with c3:
        done_count = sum(1 for it in db.items.values() if it.done)
        st.metric("Done items", done_count)

    st.subheader("Items")
    st.dataframe(items_df(db), use_container_width=True, hide_index=True)

    st.subheader("Effective queue order")
    order = get_queue_order(db)
    if not order:
        st.info("No items yet.")
    else:
        st.write(pd.DataFrame([{"rank": i+1, "id": iid, "name": db.items[iid].name} for i, iid in enumerate(order)]))

# -----------------------------
# Quota
# -----------------------------

elif page == "Quota":
    st.subheader("Quota rules")
    st.dataframe(quota_df(db), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Add quota rule")

    with st.form("quota_add", clear_on_submit=True):
        pattern = st.selectbox("Pattern", ["everyday", "weekday", "weekend", "custom", "on"])
        amount = st.number_input("Amount (sessions/day)", min_value=0, max_value=100, value=4, step=1)
        on_date = st.text_input("On date (YYYY-MM-DD) — only for pattern=on", value="")
        start = st.text_input("Start (YYYY-MM-DD) optional", value="")
        end = st.text_input("End (YYYY-MM-DD) optional", value="")
        weekdays = st.multiselect("Weekdays (for custom)", options=list(range(7)), default=[0,1,2,3,4])
        submitted = st.form_submit_button("Add rule")

    if submitted:
        r = QuotaRule(
            id=new_id("qr"),
            pattern=pattern,
            amount=int(amount),
            on_date=on_date.strip() or None,
            start=start.strip() or None,
            end=end.strip() or None,
            weekdays=list(weekdays) if pattern == "custom" else None,
        )
        db.quota_rules.append(r)
        save(db)
        st.success("Quota rule added.")
        st.rerun()

    st.divider()
    st.subheader("Delete quota rule")
    if db.quota_rules:
        rid = st.selectbox("Select rule id", [r.id for r in db.quota_rules])
        if st.button("Delete selected rule"):
            db.quota_rules = [r for r in db.quota_rules if r.id != rid]
            save(db)
            st.success("Deleted.")
            st.rerun()
    else:
        st.info("No quota rules to delete.")

# -----------------------------
# Items
# -----------------------------

elif page == "Items":
    st.subheader("Items")
    st.dataframe(items_df(db), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Add item")
    with st.form("item_add", clear_on_submit=True):
        name = st.text_input("Name", value="")
        cost = st.number_input("Cost (sessions)", min_value=0, max_value=10000, value=6, step=1)
        parent_id = st.selectbox("Parent (optional)", [""] + sorted(list(db.items.keys())))
        defer = st.text_input("Defer (YYYY-MM-DD) optional", value="")
        due = st.text_input("Due (YYYY-MM-DD) optional", value="")
        submitted = st.form_submit_button("Add item")

    if submitted:
        if not name.strip():
            st.error("Name is required.")
        else:
            iid = new_id("it")
            db.items[iid] = Item(
                id=iid,
                name=name.strip(),
                cost=int(cost),
                parent_id=parent_id or None,
                defer=defer.strip() or None,
                due=due.strip() or None,
                done=False,
            )
            db.queue.append(iid)  # default: add to manual queue end
            save(db)
            st.success("Item added.")
            st.rerun()

    st.divider()
    st.subheader("Update / Mark done / Delete")
    if db.items:
        iid = st.selectbox("Select item", sorted(list(db.items.keys())))
        it = db.items[iid]

        c1, c2 = st.columns(2)
        with c1:
            new_name = st.text_input("Name", value=it.name, key="upd_name")
            new_cost = st.number_input("Cost (sessions)", min_value=0, max_value=10000, value=int(it.cost), step=1, key="upd_cost")
            new_parent = st.selectbox("Parent (optional)", [""] + sorted(list(db.items.keys())), index=([""] + sorted(list(db.items.keys()))).index(it.parent_id or ""), key="upd_parent")
        with c2:
            new_defer = st.text_input("Defer (YYYY-MM-DD)", value=it.defer or "", key="upd_defer")
            new_due = st.text_input("Due (YYYY-MM-DD)", value=it.due or "", key="upd_due")
            new_done = st.checkbox("Done", value=bool(it.done), key="upd_done")

        c3, c4, c5 = st.columns(3)
        with c3:
            if st.button("Save changes"):
                it.name = new_name.strip() or it.name
                it.cost = int(new_cost)
                it.parent_id = new_parent or None
                it.defer = new_defer.strip() or None
                it.due = new_due.strip() or None
                it.done = bool(new_done)
                save(db)
                st.success("Saved.")
                st.rerun()

        with c4:
            if st.button("Mark done (and children)"):
                it.done = True
                # also mark children as done (simple VIR-like behavior)
                for child in list(db.items.values()):
                    if child.parent_id == iid:
                        child.done = True
                save(db)
                st.success("Marked done.")
                st.rerun()

        with c5:
            if st.button("Delete item"):
                # remove from items
                del db.items[iid]
                # remove from queue
                db.queue = [x for x in db.queue if x != iid]
                # remove sessions referencing it
                db.sessions = [s for s in db.sessions if s.item_id != iid]
                # orphan children
                for child in db.items.values():
                    if child.parent_id == iid:
                        child.parent_id = None
                save(db)
                st.success("Deleted.")
                st.rerun()
    else:
        st.info("No items yet.")

# -----------------------------
# Queue
# -----------------------------

elif page == "Queue":
    st.subheader("Manual queue (priority order)")
    if not db.queue:
        st.info("Manual queue is empty. Add items first.")
    else:
        qrows = []
        for i, iid in enumerate(db.queue):
            if iid in db.items:
                qrows.append({"rank": i+1, "id": iid, "name": db.items[iid].name, "done": db.items[iid].done})
        st.dataframe(pd.DataFrame(qrows), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Reorder queue")
    if db.queue:
        iid = st.selectbox("Item", [x for x in db.queue if x in db.items])
        direction = st.radio("Move", ["Up", "Down"], horizontal=True)
        if st.button("Apply move"):
            idx = db.queue.index(iid)
            if direction == "Up" and idx > 0:
                db.queue[idx], db.queue[idx-1] = db.queue[idx-1], db.queue[idx]
                save(db)
                st.success("Moved.")
                st.rerun()
            elif direction == "Down" and idx < len(db.queue)-1:
                db.queue[idx], db.queue[idx+1] = db.queue[idx+1], db.queue[idx]
                save(db)
                st.success("Moved.")
                st.rerun()
            else:
                st.info("Can't move further.")

    st.divider()
    st.subheader("Effective queue order (manual + due-date fallback)")
    order = get_queue_order(db)
    if not order:
        st.info("No items.")
    else:
        st.dataframe(
            pd.DataFrame([{"rank": i+1, "id": iid, "name": db.items[iid].name} for i, iid in enumerate(order)]),
            use_container_width=True,
            hide_index=True,
        )

# -----------------------------
# Sessions
# -----------------------------

elif page == "Sessions":
    st.subheader("Sessions")
    st.dataframe(sessions_df(db).sort_values(["day", "kind"]), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Record completed sessions")
    if not db.items:
        st.info("Add items first.")
    else:
        with st.form("sess_add", clear_on_submit=True):
            iid = st.selectbox("Item", sorted(list(db.items.keys())))
            day = st.date_input("Day", value=date.today())
            count = st.number_input("Count", min_value=1, max_value=100, value=1, step=1)
            submitted = st.form_submit_button("Add completed session(s)")

        if submitted:
            s = Session(kind="completed", item_id=iid, day=fmt_date(day), count=int(count))
            db.sessions.append(s)
            db.items[iid].completed += int(count)
            save(db)
            st.success("Recorded.")
            st.rerun()

    st.divider()
    st.subheader("Delete a session record")
    if db.sessions:
        options = [f"{i}: {s.day} {s.kind} {s.item_id} x{s.count}" for i, s in enumerate(db.sessions)]
        sel = st.selectbox("Select", options)
        if st.button("Delete selected session"):
            idx = int(sel.split(":")[0])
            s = db.sessions[idx]
            if s.kind == "completed" and s.item_id in db.items:
                db.items[s.item_id].completed = max(0, db.items[s.item_id].completed - int(s.count))
            del db.sessions[idx]
            save(db)
            st.success("Deleted.")
            st.rerun()
    else:
        st.info("No sessions to delete.")

# -----------------------------
# Plan
# -----------------------------

elif page == "Plan":
    st.subheader("Generate a projected schedule")

    c1, c2, c3 = st.columns(3)
    with c1:
        start = st.date_input("Start", value=date.today())
    with c2:
        days = st.number_input("Days", min_value=1, max_value=365, value=14, step=1)
    with c3:
        strategy = st.selectbox("Strategy", ["early", "late"])

    schedule, alerts = plan_schedule(db, start, int(days), strategy=strategy)

    st.divider()
    st.subheader("Projected schedule")
    if not schedule:
        st.info("Nothing to schedule (or no free quota).")
    else:
        rows = []
        for day, entries in schedule.items():
            for iid, cnt in entries:
                rows.append({"day": day, "item_id": iid, "item": db.items[iid].name if iid in db.items else iid, "sessions": cnt})
        df = pd.DataFrame(rows).sort_values(["day", "sessions"], ascending=[True, False])
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Compact day-by-day view
        st.subheader("Day view")
        for day in sorted(schedule.keys()):
            parts = []
            for iid, cnt in schedule[day]:
                nm = db.items[iid].name if iid in db.items else iid
                parts.append(f"{nm} × {cnt}")
            st.write(f"**{day}** — " + " · ".join(parts))

    st.divider()
    st.subheader("Alerts")
    if alerts:
        for a in alerts:
            st.warning(a)
    else:
        st.success("No alerts within the horizon.")

    st.divider()
    st.subheader("Quota preview (within horizon)")
    qrows = []
    for i in range(int(days)):
        d = start + pd.Timedelta(days=i)
        d = d.date()
        qrows.append({"day": fmt_date(d), "quota": quota_for_day(db, d), "used": int(0)})
    st.dataframe(pd.DataFrame(qrows), use_container_width=True, hide_index=True)
