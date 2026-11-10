#!/bin/bash
# dec_after.sh - 10-26 13:25 (Karl: a decode check before IQ_Q8K is dropped): waits for the running ports session to
# close, then starts "iqq8k@dec" + "?p343+iqq8k" in a new session only if IQ_Q8K missed the placement bar in 8-token
# windows with everything else passing (gate, off identical, candidate differs). Met bar: the session ran the combined
# A/B/A itself - nothing to do. Anything else (gate failed, not reached, session stopped): nothing starts; a line says why.
SC=/home/USER/ai-speed-testing/strata-compare
LOG=$SC/results/ds41/ports/session.log
while systemctl --user is-active -q ds41-ports; do sleep 20; done
sleep 5
why=$(python3 - <<'EOF'
import json
R = "/home/USER/ai-speed-testing/strata-compare/results/ds41/ports"
ss = json.load(open(f"{R}/state-session.json"))
if ss.get("stopped"):
    print("stopped: " + str(ss["stopped"])); raise SystemExit
w = json.load(open(f"{R}/state-iqq8k.json")).get("iq_w8") or {}
if not w:
    print("no 8-token result")
elif w.get("cand_identical_to_base"):
    print("not reached")
elif not (w.get("gate") and w.get("off_identical_to_base")):
    print("gate or off check failed")
elif w.get("clearly_less"):
    print("bar met")
else:
    print("RUN")
EOF
)
if [ "$why" != "RUN" ]; then
  echo "=== $(date '+%F %T') decode check not started: $why" >> $LOG
  exit 0
fi
echo "=== $(date '+%F %T') IQ_Q8K missed the placement bar: the decode check (Karl, 13:20) starts" >> $LOG
for i in 1 2 3; do
  systemd-run --user --unit ds41-ports --collect -p WorkingDirectory=$SC /usr/bin/python3 -u $SC/work/ds41/after/ports.py \
    'iqq8k@dec' '{}' '?p343+iqq8k' '{"STRATA_DS4_PROMPT_SKIP": "1", "_A": {"engine": "v026p343", "mods": {"STRATA_DS4_PROMPT_SKIP": "1"}}}' && exit 0
  sleep 10
done
echo "=== $(date '+%F %T') decode check: the session would not start" >> $LOG
exit 1
