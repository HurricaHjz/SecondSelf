#!/usr/bin/env python3
"""test_routing_layers.py — the routing overlay: its merge, its refusals, its readers, the fold.

  python3 test_routing_layers.py [--flat] [--delegate DIR] [--lane FILE] [--review FILE] [--require-lane]

Every fixture is a throwaway vault under one temporary folder, built from a small table written
here, so no leg grades the code against the file the code reads. The exceptions read the shipped
table on purpose, since an overlay has to work against it: the legs on a preset's model and the
leg that every shipped row passes as an overlay row. Nothing outside that folder is written. The
last line is `PASS n/n` or `FAIL k/n`, and the exit code follows it.

  --delegate DIR   the folder holding the scripts under test (default: this file's own)
  --lane FILE      the lane.py under test (default: the one in that folder)
  --review FILE    the spawn-record-review.py under test (default: the deep-lint skill beside it)
  --flat           build each fixture's `.claude` folder as `claude`, for a sandbox that refuses a
                   folder of that name; the fixture's throttle.py reads the changed name
  --require-lane   a lane.py with no overlay branch fails; without this flag those legs print one
                   UNRUN line outside the tally, since lane.py may install after this suite

Exit 0 every leg passed. Exit 1 a leg failed. Exit 2 PROBE FAILED: a premise of the suite broke.
"""
import argparse
import ast
import decimal
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
OVERLAY_NAME = "routing.local.json"


def class_row(models, default):
    return {"layer": "core", "model": {"options": models, "default": default},
            "effort": {"options": ["high", "xhigh", "max"], "default": "xhigh"},
            "grants": {"default": [], "extras": []}, "writes": [], "tools": ["Read"],
            "skills": {"default": ["lane-core"], "extras": []},
            "mcp": {"default": [], "grantable": []}, "cache": "1h",
            "gate": "fixture gate", "dated": "fixture date"}


HARNESS = {"codex": {"model": {"options": ["fixture-model"], "default": "fixture-model"},
                     "effort": {"options": ["xhigh", "max"], "default": "max"},
                     "note": "fixture"}}
TABLE = {"schema": 2,
         "rules": [{"from": "fixture", "layer": "core", "text": "a shipped row"}],
         "order": {"model": ["haiku", "sonnet", "opus", "fable"],
                   "effort": ["low", "medium", "high", "xhigh", "max"]},
         "preset_model": {"top": "opus", "cheap": "opus", "_": "the shipped table's shape"},
         "classes": {"critic": dict(class_row(["opus"], "opus"), harness=HARNESS),
                     "writer": class_row(["sonnet", "opus"], "opus")},
         "_": "the table's own note"}
OWN_ROW = class_row(["sonnet"], "sonnet")
THROTTLES = ("auto", "top", "default", "cheap", "fast", "cheap-fast")
SONNET_ONLY = {"model": {"options": ["sonnet"], "default": "sonnet"}}
RULES = [{"from": "fixture", "layer": "yours", "text": "the user's first row"},
         {"from": "fixture", "layer": "yours", "text": "the user's second row"}]
DEFINITION = """---
name: %s
description: Routing range; the active throttle sets the current values.
model: %s
effort: xhigh
disallowedTools: Agent, SendMessage, Skill
---

Body text.
"""
SETTINGS = """`CUSTOMISATION-LOADED-v1` marker.

## Settings
- **throttle**: auto — routing throttle
"""


class Suite:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def leg(self, name, held, detail=""):
        if held:
            self.passed += 1
            print("  ok   — " + name)
        else:
            self.failed += 1
            print("FAIL   — %s%s" % (name, " (%s)" % detail if detail else ""))

    def finish(self):
        total = self.passed + self.failed
        if self.failed:
            print("FAIL %d/%d" % (self.failed, total))
            return 1
        print("PASS %d/%d" % (total, total))
        return 0


def run(argv, cwd=None):
    done = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True, timeout=120)
    return done.returncode, done.stdout


def write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def manifest(folder):
    """path -> sha-256 of every file under `folder`."""
    found = {}
    for root, _dirs, files in os.walk(folder):
        for name in files:
            path = os.path.join(root, name)
            found[os.path.relpath(path, folder)] = hashlib.sha256(read_bytes(path)).hexdigest()
    return found


def imports_at_top(source, module):
    """True where `module` is imported at module level, outside any function."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.Import) and any(a.name == module for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == module:
            return True
    return False


class Fixtures:
    def __init__(self, work, opts):
        self.work = work
        self.flat = opts.flat
        self.delegate = opts.delegate
        self.dot = "claude" if opts.flat else ".claude"
        self.lane = opts.lane
        self.review = opts.review
        self.count = 0
        shipped = os.path.join(opts.delegate, "routing.json")
        self.shipped_table = read_json(shipped) if os.path.isfile(shipped) else None

    def copy_script(self, source, dest):
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
        if self.flat and os.path.basename(source) == "throttle.py":
            text = text.replace('".claude"', '"claude"')
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as handle:
            handle.write(text)

    def vault(self, overlay=None, table=None, scripts=("throttle.py", "routing_layers.py"),
              core_list=False, own_definition=False, overlay_text=None):
        """A throwaway vault; returns its root. Scripts that the tree lacks are left out, so the
        suite reports a failed leg on an old tree and never stops."""
        self.count += 1
        root = os.path.join(self.work, "vault%d" % self.count)
        dot = os.path.join(root, self.dot)
        delegate = os.path.join(dot, "skills", "delegate")
        write_json(os.path.join(delegate, "routing.json"), table or TABLE)
        for name in scripts:
            source = self.lane if name == "lane.py" else os.path.join(self.delegate, name)
            if os.path.isfile(source):
                self.copy_script(source, os.path.join(delegate, name))
        os.makedirs(os.path.join(dot, "agents"))
        stems = [("critic", "opus"), ("writer", "opus")]
        if own_definition:
            stems.append(("my-helper", "sonnet"))
        for stem, model in stems:
            with open(os.path.join(dot, "agents", stem + ".md"), "w", encoding="utf-8") as handle:
                handle.write(DEFINITION % (stem, model))
        with open(os.path.join(root, "CUSTOMISATION.md"), "w", encoding="utf-8") as handle:
            handle.write(SETTINGS)
        if overlay is not None:
            write_json(os.path.join(dot, OVERLAY_NAME), overlay)
        if overlay_text is not None:
            with open(os.path.join(dot, OVERLAY_NAME), "w", encoding="utf-8") as handle:
                handle.write(overlay_text)
        if core_list:
            with open(os.path.join(dot, "core-paths"), "w", encoding="utf-8") as handle:
                handle.write("CLAUDE.md\n")
        return root

    def table(self, root):
        return os.path.join(root, self.dot, "skills", "delegate", "routing.json")

    def overlay(self, root):
        return os.path.join(root, self.dot, OVERLAY_NAME)

    def script(self, root, name):
        return os.path.join(root, self.dot, "skills", "delegate", name)

    def throttle(self, root, *argv):
        return run([PY, self.script(root, "throttle.py")] + list(argv) + ["--root", root])

    def resolve(self, root, cls, *extra):
        """(exit, the row or None, the raw output)."""
        code, out = run([PY, self.script(root, "throttle.py"), "resolve", "--root", root,
                         "--class", cls, "--json"] + list(extra))
        try:
            return code, json.loads(out), out
        except ValueError:
            return code, None, out

    def load(self, root, parse="float"):
        """(exit, the record or None, raw output) from routing_layers.load in the fixture."""
        code = ("import decimal, json, sys\nsys.path.insert(0, sys.argv[1])\nimport routing_layers\n"
                "record = routing_layers.load(sys.argv[2], parse_float=%s)\n"
                "print(json.dumps(record, default=lambda v: 'Decimal:' + str(v)))\n"
                % ("decimal.Decimal" if parse == "decimal" else "float"))
        status, out = run([PY, "-c", code, os.path.dirname(self.script(root, "routing_layers.py")),
                           self.table(root)])
        try:
            return status, json.loads(out), out
        except ValueError:
            return status, None, out

    def check(self, root):
        return run([PY, self.script(root, "routing_layers.py"), "--check", self.table(root)])

    def check_throttle(self, root):
        return run([PY, self.script(root, "throttle.py"), "check", "--root", root])


def merge_legs(suite, fx):
    print("== the merge")
    root = fx.vault()
    code, record, out = fx.load(root)
    suite.leg("no overlay: load gives the table's own record, key for key",
              code == 0 and json.dumps(record) == json.dumps(read_json(fx.table(root))), out[-300:])

    root = fx.vault({"rules": RULES})
    code, record, out = fx.load(root)
    texts = [row["text"] for row in (record or {}).get("rules", [])]
    suite.leg("`rules` rows append after the table's, in the overlay's order",
              texts == ["a shipped row", "the user's first row", "the user's second row"], out[-300:])
    suite.leg("an overlay of rows alone leaves every class as the table has it",
              (record or {}).get("classes") == TABLE["classes"])

    plain = fx.vault()
    _code, row, out = fx.resolve(plain, "writer")
    suite.leg("control: with no overlay `writer` resolves to the table's default", bool(row) and row["model"] == "opus", out[-300:])
    root = fx.vault({"classes": {"writer": {"model": {"default": "sonnet"}}}})
    code, row, out = fx.resolve(root, "writer")
    suite.leg("a class override changes `resolve`", code == 0 and bool(row) and row["model"] == "sonnet", out[-300:])
    suite.leg("an object merges key by key: the table's options survive",
              bool(row) and row["model_options"] == ["sonnet", "opus"], out[-300:])

    root = fx.vault({"classes": {"writer": {"effort": {"options": ["high"], "default": "high"}}}})
    code, row, out = fx.resolve(root, "writer")
    suite.leg("a list replaces what the table holds, whole",
              code == 0 and bool(row) and row["effort_options"] == ["high"], out[-300:])

    block = {"soft_usd": 1.25, "usual_usd": 0.5, "n": 3, "window": "w", "source": "s"}
    root = fx.vault({"classes": {"writer": {"cost": block}}})
    _code, record, out = fx.load(root, "decimal")
    cost = ((record or {}).get("classes", {}).get("writer") or {}).get("cost") or {}
    suite.leg("parse_float reaches the overlay's numbers", cost.get("soft_usd") == "Decimal:1.25", out[-300:])

    root = fx.vault({"_": "the user's note", "rules": RULES})
    _code, record, out = fx.load(root)
    suite.leg("the overlay may carry a note, and the table's own stays",
              (record or {}).get("_") == "the table's own note", out[-300:])


REFUSALS = [
    ("an overlay that is not JSON", None, "{ nope", "not valid JSON"),
    ("an overlay that is not an object", None, "[]\n", "is not an object"),
    ("an unknown top-level key", {"preset_model": {"top": "sonnet"}}, None, "unknown key: preset_model"),
    ("a class the table lacks, without the prefix", {"classes": {"stranger": class_row(["opus"], "opus")}}, None,
     "names no class of the table"),
    ("an unknown key on a class", {"classes": {"writer": {"modle": {"default": "sonnet"}}}}, None,
     "names an unknown key: modle"),
    ("an unknown key inside a block", {"classes": {"writer": {"model": {"defualt": "sonnet"}}}}, None,
     "names an unknown key: defualt"),
    ("a default outside the options", {"classes": {"writer": {"model": {"default": "fable"}}}}, None,
     "is not one of its options"),
    ("an option outside `order`", {"classes": {"writer": {"model": {"options": ["gpt"], "default": "gpt"}}}}, None,
     "is not in `order.model`"),
    ("`rules` that is not a list", {"rules": {"text": "x"}}, None, "`rules` is not a list"),
    ("a rule with no text", {"rules": [{"from": "x"}]}, None, "has no `text`"),
    ("an unknown key on a rule", {"rules": [{"text": "x", "weight": 2}]}, None, "names an unknown key: weight"),
    ("a class of the user's own that is not a whole row", {"classes": {"my-helper": {"model": {"options": ["opus"], "default": "opus"}}}}, None,
     "is missing"),
    ("a key of the merged record's own", {"preset_free": ["critic"]}, None, "unknown key: preset_free"),
    ("an unknown key in `harness`", {"classes": {"critic": {"harness": {"claude": {}}}}}, None,
     "names an unknown key: claude"),
    ("an unknown key in `harness.codex`", {"classes": {"critic": {"harness": {"codex": {"efort": {"default": "xhigh"}}}}}}, None,
     "names an unknown key: efort"),
    ("an unknown key in `harness.codex.effort`", {"classes": {"critic": {"harness": {"codex": {"effort": {"defualt": "xhigh"}}}}}}, None,
     "names an unknown key: defualt"),
    ("an unknown key in `harness.codex.model`", {"classes": {"critic": {"harness": {"codex": {"model": {"optoins": []}}}}}}, None,
     "names an unknown key: optoins"),
    ("a nested default outside its options", {"classes": {"critic": {"harness": {"codex": {"effort": {"options": ["xhigh"]}}}}}}, None,
     "needs options containing its default"),
    ("a nested default outside the table's options", {"classes": {"critic": {"harness": {"codex": {"effort": {"default": "ultra"}}}}}}, None,
     "needs options containing its default"),
    ("a nested block with no options", {"classes": {"writer": {"harness": {"codex": {"model": {"default": "x"}}}}}}, None,
     "needs options containing its default"),
    ("`harness` that is not an object", {"classes": {"critic": {"harness": "codex"}}}, None,
     "`classes.critic.harness` is not an object"),
    ("`harness.codex` that is not an object", {"classes": {"critic": {"harness": {"codex": "on"}}}}, None,
     "`classes.critic.harness.codex` is not an object"),
    ("an unknown key in `cost`", {"classes": {"writer": {"cost": {"sof_usd": 1.0}}}}, None,
     "names an unknown key: sof_usd"),
    ("`cost` that is not an object", {"classes": {"writer": {"cost": "dear"}}}, None,
     "`classes.writer.cost` is not an object"),
    ("a `cost` figure that is not a positive number", {"classes": {"writer": {"cost": {"soft_usd": -1, "usual_usd": 0.5}}}}, None,
     "`classes.writer.cost.soft_usd` is not a positive number"),
    ("a `cost` block short of a figure", {"classes": {"writer": {"cost": {"soft_usd": 1.0}}}}, None,
     "`classes.writer.cost.usual_usd` is not a positive number"),
]


def refusal_legs(suite, fx):
    print("== the refusals: exit 2, PROBE FAILED, and never the table alone")
    for name, overlay, text, reason in REFUSALS:
        root = fx.vault(overlay, overlay_text=text)
        code, row, out = fx.resolve(root, "writer")
        suite.leg("refused: %s" % name,
                  code == 2 and row is None and "PROBE FAILED" in out and reason in out, out[-300:])
    root = fx.vault(overlay_text="{ nope")
    code, out = fx.check(root)
    suite.leg("`--check` refuses the same overlay, exit 2", code == 2 and "PROBE FAILED" in out, out[-300:])
    root = fx.vault({"rules": RULES})
    code, out = fx.check(root)
    suite.leg("control: `--check` passes a good overlay, naming its counts",
              code == 0 and "merges cleanly (3 rules rows, 2 classes)" in out, out[-300:])
    old = {"order": TABLE["order"], "roles": {"critic": {"model": ["opus", "opus", "opus"], "effort": ["max", "max"]}}}
    root = fx.vault({"classes": {"critic": {"cache": "5m"}}}, table=old)
    code, out = fx.check(root)
    suite.leg("refused: class overrides on a table that is not schema 2",
              code == 2 and "need a schema 2 table" in out, out[-300:])


def nested_legs(suite, fx):
    print("== `harness` and `cost` overrides that are well formed")
    root = fx.vault({"classes": {"critic": {"harness": {"codex": {"effort": {"default": "xhigh"}}}}}})
    code, record, out = fx.load(root)
    effort = ((record or {}).get("classes", {}).get("critic", {}).get("harness", {}).get("codex", {})).get("effort") or {}
    suite.leg("the spelt override passes and moves the nested default", code == 0 and effort.get("default") == "xhigh", out[-300:])
    suite.leg("and the table's nested options survive it", effort.get("options") == ["xhigh", "max"], out[-300:])
    suite.leg("control: the fixture's own nested default is another value", HARNESS["codex"]["effort"]["default"] != "xhigh")
    block = {"soft_usd": 1.25, "usual_usd": 0.5, "n": 3, "window": "w", "source": "s"}
    root = fx.vault({"classes": {"my-helper": dict(OWN_ROW, harness=HARNESS, cost=block)}})
    code, out = fx.check(root)
    suite.leg("a class of the user's own may carry both blocks", code == 0 and "merges cleanly" in out, out[-300:])
    root = fx.vault({"classes": {"writer": {"cost": None}}})
    code, out = fx.check(root)
    suite.leg("a `cost` of null is no block, as lane.py reads it", code == 0, out[-300:])
    if fx.shipped_table is None:
        suite.leg("the shipped table is there to read", False, fx.delegate)
        return
    root = fx.vault({"classes": fx.shipped_table["classes"]}, table=fx.shipped_table)
    code, out = fx.check(root)
    suite.leg("every shipped row passes as an overlay row, so the key lists hold what the table holds",
              code == 0 and "merges cleanly" in out, out[-300:])


def resolved_models(fx, root, cls):
    """{throttle: model} through `throttle.py resolve`; a refused preset reads as its exit code."""
    found = {}
    for name in THROTTLES:
        code, row, _out = fx.resolve(root, cls, "--throttle", name)
        found[name] = row["model"] if code == 0 and row else code
    return found


def preset_legs(suite, fx):
    print("== a user may exclude a preset's model from a class")
    if fx.shipped_table is None:
        suite.leg("the shipped table is there to read", False, fx.delegate)
        return
    shipped = fx.shipped_table
    pins = {name: model for name, model in (shipped.get("preset_model") or {}).items() if name != "_"}
    suite.leg("control: the shipped table pins presets, and `critic` lists only the pinned model",
              bool(pins) and all(shipped["classes"]["critic"]["model"]["options"] == [model] for model in pins.values()), str(pins))
    sonnet = {name: "sonnet" for name in THROTTLES}
    overlay = {"classes": {"critic": SONNET_ONLY, "my-helper": OWN_ROW}}
    root = fx.vault(overlay, table=shipped)
    code, out = fx.check(root)
    suite.leg("the shipped table takes an overlay with opus left out", code == 0 and "merges cleanly" in out, out[-300:])
    found = resolved_models(fx, root, "critic")
    suite.leg("an existing class on sonnet alone resolves to sonnet under every preset", found == sonnet, str(found))
    found = resolved_models(fx, root, "my-helper")
    suite.leg("a class of the user's own on sonnet alone resolves to sonnet under every preset", found == sonnet, str(found))
    pinned_class = next(name for name, row in shipped["classes"].items() if len(row["model"]["options"]) > 1)
    found = resolved_models(fx, root, pinned_class)
    suite.leg("control: a class the overlay left alone keeps each pin",
              all(found[name] == model for name, model in pins.items()), str(found))

    root = fx.vault({"classes": {pinned_class: {"model": {"default": "sonnet"}}}}, table=shipped)
    found = resolved_models(fx, root, pinned_class)
    suite.leg("control: a class that keeps the model listed keeps the pin, whatever its default",
              all(found[name] == model for name, model in pins.items()) and found["auto"] == "sonnet", str(found))

    root = fx.vault({"classes": {"critic": {"model": {"options": ["haiku", "sonnet"], "default": "sonnet"}}}}, table=shipped)
    found = resolved_models(fx, root, "critic")
    suite.leg("a freed class of two options picks by the throttle's table: strongest, weakest, default",
              (found["top"], found["cheap"], found["auto"]) == ("sonnet", "haiku", "sonnet"), str(found))

    two_pins = dict(TABLE, preset_model={"top": "opus", "cheap": "sonnet"})
    two_pins["classes"] = {"critic": class_row(["sonnet", "opus"], "opus"), "writer": class_row(["sonnet", "opus"], "opus")}
    root = fx.vault({"classes": {"critic": {"model": {"options": ["haiku", "sonnet"], "default": "sonnet"}}}}, table=two_pins)
    found = resolved_models(fx, root, "critic")
    suite.leg("a freed class still takes a pin it lists", (found["top"], found["cheap"]) == ("sonnet", "sonnet"), str(found))

    faulty = dict(TABLE, classes=dict(TABLE["classes"], critic=class_row(["sonnet"], "sonnet")))
    root = fx.vault(table=faulty)
    code, out = fx.check_throttle(root)
    suite.leg("the table alone may not leave the model out: a broken premise",
              code == 2 and "does not list among its model options" in out, out[-300:])
    root = fx.vault({"rules": RULES, "classes": {"critic": {"cache": "5m"}}}, table=faulty)
    code, out = fx.check_throttle(root)
    suite.leg("nor may an overlay that gave that class no options free it",
              code == 2 and "does not list among its model options" in out, out[-300:])

    root = fx.vault({"classes": {"critic": SONNET_ONLY}})
    for name in ("cheap", "top"):
        code, out = fx.throttle(root, "set", name)
        with open(os.path.join(root, fx.dot, "agents", "critic.md"), encoding="utf-8") as handle:
            written = handle.read()
        suite.leg("`set %s` writes the freed class's definition" % name, code == 0 and "model: sonnet" in written, out[-300:])
    code, out = fx.throttle(root, "check")
    suite.leg("and check is clean after it", code == 0 and "check: clean" in out, out[-300:])

    root = fx.vault({"rules": RULES, "classes": {"writer": {"model": {"default": "sonnet"}}}})
    _code, record, out = fx.load(root)
    suite.leg("an overlay that frees nothing adds no key to the record", "preset_free" not in (record or {"preset_free": 1}), out[-300:])


def own_class_legs(suite, fx):
    print("== a class of the user's own, and where the overlay sits")
    root = fx.vault(own_definition=True)
    _code, out = fx.throttle(root, "check")
    suite.leg("control: a user's helper with no row reads UNROUTED", "UNROUTED" in out and "my-helper" in out, out[-300:])
    root = fx.vault({"classes": {"my-helper": OWN_ROW}}, own_definition=True)
    code, out = fx.throttle(root, "check")
    suite.leg("`classes.my-<name>` routes it: no UNROUTED, and check is clean",
              code == 0 and "UNROUTED" not in out and "check: clean" in out, out[-300:])
    code, row, out = fx.resolve(root, "my-helper")
    suite.leg("the throttle resolves it", code == 0 and bool(row) and row["model"] == "sonnet", out[-300:])
    code, out = fx.throttle(root, "set", "cheap")
    with open(os.path.join(root, fx.dot, "agents", "my-helper.md"), encoding="utf-8") as handle:
        written = handle.read()
    suite.leg("`set` writes its definition like any other", code == 0 and "model: sonnet" in written, out[-300:])

    root = fx.vault({"classes": {"writer": {"model": {"default": "sonnet"}}}})
    delegate = os.path.dirname(fx.table(root))
    custom = os.path.join(fx.work, "elsewhere", "a", "b", "c")
    os.makedirs(custom)
    shutil.copy(fx.table(root), os.path.join(custom, "routing.json"))
    for name in ("routing_layers.py", "throttle.py"):
        if os.path.isfile(os.path.join(delegate, name)):
            shutil.copy(os.path.join(delegate, name), os.path.join(custom, name))
    write_json(os.path.join(fx.work, "elsewhere", "a", OVERLAY_NAME), {"rules": RULES})
    code, out = run([PY, os.path.join(custom, "routing_layers.py"), "--check", os.path.join(custom, "routing.json")])
    suite.leg("the overlay sits three levels above a table named anywhere",
              code == 0 and "merges cleanly (3 rules rows" in out, out[-300:])
    os.remove(os.path.join(fx.work, "elsewhere", "a", OVERLAY_NAME))
    write_json(os.path.join(fx.work, "elsewhere", "a", "b", OVERLAY_NAME), {"rules": RULES})
    code, out = run([PY, os.path.join(custom, "routing_layers.py"), "--check", os.path.join(custom, "routing.json")])
    suite.leg("control: an overlay two levels above is not read", code == 0 and "no overlay at" in out, out[-300:])


def lazy_legs(suite, fx):
    print("== the lazy import")
    root = fx.vault(scripts=("throttle.py",))
    code, out = fx.throttle(root, "show")
    suite.leg("throttle.py copied alone, no overlay: it runs", code == 0 and "check: clean" in out, out[-300:])
    suite.leg("control: that fixture holds no routing_layers.py",
              not os.path.exists(fx.script(root, "routing_layers.py")))
    root = fx.vault({"rules": RULES}, scripts=("throttle.py",))
    code, out = fx.throttle(root, "show")
    suite.leg("throttle.py alone with an overlay: exit 2, naming the module, never the table alone",
              code == 2 and "PROBE FAILED" in out and "routing_layers.py" in out, out[-300:])
    sources = [("throttle.py", os.path.join(fx.delegate, "throttle.py")), ("the review", fx.review)]
    if fx_lane_ready(fx):
        sources.append(("lane.py", fx.lane))
    for name, path in sources:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        suite.leg("%s holds no top-level import of routing_layers" % name,
                  not imports_at_top(text, "routing_layers") and "import routing_layers" in text)
    suite.leg("control: the same probe catches a top-level import",
              imports_at_top("import os\nimport routing_layers\n", "routing_layers"))
    suite.leg("control: and passes one inside a function",
              not imports_at_top("def load():\n    import routing_layers\n", "routing_layers"))
    root = fx.vault({"rules": RULES})
    fx.throttle(root, "show")
    caches = [folder for folder, _dirs, _files in os.walk(root) if os.path.basename(folder) == "__pycache__"]
    suite.leg("the import leaves no __pycache__ in the skill folder", not caches, ", ".join(caches))


def review_legs(suite, fx):
    print("== spawn-record-review.py reads the merged table")
    records = os.path.join(fx.work, "review-records")
    os.makedirs(records)
    with open(os.path.join(records, "a.jsonl"), "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": "lane-open", "ts": "2026-10-01T10:00:00+0100", "lane": "L1",
                                 "class": "my-helper", "model": "sonnet", "effort": "xhigh",
                                 "throttle": "auto", "row_default": {"model": "sonnet", "effort": "xhigh"}}) + "\n")
    log = os.path.join(fx.work, "review-log.md")
    with open(log, "w", encoding="utf-8") as handle:
        handle.write("# log\n")

    def review(root):
        code, out = run([PY, fx.script(root, "spawn-record-review.py"), "--records", records,
                         "--routing", fx.table(root), "--log", log, "--json"])
        return code, out

    def plant(root):
        target = os.path.join(root, fx.dot, "skills", "deep-lint")
        os.makedirs(target)
        shutil.copy(fx.review, os.path.join(target, "spawn-record-review.py"))
        return target

    root = fx.vault(scripts=())
    target = plant(root)
    os.rename(os.path.join(target, "spawn-record-review.py"), fx.script(root, "spawn-record-review.py"))
    code, out = review(root)
    suite.leg("the review copied alone, no overlay: it runs", code == 0 and not os.path.exists(fx.script(root, "routing_layers.py")), out[-300:])
    suite.leg("control: with no overlay a user's class reads as unknown", "unknown class" in out, out[-300:])

    root = fx.vault({"classes": {"my-helper": OWN_ROW}})
    target = plant(root)
    code, out = run([PY, os.path.join(target, "spawn-record-review.py"), "--records", records,
                     "--routing", fx.table(root), "--log", log, "--json"])
    suite.leg("through the overlay the class is known", code == 0 and "unknown class" not in out and '"lanes": 1' in out, out[-300:])

    root = fx.vault(overlay_text="{ nope")
    target = plant(root)
    code, out = run([PY, os.path.join(target, "spawn-record-review.py"), "--records", records,
                     "--routing", fx.table(root), "--log", log, "--json"])
    suite.leg("a broken overlay stops the review: exit 2, PROBE FAILED", code == 2 and "PROBE FAILED" in out, out[-300:])


def fx_lane_ready(fx):
    if not os.path.isfile(fx.lane):
        return False
    with open(fx.lane, encoding="utf-8") as handle:
        return "def fold_source(" in handle.read()


def costs(work, name, by_class):
    folder = os.path.join(work, name)
    os.makedirs(folder)
    with open(os.path.join(folder, "a.jsonl"), "w", encoding="utf-8") as handle:
        for cls, amounts in by_class.items():
            for amount in amounts:
                handle.write(json.dumps({"event": "lane-closed", "exit_class": "completed", "class": cls,
                                         "total_cost_usd": amount, "ts": "2026-10-01T10:00:00+0100"}) + "\n")
    return folder


def lane_legs(suite, fx):
    print("== lane.py: the merged read and the fold")
    script = ("import decimal, json, sys\nsys.path.insert(0, sys.argv[1])\nimport lane\n"
              "data = lane.load_routing(sys.argv[2], parse_float=decimal.Decimal)\n"
              "row = data['classes']['writer']\n"
              "print(row['model']['default'], type((row.get('cost') or {}).get('soft_usd')).__name__, len(data.get('rules', [])))\n")
    both = ("throttle.py", "routing_layers.py", "lane.py")

    def lane_read(root):
        return run([PY, "-c", script, os.path.dirname(fx.script(root, "lane.py")), fx.table(root)])

    block = {"soft_usd": 1.25, "usual_usd": 0.5, "n": 3, "window": "w", "source": "s"}
    root = fx.vault({"rules": RULES, "classes": {"writer": {"model": {"default": "sonnet"}, "cost": block}}}, scripts=both)
    code, out = lane_read(root)
    suite.leg("load_routing merges the overlay, its numbers parsed as the caller asks",
              code == 0 and out.strip() == "sonnet Decimal 3", out[-300:])
    root = fx.vault(scripts=("lane.py",))
    code, out = lane_read(root)
    suite.leg("lane.py copied alone, no overlay: it reads the table", code == 0 and out.startswith("opus "), out[-300:])
    root = fx.vault({"rules": RULES}, scripts=("lane.py",))
    code, out = lane_read(root)
    suite.leg("lane.py alone with an overlay: exit 2, naming the module",
              code == 2 and "PROBE FAILED" in out and "routing_layers.py" in out, out[-300:])
    root = fx.vault(overlay_text="{ nope", scripts=both)
    code, out = lane_read(root)
    suite.leg("a broken overlay stops lane.py: exit 2, PROBE FAILED", code == 2 and "PROBE FAILED" in out, out[-300:])

    closes = costs(fx.work, "closes-writer", {"writer": [2.0, 3.0, 4.0]})

    def fold(root, records=closes, *extra):
        return run([PY, fx.script(root, "lane.py"), "cost-figures", "--records", records,
                    "--routing", fx.table(root)] + list(extra))

    overlay = {"rules": RULES, "classes": {"writer": {"model": {"default": "sonnet"}}}}
    root = fx.vault(overlay, scripts=both)
    held = read_bytes(fx.overlay(root))
    code, out = fold(root, closes, "--fold")
    table = read_json(fx.table(root))
    suite.leg("a vault with no core list folds into its table", code == 0 and "cost" in table["classes"]["writer"], out[-300:])
    suite.leg("no overlay row reaches the table after a fold", [r["text"] for r in table["rules"]] == ["a shipped row"])
    suite.leg("no overlay class value reaches the table", table["classes"]["writer"]["model"]["default"] == "opus")
    suite.leg("that fold leaves the overlay byte-identical", read_bytes(fx.overlay(root)) == held)

    root = fx.vault(overlay, scripts=both, core_list=True)
    held = read_bytes(fx.table(root))
    code, out = fold(root, closes, "--fold")
    after = read_json(fx.overlay(root))
    suite.leg("a user's copy folds into the overlay and leaves the table byte-identical",
              code == 0 and read_bytes(fx.table(root)) == held and "cost" in after["classes"]["writer"], out[-300:])
    suite.leg("it writes only `classes.<name>.cost`: rows and overrides stand as they were",
              after["rules"] == RULES and set(after["classes"]) == {"writer"}
              and after["classes"]["writer"]["model"] == {"default": "sonnet"}
              and set(after["classes"]["writer"]) == {"model", "cost"})
    code, out = fx.check(root)
    suite.leg("the overlay passes its check after a fold", code == 0 and "merges cleanly" in out, out[-300:])
    folded = read_bytes(fx.overlay(root))
    code, out = fold(root, closes, "--fold")
    suite.leg("a second fold writes nothing", code == 0 and read_bytes(fx.overlay(root)) == folded, out[-300:])
    code, out = fold(root, closes, "--check")
    suite.leg("`--check` reads the folded block as the same", code == 0 and "same" in out, out[-300:])

    root = fx.vault(scripts=both, core_list=True)
    code, out = fold(root, closes, "--fold")
    after = read_json(fx.overlay(root)) if os.path.exists(fx.overlay(root)) else {}
    suite.leg("a user's copy with no overlay gets one, holding that class alone",
              code == 0 and list(after.get("classes", {})) == ["writer"], out[-300:])
    code, out = fx.check(root)
    suite.leg("and it passes its check", code == 0 and "merges cleanly" in out, out[-300:])

    root = fx.vault(overlay_text='{"rules": []}', scripts=both, core_list=True)
    code, out = fold(root, closes, "--fold")
    suite.leg("a one-line overlay folds", code == 0 and "cost" in read_json(fx.overlay(root))["classes"]["writer"], out[-300:])

    few = costs(fx.work, "closes-few", {"writer": [2.0]})
    root = fx.vault({"classes": {"writer": {"cost": block}}}, scripts=both, core_list=True)
    code, out = fold(root, few, "--fold")
    after = read_json(fx.overlay(root))
    suite.leg("a block below the floor goes, and the emptied row with it",
              code == 0 and after.get("classes") == {}, out[-300:])

    own = costs(fx.work, "closes-own", {"my-helper": [1.0, 1.0, 1.0]})
    root = fx.vault({"classes": {"my-helper": OWN_ROW}}, scripts=both, core_list=True, own_definition=True)
    code, out = fold(root, own, "--fold")
    row = read_json(fx.overlay(root))["classes"]["my-helper"]
    suite.leg("a class of the user's own keeps its whole row and gains its cost",
              code == 0 and "cost" in row and row["model"] == OWN_ROW["model"] and row["gate"] == OWN_ROW["gate"], out[-300:])

    root = fx.vault(overlay_text="{ nope", scripts=both, core_list=True)
    held = read_bytes(fx.overlay(root))
    code, out = fold(root, closes, "--fold")
    suite.leg("a broken overlay stops the fold and is left as it was",
              code == 2 and "PROBE FAILED" in out and read_bytes(fx.overlay(root)) == held, out[-300:])

    root = fx.vault({"classes": {"critic": SONNET_ONLY}}, scripts=both, core_list=True)
    code, out = fold(root, closes, "--fold")
    text = read_bytes(fx.overlay(root)).decode("utf-8")
    suite.leg("a fold writes no `preset_free`, which only the merged record holds",
              code == 0 and "cost" in read_json(fx.overlay(root))["classes"]["writer"] and "preset_free" not in text, out[-300:])

    print("== lane.py under a class that leaves a preset's model out")
    shipped = fx.shipped_table
    tiers = ("import json, sys\nsys.path.insert(0, sys.argv[1])\nimport lane\n"
             "data = lane.load_routing(sys.argv[2])\nfound = {}\n"
             "for cls in sys.argv[3:]:\n"
             "    found[cls] = {name: lane.resolve_tier(data, data['classes'][cls], cls, name)[0] for name in lane.THROTTLES}\n"
             "print(json.dumps(found))\n")

    def lane_tiers(root, *classes):
        code, out = run([PY, "-c", tiers, os.path.dirname(fx.script(root, "lane.py")), fx.table(root)] + list(classes))
        try:
            return code, json.loads(out), out
        except ValueError:
            return code, {}, out

    if shipped is None:
        suite.leg("the shipped table is there to read", False, fx.delegate)
        return
    pinned_class = next(name for name, row in shipped["classes"].items() if len(row["model"]["options"]) > 1)
    root = fx.vault({"classes": {"critic": SONNET_ONLY, "my-helper": OWN_ROW}}, table=shipped, scripts=both)
    code, found, out = lane_tiers(root, "critic", "my-helper", pinned_class)
    sonnet = {name: "sonnet" for name in THROTTLES}
    suite.leg("an existing class on sonnet alone resolves to sonnet under every preset, through lane.py",
              code == 0 and found.get("critic") == sonnet, out[-300:])
    suite.leg("a class of the user's own too", found.get("my-helper") == sonnet, out[-300:])
    suite.leg("control: the two resolvers agree on each of the three classes under every preset",
              all(found.get(cls) == resolved_models(fx, root, cls) for cls in ("critic", "my-helper", pinned_class)), out[-300:])
    suite.leg("control: a class the overlay left alone keeps each pin",
              all(found.get(pinned_class, {}).get(name) == model for name, model in shipped["preset_model"].items() if name != "_"), out[-300:])
    two_pins = dict(TABLE, preset_model={"top": "opus", "cheap": "sonnet"})
    two_pins["classes"] = {"critic": class_row(["sonnet", "opus"], "opus"), "writer": class_row(["sonnet", "opus"], "opus")}
    root = fx.vault({"classes": {"critic": {"model": {"options": ["haiku", "sonnet"], "default": "sonnet"}}}}, table=two_pins, scripts=both)
    code, found, out = lane_tiers(root, "critic")
    suite.leg("a freed class still takes a pin it lists, through lane.py",
              code == 0 and (found["critic"]["top"], found["critic"]["cheap"]) == ("sonnet", "sonnet"), out[-300:])
    faulty = dict(TABLE, classes=dict(TABLE["classes"], critic=class_row(["sonnet"], "sonnet")))
    root = fx.vault(table=faulty, scripts=both)
    code, found, out = lane_tiers(root, "critic")
    suite.leg("the table alone leaving the model out stops lane.py, exit 2",
              code == 2 and "does not list among its model" in out, out[-300:])


def bytes_legs(suite, fx):
    print("== the read paths write nothing")
    root = fx.vault({"rules": RULES, "classes": {"my-helper": OWN_ROW}}, own_definition=True)
    before = manifest(root)
    resolved = fx.resolve(root, "writer")
    runs = [fx.check(root), fx.throttle(root, "show"), fx.throttle(root, "check"), (resolved[0], resolved[2])]
    suite.leg("each read exits 0", [code for code, _out in runs] == [0, 0, 0, 0], str([out[-200:] for _c, out in runs]))
    suite.leg("the fixture is byte-identical after them", manifest(root) == before)
    target = fx.table(root)
    mode = os.stat(target).st_mode
    with open(target, "ab") as handle:
        handle.write(b" ")
    os.chmod(target, mode)
    suite.leg("control: a byte changed under the same mode, in the same folder, is caught", manifest(root) != before)


def main():
    parser = argparse.ArgumentParser(description="the routing overlay's suite")
    parser.add_argument("--delegate", default=HERE)
    parser.add_argument("--lane")
    parser.add_argument("--review")
    parser.add_argument("--flat", action="store_true")
    parser.add_argument("--require-lane", action="store_true")
    opts = parser.parse_args()
    opts.delegate = os.path.abspath(opts.delegate)
    opts.lane = os.path.abspath(opts.lane or os.path.join(opts.delegate, "lane.py"))
    opts.review = os.path.abspath(opts.review or os.path.join(
        opts.delegate, "..", "deep-lint", "spawn-record-review.py"))
    for path in (os.path.join(opts.delegate, "throttle.py"), opts.review):
        if not os.path.isfile(path):
            print("PROBE FAILED: no script to test at %s" % path)
            return 2
    work = tempfile.mkdtemp(prefix="routing-layers-")
    suite = Suite()
    try:
        fx = Fixtures(work, opts)
        merge_legs(suite, fx)
        refusal_legs(suite, fx)
        nested_legs(suite, fx)
        preset_legs(suite, fx)
        own_class_legs(suite, fx)
        lazy_legs(suite, fx)
        review_legs(suite, fx)
        if fx_lane_ready(fx):
            lane_legs(suite, fx)
        elif opts.require_lane:
            suite.leg("lane.py carries the overlay branch", False, opts.lane)
        else:
            print("UNRUN lane legs: %s has no overlay branch yet; --require-lane fails on this" % opts.lane)
        bytes_legs(suite, fx)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return suite.finish()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, subprocess.TimeoutExpired, decimal.InvalidOperation) as exc:
        print("PROBE FAILED: %s" % exc)
        sys.exit(2)
