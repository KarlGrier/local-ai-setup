"""Research with web search: questions whose right answer depends on current information.  Every model gets the same
two tools (web_search, fetch_page; msuite/web.py, the shared cache) through the same loop: one user turn, at most 10
tool calls.  Scored by the editable key (items/research/key.json) per question = checks passed / checks decided;
your 1-5 rating from the blind page is reported beside it (`run.sh ratings import`).  Tool calls, tokens and wall
time are recorded per answer; speed claims are recorded, not scored.

No research question runs before items/research/APPROVED exists (you see the key first)."""
from __future__ import annotations

import json
import re
import time
from datetime import date

from ..common import ITEMS, read_json
from .. import web

DIR = ITEMS / "research"
MAX_CALLS = 10
MAX_STEPS = 14


def approved() -> bool:
    return (DIR / "APPROVED").exists()


def load() -> list[dict]:
    q = read_json(DIR / "questions.json")
    hw = (ITEMS / "freshness" / "hardware.txt").read_text(encoding="utf-8").strip()
    out = []
    for it in q["questions"]:
        prompt = (it["prompt"].replace("{hardware}", hw) + "\n\n" + q["format_intro"] + "\n```json\n" + it["json"]
                  + "\n```")
        out.append({"id": f"research/{it['id']}", "category": "research", "prompt": prompt, "research": True})
    return out


# ------------------------------------------------------------------------------------------------ the loop
def run_item(item: dict, backend, log=print, mode: str = "live") -> dict:
    sess = web.WebSession(item["prompt"], mode=mode)
    tools = sess.tool_defs()
    messages = [{"role": "user", "content": item["prompt"]}]
    steps, used, t0 = [], 0, time.monotonic()
    stop = None
    for step in range(1, MAX_STEPS + 1):
        est = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages) // 3
        rec = backend.chat(messages, tools=tools, max_tokens=None, prompt_tokens_est=est)
        r = rec["response"]
        calls = r.get("tool_calls") or []
        steps.append({"step": step, "tokens": rec["tokens"], "timing": rec["timing"], "cut_off": rec.get("cut_off"),
                      "finish_reason": r.get("finish_reason"), "n_calls": len(calls), "cost_usd": rec.get("cost_usd"),
                      "provider": (r.get("meta") or {}).get("provider")})
        if not calls:
            stop = "answered" if not rec.get("cut_off") else "cut off"
            final = rec
            break
        messages.append(backend.assistant_message(rec))
        results = []
        for c in calls:
            if used >= MAX_CALLS:
                out = (f"error: the tool-call budget ({MAX_CALLS}) is used up. Answer now with what you have, "
                       "ending with the JSON block.")
                sess.calls.append({"tool": c["name"], "args": c.get("arguments"), "cache": "refused (budget)"})
            else:
                out = sess.call(c["name"], c["arguments"])
                used += 1
            results.append((c["id"], out))
        messages += backend.tool_result_messages(results)
        final = rec
    else:
        stop = f"step limit ({MAX_STEPS})"
    tok = lambda k: sum((s["tokens"].get(k) or 0) for s in steps)
    fr = final["response"]
    return {
        "response": {"content": fr.get("content") or "", "reasoning": fr.get("reasoning") or "", "tool_calls": [],
                     "finish_reason": stop, "meta": fr.get("meta")},
        "cut_off": any(s.get("cut_off") for s in steps),
        "steps": steps, "n_steps": len(steps), "stop": stop,
        "tool_calls": sess.calls, "n_tool_calls": used,
        "web_cache": {"created": sess.info["created"], "today": sess.info["today"], "mode": sess.mode,
                      "frozen_at": sess.info.get("frozen_at"),
                      "nearest": sum(1 for c in sess.calls if c.get("cache") in ("nearest", "snapshot: no match")),
                      "hits": sum(1 for c in sess.calls if c.get("cache") == "hit"),
                      "misses": sum(1 for c in sess.calls if c.get("cache") == "miss")},
        "tokens": {"prompt": tok("prompt"), "completion": tok("completion"), "reasoning": tok("reasoning"),
                   "answer": tok("answer"), "method": steps[0]["tokens"].get("method") if steps else None},
        "timing": {"wall_s": round(time.monotonic() - t0, 2), "ttft_s": None, "e2e_tps": None, "decode_tps": None,
                   "server_decode_tps": None},
        "cost_usd": round(sum(s.get("cost_usd") or 0 for s in steps), 6) if any(s.get("cost_usd") for s in steps) else None,
    }


# ------------------------------------------------------------------------------------------------ the key
def norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def _json_answer(text: str):
    blocks = re.findall(r"```(?:json)?\s*\n(.*?)```", text or "", re.S)
    for b in reversed(blocks):
        try:
            v = json.loads(b)
            if isinstance(v, dict):
                return v
        except ValueError:
            continue
    for m in reversed(list(re.finditer(r"\{.*\}", text or "", re.S))):
        try:
            v = json.loads(m.group(0))
            if isinstance(v, dict):
                return v
        except ValueError:
            continue
    return None


class Key:
    def __init__(self, data=None):
        self.d = data or read_json(DIR / "key.json")
        self.models = sorted(((norm(a), name) for name, m in self.d["models"].items() for a in m["aliases"]),
                             key=lambda x: -len(x[0]))
        self.gpus = sorted(((norm(a), name) for name, g in self.d["gpus"].items() for a in g["aliases"]),
                           key=lambda x: -len(x[0]))

    def model_of(self, text):
        n = norm(text)
        return next((name for a, name in self.models if a and a in n), None)

    def gpu_of(self, text):
        n = norm(text)
        return next((name for a, name in self.gpus if a and a in n), None)

    def quant_of(self, q):
        """The key's quant name in q ('UD-Q4_K_XL' -> 'Q4_K_XL', '4-bit' -> 'INT4'), or None."""
        s = str(q or "").upper().replace("-", "_").replace(" ", "_")
        s = re.sub(r"^UD_", "", s)
        names = sorted(self.d["quant_bpw"], key=len, reverse=True)
        for name in names:
            if name in s:
                return name
        if re.search(r"(^|_)4_?BIT", s):
            return "INT4"
        if re.search(r"(^|_)8_?BIT", s):
            return "INT8"
        m = re.search(r"(^|_)Q([2-8])($|_)", s)
        if m:
            return {"2": "Q2_K", "3": "Q3_K_M", "4": "Q4_K_M", "5": "Q5_K_M", "6": "Q6_K", "8": "Q8_0"}[m.group(2)]
        return None

    def fit_size_gib(self, model, quant, stated=None):
        """The size that must fit in RAM + VRAM: main weights for models with fit_params_b (Flash-Next: its n-gram
        table may stay on the SSD), or the answer's stated size when the key allows it and it is smaller."""
        m = self.d["models"].get(model) or {}
        q = self.quant_of(quant)
        if m.get("fit_params_b") and q:
            size = m["fit_params_b"] * 1e9 * self.d["quant_bpw"][q] / 8 / 2 ** 30
            how = f"main weights {m['fit_params_b']}B x {q}"
            if m.get("fit_use_stated_size") and stated is not None and stated < size:
                return stated, "the size the answer states"
            return size, how
        if m.get("fit_params_b") and m.get("fit_use_stated_size") and stated is not None:
            return stated, "the size the answer states"
        return self.size_gib(model, quant)

    def size_gib(self, model, quant):
        m = self.d["models"].get(model) or {}
        q = self.quant_of(quant)
        sizes = {self.quant_of(k) or k.upper(): v for k, v in (m.get("sizes_gib") or {}).items()}
        raw = str(quant or "").upper().replace("-", "")
        for k, v in (m.get("sizes_gib") or {}).items():          # names like BPW2.5 / 3BIT
            if k.upper().replace("-", "") in raw:
                return float(v), "measured file"
        if q and q in sizes:
            return float(sizes[q]), "measured file"
        if q and m.get("params_b"):
            return m["params_b"] * 1e9 * self.d["quant_bpw"][q] / 8 / 2 ** 30, f"{m['params_b']}B x {q}"
        return None, None


def _picks(ans: dict, fields) -> list[dict]:
    out = []
    for f in fields:
        v = ans.get(f)
        if isinstance(v, list):
            out += [x if isinstance(x, dict) else {"model": x} for x in v]
        elif isinstance(v, dict):
            out.append(v)
        elif v is not None:
            out.append({"model": v})
    return out


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d[\d,]*\.?\d*", str(v or ""))
    return float(m.group(0).replace(",", "")) if m else None


def run_check(c: dict, ans: dict, text: str, key: Key):
    """-> (result 'pass' | 'fail' | 'unchecked', detail)"""
    t = c["type"]
    if t == "must_appear":
        names = [str(p.get("model") or p.get("name") or "") for p in _picks(ans, c.get("in", ["top_pick"]))]
        found = [key.model_of(n) or key.gpu_of(n) for n in names]
        hit = [x for x in c["any_of"] if x in found]
        return ("pass" if hit else "fail"), f"picks {names[:6]}"
    if t == "picks_fit":
        hw = key.d["hardware"]
        ok_lim, err_lim = hw["fit_pass_gib"], hw["fit_error_gib"]
        bad, unk, ok = [], [], []
        for p in _picks(ans, c["in"]):
            name, quant = p.get("model") or p.get("name"), p.get("quant")
            mod = key.model_of(name)
            stated = _num(p.get("size_gib"))
            size, how = key.fit_size_gib(mod, quant, stated) if mod else (None, None)
            if size is None and stated is not None and stated > err_lim:
                size, how = stated, "the answer's own size"
            if size is None:
                unk.append(f"{name} {quant}: size unknown")
            elif size > err_lim:
                bad.append(f"{name} {quant}: ~{size:.0f} GiB ({how}) > {err_lim}")
            elif size > ok_lim:
                unk.append(f"{name} {quant}: ~{size:.0f} GiB between {ok_lim} and {err_lim}")
            else:
                ok.append(f"{name} {quant}: ~{size:.0f} GiB ({how})")
        if bad:
            return "fail", "does not fit: " + "; ".join(bad)
        if not ok:
            return "unchecked", "; ".join(unk)
        return "pass", "fits: " + "; ".join(ok) + (f" (unchecked: {'; '.join(unk)})" if unk else "")
    if t == "top_pick_is":
        tp = _picks(ans, ["top_pick"])
        mod = key.model_of((tp[0] if tp else {}).get("model") or (tp[0] if tp else {}).get("name"))
        return ("pass" if mod in c["any_of"] else "fail"), f"top pick {mod or (tp[0] if tp else None)}"
    if t == "top_pick_open_weights":
        tp = _picks(ans, ["top_pick"])
        mod = key.model_of((tp[0] if tp else {}).get("model"))
        if mod is None:
            return "unchecked", "top pick unknown to the key"
        return ("pass" if key.d["models"][mod].get("open_weights") else "fail"), mod
    if t == "top_pick_min_vram_gb":
        tp = ans.get("top_pick")
        g = key.gpu_of(tp if isinstance(tp, str) else json.dumps(tp))
        vram = key.d["gpus"][g]["vram_gb"] if g else _num(ans.get("vram_gb"))
        if vram is None:
            return "unchecked", f"top pick {tp!r} unknown"
        return ("pass" if vram >= c["min"] else "fail"), f"{tp}: {vram:.0f} GB"
    if t == "price_for_top_pick":
        tp = ans.get("top_pick")
        g = key.gpu_of(tp if isinstance(tp, str) else json.dumps(tp))
        rng = c["ranges"].get(g) if g else None
        price = _num(ans.get(c["field"]))
        if rng is None:
            return "unchecked", f"no price range in the key for {tp!r}"
        if price is None:
            return "fail", "no price given"
        return ("pass" if rng[0] <= price <= rng[1] else "fail"), f"{g}: ${price:,.0f} vs ${rng[0]:,}-{rng[1]:,}"
    if t == "number_between":
        v = _num(ans.get(c["field"]))
        if v is None:
            return "fail", f"no {c['field']}"
        return ("pass" if c["min"] <= v <= c["max"] else "fail"), f"{c['field']} {v:,.0f} vs {c['min']:,}-{c['max']:,}"
    if t == "equals_version":
        v = str(ans.get(c["field"]) or "").strip().lstrip("vV")
        return ("pass" if v == c["value"] else "fail"), f"{c['field']} {v!r}"
    if t == "date_near":
        try:
            got = date.fromisoformat(str(ans.get(c["field"]) or "")[:10])
            want = date.fromisoformat(c["value"])
        except ValueError:
            return "fail", f"{c['field']} {ans.get(c['field'])!r} is not a date"
        return ("pass" if abs((got - want).days) <= c["days"] else "fail"), f"{got} vs {want}"
    if t == "keywords_min":
        v = ans.get(c["field"])
        hay = (" ".join(map(str, v)) if isinstance(v, list) else str(v or "")).lower()
        n = sum(1 for g in c["groups"] if any(k.lower() in hay for k in g))
        return ("pass" if n >= c["min"] else "fail"), f"{n} of {len(c['groups'])} change topics named"
    if t == "equals":
        return ("pass" if ans.get(c["field"]) == c["value"] else "fail"), f"{c['field']} {ans.get(c['field'])!r}"
    raise ValueError(f"unknown check type {t}")


def speed_notes(ans: dict, key: Key) -> list[str]:
    """Recorded, not scored: each expected_tok_s next to what was measured on this PC."""
    out = []
    for p in _picks(ans, ["top_pick", "alternatives"]):
        claim = _num(p.get("expected_tok_s"))
        if claim is None:
            continue
        mod = key.model_of(p.get("model"))
        meas = (key.d["models"].get(mod) or {}).get("measured_tok_s") or {}
        q = key.quant_of(p.get("quant"))
        m = meas.get(q) or meas.get("*")
        out.append(f"{p.get('model')} {p.get('quant')}: claims {claim:.0f} tok/s" +
                   (f", measured here {m}" if m else ", not measured here"))
    for a in ans.get("avoid") or []:
        if isinstance(a, dict):
            out.append(f"avoid: {a.get('model')} ({str(a.get('reason'))[:80]})")
    return out


def grade(item: dict, rec: dict, key: Key | None = None) -> dict:
    key = key or Key()
    qid = item["id"].split("/")[1]
    text = (rec.get("response") or {}).get("content") or ""
    ans = _json_answer(text)
    checks = key.d["questions"].get(qid, {}).get("checks", [])
    if ans is None:
        return {"score": 0.0, "solved": False, "detail": "no JSON answer block", "checks": [],
                "n_tool_calls": rec.get("n_tool_calls")}
    res = []
    for c in checks:
        try:
            r, why = run_check(c, ans, text, key)
        except Exception as e:  # noqa: BLE001
            r, why = "fail", f"checker error: {e}"
        res.append({"id": c["id"], "result": r, "detail": why})
    decided = [x for x in res if x["result"] != "unchecked"]
    # no check decided (every pick unknown to the key): not a zero - left out of the scores, for your rating
    score = sum(1 for x in decided if x["result"] == "pass") / len(decided) if decided else None
    notes = speed_notes(ans, key)
    return {"score": score, "solved": bool(decided) and score == 1.0,
            "detail": "; ".join(f"{x['id']} {x['result'].upper()}" for x in res) + f"; {rec.get('n_tool_calls')} tool calls"
                      + ("" if decided else "; no check decided - not scored, needs your rating"),
            "checks": res, "speed_claims_not_scored": notes, "answer_json": ans, "n_tool_calls": rec.get("n_tool_calls"),
            "web_cache": rec.get("web_cache")}


# ------------------------------------------------------------------------------------------------ self-test
SAMPLES = {
    "r01_best_gpu": ({"top_pick": "NVIDIA GeForce RTX 5090", "vram_gb": 32, "price_usd": 5400, "alternatives": ["RTX PRO 6000 Blackwell"]},
                     {"top_pick": "RTX 5070 Ti", "vram_gb": 16, "price_usd": 799, "alternatives": []}),
    "r02_best_model": ({"top_pick": {"model": "Qwen3.8-Flash-Next", "quant": "IQ3_S", "size_gib": 78, "expected_tok_s": 120},
                        "alternatives": [{"model": "GLM-5.3-Flash", "quant": "UD-Q2_K_XL", "size_gib": 102, "expected_tok_s": 15}],
                        "avoid": [{"model": "Qwen3.8-2.4T-A95B", "reason": "too big"}]},
                       {"top_pick": {"model": "GLM-5.3-Flash", "quant": "Q4_K_M", "size_gib": 95, "expected_tok_s": 40},
                        "alternatives": [{"model": "Qwen3.8-Flash-Next", "quant": "Q8_0", "size_gib": 176}], "avoid": []}),
    "r03_coding_model": ({"top_pick": {"model": "Qwen3.8-Flash-Next", "quant": "UD-Q4_K_XL", "size_gib": 104},
                          "alternatives": [{"model": "Qwen3.8-27B", "quant": "Q8_0", "size_gib": 28}]},
                         {"top_pick": {"model": "Qwen3.8-Max", "quant": "API", "size_gib": 0}, "alternatives": []}),
    "r04_strata_release": ({"version": "v0.1.43.1", "release_date": "2026-10-12",
                            "changes": ["The adaptive overlap is opt-in again", "Long prompts no longer stall on SATA SSDs",
                                        "two-card batch serving faster"]},
                           {"version": "v0.1.43", "release_date": "2026-10-10", "changes": ["non-finite guard"]}),
    "r05_gpu_price": ({"gpu": "NVIDIA GeForce RTX 5090", "low_usd": 4800, "high_usd": 7400},
                      {"gpu": "NVIDIA GeForce RTX 5090", "low_usd": 1999, "high_usd": 2600}),
    "r06_linux_kernel": ({"version": "7.2.10", "release_date": "2026-10-11"}, {"version": "6.12", "release_date": "2024-11-17"}),
    "r07_qwen4_flash": ({"qwen4_flash_released": False, "release_date": None, "newest_flash_model": "Qwen3.8-Flash-Next"},
                        {"qwen4_flash_released": True, "release_date": "2026-09-01", "newest_flash_model": "Qwen4-Flash"}),
}


def selftest():
    out = []
    key = Key()
    items = {i["id"].split("/")[1]: i for i in load()}
    out.append(("research: 7 questions, each with key checks and a JSON format in its prompt",
                len(items) == 7 and all(q in key.d["questions"] for q in items) and all("```json" in i["prompt"] for i in items.values()), ""))
    for qid, (good, bad) in SAMPLES.items():
        g = grade(items[qid], {"response": {"content": "Sources: ...\n```json\n" + json.dumps(good) + "\n```"}}, key)
        b = grade(items[qid], {"response": {"content": "```json\n" + json.dumps(bad) + "\n```"}}, key)
        out.append((f"research/{qid}: key passes the right answer, fails the stale / wrong one",
                    g["score"] == 1.0 and b["score"] < 1.0, f"good: {g['detail']} | bad: {b['detail']}"))
    g = grade(items["r02_best_model"], {"response": {"content": "```json\n" + json.dumps(SAMPLES["r02_best_model"][0]) + "\n```"}}, key)
    out.append(("research: speed claims recorded next to the measured values, not scored",
                any("measured here 145" in n for n in g["speed_claims_not_scored"]) and g["score"] == 1.0,
                "; ".join(g["speed_claims_not_scored"])))
    b = grade(items["r02_best_model"], {"response": {"content": "```json\n" + json.dumps(SAMPLES["r02_best_model"][1]) + "\n```"}}, key)
    fit = next(c for c in b["checks"] if c["id"] == "picks_fit")
    out.append(("research: Flash-Next Q8_0 (main weights 125B x 8.5 = ~124 GiB) is flagged as not fitting",
                fit["result"] == "fail" and "124" in fit["detail"], fit["detail"]))
    one = {"top_pick": {"model": "Qwen3.8-Flash-Next", "quant": "UD-Q4_K_XL", "size_gib": 104}, "alternatives": [],
           "avoid": []}
    g4 = grade(items["r02_best_model"], {"response": {"content": "```json\n" + json.dumps(one) + "\n```"}}, key)
    f4 = next(c for c in g4["checks"] if c["id"] == "picks_fit")
    out.append(("research: Flash-Next UD-Q4_K_XL checked by main weights (~71 GiB, fits), not the 104 GiB file",
                f4["result"] == "pass" and "71" in f4["detail"], f4["detail"]))
    unk = {"top_pick": {"model": "Some-Model-Not-In-The-Key 20B", "quant": "Q4_K_M", "size_gib": 12}, "alternatives": []}
    gu = grade(items["r03_coding_model"], {"response": {"content": "```json\n" + json.dumps(unk) + "\n```"}}, key)
    out.append(("research: an answer with no check decided (picks unknown to the key) is not scored, not a zero",
                gu["score"] is None and not gu["solved"] and "needs your rating" in gu["detail"], gu["detail"]))
    return out


def loop_selftest():
    """The loop and the cache offline: a scripted 'model', a mock SearXNG on 127.0.0.1, a temporary cache."""
    import shutil
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from ..common import TMP
    out = []

    class H(BaseHTTPRequestHandler):
        hits = []

        def log_message(self, *a):
            pass

        def do_GET(self):
            H.hits.append(self.path)
            body = json.dumps({"results": [{"title": "Kernel releases", "url": "https://www.kernel.org/releases.html",
                                            "content": "stable 7.2.10"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    old_cache, old_sx = web.CACHE, web.SEARXNG
    web.CACHE = TMP / "webcache-selftest"
    shutil.rmtree(web.CACHE, ignore_errors=True)
    web.SEARXNG = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        web.cache_info()
        web._cache_put("pages", web.norm_url("https://www.kernel.org/releases.html"),
                       {"url": "https://www.kernel.org/releases.html", "fetched_at": "x", "final_url": "https://www.kernel.org/releases.html",
                        "title": "releases", "text": "stable: 7.2.10 2026-10-11"})

        class Scripted:
            """12 tool calls in one step, then an answer."""
            def __init__(self):
                self.n = 0

            def chat(self, messages, tools=None, max_tokens=None, prompt_tokens_est=0):
                self.n += 1
                assert [t["name"] for t in tools] == ["web_search", "fetch_page"]
                if self.n == 1:
                    calls = [{"id": "c0", "name": "web_search", "arguments": '{"query": "Latest  stable kernel"}'},
                             {"id": "c1", "name": "fetch_page", "arguments": '{"url": "https://kernel.org/releases.html"}'},
                             {"id": "c2", "name": "fetch_page", "arguments": '{"url": "https://evil.example/x"}'}] + \
                            [{"id": f"c{k}", "name": "web_search", "arguments": '{"query": "latest stable kernel"}'} for k in range(3, 12)]
                    content = ""
                else:
                    calls, content = [], 'Done.\n```json\n{"version": "7.2.10", "release_date": "2026-10-11"}\n```'
                return {"response": {"content": content, "reasoning": "", "tool_calls": calls, "finish_reason": "stop"},
                        "cut_off": False, "tokens": {"prompt": 10, "completion": 5, "reasoning": 1, "answer": 4, "method": "x"},
                        "timing": {"wall_s": 0.1}}

            @staticmethod
            def assistant_message(rec):
                return {"role": "assistant", "content": rec["response"]["content"]}

            @staticmethod
            def tool_result_messages(results):
                return [{"role": "tool", "tool_call_id": c, "content": t} for c, t in results]

        item = [i for i in load() if i["id"].endswith("r06_linux_kernel")][0]
        rec = run_item(item, Scripted())
        calls = rec["tool_calls"]
        out.append(("research loop: 10 calls allowed, the rest refused; one search reaches SearXNG, repeats replay",
                    rec["n_tool_calls"] == 10 and sum(1 for c in calls if c.get("cache") == "refused (budget)") == 2
                    and len(H.hits) == 1 and calls[0]["cache"] == "miss" and calls[3]["cache"] == "hit", str([c.get("cache") for c in calls])))
        out.append(("research loop: fetch_page replays the cached page; a URL not from the results is refused",
                    calls[1]["cache"] == "hit" and calls[2]["cache"] == "error", ""))
        g = grade(item, rec)
        out.append(("research loop: the answer is graded by the key", g["score"] == 1.0, g["detail"]))
        web.freeze(log=lambda m: None)
        s = web.WebSession("q")
        near = s.call("web_search", '{"query": "newest stable linux kernel version"}')
        none = s.call("web_search", '{"query": "best pizza in naples"}')
        page = s.call("fetch_page", '{"url": "https://www.kernel.org/releases.html"}')
        out.append(("research loop: after the freeze a new search gets the closest stored one (said so), an unrelated "
                    "one gets none, stored pages still open, nothing goes live",
                    s.mode == "frozen" and "closest search" in near and "kernel.org" in near and "No results" in none
                    and "7.2.10" in page and len(H.hits) == 1, near[:160]))
    finally:
        srv.shutdown()
        shutil.rmtree(web.CACHE, ignore_errors=True)
        web.CACHE, web.SEARXNG = old_cache, old_sx
    return out
