#!/usr/bin/env python3
"""c2_client.py URL OUTDIR --plan PLAN.json [--label L | --server-log F] [--elog-base N] - C2 of the v0.2.13 switch
checks (work/r23/switch-gap/switch_rules.py, the C2 rule): the served-output requests of one arm, sent to ONE fresh test
server (bringup/lib/with_server.sh: 127.0.0.1:8081, $ELOG = its engine log) whose config carries STRATA_DEBUG=1, so
server.py prints each request's generated ids ("[strata] raw ids: [...]", every id: the answer_room wrap-up's and the stop
token included). Written 2026-11-10 at the desk; NOT RUN against a server (only `selftest`, on a fake one).

The plan (switch_rules.py c2plan): each request's messages, thinking on / off (chat_template_kwargs enable_thinking), its
max_tokens and seed; every request sends the standard sampling (temperature 1.0, top_p 0.95, top_k 20, min_p 0.05) and
presence 0 / frequency 0 / repetition 1 (the plan's "fields"), stream with usage; no Origin header, no logprobs.
-> OUTDIR/c2.jsonl (one record a request: name, prompt, seed, thinking, max_tokens, prompt_tokens, completion_tokens,
finish, ids, the content / reasoning sha256, continuation = the server's "thinking budget reached" line in the request's
log slice, the server / engine log byte ranges, error), OUTDIR/server.out, OUTDIR/engine.out.
Exit 0 every request answered with its ids, 1 a request failed or had no raw-ids line, 2 refused (a bad plan).
`c2_client.py selftest DIR` (DIR under work/r23/switch-gap/scratch/; no server, no network: urlopen is a stub).
"""
import glob
import hashlib
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WS = "/home/USER/ai-speed-testing/strata-compare"
SERVER_LOGS = f"{WS}/bringup/out/logs"
SCRATCH = os.path.join(HERE, "scratch")
RAW = "[strata] raw ids: "
WRAP_RE = re.compile(r"^\[strata\] thinking budget reached \((\d+) tokens\)", re.M)
LIMIT_RE = re.compile(r"^\[strata\] thinking limited to (\d+) of max_tokens (\d+)", re.M)
LOST = "a request ended without an answer and without a finish reason"
STANDARD = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}
RAW_WAIT_S = 15.0                                  # (the selftest shortens it)


def size(p):
    try:
        return os.path.getsize(p) if p else None
    except OSError:
        return None


def server_log(label, path=None):
    if path:
        return path
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", label or ""):
        return None
    c = sorted(glob.glob(f"{SERVER_LOGS}/server_{label}_*.log"), key=os.path.getmtime)
    return c[-1] if c else None


def wait_raw(p, off, deadline_s=None):
    """the raw-ids line follows the request's last token: wait for it after OFF, return the log's size"""
    if p is None or off is None:
        return None
    t = time.monotonic() + (RAW_WAIT_S if deadline_s is None else deadline_s)
    while True:
        with open(p, "rb") as f:
            f.seek(off)
            got = f.read()
        if RAW.encode() in got or time.monotonic() > t:
            return off + len(got)
        time.sleep(0.2)


def body_of(r, fields):
    return {"model": "x", "messages": r["messages"], "max_tokens": r["max_tokens"], "stream": True,
            "stream_options": {"include_usage": True}, **fields, "seed": r["seed"],
            "chat_template_kwargs": {"enable_thinking": bool(r["thinking"])}}


def post_stream(url, body, timeout=900):
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    content, reasoning, usage, finish, err, done = [], [], None, None, None, False
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                done = True
                break
            try:
                ev = json.loads(data)
            except ValueError:
                continue
            if ev.get("error"):
                err = str(ev["error"])[:300]
            if ev.get("usage"):
                usage = ev["usage"]
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                if d.get("content"):
                    content.append(d["content"])
                if d.get("reasoning_content"):
                    reasoning.append(d["reasoning_content"])
                if ch.get("finish_reason"):
                    finish = ch["finish_reason"]
    c, r = "".join(content), "".join(reasoning)
    return {"prompt_tokens": (usage or {}).get("prompt_tokens"), "completion_tokens": (usage or {}).get("completion_tokens"),
            "finish": finish if not err else "error", "done": done, "error": err, "wall_s": round(time.monotonic() - t0, 2),
            "content_sha": hashlib.sha256(c.encode()).hexdigest()[:16], "content_chars": len(c),
            "reasoning_sha": hashlib.sha256(r.encode()).hexdigest()[:16], "reasoning_chars": len(r)}


def run(url, out, plan, slog, elog, ebase):
    os.makedirs(out, exist_ok=True)
    fields = plan.get("fields") or {}
    bad = [f"{k}={fields.get(k)!r} (the standard sampling is {v})" for k, v in STANDARD.items() if fields.get(k) != v]
    if bad or not plan.get("requests"):
        print("refused: " + ("; ".join(bad) or "no requests in the plan"), flush=True)
        return 2
    rc = 0
    for r in plan["requests"]:
        s0, e0 = size(slog), size(elog)
        rec = {k: r.get(k) for k in ("name", "prompt", "seed", "thinking", "max_tokens", "workload")}
        try:
            rec.update(post_stream(url, body_of(r, fields)))
        except Exception as e:  # noqa: BLE001
            rec.update(finish="error", error=f"{type(e).__name__}: {e}"[:300])
        s1 = wait_raw(slog, s0) if rec.get("finish") != "error" else size(slog)
        e1 = size(elog)
        sl = ""
        if slog and s0 is not None and s1 is not None:
            with open(slog, "rb") as f:
                f.seek(s0)
                sl = f.read(s1 - s0).decode("utf-8", "replace")
        raws = [x for x in sl.splitlines() if x.startswith(RAW)]
        if len(raws) == 1:
            rec["ids"] = [int(x) for x in json.loads(raws[0][len(RAW):].strip())]
        else:
            rec["ids"] = None
            rec["ids_why"] = f"{len(raws)} raw-ids lines in the request's server-log slice"
        rec["continuation"] = bool(WRAP_RE.search(sl))
        lm = LIMIT_RE.search(sl)
        rec["think_limit"] = int(lm.group(1)) if lm else None
        if LOST in sl:
            rec["error"] = (rec.get("error") or "") + " [the lost-answer line]"
            rec["finish"] = "error"
        rec["srv_off"] = [s0, s1] if s0 is not None and s1 is not None else None
        rec["eng_off"] = [e0 - ebase, e1 - ebase] if e0 is not None and e1 is not None else None
        if rec.get("finish") == "error" or rec["ids"] is None:
            rc = 1
        with open(f"{out}/c2.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"{rec['name']}: seed {rec['seed']}, {rec.get('completion_tokens')} tokens ({rec.get('finish')}), "
              f"{len(rec['ids']) if rec['ids'] is not None else 'NO'} ids, continuation {rec['continuation']}"
              + (f", ERROR {rec['error']}" if rec.get("error") else ""), flush=True)
    for src, dst, off in ((slog, "server.out", 0), (elog, "engine.out", ebase)):
        if src and os.path.exists(src):
            with open(src, "rb") as f, open(f"{out}/{dst}", "wb") as g:
                f.seek(off)
                g.write(f.read())
    print(f"done: {sum(1 for _ in open(f'{out}/c2.jsonl'))} of {len(plan['requests'])} requests; server.out / engine.out copied",
          flush=True)
    return rc


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["selftest"]:
        return selftest(argv[1] if len(argv) > 1 else f"{SCRATCH}/c2-client-selftest")
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--label")
    ap.add_argument("--server-log")
    ap.add_argument("--elog-base", type=int, default=0)
    a = ap.parse_args(argv)
    try:
        plan = json.load(open(a.plan))
    except (OSError, ValueError) as e:
        print(f"refused: the plan {a.plan}: {e}")
        return 2
    slog = server_log(a.label, a.server_log)
    if slog is None:
        print("WARNING: no server log found (--label / --server-log): no ids can be read", flush=True)
    return run(a.url, a.out, plan, slog, os.environ.get("ELOG"), a.elog_base)


# ================================================================ the stub selftest (no server, no network)
class Fake:
    """stands in for server.py + engine: per request a deterministic id list from (seed, thinking), its server lines"""
    def __init__(self, slog, elog, error_at=None, no_raw_at=None):
        self.slog, self.elog, self.error_at, self.no_raw_at, self.reqs = slog, elog, error_at, no_raw_at, []

    def __call__(self, req, timeout=None):
        import io
        b = json.loads(req.data.decode())
        self.reqs.append((req, b))
        n = len(self.reqs)
        think = b["chat_template_kwargs"]["enable_thinking"]
        ids = [b["seed"] % 1000 + i for i in range(5 if not think else 9)]
        with open(self.slog, "a") as f:
            f.write(f"[strata] req openai: msgs=1 max_new={b['max_tokens']} thinking={think} prompt_tokens=40\n")
            if think:
                f.write(f"[strata] thinking limited to 1024 of max_tokens {b['max_tokens']} so the answer has room\n")
                f.write("[strata] thinking budget reached (1024 tokens): wrapping up the thinking\n")
            f.write(f"[strata] done: {len(ids)} tokens in 1 s (9.0 tok/s) (length, cancel=False)\n")
            if n != self.no_raw_at:
                f.write(f"{RAW}{ids}\n")
        with open(self.elog, "a") as f:
            f.write(f"strata serve: prompt 40 tokens = 0 reused + 40 read in 10 ms (4000.0 tok/s), {len(ids)} generated in 9 ms\n")
        ev = [{"choices": [{"delta": {"reasoning_content": "hm"}}]}] if think else []
        ev += [{"choices": [{"delta": {"content": "x"}}]}]
        if n == self.error_at:
            ev += [{"error": {"type": "server_error", "message": "the engine ended the request without an answer"}}]
        else:
            ev += [{"choices": [{"delta": {}, "finish_reason": "length"}],
                    "usage": {"prompt_tokens": 40, "completion_tokens": len(ids)}}]

        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        return Resp(("".join(f"data: {json.dumps(e)}\n\n" for e in ev) + "data: [DONE]\n").encode())


def selftest(base):
    import shutil
    global RAW_WAIT_S
    RAW_WAIT_S = 0.5
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
    fields = dict(STANDARD, presence_penalty=0.0, frequency_penalty=0.0, repetition_penalty=1.0)
    plan = {"fields": fields, "requests": [
        {"name": "think-s1", "prompt": "think", "messages": [{"role": "user", "content": "prove"}], "thinking": True,
         "max_tokens": 1536, "seed": 7100001},
        {"name": "conv-s1", "prompt": "conv", "messages": [{"role": "user", "content": "chat"}], "thinking": False,
         "max_tokens": 512, "seed": 7100001},
        {"name": "conv-s2", "prompt": "conv", "messages": [{"role": "user", "content": "chat"}], "thinking": False,
         "max_tokens": 512, "seed": 7100002}]}
    real = urllib.request.urlopen
    try:
        for name, kw in (("clean", {}), ("error", {"error_at": 2}), ("noraw", {"no_raw_at": 3})):
            d = f"{base}/{name}"
            os.makedirs(d)
            slog, elog = f"{d}/server.log", f"{d}/engine.log"
            open(slog, "w").write("[strata] sampling defaults\n")
            open(elog, "w").write("strata generate: memory guard: mock\n")
            fake = Fake(slog, elog, **kw)
            urllib.request.urlopen = fake
            os.environ["ELOG"] = elog
            rc = run("http://127.0.0.1:1", f"{d}/out", plan, slog, elog, 0)
            recs = [json.loads(x) for x in open(f"{d}/out/c2.jsonl")]
            if name == "clean":
                bodies = [b for _, b in fake.reqs]
                chk(f"clean: exit {rc}, 3 records with ids, the think request's continuation seen, the others not",
                    rc == 0 and len(recs) == 3 and all(r["ids"] for r in recs) and recs[0]["continuation"] is True
                    and recs[0]["think_limit"] == 1024 and not recs[1]["continuation"] and recs[1]["ids"] == [1, 2, 3, 4, 5])
                chk("clean: every body has the standard sampling, presence 0, its seed and thinking flag, stream + usage, "
                    "no logprobs / strata_web; no Origin header",
                    all(all(b[k] == v for k, v in fields.items()) and b["stream"] is True and "logprobs" not in b
                        and "strata_web" not in b for b in bodies)
                    and [b["seed"] for b in bodies] == [7100001, 7100001, 7100002]
                    and [b["chat_template_kwargs"]["enable_thinking"] for b in bodies] == [True, False, False]
                    and all(rq.get_header("Origin") is None and rq.get_header("Content-type") == "application/json"
                            for rq, _ in fake.reqs))
                so = open(f"{d}/out/server.out", "rb").read()
                chk("clean: each record's server slice holds exactly its raw-ids line; server.out / engine.out copied",
                    all(so[r["srv_off"][0]:r["srv_off"][1]].decode().count(RAW) == 1 for r in recs)
                    and os.path.getsize(f"{d}/out/engine.out") > 0)
            elif name == "error":
                chk(f"an error chunk: exit {rc}, that record finish error, the others answered",
                    rc == 1 and recs[1]["finish"] == "error" and "without an answer" in recs[1]["error"] and recs[2]["ids"])
            else:
                chk(f"no raw-ids line: exit {rc}, ids None with the reason", rc == 1 and recs[2]["ids"] is None
                    and "0 raw-ids lines" in recs[2]["ids_why"])
        rc = run("http://127.0.0.1:1", f"{base}/refused", dict(plan, fields=dict(fields, temperature=0.6)), None, None, 0)
        chk(f"a plan without the standard sampling is refused (exit {rc})", rc == 2)
    finally:
        urllib.request.urlopen = real
        os.environ.pop("ELOG", None)
    print("C2 CLIENT SELFTEST " + ("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
