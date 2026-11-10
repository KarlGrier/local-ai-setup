#!/usr/bin/env python3
"""ctx128c.py - 10-27 02:15: the 128K check's identity step again, as it should have run. ctx128b.py's id-old / id-new ran
the daily config with the expert cache on, where experts move into VRAM on their own timing: the two texts split ~30
tokens into the first request (292 vs 321 tokens), too early for anything the slot cap touches (two short chats never
reach it). Fresh engines repeat their first requests exactly only with placement frozen (10-26 repeat pairs; 10-27 the
decode path's carry-over is identical frozen). Here, in one gap:
  id-old-frozen / id-new-frozen  the shipped engine and the slot-cap build (cap as estimated), --no-expert-cache, fresh
                                 engines, the same two seeded requests -> must be identical (both requests)
  id-old-again                   the shipped engine with the cache on, as id-old: a control - if it differs from id-old,
                                 the cache-on check could not pass even for one build
Then ctx128.py's switch() with the frozen result as the identity check (the cache-on one kept as idcheck_cache_on).
State ctx128's, log ctx128.log."""
import json
import os
import shutil
import sys
import time

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/after")
import ctx128 as C  # noqa: E402

A = C.A


def idpair(st, key, eng, extra, desc):
    sd = f"{C.R}/slots-{key}"
    shutil.rmtree(sd, ignore_errors=True)
    r = A.arm(st, key, C.daily_mods(sd, engine=eng, **extra), f"128K check part 3: two seeded requests on a fresh {eng} engine ({desc})",
              f"{A.PY} {A.A}/idcheck_client.py $URL $OUT", server_env="STRATA_DS4_AUTO_PIN=1", client_timeout=1800)
    p = f"{r['dir']}/idcheck.json" if r.get("dir") else ""
    return json.load(open(p)) if p and os.path.exists(p) else None


def texts(x):
    return [y["text"] for y in x] if x else None


def main():
    st = A.load()
    if st.get("stopped"):
        A.say(f"not resuming: stopped earlier ({st['stopped']})")
        return 1
    est = st["estimate"]
    cap = est["cap_gib"]
    if not st.get("part3_gap"):
        st.pop("gap_open", None)
        st.pop("gap_closed", None)
        st["part3_gap"] = time.strftime("%F %T")
        A.save(st)
    A.open_gap(st)
    fz = {"--no-expert-cache": None}
    old_f = idpair(st, "id-old-frozen", A.FINAL_ENG, fz, "placement frozen")
    new_f = idpair(st, "id-new-frozen", C.NEW, dict(fz, STRATA_DS4_SLOT_RAM_GB=str(cap)), f"placement frozen, slot RAM cap {cap} GiB")
    ctl = idpair(st, "id-old-again", A.FINAL_ENG, {}, "expert cache on, as id-old: the control")
    old_on = json.load(open(f"{st['steps']['id-old']['dir']}/idcheck.json"))
    if "idcheck_cache_on" not in st:
        st["idcheck_cache_on"] = st.pop("idcheck", None)
    to, tn = texts(old_f), texts(new_f)
    st["idcheck"] = {"identical": bool(to) and to == tn, "mode": "placement frozen (--no-expert-cache), fresh engines, seed 4242",
                     "per_request": [a == b for a, b in zip(to or [], tn or [])],
                     "tokens": {"old": [x["completion_tokens"] for x in old_f or []], "new": [x["completion_tokens"] for x in new_f or []]},
                     "control_same_build_cache_on_identical": bool(ctl) and texts(ctl) == texts(old_on),
                     "control_tokens": {"id-old": [x["completion_tokens"] for x in old_on], "id-old-again": [x["completion_tokens"] for x in ctl or []]}}
    A.save(st)
    A.say(f"identity check, placement frozen: {json.dumps(st['idcheck'])}")
    if "switch_part2" not in st:
        st["switch_part2"] = st.pop("switch", None)
        A.save(st)
    C.switch(st, est)
    rc = A.close_gap(st)
    C.summary(st)
    A.notify("128K check part 3 done", f"{st.get('switch')}; 8080 {'back on P021m' if rc == 0 else 'NOT restored'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
