#!/usr/bin/env python3
"""holdout.py LABEL BASE ENGINE_LOG — round 10 Phase E: the FRESH general holdout (written 08:05 on 2026-10-02, before any
Round 10 decision; NOT run by any screen until Phase E).  Through scripts/bench.py's Runner (results/runs.jsonl, engine
stats from the engine log), the server's own settings (your shared settings: T 1.0 / top-p 0.95 / top-k 20, min-p 0.05):
  beam (engineering), lrucache (Go code), logbook (story), indexes (comparison), three short questions,
  one ~30K-token document (SearXNG's DEVELOPER docs, websearch/searxng/docs/dev — Round 9's holdout used the admin
  docs; no screen reads either) + a question.
Round 9's holdout (circuit / parser / letter / tradeoff / admin docs) was used for Round 9's decision, so it is not fresh."""
import argparse
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "scripts"))
from bench import Runner  # noqa: E402

U = lambda t: [{"role": "user", "content": t}]
ITEMS = [
    ("beam", 4096, U("A simply supported steel beam 6 m long carries a uniformly distributed load of 12 kN/m over its whole "
                     "length and a point load of 20 kN at 2 m from the left support. Find the support reactions, the "
                     "shear force and bending moment at the key points, the maximum bending moment and where it occurs, "
                     "and the section modulus needed for an allowable bending stress of 165 MPa. Show each step and "
                     "check units.")),
    ("lrucache", 4096, U("Write a Go package with an LRU cache that has a per-entry time-to-live and is safe for concurrent "
                         "use: Get, Set, Delete, Len, and a background janitor that removes expired entries without "
                         "holding the lock for long. Include table-driven tests and a benchmark.")),
    ("logbook", 3072, U("Write a short story (about 1,000 words) told entirely as the maintenance log of the machine that "
                        "replaced a lighthouse keeper, which slowly starts adding entries nobody programmed it to write. "
                        "Keep the tone restrained and leave the ending open.")),
    ("indexes", 3072, U("Compare B-trees, LSM-trees and hash indexes as the storage engine of a time-series database: "
                        "write amplification, read amplification, range scans, compaction or rebalancing, space "
                        "overhead and crash recovery. Finish with a recommendation table for three workloads.")),
    ("short1", 512, U("Why is the clear daytime sky darker straight overhead than near the horizon? Two sentences.")),
    ("short2", 512, U("Name three common reasons a car battery drains overnight, one sentence each.")),
    ("short3", 512, U("What is 17% of 2,450? Show the arithmetic.")),
]


def long_doc():
    src = WS / "websearch/searxng/docs/dev"
    parts = sorted(src.rglob("*.rst"))
    text, n = [], 0
    for q in parts:
        t = q.read_text(encoding="utf-8", errors="replace")
        if n + len(t) > 112000:
            continue
        text.append(f"=== {q.relative_to(src)} ===\n{t}"); n += len(t)
    return U("Here is the developer documentation of a metasearch engine.\n\n" + "\n\n".join(text) +
             "\n\nUsing only the documentation above: how would a developer add a new search engine to it, test it "
             "locally, and get it accepted? Answer in about 300 words.")


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
        r.call("holdout10", item, 0, msgs, mt)
    r.call("holdout10", "devdoc", 0, long_doc(), 1024)


if __name__ == "__main__":
    main()
