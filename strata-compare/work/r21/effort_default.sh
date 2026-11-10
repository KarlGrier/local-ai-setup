#!/bin/bash
# effort_default.sh LEVEL - 2026-10-17, your item 2: the default reasoning effort on every path -> LEVEL (medium, or low
# if low scored at least as well as medium in every category): 8080's fallback (the Chat settings, live through
# POST /settings, as the chat page does it; saved to configs/Cstar18t.shared-settings.json) and the rollback configs'
# files, OpenCode, Codex (template + ~/.codex-strata copy), dsh (template; ~/.dsh does not exist yet), Jan's default
# assistant (Jan must be closed). A request that names a level keeps it (server.py with_shared fills one in only where
# a request has none), so xhigh stays available: OpenCode variants (/variants, -m strata/qwen3.8-flash#xhigh), Codex
# -c model_reasoning_effort="xhigh" or /model, dsh's level menu, Jan's assistant parameters.
# Backups: work/r21/effort-default-backup/. Run when no harness or suite run uses these files.
set -eu
LV=${1:?usage: effort_default.sh medium|low}
case $LV in medium|low) ;; *) echo "medium or low only"; exit 2;; esac
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
B=work/r21/effort-default-backup; mkdir -p $B
U=configs/usability; JAN=$HOME/.local/share/Jan/data/assistants/jan/assistant.json
step() { echo "=== $(date -Is) $*"; }
pgrep -f "$HOME/.local/opt/jan" > /dev/null && { echo "Jan is running: close it first"; exit 3; }
for f in configs/Cstar18t.shared-settings.json configs/Cstar18.shared-settings.json \
         configs/Cstar18-single.shared-settings.json $U/opencode/opencode.jsonc $U/codex/config.toml \
         $HOME/.codex-strata/config.toml $U/dsh/web.cordis.patch.yml $U/jan/jan_config.py $JAN; do
  n=$(echo "$f" | sed "s|$HOME/||; s|/|__|g"); [ -e "$B/$n" ] || cp -p "$f" "$B/$n"
done

step "1 8080's fallback (the Chat settings) -> $LV, live"
body=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); d['reasoning_effort']=sys.argv[2]; print(json.dumps({'defaults': d}))" \
       configs/Cstar18t.shared-settings.json $LV)
curl -s -m 10 -X POST -H 'Content-Type: application/json' -d "$body" http://127.0.0.1:8080/settings; echo
echo "saved: $(tr -d '\n ' < configs/Cstar18t.shared-settings.json)"
for c in Cstar18 Cstar18-single; do     # the rollback configs, so a rollback keeps the level
  python3 -c "import json,sys; p=sys.argv[1]; d=json.load(open(p)); d['reasoning_effort']=sys.argv[2]; open(p,'w').write(json.dumps(d, indent=1))" \
    configs/$c.shared-settings.json $LV
  echo "$c: $(tr -d '\n ' < configs/$c.shared-settings.json)"
done

step "2 OpenCode -> $LV, with variants low / medium / xhigh"
python3 - "$LV" <<'EOF'
import sys
from pathlib import Path
lv = sys.argv[1]
p = Path("configs/usability/opencode/opencode.jsonc"); s = p.read_text()
old = '          "settings": { "reasoningEffort": "xhigh" },\n'
assert s.count(old) == 1, "OpenCode settings line not found"
new = (f'          "settings": {{ "reasoningEffort": "{lv}" }},\n'
       '          // 2026-10-17: default level from the suite runs (REPORT.md Round 21); the others on demand:\n'
       '          // /variants in the TUI, or -m strata/qwen3.8-flash#xhigh\n'
       '          "variants": [\n'
       '            { "id": "low", "settings": { "reasoningEffort": "low" } },\n'
       '            { "id": "medium", "settings": { "reasoningEffort": "medium" } },\n'
       '            { "id": "xhigh", "settings": { "reasoningEffort": "xhigh" } }\n'
       '          ],\n')
p.write_text(s.replace(old, new))
EOF
grep -n 'reasoningEffort' $U/opencode/opencode.jsonc

step "3 Codex -> $LV (template and ~/.codex-strata copy)"
for f in $U/codex/config.toml $HOME/.codex-strata/config.toml; do
  sed -i "s|^model_reasoning_effort = \"xhigh\"\$|model_reasoning_effort = \"$LV\"    # 2026-10-17; xhigh on demand: -c model_reasoning_effort=\"xhigh\" or /model|" "$f"
  grep -n '^model_reasoning_effort' "$f"
done

step "4 dsh -> $LV (the profile template; the level menu keeps every level)"
sed -i "s|^        reasoning: xhigh\$|        reasoning: $LV                       # the default level (2026-10-17); the menu offers the others|" \
  $U/dsh/web.cordis.patch.yml
grep -n '^        reasoning:' $U/dsh/web.cordis.patch.yml

step "5 Jan's default assistant -> $LV (new chats; existing chats keep their own)"
python3 - "$LV" "$JAN" <<'EOF'
import json, sys
from pathlib import Path
lv, p = sys.argv[1], Path(sys.argv[2])
a = json.loads(p.read_text())
a["parameters"]["reasoning_effort"] = lv
p.write_text(json.dumps(a, indent=2, ensure_ascii=False))
print(p.name, a["parameters"])
c = Path("configs/usability/jan/jan_config.py"); s = c.read_text()
s = s.replace('"min_p": 0.05, "reasoning_effort": "xhigh"}', f'"min_p": 0.05, "reasoning_effort": "{lv}"}}')
s = s.replace("top_k 20, min_p 0.05, reasoning_effort xhigh\n", f"top_k 20, min_p 0.05, reasoning_effort {lv}\n"
              f"    (xhigh until 2026-10-17)\n")
c.write_text(s)
r = Path("configs/usability/jan/settings-applied.json"); t = json.loads(r.read_text())
for k, v in t.items():
    if k.startswith("assistant ") and isinstance(v, dict) and "parameters" in v:
        v["parameters"]["reasoning_effort"] = lv
r.write_text(json.dumps(t, indent=1) + "\n")
EOF
grep -n 'reasoning_effort' $U/jan/jan_config.py | head -3
step "done"
