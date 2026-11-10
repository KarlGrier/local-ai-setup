#!/usr/bin/env python3
"""r04_cut_probe.py TREE CONFIG - 2026-10-12, the user's "find what cut C*17.1's r04 answers": no model. The C*17.1
server (TREE/serve/server.py, the config's tokenizer) with a scripted engine in place of `strata --serve`, one OpenAI
chat request with the research tools (as the suite sends them). Each scenario scripts the generated token ids after the
prompt; the response shows what the server does with them:
  A  "... quoting `" then <|im_end|>                         (the model ends its turn right there)
  B  "... quoting `" then </tool_call> (248059) then <|im_end|> (the special token, then the turn's end)
  C  "... quoting `" then </tool_call> then more text then <|im_end|>
  D  "... quoting `" then the text "</tool_call>" spelled as ordinary tokens, then more text
r04's four answers all end exactly at "quoting `" with finish "stop"."""
import json
import sys
import urllib.request
from pathlib import Path

TREE, CFG = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text())
sys.path.insert(0, str(TREE / "tools"))
sys.path.insert(0, str(TREE))
sys.path.insert(0, str(TREE / "serve"))
import server as S  # noqa: E402
from serve.frontend import ChatTemplate  # noqa: E402
import strata_tokenizer as ST  # noqa: E402

tpath = Path(CFG["tokenizer"])
vocab = json.loads((tpath / "vocab.json").read_text(encoding="utf-8"))
tokens = [None] * len(vocab)
for t, i in vocab.items():
    tokens[i] = t
tok = ST.Tokenizer(tokens, (tpath / "merges.txt").read_text(encoding="utf-8").split("\n"),
                   json.loads((tpath / "token_type.json").read_text()))
END, CLOSE = vocab["<|im_end|>"], vocab["</tool_call>"]


def enc(s):
    return tok.encode(s)


HEAD = enc("Checking the release.\n</think>\n\nv0.1.43.1 is byte-identical except that a user message quoting `")
TAIL = enc("` in its text no longer ends the turn.\n\n```json\n{\"version\": \"0.1.43.1\"}\n```")
OPEN = vocab["<tool_call>"]
RHEAD = enc("Also note: answers byte-identical except the ")
SCEN = {"A": HEAD + [END],
        "B": HEAD + [CLOSE, END],
        "C": HEAD + [CLOSE] + TAIL + [END],
        "D": HEAD + [i for i in enc("</") + enc("tool_call>")] + TAIL + [END],
        "E": HEAD + [OPEN] + TAIL + [END],                  # <tool_call> in the answer, then text
        "F": HEAD + [OPEN, END],                            # <tool_call> in the answer, then the turn's end
        "G": RHEAD + [CLOSE] + enc(" stuff.\n</think>\n\nAnswer.") + [END],   # </tool_call> while reasoning
        "H": RHEAD + [OPEN] + enc(" stuff.\n</think>\n\nAnswer.") + [END]}    # <tool_call> while reasoning


class Scripted(S.MockEngine):
    def __init__(self):
        super().__init__(tok, "x", max_context=131072)
        self.seq = []

    def generate(self, ids, max_new, sampling, cancel, embeddings=None):
        yield from self.seq[:max_new]


TOOLS = [{"type": "function", "function": {"name": "web_search", "description": "search",
          "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
         {"type": "function", "function": {"name": "fetch_page", "description": "fetch",
          "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}}]
eng = Scripted()
svc = S.Service(eng, tok, ChatTemplate(tpath / "chat_template.jinja"), model_name="probe",
                sampling_defaults=S.sampling_defaults_from_config(CFG))
httpd = S.serve(svc, port=0)
try:
    for name, seq in SCEN.items():
        eng.seq = seq
        body = {"messages": [{"role": "user", "content": "What is Strata's latest release?"}], "tools": TOOLS,
                "max_tokens": 81920, "stream": False}
        req = urllib.request.Request(f"http://127.0.0.1:{httpd.server_address[1]}/v1/chat/completions",
                                     data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
        ch = resp["choices"][0]
        c = ch["message"].get("content") or ""
        rz = ch["message"].get("reasoning_content") or ch["message"].get("reasoning") or ""
        print(f"{name}: finish {ch['finish_reason']!r}, tool_calls {len(ch['message'].get('tool_calls') or [])}, "
              f"completion_tokens {resp['usage']['completion_tokens']} of {len(seq)} scripted, content tail {c[-70:]!r}, reasoning tail {rz[-40:]!r}")
finally:
    httpd.shutdown()
    httpd.server_close()
