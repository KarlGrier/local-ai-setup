# Round 10 D.3 — Q4 fair retest (≤ 2 h, no tuning) + your acceptance addition

Budget steps 24 → 56 GiB (8 GiB steps; at 56 GiB min MemAvailable 28.6 GiB, the next step would cross ~20 GiB) → **56 GiB**. Q4 = the base built with -DSTRATA_MMQ_KQUANTS=ON (engine-v36q4), --vram-reserve-mib 1000, 32K context, no chat cache, the 5080 alone; IQ3_S reference = the base on the 5080 alone, same settings. Your settings (T 1.0 / 0.95 / 20 / min-p 0.05).

## Served (two Q4 runs around one IQ3_S run)

| item | Q4 run 1 | IQ3_S | Q4 run 2 |
|---|---|---|---|
| math | 59.7 tok/s, TTFT 0.95 s, NVMe 4.3 GB, file tier 48.0 GB, swap-in 96166 pages | 124.8 tok/s, TTFT 0.54 s, NVMe 0.1 GB, file tier 0.0 GB, swap-in 148 pages | 60.2 tok/s, TTFT 0.92 s, NVMe 4.0 GB, file tier 47.6 GB, swap-in 33156 pages |
| code | 49.7 tok/s, TTFT 1.03 s, NVMe 4.3 GB, file tier 33.4 GB, swap-in 5605 pages | 103.8 tok/s, TTFT 0.53 s, NVMe 0.1 GB, file tier 0.0 GB, swap-in 347 pages | 48.8 tok/s, TTFT 1.14 s, NVMe 4.9 GB, file tier 34.8 GB, swap-in 5766 pages |
| 8k | 47.5 tok/s, TTFT 4.34 s, NVMe 2.9 GB, file tier 18.3 GB, swap-in 4719 pages | 90.3 tok/s, TTFT 2.33 s, NVMe 0.3 GB, file tier 0.0 GB, swap-in 8 pages | 55.3 tok/s, TTFT 4.11 s, NVMe 3.3 GB, file tier 18.2 GB, swap-in 5119 pages |
| 32k-cut | 55.4 tok/s, TTFT 12.50 s, NVMe 2.2 GB, file tier 56.4 GB, swap-in 50402 pages | 96.8 tok/s, TTFT 8.17 s, NVMe 0.7 GB, file tier 0.0 GB, swap-in 26 pages | 58.5 tok/s, TTFT 12.23 s, NVMe 1.5 GB, file tier 56.3 GB, swap-in 2417 pages |

| text (human-written) | IQ3_S NLL (one GPU) | Q4 NLL (one GPU) | Q4 − IQ3_S (clipped at 5) | ± se |
| corpus | 0.3884 | 0.3805 | -0.0069 | 0.0048 |
| long16k | 2.9210 | 2.3681 | -0.2483 | 0.0285 |
| long24k | 2.8899 | 2.3767 | -0.2208 | 0.0280 |
| long28k | 2.0153 | 1.8285 | -0.0777 | 0.0269 |
| text (forced, same ids) | IQ3_S acceptance | Q4 acceptance | IQ3_S first draft | Q4 first draft | IQ3_S / Q4 NLL |
| corpus | 0.839 (844/1006) | 0.857 (853/995) | 0.859 | 0.865 | 0.390 / 0.381 |
| long16k | 0.585 (544/930) | 0.576 (536/930) | 0.633 | 0.638 | 5.488 / 6.157 |
| long24k | 0.553 (505/913) | 0.543 (512/943) | 0.643 | 0.664 | 6.237 / 5.748 |
| long28k | 0.618 (586/948) | 0.615 (587/954) | 0.690 | 0.688 | 4.517 / 4.525 |
