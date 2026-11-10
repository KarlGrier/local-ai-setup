"""bp90_client.py - Basalt PR #90's "community-1" preset, sent to one of our servers (Karl 10-30).

  bp90_client.py URL --label L --sets decode,pp16k,pp64k --out FILE.jsonl [--passes N] [--tree TREE] [--data DIR]

The prompts are Basalt's data/bench/*.ids at b2fe96bf30 (extracted as plain data into DIR; nothing of Basalt is imported
or run). check_ids.py showed every fixture re-encodes to the identical ids with our tokenizer and chat template
(thinking off), so each one is sent as its user text over /v1/chat/completions with enable_thinking false, and the
server's prompt_tokens is checked against the id count.

  decode  conv (1200 tokens, T 0.6), struct (8192, T 0), prose (1200, T 0.6), in that fixed order (Basalt: the draft
          state carries across requests), top_p 0.95, top_k 20 - Basalt's request keys. Basalt's engine default min_p is
          0 and it sends no penalties, so min_p 0 and presence_penalty 0 are sent explicitly (our config's min_p 0.05 and
          the model card's thinking-off presence_penalty 1.5 would otherwise apply).
  pp16k / pp64k  "Document:\\n" + 4 random ids (1000..150000) + the 16,384-depth body cut or repeated by id
          (n_body = round(16647 x depth / 16384), body[k % 16647]) + the question; 32 new tokens at 16K, 1 at 64K, keys
          top_p 0.95 top_k 20 (Basalt's), T 1.0. The 4 random ids are drawn until the whole prompt round-trips to the
          exact id list through our template and tokenizer (else the closest draw is sent and the difference recorded).

Per request it records our server's timings (llama.cpp's fields: prompt_n / prompt_ms = Basalt's "engine t/s",
predicted_n / predicted_ms) and the time to the first streamed token (Basalt's "wall t/s" = prompt / first token)."""
import argparse
import json
import random
import sys
import time
import urllib.request
from pathlib import Path

DECODE = [("conv", 1200, 0.6), ("struct", 8192, 0.0), ("prose", 1200, 0.6)]
BASE = 16384
DEPTHS = {"pp16k": (16384, 32), "pp64k": (65536, 1)}

ap = argparse.ArgumentParser()
ap.add_argument("url")
ap.add_argument("--label", required=True)
ap.add_argument("--sets", default="decode,pp16k,pp64k")
ap.add_argument("--out", required=True)
ap.add_argument("--passes", type=int, default=1)
ap.add_argument("--first-pass", type=int, default=1, help="the pass number recorded for the first pass")
ap.add_argument("--dry-run", action="store_true", help="build the prompts and check them; send nothing")
ap.add_argument("--tree", default="/home/USER/ai-speed-testing/strata-compare/strata-r22p021m")
ap.add_argument("--data", default="/home/USER/ai-speed-testing/basalt-pr90-data")
ap.add_argument("--gguf", default="/home/USER/ai-speed-testing/strata-compare/models/ISTA-GSQ-RCO/IQ3_S/"
                                  "Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf")
a = ap.parse_args()

tree, data = Path(a.tree), Path(a.data)
sys.path.insert(0, str(tree))
sys.path.insert(0, str(tree / "tools"))
from strata_tokenizer import Tokenizer          # noqa: E402
from serve.frontend import ChatTemplate          # noqa: E402

tok = Tokenizer.from_gguf(a.gguf)
tpl = ChatTemplate(str(tree / "serve" / "chat_template.jinja"))
render = lambda user: tpl.render([{"role": "user", "content": user}], enable_thinking=False)   # noqa: E731
MARK = "⁣BODY⁣"
PRE_TXT, POST_TXT = render(MARK).split(MARK)
ids_of = lambda name: [[int(x) for x in l.split(",")] for l in (data / name).read_text().strip().split("\n")]   # noqa: E731


def user_text(ids):
    """The user message whose rendering is `ids` (the template's prefix and suffix taken off the decoded text)."""
    text = tok.decode(ids)
    assert text.startswith(PRE_TXT) and text.endswith(POST_TXT), "not our template around one user message"
    return text[len(PRE_TXT):len(text) - len(POST_TXT)]


def prefill_prompt(depth, rng):
    pre, body, post = ids_of("prefill.ids")
    n_body = max(1, round(len(body) * depth / BASE))
    full_body = [body[k % len(body)] for k in range(n_body)]
    best = None
    for attempt in range(60):
        nonce = [rng.randint(1000, 150000) for _ in range(4)]
        ids = pre + nonce + full_body + post
        user = user_text(ids)
        back = tok.encode(render(user), parse_special=True)
        d = 0 if back == ids else (abs(len(back) - len(ids)) or 1)
        if best is None or d < best[0]:
            best = (d, ids, user, len(back), attempt + 1)
        if d == 0:
            break
    d, ids, user, n_back, tries = best
    return user, len(ids), {"exact_roundtrip": d == 0, "ids_sent_as": n_back, "nonce_tries": tries}


def chat(user, max_new, temperature, label):
    body = {"model": "x", "messages": [{"role": "user", "content": user}], "max_tokens": max_new, "stream": True,
            "stream_options": {"include_usage": True}, "chat_template_kwargs": {"enable_thinking": False},
            "temperature": temperature, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 0.0,
            "frequency_penalty": 0.0, "repetition_penalty": 1.0}
    req = urllib.request.Request(a.url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    first = None
    usage = timings = finish = None
    n_chars = 0
    with urllib.request.urlopen(req, timeout=3600) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            c = json.loads(payload)
            for ch in c.get("choices") or []:
                delta = ch.get("delta") or {}
                piece = (delta.get("content") or "") + (delta.get("reasoning_content") or "")
                if piece and first is None:
                    first = time.monotonic() - t0
                n_chars += len(piece)
                finish = ch.get("finish_reason") or finish
            usage = c.get("usage") or usage
            timings = c.get("timings") or timings
    wall = time.monotonic() - t0
    return {"first_token_s": first, "wall_s": round(wall, 3), "usage": usage, "timings": timings, "finish": finish,
            "chars": n_chars}


rng = random.Random()
sets = a.sets.split(",")
expect = {name: len(ids_of(f"{name}.ids")[0]) for name, _, _ in DECODE}
with open(a.out, "a") as out:
    for p in range(a.first_pass, a.first_pass + a.passes):
        jobs = []
        if "decode" in sets:
            jobs += [(name, user_text(ids_of(f"{name}.ids")[0]), mx, t, expect[name], {}) for name, mx, t in DECODE]
        for s in ("pp16k", "pp64k"):
            if s in sets:
                depth, mx = DEPTHS[s]
                user, n, info = prefill_prompt(depth, rng)
                jobs.append((s, user, mx, 1.0, n, info))
        for name, user, mx, t, n_expect, info in jobs:
            if a.dry_run:
                n_back = len(tok.encode(render(user), parse_special=True))
                print(f"dry run {name}: {n_expect} ids expected, our template encodes {n_back}, {info}", flush=True)
                continue
            r = chat(user, mx, t, a.label)
            u, tm = r["usage"] or {}, r["timings"] or {}
            rec = {"label": a.label, "pass": p, "test": name, "max_tokens": mx, "temperature": t,
                   "prompt_ids_expected": n_expect, "prompt_tokens": u.get("prompt_tokens"),
                   "cached": (u.get("prompt_tokens_details") or {}).get("cached_tokens"),
                   "completion_tokens": u.get("completion_tokens"), "finish": r["finish"], **info,
                   "prompt_n": tm.get("prompt_n"), "prompt_ms": tm.get("prompt_ms"), "prompt_tps": tm.get("prompt_per_second"),
                   "predicted_n": tm.get("predicted_n"), "predicted_ms": tm.get("predicted_ms"),
                   "decode_tps": tm.get("predicted_per_second"), "draft_n": tm.get("draft_n"),
                   "draft_n_accepted": tm.get("draft_n_accepted"), "first_token_s": r["first_token_s"], "wall_s": r["wall_s"],
                   "time": time.strftime("%F %T")}
            out.write(json.dumps(rec) + "\n")
            out.flush()
            ok = "" if rec["prompt_tokens"] == n_expect else f"  PROMPT TOKENS {rec['prompt_tokens']} != {n_expect}"
            if name.startswith("pp"):
                print(f"{a.label} pass {p} {name}: {rec['prompt_tokens']} tokens, {rec['prompt_tps']} tok/s engine{ok}", flush=True)
            else:
                print(f"{a.label} pass {p} {name}: {rec['completion_tokens']} tokens ({rec['finish']}), {rec['decode_tps']} tok/s decode{ok}",
                      flush=True)
