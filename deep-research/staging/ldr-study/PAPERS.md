# Item 5, first half (B): how LDR misreads papers - traced, and the staged fixes

Written 2026-11-04 by the ldr-study helper. Staged only. The sources were our blind gradings (`results/bench2/blind-p7a/`,
`blind-p7c/`: SUMMARY, grades-o01, KEY) and our bench runs' own files (`results/bench2/runs/screen-deep-{p7a,p7c,p4s8}/o01/deep/`:
evidence.jsonl, report.md, lead_answer.md, consistency.json) plus the ldr-web logs. No model call, search or fetch was made.

## 1. Short answer

The PDFs were read correctly. In every traced case the paper's full text reached the store (45-80 k chars, under the
120 k cap). Where an agent fetched the paper, the right numbers or caveats were in at least one extraction. The errors
come from five steps after the fetch, and from one that runs before it:
1. **Subagent findings are thrown away** (a bug): every deep subagent that reaches its 23rd model call dies with
   LangGraph's GraphRecursionError, and its findings are replaced by "reached iteration limit". This hit **148 of 217
   subagents since 11-01**, in every LDR log since 10-19. In 7a o01 it hit the subagent that had read the KTransformers
   paper. The section writers then worked from raw quotes, without a reader's synthesis.
2. **The extraction cuts the qualifier off a quote, or misses the paper's setup** because it answers only the focus.
3. **The writers put their own derivations under the paper's name and drop qualifiers when shortening**, above all in
   the Answer and Key findings.
4. **A paper cited from search snippets only, mixed with another paper**: the fMoE case.
5. **Our checks catch these but nothing repairs them**: the consistency check flagged 4 of the 6 traced errors, with
   the correction. The marks stand inline, the graders' copy strips them, and the wrong sentence stays.

## 2. How a paper reaches the model (deep mode, as installed)

1. **Search:** a SearXNG result. The agent sees 300 chars of snippet; the store keeps the whole snippet. The same
   URL gets a new [N] in each search and each fetch (the KTransformers PDF had 12 in 7a o01).
2. **Fetch:** the agent calls `fetch_content(url, focus)` in summary_focus_query mode. `ContentFetcher` classifies the
   URL. For `arxiv.org/abs|pdf`, `ArxivDownloader` downloads **the PDF** (not the abs page), runs pypdf `extract_text`
   (plain mode, pages joined, no page marks), and prepends the API's title / authors / abstract plus "FULL PAPER TEXT".
   `arxiv.org/html` and publisher pages go through the HTML pipeline (trafilatura etc.); direct PDFs through pypdf.
   The text is cut at 120,000 chars (`fetch_max_chars`). 30 of 469 distinct paper pages in p4s8 / 7a / 7b / 7c were
   cut; the median paper is 58 k chars.
3. **Extraction:** one model call with `SUMMARY_FOCUS_QUERY_PROMPT` ("verbatim quotes" for the focus and the
   question, at most 4,000 chars). The agent gets "[N] Title, URL, quotes". The store keeps the page text, the
   extraction and item 5's claims (each quote checked against the page and dated).
4. **Reader (item 6):** pages that findings cite without having read them are fetched (text only), plus up to 2
   primary links per page.
5. **Subagent findings** (at most 16,000 chars to the lead) -> **lead answer** -> **report stage**: outline, sections
   written from the store (claims / extractions plus passages of read pages), the opening (Answer + Key findings,
   written from the sections), then the citation check, setup / version / arithmetic / consistency checks and the
   critic. Their output is inline marks plus check sections; blind-open.py drops both.

## 3. The traced errors

| # | wrong claim (grader) | what the run had | where it went wrong | pattern |
|---|---|---|---|---|
| P1 | 7a o01: "deferring 4 of 6 DeepSeek experts per layer (**the SOSP paper's own DeepSeek-V3 quantized default**)" and "**33 % single-layer**" | sub1 fetched SOSP25-chen.pdf twice (80,175 chars, whole). Its extraction (evidence L49) quotes it right: "for DS-3, we defer 3 experts in the BF16 model and 6 in the quantized model. For DS-2, we defer 4 ..."; "reduced single-layer execution time by 26%, and increased end-to-end decoding throughput by 33%". **sub1 then hit the 23-call limit; its findings were lost.** | Section 1's table applied the paper's "at least 2 immediate experts" heuristic to DeepSeek-V4.1's 6 experts ("would defer 4 of 6") and merged 26 % / 33 % into "33 % single-layer". The Answer then made the derived 4-of-6 "the paper's own DS-V3 quantized default". The Limitations call 3 the "DS-V3 Int4" default (3 is BF16) | derived number relabelled as the source's; two configurations mixed; two numbers merged |
| P2 | 7a o01: Expert Deferral and the AcceptMoE mask recommended without "changes the outputs" | KTransformers: the extraction and section 1 quote "accuracy drop of no more than 0.5 %". **AcceptMoE** (sub8, arXiv abs -> 44,973 chars): the extraction kept "across 12 model-task pairs ... 0.27 percentage points lower" and **cut off the sentence's first clause "Although constraining target-expert eligibility changes the model distribution,"** | The Answer / Key findings call deferral "the single most transplantable idea" with no lossy note. The action table marks AcceptMoE "Try next" | qualifier dropped by the extraction (AcceptMoE) and by the opening (deferral) |
| P3 | 7c o01 (the headline): fMoE "caches gate/up/down sub-tensors independently", so "splitting triples the 4060 Ti's slots" | **The fMoE paper (arXiv 2502.05370) was never fetched.** The lead searched "fMoE fine-grained expert offloading ... partial expert granularity" (its own idea in the query) and got 3 snippets: a lab page, slides, the GitHub README | The lead's answer (section 6) merged PreScope's AsyncIO, which it had read (three CUDA streams per gate / up / down), into fMoE's "fine-grained". The reader fetched the 3 secondary pages (1.6 k / 11 k / 3.3 k chars) after the answer; none states the claim, but the report counts them as read | paper cited from snippets; two papers merged; hypothesis-led query |
| P4 | 7c o01: SP-MoE "gains scale inversely with link speed (1.41x 3090, 1.32x 4090, 1.21x A100)" | Fetched (arXiv abs, 73,862 chars; html v2 65,104). The quote is right, and the paper's reason is "efficiency in resource-constrained settings". Its Table 2 lists every testbed at PCIe 4.0 x16. No extraction kept that table | The writer added the cause; the opening then turned it into a promise for the x4 link | the model's inference presented as the paper's finding; setup missing from the extraction |
| P5 | 7c o01 and p4s8 o01 (both rounds): DALI's "64-core EPYC" | 7c: three extractions of DALI. Only sub10's second (focus: baselines) has "we set the number of CPU cores to 16 and threads to 32 for all frameworks". p4s8: two extractions, neither has it. 7c also adds Apex's 512 GB box to DALI | Writers used "64 cores", the hardware line, against the experiments' cap | focus-only extraction misses the setup; two papers merged |
| P6 | 7c o01: "Specter / MoE-SpeQ (ASPLOS 2026)" heading | the body says 2027 | heading only | not traced further |

**Our checks saw most of it** (`consistency.json`). They found P1 ("the second holds ... 6, not 4", with the fix), P2
twice (deferral and AcceptMoE "should be lossy"), P4 ("observed only on x16 links") and P3's "no predictor" (the
critic also marked fMoE's headline "[Check: unsupported ...]"). Each became an inline mark plus a line in "Consistency
check". The sentences themselves stayed.

## 4. The systemic numbers (offline scans: `scratch/bin/scan_extractions.py`, `scratch/scan-extractions.json`; logs)

- **Subagents lost at 23 calls.** Deep subagents run with `recursion_limit = 2 x 30 + 10 = 70`. With
  DeepAgentMiddleware every round is **three** graph steps (its `before_model` hook is a node of its own, then the
  model, then the tools). So the graph stops at the **23rd** call, before the middleware's step-limit wrap-up (at call
  29) could make the subagent write its findings. Reproduced offline twice: a bare create_agent, and a test with the
  real middleware. Logs: since 11-01, 148 of 217 deep subagents ended "recursion_limit", **all at exactly 23 calls**.
  Runs: 7a o01 6 of 11 started subagents, 7c o01 9 of 16, p4s8 o01 13 of 17, whose 141 / 181 / 194 extractions reached
  the lead only as "reached iteration limit". This is not in NOTES or the backlog.
- **Quotes cut open.** 6,444 of 60,204 verbatim quote lines (10.7 %; 20 runs: p4s8, 7a, 7b, 7c, 7e) start inside a
  sentence. In 704 the cut-off words carry a qualifier. Real examples: "However, during the decoding stage, [the
  prefetching technique offers only modest benefits ...]"; "However, [the time required to copy activation ... is
  negligible ...]".
- **Non-verbatim "quotes".** 20,869 of 81,073 quote lines (25.7 %) are not on the page verbatim (16,178 partly). The
  claims check labels them, but the extraction text still reaches agents and writers.
- **PDF text quality is a minor cause.** pypdf lost word spaces on 1.5 % of PDF-derived pages (AcceptMoE 2.4 %:
  "insteadofpredictingnaturalroutes ..."). Tables come out as flat token runs (SP-MoE's "Env. 1 NVIDIA RTX 3090 24 GB
  ... 4.0 x 16"). pypdfium2 is installed in the venv and was 13x faster with clean spacing on Strata-Paper.pdf. Not
  staged: it touches research_library/downloaders/base.py, which no patch covers yet.

## 5. Staged fixes (not installed; both behind new LDR_DEEP_FIX items, off unless named, never part of "all")

**`patches/0008-subagent-steps.patch`, item "steps"** (the strategy and `deep/checks.py` ITEMS):
- `_deep_recursion_limit(calls) = 3 x calls + 10` for deep subagents and the lead. Without "steps" the old `2 x + 10`
  stays.
- `_deep_salvage`: if a subagent still hits the limit, the lead gets that subagent's own extractions from the store
  ("[N] title - url" plus quotes, at most 12 k chars) instead of the bare message.
- Tests: with the real middleware and a fake tool-calling model, the old limit stops at call 23 with no wrap-up; with
  "steps" the middleware wraps up and the subagent answers at call 30. The salvage returns only its own subagent's
  extractions.
- Expect longer subagents (30 calls instead of 23), so fewer waves fit the budget; it needs a bench A/B.

**`patches/0009-paper-quotes.patch`, item "papers"**: new `deep/quotes.py` plus `tools/fetch`, `deep/files.py`,
`deep/prompts.py`, `deep/report.py`, `deep/checks.py`.
- **Deterministic, no model call** (`quotes.improve`, applied to every extraction):
  - Each quote cut inside a sentence is extended to the whole page sentence (at most 400 chars back / 200 forward, at
    most +25 % of the cap).
  - For a paper (arXiv / DOI / proceedings host, a PDF, or abstract + references), up to 6 verbatim page sentences
    stating a caveat ("changes the model distribution", "accuracy drop", "lossy", "not exact") or the setup ("all
    experiments are conducted on ...", "we set the number of cores ...") are added under "(also on this page:)".
  - Both stay verbatim, so the claims check finds them exact. `LDR_DEEP_QUOTES=0` is a kill switch.
- **Prompt rules:**
  - Extraction (`EXTRACT_PAPER_RULES`): whole sentences; every number with its model, configuration and hardware; the
    page's own caveats and setup even when the focus did not ask.
  - Section writer (`FIX_SECTION_RULES`): a figure attributed to a source must be the one its quote states for that
    configuration; label your own applications of a source's rule as your own; keep the conditions; output-changing
    means not lossless.
  - Opening (`FIX_OPENING_RULES`): shortening keeps the qualifiers.
- **Offline replay of the deterministic part over 5,137 extractions from 20 runs** (`scratch/replay-quotes.json`):
  - 3,301 extractions changed; 5,121 quote starts and 8,570 ends completed; +10.0 % chars; notes on 271 of 501 paper
    pages; at most 24 ms per call.
  - AcceptMoE's "Although ... changes the model distribution" comes back.
  - DALI's p4s8 extraction gains "we set the number of CPU cores to 16 and threads to 32 for all frameworks" and the
    hardware line.
  - SP-MoE's extraction gains the three testbed rows, each "4.0 x 16".
  - These are tests 09-13 (real data). The prompt rules are not measured; they need the model.

**Tests:** `tests/run.sh` builds the patched copy and runs all 15 tests: 15 / 15 pass (`tests/test-output.txt`). Patch
checks: 0007 -> 0008 -> 0009 apply in order to copies of the installed files, reverse cleanly, and give exactly
`site/`. On a scratch copy of the whole package, after the three patches and a `make-patches.sh`-style regeneration,
apply.sh's state test answers "patched". The order is fixed: 0009's checks.py hunk sits on 0008's.

## 6. Designs, not staged as code

- **A repair pass (the biggest missing step).** After the consistency check and the critic, take each flagged
  sentence in the Answer / Key findings / action table whose pair is settled ("right": a | b) or whose critic fix is
  "fix". Make one short model call to rewrite only that sentence with the check's `fix` text, keeping its [N]
  citations, then replace it with `checks.Locator` (the code that places the marks today). Log a "Corrections" list.
  On 7a o01 this would have rewritten P1 and P2 (both deferral and AcceptMoE), using the fixes consistency.json already
  holds. Cost: at most about 12 calls x 15-30 s, from the report reserve (Fix 6's plan). It needs a model replay of the
  7a / 7c report stages first.
- **A paper behind a secondary page** (P3): when a cited non-primary page names a paper (title in its snippet or
  text) and the store has a search result for an arXiv / DOI / OpenReview URL with matching title words, the reader
  reads that URL too and links it as the primary source. The citation check then checks the claim against the paper.
- **A PDF text fallback:** if pypdf's text has 1 % or more glued words, use pypdfium2 (a new patch on
  `research_library/downloaders/base.py`; apply.sh FILES would gain the file).

## 7. What testing the prompt parts needs (GPU, Karl's call)

1. **Extraction replay:** the 5 traced extractions (P1, P2, P4, P5 x 2), old prompt vs "papers", from evidence.jsonl
   (focus, page text, question). About 10 calls, a few minutes on 8080.
2. **Report replay** of 7a o01 and 7c o01 with "papers" (sections + opening) against the same evidence.
3. **Then a bench A/B:** "steps", "papers" or both against the current arm on o01-o03 (171 min each), graded blind by
   wrong claims as before.

## 8. Install (only when Karl says so; no LDR run or Jan job live)

Apply 0007, 0008, 0009 in that order to the venv's site-packages (`patch -p1`, backups first), then run
`patches/ldr/make-patches.sh` (see MEMORY.md section 5). To switch the items on, add them to LDR_DEEP_FIX (for example
`all,read,claims,steps,papers`). run-ldr.sh stamps unknown items as "fix:steps,papers" in run/ldr.items, so it needs no
change, but the bench and runner stamps should list them. Nothing changes until the items are named, apart from 0007's
memory records and trims.
