#!/usr/bin/env python3
"""mkcfg.py NAME ENGINE_DIR [--set FLAG VALUE]... [--add FLAG [VALUE]]... [--drop FLAG]... [--env K=V]... [--comment TEXT]

Round 3: writes configs/NAME.json = configs/Cstar2.json (never modified) with the engine binary ENGINE_DIR/strata,
the v0.1.12 server (strata-r3-run unless --server), its own engine log, and the given flag edits.
"""
import json
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
name, engine = sys.argv[1], sys.argv[2]
cfg = json.loads((WS / "configs/Cstar2.json").read_text())
args = cfg["args"]
server = str(WS / "strata-r3-run/serve/server.py")
comment = ""
i = 3


def find(flag):
    return args.index(flag) if flag in args else -1


while i < len(sys.argv):
    op = sys.argv[i]
    if op == "--set":
        flag, val = sys.argv[i + 1], sys.argv[i + 2]
        j = find(flag)
        if j < 0:
            args += [flag, val]
        else:
            args[j + 1] = val
        i += 3
    elif op == "--add":
        flag = sys.argv[i + 1]
        if i + 2 < len(sys.argv) and not sys.argv[i + 2].startswith("--"):
            args += [flag, sys.argv[i + 2]]
            i += 3
        else:
            args += [flag]
            i += 2
    elif op == "--drop":
        flag = sys.argv[i + 1]
        j = find(flag)
        if j >= 0:
            has_val = j + 1 < len(args) and not args[j + 1].startswith("--")
            del args[j:j + (2 if has_val else 1)]
        i += 2
    elif op == "--env":
        k, v = sys.argv[i + 1].split("=", 1)
        cfg.setdefault("env", {})[k] = v
        i += 2
    elif op == "--server":
        server = sys.argv[i + 1]
        i += 2
    elif op == "--comment":
        comment = sys.argv[i + 1]
        i += 2
    else:
        sys.exit(f"unknown option {op}")

cfg["exe"] = str(Path(engine).resolve() / "strata")
cfg["server"] = server
cfg["log"] = str(WS / f"logs/engine-{name}.log")
cfg["args"] = args
cfg["_comment"] = f"Round 3 candidate {name}: Cstar2 flags on {cfg['exe']}. {comment}".strip()
out = WS / f"configs/{name}.json"
out.write_text(json.dumps(cfg, indent=1) + "\n")
print(out, " ".join(a for a in args if a.startswith("--")))
