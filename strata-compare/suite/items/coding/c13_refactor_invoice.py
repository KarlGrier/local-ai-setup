LEVEL = "medium"
KIND = "refactor"
ENTRY = "invoice_total"
PROMPT = '''Refactor this module. Keep `invoice_total` with the same signature and exactly the same results (the existing tests below must keep passing), and split its logic into three new public functions:

- `line_total(item: dict) -> Decimal`: price times quantity for one item (no rounding).
- `discount_rate(coupon: str | None, subtotal: Decimal) -> Decimal`: the discount rate the coupon gives for this subtotal (0 when there is none).
- `tax_rate(region: str) -> Decimal`: the tax rate of the region; an unknown region raises `ValueError` (with any message).

`invoice_total` must use these three functions. Return the whole refactored module.

```python
from decimal import Decimal, ROUND_HALF_UP


def invoice_total(items, region, coupon=None):
    subtotal = Decimal("0")
    for it in items:
        if it["qty"] < 0:
            raise ValueError("negative quantity")
        subtotal += Decimal(str(it["price"])) * it["qty"]
    rate = Decimal("0")
    if coupon == "SAVE10":
        rate = Decimal("0.10")
    elif coupon == "BIG20":
        if subtotal >= 100:
            rate = Decimal("0.20")
        else:
            rate = Decimal("0.05")
    elif coupon is not None:
        raise ValueError("unknown coupon")
    after = subtotal - subtotal * rate
    if region == "north":
        tax = Decimal("0.07")
    elif region == "south":
        tax = Decimal("0.05")
    elif region == "islands":
        tax = Decimal("0")
    else:
        raise ValueError("unknown region")
    total = after + after * tax
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

Existing tests:

```python
from decimal import Decimal

def test_plain():
    assert invoice_total([{"price": 10, "qty": 3}], "north") == Decimal("32.10")

def test_coupons():
    items = [{"price": "19.99", "qty": 5}]
    assert invoice_total(items, "south", "SAVE10") == Decimal("94.45")
    assert invoice_total([{"price": "20.01", "qty": 5}], "islands", "BIG20") == Decimal("80.04")
    assert invoice_total([{"price": 5, "qty": 1}], "islands", "BIG20") == Decimal("4.75")
```
'''

GOOD = r'''
from decimal import Decimal, ROUND_HALF_UP

_TAX = {"north": Decimal("0.07"), "south": Decimal("0.05"), "islands": Decimal("0")}


def line_total(item):
    if item["qty"] < 0:
        raise ValueError("negative quantity")
    return Decimal(str(item["price"])) * item["qty"]


def discount_rate(coupon, subtotal):
    if coupon is None:
        return Decimal("0")
    if coupon == "SAVE10":
        return Decimal("0.10")
    if coupon == "BIG20":
        return Decimal("0.20") if subtotal >= 100 else Decimal("0.05")
    raise ValueError("unknown coupon")


def tax_rate(region):
    try:
        return _TAX[region]
    except KeyError:
        raise ValueError("unknown region") from None


def invoice_total(items, region, coupon=None):
    subtotal = sum((line_total(it) for it in items), Decimal("0"))
    rate = discount_rate(coupon, subtotal)
    after = subtotal - subtotal * rate
    tax = tax_rate(region)
    total = after + after * tax
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
'''

BAD = r'''
from decimal import Decimal, ROUND_HALF_UP

_TAX = {"north": Decimal("0.07"), "south": Decimal("0.05"), "islands": Decimal("0")}


def line_total(item):
    if item["qty"] < 0:
        raise ValueError("negative quantity")
    return (Decimal(str(item["price"])) * item["qty"]).quantize(Decimal("0.01"))


def discount_rate(coupon, subtotal):
    if coupon == "SAVE10":
        return Decimal("0.10")
    if coupon == "BIG20":
        return Decimal("0.20") if subtotal > 100 else Decimal("0.05")
    return Decimal("0")


def tax_rate(region):
    return _TAX.get(region, Decimal("0"))


def invoice_total(items, region, coupon=None):
    subtotal = sum((line_total(it) for it in items), Decimal("0"))
    after = subtotal * (1 - discount_rate(coupon, subtotal))
    total = after * (1 + tax_rate(region))
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
'''

# ==== HIDDEN TESTS ====
from decimal import Decimal as _D


def _raises(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False


def test_existing_plain(sol):
    assert sol.invoice_total([{"price": 10, "qty": 3}], "north") == _D("32.10")


def test_existing_coupons(sol):
    items = [{"price": "19.99", "qty": 5}]
    assert sol.invoice_total(items, "south", "SAVE10") == _D("94.45")
    assert sol.invoice_total([{"price": "20.01", "qty": 5}], "islands", "BIG20") == _D("80.04")
    assert sol.invoice_total([{"price": 5, "qty": 1}], "islands", "BIG20") == _D("4.75")


def test_behaviour_kept(sol):
    assert sol.invoice_total([], "south") == _D("0.00")
    assert sol.invoice_total([{"price": 100, "qty": 1}], "islands", "BIG20") == _D("80.00")
    assert sol.invoice_total([{"price": "0.005", "qty": 1}], "islands") == _D("0.01")
    assert sol.invoice_total([{"price": "33.335", "qty": 3}], "north", "SAVE10") == _D("96.30")
    assert sol.invoice_total([{"price": "19.99", "qty": 5}], "islands", "BIG20") == _D("94.95")
    assert sol.invoice_total([{"price": "2.675", "qty": 1}], "islands") == _D("2.68")
    assert sol.invoice_total([{"price": "1.105", "qty": 3}], "south") == _D("3.48")
    assert _raises(sol.invoice_total, [{"price": 1, "qty": 1}], "west")
    assert _raises(sol.invoice_total, [{"price": 1, "qty": 1}], "north", "FREE")
    assert _raises(sol.invoice_total, [{"price": 1, "qty": -1}], "north")


def test_line_total(sol):
    assert sol.line_total({"price": "19.99", "qty": 5}) == _D("99.95")
    assert sol.line_total({"price": "0.333", "qty": 3}) == _D("0.999")


def test_discount_rate(sol):
    assert sol.discount_rate(None, _D("50")) == 0
    assert sol.discount_rate("SAVE10", _D("5")) == _D("0.10")
    assert sol.discount_rate("BIG20", _D("100")) == _D("0.20")
    assert sol.discount_rate("BIG20", _D("99.99")) == _D("0.05")


def test_tax_rate(sol):
    assert sol.tax_rate("north") == _D("0.07")
    assert sol.tax_rate("islands") == 0
    assert _raises(sol.tax_rate, "east")


def test_uses_helpers(sol):
    import inspect
    src = inspect.getsource(sol.invoice_total)
    for name in ("line_total", "discount_rate", "tax_rate"):
        assert name in src, name
