#!/usr/bin/env python3
# AMENDMENT 2026-11-07 (Karl) - it applies from now on, not to finished gates; recorded before the confirmation gap
# (work/r23/gap-confirm0211.sh). Karl, 11-07, on results/r23/port-0211/HUNT-1107.md:
#   "Measurement rule: yes, as a dated amendment applying from now on. Per-workload prompt numbers exclude the
#   chat-cache save. Time the save as its own line in every screen, and judge it separately against its own noise,
#   taking its two-speed pattern into account, so a real regression in saving still shows."
#   "Prompt clock: engine clock for the per-workload prompt numbers, as you recommend. The overall screen rule stays on
#   the client clock minus the save, at -1%. Add one INFO flag, not a fail: if a workload's outside-engine time is worse
#   in all 3 passes by more than its own spread, flag it for review, so a server-side slowdown hitting one workload
#   can't hide under the overall rule. Record the amendment as dated before the confirmation gap."
# The rule as implemented (work/r22/g17_rules.py, section "11-07 park amendment"):
#   - Per-workload prompt numbers exclude the chat-cache save and are taken on the engine clock: prompt tokens / (the
#     engine's prompt ms - the `chat cache: parked ... in N ms` line logged just before that request). They feed Karl
#     11-03's no-loss rule (wl_noloss) and g16's "no workload more than 3 % below".
#   - The overall screen rule (g16's geometric mean, -1 %) stays on the client clock minus the save: prompt tokens /
#     (TTFT - save).
#   - The save is judged as its own "chat-cache save" line (save_rule), against its own noise and with its two levels
#     taken into account. The level mix is INFO.
#   - The outside-engine INFO flag (outside_flags). It is INFO and never changes a verdict.
#     - A workload's outside-engine time per request = client TTFT - the engine's prompt ms. The save is inside the
#       engine figure, so it cancels.
#     - Its spread = the larger of the two arms' half-ranges over their passes.
#     - Flag: every pass of the arm is above the base's mean by more than that spread -> "outside-engine time worse in
#       every pass - for review (INFO)".
# A gate that started before 2026-11-07 14:00 keeps the rules it ran under; so does screen data without engine logs.
# Here: the screen numbers and the per-workload no-loss line (with the INFO flag) come from g17's screen_passes /
# wl_noloss. The SPEED section (U and S against P) also takes the save line: a FAIL is a loss, NOT DECIDED leaves it
# undecided. This file's finished gates keep the verdicts they ran under.
"""ud31_rules.py - r23, Karl's Unsloth Dynamic v3.1 test (approved 11-04: "P, U, S, R; text NLL and KL against R; speed
with the no-loss rule; exactness. Put it after the DeepSeek C gap, once tonight's NLL gap has validated the scorer.").
The rules of work/r23/gap-ud31.sh, WRITTEN 11-04 BEFORE THE GAP RAN, plus the helpers the driver calls. NOTHING SWITCHES:
P028x stays served whatever this says; every verdict below is a measurement for Karl.

REVISED 11-05 (Karl: STRATA_HC_Q8=1 on U, and R; the frozen pack-rounding rule; the decode-path follow-up), STILL BEFORE
ANY RUN of the gap. REVISED AGAIN 11-05 09:xx: the many-positions NLL bound is REVOKED as a gate
(results/r23/nll-many/gap/ADOPTED-BOUND.REVOKED.json; why: results/r23/nll-many/recompute/REPORT.md - 8 distinct texts,
whole-text SE 0.051-0.065 vs its 0.01 cap). Karl: "Basalt a/b, the v3.1 gap and later gates go back to the KL rules.
Report many-positions NLL as information only: whole-text uncertainty, with the 2,048-block figure beside it,
labelled. ... v3.1: carry my frozen rule over to whatever replaces the bound." The quality verdict below is the KL
rules against R at the text level; text NLL is INFO.

ARMS (results/qwen4-kit/unsloth-v31/REPORT.md sections 3, 5, 7; configs written by `configs` from configs/x28h.json)
  P  P028x as served without vision: configs/x28h.json itself (engine-r22p028x); STRATA_HC_Q8 unset = off on CUDA
  U  UD-IQ3_XXS v3.1 as shipped (models/unsloth-v31/UD-IQ3_XXS, 4 shards): pack bringup/out/ud31/pack-u (iq_pack
     --compat-bf16: the Q8_0 hyper-connections and PLE value rounded to BF16), x28h with only --pack, --native (shard 1/4)
     and --ple-gguf (shard 4/4) changed + env STRATA_HC_Q8=1 (Karl 11-05; upstream's run config for every UD-* file on
     CUDA, v0.2.11 setup.py unsloth_default_env :4312-4334); same drafter, switches, --expert-cache-device1 3300, chat cache
  S  the splice: v3.1's 144 routed-expert tensors + our 1,079 other shard-1 tensors (dense, head, embedding) in our ISTA
     shard 1 (work/r15/splice_shard1.py), our shard 2 (the n-gram table) hard-linked; pack bringup/out/ud31/pack-s (no
     --compat-bf16: its dense path is P028x's bit for bit, checked: pack_S_dense); x28h with the three paths changed;
     no switch (its hyper-connections are ours, BF16)
  R  UD-Q4_K_XL from the HF cache: the higher-precision reference of the KL (quality arms only). Pack
     bringup/out/ud31/pack-r (--compat-bf16), x28h's switches and drafter with R's paths in configs/r21-yq-udq4.json's
     memory form (its 71.7 GiB of experts do not fit the RAM): the 5080 alone, --resident-budget-gib 52, chat cache
     2 GiB, STRATA_UNBUFFERED_LOAD=1, no --expert-cache-device1; + env STRATA_HC_Q8=1 (below)

THE HYPER-CONNECTION SWITCH STRATA_HC_Q8=1 (Karl 11-05; read in the served tree strata-r22p028x, 8f7a48aab)
  what it does: native_dense.cpp:46-84 hc_q8_env() (1 = on; unset = off on CUDA). NativeDense::load walks every shard of
     --native (gguf_split_paths, + the PLE shard; generate.cpp:3805, :3841): each Q8_0 tensor named
     blk.N.hc_{attn,ffn}_{down,up,inject}.weight or output_hc_{down,up}.weight gets ITS GGUF BYTES as the Q8_0 copy
     (:404-430). Only a layer down / up row still without one (a BF16 file or pack) is quantized from the pack's BF16 at
     load (:431-466) - the lossy kind. With one dense GPU (no layer split; --expert-cache-device1's helper is none,
     generate.cpp:3592) the layers' BF16 down / up rows are not loaded at all (generate.cpp:4427, add_hc_skip).
  U: its 194 Q8_0 projections (48 layers x down / up x attn / ffn + output_hc_down / up, 675,430,400 B in shard 2; the
     injects F32, the norms F32) are the file's own bytes. The engine says "STRATA_HC_Q8=1: 0.63 GiB of Q8_0
     hyper-connection projections for the verify read"; 0.62 would mean the 192 layer rows quantized from BF16 (the
     final mixer is taken only from a GGUF). Checked per arm from the engine's own log (hcq8_nll_X, hcq8_scr_X1,
     hcq8_dec_U): U and R = the sum of their GGUF's Q8_0 hc bytes (headers) with every layer row Q8_0 in the file;
     P and S = no such line.
  read by the verify / decode read only: verify.cpp:1480 (the layers), :2416 (the final mixer), fused_gr.cu:2625
     launch_q8 - upstream's Q8_0 read, taken before our STRATA_GR_FORK / GR_V3 read (another summation order). So:
     exact7, the screen, score.py's validate window rows (first.<i>) and the decode-path follow-up.
  NOT by the prompt path: prefill.cpp:3747 "this path's GEMMs read bf16, so the matrices are dequantized per half"
     (gr_dequant_q8_0_kernel: bf16_from_f32(fp16 d x int8 q), nearest-even). These are the same BF16 values as the
     pack's --compat-bf16 rounding (gguf-py Q8_0 dequantize = d x q in float32, then ggml's nearest-even BF16), so U's
     and R's prompt rows read their files' Q8_0 hc rounded to BF16 with or without the switch. The offline head reads
     output_hc_* as BF16 from the pack, which is what the prompt path reads. The injects (F32 in U and R) are the pack's
     BF16 on every path: exact when iq_pack found BF16 values (conversions.json; hcforms_X INFO).
  validate_U / validate_R therefore compare the window rows (the file's Q8_0 hc, upstream's read kernel) with the
     offline head on the prompt row (BF16 hc). The switch's own difference (upstream on gfx12: KL 0.0003-0.0010 over the
     noise floor) adds to the batched-vs-window rounding (~0.01-0.02). The thresholds (mean 0.05, each 0.5) are unchanged.
  P and S: off. P stays exactly as served. S's hyper-connections are our ISTA BF16; on a BF16 pack the switch would
     make a Q8_0 copy at load, which is the lossy kind.
  R: on. Karl: "Any reference or exactness rows used for U must be made with the same switch", and R is U's KL
     reference. R's file stores its hyper-connections as U's does (UD-Q4_K_XL headers, read 11-05: 192 layer down / up
     Q8_0 in shards 2-4 + output_hc_down / up Q8_0 in shard 2; injects and norms F32), so the switch reads R's own
     bytes, not the lossy copy. One R serves P, S and U: KL(R || X) uses R's prompt rows, which read the same BF16
     values either way, so P's and S's KL do not depend on this choice.
  exactness rows used for U: e7_U1 and e7_U2, both with U's config (the switch). e7_U1's INFO line against P028x's
     x28h-e7a compares with rows made without it (P as served): INFO only, no verdict rests on it.
  speed: U's screen runs with the switch, as upstream runs UD-* files. P's and S's run without it.
  ASYMMETRY (GGUF tensor types: results/qwen4-kit/unsloth-v31/day1-check/files/*.tensors.tsv; R's headers): our ISTA
     file stores hc_{attn,ffn}_{down,up,inject} and output_hc_{down,up} as BF16 (norms F32). So P / S read their HC
     projections unrounded; U's are rounded at pack time (Q8_0 -> BF16, --compat-bf16; R's too). On the prompt path U
     and R carry a rounding that P and S do not. In KL(R || X), R's side carries it for every X, and for U both sides do.

THE PACK-ROUNDING RULE (Karl 11-05, FROZEN before the gap starts; the driver copies this text to gap/rules.txt at the
start and `decide` flags any later change)
  Why: the prompt path still reads the HC projections as BF16 with STRATA_HC_Q8=1 (above), so U's prompt-path scores
  include the pack's BF16 rounding of the file's Q8_0 HC projections. Upstream measured that rounding as a real cost:
  docs/QUANTS.md "The hyper-connections on NVIDIA": A4000 UD-Q4_K_XL yardstick KL 0.0562 -> 0.0526, p99 0.925 -> 0.716
  with HC_Q8=1; docs/UNSLOTH_Q4.md: perplexity 6-9 % above llama.cpp on Strix Halo, attributed to it.
  - every quality verdict and NLL INFO line of U carries the tag "includes pack rounding (the prompt path reads U's
    Q8_0 HC projections as BF16 from the pack)".
  - CARRIED OVER (11-05) onto the text-level KL verdict that replaces the revoked bound (QUALITY below): if U comes out
    WORSE THAN P, or INSIDE THE MARGIN on either side (ABOVE P or AT OR BELOW P; Karl 11-05: "If U comes out worse than
    P, or inside the margin on the KL rules, record 'includes pack rounding' and set the follow-up flag the same way"),
    the verdict is RECORDED AS "INCLUDES PACK ROUNDING", not as a verdict on the file (decision.json quality.kl_U; the
    class stays in quality.kl_U_class). The decision then says "=> U DECODE-PATH FOLLOW-UP: WANTED"
    (quality.pack_rounding.dec_followup), and work/r23/gap-ud31-dec.sh decides (below). Only BETTER THAN P escapes it:
    the class stands, with the tag, and there is no follow-up ("NOT NEEDED").
  - R's KL rows carry the rounding too (its prompt path reads R's Q8_0 hc as BF16), for every arm. S and P carry none.

THE DECODE-PATH FOLLOW-UP (work/r23/gap-ud31-dec.sh; its rules, written 11-05 before any run)
  runs only when the v3.1 decision says WANTED (decision.json and decision.txt agree) and the decode-path gap's dec arm
  exists (results/r23/decpath/gap/dec: index.json + score.tsv; that gap's run_dec and env_dec PASS; >= 5 texts; x28h,
  logpos, no --env). Else it refuses (exit 1: the series skips it, 8080 untouched).
  U's arm: decpath_rules.py's runner and env check, unchanged (run / envwatch --kind logpos: STRATA_LOGPOS top 64 through
     2-row verify windows, score.py run's yardstick settings). They are called through `dec-run` / `dec-envwatch`, which
     give them dec's own reads: the same texts in the same order, the same cuts, and the same --max-context /
     --short-read (dec's L = its --short-read - 64). The config is U's (STRATA_HC_Q8=1: the verify read takes the
     file's own Q8_0 hc, the final mixer included). A text may be cut further to fit the budget, but not below
     decpath's min cut; positions are compared where both have them. P = dec's rows (x28h as served), NOT rerun.
  checks: env_decU (decpath's env check on U's config, so STRATA_HC_Q8=1 is required); run_decU (rc 0, or rc 2 with the
     finished texts kept); dec_args (U's engine args = dec's except the values of --pack / --native / --ple-gguf, which
     must be U's); hcq8_dec_U (the switch's line, as above).
  positions: every 8th from 1,024 (dec's compare positions), up to cut - 2; both lines' target = the text's next token.
     dec reads the 8 distinct texts (pp4k, rep9k, ldrsyn20k, 32k, tf-long64k, tf-long28k, tf-long112k, tf-long40k).
  THE RULE (Karl 11-05, verbatim: "Use your recommended rule: U vs P on decode-path text NLL, by consistency across the
     8 texts. U lower in at least 6 and higher in at most 1: better. The mirror image: worse. Anything else:
     inconclusive. Whole-text interval beside it, with the 2,048-block figure labelled 'not used for the verdict'. Judge
     only texts that both U and P have. If fewer than 8 finish, use the same scaled fallback as the decode-path check
     (under 5 texts: not judged). Don't add R to the follow-up. If it comes back inconclusive and the file choice
     actually hinges on it, tell me, and we'll decide on a separate R decode-path gap then."):
     per text t that both U and P have: d_t = mean(NLL_U - NLL_P) over its positions on the decode path; t is "lower"
     if d_t < 0, "higher" if d_t > 0; a tie (|d_t| < 1e-6, e.g. identical rows) counts as neither side.
     N = 8: BETTER THAN P if lower in >= 6 and higher in <= 1; WORSE THAN P if higher in >= 6 and lower in <= 1; else
     INCONCLUSIVE. Fewer texts (N < 8), scaled as the decode-path check scales its own (decpath_rules.py: the same
     proportions, each rounded the demanding way): at least ceil(6N/8) one way, at most floor(N/8) the other ->
     N 7: >= 6 and <= 0; N 6: >= 5 and <= 0; N 5: >= 4 and <= 0; FLAGGED "Karl's rule is written for 8 texts".
     N < 5: NOT JUDGED. INCONCLUSIVE prints "if the file choice hinges on it, Karl decides on a separate R decode-path
     gap". No R is added to the follow-up.
  uncertainty (beside the verdict, never used for it): the pooled d (position-weighted, as score.py) with its WHOLE-TEXT
     bootstrap se / 95 % CI (the texts resampled; 8 texts, crude) and, beside it, the 2,048-token-block figure
     labelled "not used for the verdict" (it also understates ~2.2x, recompute section 2); per length range (1-4K /
     4-16K / 16-32K) the means with the 2,048-block figure only (labelled the same way).
  INFO: top-1 agreement U vs P and KL(P || U) over P's top 64 (quant_quality compare's floor rule, decpath
     kl_top_floor) per text.
  INFO ONLY (no extra engine time) - THE ROUNDING COST per text: rc_t = mean over the positions that all four terms have
     of (U decode - U prompt) - (P decode - P prompt) text NLL, where U decode = this follow-up's U rows; U prompt = the
     v3.1 gap's U many-positions rows (results/r23/ud31/gap/rows.tsv nll_U, U's own offline head); P decode = the
     decode-path gap's dec rows (results/r23/decpath/gap/dec); P prompt = the NLL gap's ref rows (= x28h, byte-identical;
     results/r23/nll-many/gap/rows.tsv nll_ref). P's HC weights are native BF16 on both paths, so rc isolates what the
     BF16 rounding costs U, plus path noise; negative = U's prompt path is worse, relative to its decode path, than P's.
     Reported: per-text values and signs, the pooled value with its whole-text interval and the 2,048-block figure
     (labelled); a cross-check of the v3.1 gap's own P rows against the NLL gap's ref rows (0 expected).
  NO pack-rounding caveat on this verdict: on the decode path U reads its file's Q8_0 hc (the switch) and P its file's
     BF16. Two things remain. The injects are the pack's BF16 (exact, or flagged from pack-u/conversions.json). The hc
     read kernel differs (upstream's Q8_0 read vs our fork's), which is a summation order.
  NOT JUDGED: U's arm not clean (run_decU / env_decU / dec_args / hcq8_dec_U not PASS), no compare result, fewer than
     5 texts that both U and P have, a target mismatch, or no v3.1 KL verdict.

PRECONDITIONS (the driver refuses before the gap opens, exit 1, 8080 untouched, unless all hold)
  predl   all 4 UD-IQ3_XXS shards in models/unsloth-v31/UD-IQ3_XXS/, each size = work/qwen4-kit/unsloth-v31/dl/tree.json's
          and its sha256 = the pinned LFS oid there: the downloader (gentle_dl.py) hashes the stream and writes a
          SHA256SUMS line only after a match - every line must be there, no .part / .bad file. Inside the gap, before
          anything reads them, `rehash` hashes the 4 files again (dl_sha; a mismatch ends the gap at once, nothing runs)
  prenll  the NLL gap validated the scorer: its gates' validate_ref PASS (results/r23/nll-many/gap/gates.txt) - that is
          all (11-05: the bound is revoked and NLL is INFO; ADOPTED-BOUND.json is neither required nor read)
  cfgcheck  U, S, R's configs = configs/x28h.json with only the differences named above (+ "log", "_comment");
          STRATA_ROUTE_TAIL_SKIP=0 in every one; STRATA_HC_Q8=1 in U and R, absent in S and in x28h (P); the engine
          is engine-r22p028x
  the driver's own: no gpu-test.lock / other gap / model server other than the 8080 queue's P028x / 8081 listener; the
  kernel watcher; the lossless config check (patchtest.sh lossless) on U and S; >= 100 GB free after the splice

EXACTNESS (U and S; new weights cannot be bit-identical to P028x, so the test is repeatability)
  e7_X1   exact7 at pin 2500 (bringup/lib/exact7.sh: 7 items, --adapt-swaps 0 --suffix-draft 0) against P028x's x28h-e7a:
          INFO (N/7 identical expected low; its slots reported)
  e7_X2   exact7 again, against X1: 7/7 identical + slots MATCHED + 7/7 item outputs -> PASS, else FAIL
  env_e7X1, env_e7X2   each exact7 engine's environment = the config's exactly (decode_rules.py envcli, mode e7)
  lossless_X_cfg (pre-gap) + lossless_X_log (with the arm's first screen engine log): bringup/patchtest.sh lossless PASS
  start_X  g17_rules.py startlines base on the arm's first screen start log (the doorbell Q8_K, exact sampling,
          cumulative draft, cost gate, v2 prompt kernels lines present; none of the unwanted lines) PASS
  hcq8_scr_X  the switch's line in the arm's first screen engine log (U: on, S: off; above) PASS
  S only:  splice_verify (the written shard 1: 1,223 tensors in our order, ours except the 144 experts = v3.1's types,
          our split.* keys, sizes, byte spot checks) PASS; pack_S_dense (pack-s dense.bin and index rows = P028x's
          bringup/out/r20a/pack byte for byte) PASS
  -> REPEATABLE = all PASS; NOT REPEATABLE = e7_X2 FAIL; CHECK FAILED (names) = e7_X2 PASS but another check FAIL;
     VOID = an env gate FAIL; NOT RUN = no e7_X2
  INFO: tok_X (the pack's tokenizer = r20a's; the configs keep r20a's tokenizer path, as P028x)

QUALITY - a QUANT COMPARISON, NOT A LOSSLESS GATE: the KL RULES AGAINST R, AT THE TEXT LEVEL (11-05). LOWER KL against
R is better (closer to the higher-precision quant). Text NLL is INFO only.
  data    score.py run CONFIG nll/ARM --set long11 --rows all:8 for P, U, S, R (one cold read of the 11 long texts,
          every 8th batched prompt row; run_X + env_X gates as the NLL gap's; hcq8_nll_X: the switch's line in the
          arm's engine stderr, U and R on, P and S off)
  heads   each arm's own head applied offline: output_hc_{norm,down,up} from ITS pack's dense.bin (what its prompt
          path reads: U's / R's are the --compat-bf16 BF16 roundings of their Q8_0 tensors) and output.weight from ITS
          GGUF (Q6_K for P / S / U, Q8_0 for R). score.py's own Head reads only our ISTA GGUF, so it is right only for
          P and S
  validate_X  score.py's validate step per arm with the arm's own head (the engine's window rows at the 5 check prompts
          vs the offline head on the full read's row): mean KL <= 0.05, each <= 0.5 -> PASS (an arm's numbers count only
          with run_X, env_X, validate_X and hcq8_nll_X PASS). head_P: score.py validate itself (its own head) on P
          gives the same 5 KL values as the per-arm head on P (to 1e-9) -> PASS; without head_P PASS + validate_P PASS:
          QUALITY NOT JUDGED
  texts   the compare's rows.tsv (every 8th row from 1,024 of the 11 long texts; `compare` writes it), DEDUPLICATED as
          the recompute did (Karl's rule): keep 32k and tf-long64k; drop pp32k (= 32k), tf-long96k (= tf-long64k over
          the scored 32,768 tokens) and pp8k (= 32k's first 8,011 tokens) -> the 8 distinct texts 32k, tf-long28k,
          tf-long40k, tf-long64k, tf-long112k, pp4k, ldrsyn20k, rep9k (~22,600 positions). The text is the unit.
  metrics the KL rules' four (kernel_rule2/3), per text t and arm X in P, U, S: mean KL(R || X), p90 KL(R || X), rows
          with KL(R || X) > 1, changed top-1 against R's top-1 (full vocabulary, each arm's own head)
  per text, X vs P (written 11-05 before any run): worse if X_t > 1.10 x P_t (+ 1 for the two counts), better if
          P_t > 1.10 x X_t (+ 1 for the counts), else inside; a text where both arms are below the floor (mean / p90
          0.01 nats, counts 5) is inside (uninformative: rep9k's KL is ~1e-4 in every arm, so its ratios are noise).
          Why 1.10: it is the KL rules' own tolerance (candidate <= 1.10 x the reference). Why the + 1: per-text counts
          are small (pp4k: 384 positions); the pooled rule's "+ 1" alone would turn every count change into a side.
  per metric over the 8 texts: WORSE if worse on >= 6 and better on <= 1; BETTER if better on >= 6 and worse on <= 1;
          else INSIDE THE MARGIN. Why 6 of 8 (calibrated 11-05 on the recompute's rows of these 8 texts, all against
          ref; re-checked in the selftest): the NLL gap's two rounding references (cpushare vs unfused, either way) are
          beyond the 1.10 margin on at most 3 texts on one side per metric (mean 2, p90 2, KL > 1 rows 1, top-1 3), and
          v2 (another prompt kernel the KL rules pass) vs either on at most 5 (p90) - so 6 is not reached by rounding
          or a passing kernel change; 7 of 8 would let one short or near-zero text (pp4k, rep9k) veto a clear result.
  X vs P (the verdict): WORSE THAN P if any of the four metrics is WORSE (the KL rules fail on any check); BETTER THAN
          P if the mean is BETTER and no metric WORSE; else INSIDE THE MARGIN - ABOVE P if X's pooled mean KL (over the
          8 texts' positions) exceeds P's, else AT OR BELOW P. For U the pack-rounding rule acts on this verdict (above).
  uncertainty (INFO, labelled): the pooled ratio mean KL(R || X) / mean KL(R || P) and the pooled difference with the
          WHOLE-TEXT bootstrap 95 % CI (texts resampled with replacement, 10,000 replicates, seed 20261104; 8 texts,
          crude) and, beside it, the 2,048-TOKEN-BLOCK bootstrap figure (labelled: it understates ~2.2x).
  text NLL  INFO only: per arm and text the mean NLL of the text's own next token; per X in U, S, R: d_X = pooled
          mean(NLL_X - NLL_P) with its WHOLE-TEXT se / CI and the 2,048-block se / CI beside it (labelled), the per-text
          d and how many texts are lower / higher. No verdict.
  No R (run / env / validate / hcq8 not PASS) or no rows.tsv -> QUALITY NOT JUDGED.
  INFO    U against S (the mean metric's per-text counts, the pooled ratio): Unsloth's whole file vs its experts at
          equal bytes in our file

SPEED (Karl's no-loss rule; U and S against P on the same build)
  the 9-workload screen (work/r22/abarm.sh: W1-W3, agent x2, research4 x4; a warm-up first), 3 passes in turned order
  (P U S, S U P, U S P), a fresh test server each (with_server.sh; env checked: g17_rules.py envcheck --ngpu 2)
  NO LOSS = g17_rules.py wl_noloss (Karl 11-03): for every workload, decode AND prompt tok/s each, the arm's pass mean
          >= P's pass mean x (1 - the larger of the two arms' pass-to-pass spreads there); one workload slower beyond
          its noise -> LOSS (listed); fewer than 2 passes of a workload -> NOT DECIDED. VOID = an env_scr / fatal_scr /
          hcq8_scr gate of the arm or of P FAIL. INFO: the screen geomeans (decode, prompt) vs P, the 5080 slots.

Every line ends "NOTHING SWITCHES": P028x stays served; any use of v3.1 is Karl's call.

Subcommands: configs OUTDIR | cfgcheck OUTDIR | predl DIR TREE | rehash DIR TREE | prenll ROOT | heads CONFIG... |
  validate OUTDIR CONFIG | headcheck SCOREPY_TXT VALIDATE_JSON | compare ROOT --cfg ARM=CONFIG ... | dirty |
  hcline LOG CONFIG --want on|off | hcforms PACK | rules --out F | decide ROOT | dec-pre | dec-run CONFIG OUTDIR |
  dec-envwatch JOB CONFIG | dec-args UDIR | dec-compare UDIR | dec-decide DIR | selftest [--dir D]
  (most take --gate NAME --gates FILE). Python: .venv/bin/python -I -B (numpy).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import sys
import time
from pathlib import Path


def _threads_from_argv() -> None:   # BLAS threads must be set before numpy loads (as score.py)
    n = "1"
    for i, a in enumerate(sys.argv):
        if a == "--threads" and i + 1 < len(sys.argv):
            n = sys.argv[i + 1]
    for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(k, n)


_threads_from_argv()
import numpy as np  # noqa: E402

sys.dont_write_bytecode = True
WS = Path("/home/USER/ai-speed-testing/strata-compare")
SCORE = WS / "work/r23/nll-many/score.py"
G17 = WS / "work/r22/g17_rules.py"
GGUF_TOOLS = WS / "strata-r22p0210/tools"
NLL_ROOT = WS / "results/r23/nll-many/gap"
X28H = WS / "configs/x28h.json"
EXE = WS / "engine-r22p028x/strata"
P_PACK = WS / "bringup/out/r20a/pack"
U_DIR = WS / "models/unsloth-v31/UD-IQ3_XXS"
U_NAME = "Qwen3.8-Flash-Next-UD-IQ3_XXS-%05d-of-00004.gguf"
S_DIR = WS / "models/unsloth-v31/splice-S"
S_NAME = "Qwen3.8-Flash-Next-UD31x-GSQ-RCO-IQ3_S-%05d-of-00002.gguf"
R_DIR = Path("/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/"
             "38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL")
R_NAME = "Qwen3.8-Flash-Next-UD-Q4_K_XL-%05d-of-00004.gguf"
PACKS = {"U": WS / "bringup/out/ud31/pack-u", "S": WS / "bringup/out/ud31/pack-s", "R": WS / "bringup/out/ud31/pack-r"}
GPU5080 = "GPU-UUID-RTX5080"
N_EMBD, HC, HC_LR, VOCAB = 2560, 4, 320, 248320
D = HC * N_EMBD
# the adopted bound's parameters (nll_rules.py RULE); ADOPTED-BOUND.json's values replace them when present
DEFAULTS = {"min_pos": 1024, "block_tokens": 2048, "boot": 10000, "seed": 20261104, "tol": 1.10, "z_one_sided": 1.645,
            "se_cap": 0.01}
KL_HIGH = 1.0
# 11-05: the hyper-connection switch, the pack-rounding rule and the decode-path follow-up
HC_SWITCH = {"U": "1", "R": "1"}                  # STRATA_HC_Q8 per arm; absent = off (P, S)
N_LAYERS = 48
PACK_TAG = "includes pack rounding (the prompt path reads U's Q8_0 HC projections as BF16 from the pack)"
FOLLOW_MARK = "=> U DECODE-PATH FOLLOW-UP: "
HCQ8_RE = re.compile(r"STRATA_HC_Q8=1: ([0-9.]+) GiB of Q8_0 hyper-connection projections for the verify read")
TREE = WS / "work/qwen4-kit/unsloth-v31/dl/tree.json"
UD31 = WS / "results/r23/ud31"
DECPATH = WS / "work/r23/decpath_rules.py"
PDEC = WS / "results/r23/decpath/gap/dec"
DEC_PLAN = "ud31dec"
DEC_EVERY, DEC_MIN_POS = 8, 1024
DEC_STRATA = [("1-4K", 1024, 4096), ("4-16K", 4096, 16384), ("16-32K", 16384, 32768)]
THIN_N, THIN_T = 500, 2
# 11-05 (the NLL bound revoked): the text-level KL rules - all written before any run (the docstring says why)
DUP_TEXTS = ("pp32k", "tf-long96k", "pp8k")       # the recompute's dedup: 32k, tf-long64k kept
KL_TOL = 1.10                                      # the KL rules' tolerance
WIN_N, OTHER_MAX = 6, 1                            # of the 8 texts: >= 6 on one side and <= 1 on the other
METRICS = ("mean", "p90", "high", "flips")
COUNT_METRICS = ("high", "flips")
FLOOR = {"mean": 0.01, "p90": 0.01, "high": 5, "flips": 5}
DEC_MIN_TEXTS = 5                                  # the follow-up (Karl 11-05): under 5 texts both have -> not judged
DEC_TIE = 1e-6                                     # |mean NLL_U - NLL_P| below this on a text = a tie (neither side)
NLL_ROWS = NLL_ROOT / "rows.tsv"                   # P prompt for the rounding cost: the NLL gap's ref (= x28h) rows
RECOMP_ROWS = WS / "work/r23/scratch-recompute/nll-dedup.tsv"       # the recompute's deduplicated rows (read only)
NOTE_SWITCH = "NOTHING SWITCHES: P028x stays served; any use of v3.1 is Karl's call."
NOTE_QUANT = ("A QUANT COMPARISON, NOT A LOSSLESS GATE, judged by the KL RULES AGAINST R AT THE TEXT LEVEL (11-05; the "
              "many-positions NLL bound is revoked, text NLL is INFO): lower KL against R is better")


# ------------------------------------------------------------------------------------------------ small helpers
def gate(a, status, detail):
    if getattr(a, "gates", None) and getattr(a, "gate", None):
        with open(a.gates, "a") as f:
            f.write(f"{a.gate} {status} {detail} [ud31 {time.strftime('%m-%d %H:%M')}]\n")


def read_gates(p):
    g = {}
    p = Path(p)
    for line in p.read_text().splitlines() if p.exists() else []:
        k, _, rest = line.partition(" ")
        s, _, det = rest.partition(" ")
        g[k] = (s, det)
    return g


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_SCORE = None


def score():
    global _SCORE
    if _SCORE is None:
        _SCORE = load("score_nll", SCORE)
    return _SCORE


def gguf_reader():
    if str(GGUF_TOOLS) not in sys.path:
        sys.path.insert(0, str(GGUF_TOOLS))
    import gguf_reader as G   # header reader only (no ggml)
    return G


def argval(args, flag):
    v = [args[i + 1] for i, x in enumerate(args[:-1]) if x == flag]
    return v[-1] if v else None


def shards_of(first: Path):
    m = re.search(r"-(\d{5})-of-(\d{5})\.gguf$", first.name)
    if not m:
        return [first]
    n = int(m[2])
    return [first.with_name(first.name[:m.start()] + "-%05d-of-%05d.gguf" % (i, n)) for i in range(1, n + 1)]


def bound_params(path=None):
    """the statistics' parameters: this file's DEFAULTS (11-05: the NLL bound is revoked, ADOPTED-BOUND.json is not read;
    `path` is accepted and ignored so old command lines still parse)"""
    out = dict(DEFAULTS)
    out["source"] = "work/r23/ud31_rules.py DEFAULTS (the many-positions NLL bound is revoked 11-05; not read)"
    return out


# ------------------------------------------------------------------------------------------------ the arm configs
def arm_configs():
    """the three derived configs, from configs/x28h.json (never edited)"""
    base = json.loads(X28H.read_text())
    out = {}

    def swap(args, pack, native, ple):
        a = list(args)
        for flag, val in (("--pack", pack), ("--native", native), ("--ple-gguf", ple)):
            i = a.index(flag)
            a[i + 1] = str(val)
        return a
    u = json.loads(json.dumps(base))
    u["args"] = swap(base["args"], PACKS["U"], U_DIR / (U_NAME % 1), U_DIR / (U_NAME % 4))
    u["env"] = dict(base["env"], STRATA_HC_Q8=HC_SWITCH["U"])
    u["log"] = str(WS / "logs/engine-ud31-U.log")
    u["_comment"] = ("r23 v3.1 gap arm U (work/r23/gap-ud31.sh, written by ud31_rules.py configs): configs/x28h.json "
                     "with only --pack, --native (shard 1/4) and --ple-gguf (shard 4/4) changed to Unsloth's UD-IQ3_XXS "
                     "v3.1 (pinned d9620119) and its --compat-bf16 pack, + STRATA_HC_Q8=1 (Karl 11-05: the verify read "
                     "takes the GGUF's own Q8_0 hyper-connection projections, as upstream runs UD-* files); a test arm, "
                     "never served")
    out["U"] = u
    s = json.loads(json.dumps(base))
    s["args"] = swap(base["args"], PACKS["S"], S_DIR / (S_NAME % 1), S_DIR / (S_NAME % 2))
    s["log"] = str(WS / "logs/engine-ud31-S.log")
    s["_comment"] = ("r23 v3.1 gap arm S (work/r23/gap-ud31.sh): configs/x28h.json with only the three paths changed to "
                     "the splice (v3.1's 144 routed experts in our ISTA shard 1, work/r15/splice_shard1.py; our shard 2 "
                     "hard-linked) and its pack (no --compat-bf16); a test arm, never served")
    out["S"] = s
    r = json.loads(json.dumps(base))
    a = swap(base["args"], PACKS["R"], R_DIR / (R_NAME % 1), R_DIR / (R_NAME % 2))
    i = a.index("--expert-cache-device1")
    del a[i:i + 2]
    a[a.index("--chat-cache-mib") + 1] = "2048"
    a += ["--resident-budget-gib", "52"]
    r["args"] = a
    r["env"] = dict(base["env"], CUDA_VISIBLE_DEVICES=GPU5080, STRATA_UNBUFFERED_LOAD="1", STRATA_HC_Q8=HC_SWITCH["R"])
    r["log"] = str(WS / "logs/engine-ud31-R.log")
    r["_comment"] = ("r23 v3.1 gap arm R (work/r23/gap-ud31.sh): the KL reference, quality only - Unsloth's UD-Q4_K_XL "
                     "(HF cache 38bb39e) with a fresh --compat-bf16 pack, x28h's switches and drafter in "
                     "configs/r21-yq-udq4.json's memory form (5080 alone, --resident-budget-gib 52, chat cache 2 GiB, "
                     "STRATA_UNBUFFERED_LOAD=1, no --expert-cache-device1), + STRATA_HC_Q8=1 as U (Karl 11-05: reference "
                     "rows used for U are made with U's switch; R's Q8_0 hyper-connections are its file's own); never served")
    out["R"] = r
    return out


def cmd_configs(a):
    o = Path(a.outdir)
    o.mkdir(parents=True, exist_ok=True)
    for k, c in arm_configs().items():
        (o / f"ud31-{k}.json").write_text(json.dumps(c, indent=1) + "\n")
        print(f"wrote {o / f'ud31-{k}.json'}")
    return 0


def cfg_diffs(cfg, base):
    """the differences of a derived config from x28h.json, as readable strings"""
    out = []
    for k in sorted(set(cfg) | set(base)):
        if k in ("args", "env"):
            continue
        if cfg.get(k) != base.get(k):
            out.append(f"key {k}")
    eb, ec = base.get("env", {}), cfg.get("env", {})
    for k in sorted(set(eb) | set(ec)):
        if eb.get(k) != ec.get(k):
            out.append(f"env {k}={ec.get(k, 'unset')}")
    ab, ac = base["args"], cfg["args"]
    flags = lambda a: [x for x in a if x.startswith("--")]
    for f in sorted(set(flags(ab)) | set(flags(ac))):
        vb = argval(ab, f) if f in ab else None
        vc = argval(ac, f) if f in ac else None
        if (f in ab) != (f in ac) or vb != vc:
            out.append(f"arg {f}={vc if f in ac else 'absent'}")
    return out


def cmd_cfgcheck(a):
    base = json.loads(X28H.read_text())
    want = {k: sorted(cfg_diffs(c, base)) for k, c in arm_configs().items()}
    bad = []
    for k in ("U", "S", "R"):
        p = Path(a.outdir) / f"ud31-{k}.json"
        if not p.exists():
            bad.append(f"{p.name} missing")
            continue
        c = json.loads(p.read_text())
        got = sorted(cfg_diffs(c, base))
        allowed = {"U": {"arg --pack", "arg --native", "arg --ple-gguf", "key log", "key _comment", "env STRATA_HC_Q8"},
                   "S": {"arg --pack", "arg --native", "arg --ple-gguf", "key log", "key _comment"},
                   "R": {"arg --pack", "arg --native", "arg --ple-gguf", "key log", "key _comment", "env CUDA_VISIBLE_DEVICES",
                         "env STRATA_UNBUFFERED_LOAD", "arg --expert-cache-device1", "arg --chat-cache-mib",
                         "arg --resident-budget-gib", "env STRATA_HC_Q8"}}[k]
        kinds = {re.sub(r"=.*$", "", x) for x in got}
        if got != want[k]:
            bad.append(f"{p.name} differs from what `configs` writes from today's x28h.json ({'; '.join(sorted(set(got) ^ set(want[k])))[:200]})")
        if not kinds <= allowed:
            bad.append(f"{p.name}: differences beyond the allowed ones: {', '.join(sorted(kinds - allowed))}")
        if c.get("env", {}).get("STRATA_ROUTE_TAIL_SKIP") != "0":
            bad.append(f"{p.name}: STRATA_ROUTE_TAIL_SKIP not 0")
        if c.get("env", {}).get("STRATA_HC_Q8") != HC_SWITCH.get(k):     # Karl 11-05: U and R on, S off (absent)
            bad.append(f"{p.name}: STRATA_HC_Q8={c.get('env', {}).get('STRATA_HC_Q8', 'unset')} "
                       f"(want {HC_SWITCH.get(k, 'unset')})")
        if os.path.realpath(c["exe"]) != os.path.realpath(EXE):
            bad.append(f"{p.name}: exe is not engine-r22p028x")
    if base.get("env", {}).get("STRATA_HC_Q8", "0") != "0":              # P = x28h as served, the switch off
        bad.append(f"configs/x28h.json sets STRATA_HC_Q8={base['env']['STRATA_HC_Q8']} (P must run as served, off)")
    line = ("U, S, R configs = configs/x28h.json + only their named differences; tail skip 0; STRATA_HC_Q8=1 in U and "
            "R only (P = x28h and S off); engine-r22p028x" if not bad else "; ".join(bad))
    print(("CFG OK: " if not bad else "CFG FAIL: ") + line)
    gate(a, "PASS" if not bad else "FAIL", line[:300])
    return 0 if not bad else 1


# ------------------------------------------------------------------------------------------------ the download
def pinned(tree, prefix="UD-IQ3_XXS/"):
    return {Path(e["path"]).name: (int(e["lfs"]["size"]), e["lfs"]["oid"]) for e in json.loads(Path(tree).read_text())
            if e.get("type") == "file" and e.get("lfs") and e["path"].startswith(prefix) and e["path"].endswith(".gguf")}


def cmd_predl(a):
    d = Path(a.dir)
    pin = pinned(a.tree)
    sums = {}
    p = d / "SHA256SUMS"
    for line in p.read_text().splitlines() if p.exists() else []:
        f = line.split()
        if len(f) == 2:
            sums[f[1]] = f[0]
    bad = []
    if len(pin) != 4:
        bad.append(f"tree.json pins {len(pin)} UD-IQ3_XXS files, not 4")
    for n, (size, oid) in sorted(pin.items()):
        f = d / n
        if not f.exists():
            bad.append(f"{n} missing")
            continue
        if f.stat().st_size != size:
            bad.append(f"{n} {f.stat().st_size:,} B (pinned {size:,})")
        if sums.get(n) != oid:
            bad.append(f"{n}: no SHA256SUMS line with the pinned oid {oid[:12]}")
    extra = sorted(x.name for x in d.glob("*.part")) + sorted(x.name for x in d.glob("*.bad")) if d.exists() else []
    if extra:
        bad.append("unfinished / failed files: " + ", ".join(extra))
    line = (f"{len(pin)} shards, sizes and SHA256SUMS = tree.json's pinned LFS oids (the downloader's stream hashes)"
            if not bad else "; ".join(bad))
    print(("DOWNLOAD OK: " if not bad else "DOWNLOAD NOT READY: ") + line)
    gate(a, "PASS" if not bad else "FAIL", line[:300])
    return 0 if not bad else 1


def sha_file(path, chunk=16 << 20):
    h, n = hashlib.sha256(), 0
    with open(path, "rb") as f:
        fd = f.fileno()
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
            n += len(b)
            if n % (1 << 30) < chunk:
                os.posix_fadvise(fd, 0, n, os.POSIX_FADV_DONTNEED)   # keep the page cache clean as it reads
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    return h.hexdigest(), n


def cmd_rehash(a):
    d = Path(a.dir)
    pin = pinned(a.tree)
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        got = dict(zip(sorted(pin), ex.map(lambda n: sha_file(d / n) if (d / n).exists() else ("missing", 0), sorted(pin))))
    bad = [f"{n}: {got[n][0][:12]} ({got[n][1]:,} B), pinned {oid[:12]} ({size:,} B)" for n, (size, oid) in sorted(pin.items())
           if got[n] != (oid, size)]
    line = (f"{len(pin)} shards re-hashed in {time.time() - t0:.0f} s: sha256 = the pinned oids" if not bad else "; ".join(bad))
    print(("SHA OK: " if not bad else "SHA MISMATCH: ") + line)
    gate(a, "PASS" if not bad else "FAIL", line[:300])
    return 0 if not bad else 1


# ------------------------------------------------------------------------------------------------ the NLL gap
def cmd_prenll(a):
    """11-05: only that the NLL gap validated the scorer (validate_ref PASS). The bound is revoked and NLL is INFO, so
    ADOPTED-BOUND.json (gone) and the gap's decision status are not required; the revocation is named when on file"""
    root = Path(a.root)
    why = []
    v = read_gates(root / "gates.txt").get("validate_ref", ("MISSING", ""))
    if v[0] != "PASS":
        why.append(f"validate_ref {v[0]} in {root / 'gates.txt'} (the offline head is not shown to agree with the engine)")
    rv = root / "ADOPTED-BOUND.REVOKED.json"
    note = "; the bound REVOKED 11-05 (ADOPTED-BOUND.REVOKED.json): NLL is INFO" if rv.exists() else ""
    line = (f"the NLL gap validated the scorer (validate_ref PASS: {v[1][:90]}){note}" if not why else "; ".join(why))
    print(("NLL OK: " if not why else "NLL NOT VALIDATED: ") + line)
    gate(a, "PASS" if not why else "FAIL", line[:400])
    return 0 if not why else 1


# ------------------------------------------------------------------------------------------------ per-arm heads
def pack_index(pack: Path):
    rows = {}
    for line in (pack / "index.txt").read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        f = line.split()
        rows[f[0]] = {"kind": int(f[2]), "off": int(f[3]), "n": int(f[4]), "ne0": int(f[7]), "ne1": int(f[8])}
    return rows


HC_NEED = {"output_hc_norm.weight": (2, D * 4), "output_hc_down.weight": (4, D * HC_LR * 2),
           "output_hc_up.weight": (4, D * HC_LR * 2)}
OUT_BYTES = {"Q6_K": VOCAB * (N_EMBD // 256) * 210, "Q8_0": VOCAB * (N_EMBD // 32) * 34}


def out_weight(native: Path):
    """(shard path, absolute offset, type, shape) of output.weight among the model's shards (headers only)"""
    G = gguf_reader()
    for p in shards_of(native):
        g = G.GGUFFile(p)
        for t in g.tensors:
            if t.name == "output.weight":
                return p, g.data_start + t.offset, t.type_name, list(t.shape)
    raise SystemExit(f"{native.name}: no output.weight in its shards")


def head_sources(cfg_path):
    cfg = json.loads(Path(cfg_path).read_text())
    pack, native = Path(argval(cfg["args"], "--pack")), Path(argval(cfg["args"], "--native"))
    ow = out_weight(native)
    if ow[2] not in OUT_BYTES or ow[3] != [N_EMBD, VOCAB]:
        raise SystemExit(f"{cfg_path}: output.weight {ow[2]} {ow[3]} (the head reads Q6_K or Q8_0 [2560, 248320])")
    idx = pack_index(pack)
    for k, (kind, n) in HC_NEED.items():
        r = idx.get(k)
        if r is None or r["kind"] != kind or r["n"] != n:
            raise SystemExit(f"{pack}: {k} is {r} in index.txt (want kind {kind}, {n} B in dense.bin)")
    return {"pack": pack, "out": ow, "hc": {k: idx[k] for k in HC_NEED}}


def read_at(path, off, n):
    with open(path, "rb") as f:
        f.seek(off)
        b = f.read(n)
    if len(b) != n:
        raise SystemExit(f"{path}: short read at {off}")
    return b


def dequant_q8_0(raw: np.ndarray) -> np.ndarray:
    """ggml's dequantize_row_q8_0 on (nb, 34) uint8 blocks -> (nb, 32) float32: y = qs[j] * fp16 d"""
    raw = np.ascontiguousarray(raw, dtype=np.uint8).reshape(-1, 34)
    d = raw[:, :2].copy().view(np.float16).astype(np.float32)
    return d * raw[:, 2:].copy().view(np.int8).astype(np.float32)


def dequant_q8_0_scalar(blk: bytes):
    d = np.float32(np.frombuffer(blk[:2], np.float16)[0])
    return [float(np.float32(np.float32(x - 256 if x > 127 else x) * d)) for x in blk[2:34]]


def head_key(src):
    h = hashlib.sha256()
    for k in HC_NEED:
        r = src["hc"][k]
        h.update(read_at(src["pack"] / "dense.bin", r["off"], r["n"]))
    p, off, ty, _ = src["out"]
    h.update(ty.encode())
    h.update(read_at(p, off, OUT_BYTES[ty]))
    return h.hexdigest()[:16]


def build_head(src):
    S = score()
    hc = {k: read_at(src["pack"] / "dense.bin", r["off"], r["n"]) for k, r in src["hc"].items()}
    w_norm = np.frombuffer(hc["output_hc_norm.weight"], np.float32).copy()
    w_down = S.bf16_to_f32(np.frombuffer(hc["output_hc_down.weight"], np.uint16)).reshape(HC_LR, D)
    w_up = S.bf16_to_f32(np.frombuffer(hc["output_hc_up.weight"], np.uint16)).reshape(D, HC_LR)
    p, off, ty, _ = src["out"]
    raw = np.frombuffer(read_at(p, off, OUT_BYTES[ty]), np.uint8)
    W = np.empty((VOCAB, N_EMBD), np.float32)
    if ty == "Q6_K":
        nb, bs, deq = N_EMBD // 256, 210, S.dequant_q6_k
    else:
        nb, bs, deq = N_EMBD // 32, 34, dequant_q8_0
    raw = raw.reshape(VOCAB * nb, bs)
    for v0 in range(0, VOCAB, 8192):
        v1 = min(VOCAB, v0 + 8192)
        W[v0:v1] = deq(raw[v0 * nb:v1 * nb]).reshape(v1 - v0, N_EMBD)
    return S.Head(weights=(w_norm, w_down, w_up, W, N_EMBD, HC, HC_LR))


def cmd_heads(a):
    for c in a.config:
        s = head_sources(c)
        p, off, ty, sh = s["out"]
        print(f"{Path(c).name}: hc from {s['pack']}/dense.bin "
              + ", ".join(f"{k.split('.')[0]} kind {r['kind']} @{r['off']}" for k, r in s["hc"].items())
              + f"; output.weight {ty} {sh} in {p.name} @{off}" + (f"; key {head_key(s)}" if a.key else ""))
    return 0


# ------------------------------------------------------------------------------------------------ the hc switch (11-05)
def hc_role(name):
    """the hyper-connection role of a tensor name (native_dense.cpp hc_q8_name's set + the norms), or None"""
    if name in ("output_hc_down.weight", "output_hc_up.weight"):
        return "output down/up"
    if name == "output_hc_norm.weight":
        return "output norm"
    m = re.match(r"blk\.\d+\.hc_(attn|ffn)_(down|up|inject|norm)\.weight$", name)
    return None if m is None else {"down": "down/up", "up": "down/up", "inject": "inject", "norm": "norm"}[m[2]]


def hc_header(native):
    """a model's hyper-connection tensors from its GGUF headers: {role: {type: count}} and what NativeDense uploads as
    the file's own Q8_0 copy under STRATA_HC_Q8=1 (native_dense.cpp:404-430: Q8_0, an hc_q8_name, 2-D; the F32 injects
    stay unless STRATA_HC_Q8_INJECT=1)"""
    G = gguf_reader()
    forms, q8b, q8n, layer_q8 = {}, 0, 0, 0
    for p in shards_of(Path(native)):
        for t in G.GGUFFile(p).tensors:
            r = hc_role(t.name)
            if r is None:
                continue
            forms.setdefault(r, {})
            forms[r][t.type_name] = forms[r].get(t.type_name, 0) + 1
            if t.type_name == "Q8_0" and not r.endswith("norm") and len(t.shape) == 2:
                q8b += t.expected_bytes()
                q8n += 1
                layer_q8 += r == "down/up"
    return {"forms": forms, "q8_bytes": q8b, "q8_tensors": q8n, "layer_q8": layer_q8}


def hcline_check(txt, cfg, want):
    """(ok, line): the engine's STRATA_HC_Q8 line(s) in a log against the arm's switch and its GGUF headers"""
    got = HCQ8_RE.findall(txt)
    env = cfg.get("env", {}).get("STRATA_HC_Q8")
    if want == "off":
        ok = not got and env in (None, "0")
        return ok, ("no STRATA_HC_Q8 line, the config's switch off: the hc projections as the file / pack store them"
                    if ok else f"{len(got)} STRATA_HC_Q8 line(s) ({', '.join(got)} GiB), config STRATA_HC_Q8={env or 'unset'}: "
                    "the switch acted on an arm that must run without it")
    h = hc_header(argval(cfg["args"], "--native"))
    gib = f"{h['q8_bytes'] / 2 ** 30:.2f}"
    full = h["layer_q8"] == 4 * N_LAYERS
    ok = bool(got) and all(g == gib for g in got) and full and env == "1"
    return ok, (f"{len(got)} engine start(s) with 'STRATA_HC_Q8=1: {', '.join(got) or '-'} GiB of Q8_0 hyper-connection "
                f"projections'; the GGUF's own Q8_0 hc: {h['q8_tensors']} tensors, {h['q8_bytes']:,} B = {gib} GiB, "
                f"{h['layer_q8']} of {4 * N_LAYERS} layer down/up rows Q8_0 in the file"
                + ("" if ok else " -> NOT the file's own bytes as configured (or no line)"))


def cmd_hcline(a):
    cfg = json.loads(Path(a.config).read_text())
    p = Path(a.log)
    if p.exists():
        ok, line = hcline_check(p.read_text(errors="replace"), cfg, a.want)
    else:
        ok, line = False, f"no log {p}"
    line = f"{Path(a.config).name} ({a.want}): {line}"
    print(("HCQ8 OK: " if ok else "HCQ8 FAIL: ") + line)
    gate(a, "PASS" if ok else "FAIL", line[:300])
    return 0 if ok else 1


def hc_conversions(pack):
    """pack/conversions.json's hyper-connection records: {"ROLE SRC->DST exact|rounded": count}, compat_bf16"""
    j = json.loads((Path(pack) / "conversions.json").read_text())
    out = {}
    for r in j.get("tensors", []):
        role = hc_role(r.get("name", ""))
        if role is None:
            continue
        k = f"{role} {r.get('src_type')}->{r.get('dst_type')} {'exact' if r.get('exact') else 'rounded'}"
        out[k] = out.get(k, 0) + 1
    return out, j.get("compat_bf16")


def cmd_hcforms(a):
    try:
        c, cb = hc_conversions(a.pack)
    except (OSError, ValueError) as e:
        line = f"{a.pack}: no conversions.json ({e})"
        print(line)
        gate(a, "INFO", line[:300])
        return 1
    ri = sum(v for k, v in c.items() if k.startswith("inject") and k.endswith("rounded"))
    line = (f"{Path(a.pack).name} (compat_bf16 {cb}): hc conversions "
            + (", ".join(f"{v} {k}" for k, v in sorted(c.items())) or "none (stored as the engine reads them)")
            + (f"; {ri} inject row(s) ROUNDED at pack time (read from the pack on every path)" if ri else ""))
    print(line)
    gate(a, "INFO", line[:300])
    return 0


def rules_text():
    return __doc__.split("\nSubcommands:")[0].rstrip() + "\n"


def cmd_rules(a):
    Path(a.out).write_text(rules_text())
    print(f"wrote {a.out} (sha {hashlib.sha256(Path(a.out).read_bytes()).hexdigest()[:12]})")
    return 0


# ------------------------------------------------------------------------------------------------ validate (per arm)
def cmd_validate(a):
    S = score()
    d = Path(a.outdir)
    head = build_head(head_sources(a.config))
    rows = []
    for name, fw, row, tg in S.validation_pairs(d):
        if fw is None or row is None:
            rows.append({"name": name, "kl": None})
            continue
        lw = np.fromfile(fw, dtype=np.float32).astype(np.float64)
        lw -= lw.max()
        lw -= np.log(np.exp(lw).sum())
        lh = head.logp(row[None, :])[0]
        rows.append({"name": name, "kl": float((np.exp(lw) * (lw - lh)).sum()), "top1_same": bool(lw.argmax() == lh.argmax()),
                     "nll_window": float(-lw[tg]), "nll_head": float(-lh[tg])})
    ok = [r for r in rows if r["kl"] is not None]
    for r in rows:
        print(f"{r['name']:32s} " + ("no data" if r["kl"] is None else
                                     f"KL(window || offline head) {r['kl']:.5f}  top-1 {'same' if r['top1_same'] else 'DIFFERS'}  "
                                     f"NLL window {r['nll_window']:.4f} head {r['nll_head']:.4f}"))
    good = bool(ok) and len(ok) == len(rows) and float(np.mean([r["kl"] for r in ok])) <= a.kl_mean and \
        all(r["kl"] <= a.kl_max for r in ok)
    line = (f"offline head (the arm's own: {Path(a.config).name}) {'AGREES' if good else 'DOES NOT AGREE'} with the engine's "
            f"window rows ({len(ok)} of {len(rows)} checks, mean KL {np.mean([r['kl'] for r in ok]) if ok else float('nan'):.5f}; "
            f"<= {a.kl_mean} mean, <= {a.kl_max} each)")
    print(line)
    if a.json:
        Path(a.json).write_text(json.dumps({"rows": rows, "agrees": good, "config": a.config}, indent=1))
    gate(a, "PASS" if good else "FAIL", line[:300])
    return 0 if good else 1


def cmd_headcheck(a):
    """score.py validate's own lines (its own head = our ISTA GGUF) against the per-arm head's JSON on P: equal KL"""
    sp = {}
    for line in Path(a.scorepy).read_text(errors="replace").splitlines() if Path(a.scorepy).exists() else []:
        m = re.match(r"^(\S+)\s+KL\(window \|\| offline head\) ([0-9.eE+-]+)", line)
        if m:
            sp[m[1]] = float(m[2])
    mine = {r["name"]: r["kl"] for r in json.loads(Path(a.vjson).read_text())["rows"]} if Path(a.vjson).exists() else {}
    diff = [f"{n}: score.py {sp.get(n)} vs {mine.get(n)}" for n in sorted(set(sp) | set(mine))
            if n not in sp or mine.get(n) is None or abs(round(mine[n], 5) - sp[n]) > 1e-9]
    ok = bool(sp) and not diff
    line = (f"P: score.py's own head and the per-arm head give the same KL at all {len(sp)} checks (5 decimals)" if ok
            else ("no data" if not sp else "; ".join(diff)[:250]))
    print(("HEAD CHECK OK: " if ok else "HEAD CHECK FAILED: ") + line)
    gate(a, "PASS" if ok else "FAIL", line)
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------------ compare
def measure(root, arms, heads, pos_arm, ref, prm, ids_of, chunk=128):
    """one pass over the dumps: per position the text NLL of every arm in `arms` (each with heads[arm]) and, when ref is
    one of them, KL(ref || arm) and the changed top-1 against ref. Positions: pos_arm's kept rows from min_pos on."""
    S = score()
    root = Path(root)
    idx = {x: json.loads((root / x / "index.json").read_text()) for x in set(arms) | {pos_arm}}
    texts = [r for r in idx[pos_arm]["requests"] if r["kind"] == "text" and r.get("rows")]
    out = {"keys": [], "block": [], "nll": {x: [] for x in arms}, "kl": {x: [] for x in arms if x != ref},
           "flip": {x: [] for x in arms if x != ref}}
    for r in texts:
        ids = ids_of(r["file"])[:r["cut"]]
        pos0, _ = S.rows_of(root / pos_arm, r)
        sel = np.nonzero((pos0 >= prm["min_pos"]) & (pos0 + 1 < len(ids)))[0]
        want = [int(pos0[j]) for j in sel]
        data = {}
        for x in arms:
            q = next((q for q in idx[x]["requests"] if q["name"] == r["name"] and q.get("rows")), None)
            if q is None:
                raise SystemExit(f"{x}: no dump for {r['name']}")
            px, Rx = S.rows_of(root / x, q)
            where = {int(v): j for j, v in enumerate(px)}
            miss = [p for p in want if p not in where]
            if miss:
                raise SystemExit(f"{x} {r['name']}: rows missing at {miss[:5]}")
            data[x] = (Rx, [where[p] for p in want])
        for c0 in range(0, len(want), chunk):
            ps = want[c0:c0 + chunk]
            tg = np.array([ids[p + 1] for p in ps])
            P_ = np.arange(len(ps))
            z = {}
            if ref is not None:
                Rr, wr = data[ref]
                zr = heads[ref].logits(np.asarray(Rr[wr[c0:c0 + chunk]], np.float32))
                er, lser, sr = S.lse_rows(zr)
                pr = er / sr[:, None].astype(np.float32)
                del er
                ar = zr.argmax(axis=1)
                z[ref] = (zr, lser)
            for x in arms:
                if x == ref:
                    zx, lsex = z[ref]
                else:
                    Rx, wx = data[x]
                    zx = heads[x].logits(np.asarray(Rx[wx[c0:c0 + chunk]], np.float32))
                    lsex = S.lse_rows(zx)[1]
                out["nll"][x] += (lsex - zx[P_, tg]).tolist()
                if ref is not None and x != ref:
                    kl = (pr * (zr - zx)).sum(axis=1, dtype=np.float64) + (lsex - lser)
                    out["kl"][x] += np.maximum(kl, 0.0).tolist()
                    out["flip"][x] += (zx.argmax(axis=1) != ar).tolist()
            for p in ps:
                out["keys"].append((r["name"], p))
                out["block"].append((r["name"], p // prm["block_tokens"]) if prm["block_tokens"] > 0 else (r["name"],))
        print(f"  {r['name']}: {len(want)} positions ({', '.join(arms)})", flush=True)
    return out


def plan_passes(keys: dict, ref):
    """group the arms by head; each pass holds at most two heads (the reference's and one group's)"""
    groups = {}
    for x, k in keys.items():
        groups.setdefault(k, []).append(x)
    rk = keys.get(ref) if ref else None
    passes = []
    for k, xs in groups.items():
        if k == rk:
            continue
        passes.append(([ref] if ref else []) + sorted(xs))
    if ref and not passes:
        passes.append([ref])
    if ref and len(groups.get(rk, [])) > 1:      # other arms that share the reference's head ride on the first pass
        passes[0] = [ref] + sorted(x for x in groups[rk] if x != ref) + [x for x in passes[0] if x != ref]
    return passes


def stats_of(meas, arms, ref, base, prm):
    """the paired statistics (block bootstrap as score.py analyse: blocks inside a text, the same resampling for every
    difference) and the KL metrics"""
    S = score()
    blk = meas["block"]
    ids = {}
    inv = np.array([ids.setdefault(b, len(ids)) for b in blk])
    nb = len(ids)
    nblk = np.bincount(inv, minlength=nb).astype(np.float64)
    C = S.boot_counts(nb, prm["boot"], prm["seed"])
    den = C @ nblk
    nll = {x: np.array(meas["nll"][x]) for x in arms}

    def paired(df):
        db = (C @ np.bincount(inv, weights=df, minlength=nb)) / den
        return {"d": float(df.mean()), "se": float(db.std(ddof=1)), "lo": float(np.percentile(db, 2.5)),
                "hi": float(np.percentile(db, 97.5)), "sd_pos": float(df.std(ddof=1)) if df.size > 1 else float("nan"),
                "frac_exact0": float((df == 0).mean())}
    res = {"n": int(len(blk)), "blocks": int(nb), "nll_mean": {x: float(nll[x].mean()) for x in arms}, "d": {}, "kl": {},
           "dkl": {}, "pairs": {}}
    for x in arms:
        if x != base:
            res["d"][x] = paired(nll[x] - nll[base])
    if ref is not None:
        kl = {x: np.array(meas["kl"][x]) for x in arms if x != ref}
        fl = {x: np.array(meas["flip"][x], bool) for x in arms if x != ref}
        for x in kl:
            k = kl[x]
            res["kl"][x] = {"n": int(k.size), "mean": float(k.mean()), "p90": float(np.percentile(k, 90)),
                            "high": int((k > KL_HIGH).sum()), "max": float(k.max()), "flips": int(fl[x].sum())}
            if x != base and base in kl:
                res["dkl"][x] = paired(kl[x] - kl[base])
        if "S" in kl and "U" in kl:
            res["pairs"]["S-U dkl"] = paired(kl["S"] - kl["U"])
    if "S" in nll and "U" in nll:
        res["pairs"]["S-U d"] = paired(nll["S"] - nll["U"])
    return res


def cmd_compare(a):
    S = score()
    root = Path(a.root)
    prm = bound_params(a.bound)
    cfgs = dict(x.split("=", 1) for x in a.cfg)
    arms = [x for x in cfgs if (root / x / "index.json").exists()]
    if a.base not in arms:
        raise SystemExit(f"the base arm {a.base} has no dump in {root}")
    ref = a.ref if a.ref in arms else None
    pos_arm = ref or a.base
    t0 = time.time()
    srcs = {x: head_sources(cfgs[x]) for x in arms}
    keys = {x: head_key(srcs[x]) for x in arms}
    passes = plan_passes(keys, ref)
    print(f"arms {', '.join(arms)}; reference {ref or 'none (no KL)'}; heads " + ", ".join(f"{x} {keys[x]}" for x in arms)
          + f"; passes {passes}; stats {prm}", flush=True)
    merged = None
    for ps in passes:
        built = {}
        heads = {}
        for x in ps:
            k = keys[x]
            if k not in built:
                built[k] = build_head(srcs[x])
            heads[x] = built[k]
        m = measure(root, ps, heads, pos_arm, ref if ref in ps else None, prm, S.load_ids, a.chunk)
        del built, heads
        if merged is None:
            merged = m
        else:
            if m["keys"] != merged["keys"]:
                raise SystemExit("the passes scored different positions")
            for kind in ("nll", "kl", "flip"):
                for x, v in m[kind].items():
                    if x in merged[kind]:
                        if kind == "nll" and v != merged[kind][x]:
                            raise SystemExit(f"{x}: the NLL differs between passes (non-deterministic head?)")
                        continue
                    merged[kind][x] = v
    res = stats_of(merged, arms, ref, a.base, prm)
    res.update({"arms": arms, "ref": ref, "base": a.base, "heads": keys, "head_sources": {
        x: {"pack": str(s["pack"]), "output": [str(s["out"][0]), s["out"][1], s["out"][2]]} for x, s in srcs.items()},
        "params": prm, "seconds": round(time.time() - t0), "root": str(root)})
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1))
    if a.rows_out:
        with open(a.rows_out, "w") as f:
            f.write("\t".join(["text", "pos"] + [f"nll_{x}" for x in arms]
                              + ([f"{h}_{x}" for x in arms if x != ref for h in ("kl", "flip")] if ref else [])) + "\n")
            for i, (t, p) in enumerate(merged["keys"]):
                f.write("\t".join([t, str(p)] + [f"{merged['nll'][x][i]:.6f}" for x in arms]
                                  + ([f"{v:.6g}" for x in arms if x != ref for v in (merged["kl"][x][i], float(merged["flip"][x][i]))]
                                     if ref else [])) + "\n")
    print(f"{res['n']} positions in {res['blocks']} blocks; text NLL " + ", ".join(f"{x} {v:.4f}" for x, v in res["nll_mean"].items())
          + "; d vs " + a.base + ": " + ", ".join(f"{x} {v['d']:+.4f} (se {v['se']:.4f})" for x, v in res["d"].items())
          + ("; KL vs R: " + ", ".join(f"{x} {v['mean']:.5f}" for x, v in res["kl"].items()) if ref else "")
          + f" ({res['seconds']} s)")
    gate(a, "PASS", f"result.json: {res['n']} positions, arms {','.join(arms)}, ref {ref}")
    return 0


# ------------------------------------------------------------------------------------------------ page cache
def meminfo():
    m = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        m[k] = int(v.split()[0]) // 1024     # MiB
    return m


def cmd_dirty(a):
    t0 = time.time()
    while True:
        m = meminfo()
        dw = m.get("Dirty", 0) + m.get("Writeback", 0)
        if dw <= a.below_mb or time.time() - t0 > a.max_s:
            break
        time.sleep(2)
    ok = dw <= a.below_mb
    line = (f"Dirty + Writeback {dw} MiB after {time.time() - t0:.0f} s (want <= {a.below_mb}); MemAvailable "
            f"{m['MemAvailable'] // 1024} GiB, swap used {(m['SwapTotal'] - m['SwapFree'])} MiB")
    print(("PAGE CACHE OK: " if ok else "PAGE CACHE NOT CLEAN: ") + line)
    gate(a, "PASS" if ok else "FAIL", line)
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------------ the text level (11-05)
def text_stem(name):
    return str(name).rsplit("-", 1)[0]


def read_rows_tsv(path, drop=DUP_TEXTS):
    """a compare rows.tsv (columns text, pos, nll_X, kl_X, flip_X; extra columns ignored) without the texts in `drop`"""
    with open(path) as fh:
        hd = fh.readline().rstrip("\n").split("\t")
        rows = [ln.rstrip("\n").split("\t") for ln in fh if ln.strip()]
    col = {h: i for i, h in enumerate(hd)}
    st = [text_stem(r[col["text"]]) for r in rows]
    keep = [i for i, s in enumerate(st) if s not in drop]
    D = {"text": np.array([st[i] for i in keep]), "pos": np.array([int(rows[i][col["pos"]]) for i in keep], dtype=np.int64),
         "dropped": sorted(set(st) & set(drop)), "cols": {}}
    for h, j in col.items():
        if h.startswith(("nll_", "kl_", "flip_")):
            D["cols"][h] = np.array([float(rows[i][j]) for i in keep])
    D["texts"] = list(dict.fromkeys(D["text"].tolist()))
    return D


def kl_metrics(k, f):
    return {"n": int(k.size), "mean": float(k.mean()), "p90": float(np.percentile(k, 90)), "high": int((k > KL_HIGH).sum()),
            "flips": int(f.sum())}


def side(x, p, metric):
    """one text, one metric, arm X against the base: worse / better / inside, or floor (both below it: inside)"""
    a = 1 if metric in COUNT_METRICS else 0
    if max(x, p) < FLOOR[metric]:
        return "floor"
    if x > KL_TOL * p + a:
        return "worse"
    if p > KL_TOL * x + a:
        return "better"
    return "inside"


def metric_verdict(sides):
    nw, nb = sides.count("worse"), sides.count("better")
    if nw >= WIN_N and nb <= OTHER_MAX:
        return "WORSE"
    if nb >= WIN_N and nw <= OTHER_MAX:
        return "BETTER"
    return "INSIDE THE MARGIN"


def boot_reps(vals, blocks, prm):
    """replicates of the position-weighted mean of each value, the blocks (texts, or (text, 2,048-token block)) resampled
    with replacement - the same draws for every value"""
    S = score()
    ids = {}
    inv = np.array([ids.setdefault(b, len(ids)) for b in blocks])
    nb = len(ids)
    C = S.boot_counts(nb, prm["boot"], prm["seed"])
    den = C @ np.bincount(inv, minlength=nb).astype(np.float64)
    return {k: (C @ np.bincount(inv, weights=np.asarray(v, np.float64), minlength=nb)) / den for k, v in vals.items()}, nb


def uncertainty(text, pos, vals, fn, prm):
    """fn of the pooled means: its point value, and se / 95 % CI under the WHOLE-TEXT bootstrap and, beside it, the
    2,048-token-block bootstrap (labelled; it understates)"""
    out = {"point": float(fn({k: float(np.mean(v)) for k, v in vals.items()}))}
    t = [str(x) for x in text]
    for unit, blocks in (("text", t), ("b2048", list(zip(t, (np.asarray(pos) // prm["block_tokens"]).tolist())))):
        reps, nb = boot_reps(vals, blocks, prm)
        r = np.asarray(fn(reps), np.float64)
        out[unit] = {"se": float(r.std(ddof=1)) if nb > 1 else float("nan"), "lo": float(np.percentile(r, 2.5)),
                     "hi": float(np.percentile(r, 97.5)), "blocks": nb}
    return out


def fmt_unc(u, nd=4, what="", sign=True):
    t, b, sg = u["text"], u["b2048"], "+" if sign else ""
    return (f"{what}{u['point']:{sg}.{nd}f}: whole-text bootstrap se {t['se']:.{nd}f} CI [{t['lo']:{sg}.{nd}f}, "
            f"{t['hi']:{sg}.{nd}f}] ({t['blocks']} texts); [2,048-token blocks - not used for the verdict; understates: se {b['se']:.{nd}f} CI "
            f"[{b['lo']:{sg}.{nd}f}, {b['hi']:{sg}.{nd}f}], {b['blocks']} blocks]")


def text_level_kl(D, x, base, prm):
    """the KL rules against R at the text level, arm x against `base` (columns kl_x / flip_x = KL(R || x), changed top-1)"""
    kx, fx, kb, fb = (D["cols"][f"{c}_{a}"] for a in (x, base) for c in ("kl", "flip"))
    tx = {t: kl_metrics(kx[D["text"] == t], fx[D["text"] == t]) for t in D["texts"]}
    tb = {t: kl_metrics(kb[D["text"] == t], fb[D["text"] == t]) for t in D["texts"]}
    px, pb = kl_metrics(kx, fx), kl_metrics(kb, fb)
    mets = {}
    for mt in METRICS:
        sides = {t: side(tx[t][mt], tb[t][mt], mt) for t in D["texts"]}
        sl = list(sides.values())
        mets[mt] = {"verdict": metric_verdict(sl), "sides": sides, "worse": sl.count("worse"), "better": sl.count("better"),
                    "inside": sl.count("inside"), "floor": sl.count("floor"), "pooled": [px[mt], pb[mt]]}
    worse = [mt for mt in METRICS if mets[mt]["verdict"] == "WORSE"]
    if worse:
        v = f"WORSE THAN {base}"
    elif mets["mean"]["verdict"] == "BETTER":
        v = f"BETTER THAN {base}"
    else:
        v = f"INSIDE THE MARGIN, {'ABOVE' if px['mean'] > pb['mean'] else 'AT OR BELOW'} {base}"
    return {"verdict": v, "worse_metrics": worse, "metrics": mets, "per_text": {"x": tx, "base": tb},
            "ratio": uncertainty(D["text"], D["pos"], {"x": kx, "b": kb}, lambda m: m["x"] / m["b"], prm),
            "diff": uncertainty(D["text"], D["pos"], {"x": kx, "b": kb}, lambda m: m["x"] - m["b"], prm),
            "texts": list(D["texts"]), "n": int(kx.size)}


def nll_info(D, x, base, prm):
    """text NLL, INFO only: the pooled d with its whole-text and 2,048-block uncertainty, per-text d"""
    d = D["cols"][f"nll_{x}"] - D["cols"][f"nll_{base}"]
    pt = {t: float(d[D["text"] == t].mean()) for t in D["texts"]}
    return {"d": uncertainty(D["text"], D["pos"], {"d": d}, lambda m: m["d"], prm), "per_text": pt,
            "lower": sum(v < 0 for v in pt.values()), "higher": sum(v > 0 for v in pt.values()),
            "nll_x": float(D["cols"][f"nll_{x}"].mean()), "nll_base": float(D["cols"][f"nll_{base}"].mean())}


def kl_lines(tl, x, base):
    L = []
    for mt in METRICS:
        m = tl["metrics"][mt]
        nd = 0 if mt in COUNT_METRICS else 4
        fl = f" (+ {m['floor']} below the floor, inside)" if m["floor"] else ""
        L.append(f"    {mt:5s} {m['verdict']:17s} texts worse {m['worse']}, better {m['better']}, inside {m['inside']}{fl}; "
                 f"pooled {x} {m['pooled'][0]:.{nd}f} vs {base} {m['pooled'][1]:.{nd}f}; per text "
                 + " ".join(f"{t}:{s[0]}" for t, s in m["sides"].items()))
    L.append("    " + fmt_unc(tl["ratio"], 3, f"pooled ratio mean KL(R || {x}) / KL(R || {base}) ", sign=False))
    return L


# ------------------------------------------------------------------------------------------------ the decision
def decide(root, nll_root=NLL_ROOT, out=None):
    root = Path(root)
    g = read_gates(root / "gates.txt")
    st = lambda k: g.get(k, ("MISSING", ""))[0]
    det = lambda k: g.get(k, ("", ""))[1]
    L, flags = [], []
    dec = {"written": time.strftime("%F %T"),
           "rules": "work/r23/ud31_rules.py (written 11-04, revised 11-05 before the gap)",
           "exactness": {}, "quality": {}, "speed": {}, "flags": flags}
    L.append(f"Unsloth Dynamic v3.1 gap - decision ({dec['written']}; rules {dec['rules']})")
    L.append("ARMS: P = P028x (configs/x28h.json, STRATA_HC_Q8 off as served); U = UD-IQ3_XXS v3.1 as shipped, "
             "STRATA_HC_Q8=1; S = v3.1's routed experts spliced into our ISTA file (off); R = UD-Q4_K_XL (HF cache), "
             "the KL reference, STRATA_HC_Q8=1")
    rt = root / "rules.txt"
    if not rt.exists():
        flags.append("no rule snapshot (gap/rules.txt): the rule text at the gap's start is not on file")
    elif rt.read_text() != rules_text():
        flags.append("the rule text CHANGED after the gap started (gap/rules.txt vs work/r23/ud31_rules.py): "
                     "this decision uses today's rules")
    dec["rules_sha"] = hashlib.sha256(rules_text().encode()).hexdigest()[:12]
    for k in ("rules", "dl_sha", "pack_U", "hcforms_U", "splice", "splice_verify", "dirty", "pack_S", "pack_S_dense",
              "pack_S_tool", "pack_R", "hcforms_R", "tok_U", "tok_S", "tok_R"):
        if k in g:
            L.append(f"  {k} {st(k)} {det(k)[:150]}")
    if "kfail" in g:
        flags.append("a kernel check failed during the gap")
    # ---- exactness
    L.append("EXACTNESS (repeatability: new weights cannot be bit-identical to P028x)")
    for x in ("U", "S"):
        e1, e2 = f"e7_{x}1", f"e7_{x}2"
        envs = [k for k in (f"env_e7{x}1", f"env_e7{x}2") if st(k) == "FAIL"]
        checks = [f"lossless_{x}_cfg", f"lossless_{x}_log", f"start_{x}", f"hcq8_scr_{x}"] + \
            (["splice_verify", "pack_S_dense"] if x == "S" else [])
        failed = [k for k in checks if st(k) == "FAIL"]
        missing = [k for k in checks if st(k) == "MISSING"]
        if st(e2) == "MISSING":
            v = "NOT RUN"
        elif envs:
            v = "VOID (" + ", ".join(envs) + ")"
        elif st(e2) != "PASS":
            v = "NOT REPEATABLE"
        elif failed:
            v = "CHECK FAILED (" + ", ".join(failed) + ")"
        else:
            v = "REPEATABLE" + (f" (not run: {', '.join(missing)})" if missing else "")
        dec["exactness"][x] = v
        L.append(f"  {x}: {v}. {e1} (vs P028x's x28h-e7a, INFO): {det(e1)[:90] or 'missing'}; {e2}: {st(e2)} "
                 f"{det(e2)[:90]}; " + ", ".join(f"{k} {st(k)}" for k in checks))
    # ---- quality (11-05: the KL rules against R at the text level; text NLL INFO - the NLL bound is revoked)
    L.append("QUALITY - " + NOTE_QUANT)
    resp, rowsp = root / "result.json", root / "rows.tsv"
    prm = bound_params()
    ok_arm = {x: st(f"run_{x}") == "PASS" and st(f"env_{x}") == "PASS" and st(f"validate_{x}") == "PASS"
              and st(f"hcq8_nll_{x}") == "PASS" for x in ("P", "U", "S", "R")}
    pr = dec["quality"]["pack_rounding"] = {"tag": PACK_TAG, "dec_followup": "NOT DECIDED"}
    why = None
    if not (ok_arm["P"] and st("head_P") == "PASS"):
        why = (f"P's data or head check not PASS (run_P {st('run_P')}, env_P {st('env_P')}, validate_P {st('validate_P')}, "
               f"head_P {st('head_P')}, hcq8 {st('hcq8_nll_P')})")
    elif not ok_arm["R"]:
        why = (f"R (the KL reference) not valid: run {st('run_R')}, env {st('env_R')}, validate {st('validate_R')}, "
               f"hcq8 {st('hcq8_nll_R')}")
    elif not resp.exists() or not rowsp.exists():
        why = f"no result.json / rows.tsv (compare {st('compare')} {det('compare')[:100]})"
    D = None
    if why is None:
        D = read_rows_tsv(rowsp)
        if "kl_P" not in D["cols"] or len(D["texts"]) < WIN_N:
            why = f"rows.tsv has no KL against R for P, or only {len(D['texts'])} distinct texts (< {WIN_N})"
    if why:
        dec["quality"]["status"] = "NOT JUDGED"
        L.append(f"  NOT JUDGED: {why}")
    else:
        dec["quality"].update({"status": "JUDGED", "texts": D["texts"], "dropped": D["dropped"], "n": int(D["pos"].size),
                               "params": {k: prm[k] for k in ("block_tokens", "boot", "seed")}, "rule": {
                                   "tol": KL_TOL, "win": WIN_N, "other_max": OTHER_MAX, "floor": FLOOR}})
        L.append(f"  texts: {len(D['texts'])} distinct ({', '.join(D['texts'])}; dropped as duplicates: "
                 f"{', '.join(D['dropped']) or 'none'}), {D['pos'].size} positions (every 8th row from 1,024)")
        L.append(f"  rule (written before the gap): per text X vs P worse if X > {KL_TOL:.2f} x P (+ 1 for the counts), better "
                 f"if P > {KL_TOL:.2f} x X (+ 1); per metric WORSE / BETTER = >= {WIN_N} of the texts on that side and <= "
                 f"{OTHER_MAX} on the other; X WORSE THAN P if any metric WORSE; BETTER if the mean BETTER and none WORSE; "
                 "else INSIDE THE MARGIN (ABOVE / AT OR BELOW P by the pooled mean)")
        L.append("  PACK ROUNDING (frozen rule, Karl 11-05): U's and R's prompt rows read their files' Q8_0 hyper-"
                 "connections rounded to BF16 (pack time); P's and S's are BF16 in the file (unrounded)")
        L.append("  KL vs R per arm, pooled (lower is better): " + "; ".join(
            f"{x} mean {m['mean']:.5f} p90 {m['p90']:.5f} >1 {m['high']} top-1 changed {m['flips']} of {m['n']}"
            for x in ("P", "U", "S") if f"kl_{x}" in D["cols"]
            for m in [kl_metrics(D["cols"][f"kl_{x}"], D["cols"][f"flip_{x}"])]))
        tls = {}
        for x in ("U", "S"):
            if f"kl_{x}" not in D["cols"] or not ok_arm[x]:
                dec["quality"][f"kl_{x}"] = "NOT DECIDED"
                L.append(f"  KL rules, {x} vs P: NOT DECIDED (run {st('run_' + x)}, env {st('env_' + x)}, validate "
                         f"{st('validate_' + x)}, hcq8 {st('hcq8_nll_' + x)})")
                continue
            tl = tls[x] = text_level_kl(D, x, "P", prm)
            v = tl["verdict"]
            dec["quality"][f"kl_{x}"] = v
            dec["quality"][f"kl_{x}_detail"] = {mt: {k: tl["metrics"][mt][k] for k in ("verdict", "worse", "better",
                                                                                        "inside", "floor", "pooled")}
                                                for mt in METRICS}
            dec["quality"][f"kl_{x}_ratio"] = tl["ratio"]
            tail = ""
            if x == "U":
                trig = not v.startswith("BETTER")       # worse, or inside the margin on either side (Karl 11-05)
                pr["kl_U"] = {"class": v, "trigger": bool(trig), "worse_metrics": tl["worse_metrics"],
                              "pooled_mean": tl["metrics"]["mean"]["pooled"], "ratio": tl["ratio"],
                              "why": (("WORSE THAN P on " + ", ".join(tl["worse_metrics"])) if v.startswith("WORSE") else
                                      "inside the margin (" + v.split(", ", 1)[1] + " by the pooled mean KL)") if trig else None}
                dec["quality"]["kl_U_class"] = v
                dec["quality"]["kl_U_tag"] = PACK_TAG
                if trig:
                    dec["quality"]["kl_U"] = "INCLUDES PACK ROUNDING"
                    tail = (f"; RECORDED AS INCLUDES PACK ROUNDING ({pr['kl_U']['why']}) - {PACK_TAG}; not a verdict "
                            "on the file")
                else:
                    tail = f" [{PACK_TAG}]"
            L.append(f"  KL rules, {x} vs P, text level -> {v}{tail}")
            L += kl_lines(tl, x, "P")
        if "U" in tls and "S" in tls:
            tus = text_level_kl(D, "U", "S", prm)
            dec["quality"]["info_U_vs_S"] = tus["verdict"]
            L.append(f"  INFO U vs S (the whole file vs its experts in our file), the same rule: {tus['verdict']}; mean: "
                     f"texts worse {tus['metrics']['mean']['worse']}, better {tus['metrics']['mean']['better']}; "
                     + fmt_unc(tus["ratio"], 3, "pooled ratio ", sign=False))
        # text NLL: INFO only
        L.append("  TEXT NLL - INFO ONLY (the many-positions NLL bound is revoked 11-05; whole-text uncertainty first, the "
                 "2,048-token-block figure beside it, labelled):")
        L.append("    per arm, pooled NLL (nats/token): " + ", ".join(
            f"{x} {D['cols'][f'nll_{x}'].mean():.4f}" for x in ("P", "U", "S", "R") if f"nll_{x}" in D["cols"]))
        dec["quality"]["nll_info"] = {}
        for x in ("U", "S", "R"):
            if f"nll_{x}" not in D["cols"] or not ok_arm[x]:
                continue
            ni = nll_info(D, x, "P", prm)
            dec["quality"]["nll_info"][x] = ni
            tag = f" [{PACK_TAG}]" if x == "U" else (" [R: the reference quant; its hc rounded at pack time too]" if x == "R" else "")
            L.append(f"    {x} vs P: " + fmt_unc(ni["d"], 4, "d ") + f"; texts lower {ni['lower']}, higher {ni['higher']}; "
                     + " ".join(f"{t}:{v:+.3f}" for t, v in ni["per_text"].items()) + tag)
    for x in ("P", "U", "S", "R"):
        if st(f"validate_{x}") not in ("PASS", "MISSING"):
            flags.append(f"validate_{x} {st('validate_' + x)}: its offline head and window rows disagree")
        if st(f"hcq8_nll_{x}") == "FAIL":
            flags.append(f"hcq8_nll_{x} FAIL: the switch did not act as configured on {x}'s NLL engine ({det('hcq8_nll_' + x)[:120]})")
    ku = pr.get("kl_U")
    if ku is None:
        pr["dec_followup"] = "NOT DECIDED"
        L.append(FOLLOW_MARK + "NOT DECIDED (no KL verdict for U)")
    elif ku["trigger"]:
        pr["dec_followup"] = "WANTED"
        L.append(FOLLOW_MARK + f"WANTED (U's KL verdict {ku['class']}: {ku['why']}; work/r23/gap-ud31-dec.sh scores U's "
                 "decode path with STRATA_HC_Q8=1 against the decode-path gap's P rows -> results/r23/ud31/dec/decision.txt "
                 "decides)")
    else:
        pr["dec_followup"] = "NOT NEEDED"
        L.append(FOLLOW_MARK + f"NOT NEEDED (U's KL verdict {ku['class']}: clearly better than P, which the pack rounding "
                 "can only have hidden, not caused)")
    # ---- speed
    L.append("SPEED (Karl's no-loss rule: no workload slower beyond its noise; U and S vs P, the 9-workload screen x3)")
    g17 = load("g17_rules_ud31", G17)
    bad_p = [k for k, (s_, _) in g.items() if re.match(r"((env|fatal)_scrP\d|hcq8_scr_P)$", k) and s_ == "FAIL"]
    for x in ("U", "S"):
        bad = [k for k, (s_, _) in g.items() if re.match(rf"((env|fatal)_scr{x}\d|hcq8_scr_{x})$", k) and s_ == "FAIL"] + bad_p
        ok, line = g17.wl_noloss(root, x, ref="P")
        px, pp = g17.screen_passes(root, x), g17.screen_passes(root, "P")
        geo = ""
        if px and pp:
            for i, nm in ((0, "decode"), (1, "prompt")):
                mx, mp = g17.gm([v[i] for v in px.values()]), g17.gm([v[i] for v in pp.values()])
                geo += f"{nm} {100 * (mx / mp - 1):+.2f} % "
            geo = f"; screen geomeans vs P: {geo.strip()} ({len(px)} / {len(pp)} complete passes)"
        v = ("VOID (" + ", ".join(bad) + ")") if bad else ("NOT DECIDED" if ok is None else ("NO LOSS" if ok else "LOSS"))
        sv, sl = g17.save_rule(root, x, "P")   # 11-07 amendment: (None, []) for a gate before it
        if sv is not None:
            line += "; " + sl[0]
            if not bad and v == "NO LOSS" and sv in ("FAIL", "NOT DECIDED"):
                v = "LOSS" if sv == "FAIL" else "NOT DECIDED"
        dec["speed"][x] = v
        L.append(f"  {x}: {v}: {line}{geo}")
    if "slots" in g:
        L.append(f"  INFO slots: {det('slots')[:200]}")
    # ---- summary
    L.append("SUMMARY")
    for x in ("U", "S"):
        q = dec["quality"]
        tag = ""
        if x == "U":
            cls = [f"class {q['kl_U_class']}"] if q.get("kl_U") == "INCLUDES PACK ROUNDING" else []
            tag = f" [{'; '.join(cls) + '; ' if cls else ''}{PACK_TAG}]" if "kl_U_class" in q else ""
        ni = q.get("nll_info", {}).get(x)
        nl = f"d {ni['d']['point']:+.4f} (whole-text se {ni['d']['text']['se']:.4f})" if ni else "-"
        L.append(f"  {x}: exactness {dec['exactness'][x]}; KL rules vs P (text level) {q.get('kl_' + x, 'NOT JUDGED')}; "
                 f"text NLL vs P (INFO) {nl}; speed {dec['speed'][x]}{tag}")
    L.append("  " + FOLLOW_MARK.lstrip("=> ") + pr["dec_followup"])
    if flags:
        L.append("FLAGS: " + " | ".join(flags))
    L.append(NOTE_SWITCH)
    out = Path(out) if out else root
    (out / "decision.txt").write_text("\n".join(L) + "\n")
    (out / "decision.json").write_text(json.dumps(dec, indent=1, default=str))
    print("\n".join(L))
    return dec


def cmd_decide(a):
    decide(a.root, a.nll_root, a.out)
    return 0


# ------------------------------------------------------------------------------------------------ the decode-path follow-up
_DP = None


def dp_mod():
    """work/r23/decpath_rules.py, loaded (never edited): its runner, env check and KL floor rule"""
    global _DP
    if _DP is None:
        _DP = load("decpath_rules_ud31", DECPATH)
    return _DP


def pdec_plan(pdec):
    """the decode-path gap's dec arm as a plan: [(file, cut, min_cut)] in its order (its finished reads), its L (the
    --short-read it ran with - 64) and its index"""
    idx = json.loads((Path(pdec) / "index.json").read_text())
    args = idx.get("args") or []
    try:
        L = int(argval(args, "--short-read")) - 64
        mc = int(argval(args, "--max-context"))
    except (TypeError, ValueError):
        raise SystemExit(f"{pdec}/index.json: no --short-read / --max-context in its args")
    if mc != L + 512:
        raise SystemExit(f"{pdec}/index.json: --max-context {mc} is not --short-read - 64 + 512 ({L + 512})")
    mains = {f: mn for f, _, mn in dp_mod().PLANS["main"]}
    plan = [(r["file"], int(r["cut"]), min(mains.get(r["file"], 0), int(r["cut"])) if mains.get(r["file"]) else 0)
            for r in idx.get("requests", []) if r.get("end_line") is not None]
    return plan, L, idx


def dp_with_plan(pdec):
    """decpath_rules with one more plan (DEC_PLAN = dec's own reads) and its max_len giving dec's L for that plan"""
    DP = dp_mod()
    plan, L, idx = pdec_plan(pdec)
    DP.PLANS[DEC_PLAN] = plan
    if not getattr(DP, "_ud31_orig_max_len", None):
        DP._ud31_orig_max_len = DP.max_len
    orig = DP._ud31_orig_max_len
    DP.max_len = lambda name, ids_of=None: L if name == DEC_PLAN else orig(name, ids_of)
    return DP, plan, L, idx


def cmd_dec_run(a):
    DP, plan, L, _ = dp_with_plan(a.pdec)
    print(f"plan {DEC_PLAN} (the decode-path gap's dec reads, {a.pdec}): " + ", ".join(f"{f} {c}" for f, c, _ in plan)
          + f"; L {L}", flush=True)
    return DP.cmd_run(argparse.Namespace(config=a.config, outdir=a.outdir, kind="logpos", plan=DEC_PLAN,
                                         budget_min=a.budget_min, env=None, min_free_gb=a.min_free_gb))


def cmd_dec_envwatch(a):
    DP, _, _, _ = dp_with_plan(a.pdec)
    return DP.cmd_envwatch(argparse.Namespace(job=a.job, config=a.config, kind="logpos", plan=DEC_PLAN, env=None,
                                              kill=a.kill, max_s=a.max_s, gate=a.gate, gates=a.gates))


def dec_args_diff(u_args, p_args, cfg):
    """U's engine args against dec's: the same list except the values of --pack / --native / --ple-gguf (U's)"""
    bad = []
    if len(u_args) != len(p_args):
        return [f"{len(u_args)} args vs dec's {len(p_args)}"]
    paths = {"--pack", "--native", "--ple-gguf"}
    for i, (x, y) in enumerate(zip(u_args, p_args)):
        if i > 0 and u_args[i - 1] in paths and p_args[i - 1] == u_args[i - 1]:
            if x != argval(cfg["args"], u_args[i - 1]):
                bad.append(f"{u_args[i - 1]} {x} (U's config has {argval(cfg['args'], u_args[i - 1])})")
            continue
        if i == 0:
            continue                                   # the exe: both engine-r22p028x (envwatch checks /proc/PID/exe)
        if x != y:
            bad.append(f"arg {i}: {x} (dec: {y})")
    return bad


def cmd_dec_args(a):
    cfg = json.loads(Path(a.cfg).read_text())
    try:
        u = json.loads((Path(a.udir) / "index.json").read_text())
        p = json.loads((Path(a.pdec) / "index.json").read_text())
        bad = dec_args_diff(u.get("args", []), p.get("args", []), cfg)
        if os.path.realpath(u["args"][0]) != os.path.realpath(p["args"][0]):
            bad.append(f"exe {u['args'][0]} (dec: {p['args'][0]})")
    except (OSError, ValueError, KeyError, IndexError) as e:
        bad = [f"no index ({e})"]
    line = ("U's engine args = the decode-path gap's dec arm's, except U's three paths" if not bad
            else "; ".join(bad)[:300])
    print(("DEC ARGS OK: " if not bad else "DEC ARGS DIFFER: ") + line)
    gate(a, "PASS" if not bad else "FAIL", line)
    return 0 if not bad else 1


def dec_pre_problems(ud31, pdec, cfgp, files=True):
    """why the follow-up must not run (empty = it may): the v3.1 decision asks for it, the dec arm exists, U as used"""
    bad = []
    ud31, pdec = Path(ud31), Path(pdec)
    try:
        d = json.loads((ud31 / "decision.json").read_text())
    except (OSError, ValueError):
        d = None
        bad.append(f"no v3.1 decision ({ud31 / 'decision.json'})")
    if d is not None:
        q = d.get("quality", {})
        fu = q.get("pack_rounding", {}).get("dec_followup")
        if q.get("status") != "JUDGED":
            bad.append(f"the v3.1 decision's quality is {q.get('status', 'missing')}, not JUDGED")
        if fu != "WANTED":
            bad.append(f"the v3.1 decision does not ask for it (U's KL verdict {q.get('kl_U_class', q.get('kl_U', 'NOT DECIDED'))}, "
                       f"follow-up {fu or 'not recorded'}): U is clearly BETTER THAN P, which needs no follow-up")
        dt = ud31 / "decision.txt"
        if fu == "WANTED" and (not dt.exists() or (FOLLOW_MARK + "WANTED") not in dt.read_text(errors="replace")):
            bad.append("decision.txt does not say WANTED: it and decision.json disagree")
    g = read_gates(pdec.parent / "gates.txt")
    for k in ("run_dec", "env_dec"):
        if g.get(k, ("MISSING",))[0] != "PASS":
            bad.append(f"the decode-path gap's {k} is {g.get(k, ('MISSING',))[0]}")
    if not (pdec / "index.json").exists() or not (pdec / "score.tsv").exists():
        bad.append(f"no dec rows ({pdec}/index.json + score.tsv)")
    else:
        try:
            plan, L, idx = pdec_plan(pdec)
            if len(plan) < DEC_MIN_TEXTS:
                bad.append(f"the dec arm read {len(plan)} text(s) (< {DEC_MIN_TEXTS})")
            if os.path.realpath(idx.get("config", "")) != os.path.realpath(X28H):
                bad.append(f"the dec arm's config is {idx.get('config')}, not configs/x28h.json")
            if idx.get("kind") != "logpos" or idx.get("env"):
                bad.append(f"the dec arm ran kind {idx.get('kind')} with --env {idx.get('env')} (want logpos, none)")
        except (SystemExit, KeyError, ValueError) as e:
            bad.append(str(e))
    try:
        c = json.loads(Path(cfgp).read_text())
        w = arm_configs()["U"]
        c2, w2 = dict(c), dict(w)
        for k in ("_comment",):
            c2.pop(k, None), w2.pop(k, None)
        if c2 != w2:
            bad.append(f"{Path(cfgp).name} is not what `configs` writes for U ({', '.join(sorted(cfg_diffs(c, w)))[:150]})")
        if c.get("env", {}).get("STRATA_HC_Q8") != "1":
            bad.append(f"{Path(cfgp).name}: STRATA_HC_Q8 not 1")
    except (OSError, ValueError) as e:
        bad.append(f"U's config: {e}")
    if files:
        g31 = read_gates(ud31 / "gap" / "gates.txt")
        for k in ("dl_sha", "pack_U"):
            if g31.get(k, ("MISSING",))[0] != "PASS":
                bad.append(f"the v3.1 gap's {k} is {g31.get(k, ('MISSING',))[0]}")
        for f in ("index.txt", "native_experts.txt", "dense.bin"):
            if not (PACKS["U"] / f).exists():
                bad.append(f"U's pack has no {f}")
        for n, (size, _) in sorted(pinned(TREE).items()):
            if not (U_DIR / n).exists() or (U_DIR / n).stat().st_size != size:
                bad.append(f"U's shard {n} missing or not {size:,} B")
    return bad


def cmd_dec_pre(a):
    bad = dec_pre_problems(a.ud31, a.pdec, a.cfg)
    if bad:
        print("REFUSED " + "; ".join(bad))
        return 1
    plan, L, _ = pdec_plan(a.pdec)
    print(f"PASS the v3.1 decision asks for it (WANTED); the decode-path gap's dec arm: {len(plan)} texts "
          f"({', '.join(f'{f.split(chr(46))[0]} {c}' for f, c, _ in plan)}), L {L}; U's config, pack and shards as the v3.1 gap used them")
    return 0


def read_dec_rows(d, ids_of):
    """a decpath logpos dir at the compare positions: {file: {"name", "cut", "pos": {p: (target, lp, argmax, ids, lps)}}}
    (every DEC_EVERY-th from DEC_MIN_POS, p + 1 < cut; only those lines are parsed); target mismatches counted"""
    idx = json.loads((Path(d) / "index.json").read_text())
    reqs = sorted((r for r in idx.get("requests", []) if r.get("end_line") is not None), key=lambda r: r["first_line"])
    out = {r["file"]: {"name": r["name"], "cut": int(r["cut"]), "pos": {}} for r in reqs}
    bounds = [(r["first_line"], r["end_line"], r["file"], int(r["cut"])) for r in reqs]
    bad, bi = 0, 0
    ids_cache = {}
    with open(Path(d) / "score.tsv", errors="replace") as fh:
        for i, line in enumerate(fh):
            while bi < len(bounds) and i >= bounds[bi][1]:
                bi += 1
            if bi >= len(bounds):
                break
            lo, hi, fl, cut = bounds[bi]
            if i < lo:
                continue
            t = line.find("\t")
            try:
                p = int(line[:t])
            except ValueError:
                continue
            if p % DEC_EVERY or p < DEC_MIN_POS or p + 1 >= cut:
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 8 + 64:
                continue
            tk = [z.split(":") for z in f[8:72]]
            ids = ids_cache.setdefault(fl, ids_of(fl))
            if ids[p + 1] != int(f[1]):
                bad += 1
                continue
            out[fl]["pos"][p] = (int(f[1]), float(f[2]), int(f[3]), np.array([int(x) for x, _ in tk]),
                                 np.array([float(y) for _, y in tk]))
    return out, bad


def dec_stratum(p):
    for name, lo, hi in DEC_STRATA:
        if lo <= p < hi:
            return name
    return None


def boot_paired(vals, blocks, prm):
    """per key: mean, block-bootstrap se and 95 % percentile CI (the same resampling for every key)"""
    S = score()
    ids = {}
    inv = np.array([ids.setdefault(b, len(ids)) for b in blocks])
    nb = len(ids)
    C = S.boot_counts(nb, prm["boot"], prm["seed"])
    den = C @ np.bincount(inv, minlength=nb).astype(np.float64)
    out = {}
    for k, v in vals.items():
        v = np.asarray(v, np.float64)
        rep = (C @ np.bincount(inv, weights=v, minlength=nb)) / den
        out[k] = {"mean": float(v.mean()), "se": float(rep.std(ddof=1)) if nb > 1 else float("nan"),
                  "lo": float(np.percentile(rep, 2.5)), "hi": float(np.percentile(rep, 97.5))}
    return out, nb


def read_prompt_rows(path, col, want):
    """{(text stem, pos): value} of one column of a rows.tsv, at the wanted keys only"""
    out = {}
    if not path or not Path(path).exists():
        return out
    with open(path) as fh:
        hd = fh.readline().rstrip("\n").split("\t")
        if not {"text", "pos", col} <= set(hd):
            return out
        it, ip, ic = hd.index("text"), hd.index("pos"), hd.index(col)
        for line in fh:
            x = line.rstrip("\n").split("\t")
            k = (text_stem(x[it]), int(x[ip]))
            if k in want:
                out[k] = float(x[ic])
    return out


def dec_compare(udir, pdec, rows_tsv, prm, ids_of, prows=None):
    """U's decode-path rows against dec's (P) at dec's compare positions, per text and pooled (Karl's rule 11-05), and
    the rounding cost (U decode - U prompt) - (P decode - P prompt) at the positions all four terms have"""
    DP = dp_mod()
    P_, bp = read_dec_rows(pdec, ids_of)
    U_, bu = read_dec_rows(udir, ids_of)
    keys, nll_p, nll_u, agree, kl = [], [], [], [], []
    for f, pu in U_.items():
        pp = P_.get(f)
        if pp is None:
            continue
        stem = f.split(".")[0]
        for p in sorted(set(pu["pos"]) & set(pp["pos"])):
            a_, b_ = pp["pos"][p], pu["pos"][p]
            keys.append((stem, p))
            nll_p.append(-a_[1])
            nll_u.append(-b_[1])
            agree.append(float(a_[2] == b_[2]))
            kl.append(DP.kl_top_floor(a_[3], a_[4], b_[3], b_[4]))
    want = set(keys)
    u_pr = read_prompt_rows(rows_tsv, "nll_U", want)          # U prompt: the v3.1 gap's U many-positions rows
    p_pr = read_prompt_rows(prows, "nll_ref", want)           # P prompt: the NLL gap's ref rows (= x28h, byte-identical)
    p_pr31 = read_prompt_rows(rows_tsv, "nll_P", want)        # the v3.1 gap's own P rows (a cross-check, INFO)
    res = {"n": len(keys), "target_mismatch": {"P": bp, "U": bu}, "texts": list(dict.fromkeys(k[0] for k in keys)),
           "u_texts": sorted(f.split(".")[0] for f in U_), "p_texts": sorted(f.split(".")[0] for f in P_),
           "params": {k: prm[k] for k in ("block_tokens", "boot", "seed")}, "per_text": {}, "strata": {},
           "sources": {"U_decode": str(udir), "P_decode": str(pdec), "U_prompt": f"{rows_tsv} nll_U",
                       "P_prompt": f"{prows} nll_ref"}}
    if not keys:
        return res
    T = np.array([k[0] for k in keys])
    Pos = np.array([k[1] for k in keys], dtype=np.int64)
    NU, NP = np.array(nll_u), np.array(nll_p)
    d = NU - NP
    A, K = np.array(agree), np.array(kl)
    for t in res["texts"]:
        m = T == t
        res["per_text"][t] = {"n": int(m.sum()), "d": float(d[m].mean()), "agree": float(A[m].mean()),
                              "kl": float(K[m].mean()), "nll_U": float(NU[m].mean()), "nll_P": float(NP[m].mean())}
    res["pooled"] = {"d": uncertainty(T, Pos, {"d": d}, lambda q: q["d"], prm), "agree": float(A.mean()),
                     "kl": float(K.mean()), "nll_U": float(NU.mean()), "nll_P": float(NP.mean())}
    four = [i for i, k in enumerate(keys) if k in u_pr and k in p_pr]
    if four:
        rc = np.array([(NU[i] - u_pr[keys[i]]) - (NP[i] - p_pr[keys[i]]) for i in four])
        Tf, Pf = T[four], Pos[four]
        pt = {}
        for t in dict.fromkeys(Tf.tolist()):
            m = Tf == t
            pt[t] = {"n": int(m.sum()), "rc": float(rc[m].mean())}
        cross = [abs(p_pr31[keys[i]] - p_pr[keys[i]]) for i in four if keys[i] in p_pr31]
        res["rounding_cost"] = {"n": len(four), "per_text": pt,
                                "pooled": uncertainty(Tf, Pf, {"rc": rc}, lambda q: q["rc"], prm),
                                "p_prompt_crosscheck_max_abs": max(cross) if cross else None, "crosscheck_n": len(cross)}
    for sname, lo, hi in DEC_STRATA:
        m = (Pos >= lo) & (Pos < hi)
        if not m.any():
            res["strata"][sname] = {"n": 0}
            continue
        u = uncertainty(T[m], Pos[m], {"d": d[m]}, lambda q: q["d"], prm)
        res["strata"][sname] = {"n": int(m.sum()), "texts": sorted(set(T[m].tolist())), "d": u["point"], "b2048": u["b2048"],
                                "agree": float(A[m].mean()), "kl": float(K[m].mean())}
    return res


def cmd_dec_compare(a):
    prm = bound_params()
    res = dec_compare(a.udir, a.pdec, a.rows, prm, score().load_ids, a.prows)
    res.update(udir=str(a.udir), pdec=str(a.pdec), rows=str(a.rows), prows=str(a.prows))
    Path(a.json).write_text(json.dumps(res, indent=1))
    print(f"{res['n']} positions in {len(res['texts'])} texts; target mismatches P {res['target_mismatch']['P']}, U "
          f"{res['target_mismatch']['U']}" + (f"; pooled d_dec {res['pooled']['d']['point']:+.4f} (whole-text se "
                                              f"{res['pooled']['d']['text']['se']:.4f})" if res.get("pooled") else "")
          + (f"; rounding cost at {res['rounding_cost']['n']} positions" if res.get("rounding_cost") else "; no rounding cost"))
    gate(a, "PASS", f"result.json: {res['n']} positions, {len(res['texts'])} texts")
    return 0


def dec_thresholds(N):
    """Karl's 8-text rule (>= 6 one way, <= 1 the other) at N texts, scaled as the decode-path check scales its own
    (decpath_rules.py: the same proportions, rounded the demanding way): at least ceil(6N/8), at most floor(N/8).
    N 8: 6 / 1; N 7: 6 / 0; N 6: 5 / 0; N 5: 4 / 0; N < 5: not judged"""
    return math.ceil(6 * N / 8), math.floor(N / 8)


def dec_text_verdict(per_text):
    """per text: lower / higher = U's decode-path text NLL below / above P's on the same positions; a tie (|d_t| <
    DEC_TIE) counts as neither. -> (verdict, sides, lower, higher, N)"""
    sides = {t: ("tie" if abs(e["d"]) < DEC_TIE else ("lower" if e["d"] < 0 else "higher")) for t, e in per_text.items()}
    N = len(sides)
    lo_, hi_ = list(sides.values()).count("lower"), list(sides.values()).count("higher")
    if N < DEC_MIN_TEXTS:
        return f"NOT JUDGED ({N} texts that both U and P have, fewer than {DEC_MIN_TEXTS})", sides, lo_, hi_, N
    need, other = dec_thresholds(N)
    if lo_ >= need and hi_ <= other:
        return "BETTER THAN P", sides, lo_, hi_, N
    if hi_ >= need and lo_ <= other:
        return "WORSE THAN P", sides, lo_, hi_, N
    return "INCONCLUSIVE", sides, lo_, hi_, N


def dec_decide(dd, ud31=UD31, pack_u=None):
    dd, ud31 = Path(dd), Path(ud31)
    pack_u = Path(pack_u) if pack_u else PACKS["U"]
    g = read_gates(dd / "gap" / "gates.txt")
    st = lambda k: g.get(k, ("MISSING", ""))[0]
    out = {"written": time.strftime("%F %T"), "rules": "work/r23/ud31_rules.py, THE DECODE-PATH FOLLOW-UP (Karl's rule, 11-05)",
           "rules_sha": hashlib.sha256(rules_text().encode()).hexdigest()[:12]}
    L = [f"Unsloth v3.1 U on the decode path (the v3.1 gap's follow-up) - decision ({out['written']}; rules "
         f"{out['rules']}, sha {out['rules_sha']})"]
    why = []
    try:
        d31 = json.loads((ud31 / "decision.json").read_text())
        ku = d31["quality"]["pack_rounding"]["kl_U"]
        L.append(f"WHY: the v3.1 gap ({ud31 / 'decision.txt'}, {d31.get('written')}): U's KL rules vs P (text level, against "
                 f"R, prompt path) {ku['class']} -> RECORDED AS INCLUDES PACK ROUNDING ({ku['why']}). Karl 11-05: before "
                 "deciding, U's decode-path teacher-forced score with STRATA_HC_Q8=1.")
        out.update(prompt_path=ku, v31_written=d31.get("written"))
    except (OSError, ValueError, KeyError, TypeError):
        why.append("no v3.1 KL verdict for U (results/r23/ud31/decision.json without quality.pack_rounding.kl_U)")
    L.append("DECODE PATH: engine-r22p028x, 2-row verify windows, STRATA_LOGPOS top 64 (decpath_rules.py run, with the "
             "decode-path gap's dec texts, cuts and length); U = results/r23/ud31/configs/ud31-U.json (STRATA_HC_Q8=1: "
             "the verify read takes the file's own Q8_0 hyper-connections, the final mixer included); P = the decode-path "
             "gap's dec rows (configs/x28h.json as served, the switch off: its BF16 hyper-connections are the file's own)")
    for k in ("env_decU", "run_decU", "dec_args", "hcq8_dec_U", "compare"):
        L.append(f"  {k} {st(k)} {g.get(k, ('', ''))[1][:170]}")
        if k != "compare" and st(k) != "PASS":
            why.append(f"{k} {st(k)}")
    rp = dd / "gap" / "result.json"
    res = json.loads(rp.read_text()) if rp.exists() else None
    if res is None:
        why.append("no compare result (gap/result.json)")
    else:
        if res["target_mismatch"]["P"] or res["target_mismatch"]["U"]:
            why.append(f"target mismatches P {res['target_mismatch']['P']}, U {res['target_mismatch']['U']}")
        if not res["n"]:
            why.append("no positions in common")
    try:
        c, _ = hc_conversions(pack_u)
        ri = sum(v for k, v in c.items() if k.startswith("inject") and k.endswith("rounded"))
        hcl = ("pack-u's injects: " + (", ".join(f"{v} {k}" for k, v in sorted(c.items()) if k.startswith("inject")) or "none converted")
               + (f" -> {ri} ROUNDED: the caveat is NOT fully removed for them" if ri else " -> unrounded"))
    except (OSError, ValueError):
        ri, hcl = None, "pack-u/conversions.json not read: the injects' exactness is not on file"
    out["inject_rounded"] = ri
    verdict = None
    if not why:
        verdict, sides, nlo, nhi, N = dec_text_verdict(res["per_text"])
        if verdict.startswith("NOT JUDGED"):
            why.append(verdict)
    if why:
        L.append("=> NOT JUDGED: " + "; ".join(why))
        out["verdict"] = "NOT JUDGED"
    else:
        need, other = dec_thresholds(N)
        out.update(verdict=verdict, sides=sides, lower=nlo, higher=nhi, N=N, need=need, other_max=other)
        L.append(f"positions: {res['n']} (every {DEC_EVERY}th from {DEC_MIN_POS:,}; targets checked on both) in the "
                 f"{N} texts both U and P have: {', '.join(res['texts'])}" + (
                     f" (U read {len(res['u_texts'])}, dec {len(res['p_texts'])})" if res["u_texts"] != res["p_texts"] else ""))
        L.append(f"NO PACK-ROUNDING CAVEAT on this verdict: on the decode path U reads its file's Q8_0 hyper-connections "
                 f"and P its file's BF16. {hcl}. Left: the hc read kernel (upstream's Q8_0 read vs our fork's: a "
                 "summation order).")
        L.append(f"rule (Karl 11-05, written before any run): per text, U's decode-path text NLL vs P's on the same "
                 f"positions - lower / higher (a tie, |d_t| < {DEC_TIE:g}, counts as neither); U lower in >= {need} and "
                 f"higher in <= {other} of the {N} texts: BETTER THAN P; the mirror image: WORSE THAN P; anything else: "
                 "INCONCLUSIVE" + ("" if N == 8 else f" [FLAG: {N} of 8 texts - the 6-of-8 / at-most-1 rule scaled as the "
                                                    "decode-path check scales its own; Karl's rule is written for 8 texts]"))
        for t, e in res["per_text"].items():
            L.append(f"  {t:12s} {e['n']:5d} positions: NLL U {e['nll_U']:.4f} P {e['nll_P']:.4f}, d_t {e['d']:+.4f} -> "
                     f"{sides[t]} | top-1 agree {100 * e['agree']:.1f} % | KL(P || U) top-64 {e['kl']:.4f}")
        L.append("  pooled (INFO): " + fmt_unc(res["pooled"]["d"], 4, "d_dec ")
                 + f"; top-1 agree {100 * res['pooled']['agree']:.1f} %; KL(P || U) top-64 {res['pooled']['kl']:.4f}")
        for s in [x for x, _, _ in DEC_STRATA]:
            e = res["strata"].get(s, {"n": 0})
            if not e.get("n"):
                L.append(f"  [{s}] no positions")
                continue
            b = e["b2048"]
            L.append(f"  [{s}] INFO {e['n']} positions, {len(e['texts'])} texts: d_dec {e['d']:+.4f} [2,048-token blocks - "
                     f"not used for the verdict: se {b['se']:.4f} CI [{b['lo']:+.4f}, {b['hi']:+.4f}]] | top-1 agree "
                     f"{100 * e['agree']:.1f} % | KL(P || U) {e['kl']:.4f}")
        if verdict == "INCONCLUSIVE":
            L.append(f"=> U vs P, text NLL on the decode path: INCONCLUSIVE (lower in {nlo}, higher in {nhi} of {N} texts) - "
                     "if the file choice hinges on it, Karl decides on a separate R decode-path gap")
        else:
            L.append(f"=> U vs P, text NLL on the decode path: {verdict} (lower in {nlo}, higher in {nhi} of {N} texts) - the "
                     "verdict on the file that the v3.1 gap deferred (its prompt-path KL record: INCLUDES PACK ROUNDING)"
                     + ("; FLAG: some inject rows were rounded at pack time" if ri else ""))
    rc = (res or {}).get("rounding_cost")
    if rc:
        out["rounding_cost"] = {t: v["rc"] for t, v in rc["per_text"].items()}
        L.append("INFO ONLY - the rounding cost per text, (U decode - U prompt) - (P decode - P prompt) text NLL at the "
                 f"{rc['n']} positions all four have (U decode: this gap's U rows; U prompt: the v3.1 gap's U many-positions "
                 "rows, rows.tsv nll_U; P decode: the decode-path gap's dec rows; P prompt: the NLL gap's ref rows = x28h, "
                 "rows.tsv nll_ref). P's HC weights are native BF16 on both paths, so this isolates what the BF16 rounding "
                 "costs U, plus path noise. Negative = U's prompt path is worse, relative to its decode path, than P's:")
        L.append("  per text: " + " ".join(f"{t}:{v['rc']:+.4f}({'-' if v['rc'] < 0 else '+' if v['rc'] > 0 else '0'})"
                                           for t, v in rc["per_text"].items())
                 + f"; signs - {sum(v['rc'] < 0 for v in rc['per_text'].values())}, + "
                 f"{sum(v['rc'] > 0 for v in rc['per_text'].values())} of {len(rc['per_text'])}")
        L.append("  " + fmt_unc(rc["pooled"], 4, "pooled rounding cost "))
        if rc.get("p_prompt_crosscheck_max_abs") is not None:
            L.append(f"  cross-check: the v3.1 gap's own P rows vs the NLL gap's ref rows at {rc['crosscheck_n']} positions: "
                     f"max |difference| {rc['p_prompt_crosscheck_max_abs']:.6f} (same build and rows: 0 expected)")
    else:
        L.append("INFO ONLY - the rounding cost: not computed (U prompt rows or P prompt rows missing at these positions)")
    L.append(NOTE_SWITCH)
    (dd / "decision.txt").write_text("\n".join(L) + "\n")
    (dd / "decision.json").write_text(json.dumps(out, indent=1, default=str))
    print("\n".join(L))
    return out


def cmd_dec_decide(a):
    dec_decide(a.dir, a.ud31)
    return 0


# ------------------------------------------------------------------------------------------------ selftest
def selftest(a):
    S = score()
    d = Path(a.dir)
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    bad = []

    def chk(name, ok, detail=""):
        print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + detail) if detail else ''}")
        if not ok:
            bad.append(name)
    rng = np.random.default_rng(31)
    # 1 Q8_0 decoder against a scalar transcription of ggml's loop
    blk = rng.integers(0, 256, size=(50, 34), dtype=np.uint8)
    blk[:, :2] = np.frombuffer(rng.uniform(-0.02, 0.02, 50).astype(np.float16).tobytes(), np.uint8).reshape(50, 2)
    vec = dequant_q8_0(blk)
    ref = np.array([dequant_q8_0_scalar(bytes(b)) for b in blk], np.float32)
    chk("Q8_0 decoder = ggml dequantize_row_q8_0 (50 random blocks)", np.array_equal(vec, ref))
    # 2 head sources: P's pack copies = the bytes score.py's Head reads from the GGUF; U / R's output.weight (headers)
    G = gguf_reader()
    src = head_sources(X28H)
    g = G.GGUFFile(S.GGUF)
    t = {x.name: x for x in g.tensors}
    same = all(read_at(src["pack"] / "dense.bin", src["hc"][k]["off"], src["hc"][k]["n"]) ==
               read_at(S.GGUF, g.data_start + t[k].offset, src["hc"][k]["n"]) for k in HC_NEED)
    chk("P: the pack's output_hc_* = score.py Head's GGUF bytes", same)
    chk("P: output.weight Q6_K where score.py reads it", src["out"][0] == S.GGUF and src["out"][1] == g.data_start
        + t["output.weight"].offset and src["out"][2] == "Q6_K")
    uh = WS / "work/qwen4-kit/unsloth-v31/headers/UD-IQ3_XXS" / (U_NAME % 1)
    if uh.exists():
        p, off, ty, sh = out_weight(uh)
        chk("U (header files): output.weight Q6_K [2560, 248320] in shard 2", ty == "Q6_K" and sh == [N_EMBD, VOCAB]
            and p.name == U_NAME % 2, f"{ty} {sh} {p.name}")
    if (R_DIR / (R_NAME % 1)).exists():
        p, off, ty, sh = out_weight(R_DIR / (R_NAME % 1))
        chk("R (HF cache): output.weight Q8_0 [2560, 248320] in shard 2", ty == "Q8_0" and sh == [N_EMBD, VOCAB]
            and p.name == R_NAME % 2, f"{ty} {sh} {p.name}")
    # 3 the configs: written + checked; a tampered copy fails
    cd = d / "configs"
    cmd_configs(argparse.Namespace(outdir=str(cd)))
    chk("configs + cfgcheck PASS", cmd_cfgcheck(argparse.Namespace(outdir=str(cd), gate=None, gates=None)) == 0)
    c = json.loads((cd / "ud31-U.json").read_text())
    c["env"]["STRATA_GDN_TC"] = "1"
    (cd / "ud31-U.json").write_text(json.dumps(c))
    chk("a stray switch in U's config fails cfgcheck", cmd_cfgcheck(argparse.Namespace(outdir=str(cd), gate=None, gates=None)) == 1)
    diffs = sorted(cfg_diffs(arm_configs()["R"], json.loads(X28H.read_text())))
    chk("R = x28h + its memory form only", all(re.sub(r"=.*$", "", x) in {
        "arg --pack", "arg --native", "arg --ple-gguf", "key log", "key _comment", "env CUDA_VISIBLE_DEVICES",
        "env STRATA_UNBUFFERED_LOAD", "arg --expert-cache-device1", "arg --chat-cache-mib", "arg --resident-budget-gib",
        "env STRATA_HC_Q8"} for x in diffs), "; ".join(diffs))
    # 4 predl / rehash on synthetic files
    dd = d / "dl"
    dd.mkdir()
    tree, sums = [], []
    for i in range(1, 5):
        b = rng.integers(0, 256, size=1000 + i, dtype=np.uint8).tobytes()
        (dd / (U_NAME % i)).write_bytes(b)
        oid = hashlib.sha256(b).hexdigest()
        tree.append({"type": "file", "path": "UD-IQ3_XXS/" + U_NAME % i, "lfs": {"oid": oid, "size": len(b)}})
        sums.append(f"{oid}  {U_NAME % i}")
    (d / "tree.json").write_text(json.dumps(tree))
    (dd / "SHA256SUMS").write_text("\n".join(sums[:3]) + "\n")
    ns = argparse.Namespace(dir=str(dd), tree=str(d / "tree.json"), gate=None, gates=None)
    chk("predl: a missing SHA256SUMS line refuses", cmd_predl(ns) == 1)
    (dd / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    chk("predl: complete -> PASS", cmd_predl(ns) == 0)
    (dd / "x.gguf.part").write_bytes(b"x")
    chk("predl: a .part file refuses", cmd_predl(ns) == 1)
    (dd / "x.gguf.part").unlink()
    chk("rehash: PASS", cmd_rehash(ns) == 0)
    with open(dd / (U_NAME % 2), "r+b") as f:
        f.seek(10)
        f.write(b"\xff\x00")
    chk("rehash: a changed byte fails", cmd_rehash(ns) == 1)
    # 5 prenll (11-05: validate_ref PASS is all; no ADOPTED-BOUND.json, any decision status)
    nr = d / "nll"
    nr.mkdir()
    (nr / "gates.txt").write_text("validate_ref PASS offline head AGREES\n")
    np_ = argparse.Namespace(root=str(nr), gate=None, gates=None)
    chk("prenll: validate_ref PASS, no ADOPTED-BOUND.json, no decision.json -> PASS", cmd_prenll(np_) == 0)
    (nr / "decision.json").write_text(json.dumps({"status": "NOT JUDGED"}))
    (nr / "ADOPTED-BOUND.REVOKED.json").write_text("{}")
    chk("prenll: a revoked bound and another decision status do not refuse", cmd_prenll(np_) == 0)
    (nr / "gates.txt").write_text("validate_ref FAIL DOES NOT AGREE\n")
    chk("prenll: validate_ref FAIL refuses", cmd_prenll(np_) == 1)
    (nr / "gates.txt").write_text("validate_ref PASS offline head AGREES\n")
    # 6 the compare pipeline on synthetic dumps with per-arm heads (small dims)
    n, hc, lr, V = 16, 4, 4, 200
    Dd = n * hc

    def mkhead(seed):
        r = np.random.default_rng(seed)
        return S.Head(weights=(r.uniform(0.5, 1.5, Dd).astype(np.float32), r.standard_normal((lr, Dd)).astype(np.float32) * 0.2,
                               r.standard_normal((Dd, lr)).astype(np.float32) * 0.2, r.standard_normal((V, n)).astype(np.float32),
                               n, hc, lr))
    hP, hU, hR = mkhead(1), mkhead(2), mkhead(3)
    hU.W = hP.W + 0.05 * np.random.default_rng(4).standard_normal(hP.W.shape).astype(np.float32)   # a near head
    texts = {"t1": rng.integers(0, V, 6000).tolist(), "t2": rng.integers(0, V, 4000).tolist()}
    base_rows = {t: rng.standard_normal((len(ids) - 1, Dd)).astype(np.float32) for t, ids in texts.items()}
    rows = {"P": base_rows, "S": base_rows,
            "U": {t: v + 0.05 * rng.standard_normal(v.shape).astype(np.float32) for t, v in base_rows.items()},
            "R": {t: v + 0.10 * rng.standard_normal(v.shape).astype(np.float32) for t, v in base_rows.items()}}
    cr = d / "cmp"
    for arm, rr in rows.items():
        o = cr / arm
        o.mkdir(parents=True)
        reqs = []
        for i, (t, ids) in enumerate(texts.items()):
            keep = S.bf16_round(rr[t])[::8]
            np.save(o / f"a.{i}.npy", (np.ascontiguousarray(keep).view(np.uint32) >> 16).astype(np.uint16))
            reqs.append({"name": f"{t}-{len(ids)}", "file": t, "cut": len(ids), "kind": "text", "dump": f"a.{i}.npy",
                         "rows": int(keep.shape[0])})
        (o / "index.json").write_text(json.dumps({"requests": reqs, "rows": "all:8"}))
    prm = dict(DEFAULTS, boot=2000)
    heads = {"P": hP, "S": hP, "U": hU, "R": hR}
    keys = {"P": "kP", "S": "kP", "U": "kU", "R": "kR"}
    passes = plan_passes(keys, "R")
    chk("plan: two passes with two heads each (R+P+S, R+U)", passes == [["R", "P", "S"], ["R", "U"]], str(passes))
    ids_of = lambda f: texts[f]
    merged = None
    for ps in passes:
        m = measure(cr, ps, {x: heads[x] for x in ps}, "R", "R", prm, ids_of, chunk=96)
        if merged is None:
            merged = m
        else:
            chk("passes score the same positions, R's NLL identical", m["keys"] == merged["keys"] and m["nll"]["R"] == merged["nll"]["R"])
            for kind in ("nll", "kl", "flip"):
                for x, v in m[kind].items():
                    merged[kind].setdefault(x, v)
    res = stats_of(merged, ["P", "U", "S", "R"], "R", "P", prm)
    npos = sum(len([p for p in range(0, len(ids) - 1, 8) if p >= 1024 and p + 1 < len(ids)]) for ids in texts.values())
    chk(f"positions: every 8th row from 1,024 ({npos})", res["n"] == npos, str(res["n"]))
    chk("S (P's rows, P's head) = P exactly: d 0, dKL 0", res["d"]["S"]["d"] == 0 and res["d"]["S"]["frac_exact0"] == 1.0
        and res["dkl"]["S"]["d"] == 0)
    chk("U and R differ from P", res["d"]["U"]["d"] != 0 and res["kl"]["U"]["mean"] > 0 and res["d"]["R"]["se"] > 0)
    # one position by hand: KL(R || U) with each arm's own head, float64
    t0n, p0 = merged["keys"][5]
    t0 = t0n.split("-")[0]
    rU = S.bf16_round(rows["U"][t0][p0][None, :])
    rR = S.bf16_round(rows["R"][t0][p0][None, :])
    lu, lr_ = hU.logp(rU)[0], hR.logp(rR)[0]
    kl_hand = float((np.exp(lr_) * (lr_ - lu)).sum())
    chk("KL(R || U) at one position = a float64 computation with each arm's own head",
        abs(kl_hand - merged["kl"]["U"][5]) < 1e-4, f"{kl_hand:.6f} vs {merged['kl']['U'][5]:.6f}")
    lu_single = hP.logp(rU)[0]                                   # what one shared head (score.py's) would give
    chk("the per-arm head matters (U with P's head gives another KL)", abs(float((np.exp(lr_) * (lr_ - lu_single)).sum()) - kl_hand) > 1e-4)
    # 7 decide on synthetic gaps (11-05: the KL rules at the text level from a synthetic rows.tsv; the 11 texts, 3 of them
    # duplicates that decide must drop)
    TX = [("32k", 32768), ("pp32k", 32768), ("tf-long28k", 28672), ("tf-long40k", 32768), ("tf-long64k", 32768),
          ("tf-long96k", 32768), ("tf-long112k", 32768), ("pp4k", 4096), ("pp8k", 8019), ("ldrsyn20k", 16110), ("rep9k", 9010)]

    def mkrows(path, fU, fS=1.0, dU=0.0, seed=5):
        """P's KL(R || P) per position; U's = P's x fU(text) (paired, 3 % noise), S's = P's x fS; flips paired; rep9k's KL ~1e-4"""
        r_ = np.random.default_rng(seed)
        with open(path, "w") as fo:
            fo.write("text\tpos\tnll_P\tnll_U\tnll_S\tnll_R\tkl_P\tflip_P\tkl_U\tflip_U\tkl_S\tflip_S\n")
            for t, n in TX:
                fu, fs = (fU(t) if callable(fU) else fU), (fS(t) if callable(fS) else fS)
                base = 1e-4 if t == "rep9k" else 0.3
                for i in range(200):
                    k, u, nl = r_.exponential(base), r_.random(), 2 + 0.5 * abs(float(r_.standard_normal()))
                    ku = k * fu * math.exp(0.03 * float(r_.standard_normal()))
                    fo.write(f"{t}-{n}\t{1024 + 8 * i}\t{nl:.6f}\t{nl + dU + 0.05 * float(r_.standard_normal()):.6f}\t"
                             f"{nl:.6f}\t{nl - 0.1:.6f}\t{k:.6g}\t{float(u < 0.1)}\t{ku:.6g}\t{float(u < 0.1 * fu)}\t"
                             f"{k * fs:.6g}\t{float(u < 0.1 * fs)}\n")

    def mkgap(name, rows, gates, speed):
        r = d / name
        r.mkdir()
        (r / "gates.txt").write_text("".join(f"{k} {s} {t}\n" for k, s, t in gates))
        (r / "rules.txt").write_text(rules_text())          # the driver's snapshot at the gap's start
        (r / "result.json").write_text(json.dumps({"n": 2200, "ref": "R"}))
        if rows is not None:
            mkrows(r / "rows.tsv", **rows)
        sp = r / "speed"
        sp.mkdir()
        for arm, (dec_, pr_) in speed.items():
            for k in (1, 2, 3):
                jit = 1 + 0.004 * (k - 2)
                (sp / f"{arm}{k}n.jsonl").write_text("".join(json.dumps(
                    {"id": w, "decode_tps": dec_ * jit * (1 + 0.01 * j), "prompt_tps": pr_ * jit * (1 + 0.02 * j)}) + "\n"
                    for j, w in enumerate(load("g17_rules_t", G17).WL9)))
        return decide(r, nr)
    allok = [(f"{p}_{x}", "PASS", "synthetic") for p in ("run", "env", "validate") for x in "PUSR"] + \
            [("head_P", "PASS", "x"), ("compare", "PASS", "x"), ("e7_U1", "INFO", "exact7 x: 1/7"), ("e7_U2", "PASS", "7/7"),
             ("e7_S1", "INFO", "0/7"), ("e7_S2", "PASS", "7/7"), ("env_e7U1", "PASS", ""), ("env_e7U2", "PASS", ""),
             ("env_e7S1", "PASS", ""), ("env_e7S2", "PASS", ""), ("splice_verify", "PASS", ""), ("pack_S_dense", "PASS", "")] + \
            [(f"{c}_{x}{s}", "PASS", "") for c in ("lossless",) for x in "US" for s in ("_cfg", "_log")] + \
            [(f"start_{x}", "PASS", "") for x in "PUS"] + [(f"env_scr{x}{k}", "PASS", "") for x in "PUS" for k in (1, 2, 3)] + \
            [(f"hcq8_nll_{x}", "PASS", "") for x in "PUSR"] + [(f"hcq8_scr_{x}", "PASS", "") for x in "PUS"]
    sp_ok = {"P": (150, 1000), "U": (149.5, 1003), "S": (151, 1001)}
    dj = mkgap("g-good", {"fU": 0.7}, allok, sp_ok)
    q = dj["quality"]
    chk("decide: 8 distinct texts (pp32k, tf-long96k, pp8k dropped); U x0.7 -> BETTER THAN P; S = P -> INSIDE, AT OR BELOW",
        q["texts"] == ["32k", "tf-long28k", "tf-long40k", "tf-long64k", "tf-long112k", "pp4k", "ldrsyn20k", "rep9k"]
        and q["dropped"] == ["pp32k", "pp8k", "tf-long96k"] and q["kl_U"] == "BETTER THAN P"
        and q["kl_S"] == "INSIDE THE MARGIN, AT OR BELOW P" and q["pack_rounding"]["dec_followup"] == "NOT NEEDED",
        str({k: q.get(k) for k in ("texts", "dropped", "kl_U", "kl_S")}))
    chk("decide: rep9k (KL ~1e-4) is below the floor on mean / p90, not a side",
        q["kl_U_detail"]["mean"]["floor"] == 1 and q["kl_U_detail"]["mean"]["better"] == 7, str(q["kl_U_detail"]["mean"]))
    chk("decide: text NLL is INFO with the whole-text and the 2,048-block figure", "nll_info" in q and "text" in q["nll_info"]["U"]["d"]
        and "b2048" in q["nll_info"]["U"]["d"] and "TEXT NLL - INFO ONLY" in (d / "g-good" / "decision.txt").read_text())
    chk("decide: exactness REPEATABLE both; speed NO LOSS both", dj["exactness"] == {"U": "REPEATABLE", "S": "REPEATABLE"}
        and dj["speed"] == {"U": "NO LOSS", "S": "NO LOSS"}, f"{dj['exactness']} {dj['speed']}")
    dj = mkgap("g-worse", {"fU": 1.3}, allok, {"P": (150, 1000), "U": (140, 1000), "S": (150, 1000)})
    q = dj["quality"]
    chk("decide: U x1.3 -> WORSE THAN P, recorded INCLUDES PACK ROUNDING, follow-up WANTED",
        q["kl_U_class"] == "WORSE THAN P" and q["kl_U"] == "INCLUDES PACK ROUNDING"
        and q["pack_rounding"]["dec_followup"] == "WANTED", str({k: q.get(k) for k in ("kl_U", "kl_U_class")}))
    chk("decide: U 6.7 % slower decode on every workload -> LOSS", dj["speed"]["U"] == "LOSS", dj["speed"]["U"])
    g2 = [x for x in allok if x[0] not in ("e7_U2", "validate_R")] + [("e7_U2", "FAIL", "5/7"), ("validate_R", "FAIL", "x"),
                                                                       ("env_scrS2", "FAIL", "stray")]
    dj = mkgap("g-mixed", {"fU": 0.7}, g2, sp_ok)
    chk("decide: e7_U2 FAIL -> NOT REPEATABLE; R not valid -> QUALITY NOT JUDGED (follow-up NOT DECIDED); S's env FAIL -> VOID",
        dj["exactness"]["U"] == "NOT REPEATABLE" and dj["quality"]["status"] == "NOT JUDGED"
        and dj["quality"]["pack_rounding"]["dec_followup"] == "NOT DECIDED" and dj["speed"]["S"].startswith("VOID"),
        f"{dj['exactness']} {dj['quality'].get('status')} {dj['speed']}")
    g3 = [x for x in allok if x[0] != "head_P"] + [("head_P", "FAIL", "differ")]
    dj = mkgap("g-nohead", {"fU": 0.7}, g3, sp_ok)
    chk("decide: head_P FAIL -> QUALITY NOT JUDGED", dj["quality"]["status"] == "NOT JUDGED")
    dj = mkgap("g-norows", None, allok, sp_ok)
    chk("decide: no rows.tsv -> QUALITY NOT JUDGED", dj["quality"]["status"] == "NOT JUDGED")
    fres = None
    # 8 headcheck parsing
    (d / "sp.txt").write_text("check-32k-2049                   KL(window || offline head) 0.01234  top-1 same  NLL window 1 head 1\n")
    (d / "v.json").write_text(json.dumps({"rows": [{"name": "check-32k-2049", "kl": 0.0123449}]}))
    chk("headcheck: equal to 5 decimals -> PASS", cmd_headcheck(argparse.Namespace(scorepy=str(d / "sp.txt"), vjson=str(d / "v.json"),
                                                                                  gate=None, gates=None)) == 0)
    (d / "v.json").write_text(json.dumps({"rows": [{"name": "check-32k-2049", "kl": 0.0125}]}))
    chk("headcheck: a different KL -> FAIL", cmd_headcheck(argparse.Namespace(scorepy=str(d / "sp.txt"), vjson=str(d / "v.json"),
                                                                             gate=None, gates=None)) == 1)
    selftest_1105(d, chk, mkgap, fres, allok, sp_ok, nr, rng)
    print(f"selftest: {len(bad)} failure(s)" + (": " + ", ".join(bad) if bad else ""))
    return 1 if bad else 0


def selftest_1105(d, chk, mkgap, fres, allok, sp_ok, nr, rng):
    """11-05: the switch in the configs, the hc forms from the headers, the switch's line, the pack-rounding rule,
    the rules snapshot, the decode-path follow-up (pre, runner wiring on decpath's mock engine, args, compare, decide)"""
    S = score()
    # 9 configs: U and R carry STRATA_HC_Q8=1, S and P not; cfgcheck catches each mistake
    cd = d / "configs-1105"
    cmd_configs(argparse.Namespace(outdir=str(cd)))
    ac = arm_configs()
    chk("configs: STRATA_HC_Q8=1 in U and R, absent in S and x28h",
        ac["U"]["env"].get("STRATA_HC_Q8") == "1" and ac["R"]["env"].get("STRATA_HC_Q8") == "1"
        and "STRATA_HC_Q8" not in ac["S"]["env"] and "STRATA_HC_Q8" not in json.loads(X28H.read_text())["env"])
    ns = argparse.Namespace(outdir=str(cd), gate=None, gates=None)
    chk("cfgcheck PASS on the 11-05 configs", cmd_cfgcheck(ns) == 0)
    for arm, mut in (("U", lambda e: e.pop("STRATA_HC_Q8")), ("R", lambda e: e.pop("STRATA_HC_Q8")),
                     ("S", lambda e: e.update(STRATA_HC_Q8="1")), ("U", lambda e: e.update(STRATA_HC_Q8="0"))):
        c = json.loads((cd / f"ud31-{arm}.json").read_text())
        keep = json.dumps(c)
        mut(c["env"])
        (cd / f"ud31-{arm}.json").write_text(json.dumps(c))
        chk(f"cfgcheck fails: {arm} with STRATA_HC_Q8={c['env'].get('STRATA_HC_Q8', 'unset')}", cmd_cfgcheck(ns) == 1)
        (cd / f"ud31-{arm}.json").write_text(keep)
    chk("cfgcheck PASS again after the restores", cmd_cfgcheck(ns) == 0)
    # 10 the hyper-connection forms from the GGUF headers (the asymmetry note)
    ista = hc_header(S.GGUF)
    chk("ISTA (P / S): every hc down/up, inject, output down/up BF16 (norms F32): unrounded, no Q8_0",
        ista["forms"].get("down/up") == {"BF16": 192} and ista["forms"].get("inject") == {"BF16": 96}
        and ista["forms"].get("output down/up") == {"BF16": 2} and ista["forms"].get("norm") == {"F32": 96}
        and ista["q8_tensors"] == 0, str(ista))
    for name, first in (("U (downloaded shards)", U_DIR / (U_NAME % 1)),
                        ("U (header files)", WS / "work/qwen4-kit/unsloth-v31/headers/UD-IQ3_XXS" / (U_NAME % 1)),
                        ("R (HF cache)", R_DIR / (R_NAME % 1))):
        if first.exists():
            h = hc_header(first)
            chk(f"{name}: 192 layer down/up + 2 output Q8_0 = 675,430,400 B (0.63 GiB), injects F32",
                h["forms"].get("down/up") == {"Q8_0": 192} and h["forms"].get("output down/up") == {"Q8_0": 2}
                and h["forms"].get("inject") == {"F32": 96} and h["q8_bytes"] == 675430400 and h["layer_q8"] == 192, str(h))
    # 11 the switch's line (hcline) on synthetic logs, U's config against U's header files
    uh = WS / "work/qwen4-kit/unsloth-v31/headers/UD-IQ3_XXS" / (U_NAME % 1)
    if uh.exists():
        cu = json.loads(json.dumps(ac["U"]))
        cu["args"][cu["args"].index("--native") + 1] = str(uh)
        ln = "strata: STRATA_HC_Q8=1: %s GiB of Q8_0 hyper-connection projections for the verify read\n"
        chk("hcline on: the file's own 0.63 GiB -> PASS", hcline_check("x\n" + ln % "0.63", cu, "on")[0])
        chk("hcline on: 0.62 (layers quantized from BF16) -> FAIL", not hcline_check(ln % "0.62", cu, "on")[0])
        chk("hcline on: no line -> FAIL", not hcline_check("nothing\n", cu, "on")[0])
        chk("hcline on: two starts, one wrong -> FAIL", not hcline_check(ln % "0.63" + ln % "0.62", cu, "on")[0])
        chk("hcline off: P (no line, switch unset) -> PASS", hcline_check("nothing\n", ac["S"], "off")[0])
        chk("hcline off: a line on P -> FAIL", not hcline_check(ln % "0.62", ac["S"], "off")[0])
    # 12 hcforms on a synthetic conversions.json
    pk = d / "pack-x"
    pk.mkdir()
    recs = [{"name": f"blk.{i}.hc_attn_down.weight", "src_type": "Q8_0", "dst_type": "BF16", "exact": False} for i in range(3)] + \
           [{"name": "blk.0.hc_ffn_inject.weight", "src_type": "F32", "dst_type": "BF16", "exact": True},
            {"name": "blk.1.hc_ffn_inject.weight", "src_type": "F32", "dst_type": "BF16", "exact": False},
            {"name": "blk.0.ffn_gate_inp.weight", "src_type": "F32", "dst_type": "BF16", "exact": True}]
    (pk / "conversions.json").write_text(json.dumps({"compat_bf16": True, "tensors": recs}))
    c, _ = hc_conversions(pk)
    chk("hcforms: hc records only, by role / types / exactness", c == {"down/up Q8_0->BF16 rounded": 3,
                                                                       "inject F32->BF16 exact": 1, "inject F32->BF16 rounded": 1}, str(c))
    # 13 the pack-rounding rule on the text-level KL verdict (11-05)
    five = ("32k", "tf-long28k", "tf-long40k", "tf-long64k", "tf-long112k")
    four = ("32k", "tf-long28k", "tf-long40k", "tf-long64k")
    cases = [("pr-worse", {"fU": 1.3}, "WORSE THAN P", "INCLUDES PACK ROUNDING", "WANTED"),
             ("pr-above", {"fU": 1.05}, "INSIDE THE MARGIN, ABOVE P", "INCLUDES PACK ROUNDING", "WANTED"),
             ("pr-below", {"fU": 0.97}, "INSIDE THE MARGIN, AT OR BELOW P", "INCLUDES PACK ROUNDING", "WANTED"),
             ("pr-better", {"fU": 0.7}, "BETTER THAN P", "BETTER THAN P", "NOT NEEDED"),
             ("pr-mixed", {"fU": lambda t: 1.3 if t in five else 0.8}, "INSIDE THE MARGIN, ABOVE P", "INCLUDES PACK ROUNDING",
              "WANTED"),
             # 4 distinct texts worse + the 3 duplicates: 7 "texts" if the dedup failed (WORSE); 4 of 8 after it
             ("pr-dedup", {"fU": lambda t: 1.3 if t in four + ("pp32k", "tf-long96k", "pp8k") else 1.0},
              "INSIDE THE MARGIN, ABOVE P", "INCLUDES PACK ROUNDING", "WANTED")]
    for name, rows, cls, rec, fu in cases:
        dj = mkgap(name, rows, allok, sp_ok)
        q = dj["quality"]
        txt = (d / name / "decision.txt").read_text()
        chk(f"pack rounding: {name} -> class {cls}, recorded {rec}, follow-up {fu}",
            q.get("kl_U_class") == cls and q.get("kl_U") == rec and q["pack_rounding"]["dec_followup"] == fu
            and (FOLLOW_MARK + fu) in txt and PACK_TAG in txt
            and (("RECORDED AS INCLUDES PACK ROUNDING" in txt) == (rec == "INCLUDES PACK ROUNDING")),
            f"{q.get('kl_U_class')} / {q.get('kl_U')} / {q['pack_rounding']['dec_followup']} / mean "
            f"{ {k: q.get('kl_U_detail', {}).get('mean', {}).get(k) for k in ('worse', 'better', 'floor')} }")
    q = json.loads((d / "pr-worse" / "decision.json").read_text())["quality"]
    chk("pack rounding: S (= P) untagged and not recorded as pack rounding",
        q.get("kl_S") == "INSIDE THE MARGIN, AT OR BELOW P" and "kl_S_class" not in q, str(q.get("kl_S")))
    dj = mkgap("pr-nohc", {"fU": 1.3}, [x for x in allok if x[0] != "hcq8_nll_U"] + [("hcq8_nll_U", "FAIL", "0.62")], sp_ok)
    chk("hcq8_nll_U FAIL -> U's KL NOT DECIDED, follow-up NOT DECIDED",
        dj["quality"]["kl_U"] == "NOT DECIDED" and dj["quality"]["pack_rounding"]["dec_followup"] == "NOT DECIDED")
    dj = mkgap("pr-scr", {"fU": 1.0}, [x for x in allok if x[0] != "hcq8_scr_U"] + [("hcq8_scr_U", "FAIL", "no line")], sp_ok)
    chk("hcq8_scr_U FAIL -> U's exactness CHECK FAILED, speed VOID",
        dj["exactness"]["U"].startswith("CHECK FAILED") and dj["speed"]["U"].startswith("VOID"), f"{dj['exactness']} {dj['speed']}")
    # 13b calibration on REAL rows (read only): the NLL gap's rounding references and v2, all against ref, on the
    # recompute's 8 distinct texts - the rule must call none of them WORSE / BETTER (the docstring's counts)
    if RECOMP_ROWS.exists():
        Dr = read_rows_tsv(RECOMP_ROWS)
        prm_c = dict(DEFAULTS, boot=500)
        mx = {}
        for xa, ba in (("cpushare", "unfused"), ("unfused", "cpushare"), ("v2", "unfused"), ("v2", "cpushare"),
                       ("unfused", "v2"), ("cpushare", "v2")):
            tl = text_level_kl(Dr, xa, ba, prm_c)
            mx[(xa, ba)] = (tl["verdict"], max(max(m["worse"], m["better"]) for m in tl["metrics"].values()))
        pair = max(mx[k][1] for k in (("cpushare", "unfused"), ("unfused", "cpushare")))
        v2m = max(mx[k][1] for k in mx if "v2" in k)
        chk(f"calibration (recompute rows, 8 texts): rounding pair at most {pair} texts on one side (doc: 3), v2 at most "
            f"{v2m} (doc: 5); all INSIDE THE MARGIN", len(Dr["texts"]) == 8 and pair == 3 and v2m == 5
            and all(v.startswith("INSIDE") for v, _ in mx.values()), str(mx))
    # 14 the rules snapshot: equal -> no flag; changed -> FLAG
    (d / "pr-below" / "rules.txt").write_text(rules_text() + "x\n")
    dj = decide(d / "pr-below", nr)
    chk("rules snapshot: a changed rule text is flagged", any("CHANGED" in f for f in dj["flags"]), str(dj["flags"]))
    chk("rules snapshot: the unchanged one is not", not any("rule" in f for f in json.loads(
        (d / "pr-worse" / "decision.json").read_text())["flags"]))
    # 15 the follow-up: decpath's runner with dec's plan (its mock engine), the env rule, the args check
    DP = dp_mod()
    ids_of = S.load_ids
    sc = d / "dec"
    sc.mkdir()
    mock = sc / "mock_engine.py"
    mock.write_text(DP.MOCK)
    mock.chmod(0o755)
    cfgP = {"exe": str(mock), "args": ["--pack", "/p/pack", "--native", "/p/n1.gguf", "--ple-gguf", "/p/n2.gguf", "--spec",
                                       "7", "--kv", "int8"], "env": {"CUDA_VISIBLE_DEVICES": "0", "STRATA_ROUTE_TAIL_SKIP": "0"},
            "cwd": str(sc)}
    cfgU = json.loads(json.dumps(cfgP))
    cfgU["args"][1], cfgU["args"][3], cfgU["args"][5] = "/u/pack", "/u/n1.gguf", "/u/n4.gguf"
    cfgU["env"]["STRATA_HC_Q8"] = "1"
    (sc / "cfgU.json").write_text(json.dumps(cfgU))
    qq = DP.qq_mod()
    Lp = 4096
    pargs = qq.engine_args(cfgP, False, Lp)
    pargs[pargs.index("--spec") + 1] = "2"
    pdec = sc / "pgap" / "dec"
    pdec.mkdir(parents=True)
    (pdec / "index.json").write_text(json.dumps({"kind": "logpos", "plan": "main", "config": str(X28H), "env": [], "args": pargs,
                                                 "requests": [{"name": "pp4k-2048", "file": "pp4k.tokens", "cut": 2048,
                                                               "first_line": 0, "end_line": 2047},
                                                              {"name": "rep9k-3000", "file": "rep9k.tokens", "cut": 3000,
                                                               "first_line": 2047, "end_line": 5046}]}))
    (pdec / "score.tsv").write_text("")
    plan, L_, _ = pdec_plan(pdec)
    chk("pdec_plan: dec's reads in order, L from its --short-read", plan == [("pp4k.tokens", 2048, 0), ("rep9k.tokens", 3000, 0)]
        and L_ == Lp, f"{plan} {L_}")
    ud = sc / "U"
    try:
        rc = cmd_dec_run(argparse.Namespace(config=str(sc / "cfgU.json"), outdir=str(ud), pdec=str(pdec), budget_min=30,
                                            min_free_gb=0))
    except SystemExit as e:
        rc = f"SystemExit {e}"
    ui = json.loads((ud / "index.json").read_text()) if (ud / "index.json").exists() else {}
    chk("dec-run on decpath's mock engine: rc 0, dec's two texts at dec's cuts, cut-1 lines each",
        rc == 0 and [(r["file"], r["cut"]) for r in ui.get("requests", [])] == [("pp4k.tokens", 2048), ("rep9k.tokens", 3000)]
        and all(r["end_line"] - r["first_line"] == r["cut"] - 1 for r in ui["requests"]), f"rc {rc} {ui.get('problems')}")
    chk("dec-run: the engine args = dec's (L, --short-read, --max-context) except U's three paths",
        not dec_args_diff(ui.get("args", []), pargs, cfgU), "; ".join(dec_args_diff(ui.get("args", []), pargs, cfgU)))
    bad_args = list(ui.get("args", []))
    bad_args[bad_args.index("--spec") + 1] = "7"
    chk("dec-args: a changed setting (--spec 7) differs", bool(dec_args_diff(bad_args, pargs, cfgU)))
    bad_args = list(ui.get("args", []))
    bad_args[bad_args.index("--pack") + 1] = "/other/pack"
    chk("dec-args: a path that is not U's differs", bool(dec_args_diff(bad_args, pargs, cfgU)))
    NR = load("nll_rules_ud31", WS / "work/r23/nll_rules.py")
    wantU = NR.want_of(ac["U"], None, qq.FIXED_ENV)
    aw = {"--expert-cache": "1", "--pcie-frac": "0", "--kv": "fp16", "--adapt-every": "100000", "--suffix-draft": "0",
          "--prompt-cache": "0", "--spec": "2", "--short-read": str(Lp + 64), "--prefill": "512", "--max-context": str(Lp + 512)}
    envU = dict(wantU, STRATA_LOGPOS="x", STRATA_LOGPOS_TOPK="64")
    argvU = [str(EXE), "--serve"] + [v for k, x in aw.items() for v in (k, x)]
    chk("dec envwatch rule: U's engine with the switch passes", not DP.check_engine(envU, argvU, wantU, 2, aw, "logpos"),
        str(DP.check_engine(envU, argvU, wantU, 2, aw, "logpos")))
    chk("dec envwatch rule: U's engine without the switch fails",
        bool(DP.check_engine({k: v for k, v in envU.items() if k != "STRATA_HC_Q8"}, argvU, wantU, 2, aw, "logpos")))
    # 16 dec-pre on synthetic decisions (files=False: U's pack / shards are the gap's)
    u31 = sc / "u31"
    u31.mkdir()
    pg = pdec.parent / "gates.txt"
    pg.write_text("run_dec PASS x\nenv_dec PASS x\n")
    cu_path = d / "configs-1105" / "ud31-U.json"
    for name, fu in (("pr-worse", "WANTED"), ("pr-better", "NOT NEEDED")):
        for f in ("decision.json", "decision.txt"):
            shutil.copy(d / name / f, u31 / f)
        probs = dec_pre_problems(u31, pdec, cu_path, files=False)
        rest = [p for p in probs if f"text(s) (< {DEC_MIN_TEXTS})" not in p]
        chk(f"dec-pre: the v3.1 decision {fu} -> " + ("only the 2-text dec arm stops it" if fu == "WANTED" else "refused"),
            (not rest) if fu == "WANTED" else any("does not ask for it" in p for p in probs), "; ".join(probs))
    (u31 / "decision.txt").write_text("no marker\n")
    shutil.copy(d / "pr-worse" / "decision.json", u31 / "decision.json")
    chk("dec-pre: decision.txt without the WANTED line -> refused",
        any("disagree" in p for p in dec_pre_problems(u31, pdec, cu_path, files=False)))
    pg.write_text("run_dec FAIL x\nenv_dec PASS x\n")
    chk("dec-pre: the decode-path gap's run_dec FAIL -> refused",
        any("run_dec is FAIL" in p for p in dec_pre_problems(u31, pdec, cu_path, files=False)))
    # 17 dec-compare + dec-decide on synthetic logpos rows of dec's 8 texts (only the compare positions written in full)
    texts = [("pp4k.tokens", 2000), ("rep9k.tokens", 5000), ("ldrsyn20k.tokens", 2000), ("32k.tokens", 2000),
             ("tf-long64k.prompt", 2000), ("tf-long28k.prompt", 2000), ("tf-long112k.prompt", 2000), ("tf-long40k.prompt", 2000)]

    def mklog(dirp, shift, seed, texts_=texts, wrong=0, step=0.10):
        dirp.mkdir(parents=True, exist_ok=True)
        r_ = np.random.default_rng(seed)
        lines, reqs = [], []
        for f, cut in texts_:
            ids = ids_of(f)
            first = len(lines)
            sh = shift(f.split(".")[0]) if callable(shift) else shift
            for p in range(cut - 1):
                if p % DEC_EVERY or p < DEC_MIN_POS:
                    lines.append(f"{p}\t0")                    # never parsed (not a compare position)
                    continue
                tg = ids[p + 1] if not (wrong and p == 1600) else ids[p + 1] + 1
                lt = -1.0 - 0.1 * abs(float(r_.standard_normal())) - sh
                top = [tg] + [tg + 1 + j for j in range(63)]
                lps = [lt] + [lt - 0.5 - j * step for j in range(63)]
                lines.append("\t".join([str(p), str(tg), f"{lt:.6f}", str(tg if r_.random() < 0.9 else tg + 1), f"{lt:.6f}", "0",
                                        "nan", "nan"] + [f"{a_}:{b_:.6f}" for a_, b_ in zip(top, lps)]))
            reqs.append({"name": f"{f.split('.')[0]}-{cut}", "file": f, "cut": cut, "first_line": first, "end_line": len(lines)})
        (dirp / "score.tsv").write_text("\n".join(lines) + "\n")
        (dirp / "index.json").write_text(json.dumps({"kind": "logpos", "requests": reqs, "args": pargs}))
    pd2 = sc / "syn" / "pdec"
    mklog(pd2, 0.0, 1)
    rows = sc / "syn" / "rows.tsv"
    with open(rows, "w") as fo:
        fo.write("text\tpos\tnll_P\tnll_U\tnll_S\tnll_R\n")
        for f, cut in texts + [("pp32k.tokens", 2000)]:            # a duplicate text in the v3.1 rows is never matched
            for p in range(1024, cut - 1, 8):
                fo.write(f"{f.split('.')[0]}-{cut}\t{p}\t1.0\t1.08\t1.0\t0.9\n")
    prows = sc / "syn" / "nll-rows.tsv"                    # P prompt: the NLL gap's ref rows (its column layout)
    with open(prows, "w") as fo:
        fo.write("block\ttext\tpos\tnll_ref\tnll_unfused\tkl_unfused\tflip_unfused\n")
        for f, cut in texts:
            for p in range(1024, cut - 1, 8):
                fo.write(f"0\t{f.split('.')[0]}-{cut}\t{p}\t1.0\t1.1\t0.1\t0\n")
    prm = dict(DEFAULTS, boot=2000)
    nexp = sum(len(range(1024, cut - 1, 8)) for _, cut in texts)
    ud2 = sc / "syn" / "U"
    mklog(ud2, 0.05, 2, step=0.07)                   # another shape over P's top 64: KL(P || U) > 0
    res = dec_compare(ud2, pd2, rows, prm, ids_of, prows)
    chk(f"dec-compare: every 8th position from 1,024 of 8 texts ({nexp}), targets all equal",
        res["n"] == nexp and res["target_mismatch"] == {"P": 0, "U": 0} and len(res["per_text"]) == 8,
        f"{res['n']} {res['target_mismatch']}")
    pdd = res["pooled"]["d"]
    chk("dec-compare: pooled d ~ +0.05 with the whole-text and the 2,048-block figure; 1-4K / 4-16K filled, 16-32K empty",
        abs(pdd["point"] - 0.05) < 0.02 and pdd["text"]["blocks"] == 8 and pdd["b2048"]["blocks"] > 8
        and res["strata"]["1-4K"]["n"] > 0 and res["strata"]["4-16K"]["n"] > 0 and res["strata"]["16-32K"]["n"] == 0, str(pdd))
    rc = res["rounding_cost"]
    chk("dec-compare: rounding cost (U dec - U prompt) - (P dec - P prompt) = d_dec - 0.08 at all positions, 8 texts; "
        "the P-prompt cross-check 0",
        rc["n"] == nexp and len(rc["per_text"]) == 8 and abs(rc["pooled"]["point"] - (pdd["point"] - 0.08)) < 1e-9
        and rc["p_prompt_crosscheck_max_abs"] == 0.0 and "b2048" in rc["pooled"], str(rc["pooled"]["point"]))
    chk("dec-compare: no P prompt rows -> no rounding cost (the verdict does not need it)",
        "rounding_cost" not in dec_compare(ud2, pd2, rows, prm, ids_of, None))
    p0 = res["per_text"]["pp4k"]
    chk("dec-compare: KL(P || U) over P's top 64 > 0 with the floor rule; top-1 agreement in (0, 1)",
        p0["kl"] > 1e-3 and 0 < p0["agree"] < 1, f"{p0['kl']:.4f} {p0['agree']:.3f}")
    mklog(sc / "syn" / "Uwrong", 0.05, 2, wrong=1)
    rw = dec_compare(sc / "syn" / "Uwrong", pd2, None, prm, ids_of)
    chk("dec-compare: a line with another target is counted and dropped", rw["target_mismatch"]["U"] == 8
        and rw["n"] == nexp - 8, str(rw["target_mismatch"]))
    # Karl's rule: the thresholds and the counting, on synthetic per-text d (ties included)
    chk("dec rule thresholds: N 8 -> 6 / 1, N 7 -> 6 / 0, N 6 -> 5 / 0, N 5 -> 4 / 0",
        [dec_thresholds(n) for n in (8, 7, 6, 5)] == [(6, 1), (6, 0), (5, 0), (4, 0)])
    pt = lambda ds: {f"t{i}": {"d": v} for i, v in enumerate(ds)}
    for ds, want in (([-0.1] * 7 + [0.1], "BETTER THAN P"), ([-0.1] * 6 + [0.1] * 2, "INCONCLUSIVE"),
                     ([0.1] * 6 + [0.0, 0.0], "WORSE THAN P"), ([-0.1] * 5 + [0.0] * 3, "INCONCLUSIVE"),
                     ([-0.1] * 6 + [0.1], "INCONCLUSIVE"), ([-0.1] * 6 + [0.0], "BETTER THAN P"),
                     ([0.1] * 5 + [0.0], "WORSE THAN P"), ([-0.1] * 4 + [1e-7], "BETTER THAN P"),
                     ([-0.1] * 4 + [0.1], "INCONCLUSIVE"), ([-0.1] * 4, "NOT JUDGED")):
        v = dec_text_verdict(pt(ds))[0]
        chk(f"dec rule: N {len(ds)}, lower {sum(x <= -DEC_TIE for x in ds)}, higher {sum(x >= DEC_TIE for x in ds)}, "
            f"ties {sum(abs(x) < DEC_TIE for x in ds)} -> {want}", v.startswith(want), v)
    # decide end to end
    dd = sc / "out"
    (dd / "gap").mkdir(parents=True)
    gp = "".join(f"{k} PASS synthetic\n" for k in ("env_decU", "run_decU", "dec_args", "hcq8_dec_U", "compare"))
    (dd / "gap" / "gates.txt").write_text(gp)
    for f in ("decision.json", "decision.txt"):
        shutil.copy(d / "pr-worse" / f, u31 / f)
    five = ("32k", "tf-long64k", "tf-long28k", "tf-long112k", "tf-long40k")
    for name, shift, tx, want in (("small", 0.05, texts, "WORSE THAN P"), ("lower", -0.05, texts, "BETTER THAN P"),
                                  ("same", None, texts, "INCONCLUSIVE"),
                                  ("five", lambda t: 0.05 if t in five else -0.05, texts, "INCONCLUSIVE"),
                                  ("seven", -0.05, texts[:7], "BETTER THAN P"), ("four", -0.05, texts[:4], "NOT JUDGED")):
        if shift is None:
            r_ = dec_compare(pd2, pd2, rows, prm, ids_of, prows)
        else:
            mklog(sc / "syn" / f"U-{name}", shift, 3, texts_=tx, step=0.07)
            r_ = dec_compare(sc / "syn" / f"U-{name}", pd2, rows, prm, ids_of, prows)
        (dd / "gap" / "result.json").write_text(json.dumps(r_))
        o = dec_decide(dd, u31, pk)
        txt = (dd / "decision.txt").read_text()
        chk(f"dec-decide: {name} ({len(r_['per_text'])} texts) -> {want} (lower {o.get('lower')}, higher {o.get('higher')})",
            o["verdict"] == want and (("Karl decides on a separate R decode-path gap" in txt) == (want == "INCONCLUSIVE"))
            and (("Karl's rule is written for 8 texts" in txt) == (want != "NOT JUDGED" and len(r_["per_text"]) < 8)),
            str(o.get("sides")))
        if name == "five":
            chk("dec-decide: the labelled uncertainty, the caveat-removed line, the inject flag, the rounding-cost line",
                "NO PACK-ROUNDING CAVEAT" in txt and "1 ROUNDED" in txt and "whole-text bootstrap" in txt
                and "2,048-token blocks - not used for the verdict" in txt and "the rounding cost per text" in txt
                and "signs - " in txt and "cross-check" in txt and o["inject_rounded"] == 1)
    (dd / "gap" / "gates.txt").write_text(gp.replace("dec_args PASS", "dec_args FAIL"))
    chk("dec-decide: dec_args FAIL -> NOT JUDGED", dec_decide(dd, u31, pk)["verdict"] == "NOT JUDGED")


# ------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    def sub(name, *pos):
        p = sp.add_parser(name)
        for x in pos:
            p.add_argument(x)
        p.add_argument("--gate")
        p.add_argument("--gates")
        return p
    sub("configs", "outdir")
    sub("cfgcheck", "outdir")
    sub("predl", "dir", "tree")
    sub("rehash", "dir", "tree")
    sub("prenll", "root")
    p = sp.add_parser("heads")
    p.add_argument("config", nargs="+")
    p.add_argument("--key", action="store_true")
    p = sub("validate", "outdir", "config")
    p.add_argument("--json")
    p.add_argument("--kl-mean", type=float, default=0.05)
    p.add_argument("--kl-max", type=float, default=0.5)
    sub("headcheck", "scorepy", "vjson")
    p = sub("compare", "root")
    p.add_argument("--cfg", action="append", required=True, help="ARM=CONFIG (P, U, S, R)")
    p.add_argument("--ref", default="R")
    p.add_argument("--base", default="P")
    p.add_argument("--bound", default=str(NLL_ROOT / "ADOPTED-BOUND.json"))
    p.add_argument("--threads", default="1")
    p.add_argument("--chunk", type=int, default=128)
    p.add_argument("--json")
    p.add_argument("--rows-out")
    p = sub("dirty")
    p.add_argument("--below-mb", type=int, default=256)
    p.add_argument("--max-s", type=float, default=300)
    p = sp.add_parser("decide")
    p.add_argument("root")
    p.add_argument("--nll-root", default=str(NLL_ROOT))
    p.add_argument("--out")
    p = sub("hcline", "log", "config")
    p.add_argument("--want", required=True, choices=["on", "off"])
    sub("hcforms", "pack")
    sp.add_parser("rules").add_argument("--out", required=True)
    p = sp.add_parser("dec-pre")
    p.add_argument("--ud31", default=str(UD31))
    p.add_argument("--pdec", default=str(PDEC))
    p.add_argument("--cfg", default=str(UD31 / "configs/ud31-U.json"))
    p = sp.add_parser("dec-run")
    p.add_argument("config")
    p.add_argument("outdir")
    p.add_argument("--pdec", default=str(PDEC))
    p.add_argument("--budget-min", type=float, required=True)
    p.add_argument("--min-free-gb", type=float, default=16)
    p = sub("dec-envwatch")
    p.add_argument("job", type=int)
    p.add_argument("config")
    p.add_argument("--pdec", default=str(PDEC))
    p.add_argument("--kill", action="store_true")
    p.add_argument("--max-s", type=float, default=7200)
    p = sub("dec-args", "udir")
    p.add_argument("--pdec", default=str(PDEC))
    p.add_argument("--cfg", default=str(UD31 / "configs/ud31-U.json"))
    p = sub("dec-compare", "udir")
    p.add_argument("--pdec", default=str(PDEC))
    p.add_argument("--ud31", default=str(UD31))
    p.add_argument("--rows", default=str(UD31 / "gap/rows.tsv"))
    p.add_argument("--prows", default=str(NLL_ROWS))
    p.add_argument("--json", required=True)
    p.add_argument("--threads", default="1")
    p = sp.add_parser("dec-decide")
    p.add_argument("dir", nargs="?", default=str(UD31 / "dec"))
    p.add_argument("--ud31", default=str(UD31))
    sp.add_parser("selftest").add_argument("--dir", default=str(WS / "work/r23/scratch-ud31/selftest"))
    a = ap.parse_args()
    return {"configs": cmd_configs, "cfgcheck": cmd_cfgcheck, "predl": cmd_predl, "rehash": cmd_rehash, "prenll": cmd_prenll,
            "heads": cmd_heads, "validate": cmd_validate, "headcheck": cmd_headcheck, "compare": cmd_compare,
            "dirty": cmd_dirty, "decide": cmd_decide, "hcline": cmd_hcline, "hcforms": cmd_hcforms, "rules": cmd_rules,
            "dec-pre": cmd_dec_pre, "dec-run": cmd_dec_run, "dec-envwatch": cmd_dec_envwatch, "dec-args": cmd_dec_args,
            "dec-compare": cmd_dec_compare, "dec-decide": cmd_dec_decide, "selftest": selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
