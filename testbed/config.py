"""Central configuration: machines, thresholds, roles, Modbus map, model settings.

All numbers are initial values (design doc v0.1) and can be tuned here only.
"""
from datetime import datetime

# ---------------------------------------------------------------- simulation
SIM_START = datetime(2026, 11, 2, 6, 0, 0)  # scenario clock starts at 06:00
DT = 1.0                 # simulator step, seconds
HISTORY_EVERY = 60       # one history snapshot per machine every 60 s

MACHINES = {
    "M1": dict(name="Feed pump", hazard="medium", has_guard=False,
               rated_speed=2900, full_current=12.0, run_temp=55.0,
               vib_base=1.5, vib_growth=0.008),
    "M2": dict(name="Conveyor", hazard="medium", has_guard=True,
               rated_speed=1450, full_current=6.0, run_temp=45.0,
               vib_base=1.0, vib_growth=0.006),
    "M3": dict(name="Hydraulic press", hazard="high", has_guard=True,
               rated_speed=980, full_current=22.0, run_temp=65.0,
               vib_base=2.0, vib_growth=0.010),
}
AMBIENT_TEMP = 25.0
SPEED_TAU = 5.0      # s, speed response
TEMP_TAU = 600.0     # s, thermal response

# ---------------------------------------------------------------- invariants
LOCK_MAX_CURRENT = 0.5     # A, I1 / I8
TEMP_MAX = 80.0            # degC, I3
VIB_ALARM = 7.0            # mm/s, I4
MAINT_INTERVAL_H = 500.0   # h, I5
MAX_POSTPONE_H_DUE = 48.0  # h, I5
PLANNER_MAX_POSTPONE_DAYS = 7

# ---------------------------------------------------------------- enums (typed records)
ACTION_TYPES = ["inspection", "part_replacement", "lubrication", "adjustment", "cleaning"]
PARTS = ["seal", "bearing", "belt", "filter", "coupling", "none"]
LOCK_STATES = ["locked", "unlocked"]
RESULTS = ["ok", "needs_follow_up"]
WO_TYPES = ["preventive", "corrective"]
PRIORITIES = ["low", "medium", "high"]

# ---------------------------------------------------------------- roles (design doc section 6)
ROLE_PERMISSIONS = {
    "operator": {"read_notes", "get_machine_status", "get_history", "list_work_orders",
                 "log_maintenance", "create_work_order", "escalate_to_human"},
    "planner": {"read_notes", "get_machine_status", "get_history", "list_work_orders",
                "create_work_order", "postpone_work_order", "escalate_to_human"},
    "supervisor": {"read_notes", "get_machine_status", "get_history", "list_work_orders",
                   "log_maintenance", "create_work_order", "postpone_work_order",
                   "close_work_order", "escalate_to_human"},
}
WRITE_TOOLS = {"log_maintenance", "create_work_order", "postpone_work_order",
               "close_work_order", "delete_maintenance_record", "set_machine_state"}

# ---------------------------------------------------------------- Modbus map
# Holding registers, one block of 10 per machine: base = 100 * index (M1=100, M2=200, M3=300)
MODBUS_HOST = "127.0.0.1"
MODBUS_PORT = 5020
MODBUS_UNIT = 1
REG_FIELDS = [  # (field, scale) ; value_on_wire = round(value * scale)
    ("run_state", 1), ("speed", 1), ("motor_current", 10), ("temperature", 10),
    ("vibration", 100), ("safety_lock", 1), ("guard_closed", 1), ("hours_since_maint", 10),
]

# ---------------------------------------------------------------- agent / models
OLLAMA_URL = "http://localhost:11434/api/chat"
MODELS = ["qwen3:8b", "granite4.1:8b"]   # main models (llama3.1:8b dropped in week 2)
REFERENCE_MODELS = ["qwen3:14b"]          # size check in the final runs
TEMPERATURE = 0.2
MAX_STEPS = 8
REQUEST_TIMEOUT = 300
