# Pinpoint: which change moves the KL percentiles (report only, v026)

Teacher-forced, 8 segments x 256 positions (2040 compared), against the final check's base (the engine defaults).
Each step adds one group of the ship config's settings. 'vs base' = KL of the step against the base; 'vs previous' = KL of the step against the step before (what that one change moves).

| run | vs | p50 | p75 | p90 | p95 | p99 | mean | max | KL>1 | top-1 |
|---|---|---|---|---|---|---|---|---|---|---|
| reference R1-chunk4096 | base | 0.00017 | 0.00303 | 0.01358 | 0.02700 | 0.08630 | 0.00719 | 1.546 | 1 | 2010 |
| reference R2-cpu-share | base | 0.00014 | 0.00272 | 0.01265 | 0.02762 | 0.07111 | 0.00609 | 0.961 | 0 | 2011 |
| pin1-profile (the ship's expert profile file) | base | 0.00012 | 0.00284 | 0.01289 | 0.02558 | 0.08556 | 0.00598 | 1.522 | 1 | 2012 |
|  | base | 0.00012 | 0.00284 | 0.01289 | 0.02558 | 0.08556 | 0.00598 | 1.522 | 1 | 2012 |
| pin2-placement (+ GPU order and layer split) | base | 0.00013 | 0.00313 | 0.01491 | 0.02696 | 0.07458 | 0.00672 | 1.912 | 1 | 2014 |
|  | pin1-profile | 0.00017 | 0.00288 | 0.01299 | 0.02641 | 0.08076 | 0.00771 | 3.788 | 2 | 2016 |
| pin3-decay (+ cache decay) | base | 0.00012 | 0.00295 | 0.01443 | 0.02821 | 0.07458 | 0.00577 | 0.806 | 0 | 2015 |
|  | pin2-placement | 0.00000 | 0.00006 | 0.00252 | 0.00853 | 0.02730 | 0.00200 | 0.600 | 0 | 2035 |
| pin4-ship (+ the rest (settle, Engram cache, ...) = what ships) | base | 0.00012 | 0.00308 | 0.01376 | 0.02638 | 0.08053 | 0.00622 | 1.540 | 1 | 2015 |
|  | pin3-decay | 0.00006 | 0.00137 | 0.00748 | 0.01491 | 0.05628 | 0.00437 | 0.908 | 0 | 2028 |

Moves the percentiles most: **pin2-placement** (+ GPU order and layer split): against the step before, p90 0.01299, mean 0.00771.
pin4-ship byte-identical to final-cand-final (the final check's candidate): True.

Placement (segment 0):
- base: ds4: RAM store: up to 6814 slots of 10.3 MB (70.0 GB), policy 0, 8 reader threads, unbuffered reads / ds4: RAM store: 6558 of the profile's hottest experts read in (50.9 GB) in 5.6 s / ds4: CUDA0 layers [0, 21]: weights 3.08 GB, experts 9.70 GB (1160 of 8448 in VRAM), caches 0.02 GB, 572 MiB free / ds4: CUDA1 layers [22, 39] + head: weights 2.78 GB, experts 2.03 GB (204 of 6912 in VRAM), caches 0.01 GB, 584 MiB free / ds4: 13996 routed experts on the CPU lane (121.1 GB, in place in the model's files), 16 threads
- pin1-profile: ds4: RAM store: up to 6814 slots of 10.3 MB (70.0 GB), policy 0, 8 reader threads, unbuffered reads / ds4: RAM store: 6558 of the profile's hottest experts read in (50.9 GB) in 5.6 s / ds4: CUDA0 layers [0, 21]: weights 3.08 GB, experts 9.70 GB (1160 of 8448 in VRAM), caches 0.02 GB, 572 MiB free / ds4: CUDA1 layers [22, 39] + head: weights 2.78 GB, experts 2.03 GB (204 of 6912 in VRAM), caches 0.01 GB, 584 MiB free / ds4: 13996 routed experts on the CPU lane (121.1 GB, in place in the model's files), 16 threads
- pin2-placement: ds4: RAM store: up to 6814 slots of 10.3 MB (70.0 GB), policy 0, 8 reader threads, unbuffered reads / ds4: RAM store: 6558 of the profile's hottest experts read in (50.9 GB) in 5.6 s / ds4: CUDA0 layers [0, 9]: weights 1.42 GB, experts 3.36 GB (418 of 3840 in VRAM), caches 0.01 GB, 590 MiB free / ds4: CUDA1 layers [10, 39] + head: weights 4.44 GB, experts 8.29 GB (904 of 11520 in VRAM), caches 0.01 GB, 566 MiB free / ds4: 14038 routed experts on the CPU lane (121.1 GB, in place in the model's files), 16 threads
- pin3-decay: ds4: RAM store: up to 6814 slots of 10.3 MB (70.0 GB), policy 0, 8 reader threads, unbuffered reads / ds4: RAM store: 6558 of the profile's hottest experts read in (50.9 GB) in 5.6 s / ds4: CUDA0 layers [0, 9]: weights 1.42 GB, experts 3.36 GB (418 of 3840 in VRAM), caches 0.01 GB, 590 MiB free / ds4: CUDA1 layers [10, 39] + head: weights 4.44 GB, experts 8.29 GB (904 of 11520 in VRAM), caches 0.01 GB, 566 MiB free / ds4: 14038 routed experts on the CPU lane (121.1 GB, in place in the model's files), 16 threads
- pin4-ship: ds4: RAM store: up to 6814 slots of 10.3 MB (70.0 GB), policy 0, 8 reader threads, unbuffered reads / ds4: RAM store: 6558 of the profile's hottest experts read in (50.9 GB) in 5.6 s / ds4: CUDA0 layers [0, 9]: weights 1.42 GB, experts 3.36 GB (418 of 3840 in VRAM), caches 0.01 GB, 590 MiB free / ds4: CUDA1 layers [10, 39] + head: weights 4.44 GB, experts 8.29 GB (904 of 11520 in VRAM), caches 0.01 GB, 566 MiB free / ds4: 14038 routed experts on the CPU lane (121.1 GB, in place in the model's files), 16 threads

Run times: pin1-profile: rc 0, 543 s, lowest MemAvailable 22.6 GB (8 engine runs, one segment each); pin2-placement: rc 0, 423 s, lowest MemAvailable 23.3 GB (8 engine runs, one segment each); pin3-decay: rc 0, 423 s, lowest MemAvailable 23.2 GB (8 engine runs, one segment each); pin4-ship: rc 0, 371 s, lowest MemAvailable 27.9 GB (8 engine runs, one segment each)
