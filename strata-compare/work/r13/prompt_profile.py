#!/usr/bin/env python3
"""prompt_profile.py — round 10 C (your addition): prompt times at 4K / 8K / 32K / 120K, ours vs the fork with and
without its second GPU (CLI, cold page cache, logs/r13/prof/Cpp-*), and the raw prompt-stage profiles (ours:
STRATA_PREFILL_TIMING=1; the fork: --prefill-profile) for the side-by-side table in the report."""
import re
from pathlib import Path
P = Path("/home/USER/ai-speed-testing/strata-compare/logs/r13/prof")
PF = re.compile(r"prefill\s+(\d+) tokens in ([\d.]+) ms\s+->\s+([\d.]+) tok/s\s+\(time to first token ([\d.]+) ms\)")
def pf(name):
    f = P / f"{name}.out"
    if not f.exists(): return None
    m = PF.search(f.read_text(errors="replace"))
    return (int(m[1]), float(m[2]), float(m[4])) if m else None
print("| prompt | ours (base) ms | fork + 4060 Ti ms | fork, 5080 alone ms | fork+GPU2 vs ours | fork alone vs ours |")
print("|---|---|---|---|---|---|")
for s in ("pp4k", "pp8k", "pp32k", "pp120k"):
    row = []
    for arm in ("v36", "fk2", "fk1"):
        v = [x for x in (pf(f"Cpp-{arm}-{s}"), pf(f"Cpp-{arm}-{s}-b")) if x]
        row.append((v[0][0], sum(x[2] for x in v) / len(v), [x[2] for x in v]) if v else None)
    cells = [" / ".join(f"{t:.0f}" for t in r[2]) + f" → **{r[1]:.0f}**" if r else "–" for r in row]
    rel = [f"{100 * (r[1] / row[0][1] - 1):+.1f} %" if r and row[0] else "–" for r in row[1:]]
    n = row[0][0] if row[0] else "?"
    print(f"| {s} ({n} tokens) | " + " | ".join(cells) + " | " + " | ".join(rel) + " |")
for arm in ("v36", "fk2", "fk1"):
    for s in ("pp4k", "pp8k", "pp32k", "pp120k"):
        for ext in (".out", ".err"):
            f = P / f"Cpp-{arm}-{s}-prof{ext}"
            if f.exists():
                lines = [l for l in f.read_text(errors="replace").split("\n") if re.search(r"prefill|prompt (path|chunk)|section|chunk|ms per|gemm|attn|experts|ple|gdn|qsa", l, re.I)]
                if lines:
                    print(f"\n#### {arm} {s} ({f.name})\n```\n" + "\n".join(lines[:60]) + "\n```")
