#!/bin/bash
# a1count.sh LABEL MINUTES — round 10 A.1/A.2 counting run, inside work/r12/with_server.sh (which started the counting
# build's server on 8081 and exported ELOG): warm-up, the LDR-shaped screen on the FRESH server (LABEL-fresh), MINUTES of
# LDR-shaped pool traffic (LABEL-pool, prompts/r10/ldr-pool.json shuffled), the screen again on the AGED server
# (LABEL-aged). The engine log's byte offsets at each step go to logs/r12/LABEL.offsets for a1_counts.py.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
L=$1 M=$2; O=logs/r12/$L.offsets; : > $O
.venv/bin/python work/r5/warmup.py http://127.0.0.1:8081
echo "fresh $(stat -c %s $ELOG)" >> $O
.venv/bin/python work/r12/ldrbench.py --config $L-fresh --engine-log $ELOG --set screen
echo "pool $(stat -c %s $ELOG)" >> $O
.venv/bin/python work/r12/ldrbench.py --config $L-pool --engine-log $ELOG --set pool --loop-min $M
echo "aged $(stat -c %s $ELOG)" >> $O
.venv/bin/python work/r12/ldrbench.py --config $L-aged --engine-log $ELOG --set screen
echo "end $(stat -c %s $ELOG)" >> $O
