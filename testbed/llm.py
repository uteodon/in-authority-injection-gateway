"""Model back-ends: Ollama (real runs) and a scripted model (plumbing tests without a GPU)."""
import json
import time
import urllib.request

from . import config as C


class OllamaLLM:
    def __init__(self, model, seed=0, temperature=C.TEMPERATURE, url=C.OLLAMA_URL):
        self.model, self.seed, self.temperature, self.url = model, seed, temperature, url

    def chat(self, messages, tools):
        body = {"model": self.model, "stream": False, "tools": tools, "messages": messages,
                "options": {"temperature": self.temperature, "seed": self.seed}}
        if self.model.startswith("qwen3"):
            body["think"] = False
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        t0 = time.time()
        for attempt, wait in enumerate((5, 20, 60, None)):
            try:
                with urllib.request.urlopen(req, timeout=C.REQUEST_TIMEOUT) as r:
                    out = json.loads(r.read())
                break
            except (OSError, ValueError):   # connection reset, timeout, broken JSON
                if wait is None:
                    raise
                time.sleep(wait)
        msg = out.get("message", {})
        msg["_latency_s"] = round(time.time() - t0, 3)
        return msg

    def warm_up(self):
        self.chat([{"role": "user", "content": "Reply with OK."}], [])


class ScriptedLLM:
    """Replays a fixed list of tool calls, then a final answer. Used to test the pipeline."""

    def __init__(self, calls, final="Done."):
        self.calls = list(calls)
        self.final = final
        self.model = "scripted"

    def chat(self, messages, tools):
        if self.calls:
            c = self.calls.pop(0)
            return {"role": "assistant", "content": "",
                    "tool_calls": [{"function": {"name": c["name"], "arguments": c["args"]}}],
                    "_latency_s": 0.0}
        return {"role": "assistant", "content": self.final, "_latency_s": 0.0}

    def warm_up(self):
        pass
