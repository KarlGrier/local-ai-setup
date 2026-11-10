# Sonnet 5.5: our LDR build vs stock LDR (planned 10-27; the LAST LDR item)

**Rescaled 10-27 (Karl: $100 a month in API credits):**
- **Question:** one only, **o03** (EU AI Act, 2026). It is the cleaner comparison: no code side and no attached files,
  so stock is not handicapped. The 10-24 question would favour our code tool by design.
- **Arms:** both. Prompt caching on, per-run caps, and a **total hard stop of $60** (both arms together, pilots
  included).
- **Order in the month:** the Opus 4.5 hard-set run comes first in November (its own $25 stop). If the month's credits
  don't cover both, this experiment moves to the next month.
- **Before it:** the per-model profile files (backlog C3b), so the Sonnet arm runs with a Sonnet profile. Otherwise it
  would be measuring Flash-Next limits.
- **Estimate for o03:**

| arm | at Flash-Next volumes, with caching | possible on a faster model |
|---|---|---|
| ours | ~$28 | up to ~$60 |
| stock | ~$5-12 | ~$5-12 |

- **Caps:** a $3 pilot of each arm first, to measure tokens per minute. Then ours capped at ~$40 and stock at ~$12;
  the guard stops everything at $60 in total.
- The design notes below (written for two questions) still hold for o03; the 10-24 question is dropped.

---


**When (Karl 10-27, corrected):** at the very end of the LDR work - after the six fixes, Phase 5 and items 5-8 (if Karl
does them) - and only after Karl's monthly API credits have reset (they are low until then). API only, no GPU; it can
run beside other work while nothing timed runs. The cost estimate below is redone from the prices of that day and sent
to Karl before anything starts; a hard stop is set.

## Design (Karl 10-27)
- **Model:** Claude Sonnet 5.5 (`claude-sonnet-5-5`) through the API with Karl's key, read from the key file only inside
  the program that sends the requests - never printed, logged, put in an environment variable or written into results.
- **Questions:**
  - the 10-24 DeepSeek-tuning question (results/bench2/codetool/question.txt; answer key K1-K7, code-reference check);
  - one general research question from the Phase 4 set that needs no code: **o03** (what changed in 2026 in the EU AI
    Act's obligations for GPAI and high-risk providers, Digital Omnibus, what applies in October 2026). It has no
    attached files and no code side, so stock is not handicapped.
- **Arms:**
  - (a) our build with the six fixes, the code tool on;
  - (b) stock LDR 1.10.7 (the version our build is based on) at its own defaults apart from the model and search, in
    its own install (a separate venv from the pinned wheel, its own data folder and port), so our build and the
    bench locks are untouched.
  - Both search SearXNG only (8889, no paid fallback) with the same time budget.
- **Grading:**
  - the usual blind A/B, a fresh grader per question;
  - then the answer key (10-24 question), the code-reference check (coderefs-check.py) and the citation check. Stock
    keeps no evidence store, so the cited pages of both arms are fetched once at grading time and checked the same
    way, on the local model (no API cost);
  - our earlier Flash-Next reports on the same questions are reported as a reference point: the code-tool rerun and
    the six-fix rerun for the 10-24 question, and the Phase 4 / Phase 5 runs for o03.

## Cost estimate (10-27; to be redone at the start)
Prices (Anthropic first-party, as cached 2026-10-06): Sonnet 5.5 $2 per million input tokens, $10 per million output;
prompt-cache writes ~1.25x input (~$2.50/M), cache reads $0.20/M; 1M context, 128K output.

Token use measured on Flash-Next (our call logs):

| run | calls | input tokens | output tokens | wall |
|---|---|---|---|---|
| ours, 10-24 question (code tool + setup + critic, 4 h budget) | 992 | 26.8 M (agent loops 18.1 M) | 1.89 M | 291 min |
| ours, o03 (Phase 4 stage 3) | 704 | 15.1 M | 1.13 M | 172 min |
| stock (baseline profile), open questions | 132-318 | 2.2-4.9 M | 0.07-0.21 M | 13-37 min |

At those volumes:

| arm | no prompt caching | caching on our agent loops |
|---|---|---|
| ours, 10-24 question | ~$72 | ~$45 |
| ours, o03 | ~$41 | ~$28 |
| stock, each question | ~$5-12 | - |
| **all four runs** | **~$130** | **~$95** |

**The main risk:** Sonnet is several times faster than Flash-Next, so with the same time budget our build can make 2-3x
more calls before its step caps stop it (stock stops on its own small caps long before the budget). That could put
our arm at ~$150-200 per run.

So:
1. A 15-minute pilot of each arm at a $5 cap first, to measure tokens per minute on Sonnet.
2. Then per-run caps: about $60 for ours and $15 for stock, with a total hard stop around $150, or Karl's figure.

## To build before it (code only)
- **Karl 10-29: prompt caching ON in every API call of this experiment** (both arms: the agent loops, the report
  stage and the checks; cache_control on the stable prefix - system prompt, tools, task - and the growing transcript).
  Credits confirmed 10-29 ($130.15 available).
- **Anthropic in our build:**
  - map our reasoning-effort setting to the API's effort (adaptive thinking; Sonnet 5.5 rejects disabled thinking);
  - prompt caching on the agent loops;
  - context and compaction settings for a 1M-context model (see the Flash-Next tuning audit,
    ~/ai/deep-research/results/AUDIT-FLASHNEXT-TUNING-1027.md, for what is tuned to Flash-Next).
- **A local budget guard (127.0.0.1)** in front of the API for both arms:
  - it reads the key from the file, adds it to each request, and counts every response's reported usage;
  - it refuses new requests once a cap is reached;
  - it logs costs, never the key.
- **The stock install** and its launcher; a pre-flight check that it never touches run/bench.lock or the main LDR.

## Karl 10-29: a third arm - the Claude web app (no change to anything now; for when the experiment runs)
- **Arm (c), web chat:** Karl runs the same question (the frozen o03 text, word for word) in the Claude web app with
  Sonnet 5.5 and Research / web search on, and saves the report. No API credits (his subscription).
- **For Karl when it runs:** use the exact question text from questions-screen.jsonl (o03), run it on the same day as the
  two API arms (o03 is "as of" a date), and save the full report with its sources and links (Markdown copy with links, or
  a PDF) to ~/ai/deep-research/results/bench2/sonnet55/webchat-o03.md (or .pdf). Nothing of his other chats is read.
- **Grading, all three arms the same way:** blind-open.py packets A/B/C in one round, one fresh grader, the reference
  checklist (my-research/o03-eu-ai-act.md) as the key, the wrong-claims count, and the citation check on every arm.
  - The web report's citation style is converted to the packets' common "[n] title - URL" source list first, and its
    app-specific wording (e.g. "Research completed", tool notes) taken out, so the grader cannot tell the arms apart.
  - The citation check needs the cited pages: for the web arm they are fetched from its links (SearXNG-era fetcher, no
    paid search), the same checker as the LDR arms.
- Reference point as before: our Flash-Next o03 reports.

## Karl 10-29: the adapter's settings (staging/c4)
1. Stock-LDR arm effort: high, the same as our arm (harnesses compared at matched settings).
2. Report-stage reserve: ~20-25 % of each run's cap kept for the report stage; research spending stops when the rest is
   used.
3. No prompt caching on one-shot calls; cache only prefixes reused within a run (system prompts, the lead's and the
   agents' growing context).
4. Cache lifetime 5 minutes by default; 1 hour only for the lead agent's prefix, and only if the $3 pilots show gaps of
   more than 5 minutes between its calls.
- Karl 10-29: our arm's extraction step stays at effort low (our harness's design); strict matching covers the shared
  roles only (lead, agents, writer: high on both arms). **Note this in the experiment report.**
