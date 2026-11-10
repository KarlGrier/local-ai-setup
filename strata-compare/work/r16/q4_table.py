#!/usr/bin/env python3
"""q4_table.py — round 16 Q4 check: UD-Q4_K_XL (label r16-q4u, one session) next to IQ3_S C*16 (step 2's arms), computed as
ab_table.py / ldr_table.py compute them: decode screen = the engine's accepted tokens / decode time over long reasoning math
+ code, correctness (answers > 100 tokens) and the 32K r1 answer; LDR screen = every ldr-* request > 100 tokens; TTFT 32K /
120K = the client's time to first token of the speed prompts; needle 120K; ms per verify round, tokens per round."""
import json, statistics as st
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
runs = [json.loads(l) for l in open(WS / "results/runs.jsonl")]
runs = [r for r in runs if r.get("started", "") >= "2026-10-08T17:07" and not r.get("error")]
def rows(labels, pred): return [r for r in runs if r["config"] in labels and pred(r)]
def agg(rs):
    e = [r["engine"] for r in rs if r.get("engine") and (r.get("completion_tokens") or 0) > 100]
    g = sum(x["generated"] for x in e); ms = sum(x["decode_ms"] for x in e)
    rounds = sum(x["generated"] - x["drafts_accepted"] for x in e); off = sum(x["drafts_offered"] for x in e)
    return g / (ms / 1000), ms / max(1, rounds), g / max(1, rounds), sum(x["drafts_accepted"] for x in e) / off
dec = lambda r: r["scenario"] in ("longreason", "correctness") or (r["scenario"] == "speed" and r["item"] == "32k")
ldr = lambda r: str(r["scenario"]).startswith("ldr-")
def ttft(labels, size): v = [r["ttft_s"] for r in rows(labels, lambda r: r["scenario"] == "speed" and r["item"] == size)]; return (st.mean(v), len(v)) if v else (None, 0)
Q = ["r16-q4u"]
I_D, I_L = ["r16-s2-D-c16-a", "r16-s2-D-c16-b"], ["r16-s2-L-c16-a", "r16-s2-L-c16-b"]
I_T = ["r16-s2-F-c16-a", "r16-s2-F-c16-b", "r16-s2-T-c16-a", "r16-s2-T-c16-b", "r16-s2-D-c16-a", "r16-s2-D-c16-b"]
qd, qdl, id_, il = agg(rows(Q, dec)), agg(rows(Q, ldr)), agg(rows(I_D, dec)), agg(rows(I_L, ldr))
print("| | IQ3_S, C\\*16 as served (both GPUs; step 2, 2 arms) | UD-Q4_K_XL (the 5080 + 66 GiB RAM, unbuffered; one session) | Q4 vs IQ3_S |")
print("|---|---|---|---|")
for name, a, b in (("decode screen, tok/s", id_[0], qd[0]), ("LDR screen, tok/s", il[0], qdl[0])):
    print(f"| {name} | {a:.1f} | **{b:.1f}** | {100 * (b / a - 1):+.0f} % |")
print(f"| ms per verify round (decode / LDR) | {id_[1]:.2f} / {il[1]:.2f} | {qd[1]:.2f} / {qdl[1]:.2f} | |")
print(f"| tokens per round (decode / LDR) | {id_[2]:.3f} / {il[2]:.3f} | {qd[2]:.3f} / {qdl[2]:.3f} | |")
print(f"| acceptance (decode / LDR) | {id_[3]:.3f} / {il[3]:.3f} | {qd[3]:.3f} / {qdl[3]:.3f} | |")
for size in ("32k", "120k"):
    a, na = ttft(I_T, size); b, nb = ttft(Q, size)
    print(f"| time to first token {size.upper()} | {a:.2f} s (n = {na}) | **{b:.2f} s** (n = {nb}) | {100 * (b / a - 1):+.0f} % |")
