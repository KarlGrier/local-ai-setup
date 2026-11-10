#!/usr/bin/env python3
"""delete.py WHEN - delete the manifest's entries for WHEN ("now" or "after"), each checked to lie under an approved
prefix; one log line per entry (work/cleanup-1027/deleted.log). Run under ionice -c3 (idle IO)."""
import json, os, shutil, sys, time
S = "/home/USER/ai-speed-testing/strata-compare"
H = os.path.expanduser("~")
OK = (f"{S}/bringup/out/", f"{S}/tmp/", f"{S}/strata-", f"{S}/engine-", f"{H}/.cache/uv", f"{H}/.cache/pip",
      f"{H}/.cache/usability-downloads", f"{H}/ai/deep-research/tmp/", f"{H}/ai/deep-research/cache",
      f"{S}/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf")
when = {"now": "now", "after": "after the LDR rerun"}[sys.argv[1]]
rows = [r for r in json.load(open(f"{S}/work/cleanup-1027/manifest.json")) if r["when"] == when]
log = open(f"{S}/work/cleanup-1027/deleted.log", "a")
gone = 0.0
for r in rows:
    p = r["path"]
    assert p.startswith(OK) and "/models/" not in p.replace("dspark-DeepSeek", "") or p.endswith("dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf"), p
    assert os.path.basename(p) not in ("r20a", "r5") and not p.startswith(f"{S}/tmp/r5"), p
    if not os.path.lexists(p):
        continue
    if os.path.isdir(p) and not os.path.islink(p):
        shutil.rmtree(p)
    else:
        os.remove(p)
    gone += r["gb"]
    log.write(f"{time.strftime('%m-%d %H:%M:%S')} {r['gb']:8.3f} GB {r['group']}: {p}\n")
log.close()
print(f"{len(rows)} entries ({when}): {gone:.1f} GB deleted")
