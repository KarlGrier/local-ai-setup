expert blob bytes per layer: 7 distinct sizes, 1.510 - 2.662 MB (by layer count: 1.51 MB x 5, 1.72 MB x 3, 1.87 MB x 1, 1.97 MB x 15, 2.18 MB x 14, 2.33 MB x 9, 2.66 MB x 1)
5080 today (native pack + profile -> open_sized, per-expert slots, 256-byte aligned): 4559 slots = 8.695 GiB; padding = the 256-byte rounding only: 0.0 KB (0.0000 %)
if every slot were sized for the largest expert (2.662 MB, the uniform path): the same 8.69 GiB holds 3506 slots, of which 1.99 GiB (22.9 %) is padding; sized slots fit 1053 more experts (+30.0 %)
engine log (configs/R12B start): 'expert cache auto ... -> 3507 slots' (the uniform count) then 'expert cache 4559 slots, 8.69 GiB' (sized)
5080 slots per layer (min / median / max): 75 94 115
4060 Ti helper: 3300 sized slots = 6.21 GiB; uniform slots of 2.66 MB would hold 2504 (sized: +796, +31.8 %)
