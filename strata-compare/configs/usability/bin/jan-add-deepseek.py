#!/usr/bin/python3 -I
"""jan-add-deepseek.py (Karl 11-06) - add the DeepSeek model to Jan's Strata provider, once.

Jan holds its settings in memory and writes them back, so settings.json is edited only while Jan is closed. jan-strata
(the Jan icon) runs this with --if-pending before it opens Jan; after one success the marker tmp/jan-ds-entry.applied stops
it for good, so a model removed by hand in Jan does not come back.

  jan-add-deepseek.py --dry-run [SETTINGS]   prints the provider's models after the change; writes nothing
  jan-add-deepseek.py --if-pending           adds it if not done yet and Jan is closed (silent otherwise)

Provider: Strata (base URL 127.0.0.1:8080, where DeepSeek runs too). Tools on; vision off: DeepSeek's config has no image
encoder (the server says "this server has no image encoder"). Key values are never read out or printed.
"""
import json
import os
import shutil
import subprocess
import sys
import time

SETTINGS = os.path.expanduser("~/.local/share/Jan/data/settings.json")
DONE = "/home/USER/ai-speed-testing/strata-compare/tmp/jan-ds-entry.applied"
ENTRY = {"id": "deepseek-v4.1-flash",
         "name": "DeepSeek V4.1 Flash (only after the DeepSeek launcher; otherwise Qwen answers)",
         "capabilities": ["tools"],
         "_userConfiguredCapabilities": True}


def load(path):
    raw = open(path, encoding="utf-8").read()
    outer = json.loads(raw)
    inner = json.loads(outer["model-provider"])
    if json.dumps(json.loads(raw), indent=2, ensure_ascii=False) not in (raw, raw.rstrip("\n")):
        raise SystemExit("settings.json has an unexpected format - not touched")
    if json.dumps(inner, separators=(",", ":"), ensure_ascii=False) != outer["model-provider"]:
        raise SystemExit("the model-provider value has an unexpected format - not touched")
    return raw, outer, inner


def strata(inner):
    ps = [p for p in inner["state"]["providers"] if p.get("provider") == "Strata"]
    if len(ps) != 1:
        raise SystemExit(f"{len(ps)} providers named Strata - not touched")
    return ps[0]


def change(inner):
    p = strata(inner)
    if p.get("base_url") != "http://127.0.0.1:8080/v1":
        raise SystemExit("the Strata provider's base URL is not 127.0.0.1:8080 - not touched")
    if any(m.get("id") == ENTRY["id"] for m in p["models"]):
        return False
    p["models"].append(dict(ENTRY))
    return True


def jan_running():
    return subprocess.run(["pgrep", "-x", "Jan-Desktop"], capture_output=True).returncode == 0


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    path = sys.argv[2] if len(sys.argv) > 2 else SETTINGS
    if mode == "--dry-run":
        raw, outer, inner = load(path)
        changed = change(inner)
        outer["model-provider"] = json.dumps(inner, separators=(",", ":"), ensure_ascii=False)
        new = json.dumps(outer, indent=2, ensure_ascii=False)
        json.loads(new)
        print(f"would change: {changed}; Jan running now: {jan_running()}; already applied: {os.path.exists(DONE)}")
        for m in strata(inner)["models"]:
            print("  ", {k: m.get(k) for k in ("id", "name", "capabilities")})
        others = [k for k in outer if k != "model-provider" and json.loads(raw)[k] != outer[k]]
        print("other settings changed:", others or "none")
        return 0
    if mode != "--if-pending":
        print(__doc__)
        return 2
    if os.path.exists(DONE) or jan_running():
        return 0
    raw, outer, inner = load(path)
    if change(inner):
        shutil.copy2(path, path + ".before-deepseek")
        outer["model-provider"] = json.dumps(inner, separators=(",", ":"), ensure_ascii=False)
        tmp = path + ".new"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(outer, indent=2, ensure_ascii=False) + ("\n" if raw.endswith("\n") else ""))
        os.replace(tmp, path)
    with open(DONE, "w") as f:
        f.write(time.strftime("%F %T\n"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
