#!/bin/bash
# bringup/runbook.sh RUN STAGE [STAGE...] | RUN all | RUN series-all — bring a model (or a release) up on this PC, stage
# by stage (bringup/RUNBOOK.md; the one-page order: bringup/DAY-ONE.md). Every stage writes into bringup/out/RUN/ and
# appends its time to times.tsv; a stage that cannot continue writes STOP-<stage> with the reason (a manual step) and
# the script stops. GPU stages need the GPUs free (8080 stopped by you first - this script never stops a server).
#
# 10-27 (Strata v0.2.6 refresh, bringup/REFRESH-1027.md): two phases, in the user's order -
#   all        = summary preflight clone inspect fitplan config pack build stock screen suite
#                the release ALONE: summary stops until you have sent the user the release summary and got the go
#                (RB_GO=1 in run.env); then the stock build with the LOSSLESS config (STRATA_ROUTE_TAIL_SKIP=0,
#                STRATA_ADAPT_ASYNC=0, STRATA_PREFILL_CPU_SHARE=0; sampling 1.0 / 0.95 / 20 / min-p 0.05, effort medium),
#                exact7 twice + a served repeat (does it repeat itself?), a decode screen, the suite's quick run at medium
#   series-all = series build_series patched patches calib b3table screens accept soak promote
#                only after phase A and the user's go: our patch series on the release (the ledger pass by hand, its
#                model-specific parts refitted: patches/LEDGER.md "model assumptions"), then the old Round 13 chain
# Around every GPU stage: no other model server (process names, never a command-line pattern), the kernel-log check
# (bringup/lib/kcheck.sh) before and after, tmp/gpu-test.lock held shared (the app launchers then say "busy"), MemAvailable
# >= 12 GB and the swap rule watched (fail: the engine's VmSwap > 0, or swap-ins / swap-outs in 5 samples in a row adding
# up to >= 4 MB - swap-outs only after the run's first episode, which is logged only), the lossless check of the engine
# logs (no tail-skip / asynchronous-tier / CPU-share-default lines) after the stock stages.
#
# Inputs (environment, or bringup/out/RUN/run.env, which is sourced first):
#   RB_TAG        the release tag (default v0.2.6)            RB_REPO     where to clone from (default: the local mirror strata/)
#   RB_BASE_TAG   what the summary diffs against (default v0.2.6 = the accepted baseline; v0.2.1 when RB_TAG is v0.2.6:
#                 the served P021m's base)
#   RB_GGUF       the model's first shard (downloaded: bringup/fetch_model.py; pinned + sha256-checked)
#   RB_MTP        qwen4exp only: the drafter directory (dense.bin, experts.bin, draft_vocab.bin) made for THIS model
#   RB_GO         1 = the user gave the go after the release summary (stage summary stops without it)
#   RB_BASECFG    the served config whose upstream flags / env / sampling are kept (default configs/P021m.json)
#   RB_PROMOTED   the build the screens compare against (default configs/P021m.json = 8080's, the rollback)
#   RB_HELPER     1 = the 4060 Ti helper (default 1)          RB_CONV_CACHE_GIB  stock conversation cache (default 8)
#   RB_STOCK_ENV_KEEP  env keys of RB_BASECFG kept in the stock config (default: CUDA_VISIBLE_DEVICES CUDA_MODULE_LOADING
#                 STRATA_IO_THREADS); RB_OWN_ARGS our flags dropped from it (--chat-cache --chat-cache-mib --side-stash)
#   RB_FIT        1 = apply the planner's resident budget / helper slots / reserve (a file that does not fit in RAM)
#   RB_CMAKE_EXTRA  further build options (the family's own come from the inspector: -DSTRATA_BUILD_DSV41=ON ...)
#   RB_LLAMA      the llama.cpp checkout at the release's pinned ggml (default strata/third_party/llama.cpp)
#   RB_JOBS       build jobs (default 16, never more)         RB_MODEL_NAME  the served model id (default from the file name)
#   phase B: RB_PATCHES (patch files) or RB_SERIES_BRANCH + RB_SERIES_BASE (default r22-port021-cont2 on v0.2.1 = P021m's
#   30 commits, exported by stage series), RB_MEAS (the twin's MEASUREMENT commits; none = no twin), RB_REF, RB_STOCK_REF,
#   RB_SWITCH_ENV, RB_PATCH_ORDER, RB_CALIB_MIN (90), RB_SOAK (1 = the 2-hour soak on 8080), RB_SCREENS ("ldr dec")
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
RUN=$1; shift
R=$WS/bringup/out/$RUN; mkdir -p $R/configs $R/state
[ -f $R/run.env ] && source $R/run.env
source $WS/bringup/lib/env.sh
P=$WS/.venv/bin/python
NVCC=/usr/local/cuda-13.3/bin/nvcc
RB_TAG=${RB_TAG:-v0.2.6} RB_REPO=${RB_REPO:-$WS/strata} RB_BASE_TAG=${RB_BASE_TAG:-v0.2.6}
[ "$RB_BASE_TAG" = "$RB_TAG" ] && RB_BASE_TAG=v0.2.1
RB_BASECFG=${RB_BASECFG:-$WS/configs/P021m.json} RB_PROMOTED=${RB_PROMOTED:-$WS/configs/P021m.json}
RB_HELPER=${RB_HELPER:-1} RB_CALIB_MIN=${RB_CALIB_MIN:-90} RB_REF=${RB_REF:-} RB_MEAS=${RB_MEAS:-}
RB_SERIES_BRANCH=${RB_SERIES_BRANCH:-r22-port021-cont2} RB_SERIES_BASE=${RB_SERIES_BASE:-v0.2.1}
RB_GGUF=${RB_GGUF:?set RB_GGUF}
LL=$(readlink -f ${RB_LLAMA:-$WS/strata/third_party/llama.cpp})
JOBS=$(( ${RB_JOBS:-16} > 16 ? 16 : ${RB_JOBS:-16} ))          # the user's limit: at most 16 compile jobs
LOSSLESS_ENV="STRATA_ROUTE_TAIL_SKIP=0 STRATA_ADAPT_ASYNC=0 STRATA_PREFILL_CPU_SHARE=0"
# v0.2.7 (the user, 10-27): STRATA_DEFAULTS=026 turns every 0.2.7 default back to 0.2.6; the lossy ones that act on our two
# cards are pinned by name too (route prior on the 4060 Ti, int8 prompt attention, split HC read, layer-major prefill, PLE auto RAM)
V027_ENV="STRATA_DEFAULTS=026 STRATA_ROUTE_PRIOR=0 STRATA_PROMPT_ATTN_IMMA=0 STRATA_GR_V3=0 STRATA_PREFILL_LAYER_MAJOR=0 STRATA_PLE_AUTO_RAM=0"
LOSSLESS_ENV="$LOSSLESS_ENV $V027_ENV"
FLOOR_MIB=12288                                                  # MemAvailable floor (the user, 10-19); never lower
export EVICT_GLOB="$(dirname $RB_GGUF)/*.gguf" PROMPT_DIR=$R/prompts
# exact7's pinned cache (since 10-22: 2500, under the free VRAM of both builds so that slot counts MATCH; a model with
# bigger experts: 90 % of the planner's 5080 slots when that is less)
[ -f $R/fitplan.json ] && export PIN_CACHE=$($P -c "import json; print(min(2500, int(json.load(open('$R/fitplan.json')).get('slots_5080', 2778) * 0.9)))")
# the engine path the inspector found (stage inspect): family, binary, build options, pack kind
[ -f $R/state/engine.env ] && source $R/state/engine.env
ENG_FAM=${ENG_FAM:-Qwen4Exp} ENG_BIN=${ENG_BIN:-strata} ENG_CMAKE=${ENG_CMAKE:-} ENG_PACK=${ENG_PACK:-iq_pack} ENG_ARCH=${ENG_ARCH:-qwen4exp}
log() { echo "=== $(date -Is) [$RUN] $*" | tee -a $R/runbook.log; }
stop() { echo "$*" > $R/STOP-$STAGE; log "STOP at $STAGE: $*"; exit 2; }
# 10-27: the series' guards (P021m's src/core/patch_guard.cpp) and its local switches
G="spec_exact side_mixer router_q8k qsa_split_attn gr_fork draft_cum prefill_v2"
SWITCH_ENV=${RB_SWITCH_ENV:-"STRATA_SPEC_EXACT STRATA_SIDE_MIXER STRATA_ROUTER_Q8K STRATA_GR_FORK STRATA_QSA_SPLIT_ATTN STRATA_COST_GATE STRATA_DRAFT_CUM STRATA_PREFILL_V2"}

disk_free_gb() { df -B1 --output=avail $WS/models | tail -1 | awk '{printf "%d", $1 / 1e9}'; }
need_disk() {   # need_disk GB WHAT - the user's rule: >= 100 GB free stays free after this stage's writes
  local f; f=$(disk_free_gb)
  [ $(( f - $1 )) -ge 100 ] || stop "$2 needs ~$1 GB, $f GB free: less than 100 GB would stay free - ask the user what to delete (never delete anything yourself)"
}

mkcfg() {   # mkcfg NAME EXE TREE -> $R/configs/NAME.json (+ .shared-settings.json); RB_MODE=stock (lossless, upstream only) | series
  $P - "$@" <<'PY'
import json, os, re, sys
from pathlib import Path
name, exe, tree = sys.argv[1:4]
tree = Path(tree)
R = Path(os.environ["R"]); base = json.loads(Path(os.environ["RB_BASECFG"]).read_text())
fit = json.loads((R / "fitplan.json").read_text()) if (R / "fitplan.json").exists() else {}
ins = json.loads((R / "inspect.json").read_text()) if (R / "inspect.json").exists() else {}
mode = os.environ.get("RB_MODE", "series")
eng = ins.get("engine") or {}
fam, arch = eng.get("family", "Qwen4Exp"), ins.get("arch", "qwen4exp")
gen = (tree / "src/program/generate.cpp").read_text(errors="replace") if (tree / "src/program/generate.cpp").exists() else ""
lossless = dict(kv.split("=", 1) for kv in os.environ["LOSSLESS_ENV"].split())
shards = ins.get("file", [os.environ["RB_GGUF"]])
if fam == "Qwen35Moe":
    # the own path (setup.py install_own_path): --native, the context (32K on a 16 GB card), --prefill auto, --mtp N
    # drafts per step, --expert-vram GiB; no pack, profile, helper or RAM budget
    a = ["--native", shards[0], "--max-context", str(fit.get("ctx", 32768)), "--prefill", "auto", "--mtp", "2"]
    if fit.get("expert_vram_gib"):
        a += ["--expert-vram", str(fit["expert_vram_gib"])]
    env = {k: v for k, v in base.get("env", {}).items() if k in ("CUDA_VISIBLE_DEVICES", "CUDA_MODULE_LOADING")}
    env["CUDA_VISIBLE_DEVICES"] = env.get("CUDA_VISIBLE_DEVICES", "").split(",")[0]     # one card
    env.update(lossless)
else:
    a = list(base["args"])
    def setarg(flag, val):
        if flag in a: a[a.index(flag) + 1] = val
        else: a.extend([flag, val])
    def droparg(flag, n=2):
        if flag in a:
            i = a.index(flag); del a[i:i + n]
    env = dict(base.get("env", {}))
    if mode == "stock":
        # the release with upstream's defaults: our flags out, the base's env reduced to the allow-list, the lossless block
        for f in os.environ.get("RB_OWN_ARGS", "--chat-cache --chat-cache-mib --side-stash").split():
            droparg(f)
        keep = os.environ.get("RB_STOCK_ENV_KEEP", "CUDA_VISIBLE_DEVICES CUDA_MODULE_LOADING STRATA_IO_THREADS").split()
        env = {k: v for k, v in env.items() if k in keep}
        env.update(lossless)
        if "--conversation-cache-mib" in gen:   # v0.2.x: upstream's conversation cache, sized explicitly + our RAM floor
            setarg("--conversation-cache-mib", str(int(float(os.environ.get("RB_CONV_CACHE_GIB", "8")) * 1024)))
            setarg("--conversation-cache-min-free-mib", os.environ.get("FLOOR_MIB", "12288"))
    else:
        for k in os.environ.get("RB_ENV_DROP", "").split():
            env.pop(k, None)
        env["STRATA_ROUTE_TAIL_SKIP"] = "0"; env["STRATA_ADAPT_ASYNC"] = "0"   # lossless in every phase
        env.setdefault("STRATA_PREFILL_CPU_SHARE", "0")                        # the share stays explicit (P021m: 0.4 < 1792)
        for k, v in lossless.items():   # v0.2.7's defaults: off unless the series config adopted a value (P021m: STRATA_GR_V3=1)
            if k.startswith(("STRATA_DEFAULTS", "STRATA_ROUTE_PRIOR", "STRATA_PROMPT_ATTN", "STRATA_GR_V3", "STRATA_PREFILL_LAYER", "STRATA_PLE_AUTO")):
                env.setdefault(k, v)
    setarg("--pack", str(R / "pack")); setarg("--native", shards[0])
    ple = ins.get("ple_shard") or (shards[-1] if len(shards) > 1 else shards[0])
    setarg("--ple-gguf", ple)
    setarg("--mtp", os.environ.get("RB_MTP", ""))
    # the expert profile must be this model's shape (layers x experts; Flash-Next's data/expert-profile.bin is 48 x 512):
    # RB_PROFILE, else the first STRP file under the tree's data/ whose header matches, else none (stage config stops)
    import struct
    want = (ins.get("layers", {}).get("trunk"), (fit.get("experts_per_layer") or 0))
    def dims(p):
        try:
            b = Path(p).read_bytes()[:24]
            return struct.unpack("<5I", b[4:24])[1:3] if b[:4] == b"STRP" else None
        except OSError:
            return None
    cands = [os.environ["RB_PROFILE"]] if os.environ.get("RB_PROFILE") else [str(tree / "data/expert-profile.bin")] + sorted(map(str, (tree / "data").rglob("*.bin")))
    prof = next((c for c in cands if dims(c) == want), None)
    if prof:
        setarg("--expert-profile", prof)
    else:
        droparg("--expert-profile")
        print(f"NO-PROFILE {want[0]} x {want[1]}", file=sys.stderr)
    if os.environ.get("RB_VISION") != "1":          # a new model's picture reader (mmproj) is its own: off until checked
        if "--vision" in a: a.remove("--vision")
        base.pop("vision", None)
    if os.environ.get("RB_HELPER", "1") != "1":
        droparg("--expert-cache-device1")
        env["CUDA_VISIBLE_DEVICES"] = env.get("CUDA_VISIBLE_DEVICES", "").split(",")[0]
    elif fit.get("helper_slots_max") and os.environ.get("RB_HELPER_SLOTS"):
        setarg("--expert-cache-device1", os.environ["RB_HELPER_SLOTS"])
    if os.environ.get("RB_FIT") == "1" and fit.get("start_config"):   # the planner's RAM / VRAM choices (stage fitplan)
        sc = fit["start_config"].split()
        for i in range(0, len(sc) - 1):
            if sc[i] in ("--resident-budget-gib", "--expert-cache-device1", "--vram-reserve-mib") and not sc[i + 1].startswith("--"):
                setarg(sc[i], sc[i + 1])
        if "--resident-budget-gib" in sc:
            env.update(fit.get("start_env", {}))
            # v0.1.39 - v0.1.44 refused a RAM budget beside a helper cache; v0.1.45+ (v0.2.6) leave its experts out of the copy
            if "helper-GPU caches are allowed beside the resident RAM mode" not in gen:
                droparg("--expert-cache-device1")
                env["CUDA_VISIBLE_DEVICES"] = env.get("CUDA_VISIBLE_DEVICES", "").split(",")[0]
    for kv in os.environ.get("RB_ARGS", "").split():
        f, v = kv.split("=", 1); setarg(f, v)
    for f in os.environ.get("RB_DROP", "").split():
        droparg(f)
for kv in os.environ.get("RB_ENV", "").split():
    k, v = kv.split("=", 1); env[k] = v
slug = os.environ.get("RB_MODEL_NAME") or "strata-" + re.sub(r"[^a-z0-9.]+", "-", re.sub(r"(-\d{5}-of-\d{5})?\.gguf$", "", Path(shards[0]).name.lower())).strip("-")
cfg = dict(base, exe=exe, args=a, env=env, server=str(tree / "serve/server.py"), cwd=str(R),
           tokenizer=str(R / "pack/tokenizer"), log=str(R / f"engine-{name}.log"), model_name=slug, arch=arch,
           port=8081, host="127.0.0.1", reasoning_effort="medium",
           sampling={"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05})   # the user's settings, every path
for k in ("fallback", "_comment", "expert_profile_seed", "expert_profile_seed_sha256", "expert_profile_from"):
    cfg.pop(k, None)
if mode == "stock" or os.environ.get("RB_NOWEB") == "1":
    cfg.pop("web_search", None); cfg.pop("mcp", None)
if fit.get("need_ram_mib"):
    cfg["need_ram_mib"] = fit["need_ram_mib"]
if fit.get("need_vram_mib"):
    cfg["need_vram_mib"] = fit["need_vram_mib"]
cfg["_comment"] = f"bringup {R.name} {name} ({mode}, {fam}): written by bringup/runbook.sh mkcfg from {os.environ['RB_BASECFG']}"
(R / "configs" / f"{name}.json").write_text(json.dumps(cfg, indent=1) + "\n")
# the shared Chat settings: medium effort and the sampling block on every path (min_p cannot go here: the config's
# "sampling" block carries it; Rehearsal A's screens once compared T 0.6 against T 1.0 without this file)
(R / "configs" / f"{name}.shared-settings.json").write_text(json.dumps(
    {"reasoning_effort": "medium", "temperature": 1.0, "top_p": 0.95, "top_k": 20}, indent=1) + "\n")
print(R / "configs" / f"{name}.json")
PY
}
export R RB_BASECFG RB_GGUF RB_MTP=${RB_MTP:-} RB_HELPER RB_HELPER_SLOTS=${RB_HELPER_SLOTS:-} RB_FIT=${RB_FIT:-0} LOSSLESS_ENV FLOOR_MIB \
       RB_CONV_CACHE_GIB=${RB_CONV_CACHE_GIB:-8} RB_STOCK_ENV_KEEP=${RB_STOCK_ENV_KEEP:-} RB_OWN_ARGS=${RB_OWN_ARGS:-} \
       RB_MODEL_NAME=${RB_MODEL_NAME:-} RB_VISION=${RB_VISION:-0}
[ -z "$RB_STOCK_ENV_KEEP" ] && unset RB_STOCK_ENV_KEEP; [ -z "$RB_OWN_ARGS" ] && unset RB_OWN_ARGS

# ---- around every GPU stage
other_server() {   # process names only (no command-line pattern: a pattern can match the shell that runs it)
  local p; for p in strata strata-dsv41 llama-server; do pgrep -x $p > /dev/null && { echo $p; return 0; }; done
  for p in 8080 8081 8085 8086; do ss -H -ltn "( sport = :$p )" | grep -q . && { echo "a listener on $p"; return 0; }; done
  return 1
}
swp() { awk '/^pswpin /{i=$2} /^pswpout /{o=$2} END{print i, o}' /proc/vmstat; }
eng_swap_kb() { local r=0 p v; for p in $(pgrep -x $ENG_BIN); do v=$(awk '/VmSwap/{print $2}' /proc/$p/status 2>/dev/null); r=$((r + ${v:-0})); done; echo $r; }
stage_watch() {   # the 10-27 swap rule (work/ds41/tune/tunearm.sh swapcheck) + the 12 GB floor, every 2 s, until $R/state/watch.stop
  local i0 o0 i1 o1 si so es sw sp=0 busy=0 busyp=0 qo=99 nb=0 ob=0 obp=0 a why
  read i0 o0 < <(swp)
  echo "time memavail_mib swap_used_mib swapin swapout engine_vmswap_kb" > $R/state/watch-$STAGE.tsv
  while [ ! -e $R/state/watch.stop ]; do
    a=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo); sw=$(awk '/^SwapTotal/{t=$2} /^SwapFree/{f=$2} END{print int((t-f)/1024)}' /proc/meminfo)
    read i1 o1 < <(swp); si=$((i1 - i0)); so=$((o1 - o0)); i0=$i1; o0=$o1; es=$(eng_swap_kb)
    echo "$(date +%T) $a $sw $si $so $es" >> $R/state/watch-$STAGE.tsv
    if [ $si -gt 0 ] && [ $sw -ge $sp ]; then busy=$((busy + 1)); busyp=$((busyp + si)); else busy=0; busyp=0; fi; sp=$sw
    if [ $so -gt 0 ]; then [ $qo -ge 15 ] && { nb=$((nb + 1)); ob=0; obp=0; }; ob=$((ob + 1)); obp=$((obp + so)); qo=0
    else qo=$((qo + 1)); ob=0; obp=0; fi
    why=""
    [ $a -lt $FLOOR_MIB ] && why="MemAvailable $a MiB < $FLOOR_MIB"
    [ $es -gt 0 ] && why="the engine's own memory was swapped (VmSwap $es kB)"
    [ $busy -ge 5 ] && [ $busyp -ge 1024 ] && why="swap-ins in $busy samples in a row, $((busyp * 4 / 1024)) MB"
    [ $nb -ge 2 ] && [ $ob -ge 5 ] && [ $obp -ge 1024 ] && why="swap-outs in $ob samples in a row after the first push-out (episode $nb), $((obp * 4 / 1024)) MB"
    if [ -n "$why" ]; then
      echo "failed: memory - $why" > $R/state/MEMFAIL
      for p in $(pgrep -x $ENG_BIN); do kill -TERM $p; done      # by PID; the guard.py / with_server.sh wrappers then end
      return
    fi
    sleep 2
  done
}
gpu_begin() {
  local o a; o=$(other_server) && stop "another model server is running ($o): one at a time - stop 8080 yourself first (P021m stays its config)"
  bash $WS/bringup/lib/kcheck.sh rb-$RUN-$STAGE-before || stop "the kernel-log check failed before $STAGE (bringup/lib/kcheck.sh): look at the kernel log, tell the user"
  a=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  local need=$($P -c "import json; print(json.load(open('$R/fitplan.json')).get('need_ram_mib', 0))" 2>/dev/null || echo 0)
  [ $a -ge ${need:-0} ] || stop "MemAvailable $a MiB < the plan's need_ram_mib $need (the experts + the 12 GB floor): close programs, never lower the floor"
  exec 9> $WS/tmp/gpu-test.lock; flock -s 9                       # shared, as with_server.sh (an exclusive hold deadlocked gap 1)
  rm -f $R/state/watch.stop $R/state/MEMFAIL; stage_watch & WATCH=$!
}
gpu_end() {
  touch $R/state/watch.stop; wait $WATCH 2>/dev/null; exec 9>&-
  [ -f $R/state/MEMFAIL ] && stop "$(cat $R/state/MEMFAIL) (during $STAGE; $R/state/watch-$STAGE.tsv)"
  awk 'NR > 1 { if (m == "" || $2 < m) m = $2; si += $4; so += $5 } END { printf "lowest MemAvailable %d MiB, swap in %.1f MB / out %.1f MB\n", m, si * 4 / 1024, so * 4 / 1024 }' \
    $R/state/watch-$STAGE.tsv | while read -r l; do log "$STAGE memory: $l"; done
  bash $WS/bringup/lib/kcheck.sh rb-$RUN-$STAGE-after || stop "the kernel-log check failed after $STAGE: stop everything, tell the user (a page-allocation-failure-only log under pressure: drop the run, 10-25 rule)"
}
lossless_check() {   # lossless_check LOG... - none of the release's lossy defaults may act (10-10 / 10-27 rules)
  local bad
  bad=$(grep -h -E "STRATA_ROUTE_TAIL_SKIP=[1-9][0-9]* is ON|route tail skip: [1-9]|adaptive tier asynchronous|asynchronous tier is tried|asynchronous tier stays on|asynchronous adaptive tier:|CPU share is ON by default|residency-biased routing is on by default|chosen by the residency policy|layer-major prefill is on for this layer split|strata prefill: layer-major \\(layers" "$@" 2>/dev/null | sort | uniq -c | head -5)
  [ -z "$bad" ] || stop "a lossy default acted in $STAGE: $bad"
  log "$STAGE: lossless check clean ($(ls "$@" 2>/dev/null | wc -l) log(s))"
}

ggml_dir() {   # ggml_dir TREE - the llama.cpp checkout its ggml comes from (v0.2.x: third_party/ggml/VERSION.txt pins it)
  local T=$1 pin
  if [ -f $T/third_party/ggml/VERSION.txt ]; then
    pin=$(cut -d' ' -f1 $T/third_party/ggml/VERSION.txt)
    [ "$(git -C $LL rev-parse HEAD 2>/dev/null)" = "$pin" ] || { echo "$pin"; return 1; }
    echo $LL
  else   # <= v0.1.4x: the tree's own link (strata-v0115's checkout, absolute: its relative link points nowhere from out/RUN/)
    [ -d $T/third_party/llama.cpp/ggml ] || { rm -rf $T/third_party/llama.cpp; ln -sfn $(readlink -f $WS/strata-v0115/third_party/llama.cpp) $T/third_party/llama.cpp; }
    echo $T/third_party/llama.cpp
  fi
}
build_guard() {   # build_guard TREE PID - work/r22/build_memguard.sh's rule for this tree's ninja (that guard watches fixed folders)
  local T=$1 bp=$2 a n paused="" low=999999
  while kill -0 $bp 2>/dev/null; do
    a=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo); [ $a -lt $low ] && low=$a
    n=$(for p in $(pgrep -x ninja); do case $(readlink /proc/$p/cwd 2>/dev/null) in $T*) echo $p;; esac; done)
    if [ -n "$n" ] && [ $a -lt 14336 ]; then for p in $n; do kill -CONT $p; kill -TERM $p; done; log "build: MemAvailable $a MiB < 14 GB: build STOPPED"; paused=""
    elif [ -n "$n" ] && [ $a -lt 24576 ] && [ -z "$paused" ]; then for p in $n; do kill -STOP $p; done; paused=$n; log "build: MemAvailable $a MiB < 24 GB: ninja paused"
    elif [ -n "$paused" ] && [ $a -gt 32768 ]; then for p in $paused; do kill -CONT $p; done; paused=""; log "build: resumed"; fi
    sleep 0.5
  done
  for p in $paused; do kill -CONT $p 2>/dev/null; done
  log "build: lowest MemAvailable $low MiB"
}
build_tree() {   # build_tree TREE OUTDIR - its own folder (never over a served build), <= 16 jobs, nice 5, under the build memory guard
  local T=$1 OUT=$2 GG bp
  case $OUT in $WS/bringup/out/*) ;; *) stop "build output $OUT is not under bringup/out: a served build (engine-r22p021m = P021m, the rollback) is never overwritten";; esac
  case $(readlink -f $T) in $WS/bringup/out/*) ;; *) stop "$T resolves to $(readlink -f $T), outside bringup/out: never build in a shared worktree (strata-v026 holds the DeepSeek build)";; esac
  GG=$(ggml_dir $T) || stop "$(basename $T) pins ggml $GG but $LL is at $(git -C $LL rev-parse --short HEAD 2>/dev/null): fetch that commit into a llama.cpp checkout (network, manual) and set RB_LLAMA"
  need_disk 5 "the $(basename $T) build"
  (cd $T && nice -n 5 cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
    "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC $ENG_CMAKE $([ "${RB_KQUANTS:-0}" = 1 ] && echo -DSTRATA_MMQ_KQUANTS=ON) \
    ${RB_CMAKE_EXTRA:-} -DSTRATA_GGML_DIR="$GG" > build-configure.log 2>&1) || return 1
  (cd $T && nice -n 5 cmake --build build --target $ENG_BIN -j $JOBS > build.log 2>&1) & bp=$!
  build_guard $T $bp
  wait $bp || return 1
  mkdir -p $OUT && cp $T/build/$ENG_BIN $OUT/$ENG_BIN && sha256sum $OUT/$ENG_BIN > $OUT/SHA256
  echo "$(git -C $T describe --tags --always) + $(git -C $T log --oneline $RB_TAG..HEAD | wc -l) commits, tree $(git -C $T rev-parse HEAD^{tree}), target $ENG_BIN $ENG_CMAKE, ggml $(git -C $GG rev-parse --short HEAD 2>/dev/null)" > $OUT/SOURCE
}

exact7_hashes() { $P - "$1" <<'PY'
import sys
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/bringup/lib")
from p0_table import parse
print(" ".join(parse(f"{sys.argv[1]}-{k}").get("out", "-") for k in ("x-math", "s-math", "x-code", "s-code", "x-p2000", "x-32k", "x-112k")))
PY
}
served_repeat() {   # served_repeat LABEL CONFIG - two identical greedy requests through the server: the same text? (any family)
  bringup/lib/with_server.sh $1 $2 -- "$P - <<'PY'
import json, urllib.request
def ask():
    body = {'model': 'x', 'messages': [{'role': 'user', 'content': 'Prove that the square root of 2 is irrational, then list the first ten primes.'}],
            'temperature': 0, 'max_tokens': 768, 'reasoning_effort': 'medium'}
    r = urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8081/v1/chat/completions', json.dumps(body).encode(),
                               {'Content-Type': 'application/json'}), timeout=1800)
    m = json.load(r)['choices'][0]['message']
    return (m.get('reasoning_content') or '') + '|' + (m.get('content') or '')
a, b = ask(), ask()
print('served repeat:', 'IDENTICAL' if a == b else 'DIFFERENT at char %d of %d' % (next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b))), len(a)))
PY"
}

# ---- phase A: the release alone
st_summary() {   # no GPU: the raw material of the release summary the user reads BEFORE anything is built or measured
  git -C $RB_REPO rev-parse -q --verify "$RB_TAG^{commit}" > /dev/null || stop "no tag $RB_TAG in $RB_REPO: git -C $RB_REPO fetch --tags origin first (network; upstream may rewrite tag history - compare trees, not hashes)"
  local B=$RB_BASE_TAG
  envs() { git -C $RB_REPO grep -h -o -E 'getenv\("STRATA_[A-Z0-9_]+"\)' $1 -- src include 2>/dev/null | sed 's/getenv("//; s/")//' | sort -u; }
  flags() { git -C $RB_REPO grep -h -o -E 'a == "--[a-z0-9-]+"' $1 -- src 2>/dev/null | sed 's/a == "//; s/"//' | sort -u; }
  { echo "# $RB_TAG vs $B on our path ($(date -Is))"
    echo "## files changed (src include serve third_party cmake CMakeLists.txt)"
    git -C $RB_REPO diff --stat=160 $B $RB_TAG -- src include serve third_party cmake CMakeLists.txt | tail -60
    echo "## new STRATA_* switches"; comm -13 <(envs $B) <(envs $RB_TAG)
    echo "## new engine flags"; comm -13 <(flags $B) <(flags $RB_TAG)
    echo "## architectures the release's reader knows (model_family.hpp) / engine targets"
    git -C $RB_REPO show $RB_TAG:include/strata/artifact/model_family.hpp 2>/dev/null | grep -E 'arch == "' ; git -C $RB_REPO show $RB_TAG:CMakeLists.txt | grep -E 'add_executable\(strata' | cut -c1-120
    echo "## the pinned ggml"; git -C $RB_REPO show $RB_TAG:third_party/ggml/VERSION.txt 2>/dev/null
    echo "## added lines that speak of defaults or exactness (read each: a new output-changing default is decided on its own)"
    git -C $RB_REPO diff $B $RB_TAG -- src include serve | grep -E '^\+' | grep -iE 'by default|on by default|not bit-exact|bit-exact|answers differ|run to run|lossy| KL ' | cut -c1-220 | head -80
    echo "## release notes in the tree"; git -C $RB_REPO show $RB_TAG:docs/release-notes-${RB_TAG#v}.md 2>/dev/null | head -120
  } > $R/summary-raw.md 2>&1
  log "summary: $(wc -l < $R/summary-raw.md) lines of material in $R/summary-raw.md"
  [ "${RB_GO:-0}" = 1 ] || stop "write the user a short release summary from $R/summary-raw.md (what changed on our path - the Flash-Next / new model files, CUDA, RTX 5080 + 4060 Ti helper, the 8080 server and clients; new defaults; anything not bit-exact; concurrency) and WAIT for the go; then RB_GO=1 in $R/run.env"
}
st_preflight() {   # no GPU: the room for this run and the state of the PC
  local a; a=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  need_disk 10 "this run (clone, pack, builds)"
  [ -x $NVCC ] || stop "no $NVCC"
  [ -f $RB_GGUF ] || stop "RB_GGUF $RB_GGUF is not here (bringup/fetch_model.py: pins -> heads -> plan -> unit/get)"
  [ -f $RB_GGUF.size ] && stop "RB_GGUF is a HEAD-ONLY file (fetch_model.py heads): the planning stages run on it, the build and runs need the download"
  bash $WS/bringup/lib/kcheck.sh rb-$RUN-preflight || stop "the kernel-log check failed (bringup/lib/kcheck.sh)"
  log "preflight: $(disk_free_gb) GB free on the models' drive, MemAvailable $a MiB, kernel log clean, other server: $(other_server || echo none); $(nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader | tr '\n' ';')"
}
st_clone() {   # the release as shipped (stock); our series comes in phase B (stage series)
  rm -rf $R/strata-stock
  git clone -q $RB_REPO $R/strata-stock && git -C $R/strata-stock checkout -q $RB_TAG || stop "clone of $RB_TAG failed"
  local GG; GG=$(ggml_dir $R/strata-stock) || log "clone: NOTE the release pins ggml $GG; $LL is at $(git -C $LL rev-parse --short HEAD) - the build will stop until RB_LLAMA has that commit"
  log "clone: $RB_TAG stock, tree $(git -C $R/strata-stock rev-parse HEAD^{tree}), ggml from ${GG:-?}"
}
st_inspect() {
  local ST=${RB_SERIES_TREE:-$([ -d $R/strata-patched ] && echo $R/strata-patched || echo $WS/strata-r22p021m)}
  $P bringup/inspect_model.py $RB_GGUF $([ -n "${RB_MTP:-}" ] && echo --mtp $RB_MTP) --tree $R/strata-stock --series-tree $ST --json $R/inspect.json > $R/inspect.txt; local rc=$?
  log "inspect: $(grep VERDICT $R/inspect.txt | cut -c1-300)"
  $P - $R <<'PY'
import json, sys
from pathlib import Path
R = Path(sys.argv[1]); ins = json.loads((R / "inspect.json").read_text()); e = ins.get("engine") or {}
(R / "state/engine.env").write_text(f"ENG_FAM={e.get('family', '')}\nENG_BIN={e.get('binary', 'strata')}\n"
                                    f"ENG_CMAKE=\"{' '.join(e.get('cmake', []))}\"\nENG_PACK={e.get('pack', '?')}\nENG_ARCH={ins['arch']}\n")
PY
  [ $rc = 0 ] || stop "$(grep VERDICT $R/inspect.txt | cut -c1-400) - wait for the release that adds exactly that"
  source $R/state/engine.env
  [ "$ENG_FAM" = Qwen4Exp ] && [ -z "${RB_MTP:-}" ] && stop "the qwen4exp path needs RB_MTP: the MTP draft layer made for THIS model (tools/mtp_fetch.py fetches only Qwen3.8-Flash-Next's)"
  true
}
st_fitplan() {
  $P bringup/fitplan.py $RB_GGUF --tree $R/strata-stock --profile $R/strata-stock/data/expert-profile.bin $([ "$RB_HELPER" = 1 ] || echo --no-helper) \
    --chat-cache-gib ${RB_CONV_CACHE_GIB:-8} ${RB_FITPLAN_ARGS:-} --json $R/fitplan.json > $R/fitplan.txt || stop "fitplan: $(tail -1 $R/fitplan.txt)"
  log "fitplan: $(grep -E '^(slots_5080|helper_slots_max|ram_need_gib|ram_need_budget_gib|ram_ok|ram_ok_serve|need_ram_mib|pack_gib_est|disk_free_after_gb|disk_ok|locked_note) ' $R/fitplan.txt | tr -s ' ' | tr '\n' ';' | cut -c1-500)"
  grep -q "^ram_ok *False" $R/fitplan.txt && [ "${RB_FIT:-0}" != 1 ] && log "fitplan: the experts do not fit in RAM at the 12 GB floor: RB_FIT=1 applies the planner's resident budget (the helper stays beside it on v0.1.45+)"
  grep -q "^locked_note" $R/fitplan.txt && log "fitplan: $(grep '^locked_note' $R/fitplan.txt | cut -c30-)"
  true
}
st_config() {   # no GPU: the lossless stock config (and its shared settings) - read it before stage stock runs it
  [ -d $R/strata-stock ] || stop "no stock tree (stage clone)"
  case $ENG_FAM in Qwen4Exp|Qwen35Moe) ;; *) stop "no config template for $ENG_FAM here (DeepSeek: configs/DS41-daily.json and work/ds41/ are the pattern)";; esac
  RB_MODE=stock mkcfg stock $R/engine-stock/$ENG_BIN $R/strata-stock > /dev/null 2> $R/mkcfg.err || stop "mkcfg failed: $(tail -2 $R/mkcfg.err)"
  grep -q NO-PROFILE $R/mkcfg.err && stop "no expert profile of this model's shape ($(grep -o 'NO-PROFILE.*' $R/mkcfg.err | cut -c12-)) in the release's data/: the serve path's graphed hits need one - make it (tools/make_profile.py from routing traces) or set RB_PROFILE"
  log "config: $R/configs/stock.json (env $($P -c "import json; print(' '.join(f'{k}={v}' for k, v in json.load(open('$R/configs/stock.json'))['env'].items()))" | cut -c1-300))"
}
st_prompts() {
  mkdir -p $R/prompts
  $P - $R <<'PY'
import json, sys
from pathlib import Path
R = Path(sys.argv[1]); WS = Path("/home/USER/ai-speed-testing/strata-compare")
T = R / "strata-stock"
sys.path.insert(0, str(T / "tools"))
import strata_tokenizer as ST
tp = R / "pack/tokenizer" if (R / "pack/tokenizer/vocab.json").exists() else None
if tp is None:   # before the pack: the tokenizer straight from the GGUF
    import os, subprocess
    subprocess.run([sys.executable, str(T / "tools/strata_tokenizer.py"), "--gguf", os.environ["RB_GGUF"], "--out", str(R / "tok")], check=True)
    tp = R / "tok/tokenizer"
vocab = json.loads((tp / "vocab.json").read_text(encoding="utf-8")); toks = [None] * len(vocab)
for t, i in vocab.items(): toks[i] = t
tcfg = json.loads((tp / "tokenizer.json").read_text(encoding="utf-8")) if (tp / "tokenizer.json").exists() else {}
# v0.2.x: the pre-tokenizer name and special ids travel with the pack (serve/server.py does the same)
tok = ST.Tokenizer(toks, (tp / "merges.txt").read_text(encoding="utf-8").split("\n"), json.loads((tp / "token_type.json").read_text()),
                   tcfg.get("pre") or "qwen35", tcfg.get("special_ids") or None)
n = 0
for p in sorted((WS / "bringup/prompts").glob("*.txt")):
    ids = tok.encode(p.read_text(encoding="utf-8"), parse_special=True)
    (R / "prompts" / p.name[:-4]).write_text(",".join(map(str, ids)))
    n += 1
print(f"{n} prompt files re-encoded with {tp} (their chat markup is Qwen's: check it fits this model's template)")
PY
  log "prompts: $(ls $R/prompts | wc -l) files -> PROMPT_DIR=$R/prompts"
}
st_pack() {
  local args="" t0=$(date +%s) GG
  GG=$(ggml_dir $R/strata-stock) || stop "the release pins ggml $GG; the packer's gguf-py comes from that checkout (RB_LLAMA)"
  need_disk $(( $($P -c "import json; print(int(json.load(open('$R/fitplan.json')).get('pack_gib_est', 2)) + 1)") + 1 )) "the pack"
  case $ENG_PACK in
    iq_pack)
      $P -c "import json,sys; d=json.load(open('$R/inspect.json')); sys.exit(0 if any(t not in ('BF16',) for k,v in d['roles'].items() if 'hc_' in k and (k.endswith('_down.weight') or k.endswith('_up.weight')) for t in v['types']) else 1)" && args="--compat-bf16"
      (cd $R/strata-stock && STRATA_GGUF_PY=$GG/gguf-py nice -n 5 $P tools/iq_pack.py --gguf $RB_GGUF --out $R/pack $args > $R/pack.log 2>&1) || stop "the packer refused the file: $(tail -3 $R/pack.log)"
      [ -f $R/pack/tokenizer/vocab.json ] || (cd $R/strata-stock && STRATA_GGUF_PY=$GG/gguf-py $P tools/strata_tokenizer.py --gguf $RB_GGUF --out $R/pack >> $R/pack.log 2>&1) ;;
    tokenizer)   # the qwen35 own path: no pack, the tokenizer only (setup.py install_own_path)
      (cd $R/strata-stock && STRATA_GGUF_PY=$GG/gguf-py $P tools/strata_tokenizer.py --gguf $RB_GGUF --out $R/pack > $R/pack.log 2>&1) || stop "the tokenizer export failed: $(tail -3 $R/pack.log)" ;;
    dsv41) stop "DeepSeek's pack is its own recipe (tools/dsv41/pack_gguf.py with --engram / --engram-meta / --dspark-gguf: work/ds41/pack.sh)" ;;
    *) stop "no pack step known for $ENG_FAM: read the release notes / setup.py for it" ;;
  esac
  log "pack: $(du -sh $R/pack | cut -f1) in $(( $(date +%s) - t0 )) s ($ENG_PACK $args)"
  st_prompts
}
st_build() {   # phase A: the release alone (RB_BUILDS=stock); phase B: build_series
  for T in ${RB_BUILDS:-stock}; do build_tree $R/strata-$T $R/engine-$T || stop "the $T build failed: $(tail -5 $R/strata-$T/build.log 2>/dev/null || tail -5 $R/strata-$T/build-configure.log)"; done
  log "build: $(for T in ${RB_BUILDS:-stock}; do echo -n "$T $(cat $R/engine-$T/SOURCE) | "; done)"
}
st_stock() {
  [ -f $R/configs/stock.json ] || st_config
  gpu_begin
  if [ "$ENG_FAM" = Qwen4Exp ]; then
    REF=${RB_STOCK_REF:-c13} bringup/lib/exact7.sh rb-$RUN-stock $R/configs/stock.json > $R/exact7-stock.txt 2>&1
    log "stock: exact7 $(exact7_hashes rb-$RUN-stock) ($(grep -h 'exact7-slots' $R/exact7-stock.txt | cut -c1-100))"
    [ "$(exact7_hashes rb-$RUN-stock | grep -c -- '-')" = 0 ] || stop "the stock release did not produce all seven outputs (see $R/exact7-stock.txt)"
    # does the release repeat itself on this file and placement? (v0.2.2+: near-tie words differ at default settings -
    # the release notes; the lossless switches should make it repeat: a NO here is a finding for the user)
    REF=rb-$RUN-stock bringup/lib/exact7.sh rb-$RUN-stock2 $R/configs/stock.json > $R/exact7-stock2.txt 2>&1
    rm -f $R/state/nonrepeat
    grep -q "MATCHED" $R/exact7-stock2.txt || log "stock: the two exact7 runs had DIFFERENT slot counts ($(grep -h 'exact7-slots' $R/exact7-stock2.txt | cut -c1-120)): their hashes cannot be compared"
    if grep -qE -- "--resident-budget-gib|--mmap-experts" $R/configs/stock.json; then touch $R/state/nonrepeat
      log "stock: $(tail -2 $R/exact7-stock2.txt | head -1 | cut -c1-60); experts partly read from the files -> treated as not repeatable (first-difference agreement, teacher-forced NLL)"
    elif grep -q "7/7" $R/exact7-stock2.txt; then log "stock: repeats itself 7/7 -> bit-identity gates"
    else touch $R/state/nonrepeat
      log "stock: does NOT repeat itself ($(grep 'exact7 rb' $R/exact7-stock2.txt | cut -c1-60)) -> a finding for the user (which default?); patched-off by first-difference agreement, switches by teacher-forced NLL"; fi
  else
    log "stock: exact7 is Flash-Next's CLI harness - on the $ENG_FAM path the served repeat below is the repeat check"
  fi
  served_repeat rb-$RUN-stock-rep $R/configs/stock.json > $R/served-repeat-stock.txt 2>&1
  log "stock: $(grep -h 'served repeat' $R/served-repeat-stock.txt | tail -1)"
  lossless_check $R/engine-stock.log bringup/out/logs/prof/rb-$RUN-stock*.err
  (cd $R/strata-stock && timeout 900 $P -m unittest discover -s serve -t . > $R/servertests-stock.txt 2>&1); log "stock: server tests $(tail -1 $R/servertests-stock.txt)"
  gpu_end
}
st_screen() {   # the decode screen, A B B A: the stock lossless config vs the promoted P021m (speed context, not a gate)
  gpu_begin
  local SS; SS=$(date -Iseconds | cut -c1-19)
  bringup/lib/decscreen.sh rb-$RUN-D-stock-a $R/configs/stock.json > /dev/null 2>&1
  [ "${RB_SCREEN_PROMOTED:-1}" = 1 ] && bringup/lib/decscreen.sh rb-$RUN-D-prom-a $RB_PROMOTED > /dev/null 2>&1 && bringup/lib/decscreen.sh rb-$RUN-D-prom-b $RB_PROMOTED > /dev/null 2>&1
  bringup/lib/decscreen.sh rb-$RUN-D-stock-b $R/configs/stock.json > /dev/null 2>&1
  SINCE=$SS $P bringup/lib/ab_table.py $([ "${RB_SCREEN_PROMOTED:-1}" = 1 ] && echo promoted=rb-$RUN-D-prom-a,rb-$RUN-D-prom-b) stock=rb-$RUN-D-stock-a,rb-$RUN-D-stock-b > $R/screen-stock.md 2>&1
  log "screen: $(grep -iE 'decode|tok/s' $R/screen-stock.md | head -2 | tr '\n' ' ' | cut -c1-200)"
  lossless_check $R/engine-stock.log
  gpu_end
}
st_suite() {   # the suite's quick run at medium on the stock lossless config (suite/README.md)
  gpu_begin
  bringup/lib/with_server.sh rb-$RUN-suite $R/configs/stock.json -- "suite/run.sh --label rb-$RUN-stock-quick-medium --endpoint http://127.0.0.1:8081 --mode quick --extra-body '{\"reasoning_effort\": \"medium\"}'" > $R/suite-stock.txt 2>&1
  log "suite: $(grep -iE 'total|score' $R/suite-stock.txt | tail -2 | tr '\n' ' ' | cut -c1-200) (suite/results/rb-$RUN-stock-quick-medium)"
  lossless_check $R/engine-stock.log
  gpu_end
  log "phase A done: report stock's speed, repeat check and suite to the user; phase B (series-all) only after the go"
}

# ---- phase B: our series on the release (after phase A and the go)
st_series() {
  rm -rf $R/strata-patched $R/strata-twin
  local S=${RB_PATCHES:-}
  if [ -z "$S" ]; then   # the served P021m's commits, exported from its branch
    S=$R/series; rm -rf $S
    git -C $RB_REPO format-patch -q -o $S $RB_SERIES_BASE..$RB_SERIES_BRANCH || stop "could not export $RB_SERIES_BASE..$RB_SERIES_BRANCH"
  fi
  local gi="-c user.name=bringup -c user.email=noreply@localhost"
  for T in patched $([ -n "$RB_MEAS" ] && echo twin); do
    git clone -q $RB_REPO $R/strata-$T && git -C $R/strata-$T checkout -q $RB_TAG || stop "clone of $RB_TAG failed"
  done
  git -C $R/strata-patched $gi am -q $S/0*.patch > $R/am.log 2>&1 || { git -C $R/strata-patched $gi am --abort; stop "our series does not apply to $RB_TAG ($(grep -m1 'Patch failed\|error' $R/am.log)): the ledger pass by hand (bringup/RUNBOOK.md), then RB_PATCHES=<the new series>"; }
  if [ -n "$RB_MEAS" ]; then
    git -C $R/strata-twin $gi am -q $S/0*.patch $RB_MEAS/0*.patch > $R/am-twin.log 2>&1 || { git -C $R/strata-twin $gi am --abort; stop "the twin's MEASUREMENT commits do not apply"; }
  fi
  log "series: $RB_TAG + $(ls $S/0*.patch | wc -l) patches$([ -n "$RB_MEAS" ] && echo "; twin + $(ls $RB_MEAS/0*.patch | wc -l) MEASUREMENT" || echo "; no twin (RB_MEAS unset: no teacher-forced gates)")"
}
st_build_series() { RB_BUILDS="patched $([ -n "$RB_MEAS" ] && echo twin)" st_build; }
st_patched() {
  gpu_begin
  RB_MODE=series RB_ENV_DROP="$SWITCH_ENV" mkcfg patched-off $R/engine-patched/$ENG_BIN $R/strata-patched > /dev/null
  REF=rb-$RUN-stock bringup/lib/exact7.sh rb-$RUN-poff $R/configs/patched-off.json > $R/exact7-poff.txt 2>&1
  log "patched, switches off: $(grep 'exact7 rb' $R/exact7-poff.txt) $(grep -h 'exact7-slots' $R/exact7-poff.txt | grep -o 'MATCHED\|DIFFER') | $(grep -h 'patch guards:' bringup/out/logs/prof/rb-$RUN-poff-x-math.err bringup/out/logs/prof/rb-$RUN-poff-x-math.out 2>/dev/null | head -1 | cut -c1-160)"
  grep -q MATCHED $R/exact7-poff.txt || stop "patched-off ran at other slot counts than stock: compare at MATCHED slots (PIN_CACHE; 10-22 rule) before reading the hashes"
  if [ -f $R/state/nonrepeat ]; then
    REF=rb-$RUN-poff bringup/lib/exact7.sh rb-$RUN-poff2 $R/configs/patched-off.json > $R/exact7-poff2.txt 2>&1
    $P bringup/lib/repeat_gate.py rb-$RUN-stock rb-$RUN-stock2 rb-$RUN-poff rb-$RUN-poff2 > $R/repeat-gate.txt 2>&1
    log "patched, switches off (stock does not repeat): $(tail -1 $R/repeat-gate.txt) | $(grep -v '^repeat gate' $R/repeat-gate.txt | tr '\n' ';' | cut -c1-300)"
    grep -q "repeat gate: PASS" $R/repeat-gate.txt || stop "the patched build with its switches off differs from the release earlier than the release differs from itself: $(tail -1 $R/repeat-gate.txt)"
  else
    grep -q "7/7" $R/exact7-poff.txt || stop "the patched build with its switches off does not compute what the release computes: $(grep 'exact7 rb' $R/exact7-poff.txt)"
  fi
  (cd $R/strata-patched && timeout 900 $P -m unittest discover -s serve -t . > $R/servertests-patched.txt 2>&1); log "patched: server tests $(tail -1 $R/servertests-patched.txt)"
  gpu_end
}
st_patches() {
  gpu_begin
  RB_MODE=series mkcfg cand $R/engine-patched/$ENG_BIN $R/strata-patched > /dev/null
  [ -n "$RB_MEAS" ] && RB_MODE=series RB_ENV="STRATA_STATE_HASH=1" RB_ARGS="--adapt-swaps=0" mkcfg twin $R/engine-twin/$ENG_BIN $R/strata-twin > /dev/null
  # in order of measured value on this PC (patches/LEDGER.md), each switch alone on top of the ones before it
  # 10-27: P021m's switches (B.3 / mmvq_il is upstream's own since v0.1.40.2: not ours to gate)
  local tfo=0 list="${RB_PATCH_ORDER:-qsa_split_attn spec_exact side_mixer router_q8k gr_fork cost_gate draft_cum prefill_v2}"
  [ -f $R/state/nonrepeat ] && { tfo=1; list="tf_noise $list"; }
  for n in $list; do
    PT_TF_ONLY=$tfo CFG=$R/configs/cand.json TREE=$(realpath --relative-to=$WS $R/strata-patched) TFEXE=$R/engine-twin/$ENG_BIN bringup/patchtest.sh $n > $R/patch-$n.txt 2>&1
    log "patch $n: $(grep '^patchtest' $R/patch-$n.txt | tail -1 | cut -c1-200)"
  done
  if [ -n "$RB_REF" ]; then REF=$RB_REF bringup/lib/exact7.sh rb-$RUN-cand $R/configs/cand.json > $R/exact7-cand.txt 2>&1
    log "all on: $(grep 'exact7 rb' $R/exact7-cand.txt) $(grep -h 'exact7-slots' $R/exact7-cand.txt | grep -o 'MATCHED\|DIFFER')"; fi
  lossless_check $R/engine-cand.log
  gpu_end
}
calib_ab() {   # calib_ab PARAM OLD NEW SCREEN(dec|ttft) MAKE_OLD MAKE_NEW
  local p=$1 old=$2 new=$3 sc=$4
  [ $(( ($(date +%s) - CAL0) / 60 )) -ge $RB_CALIB_MIN ] && { log "calib $p: skipped (budget of $RB_CALIB_MIN min used)"; return; }
  eval "RB_MODE=series $5" > /dev/null; eval "RB_MODE=series $6" > /dev/null
  local S=bringup/lib/decscreen.sh; [ $sc = ttft ] && S=bringup/lib/ttftscreen.sh
  $S rb-$RUN-cal-$p-old $R/configs/cal-$p-old.json > $R/cal-$p-old.txt 2>&1
  $S rb-$RUN-cal-$p-new $R/configs/cal-$p-new.json > $R/cal-$p-new.txt 2>&1
  # round 14: the whole table (Round 14's first calibration kept only its last 4 lines: the decode row was lost)
  SINCE=$CALSINCE $P bringup/lib/ab_table.py old=rb-$RUN-cal-$p-old new=rb-$RUN-cal-$p-new > $R/cal-$p.md 2>&1
  log "calib $p: old $old vs new $new: $(grep -E '^\| (decode|ms per|TTFT)' $R/cal-$p.md | awk -F'|' '{printf "%s %s;", $2, $5}' | tr -s ' ' | cut -c1-240)"
}
st_calib() {
  gpu_begin
  CAL0=$(date +%s); CALSINCE=$(date -Iseconds | cut -c1-19)
  local E=$R/engine-patched/$ENG_BIN T=$R/strata-patched hs oldh oldr
  hs=$($P -c "import json; print(json.load(open('$R/fitplan.json'))['helper_slots_max'])")
  oldh=$($P -c "import json; a=json.load(open('$RB_BASECFG'))['args']; print(a[a.index('--expert-cache-device1')+1] if '--expert-cache-device1' in a else 0)")
  # the justified alternatives: the planner's helper maximum (less 3 %), a 100 MiB smaller reserve, half the resident KV
  # (Round 12 A6d: +-150 slots), a 32K prompt chunk (Round 11 D), the draft floor 0.4 (Round 12 A1: +0.78 % modeled)
  [ "$RB_HELPER" = 1 ] && grep -q -- "--expert-cache-device1" $R/configs/cand.json && calib_ab helper $oldh $(( hs * 97 / 100 )) dec "mkcfg cal-helper-old $E $T" "RB_ARGS=--expert-cache-device1=$(( hs * 97 / 100 )) mkcfg cal-helper-new $E $T"
  oldr=$($P -c "import json; a=json.load(open('$R/configs/cand.json'))['args']; print(a[a.index('--vram-reserve-mib')+1])")
  calib_ab reserve $oldr $(( oldr - 100 )) dec "mkcfg cal-reserve-old $E $T" "RB_ARGS=--vram-reserve-mib=$(( oldr - 100 )) mkcfg cal-reserve-new $E $T"
  calib_ab kvres 32768 16384 dec "mkcfg cal-kvres-old $E $T" "RB_ARGS=--kv-resident=16384 mkcfg cal-kvres-new $E $T"
  calib_ab chunk auto:16384 auto:32768 ttft "mkcfg cal-chunk-old $E $T" "RB_ARGS=--prefill=auto:32768 mkcfg cal-chunk-new $E $T"
  calib_ab draft 0.5 0.4 dec "mkcfg cal-draft-old $E $T" "RB_ARGS=--spec-min-p=0.4 mkcfg cal-draft-new $E $T"
  log "calib: $(( ($(date +%s) - CAL0) / 60 )) min of $RB_CALIB_MIN (decide by hand from cal-*.md: an alternative needs >= +2 % beyond the noise)"
  gpu_end
}
st_b3table() {   # v0.2.x: upstream's own tool prints the rows-a-warp table (mmvq_il_parity --bench --emit-table)
  local T=$R/strata-patched GG
  grep -q "add_executable(mmvq_il_parity" $T/CMakeLists.txt || { log "b3table: no mmvq_il_parity target in this tree - skipped"; return; }
  GG=$(ggml_dir $T) || stop "ggml pin $GG (RB_LLAMA)"
  (cd $T && nice -n 5 cmake -G Ninja -S . -B build-tests -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=ON \
     "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=$NVCC -DSTRATA_GGML_DIR="$GG" > $R/b3-configure.log 2>&1 \
   && nice -n 5 cmake --build build-tests --target mmvq_il_parity -j $JOBS > $R/b3-build.log 2>&1) || stop "mmvq_il_parity did not build"
  gpu_begin
  CUDA_VISIBLE_DEVICES=GPU-UUID-RTX5080 $P bringup/lib/guard.py rb-$RUN-b3 -- $T/build-tests/mmvq_il_parity > $R/b3-parity.txt 2>&1
  CUDA_VISIBLE_DEVICES=GPU-UUID-RTX5080 $P bringup/lib/guard.py rb-$RUN-b3b -- $T/build-tests/mmvq_il_parity --bench --emit-table > $R/b3-bench.txt 2>&1
  log "b3table: parity $(tail -1 $R/b3-parity.txt | cut -c1-80); the table in $R/b3-bench.txt (compare with the config's STRATA_MMVQ_IL_ROWS; speed only)"
  gpu_end
}
st_screens() {
  gpu_begin
  local SS; SS=$(date -Iseconds | cut -c1-19)
  if [ "${RB_SCREENS:-ldr dec}" != dec ]; then
  bringup/lib/ldrscreen.sh rb-$RUN-L-prom-a $RB_PROMOTED > /dev/null 2>&1; bringup/lib/ldrscreen.sh rb-$RUN-L-cand-a $R/configs/cand.json > /dev/null 2>&1
  bringup/lib/ldrscreen.sh rb-$RUN-L-cand-b $R/configs/cand.json > /dev/null 2>&1; bringup/lib/ldrscreen.sh rb-$RUN-L-prom-b $RB_PROMOTED > /dev/null 2>&1
  SINCE=$SS $P bringup/lib/ldr_table.py promoted=rb-$RUN-L-prom-a,rb-$RUN-L-prom-b candidate=rb-$RUN-L-cand-a,rb-$RUN-L-cand-b > $R/screen-ldr.md 2>&1
  fi
  bringup/lib/decscreen.sh rb-$RUN-D-prom-a $RB_PROMOTED > /dev/null 2>&1; bringup/lib/decscreen.sh rb-$RUN-D-cand-a $R/configs/cand.json > /dev/null 2>&1
  bringup/lib/decscreen.sh rb-$RUN-D-cand-b $R/configs/cand.json > /dev/null 2>&1; bringup/lib/decscreen.sh rb-$RUN-D-prom-b $RB_PROMOTED > /dev/null 2>&1
  SINCE=$SS $P bringup/lib/ab_table.py promoted=rb-$RUN-D-prom-a,rb-$RUN-D-prom-b candidate=rb-$RUN-D-cand-a,rb-$RUN-D-cand-b > $R/screen-dec.md 2>&1
  log "screens: LDR $(grep -iE 'decode|tok/s' $R/screen-ldr.md 2>/dev/null | head -2 | tr '\n' ' ' | cut -c1-160) | decode $(grep -iE 'decode|tok/s' $R/screen-dec.md | head -2 | tr '\n' ' ' | cut -c1-160)"
  gpu_end
}
st_accept() {
  [ -n "$RB_MEAS" ] || { log "accept: skipped - the acceptance suite needs the twin (RB_MEAS)"; return; }
  gpu_begin
  bringup/acceptance.sh rb-$RUN $R/configs/cand.json $R/configs/twin.json $RB_GGUF > $R/accept.txt 2>&1
  log "accept: $(grep -E 'pass, .* fail' $R/accept.txt | tail -1) $(grep 'suite run time' $R/accept.txt)"
  gpu_end
}
st_soak() {
  [ "${RB_SOAK:-0}" = 1 ] || { log "soak: skipped (RB_SOAK=1 runs it on 8080)"; return; }
  gpu_begin
  STRATA_CONFIG=$R/configs/cand.json bringup/lib/soak13.sh 120 > $R/soak.txt 2>&1; log "soak: $(tail -3 $R/soak.txt | tr '\n' ' ' | cut -c1-200)"
  gpu_end
}
st_promote() { log "promote (manual, the user's decision): copy $R/configs/cand.json to configs/ (+ its .shared-settings.json), STRATA_CONFIG for run-strata.sh / switch-model.sh, a real rollback test to configs/P021m.json (bringup/lib/rollback_test.sh is the pattern); keep P021m and its engine-r22p021m"; }

PHASE_A="summary preflight clone inspect fitplan config pack build stock screen suite"
PHASE_B="series build_series patched patches calib b3table screens accept soak promote"
[ "${1:-}" = all ] && set -- $PHASE_A
[ "${1:-}" = series-all ] && set -- $PHASE_B
for STAGE in "$@"; do
  declare -F st_$STAGE > /dev/null || { echo "unknown stage $STAGE (phase A: $PHASE_A; phase B: $PHASE_B)"; exit 2; }
  t0=$(date +%s); log "stage $STAGE start"
  st_$STAGE
  dt=$(( $(date +%s) - t0 )); printf "%s\t%s\t%d\n" "$STAGE" "$(date -Is)" $dt >> $R/times.tsv; touch $R/state/$STAGE.done
  log "stage $STAGE done in $dt s"
done
