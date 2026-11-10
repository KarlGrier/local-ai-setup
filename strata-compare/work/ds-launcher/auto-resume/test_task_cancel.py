#!/usr/bin/python3 -I
"""Real DS Harness code on a scratch home + port + stub model: a real running turn, read and cancelled by the real
ds-harness-task.py executed as a program. Needs the scratch instance on 3099 (see NOTES in this folder)."""
import importlib.util, json, os, subprocess, sys, time, uuid
TASK = os.path.expanduser("~/ai-speed-testing/strata-compare/configs/usability/bin/ds-harness-task.py")
HOME = os.path.expanduser("~/ai-speed-testing/strata-compare/work/ds-launcher/auto-resume/scratch/home")
WSP = os.path.expanduser("~/ai-speed-testing/strata-compare/work/ds-launcher/auto-resume/scratch/workspace")
sp = importlib.util.spec_from_file_location("t", TASK); t = importlib.util.module_from_spec(sp); sp.loader.exec_module(t)
PORT = 3099
ck = t.sign_in(HOME, PORT)
def run(what):
    p = subprocess.run([TASK, what, "--home", HOME, "--port", str(PORT)], capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()
def rpc(m, args): return t.rpc(PORT, ck, m, {"args": args})
print("before:", run("running"))
s = rpc("session/create", {"request": {"cwd": WSP}})
sid = s["sessionId"]
print("create keys:", sorted(s))
print("prompt:", rpc("session/prompt", {"request": {"sessionId": sid, "requestId": str(uuid.uuid4()), "mode": "queue", "content": [{"type": "text", "text": "say a long thing"}]}}))
for i in range(30):
    r = run("running")
    if r[1] == "running 1": break
    time.sleep(1)
print(f"after prompt ({i} s):", r)
time.sleep(5); print("still, 5 s later:", run("running"))
print("cancel:", run("cancel"))
t0 = time.time()
for i in range(60):
    r = run("running")
    if r[1] == "running 0": break
    time.sleep(0.5)
print(f"after cancel ({time.time()-t0:.1f} s):", r)
print("cancel with nothing running:", run("cancel"))
print("the session stays:", any(i.get("sessionId") == sid for i in rpc("session/list", {"_request": {}})["items"]))
print("wrong port:", subprocess.run([TASK, "running", "--home", HOME, "--port", "3098"], capture_output=True, text=True).stdout.strip())
print("no log:", subprocess.run([TASK, "running", "--home", WSP, "--port", "3099"], capture_output=True, text=True).stdout.strip())
