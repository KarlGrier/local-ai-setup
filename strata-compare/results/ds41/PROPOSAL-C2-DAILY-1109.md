# Proposal: DeepSeek C2 as the daily config (2026-11-09, after gaps D1 and D2)

Nothing has switched. `configs/DS41-daily.json` is unchanged (both gaps checked its sha256). This needs Karl's OK.

## What C2 is

- The DeepSeek trunk sits on the 5080 with the CPU lane, in the placement that B and C share (`DS4_SPLIT 0,40` instead of
  A's `8,32`).
- Lucebox's DSpark drafter (Q2K/Q4K, from the original V4.1 checkpoint's mtp block) runs fully in VRAM on the 4060 Ti,
  with 2-token drafts.
- Engine and trunk are the same as today's daily: the same engine binary, and the 1017 GSQ-RCO trunk. Its pack
  (`pack-ist-das-2.00bpw-lucebox-q2k`, 11-04) is today's pack index with the drafter entries pointing at the converted
  Lucebox drafter, which D1 checked at its start.

## Results against today's daily A

| | A (daily now, 11-07) | C2 (D1, 11-09) | change |
|---|---|---|---|
| decode tok/s (3 passes) | 28.05 | 30.83 | **+9.9 %** |
| 4K prompt read tok/s | 345.8 | 458.8 | **+33 %** |
| 20K prompt read tok/s | 692.4 | 814.0 | **+18 %** |
| SSD read GB per token | 0.0777 | 0.0964 | +24 % (reads only, no wear) |
| lowest MemAvailable (W1-W3 + P4K) | 17.1 GB | 17.7 GB | - |

C2 on 11-07 measured 30.75, so it holds across days. Drafter acceptance: position 1 82 %, position 2 87 %, 2.34 tokens
per verify round.

## Karl's daily conditions (11-03 / 11-07): all three pass

1. **Sampled-distribution test: PASS.** D2(X, R1) is 2.440, under the noise bound of 11.345 (results/ds41/gate-1109-1050-csampled/d2.md).
2. **Trunk KL check against A: PASS.** 35 changed top-1 picks against a band of 40; NLL distance 0.00073 against a band of 0.00701.
3. **Long-prompt memory arm CL: PASS.** L64 and L97 were both answered, with no stops. The lowest MemAvailable was
   19.4 GB with everything up, above the 14 GB line.

Also seen, information only:
- Thinking on, 11.285, was inside the bound.
- The 1017 drafter probe is **CLOSED** at -1.28 points at position 1, so there is no Q2_K requant build.
- In D1, C3 had swap trouble: the engine's VmSwap reached 102 MB. C2 and C4 were clean, and C4's +2.66 % was not
  beyond the noise.

## Costs

- **The 4060 Ti is in use during a DeepSeek session:** 6.7 GB of VRAM for the drafter. Qwen is not running then anyway,
  and the monitor is on the iGPU.
- **The SSD reads more:** about 24 % more read volume per token.

## On Karl's OK (outside a gap)

1. Back up `configs/DS41-daily.json` to `DS41-daily.json.before-c2`.
2. Make a new DS41-daily.json: today's daily with C2's engine changes only:
   - the lucebox-q2k pack and its tokenizer path;
   - `--dspark on`, `--dspark-block 2`, `--vram-experts 1.0`;
   - `DS4_SPLIT 0,40`.
3. Keep the daily's own settings: 128K context, effort 50, slot keep cap 16, the 68 GB store, the slot RAM cap, its own
   slot folder and profile, the model guard key, and its log.
4. Update "Switch to DeepSeek" (`configs/usability/bin/deepseek-session.sh`). Its start checks should look for:
   - the drafter loaded;
   - the drafter experts on the 4060 Ti;
   - the trunk on the 5080.
5. Re-run `test_deepseek_session.sh` with the real files and permissions.
6. Rollback: copy the `.before-c2` backup back.
