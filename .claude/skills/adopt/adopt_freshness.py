#!/usr/bin/env python3
"""Read-only candidate/model qualification. Supplied artefacts, no network."""
import argparse
import copy
import base64
import sys
from pathlib import Path
from adopt_data import (Context, Problem, Finding, require, digest, index, operational_definition,
                        load_current, date, timestamp, encoded, cli_error, control,
                        shape, ref, evidence_ids, evidence_closure, COMPARISON, obj, S, IDS, DELIVERY_ROUTE, TIER)
from adopt_resources import evidence_body, evidence_record, observation


def qualification_observation(resource, observed):
    """Task qualification follows exact skill bytes, not a staging inode.

    The resource definition retains the installation destination and requirements.
    Activation/resource checks separately retain full physical observations.
    """
    require(resource["type"] == "skill-tree" and observed["type"] == "content",
            "qualification requires a skill content observation")
    return {"type": "skill-qualification", "resource_definition_sha256": digest(resource),
            "pin_sha256": resource["expected"]["pin_sha256"],
            "skill_tree_sha256": observed["sha256"]}


# Ordinal derived from the three ordered assurance states in the policy.
TIERS = ("unproven", "claimed", "proven")
DELIVERY_ROUTES = {"use-directly": "use-directly", "take-pattern": "internalise"}


def assurance_scope(doc, row, skill, model_id, release_date):
    resource = index(doc, "resources")[skill["resource_id"]]
    return digest({"kind": "skill-assurance-v2", "register_id": doc["register_id"],
        "row_id": row["id"], "resource_id": resource["id"],
        "resource_definition_sha256": digest(resource),
        "pin_sha256": skill["candidate"]["pin_sha256"],
        "skill_tree_sha256": skill["candidate"]["skill_tree_sha256"],
        "model_id": model_id, "model_release_date": release_date,
        "criterion": row["acceptance"]["criterion"], "judge": row["output_judge"]})


def owner_judgement(doc, record, body):
    owner = doc["policy"]["owner_identity"]
    require(owner is not None and record["kind"] == "human" and
            record["method"].get("judge") == owner and body.get("human_judge") == owner,
            "O5_OWNER_MISMATCH: configured owner judgement required", Finding)
    require(record["method"].get("criterion") == body.get("criterion", record["method"].get("criterion")),
            "O5_OWNER_MISMATCH: human criterion differs", Finding)


def checked_outcome(row, record, body):
    require(record["kind"] == "scripted" and record["method"].get("implementation_sha256") and
            body.get("positive_control") is True and body.get("negative_control") is True and
            body.get("criterion") == row["acceptance"]["criterion"] and body.get("output"),
            "O5_CHECK: captured automatic result and controls required", Finding)


def task_record(doc, row, ctx, scope, identity):
    """A task label never substitutes for captured inputs and the current job."""
    require(all(k in identity for k in ("task_id", "task_evidence_ref", "task_sha256")),
            "O5_TASK_MISMATCH: missing task binding", Finding)
    record, body = evidence_body(doc, identity["task_evidence_ref"], ctx)
    expected = {"type": "skill-task", "scope_sha256": scope,
                "task_id": identity["task_id"], "task_sha256": identity["task_sha256"]}
    require("task" in body, "O5_TASK_MISMATCH: frozen task capture missing")
    require(record["subject"] == expected and record["kind"] == "captured-source",
            "O5_TASK_MISMATCH: frozen record subject", Finding)
    task = body["task"]
    shape(task, ref("task"))
    jobs = index(doc, "jobs")
    require(digest(task) == identity["task_sha256"] and task["task_id"] == identity["task_id"] and
            task["job_id"] in jobs and task["definition"] == jobs[task["job_id"]]["definition"] and
            any(r["job_id"] == task["job_id"] and r["status"] == "implemented" for r in row["routes"]) and
            task["criterion"] == row["acceptance"]["criterion"],
            "O5_TASK_MISMATCH: content, routed job or criterion", Finding)
    names = [i["name"] for i in task["inputs"]]
    require(names == sorted(set(names)), "O5_TASK_MISMATCH: input names must be unique and sorted", Finding)
    for item in task["inputs"]:
        try:
            raw = base64.b64decode(item["content_base64"], validate=True)
        except (ValueError, UnicodeError) as exc:
            raise Finding("O5_TASK_MISMATCH: invalid base64 capture") from exc
        require(base64.b64encode(raw).decode("ascii") == item["content_base64"],
                "O5_TASK_MISMATCH: noncanonical base64 capture", Finding)
    return record


def run_record(doc, row, ctx, scope, eid, event, mode, expected_task=None, after=None):
    record, body = evidence_record(doc, eid, ctx)
    subject = record["subject"]
    require(subject["type"] == "skill-run" and subject["scope_sha256"] == scope and
            subject["mode"] == mode, "O5_RUN: subject or mode mismatch", Finding)
    identity = {k: subject[k] for k in ("task_id", "task_evidence_ref", "task_sha256")}
    require(expected_task is None or identity == expected_task,
            "O5_TASK_MISMATCH: runs and judgement need the identical frozen task", Finding)
    task = task_record(doc, row, ctx, scope, identity)
    observed = timestamp(record["observed_at"])
    require(timestamp(task["observed_at"]) < observed <= timestamp(event["at"]) and
            (after is None or observed > after), "O5_CHRONOLOGY: task/run/event order", Finding)
    checked_outcome(row, record, body)
    return record, body


def assess_events(doc, row, skill, comparison, ctx, scope, date_ok):
    shape(comparison, COMPARISON)
    require(comparison["rule_version"] == doc["policy"]["freshness_rule_version"] == 2,
            "O5_RULE: unsupported rule")
    state, previous, reset = "unproven", None, None
    seen, used, run_ids, successes = set(), set(), set(), []
    valid = set()
    last_drop = None
    for event in comparison["events"]:
        shape(event, ref("freshness-event"))
        at = timestamp(event["at"])
        require(event["id"] not in seen and (previous is None or at >= previous),
                "O5_EVENT: duplicate or unordered event", Finding)
        seen.add(event["id"])
        previous = at
        require(event["from_tier"] == state, "O5_EVENT: inconsistent starting tier", Finding)
        action = event["action"]
        refs = evidence_ids(event)
        require(not refs & used, "O5_EVENT: supporting evidence reused", Finding)
        # A shared frozen task is legitimate; supporting outcome/claim IDs are not reused.
        supporting = refs - {event.get("comparison", {}).get("task_evidence_ref")}
        if action == "claim":
            require(state == "unproven" and date_ok and event["evidence_refs"] and
                    set(event["evidence_refs"]) <= set(comparison["claim_evidence_refs"]),
                    "O5_CLAIM: qualifying date and captured claim required", Finding)
            publisher = index(doc, "installations")[skill["candidate"]["installation_id"]]["publisher"]["identity"]
            for eid in event["evidence_refs"]:
                record, body = evidence_body(doc, eid, ctx)
                s = record["subject"]
                require(s["type"] == "skill-claim" and s["scope_sha256"] == scope and
                        s["author_identity"] == publisher and record["kind"] == "publisher-claim" and
                        body.get("output"), "O5_CLAIM: exact author statement required", Finding)
                require(timestamp(s["published_at"]) <= timestamp(record["observed_at"]) <= at and
                        (reset is None or timestamp(record["observed_at"]) > reset),
                        "O5_CHRONOLOGY: stale claim after drop", Finding)
            state = "claimed"
        elif action == "comparison":
            require(state == "claimed" and comparison["proof_route"] == "comparison" and date_ok,
                    "O5_COMPARISON: claimed comparison route required", Finding)
            pair = event["comparison"]
            task = {k: pair[k] for k in ("task_id", "task_evidence_ref", "task_sha256")}
            with_run, with_body = run_record(doc, row, ctx, scope, pair["with_skill_evidence_ref"],
                                            event, "with-skill", task, reset)
            without, without_body = run_record(doc, row, ctx, scope, pair["without_skill_evidence_ref"],
                                              event, "without-skill", task, reset)
            require(with_run["subject"]["run_id"] != without["subject"]["run_id"] and
                    with_run["subject"]["run_id"] not in run_ids and
                    without["subject"]["run_id"] not in run_ids,
                    "O5_RUN_ID_REUSED: comparison needs distinct new runs", Finding)
            require(timestamp(with_run["observed_at"]) < timestamp(without["observed_at"]),
                    "O5_CHRONOLOGY: baseline must follow the with-skill run", Finding)
            record, body = evidence_record(doc, pair["judgement_evidence_ref"], ctx)
            s = record["subject"]
            require(all(s.get(k) == v for k, v in task.items()),
                    "O5_TASK_MISMATCH: judgement task differs", Finding)
            require(s == {"type": "skill-comparison", "scope_sha256": scope, **task,
                "with_skill_evidence_ref": pair["with_skill_evidence_ref"],
                "without_skill_evidence_ref": pair["without_skill_evidence_ref"]},
                "O5_COMPARISON: judgement outcome references differ", Finding)
            require(timestamp(without["observed_at"]) <= timestamp(record["observed_at"]) <= at and
                    body.get("criterion") == row["acceptance"]["criterion"] and
                    body.get("verdict") == pair["verdict"] and body.get("output"),
                    "O5_COMPARISON: judgement criterion, verdict or chronology", Finding)
            if row["output_judge"]["kind"] == "objective-check":
                checked_outcome(row, record, body)
            else:
                owner_judgement(doc, record, body)
            if pair["verdict"] == "supports":
                require(record["result"] == "pass" and with_run["result"] == "pass" and
                        without["result"] != "unknown", "O5_COMPARISON: inconclusive outcome cannot promote", Finding)
                state = "proven"
            run_ids.update((with_run["subject"]["run_id"], without["subject"]["run_id"]))
        elif action == "checked-runs":
            require(state == "claimed" and comparison["proof_route"] == "how-to" and date_ok and
                    row["output_judge"]["kind"] == "objective-check" and event["evidence_refs"],
                    "O5_CHECKED_RUNS: objective how-to route required", Finding)
            for eid in event["evidence_refs"]:
                record, body = run_record(doc, row, ctx, scope, eid, event, "with-skill", after=reset)
                require(record["result"] == "pass", "O5_CHECKED_RUNS: failed result", Finding)
                rid = record["subject"]["run_id"]
                require(rid not in run_ids, "O5_RUN_ID_REUSED: two records are not two runs", Finding)
                run_ids.add(rid)
                successes.append(eid)
            require(type(event["successful_run_count"]) is int and
                    event["successful_run_count"] == len(event["evidence_refs"]),
                    "O5_CHECKED_RUNS: count differs from evidence", Finding)
            if len(successes) >= doc["policy"]["how_to_successes_required"]:
                state = "proven"
        elif action == "drop":
            require(event["evidence_refs"], "O5_DROP: adverse evidence required", Finding)
            for eid in event["evidence_refs"]:
                if row["output_judge"]["kind"] == "objective-check":
                    record, body = run_record(doc, row, ctx, scope, eid, event, "with-skill", after=reset)
                else:
                    record, body = evidence_record(doc, eid, ctx)
                    owner_judgement(doc, record, body)
                    subject = record["subject"]
                    require(subject["type"] == "skill-run" and subject["mode"] == "with-skill" and
                            subject.get("scope_sha256") == scope and
                            body.get("criterion") == row["acceptance"]["criterion"] and body.get("output") and
                            (reset is None or timestamp(record["observed_at"]) > reset) and
                            timestamp(record["observed_at"]) <= at, "O5_DROP: judgement scope/order", Finding)
                    task = task_record(doc, row, ctx, scope, subject)
                    require(timestamp(task["observed_at"]) < timestamp(record["observed_at"]),
                            "O5_CHRONOLOGY: rejected use must follow its task", Finding)
                require(record["result"] == "fail", "O5_DROP: failure or owner rejection required", Finding)
                rid = record["subject"]["run_id"]
                require(rid not in run_ids, "O5_RUN_ID_REUSED: adverse use already recorded", Finding)
                run_ids.add(rid)
            for eid in event["decision_refs"]:
                owner_judgement(doc, *evidence_body(doc, eid, ctx))
            state = TIERS[max(0, TIERS.index(state) - 1)]
            reset, last_drop, successes = at, event, []
        require(event["to_tier"] == state, "O5_EVENT: unsupported resulting tier", Finding)
        used.update(supporting)
        valid.update(refs)
    require(state == comparison["tier"], "O5_EVENT: recorded tier lacks supporting history", Finding)
    require(date_ok or state == "unproven", "O5_DATE: date cannot support recorded tier", Finding)
    records = evidence_closure(doc, valid)
    return {"tier": state, "proof_route": comparison["proof_route"],
        "valid_evidence_ids": [r["id"] for r in records], "checked_successes": len(successes),
        "checked_success_evidence_refs": successes,
        "how_to_successes_required": doc["policy"]["how_to_successes_required"],
        "last_transition": comparison["events"][-1] if comparison["events"] else None,
        "last_drop": last_drop}


def evaluate(doc, row, ctx, model_id, candidate_sources=None):
    require(isinstance(row, dict) and isinstance(row.get("freshness"), dict),
            "missing row freshness premise")
    shape(doc["policy"], ref("policy"))
    require(doc["schema_version"] == 2 and doc["policy"]["freshness_rule_version"] == 2,
            "O5_RULE: explicit upgrade required")
    expanded = operational_definition(doc, row)
    skill_ids = {b["resource_id"] for b in expanded["bindings"]
                 if b["resource_definition"]["type"] == "skill-tree"}
    if row["freshness"]["status"] == "not-applicable":
        require(not skill_ids, "MODEL_UNQUALIFIED: skill-bearing closure cannot omit freshness", Finding)
        return {"status": "not-applicable", "tier": None, "skills": [],
                "qualification_refs": [], "control_hits": control()}
    listed = [s["resource_id"] for s in row["freshness"]["skills"]]
    require(set(listed) == skill_ids and len(listed) == len(skill_ids),
            "MODEL_UNQUALIFIED: incomplete skill freshness coverage", Finding)
    targets = [m for m in doc["policy"]["model_targets"] if m["model_id"] == model_id]
    if not targets and model_id:
        releases = [e for e in doc["evidence"] if e["subject"]["type"] == "model-release"
                    and e["subject"]["model_id"] == model_id]
        if len(releases) == 1:
            targets = [{"model_id": model_id, "release_date": releases[0]["subject"]["release_date"],
                        "evidence_refs": [releases[0]["id"]]}]
    require(model_id and len(targets) == 1, "missing, alias or unknown caller-model identity")
    target = targets[0]
    require(target["evidence_refs"], "model release evidence missing")
    for eid in target["evidence_refs"]:
        evidence_body(doc, eid, ctx, {"type": "model-release", "model_id": model_id,
                                     "release_date": target["release_date"]})
    resources, installs = index(doc, "resources"), index(doc, "installations")
    skills, refs = [], set()
    for skill in row["freshness"]["skills"]:
        candidate = skill["candidate"]
        resource = resources[skill["resource_id"]]
        require(candidate["pin_sha256"] == digest(installs[candidate["installation_id"]]["pin"]) and
                resource["owner"] == {"type": "installation", "id": candidate["installation_id"]} and
                candidate["skill_tree_sha256"] == resource["expected"]["sha256"] and
                candidate["pin_sha256"] == resource["expected"]["pin_sha256"],
                "MODEL_UNQUALIFIED: candidate identity differs", Finding)
        observed_resource = resource
        if candidate_sources and resource["id"] in candidate_sources:
            source = Path(candidate_sources[resource["id"]])
            require(source.is_absolute() and source.resolve(strict=True) == source,
                    "candidate source must be canonical and absolute")
            observed_resource = copy.deepcopy(resource)
            observed_resource["locator"] = {"root": "absolute", "path": str(source)}
        observation(doc, row, observed_resource, ctx)
        reason = None
        if not isinstance(candidate["version_date"], str) or candidate["date_basis"] == "unknown":
            reason = "unknown-date"
        else:
            require(candidate["date_evidence_refs"], "MODEL_UNQUALIFIED: no version-date evidence", Finding)
            for eid in candidate["date_evidence_refs"]:
                evidence_body(doc, eid, ctx, {"type": "version-date", "resource_id": resource["id"],
                    "pin_sha256": candidate["pin_sha256"], "tree_sha256": candidate["skill_tree_sha256"],
                    "version_date": candidate["version_date"]})
            if date(candidate["version_date"]) < date(target["release_date"]):
                reason = "old-date"
        comparisons = [c for c in skill["comparisons"] if c["model_id"] == model_id]
        require(len(comparisons) <= 1, "ambiguous model comparison")
        scope = assurance_scope(doc, row, skill, model_id, target["release_date"])
        if comparisons:
            comparison = comparisons[0]
            require(comparison["model_release_date"] == target["release_date"] and
                    comparison["release_evidence_refs"] == target["evidence_refs"],
                    "MODEL_UNQUALIFIED: model target changed", Finding)
            result = assess_events(doc, row, skill, comparison, ctx, scope, reason is None)
        else:
            result = {"tier": "unproven", "proof_route": "undetermined", "valid_evidence_ids": [],
                      "checked_successes": 0, "checked_success_evidence_refs": [],
                      "how_to_successes_required": doc["policy"]["how_to_successes_required"],
                      "last_transition": None, "last_drop": None}
        reasons = [reason] if reason else []
        if result["tier"] == "unproven":
            reasons.append("poor-use" if result["last_drop"] else "missing-claim")
        result.update(resource_id=resource["id"], scope_sha256=scope,
                      candidate_date=candidate["version_date"], model_release_date=target["release_date"],
                      date_result="pass" if reason is None else "fail", date_reason=reason,
                      unproven_reasons=sorted(reasons))
        refs.update(result["valid_evidence_ids"])
        skills.append(result)
    return {"status": "applicable", "tier": min((s["tier"] for s in skills), key=TIERS.index),
            "skills": skills, "qualification_refs": sorted(refs), "control_hits": control()}


def exception_coverage(doc, row, ctx, assessment, freshness_decision_refs=None, route="use-directly"):
    require(route in DELIVERY_ROUTES, "unsupported delivery route")
    refs = [] if freshness_decision_refs is None else freshness_decision_refs
    require(isinstance(refs, list) and len(refs) == len(set(refs)),
            "O5_EXCEPTION_COVERAGE: unique decision list required", Finding)
    unproven = {s["scope_sha256"]: s for s in assessment["skills"] if s["tier"] == "unproven"}
    covered = set()
    for eid in refs:
        record, body = evidence_body(doc, eid, ctx)
        subject = record["subject"]
        scope = subject.get("scope_sha256")
        require(subject["type"] == "skill-exception" and scope in unproven and scope not in covered,
                "O5_EXCEPTION_COVERAGE: exact resource decision required", Finding)
        require(subject["route"] == route, "O5_EXCEPTION_ROUTE: consent route differs", Finding)
        owner_judgement(doc, record, body)
        require(body.get("suggestion") and body.get("output"), "O5_EXCEPTION_COVERAGE: missing decision capture", Finding)
        reasons = set(unproven[scope]["unproven_reasons"])
        accepted = set(body.get("accepted_uncertainties", []))
        require(reasons & {"old-date", "unknown-date"} <= accepted,
                "O5_EXCEPTION_DATE: date uncertainty not acknowledged", Finding)
        require(reasons <= accepted, "O5_EXCEPTION_COVERAGE: uncertainty not acknowledged", Finding)
        last = unproven[scope]["last_transition"]
        require(last is None or timestamp(record["observed_at"]) >= timestamp(last["at"]),
                "O5_EXCEPTION_COVERAGE: consent predates adverse event", Finding)
        covered.add(scope)
    require(covered == set(unproven), "O5_EXCEPTION_COVERAGE: incomplete resource consent", Finding)
    require(any(r["status"] == "implemented" and r["route"] == DELIVERY_ROUTES[route]
                for r in row["routes"]), "O5_EXCEPTION_ROUTE: requested route is not implemented", Finding)
    return sorted(refs)


def evaluate_targets(doc, row, ctx, candidate_sources=None, decisions=None, route="use-directly"):
    if decisions is not None:
        require(isinstance(decisions, list), "O5_EXCEPTION_COVERAGE: activation decisions need a list")
        for selected in decisions:
            shape(selected, obj({"model_id": S, "freshness_decision_refs": IDS, "route": DELIVERY_ROUTE,
                                 "tier": TIER, "qualification_refs": IDS},
                                ("tier", "qualification_refs")))
        require(len({x["model_id"] for x in decisions}) == len(decisions),
                "O5_EXCEPTION_COVERAGE: duplicate activation models", Finding)
    if row["freshness"]["status"] == "not-applicable":
        evaluate(doc, row, ctx, None, candidate_sources)
        require(not decisions, "O5_EXCEPTION_COVERAGE: no skill needs no decisions", Finding)
        return []
    require(doc["policy"]["model_targets"], "no model targets for skill activation", Finding)
    result = []
    for target in doc["policy"]["model_targets"]:
        assessment = evaluate(doc, row, ctx, target["model_id"], candidate_sources)
        selected = next((x for x in (decisions or []) if x["model_id"] == target["model_id"]), {})
        selected_route = selected.get("route", route)
        refs = exception_coverage(doc, row, ctx, assessment, selected.get("freshness_decision_refs", []), selected_route)
        result.append({"model_id": target["model_id"], "tier": assessment["tier"],
                       "qualification_refs": assessment["qualification_refs"],
                       "freshness_decision_refs": refs, "route": selected_route})
    require(not decisions or {x["model_id"] for x in decisions} == {x["model_id"] for x in result},
            "O5_EXCEPTION_COVERAGE: unexpected activation model", Finding)
    return result


def revalidate_active(doc, ctx):
    for row in doc["rows"]:
        if row["lifecycle"]["state"] == "active":
            prior = row["lifecycle"]["activation"]["freshness_evaluation"]
            require(evaluate_targets(doc, row, ctx, decisions=prior) == prior,
                    "active freshness evaluation differs from current targets", Finding)


def main():
    from adopt_data import ProbeParser
    parser = ProbeParser(description=__doc__)
    for key in ("vault", "home", "row", "caller-model-id"):
        parser.add_argument("--" + key, required=True)
    args = parser.parse_args()
    try:
        ctx = Context(args.vault, args.home)
        doc, _ = load_current(ctx)
        row = index(doc, "rows").get(args.row)
        require(row is not None, "unknown row")
        require(row["lifecycle"]["state"] != "legacy-recorded", "legacy freshness unresolved", Finding)
        assessment = evaluate(doc, row, ctx, args.caller_model_id)
        print(encoded(assessment).decode(), end="")
        return 0
    except (Problem, OSError, ValueError, TypeError, KeyError, IndexError, RuntimeError) as exc:
        return cli_error(exc)


if __name__ == "__main__":
    sys.exit(main())
