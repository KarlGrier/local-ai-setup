Phase 0 LDR: exposed CPU wait 3.61 ms, CPU pool 5.66 ms per window; lookahead recall in time per layer: L0 0, L1 33, L2 47, L5 46, L10 48, L20 58, L30 59, L40 58, L47 46
A8-1 paper estimate (cached / DRAM = 0.575): saving 1.166 ms per LDR window = 6.5 % of the round (if only half of each warmed expert's bytes are still cached when used: 0.583 ms = 3.3 %); kill under 3 % (0.54 ms)
