LEVEL = "medium"
KIND = "parsing"
ENTRY = "parse_csv_line"
PROMPT = """Write a Python function `parse_csv_line(line: str) -> list[str]` that splits one CSV record into fields.

Rules:
- Fields are separated by commas. An empty line is one empty field: `[""]`. "a,,b" is ["a", "", "b"]; "a," is ["a", ""].
- A field may be quoted: it then starts with `"` and ends with the matching closing `"`. Inside a quoted field, commas are ordinary characters and two double quotes `""` stand for one literal `"`.
- After a closing quote the next character must be a comma or the end of the line; anything else is an error.
- An unquoted field may not contain a double quote anywhere; that is an error.
- A quote that is never closed is an error.
- Whitespace is kept exactly as it is (no trimming), and whitespace before an opening quote makes the field unquoted (so `a, "b"` is an error because the second field contains a quote).
- Raise `ValueError` for every error.
"""

GOOD = r'''
def parse_csv_line(line):
    fields = []
    i, n = 0, len(line)
    while True:
        if i < n and line[i] == '"':
            i += 1
            buf = []
            while True:
                if i >= n:
                    raise ValueError("unterminated quote")
                ch = line[i]
                if ch == '"':
                    if i + 1 < n and line[i + 1] == '"':
                        buf.append('"')
                        i += 2
                        continue
                    i += 1
                    break
                buf.append(ch)
                i += 1
            fields.append("".join(buf))
            if i == n:
                return fields
            if line[i] != ",":
                raise ValueError("text after closing quote")
            i += 1
        else:
            j = line.find(",", i)
            end = n if j < 0 else j
            field = line[i:end]
            if '"' in field:
                raise ValueError("quote in unquoted field")
            fields.append(field)
            if j < 0:
                return fields
            i = j + 1
'''

BAD = r'''
def parse_csv_line(line):
    fields, buf, quoted = [], [], False
    for ch in line:
        if ch == '"':
            quoted = not quoted
        elif ch == "," and not quoted:
            fields.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if quoted:
        raise ValueError("unterminated quote")
    fields.append("".join(buf))
    return fields
'''

# ==== HIDDEN TESTS ====
def _raises(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False


def test_plain(sol):
    assert sol.parse_csv_line("a,b,c") == ["a", "b", "c"]
    assert sol.parse_csv_line("") == [""]
    assert sol.parse_csv_line("a,,b") == ["a", "", "b"]
    assert sol.parse_csv_line("a,") == ["a", ""]
    assert sol.parse_csv_line(",") == ["", ""]


def test_whitespace_kept(sol):
    assert sol.parse_csv_line(" a , b ") == [" a ", " b "]


def test_quoted(sol):
    assert sol.parse_csv_line('"a,b",c') == ["a,b", "c"]
    assert sol.parse_csv_line('"",x') == ["", "x"]
    assert sol.parse_csv_line('x,"y"') == ["x", "y"]


def test_escaped_quotes(sol):
    assert sol.parse_csv_line('"say ""hi""",2') == ['say "hi"', "2"]
    assert sol.parse_csv_line('""""') == ['"']
    assert sol.parse_csv_line('"a""",b') == ['a"', "b"]


def test_errors(sol):
    for bad in ['"abc', 'a"b', '"a"b', 'a, "b"', '"a"x,y', '"""', 'x,"y']:
        assert _raises(sol.parse_csv_line, bad), bad


def test_many_fields(sol):
    line = ",".join('"%d,%d"' % (i, i) if i % 2 else str(i) for i in range(200))
    out = sol.parse_csv_line(line)
    assert len(out) == 200 and out[3] == "3,3" and out[4] == "4"
