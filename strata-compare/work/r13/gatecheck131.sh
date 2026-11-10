#!/bin/bash
# gatecheck131.sh — round 13 Part 2.5: read every C*13.1 gate from logs/r13/batch.log and the result files; when ALL pass,
# create tmp/r13/go-soak131 (the queue's hold before the soak then releases by itself); otherwise print what failed and
# leave the hold closed (the waiter returns on the hold, and I read the results).
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
.venv/bin/python - <<'PY'
import re, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
log = (WS / "logs/r13/batch.log").read_text(errors="replace")
def block(start):
    i = log.rfind(start)
    return log[i:log.find("### ", log.find("\n", i) + 1)] if i >= 0 else ""
g = []
g.append(("exact7 = C*13", "exact7 cstar131: 7/7 identical to C*13" in log))
nb = block("RUN: work/r13/with_server.sh N131")
g.append(("needles 12 x 6/6", nb.count("score 6/6") == 12))
fb = block("RUN: work/r13/with_server.sh FAIL131")
g.append(("Stop at 120K", fb.count("PASS  stop120k") >= 7 and "FAIL  stop120k" not in fb))   # (the label FAIL131 holds "FAIL")
tb = block("RUN: work/r13/with_server.sh C131-tstop")
g.append(("#652 follow-ups", "14 of 14 follow-ups resumed" in tb and "5 of 5 follow-ups resumed" in tb))
g.append(("stops", "stoptest c131: ALL PASS" in tb))
g.append(("#931 copy / forged", "c131 copy: 20/20" in tb and "c131 forged: 0/30" in tb))
tt = [l for l in tb.splitlines() if l.startswith(("PASS stream", "FAIL stream"))]
g.append(("tool calls parsed", len(tt) == 6 and all("finish=tool_calls" in l and "('web_search'" in l and "error= " in l for l in tt)))
g.append(("repeat 3/3", "repeat3 rep-c131: outputs" in log and "3/3 identical" in block("RUN: work/r13/repeat3.sh rep-c131")))
rt = (WS / "results/r13/roundtrip-c131.md").read_text(errors="replace") if (WS / "results/r13/roundtrip-c131.md").exists() else ""
g.append(("round trips identical", sum(1 for l in rt.splitlines() if l.startswith("| small |") and "| 0 (None) |" in l) == 3))
bb = block("RUN: work/r13/with_server.sh BR131")
fails = [l for l in bb.splitlines() if l.startswith("FAIL")]
known = [l for l in fails if "favicon" in l or "prompt 110 tokens = 0 reused" in l]   # Round 10's two known non-bugs
g.append((f"browser ({len(fails)} fail, {len(known)} known)", "PASS" in bb and len(fails) == len(known)))
def ab(path, metric):
    p = WS / path
    if not p.exists():
        return None
    for l in p.read_text().splitlines():
        if l.startswith(f"| {metric}"):
            m = re.search(r"\| ([+-][\d.]+) % \|\s*$", l)
            return float(m.group(1)) if m else None
    return None
for path, name in (("results/r13/ab-ldr.md", "LDR"), ("results/r13/ab-decode.md", "decode")):
    d = ab(path, "decode, all requests" if name == "LDR" else "decode (tok/s)")
    r = ab(path, "ms per verify round")
    g.append((f"{name} screen within noise (decode {d} %, ms/round {r} %)", d is not None and r is not None and d >= -2.0 and r <= 2.0))
for name, ok in g:
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
allok = all(ok for _, ok in g)
print("GATES: " + ("ALL PASS -> releasing the soak hold" if allok else "NOT ALL PASS -> the soak waits (hold soak131)"))
if allok:
    (WS / "tmp/r13/go-soak131").touch()
PY
