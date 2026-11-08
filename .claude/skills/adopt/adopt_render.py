#!/usr/bin/env python3
"""Pure whole-page renderer. No Markdown input, clock read or filesystem write.

Layout 1 keeps commit bookkeeping in the body and is reproduced byte for byte.
Layout 2 constructs the body once, declares its exact SHA-256 in the frontmatter
beside the revision, commit time and data digest, and adds real Sources Used and
Related sections built only from typed links already held in the data.
"""
import json
import re
from urllib.parse import quote
from adopt_data import Problem, sha, encoded, validate, timestamp

# The page layout the writer emits; layout 1 stays readable for existing tuples.
CURRENT_LAYOUT = 2
BODY_DIGEST_FIELD = "register-body-sha256"
OWNED_FIELDS = (BODY_DIGEST_FIELD, "register-committed", "register-data-sha256", "register-revision")
# The framework's standard navigation page, linked only when no local target is recorded.
NAVIGATION_TARGET = "index"
SOURCES_SECTION = "Sources Used"
# The body starts after the closing delimiter line of the initial frontmatter, the same
# boundary the Stop hook's split uses; the delimiter's own LF or CRLF belongs to the header.
FRONTMATTER = re.compile(rb"\A---\r?\n(.*?\r?\n)---\r?\n", re.S)


def escape(text):
    # Numeric entities also prevent headings, HTML, code fences and markers.
    return "".join(c if c.isalnum() or c in " ,.;:!?/()-" else
                   "&#" + str(ord(c)) + ";" for c in str(text)).replace("\n", "&#10;")


def token(item):
    if item["type"] in ("text", "code"):
        return escape(item["text"])
    target = item["target"]
    return "[" + escape(item["label"]) + "](" + quote(target, safe="/:#%?=&") + ")"


def wikilink(target, label):
    """One local wiki link. Delimiters are assembled from character values; the target keeps its
    spelling, case, Unicode, spaces, paths and fragments, and a structural character refuses."""
    unsafe = [c for c in target if c in "[]|" or ord(c) < 32 or 127 <= ord(c) < 160 or c in "\u2028\u2029"]
    if unsafe or not target.strip() or target.startswith("https://"):
        raise Problem("unsafe local link target " + json.dumps(target, ensure_ascii=True) +
                      ": brackets, a pipe, a line or control break, an empty target and a web address "
                      "cannot form a wiki link")
    opening, closing = chr(91) * 2, chr(93) * 2
    if label == target:
        return opening + target + closing
    return opening + target + "|" + escape(label) + closing


def split_page(raw):
    """(header, body) at the hook's boundary, or (None, raw) without a closed initial frontmatter."""
    match = FRONTMATTER.match(raw)
    if not match:
        return None, raw
    return raw[:match.end()], raw[match.end():]


def assurance_labels(data, row):
    if row["lifecycle"]["state"] == "legacy-recorded":
        return ["unproven; model evidence unresolved; legacy recorded, not re-proved"]
    if row["freshness"]["status"] == "not-applicable":
        return ["not applicable"]
    labels = []
    for skill in row["freshness"]["skills"]:
        if not skill["comparisons"]:
            labels.append(skill["resource_id"] + ": unproven; model evidence unresolved")
        for c in skill["comparisons"]:
            route = c["proof_route"]
            if c["tier"] == "claimed":
                route = "comparison pending" if route != "how-to" else "checked runs pending"
            elif c["tier"] == "proven" and route == "how-to":
                runs = []
                for e in c["events"]:
                    if e["action"] == "drop":
                        runs = []
                    elif e["action"] == "checked-runs":
                        runs.extend(e["evidence_refs"])
                route = f"checked runs {len(runs)}/{data['policy']['how_to_successes_required']} (recorded evidence IDs)"
            labels.append(f"{skill['resource_id']}: {c['tier']} · {c['model_id']} · {route}")
    return labels


def assurance_details(data, row):
    result = assurance_labels(data, row)
    evidence = {e["id"]: e for e in data["evidence"]}
    for skill in row["freshness"].get("skills", []):
        candidate = skill["candidate"]
        for c in skill["comparisons"]:
            candidate_date = candidate["version_date"] if isinstance(candidate["version_date"], str) else json.dumps(candidate["version_date"], sort_keys=True)
            result.append(f"{skill['resource_id']} / {c['model_id']}: candidate date {candidate_date}; "
                          f"model release {c['model_release_date']}; author statement refs {', '.join(c['claim_evidence_refs']) or 'none'}")
            for event in c["events"]:
                detail = f"{event['action']}: {event['from_tier']} → {event['to_tier']}; {event['reason']}"
                if event["action"] == "comparison":
                    p = event["comparison"]
                    with_result = evidence[p['with_skill_evidence_ref']]['result']
                    without_result = evidence[p['without_skill_evidence_ref']]['result']
                    judgement = evidence[p['judgement_evidence_ref']]
                    detail += (f"; frozen task {p['task_evidence_ref']} ({p['task_sha256']}); "
                               f"with skill {p['with_skill_evidence_ref']} ({with_result}); "
                               f"without skill {p['without_skill_evidence_ref']} ({without_result}); "
                               f"judgement {p['judgement_evidence_ref']} ({judgement['result']}): {p['verdict']}")
                else:
                    detail += "; evidence " + ", ".join(event["evidence_refs"])
                result.append(detail)
    for evaluation in row["lifecycle"].get("activation", {}).get("freshness_evaluation", []):
        if evaluation["freshness_decision_refs"]:
            result.append("Unproven owner exception: " + ", ".join(evaluation["freshness_decision_refs"]) +
                          "; " + evaluation["model_id"] + "; " + evaluation["route"])
    return result


def shared_lines(data):
    """Categories, rows, installation pins, authored material and migration provenance."""
    lines = []
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
            fresh = "; ".join(assurance_labels(data, row))
            proof = "no current activation"
            if "activation" in row["lifecycle"]:
                proof = "last verified " + row["lifecycle"]["activation"]["verified_at"]
            if "maintenance_id" in row:
                proof += "; MAINTENANCE " + row["maintenance_id"]
            lines.append("| " + " | ".join(escape(v) for v in
                         (row["id"] + " / " + row["name"], level, route, state, fresh, proof)) + " |")
        for row in rows:
            lines += ["", "### " + escape(row["id"]), "", escape(row["name"])]
            for detail in assurance_details(data, row):
                lines += ["", escape(detail)]
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
    return lines


def render_layout1(data):
    meta = data["page"]["metadata"]
    lines = ["---"]
    for key, value in sorted(meta.items()):
        lines.append(key + ": " + json.dumps(value, ensure_ascii=False))
    lines += ["---", "", "Generated capability register",
              "", "Authority: `.claude/adopt/capability-register.json`. Edit through `/adopt --edit` or `/adopt --edit-prose`.",
              "", f"Revision {data['revision']} · committed {data['commit']['at']}",
              "", f"<!-- register-data {sha(encoded(data))} renderer 1 layout {data['page']['layout_version']} -->"]
    lines += shared_lines(data)
    return ("\n".join(lines) + "\n").encode("utf-8")


def related_links(data):
    """Distinct recorded local targets in target order, each with the first label met in data order:
    linked note links on every row, linked record links on managed rows, and local link tokens in
    typed prose. Unresolved entries and web addresses are never wiki targets."""
    found = {}
    for row in data["rows"]:
        for note in row["notes"]:
            for link in note["links"]:
                if link["status"] == "linked":
                    found.setdefault(link["path"], link["label"])
        if row["lifecycle"]["state"] != "legacy-recorded":
            for link in row["record_links"]:
                if link["status"] == "linked":
                    found.setdefault(link["path"], link["label"])
    for block in data["page"]["prose_blocks"]:
        for item in block["content"]:
            if item["type"] == "link" and not item["target"].startswith("https://"):
                found.setdefault(item["target"], item["label"])
    return sorted(found.items())


def source_links(data):
    """Link tokens recorded under the source section of typed prose, in data order, deduplicated."""
    found = {}
    for block in data["page"]["prose_blocks"]:
        if block["section"].strip() != SOURCES_SECTION:
            continue
        for item in block["content"]:
            if item["type"] == "link":
                found.setdefault(item["target"], item)
    return list(found.values())


def body_instants(data):
    """RFC 3339 instants the layout-2 body prints: activation times and recorded freshness times."""
    found = set()
    def walk(value):
        if isinstance(value, dict):
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, str) and re.fullmatch(
                r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)", value):
            found.add(value)
    for row in data["rows"]:
        if "activation" in row["lifecycle"]:
            found.add(row["lifecycle"]["activation"]["verified_at"])
        if row["lifecycle"]["state"] != "legacy-recorded":
            walk(row["freshness"])
    return found


def layout2_body(data):
    """The exact layout-2 body bytes for already validated data."""
    lines = ["", "Generated capability register",
             "", "Authority: `.claude/adopt/capability-register.json`. Edit through `/adopt --edit` or `/adopt --edit-prose`."]
    lines += shared_lines(data)
    lines += ["", "## " + SOURCES_SECTION, ""]
    sources = source_links(data)
    if sources:
        lines += ["- " + (token(item) if item["target"].startswith("https://") else
                          wikilink(item["target"], item["label"])) for item in sources]
    else:
        lines.append("No source page is recorded in the structured data; the structured register "
                     "`.claude/adopt/capability-register.json` is the authority for this page.")
    lines += ["", "## Related", ""]
    related = related_links(data)
    if related:
        lines += ["- " + wikilink(target, label) for target, label in related]
    else:
        lines.append("- " + wikilink(NAVIGATION_TARGET, "Wiki index") +
                     " (navigation only: no add-on record or source page is recorded yet)")
    return ("\n".join(lines) + "\n").encode("utf-8")


def body_bytes(document):
    """The exact body of the page the document renders to, from the same construction."""
    if document.get("schema_version") == 1:
        from adopt_compat_v1 import render as render_v1
        return split_page(render_v1(document))[1]
    validate(document)
    if document["page"]["layout_version"] == 1:
        return split_page(render_layout1(document))[1]
    return layout2_body(document)


def render(data):
    validate(data)
    if data["page"]["layout_version"] == 1:
        return render_layout1(data)
    body = layout2_body(data)
    meta = dict(data["page"]["metadata"])
    if set(meta) & set(OWNED_FIELDS):
        raise Problem("renderer-owned field in editable page metadata")
    timestamp(data["commit"]["at"])
    meta.update({BODY_DIGEST_FIELD: sha(body), "register-revision": data["revision"],
                 "register-committed": data["commit"]["at"], "register-data-sha256": sha(encoded(data))})
    lines = ["---"] + [key + ": " + json.dumps(value, ensure_ascii=False)
                       for key, value in sorted(meta.items())] + ["---"]
    return ("\n".join(lines) + "\n").encode("utf-8") + body
