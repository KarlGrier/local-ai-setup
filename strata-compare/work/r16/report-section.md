
## Round 16 — catch-up to v0.1.41: the port, v0.1.41's CPU prompt-read share (kept off), C\*16 promoted for the server fixes, a Q4 speed check (2026-10-08 14:05 → 23:10)

Chronological notes: `NOTES.md` ("ROUND 16"). Phone summary: `results/round16-summary.md`. Scripts: `work/r16/`; runbook runs
`bringup/out/r16` (the release alone, upstream's defaults), `r16z` (the port's gates, the share off), `r16q4` (the Q4 build).
Raw results: `results/r16/`, `results/runs.jsonl`. Branches (local): r16-port (= patches/r16p27), r16-meas (+ r16-meas27).
Configs: `configs/Cstar16.json` (+ `Cstar16-single`, `R16RT`, `BR16`), `configs/r16-q4.json`. Ledger: `patches/LEDGER.md`
(C\*16; C\*15's is `LEDGER-r15.md`).

### Result

* **C\*16 = Strata v0.1.41 + our 27 patches is on 8080** (promoted 22:24). It computes exactly what C\*15 computes (exact7
  7/7 = C\*15's hashes) at the same speed: **LDR +0.4 %, decode −1.4 %, full +0.5 %, prompts 0.4–0.8 % faster** (A B B A).
  Not ≥ 1 % faster; promoted under your rule because **it carries v0.1.41's server fixes that reach your Open WebUI → 8080
  path**: a frozen engine is ended and restarted (#1317 part 2), malformed / oversized request bodies are answered 400 / 413,
  and `<function= NAME>` tool calls are parsed. Every gate, the acceptance suite (11 pass / 0 fail), a 2-hour soak (439
  requests, 0 errors) and a real rollback test passed. Rollback: stop 8080, `STRATA_CONFIG=configs/Cstar15.json ./switch-model.sh strata`.
* **The 2–3 % gap to C\*14 has not closed** (C\*16 vs C\*14: LDR −2.4 %, decode −3.5 %, full −1.7 %; ms per verify round
  +2.7…3.5 %).
* **v0.1.41's new CPU prompt-read share is ON by default on your two-card config.** It reads short prompts and every chat
  turn's new text 16–17 % faster (512 tokens: 581 vs 694 ms). It passed the long-text NLL check, but it reads those prompts
  with timing-dependent rounding, so it failed the acceptance suite's chat-cache round trip (1/3), and it's **off in C\*16
  (`STRATA_PREFILL_CPU_SHARE=0`) by your rule.** `STRATA_STAGE_PIN` stays off (opt-in in v0.1.41).
* **Q4 check (UD-Q4_K_XL, the 5080 + 66 GiB RAM, your 6 GiB floor): 68.7 tok/s on the decode screen, 64.0 on LDR (about half of
  IQ3_S's 138.8 / 138.3), 32K prompt in 11.7 s (7.7), 120K in 34.4 s (29.7), needle at 120K 6/6.** Saved as
  configs/r16-q4.json; not promoted.
* Upstream released nothing newer during the round (v0.1.41 = main all day). Nothing was fetched or downloaded.

**Display: the monitor is on the motherboard output (the AMD iGPU) for the whole round, as in Round 15** (your message;
sysfs lists no connected output on any card, Xorg holds 4 MiB on each NVIDIA card). Nothing about the display was changed.

### Before the first test

* **48-hour monitor of C\*15 stopped** (logs/r15/uptime-c15/): 11:24 → 14:04, 11 samples, health ok 11/11, idle 11/11, **no
  requests of yours**, engine RSS 51,812 MiB flat, MemAvailable 36.7–36.8 GiB.
* **Base = v0.1.41** (fb58e0db, tree b5a210b6; 151 commits after v0.1.40.2, v0.1.40.3 and v0.1.40.4 included). `git ls-remote`
  at the start: v0.1.41 is the newest tag (no v0.1.41.x) and main's head; the local mirror already had it, so nothing was
  fetched.
* **Round 15's release slip, fixed:** the waiter looked only at the first NEW-RELEASE flag (already marked seen), so later
  flags never woke it. It now checks every flag (tested with a fake one). The release watcher ran all round
  (logs/r16/tagwatch.log).

### The port (the runbook) — 27 → 27 commits

| | outcome on v0.1.41 |
|---|---|
| the ledger pass | **all 27 rows apply by cherry-pick; one conflict**: row 18 (#567's prompt encoder) adds `tools/test_strata_tokenizer.py`, and v0.1.41 added its own file of that name (tests of its new tokenizer piece cache) → one file with both test sets. `strata_tokenizer.py` merged by itself (upstream's piece cache in `_encode_plain`, our resume marks in `_encode_matching`). Upstream merged none of our transplants (#652, #567, #619 still open): nothing dropped, nothing added |
| where both sides changed the same files | read by hand: upstream's HC-norm scratch change sits in its own split norm (our B.1 read replaces that read when on); the three q8_1 sites #606 / #1448 clamped are not in our series (B.1 writes no QFUSE image; A.2 writes Q8_K as ggml does) |
| the release alone, upstream's defaults | exact7 3/7 = v0.1.40.2's stock, not repeatable (the CPU share, step 1) |
| **the release alone, `STRATA_PREFILL_CPU_SHARE=0`** | **exact7 7/7 = v0.1.40.2's stock; repeats itself 7/7** |
| patched, every switch off (share off) | **= the release 7/7**; `strata patch guards: 5 checked, 0 off` |
| every switch's gate (share off) | **ALL PASS with Round 14/15's values to the digit**: B.2 TF −0.0008 / −0.0006, exact sampling chi-square ALL PASS, side mixer pair identical (= C\*15's hashes), A.2 pair identical, B.1 TF +0.0008 / −0.0026 (bound 0.005), cost gate chi-square ALL PASS |
| server tests | 598 (593 upstream + 5 ours), **1 failure in upstream's own test** `test_vision_device` (in the stock tree too): v0.1.41 orders a `"gpu"` list's cards faster-last for an auto layer split, and on this PC the 5080 is faster, so the test's expected "0,1" comes out "1,0". It does not touch your config (it sets CUDA_VISIBLE_DEVICES itself and uses a helper cache, not a layer split) |
| time | 14:07 → 14:55 (48 min): the ledger pass ~10 min by hand beside the queue; the release alone twice, the clean clone and its gates unattended |

### Step 1 — every default changed since v0.1.40.2, and the CPU prompt-read share

The full list: results/r16/v041-defaults.md. No existing engine option changed its default. On by default here:

| change | here | effect on your server |
|---|---|---|
| **CPU prompt-read share** (`STRATA_PREFILL_CPU_SHARE` unset = `auto` for prompt chunks below 1,024 tokens; CUDA, no layer split, no batch slots) | **ON for your served two-card config** — the rule tests for a layer split, not for the helper cache; the engine logs "the CPU share is ON by default for prompt chunks below 1024 tokens" | short prompts and every chat turn's new text (read as a short chunk after the cached conversation) |
| stage buffers pinned (`STRATA_STAGE_PIN`) | **off** (made opt-in by v0.1.41's last commit after upstream's gate saw IQ3_S decode corrupted after a long prompt); kept off | none (the file tier only) |
| file tier: batched direct reads (`STRATA_STAGER_BATCH` 8), the mapping closed under direct reads, the stager's RAM profile when the GGUF is cached (#1353), the watchdog's I/O allowance (#1407) | only when experts come from the SSD | none on IQ3_S |
| q8_1 emit sites clamped (#606, #1448), HC norm products kept in scratch, tokenizer piece cache, F4's rows table per architecture (sm_120 / sm_89 keep v0.1.40.2's table), the drafter's router guard (this model is 512 / 10) | always | outputs unchanged here (below) |
| server: frozen-engine watchdog (#1317 part 2, 90 s), malformed / oversized bodies answered 400 / 413, `<function= NAME>` tool calls parsed, listen backlog 256 | on | **yes** (the fixes that reach your server) |

**The release alone, your flags:** with upstream's defaults exact7 is 3/7 equal to v0.1.40.2's stock (the three long
prompts equal, the four short ones differ) and does **not** repeat itself (3/7) — the share's `auto` mode picks the layers
that share by measured time, so a short prompt's rounding depends on timing. **With `STRATA_PREFILL_CPU_SHARE=0` v0.1.41
computes exactly what v0.1.40.2 computed (7/7) and repeats itself 7/7**: the share is the release's only output change on
this file and config.

**The share on vs off** (C\*16, served, A B B A with A = on; fresh guarded servers, the 9.5K + two ~600-token warm-ups, then 6
prompts of 513 and 6 of 1,001 rendered tokens each arm, each a different text, 64 tokens; results/r16/s1-share.md):

| prompt | share on: TTFT (arm a / b) | share off | C\*15 (v0.1.40.2, reference) | on vs off |
|---|---|---|---|---|
| 512 tokens | **581 ms** (573 / 588) | 694 ms (693 / 695) | 692 ms (691 / 693) | **−16.3 %** |
| 1,000 tokens | **717 ms** (714 / 720) | 861 ms (862 / 861) | 864 ms (863 / 864) | **−16.7 %** |

(engine's own read time: 550 vs 663 ms and 689 vs 834 ms; C\*16 with the share off reads short prompts exactly as fast as
C\*15.) ≥ 3 % → the share had to pass the long-text NLL check and the acceptance suite.

**The long-text NLL check** (teacher-forced NLL through the twin, share on vs off, A B B A; results/r16/s1-tflong2.md,
s1-tfctl.md). The harness's own long prompts never leave a chunk below 1,024 tokens (they are 4,096-multiples) and the
forced text goes through the verify windows, so it would not have touched the share: I cut each of the 6 long texts' prompts
to N x 16,384 + 700 tokens (last chunk 700, read through the share) and forced the 1,536 tokens that follow the cut.

| | share on vs off | B.1 off vs on (control) | B.2 off vs on (control) |
|---|---|---|---|
| short texts (math, corpus; their prompts read wholly through the share) | −0.0017 … +0.0015 nats | −0.0012 / +0.0001 | +0.0001 / +0.0019 |
| 6 long texts: mean change of mean NLL | **−0.010** (12 runs; ≈ 1 se) | −0.003 | −0.022 |
| 6 long texts: mean \|change\| per text | 0.076 | 0.075 | 0.098 |
| per token, mean \|d\| (long texts) | 0.27–0.83 | 0.30–0.82 | 0.27–0.84 |
| repeats itself | no (two "on" runs up to 0.18 apart) | yes | yes |

The long texts move a lot per token under **any** rounding change — two known rounding-level switches (B.1 and B.2, both
passing their gates) move them exactly as much as the share does; llama.cpp moves ~0.11 nats per long text between identical
runs (Round 14). So the short-text gates' 0.005-nats bound cannot be applied per long text, and the check is: no bias, and a
spread no larger than a known rounding change → **PASS**. (My first version of this check, results/r16/s1-tflong.md, forced
text that no longer continued its cut prompt; it showed the same picture at higher NLL.)

**The acceptance suite with the share on** (C\*16 + the share, results/r16/accept-c16-share-on.md): **10 pass, 1 FAIL** — the
chat-cache round trip, 1/3 identical. The cause is the share, not the cache: two identical *direct* builds of the test chat
already differ (31 argmax changes, different GDN / KV state hashes), because the chat's 96-token follow-up read (5,822
tokens, 5,726 reused) goes through the share; parked → resumed vs direct differs by the same amount; the edit case (a
3,247-token read, no short chunk) is identical. With the share off the same round trips are identical in all three cases
(step 3). Every other row passed (TF short 0.2904 / 0.3852, long within 2 se, needles 36/36, samplers, stops, tool calls,
splits, control text).

**Decision (your rule: keep it only if it passes the acceptance suite and the long-text NLL check and is ≥ 3 % faster):**
16–17 % faster ✓, long-text NLL ✓, acceptance suite ✗ → **`STRATA_PREFILL_CPU_SHARE=0` in C\*16.** What you give up: ~0.11
s on a 512-token prompt and ~0.14 s on a 1,000-token one, and on each chat turn's new text. What you keep: every output
repeats itself, and a parked chat resumes bit-identically. `STRATA_STAGE_PIN` stays off (unset = off in v0.1.41).

### Step 2 — C\*16 (v0.1.41 + 27 patches, share off) vs C\*15, and the gap to C\*14

A B C C B A (A = C\*15 as served, B = C\*16, C = C\*14 for the gap question), each arm a fresh guarded server, your config
and sampling, the 20 GB floor; per arm the LDR screen, the decode screen, the full screen and a TTFT screen (8K, 32K x2,
120K; the full screen adds 32K, 64K and 120K) — results/r16/s2-*-c16-vs-{c15,c14}.md.

| | C\*15 | **C\*16** | C\*16 vs C\*15 | C\*14 | C\*16 vs C\*14 |
|---|---|---|---|---|---|
| LDR screen, decode tok/s (arms) | 137.8 (137.5 / 138.2) | **138.4** (139.4 / 137.3) | **+0.4 %** | 141.8 (143.1 / 140.5) | −2.4 % |
| decode screen, tok/s | 140.8 (139.6 / 141.9) | **138.8** (139.5 / 138.0) | **−1.4 %** | 143.8 (144.8 / 142.8) | −3.5 % |
| full screen, decode tok/s | 141.7 (142.9 / 140.5) | **142.3** (142.9 / 141.7) | **+0.5 %** | 144.8 (146.8 / 142.7) | −1.7 % |
| ms per verify round (LDR / decode / full) | 18.08 / 16.65 / 16.35 | 18.11 / 16.77 / 16.51 | +0.2 / +0.7 / +0.9 % | 17.57 / 16.21 / 16.08 | +3.1 / +3.5 / +2.7 % |
| time to first token 8K (n = 2) | 2.20 s | **2.19 s** | −0.4 % | 2.20 s | −0.4 % |
| 32K (n = 6) | 7.73 s | **7.69 s** | −0.6 % | 7.74 s | −0.7 % |
| 64K (n = 2) | 15.54 s | **15.41 s** | −0.8 % | 15.54 s | −0.8 % |
| 120K (n = 4) | 29.90 s | **29.74 s** | −0.6 % | 29.91 s | −0.6 % |
| acceptance (LDR) | 0.699 | 0.696 | | 0.697 | |

* **C\*16 computes what C\*15 computes and runs at the same speed:** decode −1.4 … +0.5 % across the three screens (the arms
  of one build spread up to 1.6 %), ms per verify round +0.2 … +0.9 %, prompt reads 0.4–0.8 % faster. Not ≥ 1 % faster.
* **The 2–3 % gap to C\*14 has not closed:** C\*16 is 1.7–3.5 % behind C\*14, ms per verify round +2.7 … +3.5 % — Round 15's
  picture (C\*15 vs C\*14 in this session: −2.8 / −2.1 / −2.1 %). v0.1.41 changed nothing that brings it back.

### Step 3 — the promotion decision

**Rule: promote only if ≥ 1 % faster or carrying a fix that reaches your server.** C\*16 is not ≥ 1 % faster (step 2:
−1.4 … +0.5 %), but it carries v0.1.41's server fixes on your Open WebUI → 8080 path (the frozen-engine watchdog, the
malformed / oversized body answers, the `<function= NAME>` tool-call parse) → **promote, after every gate.**

**Gates** (results/r16/s3-gates-c16.txt; C\*16 as it will serve: the share off):

| gate | C\*16 | C\*15 (Round 15) |
|---|---|---|
| exact7 vs C\*15's hashes | **7/7 identical** (twice) | 7/7 = C\*14's |
| needles 32K / 64K / 120K | 12 × 6/6 (TTFT 7.6–7.8 / 15.3 / 29.7–29.8 s) | 12 × 6/6 |
| Stop during a 120K read | all PASS (closed 20.1 s; read cancelled at 98,304 of 122,881; chat A back from the cache in 0.34 s; same engine) | all PASS |
| #652 follow-ups | plain 14/14, think 4/5 | 13/14, 4/5 |
| stop strings | ALL PASS | ALL PASS |
| tool-tag probe (by its sentence) | 3/6, every call parsed | 4/6, every call parsed |
| #931 control text: copy / forged / plain | 20/20 / 0/30 / 0/30 | 20/20 / 0/30 / 0/30 |
| repeat (adaptive tier live) | 3/3 | 3/3 |
| chat-cache round trips | identical in all three cases | identical |
| browser (config copy BR16) | 41 pass / 2 fail (C\*15's and C\*14's same two) | 41 / 2 |
| **acceptance suite vs llama.cpp** | **11 pass / 0 fail** (TF short = C\*15's to the digit, long within 2 se, needles 36/36, round trips 3/3, chi-square ALL PASS, stops, tool calls 6/6, 0 / 4,235 splits) | 11 / 0 |

**Soak (C\*16 on 8080, 20:20–22:20; logs/r16/s3-soak.log): 439 requests, 0 errors**, 158 Stops; back to a big chat (kept)
median 0.61 s (max 1.20 s; C\*15: 0.74 / 1.56 s); 12 chats the cache had dropped were read again (median 6.5 s); MemAvailable
min 22.2 GB; engine RSS 50.5–64.5 GB with no trend; swap ≤ 1.5 GiB. **Soaked decode 141.0 vs fresh 138.8 tok/s (+1.6 %)**
(results/r16/s3-soaked-vs-fresh.md).

**Promoted 22:24** (work/r16/promote-c16.sh; old launchers in work/r16/*.before-c16-promotion) after `git ls-remote` showed
nothing newer than v0.1.41. **Rollback test: 8080 → C\*15 (94e79d9b, answered, 18 s) → the default C\*16 (f7b1ea34,
answered, 18 s).** A 48-hour passive monitor watches C\*16 (logs/r16/uptime-c16/).

### The Q4 check (1 hour at most, not promoted; results/r16/q4.md, configs/r16-q4.json)

UD-Q4_K_XL on the step-3 build's tree (v0.1.41 + our 27 patches, built with the K-quant prompt kernels the file needs) and
C\*16's flags: **the 5080 + a 66 GiB RAM budget** — that holds every expert the 5080 does not (21,925 experts, 64.00 GiB
page-locked; 2,651 in the 5080's cache), with MemAvailable ≥ 12.9 GiB through the run (your floor: 6). A larger budget
cannot hold more: in budget mode the RAM copy has no room for the experts of the 2,225 cache slots a 16K prompt chunk
borrows, so **prompt reads take those from the SSD** (the engine's own warning) → `STRATA_UNBUFFERED_LOAD=1` by your rule
(my first start was buffered; I restarted it after one minute). Chat cache 2 GiB, `STRATA_STAGE_PIN=0`, the share off.
One session: the decode screen's items, the LDR screen, 32K and 120K prompts, the 120K needle document once.

| | IQ3_S, C\*16 as served (both GPUs; step 2, two arms) | **UD-Q4_K_XL** (the 5080 + 66 GiB RAM) | Q4 vs IQ3_S |
|---|---|---|---|
| decode screen, tok/s | 138.8 | **68.7** | −51 % |
| LDR screen, tok/s | 138.3 | **64.0** | −54 % |
| ms per verify round (decode / LDR) | 16.8 / 18.1 | 33.9 / 38.5 | ×2.0 / ×2.1 |
| tokens per round, acceptance (decode) | 2.33, 0.668 | 2.33, 0.668 | equal |
| time to first token 32K | 7.69 s | **11.66 s** | +52 % |
| time to first token 120K | 29.74 s | **34.35 s** | +15 % |
| needle at 120K | 6/6 (4 runs in the gates) | **6/6** | |
| RAM / VRAM | engine RSS 51.8 GB fresh (50.5–64.5 GB in the soak), both GPUs | engine RSS up to 74.8 GiB (64 GiB page-locked), MemAvailable min 12.9 GiB; one GPU, 5080 ≥ 440 MiB free | |

Every verify round costs about twice as long while drafting is unchanged (same tokens per round, same acceptance). I did
not split the round by phase in this hour; the likely reasons are one GPU instead of two and ~1.5x the expert bytes
(71.7 vs 46.8 GiB) for the CPU pool and the PCIe link. Round 10's Q4 result ("decodes at
half speed") still holds on v0.1.41 with every expert in RAM. Round 15 measured the quality side: UD-Q4_K_XL reads long
documents better (long-text NLL −0.21 ± 0.08 nats vs IQ3_S), equal on short texts.

### What changed upstream that matters (v0.1.40.2 → v0.1.41, 151 commits; full list results/r16/v041-defaults.md)

1. **The CPU prompt-read share is on by default — also on your two-card config** (its rule excludes only a layer split,
   batch slots and HIP; the helper cache is not a layer split). It reads short prompt chunks (below 1,024 tokens: short
   prompts, and every chat turn's new text after the cached conversation) 16–17 % faster here, but its `auto` mode picks the
   sharing layers by measured time, so those reads round differently run to run. **C\*16 turns it off** (step 1: it failed the
   acceptance suite's round-trip row); with it off v0.1.41 computes exactly what v0.1.40.2 did.
2. **Server fixes that reach your Open WebUI → 8080 path:** a frozen engine (no output, no CPU, no disk I/O for 90 s, GPU not
   busy) is ended and restarted by the next request (#1317 part 2; psutil is in the venv); a malformed request body gets a 400
   and an oversized one a 413 before it is read (a huge Content-Length used to be read until the client gave up); a tool call
   the model writes as `<function= NAME>` is parsed (it used to be kept as text inside the thinking, or reach the client under
   the name " NAME"); listen backlog 256.
3. **Pinned stage buffers (`STRATA_STAGE_PIN`) are opt-in** — upstream's own release gate found IQ3_S decode corrupted after a
   long prompt with them on. Off here (unset = off); they only act when experts are read from the files.
4. **File-tier work** (batched direct reads in the prompt path's stager, the mapping closed under direct reads, a RAM
   profile when the GGUF is cached, the watchdog's I/O allowance): only when experts come from the SSD — not on IQ3_S, and
   not in the Q4 check below (its 66 GiB budget held every expert).
5. **Numerically silent here:** the q8_1 clamps (#606 / #1448) change only blocks whose scale overflows; the HC-norm
   scratch change is bitwise by upstream's note; the tokenizer piece cache gives the same ids; F4's per-architecture table
   keeps v0.1.40.2's rows on the 5080 and the 4060 Ti; the drafter's router guard matches this model (512 / 10).
6. **New opt-in switches, not used:** the Foresight swap space (`STRATA_FS_*`), chunked DeltaNet prompt recurrence
   (`STRATA_GDN_CHUNKED`, other bits), residency-biased routing (`STRATA_ROUTE_RESIDENT`: changes the output — not lossless),
   the no-P2P peer prompt path, debug hooks.
7. **Nothing restores the ~3 % Round 15 lost against C\*14** (step 2).

### What I got wrong

1. **`pkill -f` matched my own shell again** (Rounds 14 and 15's slip): it ended the command along with the slow prompt
   builder it was meant to stop. Nothing else was affected; I kill by PID since.
2. **The prompt builder looped**: my token-count adjustment oscillated by one token forever. Bounded (±2 tokens accepted).
3. **Step 1's first two starts did nothing**: build-cstar16.sh was not executable, and the A/B script called
   `scripts/mkcfg.py` (another tool) instead of `bringup/lib/mkcfg.py`. Both failed before any server started. Fixed and
   dry-tested.
4. **My first long-text NLL check forced text that no longer continued its cut prompt** (NLL 2.4–6 nats). Kept as an
   on/off comparison and redone in context; the control (B.1 / B.2) then showed long texts move this much under any
   rounding change.
5. **Two waits returned early**: a waiter started while the queue's last line was a hold, and an until-loop matching
   "MARK r16-s3" inside "MARK r16-s3gates". Both harmless; noted in DAY-ONE.md.
6. **The Q4 check started with buffered reads** before I read the engine's warning that prompt reads take lent-slot experts
   from the SSD; restarted with `STRATA_UNBUFFERED_LOAD=1` after one minute (inside the hour).
7. A few notebook times were estimates and were corrected (15:56 → 15:51).

### Time

14:05 → 23:10 ≈ **9 h**. The port and the release alone 50 min (ledger pass ~10 min by hand). Step 1 2 h 10 min (the A/B 6
min; two long-text checks and a control 45 min; the acceptance suite with the share 58 min). Step 2 1 h 53 min (six arms).
Step 3 3 h 28 min (gates 23 min, the acceptance suite 58 min, the soak 2 h, promotion 2 min). Q4 check 20 min (one minute
lost to the restart). Report 25 min.
