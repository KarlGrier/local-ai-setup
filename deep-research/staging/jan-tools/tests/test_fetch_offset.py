"""Offline: fetch_page's parts and "continue from" (no network: fetch and page_text are stubbed)."""
import importlib.util, sys
spec = importlib.util.spec_from_file_location("webmcp", "/home/USER/ai/deep-research/staging/jan-tools/web-mcp.py")
w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
w.log = lambda m: None
paras = [f"Paragraph {i}. " + ("word " * 150).strip() + "." for i in range(400)]
TEXT = "\n".join(paras)                      # ~300K chars
calls = []
w.fetch = lambda url: (calls.append(url), ("https://example.org/long", "text/html", b""))[1]
w.page_text = lambda final, ctype, body: ("Long page", TEXT)
out = w.t_fetch({"url": "https://example.org/long"})
assert out.startswith("Long page\nhttps://example.org/long\n(source: the page itself; characters 1-"), out[:200]
nxt = int(out.split("start=")[1].split(")")[0])
assert 12_500 <= nxt <= 25_000 and TEXT[nxt - 1] in "\n ." , nxt
body = out.split(")\n\n", 1)[1]
assert body == TEXT[:nxt]
# read on: no second load (cache), contiguous, and the parts cover the page exactly
got, start, parts = body, nxt, 1
while True:
    o = w.t_fetch({"url": "https://example.org/long", "start": start})
    parts += 1
    b = o.split(")\n\n", 1)[1]
    assert TEXT[start:start + len(b)] == b
    got += b
    if "to read on" not in o:
        assert "this part ends the page" in o
        break
    start = int(o.split("start=")[1].split(")")[0])
assert got == TEXT and len(calls) == 1, (len(got), len(TEXT), len(calls))
assert all(len(x) <= 30_000 for x in [body])
o = w.t_fetch({"url": "https://example.org/long", "start": len(TEXT) + 5})
assert "past the end" in o
o = w.t_fetch({"url": "https://example.org/long", "max_chars": 999999})
assert len(o.split(")\n\n", 1)[1]) <= 30_000
w.page_text = lambda final, ctype, body: ("Short", "just a short page")
o = w.t_fetch({"url": "https://example.org/short"})
assert o == "Short\nhttps://example.org/long\n(source: the page itself)\n\njust a short page", o
print(f"ok: {parts} parts of <= 25K cover the {len(TEXT):,}-char page exactly, one load, past-end and cap handled")
