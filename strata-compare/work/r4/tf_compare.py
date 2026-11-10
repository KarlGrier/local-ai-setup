"""tf_compare.py — round 4: teacher-forced NLL tables. For each pair (A, B) and text: perplexities, paired mean
difference B − A ± standard error (nats/token), tokens that changed, and "flips" = tokens where one side is near
certain (NLL < 0.5) and the other is far off (NLL > 5) — the far-context copy tokens round 3 saw flipping.
    tf_compare.py 'title|A|B|text,text' ...     (results/tf-<label>-<text>.nll)"""
import math, statistics, sys
WS = "/home/USER/ai-speed-testing/strata-compare"
def nll(L, T):
    try:
        return [float(l.split()[-1]) for l in open(f"{WS}/results/tf-{L}-{T}.nll") if l.strip()]
    except FileNotFoundError:
        return None
print("| comparison | text | ppl A | ppl B | mean NLL A → B | B − A (nats/token) | tokens changed | flips A-good/B-bad · A-bad/B-good |")
print("|---|---|---|---|---|---|---|---|")
for spec in sys.argv[1:]:
    title, A, B, texts = spec.split("|")
    for T in texts.split(","):
        a, b = nll(A, T), nll(B, T)
        if not a or not b:
            print(f"| {title} | {T} | – | – | – | missing ({A if not a else B}) | – | – |"); continue
        n = min(len(a), len(b)); d = [b[i] - a[i] for i in range(n)]
        se = statistics.stdev(d) / math.sqrt(n) if n > 1 else 0
        ch = sum(1 for x in d if abs(x) > 1e-6)
        f1 = sum(1 for i in range(n) if a[i] < 0.5 and b[i] > 5); f2 = sum(1 for i in range(n) if b[i] < 0.5 and a[i] > 5)
        ma, mb = statistics.mean(a[:n]), statistics.mean(b[:n])
        print(f"| {title} | {T} | {math.exp(ma):.4f} | {math.exp(mb):.4f} | {ma:.3f} → {mb:.3f} | {statistics.mean(d):+.4f} ± {se:.4f} | {ch} of {n} | {f1} · {f2} |")
