#!/bin/bash
# s6_session.sh CFG — round 14 step 6 (report only, 1 hour): session files with my config (CFG = the candidate) for a
# 40K and a 190K chat (the 190K one with --max-context 262144, as configs/Cstar13-262k.json). Per size: server 1 builds
# the chat, saves, parks it behind another chat, restores, continues (+ the short chat again); server 2 (fresh) is the
# control without save / restore; server 3 (fresh) restores in a new process and continues. work/r14/s6_session.py.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
CFG=${1:?config}; D=$WS/work/r14/cfg; mkdir -p $D tmp/r14/sessions; chmod 700 tmp/r14/sessions
for size in 40k 190k; do
  .venv/bin/python - $CFG $D/s6-$size.json $size <<'PY'
import json, sys, shutil
from pathlib import Path
src, dst, size = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
c = json.loads(src.read_text())
c["slot_save_path"] = "/home/USER/ai-speed-testing/strata-compare/tmp/r14/sessions"
a = c["args"]
if size == "190k":
    a[a.index("--max-context") + 1] = "262144"
c["log"] = str(dst.with_suffix(".log"))
dst.write_text(json.dumps(c, indent=1) + "\n")
sh = src.with_suffix("").as_posix() + ".shared-settings.json"
if Path(sh).exists(): shutil.copy(sh, dst.with_suffix("").as_posix() + ".shared-settings.json")
PY
  N=40000; [ $size = 190k ] && N=190000
  L=r14-s6-$size; C=$D/s6-$size.json; E=$D/s6-$size.log
  rm -f tmp/r14/s6/$L.json tmp/r14/sessions/$L.bin
  bringup/lib/srv.sh start $L-build $C && { .venv/bin/python work/r14/s6_session.py http://127.0.0.1:8081 $L $N build $E
      .venv/bin/python work/r14/s6_session.py http://127.0.0.1:8081 $L $N back $E; }; bringup/lib/srv.sh stop
  bringup/lib/srv.sh start $L-control $C && .venv/bin/python work/r14/s6_session.py http://127.0.0.1:8081 $L $N control $E; bringup/lib/srv.sh stop
  bringup/lib/srv.sh start $L-restart $C && .venv/bin/python work/r14/s6_session.py http://127.0.0.1:8081 $L $N restart $E; bringup/lib/srv.sh stop
  .venv/bin/python work/r14/s6_session.py http://127.0.0.1:8081 $L $N compare
  ls -la tmp/r14/sessions/
done
