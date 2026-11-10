"""Streaming OpenAI-compatible chat client with client-side timing (identical for llama-server and Strata)."""
from __future__ import annotations

import json
import time

import requests


def vmstat() -> dict:
    out = {}
    for line in open("/proc/vmstat"):
        k, v = line.split()
        if k in ("pswpin", "pswpout"):
            out[k] = int(v)
    return out


def stream_chat(base: str, body: dict, timeout: float = 7200, keep_pieces: bool = False) -> dict:
    """POST /v1/chat/completions with stream=True. Returns timings measured on this side of the socket:
    ttft_s = first reasoning/content delta, decode_s = last delta - first delta, plus the server's usage/timings."""
    body = dict(body, stream=True, stream_options={"include_usage": True})
    sw0 = vmstat()
    t0 = time.perf_counter()
    t_first = t_last = None
    reasoning, content, pieces = [], [], []
    usage = timings = finish = None
    n_chunks = 0
    err = None
    try:
        with requests.post(base.rstrip("/") + "/v1/chat/completions", json=body, stream=True, timeout=timeout) as r:
            if r.status_code != 200:
                return {"error": f"HTTP {r.status_code}: {r.text[:500]}", "t_total_s": time.perf_counter() - t0}
            for raw in r.iter_lines(decode_unicode=False):
                if not raw or raw.startswith(b":"):
                    continue
                if not raw.startswith(b"data: "):
                    continue
                data = raw[6:]
                if data == b"[DONE]":
                    break
                c = json.loads(data)
                if c.get("usage"):
                    usage = c["usage"]
                if c.get("timings"):
                    timings = c["timings"]
                for ch in c.get("choices") or []:
                    d = ch.get("delta") or {}
                    rc, cc = d.get("reasoning_content") or "", d.get("content") or ""
                    if rc or cc:
                        now = time.perf_counter()
                        if t_first is None:
                            t_first = now
                        t_last = now
                        n_chunks += 1
                        if rc:
                            reasoning.append(rc)
                        if cc:
                            content.append(cc)
                        if keep_pieces:
                            pieces.append((round(now - t0, 4), "r" if rc else "c", rc or cc))
                    if ch.get("finish_reason"):
                        finish = ch["finish_reason"]
    except Exception as e:  # noqa: BLE001 - recorded, the run is marked invalid
        err = repr(e)
    t_end = time.perf_counter()
    sw1 = vmstat()
    rec = {
        "t_total_s": t_end - t0,
        "ttft_s": (t_first - t0) if t_first else None,
        "decode_s": (t_last - t_first) if t_first and t_last else None,
        "n_chunks": n_chunks,
        "usage": usage, "server_timings": timings, "finish_reason": finish,
        "reasoning": "".join(reasoning), "content": "".join(content),
        "swap_in_pages": sw1["pswpin"] - sw0["pswpin"], "swap_out_pages": sw1["pswpout"] - sw0["pswpout"],
    }
    if err:
        rec["error"] = err
    if keep_pieces:
        rec["pieces"] = pieces
    u = usage or {}
    ct, pt = u.get("completion_tokens"), u.get("prompt_tokens")
    rec["completion_tokens"], rec["prompt_tokens"] = ct, pt
    if ct and rec["decode_s"] and ct > 1:
        rec["decode_tps"] = (ct - 1) / rec["decode_s"]
    if pt and rec["ttft_s"]:
        rec["prompt_tps_client"] = pt / rec["ttft_s"]
    if timings:
        rec["server_prompt_tps"] = timings.get("prompt_per_second")
        rec["server_decode_tps"] = timings.get("predicted_per_second")
        rec["server_prompt_n"] = timings.get("prompt_n")
        rec["server_cache_n"] = timings.get("cache_n")
    return rec
