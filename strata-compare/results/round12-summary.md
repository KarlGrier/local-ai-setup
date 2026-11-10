# Round 12 — summary

**Status (10-05 16:58) — Round 12 is done (ended early on your wrap-up note). Nothing kept, nothing promoted: C\*13 is on
127.0.0.1:8080** (engine 0839b20b…, answered; SearXNG 8888 up; a fresh 48-hour passive monitor runs in logs/r12/uptime-c13/).

1. **Where an extra token goes** (one profile of C\*13, research traffic): going from 1 to 4 tokens per window adds 7.3 ms —
   51 % the GPU waiting for the CPU's experts (DRAM-bound: 380 MB per window at ~74 of ~77 GB/s), 29 % GPU expert reads.
   29 % of draft windows carry no draft; the draft round is 1.5 ms of GPU time. [carries over]
2. **Built and dead: next-layer warming** (my A8 idea, engine-level, passed its paper kill 5–7 %): exact, but **−6.5 %
   served** (pinned −7…−26 %) — the warming reads compete for the DRAM the pool needs. [carries over]
3. **Dead on numbers:** draft-round warming (≤ 1.5 %), a better starting cache (≈ 0 %), an L3 hot set (0.9 %), tree drafting
   (−10 %), the drafter adapter (+0.68 points ≈ 0.4 %), mixed precision (the Q4 file's long-text gain is in its experts),
   two requests in one window (pairs finish **20 % later**: slots decode without drafts). 
4. **Open (one A/B away):** a cost-aware draft length — +2.85 % in the policy model, sampler test passed; stopped by the
   wrap-up. [mechanism carries over; its table is fitted to this drafter]
5. **Your padding question:** the 5080's cache already has per-expert slots on this file — **0 bytes of padding**; slots sized
   for the largest expert would waste 1.99 GiB (22.9 %) and hold **1,053 fewer experts** (helper: 796 fewer). [carries over]

Full write-up: REPORT.md "Round 12" (every idea: kept / dead / open, the number, the cheapest reversal, carries over or this
file); notes NOTES.md "ROUND 12"; data results/r12/.

| phase | result |
|---|---|
| 0 base + profile | base check 7/7; profile tables results/r12/p0-profile.md |
| A1 drafter | overlap 0.80; corrections +0.01 pts; adapter +0.68 pts (dead); ceilings: true-acceptance gate +7.25 %, +10 pts +5.2 %, perfect +47 %; cost-aware gate +2.85 % (open); Signal has no drafter |
| A2 | dead (oracle ≤ 1.5 % < 3 %) |
| A3 | dead (ceiling ≈ 0 %) |
| A4 | measured: both slots active −17.7 % total tok/s, pair completion +20 % |
| A5 | prompt reading = 6.3 % of your time (ceiling) |
| A6 | tree drafting / expert splitting / experts-vs-KV dead; cost-aware drafts → the gate |
| A7 | dead (splice recovers 15 % of Q4's gain) |
| A8 | warming dead (−6.5 % served), faster draft sampler dead (0.8 %), L3 hot set dead (0.9 %); long-prompt drift: the drafter's prompt state depends on timing, < 0.1 % effect |
| B | only A8-1 (engine-level) built → dead; no Phase C |
