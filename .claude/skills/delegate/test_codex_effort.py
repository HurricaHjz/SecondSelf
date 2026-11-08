#!/usr/bin/env python3
"""Routing effort regression; fixtures belong to the caller's disposable directory.

Run with --fixture-root inside a mktemp -d, then remove that directory. No helper is
started: all spawns use --dry-run and the CLI shim only accepts --version.
"""

import argparse
import ast
import contextlib
import hashlib
import importlib.util
import inspect
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, default=Path(__file__).with_name("codex-lane.py"))
    parser.add_argument("--routing", type=Path, default=Path(__file__).with_name("routing.json"))
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--case", choices=("explicit", "anchor", "missing", "all"), default="all")
    args = parser.parse_args()
    root = args.fixture_root.resolve()
    if not root.is_dir() or any(root.iterdir()):
        print("PROBE FAILED: --fixture-root must be an existing empty disposable directory")
        return 2
    for path in (args.adapter, args.adapter.with_name("lane.py"), args.routing):
        if not path.is_file():
            print("PROBE FAILED: missing input %s" % path)
            return 2
    table = json.loads(args.routing.read_text(encoding="utf-8"))
    classes = table.get("classes")
    if not isinstance(classes, dict) or not classes:
        print("PROBE FAILED: routing has no class anchors to control the probe")
        return 2

    wrappers = root / "wrappers"
    wrappers.mkdir()
    for name in (args.adapter.name, "lane.py"):
        shutil.copy2(args.adapter.with_name(name), wrappers / name)
    shutil.copy2(args.routing, wrappers / "routing.json")
    vault = root / "vault"
    definitions = vault / ".claude" / "agents"
    definitions.mkdir(parents=True)
    # These are labelled fixture definitions, never substitutes for live definitions.
    for cls in classes:
        (definitions / (cls + ".md")).write_text("Fixture definition.\n", encoding="utf-8")
    (root / "work").mkdir()
    (root / "store").mkdir()
    (root / "brief.md").write_text("Fixture composition only.\nCONTROL+: EFFORT-CONTROL in %s\n"
                                   % (root / "core.md"), encoding="utf-8")
    (root / "core.md").write_text("Fixture lane core. EFFORT-CONTROL\n", encoding="utf-8")
    shim = root / "codex-shim"
    shim.write_text('#!/bin/sh\nif [ "$#" = 1 ] && [ "$1" = --version ]; then\n'
                    '  printf "%s\\n" codex-effort-fixture\n  exit 0\nfi\n'
                    'printf "%s\\n" "PROBE FAILED: helper invocation forbidden" >&2\nexit 2\n',
                    encoding="utf-8")
    shim.chmod(0o555)
    def table(rows):
        return json.dumps({"schema": 2, "order": {"model": [], "effort": []}, "classes": rows})

    custom = root / "custom-routing.json"
    custom.write_text(table({"critic": {"effort": {"default": "high"}}}), encoding="utf-8")

    sys.path.insert(0, str(wrappers))
    spec = importlib.util.spec_from_file_location("effort_adapter", wrappers / args.adapter.name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    results = []

    def check(name, good, detail=""):
        results.append(bool(good))
        print(("PASS " if good else "FAIL ") + name + (": " + detail if detail else ""))

    def invoke(extra=(), cls="critic"):
        command = ["spawn", "--run", "fixture-effort", "--lane", "probe", "--class", cls,
                   "--brief", str(root / "brief.md"), "--cwd", str(root / "work"),
                   "--codex", str(shim), "--append-core", str(root / "core.md"),
                   "--reason", "(a) fixture", "--choice-reason", "effort regression",
                   "--delegation", "single", "--delegation-src", "head", "--viewer", "none",
                   "--read-only", "--dry-run", *extra]
        out, err = io.StringIO(), io.StringIO()
        # Isolate unrelated global metadata reads; effort resolution, premise checks,
        # definition reads, command composition and the dry-run branch remain real.
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(vault),
                                    "LLM_WIKI_STORE": str(root / "store")}), \
                patch.object(module, "global_instructions_bytes", return_value=(None, 0)), \
                patch.object(module, "in_git_repo", return_value=False), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = module.main(command)
            except SystemExit as exc:
                rc = exc.code
        text = out.getvalue()
        rows = [json.loads(line) for line in text.splitlines() if line.startswith('  {"ts":')]
        return rc, text, err.getvalue(), rows[-1] if rows else {}

    def anchor_of(row):
        half = (row.get("harness") or {}).get("codex") or {}
        return (half.get("effort") or row["effort"])["default"]

    def composed(result, effort):
        rc, out, err, row = result
        return (rc == 0 and row.get("effort") == effort
                and 'model_reasoning_effort="%s"' % effort in out
                and row.get("controls_checked")
                and not list((root / "store").iterdir()))

    def refusal(result, phrase):
        rc, out, err, row = result
        return (rc == 2 and "PROBE FAILED:" in err and phrase in err
                and not row and not list((root / "store").iterdir()))

    selected = args.case
    if selected in ("explicit", "all"):
        for effort in module.EFFORTS:
            result = invoke(("--effort", effort, "--routing", str(root / "absent.json")))
            check("explicit effort %s wins without routing" % effort, composed(result, effort))
        result = invoke(("--effort", ""))
        check("empty explicit effort refuses", refusal(result, "--effort"))

    if selected in ("anchor", "all"):
        result = invoke()
        check("sibling class anchor resolves", composed(result, anchor_of(classes["critic"])))
        result = invoke(("--routing", str(custom)))
        check("selected routing anchor resolves", composed(result, "high"))
        check("anchor provenance recorded", result[3].get("effort_src") == "routing class anchor"
              and result[3].get("routing_path") == str(custom))
        custom.write_text(table({"critic": {"effort": {"default": "medium"}}}), encoding="utf-8")
        check("later anchor edit changes composition", composed(invoke(("--routing", str(custom))), "medium"))
        sibling = wrappers / "routing.json"
        original = sibling.read_bytes()
        changed = json.loads(original)
        changed["classes"]["critic"]["effort"]["default"] = "low"
        changed["classes"]["critic"].get("harness", {}).get("codex", {}).get("effort", {})["default"] = "low"
        try:
            sibling.write_text(json.dumps(changed), encoding="utf-8")
            check("later sibling anchor edit changes composition", composed(invoke(), "low"))
        finally:
            sibling.write_bytes(original)
        custom.write_text(table({"critic": {
            "effort": {"default": "high"},
            "harness": {"codex": {"effort": {"default": "medium"}}}}}), encoding="utf-8")
        check("the Codex half's anchor wins over the row's", composed(invoke(("--routing", str(custom))), "medium"))
        custom.write_text(table({"critic": {
            "effort": {"default": "high"}, "harness": {"codex": {"model": {"default": "m"}}}}}), encoding="utf-8")
        check("a Codex half with no effort falls to the row's anchor",
              composed(invoke(("--routing", str(custom))), "high"))

    if selected in ("missing", "all"):
        custom.write_text(table({"critic": {"effort": {}}}), encoding="utf-8")
        check("missing anchor refuses", refusal(invoke(("--routing", str(custom))), "anchor"))
        check("explicit effort wins with missing anchor",
              composed(invoke(("--routing", str(custom), "--effort", "max")), "max"))

    if selected == "all":
        check("unknown class refuses", refusal(invoke(cls="unlisted-fixture-class"), "class"))
        check("missing routing refuses", refusal(invoke(("--routing", str(root / "absent.json"))), "routing"))
        for label, value in (("unsupported", "turbo"), ("null", None), ("empty", ""),
                             ("object", {}), ("list", [])):
            custom.write_text(table({"critic": {"effort": {"default": value}}}), encoding="utf-8")
            check(label + " anchor refuses", refusal(invoke(("--routing", str(custom))), "anchor"))
        for label, value in (("malformed JSON", "{"), ("non-object table", "[]"),
                             ("the wrong schema", '{"schema": 1, "classes": {}}'),
                             ("non-object classes", table([])),
                             ("non-object class", table({"critic": []}))):
            custom.write_text(value, encoding="utf-8")
            check(label + " refuses", refusal(invoke(("--routing", str(custom))), "routing"))

        copied_module = module
        direct_spec = importlib.util.spec_from_file_location("direct_effort_adapter", args.adapter)
        module = importlib.util.module_from_spec(direct_spec)
        direct_spec.loader.exec_module(module)
        for cls, row in classes.items():
            effort = anchor_of(row)
            result = invoke(("--routing", str(args.routing.resolve())), cls=cls)
            check("live anchor dry-run " + cls, composed(result, effort),
                  'model_reasoning_effort="%s"' % result[3].get("effort"))
        module = copied_module

        spawn_help = " ".join(module.build_parser()._subparsers._group_actions[0]
                              .choices["spawn"].format_help().split())
        check("help describes anchor", "class's anchor in routing.json" in spawn_help)

        # The old resume fallback is deliberately separate from spawn defaults.
        resume_tree = ast.parse(inspect.getsource(module.cmd_resume))
        blocks = [node for node in ast.walk(resume_tree) if isinstance(node, ast.If)
                  and ast.unparse(node.test) == "args.effort is None"]
        if len(blocks) != 1:
            print("PROBE FAILED: cannot identify the resume effort block")
            return 2
        block = compile(ast.fix_missing_locations(ast.Module(body=[blocks[0]], type_ignores=[])),
                        "<resume effort block>", "exec")
        for recorded, explicit, expected in (("high", None, "high"),
                                              ("high", "low", "low"), (None, None, "max")):
            state = dict(vars(module), args=argparse.Namespace(effort=explicit),
                         opened={"effort": recorded}, carried={})
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                exec(block, state)
            check("resume effort recorded=%r explicit=%r" % (recorded, explicit),
                  state["args"].effort == expected
                  and (recorded is not None or "historical resume fallback" in err.getvalue()))

        def manifest():
            return {str(path.relative_to(root)): (hashlib.sha256(path.read_bytes()).hexdigest(),
                                                 stat.S_IMODE(path.stat().st_mode))
                    for path in root.rglob("*") if path.is_file()}

        # Final leg: a read-only fixture, hashes before and after, and a planted
        # difference to prove that the manifest comparison can detect a change.
        all_paths = sorted(root.rglob("*"), key=lambda path: len(path.parts), reverse=True)
        for path in all_paths + [root]:
            path.chmod(0o555 if path.is_dir() or path == shim else 0o444)
        before = manifest()
        mutated = dict(before)
        key = next(iter(mutated))
        mutated[key] = ("planted difference", mutated[key][1])
        try:
            good = invoke(("--effort", "high"))
            anchored = invoke()
            bad = invoke(("--routing", str(root / "absent.json")))
            after = manifest()
            check("read-only manifests unchanged with difference control",
                  bool(before) and before == after and before != mutated
                  and composed(good, "high")
                  and composed(anchored, anchor_of(classes["critic"]))
                  and refusal(bad, "routing"), "%d files; changed=0; control=1" % len(before))
        finally:
            for path in [root] + list(reversed(all_paths)):
                path.chmod(0o755 if path.is_dir() or path == shim else 0o644)

        resolver = getattr(module, "resolve_spawn_effort", None)
        source = inspect.getsource(resolver) if resolver else ""
        pattern = re.compile(r"\b(?:write\w*|unlink|remove|rename|replace|mkdir|makedirs|rmdir|"
                             r"rmtree|copy\w*|move|touch|chmod|truncate)\s*\(|"
                             r"\bopen\([^\n]*,[ \t]*['\"][wax+]")
        clean = len(pattern.findall(source))
        planted = len(pattern.findall('open(path, "w"); path.write_text("planted")'))
        check("resolver source write-pattern grep", bool(source) and clean == 0 and planted > 0,
              "writes=%d; control=%d" % (clean, planted))

    failures = len(results) - sum(results)
    print("FAIL %d/%d" % (failures, len(results)) if failures else "PASS %d/%d" % (len(results), len(results)))
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("PROBE FAILED: %s" % exc)
        raise SystemExit(2)
