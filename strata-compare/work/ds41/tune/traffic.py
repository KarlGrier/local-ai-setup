#!/usr/bin/env python3
"""traffic.py BASE OUTDIR - 10-24 DeepSeek-V4.1 tuning round, item B.8 (the user: "Hot-expert profile: build one from my
kind of traffic (routing traces from chat, code and research-style prompts, not the test prompts) and compare it with
the shipped profile"). Sends chat, code and research-style requests to a running server whose engine counts every
routed pick into its --expert-profile file (written back after every request; the arm starts it from an all-zero file).
  chat (8):     everyday questions in the user's areas (PC hardware, Linux, local models), written here
  code (8):     scripts, fixes and reviews; some quote public Strata source (strata-v024's serve/ and tools/)
  research (8): LLM calls captured in our own phase 4 benchmark runs (results/bench2/runs/*-p4s3/*/capture: extract,
                verify, report and agent calls, 10-60K characters) - not the speed test's prompts (W1-W3, P4K, P20K;
                checked: none of them shares its first 2,000 characters with a W prompt)
Thinking effort "high" (the template's default, what a chat client gets when it sends none), T 1.0 / 0.95 / 20 / min-p 0.05, a fresh nonce in every request.
Records -> OUTDIR/traffic.jsonl.
"""
import glob
import json
import random
import sys

sys.path.insert(0, "/home/USER/ai-speed-testing/basalt-ab/scripts")
import abrun  # noqa: E402

V24 = "/home/USER/ai-speed-testing/strata-compare/strata-v024"
RUNS = "/home/USER/ai/deep-research/results/bench2/runs"

CHAT = [
    "My PC has an RTX 5080 16 GB and an RTX 4060 Ti 8 GB on a chipset x4 link. For running a large mixture-of-experts model, what limits speed more: the x4 link or system RAM bandwidth? Explain briefly.",
    "What's the practical difference between DDR5-6000 and DDR5-6400 for a 96 GB kit on a Ryzen 9 9950X3D, and how would I check if 6400 is stable?",
    "Explain how top-k routing in a mixture-of-experts layer works, and why some experts get used much more than others.",
    "How do I make a systemd user service restart automatically after a crash, but give up after five failures in ten minutes?",
    "My NVMe SSD reads at 14 GB/s sequentially. Why might random 3 MB reads with O_DIRECT be much slower, and what queue depth should I use?",
    "Give me a short checklist for deciding whether a new GPU driver version is safe to install on a machine that runs long LLM benchmarks overnight.",
    "What is speculative decoding, and why does exact speculative sampling keep the target model's output distribution?",
    "Summarise the trade-offs between keeping a long chat's KV cache in RAM versus re-reading the conversation on every turn.",
]


def src(path, start, n):
    try:
        lines = open(f"{V24}/{path}", encoding="utf-8", errors="replace").read().splitlines()
        return "\n".join(lines[start:start + n])
    except OSError:
        return ""


CODE = [
    "Write a Python script that tails a log file, and sends a desktop notification with notify-send whenever a line matches a regular expression given on the command line. Handle log rotation.",
    "Write a bash function that waits until a TCP port on 127.0.0.1 is free, with a timeout, without using sleep loops longer than one second.",
    "Write a CUDA kernel that computes a numerically stable softmax over each row of a float matrix with up to 8192 columns, one block per row.",
    "Here is a Python function. Explain what it does and point out any bugs or edge cases:\n\n```python\n" + src("serve/frontend.py", 130, 60) + "\n```",
    "Review this code for correctness and suggest a cleaner version:\n\n```python\n" + src("serve/server.py", 3460, 70) + "\n```",
    "Write a small C++17 class for a fixed-capacity LRU cache keyed by uint32 with O(1) get and put, and a short test.",
    "Convert this shell pipeline into a robust Python function with error handling: `ss -ltnp | grep 127.0.0.1:8085 | sed 's/.*pid=\\([0-9]*\\),.*/\\1/'`",
    "Write a Python script that reads a binary file of little-endian uint32 counts shaped [40][384], and prints for each layer the 10 largest entries and the share of the total they hold.",
]


def research(rng):
    w = json.load(open(abrun.WL))
    wheads = [m["content"][:2000] for x in w["normal"] for m in x["messages"] if isinstance(m.get("content"), str)]
    pool = {"extract": [], "verify": [], "report": [], "agent": []}
    for f in sorted(glob.glob(f"{RUNS}/hard-screen-deep-p4s3/*/capture/calls.jsonl") + glob.glob(f"{RUNS}/screen-deep-p4s3/*/capture/calls.jsonl")):
        for line in open(f):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            m = d.get("messages") or []
            if not m or not all(isinstance(x.get("content"), str) for x in m) or m[-1].get("role") != "user":
                continue
            n = sum(len(x["content"]) for x in m)
            if d.get("cls") in pool and 10000 <= n <= 60000 and not any(x["content"][:2000] in wheads for x in m):
                pool[d["cls"]].append({"messages": [{"role": x["role"], "content": x["content"]} for x in m],
                                       "tools": d.get("tools") if d.get("cls") == "agent" else None, "cls": d["cls"]})
    out = []
    for cls, k in (("extract", 4), ("verify", 2), ("report", 1), ("agent", 1)):
        out += rng.sample(pool[cls], min(k, len(pool[cls])))
    return out


def main():
    base, out = sys.argv[1], sys.argv[2]
    rng = random.Random(1024)
    jobs = [{"id": f"chat{i}", "messages": [{"role": "user", "content": t}], "max_tokens": 384} for i, t in enumerate(CHAT)]
    jobs += [{"id": f"code{i}", "messages": [{"role": "user", "content": t}], "max_tokens": 512} for i, t in enumerate(CODE)]
    for i, r in enumerate(research(rng)):
        j = {"id": f"research{i}-{r['cls']}", "messages": r["messages"], "max_tokens": 384}
        if r["tools"]:
            j["tools"] = r["tools"]
        jobs.append(j)
    print(f"{len(jobs)} requests", flush=True)
    for j in jobs:
        j["effort"] = "high"                              # the template's default (75) when a client sends none
        rec = abrun.one(base, "traffic", dict(j, thinking=True), abrun.NORMAL, {}, 0, f"{out}/traffic.jsonl")
        print(f"  {j['id']}: {rec.get('prompt_tokens')} prompt + {rec.get('completion_tokens')} tokens", flush=True)


if __name__ == "__main__":
    main()
