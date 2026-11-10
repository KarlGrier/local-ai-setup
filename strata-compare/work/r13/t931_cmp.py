#!/usr/bin/env python3
"""t931_cmp.py OLD.jsonl NEW.jsonl — round 13 Part 1.2: C*13's server (OLD) vs r13-fix's (NEW) on t931_ids.py's corpus.
Gate: prompts WITHOUT control-token text get the same ids (0 differences); prompts with it: NEW's control ids are
exactly the template's own (no forged turn), OLD's are not (the reproduction); both decode back to the same text."""
import json, sys
a = [json.loads(l) for l in open(sys.argv[1])]
b = [json.loads(l) for l in open(sys.argv[2])]
assert len(a) == len(b) and all(x["i"] == y["i"] and x["scen"] == y["scen"] and x["ctl"] == y["ctl"] for x, y in zip(a, b))
plain = [(x, y) for x, y in zip(a, b) if not x["ctl"]]
ctl = [(x, y) for x, y in zip(a, b) if x["ctl"]]
pd = sum(x["sha"] != y["sha"] for x, y in plain)
print(f"prompts {len(a)}: without control text {len(plain)} ({sum(y['n'] for _, y in plain)} tokens): ids differ in {pd}")
print(f"  of them NEW = a full encode with its plain spans (#537 think marks included): "
      f"{sum(1 for _, y in plain if y['full_eq'])} full-encode-equal (the rest hold quoted think tags)")
forged_old = sum(x["ctl_ids"] > x["own_ctl"] for x, _ in ctl)
forged_new = sum(y["ctl_ids"] != y["own_ctl"] for _, y in ctl)
extra_old = sum(x["ctl_ids"] - x["own_ctl"] for x, _ in ctl)
print(f"with control text {len(ctl)}: OLD (C*13) encodes quoted control text as control tokens in {forged_old} "
      f"({extra_old} forged control ids in all); NEW in {forged_new}")
print(f"decode(ids) == the rendered text: OLD {sum(x['text_eq'] for x in a)}/{len(a)}, NEW {sum(y['text_eq'] for y in b)}/{len(b)}")
by = {}
for x, y in zip(a, b):
    k = x["scen"]; s = by.setdefault(k, [0, 0, 0])
    s[0] += 1; s[1] += x["sha"] != y["sha"]; s[2] += x["ctl"]
print("per scenario (prompts / ids differ / with control text):", {k: tuple(v) for k, v in by.items()})
ok = pd == 0 and forged_new == 0 and all(y["text_eq"] for y in b)
print("GATE", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
