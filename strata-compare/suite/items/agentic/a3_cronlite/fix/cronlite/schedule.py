from datetime import timedelta

from .parse import parse


def matches(spec, t):
    """Cron's rule: minute, hour and month must match. If both day-of-month and day-of-week are restricted (neither
    is '*'), the day matches when EITHER matches; otherwise only the restricted one (if any) must match."""
    if t.minute not in spec["minute"] or t.hour not in spec["hour"] or t.month not in spec["month"]:
        return False
    dow = (t.weekday() + 1) % 7          # Python: Monday = 0; cron: Sunday = 0
    dom_ok, dow_ok = t.day in spec["dom"], dow in spec["dow"]
    if not spec["dom_star"] and not spec["dow_star"]:
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def next_run(expr, after):
    """The first minute strictly after `after` (seconds and microseconds are ignored) that matches `expr`.
    Searches at most 5 years ahead; raises ValueError if nothing matches in that time."""
    spec = parse(expr)
    t = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    end = t + timedelta(days=5 * 366)
    while t < end:
        if t.month not in spec["month"]:
            t = (t.replace(day=1, hour=0, minute=0) + timedelta(days=32)).replace(day=1)
            continue
        if matches(spec, t):
            return t
        if t.hour not in spec["hour"]:
            t = t.replace(minute=0) + timedelta(hours=1)
            continue
        t += timedelta(minutes=1)
    raise ValueError("no match within 5 years")
