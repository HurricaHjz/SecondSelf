#!/usr/bin/env python3
"""routing_marks.py — the routing table's core-or-yours marks, read one way by every caller.

  routing_marks.py --check TABLE       report the marks, write nothing
  routing_marks.py --hold-back TABLE   the same check, then take each row marked yours out of TABLE

export_template.sh runs --check on the vault's table before it copies anything, and --hold-back on
the copy it is about to ship; the vault's own table is never rewritten.

What a mark is:
  - The key is `layer`. Its value is `core` (the row ships) or `yours` (the row stays in the vault).
  - A row is an entry of `classes`, or any other top-level entry outside the table's frame. It is an
    object carrying the key; a top-level entry may instead hold several rows, as a list or an object
    of them and nothing else, since an unmarked note beside them could carry a choice of the owner's.
  - The frame is `schema`, `order`, `preset_model` and `_`. Every reader needs them, so they ship and
    carry no mark; throttle.py refuses an unknown key inside `preset_model`.
  - A mark may also sit on a part of a row that ships. That part goes when it is marked yours.

What the public copy must keep:
  - at least one class, since lane.py and throttle.py read the table's classes and throttle.py
    refuses a table with none;
  - each shipping class's `model` and `effort`, the two defaults a lane resolves from;
  - the class of every agent definition: the export ships each definition, and a definition whose
    class is held back reads as UNROUTED to throttle.py and cannot be spawned by lane.py.

Exit 0 every row carries a mark and the public copy keeps its defaults. Exit 2 PROBE FAILED, one line
per fault: a row with no mark, a null or unknown mark, a mark in the frame, a public copy that loses
what it must keep, an unreadable table. A table that fails is left as it was.
"""
import copy
import json
import os
import re
import sys

KEY = "layer"
SHIPS = "core"
STAYS = "yours"
FRAME = ("schema", "order", "preset_model", "_")
REQUIRED_BLOCKS = ("model", "effort", "grants", "skills", "mcp")
LINK = re.compile(r";?\s*\[\[[^\]]+\]\]")   # a rule row's link to a vault page, which does not ship


class Broken(Exception):
    """A premise of the marks does not hold; the message is the reason."""


def marked(node):
    return isinstance(node, dict) and KEY in node


def held(node):
    return marked(node) and node[KEY] == STAYS


def every_mark(node, where=""):
    """(where, value) of each mark in the table, at any depth."""
    if isinstance(node, dict):
        if KEY in node:
            yield where or "the table itself", node[KEY]
        for key, value in node.items():
            yield from every_mark(value, where + "." + key if where else key)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from every_mark(value, "%s[%d]" % (where, index))


def rows_of(table):
    """(rows, unmarked): the (where, node) of each row that carries a mark, and each that does not."""
    rows, unmarked = [], []
    classes = table.get("classes", {})
    if not isinstance(classes, dict):
        raise Broken("`classes` is not an object")
    for name, row in classes.items():
        (rows if marked(row) else unmarked).append(("classes." + name, row))
    for name, entry in table.items():
        if name in FRAME or name == "classes":
            continue
        if marked(entry):
            rows.append((name, entry))
            continue
        if isinstance(entry, list):
            items = [("%s[%d]" % (name, index), value) for index, value in enumerate(entry)]
        elif isinstance(entry, dict):
            items = [("%s.%s" % (name, key), value) for key, value in entry.items()]
        else:
            items = []
        if any(marked(value) for _where, value in items):
            for item in items:
                (rows if marked(item[1]) else unmarked).append(item)
        else:
            unmarked.append((name, entry))
    return rows, unmarked


def hold_back(node):
    """Remove every row marked yours from `node`, at any depth."""
    if isinstance(node, dict):
        for key in [k for k, value in node.items() if held(value)]:
            del node[key]
        for value in node.values():
            hold_back(value)
    elif isinstance(node, list):
        node[:] = [value for value in node if not held(value)]
        for value in node:
            hold_back(value)


def public_table(table):
    """The table a public copy ships: yours rows gone, a shipped rule's link to a vault page gone, and
    a top-level holder they emptied gone too, so that the public copy's own export finds no unmarked
    entry. The vault's own table keeps its links."""
    public = copy.deepcopy(table)
    hold_back(public)
    for row in public.get("rules", []):
        if isinstance(row, dict) and isinstance(row.get("text"), str):
            row["text"] = LINK.sub("", row["text"])
    for name in list(public):
        if name not in FRAME and name != "classes" and public[name] in ({}, []):
            del public[name]
    return public


def faults(table, path):
    """One line for each thing wrong with this table's marks."""
    found = []
    for where, value in every_mark(table):
        if value not in (SHIPS, STAYS):
            found.append('unknown routing mark %r at %s in %s; a mark is "%s": "%s" or "%s": "%s"'
                         % (value, where, path, KEY, SHIPS, KEY, STAYS))
    for name in FRAME:
        for where, _value in every_mark(table.get(name), name):
            found.append("routing mark at %s in %s: the table's frame ships and carries no mark" % (where, path))
    _rows, unmarked = rows_of(table)
    if unmarked:
        found.append('%d routing row(s) carry no mark in %s: %s; give each "%s": "%s" (it ships) or "%s": "%s" (it stays in the vault)'
                     % (len(unmarked), path, ", ".join(where for where, _node in unmarked), KEY, SHIPS, KEY, STAYS))
    if found:
        return found
    classes = table.get("classes", {})
    public = public_table(table)
    kept = public.get("classes", {})
    if not kept:
        found.append("no class would ship from %s: the public copy needs its defaults" % path)
    for name, row in kept.items():
        for axis in REQUIRED_BLOCKS:
            if axis in classes[name] and axis not in row:
                found.append("classes.%s.%s in %s is marked %s: the class would ship without a required block"
                             % (name, axis, path, STAYS))
    agents = os.path.join(os.path.dirname(os.path.abspath(path)), "..", "..", "agents")
    for name in classes:
        if name not in kept and os.path.isfile(os.path.join(agents, name + ".md")):
            found.append("classes.%s in %s is marked %s, but .claude/agents/%s.md ships: the public copy needs that class"
                         % (name, path, STAYS, name))
    return found


def read_table(path):
    try:
        with open(path, encoding="utf-8") as handle:
            table = json.load(handle)
    except (OSError, ValueError) as err:
        raise Broken("cannot read the routing table %s (%s)" % (path, err))
    if not isinstance(table, dict):
        raise Broken("the routing table %s is not an object" % path)
    return table


def main(argv):
    if len(argv) != 2 or argv[0] not in ("--check", "--hold-back"):
        raise Broken("usage: routing_marks.py --check TABLE | --hold-back TABLE")
    mode, path = argv
    table = read_table(path)
    found = faults(table, path)
    if found:
        for line in found:
            print("PROBE FAILED: " + line)
        return 2
    rows, _unmarked = rows_of(table)
    yours = sum(1 for _where, node in rows if held(node))
    print("routing marks: %d row(s), %d core, %d yours" % (len(rows), len(rows) - yours, yours))
    if mode == "--hold-back":
        public = public_table(table)
        if public != table:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(public, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
        going = [where for where, value in every_mark(table) if value == STAYS]
        print("routing rows held back from this copy: %s" % (", ".join(going) or "none"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Broken as err:
        print("PROBE FAILED: %s" % err)
        sys.exit(2)
