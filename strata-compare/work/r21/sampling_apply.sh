#!/bin/bash
# sampling_apply.sh - 2026-10-16, your sampling on every path (T 1.0, top-p 0.95, top-k 20, min-p 0.05), applied after
# the FP4-Local / NVFP4 measurements:
#   OpenCode: "body" temperature 0.6 -> 1.0 (configs/usability/opencode/opencode.jsonc; comment corrected)
#   8080's fallback: the "sampling" block's temperature 0.6 -> 1.0 in configs/Cstar18t.json (served), Cstar18.json
#     (rollback) and Cstar18-single.json (fallback), so a client that sends nothing gets your settings even without the
#     Chat settings file (which cannot hold min-p; the block supplies 0.05)
#   dsh, Codex: send no sampling -> the fallback above; Jan: sends 1.0 / 0.95 / 20, min-p from the fallback
#   configs/usability/README.md: the sampling paragraph
# Backups: work/r21/*.before-sampling.  Does not restart anything (night_chain.sh does).
set -eu
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
B=work/r21
cp -p configs/usability/opencode/opencode.jsonc $B/opencode.jsonc.before-sampling
cp -p configs/usability/README.md $B/usability-README.md.before-sampling
for c in Cstar18t Cstar18 Cstar18-single; do cp -p configs/$c.json $B/$c.json.before-sampling || true; done
.venv/bin/python - <<'PY'
from pathlib import Path
import json
WS = Path("/home/USER/ai-speed-testing/strata-compare")
def swap(p, old, new):
    s = p.read_text()
    if s.count(old) != 1:
        raise SystemExit(f"{p}: expected the text once, found {s.count(old)}: {old[:60]!r}")
    p.write_text(s.replace(old, new))
oc = WS / "configs/usability/opencode/opencode.jsonc"
swap(oc, """          // Strata C*18's own defaults (configs/Cstar18.json "sampling"), sent explicitly so OpenCode's model-family
          // defaults cannot apply; Codex cannot send sampling at all, so all three harnesses run at these
          "body": { "temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0.05 }""",
"""          // your sampling (2026-10-16), sent explicitly so OpenCode's model-family defaults cannot apply; Strata
          // gives clients that send none (dsh, Codex; Jan's missing min-p) the same since 2026-10-16
          "body": { "temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05 }""")
rd = WS / "configs/usability/README.md"
swap(rd, """* The coding harnesses use Strata's default sampling (temperature 0.6, top-p 0.95, top-k 20, min-p 0.05; Codex has no
  way to send sampling, so all three run alike) and reasoning effort xhigh.""",
"""* Every path runs at your sampling: temperature 1.0, top-p 0.95, top-k 20, min-p 0.05, reasoning effort xhigh
  (since 2026-10-16; until then OpenCode sent 0.6). OpenCode sends it itself; dsh and Codex send no sampling and get
  Strata's defaults (the config's "sampling" block, now the same values, plus the Chat settings file).""")
for c in ("Cstar18t", "Cstar18", "Cstar18-single"):
    p = WS / f"configs/{c}.json"
    swap(p, '"temperature": 0.6', '"temperature": 1.0')
    s = json.loads(p.read_text())["sampling"]
    assert s == {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}, (c, s)
    print(c, "sampling", s)
PY
for f in configs/usability/opencode/opencode.jsonc configs/usability/README.md; do diff $B/$(basename $f | sed 's/README.md/usability-README.md/').before-sampling $f || true; done
for c in Cstar18t Cstar18 Cstar18-single; do diff $B/$c.json.before-sampling configs/$c.json || true; done
echo "sampling applied"
