"""Tuning-screen summary: per config, decode tok/s of the three 1K prompts (median [min-max]), 32K decode, 32K TTFT
and prompt tok/s, correctness decode median, mean draft acceptance, and first-divergence vs a reference screen."""
import json, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RESULTS, read_jsonl, load_tokenizer
from analyze import outputs, raw_text
labels = sys.argv[1].split(",")
ref = sys.argv[2] if len(sys.argv) > 2 else None
runs = read_jsonl(RESULTS / "runs.jsonl")
tok = load_tokenizer()
def med(v): return f"{statistics.median(v):.1f} [{min(v):.1f}–{max(v):.1f}]" if v else "–"
print("| config | 1K decode tok/s (3 prompts) | 32K decode tok/s | 32K TTFT s (PP tok/s) | correctness decode tok/s (5) | draft acceptance | tokens/round | same tokens as " + (ref or "-") + " (first divergence) |")
print("|---|---|---|---|---|---|---|---|")
for L in labels:
    rs = [r for r in runs if r["config"] == L and not r.get("error")]
    s1 = [r["decode_tps"] for r in rs if r["scenario"] == "speed" and r["item"] == "1k"]
    s32 = [r for r in rs if r["scenario"] == "speed" and r["item"] == "32k"]
    cr = [r["decode_tps"] for r in rs if r["scenario"] == "correctness" and r.get("decode_tps")]
    eng = [r["engine"] for r in rs if r.get("engine") and r["scenario"] in ("speed", "correctness")]
    acc = sum(e["drafts_accepted"] for e in eng) / max(1, sum(e["drafts_offered"] for e in eng))
    gen = sum(e["generated"] for e in eng)
    # rounds = generated - accepted (each round emits accepted + 1)
    rounds = sum(e["generated"] - e["drafts_accepted"] for e in eng)
    div = ""
    if ref:
        a, b = outputs(ref, "correctness"), outputs(L, "correctness")
        parts = []
        for it in sorted(a):
            if it in b:
                x, y = tok.encode(raw_text(a[it][-1])), tok.encode(raw_text(b[it][-1]))
                n = next((i for i, (p, q) in enumerate(zip(x, y)) if p != q), None)
                parts.append("=" if n is None and len(x) == len(y) else str(n if n is not None else min(len(x), len(y))))
        div = f"{sum(p == '=' for p in parts)}/5 ({' '.join(parts)})"
    t32 = s32[-1] if s32 else None
    print(f"| {L} | {med(s1)} | {t32['decode_tps']:.1f} | {t32['ttft_s']:.1f} ({t32['prompt_tps_client']:.0f}) | {med(cr)} | "
          f"{acc:.3f} | {gen / max(1, rounds):.2f} | {div} |" if t32 else f"| {L} | {med(s1)} | – | – | {med(cr)} | {acc:.3f} | | {div} |")
