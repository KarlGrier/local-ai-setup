#!/usr/bin/env python3
"""dropcache.py - 10-24 DeepSeek-V4.1 tuning round: before every run, drop the model files' pages from the page cache
(posix_fadvise DONTNEED on each .gguf in the model folder; no root needed, other files untouched). On Linux the engine's
Engram reads and its VRAM-swap reads are buffered (engram_io.hpp:236-251; model.cu:5762-5848), so without this a later arm
would find the earlier arms' rows cached and look faster. Prints how much of the files was cached before (mincore over
a sample is not worth it here: just the file count and the time taken).
"""
import glob
import os
import time

M = "/home/USER/ai-speed-testing/strata-compare/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF"
t = time.time()
n = 0
for p in sorted(glob.glob(f"{M}/*.gguf")):
    fd = os.open(p, os.O_RDONLY)
    try:
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        n += 1
    finally:
        os.close(fd)
print(f"dropcache: {n} model files dropped from the page cache in {time.time() - t:.1f} s")
