"""Derive a Strata server config (the JSON setup.py writes) with changed engine args.
    mkcfg.py BASE.json OUT.json [--exe PATH] [--set --flag value]... [--add --flag [value]]... [--drop --flag]...
            [--env K=V]... [--log PATH] [--server PATH]
--set replaces the value of an existing flag (or appends flag+value), --drop removes a flag (and its value if the
next token is not a flag), --add appends a bare flag or flag+value."""
import json, sys
a = sys.argv[1:]
base, out, rest = a[0], a[1], a[2:]
cfg = json.load(open(base, encoding="utf-8-sig"))
args = list(cfg["args"])
def has_value(i):
    return i + 1 < len(args) and not args[i + 1].startswith("--")
i = 0
env = dict(cfg.get("env", {}))
while i < len(rest):
    op = rest[i]
    if op == "--exe": cfg["exe"] = rest[i + 1]; i += 2
    elif op == "--log": cfg["log"] = rest[i + 1]; i += 2
    elif op == "--server": cfg["server"] = rest[i + 1]; i += 2
    elif op == "--env": k, v = rest[i + 1].split("=", 1); env[k] = v; i += 2
    elif op == "--set":
        f, v = rest[i + 1], rest[i + 2]
        if f in args: args[args.index(f) + 1] = v
        else: args += [f, v]
        i += 3
    elif op == "--drop":
        f = rest[i + 1]
        if f in args:
            j = args.index(f); n = 2 if has_value(j) else 1; del args[j:j + n]
        i += 2
    elif op == "--add":
        f = rest[i + 1]
        if i + 2 < len(rest) and not rest[i + 2].startswith("--") and rest[i + 2] not in ("--set", "--drop", "--add", "--env", "--exe"):
            args += [f, rest[i + 2]]; i += 3
        else:
            args.append(f); i += 2
    else:
        sys.exit("unknown op " + op)
cfg["args"] = args
if env: cfg["env"] = env
json.dump(cfg, open(out, "w"), indent=1)
print(" ".join(args))
