#!/usr/bin/env python3
"""fixtures_client.py URL OUT.jsonl --plan PLAN.json [--label L] - C5 of the v0.2.13 switch checks: the three chat
fixtures (Basalt's decode fixtures conv / struct / prose, their user texts and max_tokens 1200 / 8192 / 1200, rendered
before the gap by switch_rules.py fixtures with P's tree) sent to ONE fresh test server at the standard sampling
(temperature 1.0, top_p 0.95, top_k 20, min_p 0.05; presence 0, frequency 0, repetition 1; a fixed seed each; thinking
off) - the gap driver's rule for every request (bp90_client.py's own T 0.6 / T 0 is not used). Written 2026-11-10 at the
desk; NOT RUN against a server (only `selftest`, on a fake one).
-> OUT.jsonl, one record a request: name, prompt_tokens (and the expected count), completion_tokens, finish, the server's
timings (llama.cpp's fields: decode_tps = predicted_per_second, prompt_tps), the first-token and wall times, error.
Exit 0 every request answered, 1 one failed, 2 refused (a bad plan). `fixtures_client.py selftest DIR` (no server).
"""
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = os.path.join(HERE, "scratch")
STANDARD = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}


def chat(url, r, fields):
    body = {"model": "x", "messages": r["messages"], "max_tokens": r["max_tokens"], "stream": True,
            "stream_options": {"include_usage": True}, **fields, "seed": r["seed"],
            "chat_template_kwargs": {"enable_thinking": bool(r.get("thinking"))}}
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    first = usage = timings = finish = err = None
    with urllib.request.urlopen(req, timeout=3600) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                c = json.loads(data)
            except ValueError:
                continue
            if c.get("error"):
                err = str(c["error"])[:200]
            for ch in c.get("choices") or []:
                d = ch.get("delta") or {}
                if (d.get("content") or d.get("reasoning_content")) and first is None:
                    first = time.monotonic() - t0
                finish = ch.get("finish_reason") or finish
            usage = c.get("usage") or usage
            timings = c.get("timings") or timings
    u, tm = usage or {}, timings or {}
    return {"prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
            "finish": "error" if err else finish, "error": err, "decode_tps": tm.get("predicted_per_second"),
            "prompt_tps": tm.get("prompt_per_second"), "first_token_s": round(first, 3) if first else None,
            "wall_s": round(time.monotonic() - t0, 2)}, body


def run(url, out, plan):
    fields = plan.get("fields") or {}
    bad = [f"{k}={fields.get(k)!r} (the standard sampling is {v})" for k, v in STANDARD.items() if fields.get(k) != v]
    if bad or not plan.get("requests"):
        print("refused: " + ("; ".join(bad) or "no requests in the plan"), flush=True)
        return 2, []
    rc, bodies = 0, []
    for r in plan["requests"]:
        rec = {"name": r["name"], "max_tokens": r["max_tokens"], "seed": r["seed"],
               "expect_prompt_tokens": r.get("expect_prompt_tokens"), "time": time.strftime("%F %T")}
        try:
            got, body = chat(url, r, fields)
            rec.update(got)
            bodies.append(body)
        except Exception as e:  # noqa: BLE001
            rec.update(finish="error", error=f"{type(e).__name__}: {e}"[:200])
        if rec.get("finish") not in ("stop", "length"):
            rc = 1
        with open(out, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"fixture {rec['name']}: {rec.get('completion_tokens')} tokens ({rec.get('finish')}), {rec.get('decode_tps')} tok/s"
              + ("" if rec.get("prompt_tokens") == rec.get("expect_prompt_tokens") else
                 f"  PROMPT TOKENS {rec.get('prompt_tokens')} != {rec.get('expect_prompt_tokens')}"), flush=True)
    return rc, bodies


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["selftest"]:
        return selftest(argv[1] if len(argv) > 1 else f"{SCRATCH}/fixtures-selftest")
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--label")
    a = ap.parse_args(argv)
    try:
        plan = json.load(open(a.plan))
    except (OSError, ValueError) as e:
        print(f"refused: the plan {a.plan}: {e}")
        return 2
    return run(a.url, a.out, plan)[0]


def selftest(base):
    import io
    import shutil
    root = os.path.realpath(SCRATCH)
    if not os.path.realpath(base).startswith(root + os.sep):
        print(f"selftest writes only under {root}")
        return 2
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(base)
    ok = True

    def chk(what, cond):
        nonlocal ok
        print(f"{'ok  ' if cond else 'FAIL'} {what}", flush=True)
        ok = ok and bool(cond)

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(req, timeout=None):
        b = json.loads(req.data.decode())
        ev = [{"choices": [{"delta": {"content": "x"}}]},
              {"choices": [{"delta": {}, "finish_reason": "length"}], "usage": {"prompt_tokens": 38, "completion_tokens": b["max_tokens"]},
               "timings": {"predicted_per_second": 130.5, "prompt_per_second": 400.0}}]
        return Resp(("".join(f"data: {json.dumps(e)}\n\n" for e in ev) + "data: [DONE]\n").encode())
    fields = dict(STANDARD, presence_penalty=0.0, frequency_penalty=0.0, repetition_penalty=1.0)
    plan = {"fields": fields, "requests": [{"name": n, "messages": [{"role": "user", "content": n}], "max_tokens": m,
                                            "seed": 7300001 + i, "expect_prompt_tokens": 38}
                                           for i, (n, m) in enumerate((("conv", 1200), ("struct", 8192), ("prose", 1200)))]}
    real = urllib.request.urlopen
    try:
        urllib.request.urlopen = fake
        rc, bodies = run("http://127.0.0.1:1", f"{base}/fx.jsonl", plan)
    finally:
        urllib.request.urlopen = real
    recs = [json.loads(x) for x in open(f"{base}/fx.jsonl")]
    chk(f"exit {rc}, 3 records with the timings", rc == 0 and len(recs) == 3 and recs[1]["decode_tps"] == 130.5
        and recs[1]["completion_tokens"] == 8192)
    chk("every body at the standard sampling (not Basalt's T 0.6 / T 0), thinking off, its seed",
        all(all(b[k] == v for k, v in fields.items()) and b["chat_template_kwargs"] == {"enable_thinking": False} for b in bodies)
        and [b["seed"] for b in bodies] == [7300001, 7300002, 7300003])
    rc2, _ = run("http://127.0.0.1:1", f"{base}/fx2.jsonl", dict(plan, fields=dict(fields, temperature=0.6)))
    chk(f"a plan at T 0.6 is refused (exit {rc2})", rc2 == 2)
    print("FIXTURES CLIENT SELFTEST " + ("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
