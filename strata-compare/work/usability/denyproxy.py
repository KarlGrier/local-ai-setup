#!/usr/bin/env python3
"""denyproxy.py - a proxy that refuses everything and writes down what was asked (usability round).

The usability apps run with HTTP_PROXY / HTTPS_PROXY / ALL_PROXY pointing here and NO_PROXY = loopback, so their traffic
to 127.0.0.1 (Strata on 8080, SearXNG on 8888) goes direct and anything bound for the internet lands here instead: the
request line is logged (time, the client's process when it can be found, CONNECT host:port or the plain-HTTP URL) and
answered 403. Nothing is forwarded. Listens on 127.0.0.1 only.

    python3 denyproxy.py [--port 18999] [--log logs/usability/denied.log]
"""
import argparse
import asyncio
import datetime
import os
import re


def owner_of(peer_port: int) -> str:
    """The local process whose TCP connection uses this source port (from /proc), best effort."""
    try:
        inode = None
        for table in ("/proc/net/tcp", "/proc/net/tcp6"):
            with open(table) as f:
                for line in f.readlines()[1:]:
                    p = line.split()
                    if int(p[1].split(":")[1], 16) == peer_port:
                        inode = p[9]
                        break
            if inode:
                break
        if not inode:
            return "?"
        target = f"socket:[{inode}]"
        for pid in filter(str.isdigit, os.listdir("/proc")):
            try:
                for fd in os.listdir(f"/proc/{pid}/fd"):
                    if os.readlink(f"/proc/{pid}/fd/{fd}") == target:
                        with open(f"/proc/{pid}/comm") as c:
                            return f"{c.read().strip()}({pid})"
            except OSError:
                continue
    except OSError:
        pass
    return "?"


async def handle(reader, writer, log_path):
    peer = writer.get_extra_info("peername")
    who = owner_of(peer[1]) if peer else "?"
    try:
        line = (await asyncio.wait_for(reader.readline(), 10)).decode("latin-1").strip()
    except Exception:
        line = "(no request line)"
    m = re.match(r"^(CONNECT|GET|POST|PUT|HEAD|OPTIONS|DELETE|PATCH)\s+(\S+)", line)
    target = f"{m.group(1)} {m.group(2)}" if m else line[:200]
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    with open(log_path, "a") as f:
        f.write(f"{stamp}\t{who}\t{target}\n")
    try:
        writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        await writer.drain()
    finally:
        writer.close()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18999)
    ap.add_argument("--log", default=os.path.expanduser("~/.local/state/denyproxy/denied.log"))
    a = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(a.log)), exist_ok=True)
    server = await asyncio.start_server(lambda r, w: handle(r, w, a.log), "127.0.0.1", a.port)
    print(f"denyproxy on 127.0.0.1:{a.port}, log {a.log}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
