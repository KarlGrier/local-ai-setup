#!/usr/bin/env python3
"""sq_client.py URL OUTDIR - the request driver of the Qwen served-mode sampled-distribution test (work/r23/sampled-qwen/).
Written 2026-11-09 at the desk and NOT RUN against a server: it is started only inside an open gap, as the CMD of one
fresh test server (bringup/lib/with_server.sh: the server on 127.0.0.1:8081, $ELOG = the engine log), after the
arm's env check. Its server must run with STRATA_DEBUG=1 in its config's env (sq.py derive puts it there): server.py then
prints each request's generated ids, stop token included ("[strata] raw ids: [...]", serve/server.py:5803-5805); the
engine binary does not read STRATA_DEBUG (sq.py derive checks the binary). It only sends requests to the server it is
given and reads that start's server / engine logs.

Env:
  SQ_SPEC         the run's resolved spec (OUTDIR/../spec.json, written by sq.py derive): plan, seeds, prompts' messages
  SQ_ARM          the arm (a name in the spec; role reference / noise / candidate / verify)
  SQ_K            rounds (default: the arm's k, else the plan's)
  SQ_BUDGET_S     no request starts after this many seconds (default: the spec's plan.budget_s, else 600)
  SQ_LABEL        the with_server.sh label: the server log is the newest bringup/out/logs/server_<LABEL>_*.log
  SQ_SERVER_LOG   ... or its path
  ELOG            the engine log (with_server.sh exports it; SQ_ENGINE_LOG overrides)
  SQ_ELOG_BASE    the engine log's size before this server started (the gap's offset); else the start of the last
                  engine start in it (its first line, /^strata generate: memory guard/), else 0
The plan: K rounds, each the spec's prompts in order; thinking off (chat_template_kwargs enable_thinking false: the
template's empty thinking block, frontend.py:612-616), no nonce, stream; temperature 1.0, top_p 0.95, top_k 20,
min_p 0.05, presence_penalty 0, frequency_penalty 0, repetition_penalty 1 (sent: server.py:5302-5307 merges the model
card's thinking-off presence_penalty 1.5 under the request's own fields, server.py:8687-8689), seed = the arm's base +
1000 x prompt index + round (server.py:1443-1445 forwards it; the engine's Philox counter is the token's position,
core/verify.cpp:3386, so two requests with one seed and one prompt would draw the same uniforms: every request has its
own). No logprobs (they would change the engine's path: server.py:1497-1505).
-> OUTDIR/sampled-plan.json (before the first request), OUTDIR/sampled.jsonl (one record a request: name, prompt, round,
seed, prompt_tokens, completion_tokens, finish, timings, the server / engine log byte ranges of the request),
OUTDIR/server.out (the server log of this start), OUTDIR/engine.out (the engine log of this start).
Exit 0 every planned request answered, 1 a request failed, 2 refused (env / spec), 4 the budget ended the plan early.
`sq_client.py selftest DIR` (no server, no network: urlopen is a stub) checks the bodies, seeds, records and log slices.
"""
import glob
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sq_stat as ST  # noqa: E402

WS = "/home/USER/ai-speed-testing/strata-compare"
SERVER_LOGS = f"{WS}/bringup/out/logs"                 # bringup/lib/srv.sh: server_<LABEL>_<stamp>.log
FIELDS = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05, "presence_penalty": 0.0,
          "frequency_penalty": 0.0, "repetition_penalty": 1.0}
ELOG_START_RE = re.compile(rb"^strata generate: memory guard", re.M)
SCRATCH = os.path.join(HERE, "scratch")


def plan(spec, arm, k=None):
    pr = ST.prompts_of(spec)
    base = int(spec["arms"][arm]["seed_base"])
    k = int(k or ST.arm_k(spec, arm))
    out = []
    for rnd in range(k):
        for qi, q in enumerate(pr):
            out.append({"name": f"{arm}-{q}-{rnd:02d}", "arm": arm, "prompt": q, "round": rnd,
                        "seed": base + 1000 * qi + rnd, "max_tokens": int(spec["plan"]["max_tokens"])})
    return out


def body_of(messages, r):
    return {"model": "x", "messages": messages, "max_tokens": r["max_tokens"], "stream": True,
            "stream_options": {"include_usage": True}, **FIELDS, "seed": r["seed"],
            "chat_template_kwargs": {"enable_thinking": False}}


def post_stream(url, body, timeout=900):
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    t1 = t2 = None
    usage = finish = None
    n_delta = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                ev = json.loads(data)
            except ValueError:
                continue
            if ev.get("error"):
                raise RuntimeError(f"server error: {str(ev['error'])[:200]}")
            if ev.get("usage"):
                usage = ev["usage"]
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                if d.get("content") or d.get("reasoning_content") or d.get("reasoning") or d.get("tool_calls"):
                    now = time.monotonic()
                    t1 = t1 or now
                    t2 = now
                    n_delta += 1
                if ch.get("finish_reason"):
                    finish = ch["finish_reason"]
    pt, ct = (usage or {}).get("prompt_tokens"), (usage or {}).get("completion_tokens")
    rec = {"prompt_tokens": pt, "completion_tokens": ct, "finish": finish, "deltas": n_delta,
           "cached_tokens": ((usage or {}).get("prompt_tokens_details") or {}).get("cached_tokens"),
           "ttft_s": round(t1 - t0, 3) if t1 else None, "decode_s": round(t2 - t1, 3) if t1 else None}
    if ct and t1 and t2 > t1:
        rec["decode_tps"] = round((ct - 1) / (t2 - t1), 2)
    return rec


def size(p):
    try:
        return os.path.getsize(p) if p else None
    except OSError:
        return None


def server_log():
    p = os.environ.get("SQ_SERVER_LOG")
    if p:
        return p
    lab = os.environ.get("SQ_LABEL", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", lab):
        return None
    c = sorted(glob.glob(f"{SERVER_LOGS}/server_{lab}_*.log"), key=os.path.getmtime)
    return c[-1] if c else None


def wait_raw(p, off, deadline_s=15.0):
    """the request's raw-ids line follows its last token (server.py prints it before the last chunk): wait until it is in
    the server log after `off`, then return the log's size"""
    if p is None or off is None:
        return None
    t = time.monotonic() + deadline_s
    while True:
        with open(p, "rb") as f:
            f.seek(off)
            got = f.read()
        if ST.RAW.encode() in got or time.monotonic() > t:
            return off + len(got)
        time.sleep(0.2)


def copy_logs(out, slog, elog, ebase):
    if slog and os.path.exists(slog):
        with open(slog, "rb") as f, open(f"{out}/server.out", "wb") as g:
            g.write(f.read())
    if elog and os.path.exists(elog):
        with open(elog, "rb") as f, open(f"{out}/engine.out", "wb") as g:
            f.seek(ebase)
            g.write(f.read())


def elog_base(elog, at):
    v = os.environ.get("SQ_ELOG_BASE", "")
    if v.isdigit():
        return int(v)
    if not elog or at is None:
        return 0
    with open(elog, "rb") as f:
        head = f.read(at)
    starts = [m.start() for m in ELOG_START_RE.finditer(head)]
    return starts[-1] if starts else 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["selftest"]:
        return selftest(argv[1] if len(argv) > 1 else f"{SCRATCH}/client-selftest")
    if len(argv) != 2:
        print(__doc__)
        return 2
    url, out = argv
    sp = os.environ.get("SQ_SPEC", "")
    try:
        spec = ST.load_spec(sp)
    except (OSError, ValueError) as e:
        print(f"SQ_SPEC {sp!r}: {e}", flush=True)
        return 2
    bad = ST.check_spec(spec)
    arm = os.environ.get("SQ_ARM", "")
    if arm not in spec.get("arms", {}):
        bad.append(f"SQ_ARM {arm!r} is not an arm of the spec ({sorted(spec.get('arms', {}))})")
    msgs = ((spec.get("resolved") or {}).get("prompts") or {})
    if set(msgs) != set(ST.prompts_of(spec)):
        bad.append("the spec has no resolved prompts (run sq.py derive; SQ_SPEC = its OUTDIR/spec.json)")
    if bad:
        print("refused: " + "; ".join(bad), flush=True)
        return 2
    reqs = plan(spec, arm, os.environ.get("SQ_K") or None)
    budget = float(os.environ.get("SQ_BUDGET_S") or spec["plan"].get("budget_s") or 600)
    slog = server_log()
    elog = os.environ.get("SQ_ENGINE_LOG") or os.environ.get("ELOG")
    os.makedirs(out, exist_ok=True)
    e_at = size(elog)
    ebase = elog_base(elog, e_at)
    json.dump({"arm": arm, "spec": spec["name"], "spec_sha": ST.spec_sha(spec)[:16], "k": len(reqs) // len(msgs),
               "max_tokens": spec["plan"]["max_tokens"], "budget_s": budget, "fields": FIELDS, "thinking": False,
               "nonce": False, "order": ST.prompts_of(spec), "prompts": {q: {"messages": msgs[q]} for q in msgs},
               "requests": reqs, "server_log": slog, "engine_log": elog, "engine_log_base": ebase},
              open(f"{out}/sampled-plan.json", "w"), indent=1)
    if slog is None:
        print("WARNING: no server log found (SQ_LABEL / SQ_SERVER_LOG): the ids step will parse server.out in order", flush=True)
    t0 = time.monotonic()
    rc = 0
    for r in reqs:
        if time.monotonic() - t0 > budget:
            print(f"budget {budget:.0f} s reached: {r['name']} and later not sent", flush=True)
            rc = 4
            break
        s0, e0 = size(slog), size(elog)
        try:
            rec = post_stream(url, body_of(msgs[r["prompt"]], r))
        except Exception as e:  # noqa: BLE001
            print(f"{r['name']}: failed ({type(e).__name__}: {e})", flush=True)
            with open(f"{out}/sampled.jsonl", "a") as f:
                f.write(json.dumps(dict(r, finish="error", error=f"{type(e).__name__}: {e}"[:300])) + "\n")
            rc = 1
            break
        s1 = wait_raw(slog, s0)
        e1 = size(elog)
        row = dict(r, **rec, srv_off=[s0, s1] if s0 is not None and s1 is not None else None,
                   eng_off=[e0 - ebase, e1 - ebase] if e0 is not None and e1 is not None else None)
        with open(f"{out}/sampled.jsonl", "a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"{r['name']}: seed {r['seed']}, {rec.get('completion_tokens')} tokens ({rec.get('finish')}), "
              f"prompt {rec.get('prompt_tokens')}, {rec.get('decode_tps')} tok/s", flush=True)
    copy_logs(out, slog, elog, ebase)
    n = sum(1 for _ in open(f"{out}/sampled.jsonl")) if os.path.exists(f"{out}/sampled.jsonl") else 0
    print(f"done: {n} of {len(reqs)} requests in {time.monotonic() - t0:.0f} s; server.out / engine.out copied", flush=True)
    return rc


# ================================================================ the stub selftest (no server, no network)
class FakeServer:
    """stands in for server.py + engine: renders the prompt with `render`, draws the answer from the synthetic model
    (jittered rows, the request's seed), streams it, and writes the lines server.py (STRATA_DEBUG=1) and the engine write"""
    def __init__(self, slog, elog, render, model, sd=0.02, temperature=1.0, eng_extra=(), stop_id=None):
        self.slog, self.elog, self.render, self.model = slog, elog, render, model
        self.sd, self.temperature, self.eng_extra, self.stop_id = sd, temperature, list(eng_extra), stop_id
        self.bodies = []

    def __call__(self, req, timeout=None):
        import io
        import random
        b = json.loads(req.data.decode())
        self.bodies.append(b)
        pids = self.render(b["messages"])
        rng = random.Random(b["seed"] * 7919 + 13)
        gen, finish = [], "length"
        ctx = list(pids)
        while len(gen) < b["max_tokens"]:
            x = ST.draw(ST.jitter(self.model.row_at(ctx, len(ctx) - 1), rng, self.sd), rng, self.temperature)
            gen.append(x)
            ctx.append(x)
            if self.stop_id is not None and x == self.stop_id:
                finish = "stop"
                break
        with open(self.slog, "a") as f:
            f.write(f"[strata] req openai: msgs={len(b['messages'])} tools=0 max_tokens_raw={b['max_tokens']!r}/None "
                    f"max_new={b['max_tokens']} thinking=False stream=True prompt_tokens={len(pids)} last='user':'x'\n")
            f.write(f"[strata] done: {len(gen)} tokens in 4 s (120.0 tok/s) ({finish}, cancel=False), expert cache 86.0% "
                    "hit (+20.0% of the routed experts over PCIe)\n")
            f.write(f"[strata] raw: 'text'\n{ST.RAW}{gen}\n")
        with open(self.elog, "a") as f:
            for e in self.eng_extra:
                f.write(e + "\n")
            f.write(f"strata serve: prompt {len(pids)} tokens = 0 reused + {len(pids)} read in 10 ms (100.0 tok/s), "
                    f"{len(gen)} generated in {len(gen) * 8} ms (125.0 tok/s), drafts accepted {len(gen) // 2} of "
                    f"{len(gen)}, 1 checkpoints, {len(gen) // 2} windows, 2.00 drafts per window\n")
        ev = [{"choices": [{"delta": {"content": "x"}}]}] * 2 + \
             [{"choices": [{"delta": {}, "finish_reason": finish}],
               "usage": {"prompt_tokens": len(pids), "completion_tokens": len(gen), "total_tokens": len(pids) + len(gen),
                         "prompt_tokens_details": {"cached_tokens": 0}}}]

        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        return Resp(("".join(f"data: {json.dumps(e)}\n\n" for e in ev) + "data: [DONE]\n").encode())


def run_with_fake(spec_path, arm, out, fake, slog, elog, env_extra=None):
    """one client run against `fake` (urlopen stubbed, sleeps cut), env as the gap sets it; -> exit code"""
    real = urllib.request.urlopen
    keys = ("SQ_SPEC", "SQ_ARM", "SQ_K", "SQ_BUDGET_S", "SQ_LABEL", "SQ_SERVER_LOG", "ELOG", "SQ_ENGINE_LOG", "SQ_ELOG_BASE")
    saved = {k: os.environ.get(k) for k in keys}
    urllib.request.urlopen = fake
    try:
        for k in keys:
            os.environ.pop(k, None)
        os.environ.update(SQ_SPEC=spec_path, SQ_ARM=arm, SQ_SERVER_LOG=slog, ELOG=elog, **(env_extra or {}))
        return main([f"http://127.0.0.1:1", out])
    finally:
        urllib.request.urlopen = real
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def client_checks(base, chk):
    """the client's own checks on a tiny synthetic spec (used by sq.py selftest and `sq_client.py selftest`)"""
    import shutil
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(base)
    spec = {"name": "client-selftest", "use": "selftest", "plan": {"prompts": [{"name": "a"}, {"name": "b"}],
            "max_tokens": 20, "thinking": False, "k": 2},
            "arms": {"R1": {"role": "reference", "base": "/x.json", "seed_base": 1_000_000, "exercise": []},
                     "R2": {"role": "noise", "same_as": "R1", "seed_base": 2_000_000},
                     "X1": {"role": "candidate", "same_as": "R1", "seed_base": 3_000_000, "k": 3}},
            "exercise": {}, "verify": {}, "scorer": {"base": "/s.json", "spec": 2, "topk": 64}, "taint": [],
            "resolved": {"prompts": {"a": [{"role": "user", "content": "alpha"}], "b": [{"role": "user", "content": "beta"}]}}}
    sp = f"{base}/spec.json"
    json.dump(spec, open(sp, "w"))
    model = ST.SynthModel(vocab=5000, salt=3)
    render = lambda m: [11, 12, 13] + [100 + len(m[0]["content"])]          # noqa: E731 (a synthetic renderer)
    slog, elog = f"{base}/server.log", f"{base}/engine.log"
    open(slog, "w").write("[strata] sampling defaults from the config: temperature=1.0\n")
    open(elog, "w").write("old start\nstrata generate: memory guard: old\nx\nstrata generate: memory guard: this start\n"
                          + ST.ENGINE_EXACT + "\n")
    fake = FakeServer(slog, elog, render, model, stop_id=None)
    rc = run_with_fake(sp, "X1", f"{base}/X1", fake, slog, elog)
    recs = ST.read_jsonl(f"{base}/X1/sampled.jsonl")
    bodies = fake.bodies
    want = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05, "presence_penalty": 0.0,
            "frequency_penalty": 0.0, "repetition_penalty": 1.0}
    chk(f"client: X1 K 3 -> {len(bodies)} requests, rounds interleaved {[b['messages'][0]['content'] for b in bodies[:4]]}, "
        f"seeds {[b['seed'] for b in bodies]}",
        rc == 0 and len(bodies) == 6 and [b["seed"] for b in bodies] == [3_000_000, 3_001_000, 3_000_001, 3_001_001,
                                                                          3_000_002, 3_001_002]
        and [b["messages"][0]["content"] for b in bodies[:2]] == ["alpha", "beta"])
    chk("client: every body thinking off (chat_template_kwargs only, no reasoning_effort / thinking / logprobs / nonce), "
        "T 1.0 / 0.95 / 20 / min-p 0.05, presence 0, frequency 0, repetition 1, stream with usage",
        all(b.get("chat_template_kwargs") == {"enable_thinking": False} and "reasoning_effort" not in b and "thinking" not in b
            and "logprobs" not in b and "top_logprobs" not in b and all(b[k] == v for k, v in want.items())
            and b["stream"] is True and b["stream_options"] == {"include_usage": True} and b["max_tokens"] == 20
            and b["messages"] == spec["resolved"]["prompts"][["a", "b"][(b["seed"] - 3_000_000) // 1000]]
            for b in bodies))
    so = open(f"{base}/X1/server.out", "rb").read()
    eo = open(f"{base}/X1/engine.out", "rb").read()
    sl = [so[r["srv_off"][0]:r["srv_off"][1]].decode() for r in recs]
    el = [eo[r["eng_off"][0]:r["eng_off"][1]].decode() for r in recs]
    chk(f"client: records {len(recs)}, each server slice holds exactly its raw-ids line, each engine slice its decode line; "
        f"engine.out starts at this start's first line ({eo[:40]!r})",
        len(recs) == 6 and all(s.count(ST.RAW) == 1 for s in sl) and all(e.count("strata serve: prompt ") == 1 for e in el)
        and eo.startswith(b"strata generate: memory guard: this start")
        and all(r["completion_tokens"] == 20 and r["prompt_tokens"] == 4 and r["finish"] == "length" for r in recs))
    pl = json.load(open(f"{base}/X1/sampled-plan.json"))
    chk("client: sampled-plan.json written with the prompts, the fields, thinking false",
        pl["thinking"] is False and pl["fields"] == want and set(pl["prompts"]) == {"a", "b"} and len(pl["requests"]) == 6)
    rc2 = run_with_fake(sp, "Z9", f"{base}/Z9", fake, slog, elog)
    spec_t = dict(spec, plan=dict(spec["plan"], thinking=True))
    json.dump(spec_t, open(f"{base}/spec-think.json", "w"))
    rc3 = run_with_fake(f"{base}/spec-think.json", "R1", f"{base}/T", fake, slog, elog)
    chk(f"client: an unknown arm (exit {rc2}) and a thinking-on plan (exit {rc3}) are refused", rc2 == 2 and rc3 == 2)
    allseeds = [s for a in spec["arms"] for s in ST.seeds_of(spec, a)]
    chk(f"client: no seed shared between arms ({len(allseeds)} seeds, {len(set(allseeds))} distinct)",
        len(set(allseeds)) == len(allseeds))


def selftest(base):
    root = os.path.realpath(SCRATCH)
    if not os.path.realpath(base).startswith(root + os.sep):
        print(f"selftest writes only under {root}")
        return 2
    ok = True

    def chk(what, cond):
        nonlocal ok
        print(f"{'ok  ' if cond else 'FAIL'} {what}", flush=True)
        ok = ok and bool(cond)
    client_checks(base, chk)
    print("CLIENT SELFTEST " + ("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
