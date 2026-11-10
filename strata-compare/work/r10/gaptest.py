#!/usr/bin/env python3
"""gaptest.py --base URL --label L — round 9: the SSD keepalive's case. One chat, short turns (max 96 tokens, your settings)
after idle gaps of 1-90 s (fixed order); per turn TTFT and total time -> results/r10/gaptest.jsonl. STRATA_SSD_KEEPALIVE
keeps reading for 60 s after the last request, so gaps below 60 s are where it can help; the 90 s gap is the control."""
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r6")
from webreplay import stream, USER
WS = Path("/home/USER/ai-speed-testing/strata-compare")
GAPS = [1, 45, 5, 15, 90, 1, 15, 5, 45, 30, 30]
ap = argparse.ArgumentParser(); ap.add_argument("--base", required=True); ap.add_argument("--label", required=True)
a = ap.parse_args()
msgs = [{"role": "user", "content": "Let's play a word game. Name one animal, nothing else."}]
r = stream(a.base, msgs, {**USER, "max_tokens": 96}); msgs.append({"role": "assistant", "content": r["text"] or "Cat."})
for i, g in enumerate(GAPS):
    time.sleep(g)
    msgs.append({"role": "user", "content": f"Turn {i + 1}: name a different animal whose name starts with the letter "
                                            f"{'BDFGHKLMPRSTW'[i % 13]}. Just the name."})
    r = stream(a.base, msgs, {**USER, "max_tokens": 96})
    msgs.append({"role": "assistant", "content": r["text"] or "Ok."})
    rec = {"label": a.label, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "turn": i + 1, "gap_s": g, "ttft": r["ttft"],
           "total": r["total"], "usage": r["usage"], "error": r["error"]}
    with open(WS / "results/r10/gaptest.jsonl", "a") as f: f.write(json.dumps(rec) + "\n")
    print(f"turn {i + 1:2d} gap {g:3d} s  ttft {r['ttft']:.3f} s  total {r['total']:.2f} s  err={r['error']}")
