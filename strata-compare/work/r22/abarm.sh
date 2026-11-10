#!/bin/bash
# abarm.sh URL OFF0 OUTDIR NAME ARM=SET:REPS[:ONLY] ... - Basalt round 2 (10-21): one Strata test server's requests, run
# INSIDE bringup/lib/with_server.sh (it exports $ELOG, the engine log). OFF0 = the engine log's size before the server
# started: NAME.startlog = the startup lines. Then the warm-up (NAME.wu.jsonl, kept out of the arms' slices) and each
# ARM=SET:REPS[:ONLY] in turn, with its own engine-log slice (ARM.englog) for basalt-ab/scripts/abreport.py --dir OUTDIR.
#   abarm.sh http://127.0.0.1:8081 123456 .../results/r2 s0 s0=normal:2 s0cal=calib:1
set -u
P=/home/USER/ai-speed-testing/strata-compare/.venv/bin/python; BA=/home/USER/ai-speed-testing/basalt-ab
URL=$1 OFF0=$2 R=$3 N=$4; shift 4
mkdir -p $R
tail -c +$((OFF0 + 1)) $ELOG > $R/$N.startlog
$P $BA/scripts/abrun.py run --base $URL --arm $N --set warmup --reps 1 --out $R/$N.wu.jsonl > /dev/null
for a in "$@"; do
  arm=${a%%=*}; IFS=: read -r set reps only <<< "${a#*=}"
  off=$(stat -c %s $ELOG)
  $P $BA/scripts/abrun.py run --base $URL --arm $arm --set $set --reps $reps ${only:+--only $only} --outdir $R
  sleep 3   # the last request's engine lines follow its last streamed token
  tail -c +$((off + 1)) $ELOG > $R/$arm.englog
  [ -e $R/$arm.startlog ] || cp $R/$N.startlog $R/$arm.startlog
done
