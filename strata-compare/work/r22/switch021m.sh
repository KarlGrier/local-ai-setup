#!/bin/bash
# switch021m.sh - called by work/r22/gap10.sh inside the gap (lock held, 8080 stopped) when every check passed (the user,
# 10-23: "switch 8080 to it if they all pass ... keep the current build as rollback"):
#   configs/P021m.json = configs/P021n.json (as served since gap 9: no forced --pcie-frac 0; pictures, answer_room, the
#     fallback) with the continuation fix's engine and server (engine-r22p021m, strata-r22p021m/serve; branch
#     r22-port021-cont2 = P021n + a653ae6c) and its own engine log
#   switch-model.sh / run-strata.sh default -> P021m.json (backups *.before-p021m); rollback STRATA_CONFIG=configs/P021n.json
#   work/r22/port_gap4.sh: the engine identity it checks at a gap end -> engine-r22p021m's (backup .before-p021m)
# port_gap4.sh end (gap10.sh) then starts it on 8080 and checks the sha and the chat-cache policy.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
NEW_SHA=$(sha256sum engine-r22p021m/strata | cut -c1-12)
OLD_SHA=$(sha256sum engine-r22p021n/strata | cut -c1-12)
.venv/bin/python - <<'EOF'
import json
WS = "/home/USER/ai-speed-testing/strata-compare"
d = json.load(open(f"{WS}/configs/P021n.json"))
assert d["exe"].endswith("engine-r22p021n/strata") and d["server"].endswith("strata-r22p021n/serve/server.py") and d.get("vision")
assert "--pcie-frac" not in d["args"], "P021n.json is expected without the forced --pcie-frac 0 (gap 9)"
d["exe"] = f"{WS}/engine-r22p021m/strata"
d["server"] = f"{WS}/strata-r22p021m/serve/server.py"
d["log"] = f"{WS}/logs/engine-P021m.log"
d["_comment"] = ("P021m (the user, 10-23: switched after gap 10's checks): P021n as served since gap 9 (arm C + STRATA_PREFILL_V2 + "
                 "STRATA_DEQUANT_WIDE, no forced --pcie-frac 0) with the answer_room continuation fix in its minimal form "
                 "(branch r22-port021-cont2 = P021n + a653ae6c, engine-r22p021m: keep=1 for one-shot calls + tcap/tend, the "
                 "engine stops at the thinking budget itself). Rollback: STRATA_CONFIG=configs/P021n.json.")
json.dump(d, open(f"{WS}/configs/P021m.json", "w"), indent=1)
print("configs/P021m.json:", d["exe"], d["server"])
EOF
cp -p configs/P021n.shared-settings.json configs/P021m.shared-settings.json 2> /dev/null || true
for f in switch-model.sh run-strata.sh; do
  cp -p $f $f.before-p021m
  sed -i 's#\${STRATA_CONFIG:-\$WS/configs/P021n.json}   \# 10-22: P021n (the P021 backport) promoted mid-phase-4; rollback STRATA_CONFIG=\$WS/configs/P021.json#${STRATA_CONFIG:-$WS/configs/P021m.json}   \# 10-23: P021m (P021n + the continuation fix) promoted; rollback STRATA_CONFIG=$WS/configs/P021n.json#' $f
  grep -q 'configs/P021m.json}' $f || { echo "could not change the default in $f - restoring"; cp -p $f.before-p021m $f; exit 1; }
done
cp -p work/r22/port_gap4.sh work/r22/port_gap4.sh.before-p021m
sed -i "s#^P021_SHA=$OLD_SHA .*#P021_SHA=$NEW_SHA                          \# engine-r22p021m/strata (P021m, served since the gap 10 switch; P021n = $OLD_SHA is the rollback)#" work/r22/port_gap4.sh
grep -q "^P021_SHA=$NEW_SHA" work/r22/port_gap4.sh || { echo "could not set port_gap4.sh's sha - restoring everything"; cp -p work/r22/port_gap4.sh.before-p021m work/r22/port_gap4.sh; for f in switch-model.sh run-strata.sh; do cp -p $f.before-p021m $f; done; exit 1; }
sed -i 's/(configs default, P021n since 10-22)/(configs default, P021m since 10-23)/' work/r22/port_gap4.sh
echo "switch prepared: default configs/P021m.json, engine sha $NEW_SHA; port_gap4.sh end starts it"
