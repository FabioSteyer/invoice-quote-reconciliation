"""Regression tests for the price tolerance.

The first scored run of this project reported 3 of 4 planted deviations. The
one it missed was a 12 % overcharge on a screw. The tolerance was absolute
(0.005 EUR) while the article cost 0.004 EUR per piece, so the overcharge was
mathematically invisible. These tests keep that hole closed.
"""

from decimal import Decimal

from reconcile.match import price_tolerance, reconcile
from reconcile.model import Document, LineItem


def item(sku, qty, unit, price, description="Drywall screw 3.5x35"):
    return LineItem(sku, description, Decimal(qty), unit, Decimal(price))


def test_tolerance_scales_with_the_price():
    assert price_tolerance(Decimal("100")) > price_tolerance(Decimal("1"))


def test_tolerance_never_collapses_to_zero():
    assert price_tolerance(Decimal("0")) > 0


def test_twelve_percent_overcharge_on_a_cent_article_is_caught():
    """The exact case the first run missed."""
    quote = Document("quote", "Q-1", "2026-01-05", [item("NW-1003", "50", "pack", "0.04")])
    invoice = Document("invoice", "R-1", "2026-01-20", [item("NW-1003", "50", "pack", "0.045")])
    findings = reconcile(quote, [invoice])
    assert [f.kind for f in findings] == ["price_mismatch"]


def test_twelve_percent_overcharge_on_an_expensive_article_is_caught():
    quote = Document("quote", "Q-1", "2026-01-05", [item("NW-1007", "3", "pc", "64.30", "Foil")])
    invoice = Document("invoice", "R-1", "2026-01-20", [item("NW-1007", "3", "pc", "72.02", "Foil")])
    findings = reconcile(quote, [invoice])
    assert [f.kind for f in findings] == ["price_mismatch"]


def test_half_a_percent_stays_below_the_threshold():
    quote = Document("quote", "Q-1", "2026-01-05", [item("NW-1007", "3", "pc", "64.30", "Foil")])
    invoice = Document("invoice", "R-1", "2026-01-20", [item("NW-1007", "3", "pc", "64.45", "Foil")])
    assert reconcile(quote, [invoice]) == []
