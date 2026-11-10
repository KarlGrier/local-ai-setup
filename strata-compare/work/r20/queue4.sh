#!/bin/bash
# queue4.sh - 2026-10-14 12:47 (after the kernel stop; the user: continue): D, then the presence-penalty continuation
# + the 2 missing Q8_0 probes (c_pp05.sh).  The dense llama.cpp scan is dropped (no more mmap runs larger than RAM).
cd /home/USER/ai-speed-testing/strata-compare
work/r20/d_conc.sh > logs/r20/d_conc.console 2>&1
work/r20/c_pp05.sh > logs/r20/c_pp05.console 2>&1
