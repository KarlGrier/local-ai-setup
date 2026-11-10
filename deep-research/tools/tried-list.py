#!/usr/bin/env python3
"""tried-list.py - phase 4 item 4 (the user, 10-23: "Continue with the 'tried / ruled out' list next"): build the "tried
/ ruled out" list for a set of the user's files BEFORE a measured run, so its extraction calls are not part of that
run's calls and tokens. Same code as inside deep research (local_deep_research/deep/tried.py, LDR_DEEP_TRIED=1): one
low-effort call per ~60K-character part of the files (at most 30 entries each), then medium-effort merge calls
(batched when long), through strata-proxy (8090), holding
run/bench.lock like the other measurement tools. The list is cached by the files' contents in run/tried/<key>.json and
.md; a run with the same files then loads it.

  tried-list.py FILE [FILE ...] [--force]      (run it with the LDR venv: .venv/bin/python tools/tried-list.py ...)
"""
from __future__ import annotations

import argparse
import fcntl
import json
import sys
import time
from pathlib import Path

import requests

WS = Path("/home/USER/ai/deep-research")
PROXY = "http://127.0.0.1:8090"
NOPROXY = {"http": None, "https": None}


def llm(prompt: str, max_tokens: int, effort: str, calls: list) -> tuple[str, str | None]:
    body = {"model": "strata", "messages": [{"role": "user", "content": prompt}], "stream": True, "temperature": 1.0,
            "max_tokens": max_tokens, "reasoning_effort": effort, "stream_options": {"include_usage": True}}
    t0 = time.time()
    text, usage, finish = [], None, None
    with requests.post(PROXY + "/v1/chat/completions", json=body, stream=True, timeout=3600, proxies=NOPROXY) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith(b"data: ") or line == b"data: [DONE]":
                continue
            d = json.loads(line[6:])
            if d.get("error"):
                raise RuntimeError(str(d["error"])[:300])
            usage = d.get("usage") or usage
            for ch in d.get("choices") or []:
                text.append((ch.get("delta") or {}).get("content") or "")
                finish = ch.get("finish_reason") or finish
    calls.append({"seconds": round(time.time() - t0, 1), "effort": effort, "finish": finish,
                  "prompt_tokens": (usage or {}).get("prompt_tokens"), "completion_tokens": (usage or {}).get("completion_tokens")})
    print(f"  call {len(calls)}: {calls[-1]}", flush=True)
    return "".join(text).strip(), finish


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--force", action="store_true", help="build again even if the list is cached")
    a = ap.parse_args()
    from local_deep_research.deep import tried

    files = [str(Path(f).resolve()) for f in a.files]
    k = tried.key(files)
    cached = tried.CACHE / f"{k}.json"
    if cached.exists() and not a.force:
        res = json.loads(cached.read_text())
        print(f"cached: {cached} ({len(res['entries'])} entries, built {res['built']})")
        return
    if a.force and cached.exists():
        cached.rename(cached.with_suffix(f".json.old-{int(time.time())}"))
    lock = open(WS / "run" / "bench.lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    calls: list = []
    res = tried.get(files, lambda p, mt, eff: llm(p, mt, eff, calls))
    lock.close()
    if not res or not res.get("entries"):
        raise SystemExit("no entries extracted - nothing cached")
    (tried.CACHE / f"{k}.calls.json").write_text(json.dumps(calls, indent=1))
    pt = sum(c.get("prompt_tokens") or 0 for c in calls)
    ct = sum(c.get("completion_tokens") or 0 for c in calls)
    print(f"tried list {k}: {len(res['entries'])} entries from {res['parts']} parts ({res['parts_failed']} failed, "
          f"{res['raw_entries']} before the merge, {res['mode']}), {len(calls)} calls, {pt} prompt / {ct} generated "
          f"tokens, {res['seconds']} s -> {tried.CACHE / (k + '.md')}")


if __name__ == "__main__":
    sys.exit(main())
