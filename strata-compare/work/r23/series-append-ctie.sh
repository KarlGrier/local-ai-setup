#!/bin/bash
# series-append-ctie.sh (11-06 09:0x, Claude) - one shot. Karl 11-06: the served-path near-tie check
# (work/ds41/gate/gap-ctie-served.sh) is the series' step after the Basalt rerun, between questions. The running series
# (started 06:58) holds its steps in memory without it; gap-series.sh on disk lists it last (so any restart or a boot
# resume includes it). This waits for the running series' "series done" line (logged after this waiter started); then,
# when no gap is open, the series unit is inactive and the step has not run since, it starts the series with that step
# only - its boundary = a question that starts after "series done" (SERIES_T_END). The series stopped early (no
# "series done"): nothing is started (a series restart takes the step from disk). Children get 8>&- 9>&-.
set -u
SC=/home/USER/ai-speed-testing/strata-compare; W=$SC/work/r23; L=$SC/results/r23/gap-series.log; F=$W/gap-series.sh
CT=work/ds41/gate/gap-ctie-served.sh
log() { echo "$(date '+%F %T') series-append-ctie: $*" | tee -a $L; }
alert() { log "$1"; echo "$(date '+%m-%d %H:%M') GAP SERIES series-append-ctie: $1" >> $SC/NOTES.md
          notify-send -a "Strata gaps" -u critical "Gap series" "$1" 2> /dev/null || true; }
T0=${APPEND_T0:-$(date '+%F %T')}
TSRE='^20[0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9] '
done_line() { awk -v t="$T0" -v re="$TSRE" '$0 ~ re && substr($0, 1, 19) >= t && / series done$/ {l = $0} END {print l}' $L; }
ran_since() { awk -v t="$T0" -v re="$TSRE" -v c="$CT exit" '$0 ~ re && substr($0, 1, 19) >= t && index($0, c) {f = 1} END {exit !f}' $L; }
log "waiting for the running series to finish ('series done' after $T0); then the series with $CT only"
for i in $(seq 17280); do [ -n "$(done_line)" ] && break; sleep 30; done   # up to 6 days
TD=$(done_line | cut -c1-19)
[ -n "$TD" ] || { alert "no 'series done' within 6 days - $CT NOT started"; exit 1; }
sleep 10
[ -s $SC/tmp/port-gap.lockpid ] && { alert "a gap is open after 'series done' ($TD) - $CT NOT started"; exit 1; }
systemctl --user is-active -q gap-series.service && { log "gap-series is active again (restarted meanwhile) - nothing to do"; exit 0; }
ran_since && { log "$CT has run since $T0 - nothing to do"; exit 0; }
grep -q "^STEPS=(.*$CT" $F || { alert "gap-series.sh's STEPS line does not list $CT - NOT started"; exit 1; }
cp -p $F $F.before-ctie-start && cp -p $F $F.new
sed -i "s#^STEPS=.*#STEPS=($CT)#" $F.new
bash -n $F.new && grep -qF "'/^20[0-9][0-9]-" $F.new && grep -q '^question_since()' $F.new && grep -q '^t_end=' $F.new \
  || { alert "the series copy fails its checks (bash -n / the timestamp, retry or end-time rules) - $CT NOT started"; exit 1; }
mv $F.new $F
systemd-run --user --unit=gap-series --collect --setenv=GAP19_T0="$TD" --setenv=SERIES_T_END="$TD" \
  --description="r23 gap series (the DeepSeek served-path near-tie check, Karl 11-06)" /bin/bash $F > /dev/null 2>&1 8>&- 9>&-
sleep 5
log "series started (pid $(systemctl --user show -p MainPID --value gap-series)) with $CT only; its boundary: a question after $TD"
