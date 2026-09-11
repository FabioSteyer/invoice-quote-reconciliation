# Invoice / quote reconciliation

A supplier sends a quote, then invoices against it. Whether the invoice matches
what was agreed is something nobody checks position by position once a document
runs to three digits of line items. This project reads both documents out of
PDF, matches the positions, and reports every deviation with its monetary
effect.

Everything here runs on invented data. No supplier, article, price or customer
in this repository corresponds to a real company.

## Run it

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # Linux, macOS
pip install -e ".[dev]"

python -m reconcile generate --out out   # write synthetic PDFs + ground truth
python -m reconcile check --out out      # read them back and score the result
pytest                                   # 20 tests
```

`check` prints a report per case and, at the end, a score:

```
planted 4, detected 4, false alarms 0, cases off target 0
```

## Why the ground truth file is the point

The generator knows which deviations it planted and writes them to
`ground_truth.json`. The checker compares its own findings against that file.
That turns "it works" into a number: how many planted deviations were found,
and how many findings were invented. Without it, a reconciliation tool can
only be believed, not verified.

Three of the seven generated cases contain no deviation at all. They are the
traps, and they matter more than the obvious ones:

| Case | Expected |
| --- | --- |
| `clean` | nothing |
| `unit_change` | nothing — quote in packs, invoice in pieces, same delivery |
| `partial_delivery` | nothing — two invoices that together match the quote |
| `price_mismatch` | one finding |
| `over_delivery` | one finding |
| `extra_position` | one finding |
| `missing_position` | one finding |

A checker that reports every partial delivery as an error is worse than no
checker: people stop reading the report after the second week.

## Three decisions that carry the matcher

**Compare in base units, never in the printed unit.** A quote in packs of ten
and an invoice in single pieces describe the same delivery. The comparison
happens after normalisation, not before.

**Sum all invoices belonging to a quote before judging quantity.** A supplier
who ships in two batches has not overcharged. Judging each invoice on its own
against the full quote produces a false alarm every time.

**Report a shortfall only when the order is closed.** Until then, the missing
quantity is simply not invoiced yet. This is a caller decision
(`order_closed=True`), not something the data can answer.

## A mistake this project found in itself

The first scored run reported **3 of 4** planted deviations. The one it missed
was a 12 % overcharge on a drywall screw.

The cause was the price tolerance. It was absolute — 0.005 EUR — which looks
harmless until it meets an article costing 0.004 EUR per piece. There, the
tolerance is larger than the entire unit price, and no overcharge of any size
can ever exceed it. The bug was not in the matching logic but in a constant
that looked obviously reasonable.

The fix was a relative tolerance (0.5 %) with a small absolute floor against
rounding noise. `tests/test_tolerance.py` keeps that hole closed, including the
exact case that slipped through.

This is recorded here rather than quietly fixed because it is the honest
answer to "how do you know it works": the scoring harness caught it, and
nothing else would have.

## What this does not show

- **Real supplier documents.** The generated PDFs write one position per line
  with a fixed separator, so the extractor has a defined contract. Real
  documents are far messier: multi-line descriptions, wrapped columns, scanned
  pages, per-supplier layouts. Handling those is a larger problem than the one
  solved here.
- **Proprietary data structures.** Decoding a wholesaler's own price format is
  a different problem and cannot be shown without that supplier's data.
- **Integration.** No ERP connection, no database, no scheduler. The scope
  ends at a report on stdout.
- **OCR.** The extractor reads the text layer. Scanned documents would need an
  OCR stage that is not part of this repository.

## Layout

```
src/reconcile/
  model.py      data types, unit conversion, the fictional catalogue
  generate.py   synthetic quotes and invoices as PDF + ground truth
  extract.py    read positions back out of a PDF, count what it could not read
  match.py      the comparison, and the three decisions above
  report.py     human readable output, and scoring against the truth
  cli.py        generate / check
tests/
  test_match.py      one test per deviation, one per trap
  test_tolerance.py  regression tests for the tolerance bug
  test_pipeline.py   end to end, across four generator seeds
```

## On AI assistance

This repository was written with AI assistance. The problem, the decisions
recorded above and the review of the result are mine; the tolerance bug and its
fix came out of running the scoring harness, not out of the model getting it
right the first time.

## Licence

MIT. See `LICENSE`.
