#!/usr/bin/env python3
"""vision_check.py URL IMAGE OUT_PREFIX - round 22 pictures step 2 (the user, 10-19: "Test with a screenshot: time from
paste to answer, and whether the description is right").

Sends the picture the way Jan does (OpenAI chat completions, streamed, a text part + an image_url data URI, the
config's sampling, reasoning effort medium) twice on fresh conversations: the first read encodes the picture on the
CPU reader, the second may reuse the server's encoded copy. Per request: seconds to the first answer token and to the
end, tokens, and the answer (OUT_PREFIX-<n>.txt) - judged by hand against the picture. Also the reader process's RSS.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

URL, IMG, OUT = sys.argv[1].rstrip("/"), Path(sys.argv[2]), sys.argv[3]
ASK = "I pasted a screenshot. What does it show? Describe it briefly, and give the key numbers you can read."


def reader_rss_mib() -> list[int]:
    out = subprocess.run(["ps", "-C", "strata-vision", "-o", "rss="], capture_output=True, text=True).stdout.split()
    return [int(x) // 1024 for x in out]


def ask(n: int) -> dict:
    mime = mimetypes.guess_type(IMG.name)[0] or "image/png"
    uri = f"data:{mime};base64," + base64.b64encode(IMG.read_bytes()).decode()
    body = {"model": "x", "stream": True, "reasoning_effort": "medium", "max_tokens": 2048,
            "messages": [{"role": "user", "content": [{"type": "text", "text": ASK},
                                                      {"type": "image_url", "image_url": {"url": uri}}]}]}
    req = urllib.request.Request(URL + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    first = None
    text, think = [], []
    usage = {}
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=900) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line == "data: [DONE]":
                continue
            d = json.loads(line[5:])
            usage = d.get("usage") or usage
            for ch in d.get("choices") or []:
                delta = ch.get("delta") or {}
                if delta.get("reasoning_content"):
                    think.append(delta["reasoning_content"])
                if delta.get("content"):
                    first = first or time.time()
                    text.append(delta["content"])
    t1 = time.time()
    answer = "".join(text)
    Path(f"{OUT}-{n}.txt").write_text(answer)
    return {"n": n, "first_answer_token_s": round((first or t1) - t0, 1), "total_s": round(t1 - t0, 1),
            "thinking_chars": len("".join(think)), "answer_chars": len(answer), "usage": usage}


if __name__ == "__main__":
    print(f"reader RSS before: {reader_rss_mib()} MiB")
    for n in (1, 2):
        print(json.dumps(ask(n)))
    print(f"reader RSS after: {reader_rss_mib()} MiB")
