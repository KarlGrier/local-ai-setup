#!/usr/bin/env python3
"""compare_packs.py DAILY_PACK NEW_PACK DRAFTER_REL - 11-03 (Karl's gate, arm C): the new pack must be the daily pack
with only the drafter swapped. CPU only, reads the two index folders (a DeepSeek pack is an index beside the model's
files: ds4.txt, tensors.txt, engram.bin, tokenizer/, expert-profile.bin):
  - ds4.txt identical (the drafter's geometry keys come from the shards / the drafter file's REF metadata: unchanged);
  - engram.bin and every tokenizer/ file byte-identical;
  - tensors.txt: files 0-4 the same names, file 5 = DRAFTER_REL (relative to model_dir); every trunk entry (not mtp.*)
    identical; the same set of mtp.* names (types, offsets and sizes differ: that is the new drafter);
  - the mtp.* entries' types and bytes summarized for both packs.
Exit 0 = as expected, 1 = not.
"""
import collections
import filecmp
import os
import sys


def tensors(p):
    files, ent = {}, {}
    for line in open(f"{p}/tensors.txt"):
        f = line.rstrip("\n").split(" ")
        if f[0] == "file":
            files[int(f[1])] = f[2]
        elif f[0] == "t":
            ent[f[1]] = (f[2], int(f[3]), int(f[4]), int(f[5]), " ".join(f[6:]))
    return files, ent


def main():
    a, b, drel = sys.argv[1:4]
    bad = []
    if open(f"{a}/ds4.txt").read() != open(f"{b}/ds4.txt").read():
        bad.append("ds4.txt differs")
    if not filecmp.cmp(f"{a}/engram.bin", f"{b}/engram.bin", shallow=False):
        bad.append("engram.bin differs")
    ta, tb = sorted(os.listdir(f"{a}/tokenizer")), sorted(os.listdir(f"{b}/tokenizer"))
    if ta != tb:
        bad.append(f"tokenizer files differ: {ta} vs {tb}")
    else:
        for n in ta:
            if not filecmp.cmp(f"{a}/tokenizer/{n}", f"{b}/tokenizer/{n}", shallow=False):
                bad.append(f"tokenizer/{n} differs")
    fa, ea = tensors(a)
    fb, eb = tensors(b)
    for i in range(5):
        if fa.get(i) != fb.get(i):
            bad.append(f"file {i}: {fa.get(i)} vs {fb.get(i)}")
    if fb.get(5) != drel:
        bad.append(f"file 5 is {fb.get(5)}, want {drel}")
    if len(fb) != len(fa):
        bad.append(f"{len(fa)} files in the daily pack, {len(fb)} in the new one")
    trunk_a = {k: v for k, v in ea.items() if not k.startswith("mtp.")}
    trunk_b = {k: v for k, v in eb.items() if not k.startswith("mtp.")}
    if trunk_a != trunk_b:
        diff = [k for k in set(trunk_a) | set(trunk_b) if trunk_a.get(k) != trunk_b.get(k)]
        bad.append(f"{len(diff)} trunk entries differ, e.g. {sorted(diff)[:5]}")
    ma = {k: v for k, v in ea.items() if k.startswith("mtp.")}
    mb = {k: v for k, v in eb.items() if k.startswith("mtp.")}
    if set(ma) != set(mb):
        bad.append(f"mtp.* names differ: only daily {sorted(set(ma) - set(mb))[:5]}, only new {sorted(set(mb) - set(ma))[:5]}")
    if any(v[1] != 5 for v in mb.values()):
        bad.append("an mtp.* entry of the new pack is not in file 5")
    for lab, m in (("daily", ma), ("new", mb)):
        by = collections.defaultdict(lambda: [0, 0])
        for v in m.values():
            by[v[0]][0] += 1
            by[v[0]][1] += v[3]
        exp = sum(v[3] for k, v in m.items() if ".ffn.experts." in k)
        print(f"  {lab}: {len(m)} mtp.* entries, {sum(v[3] for v in m.values()) / 1e9:.3f} GB "
              f"(routed experts {exp / 1e9:.3f} GB); " + ", ".join(f"{t} {n} / {s / 1e9:.3f} GB" for t, (n, s) in sorted(by.items())))
    print(f"  trunk entries {len(trunk_b)} identical: {trunk_a == trunk_b}; files {fb}")
    for x in bad:
        print("  BAD " + x)
    print("compare_packs: " + ("OK (only the drafter differs)" if not bad else f"NOT OK ({len(bad)})"))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
