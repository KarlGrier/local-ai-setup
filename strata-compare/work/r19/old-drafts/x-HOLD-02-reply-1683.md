Thanks. To your question: no, there was no reason against 72; I just didn't know yet that the lend region mattered. The budget was sized before the model's first start. The 5080's cache would hold about 2,650 experts, and every other expert came to 63.9 GiB. Since the budget branch only allocates what it places, I expected anything above 64 GiB to hold every expert, and set 66 for some slack. The lend slots' 6.5 GiB was not part of that sum, because I didn't know a budget turns the lend region off. I only learned that from the start warning, and then from `pin_cache_complement`, which also showed that a larger budget could not change the count. So I didn't measure one, and for the issue I kept 66 to match the earlier run.

I have now started it with `--resident-budget-gib 72`, on stock v0.1.42 (`61b3fb5d`, built with `-DSTRATA_MMQ_KQUANTS=ON`) with `STRATA_ROUTE_TAIL_SKIP=0`, otherwise the issue's machine, file and flags. The engine's own lines:

```
FileExpertSource: RAM budget 72.00 GiB: 21925 of the 64.00 GiB of experts the GPU cache does not hold, by profile rank; the rest are read from the files
FileExpertSource: mapped pinned cache complement ready: resident 64.00 GiB, pinned 64.00 GiB in 15 s; page-locked and mapped
strata generate: WARNING: a prompt chunk of 16384 tokens lends 2225 cache slots to the prompt path, but only 0 of their experts fit in RAM: the others are read from the SSD on every chunk, ...
```

So with 72 the RAM copy is the same 64.00 GiB as with 66, and 0 of the 2,225 lent slots keep their experts in RAM.

I don't have the 32K read time, the bytes read from the drive or the lowest MemAvailable for 72 yet. The server did not get as far as the prompts: right after `the prompt path borrows 2225 CUDA0 cache slots (6.49 GiB)`, the kernel's OOM killer ended the engine. The same happened with 66 on the same build, although 66 ran on v0.1.41 in the issue with MemAvailable at 16.6 GiB or more. The guard I run beside it still saw 17.3 GiB available. I don't know yet whether this is v0.1.42 or this machine today, and I'll follow up when I do.

Measured and drafted with Claude Code.
