#!/bin/bash
# u-adopt-after-chain.sh - Karl 11-09: U is adopted "after D2 and the end of the chain ... together with the mismatch guard
# install, so it's one restart". Waits (every 30 s) until the post-p5-chain unit has ended, then runs
# work/r23/gap-u-adopt.sh. That driver refuses by itself (nothing changed) unless the chain's log says "mismatch guard
# installed" and configs/P028x.json carries the guard key. A busy refusal (exit 1: a test lock, another gap, a DeepSeek
# session or another model server) is retried every 15 min for up to 3 h, then an alert; every other exit is final (the
# driver alerts itself). Holds no lock; children get no fd 8 / 9.
# Log: results/r23/u-adopt-start.log (the gap's own: results/r23/u-adopt/summary.txt).
set -u
exec 8>&- 9>&-
WS=/home/USER/ai-speed-testing/strata-compare
LOG=$WS/results/r23/u-adopt-start.log
say() { echo "$(date '+%F %T') u-adopt-after-chain: $*" >> $LOG; }
say "start (pid $$): waiting for the post-p5-chain unit to end"
n=0
while systemctl --user is-active -q post-p5-chain 2> /dev/null; do
  n=$((n + 1)); [ $((n % 60)) = 0 ] && say "the chain is still running ($((n / 2)) min)"
  sleep 30
done
say "the chain has ended: $(grep -E 'post-p5-chain:' $WS/results/r23/post-p5-chain.log | tail -1 | cut -c1-200)"
sleep 20   # the chain's last lines (the guard step, its note) are written
for try in $(seq 1 13); do
  /bin/bash $WS/work/r23/gap-u-adopt.sh 8>&- 9>&- < /dev/null >> $LOG 2>&1
  rc=$?
  say "try $try: gap-u-adopt.sh exit $rc ($(cut -c1-200 $WS/results/r23/u-adopt/result.txt 2> /dev/null))"
  [ $rc = 1 ] || exit $rc
  [ $try = 13 ] && break
  sleep 900
done
say "still busy after 3 h of retries - U NOT adopted"
notify-send -a Strata -u critical "U adoption not started" "the PC stayed busy for 3 h after the chain (a test lock, a gap or another model server); nothing changed" 2> /dev/null || true
exit 1
