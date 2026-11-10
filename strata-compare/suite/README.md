# Model test suite

One command runs the same fixed tests against any model endpoint, saves every answer, grades everything a script can
grade, and builds a blind side-by-side page for the visual tests.

```
suite/run.sh --label <name> --endpoint <url or claude:<model-id>> --mode quick|full
```

- `--endpoint http://127.0.0.1:8080`: any OpenAI-compatible server on 127.0.0.1 (Strata, llama.cpp's llama-server,
  vLLM ...). Other hosts are refused.
- `--endpoint claude:claude-opus-4-6`: a Claude model through the Anthropic API (see below).
- `--endpoint openrouter:qwen/qwen3.8-flash`: a model hosted on OpenRouter, one provider endpoint pinned for the whole
  run (see below); `openrouter:<model>@<endpoint slug>` picks the endpoint by hand.
- `--mode quick`: 1 run per item. `--mode full`: 3 runs per item (all local items are sampled). Claude runs use quick
  unless you ask for full.
- A run is resumable: run the same command again and it collects only the answers that are missing.

Results go to `suite/results/<label>/`:

| file | what |
|---|---|
| `answers/<category>/<item>.r<run>.json` | every answer: content, reasoning, tool calls, finish reason, cut-off flag, token counts (prompt / reasoning / answer), wall time, time to first token, tok/s, cost (Claude) |
| `grades.json` | the grade of every answer, with the reason |
| `scores.md`, `scores.json` | the scores table with 95 % intervals, tokens and wall time per solved item, per-item detail, the freshness answers |
| `visual/<item>.r<run>/` | the extracted SVG / HTML, screenshots, `render.json` (console errors, blocked requests) |
| `meta.json`, `run.log` | endpoint, settings, item fingerprint, timing, status, cost |
| `privacy.txt` | the privacy check of this folder |

Other commands:

```
suite/run.sh selftest                 # test every checker against known-good and known-bad answers (+ sandbox, renderer, stats)
suite/run.sh compare <A> <B>          # item-by-item comparison -> results/compare-A-vs-B.md, blind page results/blind-A-vs-B.html
suite/run.sh table [<label> ...]      # all labels side by side -> results/SCORES.md
suite/run.sh regrade <label>          # grade + render + report again from the saved answers (after a checker fix)
suite/run.sh estimate claude:<model>  # print the dollar estimate only
suite/run.sh privacy [<path> ...]     # privacy check (default: all results)
```

## What is in it

| category | items | graded by | score |
|---|---|---|---|
| coding | 25 Python problems: 5 easy, 10 medium, 10 hard (parsing, algorithms, data structures, 4 bug fixes, 2 refactors that must keep the given tests passing) | hidden unit tests in the sandbox | share of hidden tests passed, first answer only |
| agentic | 3 small repos with failing tests (inventory, text statistics, cron parser), tool loop read_file / write_file / run_tests, at most 15 steps of at most 65,536 output tokens each (32,768 before 2026-10-13; only Sonnet 5.5 reached that, its agentic items re-run) | original tests restored + hidden tests, in the sandbox | 1 if green; steps and tokens recorded |
| math | 20 competition-style problems, new or with changed numbers | final line `ANSWER: <integer>`; every answer recomputed by brute force in `items/math/verify.py` | correct |
| instruct | 20 prompts with script-checkable rules (word / sentence counts, banned letters, exact formats, JSON schema) | a checker per prompt | rule followed |
| tools | 10 prompts with real tool definitions sent through each API (3 of them have no fitting tool) | right tool, JSON-schema-valid arguments that match the request, no call when nothing fits | correct |
| longctx | two ~95K-token documents (`items/longctx/gen.py`), 3 questions each: five needles at once with near-miss distractors, counting mentions with look-alike distractors, tracking a value through relative updates and re-counts | JSON object / `ANSWER: <integer>` | needles: share found; others: correct |
| honesty | 15 questions about things that do not exist or cannot be known + 5 with real answers | `ANSWER: <answer>` or `ANSWER: UNKNOWN` | balanced: (unknowable right + answerable right) / 2 |
| freshness | stated training cutoff (the two questions about the best GPU and the best model for your hardware moved to research on 2026-10-12; older answers keep their record) | recorded only | never scored, never in totals |
| research | 7 questions whose answer depends on current information (best GPU now, best model for your hardware, best open-weights coding model that fits 96 GB RAM + 24 GB VRAM, latest Strata release, RTX 5090 price range, latest stable Linux kernel, Qwen4 Flash status), with web_search + fetch_page (the same loop for every model, at most 10 tool calls, one user turn) on the local SearXNG (127.0.0.1:8888) and a shared web cache | the editable key `items/research/key.json` (picks, fit in RAM + VRAM at the stated quant, hard facts; speed claims recorded, not scored) + your 1-5 rating on the blind page | checks passed / checks decided |
| visual | pelican on a bicycle (SVG), voxel pagoda (Three.js), 20 balls in a spinning heptagon, playable Tetris, plus an unpublished variant of each (flamingo on a unicycle juggling, voxel lighthouse at dusk, balls escaping a hexagon with a gap, pentomino Tetris with hold and ghost) | you, on the blind page | - |

Every auto-graded prompt states its machine-checkable format (an `ANSWER:` line, a JSON object, a fenced code block
defining a named function, or UNKNOWN). No model grades another model.

The total is the unweighted mean of the 8 scored categories (coding, agentic, math, instruction following, tool calls,
long context, honesty, research; research since 2026-10-12). Freshness and visual are not in it.

## Local models

Every request sends the sampling explicitly: temperature 1.0, top-p 0.95, top-k 20, min-p 0.05,
`reasoning_effort: "xhigh"`, and `max_tokens` 81,920 (fit to the context the server reports, so long-context items get
whatever the context leaves). An answer that stops at max_tokens is recorded as cut off and graded as it is.

Token counts: the server's usage gives the total; the reasoning / answer split comes from the API if it reports it,
else from the model's tokenizer (llama.cpp's `/tokenize`, or for a Strata server the pack tokenizer found through its
`/config`), else an estimate by characters (marked `estimate` in each answer).

### Another endpoint, e.g. llama.cpp serving another model

One model server at a time. Start the server on 127.0.0.1, then point the suite at it:

```
llama-server -m /path/to/model.gguf --host 127.0.0.1 --port 8090 -c 131072 --jinja -ngl 99 ...
suite/run.sh --label other-model-q4 --endpoint http://127.0.0.1:8090 --mode quick
```

- `--model <id>` if the server lists several models.
- `--ctx <n>` if `/v1/models` does not report the context.
- `--extra-body '<json>'` adds fields to every request, for servers that take the reasoning level another way, e.g.
  `--extra-body '{"chat_template_kwargs": {"reasoning_effort": "high"}}'`.
- `--tokenizer <dir>` (vocab.json, merges.txt, token_type.json) if the server has no `/tokenize`.
- `--max-tokens <n>` to change the per-answer cap.

## Claude models

```
suite/run.sh --label opus-4-5-quick --endpoint claude:claude-opus-4-5-20251101
```

- The key is read from `~/.config/model-suite/anthropic.key` and handed to the SDK client only. It is never printed,
  logged or written anywhere, and never put in an environment variable (`run.sh` also unsets `ANTHROPIC_API_KEY`).
  Without the file nothing is sent and the run stops with a message.
- Thinking / effort: the Models API is asked for the model's capabilities at the start of each run; the run uses
  adaptive thinking where supported (else extended thinking with the largest budget that leaves 16K for the answer)
  and the highest effort level the API reports (`max` > `xhigh` > `high` ...). Both are recorded in `meta.json`.
- Single-turn items go through the Message Batches API (half price), in chunks of 40. Long-context documents are
  prompt-cached: the first question writes the cache, the other two start once it streams. Agentic loops stream with
  automatic caching of the conversation.
- Cost: before the run, a dollar estimate is printed from the last local run's token counts and the published prices
  (`msuite/backend_anthropic.py`, `PRICES`). The run does not start if the estimate is above `--max-estimate`
  (default $25). During the run every response's reported usage is priced and added up; it stops at the hard limit
  (`--budget`, default $40). The actual cost is in `meta.json` and `scores.md`.

## Research with web search

- Runs only after `items/research/APPROVED` exists (you see the key first; approved 2026-10-12 with your changes).
- Tools: `msuite/web.py`, a copy of Strata's web tools (public http/https pages only, only URLs from the answer's
  own search results or the question; never 8889 / 8890). Cache `suite/webcache/`: every search result list and page
  (or error) is stored on first use and replayed; `CACHE.json` holds the start date, which the tools give the model
  as "today"; each answer records its hits and misses.
- Snapshot: the first model's research runs capture the web (`--web-capture`), then `run.sh webcache expand` stores
  every result page of the captured searches and `run.sh webcache freeze` freezes it. From then on every model
  replays the snapshot: a search not stored gets the closest stored search (the tool result says so), a page not
  stored is an error, nothing is fetched live. Research items run only on a frozen snapshot (or with
  `--web-capture`). `run.sh webcache status` shows its dates and size.
- Key: `items/research/key.json` (see its `_readme`). `suite/run.sh regrade <label>` re-scores after an edit.
- Ratings: on the blind page rate each research answer 1-5, "Copy my picks", save the JSON to a file, then
  `suite/run.sh ratings import <file>`; scores.md shows them beside the key score.

## OpenRouter models

```
suite/run.sh --label or-qwen3.8-flash-full --endpoint openrouter:qwen/qwen3.8-flash --mode full
```

- The key is read from `~/.config/model-suite/openrouter.key`, handled like the Anthropic key (only the API client
  reads it; never printed, logged, written or put in an environment variable). Without it nothing is sent.
- At the start of each run the suite reads OpenRouter's public model page data (name, Hugging Face id) and the
  model's provider endpoints (published precision, context, supported parameters, prices) and pins one endpoint:
  the highest published precision ("unknown" ranks lowest) among endpoints that take tools and reasoning, then the
  one that honours the most of the four sampling parameters. Requests carry `provider.order = provider.only =
  [slug]` and `allow_fallbacks: false`; every response's provider and model are recorded, and a response from any
  other provider stops the run.
- Sampling: temperature 1.0, top-p 0.95, top-k 20, min-p 0.05 are sent; which ones the pinned endpoint honours (its
  published `supported_parameters`) is recorded, and every scores table and comparison with a local run says which
  ones the provider ignores. Thinking: `reasoning.effort = "xhigh"` (OpenRouter's documented levels go up to xhigh /
  max; on budget-only providers xhigh is ~95 % of max_tokens). max_tokens 81,920 as for local runs.
- Cost: an estimate first (the last local run's tokens x the pinned endpoint's prices; `--estimate-from` picks the
  local run); the run does not start above the hard stop and stops at it (`--budget`, default $15); the actual cost
  is the sum of the `usage.cost` OpenRouter returns. Requests run 6 at a time (`--concurrency`); each open request
  reserves its worst case against the limit; 429 / 5xx / 529 are retried with back-off.

## API runs beside local runs

`work/suite/api_jobs.py` (started detached; log `logs/suite/api_jobs.log`) starts each provider's chain as soon as its
key file exists: Anthropic opus-4-5-quick -> sonnet-4-6-quick -> opus-4-6-quick; OpenRouter or-qwen3.8-flash-full ->
or-qwen3.8-27b-full -> or-qwen3.8-max-0902-quick; both chains at the same time. Each run first runs with
`--collect-only` (requests and saved answers only: no agentic items, no grading), so a local run's timings stay
clean; when no local run is going (it takes `tmp/suite/heavy.lock`, which `work/suite/local_chain.sh` holds for the
local runs) the same command runs again without it, which adds the agentic items and grades. No API run starts
while MemAvailable is under 20 GiB, except during the Q4 run (its own 6 GiB floor), when they only keep sending.
Stop it with `touch tmp/suite/api_jobs/STOP`; it ends by itself after 72 h or when every run is finished.

## Adding a test

Add the item, then run `suite/run.sh selftest`; every checker must accept its known-good answer and reject its
known-bad one. Changing any file under `items/` changes the items fingerprint shown in every scores table, so old and
new results are never silently compared.

- coding: a new `items/coding/cNN_name.py` with `LEVEL`, `KIND`, `ENTRY`, `PROMPT`, `GOOD`, `BAD`, then the line
  `# ==== HIDDEN TESTS ====` and `test_*` functions that take the solution module as their argument. Only the part
  after the marker is shipped into the sandbox.
- agentic: a folder `items/agentic/aN_name/` with `repo/` (code + `tests/`, failing), `hidden/test_hidden_*.py` and
  `fix/` (files that make it green).
- math: add the problem to `items/math/problems.json` and a brute-force function to `items/math/verify.py`.
- instruct: add a dict with `prompt`, `check`, `good`, `bad` to `items/instruct/items.py`.
- tools: add a dict with `tools`, `prompt`, `expect` (or `None` for "no call"), `good`, `bad` to `items/tools/items.py`.
- honesty: add a question to `items/honesty/items.json` (`kind`: `nonexistent`, `unknowable` or `real` with `answer`).
- longctx: edit `items/longctx/gen.py` and rerun it (`cd suite/items/longctx && python3 gen.py`).
- visual: add an entry to `items/visual/items.json` (`kind` svg or html, `shots` in seconds, `game` for key presses).

## Sandbox

Code a model writes (coding answers, agentic repos, visual pages) runs with bubblewrap: a throwaway folder under
`tmp/suite/sbx` mounted as `/work`, the system's `/usr` read-only, no `/home`, no network (own network namespace),
an empty environment, a wall-clock limit (the whole process group is killed), and limits on memory, CPU time, file
size and process count. The folder is deleted afterwards. Visual pages render in headless Chrome inside the same kind
of sandbox (no network at all); the page's files and local copies of the common browser libraries are served through
the DevTools protocol, every other request is refused and listed (Google Fonts included: pages fall back to local
fonts). The copies come from npm, each tarball checked against the registry's sha512 integrity: Three.js 0.128.0 /
0.160.0 / 0.186.1 in `suite/vendor/three`, and since 2026-10-14 (future runs only; earlier renders are unchanged) p5,
d3, GSAP, Chart.js, PixiJS, Phaser, Babylon.js, Plotly, matter-js, cannon(-es), Tone.js, lil-gui, dat.gui,
simplex-noise, tween.js, anime.js, jQuery, React 18 + Babel, Vue, Alpine, Tailwind (v4 browser build; the v3 Play CDN
script from cdn.tailwindcss.com, SHA-256 recorded), Font Awesome, howler, stats.js, Konva and Fabric in
`suite/vendor/npm` (list, versions and sources: `INDEX.json`, `SOURCE.txt`; refetch: `work/r20/vendor_libs.py`).
jsDelivr, unpkg, cdnjs, esm.sh, Skypack and jspm URLs map to them (a requested version that is not vendored gets the
newest vendored one of the same major, noted in the render log); a bare package URL is redirected to its entry file so
relative imports resolve. Not covered: packages that only exist as ES modules with bare imports (React 19, d3 as ES
modules), map tiles and fonts from the network.

## Statistics

- Category score: the mean over items of each item's mean over its runs (honesty weights its two halves equally).
- 95 % interval: Wilson for pass/fail with one run; otherwise a two-stage bootstrap (items, then runs within items),
  10,000 draws, never narrower than a Wilson interval over the items.
- `compare A B`: item by item on the shared items: the difference, a paired bootstrap interval, and a sign-flip
  permutation test. "within noise" means the interval contains 0 (or p >= 0.05). With 10-25 items per category only
  large differences are distinguishable; full mode (3 runs) narrows the intervals of sampled models.
- Tokens and wall time per solved item: all output tokens (wall seconds) spent in the category divided by the sum of
  item scores, so a model that thinks less can come out ahead even with the same score.

## Privacy

The suite stores only its own test prompts and the answers to them. `results/<label>/privacy.txt` is the check of each
run (API keys `sk-ant-...` / `sk-or-...`, home paths, user name, hostname, e-mail addresses other than the prompts'
fictional example.com ones, private-range or this machine's IP addresses, GPU UUIDs). The key files themselves are
read only by the API clients.
