#!/usr/bin/env python3
"""undecided-page.py - a blind page for Karl with only the points the blind graders could not decide (Karl 11-01: "send me
blind pages only for answers the checklists can't decide"). Item 7 parts first (blind-p7b, -p7c, -p7a).

  undecided-page.py BLIND_DIR PART OUT.html
      BLIND_DIR  results/bench2/blind-<part> (grades-<qid>.json with "undecided", <qid>/A.md, B.md)
      PART       a name for the page and its browser store, e.g. "item 7 part 7b"
      OUT.html   e.g. ~/Desktop/To-rate/blind-item7-7b-undecided.html

Points settled outside the page (a fact found in our own files, say) are listed in BLIND_DIR/settled.json as
{"<qid>": [<index in that grader's "undecided" list>, ...]} and left out. Labels stay A / B as in the packets; the key
is not in the page. Picks (A / tie / B) and notes stay in the browser per page address; "Copy my picks (JSON)" gives
them for the import (they are read by hand into the part's SUMMARY.md, not by a script score).
"""
import html
import json
import sys
from pathlib import Path

B = Path("/home/USER/ai/deep-research/results/bench2")


def main() -> None:
    bdir, part, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]).expanduser()
    qtext = {}
    for line in (B / "questions-screen.jsonl").read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            qtext[d["id"]] = d["question"]
    settled = json.loads((bdir / "settled.json").read_text()) if (bdir / "settled.json").exists() else {}
    qs = []
    for g in sorted(bdir.glob("grades-*.json")):
        d = json.loads(g.read_text())
        skip = set(settled.get(d["id"], []))
        pts = [u for i, u in enumerate(d.get("undecided") or []) if i not in skip]
        if not pts:
            continue
        qs.append({"id": d["id"], "question": qtext.get(d["id"], ""), "points": pts,
                   "A": (bdir / d["id"] / "A.md").read_text(), "B": (bdir / d["id"] / "B.md").read_text()})
    data = json.dumps({"part": part, "questions": qs}, ensure_ascii=False).replace("</", "<\\/")
    n = sum(len(q["points"]) for q in qs)
    page = PAGE.replace("__TITLE__", html.escape(f"Undecided points, {part}")).replace("__N__", str(n)) \
               .replace("__DATA__", data)
    out.write_text(page, encoding="utf-8")
    print(f"{out}: {len(qs)} questions, {n} points, {len(page) // 1024} KiB")


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#fbfbf9;--fg:#1d1d1b;--muted:#5f5f5a;--card:#ffffff;--line:#dcdcd5;--accent:#2f5d8a;--on:#2f5d8a;--onfg:#fff}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#171716;--fg:#e8e8e3;--muted:#a3a39b;--card:#20201e;--line:#3a3a36;--accent:#8db4dc;--on:#8db4dc;--onfg:#111}}
:root[data-theme="dark"]{--bg:#171716;--fg:#e8e8e3;--muted:#a3a39b;--card:#20201e;--line:#3a3a36;--accent:#8db4dc;--on:#8db4dc;--onfg:#111}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main,header{max-width:920px;margin:0 auto;padding:0 16px}
header{padding-top:24px}
h1{font-size:1.4rem;margin:0 0 8px}
h2{font-size:1.15rem;margin:0 0 6px}
p{margin:6px 0}
.muted{color:var(--muted)}
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:12px 0 20px}
button{font:inherit;padding:6px 12px;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;cursor:pointer}
button.on{background:var(--on);color:var(--onfg);border-color:var(--on)}
section.q{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:0 0 20px}
.qtext{color:var(--muted);font-size:.95rem}
.pt{border-top:1px solid var(--line);margin-top:14px;padding-top:12px}
.pt h3{font-size:1rem;margin:0 0 4px}
.sides{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:8px 0}
@media (max-width:640px){.sides{grid-template-columns:1fr}}
.side{border:1px solid var(--line);border-radius:8px;padding:10px}
.side b{color:var(--accent)}
.votes{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
textarea{width:100%;min-height:52px;font:inherit;padding:6px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}
details{margin-top:12px}
summary{cursor:pointer;color:var(--accent)}
pre{white-space:pre-wrap;word-wrap:break-word;font:14px/1.45 ui-monospace,Menlo,Consolas,monospace;max-height:70vh;overflow:auto;border:1px solid var(--line);border-radius:8px;padding:10px;background:var(--bg)}
</style></head><body>
<header>
<h1>__TITLE__</h1>
<p>__N__ points that the blind graders could not settle from the checklists: matters of judgment, of your own
preference, or facts nobody could check. Each question has two reports, A and B, in a random order. For each point,
pick the report that handles it better, or a tie; a note is optional. The full reports are at the end of each question
if you want to look.</p>
<p class="muted">Your picks stay in this browser for this page. When you're done, press "Copy my picks (JSON)", save it
in To-rate/ratings/ (or paste it to Claude), and tell Claude.</p>
<div class="bar"><button id="copy">Copy my picks (JSON)</button><span id="tally" class="muted"></span></div>
</header>
<main id="m"></main>
<script>
const DATA = __DATA__;
const KEY = "undecided:" + DATA.part;
let st = {picks:{}, notes:{}};
try { st = Object.assign(st, JSON.parse(localStorage.getItem(KEY) || "{}")); } catch (e) {}
function save(){ try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} tally(); }
function el(t, a={}, ...k){ const e=document.createElement(t); for(const [x,y] of Object.entries(a)){ if(x==="class") e.className=y; else e.setAttribute(x,y);} for(const c of k) e.append(c); return e; }
function total(){ return DATA.questions.reduce((n,q)=>n+q.points.length,0); }
function tally(){ document.getElementById("tally").textContent = `${Object.keys(st.picks).length} of ${total()} picked`; }
function render(){
  const m=document.getElementById("m"); m.innerHTML="";
  for(const q of DATA.questions){
    const s=el("section",{class:"q"});
    s.append(el("h2",{}, q.id), el("p",{class:"qtext"}, q.question));
    q.points.forEach((p,i)=>{
      const k=q.id+"#"+(i+1);
      const d=el("div",{class:"pt"});
      d.append(el("h3",{}, `Point ${i+1}: ${p.item}`), el("p",{class:"muted"}, "Why the checklist can't decide: "+p.why));
      const sides=el("div",{class:"sides"});
      for(const x of ["A","B"]){ const b=el("div",{class:"side"}); b.append(el("b",{}, "Report "+x+": "), document.createTextNode(p[x]||"")); sides.append(b); }
      d.append(sides, el("p",{class:"muted"}, "(The grader's summary of each report's position; it may include the grader's own checks.)"));
      const v=el("div",{class:"votes"});
      for(const [val,t] of [["A","A is better"],["tie","Tie"],["B","B is better"]]){
        const b=el("button",{class: st.picks[k]===val?"on":""}, t);
        b.addEventListener("click",()=>{ st.picks[k]=val; save(); render(); }); v.append(b); }
      const ta=el("textarea",{placeholder:"Note (optional)"}); ta.value=st.notes[k]||"";
      ta.addEventListener("input",()=>{ st.notes[k]=ta.value; save(); });
      d.append(v, ta); s.append(d);
    });
    for(const x of ["A","B"]){ const det=el("details",{}, el("summary",{}, `Read report ${x} in full (${Math.round(q[x].length/1000)}k characters)`), el("pre",{}, q[x])); s.append(det); }
    m.append(s);
  }
  tally();
}
document.getElementById("copy").addEventListener("click",()=>{
  const out={page:DATA.part, picks:st.picks, notes:Object.fromEntries(Object.entries(st.notes).filter(([k,v])=>v&&v.trim()))};
  const s=JSON.stringify(out,null,1); if(navigator.clipboard) navigator.clipboard.writeText(s).catch(()=>{}); alert(s);
});
render();
</script></body></html>
"""

if __name__ == "__main__":
    main()
