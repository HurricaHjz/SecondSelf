#!/usr/bin/env python3
"""Stdout-only row-resource audit. Reads the authoritative structured register."""
import argparse
import sys
from adopt_data import Context, Problem, Finding, require, load_current, index, encoded, cli_error, control
from adopt_resources import recheck


def audit(ctx, row_ids=None):
    doc, _ = load_current(ctx)
    rows = index(doc, "rows")
    selected = list(rows) if row_ids is None else row_ids
    require(all(r in rows for r in selected), "unknown audit row")
    findings, checked = [], []
    for rid in selected:
        row = rows[rid]
        if row["lifecycle"]["state"] == "legacy-recorded":
            findings.append({"row_id": rid, "finding": "legacy recorded; not re-proved"})
        elif row["lifecycle"]["state"] in ("active", "prepared"):
            try:
                checks = recheck(doc, row, ctx)
                checked.append({"row_id": rid, "checks": len(checks)})
            except Finding as exc:
                findings.append({"row_id": rid, "finding": str(exc)})
    return {"rows": len(selected), "checked": checked, "findings": findings, "control_hits": control()}


def main():
    from adopt_data import ProbeParser
    parser = ProbeParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--home", required=True)
    parser.add_argument("--row", action="append")
    args = parser.parse_args()
    try:
        result = audit(Context(args.vault, args.home), args.row)
        print(encoded(result).decode(), end="")
        return 1 if result["findings"] else 0
    except (Problem, OSError, ValueError, TypeError, KeyError, IndexError, RuntimeError) as exc:
        return cli_error(exc)


if __name__ == "__main__":
    sys.exit(main())
