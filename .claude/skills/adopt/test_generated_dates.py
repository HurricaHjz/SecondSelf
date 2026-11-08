#!/usr/bin/env python3
"""Generated register dates, body digest and navigation: the native acceptance family.

Fixture-only. Run with -B and an explicit scratch TMPDIR:
  python3 -B test_generated_dates.py --adopt-dir DIR [--stamp-hook FILE] [--audit-pools FILE]
      [--required-sections FILE] [--link-check FILE] [--lint-adapter FILE] [--instance-data FILE]
      [--demo-instance FILE] [--deep-lint-skill FILE] [--lint-skill FILE] [--group all|pure|hook]
      [--case NAME]

Reader inputs default to the shipped sibling skills beside DIR. --instance-data is the frozen
historical v2/layout-1 tuple kept as a compatibility fixture; --demo-instance is the demonstration
instance regenerated from it through the writer. The Stop hook is vault-local and never ships:
hook-dependent cases run only with --stamp-hook and otherwise print `NOT APPLICABLE: hook absent`;
the vault's hook suite runs them with `--group hook`. A missing reader input is `UNRUN REQUIRED`
and fails the family. A broken premise prints `PROBE FAILED` and exits 2. Expected values derive
from fixture instants and independent byte hashing, never from the renderer under test or
today's clock. Each case line names its evidence kind: an original-base discriminator fails on
the build before this feature, a preservation control passes there too, and a case whose own
delta refines a rule the original base lacks names the mutant that discriminates it. Ends
`PASS n/n` or `FAIL k/n`.
"""
import argparse
import contextlib
import copy
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import traceback
from unittest.mock import patch
from zoneinfo import ZoneInfo

REG = "wiki/developments/capability-register.md"
FM = re.compile(rb"\A---\r?\n(.*?\r?\n)---\r?\n", re.S)
OPEN, CLOSE = chr(91) * 2, chr(93) * 2
WIKILINK = re.compile(re.escape(OPEN) + r"([^\]|\n]+)(?:\|[^\]\n]*)?" + re.escape(CLOSE))
STAGES = ["before-pending", "after-pending", "before-data", "after-data", "before-receipt",
          "after-receipt", "before-page", "after-page", "before-clear", "after-clear"]
COUNT = 0
ARGS = None
D = W = R = G = T = render = None


class Unrun(Exception):
    pass


def check(ok, label):
    global COUNT
    COUNT += 1
    if not ok:
        raise AssertionError(label)
    print("    PASS " + label, flush=True)


def refuses(call, label, codes=(1, 2, 3), ctx=None, text=None):
    before = W.tuple_bytes(ctx) if ctx else None
    try:
        call()
    except D.Problem as exc:
        check(exc.code in codes and (text is None or text in str(exc)),
              label + " (exit " + str(exc.code) + ": " + str(exc)[:90] + ")")
        if ctx:
            check(W.tuple_bytes(ctx) == before, label + ": data, receipt and page unchanged")
        return exc
    raise AssertionError("accepted prohibited case: " + label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def split(page):
    m = FM.match(page)
    return (m.group(1), page[m.end():]) if m else (None, page)


def header(page):
    head, _ = split(page)
    out = {}
    for line in (head or b"").split(b"\n"):
        if b": " in line:
            key, value = line.split(b": ", 1)
            out.setdefault(key.decode(), []).append(value.decode())
    return out


def field(page, key):
    values = header(page).get(key, [])
    return json.loads(values[0]) if len(values) == 1 else None


def body(page):
    return split(page)[1]


def day(instant, zone):
    return dt.datetime.fromisoformat(instant.replace("Z", "+00:00")).astimezone(ZoneInfo(zone)).date().isoformat()


def section(page, title):
    """The lines under one level-2 heading of a body, or None if it is not there exactly once."""
    lines = body(page).decode().split("\n")
    heads = [i for i, line in enumerate(lines) if line == "## " + title]
    if len(heads) != 1:
        return None
    out = []
    for line in lines[heads[0] + 1:]:
        if line.startswith("## "):
            break
        out.append(line)
    return out


def targets(lines):
    return {m.group(1) for line in (lines or []) for m in WIKILINK.finditer(line)}


@contextlib.contextmanager
def clock(instant, zone, apply_instant=None):
    """Freeze the proposal clock and the activation clock in process, in one local zone."""
    saved = os.environ.get("TZ")
    os.environ["TZ"] = zone
    time.tzset()
    try:
        with patch.object(W, "now", lambda: instant), patch.object(R, "now", lambda: apply_instant or instant):
            yield
    finally:
        if saved is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = saved
        time.tzset()


LONDON, TOKYO, LA = "Europe/London", "Asia/Tokyo", "America/Los_Angeles"


def seeded(name, instant="2026-03-10T10:00:00Z", zone=LONDON):
    with clock(instant, zone):
        return T.fixture(name)


def current(ctx):
    return D.load_current(ctx)[0]


def page_bytes(ctx):
    return ctx.page.read_bytes()


def edit_prose(ctx, text, instant, zone=LONDON, block="note-a", hook=None):
    with clock(instant, zone):
        doc = current(ctx)
        blocks = [b for b in copy.deepcopy(doc["page"]["prose_blocks"]) if b["id"] != block]
        blocks.append({"id": block, "section": "Notes", "kind": "paragraph",
                       "content": [{"type": "text", "text": text}], "provenance": []})
        return W.commit(ctx, W.proposal(ctx, "edit-prose", {"page": {"prose_blocks": blocks}}), hook=hook)


def edit_page(ctx, instant, zone=LONDON, **meta):
    with clock(instant, zone):
        doc = current(ctx)
        page = copy.deepcopy(doc["page"])
        page["metadata"].update(meta)
        return W.commit(ctx, W.proposal(ctx, "edit", {"page": page}))


def observed(ctx):
    return [sha(x) if x is not None else None for x in W.tuple_bytes(ctx)]


def run_hook(vault, state, today, dry=False):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AIMYTH_UPDATED_STAMP")}
    env.update(AIMYTH_UPDATED_STAMP_ROOT=str(vault), AIMYTH_UPDATED_STAMP_DIR=str(state),
               AIMYTH_UPDATED_STAMP_TODAY=today)
    if dry:
        env["AIMYTH_UPDATED_STAMP_DRY_RUN"] = "1"
    result = subprocess.run([sys.executable, "-B", str(ARGS.stamp_hook)], env=env, capture_output=True, text=True)
    log = state / "actions.log"
    return result, (log.read_text().splitlines()[-1] if log.exists() and log.read_text() else "")


def arm_hook(vault, state):
    if (state / "body-hashes.tsv").exists():
        (state / "body-hashes.tsv").unlink()
    run_hook(vault, state, "2026-01-01")


SOURCE = """---
title: "Capability register"
type: development
confidence: medium
audited: 2026-03-01
created: 2026-01-05
updated: 2026-03-09
tags: [capabilities]
aliases: []
---

# Capability register

## User-level skills

| Name | Level | Record |
|---|---|---|
| `alpha-skill` | auto | {o}alpha-record{c} |
| `beta-tool` · `gamma-tool` | propose-first | {o}shared-record{c} and {o}shared-record{c} again |

## Sources Used

- {o}source-page{c} and the reviewed design {o}register-design{c}

## Related

- {o}related-design{c} · {o}alpha-record{c}
""".format(o=OPEN, c=CLOSE).encode()


def source_mapping(raw):
    lines = raw.decode().split("\n")
    first = next(i for i, l in enumerate(lines, 1) if l.startswith("| `alpha-skill`"))
    second = next(i for i, l in enumerate(lines, 1) if l.startswith("| `beta-tool`"))
    return {"source_sha256": sha(raw), "qualifications": [], "rows": [
        {"line": first, "kind": "skill", "members": [
            {"id": "alpha-skill", "name": "alpha-skill", "source_text": "`alpha-skill`"}]},
        {"line": second, "kind": "skill", "members": [
            {"id": "beta-tool", "name": "beta-tool", "source_text": "`beta-tool`"},
            {"id": "gamma-tool", "name": "gamma-tool", "source_text": "`gamma-tool`"}]}]}


SOURCE_TARGETS = {"alpha-record", "shared-record", "source-page", "register-design", "related-design"}


def migrated(name, instant="2026-03-10T10:00:00Z", zone=LONDON, raw=SOURCE):
    """A fresh vault holding only the handwritten source, migrated through the writer."""
    base = seeded(name + "-seed", instant, zone)
    vault = base.vault.parent / "import"
    vault.mkdir()
    ctx = D.Context(vault, base.home, base.locks)
    T.write(ctx.page, raw)
    with clock(instant, zone):
        doc = W.commit(ctx, W.proposal(ctx, "migrate", {"source_sha256": sha(raw), "mapping": source_mapping(raw)}))
    return ctx, doc


def managed_row(ctx, rid, record_links=None, notes=None):
    doc = current(ctx)
    row = T.add_cli(doc, ctx, rid)
    if record_links is not None:
        row["record_links"] = record_links
    if notes is not None:
        row["notes"] = notes
    T.bind_evidence(doc, ctx, [row])
    return doc


# --------------------------------------------------------------------------- cases

def case_d1(root):
    ctx = seeded("d1")
    seed_page = page_bytes(ctx)
    check(field(seed_page, "updated") == "2026-03-10", "D1 seed dated the proposal's local day")
    edit_prose(ctx, "A real prose change.", "2026-03-11T10:00:00Z")
    page = page_bytes(ctx)
    check(field(page, "updated") == "2026-03-11" and current(ctx)["page"]["metadata"]["updated"] == "2026-03-11",
          "D1 a prose change on D+1 dates data and page D+1; full receipt load succeeds")
    with clock("2026-03-12T10:00:00Z", LONDON):
        doc = managed_row(ctx, "tool-a")
        T.save_doc(ctx, doc)
    check(field(page_bytes(ctx), "updated") == "2026-03-12", "D1 a row and note change dates its day")
    with clock("2026-03-13T10:00:00Z", LONDON):
        T.activate(ctx, ["tool-a"])
    check(field(page_bytes(ctx), "updated") == "2026-03-13", "D1 a lifecycle change (activation) dates its day")
    rev = current(ctx)["revision"]
    edit_prose(ctx, "A further change the same day.", "2026-03-13T18:00:00Z")
    page = page_bytes(ctx)
    check(field(page, "updated") == "2026-03-13" and current(ctx)["revision"] == rev + 1 and
          b"A further change the same day." in page, "D1 a further same-day change keeps the date and publishes")


def freshness_register(name, seed_instant, build_instant, zone=LONDON):
    """A register seeded on one day with a managed skill row added on a later day: two skill trees
    whose comparisons carry captured evidence and no recorded event yet (tier unproven). This is
    the writer suite's skill fixture built with every clock frozen at build_instant, so its events
    can be recorded on later days. Returns the context and the events to record, in order."""
    ctx = seeded(name, seed_instant, zone)
    with clock(build_instant, zone), patch.object(D, "now", lambda: build_instant):
        doc = current(ctx)
        install = T.installation("skill", [])
        resources = []
        for label in ("primary", "dependency"):
            tree = ctx.home / "trees" / label
            T.write(tree / "SKILL.md", "---\nname: " + label + "\n---\nUse the frozen fixture.")
            T.write(tree / "reference.txt", "The answer is in the fixture.")
            carrier = ctx.home / ".claude/skills" / label
            carrier.symlink_to(tree)
            resources += [T.resource(label, "skill-tree", tree,
                                     {"sha256": T.S.tree_hash(tree), "entry": "SKILL.md", "references": ["reference.txt"],
                                      "carrier_id": label + "-carrier", "pin_sha256": D.digest(install["pin"])},
                                     ["skill-content", "skill-invocation"], install["id"]),
                          T.resource(label + "-carrier", "carrier", carrier,
                                     {"skill_name": label, "level": "auto", "kind": "symlink",
                                      "target_resource_id": label, "declaration": ""}, ["carrier-load"], install["id"])]
        install["resource_ids"] = [r["id"] for r in resources]
        row = T.normal_row("skill", resources, "skill")
        doc["resources"], doc["installations"], doc["rows"] = resources, [install], [row]
        doc["jobs"] = [{"id": "skill-job", "label": "Skill fixture", "definition": "Frozen task", "notes": []}]
        release = build_instant[:10]
        for model in ("model-a-release", "model-b-release"):
            T.add_evidence(doc, ctx, model, {"type": "model-release", "model_id": model, "release_date": release},
                           kind="captured-source")
        doc["policy"]["model_targets"] = [{"model_id": "model-a-release", "release_date": release,
                                           "evidence_refs": ["model-a-release"]}]
        row["freshness"] = {"status": "applicable", "skills": []}
        for tree in [r for r in resources if r["type"] == "skill-tree"]:
            eid, task = tree["id"] + "-date", tree["id"] + "-task"
            T.add_evidence(doc, ctx, eid, {"type": "version-date", "resource_id": tree["id"],
                                           "pin_sha256": D.digest(install["pin"]), "tree_sha256": tree["expected"]["sha256"],
                                           "version_date": release}, kind="captured-source")
            row["freshness"]["skills"].append({"resource_id": tree["id"],
                "candidate": {"installation_id": install["id"], "pin_sha256": D.digest(install["pin"]),
                              "skill_tree_sha256": tree["expected"]["sha256"], "version_label": "1.0.0",
                              "version_date": release, "date_basis": "relevant-file-revision", "date_evidence_refs": [eid]},
                "comparisons": [{"model_id": "model-a-release", "model_release_date": release,
                                 "release_evidence_refs": ["model-a-release"], "applicability_evidence_refs": [task],
                                 "evaluated_at": build_instant, "rule_version": 2, "result": "pass", "reasons": [],
                                 "tier": "unproven", "proof_route": "comparison", "claim_evidence_refs": [], "events": []}],
                "applicability_evidence": [task]})
        T.bind_tasks(doc, ctx)
        T.bind_evidence(doc, ctx)
        events = []
        for r in doc["rows"]:
            for skill in r["freshness"].get("skills", []):
                for c in skill["comparisons"]:
                    events += [{"row_id": r["id"], "resource_id": skill["resource_id"], "model_id": c["model_id"],
                                "event": e} for e in c["events"]]
                    c.update(events=[], tier="unproven", result="unknown")
        parent = current(ctx)
        changes = {k: doc[k] for k in ("jobs", "installations", "resources", "rows", "evidence", "policy", "page")
                   if doc[k] != parent[k]}
        W.commit(ctx, W.proposal(ctx, "edit", changes))
    return ctx, events


def case_d1_freshness(root):
    """D1, freshness half (closed check F6): a freshness transition recorded on a later day changes
    the rendered body and takes that day; body, date and the complete tuple are checked each time."""
    ctx, events = freshness_register("d1f", "2026-03-10T10:00:00Z", "2026-03-11T10:00:00Z")
    pending = [e for e in events if e["event"]["action"] in ("claim", "comparison")]
    dot = " &#183; "   # the renderer escapes the middle dot in table cells and details
    unproven = ("primary: unproven" + dot + "model-a-release" + dot + "comparison").encode()
    check(len(pending) == 4 and [e["event"]["action"] for e in pending] == ["claim", "comparison"] * 2 and
          unproven in body(page_bytes(ctx)), "D1-freshness arm: a managed skill row with two comparisons, no event recorded yet")
    def transition(event, instant, label, shown_tier):
        before_page, before_doc = page_bytes(ctx), current(ctx)
        with clock(instant, LONDON):
            W.commit(ctx, W.proposal(ctx, "record-freshness", event))
        page = page_bytes(ctx)
        doc, data_raw = D.load_current(ctx)
        receipt = json.loads(ctx.receipt.read_bytes())
        head, rest = split(page)
        expected = day(instant, LONDON)
        check(rest != body(before_page) and shown_tier.encode() in rest,
              label + ": the rendered body changes and shows the new tier")
        check(field(page, "updated") == expected and doc["page"]["metadata"]["updated"] == expected,
              label + ": data and page take the transition's local day " + expected)
        check(doc["revision"] == before_doc["revision"] + 1 and receipt["revision"] == doc["revision"] and
              receipt["data_sha256"] == sha(data_raw) and receipt["page_sha256"] == sha(page) and
              field(page, "register-revision") == doc["revision"] and field(page, "register-data-sha256") == sha(data_raw) and
              [l for l in head.split(b"\n") if l.startswith(b"register-body-sha256")] ==
              [b'register-body-sha256: "' + sha(rest).encode() + b'"'],
              label + ": complete tuple integrity (data, receipt, page, revision and body digest agree; full load)")
    transition(pending[0], "2026-03-12T10:00:00Z", "D1-freshness claim recorded on D+2",
               "primary: claimed" + dot + "model-a-release" + dot + "comparison pending")
    transition(pending[1], "2026-03-13T10:00:00Z", "D1-freshness comparison recorded on D+3",
               "primary: proven" + dot + "model-a-release" + dot + "comparison")
    transition(pending[2], "2026-03-13T18:00:00Z", "D1-freshness a further transition the same day keeps D+3",
               "dependency: claimed" + dot + "model-a-release" + dot + "comparison pending")


def case_d1_preserve(root):
    ctx = seeded("d1p")
    def stages():
        seen = []
        return seen, seen.append
    for label, make in (
            ("empty edit", lambda doc: ("edit", {})),
            ("identical full-page edit", lambda doc: ("edit", {"page": copy.deepcopy(doc["page"])})),
            ("identical prose", lambda doc: ("edit-prose", {"page": {"prose_blocks": copy.deepcopy(doc["page"]["prose_blocks"])}})),
            ("reordered object keys", lambda doc: ("edit", {"page": dict(reversed(list(copy.deepcopy(doc["page"]).items())))}))):
        before = page_bytes(ctx)
        rev = current(ctx)["revision"]
        seen, hook = stages()
        with clock("2026-03-11T10:00:00Z", LONDON):
            operation, changes = make(current(ctx))
            W.commit(ctx, W.proposal(ctx, operation, changes), hook=hook)
        after = page_bytes(ctx)
        check(body(after) == body(before) and field(after, "register-body-sha256") == field(before, "register-body-sha256")
              and field(after, "updated") == field(before, "updated") == "2026-03-10",
              "D1-preserve " + label + ": exact body, digest and updated kept")
        check(current(ctx)["revision"] == rev + 1 and "after-page" in seen and "after-clear" in seen and after != before,
              "D1-preserve " + label + ": ordinary publication ran (revision, final page publication, journal clear)")
    edit_page(ctx, "2026-03-12T10:00:00Z", title="Owner title")
    after = page_bytes(ctx)
    check(field(after, "title") == "Owner title" and field(after, "updated") == "2026-03-10",
          "D1-preserve a title edit publishes as frontmatter only; updated kept")
    edit_prose(ctx, "Genuine change.", "2026-03-12T11:00:00Z")
    check(field(page_bytes(ctx), "updated") == "2026-03-12", "D1-preserve control: a genuine prose change moves the date")
    with clock("2026-03-12T12:00:00Z", LONDON):
        stale = W.proposal(ctx, "edit", {})
        W.commit(ctx, W.proposal(ctx, "edit", {}))
        refuses(lambda: W.commit(ctx, stale), "D1-preserve stale expectation still refuses", codes=(3,), ctx=ctx)


def case_d3(root):
    ctx = seeded("d3")
    doc = current(ctx)
    with clock("2026-03-11T10:00:00Z", LONDON):
        for label, mutate in (
                ("updated alone", lambda p: p["metadata"].update(updated="2026-01-01")),
                ("updated with content", lambda p: (p["metadata"].update(updated="2026-01-01"),
                                                    p["prose_blocks"].append({"id": "x", "section": "Notes", "kind": "paragraph",
                                                    "content": [{"type": "text", "text": "content"}], "provenance": []}))),
                ("layout override", lambda p: p.update(layout_version=1))):
            page = copy.deepcopy(doc["page"])
            mutate(page)
            request = W.proposal(ctx, "edit", {"page": page})
            refuses(lambda: W.commit(ctx, request), "D3 writer-owned " + label + " refuses", codes=(2,), ctx=ctx,
                    text="writer-owned field page.")
        page = copy.deepcopy(doc["page"])
        page["metadata"]["audited"] = "2026-03-11"
        W.commit(ctx, W.proposal(ctx, "edit", {"page": page}))
    check(field(page_bytes(ctx), "audited") == "2026-03-11", "D3 carrying the existing updated and layout succeeds")
    ctx.page.write_bytes(page_bytes(ctx) + b"drift\n")
    with clock("2026-03-12T10:00:00Z", LONDON):
        page = copy.deepcopy(current_parent(ctx)["page"])
        page["metadata"]["updated"] = "2026-01-02"
        request = W.proposal(ctx, "reconcile-page", {"typed_changes": {"page": page}}, observed(ctx))
        refuses(lambda: W.commit(ctx, request), "D3 writer-owned updated refuses inside typed reconciliation",
                codes=(2,), ctx=ctx, text="writer-owned field page.metadata.updated")
        page["metadata"]["updated"] = current_parent(ctx)["page"]["metadata"]["updated"]
        W.commit(ctx, W.proposal(ctx, "reconcile-page", {"typed_changes": {"page": page}}, observed(ctx)))
    check(D.load_current(ctx)[0]["commit"]["operation"] == "reconcile-page",
          "D3 typed reconciliation carrying the existing values succeeds")


def current_parent(ctx):
    receipt = json.loads(ctx.receipt.read_bytes())
    return json.loads((ctx.objects / receipt["data_sha256"]).read_bytes())


def case_d4(root):
    instant = "2026-03-10T23:30:00Z"
    for zone in (LONDON, TOKYO, LA):
        ctx = seeded("d4-" + zone.split("/")[1].lower(), instant, zone)
        request = None
        with clock(instant, zone):
            request = W.proposal(ctx, "edit", {})
        offset = dt.datetime.fromisoformat(instant.replace("Z", "+00:00")).astimezone(ZoneInfo(zone)).strftime("%z")
        offset = offset[:3] + ":" + offset[3:]
        check(request["at"].endswith(offset) and request["at"][:10] == day(instant, zone) and
              field(page_bytes(ctx), "updated") == day(instant, zone),
              "D4 one instant in " + zone + " records its own local day " + day(instant, zone) + " and offset " + offset)
    ctx = seeded("d4-spellings", instant, TOKYO)
    spelt = set()
    for spelling in ("2026-03-10T23:30:00Z", "2026-03-11T08:30:00+09:00", "2026-03-10T23:30:00.000000+00:00",
                     "2026-03-10T18:30:00-05:00"):
        with clock(spelling, TOKYO):
            spelt.add(W.proposal(ctx, "edit", {})["at"])
    check(len(spelt) == 1 and next(iter(spelt)).startswith("2026-03-11T08:30:00") and next(iter(spelt)).endswith("+09:00"),
          "D4 equivalent spellings of one instant become one local timestamp " + str(sorted(spelt)))
    ctx = seeded("d4-apply", "2026-03-10T10:00:00Z", TOKYO)
    with clock("2026-03-11T08:30:00+09:00", TOKYO):
        doc = current(ctx)
        blocks = [{"id": "late", "section": "Notes", "kind": "paragraph",
                   "content": [{"type": "text", "text": "Proposed before midnight."}], "provenance": []}]
        request = W.proposal(ctx, "edit-prose", {"page": {"prose_blocks": blocks}})
        first, second = W.preview(ctx, request), W.preview(ctx, request)
        expected = render(W.transformed(ctx, doc, request))
    check(first["page_diff"] == second["page_diff"] and first["data_diff"] == second["data_diff"], "D4 repeated previews match")
    check((first.get("page_date") or {}).get("updated") == "2026-03-11" and "local day" in (first.get("page_date") or {}).get("rule", ""),
          "D4 the preview states the page date and its rule")
    with clock("2026-03-12T09:00:00Z", LA):
        W.commit(ctx, request)
    check(page_bytes(ctx) == expected and field(page_bytes(ctx), "updated") == "2026-03-11",
          "D4 applied after local and UTC midnight in another zone: exact previewed bytes and the proposal's day")
    with clock("2026-03-01T12:00:00Z", LONDON):
        edit = W.proposal(ctx, "edit-prose", {"page": {"prose_blocks": blocks + [{"id": "back", "section": "Notes",
                          "kind": "paragraph", "content": [{"type": "text", "text": "Clock rolled back."}], "provenance": []}]}})
        W.commit(ctx, edit)
    check(field(page_bytes(ctx), "updated") == "2026-03-01", "D4 a rolled-back proposal is accepted and dated as captured, no clamping")
    with clock("2026-03-20T10:00:00Z", LONDON):
        request = W.proposal(ctx, "edit-prose", {"page": {"prose_blocks": blocks}})
        class Interrupted(Exception):
            pass
        def stop(point):
            if point == "after-receipt":
                raise Interrupted(point)
        try:
            W.commit(ctx, request, hook=stop)
        except Interrupted:
            pass
    with clock("2026-03-25T10:00:00Z", TOKYO):
        outcome = W.recover(ctx)
    check(outcome == "new" and field(page_bytes(ctx), "updated") == "2026-03-20" and current(ctx)["commit"]["at"] == request["at"],
          "D4 cross-day recovery publishes the journalled date")
    with clock("2026-03-21T10:00:00Z", LONDON):
        bad = W.proposal(ctx, "edit", {})
        bad["at"] = "2026-02-30T10:00:00Z"
        bad["proposal_sha256"] = D.digest({k: v for k, v in bad.items() if k != "proposal_sha256"})
        refuses(lambda: W.commit(ctx, bad), "D4 an invalid timestamp still refuses", ctx=ctx)
        stale = W.proposal(ctx, "edit", {})
        W.commit(ctx, W.proposal(ctx, "edit", {}))
        refuses(lambda: W.commit(ctx, stale), "D4 stale data still refuses", codes=(3,), ctx=ctx)


def case_d4_activation(root):
    """N2: an activation proposed late on day D and applied after local midnight writes an apply-time
    instant into the body; the page date is the later local day, and the preview says so."""
    ctx = seeded("d4n2", "2026-03-19T10:00:00Z", LONDON)
    with clock("2026-03-19T11:00:00Z", LONDON):
        T.save_doc(ctx, managed_row(ctx, "tool-n"))
    proposed, applied = "2026-03-20T23:50:00Z", "2026-03-21T00:10:00.000000+00:00"
    with clock(proposed, LONDON, apply_instant="2026-03-20T23:55:00.000000+00:00"):
        request = W.proposal(ctx, "activate", {"row_ids": ["tool-n"], "reason": "cross-day activation"})
        shown = W.preview(ctx, request).get("page_date") or {}
    check(shown.get("proposal_day") == "2026-03-20" and "apply-time" in shown.get("rule", ""),
          "D4/N2 the preview states the proposal day and the apply-time rule")
    with clock(applied, LONDON):
        W.commit(ctx, request)
    page = page_bytes(ctx)
    verified = current(ctx)["rows"][0]["lifecycle"]["activation"]["verified_at"]
    check(verified == applied and b"last verified 2026-03-21T00:10:00.000000" in body(page),
          "D4/N2 the apply-time instant is in the body")
    check(field(page, "updated") == "2026-03-21",
          "D4/N2 the page date is the later local day of the proposal (2026-03-20) and the apply-time instant (2026-03-21)")
    later = [d for d in re.findall(rb"\d{4}-\d\d-\d\d", body(page)) if d.decode() > field(page, "updated")]
    check(not later, "D4/N2 no body date postdates updated: (the deep-lint accuracy rule)")


def case_d5(root):
    ctx = seeded("d5")
    for label, meta in (("audited", {"audited": "2026-03-12"}), ("confidence", {"confidence": "medium"}),
                        ("identical repeat", {"confidence": "medium"})):
        before = page_bytes(ctx)
        rev = current(ctx)["revision"]
        edit_page(ctx, "2026-03-12T10:00:00Z", **meta)
        after = page_bytes(ctx)
        check(current(ctx)["revision"] == rev + 1 and body(after) == body(before) and
              field(after, "register-body-sha256") == field(before, "register-body-sha256") and
              field(after, "updated") == "2026-03-10",
              "D5 typed " + label + " edit publishes with body, digest and updated fixed")
    check(field(page_bytes(ctx), "audited") == "2026-03-12" and field(page_bytes(ctx), "confidence") == "medium",
          "D5 the assessed values are published in the frontmatter")
    good = page_bytes(ctx)
    ctx.page.write_bytes(good.replace(b'audited: "2026-03-12"', b'audited: "2026-03-13"'))
    refuses(lambda: D.load_current(ctx), "D5 a direct Markdown audit edit is PAGE DRIFT", codes=(1,), text="PAGE DRIFT")
    ctx.page.write_bytes(good)
    with clock("2026-03-14T10:00:00Z", LONDON):
        doc = current(ctx)
        page = copy.deepcopy(doc["page"])
        page["metadata"]["audited"] = "2026-03-14"
        page["prose_blocks"].append({"id": "repair", "section": "Notes", "kind": "paragraph",
                                     "content": [{"type": "text", "text": "Prose repair."}], "provenance": []})
        W.commit(ctx, W.proposal(ctx, "edit", {"page": page}))
    check(field(page_bytes(ctx), "updated") == "2026-03-14" and body(page_bytes(ctx)) != body(good),
          "D5 a combined audit and prose repair changes the body and its date")


def case_d6(root):
    ctx = seeded("d6")
    hostile = ("\n---\nregister-body-sha256: \"" + "a" * 64 + "\"\n## Related\n" + OPEN + "evil" + CLOSE +
               "\n<!-- register-data -->\n")
    edit_prose(ctx, hostile, "2026-03-11T10:00:00Z")
    page = page_bytes(ctx)
    head, rest = split(page)
    declared = [l for l in head.split(b"\n") if l.startswith(b"register-body-sha256")]
    check(len(declared) == 1 and declared[0] == b'register-body-sha256: "' + sha(rest).encode() + b'"',
          "D6 exactly one canonical digest line equals an independent SHA-256 of the exact body")
    doc = current(ctx)
    check(field(page, "register-revision") == doc["revision"] and field(page, "register-committed") == doc["commit"]["at"]
          and field(page, "register-data-sha256") == sha(D.encoded(doc)),
          "D6 revision, commit time and data digest are in the frontmatter")
    check(b"\nRevision " not in rest and b"register-data " not in rest.replace(b"&#60;!-- register-data", b""),
          "D6 the body carries no commit envelope")
    check(rest.count(b"\n## Related\n") == 1 and "evil" not in targets(section(page, "Related") or []) and
          b"\n---\nregister-body-sha256" not in rest, "D6 hostile typed text cannot add a marker, a heading or a link target")
    check(sha(rest) != sha(rest.replace(b"\n", b"\r\n")), "D6 LF and CRLF bodies have different digests")
    bad = copy.deepcopy(doc)
    bad["page"]["prose_blocks"].append({"id": "pipe", "section": "Notes", "kind": "paragraph",
                                        "content": [{"type": "link", "target": "bad|target", "label": "x"}], "provenance": []})
    refuses(lambda: render(bad), "D6 a structural target character refuses with a diagnostic", codes=(2,), text="unsafe")
    data_path = need("instance-data", ARGS.instance_data)
    instance = data_path.parent
    receipt = json.loads((instance / "register-state/receipt.json").read_bytes())
    data = json.loads(data_path.read_bytes())
    stored = (instance.parent.parent / REG).read_bytes()
    check(render(data) == stored and sha(stored) == receipt["page_sha256"],
          "D6 a saved v2/layout-1 tuple re-renders to its exact page and receipt")
    import adopt_compat_v1
    old_data = next(p for p in (instance / "register-state/objects").iterdir()
                    if p.read_bytes()[:1] == b"{" and json.loads(p.read_bytes()).get("schema_version") == 1)
    old = json.loads(old_data.read_bytes())
    old_page = adopt_compat_v1.render(old)
    check((instance / "register-state/objects" / sha(old_page)).is_file(),
          "D6 the saved frozen v1 tuple re-renders to its archived page bytes")


def need(label, path):
    if path is None or not Path(path).is_file():
        raise Unrun(label + " not found at " + str(path))
    return Path(path)


def case_d7(root):
    ctx, doc = migrated("d7", "2026-03-10T10:00:00Z", LONDON)
    page = page_bytes(ctx)
    check(field(page, "updated") == "2026-03-10" and field(page, "created") == "2026-01-05" and
          field(page, "audited") == "2026-03-01", "D7 the migrated page takes the proposal's day; created and audited kept")
    check((ctx.objects / sha(SOURCE)).read_bytes() == SOURCE, "D7 the source archive is byte-exact")
    mapping = source_mapping(SOURCE)
    result = G.verify_coverage(SOURCE, doc, mapping)
    check(result["source_rows"] == 2 and result["destination_rows"] == 3 and result["covered_bytes"] == len(SOURCE),
          "D7 forward and reverse coverage with non-zero row controls")
    tampers = (("new date", lambda d: d["page"]["metadata"].update(updated="2026-03-11")),
               ("audited", lambda d: d["page"]["metadata"].update(audited="2026-03-02")),
               ("created", lambda d: d["page"]["metadata"].update(created="2026-01-06")),
               ("title", lambda d: d["page"]["metadata"].update(title="Other")),
               ("row", lambda d: d["rows"].pop()),
               ("cell", lambda d: d["rows"][0]["notes"][0].update(text="changed")),
               ("linked target", lambda d: d["rows"][0]["notes"][2]["links"][0].update(path="moved-record")),
               ("prose", lambda d: d["page"]["prose_blocks"][-1]["content"].pop()),
               ("archive hash", lambda d: d["migration"].update(source_archive="0" * 64)))
    for label, mutate in tampers:
        bad = copy.deepcopy(doc)
        mutate(bad)
        refuses(lambda: G.verify_coverage(SOURCE, bad, mapping), "D7 coverage catches a tampered " + label)


def layout1_tuple(ctx):
    """Re-persist the current data as a v2/layout-1 tuple, the way an earlier writer published it."""
    doc = current(ctx)
    doc["page"]["layout_version"] = 1
    raw, page = D.encoded(doc), render(doc)
    receipt = D.encoded({"register_id": doc["register_id"], "revision": doc["revision"], "data_sha256": sha(raw),
                         "page_sha256": sha(page), "transaction_id": "00000000-0000-4000-8000-000000000001"})
    for path, content in ((ctx.data, raw), (ctx.page, page), (ctx.receipt, receipt)):
        W.publish(path, content)
        W.archive(ctx, content)
    return [raw, receipt, page]


def case_d8(root):
    for label, change in (("body edit", True), ("empty transaction", False)):
        ctx = seeded("d8-" + label.split()[0])
        old = layout1_tuple(ctx)
        check(b"\nRevision " in old[2] and field(old[2], "register-body-sha256") is None, "D8 arm: a layout-1 tuple is in place (" + label + ")")
        if change:
            edit_prose(ctx, "Body edit on layout 1.", "2026-03-11T10:00:00Z")
        else:
            with clock("2026-03-11T10:00:00Z", LONDON):
                W.commit(ctx, W.proposal(ctx, "edit", {}))
        page = page_bytes(ctx)
        check(current(ctx)["page"]["layout_version"] == 2 and field(page, "register-body-sha256") == sha(body(page)) and
              field(page, "updated") == "2026-03-11", "D8 a " + label + " on layout 1 promotes to layout 2 and is dated")
        check(all((ctx.objects / sha(x)).read_bytes() == x for x in old), "D8 the old layout-1 objects are preserved byte-exact")
    ctx = seeded("d8-repair")
    committed = page_bytes(ctx)
    planted = committed + b"hand edit\n"
    ctx.page.write_bytes(planted)
    with clock("2026-03-12T10:00:00Z", LONDON):
        W.commit(ctx, W.proposal(ctx, "reconcile-page", {"discard": True}, observed(ctx)))
    check((ctx.objects / sha(planted)).read_bytes() == planted and field(page_bytes(ctx), "updated") == "2026-03-12",
          "D8 a body repair archives the observed edit and is dated")
    for label, old_line, new_line in (("date-only", b'updated: "2026-03-12"', b'updated: "2026-03-15"'),
                                      ("audit-only", b'audited: "2026-03-10"', b'audited: "2026-03-15"')):
        good = page_bytes(ctx)
        ctx.page.write_bytes(good.replace(old_line, new_line))
        rev = current_parent(ctx)["revision"]
        with clock("2026-03-16T10:00:00Z", LONDON):
            W.commit(ctx, W.proposal(ctx, "reconcile-page", {"discard": True}, observed(ctx)))
        page = page_bytes(ctx)
        check(field(page, "updated") == "2026-03-12" and body(page) == body(good) and current(ctx)["revision"] == rev + 1,
              "D8 a " + label + " drift repair keeps the committed date and body")
    ctx.page.write_bytes(page_bytes(ctx) + b"typed\n")
    rev = current_parent(ctx)["revision"]
    with clock("2026-03-17T10:00:00Z", LONDON):
        doc = current_parent(ctx)
        page = copy.deepcopy(doc["page"])
        page["prose_blocks"].append({"id": "typed", "section": "Notes", "kind": "paragraph",
                                     "content": [{"type": "text", "text": "Typed repair."}], "provenance": []})
        W.commit(ctx, W.proposal(ctx, "reconcile-page", {"typed_changes": {"page": page}}, observed(ctx)))
    check(current(ctx)["revision"] == rev + 1 and current(ctx)["commit"]["operation"] == "reconcile-page" and
          field(page_bytes(ctx), "updated") == "2026-03-17", "D8 typed reconciliation finalises once, dated")
    for label, damage, day_ in (
            ("missing page", lambda p: ctx.page.unlink(), "2026-03-18"),
            ("unclosed frontmatter", lambda p: ctx.page.write_bytes(p[:len(p) - len(body(p))].rsplit(b"---", 1)[0] + body(p)), "2026-03-19"),
            ("body-only page", lambda p: ctx.page.write_bytes(body(p)), "2026-03-20")):
        damage(page_bytes(ctx))
        with clock(day_ + "T10:00:00Z", LONDON):
            W.commit(ctx, W.proposal(ctx, "reconcile-page", {"discard": True}, observed(ctx)))
        check(field(page_bytes(ctx), "updated") == day_, "D8 a " + label + " repair counts as a body change")


def case_d8_absorb(root):
    """N5: a hand edit absorbed into the data by typed reconciliation moves the date, even though the
    candidate body equals the observed one, because it differs from the committed parent's body."""
    ctx = seeded("d8n5")
    edit_prose(ctx, "Committed text.", "2026-03-11T10:00:00Z")
    committed = page_bytes(ctx)
    doc = current(ctx)
    page = copy.deepcopy(doc["page"])
    page["prose_blocks"][-1]["content"] = [{"type": "text", "text": "Hand-edited text."}]
    candidate = copy.deepcopy(doc)
    candidate["page"] = page
    hand = split(committed)[0] and committed[:len(committed) - len(body(committed))].replace(b'updated: "2026-03-11"', b'updated: "2026-03-12"')
    absorbed_body = body(render(candidate))
    ctx.page.write_bytes(hand + absorbed_body)
    refuses(lambda: D.load_current(ctx), "D8/N5 arm: the hand-edited, hook-stamped page is PAGE DRIFT", codes=(1,))
    with clock("2026-03-13T10:00:00Z", LONDON):
        W.commit(ctx, W.proposal(ctx, "reconcile-page", {"typed_changes": {"page": page}}, observed(ctx)))
    after = page_bytes(ctx)
    check(body(after) == absorbed_body, "D8/N5 the reconciled body equals the observed hand-edited body")
    check(field(after, "updated") == "2026-03-13",
          "D8/N5 absorbing a hand edit moves the date to the proposal day, never back to the committed 2026-03-11")


def case_r1(root):
    ctx, doc = migrated("r1")
    with clock("2026-03-11T10:00:00Z", LONDON):
        doc = managed_row(ctx, "tool-r", record_links=[
            {"status": "linked", "path": "records/Café notes#Usage", "label": "Café notes"},
            {"status": "unresolved", "label": "Missing record", "reason": "not written yet"}])
        doc["page"]["prose_blocks"].append({"id": "web", "section": "Notes", "kind": "paragraph",
            "content": [{"type": "link", "target": "https://example.test/doc", "label": "web"}], "provenance": []})
        T.save_doc(ctx, doc)
    page = page_bytes(ctx)
    related = section(page, "Related")
    expected = SOURCE_TARGETS | {"records/Café notes#Usage"}
    check(related is not None and targets(related) == expected,
          "R1 one real Related section lists every recorded local target: " + str(sorted(targets(related or []))))
    check("Missing record" not in "\n".join(related) and "https://example.test/doc" not in "\n".join(related),
          "R1 unresolved entries and web addresses are not wiki targets")
    sources = section(page, "Sources Used")
    check(sources is not None and targets(sources) == {"source-page", "register-design"},
          "R1 Sources Used lists the recorded source tokens")
    removed = copy.deepcopy(current(ctx))
    for row in removed["rows"]:
        for note in row["notes"]:
            note["links"] = [l for l in note["links"] if l.get("path") != "shared-record"]
    check(targets(section(render(removed), "Related")) != expected,
          "R1 control: a removed record target fails the independent target-set comparison")
    empty = seeded("r1-empty")
    fallback = section(page_bytes(empty), "Related")
    check(fallback is not None and targets(fallback) == {"index"} and "navigation" in "\n".join(fallback),
          "R1 an empty register links the index as labelled navigation")
    for bad in ("bad|pipe", "bad" + CLOSE + "close", "line\nbreak", "bell\x07"):
        broken = copy.deepcopy(current(ctx))
        broken["page"]["prose_blocks"].append({"id": "unsafe", "section": "Notes", "kind": "paragraph",
            "content": [{"type": "link", "target": bad, "label": "x"}], "provenance": []})
        try:
            render(broken)
            raise AssertionError("unsafe target rendered: " + repr(bad))
        except D.Problem as exc:
            check("unsafe" in str(exc), "R1 unsafe target " + repr(bad) + " refuses before publication")
    # N8: a converted (managed) row's linked note links still feed Related.
    with clock("2026-03-12T10:00:00Z", LONDON):
        doc = managed_row(ctx, "converted", notes=[{"id": "cell-1", "text": "Record cell",
            "links": [{"status": "linked", "path": "converted-record", "label": "converted-record"}],
            "supersedes_note_ids": []}])
        T.save_doc(ctx, doc)
    check("converted-record" in targets(section(page_bytes(ctx), "Related")),
          "R1/N8 a converted managed row's linked note link stays in Related")
    checker = need("required-sections", ARGS.required_sections)
    vault = root / "r1-lint"
    (vault / "raw").mkdir(parents=True)
    T.write(vault / REG, page_bytes(ctx))
    clean = subprocess.run([sys.executable, "-B", str(checker), "--vault", str(vault)], capture_output=True, text=True)
    check(clean.returncode == 0, "R1 the unchanged required-sections checker reports zero for the generated page")
    T.write(vault / REG, page_bytes(ctx).replace(b"\n## Sources Used\n", b"\n## Sources\n"))
    planted = subprocess.run([sys.executable, "-B", str(checker), "--vault", str(vault)], capture_output=True, text=True)
    check(planted.returncode == 1 and "Sources Used" in planted.stdout, "R1 positive control: a missing Sources Used is caught")
    check(section(page_bytes(ctx).replace(b"\n## Related\n", b"\n## Elsewhere\n"), "Related") is None,
          "R1 native assertion: removing Related is caught (the checker does not require it for development pages)")
    data_path = need("instance-data", ARGS.instance_data)
    data = json.loads(data_path.read_bytes())
    source = (data_path.parent / "register-state/objects" / data["migration"]["source_archive"]).read_bytes()
    census = targets(body(source).decode().split("\n"))
    data["page"]["layout_version"] = 2
    produced = targets(section(render(data), "Related"))
    check(census and census <= produced,
          "R1 real-data copy: all %d source targets appear among %d Related targets" % (len(census), len(produced)))


def case_r2(root):
    ctx, doc = migrated("r2")
    vault = ctx.vault
    (vault / "raw").mkdir(exist_ok=True)
    T.write(vault / "wiki/index.md", b"---\ntitle: Index\ntype: index\n---\n\n# Index\n")
    check(section(page_bytes(ctx), "Related") is not None, "R2 arm: the generated page has a real Related section")
    related = targets(section(page_bytes(ctx), "Related"))
    for target in related:
        T.write(vault / "wiki/concepts" / (target + ".md"), b"---\ntitle: t\ntype: concept\n---\n\n## Related\n\n- " +
                OPEN.encode() + b"index" + CLOSE.encode() + b"\n")
    checker = need("link-check", ARGS.link_check)
    clean = subprocess.run([sys.executable, "-B", str(checker), "--vault", str(vault)], capture_output=True, text=True)
    scanned = re.search(r"\| (\d+) page links", clean.stdout)
    check(clean.returncode == 0 and "DEAD LINKS: 0" in clean.stdout and scanned and int(scanned.group(1)) >= len(related),
          "R2 the unchanged link reader resolves every generated Related target (positive link count)")
    (vault / "wiki/concepts/related-design.md").unlink()
    planted = subprocess.run([sys.executable, "-B", str(checker), "--vault", str(vault)], capture_output=True, text=True)
    check(planted.returncode == 1 and "related-design" in planted.stdout, "R2 control: a missing target is caught on the same reader")
    adapter = need("lint-adapter", ARGS.lint_adapter)
    def capability(c):
        return subprocess.run([sys.executable, "-B", str(adapter), "--capability", "--vault", str(c.vault),
                               "--home", str(c.home), "--adopt-dir", str(ARGS.adopt_dir)], capture_output=True, text=True)
    seed = seeded("r2-clean")
    result = capability(seed)
    check(result.returncode == 0 and "control OK" in result.stdout, "R2 adapter capability arm: a clean seed reports zero with its control")
    result = capability(ctx)
    check(result.returncode == 1 and "legacy findings" in result.stdout and "alpha-skill" in result.stdout,
          "R2 adapter capability arm: a migrated register reports its legacy findings")
    seed.page.write_bytes(page_bytes(seed) + b"drift\n")
    result = capability(seed)
    check(result.returncode == 1 and "PAGE DRIFT" in result.stdout, "R2 adapter capability arm: a hand edit is PAGE DRIFT")


def case_i2(root):
    script = need("audit-pools", ARGS.audit_pools)
    ctx = seeded("i2")
    vault = ctx.vault
    T.write(vault / "wiki/index.md", b"---\ntitle: Index\ntype: index\nconfidence: high\nupdated: 2026-03-01\n---\n\n# Index\nAdded 2026-02-01.\n- " +
            OPEN.encode() + b"capability-register" + CLOSE.encode() + b" - register\n- " + OPEN.encode() + b"plain" + CLOSE.encode() + b" - plain\n")
    T.write(vault / "wiki/log.md", b"---\ntitle: Log\ntype: log\n---\n\n## [2026-03-01] init | fixture\n")
    T.write(vault / "wiki/concepts/plain.md", b"---\ntitle: Plain\ntype: concept\nconfidence: high\nupdated: 2026-03-01\n---\n\nPlain body.\n")
    edit_page(ctx, "2026-03-15T10:00:00Z", audited="2026-03-15")
    def pools():
        out = subprocess.run([sys.executable, "-B", str(script), "--vault", str(vault), "--today", "2026-03-20",
                              "--format", "json"], capture_output=True, text=True)
        if out.returncode != 0:
            raise AssertionError("audit-pools exit " + str(out.returncode) + ": " + (out.stdout + out.stderr)[-300:])
        return json.loads(out.stdout)
    result = pools()
    hits = {h["path"] for h in result["updated_accuracy"]["hits"]}
    check(REG not in hits and result["updated_accuracy"]["control"]["caught"],
          "I2 after a later-day audit edit the moved envelope gives no false stale-body-date finding (control caught)")
    check(result["eligible"] == 2 and REG not in result["pools"]["unclassifiable"] and
          REG not in {item["path"] for item in result["confidence"]["invalid"]},
          "I2 the register stays audit-eligible and classifiable with a valid confidence (2 eligible pages: register and plain)")
    T.write(vault / "wiki/concepts/plain.md", b"---\ntitle: Plain\ntype: concept\nconfidence: high\nupdated: 2026-03-01\n---\n\nEdited 2026-03-18.\n")
    hits = {h["path"] for h in pools()["updated_accuracy"]["hits"]}
    check("wiki/concepts/plain.md" in hits, "I2 positive control: a planted older updated: on an ordinary page is caught")
    deep = need("deep-lint skill", ARGS.deep_lint_skill).read_text()
    lint = need("lint skill", ARGS.lint_skill).read_text()
    rule = "The generated capability register at `wiki/developments/capability-register.md` is never edited by hand in any step of this run"
    check(deep.count(rule) == 1 and lint.count(rule) == 1, "I2 one general no-hand-edit rule in each skill text")
    check("Metadata-only `audited:` and `confidence:` edits" in deep and "deep-lint head" in deep and
          "Metadata-only `audited:`" not in lint, "I2 the audit pre-authorisation is deep-lint's head, metadata only")
    check(deep.count("This rule still applies if its digest is missing or invalid") == 1 and
          lint.count("This rule still applies if its digest is missing or invalid") == 1,
          "I2 no marker-dependent hand-edit permission")
    check("Fix the cheap, unambiguous issues" in deep and "Lint checks a fix's effect by re-running the check that found it." in lint,
          "I2 the existing checks' text is retained")


def case_i4(root):
    import adopt_snapshot as S
    ctx = seeded("i4")
    settings = ctx.home / ".claude/settings.json"
    settings.write_bytes(b'{"enabledPlugins":{"p":true},"hooks":{"Stop":"fixture"}}\n')
    a = S.snapshot(ctx.home)
    settings.write_bytes(b'{"hooks":{"Stop":"fixture"},"enabledPlugins":{"p":true}}\n')
    b = S.snapshot(ctx.home)
    delta = S.changes(a, b)
    check(len(delta) == 1 and "#" not in delta[0]["address"], "I4 a key-order rewrite is one raw event and no typed-pointer event")
    check(S.compare(a, b, [])["findings"] > 0 and S.compare(a, b, delta)["findings"] == 0,
          "I4 undeclared rewrite is a finding; the exact declaration passes")
    settings.write_bytes(b'{"hooks":{"Stop":"changed"},"enabledPlugins":{"p":true}}\n')
    c = S.snapshot(ctx.home)
    check(any("#" in x["address"] for x in S.changes(b, c)), "I4 control: a value change gives a pointer event")


def case_no_write(root):
    ctx = seeded("nw")
    edit_prose(ctx, "Content for read paths.", "2026-03-11T10:00:00Z")
    for path in sorted(ctx.vault.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        path.chmod(0o500 if path.is_dir() else 0o400)
    ctx.vault.chmod(0o500)
    def manifest():
        out = {}
        for p in sorted(ctx.vault.parent.rglob("*")):
            info = p.lstat()
            out[str(p)] = (stat.S_IMODE(info.st_mode), info.st_mtime_ns, None if p.is_dir() else sha(p.read_bytes()))
        return out
    before = manifest()
    try:
        with clock("2026-03-12T10:00:00Z", LONDON):
            doc = current(ctx)
            render(doc)
            W.preview(ctx, W.proposal(ctx, "edit", {}))
            W.preview(ctx, W.proposal(ctx, "edit-prose", {"page": {"prose_blocks": []}}))
            refuses(lambda: W.preview(ctx, W.proposal(ctx, "edit-prose", {"page": {"prose_blocks": [], "title": "x"}})),
                    "N1-last refused read path")
        check(manifest() == before and any(k.endswith("capability-register.md") for k in before),
              "N1-last load, render and previews (successful and refused) leave SHA-256, modes and mtimes unchanged")
    finally:
        ctx.vault.chmod(0o700)
        for path in sorted(ctx.vault.rglob("*"), key=lambda p: len(p.parts)):
            path.chmod(0o700 if path.is_dir() else 0o600)
    pattern = re.compile(r"\b(?:write_text|write_bytes|mkdir|unlink|chmod|rmtree|Popen)\s*\(|\bos\.(?:write|replace|remove|rename)\s*\(|\bsubprocess\.|\.open\([^\n]*[\"'][wax]|\bopen\([^\n]*,[ ]*[\"'][wax]")
    hits = {name: [(i, l.strip()) for i, l in enumerate((ARGS.adopt_dir / name).read_text().splitlines(), 1)
                   if pattern.search(l)] for name in ("adopt_render.py", "adopt_data.py", "adopt_migrate.py")}
    planted = ["path.write_text('control')", "os.replace(a, b)", "open(path, 'w')"]
    check(not any(hits.values()) and all(pattern.search(p) for p in planted),
          "N1-last pure renderer, contract and migration sources hold no write pattern; 3/3 planted controls hit")


# --------------------------------------------------------------------- hook-dependent cases

def hook_vault(name):
    ctx = seeded(name)
    state = ctx.vault.parent / "stamp-state"
    return ctx, state


def case_i1(root):
    base = seeded("i1-seed", "2026-03-10T10:00:00Z", LONDON)
    vault = base.vault.parent / "cycle"
    vault.mkdir()
    ctx = D.Context(vault, base.home, base.locks)
    state = vault.parent / "stamp-state"
    settings = base.home / ".claude/settings.json"
    settings_before = settings.read_bytes()
    T.write(ctx.page, SOURCE)
    T.write(vault / "wiki/concepts/plain.md", b"---\ntitle: Plain\ntype: concept\nupdated: 2026-03-01\n---\n\nPlain.\n")
    arm_hook(vault, state)
    with clock("2026-03-10T10:00:00Z", LONDON):
        W.commit(ctx, W.proposal(ctx, "migrate", {"source_sha256": sha(SOURCE), "mapping": source_mapping(SOURCE)}))
    installed = page_bytes(ctx)
    _, line = run_hook(vault, state, "2026-03-11")
    check(page_bytes(ctx) == installed and " generated 1," in line, "I1 install then Stop: the generated page is byte-exact; generated logged")
    D.load_current(ctx)
    edit_prose(ctx, "Typed body edit after Stop.", "2026-03-11T10:00:00Z")
    check(field(page_bytes(ctx), "updated") == "2026-03-11", "I1 the next adopt operation succeeds and dates its body change")
    edited = page_bytes(ctx)
    run_hook(vault, state, "2026-03-12")
    check(page_bytes(ctx) == edited, "I1 a later-day Stop leaves the edited page exact")
    with clock("2026-03-12T10:00:00Z", LONDON):
        W.commit(ctx, W.proposal(ctx, "edit", {}))
    check(D.load_current(ctx)[0]["revision"] >= 2 and settings.read_bytes() == settings_before,
          "I1 the next load and proposal succeed; the copied settings stay byte-exact")


def case_d5_stop(root):
    ctx, state = hook_vault("d5stop")
    arm_hook(ctx.vault, state)
    edit_page(ctx, "2026-03-12T10:00:00Z", audited="2026-03-12")
    audited = page_bytes(ctx)
    run_hook(ctx.vault, state, "2026-03-13")
    check(page_bytes(ctx) == audited and D.load_current(ctx)[0]["page"]["metadata"]["audited"] == "2026-03-12",
          "D5 the later-day Stop after a typed audit edit leaves the page exact and loadable")


def case_i3(root):
    for number, stage in enumerate(STAGES):
        ctx, state = hook_vault("i3-" + str(number))
        arm_hook(ctx.vault, state)
        old = page_bytes(ctx)
        class Interrupted(Exception):
            pass
        def stop(point):
            if point == stage:
                raise Interrupted(point)
        with clock("2026-03-11T10:00:00Z", LONDON):
            doc = current(ctx)
            blocks = [{"id": "crash", "section": "Notes", "kind": "paragraph",
                       "content": [{"type": "text", "text": "Body change under a crash."}], "provenance": []}]
            request = W.proposal(ctx, "edit-prose", {"page": {"prose_blocks": blocks}})
            new_page = render(W.transformed(ctx, doc, request))
            try:
                W.commit(ctx, request, hook=stop)
                raise AssertionError("failure injection not reached at " + stage)
            except Interrupted:
                pass
        pending = page_bytes(ctx)
        run_hook(ctx.vault, state, "2026-03-12")
        check(page_bytes(ctx) == pending and pending in (old, new_page), "I3 Stop while pending at " + stage + " leaves the page exact")
        if ctx.pending.exists():
            with clock("2026-03-14T10:00:00Z", TOKYO):
                outcome = W.recover(ctx)
            chosen = page_bytes(ctx)
            check(chosen == (new_page if outcome == "new" else old) and
                  field(chosen, "updated") == ("2026-03-11" if outcome == "new" else "2026-03-10"),
                  "I3 later-day recovery at " + stage + " chooses an exact tuple and keeps its recorded date")
        run_hook(ctx.vault, state, "2026-03-15")
        D.load_current(ctx)
        check(page_bytes(ctx) in (old, new_page), "I3 Stop after recovery at " + stage + " leaves a loadable exact page")


def case_n1_rename(root):
    """Delta N1: Obsidian rewrites a renamed Related target inside the generated page."""
    ctx, doc = migrated("n1")
    vault = ctx.vault
    state = vault.parent / "stamp-state"
    (vault / "raw").mkdir(exist_ok=True)
    T.write(vault / "wiki/index.md", b"---\ntitle: Index\ntype: index\n---\n\n# Index\n")
    check("related-design" in targets(section(page_bytes(ctx), "Related")), "N1-rename arm: the Related section links the page to be renamed")
    for target in targets(section(page_bytes(ctx), "Related")):
        T.write(vault / "wiki/concepts" / (target + ".md"), b"---\ntitle: t\ntype: concept\n---\n\nTarget.\n")
    arm_hook(vault, state)
    old_link, new_link = (OPEN + "related-design" + CLOSE).encode(), (OPEN + "design-renamed" + CLOSE).encode()
    (vault / "wiki/concepts/related-design.md").rename(vault / "wiki/concepts/design-renamed.md")
    rewritten = page_bytes(ctx).replace(old_link, new_link)
    ctx.page.write_bytes(rewritten)
    _, line = run_hook(vault, state, "2026-03-11")
    check(field(page_bytes(ctx), "updated") == "2026-03-11" and " generated 0," in line,
          "N1-rename the rewritten page's digest no longer matches: the hook stamps it")
    refuses(lambda: D.load_current(ctx), "N1-rename load refuses the rewritten page", codes=(1,), text="PAGE DRIFT")
    with clock("2026-03-12T10:00:00Z", LONDON):
        parent = current_parent(ctx)
        changes = {k: copy.deepcopy(parent[k]) for k in ("rows", "page")}
        for row in changes["rows"]:
            for note in row["notes"]:
                for link in note["links"]:
                    if link.get("path") == "related-design":
                        link.update(path="design-renamed", label="design-renamed")
        for block in changes["page"]["prose_blocks"]:
            for item in block["content"]:
                if item["type"] == "link" and item["target"] == "related-design":
                    item.update(target="design-renamed", label="design-renamed")
        W.commit(ctx, W.proposal(ctx, "reconcile-page", {"typed_changes": changes}, observed(ctx)))
    after = page_bytes(ctx)
    D.load_current(ctx)
    check("design-renamed" in targets(section(after, "Related")) and "related-design" not in targets(section(after, "Related"))
          and field(after, "updated") == "2026-03-12", "N1-rename the typed reconcile restores equality with the renamed target, dated")
    checker = need("link-check", ARGS.link_check)
    clean = subprocess.run([sys.executable, "-B", str(checker), "--vault", str(vault)], capture_output=True, text=True)
    check(clean.returncode == 0 and "DEAD LINKS: 0" in clean.stdout, "N1-rename the link reader is clean afterwards")
    T.write(vault / "wiki/concepts/planted.md", b"---\ntitle: p\ntype: concept\n---\n\n" + OPEN.encode() + b"related-design" + CLOSE.encode() + b"\n")
    planted = subprocess.run([sys.executable, "-B", str(checker), "--vault", str(vault)], capture_output=True, text=True)
    check(planted.returncode == 1 and "related-design" in planted.stdout, "N1-rename control: the old name is a dead link on the same reader")


def case_n1_route(root):
    """N1 (delta review), text half: the adopt skill states the rename route in section 2.4 terms."""
    text = (ARGS.adopt_dir / "SKILL.md").read_text(encoding="utf-8")
    route = "A rename of a page the register links is followed in the same pass by a typed adopt edit"
    repair = "repair it with `reconcile-page` and `typed_changes` making the same rename, never by hand"
    check(text.count(route) == 1 and text.count(repair) == 1,
          "N1-route the adopt skill states the rename route once: a typed edit, or reconcile-page with typed_changes")


def case_f7_demo_instance(root):
    """F7 (closed check): the demonstration instance is regenerated through the writer, and the
    historical tuple it came from is kept as an explicit compatibility fixture, every object kept."""
    compat_path = need("instance-data", ARGS.instance_data)
    demo_path = need("demo-instance", ARGS.demo_instance)
    compat_state, demo_state = compat_path.parent / "register-state", demo_path.parent / "register-state"
    compat_raw = compat_path.read_bytes()
    compat = json.loads(compat_raw)
    compat_page = (compat_path.parent.parent.parent / REG).read_bytes()
    compat_receipt_raw = (compat_state / "receipt.json").read_bytes()
    compat_receipt = json.loads(compat_receipt_raw)
    check(compat["schema_version"] == 2 and compat["page"]["layout_version"] == 1 and render(compat) == compat_page and
          compat_receipt["data_sha256"] == sha(compat_raw) and compat_receipt["page_sha256"] == sha(compat_page),
          "F7 the compatibility fixture is a self-consistent historical v2/layout-1 tuple")
    home = root / "home"
    (home / ".claude/skills").mkdir(parents=True)
    ctx = D.Context(demo_path.parent.parent.parent, home, root / "locks")
    demo, demo_raw = D.load_current(ctx)
    page = ctx.page.read_bytes()
    head, rest = split(page)
    check(demo["page"]["layout_version"] == 2 and
          [l for l in head.split(b"\n") if l.startswith(b"register-body-sha256")] == [b'register-body-sha256: "' + sha(rest).encode() + b'"'],
          "F7 the demonstration instance loads through the writer at layout 2, its body digest exact")
    check(demo["revision"] == compat["revision"] + 1 and demo["commit"].get("parent_data_sha256") == sha(compat_raw) and
          demo["register_id"] == compat["register_id"],
          "F7 it is one writer commit on the historical tuple: next revision, parent data hash, same register identity")
    same_meta = {k: v for k, v in demo["page"]["metadata"].items() if k != "updated"} == \
        {k: v for k, v in compat["page"]["metadata"].items() if k != "updated"}
    check(demo["rows"] == compat["rows"] and demo["migration"] == compat["migration"] and
          demo["page"]["prose_blocks"] == compat["page"]["prose_blocks"] and same_meta,
          "F7 rows, migration provenance, prose and every metadata value but the writer-owned date are preserved")
    old = {p.name: p.read_bytes() for p in (compat_state / "objects").iterdir()}
    kept = [n for n, raw in old.items() if (demo_state / "objects" / n).is_file() and (demo_state / "objects" / n).read_bytes() == raw]
    check(old and len(kept) == len(old) and {sha(compat_raw), sha(compat_page), sha(compat_receipt_raw)} <= set(kept),
          "F7 all %d historical objects are preserved byte for byte, the parent tuple among them" % len(old))
    source = (demo_state / "objects" / demo["migration"]["source_archive"]).read_bytes()
    census = targets(body(source).decode().split("\n"))
    produced = targets(section(page, "Related"))
    check(census and census <= produced, "F7 its Related section carries all %d source targets" % len(census))


# Evidence kind of each case (closed check F9). "original-base" cases fail on the build before
# this feature; "preservation" cases pass there too; "+ mutant" names the delta's discriminator.
KINDS = {"D1": "original-base", "D1-freshness": "original-base", "D1-preserve": "original-base",
         "D3": "original-base", "D4": "original-base", "D4-N2-activation": "original-base + mutant N2",
         "D5": "original-base", "D6": "original-base", "D7": "original-base", "D8": "original-base",
         "D8-N5-absorb": "original-base + mutant N5", "R1": "original-base + mutant N8", "R2": "original-base",
         "I2": "original-base", "I4": "preservation", "F7-demo-instance": "original-base", "N1-route": "original-base",
         "I1": "original-base", "D5-stop": "original-base", "I3": "original-base",
         "N1-rename": "original-base (fails at its arm: no Related section to rewrite)", "N1-last": "preservation"}
CASES = [("D1", case_d1, "pure"), ("D1-freshness", case_d1_freshness, "pure"), ("D1-preserve", case_d1_preserve, "pure"),
         ("D3", case_d3, "pure"), ("D4", case_d4, "pure"), ("D4-N2-activation", case_d4_activation, "pure"),
         ("D5", case_d5, "pure"), ("D6", case_d6, "pure"), ("D7", case_d7, "pure"), ("D8", case_d8, "pure"),
         ("D8-N5-absorb", case_d8_absorb, "pure"), ("R1", case_r1, "pure"), ("R2", case_r2, "pure"), ("I2", case_i2, "pure"),
         ("I4", case_i4, "pure"), ("F7-demo-instance", case_f7_demo_instance, "pure"), ("N1-route", case_n1_route, "pure"),
         ("I1", case_i1, "hook"), ("D5-stop", case_d5_stop, "hook"), ("I3", case_i3, "hook"),
         ("N1-rename", case_n1_rename, "hook"), ("N1-last", case_no_write, "pure")]


def main():
    global ARGS, D, W, R, G, T, render
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adopt-dir", type=Path, required=True)
    for name in ("stamp-hook", "audit-pools", "required-sections", "link-check", "lint-adapter",
                 "instance-data", "demo-instance", "deep-lint-skill", "lint-skill"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--group", choices=("all", "pure", "hook"), default="all")
    parser.add_argument("--case", choices=[c[0] for c in CASES])
    try:
        ARGS = parser.parse_args()
    except SystemExit as exc:
        print("PROBE FAILED: arguments")
        return 2
    if not os.environ.get("TMPDIR") or not Path(os.environ["TMPDIR"]).is_dir():
        print("PROBE FAILED: explicit existing TMPDIR required")
        return 2
    try:
        ARGS.adopt_dir = ARGS.adopt_dir.resolve(strict=True)
    except OSError as exc:
        print("PROBE FAILED: adopt directory: " + str(exc))
        return 2
    skills = ARGS.adopt_dir.parent
    defaults = {"audit_pools": skills / "deep-lint/audit-pools.py", "required_sections": skills / "lint/check-required-sections.py",
                "link_check": skills / "lint/check-links.py", "lint_adapter": skills / "lint/check_register.py",
                "instance_data": skills / "fixtures/instance-layout1/.claude/adopt/capability-register.json",
                "demo_instance": skills / "instance/.claude/adopt/capability-register.json",
                "deep_lint_skill": skills / "deep-lint/SKILL.md", "lint_skill": skills / "lint/SKILL.md"}
    for key, value in defaults.items():
        if getattr(ARGS, key) is None:
            setattr(ARGS, key, value)
    if ARGS.stamp_hook is not None and not ARGS.stamp_hook.is_file():
        print("PROBE FAILED: --stamp-hook names no file: " + str(ARGS.stamp_hook))
        return 2
    sys.path.insert(0, str(ARGS.adopt_dir))
    sys.dont_write_bytecode = True
    import adopt_data, adopt_register, adopt_resources, adopt_migrate, adopt_render, test_register
    D, W, R, G, T, render = adopt_data, adopt_register, adopt_resources, adopt_migrate, test_register, adopt_render.render
    if not (D.control() == 3):
        print("PROBE FAILED: decoder control")
        return 2
    root = Path(tempfile.mkdtemp(prefix="generated-dates.", dir=os.environ["TMPDIR"])).resolve(strict=True)
    T.ROOT = root
    failed = total = 0
    try:
        for name, function, group in CASES:
            if ARGS.case and name != ARGS.case:
                continue
            if ARGS.group != "all" and group != ARGS.group:
                continue
            if group == "hook" and ARGS.stamp_hook is None:
                print("NOT APPLICABLE: hook absent: " + name + " (the vault's hook suite runs it)", flush=True)
                continue
            total += 1
            print("CASE " + name + " (kind: " + KINDS[name] + ")", flush=True)
            case_root = root / ("case-" + name)
            case_root.mkdir()
            try:
                function(case_root)
                print("PASS " + name, flush=True)
            except Unrun as exc:
                failed += 1
                print("UNRUN REQUIRED " + name + ": " + str(exc), flush=True)
            except (AssertionError, D.Problem) as exc:
                failed += 1
                print("FAIL " + name + ": " + type(exc).__name__ + ": " + str(exc), flush=True)
            except Exception as exc:
                failed += 1
                print("FAIL " + name + ": unexpected " + type(exc).__name__ + ": " + str(exc), flush=True)
                traceback.print_exc(file=sys.stdout)
    finally:
        for path in sorted(root.rglob("*"), key=lambda p: len(p.parts)):
            try:
                if not path.is_symlink():
                    path.chmod(0o700 if path.is_dir() else 0o600)
            except OSError:
                pass
        shutil.rmtree(root)
    print("COUNTS " + json.dumps({"assertions": COUNT, "cases": total, "failed": failed}))
    if total == 0:
        print("PROBE FAILED: no case selected")
        return 2
    print(f"FAIL {failed}/{total}" if failed else f"PASS {total}/{total}")
    return 1 if failed else 0


if __name__ == "__main__":
    import multiprocessing as mp
    mp.set_start_method("spawn")
    sys.exit(main())
