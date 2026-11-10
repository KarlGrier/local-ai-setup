# Item 7d - install note (staged 11-03; NOTHING installed, nothing started)

Plan and evidence: `results/bench2/PLAN-7D.md`. Queue plan draft: `results/bench2/queue-plan-7d.json.draft`.

**Only with no LDR run, Jan job, bench queue, replay or grading live.** `check.sh pre` enforces it (bench unit
inactive, `run/bench.lock` free, no `run/paid-run.json`, the queue's own Jan-job test (state only), no replay /
grading / install unit active) and refuses otherwise. It was green on 11-03 at staging time.

## What changes

| live file | from | backup | change |
|---|---|---|---|
| tools/search_route.py | staging/item7d/tools/ | tools/search_route.py.before-7d | `_select` in a profile (parsed, validated; a broken one = routing off, as any broken table); `select_step()`, the 7d rule (pure) |
| tools/paid_search.py | staging/item7d/tools/ | tools/paid_search.py.before-7d | a profile with `_select` asks its paid sources only on picked searches; agent label from LDR's ContextVar (`sys.modules`, never imported); per-run state `~/.config/deep-research/paid-route-state.json` (locked; key run id + run-file stamp; 7-day expiry, no month reset); `"select"` in the route log; S2's status in the route log |
| tools/paid-route.json | staging/item7d/tools/ | tools/paid-route.json.before-7d | + profiles `7d`, `7dx` (every other profile byte-identical; `enabled` and `cache` stay false) |
| tools/s2_search.py | staging/item7d/tools/ | tools/s2_search.py.before-7d | key from `~/.config/deep-research/semanticscholar.key` when it exists (x-api-key, read at request time, never logged); one line per call in `logs/s2-search.jsonl` (HTTP status, count, key yes/no; no key, no query). Not used by 7d; harmless for the other profiles |
| results/bench2/queue-plan-7d.json | the .draft | (new file) | 11 runs: s1-s4 p7d / p7dx pairs, then o01-o03 p7d |
| (not installed) | staging/item7d/tools/relief_counts.py | - | the live copy scans only screen / hard-screen folders; this one adds shop-7e (needed for s1-s4's restart counts). A read-only report: run it from staging (step 6); install later if wanted |

Not changed: the LDR package and its hook (patch 0005 calls `paid_search.search(query, results, client="ldr",
max_results=10)`, which still works), bench2.py, bench2-queue.sh, paid_budget.py, exa_fallback.py,
tavily_fallback.py, paid_cache.py, paid_tracker.py, the counters. **Never install paid-route.json alone**: the old
search_route ignores `_select`, so "7d" would be Tavily on every search (a 7b rerun). install.sh copies all four.

## Steps

All commands use absolute paths (no cd).

0. Review: `diff -u /home/USER/ai/deep-research/tools/<file> /home/USER/ai/deep-research/staging/item7d/tools/<file>` for the four files; `cat /home/USER/ai/deep-research/results/bench2/queue-plan-7d.json.draft`.
1. `bash /home/USER/ai/deep-research/staging/item7d/check.sh pre` - nothing live; the live files still match `LIVE-SHA256-AT-STAGING.txt`
   (if one changed since 11-03, re-port the 7d change onto it instead of copying); `tests/run_all.sh`: test_select
   (52), test_paid_search_7d (29), test_s2 (13), item 7's own suites against the staged code (3) - all offline
   (127.0.0.1 mock, fake keys, temp files under staging/item7d/scratch).
2. `bash /home/USER/ai/deep-research/staging/item7d/install.sh` - runs step 1 again, installs the four files (backup, new file + mv), copies the
   plan draft to `results/bench2/queue-plan-7d.json`, then `check.sh post`: installed == staged (sha256), backups
   present, the live table loads with routing + cache off and `_select` on 7d / 7dx only, the 7d suites pass,
   `BENCH2_PLAN=queue-plan-7d.json bench2.py next --wide` = `shop-7e deep s1 medium p7d xhigh ... 7d - -`.
   (item7_regression is a pre-install check only: after the install the live table has two more profiles, and item
   7's test_route counts profiles.)
3. Bench unit, as for 7e: `cp -p /home/USER/.config/systemd/user/deep-research-bench.service /home/USER/ai/deep-research/tools/deep-research-bench.service.before-7d`;
   set `Environment=BENCH2_PLAN=queue-plan-7d.json` and the Description ("phase 4 item 7d since 11-0x:
   queue-plan-7d.json - s1-s4 p7d / p7dx pairs (routes 7d / 7dx, <= 30 paid per run), then o01-o03 p7d");
   `systemctl --user daemon-reload`.
4. `systemctl --user start deep-research-bench.service`. Its first question starts a fresh LDR (the fresh-LDR rule)
   with `LDR_SEARCH_FALLBACK=1`, so the new modules load there; Jan's research keeps the routing-off path.
5. Confirm it is running (Karl's rule): unit active + MainPID; `logs/bench2-queue.log` shows
   `LDR -> ... (a fresh LDR for every question)` and `shop-7e / deep / p7d / s1: running (item 7 route 7d)`;
   `run/paid-run.json` has `"route": "7d"`; `logs/paid-route.jsonl` rows for `shop-7e-deep-p7d/s1` carry
   `"select": {..., "picked": false, "why": "opening: ..."}` from the first search on. Expected first pick ~45-75 min
   in (the lead's first follow-up search, or search 101). A count at any time:
   `/home/USER/ai/deep-research/.venv/bin/python -I -c "import json; r=[json.loads(l) for l in open('/home/USER/ai/deep-research/logs/paid-route.jsonl') if '\"shop-7e-deep-p7d/s1\"' in l]; print(len(r), 'searches,', sum(x.get('select',{}).get('picked',False) for x in r), 'picked,', sum(a.get('outcome')=='sent' for x in r for a in x['actions']), 'sent')"`
6. After each run: `/home/USER/ai/deep-research/.venv/bin/python -I /home/USER/ai/deep-research/tools/paid_tracker.py` (read-only) and `/home/USER/ai/deep-research/.venv/bin/python -I -B /home/USER/ai/deep-research/staging/item7d/tools/relief_counts.py p7d p7dx p7ew p4s8` (the staged copy: it also reads shop-7e runs; checked 11-03 against 7e's recorded 6 / 6).

## Rollback (R)

With nothing live: for each of the four files `cp -p /home/USER/ai/deep-research/tools/<f>.before-7d /home/USER/ai/deep-research/tools/<f>.new-7d && mv -f /home/USER/ai/deep-research/tools/<f>.new-7d /home/USER/ai/deep-research/tools/<f>`;
unit from `/home/USER/ai/deep-research/tools/deep-research-bench.service.before-7d` + `systemctl --user daemon-reload`. LDR uses the old modules from its next start.
`~/.config/deep-research/paid-route-state.json` (+ .lock) can be deleted when no 7d run is live.

## Notes

- Month change: paid_budget's 10-31 bug (run counts cleared at the UTC month change) is still unfixed (planned after
  item 7). 7d ends long before 12-01 00:00 UTC (11-30 18:00 CST); do not let a 7d run cross it.
- The 7d state file is keyed by run id + the run file's `written` stamp, so a rerun of a question under the same run id
  starts its own state (paid-runs.json's count for that run id would still need the 10-31 rename trick for a rerun).
- Free S2 is untouched by `_select`; neither 7d profile has a free source.
