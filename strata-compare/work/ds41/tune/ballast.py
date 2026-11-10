#!/usr/bin/env python3
"""ballast.py GIB - 10-24 DeepSeek-V4.1 tuning round, the daily store size: LDR's RAM stood in for while 8080 is down
(run-ldr.sh start needs Strata answering on 8080). Holds GIB of touched anonymous memory until killed (by PID)."""
import sys
import time

b = bytearray(int(float(sys.argv[1]) * 2**30))
for i in range(0, len(b), 4096):
    b[i] = 1
print(f"ballast: {sys.argv[1]} GiB held", flush=True)
while True:
    time.sleep(3600)
