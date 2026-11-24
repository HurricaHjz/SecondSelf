#!/usr/bin/env python3
"""test_bulk_clean_check.py: the planted cases of bulk-clean-check.py (the clean method, section 6).

Every case runs the check as a program on fixtures built in a fresh temporary folder, which the
suite removes. Its last leg shows that the check left every fixture byte-identical, with a control
that changes one byte in the same folder and must be caught. Ends `PASS n/n` or `FAIL k/n`.

  test_bulk_clean_check.py            (about 3 seconds)
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK = os.path.join(HERE, "bulk-clean-check.py")
PAGE = "wiki/developments/page.md"
LESSONS = "wiki/experience/lessons.md"

BASE = """---
title: Page
type: development
confidence: medium
updated: 2026-11-01
sources: [a.md, b.md]
---

# Page

The current state, said plainly.

**Status 2026-10-01:** an older layer that a newer state replaced.

He said "keep only the newest version of the phrasing" on 19 October 2026.

> his words, a quotation block
> its second line

## Current

- A list item that stays.
- A twin line.
- A twin line.

| a | b |
|---|---|
| 1 | 2 |

See [[#Current]] for the state.

## Old heading

A paragraph under a heading the clean removes.

## Sources Used

- a.md
"""

LESSONS_BASE = """---
title: Lessons
type: synthesis
sources: [a.md]
---

## Rules
E1. An owner rule, kept as written. (owner · 2026-11-07 · his word)
E2. A lesson whose bracket tells its history. (lesson · 2026-11-08 · a round; widened on 2026-11-09 by run x)
E3. A second owner rule. (owner · 2026-11-08 · his word)

## Sources Used
- a.md
"""

RESULTS = []
RUNS = []          # (fixture folder, every file byte-identical after the run)


def record(name, ok, detail=""):
    RESULTS.append((name, ok))
    print("%s  %s%s" % ("ok  " if ok else "FAIL", name, "" if ok else "  :: " + detail))


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def block_lines(text, block):
    """The 1-based lines `N-M` where `block` (whole lines) stands in `text`."""
    start = text.index(block)
    first = text.count("\n", 0, start) + 1
    return "%d-%d" % (first, first + block.count("\n")) if "\n" in block else str(first)


def row(page, text, block, cls, replaced_by, hq="no", held="page.hold-2026-11-21.md",
        lines=None):
    return "\t".join([page, lines if lines is not None else block_lines(text, block),
                      " ".join(block.split()[:12]), str(len(block.encode())), sha(block), cls,
                      replaced_by, hq, held])


HEADER = "\t".join(("page", "lines", "first_words", "bytes", "sha256", "class", "replaced_by",
                    "held_quotation", "held"))


class Fixture:
    """A wiki with the page, its hold, a clean's folder, a page that links to it and a destination."""

    def __init__(self, root, name, page=PAGE, before=BASE):
        self.dir = os.path.join(root, name)
        self.wiki = os.path.join(self.dir, "wiki")
        self.page = page
        self.before = before
        for folder in ("developments", "experience"):
            os.makedirs(os.path.join(self.wiki, folder), exist_ok=True)
        self.write(os.path.join(self.dir, page), before)
        self.write(os.path.join(self.wiki, "developments", "other.md"),
                   "---\ntitle: Other\ntype: development\n---\n\nSee [[page#Old heading]] and "
                   "[[page#Current]].\n\n## Sources Used\n- x\n")
        self.write(os.path.join(self.wiki, "developments", "dest.md"),
                   "---\ntitle: Dest\ntype: development\n---\n\n## Moved here\n\nA paragraph under "
                   "a heading the clean removes.\n\n## Sources Used\n- x\n")
        self.clean = os.path.join(self.dir, "clean")
        os.makedirs(self.clean)
        self.hold = os.path.join(self.clean, "page.hold-2026-11-21.md")
        self.write(self.hold, before)
        self.write(os.path.join(self.clean, "BEFORE.md"), before)

    @staticmethod
    def write(path, text, binary=False):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(text if binary else text.encode("utf-8"))

    def set(self, after, rows=(), header=True):
        self.write(os.path.join(self.clean, "AFTER.md"), after)
        body = ([HEADER] if header else []) + list(rows)
        self.write(os.path.join(self.clean, "LEDGER.tsv"), "\n".join(body) + ("\n" if body else ""))

    def run(self, *extra, hold=None, trial=False):
        argv = [sys.executable, "-B", CHECK, "--page", self.page, "--wiki", self.wiki,
                "--hold", hold or self.hold, "--dir", self.clean] + list(extra)
        if trial:
            argv.append("--trial")
        seen = manifest(self.dir)
        done = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        RUNS.append((self.dir, seen == manifest(self.dir)))
        return done.returncode, done.stdout.decode("utf-8", "replace")


def failed(out):
    return sorted(set(re.findall(r"^(\w\d) FAIL", out, re.M)))


def expect(name, result, code, legs=None, contains=()):
    rc, out = result
    ok = rc == code and (legs is None or failed(out) == sorted(legs)) \
        and all(c in out for c in contains)
    record(name, ok, "exit %d, failed %s\n%s" % (rc, failed(out), out[-1500:]))


def good_clean(text):
    """A clean that the check must let through: three removals, one rewrite, frontmatter trimmed."""
    status = "**Status 2026-10-01:** an older layer that a newer state replaced."
    said = 'He said "keep only the newest version of the phrasing" on 19 October 2026.'
    old_head = "## Old heading"
    old_para = "A paragraph under a heading the clean removes."
    rewrite = ("aiMyth's wording of his words of 19 October 2026: a page keeps only the newest "
               "version of the phrasing.")
    after = (text.replace(status + "\n\n", "").replace(said, rewrite)
             .replace(old_head + "\n\n" + old_para + "\n\n", "")
             .replace("updated: 2026-11-01", "updated: 2026-11-21")
             .replace("sources: [a.md, b.md]", "sources: [a.md]"))
    rows = [row(PAGE, text, status, "change log", "## Current"),
            row(PAGE, text, said, "replaced", "## Current", hq="yes"),
            row(PAGE, after, rewrite, "rewritten", block_lines(text, said), lines=""),
            row(PAGE, text, old_head, "replaced", "[[#Current]]"),
            row(PAGE, text, old_para, "expired", "ended on 1 October 2026")]
    return after, rows


def main():
    if not os.path.isfile(CHECK):
        print("PROBE FAILED: bulk-clean-check.py is not beside the suite at %s" % CHECK)
        return 2
    root = tempfile.mkdtemp(prefix="bulk-clean-check.")
    try:
        cases(root)
    finally:
        shutil.rmtree(root)
    failures = sum(1 for _n, ok in RESULTS if not ok)
    print("PASS %d/%d" % (len(RESULTS), len(RESULTS)) if not failures
          else "FAIL %d/%d" % (failures, len(RESULTS)))
    return 1 if failures else 0


def manifest(folder):
    found = {}
    for here, _dirs, files in os.walk(folder):
        for name in files:
            path = os.path.join(here, name)
            with open(path, "rb") as handle:
                found[os.path.relpath(path, folder)] = hashlib.sha256(handle.read()).hexdigest()
    return found


def cases(root):
    # The must-pass cases first: an identical candidate, and a real clean.
    f = Fixture(root, "identity")
    f.set(BASE, header=False)
    expect("identical candidate with an empty ledger passes", f.run(), 0, [],
           ["PASS: every leg passed", "CONTROL+ in memory"])
    out = f.run()[1]
    record("with no listed block the verdict is bare (must not name a wait)",
           "PASS: every leg passed\n" in out and "the swap waits" not in out, out[-400:])

    f = Fixture(root, "good")
    after, rows = good_clean(BASE)
    f.set(after, rows)
    expect("a clean with every removal in the ledger passes (enforce)", f.run(), 0, [],
           ["PASS: every leg passed"])
    expect("links from another page to a lost heading are listed, and list only", f.run(), 0, [],
           ["LISTED: wiki/developments/other.md:6 links to the heading 'Old heading'"])
    out = f.run()[1]
    record("the link to a heading AFTER keeps is not listed", "'Current' that AFTER lost" not in out,
           out)
    expect("the bytes added and removed are printed", f.run(), 0, [],
           ["NOTE: L3 bytes: BEFORE %d" % len(BASE.encode())])

    # Q1, Q2: one character changed inside a quotation.
    f = Fixture(root, "q1")
    after = BASE.replace("> its second line", "> its second lime")
    block = "> his words, a quotation block\n> its second line"
    f.set(after, [row(PAGE, BASE, block, "replaced", "## Current", hq="yes")])
    expect("one character changed in a quotation block fails Q1", f.run(), 1, ["L3", "Q1"])

    f = Fixture(root, "q2")
    said = 'He said "keep only the newest version of the phrasing" on 19 October 2026.'
    after = BASE.replace(said, said.replace("newest", "newset"))
    f.set(after, [row(PAGE, BASE, said, "replaced", "## Current", hq="yes"),
                  row(PAGE, after, said.replace("newest", "newset"), "rewritten",
                      block_lines(BASE, said), lines="")])
    # Q4 reads words outside quotation marks, so the altered quotation is Q2's; Q4 lists the block.
    expect("one character changed in an inline quotation fails Q2", f.run(), 1, ["Q2"],
           ["LISTED: Q4 LEDGER line 3"])

    f = Fixture(root, "q2-curly")
    curly = "He said “keep only the newest version” and left."
    text = BASE.replace(said, curly)
    f = Fixture(root, "q2-curly-b", before=text)
    after = text.replace("newest version”", "newest versions”")
    f.set(after, [row(PAGE, text, curly, "replaced", "## Current", hq="yes"),
                  row(PAGE, after, curly.replace("version”", "versions”"), "rewritten",
                      block_lines(text, curly), lines="")])
    expect("a curly quotation changed fails Q2", f.run(), 1, ["Q2"])

    # Q3: a removed quoted sentence in a row marked no.
    f = Fixture(root, "q3")
    f.set(BASE.replace(said + "\n\n", ""), [row(PAGE, BASE, said, "replaced", "## Current", hq="no")])
    expect("a removed quoted sentence marked held_quotation: no fails Q3", f.run(), 1, ["Q3"])
    f.set(BASE.replace(said + "\n\n", ""), [row(PAGE, BASE, said, "replaced", "## Current", hq="yes")])
    expect("the same removal marked yes passes", f.run(), 0, [])

    # Q4: a rewrite of his quoted words with no "aiMyth's wording".
    f = Fixture(root, "q4")
    plain = "A page keeps only the newest version of the phrasing (19 October 2026)."
    after = BASE.replace(said, plain)
    f.set(after, [row(PAGE, BASE, said, "replaced", "## Current", hq="yes"),
                  row(PAGE, after, plain, "rewritten", block_lines(BASE, said), lines="")])
    expect("a rewrite of a removed quotation without \"aiMyth's wording\" fails Q4", f.run(), 1,
           ["Q4"])
    marked = "aiMyth’s wording of his words of 19 October 2026: a page keeps only the newest version."
    after = BASE.replace(said, marked)
    f.set(after, [row(PAGE, BASE, said, "replaced", "## Current", hq="yes"),
                  row(PAGE, after, marked, "rewritten", sha(said)[:10], lines="")])
    expect("the rewrite marked as aiMyth's (curly apostrophe, row named by checksum) passes",
           f.run(), 0, [])
    drop = "A page keeps one version (19 October 2026)."
    after = BASE.replace(said, drop)
    f.set(after, [row(PAGE, BASE, said, "replaced", "## Current", hq="yes"),
                  row(PAGE, after, drop, "rewritten", block_lines(BASE, said), lines="")])
    expect("a rewritten block that only drops a quotation is listed, not failed", f.run(), 0, [],
           ["LISTED: Q4 LEDGER line"])
    expect("a verdict with a listed block says the swap waits on the reader's read of it", f.run(), 0,
           [], ["PASS: every leg passed, once the reader has read the 1 LISTED: Q4 block; the swap "
                "waits on that read"])

    # L1: a paragraph removed with no ledger row; a twin removed with none.
    f = Fixture(root, "l1")
    f.set(BASE.replace("The current state, said plainly.\n\n", ""))
    expect("a paragraph removed with no ledger row fails L1", f.run(), 1, ["L1"])
    expect("the same with --trial prints WOULD BLOCK and exits 0", f.run(trial=True), 0, ["L1"],
           ["TRIAL: WOULD BLOCK: L1 failed (trial: nothing is blocked"])
    f.set(BASE.replace("- A twin line.\n- A twin line.\n", "- A twin line.\n"))
    expect("one of two identical blocks removed with no row fails L1", f.run(), 1, ["L1"])
    f.set(BASE.replace(said + "\n\n", ""))
    expect("a quoted sentence dropped with no row fails L1 and Q3", f.run(), 1, ["L1", "Q3"])

    # L2: an empty replaced_by; a heading AFTER lacks; a class that stays; a move.
    status = "**Status 2026-10-01:** an older layer that a newer state replaced."
    f = Fixture(root, "l2")
    gone = BASE.replace(status + "\n\n", "")
    f.set(gone, [row(PAGE, BASE, status, "change log", "")])
    expect("a ledger row with an empty replaced_by fails L2", f.run(), 1, ["L2"])
    f.set(gone, [row(PAGE, BASE, status, "change log", "## No such heading")])
    expect("a replaced_by naming a heading AFTER lacks fails L2", f.run(), 1, ["L2"])
    f.set(gone, [row(PAGE, BASE, status, "change log", "[[other#No such heading]]")])
    expect("a replaced_by naming a heading another page lacks fails L2", f.run(), 1, ["L2"])
    f.set(gone, [row(PAGE, BASE, status, "open", "## Current")])
    expect("a removed block of a class that stays fails L2", f.run(), 1, ["L2"])
    f.set(gone, [row(PAGE, BASE, status, "reason", "## Current")])
    expect("a reason removed whole, no rewrite naming it, fails L2 (a reason stays)", f.run(), 1, ["L2"])
    f.set(gone, [row(PAGE, BASE, status, "settled", "## Current")])
    expect("a settled block removed whole, no rewrite naming it, fails L2 (it is trimmed)", f.run(), 1,
           ["L2"])
    f.set(gone, [row(PAGE, BASE, status, "change log", "## Current",
                     lines=block_lines(BASE, status) + "", ).replace(sha(status), sha("x"))])
    expect("a row whose checksum is no block of BEFORE fails L2 (and L1)", f.run(), 1, ["L1", "L2"])
    para = "A paragraph under a heading the clean removes."
    moved = BASE.replace("## Old heading\n\n" + para + "\n\n", "")
    f.set(moved, [row(PAGE, BASE, "## Old heading", "replaced", "## Current"),
                  row(PAGE, BASE, para, "moved", "wiki/developments/dest.md")])
    expect("a block moved byte for byte to its destination passes", f.run(), 0, [])
    f.set(moved, [row(PAGE, BASE, "## Old heading", "replaced", "## Current"),
                  row(PAGE, BASE, para, "moved", "wiki/developments/other.md")])
    expect("a moved block missing from its destination fails L2", f.run(), 1, ["L2"])
    cand = os.path.join(f.dir, "dest-candidate.md")
    f.write(cand, "## Moved here\n\n" + para + "\n")
    f.set(moved, [row(PAGE, BASE, "## Old heading", "replaced", "## Current"),
                  row(PAGE, BASE, para, "moved", "wiki/developments/new.md")])
    expect("a move to a destination no file holds fails L2 (cannot decide)", f.run(), 1, ["L2"])
    expect("the same move read from --dest passes", f.run("--dest", "wiki/developments/new.md=" + cand),
           0, [])
    run_of = status + "\n\n" + said
    f.set(BASE.replace(run_of + "\n\n", ""),
          [row(PAGE, BASE, run_of, "replaced", "## Current", hq="yes")])
    expect("one row covering a run of two whole blocks passes", f.run(), 0, [])

    # The cleaners' own ledger shapes, which the method allows.
    f = Fixture(root, "shapes")
    gone = BASE.replace(status + "\n\n", "")
    f.set(gone, [row(PAGE, BASE, status, "change log", "## Current",
                     held="page.hold-2026-11-21.md (filed copy; the lead names commit 3aa10355)")])
    expect("a held cell naming the filed copy with a bracket beside it passes G1", f.run(), 0, [])
    f.set(gone, [row(PAGE, BASE, status, "change log", "## Current; the status it carried is the "
                     "current text")])
    expect("a replaced_by opening with a heading AFTER has, then a reason, passes L2", f.run(), 0, [])
    f.set(gone, [row(PAGE, BASE, status, "change log", "## Currently absent; a reason")])
    expect("a replaced_by opening with a heading AFTER lacks fails L2", f.run(), 1, ["L2"])
    f.set(gone, [row(PAGE, BASE, status, "merged", "## Current")])
    expect("a merged row for the removed side of a merge (a block of BEFORE) passes", f.run(), 0, [])
    f.set(gone, [row(PAGE, BASE, status, "merged", "")])
    expect("the same with an empty replaced_by fails L2", f.run(), 1, ["L2"])
    alone = "The current state, said plainly, standing alone."
    after = BASE.replace("The current state, said plainly.", alone)
    f.set(after, [row(PAGE, BASE, "The current state, said plainly.", "current", "rewritten to "
                      "stand alone"),
                  row(PAGE, after, alone, "rewritten", "from rows: L" +
                      block_lines(BASE, "The current state, said plainly."), lines="")])
    expect("a current block rewritten to stand alone, its rewrite naming it, passes", f.run(), 0, [])
    f.set(after, [row(PAGE, BASE, "The current state, said plainly.", "settled", "trimmed to its "
                      "outcome"),
                  row(PAGE, after, alone, "rewritten", "from rows: L" +
                      block_lines(BASE, "The current state, said plainly."), lines="")])
    expect("a settled block trimmed, its rewrite naming it, passes", f.run(), 0, [])
    f.set(after, [row(PAGE, BASE, "The current state, said plainly.", "current", "rewritten"),
                  row(PAGE, after, alone, "rewritten", "## Current", lines="")])
    expect("the same with a rewrite that names no source fails L2", f.run(), 1, ["L2"])

    # L3: a new block with no row.
    f = Fixture(root, "l3")
    f.set(BASE.replace("## Current\n", "## Current\n\nA sentence nobody accounted for.\n"))
    expect("a new block with no rewritten or merged row fails L3", f.run(), 1, ["L3"])

    # S1: frontmatter, required sections, the page's own links.
    f = Fixture(root, "s1")
    f.set(BASE.replace("confidence: medium", "confidence: high"))
    expect("a frontmatter field other than updated, audited or sources changed fails S1", f.run(),
           1, ["S1"])
    f.set(BASE.replace("sources: [a.md, b.md]", "sources: [a.md, b.md, c.md]"))
    expect("sources gaining an entry fails S1", f.run(), 1, ["S1"])
    f.set(BASE.replace("title: Page\n", "title: [unclosed\n"))
    expect("a frontmatter that does not parse fails S1", f.run(), 1, ["S1"])
    f.set(BASE.replace("## Sources Used\n\n- a.md\n", ""),
          [row(PAGE, BASE, "## Sources Used", "replaced", "## Current"),
           row(PAGE, BASE, "- a.md", "replaced", "## Current")])
    expect("a required section removed fails S1", f.run(), 1, ["S1"])
    f.set(BASE.replace("## Current\n", "## Now\n"),
          [row(PAGE, BASE, "## Current", "replaced", "## Now"),
           row(PAGE, BASE.replace("## Current\n", "## Now\n"), "## Now", "rewritten",
               block_lines(BASE, "## Current"), lines="")])
    expect("a link to its own heading that no longer resolves fails S1", f.run(), 1, ["S1"])

    # G1: the live page changed; a row naming another hold or page; a commit hold.
    f = Fixture(root, "g1")
    f.set(BASE)
    f.write(os.path.join(f.dir, PAGE), BASE + "\nA line another writer added.\n")
    expect("a live page changed since the hold fails G1", f.run(), 1, ["G1"],
           ["the live page changed since the hold"])
    f.write(os.path.join(f.dir, PAGE), BASE.replace("plainly", "plainly now"))
    f.set(BASE.replace("plainly", "plainly now"),
          [row(PAGE, BASE, "The current state, said plainly.", "replaced", "## Current"),
           row(PAGE, BASE.replace("plainly", "plainly now"), "The current state, said plainly now.",
               "rewritten", block_lines(BASE, "The current state, said plainly."), lines="")])
    expect("a live page that already holds the candidate fails G1 and says the swap is done",
           f.run(), 1, ["G1"], ["the live page already holds the candidate"])
    f = Fixture(root, "g1-rows")
    gone = BASE.replace(status + "\n\n", "")
    f.set(gone, [row(PAGE, BASE, status, "change log", "## Current", held="other.hold.md")])
    expect("a row naming another hold fails G1", f.run(), 1, ["G1"])
    f.set(gone, [row("wiki/developments/else.md", BASE, status, "change log", "## Current")])
    expect("a row naming another page fails G1", f.run(), 1, ["G1"])
    f.write(f.hold, BASE.replace("plainly", "plainly!"))
    f.set(BASE)
    expect("a filed hold that is not BEFORE fails G1", f.run(), 1, ["G1"])

    g = Fixture(root, "commit")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
           "-c", "commit.gpgsign=false", "-C", g.dir]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "wiki"], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "hold"], check=True)
    commit = subprocess.run(git + ["rev-parse", "--short=8", "HEAD"], stdout=subprocess.PIPE,
                            check=True).stdout.decode().strip()
    gone = BASE.replace(status + "\n\n", "")
    g.set(gone, [row(PAGE, BASE, status, "change log", "## Current", held=commit)])
    expect("a commit hold that has the page passes G1", g.run(hold=commit), 0, [])
    g.page = "wiki/developments/other.md"
    expect("a commit hold that lacks BEFORE's text fails G1",
           g.run(hold=commit), 1, ["G1"])
    g.page = PAGE
    other = Fixture(root, "commit-missing")
    other.set(BASE)
    expect("a commit that does not have the page prints PROBE FAILED", other.run(hold="0123abcd"),
           2, [], ["PROBE FAILED: the hold 0123abcd does not have the page"])

    # The broken premises.
    f = Fixture(root, "premises")
    f.set(BASE)
    os.remove(os.path.join(f.clean, "BEFORE.md"))
    expect("a missing BEFORE prints PROBE FAILED", f.run(), 2, [], ["PROBE FAILED: BEFORE is missing"])
    expect("a missing BEFORE prints PROBE FAILED in trial too", f.run(trial=True), 2, [],
           ["PROBE FAILED"])
    f.write(os.path.join(f.clean, "BEFORE.md"), "")
    expect("an empty BEFORE prints PROBE FAILED", f.run(), 2, [], ["PROBE FAILED: BEFORE is empty"])
    f.write(os.path.join(f.clean, "BEFORE.md"), BASE)
    f.write(os.path.join(f.clean, "LEDGER.tsv"), "wiki/developments/page.md\t1\tfive\tcells\tonly\n")
    expect("a ledger row of five cells prints PROBE FAILED", f.run(), 2, [],
           ["PROBE FAILED: LEDGER line 1 has 5 cells"])
    f.write(os.path.join(f.clean, "LEDGER.tsv"), b"\xff\xfe not utf-8\n", binary=True)
    expect("a ledger that is not UTF-8 prints PROBE FAILED", f.run(), 2, [], ["PROBE FAILED"])
    f.write(os.path.join(f.clean, "LEDGER.tsv"),
            HEADER + "\n" + row(PAGE, BASE, status, "change log", "## Current", hq="maybe") + "\n")
    expect("a held_quotation cell that is not yes or no prints PROBE FAILED", f.run(), 2, [],
           ["PROBE FAILED"])
    f.write(os.path.join(f.clean, "LEDGER.tsv"), "page\tlines\tsha\n")
    expect("a ledger header that is not the nine columns prints PROBE FAILED", f.run(), 2, [],
           ["PROBE FAILED: the LEDGER's header"])
    f.set(BASE)
    expect("a filed hold that does not exist prints PROBE FAILED",
           f.run(hold=os.path.join(f.clean, "absent.hold.md")), 2, [],
           ["PROBE FAILED: the hold does not have the page"])
    os.remove(os.path.join(f.dir, PAGE))
    expect("a missing live page prints PROBE FAILED", f.run(), 2, [], ["PROBE FAILED: no live page"])
    f.write(os.path.join(f.dir, PAGE), BASE)
    os.remove(os.path.join(f.clean, "AFTER.md"))
    expect("a missing AFTER prints PROBE FAILED", f.run(), 2, [], ["PROBE FAILED: AFTER is missing"])
    f.set(BASE)
    os.remove(os.path.join(f.clean, "LEDGER.tsv"))
    expect("a missing LEDGER prints PROBE FAILED", f.run(), 2, [],
           ["PROBE FAILED: the LEDGER is missing"])
    f.set(BASE)
    f.write(os.path.join(f.clean, "AFTER.md"), b"\xff\xfe not utf-8\n", binary=True)
    expect("an AFTER that is not UTF-8 prints PROBE FAILED", f.run(), 2, [],
           ["PROBE FAILED: AFTER cannot be read as UTF-8"])
    f.set(BASE)
    f.write(os.path.join(f.dir, PAGE), b"\xff\xfe not utf-8\n", binary=True)
    expect("a live page that is not UTF-8 prints PROBE FAILED", f.run(), 2, [],
           ["PROBE FAILED: the live page cannot be read as UTF-8"])
    f.write(os.path.join(f.dir, PAGE), BASE)

    # E2: a lessons page.
    e = Fixture(root, "e2", page=LESSONS, before=LESSONS_BASE)
    lesson = "E2. A lesson whose bracket tells its history. (lesson · 2026-11-08 · a round; widened on 2026-11-09 by run x)"
    trimmed = "E2. A lesson whose bracket tells its history. (lesson · 2026-11-08 · a round)"
    after = LESSONS_BASE.replace(lesson, trimmed)
    lrow = lambda text, block, cls, rb, lines=None: row(LESSONS, text, block, cls, rb,
                                                        held="page.hold-2026-11-21.md", lines=lines)
    e.set(after, [lrow(LESSONS_BASE, lesson, "change log", "## Rules"),
                  lrow(after, trimmed, "rewritten", block_lines(LESSONS_BASE, lesson), lines="")])
    expect("a lesson entry's history trimmed from its bracket passes E2", e.run(), 0, [])
    owner = "E1. An owner rule, kept as written. (owner · 2026-11-07 · his word)"
    owner2 = owner.replace("kept as written", "kept as writen")
    after = LESSONS_BASE.replace(owner, owner2)
    e.set(after, [lrow(LESSONS_BASE, owner, "replaced", "## Rules"),
                  lrow(after, owner2, "rewritten", block_lines(LESSONS_BASE, owner), lines="")])
    expect("an owner entry line altered fails E2", e.run(), 1, ["E2"])
    third = "E3. A second owner rule. (owner · 2026-11-08 · his word)"
    after = LESSONS_BASE.replace(third + "\n", "")
    e.write(os.path.join(e.wiki, "experience", "elsewhere.md"),
            "---\ntitle: Elsewhere\ntype: synthesis\n---\n\n## Rules\n" + third + "\n")
    e.set(after, [lrow(LESSONS_BASE, third, "moved", "wiki/experience/elsewhere.md")])
    expect("an owner entry moved whole to another lessons page passes E2", e.run(), 0, [])
    reuse = after.replace("## Sources Used", "E3. A new entry under an old label. (lesson · 2026-11-21 · x)\n\n## Sources Used")
    e.set(reuse, [lrow(LESSONS_BASE, third, "moved", "wiki/experience/elsewhere.md"),
                  lrow(reuse, "E3. A new entry under an old label. (lesson · 2026-11-21 · x)",
                       "merged", block_lines(LESSONS_BASE, third), lines="")])
    expect("the label of a moved owner entry reused fails E2", e.run(), 1, ["E2"])
    twice = LESSONS_BASE.replace(lesson, trimmed + "\n" + trimmed.replace("E2.", "E2.") + " again")
    e.set(twice)
    out = e.run()[1]
    record("a label standing twice in AFTER fails E2", "the label E2 stands 2 times" in out, out[-800:])

    # The source: no call that writes, removes or renames a file; no owner path, name or run id. Each
    # search has its positive control. "aiMyth's wording" is the design's marker, and aiMyth is the
    # agent name the shipped setup seeds, which the publish guard reads as identifying nobody.
    with open(CHECK, encoding="utf-8") as handle:
        source = handle.read()
    code = source.split('"""', 2)[2]
    writers = re.findall(r"open\([^)]*[\"'](?:w|a|x|r\+|w\+|a\+)b?[\"']|os\.(?:remove|unlink|rename|"
                         r"replace|rmdir|makedirs|mkdir|truncate|chmod)\(|shutil\.|\.write_text\(|"
                         r"\.write_bytes\(|\.unlink\(", code)
    record("the check's source holds no call that writes, removes or renames a file", writers == [],
           str(writers))
    record("control: the same search method finds the read the source does make",
           len(re.findall(r"open\(path, \"rb\"\)", code)) == 1)
    owner = re.findall(r"/Users/|/home/[a-z]|OneDrive|[Jj]erry|" + "jer" + "ang" + r"|run-2026\d{4}|HD-\d+", source)
    record("the check's source holds no owner path, name, run id or decision id", owner == [], str(owner))
    record("control: the same search finds a word the source does hold",
           len(re.findall(r"PROBE FAILED", source)) >= 3)

    # The last leg: no run of the check changed a file, and the manifest catches a changed byte.
    changed_runs = [folder for folder, same in RUNS if not same]
    record("every one of the %d runs left its fixture folder byte-identical" % len(RUNS),
           not changed_runs and len(RUNS) >= 40, "changed: %s" % changed_runs)
    folder = os.path.join(root, "identity")
    seen = manifest(folder)
    victim = os.path.join(folder, "clean", "AFTER.md")
    with open(victim, "r+b") as handle:
        first = handle.read(1)
        handle.seek(0)
        handle.write(bytes([first[0] ^ 1]))
    record("control: one byte changed in a fixture folder, same permissions, is caught by the "
           "manifest", manifest(folder) != seen)

if __name__ == "__main__":
    sys.exit(main())
