#!/usr/bin/env python3
"""Read-only row-bound resource checks; never executes an installed programme."""
import os
from pathlib import Path
import stat
import uuid
from adopt_data import (Problem, Finding, require, digest, sha, decode, read_json,
                        index, expansion, operational_definition, proof_tuples, PURE_CHECKS, now, shape, obj,
                        ref, S, BOOL, HASH, enum, arr)
from adopt_snapshot import tree_hash, accessible, within


def pointer(value, path):
    for part in path.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        try:
            value = value[int(part)] if isinstance(value, list) else value[part]
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise Finding("missing pointer " + path) from exc
    return value


def skill_header(text):
    lines = text.splitlines()
    require(lines and lines[0] == "---" and "---" in lines[1:], "skill/carrier frontmatter missing", Finding)
    end = lines.index("---", 1)
    fields = {}
    for line in lines[1:end]:
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            require(key not in fields, "duplicate skill frontmatter key", Finding)
            fields[key] = value.strip().strip('"').strip("'")
    return fields


def evidence_record(doc, evidence_id, ctx, subject=None):
    """Read an authentic outcome, including failure; this grants no proof."""
    records = index(doc, "evidence")
    require(evidence_id in records, "missing evidence " + str(evidence_id), Finding)
    record = records[evidence_id]
    path = ctx.locate(record["artefact"]["locator"])
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise Problem(f"evidence {path}: {exc}") from exc
    require(sha(raw) == record["artefact"]["sha256"], "stale artefact " + evidence_id, Finding)
    body = decode(raw)
    shape(body, obj({"subject": ref("subject"), "result": enum("pass", "fail", "unknown"),
                     "observation_sha256": HASH, "positive_control": BOOL,
                     "negative_control": BOOL, "criterion": S, "output": S,
                     "human_judge": S, "task": ref("task"),
                     "verdict": enum("supports", "does-not-support", "unknown"),
                     "suggestion": S, "accepted_uncertainties": arr(
                         enum("missing-claim", "poor-use", "old-date", "unknown-date"), unique=True)},
                     ("observation_sha256", "positive_control", "negative_control", "criterion",
                      "output", "human_judge", "task", "verdict", "suggestion", "accepted_uncertainties")))
    require(body["subject"] == record["subject"] and body["result"] == record["result"],
            "artefact subject/result mismatch", Finding)
    require(subject is None or subject == record["subject"], "evidence subject mismatch", Finding)
    return record, body


def evidence_body(doc, evidence_id, ctx, subject=None):
    record, body = evidence_record(doc, evidence_id, ctx, subject)
    require(record["result"] == "pass", "evidence did not pass: " + evidence_id, Finding)
    return record, body


def row_subject(doc, row, binding, position, check):
    return {"type": "resource-check", "register_id": doc["register_id"], "row_id": row["id"],
            "definition_sha256": digest(operational_definition(doc, row)),
            "field_pointer": f"/bindings/{position}/resource_definition",
            "resource_id": binding["resource_id"],
            "resource_definition_sha256": digest(binding["resource_definition"]), "check_id": check}


def observation(doc, row, resource, ctx):
    kind, expected = resource["type"], resource["expected"]
    if kind == "hosted-capability":
        return {"type": "hosted", "capability_id": resource["locator"]["capability_id"],
                "principal": expected["principal"], "evidence_subject": digest(resource)}
    path = ctx.locate(resource["locator"])
    try:
        logical = path.lstat()
        resolved = path.resolve(strict=True)
        info = path.stat()
        if kind == "workspace-directory":
            require(stat.S_ISDIR(info.st_mode), f"workspace kind {path}", Finding)
            results = [{"access": a, "allowed": accessible(path, a)}
                       for a in expected["required_access"]]
            require(all(r["allowed"] for r in results), f"workspace access {path}", Finding)
            return {"type": "workspace", "logical_root": str(path), "resolved_root": str(resolved),
                    "object_identity": {"device": info.st_dev, "inode": info.st_ino},
                    "kind": "directory", "principal": os.geteuid(),
                    "required_access_results": results, "scope": expected["scope"]}
        identity = {"logical": str(path), "resolved": str(resolved),
                    "device": info.st_dev, "inode": info.st_ino,
                    "kind": "directory" if stat.S_ISDIR(info.st_mode) else "file",
                    "mode": stat.S_IMODE(info.st_mode)}
        require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode),
                f"resource kind {path}", Finding)
        if kind == "file":
            require(stat.S_ISREG(info.st_mode), f"file resource is not a file: {path}", Finding)
        elif kind == "directory-tree":
            require(stat.S_ISDIR(info.st_mode), f"directory-tree resource is not a directory: {path}", Finding)
        allowed = [ctx.locate(r["locator"]) for r in doc["resources"]
                   if r["locator"]["root"] != "hosted"]
        # Missing resource paths must not suppress failed lookup errors.
        from adopt_snapshot import lookup
        allowed = [p for p in allowed if lookup(p)[0] is not None]
        if stat.S_ISDIR(info.st_mode):
            hashed = tree_hash(path, allowed)
        else:
            require(accessible(path, "read"), f"resource unreadable {path}")
            hashed = sha(path.read_bytes())
        if "sha256" in expected:
            require(hashed == expected["sha256"], f"content mismatch {resource['id']}", Finding)
        resources = index(doc, "resources")
        if kind == "executable":
            require(stat.S_ISREG(info.st_mode) and accessible(path, "search"),
                    f"executable unusable {path}", Finding)
            require(expected["version_argv"][0] == str(path), "version command names another binary", Finding)
        elif kind == "skill-tree":
            require(stat.S_ISDIR(info.st_mode), "skill root is not a directory", Finding)
            for rel in [expected["entry"]] + expected["references"]:
                require(not Path(rel).is_absolute() and ".." not in Path(rel).parts, "skill reference escapes root")
                child = path / rel
                require(within(child.resolve(strict=True), [resolved]),
                        "skill reference target escapes root")
                child.read_bytes().decode("utf-8-sig")
            carrier = resources.get(expected["carrier_id"])
            require(carrier and carrier["type"] == "carrier" and
                    carrier["expected"]["target_resource_id"] == resource["id"], "skill/carrier binding mismatch")
            fields = skill_header((path / "SKILL.md").read_bytes().decode("utf-8-sig"))
            require(fields.get("name") == carrier["expected"]["skill_name"], "skill name differs from carrier", Finding)
        elif kind == "carrier":
            target = ctx.locate(resources[expected["target_resource_id"]]["locator"]).resolve(strict=True)
            if expected["kind"] == "symlink":
                require(stat.S_ISLNK(logical.st_mode) and resolved == target and
                        expected["level"] == "auto", "carrier symlink mismatch", Finding)
            else:
                text = (path / "SKILL.md").read_bytes().decode("utf-8-sig")
                fields = skill_header(text)
                require(fields.get("name") == expected["skill_name"], "wrapper name mismatch", Finding)
                require((path / "upstream").is_symlink() and
                        (path / "upstream").resolve(strict=True) == target, "wrapper target mismatch", Finding)
                require(expected["declaration"] and expected["declaration"] in text,
                        "wrapper declaration mismatch", Finding)
                if expected["level"] == "by-name":
                    require(fields.get("disable-model-invocation") == "true", "by-name carrier visible", Finding)
        elif kind == "server-config":
            require(resolved not in ((ctx.home / ".claude.json").resolve(),
                                     (ctx.home / ".claude/settings.json").resolve()),
                    "server registration cannot use global configuration", Finding)
            raw = path.read_bytes()
            if expected["format"] == "json":
                config = decode(raw)
                servers = config.get("mcpServers", {})
            else:
                try:
                    import tomllib
                except ImportError as exc:
                    raise Problem("TOML support unavailable") from exc
                servers = tomllib.loads(raw.decode("utf-8-sig")).get("mcp_servers", {})
            server = servers.get(expected["server_id"])
            executable = resources[expected["executable_resource_id"]]
            require(executable["type"] == "executable", "server executable resource type")
            launch = {"command": str(ctx.locate(executable["locator"])),
                      "args": expected["arguments"],
                      "env": {x["name"]: x["value"] for x in expected["environment"]}}
            require(type(server) is dict and all(type(server.get(k)) is type(v) and server[k] == v
                    for k, v in launch.items()), "server launch definition mismatch", Finding)
        elif kind == "plugin-enable":
            value = pointer(decode(path.read_bytes()), expected["pointer"])
            require(value is True and expected["pointer"].split("/")[-1].replace("~1", "/").replace("~0", "~")
                    == expected["plugin_id"], "plugin is not exactly enabled", Finding)
            inspected = resources[expected["inspection_resource_id"]]
            require(inspected["expected"].get("sha256") == expected["inspected_tree_sha256"],
                    "plugin inspection tree mismatch", Finding)
            from adopt_snapshot import inventory
            inspected_path = ctx.locate(inspected["locator"])
            entries, _ = inventory(inspected_path, allowed)
            hooks = [e for e in entries.values() if e["type"] == "file" and
                     Path(e["logical"]).name == "hooks.json"]
            require(bool(hooks) == expected["hooks_present"], "plugin hook inspection differs", Finding)
            for hook in hooks:
                require(isinstance(decode(Path(hook["logical"]).read_bytes()), dict), "malformed plugin hooks")
            skill_roots = {str(Path(e["resolved"]).parent) for e in entries.values()
                           if e["type"] == "file" and Path(e["logical"]).name == "SKILL.md"}
            declared = [b["resource_definition"] for b in operational_definition(doc, row)["bindings"]] if row else doc["resources"]
            declared_skills = {str(ctx.locate(r["locator"]).resolve(strict=True))
                               for r in declared if r["type"] == "skill-tree"}
            require(skill_roots <= declared_skills, "plugin skill omitted from qualification closure", Finding)
        elif kind == "class-binding":
            definition = resources[expected["definition_resource_id"]]
            require(definition["type"] == "file", "class definition is not a file", Finding)
            ctx.locate(definition["locator"]).read_bytes().decode("utf-8-sig")
            config = decode(path.read_bytes())
            require(config.get(expected["class_id"]) ==
                    {"definition_resource_id": expected["definition_resource_id"],
                     "required_resource_ids": expected["required_resource_ids"]},
                    "class routing mismatch", Finding)
        if "pin_sha256" in expected:
            owner = resource["owner"]
            require(owner["type"] == "installation" and
                    digest(index(doc, "installations")[owner["id"]]["pin"]) == expected["pin_sha256"],
                    "resource pin identity mismatch", Finding)
        return {"type": "content", "identity": identity, "sha256": hashed}
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        raise Problem(f"resource {resource['id']} at {path}: {exc}") from exc


def blocked(doc, row, ctx):
    if row.get("maintenance_id"):
        raise Finding("MAINTENANCE " + row["maintenance_id"])
    if row["lifecycle"]["state"] == "legacy-recorded":
        return
    for hold in doc["maintenance"]:
        for binding in expansion(doc, row)["bindings"]:
            r = binding["resource_definition"]
            if r["locator"]["root"] == "hosted":
                continue
            path = ctx.locate(r["locator"]).resolve()
            for scope in map(Path, hold["mutation_scope"]):
                if overlaps(path, scope):
                    raise Finding("MAINTENANCE " + hold["id"])


def overlaps(a, b):
    a, b = Path(a).resolve(), Path(b).resolve()
    if a == b or a in b.parents or b in a.parents:
        return True
    try:
        return os.path.samestat(a.stat(), b.stat())
    except FileNotFoundError:
        return False


def footprint_check(doc, ctx):
    files = [ctx.data, ctx.page, ctx.receipt, ctx.pending, ctx.lock, ctx.guard]
    trees = [ctx.state, ctx.locks]
    for r in doc["resources"]:
        if r["type"] in ("workspace-directory", "hosted-capability"):
            continue
        path = ctx.locate(r["locator"]).resolve()
        tree = r["type"] in ("directory-tree", "skill-tree", "carrier")
        for target in files + trees:
            require(not (overlaps(path, target) if tree or target in trees else path == target.resolve()
                         or (path.exists() and target.exists() and os.path.samestat(path.stat(), target.stat()))),
                    "immutable proof overlaps writer footprint: " + r["id"], Finding)
        if tree:
            require(not any(overlaps(path, p.parent) for p in files),
                    "immutable tree overlaps temporary-write parent: " + r["id"], Finding)
            # An alias nested inside a tree can reach a writer destination too.
            from adopt_snapshot import inventory, lookup
            if lookup(path)[0] is not None:
                allowed = [ctx.locate(x["locator"]) for x in doc["resources"]
                           if x["locator"]["root"] != "hosted" and
                           lookup(ctx.locate(x["locator"]))[0] is not None]
                entries, _ = inventory(path, allowed)
                for entry in entries.values():
                    if entry["type"] not in ("file", "symlink"):
                        continue
                    target_path = Path(entry["resolved"])
                    require(not any(overlaps(target_path, f) for f in files + trees),
                            "immutable alias overlaps writer footprint: " + r["id"], Finding)


def prove(doc, row, ctx, allow_reserved=False):
    if not allow_reserved:
        blocked(doc, row, ctx)
    expanded = expansion(doc, row)
    types = {b["resource_definition"]["type"] for b in expanded["bindings"]}
    minima = {"skill": {"skill-tree", "carrier"}, "cli": {"executable"},
              "tool-server": {"executable", "server-config"}, "plugin": {"plugin-enable"}}
    require(minima.get(row["kind"], set()) <= types, "missing kind minimum for " + row["id"], Finding)
    require(any(r["status"] == "implemented" for r in row["routes"]) and bool(types),
            "no implemented managed capability", Finding)
    checks = []
    for i, binding in enumerate(expanded["bindings"]):
        resource = binding["resource_definition"]
        observed = observation(doc, row, resource, ctx)
        for check in resource["check_ids"]:
            item = {"row_id": row["id"], "field_pointer": f"/bindings/{i}/resource_definition",
                    "resource_id": resource["id"], "resource_definition_sha256": digest(resource),
                    "observation": observed, "check_id": check, "observed_at": now(), "result": "pass"}
            if check not in PURE_CHECKS:
                subject = row_subject(doc, row, binding, i, check)
                matching = [e for e in doc["evidence"] if e["subject"] == subject and
                            e["id"] in row["acceptance"]["evidence_refs"]]
                require(len(matching) == 1, "missing/duplicate row-bound evidence " + str(subject), Finding)
                record, body = evidence_body(doc, matching[0]["id"], ctx, subject)
                require(record["kind"] in ("scripted", "human") and
                        body.get("observation_sha256") == digest(observed) and
                        body.get("positive_control") is True and body.get("negative_control") is True and
                        body.get("criterion") == row["acceptance"]["criterion"],
                        "unusable acceptance evidence " + record["id"], Finding)
                if check == "executable-version":
                    require(body.get("output") == resource["expected"]["version"],
                            "wrong version output", Finding)
                if row["acceptance"]["human_required"]:
                    require(record["kind"] == "human" and body.get("human_judge"),
                            "human judgement missing", Finding)
                item["evidence_ref"] = record["id"]
            checks.append(item)
    require(set(c["check_id"] for c in checks) >= set(row["acceptance"]["check_ids"]),
            "acceptance check not in resource closure", Finding)
    return checks


def stable_checks(checks):
    return [{k: v for k, v in c.items() if k != "observed_at"} for c in checks]


def activate_record(doc, row, ctx, decisions=None):
    from adopt_freshness import evaluate_targets
    checks = prove(doc, row, ctx)
    evaluations = evaluate_targets(doc, row, ctx, decisions=decisions)
    import copy
    bound_row = copy.deepcopy(row)
    bound_row["lifecycle"]["activation"] = {"freshness_evaluation": evaluations}
    return {"id": str(uuid.uuid4()), "register_id": doc["register_id"], "row_id": row["id"],
            "definition_sha256": digest(expansion(doc, bound_row)), "verified_at": now(),
            "checks": checks, "freshness_evaluation": evaluations,
            "evidence_refs": sorted({c["evidence_ref"] for c in checks if "evidence_ref" in c})}


def recheck(doc, row, ctx):
    checks = prove(doc, row, ctx)
    if row["lifecycle"]["state"] == "active":
        require(stable_checks(checks) == stable_checks(row["lifecycle"]["activation"]["checks"]),
                "current resources differ from activation", Finding)
        from adopt_freshness import evaluate_targets
        require(evaluate_targets(doc, row, ctx, decisions=row["lifecycle"]["activation"]["freshness_evaluation"]) == row["lifecycle"]["activation"]["freshness_evaluation"],
                "current freshness differs from activation", Finding)
    return checks
