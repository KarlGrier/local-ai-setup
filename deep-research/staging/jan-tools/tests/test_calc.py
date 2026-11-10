"""Offline tests of calc-mcp.py: results, units, %, errors and the hostile inputs (no network, no files)."""
import importlib.util, json, subprocess, sys
P = "/home/USER/ai/deep-research/staging/jan-tools/calc-mcp.py"
spec = importlib.util.spec_from_file_location("calc", P)
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)

def ok(expr, want):
    got = c.calculate(expr).split(" = ", 1)[1]
    assert got.startswith(want), f"{expr!r}: got {got!r}, want {want!r}"

def bad(expr, why=""):
    try:
        r = c.calculate(expr)
    except c.CalcError as e:
        assert why in str(e), f"{expr!r}: {e}"
        return
    raise AssertionError(f"{expr!r} should fail, got {r!r}")

ok("2 + 3 * 4", "14"); ok("(2 + 3) * 4", "20"); ok("2^3^2", "512"); ok("2**10", "1,024"); ok("-3^2", "-9")
ok("1/3", "0.3333333333"); ok("0.1 + 0.2", "0.3"); ok("1,357 * 2", "2,714"); ok("10 / 4", "2.5")
ok("sqrt(2)", "1.414213562"); ok("log(1000)", "3"); ok("log(8, 2)", "3"); ok("round(2.345, 2)", "2.35")
ok("max(3, 7, 5)", "7"); ok("pi", "3.14159265"); ok("ln(e)", "1")
ok("15% of 2804", "420.6"); ok("2804 + 15%", "3,224.6"); ok("2804 - 10%", "2,523.6"); ok("50%", "0.5")
ok("(2816 - 2804) / 2804 to %", "0.4279600571 %")
ok("75 GB / 11.4 MB", "6,578.947368"); ok("138 GB / 1.8 GB/s", "76.66666667 s")
ok("6000 MT/s * 8 B * 2 to GB/s", "96 GB/s"); ok("6000 MT/s * 8 B * 2", "96 GB/s")
ok("350 W * 24 h to kWh", "8.4 kWh"); ok("1 TB to GiB", "931.3225746 GiB"); ok("8 GB to MiB", "7,629.394531 MiB")
ok("1 Gbps to MB/s", "125 MB/s"); ok("2804 $ / 128 GB", "21.90625 $/GB"); ok("$2804 / 128 GB", "21.90625 $/GB")
ok("12 in to cm", "30.48 cm"); ok("90 min to h", "1.5 h"); ok("5.9 GB + 1357 * 11.4 MB", "21.3698 GB")
ok("100 tok / 0.7 s", "142.8571429 tok/s"); ok("960 GB/s * 0.8", "768 GB/s")
bad("1 GB + 1 s", "cannot add"); bad("1 / 0", "division by zero"); bad("2 kWh to GB", "cannot convert")
bad("9^9^9", "too large"); bad("10^400", "too large"); bad("1e308 * 1e10", "too large")
bad("__import__('os')", ""); bad("open('/etc/passwd')", ""); bad("().__class__", ""); bad("x" * 500, "longer")
bad("eval(1)", "unknown"); bad("2 +", "ends too early"); bad("((((" * 30 + "1" + "))))" * 30, "")
bad("sqrt(4 GB)", "plain number"); bad("2 ^ (1 GB)", "plain number")

# the server: the MCP handshake and a call, run the way Jan will run it (no network)
msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "calculate", "arguments": {"expression": "138 GB / 1.8 GB/s"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "calculate", "arguments": {"expression": "open('x')"}}}]
r = subprocess.run(["/usr/bin/unshare", "-rn", "/usr/bin/python3", "-I", P], input="\n".join(json.dumps(m) for m in msgs) + "\n",
                   capture_output=True, text=True, timeout=20)
out = [json.loads(l) for l in r.stdout.splitlines()]
assert [o["id"] for o in out] == [1, 2, 3, 4], (out, r.stderr)
assert out[1]["result"]["tools"][0]["name"] == "calculate"
assert out[2]["result"]["content"][0]["text"].split(" = ", 1)[1].startswith("76.66666667 s") and not out[2]["result"]["isError"]
assert out[3]["result"]["isError"]
# inside the sandbox: no network, no new files, no writes
probe = ("import socket,os,resource\n"
         "exec(open('/home/USER/ai/deep-research/staging/jan-tools/calc-mcp.py').read().split('def main')[0])\n"
         "sandbox()\n"
         "try:\n s=socket.socket(); s.settimeout(2); s.connect(('1.1.1.1',443)); print('NET')\nexcept OSError: print('no-net')\n"
         "try:\n open('/etc/hostname').read(); print('READ')\nexcept OSError: print('no-open')\n")
r = subprocess.run(["/usr/bin/unshare", "-rn", "/usr/bin/python3", "-I", "-c", probe], capture_output=True, text=True, timeout=20)
assert r.stdout.split() == ["no-net", "no-open"], (r.stdout, r.stderr[-500:])
print("ok: 40 results, 15 refusals, MCP handshake + calls under unshare -rn, no network and no file opens inside")
