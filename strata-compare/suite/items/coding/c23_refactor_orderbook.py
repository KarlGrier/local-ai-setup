LEVEL = "hard"
KIND = "refactor"
ENTRY = "process_orders"
PROMPT = '''Refactor this module. `process_orders(lines)` must keep exactly the same output for every input. Move the state and the rules into a class `OrderBook` with these public methods, and make `process_orders` a thin loop that parses each line and calls them:

- `add(order_id: str, qty: int, price: Decimal)`
- `cancel(order_id: str)`
- `fill(order_id: str, qty: int)`
- `report() -> str` (the same text a REPORT line produces)

Each of `add`, `cancel` and `fill` raises `ValueError` with exactly the message text that `process_orders` puts after "ERROR " (for example `ValueError("duplicate order A1")`); `process_orders` catches it and appends the "ERROR ..." line. Line-format problems (unknown command, wrong number of fields, bad numbers) stay in `process_orders`. Return the whole refactored module.

```python
from decimal import Decimal, InvalidOperation


def process_orders(lines):
    orders = {}
    filled_value = Decimal("0")
    out = []
    for raw in lines:
        parts = raw.split()
        if not parts:
            continue
        cmd = parts[0].upper()
        if cmd == "ADD":
            if len(parts) != 4:
                out.append("ERROR bad line: " + raw.strip())
                continue
            oid = parts[1]
            try:
                qty = int(parts[2])
                price = Decimal(parts[3])
            except (ValueError, InvalidOperation):
                out.append("ERROR bad line: " + raw.strip())
                continue
            if qty <= 0 or price <= 0:
                out.append("ERROR bad values for " + oid)
            elif oid in orders:
                out.append("ERROR duplicate order " + oid)
            else:
                orders[oid] = [qty, price]
        elif cmd == "CANCEL":
            if len(parts) != 2:
                out.append("ERROR bad line: " + raw.strip())
                continue
            oid = parts[1]
            if oid not in orders:
                out.append("ERROR unknown order " + oid)
            else:
                del orders[oid]
        elif cmd == "FILL":
            if len(parts) != 3:
                out.append("ERROR bad line: " + raw.strip())
                continue
            oid = parts[1]
            try:
                qty = int(parts[2])
            except ValueError:
                out.append("ERROR bad line: " + raw.strip())
                continue
            if oid not in orders:
                out.append("ERROR unknown order " + oid)
            elif qty <= 0 or qty > orders[oid][0]:
                out.append("ERROR bad fill for " + oid)
            else:
                orders[oid][0] -= qty
                filled_value += qty * orders[oid][1]
                if orders[oid][0] == 0:
                    del orders[oid]
        elif cmd == "REPORT":
            open_qty = sum(q for q, _ in orders.values())
            open_value = sum(q * p for q, p in orders.values())
            out.append("open=%d qty=%d value=%s filled=%s" % (len(orders), open_qty,
                       open_value.quantize(Decimal("0.01")) if orders else "0.00",
                       filled_value.quantize(Decimal("0.01"))))
        else:
            out.append("ERROR bad line: " + raw.strip())
    return out
```
'''

GOOD = r'''
from decimal import Decimal, InvalidOperation


class OrderBook:
    def __init__(self):
        self.orders = {}
        self.filled_value = Decimal("0")

    def add(self, order_id, qty, price):
        if qty <= 0 or price <= 0:
            raise ValueError("bad values for " + order_id)
        if order_id in self.orders:
            raise ValueError("duplicate order " + order_id)
        self.orders[order_id] = [qty, price]

    def cancel(self, order_id):
        if order_id not in self.orders:
            raise ValueError("unknown order " + order_id)
        del self.orders[order_id]

    def fill(self, order_id, qty):
        if order_id not in self.orders:
            raise ValueError("unknown order " + order_id)
        if qty <= 0 or qty > self.orders[order_id][0]:
            raise ValueError("bad fill for " + order_id)
        self.orders[order_id][0] -= qty
        self.filled_value += qty * self.orders[order_id][1]
        if self.orders[order_id][0] == 0:
            del self.orders[order_id]

    def report(self):
        open_qty = sum(q for q, _ in self.orders.values())
        open_value = sum(q * p for q, p in self.orders.values())
        return "open=%d qty=%d value=%s filled=%s" % (
            len(self.orders), open_qty,
            open_value.quantize(Decimal("0.01")) if self.orders else "0.00",
            self.filled_value.quantize(Decimal("0.01")))


_ARITY = {"ADD": 4, "CANCEL": 2, "FILL": 3, "REPORT": None}


def process_orders(lines):
    book = OrderBook()
    out = []
    for raw in lines:
        parts = raw.split()
        if not parts:
            continue
        cmd = parts[0].upper()
        bad = "ERROR bad line: " + raw.strip()
        if cmd not in _ARITY or (_ARITY[cmd] is not None and len(parts) != _ARITY[cmd]):
            out.append(bad)
            continue
        try:
            if cmd == "ADD":
                try:
                    qty, price = int(parts[2]), Decimal(parts[3])
                except (ValueError, InvalidOperation):
                    out.append(bad)
                    continue
                book.add(parts[1], qty, price)
            elif cmd == "CANCEL":
                book.cancel(parts[1])
            elif cmd == "FILL":
                try:
                    qty = int(parts[2])
                except ValueError:
                    out.append(bad)
                    continue
                book.fill(parts[1], qty)
            else:
                out.append(book.report())
        except ValueError as e:
            out.append("ERROR " + str(e))
    return out
'''

BAD = r'''
from decimal import Decimal, InvalidOperation


class OrderBook:
    def __init__(self):
        self.orders = {}
        self.filled_value = Decimal("0")

    def add(self, order_id, qty, price):
        if order_id in self.orders:
            raise ValueError("duplicate order " + order_id)
        if qty <= 0 or price <= 0:
            raise ValueError("bad values for " + order_id)
        self.orders[order_id] = [qty, price]

    def cancel(self, order_id):
        if order_id not in self.orders:
            raise ValueError("unknown order " + order_id)
        del self.orders[order_id]

    def fill(self, order_id, qty):
        if order_id not in self.orders:
            raise ValueError("unknown order " + order_id)
        if qty <= 0 or qty > self.orders[order_id][0]:
            raise ValueError("bad fill for " + order_id)
        self.orders[order_id][0] -= qty
        self.filled_value += qty * self.orders[order_id][1]

    def report(self):
        open_qty = sum(q for q, _ in self.orders.values())
        open_value = sum((q * p for q, p in self.orders.values()), Decimal("0"))
        return "open=%d qty=%d value=%s filled=%s" % (len(self.orders), open_qty, open_value.quantize(Decimal("0.01")),
                                                      self.filled_value.quantize(Decimal("0.01")))


def process_orders(lines):
    book = OrderBook()
    out = []
    for raw in lines:
        parts = raw.split()
        if not parts:
            continue
        cmd = parts[0].upper()
        try:
            if cmd == "ADD" and len(parts) == 4:
                book.add(parts[1], int(parts[2]), Decimal(parts[3]))
            elif cmd == "CANCEL" and len(parts) == 2:
                book.cancel(parts[1])
            elif cmd == "FILL" and len(parts) == 3:
                book.fill(parts[1], int(parts[2]))
            elif cmd == "REPORT":
                out.append(book.report())
            else:
                out.append("ERROR bad line: " + raw.strip())
        except (ValueError, InvalidOperation) as e:
            out.append("ERROR " + str(e))
    return out
'''

# ==== HIDDEN TESTS ====
from decimal import Decimal as _D, InvalidOperation as _IO


def _original(lines):
    orders = {}
    filled_value = _D("0")
    out = []
    for raw in lines:
        parts = raw.split()
        if not parts:
            continue
        cmd = parts[0].upper()
        if cmd == "ADD":
            if len(parts) != 4:
                out.append("ERROR bad line: " + raw.strip())
                continue
            oid = parts[1]
            try:
                qty = int(parts[2])
                price = _D(parts[3])
            except (ValueError, _IO):
                out.append("ERROR bad line: " + raw.strip())
                continue
            if qty <= 0 or price <= 0:
                out.append("ERROR bad values for " + oid)
            elif oid in orders:
                out.append("ERROR duplicate order " + oid)
            else:
                orders[oid] = [qty, price]
        elif cmd == "CANCEL":
            if len(parts) != 2:
                out.append("ERROR bad line: " + raw.strip())
                continue
            oid = parts[1]
            if oid not in orders:
                out.append("ERROR unknown order " + oid)
            else:
                del orders[oid]
        elif cmd == "FILL":
            if len(parts) != 3:
                out.append("ERROR bad line: " + raw.strip())
                continue
            oid = parts[1]
            try:
                qty = int(parts[2])
            except ValueError:
                out.append("ERROR bad line: " + raw.strip())
                continue
            if oid not in orders:
                out.append("ERROR unknown order " + oid)
            elif qty <= 0 or qty > orders[oid][0]:
                out.append("ERROR bad fill for " + oid)
            else:
                orders[oid][0] -= qty
                filled_value += qty * orders[oid][1]
                if orders[oid][0] == 0:
                    del orders[oid]
        elif cmd == "REPORT":
            open_qty = sum(q for q, _ in orders.values())
            open_value = sum(q * p for q, p in orders.values())
            out.append("open=%d qty=%d value=%s filled=%s" % (len(orders), open_qty,
                       open_value.quantize(_D("0.01")) if orders else "0.00",
                       filled_value.quantize(_D("0.01"))))
        else:
            out.append("ERROR bad line: " + raw.strip())
    return out


_SCRIPT = ["ADD A1 10 2.50", "add B2 5 10", "REPORT", "FILL A1 4", "FILL A1 6", "REPORT", "FILL A1 1",
           "ADD B2 1 1", "ADD C3 0 5", "ADD C3 2 -1", "ADD D4 x 5", "ADD D4 3 abc", "CANCEL Z9", "CANCEL B2",
           "REPORT", "", "   ", "HELLO", "FILL", "FILL B2 1 2", "ADD E5 3 1.005", "FILL E5 3", "report",
           "Add F6 7 0.10", "fill F6 2", "Report", "CANCEL F6 extra", "ADD G7 1 1e2", "REPORT"]


def _raises(msg, f, *a):
    try:
        f(*a)
    except ValueError as e:
        return str(e) == msg
    return False


def test_same_output_script(sol):
    assert sol.process_orders(_SCRIPT) == _original(_SCRIPT)


def test_same_output_random(sol):
    import random
    rng = random.Random(23)
    cmds = ["ADD", "add", "CANCEL", "FILL", "REPORT", "NOPE"]
    for _ in range(300):
        lines = []
        for _ in range(rng.randint(0, 25)):
            c = rng.choice(cmds)
            oid = rng.choice(["A", "B", "C"])
            if c.upper() == "ADD":
                lines.append("%s %s %s %s" % (c, oid, rng.choice(["1", "3", "0", "-2", "q"]),
                                              rng.choice(["1.25", "0", "7", "x", "0.333"])))
            elif c == "CANCEL":
                lines.append("CANCEL " + oid)
            elif c == "FILL":
                lines.append("FILL %s %s" % (oid, rng.choice(["1", "2", "5", "0", "z"])))
            else:
                lines.append(c)
        assert sol.process_orders(lines) == _original(lines), lines


def test_orderbook_api(sol):
    b = sol.OrderBook()
    b.add("X", 3, _D("2.00"))
    assert b.report() == "open=1 qty=3 value=6.00 filled=0.00"
    b.fill("X", 1)
    assert b.report() == "open=1 qty=2 value=4.00 filled=2.00"
    b.fill("X", 2)
    assert b.report() == "open=0 qty=0 value=0.00 filled=6.00"


def test_orderbook_errors(sol):
    b = sol.OrderBook()
    b.add("X", 1, _D("1"))
    assert _raises("duplicate order X", b.add, "X", 1, _D("1"))
    assert _raises("bad values for Y", b.add, "Y", 0, _D("1"))
    assert _raises("bad values for X", b.add, "X", 0, _D("1"))
    assert _raises("unknown order Q", b.cancel, "Q")
    assert _raises("unknown order Q", b.fill, "Q", 1)
    assert _raises("bad fill for X", b.fill, "X", 2)
    b.cancel("X")
    assert b.report() == "open=0 qty=0 value=0.00 filled=0.00"


def test_thin_loop(sol):
    import inspect
    src = inspect.getsource(sol.process_orders)
    assert "OrderBook" in src
    assert "filled_value" not in src
