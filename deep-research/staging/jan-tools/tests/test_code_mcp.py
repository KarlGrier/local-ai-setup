"""code-mcp.py over stdio with a tiny public repo (octocat/Hello-World): search, read, layout, refusals."""
import json, subprocess
P = "/home/USER/ai/deep-research/staging/jan-tools/code-mcp.py"
PY = "/home/USER/ai/deep-research/.venv/bin/python"
def call(i, name, args):
    return {"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": args}}
msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        call(3, "code_read", {"repo": "octocat/Hello-World"}),
        call(4, "code_search", {"repo": "octocat/Hello-World", "pattern": "Hello"}),
        call(5, "code_read", {"repo": "octocat/Hello-World", "path": "README", "start_line": 1, "end_line": 5}),
        call(6, "code_read", {"repo": "octocat/Hello-World", "path": "../../../etc/passwd"}),
        call(7, "code_read", {"repo": "octocat/Hello-World", "path": ".git/config"}),
        call(8, "code_search", {"repo": "not a repo; rm -rf /", "pattern": "x"})]
r = subprocess.run([PY, "-I", P], input="\n".join(json.dumps(m) for m in msgs) + "\n", capture_output=True, text=True, timeout=120)
out = {o["id"]: o for o in map(json.loads, r.stdout.splitlines())}
assert [t["name"] for t in out[2]["result"]["tools"]] == ["code_search", "code_read", "github"]
txt = lambda i: out[i]["result"]["content"][0]["text"]
print(txt(3)[:120].replace("\n", " | ")); print(txt(4)[:160].replace("\n", " | ")); print(txt(5)[:160].replace("\n", " | "))
assert "README" in txt(3) and "hit(s)" in txt(4) and "github.com/octocat/Hello-World/blob/" in txt(5)
for i in (6, 7, 8):
    assert out[i]["result"]["isError"], (i, txt(i))
    print(i, txt(i)[:100])
print("ok: 3 tools, layout/search/read work, path escape, .git and a bad repo name refused")
