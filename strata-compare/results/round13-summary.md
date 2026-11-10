# Round 13 — summary

**Status (10-06 06:50) — done. C\*13.1 (v0.1.39 + 53 patches) is on 127.0.0.1:8080**, promoted 10-05 22:45 after all
gates, a 2-hour soak (423 requests, 0 errors) and a real rollback test. It computes what C\*13 computed (exact7 7/7;
screens +0.3 %). Rollback: stop 8080, `STRATA_CONFIG=configs/Cstar13.json ./switch-model.sh strata`. Upstream released
v0.1.40 and v0.1.40.1 overnight — logged, not adopted; their security fix cannot be reached on this server. **Nothing was posted: the
publish list is in `publish/README.md`, for you to decide.**

**Fixed**
1. **#838 + a third site in our tree** (PR245's decode kernel): up to 700 / 700 scale blocks stored as inf at large
   activations → 0, bit-identical otherwise. Found on the way: **PR245's grid-stride bug** (1,229 upstream parity failures
   → 0; latent here).
2. **#931 control-token text** (reproduced: a forged turn inside a document was followed 30/30) → 0/30, copying
   such text 3/20 → 20/20; 0 id changes on 851,570 ordinary tokens. llama.cpp has the same bug.
3. Loading safeguards #958, #648, #896, #619 (code) taken; crash recovery has no gap (12 s restart; the chat cache is
   lost) → #788 / #748 not needed; CUDA 13.3 parity clean.

**Ledger:** 53 patches — exact 16, rounding-level 2, distribution-preserving 1, fixes 15, serve / UI 7, measurement 12;
12 upstream PRs carried. **8 startup guards** cover every patch that assumes something about the model (a mismatch → one
log line, that patch off); each guard forced = the switch off, hash for hash. One-command test per patch.

**Inspector / planner vs reality:** IQ3_S and UD-Q4_K_XL RUNS, Signal needs upstream (Q6_K embedding) — all correct.
5080 slots predicted within −2.5 … +2.2 % (5 checks); RAM within 0.3 GiB. Wrong once: the planner put a RAM budget
beside the helper cache, which the engine refuses → fixed (one GPU + budget for files too big for RAM).

**Rehearsal A** (same model, clean clone, unattended): **reproduces C\*13.1** — every gate, exact7 7/7, calibration
keeps every value, B.3 table 0 of 80 differ, suite 11/0, screens within noise. **2 h 33 min** (+ 37 min re-run of the
screens after a fix). Manual steps: 3 script fixes, then only reading tables.
**Rehearsal B** (UD-Q4_K_XL, a file whose experts do not fit in RAM): **2 h 18 min** for the run that went through
(3 h 17 min with two stopped starts). **Untuned 26.8 → tuned 47.4 tok/s (+77 %)**: the placement +67 %, patches and
calibration +6 %. What it taught: (1) such a file **cannot use the helper GPU** on v0.1.39 / v0.1.40 — one GPU + RAM
budget beats both GPUs with mmap; (2) **stock v0.1.39 does not repeat itself** when experts are read from the files
(late near-tie flips) → the gates there now use first-difference agreement + teacher-forced NLL (the negative control
fails as it should); every switch gate passes on the Q4; calibration kept every value (re-test resident KV 16K and a
32K chunk on day one). **#773: no effect** — with 96 GB the file cache already keeps the rest of the experts, so its own
rule picks the normal path.

**Acceptance suite vs llama.cpp** (one command, 57 min): **11 pass, 0 fail, 2 reported** on C\*13.1 and on Rehearsal A's
build.

| row | Strata | llama.cpp | result |
|---|---|---|---|
| token ids, 9 conversations | identical 9/9 | template text 9/9 | PASS |
| TF NLL short / long (clipped) | 0.291 / 0.387; 2.046 | 0.288 / 0.387; 2.052 (next run 1.976) | PASS |
| needles 32K–123K | 36/36 | 36/36 | PASS |
| chat-cache round trip | 3/3 identical | – | PASS |
| samplers (chi-square; near-ties vs own probabilities) | ALL PASS; min p 0.039 | – | PASS |
| stops / tool calls / 4,235 boundary splits | ALL / 6/6 / 0 differ | 5 of 9 / 6/6 / – | PASS |
| control-token text (copy / forged) | 20/20 / 0/30 | 0/20 / 30/30 | PASS |

Also: **llama.cpp's long-text NLL moves ~0.11 nats per text between identical runs** (Strata: bit-identical); int8 KV
cleared (inside that spread); MT_MIN=1 repeats 6/6.

## Day one (bringup/DAY-ONE.md)

1. **Headers first** (16 MB per shard): `inspect_model.py` → RUNS / RUNS WITH PATCHES OFF / NEEDS UPSTREAM (names what).
2. `fitplan.py`: slots, RAM. Experts too big for RAM → one GPU + `--resident-budget-gib` (the helper cannot join; such a file does not repeat run to run).
3. New release: fetch; `run.env`; **drop the transplants upstream merged** (v0.1.40 already has #550 #454 #700 #838
   #931 #651 #748 — the series otherwise conflicts in 57 hunks); `runbook.sh RUN clone inspect fitplan pack build`.
4. Model-specific test inputs: needles, sampler near-ties, round-trip tokens, B.3 shapes.
5. `runbook.sh RUN stock patched patches` (half a day, unattended) — read the guard and model-check lines.
6. `runbook.sh RUN calib b3table screens accept` — change a value only for ≥ +2 %; no FAIL row; llama.cpp's long TF
   is one noisy sample.
7. Soak 2 h on 8080, promote with a real rollback test, keep the old config.
Traps: no `--remote-expert-opt`; `--pcie-frac 0`; one model server; MemAvailable ≥ 20 GB; don't edit runbook.sh while
it runs.

Full write-up: REPORT.md "Round 13"; notes NOTES.md "ROUND 13"; data results/r13/, bringup/out/.
