#!/usr/bin/env bash
# run-ldr.sh — Local Deep Research (LDR 1.10.7) on top of Strata, web UI on http://127.0.0.1:5000
#
#   ./run-ldr.sh start     start strata-proxy (127.0.0.1:8090 -> Strata 8080) and the LDR web UI (127.0.0.1:5000)
#   ./run-ldr.sh stop      stop both (a running research is ended)
#   ./run-ldr.sh restart   restart LDR (strata-proxy keeps running; `stop` stops both)
#   ./run-ldr.sh status    what runs, health, Strata's state, MemAvailable
#   ./run-ldr.sh proxy     start strata-proxy only (8090; for the replay tools - 10-21: it had gone down with the queue service)
#
# Strata itself is not started or stopped here (~/ai-speed-testing/strata-compare/switch-model.sh strata does that).
# Everything lives in this folder: venv, caches, LDR's data dir (data/: encrypted per-user DBs, research outputs,
# logs). Only 127.0.0.1 is used. LDR is kept off the GPUs (CUDA_VISIBLE_DEVICES=""): Strata needs its VRAM.
#
# The settings that make LDR fit Strata are fixed here as LDR_* variables (LDR treats them as operator settings:
# they apply to every account and are locked in the UI). Three more (llm.streaming, llm.request_timeout,
# llm.max_retries) are per account in LDR 1.10.7; `tools/ldr-client.py setup` sets them (see README.md).
# Overrides for experiments: LDR_WORKERS (subagent workers, default 1), LDR_VIA_PROXY=0 (LDR talks to 8080 directly).
# Model profile (C3b, 10-29): LDR_MODEL_PROFILE=<name> (profiles/<name>.env) or a path, default flash-next - the
# context, output sizes, the sizes the agents and writers see, tokenizer, efforts, workers, step limits, code-tool
# reads; deep/modelprofile.py resolves it (an explicit variable > the profile > derived from the context / default).
#
# Profiles (LDR_PROFILE):
#   deep      (default) the patched LDR (patches/ldr/, LDR_DEEP=1: raised caps, time budget, context compaction,
#             evidence store, full report + citation check; files per research in results/deep-runs/), searching
#             LDR's own SearXNG on 127.0.0.1:8889 (searxng/: working web engines + academic engines)
#   baseline  pristine LDR 1.10.7 (baseline/site/ is put first on PYTHONPATH) with the setup session's settings,
#             searching searxng/'s baseline instance on 127.0.0.1:8890 (the chat page's engine choices) — for
#             measurements only
# Deep-profile knobs (defaults in local_deep_research/deep/__init__.py): LDR_DEEP_TIME_BUDGET_S (research phase,
# default 10800 = 3 h), LDR_DEEP_MAX_ITERATIONS, LDR_DEEP_MAX_SUB_ITERATIONS, LDR_DEEP_SUBAGENT_BUDGET_S,
# LDR_DEEP_MAX_SUBTOPICS, LDR_DEEP_FETCH_MAX_CHARS, LDR_DEEP_EXTRACT_MAX_CHARS, LDR_DEEP_COMPACT_AT, LDR_DEEP_VERIFY.
#
# C4 (staged 10-29, NOT installed; staging/c4/README.md): LDR_BACKEND=guard runs one arm of the Sonnet 5.5 experiment
# against its Anthropic budget guard (tools/anthropic_guard.py, started by c4-arm.sh) instead of Strata:
#   needs   C4_ARM_DIR (the arm's folder), GUARD_URL (http://127.0.0.1:<guard port>), C4_LDR_PORT (not 5000),
#           LDR_MODEL_PROFILE=sonnet-5-5 (+ LDR_ALLOW_DRAFT_PROFILE=1 while the profile is a draft);
#           optional LDR_VENV (the stock arm's own install; default: this venv)
#   changes no model discovery on 8080, no strata-proxy (the guard does caching, effort and the money), SearXNG is
#           checked, never started or stopped (shared service); run/, logs/, data/, results/deep-runs, the research
#           clock and the runner's next-job file all move into C4_ARM_DIR, so the live LDR is never touched
#   ./run-ldr.sh env    (guard mode only) print the environment LDR would get, start nothing
set -euo pipefail

WS=/home/USER/ai/deep-research
VENV=$WS/.venv
RUN=$WS/run
LOGS=$WS/logs
STRATA=${STRATA_URL:-http://127.0.0.1:8080}
PROXY_PORT=8090
LDR_PORT=5000
MODEL_PROFILE=${LDR_MODEL_PROFILE:-flash-next}
DEEP_PKG=${LDR_DEEP_PKG:-$VENV/lib/python3.12/site-packages/local_deep_research/deep}   # deep/modelprofile.py: the profile loader
PROFILES_DIR=${LDR_PROFILES_DIR:-$WS/profiles}
BACKEND=${LDR_BACKEND:-strata}      # C4: strata (default, unchanged) | guard
DATA_DIR=$WS/data
OUT_DIR=$WS/results/deep-runs
LDR_VENV_DIR=$VENV                  # the venv whose ldr-web runs (guard mode: LDR_VENV for the stock arm's install)
MIN_AVAIL_GB=14            # refuse to start below this (the floor is 12 GB while running since 2026-10-19 evening; was 18/22/20)
PROFILE=${LDR_PROFILE:-deep}
case $PROFILE in
  deep)     SEARXNG_PORT=8889; SEARXNG_INST=main;;
  # 2026-10-17: the baseline instance (8890: Brave + google cse) returns 0 results from this address (both suspended,
  # checked 22:2x), so the baseline searches the same working instance as deep - with LDR's own default search
  # settings (categories, result count). LDR_BASELINE_SEARXNG=baseline brings the old instance back.
  baseline) if [[ ${LDR_BASELINE_SEARXNG:-main} == baseline ]]; then SEARXNG_PORT=8890; SEARXNG_INST=baseline;
            else SEARXNG_PORT=8889; SEARXNG_INST=main; fi;;
  *) echo "run-ldr: unknown LDR_PROFILE=$PROFILE (deep|baseline)" >&2; exit 2;;
esac

# C4: an API arm behind the guard - every path that could touch the live LDR moves into the arm's folder
case $BACKEND in
  strata) ;;
  guard)
    c4_die() { echo "run-ldr: $*" >&2; exit 2; }
    [[ -n ${C4_ARM_DIR:-} ]] || c4_die "LDR_BACKEND=guard needs C4_ARM_DIR (the arm's folder)"
    [[ -n ${GUARD_URL:-} ]] || c4_die "LDR_BACKEND=guard needs GUARD_URL (http://127.0.0.1:<guard port>)"
    [[ -n ${C4_LDR_PORT:-} ]] || c4_die "LDR_BACKEND=guard needs C4_LDR_PORT (the arm's LDR port)"
    [[ $GUARD_URL =~ ^http://127\.0\.0\.1:[0-9]+$ ]] || c4_die "GUARD_URL must be http://127.0.0.1:<port> (got $GUARD_URL)"
    C4_ARM_DIR=$(realpath -m "$C4_ARM_DIR")
    case $C4_ARM_DIR/ in
      "$WS"/run/*|"$WS"/logs/*|"$WS"/data/*|"$WS"/results/deep-runs/*|"$WS"/results/quick-runs/*|"$WS"/jobs/*|"$WS"/reports/*)
        c4_die "C4_ARM_DIR=$C4_ARM_DIR is inside a live folder of the main LDR - refusing";;
    esac
    [[ $C4_ARM_DIR != "$WS" && $C4_ARM_DIR != / ]] || c4_die "C4_ARM_DIR=$C4_ARM_DIR - refusing"
    [[ $C4_LDR_PORT =~ ^[0-9]+$ ]] || c4_die "C4_LDR_PORT must be a number"
    case $C4_LDR_PORT in 5000|8080|8090|8888|8889|8890) c4_die "C4_LDR_PORT=$C4_LDR_PORT belongs to a live service - refusing";; esac
    RUN=$C4_ARM_DIR/run LOGS=$C4_ARM_DIR/logs DATA_DIR=$C4_ARM_DIR/data OUT_DIR=$C4_ARM_DIR/deep-runs
    LDR_PORT=$C4_LDR_PORT
    LDR_VENV_DIR=${LDR_VENV:-$VENV}
    ;;
  *) echo "run-ldr: unknown LDR_BACKEND=$BACKEND (strata|guard)" >&2; exit 2;;
esac

[[ ${1:-} == env ]] || mkdir -p "$RUN" "$LOGS" "$DATA_DIR" "$WS/tmp" "$WS/cache"

die()  { echo "run-ldr: $*" >&2; exit 1; }
info() { echo "run-ldr: $*"; }
pid_alive() { [[ -f $1 ]] && kill -0 "$(cat "$1")" 2>/dev/null; }
listener() { ss -H -ltnp "( sport = :$1 )" 2>/dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2 || true; }
avail_gb() { awk '/MemAvailable/{printf "%.1f", $2/1048576}' /proc/meminfo; }

# ---- the model profile (C3b, 10-29) -----------------------------------------------------------------------------
# P_FILE P_MODEL P_STATUS P_CONTEXT P_MAX_TOKENS P_TEMPERATURE P_WORKERS P_QUICK_ITERATIONS P_TOKENIZER_DIR, resolved
# like LDR resolves the rest (an explicit variable wins); a draft profile is refused unless LDR_ALLOW_DRAFT_PROFILE=1
model_profile() {
  local pv
  pv=$("$VENV/bin/python" -I "$DEEP_PKG/modelprofile.py" --shell --profile "$MODEL_PROFILE" --profiles-dir "$PROFILES_DIR") \
    || die "model profile '$MODEL_PROFILE' could not be read (see above)"
  eval "$pv"
  if [[ $P_STATUS != measured && ${LDR_ALLOW_DRAFT_PROFILE:-0} != 1 ]]; then
    die "model profile $P_FILE is '$P_STATUS' (unmeasured values) - set LDR_ALLOW_DRAFT_PROFILE=1 to use it anyway"
  fi
}

# ---- the environment LDR runs in --------------------------------------------------------------------------------
ldr_env() {
  local model=$1
  export TMPDIR=$WS/tmp XDG_CACHE_HOME=$WS/cache/xdg XDG_CONFIG_HOME=$WS/cache/config XDG_DATA_HOME=$WS/cache/share
  export PIP_CACHE_DIR=$WS/cache/pip HF_HOME=$WS/cache/huggingface TORCH_HOME=$WS/cache/torch
  export NLTK_DATA=$WS/cache/nltk_data TIKTOKEN_CACHE_DIR=$WS/cache/tiktoken MPLCONFIGDIR=$WS/cache/matplotlib
  export CRAWL4_AI_BASE_DIRECTORY=$WS/cache/crawl4ai PLAYWRIGHT_BROWSERS_PATH=$WS/cache/ms-playwright
  export CUDA_VISIBLE_DEVICES=""                                   # keep LDR (torch) off both GPUs
  export PYTHONWARNINGS="ignore:urllib3"                             # requests: urllib3/chardet version nag

  export LDR_DATA_DIR=$DATA_DIR
  export LDR_WEB_HOST=127.0.0.1 LDR_WEB_PORT=$LDR_PORT LDR_WEB_USE_HTTPS=false
  # LLM: Strata's OpenAI-compatible endpoint (through strata-proxy unless LDR_VIA_PROXY=0)
  export LDR_LLM_PROVIDER=openai_endpoint
  if [[ $BACKEND == guard ]]; then
    # C4: the arm's Anthropic guard (OpenAI-compatible; it drops the temperature, sends the effort, caches prompts)
    export LDR_LLM_OPENAI_ENDPOINT_URL=$GUARD_URL/v1
  elif [[ ${LDR_VIA_PROXY:-1} == 1 ]]; then
    export LDR_LLM_OPENAI_ENDPOINT_URL=http://127.0.0.1:$PROXY_PORT/v1
  else
    export LDR_LLM_OPENAI_ENDPOINT_URL=$STRATA/v1
  fi
  export LDR_LLM_MODEL=$model
  # 2026-10-17: 1.0 (your sampling everywhere: T 1.0 / top-p 0.95 / top-k 20 / min-p 0.05; LDR sends only the
  # temperature, Strata's config supplies the rest). Was 0.6 (the chat settings of 09-29).
  # 10-29: the temperature, context and max_tokens come from the model profile (flash-next: 1.0, 131072, 30000)
  export LDR_LLM_TEMPERATURE=$P_TEMPERATURE
  # context: 131072 (local window as asked; openai_endpoint only honours context_window_size when
  # "unrestricted" is off, so set that too). max_tokens 30000 (LDR's default; answer + thinking per call).
  export LDR_LLM_LOCAL_CONTEXT_WINDOW_SIZE=$P_CONTEXT
  export LDR_LLM_CONTEXT_WINDOW_UNRESTRICTED=false LDR_LLM_CONTEXT_WINDOW_SIZE=$P_CONTEXT
  export LDR_LLM_MAX_TOKENS=$P_MAX_TOKENS
  # search: LDR's own SearXNG (searxng/searxng.sh; env-locked, so LDR accepts the loopback URL), JSON API
  export LDR_SEARCH_TOOL=searxng
  export LDR_SEARCH_ENGINE_WEB_SEARXNG_DEFAULT_PARAMS_INSTANCE_URL=http://127.0.0.1:$SEARXNG_PORT
  export LDR_SEARCH_ENGINE_WEB_SEARXNG_DEFAULT_PARAMS_RESULT_FORMAT=json
  # SearXNG only: the langgraph agent otherwise also gets every keyless engine as its own tool (Wikipedia, arXiv,
  # PubMed, OpenAlex, ...), queried directly, each with an LLM relevance filter that fires ~10 parallel calls per
  # search (measured in the first test). These 13 have a registered flag; the other 5 (gutenberg, openlibrary,
  # pubchem, stackexchange, zenodo) are switched off per account by `tools/ldr-client.py setup`.
  local e
  for e in arxiv brave elasticsearch exa github google_pse mojeek openalex pubmed semantic_scholar serpapi sofya \
           tavily tinyfish wayback wikinews wikipedia; do
    export "LDR_SEARCH_ENGINE_WEB_${e^^}_AGENT_ENABLED=false"
  done
  # 2026-10-19: Semantic Scholar's own engine (official API, no key) as an agent tool for the user's research only
  # (LDR_RESEARCH_S2=1, set by the Jan runner; measurements keep it off - bench2 checks run/ldr.s2). Its LLM relevance
  # filter is off per account (ldr-client setup: ...semantic_scholar.default_params.enable_llm_relevance_filter=false)
  # and its journal-quality filter (an LLM call per new journal) off here.
  # 2026-10-19 (the user's option 2): quick answers stay quick - only when the Jan runner starts LDR for a quick job
  # (LDR_QUICK_LIMITS=1): no subtopic agents and at most 12 agent cycles. Measurements never (bench2 checks
  # run/ldr.quicklimits; the queue starts LDR without it).
  if [[ ${LDR_QUICK_LIMITS:-0} == 1 ]]; then
    export LDR_LANGGRAPH_AGENT_INCLUDE_SUB_RESEARCH=false LDR_LANGGRAPH_AGENT_MAX_ITERATIONS=$P_QUICK_ITERATIONS
  fi
  if [[ ${LDR_RESEARCH_S2:-0} == 1 ]]; then
    export LDR_SEARCH_ENGINE_WEB_SEMANTIC_SCHOLAR_AGENT_ENABLED=true
    export LDR_SEARCH_ENGINE_WEB_SEMANTIC_SCHOLAR_JOURNAL_REPUTATION_ENABLED=false
  fi
  # Strata answers one request at a time: parallel subagents only queue (LDR_WORKERS > the profile's, 1 for flash-next)
  export LDR_LANGGRAPH_AGENT_MAX_SUBAGENT_WORKERS=$P_WORKERS
  if [[ $PROFILE == deep ]]; then
    # the tokenizer from the profile (flash-next: $WS/deep/tokenizer); the deep package reads the rest of the profile
    export LDR_DEEP=1 LDR_DEEP_TOKENIZER_DIR=$P_TOKENIZER_DIR LDR_DEEP_OUT_DIR=$OUT_DIR
    export LDR_DEEP_MODEL_PROFILE=$P_FILE
    # jobs from Jan (2026-10-17): the research clock (pauses held by strata-proxy's gate do not count) and the
    # runner's per-job settings (research time, the user's files, earlier runs to continue from)
    export LDR_DEEP_CLOCK_FILE=$RUN/research-clock.json LDR_DEEP_NEXT_FILE=$RUN/next-research.json
    # one search reaches the web engines and the academic ones (arXiv, Semantic Scholar, PubMed, Europe PMC,
    # Crossref, Google Scholar) inside SearXNG; 50 results per search (LDR's maximum)
    export LDR_SEARCH_ENGINE_WEB_SEARXNG_DEFAULT_PARAMS_CATEGORIES='["general", "science"]'
    export LDR_SEARCH_ENGINE_WEB_SEARXNG_DEFAULT_PARAMS_MAX_RESULTS=50 LDR_SEARCH_MAX_RESULTS=50
  elif [[ $LDR_VENV_DIR == "$VENV" ]]; then
    export PYTHONPATH=$WS/baseline/site${PYTHONPATH:+:$PYTHONPATH}      # pristine LDR 1.10.7 first
  fi                                  # (C4's stock arm in its own install: nothing to put first)
}

strata_model() {
  curl -s -m 5 "$STRATA/v1/models" | "$VENV/bin/python" -c "import json,sys; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null || true
}

start_proxy() {
  if pid_alive "$RUN/proxy.pid"; then info "strata-proxy already running (pid $(cat "$RUN/proxy.pid"))"; return; fi
  [[ -z $(listener $PROXY_PORT) ]] || die "port $PROXY_PORT is taken by pid $(listener $PROXY_PORT)"
  # the research gate (2026-10-17): the runner's control file in, the research clock out (tools/strata-proxy.py)
  PROXY_PORT=$PROXY_PORT UPSTREAM=$STRATA PROXY_MODE_FILE=$RUN/proxy-mode.json PROXY_LOG=$LOGS/llm-calls.jsonl \
    PROXY_CONTROL_FILE=$RUN/research-control.json PROXY_CLOCK_FILE=$RUN/research-clock.json \
    setsid nohup "$VENV/bin/python" "$WS/tools/strata-proxy.py" >> "$LOGS/proxy.out" 2>&1 < /dev/null &
  echo $! > "$RUN/proxy.pid"
  local i; for i in $(seq 1 20); do [[ -n $(listener $PROXY_PORT) ]] && break; sleep 0.25; done
  [[ -n $(listener $PROXY_PORT) ]] || die "strata-proxy did not start (see $LOGS/proxy.out)"
  info "strata-proxy on 127.0.0.1:$PROXY_PORT -> $STRATA (log $LOGS/llm-calls.jsonl)"
}

do_start() {
  local model avail
  model_profile                      # a bad or draft profile stops here, before anything is started
  avail=$(avail_gb)
  awk -v a="$avail" -v m=$MIN_AVAIL_GB 'BEGIN{exit !(a >= m)}' || die "MemAvailable is ${avail} GB (< ${MIN_AVAIL_GB} GB); not starting"
  if [[ $BACKEND == guard ]]; then
    model=$P_MODEL                   # C4: the profile's model; the guard must serve it (and cache prompts)
    [[ -n $model ]] || die "model profile $P_FILE names no model (LDR_PROFILE_MODEL)"
    guard_check "$model"
    [[ $(curl -s -m 5 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$SEARXNG_PORT/" || true) =~ ^[23] ]] \
      || die "SearXNG ($SEARXNG_INST, 127.0.0.1:$SEARXNG_PORT) does not answer - a shared service, not started from here"
  else
  model=$(strata_model)
  [[ -n $model ]] || die "Strata does not answer on $STRATA/v1/models — start it first (switch-model.sh strata)"
  SEARXNG_INSTANCE=$SEARXNG_INST "$WS/searxng/searxng.sh" start || die "LDR's SearXNG ($SEARXNG_INST, 127.0.0.1:$SEARXNG_PORT) did not start"
  [[ ${LDR_VIA_PROXY:-1} == 1 ]] && start_proxy
  fi
  if pid_alive "$RUN/ldr.pid"; then info "LDR already running (pid $(cat "$RUN/ldr.pid"))"; do_status; return; fi
  [[ -z $(listener $LDR_PORT) ]] || die "port $LDR_PORT is taken by pid $(listener $LDR_PORT)"
  local log=$LOGS/ldr-web_$(date +%Y%m%dT%H%M%S).log
  (
    ldr_env "$model"
    cd "$WS"
    echo "# run-ldr $(date -Is) profile=$PROFILE model=$model llm=$LDR_LLM_OPENAI_ENDPOINT_URL workers=$LDR_LANGGRAPH_AGENT_MAX_SUBAGENT_WORKERS searxng=$LDR_SEARCH_ENGINE_WEB_SEARXNG_DEFAULT_PARAMS_INSTANCE_URL" > "$log"
    echo "# model profile: $P_FILE (${P_MODEL:-?}, $P_STATUS; context $P_CONTEXT, max_tokens $P_MAX_TOKENS)" >> "$log"
    { env | grep -E '^LDR_DEEP' || true; } | sort | sed 's/^/# /' >> "$log"   # (none in the baseline profile)
    echo "$PROFILE" > "$RUN/ldr.profile"
    echo "$(basename "$P_FILE" .env) $(sha256sum < "$P_FILE" | cut -c1-12)" > "$RUN/ldr.modelprofile"   # name + content
    # report / citation-check efforts LDR read at start (deep profile; "default" = the deep package's xhigh) - bench2 checks it
    echo "report=${LDR_DEEP_REPORT_EFFORT:-default} verify=${LDR_DEEP_VERIFY_EFFORT:-default}" > "$RUN/ldr.efforts"
    # 2026-10-19: the search fallback (patch 0005: Exa, then Tavily) is on only with LDR_SEARCH_FALLBACK=1 (the Jan runner sets it,
    # the measurements do not; bench2.py refuses to measure on an LDR that has it)
    if [[ ${LDR_SEARCH_FALLBACK:-0} == 1 ]]; then echo on > "$RUN/ldr.fallback"; else echo off > "$RUN/ldr.fallback"; fi
    if [[ ${LDR_RESEARCH_S2:-0} == 1 ]]; then echo on > "$RUN/ldr.s2"; else echo off > "$RUN/ldr.s2"; fi
    if [[ ${LDR_QUICK_LIMITS:-0} == 1 ]]; then echo on > "$RUN/ldr.quicklimits"; else echo off > "$RUN/ldr.quicklimits"; fi
    # 2026-10-21: phase 4 stage 2 items (deep profile only) - bench2.py and the research runner check run/ldr.items:
    #   setup    item 1: the user's setup profile in the lead and report prompts + the setup check (LDR_DEEP_SETUP_PROFILE)
    #   critic   item 3: the critic's advisory "Check these" list (LDR_DEEP_CRITIC=1)
    #   verify2  item 3: the two-source verifier, flag-only, in the same list (LDR_DEEP_VERIFY2=flag)
    items=""
    if [[ $PROFILE == deep && -n ${LDR_DEEP_SETUP_PROFILE:-} ]]; then items+=" setup"; else unset LDR_DEEP_SETUP_PROFILE; fi
    if [[ $PROFILE == deep && ${LDR_DEEP_CRITIC:-0} == 1 ]]; then items+=" critic"; else unset LDR_DEEP_CRITIC; fi
    if [[ $PROFILE == deep && ${LDR_DEEP_VERIFY2:-} == flag ]]; then items+=" verify2"; else unset LDR_DEEP_VERIFY2; fi
    # 2026-10-23: item 4, the "tried / ruled out" list from the user's files (LDR_DEEP_TRIED=1), and item 2, the "not
    # yet" fresh check in the report stage (LDR_DEEP_NOTYET=1), bundled into item 4's stage 2-3 runs (the user)
    if [[ $PROFILE == deep && ${LDR_DEEP_TRIED:-0} == 1 ]]; then items+=" tried"; else unset LDR_DEEP_TRIED; fi
    if [[ $PROFILE == deep && ${LDR_DEEP_NOTYET:-0} == 1 ]]; then items+=" notyet"; else unset LDR_DEEP_NOTYET; fi
    # 2026-10-27: phase 4, the read-only code tool (LDR_DEEP_CODE=1): a project's GitHub source at a version - grep, line
    # reads, tree, issues / PRs / commits (deep/codetool.py; clones capped and deleted after the run)
    if [[ $PROFILE == deep && ${LDR_DEEP_CODE:-0} == 1 ]]; then items+=" code"; else unset LDR_DEEP_CODE; fi
    # 2026-10-27: phase 4's six fixes + the consistency pass (LDR_DEEP_FIX=all or a comma list of version, inline, arith,
    # cite, baseline, budget, consist; deep/checks.py) - deep profile only; the item reads "fix:<list>"
    # (the item is "fixes" for all of them - the name the queue plans use - or "fix:<list>" for a subset)
    # 10-28: the bundle's items 5 + 6 ride on the same variable (LDR_DEEP_FIX=all,read,claims) and get their own item
    # names, "read" and "claims"; "all" stays "fixes", any other subset stays "fix:<list>"
    if [[ $PROFILE == deep && -n ${LDR_DEEP_FIX:-} ]]; then
      rest=""
      for f in ${LDR_DEEP_FIX//,/ }; do
        case $f in all) items+=" fixes";; read|claims) items+=" $f";; *) rest+=",$f";; esac
      done
      [[ -n $rest ]] && items+=" fix:${rest#,}"
    else unset LDR_DEEP_FIX; fi
    items=${items# }; echo "${items:-off}" > "$RUN/ldr.items"; rm -f "$RUN/ldr.setup"
    [[ $BACKEND == guard ]] && echo "# C4 guard $GUARD_URL, arm folder $C4_ARM_DIR, ldr-web from $LDR_VENV_DIR" >> "$log"
    PYTHONFAULTHANDLER=1 setsid nohup "$LDR_VENV_DIR/bin/ldr-web" >> "$log" 2>&1 < /dev/null &   # faulthandler: a crash leaves its Python stacks in the log (10-18)
    echo $! > "$RUN/ldr.pid"
  )
  ln -sfn "$log" "$LOGS/ldr-web.log"
  info "starting LDR (pid $(cat "$RUN/ldr.pid"), log $log) ..."
  local i; for i in $(seq 1 120); do
    [[ -n $(listener $LDR_PORT) ]] && break
    pid_alive "$RUN/ldr.pid" || { tail -20 "$log"; die "LDR exited during start"; }
    sleep 0.5
  done
  [[ -n $(listener $LDR_PORT) ]] || die "LDR did not open 127.0.0.1:$LDR_PORT within 60 s (see $log)"
  info "LDR web UI: http://127.0.0.1:$LDR_PORT (model $model)"
  do_status
}

stop_pidfile() {  # $1 pidfile, $2 name: TERM the process group, then KILL after 15 s
  local f=$1 name=$2 pid i
  pid_alive "$f" || { rm -f "$f"; info "$name is not running"; return; }
  pid=$(cat "$f")
  kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  for i in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
  if kill -0 "$pid" 2>/dev/null; then kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true; fi
  rm -f "$f"; info "$name stopped (pid $pid)"
}

do_stop() {
  stop_pidfile "$RUN/ldr.pid" LDR
  [[ $BACKEND == guard ]] || stop_pidfile "$RUN/proxy.pid" strata-proxy     # C4: the guard is c4-arm.sh's
}

# C4: the arm's guard answers, serves the profile's model and caches prompts (LDR_PROMPT_CACHING=required)
guard_check() {
  local st
  st=$(curl -s -m 5 "$GUARD_URL/v1/guard/status") || die "the guard does not answer on $GUARD_URL - start it with c4-arm.sh"
  "$VENV/bin/python" -I -c '
import json, sys
s, want = json.loads(sys.argv[1]), sys.argv[2]
if s.get("model") != want:
    sys.exit("the guard serves %r, the profile wants %r" % (s.get("model"), want))
if s.get("cache") != "on":
    sys.exit("the guard does not cache prompts")
c = s["caps_usd"]
print("run-ldr: guard %s, run %s: spent $%.2f of $%.2f (all runs $%.2f of $%.2f)"
      % (s["arm"], s["run"], s["run_spent_usd"], c["run"], s["total_spent_usd"], c["total"]))
' "$st" "$1" || die "guard check failed ($GUARD_URL)"
}

do_status() {
  local p
  if pid_alive "$RUN/ldr.pid"; then
    p=$(cat "$RUN/ldr.pid")
    echo "LDR ($(cat "$RUN/ldr.profile" 2>/dev/null || echo '?') profile, model profile $(cat "$RUN/ldr.modelprofile" 2>/dev/null || echo '?')): running (pid $p, RSS $(( $(ps -o rss= -p "$p" 2>/dev/null || echo 0) / 1024 )) MiB), UI http://127.0.0.1:$LDR_PORT -> HTTP $(curl -s -m 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:$LDR_PORT/auth/login || echo -), log $(readlink "$LOGS/ldr-web.log" 2>/dev/null)"
    ss -H -ltnp 2>/dev/null | grep "pid=$p," | awk '{print "  listening: " $4}'
  else
    echo "LDR: not running"
  fi
  if [[ $BACKEND == guard ]]; then    # C4: the arm's guard instead of strata-proxy / Strata
    echo "guard $GUARD_URL: $(curl -s -m 3 "$GUARD_URL/v1/guard/status" | "$VENV/bin/python" -c "import json,sys; s=json.load(sys.stdin); print(s['arm'], s['run'], s['model'], 'spent \$%.2f of \$%.2f, all runs \$%.2f of \$%.2f' % (s['run_spent_usd'], s['caps_usd']['run'], s['total_spent_usd'], s['caps_usd']['total']))" 2>/dev/null || echo 'not answering')"
    echo "SearXNG 127.0.0.1:$SEARXNG_PORT: HTTP $(curl -s -m 3 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$SEARXNG_PORT/" || echo -)"
    echo "MemAvailable: $(avail_gb) GB"
    return
  fi
  if pid_alive "$RUN/proxy.pid"; then echo "strata-proxy: running (pid $(cat "$RUN/proxy.pid")), 127.0.0.1:$PROXY_PORT -> $STRATA, mode $(cat "$RUN/proxy-mode.json" 2>/dev/null || echo 'pass-through')"
  else echo "strata-proxy: not running"; fi
  echo "Strata: $(curl -s -m 3 "$STRATA/metrics" | "$VENV/bin/python" -c "import json,sys; d=json.load(sys.stdin); l=d['live']; print(d['engine']['model'], '-', l['state'], '(queued', str(l['queued'])+')')" 2>/dev/null || echo 'not answering')"
  "$WS/searxng/searxng.sh" status || true
  SEARXNG_INSTANCE=baseline "$WS/searxng/searxng.sh" status || true
  echo "MemAvailable: $(avail_gb) GB"
}

case ${1:-} in
  start) do_start;;
  stop) do_stop;;
  restart) stop_pidfile "$RUN/ldr.pid" LDR; do_start;;     # the proxy keeps running (other clients may be using it)
  status) do_status;;
  proxy) [[ $BACKEND != guard ]] || die "proxy: not in guard mode (C4)"; start_proxy;;
  env)                                # C4: what LDR would get, nothing started
    [[ $BACKEND == guard ]] || die "env: only with LDR_BACKEND=guard"
    model_profile
    ( ldr_env "$P_MODEL"; env | grep -E '^(LDR_|PYTHONPATH=|TMPDIR=|CUDA_VISIBLE_DEVICES=)' | sort );;
  *) sed -n '2,20p' "$0"; exit 2;;
esac
