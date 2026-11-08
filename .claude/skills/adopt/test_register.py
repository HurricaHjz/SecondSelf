#!/usr/bin/env python3
"""Fixture-only acceptance suite. Run with -B and an explicit scratch TMPDIR."""
import argparse
import copy
import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import traceback
from unittest.mock import patch
import adopt_data as D
import adopt_register as W
import adopt_resources as R
import adopt_snapshot as S
import adopt_freshness as F
import adopt_manifest as V
import adopt_maintenance as M
import adopt_migrate as G
from adopt_render import render

ROOT = None
COUNT = 0
FAILURES = 0
RESULTS = []
POLL_SECONDS = 15  # Set by judgement, unmeasured; test deadlock timeout, never a lease.


def check(ok, label):
    global COUNT
    COUNT += 1
    if not ok:
        raise AssertionError(label)
    print("  PASS " + label, flush=True)


def refuses(call, label, codes=(1, 2, 3), ctx=None):
    before = W.tuple_bytes(ctx) if ctx else None
    try:
        call()
    except D.Problem as exc:
        check(exc.code in codes, label + " (exit " + str(exc.code) + ")")
        if ctx:
            check(W.tuple_bytes(ctx) == before, label + " preserved data/receipt/page")
        return exc
    raise AssertionError("accepted prohibited case: " + label)


def write(path, raw, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw if isinstance(raw, bytes) else raw.encode())
    if mode is not None:
        path.chmod(mode)


def fixture(name):
    root = ROOT / name
    root.mkdir()
    vault, home = root / "vault", root / "home"
    vault.mkdir()
    home.mkdir()
    (home / ".claude/skills").mkdir(parents=True)
    write(home / ".claude.json", b'{"mcpServers":{},"approval":[]}')
    write(home / ".claude/settings.json", b'{"enabledPlugins":{},"hooks":{}}')
    ctx = D.Context(vault, home, root / "locks")
    W.commit(ctx, W.proposal(ctx, "seed"))
    return ctx


def note(identifier, text):
    return {"id": identifier, "text": text, "links": [], "supersedes_note_ids": []}


def normal_row(rid, resources, kind="cli"):
    return {"id": rid, "name": rid, "kind": kind, "installation_ids": [rid + "-install"],
            "level": {"base": "auto", "conditions": [], "decision_refs": []},
            "reference_use": "Read as data within the existing grant.",
            "routes": [{"job_id": rid + "-job", "route": "use-directly", "status": "implemented",
                        "reason": "fixture capability", "decision_refs": []}],
            "lifecycle": {"state": "prepared", "changed_at": D.now(), "reason": "fixture", "decision_refs": []},
            "resource_bindings": [{"role": r["role"], "resource_id": r["id"]} for r in resources],
            "record_links": [{"status": "unresolved", "label": "Fixture", "reason": "No live record in fixture"}],
            "acceptance": {"check_ids": [], "evidence_refs": [], "criterion": "exact-fixture",
                           "human_required": False},
            "freshness": {"status": "not-applicable", "reason": "No skill tree"},
            "run_needs": [], "output_judge": {"kind": "objective-check", "criterion": "exact-fixture",
                                            "evidence_refs": []}, "notes": [], "provenance": []}


def installation(rid, resources):
    return {"id": rid + "-install", "publisher": {"identity": "Fixture publisher", "evidence_refs": []},
            "source": {"kind": "local-build", "uri": "fixture:local", "evidence_refs": []},
            "pin": {"type": "registry-version", "ecosystem": "npm", "package": rid,
                    "version": "1.0.0", "sha256": D.sha(b"fixture")},
            "update_policy": {"mode": "manual", "acceptance_check_ids": [],
                              "revert_resource_ids": [], "notes": ""},
            "resource_ids": [r["id"] for r in resources], "notes": []}


def resource(rid, kind, path, expected, checks, owner):
    return {"id": rid, "owner": {"type": "installation", "id": owner},
            "role": kind, "type": kind, "locator": {"root": "absolute", "path": str(path)},
            "expected": expected, "check_ids": checks}


def add_cli(doc, ctx, rid, present=True):
    path = ctx.home / "bin" / rid
    if present:
        write(path, b"#!/bin/sh\nexit 0\n", 0o755)
    install = installation(rid, [])
    r = resource(rid + "-binary", "executable", path,
                 {"sha256": D.sha(b"#!/bin/sh\nexit 0\n"), "version_argv": [str(path), "--version"],
                  "version": "1.0.0", "pin_sha256": D.digest(install["pin"])},
                 ["executable-version"], install["id"])
    install["resource_ids"] = [r["id"]]
    row = normal_row(rid, [r])
    doc["jobs"].append({"id": rid + "-job", "label": rid, "definition": "Fixture " + rid, "notes": []})
    doc["resources"].append(r)
    doc["installations"].append(install)
    doc["rows"].append(row)
    return row


def add_evidence(doc, ctx, eid, subject, body=None, kind="scripted"):
    payload = {"subject": subject, "result": "pass", **(body or {})}
    path = ctx.vault / "evidence" / (eid + ".json")
    write(path, D.encoded(payload))
    record = {"id": eid, "kind": kind, "observed_at": D.now(), "subject": subject,
              "artefact": {"locator": {"root": "absolute", "path": str(path)},
                           "sha256": D.sha(path.read_bytes())}, "result": "pass",
              "method": {"check_id": "fixture", "implementation_sha256": D.sha(b"fixture checks"),
                         "description": "Measured fixture result and control"},
              "limitations": ["Fixture stand-in; no real runtime invoked"]}
    doc["evidence"] = [e for e in doc["evidence"] if e["id"] != eid] + [record]
    return eid


def bind_evidence(doc, ctx, rows=None):
    rows = rows or doc["rows"]
    # Reserve evidence identities before computing operational definition digests.
    for row in rows:
        row["acceptance"]["evidence_refs"] = [
            row["id"] + "-" + b["resource_id"] + "-" + check
            for b in D.operational_definition(doc, row)["bindings"]
            for check in b["resource_definition"]["check_ids"] if check not in D.PURE_CHECKS]
    for row in rows:
        for i, b in enumerate(D.operational_definition(doc, row)["bindings"]):
            r = b["resource_definition"]
            try:
                obs = R.observation(doc, row, r, ctx)
            except D.Problem:
                continue
            for check_id in r["check_ids"]:
                if check_id not in D.PURE_CHECKS:
                    add_evidence(doc, ctx, row["id"] + "-" + r["id"] + "-" + check_id,
                                 R.row_subject(doc, row, b, i, check_id),
                                 {"observation_sha256": D.digest(obs), "positive_control": True,
                                  "negative_control": True, "criterion": row["acceptance"]["criterion"],
                                  "output": r["expected"].get("version", "passed")})


def save_doc(ctx, doc):
    current, _ = D.load_current(ctx)
    doc = copy.deepcopy(doc)
    additions = []
    existing = {(r["id"], s["resource_id"], c["model_id"])
                for r in current["rows"] for s in r["freshness"].get("skills", []) for c in s["comparisons"]}
    for row in doc["rows"]:
        for skill in row["freshness"].get("skills", []):
            for c in skill["comparisons"]:
                if (row["id"], skill["resource_id"], c["model_id"]) not in existing:
                    for event in c["events"]:
                        additions.append({"row_id": row["id"], "resource_id": skill["resource_id"],
                                          "model_id": c["model_id"], "event": event})
                    c.update(events=[], tier="unproven", result="unknown")
    changes = {k: doc[k] for k in ("jobs", "installations", "resources", "rows", "evidence", "policy", "page")
               if doc[k] != current[k]}
    result = W.commit(ctx, W.proposal(ctx, "edit", changes))
    for addition in additions:
        result = W.commit(ctx, W.proposal(ctx, "record-freshness", addition))
    return result


def activate(ctx, ids):
    return W.commit(ctx, W.proposal(ctx, "activate", {"row_ids": ids, "reason": "tested fixture"}))


def test_schema():
    doc = W.seed_document()
    check(D.validate(D.decode(b"\xef\xbb\xbf" + D.encoded(doc))) == doc, "BOM seed validates")
    for key in D.SCHEMA["required"]:
        bad = copy.deepcopy(doc)
        del bad[key]
        refuses(lambda: D.validate(bad), "missing top-level " + key)
    for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e999}', b'\xff'):
        refuses(lambda: D.decode(raw), "strict JSON refusal")
    for key, value in (("revision", True), ("schema_version", doc["schema_version"] + 1), ("migration", None), ("unknown", "")):
        bad = copy.deepcopy(doc)
        bad[key] = value
        refuses(lambda: D.validate(bad), "schema type/closure " + key)
    for value in ("2025-02-30", "2025-01-01T00:00:00", "2025-13-01T10:20:30Z"):
        refuses(lambda: D.timestamp(value), "malformed timestamp")
    check(D.control() == 3, "strict decoder positive and valid controls")
    schema = Path(__file__).with_name("register-schema.json")
    check(D.read_json(schema) == D.SCHEMA, "published schema equals shared validator")
    ctx = fixture("schema")
    managed, _ = D.load_current(ctx)
    row = add_cli(managed, ctx, "one")
    bind_evidence(managed, ctx)
    for key in D.NORMAL:
        if key == "maintenance_id":
            continue
        bad = copy.deepcopy(managed)
        del bad["rows"][0][key]
        refuses(lambda: D.validate(bad), "required normal row " + key)
    for value in ("latest", "^1.0.0", "1.*", ">=1.0.0"):
        bad = copy.deepcopy(managed)
        bad["installations"][0]["pin"]["version"] = value
        refuses(lambda: D.validate(bad), "non-exact pin " + value)
    check(D.validate(managed) == managed, "exact registry pin control")
    for null_path in ("activation", "maintenance_id"):
        bad = copy.deepcopy(managed)
        (bad["rows"][0]["lifecycle"] if null_path == "activation" else bad["rows"][0])[null_path] = None
        refuses(lambda: D.validate(bad), "optional null " + null_path)
    full = copy.deepcopy(managed)
    full["installations"][0]["pin"] = {"type": "git-commit", "origin": "https://example.test/source",
                                      "object_id": "a" * 40}
    check(D.validate(full) == full, "full commit pin control")
    # Test every published closed nested shape, including branches absent from this fixture.
    def sample(spec):
        if "$ref" in spec:
            return sample(D.DEFS[spec["$ref"].rsplit("/", 1)[1]])
        if "oneOf" in spec:
            return sample(spec["oneOf"][0])
        if "enum" in spec:
            return spec["enum"][0]
        kind = spec["type"]
        if kind == "object":
            return {k: sample(v) for k, v in spec["properties"].items() if k in spec["required"]}
        if kind == "array":
            return [sample(spec["items"]) for _ in range(spec.get("minItems", 0))]
        if kind == "integer":
            return spec.get("minimum", 0)
        if kind == "boolean":
            return False
        fmt = spec.get("format")
        if fmt == "date":
            return "2025-01-01"
        if fmt == "date-time":
            return "2025-01-01T00:00:00Z"
        if fmt == "uuid":
            return "00000000-0000-0000-0000-000000000000"
        if fmt in ("absolute", "pointer"):
            return "/fixture"
        pattern = spec.get("pattern", "")
        if pattern == D.HASH["pattern"]:
            return "a" * 64
        if "{40}" in pattern:
            return "a" * 40
        if pattern.startswith("^https://"):
            return "https://example.test/claim"
        return "fixture"
    def walk(spec, label):
        if "$ref" in spec:
            return  # Each definition is walked separately.
        if "oneOf" in spec:
            for i, branch in enumerate(spec["oneOf"]):
                walk(branch, label + "-" + str(i))
            return
        if spec.get("type") == "object":
            value = sample(spec)
            D.shape(value, spec)
            for key in spec["required"]:
                bad = copy.deepcopy(value)
                del bad[key]
                refuses(lambda: D.shape(bad, spec), "closed nested required " + label + "/" + key)
            bad = {**value, "unknown-field": True}
            refuses(lambda: D.shape(bad, spec), "closed nested unknown " + label)
            for key, child in spec["properties"].items():
                bad = {**value, key: None}
                if child == D.union(D.S, D.enum(None)):
                    check(D.shape(bad, spec) is None, "explicit nullable " + label + "/" + key)
                else:
                    refuses(lambda: D.shape(bad, spec), "nested null " + label + "/" + key)
                walk(child, label + "/" + key)
        elif spec.get("type") == "array" and "items" in spec:
            walk(spec["items"], label + "[]")
    for label, spec in D.DEFS.items():
        walk(spec, label)


GHOST = "\n  ## User-level skills\n\n| **Name** | Level | Carrier | Pin · publisher | Acceptance | Bump | Route | State | Record |\n|---|---|---|---|---|---|---|---|---|\n| `ghost` | auto | symlink | 1.0.0 · x | listed | fetch | ghost work: use directly | active | x |\n"


def test_h1_edits_render():
    ctx = fixture("h1")
    valid, _ = D.load_current(ctx)
    good_page = ctx.page.read_bytes()
    ctx.page.write_bytes(good_page + GHOST.encode())
    refuses(lambda: D.load_current(ctx), "H1 formatted ghost is PAGE DRIFT", codes=(1,))
    p = {"operation": "edit", "changes": {}}
    refuses(lambda: W.proposal(ctx, **p), "H1 ordinary edit cannot import ghost", ctx=ctx)
    observed = [D.sha(x) for x in W.tuple_bytes(ctx)]
    reconcile = W.proposal(ctx, "reconcile-page", {"discard": True}, observed)
    ghost_hash = D.sha(ctx.page.read_bytes())
    W.commit(ctx, reconcile)
    check((ctx.objects / ghost_hash).read_bytes().endswith(GHOST.encode()), "observed drift archived byte-exact")
    doc, _ = D.load_current(ctx)
    check(not doc["rows"], "ghost never becomes a row")
    for addition in (b"cell hand edit", b"prose hand edit", b"metadata hand edit", b"<!-- fake marker -->"):
        page = ctx.page.read_bytes()
        ctx.page.write_bytes(page + addition)
        refuses(lambda: D.load_current(ctx), "complete-page drift control")
        ctx.page.write_bytes(page)
    old = ctx.data.read_bytes()
    ctx.data.write_bytes(old + b" ")
    refuses(lambda: D.load_current(ctx), "valid JSON hand edit fails receipt", codes=(2,))
    reconcile = W.proposal(ctx, "reconcile-data", {"discard": True}, [D.sha(x) for x in W.tuple_bytes(ctx)])
    W.commit(ctx, reconcile)
    check((ctx.objects / D.sha(old + b" ")).is_file(), "data drift archived")
    doc, _ = D.load_current(ctx)
    doc["page"]["prose_blocks"] = [{"id": "hostile", "section": "Notes", "kind": "paragraph",
        "content": [{"type": "text", "text": "| fake | table |\n## heading\n```code\n<div>Ω</div><!-- marker -->"}],
        "provenance": []}]
    new = save_doc(ctx, doc)
    page = render(new)
    check(page == render(D.decode(D.encoded(new))), "deterministic renderer independent of object insertion order")
    check(b"<div>" not in page and b"\n## heading" not in page and b"\n| fake" not in page,
          "hostile display text cannot create structure")
    for target in ("javascript:alert(1)", "//outside.test/link", "../escape"):
        bad = copy.deepcopy(new)
        bad["page"]["prose_blocks"][0]["content"] = [{"type": "link", "target": target, "label": "unsafe"}]
        refuses(lambda: D.validate(bad), "unsafe typed link " + target)
    request = W.proposal(ctx, "edit", {"page": {**new["page"],
                         "metadata": {**new["page"]["metadata"], "title": "Owner edit"}}})
    preview = W.preview(ctx, request)
    check("Owner edit" in preview["page_diff"] and preview["data_diff"], "owner preview carries both exact diffs")
    W.commit(ctx, request)
    refuses(lambda: W.commit(ctx, request), "stale apply refuses", codes=(3,), ctx=ctx)
    refuses(lambda: W.commit(ctx, W.proposal(ctx, "seed", {"markdown": GHOST})),
            "custom/second seed refuses", ctx=ctx)


def test_h2_proof():
    ctx = fixture("h2")
    doc, _ = D.load_current(ctx)
    a, b = add_cli(doc, ctx, "alpha"), add_cli(doc, ctx, "beta")
    bind_evidence(doc, ctx)
    save_doc(ctx, doc)
    path = ctx.home / "bin/beta"
    content = path.read_bytes()
    path.unlink()
    refuses(lambda: activate(ctx, ["alpha", "beta"]), "H2 missing B refuses whole batch", ctx=ctx)
    check(all(r["lifecycle"]["state"] == "prepared" for r in D.load_current(ctx)[0]["rows"]),
          "H2 neither row activated")
    write(path, content, 0o755)
    doc, _ = D.load_current(ctx)
    bind_evidence(doc, ctx)
    save_doc(ctx, doc)
    active = activate(ctx, ["alpha", "beta"])
    check(all(r["lifecycle"]["state"] == "active" for r in active["rows"]), "two separate resources activate")
    for row in active["rows"]:
        check({c["row_id"] for c in row["lifecycle"]["activation"]["checks"]} == {row["id"]},
              "activation bound to its own row")
    for mutation in ("row", "register", "pointer", "extra", "missing", "digest"):
        bad = copy.deepcopy(active)
        act = bad["rows"][0]["lifecycle"]["activation"]
        if mutation == "row":
            act["row_id"] = "beta"
        elif mutation == "register":
            act["register_id"] = "00000000-0000-0000-0000-000000000000"
        elif mutation == "pointer":
            act["checks"][0]["field_pointer"] = "/bindings/99/resource_definition"
        elif mutation == "extra":
            act["checks"].append(copy.deepcopy(act["checks"][0]))
        elif mutation == "missing":
            act["checks"].clear()
        else:
            act["checks"][0]["resource_definition_sha256"] = "0" * 64
        refuses(lambda: D.validate(bad), "wrong activation " + mutation)
    bad = copy.deepcopy(active)
    bad["rows"][0]["level"]["base"] = "by-name"
    refuses(lambda: save_doc(ctx, bad), "ordinary edit cannot forge/preserve stale activation", ctx=ctx)
    W.commit(ctx, W.proposal(ctx, "deactivate", {"row_ids": ["alpha", "beta"], "reason": "share"}))
    doc, _ = D.load_current(ctx)
    doc["rows"][1]["installation_ids"] = ["alpha-install"]
    doc["rows"][1]["resource_bindings"] = [{"role": "executable", "resource_id": "alpha-binary"}]
    bind_evidence(doc, ctx)
    save_doc(ctx, doc)
    active = activate(ctx, ["alpha", "beta"])
    check(active["rows"][0]["lifecycle"]["activation"]["checks"][0]["resource_id"] ==
          active["rows"][1]["lifecycle"]["activation"]["checks"][0]["resource_id"],
          "explicit shared resource produces distinct row-bound checks")
    previous = ctx.data.read_bytes()
    retired = W.commit(ctx, W.proposal(ctx, "retire", {"row_ids": ["alpha"], "reason": "owner retirement"}))
    check(D.index(retired, "rows")["alpha"]["lifecycle"]["state"] == "retired" and
          D.index(retired, "rows")["beta"]["lifecycle"]["state"] == "active",
          "retiring shared CLI retains the other active row")
    check((ctx.objects / D.sha(previous)).read_bytes() == previous and (ctx.home / "bin/alpha").is_file(),
          "retirement archives activation and does not uninstall the shared binary")


def test_snapshot():
    ctx = fixture("snapshot")
    first = S.snapshot(ctx.home)
    check(S.compare(first, S.snapshot(ctx.home), [])["findings"] == 0, "empty-tree control with positive hit")
    original_lstat = Path.lstat
    for target in (ctx.home, ctx.home / ".claude", ctx.home / ".claude/skills",
                   ctx.home / ".claude.json", ctx.home / ".claude/settings.json"):
        for error in (PermissionError("denied"), NotADirectoryError("not directory"),
                      OSError(40, "loop"), OSError(5, "I/O")):
            def broken(path, *args, **kwargs):
                if path == target:
                    raise error
                return original_lstat(path, *args, **kwargs)
            with patch.object(Path, "lstat", broken):
                refuses(lambda: S.snapshot(ctx.home), "H3a lookup error never absence: " + target.name)
    missing = ctx.home / "absent"
    check(S.inventory(missing)[0]["."]["type"] == "absent", "accessible-parent ENOENT control")
    before = S.snapshot(ctx.home)
    write(ctx.home / ".claude/skills/new/SKILL.md", "New fixture skill")
    intended = S.snapshot(ctx.home)
    declaration = S.changes(before, intended)
    write(ctx.home / ".claude/skills/new/extra-hook", "Unexpected effect")
    after = S.snapshot(ctx.home)
    result = S.compare(before, after, declaration)
    check(result["findings"] > 0 and any("extra-hook" in c["address"] for c in result["unexpected"]),
          "H3b undeclared new-skill child reported by exact address")
    check(S.compare(before, after, S.changes(before, after))["findings"] == 0, "fully enumerated new skill control")
    changes = [
        (ctx.home / ".claude.json", b'{"mcpServers":{"s":{"command":"changed","env":{"X":"y"}}},"approval":["s"],"empty":{}}'),
        (ctx.home / ".claude/settings.json", b'{"enabledPlugins":{"p":true},"hooks":{"run":"extra"}}'),
        (ctx.home / ".claude/skills/new/.git/hooks/action", b"hidden hook"),
        (ctx.home / ".claude/skills/new/deep/reference", b"nested reference"),
    ]
    for path, content in changes:
        a = S.snapshot(ctx.home)
        write(path, content)
        b = S.snapshot(ctx.home)
        check(S.compare(a, b, [])["findings"] > 0, "full snapshot catches " + path.name)
        check(S.compare(a, b, S.changes(a, b))["findings"] == 0, "exact declaration control " + path.name)
    a = S.snapshot(ctx.home)
    config = ctx.home / ".claude/settings.json"
    config.write_bytes(config.read_bytes() + b" ")
    b = S.snapshot(ctx.home)
    delta = S.changes(a, b)
    check(len(delta) == 1 and "#" not in delta[0]["address"], "byte-only formatting is declared separately")
    a = S.snapshot(ctx.home)
    child = ctx.home / ".claude/skills/new/SKILL.md"
    child.chmod(0o755)
    check(S.compare(a, S.snapshot(ctx.home), [])["findings"] > 0, "executable bit comparison")
    a = S.snapshot(ctx.home)
    link = ctx.home / ".claude/skills/linked"
    link.symlink_to("new")
    b = S.snapshot(ctx.home)
    check(S.compare(a, b, [])["findings"] > 0, "symlink and target inventory")
    broken = copy.deepcopy(b)
    broken["complete"] = False
    refuses(lambda: S.compare(a, broken, []), "partial snapshot refused")
    broken = copy.deepcopy(b)
    broken["state"].pop(next(k for k in broken["state"] if k.endswith("extra-hook")))
    broken["state_sha256"] = D.digest(broken["state"])
    refuses(lambda: S.compare(a, broken, []), "forged complete marker cannot hide listed child")
    with patch.object(os, "listdir", side_effect=PermissionError("enumeration failed")):
        refuses(lambda: S.snapshot(ctx.home), "failed enumeration")
    link.unlink()
    link.symlink_to("linked")
    refuses(lambda: S.snapshot(ctx.home), "symlink cycle failure")


def test_routes_extensions():
    ctx = fixture("routes")
    doc, _ = D.load_current(ctx)
    for rid in ("alpha", "beta", "gamma"):
        add_cli(doc, ctx, rid)
    doc["rows"][1]["routes"][0].update(job_id="alpha-job", route="internalise")
    doc["rows"][2]["routes"][0].update(job_id="alpha-job")
    bind_evidence(doc, ctx)
    refuses(lambda: save_doc(ctx, doc), "ordered A/B/C route conflict", ctx=ctx)
    doc["rows"][1]["routes"][0]["route"] = "use-directly"
    check(D.validate(doc) == doc, "same route sharing control")
    for switch in doc["policy"]["extensions"]:
        bad = copy.deepcopy(doc)
        bad["policy"]["extensions"][switch] = True
        refuses(lambda: D.validate(bad), "unsupported extension enablement " + switch)
    check(not any(doc["policy"]["extensions"].values()), "both extension defaults explicitly off")


def test_workspace():
    ctx = fixture("workspace")
    doc, _ = D.load_current(ctx)
    row = add_cli(doc, ctx, "alpha")
    for rid, path in (("vault-work", ctx.vault), ("wiki-work", ctx.vault / "wiki")):
        work = resource(rid, "workspace-directory", path,
            {"required_kind": "directory", "required_access": ["read", "write", "search"], "scope": "output"},
            ["workspace-access"], "alpha-install")
        doc["resources"].append(work)
        row["run_needs"].append({"role": "workspace-directory", "resource_id": rid})
    bind_evidence(doc, ctx)
    save_doc(ctx, doc)
    active = activate(ctx, ["alpha"])
    before = R.recheck(active, active["rows"][0], ctx)
    write(ctx.vault / "wiki/output.txt", "ordinary output")
    after = R.recheck(*[active, active["rows"][0], ctx])
    check(R.stable_checks(before) == R.stable_checks(after), "F2 activation and ordinary workspace output preserve proof")
    bad = copy.deepcopy(active)
    work = next(c for c in bad["rows"][0]["lifecycle"]["activation"]["checks"] if c["check_id"] == "workspace-access")
    work["observation"]["sha256"] = "0" * 64
    refuses(lambda: D.validate(bad), "workspace observations forbid content hashes")
    original_access = R.accessible
    with patch.object(R, "accessible", side_effect=lambda p, a: False if p == ctx.vault and a == "write" else original_access(p, a)):
        refuses(lambda: R.recheck(active, active["rows"][0], ctx), "lost required workspace access")
    path = ctx.home / "bin/alpha"
    path.write_bytes(b"changed")
    refuses(lambda: R.recheck(active, active["rows"][0], ctx), "changed immutable bytes still fail")
    for target in (ctx.vault, ctx.vault / "wiki", ctx.state):
        bad = copy.deepcopy(active)
        r = resource("self-proof", "directory-tree", target,
                     {"sha256": "0" * 64, "use": "immutable input"}, ["file-content", "input-use"], "alpha-install")
        bad["resources"].append(r)
        refuses(lambda: R.footprint_check(bad, ctx), "immutable tree rejects writer footprint " + target.name)
    symlink = ctx.home / "immutable-alias"
    symlink.symlink_to(ctx.vault / "wiki")
    bad = copy.deepcopy(active)
    bad["resources"].append(resource("alias-input", "directory-tree", symlink,
        {"sha256": "0" * 64, "use": "input"}, ["file-content", "input-use"], "alpha-install"))
    refuses(lambda: R.footprint_check(bad, ctx), "immutable symlink alias rejects writer footprint")
    hardlink = ctx.home / "data-alias"
    os.link(ctx.data, hardlink)
    bad = copy.deepcopy(active)
    bad["resources"].append(resource("hardlink-input", "file", hardlink,
        {"sha256": D.sha(hardlink.read_bytes()), "use": "input"}, ["file-content", "input-use"], "alpha-install"))
    refuses(lambda: R.footprint_check(bad, ctx), "immutable hard-link alias rejects writer data")
    external = ctx.home / "workspace"
    external.mkdir()
    alias = ctx.home / "workspace-alias"
    alias.symlink_to(external)
    r = resource("alias-work", "workspace-directory", alias,
                 {"required_kind": "directory", "required_access": ["read"], "scope": "output"},
                 ["workspace-access"], "alpha-install")
    a = R.observation(active, active["rows"][0], r, ctx)
    other = ctx.home / "other-workspace"
    other.mkdir()
    alias.unlink()
    alias.symlink_to(other)
    check(R.observation(active, active["rows"][0], r, ctx) != a, "workspace symlink retarget changes identity")
    alias.unlink()
    refuses(lambda: R.observation(active, active["rows"][0], r, ctx), "deleted workspace root")
    write(alias, b"not a directory")
    refuses(lambda: R.observation(active, active["rows"][0], r, ctx), "workspace kind change")


def skill_fixture(name, labels=("primary", "dependency")):
    ctx = fixture(name)
    doc, _ = D.load_current(ctx)
    rid = "skill"
    install = installation(rid, [])
    resources = []
    for label in labels:
        root = ctx.home / "trees" / label
        write(root / "SKILL.md", "---\nname: " + label + "\n---\nUse the frozen fixture.")
        write(root / "reference.txt", "The answer is in the fixture.")
        carrier = ctx.home / ".claude/skills" / label
        carrier.symlink_to(root)
        tree = resource(label, "skill-tree", root,
            {"sha256": S.tree_hash(root), "entry": "SKILL.md", "references": ["reference.txt"],
             "carrier_id": label + "-carrier", "pin_sha256": D.digest(install["pin"])},
            ["skill-content", "skill-invocation"], install["id"])
        wrapper = resource(label + "-carrier", "carrier", carrier,
            {"skill_name": label, "level": "auto", "kind": "symlink",
             "target_resource_id": label, "declaration": ""}, ["carrier-load"], install["id"])
        resources.extend([tree, wrapper])
    install["resource_ids"] = [r["id"] for r in resources]
    row = normal_row(rid, resources, "skill")
    doc["resources"] = resources
    doc["installations"] = [install]
    doc["jobs"] = [{"id": "skill-job", "label": "Skill fixture", "definition": "Frozen task", "notes": []}]
    doc["rows"] = [row]
    today = D.now()[:10]
    for model in ("model-a-release", "model-b-release"):
        add_evidence(doc, ctx, model, {"type": "model-release", "model_id": model, "release_date": today},
                     kind="captured-source")
    doc["policy"]["model_targets"] = [{"model_id": "model-a-release", "release_date": today,
                                      "evidence_refs": ["model-a-release"]}]
    row["freshness"] = {"status": "applicable", "skills": []}
    for tree in [r for r in resources if r["type"] == "skill-tree"]:
        eid = tree["id"] + "-date"
        add_evidence(doc, ctx, eid, {"type": "version-date", "resource_id": tree["id"],
            "pin_sha256": D.digest(install["pin"]), "tree_sha256": tree["expected"]["sha256"],
            "version_date": today}, kind="captured-source")
        task = tree["id"] + "-task"
        row["freshness"]["skills"].append({"resource_id": tree["id"],
            "candidate": {"installation_id": install["id"], "pin_sha256": D.digest(install["pin"]),
                          "skill_tree_sha256": tree["expected"]["sha256"], "version_label": "1.0.0",
                          "version_date": today, "date_basis": "relevant-file-revision", "date_evidence_refs": [eid]},
            "comparisons": [{"model_id": "model-a-release", "model_release_date": today,
                             "release_evidence_refs": ["model-a-release"],
                             "applicability_evidence_refs": [task], "evaluated_at": D.now(),
                             "rule_version": 2, "result": "pass", "reasons": [], "tier": "unproven",
                             "proof_route": "comparison", "claim_evidence_refs": [], "events": []}],
            "applicability_evidence": [task]})
    bind_tasks(doc, ctx)
    bind_evidence(doc, ctx)
    save_doc(ctx, doc)
    return ctx


def bind_tasks(doc, ctx):
    """Captured paired v2 outcomes; no installed model or programme is invoked."""
    import datetime as dt
    import base64
    row = doc["rows"][0]
    for skill in row["freshness"]["skills"]:
        for comparison in skill["comparisons"]:
            eid = comparison["applicability_evidence_refs"][0]
            at = comparison["evaluated_at"]
            def earlier(seconds):
                return (D.timestamp(at) - dt.timedelta(seconds=seconds)).isoformat()
            scope = F.assurance_scope(doc, row, skill, comparison["model_id"], comparison["model_release_date"])
            def capture(name, subject, body, observed, kind="scripted", result="pass"):
                add_evidence(doc, ctx, name, subject, {**body, "result": result}, kind=kind)
                rec = D.index(doc, "evidence")[name]
                rec.update(observed_at=observed, result=result)
            claim = eid + "-claim"
            capture(claim, {"type": "skill-claim", "scope_sha256": scope,
                "author_identity": "Fixture publisher", "published_uri": "https://example.test/claim",
                "published_at": earlier(4)}, {"output": "Captured support for this exact model and candidate."}, earlier(4), "publisher-claim")
            task = {"task_id": eid, "job_id": row["routes"][0]["job_id"],
                    "definition": D.index(doc, "jobs")[row["routes"][0]["job_id"]]["definition"],
                    "invocation": "Check the captured fixture input.", "criterion": row["acceptance"]["criterion"],
                    "inputs": [{"name": "input.txt", "media_type": "text/plain",
                                "content_base64": base64.b64encode(b"frozen fixture input").decode()}]}
            identity = {"task_id": eid, "task_evidence_ref": eid + "-frozen", "task_sha256": D.digest(task)}
            capture(identity["task_evidence_ref"], {"type": "skill-task", "scope_sha256": scope,
                "task_id": eid, "task_sha256": D.digest(task)}, {"task": task}, earlier(3), "captured-source")
            controls = {"positive_control": True, "negative_control": True,
                        "criterion": row["acceptance"]["criterion"], "output": "Captured fixture output."}
            for name, mode, seconds, outcome in ((eid, "with-skill", 2, "pass"), (eid + "-baseline", "without-skill", 1, "fail")):
                capture(name, {"type": "skill-run", "scope_sha256": scope, **identity,
                        "run_id": name, "mode": mode}, controls, earlier(seconds), result=outcome)
            capture(eid + "-judgement", {"type": "skill-comparison", "scope_sha256": scope, **identity,
                    "with_skill_evidence_ref": eid, "without_skill_evidence_ref": eid + "-baseline"},
                    {**controls, "verdict": "supports"}, at)
            common = {"at": at, "reason": "Captured fixture comparison"}
            comparison.update(tier="proven", proof_route="comparison", claim_evidence_refs=[claim], events=[
                {**common, "id": eid + "-claim-event", "action": "claim", "from_tier": "unproven", "to_tier": "claimed", "evidence_refs": [claim]},
                {**common, "id": eid + "-comparison-event", "action": "comparison", "from_tier": "claimed", "to_tier": "proven", "comparison": {
                    **identity, "with_skill_evidence_ref": eid, "without_skill_evidence_ref": eid + "-baseline",
                    "judgement_evidence_ref": eid + "-judgement", "verdict": "supports"}}])


def test_freshness_model():
    ctx = skill_fixture("freshness")
    doc, _ = D.load_current(ctx)
    a = V.resolve(ctx, "skill", "model-a-release")
    check(a["state"] == "prepared-delivery" and a["assurance_tier"] == "proven" and
          {s["resource_id"] for s in a["assurance_basis"]} == {"primary", "dependency"},
          "F3 prepared delivery qualifies each skill dependency for A")
    refuses(lambda: V.resolve(ctx, "skill", "model-b-release"), "F3 known B unqualified", codes=(1,))
    for model in (None, "latest"):
        refuses(lambda: V.resolve(ctx, "skill", model), "F3 missing/alias model", codes=(2,))
    acceptance = {"row_id": "skill", "caller_model_id": "model-b-release",
                  "resource_ids": [b["resource_id"] for b in D.expansion(doc, doc["rows"][0])["bindings"]],
                  "criterion": "exact-fixture"}
    delivered = V.resolve(ctx, "skill", "model-b-release", purpose="acceptance", acceptance_plan=acceptance)
    check(delivered["purpose"] == "acceptance-only" and delivered["qualified_delivery"] is False,
          "unqualified B may enter explicit acceptance without production delivery")
    activate(ctx, ["skill"])
    a = V.resolve(ctx, "skill", "model-a-release")
    check(a["state"] == "active", "F3 qualified active delivery")
    refuses(lambda: V.resolve(ctx, "skill", "model-b-release", cached=a), "fallback B cannot use A cache", codes=(1,))
    doc, _ = D.load_current(ctx)
    baseline = S.snapshot(ctx.home, [ctx.home / "trees"])
    bad_row = copy.deepcopy(doc["rows"][0])
    bad_row["freshness"]["skills"][0]["candidate"]["version_date"] = "2000-01-01"
    plan = {"id": "maintenance-stale-candidate", "expect_data": D.sha(ctx.data.read_bytes()),
            "scope": [str(ctx.home / "trees/primary")], "before": baseline, "declaration": [],
            "steps": [], "changes": {"rows": [bad_row]}, "allowed_roots": [str(ctx.home / "trees")]}
    before_files = filesystem_manifest(ctx.home)
    refuses(lambda: M.run(ctx, plan, D.digest(plan)), "stale update candidate held before reservation/install", ctx=ctx)
    check(filesystem_manifest(ctx.home) == before_files, "failed freshness leaves installed candidate bytes unchanged")
    for label, change in (
        ("old date", lambda s: s["candidate"].update(version_date="2000-01-01")),
        ("unknown date", lambda s: s["candidate"].update(version_date={"status": "unknown", "reason": "No source"})),
        ("wrong pin", lambda s: s["candidate"].update(pin_sha256="0" * 64)),
        ("wrong tree", lambda s: s["candidate"].update(skill_tree_sha256="0" * 64)),
        ("wrong model", lambda s: s["comparisons"][0].update(model_id="model-b-release")),
        ("no criterion evidence", lambda s: s["comparisons"][0]["events"].pop()),
    ):
        bad = copy.deepcopy(doc)
        change(bad["rows"][0]["freshness"]["skills"][1])
        if label == "wrong model":
            check(F.evaluate(bad, bad["rows"][0], ctx, "model-a-release")["tier"] == "unproven",
                  "freshness changed model has no reused assurance")
        else:
            refuses(lambda: F.evaluate(bad, bad["rows"][0], ctx, "model-a-release"), "freshness " + label, codes=(1,))
    bad = copy.deepcopy(doc)
    next(e for e in bad["evidence"] if e["id"] == "dependency-task")["kind"] = "publisher-claim"
    refuses(lambda: F.evaluate(bad, bad["rows"][0], ctx, "model-a-release"), "publisher-only claim insufficient")
    bad = copy.deepcopy(doc)
    next(e for e in bad["evidence"] if e["id"] == "dependency-task")["result"] = "fail"
    refuses(lambda: F.evaluate(bad, bad["rows"][0], ctx, "model-a-release"), "failed task evidence")
    W.commit(ctx, W.proposal(ctx, "deactivate", {"row_ids": ["skill"], "reason": "Add B evidence"}))
    doc, _ = D.load_current(ctx)
    for skill in doc["rows"][0]["freshness"]["skills"]:
        comparison = copy.deepcopy(skill["comparisons"][0])
        task = skill["resource_id"] + "-b-task"
        comparison.update(model_id="model-b-release", release_evidence_refs=["model-b-release"],
                          applicability_evidence_refs=[task])
        skill["comparisons"].append(comparison)
        skill["applicability_evidence"].append(task)
    bind_tasks(doc, ctx)
    bind_evidence(doc, ctx)
    save_doc(ctx, doc)
    check(V.resolve(ctx, "skill", "model-b-release")["caller_model_id"] == "model-b-release",
          "separately measured B evidence permits B")
    refuses(lambda: V.resolve(ctx, "skill", "model-a-release", cached=a), "stale exported view refused")
    doc, _ = D.load_current(ctx)
    doc["rows"][0]["output_judge"]["kind"] = "owner"
    bind_tasks(doc, ctx)
    bind_evidence(doc, ctx)
    refuses(lambda: F.evaluate(doc, doc["rows"][0], ctx, "model-a-release"), "taste requires human judgement")
    retired = W.commit(ctx, W.proposal(ctx, "retire", {"row_ids": ["skill"], "reason": "owner retirement"}))
    check(retired["rows"][0]["lifecycle"]["state"] == "retired", "skill retirement retains its record")
    refuses(lambda: V.resolve(ctx, "skill", "model-a-release"), "retired skill has no qualified delivery")


def test_crash_race():
    stages = ["before-pending", "after-pending", "before-data", "after-data",
              "before-receipt", "after-receipt", "before-page", "after-page", "before-clear", "after-clear"]
    for number, stage in enumerate(stages):
        ctx = fixture("crash-" + str(number))
        old, _ = D.load_current(ctx)
        page = copy.deepcopy(old["page"])
        page["metadata"]["title"] = "Committed candidate"
        p = W.proposal(ctx, "edit", {"page": page})
        class Interrupted(Exception):
            pass
        def hook(point):
            if point == stage:
                raise Interrupted(point)
        try:
            W.commit(ctx, p, hook=hook)
            raise AssertionError("failure injection not reached")
        except Interrupted:
            pass
        if ctx.pending.exists():
            refuses(lambda: D.load_current(ctx), "partial transaction never reads clean at " + stage, codes=(2,))
            outcome = W.recover(ctx)
            doc, _ = D.load_current(ctx)
            check(doc["revision"] in (old["revision"], old["revision"] + 1), "recovery old/new tuple at " + stage)
            check((doc["page"]["metadata"]["title"] == "Committed candidate") == (outcome == "new"),
                  "recovery projection matches authority at " + stage)
        else:
            check(D.load_current(ctx)[0]["revision"] in (0, 1), "no pending incomplete state at " + stage)
    for stage in ("before-data", "after-data"):
        base = fixture("seed-sentinel-" + stage)
        vault = base.vault.parent / "fresh"
        vault.mkdir()
        ctx = D.Context(vault, base.home, base.locks)
        def interrupt(point):
            if point == stage:
                raise RuntimeError("seed interrupted")
        try:
            W.commit(ctx, W.proposal(ctx, "seed"), hook=interrupt)
        except RuntimeError:
            pass
        outcome = W.recover(ctx)
        check((outcome == "old" and W.tuple_bytes(ctx) == [None, None, None]) or
              (outcome == "new" and D.load_current(ctx)[0]["revision"] == 0),
              "create-only seed recovery honours absent sentinels " + stage)
    ctx = fixture("corrupt-journal")
    def die(point):
        if point == "after-data":
            raise RuntimeError("interrupted")
    p = W.proposal(ctx, "edit", {})
    try:
        W.commit(ctx, p, hook=die)
    except RuntimeError:
        pass
    original = ctx.page.read_bytes()
    ctx.page.write_bytes(original + b"outside edit")
    refuses(lambda: W.recover(ctx), "recovery preserves unexpected bytes", ctx=ctx)
    ctx.page.write_bytes(original)
    pending = ctx.pending.read_bytes()
    ctx.pending.write_bytes(b"not JSON")
    refuses(lambda: W.recover(ctx), "corrupt journal never silently repaired", ctx=ctx)
    ctx.pending.write_bytes(pending)
    with patch.object(W, "publish", side_effect=PermissionError("recovery write failure")):
        try:
            W.recover(ctx)
        except PermissionError:
            check(ctx.pending.exists(), "failed recovery retains pending marker")
    W.recover(ctx)
    ctx = fixture("race")
    a, b = W.proposal(ctx, "edit", {}), W.proposal(ctx, "edit", {})
    W.commit(ctx, a)
    refuses(lambda: W.commit(ctx, b), "competing expected revision cannot lose update", codes=(3,), ctx=ctx)
    with W.lock(ctx.lock, ctx.lock_identity):
        refuses(lambda: W.commit(ctx, W.proposal(ctx, "edit", {})), "nonblocking lock contention", codes=(3,), ctx=ctx)
    with patch.object(W, "fcntl", None):
        refuses(lambda: W.commit(ctx, W.proposal(ctx, "edit", {})), "unsupported locking never falls back", codes=(2,), ctx=ctx)
    before = W.tuple_bytes(ctx)
    with patch.object(W, "fsync_directory", side_effect=OSError("unsupported durable primitive")):
        try:
            W.commit(ctx, W.proposal(ctx, "edit", {}))
            raise AssertionError("unsupported fsync accepted")
        except OSError:
            check(W.tuple_bytes(ctx) == before, "unsupported fsync leaves authoritative tuple unchanged")
    ctx = fixture("resource-race")
    doc, _ = D.load_current(ctx)
    add_cli(doc, ctx, "alpha")
    bind_evidence(doc, ctx)
    save_doc(ctx, doc)
    p = W.proposal(ctx, "activate", {"row_ids": ["alpha"], "reason": "race"})
    def remove(point):
        if point == "before-data":
            (ctx.home / "bin/alpha").unlink()
    refuses(lambda: W.commit(ctx, p, hook=remove), "resource removed after initial locked proof", ctx=ctx)
    if ctx.pending.exists():
        W.recover(ctx)
    check(D.load_current(ctx)[0]["rows"][0]["lifecycle"]["state"] == "prepared", "race did not activate")
    unlocked = {"rows": []}
    copy_a, copy_b = copy.deepcopy(unlocked), copy.deepcopy(unlocked)
    copy_a["rows"].append("A")
    copy_b["rows"].append("B")
    unlocked = copy_a
    unlocked = copy_b
    check(unlocked["rows"] == ["B"], "unlocked test double loses planted addition")
    ctx = fixture("preview-resource-race")
    doc, _ = D.load_current(ctx)
    add_cli(doc, ctx, "alpha")
    bind_evidence(doc, ctx)
    save_doc(ctx, doc)
    request = W.proposal(ctx, "activate", {"row_ids": ["alpha"], "reason": "preview race"})
    W.preview(ctx, request)
    (ctx.home / "bin/alpha").unlink()
    refuses(lambda: W.commit(ctx, request), "resource removed between preview and lock", ctx=ctx)
    ctx = fixture("process-additions")
    requests = []
    for name in ("alpha", "beta"):
        doc, _ = D.load_current(ctx)
        add_cli(doc, ctx, name)
        bind_evidence(doc, ctx)
        requests.append(W.proposal(ctx, "edit", {k: doc[k] for k in
            ("rows", "resources", "installations", "evidence", "jobs")}))
    exits = simultaneous_writers(ctx, requests)
    check(sorted(exits) == [0, 3], "two process additions: one committed, one explicit stale/busy refusal")
    doc, _ = D.load_current(ctx)
    check(len(doc["rows"]) == 1 and doc["rows"][0]["id"] in ("alpha", "beta"),
          "concurrent additions preserve the committed row")
    fresh = ctx.vault.parent / "seed-race"
    fresh.mkdir()
    initial = D.Context(fresh, ctx.home, ctx.locks)
    exits = simultaneous_writers(initial, [W.proposal(initial, "seed"), W.proposal(initial, "seed")])
    check(sorted(exits) == [0, 3] and D.load_current(initial)[0]["revision"] == 0,
          "two process seeds use no-replace publication")
    exits = simultaneous_writers(initial, [W.proposal(initial, "seed"), W.proposal(initial, "edit", {})])
    revision = D.load_current(initial)[0]["revision"]
    check(exits[0] == 3 and exits[1] in (0, 3) and revision == (1 if exits[1] == 0 else 0),
          "create-only seed cannot overwrite concurrent edit; busy refusal is explicit")
    if exits[1] == 3:
        W.commit(initial, W.proposal(initial, "edit", {}))
    check(D.load_current(initial)[0]["revision"] == 1, "fresh edit succeeds after refused seed")
    ctx = fixture("terminated-writer")
    ready_parent, ready_child = mp.Pipe()
    request = W.proposal(ctx, "edit", {})
    process = mp.Process(target=terminated_writer, args=(
        str(ctx.vault), str(ctx.home), str(ctx.locks), request, ready_child))
    process.start()
    try:
        check(ready_parent.poll(POLL_SECONDS) and ready_parent.recv() == "before-data",
              "writer process reached durable pending plus temporary data")
        process.terminate()
        process.join(POLL_SECONDS)
        check(not process.is_alive() and ctx.pending.is_file(), "terminated writer leaves durable journal")
        refuses(lambda: D.load_current(ctx), "terminated writer cannot read clean")
        check(W.recover(ctx) == "old", "terminated writer recovery selects old data")
        check(not list(ctx.data.parent.glob(".register-tmp-*")), "recognised orphan temporary cleaned under lock")
        D.load_current(ctx)
    finally:
        if process.is_alive():
            process.terminate()
            process.join()
    import uuid
    suspect = ctx.data.parent / (".register-tmp-" + str(uuid.uuid4()))
    suspect.symlink_to(ctx.data)
    refuses(lambda: W.commit(ctx, W.proposal(ctx, "edit", {})), "unexpected temporary symlink preserved", ctx=ctx)
    check(suspect.is_symlink(), "unknown temporary object not removed")


def terminated_writer(vault, home, locks, request, ready):
    ctx = D.Context(vault, home, locks)
    def pause(phase):
        if phase == "before-data":
            ready.send(phase)
            ready.recv()
    W.commit(ctx, request, hook=pause)


def simultaneous_writers(ctx, requests):
    children = []
    for i, request in enumerate(requests):
        path = ctx.home / ("proposal-" + str(i) + ".json")
        write(path, D.encoded(request))
        command = [sys.executable, "-B", str(Path(__file__).with_name("adopt_register.py")),
                   "--vault", str(ctx.vault), "--home", str(ctx.home), "--lock-root", str(ctx.locks),
                   "apply", "--proposal", str(path), "--expect-data", request["expect_data"],
                   "--expect-proposal", request["proposal_sha256"], "--write"]
        children.append(subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
    exits = []
    for child in children:
        output, errors = child.communicate(timeout=POLL_SECONDS)
        exits.append(child.returncode)
        print("WRITER_PROCESS " + json.dumps({"exit": child.returncode, "stdout": output, "stderr": errors}), flush=True)
    return exits


def maintenance_plan(ctx, name):
    doc, raw = D.load_current(ctx)
    path = ctx.home / ".claude/skills" / (name + ".txt")
    write(path, "before")
    before = S.snapshot(ctx.home)
    write(path, "after")
    after = S.snapshot(ctx.home)
    write(path, "before")
    artefact = ctx.vault / (name + "-target")
    write(artefact, "after")
    plan = {"id": "maintenance-" + name, "expect_data": D.sha(raw), "scope": [str(path)],
            "before": before, "declaration": S.changes(before, after),
            "steps": [{"kind": "replace-file", "path": str(path), "old_sha256": D.sha(b"before"),
                       "artefact": str(artefact), "new_sha256": D.sha(b"after"), "mode": 0o644,
                       "old_mode": stat.S_IMODE(path.stat().st_mode)}],
            "changes": {}, "allowed_roots": []}
    return plan


def refresh_plan(ctx, plan):
    plan = copy.deepcopy(plan)
    plan["expect_data"] = D.sha(ctx.data.read_bytes())
    before = S.snapshot(ctx.home)
    originals = [(Path(step["path"]), Path(step["path"]).read_bytes()) for step in plan["steps"]]
    for step in plan["steps"]:
        write(Path(step["path"]), Path(step["artefact"]).read_bytes(), step["mode"])
    after = S.snapshot(ctx.home)
    for path, raw in originals:
        write(path, raw)
    plan["before"], plan["declaration"] = before, S.changes(before, after)
    return plan


def maintenance_worker(vault, home, locks, plan, ready, resume):
    ctx = D.Context(vault, home, locks)
    def hold(phase, coordinator):
        if phase == "reserved":
            ready.send("reserved")
            resume.recv()
    try:
        result = M.run(ctx, plan, D.digest(plan), hook=hold)
        ready.send(result)
    except BaseException as exc:
        ready.send({"error": str(exc)})


def test_maintenance():
    ctx = fixture("maintenance")
    doc, _ = D.load_current(ctx)
    add_cli(doc, ctx, "alpha")
    bind_evidence(doc, ctx)
    save_doc(ctx, doc)
    activate(ctx, ["alpha"])
    p = maintenance_plan(ctx, "first")
    second = maintenance_plan(ctx, "second")
    p = refresh_plan(ctx, p)
    second = refresh_plan(ctx, second)
    # Reserve the existing executable too, without changing it.
    p["scope"].append(str(ctx.home / "bin/alpha"))
    parent_ready, child_ready = mp.Pipe()
    child_resume, parent_resume = mp.Pipe()
    process = mp.Process(target=maintenance_worker, args=(
        str(ctx.vault), str(ctx.home), str(ctx.locks), p, child_ready, child_resume))
    process.start()
    try:
        check(parent_ready.poll(POLL_SECONDS) and parent_ready.recv() == "reserved", "F1 process paused after atomic reservation")
        doc, _ = D.load_current(ctx)
        check(doc["rows"][0]["lifecycle"]["state"] == "prepared" and doc["rows"][0].get("maintenance_id"),
              "F1 old active row is prepared and reserved before first install write")
        refuses(lambda: activate(ctx, ["alpha"]), "F1 fresh-revision interposed activation", ctx=ctx)
        refuses(lambda: W.commit(ctx, W.proposal(ctx, "retire", {"row_ids": ["alpha"], "reason": "interposed"})),
                "F1 retirement cannot erase a live reservation", ctx=ctx)
        refuses(lambda: V.resolve(ctx, "alpha", None, purpose="describe"), "F1 even compatibility delivery held")
        changed = copy.deepcopy(doc)
        alias_row = add_cli(changed, ctx, "alias")
        alias_path = ctx.home / "bin/alias"
        alias_path.unlink()
        alias_path.symlink_to(ctx.home / "bin/alpha")
        bind_evidence(changed, ctx, [alias_row])
        refuses(lambda: save_doc(ctx, changed), "F1 new physical-alias binding cannot bypass hold", ctx=ctx)
        altered = copy.deepcopy(doc)
        altered["installations"][0]["pin"]["version"] = "1.0.1"
        refuses(lambda: save_doc(ctx, altered), "F1 reserved installation cannot be edited", ctx=ctx)
        second["expect_data"] = D.sha(ctx.data.read_bytes())
        check(set(p["scope"]).isdisjoint(second["scope"]), "F4 independent rows/files share only comparison domain")
        before_file = Path(second["steps"][0]["path"]).read_bytes()
        refuses(lambda: M.run(ctx, second, D.digest(second)), "F4 second operation refuses before mutation", codes=(3,), ctx=ctx)
        check(Path(second["steps"][0]["path"]).read_bytes() == before_file, "F4 prohibited concurrent write did not occur")
        refuses(lambda: M.run(ctx, p, D.digest(p), recovering=True), "recovery refuses live/paused guard", codes=(3,), ctx=ctx)
        parent_resume.send("continue")
        check(parent_ready.poll(POLL_SECONDS), "foreground maintenance completes")
        result = parent_ready.recv()
        check(result.get("outcome") == "target", "first measured interval completed: " + str(result))
        process.join(POLL_SECONDS)
        check(not process.is_alive(), "maintenance process exited")
    finally:
        if process.is_alive():
            process.terminate()
            process.join()
    doc, _ = D.load_current(ctx)
    check(not doc["maintenance"] and doc["rows"][0]["lifecycle"]["state"] == "prepared",
          "release remains prepared")
    activate(ctx, ["alpha"])
    check(D.load_current(ctx)[0]["rows"][0]["lifecycle"]["state"] == "active", "fresh activation succeeds after release")
    p2 = refresh_plan(ctx, second)
    check(M.run(ctx, p2, D.digest(p2))["outcome"] == "target", "F4 second succeeds with fresh proposal")
    p3 = maintenance_plan(ctx, "undeclared")
    def unrelated(phase, coordinator):
        if phase == "verifying":
            write(ctx.home / ".claude/settings.json", b'{"unrelated":true}')
    refuses(lambda: M.run(ctx, p3, D.digest(p3), hook=unrelated), "F4 unrelated undeclared change still fails", codes=(1,))
    doc, _ = D.load_current(ctx)
    check(doc["maintenance"][0]["status"] == "recovery-required", "undeclared change retains durable hold")
    # An in-process adapter cannot leave a mutation-capable child after termination.
    bad = copy.deepcopy(p3)
    bad["steps"] = [{"kind": "external-process", "argv": ["unsupported"]}]
    refuses(lambda: M.run(ctx, bad, D.digest(bad)), "escaping/external adapter refused before execution")
    for timing in ("reserved", "after-step"):
        ctx = fixture("maintenance-death-" + timing)
        p = maintenance_plan(ctx, "crash")
        ready_parent, ready_child = mp.Pipe()
        process = mp.Process(target=crashing_maintenance_worker, args=(
            str(ctx.vault), str(ctx.home), str(ctx.locks), p, timing, ready_child))
        process.start()
        try:
            check(ready_parent.poll(POLL_SECONDS) and ready_parent.recv() == timing, "coordinator reached death point " + timing)
            process.terminate()
            process.join(POLL_SECONDS)
            check(not process.is_alive(), "old in-process mutator cannot resume")
            held, _ = D.load_current(ctx)
            check(bool(held["maintenance"]), "coordinator death retains reservation")
            result = M.run(ctx, p, D.digest(p), recovering=True)
            check(result["outcome"] == ("original" if timing == "reserved" else "target"),
                  "recovery verifies actual original/target " + timing)
            obsolete = M.Coordinator(ctx, p)
            obsolete.held = True
            refuses(lambda: obsolete.step(p["steps"][0]), "stale generation cannot execute a mutation")
        finally:
            if process.is_alive():
                process.terminate()
                process.join()


def crashing_maintenance_worker(vault, home, locks, plan, timing, ready):
    ctx = D.Context(vault, home, locks)
    def pause(phase, coordinator):
        if phase == timing:
            ready.send(timing)
            ready.recv()
    M.run(ctx, plan, D.digest(plan), hook=pause)


def test_kinds():
    import adopt_kinds as K
    for kind in ("skill", "cli", "tool-server", "plugin"):
        request = {"kind": kind, "name": "fixture", "pin": {"type": "git-commit",
                   "origin": "https://example.test/fixture", "object_id": "a" * 40},
                   "scope": "local", "hooks_present": False, "level": "auto", "route": "use-directly"}
        planned = K.plan(request)
        check(planned["state"] == "planned" and not planned["commands"],
              "per-kind source pin produces manual plan without registry command " + kind)
        refuses(lambda: K.plan({**request, "scope": "user"}), "non-local scope refused " + kind)
        refuses(lambda: K.plan({**request, "hooks_present": True}), "hook level preserved " + kind)
    ctx = fixture("server")
    doc, _ = D.load_current(ctx)
    row = add_cli(doc, ctx, "server")
    row["kind"] = "tool-server"
    configs = []
    for rid in ("primary-config", "extra-config"):
        path = ctx.home / (rid + ".json")
        write(path, D.encoded({"mcpServers": {"fixture-server": {
            "command": str(ctx.home / "bin/server"), "args": [], "env": {}}}}))
        config = resource(rid, "server-config", path,
            {"format": "json", "server_id": "fixture-server", "scope": "local",
             "executable_resource_id": "server-binary", "arguments": [], "environment": [],
             "surface": "session"}, ["server-handshake"], "server-install")
        configs.append(config)
        doc["resources"].append(config)
        row["resource_bindings"].append({"role": "server-config", "resource_id": rid})
    bind_evidence(doc, ctx)
    save_doc(ctx, doc)
    (ctx.home / "extra-config.json").unlink()
    refuses(lambda: activate(ctx, ["server"]), "H2 every recorded extra server config required", ctx=ctx)
    write(ctx.home / "extra-config.json", (ctx.home / "primary-config.json").read_bytes())
    doc, _ = D.load_current(ctx)
    bind_evidence(doc, ctx)
    save_doc(ctx, doc)
    activate(ctx, ["server"])
    check(D.load_current(ctx)[0]["rows"][0]["lifecycle"]["state"] == "active", "complete local server control")
    for altered in ("server-id", "bad-args"):
        original = (ctx.home / "primary-config.json").read_bytes()
        write(ctx.home / "primary-config.json", D.encoded({"mcpServers": {
            "wrong-id" if altered == "server-id" else "fixture-server": {
                "command": str(ctx.home / "bin/server"), "args": "bad", "env": {}}}}))
        doc, _ = D.load_current(ctx)
        refuses(lambda: R.recheck(doc, doc["rows"][0], ctx), "server substituted identity/malformed launch " + altered)
        write(ctx.home / "primary-config.json", original)
    retired = W.commit(ctx, W.proposal(ctx, "retire", {"row_ids": ["server"], "reason": "owner retirement"}))
    check(retired["rows"][0]["lifecycle"]["state"] == "retired" and
          (ctx.home / "primary-config.json").is_file(), "server retirement retains configuration and history")
    ctx = fixture("plugin")
    doc, _ = D.load_current(ctx)
    root = ctx.home / "plugin"
    write(root / "manifest.json", b'{"hooks_present":false}')
    install = installation("plugin", [])
    inspected = resource("plugin-tree", "directory-tree", root,
        {"sha256": S.tree_hash(root), "use": "plugin inspection"}, ["file-content", "input-use"], install["id"])
    path = ctx.home / ".claude/settings.json"
    write(path, b'\xef\xbb\xbf{"enabledPlugins":{"fixture@market":true}}')
    enable = resource("plugin-enable", "plugin-enable", path,
        {"pointer": "/enabledPlugins/fixture@market", "plugin_id": "fixture@market", "enabled": True,
         "hooks_present": False, "inspected_tree_sha256": inspected["expected"]["sha256"],
         "inspection_resource_id": inspected["id"]}, ["plugin-inspection"], install["id"])
    install["resource_ids"] = [inspected["id"], enable["id"]]
    row = normal_row("plugin", [inspected, enable], "plugin")
    doc["rows"] = [row]
    doc["resources"] = [inspected, enable]
    doc["installations"] = [install]
    doc["jobs"] = [{"id": "plugin-job", "label": "Plugin", "definition": "Plugin fixture", "notes": []}]
    bind_evidence(doc, ctx)
    save_doc(ctx, doc)
    activate(ctx, ["plugin"])
    check(D.load_current(ctx)[0]["rows"][0]["lifecycle"]["state"] == "active", "actual plugin enable-proof BOM accepted")
    doc, _ = D.load_current(ctx)
    for raw in (b'{"enabledPlugins":{"fixture@market":false}}',
                b'{"enabledPlugins":{"fixture@market":null}}', b"\xff"):
        write(path, raw)
        refuses(lambda: R.recheck(doc, doc["rows"][0], ctx), "disabled/null/invalid-byte enable proof")
    bad = copy.deepcopy(doc)
    bad["resources"][1]["expected"]["hooks_present"] = True
    refuses(lambda: D.validate(bad), "hook plugin cannot be auto")
    write(path, b'\xef\xbb\xbf{"enabledPlugins":{"fixture@market":true}}')
    write(root / "hooks.json", b'{"hooks":{}}')
    altered = copy.deepcopy(doc)
    inspected = next(r for r in altered["resources"] if r["id"] == "plugin-tree")
    inspected["expected"]["sha256"] = S.tree_hash(root)
    enabling = next(r for r in altered["resources"] if r["id"] == "plugin-enable")
    enabling["expected"]["inspected_tree_sha256"] = inspected["expected"]["sha256"]
    refuses(lambda: R.observation(altered, altered["rows"][0], enabling, ctx), "actual hook cannot be labelled absent")
    (root / "hooks.json").unlink()
    write(root / "hidden-skill/SKILL.md", "---\nname: hidden-skill\n---\nFixture")
    inspected["expected"]["sha256"] = S.tree_hash(root)
    enabling["expected"]["inspected_tree_sha256"] = inspected["expected"]["sha256"]
    refuses(lambda: R.observation(altered, altered["rows"][0], enabling, ctx), "plugin skill cannot evade freshness closure")
    config_path = ctx.home / "class-routing.json"
    definition_path = ctx.home / "class-definition.md"
    write(definition_path, "Fixture class definition")
    doc["resources"].append(resource("class-definition", "file", definition_path,
        {"sha256": D.sha(definition_path.read_bytes()), "use": "class definition"},
        ["file-content", "input-use"], "plugin-install"))
    class_resource = resource("class", "class-binding", config_path,
        {"class_id": "worker", "definition_resource_id": "class-definition", "required_resource_ids": ["plugin-enable"]},
        ["class-launch"], "plugin-install")
    write(config_path, b'{"other-class":{}}')
    refuses(lambda: R.observation(doc, doc["rows"][0], class_resource, ctx), "class existence cannot prove another class")
    write(config_path, D.encoded({"worker": {"definition_resource_id": "class-definition",
                                           "required_resource_ids": ["plugin-enable"]}}))
    check(R.observation(doc, doc["rows"][0], class_resource, ctx)["type"] == "content",
          "exact class routing control")
    definition_path.unlink()
    refuses(lambda: R.observation(doc, doc["rows"][0], class_resource, ctx), "missing class definition refuses")
    retired = W.commit(ctx, W.proposal(ctx, "retire", {"row_ids": ["plugin"], "reason": "owner retirement"}))
    check(retired["rows"][0]["lifecycle"]["state"] == "retired" and path.is_file(),
          "plugin retirement does not silently edit settings")


def filesystem_manifest(root):
    result = {}
    for parent, directories, files in os.walk(root, followlinks=False):
        for name in sorted(directories + files):
            path = Path(parent) / name
            info = path.lstat()
            entry = {"mode": stat.S_IMODE(info.st_mode)}
            if path.is_symlink():
                entry["link"] = os.readlink(path)
            elif path.is_file():
                entry["sha256"] = D.sha(path.read_bytes())
            else:
                entry["directory"] = True
            result[str(path.relative_to(root))] = entry
    return result


def test_no_write():
    ctx = fixture("read-only")
    paths = sorted(ctx.vault.rglob("*"), key=lambda p: len(p.parts), reverse=True)
    for path in paths:
        path.chmod(0o500 if path.is_dir() else 0o400)
    ctx.vault.chmod(0o500)
    before = filesystem_manifest(ctx.vault.parent)
    try:
        doc, _ = D.load_current(ctx)
        S.compare(S.snapshot(ctx.home), S.snapshot(ctx.home), [])
        render(doc)
        D.validate(doc)
        W.preview(ctx, W.proposal(ctx, "edit", {}))
        from adopt_acceptance import audit
        check(audit(ctx)["findings"] == [], "empty row audit completed with controls")
        refuses(lambda: V.resolve(ctx, "missing", "model-a-release"), "reader failure branch no-write")
        refuses(lambda: F.evaluate(doc, {}, ctx, "unknown"), "freshness failure branch no-write")
        after = filesystem_manifest(ctx.vault.parent)
        check(before == after and any(x.endswith("capability-register.json") for x in before),
              "T-no-write complete hashes/modes/link manifest unchanged; known data control")
        # Complete explicit source inventory, including permitted writers and harnesses.
        pattern = re.compile(r"\b(?:write_text|write_bytes|mkdir|unlink|chmod|replace|Popen|run)\s*\(|\b(?:subprocess|requests)\b|open\([^\\n]*[\"'][wax]")
        inventory = {}
        for source in sorted(Path(__file__).parent.glob("*.py")):
            hits = [(i, line.strip()) for i, line in enumerate(source.read_text().splitlines(), 1) if pattern.search(line)]
            inventory[source.name] = hits
        pure = ("adopt_data.py", "adopt_render.py", "adopt_resources.py", "adopt_snapshot.py",
                "adopt_freshness.py", "adopt_manifest.py", "adopt_migrate.py",
                "adopt_acceptance.py", "adopt_kinds.py", "adopt_compat_v1.py")
        string_replacements = {
            'return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))',
            '"&#" + str(ord(c)) + ";" for c in str(text)).replace("\\n", "&#10;")',
            'part = part.replace("~1", "/").replace("~0", "~")',
            'require(value is True and expected["pointer"].split("/")[-1].replace("~1", "/").replace("~0", "~")',
            'out.update(pointer_nodes(v, pointer + "/" + k.replace("~", "~0").replace("/", "~1")))',
            'require(all(address + "/" + k.replace("~", "~0").replace("/", "~1") in value["state"]',
        }
        for name in pure:
            code_hits = [(i, line) for i, line in inventory[name]
                         if line not in string_replacements]
            check(not code_hits, "source write/process scan: " + name)
        planted = "target.write_text('planted')"
        check(bool(pattern.search(planted)) and bool(pattern.search("os.replace(a, b)")),
              "source-grep planted writer and replacement positive controls")
        print("SOURCE_SCAN " + json.dumps(inventory, sort_keys=True), flush=True)
        print("NO_WRITE_MANIFEST " + json.dumps({"before": before, "after": after}, sort_keys=True), flush=True)
    finally:
        ctx.vault.chmod(0o700)
        for path in sorted(ctx.vault.rglob("*"), key=lambda p: len(p.parts)):
            path.chmod(0o700 if path.is_dir() else 0o600)


def test_consumers():
    ctx = fixture("consumers")
    script = Path(__file__).parent
    lint = script.parent / "lint/check_register.py"
    commands = [
        [script / "adopt_register.py", "--vault", ctx.vault, "--home", ctx.home, "check"],
        [script / "adopt_acceptance.py", "--vault", ctx.vault, "--home", ctx.home],
        [script / "adopt_snapshot.py", "snapshot", "--home", ctx.home],
        [lint, "--capability", "--vault", ctx.vault, "--home", ctx.home],
    ]
    upstream = ctx.vault / "fixture-upstream"
    write(upstream / "README.md", "# Fixture\nLocal inert test data.\n")
    write(upstream / "SKILL.md", "---\nname: fixture\ndescription: A fixture\n---\nRead inert fixture data.\n")
    commands.extend([
        [script / "adopt_fingerprint.py", upstream],
        [script / "adopt_wrapper.py", "--name", "fixture", "--upstream", upstream,
         "--level", "by-name", "--description", "Only when named", "--skills-root", ctx.home / ".claude/skills"],
    ])
    before = filesystem_manifest(ctx.vault.parent)
    for command in commands:
        result = subprocess.run([sys.executable, "-B"] + list(map(str, command)),
                                capture_output=True, text=True)
        check(result.returncode == 0 and ("control" in result.stdout or "dry-run" in result.stdout),
              "supplied read consumer " + Path(command[0]).name)
    check(before == filesystem_manifest(ctx.vault.parent), "all exercised CLI consumers wrote nothing")
    for name in ("register", "acceptance", "snapshot", "freshness", "manifest", "migrate", "kinds"):
        result = subprocess.run([sys.executable, "-B", str(script / ("adopt_" + name + ".py"))],
                                capture_output=True, text=True)
        check(result.returncode == 2 and "PROBE FAILED" in result.stdout + result.stderr,
              "missing CLI premise reports PROBE FAILED: " + name)
    malformed = ctx.vault / "malformed-snapshot.json"
    bad = S.snapshot(ctx.home)
    bad["scope"]["home"] = 123
    write(malformed, D.encoded(bad))
    declaration = ctx.vault / "declaration.json"
    write(declaration, b"[]")
    before = filesystem_manifest(ctx.vault.parent)
    result = subprocess.run([sys.executable, "-B", str(script / "adopt_snapshot.py"), "compare",
                             "--before", str(malformed), "--after", str(malformed),
                             "--declaration", str(declaration)], capture_output=True, text=True)
    check(result.returncode == 2 and "PROBE FAILED" in result.stdout,
          "malformed snapshot type is failed premise, not partial/clean output")
    check(before == filesystem_manifest(ctx.vault.parent), "malformed comparison CLI writes nothing")
    absent = ctx.vault.parent / "missing-register"
    absent.mkdir()
    result = subprocess.run([sys.executable, "-B", str(lint), "--capability",
                             "--vault", str(absent), "--home", str(ctx.home)], capture_output=True, text=True)
    check(result.returncode == 2 and "PROBE FAILED" in result.stdout, "lint missing authority cannot report n/a")
    spec = importlib.util.spec_from_file_location("fixture_lint", lint)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    results = module.check(module.CONTROL_REGISTER)
    check(len(results[2]) == 3 and len(results[3]) == 1, "retained known-issues control behaviour")
    # Labelled unfolded-design models, distinct from execution of the stopped build.
    old_state = "prepared"
    old_state = "active"  # No reservation prevents the interposed fresh activation.
    check(old_state == "active", "F1 unfolded-design trace admits active during installation")
    old_hash = D.digest({"page": "prepared", "output": ""})
    check(old_hash != D.digest({"page": "active", "output": ""}),
          "F2 unfolded-design tree-content trace invalidates its own page commit")
    signature = ("row", "purpose", "authorisation")
    check("caller_model_id" not in signature, "F3 unfolded-design API trace lacks a model discriminator")
    print("DESIGN_BASELINE unfolded specification: F1/F2/F3 are design counterexamples, "
          "not old implementation runs; the run evidence records the reviewed source hash", flush=True)


def test_migration(source, mapping):
    raw, mapping = source.read_bytes(), D.read_json(mapping)
    doc = G.migration_document(raw, mapping, D.now())
    result = G.verify_coverage(raw, doc, mapping)
    check(result["source_rows"] == len(mapping["rows"]) and
          result["covered_bytes"] == len(raw) and not result["unexplained_facts"], "migration complete forward/reverse ledger")
    for label, mutate in (
        ("row", lambda x: x["rows"].pop()),
        ("cell", lambda x: x["rows"][0]["notes"].pop()),
        ("prose", lambda x: x["page"]["prose_blocks"].pop()),
        ("route", lambda x: x["rows"][0]["routes"].update(reason="invented route")),
        ("state", lambda x: x["rows"][0]["lifecycle"].update(original_state_text="active")),
        ("extra fact", lambda x: x["rows"][0]["notes"].append(note("invented", "Unsupported fact"))),
    ):
        bad = copy.deepcopy(doc)
        mutate(bad)
        refuses(lambda: G.verify_coverage(raw, bad, mapping), "loss accounting catches omitted/invented " + label)
    if mapping["qualifications"]:
        bad = copy.deepcopy(doc)
        row = next(r for r in bad["rows"] if any(n["supersedes_note_ids"] for n in r["notes"]))
        row["notes"] = [n for n in row["notes"] if not n["supersedes_note_ids"]]
        refuses(lambda: G.verify_coverage(raw, bad, mapping), "omitted superseding note")
    for label in ("row", "member"):
        bad = copy.deepcopy(mapping)
        if label == "row":
            bad["rows"].pop()
        else:
            group = next(r for r in bad["rows"] if len(r["members"]) > 1)
            group["members"].pop()
        refuses(lambda: G.migration_document(raw, bad, D.now()), "mapping omission " + label)
    ctx = fixture("migration")
    # Initial import requires absence, so use a fresh vault separate from the seed.
    vault = ctx.vault.parent / "import"
    vault.mkdir()
    ctx = D.Context(vault, ctx.home, ctx.locks)
    write(ctx.page, raw)
    request = W.proposal(ctx, "migrate", {"source_sha256": D.sha(raw), "mapping": mapping})
    ctx.page.write_bytes(raw + b"\n")
    refuses(lambda: W.commit(ctx, request), "changed migration base", ctx=ctx)
    ctx.page.write_bytes(raw)
    migrated = W.commit(ctx, request)
    check((ctx.objects / D.sha(raw)).read_bytes() == raw, "source archive restores original byte-exact")
    check(all(r["lifecycle"]["state"] == "legacy-recorded" for r in migrated["rows"]), "migration invents no active state")
    check(not any(migrated["policy"]["extensions"].values()), "migration extensions explicitly off")
    refuses(lambda: W.commit(ctx, request), "second migration refuses", ctx=ctx)
    compatibility = V.resolve(ctx, migrated["rows"][0]["id"], None, purpose="describe")
    check(compatibility["qualified_delivery"] is False and compatibility["legacy_findings"],
          "legacy compatibility preserves notes without inventing qualification")
    print("MIGRATION " + json.dumps(result, sort_keys=True), flush=True)


def old_discriminators(build):
    copied = ROOT / "stopped-copy"
    shutil.copytree(build, copied)
    fixtures = ROOT / "stopped-fixtures"
    fixtures.mkdir()
    result = subprocess.run([sys.executable, "-B", str(Path(__file__).with_name("test_stopped.py")),
                             "--build", str(copied), "--fixture", str(fixtures)], capture_output=True,
                            text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", flush=True)
    check(result.returncode == 0 and "BASELINE reproduced 4/4" in result.stdout,
          "stopped H1/H2/H3a/H3b prohibited outcomes executed on isolated copy")


def reg3_depth():
    import test_reg3_depth
    root = ROOT / "reg3-depth"
    root.mkdir()
    result = test_reg3_depth.run(root, sys.modules[__name__])
    check(result["failed"] == 0, "REG3 depth cases and controls passed")


def reg3_basic():
    import test_reg3_basic
    root = ROOT / "reg3-basic"
    root.mkdir()
    result = test_reg3_basic.run(root, sys.modules[__name__])
    check(result["failed"] == 0, "REG3 exact-kind and conditional model-gate cases passed")


def reg3_snapshot():
    import test_reg3_snapshot
    root = ROOT / "reg3-snapshot"
    root.mkdir()
    for result in test_reg3_snapshot.run_cases(S, root):
        check(result["passed"], "REG3 F3 " + result["case"])


def previous_regressions(previous):
    copied = ROOT / "previous-reviewed-copy"
    shutil.copytree(previous, copied)
    directory = Path(__file__).parent
    summaries = {}
    observations = {}
    for name in ("depth", "basic"):
        process = subprocess.run([sys.executable, "-B", str(directory / ("test_reg3_" + name + ".py")),
                                  "--build", str(copied / "adopt")], capture_output=True, text=True,
                                 env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        print("PREVIOUS_NATIVE " + name, flush=True)
        for line in (process.stdout + process.stderr).splitlines():
            print("PREVIOUS | " + line, flush=True)
        check(process.returncode == 1, "previous " + name + " regression assertions fail natively")
        summaries[name] = next(json.loads(line[7:]) for line in process.stdout.splitlines()
                               if line.startswith("COUNTS "))
        for line in process.stdout.splitlines():
            if line.startswith("OBSERVED "):
                value = json.loads(line[9:])
                observations[value["case"]] = value
    check(observations["REG3-F1"]["edit_accepted"] and observations["REG3-F1"]["state"] == "active" and
          not observations["REG3-F1"]["evidence_bound_digest_changed"],
          "previous F1 actually commits failed evidence while active")
    check(observations["REG3-F1-final"]["commit_accepted"] and observations["REG3-F1-final"]["data_changed"],
          "previous F1 actually publishes after task artefact revocation")
    check(observations["REG3-F1-recovery"]["recovery_accepted"] and
          not observations["REG3-F1-recovery"]["pending_retained"],
          "previous F1 recovery actually clears revoked active transaction")
    check(observations["REG3-F2"]["activation_accepted"] and
          not observations["REG3-F2"]["named_carrier_present"] and
          observations["REG3-F2"]["spare_carrier_present"],
          "previous F2 actually activates without the named carrier")
    check(observations["REG3-F6"]["installed_A_unchanged"] and observations["REG3-F6"]["different_candidate"] and
          "content mismatch primary" in observations["REG3-F6"]["assessment_error"],
          "previous F6 fails on installed A bytes, not a missing command or plan field")
    basic = {item["case"]: item for item in summaries["basic"]["cases"]}
    check("accepted prohibited case" in basic["REG3-F4"]["error"],
          "previous F4 actually accepts a directory declared as a file")
    check("missing, alias or unknown caller-model identity" in basic["REG3-F5-delivery"]["error"],
          "previous F5 rejects a non-skill CLI on the model-release gate")
    scratch = ROOT / "previous-typed-snapshot"
    scratch.mkdir()
    process = subprocess.run([sys.executable, "-B", str(directory / "test_reg3_snapshot.py"),
                              "--module-dir", str(copied / "adopt"), "--scratch", str(scratch)],
                             capture_output=True, text=True)
    print("PREVIOUS_NATIVE snapshot", flush=True)
    for line in (process.stdout + process.stderr).splitlines():
        print("PREVIOUS | " + line, flush=True)
    expected = [
        "FAIL " + direction + ": " + suffix
        for direction in ("true-to-one", "one-to-true", "false-to-zero", "zero-to-false")
        for suffix in ("typed pointer event", "raw-only declaration refused")]
    expected += ["FAIL " + direction + ": wrongly typed " + field + " declaration refused"
                 for direction in ("true-to-false", "false-to-true") for field in ("old", "new")]
    check(process.returncode == 1 and all(line in process.stdout.splitlines() for line in expected),
          "previous F3 misses typed pointer events and accepts wrongly typed declarations")


def reg4():
    import test_reg4
    root = ROOT / "reg4"
    root.mkdir()
    result = test_reg4.run(root, sys.modules[__name__])
    check(result["failed"] == 0, "REG4 complete installation and symlink closure cases passed")


def previous_reg4_regressions(previous):
    copied = ROOT / "reg4-reviewed-copy"
    shutil.copytree(previous, copied)
    before = filesystem_manifest(copied)
    process = subprocess.run([sys.executable, "-B", str(Path(__file__).with_name("test_reg4.py")),
                              "--build", str(copied / "adopt")], capture_output=True, text=True,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    print("PREVIOUS_NATIVE REG4", flush=True)
    for line in (process.stdout + process.stderr).splitlines():
        print("PREVIOUS | " + line, flush=True)
    check(process.returncode == 1, "REG4 previous regression assertions fail natively")
    summary = next(json.loads(line[7:]) for line in process.stdout.splitlines()
                   if line.startswith("COUNTS "))
    observations = {item["case"]: item for item in
                    (json.loads(line[9:]) for line in process.stdout.splitlines()
                     if line.startswith("OBSERVED "))}
    indirect = ("binding", "run-needs", "dependency")
    snapshot_gaps = ("all-targets", "file-target", "directory-target", "empty-target",
                     "nested-target", "root-target", "target-json", "target-absent",
                     "target-logical", "target-resolved")
    expected = {"N1-" + route + "-" + state for route in indirect for state in ("prepared", "active")}
    expected |= {"N1-publication-" + route for route in indirect}
    expected |= {"N2-" + variant for variant in snapshot_gaps}
    check({c["case"] for c in summary["cases"] if c["result"] == "FAIL"} == expected and
          summary["failed"] == len(expected), "REG4 previous fails exactly the planted closure gaps")
    for route in indirect:
        for state in ("prepared", "active"):
            item = observations["N1-" + route + "-" + state]
            check(item["accepted"] and item["indirect"] and item["state"] == state,
                  "REG4 previous accepts unresolved indirect pin: " + route + " " + state)
        item = observations["N1-publication-" + route]
        check(item["activation_accepted"] and item["state"] == "active" and not item["tuple_unchanged"],
              "REG4 previous actually publishes unresolved-pin activation: " + route)
    for variant in snapshot_gaps:
        item = observations["N2-" + variant]
        check(item["accepted"] and item["valid_digests"] and item["comparison"]["findings"] == 0 and
              item["comparison"]["control_hits"] > 0,
              "REG4 previous actually compares malformed target inventory clean: " + variant)
    controls = [c for c in summary["cases"] if c["case"] not in expected]
    check(controls and all(c["result"] == "PASS" for c in controls),
          "REG4 previous direct-pin, child-omission and observed-change controls pass")
    check(filesystem_manifest(copied) == before and bool(before),
          "REG4 previous source copy unchanged during native replay")


def reg5():
    import test_reg5
    root = ROOT / "reg5"
    root.mkdir()
    result = test_reg5.run(root, sys.modules[__name__])
    check(result["failed"] == 0, "REG5 complete installation identity cases passed")


def previous_reg5_regressions(previous):
    copied = ROOT / "reg5-reviewed-copy"
    shutil.copytree(previous, copied)
    before = filesystem_manifest(copied)
    process = subprocess.run([sys.executable, "-B", str(Path(__file__).with_name("test_reg5.py")),
                              "--build", str(copied / "adopt")], capture_output=True, text=True,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    print("PREVIOUS_NATIVE REG5", flush=True)
    for line in (process.stdout + process.stderr).splitlines():
        print("PREVIOUS | " + line, flush=True)
    check(process.returncode == 1, "REG5 previous regression assertions fail natively")
    summary = next(json.loads(line[7:]) for line in process.stdout.splitlines()
                   if line.startswith("COUNTS "))
    observations = {item["case"]: item for item in
                    (json.loads(line[9:]) for line in process.stdout.splitlines()
                     if line.startswith("OBSERVED "))}
    expected = {"N3-empty-direct", "N3-row-owned-member", "N3-complete-closure"}
    check({c["case"] for c in summary["cases"] if c["result"] == "FAIL"} == expected and
          summary["failed"] == len(expected), "REG5 previous fails exactly the installation identity gaps")
    for name in ("N3-empty-direct", "N3-row-owned-member"):
        item = observations[name]
        check(item["commit_accepted"] and not item["digest_changed"] and item["state"] == "active" and
              item["pin"] == "2.0.0" and item["activation_unchanged"] and
              item["physical_recheck_passed"] and not item["tuple_unchanged"],
              "REG5 previous actually publishes a changed pin with retained activation: " + name)
    check(observations["N3-complete-closure"]["pin_changes"] ==
          {"delivery-install": True, "empty-install": False, "unrelated-install": False},
          "REG5 previous digest omits the named empty installation and includes the owned one")
    controls = [c for c in summary["cases"] if c["case"] not in expected]
    check(controls and all(c["result"] == "PASS" for c in controls),
          "REG5 previous owned/binding/run-needs controls and unrelated edits pass")
    check(filesystem_manifest(copied) == before and bool(before),
          "REG5 previous source copy unchanged during native replay")


INPUTS = {}


def o5_contracts():
    command = [sys.executable, "-B", str(Path(__file__).with_name("test_o5.py")),
               "--build", str(Path(__file__).resolve().parent.parent)]
    if INPUTS.get("instance_data"):
        command += ["--instance-data", str(INPUTS["instance_data"])]
    process = subprocess.run(command, capture_output=True, text=True)
    print(process.stdout + process.stderr, end="", flush=True)
    check(process.returncode == 0, "O5 complete acceptance cases and read-only controls")


def o5_integration():
    import test_o5_integration
    test_o5_integration.run(sys.modules[__name__])


def generated_dates():
    """The generated-register family: dates, body digest, navigation, migration and readers.
    Hook-dependent cases run only with --stamp-hook; outside the vault they are not applicable."""
    command = [sys.executable, "-B", str(Path(__file__).with_name("test_generated_dates.py")),
               "--adopt-dir", str(Path(__file__).resolve().parent)]
    for key, value in sorted(INPUTS.items()):
        if value:
            command += ["--" + key.replace("_", "-"), str(value)]
    process = subprocess.run(command, capture_output=True, text=True,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    for line in (process.stdout + process.stderr).splitlines():
        print("GD | " + line, flush=True)
    lines = process.stdout.splitlines()
    check(process.returncode == 0 and lines and re.fullmatch(r"PASS (\d+)/\1", lines[-1]) is not None,
          "generated-register family executed and passed: " + (lines[-1] if lines else "no output"))
    absent = [line for line in lines if line.startswith("NOT APPLICABLE: hook absent")]
    if absent:
        print("NOT APPLICABLE hook-dependent cases: hook absent (" + str(len(absent)) +
              "); the vault's hook suite runs them", flush=True)


def family(name, function):
    global FAILURES
    before = COUNT
    print("\nCASE " + name, flush=True)
    try:
        function()
        result = {"family": name, "result": "PASS", "assertions": COUNT - before}
    except Exception as exc:
        FAILURES += 1
        traceback.print_exc(file=sys.stdout)
        result = {"family": name, "result": "FAIL", "assertions": COUNT - before, "error": str(exc)}
    RESULTS.append(result)
    print("RESULT " + json.dumps(result, sort_keys=True), flush=True)


def main():
    global ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument("--stopped-build")
    parser.add_argument("--previous-build")
    parser.add_argument("--reg4-build")
    parser.add_argument("--reg5-build")
    parser.add_argument("--source")
    parser.add_argument("--mapping")
    for name in ("stamp-hook", "audit-pools", "required-sections", "link-check", "lint-adapter",
                 "instance-data", "demo-instance", "deep-lint-skill", "lint-skill"):
        parser.add_argument("--" + name)
    args = parser.parse_args()
    for key in ("stamp_hook", "audit_pools", "required_sections", "link_check", "lint_adapter",
                "instance_data", "demo_instance", "deep_lint_skill", "lint_skill"):
        INPUTS[key] = getattr(args, key)
    if not os.environ.get("TMPDIR"):
        raise SystemExit("PROBE FAILED: explicit TMPDIR is required")
    ROOT = Path(subprocess.check_output(["/usr/bin/mktemp", "-d", os.path.join(os.environ["TMPDIR"], "adopt.XXXXXXXX")], text=True).strip())
    try:
        family("T-schema", test_schema)
        family("H1 T-edits T-render", test_h1_edits_render)
        family("H2 T-proof", test_h2_proof)
        family("H3a H3b T-snapshot", test_snapshot)
        family("T-routes T-core-extensions", test_routes_extensions)
        family("F2-workspace", test_workspace)
        family("F3-caller-model T-freshness", test_freshness_model)
        family("T-crash T-race", test_crash_race)
        family("F1-maintenance F4-domain-guard", test_maintenance)
        family("T-kinds", test_kinds)
        family("T-consumers supplied adapters; unfolded traces", test_consumers)
        family("CR-REG3 F1 F2 F6 depth regressions", reg3_depth)
        family("CR-REG3 F3 typed snapshot regressions", reg3_snapshot)
        family("CR-REG3 F4 F5 kind and model regressions", reg3_basic)
        family("CR-REG4 N1 N2 closure regressions", reg4)
        family("CR-REG5 N3 installation identity regressions", reg5)
        family("O5 tier and input contracts", o5_contracts)
        family("O5 writer and recovery integration", o5_integration)
        family("GD generated register dates, digest and navigation", generated_dates)
        if args.source and args.mapping:
            family("T-migration", lambda: test_migration(Path(args.source), Path(args.mapping)))
        else:
            print("UNRUN T-migration: source and reviewed mapping not supplied", flush=True)
        if args.stopped_build:
            family("stopped HIGH discriminators", lambda: old_discriminators(Path(args.stopped_build)))
        else:
            print("UNRUN stopped discriminators: stopped build not supplied", flush=True)
        if args.previous_build:
            family("CR-REG3 reviewed-build discriminators", lambda: previous_regressions(Path(args.previous_build)))
        else:
            print("UNRUN CR-REG3 regressions: previous reviewed build not supplied", flush=True)
        if args.reg4_build:
            family("CR-REG4 reviewed-build discriminators", lambda: previous_reg4_regressions(Path(args.reg4_build)))
        else:
            print("UNRUN CR-REG4 regressions: last reviewed build not supplied", flush=True)
        if args.reg5_build:
            family("CR-REG5 reviewed-build discriminators", lambda: previous_reg5_regressions(Path(args.reg5_build)))
        else:
            print("UNRUN CR-REG5 regressions: last reviewed build not supplied", flush=True)
        family("T-no-write", test_no_write)
        print("COUNTS " + json.dumps({"assertions": COUNT, "families": RESULTS}, sort_keys=True))
        # The external cutover manifest-schema.md requires is its own registered work: no run of this
        # suite can execute it, so it is named and never counted.
        outside = ["T-consumers: live update/install, launcher, setup/export/deep-lint sources and integration grants"]
        missing = []
        if not (args.source and args.mapping):
            missing.append("T-migration: live-page copy and reviewed mapping")
        if not args.stopped_build:
            missing.append("stopped HIGH discriminators: stopped build")
        if not args.previous_build:
            missing.append("CR-REG3 reviewed-build discriminators: previous build")
        if not args.reg4_build:
            missing.append("CR-REG4 reviewed-build discriminators: last reviewed build")
        if not args.reg5_build:
            missing.append("CR-REG5 reviewed-build discriminators: last reviewed build")
        for gap in outside:
            print("UNRUN (outside the tally) " + gap, flush=True)
        for gap in missing:
            print("UNRUN REQUIRED " + gap, flush=True)
        print(f"EXECUTED {'FAIL' if FAILURES else 'PASS'} {len(RESULTS) - FAILURES}/{len(RESULTS)} families; "
              f"{COUNT} assertions", flush=True)
        total = len(RESULTS) + len(missing)
        failed = FAILURES + len(missing)
        print(f"FAIL {failed}/{total}" if failed else f"PASS {total}/{total}", flush=True)
        return 1 if failed else 0
    finally:
        shutil.rmtree(ROOT)


if __name__ == "__main__":
    mp.set_start_method("spawn")
    sys.exit(main())
