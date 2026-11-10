#!/usr/bin/env python3
"""maya-ckpt_client.py BASE OUTDIR ENGINE_LOG [SLOTS] - PREPARED 10-25 for the Maya v1.1.28 head-to-head (not run yet).
work/ds41/tune/ckpt_client.py unchanged (Jan's request format, the same chats and follow-ups, its LINE / SLOTLINE regexes:
the engine's "prompt N tokens = R reused + X read in Z ms (...), G generated" line is the same text in maya-ds4,
ds4_main.cpp:1063-1070), except reasoning_effort: a JSON integer EFFORT (default 62) instead of "medium", set on the
body before both the local render and the request, so Maya (whose "medium" is 75) and Strata get the same prompt.
For a Maya arm:
  - ENGINE_LOG = the Maya config's "log", with STRATA_SERVER_LOG=0 in that config's env (else Maya's server copies its own
    "[maya] ..." lines into the same file and SLOTLINE counts slot notes twice);
  - pass SLOTS=1: Maya's engine pins the anchor on every new run of prompts whether or not slots are kept
    (ds4_main.cpp:927 `if (!continued) m.pin();`), so the expected checkpoints include the anchor, as with slots here;
  - "budget_hit" (two engine passes) never happens on Maya: its thinking budget closes inside one decode (think_budget,
    ds4_main.cpp:1009-1046) - a capped answer shows as one pass;
  - render_ok (the server's prompt_tokens == our local render with Strata's template) is the check that Maya's
    ds41_encoding renders the same tokens as Strata's template; if it is false the "target_read" numbers are approximate
    (not verified before the run).
"""
import os
import sys

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/tune")
import ckpt_client as C  # noqa: E402

EFFORT = int(os.environ.get("EFFORT", "62"))
_renderer = C.renderer


def renderer():
    render = _renderer()
    # ckpt_client's local Service never calls set_family("deepseek41"), so the Strata frontend's integer efforts are off
    # (frontend.py:146-160: _NUMERIC_EFFORT) and 62 would raise "unknown reasoning effort" here; switch them on (module
    # state of strata-v024/serve/frontend.py, imported by _renderer above; the effort words' table changes too, unused)
    import serve.frontend as F
    F.use_family("deepseek41")

    def render_with_effort(body):
        body["reasoning_effort"] = EFFORT   # (the same dict main() then sends with ask())
        return render(body)
    return render_with_effort


C.renderer = renderer

if __name__ == "__main__":
    C.main()
