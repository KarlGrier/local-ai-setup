# Proposal: stop Strata's chat cache parking research's one-off calls (2026-10-19, proposal only, not built)

## What happens now
Strata (C*18t) runs with `--chat-cache 16 --chat-cache-mib 12288`. When a request takes the session for another
conversation, the engine copies the current one (its checkpoints and the host K/V below them) into RAM ("parks" it)
so a later request can continue it; least recently used are dropped beyond 16 conversations or 12 GiB.

Data: the engine log since C*18t was served (10-16; 4,777 requests over 53 engine starts), matched request by request
to the research proxy's call log (3,337 matched by prompt and completion tokens; classes from the proxy).

| class (proxy) | parks | RAM copied | restored later |
|---|---|---|---|
| agent (lead / sub-agents) | 1,070 | 1,040 GiB | 870 (81 %) |
| extract (page summaries) | 1,417 | 321 GiB | 0 |
| compact (history compaction) | 95 | 82 GiB | 0 |
| report (report writing) | 71 | 78 GiB | 0 |
| verify (citation check) | 89 | 51 GiB | 0 |
| other | 83 | 52 GiB | 0 |
| not research (Jan, chat page, suite) | 185 | 138 GiB | 49 |

None of the one-off classes was ever continued; report/verify/compact prompts reused 0 tokens. The cache's high point
(12.0 GiB, the full budget) was all report (8.9) + verify (3.4) conversations. Each of the 13 memory-relief
restarts since 10-18 freed 11-14 GB (MemAvailable 20.1-22.0 -> 30.7-35.0), i.e. the chat cache.

## Options (replayed over the same requests: tools/chatcache_park_sim.py)
| option | parked during report stage (median / max) | agent restores missed (3 days) | needs |
|---|---|---|---|
| now (16 / 12 GiB) | 5.4 / 12.0 GiB | 15 (1.3 min re-read) | - |
| A. "don't park" flag on extract/compact/report/verify/other | 0.2 / 11.5 GiB | 0 | proxy + server + engine change |
| A + drop research's parked conversations when the report stage starts | 0.25 / 0.9 GiB | 0 | same, + an owner tag on parked entries |
| B. budget 6 GiB (`--chat-cache-mib 6144`) | 5.0 / 6.0 GiB | 16 | config only |
| B. budget 4 GiB | 3.4 / 4.0 GiB | 18 (1.7 min) | config only |
| A + 4 GiB | 0.2 / 3.6 GiB | 16 | both |

A alone leaves a tail (8 % of report-stage moments): the finished lead and sub-agent conversations stay parked (up to
11.5 GiB); they are never continued after the lead's answer, so dropping them at the report start removes it.

How A would work: the proxy already classifies every call; for the one-off classes it adds a request field (e.g.
`"strata_park": false`), the server passes it to the engine, and the engine drops that conversation instead of parking
it when the next request takes the session. For the tail, the first report call carries "drop parked research
conversations"; parked entries remember who parked them, so Jan's and the chat page's parked chats stay.
Jan, the chat page and the agent loop are unchanged.

## RAM saved
Measured on o03 (10-19, 12:43:59, citation check): MemAvailable 20.74 GiB; the chat cache held 11 parked conversations,
11.6 GiB - all of it would be free under A with the report-start drop (MemAvailable ~32 GiB there). It refilled from
0 to 11.6 GiB in about 6 minutes after a relief restart.
At the report-stage low point: typically ~5 GiB (the parked report/verify conversations), up to the whole 12 GiB
budget; with the report-start drop, everything except other clients' chats (< 1 GiB here). That is the margin the
relief restarts recover today (11-14 GB each).

## Outputs and speed
* Outputs: unchanged under A. Parking is a copy made after a request has finished; a conversation that is never
  continued gives the same tokens either way, and the replay found no research conversation of these classes that was
  continued. Under B, the few extra misses (3 in 3 days) re-read their prompt instead of restoring it; those requests
  could differ at rounding level.
* Speed: A saves the park copy (47 ms on average for conversations over 20K tokens; max 244 ms) and, more importantly,
  the relief restarts (~1 min each plus a cold engine; 13 in two days, at the old 22 GB trigger). Jan's parked chats
  are no longer pushed out by a research run, so continuing a Jan chat after research stays fast. B costs a little in
  re-reads (~0.4 min over 3 days at 4 GiB) and keeps fewer of Jan's long chats (a 100K-token chat parks at ~2.3 GiB).

## Recommendation
A with the report-start drop (it removes the dip at its source, changes no output and keeps Jan's chat cache as it
is). B (4-6 GiB) is the config-only fallback if the engine change is not wanted; it caps the dip but trims Jan's cache.
Either is a Strata change: not built, waiting for the user's OK (this round allows proposals only).
