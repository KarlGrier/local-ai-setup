# A8 (1): what Fix 1 missed in the 10-24 report, by kind (10-27 ~21:00; read-only analysis, nothing changed)

**Inputs:**
- The reference list is the code-tool grading's stage 3 (codetool/blind/grades-stage3.json, report B = the 10-24
  report): **30 names** the grader judged "presented as this engine's" but not Strata v0.2.4 DeepSeek-engine options.
- These are compared with Fix 1's last replay on the same report (replays/f1-jan1024-r4/versioncheck.json: 74 names
  checked).
- The report was read for Fix 1 only, as Karl allowed.

**Correction to my earlier summary:**
- "Fix 1 caught ~16 of ~30" mixed two counts. It **marked 15** of the grader's 30 names, plus one more, and **classed 24
  correctly** as another engine's or as not in Strata at all.
- Most of the gap is in deciding which correctly classed names to mark, not in finding the names.

| kind | names | n | why missed | fix |
|---|---|---|---|---|
| **Right class, judged "not recommended", so not marked** | `--chunk-mmq`, `STRATA_PLE_AUTO_MMAP`, `--pcie`, `--prefill`, `STRATA_DMA_BATCH`, `--pcie-mode`, `--adapt-swaps`, `--adapt-decay`, `STRATA_IQ_MT_MIN` | **9** | Only names the report *recommends* get a mark. These are described as this engine's ("do not add `--chunk-mmq`", "Strata's adapt loop uses `--adapt-swaps`") but not recommended. | Mark every name presented as this engine's: recommended ones as now; described ones with a lighter note ("not an option of this engine at v0.2.4; another engine's"). |
| **Passed as "this version" through the shared launcher** | `--ple-io`, `--pcie-frac`, `--adapt-every` | **3** | The engine-folder step took in `strata_cli/launch`. The launcher parses options for every engine, so a Qwen flag found there looked like a DeepSeek option. | A name counts as the engine's only if the engine's own folders (`src/dsv41`, `include/strata/dsv41`) read it. Found only in a shared launcher or server folder, it is "parsed, not read by this engine: unverified". |
| **Classed "another project" though recommended for this engine** | `--tier-batch-pcie`, `--kv-fp4` (Xolotl flags) | **2** | "other-project" is not one of the kinds that get marked. | "other-project" plus recommended (or presented) for this engine gets marked as well. |
| **Config keys, never extracted** | `"gpu_order"` (in the grader's list), plus `"gpu": [0]`, `"layer_split"`, `"expert_profile_save"`, `"expert_profile_save_every"` (JSON keys the grader's tool did not extract either) | **1 (+4)** | The name finder looks for `--flags`, `UPPER_SNAKE` variables and `-D` options, not quoted JSON keys. | Extract `"key":` patterns, check them as string literals in the engine's folders, and mark the same way. |
| **Env vars without code formatting** | none | **0** | The finder already scans the whole text, not only code spans; every variable in the grader's list was found. | - |
| **Prose mentions** (a setting described in words, no name) | none in the grader's list | **0** | Cannot be checked by name. | Out of reach for a name check; the setup check and critic remain the net. |

**Plan for the replay (after p4s6 is graded):**
1. Make the four changes above.
2. Replay on the 10-24 report.
   - The target: all 30 grader names marked, plus the 5 config keys if the engine does not read them.
   - Count new false marks: a real DeepSeek option marked, or a warning marked as a recommendation.
3. Replay on both reruns (the code-tool rerun and tonight's rerun).
   - These check false alarms on reports that mostly name the right engine.
   - `--experts` and `STRATA_SPLIT_UNIFORM` must stay marked.
