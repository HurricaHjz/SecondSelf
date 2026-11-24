#!/usr/bin/env python3
"""test_old_state_listing.py: the suite of old_state_listing.py. Ends `PASS n/n` or `FAIL k/n`.

Usage: test_old_state_listing.py [--tmp-root DIR]   (about 2 seconds)
  Fixtures are built in a fresh folder under --tmp-root (default: the system's temporary folder)
  and removed at the end. The suite reads the script beside it and writes nowhere else.

Legs
  A  planted cases: each category counted once where it is planted, and not where a quotation,
     a code fence, the frontmatter, a narrative use or an open conflict holds the same words.
  B  a clean page gives no row, in a run whose controls and whose planted page both show.
  C  owner notes: linked from the page's own text, from another page, from inside the notes
     section only, and marked as withdrawn.
  D  the registries skipped; the three record pages skipped, and counted with --with-records;
     the date that "past" is judged against; count(), which the weekly pass imports.
  E  --show prints hit lines and no table.
  F  the live control: found, and not found.
  G  broken premises: each prints PROBE FAILED, exits 2 and prints no table.
  H  the script leaves the pages byte-identical: a checksum manifest before and after every run
     of the suite, with a control that changes one byte in the same folder, which the same
     comparison must catch.
  I  the source holds no call that writes, removes or renames a file, and no owner path or name;
     each search has its own positive control.
"""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "old_state_listing.py")
RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    sys.stdout.write("%s  %s%s\n" % ("ok  " if condition else "FAIL", name,
                                    "" if condition or not detail else "  [" + detail + "]"))


def run(*args):
    done = subprocess.run([sys.executable, "-B", SCRIPT] + list(args), capture_output=True,
                          text=True)
    return done.returncode, done.stdout, done.stderr


def table(stdout):
    lines = [line for line in stdout.split("\n") if line]
    if not lines:
        return [], {}
    header = lines[0].split("\t")
    rows = {}
    for line in lines[1:]:
        cells = line.split("\t")
        rows[cells[0]] = dict(zip(header, cells))
    return header, rows


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    return path


def manifest(root):
    sums = {}
    for folder, _dirs, files in os.walk(root):
        for name in sorted(files):
            path = os.path.join(folder, name)
            with open(path, "rb") as handle:
                sums[os.path.relpath(path, root)] = hashlib.sha256(handle.read()).hexdigest()
    return sums


FRONT = "---\ntitle: %s\ntype: %s\nupdated: 2026-01-02\n%s---\n"

PLANTED = FRONT % ("planted", "development", "flagged: 2026-01-01 a dated allowance. Clears on 2026-01-05.\n") + """# Planted

**Status 2026-01-03:** the newer layer.
2026-01-04 (a session): what changed that day.
The rule was superseded on 4 January 2026 by a newer one.
- **Settled 2026-01-04: which name.** Both statements are kept.
The old name is ~~no longer used~~ here.
The allowance runs until 3 January 2026.

## Superseded design
An old section.

## Closed
### [2026-01-01 10:00] a closed entry (minor)
- [x] a ticked line
- [-] a dropped line

## Related
- [[clean]]
"""

GUARDED = FRONT % ("guarded", "source", "") + """# Guarded

> **Status 2026-01-03:** his quoted words, never counted.
> 2026-01-04 he said this.

```
**Status 2026-01-03:** inside a code fence.
2026-01-04 a dated line inside a code fence.
```

~~~
Settled 2026-01-04: inside a tilde fence.
~~~

Three probes settled it (2026-01-02).
The count stood at twelve by 2 January 2026.
- **Is the term proper?** Both statements are kept until evidence settles them.
The allowance of next year runs until 3 January 2099.

## Open
### [2026-01-02 09:00] five retired watchers still on disk (minor)

## Related
- [[clean]]
"""

CLEAN = FRONT % ("clean", "concept", "") + """# Clean

## Definition
A page that states what holds now, with its reason.

## Key Points
- The measure was 379 of 623 pages when it was last taken.

## Related
- [[planted]]
"""

NOTES = FRONT % ("notes", "user", "") + """# Notes

The current text rests on [[#2026-01-02 — the note the text draws on]].

## Dated owner notes
### 2026-01-02 — the note the text draws on
> his words
### 2026-01-03 — a note another page draws on
> his words
### 2026-01-04 - a note only another note names
> his words
- See [[#2026-01-05 — a note later withdrawn]] and [[#2026-01-04 - a note only another note names]].
### 2026-01-05 — a note later withdrawn
> his words, which say the plan was withdrawn
- This note was superseded by his later words.

## Related
- [[clean]]
"""

CITER = FRONT % ("citer", "synthesis", "") + """# Citer

It rests on [[notes#2026-01-03 — a note another page draws on|his note]].

## Sources Used
- [[notes]]
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tmp-root", default=None)
    args = parser.parse_args()
    if not os.path.isfile(SCRIPT):
        sys.stdout.write("PROBE FAILED: old_state_listing.py is not beside the suite at %s\n" % SCRIPT)
        return 2
    root = tempfile.mkdtemp(prefix="old-state-listing-suite.", dir=args.tmp_root)
    try:
        wiki = os.path.join(root, "wiki")
        write(wiki, "developments/planted.md", PLANTED)
        write(wiki, "sources/guarded.md", GUARDED)
        write(wiki, "concepts/clean.md", CLEAN)
        write(wiki, "user/notes.md", NOTES)
        write(wiki, "syntheses/citer.md", CITER)
        write(wiki, "index.md", "---\ntitle: index\ntype: index\n---\n**Status 2026-01-03:** x\n")
        write(wiki, "log.md", "---\ntitle: log\ntype: log\n---\n## [2026-01-03] ingest | x\n2026-01-04 y\n")
        record = FRONT % ("register", "development", "") + "## Open\n### [2026-01-02 09:00] x\n- **Status 2026-01-03:** a\n- **Status 2026-01-04:** b\n\n## Closed\n### [2026-01-01 10:00] y\n"
        for rel in ("developments/known-issues.md", "developments/decided-work.md",
                    "developments/decided-work-done.md"):
            write(wiki, rel, record)
        before = manifest(root)

        # A · planted cases
        code, out, err = run("--wiki", wiki, "--today", "2026-01-10")
        header, rows = table(out)
        planted = rows.get("developments/planted.md", {})
        check("A1 the run exits 0", code == 0, err)
        check("A2 the header names path first and items last",
              header[:1] == ["path"] and header[-1:] == ["items"])
        expect = {"status_dated": "1", "dated_log_lines": "1", "change_dated": "1", "settled": "1",
                  "settled_keeps_both": "1", "history_headings": "2", "closed_entries": "3",
                  "struck": "1", "until_past": "1", "owner_notes": "0",
                  "items": "11"}
        for column, value in sorted(expect.items()):
            check("A3 planted page: %s is %s" % (column, value), planted.get(column) == value,
                  "got %r" % planted.get(column))
        check("A4 the guarded page gives no row: quotation, fences, narrative 'settled', a count "
              "'by' a date, an open conflict, a future end date and a register entry's heading",
              "sources/guarded.md" not in rows, str(rows.get("sources/guarded.md")))
        check("A5 the page's type is read from its frontmatter", planted.get("type") == "development")

        # B · the clean page, with its controls on the same run
        check("B1 the clean page gives no row", "concepts/clean.md" not in rows)
        check("B2 control: the same run counted the planted page", planted.get("items") == "11")
        check("A6 the frontmatter's `flagged:` line with a past date is not a column and not an item",
              "flag_past" not in header and planted.get("items") == "11")
        check("B3 control: the in-memory control printed", "CONTROL+ in memory" in err)
        check("B4 control: the engine control names the pages read",
              "CONTROL+ engine: 5 pages read, 5 with a `type:` field" in err, err)
        check("B5 the totals line counts pages read and pages with items",
              "TOTAL: 5 pages read · 2 pages with items · 13 items" in err, err)

        # C · owner notes
        notes = rows.get("user/notes.md", {})
        check("C1 four notes are found", notes.get("owner_notes") == "4", str(notes))
        check("C2 one note is marked as withdrawn or superseded, its quotation not read",
              notes.get("owner_notes_marked") == "1", str(notes))
        check("C3 two notes are unlinked: one named only inside the notes section, one withdrawn",
              notes.get("owner_notes_unlinked") == "2", str(notes))
        check("C4 a note marked and unlinked is one item, so the page holds two",
              notes.get("items") == "2", str(notes))
        check("C5 the citing page itself gives no row", "syntheses/citer.md" not in rows)

        # D · registries, records, the date, count()
        check("D1 the registries are skipped", "index.md" not in rows and "log.md" not in rows)
        check("D2 the fault list, the work list and its closed page are skipped by default",
              not any(rel in rows for rel in ("developments/known-issues.md",
                      "developments/decided-work.md", "developments/decided-work-done.md"))
              and "the records skipped: developments/known-issues.md" in err, err)
        code, out, err = run("--wiki", wiki, "--today", "2026-01-10", "--with-records")
        _header, whole = table(out)
        check("D3 --with-records counts the three record pages",
              all(whole.get(rel, {}).get("status_dated") == "2" and
                  whole.get(rel, {}).get("closed_entries") == "1"
                  for rel in ("developments/known-issues.md", "developments/decided-work.md",
                              "developments/decided-work-done.md"))
              and "CONTROL+ engine: 8 pages read" in err, err)
        code, out, err = run("--wiki", wiki, "--today", "2026-01-02")
        _header, early = table(out)
        check("D4 judged on an earlier day, the end date is not past",
              early.get("developments/planted.md", {}).get("until_past") == "0")
        sys.path.insert(0, HERE)
        import old_state_listing
        found, typed = old_state_listing.count(wiki, old_state_listing.parse_date("2026-01-10"))
        check("D5 count() gives the weekly pass the same counts as the table",
              found["developments/planted.md"][2]["items"] == 11 and typed == 5
              and found["concepts/clean.md"][2]["items"] == 0)
        try:
            old_state_listing.count(os.path.join(root, "no-such-folder"),
                                    old_state_listing.parse_date("2026-01-10"))
            raised = False
        except old_state_listing.ProbeFailed:
            raised = True
        check("D6 count() raises ProbeFailed on a missing folder, never an empty count", raised)

        # E · --show
        code, out, err = run("--wiki", wiki, "--today", "2026-01-10", "--show", "status_dated,settled")
        check("E1 --show exits 0 and prints hit lines, no table",
              code == 0 and "path\ttype" not in out and
              "developments/planted.md:9:status_dated:" in out and
              "developments/planted.md:12:settled:" in out, out)
        check("E2 --show names how many it showed", "SHOWN: 2 of 2 hits" in err, err)
        code, out, err = run("--wiki", wiki, "--today", "2026-01-10", "--show", "closed_entries",
                             "--every", "2")
        check("E3 --every 2 shows every second hit", "SHOWN: 1 of 3 hits" in err, err)

        # F · the live control
        code, out, err = run("--wiki", wiki, "--today", "2026-01-10", "--control-page",
                             "developments/planted.md", "--control-text", "Status 2026-01-03")
        check("F1 a live control that is there prints CONTROL+ live and the table",
              code == 0 and "CONTROL+ live" in err and "developments/planted.md" in out, err)
        code, out, err = run("--wiki", wiki, "--today", "2026-01-10", "--control-page",
                             "concepts/clean.md", "--control-text", "Status 2026-01-03")
        check("F2 a live control that is not there is PROBE FAILED, exit 2, no table",
              code == 2 and "PROBE FAILED" in err and out == "", err)
        code, out, err = run("--wiki", wiki, "--control-page", "developments/absent.md",
                             "--control-text", "Status")
        check("F3 a live control page that does not exist is PROBE FAILED",
              code == 2 and "PROBE FAILED" in err and out == "", err)

        # G · broken premises
        code, out, err = run("--wiki", os.path.join(root, "no-such-folder"))
        check("G1 a missing wiki folder is PROBE FAILED", code == 2 and "PROBE FAILED" in err and out == "")
        empty = os.path.join(root, "empty")
        os.makedirs(empty)
        code, out, err = run("--wiki", empty)
        check("G2 a folder with no pages is PROBE FAILED", code == 2 and "0 pages read" in err and out == "")
        untyped = os.path.join(root, "untyped")
        write(untyped, "a.md", "# no frontmatter\n**Status 2026-01-03:** x\n")
        code, out, err = run("--wiki", untyped)
        check("G3 pages with no `type:` field anywhere are PROBE FAILED",
              code == 2 and "none carries a `type:` field" in err and out == "")
        broken = os.path.join(root, "broken")
        write(broken, "a.md", CLEAN)
        with open(os.path.join(broken, "b.md"), "wb") as handle:
            handle.write(b"---\ntype: source\n---\n\xff\xfe not utf-8\n")
        code, out, err = run("--wiki", broken)
        check("G4 a page that cannot be decoded is PROBE FAILED, never a partial count",
              code == 2 and "could not finish" in err and out == "", err)
        code, out, err = run("--wiki", wiki, "--today", "10 January")
        check("G5 a --today that is no date is PROBE FAILED", code == 2 and "PROBE FAILED" in err)
        code, out, err = run("--wiki", wiki, "--show", "no_such_category")
        check("G6 an unknown --show category is PROBE FAILED", code == 2 and "PROBE FAILED" in err)
        code, out, err = run("--wiki", wiki, "--control-page", "developments/planted.md")
        check("G7 a control page without its text is PROBE FAILED", code == 2 and "PROBE FAILED" in err)
        code, out, err = run("--wiki", wiki, "--show", "settled", "--every", "0")
        check("G8 --every 0 is PROBE FAILED", code == 2 and "PROBE FAILED" in err)

        # H · the pages are left byte-identical
        fixtures_before = {k: v for k, v in before.items() if k.startswith("wiki" + os.sep)}
        after = manifest(root)
        fixtures_after = {k: v for k, v in after.items() if k.startswith("wiki" + os.sep)}
        check("H1 after every run above, the ten wiki files have the checksums they began with",
              len(fixtures_before) == 10 and fixtures_before == fixtures_after)
        check("H2 the runs made no new file beside the pages",
              sorted(fixtures_after) == sorted(fixtures_before))
        victim = os.path.join(wiki, "concepts", "clean.md")
        with open(victim, "r+b") as handle:
            handle.seek(-2, os.SEEK_END)
            byte = handle.read(1)
            handle.seek(-2, os.SEEK_END)
            handle.write(b"X" if byte != b"X" else b"Y")
        changed = {k: v for k, v in manifest(root).items() if k.startswith("wiki" + os.sep)}
        check("H3 control: one byte changed in the same folder is caught by the same comparison",
              changed != fixtures_before and
              [k for k in changed if changed[k] != fixtures_before.get(k)] ==
              [os.path.join("wiki", "concepts", "clean.md")])

        # I · the source
        with open(SCRIPT, "r", encoding="utf-8") as handle:
            source = handle.read()
        code_lines = source.split('"""', 2)[2] if source.count('"""') >= 2 else source
        writers = re.findall(r"open\([^)]*[\"'](?:w|a|x|r\+|w\+|a\+)b?[\"']|os\.(?:remove|unlink|rename|"
                             r"replace|rmdir|makedirs|mkdir|truncate)\(|shutil\.|\.write_text\(|"
                             r"\.write_bytes\(|\.unlink\(", code_lines)
        check("I1 the source holds no call that writes, removes or renames a file", writers == [],
              str(writers))
        check("I2 control: the same search method finds the read the source does make",
              len(re.findall(r"open\(path, \"rb\"\)", code_lines)) == 1)
        owner = re.findall(r"/Users/|/home/[a-z]|OneDrive|" + "ai" + "Myth" + r"|[Jj]erry|" + "jer" + "ang" + r"|run-2026\d{4}", source)
        check("I3 the source holds no owner path, name or run id", owner == [], str(owner))
        check("I4 control: the same search finds a word the source does hold",
              len(re.findall(r"PROBE FAILED", source)) >= 3)
        check("I5 the source keeps UK spelling in the words it prints (normalised, not normalized)",
              "normalized" not in source and "color" not in source.lower().replace("colour", ""))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    check("Z1 the suite's fixture folder is removed", not os.path.exists(root))
    failed = [name for name, ok in RESULTS if not ok]
    total = len(RESULTS)
    if failed:
        sys.stdout.write("FAIL %d/%d\n" % (len(failed), total))
        return 1
    sys.stdout.write("PASS %d/%d\n" % (total, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
