#!/bin/bash
# coldstart.sh - 2026-10-17, your item 3d: how long a cold start takes from clicking the "Jan (Strata)" icon to the
# first answer. Strata stopped and Jan closed first; the icon is "clicked" with gtk-launch (the same desktop entry).
#   T0 click -> T1 Strata ready (/health: loaded) -> T2 Jan's window is on screen -> first answer to Jan's own first
#   request (recorded from Jan through the request monitor, user text replaced), sent the moment the window is up:
#   time to the first token and to the end. Typing time is not included.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
REQ=${1:-tmp/usability/jan-first-request.json}
[ -f "$REQ" ] || { echo "no recorded Jan request at $REQ"; exit 1; }
curl -s -m 2 http://127.0.0.1:8080/health > /dev/null && { echo "8080 is up: stop it first"; exit 1; }
[ -n "$(ps -eo args | grep -E '[J]an_0\.8\.6|[.]mount_Jan')" ] && { echo "Jan is open: close it first"; exit 1; }
now() { date +%s.%N; }
dt() { awk "BEGIN {printf \"%.1f\", $2 - $1}"; }
jan_window() {
  for w in $(xprop -root _NET_CLIENT_LIST 2>/dev/null | grep -o '0x[0-9a-f]*'); do
    xprop -id "$w" WM_CLASS 2>/dev/null | grep -qi 'jan' && return 0
  done
  return 1
}
free -g | awk '/Mem:/ {print "RAM available before: " $7 " GiB"}'
T0=$(now)
gtk-launch jan-strata > /dev/null 2>&1 &
until curl -s -m 2 http://127.0.0.1:8080/health 2>/dev/null | grep -q '"loaded": *true'; do
  sleep 0.2; [ "$(dt "$T0" "$(now)" | cut -d. -f1)" -gt 300 ] && { echo "not ready after 300 s"; exit 1; }
done
T1=$(now)
until jan_window; do
  sleep 0.2; [ "$(dt "$T0" "$(now)" | cut -d. -f1)" -gt 400 ] && { echo "no Jan window after 400 s"; exit 1; }
done
T2=$(now)
.venv/bin/python - "$REQ" <<'EOF' > tmp/usability/coldstart-answer.txt
import json, sys, time, urllib.request
body = json.load(open(sys.argv[1]))
body["stream"] = True
t0 = time.time(); first = None; n = 0
req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=600) as r:
    for line in r:
        if not line.startswith(b"data: ") or line.strip() == b"data: [DONE]":
            continue
        d = json.loads(line[6:])
        delta = (d.get("choices") or [{}])[0].get("delta") or {}
        if first is None and (delta.get("content") or delta.get("reasoning_content")):
            first = time.time() - t0
        n += 1
print(f"{first:.1f} {time.time() - t0:.1f} {n}")
EOF
read FIRST TOTAL CHUNKS < tmp/usability/coldstart-answer.txt
echo "click -> Strata ready:        $(dt "$T0" "$T1") s"
echo "ready -> Jan window on screen: $(dt "$T1" "$T2") s   (click -> window $(dt "$T0" "$T2") s)"
echo "first request: first token after ${FIRST} s, answer done after ${TOTAL} s ($CHUNKS chunks)"
echo "click -> first answer (without typing): $(awk "BEGIN {printf \"%.1f\", $(dt "$T0" "$T2") + $TOTAL}") s"
tail -3 logs/run/strata-ensure.log
