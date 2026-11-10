#!/usr/bin/env python3
"""holdout.py LABEL BASE ENGINE_LOG — round 9 Phase C: the FRESH holdout, prompts no screen or decision used.
Through scripts/bench.py's Runner (results/runs.jsonl, engine stats from the engine log), the server's own settings
(the config's shared settings: T 1.0 / top-p 0.95 / top-k 20, min-p 0.05):
  circuit, parser (4,096-token cap), letter, tradeoff (3,072), three short questions (512),
  one ~28K-token document (SearXNG's admin docs, which no screen reads) + a question (1,024).
Round 9's prompts are NEW (written 16:50, before any Phase C decision); round 8's holdout prompts were used for round 8's
decisions, so they are not fresh any more."""
import argparse
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "scripts"))
from bench import Runner  # noqa: E402

U = lambda t: [{"role": "user", "content": t}]
ITEMS = [
    ("circuit", 4096, U("An RC circuit has R = 4.7 kOhm and C = 220 uF, charged from a 12 V source through a switch at t = 0. "
                        "Derive the voltage across the capacitor over time, find the time to reach 9 V, the energy stored "
                        "at that moment, and the energy dissipated in the resistor up to then. Show each step and check "
                        "units.")),
    ("parser", 4096, U("Write a Rust command-line tool that reads an nginx access log, parses each line with a hand-written "
                       "parser (no regex crate), and prints the top 10 client IPs, the status-code histogram, and the "
                       "95th-percentile response size per hour. Include error handling for malformed lines and unit tests.")),
    ("letter", 3072, U("Write a letter (about 1,000 words) from a retired cartographer to the grandchild who just inherited "
                       "her unfinished map of a coastline that no longer exists. Warm but unsentimental; end with an "
                       "instruction the grandchild may or may not follow.")),
    ("tradeoff", 3072, U("Compare Raft, Paxos (Multi-Paxos) and viewstamped replication for a small replicated "
                         "configuration store: leader election, log replication, membership changes, read paths, and "
                         "failure modes under network partitions. Finish with a recommendation table.")),
    ("short1", 512, U("Why does ice float on water? Two sentences.")),
    ("short2", 512, U("Give three ways to say 'thank you' in a formal email, each in one sentence.")),
    ("short3", 512, U("How many seconds are there in a leap year? Show the arithmetic.")),
]


def long_doc():
    # round 9's fresh document: SearXNG's administrator docs (in websearch/searxng/docs), which no screen, test or
    # earlier holdout reads; about 28K tokens
    src = WS / "websearch/searxng/docs/admin"
    parts = sorted(src.glob("*.rst")) + sorted((src / "settings").glob("*.rst"))
    text, n = [], 0
    for q in parts:
        t = q.read_text(encoding="utf-8", errors="replace")
        if n + len(t) > 104000:
            break
        text.append(f"=== {q.relative_to(src)} ===\n{t}"); n += len(t)
    return U("Here is the administrator documentation of a metasearch engine.\n\n" + "\n\n".join(text) +
             "\n\nUsing only the documentation above: how do you install it behind a reverse proxy, and which settings "
             "control which search engines are used and how outgoing requests are made? Answer in about 300 words.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("base")
    ap.add_argument("engine_log")
    a = ap.parse_args()
    ns = argparse.Namespace(model="x", base=a.base, engine_log=a.engine_log, config=a.label, extra="",
                            session=None, rep=0, items="", max_tokens=0)
    r = Runner(ns)
    for item, mt, msgs in ITEMS:
        r.call("holdout", item, 0, msgs, mt)
    r.call("holdout", "doc28k", 0, long_doc(), 1024)


if __name__ == "__main__":
    main()
