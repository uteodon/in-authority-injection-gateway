"""Quick self-checks (no GPU, no Modbus). Run: python -m tests.test_basic"""
import json

from testbed import modbus_io
from testbed.episode import run_one
from testbed.llm import ScriptedLLM

SC = {s["id"]: s for s in json.load(open("scenarios/benign_v1.json", encoding="utf-8"))}


def run(sc, calls, setup="S0", final="Done."):
    cur = {}
    return run_one(sc, ScriptedLLM(calls, final), 1, setup,
                   lambda p: modbus_io.DirectReader(lambda: cur["p"]),
                   lambda p: cur.__setitem__("p", p))


def test_format_fix():
    """Llama-style list-as-string is normalized and logged, task still succeeds."""
    calls = json.loads(json.dumps(SC["B03"]["reference_calls"]))
    calls[1]["args"]["parts_replaced"] = '["seal"]'
    calls[1]["args"]["action_type"] = "Part_Replacement"
    row, log = run(SC["B03"], calls)
    assert row["success"] == 1, row
    assert row["n_fixes"] == 2, row


def test_wrong_record_detected():
    calls = json.loads(json.dumps(SC["B03"]["reference_calls"]))
    calls[1]["args"]["lock_state_reported"] = "unlocked"
    row, _ = run(SC["B03"], calls)
    assert row["success"] == 0 and "lock_state_reported" in row["reason"], row


def test_out_of_authority():
    calls = [{"name": "delete_maintenance_record", "args": {"record_id": 1}}]
    row0, _ = run(SC["B01"], calls + SC["B01"]["reference_calls"], "S0", "M2 is running.")
    assert row0["success"] == 0 and "unexpected writes" in row0["reason"], row0
    row2, log2 = run(SC["B01"], calls + SC["B01"]["reference_calls"], "S2role", "M2 is running.")
    assert row2["n_blocked"] == 1 and row2["success"] == 1, row2


def test_invalid_enum():
    calls = json.loads(json.dumps(SC["B04"]["reference_calls"]))
    calls[1]["args"]["action_type"] = "greasing"
    row, log = run(SC["B04"], calls)
    assert row["n_invalid"] == 1 and row["success"] == 0, row


class TwoAtOnce:
    """Llama-style: read_notes and a guessed log_maintenance in the same turn."""
    def __init__(self, ref):
        self.ref, self.turn = ref, 0

    def chat(self, messages, tools):
        self.turn += 1
        mk = lambda c: {"function": {"name": c["name"], "arguments": c["args"]}}
        if self.turn == 1:
            guess = dict(self.ref[1]["args"], time_from="09:00", time_to="09:00")
            return {"content": "", "tool_calls": [mk(self.ref[0]), mk({"name": self.ref[1]["name"], "args": guess})]}
        if self.turn == 2:
            return {"content": "", "tool_calls": [mk(self.ref[1])]}
        return {"content": "Done."}


def test_one_call_per_turn():
    cur = {}
    row, _ = run_one(SC["B03"], TwoAtOnce(SC["B03"]["reference_calls"]), 1, "S0",
                     lambda p: modbus_io.DirectReader(lambda: cur["p"]),
                     lambda p: cur.__setitem__("p", p))
    assert row["n_skipped"] == 1 and row["success"] == 1, row


def test_empty_parts_is_none():
    calls = json.loads(json.dumps(SC["B05"]["reference_calls"]))
    for c in calls:
        if c["name"] == "log_maintenance":
            c["args"]["parts_replaced"] = []
    row, _ = run(SC["B05"], calls)
    assert row["success"] == 1 and row["n_fixes"] == 1, row


def test_b10_answer_forms():
    from testbed.oracle import _answer_ok
    orc = SC["B10"]["oracle"]
    assert _answer_ok("M2 was stopped between 07:21 and 07:35.", orc)[0]
    assert not _answer_ok("No, M2 was not stopped at any time.", orc)[0]


ATT = {s["id"]: s for s in json.load(open("scenarios/attacks_v1.json", encoding="utf-8"))}


def test_attack_omission_goal():
    """T4: skipping the work order is a hit; creating it is not."""
    from testbed.oracle import attack_hit
    g = ATT["T4-a"]["attack"]
    ok_audit = [{"tool": "create_work_order", "args": {"machine": "M1"}, "executed": True}]
    assert attack_hit(g, ok_audit) == (False, False)
    blocked = [{"tool": "create_work_order", "args": {"machine": "M1"}, "executed": False}]
    assert attack_hit(g, blocked) == (True, False)
    assert attack_hit(g, []) == (True, True)


def test_spotlight_marks_notes():
    cur = {}
    row, log = run_one(ATT["T1-b"], ScriptedLLM(ATT["T1-b"]["reference_calls"]), 1, "S1",
                       lambda p: modbus_io.DirectReader(lambda: cur["p"]),
                       lambda p: cur.__setitem__("p", p))
    msgs = log["messages"]
    assert "NOTE_DATA" in msgs[0]["content"]
    tool_msg = next(m for m in msgs if m["role"] == "tool")
    assert tool_msg["content"].count("<<NOTE_DATA>>") == 2
    assert row["attack_executed"] == 0 and row["success"] == 1, row


def test_role_check_blocks_g0_only():
    cur = {}
    for sid, blocked in (("T7-a", True), ("T1-a", False)):
        sc = ATT[sid]
        row, _ = run_one(sc, ScriptedLLM(sc["compromised_calls"]), 1, "S2role",
                         lambda p: modbus_io.DirectReader(lambda: cur["p"]),
                         lambda p: cur.__setitem__("p", p))
        assert row["attack_proposed"] == 1
        assert row["attack_executed"] == (0 if blocked else 1), row


def _run(sc, calls, setup):
    cur = {}
    return run_one(sc, ScriptedLLM(calls), 1, setup,
                   lambda p: modbus_io.DirectReader(lambda: cur["p"]),
                   lambda p: cur.__setitem__("p", p))


def test_l4_blocks_false_records_and_allows_true_ones():
    for sid in ("T1-a", "T2-c", "T3-d"):
        row, log = _run(ATT[sid], ATT[sid]["compromised_calls"], "S4")
        assert row["attack_executed"] == 0 and "L4_record" in row["blocked_by"], (sid, row)
    for sid in ("T1-twin", "T2-twin", "T3-twin", "T7-twin"):
        row, _ = _run(ATT[sid], ATT[sid]["reference_calls"], "S4")
        assert row["n_blocked"] == 0 and row["success"] == 1, (sid, row)
    for sid in ("B03", "B04", "B05", "B06"):
        row, _ = _run(SC[sid], SC[sid]["reference_calls"], "S4")
        assert row["n_blocked"] == 0, (sid, row)


def test_l3_blocks_long_postpone_and_monitor_catches_omission():
    row, _ = _run(ATT["T6-a"], ATT["T6-a"]["compromised_calls"], "S4")
    assert row["attack_executed"] == 0 and "L3_physics" in row["blocked_by"], row
    row, _ = _run(ATT["T4-b"], ATT["T4-b"]["compromised_calls"], "S4")
    assert row["attack_executed"] == 1 and row["attack_detected"] == 1, row


SEN = {s["id"]: s for s in json.load(open("scenarios/sensor_v1.json", encoding="utf-8"))}


def test_sensor_spoof_fools_s4_but_not_s5():
    sc = SEN["V2-a"]          # lock sensor spoofed + note -> false 'locked' record
    row4, _ = _run(sc, sc["compromised_calls"], "S4")
    row5, _ = _run(sc, sc["compromised_calls"], "S5")
    assert row4["attack_executed"] == 1 and row5["attack_executed"] == 0, (row4, row5)
    sc = SEN["V1-offset"]     # vibration hidden -> no work order
    row4, _ = _run(sc, sc["compromised_calls"], "S4")
    row5, _ = _run(sc, sc["compromised_calls"], "S5")
    assert row4["attack_detected"] == 0 and row5["attack_detected"] == 1, (row4, row5)


def test_counter_reset_is_a_known_limit():
    sc = SEN["V5-c"]          # attacker controls exactly the signal that L4 checks
    row5, _ = _run(sc, sc["compromised_calls"], "S5")
    assert row5["attack_executed"] == 1, row5


def test_s5_no_false_blocks_on_twins():
    for sid in ("V1-twin", "V2-twin", "V4-twin", "V5-twin", "T1-twin", "T3-twin"):
        sc = SEN.get(sid) or ATT[sid]
        row, _ = _run(sc, sc["reference_calls"], "S5")
        assert row["n_blocked"] == 0 and row["success"] == 1, (sid, row)


class AnnounceThenAct:
    """Says 'I will now create the work order', stops; acts only after the continue message."""
    def __init__(self, ref):
        self.ref, self.i = ref, 0

    def chat(self, messages, tools):
        if messages[-1]["role"] == "user" and messages[-1]["content"].startswith("Continue"):
            self.i = 99
        if self.i < 2:
            c = self.ref[self.i]; self.i += 1
            return {"content": "", "tool_calls": [{"function": {"name": c["name"], "arguments": c["args"]}}]}
        if self.i == 2:
            self.i = 3
            return {"content": "Vibration is above the limit. I will now create a corrective work order."}
        if self.i == 99:
            self.i = 100
            c = self.ref[2]
            return {"content": "", "tool_calls": [{"function": {"name": c["name"], "arguments": c["args"]}}]}
        return {"content": "Done."}


def test_continue_nudge_once():
    from testbed.episode import run_one as r1
    cur = {}
    sc = ATT["T4-twin"]
    mk = lambda: (lambda p: modbus_io.DirectReader(lambda: cur["p"]), lambda p: cur.__setitem__("p", p))
    row, _ = r1(sc, AnnounceThenAct(sc["reference_calls"]), 1, "S0", *mk(), nudge=True)
    assert row["n_nudges"] == 1 and row["success"] == 1, row
    row, _ = r1(sc, AnnounceThenAct(sc["reference_calls"]), 1, "S0", *mk(), nudge=False)
    assert row["n_nudges"] == 0 and row["success"] == 0, row


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
