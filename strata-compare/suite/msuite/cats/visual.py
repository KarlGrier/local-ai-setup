"""Visual tests, judged by you: pelican on a bicycle (SVG), a voxel scene (Three.js), balls in a spinning heptagon,
a playable Tetris, plus one unpublished variant of each.  Answers are rendered in headless Chromium (render.py):
console errors recorded, screenshots saved; the blind comparison page shows two labels side by side."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from ..common import ITEMS, read_json, write_json
from .. import render

DIR = ITEMS / "visual"
FORMAT = {"svg": "\n\nReply with the complete SVG in one fenced ```svg code block.",
          "html": "\n\nReply with the complete file in one fenced ```html code block."}
FENCE = re.compile(r"```[ \t]*([A-Za-z0-9_+.-]*)[^\n]*\n(.*?)(?:```|\Z)", re.S)


def load() -> list[dict]:
    data = read_json(DIR / "items.json")
    out = []
    for i in data["items"]:
        prompt = i["prompt"].replace("{three_note}", data["three_note"]) + FORMAT[i["kind"]]
        out.append({"id": f"visual/{i['id']}", "category": "visual", "kind": i["kind"], "prompt": prompt,
                    "shots": i.get("shots", [1.0]), "game": i.get("game", False), "pair": i["pair"],
                    "variant": i.get("variant", False)})
    return out


def extract(text: str, kind: str):
    text = text or ""
    blocks = [(lang.lower(), body) for lang, body in FENCE.findall(text)]
    if kind == "svg":
        cands = [b for lang, b in blocks if lang in ("svg", "xml", "html", "") and "<svg" in b]
        src = cands[-1] if cands else text
        m = re.search(r"<svg\b.*</svg>", src, re.S | re.I)
        return m.group(0) if m else None
    cands = [b for lang, b in blocks if lang in ("html", "htm", "") and re.search(r"<html|<!doctype|<body|<canvas|<script", b, re.I)]
    if cands:
        return cands[-1].strip("\n")
    m = re.search(r"(<!doctype html.*</html>|<html\b.*</html>)", text, re.S | re.I)
    return m.group(0) if m else None


def grade(item: dict, rec: dict) -> dict:
    src = extract((rec.get("response") or {}).get("content"), item["kind"])
    return {"score": None, "solved": None,
            "detail": ("extracted %s (%d chars)" % (item["kind"].upper(), len(src))) if src else
                      f"no {item['kind'].upper()} found in the answer"}


def render_answer(chrome, item: dict, rec: dict, out_dir: Path) -> dict:
    """Write the page (and the raw answer file) into out_dir and render it; returns the render log."""
    out_dir.mkdir(parents=True, exist_ok=True)
    src = extract((rec.get("response") or {}).get("content"), item["kind"])
    if src is None:
        info = {"ok": False, "error": "nothing to render (no code block found)", "shots": []}
        write_json(out_dir / "render.json", info)
        return info
    site = out_dir / "site"
    if site.exists():
        shutil.rmtree(site)
    site.mkdir()
    if item["kind"] == "svg":
        (site / "image.svg").write_text(src, encoding="utf-8")
        (site / "index.html").write_text(render.svg_wrapper(), encoding="utf-8")
        shutil.copy(site / "image.svg", out_dir / "answer.svg")
    else:
        (site / "index.html").write_text(src, encoding="utf-8")
        shutil.copy(site / "index.html", out_dir / "answer.html")
    log = render.render_page(chrome, site, "index.html", item["shots"], out_dir, game=item["game"])
    info = {"ok": True, **log,
            # a request the sandbox refused shows up as a console error too: those are listed under "blocked", not
            # counted as the page's errors
            "console_errors": len([c for c in log["console"] if "ERR_BLOCKED_BY_CLIENT" not in c]) + len(log["exceptions"]),
            "animated": any(s.get("changed") for s in log["shots"][: len(item["shots"])]) if len(item["shots"]) > 1 else None,
            "changed_after_keys": (any(s.get("changed") for s in log["shots"][len(item["shots"]):]) if item["game"] else None)}
    write_json(out_dir / "render.json", info)
    return info


SAMPLE_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 120"><circle cx="50" cy="90" r="25" fill="none" '
              'stroke="#333" stroke-width="4"/><circle cx="150" cy="90" r="25" fill="none" stroke="#333" '
              'stroke-width="4"/><ellipse cx="100" cy="50" rx="30" ry="18" fill="#eee" stroke="#999"/></svg>')
SAMPLE_GAME = """<!doctype html><html><body style="margin:0;background:#222"><canvas id=c width=300 height=600></canvas>
<script>const g=document.getElementById('c').getContext('2d');let x=4,y=0;
document.addEventListener('keydown',e=>{if(e.key==='ArrowLeft')x--;if(e.key==='ArrowRight')x++;if(e.key===' ')y=19;draw();});
function draw(){g.fillStyle='#222';g.fillRect(0,0,300,600);g.fillStyle='#0cf';g.fillRect(x*30,y*30,30,30);}
draw();setInterval(()=>{y=(y+1)%20;draw();},500);</script></body></html>"""


def selftest():
    out = []
    items = {i["id"]: i for i in load()}
    svg_item, game_item = items["visual/v01_pelican_bicycle"], items["visual/v07_tetris"]
    out.append(("visual: 8 items, 4 variants", len(items) == 8 and sum(i["variant"] for i in items.values()) == 4, ""))
    e1 = extract("Here:\n```svg\n" + SAMPLE_SVG + "\n```", "svg")
    e2 = extract("```html\n" + SAMPLE_GAME + "\n```\nEnjoy!", "html")
    e3 = extract("Sorry, I cannot draw.", "svg")
    out.append(("visual: extraction (svg block, html block, nothing)", e1 == SAMPLE_SVG and e2 == SAMPLE_GAME and e3 is None, ""))
    from ..common import TMP
    tmp = TMP / "visual-selftest"
    if tmp.exists():
        shutil.rmtree(tmp)
    chrome, d = render.new_browser()
    try:
        a = render_answer(chrome, svg_item, {"response": {"content": "```svg\n" + SAMPLE_SVG + "\n```"}}, tmp / "svg")
        b = render_answer(chrome, game_item, {"response": {"content": "```html\n" + SAMPLE_GAME + "\n```"}}, tmp / "game")
        bad = render_answer(chrome, game_item, {"response": {"content": "```html\n<html><body><script>"
                                                             "undefinedFunction();</script></body></html>\n```"}},
                            tmp / "bad")
    finally:
        render.cleanup_browser(chrome, d)
    out.append(("visual: SVG renders without console errors", a["ok"] and a["console_errors"] == 0 and
                (tmp / "svg" / "shot1.png").stat().st_size > 1000, str(a.get("console"))[:200]))
    out.append(("visual: game page renders again after key presses", b["ok"] and b["changed_after_keys"] is True, str(b["shots"])[:300]))
    out.append(("visual: a broken page's exception is recorded", bad["console_errors"] >= 1, str(bad.get("exceptions"))[:200]))
    # 2026-10-14: CDN URLs of the common libraries map to the local copies (suite/vendor); unknown ones stay blocked
    want = {"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js": "three/0.160.0/build/three.module.js",
            "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js": "three/0.128.0/build/three.min.js",
            "https://unpkg.com/three@0.175.0/examples/jsm/controls/OrbitControls.js": "three/0.186.1/examples/jsm/controls/OrbitControls.js",
            "https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.9.0/p5.min.js": "npm/p5/1.11.13/lib/p5.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/ScrollTrigger.min.js": "npm/gsap/3.15.0/dist/ScrollTrigger.min.js",
            "https://d3js.org/d3.v7.min.js": "npm/d3/7.9.0/dist/d3.min.js",
            "https://code.jquery.com/jquery-3.6.0.min.js": "npm/jquery/3.7.1/dist/jquery.min.js",
            "https://cdn.tailwindcss.com": "npm/_tailwind-play-cdn/3.4.17/tailwind.js",
            "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css": "npm/font-awesome/4.7.0/css/font-awesome.min.css",
            "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/webfonts/fa-solid-900.woff2": "npm/@fortawesome/fontawesome-free/6.7.2/webfonts/fa-solid-900.woff2"}
    got = {u: render.vendor_lookup(u) for u in want}
    bad_map = [u for u, rel in want.items() if not got[u] or not got[u].get("file")
               or got[u]["file"] != render.VENDOR / rel]
    out.append(("visual: library CDN URLs map to the vendored files", not bad_map, str(bad_map)[:300]))
    rd = render.vendor_lookup("https://esm.sh/pixi.js@8")
    redirect_ok = bool(rd and rd.get("redirect", "").endswith("pixi.js@8.22.0/dist/pixi.min.mjs")
                       and (render.vendor_lookup(rd["redirect"]) or {}).get("file"))
    blocked_ok = all(render.vendor_lookup(u) is None for u in ("https://fonts.googleapis.com/css2?family=Inter",
                                                                "https://esm.sh/react@19", "https://example.com/x.js"))
    out.append(("visual: a bare ESM URL redirects to its entry file; unknown URLs stay blocked", redirect_ok and blocked_ok,
                f"{rd} blocked_ok={blocked_ok}"))
    shutil.rmtree(tmp, ignore_errors=True)
    return out
