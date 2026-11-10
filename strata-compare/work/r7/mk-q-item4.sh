#!/bin/bash
# mk-q-item4.sh PROMOTED_CONFIG — writes work/r7/q-item4.txt: item 4 runs on the promoted build (engine untouched; only
# CLI flags / env / clients). 4a nsys uses the trace twin of the same source (engine-r7o-trace, oracle off).
P=${1:?promoted config}
G="--adapt-swaps 0 --suffix-draft 0 --spec-min-p 0"
{
echo 'work/r7/tagcheck.sh "item4 start"'
# 4a: nsys, one decode window at a time over 120 windows (your flags, greedy), trace twin
echo "NSYS=node EXE=/home/USER/ai-speed-testing/strata-compare/engine-r7o-trace/strata ENVX=\"STRATA_PROFILE_FROM=60 STRATA_PROFILE_ROUNDS=120\" work/r7/run.sh nsys7-dec-math $P math 600"
echo "NSYS=node EXE=/home/USER/ai-speed-testing/strata-compare/engine-r7o-trace/strata ENVX=\"STRATA_PROFILE_FROM=60 STRATA_PROFILE_ROUNDS=120\" work/r7/run.sh nsys7-dec-math-x $P math 600 --adapt-swaps 0 --suffix-draft 0"
# 4b: --spec-split at the largest groups (8 = 4+4) vs unsplit 8 vs 4 (two back-to-back half windows); and 6 = 3+3 vs 6 vs 3
for r in a b; do
for P2 in math code; do
echo "work/r7/run.sh s8-$P2-$r $P $P2 512 --spec 8 $G"
echo "work/r7/run.sh s8split-$P2-$r $P $P2 512 --spec 8 --spec-split $G"
echo "work/r7/run.sh s4-$P2-$r $P $P2 512 --spec 4 $G"
echo "work/r7/run.sh s6-$P2-$r $P $P2 512 --spec 6 $G"
echo "work/r7/run.sh s6split-$P2-$r $P $P2 512 --spec 6 --spec-split $G"
echo "work/r7/run.sh s3-$P2-$r $P $P2 512 --spec 3 $G"
done
done
echo 'work/r7/tagcheck.sh "item4 4a/4b done"'
# 4e: two agents with web search, one after another vs overlapped, fresh guarded server each (SearXNG on)
for r in 1 2; do
echo "WEB=1 work/r7/with_server.sh AG-seq$r $P -- \".venv/bin/python work/r7/agents2.py seq seq$r\""
echo "WEB=1 work/r7/with_server.sh AG-ovl$r $P -- \".venv/bin/python work/r7/agents2.py ovl ovl$r\""
done
echo 'work/r7/tagcheck.sh "item4 done"'
} > work/r7/q-item4.txt
wc -l work/r7/q-item4.txt
