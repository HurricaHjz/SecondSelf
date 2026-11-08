#!/usr/bin/env python3
"""Fixture regressions for immutable resource kinds and non-skill delivery."""
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


def test_exact_resource_kinds(t):
    ctx = t.fixture("reg3-basic-kinds")
    doc, _ = t.D.load_current(ctx)
    tree = ctx.home / "inputs" / "tree"
    leaf = tree / "source.txt"
    t.write(leaf, "Measured fixture input.\n")
    file_resource = t.resource("input-file", "file", leaf,
        {"sha256": t.D.sha(leaf.read_bytes()), "use": "Read fixture input"},
        ["file-content", "input-use"], "input-install")
    tree_resource = t.resource("input-tree", "directory-tree", tree,
        {"sha256": t.S.tree_hash(tree), "use": "Read fixture tree"},
        ["file-content", "input-use"], "input-install")
    doc["resources"] = [file_resource, tree_resource]
    t.check(t.R.observation(doc, None, file_resource, ctx)["identity"]["kind"] == "file",
            "REG3 F4 matching file positive control")
    t.check(t.R.observation(doc, None, tree_resource, ctx)["identity"]["kind"] == "directory",
            "REG3 F4 matching directory-tree positive control")
    wrong_file = copy.deepcopy(tree_resource)
    wrong_file["type"] = "file"
    t.refuses(lambda: t.R.observation(doc, None, wrong_file, ctx),
              "REG3 F4 file declaration refuses actual directory with matching digest", codes=(1,))
    wrong_tree = copy.deepcopy(file_resource)
    wrong_tree["type"] = "directory-tree"
    t.refuses(lambda: t.R.observation(doc, None, wrong_tree, ctx),
              "REG3 F4 directory-tree declaration refuses actual file with matching digest", codes=(1,))


def test_non_skill_delivery(t):
    ctx = t.fixture("reg3-basic-cli")
    doc, _ = t.D.load_current(ctx)
    row = t.add_cli(doc, ctx, "ordinary-tool")
    t.bind_evidence(doc, ctx)
    t.save_doc(ctx, doc)
    doc, _ = t.D.load_current(ctx)
    row = t.D.index(doc, "rows")["ordinary-tool"]
    t.check(not doc["policy"]["model_targets"] and
            not any(b["resource_definition"]["type"] == "skill-tree"
                    for b in t.D.expansion(doc, row)["bindings"]),
            "REG3 F5 ordinary CLI has no model targets or skill dependency")
    t.check(t.F.evaluate(doc, row, ctx, None)["tier"] is None,
            "REG3 F5 not-applicable qualification needs no model release")
    view = t.V.resolve(ctx, row["id"], None)
    t.check(view["state"] == "prepared-delivery" and
            view["qualification_refs"] == [] and view["caller_model_id"] is None,
            "REG3 F5 prepared CLI resolves without caller-model identity")
    t.check(t.V.resolve(ctx, row["id"], None, cached=view) == view,
            "REG3 F5 same caller cache remains valid positive control")
    t.refuses(lambda: t.V.resolve(ctx, row["id"], "different-caller", cached=view),
              "REG3 F5 non-skill cache still rejects changed caller binding", codes=(1,))
    t.check(t.V.resolve(ctx, row["id"], "unregistered-caller")["qualification_refs"] == [],
            "REG3 F5 ordinary CLI ignores absent model-release qualification")
    t.activate(ctx, [row["id"]])
    t.check(t.V.resolve(ctx, row["id"], None)["state"] == "active",
            "REG3 F5 active CLI resolves without model policy")
    t.write(ctx.home / "bin" / row["id"], "#!/bin/sh\nexit 1\n", 0o755)
    t.refuses(lambda: t.V.resolve(ctx, row["id"], None),
              "REG3 F5 ordinary delivery still checks installed bytes", codes=(1,))


def test_skill_closure_guard(t):
    ctx = t.skill_fixture("reg3-basic-skill-closure")
    doc, _ = t.D.load_current(ctx)
    row = doc["rows"][0]
    t.check(bool(t.F.evaluate(doc, row, ctx, "model-a-release")),
            "REG3 F5 qualified skill positive control")
    t.refuses(lambda: t.V.resolve(ctx, row["id"], None),
              "REG3 F5 skill delivery retains required caller identity", codes=(2,))
    t.refuses(lambda: t.V.resolve(ctx, row["id"], "latest"),
              "REG3 F5 skill delivery refuses alias model", codes=(2,))
    t.refuses(lambda: t.V.resolve(ctx, row["id"], "model-b-release"),
              "REG3 F5 skill delivery requires qualification for exact model", codes=(1,))
    row["kind"] = "cli"
    row["freshness"] = {"status": "not-applicable", "reason": "Forged fixture exemption"}
    t.refuses(lambda: t.F.evaluate(doc, row, ctx, "model-a-release"),
              "REG3 F5 CLI label cannot hide actual skill-bearing closure", codes=(1,))


def run(root, harness=None):
    """Run against the adopt modules selected by the caller's import path."""
    t = harness or importlib.import_module("test_register")
    previous_root, before = t.ROOT, t.COUNT
    t.ROOT = Path(root)
    cases = []
    try:
        for name, test in (("REG3-F4", test_exact_resource_kinds),
                           ("REG3-F5-delivery", test_non_skill_delivery),
                           ("REG3-F5-skill-guard", test_skill_closure_guard)):
            count = t.COUNT
            print("SUBCASE " + name, flush=True)
            try:
                test(t)
                case = {"case": name, "result": "PASS", "assertions": t.COUNT - count}
            except Exception as exc:
                traceback.print_exc(file=sys.stdout)
                case = {"case": name, "result": "FAIL", "assertions": t.COUNT - count,
                        "error": str(exc)}
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
