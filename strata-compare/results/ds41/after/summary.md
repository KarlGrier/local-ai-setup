# DeepSeek follow-ups (2026-10-26)

Builds: fix 789678b59527, test 0cf5fa1bac59. Ship config: `{"order": "rev", "DS4_SPLIT": "10,30", "DS4_SETTLE_MS": 0, "DS4_CACHE_DECAY": "0.8", "DS4_ENGRAM_CACHE_MB": 16}`.

## Split screen (Karl: 8/32 with the 4060 Ti first, before the graded set)

```
{
 "from": "10,30",
 "screen_a": {
  "decode": 28.05,
  "P4K": 319.1,
  "P20K": 605.5,
  "vram_experts": [
   415,
   901
  ],
  "guard": null
 },
 "screen_8,32": {
  "decode": 28.83,
  "P4K": 341.5,
  "P20K": 705.3,
  "vram_experts": [
   460,
   870
  ],
  "guard": null
 },
 "screen_gain": {
  "decode": 2.78,
  "P20K": 16.48,
  "P4K": 7.02
 },
 "aba": {
  "A1": {
   "decode": {
    "ref": 27.97,
    "new": 28.56,
    "gain_pct": 2.11,
    "noise_pct": 1.8
   },
   "P4K": {
    "ref": 332.1,
    "new": 357.9,
    "gain_pct": 7.77,
    "noise_pct": 3.34,
    "ssd_gb_ref": 53.1,
    "ssd_gb_new": 53.0
   },
   "P20K": {
    "ref": 601.4,
    "new": 698.8,
    "gain_pct": 16.2,
    "noise_pct": 1.68,
    "ssd_gb_ref": 109.7,
    "ssd_gb_new": 109.2
   }
  },
  "A2": {
   "decode": {
    "ref": 28.13,
    "new": 28.56,
    "gain_pct": 1.53,
    "noise_pct": 0.47
   },
   "P4K": {
    "ref": 334.7,
    "new": 357.9,
    "gain_pct": 6.93,
    "noise_pct": 3.17,
    "ssd_gb_ref": 53.6,
    "ssd_gb_new": 53.0
   },
   "P20K": {
    "ref": 599.2,
    "new": 698.8,
    "gain_pct": 16.62,
    "noise_pct": 1.68,
    "ssd_gb_ref": 110.0,
    "ssd_gb_new": 109.2
   }
  }
 },
 "kept": true,
 "verdict": "screen 8,32: P20K +16.5 %, decode +2.8 %; A/B/A: vs A1 decode +2.1 % (noise 1.8), P4K +7.8 %, P20K +16.2 %; vs A2 decode +1.5 % (noise 0.5), P4K +6.9 %, P20K +16.6 % -> KEPT"
}
```

## Item 6 - the one-line fix, slot keep off (follow-up reads)

```
 answer (2 passes): shared 7721 of the previous 7721, history matches, expected checkpoints {'ck0': 7994, 'ck1': 7993}, went back to 7720, read 250 (target 249) -> ok, TTFT 4.87 s
jan F5 (cap 512): prompt 8380 (server 8380), passes [[8380, 7970, 410]] (prompt, reused, read); after a normal answer (1 pass): shared 7970 of the previous 7970, history matches, expected checkpoints {'ck0': 7970, 'ck1': 7969}, went back to 7970, read 410 (target 410) -> ok, TTFT 6.22 s
notools start (cap 4096): prompt 7070 (server 7070), passes [[7070, 0, 7070]] (prompt, reused, read), TTFT 19.09 s
notools F1 (cap 512): prompt 7413 (server 7413), passes [[7413, 7069, 344], [7686, 7669, 17]] (prompt, reused, read); after a normal answer (1 pass): shared 7069 of the previous 7070, history matches, expected checkpoints {'ck0': 7070, 'ck1': 7069}, went back to 7069, read 344 (target 344) -> ok, TTFT 5.82 s
notools F2 (cap 4096): prompt 7571 (server 7571), passes [[7571, 7412, 159]] (prompt, reused, read); after a budget-hit answer (2 passes): shared 7412 of the previous 7413, history matches, expected checkpoints {'ck0': 7686, 'ck1': 7685}, went back to 7412, read 159 (target 159) -> ok, TTFT 3.87 s
notools F3 (cap 512): prompt 7796 (server 7796), passes [[7796, 7570, 226], [8069, 8052, 17]] (prompt, reused, read); after a normal answer (1 pass): shared 7570 of the previous 7571, history matches, expected checkpoints {'ck0': 7571, 'ck1': 7570}, went back to 7570, read 226 (target 226) -> ok, TTFT 4.72 s
notools F4 (cap 4096): prompt 7994 (server 7994), passes [[7994, 7795, 199]] (prompt, reused, read); after a budget-hit answer (2 passes): shared 7795 of the previous 7796, history matches, expected checkpoints {'ck0': 8069, 'ck1': 8068}, went back to 7795, read 199 (target 199) -> ok, TTFT 4.17 s
notools F5 (cap 512): prompt 8140 (server 8140), passes [[8140, 7993, 147], [8413, 8396, 17]] (prompt, reused, read); after a normal answer (1 pass): shared 7993 of the previous 7994, history matches, expected checkpoints {'ck0': 7994, 'ck1': 7993}, went back to 7993, read 147 (target 147) -> ok, TTFT 3.82 s
follow-up reads (slot keep off): PASS - 12 of 12 read only the last answer + the new message; after a budget-hit answer (2 passes): 6/6 ok, read 141 (target 141), TTFT 2.9 s; after a normal answer (1 pass): 6/6 ok, read 288 (target 288), TTFT 5.25 s; render mismatches 0, history differs 0
```

## Item 2 - repeat pairs, stock v0.2.6, STRATA_DS4_REUSE=0

```
jan1024 #1: passes [(688, 0, 688, 116)] (prompt, reused, read, generated) -> continuation None; finish tool_calls, calls ['web_search', 'fetch_page'], 13.8 s
jan1024 #2: passes [(688, 0, 688, 90)] (prompt, reused, read, generated) -> continuation None; finish tool_calls, calls ['web_search'], 11.0 s
jan4096 #1: passes [(688, 0, 688, 140)] (prompt, reused, read, generated) -> continuation None; finish tool_calls, calls ['web_search', 'fetch_page'], 12.9 s
jan4096 #2: passes [(688, 0, 688, 88)] (prompt, reused, read, generated) -> continuation None; finish tool_calls, calls ['web_search'], 10.7 s
w1 #1: passes [(113, 0, 113, 2304), (2434, 0, 2434, 751)] (prompt, reused, read, generated) -> continuation MISS; finish length, calls [], 124.9 s
w1 #2: passes [(113, 0, 113, 2304), (2434, 0, 2434, 751)] (prompt, reused, read, generated) -> continuation MISS; finish length, calls [], 122.9 s
w1k #1: passes [(113, 0, 113, 2304), (2434, 0, 2434, 751)] (prompt, reused, read, generated) -> continuation MISS; finish length, calls [], 123.6 s
w1k #2: passes [(113, 0, 113, 2304), (2434, 0, 2434, 751)] (prompt, reused, read, generated) -> continuation MISS; finish length, calls [], 122.8 s
continuations (exact): 0 hits, 4 misses, 4 requests without one (the thinking ended before the budget); identical pairs: {'jan1024': False, 'jan4096': False, 'w1': False, 'w1k': False}
```

## Item 2 - repeat pairs, counter reset per seeded request, REUSE=0

```
jan1024 #1: passes [(688, 0, 688, 116)] (prompt, reused, read, generated) -> continuation None; finish tool_calls, calls ['web_search', 'fetch_page'], 13.8 s
jan1024 #2: passes [(688, 0, 688, 116)] (prompt, reused, read, generated) -> continuation None; finish tool_calls, calls ['web_search', 'fetch_page'], 11.5 s
jan4096 #1: passes [(688, 0, 688, 44)] (prompt, reused, read, generated) -> continuation None; finish tool_calls, calls ['web_search'], 8.8 s
jan4096 #2: passes [(688, 0, 688, 102)] (prompt, reused, read, generated) -> continuation None; finish tool_calls, calls ['web_search', 'fetch_page'], 11.4 s
w1 #1: passes [(113, 0, 113, 2304), (2434, 0, 2434, 751)] (prompt, reused, read, generated) -> continuation MISS; finish length, calls [], 125.1 s
w1 #2: passes [(113, 0, 113, 2304), (2434, 0, 2434, 751)] (prompt, reused, read, generated) -> continuation MISS; finish length, calls [], 123.3 s
w1k #1: passes [(113, 0, 113, 2304), (2434, 0, 2434, 751)] (prompt, reused, read, generated) -> continuation MISS; finish length, calls [], 122.5 s
w1k #2: passes [(113, 0, 113, 2304), (2434, 0, 2434, 751)] (prompt, reused, read, generated) -> continuation MISS; finish length, calls [], 122.6 s
continuations (exact): 0 hits, 4 misses, 4 requests without one (the thinking ended before the budget); identical pairs: {'jan1024': False, 'jan4096': False, 'w1': False, 'w1k': False}
```

## Item 2 - repeat pairs, counter reset per seeded request, reuse on

```
jan1024 #1: passes [(688, 0, 688, 116)] (prompt, reused, read, generated) -> continuation None; finish tool_calls, calls ['web_search', 'fetch_page'], 13.7 s
jan1024 #2: passes [(688, 687, 1, 85)] (prompt, reused, read, generated) -> continuation None; finish tool_calls, calls ['web_search', 'fetch_page'], 3.7 s
jan4096 #1: passes [(688, 687, 1, 85)] (prompt, reused, read, generated) -> continuation None; finish tool_calls, calls ['web_search', 'fetch_page'], 3.3 s
jan4096 #2: passes [(688, 687, 1, 85)] (prompt, reused, read, generated) -> continuation None; finish tool_calls, calls ['web_search', 'fetch_page'], 3.3 s
w1 #1: passes [(113, 0, 113, 2304), (2434, 2417, 17, 751)] (prompt, reused, read, generated) -> continuation hit; finish length, calls [], 115.7 s
w1 #2: passes [(113, 0, 113, 2304), (2434, 2417, 17, 751)] (prompt, reused, read, generated) -> continuation hit; finish length, calls [], 113.3 s
w1k #1: passes [(113, 0, 113, 2304), (2434, 2417, 17, 751)] (prompt, reused, read, generated) -> continuation hit; finish length, calls [], 114.2 s
w1k #2: passes [(113, 0, 113, 2304), (2434, 2417, 17, 751)] (prompt, reused, read, generated) -> continuation hit; finish length, calls [], 114.3 s
continuations (exact): 4 hits, 0 misses, 4 requests without one (the thinking ended before the budget); identical pairs: {'jan1024': False, 'jan4096': True, 'w1': False, 'w1k': False}
```

## Item 3 - resumed vs fresh (teacher-forced, report only)

```
{
 "vs_fresh": {
  "R1-chunk4096": {
   "p50": 0.00012049011133336349,
   "p75": 0.0030060419963251804,
   "p90": 0.012784930236444997,
   "p95": 0.024782544427420405,
   "p99": 0.08555312426472894,
   "mean": 0.006628134111781643,
   "max": 1.9685471691141623,
   "gt1": 1,
   "top1": 2010,
   "positions": 2040
  },
  "R2-cpu-share": {
   "p50": 0.0001476422545366881,
   "p75": 0.002921346957258955,
   "p90": 0.014005553992414013,
   "p95": 0.027891265559159033,
   "p99": 0.07993624803360908,
   "mean": 0.006204948409885757,
   "max": 1.2582027782031306,
   "gt1": 1,
   "top1": 2012,
   "positions": 2040
  },
  "pieces4": {
   "p50": 0.00016490541375520397,
   "p75": 0.00263151688281763,
   "p90": 0.01314420211019434,
   "p95": 0.029826444781372714,
   "p99": 0.0885220349126641,
   "mean": 0.006798757502117795,
   "max": 1.7341659358725556,
   "gt1": 1,
   "top1": 2015,
   "positions": 2040
  },
  "resume4": {
   "p50": 0.00016490541375520397,
   "p75": 0.00263151688281763,
   "p90": 0.01314420211019434,
   "p95": 0.029826444781372714,
   "p99": 0.0885220349126641,
   "mean": 0.006798757502117795,
   "max": 1.7341659358725556,
   "gt1": 1,
   "top1": 2015,
   "positions": 2040
  },
  "resume1": {
   "p50": 0.0,
   "p75": 0.0,
   "p90": 0.0,
   "p95": 0.0,
   "p99": 0.0,
   "mean": 0.0,
   "max": 0.0,
   "gt1": 0,
   "top1": 2040,
   "positions": 2040
  }
 },
 "pairs": {
  "resume4 vs pieces4 (the set-aside / take-back alone)": {
   "p50": 0.0,
   "p75": 0.0,
   "p90": 0.0,
   "p95": 0.0,
   "p99": 0.0,
   "mean": 0.0,
   "max": 0.0,
   "gt1": 0,
   "top1": 2040,
   "positions": 2040
  }
 },
 "fresh_equals_round_eng_cand": true,
 "resume4_judged": "within the rounding references",
 "pieces4_judged": "within the rounding references",
 "resume1_judged": "within the rounding references"
}
```

## Item 1 - the daily config

```
{
 "tries": [
  {
   "store_gb": 68,
   "ok": true,
   "lowest_mem": 15.5,
   "guard": null,
   "softstop": false,
   "fill": {
    "chats": 17,
    "saved": 16,
    "in_ram_last": 16,
    "slot_gb_sum": 0.64,
    "largest_slot": {
     "tokens": 31901,
     "gb": 0.04,
     "in_ram": 2
    },
    "gb_per_1k_tokens": 0.0013,
    "at_32768_x16_gb": 0.66,
    "rss_growth_mb": 1954,
    "memavail_after_fill_gb": 20.44
   },
   "dir": "/home/USER/ai-speed-testing/strata-compare/results/ds41/tuning/daily-68-1026-1536",
   "cfg": "/home/USER/ai-speed-testing/strata-compare/configs/DS41-tune-after-daily-68.json"
  }
 ],
 "store_gb": 68
}
```
Config: /home/USER/ai-speed-testing/strata-compare/configs/DS41-daily.json; launcher smoke test: ok (start rc 0; models {"object": "list", "data": [{"id": "deepseek-v4.1-flash", "object": "model", "status": {"value": "loaded"}, "meta": {"n_; reply {"id": "chatcmpl-887250216e9145e19b1c21ab", "object": "chat.completion", "created": 1793048159, "model": "deepseek-v4.1-flash", "choices": [{"index": 0, "messag)

## The graded set (answers; grades and the report come after the gap: graded/REPORT.md)

- DeepSeek engine: v026p343 + {"STRATA_DS4_PROMPT_SKIP": "1", "DS4_SPLIT": "8,32"}
- Qwen: {'label': 'g1026-qwen-p021m-medium', 'min': 25.6, 'lowest_mem': 23.9, 'guard': None, 'complete': True}
- DeepSeek 50: {'label': 'g1026-ds-e50', 'engine': 'v026p343', 'mods': {'STRATA_DS4_PROMPT_SKIP': '1', 'DS4_SPLIT': '8,32'}, 'items': 51, 'complete': True, 'runs': ['g-ds50']}
- DeepSeek 75: {'label': 'g1026-ds-e75', 'engine': 'v026p343', 'mods': {'STRATA_DS4_PROMPT_SKIP': '1', 'DS4_SPLIT': '8,32'}, 'items': 14, 'complete': True, 'runs': ['g-ds75']}

## Context cost (report only)

```
{
 "32768": {
  "decode": 28.34,
  "P4K": 348.9,
  "P20K": 698.9,
  "vram_experts": [
   460,
   870
  ],
  "lowest_mem": 19.4,
  "guard": null,
  "softstop": false,
  "dir": "/home/USER/ai-speed-testing/strata-compare/results/ds41/tuning/ctx-32k-1026-1928",
  "engine_lines": "[strata] 2026-10-26 19:29:11 engine started: /home/USER/ai-speed-testing/strata-compare/engine-v026p343-ds41/strata-dsv41 --serve --pack /home/USER/ai-speed-tes / ds4: CUDA0 layers [0, 7]: weights 1.14 GB, experts 3.66 GB (460 of 3072 in VRAM), caches 0.01 GB, 594 MiB free / ds4: CUDA1 layers [8, 39] + head: weights 4.72 GB, experts 7.95 GB (870 of 12288 in VRAM), caches 0.03 GB, 578 MiB free / ds4: 14030 routed experts on the CPU lane (121.2 GB, in place in the model's files), 16 threads"
 },
 "65536": {
  "decode": 28.47,
  "P4K": 349.9,
  "P20K": 695.2,
  "vram_experts": [
   456,
   864
  ],
  "lowest_mem": 19.4,
  "guard": null,
  "softstop": false,
  "dir": "/home/USER/ai-speed-testing/strata-compare/results/ds41/tuning/ctx-64k-1026-1948",
  "engine_lines": "[strata] 2026-10-26 19:49:31 engine started: /home/USER/ai-speed-testing/strata-compare/engine-v026p343-ds41/strata-dsv41 --serve --pack /home/USER/ai-speed-tes / ds4: CUDA0 layers [0, 7]: weights 1.14 GB, experts 3.63 GB (456 of 3072 in VRAM), caches 0.01 GB, 596 MiB free / ds4: CUDA1 layers [8, 39] + head: weights 4.72 GB, experts 7.91 GB (864 of 12288 in VRAM), caches 0.05 GB, 580 MiB free / ds4: 14040 routed experts on the CPU lane (121.3 GB, in place in the model's files), 16 threads"
 },
 "131072": {
  "decode": 28.27,
  "P4K": 350.1,
  "P20K": 699.0,
  "vram_experts": [
   451,
   857
  ],
  "lowest_mem": 19.4,
  "guard": null,
  "softstop": false,
  "dir": "/home/USER/ai-speed-testing/strata-compare/results/ds41/tuning/ctx-128k-1026-2009",
  "engine_lines": "[strata] 2026-10-26 20:10:11 engine started: /home/USER/ai-speed-testing/strata-compare/engine-v026p343-ds41/strata-dsv41 --serve --pack /home/USER/ai-speed-tes / ds4: CUDA0 layers [0, 7]: weights 1.14 GB, experts 3.59 GB (451 of 3072 in VRAM), caches 0.02 GB, 590 MiB free / ds4: CUDA1 layers [8, 39] + head: weights 4.72 GB, experts 7.83 GB (857 of 12288 in VRAM), caches 0.10 GB, 586 MiB free / ds4: 14052 routed experts on the CPU lane (121.4 GB, in place in the model's files), 16 threads"
 }
}
```

