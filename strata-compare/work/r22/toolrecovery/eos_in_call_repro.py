"""Generation stops (end-of-turn token) inside an open tool call's parameter value: what does each OutputParser return?
    python3 -I eos_repro.py /path/to/strata-checkout"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
from serve.frontend import OutputParser  # noqa: E402

S = {"type": "string"}
TOOLS = [{"name": "read", "parameters": {"type": "object", "properties": {"path": S}}},
         {"name": "write_file", "parameters": {"type": "object", "properties": {"path": S, "content": S}}}]
TEXT = ("I will write the test.\n\n<tool_call>\n<function=write_file>\n<parameter=path>\ntests/test_template.py\n</parameter>\n"
        "<parameter=content>\n\"\"\"Test the rendered turn.\"\"\"\n\nexpected = \"\"\"<|im_start|>\n"
        "I should open the example file before answering.")
for recover in (False, True):
    for stream in (False, True):
        for size in (None, 7):
            pieces = [TEXT] if size is None else [TEXT[i:i + size] for i in range(0, len(TEXT), size)]
            try:
                p = OutputParser(thinking=False, tools=TOOLS, stream_tools=stream, recover=recover, declared_only=True)
            except TypeError:
                p = OutputParser(thinking=False, tools=TOOLS, stream_tools=stream)
            evs = []
            for piece in pieces:
                evs += p.feed(piece)
            evs += p.finish("stop")
            kinds = sorted({e.kind for e in evs})
            calls = [(e.call.name, e.call.arguments) for e in evs if e.kind == "tool_call" and getattr(e, "call", None)]
            deltas = "".join(str(getattr(e, "text", "") or getattr(e, "arguments", "") or "") for e in evs if "delta" in e.kind or "arg" in e.kind)
            content = "".join(e.text for e in evs if e.kind == "content")
            ok = []
            for _, a in calls:
                try:
                    json.loads(a); ok.append(True)
                except Exception:
                    ok.append(False)
            print(f"recover={recover} stream_tools={stream} fed={'whole' if size is None else size}: kinds {kinds}; calls "
                  f"{[c[0] for c in calls]} json_ok {ok}; args {json.dumps([c[1][-80:] for c in calls])}; answer {json.dumps(content[-120:])}"
                  + (f"; streamed arg text {len(deltas)} chars" if deltas else ""))
