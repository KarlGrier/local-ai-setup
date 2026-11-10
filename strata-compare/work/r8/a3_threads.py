#!/usr/bin/env python3
"""a3_threads.py [--base URL] — round 8 A.3: thread affinity of the running engine during a prompt read and during decode.
Starts a 32K-prompt request (768 output tokens) in the background; samples every engine thread (work/r8/threads.py) for
6 s while the prompt is read, then for 8 s during its decode; then a long-reasoning request for a pure-decode sample."""
import json, subprocess, sys, threading, time
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); sys.path.insert(0, str(WS / "scripts"))
from client import stream_chat
base = "http://127.0.0.1:8081"
SET = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05, "reasoning_effort": "high"}
pids = [int(x) for x in subprocess.run(["pgrep", "-f", "strata --serve"], capture_output=True, text=True).stdout.split()]
pid = next(p for p in pids if open(f"/proc/{p}/comm").read().strip() == "strata")   # the engine, not the guard/monitor
speed = json.load(open(WS / "prompts/speed.json"))
doc = next(p for p in speed if (p["size"], p["rep"]) == ("32k", 2))["messages"]
res = {}
t = threading.Thread(target=lambda: res.update(r=stream_chat(base, dict(SET, model="x", max_tokens=768, messages=doc))))
t.start(); time.sleep(1.0)
sample = lambda lab, d: subprocess.run([str(WS / ".venv/bin/python"), str(WS / "work/r8/threads.py"), str(pid), lab,
                                         "--duration", str(d), "--interval", "0.5"])
print(f"engine pid {pid}: sampling during the 32K prompt read", flush=True); sample("A3-prompt", 6)
time.sleep(3.0)   # the read takes ~9.5 s: the decode of the same request follows
print("sampling during its decode", flush=True); sample("A3-decode", 8)
t.join()
print(f"32K request: ttft {res['r'].get('ttft_s'):.2f} s, decode {res['r'].get('decode_tps')}", flush=True)
