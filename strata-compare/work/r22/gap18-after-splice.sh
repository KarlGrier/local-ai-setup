#!/bin/bash
# gap18-after-splice.sh (11-03): starts work/r22/gap18.sh once the splice rerun (user unit sweep-splice58) has ended -
# the two gaps must not overlap (both hold the test lock shared and use port 8081). Waits at most 3 h.
for i in $(seq 1080); do systemctl --user is-active -q sweep-splice58.service || break; sleep 10; done
systemctl --user is-active -q sweep-splice58.service && { echo "$(date '+%F %T') the splice rerun is still running after 3 h - gap 18 not started"; exit 1; }
sleep 30
exec /bin/bash /home/USER/ai-speed-testing/strata-compare/work/r22/gap18.sh
