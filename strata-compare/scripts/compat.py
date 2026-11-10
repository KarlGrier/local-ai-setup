"""Client-compatibility and reasoning-effort checks (section 5 item 7, section 4 C0 effort proof).

    compat.py --base http://127.0.0.1:8081 --config C0 [--strata-template PATH]

1. /v1/models; 2. an Open WebUI-style streamed request through the official OpenAI client: reasoning must arrive
separately (delta.reasoning_content) from the answer (delta.content); 3. non-streamed; 4. a request with NO
max_tokens (what Open WebUI sends by default) -> finish_reason / length; 5. client disconnect mid-stream, then a new
request must work; 6. (Strata) the rendered prompt for each reasoning_effort, and usage.prompt_tokens as proof of
what reached the template.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RESULTS, append_jsonl, load_template, load_tokenizer, now_iso  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--model", default="model")
    ap.add_argument("--strata-template", default="")
    ap.add_argument("--skip-nomax", action="store_true")
    a = ap.parse_args()
    out = {"config": a.config, "started": now_iso(), "checks": {}}
    ck = out["checks"]
    cl = OpenAI(base_url=a.base.rstrip("/") + "/v1", api_key="sk-anything", timeout=3600)

    ck["models"] = [m.id for m in cl.models.list().data]

    # 2. Open WebUI style: system prompt + user, stream=True, stream_options include_usage, no max_tokens
    msgs = [{"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "In one short paragraph: what does a DNS resolver do?"}]
    t0 = time.time()
    rs, cs, finish, usage, n_r, n_c, order = [], [], None, None, 0, 0, []
    stream = cl.chat.completions.create(model=a.model, messages=msgs, stream=True, max_tokens=2048,
                                        stream_options={"include_usage": True})
    for ch in stream:
        if ch.usage:
            usage = ch.usage.model_dump()
        for c in ch.choices:
            d = c.delta
            r = getattr(d, "reasoning_content", None) or (d.model_extra or {}).get("reasoning_content")
            if r:
                rs.append(r); n_r += 1
                if not order or order[-1] != "reasoning": order.append("reasoning")
            if d.content:
                cs.append(d.content); n_c += 1
                if not order or order[-1] != "content": order.append("content")
            if c.finish_reason:
                finish = c.finish_reason
    ck["stream"] = {"reasoning_chunks": n_r, "content_chunks": n_c, "order": order, "finish": finish, "usage": usage,
                    "reasoning_head": "".join(rs)[:200], "content": "".join(cs)[:600],
                    "think_tags_leaked": "<think>" in "".join(cs) or "</think>" in "".join(cs),
                    "seconds": round(time.time() - t0, 1)}

    # 3. non-streamed
    r = cl.chat.completions.create(model=a.model, messages=msgs, max_tokens=2048)
    m = r.choices[0].message
    ck["nonstream"] = {"finish": r.choices[0].finish_reason, "has_reasoning": bool((m.model_extra or {}).get("reasoning_content")),
                       "content": (m.content or "")[:300], "usage": r.usage.model_dump() if r.usage else None}

    # 4. no max_tokens at all (Open WebUI default) on a prompt that needs a long answer
    if not a.skip_nomax:
        body = {"model": a.model, "stream": True, "messages": [{"role": "user", "content":
                "Write a detailed 2,000-word guide to subnetting IPv4 networks, with worked examples."}]}
        t0 = time.time()
        fin, ntok = None, None
        with requests.post(a.base.rstrip("/") + "/v1/chat/completions", json=dict(body, stream_options={"include_usage": True}),
                           stream=True, timeout=7200) as resp:
            for raw in resp.iter_lines():
                if raw.startswith(b"data: ") and raw[6:] != b"[DONE]":
                    c = json.loads(raw[6:])
                    if c.get("usage"): ntok = c["usage"].get("completion_tokens")
                    for ch in c.get("choices") or []:
                        if ch.get("finish_reason"): fin = ch["finish_reason"]
        ck["no_max_tokens"] = {"finish": fin, "completion_tokens": ntok, "seconds": round(time.time() - t0, 1)}

    # 5. disconnect mid-stream, then a fresh request
    body = {"model": a.model, "stream": True, "max_tokens": 4000,
            "messages": [{"role": "user", "content": "Count slowly from 1 to 500, one number per line."}]}
    t0 = time.time()
    with requests.post(a.base.rstrip("/") + "/v1/chat/completions", json=body, stream=True, timeout=600) as resp:
        n = 0
        for raw in resp.iter_lines():
            if raw.startswith(b"data: "):
                n += 1
                if n >= 30:
                    break
    t1 = time.time()
    r = cl.chat.completions.create(model=a.model, messages=[{"role": "user", "content": "Say OK."}], max_tokens=300)
    ck["abort_then_new"] = {"chunks_before_abort": n, "next_request_ok": bool(r.choices), "next_latency_s": round(time.time() - t1, 2),
                            "next_finish": r.choices[0].finish_reason if r.choices else None}

    # 6. reasoning effort -> template (Strata: render exactly as serve/frontend does; prompt_tokens as proof)
    if a.strata_template:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "strata"))
        from serve.frontend import openai_to_messages
        tpl = load_template(a.strata_template)
        tk = load_tokenizer(Path(a.strata_template).parent)
        eff = {}
        for effort in [None, "low", "medium", "high", "xhigh", "max", "none"]:
            req = {"messages": [{"role": "user", "content": "Hi"}]}
            if effort:
                req["reasoning_effort"] = effort
            ms, tools, kw = openai_to_messages(req)
            prompt = tpl.render(ms, tools=tools, **kw)
            n_local = len(tk.encode(prompt, parse_special=True))
            resp = cl.chat.completions.create(model=a.model, max_tokens=1, **({"reasoning_effort": effort} if effort else {}),
                                              messages=[{"role": "user", "content": "Hi"}])
            eff[str(effort)] = {"template_kwargs": kw, "rendered_prompt": prompt, "rendered_tokens": n_local,
                                "server_prompt_tokens": resp.usage.prompt_tokens if resp.usage else None}
        ck["effort"] = eff
    path = RESULTS / f"compat_{a.config}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    append_jsonl(RESULTS / "compat.jsonl", out)
    print(json.dumps(out, indent=1, ensure_ascii=False)[:6000])


if __name__ == "__main__":
    main()
