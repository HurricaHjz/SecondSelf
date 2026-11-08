#!/usr/bin/env python3
"""Regression fixtures for typed configuration observations and declarations."""
import argparse
import copy
import hashlib
import importlib
import json
from pathlib import Path
import stat
import sys


def fixture_manifest(root):
    """Include every fixture entry, so helper-created files cannot pass unnoticed."""
    result = {}
    for path in [root, *sorted(root.rglob("*"))]:
        info = path.lstat()
        result[str(path.relative_to(root))] = {
            "mode": stat.S_IMODE(info.st_mode),
            "kind": "directory" if path.is_dir() else "file",
            "sha256": None if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    return result


def run_cases(snapshot_module, fixture_root):
    """Return named results; the caller supplies and removes a fresh scratch root."""
    root = Path(fixture_root).resolve(strict=True)
    if not root.is_dir() or any(root.iterdir()):
        raise ValueError("typed snapshot fixtures need an empty scratch directory")
    results = []

    def check(name, condition):
        results.append({"case": name, "passed": bool(condition)})

    def observe(home, name):
        before = fixture_manifest(home)
        value = snapshot_module.snapshot(home)
        check(name + ": snapshot writes nothing", fixture_manifest(home) == before)
        return value

    for name, old, new in (("true-to-one", True, 1), ("one-to-true", 1, True),
                           ("false-to-zero", False, 0), ("zero-to-false", 0, False)):
        home = root / name
        home.mkdir()
        config = home / ".claude.json"
        config.write_text(json.dumps({"flag": old}) + "\n", encoding="utf-8")
        before = observe(home, name + " before")
        config.write_text(json.dumps({"flag": new}) + "\n", encoding="utf-8")
        after = observe(home, name + " after")
        manifest = fixture_manifest(home)
        actual = snapshot_module.changes(before, after)
        pointer = str(config) + "#/flag"
        semantic = [item for item in actual if item["address"] == pointer]
        typed_pointer_ok = (len(semantic) == 1 and
                            type(semantic[0]["old"]["value"]) is type(old) and
                            type(semantic[0]["new"]["value"]) is type(new))
        if not typed_pointer_ok:
            print("SNAPSHOT_DIAGNOSTIC " + json.dumps({"expected": pointer,
                "scope": before["scope"], "events": actual}, sort_keys=True), flush=True)
        check(name + ": typed pointer event", typed_pointer_ok)
        raw_only = [item for item in actual if "#" not in item["address"]]
        refused = snapshot_module.compare(before, after, raw_only)
        check(name + ": raw-only declaration refused",
              refused["findings"] == 1 and
              [item["address"] for item in refused["unexpected"]] == [pointer])
        exact = snapshot_module.compare(before, after, actual)
        check(name + ": exact declaration clean with control",
              exact["findings"] == 0 and exact["control_hits"] > 0)
        check(name + ": comparisons write nothing", fixture_manifest(home) == manifest)

    # Actual boolean changes are visible even in the defective implementation;
    # these cases therefore isolate declaration equality from event discovery.
    for old, new, name in ((True, False, "true-to-false"),
                           (False, True, "false-to-true")):
        home = root / name
        home.mkdir()
        config = home / ".claude.json"
        config.write_text(json.dumps({"flag": old}) + "\n", encoding="utf-8")
        before = observe(home, name + " before")
        config.write_text(json.dumps({"flag": new}) + "\n", encoding="utf-8")
        after = observe(home, name + " after")
        manifest = fixture_manifest(home)
        actual = snapshot_module.changes(before, after)
        pointer = str(config) + "#/flag"
        check(name + ": boolean-change positive control",
              len([item for item in actual if item["address"] == pointer]) == 1)
        exact = snapshot_module.compare(before, after, actual)
        check(name + ": exact declaration clean with control",
              exact["findings"] == 0 and exact["control_hits"] > 0)
        for field in ("old", "new"):
            forged = copy.deepcopy(actual)
            for item in forged:
                if item["address"] == pointer:
                    item[field]["value"] = int(item[field]["value"])
            refused = snapshot_module.compare(before, after, forged)
            check(name + ": wrongly typed " + field + " declaration refused",
                  refused["findings"] == 2 and
                  [item["address"] for item in refused["unexpected"]] == [pointer] and
                  [item["address"] for item in refused["unobserved"]] == [pointer])
        check(name + ": comparisons write nothing", fixture_manifest(home) == manifest)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module-dir", required=True)
    parser.add_argument("--scratch", required=True)
    args = parser.parse_args()
    try:
        sys.path.insert(0, str(Path(args.module_dir).resolve(strict=True)))
        module = importlib.import_module("adopt_snapshot")
        results = run_cases(module, args.scratch)
        for result in results:
            print(("PASS " if result["passed"] else "FAIL ") + result["case"])
        failed = sum(not result["passed"] for result in results)
        print(f"FAIL {failed}/{len(results)}" if failed else f"PASS {len(results)}/{len(results)}")
        return 1 if failed else 0
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        print("PROBE FAILED: " + str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
