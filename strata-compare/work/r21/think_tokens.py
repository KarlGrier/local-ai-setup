#!/usr/bin/env python3
"""think_tokens.py - r21 item 4, the token gate: send the same recorded requests, greedy, to a test server on 8081 and
keep what comes back.  Run once against C*18 (TK18A) and once against C*18 + the think-fence fix (TK18B); then
`think_tokens.py compare A_DIR B_DIR A_SERVER_LOG B_SERVER_LOG` checks that every raw output (the server's
STRATA_DEBUG "[strata] raw:" line, the decoded generated ids) and every completion token count are identical, and
lists where the reasoning / answer / tool-call split differs.

    think_tokens.py send OUT_DIR
    think_tokens.py compare A_DIR B_DIR A_SERVER_LOG B_SERVER_LOG

The requests: the 7 turns whose tool call the quoted `</think>` lost in the usability round (6 chat completions, 1
Responses API) and 3 ordinary turns, as the harness sent them, with temperature 0 and at most 3000 new tokens.
"""
import gzip
import json
import sys
import time
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
TURNS = WS / "logs/usability/turns"
PICK = [("opencode-rt_effort-r1", 16), ("opencode-rt_effort-r2", 20), ("dsh-minimal-rt_effort-r1", 20),
        ("dsh-minimal-rt_effort-r2", 27), ("dsh-standard-rt_effort-r2", 40), ("dsh-ptc-rt_effort-r1", 38),
        ("codex-rt_effort-r1", 36),
        ("opencode-a1_inventory-r1", 5), ("dsh-minimal-a2_textstats-r1", 6), ("codex-a3_cronlite-r1", 4)]
MAX_NEW = 3000


def send(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    for lab, n in PICK:
        d = TURNS / lab
        idx = {e["n"]: e for e in (json.loads(l) for l in open(d / "index.jsonl"))}
        path = idx[n]["path"]
        req = json.loads(gzip.open(d / f"{n:04d}.req.json.gz").read())
        req["temperature"] = 0
        req["stream"] = True
        if path.endswith("/responses"):
            req["max_output_tokens"] = MAX_NEW
        else:
            req.pop("max_completion_tokens", None)
            req["max_tokens"] = MAX_NEW
            req["stream_options"] = {"include_usage": True}
        t0 = time.time()
        r = urllib.request.urlopen(urllib.request.Request(
            "http://127.0.0.1:8081" + path, json.dumps(req).encode(), {"Content-Type": "application/json"}), timeout=1800)
        raw = r.read().decode()
        (out / f"{lab}-{n}.sse").write_text(raw)
        s = summarize(raw)
        s.update(label=f"{lab}-{n}", path=path, wall_s=round(time.time() - t0, 1))
        (out / f"{lab}-{n}.json").write_text(json.dumps(s, indent=1))
        print(json.dumps({k: s[k] for k in ("label", "completion_tokens", "finish", "calls", "reasoning_chars",
                                            "answer_chars", "wall_s")}), flush=True)


def summarize(raw):
    reasoning = answer = ""
    calls, finish, ctoks = [], None, None
    tc = {}
    for line in raw.splitlines():
        if not line.startswith("data:") or "[DONE]" in line:
            continue
        ev = json.loads(line[5:])
        t = ev.get("type", "")
        if t == "response.output_text.delta":
            answer += ev["delta"]
        elif t.startswith("response.reasoning") and t.endswith(".delta"):
            reasoning += ev["delta"]
        elif t == "response.output_item.done" and ev["item"].get("type") == "function_call":
            calls.append(ev["item"]["name"])
        elif t == "response.completed":
            finish = ev["response"].get("status")
            ctoks = (ev["response"].get("usage") or {}).get("output_tokens")
        for ch in ev.get("choices", []):
            dl = ch.get("delta", {})
            reasoning += dl.get("reasoning_content") or ""
            answer += dl.get("content") or ""
            for c in dl.get("tool_calls") or []:
                tc.setdefault(c.get("index", 0), "")
                tc[c.get("index", 0)] += (c.get("function") or {}).get("name") or ""
            finish = ch.get("finish_reason") or finish
        if ev.get("usage"):
            ctoks = ev["usage"].get("completion_tokens", ctoks)
    calls += [tc[k] for k in sorted(tc)]
    return {"completion_tokens": ctoks, "finish": finish, "calls": calls, "reasoning_chars": len(reasoning),
            "answer_chars": len(answer), "reasoning": reasoning, "answer": answer}


def raws(log):
    out = []
    for line in open(log, errors="replace"):
        if line.startswith("[strata] raw: "):
            out.append(line[len("[strata] raw: "):].rstrip("\n"))
    return out


def compare(a_dir, b_dir, a_log, b_log):
    ra, rb = raws(a_log), raws(b_log)
    print(f"raw outputs: A {len(ra)}, B {len(rb)}; identical: {sum(x == y for x, y in zip(ra, rb))} of {max(len(ra), len(rb))}")
    same_tokens = 0
    for lab, n in PICK:
        a = json.loads((Path(a_dir) / f"{lab}-{n}.json").read_text())
        b = json.loads((Path(b_dir) / f"{lab}-{n}.json").read_text())
        same_tokens += a["completion_tokens"] == b["completion_tokens"]
        split = "same split" if (a["calls"], a["reasoning"], a["answer"]) == (b["calls"], b["reasoning"], b["answer"]) else \
            f"SPLIT DIFFERS: A calls {a['calls']} reasoning {a['reasoning_chars']} answer {a['answer_chars']} | " \
            f"B calls {b['calls']} reasoning {b['reasoning_chars']} answer {b['answer_chars']}"
        print(f"{lab}-{n}: tokens A {a['completion_tokens']} B {b['completion_tokens']}, finish {a['finish']}/{b['finish']}; {split}")
    print(f"completion tokens identical: {same_tokens} of {len(PICK)}")
    ok = ra == rb and len(ra) >= len(PICK) and same_tokens == len(PICK)
    print("TOKEN GATE", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    if sys.argv[1] == "send":
        send(Path(sys.argv[2]))
    else:
        compare(*sys.argv[2:6])
