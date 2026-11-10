import unittest

from inventory import Store
from inventory.report import format_report, money
from decimal import Decimal


class ReportTests(unittest.TestCase):
    def test_money_rounds_half_up(self):
        self.assertEqual(money(Decimal("2.675")), "2.68")
        self.assertEqual(money(Decimal("0.125")), "0.13")
        self.assertEqual(money(Decimal("3")), "3.00")

    def test_report(self):
        s = Store()
        s.add_item("B-2", "bolts", 40, "0.15")
        s.add_item("A-1", "anchors", 3, "2.675")
        self.assertEqual(format_report(s), "A-1 | anchors | 3 | 8.03\nB-2 | bolts | 40 | 6.00\nTOTAL | 14.03")


if __name__ == "__main__":
    unittest.main()
