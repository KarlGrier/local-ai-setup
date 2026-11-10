# Patch ledger — C\*16 (Strata v0.1.41 fb58e0db + branch `r16-port` = patches/r16p27, 27 commits)

One row per commit of `git log v0.1.41..r16-port` (exported to `patches/r16p27/`; the twin's 4 MEASUREMENT commits in
`patches/r16-meas27/`). C\*15's ledger (v0.1.40.2, 27 rows) is now `patches/LEDGER-r15.md`; the rows are the same commits
in the same order (row numbers unchanged; commit ids below are r15-port's, as before — r16-port's are the cherry-picks).
**Round 16's ledger pass** (REPORT.md "Round 16", the port): all 27 rows apply to v0.1.41 by cherry-pick; **one conflict,
row 18 (prompt_encoder, 8f7615d5)**: v0.1.41 added its own `tools/test_strata_tokenizer.py` (tests of the new tokenizer piece
cache, f346dc6b) where our row adds #567's tests under the same name — one file with both test sets. Upstream merged none of our
transplants (#652, #567, #619 still open); no row dropped, none added.

**Gates on v0.1.41** (run r16z, clean clone, IQ3_S, `STRATA_PREFILL_CPU_SHARE=0`: v0.1.41's new CPU prompt-read share reads
short prompts with timing-dependent rounding, so the exactness gates run with it off): the release alone = v0.1.40.2's
stock 7/7 and repeats itself; patched with every switch off = the release 7/7; `strata patch guards: 5 checked, 0 off`;
every switch gate PASS with Round 14/15's values to the digit (B.2 TF −0.0008 / −0.0006, exact sampling and cost gate
chi-square ALL PASS, side mixer and A.2 pairs identical, B.1 TF +0.0008 / −0.0026). C\*16 itself runs with the share at
upstream's default (on; step 1 of Round 16).

**Gains** in the table are Round 14's (v0.1.40.1), as in C\*15's ledger. Classes and columns: as in LEDGER-r14.md.
Upstream overlaps new in v0.1.41: row 18 (#567's prompt encoder) now sits beside upstream's tokenizer piece cache (f346dc6b:
the ids of repeated pre-tokenizer pieces are remembered) — complementary (ours skips encoding up to the last shared
special-token boundary; theirs speeds the pieces that are encoded); both on.

| # | name (commit) | R14 # | what it does | switch (C\*15) | class | gate on v0.1.40.1 (Round 14) | measured on v0.1.40.1 | upstream overlap | assumes about the model | guard |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | side_stash (b33fdeea) | 1 | `--side-stash N`: a short unrelated request runs beside the cached chat | flag, not set (dormant) | serve | – | – (the chat cache is built on its code) | – | none | – |
| 2 | chat_cache (5b4a2e5a) | 2 | other conversations' state parked in RAM, restored on return | `--chat-cache 16 --chat-cache-mib 12288` | serve (exact state) | round trips in the acceptance suite (step 8) | returns to a parked chat in < 1 s (soak) | upstream's #189 `--conversation-cache-mib` (R8: ours switches 0.06–0.18 s faster, 3.5 GB less RAM) | KV / GDN state as upstream serializes it | – |
| 3 | webapp_chats (b539c226) | 3 | web app: chat list, attached files keep their text | always | UI | browser test (step 8) | – | – | none | – |
| 4 | chat_cache_root (81cdf998) | 4 | the chat cache parks the shared-prefix checkpoint | with 2 | (a) | round trips | – | – | none | – |
| 5 | web_search (c2c2310c) | 5 | Web search switch (SearXNG) | config `web_search` | serve | browser + live test | feature | MCP related | Qwen XML tool calls | server check (model_check) |
| 6 | web_search_date (a97a29fb) | 6 | today's date; `www.` = bare host | with 5 | serve | – | – | – | none | – |
| 7 | webapp_tabs (79db478f) | 7 | two tabs keep each other's chats | always | UI | browser test | – | – | none | – |
| 8 | spec_exact (d4a4137e) | 8 | exact speculative sampling (drafter samples from q, rows accepted against p) | `STRATA_SPEC_EXACT=1` | (c) | chi-square ALL PASS (patched tree's kernels, r14 and r14f) | **decode +3.5 %** (acceptance +8.5 %) | – | draft vocabulary ⊂ model ids | spec_exact |
| 9 | side_mixer (e4b00505) | 9 | GDN gates + QSA indexer chain (=1), GDN gate projection + QSA query chain (=2) on branches beside the mixer; **rewritten on 0.1.40's window** (each branch runs upstream's PR-b/d/f operations) | `STRATA_SIDE_MIXER=2` | (a) | pair identical (r14, r14f) | **decode +2.5 %, per round −4.7 %** | none in the verify window (upstream's branch is the drafter's shared expert) | 0.1.39/0.1.40 window: GDN ×3 + QSA, full attention every 4 | side_mixer |
| 10 | commit_652 (de39398d) | 10 | commit only the tokens a window hands out | default on; `STRATA_COMMIT_ALL=1` = off | fix | #652 follow-ups (step 8) | follow-ups resume | **upstream PR #652** (open) | none | – |
| 11 | router_q8k (3f4d6e82) | 11 | A.2: the doorbell writes ggml's Q8_K rows for the CPU pool | `STRATA_ROUTER_Q8K=1` | (a) | pair identical | **LDR +1.4 %, per round −1.0 %** | fork d9ce223 (idea) | n_embd % 256 | router_q8k |
| 12 | router_q8k_round (be5e746e) | 12 | A.2: ggml's nearest_int bit for bit | with 11 | (a) | parity | – | – | as 11 | router_q8k |
| 13 | router_q8k_bsums (9db6964b) | 13 | A.2: bsums of the stored int8 | with 11 | (a) | parity | – | – | as 11 | router_q8k |
| 14 | router_q8k_nan (03950794) | 14 | A.2: x86's default NaN | with 11 | (a) | parity | – | – | as 11 | router_q8k |
| 15 | qsa_split_attn (525bbb6c) | 15 | B.2: decode attention through the int8 tensor-core kernel, split | `STRATA_QSA_SPLIT_ATTN=1` | **(b)** | TF −0.0008 / −0.0006 (r14, r14f) | **LDR +3.0 %, per round −4.6 %** | fork fd23d91 (idea) | head 256, 12 q per KV head | qsa_split_attn |
| 16 | gr_fork (5b4f265c) | 21 | B.1: fork's hyper-connection read (also the final mixer's since 0.1.40's HEAD_MIX_MULTI) | `STRATA_GR_FORK=1` | **(b)** | TF +0.0008 / −0.0026 | LDR +0.8 % / per round −2.2 % vs GR_V3; **vs v0.1.40's default read +6.1 %** | **#783 PR-g multi-token read (ours kept: faster)** | n_embd 2560, 4 streams, low rank 320 | gr_fork |
| 17 | gr_fork_scratch (ac24d406) | 22 | B.1's own scratch (also for 0.1.40's multi head mix) | with 21 | fix | – | – | – | 2 × 26,368 floats | gr_fork |
| 18 | prompt_encoder (8f7615d5) | 23 | the prompt tokenised from the last shared prefix (post-#931 form) | default on; `STRATA_PROMPT_ENCODER_OLD=1` = off | (a) (ids) | server tests; t567 ids (step 8 acceptance: ids 9/9) | TTFT of cached turns (R11: 31K 0.216 → 0.150 s) | **upstream PR #567** (open) | a BPE tokenizer with resume points | – |
| 19 | prompt_encoder_ab (7630c31e) | 24 | the OLD switch | off | test | – | – | – | none | – |
| 20 | prompt_encoder_tests (fab8544d) | 25 | #567's tests, renamed method | – | test | server tests | – | – | none | – |
| 21 | prompt_encoder_931_tests (dd407e48) | 26 | #567's tests with #931 | – | test | server tests | – | #567 head | none | – |
| 22 | patch_guards (c536f5d1) | 27 | startup guards (6 since Round 14) + patch_guard_test | always | (a) (switches) | 6 checked, 0 off (r14f) | – | ours | reads the header | – |
| 23 | nextn_619 (fa103be2) | 29 | reads nextn_predict_layers | always | fix | patched-off = stock | inert here | **#619** | none | – |
| 24 | gr_fork_guard_fix (39e8c729) | 31 | the gr_fork guard ignores the GGUF's hc type | – | test | patch_guard_test | – | ours | – | – |
| 25 | model_check (edcd5385) | 32 | the server's fixed template strings checked at start; **Round 14: only our web search is turned off on a mismatch** (#700 is upstream's code) | always | serve | test_model_check 2/2 | – | ours | tokenizer / template | (the server's guard) |
| 26 | cost_gate (273ec13e) | 33 | a cost-aware draft length: draft d joins while the predicted acceptance product clears θ(d) = rate × the extra time of one more row | `STRATA_COST_GATE=configs/r12-cost-gate.txt` | (c) for sampled requests; (b) for greedy (it regroups windows) | chi-square ALL PASS with 2 gate cases + the negative control (step 4, r14f) | **LDR +2.8 %, decode +3.4 %** (step 4) | – | **its table is fitted to this drafter** (Round 12 recording, v0.1.39's window costs) — refit for a new drafter / model | – (refit, no guard) |
| 27 | b3_guard_drop (a877edce) | – | the B.3 guard goes with B.3: on v0.1.40.2 STRATA_MMVQ_IL is upstream's F4 (on by default), which the guard must not turn off | – | test | guards 5 checked, 0 off | – | F4 = B.3's code | none | removes mmvq_il |

## Dropped in Round 15 (8 of Round 14's 34 rows)

| R14 # | name | why |
|---|---|---|
| 16 | mmvq_il (15d3b5b) | B.3: upstream F4 (ffac97f7) is the same fork code under the same switch STRATA_MMVQ_IL, on by default |
| 17 | mmvq_il_rows (e46f581) | B.3: upstream F4 (ffac97f7) is the same fork code under the same switch STRATA_MMVQ_IL, on by default |
| 18 | mmvq_il_bench (e006ffc) | B.3: upstream F4 (ffac97f7) is the same fork code under the same switch STRATA_MMVQ_IL, on by default |
| 19 | mmvq_il_finite (b0d609c) | B.3: upstream F4 (ffac97f7) is the same fork code under the same switch STRATA_MMVQ_IL, on by default |
| 20 | mmvq_il_table (17d87f0) | B.3: upstream F4 (ffac97f7) is the same fork code under the same switch STRATA_MMVQ_IL, on by default |
| 28 | fused_layout_958 (a11b850) | upstream carries #954's backstop and the fused-layout fix |
| 30 | shard_guard_648 (3b09bc3) | empty on v0.1.40.2: upstream ccfdc2eb is the same change |
| 34 | mmvq_il_table_r14 (60764a4) | B.3: upstream F4 (ffac97f7) is the same fork code under the same switch STRATA_MMVQ_IL, on by default |
