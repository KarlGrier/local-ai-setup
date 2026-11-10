#!/usr/bin/env python3
"""chatpage_check.py [CONFIG.json] — item 1, offline (no model server): what Strata's chat page sends by default and
what the server turns it into. Builds the request exactly as serve/web/app.js does with its built-in DEFAULTS
(thinking "high", temperature 0.6, top_p 0.95, top_k 20, no max, no seed), runs it through the server's own code
(openai_to_messages -> chat template -> tokenizer -> Service.prepare's max_new rule -> Service.run's sampling merge),
and compares the rendered prompt with reasoning_effort "xhigh". Uses a mock engine only for max_context."""
import json
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
SERVE_ROOT = WS / "strata-r3-run"
sys.path.insert(0, str(SERVE_ROOT))
sys.path.insert(0, str(SERVE_ROOT / "serve"))
import server as S  # noqa: E402
from serve.frontend import ChatTemplate, openai_to_messages  # noqa: E402

cfg_path = Path(sys.argv[1] if len(sys.argv) > 1 else WS / "configs/Cstar2.json")
cfg = json.loads(cfg_path.read_text())
tpath = Path(cfg["tokenizer"])
import strata_tokenizer as ST  # noqa: E402
vocab = json.loads((tpath / "vocab.json").read_text(encoding="utf-8"))
tokens = [None] * len(vocab)
for t, i in vocab.items():
    tokens[i] = t
tok = ST.Tokenizer(tokens, (tpath / "merges.txt").read_text(encoding="utf-8").split("\n"),
                   json.loads((tpath / "token_type.json").read_text()))
tpl = tpath / "chat_template.jinja"


class Eng:            # only what Service.prepare reads
    max_context = 131072


svc = S.Service(Eng(), tok, ChatTemplate(tpl if tpl.exists() else SERVE_ROOT / "serve/chat_template.jinja"),
                sampling_defaults=S.sampling_defaults_from_config(cfg))
shared_file = Path(str(cfg_path.with_suffix("")) + ".shared-settings.json")
if shared_file.exists():
    svc.shared = S.clean_shared_defaults(json.loads(shared_file.read_text()))

# app.js send(): body = {model, messages, stream, reasoning_effort: settings.thinking} + temperature/top_p/top_k
DEFAULTS = {"thinking": "high", "temperature": 0.6, "top_p": 0.95, "top_k": 20, "max": "", "seed": ""}
history = [{"role": "user", "content": "What is 17 * 23?"},
           {"role": "assistant", "content": "17 * 23 = 391."},
           {"role": "user", "content": "And 391 / 17?"}]


def page_body(s):
    body = {"model": "x", "messages": history, "stream": True, "reasoning_effort": s["thinking"]}
    if s["temperature"] > 0:
        body.update(temperature=s["temperature"], top_p=s["top_p"], top_k=s["top_k"])
    else:
        body["temperature"] = 0
    if s["seed"]:
        body["seed"] = int(s["seed"])
    if s["max"]:
        body["max_tokens"] = int(s["max"])
    return body


def server_view(body):
    req = svc.with_shared(body, "openai")
    messages, tools, kw = openai_to_messages(req)
    max_new = int(req.get("max_completion_tokens") or req.get("max_tokens") or 0)
    ids, thinking, max_new = svc.prepare(messages, tools, kw, max_new)
    sampling = {k: req.get(k) for k in ("temperature", "top_p", "top_k", "min_p", "seed", "presence_penalty",
                                        "frequency_penalty", "repetition_penalty")}
    defaults = {**svc.sampling_defaults, **svc.shared}
    if defaults:
        sampling = {**defaults, **{k: v for k, v in sampling.items() if v is not None}}
    return ids, kw, max_new, {k: v for k, v in sampling.items() if v is not None}


body = page_body(DEFAULTS)
ids_high, kw_high, max_high, samp = server_view(body)
ids_x, kw_x, _, _ = server_view({**body, "reasoning_effort": "xhigh"})
ids_none, kw_none, _, _ = server_view({k: v for k, v in body.items() if k != "reasoning_effort"})
print("config:", cfg_path.name, "| shared settings file:", shared_file.name if shared_file.exists() else "none")
print("chat page request body (built-in defaults):", json.dumps({k: v for k, v in body.items() if k != "messages"}))
print("template kwargs for 'high':", kw_high, "| for 'xhigh':", kw_x, "| field absent:", kw_none)
print("rendered prompt identical high vs xhigh:", ids_high == ids_x, "| high vs absent:", ids_high == ids_none,
      f"({len(ids_high)} tokens)")
line = tok.decode(ids_high)
print("effort line present:", "Reasoning effort is set to xhigh" in line)
print("effective sampling after the server's merge:", samp)
print(f"max_new with no max_tokens: {max_high} (= context {Eng.max_context} - 8 - prompt {len(ids_high)})")
