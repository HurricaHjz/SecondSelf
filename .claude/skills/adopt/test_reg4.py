#!/usr/bin/env python3
"""Fixture regressions for derived installation pins and symlink inventories."""
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


def observed(case, **values):
    print("OBSERVED " + json.dumps({"case": case, **values}, sort_keys=True), flush=True)


def pin_fixture(t, name, route):
    ctx = t.fixture(name)
    doc, _ = t.D.load_current(ctx)
    row = t.add_cli(doc, ctx, "tool")
    installation = doc["installations"][0]
    binary = doc["resources"][0]
    if route == "direct":
        row["resource_bindings"] = []
    elif route == "binding":
        row["installation_ids"] = []
    elif route == "run-needs":
        row["installation_ids"] = []
        row["run_needs"] = row["resource_bindings"]
        row["resource_bindings"] = []
    elif route == "dependency":
        row["installation_ids"] = []
        path = ctx.home / "session.json"
        t.write(path, t.D.encoded({"mcpServers": {"fixture": {
            "command": binary["locator"]["path"], "args": [], "env": {}}}}))
        server = t.resource("server", "server-config", path,
            {"format": "json", "server_id": "fixture", "scope": "local",
             "executable_resource_id": binary["id"], "arguments": [],
             "environment": [], "surface": "session"}, ["server-handshake"], installation["id"])
        server["owner"] = {"type": "row", "id": row["id"]}
        doc["resources"].append(server)
        row["resource_bindings"] = [{"role": server["role"], "resource_id": server["id"]}]
    elif route == "empty-direct":
        installation = t.installation("empty", [])
        doc["installations"].append(installation)
        row["installation_ids"].append(installation["id"])
    else:
        raise ValueError("unknown pin fixture route")
    return ctx, doc, row, installation


def unresolved_pin(t, doc, installation):
    installation["pin"] = {"type": "unresolved", "reason": "Planted unresolved installation"}
    for resource in doc["resources"]:
        if resource["owner"] == {"type": "installation", "id": installation["id"]}:
            if "pin_sha256" in resource["expected"]:
                resource["expected"]["pin_sha256"] = t.D.digest(installation["pin"])


def test_pin_validation(t, route, state):
    case = "N1-" + route + "-" + state
    ctx, doc, row, installation = pin_fixture(t, case, route)
    target_id = installation["id"]
    t.bind_evidence(doc, ctx)
    t.save_doc(ctx, doc)
    if state == "active":
        t.activate(ctx, [row["id"]])
    doc, _ = t.D.load_current(ctx)
    row = doc["rows"][0]
    t.check(t.D.validate(doc) == doc and bool(t.R.recheck(doc, row, ctx)),
            case + " resolved-pin publication and physical proof control")
    binding_ids = {b["installation_definition"]["id"] for b in t.D.expansion(doc, row)["bindings"]
                   if "installation_definition" in b}
    t.check(target_id in (set(row["installation_ids"]) | binding_ids) and
            (route not in ("binding", "run-needs", "dependency") or not row["installation_ids"]),
            case + " installation reached through the intended closure")
    bad = copy.deepcopy(doc)
    bad_row = bad["rows"][0]
    unresolved_pin(t, bad, t.D.index(bad, "installations")[target_id])
    t.bind_evidence(bad, ctx)
    if state == "active":
        bad_row["lifecycle"]["activation"] = t.R.activate_record(bad, bad_row, ctx)
    manifest = t.filesystem_manifest(ctx.vault.parent)
    original = t.D.encoded(bad)
    error = None
    try:
        t.D.validate(bad)
    except t.D.Problem as exc:
        error = exc
    observed(case, accepted=error is None, state=state, indirect=not bool(row["installation_ids"]),
             code=None if error is None else error.code,
             error=None if error is None else str(error))
    t.check(t.D.encoded(bad) == original and t.filesystem_manifest(ctx.vault.parent) == manifest,
            case + " validation changes neither input nor files")
    t.check(error is not None and error.code == 2 and
            "prepared/active installation pin unresolved" in str(error),
            case + " unresolved pin refused by the pin gate")
    bad_row["lifecycle"] = {k: v for k, v in bad_row["lifecycle"].items() if k != "activation"}
    bad_row["lifecycle"]["state"] = "planned"
    t.check(t.D.validate(bad) == bad, case + " unresolved planned record remains legal")


def test_pin_publication(t, route):
    case = "N1-publication-" + route
    ctx, doc, row, installation = pin_fixture(t, case, route)
    resolved = copy.deepcopy(installation["pin"])
    unresolved_pin(t, doc, installation)
    row["lifecycle"]["state"] = "planned"
    t.bind_evidence(doc, ctx)
    t.save_doc(ctx, doc)
    t.check(t.D.load_current(ctx)[0]["rows"][0]["lifecycle"]["state"] == "planned",
            case + " planned unresolved-pin publication control")
    before = t.W.tuple_bytes(ctx)
    row["lifecycle"]["state"] = "prepared"
    error = None
    try:
        t.save_doc(ctx, doc)
        t.activate(ctx, [row["id"]])
    except t.D.Problem as exc:
        error = exc
    state = t.D.load_current(ctx)[0]["rows"][0]["lifecycle"]["state"]
    observed(case, activation_accepted=error is None, state=state,
             tuple_unchanged=t.W.tuple_bytes(ctx) == before,
             code=None if error is None else error.code,
             error=None if error is None else str(error))
    t.check(error is not None and error.code == 2 and
            "prepared/active installation pin unresolved" in str(error),
            case + " writer refuses before preparation or activation")
    t.check(state == "planned" and t.W.tuple_bytes(ctx) == before and not ctx.pending.exists(),
            case + " refused write preserves the complete published tuple")
    installation["pin"] = resolved
    for resource in doc["resources"]:
        if "pin_sha256" in resource["expected"]:
            resource["expected"]["pin_sha256"] = t.D.digest(resolved)
    t.bind_evidence(doc, ctx)
    t.save_doc(ctx, doc)
    t.activate(ctx, [row["id"]])
    t.check(t.D.load_current(ctx)[0]["rows"][0]["lifecycle"]["state"] == "active",
            case + " fresh resolved-pin proposal prepares and activates")


def snapshot_fixture(t, name):
    ctx = t.fixture(name)
    targets = ctx.vault.parent / "targets"
    t.write(targets / "leaf", "Fixture target bytes.\n")
    t.write(targets / "tree/.git/config", "Hidden inventory control.\n")
    t.write(targets / "nested/child", "Nested target bytes.\n")
    (targets / "empty").mkdir()
    (targets / "tree/nested-link").symlink_to(targets / "nested", target_is_directory=True)
    skills = ctx.home / ".claude/skills"
    for name, target in (("file-link", "leaf"), ("tree-link", "tree"), ("empty-link", "empty")):
        (skills / name).symlink_to(targets / target, target_is_directory=target != "leaf")
    settings = ctx.home / ".claude/settings.json"
    t.write(targets / "settings.json", settings.read_bytes())
    settings.unlink()
    settings.symlink_to(targets / "settings.json")
    return ctx, targets


def remove_inventory(snapshot, prefix):
    snapshot["state"] = {k: v for k, v in snapshot["state"].items()
                         if k != prefix and not k.startswith(prefix + "/")}


def test_snapshot_inventory(t, variant):
    case = "N2-" + variant
    ctx, targets = snapshot_fixture(t, case)
    root = ctx.vault.parent
    paths = [root, *sorted(root.rglob("*"))]
    modes = {p: stat.S_IMODE(p.lstat().st_mode) for p in paths if not p.is_symlink()}
    for path in sorted(modes, key=lambda p: len(p.parts), reverse=True):
        path.chmod(0o500 if path.is_dir() else 0o400)
    try:
        manifest = t.filesystem_manifest(root)
        before, after = t.S.snapshot(ctx.home, [targets]), t.S.snapshot(ctx.home, [targets])
        complete = t.S.compare(before, after, [])
        targets_seen = [k for k in before["state"] if k.endswith("/@target")]
        t.check(complete["findings"] == 0 and complete["control_hits"] == t.S.controls() and
                targets_seen and any("/@target/.git/config" in k for k in before["state"]),
                case + " complete unchanged target inventory clean with comparison controls")
        skills = str(ctx.home / ".claude/skills")
        target = skills + "/tree-link/@target"
        for value in (before, after):
            if variant == "all-targets":
                value["state"] = {k: v for k, v in value["state"].items() if "/@target" not in k}
            elif variant in ("file-target", "directory-target", "empty-target", "nested-target", "root-target"):
                prefix = {"file-target": skills + "/file-link/@target",
                          "directory-target": target,
                          "empty-target": skills + "/empty-link/@target",
                          "nested-target": target + "/nested-link/@target",
                          "root-target": str(ctx.home / ".claude/settings.json") + "/@target"}[variant]
                remove_inventory(value, prefix)
            elif variant == "target-child":
                del value["state"][target + "/.git/config"]
            elif variant == "target-json":
                value["state"][target] = {"type": "json", "value": None}
            elif variant == "target-absent":
                value["state"][target] = {"type": "absent", "logical": str(targets / "tree"),
                                         "parent": str(targets), "component": "tree"}
            elif variant in ("target-logical", "target-resolved"):
                value["state"][target][variant.removeprefix("target-")] = str(targets / "empty")
            else:
                raise ValueError("unknown target inventory variant")
            value["state_sha256"] = t.D.digest(value["state"])
        encoded = t.D.encoded([before, after])
        result, error = None, None
        try:
            result = t.S.compare(before, after, [])
        except t.D.Problem as exc:
            error = exc
        observed(case, accepted=error is None, comparison=result,
                 valid_digests=all(v["state_sha256"] == t.D.digest(v["state"]) for v in (before, after)),
                 control_hits=before["control_hits"], code=None if error is None else error.code,
                 error=None if error is None else str(error))
        t.check(t.D.encoded([before, after]) == encoded and t.filesystem_manifest(root) == manifest,
                case + " read-only copy manifests and snapshot inputs unchanged")
        t.check(error is not None and error.code == 2 and
                ("incomplete child inventory" if variant == "target-child" else
                 "incomplete symlink target inventory") in str(error),
                case + " malformed inventory refuses despite recomputed digests and valid controls")
    finally:
        for path in sorted(modes, key=lambda p: len(p.parts)):
            path.chmod(modes[path])


def test_snapshot_change(t):
    ctx, targets = snapshot_fixture(t, "N2-target-change")
    before = t.S.snapshot(ctx.home, [targets])
    t.write(targets / "nested/child", "Changed nested target bytes.\n")
    after = t.S.snapshot(ctx.home, [targets])
    manifest = t.filesystem_manifest(ctx.vault.parent)
    actual = t.S.changes(before, after)
    result = t.S.compare(before, after, [])
    t.check(result["findings"] > 0 and
            any("/tree-link/@target/nested-link/@target/child" in x["address"] for x in actual),
            "N2 complete nested target change is observed and undeclared change fails")
    exact = t.S.compare(before, after, actual)
    t.check(exact["findings"] == 0 and exact["control_hits"] == t.S.controls(),
            "N2 fully declared target change clean with positive controls")
    t.check(t.filesystem_manifest(ctx.vault.parent) == manifest,
            "N2 changed-target comparison writes nothing")


def run(root, harness=None):
    t = harness or importlib.import_module("test_register")
    previous_root, before = t.ROOT, t.COUNT
    t.ROOT = Path(root)
    cases = []
    tests = [("N1-" + route + "-" + state,
              lambda route=route, state=state: test_pin_validation(t, route, state))
             for route in ("direct", "binding", "run-needs", "dependency", "empty-direct")
             for state in ("prepared", "active")]
    tests += [("N1-publication-" + route, lambda route=route: test_pin_publication(t, route))
              for route in ("direct", "binding", "run-needs", "dependency")]
    tests += [("N2-" + variant, lambda variant=variant: test_snapshot_inventory(t, variant))
              for variant in ("all-targets", "file-target", "directory-target", "empty-target",
                              "nested-target", "root-target", "target-child", "target-json",
                              "target-absent", "target-logical", "target-resolved")]
    tests.append(("N2-target-change", lambda: test_snapshot_change(t)))
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
