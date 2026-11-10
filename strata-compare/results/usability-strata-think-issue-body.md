### What happened

This is the same family as #537 / #1526 (a quoted `</think>`) and #2026 (a quoted `</tool_call>`, fixed in 0.1.43.1). The model quotes a tag while it thinks, and the server takes the quote for the real tag. #1526's rule (v0.1.42) treats a `</think>` written right after a quote or backtick, and followed by anything but a line break, as reasoning text. That rule misses a tag the model writes as Python source with escapes inside a fenced code block, which is common when an agent works on code that renders the chat template:

````
I will add this test:
```python
    self.assertIn("<think>\n\n</think>\n\n", prompt)
```
````

(`\n` here is the two characters of the escape.) The character before the quoted `</think>` is the `n` of `\n`, so `OutputParser` ends the reasoning there. What follows:

- **The answer:** the rest of the thinking comes back as answer text, including the model's real `</think>`.
- **The tool call:** the real call after the real `</think>` reads as quoted, because fence tracking restarts at the answer and the closing ``` of the quoted block opens a "fence".
- **The client:** it gets `finish_reason: "stop"`, part of the reasoning as the answer, and no tool call, so an agent ends the session.

**How often.** We ran one real task on Strata's own `serve/` code 9 times, across four agent harnesses, over both `/v1/chat/completions` and `/v1/responses`. The task was to make the config's `reasoning_effort` default apply to every API; it involves `"none"` and so the `<think>\n\n</think>` prompt. **All 9 sessions ended at this point.** Whether the task got solved depended only on whether the fix was complete by then (3 of 9 were not). 18 sessions on plain coding tasks never hit it.

**Parser-only reproduction** (from the repo root, no model needed):

```python
from serve.frontend import OutputParser
tools = [{"name": "read", "parameters": {"properties": {"path": {"type": "string"}}}}]
p = OutputParser(thinking=True, tools=tools)
text = ('I will add this test:\n```python\n    self.assertIn("<think>\\n\\n</think>\\n\\n", prompt)\n```\n'
        'Now read the file.\n</think>\n\n'
        '<tool_call>\n<function=read>\n<parameter=path>\nserve/x.py\n</parameter>\n</function>\n</tool_call>')
evs = p.feed(text) + p.finish()
print("tool calls:", [e.call.name for e in evs if e.kind == "tool_call"])
print("content:", repr("".join(e.text for e in evs if e.kind == "content")[:70]))
```

On v0.1.44.1 this prints `tool calls: []` and a content that starts with the rest of the quoted test (`'\\n\\n", prompt)\n```\nNow read the file.\n</think>\n\n<tool_call>...'`). Expected: `tool calls: ['read']` and an empty content.

**A fix we tested.** Inside a code fence (``` or ~~~) of the reasoning, a `</think>` is quoted text, the same way #804 / #1058 already treat `<tool_call>`. A fence the model never closes must not swallow the real end of the thinking, so the fix has a safeguard:

- From a fenced `</think>` on, the text is held until the fence closes. Then the held text was reasoning, and it is released and read again as reasoning.
- If the turn ends with the fence still open, the last `</think>` held is the end of the thinking.
- Only the reasoning / answer / tool-call split can change; the generated tokens do not. Streaming of the reasoning pauses only while a fenced tag waits for its fence to close.
- Inline code (an odd backtick count in the paragraph) is left out on purpose. Counting it misfired once in our data, on a real end of thinking after the model wrote "escape backticks with \`".

How we checked it:

- **Replay:** all 503 recorded tool-enabled turns from those sessions went through `OutputParser`, as shipped and patched. The patched parser recovers the **7** lost tool calls (one for each session that was cut mid-task) and gives the **same events for the other 496 turns**. Its events are the same whether the text arrives 1 character, 7 characters or all at once.
- **Unit tests:** five new tests, covering a fenced tag followed by a call, the hold ending when the fence closes, an unclosed fence with a real `</think>`, an unclosed fence with a quoted and then a real tag, and a turn cut inside an unclosed fence. The existing `serve.test_reasoning_tools` tests pass, and so does the full serve suite.
- **Server level:** 10 recorded agent requests (7 of them the turns that lost their call) went greedy through two servers on the same engine, one as shipped and one patched. The prompt's CPU share was off, which makes repeated runs identical. The raw generated text and the token counts were identical in all 10. The split differed in 3 requests, where the patched server returned the tool call and the shipped one returned none.
- **End to end:** the same real task, 4 more sessions on the patched server (two of the harnesses, 2 each). All 4 ran to the end and solved it (hidden tests and the full suite), with no lost or unparsed tool call.
- **The patch:** 54 lines in `serve/frontend.py` plus the tests. Happy to open it as a PR if that helps.

**Not covered:** in one session the model wrote `"<think>\n\n` and then a `</think>` with real line breaks around it, and ended its turn 12 tokens later. That looks like the model emitting its real end-of-thinking token, the #1814 / #2731 shape, which no parser rule can recover.

### Strata version, GPU, OS

Strata 0.1.44.1 server code. `serve/frontend.py` is unchanged from the tag, and main had no newer change to it on 2026-10-16. Our build carries local engine patches that do not touch `serve/`.

Qwen3.8-Flash-Next IQ3_S, RTX 5080 16 GB and RTX 4060 Ti 8 GB, Linux.

### Engine log

Not attached: the parser-only reproduction above shows the problem without a model.

Measured and drafted with Claude Code.
