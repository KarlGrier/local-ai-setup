#!/bin/bash
# switch021n.sh V2 WIDE IMMA [PCIE] - called by work/r22/gap8.sh inside the gap (lock held, 8080 stopped) when every check
# passed (the user, 10-21: switch 8080 mid-phase-4 to P021 + the two lossless ports; P021 stays the rollback):
#   configs/P021n.json = configs/P021.json (pictures: the CPU reader, budget 1000; answer_room on; the fallback) with the
#     backport's engine and server, --spec 7, STRATA_DRAFT_CUM=1, STRATA_PREFILL_V2=V2, STRATA_DEQUANT_WIDE=1 when WIDE=1,
#     STRATA_PROMPT_ATTN_IMMA=1 when IMMA=1; without the forced --pcie-frac 0 when PCIE=1 (the user, 10-22 12:2x:
#     pre-approved when it passes PC vs C, its 40-prompt KL check and the candidate checks); its own engine log
#   switch-model.sh / run-strata.sh default -> P021n.json (backups *.before-p021n)
#   work/r22/port_gap4.sh: the engine identity it checks at a gap end -> the backport's (backup .before-p021n)
# port_gap4.sh end (gap8.sh) then starts it on 8080 and checks the sha and the chat-cache policy.
set -euo pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
V2=${1:?v2 value}; WIDE=${2:?}; IMMA=${3:?}; PCIE=${4:-0}
NEW_SHA=$(sha256sum engine-r22p021n/strata | cut -c1-12)
.venv/bin/python - "$V2" "$WIDE" "$IMMA" "$PCIE" <<'EOF'
import json, sys
v2, wide, imma, pcie = sys.argv[1], sys.argv[2] == "1", sys.argv[3] == "1", sys.argv[4] == "1"
WS = "/home/USER/ai-speed-testing/strata-compare"
d = json.load(open(f"{WS}/configs/P021.json"))
assert d["exe"].endswith("engine-r22p021/strata") and d.get("vision")
d["exe"] = f"{WS}/engine-r22p021n/strata"
d["server"] = f"{WS}/strata-r22p021n/serve/server.py"
a = d["args"]; a[a.index("--spec") + 1] = "7"
d["env"]["STRATA_DRAFT_CUM"] = "1"
d["env"]["STRATA_PREFILL_V2"] = v2
if wide:
    d["env"]["STRATA_DEQUANT_WIDE"] = "1"
if imma:
    d["env"]["STRATA_PROMPT_ATTN_IMMA"] = "1"
if pcie:
    i = a.index("--pcie-frac"); assert a[i + 1] == "0"; del a[i:i + 2]
d["log"] = f"{WS}/logs/engine-P021n.log"
d["_comment"] = ("P021n (the user, 10-21: switched mid-phase-4 after gap 8's checks): the P021 backport (branch r22-port021-next "
                 "= P021 + the cost gate past its table + STRATA_DRAFT_CUM + STRATA_PREFILL_V2, engine-r22p021n) with arm C "
                 f"(--spec 7, STRATA_DRAFT_CUM=1), STRATA_PREFILL_V2={v2}" + (", STRATA_DEQUANT_WIDE=1" if wide else "")
                 + (", STRATA_PROMPT_ATTN_IMMA=1" if imma else "") + (", no forced --pcie-frac 0" if pcie else "") + "; otherwise P021's flags, pictures (CPU reader, "
                 "budget 1000) and answer_room. Rollback: STRATA_CONFIG=configs/P021.json.")
json.dump(d, open(f"{WS}/configs/P021n.json", "w"), indent=1)
print("configs/P021n.json:", {k: d["env"][k] for k in ("STRATA_DRAFT_CUM", "STRATA_PREFILL_V2") }, "spec", a[a.index("--spec") + 1],
      "pcie-frac", a[a.index("--pcie-frac") + 1] if "--pcie-frac" in a else "not forced")
EOF
cp -p configs/P021.shared-settings.json configs/P021n.shared-settings.json 2> /dev/null || true
for f in switch-model.sh run-strata.sh; do
  cp -p $f $f.before-p021n
  sed -i 's#\${STRATA_CONFIG:-\$WS/configs/P021.json}   \# 10-20: P021 (0.2.1) promoted; rollback STRATA_CONFIG=\$WS/configs/Cstar18t.json#${STRATA_CONFIG:-$WS/configs/P021n.json}   \# 10-22: P021n (the P021 backport) promoted mid-phase-4; rollback STRATA_CONFIG=$WS/configs/P021.json#' $f
  grep -q 'configs/P021n.json}' $f || { echo "could not change the default in $f - restoring"; cp -p $f.before-p021n $f; exit 1; }
done
cp -p work/r22/port_gap4.sh work/r22/port_gap4.sh.before-p021n
sed -i "s#^P021_SHA=c9fe314316c4 .*#P021_SHA=$NEW_SHA                          \# engine-r22p021n/strata (P021n, served since the gap 8 switch; P021 = c9fe314316c4 is the rollback)#" work/r22/port_gap4.sh
grep -q "^P021_SHA=$NEW_SHA" work/r22/port_gap4.sh || { echo "could not set port_gap4.sh's sha - restoring everything"; cp -p work/r22/port_gap4.sh.before-p021n work/r22/port_gap4.sh; for f in switch-model.sh run-strata.sh; do cp -p $f.before-p021n $f; done; exit 1; }
echo "switch prepared: default configs/P021n.json, engine sha $NEW_SHA; port_gap4.sh end starts it"
