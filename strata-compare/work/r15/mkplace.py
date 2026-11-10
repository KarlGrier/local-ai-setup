#!/usr/bin/env python3
"""mkplace.py RUN NAME — round 15 step 3: the placements of bringup/placements.py as configs, from the runbook run's
candidate (bringup/out/RUN/configs/cand.json: placement B, every switch on, your chat cache of 2 GiB):
  configs/r15-NAME-{A,B,C,D,E}.json (+ .shared-settings.json)
  A both GPUs: helper cache (90 % of the planner's helper maximum) + --mmap-experts, reserve 713
  B the 5080 + --resident-budget-gib (the candidate as it is; reserve +100)
  C layer split over both cards (--layer-split auto) + B's RAM budget (#642 / #848)
  D the 5080 + --peer-device 1 + the candidate's budget
  E the 5080 + --resident-experts (setup's low-RAM mode; headroom 8 GiB)
Every config keeps the candidate's flags otherwise; each writes its own engine log."""
import json
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
run, name = sys.argv[1], sys.argv[2]
R = WS / "bringup/out" / run
cand = json.loads((R / "configs/cand.json").read_text())
plan = json.loads((WS / f"results/r15/plan-{sys.argv[3]}.json").read_text()) if len(sys.argv) > 3 else None
both = "GPU-UUID-RTX5080,GPU-UUID-RTX4060TI"
one = "GPU-UUID-RTX5080"
helper_max = None
if plan:
    helper_max = next(p["card2_slots"] for p in plan["placements"] if p["key"] == "A")


def make(key, edit, comment):
    c = json.loads(json.dumps(cand))
    a = c["args"]

    def setarg(f, v):
        if f in a:
            a[a.index(f) + 1] = v
        else:
            a.extend([f, v])

    def drop(f, has_value=True):
        if f in a:
            i = a.index(f)
            del a[i:i + (2 if has_value else 1)]

    edit(c, a, setarg, drop)
    c["env"]["STRATA_DECODE_TIMING"] = "1"   # the serve path's per-request window split (host timers), every placement alike
    c["log"] = str(WS / f"logs/engine-r15-{name}-{key}.log")
    c["_comment"] = f"Round 15 step 3, {name}, placement {key}: {comment}"
    out = WS / f"configs/r15-{name}-{key}.json"
    out.write_text(json.dumps(c, indent=1) + "\n")
    sh = R / "configs/cand.shared-settings.json"
    if sh.exists():
        (WS / f"configs/r15-{name}-{key}.shared-settings.json").write_text(sh.read_text())
    print(out, " ".join(x for x in a if x.startswith("--") and x in (
        "--resident-budget-gib", "--mmap-experts", "--expert-cache-device1", "--layer-split", "--peer-device",
        "--resident-experts", "--vram-reserve-mib")), c["env"]["CUDA_VISIBLE_DEVICES"][:12])


def ed_a(c, a, setarg, drop):
    c["env"]["CUDA_VISIBLE_DEVICES"] = both
    drop("--resident-budget-gib")
    a.append("--mmap-experts")
    setarg("--vram-reserve-mib", "713")
    setarg("--expert-cache-device1", str(int((helper_max or 1500) * 0.9) // 100 * 100))


def ed_b(c, a, setarg, drop):
    c["env"]["CUDA_VISIBLE_DEVICES"] = one


def ed_c(c, a, setarg, drop):
    # the layer split with B's RAM budget (#642 / #848: v0.1.40.x keeps a budget on a split); --resident-experts would
    # size the copy itself with a 4 GiB headroom - under your 6 GB floor
    c["env"]["CUDA_VISIBLE_DEVICES"] = both
    setarg("--layer-split", "auto")


def ed_d(c, a, setarg, drop):
    c["env"]["CUDA_VISIBLE_DEVICES"] = both
    setarg("--peer-device", "1")


def ed_e(c, a, setarg, drop):
    c["env"]["CUDA_VISIBLE_DEVICES"] = one
    c["env"]["STRATA_RESIDENT_HEADROOM_GIB"] = "8"   # above your 6 GB floor (default 4)
    drop("--resident-budget-gib")
    a.append("--resident-experts")


make("A", ed_a, "both GPUs, the helper cache + --mmap-experts (no RAM budget beside a helper cache)")
make("B", ed_b, "the 5080 + the RAM budget (the runbook's candidate)")
make("C", ed_c, "layer split over the 4060 Ti and the 5080 (auto) + the RAM budget (#642 / #848)")
make("D", ed_d, "the 5080 + --peer-device 1 (the 4060 Ti as an adaptive tier) + the RAM budget")
make("E", ed_e, "the 5080 + --resident-experts (setup's low-RAM mode)")
