#!/usr/bin/env python3
"""vendor_libs.py - 2026-10-14 (B, the user's request): local copies of the common browser libraries that model-written
pages load from CDNs, for the suite's screenshot renderer (future runs only; nothing re-rendered or re-rated).

For each package@version below: the tarball from registry.npmjs.org, checked against the registry's own dist.integrity
(sha512), extracted with tarfile's "data" filter into a fresh staging folder (tmp/r20/vendor-dl/<name>@<ver>/), then the
shipped build files copied to suite/vendor/npm/<name>/<ver>/ (sources, tests, type files, source maps and docs left out).
Plus the Tailwind v3 Play CDN script (not on npm): fetched from cdn.tailwindcss.com, SHA-256 recorded.
Writes suite/vendor/npm/INDEX.json (what the renderer maps from) and suite/vendor/npm/SOURCE.txt.  Three.js stays in
suite/vendor/three (0.160.0 / 0.128.0, vendored 2026-10-12); the newest Three.js is added there in the same layout.
Run:  suite/.venv/bin/python -I work/r20/vendor_libs.py"""
import base64
import fnmatch
import hashlib
import io
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
VEND = WS / "suite" / "vendor"
NPM = VEND / "npm"
STAGE = WS / "tmp" / "r20" / "vendor-dl"

# name: versions; cdnjs names; ESM entry (one path, or per major); the bare-URL script entry when package.json's
# fields point at a CommonJS file (per major or one path); "only": keep just these globs (big packages)
PKGS = {
    "p5": {"v": ["1.11.13", "2.3.4"], "cdnjs": ["p5.js"], "esm": {"2": "lib/p5.esm.min.js"}, "only": ["lib/*"]},
    "d3": {"v": ["7.9.0"], "cdnjs": ["d3"]},
    "gsap": {"v": ["3.15.0"], "cdnjs": ["gsap"], "esm": "index.js", "script": "dist/gsap.min.js"},
    "chart.js": {"v": ["2.9.4", "3.9.1", "4.5.1"], "cdnjs": ["Chart.js", "chart.js"]},
    "pixi.js": {"v": ["7.4.3", "8.22.0"], "cdnjs": ["pixi.js"], "esm": "dist/pixi.min.mjs", "script": "dist/pixi.min.js",
                "only": ["dist/pixi.js", "dist/pixi.min.js", "dist/pixi.mjs", "dist/pixi.min.mjs"]},
    "matter-js": {"v": ["0.20.0"], "cdnjs": ["matter-js"], "script": "build/matter.min.js"},
    "cannon-es": {"v": ["0.20.0"], "esm": "dist/cannon-es.js", "script": "dist/cannon-es.js"},
    "cannon": {"v": ["0.6.2"], "cdnjs": ["cannon.js"], "only": ["build/*"]},
    "tone": {"v": ["14.9.17", "15.1.22"], "cdnjs": ["tone"], "only": ["build/Tone.js"]},
    "lil-gui": {"v": ["0.21.0"], "cdnjs": ["lil-gui"], "esm": "dist/lil-gui.esm.min.js", "script": "dist/lil-gui.umd.min.js"},
    "dat.gui": {"v": ["0.7.9"], "cdnjs": ["dat-gui"], "esm": "build/dat.gui.module.js", "script": "build/dat.gui.min.js"},
    "simplex-noise": {"v": ["2.4.0", "4.0.3"], "cdnjs": ["simplex-noise"], "esm": {"4": "dist/esm/simplex-noise.js"},
                      "script": {"4": "dist/esm/simplex-noise.js"}},
    "@tweenjs/tween.js": {"v": ["18.6.4", "25.0.0"], "cdnjs": ["tween.js"], "esm": "dist/tween.esm.js",
                          "script": "dist/tween.umd.js"},
    "animejs": {"v": ["3.2.2", "4.5.0"], "cdnjs": ["animejs"], "esm": {"3": "lib/anime.es.js", "4": "dist/bundles/anime.esm.min.js"},
                "script": {"3": "lib/anime.min.js"}, "only": ["lib/*", "dist/bundles/*"]},
    "phaser": {"v": ["3.90.0", "4.2.1"], "cdnjs": ["phaser"], "esm": "dist/phaser.esm.min.js", "script": "dist/phaser.min.js",
               "only": ["dist/phaser.js", "dist/phaser.min.js", "dist/phaser.esm.js", "dist/phaser.esm.min.js",
                        "dist/phaser-arcade-physics.min.js"]},
    "babylonjs": {"v": ["9.30.0"], "cdnjs": ["babylonjs"], "only": ["babylon.js"]},
    "plotly.js-dist-min": {"v": ["2.35.3", "4.1.2"]},
    "jquery": {"v": ["3.7.1", "4.0.0"], "cdnjs": ["jquery"], "script": "dist/jquery.min.js", "only": ["dist/*"]},
    "react": {"v": ["18.3.1"], "cdnjs": ["react"], "script": "umd/react.production.min.js", "only": ["umd/*"]},
    "react-dom": {"v": ["18.3.1"], "cdnjs": ["react-dom"], "script": "umd/react-dom.production.min.js", "only": ["umd/*"]},
    "@babel/standalone": {"v": ["7.29.10"], "cdnjs": ["babel-standalone"], "script": "babel.min.js"},
    "vue": {"v": ["2.7.16", "3.5.44"], "cdnjs": ["vue"], "esm": {"3": "dist/vue.esm-browser.prod.js", "2": "dist/vue.esm.browser.min.js"},
            "only": ["dist/*"]},
    "alpinejs": {"v": ["3.17.4"], "cdnjs": ["alpinejs"], "esm": "dist/module.esm.js"},
    "@tailwindcss/browser": {"v": ["4.3.3"]},
    "@fortawesome/fontawesome-free": {"v": ["6.7.2"], "cdnjs": ["font-awesome"], "only": ["css/*", "webfonts/*", "js/*"]},
    "font-awesome": {"v": ["4.7.0"], "cdnjs": ["font-awesome"], "only": ["css/*", "fonts/*"]},
    "howler": {"v": ["2.2.4"], "cdnjs": ["howler"], "script": "dist/howler.min.js"},
    "stats.js": {"v": ["0.17.0"], "cdnjs": ["stats.js"]},
    "konva": {"v": ["9.3.22", "10.8.0"], "cdnjs": ["konva"], "script": "konva.min.js", "only": ["konva.js", "konva.min.js"]},
    "fabric": {"v": ["5.5.2", "6.9.1"], "cdnjs": ["fabric.js"], "script": {"5": "dist/fabric.min.js", "6": "dist/index.min.js"},
               "esm": {"6": "dist/index.min.mjs"}, "only": ["dist/fabric.js", "dist/fabric.min.js", "dist/index.js",
                                                            "dist/index.min.js", "dist/index.mjs", "dist/index.min.mjs"]},
}
THREE_NEW = "0.186.1"
TAILWIND3 = "3.4.17"

DROP_DIRS = {"src", "test", "tests", "__tests__", "docs", "doc", "types", "typings", "examples", "example", "demo",
             "demos", "benchmark", "benchmarks", "scripts", "node_modules", ".github", "editor", "manual", "utils",
             "svgs", "metadata", "sprites"}
DROP_GLOBS = ["*.map", "*.ts", "*.tsx", "*.md", "*.markdown", "*.max.js", "*.flow", "*.coffee", ".*", "*.yml",
              "*.yaml", "tsconfig*.json", "*.scss", "*.less", "*.svelte"]


def get(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "strata-compare-suite-vendor/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def keep(rel: str, only) -> bool:
    parts = rel.split("/")
    name = parts[-1]
    if name == "package.json" and len(parts) == 1:
        return True
    if len(parts) == 1 and name.upper().startswith(("LICENSE", "LICENCE", "COPYING")):
        return True
    if only:
        return any(fnmatch.fnmatch(rel, g) for g in only) and not rel.endswith(".map")
    if any(p in DROP_DIRS for p in parts[:-1]):
        return False
    return not any(fnmatch.fnmatch(name, g) for g in DROP_GLOBS)


def fetch_npm(name, ver, only, dest, three=False):
    meta = json.loads(get(f"https://registry.npmjs.org/{name.replace('/', '%2F')}/{ver}"))
    tb_url, integ = meta["dist"]["tarball"], meta["dist"]["integrity"]
    assert integ.startswith("sha512-"), integ
    st = STAGE / f"{name.replace('/', '__')}@{ver}"
    if st.exists():
        shutil.rmtree(st)
    st.mkdir(parents=True)
    blob = get(tb_url)
    got = "sha512-" + base64.b64encode(hashlib.sha512(blob).digest()).decode()
    if got != integ:
        raise SystemExit(f"{name}@{ver}: integrity mismatch ({got[:30]} vs {integ[:30]})")
    (st / "package.tgz").write_bytes(blob)
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        tf.extractall(st / "x", filter="data")
    roots = [p for p in (st / "x").iterdir() if p.is_dir()]
    assert len(roots) == 1, roots
    root = roots[0]
    if dest.exists():
        shutil.rmtree(dest)
    n = size = 0
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.is_symlink():
            continue
        rel = f.relative_to(root).as_posix()
        ok = (rel.startswith(("build/", "examples/jsm/")) or rel in ("package.json", "LICENSE")) if three else keep(rel, only)
        if three and ok and fnmatch.fnmatch(rel, "*.map"):
            ok = False
        if ok:
            t = dest / rel
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, t)
            n += 1
            size += f.stat().st_size
    pj = json.loads((root / "package.json").read_text(encoding="utf-8"))
    shutil.rmtree(st / "x")
    return {"tarball": tb_url, "integrity": integ, "files": n, "bytes": size,
            "fields": {k: pj.get(k) for k in ("main", "module", "browser", "unpkg", "jsdelivr", "exports") if k in pj}}


def entry(fields, kind, dest):
    """The file a bare URL gets: kind 'script' (jsdelivr / unpkg defaults) or 'esm'."""
    order = ["jsdelivr", "unpkg", "browser", "main"] if kind == "script" else ["module", "browser", "main"]
    for k in order:
        v = fields.get(k)
        if isinstance(v, str):
            v = v.lstrip("./")
            for cand in (v, v + ".js", v + "/index.js"):
                if (dest / cand).is_file():
                    return cand
    return "index.js" if (dest / "index.js").is_file() else None


def main():
    NPM.mkdir(parents=True, exist_ok=True)
    STAGE.mkdir(parents=True, exist_ok=True)
    index = {"_note": "written by work/r20/vendor_libs.py; the renderer (msuite/render.py) maps CDN URLs to these files",
             "packages": {}, "cdnjs": {}}
    src_lines = []
    for name, spec in PKGS.items():
        rec = {"versions": {}}
        cdnjs = spec.get("cdnjs", [])
        for ver in spec["v"]:
            dest = NPM / name / ver
            info = fetch_npm(name, ver, spec.get("only"), dest)
            major = ver.split(".")[0] if not ver.startswith("0.") else "0." + ver.split(".")[1]
            pick = lambda x: x.get(major) if isinstance(x, dict) else x   # noqa: E731
            e_esm = pick(spec.get("esm"))
            e_scr = pick(spec.get("script")) or entry(info["fields"], "script", dest)
            for e in (e_esm, e_scr):
                if e and not (dest / e).is_file():
                    raise SystemExit(f"{name}@{ver}: entry {e} missing")
            rec["versions"][ver] = {"script": e_scr, "esm": e_esm, "files": info["files"], "bytes": info["bytes"]}
            src_lines.append(f"{name}@{ver}  {info['tarball']}  {info['integrity']}  ({info['files']} files kept, "
                             f"{info['bytes'] / 1e6:.2f} MB)")
            print(src_lines[-1], "| script:", rec["versions"][ver]["script"], "| esm:", e_esm, flush=True)
        index["packages"][name] = rec
        for c in cdnjs:
            index["cdnjs"].setdefault(c, [])
            index["cdnjs"][c].append(name)
    # the newest Three.js beside the two vendored ones (same layout: build/, examples/jsm/)
    info = fetch_npm("three", THREE_NEW, [], VEND / "three" / THREE_NEW, three=True)
    src_lines.append(f"three@{THREE_NEW}  {info['tarball']}  {info['integrity']}  (suite/vendor/three/{THREE_NEW}: "
                     f"build/ + examples/jsm/, {info['files']} files, {info['bytes'] / 1e6:.2f} MB)")
    print(src_lines[-1], flush=True)
    (VEND / "three" / "SOURCE.txt").write_text(
        (VEND / "three" / "SOURCE.txt").read_text().rstrip("\n") +
        f"\nthree-{THREE_NEW}.tgz added 2026-10-14 (npm integrity sha512 verified; build/ and examples/jsm/ kept).\n")
    # Tailwind v3 Play CDN (not an npm package): the script cdn.tailwindcss.com serves for this version
    tw = get(f"https://cdn.tailwindcss.com/{TAILWIND3}")
    assert tw[:200].lstrip().startswith((b"(()", b"!function", b"/*", b"\"use strict", b"var ", b"(function")), tw[:80]
    d = NPM / "_tailwind-play-cdn" / TAILWIND3
    d.mkdir(parents=True, exist_ok=True)
    (d / "tailwind.js").write_bytes(tw)
    h = hashlib.sha256(tw).hexdigest()
    index["tailwind_play_cdn"] = {"version": TAILWIND3, "file": f"_tailwind-play-cdn/{TAILWIND3}/tailwind.js", "sha256": h}
    src_lines.append(f"Tailwind Play CDN {TAILWIND3}  https://cdn.tailwindcss.com/{TAILWIND3}  sha256 {h} "
                     f"({len(tw) / 1e6:.2f} MB; not on npm: fetched once, hash recorded)")
    print(src_lines[-1], flush=True)
    (NPM / "INDEX.json").write_text(json.dumps(index, indent=1) + "\n")
    (NPM / "SOURCE.txt").write_text(
        "Fetched 2026-10-14 by work/r20/vendor_libs.py from registry.npmjs.org; every tarball checked against the "
        "registry's dist.integrity (sha512) before use; only the shipped build files kept (no sources, tests, types, "
        "source maps, docs). Each package's own LICENSE file is kept beside it.\n\n" + "\n".join(src_lines) + "\n")
    tot = sum(f.stat().st_size for f in NPM.rglob("*") if f.is_file())
    print(f"suite/vendor/npm: {tot / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
