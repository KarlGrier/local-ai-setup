
**Round 21 (last section, 2026-10-16/17): the morning queue. C\*18t (C\*18 + the think-tag fix) is on 8080 with your
sampling on every client; IQ3_S stays the daily model.**
* **C\*18t:** the real bug-fix task went from cut off in all 9 sessions to 4/4 green. Issue #2794 posted.
  Rollback: stop 8080, `STRATA_CONFIG=configs/Cstar18.json ./switch-model.sh strata`.
* **Desktop on the iGPU:** the expert cache gained 0.24 GiB by itself. A lower reserve was not faster at equal sampling,
  so it stays 713. The guard now warns first and stops Strata only after 60 s under the VRAM floor.
* **NVFP4:** FP4-Local converts exactly but is no better than the GPTQ pack. Both decode ~30 % slower than IQ3_S (100 vs
  143 tok/s). UD-Q4_K_XL is the closest to Q8_0 of all packs measured.
* **Reasoning effort:** at medium, C\*18t answered honesty 12/12 and c14 3/3; at xhigh (the default), 4/12 and 2/3, with
  10-50× the reasoning. "High" is xhigh in Strata. The hosted Flash run also ran at xhigh.
* **Q8_0 honesty (overnight):** Q8_TOP_PENDING
