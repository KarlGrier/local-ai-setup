from datetime import timedelta

from .parse import parse


def matches(spec, t):
    """Cron's rule: minute, hour and month must match. If both day-of-month and day-of-week are restricted (neither
    is '*'), the day matches when EITHER matches; otherwise only the restricted one (if any) must match."""
    if t.minute not in spec["minute"] or t.hour not in spec["hour"] or t.month not in spec["month"]:
        return False
    dow = t.weekday()
    return t.day in spec["dom"] and dow in spec["dow"]


def next_run(expr, after):
    """The first minute strictly after `after` (seconds and microseconds are ignored) that matches `expr`.
    Searches at most 5 years ahead; raises ValueError if nothing matches in that time."""
    spec = parse(expr)
    t = after.replace(second=0, microsecond=0)
    for _ in range(5 * 366 * 24 * 60):
        if matches(spec, t):
            return t
        t += timedelta(minutes=1)
    raise ValueError("no match within 5 years")
