#!/bin/bash
# switch028x.sh - called by work/r22/gap16.sh inside the gap (lock held, 8080 stopped) only when g16_rules.py decide says
# SWITCH (Karl 10-30, condition 5: "Switch 8080 to the port and tell me only if all of these hold"):
#   configs/P028x.json = configs/P021m.json (as served: pictures, the fallback) with the port's engine and server
#     (engine-r22p028x, strata-r22p028x/serve; branch r22-port028x = v0.2.8 + 28: both switches, exact v2), x28h's pinned
#     0.2.7 defaults, --conversation-cache-mib 0 and tool_call_recovery false (gap 15), and its own engine log
#   switch-model.sh / run-strata.sh default -> P028x.json (backups *.before-p028x); rollback STRATA_CONFIG=configs/P021m.json
#   work/r22/port_gap4.sh: the engine identity it checks at a gap end -> engine-r22p028x's (backup .before-p028x)
# port_gap4.sh end (gap16.sh) then starts it on 8080 and checks the sha and the chat-cache policy. Full rollback: copy the
# three .before-p028x files back.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
NEW_SHA=$(sha256sum engine-r22p028x/strata | cut -c1-12)
OLD_SHA=$(sha256sum engine-r22p021m/strata | cut -c1-12)
.venv/bin/python - <<'EOF'
import json
WS = "/home/USER/ai-speed-testing/strata-compare"
d = json.load(open(f"{WS}/configs/P021m.json"))
t, x = json.load(open(f"{WS}/configs/r21n-candpm.json")), json.load(open(f"{WS}/configs/x28h.json"))
assert d["exe"].endswith("engine-r22p021m/strata") and d["server"].endswith("strata-r22p021m/serve/server.py") and d.get("vision")
assert d["env"] == t["env"] and d["args"] == t["args"] + ["--vision"], "P021m.json is no longer r21n-candpm + --vision"
pins = {k: v for k, v in x["env"].items() if t["env"].get(k) != v}
assert x["args"] == t["args"] + ["--conversation-cache-mib", "0"] and set(x["env"]) >= set(t["env"]), "x28h is not r21n-candpm + the pins"
d["exe"], d["server"] = x["exe"], x["server"]
d["args"] = x["args"] + ["--vision"]
d["env"].update(pins)
d["tool_call_recovery"] = False
d["log"] = f"{WS}/logs/engine-P028x.log"
d["_comment"] = ("P028x (Karl 10-30, gap 16's switch rule): the v0.2.8 port (branch r22-port028x = v0.2.8 + 28, engine-r22p028x: "
                 "GR_FORK and PREFILL_V2 back, v2 bit-identical to v2 off) in P021m's served form (pictures, the fallback), with "
                 "0.2.7's new defaults pinned off (" + ", ".join(sorted(pins)) + "), 0.2.3's conversation cache off "
                 "(--conversation-cache-mib 0) and tool_call_recovery false. Rollback: STRATA_CONFIG=configs/P021m.json.")
json.dump(d, open(f"{WS}/configs/P028x.json", "w"), indent=1)
print("configs/P028x.json:", d["exe"], d["server"], "pins", sorted(pins))
EOF
cp -p configs/P021m.shared-settings.json configs/P028x.shared-settings.json 2> /dev/null || true
for f in switch-model.sh run-strata.sh; do
  cp -p $f $f.before-p028x
  sed -i 's#\${STRATA_CONFIG:-\$WS/configs/P021m.json}   \# 10-23: P021m (P021n + the continuation fix) promoted; rollback STRATA_CONFIG=\$WS/configs/P021n.json#${STRATA_CONFIG:-$WS/configs/P028x.json}   \# '"$(date +%m-%d)"': P028x (the v0.2.8 port, gap 16) promoted; rollback STRATA_CONFIG=$WS/configs/P021m.json#' $f
  grep -q 'configs/P028x.json}' $f || { echo "could not change the default in $f - restoring"; cp -p $f.before-p028x $f; exit 1; }
done
cp -p work/r22/port_gap4.sh work/r22/port_gap4.sh.before-p028x
sed -i "s#^P021_SHA=$OLD_SHA .*#P021_SHA=$NEW_SHA                          \# engine-r22p028x/strata (P028x, served since the gap 16 switch; P021m = $OLD_SHA is the rollback)#" work/r22/port_gap4.sh
grep -q "^P021_SHA=$NEW_SHA" work/r22/port_gap4.sh || { echo "could not set port_gap4.sh's sha - restoring everything"; cp -p work/r22/port_gap4.sh.before-p028x work/r22/port_gap4.sh; for f in switch-model.sh run-strata.sh; do cp -p $f.before-p028x $f; done; exit 1; }
sed -i "s/(configs default, P021m since 10-23)/(configs default, P028x since $(date +%m-%d))/" work/r22/port_gap4.sh
echo "switch prepared: default configs/P028x.json, engine sha $NEW_SHA; port_gap4.sh end starts it"
