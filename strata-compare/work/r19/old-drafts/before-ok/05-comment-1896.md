Tested on CUDA, which the PR lists as not tested: RTX 5080 16 GB, CUDA 13.3, driver 615.71.09, Linux, with the file, flags and method from #1683 (served, a fresh server per arm, the model's page cache dropped first, the same two 32,768-token prompts, `STRATA_ROUTE_TAIL_SKIP=0`). I cherry-picked this PR's commit (`29063eb2`) onto v0.1.43 (`7695859a`), where it applied without conflicts, and built both with `-DSTRATA_MMQ_KQUANTS=ON`. One server per arm, two prompts each:

| arm | RAM copy | lent slots' experts in RAM | 32K prompt read (s) | prompt tok/s | read from the drive per 32K prompt | decode tok/s | MemAvailable, lowest |
|---|---|---|---|---|---|---|---|
| `--resident-budget-gib 72`, v0.1.43 | 63.95 GiB | 0 of 2,258 | 11.42 / 11.23 | 2,870 / 2,919 | 28.9 / 28.9 GB | 62.0 / 67.5 | 17.0 GiB |
| `--resident-budget-gib 72`, v0.1.43 + this PR | 70.53 GiB | 2,258 of 2,258 | 8.87 / 8.78 | 3,695 / 3,731 | 1.2 / 1.2 GB | 67.4 / 70.8 | 11.6 GiB |
| `--resident-experts`, v0.1.43 | 70.53 GiB | 2,258 of 2,258 | 8.95 / 8.83 | 3,660 / 3,712 | 1.2 / 1.2 GB | 68.0 / 68.6 | 12.6 GiB |

The engine's lines with this PR at 72:

```
FileExpertSource: RAM budget 72.00 GiB: 21907 of the 63.95 GiB of experts the GPU cache does not hold, by profile rank; the rest are read from the files
FileExpertSource: the prompt path's lend region: 2258 of its 2258 slots keep their experts in RAM too (6.59 GiB of the budget's remaining 8.05 GiB)
FileExpertSource: mapped pinned cache complement ready: resident 70.53 GiB, pinned 70.53 GiB in 19 s; 70.53 GiB page-locked after taking the pages in steps;
FileExpertSource: 2258 of the prompt path's 2258 lendable slots keep their experts in RAM too
strata serve: the prompt path borrows 2258 CUDA0 cache slots (6.59 GiB)
```

Stock v0.1.43 at 72 still prints the #669 warning ("lends 2258 cache slots to the prompt path, but only 0 of their experts fit in RAM"); with the PR it is gone. A 72 GiB budget now ends up where `--resident-experts` does: the same 70.53 GiB in RAM, the 32K read in 8.8-8.9 s instead of 11.2-11.4 s, and 1.2 GB read from the drive per prompt instead of 28.9 GB. The lowest MemAvailable drops by about the 6.6 GiB the lend region takes, as it should. The kernel log was clean after each run.

Not tested here: a budget too small for the whole lend region, a layer split, a helper GPU.

Measured and drafted with Claude Code.
