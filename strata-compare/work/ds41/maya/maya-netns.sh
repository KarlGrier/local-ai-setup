#!/bin/bash
# maya-netns.sh CMD [ARGS...] - PREPARED 10-25 for the Maya head-to-head (not run yet). Runs CMD in a new user + network
# namespace (`unshare -rn`, no root needed here: kernel.apparmor_restrict_unprivileged_userns = 0) whose only interface
# is its own loopback, brought up first: Maya's server, engine, client and the arm's guards then talk over that
# namespace's 127.0.0.1 and reach no network at all. Same PID namespace and file system as outside (pgrep, kill, the
# test lock, /proc, /sys, the GPUs' device nodes all as before).
# NOT VERIFIED (try once in a gap, before the first arm): `bash maya-netns.sh nvidia-smi` (CUDA inside the namespace),
# `bash maya-netns.sh bash bringup/lib/kcheck.sh netns-test` (kill -0 on the kernel-log watcher from inside: same real
# uid, so it should pass), and `bash maya-netns.sh curl -s -m 2 http://example.com` (must fail: no route).
# Keep tune.py-level steps (notify-send, systemctl --user, kernel_event) outside the namespace: wrap the arm script only.
set -u
[ $# -ge 1 ] || { echo "usage: maya-netns.sh CMD [ARGS...]" >&2; exit 2; }
exec unshare -rn bash -c '/usr/sbin/ip link set lo up || { echo "maya-netns: cannot bring lo up" >&2; exit 97; }; exec "$@"' maya-netns "$@"
