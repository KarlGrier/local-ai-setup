"""Screenshot PNG -> WebP for the blind pages (2026-10-13): the pages embed their screenshots as data URIs, so they
open as a single file (a browser that reaches local files through the document portal sees only the HTML).  Runs
with the system Python (/usr/bin/python3 -I), which has Pillow; the suite's venv does not.  Same pixel size (1024 x
768), WebP quality 90: ~30 KB a screenshot instead of ~180 KB.  argv: a JSON list of [png, webp] pairs; each WebP is
written to a temporary name and renamed, so a half-written file is never used."""
import json
import os
import sys

from PIL import Image

for src, dst in json.loads(sys.argv[1]):
    tmp = f"{dst}.part{os.getpid()}"
    with Image.open(src) as im:
        im.convert("RGB").save(tmp, format="WEBP", quality=90, method=4)
    os.replace(tmp, dst)
