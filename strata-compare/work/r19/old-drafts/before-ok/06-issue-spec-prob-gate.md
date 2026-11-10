Title: STRATA_SPEC_PROB: --spec-min-p gates on the drawn draft's q, which skews sampled tokens toward the draft head's favourite

### What happened

With `STRATA_SPEC_PROB=1` and `--spec-min-p 0.5`, a near-tie inside a speculative window comes out skewed toward one token. With `--spec-min-p 0`, or with `STRATA_SPEC_PROB_GATE=top`, the same position matches speculation off again, so the gate causes the skew, not the acceptance rule.

Stock v0.1.43 (`7695859a`), the arithmetic case below, temperature 0.6, top_k 20, top_p 0.95, min_p 0.05, no penalties, no seed sent (so the server's clock seed). The counts are of `=` among the samples that took the 3-token path to the position:

| run | `=` | share | vs speculation off |
|---|---|---|---|
| speculation off (`--spec-min-p 2`: no draft passes) | 2,027 of 3,830 | 52.9 % | - |
| `STRATA_SPEC_PROB=1`, `--spec-min-p 0.5` | 1,092 of 1,914 | 57.1 % | +4.1 points, z 3.0, p 0.0031 |
| `STRATA_SPEC_PROB=1`, `--spec-min-p 0` | 1,030 of 1,934 | 53.3 % | +0.3 points, z 0.2, p 0.81 |
| `STRATA_SPEC_PROB=1`, `--spec-min-p 0.5`, `STRATA_SPEC_PROB_GATE=top` | 986 of 1,917 | 51.4 % | -1.5 points, z -1.1, p 0.29 |
| default exact-match drafting, `--spec-min-p 0.5` | 1,008 of 1,920 | 52.5 % | -0.4 points, z -0.3, p 0.76 |
| our local exact-sampling patch, `--spec-min-p 0.5` (not in Strata) | 1,054 of 1,933 | 54.5 % | +1.6 points, z 1.2, p 0.25 |

The last row is our own build (v0.1.43 plus our patches, including an exact-sampling path of ours), shown for comparison only. All three `STRATA_SPEC_PROB` runs drafted in every request (3.9 drafts per request with the gate on the drawn token, 4.2 with the other two).

Strata's own probabilities at the position, forced through the `STRATA_SPEC_PROB` server, are `=` 0.5018, ` ` 0.4902, ` =` 0.0076. After top_k 20, top_p 0.95, min_p 0.05 and temperature 0.6 only `=` and ` ` are left, at 51.0 % / 49.0 %. Against that, the gated run gives χ² 28.3 (p < 1e-6); `GATE=top` gives 0.16 (p 0.69). The speculation-off server forces slightly different values at the same position (`=` 0.5219, ` ` 0.4707, so 54.3 % after the chain), so I compare the runs with each other rather than with one fixed number.

### Why (where the two samplers differ)

In probabilistic mode the drafter writes the drawn token's own probability under q to `*out_prob`:

- `src/kernels/cuda/sampler.cu` line 980, `spec_draft_merge_kernel`: `prob[0] = n_keep > 0 ? (float) ex[gate_pick ? pi : 0] : 1.0f;`. Here `gate_pick = spec_gate_pick()`, which is on by default (`include/strata/core/spec_prob.hpp` line 45, `STRATA_SPEC_PROB_GATE` unset).

The serve loop then adds draft j to the window only while that value passes `--spec-min-p`:

- `src/program/generate.cpp` line 11815 (the serve loop): `while (T < S_mtp && dprob[(size_t) T - 1] >= (float) req_spec_min_p) ++T;`. The CLI loop does the same at line 13012 and also hands q to the verifier.

So whether a row is judged by `min(1, p(d)/q(d))` depends on which token the drafter drew. A draw with `q(d) < --spec-min-p` is dropped, and that row becomes a plain sample of p. Rejection sampling gives p only averaged over every draw from q. With the draws selected by their own q, a row's output is

`P(x) = Σ_d q(d)·[q(d) ≥ θ]·P(x | d judged) + Σ_d q(d)·[q(d) < θ]·p(x)`

For two tokens A and B with `q(A) ≥ p(A)` and `q(A) ≥ θ > q(B)`, this is `P(A) = p(A)·(2 − q(A))`. For example, with p = (0.51, 0.49), a draft head at q(A) = 0.88 would give 57 % instead of 51 %. The skew always goes toward the draft head's favourite token. It disappears when no draw passes the gate, so it varies with temperature: on v0.1.42, at this position (our build, running `STRATA_SPEC_PROB`), we saw +8 to +10 points at temperature 0.6 and no detectable skew at 1.0. A Monte Carlo of the kernel's rule (accept if `u·q(d) < p(d)`, otherwise sample the residual `max(0, p − q)`) gives the same numbers, and p itself for every q with θ = 0.

The comment at `spec_gate_pick` says it gates "as the coupled drafter does". For the coupled drafter and plain exact-match drafting the gate is harmless: the row's output is the target's own draw whether or not a draft was proposed. Rejection sampling is different. Before this I also checked the Philox draws behind the pick, the draft, the accept and the residual (the bit-61/62/63 counters). In a port of `philox_uniform`, 400K random seeds and positions showed no correlation (|r| ≤ 0.003).

Suggested fix: in `STRATA_SPEC_PROB` mode, gate on something that does not depend on the draw, such as q's top probability, which is what `STRATA_SPEC_PROB_GATE=top` does. The gate on each draft then depends only on the context before it, so each row still samples exactly from p. The comment there says top gating decoded slower on an RTX 3060; I have not measured its speed here. Another option is to fix the window length before drawing.

### How to rebuild the case

The chat request, with the server's `reasoning_effort` "high" template as Strata renders it (76 prompt ids):

```
<|im_start|>system
Reasoning effort is set to xhigh. Please think carefully through the task, validate key assumptions, consider plausible alternatives, and prioritize correctness, consistency, and clarity in the final answer.<|im_end|>
<|im_start|>user
What is 17 * 23 + 144 / 12? Show the steps briefly.<|im_end|>
<|im_start|>assistant
<think>
```

That is followed by the first 32 tokens of the greedy answer, `We need answer simple arithmetic. Need final brief steps. Compute 17*23=391. 144/12=1`:

```
1596, 1144, 4087, 4145, 33633, 13, 14235, 1534, 9522, 7123, 13, 21902, 220, 16, 22, 9, 17, 18, 28, 18, 24, 16, 13, 220, 16, 19, 19, 14, 16, 17, 28, 16
```

Each request generates 4 tokens from there (`max_tokens` 4). I count the samples whose first three tokens are `2. Sum` (17, 13, 7860), then whether the fourth is `=` (28) or ` ` (220). The position is the 4th generated token, so it falls inside a speculative window (`--spec 4`), not in a request's first one-token window. Stock's server has no field for appending token ids to a chat prompt, so I appended the 32 ids with a small server hook that is only for measurement and changes nothing else.

Flags (served, two GPUs; the measured build is stock v0.1.43 plus that hook):

```
--native Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf --ple-gguf ...-00002-of-00002.gguf --expert-cache auto
--prefill auto:16384 --spec 4 --spec-min-p 0.5 --mtp <the MTP head> --max-context 131072 --kv int8 --kv-resident 32768
--pcie-frac 0 --ple-inflight 128 --expert-cache-device1 3300 --adapt-swaps 0
STRATA_SPEC_PROB=1
```

### Strata version, GPU, OS

v0.1.43 (`7695859a`) · RTX 5080 16 GB + RTX 4060 Ti 8 GB, driver 615.71.09, CUDA 13.3 · Linux 7.0 (Ubuntu 24.04-based)

### Engine log

```
strata mtp: probabilistic draft acceptance on (STRATA_SPEC_PROB): sampled requests draft by sampling the draft head's distribution over 40525 tokens; the verifier accepts with min(1, p/q) and resamples the residual
strata serve: prompt 108 tokens = 71 reused + 37 read in 245 ms (150.8 tok/s), 4 generated in 77 ms (52.3 tok/s), drafts accepted 3 of 4, 1 checkpoints
strata serve: prompt 108 tokens = 71 reused + 37 read in 245 ms (150.8 tok/s), 4 generated in 93 ms (43.1 tok/s), drafts accepted 1 of 6, 1 checkpoints
```

Measured and drafted with Claude Code.
