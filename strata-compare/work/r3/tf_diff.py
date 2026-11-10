"""paired teacher-forced NLL difference B − A per text: mean ± standard error over tokens, plus each perplexity"""
import math, statistics, sys
A, B = sys.argv[1], sys.argv[2]
def nll(L, T):
    v = []
    for line in open(f"/home/USER/ai-speed-testing/strata-compare/results/tf-{L}-{T}.nll"):
        p = line.split()
        if p: v.append(float(p[-1]))
    return v
for T in (sys.argv[3].split(",") if len(sys.argv) > 3 else ("math", "corpus")):
    a, b = nll(A, T), nll(B, T)
    n = min(len(a), len(b)); d = [b[i] - a[i] for i in range(n)]
    print(f"{T}: {n} tokens, ppl {A} {math.exp(statistics.mean(a[:n])):.4f}, {B} {math.exp(statistics.mean(b[:n])):.4f}; "
          f"paired diff {statistics.mean(d):+.4f} ± {statistics.stdev(d) / math.sqrt(n):.4f} nats/token")
