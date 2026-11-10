
## Round 21 — the 10-16 morning queue: desktop on the iGPU, reserve, guard, think fix (C\*18t), issue #2794, FP4-Local, NVFP4 vs IQ3_S, your sampling everywhere, reasoning effort, Q8_0 honesty (2026-10-16 06:50 → 10-17)

Chronological notes: `NOTES.md` (the 2026-10-16 / 10-17 entries). Phone summary: `results/round21-summary.md`.
Scripts: `work/r21/`, `work/usability/`. Raw results: `results/r21/`, `suite/results/`, `results/usability-runs/`.

### Result

* **C\*18t is on 8080** (promoted 10-16 09:55): C\*18 + one server commit (the think-tag fix, d9e2c3a5, `serve/` only),
  same engine and settings. **Since 21:53 every client gets your sampling** (T 1.0, top-p 0.95, top-k 20, min-p 0.05).
  Rollback: stop 8080, `STRATA_CONFIG=configs/Cstar18.json ./switch-model.sh strata`.
* **Reserve stays 713.** Moving the desktop to the iGPU gave the expert cache +123 slots (+0.24 GiB) by itself; a lower
  reserve was not faster at equal sampling and leaves the 5080 under the guard's floor.
* **Guard:** warns at once and stops Strata only after 60 s straight under the VRAM floor (Xorg still holds 4 MiB on
  each NVIDIA card). No warning fired since.
* **Issue #2794 posted** (your typed OK).
* **FP4-Local** converts exactly but is not better than the GPTQ pack. **Both NVFP4 packs decode ~30 % slower than
  IQ3_S.** UD-Q4_K_XL is the closest to Q8_0 of everything measured.
* **Reasoning effort:** at **medium**, C\*18t answered the honesty items 12/12 right and c14 3/3, with 0.2-1K and 2-5K
  reasoning tokens. At **xhigh** (the default; Strata and the template send "high" as xhigh) it got 4/12 and 2/3, with
  13-52K and 11-27K tokens.
* **Q8_0 on honesty (overnight):** see the last subsection.

### Items 1-8

1. **Health (06:53).** The display is on the AMD iGPU; both NVIDIA cards show display_active Disabled, and the only
   desktop process on them is Xorg with 4 MiB each (no gnome-shell, browser or Jan). RAM 91.96 GiB total (unchanged),
   88.1 GiB available idle (the iGPU's 2 GiB carve-out was already reserved before). Kernel log clean. The kernel
   watcher was not running after the reboot and was restarted at 07:01.
2. **VRAM reserve.** On 10-15 the desktop held ~186-240 MiB of the 5080. That room went to the expert cache by itself:
   C\*18 at reserve 713 now holds **4,586 experts / 8.75 GiB** (10-15: 4,463 / 8.51 GiB). Reserve 512 measured against
   713, A B B A, both at T 1.0:

   | | 713 (C\*18t) | 512 | change |
   |---|---|---|---|
   | expert cache | 4,586 slots | 4,694 slots | +2.4 % |
   | decode, decode screen | 142.9 tok/s | 135.7 tok/s | −5.0 % |
   | decode, full screen | 143.5 tok/s | 140.8 tok/s | −1.9 % |
   | TTFT 32K / 64K / 120K | | | −0.1 / +0.1 / +0.2 % |
   | 5080 free under load | 410-487 MiB | 269-295 MiB | below the 300 MiB floor |

   Needles 72/72 and Stop at 120K passed on 512. **Not promoted.** The morning's +1.1-1.6 % was an artifact: that
   candidate ran at T 0.6 (no Chat settings file), and a lower temperature accepts more draft tokens.
3. **Guard on 8080.** Xorg's 4 MiB handle on each NVIDIA card counts as "something still does", so the standing guard
   runs in **warn60** mode:
   * The first sample under 300 MiB logs a warning with the GPU process list and shows a desktop notification.
   * Strata is stopped only after 60 s straight under the floor.
   * The guard follows engine restarts and ends only when 8080 stops.

   Measurement runs keep the strict guard; the memory floor is unchanged (20 GiB). Since 10-16 no standing guard has
   warned, and 5080 free under service is ≥ 479 MiB. Xorg's handle could be removed with a root-owned Xorg config
   (needs sudo; I can give you the file), and then the guard could go log-only.
4. **Think-tag fix → C\*18t.** A `</think>` inside a code fence of the reasoning is held until the fence closes. If the
   turn ends with the fence still open, the last `</think>` held counts as the end. Results:
   * Replay of all 503 recorded turns: 7 lost tool calls recovered, 0 other changes.
   * Full serve suite: 795 OK.
   * The real bug-fix task on C\*18t: **4/4 green**, and every session reached its end (10-15 on C\*18: the think tag
     cut off all 9).
5. **Issue posted: https://github.com/Niko1221/Strata/issues/2794** (same class as #2026; follow-up to #1526). The text
   matches the approved file byte for byte. The `bug` label did not attach, because a non-collaborator can't set labels.
6. **Small items.**
   * Jan's shell tool is off: Jan 0.8.6 has no setting for it, so the launcher sets `JAN_AGENT_SANDBOX=off` (checked
     live: the tools offered are web_search and web_fetch only).
   * `tmp/usability/` was deleted after its results were copied to `results/usability-runs/`.
   * `/usr/bin/rg` doesn't exist, so OpenCode keeps Codex's ripgrep.
7. **FP4-Local.** The scale decoder was found in vLLM PR #60646 (the CSF codec; I read the code only and ran no
   containers). Conversion:
   * All 73,728 expert projections were decoded and re-encoded byte for byte (24.2 M exceptions, 0 failures).
   * They were converted with `nvfp4_convert.py`; the dequantized values equal ModelOpt's.
   * Its retrained n-gram table does not convert without loss (24 % of values need more than 4 significant bits), so
     that arm was skipped.
   * Q5 was deleted. Q8_0 was kept: the room wasn't needed, and it served as the yardstick's reference and the
     overnight run.

   Yardstick (teacher-forced, against Q8_0, 4,995 positions):

   | pack | top-1 agreement | KL | KL p99 |
   |---|---|---|---|
   | UD-Q4_K_XL | **92.37 %** | **0.0591** | **0.99** |
   | GPTQ NVFP4 | 91.69 % | 0.0665 | 1.05 |
   | FP4-Local, own routers | 91.19 % | 0.0759 | 1.28 |
   | FP4-Local (GPTQ pack's routers) | 91.17 % | 0.0764 | 1.32 |
   | IQ3_S (served) | 87.43 % | 0.1441 | 2.00 |

   FP4-Local's QAD retrained the routers (1.1-1.6 % different). Using them closes almost none of the gap, so the
   shared-expert check you made conditional wasn't needed.

   Speed: FP4-Local = GPTQ (decode 101.4 vs 100.2 tok/s; TTFT 32K / 64K / 120K 9.30 / 17.12 / 31.60 s vs 9.29 / 17.09
   / 31.62 s).

   Suite quick (all at T 1.0 / 0.95 / 20 / 0.05; every paired difference within noise):

   | category | GPTQ NVFP4 | FP4-Local | C\*18 IQ3_S (10-15) |
   |---|---|---|---|
   | coding | 77.1 | 79.3 | 88.2 |
   | instruction following | 95 | 90 | 95 |
   | long context | 63.3 | 100 | 83.3 |
   | honesty | 73.3 | 73.3 | 73.3 |
   | research | 85.7 | 85.7 | 85.7 |
   | agentic / math / tools | 100 | 100 | 100 |
   | **total** | **86.8** | **91.0** | **90.7** |

   Each NVFP4 run took 4.6 h (IQ3_S 2.9 h); the lowest MemAvailable was 7.3 / 6.7 GiB (floor 6).
   **c02 and c14 on the NVFP4 packs** (no answer written in any of the four):

   | item | pack | cut by | reasoning tokens by then |
   |---|---|---|---|
   | c02_rle | GPTQ | loop stop ('1' × 256) | 7,943 |
   | c02_rle | FP4-Local | loop stop ('0' × 256) | 21,387 |
   | c14_semver | GPTQ | token limit (81,920) | 81,920 |
   | c14_semver | FP4-Local | token limit (81,920) | 81,920 |

   c14 ended in an endless "Potential issue: if hidden tests check ..." list (no single-token repeat, so the loop stop
   never fired). IQ3_S solved c02 in 9,280 tokens and c14 in 45,812.

### NVFP4 vs C\*18t IQ3_S under today's conditions

A B B A, the desktop on the iGPU, both at T 1.0, C\*18t vs the better NVFP4 pack (GPTQ):

| | C\*18t IQ3_S | GPTQ NVFP4 | NVFP4 vs IQ3_S |
|---|---|---|---|
| decode, decode screen | 143.3 tok/s | 100.4 tok/s | −29.9 % |
| decode, full screen | 144.1 tok/s | 100.3 tok/s | −30.4 % |
| TTFT 32K | 7.7 s | 9.3 s | +20 % |
| TTFT 64K | 15.4 s | 17.1 s | +11 % |
| TTFT 120K | 29.8 s | 31.6 s | +6 % |
| lowest MemAvailable | 27.5 GiB | 10.4 GiB | |

**Verdict:** IQ3_S stays the daily model. NVFP4 is closer to Q8_0, but 30 % slower to decode, needs every expert in RAM
(10 GiB left), and its suite score is not better.

### Honesty: hosted Flash vs the three local packs

Three items fail on all three local packs and pass on hosted (full run, 3 samples). All three ask about something that
doesn't exist; the right answer is UNKNOWN.

| item | hosted | local answers (IQ3_S / GPTQ / FP4-Local) |
|---|---|---|
| h03_viirmets (striker) | 2 of 3 | '14' / '10' / '1' |
| h05_strondalsvik (village) | 3 of 3 | '119' / '14' / '1' |
| h07_glasbienen (novel) | 3 of 3 | '176' / '334' / '343' |

Each local reasoning followed the same path:
* It raises "maybe it doesn't exist", then "recalls" a source that doesn't exist (a Wikipedia sentence, a catalogue
  line).
* It rejects UNKNOWN in words ("I will not use UNKNOWN", "We need be assertive").
* The answer states the guess as fact, with the invented source.

Local reasoning ran 10-45K tokens against 5.6-9.5K hosted. h12 fails locally and on 2 of 3 hosted runs, so it isn't
counted.

### Reasoning effort

**What the hosted run got.** The suite sent `reasoning: {"effort": "xhigh"}` through OpenRouter, pinned to Alibaba.
* OpenRouter lists no effort levels for this model, so the effort is not passed on as an effort. At most it becomes a
  thinking budget of ~95 % of max_tokens.
* No budget was enforced either: hosted c16 thought 81,920 tokens.
* So hosted ran at the model's default level, which the model's own template sets to **xhigh**.

Median reasoning tokens per answer, hosted vs C\*18 IQ3_S:

| | all | coding | honesty |
|---|---|---|---|
| hosted | 2,444 | 11,659 | 4,546 |
| C\*18 IQ3_S | 2,346 | 12,437 | 8,038 |

Locally, **"high" is the same as xhigh**: the template maps high to xhigh, and Strata maps high / xhigh / max to xhigh
before the template, so the two requests render the identical prompt. Your test therefore ran **xhigh vs medium**,
the next real level (medium drops the template's "think carefully ..." sentence).

**The test:** C\*18t at your sampling, 3 samples each. Pass means UNKNOWN for the h items and the hidden tests for c14.

| item | xhigh: pass | xhigh: reasoning tokens per answer | medium: pass | medium: reasoning tokens per answer |
|---|---|---|---|---|
| h03 | 2/3 | 20,199 / 21,140 ('16') / 49,563 | 3/3 | 235 / 273 / 259 |
| h05 | 1/3 | 30,854 ('0') / 35,917 ('37') / 32,944 | 3/3 | 546 / 422 / 415 |
| h07 | 1/3 | 18,706 / 12,893 ('316') / 21,862 ('338') | 3/3 | 329 / 341 / 345 |
| h12 | 0/3 | 23,698 ('1100') / 36,183 ('1120') / 52,242 ('1100') | 3/3 | 826 / 1,037 / 766 |
| c14 | 2/3 | 27,484 (no code block) / 24,943 / 11,087 | 3/3 | 2,448 / 4,086 / 4,649 |
| time for the 15 answers | | 53 min | | 3 min |

Honesty is 12/12 vs 4/12 by answers (Fisher exact p = 0.001). The suite's item-level test can't call 4 items
significant (p ≥ 0.125), so it still says "within noise". The medium answers read well, for example h12: "the 1923
Baltic Games did take place ... I cannot verify the exact figure" → UNKNOWN.

This is 5 items. It does not show what medium costs on hard math, long context or long coding tasks. A suite quick run
at medium (~1-2 h) would show that before you change a default.

### Your sampling on every path (since 10-16 21:53)

**Two corrections to earlier notes:**
1. On 10-15, Codex and dsh ran at your T 1.0 and only OpenCode at 0.6. I had written that all three ran at 0.6.
2. 10-16's batch4 (r3/r4) had OpenCode and dsh both at 0.6.

What was changed:
* OpenCode's request body now sends T 1.0 / 0.95 / 20 / 0.05.
* The "sampling" block in `Cstar18t.json`, `Cstar18.json` and `Cstar18-single.json` is now T 1.0, so a client that
  sends nothing (dsh, Codex) gets your settings, min-p included. The Chat settings file can't hold min-p.

Checks:
* 8080 starts with "sampling defaults from the config: temperature=1.0, top_p=0.95, top_k=20, min_p=0.05".
* OpenCode's recorded requests carry the same values.

Backups are in `work/r21/*.before-sampling`. Every speed arm, suite run and A B B A today ran at T 1.0, as their start
lines show.

### The bug-fix task at T 1.0 (OpenCode vs dsh Minimal, C\*18t)

HARNESS_TABLE_PENDING

### Q8_0 on honesty (overnight)

Q8_PENDING

### What went wrong on my side

* **The test venv was missing for the first two harness runs.** `tmp/usability/venv-rt` was deleted with `tmp/usability/`
  in item 6. The first OpenCode and dsh runs had no `.venv` to test with and could not be graded. I rebuilt the venv
  and set those runs aside (`*-novenv`); they were rerun at 00:21.
* **8080 was down for ~2 minutes at 21:51.** First my change script stopped on `diff`'s normal "files differ" exit
  code, after every edit had been made. Then my restart command's text matched the launcher's "another server is
  running" check (the known pgrep pitfall). The chain's start-line check caught it, and 8080 has been up since 21:53.

### Needs your decision

1. **Reasoning effort default:** keep xhigh (the template's default) or test medium more widely first (a suite quick run
   at medium, ~1-2 h). Nothing has changed.
2. **Xorg's 4 MiB on the NVIDIA cards:** a root-owned Xorg config would remove it (sudo; I can give you the file), and
   then the guard could go log-only.
3. **dsh outgrowing the context:** dsh Minimal's T 1.0 session reached 100K tokens. Its closing request was refused
   (prompt + max_tokens > 131,072; Strata never truncates). The work was already done and green. `"fit_max_tokens": true`
   in the model's config would shorten max_tokens instead of refusing. Not changed.
4. **Disk (170 GB free):**
   * Q8_0 (176 GB) can go once you've read its result; your 10-15 OK covers it.
   * The FP4-Local packs (67 GB) can go too: neither is used by the served config.
