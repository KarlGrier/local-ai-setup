
**The acceptance suite with the share on** (C\*16 + the share, results/r16/accept-c16-share-on.md): **10 pass, 1 FAIL** — the
chat-cache round trip, 1/3 identical. The cause is the share, not the cache: two identical *direct* builds of the test chat
already differ (31 argmax changes, different GDN / KV state hashes), because the chat's 96-token follow-up read (5,822
tokens, 5,726 reused) goes through the share; parked → resumed vs direct differs by the same amount; the edit case (a
3,247-token read, no short chunk) is identical. With the share off the same round trips are identical in all three cases
(step 3). Every other row passed (TF short 0.2904 / 0.3852, long within 2 se, needles 36/36, samplers, stops, tool calls,
splits, control text).

**Decision (your rule: keep it only if it passes the acceptance suite and the long-text NLL check and is ≥ 3 % faster):**
16–17 % faster ✓, long-text NLL ✓, acceptance suite ✗ → **`STRATA_PREFILL_CPU_SHARE=0` in C\*16.** What you give up: ~0.11
s on a 512-token prompt and ~0.14 s on a 1,000-token one, and on each chat turn's new text. What you keep: every output
repeats itself, and a parked chat resumes bit-identically. `STRATA_STAGE_PIN` stays off (unset = off in v0.1.41).
