"""Turn findings into something a person can act on, and score a run."""

from __future__ import annotations

from decimal import Decimal

from .model import Finding

LABEL = {
    "price_mismatch": "Price differs from quote",
    "quantity_mismatch": "Quantity differs from quote",
    "extra_position": "Invoiced but never quoted",
    "missing_position": "Quoted but never invoiced",
}


def render(findings: list[Finding], *, quote_number: str) -> str:
    if not findings:
        return f"{quote_number}: no deviations found."

    lines = [f"{quote_number}: {len(findings)} deviation(s)", ""]
    for f in findings:
        sign = "+" if f.amount >= 0 else "-"
        lines.append(f"  [{LABEL[f.kind]}] {f.sku}")
        lines.append(f"      {f.detail}")
        lines.append(f"      effect: {sign}{abs(f.amount):.2f} EUR")
    total = sum((f.amount for f in findings), Decimal("0"))
    lines.append("")
    lines.append(f"  net effect: {total:.2f} EUR")
    return "\n".join(lines)


def score(found: list[Finding], planted: list[dict]) -> dict:
    """Compare what the matcher found against what the generator planted."""
    found_keys = {(f.kind, f.sku) for f in found}
    planted_keys = {(p["kind"], p["sku"]) for p in planted}
    hits = found_keys & planted_keys
    return {
        "planted": len(planted_keys),
        "detected": len(hits),
        "missed": sorted(planted_keys - found_keys),
        "false_alarms": sorted(found_keys - planted_keys),
    }
