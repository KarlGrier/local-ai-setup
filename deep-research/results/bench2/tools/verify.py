#!/usr/bin/env python3
"""verify.py - fetch a page (Wikipedia through its API, else plain HTTP with a browser user agent), strip it to text,
and show the context of each phrase: the evidence behind a stored answer.

  verify.py URL "phrase" ["phrase" ...]       prints each phrase's first hits with ~200 chars around them
  verify.py --save DIR URL ...                 also saves the page text (DIR/<sha1>.txt) for the answer record
"""
import hashlib
import html
import json
import re
import sys
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"


def fetch(url: str) -> str:
    u = urllib.parse.urlsplit(url)
    if u.netloc.endswith("wikipedia.org") and u.path.startswith("/wiki/"):
        title = urllib.parse.unquote(u.path[len("/wiki/"):])
        api = (f"https://{u.netloc}/w/api.php?action=query&prop=extracts&explaintext=1&redirects=1&format=json&titles="
               + urllib.parse.quote(title))
        import time
        time.sleep(2)                     # Wikipedia's API rate limit
        wua = "deep-research-bench/1.0 (personal research test set; python urllib)"
        with urllib.request.urlopen(urllib.request.Request(api, headers={"User-Agent": wua}), timeout=30) as r:
            d = json.load(r)
        return "\n".join(p.get("extract", "") for p in d["query"]["pages"].values())
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
                                              "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        if r.headers.get("Content-Encoding") == "gzip" or body[:2] == b"\x1f\x8b":
            import gzip
            body = gzip.decompress(body)
        raw = body.decode(r.headers.get_content_charset() or "utf-8", errors="replace")
    raw = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw)
    t = html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))
    return re.sub(r"\s+", " ", t)


def main() -> None:
    args = sys.argv[1:]
    save = None
    if args and args[0] == "--save":
        save, args = args[1], args[2:]
    url, phrases = args[0], args[1:]
    try:
        text = fetch(url)
    except Exception as e:  # noqa: BLE001
        print(f"FETCH FAILED {url}: {type(e).__name__}: {e}")
        sys.exit(1)
    print(f"{url}  ({len(text)} chars)")
    if save:
        import os
        os.makedirs(save, exist_ok=True)
        p = os.path.join(save, hashlib.sha1(url.encode()).hexdigest()[:12] + ".txt")
        open(p, "w").write(url + "\n\n" + text)
    low = text.lower()
    for ph in phrases:
        i = low.find(ph.lower())
        if i < 0:
            print(f"  [missing] {ph!r}")
            continue
        print(f"  [found] {ph!r}: ...{text[max(0, i - 110):i + 130]}...")


if __name__ == "__main__":
    main()
