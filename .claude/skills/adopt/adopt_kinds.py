#!/usr/bin/env python3
"""Read-only planning adapter. Execution uses the guarded writer interface."""
import argparse
import sys
from adopt_data import (Problem, require, shape, ref, encoded, read_json, cli_error,
                        control, KINDS, ROUTES)


def plan(request):
    require(type(request) is dict and set(request) ==
            {"kind", "name", "pin", "scope", "hooks_present", "level", "route"},
            "closed planning request required")
    require(request["kind"] in KINDS and request["route"] in ROUTES, "unknown kind/route")
    shape(request["pin"], ref("pin"))
    require(request["scope"] == "local", "installation plan requires local scope")
    require(type(request["hooks_present"]) is bool and
            request["level"] in ("auto", "propose-first", "by-name"), "invalid hook/level declaration")
    require(not request["hooks_present"] or request["level"] != "auto", "hooks cannot be auto")
    manual = request["pin"]["type"] in ("git-commit", "floating", "unresolved")
    return {"request": request, "state": "planned", "installation_mode": "manual" if manual else "reviewed-adapter",
            "commands": [], "next_writer_operation": "maintenance-run", "isolated_trial_required":
            request["kind"] == "plugin", "findings": 0, "control_hits": control()}


def main():
    from adopt_data import ProbeParser
    parser = ProbeParser(description=__doc__)
    parser.add_argument("--request", required=True)
    args = parser.parse_args()
    try:
        print(encoded(plan(read_json(args.request))).decode(), end="")
        return 0
    except (Problem, OSError, ValueError, TypeError, KeyError, IndexError, RuntimeError) as exc:
        return cli_error(exc)


if __name__ == "__main__":
    sys.exit(main())
