"""post_daily.py - 10-26 14:25 (Karl: "Daily DeepSeek launcher: give it its own expert-profile file, separate from every
measurement copy, and let it learn (the engine updates it on exit). Before first use, seed it from the profile the final
config was measured with. Measurements keep using their own pinned copies."). The block that writes configs/DS41-daily.json
(ds41-after, started 14:14) runs the older write_daily: "expert_profile_from" = SHIPPED and a launcher smoke test on the
daily profile itself. Once its smoke test is done this: points the config at the pinned seed (expert_profile_seed + its
sha256; run-strata.sh seeds only a missing profile), sets the smoke test's learned profile aside and seeds the daily
profile from the seed, so first use starts there. Idempotent; prints what it did. No GPU."""
import hashlib
import json
import os
import shutil
import time

SC = "/home/USER/ai-speed-testing/strata-compare"
CFG = f"{SC}/configs/DS41-daily.json"
SEED = f"{SC}/configs/DS41-daily-profile.seed.bin"
SHA = "8db93e483b34b15dbf63a0826601f1db2107a8cfea73774e7d21d8559e0a9568"
MARK = f"{SC}/results/ds41/after/post_daily.done"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    if os.path.exists(MARK):
        print(f"already done: {open(MARK).read().strip()}")
        return 0
    if sha(SEED) != SHA:
        raise SystemExit(f"{SEED} does not match {SHA[:12]} - nothing changed")
    c = json.load(open(CFG))
    a = c["args"]
    prof = a[a.index("--expert-profile") + 1]
    c.pop("expert_profile_from", None)
    c["expert_profile_seed"], c["expert_profile_seed_sha256"] = SEED, SHA
    c["_comment"] = c.get("_comment", "") + (" 14:25 (Karl): its own profile " + prof + ", learning; seeded once from "
                                             + SEED + " (what the final config was measured with).")
    json.dump(c, open(CFG + ".tmp", "w"), indent=1)
    os.replace(CFG + ".tmp", CFG)
    if os.path.exists(prof):
        aside = f"{SC}/results/ds41/after/daily-profile.after-smoke-test.bin"
        shutil.move(prof, aside)
        print(f"the smoke test's profile set aside: {aside} ({sha(aside)[:12]})")
    os.makedirs(os.path.dirname(prof), exist_ok=True)
    shutil.copyfile(SEED, prof)
    note = f"{time.strftime('%F %T')}: {CFG} -> expert_profile_seed {SEED}; {prof} seeded ({sha(prof)[:12]})"
    open(MARK, "w").write(note + "\n")
    print(note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
