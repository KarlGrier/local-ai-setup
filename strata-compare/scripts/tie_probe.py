"""At each first divergence between two greedy runs (REF=B llama.cpp, OTHER=C0 Strata), ask the llama.cpp server for
the top-10 next-token probabilities after the common prefix: a near-tie (the two choices within a few % of each other)
means ordinary floating-point differences; a clear winner that Strata did not pick would be a red flag.

    tie_probe.py --base http://127.0.0.1:8081 [--ref B --other C0]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze import outputs, raw_text  # noqa: E402
from common import PROMPTS, RESULTS, load_template, load_tokenizer  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--ref", default="B")
    ap.add_argument("--other", default="C0")
    ap.add_argument("--scenario", default="correctness")
    a = ap.parse_args()
    tok = load_tokenizer(Path(__file__).resolve().parents[1] / "strata/packs/iq3_s/tokenizer")
    tpl = load_template(Path(__file__).resolve().parents[1] / "strata/packs/iq3_s/tokenizer/chat_template.jinja")
    prompts = {p["id"]: p["messages"] for p in json.loads((PROMPTS / f"{a.scenario}.json").read_text())}
    ref, oth = outputs(a.ref, a.scenario), outputs(a.other, a.scenario)
    rows = []
    for item, rs in ref.items():
        if item not in oth:
            continue
        x, y = tok.encode(raw_text(rs[-1])), tok.encode(raw_text(oth[item][-1]))
        n = next((i for i, (p, q) in enumerate(zip(x, y)) if p != q), None)
        if n is None:
            rows.append((item, None, None, None, None))
            continue
        prompt_ids = tok.encode(tpl.render(prompts[item]), parse_special=True) + x[:n]
        body = {"prompt": prompt_ids, "n_predict": 1, "n_probs": 10, "temperature": 0, "cache_prompt": False,
                "post_sampling_probs": False}
        r = requests.post(a.base.rstrip("/") + "/completion", json=body, timeout=600).json()
        cp = (r.get("completion_probabilities") or [{}])[0]
        tops = cp.get("top_logprobs") or cp.get("top_probs") or cp.get("probs") or []
        probs = {}
        for t in tops:
            tid = t.get("id")
            if "logprob" in t:
                probs[tid] = math.exp(t["logprob"])
            elif "prob" in t:
                probs[tid] = t["prob"]
        rows.append((item, n, (x[n], tok.decode([x[n]]), probs.get(x[n])), (y[n], tok.decode([y[n]]), probs.get(y[n])),
                     sorted(probs.values(), reverse=True)[:3]))
    out = ["| prompt | divergence at | B's token (llama.cpp p) | C0's token (llama.cpp p) | top-3 p |", "|---|---|---|---|---|"]
    for item, n, bx, cy, top in rows:
        if n is None:
            out.append(f"| {item} | identical | | | |")
        else:
            f = lambda t: f"{t[1]!r} ({t[2]:.3f})" if t[2] is not None else f"{t[1]!r} (not in top-10)"
            out.append(f"| {item} | {n} | {f(bx)} | {f(cy)} | {', '.join(f'{p:.3f}' for p in top)} |")
    text = "\n".join(out)
    print(text)
    (RESULTS / f"tie_probe_{a.ref}_{a.other}.md").write_text(text + "\n")


if __name__ == "__main__":
    main()
