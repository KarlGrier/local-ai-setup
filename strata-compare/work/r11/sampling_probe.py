#!/usr/bin/env python3
"""sampling_probe.py (round 9 copy: SP_LABEL names the arm; the cases and llama.cpp candidates are round 5's) prepare|llama|strata|analyze — round 5, phase 2b: is Strata's sampled output distributed as the
sampler chain says, at a near-tie?

Cases: the round-1 near-ties (results/tie_probe_B_C0.md: arith @35, code @43, science @46 of llama.cpp's greedy
answer). For each, the answer's first n-j tokens are appended to the rendered prompt (server field strata_prefix_ids,
MEASUREMENT build), so the tie is j tokens into the generation:
  j = 0: the tie is the first token (a T=1 window: the sampler alone);
  j = 3: three near-certain tokens first, so the tie is drawn inside a speculative window (drafts, verify, accept).
  prepare          -> work/r5/sp-cases.json (prompt ids exactly as Strata's server renders the chat page's request)
  llama BASE       llama-server /completion on the same ids: raw (pre-sampling) top-64 probabilities at every position
                   from the prefix to the tie -> work/r5/sp-llama.json
  strata BASE N    N sampled requests per case through Strata's server (your settings: 0.6/0.95/20 + the config's
                   min_p 0.05), generated ids back -> work/r5/sp-strata.jsonl
  analyze          the sampler chain (top_k 20 -> top_p 0.95 -> min_p 0.05 -> temperature 0.6, llama.cpp's order,
                   which Strata uses since 0.1.17) applied to llama.cpp's probabilities vs Strata's frequencies at
                   the tie among the samples whose first j tokens are the expected ones; chi-square test.
"""
import json
import math
import os
import sys
import time
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
SERVE = WS / "strata-essm10"   # round 9: the exact-sampling measurement twin (v0.1.32 base)
CASES = WS / "work/r5/sp-cases.json"
LLAMA = WS / "work/r5/sp-llama.json"
STRATA = WS / f"work/r11/sp-strata-{os.environ.get('SP_LABEL', 'x')}.jsonl"   # round 9: one file per arm          # one line per sample: case, temperature, generated ids
TIES = {"arith": 35, "code": 43, "science": 46}
JS = (0, 3)
# your chat settings (the page's shared settings since 2026-09-28 18:29: temperature 1.0; top_p 0.95, top_k 20; min_p 0.05
# from the config); temperature is a parameter so 0.6 (the earlier rounds' setting) can be checked as well
PAGE = {"reasoning_effort": "high", "top_p": 0.95, "top_k": 20, "stream": False}
CHAIN = {"top_k": 20, "top_p": 0.95, "min_p": 0.05}


def post(base, path, body, timeout=600):
    req = urllib.request.Request(base.rstrip("/") + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def server_objects():
    sys.path.insert(0, str(SERVE))
    sys.path.insert(0, str(SERVE / "serve"))
    import server as S  # noqa: E402
    from serve.frontend import ChatTemplate, openai_to_messages  # noqa: E402
    import strata_tokenizer as ST  # noqa: E402
    cfg = json.loads((WS / "configs/R9-C10.json").read_text())
    tpath = Path(cfg["tokenizer"])
    vocab = json.loads((tpath / "vocab.json").read_text(encoding="utf-8"))
    tokens = [None] * len(vocab)
    for t, i in vocab.items():
        tokens[i] = t
    tok = ST.Tokenizer(tokens, (tpath / "merges.txt").read_text(encoding="utf-8").split("\n"),
                       json.loads((tpath / "token_type.json").read_text()))

    class Eng:
        max_context = 131072
    svc = S.Service(Eng(), tok, ChatTemplate(tpath / "chat_template.jinja"),
                    sampling_defaults=S.sampling_defaults_from_config(cfg))
    return S, svc, tok, openai_to_messages


def prepare():
    S, svc, tok, o2m = server_objects()
    sys.path.insert(0, str(WS / "scripts"))
    from analyze import raw_text  # noqa: E402
    prompts = {p["id"]: p["messages"] for p in json.loads((WS / "prompts/correctness.json").read_text())}
    cases = []
    for item, n in TIES.items():
        body = {**PAGE, "messages": prompts[item]}
        messages, tools, kw = o2m(body)
        ids, thinking, _ = svc.prepare(messages, tools, kw, 0)
        r = json.loads((WS / f"results/outputs/B/correctness_{item}_r0_B-main.json").read_text())
        x = tok.encode(raw_text(r))
        for j in JS:
            cases.append({"case": f"{item}-j{j}", "item": item, "j": j, "tie": n, "prompt_ids": list(ids),
                          "prefix": x[:n - j], "path": x[n - j:n], "b_token": x[n],
                          "path_text": tok.decode(x[n - j:n]), "b_text": tok.decode([x[n]])})
        print(f"{item}: prompt {len(ids)} ids, tie at {n}: prefix ...{tok.decode(x[max(0, n - 12):n])!r} | B took "
              f"{tok.decode([x[n]])!r}")
    CASES.write_text(json.dumps(cases))


def top_probs(base, ids, n=64):
    r = post(base, "/completion", {"prompt": ids, "n_predict": 1, "n_probs": n, "temperature": 0,
                                   "cache_prompt": False, "post_sampling_probs": False})
    cp = (r.get("completion_probabilities") or [{}])[0]
    out = {}
    for t in cp.get("top_logprobs") or cp.get("top_probs") or []:
        out[int(t["id"])] = t["logprob"] if "logprob" in t else math.log(max(t["prob"], 1e-30))
    return out                                              # id -> log p (raw softmax over the vocabulary)


def llama(base):
    cases = json.loads(CASES.read_text())
    res = {}
    for c in cases:
        seq = c["prompt_ids"] + c["prefix"]
        steps = []
        for i in range(c["j"] + 1):                        # every position from the prefix end to the tie
            steps.append(top_probs(base, seq + c["path"][:i]))
        res[c["case"]] = steps
        tie = sorted(steps[-1].items(), key=lambda kv: -kv[1])[:4]
        print(c["case"], "path p:", [round(math.exp(steps[i].get(c["path"][i], -99)), 4) for i in range(c["j"])],
              "tie top:", [(k, round(math.exp(v), 4)) for k, v in tie], flush=True)
    LLAMA.write_text(json.dumps(res))


def strata(base, n, temp, only=None):
    cases = [c for c in json.loads(CASES.read_text()) if not only or c["case"] in only]
    with open(STRATA, "a") as f:
        for c in cases:
            prompts = {p["id"]: p["messages"] for p in json.loads((WS / "prompts/correctness.json").read_text())}
            t0 = time.time()
            for k in range(n):
                r = post(base, "/v1/chat/completions", {**PAGE, "temperature": temp, "messages": prompts[c["item"]],
                                                        "strata_prefix_ids": c["prefix"], "max_tokens": c["j"] + 1,
                                                        "strata_return_ids": True})
                f.write(json.dumps({"case": c["case"], "temp": temp, "ids": r.get("strata_ids")}) + "\n")
                if k % 200 == 199:
                    f.flush()
                    print(f"  {c['case']} T={temp}: {k + 1} samples, {(time.time() - t0) / (k + 1):.3f} s each", flush=True)


def strata_logp(base, reps=3):
    """Strata's OWN log-probabilities at the tie: for each candidate (llama.cpp's top 30 there), force the path + that
    token through the serve path (measurement build: force=N) and read -NLL from the engine log (FORCE lines). The
    first forced token of a request is scored in a one-token window, as the j=0 samples were drawn."""
    import os
    import re as _re
    elog = os.environ.get("ELOG")
    cases = json.loads(CASES.read_text())
    ref = json.loads(LLAMA.read_text())
    prompts = {p["id"]: p["messages"] for p in json.loads((WS / "prompts/correctness.json").read_text())}
    out = {}
    for c in cases:
        cands = [int(t) for t, _ in sorted(ref[c["case"]][-1].items(), key=lambda kv: -kv[1])[:30]]
        res = {}
        for rep in range(reps):
            for t in cands:
                off = os.path.getsize(elog)
                post(base, "/v1/chat/completions", {**PAGE, "temperature": 1.0, "messages": prompts[c["item"]],
                                                    "strata_prefix_ids": c["prefix"],
                                                    "strata_force_ids": c["path"] + [t]})
                time.sleep(0.2)
                with open(elog, "rb") as f:
                    f.seek(off)
                    lines = [ln for ln in f.read().decode("utf-8", "replace").splitlines() if ln.startswith("FORCE ")]
                last = lines[-1].split() if lines else None       # FORCE pos target argmax nll
                if last and int(last[2]) == t:
                    res.setdefault(str(t), []).append(-float(last[4]))
        out[c["case"]] = res
        top = sorted(((sum(v) / len(v), k) for k, v in res.items()), reverse=True)[:4]
        print(c["case"], [(k, round(math.exp(v), 4), [round(math.exp(x), 4) for x in res[k]]) for v, k in top], flush=True)
    (WS / f"work/r11/sp-strata-logp-{os.environ.get('SP_LABEL', 'x')}.json").write_text(json.dumps(out))


def chain(logp: dict, temp, p=CHAIN):
    """llama.cpp's default sampler chain on raw log-probabilities: top_k -> top_p -> min_p -> temperature."""
    items = sorted(logp.items(), key=lambda kv: -kv[1])[:p["top_k"]]
    mx = items[0][1]
    w = [math.exp(v - mx) for _, v in items]
    s = sum(w)
    cum, keep = 0.0, len(items)
    for i, x in enumerate(w):
        cum += x / s
        if cum >= p["top_p"]:
            keep = i + 1
            break
    items = items[:keep]
    items = [(t, v) for t, v in items if v >= mx + math.log(p["min_p"])]
    w = [math.exp((v - mx) / temp) for _, v in items]
    s = sum(w)
    return {t: x / s for (t, _), x in zip(items, w)}


def chi2_sf(x, k):
    """Survival function of the chi-square distribution (k degrees of freedom), by the regularized gamma series."""
    if x <= 0:
        return 1.0
    a, z = k / 2.0, x / 2.0
    # lower regularized gamma P(a, z) by series; Q = 1 - P
    term = 1.0 / a
    s = term
    for n in range(1, 2000):
        term *= z / (a + n)
        s += term
        if term < s * 1e-15:
            break
    p = s * math.exp(-z + a * math.log(z) - math.lgamma(a))
    return max(0.0, 1.0 - p)


def analyze():
    cases = {c["case"]: c for c in json.loads(CASES.read_text())}
    ref = json.loads(LLAMA.read_text())
    samples = {}
    for ln in open(STRATA):
        d = json.loads(ln)
        samples.setdefault((d["case"], d.get("temp", 0.6)), []).append(d["ids"])
    sys.path.insert(0, str(SERVE))
    _, _, tok, _ = server_objects()
    own_p = WS / f"work/r11/sp-strata-logp-{os.environ.get('SP_LABEL', 'x')}.json"
    own = json.loads(own_p.read_text()) if own_p.exists() else {}
    rows = []
    for (name, temp), got in sorted(samples.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        c = cases[name]
        j = c["j"]
        on_path = [s for s in got if s and len(s) > j and s[:j] == c["path"]]
        use_own = len(sys.argv) > 2 and sys.argv[2] == "own" and own.get(name)
        exp = chain({int(k): sum(v) / len(v) for k, v in own[name].items()} if use_own else
                    {int(k): v for k, v in ref[name][-1].items()}, temp)
        path_p = [chain({int(k): v for k, v in ref[name][i].items()}, temp).get(c["path"][i], 0.0) for i in range(j)]
        counts = {}
        for s in on_path:
            counts[s[j]] = counts.get(s[j], 0) + 1
        n = len(on_path)
        # chi-square over the tokens the chain allows (bins with expected < 5 merged into one); a sampled token
        # outside the allowed set counts as an immediate failure
        outside = sum(v for t, v in counts.items() if t not in exp)
        bins, rest_e, rest_o = [], 0.0, 0
        for t, pe in sorted(exp.items(), key=lambda kv: -kv[1]):
            e = pe * n
            if e >= 5:
                bins.append((t, counts.get(t, 0), e))
            else:
                rest_e += e
                rest_o += counts.get(t, 0)
        if rest_e > 0:
            bins.append(("rest", rest_o, rest_e))
        chi = sum((o - e) ** 2 / e for _, o, e in bins if e > 0)
        dof = max(1, len(bins) - 1)
        pval = chi2_sf(chi, dof)
        detail = ", ".join(f"{tok.decode([t]) if t != 'rest' else 'rest'!r}: {o} vs {e:.1f}" for t, o, e in bins)
        rows.append((f"{name} T={temp}", len(got), n, path_p, detail, chi, dof, pval, outside))
    print("| case | samples | on path (expected share) | tie: observed vs expected (llama.cpp probabilities through the "
          "chain) | chi-square (dof) | p-value | outside the allowed set |")
    print("|---|---|---|---|---|---|---|")
    for name, tot, n, pp, detail, chi, dof, pval, outside in rows:
        share = math.prod(pp) if pp else 1.0
        print(f"| {name} | {tot} | {n} ({share:.3f}) | {detail} | {chi:.2f} ({dof}) | {pval:.3f} | {outside} |")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "prepare":
        prepare()
    elif cmd == "llama":
        llama(sys.argv[2])
    elif cmd == "strata":
        strata(sys.argv[2], int(sys.argv[3]), float(sys.argv[4]), sys.argv[5].split(",") if len(sys.argv) > 5 else None)
    elif cmd == "strata_logp":
        strata_logp(sys.argv[2])
    elif cmd == "analyze":
        analyze()
