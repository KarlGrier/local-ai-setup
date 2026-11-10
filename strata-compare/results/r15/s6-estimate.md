| placement | measured round (CLI) ms | of it: GPU ~ / CPU RAM experts / SSD reading | SSD MB per round | pool RAM rate GB/s | **estimated round, all in RAM** ms | CLI tok/s measured → **estimated** | served tok/s measured → **estimated** | RAM needed (GiB) |
|---|---|---|---|---|---|---|---|---|
| r15-q8-Dx71-full | 143.5 | 22 / 37 / 85 | 559 | 69.9 | **66.5** | 18.9 → **40.9** | 14.8 → **31.9** | 123 |
| r15-q8-Bx71-full | 126.9 | 20 / 38 / 68 | 446 | 70.7 | **64.7** | 19.5 → **38.3** | 12.9 → **25.3** | 130 |
| r15-q5s-Bx72-full | 56.2 | 16 / 25 / 14 | 80 | 73.6 | **42.8** | 48.7 → **64.0** | 34.7 → **45.6** | 101 |

ESTIMATE, not measured: the SSD part of the round replaced by RAM reads at the pool's measured rate; the CPU's RAM bandwidth is shared, so the real number would sit somewhat lower.
