"""Privacy check for everything the suite writes: no API key (sk-ant-..., sk-or-...), no home
paths, user name, hostname, e-mail addresses, private-range or this machine's own IPv4 addresses, or GPU UUIDs in
results or reports.
Prints one line per finding; never prints a matched key."""
from __future__ import annotations

import getpass
import re
import socket
import subprocess
from pathlib import Path


TEXT_SUFFIXES = {".json", ".md", ".txt", ".html", ".svg", ".log", ".csv", ".py", ".sh"}


def _patterns():
    user, host = getpass.getuser(), socket.gethostname()
    pats = [
        (re.compile(r"sk-ant-[A-Za-z0-9_-]{6,}"), "Anthropic API key (sk-ant-)", True),
        (re.compile(r"sk-or-[A-Za-z0-9_-]{6,}"), "OpenRouter API key (sk-or-)", True),
        (re.compile(r"\b(?:sk-|hf_|ghp_|gho_|github_pat_)[A-Za-z0-9_]{16,}"), "API key / token", True),
        (re.compile(r"/home/" + re.escape(user)), "home path", False),
        (re.compile(r"\b" + re.escape(user) + r"\b", re.I), "user name", False),
        (re.compile(r"\b" + re.escape(host) + r"\b", re.I), "hostname", False),
        (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "e-mail address", False),
        (re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"), "IPv4 address", False),
        (re.compile(r"GPU-[0-9a-f]{8}-[0-9a-f]{4}-"), "GPU UUID", False),
    ]
    # the key files are read only by the API clients (the user's rule), so leaks are found by their patterns
    return pats, None


# e-mail addresses that are part of the test prompts themselves (fictional example.com / example.org)
ALLOWED_EMAIL = re.compile(r"@example\.(?:com|org)$|^noreply@")


def _own_addresses() -> set[str]:
    out = set()
    try:
        r = subprocess.run(["ip", "-4", "-o", "addr", "show"], capture_output=True, text=True, timeout=5).stdout
        out |= set(re.findall(r"inet (\d+\.\d+\.\d+\.\d+)", r))
    except (OSError, subprocess.SubprocessError):
        pass
    return out - {"127.0.0.1"}


OWN = _own_addresses()


def _sensitive_ip(s: str) -> bool:
    """Private-range addresses and this machine's own addresses (model answers are full of version strings such
    as 1.0.0.0, which are not addresses of yours)."""
    if s == "127.0.0.1":
        return False
    a, b = (int(x) for x in s.split(".")[:2])
    return (s in OWN or a == 10 or (a == 192 and b == 168) or (a == 172 and 16 <= b <= 31) or (a == 169 and b == 254)
            or (a == 100 and 64 <= b <= 127))


def check_text(text: str, where: str, pats, secret) -> list[str]:
    out = []
    if secret and secret in text:
        out.append(f"{where}: the API key's value appears here")
    for i, line in enumerate(text.splitlines(), 1):
        for pat, what, is_key in pats:
            for m in pat.finditer(line):
                s = m.group(0)
                if what == "e-mail address" and ALLOWED_EMAIL.search(s):
                    continue
                if what == "IPv4 address" and not _sensitive_ip(s):
                    continue
                shown = "[redacted]" if is_key or what in ("home path", "user name", "hostname") else s[:60]
                out.append(f"{where}:{i}: {what}: {shown}")
    return out


def check_paths(paths) -> list[str]:
    pats, secret = _patterns()
    out = []
    for root in paths:
        root = Path(root)
        files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
        for p in files:
            if p.suffix.lower() not in TEXT_SUFFIXES or p.stat().st_size > 50_000_000 or p.name == "privacy.txt":
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            out += check_text(text, str(p.relative_to(root.parent if root.is_dir() else root.parent)), pats, secret)
    return out


def selftest():
    pats, _ = _patterns()
    fake = "sk-ant-api03-" + "Ab1_" * 6
    fake_or = "sk-or-v1-" + "0f" * 32
    hits = check_text(f"token={fake}\nother {fake_or}\nuser jana@example.com ok\nnot 10.0.0.7\n", "sample", pats, None)
    ok = (any("sk-ant-" in h for h in hits) and any("sk-or-" in h for h in hits)
          and not any(fake in h or fake_or in h for h in hits)
          and not any("example.com" in h for h in hits) and any("IPv4" in h for h in hits))
    return [("privacy: catches sk-ant- and sk-or- keys (without printing them) and private IPs; allows the "
             "prompts' example.com addresses", bool(ok), "; ".join(hits)[:300])]
