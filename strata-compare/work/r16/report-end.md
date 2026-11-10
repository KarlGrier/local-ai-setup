
### What I got wrong

1. **`pkill -f` matched my own shell again** (Rounds 14 and 15's slip): it ended the command along with the slow prompt
   builder it was meant to stop. Nothing else was affected; I kill by PID since.
2. **The prompt builder looped**: my token-count adjustment oscillated by one token forever. Bounded (±2 tokens accepted).
3. **Step 1's first two starts did nothing**: build-cstar16.sh was not executable, and the A/B script called
   `scripts/mkcfg.py` (another tool) instead of `bringup/lib/mkcfg.py`. Both failed before any server started. Fixed and
   dry-tested.
4. **My first long-text NLL check forced text that no longer continued its cut prompt** (NLL 2.4–6 nats). Kept as an
   on/off comparison and redone in context; the control (B.1 / B.2) then showed long texts move this much under any
   rounding change.
5. **Two waits returned early**: a waiter started while the queue's last line was a hold, and an until-loop matching
   "MARK r16-s3" inside "MARK r16-s3gates". Both harmless; noted in DAY-ONE.md.
6. **The Q4 check started with buffered reads** before I read the engine's warning that prompt reads take lent-slot experts
   from the SSD; restarted with `STRATA_UNBUFFERED_LOAD=1` after one minute (inside the hour).
7. A few notebook times were estimates and were corrected (15:56 → 15:51).

### Time

14:05 → 23:10 ≈ **9 h**. The port and the release alone 50 min (ledger pass ~10 min by hand). Step 1 2 h 10 min (the A/B 6
min; two long-text checks and a control 45 min; the acceptance suite with the share 58 min). Step 2 1 h 53 min (six arms).
Step 3 3 h 28 min (gates 23 min, the acceptance suite 58 min, the soak 2 h, promotion 2 min). Q4 check 20 min (one minute
lost to the restart). Report 25 min.
