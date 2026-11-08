#!/usr/bin/env python3
"""Disposable, model-bound views. This module has no manifest write API."""
import argparse
import sys
from adopt_data import (Context, Problem, Finding, require, digest, sha, index,
                        expansion, load_current, encoded, read_json, cli_error, control)
from adopt_resources import blocked, recheck
from adopt_freshness import evaluate, exception_coverage


def resolve(ctx, row_id, caller_model_id, purpose="use", authorisation="auto", cached=None,
            acceptance_plan=None, coordinator=None, importance="ordinary",
            freshness_decision_refs=None, route="use-directly"):
    doc, raw = load_current(ctx)
    row = index(doc, "rows").get(row_id)
    require(row is not None, "unknown row")
    if purpose == "acceptance" and row.get("maintenance_id"):
        require(coordinator is not None and coordinator.ctx is ctx and coordinator.held,
                "reserved acceptance requires private held supervisor")
        _, hold = coordinator.current()
        require(row["maintenance_id"] == hold["id"], "acceptance reservation mismatch")
    else:
        blocked(doc, row, ctx)
    if purpose == "describe":
        return {"register_id": doc["register_id"], "revision": doc["revision"],
                "row": row, "purpose": "metadata/compatibility", "qualified_delivery": False,
                "legacy_findings": [row_id] if row["lifecycle"]["state"] == "legacy-recorded" else [],
                "control_hits": control()}
    require(row["lifecycle"]["state"] in ("prepared", "active"), "no managed delivery for state", Finding)
    if purpose == "acceptance":
        require(caller_model_id and acceptance_plan and set(acceptance_plan) ==
                {"row_id", "caller_model_id", "resource_ids", "criterion"} and
                acceptance_plan["row_id"] == row_id and acceptance_plan["caller_model_id"] == caller_model_id and
                set(acceptance_plan["resource_ids"]) ==
                {b["resource_id"] for b in expansion(doc, row)["bindings"]} and
                acceptance_plan["criterion"] == row["acceptance"]["criterion"],
                "explicit exact acceptance plan required")
        require(any(e["subject"]["type"] == "model-release" and
                e["subject"]["model_id"] == caller_model_id for e in doc["evidence"]),
                "unknown acceptance model")
        return {"register_id": doc["register_id"], "revision": doc["revision"], "row_id": row_id,
                "caller_model_id": caller_model_id, "purpose": "acceptance-only",
                "qualified_delivery": False, "plan_sha256": digest(acceptance_plan), "control_hits": control()}
    require(purpose == "use", "unknown query purpose")
    skill_bearing = any(b["resource_definition"]["type"] == "skill-tree"
                        for b in expansion(doc, row)["bindings"])
    require(not skill_bearing or caller_model_id, "actual caller-model identity required")
    require(importance in ("ordinary", "important"), "unknown importance")
    assessment = evaluate(doc, row, ctx, caller_model_id)
    decisions = exception_coverage(doc, row, ctx, assessment, freshness_decision_refs, route)
    ranks = {"auto": 0, "propose-first": 1, "by-name": 2}
    # Conditions are printed; absent intent classification uses the restrictive bound.
    level = max([row["level"]["base"]] + [c["level"] for c in row["level"]["conditions"]], key=ranks.get)
    require(authorisation in ranks and ranks[authorisation] >= ranks[level], "use-level authorisation required", Finding)
    recheck(doc, row, ctx)
    result = {"register_id": doc["register_id"], "revision": doc["revision"],
              "data_sha256": sha(raw), "row_id": row_id,
              "definition_sha256": digest(expansion(doc, row)), "caller_model_id": caller_model_id,
              "qualification_refs": assessment["qualification_refs"], "purpose": purpose,
              "assurance_tier": assessment["tier"], "assurance_basis": assessment["skills"],
              "importance": importance,
              "testing_recommended": importance == "important" and assessment["tier"] == "claimed",
              "freshness_decision_refs": decisions, "route": route,
              "decision_records": [index(doc, "evidence")[eid] for eid in decisions],
              "owner_identity": doc["policy"]["owner_identity"],
              "state": "prepared-delivery" if row["lifecycle"]["state"] == "prepared" else "active",
              "resources": expansion(doc, row)["bindings"], "control_hits": control()}
    require(cached is None or cached == result, "stale or differently model-bound cached view", Finding)
    return result


def main():
    from adopt_data import ProbeParser
    parser = ProbeParser(description=__doc__)
    for key in ("vault", "home", "row"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--caller-model-id")
    parser.add_argument("--purpose", choices=("describe", "use", "acceptance"), default="describe")
    parser.add_argument("--authorisation", default="auto")
    parser.add_argument("--cached")
    parser.add_argument("--acceptance-plan")
    parser.add_argument("--importance", choices=("ordinary", "important"), default="ordinary")
    parser.add_argument("--route", choices=("use-directly", "take-pattern"), default="use-directly")
    parser.add_argument("--freshness-decision-ref", action="append", default=[])
    args = parser.parse_args()
    try:
        result = resolve(Context(args.vault, args.home), args.row, args.caller_model_id,
                         args.purpose, args.authorisation, read_json(args.cached) if args.cached else None,
                         read_json(args.acceptance_plan) if args.acceptance_plan else None,
                         importance=args.importance, freshness_decision_refs=args.freshness_decision_ref,
                         route=args.route)
        print(encoded(result).decode(), end="")
        return 1 if result.get("legacy_findings") else 0
    except (Problem, OSError, ValueError, TypeError, KeyError, IndexError, RuntimeError) as exc:
        return cli_error(exc)


if __name__ == "__main__":
    sys.exit(main())
