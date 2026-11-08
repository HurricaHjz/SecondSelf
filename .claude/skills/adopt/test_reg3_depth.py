#!/usr/bin/env python3
"""Native regression fixtures for evidence binding, carrier closure and candidates.

The selected build supplies its own fixture constructors and APIs. The same facts
are exercised on the reviewed build and the replacement; no missing-command
failure is treated as a reproduced defect.
"""
import argparse
import copy
import importlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import traceback


def observed(case, value):
    print("OBSERVED " + json.dumps({"case": case, **value}, sort_keys=True), flush=True)


def structural(t, doc, row):
    return getattr(t.D, "operational_definition", t.D.expansion)(doc, row)


def test_evidence_invalidation(t):
    ctx = t.skill_fixture("reg3-evidence")
    t.activate(ctx, ["skill"])
    valid, _ = t.D.load_current(ctx)
    t.W.commit(ctx, t.W.proposal(ctx, "edit", {}))
    current, _ = t.D.load_current(ctx)
    t.check(current["rows"][0]["lifecycle"]["state"] == "active",
            "REG3 F1 unchanged valid qualification retains activation")
    unused = copy.deepcopy(current)
    next(e for e in unused["evidence"] if e["id"] == "model-b-release")["result"] = "fail"
    t.save_doc(ctx, unused)
    current, _ = t.D.load_current(ctx)
    t.check(current["rows"][0]["lifecycle"]["state"] == "active",
            "REG3 F1 unrelated evidence is outside the activation digest")
    before = t.W.tuple_bytes(ctx)
    bad = copy.deepcopy(current)
    next(e for e in bad["evidence"] if e["id"] == "primary-task")["result"] = "fail"
    changed = t.D.digest(t.D.expansion(bad, bad["rows"][0])) != \
              t.D.digest(t.D.expansion(current, current["rows"][0]))
    accepted, refusal = False, None
    try:
        t.save_doc(ctx, bad)
        accepted = True
    except t.D.Problem as exc:
        refusal = str(exc)
    state = t.D.load_current(ctx)[0]["rows"][0]["lifecycle"]["state"]
    observed("REG3-F1", {"evidence_bound_digest_changed": changed, "edit_accepted": accepted,
                         "state": state, "refusal": refusal})
    t.check(not accepted and t.W.tuple_bytes(ctx) == before,
            "REG3 F1 revoked task evidence cannot be committed with active state")
    t.check(changed, "REG3 F1 activation digest binds the full referenced evidence record")
    for eid in ("primary-date", "model-a-release"):
        changed_record = copy.deepcopy(current)
        next(e for e in changed_record["evidence"] if e["id"] == eid)["result"] = "unknown"
        t.check(t.D.digest(t.D.expansion(changed_record, changed_record["rows"][0])) !=
                t.D.digest(t.D.expansion(current, current["rows"][0])),
                "REG3 F1 referenced date/release evidence is bound: " + eid)
    bad["rows"][0]["lifecycle"] = {"state": "prepared", "changed_at": t.D.now(),
                                  "reason": "qualification revoked", "decision_refs": []}
    result = t.save_doc(ctx, bad)
    t.check(result["rows"][0]["lifecycle"]["state"] == "prepared",
            "REG3 F1 explicit deactivation permits recording the failed evidence")


def test_final_freshness_gate(t):
    ctx = t.skill_fixture("reg3-final-freshness")
    t.activate(ctx, ["skill"])
    doc, _ = t.D.load_current(ctx)
    artefact = ctx.locate(next(e for e in doc["evidence"] if e["id"] == "primary-task")["artefact"]["locator"])
    original = artefact.read_bytes()
    before = t.W.tuple_bytes(ctx)
    def revoke(phase):
        if phase == "before-data":
            body = t.D.decode(original)
            body["result"] = "fail"
            t.write(artefact, t.D.encoded(body))
    accepted, refusal = False, None
    try:
        t.W.commit(ctx, t.W.proposal(ctx, "edit", {}), hook=revoke)
        accepted = True
    except t.D.Problem as exc:
        refusal = str(exc)
    observed("REG3-F1-final", {"commit_accepted": accepted, "data_changed": t.W.tuple_bytes(ctx) != before,
                               "refusal": refusal})
    t.check(not accepted and t.W.tuple_bytes(ctx) == before,
            "REG3 F1 final publication re-evaluates task freshness after initial proof")
    t.write(artefact, original)
    if ctx.pending.exists():
        t.W.recover(ctx)
    t.check(t.V.resolve(ctx, "skill", "model-a-release")["state"] == "active",
            "REG3 F1 restored artefact control retains the unchanged committed activation")


def test_recovery_freshness(t):
    ctx = t.skill_fixture("reg3-recovery-freshness")
    t.activate(ctx, ["skill"])
    doc, _ = t.D.load_current(ctx)
    artefact = ctx.locate(next(e for e in doc["evidence"] if e["id"] == "primary-task")["artefact"]["locator"])
    original = artefact.read_bytes()
    def crash(phase):
        if phase == "after-data":
            raise RuntimeError("fixture termination after data publication")
    try:
        t.W.commit(ctx, t.W.proposal(ctx, "edit", {}), hook=crash)
    except RuntimeError:
        pass
    t.check(ctx.pending.is_file(), "REG3 F1 recovery starts from a durable pending tuple")
    broken = t.D.decode(original)
    broken["result"] = "fail"
    t.write(artefact, t.D.encoded(broken))
    before = t.W.tuple_bytes(ctx)
    recovered, refusal = False, None
    try:
        t.W.recover(ctx)
        recovered = True
    except t.D.Problem as exc:
        refusal = str(exc)
    observed("REG3-F1-recovery", {"recovery_accepted": recovered,
                                  "pending_retained": ctx.pending.is_file(), "refusal": refusal})
    t.check(not recovered and ctx.pending.is_file() and t.W.tuple_bytes(ctx) == before,
            "REG3 F1 recovery cannot publish an active state with revoked qualification")
    t.write(artefact, original)
    t.check(t.W.recover(ctx) == "new" and
            t.V.resolve(ctx, "skill", "model-a-release")["state"] == "active",
            "REG3 F1 valid qualification permits recovery of the exact committed tuple")


def test_named_carrier(t):
    ctx = t.skill_fixture("reg3-named-carrier")
    doc, _ = t.D.load_current(ctx)
    row = doc["rows"][0]
    named = t.D.index(doc, "resources")["primary-carrier"]
    spare = copy.deepcopy(named)
    spare["id"] = "spare-carrier"
    path = ctx.home / ".claude/skills/spare"
    path.symlink_to(ctx.home / "trees/primary")
    spare["locator"] = {"root": "absolute", "path": str(path)}
    doc["resources"].append(spare)
    row["resource_bindings"] = [b for b in row["resource_bindings"] if b["resource_id"] != named["id"]]
    row["resource_bindings"].append({"role": "carrier", "resource_id": spare["id"]})
    install = doc["installations"][0]
    install["resource_ids"] = [rid for rid in install["resource_ids"] if rid != named["id"]] + [spare["id"]]
    if t.W.seed_document()["schema_version"] == 2:
        t.bind_tasks(doc, ctx)
        t.bind_evidence(doc, ctx)
    else:
        t.bind_evidence(doc, ctx)
        t.bind_tasks(doc, ctx)
    t.save_doc(ctx, doc)
    doc, _ = t.D.load_current(ctx)
    closure = [b["resource_id"] for b in t.D.expansion(doc, doc["rows"][0])["bindings"]]
    t.check(bool(t.R.prove(doc, doc["rows"][0], ctx)), "REG3 F2 all present carrier control")
    named_path = ctx.locate(named["locator"])
    named_path.unlink()
    before = t.W.tuple_bytes(ctx)
    accepted, refusal = False, None
    try:
        t.activate(ctx, ["skill"])
        accepted = True
    except t.D.Problem as exc:
        refusal = str(exc)
    observed("REG3-F2", {"expanded_resources": closure, "named_carrier_present": named_path.is_symlink(),
                         "spare_carrier_present": path.is_symlink(), "activation_accepted": accepted,
                         "refusal": refusal})
    t.check(not accepted and t.W.tuple_bytes(ctx) == before,
            "REG3 F2 missing named carrier refuses despite an alternative carrier")
    t.check(named["id"] in closure, "REG3 F2 exact named carrier belongs to the derived closure")
    named_path.symlink_to(ctx.home / "trees/primary")
    active = t.activate(ctx, ["skill"])
    proved = {c["resource_id"] for c in active["rows"][0]["lifecycle"]["activation"]["checks"]}
    t.check({named["id"], spare["id"]} <= proved,
            "REG3 F2 reciprocal named pair and additional carrier are each observed")
    cyclic = copy.deepcopy(active)
    definition = t.resource("definition", "file", ctx.home / "definition",
        {"sha256": "0" * 64, "use": "cycle fixture"}, ["file-content", "input-use"], install["id"])
    cyclic["resources"].append(definition)
    for rid, dependency in (("class-a", "class-b"), ("class-b", "class-a")):
        cyclic["resources"].append(t.resource(rid, "class-binding", ctx.home / rid,
            {"class_id": rid, "definition_resource_id": "definition", "required_resource_ids": [dependency]},
            ["class-launch"], install["id"]))
    cyclic["rows"][0]["resource_bindings"].append({"role": "class-binding", "resource_id": "class-a"})
    t.refuses(lambda: structural(t, cyclic, cyclic["rows"][0]),
              "REG3 F2 non-reciprocal dependency cycles still refuse")


def single_skill(t, name):
    ctx = (t.skill_fixture(name, labels=("primary",)) if t.W.seed_document()["schema_version"] == 2
           else t.skill_fixture(name))
    doc, _ = t.D.load_current(ctx)
    removed = {"dependency", "dependency-carrier"}
    doc["resources"] = [r for r in doc["resources"] if r["id"] not in removed]
    doc["installations"][0]["resource_ids"] = [r for r in doc["installations"][0]["resource_ids"] if r not in removed]
    row = doc["rows"][0]
    row["resource_bindings"] = [b for b in row["resource_bindings"] if b["resource_id"] not in removed]
    row["freshness"]["skills"] = [s for s in row["freshness"]["skills"] if s["resource_id"] not in removed]
    doc["evidence"] = [e for e in doc["evidence"] if e["subject"].get("resource_id") not in removed]
    if t.W.seed_document()["schema_version"] == 2:
        t.bind_tasks(doc, ctx)
        t.bind_evidence(doc, ctx)
    else:
        t.bind_evidence(doc, ctx)
        t.bind_tasks(doc, ctx)
    t.save_doc(ctx, doc)
    t.activate(ctx, ["skill"])
    return ctx


def candidate_plan(t, ctx):
    """Build a prospective fixture plan without ever replacing installed A.

    Task evidence is a staged-content fixture. Physical acceptance envelopes are
    explicit expected-output stand-ins: unchanged directory identity plus B's
    reviewed inventory. Their hashes must match the actual installation at finish.
    """
    old, raw = t.D.load_current(ctx)
    target = copy.deepcopy(old)
    row = target["rows"][0]
    row["lifecycle"] = {"state": "prepared", "changed_at": t.D.now(),
                        "reason": "reviewed candidate B", "decision_refs": []}
    root = ctx.home / "trees/primary"
    stage = ctx.home / "candidate-b"
    shutil.copytree(root, stage)
    t.write(stage / "reference.txt", "Candidate B answers the revised frozen task.\n")
    tree_hash = t.S.tree_hash(stage)
    install = target["installations"][0]
    install["pin"].update(version="1.0.1", sha256=t.D.sha(b"candidate B package"))
    primary = t.D.index(target, "resources")["primary"]
    primary["expected"].update(sha256=tree_hash, pin_sha256=t.D.digest(install["pin"]))
    skill = row["freshness"]["skills"][0]
    skill["candidate"].update(pin_sha256=t.D.digest(install["pin"]), skill_tree_sha256=tree_hash,
                              version_label="1.0.1", date_evidence_refs=["candidate-b-date"])
    skill["applicability_evidence"] = ["candidate-b-task"]
    skill["comparisons"][0]["applicability_evidence_refs"] = ["candidate-b-task"]
    row["acceptance"]["evidence_refs"] = [
        "candidate-b-" + b["resource_id"] + "-" + c
        for b in structural(t, target, row)["bindings"]
        for c in b["resource_definition"]["check_ids"] if c not in t.D.PURE_CHECKS]
    t.add_evidence(target, ctx, "candidate-b-date", {"type": "version-date", "resource_id": "primary",
        "pin_sha256": skill["candidate"]["pin_sha256"], "tree_sha256": tree_hash,
        "version_date": skill["candidate"]["version_date"]}, kind="captured-source")
    if t.W.seed_document()["schema_version"] == 2:
        t.bind_tasks(target, ctx)
    old_row = old["rows"][0]
    future_observations = {}
    for i, binding in enumerate(structural(t, target, row)["bindings"]):
        r = binding["resource_definition"]
        previous = t.R.observation(old, old_row, t.D.index(old, "resources")[r["id"]], ctx)
        future = copy.deepcopy(previous)
        if r["type"] == "skill-tree":
            future["sha256"] = tree_hash
        elif r["type"] == "carrier":
            entries, _ = t.S.inventory(ctx.locate(r["locator"]), [ctx.home / "trees"])
            staged, _ = t.S.inventory(stage)
            projected = {".": entries["."]}
            projected.update({"./@target" + k[1:]: v for k, v in staged.items()})
            future["sha256"] = t.D.digest({k: {f: v for f, v in entry.items()
                if f not in ("logical", "resolved")} for k, entry in projected.items()})
        future_observations[r["id"]] = future
        for check in r["check_ids"]:
            if check not in t.D.PURE_CHECKS:
                eid = "candidate-b-" + r["id"] + "-" + check
                t.add_evidence(target, ctx, eid, t.R.row_subject(target, row, binding, i, check),
                    {"observation_sha256": t.D.digest(future), "positive_control": True,
                     "negative_control": True, "criterion": row["acceptance"]["criterion"], "output": "passed"})
                t.D.index(target, "evidence")[eid]["limitations"] = [
                    "Expected target observation fixture; no installed executable/model was run."]
    if t.W.seed_document()["schema_version"] == 1:
        i, binding = next((i, b) for i, b in enumerate(structural(t, target, row)["bindings"])
                          if b["resource_id"] == "primary")
        subject = {**t.R.row_subject(target, row, binding, i, "skill-invocation"),
            "type": "task-check", "model_id": "model-a-release",
            "fixture_sha256": t.D.sha(b"revised positive and without-skill task"),
            "criterion_id": row["acceptance"]["criterion"]}
        future = future_observations["primary"]
        qualification = t.F.qualification_observation(primary, future) if hasattr(t.F, "qualification_observation") else future
        t.add_evidence(target, ctx, "candidate-b-task", subject,
            {"observation_sha256": t.D.digest(qualification), "positive_control": True,
             "negative_control": True, "criterion": row["acceptance"]["criterion"]})
    before = t.S.snapshot(ctx.home, [ctx.home / "trees"])
    expected = copy.deepcopy(before)
    destination = root / "reference.txt"
    replacement = stage / "reference.txt"
    for entry in expected["state"].values():
        if entry.get("resolved") == str(destination) and entry.get("type") == "file":
            entry.update(sha256=t.D.sha(replacement.read_bytes()), size=replacement.stat().st_size,
                         mode=stat.S_IMODE(replacement.stat().st_mode))
    expected["state_sha256"] = t.D.digest(expected["state"])
    expected["started_at"] = expected["ended_at"] = t.D.now()
    plan = {"id": "maintenance-candidate-b", "expect_data": t.D.sha(raw),
        "scope": [str(destination)], "before": before, "declaration": t.S.changes(before, expected),
        "steps": [{"kind": "replace-file", "path": str(destination),
                   "old_sha256": t.D.sha(destination.read_bytes()), "artefact": str(replacement),
                   "new_sha256": t.D.sha(replacement.read_bytes()),
                   "old_mode": stat.S_IMODE(destination.stat().st_mode),
                   "mode": stat.S_IMODE(replacement.stat().st_mode)}],
        "changes": {k: target[k] for k in ("rows", "resources", "installations", "evidence")},
        "allowed_roots": [str(ctx.home / "trees")],
        "candidate_sources": [{"resource_id": "primary", "path": str(stage), "tree_sha256": tree_hash}]}
    return old, target, plan, stage


def test_changed_candidate(t):
    ctx = single_skill(t, "reg3-candidate-success")
    old, target, plan, stage = candidate_plan(t, ctx)
    installed = ctx.home / "trees/primary"
    old_hash = t.S.tree_hash(installed)
    t.check(old_hash != t.S.tree_hash(stage), "REG3 F6 B has genuinely different skill bytes")
    t.check(t.V.resolve(ctx, "skill", "model-a-release")["state"] == "active",
            "REG3 F6 preparing candidate evidence does not overwrite A's artefacts")
    error = None
    try:
        t.M.assess_candidate(ctx, old, plan)
    except t.D.Problem as exc:
        error = str(exc)
    observed("REG3-F6", {"assessment_error": error, "installed_A_unchanged": t.S.tree_hash(installed) == old_hash,
                         "different_candidate": old_hash != t.S.tree_hash(stage)})
    t.check(error is None and t.S.tree_hash(installed) == old_hash,
            "REG3 F6 qualifying staged B is assessed while installed A remains unchanged")
    result = t.M.run(ctx, plan, t.D.digest(plan))
    current, _ = t.D.load_current(ctx)
    t.check(result["outcome"] == "target" and current["rows"][0]["lifecycle"]["state"] == "prepared"
            and not current["maintenance"], "REG3 F6 changed-tree installation releases prepared")
    t.check(t.S.tree_hash(installed) == t.S.tree_hash(stage),
            "REG3 F6 installed target bytes equal the reviewed candidate")
    t.check(bool(t.F.evaluate(current, current["rows"][0], ctx, "model-a-release")),
            "REG3 F6 final qualification observes the installed destination")
    active = t.activate(ctx, ["skill"])
    t.check(active["rows"][0]["lifecycle"]["state"] == "active",
            "REG3 F6 fresh activation proves installed B and its exact carrier")


def test_candidate_controls(t):
    for variant in ("failed-evidence", "changed-source", "changed-target",
                    "final-freshness", "late-plan-change"):
        ctx = single_skill(t, "reg3-candidate-" + variant)
        old, target, plan, stage = candidate_plan(t, ctx)
        installed = ctx.home / "trees/primary"
        old_hash = t.S.tree_hash(installed)
        if variant == "failed-evidence":
            next(e for e in plan["changes"]["evidence"] if e["id"] == "candidate-b-task")["result"] = "fail"
        elif variant == "changed-source":
            t.write(stage / "reference.txt", "Unreviewed candidate bytes")
        def corrupt(phase, coordinator):
            if phase == "verifying":
                if variant == "changed-target":
                    t.write(installed / "reference.txt", "Unreviewed installed target")
                elif variant == "final-freshness":
                    record = next(e for e in plan["changes"]["evidence"] if e["id"] == "candidate-b-task")
                    path = ctx.locate(record["artefact"]["locator"])
                    body = t.D.read_json(path)
                    body["result"] = "fail"
                    t.write(path, t.D.encoded(body))
                elif variant == "late-plan-change":
                    plan["changes"]["rows"][0]["name"] = "Unreviewed late change"
        before = t.W.tuple_bytes(ctx)
        t.refuses(lambda: t.M.run(ctx, plan, t.D.digest(plan),
                  hook=corrupt if variant in ("changed-target", "final-freshness", "late-plan-change") else None),
                  "REG3 F6 candidate control " + variant)
        current, _ = t.D.load_current(ctx)
        if variant in ("changed-target", "final-freshness", "late-plan-change"):
            t.check(current["maintenance"] and current["rows"][0]["lifecycle"]["state"] == "prepared",
                    "REG3 F6 altered installed target remains held and cannot activate")
            if variant != "changed-target":
                t.check(t.S.tree_hash(installed) == t.S.tree_hash(stage),
                        "REG3 F6 release guard is tested with exact installed target bytes")
        else:
            t.check(t.W.tuple_bytes(ctx) == before and t.S.tree_hash(installed) == old_hash and
                    not current["maintenance"], "REG3 F6 failed candidate leaves A unchanged before reservation")


def run(root, harness=None):
    t = harness or importlib.import_module("test_register")
    previous, before = t.ROOT, t.COUNT
    t.ROOT = Path(root)
    cases = []
    try:
        for name, function in (("REG3-F1", test_evidence_invalidation),
                               ("REG3-F1-final", test_final_freshness_gate),
                               ("REG3-F1-recovery", test_recovery_freshness),
                               ("REG3-F2", test_named_carrier), ("REG3-F6", test_changed_candidate),
                               ("REG3-F6-controls", test_candidate_controls)):
            count = t.COUNT
            try:
                function(t)
                result = {"case": name, "result": "PASS", "assertions": t.COUNT - count}
            except Exception as exc:
                traceback.print_exc(file=sys.stdout)
                result = {"case": name, "result": "FAIL", "assertions": t.COUNT - count, "error": str(exc)}
            cases.append(result)
            print("REGRESSION " + json.dumps(result, sort_keys=True), flush=True)
        return {"cases": cases, "failed": sum(c["result"] == "FAIL" for c in cases),
                "assertions": t.COUNT - before}
    finally:
        t.ROOT = previous


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path)
    args = parser.parse_args()
    if not os.environ.get("TMPDIR"):
        print("PROBE FAILED: explicit TMPDIR is required")
        return 2
    if args.build:
        sys.path.insert(0, str(args.build.resolve()))
    root = Path(subprocess.check_output(["/usr/bin/mktemp", "-d", os.path.join(os.environ["TMPDIR"], "adopt.XXXXXXXX")], text=True).strip())
    try:
        result = run(root)
        print("COUNTS " + json.dumps(result, sort_keys=True))
        total = len(result["cases"])
        print(f"FAIL {result['failed']}/{total}" if result["failed"] else f"PASS {total}/{total}")
        return 1 if result["failed"] else 0
    finally:
        shutil.rmtree(root)


if __name__ == "__main__":
    sys.exit(main())
