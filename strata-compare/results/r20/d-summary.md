# D (2026-10-14): concurrency on C*17.1 (config copies on 8081; configs/Cstar171.json unchanged)

Arms: base = C*17.1 as served (4060 Ti helper cache, one request at a time); b8 = + --batch 8 (helper kept);
b8-nohelp = --batch 8 on the 5080 alone (STRATA_ROUTE_TAIL_SKIP=0); b8-mtp = --batch 8 --batch-mtp (helper kept).
The batch configs need --vram-reserve-mib 1213 (713 as served): with 713 the first b8 arm was guard-stopped at the
5080's 300 MiB floor (free VRAM fell from ~470 MiB as batch windows ran). 8 slots fit; per-slot context 131,072
(32,768 resident in VRAM per slot, the rest streamed from pinned RAM); each slot session 0.73 GiB, 5.82 GiB for 8.
Expert cache on the 5080: base 4,467 slots; b8 / b8-nohelp 1,129 (-75 %); b8-mtp 889 (-80 %).
Work: decode = 8 short prompts (longreason math / code / puzzle + 5 suite coding items), 4,096-token answers;
agent = 8 coding-agent turns, 27,709-token prompts with 7 tool definitions (Python 3.12 stdlib sources as read_file
results), the model answers with one tool call (~100-200 tokens). Your sampling (T 1.0, 0.95, 20, min_p 0.05), xhigh.
N requests sent at the same instant; 2 repetitions (1,2,4,8 then 8,4,2,1); every cell below is the median of the 2
repetitions (for 2 values, their mean). Correction (evening of 10-14): the first version showed the worst first token as
the worst of both repetitions but the wall time as their median, so the served agent row at N = 8 read 86 s / 76 s
(rep 1: worst 66 s, wall 67 s; rep 2: worst 86 s, wall 86 s). Now both are medians; no re-run.

## Decode-style (total tok/s | per request tok/s | TTFT median / worst | wall for the set)
| N | base | b8 | b8-nohelp | b8-mtp |
|---|---|---|---|---|
| 1 | 156.2 / 159 / 0.5 s / 26 s | 110.2 / 112 / 0.7 s / 37 s | 93.4 / 95 / 0.6 s / 44 s | 103.1 / 105 / 0.7 s / 40 s |
| 2 | 142.6 / 146 / 13 / 26 s / 57 s | 90.2 / 46 / 0.9 / 1.2 s / 91 s | 76.7 / 39 / 0.9 / 1.2 s / 107 s | 90.3 / 47 / 0.9 / 1.3 s / 91 s |
| 4 | 141.5 / 138 / 41 / 70 s / 100 s | 97.1 / 29 / 1.5 / 2.6 s / 145 s | 83.7 / 22 / 1.6 / 2.7 s / 186 s | 90.2 / 28 / 1.6 / 2.7 s / 151 s |
| 8 | 137.3 / 137 / 84 / 181 s / 209 s | 106.2 / 15 / 3.0 / 5.8 s / 269 s | 88.3 / 14 / 3.0 / 5.9 s / 304 s | 92.2 / 13 / 3.1 / 6.7 s / 324 s |

## Agent-style (TTFT median / worst | wall for the set)
| N | base | b8 | b8-nohelp | b8-mtp |
|---|---|---|---|---|
| 1 | 6.5 s / 8 s | 33 s / 34 s | 33 s / 34 s | 44 s / 45 s |
| 2 | 10.0 / 13 s / 14 s | 51 / 70 s / 71 s | 49 / 66 s / 68 s | 66 / 89 s / 89 s |
| 4 | 18 / 30 s / 31 s | 86 / 147 s / 148 s | 87 / 149 s / 170 s | 111 / 179 s / 181 s |
| 8 | 31 / 76 s / 76 s | 161 / 291 s / 291 s | 150 / 275 s / 296 s | 200 / 366 s / 379 s |

Lowest MemAvailable: base 27.2 GiB, b8 13.3, b8-nohelp 13.8, b8-mtp 11.6 (floor 8). Kernel checks ok after every server.

**Which wins:** base (one at a time, with the helper) at every level for both kinds of work, by total throughput and by
the time the whole set takes. Batch slots win only one thing: on decode-style work every request starts within ~6 s
instead of waiting up to 3 minutes in the queue. Helper vs batch: --batch works with the helper (it serves batch rows),
but the slots' 5.82 GiB cut the 5080's expert cache by 75 %; a 27.7K-token agent prompt then takes ~33 s to read
instead of 6.5 s (without the helper the same), and --batch-mtp is no better than plain slots (44 s).

**Outputs vs single requests (greedy, each prompt alone then all together):** with C*17.1's settings they part at
near-ties (decode 0 of 8 equal at N=8, first difference at characters 14-1,692; agents 3 of 4). The same with
docs/BATCHING.md's exactness settings (STRATA_IQ_MT_MIN=1, --adapt-every 1000000, --no-prefill-borrow) and with
drafting off. With our kernel switches off as well (side mixer, Q8_K router, GR fork, split decode attention, B.3
rows) every request equals its solo output: decode 8 of 8 at N=8, agents 4 of 4. So our switches round differently in
solo windows and in batch rows (they change both paths against the release's own arithmetic); rounding-level, not a
batch-path error.
**Our exact sampling in batch mode:** near-tie probe arith-j3 at T 0.6, 2,000 samples per arm with the twin's own
probabilities: 8 in flight (all 2,000 in batch slots) '=' 991 vs 959.1 expected, p 0.142; one at a time (our exact
speculative sampling) 974 vs 959.6, p 0.507 - both pass. Batch rows draw sample-and-match with Philox(seed, position)
(--batch-mtp keeps a proposal only when it equals the target's own draw), so they are exact by construction; with
sampling, solo and batch texts differ by design (our exact sampler uses other random streams), not in distribution.
