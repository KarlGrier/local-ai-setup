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
