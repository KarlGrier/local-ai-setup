#!/usr/bin/env python3
"""workers-compare.py LABEL... — compare the research phase of bench-LABEL-open1 runs (the subagent-worker test).

Research phase = from the research start to the first report-stage call (so the report stage, whose length depends
only on how much was found, does not blur the comparison). From strata-proxy's call log slice (calls.jsonl), the
deep evidence store (deep/evidence.jsonl) and Strata's request records (strata-requests.json):
  work done:   subagents finished, searches, pages read, page extractions, findings text
  throughput:  generated tokens, generated tokens per wall second, Strata busy share (union of call intervals)
  cache:       agent prompt tokens Strata had to read again (prompt - reused) — a conversation that fell out of
               Strata's chat cache (6 slots) while other agents ran is re-read in full
Writes results/workers-compare.md and prints it."""
import json
import sys
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")


def load(label):
    d = WS / "results" / f"bench-{label}-open1"
    marks = json.loads((d / "marks.json").read_text())
    calls = [json.loads(l) for l in (d / "calls.jsonl").read_text().splitlines() if l.strip()]
    calls = [c for c in calls if c.get("path", "").endswith("/chat/completions") and c.get("t_end")]
    ev = d / "deep" / "evidence.jsonl"
    evidence = [json.loads(l) for l in ev.read_text().splitlines()] if ev.exists() else []
    return d, marks, calls, evidence


def busy(iv):
    tot, cur = 0.0, None
    for a, b in sorted(iv):
        if cur is None or a > cur[1]:
            if cur:
                tot += cur[1] - cur[0]
            cur = [a, b]
        else:
            cur[1] = max(cur[1], b)
    return tot + (cur[1] - cur[0] if cur else 0)


def metrics(label):
    d, marks, calls, evidence = load(label)
    t0 = marks["t_start"]
    rep = [c["t0"] for c in calls if c.get("cls") in ("report", "verify")]
    t1 = min(rep) if rep else marks["t_end"]
    rc = [c for c in calls if c["t0"] < t1]
    wall = t1 - t0
    gen = {}
    for c in rc:
        u = c.get("usage") or {}
        gen[c.get("cls")] = gen.get(c.get("cls"), 0) + (u.get("completion_tokens") or 0)
    reread = sum(max(0, (c.get("usage") or {}).get("prompt_tokens", 0) -
                     ((c.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens", 0))
                 for c in rc if c.get("cls") == "agent")
    subs = [e for e in evidence if e["type"] == "subagent"]
    fetches = [e for e in evidence if e["type"] == "fetch"]
    pages = {e["url"] for e in fetches if e.get("extraction") and not e["extraction"].startswith("NOT RELEVANT")}
    searches = [e for e in evidence if e["type"] == "search"]
    ran = [s for s in subs if not s["status"].startswith("not started")]
    return {
        "label": label, "workers": marks.get("workers") or "".join(ch for ch in label if ch.isdigit()), "research_min": round(wall / 60, 1),
        "llm_calls": len(rc), "generated": sum(gen.values()), "gen_by_class": gen,
        "gen_tok_per_s": round(sum(gen.values()) / wall, 1) if wall else None,
        "strata_busy": round(busy([(max(c["t0"], t0), min(c["t_end"], t1)) for c in rc]) / wall, 3) if wall else None,
        "agent_reread_tokens": reread,
        "subagents_run": len(ran), "subagents_not_started": len(subs) - len(ran),
        "subagent_findings_chars": sum(len(s.get("text") or "") for s in ran),
        "searches": len(searches), "extractions": len(fetches), "pages_read": len(pages),
        "report_stage_min": round((marks["t_end"] - t1) / 60, 1) if rep else None,
        "final_status": marks.get("final_status"),
    }


def main():
    rows = [metrics(l) for l in sys.argv[1:]]
    keys = [("workers", "workers"), ("research_min", "research phase (min)"), ("llm_calls", "LLM calls"),
            ("generated", "generated tokens"), ("gen_tok_per_s", "generated tok/s (wall)"),
            ("strata_busy", "Strata busy share"), ("agent_reread_tokens", "agent prompt tokens re-read"),
            ("subagents_run", "subagents run"), ("subagents_not_started", "subagents not started"),
            ("subagent_findings_chars", "subagent findings (chars)"), ("searches", "searches"),
            ("extractions", "page extractions"), ("pages_read", "distinct pages with findings"),
            ("report_stage_min", "report stage (min)"), ("final_status", "status")]
    out = ["| | " + " | ".join(r["label"] for r in rows) + " |", "|---|" + "---|" * len(rows)]
    for k, name in keys:
        out.append(f"| {name} | " + " | ".join(str(r.get(k)) for r in rows) + " |")
    out.append("")
    out.append("generated tokens by call type: " + "; ".join(
        f"{r['label']}: " + ", ".join(f"{k} {v:,}" for k, v in sorted(r["gen_by_class"].items(), key=lambda x: -x[1]))
        for r in rows))
    text = "\n".join(out)
    (WS / "results" / "workers-compare.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
