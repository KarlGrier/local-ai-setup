**CORRECTION (11-03 10:xx, from UPGRADE-ESTIMATE.md, verified in ds4_main.cpp:933): the DeepSeek "on the GPU" / "CPU lane" / SSD columns below are WRONG.** The engine's per-request "CPU lane N%" divides counters that run since the engine started (never reset), so prompt tokens are mixed in; decode-only (per-turn differences) VRAM shares are ~60 / 54 / 47 % (two cards, 100 / 75 / 50 %) and ~48 / 44 / 34 % (the 5080 alone). The SSD GB / token column includes W3's 23.5K-token prompt reads: decode alone is ~40-50 MB / token. The splice's "PCIe / 4060 Ti" column adds two tiers (on-100: 4060 Ti 10.6 %, PCIe 7.8 %). Decode / P4K / P20K rates and the P20K SSD GB are right. See UPGRADE-ESTIMATE.md for the corrected tier numbers.

# Upgrade-pricing sweep (11-03): speed against the experts held in VRAM, 1 pass each

## DeepSeek V4.1 Flash, the daily config (15,360 experts)

| arm | experts in VRAM | RAM store | on the GPU (VRAM or RAM over PCIe) | CPU lane from RAM | SSD (upper bound) | SSD GB / token | decode | P4K | P20K | P20K SSD GB |
|---|---|---|---|---|---|---|---|---|---|---|
| on-v10 | 1,308 | 6,363 | 89.8 % | 6.9 % | 3.3 % | 0.067 | 28.8 | 342 | 701 | 115.08 |
| on-v075 | 971 | 6,363 | 88.1 % | 8.3 % | 3.6 % | 0.075 | 27.1 | 335 | 689 | 118.13 |
| on-v05 | 635 | 6,363 | 86.1 % | 10.1 % | 3.8 % | 0.078 | 25.7 | 328 | 676 | 122.69 |
| off-v10 | 711 | 6,363 | 86.6 % | 9.9 % | 3.5 % | 0.073 | 28.2 | 438 | 714 | 64.11 |
| off-v075 | 521 | 6,363 | 85.3 % | 11.2 % | 3.5 % | 0.072 | 27.4 | 434 | 701 | 65.54 |
| off-v05 | 335 | 6,363 | 83.4 % | 12.7 % | 3.8 % | 0.079 | 25.4 | 431 | 725 | 66.96 |

## Round 15's splice on the P028x engine (24,576 experts, Q5 ~4.0 MB each)

| arm | slots 5080 + 4060 Ti | 5080 cache | PCIe / 4060 Ti | RAM | SSD | SSD GB / token | decode | P4K | P20K | P20K SSD GB |
|---|---|---|---|---|---|---|---|---|---|---|
| on-100 | 2371 + 1893 | - | - | - | - | - | - (0 of 3) | 1,155 | 2,032 | 62.75 |
| on-75 | 1778 + 1893 | - | - | - | - | - | - (0 of 3) | 1,080 | 2,120 | 64.25 |
| on-50 | 1186 + 1893 | - | - | - | - | - | - (0 of 3) | 1,012 | 1,668 | 91.99 |
| off-100 | 2371 + 0 | 60.4 % | 9.1 % | 26.8 % | 3.7 % | 0.092 | 34.9 (2 of 3) | 1,110 | 2,006 | 62.93 |
| off-75 | 1778 + 0 | 50.3 % | 11.5 % | 33.9 % | 4.3 % | 0.106 | 30.0 (3 of 3) | 1,074 | 2,076 | 64.39 |
| off-50 | 1186 + 0 | 44.6 % | 12.6 % | 37.5 % | 5.2 % | 0.130 | 26.7 (2 of 3) | 1,003 | 1,652 | 92.22 |
