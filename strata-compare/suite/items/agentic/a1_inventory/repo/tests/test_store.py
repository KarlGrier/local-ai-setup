import unittest
from decimal import Decimal

from inventory import InsufficientStock, Store, UnknownSku


def make():
    s = Store()
    s.add_item("B-200", "bolts", 40, "0.15")
    s.add_item("A-100", "anchors", 3, "2.675")
    s.add_item("C-300", "clamps", 7, "1.10")
    return s


class StoreTests(unittest.TestCase):
    def test_remove_stock(self):
        s = make()
        s.remove_stock("B-200", 15)
        self.assertEqual(s.get("B-200").qty, 25)

    def test_remove_too_much(self):
        s = make()
        with self.assertRaises(InsufficientStock):
            s.remove_stock("A-100", 4)
        self.assertEqual(s.get("A-100").qty, 3)

    def test_unknown(self):
        with self.assertRaises(UnknownSku):
            make().remove_stock("Z-999", 1)

    def test_total_value_is_exact(self):
        self.assertEqual(make().total_value(), Decimal("21.725"))

    def test_low_stock(self):
        s = make()
        self.assertEqual(s.low_stock(8), ["A-100", "C-300"])
        self.assertEqual(s.low_stock(1), [])


if __name__ == "__main__":
    unittest.main()
