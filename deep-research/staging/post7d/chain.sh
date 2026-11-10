#!/bin/bash
# chain.sh - the whole post-7d order in one waiter (staged 11-04, staging/post7d; NOT run). Start it only with Karl's
# OK, as a transient user unit so it outlives the session:
#   systemd-run --user --unit=post7d-chain --description="post-7d bench plan chain" /bin/bash /home/USER/ai/deep-research/staging/post7d/chain.sh
# then confirm: systemctl --user is-active post7d-chain; its pid; the line "waiting for queue-plan-7d.json to finish"
# in logs/post7d-switch.log. Order (Karl 11-04): install -> fresh baseline -> item 8 -> C3c -> (Phase 5 with GO-p5).
#   1 queue-plan-7d.json finished ("queue finished (queue-plan-7d.json)", unit inactive, every run done; no hold file)
#     -> install-ldr-fixes.sh (0007 memwatch + 0008 steps + runner-fresh-ldr + the queue's fix:steps; no LDR run, Jan
#     job or gap live; tests after) -> the unit on queue-plan-p4s9.json (the fresh baseline: o01-o03, ~8.7 h)
#   2 queue-plan-p4s9.json finished -> queue-plan-item8.json (item 8 stage 2: six 62-min runs, ~6.4 h)
#   3 queue-plan-item8.json finished -> replays.sh (merges + 10 report replays vs p4s9, ~8 h) -> queue-plan-c3c.json
#     (C3c runs, ~8.7 h; installs profiles/flash-next-c3c.env first)
#   4 queue-plan-c3c.json finished AND staging/post7d/GO-p5 = sha256 of queue-plan-p5-holdout.json (written only after
#     7d's grading, Karl's adoption calls and his OK on that exact plan) -> tools/bench2.py with the p5 sets, the unit
#     on queue-plan-p5-holdout.json (~35 h). Until GO-p5 exists the chain waits (the GPU is free for phase-4 gaps).
# Every step waits while tmp/bench2.hold exists. A step that does not switch ends the chain (exit 1, desktop notice);
# fix the cause and run the remaining steps by hand (CHAIN_STEPS="2 3 4" bash chain.sh, or switch.sh FROM TO).
# staging/post7d/STOP-switch stops a wait (exit 3); STOP-replays stops the replays before the next one.
# CHAIN_STEPS="1 2 3" leaves Phase 5 out. P028x stays the served build throughout (replays.sh checks it).
set -u
S=/home/USER/ai/deep-research/staging/post7d
for st in ${CHAIN_STEPS:-1 2 3 4}; do
  case $st in
    1) bash $S/switch.sh --between $S/install-ldr-fixes.sh queue-plan-7d.json queue-plan-p4s9.json || exit 1 ;;
    2) bash $S/switch.sh queue-plan-p4s9.json queue-plan-item8.json || exit 1 ;;
    3) bash $S/switch.sh --between $S/replays.sh queue-plan-item8.json queue-plan-c3c.json || exit 1 ;;
    4) bash $S/switch.sh queue-plan-c3c.json queue-plan-p5-holdout.json || exit 1 ;;
  esac
done
exit 0
