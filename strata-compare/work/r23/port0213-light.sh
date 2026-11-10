#!/bin/bash
# port0213-light.sh (Karl 11-09, v0.2.13 groundwork item 1 + the stock tree): the CPU-light steps, each through
# work/r23/nogap-run.sh (nice 19; waits while a gap is open, freezes if one opens). No GPU, no engine, no download:
#   1 the stock v0.2.13 worktree strata-v0213stock (upstream's intake tool runs from it; never our patched tree)
#   2 upstream's tools/test_qwen4_intake.py (fixtures only; TMPDIR inside the work folder)
#   3 work/qwen4-kit/intake_hook.py selftest (synthetic reports, a fake tool, the real nogap-run)
#   4 the patched HF watch, one synthetic dry poll with the fake tool (inline path: no gap open)
#   5 the intake on our local files: the ISTA IQ3_S set, the saved unsloth header stubs, the DeepSeek UD-Q8_K_XL set
#   6 the --hf path on one small folder of unsloth's Flash-Next repo at the pinned commit (header range reads only)
# Log: results/r23/port-0213/intake/light.log
set -u
SC=/home/USER/ai-speed-testing/strata-compare
NG="/bin/bash $SC/work/r23/nogap-run.sh"; PY=$SC/.venv/bin/python; ST=$SC/strata-v0213stock; K=$SC/work/qwen4-kit
OUT=$SC/results/r23/port-0213/intake; L=$OUT/light.log; T=$SC/work/r23/scratch-port0213/tmp
mkdir -p "$OUT" "$T"
say() { echo "=== $(date '+%F %T') $*" >> "$L"; }
say "port0213-light start (pid $$)"
if [ ! -d "$ST" ]; then
  say "1 stock worktree"
  $NG "$L" ionice -c3 git -C $SC/strata worktree add --detach "$ST" v0.2.13 || { say "1 FAILED"; exit 1; }
fi
say "1 stock tree: $(git -C "$ST" describe --tags 2> /dev/null) $(git -C "$ST" rev-parse --short HEAD) clean: $(git -C "$ST" status --porcelain | wc -l) changes"
say "2 upstream test_qwen4_intake.py"
TMPDIR=$T $NG "$L" ionice -c3 $PY -I -B "$ST/tools/test_qwen4_intake.py" -v; say "2 rc $?"
say "3 intake_hook selftest"
$PY -I -B $K/intake_hook.py selftest $K/scratch-f/selftest >> "$L" 2>&1; say "3 rc $?"
say "4 synthetic dry poll (fake tool, inline)"
rm -f $K/scratch-f/watch/state.json
Q4_INTAKE_TOOL=$K/scratch-f/selftest/fake_intake.py $PY -I -B $K/dayone.py watch --dry --force --no-download \
  --synthetic $K/scratch-f/watch/synthetic.json --state $K/scratch-f/watch/state.json --out $K/scratch-f/watch/plans >> "$L" 2>&1; say "4 rc $?"
say "5 local intake"
H=$K/unsloth-v31/headers
for x in "ista-iq3s $SC/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf" \
         "ud31-iq3xxs-stub $H/UD-IQ3_XXS" "ud31-iq2xs-stub $H/UD-IQ2_XS" "pre31-q2kxl-stub $H/pre-v31/UD-Q2_K_XL" \
         "pre31-iq3xxs-stub $H/pre-v31/UD-IQ3_XXS" "mtp-stub $H/MTP" \
         "ds41-udq8kxl $SC/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/DeepSeek-V4.1-Flash-1017-UD-Q8_K_XL-00001-of-00009.gguf"; do
  set -- $x
  say "5 $1"
  $PY -I -B $K/intake_hook.py local "$OUT/$1" "$2" >> "$L" 2>&1; say "5 $1 rc $?"
done
say "6 --hf unsloth Flash-Next UD-IQ3_XXS folder at d96201194f10"
mkdir -p "$OUT/hf-unsloth-iq3xxs"
$NG "$L" $PY -I -B "$ST/tools/qwen4_intake.py" --hf unsloth/Qwen3.8-Flash-Next-GGUF --rev d96201194f103c906994f283f504209dc8d2a10c \
  --dir UD-IQ3_XXS --out "$OUT/hf-unsloth-iq3xxs/intake.json"; say "6 rc $?"
say "port0213-light end"
