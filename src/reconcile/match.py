"""Reconcile one quote against the invoices that belong to it.

The hard part is not reading the documents, it is deciding what counts as a
deviation. Three rules carry this module:

1. Compare in base units, never in the unit printed on the page. A quote in
   packs and an invoice in pieces describe the same delivery.
2. Sum every invoice that belongs to the quote before judging quantities.
   A supplier who delivers in two shipments has not overcharged.
3. Report an under-delivery only when the caller says the order is closed.
   Otherwise the shortfall is simply not invoiced yet. Getting this wrong is
   what makes an automated checker useless: it cries wolf on every partial
   delivery and people stop reading the report.
"""

from __future__ import annotations

import re
from decimal import Decimal

from .model import Document, Finding, LineItem

# Price tolerance. A purely absolute tolerance looks harmless until it meets a
# cent article: 0.005 EUR on a screw costing 0.004 EUR per piece is a 125 %
# blind spot, and a planted 12 % overcharge slips through unseen. The first
# scored run of this project did exactly that. The tolerance is therefore
# relative, with a tiny absolute floor for rounding noise on the document.
PRICE_TOLERANCE_RELATIVE = Decimal("0.005")  # 0.5 %
PRICE_TOLERANCE_ABSOLUTE = Decimal("0.0001")


def price_tolerance(reference: Decimal) -> Decimal:
    return max(PRICE_TOLERANCE_ABSOLUTE, abs(reference) * PRICE_TOLERANCE_RELATIVE)


def normalise(text: str) -> str:
    """Reduce a description to a comparable form."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _key(item: LineItem) -> str:
    """The identity of a position: SKU if present, else the description."""
    return item.sku.strip().upper() if item.sku.strip() else normalise(item.description)


def _fold(items: list[LineItem]) -> dict[str, list[LineItem]]:
    out: dict[str, list[LineItem]] = {}
    for item in items:
        out.setdefault(_key(item), []).append(item)
    return out


def reconcile(
    quote: Document,
    invoices: list[Document],
    *,
    order_closed: bool = False,
) -> list[Finding]:
    """Compare a quote against all invoices issued for it.

    Set ``order_closed`` once no further delivery is expected; only then does
    a shortfall become a finding.
    """
    quoted = _fold(quote.items)
    invoiced: dict[str, list[LineItem]] = {}
    for invoice in invoices:
        for key, items in _fold(invoice.items).items():
            invoiced.setdefault(key, []).extend(items)

    findings: list[Finding] = []

    for key, q_items in quoted.items():
        q_quantity = sum((i.base_quantity for i in q_items), Decimal("0"))
        q_price = q_items[0].base_unit_price
        sku = q_items[0].sku or key

        if key not in invoiced:
            if order_closed:
                findings.append(
                    Finding(
                        kind="missing_position",
                        sku=sku,
                        detail=(
                            f"quoted {q_quantity} base units, never invoiced"
                        ),
                        amount=-(q_quantity * q_price),
                    )
                )
            continue

        i_items = invoiced[key]
        i_quantity = sum((i.base_quantity for i in i_items), Decimal("0"))

        # Price: every invoice line must match the quoted base price.
        for line in i_items:
            delta = line.base_unit_price - q_price
            if abs(delta) > price_tolerance(q_price):
                findings.append(
                    Finding(
                        kind="price_mismatch",
                        sku=sku,
                        detail=(
                            f"quoted {q_price} per base unit, "
                            f"invoiced {line.base_unit_price}"
                        ),
                        amount=delta * line.base_quantity,
                    )
                )

        # Quantity: over-delivery always counts, under-delivery only when closed.
        if i_quantity > q_quantity:
            surplus = i_quantity - q_quantity
            findings.append(
                Finding(
                    kind="quantity_mismatch",
                    sku=sku,
                    detail=(
                        f"quoted {q_quantity} base units, "
                        f"invoiced {i_quantity}"
                    ),
                    amount=surplus * q_price,
                )
            )
        elif i_quantity < q_quantity and order_closed:
            shortfall = q_quantity - i_quantity
            findings.append(
                Finding(
                    kind="quantity_mismatch",
                    sku=sku,
                    detail=(
                        f"quoted {q_quantity} base units, "
                        f"only {i_quantity} invoiced and order closed"
                    ),
                    amount=-(shortfall * q_price),
                )
            )

    for key, i_items in invoiced.items():
        if key in quoted:
            continue
        amount = sum((i.total for i in i_items), Decimal("0"))
        findings.append(
            Finding(
                kind="extra_position",
                sku=i_items[0].sku or key,
                detail=f"invoiced but not quoted: {i_items[0].description}",
                amount=amount,
            )
        )

    return sorted(findings, key=lambda f: (f.kind, f.sku))
