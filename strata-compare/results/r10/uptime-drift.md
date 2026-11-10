# Decode speed vs server uptime (round 10, Phase 0.4)

## C\*7's monitor (your requests, 329 answers of 768+ tokens, uptime 3.0–10.6 h)

- mean 108.5 tok/s; first half of the uptime range (median uptime 6.2 h) 108.1, second half 108.8 tok/s
- raw trend: **+0.77 ± 0.29 tok/s per hour** (+0.71 % per hour)
- with log(prompt tokens) and log(answer tokens) as covariates: **+0.95 ± 0.30 tok/s per hour** (+0.88 % per hour); prompt +1.75 ± 0.41 per e-fold, answer -3.03 ± 0.56 per e-fold

## Round 9's soak of C\*11 (2 h, server fresh at the start)

- 32K probe (12 runs, same prompt, 512 tokens): 116.7, 105.1, 105.7, 107.6, 104.5, 103.6, 110.0, 106.7, 109.9, 109.9, 105.0, 103.2 tok/s; first 108.8, last four 107.0; trend **-1.84 ± 1.76 tok/s per hour**
- other completed answers of 256+ tokens (169; chats, follow-ups, web): trend with log(answer tokens) as covariate **+2.60 ± 1.93 tok/s per hour** (mean 100.2)
- C\*7 by 2-hour bin of uptime (answers ≥ 768 tokens): 3–5 h n 69 **108.5** tok/s (expert-cache hit rate 0.729), 5–7 h
  n 142 **106.0** (0.730), 7–9 h n 67 **111.8** (0.753), 9–11 h n 50 **111.2** (0.744); hit rate trend +0.005 per hour,
  correlation of hit rate with decode speed 0.19.

## Verdict
**No slowdown with uptime.** Over 3–10.6 h of your real traffic C\*7's decode speed did not fall (if anything +0.9 %
per hour with the request mix controlled, which is the afternoon's topics as much as anything; the 2-hour bins move
±3 % without a direction), and in Round 9's 2-hour soak the same 32K probe has no significant trend (−1.8 ± 1.8 tok/s
per hour; the first probe, on a fresh server with an empty chat cache, was the fastest at 116.7). Engine memory was
flat in both (Round 9's soak: RSS stopped growing once the chat cache filled). Nothing here asks for a periodic restart.
Figure: results/r10/uptime-drift.png.
