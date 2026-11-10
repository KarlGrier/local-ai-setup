#!/usr/bin/env python3
"""e2_hook_equiv.py TREE CONFIG REQUEST.json OUT.json - #2028 follow-up (2026-10-12), no model: the exact request (REQUEST.json,
parsed from the reply draft's json block) through
TREE's serve/server.py over HTTP (127.0.0.1, a free port), with a recording engine in place of `strata --serve`. Records
what reaches the engine (prompt ids, max_new, the sampling dict, the request keys StrataEngine.sampling_keys would send)
and the response. Run once on the full hook's tree (r19-stockmeas43) and once on v0.1.43 + the cut-down diff: equal
records mean the engine cannot tell the two hooks apart for this request."""
import json
import sys
import urllib.request
from pathlib import Path

TREE, CFG, OUT = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text()), Path(sys.argv[4])
BODY = json.loads(Path(sys.argv[3]).read_text())
sys.path.insert(0, str(TREE))
sys.path.insert(0, str(TREE / "serve"))
import server as S  # noqa: E402
from serve.frontend import ChatTemplate  # noqa: E402
import strata_tokenizer as ST  # noqa: E402

OUTPUT = [17, 13, 7860, 28]          # what the recording engine "generates": 2. Sum =

tpath = Path(CFG["tokenizer"])
vocab = json.loads((tpath / "vocab.json").read_text(encoding="utf-8"))
tokens = [None] * len(vocab)
for t, i in vocab.items():
    tokens[i] = t
tok = ST.Tokenizer(tokens, (tpath / "merges.txt").read_text(encoding="utf-8").split("\n"),
                   json.loads((tpath / "token_type.json").read_text()))


class Recorder(S.MockEngine):
    def __init__(self):
        super().__init__(tok, "x", max_context=131072)
        self.calls = []

    def generate(self, ids, max_new, sampling, cancel, embeddings=None):
        self.calls.append({"ids": list(ids), "max_new": max_new,
                           "sampling": json.loads(json.dumps(sampling, sort_keys=True, default=repr)),
                           "engine_keys": S.StrataEngine.sampling_keys(sampling)})
        yield from OUTPUT[:max_new]


eng = Recorder()
svc = S.Service(eng, tok, ChatTemplate(tpath / "chat_template.jinja"),      # as main() builds it for --engine strata
                model_name=CFG.get("model_name", "qwen3.8-flash-next"),
                sampling_defaults=S.sampling_defaults_from_config(CFG))
httpd = S.serve(svc, port=0)
try:
    req = urllib.request.Request(f"http://127.0.0.1:{httpd.server_address[1]}/v1/chat/completions",
                                 data=json.dumps(BODY).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read())
finally:
    httpd.shutdown()
    httpd.server_close()
for k in ("id", "created", "system_fingerprint", "timings"):      # per-request values
    resp.pop(k, None)
OUT.write_text(json.dumps({"tree": str(TREE), "calls": eng.calls, "response": resp}, indent=1, sort_keys=True))
c = eng.calls[0] if eng.calls else {}
print(f"{TREE.name}: engine calls {len(eng.calls)}, prompt {len(c.get('ids', []))} ids, max_new {c.get('max_new')}, "
      f"keys {c.get('engine_keys')!r}, strata_ids {resp.get('strata_ids')}")
