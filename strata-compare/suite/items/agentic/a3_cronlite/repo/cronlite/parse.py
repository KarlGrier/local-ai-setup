"""Parse 5-field cron expressions: minute hour day-of-month month day-of-week.

Each field is a comma-separated list of items. An item is '*', a number, or a range 'a-b', optionally followed by
'/step' (for '*' or a range: every step-th value starting at the range's first value). Ranges: minute 0-59,
hour 0-23, day-of-month 1-31, month 1-12, day-of-week 0-6 where 0 is Sunday (7 is also accepted for Sunday).
Values outside the range, a > b in a range, step < 1 and malformed items raise CronError."""

FIELDS = [("minute", 0, 59), ("hour", 0, 23), ("dom", 1, 31), ("month", 1, 12), ("dow", 0, 6)]


class CronError(ValueError):
    pass


def parse_field(text, lo, hi, is_dow=False):
    values = set()
    for item in text.split(","):
        step = 1
        if "/" in item:
            item, step_s = item.split("/")
            step = int(step_s)
        if item == "*":
            a, b = lo, hi
        elif "-" in item:
            a, b = (int(x) for x in item.split("-"))
        else:
            a = b = int(item)
        values.update(range(a, b, step))
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
