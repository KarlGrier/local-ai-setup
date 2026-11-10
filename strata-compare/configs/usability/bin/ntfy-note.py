#!/usr/bin/python3 -I
"""ntfy-note.py TITLE MESSAGE [--dry-run] - Claude 11-08 (Karl: "send a non-urgent ntfy when Phase 5's queue
finishes"). One NON-URGENT status message to Karl's phone through ntfy.sh, beside alert-push.py (which forwards only
critical desktop alerts and stays unchanged). Uses alert-push.py's own clean() (short, path-free: no paths, ~, @, IPs
except 127.0.0.1, UUIDs / long hex, user or host name) and topic() (read from ~/.config/alert-push/topic inside this
code only - never printed or logged). Priority "default" (alert-push sends "high"). Logs the title only, to
alert-push's log. --dry-run: checks the topic file and prints the cleaned title + message, sends nothing.
Exit 0 sent (or dry run ok), 1 not sent after 3 tries, 2 usage / topic file problem.
"""
import importlib.util, sys, time, urllib.request

AP = "/home/USER/ai/deep-research/tools/alert-push.py"


def load_ap():
    spec = importlib.util.spec_from_file_location("alert_push", AP)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)          # module level only: imports, constants; main() is not called
    return m


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = len(args) != len(sys.argv) - 1
    if len(args) != 2:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        return 2
    ap = load_ap()
    try:
        ap.topic()
    except (OSError, SystemExit) as e:
        print(f"ntfy-note: topic file problem ({type(e).__name__})", file=sys.stderr)
        return 2
    title, msg = ap.clean(args[0], 90), ap.clean(args[1], 180)
    if dry:
        print(f"ntfy-note dry run: topic file ok; title: {title!r}; message: {msg!r}")
        return 0
    hdr = {"Title": title.encode("ascii", "replace").decode(), "Priority": "default", "Tags": "information_source"}
    for i in range(3):
        try:
            req = urllib.request.Request(ap.URL + ap.topic(), data=(msg or title).encode(), headers=hdr, method="POST")
            with urllib.request.urlopen(req, timeout=20) as r:
                if r.status == 200:
                    ap.log(f"ntfy-note sent (non-urgent): {title}")
                    return 0
        except Exception as e:  # noqa: BLE001 - logged without the URL
            ap.log(f"ntfy-note send failed ({type(e).__name__}), try {i + 1} of 3")
        time.sleep(10 * (i + 1))
    ap.log(f"ntfy-note NOT sent: {title}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
