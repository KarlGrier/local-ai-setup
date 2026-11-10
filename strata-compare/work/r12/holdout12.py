#!/usr/bin/env python3
"""holdout12.py LABEL BASE ENGINE_LOG — round 12: the NEW general holdout (written 2026-10-05 ~11:40, during Phase A and
before any Round 12 build or served A/B; NOT run by any screen until Phase C). Through scripts/bench.py's Runner
(results/runs.jsonl, engine stats from the engine log), the server's own settings (your shared settings: T 1.0 / top-p
0.95 / top-k 20, min-p 0.05, xhigh):
  beam (structural engineering), lsm (C++ code), lighthouse (story), cdc (comparison: change-data-capture tools),
  cards (probability), three short questions, one ~27K-token document (Strata v0.1.39's docs BATCHING / INSTALL /
  UNSLOTH_Q4 / AI_SETUP / MODELS / OLDER_GPUS / AMD_HIP_PERFORMANCE, none in Round 11's holdout; frozen in
  work/r12/holdout12-doc/ with SHA256) + a question. Round 11's holdouts were run in Round 11's Phase G: not fresh."""
import argparse
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "scripts"))
from bench import Runner  # noqa: E402

U = lambda t: [{"role": "user", "content": t}]  # noqa: E731
ITEMS = [
    ("beam", 4096, U("A simply supported glulam beam (GL24h, 140 x 450 mm) spans 6.4 m and carries a uniformly "
                     "distributed dead load of 3.2 kN/m (self-weight included) and a live load of 4.5 kN/m, plus a "
                     "point load of 12 kN at 2.4 m from the left support. Find the support reactions, the maximum "
                     "bending moment and where it occurs, the maximum shear, the bending and shear stresses, and the "
                     "mid-span deflection under the characteristic loads (E = 11,600 MPa). Show each step and check units.")),
    ("lsm", 4096, U("Write a small log-structured merge-tree key-value store in C++17: an in-memory sorted memtable, "
                    "flush to immutable sorted files with a sparse index and a Bloom filter per file, get / put / delete "
                    "(tombstones), and a size-tiered compaction that merges files. Include a write-ahead log for crash "
                    "recovery and a few unit tests with a temporary directory.")),
    ("lighthouse", 3072, U("Write a short story (about 1,000 words) about the last keeper of an automated lighthouse who "
                           "keeps writing entries in the logbook for a light that no longer needs him. Tell it through "
                           "the logbook entries and one letter he never sends. Quiet, specific, no twist ending.")),
    ("cdc", 3072, U("Compare Debezium, Maxwell and the native logical replication of PostgreSQL as ways to stream "
                    "database changes to Kafka: how each captures changes, ordering and exactly-once concerns, schema "
                    "changes, initial snapshots, operational burden and failure recovery. End with a table of when to "
                    "choose which.")),
    ("cards", 4096, U("Five cards are dealt from a well-shuffled standard 52-card deck. (a) What is the probability of "
                      "exactly one pair (and no better hand)? (b) What is the probability that all five cards are of "
                      "different ranks? (c) Given that the hand contains at least one ace, what is the probability that "
                      "it contains at least two aces? Show the counting for each part and check one result another way.")),
    ("short1", 512, U("Why do we see lightning before we hear thunder? Two sentences.")),
    ("short2", 512, U("Give three reasons a laptop battery wears out faster than expected, one sentence each.")),
    ("short3", 512, U("A price rises by 15% and then falls by 15%. What is the net change in percent? Show the arithmetic.")),
]
DOCS = ["BATCHING.md", "INSTALL.md", "UNSLOTH_Q4.md", "AI_SETUP.md", "MODELS.md", "OLDER_GPUS.md", "AMD_HIP_PERFORMANCE.md"]


def long_doc():
    src = WS / "work/r12/holdout12-doc"
    text = "\n\n".join(f"=== {name} ===\n{(src / name).read_text(encoding='utf-8')}" for name in DOCS)
    return U("Here is part of the documentation of an LLM inference engine.\n\n" + text +
             "\n\nUsing only the documentation above: when does running several requests together help on a single "
             "16 GB card, what does it cost, and how would someone install the engine and serve a 4-bit model on "
             "such a card? Answer in about 300 words.")


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
        r.call("holdout12", item, 0, msgs, mt)
    r.call("holdout12", "enginedoc", 0, long_doc(), 1024)


if __name__ == "__main__":
    main()
