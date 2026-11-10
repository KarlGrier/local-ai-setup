**Round 8 (last section, 2026-09-30/10-01):** two promotions, both measured against the build they replaced.
* **C\*8 = Strata v0.1.30 + our 12 patches (promoted 20:21).** **+13 % decode**, mostly v0.1.29's split sampler.
  Output and teacher-forced NLL are bit-identical to C\*7. Soak: 351 requests, 0 errors.
* **C\*9 = C\*8 + upstream PR245's GPU expert kernels + a prompt-path change of mine (promoted after its soak).**
  * Speed: **+4.4 to +4.8 % decode, −3 % time to first token on 32K–120K pastes, −4.5 % total request time** on a
    fresh holdout.
  * Correctness: output bit-identical to C\*8 in every fixed-computation test; needles 72/72; Stop, round trip and
    browser checks pass.
* **Feasibility (Phase A) ruled out the big ideas with numbers:** exact speculative sampling (+3.5 % modeled), GDN
  chunked prefill (FlashQLA is BF16-only and not faster), coupled drafting (−1.9 %), thread affinity (no effect),
  and every draft-length setting.
* **Open for you:** 16 chat slots would make returns to up to 16 chats instant, but costs up to ~4 GB more RAM with big
  pastes. There's also a rare, rounding-level difference from the adaptive tier's timing (explained in the section).
* Rollback: `STRATA_PORT=8080 ./run-strata.sh stop && STRATA_CONFIG=configs/Cstar8.json ./switch-model.sh strata`.
