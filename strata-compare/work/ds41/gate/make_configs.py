#!/usr/bin/env python3
"""make_configs.py [--force] - 11-03 (Karl's DeepSeek gate: A = the daily config vs B = the 5080 alone vs C = the 5080
alone + Lucebox's small DSpark drafter on the 4060 Ti). Writes configs/DS41-gate-{A,B,B64,B62,C0,C1,C2}.json from
configs/DS41-daily.json, which is only read (gate.sh runs this before its gap and checks DS41-daily.json's sha256 at the end).

Every arm (what a test arm must change; nothing else):
  log           logs/ds41/engine-DS41-v024.log (the test log work/ds41/tune/tunearm.sh reads, LOGF there)
  --expert-profile  logs/ds41/gate/profile-arm.bin (gate.sh copies the gap's snapshot of logs/ds41/daily-profile.bin
                there before every arm: the engine writes its routing counts back into this file)
  STRATA_DS4_SLOT_DIR  logs/ds41/gate-slots/<arm> (never the daily logs/ds41/ds4-slots; gate.sh empties it before the arm)
A   = the daily config with only the three changes above (8/32 split, 4060 Ti first, --tp 2, --dspark auto = not loaded).
B   = A + the 5080 alone: CUDA_VISIBLE_DEVICES = the 5080's UUID only, --tp 1, no DS4_SPLIT, --vram-experts 1.0 (the
      default, explicit as in DS41-sweep-off-v10.json); --experts 6 and --prefill-chunk 8192 stay pinned (the study:
      auto would pick 5 experts - lossy - and chunk 4096 on one 16 GiB card); need_vram_mib 15400 (run-strata.sh checks
      the FIRST card; B's first card is the 5080).
C0  = A + the new pack (pack-ist-das-2.00bpw-lucebox-q2k: the daily pack's files with the converted Lucebox Q2K/Q4K
      drafter as file 5) and its tokenizer folder, DS4_SPLIT=0,40 (every trunk layer on the 5080; the drafter always sits
      on the first CUDA device = the 4060 Ti, as in daily's order), --vram-experts 1.0 (as B), --dspark off (loaded,
      never used: C's placement without drafting). --tp 2 as daily (the study: tp falls to 1 either way).
C1  = C0 with --dspark on --dspark-block 1;  C2 = C0 with --dspark on --dspark-block 2.  --dspark-conf 0.65 as daily.
"""
import copy
import hashlib
import json
import os
import sys

SC = "/home/USER/ai-speed-testing/strata-compare"
DAILY = f"{SC}/configs/DS41-daily.json"
M = f"{SC}/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF"
NEW_PACK = f"{M}/pack-ist-das-2.00bpw-lucebox-q2k"
GATE_LOG = f"{SC}/logs/ds41/engine-DS41-v024.log"
PROFILE = f"{SC}/logs/ds41/gate/profile-arm.bin"
SLOTS = f"{SC}/logs/ds41/gate-slots"
UUID_4060 = "GPU-UUID-RTX4060TI"   # (daily's first device; nvidia-smi index 1, 8 GB)
UUID_5080 = "GPU-UUID-RTX5080"   # (daily's second device; nvidia-smi index 0, 16 GB)


def set_arg(a, k, v=None):
    if k in a:
        if v is not None:
            a[a.index(k) + 1] = str(v)
    else:
        a += [k] if v is None else [k, str(v)]


def main():
    force = "--force" in sys.argv
    raw = open(DAILY, "rb").read()
    d = json.loads(raw)
    env0 = d["env"]["CUDA_VISIBLE_DEVICES"].split(",")
    if env0 != [UUID_4060, UUID_5080]:
        raise SystemExit(f"the daily config's CUDA_VISIBLE_DEVICES changed ({env0}) - check the UUIDs first")
    out = {}

    def base(arm, note):
        c = copy.deepcopy(d)
        c["log"] = GATE_LOG
        c["env"]["STRATA_DS4_SLOT_DIR"] = f"{SLOTS}/{arm}"
        set_arg(c["args"], "--expert-profile", PROFILE)
        c["_comment"] = (f"DS41-gate-{arm} (11-03, Karl's DeepSeek gate A / B / C, a test arm - never served; "
                         f"work/ds41/gate/make_configs.py): {note} Every gate arm differs from DS41-daily.json in: log = "
                         f"the test log tunearm.sh reads, --expert-profile = logs/ds41/gate/profile-arm.bin (a fresh copy "
                         f"of the gap's daily-profile snapshot before each arm), STRATA_DS4_SLOT_DIR = its own folder.")
        return c

    a = base("A", "A = the daily config as it is (4060 Ti first, DS4_SPLIT 8,32, --tp 2, no drafter: --dspark auto does "
                  "not load it).")
    out["A"] = a

    b = base("B", "B = the 5080 alone: CUDA_VISIBLE_DEVICES = the 5080 only, --tp 1, no DS4_SPLIT, --vram-experts 1.0; "
                  "--experts 6 and --prefill-chunk 8192 pinned (auto: 5 experts, lossy; chunk 4096); need_vram_mib 15400 "
                  "(run-strata.sh checks the first card).")
    set_arg(b["args"], "--tp", 1)
    set_arg(b["args"], "--vram-experts", "1.0")
    b["env"]["CUDA_VISIBLE_DEVICES"] = UUID_5080
    b["env"].pop("DS4_SPLIT", None)
    b["need_vram_mib"] = 15400
    out["B"] = b

    for n in (64, 62):   # 11-04 (Karl, after the second gate): B with a smaller RAM store, for the ~97K prompt's 14 GB floor
        bn = base(f"B{n}", f"B{n} = B with --ssd-cache {n} (the RAM store {68 - n} GB smaller than daily's 68): BL's L97 fell "
                           "to 13.75 GB with the daily services up (dip 9.8 GB, stopped by the soft stop); the estimate in "
                           "results/ds41/gate-1104-0725 / README: 64 GB keeps ~1.5-2 GB above 14 GB, 62 GB more.")
        bn["args"] = list(b["args"]); bn["env"] = dict(b["env"], STRATA_DS4_SLOT_DIR=f"{SLOTS}/B{n}")
        bn["need_vram_mib"] = b["need_vram_mib"]
        set_arg(bn["args"], "--ssd-cache", n)
        out[f"B{n}"] = bn

    for arm, mode, block, note in (("C0", "off", None, "C0 = C's placement, the drafter loaded but never used (--dspark off)."),
                                   ("C1", "on", 1, "C1 = C's placement, DSpark on, at most 1 draft a round."),
                                   ("C2", "on", 2, "C2 = C's placement, DSpark on, at most 2 drafts a round.")):
        c = base(arm, note + " C = the new pack (the converted Lucebox Q2K/Q4K drafter as file 5), DS4_SPLIT 0,40 (all "
                             "40 trunk layers on the 5080; the drafter on the first device, the 4060 Ti), --vram-experts 1.0.")
        set_arg(c["args"], "--pack", NEW_PACK)
        set_arg(c["args"], "--dspark", mode)
        if block is not None:
            set_arg(c["args"], "--dspark-block", block)
        set_arg(c["args"], "--vram-experts", "1.0")
        c["tokenizer"] = f"{NEW_PACK}/tokenizer"
        c["env"]["DS4_SPLIT"] = "0,40"
        out[arm] = c

    for arm, c in out.items():
        p = f"{SC}/configs/DS41-gate-{arm}.json"
        if os.path.exists(p) and not force:
            if json.load(open(p)) != c:
                raise SystemExit(f"{p} exists and differs (--force rewrites it)")
            print(f"{p}: unchanged")
            continue
        json.dump(c, open(p, "w"), indent=1)
        print(f"wrote {p}")
    print(f"DS41-daily.json (read only) sha256 {hashlib.sha256(raw).hexdigest()}")


if __name__ == "__main__":
    main()
