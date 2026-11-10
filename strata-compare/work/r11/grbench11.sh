#!/bin/bash
# grbench11.sh — round 11 B.1: fork Eddoursul's hyper-connection read against our v5 and v3 (C*12.1's read) at 1-8 tokens:
# work/r11/gr_bench11.cu linked against the B.1 branch's kernel library (strata-r11b1/build), one mode per process,
# alternated, under the memory guard (no model server may run beside it); timings + the self check (each token = its
# own 1-token read) per mode.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r11/env.sh
S=$WS/strata-r11b1; D=$WS/results/r11/grbench11; mkdir -p $D tmp/r11/grbench11
/usr/local/cuda-13.3/bin/nvcc -O2 -std=c++17 -arch=sm_120 -I$S/include -o tmp/r11/grbench11/gr_bench11 work/r11/gr_bench11.cu \
  $S/build/libstrata_kernels.a $S/build/libstrata_core.a -lcuda 2>&1 | grep -v 'warning #' | head -5
for m in v5 v3 fork fork v3 v5; do
  n=$([ -f $D/$m-1.bin ] && echo 2 || echo 1)
  CUDA_VISIBLE_DEVICES=GPU-UUID-RTX5080 .venv/bin/python work/r11/guard.py grbench11-$m-$n -- tmp/r11/grbench11/gr_bench11 $m $D/$m-$n.bin > $D/$m-$n.out 2>&1; echo "$m run $n exit $?"
done
for m in v5 v3 fork; do cmp -s $D/$m-1.bin $D/$m-2.bin && echo "$m: run 1 = run 2 bit for bit" || echo "$m: runs differ"; done
.venv/bin/python - <<'PY'
import re, statistics
from pathlib import Path
D = Path("/home/USER/ai-speed-testing/strata-compare/results/r11/grbench11")
rows = {}
for f in sorted(D.glob("*.out")):
    m = f.stem.rsplit("-", 1)[0]
    for l in f.read_text().split("\n"):
        x = re.match(r"apply=(\d) T=(\d) cold_us ([\d.]+) warm_us ([\d.]+)", l)
        if x: rows.setdefault((m, int(x[1]), int(x[2])), []).append((float(x[3]), float(x[4])))
        y = re.match(r"apply=(\d) T=(\d) self check: (\d+) of", l)
        if y: rows.setdefault((m, int(y[1]), int(y[2]), "self"), []).append(int(y[3]))
print("| T | apply | v5 cold / warm (us) | v3 cold / warm | fork cold / warm | fork vs v3 (cold) | self check (tokens off their 1-token read) v5 / v3 / fork |")
print("|---|---|---|---|---|---|---|")
for T in range(1, 9):
    for ap in (0, 1):
        c = {m: (statistics.mean(v[0] for v in rows.get((m, ap, T), [(0, 0)])), statistics.mean(v[1] for v in rows.get((m, ap, T), [(0, 0)]))) for m in ("v5", "v3", "fork")}
        sc = " / ".join(str(max(rows.get((m, ap, T, "self"), [-1]))) for m in ("v5", "v3", "fork"))
        rel = 100 * (c["fork"][0] / c["v3"][0] - 1) if c["v3"][0] else 0
        print(f"| {T} | {ap} | {c['v5'][0]:.1f} / {c['v5'][1]:.1f} | {c['v3'][0]:.1f} / {c['v3'][1]:.1f} | {c['fork'][0]:.1f} / {c['fork'][1]:.1f} | {rel:+.1f} % | {sc} |")
PY
