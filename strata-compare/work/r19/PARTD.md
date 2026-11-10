# Round 19 Part D — v0.1.43 (the user's queue addition, 2026-10-11; runs after B7 and the Round 19 reports; does not
# interrupt the C*17 work). v0.1.43 = 7695859a.

1. Port C*17 (as promoted) onto v0.1.43 with the runbook. exact7 against C*17's hashes with every new default as
   shipped, the gates, ctest. v0.1.43's NaN guard drops upstream's conversation cache after a non-finite window: our chat
   cache must be dropped too (STRATA_NAN_INJECT=1,60; the next turn reuses 0 tokens). STRATA_ROUTE_RESIDENT stays off
   (changes routing). STRATA_ROUTE_TAIL_SKIP=0 stays in every one-GPU config.
2. Adaptive overlap A/B, two-card config: STRATA_ADAPT_LAG=2 (current) vs ADAPT_LAG unset (STRATA_ADAPT_OVERLAP on by
   default). Confirm the start-up line says overlap is on; find out whether it covers the helper card's swaps. B A A B, a
   fresh server per arm, the decode and LDR screens. Keep only if >= 2 % faster, passes the acceptance suite, repeats itself.
3. Q4 one-card config (tail skip 0) on v0.1.43: STRATA_ADAPT_OVERLAP_RESIDENT=1 vs off (ADAPT_LAG unset in both). Same rule.
4. PR #1896 (elightcap, the fix for #1683): stock v0.1.43 + #1896's commit, the Q4 file, the issue's method,
   --resident-budget-gib 72, vs stock v0.1.43 at 72 and vs --resident-experts: lent slots kept in RAM, 32K read time, drive
   reads per 32K prompt, decode, lowest MemAvailable; kernel log after each run. Draft a short test comment for #1896 (CUDA
   listed there as not tested). Privacy check; don't post.
5. Rebase pr18/side (#1889) onto v0.1.43; conflict in src/core/verify.cpp (v0.1.43's HIP-only STRATA_FUSE_CONVAB next to
   our branch code): keep both. exact7 with the switch off and on, ctest. Don't push; report when ready.
6. Update the CMake issue draft to v0.1.43 (still present: use at line 538, option() at 1210). If the sampler bias is
   upstream's, re-check it on stock v0.1.43 before drafting (v0.1.43 doesn't change STRATA_SPEC_PROB).
Promote the v0.1.43 port as C*17.1 if it passes every gate and is within 1 % of C*17 or faster (the NaN guard is worth it
at equal speed), with the 2-hour soak and the rollback test.
At the end, everything that needs the user's OK together: the #1684 thank-you, the CMake issue, the #1896 test comment, the
sampler issue if there is one, the #1889 force-push.
