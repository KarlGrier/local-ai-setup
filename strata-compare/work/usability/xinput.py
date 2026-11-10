#!/usr/bin/env python3
"""xinput.py - synthetic mouse and keyboard on the X display (XTEST), plus a clipboard owner, for the Jan checks.

    xinput.py click X Y          left click at screen pixel X, Y
    xinput.py key ctrl+v         a key or combination (names: ctrl, shift, alt, Return, Escape, Tab, BackSpace, letters)
    xinput.py type "text"        type plain ASCII text
    xinput.py clip FILE [SECS]   own the CLIPBOARD with FILE's text for SECS seconds (default 120), for a ctrl+v paste
"""
import ctypes
import sys
import time

X11 = ctypes.cdll.LoadLibrary("libX11.so.6")
XTST = ctypes.cdll.LoadLibrary("libXtst.so.6")
X11.XOpenDisplay.restype = ctypes.c_void_p
X11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
X11.XStringToKeysym.restype = ctypes.c_ulong
X11.XStringToKeysym.argtypes = [ctypes.c_char_p]
XTST.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
XTST.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
XTST.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
X11.XFlush.argtypes = [ctypes.c_void_p]
ALIAS = {"ctrl": "Control_L", "shift": "Shift_L", "alt": "Alt_L", "enter": "Return", "esc": "Escape", " ": "space"}


def disp():
    d = X11.XOpenDisplay(None)
    if not d:
        raise SystemExit("cannot open the X display")
    return d


def keycode(d, name):
    name = ALIAS.get(name, name)
    ks = X11.XStringToKeysym(name.encode())
    if not ks:
        raise SystemExit(f"unknown key {name!r}")
    return X11.XKeysymToKeycode(d, ks)


def click(x, y, button=1):
    d = disp()
    XTST.XTestFakeMotionEvent(d, -1, x, y, 0)
    X11.XFlush(d)
    time.sleep(0.15)
    XTST.XTestFakeButtonEvent(d, button, 1, 0)
    XTST.XTestFakeButtonEvent(d, button, 0, 0)
    X11.XFlush(d)


def combo(spec):
    d = disp()
    codes = [keycode(d, k) for k in spec.split("+")]
    for c in codes:
        XTST.XTestFakeKeyEvent(d, c, 1, 0)
    for c in reversed(codes):
        XTST.XTestFakeKeyEvent(d, c, 0, 0)
    X11.XFlush(d)


def type_text(text):
    d = disp()
    shift = keycode(d, "Shift_L")
    upper_syms = {'"': "quotedbl", "!": "exclam", "?": "question", ":": "colon", "(": "parenleft", ")": "parenright",
                  "_": "underscore", "+": "plus", "*": "asterisk", "&": "ampersand", "%": "percent", "@": "at"}
    plain = {" ": "space", ".": "period", ",": "comma", "-": "minus", "/": "slash", "'": "apostrophe", "=": "equal",
             ";": "semicolon", "\n": "Return"}
    for ch in text:
        need_shift = ch.isupper() or ch in upper_syms
        name = upper_syms.get(ch) or plain.get(ch) or ch
        c = keycode(d, name)
        if need_shift:
            XTST.XTestFakeKeyEvent(d, shift, 1, 0)
        XTST.XTestFakeKeyEvent(d, c, 1, 0)
        XTST.XTestFakeKeyEvent(d, c, 0, 0)
        if need_shift:
            XTST.XTestFakeKeyEvent(d, shift, 0, 0)
        X11.XFlush(d)
        time.sleep(0.01)


def clip(path, secs):
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GLib, Gtk
    cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    cb.set_text(open(path).read(), -1)
    cb.store()
    GLib.timeout_add_seconds(secs, Gtk.main_quit)
    print("clipboard owned for", secs, "s", flush=True)
    Gtk.main()


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "click":
        click(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == "key":
        combo(sys.argv[2])
    elif cmd == "type":
        type_text(sys.argv[2])
    elif cmd == "clip":
        clip(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 120)
