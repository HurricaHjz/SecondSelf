#!/usr/bin/env python3
"""bulk-clean-check.py: the program check of a whole-page clean, run before the swap.

It reads three things: BEFORE (the page as the hold has it), AFTER (the cleaned candidate) and the
LEDGER (one tab-separated row for every block of BEFORE that is not byte for byte in AFTER, in the
nine columns of the clean method). It passes only if every leg passes. It is stdout-only: it builds
nothing, changes nothing and writes no file. The one command it runs is `git show`, read-only, and
only where the hold is a commit.

Usage
  bulk-clean-check.py --page wiki/REL.md --wiki DIR --hold HOLD
                      (--dir DIR | --before FILE --after FILE --ledger FILE)
                      [--dest wiki/REL.md=FILE ...] [--trial]

  --page    the page's path from the vault root; it starts `wiki/`, and every ledger row names it.
  --wiki    the vault's wiki folder: the live page (G1), a commit hold (read with git from the
            page's own folder), a move's destination and other pages' links are read there.
  --hold    a commit (7 to 40 hex characters) or the path of the filed copy. Every row's `held`
            cell names it.
  --dir     a clean's folder holding BEFORE.md, AFTER.md and LEDGER.tsv.
  --dest    read a move's destination page from FILE (a candidate not yet swapped in).
  --trial   the check's trial: a failed leg prints WOULD BLOCK and exits 0, so nothing is blocked;
            whoever runs the clean reads the output and decides the swap.

Blocks. A block is a paragraph, a list item, a table row, a heading, a quotation block (consecutive
lines opening with `>`) or a fenced code block, as the clean method counts them. A wiki page writes
one line per paragraph or list item (the schema's line discipline), so each such line is a block,
and a lessons page's entry lines, which stand with no blank line between them, are a block each. The frontmatter is no block: S1 reads it. A block's checksum is the sha256 of its lines
joined by a line break, with no line break at its end (a checksum of the same text with one line
break at its end is accepted too). A ledger row may also cover a run of whole blocks: its `lines`
cell (`N` or `N-M`, in BEFORE) then names the run, and its checksum is of those lines as they stand.
A `rewritten` or `merged` row is a block of AFTER; its `replaced_by` names the rows it came from by
their `lines` cells, by lines of BEFORE, or by the first 8 or more characters of their checksums.

The legs (the clean method, section 6; leg E1, a register move, is a stopped part and is not built)
  G1  the hold has BEFORE's checksum; the live page still has it; every row names this page and
      this hold.
  Q1  every quotation block of AFTER is byte for byte a quotation block of BEFORE.
  Q2  every string of four or more words inside double quotation marks in AFTER, straight or curly,
      stands byte for byte inside quotation marks in BEFORE (the words between the marks are
      compared; code spans and fences are not read for quotations).
  Q3  every removed block holding a quotation block or such a string lies in a row marked
      `held_quotation: yes`, and every row whose blocks hold either is marked so.
  Q4  a `rewritten` or `merged` block that comes from blocks holding a quotation, and no longer
      holds it, carries the words "aiMyth's wording" or is listed as a pure drop (`LISTED: Q4`)
      for the reviewer, who reads each one. A block that still carries four or more words of the
      lost quotation in a row, outside quotation marks, restates it, and without the words fails.
  L1  every block of BEFORE is in AFTER, or lies in a ledger row (counted occurrence by occurrence,
      so a duplicate block removed is not hidden by its twin).
  L2  every row's checksum is a block (or a run of whole blocks) of BEFORE; its `class` is known and
      is no class that stays (`reason` and `settled` among them) unless a `rewritten` or `merged`
      row names it as its source; its `replaced_by` is filled, a heading it names exists in AFTER (or on
      the page it links to), a `rewritten` or `merged` row names rows that exist, and a `moved`
      block is byte for byte in its destination.
  L3  every block of AFTER that is not in BEFORE is a `rewritten` or `merged` row; the bytes added
      and removed are printed.
  S1  AFTER's frontmatter parses; no field but `updated:`, `audited:` and `sources:` changed, and
      `sources:` gained no entry (the clean method, section 4); a required section BEFORE had is
      still there; every link to one of its own headings resolves. Links from other pages to a
      heading it lost are listed, and list only.
  E2  on a lessons page (`wiki/experience/`): every `owner` entry line of BEFORE is byte for byte in
      AFTER, or on another lessons page; no label stands twice in AFTER, and the label of an
      `owner` entry moved away is not reused.

Premises. A missing or empty BEFORE, a missing AFTER or LEDGER, a file that is not UTF-8, a ledger
row that is not nine cells (or whose checksum or `held_quotation` cell is malformed), a hold that
does not have the page, a missing live page, PyYAML not importable, or the in-memory control off:
PROBE FAILED, exit 2, in both modes. When a leg cannot decide (a destination it cannot read), it
fails and says why.

Exit codes
  0  every leg passed; with --trial, the check ran to its verdict, whatever the verdict
  1  a leg failed: the swap is blocked (never with --trial)
  2  PROBE FAILED: the check could not run, and that is never read as a pass
"""

import argparse
import collections
import hashlib
import os
import re
import subprocess
import sys

COLUMNS = ("page", "lines", "first_words", "bytes", "sha256", "class", "replaced_by",
           "held_quotation", "held")
NEW_CLASSES = ("rewritten", "merged")
# The clean method's section 2 table: these classes stay on the page (a reason stays, a settled
# block is trimmed), so a row that removes one passes only as the source of a rewritten or merged row.
STAY_CLASSES = ("current", "note drawn on", "open", "unsure", "reason", "settled")
REMOVE_CLASSES = ("replaced", "change log", "note not drawn on", "expired", "moved")
# CLAUDE.md section 4.3 as lint/check-required-sections.py applies it (its REQUIRED table).
REQUIRED = {
    "concept": ("Related",), "entity": ("Related",), "tool": ("Related",),
    "model": ("Appears in",), "benchmark": ("Appears in",),
    "source": ("Summary", "Key Takeaways", "Related"),
    "synthesis": ("Sources Used",), "development": ("Sources Used",),
}
FREE_FIELDS = ("updated", "audited", "sources")
MARK = re.compile(r"aiMyth['’]s wording")

RE_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
RE_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
RE_QUOTE = re.compile(r"^\s*>")
RE_TABLE = re.compile(r"^\s*\|")
RE_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
RE_CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1")
RE_QUOTED = re.compile(r"\"([^\"\n]+)\"|“([^”\n]+)”")
RE_LINK = re.compile(r"\[\[([^\]\|#]*)#([^\]\|]+)(?:\|[^\]]*)?\]\]")
RE_LINES = re.compile(r"^\s*(\d+)\s*(?:[-–]\s*(\d+))?\s*$")
RE_LINE_TOKEN = re.compile(r"(?<![0-9a-fA-F])(\d+)(?:\s*[-–]\s*(\d+))?(?![0-9a-fA-F])")
RE_HEX_TOKEN = re.compile(r"\b([0-9a-f]{8,64})\b")
RE_ENTRY = re.compile(r"^([A-Z][A-Za-z]*\d+[a-z]?)\.\s")
RE_KIND = re.compile(r"\((owner|lesson)\s*·")
RE_DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2} [A-Z][a-z]+ \d{4}")
RE_WORD = re.compile(r"[\w’']+")
RESTATE_RUN = 4    # words in a row that make a restatement, as Q2's four; set by judgement, unmeasured


def restates(quotation, text):
    """True when `text`, outside its quotation marks and code spans, carries RESTATE_RUN or more
    words of `quotation` in a row (case aside)."""
    said = [w.lower() for w in RE_WORD.findall(quotation)]
    plain = " %s " % " ".join(w.lower() for w in RE_WORD.findall(RE_QUOTED.sub(" ", RE_CODE_SPAN.sub(" ", text))))
    return any(" %s " % " ".join(said[i:i + RESTATE_RUN]) in plain
               for i in range(len(said) - RESTATE_RUN + 1))


class ProbeFailed(Exception):
    pass


Block = collections.namedtuple("Block", "kind start end text")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def norm_heading(text):
    """A heading as a link names it: case, runs of spaces and the kind of dash are not compared."""
    return re.sub(r"\s+", " ", re.sub(r"\s[—–-]\s", " — ", text.strip().lower()))


def split_page(text):
    """(frontmatter text or None, frontmatter's last line number, body blocks)."""
    lines = text.split("\n")
    front, start = None, 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                front, start = "\n".join(lines[1:i]) + "\n", i + 1
                break
    blocks = []
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        first = i
        fence = RE_FENCE.match(line)
        if fence:
            mark = fence.group(1)
            i += 1
            while i < len(lines):
                close = RE_FENCE.match(lines[i])
                i += 1
                if close and close.group(1)[0] == mark[0] and len(close.group(1)) >= len(mark):
                    break
            kind = "code"
        elif RE_HEADING.match(line):
            i += 1
            kind = "heading"
        elif RE_QUOTE.match(line):
            while i < len(lines) and lines[i].strip() and RE_QUOTE.match(lines[i]):
                i += 1
            kind = "quote"
        elif RE_TABLE.match(line):
            i += 1
            kind = "row"
        else:
            # One line per paragraph or list item (the schema's line discipline: the renderer
            # breaks on every newline), so each such line is a block of its own.
            kind = "item" if RE_ITEM.match(line) else "para"
            i += 1
        blocks.append(Block(kind, first + 1, i, "\n".join(lines[first:i])))
    return front, start, blocks, lines


def quoted_strings(block):
    """The strings of four or more words inside double quotation marks in a block."""
    if block.kind == "code":
        return []
    found = []
    for line in block.text.split("\n"):
        plain = RE_CODE_SPAN.sub(" ", line)
        for m in RE_QUOTED.finditer(plain):
            inner = m.group(1) if m.group(1) is not None else m.group(2)
            if len(inner.split()) >= 4:
                found.append(inner)
    return found


def quotations(block):
    """What a block holds that Q3 and Q4 guard: the quotation block itself, and its quoted strings."""
    held = [block.text] if block.kind == "quote" else []
    return held + quoted_strings(block)


def headings(blocks):
    return {norm_heading(RE_HEADING.match(b.text).group(2)) for b in blocks if b.kind == "heading"}


def read_text(path, what):
    if not path or not os.path.isfile(path):
        raise ProbeFailed("%s is missing: %s" % (what, path))
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
        return raw, raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ProbeFailed("%s cannot be read as UTF-8 (%s): %s" % (what, error, path))


def read_ledger(path):
    _raw, text = read_text(path, "the LEDGER")
    rows = []
    lines = [(n + 1, line.rstrip("\r")) for n, line in enumerate(text.split("\n"))]
    lines = [(n, line) for n, line in lines if line.strip()]
    if lines and lines[0][1].split("\t")[0].strip().lower() == "page":
        header = [re.sub(r"[\s-]+", "_", cell.strip().lower()) for cell in lines[0][1].split("\t")]
        if tuple(header) != COLUMNS:
            raise ProbeFailed("the LEDGER's header is not the method's nine columns (%s): %s"
                              % (" · ".join(COLUMNS), " · ".join(header)))
        lines = lines[1:]
    for number, line in lines:
        cells = line.split("\t")
        if len(cells) != len(COLUMNS):
            raise ProbeFailed("LEDGER line %d has %d cells, not %d: the ledger is unreadable"
                              % (number, len(cells), len(COLUMNS)))
        row = dict(zip(COLUMNS, (cell.strip() for cell in cells)))
        row["number"] = number
        row["sha256"] = row["sha256"].lower()
        if not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ProbeFailed("LEDGER line %d: the sha256 cell is no checksum: %r"
                              % (number, row["sha256"]))
        row["held_quotation"] = row["held_quotation"].lower()
        if row["held_quotation"] not in ("yes", "no"):
            raise ProbeFailed("LEDGER line %d: held_quotation is %r, not yes or no"
                              % (number, row["held_quotation"]))
        row["class"] = re.sub(r"[\s_-]+", " ", row["class"].lower())
        rows.append(row)
    return rows


def span_of(lines_cell, blocks, all_lines, checksum):
    """The indices of the whole blocks that lines N-M cover, when those lines hold the checksum."""
    m = RE_LINES.match(lines_cell or "")
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2) or m.group(1))
    starts = {blk.start: k for k, blk in enumerate(blocks)}
    ends = {blk.end: k for k, blk in enumerate(blocks)}
    if a not in starts or b not in ends or starts[a] > ends[b]:
        return None
    text = "\n".join(all_lines[a - 1:b])
    if checksum not in (sha(text), sha(text + "\n")):
        return None
    return list(range(starts[a], ends[b] + 1))


def locate(rows, blocks, all_lines):
    """Each row's block indices, by its lines cell first and then by its checksum alone."""
    by_sha = collections.defaultdict(list)
    for k, blk in enumerate(blocks):
        by_sha[sha(blk.text)].append(k)
        by_sha[sha(blk.text + "\n")].append(k)
    claimed = set()
    found = {}
    for row in rows:
        span = span_of(row["lines"], blocks, all_lines, row["sha256"])
        if span is None:
            free = [k for k in by_sha.get(row["sha256"], []) if k not in claimed]
            span = [free[0]] if free else None
        if span is not None:
            claimed.update(span)
        found[row["number"]] = span
    return found


def sources_of(row, removal, r_span, b_blocks):
    """The BEFORE blocks a rewritten or merged row came from: its replaced_by names them by lines
    (`12-14`, `L39`) or by the first 8 or more characters of a removed row's checksum."""
    found = set()
    cell = RE_HEX_TOKEN.sub(" ", RE_DATE.sub(" ", row["replaced_by"]).lower())
    for a, b in line_tokens(cell):
        found.update(k for k, blk in enumerate(b_blocks) if blk.start <= b and blk.end >= a)
    for prefix in RE_HEX_TOKEN.findall(row["replaced_by"].lower()):
        for other in removal:
            if other["sha256"].startswith(prefix):
                found.update(r_span[other["number"]] or [])
    return found


def names_heading(text, heads):
    """A replaced_by such as `### Heading; why` names the heading it opens with."""
    want = norm_heading(text)
    return any(want == h or (want.startswith(h) and not want[len(h)].isalnum()) for h in heads)


def line_tokens(cell):
    return [(int(a), int(b or a)) for a, b in RE_LINE_TOKEN.findall(cell)]


def first_words(text, n=12):
    return " ".join(text.split()[:n])


def git_show(wiki, page_rel, commit):
    folder = os.path.join(wiki, os.path.dirname(page_rel))
    name = os.path.basename(page_rel)
    if not os.path.isdir(folder):
        raise ProbeFailed("the page's folder is not under the wiki: %s" % folder)
    try:
        done = subprocess.run(["git", "-C", folder, "show", "%s:./%s" % (commit, name)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as error:
        raise ProbeFailed("git cannot be run (%s): the commit hold cannot be read" % error)
    if done.returncode != 0:
        raise ProbeFailed("the hold %s does not have the page %s: %s"
                          % (commit, page_rel, done.stderr.decode("utf-8", "replace").strip()))
    return done.stdout


def wiki_pages(wiki):
    for folder, _dirs, files in os.walk(wiki):
        for name in sorted(files):
            if name.endswith(".md"):
                yield os.path.join(folder, name)


def load_yaml():
    try:
        import yaml
    except Exception as error:
        raise ProbeFailed("PyYAML cannot be imported by %s (%s): S1 has no other reader"
                          % (sys.executable, error))
    return yaml


def parse_front(yaml, front):
    try:
        value = yaml.load(front, Loader=yaml.BaseLoader)
    except Exception as error:
        return None, "does not parse (%s)" % str(error).split("\n")[0]
    if not isinstance(value, dict):
        return None, "is not a mapping"
    return value, None


def as_list(value):
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def check(args, hold_name, hold_raw, live_raw, before_raw, before, after, rows, yaml):
    """The legs, as {leg: [failure lines]}, with the notes and listings printed beside them.
    args.wiki may be None (the in-memory control): what needs other pages is then not read."""
    page = args.page
    stem = os.path.splitext(os.path.basename(page))[0].lower()
    fails = collections.OrderedDict((leg, []) for leg in
                                    ("G1", "Q1", "Q2", "Q3", "Q4", "L1", "L2", "L3", "S1", "E2"))
    notes = []
    b_front, _b_start, b_blocks, b_lines = split_page(before)
    a_front, _a_start, a_blocks, a_lines = split_page(after)

    # G1: the hold, the live page, and every row's page and hold.
    before_sha = hashlib.sha256(before_raw).hexdigest()
    if hashlib.sha256(hold_raw).hexdigest() != before_sha:
        fails["G1"].append("the hold (%s) does not have BEFORE's checksum %s: the ledger was "
                           "written against another version" % (hold_name, before_sha[:12]))
    live_sha = hashlib.sha256(live_raw).hexdigest()
    if live_sha == hashlib.sha256(after.encode("utf-8")).hexdigest() and live_sha != before_sha:
        fails["G1"].append("the live page already holds the candidate (%s): the swap is done, and "
                           "G1 reads the page before a swap" % live_sha[:12])
    elif live_sha != before_sha:
        fails["G1"].append("the live page changed since the hold (%s, not %s): cut the clean "
                           "again from the changed page" % (live_sha[:12], before_sha[:12]))
    for row in rows:
        if row["page"].lstrip("./") != page:
            fails["G1"].append("LEDGER line %d names the page %r, not %s"
                               % (row["number"], row["page"], page))
        held = row["held"]
        # The cell names the hold when it holds the commit (either hash a prefix of the other) or
        # the filed copy's name; words beside it (the method's cleaners add a bracket) are allowed.
        if hold_name.startswith("commit"):
            ok = any(t.startswith(args.hold.lower()) or args.hold.lower().startswith(t)
                     for t in re.findall(r"\b[0-9a-f]{7,40}\b", held.lower()))
        else:
            ok = os.path.basename(args.hold) in held
        if not ok:
            fails["G1"].append("LEDGER line %d names the hold %r, not the %s"
                               % (row["number"], held, hold_name))

    # A rewritten or merged row is the new block (in AFTER) or, as the method's worked example
    # writes a moved quotation, the removed side of a merge (in BEFORE): AFTER is tried first.
    a_found = locate([r for r in rows if r["class"] in NEW_CLASSES], a_blocks, a_lines)
    new = [r for r in rows if r["class"] in NEW_CLASSES and a_found[r["number"]] is not None]
    n_span = {r["number"]: a_found[r["number"]] for r in new}
    removal = [r for r in rows if r not in new]
    r_span = locate(removal, b_blocks, b_lines)
    sources = {r["number"]: sources_of(r, removal, r_span, b_blocks) for r in new}
    rewritten_from = set().union(*sources.values()) if sources else set()
    covered = collections.Counter()
    covered_by = {}
    for row in removal:
        for k in r_span[row["number"]] or []:
            covered[b_blocks[k].text] += 1
            covered_by.setdefault(k, row)
    count_b = collections.Counter(b.text for b in b_blocks)
    count_a = collections.Counter(b.text for b in a_blocks)

    # L1: every block of BEFORE in AFTER, or in a row, occurrence by occurrence.
    uncovered = []
    for text, n in count_b.items():
        missing = n - count_a.get(text, 0)
        if missing > covered.get(text, 0):
            spots = [b for k, b in enumerate(b_blocks) if b.text == text and k not in covered_by]
            for blk in spots[:missing - covered.get(text, 0)]:
                uncovered.append(blk)
                fails["L1"].append("BEFORE lines %d-%d (%s, %d bytes) are not in AFTER and lie in "
                                   "no ledger row: \"%s\"" % (blk.start, blk.end, blk.kind,
                                                             len(blk.text.encode()),
                                                             first_words(blk.text)))

    # L2: every row a block of BEFORE, a known class, a filled replaced_by that resolves.
    a_heads = headings(a_blocks)
    for row in rows:
        where = "LEDGER line %d (%s, lines %s)" % (row["number"], row["class"], row["lines"] or "-")
        if row["class"] not in NEW_CLASSES + STAY_CLASSES + REMOVE_CLASSES:
            fails["L2"].append("%s: the class is none of the method's: %r" % (where, row["class"]))
        if not row["replaced_by"]:
            fails["L2"].append("%s: replaced_by is empty" % where)
            continue
        if row in new:
            continue
        span = r_span[row["number"]]
        if span is None:
            fails["L2"].append("%s: its checksum %s is no block of BEFORE%s, nor the text of its "
                               "lines" % (where, row["sha256"][:12],
                                          " or of AFTER" if row["class"] in NEW_CLASSES else ""))
            continue
        # A block of a class that stays may leave only as the source of a rewrite (rewritten to
        # stand alone, the clean method's section 3); otherwise its removal contradicts its class.
        if row["class"] in STAY_CLASSES and not set(span) <= rewritten_from:
            fails["L2"].append("%s: a block of a class that stays is removed, and no rewritten or "
                               "merged row names it as its source" % where)
        text = "\n".join(b_blocks[k].text for k in span)
        if row["class"] == "moved":
            dest = destination(args, row["replaced_by"])
            if dest is None:
                fails["L2"].append("%s: the move's destination %r cannot be read, so the move "
                                   "cannot be checked" % (where, row["replaced_by"]))
            elif any(b_blocks[k].text not in dest for k in span):
                fails["L2"].append("%s: the moved block is not byte for byte in %s"
                                   % (where, row["replaced_by"]))
            continue
        for target, heading in RE_LINK.findall(row["replaced_by"]):
            target = target.strip()
            if not target or target.lower() == stem:
                if norm_heading(heading) not in a_heads:
                    fails["L2"].append("%s: replaced_by names the heading %r, which AFTER lacks"
                                       % (where, heading))
            else:
                other = find_page(args.wiki, target)
                if other is None:
                    fails["L2"].append("%s: replaced_by links to %r, no page of the wiki"
                                       % (where, target))
                elif norm_heading(heading) not in headings(split_page(other)[2]):
                    fails["L2"].append("%s: replaced_by names the heading %r, which %s lacks"
                                       % (where, heading, target))
        m = re.match(r"^#+\s*(.+)$", row["replaced_by"])
        if m and not names_heading(m.group(1), a_heads):
            fails["L2"].append("%s: replaced_by names the heading %r, which AFTER lacks"
                               % (where, m.group(1)))
        if row["class"] == "expired" and not RE_DATE.search(row["replaced_by"]):
            notes.append("%s: an expired fact whose replaced_by carries no end date" % where)

    # L3: every new block of AFTER is a rewritten or merged row; the bytes either way.
    new_cover = collections.Counter()
    for row in new:
        span = n_span[row["number"]]
        if span is None:
            fails["L3"].append("LEDGER line %d (%s): its checksum %s is no block of AFTER"
                               % (row["number"], row["class"], row["sha256"][:12]))
            continue
        for k in span:
            new_cover[a_blocks[k].text] += 1
    added = removed = 0
    for text, n in count_a.items():
        extra = n - count_b.get(text, 0)
        if extra > 0:
            added += extra * len(text.encode())
            if extra > new_cover.get(text, 0):
                blk = next(b for b in a_blocks if b.text == text)
                fails["L3"].append("AFTER lines %d-%d (%s) are new and no rewritten or merged row: "
                                   "\"%s\"" % (blk.start, blk.end, blk.kind, first_words(text)))
    for text, n in count_b.items():
        removed += max(0, n - count_a.get(text, 0)) * len(text.encode())
    notes.append("L3 bytes: BEFORE %d · AFTER %d · blocks added %d bytes · blocks removed %d bytes"
                 % (len(before.encode()), len(after.encode()), added, removed))

    # Q1 and Q2: no quotation in AFTER that BEFORE does not hold byte for byte.
    b_quote_blocks = {b.text for b in b_blocks if b.kind == "quote"}
    b_strings = {s for b in b_blocks for s in quoted_strings(b)}
    for blk in a_blocks:
        if blk.kind == "quote" and blk.text not in b_quote_blocks:
            fails["Q1"].append("AFTER lines %d-%d: a quotation block that is no quotation block of "
                               "BEFORE: \"%s\"" % (blk.start, blk.end, first_words(blk.text)))
        for s in quoted_strings(blk):
            if s not in b_strings:
                fails["Q2"].append("AFTER line %d: the quoted words \"%s\" stand inside quotation "
                                   "marks nowhere in BEFORE" % (blk.start, s[:160]))

    # Q3: a removed quotation lies in a row marked yes, and every row holding one is marked so.
    for row in removal:
        span = r_span[row["number"]] or []
        if any(quotations(b_blocks[k]) for k in span) and row["held_quotation"] != "yes":
            fails["Q3"].append("LEDGER line %d (lines %s): its block holds a quotation and is "
                               "marked held_quotation: no" % (row["number"], row["lines"]))
        if span and not any(quotations(b_blocks[k]) for k in span) \
                and row["held_quotation"] == "yes":
            notes.append("LEDGER line %d is marked held_quotation: yes and its block holds no "
                         "quotation the check can see (the reviewer reads it)" % row["number"])
    for blk in uncovered:
        if quotations(blk):
            fails["Q3"].append("BEFORE lines %d-%d: a quotation dropped with no ledger row: \"%s\""
                               % (blk.start, blk.end, first_words(blk.text)))

    # Q4: a rewrite of quoted words is marked as aiMyth's.
    for row in new:
        span = n_span[row["number"]]
        new_text = "\n".join(a_blocks[k].text for k in span)
        is_new = any(count_a[a_blocks[k].text] > count_b.get(a_blocks[k].text, 0) for k in span)
        if not sources[row["number"]]:
            if is_new:
                fails["L2"].append("LEDGER line %d (%s): replaced_by %r names no row or lines of "
                                   "BEFORE it came from" % (row["number"], row["class"],
                                                            row["replaced_by"]))
            continue
        lost = [q for k in sorted(sources[row["number"]]) for q in quotations(b_blocks[k])
                if q not in new_text]
        if lost and not MARK.search(new_text):
            where = "LEDGER line %d (%s, AFTER lines %d-%d)" % (row["number"], row["class"],
                                                               a_blocks[span[0]].start, a_blocks[span[-1]].end)
            said = [q for q in lost if restates(q, new_text)]
            if said:
                fails["Q4"].append("%s: it restates quoted words it no longer holds (\"%s\") and does "
                                   "not carry \"aiMyth's wording\"" % (where, first_words(said[0])))
            else:
                notes.append("LISTED: Q4 %s drops quoted words (\"%s\") and keeps no four of their words "
                             "in a row outside quotation marks: the clean's reviewer, or with none the "
                             "session that swaps, reads it for a restatement in other words, which fails "
                             "Q4" % (where, first_words(lost[0])))

    # S1: frontmatter, required sections, the page's own links; other pages' links listed.
    if b_front is not None:
        if a_front is None:
            fails["S1"].append("AFTER has no frontmatter, and BEFORE had one")
        else:
            b_fm, _error = parse_front(yaml, b_front)
            a_fm, error = parse_front(yaml, a_front)
            if error:
                fails["S1"].append("AFTER's frontmatter %s" % error)
            elif b_fm is not None:
                for key in sorted(set(b_fm) | set(a_fm)):
                    if key not in FREE_FIELDS and b_fm.get(key) != a_fm.get(key):
                        fails["S1"].append("frontmatter field %r changed; a clean may change only "
                                           "updated, audited and sources" % key)
                gained = [s for s in as_list(a_fm.get("sources")) if s not in as_list(b_fm.get("sources"))]
                if gained:
                    fails["S1"].append("frontmatter sources gained %s; a clean only removes" % gained)
                kind = str(b_fm.get("type", "")).strip()
                b_h2 = {norm_heading(RE_HEADING.match(b.text).group(2)) for b in b_blocks
                        if b.kind == "heading" and b.text.startswith("## ")}
                a_h2 = {norm_heading(RE_HEADING.match(b.text).group(2)) for b in a_blocks
                        if b.kind == "heading" and b.text.startswith("## ")}
                for section in REQUIRED.get(kind, ()):
                    if norm_heading(section) in b_h2 and norm_heading(section) not in a_h2:
                        fails["S1"].append("the required section ## %s is gone" % section)
    for blk in a_blocks:
        if blk.kind == "code":
            continue
        for target, heading in RE_LINK.findall(RE_CODE_SPAN.sub(" ", blk.text)):
            if target.strip() and target.strip().lower() != stem:
                continue
            if heading.startswith("^"):
                ok = (" " + heading) in after or ("\n" + heading) in after
            else:
                ok = norm_heading(heading) in a_heads
            if not ok:
                fails["S1"].append("AFTER line %d: the link to its own heading %r does not resolve"
                                   % (blk.start, heading))
    lost = headings(b_blocks) - a_heads
    if lost and args.wiki is not None:
        for path in wiki_pages(args.wiki):
            rel = os.path.relpath(path, args.wiki)
            if "wiki/" + rel == page:
                continue
            try:
                with open(path, encoding="utf-8") as handle:
                    for n, line in enumerate(handle, 1):
                        for target, heading in RE_LINK.findall(line):
                            if target.strip().lower() == stem and norm_heading(heading) in lost:
                                notes.append("LISTED: wiki/%s:%d links to the heading %r that "
                                             "AFTER lost" % (rel, n, heading))
            except (OSError, UnicodeDecodeError) as error:
                notes.append("LISTED: wiki/%s could not be read for links (%s)" % (rel, error))

    # E2: a lessons page keeps every owner entry line, and reuses no label.
    if page.startswith("wiki/experience/") and args.wiki is not None:
        a_set = set(a_lines)
        others = None
        a_labels = collections.Counter(m.group(1) for m in map(RE_ENTRY.match, a_lines) if m)
        for line in b_lines:
            m = RE_ENTRY.match(line)
            kinds = RE_KIND.findall(line)
            if not m or not kinds or kinds[-1] != "owner" or line in a_set:
                continue
            if others is None:
                others = set()
                folder = os.path.join(args.wiki, "experience")
                for path in wiki_pages(folder):
                    if "wiki/" + os.path.relpath(path, args.wiki) != page:
                        others.update(read_text(path, "a lessons page")[1].split("\n"))
            if line not in others:
                fails["E2"].append("the owner entry %s is altered or gone: \"%s\""
                                   % (m.group(1), first_words(line)))
            elif a_labels.get(m.group(1)):
                fails["E2"].append("the owner entry %s moved to another lessons page and its label "
                                   "is reused here" % m.group(1))
        for label, n in a_labels.items():
            if n > 1:
                fails["E2"].append("the label %s stands %d times in AFTER" % (label, n))
    return fails, notes


def find_page(wiki, target):
    if wiki is None:
        return None
    want = target.strip().lower()
    for path in wiki_pages(wiki):
        if os.path.splitext(os.path.basename(path))[0].lower() == want:
            return read_text(path, "a linked page")[1]
    return None


def destination(args, cell):
    name = cell.strip()
    m = re.fullmatch(r"\[\[([^\]\|#]+)(?:[#|][^\]]*)?\]\]", name)
    for rel, path in args.dest:
        if rel == name or (m and os.path.splitext(os.path.basename(rel))[0].lower()
                           == m.group(1).strip().lower()):
            return read_text(path, "the move's destination")[1]
    if m:
        return find_page(args.wiki, m.group(1))
    if name.startswith("wiki/"):
        path = os.path.join(args.wiki, name[len("wiki/"):])
        if os.path.isfile(path):
            return read_text(path, "the move's destination")[1]
    return None


CONTROL_BEFORE = ("---\ntitle: control\ntype: development\nupdated: 2026-01-01\n---\n# Control\n\n"
                  "A paragraph that stays.\n\n> his words, never altered\n\n## Sources Used\n- one\n")


def control(yaml):
    """The real legs on a page built here and kept nowhere: one character changed inside a
    quotation must fail Q1, Q3, L1 and L3, and the identical candidate must pass every leg. Run
    before every check, so a pass carries its positive control on the same run."""
    class Args:
        page, wiki, hold, dest = "wiki/control.md", None, "control.hold.md", []
    raw = CONTROL_BEFORE.encode("utf-8")
    altered = CONTROL_BEFORE.replace("never altered", "never alterd")
    for after, expect in ((altered, ["Q1", "Q3", "L1", "L3"]), (CONTROL_BEFORE, [])):
        fails, _notes = check(Args, "filed copy control.hold.md", raw, raw, raw, CONTROL_BEFORE,
                              after, [], yaml)
        got = [leg for leg, lines in fails.items() if lines]
        if got != expect:
            raise ProbeFailed("the in-memory control is off: %s failed %s, expected %s"
                              % ("the altered candidate" if expect else "the identical candidate",
                                 got or "nothing", expect or "nothing"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="the program check of a whole-page clean")
    parser.add_argument("--page", required=True)
    parser.add_argument("--wiki", required=True)
    parser.add_argument("--hold", required=True)
    parser.add_argument("--dir")
    parser.add_argument("--before")
    parser.add_argument("--after")
    parser.add_argument("--ledger")
    parser.add_argument("--dest", action="append", default=[])
    parser.add_argument("--trial", action="store_true")
    args = parser.parse_args(argv)
    mode = "trial" if args.trial else "enforce"
    print("bulk-clean check · page %s · mode %s" % (args.page, mode))
    try:
        if args.dir:
            args.before = args.before or os.path.join(args.dir, "BEFORE.md")
            args.after = args.after or os.path.join(args.dir, "AFTER.md")
            args.ledger = args.ledger or os.path.join(args.dir, "LEDGER.tsv")
        if not args.page.startswith("wiki/") or not args.page.endswith(".md"):
            raise ProbeFailed("--page is not a page path from the vault root (wiki/....md): %s"
                              % args.page)
        if not os.path.isdir(args.wiki):
            raise ProbeFailed("no wiki folder at %s" % args.wiki)
        dests = []
        for item in args.dest:
            rel, sep, path = item.partition("=")
            if not sep:
                raise ProbeFailed("--dest is wiki/REL.md=FILE: %s" % item)
            dests.append((rel, path))
        args.dest = dests
        yaml = load_yaml()
        control(yaml)
        print("CONTROL+ in memory: a quotation changed by one character fails Q1, Q3, L1 and L3; "
              "the identical candidate passes every leg")
        before_raw, before = read_text(args.before, "BEFORE")
        if not before_raw.strip():
            raise ProbeFailed("BEFORE is empty: there is no page to check against: %s" % args.before)
        _raw, after = read_text(args.after, "AFTER")
        rows = read_ledger(args.ledger)
        print("BEFORE %d bytes · AFTER %d bytes · LEDGER %d rows"
              % (len(before_raw), len(after.encode()), len(rows)))
        if re.fullmatch(r"[0-9a-fA-F]{7,40}", args.hold):
            hold_raw = git_show(args.wiki, args.page[len("wiki/"):], args.hold)
            hold_name = "commit %s" % args.hold
        else:
            if not os.path.isfile(args.hold):
                raise ProbeFailed("the hold does not have the page: no filed copy at %s" % args.hold)
            hold_raw = read_text(args.hold, "the filed copy")[0]
            hold_name = "filed copy %s" % os.path.basename(args.hold)
        live = os.path.join(args.wiki, args.page[len("wiki/"):])
        if not os.path.isfile(live):
            raise ProbeFailed("no live page at %s" % live)
        live_raw = read_text(live, "the live page")[0]
        fails, notes = check(args, hold_name, hold_raw, live_raw, before_raw, before, after, rows,
                             yaml)
    except ProbeFailed as failure:
        print("PROBE FAILED: %s" % failure)
        return 2
    for leg, lines in fails.items():
        if leg == "E2" and not args.page.startswith("wiki/experience/"):
            print("E2 n/a: not a lessons page")
            continue
        print("%s %s%s" % (leg, "FAIL" if lines else "PASS", " (%d)" % len(lines) if lines else ""))
        for line in lines:
            print("  - %s" % line)
    print("E1 not built: a stopped part of the design (a register move)")
    for line in notes:
        print("NOTE: %s" % line if not line.startswith("LISTED") else line)
    failed = [leg for leg, lines in fails.items() if lines]
    if not failed:
        listed = sum(1 for line in notes if line.startswith("LISTED: Q4 "))
        print(("TRIAL: would pass" if args.trial else "PASS: every leg passed") + (
            ", once the reader has read the %d LISTED: Q4 block%s; the swap waits on that read"
            % (listed, "" if listed == 1 else "s") if listed else ""))
        return 0
    if args.trial:
        print("TRIAL: WOULD BLOCK: %s failed (trial: nothing is blocked; the lead decides the swap)"
              % ", ".join(failed))
        return 0
    print("BLOCK: %s failed; the swap is blocked" % ", ".join(failed))
    return 1


if __name__ == "__main__":
    sys.exit(main())
