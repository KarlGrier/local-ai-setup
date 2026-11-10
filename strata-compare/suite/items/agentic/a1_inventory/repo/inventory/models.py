from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Item:
    sku: str
    name: str
    qty: int
    unit_price: Decimal

    @property
    def value(self) -> Decimal:
        return self.unit_price * self.qty
