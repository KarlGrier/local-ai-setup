#!/bin/bash
# rcont.sh URL OUTDIR NAME - round 22 gap 10 (10-23): the long research-call replay with answer_room on, run INSIDE
# bringup/lib/with_server.sh (it exports $ELOG). abrun.py research4's R1-verify20k (o02 p4base call 1069, ~24K tokens,
# xhigh, cap 4,096: answer_room closes the thinking at 3,072) x 3 and R2-report54k (call 1061, ~54K tokens, medium, cap
# 4,096) x 2, with "strata_checkpoint": false as the research proxy sends those classes; one engine-log slice
# (NAME.englog) for work/r22/gap9_verdicts.py cont.
set -u
P=/home/USER/ai-speed-testing/strata-compare/.venv/bin/python; BA=/home/USER/ai-speed-testing/basalt-ab
URL=$1 R=$2 N=$3
mkdir -p $R
$P $BA/scripts/abrun.py run --base $URL --arm $N --set warmup --reps 1 --out $R/$N.wu.jsonl > /dev/null
off=$(stat -c %s $ELOG)
$P $BA/scripts/abrun.py run --base $URL --arm $N --set research4 --reps 3 --only R1-verify20k --extra '{"strata_checkpoint": false}' --outdir $R
$P $BA/scripts/abrun.py run --base $URL --arm $N --set research4 --reps 2 --only R2-report54k --extra '{"strata_checkpoint": false}' --outdir $R
sleep 3; tail -c +$((off + 1)) $ELOG > $R/$N.englog
