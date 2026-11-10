"""tf_table.py — round 3 accuracy table: paired teacher-forced NLL differences (B − A, nats/token, mean ± se over the
1,536 scored tokens) for the pairs below, and each run's perplexity. Missing files are skipped."""
import math, statistics
from pathlib import Path
R = Path("/home/USER/ai-speed-testing/strata-compare/results")
def nll(L, T):
    p = R / f"tf-{L}-{T}.nll"
    if not p.exists(): return None
    return [float(l.split()[-1]) for l in open(p) if l.split()]
pairs = [
    ("determinism: v0.1.12 base run 1 vs run 2", "R3tf-base1", "R3tf-base2", ["math", "corpus", "long16k"]),
    ("determinism: C*3 run a vs run b", "R3tf-c3a", "R3tf-c3b", ["math", "corpus", "long16k"]),
    ("**C*3 vs v0.1.12 base**", "R3tf-base1", "R3tf-c3a", ["math", "corpus", "long16k", "long24k"]),
    ("C*3 with the old per-token PLE vs base (isolates patch 0003)", "R3tf-base1", "R3tf-c3pt", ["long16k", "long24k"]),
    ("sensitivity: base, --prefill 4096 vs 8192 (a rounding change accepted in round 2)", "R3tf-base1", "R3tf-basepf", ["long16k", "long24k"]),
    ("sensitivity: C*3, --prefill 4096 vs 8192", "R3tf-c3a", "R3tf-c3pf", ["long16k", "long24k"]),
]
alias = {("R3tf-base1", "long24k"): "R3tf-base1b", ("R3tf-c3a", "long24k"): "R3tf-c3ab"}
print("| comparison | text | ppl A | ppl B | B − A (nats/token) | tokens that changed |")
print("|---|---|---|---|---|---|")
for name, A, B, texts in pairs:
    for T in texts:
        a = nll(alias.get((A, T), A), T); b = nll(alias.get((B, T), B), T)
        if a is None or b is None: continue
        n = min(len(a), len(b)); d = [b[i] - a[i] for i in range(n)]
        se = statistics.stdev(d) / math.sqrt(n) if any(d) else 0.0
        ch = sum(1 for x in d if abs(x) > 1e-6)
        print(f"| {name} | {T} | {math.exp(statistics.mean(a[:n])):.4f} | {math.exp(statistics.mean(b[:n])):.4f} | "
              f"{statistics.mean(d):+.4f} ± {se:.4f} | {ch} of {n} |")
