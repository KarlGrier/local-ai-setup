# Staged on 10-29 - install order (nothing below is installed; each folder's README has the steps and backups)

Install only with no LDR run, Jan research job, bench queue, replay or API-run grading live; LDR package changes need an
LDR restart, runner changes a runner-service restart. Re-diff each staged file against the live one first (several were
copied from the install before later installs).

Already INSTALLED 10-29: deep/codetool.py + deep/report.py version labels on repo pages (07:48, *.before-verpin).

| order | folder | touches | needs first | GPU check after install |
|---|---|---|---|---|
| 1 | c3 | deep/* (modelprofile.py + 10 files), run-ldr.sh, tools/research-runner.py | - | none needed (equivalence 84/84); optional replay |
| 2 | runner-bench | tools/research-runner.py, bench2-queue.sh, run-ldr.sh, tools/ldr_runfiles.py; bench2.py -> use bench2-merged | c3 | none (dry check: no restart) |
| 3 | item7 | tools/paid_*.py, search_route.py, s2_search.py, exa/tavily_fallback.py, LDR search hook | runner-bench (its paid_budget.py) | item 7 sides later |
| 4 | fix1b | deep/checks.py (version check) | - | 5 fix-replay check --fix version + compare_replays.py |
| 5 | k4 | deep/checks.py (= fix1b + consistency) - install k4's checks.py instead of fix1b's if both go together | fix1b | 2 fix-replay check --fix baseline,consist + judge_k4.py |
| 6 | bench2-merged | tools/bench2.py (phase5 + runner-bench edits, merged clean) | with 2 or at Phase 5's start | - |
| 7 | item8 | new tool only (tools/merge-evidence.py) | - | 3 fix-replay write on merged/oNN-3 (~1 h each) |
| 8 | phase5 | p5-start.sh installs its own part at the start | the final build; p5.json placeholders filled | Phase 5 itself (~33 GPU h) |
| - | c4 | separate install for the Sonnet experiment (guard + run-ldr.sh guard mode) | c3; Karl's answers on caps | pilots ($3) |
| - | c3/profiles/qwen4-flash.env | draft profile (refused unless LDR_ALLOW_DRAFT_PROFILE=1) | c3; Qwen4 release | results/bench2/QWEN4-DAY1-PLAN.md |

Note: run-ldr.sh is staged in c3, runner-bench and c4 - install the newest in the chain (c3 -> runner-bench), and c4's
guard mode on top of that when the Sonnet experiment starts (re-diff).
