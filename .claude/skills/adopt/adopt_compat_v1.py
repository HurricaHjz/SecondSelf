#!/usr/bin/env python3
"""Strict, read-only register contract. JSON: sorted keys, two-space indent, LF.

Hash domains use compact sorted UTF-8 JSON; arrays retain their order. Schema and
layout version 1 identify the first structured format. No third-party packages.
"""
import datetime as dt
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import uuid


from adopt_data import Problem, Finding, Conflict


class ProbeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "PROBE FAILED: " + message + "\n")


def require(ok, message, error=Problem):
    if not ok:
        raise error(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return sha(canonical(value))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       indent=2, allow_nan=False) + "\n").encode("utf-8")


def decode(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "duplicate JSON key: " + key)
            out[key] = value
        return out
    def finite_float(text):
        value = float(text)
        require(math.isfinite(value), "non-finite JSON number: " + text)
        return value
    try:
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs, parse_float=finite_float,
                          parse_constant=lambda x: require(False, "non-finite JSON: " + x))
    except (UnicodeError, ValueError) as exc:
        raise Problem("strict JSON: " + str(exc)) from exc


def read_json(path):
    try:
        return decode(Path(path).read_bytes())
    except OSError as exc:
        raise Problem(f"read {path}: {exc}") from exc


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds")


def timestamp(value):
    require(isinstance(value, str) and re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)", value),
        "invalid RFC 3339 timestamp")
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Problem(str(exc)) from exc


def date(value):
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d\d-\d\d", value),
            "invalid calendar date")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise Problem(str(exc)) from exc


def string(pattern=None, fmt=None):
    out = {"type": "string", "minLength": 1}
    if pattern:
        out["pattern"] = pattern
    if fmt:
        out["format"] = fmt
    return out


TEXT = {"type": "string"}
S = string()
ID = string(r"^[a-z][a-z0-9-]*$")
HASH = string(r"^[a-f0-9]{64}$")
DATE = string(fmt="date")
TIME = string(fmt="date-time")
INT = {"type": "integer", "minimum": 0}
BOOL = {"type": "boolean"}


def enum(*items):
    return {"enum": list(items)}


def arr(item, minimum=0, unique=False):
    return {"type": "array", "items": item, "minItems": minimum, "uniqueItems": unique}


def obj(fields, optional=()):
    return {"type": "object", "properties": fields,
            "required": [k for k in fields if k not in optional],
            "additionalProperties": False}


def union(*shapes):
    return {"oneOf": list(shapes)}


def ref(name):
    return {"$ref": "#/$defs/" + name}


IDS = arr(ID, unique=True)
STRINGS = arr(S, unique=True)
LEVEL = enum("auto", "propose-first", "by-name")
KINDS = ("skill", "tool-server", "cli", "plugin", "connector", "vault-skill")
ROUTES = ("use-directly", "bring-in", "internalise", "build-our-own")
OPERATIONS = ("seed", "migrate", "edit", "edit-prose", "activate", "deactivate",
              "retire", "reconcile-page", "reconcile-data",
              "begin-maintenance", "maintenance-phase", "finish-maintenance",
              "maintenance-recover")
CHECKS = {
    "file-content": ("file", "directory-tree"),
    "input-use": ("file", "directory-tree"),
    "executable-version": ("executable",),
    "skill-content": ("skill-tree",),
    "skill-invocation": ("skill-tree",),
    "carrier-load": ("carrier",),
    "server-handshake": ("server-config",),
    "plugin-inspection": ("plugin-enable",),
    "class-launch": ("class-binding",),
    "workspace-access": ("workspace-directory",),
    "hosted-availability": ("hosted-capability",),
}
PURE_CHECKS = {"file-content", "skill-content", "workspace-access"}
DEFS = {}
DEFS["locator"] = union(
    obj({"root": enum("vault", "home"), "relative": string(fmt="relative")}),
    obj({"root": enum("absolute"), "path": string(fmt="absolute")}),
    obj({"root": enum("hosted"), "provider": S, "capability_id": S}))
DEFS["link"] = union(
    obj({"status": enum("linked"), "path": string(fmt="wiki-relative"), "label": S}),
    obj({"status": enum("unresolved"), "label": S, "reason": S}))
DEFS["provenance"] = union(obj({
    "source_sha256": HASH, "source_locator": S, "start_byte": INT,
    "end_byte": INT, "interpretation": S}), obj({"decision_evidence_id": ID}))
PROVENANCE = arr(ref("provenance"))
DEFS["note"] = obj({"id": ID, "text": TEXT, "at": TIME, "links": arr(ref("link")),
                    "supersedes_note_ids": IDS}, ("at",))
DEFS["token"] = union(
    obj({"type": enum("text", "code"), "text": TEXT}),
    obj({"type": enum("link"), "label": S, "target": string(fmt="link")}))
DEFS["block"] = obj({"id": ID, "section": S, "kind": enum("paragraph", "list", "links"),
                     "content": arr(ref("token")), "provenance": PROVENANCE})
DEFS["metadata"] = obj({"title": S, "type": enum("development"), "confidence": S,
                        "audited": DATE, "created": DATE, "updated": DATE,
                        "tags": STRINGS, "aliases": STRINGS})
DEFS["pin"] = union(
    obj({"type": enum("registry-version"), "ecosystem": enum("npm", "pypi", "brew"),
         "package": S, "version": S, "sha256": HASH}),
    obj({"type": enum("git-commit"), "origin": S,
         "object_id": string(r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$"), "tag": S}, ("tag",)),
    obj({"type": enum("floating"), "source": S, "observed_version": S, "sha256": HASH}),
    obj({"type": enum("unresolved"), "reason": S}))
DEFS["installation"] = obj({
    "id": ID, "publisher": obj({"identity": S, "evidence_refs": IDS}),
    "source": obj({"kind": enum("repository", "registry", "marketplace", "hosted",
                              "local-build"), "uri": S, "evidence_refs": IDS}),
    "pin": ref("pin"), "update_policy": obj({
        "mode": enum("newest-qualifying-release", "manual", "report-only"),
        "acceptance_check_ids": arr(enum(*CHECKS), unique=True),
        "revert_resource_ids": IDS, "notes": TEXT}),
    "resource_ids": IDS, "notes": arr(ref("note"))})
EXPECTED = {
    "file": obj({"sha256": HASH, "use": S}),
    "directory-tree": obj({"sha256": HASH, "use": S}),
    "executable": obj({"sha256": HASH, "version_argv": arr(S, 1),
                       "version": S, "pin_sha256": HASH}),
    "skill-tree": obj({"sha256": HASH, "entry": enum("SKILL.md"), "references": STRINGS,
                       "carrier_id": ID, "pin_sha256": HASH}),
    "carrier": obj({"skill_name": ID, "level": LEVEL,
                    "kind": enum("symlink", "wrapper"), "target_resource_id": ID,
                    "declaration": TEXT}),
    "server-config": obj({"format": enum("json", "toml"), "server_id": S,
                          "scope": enum("local"), "executable_resource_id": ID,
                          "arguments": arr(TEXT), "environment": arr(
                              obj({"name": S, "value": TEXT}), unique=True),
                          "surface": enum("session", "helper")}),
    "plugin-enable": obj({"pointer": string(fmt="pointer"), "plugin_id": S,
                          "enabled": enum(True), "hooks_present": BOOL,
                          "inspected_tree_sha256": HASH, "inspection_resource_id": ID}),
    "class-binding": obj({"class_id": ID, "definition_resource_id": ID,
                          "required_resource_ids": IDS}),
    "workspace-directory": obj({"required_kind": enum("directory"),
                                "required_access": arr(enum("read", "write", "search"), 1, True),
                                "scope": S}),
    "hosted-capability": obj({"operations": STRINGS, "principal": S}),
}
DEFS["resource"] = union(*(obj({
    "id": ID, "owner": obj({"type": enum("row", "installation"), "id": ID}),
    "role": enum(kind), "type": enum(kind), "locator": ref("locator"),
    "expected": shape, "check_ids": arr(enum(*CHECKS), 1, True)})
    for kind, shape in EXPECTED.items()))
DEFS["binding"] = obj({"role": enum(*EXPECTED), "resource_id": ID})
DEFS["identity"] = obj({"logical": S, "resolved": S, "device": INT, "inode": INT,
                        "kind": enum("file", "directory", "symlink"), "mode": INT})
DEFS["observation"] = union(
    obj({"type": enum("content"), "identity": ref("identity"), "sha256": HASH}),
    obj({"type": enum("workspace"), "logical_root": S, "resolved_root": S,
         "object_identity": obj({"device": INT, "inode": INT}),
         "kind": enum("directory"), "principal": INT,
         "required_access_results": arr(obj({"access": enum("read", "write", "search"),
                                            "allowed": enum(True)}), 1, True),
         "scope": S}),
    obj({"type": enum("hosted"), "capability_id": S, "principal": S,
         "evidence_subject": HASH}))
ROW_SUBJECT = {"register_id": string(fmt="uuid"), "row_id": ID,
               "definition_sha256": HASH, "field_pointer": string(fmt="pointer"),
               "resource_id": ID, "resource_definition_sha256": HASH, "check_id": enum(*CHECKS)}
DEFS["subject"] = union(
    obj({"type": enum("resource-check"), **ROW_SUBJECT}),
    obj({"type": enum("task-check"), **ROW_SUBJECT, "model_id": S,
         "fixture_sha256": HASH, "criterion_id": S}),
    obj({"type": enum("model-release"), "model_id": S, "release_date": DATE}),
    obj({"type": enum("version-date"), "resource_id": ID, "pin_sha256": HASH,
         "tree_sha256": HASH, "version_date": DATE}),
    obj({"type": enum("decision"), "decision_kind": S, "affected_ids": IDS}),
    obj({"type": enum("source"), "source_sha256": HASH, "locator": S}))
DEFS["evidence"] = obj({
    "id": ID, "kind": enum("scripted", "human", "captured-source", "publisher-claim"),
    "observed_at": TIME, "subject": ref("subject"),
    "artefact": obj({"locator": ref("locator"), "sha256": HASH, "excerpt_locator": S},
                    ("excerpt_locator",)),
    "result": enum("pass", "fail", "unknown"),
    "method": union(obj({"check_id": S, "implementation_sha256": HASH, "description": S}),
                    obj({"judge": S, "criterion": S, "description": S})),
    "limitations": arr(TEXT)})
DEFS["freshness"] = union(
    obj({"status": enum("not-applicable"), "reason": S}),
    obj({"status": enum("applicable"), "skills": arr(obj({
        "resource_id": ID, "candidate": obj({
            "installation_id": ID, "pin_sha256": HASH, "skill_tree_sha256": HASH,
            "version_label": S, "version_date": union(DATE, obj({
                "status": enum("unknown"), "reason": S})),
            "date_basis": enum("release", "relevant-file-revision", "unknown"),
            "date_evidence_refs": IDS}),
        "comparisons": arr(obj({
            "model_id": S, "model_release_date": DATE, "release_evidence_refs": IDS,
            "applicability_evidence_refs": IDS, "evaluated_at": TIME,
            "rule_version": enum(1), "result": enum("pass", "fail", "unknown"),
            "reasons": arr(TEXT)})),
        "applicability_evidence": IDS}), 1)}))
DEFS["check"] = obj({
    "row_id": ID, "field_pointer": string(fmt="pointer"), "resource_id": ID,
    "resource_definition_sha256": HASH, "observation": ref("observation"),
    "check_id": enum(*CHECKS), "observed_at": TIME, "result": enum("pass"),
    "evidence_ref": ID}, ("evidence_ref",))
DEFS["activation"] = obj({
    "id": string(fmt="uuid"), "register_id": string(fmt="uuid"), "row_id": ID,
    "definition_sha256": HASH, "verified_at": TIME, "checks": arr(ref("check")),
    "freshness_evaluation": arr(obj({"model_id": S, "result": enum("pass")})),
    "evidence_refs": IDS})
DEFS["lifecycle"] = union(obj({
    "state": enum("planned", "prepared", "retired"), "changed_at": TIME,
    "reason": S, "decision_refs": IDS}), obj({
    "state": enum("active"), "changed_at": TIME, "reason": S, "decision_refs": IDS,
    "activation": ref("activation")}))
COMMON_ROW = {"id": ID, "name": S, "kind": enum(*KINDS),
              "notes": arr(ref("note")), "provenance": PROVENANCE, "maintenance_id": ID}
DEFS["unresolved"] = obj({"status": enum("unresolved"), "source_span": S, "reason": S})
NORMAL = {
    **COMMON_ROW, "installation_ids": IDS,
    "level": obj({"base": LEVEL, "conditions": arr(obj({
        "use": S, "level": LEVEL, "reason": S})), "decision_refs": IDS}),
    "reference_use": TEXT, "routes": arr(obj({
        "job_id": ID, "route": enum(*ROUTES), "status": enum("planned", "implemented"),
        "reason": S, "decision_refs": IDS})),
    "lifecycle": ref("lifecycle"), "resource_bindings": arr(ref("binding"), unique=True),
    "record_links": arr(ref("link")), "acceptance": obj({
        "check_ids": arr(enum(*CHECKS), unique=True), "evidence_refs": IDS,
        "criterion": S, "human_required": BOOL}),
    "freshness": ref("freshness"), "run_needs": arr(ref("binding"), unique=True),
    "output_judge": obj({"kind": enum("owner", "objective-check", "other-human"),
                         "criterion": S, "evidence_refs": IDS})}
LEGACY = {k: (v if k in COMMON_ROW else ref("unresolved")) for k, v in NORMAL.items()}
LEGACY["lifecycle"] = obj({"state": enum("legacy-recorded"),
                          "original_state_text": TEXT, "source_span": S})
DEFS["row"] = union(obj(NORMAL, ("maintenance_id",)), obj(LEGACY, ("maintenance_id",)))
DEFS["maintenance"] = obj({
    "id": ID, "generation": INT, "coordinator_id": string(fmt="uuid"),
    "guard_identity": S, "status": enum("reserved", "installing", "verifying",
                                      "rolling-back", "recovery-required"),
    "row_ids": IDS, "installation_ids": IDS, "resource_ids": IDS,
    "mutation_scope": arr(string(fmt="absolute"), 1, True), "base_revision": INT,
    "base_subjects": arr(obj({"resource_id": ID, "definition_sha256": HASH,
                              "observation": ref("observation")})),
    "target_plan_sha256": HASH, "recovery_plan": obj({
        "plan_object": HASH, "mode": enum("verify-original-or-target")}),
    "started_at": TIME})
DEFS["coverage"] = obj({"start_byte": INT, "end_byte": INT, "line": INT,
                        "kind": S, "sha256": HASH, "destination_ids": IDS})
DEFS["migration"] = obj({
    "source_sha256": HASH, "source_archive": HASH,
    "coverage": arr(ref("coverage")),
    "legacy_rows": arr(obj({"id": ID, "initial_sha256": HASH})),
    "unresolved": arr(TEXT)})
DEFS["policy"] = obj({
    "model_targets": arr(obj({"model_id": S, "release_date": DATE, "evidence_refs": IDS})),
    "freshness_rule_version": enum(1), "config_exclusions": {"type": "array", "maxItems": 0},
    "extensions": obj({"legacy_execution_gate": BOOL, "category_execution_gates": BOOL}),
    "extension_decision_refs": obj({"legacy_execution_gate": ID,
                                     "category_execution_gates": ID},
                                    ("legacy_execution_gate", "category_execution_gates"))})
SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    **obj({
        "schema_version": enum(1), "revision": INT, "register_id": string(fmt="uuid"),
        "commit": obj({"id": string(fmt="uuid"), "parent_data_sha256": HASH, "at": TIME,
                       "operation": enum(*OPERATIONS), "proposal_sha256": HASH},
                      ("parent_data_sha256",)),
        "page": obj({"metadata": ref("metadata"), "layout_version": enum(1),
                     "prose_blocks": arr(ref("block"))}),
        "jobs": arr(obj({"id": ID, "label": S, "definition": S, "notes": arr(ref("note"))})),
        "installations": arr(ref("installation")), "resources": arr(ref("resource")),
        "maintenance": arr(ref("maintenance")), "rows": arr(ref("row")),
        "evidence": arr(ref("evidence")), "policy": ref("policy"),
        "migration": ref("migration")}, ("migration",)),
    "$defs": DEFS}


def shape(value, spec, path="$"):
    if "$ref" in spec:
        return shape(value, DEFS[spec["$ref"].rsplit("/", 1)[1]], path)
    if "oneOf" in spec:
        matches = 0
        for alternative in spec["oneOf"]:
            try:
                shape(value, alternative, path)
                matches += 1
            except Problem:
                pass
        require(matches == 1, f"{path}: expected one closed union member (got {matches})")
        return
    if "enum" in spec:
        require(any(type(value) is type(x) and value == x for x in spec["enum"]),
                f"{path}: invalid enum")
    types = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool}
    typ = spec.get("type")
    if typ:
        require(type(value) is types[typ], f"{path}: expected {typ}")
    if typ == "object":
        require(set(spec["required"]) <= value.keys(), f"{path}: missing required field")
        require(value.keys() <= spec["properties"].keys(), f"{path}: unknown field")
        for key, item in value.items():
            shape(item, spec["properties"][key], path + "/" + key)
    elif typ == "array":
        require(len(value) >= spec.get("minItems", 0), f"{path}: too few items")
        require(len(value) <= spec.get("maxItems", len(value)), f"{path}: too many items")
        if spec.get("uniqueItems"):
            require(len({canonical(x) for x in value}) == len(value), f"{path}: duplicate items")
        for i, item in enumerate(value):
            shape(item, spec["items"], f"{path}/{i}")
    elif typ == "integer":
        require(value >= spec.get("minimum", value), f"{path}: integer below minimum")
    elif typ == "string":
        require("\0" not in value and not any(0xD800 <= ord(c) <= 0xDFFF for c in value),
                f"{path}: invalid Unicode or NUL")
        require(len(value) >= spec.get("minLength", 0), f"{path}: empty string")
        if "pattern" in spec:
            require(re.fullmatch(spec["pattern"], value), f"{path}: invalid pattern")
        fmt = spec.get("format")
        if fmt == "date":
            date(value)
        elif fmt == "date-time":
            timestamp(value)
        elif fmt == "uuid":
            try:
                require(str(uuid.UUID(value)) == value, f"{path}: noncanonical UUID")
            except ValueError as exc:
                raise Problem(f"{path}: invalid UUID") from exc
        elif fmt in ("relative", "absolute"):
            require(Path(value).is_absolute() == (fmt == "absolute"), f"{path}: path root")
            require("\\" not in value and all(x not in ("", ".", "..") for x in
                    value.lstrip("/").split("/")), f"{path}: path traversal/empty component")
        elif fmt == "wiki-relative":
            shape(value, string(fmt="relative"), path)
            require(":" not in value, f"{path}: relative wiki link cannot contain a URI scheme")
        elif fmt == "pointer":
            require(value.startswith("/") and not re.search(r"~(?![01])", value),
                    f"{path}: invalid JSON pointer")
        elif fmt == "link":
            if value.startswith("https://"):
                require(not re.search(r"[\s<>\"\\]", value), f"{path}: unsafe URL")
            else:
                shape(value, string(fmt="wiki-relative"), path)


def index(doc, name):
    return {x["id"]: x for x in doc[name]}


def dependencies(resource):
    expected = resource["expected"]
    keys = ("target_resource_id", "executable_resource_id", "inspection_resource_id",
            "definition_resource_id", "carrier_id")
    return [expected[k] for k in keys if k in expected] + expected.get("required_resource_ids", [])


def reciprocal_carrier(first, second):
    """The declared skill/carrier pair is one association, not a dependency cycle."""
    if first["type"] == "carrier":
        first, second = second, first
    return (first["type"] == "skill-tree" and second["type"] == "carrier" and
            first["expected"]["carrier_id"] == second["id"] and
            second["expected"]["target_resource_id"] == first["id"])


def operational_definition(doc, row):
    """Evidence subject domain: requirements and reference IDs, without evidence bodies.

    Evidence records contain subjects and artefact digests. Including them in their
    own subject domain would create a recursive hash. Activation uses expansion(),
    which adds the complete records after those subjects have been captured.
    """
    resources, installs = index(doc, "resources"), index(doc, "installations")
    pairs = set((x["role"], x["resource_id"]) for x in
                row["resource_bindings"] + row["run_needs"])
    for key in row["installation_ids"]:
        pairs.update((resources[r]["role"], r) for r in installs[key]["resource_ids"])
    def descend(rid, trail):
        require(rid not in trail, "cyclic resource dependency: " + rid)
        for dep in dependencies(resources[rid]):
            pairs.add((resources[dep]["role"], dep))
            if dep in trail + [rid]:
                require(trail and dep == trail[-1] and
                        reciprocal_carrier(resources[rid], resources[dep]),
                        "cyclic resource dependency: " + dep)
                continue
            descend(dep, trail + [rid])
    for _, rid in list(pairs):
        descend(rid, [])
    bindings = []
    for role, rid in sorted(pairs):
        resource = resources[rid]
        binding = {"role": role, "resource_id": rid, "resource_definition": resource}
        if resource["owner"]["type"] == "installation":
            binding["installation_definition"] = installs[resource["owner"]["id"]]
        bindings.append(binding)
    covered = {k: row[k] for k in ("kind", "level", "installation_ids", "routes",
               "resource_bindings", "run_needs", "acceptance", "freshness", "output_judge")}
    installation_ids = set(row["installation_ids"]) | {
        b["installation_definition"]["id"] for b in bindings if "installation_definition" in b}
    # Direct references retain their definitions even without an owned resource.
    return {"row": covered, "bindings": bindings,
            "installations": [installs[i] for i in sorted(installation_ids)],
            "policy": doc["policy"]}


def evidence_ids(value):
    """Only explicit evidence-reference fields supply evidence identities."""
    keys = {"evidence_refs", "decision_refs", "date_evidence_refs", "release_evidence_refs",
            "applicability_evidence_refs", "applicability_evidence"}
    found = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in keys:
                found.update(child)
            elif key == "decision_evidence_id":
                found.add(child)
            elif key == "extension_decision_refs":
                found.update(child.values())
            else:
                found.update(evidence_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(evidence_ids(child))
    return found


def expansion(doc, row):
    """Activation/cache domain: operational subject plus full referenced records."""
    definition = operational_definition(doc, row)
    records = index(doc, "evidence")
    referenced = sorted(evidence_ids(definition))
    require(all(eid in records for eid in referenced), "unresolved operational evidence")
    return {**definition, "evidence": [records[eid] for eid in referenced]}


def proof_tuples(doc, row):
    expanded = expansion(doc, row)
    return {(row["id"], f"/bindings/{i}/resource_definition", b["resource_id"], check)
            for i, b in enumerate(expanded["bindings"])
            for check in b["resource_definition"]["check_ids"]}


def validate(doc):
    shape(doc, SCHEMA)
    for name in ("jobs", "installations", "resources", "rows", "evidence", "maintenance"):
        require(len(index(doc, name)) == len(doc[name]), "duplicate ID in " + name)
    rows, resources, installs, evidence, jobs, holds = (
        index(doc, k) for k in ("rows", "resources", "installations", "evidence", "jobs", "maintenance"))
    require(not any(doc["policy"]["extensions"].values()),
            "extension enablement unsupported in this core")
    require(not doc["policy"]["extension_decision_refs"], "disabled extensions have no decision refs")
    require((doc["revision"] == 0) == ("parent_data_sha256" not in doc["commit"]),
            "commit parent/revision mismatch")
    def refs(values, collection, label):
        require(all(v in collection for v in values), "unresolved " + label)
    targets = doc["policy"]["model_targets"]
    require(len({t["model_id"] for t in targets}) == len(targets), "duplicate model target")
    for target in targets:
        refs(target["evidence_refs"], evidence, "model-release evidence")
        require(target["evidence_refs"], "model target has no release evidence")
        for eid in target["evidence_refs"]:
            require(evidence[eid]["subject"] == {"type": "model-release", "model_id": target["model_id"],
                    "release_date": target["release_date"]}, "model release subject mismatch")
    for ev in evidence.values():
        subject = ev["subject"]
        if subject["type"] in ("resource-check", "task-check"):
            refs([subject["row_id"]], rows, "evidence row")
            refs([subject["resource_id"]], resources, "evidence resource")
            require(subject["register_id"] == doc["register_id"], "evidence register mismatch")
        elif subject["type"] == "version-date":
            refs([subject["resource_id"]], resources, "dated resource")
    def human_fields(value):
        if isinstance(value, dict):
            if set(value) == {"decision_evidence_id"}:
                refs([value["decision_evidence_id"]], evidence, "provenance decision")
            if {"start_byte", "end_byte"} <= set(value):
                require(value["end_byte"] >= value["start_byte"], "reversed source span")
            if "decision_refs" in value:
                refs(value["decision_refs"], evidence, "owner decisions")
            for child in value.values():
                human_fields(child)
        elif isinstance(value, list):
            if value and all(isinstance(child, dict) and "id" in child for child in value):
                require(len({child["id"] for child in value}) == len(value), "duplicate nested ID")
            if value and all(isinstance(child, dict) and "supersedes_note_ids" in child for child in value):
                note_ids = {child["id"] for child in value}
                require(all(set(child["supersedes_note_ids"]) <= note_ids and
                            child["id"] not in child["supersedes_note_ids"] for child in value),
                        "invalid note supersession reference")
            for child in value:
                human_fields(child)
    human_fields(doc)
    for item in installs.values():
        refs(item["resource_ids"], resources, "installation resources")
        refs(item["publisher"]["evidence_refs"] + item["source"]["evidence_refs"],
             evidence, "installation evidence")
        refs(item["update_policy"]["revert_resource_ids"], resources, "revert resources")
        pin = item["pin"]
        if pin["type"] == "registry-version":
            patterns = {"npm": r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?",
                        "pypi": r"\d+(?:\.\d+)*(?:(?:a|b|rc)\d+)?(?:\.post\d+)?(?:\.dev\d+)?",
                        "brew": r"\d+(?:\.\d+)+(?:_\d+)?"}
            require(re.fullmatch(patterns[pin["ecosystem"]], pin["version"]), "non-exact registry pin")
        if pin["type"] == "floating":
            require(item["update_policy"]["mode"] == "report-only", "floating pin must report only")
    for resource in resources.values():
        owner = resource["owner"]
        refs([owner["id"]], rows if owner["type"] == "row" else installs, "resource owner")
        refs(dependencies(resource), resources, "resource dependency")
        if resource["type"] == "skill-tree":
            require(reciprocal_carrier(resource, resources[resource["expected"]["carrier_id"]]),
                    "named skill carrier must target that exact skill")
        if resource["type"] == "carrier":
            require(resources[resource["expected"]["target_resource_id"]]["type"] == "skill-tree",
                    "carrier target must be a skill tree")
        if resource["type"] == "class-binding":
            require(resources[resource["expected"]["definition_resource_id"]]["type"] == "file",
                    "class definition must be an immutable file")
        if resource["type"] == "plugin-enable":
            require(resources[resource["expected"]["inspection_resource_id"]]["type"] == "directory-tree",
                    "plugin inspection requires a complete tree")
        require(all(resource["type"] in CHECKS[c] for c in resource["check_ids"]),
                "inapplicable check ID")
        required = {"file": {"file-content", "input-use"}, "directory-tree": {"file-content", "input-use"},
                    "skill-tree": {"skill-content", "skill-invocation"}}
        require(required.get(resource["type"], {next(c for c, ts in CHECKS.items()
                if resource["type"] in ts)}) <= set(resource["check_ids"]), "missing required use check")
        require((resource["type"] == "hosted-capability") == (resource["locator"]["root"] == "hosted"),
                "incompatible locator type")
    routes = {}
    legacy_ids = {r["id"] for r in doc.get("migration", {}).get("legacy_rows", [])}
    for row in rows.values():
        if row["lifecycle"]["state"] == "legacy-recorded":
            require(row["id"] in legacy_ids, "unregistered legacy exception")
        else:
            refs(row["installation_ids"], installs, "row installations")
            refs([x["resource_id"] for x in row["resource_bindings"] + row["run_needs"]],
                 resources, "row resources")
            refs([x["job_id"] for x in row["routes"]], jobs, "route job")
            refs(row["acceptance"]["evidence_refs"] + row["output_judge"]["evidence_refs"],
                 evidence, "acceptance evidence")
            for route in row["routes"]:
                if row["lifecycle"]["state"] != "retired":
                    routes.setdefault(route["job_id"], set()).add(route["route"])
            expanded = expansion(doc, row)
            bound = [b["resource_definition"] for b in expanded["bindings"]]
            require(all(b["role"] == resources[b["resource_id"]]["role"]
                        for b in row["resource_bindings"] + row["run_needs"]), "binding role mismatch")
            skill_ids = {r["id"] for r in bound if r["type"] == "skill-tree"}
            fresh = row["freshness"]
            require((fresh["status"] == "applicable") == bool(skill_ids), "freshness closure mismatch")
            if skill_ids:
                listed = [s["resource_id"] for s in fresh["skills"]]
                require(set(listed) == skill_ids and len(listed) == len(skill_ids),
                        "incomplete skill freshness coverage")
                for s in fresh["skills"]:
                    refs([s["candidate"]["installation_id"]], installs, "freshness installation")
                    refs(s["candidate"]["date_evidence_refs"] + s["applicability_evidence"],
                         evidence, "freshness evidence")
                    models = [c["model_id"] for c in s["comparisons"]]
                    require(len(models) == len(set(models)), "duplicate model comparison")
                    for c in s["comparisons"]:
                        refs(c["release_evidence_refs"] + c["applicability_evidence_refs"],
                             evidence, "comparison evidence")
            for r in bound:
                if r["type"] == "carrier":
                    require(r["expected"]["level"] == row["level"]["base"], "carrier level mismatch")
                if r["type"] == "plugin-enable" and r["expected"]["hooks_present"]:
                    require(row["level"]["base"] != "auto", "hooks cannot be auto")
            if row["lifecycle"]["state"] in ("active", "prepared"):
                require(all(i["pin"]["type"] != "unresolved" for i in expanded["installations"]),
                        "prepared/active installation pin unresolved")
            if row["lifecycle"]["state"] == "active":
                activation = row["lifecycle"]["activation"]
                require(activation["row_id"] == row["id"] and
                        activation["register_id"] == doc["register_id"] and
                        activation["definition_sha256"] == digest(expanded), "activation identity mismatch")
                actual = [(c["row_id"], c["field_pointer"], c["resource_id"], c["check_id"])
                          for c in activation["checks"]]
                require(len(set(actual)) == len(actual) and set(actual) == proof_tuples(doc, row),
                        "activation proof set mismatch")
                for c in activation["checks"]:
                    r = resources[c["resource_id"]]
                    require(c["resource_definition_sha256"] == digest(r), "stale resource definition")
                    require((c["observation"]["type"] == "workspace") ==
                            (r["type"] == "workspace-directory"), "observation type mismatch")
                    if c["check_id"] not in PURE_CHECKS:
                        refs([c.get("evidence_ref")], evidence, "proof evidence")
        if "maintenance_id" in row:
            refs([row["maintenance_id"]], holds, "row reservation")
            require(row["id"] in holds[row["maintenance_id"]]["row_ids"] and
                    row["lifecycle"]["state"] != "active", "reservation row/state mismatch")
    require(all(len(values) == 1 for values in routes.values()), "conflicting routes for job")
    for hold in holds.values():
        refs(hold["row_ids"], rows, "reserved row")
        refs(hold["resource_ids"], resources, "reserved resource")
        refs(hold["installation_ids"], installs, "reserved installation")
        require(all(rows[r].get("maintenance_id") == hold["id"] for r in hold["row_ids"]),
                "reservation back-reference mismatch")
    return doc


class Context:
    """Explicit roots; readers never create anything, including a lock."""
    def __init__(self, vault, home, lock_root=None):
        self.vault = Path(vault).resolve(strict=True)
        self.home = Path(home).resolve(strict=True)
        override = os.environ.get("AIMYTH_ADOPT_LOCKS")
        default = self.home / ".aimyth/adopt/locks"
        self.locks = Path(lock_root or override or default).resolve()
        require(not override or self.locks == Path(override).resolve(),
                "lock-root override disagrees with configured root")
        self.data = self.vault / ".claude/adopt/capability-register.json"
        self.page = self.vault / "wiki/developments/capability-register.md"
        self.state = self.vault / ".claude/adopt/register-state"
        self.receipt = self.state / "receipt.json"
        self.pending = self.state / "pending.json"
        self.objects = self.state / "objects"
        self.lock_identity = str(self.page.resolve())
        # Sixteen hex characters preserve the previous writer's resolver.
        self.lock = self.locks / ("register-" + sha(self.lock_identity.encode())[:16] + ".lock")
        self.domain = digest([str(self.home / ".claude.json"),
                              str(self.home / ".claude/settings.json"),
                              str(self.home / ".claude/skills")])
        self.guard = self.locks / ("maintenance-domain-" + self.domain + ".lock")

    def locate(self, locator):
        require(locator["root"] != "hosted", "hosted locator has no local path")
        if locator["root"] == "absolute":
            return Path(locator["path"])
        return (self.vault if locator["root"] == "vault" else self.home) / locator["relative"]


def optional_bytes(path):
    """ENOENT is absence only after checking the complete accessible ancestor chain."""
    path = Path(path).absolute()
    current = Path(path.anchor)
    for part in path.parts[1:]:
        require(os.access(current, os.X_OK), f"cannot search parent {current}")
        child = current / part
        try:
            child.lstat()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise Problem(f"lookup {child}: {exc}") from exc
        current = child
    try:
        return path.read_bytes()
    except OSError as exc:
        raise Problem(f"read {path}: {exc}") from exc


def load_current(ctx):
    from adopt_compat_v1 import render
    def read_tuple():
        require(optional_bytes(ctx.pending) is None, "incomplete register transaction")
        return tuple(optional_bytes(p) for p in (ctx.data, ctx.receipt, ctx.page))
    first = read_tuple()
    raw, receipt_raw, page = first
    require(all(x is not None for x in first), "missing data, receipt or generated page")
    data, receipt = validate(decode(raw)), decode(receipt_raw)
    shape(receipt, obj({"register_id": string(fmt="uuid"), "revision": INT,
                        "data_sha256": HASH, "page_sha256": HASH, "transaction_id": string(fmt="uuid")}))
    require(receipt["data_sha256"] == sha(raw), "data differs from the last writer commit")
    require(receipt["register_id"] == data["register_id"] and receipt["revision"] == data["revision"],
            "receipt identity mismatch")
    expected = render(data)
    require(receipt["page_sha256"] == sha(expected), "receipt/renderer mismatch")
    require(page == expected, "PAGE DRIFT", Finding)
    require(read_tuple() == first, "register changed during read")
    return data, raw


def control():
    hits = 0
    for raw in (b'{"a":1,"a":2}', b'{"x":NaN}', b'\xff'):
        try:
            decode(raw)
        except Problem:
            hits += 1
    require(hits == 3 and decode(b'\xef\xbb\xbf{"ok":true}') == {"ok": True},
            "decoder control failed")
    return hits


def cli_error(exc):
    prefix = "PROBE FAILED: " if getattr(exc, "code", 2) == 2 else ""
    print(prefix + str(exc))
    return getattr(exc, "code", 2)


# Frozen version 1 page projection, retained for receipts and history.
import json
from urllib.parse import quote


def escape(text):
    # Numeric entities also prevent headings, HTML, code fences and markers.
    return "".join(c if c.isalnum() or c in " ,.;:!?/()-" else
                   "&#" + str(ord(c)) + ";" for c in str(text)).replace("\n", "&#10;")


def token(item):
    if item["type"] in ("text", "code"):
        return escape(item["text"])
    target = item["target"]
    return "[" + escape(item["label"]) + "](" + quote(target, safe="/:#%?=&") + ")"


def render(data):
    validate(data)
    meta = data["page"]["metadata"]
    lines = ["---"]
    for key, value in sorted(meta.items()):
        lines.append(key + ": " + json.dumps(value, ensure_ascii=False))
    lines += ["---", "", "Generated capability register",
              "", "Authority: `.claude/adopt/capability-register.json`. Edit through `/adopt --edit` or `/adopt --edit-prose`.",
              "", f"Revision {data['revision']} · committed {data['commit']['at']}",
              "", f"<!-- register-data {sha(encoded(data))} renderer 1 layout {data['page']['layout_version']} -->"]
    categories = [("skill", "User-level skills"), ("tool-server", "Tool servers"),
                  ("plugin", "Plugins"), ("cli", "Command-line tools"),
                  ("connector", "Connectors"), ("vault-skill", "Vault skills")]
    for kind, heading in categories:
        rows = [r for r in data["rows"] if r["kind"] == kind]
        if not rows:
            continue
        lines += ["", "## " + heading, "",
                  "| ID / Name | Level | Route | State | Freshness | Proof / Maintenance |",
                  "|---|---|---|---|---|---|"]
        for row in rows:
            legacy = row["lifecycle"]["state"] == "legacy-recorded"
            level = "unresolved; original ruling below" if legacy else json.dumps(row["level"], ensure_ascii=False, sort_keys=True)
            route = "unresolved; no route invented" if legacy else "; ".join(
                x["job_id"] + ": " + x["route"] + " (" + x["status"] + ")" for x in row["routes"])
            state = "legacy recorded; not re-proved" if legacy else row["lifecycle"]["state"]
            fresh = "unknown" if legacy else row["freshness"]["status"]
            proof = "no current activation"
            if "activation" in row["lifecycle"]:
                proof = "last verified " + row["lifecycle"]["activation"]["verified_at"]
            if "maintenance_id" in row:
                proof += "; MAINTENANCE " + row["maintenance_id"]
            lines.append("| " + " | ".join(escape(v) for v in
                         (row["id"] + " / " + row["name"], level, route, state, fresh, proof)) + " |")
        for row in rows:
            lines += ["", "### " + escape(row["id"]), "", escape(row["name"])]
            for note in row["notes"]:
                for paragraph in (note["id"] + ": " + note["text"]).split("\n\n"):
                    lines += ["", escape(paragraph)]
                if note["links"]:
                    lines += ["", " · ".join(token({"type": "link", "target": link["path"],
                        "label": link["label"]}) if link["status"] == "linked" else
                        escape(link["label"] + ": " + link["reason"]) for link in note["links"])]
                if note["supersedes_note_ids"]:
                    lines += ["", "Qualifies/supersedes: " + escape(", ".join(note["supersedes_note_ids"]))]
            if row["lifecycle"]["state"] != "legacy-recorded":
                lines += ["", "Recorded requirements: " + escape(json.dumps({
                    k: row[k] for k in ("reference_use", "resource_bindings", "run_needs",
                                        "output_judge", "freshness", "record_links")},
                    ensure_ascii=False, sort_keys=True))]
                lines += ["", " · ".join(token({"type": "link", "target": link["path"], "label": link["label"]})
                          if link["status"] == "linked" else escape(link["label"] + ": " + link["reason"])
                          for link in row["record_links"])]
    if data["installations"]:
        lines += ["", "## Installation pins"]
        for item in data["installations"]:
            lines += ["", escape(item["id"] + ": " + json.dumps(item["pin"], ensure_ascii=False, sort_keys=True))]
    lines += ["", "## Authored material"]
    for block in data["page"]["prose_blocks"]:
        lines += ["", "### " + escape(block["id"] + " · " + block["section"]), "",
                  "".join(token(t) for t in block["content"])]
    if "migration" in data:
        lines += ["", "## Migration provenance", "",
                  "Source archive SHA-256: " + data["migration"]["source_archive"]]
        for gap in data["migration"]["unresolved"]:
            lines += ["", escape(gap)]
    return ("\n".join(lines) + "\n").encode("utf-8")
