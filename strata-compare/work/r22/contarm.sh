#!/bin/bash
# contarm.sh URL OUTDIR NAME - round 22 gap 9 (10-23): the answer_room continuations, run INSIDE bringup/lib/with_server.sh
# (it exports $ELOG). W1 (cap 3072: answer_room closes the thinking at 2,304 tokens) 8 times as sent (NAMEw), then 4 times
# with "strata_checkpoint": false like deep-research's one-shot calls (NAMEk), each with its own engine-log slice
# (NAME?.englog) for work/r22/gap9_verdicts.py cont.
set -u
P=/home/USER/ai-speed-testing/strata-compare/.venv/bin/python; BA=/home/USER/ai-speed-testing/basalt-ab
URL=$1 R=$2 N=$3
mkdir -p $R
$P $BA/scripts/abrun.py run --base $URL --arm $N --set warmup --reps 1 --out $R/$N.wu.jsonl > /dev/null
off=$(stat -c %s $ELOG)
$P $BA/scripts/abrun.py run --base $URL --arm ${N}w --set normal --reps 8 --only W1 --outdir $R
sleep 3; tail -c +$((off + 1)) $ELOG > $R/${N}w.englog
off=$(stat -c %s $ELOG)
$P $BA/scripts/abrun.py run --base $URL --arm ${N}k --set normal --reps 4 --only W1 --extra '{"strata_checkpoint": false}' --outdir $R
sleep 3; tail -c +$((off + 1)) $ELOG > $R/${N}k.englog
