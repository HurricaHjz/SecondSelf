#!/usr/bin/env python3
"""Fixture regressions for complete installation identity in active rows."""
import argparse
import copy
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback


def fixture(t, route):
    ctx = t.fixture("reg5-" + route)
    doc, _ = t.D.load_current(ctx)
    root = ctx.home / "workspace"
    root.mkdir()
    workspace = t.resource("working-directory", "workspace-directory", root,
        {"required_kind": "directory", "required_access": ["read", "search"],
         "scope": "Fixture working directory"}, ["workspace-access"], "delivery-install")
    if route in ("empty-direct", "row-owned-member"):
        workspace["owner"] = {"type": "row", "id": "delivery"}
    installation = t.installation("delivery", [] if route == "empty-direct" else [workspace])
    row = t.normal_row("delivery", [workspace], "vault-skill")
    if route == "row-owned-member":
        row["resource_bindings"] = []
    elif route in ("binding-only", "run-needs"):
        row["installation_ids"] = []
        if route == "run-needs":
            row["run_needs"] = row["resource_bindings"]
            row["resource_bindings"] = []
    doc["jobs"] = [{"id": "delivery-job", "label": "Fixture work",
                    "definition": "Observe the fixture working directory", "notes": []}]
    doc["installations"] = [installation, t.installation("unrelated", [])]
    doc["resources"] = [workspace]
    doc["rows"] = [row]
    t.save_doc(ctx, doc)
    t.activate(ctx, [row["id"]])
    return ctx


def test_pin_edit(t, route):
    ctx = fixture(t, route)
    doc, _ = t.D.load_current(ctx)
    row = doc["rows"][0]
    original_activation = copy.deepcopy(row["lifecycle"]["activation"])
    digest = t.D.digest(t.D.expansion(doc, row))
    t.check(row["lifecycle"]["state"] == "active" and bool(t.R.recheck(doc, row, ctx)) and
            t.D.validate(doc) == doc,
            "N3 " + route + " unchanged-definition activation and physical control")
    reordered = copy.deepcopy(doc)
    reordered["installations"].reverse()
    t.check(t.D.digest(t.D.expansion(reordered, reordered["rows"][0])) == digest,
            "N3 " + route + " installation collection order does not alter identity")

    # This installation is present in the register but outside this row's closure.
    t.D.index(doc, "installations")["unrelated-install"]["pin"]["version"] = "2.0.0"
    t.save_doc(ctx, doc)
    current, _ = t.D.load_current(ctx)
    current_row = current["rows"][0]
    t.check(current_row["lifecycle"]["activation"] == original_activation and
            t.D.digest(t.D.expansion(current, current_row)) == digest and
            bool(t.R.recheck(current, current_row, ctx)),
            "N3 " + route + " unrelated installation edit keeps activation valid")

    bad = copy.deepcopy(current)
    t.D.index(bad, "installations")["delivery-install"]["pin"]["version"] = "2.0.0"
    changed = t.D.digest(t.D.expansion(bad, bad["rows"][0])) != digest
    before = t.W.tuple_bytes(ctx)
    error = None
    try:
        t.save_doc(ctx, bad)
    except t.D.Problem as exc:
        error = exc
    after, _ = t.D.load_current(ctx)
    after_row = after["rows"][0]
    physical = bool(t.R.recheck(after, after_row, ctx))
    observed = {"case": "N3-" + route, "commit_accepted": error is None,
                "digest_changed": changed, "state": after_row["lifecycle"]["state"],
                "pin": t.D.index(after, "installations")["delivery-install"]["pin"]["version"],
                "activation_unchanged": after_row["lifecycle"]["activation"] == original_activation,
                "physical_recheck_passed": physical, "tuple_unchanged": t.W.tuple_bytes(ctx) == before,
                "code": None if error is None else error.code,
                "error": None if error is None else str(error)}
    print("OBSERVED " + json.dumps(observed, sort_keys=True), flush=True)
    t.check(error is not None and error.code == 1 and
            "ordinary edit cannot create/preserve stale activation" in str(error),
            "N3 " + route + " writer refuses retained activation after referenced pin edit")
    t.check(changed and t.W.tuple_bytes(ctx) == before and not ctx.pending.exists(),
            "N3 " + route + " pin changes identity and refusal preserves published tuple")

    manifest = t.filesystem_manifest(ctx.vault.parent)
    bad_bytes = t.D.encoded(bad)
    t.refuses(lambda: t.D.validate(bad), "N3 " + route + " validator rejects stale activation",
              codes=(2,))
    t.check(t.D.encoded(bad) == bad_bytes and t.filesystem_manifest(ctx.vault.parent) == manifest,
            "N3 " + route + " failed validation changes neither input nor files")

    # Explicit deactivation permits the reviewed definition change, then fresh proof.
    bad["rows"][0]["lifecycle"] = {
        "state": "prepared", "changed_at": t.D.now(),
        "reason": "Reviewed fixture pin change", "decision_refs": []}
    t.save_doc(ctx, bad)
    prepared, _ = t.D.load_current(ctx)
    t.check(prepared["rows"][0]["lifecycle"]["state"] == "prepared" and
            "activation" not in prepared["rows"][0]["lifecycle"] and
            t.D.index(prepared, "installations")["delivery-install"]["pin"]["version"] == "2.0.0",
            "N3 " + route + " explicit deactivation permits the resolved pin edit")
    t.activate(ctx, [row["id"]])
    final, _ = t.D.load_current(ctx)
    activation = final["rows"][0]["lifecycle"]["activation"]
    t.check(activation["id"] != original_activation["id"] and
            activation["definition_sha256"] == t.D.digest(t.D.expansion(final, final["rows"][0])) and
            activation["definition_sha256"] != original_activation["definition_sha256"] and
            bool(t.R.recheck(final, final["rows"][0], ctx)),
            "N3 " + route + " fresh activation binds the changed installation")


def test_definition_closure(t):
    ctx = fixture(t, "complete-closure")
    doc, _ = t.D.load_current(ctx)
    row = doc["rows"][0]
    empty = t.installation("empty", [])
    doc["installations"].append(empty)
    # One direct installation has no member; another is also reached by ownership.
    row["installation_ids"].append(empty["id"])
    row["lifecycle"] = {"state": "prepared", "changed_at": t.D.now(),
                        "reason": "Fixture closure", "decision_refs": []}
    t.save_doc(ctx, doc)
    t.activate(ctx, [row["id"]])
    doc, _ = t.D.load_current(ctx)
    row = doc["rows"][0]
    old = t.D.digest(t.D.expansion(doc, row))
    changes = {}
    for identifier in ("delivery-install", "empty-install", "unrelated-install"):
        changed = copy.deepcopy(doc)
        t.D.index(changed, "installations")[identifier]["pin"]["version"] = "2.0.0"
        changes[identifier] = t.D.digest(t.D.expansion(changed, changed["rows"][0])) != old
    print("OBSERVED " + json.dumps({"case": "N3-complete-closure", "pin_changes": changes},
                                   sort_keys=True), flush=True)
    t.check(changes == {"delivery-install": True, "empty-install": True, "unrelated-install": False},
            "N3 complete direct/owned installation union; unrelated definition excluded")
    definition = t.D.operational_definition(doc, row)
    t.check(definition["installations"] == [t.D.index(doc, "installations")[key]
                                           for key in ("delivery-install", "empty-install")],
            "N3 installation definitions sorted, unique and complete")
    t.check(t.D.proof_tuples(doc, row) == {
        (row["id"], "/bindings/0/resource_definition", "working-directory", "workspace-access")},
        "N3 installation inclusion leaves resource proof pointers unchanged")


def run(root, harness=None):
    t = harness or importlib.import_module("test_register")
    previous_root, before = t.ROOT, t.COUNT
    t.ROOT = Path(root)
    cases = []
    tests = [("N3-" + route, lambda route=route: test_pin_edit(t, route))
             for route in ("empty-direct", "row-owned-member", "installation-owned",
                           "binding-only", "run-needs")]
    tests.append(("N3-complete-closure", lambda: test_definition_closure(t)))
    try:
        for name, test in tests:
            count = t.COUNT
            print("SUBCASE " + name, flush=True)
            try:
                test()
                case = {"case": name, "result": "PASS", "assertions": t.COUNT - count}
            except Exception as exc:
                traceback.print_exc(file=sys.stdout)
                case = {"case": name, "result": "FAIL", "assertions": t.COUNT - count, "error": str(exc)}
            cases.append(case)
            print("REGRESSION " + json.dumps(case, sort_keys=True), flush=True)
        return {"assertions": t.COUNT - before, "failed": sum(c["result"] == "FAIL" for c in cases),
                "cases": cases}
    finally:
        t.ROOT = previous_root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path)
    args = parser.parse_args()
    if not os.environ.get("TMPDIR"):
        print("PROBE FAILED: explicit TMPDIR is required")
        return 2
    if args.build:
        sys.path.insert(0, str(args.build.resolve(strict=True)))
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
