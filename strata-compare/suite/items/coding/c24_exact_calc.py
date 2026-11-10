LEVEL = "hard"
KIND = "parsing"
ENTRY = "calc"
PROMPT = """Write a Python function `calc(expr: str) -> fractions.Fraction` that evaluates an arithmetic expression exactly (without `eval`, `exec`, `ast` or any parser library).

Grammar and rules:
- Numbers: ASCII digits with an optional fractional part ("12", "0.5", "3.", ".25" are all valid; "." alone is not). A decimal is converted exactly ("0.1" is Fraction(1, 10)).
- Operators: `+`, `-`, `*`, `/` (exact division) and `^` (power), plus parentheses and unary minus/plus.
- Precedence from low to high: `+ -` (left-associative), `* /` (left-associative), unary `+ -`, `^` (right-associative). So `-2^2` is -4, `2^3^2` is 512, `2^-1` is 1/2 (a unary minus may start the exponent), and `-3--3` is 0.
- The exponent of `^` must evaluate to an integer (it may be negative); otherwise raise `ValueError`. `0^0` is 1. A zero base with a negative exponent raises `ZeroDivisionError`.
- Spaces and tabs between tokens are ignored.
- Division by zero raises `ZeroDivisionError`. Every syntax error (empty input, unbalanced parentheses, unknown characters, missing operands, two numbers in a row, implicit multiplication like "2(3)") raises `ValueError`.
"""

GOOD = r'''
from fractions import Fraction


def _tokens(s):
    toks, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in " \t":
            i += 1
        elif c in "0123456789.":
            j = i
            while j < n and s[j] in "0123456789":
                j += 1
            if j < n and s[j] == ".":
                j += 1
                while j < n and s[j] in "0123456789":
                    j += 1
            txt = s[i:j]
            if txt == "." or txt.count(".") > 1:
                raise ValueError("bad number")
            toks.append(("num", Fraction(txt)))
            i = j
        elif c in "+-*/^()":
            toks.append((c, None))
            i += 1
        else:
            raise ValueError("unknown character %r" % c)
    return toks


class _P:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self):
        return self.t[self.i][0] if self.i < len(self.t) else None

    def take(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def expr(self):
        v = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()[0]
            r = self.term()
            v = v + r if op == "+" else v - r
        return v

    def term(self):
        v = self.unary()
        while self.peek() in ("*", "/"):
            op = self.take()[0]
            r = self.unary()
            if op == "*":
                v = v * r
            else:
                if r == 0:
                    raise ZeroDivisionError("division by zero")
                v = v / r
        return v

    def unary(self):
        if self.peek() in ("+", "-"):
            op = self.take()[0]
            v = self.unary()
            return -v if op == "-" else v
        return self.power()

    def power(self):
        base = self.atom()
        if self.peek() == "^":
            self.take()
            e = self.unary()
            if e.denominator != 1:
                raise ValueError("non-integer exponent")
            if base == 0 and e < 0:
                raise ZeroDivisionError("0 to a negative power")
            return base ** int(e)
        return base

    def atom(self):
        k = self.peek()
        if k == "num":
            return self.take()[1]
        if k == "(":
            self.take()
            v = self.expr()
            if self.peek() != ")":
                raise ValueError("missing )")
            self.take()
            return v
        raise ValueError("expected a number or (")


def calc(expr):
    toks = _tokens(expr)
    if not toks:
        raise ValueError("empty")
    p = _P(toks)
    v = p.expr()
    if p.i != len(toks):
        raise ValueError("unexpected token")
    return Fraction(v)
'''

BAD = r'''
from fractions import Fraction
import re


def calc(expr):
    toks = re.findall(r"\d+\.?\d*|\.\d+|[-+*/^()]", expr.replace(" ", ""))
    if not toks or "".join(toks) != expr.replace(" ", "").replace("\t", ""):
        raise ValueError("syntax")
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def take():
        pos[0] += 1
        return toks[pos[0] - 1]

    def atom():
        t = peek()
        if t is None:
            raise ValueError("end")
        if t == "(":
            take()
            v = add()
            if take() != ")":
                raise ValueError(")")
            return v
        if t == "-":
            take()
            return -atom()
        take()
        return Fraction(t)

    def power():
        v = atom()
        while peek() == "^":
            take()
            v = v ** int(atom())
        return v

    def mul():
        v = power()
        while peek() in ("*", "/"):
            v = v * power() if take() == "*" else v / power()
        return v

    def add():
        v = mul()
        while peek() in ("+", "-"):
            v = v + mul() if take() == "+" else v - mul()
        return v

    v = add()
    if peek() is not None:
        raise ValueError("trailing")
    return v
'''

# ==== HIDDEN TESTS ====
from fractions import Fraction as _F


def _raises(exc, f, *a):
    try:
        f(*a)
    except exc:
        return True
    except Exception:
        return False
    return False


def test_basic(sol):
    assert sol.calc("1 + 2 * 3") == 7
    assert sol.calc("(1 + 2) * 3") == 9
    assert sol.calc("10 / 4") == _F(5, 2)
    assert sol.calc("8 - 3 - 2") == 3
    assert sol.calc("2 / 3 / 4") == _F(1, 6)


def test_decimals_exact(sol):
    assert sol.calc("0.1 + 0.2") == _F(3, 10)
    assert sol.calc("3. + .25") == _F(13, 4)
    assert sol.calc("1.5 * 1.5") == _F(9, 4)


def test_power_rules(sol):
    assert sol.calc("2^3^2") == 512
    assert sol.calc("-2^2") == -4
    assert sol.calc("(-2)^2") == 4
    assert sol.calc("2^-1") == _F(1, 2)
    assert sol.calc("2^-2^2") == _F(1, 16)
    assert sol.calc("0^0") == 1
    assert sol.calc("(1/2)^(4/2)") == _F(1, 4)
    assert sol.calc("2*3^2") == 18


def test_unary(sol):
    assert sol.calc("-3--3") == 0
    assert sol.calc("+-+5") == -5
    assert sol.calc("2*-3") == -6
    assert sol.calc("-(1+2)*-(3)") == 9


def test_zero_division(sol):
    assert _raises(ZeroDivisionError, sol.calc, "1/0")
    assert _raises(ZeroDivisionError, sol.calc, "1/(2-2)")
    assert _raises(ZeroDivisionError, sol.calc, "0^-1")


def test_syntax_errors(sol):
    for bad in ["", "   ", "1+", "*2", "(1+2", "1+2)", "2(3)", "1 2", "1.2.3", ".", "2^0.5", "a+1", "1**2",
                "()", "3 % 2", "--", "1e3"]:
        assert _raises(ValueError, sol.calc, bad), bad


def test_result_type(sol):
    assert isinstance(sol.calc("7"), _F)
    assert isinstance(sol.calc("1/3+1/6"), _F) and sol.calc("1/3+1/6") == _F(1, 2)


def test_random_against_python(sol):
    import random
    rng = random.Random(24)

    def gen(d):
        if d > 3 or rng.random() < 0.3:
            return str(rng.randint(1, 9))
        op = rng.choice("+-*/")
        return "(" + gen(d + 1) + " " + op + " " + gen(d + 1) + ")"

    for _ in range(300):
        e = gen(0)
        try:
            exp = eval("".join("_F(%s)" % ch if ch.isdigit() else ch for ch in e), {"_F": _F})
        except ZeroDivisionError:
            assert _raises(ZeroDivisionError, sol.calc, e)
            continue
        assert sol.calc(e) == exp, e
