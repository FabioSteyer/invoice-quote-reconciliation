"""Read positions back out of a PDF.

The extractor is deliberately strict: it accepts a line only if it has the
expected number of fields and if quantity and prices parse as numbers.
Anything else is skipped and counted, so a silently truncated document shows
up as a low line count rather than as a clean result on half the data.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pdfplumber

from .model import Document, LineItem, PACK_SIZES

SEP = "|"
EXPECTED_FIELDS = 6


@dataclass
class ExtractionResult:
    document: Document
    skipped_lines: int


def _parse_row(raw: str) -> LineItem | None:
    parts = [p.strip() for p in raw.split(SEP)]
    if len(parts) != EXPECTED_FIELDS:
        return None
    sku, description, qty, unit, price, _total = parts
    if unit not in PACK_SIZES:
        return None
    try:
        quantity = Decimal(qty)
        unit_price = Decimal(price)
    except InvalidOperation:
        return None
    return LineItem(sku, description, quantity, unit, unit_price)


def extract(path: Path) -> ExtractionResult:
    """Read one quote or invoice PDF."""
    text_lines: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text_lines.extend((page.extract_text() or "").splitlines())

    kind = "quote"
    number = path.stem
    date = ""
    items: list[LineItem] = []
    skipped = 0

    for line in text_lines:
        stripped = line.strip()
        if stripped.startswith("QUOTE "):
            kind, number = "quote", stripped.split(" ", 1)[1].strip()
            continue
        if stripped.startswith("INVOICE "):
            kind, number = "invoice", stripped.split(" ", 1)[1].strip()
            continue
        if stripped.startswith("Date:"):
            date = stripped.split(":", 1)[1].strip()
            continue
        if SEP not in stripped:
            continue
        if stripped.startswith("SKU"):  # header row
            continue
        item = _parse_row(stripped)
        if item is None:
            skipped += 1
        else:
            items.append(item)

    return ExtractionResult(Document(kind, number, date, items), skipped)
