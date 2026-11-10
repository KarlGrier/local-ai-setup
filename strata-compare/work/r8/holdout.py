#!/usr/bin/env python3
"""holdout.py LABEL BASE ENGINE_LOG — round 8 Phase C: the FRESH holdout, prompts no screen or decision used.
Through scripts/bench.py's Runner (results/runs.jsonl, engine stats from the engine log), the server's own settings
(the config's shared settings: T 1.0 / top-p 0.95 / top-k 20, min-p 0.05):
  physics, sql (4,096-token cap), story, compare (3,072), three short questions (512),
  one ~28K-token document (Strata's own docs, which no screen reads) + a question (1,024)."""
import argparse
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "scripts"))
from bench import Runner  # noqa: E402

U = lambda t: [{"role": "user", "content": t}]
ITEMS = [
    ("physics", 4096, U("A 2 kg block slides down a 30-degree incline of length 5 m with kinetic friction coefficient 0.2, "
                        "then onto a horizontal surface with friction coefficient 0.3, and finally compresses a spring "
                        "(k = 400 N/m). Find the speed at the bottom of the incline, the maximum spring compression, and "
                        "how far from the spring the block finally stops. Show every step and check units.")),
    ("sql", 4096, U("Write a Python module that reads a CSV of bank transactions (date, account, amount, category), "
                    "loads it into SQLite, and answers: the monthly net flow per account, the three largest spending "
                    "categories per quarter, and accounts whose balance ever went negative. Include the SQL, type "
                    "hints, error handling for malformed rows, and pytest tests.")),
    ("story", 3072, U("Write a short story (about 1,200 words) about a lighthouse keeper who receives letters from a "
                      "ship that sank fifty years ago. Keep a restrained tone and end on an ambiguous note.")),
    ("compare", 3072, U("Compare B-trees, LSM-trees and hash indexes for a write-heavy time-series workload: read and "
                        "write amplification, space amplification, compaction, crash recovery, and when each wins. "
                        "Finish with a decision table.")),
    ("short1", 512, U("What is the difference between a process and a thread? Two sentences.")),
    ("short2", 512, U("Give me three synonyms for 'resilient' and one sentence using each.")),
    ("short3", 512, U("Convert 72 degrees Fahrenheit to Celsius and explain the formula briefly.")),
]


def long_doc():
    src = WS / "strata-cstar8"
    parts = [src / "README.md"] + sorted((src / "docs").glob("*.md"))
    text = "\n\n".join(f"=== {p.name} ===\n{p.read_text(encoding='utf-8', errors='replace')}" for p in parts)
    return U("Here is the documentation of an inference engine.\n\n" + text +
             "\n\nUsing only the documentation above: how does the engine decide which experts live on which GPU, and "
             "what happens when the second GPU is missing or short of memory? Answer in about 300 words.")


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
