#!/usr/bin/env python3
"""manifest.py - the exact deletion list Karl approved 10-27 (no model files except the DSpark drafter): old packs,
round scratch, old build trees, old engine copies, caches. Writes manifest.json (path, GB, group, when) and
results/DELETIONS-APPROVED-1027.md. Deletes nothing."""
import glob, json, os, subprocess
S = "/home/USER/ai-speed-testing/strata-compare"
H = os.path.expanduser("~")
OUT = f"{S}/work/cleanup-1027"
def size(p):
    return int(subprocess.run(["du", "-sb", p], capture_output=True, text=True).stdout.split()[0]) / 1e9
rows = []
def add(p, group, when="now"):
    if os.path.lexists(p):
        rows.append({"path": p, "gb": round(size(p), 3), "group": group, "when": when})
# 1. old packs: every bringup/out pack folder except the served r20a, plus bringup/out/tmp (logs/results/accept/synth/patchtest stay)
for p in sorted(glob.glob(f"{S}/bringup/out/*")):
    n = os.path.basename(p)
    if n in ("r20a", "logs", "results", "accept", "synth", "patchtest"):
        continue
    add(p, "old packs")
# 2. round scratch: subfolders of tmp/rN (top-level files stay: kwatch's pid / KERNEL_ERROR files in r19, pick lists);
#    tmp/r5 stays whole (searxng-chat's cache and temp, open now); tmp/fp4local whole
for d in sorted(glob.glob(f"{S}/tmp/r[0-9]*")):
    if os.path.basename(d) == "r5" or not os.path.isdir(d):
        continue
    for p in sorted(glob.glob(f"{d}/*")):
        if os.path.isdir(p) and not os.path.islink(p):
            add(p, "round scratch")
add(f"{S}/tmp/fp4local", "round scratch")
# 3. old build trees (209): every strata-* tree except the kept ones
keep = {"strata", "strata-cstar18", "strata-r21think", "strata-r22p021m", "strata-r22p021n", "strata-v0115", "strata-r22p021",
        "strata-v026", "strata-v024", "strata-v026p343", "strata-v026p343-slotram", "strata-v026test", "strata-r22p022",
        "strata-r22p022n", "strata-r22port", "strata-v026fix", "strata-v026iqq8k", "strata-v026p343-iqq8k", "strata-v021stock"}
for p in sorted(glob.glob(f"{S}/strata-*")):
    if os.path.isdir(p) and os.path.basename(p) not in keep:
        add(p, "old build trees")
# 4. old engine copies: every engine-* except the served / rollback / DeepSeek ones
keep_e = {"engine-r22p021", "engine-r22p021m", "engine-r22p021n", "engine-cstar18", "engine-v026p343-ds41", "engine-v026p343-slotram-ds41"}
for p in sorted(glob.glob(f"{S}/engine-*")):
    n = os.path.basename(p)
    if n in keep_e or "ds41" in n or "v026" in n or "v024" in n:
        continue
    add(p, "old engine copies")
# 5. caches
add(f"{H}/.cache/uv", "caches"); add(f"{H}/.cache/pip", "caches"); add(f"{H}/.cache/usability-downloads", "caches")
for p in sorted(glob.glob(f"{H}/ai/deep-research/tmp/*")):
    n = os.path.basename(p)
    if n.startswith("backup-2026-10-27") or n == "code-tool":
        continue
    add(p, "caches", "after the LDR rerun")
add(f"{H}/ai/deep-research/cache", "caches", "after the LDR rerun")
# 6. the DSpark drafter
add(f"{S}/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf", "DSpark drafter")
json.dump(rows, open(f"{OUT}/manifest.json", "w"), indent=1)
tot = {}
for r in rows:
    tot.setdefault(r["group"], [0, 0.0]); tot[r["group"]][0] += 1; tot[r["group"]][1] += r["gb"]
L = ["# Deletions approved by Karl 10-27 - the exact list", "",
     "No model files except the DSpark drafter (NVFP4, the splices, the PLE files, Q4_K_XL, GLM, DeepSeek all stay).",
     "Kept on purpose: bringup/out/r20a (served pack) and its logs/results/accept/synth/patchtest; tmp/r5 (searxng-chat has its",
     "cache open there); the top-level files of tmp/rN (kwatch's pid and KERNEL_ERROR files in tmp/r19, pick lists); the",
     "served / rollback / port / DeepSeek / grading trees and engines; today's LDR backups and the live code-tool scratch.",
     "Saved first: the uncommitted diffs of strata-r13t, strata-r4-web, strata-r6, strata-v0111 and v0111's untracked files",
     "(work/cleanup-1027/saved/). Afterwards: `git -C strata worktree prune` (196 of the trees are worktrees of the main checkout).",
     "Sizes in decimal GB.", "", "| group | entries | GB | when |", "|---|---|---|---|"]
for g, (n, gb) in tot.items():
    when = sorted({r["when"] for r in rows if r["group"] == g})
    L.append(f"| {g} | {n} | {gb:.1f} | {', '.join(when)} |")
L.append(f"| **total** | {len(rows)} | **{sum(r['gb'] for r in rows):.1f}** | |")
L += ["", "## Every entry", "", "| GB | path | group | when |", "|---|---|---|---|"]
for r in rows:
    L.append(f"| {r['gb']:.3f} | {r['path'].replace(H, '~')} | {r['group']} | {r['when']} |")
open(f"{S}/results/DELETIONS-APPROVED-1027.md", "w").write("\n".join(L) + "\n")
for g, (n, gb) in tot.items(): print(f"{g:18s} {n:4d} entries {gb:7.1f} GB")
print(f"total {len(rows)} entries {sum(r['gb'] for r in rows):.1f} GB")
