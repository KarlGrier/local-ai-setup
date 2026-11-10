#!/bin/bash
# nsys_test.sh BINARY LABEL [args] — kernel durations of a unit-test binary (CUDA trace only, temp files in the workspace)
WS=/home/USER/ai-speed-testing/strata-compare
B=$1 L=$2; shift 2
mkdir -p $WS/logs/r3/nsys $WS/tmp
TMPDIR=$WS/tmp /usr/local/cuda-13.3/bin/nsys profile -o $WS/logs/r3/nsys/$L --force-overwrite=true --trace=cuda --sample=none --cpuctxsw=none --export=sqlite $B "$@" > $WS/logs/r3/nsys/$L.out 2>&1
$WS/.venv/bin/python - "$WS/logs/r3/nsys/$L.sqlite" <<'PY'
import sqlite3, sys, collections
db = sqlite3.connect(sys.argv[1]); c = db.cursor()
s = dict(c.execute("SELECT id, value FROM StringIds"))
d = collections.defaultdict(list)
for n, a, b in c.execute("SELECT shortName, start, end FROM CUPTI_ACTIVITY_KIND_KERNEL"):
    d[s[n]].append((b - a) / 1e3)
for n, v in sorted(d.items(), key=lambda x: -sum(x[1])):
    v.sort(); print(f"{n[:40]:<40} n={len(v):5d} median {v[len(v)//2]:7.2f} us  min {v[0]:7.2f}")
PY
