#!/usr/bin/env python3
"""mkcfg.py NEW BASE [key=value ...] [env.K=V ...] [env-K] [args+=--flag,val] [args-=--flag] [args:--flag=val] —
round 10: write configs/NEW.json from configs/BASE.json with overrides, its own engine log, no fallback, and a copy of
BASE's shared settings (your chat settings). exe=/server= take workspace-relative paths."""
import json, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
new, base = sys.argv[1], sys.argv[2]
c = json.loads((WS / f"configs/{base}.json").read_text())
c["log"] = str(WS / f"logs/engine-{new}.log"); c["fallback"] = None
for op in sys.argv[3:]:
    if op.startswith("env."):
        k, v = op[4:].split("=", 1); c.setdefault("env", {})[k] = v
    elif op.startswith("env-"):
        c.get("env", {}).pop(op[4:], None)
    elif op.startswith("args+="):
        c["args"] += op[6:].split(",")
    elif op.startswith("args-="):
        f = op[6:]; a = c["args"]; i = a.index(f)
        del a[i:i + (2 if i + 1 < len(a) and not a[i + 1].startswith("--") else 1)]
    elif op.startswith("args:"):
        f, v = op[5:].split("=", 1); a = c["args"]
        if f in a: a[a.index(f) + 1] = v
        else: a += [f, v]
    else:
        k, v = op.split("=", 1)
        if k in ("exe", "server", "cwd") and not v.startswith("/"): v = str(WS / v)
        c[k] = v
(WS / f"configs/{new}.json").write_text(json.dumps(c, indent=1) + "\n")
sh = WS / f"configs/{base}.shared-settings.json"
if sh.exists(): (WS / f"configs/{new}.shared-settings.json").write_text(sh.read_text())
print(f"configs/{new}.json: exe {c['exe']} server {c.get('server')} env {c.get('env')} args tail {' '.join(c['args'][-12:])}")
