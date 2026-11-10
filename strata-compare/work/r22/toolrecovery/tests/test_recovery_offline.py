#!/usr/bin/env python3
"""test_recovery_offline.py - round 22 (10-29): v0.2.8's tool_call_recovery on our port, offline (no server, no GPU).

Feeds the port's OutputParser (strata-r22p028/serve/frontend.py, as the server builds it: declared_only=True, recover on)
with model texts, the way upstream's serve/test_tool_corpus.py does: whole, in pieces of 1, 3 and 7 characters, with
streaming of the arguments (stream_tools) off and on, and cut in two at every character (streaming on, as the server
runs it).

  (a) real calls - each must come out as exactly the calls listed, with the right arguments, in every feed mode; the
      streamed argument JSON must equal the final arguments; no call may be announced (tool_start) and then dropped.
      The forms recovery exists for (OutputParser's recover): <parameter=NAME> as the opener inside <tool_call>; JSON
      {"name", "arguments" | "parameters"} inside <tool_call> (also in a ```json fence, also with the arguments as a
      JSON string); a bare <function=NAME> at the start of a line outside code (with or without a stray </tool_call>);
      a second call in the same wrapper (also opened with <parameter=NAME>).  Plus 0.2.8's repairs that run whatever
      the switch says (a missing </function>, the #3441 loose opener), the template's own form as a control, and real
      calls whose arguments QUOTE the format (a test file, a format doc) - one call, the value exact.
  (b) text that only discusses or quotes calls - each must give NO call and NO announced call in every feed mode, and
      keep its text (content and reasoning equal the text written, whitespace runs collapsed).
  (c) limits by design (reported, not graded): the recovery forms written as the last thing inside the thinking are
      reasoning text, never calls (only the template's own form is rescued from the thinking, #804).

Every (b) failure and every (a) specimen is also run with recover=False: "cause: recovery" = the false call appears
only with recovery on; "cause: baseline" = the parser makes it with recovery off too (0.2.8's base rules).

    /home/USER/ai-speed-testing/strata-compare/.venv/bin/python -B \
        /home/USER/ai-speed-testing/strata-compare/work/r22/toolrecovery/tests/test_recovery_offline.py [--tree DIR] [-v]

Writes results/offline-<time>.json next to tests/ and prints the report.  Exit 0 when (a) and (b) all pass, else 1.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True          # never write __pycache__ into the port's worktree
HERE = Path(__file__).resolve().parents[1]
DEFAULT_TREE = Path("/home/USER/ai-speed-testing/strata-compare/strata-r22p028")


def tool(name, **props):
    return {"name": name, "parameters": {"type": "object", "properties": props}}


S, I, A = {"type": "string"}, {"type": "integer"}, {"type": "array"}
# the coding harness's tools (prompts/agentturn.json's six) and Jan's (web, calculator) in one request
TOOLS = [tool("read", path=S, offset=I, limit=I), tool("edit", path=S, old_string=S, new_string=S),
         tool("write", path=S, content=S), tool("bash", command=S, timeout_s=I), tool("grep", pattern=S, path=S),
         tool("glob", pattern=S), tool("web_search", query=S, max_results=I), tool("fetch_page", url=S, start=I),
         tool("calculate", expression=S), tool("todo_write", todos=A)]


def fn(name, **params):
    """<function=NAME> with its parameters, the template's own form (no wrapper)."""
    body = "".join(f"<parameter={k}>\n{v}\n</parameter>\n" for k, v in params.items())
    return f"<function={name}>\n{body}</function>"


def wrapped(name, **params):
    return f"<tool_call>\n{fn(name, **params)}\n</tool_call>"


EX = "EXAMPLE.txt"
JSON_EX = '{"name": "read", "arguments": {"path": "EXAMPLE.txt"}}'

# a pytest file about a tool-call parser (the kind the coding harness writes); TEST_THINK also tests a chat template
# with a <think> block, so a `</think>` sits at the start of a line inside a triple-quoted string
TEST_PLAIN = '''from toolparse import parse_calls

XML_CALL = """
<tool_call>
<function=read>
<parameter=path>
EXAMPLE.txt
</parameter>
</function>
</tool_call>"""

BARE_CALL = """
<function=read>
<parameter=path>
EXAMPLE.txt
</parameter>
</function>"""

JSON_CALL = '<tool_call>{"name": "read", "arguments": {"path": "EXAMPLE.txt"}}</tool_call>'


def test_xml_call():
    assert parse_calls(XML_CALL) == [("read", {"path": "EXAMPLE.txt"})]


def test_bare_and_json_calls():
    assert parse_calls(BARE_CALL) == parse_calls(JSON_CALL) == [("read", {"path": "EXAMPLE.txt"})]'''

TEST_THINK = '''from toolparse import split_turn

TURN = """<think>
I need the file first.
</think>

<tool_call>
<function=read>
<parameter=path>
EXAMPLE.txt
</parameter>
</function>
</tool_call>"""


def test_thinking_comes_before_the_call():
    reasoning, calls = split_turn(TURN)
    assert reasoning.strip() == "I need the file first."
    assert calls == [("read", {"path": "EXAMPLE.txt"})]'''

# a format doc whose closing tags stand on lines of their own (the real call's value)
DOC_CLOSERS = ("# Tool call format\n\nOpen with <tool_call>, then <function=NAME>, then one <parameter=NAME> per "
               "argument.\n\nThe closing tags, in order:\n\n</parameter>\n</function>\n</tool_call>\n\nNothing may follow "
               "the last one.")
DOC_JSON = ("# Two forms\n\nXML:\n\n" + wrapped("read", path=EX) + "\n\nJSON inside the wrapper:\n\n<tool_call>\n"
            + JSON_EX + "\n</tool_call>\n\nBare (no wrapper):\n\n" + fn("read", path=EX) + "\n")

SPECS: list[dict] = []


def add(group, name, answer="", reasoning=None, calls=(), content=None, why="", finish="stop", gated=True,
        want_reasoning=None):
    """reasoning None: a turn without thinking (the text is the answer).  Otherwise the model text is
    reasoning + "\\n</think>\\n\\n" + answer, or the reasoning alone when answer is None (the turn ends inside it)."""
    thinking = reasoning is not None
    if not thinking:
        text = answer
    elif answer is None:
        text = reasoning
    else:
        text = reasoning + "\n</think>\n\n" + answer
    SPECS.append(dict(group=group, name=name, text=text, thinking=thinking, calls=[tuple(c) for c in calls],
                      want_content=(answer or "") if content is None else content,
                      want_reasoning=(reasoning or "") if want_reasoning is None else want_reasoning, why=why,
                      finish=finish, gated=gated))


# ---- (a) real calls ---------------------------------------------------------------------------------------------
add("a", "template-form-control", "I will read it.\n\n" + wrapped("read", path="a.txt"), calls=[("read", {"path": "a.txt"})],
    content="I will read it.", why="the template's own form (control)", gated=False)
add("a", "template-form-in-thinking", None, reasoning="Plan: read the file.\n\n" + wrapped("read", path="a.txt"),
    calls=[("read", {"path": "a.txt"})], content="", want_reasoning="Plan: read the file.",
    why="#804 control: the turn ends inside the thinking on the call", gated=False)
add("a", "param-as-opener", "<tool_call>\n<parameter=read>\n<parameter=path>\na.txt\n</parameter>\n</function>\n</tool_call>",
    reasoning="Need the file.", calls=[("read", {"path": "a.txt"})], content="",
    why="recover: <parameter=NAME> as the opener (corpus 300dfba2)")
add("a", "json-in-wrapper", "Reading the file.\n\n<tool_call>\n" + '{"name": "read", "arguments": {"path": "a.txt"}}' + "\n</tool_call>",
    calls=[("read", {"path": "a.txt"})], content="Reading the file.", why="recover: JSON inside <tool_call> (corpus 5e847539)")
add("a", "json-parameters-key", '<tool_call>\n{"name": "read", "parameters": {"path": "a.txt", "limit": 20}}\n</tool_call>',
    reasoning="Read the first 20 lines.", calls=[("read", {"path": "a.txt", "limit": 20})], content="",
    why="recover: JSON with \"parameters\" instead of \"arguments\"")
add("a", "json-arguments-as-string",
    '<tool_call>\n{"name": "calculate", "arguments": "{\\"expression\\": \\"138 GB / 1.8 GB/s to min\\"}"}\n</tool_call>',
    calls=[("calculate", {"expression": "138 GB / 1.8 GB/s to min"})], content="",
    why="recover: JSON whose arguments are a JSON string (OpenAI's wire form)")
add("a", "json-in-fence-in-wrapper",
    '<tool_call>\n```json\n{"name": "web_search", "arguments": {"query": "latest stable linux kernel"}}\n```\n</tool_call>',
    reasoning="Search first.", calls=[("web_search", {"query": "latest stable linux kernel"})], content="",
    why="recover: #2037, the JSON call in a ```json fence inside the wrapper")
add("a", "bare-function-after-prose", "Let me check.\n\n" + fn("bash", command="ls -la"), calls=[("bash", {"command": "ls -la"})],
    content="Let me check.", why="recover: a bare <function=NAME> at the start of a line (corpus 395efd4c)")
add("a", "bare-function-after-thinking", fn("read", path="a.txt"), reasoning="I need a.txt.", calls=[("read", {"path": "a.txt"})],
    content="", why="recover: the bare form right after </think>")
add("a", "bare-function-stray-wrapper-close", fn("read", path="a.txt") + "\n</tool_call>", calls=[("read", {"path": "a.txt"})],
    content="", why="recover: bare call, then the wrapper's </tool_call> without its opener (dropped)")
add("a", "bare-function-typed-args", fn("read", path="a.txt", limit="20"), calls=[("read", {"path": "a.txt", "limit": 20})],
    content="", why="recover: bare call, an integer argument")
add("a", "bare-function-then-text", fn("read", path="a.txt") + "\nThen I will summarize it.",
    calls=[("read", {"path": "a.txt"})], content="Then I will summarize it.", why="recover: bare call followed by prose")
add("a", "two-bare-functions", fn("read", path="a.txt") + "\n" + fn("read", path="b.txt"),
    calls=[("read", {"path": "a.txt"}), ("read", {"path": "b.txt"})], content="", why="recover: two bare calls in a row")
add("a", "batch-in-one-wrapper", "<tool_call>\n" + fn("read", path="a.txt") + "\n" + fn("read", path="b.txt") + "\n</tool_call>",
    calls=[("read", {"path": "a.txt"}), ("read", {"path": "b.txt"})], content="",
    why="recover: a second call in the same wrapper (corpus 0912870b)")
add("a", "batch-second-param-opener", "<tool_call>\n" + fn("read", path="a.txt") +
    "\n<parameter=read>\n<parameter=path>\nb.txt\n</parameter>\n</function>\n</tool_call>",
    calls=[("read", {"path": "a.txt"}), ("read", {"path": "b.txt"})], content="",
    why="recover: batch whose second call opens with <parameter=NAME>")
add("a", "function-close-left-out", "<tool_call>\n<function=write>\n<parameter=path>\nout.txt\n</parameter>\n"
    "<parameter=content>\nhello\n</parameter>\n</tool_call>", calls=[("write", {"path": "out.txt", "content": "hello"})],
    content="", why="0.2.8 repair (not gated): no </function> (#4427)", gated=False)
add("a", "loose-opener", "<tool_call>\n<function:read>\n<parameter=path>\na.txt\n</parameter>\n</function>\n</tool_call>",
    calls=[("read", {"path": "a.txt"})], content="", why="#3441 (not gated): <function:NAME>", gated=False)
add("a", "write-test-file-quoting-calls", "Writing the test.\n\n" + wrapped("write", path="tests/test_toolparse.py", content=TEST_PLAIN),
    reasoning="The test needs sample tool calls as strings.",
    calls=[("write", {"path": "tests/test_toolparse.py", "content": TEST_PLAIN})], content="Writing the test.",
    why="a real write whose file holds an XML call, a bare <function= at a line start and a JSON call: one call, exact value")
add("a", "write-test-file-with-think-tags", wrapped("write", path="tests/test_template.py", content=TEST_THINK),
    reasoning="Write the template test.", calls=[("write", {"path": "tests/test_template.py", "content": TEST_THINK})],
    content="", why="a real write whose file holds a </think> line and a whole call")
add("a", "write-doc-with-all-forms", wrapped("write", path="docs/FORMS.md", content=DOC_JSON),
    calls=[("write", {"path": "docs/FORMS.md", "content": DOC_JSON})], content="",
    why="a real write whose file shows the XML, JSON-in-wrapper and bare forms on lines of their own")
add("a", "write-doc-listing-closers", wrapped("write", path="docs/CLOSE.md", content=DOC_CLOSERS),
    calls=[("write", {"path": "docs/CLOSE.md", "content": DOC_CLOSERS})], content="",
    why="a real write whose file lists </parameter> </function> </tool_call> on lines of their own (not gated)", gated=False)
add("a", "fenced-think-in-reasoning-then-call", wrapped("write", path="tests/test_template.py", content=TEST_THINK),
    reasoning="Draft of the test:\n```python\n" + TEST_THINK + "\n```\nThat covers it; write it now.",
    calls=[("write", {"path": "tests/test_template.py", "content": TEST_THINK})], content="",
    why="the usability round's lost calls: the test (with a </think> line) drafted in a fence in the thinking, then the "
        "real call (our think-fence rule)", gated=False)

# ---- (b) text that only discusses or quotes calls ---------------------------------------------------------------
add("b", "prose-inline-xml-call", "To read a file the model writes <tool_call><function=read><parameter=path>EXAMPLE.txt"
    "</parameter></function></tool_call> and the server runs the read tool.",
    why="a model explaining the format in a sentence")
add("b", "doc-unfenced-xml-call", "A tool call in this format looks like this:\n\n" + wrapped("read", path=EX) +
    "\n\nThe wrapper marks the call; the function tag names the tool.", reasoning="Explain the format with an example.",
    why="explaining the format, the example on lines of its own without a code fence")
add("b", "doc-unfenced-bare-function", "Inside the wrapper sits the function block:\n\n" + fn("read", path=EX) +
    "\n\nEach parameter has its own tag.", reasoning="Show the inner block.",
    why="explaining the format: the bare <function=...> block on lines of its own, no fence")
add("b", "prose-inline-json-in-wrapper", "Hermes-style models wrap JSON instead, for example <tool_call>" + JSON_EX +
    "</tool_call>, which the server turns into the same call.", why="explaining the JSON form in a sentence")
add("b", "doc-unfenced-json-in-wrapper", "The JSON form looks like this:\n\n<tool_call>\n"
    '{"name": "web_search", "arguments": {"query": "EXAMPLE QUERY"}}' + "\n</tool_call>\n\nThe name field picks the tool.",
    reasoning="Show the JSON form.", why="the JSON-in-wrapper form shown on lines of its own, no fence")
add("b", "quoted-drift-param-opener", "The model's broken output was:\n\n<tool_call>\n<parameter=read>\n<parameter=path>\n"
    "EXAMPLE.txt\n</parameter>\n</function>\n</tool_call>\n\nIt used the parameter tag where the function tag belongs.",
    reasoning="Describe the bug.", why="a bug report quoting a drifted call, no fence")
add("b", "fenced-xml-call", "Example:\n\n```xml\n" + wrapped("read", path=EX) + "\n```\n\nThat is the whole call.",
    reasoning="Give an example.", why="a markdown code block showing an example call")
add("b", "fenced-bare-function", "The inner block:\n\n```\n" + fn("read", path=EX) + "\n```", why="the bare form in a fence")
add("b", "tilde-fenced-xml-call", "Example:\n\n~~~\n" + wrapped("read", path=EX) + "\n~~~", why="a ~~~ fence")
add("b", "fenced-json-tool-calls", "In the OpenAI API a call comes back like this:\n\n```json\n{\n  \"tool_calls\": [\n    {\n"
    "      \"id\": \"call_1\",\n      \"type\": \"function\",\n      \"function\": {\"name\": \"read\", \"arguments\": "
    "\"{\\\"path\\\": \\\"EXAMPLE.txt\\\"}\"}\n    }\n  ]\n}\n```\n\nThe arguments are a JSON string.",
    reasoning="Explain OpenAI function calling.", why="a JSON example of function calling in a ```json block")
add("b", "unfenced-json-function-call", "A call object is " + JSON_EX + " - the client runs the tool.\n\nOr on its own line:\n\n"
    + JSON_EX + "\n\nEither way it is only an example.", why="a JSON example of function calling, no wrapper, no fence")
add("b", "fenced-json-in-wrapper", "```\n<tool_call>\n" + JSON_EX + "\n</tool_call>\n```", why="JSON-in-wrapper in a fence")
add("b", "inline-code-forms", "Write `<tool_call>" + JSON_EX + "</tool_call>` or `<function=read>` inside `<tool_call>`; "
    "a bare `<function=read>` also works.", why="inline code quoting calls")
add("b", "python-test-fenced", "Here is the test:\n\n```python\n" + TEST_PLAIN + "\n```\n\nRun it with pytest.",
    reasoning="Write the test in the answer.", why="a Python test in a fence holding <tool_call>, a line-start <function= and JSON")
add("b", "python-test-fenced-think-lines", "Here is the test:\n\n```python\n" + TEST_THINK + "\n```\n\nRun it with pytest.",
    reasoning="Write the template test in the answer.",
    why="a Python test in a fence whose string has a </think> line and a whole call (thinking turn)")
add("b", "python-test-fenced-think-lines-no-thinking", "Here is the test:\n\n```python\n" + TEST_THINK + "\n```\n\nRun it.",
    why="the same in a turn without thinking (control for the stray-</think> rule)")
add("b", "python-test-unfenced", "Here is the test file:\n\n" + TEST_PLAIN + "\n\nRun it with pytest.",
    reasoning="Paste the file.", why="the same test pasted as file content without a fence")
add("b", "nested-fence-doc", "Save this as docs/TOOLS.md:\n\n````markdown\n# Tool calls\n\nA call:\n\n```xml\n" +
    wrapped("read", path=EX) + "\n```\n\nThe JSON form:\n\n```json\n" + JSON_EX + "\n```\n````\n\nThat is the file.",
    reasoning="Give the doc as a markdown file.", why="a doc in a 4-backtick fence with inner ``` blocks")
add("b", "indented-code-block", "The format, indented as code:\n\n" + "\n".join("    " + x for x in wrapped("read", path=EX).split("\n"))
    + "\n\nIndentation makes it a code block in Markdown.", why="an indented (4-space) Markdown code block")
add("b", "indented-bare-function", "The block:\n\n" + "\n".join("    " + x for x in fn("read", path=EX).split("\n")) +
    "\n\nThat is all.", why="the bare form as an indented code block")
add("b", "format-doc-fenced", "# Tool calls\n\n## The XML form\n\n```xml\n" + wrapped("read", path=EX) + "\n```\n\n## The JSON form"
    "\n\n```json\n" + JSON_EX + "\n```\n\n## Closing tags\n\nEnd with `</parameter>`, `</function>` and `</tool_call>`.",
    reasoning="Write the doc.", why="a doc about the format with fenced examples")
add("b", "quote-previous-call-fenced", "My last call was:\n\n```\n" + wrapped("web_search", query="EXAMPLE PREV") +
    "\n```\n\nIt returned three results.", reasoning="Quote the call I made.", why="an answer quoting a previous call, fenced")
add("b", "quote-previous-call-unfenced", "My last call, word for word:\n\n" + wrapped("web_search", query="EXAMPLE PREV") +
    "\n\nIt returned three results.", reasoning="Quote the call I made.", why="an answer quoting a previous call, no fence")
add("b", "quote-previous-call-blockquote", "My last call:\n\n" + "\n".join("> " + x for x in wrapped("web_search", query="EXAMPLE PREV").split("\n"))
    + "\n\nIt returned three results.", why="an answer quoting a previous call as a > blockquote")
add("b", "quote-previous-call-json", "Last turn I sent:\n\n<tool_call>\n" + '{"name": "web_search", "arguments": {"query": "EXAMPLE PREV"}}'
    + "\n</tool_call>\n\nand got three results.", reasoning="Quote it.", why="quoting a previous call in the JSON form, no fence")
add("b", "reasoning-decides-not-text-after", "2 + 2 = 4.", reasoning="The user asks 2 + 2. I could call\n" +
    wrapped("calculate", expression="2 + 2") + "\nbut that is trivial, so I answer directly.",
    why="reasoning that writes a call out, then decides not to make it")
add("b", "reasoning-mid-sentence", "4", reasoning="A <tool_call><function=calculate><parameter=expression>2+2</parameter>"
    "</function></tool_call> would be overkill here.", why="reasoning mentioning a call mid-sentence")
add("b", "reasoning-json-not-made", "Paris.", reasoning="Option:\n<tool_call>\n" +
    '{"name": "web_search", "arguments": {"query": "EXAMPLE"}}' + "\n</tool_call>\nNo, I already know this.",
    why="reasoning drafting a JSON call it does not make")
add("b", "reasoning-bare-not-made", "Paris.", reasoning="I might write\n" + fn("web_search", query="EXAMPLE") +
    "\nbut a search is not needed.", why="reasoning drafting a bare call it does not make")
add("b", "reasoning-param-opener-not-made", "Paris.", reasoning="Draft:\n<tool_call>\n<parameter=web_search>\n<parameter=query>\n"
    "EXAMPLE\n</parameter>\n</function>\n</tool_call>\nNot needed.", why="reasoning drafting a drifted call it does not make")
add("b", "reasoning-fenced-test", "Here is my plan: one test file.", reasoning="Draft:\n```python\n" + TEST_THINK +
    "\n```\nThat covers it.", why="reasoning drafting the template test in a fence (think-fence rule)")
add("b", "reasoning-decided-not-call-last", "Paris is the capital of France.",
    reasoning="I decided not to search. For the record, the call would have been:\n" + wrapped("web_search", query="EXAMPLE"),
    why="EDGE: reasoning names a call it will not make, but the call is the last thing before </think> (#804 reads "
        "that as an act)")
add("b", "answer-shows-whole-turn-fenced", "A whole turn looks like this:\n\n```\n<think>\nI need the file.\n</think>\n\n" +
    wrapped("read", path=EX) + "\n```\n\nThe thinking comes first.", reasoning="Show a whole turn.",
    why="an answer showing a whole example turn (think block + call) in a fence")
add("b", "answer-explains-think-tags", "The model writes its reasoning between the tags:\n\n<think>\nstep one\n</think>\n\n"
    "and then answers after them.", reasoning="Explain the think tags.",
    why="an answer explaining the think tags with </think> on a line of its own, no call anywhere (thinking turn)")
add("b", "answer-fenced-think-block", "Like this:\n\n```\n<think>\nstep one\n</think>\nThe answer.\n```\n\nThat is all.",
    reasoning="Show the think block.", why="the same in a code fence, no call anywhere (thinking turn)")
add("b", "undeclared-name-unfenced", "Example:\n\n" + wrapped("get_weather", city="EXAMPLE") + "\n\nThat is the shape.",
    why="control: an unfenced example for a tool the request did not declare")

# ---- (c) limits by design ---------------------------------------------------------------------------------------
add("c", "json-call-last-in-thinking", None, reasoning="Search it.\n\n<tool_call>\n" +
    '{"name": "web_search", "arguments": {"query": "linux kernel"}}' + "\n</tool_call>", content="",
    why="JSON-in-wrapper as the last thing in the thinking: recovery runs only in the answer")
add("c", "bare-call-last-in-thinking", None, reasoning="Search it.\n\n" + fn("web_search", query="linux kernel"), content="",
    why="a bare call as the last thing in the thinking")
add("c", "param-opener-last-in-thinking", None, reasoning="Search it.\n\n<tool_call>\n<parameter=web_search>\n<parameter=query>\n"
    "linux kernel\n</parameter>\n</function>\n</tool_call>", content="", why="<parameter=NAME> opener as the last thing in the thinking")


# ---- running ----------------------------------------------------------------------------------------------------
def norm(s: str) -> str:
    return " ".join((s or "").split())


def cut(text, size):
    return [text[i:i + size] for i in range(0, len(text), size)]


def run(OutputParser, spec, pieces, stream_tools, recover):
    p = OutputParser(thinking=spec["thinking"], tools=TOOLS, stream_tools=stream_tools, recover=recover, declared_only=True)
    evs = []
    try:
        for piece in pieces:
            evs += p.feed(piece)
        evs += p.finish(spec["finish"])
    except Exception as e:      # noqa: BLE001 - recover off raises on a call it cannot parse (the request would fail)
        return {"error": f"{type(e).__name__}: {e}"[:200], "calls": [], "dangling": 0, "streamed_ok": True,
                "content": "", "reasoning": ""}
    calls = [(e.call.name, e.call.arguments) for e in evs if e.kind == "tool_call"]
    done = {e.call.id for e in evs if e.kind == "tool_call"}
    starts = [e.call.id for e in evs if e.kind == "tool_start"]
    streamed_ok = True
    if stream_tools:
        for e in (x for x in evs if x.kind == "tool_call"):
            s = "".join(x.text for x in evs if x.kind == "tool_args" and x.call is not None and x.call.id == e.call.id)
            if s:
                try:
                    streamed_ok &= json.loads(s) == e.call.arguments
                except ValueError:
                    streamed_ok = False
    return {"error": None, "calls": calls, "dangling": len([i for i in starts if i not in done]), "streamed_ok": streamed_ok,
            "content": "".join(e.text for e in evs if e.kind == "content"),
            "reasoning": "".join(e.text for e in evs if e.kind == "reasoning")}


def modes(text):
    for st in (False, True):
        yield f"whole st={int(st)}", [text], st
        for n in (1, 3, 7):
            yield f"pieces of {n} st={int(st)}", cut(text, n), st
    for at in range(1, len(text)):
        yield f"cut at {at} st=1", [text[:at], text[at:]], True


def problems(spec, r):
    """What is wrong with one run, by the specimen's group (empty: fine)."""
    out = []
    if r["error"]:
        return [f"parser error {r['error']}"]
    if spec["group"] == "a":
        if r["calls"] != spec["calls"]:
            out.append(f"WRONG CALLS: {call_diff(spec['calls'], r['calls'])}")
        if not r["streamed_ok"]:
            out.append("streamed arguments differ from the final ones")
    elif spec["group"] == "b":
        if r["calls"]:
            out.append(f"SPURIOUS CALL {short_calls(r['calls'])}")
    if r["dangling"]:
        out.append(f"{r['dangling']} call(s) announced (tool_start) and never finished")
    if spec["group"] in ("a", "b") and not out:
        if norm(r["content"]) != norm(spec["want_content"]):
            out.append("TEXT CHANGED (content): " + diff_hint(spec["want_content"], r["content"]))
        if norm(r["reasoning"]) != norm(spec["want_reasoning"]):
            out.append("TEXT CHANGED (reasoning): " + diff_hint(spec["want_reasoning"], r["reasoning"]))
    return out


def short_calls(calls):
    return "[" + ", ".join(f"{n}({json.dumps(a)[:70]})" for n, a in calls) + "]"


def call_diff(want, got):
    """Where the calls a run gave differ from the expected ones (first argument that differs)."""
    if len(want) != len(got):
        return f"{len(got)} call(s), expected {len(want)}"
    for (wn, wa), (gn, ga) in zip(want, got):
        if wn != gn:
            return f"tool {gn!r}, expected {wn!r}"
        for k in sorted(set(wa) | set(ga)):
            if wa.get(k) != ga.get(k):
                w, g = json.dumps(wa.get(k)), json.dumps(ga.get(k))
                i = 0
                while i < min(len(w), len(g)) and w[i] == g[i]:
                    i += 1
                return (f"{wn}.{k}: {len(g)} chars, expected {len(w)}; first difference at {i}: "
                        f"want ...{w[max(0, i - 30):i + 40]} got ...{g[max(0, i - 30):i + 40]}")
    return "same"


def diff_hint(want, got):
    w, g = norm(want), norm(got)
    i = 0
    while i < min(len(w), len(g)) and w[i] == g[i]:
        i += 1
    return f"first difference at char {i}: want {w[max(0, i - 25):i + 35]!r} got {g[max(0, i - 25):i + 35]!r}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tree", default=str(DEFAULT_TREE), help="the Strata tree whose serve/frontend.py is tested")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, a.tree)
    from serve.frontend import OutputParser     # noqa: E402

    t0 = time.time()
    rows = []
    for spec in SPECS:
        bad, n = {}, 0
        for label, pieces, st in modes(spec["text"]):
            n += 1
            pr = problems(spec, run(OutputParser, spec, pieces, st, recover=True))
            if pr:
                bad.setdefault("; ".join(pr), []).append(label)
        whole = run(OutputParser, spec, [spec["text"]], True, recover=True)
        off = run(OutputParser, spec, [spec["text"]], True, recover=False)
        off_pieces = run(OutputParser, spec, cut(spec["text"], 3), True, recover=False)
        rows.append(dict(group=spec["group"], name=spec["name"], why=spec["why"], gated=spec["gated"], modes=n,
                         bad_modes=sum(len(v) for v in bad.values()), problems={k: v[:6] + (["..."] if len(v) > 6 else [])
                                                                               for k, v in bad.items()},
                         calls_on=short_calls(whole["calls"]), calls_off=short_calls(off["calls"]),
                         n_on=len(whole["calls"]), n_off=len(off["calls"]),
                         calls_off_pieces=short_calls(off_pieces["calls"]), off_error=off["error"],
                         content_on=whole["content"][:400], reasoning_on=whole["reasoning"][:400]))
    secs = time.time() - t0

    def cause(r):
        if r["group"] != "b" or not any("SPURIOUS" in k or "announced" in k for k in r["problems"]):
            return ""
        if r["calls_off"] == "[]" and r["calls_off_pieces"] == "[]":
            return "cause: recovery"
        more = f"; recovery adds {r['n_on'] - r['n_off']} more" if r["n_on"] > r["n_off"] else ""
        return f"cause: baseline (recovery off: {r['n_off']} call(s){more})"

    def flags(r):
        f = [cause(r)] if cause(r) else []
        if 0 < r["bad_modes"] < r["modes"]:
            f.append(f"INCONSISTENT: the result depends on how the text is cut ({r['bad_modes']} of {r['modes']} modes fail)")
        return " - " + "; ".join(f) if f else ""

    print(f"tool_call_recovery offline check - {a.tree}/serve/frontend.py, {len(SPECS)} specimens, "
          f"{sum(r['modes'] for r in rows)} parser runs with recovery on (+ recovery-off runs), {secs:.1f} s\n")
    names = {"a": "(a) real calls - must come out with the right arguments",
             "b": "(b) text that discusses or quotes calls - must give no call and keep its text",
             "c": "(c) limits by design (recovery forms at the end of the thinking) - reported, not graded"}
    for g in "abc":
        print(names[g])
        for r in (x for x in rows if x["group"] == g):
            if g == "c":
                print(f"  info  {r['name']}: calls {r['calls_on']} (recovery off: {r['calls_off']}) - {r['why']}")
                continue
            ok = not r["bad_modes"]
            extra = ""
            if g == "a":
                extra = f" [recovery off: {r['calls_off'] if not r['off_error'] else 'ERROR ' + r['off_error'][:60]}]"
            print(f"  {'PASS' if ok else 'FAIL'}  {r['name']}{'' if r['gated'] else ' (not gated)'}: "
                  f"{r['modes'] - r['bad_modes']}/{r['modes']} modes ok{extra}" + ("" if ok else flags(r)))
            if not ok or a.verbose:
                print(f"        why: {r['why']}")
            for k, v in r["problems"].items():
                print(f"        {k}\n          in: {', '.join(v)}")
            if not ok and g == "b":
                print(f"        content as served (whole): {r['content_on'][:160]!r}")
        print()
    fa = [r for r in rows if r["group"] == "a" and r["bad_modes"]]
    fb = [r for r in rows if r["group"] == "b" and r["bad_modes"]]
    spur = [r for r in fb if any("SPURIOUS" in k or "announced" in k for k in r["problems"])]
    text_only = [r for r in fb if r not in spur]
    print(f"SUMMARY (a) {sum(1 for r in rows if r['group'] == 'a') - len(fa)}/{sum(1 for r in rows if r['group'] == 'a')} pass; "
          f"(b) {sum(1 for r in rows if r['group'] == 'b') - len(fb)}/{sum(1 for r in rows if r['group'] == 'b')} pass - "
          f"{len(spur)} with a false call ({sum(1 for r in spur if cause(r) == 'cause: recovery')} only with recovery on, "
          f"{sum(1 for r in spur if 'recovery adds' in cause(r))} where recovery adds calls to the baseline's), "
          f"{len(text_only)} with changed text only; "
          f"{sum(1 for r in rows if 0 < r['bad_modes'] < r['modes'])} inconsistent across feed modes")
    out = HERE / "results" / f"offline-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps({"tree": a.tree, "seconds": round(secs, 1), "rows": rows}, indent=1))
    print(f"results: {out}")
    return 0 if not fa and not fb else 1


if __name__ == "__main__":
    sys.exit(main())
