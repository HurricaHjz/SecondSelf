"""Writer-owned maintenance supervisor. No external programme or child launch.

The built-in adapter replaces existing regular files from reviewed, hashed
artefacts. External/daemonising adapters are deliberately unsupported until a
process-lifetime contract is supplied. The shared domain guard is held throughout.
"""
import copy
import os
from pathlib import Path
import stat
import uuid
from adopt_data import (Problem, Finding, Conflict, require, sha, digest, encoded,
                        load_current, index, now, validate, expansion, operational_definition,
                        shape, obj, ID, HASH, string, evidence_ids, evidence_closure)
from adopt_snapshot import snapshot, compare, validate_snapshot, typed_equal
from adopt_resources import observation, prove, overlaps
from adopt_register import (lock, commit, proposal, affected_rows, archive, publish,
                            fsync_directory, footprint_check)


def validate_plan(ctx, plan):
    required = {"id", "expect_data", "scope", "before", "declaration", "steps", "changes", "allowed_roots"}
    require(type(plan) is dict and required <= set(plan) <= required | {"candidate_sources", "freshness_decisions"},
            "maintenance plan shape")
    require(isinstance(plan["id"], str) and plan["id"].startswith("maintenance-"), "maintenance ID")
    require(plan["scope"] and len(plan["scope"]) == len(set(plan["scope"])), "maintenance scope")
    for p in plan["scope"]:
        require(Path(p).is_absolute() and str(Path(p).resolve()) == p, "scope must be canonical absolute")
        require(not any(overlaps(p, x) for x in [ctx.state, ctx.data, ctx.page, ctx.locks]),
                "installation scope intersects writer footprint")
    validate_snapshot(plan["before"])
    require(plan["before"]["scope"]["home"] == str(ctx.home), "maintenance snapshot home differs")
    for step in plan["steps"]:
        require(type(step) is dict and set(step) == {"kind", "path", "old_sha256",
                "artefact", "new_sha256", "mode", "old_mode"} and step["kind"] == "replace-file",
                "unsupported adapter step; no external processes accepted")
        require(step["path"] in plan["scope"], "step outside exact reviewed mutation scope")
        require(type(step["mode"]) is int and 0 <= step["mode"] <= 0o777,
                "unsupported file mode")
        require(type(step["old_mode"]) is int and 0 <= step["old_mode"] <= 0o777,
                "unsupported original file mode")
        require(Path(step["artefact"]).is_absolute(), "artefact needs absolute path")
        require(not any(overlaps(step["artefact"], p) for p in plan["scope"]),
                "mutable plan input")
    require(set(plan["changes"]) <= {"rows", "resources", "installations", "evidence"},
            "maintenance cannot alter policy, prose or jobs")
    decisions = plan.get("freshness_decisions", {})
    require(isinstance(decisions, dict), "maintenance freshness decisions need a row mapping")
    affected, _ = affected_rows(doc=load_current(ctx)[0], scope=plan["scope"], ctx=ctx)
    require(set(decisions) <= affected, "maintenance decision names unrelated row")
    sources = plan.get("candidate_sources", [])
    require(type(sources) is list and len({s.get("resource_id") for s in sources if isinstance(s, dict)}) ==
            len(sources), "duplicate or malformed candidate sources")
    for source in sources:
        shape(source, obj({"resource_id": ID, "path": string(fmt="absolute"), "tree_sha256": HASH}))
        path = Path(source["path"])
        require(path.resolve(strict=True) == path, "candidate source must be canonical")
        require(not any(overlaps(path, scope) for scope in plan["scope"] +
                        [ctx.state, ctx.data.parent, ctx.page.parent, ctx.locks]),
                "candidate source overlaps mutation or writer footprint")


def assess_candidate(ctx, doc, plan):
    """Read independently staged bytes, retaining destination-bound definitions."""
    from adopt_freshness import evaluate_targets
    target = copy.deepcopy(doc)
    target.update(copy.deepcopy(plan["changes"]))
    affected, _ = affected_rows(doc, plan["scope"], ctx)
    for row in target["rows"]:
        if row["id"] in affected and row["lifecycle"]["state"] == "active":
            row["lifecycle"] = {"state": "prepared", "changed_at": now(),
                                "reason": "candidate assessment", "decision_refs": []}
    validate(target)
    resources = index(target, "resources")
    skill_ids = {b["resource_id"] for row in target["rows"] if row["id"] in affected and
                 row["lifecycle"]["state"] != "legacy-recorded"
                 for b in operational_definition(target, row)["bindings"]
                 if b["resource_definition"]["type"] == "skill-tree"}
    sources = {}
    for source in plan.get("candidate_sources", []):
        rid = source["resource_id"]
        require(rid in skill_ids and source["tree_sha256"] == resources[rid]["expected"]["sha256"],
                "candidate source does not match an affected skill definition")
        require(not overlaps(source["path"], ctx.locate(resources[rid]["locator"])),
                "candidate source must be distinct from installation destination")
        sources[rid] = source["path"]
    for row in target["rows"]:
        if row["id"] in affected and row["lifecycle"]["state"] != "legacy-recorded" and \
                row["freshness"]["status"] == "applicable":
            evaluations = evaluate_targets(target, row, ctx, sources,
                decisions=plan.get("freshness_decisions", {}).get(row["id"]))
            require(all(e["tier"] in ("claimed", "proven") or e["freshness_decision_refs"]
                        for e in evaluations), "candidate assurance needs scoped consent", Finding)
    return target


class Coordinator:
    def __init__(self, ctx, plan):
        self.ctx, self.plan = ctx, plan
        self.held = False
        self.generation = 0
        self.identity = str(uuid.uuid4())
        self.result = None
        self.plan_hash = digest(plan)

    def current(self):
        require(self.held, "operation guard not held")
        require(digest(self.plan) == self.plan_hash, "reviewed maintenance plan changed during operation", Conflict)
        doc, _ = load_current(self.ctx)
        hold = index(doc, "maintenance").get(self.plan["id"])
        require(hold and hold["generation"] == self.generation and
                hold["coordinator_id"] == self.identity and
                hold["target_plan_sha256"] == self.plan_hash, "stale maintenance generation", Conflict)
        return doc, hold

    def transform(self, doc, request):
        require(self.held and digest(self.plan) == self.plan_hash,
                "reviewed maintenance plan changed during operation", Conflict)
        op = request["operation"]
        if op == "begin-maintenance":
            require(not doc["maintenance"], "unresolved maintenance holds comparison domain", Conflict)
            ids, resource_ids = affected_rows(doc, self.plan["scope"], self.ctx)
            # Unresolved legacy fields cannot establish non-overlap.
            ids.update(r["id"] for r in doc["rows"] if r["lifecycle"]["state"] == "legacy-recorded")
            subjects = []
            for rid in resource_ids:
                resource = index(doc, "resources")[rid]
                subjects.append({"resource_id": rid, "definition_sha256": digest(resource),
                                 "observation": observation(doc, None, resource, self.ctx)})
            hold = {"id": self.plan["id"], "generation": self.generation,
                    "coordinator_id": self.identity, "guard_identity": str(self.ctx.guard),
                    "status": "reserved", "row_ids": sorted(ids), "resource_ids": sorted(resource_ids),
                    "installation_ids": sorted({i for r in doc["rows"] if r["id"] in ids and
                        r["lifecycle"]["state"] != "legacy-recorded" for i in r["installation_ids"]}),
                    "mutation_scope": self.plan["scope"], "base_revision": doc["revision"],
                    "base_subjects": subjects, "target_plan_sha256": self.plan_hash,
                    "recovery_plan": {"plan_object": sha(encoded(self.plan)),
                                      "mode": "verify-original-or-target"}, "started_at": now()}
            doc["maintenance"].append(hold)
            for row in doc["rows"]:
                if row["id"] in ids:
                    row["maintenance_id"] = hold["id"]
                    if row["lifecycle"]["state"] == "active":
                        row["lifecycle"] = {"state": "prepared", "changed_at": now(),
                            "reason": "maintenance reservation", "decision_refs": []}
        else:
            hold = index(doc, "maintenance").get(self.plan["id"])
            require(hold is not None, "reservation missing")
            if op == "maintenance-recover":
                require(hold["target_plan_sha256"] == self.plan_hash and
                        hold["generation"] + 1 == self.generation, "recovery plan/generation mismatch")
                hold.update(generation=self.generation, coordinator_id=self.identity, status="recovery-required")
            else:
                require(hold["generation"] == self.generation and hold["coordinator_id"] == self.identity,
                        "stale coordinator", Conflict)
                if op == "maintenance-phase":
                    require(set(request["changes"]) == {"status"} and request["changes"]["status"] in
                            ("installing", "verifying", "rolling-back", "recovery-required"), "invalid phase")
                    hold["status"] = request["changes"]["status"]
                elif op == "finish-maintenance":
                    require(self.result in ("original", "target"), "unverified maintenance outcome")
                    before = copy.deepcopy(doc)
                    if self.result == "target":
                        doc.update(copy.deepcopy(self.plan["changes"]))
                    # Only held rows/resources/installations and their evidence may change.
                    for collection, authorised in (("rows", hold["row_ids"]),
                            ("resources", hold["resource_ids"]), ("installations", hold["installation_ids"])):
                        prior, after = index(before, collection), index(doc, collection)
                        require(set(prior) == set(after) and all(after[k] == prior[k] for k in prior
                                if k not in authorised), "maintenance changes unrelated definitions")
                    allowed_evidence = set()
                    for version in (before, doc):
                        for row in version["rows"]:
                            if row["id"] in hold["row_ids"] and row["lifecycle"]["state"] != "legacy-recorded":
                                references = evidence_ids(operational_definition(version, row))
                                references |= evidence_ids(self.plan.get("freshness_decisions", {}).get(row["id"], []))
                                allowed_evidence.update(e["id"] for e in evidence_closure(version, references))
                    old_evidence, new_evidence = index(before, "evidence"), index(doc, "evidence")
                    require(all(old_evidence.get(eid) == new_evidence.get(eid)
                                for eid in (old_evidence.keys() | new_evidence.keys()) - allowed_evidence),
                            "maintenance changes unrelated evidence")
                    doc["maintenance"] = [m for m in doc["maintenance"] if m["id"] != hold["id"]]
                    for row in doc["rows"]:
                        if row["id"] in hold["row_ids"]:
                            row.pop("maintenance_id", None)
                            if row["lifecycle"]["state"] != "legacy-recorded":
                                require(row["lifecycle"]["state"] == "prepared", "release must leave prepared")
                                prove(doc, row, self.ctx)
                                from adopt_freshness import evaluate_targets
                                evaluations = evaluate_targets(doc, row, self.ctx,
                                    decisions=self.plan.get("freshness_decisions", {}).get(row["id"]))
                                require(all(e["tier"] in ("claimed", "proven") or e["freshness_decision_refs"]
                                            for e in evaluations), "installed assurance needs scoped consent", Finding)
                    footprint_check(doc, self.ctx)

    def phase(self, status):
        self.current()
        commit(self.ctx, proposal(self.ctx, "maintenance-phase", {"status": status}), coordinator=self)

    def step(self, step):
        self.current()
        path = Path(step["path"])
        require(path.resolve(strict=True) == path and stat.S_ISREG(path.lstat().st_mode),
                "adapter requires existing regular physical file")
        require(sha(path.read_bytes()) == step["old_sha256"], "installation base changed", Conflict)
        require(stat.S_IMODE(path.stat().st_mode) == step["old_mode"], "installation base mode changed", Conflict)
        raw = Path(step["artefact"]).read_bytes()
        require(sha(raw) == step["new_sha256"], "installation artefact changed", Conflict)
        # One process owns this write and the guard; no child can survive it.
        publish(path, raw)
        os.chmod(path, step["mode"])
        fd = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        fsync_directory(path.parent)


def run(ctx, plan, expected, recovering=False, hook=None):
    validate_plan(ctx, plan)
    require(digest(plan) == expected, "reviewed maintenance plan changed", Conflict)
    coordinator = Coordinator(ctx, plan)
    with lock(ctx.guard, ctx.domain):
        coordinator.held = True
        try:
            doc, raw = load_current(ctx)
            if recovering:
                hold = index(doc, "maintenance").get(plan["id"])
                require(hold is not None, "reservation not found")
                coordinator.generation = hold["generation"] + 1
                commit(ctx, proposal(ctx, "maintenance-recover"), coordinator=coordinator)
            else:
                require(sha(raw) == plan["expect_data"], "stale maintenance proposal", Conflict)
                assess_candidate(ctx, doc, plan)
                archive(ctx, encoded(plan))
                commit(ctx, proposal(ctx, "begin-maintenance"), coordinator=coordinator)
            if hook:
                hook("reserved", coordinator)
            before = snapshot(ctx.home, plan["allowed_roots"])
            if not recovering:
                require(typed_equal(before["state"], plan["before"]["state"]), "configuration base changed", Conflict)
                coordinator.phase("installing")
                for step in plan["steps"]:
                    if hook:
                        hook("before-step", coordinator)
                    coordinator.current()
                    assess_candidate(ctx, doc, plan)
                    coordinator.step(step)
                    if hook:
                        hook("after-step", coordinator)
            coordinator.phase("verifying")
            if hook:
                hook("verifying", coordinator)
            after = snapshot(ctx.home, plan["allowed_roots"])
            states = [(sha(Path(s["path"]).read_bytes()), stat.S_IMODE(Path(s["path"]).stat().st_mode))
                      for s in plan["steps"]]
            original = all(state == (step["old_sha256"], step["old_mode"])
                           for state, step in zip(states, plan["steps"]))
            target = all(state == (step["new_sha256"], step["mode"])
                         for state, step in zip(states, plan["steps"]))
            if original and typed_equal(after["state"], plan["before"]["state"]):
                coordinator.result = "original"
                result = compare(plan["before"], after, [])
            else:
                require(target, "unresolved partial installation; reservation retained", Finding)
                result = compare(plan["before"], after, plan["declaration"])
                require(result["findings"] == 0, "undeclared configuration changes: " +
                        str(result["unexpected"] + result["unobserved"]), Finding)
                coordinator.result = "target"
            commit(ctx, proposal(ctx, "finish-maintenance"), coordinator=coordinator)
            coordinator.held = False
            return {"outcome": coordinator.result, "comparison": result, "state": "prepared"}
        except (Problem, OSError):
            try:
                coordinator.current()
                coordinator.phase("recovery-required")
            except (Problem, OSError):
                pass  # The durable existing reservation is never expired or discarded.
            raise
        finally:
            coordinator.held = False
