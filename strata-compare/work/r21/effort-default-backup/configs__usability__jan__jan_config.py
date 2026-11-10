#!/usr/bin/env python3
"""jan_config.py - set Jan 0.8.6 up for Strata by editing its settings files (Jan must be closed).

    python3 configs/usability/jan/jan_config.py [--data ~/.local/share/Jan/data]

What it sets (each change also listed in jan/settings-applied.json next to this file):
  * a provider "Strata" (OpenAI-compatible) at http://127.0.0.1:8080/v1 with the model strata-qwen3.8-flash-next-iq3s
    (completion + tools), selected as the default model; no API key (Strata needs none)
  * every cloud provider switched off (no keys are stored anywhere)
  * the default assistant's parameters: temperature 1.0, top_p 0.95, top_k 20, min_p 0.05, reasoning_effort xhigh
    (Jan's own default adds repeat_penalty 1.12 and temperature 0.7; both replaced)
  * automatic chat titles off; automatic update checks off; product analytics off and its prompt dismissed
  * web search: on, provider SearXNG at http://127.0.0.1:8888
A backup of every file it changes is kept as <file>.before-strata.
"""
import argparse
import json
import os
import shutil
from pathlib import Path

MODEL_ID = "strata-qwen3.8-flash-next-iq3s"
BASE = "http://127.0.0.1:8080/v1"
SEARXNG = "http://127.0.0.1:8888"
CLOUD_OFF = ["openai", "azure", "anthropic", "openrouter", "mistral", "groq", "xai", "gemini", "minimax", "huggingface",
             "nvidia"]
PARAMS = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05, "reasoning_effort": "xhigh"}


def backup(p: Path):
    b = p.with_name(p.name + ".before-strata")
    if not b.exists():
        shutil.copy2(p, b)


def store(settings, key, default_state, version=0):
    raw = settings.get(key)
    obj = json.loads(raw) if raw else {"state": dict(default_state), "version": version}
    return obj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.expanduser("~/.local/share/Jan/data"))
    a = ap.parse_args()
    data = Path(a.data)
    sp = data / "settings.json"
    backup(sp)
    s = json.loads(sp.read_text())
    applied = {}

    mp = json.loads(s["model-provider"])
    st = mp["state"]
    model = {"id": MODEL_ID, "name": "Qwen3.8 Flash (Strata C*18, IQ3_S)", "capabilities": ["completion", "tools"]}
    openai_tpl = next(p for p in st["providers"] if p["provider"] == "openai")
    api_key_setting = json.loads(json.dumps(next(x for x in openai_tpl["settings"] if x["key"] == "api-key")))
    api_key_setting["description"] = "Strata on 127.0.0.1 needs no key."
    api_key_setting["controller_props"]["value"] = ""
    strata = {"active": True, "provider": "Strata", "base_url": BASE, "models": [model],
              "settings": [api_key_setting,
                           {"key": "base-url", "title": "Base URL", "description": "The base OpenAI-compatible endpoint.",
                            "controller_type": "input",
                            "controller_props": {"placeholder": BASE, "value": BASE}}]}
    st["providers"] = [p for p in st["providers"] if p["provider"] != "Strata"] + [strata]
    for p in st["providers"]:
        if p["provider"] in CLOUD_OFF:
            p["active"] = False
    st["selectedProvider"] = "Strata"
    st["selectedModel"] = model
    s["model-provider"] = json.dumps(mp)
    applied["model-provider"] = {"added": strata, "deactivated": CLOUD_OFF, "selected": ["Strata", MODEL_ID]}

    g = store(s, "setting-general", {"currentLanguage": "en", "spellCheckChatInput": True, "tokenCounterCompact": True,
                                     "stripReasoningFromContext": False})
    g["state"]["autoUpdateCheck"] = False
    s["setting-general"] = json.dumps(g)
    applied["setting-general"] = {"autoUpdateCheck": False}

    i = store(s, "setting-appearance", {})
    i["state"]["autoGenerateTitle"] = False
    s["setting-appearance"] = json.dumps(i)
    applied["setting-appearance"] = {"autoGenerateTitle": False}

    for key, val in (("productAnalyticPrompt", {"productAnalyticPrompt": False}),
                     ("productAnalytic", {"productAnalytic": False})):
        o = store(s, key, {})
        o["state"].update(val)
        s[key] = json.dumps(o)
        applied[key] = val

    w = store(s, "setting-web-search", {})
    w["state"].update({"webSearchEnabled": True, "searchProvider": "searxng"})
    w["state"].setdefault("endpoints", {})["searxng"] = SEARXNG
    s["setting-web-search"] = json.dumps(w)
    applied["setting-web-search"] = w["state"]

    sp.write_text(json.dumps(s))

    for ap_path in data.glob("assistants/*/assistant.json"):
        backup(ap_path)
        asst = json.loads(ap_path.read_text())
        asst["parameters"] = dict(PARAMS)
        ap_path.write_text(json.dumps(asst, indent=2, ensure_ascii=False))
        applied[f"assistant {asst.get('id')}"] = {"parameters": PARAMS}

    out = Path(__file__).with_name("settings-applied.json")
    out.write_text(json.dumps(applied, indent=1) + "\n")
    print(json.dumps(applied, indent=1)[:3000])


if __name__ == "__main__":
    main()
