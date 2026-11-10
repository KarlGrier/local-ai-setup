"""Parse 5-field cron expressions: minute hour day-of-month month day-of-week.

Each field is a comma-separated list of items. An item is '*', a number, or a range 'a-b', optionally followed by
'/step' (for '*' or a range: every step-th value starting at the range's first value). Ranges: minute 0-59,
hour 0-23, day-of-month 1-31, month 1-12, day-of-week 0-6 where 0 is Sunday (7 is also accepted for Sunday).
Values outside the range, a > b in a range, step < 1 and malformed items raise CronError."""
import re

FIELDS = [("minute", 0, 59), ("hour", 0, 23), ("dom", 1, 31), ("month", 1, 12), ("dow", 0, 6)]
_ITEM = re.compile(r"^(\*|\d+|\d+-\d+)(?:/(\d+))?$")


class CronError(ValueError):
    pass


def parse_field(text, lo, hi, is_dow=False):
    top = 7 if is_dow else hi
    values = set()
    for item in text.split(","):
        m = _ITEM.match(item)
        if not m:
            raise CronError(f"bad item {item!r}")
        body, step_s = m.groups()
        step = int(step_s) if step_s is not None else 1
        if step < 1:
            raise CronError("step must be >= 1")
        if body == "*":
            a, b = lo, hi
        elif "-" in body:
            a, b = (int(x) for x in body.split("-"))
        else:
            a = b = int(body)
        if a < lo or b > top or a > b:
            raise CronError(f"bad range in {item!r}")
        for v in range(a, b + 1, step):
            values.add(0 if (is_dow and v == 7) else v)
    return values


def parse(expr):
    """Return a dict with the sets 'minute', 'hour', 'dom', 'month', 'dow', and the flags 'dom_star' / 'dow_star'
    (True when that field was written as '*')."""
    parts = expr.split()
    if len(parts) != 5:
        raise CronError("need 5 fields")
    out = {}
    for (name, lo, hi), text in zip(FIELDS, parts):
        out[name] = parse_field(text, lo, hi, is_dow=(name == "dow"))
    out["dom_star"] = parts[2] == "*"
    out["dow_star"] = parts[4] == "*"
    return out
