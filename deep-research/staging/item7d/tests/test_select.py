"""7d's selection rule and its config (pure; no providers asked). python -I -B test_select.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _offline as T  # noqa: E402  (sets up paths first)

import search_route as R  # noqa: E402

n_ok = 0


def ok(cond, what):
    global n_ok
    assert cond, what
    n_ok += 1


# --- config -----------------------------------------------------------------------------------------------------
cfg, err = R.load_config()
ok(err == "", f"staged paid-route.json loads: {err}")
ok(set(cfg["select"]) == {"7d", "7dx"}, f"only 7d / 7dx select: {cfg['select']}")
for p in ("fallback", "types", "7a", "7b", "7c"):
    ok(R.select_config(cfg, p) is None, f"{p} has no _select (unchanged)")
sel = R.select_config(cfg, "7d")
ok(sel == {"mode": "followup", "late": 100, "follow_after_s": 900, "per_sub": 3, "per_lead": 10, "skip_unknown": 30},
   f"7d rule values {sel}")
ok(R.select_config(cfg, "7dx") == sel, "7dx uses the same rule")
ok(R.decide("RTX 5060 Ti 16GB price Best Buy November 2026", cfg, "7dx")["paid"] == ["exa"], "7dx: product -> Exa")
ok(R.decide("KTransformers expert prefetch routing profile", cfg, "7dx")["paid"] == ["tavily"], "7dx: other -> Tavily")
ok(R.decide("RTX 5060 Ti 16GB price Best Buy November 2026", cfg, "7d")["paid"] == ["tavily"], "7d: product -> Tavily")
for p in ("7d", "7dx"):
    for tag in R.TAGS:
        r = R.rule_for(cfg, p, tag)
        ok(r["paid"] and not r["free"] and not r["fallback"], f"{p}/{tag}: one paid source, no free, no fallback")
# the live table's profiles are all still there, unchanged
live = json.loads(Path(T.LIVE_TOOLS, "paid-route.json").read_text())["profiles"]
staged = json.loads(Path(T.STAGE, "tools", "paid-route.json").read_text())["profiles"]
ok(all(staged[k] == v for k, v in live.items()), "every live profile is unchanged in the staged table")
ok(set(staged) - set(live) == {"7d", "7dx"}, "the staged table only adds 7d and 7dx")

bad_selects = [{"mode": "fifo"}, {"late": -1}, {"per_sub": True}, {"per_lead": 2.5}, {"bogus": 1}, "x"]
for b in bad_selects:
    p = T.TMP / "bad.json"
    raw = json.loads(Path(T.STAGE, "tools", "paid-route.json").read_text())
    raw["profiles"]["7d"]["_select"] = b
    p.write_text(json.dumps(raw))
    c2, e2 = R.load_config(p)
    ok(e2 and c2["profiles"] == {"fallback": {"*": R._RULE_FALLBACK}} and c2["select"] == {} and not c2["enabled"],
       f"broken _select {b!r} -> routing off ({e2})")
raw = json.loads(Path(T.STAGE, "tools", "paid-route.json").read_text())
raw["profiles"]["fallback"]["_select"] = {}
p.write_text(json.dumps(raw))
ok(R.load_config(p)[1], "_select on the routing-off profile is refused")
ok("select" in R.load_config(T.TMP / "missing.json")[0], "the built-in default has an (empty) select table")

# --- agent labels -------------------------------------------------------------------------------------------------
for a, want in (("lead", "lead"), ("sub3", "sub3"), ("sub12:llama.cpp offload", "sub12"), ("report", "report"),
                ("", "?"), (None, "?"), ("  ", "?")):
    ok(R.agent_name(a) == want, f"agent_name({a!r}) = {R.agent_name(a)!r}")


# --- the rule -----------------------------------------------------------------------------------------------------
def run(stream, sel=sel):
    """stream: [(agent, seconds since the run's first search)] -> list of (picked, why)."""
    st = R.new_state(1000.0)
    return [R.select_step(st, a, sel, 1000.0 + t) for a, t in stream], st


# opening: the lead's opening and the first wave get nothing; the lead's follow-up (>= 15 min) starts the follow-up
stream = [("lead", 0), ("lead", 5)] + [("sub1", 60 + i) for i in range(20)] + [("sub2", 400 + i) for i in range(10)]
stream += [("lead", 2000)] + [("lead", 2001 + i) for i in range(11)] + [("sub3", 2100 + i) for i in range(6)]
got, st = run(stream)
picks = [i + 1 for i, (p, _) in enumerate(got) if p]
ok(not any(p for p, _ in got[:32]), "lead opening + the first wave (32 searches): no paid source")
ok(st["follow_at"] == 33, f"follow-up starts at the lead's search 33 ({st['follow_at']})")
ok(picks == list(range(33, 43)) + [45, 46, 47], f"lead 10 then sub3's first 3: {picks}")
ok("had its 10" in got[43][1] and "had its 3" in got[-1][1], "caps give their reason")
ok(run(stream)[0] == got, "deterministic: the same stream gives the same answers")

# the time guard: a lead search right after sub1 started (parallel opening) does not open the follow-up phase
got, st = run([("lead", 0), ("sub1", 10), ("lead", 30), ("sub1", 40)] + [("sub1", 50 + i) for i in range(5)])
ok(st["follow_at"] is None and not any(p for p, _ in got), "lead search 30 s in: still the opening")
# ... and a lead follow-up after 900 s does
got, st = run([("lead", 0), ("sub1", 10), ("lead", 900), ("sub2", 950)])
ok(st["follow_at"] == 3 and [p for p, _ in got] == [False, False, True, True], f"lead at 900 s opens it {got}")

# no lead follow-up at all: the late backstop opens it at search 101, caps per subagent still apply
stream = [("lead", 0)] + [(f"sub{1 + i // 20}", 10 + i) for i in range(160)]
got, st = run(stream)
picks = [i + 1 for i, (p, _) in enumerate(got) if p]
ok(picks[0] == 101 and st["follow_at"] is None, f"late backstop from search 101 ({picks[:3]})")
# search 101 is sub5's last search (sub5 = searches 82-101), then sub6 = 102-121, sub7 = 122-141, sub8 = 142-161
ok(picks == [101, 102, 103, 104, 122, 123, 124, 142, 143, 144], f"3 per subagent after the backstop: {picks}")
ok(got[100][1].startswith("late (search 101 > 100)"), got[100][1])

# without agent labels (not LDR's deep mode): skip 30, then every search (the run cap does the rest)
got, st = run([(None, i) for i in range(45)])
ok([p for p, _ in got] == [False] * 30 + [True] * 15, "no labels: first 30 skipped, then first come, first served")

# label variants count as the same agent
got, st = run([("lead", 0), ("sub1", 1), ("lead", 1000), ("sub2:topic a", 1001), ("sub2:topic b", 1002),
               ("sub2", 1003), ("sub2", 1004)])
ok([p for p, _ in got] == [False, False, True, True, True, True, False], f"sub2 / sub2:topic share a cap {got}")

# zero caps (the 'no paid source for this tag' path in paid_search) never pick but still move the phase
zero = {**sel, "per_sub": 0, "per_lead": 0, "skip_unknown": 10 ** 9}
st = R.new_state(0.0)
R.select_step(st, "sub1", zero, 1.0)
p_, why = R.select_step(st, "lead", zero, 2000.0)
ok(not p_ and st["follow_at"] == 2 and st["n"] == 2, "zero caps: no pick, the follow-up phase still starts")

T.finish(f"test_select: {n_ok} checks passed")
