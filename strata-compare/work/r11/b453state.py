#!/usr/bin/env python3
"""b453state.py LABEL — round 10 B.1: on a measurement-twin server (STRATA_STATE_HASH=1, $ELOG), the 32K / 64K / 120K
speed prompts, each read from scratch with ONE greedy output token; the engine's STATE_HASH line after each (main
model: L, gdn, ple, tail, pooled, kv, stale, dead, pooled_full, ple_prev; the drafter: mtp) -> results/r11/b453-LABEL.json.
Compare two labels with --compare A B: every main-model part must be equal; mtp may differ (the drafter's K/V)."""
import json, os, re, sys, time
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); sys.path.insert(0, str(WS / "scripts"))
if sys.argv[1] == "--compare":
    a, b = (json.loads((WS / f"results/r11/b453-{x}.json").read_text()) for x in sys.argv[2:4])
    for k in a:
        ha, hb = a[k]["hash"], b[k]["hash"]
        same = sorted(x for x in ha if ha[x] == hb.get(x)); diff = sorted(x for x in ha if ha[x] != hb.get(x))
        main_ok = not [x for x in diff if x != "mtp"]
        print(f"{k}: main model {'IDENTICAL' if main_ok else 'DIFFERENT'} (same: {','.join(same)}; different: {','.join(diff) or '-'}); "
              f"drafter pass {a[k].get('draft')} vs {b[k].get('draft')}")
    sys.exit(0)
from client import stream_chat
L, elog = sys.argv[1], Path(os.environ["ELOG"])
sp = {(p["size"], p["rep"]): p for p in json.load(open(WS / "prompts/speed.json"))}
out = {}
for size in ("32k", "64k", "120k"):
    off = elog.stat().st_size
    r = stream_chat("http://127.0.0.1:8081", {"model": "x", "messages": sp[(size, 0)]["messages"], "max_tokens": 1,
                                             "temperature": 0.0, "reasoning_effort": "none"})
    time.sleep(1.0)
    txt = elog.read_bytes()[off:].decode("utf-8", "replace")
    h = re.findall(r"STATE_HASH (.*)", txt)
    d = re.findall(r"strata draft kv: .*", txt)
    hv = dict(kv.split("=", 1) for kv in h[-1].split()) if h else {}
    out[size] = {"hash": hv, "draft": d[-1] if d else None, "ttft": r.get("ttft_s"), "prompt": r.get("prompt_tokens")}
    print(size, r.get("prompt_tokens"), round(r.get("ttft_s") or 0, 2), hv.get("mtp"), hv.get("kv"), (d[-1] if d else "")[:120])
(WS / f"results/r11/b453-{L}.json").write_text(json.dumps(out, indent=1))
