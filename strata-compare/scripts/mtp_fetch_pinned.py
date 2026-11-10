"""Run Strata's tools/mtp_fetch.py unchanged, but against a PINNED revision of Qwen/Qwen3.8-Flash-Next
(upstream uses resolve/main). Usage: mtp_fetch_pinned.py <strata dir> <revision> fetch --out DIR"""
import sys, runpy
strata, rev = sys.argv[1], sys.argv[2]
sys.path.insert(0, strata + "/tools")
import mtp_fetch
mtp_fetch.REPO = f"https://huggingface.co/Qwen/Qwen3.8-Flash-Next/resolve/{rev}/"
print("REPO =", mtp_fetch.REPO, flush=True)
sys.argv = ["mtp_fetch.py"] + sys.argv[3:]
mtp_fetch.main()
