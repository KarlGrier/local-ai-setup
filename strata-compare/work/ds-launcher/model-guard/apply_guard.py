#!/usr/bin/python3 -I
"""apply_guard.py SERVER.PY - the model-mismatch guard (Karl 11-06), the same three small edits in either server tree.

A request that names the model which is NOT running gets a clear 400 instead of the running model's answer. Only the exact
ids listed under "model_not_running" in the server's config: no key (every test config, the rollback), no check; any other
name (LDR's, the bench client's "strata", "x", ...) is served as always. No auto-swapping.
"""
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8").read()
edits = [
    ('''        self.config_effort = None                     # #1641: the config's "reasoning_effort": the level for requests with none
''',
     '''        self.config_effort = None                     # #1641: the config's "reasoning_effort": the level for requests with none
        self.not_running = {}                         # Karl 11-06: the config's "model_not_running": {the other model's id: its error text}
'''),
    ('''                req = json.loads(self._body() or b"{}")
                if not isinstance(req, dict):
                    raise ValueError("send a JSON object")
                if path.startswith("/v1/responses/"):        # retrieve/delete/cancel/compact: nothing is stored
''',
     '''                req = json.loads(self._body() or b"{}")
                if not isinstance(req, dict):
                    raise ValueError("send a JSON object")
                # Karl 11-06: a request naming the model that is NOT running gets a clear error, not this model's answer.
                # Only the exact ids the config lists; any other name is served as always. 400: clients do not retry it
                named = req.get("model")
                why = svc.not_running.get(named) if isinstance(named, str) and \\
                    path in ("/v1/chat/completions", "/v1/messages", "/v1/responses") else None
                if why:
                    print(f"[strata] refused a request for {named}: this server runs {svc.model}", flush=True)
                    if path == "/v1/responses":
                        self._json(400, responses_error_body(why, "invalid_request_error", code="model_not_running"))
                    elif path == "/v1/messages":
                        self._json(400, {"type": "error", "error": {"type": "invalid_request_error", "message": why}})
                    else:
                        self._json(400, {"error": {"type": "invalid_request_error", "code": "model_not_running", "message": why}})
                    return
                if path.startswith("/v1/responses/"):        # retrieve/delete/cancel/compact: nothing is stored
'''),
    ('''    if cfg.get("reasoning_effort") is not None:         # #1641: the thinking level of requests that name none
''',
     '''    if cfg.get("model_not_running"):                    # Karl 11-06: {the other model's id: the error its requests get}
        svc.not_running = {k: v for k, v in cfg["model_not_running"].items() if isinstance(k, str) and isinstance(v, str) and v}
        print(f"[strata] requests naming {', '.join(svc.not_running)} get a clear error (model_not_running in the config)", flush=True)
    if cfg.get("reasoning_effort") is not None:         # #1641: the thinking level of requests that name none
'''),
]
for a, b in edits:
    if s.count(a) != 1:
        raise SystemExit(f"{p}: expected one match, found {s.count(a)}: {a[:70]!r}")
    s = s.replace(a, b)
open(p, "w", encoding="utf-8").write(s)
print("patched", p)
