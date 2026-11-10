#!/bin/bash
# e2_hook2028.sh - #2028 follow-up (2026-10-12, the user's "test the cut-down hook in the same gap as the CMake check: one
# short server start, the exact request, and confirm it matches the full hook"). Called from work/suite/q4_quick.sh while
# 8080 is stopped (after the research capture, before the Q4 run), right after the #2027 configure (e1_cmake0431.sh).
#  a. no model: the exact request (parsed from the reply draft) through the full hook's server.py (r19-stockmeas43, the
#     measured one) and through the cut-down one (git archive v0.1.43 + publish/r19/08-hook-2028.diff), each with a
#     recording engine in place of `strata --serve`: what reaches the engine and the response must be identical
#  b. one short guarded server start on 8081: stock v0.1.43's engine (tmp/r19/v43, 7695859a) + the cut-down server.py,
#     the full hook's measured flags and env (configs/r19-hook2028.json = r19-st43-sp's), the exact request 300 times
#  c. checks -> results/r19/hook2028/summary.txt, then PASS or FAIL (the live shares are compared with the full hook's
#     measured run on the same flags, results/r19/sp-v43/sp-strata-v43-sp.jsonl)
# CHECK_ONLY=1 re-runs c. on the data a. and b. left (fixed 2026-10-12 21:2x: the request-line match also took the
# engine's startup line "strata serve: prompt chunk auto: ...", 301 lines for 300 requests; now "prompt N tokens" only)
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
P=$WS/.venv/bin/python; O=$WS/results/r19/hook2028; N=300
rm -f $O/PASS $O/FAIL
if [ "${CHECK_ONLY:-0}" != 1 ]; then
rm -f $O/equiv-*.json $O/real.jsonl $O/engine-lines.txt
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB EVICT_GLOB
echo "=== $(date -Is) #2028 hook check: a. no model"
$P work/r19/e2_hook_equiv.py tmp/r19/stockmeas43 configs/r19-hook2028.json $O/request.json $O/equiv-full.json > $O/equiv.txt 2>&1
$P work/r19/e2_hook_equiv.py tmp/r19/hook2028/tree configs/r19-hook2028.json $O/request.json $O/equiv-cut.json >> $O/equiv.txt 2>&1
tail -2 $O/equiv.txt | cut -c1-200
echo "=== $(date -Is) #2028 hook check: b. one short server start (cut-down hook, stock v0.1.43), the exact request $N times"
bringup/lib/with_server.sh r19-hook2028 configs/r19-hook2028.json -- \
  "$P work/r19/e2_hook_real.py http://127.0.0.1:8081 $O/request.json $N $O/real.jsonl > $O/real.txt 2>&1; cat $O/real.txt; \
   grep -E '^strata serve: prompt |probabilistic draft acceptance' \$ELOG > $O/engine-lines.txt" 2>&1 | grep -E 'start|ready|requests in|done|exited'
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
bringup/lib/kcheck.sh r19-hook2028 || echo "KERNEL CHECK FAILED after the hook server"
fi
echo "=== $(date -Is) #2028 hook check: c. checks"
$P - $O $N <<'PY'
import json, math, re, sys
from pathlib import Path
O, N = Path(sys.argv[1]), int(sys.argv[2])
out, ok = [], True
def check(name, cond, detail=""):
    global ok
    ok = ok and bool(cond)
    out.append(f"{'ok  ' if cond else 'FAIL'} {name}" + (f": {detail}" if detail else ""))
case = [x for x in json.load(open("results/r19/sp-v43/sp-cases.json")) if x["case"] == "arith-j3"][0]
try:
    full, cut = (json.loads((O / f"equiv-{w}.json").read_text()) for w in ("full", "cut"))
    c = cut["calls"][0]
    check("no model: what reaches the engine is identical (prompt ids, max_new, sampling, engine keys)",
          full["calls"] == cut["calls"] and len(cut["calls"]) == 1,
          f"{len(cut['calls'])} call, prompt {len(c['ids'])} ids, max_new {c['max_new']}, keys{c['engine_keys']!r}")
    check("no model: identical responses", full["response"] == cut["response"], f"strata_ids {cut['response'].get('strata_ids')}")
    check("no model: the engine's prompt is the issue's 76 rendered ids + the 32 appended ones",
          c["ids"] == case["prompt_ids"] + case["prefix"], f"{len(c['ids'])} ids")
    check("no model: min_p 0.05 reaches the engine from the config's sampling", " min_p=0.05" in c["engine_keys"])
except Exception as e:
    check("no model: comparison ran", False, repr(e)[:200])
rows = [json.loads(x) for x in open(O / "real.jsonl")] if (O / "real.jsonl").exists() else []
check(f"live: {N} responses", len(rows) == N, str(len(rows)))
check("live: every response carries 4 strata_ids", bool(rows) and all(isinstance(r["ids"], list) and len(r["ids"]) == 4 for r in rows))
el = (O / "engine-lines.txt").read_text().splitlines() if (O / "engine-lines.txt").exists() else []
pr = [x for x in el if re.match(r"strata serve: prompt [0-9]+ tokens", x)]
check("live: the engine read a 108-token prompt for every request",
      len(pr) == N and all(x.startswith("strata serve: prompt 108 tokens") for x in pr), f"{len(pr)} request lines")
check("live: STRATA_SPEC_PROB's probabilistic draft acceptance is on", any("probabilistic draft acceptance on" in x for x in el))
out.append(f"     requests that drafted: {sum(1 for x in pr if re.search(r'drafts accepted [0-9]+ of [1-9]', x))} of {len(pr)}")
def tally(rs):
    on = [r for r in rs if r["ids"] and r["ids"][:3] == case["path"]]
    return len(rs), len(on), sum(r["ids"][3] == 28 for r in on)
def z(a, n, b, m):
    p = (a + b) / (n + m); se = math.sqrt(p * (1 - p) * (1 / n + 1 / m)); zz = (a / n - b / m) / se if se else 0.0
    return zz, math.erfc(abs(zz) / math.sqrt(2))
ref = [r for r in map(json.loads, open("results/r19/sp-v43/sp-strata-v43-sp.jsonl")) if r["case"] == "arith-j3" and abs(r["temp"] - 0.6) < 1e-6]
if rows:
    (n1, on1, eq1), (n0, on0, eq0) = tally(rows), tally(ref)
    zk, pk = z(on1, n1, on0, n0); ze, pe = z(eq1, on1, eq0, on0)
    check("live vs the full hook's measured run: share on the 3-token path within noise (p > 0.01)", pk > 0.01,
          f"{on1}/{n1} = {100 * on1 / n1:.1f} % vs {on0}/{n0} = {100 * on0 / n0:.1f} %, z {zk:.2f}, p {pk:.2g}")
    check("live vs the full hook's measured run: '=' share within noise (p > 0.01)", pe > 0.01,
          f"{eq1}/{on1} = {100 * eq1 / on1:.1f} % vs {eq0}/{on0} = {100 * eq0 / on0:.1f} %, z {ze:.2f}, p {pe:.2g}")
    out.append(f"     4th ids of the kept samples: {sorted(set(r['ids'][3] for r in rows if r['ids'][:3] == case['path']))}")
out.append("RESULT: " + ("PASS" if ok else "FAIL"))
(O / "summary.txt").write_text("\n".join(out) + "\n")
(O / ("PASS" if ok else "FAIL")).touch()
print("\n".join(out))
PY
