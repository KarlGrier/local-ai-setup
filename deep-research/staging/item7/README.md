# Item 7 (extra search sources) - staged 10-28 (limits) and 10-29 (routing, cache, tracker). NOTHING is installed.

The live tools (~/ai/deep-research/tools/exa_fallback.py, tavily_fallback.py, search_fallback.py, web-mcp.py), the
installed LDR package and the live counters serve Jan's chat and Karl's research unchanged. Old README: README.md.before-1029.

## 10-28: Karl's paid-search limits (unchanged since)

Karl's rule (10-27): <= 30 paid searches per test run, <= 100 per run of his research (both providers together);
tests and research stop at 25 % of a provider's month left (kept for chat); every caller stops at 10 % left.

- tools/paid_budget.py (new): who is asking (PAID_SEARCH_KIND / the client name / run/paid-run.json for LDR), run caps
  in ~/.config/deep-research/paid-runs.json, the month limits.
- tools/exa_fallback.py: tests/research stop at $7.50 of the $10 month, everyone at $9.00 (the old cap).
- tools/tavily_fallback.py: tests/research stop at 750 of 1,000, everyone at 900 (was 950).
- tools/search_fallback.py: unchanged copy (the chat chain; imports the two above).

## 10-29: routing, cache across runs, monthly tracker

One entry point for every search beside SearXNG: **route -> cache -> budget -> provider**.

| file | what |
|---|---|
| tools/search_route.py (new) | rule-based classifier (regex rules with weights, no model): academic / product / news / code / general, with the matched rules as the reason; loads the routing table; picks the profile |
| tools/paid-route.json (new) | the routing table: `enabled` (false), `profile`, `cache` (enabled false, dir, max_mb 64, empty_ttl_hours 24), `ttl_hours` per tag (news 6, product 24, code/general 168, academic 720), `profiles` |
| tools/paid_cache.py (new) | disk cache of paid answers, key = sha256(provider, normalised query, request params); TTL per tag; size cap (expired first, then least recently used, to 90 %); file-locked, atomic writes; stores only title/url/content/score/date |
| tools/s2_search.py (new) | Semantic Scholar Graph API (free, no key; 1.1 s between requests), for the academic tag |
| tools/paid_search.py (new) | the entry point `search(query, searxng_results, client="ldr")`: returns only results new to SearXNG's list; logs each decision to logs/paid-route.jsonl |
| tools/paid_tracker.py (new) | month table per provider / caller kind / run, JSON + text, `--write DIR`; read-only |
| tools/exa_fallback.py, tavily_fallback.py | + `last_status()` (thread-local: sent / off / refused: why / error: ...) for the route log; backups *.before-1029 |
| ldr/search_engine_searxng.py | patch 0005's hook now calls `paid_search.search` (with LDR_SEARCH_FALLBACK=1, as today); otherwise identical to the installed file (checked 10-29); backup *.before-1029 |

**Profiles** (paid-route.json): `fallback` = today's patch 0005 (every tag: Exa then Tavily when fewer than 5
results), used whenever routing is off; `types` = query-type routing (academic: S2 + SearXNG; product: Exa on every
search, Tavily if still < 5; news: Tavily, then Exa if < 5; code and general: today's fallback); `7a` / `7b` / `7c` =
item 7's parts (S2 / Tavily / Exa Lite on every search, no fallback). Which one: PAID_ROUTE_PROFILE, else `"route"` in
run/paid-run.json (LDR only, so a test run picks its part without restarting LDR), else the config's `profile` when
`enabled`, else `fallback`. Cache on/off the same way (PAID_SEARCH_CACHE=0/1, `"cache": true` in the run file, config).

**Log** (logs/paid-route.jsonl, one line per decision): client, kind, run, profile and where it came from, tag + why,
SearXNG's count, each source asked with step (free / paid / fallback), outcome (sent / cache hit / refused: ... /
error: ... / off) and new results, and `saved` for a hit. No key, header or result text.

**Tracker**: `python -I tools/paid_tracker.py [--month YYYY-MM] [--json] [--write DIR]` - per provider used / left vs
the 25 % and 10 % lines (Exa $7.50 / $9.00, Tavily 750 / 900; "provider said out of credit" when Exa closed the month),
per provider x kind sent / refused / errors / used / cache hits / saved, per run sent per provider vs cap 30 / 100,
paid-runs.json's own count, refusals, hits. Opens only the six files it names (never the key files).

### Design reading and deviations from the brief

1. **General fallback stays at < 5** (today's patch 0005), not the brief's "< 3": the brief also says "as today's
   fallback", and routing off must equal today. One edit in paid-route.json (`fallback_below`).
2. The fallback counts SearXNG + free + paid results so far (an academic query with 2 SearXNG + 10 S2 results asks no
   paid source). "paid" sources stop at the first that returns results.
3. **Cache is off by default too** (`cache.enabled` false), so installing changes nothing until switched. A provider
   without its key file stays dormant (no cache hits either). Empty answers are cached for at most 24 h; refusals and
   failures never. The key has no caller, so a hit serves chat, tests and research alike; a test run can therefore get
   more than 30 answer sets (30 sent + hits), as the brief says (hits do not count).
4. Logged: every decision while routing is on, and any search where a source was asked. Routing off with SearXNG
   >= 5 writes nothing (as today).
5. "The run log of paid_budget" read as paid-runs.json (per-run counts) plus the providers' logs, which carry kind and
   run per search; the route log gives the cache hits. Provider logs use local time, the counters UTC months (a few
   hours at the month edge can fall into the neighbour month in the per-kind table; "used" comes from the counter).
6. Semantic Scholar is a small own client, not LDR's engine (LDR_RESEARCH_S2 in Jan's runs stays as it is); profile
   `7a` is an alternative to lifting bench2's S2 refusal for part 7a.
7. The 10-27 draft's LDR mode (LDR_PAID_MODE=item7: an agent's first search / < 3 new results, LDR_PAID_PROVIDER,
   client "ldr:<id>") is replaced by the profiles: under paid_budget its client name would have counted LDR as chat
   (no run cap, 10 % line). The root-level exa_fallback.py, tavily_fallback.py, search_fallback.py and paid_policy.py
   in staging/item7/ are that superseded draft: **do not install them**.
8. Not built: 7d (Exa highlights for a page needs its own Exa contents request; it would go through
   `paid_search.paid_call`, which already does cache + budget) and 7e's questions (the product tag -> Exa is ready).
   The chat chain (search_fallback.py, web-mcp) is neither routed nor cached.

### Tests (offline: local mock server on 127.0.0.1, temp folders, fake key; non-local connections and DNS blocked)

`tests/run_all.sh` (nice 19, `python -I -B`) - all pass 10-29:
- test_paid_budget.py (10-28): run caps, thresholds, release on refusal, chain, no key in logs.
- test_route.py: 37 example queries, normalisation, the staged table + broken tables (-> routing and cache off),
  profile precedence, decisions per profile, TTLs.
- test_cache.py: miss / hit / normalised hit / params and provider in the key / empty answer / expiry / corrupt file /
  no keys or headers / size cap (expired first, then LRU).
- test_paid_search.py: routing off = today's fallback (dedupe, Exa then Tavily); routing on per tag; cache hits send
  nothing, spend nothing, do not count; run cap and month line refuse; refusals and failures not cached; 7c; no-run test
  refused; never raises; no keys; tracker agrees; the LDR hook compiles.
- test_tracker.py: synthetic counters/logs: thresholds, closed month, counter vs logs, kinds, runs, past month,
  missing files, the script under `python -I` (text, JSON, --write).
Each test checks that ~/.cache/deep-research/paid-search and logs/paid-route.jsonl were not created.

## Installing (later; all with backups *.before-item7, when no Jan job, LDR run or bench queue is live)

1. **Prerequisite (10-28, still not written):** tools/research-runner.py writes run/paid-run.json
   {"kind": "research", "run": <job id>} when a Jan research job starts LDR work and removes it at the end. Without it,
   Karl's research loses its paid fallback (a research caller without a run id is refused).
2. Copy the tools together: paid_budget.py, exa_fallback.py, tavily_fallback.py, search_route.py, paid-route.json
   (enabled and cache false), paid_cache.py, s2_search.py, paid_search.py, paid_tracker.py. web-mcp.py (Jan's chat)
   keeps the old modules until it restarts.
3. LDR hook: diff the installed web_search_engines/engines/search_engine_searxng.py against staged
   ldr/search_engine_searxng.py first - only patch 0005's block (~lines 691-710) may differ; if the installed file
   changed since 10-29, port that block instead of copying. Restart LDR. With routing and cache off it behaves as today
   (paid_search reads paid-route.json once per search).
4. bench2-queue.sh / run-ldr.sh, for an item 7 test run only (never edit a running script): start LDR with
   LDR_SEARCH_FALLBACK=1 and write run/paid-run.json {"kind": "test", "run": "<label>/<qid>", "route": "7b"} (or
   "types", "7a", "7c"; optional "cache": true).
5. Switches, in this order: cache on (saves credit, no other change) -> per-run routes for item 7 tests -> config
   `enabled` (routing for Karl's research) only after the item 7 sides are judged and Karl agrees.
6. Run paid_tracker.py after each item 7 run and before the month turns.
