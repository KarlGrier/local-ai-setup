#!/bin/bash
# a4profile.sh — round 10 A.4 (no GPU): personal expert profiles from the routing traces of the personal prompts
# (tools/make_profile.py --no-base), and the two-tier cache replay (work/r11/replay10.py) of the shipped profile vs the
# personal ones: first the replay validated against the engine's own placement on the traces it recorded (the shipped
# profile, landing lag 1 and 2), then each half's profile replayed on the OTHER half (held out), then the full profile.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source work/r11/env.sh
R=tmp/r11/route; SHIP=strata-v0115/data/expert-profile.bin; MP=strata-v35/tools/make_profile.py; P=.venv/bin/python
$P $MP $R/R4t-A.dump --no-base --out $R/prof-A.bin
$P $MP $R/R4t-B.dump --no-base --out $R/prof-B.bin
$P $MP $R/R4t-A.dump $R/R4t-B.dump --no-base --out $R/prof-AB.bin
sha256sum $SHIP $R/prof-*.bin
echo "== validation (shipped profile, the traces it recorded)"
for lag in 1 2; do $P work/r11/replay10.py $SHIP $R/R4t-A.r6 $R/R4t-B.r6 --lag $lag --validate; done
echo "== held out: half B replayed with the shipped profile vs the profile from half A, and the other way round"
$P work/r11/replay10.py $SHIP $R/R4t-B.r6
$P work/r11/replay10.py $R/prof-A.bin $R/R4t-B.r6
$P work/r11/replay10.py $SHIP $R/R4t-A.r6
$P work/r11/replay10.py $R/prof-B.bin $R/R4t-A.r6
echo "== the full personal profile on both halves (in-sample, for scale)"
$P work/r11/replay10.py $R/prof-AB.bin $R/R4t-A.r6 $R/R4t-B.r6
