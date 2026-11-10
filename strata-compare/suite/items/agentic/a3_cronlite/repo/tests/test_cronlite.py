import unittest
from datetime import datetime

from cronlite import CronError, next_run, parse


class Parse(unittest.TestCase):
    def test_star_and_numbers(self):
        p = parse("5 * * * *")
        self.assertEqual(p["minute"], {5})
        self.assertEqual(p["hour"], set(range(24)))

    def test_ranges_steps_lists(self):
        p = parse("*/15 9-17 1,15 */3 1-5")
        self.assertEqual(p["minute"], {0, 15, 30, 45})
        self.assertEqual(p["hour"], set(range(9, 18)))
        self.assertEqual(p["dom"], {1, 15})
        self.assertEqual(p["month"], {1, 4, 7, 10})
        self.assertEqual(p["dow"], {1, 2, 3, 4, 5})

    def test_sunday_seven(self):
        self.assertEqual(parse("0 0 * * 7")["dow"], {0})

    def test_errors(self):
        for bad in ["60 * * * *", "* * * *", "5-1 * * * *", "*/0 * * * *", "a * * * *", "* * 0 * *", "1-2-3 * * * *"]:
            with self.assertRaises(CronError, msg=bad):
                parse(bad)


class NextRun(unittest.TestCase):
    def test_next_minute_strictly_after(self):
        self.assertEqual(next_run("* * * * *", datetime(2026, 3, 1, 10, 0, 30)), datetime(2026, 3, 1, 10, 1))

    def test_weekday(self):
        # 2026-03-01 is a Sunday
        self.assertEqual(next_run("30 9 * * 1", datetime(2026, 3, 1, 12, 0)), datetime(2026, 3, 2, 9, 30))

    def test_dom_or_dow(self):
        # restricted day-of-month OR day-of-week: the 13th, or any Friday
        self.assertEqual(next_run("0 12 13 * 5", datetime(2026, 3, 1)), datetime(2026, 3, 6, 12, 0))


if __name__ == "__main__":
    unittest.main()
