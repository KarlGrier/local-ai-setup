from decimal import Decimal


def money(x):
    """Format a Decimal amount with two decimals, rounding halves up (2.675 -> 2.68)."""
    return f"{round(float(x), 2):.2f}"


def format_report(store):
    """One line per item, sorted by SKU: 'SKU | NAME | QTY | VALUE', then a 'TOTAL | VALUE' line."""
    lines = []
    for item in store.items():
        lines.append(f"{item.sku} | {item.name} | {item.qty} | {money(item.value)}")
    lines.append(f"TOTAL | {money(store.total_value())}")
    return "\n".join(lines)
