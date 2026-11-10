#!/home/USER/ai-speed-testing/strata-compare/.venv/bin/python
"""mock_engine.py - score.py selftest's stand-in for `strata --serve` (no GPU, no model): speaks the stdin protocol
(READY; GEN 1 <ids> -> DONE; QUIT) and writes the hooks' files exactly as the engine lays them out:
  STRATA_PREFILL_DUMP_R      per prompt read: truncated at the read's first chunk, then (int64 pos, D float32) for every
                             position p = 0 mod 64 below n - 1 (the batched part; the last token goes to the window)
  STRATA_PREFILL_DUMP_R_ALL  appended: (n - 1) rows of D BF16 values, position order, no header
  STRATA_DUMP_FIRST_LOGITS   <path>.<k>: the first window's logits (here a small deterministic row of VOCAB floats)
Rows are a deterministic function of (position, token) so two runs are identical. MOCK_TRUNCATE=1 drops the first
chunk's rows (the failure the driver must catch). Arguments are ignored."""
import os
import sys

import numpy as np

D = 4 * 2560
VOCAB = 1024


def row(p: int, tok: int) -> np.ndarray:
    return np.random.default_rng(p * 1000003 + tok).standard_normal(D).astype(np.float32)


def main() -> int:
    dr, da, fl = (os.environ.get(k) for k in ("STRATA_PREFILL_DUMP_R", "STRATA_PREFILL_DUMP_R_ALL",
                                              "STRATA_DUMP_FIRST_LOGITS"))
    trunc = os.environ.get("MOCK_TRUNCATE") == "1"
    k = 0
    print("READY", flush=True)
    for line in sys.stdin:
        if line.startswith("QUIT"):
            break
        if not line.startswith("GEN "):
            print("ERR bad request", flush=True)
            continue
        ids = [int(x) for x in line.split()[2].split(",")]
        n = len(ids)
        chunk = 16384
        if dr:
            for c0 in range(0, n - 1, chunk):
                if trunc and c0 == 0:
                    continue
                with open(dr, "wb" if c0 == 0 or (trunc and c0 == chunk) else "ab") as f:
                    for p in range(c0 + (64 - c0 % 64) % 64, min(n - 1, c0 + chunk), 64):
                        np.array([p], "<i8").tofile(f)
                        row(p, ids[p]).tofile(f)
        if da:
            with open(da, "ab") as f:
                for p in range(n - 1):
                    u = row(p, ids[p]).view(np.uint32).astype(np.uint64)
                    ((u + ((u >> 16) & 1) + 0x7FFF) >> 16).astype(np.uint16).tofile(f)
        if fl:
            np.random.default_rng(n).standard_normal(VOCAB).astype(np.float32).tofile(f"{fl}.{k}")
        k += 1
        print(f"DONE 1 tokens, prompt {n}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
