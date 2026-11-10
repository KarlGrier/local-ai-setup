#!/usr/bin/env python3
"""calc-mcp.py - an MCP server (stdio) with one tool, `calculate`, for Jan (2026-10-28, Karl: "a sandboxed calculator
tool (arithmetic, units, percentages; no file or network access)").

Jan starts it as: /usr/bin/unshare -rn /usr/bin/python3 -I <this file>. The user namespace without a network leaves the
process no network at all. After start-up it also limits itself: no new files (RLIMIT_NOFILE at the descriptors it has),
no file writes (RLIMIT_FSIZE 0), 512 MB of memory, and 2 s per calculation (SIGALRM). It never uses eval or exec: the
expression is parsed by the small recursive-descent parser below, which knows numbers, + - * / ^ (or **), parentheses,
%, a few functions and constants, and units. Standard library only; nothing is logged to a file (errors go to stderr,
which Jan keeps in its own log).

Units: data (B, kB..PB, KiB..PiB, bit, Mbit, Gbit, bps..Gbps), time (ns..year), frequency (Hz..GHz), transfers (MT, GT:
"6000 MT/s"), energy and power (J, kJ, Wh, kWh, MWh, W, kW, MW), length (mm, cm, m, km, in, ft), mass (g, kg, lb),
money (USD or $, EUR or €: no exchange rates), tokens (tok). A unit binds to the number before it ("1.8 GB/s"); "to" or
"in" at the end converts ("350 W * 24 h to kWh"). "15% of 2804" multiplies; "2804 + 15%" means 2804 increased by 15 %.
"""
from __future__ import annotations

import json
import math
import re
import signal
import sys
from fractions import Fraction

MAX_LEN, MAX_TOKENS, MAX_DEPTH, MAX_LOG10 = 400, 200, 40, 300
TIME_LIMIT_S = 2

# ------------------------------------------------------------------------------------------------ units
# name -> (factor to base units, {dimension: power}); dimensions: B (byte), s, J, m, g, USD, EUR, tok
_D = Fraction


def _u(f, **dims):
    return (_D(f), {k: v for k, v in dims.items() if v})


UNITS: dict[str, tuple[Fraction, dict]] = {}
for n, f in (("B", 1), ("kB", 10**3), ("KB", 10**3), ("MB", 10**6), ("GB", 10**9), ("TB", 10**12), ("PB", 10**15),
             ("KiB", 2**10), ("MiB", 2**20), ("GiB", 2**30), ("TiB", 2**40), ("PiB", 2**50),
             ("bit", _D(1, 8)), ("kbit", _D(10**3, 8)), ("Mbit", _D(10**6, 8)), ("Gbit", _D(10**9, 8)),
             ("Tbit", _D(10**12, 8))):
    UNITS[n] = _u(f, B=1)
for n, f in (("bps", _D(1, 8)), ("kbps", _D(10**3, 8)), ("Mbps", _D(10**6, 8)), ("Gbps", _D(10**9, 8))):
    UNITS[n] = _u(f, B=1, s=-1)
for n, f in (("ns", _D(1, 10**9)), ("us", _D(1, 10**6)), ("µs", _D(1, 10**6)), ("ms", _D(1, 1000)), ("s", 1),
             ("sec", 1), ("second", 1), ("seconds", 1), ("min", 60), ("minute", 60), ("minutes", 60), ("h", 3600),
             ("hr", 3600), ("hour", 3600), ("hours", 3600), ("day", 86400), ("days", 86400), ("week", 604800),
             ("weeks", 604800), ("year", 31557600), ("years", 31557600)):
    UNITS[n] = _u(f, s=1)
for n, f in (("Hz", 1), ("kHz", 10**3), ("MHz", 10**6), ("GHz", 10**9)):
    UNITS[n] = _u(f, s=-1)
for n, f in (("T", 1), ("kT", 10**3), ("MT", 10**6), ("GT", 10**9)):     # transfers: counts ("6000 MT/s")
    UNITS[n] = _u(f)
for n, f in (("J", 1), ("kJ", 10**3), ("MJ", 10**6), ("Wh", 3600), ("kWh", 3600 * 10**3), ("MWh", 3600 * 10**6)):
    UNITS[n] = _u(f, J=1)
for n, f in (("mW", _D(1, 1000)), ("W", 1), ("kW", 10**3), ("MW", 10**6)):
    UNITS[n] = _u(f, J=1, s=-1)
for n, f in (("mm", _D(1, 1000)), ("cm", _D(1, 100)), ("m", 1), ("km", 1000), ("in", _D(254, 10000)),
             ("inch", _D(254, 10000)), ("ft", _D(3048, 10000))):
    UNITS[n] = _u(f, m=1)
for n, f in (("g", 1), ("kg", 1000), ("lb", _D(45359237, 100000))):
    UNITS[n] = _u(f, g=1)
for n in ("USD", "$"):
    UNITS[n] = _u(1, USD=1)
for n in ("EUR", "€"):
    UNITS[n] = _u(1, EUR=1)
for n in ("tok", "token", "tokens"):
    UNITS[n] = _u(1, tok=1)

# how a result in these dimensions is shown when the expression gives no better unit (smallest first; the largest
# unit whose value is >= 1 wins)
SCALES = [
    ({"B": 1}, ["B", "kB", "MB", "GB", "TB", "PB"]),
    ({"B": 1, "s": -1}, ["B/s", "kB/s", "MB/s", "GB/s", "TB/s"]),
    ({"s": 1}, ["ns", "us", "ms", "s", "min", "h", "day"]),
    ({"J": 1}, ["J", "kJ", "Wh", "kWh", "MWh"]),
    ({"J": 1, "s": -1}, ["mW", "W", "kW", "MW"]),
    ({"s": -1}, ["Hz", "kHz", "MHz", "GHz"]),
    ({"m": 1}, ["mm", "cm", "m", "km"]),
]


class CalcError(Exception):
    pass


class Q:
    """A quantity: an exact (Fraction) or float value in base units, and its dimensions."""
    __slots__ = ("v", "d", "pct")

    def __init__(self, v, d=None, pct=False):
        self.v, self.d, self.pct = v, dict(d or {}), pct

    def same(self, o):
        if self.d != o.d:
            raise CalcError(f"cannot add or compare {dims_str(self.d)} and {dims_str(o.d)}")


def dims_str(d: dict) -> str:
    return " ".join(f"{k}^{v}" if v != 1 else k for k, v in sorted(d.items())) or "a plain number"


def _mul_d(a, b, sign=1):
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, 0) + sign * v
        if not out[k]:
            del out[k]
    return out


def _check(v):
    try:
        if v and abs(v) > 10 ** MAX_LOG10:
            raise CalcError("the number is too large")
    except OverflowError:
        raise CalcError("the number is too large") from None
    return v


# ------------------------------------------------------------------------------------------------ tokens
_TOK = re.compile(r"""\s*(?:
    (?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)
  | (?P<op>\*\*|[-+*/^()%,×÷·−])
  | (?P<word>[A-Za-z_µ][A-Za-z_0-9µ]*|[$€])
)""", re.X)


def tokens(s: str) -> list[tuple[str, str]]:
    s = s.strip()
    if len(s) > MAX_LEN:
        raise CalcError(f"the expression is longer than {MAX_LEN} characters")
    out, i = [], 0
    while i < len(s):
        m = _TOK.match(s, i)
        if not m or m.end() == i:
            if s[i:].strip() == "":
                break
            raise CalcError(f"cannot read the expression at: {s[i:i + 20]!r}")
        i = m.end()
        kind = m.lastgroup
        val = m.group(kind)
        val = {"×": "*", "·": "*", "÷": "/", "−": "-", "**": "^"}.get(val, val)
        out.append((kind, val))
        if len(out) > MAX_TOKENS:
            raise CalcError("the expression is too long")
    return out


FUNCS = {"sqrt": math.sqrt, "cbrt": lambda x: math.copysign(abs(x) ** (1 / 3), x), "ln": math.log,
         "log10": math.log10, "log2": math.log2, "exp": math.exp, "sin": math.sin, "cos": math.cos, "tan": math.tan,
         "asin": math.asin, "acos": math.acos, "atan": math.atan, "floor": math.floor, "ceil": math.ceil}
MULTI = ("abs", "round", "min", "max", "log")
CONSTS = {"pi": math.pi, "e": math.e}


# ------------------------------------------------------------------------------------------------ parser
class Parser:
    def __init__(self, toks):
        self.t, self.i, self.depth, self.seen_units = toks, 0, 0, []

    def peek(self, k=0):
        return self.t[self.i + k] if self.i + k < len(self.t) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expect(self, val):
        if self.peek()[1] != val:
            raise CalcError(f"expected {val!r}")
        self.take()

    def deeper(self):
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise CalcError("the expression is nested too deeply")

    def is_unit(self, k=0):
        kind, val = self.peek(k)
        # "min" is minutes unless a "(" follows (then it is the function)
        return kind == "word" and val in UNITS and val not in CONSTS and self.peek(k + 1)[1] != "("

    def top(self):
        q = self.expr()
        target = None
        if self.peek()[0] == "word" and self.peek()[1] in ("to", "in", "as") and (
                self.is_unit(1) or self.peek(1)[1] == "%"):
            self.take()
            if self.peek()[1] == "%":
                self.take()
                target = "%"
            else:
                target = self.unit_expr()
        if self.peek()[0] is not None:
            raise CalcError(f"unexpected {self.peek()[1]!r}")
        return q, target

    def expr(self):
        self.deeper()
        q = self.term()
        while self.peek()[1] in ("+", "-"):
            op = self.take()[1]
            r = self.term()
            if r.pct and not r.d:                       # "2804 + 15%": increased by 15 %
                q = Q(_check(q.v * (1 + r.v if op == "+" else 1 - r.v)), q.d)
                continue
            q.same(r)
            q = Q(_check(q.v + r.v if op == "+" else q.v - r.v), q.d)
        self.depth -= 1
        return q

    def term(self):
        q = self.unary()
        while True:
            kind, val = self.peek()
            if val in ("*", "/"):
                self.take()
                r = self.unary()
                if val == "*":
                    q = Q(_check(q.v * r.v), _mul_d(q.d, r.d))
                else:
                    if r.v == 0:
                        raise CalcError("division by zero")
                    q = Q(_check(q.v / r.v), _mul_d(q.d, r.d, -1))
            elif kind == "word" and val == "of" and q.pct:  # "15% of 2804"
                self.take()
                r = self.unary()
                q = Q(_check(q.v * r.v), _mul_d(q.d, r.d))
            else:
                return q

    def unary(self):
        if self.peek()[1] == "-":
            self.take()
            q = self.unary()
            return Q(-q.v, q.d, q.pct)
        if self.peek()[1] == "+":
            self.take()
            return self.unary()
        return self.power()

    def power(self):
        q = self.postfix()
        if self.peek()[1] == "^":
            self.take()
            e = self.unary()                            # right-associative: 2^3^2 = 2^9
            if e.d:
                raise CalcError("an exponent must be a plain number")
            ev = e.v
            if q.d and (not isinstance(ev, Fraction) or ev.denominator != 1):
                raise CalcError("a quantity with units can only be raised to a whole power")
            if q.v and abs(float(ev)) * abs(math.log10(abs(float(q.v)))) > MAX_LOG10:
                raise CalcError("the number is too large")      # checked before computing: 9^9^9 never runs
            if isinstance(ev, Fraction) and ev.denominator == 1 and isinstance(q.v, Fraction) and abs(ev) <= 1000:
                v = q.v ** int(ev) if q.v or ev >= 0 else None
                if v is None:
                    raise CalcError("division by zero")
            else:
                try:
                    v = float(q.v) ** float(ev)
                except (OverflowError, ZeroDivisionError):
                    raise CalcError("the number is too large or undefined") from None
                if isinstance(v, complex):
                    raise CalcError("the result is not a real number")
            q = Q(_check(v), {k: p * int(ev) for k, p in q.d.items()})
        return q

    def postfix(self):
        q = self.primary()
        if self.peek()[1] == "%":
            self.take()
            q = Q(q.v / 100, q.d, pct=True)
        if self.is_unit():
            f, d = self.unit_expr_q()
            q = Q(_check(q.v * f), _mul_d(q.d, d))
        return q

    def unit_expr_q(self):
        """A unit written after a number: GB, GB/s, kW*h, m^2."""
        name = self.take()[1]
        self.seen_units.append(name)
        f, d = UNITS[name]
        if self.peek()[1] == "^" and self.peek(1)[0] == "num":
            self.take()
            p = int(float(self.take()[1]))
            f, d = f ** p, {k: v * p for k, v in d.items()}
        while self.peek()[1] in ("/", "*") and self.is_unit(1):
            op = self.take()[1]
            n2 = self.take()[1]
            self.seen_units.append(n2)
            f2, d2 = UNITS[n2]
            f, d = (f * f2, _mul_d(d, d2)) if op == "*" else (f / f2, _mul_d(d, d2, -1))
        return f, d

    def unit_expr(self):
        start = self.i
        f, d = self.unit_expr_q()
        return ("".join(v for _, v in self.t[start:self.i]), f, d)

    def primary(self):
        kind, val = self.peek()
        if kind == "num":
            self.take()
            s = val.replace(",", "")
            if re.fullmatch(r"\d+", s):
                return Q(Fraction(int(s)))
            try:
                return Q(Fraction(s))
            except ValueError:
                return Q(float(s))
        if val == "(":
            self.take()
            q = self.expr()
            self.expect(")")
            return q
        if kind == "word" and (val in FUNCS or val in MULTI) and self.peek(1)[1] == "(":
            self.take()
            self.take()
            args = [self.expr()]
            while self.peek()[1] == ",":
                self.take()
                args.append(self.expr())
            self.expect(")")
            return self.call(val, args)
        if kind == "word" and val in CONSTS:
            self.take()
            return Q(CONSTS[val])
        if val in ("$", "€") and self.peek(1)[0] == "num":   # a currency sign before the number: "$2,804"
            self.take()
            q = self.primary()
            f, d = UNITS[val]
            self.seen_units.append(val)
            return Q(q.v * f, _mul_d(q.d, d))
        if self.is_unit():                               # a bare unit: "GB to MiB", "$ * 3"
            f, d = self.unit_expr_q()
            return Q(f, d)
        if kind is None:
            raise CalcError("the expression ends too early")
        raise CalcError(f"unknown name or symbol {val!r}")

    def call(self, name, args):
        if name in ("min", "max"):
            for a in args[1:]:
                args[0].same(a)
            pick = (min if name == "min" else max)(args, key=lambda a: a.v)
            return Q(pick.v, pick.d)
        if name == "abs":
            return Q(abs(args[0].v), args[0].d)
        if name == "round":
            nd = int(args[1].v) if len(args) > 1 else 0
            x = Fraction(args[0].v) * Fraction(10) ** nd                # halves away from zero, as on a calculator
            r = Fraction(math.floor(abs(x) + Fraction(1, 2))) / Fraction(10) ** nd
            return Q(r if x >= 0 else -r, args[0].d)
        if name == "log":
            if any(a.d for a in args):
                raise CalcError("log takes plain numbers")
            try:
                return Q(math.log(float(args[0].v), float(args[1].v)) if len(args) > 1 else math.log10(float(args[0].v)))
            except (ValueError, ZeroDivisionError):
                raise CalcError("log of a number that is not positive") from None
        if len(args) != 1 or args[0].d:
            raise CalcError(f"{name} takes one plain number")
        try:
            return Q(_check(float(FUNCS[name](float(args[0].v)))))
        except (ValueError, OverflowError):
            raise CalcError(f"{name} is not defined for {fmt(args[0].v)}") from None


# ------------------------------------------------------------------------------------------------ output
def fmt(v) -> str:
    if isinstance(v, Fraction) and v.denominator == 1 and abs(v) < 10**15:
        return f"{int(v):,}"
    x = float(v)
    if x == 0:
        return "0"
    s = f"{x:.10g}"                                      # 10 significant digits
    if "e" in s:
        return s
    ip, _, fp = s.partition(".")
    return f"{'-' if ip.startswith('-') else ''}{int(ip.lstrip('-')):,}" + (f".{fp}" if fp else "")


def show(q: Q, seen: list[str], target) -> str:
    if target == "%":
        if q.d:
            raise CalcError(f"only a plain number can be shown in %, this is {dims_str(q.d)}")
        return f"{fmt(q.v * 100)} %"
    if target:
        label, f, d = target
        if d != q.d:
            raise CalcError(f"cannot convert {dims_str(q.d)} to {label} ({dims_str(d)})")
        return f"{fmt(q.v / f)} {label}"
    if not q.d:
        return fmt(q.v)
    cands = []
    for n in seen:                                       # a unit from the expression with these dimensions
        if UNITS[n][1] == q.d:
            cands.append((n, UNITS[n][0]))
    for a in seen:                                       # or a ratio / product of two of them (GB/s, kW*h)
        for b in seen:
            fa, da = UNITS[a]
            fb, db = UNITS[b]
            if _mul_d(da, db, -1) == q.d:
                cands.append((f"{a}/{b}", fa / fb))
            if _mul_d(da, db) == q.d and a != b:
                cands.append((f"{a}*{b}", fa * fb))
    for dims, names in SCALES:
        if dims == q.d:
            best = names[0]
            for n in names:
                f = UNITS[n][0] if n in UNITS else UNITS[n.split("/")[0]][0] / UNITS[n.split("/")[1]][0]
                if abs(q.v) >= f:
                    best = n
            f = UNITS[best][0] if best in UNITS else UNITS[best.split("/")[0]][0] / UNITS[best.split("/")[1]][0]
            if not cands or cands[0][0] != best:
                cands.append((best, f))
            break
    if not cands:
        return f"{fmt(q.v)} (base units: {dims_str(q.d)})"
    # the first unit that puts the number between 1 and 1,000 (96 GB/s, not 96,000,000,000 B/s), else the first one
    main = next((cd for cd in cands if 1 <= abs(q.v / cd[1]) < 1000), cands[0])
    cands = [main] + [cd for cd in cands if cd != main]
    out = f"{fmt(q.v / main[1])} {main[0]}"
    extra = [f"{fmt(q.v / f)} {n}" for n, f in cands[1:3] if n != main[0]]
    return out + (f"  (= {', '.join(dict.fromkeys(extra))})" if extra else "")


def calculate(expression: str) -> str:
    p = Parser(tokens(expression))
    if not p.t:
        raise CalcError("the expression is empty")
    q, target = p.top()
    return f"{expression.strip()} = {show(q, p.seen_units, target)}"


# ------------------------------------------------------------------------------------------------ MCP (stdio)
TOOLS = [{
    "name": "calculate",
    "description": "Exact arithmetic for numbers already in the conversation: + - * / ^, parentheses, %, sqrt/log/"
                   "round/min/max, and units with conversion (GB, GiB, MB/s, Gbps, W, kWh, h, ms, MT/s, $; end with "
                   "'to <unit>' or 'to %'). Use it for multi-step or unit arithmetic instead of working it out in "
                   "your head; not for questions that need no calculation. Units carry through, so convert with 'to', "
                   "never by dividing by 60 or 1000 yourself. Examples: '138 GB / 1.8 GB/s to min', '75 GB / 11.4 MB', "
                   "'6000 MT/s * 8 B * 2 to GB/s', '350 W * 24 h to kWh', '15% of 2804', '(2816 - 2804) / 2804 to %'.",
    "inputSchema": {"type": "object", "properties": {
        "expression": {"type": "string", "description": "The calculation, e.g. '138 GB / 1.8 GB/s'. Separate "
                                                        "function arguments with ', ' (a comma and a space)."}},
        "required": ["expression"]}}]
INSTRUCTIONS = "calculate does exact arithmetic with units; it has no network or file access."


def _alarm(signum, frame):
    raise CalcError(f"the calculation took longer than {TIME_LIMIT_S} s")


def reply(msg_id, result=None, error=None) -> None:
    out = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        out["error"] = error
    else:
        out["result"] = result
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(msg: dict) -> None:
    method, mid = msg.get("method"), msg.get("id")
    if method == "initialize":
        pv = (msg.get("params") or {}).get("protocolVersion") or "2025-06-18"
        return reply(mid, {"protocolVersion": pv, "capabilities": {"tools": {"listChanged": False}},
                           "serverInfo": {"name": "calculator", "version": "1.0"}, "instructions": INSTRUCTIONS})
    if method in ("notifications/initialized", "notifications/cancelled") or (mid is None and method):
        return None
    if method == "ping":
        return reply(mid, {})
    if method == "tools/list":
        return reply(mid, {"tools": TOOLS})
    if method == "tools/call":
        p = msg.get("params") or {}
        name, args = p.get("name"), p.get("arguments") or {}
        if name != "calculate":
            return reply(mid, {"content": [{"type": "text", "text": f"Unknown tool {name}"}], "isError": True})
        signal.alarm(TIME_LIMIT_S)
        try:
            text, err = calculate(str(args.get("expression") or "")), False
        except CalcError as e:
            text, err = f"Cannot calculate: {e}", True
        except (ArithmeticError, ValueError, TypeError, RecursionError) as e:
            text, err = f"Cannot calculate: {type(e).__name__}", True
        finally:
            signal.alarm(0)
        return reply(mid, {"content": [{"type": "text", "text": text}], "isError": err})
    if mid is not None:
        return reply(mid, error={"code": -32601, "message": f"Method not found: {method}"})
    return None


def sandbox() -> None:
    """No new files, no file writes, bounded memory (the network is already gone: unshare -rn)."""
    import os
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    import stat
    if not stat.S_ISREG(os.fstat(1).st_mode):            # Jan's stdout is a pipe; a test may send it to a file
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    n = len(os.listdir("/proc/self/fd"))
    resource.setrlimit(resource.RLIMIT_NOFILE, (n, n))
    signal.signal(signal.SIGALRM, _alarm)


def main() -> None:
    sandbox()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        for m in msg if isinstance(msg, list) else [msg]:
            handle(m)


if __name__ == "__main__":
    main()
