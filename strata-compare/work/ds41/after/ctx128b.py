#!/usr/bin/env python3
"""ctx128b.py - 10-27: the 128K check's second part. ctx128.py judged its long run by the arm record's lowest MemAvailable,
which A.arm leaves empty (None) - the monitor's own line has it ("monitor: lowest MemAvailable 18.9 GB" in summary.txt,
the same as longprompt.py's 0.5 s samples), so the run read as failed and nothing after it ran: no estimate, no slot cap
test, no identity check, no switch. The long run itself is fine (no guard, no soft stop, swap one logged burst, kernel log
clean) and is not repeated; the long-context items ran in that gap as planned (state "longctx").
Here, in its own gap after ds41-pairs2: the lowest from the monitor, ok recomputed by the same rule, then ctx128.py's own
estimate -> (if 16 long slots could break 14 GB) slot cap test + identity check -> switch with the launcher smoke test.
State: ctx128's (results/ds41/ctx128/state.json), log ctx128.log."""
import json
import re
import subprocess
import sys
import time

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/after")
import ctx128 as C  # noqa: E402  (sets A.STATE / A.LOG to the 128K check's, registers the slot-cap build)

A = C.A
SC = A.SC


def wait_pairs2():
    A.say("128K part 2: waiting for the repeat pairs (ds41-pairs2) to end")
    while subprocess.run(["systemctl", "--user", "is-active", "--quiet", "ds41-pairs2.service"]).returncode == 0:
        time.sleep(60)
    try:
        h = json.load(open(f"{SC}/results/ds41/hard/pairs2-state.json"))
    except (OSError, ValueError):
        h = {}
    if h.get("stopped") or not h.get("gap_closed"):
        why = h.get("stopped") or "it ended without closing its gap"
        A.say(f"128K part 2: the repeat pairs did not finish cleanly ({why}) - nothing runs")
        A.notify("128K part 2 not started", f"the repeat pairs: {why}", True)
        sys.exit(1)
    A.say(f"128K part 2: the repeat pairs ended (gap closed {h['gap_closed']})")


def fix_long(st):
    L = st["long"]
    if L.get("lowest_source"):
        return
    m = re.search(r"monitor: lowest MemAvailable ([\d.]+) GB", open(f"{L['dir']}/summary.txt", errors="replace").read())
    low = float(m.group(1)) if m else None
    L.update(lowest_mem=low, lowest_source="summary.txt monitor line (the arm record's field was empty)",
             ok=bool(L.get("lp")) and not L.get("guard") and not L.get("softstop") and (low or 0) >= 14.0,
             first_verdict=st.pop("switch", None))
    st.pop("estimate", None)
    A.save(st)
    A.say(f"128K part 2: long run re-judged - lowest MemAvailable {low} GB (monitor), ok {L['ok']}")


def main():
    st = A.load()
    if st.get("stopped"):
        A.say(f"not resuming: stopped earlier ({st['stopped']})")
        return 1
    if not st.get("part2_gap"):
        wait_pairs2()
        fix_long(st)
        st.pop("gap_open", None)
        st.pop("gap_closed", None)
        st["part2_gap"] = time.strftime("%F %T")
        A.save(st)
    A.open_gap(st)
    est = C.estimate(st)
    if est.get("breaks_14") and st["long"].get("ok") and not str(st.get("build")).startswith("FAILED"):
        C.ramtest(st)
        if (st.get("ramtest") or {}).get("ok") and est.get("cap_gib") and est["cap_gib"] >= 0.3:
            C.idcheck(st, est["cap_gib"])
    C.switch(st, est)
    rc = A.close_gap(st)
    C.summary(st)
    A.notify("128K check part 2 done", f"{st.get('switch')}; 8080 {'back on P021m' if rc == 0 else 'NOT restored'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
