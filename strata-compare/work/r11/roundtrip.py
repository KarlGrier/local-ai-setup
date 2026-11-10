#!/usr/bin/env python3
"""roundtrip.py SESSION CASE — round 7 copy (results -> results/r7; the forced tokens X reused from work/r5): does a chat survive the chat cache's park / resume / edit exactly?

Needs the MEASUREMENT build (branch r5-meas: engine key force=N, server fields strata_force_ids / strata_return_ids)
started from configs/R5-meas.json (--adapt-swaps 0 = a static expert set; STRATA_STATE_HASH=1 = the engine logs a
fingerprint of every part of the session after each request). Requests are shaped like the chat page's
(reasoning_effort high, 0.6/0.95/20; the config adds min_p 0.05). The chat is built turn by turn with fixed assistant
texts (as a client sends its history), then the SAME 1,536 tokens X are teacher-forced after it:

  gen      build, then sample X (1,536 tokens) after the last user turn        -> work/r5/rt-X-CASE.json
  direct   build, force X                                                        (reference; run twice = residual)
  park     build, a 64K paste in chat C, a short chat B, force X (= resume A from the chat cache),
           then force X after an EDITED turn 2 (resume from the checkpoint before it)
  editref  turn 1 only, then force X after the edited chat (= the edit's reference: same checkpoint, same reads)

CASE: small (~6.6K-token chat: part 1 of the multiturn document in two halves) or 40k (the 7-turn multiturn chat).
Per forced request the engine log gives FORCE (pos target argmax nll), FDRAFT (drafter guesses after each window) and
STATE_HASH lines; they are saved to results/r5/rt-SESSION-CASE.json (compare with rt_compare.py).
"""
import json
import re
import sys
import time
import urllib.request

WS = "/home/USER/ai-speed-testing/strata-compare"
BASE = "http://127.0.0.1:8081"
ELOG = __import__("os").environ.get("ELOG", f"{WS}/logs/r11/engine-R7-meas-rt.log")
PAGE = {"reasoning_effort": "high", "temperature": 0.6, "top_p": 0.95, "top_k": 20, "stream": False}


def post(body, timeout=7200):
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def log_size():
    try:
        with open(ELOG, "rb") as f:
            f.seek(0, 2)
            return f.tell()
    except OSError:
        return 0


def log_since(off):
    with open(ELOG, "rb") as f:
        f.seek(off)
        return f.read().decode("utf-8", "replace")


def ask(label, msgs, **kw):
    off = log_size()
    t0 = time.time()
    r = post({**PAGE, "messages": msgs, **kw})
    dt = time.time() - t0
    time.sleep(0.5)                     # the engine's stderr lines after DONE
    txt = log_since(off)
    m = re.findall(r"prompt (\d+) tokens = (\d+) reused \+ (\d+) read", txt)
    events = [ln.split("strata serve: ", 1)[1] for ln in txt.splitlines()
              if "chat cache:" in ln or "conversation cache:" in ln or "FORCE begin" in ln or "FORCE done" in ln]
    print(f"  {label}: {dt:.2f} s, prompt/reused/read {m[-1] if m else '?'}, {'; '.join(events)[:300]}", flush=True)
    return r, txt


def parse_force(txt):
    force = [ln.split()[1:] for ln in txt.splitlines() if ln.startswith("FORCE ")]
    drafts = [ln.split()[1:] for ln in txt.splitlines() if ln.startswith("FDRAFT ")]
    sh = re.findall(r"STATE_HASH (.*)", txt)
    done = re.findall(r"FORCE done: (.*)", txt)
    return {"pos": [int(f[0]) for f in force], "target": [int(f[1]) for f in force],
            "argmax": [int(f[2]) for f in force], "nll": [float(f[3]) for f in force],
            "drafts": [" ".join(d) for d in drafts], "state_hash": sh[-1] if sh else None,
            "summary": done[-1] if done else None,
            "prompt": re.findall(r"prompt (\d+) tokens = (\d+) reused \+ (\d+) read", txt)[-1:]}


def chat_small(edit=False):
    mt = json.load(open(f"{WS}/prompts/multiturn.json"))["turns"]
    part = mt[0]["user"].replace("[Chat mt-7f3a] ", "")
    half = len(part) // 2
    cut = part.rfind("\n", 0, half) + 1 or half
    u1 = "[Chat rt-small] Here is the first half of a document:\n\n" + part[:cut] + \
         "\n\nList the file names or section headers you see, briefly."
    u2 = "Here is the second half:\n\n" + part[cut:] + "\n\nSame for this half, briefly."
    if edit:
        u2 = u2.replace("Here is the second half:", "Here is the second half (read it carefully):", 1)
    a1 = "In the first half I see build and configuration material: " + mt[0]["assistant"][:160]
    a2 = "The second half continues it; " + mt[1]["assistant"][:160]
    u3 = "Now write a detailed, section-by-section summary of the whole document (at least 1,500 words), then say what kind of project it belongs to."
    return [[{"role": "user", "content": u1}],
            [{"role": "user", "content": u1}, {"role": "assistant", "content": a1}, {"role": "user", "content": u2}],
            [{"role": "user", "content": u1}, {"role": "assistant", "content": a1}, {"role": "user", "content": u2},
             {"role": "assistant", "content": a2}, {"role": "user", "content": u3}]]


def chat_40k(edit=False):
    mt = json.load(open(f"{WS}/prompts/multiturn.json"))["turns"]
    hist, steps = [], []
    for k, t in enumerate(mt):
        u = t["user"].replace("[Chat mt-7f3a]", "[Chat rt-40k]")
        if edit and k == 1:
            u = u.replace("Part 2 of the document:", "Part 2 of the document (read it carefully):", 1)
        hist.append({"role": "user", "content": u})
        steps.append(list(hist))
        hist.append({"role": "assistant", "content": t["assistant"]})
    hist.append({"role": "user", "content": "Now write a detailed, section-by-section summary of the whole document (at least 1,500 words), then say what kind of project it belongs to."})
    steps.append(list(hist))
    return steps


def other_chats():
    sp = json.load(open(f"{WS}/prompts/speed.json"))
    c = next(p for p in sp if p["size"] == "64k" and p["rep"] == 0)["messages"]
    b = json.load(open(f"{WS}/prompts/correctness.json"))[1]["messages"]
    return c, b


def main():
    session, case = sys.argv[1], sys.argv[2]
    steps = chat_small() if case == "small" else chat_40k()
    esteps = chat_small(edit=True) if case == "small" else chat_40k(edit=True)
    xpath = f"{WS}/work/r5/rt-X-{case}.json"
    out = {"session": session, "case": case, "forced": {}}
    print(f"== {time.strftime('%H:%M:%S')} roundtrip {session} {case}", flush=True)
    if session == "editref":
        ask("turn 1", steps[0], max_tokens=8)
    else:
        for k, msgs in enumerate(steps[:-1]):
            ask(f"turn {k + 1}", msgs, max_tokens=8)
    if session == "gen":
        for attempt in range(4):                   # sampled: an answer can end early; X must be 1,536 tokens
            r, _ = ask("sample X", steps[-1], max_tokens=1536, strata_return_ids=True)
            ids = r["strata_ids"]
            if len(ids) >= 1536:
                break
            print(f"  X only {len(ids)} tokens, sampling again", flush=True)
        json.dump(ids, open(xpath, "w"))
        print(f"  X: {len(ids)} tokens -> {xpath}", flush=True)
        return
    X = json.load(open(xpath))
    if len(X) < 1536:
        raise SystemExit(f"X has only {len(X)} tokens (need 1,536): run the gen session again")
    if session == "park":
        c, b = other_chats()
        ask("chat C: 64K paste", c, max_tokens=8)
        ask("chat B: short", b, max_tokens=8)
    if session in ("direct", "park"):
        _, txt = ask("force X after the chat", steps[-1], strata_force_ids=X)
        out["forced"]["resume"] = parse_force(txt)
    if session in ("park", "editref"):
        _, txt = ask("force X after the edited chat", esteps[-1], strata_force_ids=X)
        out["forced"]["edit"] = parse_force(txt)
    tag = sys.argv[3] if len(sys.argv) > 3 else session
    json.dump(out, open(f"{WS}/results/r11/rt-{tag}-{case}.json", "w"))
    for k, v in out["forced"].items():
        print(f"  {k}: {v['summary']}; prompt {v['prompt']}; state {v['state_hash'][:120] if v['state_hash'] else None}")


if __name__ == "__main__":
    main()
