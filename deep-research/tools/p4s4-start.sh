#!/bin/bash
# p4s4-start.sh GAP10_PID - phase 4 item 4 stage 2 with item 2 bundled in (the user, 10-23: "bundle item 2 (the 'not
# yet' check) into the next item's stage 2-3 runs ... Continue with the 'tried / ruled out' list next"): waits for
# strata-compare's gap 10 to end normally and 8080 to answer, then
#   1 builds the tried list for o01's files (tools/tried-list.py through strata-proxy; cached by content, so the run
#     loads it and its extraction calls stay out of the run's calls and tokens)
#   2 a smoke test of the in-run fresh check (local_deep_research.deep.notyet) on stage 3's o03 report: it must finish
#     without an error (EN 18286's verdict is reported, not required here)
#   3 starts deep-research-bench.service on queue-plan-p4s4.json: o01 + o03, deep medium, citation check xhigh,
#     items setup + critic + tried + notyet (label p4s4); the "without" side is stage 3 (p4s3: setup + critic)
# Log: logs/p4-stage4-start.log.
WS=/home/USER/ai/deep-research; cd $WS
LOG=$WS/logs/p4-stage4-start.log
G=/home/USER/ai-speed-testing/strata-compare/results/r22/gap10/summary.txt
say() { echo "$(date '+%F %T') p4s4-start: $*" | tee -a $LOG; }
nostart() { say "$* - item 4 stage 2 NOT started"; notify-send -u critical "phase 4 item 4 not started" "$*" 2> /dev/null || true; exit 1; }
P=${1:?gap 10 pid}
say "waiting for gap 10 (pid $P)"
while [ -d /proc/$P ]; do sleep 30; done
last=$(tail -n 80 $G)
grep -q "gap 10 done after" <<< "$last" || nostart "gap 10 did not finish normally (no 'gap 10 done' line)"
grep -qE "KERNEL CHECK FAILED|KCHECK FAILED" <<< "$last" && nostart "gap 10 ended with a kernel-check failure"
grep -q "switch logged at" <<< "$last" && build="P021m (switched in gap 10)" || build="P021n (no switch)"
curl -s -m 15 -o /dev/null http://127.0.0.1:8080/v1/models || nostart "8080 does not answer after the gap"
say "gap 10 ended normally; 8080 = $build"
.venv/bin/python -I tools/services_check.py >> $LOG 2>&1 || say "services_check reported a problem (see above)"
./run-ldr.sh proxy >> $LOG 2>&1
curl -s -m 10 -o /dev/null http://127.0.0.1:8090/v1/models || nostart "strata-proxy (8090) does not answer"
say "1 tried list for o01's files"
.venv/bin/python tools/tried-list.py results/bench2/files/strata-REPORT.md results/bench2/files/strata-NOTES.md >> $LOG 2>&1 \
  || nostart "the tried list was not built"
grep -a "^tried list\|^cached:" $LOG | tail -1 | sed 's/^/  /' | tee -a $LOG
say "2 smoke test: the in-run fresh check on stage 3's o03 report"
.venv/bin/python - >> $LOG 2>&1 <<'PY' || nostart "the fresh-check smoke test failed"
import fcntl, json, re, sys, time
from pathlib import Path
import requests
from local_deep_research.deep import notyet
WS = Path("/home/USER/ai/deep-research")
rep = WS / "results/bench2/runs/screen-deep-p4s3/o03/deep/report.md"
body = re.split(r"(?m)^#{1,3} (Setup check|Check these|Citation check|Sources|References)\s*$", rep.read_text())[0]
def llm(prompt):
    b = {"model": "strata", "messages": [{"role": "user", "content": prompt}], "stream": False, "temperature": 1.0,
         "max_tokens": 30000, "reasoning_effort": "medium"}
    r = requests.post("http://127.0.0.1:8090/v1/chat/completions", json=b, timeout=3600, proxies={"http": None, "https": None})
    r.raise_for_status()
    return r.json()["choices"][0]["message"].get("content") or ""
lock = open(WS / "run" / "bench.lock", "w"); fcntl.flock(lock, fcntl.LOCK_EX)
t0 = time.time()
res = notyet.check(llm, body)
lock.close()
(WS / "results/bench2/replays").mkdir(parents=True, exist_ok=True)
(WS / "results/bench2/replays/notyet-module-smoke-o03-p4s3.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
v = [((c.get("judge") or {}).get("verdict")) for c in res.get("checked", [])]
en = [c for c in res.get("checked", []) if "18286" in (c.get("quote") or "")]
print(f"smoke: {res.get('claims_found')} claims found, {len(v)} checked, outdated {v.count('outdated')}, still true "
      f"{v.count('still_true')}, unclear {v.count('unclear')}; EN 18286 "
      + (", ".join((c.get('judge') or {}).get('verdict') or '?' for c in en) if en else "not among the checked")
      + f"; {round(time.time() - t0)} s" + (f"; ERROR {res['error']}" if res.get("error") else ""))
sys.exit(1 if res.get("error") else 0)
PY
grep -a "^smoke:" $LOG | tail -1 | sed 's/^/  /' | tee -a $LOG
say "3 starting deep-research-bench.service on queue-plan-p4s4.json (o01 + o03 with setup + critic + tried + notyet; 8080 = $build)"
systemctl --user start deep-research-bench.service && say "started" || say "systemctl start failed"
