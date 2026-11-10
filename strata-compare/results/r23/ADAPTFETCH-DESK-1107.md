# STRATA_ADAPT_FETCH on P028x - desk check (Karl 11-07; read only, nothing built or run)

Upstream v0.2.12 commit 24c6c2f68 "Admit the PCIe share's fetched misses to the GPU cache (opt-in STRATA_ADAPT_FETCH=1|2)".
Not in v0.2.8 or v0.2.11, so not in P028x or r23-port0211. Scratch: work/r23/scratch-adaptfetch/.

**Result: no-go as worded. P028x has a nonzero PCIe share, but ADAPT_FETCH refuses to run beside the helper cache, and
P028x always runs with one.**

1. PCIe share: nonzero. Probe 0.55 at start (logs/engine-P028x.log:10), settles at 0.40-0.45 (e.g. :80 "pcie_frac 0.45
   (was 0.55"); in the 11-07 gate the P028x arms B1-B3 logged 0.40. Larger than upstream's 0.25. With the helper the share
   takes roughly 6 % of routed entries (an estimate from log counts; ~8.5 % on the 5080 alone,
   basalt-020/SINGLE-CARD-STUDY.md:272). (The gate's INFO line cuts the text before the number: gap-port0211.sh:180 cut -c1-160.)
2. Helper cache: P028x uses it (`--expert-cache-device1 3300`; log "CUDA1: 3300 additional experts, 6.21 GiB").
   ADAPT_FETCH is refused, with a start line: v0.2.12 generate.cpp:12784 (serve) / :20461 (CLI) "STRATA_ADAPT_FETCH is off
   (helper GPUs)"; `fetch_can` needs `peer == nullptr && remote_count == 0` (expert_source.cpp:4734-4736). P028x meets every
   other condition (MTP and the chat cache are not conditions). exact7 cannot exercise it either: it runs --adapt-swaps 0.
3. What it does: the PCIe share takes each layer's most-routed misses; a fetched expert routed clearly more than the
   least-routed resident one is copied into that slot; =2 also stops the adaptive tier's own swaps in those layers.
   Unset: bit-identical by reading. Set: not bit-identical (it changes which experts sit in VRAM from the first window); no
   VRAM allocated, slot count unchanged. Upstream's +5 / +10 % is from the commit message and DETAILS.md only (RTX PRO 5000,
   3,896 slots = 16 % of experts); its quality check was token forcing (+0.19 pt mismatch, 90 % CI -0.02..+0.42).
4. Backport: 24c6c2f68 alone merges cleanly onto r22-port028x and r23-port0211 (merge-tree, no ref; 9 files, +256/-35);
   40849df0a not needed.

Odds of a solo screen: the helper is worth +15.1 % decode (154.8 vs 134.5 tok/s, basalt-020/FOLLOWUP-PLAN.md:93); the 5080
alone holds 18.7 % of experts (upstream 16 %), so upstream's +5-10 % solo would give ~141-148 tok/s - still below P028x.

Karl's decision (options): (a) drop it; (b) a 5080-alone screen for information (backport unset must be exact7 7/7 vs
P028x; start lines; STRATA_ADAPT_FETCH_VERIFY=1 "0 differ"; the 9-workload screen; quality by token forcing, since our
KL/NLL checks read only the prompt path); (c) our own patch to allow it beside the helper (drop the helper guard, leave
helper-held experts out of the pick list) - untested upstream. Any of (b)/(c) also needs his quality rule for a decode-only
switch that changes which experts sit in VRAM: token forcing, or "cache-size rounding is OK" (speed + usual checks + VRAM
margin, not bitwise).

**Karl 11-07: (a), drop it for now.** "Make ADAPT_FETCH work beside the helper cache" is parked in results/BACKLOG-1027.md
(section E, item 7) as a Qwen4-day idea: revisit once Qwen4's cache hit rate is measured (more misses, more to gain). If it
is ever tested: judge it with our placement-variant KL band; no new rule.
