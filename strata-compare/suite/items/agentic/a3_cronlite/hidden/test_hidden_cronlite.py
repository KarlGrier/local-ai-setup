import unittest
from datetime import datetime

from cronlite import CronError, next_run, parse


class HiddenCron(unittest.TestCase):
    def test_range_step(self):
        self.assertEqual(parse("10-30/10 * * * *")["minute"], {10, 20, 30})
        self.assertEqual(parse("1-7/2 * * * *")["minute"], {1, 3, 5, 7})
        self.assertEqual(parse("* * * * 5-7")["dow"], {5, 6, 0})

    def test_more_errors(self):
        for bad in ["* 24 * * *", "* * * 13 *", "* * * * 8", "1,,2 * * * *", "*/x * * * *", "-1 * * * *",
                    "* * 32 * *", "1/2/3 * * * *", "", "* * * * * *"]:
            with self.assertRaises(CronError, msg=bad):
                parse(bad)

    def test_star_dom_with_dow(self):
        # only day-of-week restricted: Sundays
        self.assertEqual(next_run("0 8 * * 0", datetime(2026, 3, 2)), datetime(2026, 3, 8, 8, 0))
        # only day-of-month restricted: the 31st (skips April)
        self.assertEqual(next_run("0 0 31 * *", datetime(2026, 3, 31, 0, 0)), datetime(2026, 5, 31, 0, 0))

    def test_or_rule_picks_dom(self):
        self.assertEqual(next_run("15 6 3 * 2", datetime(2026, 3, 1)), datetime(2026, 3, 3, 6, 15))
        self.assertEqual(next_run("15 6 4 * 0", datetime(2026, 3, 2)), datetime(2026, 3, 4, 6, 15))

    def test_leap_day(self):
        self.assertEqual(next_run("0 0 29 2 *", datetime(2026, 1, 1)), datetime(2028, 2, 29, 0, 0))

    def test_year_end(self):
        self.assertEqual(next_run("59 23 31 12 *", datetime(2026, 12, 31, 23, 59)), datetime(2027, 12, 31, 23, 59))


if __name__ == "__main__":
    unittest.main()
