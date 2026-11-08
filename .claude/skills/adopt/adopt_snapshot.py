#!/usr/bin/env python3
"""Read-only complete configuration snapshots and exact declaration comparison."""
import argparse
import os
from pathlib import Path
import stat
import sys
from adopt_data import (Problem, Finding, require, sha, digest, decode, encoded,
                        read_json, now, timestamp, cli_error, shape, HASH, INT)


def within(path, roots):
    return any(path == root or root in path.parents for root in roots)


def accessible(path, access):
    flags = {"read": os.R_OK, "write": os.W_OK, "search": os.X_OK}
    try:
        if os.access in os.supports_effective_ids:
            return os.access(path, flags[access], effective_ids=True)
        require(os.getuid() == os.geteuid() and os.getgid() == os.getegid(),
                "effective-principal access check unsupported")
        return os.access(path, flags[access])
    except (OSError, NotImplementedError) as exc:
        raise Problem(f"access {path}: {exc}") from exc


def lookup(path):
    """Walk named ancestors. Only an accessible-parent ENOENT is absence."""
    path = Path(path).absolute()
    current = Path(path.anchor)
    for part in path.parts[1:]:
        require(accessible(current, "search"), f"cannot search parent {current}")
        child = current / part
        try:
            info = child.lstat()
        except FileNotFoundError:
            return None, {"parent": str(current.resolve(strict=True)), "component": part}
        except OSError as exc:
            raise Problem(f"lookup {child}: {exc}") from exc
        current = child
    return info, None


def inventory(root, allowed_roots=()):
    """No ignore rules. Symlink targets need an explicit allowed root."""
    root = Path(root).absolute()
    roots = [Path(p).resolve(strict=True) for p in allowed_roots]
    roots.append(root)
    entries, stable = {}, {}
    def walk(path, key, ancestors):
        try:
            info = path.lstat()
            signature = (info.st_dev, info.st_ino, info.st_mode, info.st_size,
                         info.st_mtime_ns, info.st_ctime_ns)
            mode = stat.S_IMODE(info.st_mode)
            stable[key] = signature
            entry = {"logical": str(path), "resolved": str(path.resolve(strict=True)),
                     "mode": mode}
            if stat.S_ISLNK(info.st_mode):
                text = os.readlink(path)
                target = path.resolve(strict=True)
                require(within(target, roots), f"external symlink target not granted: {path}")
                require(target not in ancestors, f"symlink cycle: {path}")
                entries[key] = {**entry, "type": "symlink", "link_text": text}
                walk(target, key + "/@target", ancestors + [target])
            elif stat.S_ISDIR(info.st_mode):
                require(accessible(path, "read") and accessible(path, "search"),
                        f"cannot enumerate {path}")
                names = sorted(os.listdir(path))
                entries[key] = {**entry, "type": "directory", "children": names}
                for name in names:
                    walk(path / name, key + "/" + name, ancestors + [path.resolve(strict=True)])
            elif stat.S_ISREG(info.st_mode):
                require(accessible(path, "read"), f"cannot read {path}")
                with path.open("rb") as stream:
                    opened = os.fstat(stream.fileno())
                    require((opened.st_dev, opened.st_ino) == signature[:2], f"retargeted {path}")
                    raw = stream.read()
                    after = os.fstat(stream.fileno())
                    require((after.st_mode, after.st_size, after.st_mtime_ns, after.st_ctime_ns) ==
                            (info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns),
                            f"unstable read {path}")
                entries[key] = {**entry, "type": "file", "sha256": sha(raw), "size": len(raw)}
            else:
                raise Problem(f"unsupported special file {path}")
            end = path.lstat()
            require(signature == (end.st_dev, end.st_ino, end.st_mode, end.st_size,
                                  end.st_mtime_ns, end.st_ctime_ns), f"unstable scan {path}")
        except (OSError, RuntimeError) as exc:
            raise Problem(f"scan {path}: {exc}") from exc
    info, absent = lookup(root)
    if info is None:
        return {".": {"logical": str(root), "type": "absent", **absent}}, {}
    require(within(root.resolve(strict=True), roots), f"resolved root target not granted: {root}")
    walk(root, ".", [])
    return entries, stable


def tree_hash(path, allowed_roots=()):
    first, identities = inventory(path, allowed_roots)
    second, later = inventory(path, allowed_roots)
    require(first == second and identities == later, f"unstable tree {path}")
    # Absolute placement is separately bound by the resource identity.
    content = {k: {f: v for f, v in e.items() if f not in ("logical", "resolved")}
               for k, e in first.items()}
    return digest(content)


def pointer_nodes(value, pointer=""):
    if isinstance(value, dict):
        out = {pointer: {"container": "object", "keys": sorted(value)}}
        for k, v in value.items():
            out.update(pointer_nodes(v, pointer + "/" + k.replace("~", "~0").replace("/", "~1")))
        return out
    if isinstance(value, list):
        out = {pointer: {"container": "array", "length": len(value)}}
        for i, v in enumerate(value):
            out.update(pointer_nodes(v, pointer + "/" + str(i)))
        return out
    return {pointer: {"value": value}}


def typed_equal(left, right):
    """Compare JSON nodes without Python's boolean/number equivalence."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return (left.keys() == right.keys() and
                all(typed_equal(left[key], right[key]) for key in left))
    if type(left) is list:
        return (len(left) == len(right) and
                all(typed_equal(a, b) for a, b in zip(left, right)))
    return left == right


def controls():
    planted = difference({"x": {"value": 1}}, {"x": {"value": 2}})
    typed = difference({"true": {"value": True}, "false": {"value": False}},
                       {"true": {"value": 1}, "false": {"value": 0}})
    empty = difference({}, {})
    require(len(planted) == 1 and len(typed) == 2 and not empty,
            "comparison control failed")
    return len(planted) + len(typed)


def snapshot(home, allowed_roots=()):
    home = Path(home).resolve(strict=True)
    roots = [home / ".claude.json", home / ".claude/settings.json", home / ".claude/skills"]
    scope = {"home": str(home), "roots": [str(p) for p in roots],
             "allowed_roots": sorted(str(Path(p).resolve(strict=True)) for p in allowed_roots)}
    start = now()
    def scan():
        entries, identities = {}, {}
        for root in roots:
            items, stable = inventory(root, allowed_roots)
            for key, entry in items.items():
                address = str(root) + ("" if key == "." else key[1:])
                entries[address] = entry
                if key in stable:
                    identities[address] = stable[key]
            if root != roots[-1] and items["."]["type"] != "absent":
                parsed = decode(root.read_bytes())
                require(isinstance(parsed, dict), f"configuration root is not an object: {root}")
                for pointer, node in pointer_nodes(parsed).items():
                    entries[str(root) + "#" + pointer] = {"type": "json", **node}
        return entries, identities
    first, identities = scan()
    second, later = scan()
    require(typed_equal(first, second) and identities == later,
            "configuration changed during snapshot")
    result = {"schema_version": 1, "complete": True, "scope": scope,
              "scope_sha256": digest(scope), "exclusion_policy_sha256": digest([]),
              "started_at": start, "ended_at": now(), "state": first,
              "state_sha256": digest(first), "control_hits": controls()}
    validate_snapshot(result)
    return result


def validate_snapshot(value):
    keys = {"schema_version", "complete", "scope", "scope_sha256", "exclusion_policy_sha256",
            "started_at", "ended_at", "state", "state_sha256", "control_hits"}
    require(type(value) is dict and set(value) == keys, "malformed snapshot shape")
    require(type(value["schema_version"]) is int and value["schema_version"] == 1
            and value["complete"] is True, "incomplete or incompatible snapshot")
    require(value["exclusion_policy_sha256"] == digest([]), "unsupported snapshot exclusions")
    require(type(value["state"]) is dict and bool(value["state"]), "empty snapshot state")
    require(type(value["scope"]) is dict and set(value["scope"]) ==
            {"home", "roots", "allowed_roots"}, "malformed snapshot scope")
    home = Path(value["scope"]["home"])
    require(home.is_absolute() and value["scope"]["roots"] ==
            [str(home / p) for p in (".claude.json", ".claude/settings.json", ".claude/skills")],
            "snapshot scope does not cover full configuration domain")
    require(all(p in value["state"] for p in value["scope"]["roots"]), "snapshot root omitted")
    for root in value["scope"]["roots"][:2]:
        if value["state"][root]["type"] != "absent":
            require(root + "#" in value["state"] and value["state"][root + "#"].get("container") == "object",
                    "parsed configuration root omitted")
    for address, entry in value["state"].items():
        require(type(entry) is dict and "type" in entry, f"malformed snapshot entry {address}")
        kind = entry["type"]
        common = {"logical", "resolved", "mode", "type"}
        shapes = {"file": common | {"sha256", "size"}, "directory": common | {"children"},
                  "symlink": common | {"link_text"}, "absent": {"logical", "type", "parent", "component"}}
        if kind == "json":
            require(set(entry) in ({"type", "value"}, {"type", "container", "keys"},
                                  {"type", "container", "length"}), "malformed JSON node")
            if "keys" in entry:
                require(entry["container"] == "object" and type(entry["keys"]) is list and
                        all(type(k) is str for k in entry["keys"]) and
                        entry["keys"] == sorted(set(entry["keys"])), "invalid JSON object inventory")
                require(all(address + "/" + k.replace("~", "~0").replace("/", "~1") in value["state"]
                            for k in entry["keys"]), "omitted JSON object child")
            elif "length" in entry:
                require(entry["container"] == "array" and type(entry["length"]) is int and
                        entry["length"] >= 0, "invalid JSON array inventory")
                require(all(address + "/" + str(i) in value["state"] for i in range(entry["length"])),
                        "omitted JSON array child")
            else:
                require(not isinstance(entry["value"], (dict, list)), "container disguised as JSON leaf")
        else:
            require(kind in shapes and set(entry) == shapes[kind], "malformed inventory entry")
            if kind == "directory":
                require(entry["children"] == sorted(set(entry["children"])), "invalid child inventory")
                # Symlink targets are inventoried under the alias address.
                require(all(address.rstrip("/") + "/" + n in value["state"]
                            for n in entry["children"]), "incomplete child inventory")
            if kind == "symlink":
                target = value["state"].get(address + "/@target")
                # The scanner resolves the link fully before walking its target.
                # Directory children and nested links then face the same checks.
                require(type(target) is dict and target.get("type") in ("file", "directory") and
                        target.get("logical") == entry["resolved"] and
                        target.get("resolved") == entry["resolved"],
                        "incomplete symlink target inventory: " + address)
            if kind == "file":
                shape(entry["sha256"], HASH)
                shape(entry["size"], INT)
            if kind != "absent":
                shape(entry["mode"], INT)
                require(entry["mode"] <= 0o7777, "invalid mode")
        require(any(address == r or address.startswith(r + "/") or address.startswith(r + "#")
                    for r in value["scope"]["roots"]), "entry outside snapshot scope")
    require(value["scope_sha256"] == digest(value["scope"]) and
            value["state_sha256"] == digest(value["state"]), "snapshot digest mismatch")
    require(timestamp(value["started_at"]) <= timestamp(value["ended_at"]),
            "snapshot chronology invalid")
    require(type(value["control_hits"]) is int and value["control_hits"] > 0,
            "snapshot control failed")
    return value


def difference(before, after):
    changes = []
    for address in sorted(set(before) | set(after)):
        old, new = before.get(address), after.get(address)
        if not typed_equal(old, new):
            changes.append({"address": address,
                            "operation": "add" if address not in before else
                            "remove" if address not in after else "change",
                            "old": old, "new": new})
    return changes


def changes(before, after):
    validate_snapshot(before)
    validate_snapshot(after)
    require(before["scope"] == after["scope"], "snapshot scope mismatch")
    for root in before["scope"]["roots"]:
        old, new = before["state"][root], after["state"][root]
        if old["type"] != "absent" and new["type"] != "absent":
            require(old["resolved"] == new["resolved"], "snapshot root identity changed: " + root)
    require(timestamp(before["ended_at"]) <= timestamp(after["started_at"]),
            "snapshot interval is reversed/overlapping")
    return difference(before["state"], after["state"])


def compare(before, after, declared):
    actual = changes(before, after)
    require(type(declared) is list, "declaration must be an array")
    for item in declared:
        require(type(item) is dict and set(item) == {"address", "operation", "old", "new"} and
                item["operation"] in ("add", "remove", "change"), "malformed exact declaration")
    require(len({digest(x) for x in declared}) == len(declared), "duplicate declaration")
    unexpected = [x for x in actual if not any(typed_equal(x, y) for y in declared)]
    unobserved = [x for x in declared if not any(typed_equal(x, y) for y in actual)]
    return {"observed": len(actual), "declared": len(declared), "unexpected": unexpected,
            "unobserved": unobserved, "findings": len(unexpected) + len(unobserved),
            "control_hits": controls()}


def main():
    from adopt_data import ProbeParser
    parser = ProbeParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("snapshot")
    scan.add_argument("--home", required=True)
    scan.add_argument("--allow-root", action="append", default=[])
    diff = sub.add_parser("compare")
    for key in ("before", "after", "declaration"):
        diff.add_argument("--" + key, required=True)
    args = parser.parse_args()
    try:
        if args.command == "snapshot":
            print(encoded(snapshot(args.home, args.allow_root)).decode(), end="")
            return 0
        result = compare(read_json(args.before), read_json(args.after), read_json(args.declaration))
        print(encoded(result).decode(), end="")
        return 1 if result["findings"] else 0
    except (Problem, OSError, ValueError, TypeError, KeyError, IndexError, RuntimeError) as exc:
        return cli_error(exc)


if __name__ == "__main__":
    sys.exit(main())
