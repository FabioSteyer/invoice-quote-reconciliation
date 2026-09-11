"""Core data types and the synthetic article catalogue.

Everything here is invented. No supplier, article number or price in this
project corresponds to a real company.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

# A "pack" is a fixed multiple of a base unit. Quotes are often written in
# packs while invoices list single pieces, which is one of the mismatches
# the matcher has to see through.
PACK_SIZES: dict[str, int] = {"pc": 1, "pack": 10, "pallet": 480}


def to_base_units(quantity: Decimal, unit: str) -> Decimal:
    """Convert a quantity to base units (pieces)."""
    if unit not in PACK_SIZES:
        raise ValueError(f"unknown unit: {unit!r}")
    return quantity * PACK_SIZES[unit]


@dataclass(frozen=True)
class Article:
    """One entry of the fictional supplier's catalogue."""

    sku: str
    name: str
    unit: str
    list_price: Decimal  # price per *selling* unit, i.e. per `unit`


@dataclass
class LineItem:
    """One position on a quote or an invoice."""

    sku: str
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal  # price per *unit*, not per base unit

    @property
    def base_quantity(self) -> Decimal:
        return to_base_units(self.quantity, self.unit)

    @property
    def base_unit_price(self) -> Decimal:
        return self.unit_price / PACK_SIZES[self.unit]

    @property
    def total(self) -> Decimal:
        return self.quantity * self.unit_price


@dataclass
class Document:
    """A quote or an invoice."""

    kind: Literal["quote", "invoice"]
    number: str
    date: str
    items: list[LineItem] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((i.total for i in self.items), Decimal("0"))


FindingKind = Literal[
    "price_mismatch",
    "quantity_mismatch",
    "extra_position",
    "missing_position",
]


@dataclass(frozen=True)
class Finding:
    """One deviation between an invoice and its quote."""

    kind: FindingKind
    sku: str
    detail: str
    amount: Decimal  # monetary effect, positive = invoice too high


CATALOGUE: tuple[Article, ...] = (
    Article("NW-1001", "Gypsum board 12.5 mm", "pc", Decimal("8.40")),
    Article("NW-1002", "Insulation wool 100 mm", "pack", Decimal("3.15")),
    Article("NW-1003", "Drywall screw 3.5x35", "pack", Decimal("0.04")),
    Article("NW-1004", "Metal stud CW 75", "pc", Decimal("6.90")),
    Article("NW-1005", "Joint compound 25 kg", "pc", Decimal("17.50")),
    Article("NW-1006", "Primer 10 l", "pc", Decimal("42.00")),
    Article("NW-1007", "Vapour barrier foil 50 m", "pc", Decimal("64.30")),
    Article("NW-1008", "Corner bead 2.5 m", "pc", Decimal("2.20")),
    Article("NW-1009", "Acoustic sealant 310 ml", "pc", Decimal("6.75")),
    Article("NW-1010", "Anchor bolt M8", "pack", Decimal("0.38")),
)

BY_SKU: dict[str, Article] = {a.sku: a for a in CATALOGUE}
