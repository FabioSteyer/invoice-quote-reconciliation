"""One test per deviation the matcher is supposed to see - and one per
situation it must stay quiet about."""

from decimal import Decimal

import pytest

from reconcile.match import reconcile
from reconcile.model import Document, LineItem


def item(sku, qty, unit, price, description="Gypsum board 12.5 mm"):
    return LineItem(sku, description, Decimal(qty), unit, Decimal(price))


def quote(*items):
    return Document("quote", "Q-1", "2026-01-05", list(items))


def invoice(*items, number="R-1"):
    return Document("invoice", number, "2026-01-20", list(items))


def kinds(findings):
    return sorted(f.kind for f in findings)


def test_clean_invoice_produces_no_findings():
    q = quote(item("NW-1001", "100", "pc", "8.40"))
    r = invoice(item("NW-1001", "100", "pc", "8.40"))
    assert reconcile(q, [r]) == []


def test_price_mismatch_is_reported_with_amount():
    q = quote(item("NW-1001", "100", "pc", "8.40"))
    r = invoice(item("NW-1001", "100", "pc", "9.40"))
    findings = reconcile(q, [r])
    assert kinds(findings) == ["price_mismatch"]
    assert findings[0].amount == Decimal("100.00")


def test_over_delivery_is_a_quantity_mismatch():
    q = quote(item("NW-1001", "100", "pc", "8.40"))
    r = invoice(item("NW-1001", "120", "pc", "8.40"))
    findings = reconcile(q, [r])
    assert kinds(findings) == ["quantity_mismatch"]
    assert findings[0].amount == Decimal("168.00")


def test_extra_position_is_reported():
    q = quote(item("NW-1001", "100", "pc", "8.40"))
    r = invoice(
        item("NW-1001", "100", "pc", "8.40"),
        item("NW-1006", "2", "pc", "42.00", "Primer 10 l"),
    )
    findings = reconcile(q, [r])
    assert kinds(findings) == ["extra_position"]
    assert findings[0].amount == Decimal("84.00")


def test_missing_position_only_once_the_order_is_closed():
    q = quote(
        item("NW-1001", "100", "pc", "8.40"),
        item("NW-1006", "2", "pc", "42.00", "Primer 10 l"),
    )
    r = invoice(item("NW-1001", "100", "pc", "8.40"))
    assert reconcile(q, [r]) == []
    closed = reconcile(q, [r], order_closed=True)
    assert kinds(closed) == ["missing_position"]


def test_unit_change_between_quote_and_invoice_is_not_a_deviation():
    """Quote in packs of ten, invoice in single pieces, same delivery."""
    q = quote(item("NW-1003", "50", "pack", "0.40", "Drywall screw 3.5x35"))
    r = invoice(item("NW-1003", "500", "pc", "0.04", "Drywall screw 3.5x35"))
    assert reconcile(q, [r]) == []


def test_partial_delivery_across_two_invoices_is_not_a_deviation():
    q = quote(item("NW-1001", "100", "pc", "8.40"))
    r1 = invoice(item("NW-1001", "60", "pc", "8.40"), number="R-1")
    r2 = invoice(item("NW-1001", "40", "pc", "8.40"), number="R-2")
    assert reconcile(q, [r1, r2], order_closed=True) == []


def test_open_partial_delivery_stays_quiet():
    q = quote(item("NW-1001", "100", "pc", "8.40"))
    r = invoice(item("NW-1001", "60", "pc", "8.40"))
    assert reconcile(q, [r]) == []


def test_spelling_difference_still_matches_via_sku():
    q = quote(item("NW-1001", "10", "pc", "8.40", "Gypsum board 12.5 mm"))
    r = invoice(item("NW-1001", "10", "pc", "8.40", "Gypsum bd. 12,5mm"))
    assert reconcile(q, [r]) == []


def test_missing_sku_falls_back_to_normalised_description():
    q = quote(item("", "10", "pc", "8.40", "Gypsum board 12.5 mm"))
    r = invoice(item("", "10", "pc", "8.40", "GYPSUM  BOARD 12.5 MM"))
    assert reconcile(q, [r]) == []


def test_rounding_noise_below_tolerance_is_ignored():
    q = quote(item("NW-1001", "10", "pc", "8.40"))
    r = invoice(item("NW-1001", "10", "pc", "8.404"))
    assert reconcile(q, [r]) == []


def test_unknown_unit_is_rejected_loudly():
    q = quote(item("NW-1001", "10", "barrel", "8.40"))
    with pytest.raises(ValueError):
        reconcile(q, [invoice(item("NW-1001", "10", "pc", "8.40"))])
