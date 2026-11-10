from decimal import Decimal

from .models import Item


class UnknownSku(KeyError):
    pass


class InsufficientStock(ValueError):
    pass


class Store:
    """Items by SKU.  Quantities never go below zero."""

    def __init__(self):
        self._items = {}

    def add_item(self, sku, name, qty, unit_price):
        if sku in self._items:
            raise ValueError(f"duplicate sku {sku}")
        if qty < 0:
            raise ValueError("qty must be >= 0")
        self._items[sku] = Item(sku, name, qty, Decimal(str(unit_price)))

    def get(self, sku):
        try:
            return self._items[sku]
        except KeyError:
            raise UnknownSku(sku)

    def restock(self, sku, qty):
        if qty <= 0:
            raise ValueError("qty must be > 0")
        self.get(sku).qty += qty

    def remove_stock(self, sku, qty):
        """Take qty units out; raise InsufficientStock (and change nothing) if there are not enough."""
        if qty <= 0:
            raise ValueError("qty must be > 0")
        item = self.get(sku)
        if qty > item.qty:
            raise InsufficientStock(f"{sku}: have {item.qty}, need {qty}")
        item.qty -= qty

    def total_value(self):
        """Sum of qty * unit_price over all items, as a Decimal."""
        return sum((i.value for i in self._items.values()), Decimal("0"))

    def low_stock(self, threshold):
        """SKUs with qty < threshold, sorted by qty (lowest first), then by SKU."""
        return [i.sku for i in sorted(self._items.values(), key=lambda i: (i.qty, i.sku)) if i.qty < threshold]

    def items(self):
        return sorted(self._items.values(), key=lambda i: i.sku)
