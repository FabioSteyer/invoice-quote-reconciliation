"""Command line entry point.

    python -m reconcile generate --out out
    python -m reconcile check --out out
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .extract import extract
from .generate import generate_dataset
from .match import reconcile
from .report import render, score


def cmd_generate(args) -> int:
    result = generate_dataset(Path(args.out), seed=args.seed)
    print(f"generated {result['cases']} cases in {args.out}")
    print(f"ground truth: {result['truth']}")
    return 0


def cmd_check(args) -> int:
    out = Path(args.out)
    truth = json.loads((out / "ground_truth.json").read_text(encoding="utf-8"))

    totals = {"planted": 0, "detected": 0, "false_alarms": 0}
    failures = 0

    for case in truth:
        folder = out / case["folder"]
        quote_result = extract(folder / "quote.pdf")
        invoices = [
            extract(p).document for p in sorted(folder.glob("invoice-*.pdf"))
        ]
        findings = reconcile(
            quote_result.document, invoices, order_closed=case["order_closed"]
        )

        print("=" * 68)
        print(f"case: {case['case']}")
        print(render(findings, quote_number=quote_result.document.number))

        s = score(findings, case["planted"])
        totals["planted"] += s["planted"]
        totals["detected"] += s["detected"]
        totals["false_alarms"] += len(s["false_alarms"])
        if s["missed"] or s["false_alarms"]:
            failures += 1
            print(f"  SCORE: missed={s['missed']} false_alarms={s['false_alarms']}")
        else:
            print("  SCORE: as planted")

    print("=" * 68)
    print(
        f"planted {totals['planted']}, detected {totals['detected']}, "
        f"false alarms {totals['false_alarms']}, cases off target {failures}"
    )
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reconcile")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="write synthetic PDFs and ground truth")
    g.add_argument("--out", default="out")
    g.add_argument("--seed", type=int, default=20260911)
    g.set_defaults(func=cmd_generate)

    c = sub.add_parser("check", help="read the PDFs back and score the result")
    c.add_argument("--out", default="out")
    c.set_defaults(func=cmd_check)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
