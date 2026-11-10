# B's KL check under Karl's 11-04 noise-band rule

Verdict: **PASS - B counts as passing the KL check** (the long-prompt memory arms and Karl's OK are still needed before any switch)

- A = the first gate's A scoring (reused: same build, config, settings, snapshot)
- rule (rule.txt, written before the run): band_top1 = max(changed top-1 picks Aa vs A, Ab vs A); band_nll = max(|NLL(Aa) - NLL(A)|, |NLL(Ab) - NLL(A)|); PASS iff B's picks <= band_top1 AND B's NLL distance <= band_nll (inside the band; no 1.10 factor); else FAIL (B stays off). Long-prompt memory arms and Karl's OK still needed before any switch.

| pair (vs A) | changed top-1 picks | NLL distance | KL mean | KL p90 | KL>1 | VRAM experts | byte-identical |
|---|---|---|---|---|---|---|---|
| Aa: --vram-experts 0.98 | 40 | 0.00701 | 0.00700 | 0.01309 | 0 | 1308 | False |
| Ab: warmed by a W1 decode | 29 | 0.00469 | 0.00656 | 0.01225 | 1 | 1335 | False |
| B (first gate) | 38 | 0.00698 | 0.00717 | 0.01359 | 1 | - | False |

- band: top-1 40, NLL 0.00701; B 38 / 0.00698: top-1 inside, NLL inside
- A's VRAM experts in the harness: 1335 [462, 873]; Aa's 1308 [452, 856]
- Ab's warm-up changed 8131 of the profile's 15360 counts
- run times: {'Aa': 'rc 0, 324 s, lowest MemAvailable 27.0 GB (8 engine runs, one segment each)', 'Ab': 'rc 0, 320 s, lowest MemAvailable 26.9 GB (8 engine runs, one segment each)'}
