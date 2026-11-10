Thanks for looking into it. The numbers below are from stock v0.1.42 (`61b3fb5d`) with `STRATA_ROUTE_TAIL_SKIP=0`, on the same machine, file and flags as in the issue, so they compare with its v0.1.41 runs. (The tail skip default is only set at serve start-up, so these `strata generate` runs would not have used it anyway.)

**1. Raw drive numbers.** The Q8_0 file is still here. It is split into six shards, and the routed experts are in shards 4–6, so fio got those three as its file list (`--filename=...-00004-of-00006.gguf:...-00005-of-00006.gguf:...-00006-of-00006.gguf`). This is your command, plus `--readonly`:

| run | ioengine | bandwidth |
|---|---|---|
| 1 | psync (fio's default) | 9,386 MB/s (8,951 MiB/s), 1,118 IOPS |
| 2 | psync (fio's default) | 9,704 MB/s (9,255 MiB/s), 1,156 IOPS |
| 3: the same with `--ioengine=libaio` | libaio | 7,803 MB/s (7,441 MiB/s), 930 IOPS |

With fio's default ioengine (psync), `--iodepth=32` has no effect, so runs 1 and 2 keep 8 reads of 8 MiB in flight. The libaio run keeps 8 × 32 in flight.

**2. The A/B with `STRATA_IO_THREADS` unset and 16 (and 64, the issue's value).** The method is the issue's: `strata generate --stats`, greedy, 1,024 tokens after the 136-token math prompt, `--resident-budget-gib 64`, and the model's page cache dropped before each run.

| `STRATA_IO_THREADS` | `STRATA_UNBUFFERED_LOAD=1`: decode tok/s (two runs) | ms per verify round | file tier: ms reading per round |
|---|---|---|---|
| unset | 14.45 / 14.52 | 173.0 / 172.2 | 103.8 / 102.4 |
| 16 | 15.67 / 16.00 | 159.5 / 159.4 | 99.7 / 100.8 |
| 64 | 16.42 / 15.47 | 145.6 / 164.8 | 89.2 / 106.2 |
| 64, v0.1.41 (the issue) | 15.26 / 15.61 | 156.0 / 153.7 | 95.8 / 95.3 |

I could not measure the other arm (the rule's choice, through the file cache) on v0.1.42. I tried it four times. Three times the kernel's OOM killer ended the engine while it was page-locking the 64 GiB copy, and the fourth run went past my own swap limit (+4 GiB). In the issue's v0.1.41 runs this arm already went down to 17.6 GiB MemAvailable with swap +3.5 GiB. So I think the margin was just thinner this time, not that v0.1.42 changed anything: between the two versions the budget path only gained the layer-split lend regions. Either way, on this 96 GB PC with a 64 GiB budget the file-cache choice is close to running out of memory. The unbuffered runs stay at 15 GiB available or more, because the mapping is closed in that mode.

On the thread count: as far as I can read the code, on Linux `STRATA_IO_THREADS` only sizes `DirectFile`'s pool (default 16, clamped to 1..64), which the PLE row reader uses. The file tier's unbuffered expert reads go through `io_submit` on the calling threads (`expert_source.cpp`). For them, unset and 16 are the same setting, and 64 only changes the PLE reader. The numbers fit that, within their noise: the means are 14.49 (unset), 15.84 (16) and 15.95 tok/s (64). Unset and 16 differ by 9 % although they are the same setting, and the two runs at 64 differ by 6 %. On this PC the CPU expert pool's time per round varies between starts, and so does the reading time per round (89 and 106 ms in the two runs at 64). So I don't think the gain in the issue comes from the thread count. A clean answer would need more runs per setting than I made here.

Measured and drafted with Claude Code.
