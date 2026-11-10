# Round 19 summary: the RAM fault, #1682 / #1683 answered, C\*17 on v0.1.42 → C\*17.1 on v0.1.43, and the cause of upstream's STRATA_SPEC_PROB bias

2026-10-10 15:30 to 2026-10-11 ~18:30 (with your reboots on 10-10 and your Windows boot on 10-11). The monitor is on the
motherboard output; the display setup was not changed. Details: REPORT.md "Round 19", NOTES.md "# ROUND 19"; raw results
in results/r19/. Part D (v0.1.43, 2026-10-11 18:27 → 10-12 03:49) is at the end; C\*17.1 replaced C\*17 on 8080.

## What is on 8080

**Since 2026-10-12 03:48: C\*17.1** (v0.1.43; see Part D below). Until then:

**C\*17** = Strata v0.1.42 + C\*16.1's series (our exact sampling and cost gate kept) + `STRATA_PREFILL_CPU_SHARE=0.4` on
prompt chunks below 1,792 tokens. It carries v0.1.42's fixes that reach the server (logit bias, #1624, #984).

| vs C\*16.1 (A B B A, one session) | result |
|---|---|
| decode screen / full screen / LDR screen | −1.4 % / −0.8 % / −0.2 % |
| first token, fresh 512 / 1,000-token prompts (B3) | −15 % / −21 % |
| first token, the LDR's prompts under 4K | −4.7 % |
| outputs | C\*16.1's, plus the share's change on short prompts (exact7: 3 long items identical, repeats 7/7) |

Checks: every gate (needles 72/72, stop at 120K, follow-ups, stops, tool calls, #931, repeat, chat-cache round trips,
browser 42/1 = the known line), our sampler's chi-square, the six near-tie cases, the acceptance suite on the same
combination (11 / 0), a 2-hour soak (440 requests, 0 errors, MemAvailable ≥ 21.8 GB, swap 0), the rollback test.
Rollback: stop 8080, `STRATA_CONFIG=configs/Cstar161.json ./switch-model.sh strata`.

## The RAM fault (correction)

The kernel faults of 10-07 and 10-10 were the RAM at 6200 MT/s (your memtest), not Strata, the kernel or the driver. Now
6000 MT/s 1:1; stressapptest 1 h PASS. After the reboots every model file matched its hash (all 341 identical to 10-10),
git fsck and the worktrees were clean, and the rebuilt engines repeat their recorded outputs (35/35). Since 10-11 the
NVIDIA driver is 615.71.09.

## Part A: the two replies (posted with your OK)

* **#1682:** fio with the owner's command 10.1 / 9.0 GB/s (psync), 7.8 GB/s (libaio). Forced unbuffered vs the read rule:
  **+24.6 % (threads unset), +25.8 % (16), +24.2 % (64)**; the thread count makes no difference.
* **#1683:** 72 = 66 exactly (63.95 GiB, 0 of 2,258 lent slots in RAM, 32K read 11.2 s, 29 GB from the drive);
  `--resident-experts` 70.53 GiB, all lent slots in RAM, 8.8 s, 1.2 GB.

## Part B

| step | result |
|---|---|
| B1 port | v0.1.42 + C\*16.1's 28 commits; every gate PASS; all switches on = C\*16.1's outputs 7/7 |
| B2 tail skip, two cards | does not act (0 skips in 12 requests); only its start-up line says ON |
| B3 CPU share 0.4 | kept: repeatable, −15 / −21 % first token, suite 11/0; limited to chunks < 1,792 (above, it costs up to 27 %) |
| B4 helper source | not kept (+0.2 to +2.2 % first token) |
| B5 our sampling vs upstream's | equal speed (144.5 each); kept ours after the bias below |
| B5b cost-gate PR, two cards | +4.2 % decode, +4.3 % after 32K, −2.0 % after 120K: **not worth opening** |
| B6 C\*17 vs C\*16.1 | about −1 % decode; promoted for v0.1.42's server fixes |
| B7 Q4 config | on C\*17, tail skip 0, **`--resident-experts`**: 32K read −20 %, drive 1.2 instead of 29 GB, decode +3 % |

## The sampler bias

At a near-tie (the arith prompt, 4th token, temperature 0.6; the model's own probability for `=` 51.8 % after the filters),
same build, same position:

| arm | `=` |
|---|---|
| speculation off (ground truth), 6,000 samples | 52.3 % |
| upstream's default exact-match drafting, 4,000 | 54.0 % |
| our exact sampling, 6,000 | 54.5 % |
| upstream's `STRATA_SPEC_PROB` (with or without our gate), 2,000 | **59.6–62.2 %** |
| upstream's `STRATA_SPEC_PROB` at temperature 1.0, 2,000 | 52.6 % vs 51.1 % (no bias detected) |

The ~2 pp both exact-match and our sampling show is the verify window's own arithmetic (the default path has it too).
Upstream's sampling is ~8 pp beyond that. An issue is drafted only after the same check on stock v0.1.43.

## My mistakes

* I concluded that our cost gate is unused under upstream's sampling from a server that had not served a request yet
  (the gate logs on first use); it cost a runbook pass and one B6.
* The fallback build failed twice at its start (a missing execute bit, then a helper my edit had cut); 8080 was down
  11:36–12:45.

## Part D: v0.1.43 → C\*17.1 (now on 8080)

**C\*17.1** = v0.1.43 + C\*17's series (29 commits; the new one drops our chat cache when v0.1.43's non-finite guard fires),
C\*17's settings unchanged. It computes exactly what C\*17 computes (exact7 7/7 with every v0.1.43 default as shipped).

| vs C\*17 (A B B A) | LDR | decode screen | full screen | after a 2-hour soak (decode) |
|---|---|---|---|---|
| C\*17.1 | −0.4 % | +0.4 % | −0.3 % | 143.4 vs 142.9 tok/s |

Checks: runbook gates, ctest (= stock), the NaN test with our chat cache, every C\*17 gate, the acceptance suite (every
row PASS), the soak (450 requests, 0 errors, MemAvailable ≥ 23.4 GB), the rollback test (C\*17 → C\*17.1).
Rollback: stop 8080, `STRATA_CONFIG=configs/Cstar17.json ./switch-model.sh strata`.

* **Not kept:** v0.1.43's adaptive overlap — two cards +0.5 % decode but **−11.4 % on the LDR screen**; Q4 resident mode +1.7 %
  (bar 2 %). On two cards it would only cover the 5080's swaps: the helper card has no adaptive swaps of its own.
* **The sampler bias, cause found** (stock v0.1.43, the T 0.6 near-tie): speculation off 52.9 %, `STRATA_SPEC_PROB` 57.1 %
  (p 0.003); with `--spec-min-p 0` 53.3 %, with `STRATA_SPEC_PROB_GATE=top` 51.4 %. `--spec-min-p` gates each draft on the q
  of the token the drafter drew, so rejection sampling is no longer exact. Our exact sampling is not affected (54.5 %,
  the same as on v0.1.42; window numerics).
* **#1896 on CUDA:** at a 72 GiB budget all 2,258 lent slots stay in RAM; 32K read 8.8 vs 11.3 s; 1.2 vs 28.9 GB from the
  drive per prompt; the same as `--resident-experts`.
* **#1889** rebased onto v0.1.43: switch off = stock 7/7, on = off 7/7, ctest = stock.

## Posted with your OK (2026-10-11 ~22:2x)

| item | link |
|---|---|
| #1684 comment (thanks, the 0.4 share, the SHARE_MAX caveat) | https://github.com/Niko1221/Strata/issues/1684#issuecomment-6117080376 |
| issue #2027 (CMake: four tests only from the second configure) | https://github.com/Niko1221/Strata/issues/2027 |
| #1896 comment (CUDA test) | https://github.com/Niko1221/Strata/pull/1896#issuecomment-6117081470 |
| issue #2028 (STRATA_SPEC_PROB: the gate on the drawn draft's q) | https://github.com/Niko1221/Strata/issues/2028 |
| #1889 force-push (602a8128 → 38b03280) + comment | https://github.com/Niko1221/Strata/pull/1889#issuecomment-6117083460 |

## My mistakes in Part D

* d1b's ctest wrote its output to a wrong path; re-run (d1c).
* `switch-model.sh` line 8 had described C\*17 as lacking our exact sampling and gate since its promotion; C\*17.1's copy fixes it.
* The overlap tests' served-repeat check cannot show repeatability on these configs (B2 had shown that); the overlap was
  rejected on speed alone, so no conclusion rests on it.
* The uptime log's PLANNED lines lagged behind the queue for the 19:07–23:12 steps (noted afterwards).
