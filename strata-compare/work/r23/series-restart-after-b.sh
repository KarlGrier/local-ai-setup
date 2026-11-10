#!/bin/bash
# series-restart-after-b.sh (11-05, Karl: the decode-path check goes BEFORE Basalt a; C's tie-check rerun goes in at the
# next safe restart point). One shot: waits until the gap series has finished decode part b (exit 0) and launched
# Basalt a's snapshot (which then only waits for o03 in port_gap4 begin - no gap open), then restarts the series with
# the remaining steps: the decode-path check (+ part b's 7 lost Basalt-fixture passes as its last step), Basalt a,
# Basalt b, DeepSeek C (rerun), Unsloth v3.1. The new series' first boundary is anchored at decode b's launch time
# (GAP19_T0), so the decode-path gap lands after o03. Refuses (no restart) if decode b did not exit 0, if a gap is open,
# or if Basalt a never got launched within 20 min.
set -u
SC=/home/USER/ai-speed-testing/strata-compare; L=$SC/results/r23/gap-series.log; F=$SC/work/r23/gap-series.sh
log() { echo "$(date '+%F %T') restart-waiter: $*" | tee -a $L; }
log "waiting for decode part b to finish (one-shot; restarts the series with: decpath, Basalt a, Basalt b, C rerun, v3.1)"
for i in $(seq 1440); do grep -q 'work/r23/gap-decode-b.sh exit' $L && break; sleep 30; done
rc=$(grep 'work/r23/gap-decode-b.sh exit' $L | tail -1 | awk '{print $NF}')
[ "$rc" = 0 ] || { log "decode b exit '${rc:-none}' - NO restart (the series handles it)"; exit 1; }
for i in $(seq 120); do grep -q 'starting work/r23/gap-basalt-a.sh' $L && break; sleep 10; done
grep -q 'starting work/r23/gap-basalt-a.sh' $L || { log "Basalt a was not launched within 20 min - NO restart"; exit 1; }
sleep 30
[ -s $SC/tmp/port-gap.lockpid ] && { log "a gap is open - NO restart"; exit 1; }
t0=$(grep 'starting work/r23/gap-decode-b.sh' $L | tail -1 | cut -c1-19)
[ -n "$t0" ] || { log "no decode b launch line - NO restart"; exit 1; }
cp -p $F $F.before-decpath && cp -p $F $F.new
sed -i 's#^STEPS=.*#STEPS=(work/r23/gap-decpath.sh work/r23/gap-basalt-a.sh work/r23/gap-basalt-b.sh work/ds41/gate/gap-csample.sh work/r23/gap-ud31.sh)#' $F.new
bash -n $F.new || { log "bash -n failed on the new series - NO restart"; exit 1; }
mv $F.new $F
systemctl --user stop gap-series.service; sleep 3
[ -s $SC/tmp/port-gap.lockpid ] && { log "a gap opened during the stop?! - not starting the series again: Karl / Claude look"; exit 1; }
systemd-run --user --unit=gap-series --collect --setenv=GAP19_T0="$t0" --description="r23 gap series (decpath, Basalt a/b, C rerun, v3.1)" /bin/bash $F > /dev/null 2>&1
sleep 5
log "series restarted (pid $(systemctl --user show -p MainPID --value gap-series)), anchored at decode b's launch $t0; steps: $(grep '^STEPS' $F | cut -c7-)"
