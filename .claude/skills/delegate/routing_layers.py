#!/usr/bin/env python3
"""routing_layers.py — the routing table and a user's own overlay, read as one record.

  routing_layers.py --check TABLE   merge, validate, print one line; writes nothing

`.claude/skills/delegate/routing.json` is the shipped table, core in a user's copy. A user's own
choices sit in `.claude/routing.local.json`, the overlay, in the user's layer. The overlay is found
three levels above the table file, which also holds for a table named by `--routing`. A reader of
the classes imports this module only in the branch that finds an overlay, so a script copied on its
own, with no overlay, runs as it did without this file.

What an overlay holds, and how each part merges:
  - `rules`: rows appended after the table's own, in the overlay's order. The agent reads them; no
    script does.
  - `classes.<name>`: an override of a shipped class. An object merges key by key, at any depth; a
    list or a single value replaces what the table holds, so `options` is the whole new list.
  - `classes.my-<name>`: a class of the user's own, a whole row, so that a helper of their own can
    be routed. The prefix is the user's name space: no release uses it.
  - `_`: a note, which nothing reads.

A user's accounts decide what can be routed, so either kind of class may leave out a model that the
table's `preset_model` names. Its `model.options` then exclude that model: under that preset the
class picks from its own options by the throttle's table, and every other class keeps the preset's
model. The merged record lists such classes under `preset_free`, which exists only in memory: no
file holds it and an overlay cannot name it.

The merged record goes through the same validation as the table (`validate_routing` in
throttle.py), and `cost` and `harness`, which that validation leaves alone, are held to the same
standard here. An overlay that cannot be read, is not JSON, names an unknown key at any depth or
fails either check stops with `Broken`, and the caller prints PROBE FAILED and exits 2. It never
falls back to the shipped table, which would run a seat on a model the user ruled out.

A fold of cost figures never reads the merged record: writing it back would copy one file's rows
into the other. `fold_source` gives the fold the one file it may write in a user's copy.

Exit 0 the merged record is valid, or there is no overlay. Exit 2 PROBE FAILED.
"""
import decimal
import json
import math
import os
import re
import sys

OVERLAY_NAME = "routing.local.json"
CORE_LIST_NAME = "core-paths"
OWN_PREFIX = "my-"
PRESET_FREE = "preset_free"
OVERLAY_KEYS = ("_", "rules", "classes")
RULE_KEYS = ("from", "layer", "class", "text")
ROW_KEYS = ("layer", "model", "effort", "grants", "writes", "tools", "skills", "mcp", "cache",
            "gate", "dated", "cost", "harness")
BLOCK_KEYS = {"model": ("options", "default"), "effort": ("options", "default"),
              "grants": ("default", "extras"), "skills": ("default", "extras"),
              "mcp": ("default", "grantable"),
              "cost": ("soft_usd", "usual_usd", "n", "window", "source"),
              "harness": ("codex",),
              "harness.codex": ("model", "effort", "note"),
              "harness.codex.model": ("options", "default"),
              "harness.codex.effort": ("options", "default")}
EMPTY_OVERLAY = '{\n  "classes": {}\n}\n'


class Broken(Exception):
    """A premise of the overlay does not hold; the message is the reason."""


def layers_home(table_path):
    """The folder three levels above the table file: `.claude` in a vault."""
    path = os.path.abspath(table_path)
    for _level in range(3):
        path = os.path.dirname(path)
    return path


def overlay_path(table_path):
    return os.path.join(layers_home(table_path), OVERLAY_NAME)


def read_record(path, what, parse_float=float):
    try:
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle, parse_float=parse_float)
    except OSError as exc:
        raise Broken("%s %s is unreadable (%s)" % (what, path, exc.strerror or exc.__class__.__name__))
    except ValueError as exc:
        raise Broken("%s %s is not valid JSON (%s)" % (what, path, exc))
    if not isinstance(record, dict):
        raise Broken("%s %s is not an object" % (what, path))
    return record


def unknown_keys(found, known):
    return sorted(key for key in found if key not in known)


def check_rules(rules, where):
    if not isinstance(rules, list):
        raise Broken("%s: `rules` is not a list" % where)
    for index, row in enumerate(rules):
        if not isinstance(row, dict):
            raise Broken("%s: `rules[%d]` is not an object" % (where, index))
        extra = unknown_keys(row, RULE_KEYS)
        if extra:
            raise Broken("%s: `rules[%d]` names an unknown key: %s (known: %s)"
                         % (where, index, ", ".join(extra), ", ".join(RULE_KEYS)))
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            raise Broken("%s: `rules[%d]` has no `text`" % (where, index))


def check_class(name, row, shipped, where):
    if not isinstance(row, dict):
        raise Broken("%s: `classes.%s` is not an object" % (where, name))
    if name not in shipped and not name.startswith(OWN_PREFIX):
        raise Broken("%s: `classes.%s` names no class of the table (it has: %s); a class of your "
                     "own takes the `%s` prefix" % (where, name, ", ".join(sorted(shipped)), OWN_PREFIX))
    extra = unknown_keys(row, ROW_KEYS)
    if extra:
        raise Broken("%s: `classes.%s` names an unknown key: %s (known: %s)"
                     % (where, name, ", ".join(extra), ", ".join(ROW_KEYS)))
    for field, known in BLOCK_KEYS.items():
        block = row
        for key in field.split("."):
            block = block.get(key) if isinstance(block, dict) else None
        extra = unknown_keys(block, known) if isinstance(block, dict) else []
        if extra:
            raise Broken("%s: `classes.%s.%s` names an unknown key: %s (known: %s)"
                         % (where, name, field, ", ".join(extra), ", ".join(known)))


def check_overlay(overlay, table, where):
    """Each key of the overlay is one this module knows. Shape and membership are the validator's."""
    extra = unknown_keys(overlay, OVERLAY_KEYS)
    if extra:
        raise Broken("%s: unknown key: %s (known: %s)" % (where, ", ".join(extra), ", ".join(OVERLAY_KEYS)))
    check_rules(overlay.get("rules", []), where)
    classes = overlay.get("classes", {})
    if not isinstance(classes, dict):
        raise Broken("%s: `classes` is not an object" % where)
    if classes and table.get("schema") != 2:
        raise Broken("%s: `classes` overrides need a schema 2 table, and this one is schema %r"
                     % (where, table.get("schema")))
    shipped = table.get("classes") or {}
    for name, row in classes.items():
        check_class(name, row, shipped, where)


def deep_merge(base, over):
    merged = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def preset_free(table, overlay_classes):
    """The classes whose overlay `model.options` leave out a model `preset_model` names. Only the
    overlay can free a class: a shipped row that lacks the model and that no overlay gave options
    stays a broken premise. A malformed block is left for the validation that follows."""
    block = table.get("preset_model")
    pins = [model for name, model in block.items() if name != "_"] if isinstance(block, dict) else []
    free = []
    for name, row in overlay_classes.items():
        given = row.get("model")
        options = given.get("options") if isinstance(given, dict) else None
        if isinstance(options, list) and any(pin not in options for pin in pins):
            free.append(name)
    return free


def merge(table, overlay):
    """The record both files make. `_` stays the table's: an overlay's note is its own."""
    merged = dict(table)
    if "rules" in overlay:
        merged["rules"] = list(table.get("rules", [])) + overlay["rules"]
    if "classes" in overlay:
        merged["classes"] = deep_merge(table.get("classes") or {}, overlay["classes"])
        free = preset_free(table, overlay["classes"])
        if free:
            merged[PRESET_FREE] = free
    return merged


def is_positive(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float, decimal.Decimal))
            and math.isfinite(value) and value > 0)


def check_cost(name, cost, where):
    """lane.py's `class_cost` rule, so that a bad block stops at the check and not at a spawn."""
    if cost is None:
        return
    if not isinstance(cost, dict):
        raise Broken("%s: `classes.%s.cost` is not an object" % (where, name))
    for key in ("soft_usd", "usual_usd"):
        if not is_positive(cost.get(key)):
            raise Broken("%s: `classes.%s.cost.%s` is not a positive number (%r)"
                         % (where, name, key, cost.get(key)))


def check_harness(name, harness, where):
    if not isinstance(harness, dict):
        raise Broken("%s: `classes.%s.harness` is not an object" % (where, name))
    codex = harness.get("codex", {})
    if not isinstance(codex, dict):
        raise Broken("%s: `classes.%s.harness.codex` is not an object" % (where, name))
    for axis in ("model", "effort"):
        if axis not in codex:
            continue
        block = codex[axis]
        if (not isinstance(block, dict) or not isinstance(block.get("options"), list)
                or not block["options"] or block.get("default") not in block["options"]):
            raise Broken("%s: `classes.%s.harness.codex.%s` needs options containing its default"
                         % (where, name, axis))


def validate(merged, where):
    """The table's own validation, from throttle.py beside this file, then the blocks it leaves alone."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    sys.dont_write_bytecode = True   # the import must never leave a __pycache__ in the skill directory
    try:
        import throttle
    except ImportError as exc:
        raise Broken("%s cannot be validated: throttle.py does not import from %s (%s)" % (where, here, exc))
    try:
        throttle.validate_routing(merged, where + " merged over the table")
    except throttle.Probe as exc:
        raise Broken(str(exc))
    for name, row in merged.get("classes", {}).items():
        check_cost(name, row.get("cost"), where)
        check_harness(name, row.get("harness", {}), where)


def load(path, parse_float=float):
    """The table at `path` with its overlay merged and validated, or the table alone where no overlay
    exists. Raises Broken on any fault; the table alone never stands in for a merge that failed."""
    table = read_record(path, "the routing table", parse_float)
    where = overlay_path(path)
    if not os.path.lexists(where):
        return table
    overlay = read_record(where, "the routing overlay", parse_float)
    check_overlay(overlay, table, where)
    merged = merge(table, overlay)
    validate(merged, where)
    return merged


def is_users_copy(table_path):
    """A copy holding the core list: its table is core, so a fold may not write there."""
    return os.path.lexists(os.path.join(layers_home(table_path), CORE_LIST_NAME))


def fold_source(table_path):
    """(path, raw, record) for a fold in a user's copy: the overlay's own path, its text and its own
    rows, with an empty row for each class of the table it lacks, so that the fold can add a `cost`
    there. The fold drops the rows it left empty. Nothing is merged, so a fold can write back only
    what the overlay held and the `cost` blocks it computed."""
    table = read_record(table_path, "the routing table")
    where = overlay_path(table_path)
    if os.path.lexists(where):
        record = read_record(where, "the routing overlay")
        check_overlay(record, table, where)
        with open(where, encoding="utf-8") as handle:
            raw = handle.read()
        if not re.search(r"^[ \t]+\S", raw, re.M):
            raw = EMPTY_OVERLAY   # a one-line overlay has no indent of its own to keep
    else:
        record, raw = {}, EMPTY_OVERLAY
    classes = record.setdefault("classes", {})
    for name in table.get("classes") or {}:
        classes.setdefault(name, {})
    return where, raw, record


def main(argv):
    if len(argv) != 2 or argv[0] != "--check":
        raise Broken("usage: routing_layers.py --check TABLE")
    table_path = argv[1]
    where = overlay_path(table_path)
    if not os.path.lexists(where):
        table = read_record(table_path, "the routing table")
        print("routing layers: no overlay at %s; the table stands alone (%d classes)"
              % (where, len(table.get("classes") or {})))
        return 0
    merged = load(table_path)
    print("routing layers: %s merges cleanly (%d rules rows, %d classes)"
          % (where, len(merged.get("rules", [])), len(merged.get("classes") or {})))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Broken as err:
        print("PROBE FAILED: %s" % err)
        sys.exit(2)
