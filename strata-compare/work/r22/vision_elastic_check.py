#!/usr/bin/env python3
"""vision_elastic_check.py URL IMAGE OUT_PREFIX - round 22 (RAM option 1 for pictures): the reader started only when a
picture arrives ("elastic": true in the vision section, elastic_idle_s 30 for the test).

  1 after the server is up: is a strata-vision process running? (should not be)
  2 a screenshot sent the way Jan sends it: seconds to the first answer token and to the end - the reader's start
    included - and the reader's RSS right after
  3 then no picture: does the reader stop within elastic_idle_s + 90 s, and how much MemAvailable comes back
  4 another picture: the start again (the cost of a picture after a pause)
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
URL, IMG, OUT = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
sys.argv = [sys.argv[0], URL, IMG, OUT]
import vision_check as vc  # noqa: E402


def readers() -> list[int]:
    out = subprocess.run(["ps", "-C", "strata-vision", "-o", "rss="], capture_output=True, text=True).stdout.split()
    return [int(x) // 1024 for x in out]


def avail_gib() -> float:
    for line in open("/proc/meminfo"):
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 2**20
    return 0.0


print(f"1 after start: reader processes {readers()} (MiB RSS), MemAvailable {avail_gib():.2f} GiB")
r = vc.ask(1)
print(f"2 first picture: {r['first_answer_token_s']} s to the first answer token, {r['total_s']} s in all; "
      f"reader {readers()} MiB, MemAvailable {avail_gib():.2f} GiB")
t0 = time.time()
while readers() and time.time() - t0 < 120:
    time.sleep(2)
print(f"3 idle: reader {'stopped' if not readers() else 'STILL RUNNING'} after {time.time() - t0:.0f} s without a "
      f"picture; MemAvailable {avail_gib():.2f} GiB")
vc.IMG = Path(IMG).with_name("serving-110-color.png")   # another picture: no cached encoding can stand in for the reader
r = vc.ask(2)
print(f"4 picture after the pause: {r['first_answer_token_s']} s to the first answer token, {r['total_s']} s in all; "
      f"reader {readers()} MiB")
