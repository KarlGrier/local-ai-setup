The real bug-fix task (`rt_effort`) again, now at your sampling (T 1.0 / 0.95 / 20 / 0.05), two runs per harness, both
at effort xhigh (each client's default until 10-17 13:24). r6 ran on the evening of 10-16. OpenCode's r5 ran after
midnight, and dsh's r5 at 13:09 on 10-17 (the night's shutdown cut its first try).

| harness | run | green | steps | output tokens | wall | model time | largest prompt | tool calls | refused requests |
|---|---|---|---|---|---|---|---|---|---|
| OpenCode | r5 | yes | 114 | 40,491 | 1,419 s | 378 s | 99,179 | 111 | 1 |
| OpenCode | r6 | yes | 59 | 26,342 | 814 s | 229 s | 83,339 | 70 | 0 |
| dsh Minimal | r5 | yes | 49 | 25,286 | 548 s | 225 s | 70,294 | 53 | 0 |
| dsh Minimal | r6 | yes | 89 | 41,861 | 2,329 s | 374 s | 97,776 | 103 | 1 |

* **All 4 green** (hidden tests and the full test suite). No unparsed calls, bad arguments or early ends in any run:
  the think-tag fix holds at T 1.0 too.
* **Model time is the same for both:** 607 s (OpenCode) vs 599 s (dsh) over the two runs, with ~67K output tokens each.
  Most of the wall time is the agent running the project's test suite (3-5 minute gaps between turns), so wall time
  mostly shows how often each run chose to run it.
* **Both harnesses outgrew the context once.** OpenCode r5's 88th request was refused at 100,134 prompt + 30,990
  max_tokens (52 tokens over 131,072); it carried on and finished green. dsh r6's closing request was refused the same
  way (100,119 + 32,768) after the work was done. `"fit_max_tokens": true` would fix both (decision 3 below).
* Recommendation unchanged: OpenCode for daily use, dsh Minimal if you want a web UI.

Table: `work/usability/summarize.py r5 r6`; runs in `results/usability-runs/*-rt_effort-r5`, `-r6`.
