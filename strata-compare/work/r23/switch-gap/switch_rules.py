#!/usr/bin/env python3
"""switch_rules.py - r23 (written 2026-11-10 at the desk, NOT RUN on real data; only its selftest ran, on synthetic data):
the rules of THE v0.2.13 PORT'S SWITCH CHECKS (Karl 11-10; the plan results/r23/port-0213/SWITCH-CHECKS-PLAN-1110.md; the
driver work/r23/switch-gap/gap-switch0213.sh). Written before any run; the driver freezes this text (plus the sha256 of
every file it imports or the gap runs) into the gap's rules.txt before any engine starts, and `decide` flags a change.
NOTHING SWITCHES: 8080 stays the daily; the verdict is a report to Karl.

THE ARMS (written by `arms` into OUTDIR/configs/, checked by `cfgcheck`; each its own engine log logs/engine-r23sw-NAME.log,
never the served engine's logs/engine-P028x.log; two GPUs, the helper cache on, adaptation on, as served):
  B   the daily as served: configs/P028x.json in its test form (without the --vision flag and the vision / fallback /
      model_not_running keys: sq.py's STRIP_ARGS / STRIP_KEYS, afetch_rules.py's and af_adopt.py's form) = configs/x28h.json
      + STRATA_HC_UPMIX=1 + STRATA_ADAPT_FETCH=2 with exe engine-r23afetch/strata (sha256 153ce47d3ef0), key by key; server
      strata-r22p028x/serve/server.py. 8080 serves this same binary: the driver never stops an engine from before the gap.
  P   the port: configs/P0213x-af2.json in the same test form = configs/P0213x.json's test form + STRATA_ADAPT_FETCH=2, key
      by key; exe engine-r23p0213/strata (sha256 639dfb1b7042, its SOURCE naming r23-port0213 6dd81ecd1); server
      strata-r23p0213/serve/server.py (P's own server tree: srv.sh starts the config's "server").
      P = B apart from: exe, server, log, _comment, the port's keys ("drafting": "mtp", "user_args": ["--kv-resident",
      "32768"]) and the port's env pins (PORT_PINS: port0211_rules.py's 18 + STRATA_ARENA_FILE_CACHE=0); the same args,
      sampling (T 1.0 / 0.95 / 20 / min-p 0.05), U and STRATA_ADAPT_FETCH=2 (the plan: "apart from those pins and the
      paths, the two arms are the same config").
  B-dbg / P-dbg  B / P + STRATA_DEBUG=1 (server.py prints each request's generated ids; neither engine binary reads
      STRATA_DEBUG, checked): C2's arms.
  The sampled arms (spec-port0213.json, sq.py derive): R1 = R2 = B-dbg, X = P-dbg, VF = X + STRATA_ADAPT_FETCH_VERIFY=1 +
      STRATA_ADAPT_CHECKRES=1 (their logs under the sampled folder); cfgcheck --sampled compares them key by key.
  EVERY START (one fresh test server on 127.0.0.1:8081 through bringup/lib/with_server.sh), its gates (TAG = the start):
    env_TAG   port0211_rules.py envcheck --ngpu 2 --pins: the engine (by /proc/PID/exe) has the config's env exactly, none
              of the port's pins set behind a config that lacks it, STRATA_ROUTE_TAIL_SKIP=0, 2 GPUs, --kv-resident last
              (user_args); its PARENT is the config's server.py with the server pins as the config sets them
    fenv_TAG  `armenv`: exactly one engine of the arm's binary, its sha256 the arm's; the STRATA_ADAPT_FETCH* keys and
              STRATA_DEBUG exactly as the config has them, in the engine AND in its parent server.py's environment (the
              server reads STRATA_DEBUG); the parent's command line names the config (--config) and the config's server
    envsq_TAG (the sampled starts) sq.py envcheck
    line_TAG  the start line "STRATA_ADAPT_FETCH=2: the PCIe share takes" and no "STRATA_ADAPT_FETCH is off" (both arms)
    fatal_TAG a fatal GPU error / stall / engine restart / non-finite line in the start's engine-log slice or server log
    foreign_TAG  another GPU user before (60 s) or during the start; void_TAG  the run left its test server or an engine
              behind (stopped)
    A FAIL in any of these: the start is NOT the arm, or not clean - what it measured does not count (its check NOT
    DECIDED; a read-back FAIL stays FAIL; a C2 / C3 FAIL / DIFFERS on such a start becomes NOT DECIDED).

C1  C++ PARITY AND UNIT TESTS for the files our patches change, and the read-back start.
    The programs: build-port0213.sh's `switchtests` targets in strata-r23p0213/build-switch (SWITCH_TARGETS: the tests set,
    the shape gap's GEO_TESTS at the default shape, REVIEW-1105 4.3's list). Every registered ctest entry whose program is
    one of them (read from build-switch's CTestTestfile.cmake, its registered args, env, timeout and skip code apply; a
    `cmake -E env ...` wrapper counts by the program it runs) - prefill_fused_iq_test without --v2 (prefill_fused_iq_test,
    _q2n, _nt256, _f16, _ws) and with it (prefill_fused_v2_test) - plus the direct runs (no ctest entry; the shape gap's):
    patch_guard_test on the ISTA shard 1 + the MTP layer (GPUs hidden), qsa_prompt_attn_parity, prefill_fused_iq_test
    --edge --no-timing.
      CPU (CPU_PROGRAMS: cost_gate_test, draft_cum_test, spec_prob_test, gated_proposal_test, q8k_quant_parity (+ _avx),
      gguf_geometry_test, patch_guard_test): BEFORE the gap, 8080 serving, nice 19, CUDA_VISIBLE_DEVICES empty.
      GPU (every other entry and the two other direct runs): IN the gap, before any server, both GPUs (the 5080 first), the
      kernel-error poll and the foreign-GPU watch around them.
    Also before the gap (CPU, nice 19): the server test suite of strata-r23p0213/serve (unittest discover -v, TMPDIR in the
    gap's folder) with node (/home/USER/.unsloth/node/bin) first on PATH, so the node tests run (REVIEW 4.4); failures only
    in KNOWN_SERVE_FAILS (test_hip_ordinal); `node --check serve/web/app.js`.
    The read-back start (the fetch patch's own files, expert_source.cpp / generate.cpp, have no parity program): VF = P +
    STRATA_ADAPT_FETCH_VERIFY=1 + STRATA_ADAPT_CHECKRES=1 (K 2 = 8 requests, sq_client.py, budget 300 s), judged by sq.py
    verify -> verify-VF.json (PASS = no mismatch line, >= 200 admitted slots read back, every summary 0 differ, >= 4
    requests finished; FAIL = a mismatch line or a differ > 0). Not decided on its first try: tried once more.
    C1 PASS = every program passes (its own documented skip, rc 77 / SKIP_RETURN_CODE, allowed), the server suite has no
    failure outside KNOWN_SERVE_FAILS, the node tests ran (no "node is not installed" skip) and `node --check` passes, AND
    the read-back is PASS. FAIL = a program or a server / node test fails (a program's timeout is a failure), or the
    read-back FAILs. NOT DECIDED otherwise (not run, not reached, a foreign GPU user during the parity run, VF's start
    gates failed, and (review M4) a server suite cut by its timeout: no "Ran N tests" line = NOT DECIDED, not FAIL).
    (coordinator 11-10) A CPU part not PASS before the gap (the CPU ctest entries / patch_guard_test, the server suite,
    the node tests) does NOT stop the gap: it is C1 FAIL (or NOT DECIDED) with the failing tests named, and the gap opens
    for the other checks. A missing binary, a sha mismatch or another safety check still refuses as before.

C2  SERVED OUTPUTS against the daily (the server path, output for output). C2_PLAN: 4 prompts x 2 seeds (SEEDS_C2), each
    arm's own server at the standard sampling (T 1.0, top_p 0.95, top_k 20, min_p 0.05, presence 0, frequency 0,
    repetition 1, the fixed seed): "think" = W1-think with thinking ON, max_tokens 1536 (no budget of its own: answer_room
    caps the thinking at 1024, server.py:6191-6199; a longer thinking ends in the wrap-up continuation, server.py:6573-6599:
    its server line "thinking budget reached"); "code" W2-code, "conv" C-conv, "prose" C-prose thinking off, 512 tokens.
    The generated ids from the server's STRATA_DEBUG raw-ids line ("[strata] raw ids: [...]": every id, the wrap-up's and
    the stop token included). Arms in this order: B1 (B-dbg), B2 (B-dbg again, a fresh start), P (P-dbg).
      B-reproducible request = B1's ids equal B2's (and both have them). Information only: a request where B differs from
      itself.
      EXACT     = every planned request has ids on B1, B2 and P, at least one is B-reproducible, and on every
                  B-reproducible one P's ids equal B1's.
      DIFFERS   = some B-reproducible request gives other ids (or another prompt length) on P. Not a fail by itself: C3
                  decides (the "exactness or distribution" test).
      no B-reproducible request at all (every ids pair is complete): by C2_NOREF_FORM - "differs" [the frozen form]: as
                  DIFFERS (C3 decides; flagged), "not-decided": NOT DECIDED.
      NOT DECIDED = otherwise: a request missing / failed on an arm, an arm's start gates failed (and no DIFFERS on clean
                  starts).
    INFO: the continuation seen per arm (the "think" requests' server lines), the text / reasoning hashes.

C3  THE SAMPLED TEST (results/r23/SAMPLED-QWEN-DESIGN-1109.md, unchanged math; work/r23/sampled-qwen/, spec-port0213.json):
    R1 = B (K 8 = 32 requests), X = P (K 8), R2 = B again (K 4 = 16, the noise bound); the 4 prompts W1-think, W2-code,
    C-conv, C-prose, thinking off, 512 tokens; the x28h scorer. sq.py's own rule (sq.py rule -> sampled/rule.txt, written
    before any engine start; sq.py decide refuses a changed rule.txt). C3 = sq.py decide's candidate verdict for X
    (decision.json candidates.X): PASS = D2(X, R1) <= band = max(11.345, D2(R2, R1)) (with the harness's validity and power
    rules), FAIL = above the band, else NOT DECIDED. The gap's start gates on R1 / R2 / X and the scorer's env check
    (env_sqscore) failing: a PASS or FAIL becomes NOT DECIDED. (sq.py's "overall" X also folds in the read-back VF, which
    is C1's: INFO here.)

C4  WEB SEARCH END TO END. The server's own web search: "strata_web": true, the web page's path through run_with_mcp
    (JSON, no Origin header: _own_page). `webpath` reads both server trees' serve/websearch.py and the arms' "web_search"
    blocks: SEARXNG ONLY (only the local 127.0.0.1:8888) or PAID PATH (11-10 desk finding, both trees: websearch.py's
    _fallback -> deep-research tools/search_fallback.py, Exa then Tavily, used when SearXNG errors or returns < 3
    results). (coordinator 11-10) A PAID PATH runs C4 BOUNDED, under Karl's standing paid-search rule (<= 30 paid
    searches a test run; 25 % of each provider's month kept for Jan chat; every caller stops at ~10 % left):
      THE BUDGET CHECK (`paidcheck`, before the gap and again right before C4): each provider's month use and cap read
      through the modules' own counter code (exa_fallback.usage() / tavily_fallback.usage() / available(); no key file is
      read or printed). The cap = the provider's month budget (Exa MONTH_CREDIT_USD $10, Tavily MONTH_CREDITS 1,000 - the
      base of paid_budget.py's 25 % / 10 % shares). An available provider (its key file present, Exa's month not closed)
      with less than 25 % of its cap + PAID_MIN_CALLS (10) calls' worth left -> C4 NOT RUN ("C4 NOT RUN: paid budget"):
      INFO, and the verdict cannot be PASS (INCOMPLETE, C4 named). A provider that is not available cannot be charged.
      DURING C4 - THE HARD LIMIT (review S1) is paid_budget.py's run cap inside the test server: it runs with
      PAID_SEARCH_KIND=test, PAID_SEARCH_RUN=<this gap's run id> (one id for both arms) and PAID_SEARCH_RUN_CAP = B 5,
      P 10 (review M6: the 10 split 5 per arm - B can never take more than 5, so P always has its 5, and both arms
      together never more than 10). Before anything is sent on an arm, c4_web.py checks those three in the test server's
      own /proc/PID/environ (gate penv_webB / penv_webP); one missing -> nothing sent on that arm, "C4 NOT RUN (env)".
      c4_web.py's own stop is the SOFT one: it counts the paid calls as the counters' delta (Exa searches + Tavily count)
      against the baseline read right before C4 and stops sending at PAID_ARM_STOP (5) on the arm or PAID_STOP (10) in all
      (the requests not sent: recorded not run). Every other test server of the gap runs with PAID_SEARCH_KIND=test and no
      run id (review M7: 0 paid calls allowed). C4 then judges the requests that ran; fewer than 2 requests run on an arm
      -> NOT DECIDED. The paid-call count (per request, per arm, the counters before / after) is in the decision.
    C4 runs only if 127.0.0.1:8888 listens: C4_PROMPTS (3 search prompts, thinking off, max_tokens 1024
    a round, the standard sampling, seeds SEEDS_C4) on B, then on P (B / P test forms), one fresh server each. Per request:
    completed (a finish reason and [DONE], no error chunk, within C4_TIMEOUT_S), search rounds (web_search calls),
    fetch_page calls and the pages they opened (result ok), the URLs the answer cites, errors (an error chunk, a failed
    request, a tool error result, the lost-answer line, a fatal line in the request's server-log slice).
      cited source by CITE_FORM: "tool-url" [the frozen form, coordinator 11-10] = a URL the answer cites that a
      web_search result or a fetch_page call of this request returned; "fetch-page" = one a fetch_page call opened.
    PASS = on P, every request that ran on both arms and completed on B also completes, with >= 1 search round, an answer
    citing >= 1 source, and no error or fatal line; FAIL = such a request fails one of these on clean starts, or (review
    S2) a fatal / stall / engine-restart / non-finite line on P's C4 start (fatal_webP); NOT DECIDED otherwise (B's start
    gates failed - B's fatal line included -, P's other start gates failed, < 2 requests run on an arm, B completed none,
    a missing record).

C5  HOW OFTEN THE LOST-ANSWER GUARD (#3961) FIRES - information. Every P server log of the gap (VF, C2's P, C3's X and,
    when C4 ran, its P; the screen's and the fixtures' P starts): the count of "[strata] a request ended without an
    answer and without a finish reason" per log, the runs it saw (its "[strata] done:" lines) and the client requests
    sent there; each firing named (log, line, the request around it). Our workload on P: one pass of the 9-workload screen
    (work/r22/abarm.sh: warm-up, W1-W3, the 2 agent turns, the 4 research replays; T 1.0 / 0.95 / 20 / 0.05) and the three
    chat fixtures (Basalt's decode fixtures conv / struct / prose, their user texts and max_tokens 1200 / 8192 / 1200,
    sent by fixtures_client.py at the standard sampling - the driver's rule for every request; Basalt's own T 0.6 / T 0
    is not used). A firing on the workload: a recommendation line on whether a small switch patch is worth carrying.

INFO (never a verdict): the screen's speed, P against B, one pass each (decode / prompt geometric means over the 9, the
11-07 amendment's prompt numbers; no noise estimate from one pass); the fixtures' decode tok/s on P; exact7 of P (its
test form) at pin 2500 against the stored x28h-e7a (bit-identity is not expected with STRATA_ADAPT_FETCH=2 on).

THE VERDICT (decide -> OUTDIR/verdict.txt, decision.txt / .json, result-line.txt):
  SWITCH CHECKS PASS  = C1, C3 and C4 PASS, and C2 EXACT or DIFFERS (DIFFERS-with-C3-PASS). C5 is reported.
  SWITCH CHECKS FAIL  = any of C1, C3 or C4 FAIL (each named; parts that could not run are listed too).
  INCOMPLETE          = otherwise: a check could not run or decide (named), C2 NOT DECIDED included.
  NOTHING SWITCHES either way; the port's baseline gate (exactness on the CLI path, long40, the 3-pass screen, Basalt's
  speed rule) and REVIEW 4.7 (the single-card fallback) are not covered (the plan's "not covered").

THE SWITCHES (one constant each; their values at the freeze are written into rules.txt): CITE_FORM ("tool-url" |
"fetch-page"), C2_NOREF_FORM ("differs" | "not-decided"). Both stay implemented and selftested.

Subcommands: forms, targets, arms, cfgcheck, ctestlist, parity, pstatus, servetests, nodecheck, webpath, paidcheck, render,
armenv, startline, c2plan, c4plan, fixtures, c2compare, c4judge, lost, rules, decide, selftest. Python: .venv/bin/python -I -B at nice 19.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
import re
import shutil
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.dont_write_bytecode = True     # it loads modules from trees it must not write to

# ======== THE SWITCHES (see the docstring)
CITE_FORM = "tool-url"            # "tool-url" [coordinator 11-10] | "fetch-page"
C2_NOREF_FORM = "differs"         # "differs" | "not-decided"
FORMS = {"CITE_FORM": ("tool-url", "fetch-page"), "C2_NOREF_FORM": ("differs", "not-decided")}

WS = Path("/home/USER/ai-speed-testing/strata-compare")
SG = WS / "work/r23/switch-gap"
SQD = WS / "work/r23/sampled-qwen"
SPEC = SG / "spec-port0213.json"
CFG_B = WS / "configs/P028x.json"
CFG_P = WS / "configs/P0213x-af2.json"
CFG_P0 = WS / "configs/P0213x.json"
X28H = WS / "configs/x28h.json"
EXE_B = WS / "engine-r23afetch/strata"
EXE_P = WS / "engine-r23p0213/strata"
SHA = {"B": "153ce47d3ef0", "P": "639dfb1b7042"}
EXE = {"B": EXE_B, "P": EXE_P}
SRV = {"B": WS / "strata-r22p028x/serve/server.py", "P": WS / "strata-r23p0213/serve/server.py"}
TREE = {"B": WS / "strata-r22p028x", "P": WS / "strata-r23p0213"}
BUILD = WS / "strata-r23p0213/build-switch"
WORKLOADS = Path("/home/USER/ai-speed-testing/basalt-ab/scripts/workloads.json")
BPD = Path("/home/USER/ai-speed-testing/basalt-pr90-data")
GGUF = WS / "models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf"
MTP = WS / "strata-v0115/mtp/rt"
RU = WS / "work/r23/port0211_rules.py"
G17 = WS / "work/r22/g17_rules.py"
SHAPE = WS / "work/r23/shape-gap/shape_rules.py"
AFR = WS / "work/r23/afetch-gap/afetch_rules.py"
RULE_FILES = (SG / "switch_rules.py", SG / "gap-switch0213.sh", SG / "c2_client.py", SG / "c4_web.py",
              SG / "fixtures_client.py", SPEC, SQD / "sq.py", SQD / "sq_stat.py", SQD / "sq_client.py", RU, G17, SHAPE, AFR,
              WS / "work/r23/build-port0213.sh")
# build-port0213.sh `switchtests` (11-10): the tests set + the shape gap's GEO_TESTS + REVIEW-1105 4.3's list, sorted, unique
SWITCH_TARGETS = tuple(sorted(set((
    "patch_guard_test cost_gate_test draft_cum_test spec_prob_test gated_proposal_test spec_verify_parity "
    "spec_proposal_parity prefill_fused_iq_test native_expert_parity gguf_geometry_test "
    "gguf_geometry_test patch_guard_test prefill_fused_iq_test prefill_fused_moe_test native_dense_parity "
    "native_expert_parity native_grouped_parity gdn_parity gr_parity gr_multi_parity qsa_parity qsa_prompt_attn_parity "
    "router_top10_parity shared_expert_parity verify_parity spec_verify_parity "
    "verify_parity verify_batch_parity sampler_parity gr_parity gr_multi_parity gr_upmix_parity elementwise_parity "
    "q8k_quant_parity native_dense_ple_key_test").split())))
CPU_PROGRAMS = ("cost_gate_test", "draft_cum_test", "spec_prob_test", "gated_proposal_test", "q8k_quant_parity",
                "gguf_geometry_test", "patch_guard_test")    # cmake/backends/cpu.cmake's, the header-only gguf test, the guards
DIRECT_CPU = (("patch_guard_test", "patch_guard_test", [str(GGUF), str(MTP)]),)          # (name, program, args)
DIRECT_GPU = (("qsa_prompt_attn_parity", "qsa_prompt_attn_parity", []),
              ("prefill_fused_iq_test_edge", "prefill_fused_iq_test", ["--edge", "--no-timing"]))
UNREGISTERED = ("patch_guard_test", "qsa_prompt_attn_parity")
NODE_DIR = Path("/home/USER/.unsloth/node/bin")
NODE_SKIP = "node is not installed"
KNOWN_SERVE_FAILS = {"test_hip_ordinal"}
FETCH_KEYS = ("STRATA_ADAPT_FETCH", "STRATA_ADAPT_FETCH_VERIFY", "STRATA_ADAPT_CHECKRES", "STRATA_ADAPT_FETCH_MIN",
              "STRATA_ADAPT_FETCH_MARGIN", "STRATA_DEBUG")
STANDARD = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}
FIELDS = dict(STANDARD, presence_penalty=0.0, frequency_penalty=0.0, repetition_penalty=1.0)
C2_PLAN = (("think", "normal", "W1-think", True, 1536), ("code", "normal", "W2-code", False, 512),
           ("conv", "calib", "C-conv", False, 512), ("prose", "calib", "C-prose", False, 512))
SEEDS_C2 = (7100001, 7100002)
C2_ARMS = ("B1", "B2", "P")
C4_PROMPTS = (
    ("python", "Use the web_search tool to find the current stable release of the Python programming language as listed "
               "on python.org. Then open the most relevant python.org page with the fetch_page tool and answer in two "
               "sentences, citing the URL of the page you opened."),
    ("btree", "Use the web_search tool to find the Wikipedia article on the B-tree data structure. Open the article with "
              "the fetch_page tool and say who invented B-trees and in which year, citing the URL of the page you opened."),
    ("searxng", "Use the web_search tool to find the SearXNG documentation page about its search API. Open that page "
                "with the fetch_page tool and explain in three sentences what the format parameter does, citing the URL "
                "of the page you opened."))
SEEDS_C4 = (7200001, 7200002, 7200003)
C4_MAX_TOKENS = 1024
C4_TIMEOUT_S = 300
PAID_TOOLS = Path("/home/USER/ai/deep-research/tools")   # exa_fallback.py / tavily_fallback.py: their own counter code
PAID_KEEP = 0.25          # Karl's rule: 25 % of each provider's month kept for Jan chat
PAID_MIN_CALLS = 10       # ... and C4 starts only with 25 % + 10 calls' worth left
PAID_STOP = 10            # C4 stops at 10 paid calls in total (both arms): the soft stop; the hard one is paid_budget's
PAID_ARM_STOP = 5         # (review M6) 5 per arm; the test servers' PAID_SEARCH_RUN_CAP: B 5, P 10 (one run id)
PAID_CAP = {"B": 5, "P": 10}
FIXTURES = (("conv", 1200), ("struct", 8192), ("prose", 1200))     # Basalt's decode fixtures (bp90_client.py DECODE)
SEED_FX = 7300001
LOST_LINE = "a request ended without an answer and without a finish reason"
FATAL_RE = re.compile(r"fatal GPU error|no progress for [0-9]+ s during a request|the engine had stopped \(exit code|became non-finite")
FETCH_ON2 = re.compile(r"^strata serve: STRATA_ADAPT_FETCH=2: the PCIe share takes", re.M)
FETCH_OFF = re.compile(r"^strata serve: STRATA_ADAPT_FETCH is off", re.M)
RAW = "[strata] raw ids: "
WRAP_RE = re.compile(r"^\[strata\] thinking budget reached \((\d+) tokens\)", re.M)
LIMIT_RE = re.compile(r"^\[strata\] thinking limited to (\d+) of max_tokens (\d+)", re.M)
URL_RE = re.compile(r"https?://[^\s<>\"'`)\]}]+", re.I)
START_GATES = ("env", "fenv", "envsq", "line", "fatal", "foreign", "void")
PAID_MARKS = (("search_fallback", "imports the deep-research search fallback (Exa, then Tavily)"),
              ("_fallback(", "calls a search fallback after SearXNG"), ("api.exa.ai", "names Exa's API"),
              ("api.tavily.com", "names Tavily's API"), ("tavily", "names Tavily"), ("exa_fallback", "names Exa's fallback"))

_MOD = {}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def sqm():
    """sq.py of the sampled harness (build_config / resolve_arm / diff_keys / Renderer): read-only, loaded once"""
    if "sq" not in _MOD:
        if str(SQD) not in sys.path:
            sys.path.insert(0, str(SQD))
        _MOD["sq"] = load("sq", SQD / "sq.py")
    return _MOD["sq"]


def rum():
    """port0211_rules.py (PINS, SERVER_PINS; it imports g17_rules): read-only, loaded once"""
    if "ru" not in _MOD:
        _MOD["ru"] = load("port0211_rules", RU)
    return _MOD["ru"]


def g17m():
    return rum().g17


def shm():
    if "sh" not in _MOD:
        _MOD["sh"] = load("shape_rules_sw", SHAPE)
    return _MOD["sh"]


def port_pins():
    p = dict(rum().PINS)
    p["STRATA_ARENA_FILE_CACHE"] = "0"
    return p


def server_pins():
    return tuple(rum().SERVER_PINS)


def sha256_file(p, n=None):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()[:n] if n else h.hexdigest()


def gate(a, status, detail):
    if getattr(a, "gates", None) and getattr(a, "gate", None):
        with open(a.gates, "a") as f:
            f.write(f"{a.gate} {status} {detail}\n")


def read_gates(p):
    g = {}
    for line in Path(p).read_text(errors="replace").splitlines() if Path(p).exists() else []:
        k, _, rest = line.partition(" ")
        s, _, det = rest.partition(" ")
        if k:
            g[k] = (s, det)       # the last line of a gate counts
    return g


def gs(g, k):
    return g.get(k, ("", ""))[0]


def read_jsonl(p):
    out = []
    if Path(p).exists():
        for line in Path(p).read_text(errors="replace").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def forms_bad():
    return [f"{k}={globals()[k]!r} (want one of {v})" for k, v in FORMS.items() if globals()[k] not in v]


def rules_text():
    shas = "\n".join(f"  {p.relative_to(WS)} {sha256_file(p, 16) if p.exists() else 'MISSING'}" for p in RULE_FILES)
    sw = "\n".join(f"  {k} = {globals()[k]}" for k in FORMS)
    return (__doc__.strip() + "\n\nTHE SWITCHES AT THE FREEZE:\n" + sw
            + "\n\nThis file and the files it imports, the gap runs or the harness reads (sha256, first 16 hex, at the "
              "freeze; this file's own sha covers its code, not only this text):\n" + shas + "\n")


def cmd_forms(a):
    for k in FORMS:
        print(f"{k}={globals()[k]}")
    bad = forms_bad()
    if bad:
        print("FORMS BAD: " + "; ".join(bad))
    return 1 if bad else 0


def cmd_rules(a):
    t = rules_text()
    Path(a.out).write_text(t)
    print(f"rules frozen: {a.out} sha {hashlib.sha256(t.encode()).hexdigest()[:12]}")
    return 0


# ================================================================================================ the arm configs
def test_form(path):
    """a config without the picture reader / fallback / guard key, exactly as the sampled harness strips it"""
    return sqm().build_config({"base": str(path), "strip": True, "top": {}, "env": {}, "args_set": {}, "args_drop_value": []})


def arm_config(name, log_dir=None):
    base, dbg = name.split("-")[0], name.endswith("-dbg")
    c = test_form(CFG_B if base == "B" else CFG_P)
    if dbg:
        c["env"] = dict(c["env"], STRATA_DEBUG="1")
    c["log"] = str(Path(log_dir or WS / "logs") / f"engine-r23sw-{name}.log")
    c["_comment"] = (f"r23 v0.2.13 switch gap (work/r23/switch-gap/switch_rules.py arms): arm {name} = "
                     f"{'configs/P028x.json' if base == 'B' else 'configs/P0213x-af2.json'} without the picture reader"
                     f"{' + STRATA_DEBUG=1 (server-side raw ids)' if dbg else ''}. Measurement only, never served.")
    return c


ARMS = ("B", "P", "B-dbg", "P-dbg")


def cmd_arms(a):
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    man = {}
    for n in ARMS:
        c = arm_config(n, a.log_dir)
        (out / f"{n}.json").write_text(json.dumps(c, indent=1) + "\n")
        man[n] = {"exe": c["exe"], "server": c["server"], "log_dir": str(Path(c["log"]).parent),
                  "base": str(CFG_B if n.startswith("B") else CFG_P),
                  "base_sha256": sha256_file(CFG_B if n.startswith("B") else CFG_P)}
    man["_shas"] = {"P028x.json": sha256_file(CFG_B), "P0213x-af2.json": sha256_file(CFG_P),
                    "P0213x.json": sha256_file(CFG_P0), "x28h.json": sha256_file(X28H)}
    (out / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    print(f"arm configs in {out}: {', '.join(ARMS)}")
    return cmd_cfgcheck(a)


def cfg_problems(cfgs, man, no_sha=False):
    """[problem] of the arm configs (see the docstring's THE ARMS)"""
    sq = sqm()
    bad = []
    for n in ARMS:
        if n not in cfgs:
            bad.append(f"{n}: config missing")
    if bad:
        return bad
    for n in ARMS:
        w = arm_config(n, man.get(n, {}).get("log_dir"))
        dd = sorted(k for k in set(cfgs[n]) | set(w) if k != "_comment" and cfgs[n].get(k) != w.get(k))
        if dd:
            bad.append(f"{n}: differs from its source config's test form in {dd}")
    for name, f in (("P028x.json", CFG_B), ("P0213x-af2.json", CFG_P), ("P0213x.json", CFG_P0), ("x28h.json", X28H)):
        if sha256_file(f) != man.get("_shas", {}).get(name):
            bad.append(f"configs/{name} changed since the configs were written")
    b, p = cfgs["B"], cfgs["P"]
    want_b = json.loads(X28H.read_text())
    want_b["exe"] = str(EXE_B)
    want_b["env"] = dict(want_b.get("env", {}), STRATA_HC_UPMIX="1", STRATA_ADAPT_FETCH="2")
    d = sq.diff_keys(b, want_b)
    if d:
        bad.append(f"B is not x28h.json + exe engine-r23afetch + STRATA_HC_UPMIX=1 + STRATA_ADAPT_FETCH=2 (differs in {d})")
    p0 = test_form(CFG_P0)
    p0["env"] = dict(p0["env"], STRATA_ADAPT_FETCH="2")
    d = sq.diff_keys(p, p0)
    if d:
        bad.append(f"P is not P0213x.json's test form + STRATA_ADAPT_FETCH=2 (differs in {d})")
    top = {"exe", "server", "log", "_comment", "drafting", "user_args"}
    dtop = sorted(k for k in set(b) | set(p) if k not in top and k != "env" and b.get(k) != p.get(k))
    if dtop:
        bad.append(f"P and B differ beyond the paths, the logs and the port's keys in {dtop}")
    if p.get("drafting") != "mtp" or p.get("user_args") != ["--kv-resident", "32768"] or "drafting" in b or "user_args" in b:
        bad.append("the port's keys (drafting mtp, user_args --kv-resident 32768) are not P's alone")
    pins = port_pins()
    extra = {k: v for k, v in p["env"].items() if k not in b["env"]}
    if extra != pins:
        bad.append(f"P's env beyond B's is not the port's pins: extra {sorted(set(extra) - set(pins))}, missing "
                   f"{sorted(set(pins) - set(extra))}, values {sorted(k for k in extra if k in pins and extra[k] != pins[k])}")
    lost = sorted(k for k in b["env"] if p["env"].get(k) != b["env"][k])
    if lost:
        bad.append(f"P does not carry B's env value for {lost}")
    for n in ARMS:
        c = cfgs[n]
        arm = n.split("-")[0]
        if c.get("exe") != str(EXE[arm]):
            bad.append(f"{n}: exe {c.get('exe')}")
        if c.get("server") != str(SRV[arm]):
            bad.append(f"{n}: server {c.get('server')}")
        if c.get("sampling") != STANDARD:
            bad.append(f"{n}: sampling {c.get('sampling')}")
        if "--vision" in c.get("args", []) or any(k in c for k in ("vision", "fallback", "model_not_running")):
            bad.append(f"{n}: not the test form (the picture reader / fallback / guard key)")
        if c["env"].get("STRATA_HC_UPMIX") != "1" or c["env"].get("STRATA_ADAPT_FETCH") != "2":
            bad.append(f"{n}: STRATA_HC_UPMIX / STRATA_ADAPT_FETCH not 1 / 2")
        want_dbg = {"STRATA_DEBUG": "1"} if n.endswith("-dbg") else {}
        ev = {k: v for k, v in c["env"].items() if k in FETCH_KEYS and k != "STRATA_ADAPT_FETCH"}
        if ev != want_dbg:
            bad.append(f"{n}: harness / fetch keys {ev} (want {want_dbg})")
        if "--expert-cache-device1" not in c.get("args", []) or len([x for x in c["env"].get("CUDA_VISIBLE_DEVICES", "").split(",") if x]) != 2:
            bad.append(f"{n}: not the two-GPU helper form")
        if Path(c.get("log", "")).name in ("engine-P028x.log", "engine-P0213x.log", "engine-P0213x-af2.log"):
            bad.append(f"{n}: the log is a served / shared config's log")
    if not no_sha:
        for arm in ("B", "P"):
            if not EXE[arm].is_file():
                bad.append(f"{EXE[arm]} missing")
            elif sha256_file(EXE[arm], 12) != SHA[arm]:
                bad.append(f"{EXE[arm]} sha256 {sha256_file(EXE[arm], 12)} is not {SHA[arm]}")
            else:
                data = EXE[arm].read_bytes()
                miss = [s for s in (b"STRATA_ADAPT_FETCH\0", b"STRATA_ADAPT_FETCH_VERIFY\0", b"STRATA_HC_UPMIX\0") if s not in data]
                if miss:
                    bad.append(f"{EXE[arm]} has no {miss}")
                if b"STRATA_DEBUG" in data:
                    bad.append(f"{EXE[arm]} reads STRATA_DEBUG (the harness switch must stay server-only)")
    return bad


def sampled_problems(cfgs, spec_path, sqo=None):
    """the sampled arms = the gap's debug arms: R1 = R2 = B-dbg, X = P-dbg, VF = X + VERIFY + CHECKRES (sq.py's own build of
    the spec, or its derived cfg/ files when SQO is given)"""
    sq = sqm()
    bad = []
    spec = json.loads(Path(spec_path).read_text())
    want = {"R1": ("B-dbg", {}), "R2": ("B-dbg", {}), "X": ("P-dbg", {}),
            "VF": ("P-dbg", {"STRATA_ADAPT_FETCH_VERIFY": "1", "STRATA_ADAPT_CHECKRES": "1"})}
    for r, (n, add) in want.items():
        try:
            if sqo:
                sc = json.loads((Path(sqo) / "cfg" / f"{r}.json").read_text())
            else:
                sc = sq.build_config(sq.resolve_arm(spec, r))
                sc["env"] = dict(sc["env"], **sq.HARNESS_ENV)
        except (OSError, ValueError, KeyError) as e:
            bad.append(f"sampled arm {r}: {e}")
            continue
        w = copy.deepcopy(cfgs[n])
        w["env"] = dict(w["env"], **add)
        d = sq.diff_keys(sc, w)
        if d:
            bad.append(f"sampled {r} is not {n}{' + ' + str(add) if add else ''} (differs in {d})")
    return bad


def cmd_cfgcheck(a):
    out = Path(a.outdir)
    try:
        man = json.loads((out / "manifest.json").read_text())
    except (OSError, ValueError):
        man = {}
    cfgs = {}
    for n in ARMS:
        try:
            cfgs[n] = json.loads((out / f"{n}.json").read_text())
        except (OSError, ValueError):
            pass
    bad = cfg_problems(cfgs, man, getattr(a, "no_sha", False))
    if not bad:
        bad += sampled_problems(cfgs, getattr(a, "spec", None) or SPEC, getattr(a, "sampled", None))
    line = ("CONFIG CHECK OK: B = x28h + U + STRATA_ADAPT_FETCH=2 on engine-r23afetch (the daily's test form); P = P0213x's "
            "test form + STRATA_ADAPT_FETCH=2 on engine-r23p0213 = B + the port's pins and keys; the debug arms + STRATA_DEBUG=1 "
            "= the sampled R1 / R2 / X (VF = X + read-back)" + ("" if getattr(a, "no_sha", False) else
                                                                f"; engine shas {SHA['B']} / {SHA['P']}")
            if not bad else "CONFIG CHECK FAILED: " + "; ".join(sorted(set(bad))))
    print(line)
    gate(a, "FAIL" if bad else "PASS", line[:300])
    return 1 if bad else 0


# ================================================================================================ C1: the programs
TOK_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
ADD_RE = re.compile(r"^add_test\(\[=\[(.+?)\]=\]\s*(.*)\)\s*$")
PROP_RE = re.compile(r"^set_tests_properties\(\[=\[(.+?)\]=\]\s+PROPERTIES\s+(.*)\)\s*$")


def _unq(s):
    return re.sub(r"\\(.)", r"\1", s)


def ctest_entries(build):
    """the registered tests of BUILD's top-level CTestTestfile.cmake (read only; ctest itself is not run): name, argv,
    program (the binary a `cmake -E env` wrapper runs), env, timeout, skip code"""
    f = Path(build) / "CTestTestfile.cmake"
    tests, props = {}, {}
    for line in f.read_text(errors="replace").splitlines():
        m = ADD_RE.match(line.strip())
        if m:
            tests[m.group(1)] = [_unq(x) for x in TOK_RE.findall(m.group(2))]
            continue
        m = PROP_RE.match(line.strip())
        if m:
            toks = [_unq(x) for x in TOK_RE.findall(m.group(2))]
            keys = re.findall(r"(?:^|\s)([A-Z_]+)\s+\"", m.group(2))
            props[m.group(1)] = dict(zip(keys, toks))
    out = []
    for name, argv in tests.items():
        prog = argv[0] if argv else ""
        env = [x for x in (props.get(name, {}).get("ENVIRONMENT") or "").split(";") if x]
        if prog.endswith("/cmake") and argv[1:3] == ["-E", "env"]:
            rest = argv[3:]
            while rest and ("=" in rest[0].split("/")[0] or rest[0].startswith("--unset")):
                env.append(rest.pop(0))
            prog = rest[0] if rest else ""
        out.append({"name": name, "argv": argv, "program": prog, "base": os.path.basename(prog), "env": env,
                    "timeout": props.get(name, {}).get("TIMEOUT"), "skip_rc": props.get(name, {}).get("SKIP_RETURN_CODE")})
    return out


def select_entries(build, targets=SWITCH_TARGETS):
    """(cpu, gpu, problems): the entries whose program is one of TARGETS inside BUILD and exists; split by CPU_PROGRAMS"""
    build = os.path.realpath(build)
    ents = ctest_entries(build)
    sel = [e for e in ents if e["base"] in targets and os.path.dirname(os.path.realpath(e["program"]) if e["program"] else "") == build]
    bad = [f"{e['name']}: {e['program']} missing" for e in sel if not os.path.isfile(e["program"])]
    per = {}
    for e in sel:
        per[e["base"]] = per.get(e["base"], 0) + 1
    missing = [t for t in targets if t not in per and t not in UNREGISTERED]
    if missing:
        bad.append(f"no registered entry for {', '.join(missing)}")
    for t in targets:
        if not os.path.isfile(os.path.join(build, t)):
            bad.append(f"{t} not built in {build}")
    if len({e["name"] for e in sel}) != len(sel):
        bad.append("duplicate test names")
    cpu = [e for e in sel if e["base"] in CPU_PROGRAMS]
    gpu = [e for e in sel if e["base"] not in CPU_PROGRAMS]
    return cpu, gpu, bad, per


def cmd_ctestlist(a):
    cpu, gpu, bad, per = select_entries(a.build)
    for f, es in ((a.out_cpu, cpu), (a.out_gpu, gpu)):
        if f:
            Path(f).write_text("".join(e["name"] + "\n" for e in es))
    if a.json_out:
        Path(a.json_out).write_text(json.dumps({"cpu": cpu, "gpu": gpu, "per_program": per}, indent=1) + "\n")
    line = (f"ctestlist {a.build}: {len(cpu)} CPU + {len(gpu)} GPU registered entries of {len(per)} programs "
            f"({', '.join(f'{k} {v}' for k, v in sorted(per.items()))}); direct: "
            + ", ".join(n for n, _, _ in DIRECT_CPU + DIRECT_GPU) + (f"; PROBLEMS: {'; '.join(bad)}" if bad else ""))
    print(line)
    gate(a, "FAIL" if bad else "PASS", line[:300])
    return 1 if bad else 0


def cmd_parity(a):
    """shape_rules.py parity (junit + ctest log + direct.txt -> results.txt / counts.json), unchanged"""
    return shm().cmd_parity(a)


def parity_status(d):
    """(PASS / FAIL / NOT DECIDED, text) of one parity folder's counts.json"""
    p = Path(d) / "counts.json"
    if not p.exists():
        return "NOT DECIDED", f"{Path(d).name}: not run (no counts.json)"
    c = json.loads(p.read_text())
    real_fail = c["fail"] - c.get("notrun", 0)
    txt = (f"{c.get('label', Path(d).name)}: {c['pass']} pass / {c['skip']} skip / {real_fail} fail"
           + (f" / {c['notrun']} not run" if c.get("notrun") else "") + f" of {c['total']}")
    if real_fail > 0:
        return "FAIL", txt + ": " + "; ".join(c.get("fails", [])[:4])
    if c.get("notrun") or c["total"] == 0 or c["pass"] == 0:
        return "NOT DECIDED", txt
    return "PASS", txt


def serve_status(path):
    """(status, text) of the server suite's -v output: failures only in KNOWN_SERVE_FAILS; no 'Ran' line = not decided"""
    t = Path(path).read_text(errors="replace") if Path(path).exists() else ""
    ran = re.search(r"^Ran (\d+) tests?", t, re.M)
    bad = sorted(set(re.findall(r"^(?:FAIL|ERROR): (\S+)", t, re.M)))
    unknown = [b for b in bad if b not in KNOWN_SERVE_FAILS]
    sk = len(re.findall(r"skipped '([^']*)'", t))
    txt = (f"{ran.group(1) if ran else '?'} tests, {len(bad)} failed or erred"
           + (f" (known: {', '.join(sorted(set(bad) & KNOWN_SERVE_FAILS))})" if set(bad) & KNOWN_SERVE_FAILS else "")
           + (f"; NEW: {', '.join(unknown)}" if unknown else "") + f"; {sk} skipped")
    if not ran:
        return "NOT DECIDED", "no 'Ran N tests' line (not run, cut or crashed): " + txt
    return ("FAIL" if unknown else "PASS"), txt


def node_status(serve_out, node_check):
    """(status, text): the node tests ran (no 'node is not installed' skip in the -v output, >= 1 node test module ran) and
    node --check app.js gave rc 0 (node_check: a file whose last line is 'rc N')"""
    t = Path(serve_out).read_text(errors="replace") if Path(serve_out).exists() else ""
    nc = Path(node_check).read_text(errors="replace").strip().splitlines() if Path(node_check).exists() else []
    rc = re.match(r"^rc (\d+)", nc[-1]) if nc else None
    skipped = len(re.findall(re.escape(f"skipped '{NODE_SKIP}'"), t))
    web = re.findall(r"^test_\w+ \((?:serve\.)?test_web_\w+\.[^)]*\) \.\.\. ?(.*)$", t, re.M)   # (a test's own output may
    ran_node = sum(1 for x in web if NODE_SKIP not in x and not x.startswith("skipped"))      # split its line: counted)
    txt = (f"node --check app.js rc {rc.group(1) if rc else '?'}; {ran_node} web / node test(s) ok, {skipped} skipped for "
           f"'{NODE_SKIP}'")
    if rc and rc.group(1) != "0":
        return "FAIL", txt
    if not rc or not re.search(r"^Ran \d+ tests?", t, re.M):
        return "NOT DECIDED", txt + " (not run)"
    if skipped or not ran_node:
        return "NOT DECIDED", txt + " (the node tests did not run)"
    return "PASS", txt


def cmd_pstatus(a):
    s, t = parity_status(a.dir)
    print(f"parity status: {t} -> {s}")
    gate(a, s.replace(" ", "-"), t[:300])
    return 0


def cmd_targets(a):
    print(" ".join(SWITCH_TARGETS))
    return 0


def cmd_servetests(a):
    s, t = serve_status(a.file)
    print(f"servetests: {t} -> {s}")
    gate(a, s.replace(" ", "-"), t[:300])
    return 0


def cmd_nodecheck(a):
    s, t = node_status(a.serve_out, a.node_check)
    print(f"node: {t} -> {s}")
    gate(a, s.replace(" ", "-"), t[:300])
    return 0


# ================================================================================================ C4: the web path
def web_path(trees, cfgs):
    """(local_only, lines): the strata_web path of each server tree (serve/websearch.py) and each config's web_search
    block reaches only a local SearXNG and no paid API"""
    lines, paid = [], False
    for t in trees:
        f = Path(t) / "serve" / "websearch.py"
        if not f.exists():
            lines.append(f"{t}: no serve/websearch.py")
            paid = True
            continue
        src = f.read_text(errors="replace")
        hits = [why for mark, why in PAID_MARKS if mark.lower() in src.lower()]
        if hits:
            paid = True
            lines.append(f"{f}: PAID PATH - {'; '.join(hits)}")
        else:
            lines.append(f"{f}: SearXNG only")
    for c in cfgs:
        cfg = json.loads(Path(c).read_text())
        ws = cfg.get("web_search") or {}
        host = re.sub(r"^https?://", "", str(ws.get("searxng", "http://127.0.0.1:8888"))).split("/")[0]
        if not ws:
            paid = True
            lines.append(f"{c}: no web_search block (the web search is off)")
        elif host.split(":")[0] not in ("127.0.0.1", "localhost"):
            paid = True
            lines.append(f"{c}: web_search.searxng {ws.get('searxng')} is not local")
        else:
            lines.append(f"{c}: web_search.searxng {ws.get('searxng')} (local)")
    return not paid, lines


def paid_state(tools=PAID_TOOLS):
    """{provider: {...}} read through the modules' own counter code (usage(), available(): the key file is only stat-ed by
    available(), never read here). Raises on an unreadable module."""
    tools = str(tools)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    out = {}
    for name, modname in (("exa", "exa_fallback"), ("tavily", "tavily_fallback")):
        m = load(f"{modname}_sw", Path(tools) / f"{modname}.py")
        u = m.usage()
        if name == "exa":
            cap, used, per = float(m.MONTH_CREDIT_USD), float(u.get("usd", 0.0)), float(m.PRICE_USD.get(m.SEARCH_TYPE, 0.015))
            calls, closed, unit = int(u.get("searches", 0)), bool(u.get("closed")), "USD"
        else:
            cap, used, per = float(m.MONTH_CREDITS), float(u.get("count", 0)), 1.0
            calls, closed, unit = int(u.get("count", 0)), False, "searches"
        left, need = cap - used, PAID_KEEP * cap + PAID_MIN_CALLS * per
        out[name] = {"available": bool(m.available()), "closed": closed, "month": u.get("month"), "unit": unit, "cap": cap,
                     "used": round(used, 6), "left": round(left, 6), "need": round(need, 6), "per_call": per, "calls": calls,
                     "stop_all": u.get("cap_usd", u.get("cap"))}
    return out


def budget_ok(st):
    """(ok, [line]): every provider that can be charged (available, its month not closed) has >= 25 % of its cap + 10
    calls' worth left"""
    ok, lines = True, []
    for name, x in st.items():
        if not x["available"] or x["closed"]:
            lines.append(f"{name}: not chargeable ({'no key file' if not x['available'] else 'its month is closed'}) - "
                         f"{x['calls']} call(s) this month")
            continue
        good = x["left"] >= x["need"]
        ok &= good
        lines.append(f"{name}: {x['used']:g} of {x['cap']:g} {x['unit']} used this month ({x['calls']} calls), {x['left']:g} left, "
                     f"{'>=' if good else '<'} 25 % + {PAID_MIN_CALLS} calls = {x['need']:g}")
    return ok, lines


def paid_calls(st):
    return sum(x["calls"] for x in st.values())


def cmd_paidcheck(a):
    try:
        st = paid_state(a.tools)
    except Exception as e:  # noqa: BLE001 - the budget cannot be checked: no paid use
        line = f"C4 NOT RUN: paid budget - the counters could not be read ({type(e).__name__}: {str(e)[:120]})"
        print(line)
        gate(a, "REFUSED", line[:300])
        return 10
    ok, lines = budget_ok(st)
    if a.out:
        Path(a.out).write_text(json.dumps(st, indent=1) + "\n")
    line = (f"PAID BUDGET OK: {'; '.join(lines)}" if ok else f"C4 NOT RUN: paid budget - {'; '.join(lines)}")
    print(line)
    gate(a, "PASS" if ok else "REFUSED", line[:300])
    return 0 if ok else 10


def cmd_webpath(a):
    ok, lines = web_path(a.trees, a.configs or [])
    for x in lines:
        print(f"  {x}")
    if ok:
        line, st_ = "WEB PATH LOCAL ONLY: the strata_web path reaches only the local SearXNG", "PASS"
    elif any("not local" in x or ": no " in x for x in lines):
        line, st_ = "WEB PATH NOT USABLE: " + "; ".join(x for x in lines if "not local" in x or ": no " in x)[:300], "REFUSED"
    else:   # (coordinator 11-10) a paid path runs C4 bounded when the budget check passes
        try:
            bok, blines = budget_ok(paid_state(a.tools))
        except Exception as e:  # noqa: BLE001
            bok, blines = False, [f"the counters could not be read ({type(e).__name__}: {str(e)[:120]})"]
        if bok:
            line, st_ = (f"WEB PATH CAN REACH A PAID API, WITHIN THE BUDGET: C4 runs bounded ({PAID_STOP} paid calls at most, "
                         f"PAID_SEARCH_KIND=test) - {'; '.join(blines)}"), "PAID"
        else:
            line, st_ = f"C4 NOT RUN: paid budget - {'; '.join(blines)}", "REFUSED"
    print(line)
    gate(a, st_, line[:400])
    return 10 if st_ == "REFUSED" else 0


# ================================================================================================ the prompts rendered
def cmd_render(a):
    """the sampled plan's prompts rendered by B's and P's own server trees (sq.py's Renderer, thinking off): the same ids,
    else the sampled test cannot decide (sq.py ids would void X)"""
    sq = sqm()
    spec = json.loads(Path(a.spec).read_text())
    prompts, bad = sq.resolve_prompts(spec)
    if bad:
        print("RENDER FAILED: " + "; ".join(bad))
        return 1
    ids = {}
    for r in ("R1", "X"):
        R = sq.Renderer(sq.build_config(sq.resolve_arm(spec, r)))
        ids[r] = {q: R(m) for q, m in prompts.items()}
    diff = [q for q in prompts if ids["R1"][q] != ids["X"][q]]
    lens = {q: len(v) for q, v in ids["R1"].items()}
    line = (f"RENDER {'OK' if not diff else 'FAILED'}: the plan's prompts through B's ({TREE['B'].name}) and P's "
            f"({TREE['P'].name}) server code: {lens}" + (f"; DIFFER: {diff}" if diff else "; identical ids"))
    print(line)
    gate(a, "FAIL" if diff else "PASS", line[:300])
    return 1 if diff else 0


# ================================================================================================ evidence per start
def proc_env(pid):
    d = Path("/proc") / str(pid)
    env = dict(x.split("=", 1) for x in (d / "environ").read_bytes().decode("utf-8", "replace").split("\0") if "=" in x)
    argv = [x for x in (d / "cmdline").read_bytes().decode("utf-8", "replace").split("\0") if x != ""]
    ppid = int((d / "stat").read_text().rsplit(")", 1)[1].split()[1])
    return env, argv, ppid


def armenv_problems(procs, cfg_path, cfg, arm):
    """procs: [(pid, env, sha12, parent_argv, parent_env)]"""
    bad = []
    if len(procs) != 1:
        bad.append(f"{len(procs)} running engine(s) of {cfg['exe']} (want exactly 1: this arm's)")
    want = {k: v for k, v in cfg.get("env", {}).items() if k in FETCH_KEYS}
    for pid, env, sha12, pargv, penv in procs:
        if sha12 != SHA[arm]:
            bad.append(f"pid {pid}: binary sha256 {sha12} is not {SHA[arm]}")
        for where, e in (("engine", env), ("server", penv)):
            bad += [f"{where} {k}={e.get(k, 'unset')} (want {v})" for k, v in want.items() if e.get(k) != v]
            bad += [f"{where} {k}={e[k]} set behind the config" for k in FETCH_KEYS if k not in want and k in e]
        sp = [k for k in server_pins() if k in cfg.get("env", {})]
        bad += [f"server {k}={penv.get(k, 'unset')} (want {cfg['env'][k]})" for k in sp if penv.get(k) != cfg["env"][k]]
        if cfg.get("server") not in pargv:
            bad.append(f"pid {pid}: its parent is not {cfg.get('server')}")
        if "--config" not in pargv or pargv[pargv.index("--config") + 1:pargv.index("--config") + 2] != [str(cfg_path)]:
            bad.append(f"pid {pid}: its parent's --config is not {cfg_path}")
    return bad


def cmd_armenv(a):
    cfg_path = os.path.abspath(a.config)
    cfg = json.loads(Path(cfg_path).read_text())
    exe = os.path.realpath(a.exe)
    procs = []
    if a.mock_env:
        for p in json.loads(Path(a.mock_env).read_text())["procs"]:
            procs.append((p.get("pid", "mock"), p.get("env", {}), p.get("sha12"), p.get("parent_argv", []), p.get("parent_env", {})))
    else:
        for d in Path("/proc").iterdir():
            if not d.name.isdigit():
                continue
            try:
                if os.readlink(d / "exe") != exe:
                    continue
                env, argv, ppid = proc_env(d.name)
                penv, pargv, _ = proc_env(ppid)
                procs.append((d.name, env, sha256_file(d / "exe", 12), pargv, penv))
            except (OSError, ValueError, IndexError):
                continue
    bad = armenv_problems(procs, cfg_path, cfg, a.arm)
    for pid, env, sha12, pargv, penv in procs:
        print(f"engine pid {pid}: binary {sha12}, fetch keys {({k: env[k] for k in FETCH_KEYS if k in env}) or 'none'}; "
              f"its server: {len(pargv)} args, fetch keys {({k: penv[k] for k in FETCH_KEYS if k in penv}) or 'none'}")
    line = (f"ARM ENV OK ({a.arm}): 1 engine, binary {SHA[a.arm]}, the fetch / debug keys as configured in the engine and "
            "its server, the parent server.py names the config" if not bad else
            f"ARM ENV FAILED ({a.arm}) - this start is not the arm: " + "; ".join(bad))
    print(line)
    gate(a, "PASS" if not bad else "FAIL", line[:300])
    return 0 if not bad else 1


def startline_ok(text):
    on, off = FETCH_ON2.findall(text), FETCH_OFF.findall(text)
    ok = bool(on) and not off
    return ok, (f"{len(on)} 'STRATA_ADAPT_FETCH=2' start line(s)" if ok else
                f"UNEXERCISED: {len(on)} '=2' start line(s), {len(off)} 'is off' line(s)")


def cmd_startline(a):
    t = Path(a.englog).read_text(errors="replace") if Path(a.englog).exists() else ""
    ok, why = startline_ok(t)
    line = f"{Path(a.englog).name}: {why}"
    print(f"{line} -> {'PASS' if ok else 'FAIL'}")
    gate(a, "PASS" if ok else "FAIL", line[:300])
    return 0


# ================================================================================================ the plans
def _workload(set_, id_):
    w = json.loads(WORKLOADS.read_text())
    hit = [x for x in w[set_] if x["id"] == id_]
    if len(hit) != 1:
        raise SystemExit(f"workloads.json [{set_}] {id_}: {len(hit)} entries")
    return hit[0]["messages"]


def c2_plan():
    reqs = []
    for name, set_, id_, think, mx in C2_PLAN:
        msgs = _workload(set_, id_)
        for i, seed in enumerate(SEEDS_C2):
            reqs.append({"name": f"{name}-s{i + 1}", "prompt": name, "workload": id_, "messages": msgs, "thinking": think,
                         "max_tokens": mx, "seed": seed})
    return {"plan": "C2", "fields": FIELDS, "requests": reqs}


def c4_plan():
    return {"plan": "C4", "fields": FIELDS, "max_tokens": C4_MAX_TOKENS, "timeout_s": C4_TIMEOUT_S,
            "requests": [{"name": n, "messages": [{"role": "user", "content": t}], "seed": s, "thinking": False,
                          "max_tokens": C4_MAX_TOKENS} for (n, t), s in zip(C4_PROMPTS, SEEDS_C4)]}


def cmd_c2plan(a):
    p = c2_plan()
    Path(a.out).write_text(json.dumps(p, indent=1) + "\n")
    print(f"C2 plan: {len(p['requests'])} requests -> {a.out} (sha {sha256_file(a.out, 12)})")
    return 0


def cmd_c4plan(a):
    p = c4_plan()
    Path(a.out).write_text(json.dumps(p, indent=1) + "\n")
    print(f"C4 plan: {len(p['requests'])} requests -> {a.out} (sha {sha256_file(a.out, 12)})")
    return 0


def cmd_fixtures(a):
    """C5's three chat fixtures (Basalt's decode fixtures, bp90_client.py's user_text) rendered back to user texts with P's
    tree (tokenizer from the GGUF, the tree's chat template) -> a plan for fixtures_client.py (CPU, before the gap)"""
    tree, data = Path(a.tree), Path(a.data)
    sys.path.insert(0, str(tree))
    sys.path.insert(0, str(tree / "tools"))
    from strata_tokenizer import Tokenizer          # noqa: E402
    from serve.frontend import ChatTemplate          # noqa: E402
    tok = Tokenizer.from_gguf(a.gguf)
    tpl = ChatTemplate(str(tree / "serve" / "chat_template.jinja"))
    mark = "⁣BODY⁣"
    pre, post = tpl.render([{"role": "user", "content": mark}], enable_thinking=False).split(mark)
    reqs = []
    for i, (name, mx) in enumerate(FIXTURES):
        ids = [int(x) for x in (data / f"{name}.ids").read_text().strip().split("\n")[0].split(",")]
        text = tok.decode(ids)
        if not (text.startswith(pre) and text.endswith(post)):
            raise SystemExit(f"{name}.ids is not our template around one user message")
        reqs.append({"name": name, "messages": [{"role": "user", "content": text[len(pre):len(text) - len(post)]}],
                     "max_tokens": mx, "thinking": False, "seed": SEED_FX + i, "expect_prompt_tokens": len(ids)})
    Path(a.out).write_text(json.dumps({"plan": "C5 fixtures", "fields": FIELDS, "requests": reqs}, indent=1) + "\n")
    print(f"fixtures plan: {', '.join(f'{r['name']} {r['expect_prompt_tokens']} ids' for r in reqs)} -> {a.out}")
    return 0


# ================================================================================================ C2
def arm_void(g, tag):
    return [f"{k}_{tag}" for k in START_GATES if gs(g, f"{k}_{tag}") == "FAIL"]


def c2_compare(d, g=None, noref_form=None):
    """{result, text, rows, flags} from C2DIR/{B1,B2,P}/c2.jsonl"""
    noref_form = noref_form or C2_NOREF_FORM
    d = Path(d)
    g = g or {}
    plan = json.loads((d / "plan.json").read_text()) if (d / "plan.json").exists() else c2_plan()
    names = [r["name"] for r in plan["requests"]]
    recs = {arm: {r["name"]: r for r in read_jsonl(d / arm / "c2.jsonl")} for arm in C2_ARMS}
    voids = {arm: arm_void(g, f"c2{arm}") for arm in C2_ARMS}
    rows, flags = [], []

    def ids_of(arm, n):
        r = recs[arm].get(n)
        if not r or r.get("error") or r.get("ids") is None or r.get("finish") not in ("stop", "length"):
            return None
        return (r.get("prompt_tokens"), tuple(r["ids"]))
    nrep = ndiff = nmiss = 0
    for n in names:
        b1, b2, p = ids_of("B1", n), ids_of("B2", n), ids_of("P", n)
        row = {"name": n, "have": [x is not None for x in (b1, b2, p)]}
        if b1 is None or b2 is None or p is None:
            row["status"] = "MISSING"
            nmiss += 1
        elif b1 != b2:
            row["status"] = "B NOT REPRODUCIBLE (info)"
            row["p_vs_b1"] = "same" if p == b1 else ("same as B2" if p == b2 else "differs")
        else:
            nrep += 1
            if p == b1:
                row["status"] = "EXACT"
            else:
                ndiff += 1
                row["status"] = "DIFFERS"
                pr = ("prompt length " + f"{p[0]} vs {b1[0]}") if p[0] != b1[0] else ""
                k = next((i for i, (x, y) in enumerate(zip(p[1], b1[1])) if x != y), min(len(p[1]), len(b1[1])))
                row["first_diff"] = k
                row["why"] = pr or f"ids differ from position {k} ({len(p[1])} vs {len(b1[1])} ids)"
        for arm in C2_ARMS:
            r = recs[arm].get(n) or {}
            row[f"cont_{arm}"] = r.get("continuation")
        rows.append(row)
    bad_arms = [f"{arm} ({', '.join(v)})" for arm, v in voids.items() if v]
    if bad_arms:
        flags.append("start gates failed: " + "; ".join(bad_arms))
    if ndiff and not bad_arms:
        res = "DIFFERS"
    elif bad_arms or nmiss:
        res = "NOT DECIDED"
    elif nrep == 0:
        res = "DIFFERS" if noref_form == "differs" else "NOT DECIDED"
        flags.append(f"no request was B-reproducible (B1 = B2 on 0 of {len(names)}): C2_NOREF_FORM {noref_form} -> {res}")
    else:
        res = "EXACT"
    think = [r for r in rows if r["name"].startswith("think")]
    cont = {arm: sum(1 for r in think if r.get(f"cont_{arm}")) for arm in C2_ARMS}
    if think and any(cont[a_] == 0 for a_ in C2_ARMS if any(r["have"][C2_ARMS.index(a_)] for r in think)):
        flags.append(f"the answer_room continuation was not seen on every arm's think requests ({cont})")
    txt = (f"{res}: {nrep} of {len(names)} requests B-reproducible, {ndiff} of them differ on P"
           + (f", {nmiss} missing" if nmiss else "") + f"; B not reproducible on "
           f"{sum(1 for r in rows if r['status'].startswith('B NOT'))}; the think continuation seen B1 / B2 / P "
           f"{cont['B1']} / {cont['B2']} / {cont['P']} of {len(think)}")
    return {"result": res, "text": txt, "rows": rows, "flags": flags, "reproducible": nrep, "differ": ndiff, "missing": nmiss}


def cmd_c2compare(a):
    g = read_gates(a.gates_file) if a.gates_file else {}
    r = c2_compare(a.c2dir, g)
    Path(a.c2dir, "compare.json").write_text(json.dumps(r, indent=1) + "\n")
    lines = [f"C2 {r['text']}"] + [f"  {x['name']}: {x['status']}" + (f" ({x['why']})" if x.get("why") else "")
                                    + (f" (P {x['p_vs_b1']})" if x.get("p_vs_b1") else "") for x in r["rows"]]
    lines += [f"  FLAG {f}" for f in r["flags"]]
    Path(a.c2dir, "compare.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    gate(a, r["result"].replace(" ", "-"), r["text"][:300])
    return 0


# ================================================================================================ C4
def norm_url(u):
    u = u.strip().rstrip(".,;:")
    m = re.match(r"^(?:https?://)?([^/?#]+)([^?#]*)(\?[^#]*)?", u, re.I)
    if not m:
        return u.lower()
    host = m.group(1).lower()
    host = host[4:] if host.startswith("www.") else host
    path = m.group(2).rstrip("/") or ""
    return host + path + (m.group(3) or "")


def c4_record_ok(r, form=None):
    """(ok, [why]) of one P request under the C4 rule"""
    form = form or CITE_FORM
    why = []
    if not r.get("completed"):
        why.append(f"not completed ({r.get('finish')}, {r.get('error') or 'no error text'})")
    if (r.get("search_calls") or 0) < 1:
        why.append("no search round")
    cited = r.get("cited_fetched") if form == "fetch-page" else r.get("cited_tool")
    if not cited:
        why.append(f"no cited source ({form})")
    if r.get("errors"):
        why.append("errors: " + "; ".join(r["errors"])[:160])
    return not why, why


def c4_judge(d, g=None, form=None):
    d = Path(d)
    g = g or {}
    paid = paid_summary(d)
    for k in ("webpath", "c4budget"):
        if gs(g, k) == "REFUSED":
            return {"result": "NOT RUN", "text": ("refused before the gap: " if k == "webpath" else "refused right before C4: ")
                    + g[k][1][:240], "rows": [], "paid": paid}
    pe = [f"{k}: {g[k][1][:160]}" for k in ("penv_webB", "penv_webP") if gs(g, k) == "FAIL"]
    if pe:   # (review S1) the hard cap was not in a test server's environment: nothing was sent on that arm
        return {"result": "NOT RUN", "text": "C4 NOT RUN (env): " + "; ".join(pe), "rows": [], "paid": paid}
    plan = json.loads((d / "plan.json").read_text()) if (d / "plan.json").exists() else c4_plan()
    names = [r["name"] for r in plan["requests"]]
    recs = {arm: {r["name"]: r for r in read_jsonl(d / arm / "web.jsonl")} for arm in ("B", "P")}
    if not recs["B"] and not recs["P"]:
        return {"result": "NOT RUN", "text": g.get("skip_c4", ("", "the web-search part did not run"))[1][:240] or
                "the web-search part did not run", "rows": [], "paid": paid}
    voids = {arm: arm_void(g, f"web{arm}") for arm in ("B", "P")}
    pfatal = gs(g, "fatal_webP") == "FAIL"     # (review S2) a fatal line on P's start is a C4 FAIL, not a void
    voids["P"] = [v for v in voids["P"] if v != "fatal_webP"]
    ran = {arm: sum(1 for r in recs[arm].values() if not r.get("not_run")) for arm in ("B", "P")}
    rows, fails, nd = [], [], []
    for n in names:
        b, p = recs["B"].get(n), recs["P"].get(n)
        row = {"name": n, "B": None if b is None else {k: b.get(k) for k in ("completed", "search_calls", "fetch_ok", "cited_fetched", "cited_tool", "errors", "paid_calls", "not_run")},
               "P": None if p is None else {k: p.get(k) for k in ("completed", "search_calls", "fetch_ok", "cited_fetched", "cited_tool", "errors", "paid_calls", "not_run")}}
        if (b or {}).get("not_run") or (p or {}).get("not_run"):
            row["status"] = "NOT RUN (" + ((b or {}).get("why") or (p or {}).get("why") or "the paid-call stop") + ")"
        elif b is None or p is None:
            row["status"] = "MISSING"
            nd.append(f"{n}: missing on {'B' if b is None else 'P'}")
        elif not b.get("completed"):
            row["status"] = "NOT JUDGED (did not complete on B)"
        else:
            ok, why = c4_record_ok(p, form)
            row["status"] = "PASS" if ok else "FAIL"
            if not ok:
                row["why"] = why
                fails.append(f"{n}: {'; '.join(why)}")
        rows.append(row)
    judged = [r for r in rows if r["status"] in ("PASS", "FAIL")]
    bad = [f"{a_} ({', '.join(v)})" for a_, v in voids.items() if v]
    few = [f"{a_} {ran[a_]}" for a_ in ("B", "P") if ran[a_] < 2]
    if voids["B"]:
        res = "NOT DECIDED"
        nd.append("start gates failed: " + "; ".join(bad))
    elif pfatal:
        res = "FAIL"
        fails.insert(0, f"P's C4 start: {g['fatal_webP'][1][:160]}")
    elif bad:
        res = "NOT DECIDED"
        nd.append("start gates failed: " + "; ".join(bad))
    elif few:
        res = "NOT DECIDED"
        nd.append(f"fewer than 2 requests ran on an arm ({', '.join(few)} of {len(names)}; the paid-call stop or the deadline)")
    elif fails:
        res = "FAIL"
    elif nd or not judged:
        res = "NOT DECIDED"
        if not judged:
            nd.append("no request completed on B")
    else:
        res = "PASS"
    txt = (f"{res}: {len(judged)} of {len(names)} requests completed on B and judged on P, "
           f"{sum(1 for r in judged if r['status'] == 'PASS')} pass (CITE_FORM {form or CITE_FORM}); ran B {ran['B']} / P {ran['P']}"
           + (f"; FAIL: {' | '.join(fails)}" if fails else "") + (f"; {' | '.join(nd)}" if nd else "") + f"; {paid['text']}")
    return {"result": res, "text": txt, "rows": rows, "paid": paid}


def paid_summary(d):
    """the paid calls of C4: per arm (the clients' per-request deltas) and the counters before / after (paidcheck)"""
    d = Path(d)
    per = {arm: sum(int(r.get("paid_calls") or 0) for r in read_jsonl(d / arm / "web.jsonl")) for arm in ("B", "P")}
    out = {"B": per["B"], "P": per["P"], "total": per["B"] + per["P"], "stop": PAID_STOP}
    try:
        s0, s1 = (json.loads((d / f).read_text()) for f in ("paid-start.json", "paid-end.json"))
        out["counters"] = {k: s1[k]["calls"] - s0[k]["calls"] for k in s0 if k in s1}
    except (OSError, ValueError, KeyError):
        out["counters"] = None
    out["text"] = (f"paid searches during C4: {out['total']} (B {per['B']}, P {per['P']}; the stop at {PAID_STOP})"
                   + (f"; the counters moved {', '.join(f'{k} +{v}' for k, v in out['counters'].items())} (Jan chat's own "
                      "calls in that time included)" if out["counters"] is not None else ""))
    return out


def cmd_c4judge(a):
    g = read_gates(a.gates_file) if a.gates_file else {}
    r = c4_judge(a.c4dir, g)
    Path(a.c4dir).mkdir(parents=True, exist_ok=True)
    Path(a.c4dir, "judge.json").write_text(json.dumps(r, indent=1) + "\n")
    print(f"C4 {r['text']}")
    gate(a, r["result"].replace(" ", "-"), r["text"][:300])
    return 0


# ================================================================================================ C5
def lost_count(listfile):
    """from the driver's list (lines 'TAG ARM LABEL SERVERLOG [CLIENT_RECORDS]'): per P log the lost lines, the runs
    ('[strata] done:' lines), the client requests; each firing named"""
    out = {"logs": [], "firings": [], "lost": 0, "runs": 0, "requests": 0, "workload_lost": 0, "workload_requests": 0}
    for line in Path(listfile).read_text().splitlines() if Path(listfile).exists() else []:
        p = line.split()
        if len(p) < 4 or p[1] != "P":
            continue
        tag, log = p[0], p[3]
        nreq = int(p[4]) if len(p) > 4 and p[4].isdigit() else None
        try:
            lines = Path(log).read_text(errors="replace").splitlines()
        except OSError:
            out["logs"].append({"tag": tag, "log": log, "missing": True})
            continue
        lost, runs, last = 0, 0, ""
        for i, x in enumerate(lines, 1):
            if x.startswith("[strata] done:"):
                runs += 1
            if x.startswith("[strata] req openai") or x.startswith("[strata] done:"):
                last = x[:160]
            if LOST_LINE in x:
                lost += 1
                out["firings"].append(f"{tag}: {Path(log).name} line {i} (after: {last or 'the start'})")
        out["logs"].append({"tag": tag, "log": log, "lost": lost, "runs": runs, "requests": nreq})
        out["lost"] += lost
        out["runs"] += runs
        out["requests"] += nreq or 0
        if tag.startswith(("scr", "bp")):
            out["workload_lost"] += lost
            out["workload_requests"] += nreq or 0
    return out


def c5_text(c):
    lines = [f"C5 (information): the lost-answer guard fired {c['lost']} time(s) over {c['requests']} client requests "
             f"({c['runs']} server runs) in {len([x for x in c['logs'] if not x.get('missing')])} P server log(s); on our "
             f"workload (the screen + the fixtures) {c['workload_lost']} in {c['workload_requests']} requests"]
    for x in c["logs"]:
        lines.append(f"  {x['tag']}: " + ("server log missing" if x.get("missing") else
                                          f"{x['lost']} firing(s), {x['runs']} runs, {x['requests'] if x['requests'] is not None else '?'} requests ({Path(x['log']).name})"))
    lines += [f"  FIRING {f}" for f in c["firings"]]
    if c["workload_lost"]:
        lines.append(f"  RECOMMENDATION (for Karl): {c['workload_lost']} firing(s) in {c['workload_requests']} requests of our "
                     "workload - each restarts the engine (~1 min reload) and drops every parked conversation; a small "
                     "switch patch (the guard's engine restart behind a config key) is worth carrying into a switch")
    elif c["requests"]:
        lines.append("  recommendation: no firing on our workload - no switch patch needed now (the guard stays as upstream "
                     "ships it)")
    return lines


def cmd_lost(a):
    c = lost_count(a.listfile)
    print("\n".join(c5_text(c)))
    return 0


# ================================================================================================ the decision
def c1_verdict(o, sqo, g):
    parts = {}
    parts["cpu"] = parity_status(o / "c1" / "cpu")
    parts["servetests"] = serve_status(o / "c1" / "servetests.txt")
    parts["node"] = node_status(o / "c1" / "servetests.txt", o / "c1" / "node-check.txt")
    gp = parity_status(o / "c1" / "gpu")
    if gs(g, "foreign_par") == "FAIL":
        gp = ("NOT DECIDED", gp[1] + "; a foreign GPU user during the run (void)")
    parts["gpu"] = gp
    vp = Path(sqo) / "verify-VF.json"
    try:
        v = json.loads(vp.read_text()) if vp.exists() else None
    except ValueError:
        v = None
    vv = (v or {}).get("verdict", "NOT RUN")
    vt = (v or {}).get("why", "no verify-VF.json")
    bad = arm_void(g, "sqVF")
    if v and v.get("read_back") is not None:
        vt += f" (read back {v.get('read_back')}, differ {v.get('differ')}, mismatch lines {v.get('mismatch_lines')})"
    if bad and vv == "PASS":
        vv, vt = "NOT DECIDED", vt + f"; but VF's start gates failed: {', '.join(bad)}"
    parts["readback"] = ({"PASS": "PASS", "FAIL": "FAIL"}.get(vv, "NOT DECIDED"), f"{vv}: {vt}")
    st = [s for s, _ in parts.values()]
    res = "FAIL" if "FAIL" in st else ("PASS" if all(s == "PASS" for s in st) else "NOT DECIDED")
    return res, parts


def c3_verdict(sqo, g):
    p = Path(sqo) / "decision.json"
    try:
        d = json.loads(p.read_text()) if p.exists() else None
    except ValueError:
        d = None
    if d is None:
        return "NOT RUN", g.get("skip_sampled", ("", "the sampled part did not run (no sampled/decision.json)"))[1] or \
            "the sampled part did not run", {}
    c = (d.get("candidates") or {}).get("X", {})
    v, why = c.get("verdict", "NOT DECIDED"), c.get("why", "")
    nd = [x for r in ("R1", "R2", "X") for x in arm_void(g, f"sq{r}")]
    if gs(g, "env_sqscore") == "FAIL":
        nd.append("env_sqscore")
    if nd and v in ("PASS", "FAIL"):
        why = f"sq.py gave {v} ({why[:120]}), but the gap's gates on its starts failed: {', '.join(nd)}"
        v = "NOT DECIDED"
    if v not in ("PASS", "FAIL"):
        v = "NOT DECIDED"
    info = {"d2_x_ref": c.get("d2_x_ref"), "band": c.get("band") or d.get("band"), "overall_X": (d.get("overall") or {}).get("X", {}).get("verdict"),
            "sq_verdict": d.get("verdict"), "flags": d.get("flags") or []}
    return v, why, info


def info_speed(o):
    g17 = g17m()
    try:
        b, p = g17.screen_passes(o, "B", amended=True), g17.screen_passes(o, "P", amended=True)
    except Exception as e:  # noqa: BLE001 - information only
        return f"INFO screen speed: not computed ({type(e).__name__}: {str(e)[:120]})"
    if not b or not p:
        return f"INFO screen speed: P {len(p)} / B {len(b)} complete pass(es) of 1 - not compared"
    (db, pb, _), (dp, pp, _) = list(b.values())[0], list(p.values())[0]
    return (f"INFO screen speed (one pass each, no noise estimate): decode geomean P {dp:,.1f} vs B {db:,.1f} tok/s "
            f"({100 * (dp / db - 1):+.1f} %), prompt geomean P {pp:,.1f} vs B {pb:,.1f} tok/s ({100 * (pp / pb - 1):+.1f} %; "
            "the 11-07 amendment's client clock minus the save)")


def info_fixtures(o):
    recs = read_jsonl(Path(o) / "c5" / "fixtures-P.jsonl")
    if not recs:
        return "INFO fixtures on P: not run"
    return "INFO fixtures on P (standard sampling): " + ", ".join(
        f"{r.get('name')} {r.get('completion_tokens')} tokens ({r.get('finish')}) {r.get('decode_tps')} tok/s"
        + ("" if r.get("prompt_tokens") == r.get("expect_prompt_tokens") else f" PROMPT {r.get('prompt_tokens')} != {r.get('expect_prompt_tokens')}")
        for r in recs)


def cmd_decide(a):
    o = Path(a.outdir)
    sqo = Path(a.sampled) if a.sampled else o / "sampled"
    g = read_gates(o / "gates.txt")
    flags, info = [], []
    rp = o / "rules.txt"
    rsha = hashlib.sha256(rp.read_bytes()).hexdigest()[:12] if rp.exists() else "missing"
    if not rp.exists() or rp.read_text() != rules_text():
        flags.append(f"the rule text (or a file it names) differs from the one frozen at the gap's start (rules.txt {rsha})")
    if forms_bad():
        flags.append("a switch has no valid form: " + "; ".join(forms_bad()))
    c1, c1p = c1_verdict(o, sqo, g)
    c2 = c2_compare(o / "c2", g) if (o / "c2").is_dir() and any((o / "c2" / x / "c2.jsonl").exists() for x in C2_ARMS) else \
        {"result": "NOT RUN", "text": g.get("skip_c2", ("", "the served-output part did not run"))[1] or "the served-output part did not run",
         "rows": [], "flags": []}
    c3, c3why, c3info = c3_verdict(sqo, g)
    c4 = c4_judge(o / "c4", g)
    c5 = lost_count(o / "c5" / "serverlogs.txt")
    prio = g.get("priority")
    prio_txt = f"the priority rule stopped the gap ({prio[1][:200]})" if prio and prio[0] == "FAIL" else ""
    kfail = gs(g, "kfail") == "FAIL"
    for k, (s_, d_) in sorted(g.items()):
        if k.startswith("foreign_") and s_ == "FAIL":
            flags.append(f"{k}: {d_[:140]}")
        if k.startswith("void_") and s_ == "FAIL":
            flags.append(f"{k} (a start voided - the run left its test server or an engine behind): {d_[:120]}")
        if k.startswith("priority_") and k != "priority_override" and s_ == "INFO":   # (review M3)
            flags.append(f"the priority check could not read the watch state ({k}): {d_[:120]}")
    flags += [f"(C2) {f}" for f in c2.get("flags", [])]
    flags += [f"(sampled) {f}" for f in (c3info.get("flags") if isinstance(c3info, dict) else []) or []]
    st = {"C1": c1, "C2": c2["result"], "C3": c3, "C4": c4["result"]}
    failed = [k for k in ("C1", "C3", "C4") if st[k] == "FAIL"]
    c2_ok = st["C2"] in ("EXACT", "DIFFERS")
    if failed:
        verdict = "SWITCH CHECKS FAIL (" + ", ".join(failed) + ")"
    elif all(st[k] == "PASS" for k in ("C1", "C3", "C4")) and c2_ok:
        verdict = "SWITCH CHECKS PASS"
    else:
        miss = [f"{k} {st[k]}" for k in ("C1", "C2", "C3", "C4") if (k == "C2" and not c2_ok) or (k != "C2" and st[k] != "PASS")]
        verdict = "INCOMPLETE (" + ", ".join(miss) + ")"
    incomplete = [f"{k} {st[k]}" for k in ("C1", "C2", "C3", "C4") if st[k] in ("NOT DECIDED", "NOT RUN")]
    if failed and incomplete:
        verdict += "; could not run / decide: " + ", ".join(incomplete)
    lines = [f"v0.2.13 PORT SWITCH CHECKS (work/r23/switch-gap/gap-switch0213.sh; rules switch_rules.py, frozen {rsha}): B = "
             f"the daily as served for tests (engine-r23afetch {SHA['B']}, x28h + U + STRATA_ADAPT_FETCH=2) against P = the port "
             f"(engine-r23p0213 {SHA['P']}, P0213x + STRATA_ADAPT_FETCH=2); measurements only",
             f"rules forms (frozen): CITE_FORM {CITE_FORM}, C2_NOREF_FORM {C2_NOREF_FORM}",
             f"VERDICT: {verdict}"]
    if gs(g, "c1_pregap") == "FAIL":
        lines.append(f"C1 BEFORE THE GAP: {g['c1_pregap'][1][:300]} - the gap opened for the other checks (coordinator 11-10)")
    if prio_txt:
        lines.append(f"STOPPED: {prio_txt}; the daily was brought back")
    if kfail:
        lines.append(f"STOPPED: a kernel error / kernel check failure ({g['kfail'][1][:160]}); the daily brought back (see result.txt)")
    ovr = g.get("priority_override", ("", ""))[1]
    if ovr:
        lines.append(f"PRIORITY OVERRIDE: {ovr[:300]}")
    lines.append(f"C1 parity / unit tests + the read-back: {c1}")
    for k, (s_, t_) in c1p.items():
        lines.append(f"  {k}: {s_} - {t_}")
    lines.append(f"C2 served outputs against the daily: {c2['result']} - {c2['text']}")
    for r in c2.get("rows", []):
        lines.append(f"  {r['name']}: {r['status']}" + (f" ({r['why']})" if r.get("why") else "")
                     + (f" (P {r['p_vs_b1']})" if r.get("p_vs_b1") else ""))
    lines.append(f"C3 the sampled test (X = P vs R1 = B, noise twin R2 = B): {c3} - {c3why}")
    if isinstance(c3info, dict) and c3info:
        lines.append(f"  (info) D2(X, R1) {c3info.get('d2_x_ref')}, band {c3info.get('band')}; sq.py overall X (with the "
                     f"read-back) {c3info.get('overall_X')}; sq.py verdict {c3info.get('sq_verdict')}")
    lines.append(f"C4 web search end to end: {c4['result']} - {c4['text']}")
    for r in c4.get("rows", []):
        lines.append(f"  {r['name']}: {r['status']}" + (f" ({'; '.join(r['why'])})" if r.get("why") else ""))
    lines += c5_text(c5)
    info.append(info_speed(o))
    info.append(info_fixtures(o))
    e7 = g.get("e7_P")
    info.append(f"INFO exact7 P (test form, pin 2500) vs the stored x28h-e7a: {e7[0] + ' ' + e7[1][:160] if e7 else 'not run'}"
                f" (env {gs(g, 'env_P_e7') or '-'}; bit-identity is not expected with STRATA_ADAPT_FETCH=2)")
    tail = info + [f"FLAG {f}" for f in flags] + [
        "NOT COVERED (the plan): the port's baseline gate (exactness on the CLI path, long40, the 3-pass screen, Basalt's speed "
        "rule) and REVIEW 4.7 (the single-card fallback, still Cstar18-single).",
        "NOTHING SWITCHES: 8080 stays the daily. Karl decides."]
    txt = "\n".join(lines + tail) + "\n"
    rl = (f"{verdict}" + ("; STOPPED by the priority rule" if prio_txt else "")
          + ("; STOPPED by a kernel error" if kfail else "")
          + f" | C1 {c1}, C2 {c2['result']}, C3 {c3}, C4 {c4['result']} ({c4.get('paid', {}).get('total', 0)} paid), C5 {c5['lost']} "
          f"firing(s) in {c5['requests']} requests")
    res = {"rules_sha": rsha, "verdict": verdict, "checks": st, "c1_parts": c1p, "c2": c2, "c3": [c3, c3why, c3info],
           "c4": c4, "c5": c5, "info": info, "flags": flags, "result_line": rl}
    (o / "verdict.txt").write_text(verdict + "\n")
    (o / "decision.txt").write_text(txt)
    (o / "decision.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    (o / "result-line.txt").write_text(rl + "\n")
    if not getattr(a, "quiet", False):
        print(txt, end="")
    return 0


# ================================================================================================ the selftest
def selftest(scratch):
    """synthetic data only (no GPU, no engine, no server, no gap component run); everything under SCRATCH. Reads the real
    configs, the real build-switch/CTestTestfile.cmake and the real server trees' websearch.py (read only)."""
    sc = Path(scratch)
    if sc.exists():
        shutil.rmtree(sc)
    sc.mkdir(parents=True)
    fails = []

    def check(name, cond, detail=""):
        print(f"{'ok  ' if cond else 'FAIL'} {name}" + (f": {str(detail)[:500]}" if detail and not cond else ""), flush=True)
        if not cond:
            fails.append(name)

    def ns(**k):
        return argparse.Namespace(**k)
    buf = io.StringIO()
    # ---- the arms on the real configs
    cf = sc / "configs"
    with redirect_stdout(buf):
        rc = cmd_arms(ns(outdir=str(cf), log_dir=str(sc / "logs"), no_sha=True, spec=str(SPEC), sampled=None, gate="cfg",
                         gates=str(sc / "g-cfg.txt")))
    check("arms + cfgcheck PASS on the real configs (B = x28h + U + =2 on the fetch build; P = P0213x + =2 = B + pins; debug "
          "arms = sampled R1 / R2 / X; VF = X + read-back)", rc == 0, buf.getvalue()[-600:])
    b, p = json.loads((cf / "B.json").read_text()), json.loads((cf / "P.json").read_text())
    check("B: engine-r23afetch, strata-r22p028x server, no picture reader, its own log", b["exe"] == str(EXE_B)
          and b["server"] == str(SRV["B"]) and "--vision" not in b["args"] and "vision" not in b
          and b["log"] == str(sc / "logs/engine-r23sw-B.log"))
    check("P: engine-r23p0213, strata-r23p0213 server, the same args as B, =2", p["exe"] == str(EXE_P)
          and p["server"] == str(SRV["P"]) and p["args"] == b["args"] and p["env"]["STRATA_ADAPT_FETCH"] == "2")
    with redirect_stdout(io.StringIO()):
        rc = cmd_cfgcheck(ns(outdir=str(cf), no_sha=False, spec=str(SPEC), sampled=None, gate="cfgsha", gates=str(sc / "g-cfg.txt")))
    check("cfgcheck with the engine shas (153ce47d3ef0 / 639dfb1b7042, no STRATA_DEBUG in either binary)", rc == 0,
          read_gates(sc / "g-cfg.txt").get("cfgsha"))
    for what, edit in (("a stray fetch switch in P", lambda c: c["P"]["env"].__setitem__("STRATA_ADAPT_FETCH_VERIFY", "1")),
                       ("a missing pin in P", lambda c: c["P"]["env"].pop("STRATA_GDN_TC")),
                       ("B on the old engine", lambda c: c["B"].__setitem__("exe", str(WS / "engine-r22p028x/strata"))),
                       ("P with another arg", lambda c: c["P"]["args"].extend(["--kv", "fp16"])),
                       ("the served log", lambda c: c["B"].__setitem__("log", str(WS / "logs/engine-P028x.log"))),
                       ("P-dbg without STRATA_DEBUG", lambda c: c["P-dbg"]["env"].pop("STRATA_DEBUG"))):
        d2 = sc / f"cf-{len(list(sc.glob('cf-*')))}"
        shutil.copytree(cf, d2)
        cfgs = {n: json.loads((d2 / f"{n}.json").read_text()) for n in ARMS}
        edit(cfgs)
        for n, c in cfgs.items():
            (d2 / f"{n}.json").write_text(json.dumps(c))
        with redirect_stdout(io.StringIO()):
            rc = cmd_cfgcheck(ns(outdir=str(d2), no_sha=True, spec=str(SPEC), sampled=None, gate=None, gates=None))
        check(f"cfgcheck catches {what}", rc == 1)
    sp2 = json.loads(SPEC.read_text())
    sp2["arms"]["X"]["env"] = {"STRATA_ADAPT_FETCH": "1"}
    (sc / "spec-x.json").write_text(json.dumps(sp2))
    with redirect_stdout(io.StringIO()):
        rc = cmd_cfgcheck(ns(outdir=str(cf), no_sha=True, spec=str(sc / "spec-x.json"), sampled=None, gate=None, gates=None))
    check("cfgcheck catches a sampled X that is not P-dbg (X at =1)", rc == 1)
    # ---- the programs: the real CTestTestfile.cmake (read only) and a synthetic one
    if (BUILD / "CTestTestfile.cmake").exists():
        cpu, gpu, bad, per = select_entries(BUILD)
        names = {e["name"] for e in cpu + gpu}
        check(f"ctestlist on build-switch: {len(cpu)} CPU + {len(gpu)} GPU entries, every switchtests program covered, no problem",
              not bad and {"cost_gate_test", "q8k_quant_parity_avx", "spec_prob_test", "gguf_geometry_test"} <= {e["name"] for e in cpu}
              and {"prefill_fused_iq_test", "prefill_fused_v2_test", "sampler_parity_old", "native_dense_ple_key_test",
                   "gr_upmix_parity", "verify_batch_parity"} <= {e["name"] for e in gpu}
              and not any(e["base"] in CPU_PROGRAMS for e in gpu) and "spec_admission_top" not in names, (bad, sorted(names)[:20]))
        v2 = next(e for e in gpu if e["name"] == "prefill_fused_v2_test")
        avx = next(e for e in cpu if e["name"] == "q8k_quant_parity_avx")
        check("ctestlist: the --v2 entry's args, a cmake -E env wrapper's program and env, a registered env / skip code",
              v2["argv"][1:] == ["--v2", "--no-timing"] and v2["skip_rc"] == "77" and avx["base"] == "q8k_quant_parity"
              and avx["env"] == ["STRATA_FORCE_ISA=avx"]
              and next(e for e in gpu if e["name"] == "sampler_parity_old")["env"] == ["STRATA_OLD_SAMPLER=1", "STRATA_SAMPLER_ONE_BLOCK=0"])
    else:
        check("build-switch/CTestTestfile.cmake exists (the switchtests build)", False)
    fb = sc / "fake-build"
    fb.mkdir()
    for t in SWITCH_TARGETS:
        (fb / t).write_text("x")
    reg = [t for t in SWITCH_TARGETS if t not in UNREGISTERED and t != "verify_batch_parity"]
    (fb / "CTestTestfile.cmake").write_text("".join(f'add_test([=[{t}]=] "{fb}/{t}" "--selftest")\n' for t in reg)
                                            + f'add_test([=[other]=] "{fb}/not_ours")\n')
    cpu, gpu, bad, _ = select_entries(fb)
    check("ctestlist refuses a build where a program has no entry (verify_batch_parity)", any("verify_batch_parity" in x for x in bad), bad)
    # ---- parity counts (shape_rules' parser) and their status
    for name, junit, direct, want in (
            ("pass+skip", [("a", "run", None), ("b", "notrun", "SKIP_RETURN_CODE=77")], "patch_guard_test PASS rc=0 1 s\n", "PASS"),
            ("fail", [("a", "run", None), ("b", "fail", None)], "", "FAIL"),
            ("notrun", [("a", "run", None)], "", "NOT DECIDED")):
        d = sc / f"par-{name}"
        d.mkdir()
        cases = []
        for n, s, m in junit:
            if s == "run":
                cases.append(f'<testcase name="{n}" status="run" time="1"/>')
            elif s == "fail":
                cases.append(f'<testcase name="{n}" status="fail" time="1"><failure message="Failed"/></testcase>')
            else:
                cases.append(f'<testcase name="{n}" status="notrun" time="0"><skipped message="{m}"/></testcase>')
        (d / "junit.xml").write_text("<testsuite>" + "".join(cases) + "</testsuite>")
        (d / "direct.txt").write_text(direct)
        nm = [n for n, _, _ in junit] + (["c"] if name == "notrun" else [])
        (d / "names.txt").write_text("\n".join(nm) + "\n")
        with redirect_stdout(io.StringIO()):
            cmd_parity(ns(dir=str(d), names=str(d / "names.txt"), label=name))
        check(f"parity {name} -> {want}", parity_status(d)[0] == want, parity_status(d))
    # ---- the server suite and the node tests
    def suite(lines, ran=True):
        return "\n".join(lines + ([f"Ran {len(lines)} tests in 600.0s", "", "FAILED (failures=1)" if any(x.startswith("FAIL:") for x in lines) else "OK"] if ran else [])) + "\n"
    ok_lines = ["test_history (test_web_history.WebHistoryTests.test_history) ... ok",
                "test_math (test_web_math.MathTests.test_math) ... ok", "test_x (test_server.T.test_x) ... ok"]
    for name, text, ncheck, ws, wn in (
            ("clean", suite(ok_lines), "rc 0\n", "PASS", "PASS"),
            ("known fail", suite(ok_lines + ["FAIL: test_hip_ordinal (test_gpu_roles_server.T.test_hip_ordinal)"]), "rc 0\n", "PASS", "PASS"),
            ("new fail", suite(ok_lines + ["ERROR: test_web_follow (test_web_follow.T.test_web_follow)"]), "rc 0\n", "FAIL", "PASS"),
            ("no node", suite(["test_history (test_web_history.WebHistoryTests.test_history) ... skipped 'node is not installed'",
                               "test_x (test_server.T.test_x) ... ok"]), "rc 0\n", "PASS", "NOT DECIDED"),
            ("node check fails", suite(ok_lines), "SyntaxError\nrc 1\n", "PASS", "FAIL"),
            ("cut by its timeout", "test_x (test_server.T.test_x) ... ok\n", "rc 0\n", "NOT DECIDED", "NOT DECIDED")):
        f, nf = sc / f"serve-{name.replace(' ', '_')}.txt", sc / f"node-{name.replace(' ', '_')}.txt"
        f.write_text(text)
        nf.write_text(ncheck)
        check(f"servetests {name} -> {ws}, node -> {wn}", serve_status(f)[0] == ws and node_status(f, nf)[0] == wn,
              (serve_status(f), node_status(f, nf)))
    # ---- the web path: the real trees (the Exa / Tavily fallback) and a synthetic SearXNG-only tree
    ok, lines = web_path([TREE["B"], TREE["P"]], [CFG_B, CFG_P])
    check("webpath on the real trees: PAID PATH (websearch.py's Exa / Tavily fallback) in both", not ok
          and sum(1 for x in lines if "PAID PATH" in x) == 2, lines)
    # (coordinator 11-10) the budget check through the modules' own counter code (fake modules here; no key file anywhere)
    def tools(name, exa_usd, exa_n, tav_n, exa_av=True, tav_av=True, closed=False):
        d = sc / f"tools-{name}"
        d.mkdir()
        (d / "u.json").write_text(json.dumps({"exa": [exa_usd, exa_n, exa_av, closed], "tav": [tav_n, tav_av]}))
        (d / "exa_fallback.py").write_text(
            "import json\nfrom pathlib import Path\nU = Path(__file__).with_name('u.json')\nMONTH_CREDIT_USD = 10.0\n"
            "PRICE_USD = {'lite': 0.004}\nSEARCH_TYPE = 'lite'\nCAP_USD = 9.0\n"
            "def available():\n    return json.loads(U.read_text())['exa'][2]\n"
            "def usage():\n    u = json.loads(U.read_text())['exa']\n    return {'month': '2026-11', 'usd': u[0], 'searches': u[1], "
            "'closed': u[3], 'cap_usd': CAP_USD}\n")
        (d / "tavily_fallback.py").write_text(
            "import json\nfrom pathlib import Path\nU = Path(__file__).with_name('u.json')\nMONTH_CREDITS = 1000\nCAP = 900\n"
            "def available():\n    return json.loads(U.read_text())['tav'][1]\n"
            "def usage():\n    return {'month': '2026-11', 'count': json.loads(U.read_text())['tav'][0], 'cap': CAP}\n")
        return d
    for name, args, want in (("plenty", (1.0, 250, 100), True), ("exa-low", (7.47, 1860, 100), False),
                             ("exa-edge", (7.46, 1860, 100), True), ("tav-low", (1.0, 250, 741), False),
                             ("exa-off", (9.9, 2400, 100, False), True), ("exa-closed", (9.9, 2400, 100, True, True, True), True),
                             ("both-off", (9.9, 2400, 999, False, False), True)):
        st_ = paid_state(tools(name, *args))
        ok_, bl = budget_ok(st_)
        check(f"paid budget {name} -> {'OK' if want else 'C4 NOT RUN: paid budget'}", ok_ == want, bl)
    check("paid_calls sums Exa's searches and Tavily's count", paid_calls(paid_state(sc / "tools-plenty")) == 350)
    for name, tdir, want_rc, want_g in (("plenty", "tools-plenty", 0, "PAID"), ("low", "tools-exa-low", 10, "REFUSED"),
                                        ("unreadable", "no-such-tools", 10, "REFUSED")):
        gfw = sc / "g-web.txt"
        with redirect_stdout(io.StringIO()):
            rc = cmd_webpath(ns(trees=[str(TREE["P"])], configs=[str(CFG_P)], tools=str(sc / tdir), gate=f"wp-{name}", gates=str(gfw)))
        check(f"webpath on the paid path, budget {name} -> exit {want_rc}, gate {want_g}", rc == want_rc
              and gs(read_gates(gfw), f"wp-{name}") == want_g, read_gates(gfw).get(f"wp-{name}"))
    (sc / "local-tree0" / "serve").mkdir(parents=True)
    (sc / "local-tree0" / "serve" / "websearch.py").write_text("def search(q):\n    return get('http://127.0.0.1:8888/search?q=' + q)\n")
    with redirect_stdout(io.StringIO()):
        rc = cmd_webpath(ns(trees=[str(sc / "local-tree0")], configs=[str(CFG_P)], tools=str(sc / "no-such-tools"), gate="wp-local",
                            gates=str(sc / "g-web.txt")))
    check("webpath on a SearXNG-only tree needs no counters -> PASS", rc == 0 and gs(read_gates(sc / "g-web.txt"), "wp-local") == "PASS")
    with redirect_stdout(io.StringIO()):
        rc = cmd_paidcheck(ns(tools=str(sc / "tools-tav-low"), out=str(sc / "paid.json"), gate="pc", gates=str(sc / "g-web.txt")))
    check("paidcheck: low -> exit 10, REFUSED, the state written", rc == 10 and gs(read_gates(sc / "g-web.txt"), "pc") == "REFUSED"
          and json.loads((sc / "paid.json").read_text())["tavily"]["calls"] == 741)
    lt = sc / "local-tree"
    (lt / "serve").mkdir(parents=True)
    (lt / "serve" / "websearch.py").write_text("def search(q):\n    return get('http://127.0.0.1:8888/search?q=' + q)\n")
    ok, lines = web_path([lt], [CFG_P])
    check("webpath on a SearXNG-only tree with a local searxng -> LOCAL ONLY", ok, lines)
    rc_cfg = sc / "remote.json"
    rc_cfg.write_text(json.dumps({"web_search": {"searxng": "https://search.example.org"}}))
    check("webpath with a remote searxng -> refused", not web_path([lt], [rc_cfg])[0])
    # ---- armenv (synthetic /proc readings) and the start line
    cdbg = cf / "P-dbg.json"
    pc = json.loads(cdbg.read_text())
    good = (1, dict(pc["env"]), SHA["P"], ["python", str(SRV["P"]), "--engine", "strata", "--config", str(cdbg)], dict(pc["env"]))
    check("armenv: the arm's engine and server as configured -> no problem", not armenv_problems([good], str(cdbg), pc, "P"))
    for what, pr in (("the wrong binary", [(1, good[1], SHA["B"], good[3], good[4])]),
                     ("STRATA_DEBUG missing in the server", [(1, good[1], SHA["P"], good[3], {k: v for k, v in good[4].items() if k != "STRATA_DEBUG"})]),
                     ("a VERIFY behind the config", [(1, dict(good[1], STRATA_ADAPT_FETCH_VERIFY="1"), SHA["P"], good[3], good[4])]),
                     ("another server tree", [(1, good[1], SHA["P"], ["python", str(SRV["B"]), "--config", str(cdbg)], good[4])]),
                     ("a server pin lost", [(1, good[1], SHA["P"], good[3], dict(good[4], STRATA_BLOCKING_CONSOLE="0"))]),
                     ("two engines", [good, good]), ("none", [])):
        check(f"armenv catches {what}", bool(armenv_problems(pr, str(cdbg), pc, "P")))
    ON2 = "strata serve: STRATA_ADAPT_FETCH=2: the PCIe share takes each layer's most-routed misses and admits those routed >= 2.00\n"
    check("startline: =2 on -> PASS; off / none / on + off -> FAIL", startline_ok(ON2)[0] and not startline_ok("x\n")[0]
          and not startline_ok("strata serve: STRATA_ADAPT_FETCH is off (helper GPUs)\n")[0]
          and not startline_ok(ON2 + "strata serve: STRATA_ADAPT_FETCH is off (x)\n")[0])
    # ---- the plans
    pl = c2_plan()
    check("C2 plan: 4 prompts x 2 seeds, think = W1-think thinking on at 1536 (answer_room 1024), the others off at 512, "
          "the standard fields", len(pl["requests"]) == 8 and pl["requests"][0]["thinking"] is True
          and pl["requests"][0]["max_tokens"] == 1536 and all(r["max_tokens"] == 512 and r["thinking"] is False for r in pl["requests"][2:])
          and pl["fields"] == dict(STANDARD, presence_penalty=0.0, frequency_penalty=0.0, repetition_penalty=1.0)
          and [r["seed"] for r in pl["requests"][:2]] == list(SEEDS_C2))
    check("C4 plan: 3 search prompts, thinking off, 1024 a round", len(c4_plan()["requests"]) == 3)
    # ---- C2 compare
    def c2dir(name, mut=None, gates=None):
        d = sc / f"c2-{name}"
        (d).mkdir()
        (d / "plan.json").write_text(json.dumps(pl))
        for arm in C2_ARMS:
            (d / arm).mkdir()
            rows = []
            for i, r in enumerate(pl["requests"]):
                rec = {"name": r["name"], "prompt_tokens": 38, "ids": [100 + i, 5, 6, 7], "finish": "length",
                       "continuation": r["name"].startswith("think")}
                if mut:
                    rec = mut(arm, rec)
                if rec is not None:
                    rows.append(rec)
            (d / arm / "c2.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
        return c2_compare(d, gates or {})
    r = c2dir("exact")
    check("C2 identical ids on B1 / B2 / P -> EXACT (8 reproducible)", r["result"] == "EXACT" and r["reproducible"] == 8, r["text"])
    r = c2dir("differs", lambda arm, x: dict(x, ids=x["ids"][:2] + [9, 9]) if arm == "P" and x["name"] == "conv-s1" else x)
    check("C2 P differs on a B-reproducible request -> DIFFERS (first difference named)", r["result"] == "DIFFERS"
          and any(x["status"] == "DIFFERS" and x["first_diff"] == 2 for x in r["rows"]), r["text"])
    r = c2dir("bnorep", lambda arm, x: dict(x, ids=x["ids"] + [arm == "B2"]) if x["name"] == "think-s1" else x)
    check("C2 B differs from itself on one request -> info only, the rest EXACT", r["result"] == "EXACT"
          and r["reproducible"] == 7 and any(x["status"].startswith("B NOT") for x in r["rows"]), r["text"])
    r = c2dir("noref", lambda arm, x: dict(x, ids=x["ids"] + [1 if arm == "B2" else 0]))
    check("C2 no B-reproducible request -> DIFFERS under C2_NOREF_FORM differs (flagged)", r["result"] == "DIFFERS"
          and any("no request was B-reproducible" in f for f in r["flags"]), r["text"])
    d_nr = sc / "c2-noref"
    check("C2 no B-reproducible request -> NOT DECIDED under not-decided", c2_compare(d_nr, {}, "not-decided")["result"] == "NOT DECIDED")
    r = c2dir("missing", lambda arm, x: None if arm == "B2" and x["name"] == "prose-s2" else x)
    check("C2 a request missing on B2 -> NOT DECIDED", r["result"] == "NOT DECIDED" and r["missing"] == 1, r["text"])
    r = c2dir("void", None, {"env_c2P": ("FAIL", "x")})
    check("C2 P's start not the arm (env FAIL) -> NOT DECIDED even with equal ids", r["result"] == "NOT DECIDED", r["text"])
    r = c2dir("errfinish", lambda arm, x: dict(x, finish="error") if arm == "P" and x["name"] == "code-s1" else x)
    check("C2 an error finish on P -> that request MISSING -> NOT DECIDED", r["result"] == "NOT DECIDED", r["text"])
    r = c2dir("nocont", lambda arm, x: dict(x, continuation=False) if arm == "P" else x)
    check("C2 the continuation not seen on P: flagged (the result stands)", r["result"] == "EXACT"
          and any("continuation" in f for f in r["flags"]), r["flags"])
    # ---- C4 judge
    def c4dir(name, mut=None, gates=None):
        d = sc / f"c4-{name}"
        d.mkdir()
        (d / "plan.json").write_text(json.dumps(c4_plan()))
        for arm in ("B", "P"):
            (d / arm).mkdir()
            rows = []
            for rq in c4_plan()["requests"]:
                rec = {"name": rq["name"], "completed": True, "finish": "stop", "search_calls": 1, "fetch_ok": ["https://x.org/a"],
                       "cited_fetched": ["x.org/a"], "cited_tool": ["x.org/a"], "errors": []}
                if mut:
                    rec = mut(arm, rec)
                if rec is not None:
                    rows.append(rec)
            (d / arm / "web.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
        return c4_judge(d, gates or {})
    check("C4 every request completes with a search, a fetched cited source, no error -> PASS", c4dir("pass")["result"] == "PASS")
    check("C4 P without a search round on one -> FAIL", c4dir("nosearch", lambda a_, x: dict(x, search_calls=0) if a_ == "P" and x["name"] == "btree" else x)["result"] == "FAIL")
    r = c4dir("snippet", lambda a_, x: dict(x, cited_fetched=[]) if a_ == "P" else x)
    check("C4 P cites only search results: PASS under tool-url (the frozen form), FAIL under fetch-page", r["result"] == "PASS"
          and c4_judge(sc / "c4-snippet", {}, "fetch-page")["result"] == "FAIL", r["text"])
    r = c4dir("notool", lambda a_, x: dict(x, cited_fetched=[], cited_tool=[]) if a_ == "P" and x["name"] == "btree" else x)
    check("C4 P cites no tool URL on one -> FAIL (tool-url)", r["result"] == "FAIL", r["text"])
    r = c4dir("stop", lambda a_, x: (dict(x, paid_calls=4) if a_ == "B" else
                                     (dict(x, not_run=True, completed=False, why="the paid-call stop (10 reached)") if x["name"] == "searxng" else dict(x, paid_calls=1))))
    check("C4 the paid-call stop: the request not run on P is NOT RUN, the 2 that ran judged -> PASS, 14 paid recorded",
          r["result"] == "PASS" and any(x["status"].startswith("NOT RUN") for x in r["rows"]) and r["paid"]["total"] == 14
          and "paid searches during C4: 14" in r["text"], r["text"])
    r = c4dir("stop1", lambda a_, x: dict(x, not_run=True, completed=False, why="stop") if a_ == "P" and x["name"] != "python" else x)
    check("C4 only 1 request ran on P -> NOT DECIDED (fewer than 2 per arm)", r["result"] == "NOT DECIDED"
          and "fewer than 2 requests ran" in r["text"], r["text"])
    check("C4 refused right before C4 (c4budget) -> NOT RUN", c4_judge(sc / "c4-none2", {"c4budget": ("REFUSED", "C4 NOT RUN: paid budget")})["result"] == "NOT RUN")
    check("C4 a request that did not complete on B is not judged; the rest PASS", c4dir("bfail", lambda a_, x: dict(x, completed=False) if a_ == "B" and x["name"] == "python" else x)["result"] == "PASS")
    check("C4 none completed on B -> NOT DECIDED", c4dir("bnone", lambda a_, x: dict(x, completed=False) if a_ == "B" else x)["result"] == "NOT DECIDED")
    check("C4 an error on P -> FAIL", c4dir("perr", lambda a_, x: dict(x, errors=["the lost-answer line"]) if a_ == "P" and x["name"] == "searxng" else x)["result"] == "FAIL")
    check("C4 P's start voided -> NOT DECIDED", c4dir("pvoid", None, {"void_webP": ("FAIL", "x")})["result"] == "NOT DECIDED")
    r = c4dir("pfatal", None, {"fatal_webP": ("FAIL", "2 line(s): the engine had stopped (exit code 139)")})
    check("C4 (review S2) a fatal line on P's start -> FAIL, named", r["result"] == "FAIL" and "the engine had stopped" in r["text"], r["text"])
    check("C4 a fatal line on B's start still voids -> NOT DECIDED", c4dir("bfatal", None, {"fatal_webB": ("FAIL", "x")})["result"] == "NOT DECIDED")
    r = c4_judge(sc / "c4-pass", {"penv_webP": ("FAIL", "C4 NOT RUN (env): PAID_SEARCH_RUN_CAP=unset (want 10)")})
    check("C4 (review S1) the hard cap missing from P's server environment -> NOT RUN (env)", r["result"] == "NOT RUN"
          and r["text"].startswith("C4 NOT RUN (env)"), r["text"])
    check("the per-arm hard caps: B 5, P 10 (one run id), the soft stops 5 per arm / 10 in all", PAID_CAP == {"B": 5, "P": 10}
          and PAID_ARM_STOP == 5 and PAID_STOP == 10)
    check("C4 refused before the gap -> NOT RUN", c4_judge(sc / "c4-none", {"webpath": ("REFUSED", "WEB PATH CAN REACH A PAID API")})["result"] == "NOT RUN")
    check("C4 not run at all -> NOT RUN", c4_judge(sc / "c4-nothing", {})["result"] == "NOT RUN")
    check("norm_url: scheme / www / trailing slash / punctuation", norm_url("https://www.Python.org/downloads/.") == "python.org/downloads"
          and norm_url("python.org/downloads/") == "python.org/downloads")
    # ---- C5
    lg = sc / "c5"
    lg.mkdir()
    (lg / "scrP.log").write_text("[strata] done: 10 tokens\n[strata] done: 12 tokens\n[strata] " + LOST_LINE + "; it is answered as an error\n")
    (lg / "c2P.log").write_text("[strata] req openai: x\n[strata] done: 4 tokens\n")
    (lg / "B.log").write_text("[strata] " + LOST_LINE + "\n")
    (lg / "list.txt").write_text(f"scrP1 P lab1 {lg / 'scrP.log'} 10\nc2P P lab2 {lg / 'c2P.log'} 8\nc2B1 B lab3 {lg / 'B.log'} 8\n"
                                 f"bpP P lab4 {lg / 'nope.log'} 3\n")
    c = lost_count(lg / "list.txt")
    t5 = "\n".join(c5_text(c))
    check("C5 counts P logs only (1 firing on the screen, named; 0 in C2's; B's ignored; a missing log listed), recommends",
          c["lost"] == 1 and c["workload_lost"] == 1 and c["requests"] == 18 and len(c["firings"]) == 1
          and "scrP.log line 3" in c["firings"][0] and "RECOMMENDATION" in t5 and "server log missing" in t5, t5)

    # ---- the decision end to end (synthetic outputs)
    def mk(name, c1="PASS", vf="PASS", c2=None, c3="PASS", c4="PASS", gates=(), cpufail=False):
        o = sc / f"dec-{name}"
        sqo = o / "sampled"
        for x in ("c1/cpu", "c1/gpu", "c2", "c4", "c5", "sampled", "speed"):
            (o / x).mkdir(parents=True, exist_ok=True)
        (o / "rules.txt").write_text(rules_text())
        for part in ("cpu", "gpu"):
            fl = 1 if ((c1 == "FAIL" and part == "gpu") or (cpufail and part == "cpu")) else 0
            nr = 1 if (c1 == "NOTRUN" and part == "gpu") else 0
            (o / "c1" / part / "counts.json").write_text(json.dumps({"label": part, "pass": 10, "skip": 1, "fail": fl + nr,
                                                                     "notrun": nr, "total": 11 + fl + nr, "fails": ["x (FAIL: y)"] if fl else []}))
        (o / "c1" / "servetests.txt").write_text(suite(ok_lines))
        (o / "c1" / "node-check.txt").write_text("rc 0\n")
        if vf:
            (sqo / "verify-VF.json").write_text(json.dumps({"verdict": vf, "why": f"read-back {vf}", "read_back": 412, "differ": 0,
                                                            "mismatch_lines": 0 if vf != "FAIL" else 2}))
        if c2 != "absent":
            (o / "c2" / "plan.json").write_text(json.dumps(pl))
            for arm in C2_ARMS:
                (o / "c2" / arm).mkdir(exist_ok=True)
                rows = [{"name": r_["name"], "prompt_tokens": 38, "ids": [i, 1] + ([7] if (c2 == "DIFFERS" and arm == "P" and i == 0) else []),
                         "finish": "length", "continuation": r_["name"].startswith("think")} for i, r_ in enumerate(pl["requests"])]
                (o / "c2" / arm / "c2.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
        if c3 != "absent":
            (sqo / "decision.json").write_text(json.dumps({"verdict": "x", "flags": [], "candidates": {"X": {"verdict": c3, "why": f"D2 ({c3})",
                                                           "d2_x_ref": 3.2, "band": 11.345}}, "overall": {"X": {"verdict": c3}}}))
        g_lines = []
        if c4 == "REFUSED":
            g_lines.append("webpath REFUSED WEB PATH CAN REACH A PAID API: C4 is NOT RUN")
        elif c4 != "absent":
            (o / "c4" / "plan.json").write_text(json.dumps(c4_plan()))
            for arm in ("B", "P"):
                (o / "c4" / arm).mkdir(exist_ok=True)
                (o / "c4" / arm / "web.jsonl").write_text("".join(json.dumps(
                    {"name": rq["name"], "completed": True, "search_calls": 2, "cited_fetched": ["x.org"], "cited_tool": ["x.org"],
                     "errors": [] if not (c4 == "FAIL" and arm == "P") else ["an error chunk"]}) + "\n" for rq in c4_plan()["requests"]))
        if cpufail:
            g_lines.append("c1_pregap FAIL cpu_tests FAIL; the gap opens for the other checks")
        (o / "gates.txt").write_text("\n".join(g_lines + list(gates)) + "\n")
        (o / "c5" / "serverlogs.txt").write_text("")
        with redirect_stdout(io.StringIO()):
            cmd_decide(ns(outdir=str(o), sampled=None, quiet=True))
        return json.loads((o / "decision.json").read_text()), (o / "decision.txt").read_text()
    d, t = mk("pass", c2="EXACT")
    check("decide: C1 PASS, C2 EXACT, C3 PASS, C4 PASS -> SWITCH CHECKS PASS", d["verdict"] == "SWITCH CHECKS PASS", t[:600])
    d, t = mk("differs", c2="DIFFERS")
    check("decide: C2 DIFFERS with C3 PASS -> SWITCH CHECKS PASS", d["verdict"] == "SWITCH CHECKS PASS" and d["checks"]["C2"] == "DIFFERS", t[:600])
    d, t = mk("differs-c3nd", c2="DIFFERS", c3="NOT DECIDED")
    check("decide: C2 DIFFERS with C3 NOT DECIDED -> INCOMPLETE (C3 named)", d["verdict"].startswith("INCOMPLETE") and "C3 NOT DECIDED" in d["verdict"], d["verdict"])
    d, t = mk("c3fail", c3="FAIL")
    check("decide: C3 FAIL -> SWITCH CHECKS FAIL (C3)", d["verdict"] == "SWITCH CHECKS FAIL (C3)", d["verdict"])
    d, t = mk("c1fail", c1="FAIL")
    check("decide: a GPU program fails -> SWITCH CHECKS FAIL (C1)", d["verdict"] == "SWITCH CHECKS FAIL (C1)", d["verdict"])
    d, t = mk("vffail", vf="FAIL")
    check("decide: the read-back mismatches -> SWITCH CHECKS FAIL (C1)", d["verdict"] == "SWITCH CHECKS FAIL (C1)"
          and d["c1_parts"]["readback"][0] == "FAIL", d["verdict"])
    d, t = mk("vfvoid", gates=["fatal_sqVF FAIL 1 line"])
    check("decide: a read-back PASS on a start with a fatal line -> C1 NOT DECIDED -> INCOMPLETE", d["checks"]["C1"] == "NOT DECIDED"
          and d["verdict"].startswith("INCOMPLETE"), d["verdict"])
    d, t = mk("refused", c4="REFUSED")
    check("decide: C4 refused (the paid path) -> INCOMPLETE (C4 NOT RUN)", d["verdict"] == "INCOMPLETE (C4 NOT RUN)", d["verdict"])
    d, t = mk("c4fail-c1nd", c1="NOTRUN", c4="FAIL")
    check("decide: C4 FAIL and C1 not decided -> FAIL (C4), the undecided part listed", d["verdict"].startswith("SWITCH CHECKS FAIL (C4)")
          and "C1 NOT DECIDED" in d["verdict"], d["verdict"])
    d, t = mk("c2missing", c2="absent")
    check("decide: C2 did not run -> INCOMPLETE (C2 NOT RUN)", d["verdict"] == "INCOMPLETE (C2 NOT RUN)", d["verdict"])
    d, t = mk("sqgate", gates=["foreign_sqX FAIL seen during sqX"])
    check("decide: a foreign GPU user during X -> C3 NOT DECIDED (sq.py's PASS does not stand), flagged", d["checks"]["C3"] == "NOT DECIDED"
          and any("foreign_sqX" in f for f in d["flags"]), d["verdict"])
    d, t = mk("cpufail", cpufail=True)
    check("decide: a CPU part failed before the gap (the gap opened anyway) -> FAIL (C1) with the test named, C2-C4 still "
          "judged", d["verdict"] == "SWITCH CHECKS FAIL (C1)" and "C1 BEFORE THE GAP" in t and "x (FAIL: y)" in t
          and d["checks"]["C3"] == "PASS" and d["checks"]["C4"] == "PASS", t[:900])
    d, t = mk("override", gates=["priority_override INFO PRIORITY OVERRIDDEN: x; HOLD OVERRIDDEN by tmp/switch0213-priority-done: 2026-11-14: Karl",
                                 "priority_C2_P INFO PRIORITY UNKNOWN: the state file could not be read"])
    check("decide (review M3): the override is named, not flagged as an unreadable watch state; a real unreadable check is",
          "PRIORITY OVERRIDE: " in t and not any("priority_override" in f for f in d["flags"])
          and any("priority_C2_P" in f for f in d["flags"]), d["flags"])
    d, t = mk("budget", gates=["c4budget REFUSED C4 NOT RUN: paid budget - exa: 7.6 of 10 USD used"])
    check("decide: the budget refused right before C4 -> INCOMPLETE (C4 NOT RUN), the reason in the decision",
          d["verdict"] == "INCOMPLETE (C4 NOT RUN)" and "C4 NOT RUN: paid budget" in t, d["verdict"])
    o = sc / "dec-pass"
    (o / "rules.txt").write_text("other\n")
    with redirect_stdout(io.StringIO()):
        cmd_decide(ns(outdir=str(o), sampled=None, quiet=True))
    check("decide: a changed rules.txt -> FLAG", "FLAG the rule text" in (o / "decision.txt").read_text())
    rt = rules_text()
    check("rules text: the switches at the freeze and the files' shas (this one, the driver, the clients, the spec, sq.py)",
          "THE SWITCHES AT THE FREEZE:\n  CITE_FORM = tool-url\n  C2_NOREF_FORM = differs" in rt
          and f"work/r23/switch-gap/switch_rules.py {sha256_file(SG / 'switch_rules.py', 16)}" in rt
          and "work/r23/switch-gap/c2_client.py" in rt and "work/r23/sampled-qwen/sq.py" in rt and "spec-port0213.json" in rt)
    global CITE_FORM
    keep = CITE_FORM
    CITE_FORM = "bogus"
    check("forms_bad catches a switch outside its forms", forms_bad() == ["CITE_FORM='bogus' (want one of ('tool-url', 'fetch-page'))"])
    CITE_FORM = keep
    with redirect_stdout(io.StringIO()) as b2:
        rc = cmd_forms(ns())
    check("forms prints the switches", rc == 0 and "CITE_FORM=tool-url" in b2.getvalue())
    check("the sampling rule: every plan's fields are the standard T 1.0 / 0.95 / 20 / min-p 0.05",
          all(c2_plan()["fields"][k] == v and c4_plan()["fields"][k] == v for k, v in STANDARD.items()))
    print(f"switch_rules selftest: {len(fails)} failure(s)" + (f": {', '.join(fails)}" if fails else ""))
    return 1 if fails else 0


# ================================================================================================ main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)

    def sub(name, *pos, gates=True):
        p = sp.add_parser(name)
        for x in pos:
            p.add_argument(x)
        if gates:
            p.add_argument("--gate")
            p.add_argument("--gates")
        return p
    sub("forms", gates=False)
    for n in ("arms", "cfgcheck"):
        p = sub(n, "outdir")
        p.add_argument("--spec", default=str(SPEC))
        p.add_argument("--sampled", help="the derived sampled folder (its cfg/ files are compared)")
        p.add_argument("--no-sha", action="store_true", help="(the driver's --mock only) skip the engine sha / string checks")
        p.add_argument("--log-dir", help="(the driver's --mock only) the arms' engine logs elsewhere than logs/")
    p = sub("ctestlist", "build")
    p.add_argument("--out-cpu")
    p.add_argument("--out-gpu")
    p.add_argument("--json-out")
    p = sub("parity", "dir", gates=False)
    p.add_argument("--names")
    p.add_argument("--label", default="")
    sub("pstatus", "dir")
    sub("targets", gates=False)
    sub("servetests", "file")
    p = sub("nodecheck", "serve_out", "node_check")
    p = sub("webpath")
    p.add_argument("--trees", nargs="+", default=[str(TREE["B"]), str(TREE["P"])])
    p.add_argument("--configs", nargs="*")
    p.add_argument("--tools", default=str(PAID_TOOLS))
    p = sub("paidcheck")
    p.add_argument("--tools", default=str(PAID_TOOLS))
    p.add_argument("--out")
    p = sub("render")
    p.add_argument("--spec", default=str(SPEC))
    p = sub("armenv", "exe", "config")
    p.add_argument("--arm", required=True, choices=("B", "P"))
    p.add_argument("--mock-env")
    sub("startline", "englog")
    sub("c2plan", "out", gates=False)
    sub("c4plan", "out", gates=False)
    p = sub("fixtures", "out", gates=False)
    p.add_argument("--tree", default=str(TREE["P"]))
    p.add_argument("--data", default=str(BPD))
    p.add_argument("--gguf", default=str(GGUF))
    p = sub("c2compare", "c2dir")
    p.add_argument("--gates-file")
    p = sub("c4judge", "c4dir")
    p.add_argument("--gates-file")
    sub("lost", "listfile", gates=False)
    sub("rules", "out", gates=False)
    p = sub("decide", "outdir", gates=False)
    p.add_argument("--sampled")
    p.add_argument("--quiet", action="store_true")
    sub("selftest", "scratch", gates=False)
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest(a.scratch)
    f = {"forms": cmd_forms, "arms": cmd_arms, "cfgcheck": cmd_cfgcheck, "ctestlist": cmd_ctestlist, "parity": cmd_parity,
         "pstatus": cmd_pstatus, "targets": cmd_targets, "servetests": cmd_servetests, "nodecheck": cmd_nodecheck, "webpath": cmd_webpath, "paidcheck": cmd_paidcheck, "render": cmd_render,
         "armenv": cmd_armenv, "startline": cmd_startline, "c2plan": cmd_c2plan, "c4plan": cmd_c4plan, "fixtures": cmd_fixtures,
         "c2compare": cmd_c2compare, "c4judge": cmd_c4judge, "lost": cmd_lost, "rules": cmd_rules, "decide": cmd_decide}[a.cmd]
    return f(a)


if __name__ == "__main__":
    sys.exit(main())
