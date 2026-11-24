#!/usr/bin/env python3
"""old_state_listing.py: the old-state listing. It counts, page by page, the marks that old states
leave on wiki pages.

A lister. It reads the pages under one wiki folder and prints one row per page that holds at
least one counted item, with totals. It writes nothing, changes nothing and judges nothing: every
count is a count of CANDIDATES for a reader to judge, never a verdict that a passage is stale (a
dated status line may be the current state with its date).

What it is for: an end date that has passed with no write to announce it, and the old habit of
marking a change on the page (a dated status line, a "superseded on" note, a history section)
coming back. What it cannot see: an old state left in plain words beside the newer one, with no
date and no mark. Only a reader finds that (the closing review, deep-lint's sample).

Who runs it: deep-lint's Step 4, for its totals and the pages it ranks highest; and the weekly
pass (`rule_register.py weekly`), which imports `count()` and lists only the end dates that have
passed and the pages whose total rose since the last recorded audit (`record-audit` records the
totals it compares with).

  stdout   the table, tab-separated: a header line, then one row per page with items >= 1,
           largest first. With --show, the hit lines of the named categories instead.
  stderr   the controls, the totals and any PROBE FAILED line.

Usage
  old_state_listing.py --wiki DIR [--today YYYY-MM-DD] [--with-records]
                       [--control-page REL --control-text TEXT]
                       [--show CATEGORY[,CATEGORY...] [--every K]]

  --wiki           the wiki folder. The two registries at its root (index.md, log.md) are always
                   skipped: one is a catalogue and the other an append-only timeline. The fault list
                   and the work list with its closed page (RECORDS below), and the fault list's
                   closed page where a sweep has made it (records() below), are records by their
                   purpose and are skipped too: `check_register.py` lists an open fault entry with
                   more than one status, and the write primitives keep the work list.
  --with-records   count the record pages as well (the shape of the first count): the three, and
                   the fault list's closed page where it exists.
  --today          the date that "past its date" is judged against (default: the clock's date).
  --control-page   with --control-text: a live positive control. The page must be read and one
                   `status_dated` hit must sit on a line holding the text. Otherwise PROBE FAILED.
  --show           print each hit of the named categories as `path:line:category:text` and no
                   table, every K-th hit (default 1), so a person can read what a count counts.

What is counted (outside frontmatter, fenced code, block quotations and the inside of a wikilink,
which are never counted: a quotation is somebody's words and a link is a name, not a mark the page
carries about itself)
  status_dated         the word "status" followed directly by a date ("Status 2026-08-26:",
                       "status 20 November 2026, 23:30").
  dated_log_lines      a paragraph or list item that opens with a date, the shape of a change log.
  change_dated         a change word (superseded, replaced, retired, withdrawn, amended, corrected,
                       re-keyed, renamed, re-graded, reworded, widened, narrowed, cleared, closed)
                       followed closely by a date.
  settled              "Settled" with its capital, followed directly by a date: a settled
                       conflict's item, as the contract writes one.
  settled_keeps_both   (context, not an item) of those, items whose own line says both statements
                       are kept. Such wording elsewhere is not counted: an open conflict keeps
                       both statements by rule.
  owner_notes          (context, not an item) `### DATE — subject` headings inside a
                       `## Dated owner notes` section.
  owner_notes_marked   of those, notes whose own text (its quotation and its links aside) says
                       it was withdrawn, replaced, superseded or overtaken.
  owner_notes_unlinked of those, notes no link from outside the notes section reaches, in any page:
                       the current text names no such note as its ground.
  history_headings     headings that announce history (Status, History, Retired, Superseded,
                       Changelog, Closed, Withdrawn, Deprecated, Archive, Replaced). A heading
                       that opens with a bracketed stamp is a register entry, and one that is a
                       file path is a listing; neither is counted.
  closed_entries       entries under a `## Closed` heading: `### ` headings, and list items that
                       open with a ticked or struck box.
  struck               struck-through text.
  until_past           an end-date phrase (until, expires, valid to, ends on, closes on,
                       deadline, due) whose date, written with its year, is before --today.
  items                the sum of the above, with the owner notes counted once each when marked
                       or unlinked. The two context columns are not summed.

Controls, run first on every call
  1. In memory: a fixture built here and kept nowhere holds one case per category that must count
     and cases that must not (a status inside a quotation, a dated line inside a code fence, the
     frontmatter's own date fields and its `flagged:` line, which the weekly flag listing already
     reads). Any category off its expected count: PROBE FAILED, exit 2.
  2. Engine: at least one page was read and at least one carries a `type:` field. Otherwise the
     scan read nothing it could recognise: PROBE FAILED, exit 2.
  3. Live, when asked for: see --control-page.
  A page that cannot be read or decoded is a scan that could not finish: PROBE FAILED, exit 2.

Exit codes
  0  the count ran; the table (or the hits) was printed. Items found are not a failure.
  2  PROBE FAILED: a broken premise. Nothing is reported as a count.

Its precision, read item by item on the live wiki on 21 November 2026 by the prototype this script
adopts (a sample of every 80th, 6th, 55th, 4th and 2nd hit): dated status lines 29 of 29 were dated
status lines; lines that open with a date 27 of 27 were dated entries; change marks about 23 of 26;
`Settled` items 15 of 17; end dates now past about 11 of 14. So the table prices the reading to be
done and is no list of faults.
"""

import argparse
import datetime
import os
import re
import sys

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December")
MONTH_RE = "(?:" + "|".join(MONTHS) + ")"
ISO = r"\d{4}-\d{2}-\d{2}"
LONG = r"\d{1,2} " + MONTH_RE + r"(?: \d{4})?"
LONG_Y = r"\d{1,2} " + MONTH_RE + r" \d{4}"
DATE = "(?:" + ISO + "|" + LONG + ")"
DATE_Y = "(?:" + ISO + "|" + LONG_Y + ")"

RE_STATUS = re.compile(r"(?i)\bstatus(?: fact)?(?: added)?\s*(?:[—–:\-]\s*)?\(?\s*(" + DATE + ")")
RE_DATED_LINE = re.compile(r"^\s*(?:[-*+] |\d+\. )?(?:\*\*|\*|_)?\(?(" + DATE_Y + r")\b")
CHANGE_WORDS = ("superseded|replaced|retired|withdrawn|amended|corrected|correction|re-keyed|"
                "renamed|re-graded|reworded|widened|narrowed|cleared|closed")
RE_CHANGE = re.compile(r"(?i)\b(?:" + CHANGE_WORDS + r")\b[^.\n|]{0,12}?\b(?:on |of |at |in )?("
                       + DATE + ")")
RE_SETTLED = re.compile(r"\bSettled\s+(?:for [^,:.\n]{1,40},\s*)?(" + DATE + ")")
RE_BOTH = re.compile(
    r"(?i)\bboth (?:statements|positions|readings|quotations|versions)\b[^.\n]{0,40}?"
    r"\b(?:kept|stay|stays|remain|remains|recorded)\b"
    r"|\bboth (?:are|stay|remain)s? (?:kept|recorded)\b"
    r"|\bboth stay kept\b|\beach kept\b|\ball are kept\b"
    r"|\bstays? recorded\b|\bkept beside\b"
    r"|\bstands as the dated record\b|\bkept (?:here )?as (?:a |the )?(?:dated )?(?:record|history)\b")
RE_NOTES_HEAD = re.compile(r"(?i)^##\s+dated owner notes\s*$")
RE_NOTE = re.compile(r"^###\s+(" + ISO + r")\s+[—–-]\s+(.*\S)\s*$")
RE_NOTE_MARK = re.compile(
    r"(?i)\b(?:withdrawn|withdrew|withdraws|retracted|superseded|overtaken|replaced by|"
    r"no longer holds|no longer stands)\b")
RE_HEADING = re.compile(r"^(#{2,4})\s+(.*\S)\s*$")
RE_NOT_A_SECTION = re.compile(r"^\[|^\S+/\S+\.\w+$")
RE_HISTORY_HEAD = re.compile(
    r"(?i)^status$|\b(?:history|retired|superseded|changelog|change log|closed|withdrawn|"
    r"deprecated|archive|archived|replaced)\b")
RE_CLOSED_HEAD = re.compile(r"(?i)^##\s+closed\s*$")
RE_CLOSED_ITEM = re.compile(r"^\s*[-*+] \[(?:x|X|-)\] ")
RE_STRUCK = re.compile(r"~~[^~\n]{3,}~~")
RE_UNTIL = re.compile(
    r"(?i)\b(?:until|expires?(?: on)?|valid (?:to|until|through)|ends? on|ending on|"
    r"closes? on|deadline(?: of| is|:)?|due(?: on| by)?)\s+(" + DATE_Y + ")")
RE_LINK = re.compile(r"\[\[([^\]\|#]*)#([^\]\|]+)(?:\|[^\]]*)?\]\]")
RE_ANY_LINK = re.compile(r"\[\[[^\]]*\]\]")
RE_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")

ITEM_CATEGORIES = ("status_dated", "dated_log_lines", "change_dated", "settled",
                   "owner_notes_marked", "owner_notes_unlinked", "history_headings",
                   "closed_entries", "struck", "until_past")
CONTEXT_CATEGORIES = ("settled_keeps_both", "owner_notes")
# The fault list, the work list and its closed page, relative to the wiki folder.
RECORDS = ("developments/known-issues.md", "developments/decided-work.md",
           "developments/decided-work-done.md")
# The fault list's closed page, a record once sweep_closed.py has made it; named only where it
# exists, so an unswept wiki is read, and printed, as before.
SWEPT_RECORDS = ("developments/known-issues-closed.md",)


def records(wiki):
    """RECORDS, and each swept record page that exists in `wiki`."""
    return RECORDS + tuple(rel for rel in SWEPT_RECORDS if os.path.exists(os.path.join(wiki, rel)))
COLUMNS = ("path", "type", "bytes", "status_dated", "dated_log_lines",
           "change_dated", "settled", "settled_keeps_both", "owner_notes", "owner_notes_marked",
           "owner_notes_unlinked", "history_headings", "closed_entries", "struck", "until_past",
           "items")


class ProbeFailed(Exception):
    pass


def parse_date(text):
    """A date written as YYYY-MM-DD or as `D Month YYYY`; None when it carries no year or is no date."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    try:
        if m:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = re.fullmatch(r"(\d{1,2}) (" + MONTH_RE + r") (\d{4})", text)
        if m:
            return datetime.date(int(m.group(3)), MONTHS.index(m.group(2)) + 1, int(m.group(1)))
    except ValueError:
        return None
    return None


def norm_heading(text):
    """A heading as a link names it: case, runs of spaces and the kind of dash are not compared."""
    return re.sub(r"\s+", " ", re.sub(r"\s[—–-]\s", " — ", text.strip().lower()))


def split_page(text):
    """Frontmatter fields the count reads, and the body lines with their 1-based numbers."""
    lines = text.split("\n")
    front = {}
    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start = i + 1
                break
            m = re.match(r"^([A-Za-z_]+):\s*(.*)$", lines[i])
            if m:
                front[m.group(1)] = m.group(2)
        else:
            start = 0
            front = {}
    body = [(n + 1, lines[n]) for n in range(start, len(lines))]
    return front, body


def scan_page(text, today):
    """One page's hits, as a list of (category, line number, line text), and its note headings."""
    front, body = split_page(text)
    hits = []
    notes = []          # (line number, normalised heading text, marked)
    links = []          # (target page stem or '', normalised heading, in_notes_section)
    in_fence = None
    in_notes = False
    in_closed = False
    current_note = None
    for number, line in body:
        fence = RE_FENCE.match(line)
        if in_fence:
            if fence and fence.group(1)[0] == in_fence[0] and len(fence.group(1)) >= len(in_fence):
                in_fence = None
            continue
        if fence:
            in_fence = fence.group(1)
            continue
        heading = RE_HEADING.match(line)
        if line.startswith("## ") or line.startswith("# "):
            in_notes = bool(RE_NOTES_HEAD.match(line))
            in_closed = bool(RE_CLOSED_HEAD.match(line))
            current_note = None
        for m in RE_LINK.finditer(line):
            links.append((m.group(1).strip(), norm_heading(m.group(2)), in_notes))
        if line.lstrip().startswith(">"):
            continue
        if heading:
            title = heading.group(2)
            note = RE_NOTE.match(line) if in_notes else None
            if note:
                current_note = [number, norm_heading(title), False]
                notes.append(current_note)
            elif in_closed and heading.group(1) != "##":
                hits.append(("closed_entries", number, line))
            elif RE_HISTORY_HEAD.search(title.strip()) and not RE_NOT_A_SECTION.search(title.strip()):
                hits.append(("history_headings", number, line))
            continue
        if in_closed and RE_CLOSED_ITEM.match(line):
            hits.append(("closed_entries", number, line))
        # A link's own words are a name, not a mark: a link to a dated heading is not a status.
        plain = RE_ANY_LINK.sub("[[]]", line)
        if current_note is not None and RE_NOTE_MARK.search(plain):
            current_note[2] = True
        for _ in RE_STATUS.finditer(plain):
            hits.append(("status_dated", number, line))
        if RE_DATED_LINE.match(line):
            hits.append(("dated_log_lines", number, line))
        for _ in RE_CHANGE.finditer(plain):
            hits.append(("change_dated", number, line))
        settled_here = len(RE_SETTLED.findall(plain))
        for _ in range(settled_here):
            hits.append(("settled", number, line))
        if settled_here and RE_BOTH.search(plain):
            hits.append(("settled_keeps_both", number, line))
        for _ in RE_STRUCK.finditer(plain):
            hits.append(("struck", number, line))
        for m in RE_UNTIL.finditer(plain):
            when = parse_date(m.group(1))
            if when is not None and when < today:
                hits.append(("until_past", number, line))
    return front, hits, notes, links


FIXTURE = """---
title: fixture
type: development
updated: 2026-01-02
flagged: 2026-01-01 a time-limited fact. Clears on 2026-01-05.
---
# Fixture

**Status 2026-01-03:** the newer layer.
2026-01-04 (a session): what changed that day.
The rule was superseded on 4 January 2026 by a newer one.
- **Settled 2026-01-04: which name.** Both statements are kept.
The old name is ~~no longer used~~ here; the allowance runs until 3 January 2026.
The allowance of next year runs until 3 January 2099.
Three probes settled it (2026-01-02), and the count stood at twelve by 2 January 2026.
An open conflict is not a mark: both statements are kept until evidence settles them.

## Open
### [2026-01-02 09:00] five retired watchers still on disk (minor)

> **Status 2026-01-03:** a quotation, never counted.

```
2026-01-04 a dated line inside a code fence, never counted.
```

## Status
An undated line under a history heading.

## Dated owner notes
### 2026-01-02 — a note the text draws on
> his words
### 2026-01-03 — a note later withdrawn
> his words
- This note was withdrawn by his later words.

## Closed
### [2026-01-01 10:00] a closed entry
- [x] a ticked line

## Related
- See [[#2026-01-02 — a note the text draws on]].
"""
FIXTURE_EXPECT = {"status_dated": 1, "dated_log_lines": 1, "change_dated": 1, "settled": 1,
                  "settled_keeps_both": 1, "owner_notes": 2, "owner_notes_marked": 1,
                  "owner_notes_unlinked": 1, "history_headings": 2, "closed_entries": 2,
                  "struck": 1, "until_past": 1}


def tally(hits, notes, linked):
    """The counts of one page. `linked` is the set of its note headings some outside link reaches."""
    counts = dict.fromkeys(COLUMNS[3:], 0)
    for category, _number, _line in hits:
        counts[category] += 1
    counts["owner_notes"] = len(notes)
    candidates = 0
    for _number, heading, marked in notes:
        unlinked = heading not in linked
        counts["owner_notes_marked"] += 1 if marked else 0
        counts["owner_notes_unlinked"] += 1 if unlinked else 0
        candidates += 1 if (marked or unlinked) else 0
    counts["items"] = sum(counts[c] for c in ITEM_CATEGORIES
                          if c not in ("owner_notes_marked", "owner_notes_unlinked")) + candidates
    return counts


def control_in_memory():
    today = datetime.date(2026, 1, 10)
    _front, hits, notes, links = scan_page(FIXTURE, today)
    linked = {heading for stem, heading, in_notes in links if not in_notes and stem == ""}
    counts = tally(hits, notes, linked)
    wrong = [(c, counts[c], FIXTURE_EXPECT[c]) for c in FIXTURE_EXPECT if counts[c] != FIXTURE_EXPECT[c]]
    if wrong:
        raise ProbeFailed("the in-memory control is off: " + "; ".join(
            "%s counted %d, expected %d" % w for w in wrong))
    return len(FIXTURE_EXPECT)


def page_paths(wiki, with_records=False):
    skip = ("index.md", "log.md") + (() if with_records else records(wiki))
    found = []
    for folder, _dirs, files in os.walk(wiki):
        for name in files:
            if not name.endswith(".md"):
                continue
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, wiki)
            if rel.replace(os.sep, "/") in skip:
                continue
            found.append((rel, path))
    return sorted(found)


def count(wiki, today, with_records=False):
    """Every page's counts: {rel: (type, bytes, counts, hits)}, with the in-memory and engine
    controls run first. Raises ProbeFailed on a broken premise; writes nothing."""
    control_in_memory()
    if not os.path.isdir(wiki):
        raise ProbeFailed("no such wiki folder: %s" % wiki)
    pages = {}
    every_link = []
    typed = 0
    for rel, path in page_paths(wiki, with_records):
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise ProbeFailed("cannot read %s (%s): the scan could not finish" % (rel, error))
        front, hits, notes, links = scan_page(text, today)
        typed += 1 if front.get("type") else 0
        stem = os.path.splitext(os.path.basename(rel))[0]
        for target, heading, in_notes in links:
            every_link.append((target or stem, heading, in_notes and target in ("", stem), stem))
        pages[rel] = (stem, front, hits, notes, len(raw))
    if not pages:
        raise ProbeFailed("0 pages read under %s" % wiki)
    if typed == 0:
        raise ProbeFailed("%d pages read and none carries a `type:` field" % len(pages))
    # A note counts as linked when a link reaches its heading from another page, or from its
    # own page outside the notes section.
    reached = set()
    for target, heading, inside_own_notes, _source in every_link:
        if not inside_own_notes:
            reached.add((target.lower(), heading))
    result = {}
    for rel in sorted(pages):
        stem, front, hits, notes, size = pages[rel]
        linked = {heading for target, heading in reached if target == stem.lower()}
        kind = front.get("type", "").split("#")[0].strip().strip("\"'") or "(none)"
        result[rel] = (kind, size, tally(hits, notes, linked), hits)
    return result, typed


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=True, description="the old-state listing")
    parser.add_argument("--wiki", required=True)
    parser.add_argument("--today")
    parser.add_argument("--with-records", action="store_true")
    parser.add_argument("--control-page")
    parser.add_argument("--control-text")
    parser.add_argument("--show")
    parser.add_argument("--every", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        if bool(args.control_page) != bool(args.control_text):
            raise ProbeFailed("--control-page and --control-text go together")
        if args.today:
            today = parse_date(args.today)
            if today is None:
                raise ProbeFailed("--today is not a YYYY-MM-DD date: %r" % args.today)
        else:
            today = datetime.date.today()
        show = [c for c in (args.show or "").split(",") if c]
        unknown = [c for c in show if c not in ITEM_CATEGORIES + CONTEXT_CATEGORIES]
        if unknown:
            raise ProbeFailed("--show names no category: " + ", ".join(unknown))
        if args.every < 1:
            raise ProbeFailed("--every must be 1 or more")
        pages, typed = count(args.wiki, today, args.with_records)
        sys.stderr.write("CONTROL+ in memory: %d categories at their expected counts; a quoted status, "
                         "a fenced dated line, the frontmatter dates and flag, a narrative 'settled', a "
                         "count 'by' a date, an open conflict's 'both kept' and a register entry's "
                         "heading not counted\n" % len(FIXTURE_EXPECT))
        sys.stderr.write("CONTROL+ engine: %d pages read, %d with a `type:` field%s\n"
                         % (len(pages), typed, "" if args.with_records else
                            "; the records skipped: " + ", ".join(records(args.wiki))))
        if args.control_page:
            if args.control_page not in pages:
                raise ProbeFailed("the live control page is not among the pages read: %s"
                                  % args.control_page)
            lines = [line for category, _n, line in pages[args.control_page][3]
                     if category == "status_dated" and args.control_text in line]
            if not lines:
                raise ProbeFailed("the live control found no `status_dated` hit holding %r on %s"
                                  % (args.control_text, args.control_page))
            sys.stderr.write("CONTROL+ live: %s holds a counted dated status line with %r\n"
                             % (args.control_page, args.control_text))
    except ProbeFailed as failure:
        sys.stderr.write("PROBE FAILED: %s\n" % failure)
        return 2
    if show:
        shown = seen = 0
        for rel in sorted(pages):
            for category, number, line in pages[rel][3]:
                if category in show:
                    seen += 1
                    if seen % args.every == 0:
                        shown += 1
                        sys.stdout.write("%s:%d:%s:%s\n" % (rel, number, category,
                                                           line.strip()[:220]))
        sys.stderr.write("SHOWN: %d of %d hits in %s\n" % (shown, seen, ",".join(show)))
        return 0
    rows = [[rel, kind, size] + [counts[c] for c in COLUMNS[3:]]
            for rel, (kind, size, counts, _hits) in pages.items() if counts["items"] >= 1]
    rows.sort(key=lambda row: (-row[-1], row[0]))
    sys.stdout.write("\t".join(COLUMNS) + "\n")
    for row in rows:
        sys.stdout.write("\t".join(str(cell) for cell in row) + "\n")
    totals = {c: sum(row[3 + i] for row in rows) for i, c in enumerate(COLUMNS[3:])}
    sys.stderr.write("TOTAL: %d pages read · %d pages with items · %d items · %d bytes on those "
                     "pages\n" % (len(pages), len(rows), totals["items"], sum(row[2] for row in rows)))
    sys.stderr.write("BY CATEGORY: " + " · ".join("%s %d" % (c, totals[c]) for c in COLUMNS[3:-1])
                     + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
