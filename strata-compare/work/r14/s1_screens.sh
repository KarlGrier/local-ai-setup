#!/bin/bash
# s1_screens.sh — round 14 step 1: the release alone (stock v0.1.40.1 + my config's flags, none of our switches,
# bringup/out/r14/configs/stock.json) vs C*13.1 (configs/Cstar131.json): LDR, decode and full screens, A B B A
# (A = C*13.1, B = stock), each a fresh guarded server on 8081. Tables -> results/r14/s1-screen-{ldr,dec,full}.md
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
P=$WS/configs/Cstar131.json S=$WS/bringup/out/r14/configs/stock.json
SS=$(date -Iseconds | cut -c1-19)
for arm in "prom-a $P" "stock-a $S" "stock-b $S" "prom-b $P"; do
  set -- $arm
  bringup/lib/ldrscreen.sh r14-s1-L-$1 $2 > logs/r14/s1-L-$1.log 2>&1
  bringup/lib/decscreen.sh r14-s1-D-$1 $2 > logs/r14/s1-D-$1.log 2>&1
  bringup/lib/fullscreen.sh r14-s1-F-$1 $2 > logs/r14/s1-F-$1.log 2>&1
done
SINCE=$SS .venv/bin/python bringup/lib/ldr_table.py C131=r14-s1-L-prom-a,r14-s1-L-prom-b stock=r14-s1-L-stock-a,r14-s1-L-stock-b > results/r14/s1-screen-ldr.md 2>&1
SINCE=$SS .venv/bin/python bringup/lib/ab_table.py C131=r14-s1-D-prom-a,r14-s1-D-prom-b stock=r14-s1-D-stock-a,r14-s1-D-stock-b > results/r14/s1-screen-dec.md 2>&1
SINCE=$SS .venv/bin/python bringup/lib/ab_table.py C131=r14-s1-F-prom-a,r14-s1-F-prom-b stock=r14-s1-F-stock-a,r14-s1-F-stock-b > results/r14/s1-screen-full.md 2>&1
echo "s1 screens done: $(head -3 results/r14/s1-screen-dec.md | tail -1)"
