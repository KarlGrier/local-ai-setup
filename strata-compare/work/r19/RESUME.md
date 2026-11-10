# Round 19 — state before Part D (2026-10-11 ~18:35)

* **C\*17 is promoted and on 8080** (configs/Cstar17.json; engine-cstar17 sha 4b486ce2…, tree 1c05934d = branch r19-port:
  v0.1.42 + C\*16.1's series, our exact sampling + cost gate, STRATA_PREFILL_CPU_SHARE=0.4 below MAX 1792). One-GPU
  fallback Cstar17-single.json (tail skip 0). Rollback: `STRATA_CONFIG=configs/Cstar161.json ./switch-model.sh strata`.
* The 48-hour monitor runs on C\*17 (logs/r19/uptime-c17/; started 17:45). The kernel-log watcher runs (tmp/r19/kwatch.pid).
* Done: Parts A, B (B1–B7), Round 19's report (REPORT.md "Round 19", results/round19-summary.md), memory updates.
  configs/r16-q4.json = C\*17's K-quant engine (engine-cstar17-kq) with --resident-experts, tail skip 0.
* Waiting for the user's OK, together at the end: publish/r19/04-comment-1684.md, 03-issue-cmake-native-experts.md (to
  update to v0.1.43), and Part D's drafts.
* **Next: Part D** (work/r19/PARTD.md): v0.1.43 (7695859a) → the port (C\*17.1 if every gate passes and within 1 % or
  faster), the overlap A/Bs, the #1896 test + comment, the #1889 rebase, the CMake draft, the sampler issue (stock v0.1.43
  first). Every step ends with the promoted build (C\*17) on 8080; the kernel log is checked after each run.

# Part D progress (2026-10-11 ~19:40) — details in NOTES.md "## Part D"
* DONE: D1 port r19-port43 (29 commits, tree 1c4d1dbf): runbook r19e every gate PASS, all-on exact7 7/7 = C\*17's hashes;
  ctest = stock 110/113 (3 data-file tests); NaN chat-cache test PASS. D4 #1896 measured (results/r19/d4-1896.md), draft
  publish/r19/05-comment-1896.md. D5 #1889 rebased (pr18-v043/side 38b03280), exact7 off/on OK, ctest OK, push command in
  NOTES. D6 CMake draft updated to v0.1.43 (03-issue-...).
* Queue (bringup/lib/queue.txt): d6_sampler43.sh (stock v0.1.43: nospec / sp / sp --spec-min-p 0 / sp GATE=top / em; ours on
  the r19e twin) → d2_overlap.sh → d3_ovres.sh → STOP.
* Sampler hypothesis (NOTES 19:2x): --spec-min-p gates on the DRAWN token's q in SPEC_PROB mode → biased. If d6's spmp0 and
  sptop arms are ≈ 52 % and sp ≈ 60 %: draft the sampler issue (publish/r19/06-issue-spec-prob-gate.md) with the case data
  (arith-j3: rendered prompt + 32-token prefix + "2. Sum", '=' 0.5067 / ' ' 0.4855 raw, ~51.8 % after the chain at T 0.6).
* Then: C\*17.1 = work/r19/c171_pipeline.sh [CAND] (build-cstar171.sh → exact7 ×2 → gates17.sh → acceptance → d7_speed.sh vs
  C\*17) → soak (soak13.sh 120 with STRATA_CONFIG=configs/Cstar171.json) → promote-c171.sh (rollback test to C\*17) → new
  48-h monitor. CAND = configs/r19e-cand-ov.json only if D2's overlap qualifies (≥ 2 %, repeats; its suite = C\*17.1's).
* Then the OK round: 04-comment-1684, 03-issue-cmake, 05-comment-1896, the sampler issue (if any), the #1889 force-push.

# State at the end of Part D (2026-10-12 03:50)
* 8080: **C\*17.1** (configs/Cstar171.json, engine-cstar171 e815b609, tree 1c4d1dbf = branch r19-port43); one-GPU fallback
  Cstar171-single (tail skip 0). Rollback: configs/Cstar17.json. Launchers' old copies: work/r19/*.before-c171-promotion.
* 48-h monitor: logs/r19/uptime-c171/ (pid in its monitor.pid), started 03:49. The C\*17 monitor was stopped at 03:49.
* Posted (user's OK): #1684 comment, #2027, #1896 comment, #2028, #1889 force-push + comment (publish/r19/MANIFEST.md).
* Queue at STOP; nothing pending. Not kept: v0.1.43's adaptive overlap (two cards, Q4).
* Open threads to watch: #2027, #2028 (maintainer replies), #1889 (review), #1896 (elightcap / maintainer).
