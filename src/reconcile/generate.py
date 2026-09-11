"""Generate synthetic quotes and invoices as PDF, plus a ground truth file.

The generator knows which deviations it planted. That is what makes the
result measurable instead of merely plausible: the report can be scored
against the truth, so "it works" becomes a number.

Every name, article and price is invented. "Nordwind Baustoffe GmbH" does
not exist.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .model import BY_SKU, CATALOGUE, Document, LineItem

SUPPLIER = "Nordwind Baustoffe GmbH"
CUSTOMER = "Aurex Innenausbau GmbH"

# Which deviation to plant in a case. "clean" and the two partial variants
# must produce no finding - they are the traps.
CASES = (
    "clean",
    "price_mismatch",
    "over_delivery",
    "extra_position",
    "missing_position",
    "unit_change",
    "partial_delivery",
)


def _line(article, quantity: int) -> LineItem:
    return LineItem(
        sku=article.sku,
        description=article.name,
        quantity=Decimal(quantity),
        unit=article.unit,
        unit_price=article.list_price,
    )


def build_case(case: str, rng: random.Random) -> dict:
    """Return quote, invoices, closed-flag and the deviations planted."""
    articles = rng.sample(CATALOGUE, 4)
    quote_items = [_line(a, rng.choice([10, 20, 50, 100])) for a in articles]
    quote = Document("quote", f"Q-{rng.randint(1000, 9999)}", "2026-01-05", quote_items)

    invoice_items = [
        LineItem(i.sku, i.description, i.quantity, i.unit, i.unit_price)
        for i in quote_items
    ]
    invoices = [Document("invoice", f"R-{rng.randint(1000, 9999)}", "2026-01-20", invoice_items)]
    closed = True
    planted: list[dict] = []

    if case == "price_mismatch":
        # Pick the most expensive position, so that a 12 % overcharge is still
        # visible after rounding to the two decimals a real document carries.
        target = max(invoice_items, key=lambda i: i.unit_price)
        target.unit_price = (target.unit_price * Decimal("1.12")).quantize(Decimal("0.01"))
        planted.append({"kind": "price_mismatch", "sku": target.sku})

    elif case == "over_delivery":
        target = invoice_items[1]
        target.quantity += Decimal("15")
        planted.append({"kind": "quantity_mismatch", "sku": target.sku})

    elif case == "extra_position":
        spare = next(a for a in CATALOGUE if a not in articles)
        invoice_items.append(_line(spare, 5))
        planted.append({"kind": "extra_position", "sku": spare.sku})

    elif case == "missing_position":
        dropped = invoice_items.pop()
        planted.append({"kind": "missing_position", "sku": dropped.sku})

    elif case == "unit_change":
        # Same delivery, written in pieces instead of packs. Not a deviation.
        target = next((i for i in invoice_items if i.unit == "pack"), None)
        if target is None:
            target = invoice_items[0]
        else:
            target.quantity = target.base_quantity
            target.unit_price = target.base_unit_price
            target.unit = "pc"

    elif case == "partial_delivery":
        # Two invoices that together match the quote. Not a deviation.
        first, second = [], []
        for item in invoice_items:
            half = item.quantity / 2
            first.append(LineItem(item.sku, item.description, half, item.unit, item.unit_price))
            second.append(
                LineItem(item.sku, item.description, item.quantity - half, item.unit, item.unit_price)
            )
        invoices = [
            Document("invoice", f"R-{rng.randint(1000, 9999)}", "2026-01-20", first),
            Document("invoice", f"R-{rng.randint(1000, 9999)}", "2026-02-03", second),
        ]

    return {"case": case, "quote": quote, "invoices": invoices, "order_closed": closed, "planted": planted}


# --- PDF rendering ---------------------------------------------------------

# One position is written as a single line with a fixed separator, so the
# extractor has a defined contract. Real supplier documents are far messier;
# see the "What this does not show" section of the README.
SEP = " | "


def render_pdf(document: Document, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    y = height - 25 * mm

    title = "QUOTE" if document.kind == "quote" else "INVOICE"
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, f"{title} {document.number}")
    y -= 8 * mm

    c.setFont("Helvetica", 9)
    for line in (SUPPLIER, f"To: {CUSTOMER}", f"Date: {document.date}"):
        c.drawString(20 * mm, y, line)
        y -= 5 * mm

    y -= 4 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20 * mm, y, SEP.join(["SKU", "Description", "Qty", "Unit", "Price", "Total"]))
    y -= 6 * mm

    c.setFont("Helvetica", 9)
    for item in document.items:
        row = SEP.join(
            [
                item.sku,
                item.description,
                f"{item.quantity}",
                item.unit,
                f"{item.unit_price}",
                f"{item.total}",
            ]
        )
        c.drawString(20 * mm, y, row)
        y -= 5 * mm
        if y < 25 * mm:
            c.showPage()
            y = height - 25 * mm
            c.setFont("Helvetica", 9)

    y -= 4 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, f"Total: {document.total}")
    c.save()


def generate_dataset(out_dir: Path, seed: int = 20260911) -> dict:
    """Write one folder per case and a ground truth file next to them."""
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    truth: list[dict] = []

    for case in CASES:
        built = build_case(case, rng)
        folder = out_dir / case
        render_pdf(built["quote"], folder / "quote.pdf")
        for invoice in built["invoices"]:
            render_pdf(invoice, folder / f"invoice-{invoice.number}.pdf")
        truth.append(
            {
                "case": case,
                "folder": case,
                "quote": built["quote"].number,
                "invoices": [i.number for i in built["invoices"]],
                "order_closed": built["order_closed"],
                "planted": built["planted"],
            }
        )

    truth_path = out_dir / "ground_truth.json"
    truth_path.write_text(json.dumps(truth, indent=2), encoding="utf-8")
    return {"cases": len(truth), "truth": truth_path}
