# Draft issue: for Karl to post himself (nothing has been posted)

Found by reading the code, not reproduced. Before posting, check it against the newest tag; the lines below are v0.2.12,
and the fetch code is unchanged in v0.2.13.

---

**Title:** STRATA_ADAPT_FETCH stays on when a serve session switches itself to the asynchronous adaptive tier

**What**

`STRATA_ADAPT_FETCH=1|2` (24c6c2f68) is turned off, with a log line, under `--adapt-async`, because the asynchronous
tier picks its copies from a snapshot of the residency table and copies into slots without the per-expert `in_flight`
marks the admissions use. That check reads only the explicit option:

- `src/program/generate.cpp:12773-12777` (serve): `... : o.adapt_async ? "--adapt-async" : ...`
- `src/program/generate.cpp:20452-20455` (CLI): the same.

A serve session can still start the asynchronous tier by itself:

- `include/strata/core/adapt_async_default.hpp:41-55`: `adapt_async_self_decides()` returns true when neither
  `--adapt-async` nor `STRATA_ADAPT_ASYNC` is given (CUDA, serve, adaptive tier on, the expert arena, one GPU, no
  pipelined windows, no batch slots, no peer or helper tier, no adapt overlap). It does not look at STRATA_ADAPT_FETCH.
- `src/program/generate.cpp:13304`: `a_self = o.adapt_async_self && !o.adapt_async && ...`. The fetch check above passes,
  because `o.adapt_async` is false.
- `src/program/generate.cpp:19303`: `AdaptAsyncSelf::Action::ToAsync` creates the job thread partway through the session.
  `drive.d.fetch_admit` (set once, `:12786`) is not cleared there.

So with `STRATA_ADAPT_FETCH` set and `STRATA_ADAPT_ASYNC` unset, a one-GPU serve session can end up running admissions
and the asynchronous tier together. That is the combination the `--adapt-async` off-condition exists to prevent: an
admission can change a slot that the async tier's snapshot still counts as free, or as holding another expert.

**Expected**

`STRATA_ADAPT_FETCH` and the asynchronous tier never run in the same session.

**Possible fixes (any one)**

- Have `adapt_async_self_decides()` return false (with a reason) when `STRATA_ADAPT_FETCH > 0`, so the session stays on
  the blocking tier.
- Or add `o.adapt_async_self` to the fetch off-conditions in serve and the CLI.
- Or clear `fetch_admit` (and quiesce) before `ToAsync` starts the job thread.

The first keeps both opt-ins meaningful: someone who sets ADAPT_FETCH asked for it, and the self-choice is a default.

**Not affected:** `STRATA_ADAPT_ASYNC=0`, an explicit `--adapt-async`, or any setup the self-choice already refuses
(a layer split, a peer or helper tier, pipelined windows, batch slots).

Measured and drafted with Claude Code.
