#!/usr/bin/env bash
# localize.sh - put this PC's own values back into a restored copy of local-ai-setup.
#
# The repo is published with placeholders (setup-stage/export.py wrote them):
#   /home/USER                      -> this user's $HOME
#   -home-USER-                     -> $HOME with "/" as "-" (the form ~/.claude/projects/ folder names use)
#   GPU-UUID-RTX5080 / UUID-RTX5080      -> the RTX 5080's UUID from `nvidia-smi -L` (with / without "GPU-")
#   GPU-UUID-RTX4060TI / UUID-RTX4060TI  -> the RTX 4060 Ti's UUID from `nvidia-smi -L`
# The real values are read at run time and written only into the files it changes; this script never stores them.
# Left as they are: HOSTNAME, EMAIL and UUID (scrubbed for privacy; nothing depends on them).
#
# Usage: ./localize.sh [--dry-run] [DIR]     DIR defaults to the folder this script is in.
#        --dry-run lists what would change (counts per file) and changes nothing.
set -euo pipefail

DRY=0
if [[ ${1:-} == --dry-run ]]; then DRY=1; shift; fi
DIR=${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
[[ -d $DIR ]] || { echo "localize: no such folder: $DIR" >&2; exit 2; }
[[ -n ${HOME:-} && $HOME == /* ]] || { echo "localize: \$HOME is not set to an absolute path" >&2; exit 2; }

U5080=""; U4060=""
if command -v nvidia-smi >/dev/null 2>&1; then
  while IFS= read -r line; do
    uuid=$(sed -n 's/.*(UUID: \(GPU-[0-9a-fA-F-]*\)).*/\1/p' <<<"$line")
    [[ -n $uuid ]] || continue
    case $line in
      *"RTX 5080"*) U5080=$uuid ;;
      *"RTX 4060 Ti"*) U4060=$uuid ;;
    esac
  done < <(nvidia-smi -L 2>/dev/null || true)
fi
[[ -n $U5080 ]] || echo "localize: no RTX 5080 in nvidia-smi -L - its placeholders stay" >&2
[[ -n $U4060 ]] || echo "localize: no RTX 4060 Ti in nvidia-smi -L - its placeholders stay" >&2

LOC_DIR=$DIR LOC_DRY=$DRY LOC_U5080=$U5080 LOC_U4060=$U4060 LOC_SELF=$(readlink -f "${BASH_SOURCE[0]}") \
python3 -I - <<'PY'
import os, sys
d, dry, home = os.environ["LOC_DIR"], os.environ["LOC_DRY"] == "1", os.environ["HOME"].rstrip("/")
u5, u4, me = os.environ["LOC_U5080"], os.environ["LOC_U4060"], os.environ["LOC_SELF"]
rules = [("/home/USER", home), ("-home-USER-", home.replace("/", "-") + "-")]
if u5:
    rules += [("GPU-UUID-RTX5080", u5), ("UUID-RTX5080", u5[4:])]
if u4:
    rules += [("GPU-UUID-RTX4060TI", u4), ("UUID-RTX4060TI", u4[4:])]
files = changed = 0
for dp, dns, fns in os.walk(d):
    dns[:] = [x for x in dns if x != ".git"]
    for fn in fns:
        p = os.path.join(dp, fn)
        if os.path.islink(p) or os.path.realpath(p) == me:
            continue
        try:
            raw = open(p, "rb").read()
        except OSError:
            continue
        if b"\0" in raw:
            continue
        try:
            t = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        files += 1
        new, counts = t, []
        for a, b in rules:          # GPU-UUID-* before UUID-*: the longer placeholder goes first
            n = new.count(a)
            if n:
                new = new.replace(a, b)
                counts.append(f"{a} x{n}")
        if new != t:
            changed += 1
            print(("would change " if dry else "changed ") + os.path.relpath(p, d) + ": " + ", ".join(counts))
            if not dry:
                st = os.stat(p)
                with open(p, "w", encoding="utf-8") as f:
                    f.write(new)
                os.chmod(p, st.st_mode & 0o7777)
print(f"localize: {changed} of {files} text files {'would change' if dry else 'changed'}")
PY
