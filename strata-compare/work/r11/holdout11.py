#!/usr/bin/env python3
"""holdout11.py LABEL BASE ENGINE_LOG — round 11: the NEW general holdout (written 2026-10-04 ~03:10, before Phase A and
before any Round 11 decision; NOT run by any screen until Phase G).  Through scripts/bench.py's Runner
(results/runs.jsonl, engine stats from the engine log), the server's own settings (your shared settings: T 1.0 / top-p
0.95 / top-k 20, min-p 0.05, xhigh):
  pump (engineering), ratelimit (Rust code), letters (story), consensus (comparison), dice (probability), three short
  questions, one ~28K-token document (Strata v0.1.38's own docs: DETAILS / HOW_IT_WORKS / MULTI_GPU / SECOND_GPU /
  TROUBLESHOOTING, frozen in work/r11/holdout11-doc/ with SHA256; no screen, holdout or TF text reads them) + a question.
Round 10's general holdout (beam / lrucache / logbook / indexes / SearXNG dev docs) was used in Round 10's Phase E, so
it is not fresh."""
import argparse
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "scripts"))
from bench import Runner  # noqa: E402

U = lambda t: [{"role": "user", "content": t}]  # noqa: E731
ITEMS = [
    ("pump", 4096, U("A centrifugal pump lifts water from a reservoir to a tank 18 m higher through 140 m of 100 mm "
                     "commercial steel pipe (roughness 0.045 mm) with two 90-degree elbows, a gate valve and a check "
                     "valve, at 12 L/s and 20 °C. Find the flow velocity, the Reynolds number, the friction factor "
                     "(Colebrook or Swamee-Jain), the major and minor head losses, the total dynamic head, and the "
                     "electrical power if the pump is 72 % and the motor 92 % efficient. Show each step and check units.")),
    ("ratelimit", 4096, U("Write a Rust crate with a token-bucket rate limiter that is safe to share between threads: "
                          "try_acquire(n), acquire(n) that blocks until tokens are available, a refill rate and burst "
                          "size set at construction, and a per-key variant backed by a sharded map that evicts idle "
                          "keys. Include unit tests that use a mock clock and a short README section.")),
    ("letters", 3072, U("Write a short story (about 1,000 words) told only through the letters between a translator and "
                        "the novelist whose book she is translating, who never meet. The letters slowly reveal that the "
                        "translator is changing the ending. Keep it understated and end without resolving it.")),
    ("consensus", 3072, U("Compare Raft, Multi-Paxos and Viewstamped Replication as consensus protocols for a replicated "
                          "key-value store: leader election, log replication, membership changes, read paths "
                          "(leases vs read index), failure detection and how hard each is to implement correctly. "
                          "Finish with a table of when to choose which.")),
    ("dice", 4096, U("Three fair six-sided dice are rolled. (a) What is the probability that the sum is exactly 10? "
                     "(b) What is the probability that at least two dice show the same number? (c) Given that the sum "
                     "is 10, what is the probability that at least two dice show the same number? Show the counting "
                     "for each part and check the results another way.")),
    ("short1", 512, U("Why does ice float on liquid water? Two sentences.")),
    ("short2", 512, U("Give three common reasons home Wi-Fi gets slow in the evening, one sentence each.")),
    ("short3", 512, U("What is 23% of 1,840? Show the arithmetic.")),
]
DOCS = ["HOW_IT_WORKS.md", "DETAILS.md", "MULTI_GPU.md", "SECOND_GPU.md", "TROUBLESHOOTING.md"]


def long_doc():
    src = WS / "work/r11/holdout11-doc"
    text = "\n\n".join(f"=== {name} ===\n{(src / name).read_text(encoding='utf-8')}" for name in DOCS)
    return U("Here is the documentation of an LLM inference engine.\n\n" + text +
             "\n\nUsing only the documentation above: how does this engine decide which experts are computed on the "
             "GPU, on a second GPU and on the CPU, and what should someone with one 16 GB card and one 8 GB card "
             "configure first? Answer in about 300 words.")


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
        r.call("holdout11", item, 0, msgs, mt)
    r.call("holdout11", "enginedoc", 0, long_doc(), 1024)


if __name__ == "__main__":
    main()
