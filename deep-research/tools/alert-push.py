#!/usr/bin/python3 -I
"""alert-push.py (11-06, Karl: "Alerts: B, ntfy.sh. Use a long random topic name, short path-free messages, alerts
only.") - forwards the CRITICAL desktop alerts of this PC's own automation to Karl's phone through ntfy.sh.

How: watches the session bus as a monitor (org.freedesktop.DBus.Monitoring.BecomeMonitor) for Notify calls - every
script's `notify-send -u critical` - so no script changes. Forwarded only when the urgency is critical AND the app
name is one of ours (APPS); other programs' notifications never leave the PC. Each message is cut to a short title +
one short line with every path, ~, @, IP (except 127.0.0.1), UUID / long hex, the user name and the host name
removed; the details stay in NOTES.md. Duplicates within 15 min are dropped; at most 20 per hour (then one "more
alerts" line). The topic is read from ~/.config/alert-push/topic (mode 600) inside this code only - never printed or
logged. Log: ~/ai/deep-research/logs/alert-push.log (titles only).
Unit: ~/.config/systemd/user/alert-push.service (enabled; Restart=always).
"""
import getpass, json, os, queue, re, socket, sys, threading, time, urllib.request

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

APPS = {"Strata gaps", "Deep research", "Weekend watch", "Kernel watch", "Boot resume", "DeepSeek-V4.1",
        "DeepSeek-V4.1 download", "Strata tag watch", "Strata release check", "Strata port", "Strata", "GPU queue",
        "start check", "Gap series", "Measurement queue", "Opus 4.5 hard set", "Sonnet 4.6 hard set", "Frontier set"}
TOPIC_FILE = os.path.expanduser("~/.config/alert-push/topic")
LOG = os.path.expanduser("~/ai/deep-research/logs/alert-push.log")
URL = "https://ntfy.sh/"
DEDUP_S, PER_HOUR = 900, 20

_user, _host = getpass.getuser(), socket.gethostname()


def log(line: str) -> None:
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%F %T')} alert-push: {line}\n")


def clean(s: str, n: int) -> str:
    """Short and path-free: no paths, ~, @, IPs (127.0.0.1 kept), UUIDs / long hex, user or host name."""
    s = s.replace("\n", " ").replace("\t", " ")
    s = re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", "", s)
    s = re.sub(r"\b(?!127\.0\.0\.1\b)\d{1,3}(\.\d{1,3}){3}\b", "", s)
    s = " ".join(w for w in s.split() if not any(c in w for c in "/~@\\"))
    s = re.sub(r"\b[0-9a-fA-F]{16,}\b", "", s)
    for name in {_user, _host, _host.split(".")[0]}:
        if name:
            s = re.sub(re.escape(name), "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" -:;,")
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def topic() -> str:
    with open(TOPIC_FILE) as f:
        t = f.read().strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,64}", t):
        raise SystemExit("alert-push: the topic file does not hold a 32-64 character topic")
    return t


def post(title: str, msg: str) -> bool:
    data = (msg or title).encode()
    hdr = {"Title": title.encode("ascii", "replace").decode(), "Priority": "high", "Tags": "warning"}
    for i in range(3):
        try:
            req = urllib.request.Request(URL + topic(), data=data, headers=hdr, method="POST")
            with urllib.request.urlopen(req, timeout=20) as r:
                if r.status == 200:
                    return True
        except Exception as e:  # noqa: BLE001 - logged without the URL
            log(f"send failed ({type(e).__name__}), try {i + 1} of 3")
        time.sleep(10 * (i + 1))
    return False


Q: "queue.Queue[tuple[str, str]]" = queue.Queue()
_seen: dict[str, float] = {}
_sent: list[float] = []


def sender() -> None:
    capped_note = 0.0
    while True:
        title, msg = Q.get()
        now = time.time()
        key = title + "|" + msg
        if now - _seen.get(key, 0) < DEDUP_S:
            continue
        _seen[key] = now
        _sent[:] = [t for t in _sent if now - t < 3600]
        if len(_sent) >= PER_HOUR:
            if now - capped_note > 3600:
                capped_note = now
                post("More alerts", "Over 20 alerts this hour - the rest are on the PC (NOTES.md).")
            log(f"over {PER_HOUR}/h - not sent: {title}")
            continue
        ok = post(title, msg)
        _sent.append(now)
        log(f"{'sent' if ok else 'NOT sent'}: {title}")


def on_message(conn, msg, incoming, *_):
    # only the monitored method calls are consumed here; replies (BecomeMonitor's own) and signals pass on
    if not incoming or msg.get_message_type() != Gio.DBusMessageType.METHOD_CALL:
        return msg
    try:
        if msg.get_member() == "Notify" and msg.get_interface() == "org.freedesktop.Notifications":
            body = msg.get_body()
            if body is not None and body.n_children() >= 8:
                app, _rid, _icon, summary, text, _actions, hints, _to = body.unpack()
                urg = hints.get("urgency")
                if app in APPS and urg == 2:
                    Q.put((clean(f"{app}: {summary}", 90), clean(text, 180)))
    except Exception as e:  # noqa: BLE001
        log(f"filter error {type(e).__name__}")
    return None   # a monitor connection: consume


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        topic(); print("alert-push: topic file ok"); return
    topic()
    addr = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
    conn = Gio.DBusConnection.new_for_address_sync(
        addr, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
    conn.add_filter(on_message)
    conn.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus.Monitoring", "BecomeMonitor",
                   GLib.Variant("(asu)", (["type='method_call',interface='org.freedesktop.Notifications',member='Notify'"], 0)),
                   None, Gio.DBusCallFlags.NONE, -1, None)
    threading.Thread(target=sender, daemon=True).start()
    log(f"start (pid {os.getpid()}): forwarding critical alerts of {len(APPS)} app names")
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
