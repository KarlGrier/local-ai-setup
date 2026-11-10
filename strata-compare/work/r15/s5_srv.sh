#!/bin/bash
# s5_srv.sh NAME CONFIG.json OPTION... — round 15 step 5 for a placement the engine runs only with --serve (the layer split):
# each setting ALONE against the config as it is, A B B A, each arm a fresh guarded server (cold model page cache): a
# warm-up, then two requests of the math prompt at YOUR sampling settings (the config's shared settings), 1,024 tokens;
# decode from the engine's per-request lines (work/r15/s5_srv_arm.py). OPTION = NAME:ENV or NAME:ENV:ARG=VAL as in
# s4_filetier.sh. Keep at >= +3 %. Table -> results/r15/s5-NAME.md
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
N=$1 CFG=$2; shift 2
D=$WS/work/r15/cfg; mkdir -p $D results/r15/s5
PY=.venv/bin/python
arm() {   # arm LABEL CFG
  local L=$1 C=$2 E; E=$($PY -c "import json; print(json.load(open('$C'))['log'])"); touch "$E"
  $PY scripts/evict.py ${EVICT_GLOB:-} > /dev/null
  bringup/lib/srv.sh start $L "$C" > /dev/null 2>&1 || { echo "$L did not start"; return; }
  $PY work/r15/s5_srv_arm.py $L "$E"
  bringup/lib/srv.sh stop > /dev/null 2>&1
}
T0=$(date +%s)
for opt in "$@"; do
  IFS=: read -r on env arg <<< "$opt"
  # round 15: your 2-hour limit per file - no new setting once S5_MIN (120) minutes have gone
  if [ $(( ($(date +%s) - T0) / 60 )) -ge ${S5_MIN:-120} ]; then echo "s5 $N $on: skipped (the ${S5_MIN:-120}-minute limit)"; echo "$on" >> results/r15/s5/$N-skipped.txt; continue; fi
  # the split point and the prompt chunk are judged by the prompt read too: each arm also reads the 32K prompt
  case $on in split*|chunk*) export S5_PROMPT=1;; *) unset S5_PROMPT;; esac
  C2=$D/s5-$N-$on.json
  $PY - "$CFG" "$C2" "${env}" "${arg:-}" <<'PY'
import json, sys
from pathlib import Path
c = json.loads(Path(sys.argv[1]).read_text()); a = c["args"]
env, arg = sys.argv[3], sys.argv[4]
if env and env != "-":
    for kv in env.split(","):
        k, v = kv.split("=", 1); c["env"][k] = v
if arg:
    f, v = arg.split("=", 1)
    if f in a: a[a.index(f) + 1] = v
    else: a.extend([f, v])
c["log"] = c["log"].replace(".log", f"-s5.log")
Path(sys.argv[2]).write_text(json.dumps(c, indent=1) + "\n")
sh = Path(sys.argv[1]).with_suffix("").as_posix() + ".shared-settings.json"
if Path(sh).exists():
    Path(Path(sys.argv[2]).with_suffix("").as_posix() + ".shared-settings.json").write_text(Path(sh).read_text())
PY
  arm s5-$N-$on-base-a $CFG; arm s5-$N-$on-opt-a $C2
  # a split/chunk option the engine did not apply (the same chunk and stages as the base, e.g. a chunk it shrank back to
  # what the 4060 Ti can fund) or that did not start: reported as such after one arm, its other two arms skipped
  NOOP=$($PY - results/r15/s5/s5-$N-$on-base-a.json results/r15/s5/s5-$N-$on-opt-a.json "$on" <<'PY'
import json, sys
from pathlib import Path
b, o, on = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
if not o.exists(): print("did not start or did not answer (see the arm's server log)")
elif on.startswith(("split", "chunk")) and b.exists():
    jb, jo = json.loads(b.read_text()), json.loads(o.read_text())
    if (jb.get("chunk"), jb.get("split")) == (jo.get("chunk"), jo.get("split")):
        print(f"no effect: the engine ran the same {jo.get('chunk')}-token chunk and split ({jo.get('split')})")
PY
)
  if [ -n "$NOOP" ]; then echo "s5 $N $on: $NOOP"; echo "$NOOP" > results/r15/s5/s5-$N-$on-noop.txt; continue; fi
  arm s5-$N-$on-opt-b $C2; arm s5-$N-$on-base-b $CFG
done
$PY - $N "$@" <<'PY' > results/r15/s5-$N.md
import json, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
name = sys.argv[1]
print(f"# Round 15 step 5 — settings, {name} (served: each arm a fresh server, warm-up + 2 requests of the math prompt at your sampling, 1,024 tokens)\n")
print("| option | base tok/s (a / b) | option tok/s (a / b) | change | base arms' spread | kept (split/chunk: shorter 32K read at >= -3 % decode; others >= +3 %) |\n|---|---|---|---|---|---|")
for opt in sys.argv[2:]:
    on = opt.split(":")[0]
    v = {}
    for k in ("base-a", "opt-a", "opt-b", "base-b"):
        f = WS / f"results/r15/s5/s5-{name}-{on}-{k}.json"
        v[k] = json.loads(f.read_text())["tps"] if f.exists() else None
    b = [v["base-a"], v["base-b"]]; o = [v["opt-a"], v["opt-b"]]
    nf = WS / f"results/r15/s5/s5-{name}-{on}-noop.txt"
    if nf.exists():
        ex = ""
        for k in ("base-a", "opt-a"):
            f = WS / f"results/r15/s5/s5-{name}-{on}-{k}.json"
            if f.exists():
                j = json.loads(f.read_text())
                ex += f" {k}: {j['tps']:.2f} tok/s, chunk {j.get('chunk')}" + (f", 32K read {j['prompt_ms'] / 1000:.1f} s" if j.get("prompt_ms") else "") + ";"
        print(f"| {opt} | – | – | {nf.read_text().strip()}{ex} | – | no |"); continue
    if None in b or None in o:
        print(f"| {opt} | {b} | {o} | – | – | did not run (see the arm's server log) |"); continue
    ch = 100 * (sum(o) / sum(b) - 1); sp = 100 * (max(b) / min(b) - 1)
    pr = {}
    for k in ("base-a", "opt-a", "opt-b", "base-b"):
        f = WS / f"results/r15/s5/s5-{name}-{on}-{k}.json"
        pr[k] = json.loads(f.read_text()).get("prompt_ms") if f.exists() else None
    if all(pr.values()):   # your rule for the split point / the chunk: a shorter prompt read at no more than -3 % decode
        pb = (pr["base-a"] + pr["base-b"]) / 2; po = (pr["opt-a"] + pr["opt-b"]) / 2; pch = 100 * (po / pb - 1)
        keep = po < pb and ch >= -3
        print(f"| {opt} | {b[0]:.2f} / {b[1]:.2f} | {o[0]:.2f} / {o[1]:.2f} | **{ch:+.1f} %**; 32K read {pb / 1000:.1f} → {po / 1000:.1f} s (**{pch:+.1f} %**) | {sp:.1f} % | {'KEEP' if keep else 'no'} |")
    else:
        print(f"| {opt} | {b[0]:.2f} / {b[1]:.2f} | {o[0]:.2f} / {o[1]:.2f} | **{ch:+.1f} %** | {sp:.1f} % | {'KEEP' if ch >= 3 else 'no'} |")
PY
cat results/r15/s5-$N.md
