"""End to end: generate PDFs, read them back, score against the truth.

This is the test that matters. It does not check that the code runs, it
checks that every planted deviation is found and that no clean case produces
a false alarm.
"""

import json
from pathlib import Path

from reconcile.extract import extract
from reconcile.generate import generate_dataset
from reconcile.match import reconcile
from reconcile.report import score


def run_all(out: Path):
    truth = json.loads((out / "ground_truth.json").read_text(encoding="utf-8"))
    results = []
    for case in truth:
        folder = out / case["folder"]
        quote = extract(folder / "quote.pdf")
        invoices = [extract(p) for p in sorted(folder.glob("invoice-*.pdf"))]
        findings = reconcile(
            quote.document,
            [i.document for i in invoices],
            order_closed=case["order_closed"],
        )
        results.append(
            {
                "case": case["case"],
                "score": score(findings, case["planted"]),
                "skipped": quote.skipped_lines + sum(i.skipped_lines for i in invoices),
            }
        )
    return results


def test_every_planted_deviation_is_found_and_nothing_else(tmp_path):
    generate_dataset(tmp_path, seed=20260911)
    results = run_all(tmp_path)

    assert len(results) == 7
    for r in results:
        assert r["score"]["missed"] == [], f"{r['case']}: missed {r['score']['missed']}"
        assert r["score"]["false_alarms"] == [], f"{r['case']}: {r['score']['false_alarms']}"


def test_extraction_skips_nothing(tmp_path):
    """A skipped line means the extractor lost data silently."""
    generate_dataset(tmp_path, seed=20260911)
    for r in run_all(tmp_path):
        assert r["skipped"] == 0, f"{r['case']}: {r['skipped']} unreadable lines"


def test_result_is_stable_across_seeds(tmp_path):
    """The matcher must not depend on which articles the generator picked."""
    for seed in (1, 42, 20260911, 99999):
        folder = tmp_path / f"seed-{seed}"
        generate_dataset(folder, seed=seed)
        for r in run_all(folder):
            assert r["score"]["missed"] == [], f"seed {seed}, {r['case']}"
            assert r["score"]["false_alarms"] == [], f"seed {seed}, {r['case']}"
