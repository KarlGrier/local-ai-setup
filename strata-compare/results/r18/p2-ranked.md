# Round 18, Part 2.1: our patches ranked by their gain on the RTX 5080 alone

Single-card gains: C*16.1's one-card copy (CUDA_VISIBLE_DEVICES = the RTX 5080, no --expert-cache-device1), served decode
screen, one patch switched off at a time, mirrored order (base, X1..X7, X7..X1, base), each arm a fresh guarded server
(results/r18/p2-rank.md; base arms 133.3 / 131.8 tok/s, 18.01 / 17.69 ms per round = 1.8 % spread). Gain = base vs that
patch off: decode tok/s for the drafting patches, ms per verify round for the others. Two-card gains: Round 14's ledger
(served, v0.1.40.1, each patch added on top of the ones before it), labelled as such.

| rank | patch (switch) | class / gate | gain, RTX 5080 alone | gain, two cards (Round 14) | upstream overlap | qualifies |
|---|---|---|---|---|---|---|
| 1 | exact speculative sampling (STRATA_SPEC_EXACT=1) | (c) chi-square | **+7.9 % decode** (acceptance 0.576 → 0.684) | +3.5 % decode | STRATA_SPEC_PROB (opt-in; ours +2.7 % against it, Round 15) | yes |
| 2 | cost-aware draft length (STRATA_COST_GATE=FILE) | (c) chi-square; (b) for greedy | **+5.4 % decode** (with exact sampling on) | +3.4 % decode | none | yes - its table is fitted to this drafter and this PC's window costs; ported without exact sampling for the PR |
| 3 | B.2 split decode attention (STRATA_QSA_SPLIT_ATTN=1) | (b) TF NLL | **−4.4 % per round** (+4.2 % decode) | −4.6 % per round, LDR +3.0 % | none | yes |
| 4 | side mixer + the round-18 fix (STRATA_SIDE_MIXER=2) | (a) pair identical | −2.3 % per round (+2.9 % decode) | −4.7 % per round, decode +2.5 % | STRATA_DF_BRANCH (opt-in, the same idea; not compared) | yes (not in this batch) |
| 5 | B.1 hyper-connection read (STRATA_GR_FORK=1) | (b) TF NLL | −1.6 % per round against STRATA_GR_V3 | −2.2 % per round | v0.1.41's default staged read (not compared) | yes (not in this batch) |
| 6 | A.2 router Q8_K rows (STRATA_ROUTER_Q8K=1) | (a) pair identical | −1.3 % per round (decode −0.1 %, noise) | −1.0 % per round, LDR +1.4 % | #851's AVX2 Q8_K quantizer (on by default) | barely (not in this batch) |
| – | F4 rows table measured on this 5080 (STRATA_MMVQ_IL_ROWS) | bitwise | −0.4 % per round (noise) | ~0.6 % (Part 1, CLI GPU wait) | upstream's shared sm_86 + sm_120 table | no (< 1 % alone) |
| – | F4 rows table for sm_89 (RTX 4060 Ti) | bitwise | not measurable on the 5080 (it changes only sm_89 cards) | – (the helper card runs no dense projections) | upstream asks for one | no measured gain here |
| – | helper-aware tier | – | – | – | dropped in Round 14 for upstream's STRATA_DISJOINT_ADAPT | no (upstream's) |

Not candidates: the #567 / #619 / #652 transplants (other authors' pull requests), the server / web-app features (chat
cache, web search, tabs, model check), the patch guards and test rows.

**Decision screen on current upstream main** (results/r18/p2-decide.md; stock main fb58e0db on the RTX 5080 alone, the
community report's stock flags, sampled decode screen, mirrored order def prob ours gate df side | side df gate ours prob def,
each arm a fresh guarded server):

| arm | decode tok/s (a / b) | vs stock | ms per round | tokens per round | acceptance |
|---|---|---|---|---|---|
| stock main | 114.4 / 113.3 → 113.8 | - | 17.44 | 1.985 | 0.647 |
| + STRATA_SPEC_PROB=1 (upstream) | 117.0 / 117.6 → 117.3 | +3.0 % | 17.31 | 2.031 | 0.730 |
| + our exact sampling (STRATA_SPEC_EXACT=1) | 116.6 / 115.0 → 115.8 | +1.7 % | 17.98 | 2.082 | 0.701 |
| + SPEC_PROB + the cost gate | 120.1 / 117.5 → 118.8 | +4.3 % (+1.3 % over SPEC_PROB) | 19.04 | 2.262 | 0.670 |
| + STRATA_DF_BRANCH=1 (upstream) | 115.6 / 114.7 → 115.2 | +1.2 % | 17.21 | 1.982 | 0.645 |
| + our side mixer (STRATA_SIDE_MIXER=2) | 118.4 / 118.5 → 118.5 | +4.1 % (+2.9 % over DF_BRANCH; per round -1.9 %) | 16.89 | 2.001 | 0.645 |

→ **Exact sampling is superseded** on current main: upstream's STRATA_SPEC_PROB (the same algorithm) is 1.3 % faster than
ours here, so it is not offered. The cost gate still adds +1.3 % on top of SPEC_PROB on one card (+3.1 % on two cards in
Round 15), and the side mixer beats upstream's own DF_BRANCH by 2.9 % in decode (1.9 % per round).

**Final ranking for pull requests (single-card gain against what upstream already has):**

| rank | patch | gain, RTX 5080 alone | gain, two cards | PR |
|---|---|---|---|---|
| 1 | B.2 split decode attention (STRATA_QSA_SPLIT_ATTN=1) | -4.4 % per round, +4.2 % decode (C*16.1's one-card copy; on main: Part 2.2) | -4.6 % per round, LDR +3.0 % (R14) | yes |
| 2 | side mixer + the round-18 fix (STRATA_SIDE_MIXER=2) | +4.1 % decode vs main, +2.9 % vs DF_BRANCH | -4.7 % per round, decode +2.5 % (R14) | yes |
| 3 | cost-aware draft length with SPEC_PROB (STRATA_COST_GATE=FILE) | +1.3 % decode over SPEC_PROB alone | +3.1 % over SPEC_PROB alone (R15) | yes |
| - | exact sampling (STRATA_SPEC_EXACT=1) | -1.3 % vs SPEC_PROB | +2.7 % vs SPEC_PROB (R15, v0.1.40.2) | no: superseded |
| 5.. | B.1, A.2, the 5080 table, the sm_89 table | see above | | not this round |

**Top 3 → Part 2.2:** B.2, the side mixer, the cost gate (standalone, on SPEC_PROB).
