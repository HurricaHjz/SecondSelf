#!/usr/bin/env python3
"""Sole writer. One writing host; advisory locks coordinate cooperating processes.

A non-cooperating edit after the final comparison may be lost. Read commands
create neither locks nor caches. Installation adapters are separately scoped.
"""
import argparse
import copy
from contextlib import contextmanager
import difflib
try:
    import fcntl
except ImportError:
    fcntl = None
import os
from pathlib import Path
import stat
import sys
import uuid
from adopt_data import (Context, Problem, Finding, Conflict, require, sha, digest,
                        decode, encoded, read_json, validate, load_current, optional_bytes,
                        now, index, expansion, control, cli_error, calendar_day, local_instant,
                        timestamp)
from adopt_render import (render, render_layout1, body_bytes, layout2_body, split_page,
                          body_instants, CURRENT_LAYOUT)
from adopt_resources import (activate_record, blocked, footprint_check, prove,
                             stable_checks, overlaps)


def proposal_instant():
    """The proposal clock, restated in this machine's local zone with its numeric offset, so the
    proposal records the local calendar day it was made on. Tests freeze `now` in process."""
    return local_instant(now())


def seed_document(at=None):
    at = at or proposal_instant()
    day = calendar_day(at)
    # Two checked how-to runs: set by judgement, unmeasured.
    return {
        "schema_version": 2, "revision": 0, "register_id": str(uuid.uuid4()),
        "commit": {"id": str(uuid.uuid4()), "at": at, "operation": "seed",
                   "proposal_sha256": "0" * 64},
        "page": {"metadata": {"title": "Capability register", "type": "development",
                 "confidence": "low", "audited": day, "created": day, "updated": day,
                 "tags": ["capabilities"], "aliases": []}, "layout_version": CURRENT_LAYOUT,
                 "prose_blocks": []},
        "jobs": [], "installations": [], "resources": [], "maintenance": [], "rows": [], "evidence": [],
        "policy": {"model_targets": [], "freshness_rule_version": 2, "config_exclusions": [],
                   "how_to_successes_required": 2, "owner_identity": None,
                   "extensions": {"legacy_execution_gate": False, "category_execution_gates": False},
                   "extension_decision_refs": {}}}


def proposal(ctx, operation, changes=None, observed=None):
    if operation in ("seed", "migrate"):
        expected, revision = "absent", -1
    else:
        parent, raw = (committed_parent(ctx) if operation in (
            "reconcile-page", "reconcile-data") else upgrade_parent(ctx)
            if operation == "upgrade-freshness" else load_current(ctx))
        expected, revision = sha(raw), parent["revision"]
    value = {"operation": operation, "changes": changes or {}, "expect_data": expected,
             "expect_revision": revision, "at": proposal_instant(), "commit_id": str(uuid.uuid4())}
    if observed is not None:
        value["observed"] = observed
    value["proposal_sha256"] = digest(value)
    return value


def verify_proposal(value):
    required = {"operation", "changes", "expect_data", "expect_revision", "at", "commit_id",
                "proposal_sha256"}
    require(type(value) is dict and required <= set(value) <= required | {"observed"},
            "malformed proposal")
    require(value["proposal_sha256"] == digest({k: v for k, v in value.items()
            if k != "proposal_sha256"}), "proposal digest mismatch", Conflict)


def fsync_directory(path):
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def directories(path):
    missing = []
    here = Path(path)
    while not here.exists():
        missing.append(here)
        here = here.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        fsync_directory(directory.parent)


def publish(path, raw, create=False, hook=None, label="object"):
    path = Path(path)
    directories(path.parent)
    temporary = path.parent / (".register-tmp-" + str(uuid.uuid4()))
    try:
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fchmod(stream.fileno(), 0o600)
            os.fsync(stream.fileno())
        require(temporary.read_bytes() == raw, "temporary read-back differs")
        if hook:
            hook("before-" + label)
        if create:
            os.link(temporary, path)
            temporary.unlink()
        else:
            os.replace(temporary, path)
        fsync_directory(path.parent)
        if hook:
            hook("after-" + label)
    finally:
        if temporary.exists():
            temporary.unlink()


def archive(ctx, raw):
    if raw is None:
        return None
    name = sha(raw)
    target = ctx.objects / name
    existing = optional_bytes(target)
    if existing is None:
        publish(target, raw, create=True)
    else:
        require(existing == raw, "content-addressed object mismatch")
    return name


def object_bytes(ctx, key):
    if key is None:
        return None
    require(isinstance(key, str) and len(key) == 64 and all(c in "0123456789abcdef" for c in key),
            "invalid object name")
    raw = (ctx.objects / key).read_bytes()
    require(sha(raw) == key, "corrupt journal object " + key)
    return raw


def clean_temporaries(ctx):
    """The exclusive writer owns this reserved UUID namespace, never arbitrary files."""
    from adopt_snapshot import lookup
    parents = {ctx.data.parent, ctx.page.parent, ctx.state, ctx.objects}
    removed = []
    for parent in parents:
        if lookup(parent)[0] is None:
            continue
        for path in parent.iterdir():
            if not path.name.startswith(".register-tmp-"):
                continue
            suffix = path.name.removeprefix(".register-tmp-")
            try:
                recognised = str(uuid.UUID(suffix)) == suffix
            except ValueError:
                recognised = False
            info = path.lstat()
            require(recognised and stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
                    and info.st_nlink == 1, "unrecognised temporary object preserved: " + str(path))
            path.unlink()
            fsync_directory(parent)
            removed.append(str(path))
    if removed:
        print("Recovered writer temporary objects: " + ", ".join(sorted(removed)), flush=True)
    return removed


@contextmanager
def lock(path, identity):
    require(fcntl is not None, "platform has no supported advisory locking primitive")
    directories(path.parent)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Conflict("lock busy: " + str(path)) from exc
        size = os.fstat(fd).st_size
        old = os.read(fd, size)
        payload = identity.encode()
        require(not old or old == payload, "lock identity collision/configuration mismatch")
        if not old:
            os.write(fd, payload)
            os.fsync(fd)
            fsync_directory(path.parent)
        yield fd
    finally:
        os.close(fd)


def tuple_bytes(ctx):
    return [optional_bytes(p) for p in (ctx.data, ctx.receipt, ctx.page)]


def committed_parent(ctx):
    require(optional_bytes(ctx.pending) is None, "incomplete register transaction")
    receipt_raw = optional_bytes(ctx.receipt)
    require(receipt_raw is not None, "no committed receipt for reconciliation")
    receipt = decode(receipt_raw)
    raw = object_bytes(ctx, receipt["data_sha256"])
    data = validate(decode(raw))
    require(data["register_id"] == receipt["register_id"] and data["revision"] == receipt["revision"] and
            sha(render(data)) == receipt["page_sha256"], "committed parent/receipt mismatch")
    return data, raw


def affected_rows(doc, scope, ctx):
    affected, resource_ids = set(), set()
    for resource in doc["resources"]:
        if resource["locator"]["root"] != "hosted" and any(
                overlaps(ctx.locate(resource["locator"]), p) for p in scope):
            resource_ids.add(resource["id"])
    for row in doc["rows"]:
        if row["lifecycle"]["state"] == "legacy-recorded":
            continue
        bound = {b["resource_id"] for b in expansion(doc, row)["bindings"]}
        if bound & resource_ids:
            affected.add(row["id"])
    return affected, resource_ids


def upgrade_parent(ctx):
    from adopt_compat_v1 import load_current as load_v1
    return load_v1(ctx)


def preserve_assurance_history(old, new):
    prior = index(old, "rows")
    for row in new["rows"]:
        if row["freshness"]["status"] != "applicable":
            continue
        previous = prior.get(row["id"], {})
        old_skills = {s["resource_id"]: s for s in previous.get("freshness", {}).get("skills", [])}
        for skill in row["freshness"]["skills"]:
            models = {c["model_id"]: c for c in old_skills.get(skill["resource_id"], {}).get("comparisons", [])}
            for c in skill["comparisons"]:
                was = models.get(c["model_id"])
                require((was is not None and c["events"] == was["events"] and c["tier"] == was["tier"]) or
                        (was is None and c["events"] == [] and c["tier"] == "unproven"),
                        "tier history requires record-freshness", Finding)
            require(set(models) <= {c["model_id"] for c in skill["comparisons"]},
                    "ordinary edit cannot omit model history", Finding)
        require(set(old_skills) <= {s["resource_id"] for s in row["freshness"]["skills"]},
                "ordinary edit cannot omit skill history", Finding)
    for previous in old["rows"]:
        if previous["freshness"]["status"] == "applicable":
            current = index(new, "rows").get(previous["id"])
            require(current is not None and current["freshness"]["status"] == "applicable",
                    "ordinary edit cannot remove assurance history", Finding)


def record_freshness(ctx, doc, changes, at):
    from adopt_freshness import evaluate
    from adopt_data import shape, ref, timestamp
    required = {"row_id", "resource_id", "model_id", "event"}
    require(required <= set(changes) <= required | {"evidence", "deactivate_row_ids", "proof_route"},
            "record-freshness changes shape")
    shape(changes["event"], ref("freshness-event"))
    require(timestamp(changes["event"]["at"]) <= timestamp(at), "event cannot postdate its recording")
    rows = index(doc, "rows")
    row = rows.get(changes["row_id"])
    require(row is not None and row["freshness"]["status"] == "applicable", "unknown managed skill row")
    blocked(doc, row, ctx)
    for rid in changes.get("deactivate_row_ids", []):
        require(rid in rows, "unknown deactivation row")
        blocked(doc, rows[rid], ctx)
        require(rows[rid]["lifecycle"]["state"] == "active", "deactivation needs active row")
        rows[rid]["lifecycle"] = {"state": "prepared", "changed_at": at,
            "reason": "Reviewed assurance event invalidates activation.", "decision_refs": []}
    require(row["lifecycle"]["state"] != "active", "assurance change requires explicit deactivation", Finding)
    existing = index(doc, "evidence")
    batch = changes.get("evidence", [])
    require(isinstance(batch, list) and len({e["id"] for e in batch}) == len(batch) and
            not {e["id"] for e in batch} & set(existing), "evidence batch must append unique IDs")
    doc["evidence"].extend(copy.deepcopy(batch))
    skills = [s for s in row["freshness"]["skills"] if s["resource_id"] == changes["resource_id"]]
    require(len(skills) == 1, "unknown assessment resource")
    comparisons = [c for c in skills[0]["comparisons"] if c["model_id"] == changes["model_id"]]
    require(len(comparisons) == 1, "unknown assessment model")
    c = comparisons[0]
    require(changes["event"]["id"] not in {e["id"] for e in c["events"]}, "event replay refused", Finding)
    if "proof_route" in changes:
        require(not any(e["action"] in ("comparison", "checked-runs") for e in c["events"]),
                "proof route already used", Finding)
        c["proof_route"] = changes["proof_route"]
    if changes["event"]["action"] == "claim":
        c["claim_evidence_refs"] = sorted(set(c["claim_evidence_refs"]) | set(changes["event"]["evidence_refs"]))
    c["events"].append(copy.deepcopy(changes["event"]))
    c["tier"] = changes["event"]["to_tier"]
    c["evaluated_at"] = changes["event"]["at"]
    # evaluate derives each transition and refuses a caller's unsupported to_tier.
    evaluate(doc, row, ctx, changes["model_id"])
    c["result"] = "pass" if c["tier"] == "proven" else "unknown"


def revalidate_operation(doc, ctx, operation):
    if operation == "record-freshness":
        from adopt_freshness import evaluate
        for row in doc["rows"]:
            if row["freshness"]["status"] == "applicable":
                models = {c["model_id"] for s in row["freshness"]["skills"] for c in s["comparisons"]}
                for model in models:
                    evaluate(doc, row, ctx, model)


def writer_owned(old, changes):
    """The writer owns the page date and layout; a request may only carry their current values."""
    page = changes.get("page") if isinstance(changes, dict) else None
    if not isinstance(page, dict):
        return
    if "layout_version" in page:
        require(page["layout_version"] == old["page"]["layout_version"],
                "writer-owned field page.layout_version: the writer sets the layout; carry the current "
                "value " + str(old["page"]["layout_version"]) + " unchanged")
    meta = page.get("metadata")
    if isinstance(meta, dict) and "updated" in meta:
        require(meta["updated"] == old["page"]["metadata"]["updated"],
                "writer-owned field page.metadata.updated: the writer dates rendered body changes; carry "
                "the current value " + str(old["page"]["metadata"]["updated"]) + " unchanged")


def typed_edit(ctx, old, new, operation, changes):
    """Ordinary edit rules, shared by edit, edit-prose and typed reconciliation; no finalisation."""
    require(set(changes) <= {"jobs", "installations", "resources", "rows", "evidence",
                             "policy", "page"}, "edit contains writer-owned fields")
    writer_owned(old, changes)
    if operation == "edit-prose":
        require(set(changes) == {"page"} and
                set(changes["page"]) == {"prose_blocks"}, "prose edit shape")
        new["page"]["prose_blocks"] = changes["page"]["prose_blocks"]
    else:
        new.update(copy.deepcopy(changes))
    prior = index(old, "rows")
    preserve_assurance_history(old, new)
    require(set(prior) <= {r["id"] for r in new["rows"]},
            "ordinary edits cannot delete or replace row identities; retire preserves history", Finding)
    for row in new["rows"]:
        previous = prior.get(row["id"])
        if row["lifecycle"]["state"] == "active":
            require(previous is not None and row["lifecycle"] == previous["lifecycle"] and
                    digest(expansion(new, row)) == digest(expansion(old, previous)),
                    "ordinary edit cannot create/preserve stale activation", Finding)
        if row["lifecycle"]["state"] == "legacy-recorded":
            require(previous is not None, "only migration creates legacy rows")
            if row != previous:
                require(all(row[k] == previous[k] for k in row
                            if k not in ("name", "notes", "provenance")),
                        "legacy operational edit requires conversion", Finding)
                require(row["provenance"] != previous["provenance"],
                        "legacy correction needs changed-field provenance")
    for hold in old["maintenance"]:
        old_ids = set(hold["row_ids"])
        fresh_ids, _ = affected_rows(new, hold["mutation_scope"], ctx)
        require(fresh_ids == old_ids and all(index(new, "rows").get(r) == prior[r]
                for r in old_ids), "reserved rows/aliases cannot be edited", Finding)
        require(all(prior[r]["lifecycle"]["state"] == "legacy-recorded" or
                    digest(expansion(new, index(new, "rows")[r])) == digest(expansion(old, prior[r]))
                    for r in old_ids), "reserved operational evidence or policy cannot be edited", Finding)
        require(all(index(new, "resources").get(r) == index(old, "resources")[r]
                for r in hold["resource_ids"]), "reserved resources cannot be edited", Finding)
        require(all(index(new, "installations").get(i) == index(old, "installations")[i]
                for i in hold["installation_ids"]), "reserved installations cannot be edited", Finding)
    return new


def canonical_page(document):
    """The page a committed document renders to, under its own schema's renderer."""
    if document["schema_version"] == 1:
        from adopt_compat_v1 import render as render_v1
        return render_v1(document)
    return render(document)


def committed_body(document):
    """The body of a committed parent; the parent was validated when it was loaded."""
    if document["schema_version"] == 1:
        return body_bytes(document)
    if document["page"]["layout_version"] == 1:
        return split_page(render_layout1(document))[1]
    return layout2_body(document)


def observed_body(page):
    """The body bytes of an observed page; None for a missing page or one without a closed
    initial frontmatter, whose repair therefore always counts as a body change."""
    if page is None:
        return None
    header, body = split_page(page)
    return body if header is not None else None


def page_date(old, new, request, observed_page):
    """(updated, body_changed, apply_instants) for a validated candidate.

    The date moves when the candidate body differs from the observed page body or from the
    committed parent's body. It is then the later of the proposal's local day, read from the
    offset captured in its timestamp, and the local day of any apply-time instant this
    operation writes into the body (an instant later than the proposal, new to the body)."""
    candidate = layout2_body(new)
    parent = committed_body(old) if old is not None else None
    observed = observed_body(observed_page)
    changed = parent is None or observed is None or candidate != parent or candidate != observed
    if not changed:
        return new["page"]["metadata"]["updated"], False, []
    day = calendar_day(request["at"])
    proposed = timestamp(request["at"])
    previous = body_instants(old) if old is not None and old["schema_version"] == 2 else set()
    later = sorted(x for x in body_instants(new) - previous if timestamp(x) > proposed)
    for instant in later:
        day = max(day, timestamp(instant).astimezone().date().isoformat())
    return day, True, later


def transformed(ctx, old, request, coordinator=None, observed=None):
    """Pure transformation of the parent document. `observed` is the observed data/receipt/page
    tuple; ordinary pure calls default to the parent's canonical page, and reconciliation must
    supply the actual observation."""
    operation, changes = request["operation"], request["changes"]
    if operation == "seed":
        require(changes == {}, "seed accepts no custom document or Markdown")
        new = seed_document(request["at"])
        new["register_id"] = request["commit_id"]
    elif operation == "migrate":
        from adopt_migrate import migration_document, verify_coverage
        require(set(changes) == {"source_sha256", "mapping"}, "migration requires reviewed mapping")
        source = ctx.page.read_bytes()
        require(sha(source) == changes["source_sha256"], "migration source changed", Conflict)
        new = migration_document(source, changes["mapping"], request["at"])
        new["register_id"] = request["commit_id"]
        verify_coverage(source, new, changes["mapping"])
        from adopt_migrate import upgrade_freshness
        new = upgrade_freshness(new, at=request["at"])
        if observed is None:
            observed = [None, None, source]
    else:
        new = copy.deepcopy(old)
        if operation == "upgrade-freshness":
            from adopt_migrate import upgrade_freshness
            require(changes == {} and not old["maintenance"], "upgrade requires no changes or reservations")
            require(old["schema_version"] == 1, "already upgraded")
            new = upgrade_freshness(old, at=request["at"])
        elif operation == "record-freshness":
            record_freshness(ctx, new, changes, request["at"])
        elif operation in ("edit", "edit-prose"):
            new = typed_edit(ctx, old, new, operation, changes)
        elif operation in ("activate", "deactivate", "retire"):
            require({"row_ids", "reason"} <= set(changes) <= {"row_ids", "reason", "freshness_decisions"} and changes["row_ids"] and
                    len(set(changes["row_ids"])) == len(changes["row_ids"]), "state proposal shape")
            selected = changes.get("freshness_decisions", {})
            require(isinstance(selected, dict) and set(selected) <= set(changes["row_ids"]) and
                    (not selected or operation == "activate"), "activation decision scope")
            for rid in changes["row_ids"]:
                require(rid in index(new, "rows"), "unknown row " + rid)
                row = index(new, "rows")[rid]
                blocked(new, row, ctx)
                require(row["lifecycle"]["state"] != "legacy-recorded", "legacy row requires managed conversion", Finding)
                if operation == "activate":
                    require(row["lifecycle"]["state"] == "prepared", "activation requires prepared row", Finding)
                    activation = activate_record(new, row, ctx, decisions=selected.get(rid))
                    row["lifecycle"] = {"state": "active", "changed_at": request["at"],
                        "reason": changes["reason"], "decision_refs": [], "activation": activation}
                else:
                    row["lifecycle"] = {"state": "retired" if operation == "retire" else "prepared",
                        "changed_at": request["at"], "reason": changes["reason"], "decision_refs": []}
        elif operation in ("reconcile-page", "reconcile-data"):
            require(observed is not None, "reconciliation requires the observed data/receipt/page tuple")
            if changes != {"discard": True}:
                require(set(changes) == {"typed_changes"}, "reconciliation requires discard or reviewed typed changes")
                new = typed_edit(ctx, old, copy.deepcopy(old), "edit", changes["typed_changes"])
        elif operation in ("begin-maintenance", "maintenance-phase", "finish-maintenance", "maintenance-recover"):
            require(coordinator is not None and coordinator.held and coordinator.ctx is ctx,
                    "maintenance command requires held supervisor guard")
            coordinator.transform(new, request)
        else:
            raise Problem("unsupported operation " + operation)
        new["revision"] = old["revision"] + 1
        if observed is None:
            observed = [None, None, canonical_page(old)]
    commit_meta = {"id": request["commit_id"], "at": request["at"], "operation": operation,
                   "proposal_sha256": request["proposal_sha256"]}
    if old is not None:
        commit_meta["parent_data_sha256"] = request["expect_data"]
    new["commit"] = commit_meta
    # Finalise once: current layout, then the page date from the exact body comparison.
    new["page"]["layout_version"] = CURRENT_LAYOUT
    validate(new)
    new["page"]["metadata"]["updated"] = page_date(old, new, request, observed[2] if observed else None)[0]
    footprint_check(new, ctx)
    from adopt_freshness import revalidate_active
    revalidate_active(new, ctx)
    return new


def baseline(ctx, request):
    operation = request["operation"]
    require(optional_bytes(ctx.pending) is None, "incomplete register transaction; explicit recover required")
    observed = tuple_bytes(ctx)
    if operation in ("seed", "migrate"):
        require(observed[0] is None and observed[1] is None, "register already exists", Conflict)
        if operation == "seed":
            require(observed[2] is None, "seed page already exists", Conflict)
        require(request["expect_data"] == "absent" and request["expect_revision"] == -1,
                "initial expectations mismatch", Conflict)
        return None, observed
    if operation in ("reconcile-page", "reconcile-data"):
        old, raw = committed_parent(ctx)
        hashes = [sha(x) if x is not None else None for x in observed]
        require(request.get("observed") == hashes, "observed drift changed", Conflict)
    elif operation == "upgrade-freshness":
        old, raw = upgrade_parent(ctx)
    else:
        old, raw = load_current(ctx)
    require(sha(raw) == request["expect_data"] and old["revision"] == request["expect_revision"],
            "stale proposal", Conflict)
    return old, observed


def preview(ctx, request):
    verify_proposal(request)
    old, observed = baseline(ctx, request)
    new = transformed(ctx, old, request, observed=observed)
    updated, changed, later = page_date(old, new, request, observed[2])
    def delta(a, b, name):
        return "".join(difflib.unified_diff(a.decode("utf-8", errors="replace").splitlines(True),
            b.decode().splitlines(True), fromfile="observed-" + name, tofile="proposed-" + name))
    prior = index(old, "rows") if old else {}
    from adopt_data import operational_definition
    invalidated_resources = []
    if old and old["schema_version"] == 2:
        for row in new["rows"]:
            previous = prior.get(row["id"])
            if (previous and previous["lifecycle"]["state"] != "legacy-recorded" and
                    row["lifecycle"]["state"] != "legacy-recorded" and
                    digest(operational_definition(old, previous)) != digest(operational_definition(new, row))):
                refs = [eid for eid in previous["acceptance"]["evidence_refs"]
                        if index(old, "evidence")[eid]["subject"]["type"] == "resource-check"]
                if refs:
                    invalidated_resources.append({"row_id": row["id"], "evidence_refs": sorted(refs)})
    shared = []
    if request["operation"] == "record-freshness":
        resource_id = request["changes"]["resource_id"]
        installation_id = index(new, "resources")[resource_id]["owner"]["id"]
        shared = sorted(r["id"] for r in new["rows"] if r["lifecycle"]["state"] != "legacy-recorded" and
                        any(i["id"] == installation_id for i in expansion(new, r)["installations"]))
    return {"proposal": request, "lock": str(ctx.lock),
            "affected_rows": sorted(r["id"] for r in new["rows"] if r != prior.get(r["id"])),
            "shared_resource_rows": shared,
            "invalidated_resource_evidence": invalidated_resources,
            "invalidated_proofs": sorted(r["id"] for r in new["rows"] if
                prior.get(r["id"], {}).get("lifecycle", {}).get("state") == "active" and
                r["lifecycle"] != prior[r["id"]]["lifecycle"]),
            "legacy_findings": [r["id"] for r in new["rows"] if r["lifecycle"]["state"] == "legacy-recorded"],
            "data_diff": delta(encoded(old) if old else b"", encoded(new), "data"),
            "page_diff": delta(observed[2] or b"", render(new), "page"),
            "page_date": {"updated": updated, "body_changed": changed, "proposal_day": calendar_day(request["at"]),
                          "apply_time_instants": later,
                          "rule": "The writer owns updated: when the rendered body differs from the observed page "
                                  "body or the committed parent's body, it becomes the later of the proposal's local "
                                  "day and the local day of any apply-time instant the operation writes into the body; "
                                  "otherwise it is kept. Apply-time values are recaptured at apply, so such an "
                                  "operation can publish a later date and different bytes than this preview."},
            "control_hits": control()}


def commit(ctx, request, hook=None, coordinator=None):
    verify_proposal(request)
    with lock(ctx.lock, ctx.lock_identity):
        clean_temporaries(ctx)
        old, observed = baseline(ctx, request)
        new = transformed(ctx, old, request, coordinator, observed)
        if hook:
            hook("after-proof")
        new_raw, page = encoded(new), render(new)
        validate(decode(new_raw))
        transaction = str(uuid.uuid4())
        receipt = encoded({"register_id": new["register_id"], "revision": new["revision"],
                           "data_sha256": sha(new_raw), "page_sha256": sha(page), "transaction_id": transaction})
        new_tuple = [new_raw, receipt, page]
        if request["operation"] == "migrate":
            archive(ctx, observed[2])
        pending = {"id": transaction, "operation": request["operation"],
                   "destinations": [str(ctx.data), str(ctx.receipt), str(ctx.page)],
                   "old": [archive(ctx, x) for x in observed], "new": [archive(ctx, x) for x in new_tuple]}
        if hook:
            hook("before-pending")
        publish(ctx.pending, encoded(pending), create=True, hook=hook, label="pending")
        def last_check(stage):
            if hook:
                hook(stage)
            if stage == "before-data":
                require(tuple_bytes(ctx) == observed, "files changed before publication", Conflict)
                footprint_check(new, ctx)
                for row in new["rows"]:
                    if row["lifecycle"]["state"] == "active":
                        checked = prove(new, row, ctx)
                        require(stable_checks(checked) == stable_checks(row["lifecycle"]["activation"]["checks"]),
                                "resource changed before publication", Finding)
                from adopt_freshness import revalidate_active
                revalidate_active(new, ctx)
                revalidate_operation(new, ctx, request["operation"])
        try:
            publish(ctx.data, new_raw, create=observed[0] is None, hook=last_check, label="data")
            publish(ctx.receipt, receipt, create=observed[1] is None, hook=hook, label="receipt")
            publish(ctx.page, page, create=observed[2] is None, hook=hook, label="page")
            require(tuple_bytes(ctx) == new_tuple, "publication read-back differs")
            if hook:
                hook("before-clear")
            archive(ctx, encoded(pending))
            ctx.pending.unlink()
            fsync_directory(ctx.pending.parent)
            if hook:
                hook("after-clear")
        except (Finding, Conflict):
            if tuple_bytes(ctx) == observed:
                ctx.pending.unlink()
                fsync_directory(ctx.pending.parent)
            raise
        return new


def recover(ctx, hook=None):
    with lock(ctx.lock, ctx.lock_identity):
        clean_temporaries(ctx)
        raw = optional_bytes(ctx.pending)
        require(raw is not None, "no pending transaction")
        pending = decode(raw)
        require(set(pending) == {"id", "operation", "destinations", "old", "new"} and
                pending["destinations"] == [str(ctx.data), str(ctx.receipt), str(ctx.page)] and
                len(pending["old"]) == len(pending["new"]) == 3, "invalid transaction journal")
        old, new = ([object_bytes(ctx, x) for x in pending[k]] for k in ("old", "new"))
        if pending["operation"] == "upgrade-freshness":
            from adopt_compat_v1 import validate as validate_old, render as render_old
            historical = validate_old(decode(old[0]))
            require(render_old(historical) == old[2] and decode(old[1])["data_sha256"] == sha(old[0]) and
                    decode(old[1])["page_sha256"] == sha(old[2]), "journal v1 tuple inconsistent")
        validate(decode(new[0]))
        require(render(decode(new[0])) == new[2] and decode(new[1])["data_sha256"] == sha(new[0])
                and decode(new[1])["page_sha256"] == sha(new[2]), "journal new tuple inconsistent")
        current = tuple_bytes(ctx)
        require(current in [old, [new[0], old[1], old[2]], [new[0], new[1], old[2]], new],
                "unexpected bytes/tuple during recovery")
        chosen = old if current[0] == old[0] else new
        def current_activation():
            if chosen[0] is not None:
                from adopt_resources import recheck
                selected = decode(chosen[0])
                if selected["schema_version"] == 1:
                    from adopt_compat_v1 import validate as validate_old
                    validate_old(selected)
                    require(pending["operation"] == "upgrade-freshness", "v1 recovery needs upgrade transaction")
                    return
                validate(selected)
                footprint_check(selected, ctx)
                for row in selected["rows"]:
                    if row["lifecycle"]["state"] == "active":
                        recheck(selected, row, ctx)
                revalidate_operation(selected, ctx, pending["operation"])
        current_activation()
        expected = list(current)
        def recovery_gate(stage):
            if hook:
                hook(stage)
            if stage.startswith("before-recover-"):
                require(tuple_bytes(ctx) == expected, "unexpected bytes during recovery publication")
                current_activation()
        for i, path in enumerate((ctx.data, ctx.receipt, ctx.page)):
            if current[i] != chosen[i]:
                require(chosen[i] is not None, "unexpected recovery deletion")
                publish(path, chosen[i], create=current[i] is None, hook=recovery_gate, label="recover-" + str(i))
                expected[i] = chosen[i]
        require(tuple_bytes(ctx) == chosen, "recovery read-back differs")
        current_activation()
        archive(ctx, raw)
        ctx.pending.unlink()
        fsync_directory(ctx.pending.parent)
        return "old" if chosen is old else "new"


def main():
    from adopt_data import ProbeParser
    parser = ProbeParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--home", required=True)
    parser.add_argument("--lock-root")
    sub = parser.add_subparsers(dest="command", required=True)
    prop = sub.add_parser("propose")
    prop.add_argument("--operation", required=True)
    prop.add_argument("--changes")
    prop.add_argument("--observed")
    show = sub.add_parser("preview")
    show.add_argument("--proposal", required=True)
    apply = sub.add_parser("apply")
    for key in ("proposal", "expect-data", "expect-proposal"):
        apply.add_argument("--" + key, required=True)
    apply.add_argument("--write", action="store_true")
    repair = sub.add_parser("recover")
    repair.add_argument("--write", action="store_true")
    for command in ("maintenance-run", "maintenance-recover"):
        maintenance = sub.add_parser(command)
        maintenance.add_argument("--plan", required=True)
        maintenance.add_argument("--expect-plan", required=True)
        maintenance.add_argument("--write", action="store_true")
    sub.add_parser("check")
    args = parser.parse_args()
    try:
        ctx = Context(args.vault, args.home, args.lock_root)
        if args.command == "propose":
            result = proposal(ctx, args.operation, read_json(args.changes) if args.changes else {},
                              read_json(args.observed) if args.observed else None)
        elif args.command == "preview":
            result = preview(ctx, read_json(args.proposal))
        elif args.command == "apply":
            request = read_json(args.proposal)
            require(request["expect_data"] == args.expect_data and request["proposal_sha256"] ==
                    args.expect_proposal, "review expectations differ", Conflict)
            result = {"revision": commit(ctx, request)["revision"], "control_hits": control()} if args.write else preview(ctx, request)
        elif args.command == "recover":
            require(args.write, "recovery requires explicit --write")
            result = {"recovered": recover(ctx), "control_hits": control()}
        elif args.command.startswith("maintenance-"):
            from adopt_maintenance import run
            require(args.write, "maintenance requires explicit --write")
            result = run(ctx, read_json(args.plan), args.expect_plan, recovering=args.command == "maintenance-recover")
        else:
            from adopt_resources import recheck
            doc, _ = load_current(ctx)
            legacy = [r["id"] for r in doc["rows"] if r["lifecycle"]["state"] == "legacy-recorded"]
            for row in doc["rows"]:
                if row["lifecycle"]["state"] == "active":
                    recheck(doc, row, ctx)
            result = {"revision": doc["revision"], "rows": len(doc["rows"]),
                      "legacy_findings": legacy, "findings": len(legacy), "control_hits": control()}
        print(encoded(result).decode(), end="")
        return 1 if result.get("findings", 0) else 0
    except (Problem, OSError, ValueError, TypeError, KeyError, IndexError, RuntimeError) as exc:
        return cli_error(exc)


if __name__ == "__main__":
    sys.exit(main())
