# C3b + C3c groundwork - per-model profiles, sizes derived from the context (staged 10-29, NOT installed)

Backlog rows C3b and C3c (strata-compare/results/BACKLOG-1027.md), from results/AUDIT-FLASHNEXT-TUNING-1027.md plus
the sizes items 5 + 6 added since the audit (claims per source in a section, the reader's passages, the fetch quotas).

- **C3b:** one profile file per model. `profiles/flash-next.env` = exactly today's values. `profiles/sonnet-5-5.env`
  is a draft for C4, and every value in it is marked "draft, unmeasured".
- **C3c groundwork:** the sizes that fill a share of the context are now derived from `LDR_DEEP_CONTEXT_TOKENS`
  (alias `LDR_DEEP_CONTEXT`): `base * context // 131072`. At 131,072 that gives exactly today's values. Nothing was
  tried at a bigger context; that is the later GPU test.
- **No behaviour change with flash-next.env** (the default): the equivalence test passes 84 / 84 (below).

## How it works

`deep/modelprofile.py` (new, standard library only) is the one loader. It is used by the deep package
(`config()`), by run-ldr.sh (as a script) and by the research runner. Every setting resolves the same way:

1. An explicit environment variable wins, as before (bench2, the runner, the queue and tests set some per run).
2. Otherwise the profile's line is used.
3. Otherwise a ctx size is derived from the context, and anything else takes its built-in default (today's value).

`auto` or an empty number means "not given". Text values are different: an empty value is a value, so `""` means
"send no effort" or "use no tokenizer".

- **run-ldr.sh** reads `LDR_MODEL_PROFILE=<name or path>` (default `flash-next`, i.e. `profiles/flash-next.env`).
  It exports the profile's path to LDR as `LDR_DEEP_MODEL_PROFILE`. From the profile it takes the context window,
  max_tokens, temperature, workers, quick-mode cycles and tokenizer dir.
- **Startup checks:** run-ldr.sh refuses a missing or broken profile, and a `LDR_PROFILE_STATUS=draft` profile unless
  `LDR_ALLOW_DRAFT_PROFILE=1`.
- **New log lines:** the LDR log gets a `# model profile:` line, and `run/ldr.modelprofile` records the profile's name
  and content hash.
- **Show or check a profile:**
  `.venv/bin/python -I <pkg>/deep/modelprofile.py --show --profile flash-next` (each value and where it came from),
  `... --check profiles/*.env`.
- **Code tool:** `deep/codetool.py` stays loadable straight from its file (tools/code-mcp.py, Jan). Outside the package
  it reads the loader from the file next to it.

### In the profile (routed through the loader)

| group | settings (ctx = derived from the context) |
|---|---|
| context / output | context 131072, max_tokens 30000, report output cap 60000, report answer reserve 8192, report margin 1024, agent-call margin 512 |
| compaction | compact_at 56000 (ctx), keep_recent 6, recent share 0.35, summary-failure fallback 12000 (ctx) |
| what the lead / writers see | subagent return 16000 ch, snippets 300 ch, page to extraction 120000 ch, section evidence 48000, section findings 12000, outline lead answer 10000, citation-check passages 2000 per source per claim, batch 36000 tokens, old per-source check 40000, seed text 60000 ch, tried list 60000 / 100000 / 36000 ch (all ctx) |
| shares (not derived) | extraction 4000 ch, section extract share 0.6, outline findings share 0.40, 8 claims per citation-check call |
| items 5 + 6 | claims per source in a section 40 (ctx), reader passages 350 tokens (ctx), fetch quotas: 400 pages, 40 primaries, 2 links per page |
| tokenizer | dir, 8 tokens per message, 150 for the tool template, chars/3 without a tokenizer |
| effort | extract "", compact medium, report xhigh, verify xhigh, tried list low / medium, name map `LDR_DEEP_EFFORT_MAP`, ladder `lower` or `same` (API: same-effort retry after a pause); Jan's jobs `LDR_JOB_*_EFFORT` medium / medium / medium / xhigh (research runner) |
| pace | workers 1, steps 200 / 30, subtopics 8 / 12, subagent 3600 / 7200 s, fair share 0.75 and 60 s (strategy), time budget 10800 s, 120 checked claims, quick mode 12 cycles / 900 s |
| code tool | read lines 120, grep hits 40, tree 200, issue 3000 / comments 1500 / listing 600 ch (all ctx), line cut 240, `LDR_DEEP_CODE_SHORT_READS` (the "never whole files" wording; 0 = large-context wording) |
| sampling | temperature 1.0 |

### Kept global (not in the profile)

These are design choices or host settings, as the audit recommended:

- **Search:** SearXNG (50 results, general + science categories), bang hints.
- **Report prompt wording and fixed overheads:** report size rules, the 6000 / 2000 outline overheads, the 4000 / 1500
  opening overheads, the minimums (4096 output, 400 / 60 / 200 tokens).
- **Guard and compaction mechanics:** the 3000-token compaction prompt allowance, the re-compaction guard (20 % / 90 %),
  the context guard's 500 / 200.
- **List caps:** the critic (20 / 8), the dropped two-source verifier's 40 / 4 / 900 (its 36000 batch now follows
  verify_batch_tokens), the "not yet" check (off), list caps in seed / evidence / middleware, the claim quote cut
  (1200).
- **Host and API limits:** the code tool's clone size, time and API limits; the memory guards; the time-estimate texts
  in research-mcp.py.

## Files (diff against the installed copies, kept next to each as `*.orig`)

| file | changed lines | what |
|---|---|---|
| deep/modelprofile.py | new (393 lines) | the loader: specs (key, default, ctx), profile parser, `resolve()`, `--shell/--show/--json/--check` |
| deep/__init__.py | 94 | DeepConfig: same fields and defaults, 38 new fields (the old literals), `profile`, `profile_errors`; `load_config()` via the loader; `config_sources()` |
| deep/report.py | 31 | answer reserve / margin / 60K cap, outline lead cap and findings share, section findings and extract share, claims per source, reader passages, citation-check batch |
| deep/middleware.py | 10 | MARGIN, recent share, fallback size |
| deep/tokens.py | 14 | message / tool-template overheads, chars per token |
| deep/llm.py | 44 | effort name map, `same` ladder (default `lower` = unchanged) |
| deep/codetool.py | 59 | read sizes and issue text cuts from the loader (works standalone), tool descriptions formatted from them, wording switch |
| deep/reading.py, seed.py, tried.py, claims.py, advisory.py | 8 / 5 / 15 / 7 / 3 | fetch quotas, seed text, tried sizes and efforts, claims per source, verify2 batch |
| strategies/langgraph_agent_strategy.py | 5 | the fair-share 0.75 and the 60 s start floor |
| run-ldr.sh | 44 | `model_profile()`, the LDR_LLM_* exports from it, `LDR_DEEP_MODEL_PROFILE`, log line, run/ldr.modelprofile, status |
| tools/research-runner.py | 37 | DEEP_EFFORTS, DEEP_LDR_EFFORTS(_FILE), QUICK_CAP_S from the profile (missing file: today's values) |
| profiles/flash-next.env, sonnet-5-5.env | new | below |

## Installing

**When:** no LDR run, Jan research job, measurement or replay is live. That means after the running ldr-fixes-chain
(combined rerun + stage 3 p4s6) ends, since there are no LDR package edits until then.

**Steps:**

1. `staging/c3/install.sh --diff` (read-only) shows what would change. It also checks that every live file still equals
   its `.orig`; if one changed, re-stage that file.
2. `staging/c3/install.sh` refuses while any of these is live: LDR (run/ldr.pid), run/bench.lock, an active Jan job,
   the bench service, or a client or replay that imports the package.
3. It then reruns the equivalence test (`--skip-test` skips that) and copies the files, keeping `*.before-c3` backups.
4. It creates `profiles/`, compiles the files, test-imports the package, checks both profiles and regenerates
   patches/ldr.

LDR picks the change up at its next `run-ldr.sh restart`. The runner picks it up at its next restart; its values are
the same either way.

**Rollback:** copy the `*.before-c3` files back.

## Equivalence test - result 10-29: 84 / 84 pass (151 s, nice 19)

Run it with `.venv/bin/python -I -B staging/c3/tests/test_equivalence.py [--quick]`. It writes
`tests/results/results.{md,json}` and needs no model or services.

**How it works:**

- **Probes:** `tests/probe.py` imports one package per process: the installed one, or the staged deep/ first on the
  package path. It dumps every config field, the module constants and the code-tool descriptions.
- **Traces:** a fake model answers every call and records what it was sent. Each recorded call has the prompt hash and
  length plus max_tokens and effort. The traced code paths are:
  - the report stage in 3 modes: classic, items read+claims, and fixes all + items + critic + verify2 (22-33 calls);
  - compaction with a summary and with the failure fallback;
  - the per-call context guard;
  - the token counter, both exact BPE and chars/3;
  - the effort ladder, the seeded continuation, the tried list;
  - the code tool's grep / read / tree and its issue cuts.
- **Caps that bind:** the synthetic data is sized so the caps bind: the 60 % extraction share, the outline's lead cap,
  the 36K and 8-claim citation-check batches, and 171 claims on one source against the 40 cap.

**Results:**

- **Static checks:** both profiles parse with known keys only. flash-next.env resolves to the built-in defaults; the
  only difference is the tokenizer path, which run-ldr.sh exported before. Every `.orig` equals the live file. The
  strategy's only change is the two literals. codetool.py loads standalone with today's sizes.
- **run-ldr.sh:** the exported environment is identical except the new `LDR_DEEP_MODEL_PROFILE`, in 5 caller
  scenarios: default, bench2-like, Jan-like, baseline + quick limits, and no proxy. It refuses the draft and a missing
  profile.
- **Package:** config, constants and traces are identical in 7 scenarios:
  - no profile;
  - flash-next.env through run-ldr.sh (real tokenizer);
  - `LDR_DEEP_CONTEXT=131072`;
  - `LDR_DEEP_CONTEXT_TOKENS=131072`;
  - items read+claims;
  - bench2-like (fixes all + items, critic, verify2);
  - Jan-like.
- **Research runner:** identical with flash-next.env and with no profile file.
- **Negative controls (35):** a small change to each routed setting shows up in the traces or constants, not only in
  the config dump. So the identical results above are real, not blind spots.

**At 262,144 (shown, not asserted):** every ctx size doubles. Subagent return 32000, snippets 600, page 240000,
compaction 112000, section evidence 96000 and findings 24000, outline lead 20000, citation check 4000 / 72000,
claims 80, reader passages 700, code reads 240 lines / 80 hits / 400 entries. run-ldr.sh gives LDR a context window of
262144. A section prompt at 262K stays at roughly 96K + 24K + overhead, well under 262144 - 9216.

## sonnet-5-5.env (draft, unmeasured)

**Model facts** (Anthropic's model table cached 2026-10-06; not measured):

- 1M context and 128K output;
- effort low to max, default high;
- any non-default temperature is refused, so it stays 1.0;
- no local tokenizer: chars/3 counting, with wider margins (8192 / 16384) and a 500-token tool template.

**Derived values at 1M:** subagent return 122K ch, snippets 2288, code reads 915 lines.

**Capped for C4's $60 stop (paper numbers, not measured):**

| setting | capped to | auto value |
|---|---|---|
| compaction | 200K | 427K |
| page to extraction | 240K ch | 916K ch |
| section evidence | 150K | 366K |
| citation-check batch | 120K | 275K |

**Other draft values:**

- 4 workers;
- the `same` retry ladder;
- efforts: report high, verify high, extract low;
- the large-context code-tool wording;
- `LDR_PROMPT_CACHING=required`.

run-ldr.sh refuses the profile (it is a draft).

## Open / unresolved

1. **C4 needs an API launcher.** run-ldr.sh only talks to Strata: model discovery on 8080 and strata-proxy on 8090
   (Strata-only fields, the context-400 retry). LDR 1.10.7 sends `reasoning_effort`, while Anthropic takes
   `output_config.effort`. Prompt caching must be turned on in the client. The profile records these needs but nothing
   wires them yet.
2. **The agent's own effort for API models.** It is still set only through the proxy mode file: the runner's
   `LDR_JOB_AGENT_EFFORT`, plus bench2's and ldr-client's own choices, which are measurement tools and were not routed.
3. **Fix 6's time plan is still Flash-Next's** (checks.py `EST` seconds, 1200 / 35 tok/s). It should become profile
   settings once another model is measured; under Sonnet the report stage's plan would be off.
4. **Derived sizes scale linearly with no clamps.** At a context much smaller than 131K (with max_tokens 30K),
   compact_at could exceed the hard limit. The bigger sizes are unmeasured, which is C3c's GPU test.
5. **Small edge behaviours changed** (no current caller hits them):
   - an explicit `LDR_LLM_MAX_TOKENS` or `LDR_DEEP_TOKENIZER_DIR` from run-ldr.sh's caller now wins (it was
     overwritten before);
   - an invalid number falls back to the profile or default with a warning (before: `LDR_DEEP_READ_MAX=""` crashed on
     import);
   - `LDR_QUICK_MAX_ITERATIONS` and the other new keys can now be overridden.
6. **bench2 and the runner do not yet check `run/ldr.modelprofile`.** A profile switch would not trigger their LDR
   restart. Add that when a second profile is used for real.
7. **The runner reads its profile at start,** so it needs a restart after a profile edit.
