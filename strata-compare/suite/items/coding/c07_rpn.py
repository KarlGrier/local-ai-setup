LEVEL = "medium"
KIND = "algorithms"
ENTRY = "eval_rpn"
PROMPT = """Write a Python function `eval_rpn(tokens: list[str]) -> int` that evaluates an integer expression in reverse Polish notation.

Rules:
- A number token is an optional leading `-` followed by one or more ASCII digits (for example "42", "-7", "007"). Everything else must be one of the operators `+`, `-`, `*`, `/`.
- `/` is integer division that truncates toward zero (so 7 / -2 is -3 and -7 / 2 is -3).
- Division by zero raises `ZeroDivisionError`.
- Raise `ValueError` for: an unknown token, an operator without two operands available, an empty token list, or more than one value left at the end.
"""

GOOD = r'''
def eval_rpn(tokens):
    stack = []
    for t in tokens:
        if t in ("+", "-", "*", "/"):
            if len(stack) < 2:
                raise ValueError("not enough operands")
            b = stack.pop()
            a = stack.pop()
            if t == "+":
                stack.append(a + b)
            elif t == "-":
                stack.append(a - b)
            elif t == "*":
                stack.append(a * b)
            else:
                if b == 0:
                    raise ZeroDivisionError("division by zero")
                q = abs(a) // abs(b)
                stack.append(q if (a >= 0) == (b >= 0) else -q)
        else:
            body = t[1:] if t.startswith("-") else t
            if not body or any(c not in "0123456789" for c in body):
                raise ValueError("bad token %r" % t)
            stack.append(int(t))
    if len(stack) != 1:
        raise ValueError("malformed expression")
    return stack[0]
'''

BAD = r'''
def eval_rpn(tokens):
    stack = []
    ops = {"+": lambda a, b: a + b, "-": lambda a, b: a - b, "*": lambda a, b: a * b, "/": lambda a, b: a // b}
    for t in tokens:
        if t in ops:
            if len(stack) < 2:
                raise ValueError("not enough operands")
            b = stack.pop()
            a = stack.pop()
            stack.append(ops[t](a, b))
        else:
            try:
                stack.append(int(t))
            except ValueError:
                raise ValueError("bad token")
    if len(stack) != 1:
        raise ValueError("malformed")
    return stack[0]
'''

# ==== HIDDEN TESTS ====
def _raises(exc, f, *a):
    try:
        f(*a)
    except exc:
        return True
    return False


def test_basic(sol):
    assert sol.eval_rpn(["2", "3", "+"]) == 5
    assert sol.eval_rpn(["2", "3", "4", "*", "+"]) == 14
    assert sol.eval_rpn(["5", "1", "2", "+", "4", "*", "+", "3", "-"]) == 14


def test_negative_numbers(sol):
    assert sol.eval_rpn(["-7", "2", "*"]) == -14
    assert sol.eval_rpn(["007"]) == 7
    assert sol.eval_rpn(["3", "-4", "-"]) == 7


def test_truncating_division(sol):
    assert sol.eval_rpn(["7", "-2", "/"]) == -3
    assert sol.eval_rpn(["-7", "2", "/"]) == -3
    assert sol.eval_rpn(["-7", "-2", "/"]) == 3
    assert sol.eval_rpn(["7", "2", "/"]) == 3
    assert sol.eval_rpn(["-1", "3", "/"]) == 0


def test_div_zero(sol):
    assert _raises(ZeroDivisionError, sol.eval_rpn, ["1", "0", "/"])


def test_errors(sol):
    for bad in [[], ["+"], ["1", "+"], ["1", "2"], ["1", "2", "^"], ["1.5"], ["-"], ["--3"], ["+3"], [" 3"]]:
        assert _raises(ValueError, sol.eval_rpn, bad), bad


def test_big(sol):
    toks = ["1"] + ["2", "*"] * 200
    assert sol.eval_rpn(toks) == 2 ** 200
