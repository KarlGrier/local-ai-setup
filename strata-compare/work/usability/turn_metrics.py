#!/usr/bin/env python3
"""turn_metrics.py - per-request and per-run numbers from turnlog.py's recordings (usability round).

    turn_metrics.py LABEL_DIR [--json]

For every request: the API (chat / responses), prompt tokens and how many of them Strata reused from its cache (the
rest it had to read again), output tokens (reasoning included), finish reason, tool calls and whether their arguments
parse as JSON, and two failure signs:
  * unparsed tool call: the answer's text holds a tool-call markup the server did not turn into a call
    ("<tool_call>", "<function=", '"name":' + '"arguments"' in a fenced block)
  * early end (r04-style): the turn ended "stop" with no text and no tool call, or "length" well below its cap
"""
import gzip
import json
import re
import sys
from pathlib import Path

UNPARSED = re.compile(r"<tool_call>|</tool_call>|<function=|<\|tool_call|\{\s*\"name\"\s*:\s*\"[a-z_]+\"\s*,\s*\"arguments\"")


def sse_events(raw: str):
    for line in raw.splitlines():
        if line.startswith("data: ") and line[6:].strip() not in ("", "[DONE]"):
            try:
                yield json.loads(line[6:])
            except json.JSONDecodeError:
                pass


def one(req: dict, raw: str, path: str) -> dict:
    out = {"api": "responses" if "responses" in path else "chat", "tool_calls": 0, "bad_args": 0, "text": "",
           "reasoning_chars": 0, "finish": None, "prompt": None, "cached": None, "completion": None}
    cap = req.get("max_completion_tokens") or req.get("max_tokens") or req.get("max_output_tokens")
    out["cap"] = cap
    if not req.get("stream", False):
        try:
            ev = [json.loads(raw)]
        except json.JSONDecodeError:
            ev = []
    else:
        ev = list(sse_events(raw))
    if out["api"] == "chat":
        calls = {}
        for e in ev:
            for ch in e.get("choices", []):
                d = ch.get("delta") or ch.get("message") or {}
                out["text"] += d.get("content") or ""
                out["reasoning_chars"] += len(d.get("reasoning_content") or "")
                for tc in d.get("tool_calls") or []:
                    c = calls.setdefault(tc.get("index", len(calls)), {"args": ""})
                    c["args"] += (tc.get("function") or {}).get("arguments") or ""
                if ch.get("finish_reason"):
                    out["finish"] = ch["finish_reason"]
            u = e.get("usage")
            if u:
                out["prompt"], out["completion"] = u.get("prompt_tokens"), u.get("completion_tokens")
                out["cached"] = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        out["tool_calls"] = len(calls)
        for c in calls.values():
            try:
                json.loads(c["args"] or "{}")
            except json.JSONDecodeError:
                out["bad_args"] += 1
    else:
        for e in ev:
            t = e.get("type", "")
            if t == "response.output_text.delta":
                out["text"] += e.get("delta") or ""
            elif t == "response.reasoning_text.delta":
                out["reasoning_chars"] += len(e.get("delta") or "")
            elif t in ("response.completed", "response.incomplete", "response.failed"):
                r = e.get("response") or {}
                out["finish"] = r.get("status")
                if r.get("incomplete_details"):
                    out["finish"] += ":" + str((r["incomplete_details"] or {}).get("reason"))
                u = r.get("usage") or {}
                out["prompt"], out["completion"] = u.get("input_tokens"), u.get("output_tokens")
                out["cached"] = (u.get("input_tokens_details") or {}).get("cached_tokens", 0)
                for item in r.get("output") or []:
                    if item.get("type") == "function_call":
                        out["tool_calls"] += 1
                        try:
                            json.loads(item.get("arguments") or "{}")
                        except json.JSONDecodeError:
                            out["bad_args"] += 1
    out["unparsed_call"] = bool(UNPARSED.search(out["text"]))
    fin = (out["finish"] or "")
    out["early_end"] = bool((fin in ("stop", "completed") and not out["text"].strip() and not out["tool_calls"])
                            or (fin.startswith("length") or "max_output" in fin) and cap and out["completion"]
                            and out["completion"] < cap - 64)
    out["text_chars"] = len(out.pop("text"))
    return out


def run_metrics(d: Path, skip_titles=True):
    idx = {}
    if (d / "index.jsonl").exists():
        for line in (d / "index.jsonl").read_text().splitlines():
            r = json.loads(line)
            idx[r["n"]] = r
    turns = []
    for f in sorted(d.glob("*.req.json.gz")):
        n = int(f.name[:4])
        raw_req = gzip.open(f).read()
        try:
            req = json.loads(raw_req or b"{}")
        except json.JSONDecodeError:
            req = {}
        i = idx.get(n, {})
        rf = d / f"{n:04d}.resp.gz"
        raw = gzip.open(rf).read().decode("utf-8", "replace") if rf.exists() else ""
        if i.get("method") == "GET" or not req:
            continue
        t = one(req, raw, i.get("path", ""))
        t.update(n=n, t=i.get("t"), wall_s=i.get("wall_s"), status=i.get("status"))
        sysmsg = json.dumps((req.get("messages") or req.get("input") or [{}])[0])[:300]
        t["title"] = bool(re.search(r"title generator|concise title", sysmsg, re.I)) or (req.get("max_completion_tokens") == 64)
        turns.append(t)
    work = [t for t in turns if not (skip_titles and t["title"])]
    s = lambda k: sum((t.get(k) or 0) for t in work)
    reread = [max(0, (t["prompt"] or 0) - (t["cached"] or 0)) for t in work]
    summary = {"requests": len(turns), "title_requests": len(turns) - len(work), "steps": len(work),
               "prompt_tokens": s("prompt"), "cached_tokens": s("cached"), "output_tokens": s("completion"),
               "reread_tokens": sum(reread), "reread_per_turn_median": sorted(reread)[len(reread) // 2] if reread else 0,
               "reread_per_turn_max": max(reread) if reread else 0,
               "max_prompt": max(((t["prompt"] or 0) for t in work), default=0),
               "tool_calls": s("tool_calls"), "bad_tool_args": s("bad_args"),
               "unparsed_calls": sum(t["unparsed_call"] for t in work), "early_ends": sum(t["early_end"] for t in work),
               "http_errors": sum(1 for t in work if (t["status"] or 200) >= 400),
               "model_wall_s": round(sum((t["wall_s"] or 0) for t in work), 1),
               "finishes": {}}
    for t in work:
        summary["finishes"][t["finish"] or "?"] = summary["finishes"].get(t["finish"] or "?", 0) + 1
    return summary, turns


if __name__ == "__main__":
    d = Path(sys.argv[1])
    summary, turns = run_metrics(d)
    if "--json" in sys.argv:
        print(json.dumps({"summary": summary, "turns": turns}, indent=1))
    else:
        print(json.dumps(summary))
        for t in turns:
            print(f"  #{t['n']:3d} {t['api']:9s} prompt {t['prompt']} cached {t['cached']} out {t['completion']} "
                  f"finish {t['finish']} calls {t['tool_calls']} bad {t['bad_args']} unparsed {t['unparsed_call']} "
                  f"early {t['early_end']} title {t['title']} wall {t['wall_s']}")
