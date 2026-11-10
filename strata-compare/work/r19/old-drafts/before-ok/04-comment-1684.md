Thanks for the docs note in #1687. A follow-up on v0.1.42 with the issue's two-card setup: a fixed `STRATA_PREFILL_CPU_SHARE=0.4` repeated 4 of 4 items over two starts, reached the first token 15 % and 21 % sooner than `0` on 512- and 1,000-token prompts (583 vs 690 ms, 674 vs 856 ms), and passed our checks against llama.cpp (teacher-forced NLL, needles, sampler tests), so we're switching from 0 to 0.4.

One catch, for anyone setting the share by hand: with an explicit value it covers chunks below `STRATA_PREFILL_CPU_SHARE_MAX`, which then defaults to 3072 (1024 when the share is left unset). Here it paid up to about 1,500 tokens and cost above that: at 3,000 tokens the first token came 22 % later with the default limit than with 1024 (1.24 vs 0.97 s), at 2,000 tokens 6 % later. So we also set `STRATA_PREFILL_CPU_SHARE_MAX=1792`, which kept the gain at 512 to 1,500 tokens and removed the cost above it.

Measured and drafted with Claude Code.
