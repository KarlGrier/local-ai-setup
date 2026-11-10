#!/usr/bin/env python3
"""sampled_client.py BASE OUTDIR - the request driver of C's sampled-distribution test (results/ds41/C-SAMPLED-TEST-PLAN.md).
Written 11-07 at the desk and NOT RUN: it is started only inside an open DeepSeek gap, by work/ds41/tune/tunearm.sh as its
CLIENT (URL and OUT in the environment), on one fresh served arm whose server has STRATA_DEBUG=1 in SERVER_ENV (server.py
then prints each request's generated ids, stop token included: "[strata] raw ids: [...]" - the engine binary does not
read STRATA_DEBUG). Like greedy_client.py, it only sends requests to the test server it is given and reads the engine log.

Env:
  SAMPLED_ARM       R1 (C0) | X (C-N) | R2 (C0v): picks the seed base (1,000,000 / 3,000,000 / 2,000,000), so no two
                    arms share a seed and no draw is coupled between arms (the engine's Philox stream is keyed by seed and
                    an engine-lifetime counter: vendor/sampler.cu:46, ds4_main.cpp:327)
  SAMPLED_K         samples per prompt (default 4; R2 runs with 3)
  SAMPLED_L         max_tokens (default 512: prompt + answer stays under STRATA_DS4_SLOT_MIN 1024, so no conversation is
                    set aside to RAM or disk between requests)
  SAMPLED_BUDGET_S  no request starts after this many seconds (default 480; the plan takes ~410 s at C0's ~24 tok/s)
  GATE_LOG, GATE_EXE  as for greedy_client.py (gate_speed.py: the engine log whose "drafts A of O kept" lines it reads)

The plan, fixed: K rounds, each the four prompts in order math, code, conv, prose - W1 ("math") and W2 ("code") of the
gate's greedy check (basalt-ab workloads.json "normal", = prompts/longreason.json), C-conv and C-prose of its "calib" set;
thinking off, no nonce (identical bytes in every arm), stream, T 1.0 / top-p 0.95 / top-k 20 / min-p 0.05 (+
presence_penalty 0, which the DeepSeek engine ignores anyway: ds4_main.cpp:304-313 has no penalty keys), seed = base +
1000 * prompt index + round. Interleaved rounds keep the prompts balanced if the budget cuts the plan short.
-> OUTDIR/sampled-plan.json (written before the first request), OUTDIR/sampled.jsonl (one record a request: name, prompt,
seed, prompt_tokens, completion_tokens, finish, ttft, decode tok/s, the drafts offered / kept), OUTDIR/abrun.jsonl
(abrun's own records, with the text). sampled.py ids OUTDIR then builds the score file.
Exit 0 every planned request answered, 1 a request failed, 4 the budget ended the plan early.

2026-11-08 (d12, gap D2; backup sampled_client.py.before-d12): the INFO-only thinking-on arm (GAP-C234-PLAN.md section 6,
Karl 11-08: C0 and X only, effort low). SAMPLED_ARM may also be TR1 (C0, thinking on) or TX (X, thinking on): their seed
bases are sampled.THINK_SEED_BASE (4,000,000 / 5,000,000); SAMPLED_THINK=1 (required for TR1 / TX, refused for the
others) sends thinking on at reasoning_effort sampled.THINK_EFFORT ("low"), no nonce, the same sampling; the plan file
says "thinking": true and the effort, which `sampled.py ids` reads. A request's drafts are now the SUM of the engine's
"drafts A of O kept" lines it added (a thinking-budget wrap-up makes a second engine pass, so a second line; one line as
before for the main arms), with "draft_lines". `sampled_client.py selftest DIR` (no server, no network: abrun's HTTP call
is replaced by a stub that records the request bodies) checks the bodies, seeds and records.
"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/USER/ai-speed-testing/basalt-ab/scripts")
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/gate")
import abrun  # noqa: E402
import gate_speed as GS  # noqa: E402

SEED_BASE = {"R1": 1_000_000, "R2": 2_000_000, "X": 3_000_000,
             "TR1": 4_000_000, "TX": 5_000_000}      # (11-08: = sampled.THINK_SEED_BASE R1 / X; the selftest checks it)
THINK_ROLES = ("TR1", "TX")
THINK_EFFORT = "low"                                # (11-08: = sampled.THINK_EFFORT; the selftest checks it)
SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05, "presence_penalty": 0.0}
ORDER = ("math", "code", "conv", "prose")


def prompts():
    wl = json.load(open(abrun.WL))
    normal = {x["id"][:2]: x for x in wl["normal"]}
    calib = {x["id"]: x for x in wl["calib"]}
    return {"math": normal["W1"]["messages"], "code": normal["W2"]["messages"],
            "conv": calib["C-conv"]["messages"], "prose": calib["C-prose"]["messages"]}


def plan(arm, k, max_tokens):
    base = SEED_BASE[arm]
    reqs = []
    for rnd in range(k):
        for qi, q in enumerate(ORDER):
            reqs.append({"name": f"{arm}-{q}-{rnd:02d}", "prompt": q, "round": rnd, "seed": base + 1000 * qi + rnd,
                         "max_tokens": max_tokens})
    return reqs


def drafts_sum(lines):
    """(11-08) the request's drafts: the sum of its engine lines (one per engine pass)"""
    off = sum(int(d.get("offered") or 0) for d in lines)
    kept = sum(int(d.get("kept") or 0) for d in lines)
    pos = {}
    for d in lines:
        for p, k, n in d.get("per_pos") or []:
            x = pos.setdefault(int(p), [0, 0]); x[0] += int(k); x[1] += int(n)
    return {"offered": off, "kept": kept, "per_pos": [[p, k, n] for p, (k, n) in sorted(pos.items())] if lines else None,
            "draft_lines": len(lines)}


def main():
    if sys.argv[1:2] == ["selftest"]:
        return selftest(sys.argv[2])
    url, out = sys.argv[1], sys.argv[2]
    arm = os.environ.get("SAMPLED_ARM", "")
    if arm not in SEED_BASE:
        print(f"SAMPLED_ARM must be one of {sorted(SEED_BASE)} (got {arm!r})", flush=True)
        return 1
    think = os.environ.get("SAMPLED_THINK", "") == "1"
    if think != (arm in THINK_ROLES):
        print(f"SAMPLED_THINK=1 goes with SAMPLED_ARM in {THINK_ROLES} only (got arm {arm!r}, think {think})", flush=True)
        return 1
    k = int(os.environ.get("SAMPLED_K", "4"))
    max_tokens = int(os.environ.get("SAMPLED_L", "512"))
    budget = float(os.environ.get("SAMPLED_BUDGET_S", "480"))
    os.makedirs(out, exist_ok=True)
    msgs = prompts()
    reqs = plan(arm, k, max_tokens)
    json.dump({"arm": arm, "k": k, "max_tokens": max_tokens, "budget_s": budget, "sampling": SAMPLING,
               "thinking": think, "effort": THINK_EFFORT if think else None, "nonce": False, "order": list(ORDER),
               "prompts": {q: {"messages": msgs[q]} for q in ORDER}, "requests": reqs},
              open(f"{out}/sampled-plan.json", "w"), indent=1)
    t0 = time.monotonic()
    rc = 0
    for r in reqs:
        if time.monotonic() - t0 > budget:
            print(f"budget {budget:.0f} s reached: {r['name']} and later not sent", flush=True)
            rc = 4
            break
        job = {"id": r["name"], "messages": msgs[r["prompt"]], "max_tokens": r["max_tokens"], "thinking": think,
               "nonce": False}
        if think:
            job["effort"] = THINK_EFFORT            # (abrun.one: body["reasoning_effort"] = job["effort"])
        o0 = GS.log_size()
        try:
            rec = abrun.one(url, f"sampled-{arm}", job, dict(SAMPLING, seed=r["seed"]), {}, r["round"],
                            f"{out}/abrun.jsonl", keep_text=True)
        except Exception as e:  # noqa: BLE001
            print(f"{r['name']}: failed ({type(e).__name__}: {e})", flush=True)
            with open(f"{out}/sampled.jsonl", "a") as f:
                f.write(json.dumps(dict(r, finish="error", error=f"{type(e).__name__}: {e}")) + "\n")
            rc = 1
            break
        time.sleep(2)   # the request's engine lines follow its last token
        e = GS.engine_lines(o0, GS.log_size())
        dr = drafts_sum(e.get("drafts") or [])
        row = dict(r, prompt_tokens=rec.get("prompt_tokens"), completion_tokens=rec.get("completion_tokens"),
                   finish=rec.get("finish"), ttft_s=rec.get("ttft_s"), decode_tps=rec.get("decode_tps"),
                   drafts=dr, engine_prompt=(e.get("prompt") or [None])[0], engine_passes=len(e.get("prompt") or []),
                   slots=e.get("slots"))
        with open(f"{out}/sampled.jsonl", "a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"{r['name']}: seed {r['seed']}, {rec.get('completion_tokens')} tokens ({rec.get('finish')}), "
              f"{rec.get('decode_tps')} tok/s" + (f", drafts {dr['kept']} of {dr['offered']} kept" if dr["draft_lines"] else ""),
              flush=True)
    print(f"done: {sum(1 for _ in open(f'{out}/sampled.jsonl'))} of {len(reqs)} requests in "
          f"{time.monotonic() - t0:.0f} s", flush=True)
    return rc


def selftest(d):
    """(11-08) no server, no network: abrun's urlopen is replaced by a stub that records each request body and streams a
    fixed answer; time.sleep and the engine log are stubbed. Checks: the main and thinking-on bodies, seeds, records."""
    import io
    import shutil
    sys.path.insert(0, HERE_SAMPLED)
    import sampled as SA
    root = os.path.realpath("/home/USER/ai-speed-testing/strata-compare/work/ds41/gate/scratch-d12")
    if not os.path.realpath(d).startswith(root + os.sep):
        print(f"selftest writes only under {root}")
        return 2
    ok = True

    def chk(what, cond):
        nonlocal ok
        print(f"{'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and cond

    bodies = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        b = json.loads(req.data.decode())
        bodies.append(b)
        ev = [{"choices": [{"delta": {"content": "x"}}]}, {"choices": [{"delta": {"content": "y"}, "finish_reason": "length"}]},
              {"usage": {"prompt_tokens": 87, "completion_tokens": 2}}]
        return Resp(("".join(f"data: {json.dumps(e)}\n" for e in ev) + "data: [DONE]\n").encode())

    two = [{"kept": 5, "offered": 6, "per_pos": [[1, 3, 4], [2, 2, 2]]}, {"kept": 1, "offered": 2, "per_pos": [[1, 1, 2]]}]
    real = (abrun.urllib.request.urlopen, time.sleep, GS.log_size, GS.engine_lines)
    abrun.urllib.request.urlopen, time.sleep = fake_urlopen, (lambda s: None)
    GS.log_size, GS.engine_lines = (lambda: None), (lambda a, b: {"drafts": two, "prompt": [{"prompt": 87}, {"prompt": 300}]})
    saved_env = {k: os.environ.get(k) for k in ("SAMPLED_ARM", "SAMPLED_THINK", "SAMPLED_K", "SAMPLED_BUDGET_S")}
    saved_argv = sys.argv
    try:
        res = {}
        for arm, think in (("X", ""), ("TX", "1"), ("TR1", "1")):
            o = f"{d}/{arm}"
            shutil.rmtree(o, ignore_errors=True)
            os.environ.update(SAMPLED_ARM=arm, SAMPLED_THINK=think, SAMPLED_K="1", SAMPLED_BUDGET_S="480")
            n0 = len(bodies)
            sys.argv = ["sampled_client.py", "http://127.0.0.1:1", o]
            rc = main()
            res[arm] = (rc, bodies[n0:], [json.loads(x) for x in open(f"{o}/sampled.jsonl")], json.load(open(f"{o}/sampled-plan.json")))
        os.environ.update(SAMPLED_ARM="X", SAMPLED_THINK="1")
        sys.argv = ["sampled_client.py", "http://127.0.0.1:1", f"{d}/bad"]
        bad = main()
    finally:
        abrun.urllib.request.urlopen, time.sleep, GS.log_size, GS.engine_lines = real
        sys.argv = saved_argv
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    rc, bx, rx, px = res["X"]
    s = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}
    chk(f"main arm X: 4 requests, thinking off (chat_template_kwargs {bx[0].get('chat_template_kwargs')}, no reasoning_effort), "
        f"T 1.0 / 0.95 / 20 / min-p 0.05, presence 0, max_tokens 512, seeds {[b['seed'] for b in bx]}",
        rc == 0 and len(bx) == 4 and all(b.get("chat_template_kwargs") == {"enable_thinking": False} and "reasoning_effort" not in b
                                         and all(b[k] == v for k, v in s.items()) and b["presence_penalty"] == 0.0
                                         and b["max_tokens"] == 512 for b in bx)
        and [b["seed"] for b in bx] == [3_000_000, 3_001_000, 3_002_000, 3_003_000] and px["thinking"] is False)
    for arm in ("TX", "TR1"):
        rc, bt, rt, pt = res[arm]
        base = SEED_BASE[arm]
        chk(f"thinking arm {arm}: 4 requests, reasoning_effort {bt[0].get('reasoning_effort')!r}, no enable_thinking false, "
            f"the same sampling, seeds {[b['seed'] for b in bt]}, plan thinking {pt['thinking']} effort {pt['effort']}",
            rc == 0 and len(bt) == 4 and all(b.get("reasoning_effort") == "low" and "chat_template_kwargs" not in b
                                             and "thinking" not in b and all(b[k] == v for k, v in s.items())
                                             and b["max_tokens"] == 512 for b in bt)
            and [b["seed"] for b in bt] == [base + 1000 * i for i in range(4)] and pt["thinking"] is True and pt["effort"] == "low")
    chk(f"drafts summed over the engine passes: {rx[0]['drafts']} (want offered 8, kept 6, per_pos [[1, 4, 6], [2, 2, 2]], 2 lines)",
        rx[0]["drafts"] == {"offered": 8, "kept": 6, "per_pos": [[1, 4, 6], [2, 2, 2]], "draft_lines": 2} and rx[0]["engine_passes"] == 2)
    chk(f"SAMPLED_THINK=1 with a main role is refused (exit {bad})", bad == 1)
    allseeds = [SEED_BASE[a] + 1000 * qi + rnd for a in SEED_BASE for qi in range(4) for rnd in range(8)]
    chk(f"no seed shared between any two roles (K <= 8): {len(allseeds)} seeds, {len(set(allseeds))} distinct", len(set(allseeds)) == len(allseeds))
    chk(f"constants agree with sampled.py: effort {THINK_EFFORT} = {SA.THINK_EFFORT}, TR1 / TX = {SA.THINK_SEED_BASE}",
        THINK_EFFORT == SA.THINK_EFFORT and SEED_BASE["TR1"] == SA.THINK_SEED_BASE["R1"] and SEED_BASE["TX"] == SA.THINK_SEED_BASE["X"])
    print("CLIENT SELFTEST " + ("OK" if ok else "FAILED"))
    return 0 if ok else 1


HERE_SAMPLED = "/home/USER/ai-speed-testing/strata-compare/work/ds41/gate/sampled"


if __name__ == "__main__":
    sys.exit(main())
