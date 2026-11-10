**Display: the monitor is on the motherboard output (the AMD iGPU) for the whole round, as in Round 15** (your message;
sysfs lists no connected output on any card, Xorg holds 4 MiB on each NVIDIA card). Nothing about the display was changed.

### Before the first test

* **48-hour monitor of C\*15 stopped** (logs/r15/uptime-c15/): 11:24 → 14:04, 11 samples, health ok 11/11, idle 11/11, **no
  requests of yours**, engine RSS 51,812 MiB flat, MemAvailable 36.7–36.8 GiB.
* **Base = v0.1.41** (fb58e0db, tree b5a210b6; 151 commits after v0.1.40.2, v0.1.40.3 and v0.1.40.4 included). `git ls-remote`
  at the start: v0.1.41 is the newest tag (no v0.1.41.x) and main's head; the local mirror already had it, so nothing was
  fetched.
* **Round 15's release slip, fixed:** the waiter looked only at the first NEW-RELEASE flag (already marked seen), so later
  flags never woke it. It now checks every flag (tested with a fake one). The release watcher ran all round
  (logs/r16/tagwatch.log).

### The port (the runbook) — 27 → 27 commits

| | outcome on v0.1.41 |
|---|---|
| the ledger pass | **all 27 rows apply by cherry-pick; one conflict**: row 18 (#567's prompt encoder) adds `tools/test_strata_tokenizer.py`, and v0.1.41 added its own file of that name (tests of its new tokenizer piece cache) → one file with both test sets. `strata_tokenizer.py` merged by itself (upstream's piece cache in `_encode_plain`, our resume marks in `_encode_matching`). Upstream merged none of our transplants (#652, #567, #619 still open): nothing dropped, nothing added |
| where both sides changed the same files | read by hand: upstream's HC-norm scratch change sits in its own split norm (our B.1 read replaces that read when on); the three q8_1 sites #606 / #1448 clamped are not in our series (B.1 writes no QFUSE image; A.2 writes Q8_K as ggml does) |
| the release alone, upstream's defaults | exact7 3/7 = v0.1.40.2's stock, not repeatable (the CPU share, step 1) |
| **the release alone, `STRATA_PREFILL_CPU_SHARE=0`** | **exact7 7/7 = v0.1.40.2's stock; repeats itself 7/7** |
| patched, every switch off (share off) | **= the release 7/7**; `strata patch guards: 5 checked, 0 off` |
| every switch's gate (share off) | **ALL PASS with Round 14/15's values to the digit**: B.2 TF −0.0008 / −0.0006, exact sampling chi-square ALL PASS, side mixer pair identical (= C\*15's hashes), A.2 pair identical, B.1 TF +0.0008 / −0.0026 (bound 0.005), cost gate chi-square ALL PASS |
| server tests | 598 (593 upstream + 5 ours), **1 failure in upstream's own test** `test_vision_device` (in the stock tree too): v0.1.41 orders a `"gpu"` list's cards faster-last for an auto layer split, and on this PC the 5080 is faster, so the test's expected "0,1" comes out "1,0". It does not touch your config (it sets CUDA_VISIBLE_DEVICES itself and uses a helper cache, not a layer split) |
| time | 14:07 → 14:55 (48 min): the ledger pass ~10 min by hand beside the queue; the release alone twice, the clean clone and its gates unattended |
