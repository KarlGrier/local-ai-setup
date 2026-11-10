#!/usr/bin/env python3
"""mk_bcfg.py - round 19 Part B: the candidate's configs (all from configs/r19-cand.json = C*16.1's flags and switches on
runbook r19's patched build) and their twins (runbook r19's twin build: --teacher-force, force hooks, STRATA_STATE_HASH=1,
--adapt-swaps 0, as twin161.json).
  r19-cand            as C*16.1 serves (STRATA_PREFILL_CPU_SHARE=0, STRATA_SPEC_EXACT=1, the cost gate)
  r19-cand-sh04       + STRATA_PREFILL_CPU_SHARE=0.4                       (step 3)
  r19-cand-hs         + STRATA_PREFILL_HELPER_SOURCE=1                      (step 4)
  r19-cand-sp         STRATA_SPEC_EXACT removed, STRATA_SPEC_PROB=1, the cost gate kept (step 5)
  r19-cand-ts         STRATA_ROUTE_TAIL_SKIP unset (upstream's default)     (step 2's check; r19-cand-ts0 = explicit 0)
  r19-twin, r19-twin-sh04, r19-twin-hs   the twins"""
import json
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); C = WS / "configs"; R = WS / "bringup/out/r19"
base = json.loads((C / "r19-cand.json").read_text())
shared = (C / "Cstar161.shared-settings.json").read_text()


def put(name, c, note):
    c = json.loads(json.dumps(c)); c["log"] = str(WS / f"logs/engine-{name}.log"); c["fallback"] = None
    c["_comment"] = f"Round 19 {name}: {note}"
    (C / f"{name}.json").write_text(json.dumps(c, indent=1) + "\n"); (C / f"{name}.shared-settings.json").write_text(shared)
    print(name, {k: v for k, v in c["env"].items() if k in ("STRATA_PREFILL_CPU_SHARE", "STRATA_PREFILL_HELPER_SOURCE", "STRATA_SPEC_EXACT", "STRATA_SPEC_PROB", "STRATA_ROUTE_TAIL_SKIP", "STRATA_STATE_HASH")}, c["exe"].split("/")[-2])


def twin(c):
    t = json.loads(json.dumps(c)); t["exe"] = str(R / "engine-twin/strata"); t["server"] = str(R / "strata-twin/serve/server.py")
    t["env"]["STRATA_STATE_HASH"] = "1"; t["args"] += ["--adapt-swaps", "0"]; return t


put("r19-cand", base, "C*16.1's flags and switches on v0.1.42 + patches/r19p28 (runbook r19's patched build)")
s = json.loads(json.dumps(base)); s["env"]["STRATA_PREFILL_CPU_SHARE"] = "0.4"; put("r19-cand-sh04", s, "the candidate + STRATA_PREFILL_CPU_SHARE=0.4")
h = json.loads(json.dumps(base)); h["env"]["STRATA_PREFILL_HELPER_SOURCE"] = "1"; put("r19-cand-hs", h, "the candidate + STRATA_PREFILL_HELPER_SOURCE=1")
p = json.loads(json.dumps(base)); p["env"].pop("STRATA_SPEC_EXACT"); p["env"]["STRATA_SPEC_PROB"] = "1"
put("r19-cand-sp", p, "the candidate with upstream's STRATA_SPEC_PROB=1 instead of our STRATA_SPEC_EXACT=1, the cost gate kept")
t0 = json.loads(json.dumps(base)); t0["env"]["STRATA_ROUTE_TAIL_SKIP"] = "0"; put("r19-cand-ts0", t0, "the candidate + an explicit STRATA_ROUTE_TAIL_SKIP=0")
put("r19-cand-ts", base, "the candidate, STRATA_ROUTE_TAIL_SKIP unset (upstream's default rule decides)")
put("r19-twin", twin(base), "the candidate's twin (4 MEASUREMENT commits)")
put("r19-twin-sh04", twin(s), "the twin + STRATA_PREFILL_CPU_SHARE=0.4")
put("r19-twin-hs", twin(h), "the twin + STRATA_PREFILL_HELPER_SOURCE=1")
