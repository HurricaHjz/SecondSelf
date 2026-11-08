#!/usr/bin/env python3
"""One-time, read-only migration compiler. Ongoing readers never import Markdown.

A reviewed mapping names every source capability row and every grouped member.
The source archive remains byte-exact. Migration verifies both directions by
reconstructing the deterministic destination from that mapping and source.
"""
import argparse
import copy
import json
import re
import sys
from adopt_data import (Problem, require, sha, digest, encoded, read_json, validate,
                        PROVENANCE, NORMAL, cli_error)


def validate_v1(document):
    from adopt_compat_v1 import validate as frozen_validate
    return frozen_validate(document)


def upgrade_freshness(document, at):
    """Pure typed upgrade; the sole writer publishes the reviewed result."""
    if document.get("schema_version") == 2:
        validate(document)
        return copy.deepcopy(document)
    validate_v1(document)
    from adopt_data import timestamp
    timestamp(at)
    new = copy.deepcopy(document)
    new["schema_version"] = 2
    # Two checked runs: set by judgement, unmeasured; never a usage counter.
    new["policy"].update(freshness_rule_version=2, how_to_successes_required=2, owner_identity=None)
    for row in new["rows"]:
        if row["lifecycle"]["state"] == "legacy-recorded":
            continue
        if row["lifecycle"]["state"] == "active":
            row["lifecycle"] = {"state": "prepared", "changed_at": at,
                "reason": "Freshness schema upgrade invalidates the archived activation.", "decision_refs": []}
        if row["freshness"]["status"] == "applicable":
            for skill in row["freshness"]["skills"]:
                for c in skill["comparisons"]:
                    c.update(rule_version=2, result="unknown", tier="unproven", proof_route="undetermined",
                             claim_evidence_refs=[], events=[])
    validate(new)
    return new


def source_lines(raw):
    text = raw.decode("utf-8-sig")
    require(not raw.startswith(b"\xef\xbb\xbf"), "migration source BOM needs an explicit mapping extension")
    offset, lines = 0, []
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        length = len(line.encode())
        lines.append({"line": number, "text": line, "start_byte": offset, "end_byte": offset + length})
        offset += length
    require(offset == len(raw), "source span calculation failed")
    return lines


def cells(text):
    require(text.lstrip().startswith("|") and text.rstrip().endswith("|"), "unsupported table row")
    return [x.strip() for x in re.split(r"(?<!\\)\|", text.strip())[1:-1]]


def tokens(text):
    opening, closing = chr(91) * 2, chr(93) * 2
    pattern = re.escape(opening) + r"([^\n]+?)" + re.escape(closing)
    out, offset = [], 0
    for match in re.finditer(pattern, text):
        if match.start() > offset:
            out.append({"type": "text", "text": text[offset:match.start()]})
        target, sep, label = match.group(1).partition("|")
        if any(x in target for x in (":", "\\", "..")) or target.startswith("/"):
            out.append({"type": "text", "text": match.group(0)})
        else:
            out.append({"type": "link", "target": target, "label": label if sep else target})
        offset = match.end()
    if offset < len(text):
        out.append({"type": "text", "text": text[offset:]})
    return out


def metadata(lines):
    require(lines[0]["text"].strip() == "---", "source lacks frontmatter")
    end = next((i for i, line in enumerate(lines[1:], 1) if line["text"].strip() == "---"), None)
    require(end is not None, "source frontmatter not closed")
    result = {}
    for line in lines[1:end]:
        key, sep, value = line["text"].strip().partition(":")
        require(sep and key not in result, "unsupported/duplicate source frontmatter")
        value = value.strip()
        if value.startswith('"'):
            value = json.loads(value)
        elif value.startswith("[") and value.endswith("]"):
            value = [x.strip() for x in value[1:-1].split(",") if x.strip()]
        result[key] = value
    return result, end + 1


def migration_document(raw, mapping, at):
    from adopt_register import seed_document
    lines = source_lines(raw)
    header, header_end = metadata(lines)
    require(set(mapping) == {"source_sha256", "rows", "qualifications"} and
            mapping["source_sha256"] == sha(raw), "mapping source mismatch")
    require(all(set(x) == {"line", "kind", "members"} for x in mapping["rows"]), "mapping row shape")
    by_line = {x["line"]: x for x in mapping["rows"]}
    require(len(by_line) == len(mapping["rows"]), "duplicate mapped source row")
    doc = seed_document(at)
    # The preservation compiler retains its original v1 contract, including page layout 1.
    doc["schema_version"] = 1
    doc["page"]["layout_version"] = 1
    doc["policy"]["freshness_rule_version"] = 1
    doc["policy"].pop("how_to_successes_required", None)
    doc["policy"].pop("owner_identity", None)
    doc["page"]["metadata"] = header
    ledger, section = [], "Preamble"
    source_hash = sha(raw)
    def provenance(line, interpretation):
        return [{"source_sha256": source_hash, "source_locator": "line:" + str(line["line"]),
                 "start_byte": line["start_byte"], "end_byte": line["end_byte"],
                 "interpretation": interpretation}]
    for line in lines:
        number, text = line["line"], line["text"]
        destinations = []
        if number in by_line:
            specification = by_line[number]
            values = cells(text)
            require(specification["members"], "omitted source member")
            # Every first-cell byte is explicitly attributed to a reviewed member.
            intervals = []
            cursor = 0
            for member in specification["members"]:
                require(set(member) == {"id", "name", "source_text"}, "member mapping shape")
                source = member["source_text"]
                start = values[0].find(source, cursor)
                require(start >= 0 and member["name"] in source,
                        "member has no ordered source identity")
                cursor = start + len(source)
                intervals.append((start, start + len(source)))
                rid = member["id"]
                destinations.append(rid)
                unresolved = {"status": "unresolved", "source_span": "line:" + str(number),
                              "reason": "Historical prose is preserved below; managed facts need separate evidence."}
                row = {k: copy.deepcopy(unresolved) for k in NORMAL if k != "maintenance_id"}
                row.update(id=rid, name=member["name"], kind=specification["kind"],
                           lifecycle={"state": "legacy-recorded", "original_state_text": "",
                                      "source_span": "line:" + str(number) + "; state column absent"},
                           notes=[], provenance=provenance(line, "Transcribed member; kind is a proposed source-section classification."))
                for i, value in enumerate(values, 1):
                    links = [{"status": "linked", "path": t["target"], "label": t["label"]}
                             for t in tokens(value) if t["type"] == "link"]
                    row["notes"].append({"id": f"cell-{number}-{i}", "text": value,
                                         "links": links, "supersedes_note_ids": []})
                row["routes"] = {**unresolved, "reason": "Source has no Route column; no route inferred."}
                doc["rows"].append(row)
            intervals.sort()
            require(all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:])),
                    "overlapping member mappings")
            remainder = values[0]
            for start, end in reversed(intervals):
                remainder = remainder[:start] + remainder[end:]
            require(not remainder.strip(" ·"), "unmapped grouped member or qualification: " + remainder)
            kind = "capability-row"
        elif number <= header_end:
            kind = "frontmatter"
        elif not text.strip():
            kind = "formatting"
        else:
            if text.startswith("## "):
                section = text[3:].strip()
            bid = "source-line-" + str(number)
            doc["page"]["prose_blocks"].append({"id": bid, "section": section, "kind": "paragraph",
                "content": tokens(text.rstrip("\n")), "provenance": provenance(line, "Verbatim source material; presentation escaped.")})
            destinations.append(bid)
            kind = "prose"
        ledger.append({"start_byte": line["start_byte"], "end_byte": line["end_byte"],
                       "line": number, "kind": kind, "sha256": sha(text.encode()),
                       "destination_ids": destinations})
    require(set(by_line) <= {x["line"] for x in lines}, "mapped line missing")
    rows = {r["id"]: r for r in doc["rows"]}
    require(len(rows) == len(doc["rows"]), "duplicate destination member")
    for relation in mapping["qualifications"]:
        require(set(relation) == {"line", "row_id", "supersedes_note_ids"}, "qualification mapping shape")
        require(relation["row_id"] in rows, "qualification names omitted row")
        row = rows[relation["row_id"]]
        source = lines[relation["line"] - 1]
        require(set(relation["supersedes_note_ids"]) <= {n["id"] for n in row["notes"]},
                "qualification names missing prior note")
        row["notes"].append({"id": "qualification-" + str(relation["line"]),
                            "text": source["text"].rstrip("\n"), "links": [],
                            "supersedes_note_ids": relation["supersedes_note_ids"]})
    # The mapping is reviewed; automatic table recognition supplies an independent omission control.
    candidate_rows, in_capabilities = [], False
    for line in lines:
        text = line["text"]
        if text.startswith("## "):
            in_capabilities = any(text.startswith("## " + prefix) for prefix in (
                "User-level skills", "Plugins", "Command-line tools", "Connectors",
                "The vault's own skills", "Tool servers"))
        if text.startswith("|") and in_capabilities:
            parts = cells(text)
            if parts and not all(re.fullmatch(r":?-+:?", x) for x in parts) and parts[0] not in (
                    "Name", "Plugin", "Tool", "Connector", "Skill", "Server"):
                candidate_rows.append(line["line"])
    require(set(candidate_rows) == set(by_line), "source capability-row coverage differs")
    doc["migration"] = {"source_sha256": source_hash, "source_archive": source_hash,
                        "coverage": ledger,
                        "legacy_rows": [{"id": r["id"], "initial_sha256": digest(r)} for r in doc["rows"]],
                        "unresolved": ["Imported operational facts, exact pins, resource paths, routes, state and model evidence remain unresolved; original use rulings are preserved.",
                                       "Category and member identities follow the reviewed migration mapping; no installation or activation is inferred."]}
    doc["commit"]["operation"] = "migrate"
    validate_v1(doc)
    return doc


def current_layout(rebuilt, at):
    """The one named writer transform from the v2 preservation document to the published layout:
    layout 2, dated with the calendar day of the commit timestamp's captured local offset."""
    from adopt_data import calendar_day
    result = copy.deepcopy(rebuilt)
    result["page"]["layout_version"] = 2
    result["page"]["metadata"]["updated"] = calendar_day(at)
    return result


def verify_coverage(raw, document, mapping):
    rebuilt = migration_document(raw, mapping, document["commit"]["at"])
    if document["schema_version"] == 2:
        validate(document)
        rebuilt = upgrade_freshness(rebuilt, at=document["commit"]["at"])
        # The reviewed writer increments revision; the preservation transform does not.
        rebuilt["revision"] = document["revision"]
        if document["page"]["layout_version"] == 2:
            rebuilt = current_layout(rebuilt, document["commit"]["at"])
    # Only writer identities and commit metadata are generated independently.
    left = {k: v for k, v in document.items() if k not in ("register_id", "commit")}
    right = {k: v for k, v in rebuilt.items() if k not in ("register_id", "commit")}
    require(left == right, "forward/reverse migration coverage differs")
    ledger = document["migration"]["coverage"]
    require(ledger and ledger[0]["start_byte"] == 0 and ledger[-1]["end_byte"] == len(raw)
            and all(a["end_byte"] == b["start_byte"] for a, b in zip(ledger, ledger[1:])),
            "migration has gaps or overlapping source spans")
    return {"source_bytes": len(raw), "covered_bytes": sum(x["end_byte"] - x["start_byte"] for x in ledger),
            "source_rows": len(mapping["rows"]), "destination_rows": len(document["rows"]),
            "source_cells": sum(len(cells(source_lines(raw)[r["line"] - 1]["text"])) for r in mapping["rows"]),
            "prose_blocks": len(document["page"]["prose_blocks"]), "uncovered_bytes": 0,
            "unexplained_facts": 0, "source_archive_sha256": sha(raw),
            "control_hits": len(mapping["rows"])}


def main():
    from adopt_data import ProbeParser
    parser = ProbeParser(description=__doc__)
    for key in ("source", "mapping", "data"):
        parser.add_argument("--" + key, required=True)
    args = parser.parse_args()
    try:
        from pathlib import Path
        result = verify_coverage(Path(args.source).read_bytes(), read_json(args.data), read_json(args.mapping))
        print(encoded(result).decode(), end="")
        return 0
    except (Problem, OSError, ValueError, TypeError, KeyError, IndexError, RuntimeError) as exc:
        return cli_error(exc)


if __name__ == "__main__":
    sys.exit(main())
