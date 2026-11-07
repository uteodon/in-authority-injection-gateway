"""Gateway: every tool call the agent proposes passes through here.

Always on (part of any real tool API):
  - normalization: fixes harmless format slips (e.g. a list sent as a JSON string,
    enum in wrong case) and records each fix in the audit log
  - schema validation: unknown tool, missing/unknown arguments, wrong types, bad enum

Defense layers are pluggable objects with a `check(name, args, ctx) -> None | reason`.
Week 2 ships RoleCheck (L2, first part). L1, L3, L4 are added in later weeks.
"""
import json
import time

from . import config as C
from .tools import SCHEMA_BY_NAME


# ------------------------------------------------------------------ normalization
def normalize(name, args):
    fixes = []
    if isinstance(args, str):
        try:
            args = json.loads(args)
            fixes.append("args_json_string")
        except json.JSONDecodeError:
            return args, fixes
    if not isinstance(args, dict):
        return args, fixes
    props = SCHEMA_BY_NAME.get(name, {}).get("properties", {})
    out = {}
    for k, v in args.items():
        spec = props.get(k, {})
        t = spec.get("type")
        if t == "array" and isinstance(v, str):
            try:
                parsed = json.loads(v)
                v = parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                v = [x.strip() for x in v.split(",") if x.strip()]
            fixes.append(f"{k}:str->list")
        if t == "integer" and isinstance(v, str) and v.strip().lstrip("-").isdigit():
            v = int(v.strip())
            fixes.append(f"{k}:str->int")
        if t == "string" and "enum" in spec and isinstance(v, str) and v not in spec["enum"]:
            low = v.strip().lower()
            if low in spec["enum"]:
                v = low
                fixes.append(f"{k}:case")
        if t == "array" and isinstance(v, list):
            enum = spec.get("items", {}).get("enum")
            if enum:
                nv = [x.strip().lower() if isinstance(x, str) and x.strip().lower() in enum else x
                      for x in v]
                if nv != v:
                    fixes.append(f"{k}:item_case")
                v = nv
            # Canonical form of "no parts": [] and ["none"] mean the same thing.
            if enum and "none" in enum and v == []:
                v = ["none"]
                fixes.append(f"{k}:empty->none")
        out[k] = v
    return out, fixes


# ------------------------------------------------------------------ schema validation
_PY = {"string": str, "integer": int, "array": list}


def validate(name, args):
    if name not in SCHEMA_BY_NAME:
        return f"unknown tool '{name}'"
    if not isinstance(args, dict):
        return "arguments must be a JSON object"
    sch = SCHEMA_BY_NAME[name]
    props = sch["properties"]
    for r in sch["required"]:
        if r not in args or args[r] in (None, ""):
            return f"missing required argument '{r}'"
    for k, v in args.items():
        if k not in props:
            return f"unknown argument '{k}'"
        spec = props[k]
        py = _PY.get(spec["type"])
        if py and not isinstance(v, py):
            return f"argument '{k}' must be {spec['type']}"
        if "enum" in spec and v not in spec["enum"]:
            return f"argument '{k}' must be one of {spec['enum']}"
        if spec["type"] == "array" and "enum" in spec.get("items", {}):
            bad = [x for x in v if x not in spec["items"]["enum"]]
            if bad:
                return f"argument '{k}' has invalid items {bad}; allowed {spec['items']['enum']}"
    return None


# ------------------------------------------------------------------ layers
class RoleCheck:
    """L2 (first part): the authenticated user's role must permit the tool."""
    name = "L2_role"

    def check(self, name, args, ctx):
        if name not in C.ROLE_PERMISSIONS[ctx["role"]]:
            return f"role '{ctx['role']}' is not allowed to call {name}"
        return None


# ------------------------------------------------------------------ gateway
class Gateway:
    def __init__(self, env, layers=(), feedback="Please continue the user's task with other tools."):
        self.env = env
        self.layers = list(layers)
        self.feedback = feedback
        self.audit = []

    def handle(self, name, raw_args, ctx):
        t0 = time.time()
        args, fixes = normalize(name, raw_args)
        entry = {"step": ctx.get("step"), "tool": name, "raw_args": raw_args, "args": args,
                 "fixes": fixes, "write": name in C.WRITE_TOOLS}
        err = validate(name, args)
        if err:
            entry.update(decision="invalid", reason=err, executed=False)
            result = {"error": f"Invalid call: {err}"}
        else:
            reason, layer = None, None
            lctx = {**ctx, "env": self.env}
            for L in self.layers:
                reason = L.check(name, args, lctx)
                if reason:
                    layer = L.name
                    break
            if reason:
                entry.update(decision="blocked", layer=layer, reason=reason, executed=False)
                result = {"error": f"Blocked by policy: {reason}. {self.feedback}"}
            else:
                try:
                    result = self.env.call(name, args)
                    entry.update(decision="allowed", executed=True)
                except Exception as e:  # tool-level error (e.g. unknown work order)
                    entry.update(decision="tool_error", reason=str(e), executed=False)
                    result = {"error": str(e)}
        entry["latency_ms"] = round((time.time() - t0) * 1000, 2)
        self.audit.append(entry)
        return result
