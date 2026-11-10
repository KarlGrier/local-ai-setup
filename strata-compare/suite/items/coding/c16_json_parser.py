LEVEL = "hard"
KIND = "parsing"
ENTRY = "parse_json"
PROMPT = """Write a Python function `parse_json(text: str)` that parses JSON text (RFC 8259) without using the `json` module (or any other parser library).

Requirements:
- Values: objects -> dict (if a key repeats, the last value wins), arrays -> list, strings -> str, `true`/`false` -> bool, `null` -> None.
- Numbers follow the JSON grammar exactly: optional minus, no leading zeros ("01" is invalid, "0" and "-0" are fine), optional fraction, optional exponent. A number with no fraction and no exponent becomes an int; any other number becomes a float.
- Strings: the escapes \\" \\\\ \\/ \\b \\f \\n \\r \\t and \\uXXXX (a high and a low surrogate written as two \\u escapes combine into one character). Raw control characters (U+0000 to U+001F) inside a string are invalid.
- Whitespace between tokens is only space, tab, line feed and carriage return.
- The text must contain exactly one value (surrounded by optional whitespace).
- Raise `ValueError` for anything invalid: trailing commas, single quotes, unquoted keys, NaN/Infinity, bad escapes, unterminated strings or containers, extra text after the value, and so on.
- Nesting depth up to at least 500 must work.
"""

GOOD = r'''
_WS = " \t\n\r"
_ESC = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}


class _P:
    def __init__(self, s):
        self.s = s
        self.i = 0

    def ws(self):
        s, i = self.s, self.i
        while i < len(s) and s[i] in _WS:
            i += 1
        self.i = i

    def err(self, msg):
        raise ValueError("%s at %d" % (msg, self.i))

    def value(self):
        self.ws()
        if self.i >= len(self.s):
            self.err("unexpected end")
        c = self.s[self.i]
        if c == "{":
            return self.obj()
        if c == "[":
            return self.arr()
        if c == '"':
            return self.string()
        if c == "-" or c.isdigit():
            return self.number()
        for lit, val in (("true", True), ("false", False), ("null", None)):
            if self.s.startswith(lit, self.i):
                self.i += len(lit)
                return val
        self.err("unexpected character")

    def obj(self):
        self.i += 1
        out = {}
        self.ws()
        if self.i < len(self.s) and self.s[self.i] == "}":
            self.i += 1
            return out
        while True:
            self.ws()
            if self.i >= len(self.s) or self.s[self.i] != '"':
                self.err("expected key")
            k = self.string()
            self.ws()
            if self.i >= len(self.s) or self.s[self.i] != ":":
                self.err("expected ':'")
            self.i += 1
            out[k] = self.value()
            self.ws()
            if self.i >= len(self.s):
                self.err("unterminated object")
            c = self.s[self.i]
            self.i += 1
            if c == "}":
                return out
            if c != ",":
                self.err("expected ',' or '}'")

    def arr(self):
        self.i += 1
        out = []
        self.ws()
        if self.i < len(self.s) and self.s[self.i] == "]":
            self.i += 1
            return out
        while True:
            out.append(self.value())
            self.ws()
            if self.i >= len(self.s):
                self.err("unterminated array")
            c = self.s[self.i]
            self.i += 1
            if c == "]":
                return out
            if c != ",":
                self.err("expected ',' or ']'")

    def hex4(self):
        h = self.s[self.i:self.i + 4]
        if len(h) != 4 or any(ch not in "0123456789abcdefABCDEF" for ch in h):
            self.err("bad \\u escape")
        self.i += 4
        return int(h, 16)

    def string(self):
        self.i += 1
        buf = []
        s = self.s
        while True:
            if self.i >= len(s):
                self.err("unterminated string")
            c = s[self.i]
            if c == '"':
                self.i += 1
                return "".join(buf)
            if ord(c) < 0x20:
                self.err("control character in string")
            if c == "\\":
                self.i += 1
                if self.i >= len(s):
                    self.err("unterminated escape")
                e = s[self.i]
                self.i += 1
                if e in _ESC:
                    buf.append(_ESC[e])
                elif e == "u":
                    cp = self.hex4()
                    if 0xD800 <= cp < 0xDC00 and s.startswith("\\u", self.i):
                        save = self.i
                        self.i += 2
                        lo = self.hex4()
                        if 0xDC00 <= lo < 0xE000:
                            cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00)
                        else:
                            self.i = save
                    buf.append(chr(cp))
                else:
                    self.err("bad escape")
            else:
                buf.append(c)
                self.i += 1

    def number(self):
        s, start = self.s, self.i
        i = start
        if i < len(s) and s[i] == "-":
            i += 1
        if i >= len(s) or not s[i].isascii() or not s[i].isdigit():
            self.err("bad number")
        if s[i] == "0":
            i += 1
        else:
            while i < len(s) and s[i] in "0123456789":
                i += 1
        isfloat = False
        if i < len(s) and s[i] == ".":
            i += 1
            j = i
            while i < len(s) and s[i] in "0123456789":
                i += 1
            if i == j:
                self.err("bad fraction")
            isfloat = True
        if i < len(s) and s[i] in "eE":
            i += 1
            if i < len(s) and s[i] in "+-":
                i += 1
            j = i
            while i < len(s) and s[i] in "0123456789":
                i += 1
            if i == j:
                self.err("bad exponent")
            isfloat = True
        self.i = i
        txt = s[start:i]
        return float(txt) if isfloat else int(txt)


def parse_json(text):
    if not isinstance(text, str):
        raise ValueError("not a string")
    p = _P(text)
    v = p.value()
    p.ws()
    if p.i != len(text):
        p.err("extra data")
    return v
'''

BAD = r'''
import re
import ast


def parse_json(text):
    t = text.strip()
    if not t:
        raise ValueError("empty")
    t = re.sub(r",\s*([\]}])", r"\1", t)
    t = re.sub(r"\btrue\b", "True", t)
    t = re.sub(r"\bfalse\b", "False", t)
    t = re.sub(r"\bnull\b", "None", t)
    try:
        return ast.literal_eval(t)
    except Exception as e:
        raise ValueError(str(e))
'''

# ==== HIDDEN TESTS ====
import json as _json

_VALID = [
    '0', '-0', '12', '-12', '1.5', '-0.25', '1e3', '1E+3', '2.5e-3', '0.0', '1e400', '123456789012345678901234567890',
    '"plain"', '"esc \\" \\\\ \\/ \\b \\f \\n \\r \\t"', '"\\u00e9\\u4e2d"', '"\\ud83d\\ude00"', '"\\ud800"', '""',
    'true', 'false', 'null', '[]', '{}', '[1, [2, [3, []]]]', '{"a": 1, "b": [true, false, null]}',
    '  {"a" : {"b" : {"c" : "d"}}}  ', '{"dup": 1, "dup": 2}', '[1,2 ,3\t,\n4\r]', '"tab\\tthere"',
    '{"": ""}', '["é raw unicode ok"]', '{"k\\u0041": "v"}',
]
_INVALID = [
    '', ' ', '[1,]', '{"a":1,}', "'x'", '{a: 1}', 'NaN', 'Infinity', '-Infinity', '01', '-01', '1.', '.5', '+1',
    '1e', '1e+', '"abc', '"\\x41"', '"\\u12G4"', '[1 2]', '{"a" 1}', '{"a":1 "b":2}', '[', ']', '{', 'tru', 'nul',
    '1 2', '[1]x', '"a"\x0b', '"\x01"', '"line\nbreak"', '{"a":1}}', '[[]', ' []', '0x10', '- 1', '"\\"',
]


def test_valid_against_json(sol):
    for s in _VALID:
        got = sol.parse_json(s)
        exp = _json.loads(s)
        assert got == exp and type(got) is type(exp), s


def test_int_float_types(sol):
    assert type(sol.parse_json("10")) is int
    assert type(sol.parse_json("10.0")) is float
    assert type(sol.parse_json("1e2")) is float
    assert sol.parse_json("-0") == 0


def test_invalid(sol):
    for s in _INVALID:
        try:
            sol.parse_json(s)
        except ValueError:
            continue
        raise AssertionError("accepted %r" % s)


def test_surrogates(sol):
    assert sol.parse_json('"\\ud83d\\ude00x"') == "\U0001F600x"
    assert sol.parse_json('"\\uD834\\uDD1E"') == "\U0001D11E"


def test_deep(sol):
    s = "[" * 500 + "1" + "]" * 500
    v = sol.parse_json(s)
    for _ in range(500):
        assert isinstance(v, list) and len(v) == 1
        v = v[0]
    assert v == 1


def test_random_roundtrip(sol):
    import random
    rng = random.Random(8)

    def gen(d):
        r = rng.random()
        if d > 4 or r < 0.3:
            return rng.choice([rng.randint(-10 ** 6, 10 ** 6), rng.uniform(-1e6, 1e6), "sé\n\"%d" % rng.randint(0, 99),
                               True, False, None])
        if r < 0.65:
            return [gen(d + 1) for _ in range(rng.randint(0, 4))]
        return {"k%d" % rng.randint(0, 9): gen(d + 1) for _ in range(rng.randint(0, 4))}

    for _ in range(150):
        v = gen(0)
        s = _json.dumps(v, ensure_ascii=rng.random() < 0.5, indent=rng.choice([None, 1, 2]))
        assert sol.parse_json(s) == _json.loads(s)
