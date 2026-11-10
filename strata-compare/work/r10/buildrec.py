#!/usr/bin/env python3
"""buildrec.py LABEL CONFIG.json [NOTE] — round 9: append one build record to results/r10/builds.md:
engine sha256 + its SOURCE line, config / shared-settings / server.py sha256, the source tree's git commit + tree +
patch list (from the server's checkout), and the assets' hashes (computed once into results/r10/assets.sha256)."""
import hashlib, json, subprocess, sys, time
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""): h.update(b)
    return h.hexdigest()
lab, cfgp = sys.argv[1], Path(sys.argv[2]).resolve(); note = " ".join(sys.argv[3:])
cfg = json.loads(cfgp.read_text())
exe = Path(cfg["exe"]); src = exe.parent / "SOURCE"
shared = cfgp.with_suffix(".shared-settings.json")
srv = Path(cfg.get("server", "")); repo = srv.parent.parent if srv.name else None
def git(*a):
    try: return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True).stdout.strip()
    except Exception as e: return f"? {e}"
assets = WS / f"results/r10/assets-{lab}.sha256"
if True:
    args = cfg["args"]; get = lambda k: args[args.index(k) + 1]
    files = []
    for d in (get("--pack"), get("--mtp")):
        files += sorted(p for p in Path(d).rglob("*") if p.is_file())   # symlinks followed (S0's MTP folder)
    files.append(Path(get("--expert-profile")))
    lines = [f"{sha(p)}  {p}" for p in files]
    for g in (get("--native"), get("--ple-gguf")):   # 83 GB: size + mtime here; full sha256 in results/model-sha256.txt (round 1)
        st = Path(g).stat(); lines.append(f"size={st.st_size} mtime={int(st.st_mtime)}  {g}")
    assets.write_text("\n".join(lines) + "\n")
ah = sha(assets)
rec = [f"### {lab} — {time.strftime('%Y-%m-%d %H:%M')}" + (f" — {note}" if note else ""),
       f"- config `{cfgp.relative_to(WS)}` sha256 `{sha(cfgp)[:16]}…`" + (f"; shared settings `{sha(shared)[:16]}…`" if shared.exists() else ""),
       f"- engine `{exe.relative_to(WS) if exe.is_relative_to(WS) else exe}` sha256 `{sha(exe)}`",
       f"- engine SOURCE: {src.read_text().strip() if src.exists() else '(none)'}",
       f"- server `{srv}` sha256 `{sha(srv)[:16]}…`" if srv.name else "- server: (none)",
       f"- source: {git('describe', '--tags', '--always')} HEAD {git('rev-parse', 'HEAD')[:12]} tree {git('rev-parse', 'HEAD^{tree}')[:12]} dirty={len(git('status', '--porcelain', '-uno').splitlines())}",
       "- patches on the tag: " + "; ".join(git("log", "--format=%h %s", f"{git('describe', '--tags', '--abbrev=0')}..HEAD").splitlines()[::-1])[:3000],
       f"- env {cfg.get('env')}", f"- args {' '.join(cfg['args'])}",
       f"- assets: {assets.relative_to(WS)} sha256 `{ah[:16]}…` (pack, MTP rt, expert profile; GGUF shards by size+mtime)", ""]
out = WS / "results/r10/builds.md"
if not out.exists(): out.write_text("# Round 9 build records (work/r10/buildrec.py)\n\n")
with open(out, "a") as f: f.write("\n".join(rec) + "\n")
print("\n".join(rec))
