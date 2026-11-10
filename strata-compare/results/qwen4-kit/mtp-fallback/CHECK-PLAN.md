# GPU check plan: the converted drafter against ours (planned 11-04, NOT RUN)

This check tests the drafter that `work/qwen4-kit/mtp_from_gguf.py` makes from Unsloth's
`MTP/mtp-Qwen3.8-Flash-Next-shared-BF16.gguf`. The question is whether its draft acceptance matches our drafter's
(`strata-v0115/mtp/rt`) on the served engine, with the output still exact.

Nothing here runs without Karl's go. 8080 goes down only in a gap Karl opens.

## Arms

The two arms differ only in `--mtp`. Both configs are new files in this folder, not installed:

| arm | config | `--mtp` | log |
|---|---|---|---|
| A (ours) | `P028x-mtp-ours.json` | `strata-v0115/mtp/rt` | `logs/engine-mtpours.log` |
| B (converted) | `P028x-mtp-ud.json` | `work/qwen4-kit/mtp-fallback/rt-ud-shared-bf16` | `logs/engine-mtpud.log` |

Both are `configs/P028x.json` otherwise: the same engine (`engine-r22p028x`), server, environment switches, sampling
and helper slots (3300). Two fields change in both, for safety:
- each arm writes its own log, so the served instance's log is never touched;
- the fallback is dropped, so a failed helper check stops the run instead of starting another model.

## Placement and the counters

**Placement:**
- The CLI runs pin the 5080 to `--expert-cache 2500`, as exact7.sh does. The helper keeps the config's 3,300 slots.
- Both drafters are 837 MiB of VRAM, so the free VRAM is the same.
- exact7.sh prints both arms' slot counts and the line `exact7-slots ... MATCHED`.
- `mtp_accept.py` also compares the "expert cache N slots" and "CUDA1: N additional experts" lines and the "draft
  layer loaded, N MiB" line.

**Counters** (the engine's own lines, parsed by `work/qwen4-kit/mtp-fallback/mtp_accept.py`):
- From the CLI (`strata generate --stats`, `bringup/out/logs/prof/<label>.out`):
  - `speculation N rounds of 12, drafts accepted A of D (rate), T tokens per round`;
  - `accepted per round` (the histogram);
  - `suffix drafts W windows, drafts accepted a of d`, which is taken out, so the rate is the MTP drafter's own;
  - the decode tok/s;
  - the output hash (`p0_table.parse`, the same one exact7.sh uses).
- From the server (the engine log): each request's `drafts accepted A of D, ..., W windows` and its
  `suffix drafts: ... a of d` line.

## Step 0, no GPU (before the gap, about 2 min)

Run NOTES.md "When the file is here": `inspect`, then `verify --report verify-shared-BF16.json`, then
`convert --out work/qwen4-kit/mtp-fallback/rt-ud-shared-bf16`, then `cmp` of the four files against ours.

- If the rt is byte-identical, take outcome I. This is the expected case: offline, the pinned checkpoint goes through
  the converter to exactly our bytes.
- If anything differs, take outcome II. `verify` names each differing tensor and how it differs.

## Outcome I: byte-identical rt (about 10 min with 8080 down)

The engine reads only these four files, so identical bytes mean identical behaviour. This run only confirms that the
converted directory loads and gives the same runs, sampled ones included.

```
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; P=$WS/.venv/bin/python; D=$WS/results/qwen4-kit/mtp-fallback
work/r22/port_gap4.sh begin "mtp fallback check (outcome I)"        # Karl's go: 8080 down
bringup/lib/kcheck.sh mtpchk-pre
PIN_CACHE=2500 flock -s tmp/gpu-test.lock bringup/lib/exact7.sh mtpA $D/P028x-mtp-ours.json; bringup/lib/kcheck.sh mtpA
PIN_CACHE=2500 REF=mtpA flock -s tmp/gpu-test.lock bringup/lib/exact7.sh mtpB $D/P028x-mtp-ud.json; bringup/lib/kcheck.sh mtpB
$P -I -B work/qwen4-kit/mtp-fallback/mtp_accept.py cli mtpA mtpB --identical > $D/check-I.txt
work/r22/port_gap4.sh end
```

**Pass:**
- `exact7 mtpB: 7/7 identical to mtpA` (the 2 sampled runs at seed 11 included) and `exact7-slots ... MATCHED`;
- `mtp_accept --identical`: every count equal, VERDICT PASS.

**Time:** 2 x exact7 at about 3.3 min each (gap 17's runs took 26 s for math/code, 16 s for p2000, 22 s for 32k and 41
s for 112k). With the gap's begin, end and kcheck this is about **10 min**.

## Outcome II: the rt differs (about 45 min with 8080 down)

### G1. Exactness: greedy output must not change (the target verifies every draft)

- Run the same two exact7 lines as in outcome I.
- **Pass:**
  - the 5 greedy hashes (x-math, x-code, x-p2000, x-32k, x-112k) are identical to mtpA;
  - the slots are MATCHED.
  - The 2 sampled hashes may differ: exact speculative sampling draws from the drafter's own q, so another q gives other,
    equally distributed samples. Record them; they are not a failure.
- A greedy difference means a bug in the converted files or in the engine, not the drafter's quality. Stop there.
- About 7 min.

### G2. Acceptance on the CLI: greedy plus our sampling (the CLI has T / top-p / top-k, no min-p)

- **Settings:** the served draft policy (the cost gate and STRATA_DRAFT_CUM, as in P028x), suffix drafts off, the slots
  pinned. The arms alternate per prompt.
- **Greedy:** math, code and puzzle with 1024 new tokens; 1k, rep4k and ldrsyn20k with 512.
- **Sampled:** math and code, seeds 1-4, `--temperature 1.0 --top-p 0.95 --top-k 20`.

```
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 2500"
for t in math:1024 code:1024 puzzle:1024 1k:512 rep4k:512 ldrsyn20k:512; do p=${t%%:*}; n=${t##*:}
  for arm in A:ours B:ud; do a=${arm%%:*}; c=$D/P028x-mtp-${arm##*:}.json
    flock -s tmp/gpu-test.lock bringup/lib/run.sh mtpg$a-x-$p $c $p $n $X > /dev/null; bringup/lib/kcheck.sh mtpg$a-$p; done; done
for s in 1 2 3 4; do for p in math code; do for arm in A:ours B:ud; do a=${arm%%:*}; c=$D/P028x-mtp-${arm##*:}.json
  PROF_SAMPLING="--seed $s --temperature 1.0 --top-p 0.95 --top-k 20" flock -s tmp/gpu-test.lock \
    bringup/lib/run.sh mtpg$a-s$s-$p $c $p 1024 $X > /dev/null; bringup/lib/kcheck.sh mtpg$a-s$s-$p; done; done; done
$P -I -B work/qwen4-kit/mtp-fallback/mtp_accept.py cli mtpgA mtpgB \
   --runs x-math,x-code,x-puzzle,x-1k,x-rep4k,x-ldrsyn20k,s1-math,s1-code,s2-math,s2-code,s3-math,s3-code,s4-math,s4-code > $D/check-II-cli.txt
```

- These are 28 runs of about 25 s each, so about **12 min**.
- The greedy outputs must again be identical: same text, so the same contexts are drafted, which makes the comparison
  paired.
- **Pass, pooled separately over the greedy runs and over the sampled runs:**
  - the MTP acceptance of B is within **1.5 points** of A's, with a two-proportion **|z| < 2**;
  - tokens per round are within **3 %**.
  - About 8-10K drafts per arm give a standard error of about 0.5 points.

### G3. Acceptance on the server with the served sampling (T 1.0 / 0.95 / 20 / min-p 0.05)

The decode screen runs four times, alternating A, B, A, B. Each run is a fresh guarded server, a cold page cache and a
warm-up, then: long reasoning on math and code (4,096-token cap), correctness x5, and one 32K prompt with 768 decoded
tokens. Each arm's settings come from its config's shared settings.

```
for k in 1 2; do for arm in A:ours B:ud; do a=${arm%%:*}; c=$D/P028x-mtp-${arm##*:}.json
  L=$($P -c "import json; print(json.load(open('$c'))['log'])")
  off=$(stat -c %s $L 2>/dev/null || echo 0); echo "$a$k $L:$off" >> $D/g3-offsets.txt
  flock -s tmp/gpu-test.lock bringup/lib/decscreen.sh mtpd$a$k $c; bringup/lib/kcheck.sh mtpd$a$k; done; done
$P -I -B work/qwen4-kit/mtp-fallback/mtp_accept.py log logs/engine-mtpours.log:<offA1> logs/engine-mtpud.log:<offB1> > $D/check-II-served.txt
# (and again for pass 2, from g3-offsets.txt)
```

- About 4 x 5 min = **20 min** (an estimate: a server start, about 2 min of decode and the 32K prompt).
- **Pass:**
  - the pooled MTP acceptance is within **1.5 points**, with **|z| < 2**;
  - both arms' start lines show the same slot counts and T 1.0 / 0.95 / 20 / min-p 0.05 (memory: check each arm's start
    lines);
  - the engine's decode tok/s is within the screen's noise (about +-2 %). The tok/s is for information only.
- The output is not compared here: the runs are sampled, and the target's exact speculative sampling keeps the
  distribution.

### Budget and order for outcome II

| part | min |
|---|---|
| gap begin / end + kchecks | ~5 |
| G1 | ~7 |
| G2 | ~12 |
| G3 | ~20 |
| **total** | **~45** |

G1 comes first and decides whether to continue. G3 can be skipped if G2 already fails.

## What a result means

| result | meaning | next |
|---|---|---|
| outcome I PASS | Unsloth's MTP file is our drafter, bit for bit: the fallback is proven for Flash-Next | for Qwen4: the same converter on the publisher's shared-BF16 MTP file, then this check against `--spec` off and against the checkpoint route if one exists |
| II: G1 PASS, G2/G3 within limits | an equivalent drafter from other bytes (e.g. another rounding) | usable; note the bytes that differ (from `verify`) |
| II: acceptance clearly lower (more than 1.5 points, \|z\| > 2) | other weights or a wrong mapping: look at `verify`'s per-tensor list | an eh half or q/k order set by default (no manifest) is the first suspect: rerun `convert --eh-order he` and G2 only (about 12 min) |
| II: acceptance near 0 | wrong eh order or hyper-connection mapping (the draft head reads garbage) | as above |
| II: G1 FAIL (greedy output changed) | not a drafter-quality question: a bug, since the target verifies | stop; report with both .out files |

## Rules kept

- Each GPU step holds `tmp/gpu-test.lock`, and `kcheck.sh` runs after every run.
- MemAvailable stays at or above 12 GB, and the swap rule applies.
- A page-allocation-failure-only run is dropped and the check goes on.
- No server or guard is started with the lock fd inherited: the series' scripts already close 8/9.
- Nothing is installed in `configs/`, and 8080 is restored by `port_gap4.sh end`.
- A non-timed gap is enough: G3's tok/s is for information only, and the verdicts are on counts and hashes.
