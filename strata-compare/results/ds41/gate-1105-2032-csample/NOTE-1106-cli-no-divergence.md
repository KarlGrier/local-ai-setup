# 11-06 note: on 11-05 the command-line path did not diverge within 512 tokens

Written 11-06 by Claude, from this folder's files only. Nothing was run again.

## What happened (11-05, gap 23:24:19-23:26:19, 2 min with 8080 down)

`gate.sh csample` ran its TIE step, `work/ds41/gate/tie_check.py`.
- 23:24:23: the rule was written to `tie/rule.txt` before any engine run. p90 0.5883 nats decides; the max, 4.3312, is reported beside it.
- G-P4K0 rendered to the 4,115 ids the served engine had logged (`tie/prompt.ids`).
- **C0f on the command line** (`cliarm.sh`, cfg-C0f, `--ids ... --n 512`; `tie/decode-C0f/`; rc 0, 49 s):
  - its text reproduced 11-04's served C0f text;
  - the reproduction check passed (the run went past it).
- **C1f on the command line** (cfg-C1f, DSpark with 1 draft a round; `tie/decode-C1f/`; rc 0, 44 s):
  - **all 512 generated ids are identical to C0f's**;
  - `engine.stdout` is byte-identical between the two (checked 11-06 with `cmp`; 512 ids each).
  - C1f did not leave C0f anywhere in the 512 tokens. On 11-04 it left at char 126 ("... Version 2.0 text" vs "... Version 2.0 terms").
- So tie_check.py found no first divergent token. It printed "C1f's command-line path does not leave C0f's within 512 tokens (the served one did at char 126) - reported, no verdict" and exited 2.
- C0 / C1 / C2 were skipped, as the rule says. DS41-daily.json was unchanged. P028x came back on 8080 and the kernel check was clean.

## How the command line differed from the served path where the divergence was seen

- **Same:**
  - the configs (11-04's cfg-C0f / cfg-C1f);
  - the profile snapshot (b54bd76a);
  - the placement: CUDA0 [40, 42] 384 of 384, CUDA1 [0, 39] + head 733 of 15360, 14627 on the CPU lane;
  - the prompt: 4,115 tokens, the same prompt-skip line;
  - greedy decoding, 512 tokens.
- **Served (11-04, CG step):** one server per arm (tunearm.sh + greedy_client.py). G-P4K0 was the third request on that server, after G-W1 and G-W2.
- **Command line (11-05):** G-P4K0 alone on a fresh engine, with no earlier requests.
- **The drafter's own counts on G-P4K0 differ:**
  - served C1f: 205 drafts offered, 192 kept;
  - command-line C1f: 327 rounds, 200 offered, 184 kept.
  - So C1f's verify windows fell at different positions on the two paths.

## What follows (Karl 11-06)

> "C rerun: (a). Run the near-tie check through the served path, where the divergence appeared. Record that the
> command-line path didn't diverge within 512 tokens. Add it to the series as a step after the Basalt rerun, between
> questions. If it needs more than about 90 min with 8080 down, tell me first."

- This note is the record.
- The rerun is `work/ds41/gate/gap-ctie-served.sh` with `work/ds41/gate/tie_served.py`. See `work/ds41/gate/CTIE-SERVED-1106.md`.
- It applies tie_check.py's rule unchanged. tie_served.py checks that the recomputed rule equals this folder's `tie/rule.txt` byte for byte.
- It finds the first divergence in served C0f / C1f runs, made exactly as 11-04's.
