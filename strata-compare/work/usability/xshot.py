#!/usr/bin/env python3
"""xshot.py OUT.png [x y w h] - screenshot of the X screen (or a region) through GDK; works while the monitor sleeps."""
import sys
import gi
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk  # noqa: E402

root = Gdk.get_default_root_window()
x, y, w, h = (map(int, sys.argv[2:6]) if len(sys.argv) >= 6 else (0, 0, root.get_width(), root.get_height()))
pb = Gdk.pixbuf_get_from_window(root, x, y, w, h)
pb.savev(sys.argv[1], "png", [], [])
print(sys.argv[1], w, h)
