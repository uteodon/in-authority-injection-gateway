"""Process simulator: three generic machines with a TRUE state and a REPORTED state.

The true state is what physically happens. The reported state is what sensors / Modbus
show. They are equal unless a sensor attack (CAP-2) installs an override.
"""
import math
import random
from dataclasses import dataclass, field, asdict
from datetime import timedelta

from . import config as C

SIGNALS = ["run_state", "speed", "motor_current", "temperature", "vibration",
           "safety_lock", "guard_closed", "hours_since_maint"]


@dataclass
class MachineState:
    run_cmd: int = 1            # what the schedule asks for
    run_state: int = 1          # actual (after interlocks)
    speed: float = 0.0
    motor_current: float = 0.0
    temperature: float = C.AMBIENT_TEMP
    vibration: float = 0.2
    safety_lock: int = 0
    guard_closed: int = 1
    hours_since_maint: float = 0.0
    load: float = 0.8

    def signals(self):
        d = asdict(self)
        return {k: d[k] for k in SIGNALS}


class Plant:
    def __init__(self, seed=0, initial=None):
        self.rng = random.Random(seed)
        self.t = 0.0  # seconds since config.SIM_START
        self.m = {}
        for mid in C.MACHINES:
            st = MachineState()
            if initial and mid in initial:
                for k, v in initial[mid].items():
                    setattr(st, k, v)
            self.m[mid] = st
        self._settle()
        # sensor overrides for CAP-2 attacks: {machine: {signal: value or callable(t, true_value)}}
        self.overrides = {}
        self.events = []  # list of (time_s, machine, {field: value} or {"maintenance": True})
        self.true_log = []  # list of (t, machine, true signals) at history rate

    # ------------------------------------------------------------- helpers
    def clock(self, t=None):
        return C.SIM_START + timedelta(seconds=self.t if t is None else t)

    def hhmm(self, t=None):
        return self.clock(t).strftime("%H:%M")

    def parse_hhmm(self, s):
        h, mi = (int(x) for x in s.strip().split(":"))
        base = C.SIM_START.replace(hour=0, minute=0)
        return (base + timedelta(hours=h, minutes=mi) - C.SIM_START).total_seconds()

    def _settle(self):
        """Put each machine in its steady state for its initial command (no warm-up transient)."""
        for mid, st in self.m.items():
            p = C.MACHINES[mid]
            run = self._allowed(mid, st) and st.run_cmd
            st.run_state = int(run)
            st.speed = p["rated_speed"] if run else 0.0
            st.motor_current = p["full_current"] * st.load if run else 0.0
            st.temperature = p["run_temp"] if run else C.AMBIENT_TEMP
            st.vibration = self._vib(mid, st) if run else 0.2

    def _allowed(self, mid, st):
        if st.safety_lock:
            return False
        if C.MACHINES[mid]["has_guard"] and not st.guard_closed:
            return False
        return True

    def _vib(self, mid, st):
        p = C.MACHINES[mid]
        return p["vib_base"] + p["vib_growth"] * st.hours_since_maint

    # ------------------------------------------------------------- dynamics
    def schedule(self, at_hhmm, machine, **changes):
        self.events.append((self.parse_hhmm(at_hhmm), machine, changes))
        self.events.sort(key=lambda e: e[0])

    def step(self, dt=C.DT):
        # apply due events
        while self.events and self.events[0][0] <= self.t:
            _, mid, ch = self.events.pop(0)
            st = self.m[mid]
            for k, v in ch.items():
                if k == "maintenance" and v:
                    st.hours_since_maint = 0.0
                else:
                    setattr(st, k, v)
        for mid, st in self.m.items():
            p = C.MACHINES[mid]
            run = bool(st.run_cmd) and self._allowed(mid, st)
            st.run_state = int(run)
            target_speed = p["rated_speed"] if run else 0.0
            st.speed += (target_speed - st.speed) * (1 - math.exp(-dt / C.SPEED_TAU))
            if st.speed < 1:
                st.speed = 0.0
            frac = st.speed / p["rated_speed"]
            st.motor_current = max(0.0, p["full_current"] * st.load * frac
                                   + (self.rng.gauss(0, 0.05) if frac > 0 else 0.0))
            target_temp = C.AMBIENT_TEMP + (p["run_temp"] - C.AMBIENT_TEMP) * frac
            st.temperature += (target_temp - st.temperature) * (1 - math.exp(-dt / C.TEMP_TAU))
            if run:
                st.hours_since_maint += dt / 3600.0
                st.vibration = max(0.0, self._vib(mid, st) + self.rng.gauss(0, 0.05))
            else:
                st.vibration = 0.2 * frac
        self.t += dt

    def run_until(self, hhmm, history_cb=None):
        """Advance the simulation to the given clock time, calling history_cb every HISTORY_EVERY s."""
        end = self.parse_hhmm(hhmm)
        next_snap = self.t
        while self.t < end:
            if self.t >= next_snap:
                for mid in self.m:
                    self.true_log.append((self.t, mid, self.true_signals(mid)))
                    if history_cb:
                        history_cb(self.t, mid, self.reported_signals(mid))
                next_snap += C.HISTORY_EVERY
            self.step()

    # ------------------------------------------------------------- views
    def true_signals(self, mid):
        s = self.m[mid].signals()
        return {k: round(v, 2) if isinstance(v, float) else v for k, v in s.items()}

    def reported_signals(self, mid, t=None):
        s = self.true_signals(mid)
        for k, v in self.overrides.get(mid, {}).items():
            s[k] = v(self.t if t is None else t, s[k]) if callable(v) else v
        return s

    def install_spoofs(self, specs):
        """CAP-2 sensor attack. Each spec: {machine, signal, mode, value, from, to}.
        mode const: report value; offset: report true+value; reset_at: the counter looks reset at 'from'."""
        for sp in specs or []:
            t0 = self.parse_hhmm(sp.get("from", "00:00"))
            t1 = self.parse_hhmm(sp.get("to", "23:59"))
            mode, val, state = sp["mode"], sp.get("value", 0), {}

            def f(t, true, t0=t0, t1=t1, mode=mode, val=val, state=state):
                if not (t0 <= t <= t1):
                    return true
                if mode == "const":
                    return val
                if mode == "offset":
                    return round(max(0.0, true + val), 2)
                if mode == "reset_at":
                    state.setdefault("h0", true)
                    return round(max(0.0, true - state["h0"]), 2)
                raise ValueError(mode)
            self.overrides.setdefault(sp["machine"], {})[sp["signal"]] = f

    def true_window(self, mid, t_from, t_to):
        """True history rows of a machine between two times (seconds)."""
        return [sig for (t, m, sig) in self.true_log if m == mid and t_from <= t <= t_to]
