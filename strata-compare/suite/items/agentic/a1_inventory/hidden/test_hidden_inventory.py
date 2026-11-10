import unittest
from decimal import Decimal

from inventory import InsufficientStock, Store, UnknownSku
from inventory.report import format_report, money


class HiddenInventory(unittest.TestCase):
    def test_remove_exact_amount_to_zero(self):
        s = Store()
        s.add_item("X", "x", 5, "1")
        s.remove_stock("X", 5)
        self.assertEqual(s.get("X").qty, 0)
        with self.assertRaises(InsufficientStock):
            s.remove_stock("X", 1)
        self.assertEqual(s.get("X").qty, 0)

    def test_insufficient_is_value_error(self):
        self.assertTrue(issubclass(InsufficientStock, ValueError))

    def test_total_value_type_and_empty(self):
        s = Store()
        self.assertEqual(s.total_value(), Decimal("0"))
        s.add_item("P", "pins", 3, "0.1")
        v = s.total_value()
        self.assertIsInstance(v, Decimal)
        self.assertEqual(v, Decimal("0.3"))

    def test_low_stock_order_and_ties(self):
        s = Store()
        for sku, q in (("D", 2), ("B", 0), ("C", 2), ("A", 9), ("E", 1)):
            s.add_item(sku, sku.lower(), q, "1")
        self.assertEqual(s.low_stock(3), ["B", "E", "C", "D"])
        self.assertEqual(s.low_stock(0), [])

    def test_money_more(self):
        self.assertEqual(money(Decimal("1.005")), "1.01")
        self.assertEqual(money(Decimal("1.004")), "1.00")
        self.assertEqual(money(Decimal("1234.565")), "1234.57")

    def test_report_after_changes(self):
        s = Store()
        s.add_item("K", "keys", 10, "0.335")
        s.remove_stock("K", 1)
        self.assertEqual(format_report(s), "K | keys | 9 | 3.02\nTOTAL | 3.02")


if __name__ == "__main__":
    unittest.main()
