# Proposal: quick answers that stay quick and never wait behind a measurement run (2026-10-19, not built)

## What happened on 10-18 22:24 (logs and timings only)
* Nothing was ahead of it: the job started at once (22:24:39, first model call 1 s later), no measurement run was on,
  no other LDR job, and the research gate held none of its 104 calls.
* Searches were not the cause: 3.4 min of the 15.2 were between calls (search, fetch); two slow gaps of ~30 s.
* Thinking was normal (Strata's default, medium): 80K thinking characters against 64K of answer text.
* The cause: plain LDR's agent treated the open question as a full research - the lead plus 7 subtopic agents in turn
  (langgraph_agent.include_sub_research on, up to 50 cycles), 104 calls = 8.8 min of Strata time.
* Plus another client on Strata at the same time: 36 requests (two growing conversations, 10K->30K and 1.5K->55K
  tokens, ~2-3K new tokens a turn) took 3.9 min of Strata time - by their shape Jan's own model doing its own lookups
  with Jan's built-in web search (on then). Quick jobs do not yield to chats, so the two shared Strata.

## Can quick answers get stuck behind measurement runs? Yes
The runner starts no job while a measurement run holds LDR (research-runner.py: "a measurement owns LDR"), and with
the queue running day and night a quick answer could wait 2.5-3 h. Built today as the stopgap: research_quick says
"NOT STARTED: ... cannot start now" when a measurement run (or the night pause, or a job ahead) blocks it, withdraws the
job, and the model answers with web_search + fetch_page and says so. That changes nothing for measurement runs: they
already yield to any other use of Strata for 5 minutes (yield_minutes 5), holding between model calls with the research
clock paused (o01 medium was held 17.6 min this way), and a parked conversation is restored exactly.

## Proposal (measurement outputs unchanged)
1. A separate quick-answer LDR, started on demand for each quick answer and stopped after it:
   * baseline profile with the subtopic agents off and fewer cycles (LDR_LANGGRAPH_AGENT_INCLUDE_SUB_RESEARCH=false,
     LDR_LANGGRAPH_AGENT_MAX_ITERATIONS=12 - both in LDR's defaults, so the env values apply), aiming at 1-3 min;
   * its own data folder (no shared database, no library), SearXNG 8888 (never 8889/8890), port of its own;
   * its model calls through the proxy as the user's traffic: a running measurement then yields to it exactly as to a
     chat (held between calls, clock paused) - its research budget, steps and outputs as without the quick answer.
   * Cost: ~3 GB of RAM while it runs (LDR's RSS is 2.9 GB), ~10-20 s to start; nothing while idle.
2. Or, smaller: keep quick answers on the shared LDR but with the same two limits (set only when the runner starts LDR
   for a quick job; the queue's baseline arms start LDR without them, and bench2 refuses an LDR with them on, as for
   the fallback and Semantic Scholar). Quick answers stay quick; behind a measurement run they still fall back to
   web_search (the stopgap above).
Either changes quick answers only; phase 3's baseline runs never see these settings.
