"""Blind comparison page for the visual tests of two labels: results/blind-<A>-vs-<B>.html.

For each visual item (and each run both labels have) the two answers are shown side by side in a random order fixed
per item; the labels stay hidden until you click Reveal.  Your picks are kept in the browser (localStorage) and can be
copied out as JSON.  Screenshots come from the sandboxed render; "Open live" runs the model's page in a sandboxed
iframe in your own browser (which then loads Three.js from its CDN like any web page would).

Self-contained since 2026-10-13: the screenshots are embedded as WebP data URIs (shrink_shots.py, cached by the PNG's
SHA-256 in tmp/suite/blind-cache) and each live answer is embedded too, so the page works as a single file (a browser
reaching local files through the document portal sees only the HTML).  Served over http, "Open live" loads the
answer file itself; opened as a file, it uses the embedded copy."""
from __future__ import annotations

import base64
import hashlib
import html
import json
import subprocess
from pathlib import Path

from .common import RESULTS, TMP, label_dir, read_json
from .cats import visual

CACHE = TMP / "blind-cache"
SYS_PY = "/usr/bin/python3"                      # has Pillow (the venv does not)


def _embed(pngs: list[Path]) -> dict:
    """png path -> data URI: WebP from the cache (made for the missing ones in one call), else the PNG itself."""
    CACHE.mkdir(parents=True, exist_ok=True)
    webp = {p: CACHE / (hashlib.sha256(p.read_bytes()).hexdigest()[:32] + ".webp") for p in pngs}
    todo = [[str(p), str(w)] for p, w in webp.items() if not w.exists()]
    if todo:
        try:
            subprocess.run([SYS_PY, "-I", str(Path(__file__).with_name("shrink_shots.py")), json.dumps(todo)],
                           check=True, timeout=600, capture_output=True)
        except (OSError, subprocess.SubprocessError):
            pass                                   # no Pillow: the PNGs go in as they are
    out = {}
    for p, w in webp.items():
        f, mime = (w, "image/webp") if w.exists() else (p, "image/png")
        out[p] = f"data:{mime};base64," + base64.b64encode(f.read_bytes()).decode()
    return out


def _shots(label, item_name, run):
    d = label_dir(label) / "visual" / f"{item_name}.r{run}"
    info = read_json(d / "render.json") if (d / "render.json").exists() else {}
    files = [(d / s["file"], s) for s in info.get("shots", []) if (d / s["file"]).exists()]
    uris = _embed([p for p, _ in files])
    shots = [{"src": uris[p], "t": s.get("t"), "changed": s.get("changed")} for p, s in files]
    live = live_doc = None
    for f in ("answer.html", "answer.svg"):
        if (d / f).exists():
            live = f"{label}/visual/{item_name}.r{run}/{f}"
            live_doc = {"kind": f.split(".")[1], "text": (d / f).read_text(encoding="utf-8", errors="replace")}
    return {"shots": shots, "live": live, "live_doc": live_doc, "errors": info.get("console_errors"),
            "blocked": len(info.get("blocked") or []), "note": info.get("error") or ""}


def _research_side(label, qid, run):
    p = label_dir(label) / "answers" / "research" / f"{qid}.r{run}.json"
    if not p.exists():
        return {"text": "(no answer)", "calls": [], "checks": "", "missing": True}   # 11-01: no rating buttons on this side
    r = read_json(p)
    calls = []
    for c in r.get("tool_calls") or []:
        a = c.get("args") if isinstance(c.get("args"), dict) else {}
        calls.append(f"{c.get('tool')}: {a.get('query') or a.get('url') or ''}"[:160] + f" [{c.get('cache')}]")
    g = (read_json(label_dir(label) / "grades.json").get(f"research/{qid}#r{run}") or {}) \
        if (label_dir(label) / "grades.json").exists() else {}
    return {"text": (r.get("response") or {}).get("content") or "", "calls": calls,
            "checks": g.get("detail", ""), "score": g.get("score")}


def write_blind(a, b, runs=None):
    items = visual.load()
    ma = read_json(label_dir(a) / "meta.json")
    mb = read_json(label_dir(b) / "meta.json")
    nruns = min(ma.get("runs", 1), mb.get("runs", 1)) if runs is None else runs
    cards = []
    for it in items:
        name = it["id"].split("/")[1]
        for r in range(nruns):
            # 11-01: like the research cards, no card when neither label has the answer (the hard tier runs no visual
            # items, so its pages showed only empty "nothing rendered" cards)
            if not ((label_dir(a) / "visual" / f"{name}.r{r}").exists() or (label_dir(b) / "visual" / f"{name}.r{r}").exists()):
                continue
            sa, sb = _shots(a, name, r), _shots(b, name, r)
            flip = int(hashlib.sha256(f"{name}|{r}|{a}|{b}".encode()).hexdigest(), 16) % 2 == 1
            left, right = ((b, sb), (a, sa)) if flip else ((a, sa), (b, sb))
            cards.append({"id": f"{name}.r{r}", "title": name.split("_", 1)[1].replace("_", " "), "run": r,
                          "variant": it["variant"], "prompt": it["prompt"],
                          "L": {"tag": base64.b64encode(left[0].encode()).decode(), **left[1]},
                          "R": {"tag": base64.b64encode(right[0].encode()).decode(), **right[1]}})
    from .cats import research as R
    for it in R.load():
        qid = it["id"].split("/")[1]
        for r in range(nruns):
            if not ((label_dir(a) / "answers" / "research" / f"{qid}.r{r}.json").exists() or
                    (label_dir(b) / "answers" / "research" / f"{qid}.r{r}.json").exists()):
                continue
            flip = int(hashlib.sha256(f"{qid}|{r}|{a}|{b}".encode()).hexdigest(), 16) % 2 == 1
            (lt, ls), (rt, rs) = ((b, _research_side(b, qid, r)), (a, _research_side(a, qid, r))) if flip else \
                ((a, _research_side(a, qid, r)), (b, _research_side(b, qid, r)))
            cards.append({"kind": "research", "id": f"{qid}.r{r}", "qid": qid, "title": qid.split("_", 1)[1].replace("_", " "),
                          "run": r, "variant": False, "prompt": it["prompt"],
                          "L": {"tag": base64.b64encode(lt.encode()).decode(), **ls},
                          "R": {"tag": base64.b64encode(rt.encode()).decode(), **rs}})
    data = json.dumps({"cards": cards, "pair": f"{a}|{b}"})
    page = TEMPLATE.replace("__DATA__", data.replace("</", "<\\/")).replace("__TITLE__", "Blind comparison")
    p = RESULTS / f"blind-{a}-vs-{b}.html"
    p.write_text(page, encoding="utf-8")
    return p


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f6f6f4;--card:#fff;--ink:#1d1d1b;--muted:#6b6b66;--line:#ddd9d0;--accent:#2f5d8a;--pick:#e7efe4;--warn:#9a3b2a}
@media (prefers-color-scheme: dark){:root{--bg:#161615;--card:#20201e;--ink:#ecebe6;--muted:#a3a29b;--line:#3a3935;--accent:#8fb4dc;--pick:#25331f;--warn:#e08a74}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:20px 16px 8px;max-width:1400px;margin:0 auto}h1{font-size:22px;margin:0 0 6px}
header p{margin:4px 0;color:var(--muted);max-width:900px}
.bar{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}
button{font:inherit;padding:6px 12px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink);cursor:pointer}
button:hover{border-color:var(--accent)}button.on{background:var(--accent);color:var(--bg);border-color:var(--accent)}
main{max-width:1400px;margin:0 auto;padding:0 16px 40px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:16px 0;padding:14px}
.card h2{font-size:17px;margin:0 0 4px;text-transform:capitalize}.tag{font-size:12px;color:var(--muted);margin-left:6px;text-transform:none}
details{color:var(--muted);margin:4px 0 10px}details pre{white-space:pre-wrap;font:13px/1.4 ui-monospace,monospace;color:var(--ink)}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media (max-width:760px){.pair{grid-template-columns:1fr}}
.side{border:1px solid var(--line);border-radius:8px;padding:10px;min-width:0}.side.picked{background:var(--pick);border-color:var(--accent)}
.side h3{margin:0 0 6px;font-size:15px}.who{color:var(--accent);font-weight:600}
.shot-main{display:block;width:100%;aspect-ratio:4/3;object-fit:contain;border:1px solid var(--line);border-radius:6px;background:#fff;cursor:zoom-in}
.thumbs{display:flex;gap:6px;margin-top:6px;flex-wrap:wrap}.thumbs figure{margin:0;text-align:center;font-size:12px;color:var(--muted)}
.thumbs img{display:block;width:120px;aspect-ratio:4/3;object-fit:contain;border:2px solid var(--line);border-radius:4px;background:#fff;cursor:pointer}
.thumbs img.cur{border-color:var(--accent)}
.meta{font-size:13px;color:var(--muted);margin:6px 0}.meta .bad{color:var(--warn)}
pre.ans{white-space:pre-wrap;font:13px/1.45 ui-monospace,monospace;max-height:420px;overflow:auto;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:8px;margin:0}
ul.calls{font-size:12px;color:var(--muted);padding-left:18px;margin:4px 0}.rate{margin-top:8px;display:flex;gap:4px;align-items:center;flex-wrap:wrap}
iframe{width:100%;height:520px;border:1px solid var(--line);border-radius:6px;background:#fff;margin-top:6px}
.votes{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
#zoom{position:fixed;inset:0;background:rgba(0,0,0,.88);display:none;flex-direction:column;align-items:center;justify-content:center;z-index:9;cursor:zoom-out}
#zoom img{width:min(96vw,calc(90vh*4/3));height:auto;max-height:90vh;object-fit:contain;background:#fff}
#zoom .cap{color:#eee;font-size:13px;margin-top:8px}
</style></head><body>
<header><h1>Blind comparison: visual tests and research answers</h1>
<p>Each card shows two answers to the same prompt, left and right in a random order fixed per card. Visual cards: pick the better one (or a tie). Research cards: rate each answer 1-5; the key's script result appears when you reveal. Then reveal which label made which. "Copy my picks" exports both; import the ratings with <code>suite/run.sh ratings import &lt;file&gt;</code>. Screenshots come from a sandboxed headless Chromium with no network and are embedded in this page (1024 x 768); click one to enlarge (left / right arrow keys for the answer's other screenshots, Esc or a click to close). "Open live" runs the answer here in a sandboxed frame (it may load Three.js from its CDN). Your picks stay in this browser, per address: the same page opened as a file and over http keeps two separate sets.</p>
<div class="bar"><button id="revealAll">Reveal all labels</button><button id="copy">Copy my picks (JSON)</button><button id="clear">Clear my picks</button><span id="tally" class="meta"></span></div>
</header><main id="m"></main><div id="zoom"><img alt=""><div class="cap"></div></div>
<script>
const DATA = __DATA__;
const KEY = "blind:" + DATA.pair;
let picks = {};
try { picks = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { picks = {}; }
function save(){ try { localStorage.setItem(KEY, JSON.stringify(picks)); } catch (e) {} tally(); }
const dec = s => atob(s);
function el(t, a={}, ...k){ const e=document.createElement(t); for(const [x,y] of Object.entries(a)){ if(x==="class") e.className=y; else if(x.startsWith("on")) e.addEventListener(x.slice(2),y); else e.setAttribute(x,y);} for(const c of k){ e.append(c); } return e; }
let ratings = {};
try { ratings = JSON.parse(localStorage.getItem(KEY + ":ratings") || "{}"); } catch (e) { ratings = {}; }
function saveR(){ try { localStorage.setItem(KEY + ":ratings", JSON.stringify(ratings)); } catch (e) {} }
function researchSide(card, s, pos){
  const box = el("div",{class:"side"});
  const who = el("span",{class:"who"}, "");
  box.append(el("h3",{}, pos==="L"?"Left ":"Right ", who));
  if(s.missing){   // 11-01: the other label has this run, this one does not - nothing to rate here
    box.append(el("p",{class:"meta"}, "No answer on this side for this run. Nothing to rate here; rate the other side on its own."));
    const chk = el("div",{class:"meta hidden-check"}, ""); box.append(chk);
    box._who = who; box._tag = s.tag; box._chk = chk; box._checks = "";
    return box;
  }
  box.append(el("pre",{class:"ans"}, s.text || "(empty)"));
  const d = el("details",{}, el("summary",{}, `${s.calls.length} tool calls`));
  const ul = el("ul",{class:"calls"}); for(const c of s.calls) ul.append(el("li",{}, c)); d.append(ul); box.append(d);
  const chk = el("div",{class:"meta hidden-check"}, ""); box.append(chk);
  const rate = el("div",{class:"rate"}, "Your rating: ");
  const k = card.id + ":" + pos;
  for(let n=1;n<=5;n++){ const b=el("button",{class: ratings[k]===n?"on":""}, String(n));
    b.addEventListener("click",()=>{ ratings[k]=n; saveR(); render(); }); rate.append(b); }
  box.append(rate);
  box._who = who; box._tag = s.tag; box._chk = chk; box._checks = "key: " + (s.checks || "-");
  return box;
}
function side(card, s, pos){
  if(card.kind === "research") return researchSide(card, s, pos);
  const box = el("div",{class:"side"+(picks[card.id]===pos?" picked":"")});
  const who = el("span",{class:"who"}, "");
  box.append(el("h3",{}, pos==="L"?"Left ":"Right ", who));
  const shots = el("div",{class:"shots"});
  if(!s.shots.length) shots.append(el("div",{class:"meta"}, s.note || "nothing rendered (no code block in the answer?)"));
  const cap = k => `${pos==="L"?"Left":"Right"} · screenshot ${k+1} of ${s.shots.length}` + (s.shots[k].t!=null?` · at ${s.shots[k].t} s`:"");
  if(s.shots.length){
    let cur = 0;
    const main = el("img",{class:"shot-main", src:s.shots[0].src, alt:"screenshot", loading:"lazy", title:"click to enlarge"});
    main.addEventListener("click",()=>openZoom(s.shots, cur, cap));
    shots.append(main);
    if(s.shots.length > 1){
      const th = el("div",{class:"thumbs"});
      s.shots.forEach((sh,k)=>{ const t=el("img",{src:sh.src, alt:"screenshot "+(k+1), loading:"lazy", class:k===0?"cur":""});
        t.addEventListener("click",()=>{ cur=k; main.src=sh.src; th.querySelectorAll("img").forEach((x,j)=>x.className=j===k?"cur":""); });
        th.append(el("figure",{}, t, el("figcaption",{}, sh.t!=null?`${sh.t} s`:String(k+1)))); });
      shots.append(th);
    }
  }
  box.append(shots);
  const m = el("div",{class:"meta"});
  m.innerHTML = `console errors: <span class="${s.errors? "bad":""}">${s.errors ?? "-"}</span> · blocked requests: ${s.blocked}`;
  box.append(m);
  if(s.live){ const b=el("button",{}, "Open live"); let fr=null;
    b.addEventListener("click",()=>{ if(fr){fr.remove(); fr=null; b.textContent="Open live"; return;}
      // over http: the answer file itself; as a single file (no folder next to it): the embedded copy
      const a = {sandbox:"allow-scripts", title:"live answer"};
      if(/^https?:$/.test(location.protocol) || !s.live_doc) a.src = s.live;
      else if(s.live_doc.kind === "svg") a.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(s.live_doc.text);
      else a.srcdoc = s.live_doc.text;
      fr = el("iframe", a); box.append(fr); b.textContent="Close live"; });
    box.append(b); }
  box._who = who; box._tag = s.tag;
  return box;
}
function render(){
  const m=document.getElementById("m"); m.innerHTML="";
  for(const c of DATA.cards){
    const card = el("section",{class:"card"});
    card.append(el("h2",{}, c.title, el("span",{class:"tag"}, (c.variant?"unpublished variant · ":"")+"run "+c.run)));
    const d=el("details",{}, el("summary",{},"Prompt"), el("pre",{}, c.prompt)); card.append(d);
    const L=side(c,c.L,"L"), R=side(c,c.R,"R");
    card.append(el("div",{class:"pair"}, L, R));
    const votes=el("div",{class:"votes"});
    if(c.kind !== "research") for(const [v,t] of [["L","Left is better"],["T","Tie"],["R","Right is better"]]){
      const b=el("button",{class: picks[c.id]===v?"on":""}, t);
      b.addEventListener("click",()=>{ picks[c.id]=v; save(); render(); }); votes.append(b); }
    const rv=el("button",{}, "Reveal");
    rv.addEventListener("click",()=>{ L._who.textContent="= "+dec(L._tag); R._who.textContent="= "+dec(R._tag);
      if(L._chk){ L._chk.textContent=L._checks; R._chk.textContent=R._checks; } });
    votes.append(rv);
    card.append(votes); card._reveal=()=>rv.click(); m.append(card);
  }
}
function tally(){
  const n=Object.keys(picks).length; document.getElementById("tally").textContent = `${n} of ${DATA.cards.length} picked`;
}
document.getElementById("revealAll").addEventListener("click",()=>document.querySelectorAll(".card").forEach(c=>c._reveal&&c._reveal()));
document.getElementById("copy").addEventListener("click",()=>{
  const out={pair:DATA.pair, picks:{}};
  out.ratings = {};
  for(const c of DATA.cards){ if(c.kind==="research"){ for(const pos of ["L","R"]){ const v=ratings[c.id+":"+pos];
      if(v && !c[pos].missing) (out.ratings[c.id] ||= {})[dec(c[pos].tag)] = v; } continue; }
    const p=picks[c.id]; if(!p) continue; out.picks[c.id] = p==="T"?"tie": dec(p==="L"?c.L.tag:c.R.tag); }
  const s=JSON.stringify(out,null,1); navigator.clipboard?.writeText(s).catch(()=>{}); alert(s);
});
document.getElementById("clear").addEventListener("click",()=>{ picks={}; save(); render(); });
let zoomSet = null;
function showZoom(){ const z=document.getElementById("zoom"), {list,k,cap}=zoomSet;
  z.querySelector("img").src=list[k].src; z.querySelector(".cap").textContent=cap(k); z.style.display="flex"; }
function openZoom(list, k, cap){ zoomSet={list,k,cap}; showZoom(); }
function closeZoom(){ document.getElementById("zoom").style.display="none"; zoomSet=null; }
document.getElementById("zoom").addEventListener("click", closeZoom);
document.addEventListener("keydown",e=>{ if(!zoomSet) return;
  if(e.key==="Escape") closeZoom();
  else if(e.key==="ArrowRight"||e.key==="ArrowLeft"){ const n=zoomSet.list.length; zoomSet.k=(zoomSet.k+(e.key==="ArrowRight"?1:n-1))%n; showZoom(); e.preventDefault(); } });
render(); tally();
</script></body></html>
"""
