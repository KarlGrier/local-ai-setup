#!/usr/bin/env python3
"""qwenpath.py - 2026-10-24 (the user): "Narrow the pause rule: only pause for changes in the code our served Qwen build
uses (the Qwen engine sources and the server paths P021m runs). DeepSeek-only changes (src/dsv41/, DeepSeek-only server
defaults, its build flags), installer, launcher, docs and test changes: raise the baseline automatically, log it, and
keep running."  Called by work/r22/tagcheck.sh; read-only (git diff/show, ninja -t, file reads).

  qwenpath.py classify BASE TAG [--report FILE]    line 1: "PAUSE <what>" or "RAISE <summary>" (or "ERROR <why>")
  qwenpath.py files                                 the served build's file set, for a look

The served build is worked out fresh on every call: the config run-strata.sh starts by default (P021m since 10-23) ->
  engine:  the build folder whose binary has the served engine's sha256 (strata-r22p021m/build) and the one that built
           the vision binary: every file its objects were compiled from (ninja -t deps, compile_commands.json), the
           inputs of the binary (ninja -t inputs) and what CMake read at configure (build.ninja's RERUN_CMAKE line)
  server:  the config's server.py and every module of the checkout it imports, directly or not (serve/, strata_control/,
           strata_tokenizer/ ...), plus serve/*.jinja (the fallback chat template)
A release pauses when, between BASE and TAG:
  - a file of the engine set changed (a CMake file only if a changed line is in a block our build configures: blocks
    under a condition that is false for our build - an option OFF in its CMakeCache, or a DeepSeek switch such as
    STRATA_BUILD_DSV41 - and comments, blank lines and the project() version line don't count), or
  - in a server module, a definition our server has (a function, method, class body, module-level name or import)
    changed - docstrings and comments don't count, and definitions named for DeepSeek (deepseek, ds4, dsv41, DS41_...)
    or that our server doesn't have are left out.
Everything else raises: DeepSeek files, tests, docs, installer/launcher/packaging, engine sources our build doesn't
compile, web UI files. If the engine's build folder can't be found, src/ include/ cmake/ third_party/ and the top
CMakeLists.txt pause as before 10-24 (the old rule) - conservative.
"""
import ast, copy, hashlib, json, os, re, subprocess, sys
from collections import Counter
from pathlib import Path

SC = Path("/home/USER/ai-speed-testing/strata-compare")
REPO = SC / "strata"
RUN_STRATA = SC / "run-strata.sh"
DS = re.compile(r"deepseek|dsv?4\d|ds4", re.I)
FALSE = {"", "0", "OFF", "NO", "FALSE", "N", "IGNORE", "NOTFOUND"}


def git(*a, ok_fail=False):
    r = subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True)
    if r.returncode and not ok_fail:
        raise RuntimeError(f"git {' '.join(a[:3])}: {r.stderr.strip()[:200]}")
    return r.stdout if r.returncode == 0 else None


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def served_config():
    m = re.search(r'^CFG=\$\{STRATA_CONFIG:-\$WS/(\S+?)\}', RUN_STRATA.read_text(), re.M)
    if not m:
        raise RuntimeError("no default CFG= line in run-strata.sh")
    p = SC / m.group(1)
    return p, json.loads(p.read_text())


def worktrees():
    roots = [REPO]
    for l in (git("worktree", "list", "--porcelain") or "").splitlines():
        if l.startswith("worktree "):
            roots.append(Path(l[9:]))
    return sorted(set(roots), key=lambda r: -len(str(r)))


def rel(path, roots, builds):
    p = os.path.normpath(path)
    if any(p == str(b) or p.startswith(str(b) + "/") for b in builds):
        return None                                      # generated in a build folder
    for r in roots:
        if p.startswith(str(r) + "/"):
            return p[len(str(r)) + 1:]
    return None


def find_build(exe):
    """The build folder (strata*/build*/) holding a binary with the served binary's sha256."""
    want, name = sha(exe), Path(exe).name
    for b in sorted(SC.glob("strata*/build*/")):
        for c in (b / name, b / "bin" / name):
            if c.is_file() and c.stat().st_size == Path(exe).stat().st_size and sha(c) == want:
                return b, c.relative_to(b).as_posix()
    return None, None


def engine_set(b, target, roots, builds):
    files, cmake = set(), set()
    out = subprocess.run(["ninja", "-C", str(b), "-t", "deps"], capture_output=True, text=True).stdout
    for l in out.splitlines():
        if l.startswith("    "):
            r = rel(l.strip() if l.strip().startswith("/") else str(b / l.strip()), roots, builds)
            if r: files.add(r)
    out = subprocess.run(["ninja", "-C", str(b), "-t", "inputs", target], capture_output=True, text=True).stdout
    for l in out.splitlines():
        r = rel(l if l.startswith("/") else str(b / l), roots, builds)
        if r: files.add(r)
    for e in json.loads((b / "compile_commands.json").read_text()) if (b / "compile_commands.json").exists() else []:
        r = rel(e["file"] if e["file"].startswith("/") else os.path.join(e["directory"], e["file"]), roots, builds)
        if r: files.add(r)
    m = re.search(r"^build build\.ninja[^:]*: RERUN_CMAKE \| (.*)$", (b / "build.ninja").read_text(), re.M)
    for t in (m.group(1).split() if m else []):          # what configure read: CMake scripts, and configure_file inputs
        r = rel(t, roots, builds)
        if r: (cmake if r.rsplit("/", 1)[-1] == "CMakeLists.txt" or r.endswith(".cmake") else files).add(r)
    cache = {}
    for l in (b / "CMakeCache.txt").read_text(errors="replace").splitlines():
        mm = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):(BOOL|STRING|UNINITIALIZED|INTERNAL)=(.*)$", l)
        if mm:
            cache[mm.group(1)] = mm.group(3)
    return files, cmake, cache


def py_closure(server):
    """The checkout's modules the server imports (at any depth, also inside functions), as repo-relative paths."""
    root = server.parents[1]
    seen, todo = set(), [server]
    def resolve(mod):
        parts = mod.split(".")
        for i in range(len(parts), 0, -1):
            base = root.joinpath(*parts[:i])
            for c in (base.with_suffix(".py"), base / "__init__.py"):
                if c.is_file():
                    out = [c]
                    for j in range(1, i):                # the packages' __init__ files run too
                        ini = root.joinpath(*parts[:j]) / "__init__.py"
                        if ini.is_file(): out.append(ini)
                    return out
        return []
    while todo:
        f = todo.pop()
        if f in seen: continue
        seen.add(f)
        try:
            tree = ast.parse(f.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        pkg = ".".join(f.relative_to(root).with_suffix("").parts[:-1])
        for n in ast.walk(tree):
            mods = []
            if isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                base = n.module or ""
                if n.level:
                    up = pkg.split(".")[: len(pkg.split(".")) - (n.level - 1)] if pkg else []
                    base = ".".join([*up, *([base] if base else [])])
                mods = [base] + [f"{base}.{a.name}" for a in n.names]
            for m in mods:
                if m:
                    todo += [c for c in resolve(m) if c not in seen]
    return root, sorted(p.relative_to(root).as_posix() for p in seen)


def served():
    cfg_path, cfg = served_config()
    roots = worktrees()
    builds = [b for r in roots for b in r.glob("build*/")]
    s = {"config": str(cfg_path.relative_to(SC)), "engine": set(), "cmake": {}, "caches": {}, "builds": [], "missing": []}
    for exe in [cfg["exe"]] + ([cfg["vision"]["exe"]] if cfg.get("vision", {}).get("exe") else []):
        b, target = find_build(exe)
        if not b:
            s["missing"].append(exe); continue
        files, cmake, cache = engine_set(b, target, roots, builds)
        key = str(b.relative_to(SC))
        s["builds"].append(key); s["caches"][key] = cache; s["engine"] |= files
        for c in cmake:
            s["cmake"].setdefault(c, []).append(key)
    root, mods = py_closure(Path(cfg["server"]))
    s["server_root"], s["server"] = str(root), mods
    s["assets"] = sorted(p.relative_to(root).as_posix() for p in (root / "serve").glob("*.jinja"))
    return s


# ---------- Python: definitions -------------------------------------------------------------------------------------
def _nodoc(body):
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def defs(src):
    """{key: dump} of a module's definitions; docstrings out (comments aren't in the AST)."""
    out = {}
    def put(k, v):
        out[k] = out[k] + "\n" + v if k in out else v
    def strip(n):
        n = copy.deepcopy(n)
        for x in ast.walk(n):
            if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                x.body = _nodoc(x.body) or [ast.Pass()]
        return ast.dump(n)
    def walk(body, pre):
        for n in _nodoc(body):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                put(pre + n.name, strip(n))
            elif isinstance(n, ast.ClassDef):
                head = copy.deepcopy(n)
                head.body = [b for b in _nodoc(n.body) if not isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
                put(pre + n.name, strip(head))
                walk(n.body, pre + n.name + ".")
            elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                ts = n.targets if isinstance(n, ast.Assign) else [n.target]
                put(pre + "=" + ",".join(ast.unparse(t) for t in ts), ast.dump(n))
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    put(pre + f"import {'.' * getattr(n, 'level', 0)}{getattr(n, 'module', None) or ''}:{a.name}"
                        f"{' as ' + a.asname if a.asname else ''}", ast.dump(a))
            else:
                put(pre + f"<{type(n).__name__}>", ast.dump(n))
    walk(ast.parse(src).body, "")
    return out


def py_changes(path, base, tag, ours):
    old = git("show", f"{base}:{path}", ok_fail=True) or ""
    new = git("show", f"{tag}:{path}", ok_fail=True) or ""
    try:
        o, n = defs(old), defs(new)
    except SyntaxError as e:
        return [("qwen", f"{path}: does not parse ({e.msg})")]
    res = []
    for k in sorted(set(o) | set(n)):
        if o.get(k) == n.get(k):
            continue
        if DS.search(k):
            res.append(("deepseek", k))
        elif re.match(r"^=\w*VERSION\w*$", k, re.I) and all(re.fullmatch(r"Assign\(targets=\[Name\(id='\w+', ctx=Store\(\)\)\], "
                                                                         r"value=Constant\(value='[^']*'\)\)", d or "")
                                                            for d in (o.get(k), n.get(k))):
            res.append(("version", k))                   # a version string bumped, like CMake's project() line
        elif k not in ours:
            res.append(("not-ours", k))
        else:
            res.append(("qwen", k))
    return res


# ---------- CMake: is a changed line in a block our build configures -----------------------------------------------
def cm_eval(cond, cache, options):
    toks = re.findall(r"\(|\)|\"[^\"]*\"|[^\s()]+", cond)
    pos = 0
    def atom():
        nonlocal pos
        t = toks[pos] if pos < len(toks) else ""; pos += 1
        if t == "(":
            v = orx()
            pos += 1
            return v
        if t.upper() == "NOT":
            v = atom()
            return None if v is None else not v
        nxt = toks[pos].upper() if pos < len(toks) else ""
        if nxt and nxt not in ("AND", "OR", ")"):        # STREQUAL, MATCHES, VERSION_*, DEFINED x, ...: unknown
            while pos < len(toks) and toks[pos].upper() not in ("AND", "OR", ")"):
                pos += 1
            return None
        name = re.sub(r"^\$\{(.*)\}$", r"\1", t.strip('"'))
        if name.upper() in ("ON", "YES", "TRUE", "Y", "1"): return True
        if name.upper() in FALSE: return False
        if DS.search(name) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name): return False   # our Qwen build: no DeepSeek
        if name in cache: return cache[name].upper() not in FALSE and not cache[name].upper().endswith("-NOTFOUND")
        if name in options: return options[name]
        return None
    def andx():
        nonlocal pos
        v = atom()
        while pos < len(toks) and toks[pos].upper() == "AND":
            pos += 1; w = atom()
            v = False if (v is False or w is False) else (True if (v and w) else None)
        return v
    def orx():
        nonlocal pos
        v = andx()
        while pos < len(toks) and toks[pos].upper() == "OR":
            pos += 1; w = andx()
            v = True if (v is True or w is True) else (False if (v is False and w is False) else None)
        return v
    try:
        return orx()
    except IndexError:
        return None


def cm_off_lines(text, cache):
    """Set of 1-based line numbers in blocks our build doesn't configure."""
    options = {m.group(1): m.group(2).upper() not in FALSE
               for m in re.finditer(r'^\s*option\s*\(\s*([A-Za-z_]\w*)\s+"[^"]*"\s+(\w+)\s*\)', text, re.M | re.I)}
    lines, off, stack = text.split("\n"), set(), []          # stack: [cond_off, any_true_before]
    i = 0
    while i < len(lines):
        m = re.match(r"^\s*(if|elseif|else|endif)\s*\((.*)$", lines[i], re.I)
        j, cond = i, ""
        if m:
            kw, rest = m.group(1).lower(), m.group(2)
            depth = 1 + rest.count("(") - rest.count(")")
            buf = [rest]
            while depth > 0 and j + 1 < len(lines):
                j += 1; buf.append(lines[j]); depth += lines[j].count("(") - lines[j].count(")")
            cond = " ".join(buf)
            cond = cond[: cond.rfind(")")] if ")" in cond else cond
            cond = re.sub(r"#.*", "", cond)
            if kw == "if":
                v = cm_eval(cond, cache, options); stack.append([v is False, v is True])
            elif kw == "elseif" and stack:
                v = cm_eval(cond, cache, options); prev = stack[-1][1]
                stack[-1] = [v is False or prev, prev or v is True]
            elif kw == "else" and stack:
                stack[-1] = [stack[-1][1], stack[-1][1]]
        if any(s[0] for s in stack):
            off.update(range(i + 1, j + 2))
        if m and m.group(1).lower() == "endif" and stack:
            stack.pop()
        i = j + 1
    return off


def cm_changes(path, base, tag, cache_list):
    diff = git("diff", "-U0", base, tag, "--", path) or ""
    texts = {s: git("show", f"{r}:{path}", ok_fail=True) or "" for s, r in (("-", base), ("+", tag))}
    offs = {s: [cm_off_lines(texts[s], c) for c in cache_list] for s in texts}
    on = []
    for h in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", diff, re.M):
        for s, start, cnt in (("-", h.group(1), h.group(2)), ("+", h.group(3), h.group(4))):
            st, n = int(start), int(cnt) if cnt is not None else 1
            lines = texts[s].split("\n")
            for ln in range(st, st + n):
                t = lines[ln - 1].strip().lstrip("\ufeff") if 0 < ln <= len(lines) else ""
                if not t or t.startswith("#") or re.match(r"^project\(strata VERSION [0-9.]+ LANGUAGES CXX\)$", t):
                    continue
                dm = re.match(r"^(option|set)\s*\(\s*([A-Za-z_]\w*)", t, re.I)
                if dm and DS.search(dm.group(2)):         # declaring a DeepSeek switch (option/set of a DS-named variable)
                    continue
                if all(ln in o for o in offs[s]):
                    continue
                on.append(f"{s}{ln}: {t[:80]}")
    return on


# ---------- classify ------------------------------------------------------------------------------------------------
def kind(p):
    low = p.lower(); name = low.rsplit("/", 1)[-1]
    if DS.search(p): return "DeepSeek"
    if "/test" in "/" + low or name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py" or "/fixtures/" in low:
        return "tests"
    if low.startswith("docs/") or name.endswith(".md") or name.startswith("readme") or name in ("license", "changelog"):
        return "docs"
    if low.startswith("serve/web/"): return "web UI"
    if low.startswith(("packaging/", "install", "docker", "apps/", "strata_cli/", "tools/", "scripts/", "integrations/")) \
            or name.endswith((".bat", ".ps1", ".sh", ".nix", ".lock")) or name.startswith(("setup", "dockerfile", "flake")):
        return "installer/launcher/packaging"
    if low.startswith(("src/", "include/", "cmake/", "third_party/", "sycl/", "metal/")) or name == "cmakelists.txt":
        return "engine sources our build doesn't compile"
    if low.startswith("strata_control/"): return "Control (not imported by our server)"
    if low.startswith("serve/"): return "server files our server doesn't load"
    return "other"


def classify(base, tag):
    s = served()
    root = Path(s["server_root"])
    ours = {m: set(defs((root / m).read_text())) for m in s["server"]}
    changed = []
    for l in (git("diff", "--name-status", "-M", base, tag) or "").splitlines():
        parts = l.split("\t")
        changed += parts[1:]
    changed = sorted(set(changed))
    qwen, notes, cats = [], [], Counter()
    for p in changed:
        if p in s["engine"] and p not in s["cmake"]:
            qwen.append(f"{p} (engine)"); continue
        if p in s["cmake"]:
            on = cm_changes(p, base, tag, [s["caches"][b] for b in s["cmake"][p]])
            if on:
                qwen.append(f"{p} (build: {'; '.join(on[:3])}{' ...' if len(on) > 3 else ''})")
            else:
                cats["build settings outside our build (DeepSeek switch, options OFF, version line)"] += 1
            continue
        if s["missing"] and (p.startswith(("src/", "include/", "cmake/", "third_party/")) or p == "CMakeLists.txt") \
                and not p.startswith("src/dsv41/"):
            qwen.append(f"{p} (engine set unknown: no build folder for {', '.join(s['missing'])})"); continue
        if p in s["server"]:
            res = py_changes(p, base, tag, ours[p])
            q = [k for c, k in res if c == "qwen"]
            if q:
                qwen.append(f"{p} (server: {', '.join(q[:6])}{' ...' if len(q) > 6 else ''})")
            for c, label in (("deepseek", "DeepSeek-only"), ("not-ours", "not in our server")):
                ks = [k for cc, k in res if cc == c]
                if ks:
                    notes.append(f"{p} {label}: {', '.join(ks[:6])}{' ...' if len(ks) > 6 else ''}")
            if not q:
                cats["server: DeepSeek-only, version string or not in our server"] += 1
            continue
        if p in s["assets"]:
            qwen.append(f"{p} (server: chat template)"); continue
        cats[kind(p)] += 1
    summary = ", ".join(f"{k} ({v})" for k, v in cats.most_common())
    rep = {"base": base, "tag": tag, "config": s["config"], "builds": s["builds"], "missing": s["missing"],
           "engine_files": len(s["engine"]), "cmake_files": len(s["cmake"]), "server_modules": s["server"],
           "changed": changed, "qwen": qwen, "notes": notes, "other": dict(cats)}
    return rep, summary


def main():
    a = sys.argv[1:]
    if a[:1] == ["files"]:
        s = served()
        print(json.dumps({"config": s["config"], "builds": s["builds"], "missing": s["missing"],
                          "engine": sorted(s["engine"]), "cmake": sorted(s["cmake"]), "server": s["server"],
                          "assets": s["assets"]}, indent=1))
        return
    if a[:1] != ["classify"] or len(a) < 3:
        print("usage: qwenpath.py classify BASE TAG [--report FILE] | files", file=sys.stderr); sys.exit(2)
    try:
        rep, summary = classify(a[1], a[2])
    except Exception as e:                               # tagcheck.sh falls back to the old rule
        print(f"ERROR {type(e).__name__}: {str(e)[:200]}"); return
    if "--report" in a:
        Path(a[a.index("--report") + 1]).write_text(json.dumps(rep, indent=1))
    if rep["qwen"]:
        print(f"PAUSE {len(rep['qwen'])} on our Qwen build's path: {'; '.join(rep['qwen'][:6])}"
              f"{' ...' if len(rep['qwen']) > 6 else ''}")
    else:
        extra = f"; {'; '.join(rep['notes'][:4])}" if rep["notes"] else ""
        print(f"RAISE changed: {summary or 'nothing'}{extra}")


if __name__ == "__main__":
    main()
