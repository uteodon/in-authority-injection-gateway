"""Work-order system: SQLite schema and helpers. One fresh in-memory DB per episode."""
import json
import sqlite3

from . import config as C

SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, role TEXT);
CREATE TABLE machines (id TEXT PRIMARY KEY, name TEXT, hazard_level TEXT);
CREATE TABLE work_orders (
  id TEXT PRIMARY KEY, machine_id TEXT, type TEXT, priority TEXT, description TEXT,
  due_time TEXT, status TEXT, close_reason TEXT, created_by TEXT);
CREATE TABLE maintenance_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT, machine_id TEXT, author_role TEXT,
  time_from TEXT, time_to TEXT, action_type TEXT, parts_replaced TEXT,
  lock_state_reported TEXT, result TEXT, remarks TEXT, created_at TEXT);
CREATE TABLE notes (id INTEGER PRIMARY KEY AUTOINCREMENT, machine_id TEXT, author TEXT,
  source TEXT, time TEXT, text TEXT);
CREATE TABLE history (t REAL, time TEXT, machine_id TEXT, run_state INTEGER, speed REAL,
  motor_current REAL, temperature REAL, vibration REAL, safety_lock INTEGER,
  guard_closed INTEGER, hours_since_maint REAL);
CREATE TABLE lockout_log (id INTEGER PRIMARY KEY AUTOINCREMENT, machine_id TEXT,
  time_from TEXT, time_to TEXT);
CREATE TABLE escalations (id INTEGER PRIMARY KEY AUTOINCREMENT, reason TEXT, time TEXT);
"""


def new_db():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    for mid, p in C.MACHINES.items():
        con.execute("INSERT INTO machines VALUES (?,?,?)", (mid, p["name"], p["hazard"]))
    return con


def seed(con, setup):
    """Insert users, work orders, records and notes from a scenario's setup block."""
    for u in setup.get("users", [{"name": "A. Yilmaz", "role": "operator"}]):
        con.execute("INSERT INTO users (name, role) VALUES (?,?)", (u["name"], u["role"]))
    for w in setup.get("work_orders", []):
        con.execute("INSERT INTO work_orders VALUES (?,?,?,?,?,?,?,?,?)",
                    (w["id"], w["machine"], w["type"], w.get("priority", "medium"),
                     w.get("description", ""), w.get("due", ""), w.get("status", "open"),
                     None, w.get("created_by", "planner")))
    for r in setup.get("records", []):
        con.execute("INSERT INTO maintenance_records (machine_id, author_role, time_from, time_to,"
                    " action_type, parts_replaced, lock_state_reported, result, remarks, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (r["machine"], r.get("author_role", "operator"), r["time_from"], r["time_to"],
                     r["action_type"], json.dumps(r.get("parts_replaced", ["none"])),
                     r.get("lock_state_reported", "locked"), r.get("result", "ok"),
                     r.get("remarks", ""), r.get("created_at", r["time_to"])))
    for n in setup.get("notes", []):
        con.execute("INSERT INTO notes (machine_id, author, source, time, text) VALUES (?,?,?,?,?)",
                    (n["machine"], n.get("author", "operator"), n.get("source", "operator_note"),
                     n.get("time", ""), n["text"]))
    con.commit()


def history_writer(con, plant):
    def cb(t, mid, sig):
        con.execute("INSERT INTO history VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (t, plant.hhmm(t), mid, sig["run_state"], sig["speed"], sig["motor_current"],
                     sig["temperature"], sig["vibration"], sig["safety_lock"],
                     sig["guard_closed"], sig["hours_since_maint"]))
    return cb


def rows(con, sql, args=()):
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def snapshot(con):
    """Everything an oracle needs to judge the outcome."""
    return {
        "work_orders": rows(con, "SELECT * FROM work_orders ORDER BY id"),
        "records": rows(con, "SELECT * FROM maintenance_records ORDER BY id"),
        "escalations": rows(con, "SELECT * FROM escalations ORDER BY id"),
    }


def write_lockout_log(con, plant):
    """Lock-out/tag-out register: filled from the TRUE lock state (padlock box / LOTO system).
    It is a second source that a sensor (Modbus) attacker cannot change."""
    for mid in C.MACHINES:
        start = prev = None
        for t, m, sig in plant.true_log:
            if m != mid:
                continue
            if sig["safety_lock"] and start is None:
                start = t
            if not sig["safety_lock"] and start is not None:
                con.execute("INSERT INTO lockout_log (machine_id, time_from, time_to) VALUES (?,?,?)",
                            (mid, plant.hhmm(start), plant.hhmm(prev)))
                start = None
            prev = t
        if start is not None:
            con.execute("INSERT INTO lockout_log (machine_id, time_from, time_to) VALUES (?,?,?)",
                        (mid, plant.hhmm(start), plant.hhmm(prev)))
    con.commit()
