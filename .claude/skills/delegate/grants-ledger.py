#!/usr/bin/env python3
"""grants-ledger.py: what each helper's brief granted, one row per helper, read from the kept brief copies
a run record names; and a warning line for every brief whose GRANTS block is missing, in the old free
form, short of a field, or unreadable. Stdout only: it opens every file read-only and writes none.

usage:
  grants-ledger.py --run RUN [--run RUN ...]          the record <store>/spawn-records/RUN.jsonl
  grants-ledger.py --record FILE [--record FILE ...]   a record file by path
  grants-ledger.py --brief FILE [--brief FILE ...]     briefs by path, e.g. one about to be sent
The store is $LLM_WIKI_STORE, else ~/.llm-wiki, as lane.py reads it.

Rows. One per `lane-open` line of the record, read from its `brief_copy` (the copy lane.py keeps in the
lane's input folder). A resumed pass (`lane-resumed`) adds no row. Each row gives the five fields of the
block, each whole, and the block's other lines (read and write grants, DECISIONS, free text).
Helpers spawned in-session keep no brief copy and are not listed: the ledger covers the record's lanes only.

The block. A line that opens with GRANTS, outside fenced code, opens it; it runs to the first blank line
after its first non-blank line. A GRANTS inside a fence counts as absent. Where a brief holds several
blocks, the one with the most of the five fields is read. The five fields are list lines inside it:
  - Bounds: / - Pushed: / - Held by the reviewer: / - Left out on purpose: / - Second seat:
A field with no text after its colon, or still holding a template slot, counts as missing.

Warnings (one line each, never silence): "no GRANTS line"; "old form" (a block with none of the five
fields); "lacks <fields>"; "cannot read" (the copy, or a record line); "no brief copy recorded".

Every run first reads four planted briefs built into this file and checks the result (the positive
control for a run that prints no warning); a mismatch is a broken premise.

Exit: 0 every row has the five fields; 1 at least one warning; 2 PROBE FAILED (a missing or unreadable
record, a record with no lane-open line, a bad argument, the built-in control failing).
"""
import json
import os
import re
import sys

FIELDS = ("Bounds", "Pushed", "Held by the reviewer", "Left out on purpose", "Second seat")
OPEN_RX = re.compile(r"^(?:#{1,6}\s+)?(?:\*\*)?GRANTS\b")
FENCE_RX = re.compile(r"^ {0,3}(`{3,}|~{3,})")
FIELD_RX = re.compile(r"^\s*[-*]\s+(?:\*\*)?(%s)(?:\*\*)?\s*:(?:\*\*)?\s*(.*)$" % "|".join(re.escape(f) for f in FIELDS),
                      re.IGNORECASE)
RUN_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SLOT_RX = re.compile(r"\{\{|<<[A-Z_]+>>")


class ProbeFailed(Exception):
    pass


def blocks(text):
    """[(line_no, [lines])] for each GRANTS block outside fenced code, and the line numbers of any
    GRANTS line found inside a fence."""
    lines = text.split("\n")
    out, fenced = [], []
    fence = None
    i = 0
    while i < len(lines):
        line = lines[i]
        f = FENCE_RX.match(line)
        if f:
            mark = f.group(1)
            if fence is None:
                fence = mark[0]
            elif mark[0] == fence:
                fence = None
            i += 1
            continue
        if not OPEN_RX.match(line):
            i += 1
            continue
        if fence is not None:
            fenced.append(i + 1)
            i += 1
            continue
        start, body, j = i + 1, [], i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        while j < len(lines) and lines[j].strip() and not OPEN_RX.match(lines[j]) and not FENCE_RX.match(lines[j]):
            body.append(lines[j])
            j += 1
        out.append((start, body))
        i = j
    return out, fenced


def read_block(body):
    """({field: value}, [other lines]) for one block; a continuation line joins the field above it."""
    found, other, last = {}, [], None
    for line in body:
        m = FIELD_RX.match(line)
        if m:
            name = next(f for f in FIELDS if f.lower() == m.group(1).lower())
            found[name] = m.group(2).strip()
            last = name
        elif last is not None and line[:1] in (" ", "\t") and not re.match(r"^\s*[-*]\s", line):
            found[last] = (found[last] + " " + line.strip()).strip()
        else:
            other.append(line.strip())
            last = None
    return {k: v for k, v in found.items() if v}, other


def assess(text):
    """(status, fields, other, note) for one brief's text."""
    bs, fenced = blocks(text)
    if not bs:
        note = (" (a GRANTS inside a code fence, line %s, counts as absent)" % ", ".join(map(str, fenced))
                if fenced else "")
        return "no GRANTS", {}, [], note
    best = max(bs, key=lambda b: len(read_block(b[1])[0]))
    fields, other = read_block(best[1])
    if not fields:
        return "old form", {}, other, " (block at line %d holds none of the five fields)" % best[0]
    missing = [f for f in FIELDS if f not in fields or SLOT_RX.search(fields[f])]
    if missing:
        return "lacks", fields, other, " %s (block at line %d)" % (", ".join(missing), best[0])
    return "five fields", fields, other, ""


PLANTED = {
    "five": "\n".join(["TASK", "x", "", "GRANTS (planted)", "DECISIONS: none", "- Bounds: b", "- Pushed: p",
                       "- Held by the reviewer: none", "- Left out on purpose: l", "- Second seat: none",
                       "- Read: r. Write: w.", "", "REPORT"]),
    "old": "\n".join(["GRANTS", "Read: the vault. Write: none.", "", "REPORT"]),
    "fenced": "\n".join(["TASK", "```", "GRANTS", "- Bounds: b", "- Pushed: p", "- Held by the reviewer: h",
                         "- Left out on purpose: l", "- Second seat: s", "```", "REPORT"]),
    "none": "\n".join(["TASK", "No block here.", "Bounds are named in prose only."]),
    "short": "\n".join(["GRANTS", "- Bounds: b", "- Pushed: p", "- Second seat:", ""]),
}
PLANTED_WANT = {"five": "five fields", "old": "old form", "fenced": "no GRANTS", "none": "no GRANTS", "short": "lacks"}


def control():
    got = {k: assess(v)[0] for k, v in PLANTED.items()}
    if got != PLANTED_WANT or "Held by the reviewer, Left out on purpose, Second seat" not in assess(PLANTED["short"])[3]:
        raise ProbeFailed("the built-in planted briefs read %r, not %r: the block reader no longer reads the "
                          "shape it was written for" % (got, PLANTED_WANT))
    return ("control: the planted briefs read five fields, old form, no GRANTS (inside a fence), no GRANTS, "
            "and lacks three fields, as expected")


def store_root():
    given = os.environ.get("LLM_WIKI_STORE") or os.path.join(os.path.expanduser("~"), ".llm-wiki")
    return os.path.realpath(os.path.expanduser(given))


def read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read(), None
    except (OSError, UnicodeDecodeError) as err:
        return None, "%s: %s" % (err.__class__.__name__, getattr(err, "strerror", None) or err)


def rows_from_record(path, warnings):
    text, err = read_text(path)
    if text is None:
        raise ProbeFailed("cannot read the record %s (%s)" % (path, err))
    rows, n_lines = [], 0
    for n, line in enumerate(text.split("\n"), 1):
        if not line.strip():
            continue
        n_lines += 1
        try:
            ev = json.loads(line)
        except ValueError:
            warnings.append("WARNING: cannot read record line %d of %s: a lane-open on it would be missed" % (n, path))
            continue
        if isinstance(ev, dict) and ev.get("event") == "lane-open":
            rows.append({"lane": str(ev.get("lane") or "(no lane id, line %d)" % n),
                         "copy": ev.get("brief_copy") if isinstance(ev.get("brief_copy"), str) else None,
                         "record": path})
    if not rows:
        raise ProbeFailed("%s holds no lane-open line (%d lines read): no helper to list" % (path, n_lines))
    return rows, n_lines


def cell(t):
    return t.replace("|", "/").replace("\n", " ")


def main(argv):
    runs, records, briefs = [], [], []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            print(__doc__)
            return 0
        if a in ("--run", "--record", "--brief") and i + 1 < len(argv):
            {"--run": runs, "--record": records, "--brief": briefs}[a].append(argv[i + 1])
            i += 2
            continue
        print("PROBE FAILED: %s" % ("%s needs a value" % a if a in ("--run", "--record", "--brief")
                                    else "unknown argument %s" % a))
        print(__doc__.split("\n\n")[1])
        return 2
    if not (runs or records or briefs):
        print("PROBE FAILED: give --run, --record or --brief")
        print(__doc__.split("\n\n")[1])
        return 2
    print("## Grants ledger (grants-ledger.py)")
    warnings, rows = [], []
    try:
        print(control())
        for r in runs:
            if not RUN_RX.match(r):
                raise ProbeFailed("%r is not a run id" % r)
            records.append(os.path.join(store_root(), "spawn-records", "%s.jsonl" % r))
        n_lines = 0
        for rec in records:
            got, n = rows_from_record(rec, warnings)
            rows += got
            n_lines += n
        rows += [{"lane": "(brief)", "copy": b, "record": None} for b in briefs]
    except ProbeFailed as err:
        print("PROBE FAILED: %s" % err)
        return 2
    counts = {"five fields": 0, "lacks": 0, "old form": 0, "no GRANTS": 0, "cannot read": 0, "no copy": 0}
    print("\n| lane | status | %s | other lines in the block | brief copy |" % " | ".join(FIELDS))
    print("|---|---|%s---|---|" % ("---|" * len(FIELDS)))
    for row in rows:
        fields, other = {}, []
        if row["copy"] is None:
            status = "no copy"
            warnings.append("WARNING: no brief copy recorded: lane %s in %s" % (row["lane"], row["record"]))
        else:
            text, err = read_text(row["copy"])
            if text is None:
                status = "cannot read"
                warnings.append("WARNING: cannot read the brief copy of lane %s: %s (%s)" % (row["lane"], row["copy"], err))
            else:
                status, fields, other, note = assess(text)
                if status == "no GRANTS":
                    warnings.append("WARNING: no GRANTS line: lane %s, %s%s" % (row["lane"], row["copy"], note))
                elif status == "old form":
                    warnings.append("WARNING: old form, none of the five fields: lane %s, %s%s" % (
                        row["lane"], row["copy"], note))
                elif status == "lacks":
                    warnings.append("WARNING: GRANTS lacks%s: lane %s, %s" % (note, row["lane"], row["copy"]))
        counts[status] += 1
        print("| %s | %s | %s | %s | %s |" % (cell(row["lane"]), status,
                                              " | ".join(cell(fields.get(f, "")) for f in FIELDS),
                                              cell(" / ".join(other)), cell(row["copy"] or "")))
    if warnings:
        print("\n### Warnings")
        print("\n".join(warnings))
    if records:
        print("\nHelpers spawned in-session keep no brief copy and are not listed: this ledger covers the "
              "record's lanes only.")
    print("\nLEDGER SUMMARY records=%d record_lines=%d rows=%d five_fields=%d lacks=%d old_form=%d no_grants=%d "
          "cannot_read=%d no_copy=%d warnings=%d" % (len(records), n_lines, len(rows), counts["five fields"],
                                                     counts["lacks"], counts["old form"], counts["no GRANTS"],
                                                     counts["cannot read"], counts["no copy"], len(warnings)))
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
