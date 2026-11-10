Thanks for the docs note in #1687. A follow-up on v0.1.42 with the issue's two-card setup: a fixed `STRATA_PREFILL_CPU_SHARE=0.4` repeated 4 of 4 items over two starts, reached the first token 15 % and 21 % sooner than `0` on 512- and 1,000-token prompts (583 vs 690 ms, 674 vs 856 ms), and passed our checks against llama.cpp (teacher-forced NLL, needles, sampler tests), so we're switching from 0 to 0.4.

Measured and drafted with Claude Code.
