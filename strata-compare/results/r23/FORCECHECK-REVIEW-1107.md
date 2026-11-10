# Upstream force_check.py / STRATA_FOLLOW vs our decode-path harness - desk review (Karl 11-07; read only)

Upstream v0.2.12: tools/force_check.py (65909b2d0, f46e88d61, f281e3fe2) + serve STRATA_FOLLOW / STRATA_FOLLOW_LOGPOS (d486fbe7d).
Nothing built or run. Scratch: work/r23/scratch-forcecheck/.

**Verdict: a CHECK beside ours, not a replacement.**

Not a replacement:
- It judges the argmax only: mismatch = the scorer's argmax is not the forced token, margin from the top 2 log-probs
  (force_check.py docstring "Rules (paper)"; `STRATA_LOGPOS_TOPK=2` at :174). No KL, no NLL, no distribution - a change that
  moves probability without flipping the argmax passes. We serve sampled (T 1.0); our rules are on KL mean/p90, KL>1 rows,
  changed top-1 and NLL.
- Its rules are not ours: candidate mismatch rate within +0.5 points of stock (one-sided bootstrap) + an exact binomial test
  on large-margin events, >= 2 stock arms (:286-299). Ours: within the references' spread (x1.10), plus bitwise identity
  (exact7, logit files), which it cannot do. The paper's audit of events stock reproduces is not implemented (docstring).
  Using it as a gate would be a rule change (Karl's call).
- Greedy only (a request without sampling keys); our sampled path (STRATA_SPEC_EXACT, sampled draft lengths) is not scored.

Worth having as a check: our decode-path arm (work/r23/decpath_rules.py; results/r23/decpath) reads prompts through fixed
2-row verify windows at fixed settings, and our measurement twin's force=N accepts every forced draft. STRATA_FOLLOW forces
the token inside the real serial decode loop: real MTP draft lengths, partial acceptance and commit, int8 K/V, the adaptive
tier, the PCIe share and the helper cache (v0.2.12 generate.cpp:18046-18073, 19161-19178). None of our gates scores that
path, and our own 1-row vs 2-row check came out "NOT SHOWN SOUND".

| | force_check `--path decode` | ours (decpath / NLL / exact7) |
|---|---|---|
| path | engine `--serve` on stdin (no server.py), the config's flags, real drafted decode windows | 2-row prompt-read windows at fixed settings; batched prompt rows; free generation for exact7 |
| text | stock's greedy continuations (`gen`) | fixed long texts up to 32K; 7 prompts for exact7 |
| measures | argmax mismatch rate, top-2 margin | KL top-64, TV, NLL, top-1; bitwise identity |
| rule | +0.5 pt (one-sided 95 %) + event binomial, >= 2 stock arms | reference spread x1.10; per-text outliers; bitwise |
| catches that the other misses | drafter / commit / adaptive-tier / KV / helper-cache bugs in real decode | distribution shifts, long-prompt drift, any bit change |

What it would take:
- force_check.py itself is stdlib-only; our config JSON already has the keys it reads; configs/x28h.json (P028x without
  `--vision`) works as its CFG. `--path prompt` already runs on P028x (STRATA_LOGPOS is there).
- `--path decode` needs d486fbe7d's generate.cpp hunk (~45 lines; anchors unchanged in r22-port028x generate.cpp:16192,
  17175-17176 and r23-port0211 :18197, 19312-19313); the fault self-test needs cae562fa0's 14-line verify.cpp hunk. The CUDA
  tree had no STRATA_FOLLOW before v0.2.12 (v0.2.8/v0.2.11 had a different, sycl-only one). Put it on the measurement twin,
  not the served binary; a v0.2.12-based port brings it anyway.
- Hardware: the plain CUDA serial loop; fine here (pipeline windows that would skip the hook are off with our helper cache).

Smallest useful use (in a later decode or port gap, on the twin): ~48 fixture prompts x 300 tokens -> `gen` once with
stock -> `score --path decode` twice with stock, once with the candidate, once with `--env STRATA_FORCE_FAULT=7:0.3` (must
REJECT) -> `check`, reported as INFO beside our gates. Better: keep top 64 in our copy (one line, :174) so the
FOLLOW_LOGPOS rows (STRATA_LOGPOS format) feed decpath_rules' KL compare on real decode rows.

Caveats: inside a gap only (it needs 8080 down and has no lock, guard, kernel or swap check of its own); STRATA_FOLLOW hands
out one line per decode request in order, so never behind server.py (any extra request shifts every later line); a wrong
emitted token only warns (:199-201); P028x rewrites its expert profile only with --expert-profile-save (safe); the paper
(SpecPilot, arXiv 2611.02501) is not in the repo and was not checked.

**Karl 11-07: yes, as an INFO line only, never a gate.** Use the v0.2.12 port if it comes first; otherwise do the ~45-line
backport (d486fbe7d's generate.cpp hunk, + cae562fa0 for the fault self-test) onto the measurement twin for the next decode
or port gap. Don't add a gap just for it.
