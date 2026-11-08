#!/usr/bin/env python3
"""anomaly-lister.py — the page-visible anomaly census a verify leg checks a report against.

A compile lane's report ends with an Anomalies section. Verifying it by hand means
re-reading every page the lane touched; this script instead lists what the PAGES
themselves say, so the verify leg is a comparison rather than a re-read.

Four kinds, all read straight off the page
  open-conflict  a Conflicts / Open Questions block (CLAUDE.md 4.4) that does not record
                 its own settlement as a whole (the rule below). An empty block records
                 nothing, so it counts as an empty block rather than an open one.
  flagged        a `flagged:` frontmatter line (the query/output staleness flag), with
                 its text, so the reason travels with the count.
  thin-page      prose saying the page rests on too little — single witness, single-source
                 stub, uncorroborated.
  unverified     inline `unverified` markers (CLAUDE.md 11), counted per page.

When a conflict block counts as settled (CLAUDE.md 4.4: a settled conflict keeps both statements,
and each of its items opens with `Settled YYYY-MM-DD:` and the outcome). The register entry of
2026-10-09 found a substring test reading "unresolved" and "a single reconciled table" as
settlement; the two reviews of 2026-10-11 found settled readings of a line settling one claim
beside an open one, a nested or block-quoted open claim beside another claim's settlement, a
marker negated mid-line, a declaration of a settlement still to come and an issue closed as stale;
and the rule that followed still settled shapes 4.4 does not write (another marker word, a bare
colon such as "**Settled**:", a date with no colon, a month-name date, a `Status:` field); the
review of the 4.4 rule (2026-10-15) found a date no calendar has and a declaration with no outcome
still settling. Only explicit evidence that the WHOLE block is settled suppresses it; anything
less lists it, and where a rule is in doubt the block stays listed.
  - A settlement declaration is a line that opens, after indentation, block-quote marks, one
    list marker, a task box, heading marks and opening emphasis, with the literal 4.4 form: the
    word `Settled` as written (capital S), one space, a real calendar date in the YYYY-MM-DD
    shape (ASCII digits, a day Python's datetime.date accepts, so years 0001 to 9999) and the
    colon straight after it. So `**Settled 2026-10-01:**` and `Settled 2024-02-29:` declare,
    while `Settled 2026-13-45:`, `Settled 2026-02-30:`, `Settled 2026-02-29:`,
    `**Settled 2026-10-01**:`, `**Settled**:`, `Settled:`, `Settled on 2026-10-01:`,
    `Settled 2026-10-01 —`, `Settled 3 May 2026:`, lower-case `settled 2026-10-01:`, a
    `Status:` field and every other marker word ("Resolved 2026-10-01:", "Reconciled:",
    "Closed 2026-10-01:", "Decided 2026-10-01:") declare nothing. A block written in an older
    form is listed; this script never rewrites it.
  - A declaration settles only with its outcome on its own line (4.4: "and the outcome"): the
    rest of the line after the colon must hold at least one letter or digit, in any script.
    `Settled 2026-10-01:` with nothing after the colon, or only spaces, closing emphasis or
    punctuation (`**Settled 2026-10-01:**` alone, `Settled 2026-10-01: —`), settles nothing,
    and so does a declaration whose outcome is wrapped onto the next line, since the rule reads
    the declaration's own line.
  - A declaration whose value, after the colon, opens with a negative ("not", "no", "never",
    "none", "open", "unknown", "unresolved", "unsettled", "undecided", "stale", "yet to be" or
    "?") or a prospective connective ("once", "when", "if", "after", "until", "pending")
    settles nothing: "Settled 2026-10-01: once the two runs agree" records a settlement still
    to come, not an outcome.
  - A marker word anywhere else — mid-line, after a negation, inside "unresolved", in an
    incidental phrase such as "a single reconciled table", in a dated aside such as "(resolved
    upstream 2026-04-17)" — is a mention, never a declaration.
  - Every claim needs its own declaration. The block is read as items (a top-level list item
    or paragraph) and their parts (the item's own line, each nested list item at any depth,
    each later paragraph; a continuation line belongs to the part above it), block-quote marks
    set aside first, so a list inside a block quote is read as claims like any other; and EVERY
    part must open with a declaration. A settlement nested under a claim that does not declare
    its own cannot be told from the settlement of another claim, so it settles nothing.
  - An open signal anywhere in the block keeps it open, whatever its declarations say: a
    negated marker ("never been resolved", "not resolved", "not yet settled", "hasn't been
    reconciled": not, never, no, nor, without or a word ending in n't, then at most three
    words, then settled, resolved, adjudicated, superseded, reconciled or an active marker
    word, or closed, decided, determined, confirmed or known, case ignored), "still
    disagrees" (still or continues to, with disagree, differ, conflict, contradict or diverge),
    "remains open" (remains, stays, is, are, left or kept, with open, unresolved, unclear,
    unknown, disputed, pending and the like), "open question", "unresolved", "undecided",
    "pending", "awaiting", "TBD", "not yet", "yet to be", "cannot be decided", "nothing
    decides", "no decision", "reopened" and "unclear which". A question mark is no signal: a
    settled claim may quote the question it answers, and a question no declaration answers is
    listed by the rule above. Words a settled block uses in passing ("disagreed", "differ",
    "kept", "question") are no signals on their own. The signals are a vocabulary, so a line can
    still declare a settlement and describe an open remainder in other words: one claim per
    item, each with its own declaration, is the convention that keeps the rule sound.
Four planted settled blocks (one item; several items and a nested one, each declared; a
declaration quoting the question it answers; a leap day) and twenty-six planted unsettled ones run
in memory on every call: the twelve of the 2026-10 reviews (substring, incidental, a dated
incidental mention, negated, mixed across items, mixed on one line, a nested open claim beside a
settled one, a stale closure, a marker negated mid-line, a list inside a block quote, a
prospective declaration, a closure as stale opening the line), five shapes 4.4 does not write
(another marker word, a bare colon, "**Settled**:", a colon after the closing emphasis, a date with
no colon), five 4.4 declarations each undone by a guard (an open signal, an undeclared nested
claim, a negated marker, a block-quoted open claim, a prospective value) and four the calendar or
the outcome undoes (a month and day no calendar has, a 29 February in a common year, nothing after
the colon, only closing emphasis after it); a miss prints PROBE FAILED and exits 2.

`--settled-markers` accepts one value, `Settled`, and refuses any other with one PROBE FAILED line
naming the 4.4 form and exit 2, so no value of it can settle anything but `Settled YYYY-MM-DD:`
with a real date and an outcome. It is kept only so that a caller passing `Settled` keeps working;
earlier builds let it replace the declaration word, so "Decided 2026-10-01:" could be made to
settle a block, and it no longer can.

What is stripped before matching: fenced code blocks and HTML comments, neither of which
is page-visible prose. Inline code spans are KEPT, because the inline marker is habitually
written inside backticks and stripping spans would silently zero the commonest kind.

Counting the marker, two ways (`--unverified-form`, printed in the header)
  any        every occurrence of the word in visible prose. The default, and the honest
             census: it is a floor on nothing and a ceiling on nothing.
  backtick   only occurrences inside an inline code span, i.e. the MARKER form CLAUDE.md
             prescribes. Prose that discusses the marker rather than applying it — a
             design page explaining when to write it — drops out, so a verify leg that
             must compare like with like has a form to ask for.

Self-control (CLAUDE.md 11): every run analyses one synthetic page held in memory that
carries all four kinds (the marker in both forms, so the control vouches for whichever
`--unverified-form` is active) plus one empty conflict block, and prints
`anomaly-control: 4/4 … empty-conflict control: 1/1 · settlement-control: 30/30`. A miss
prints PROBE FAILED and exits 2 — an analyser that cannot find a planted anomaly cannot
report a page clean, and one that cannot tell a settled block from an open one cannot
report a block settled.

A broken premise prints one plain `PROBE FAILED: …` line on stdout and exits 2 whatever
`--format` says, so a JSON consumer keys on the exit code, never on parsing that line.

Stdout only: this script never creates, modifies, moves or deletes a file.

Usage:
  python3 anomaly-lister.py [--vault ROOT] [--format text|json]
  python3 anomaly-lister.py --pages PATH [PATH ...] [--format text|json]
  optional: --settled-markers Settled (the one value accepted; any other exits 2: the 4.4 form is fixed)
            --thin-regex 'x|y'   --unverified-form any|backtick
  exit 0 = the probe ran (findings or none) · exit 2 = broken premise
"""
import argparse
import collections
import datetime
import glob
import json
import os
import re
import sys

KINDS = ("open-conflict", "flagged", "thin-page", "unverified")
UNVERIFIED_FORMS = ("any", "backtick")

# CLAUDE.md 4.4: each item of a settled conflict opens with `Settled YYYY-MM-DD:` and the outcome.
# The declaration word is matched as written, case kept, and it is fixed: --settled-markers accepts
# this word alone and refuses any other value (exit 2), so no value of the switch settles anything but
# the 4.4 form. The words the rule once also accepted (resolved, adjudicated, superseded, reconciled)
# and its looser shapes (a bare colon, a date with no colon, a month-name date, a Status: field) no
# longer settle a block: one written in an older form is listed, never rewritten.
DEFAULT_SETTLED = "Settled"
# The rest of the 4.4 form: one space, a date in the YYYY-MM-DD shape and the colon straight after
# it. ASCII digits only: \d would also take the digits of other scripts. The pattern checks the shape;
# real_date() then checks that the calendar has the day.
DECLARATION_TAIL = r" (?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2}):"
# An outcome (CLAUDE.md 4.4: "and the outcome"): the rest of the declaration's line holds a letter or a
# digit, in any script. Spaces, closing emphasis and punctuation alone are no outcome.
OUTCOME_RE = re.compile(r"[^\W_]")
# The outcome words a negated-marker open signal looks for beside the declaration word, so a negated
# "resolved" keeps a block open as surely as a negated "settled". "provenance" (a topic, not an
# outcome) and "confirmed" (said of one figure, rarely of a whole disagreement) are no marker words;
# "closed" names an issue's closure, as stale or unanswered (second review of 2026-10-11), and joins
# the negated words below rather than these.
MENTION_WORDS = "settled|resolved|adjudicated|superseded|reconciled"
# The settlement rule (module docstring). Each pattern is applied to one line at a time.
LEAD_QUOTE_RE = re.compile(r"^(?:>[ \t]*)+")
LIST_ITEM_RE = re.compile(r"^[ \t]*(?:[-*+]|\d{1,9}[.)])[ \t]+")
TASK_BOX_RE = re.compile(r"^\[[ xX]\][ \t]+")
HEADING_MARK_RE = re.compile(r"^#{1,6}[ \t]+")
EMPHASIS_RE = re.compile(r"^[*_]{1,3}")
# The value after the declaration's colon: a negative, or a prospective connective (the second review
# of 2026-10-11: "Resolved: once the two runs agree" recorded a settlement still to come, not an outcome).
AFTER_COLON_BLOCKER_RE = re.compile(r"^[*_ \t]*(?:(?:not|no|never|none|open|unknown|unresolved|"
                                    r"unsettled|undecided|stale|yet to be|once|when|if|after|until|"
                                    r"pending)\b|\?)", re.I)
# A negated marker (module docstring): a negation, at most three words (emphasis aside), then a marker
# word: the declaration word or any of the words below, case ignored.
NEGATION = r"\b(?:not|never|no|nor|without|\w+n['\u2019]t)\b"
NEGATED_WORDS = MENTION_WORDS + "|closed|decided|determined|confirmed|known"
# The open signals (module docstring): any one, anywhere in a block, keeps it open. Bare words a
# settled block uses in passing ("disagreed", "differ", "kept", "question") are deliberately absent,
# and so is the question mark (second review of 2026-10-11: a settled claim may quote its question).
OPEN_WORDS = (r"open|unresolved|unsettled|undecided|undetermined|unanswered|contested|disputed|unclear|"
              r"unknown|uncertain|unexplained|unconfirmed|outstanding|pending|in dispute")
OPEN_SIGNAL_RE = re.compile(
    rf"\b(?:remains?|remained|remaining|stays?|stayed|is|are|left|kept)\s+(?:\w+\s+)?(?:{OPEN_WORDS})(?![\w-])"
    r"|\b(?:still|continues?\s+to|continued\s+to)\s+(?:\w+\s+){0,2}?(?:disagree|differ|conflict|contradict|"
    r"diverge|clash|open|unresolved|unsettled|undecided|unclear|unknown|disputed|contested|pending|"
    r"outstanding)\w*"
    r"|\bopen\s+(?:questions?|issues?|points?|items?|problems?)\b"
    r"|\b(?:un-?resolved|un-?settled|un-?decided|undetermined|unreconciled|unadjudicated|unanswered|"
    r"pending|awaiting|tbd|tba|tbc)\b"
    r"|\bnot\s+yet\b|\byet\s+to\s+be\b"
    r"|\b(?:cannot|can\s+not|can['\u2019]t|could\s+not|couldn['\u2019]t)\s+(?:yet\s+)?(?:be\s+)?"
    r"(?:decided?|determined?|resolved?|settled?|reconciled?|told|tell|confirmed?)\b"
    r"|\b(?:nothing|none|neither|no\s+one|nobody)\b[^.;\n]{0,40}?\b(?:decides?|decided|settles?|settled|"
    r"resolves?|resolved|reconciles?|reconciled|adjudicates?|adjudicated)\b"
    r"|\bno\s+(?:decision|resolution|settlement|verdict|adjudication)\b"
    r"|\bre-?open(?:ed|s)?\b"
    r"|\b(?:unclear|unknown)\s+(?:which|whether|why|how|what|who|when)\b", re.I)
# Block-quote marks, each with the one space it may carry, set aside before a block is cut into claims
# (second review of 2026-10-11: a list inside a block quote read as one claim).
QUOTE_MARKS_RE = re.compile(r"^([ \t]*)(?:>[ \t]?)+")


Markers = collections.namedtuple("Markers", "declaration negated")


def marker_pattern(words):
    """The markers for a declaration word: the 4.4 declaration a claim opens with (the word
    exactly as written, case kept, then DECLARATION_TAIL), and the negated-marker open signal (a
    negation, at most three words with blanks or emphasis between them, then the same word, a
    MENTION_WORDS word or a NEGATED_WORDS word, case ignored). Every caller in this script passes
    DEFAULT_SETTLED: --settled-markers accepts no other word."""
    declaration = re.compile(rf"(?:{words}){DECLARATION_TAIL}")
    negated = re.compile(rf"{NEGATION}(?:[\s*_]+\w+){{0,3}}?[\s*_]+"
                         rf"(?:(?:{words})(?![\w-])|(?:{NEGATED_WORDS})(?![\w-]))", re.I)
    return Markers(declaration, negated)


def strip_lead(line):
    """One line with its leading layout and markup removed: indentation, block-quote marks, one
    list marker, a task box, heading marks and the opening emphasis run."""
    s = LEAD_QUOTE_RE.sub("", line.strip())
    s = LIST_ITEM_RE.sub("", s, count=1)
    s = TASK_BOX_RE.sub("", s, count=1)
    s = HEADING_MARK_RE.sub("", s, count=1)
    return EMPHASIS_RE.sub("", s, count=1)


def real_date(m):
    """True when a declaration match names a day the calendar has: datetime.date refuses
    2026-13-45, 2026-02-30, 2026-02-29 (a common year) and the year 0000 alike."""
    try:
        datetime.date(int(m.group("year")), int(m.group("month")), int(m.group("day")))
    except ValueError:
        return False
    return True


def opens_settled(line, markers):
    """True when one line opens with the 4.4 declaration, its date is a real calendar date, and
    the rest of the line is an outcome: it holds a letter or digit, and it opens with no negative
    and no settlement still to come (the rule in the docstring)."""
    text = strip_lead(line)
    m = markers.declaration.match(text)
    if not m or not real_date(m):
        return False
    value = text[m.end():]
    return bool(OUTCOME_RE.search(value)) and not AFTER_COLON_BLOCKER_RE.match(value)


def block_items(block):
    """A block's items, each a list of parts, each part a list of lines.

    Block-quote marks are set aside first, so a quoted line is cut as the same line unquoted.
    A top-level list item, or a top-level line after a blank line, opens an item; a nested
    list item, or an indented line after a blank line, opens a new part of the current item;
    any other line continues the current part (Markdown's lazy continuation included).
    """
    items, after_blank = [], True
    for quoted in block.split("\n"):
        line = QUOTE_MARKS_RE.sub(r"\1", quoted)
        if not line.strip():
            after_blank = True
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        listed = bool(LIST_ITEM_RE.match(line))
        if not items or (indent <= 1 and (listed or after_blank)):
            items.append([[line]])
        elif listed or after_blank:
            items[-1].append([line])
        else:
            items[-1][-1].append(line)
        after_blank = False
    return items


def block_settled(block, markers):
    """True only when every claim of the block, nested items, later paragraphs and block-quoted
    items included, opens with its own 4.4 declaration and no open signal, a negated marker
    among them, sits anywhere in the block (the docstring's rule). `markers` is a
    marker_pattern()."""
    items = block_items(block)
    if not items or OPEN_SIGNAL_RE.search(block) or markers.negated.search(block):
        return False
    return all(opens_settled(part[0], markers) for item in items for part in item)


DEFAULT_THIN = "thin page|single witness|single-witness|single-source stub|only witness|uncorroborated"

CONFLICT_HEAD = re.compile(r"^(#{1,6})[ \t]*Conflicts\b.*$", re.M)
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---", re.S)
SPAN_RE = re.compile(r"`[^`\n]+`")
UNVERIFIED_RE = re.compile(r"unverified", re.I)
EXCERPT_CHARS = 140     # one terminal line minus the indent; set by judgement, unmeasured


def stdout_utf8():
    """Make stdout encode any page name, excerpt or separator this script prints.

    Without it an ascii stdout (PYTHONIOENCODING, a bare C locale on some builds) turns a
    unicode page name — or the run's own separator glyph — into a traceback and exit 1,
    which reads as neither a finding nor a probe failure.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


def read_text(path):
    """Read a file as UTF-8, dropping a BOM and normalising CRLF; bad bytes are replaced.

    A BOM or a CRLF line ending would otherwise defeat the frontmatter match and hide a
    `flagged:` line inside a block this census would then read as prose.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    return raw.decode("utf-8-sig", "replace").replace("\r\n", "\n")


def visible(text):
    """Drop what a reader never sees: fenced code blocks and HTML comments. Spans stay."""
    text = re.sub(r"```.*?```", "\n", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    return text


def excerpt(s):
    s = " ".join(s.split())
    return s if len(s) <= EXCERPT_CHARS else s[:EXCERPT_CHARS - 1] + "…"


def line_at(prose, pos):
    """The whole source line containing an offset, trimmed."""
    start = prose.rfind("\n", 0, pos) + 1
    end = prose.find("\n", pos)
    return prose[start:end if end != -1 else len(prose)].strip()


def unverified_hits(prose, form):
    """Offsets of each marker occurrence the ACTIVE form counts."""
    if form == "backtick":
        for span in SPAN_RE.finditer(prose):
            for m in UNVERIFIED_RE.finditer(span.group(0)):
                yield span.start() + m.start()
        return
    for m in UNVERIFIED_RE.finditer(prose):
        yield m.start()


def unclosed_frontmatter(text):
    """True when a page opens a frontmatter fence it never closes.

    Every key below such a fence is read as prose, so a `flagged:` line there is invisible
    to this census: the run reports the page rather than letting its count pass as zero.
    """
    return text.startswith("---\n") and not FRONTMATTER.match(text)


def analyse(text, settled_re, thin_re, form="any"):
    """Return {kind: [excerpt, ...]}, an `empty-conflict` counter and a settled-block counter
    for one page's text. `settled_re` is a marker_pattern(), applied by block_settled().

    Pure text in, findings out — the vault pass and the self-control call the same function.
    """
    found = {k: [] for k in KINDS}
    empty_conflicts = settled_blocks = 0

    fm = FRONTMATTER.match(text)
    if fm:
        for line in fm.group(1).split("\n"):
            if re.match(r"^flagged:", line):
                found["flagged"].append(excerpt(line.strip()))

    body = visible(text)
    lines = body.split("\n")
    for m in CONFLICT_HEAD.finditer(body):
        level = len(m.group(1))
        start = body[:m.start()].count("\n") + 1
        end = len(lines)
        for i in range(start, len(lines)):
            h = re.match(r"^(#{1,6})[ \t]", lines[i])
            if h and len(h.group(1)) <= level:
                end = i
                break
        block = "\n".join(lines[start:end]).strip()
        if not block:
            empty_conflicts += 1
        elif block_settled(block, settled_re):
            settled_blocks += 1          # every item records its own settlement
        else:
            first = next((ln.strip() for ln in block.split("\n") if ln.strip()), "")
            found["open-conflict"].append(excerpt(first))

    # Re-match the frontmatter on the STRIPPED text: offsets into `body` are the only ones
    # valid here, and a match against the raw text would cut the prose at the wrong place
    # whenever stripping shortened anything above it.
    fm_body = FRONTMATTER.match(body)
    prose = body[fm_body.end():] if fm_body else body
    for m in thin_re.finditer(prose):
        found["thin-page"].append(excerpt(line_at(prose, m.start())))
    for pos in unverified_hits(prose, form):
        found["unverified"].append(excerpt(line_at(prose, pos)))

    return found, empty_conflicts, settled_blocks


# A synthetic page carrying all four kinds, the marker in both forms, and one empty
# conflict block. In memory only; it never touches disk.
SELF_CONTROL_PAGE = (
    "---\n"
    "title: \"Self-control page\"\n"
    "type: concept\n"
    "flagged: 2026-01-01 mechanism may have changed since capture\n"
    "---\n\n"
    "## Definition\n"
    "A thin page resting on a single witness, so its claim stays `unverified` here, and it\n"
    "reads unverified in plain prose as well.\n\n"
    "## Conflicts / Open Questions\n"
    "- Two captures disagree on the figure and nothing decides between them.\n\n"
    "## Conflicts / Open Questions\n\n"
    "## Related\n"
    "- Another page.\n"
)


# In-memory settlement controls on the DEFAULT markers: (block text, must read as settled).
SETTLEMENT_CONTROLS = (
    ("- **Settled 2026-01-02:** the two captures measure different splits.", True),
    ("- **Settled 2026-10-01:** the first figure is the later capture's.\n"
     "  - **Settled 2026-10-02:** the footnote's figure is a rounding.\n"
     "- Settled 2026-10-03: the second figure was a transcription slip.", True),
    ("- Settled 2026-10-01: Why do the totals differ? They measure different splits.", True),
    # A leap day is a real date: the calendar check must not refuse it.
    ("- Settled 2024-02-29: the leap-day capture governs.", True),
    ("- The two figures disagree and the question stays unresolved.", False),
    ("- A single reconciled table (2026-01-02) is not available, so nothing decides.", False),
    ("- The figures differ in a single reconciled table dated 2026-10-01.", False),
    ("- Not resolved: nothing decides between the two figures.", False),
    ("- Resolved 2026-01-02: the first figure.\n- The second figure disagrees and nothing decides.", False),
    ("- Resolved 2026-10-01: the first figure; the second still disagrees and nothing decides.", False),
    ("- **Resolved 2026-10-01:** the first figure is the later capture's.\n"
     "  - The second figure differs between the captures.\n"
     "  - **Resolved 2026-10-02:** the third figure is a rounding.", False),
    ("- Closed 2026-04-17 as stale with no maintainer reply.", False),
    # The second review of 2026-10-11: a marker negated mid-line, a list inside a block quote, a
    # settlement still to come, an issue closed as stale.
    ("- Resolved 2026-10-01: the first figure; the second has never been resolved.", False),
    ("> - Resolved 2026-10-01: the first figure.\n> - The second differs between runs.", False),
    ("- Resolved: once the two runs agree.", False),
    ("- Closed: the issue was closed as stale without a reply.", False),
    # Shapes CLAUDE.md 4.4 does not write: another marker word, a bare colon, closing emphasis before
    # a colon with no date, a colon after the closing emphasis, a date with no colon.
    ("- **Resolved 2026-01-02:** the two captures measure different splits.", False),
    ("- Reconciled: the second figure was a transcription slip.", False),
    ("- **Settled**: the later capture governs.", False),
    ("- **Settled 2026-10-01**: the later capture governs.", False),
    ("- Settled 2026-10-01 — the vendor page governs.", False),
    # The 4.4 form, each undone by a guard: an open signal, an undeclared nested claim, a negated
    # marker, a block-quoted open claim, a settlement still to come.
    ("- Settled 2026-10-01: the first figure; the second still disagrees and nothing decides.", False),
    ("- Settled 2026-10-01: the first figure.\n  - The second figure differs between the captures.", False),
    ("- Settled 2026-10-01: the first figure; the second has never been resolved.", False),
    ("> - Settled 2026-10-01: the first figure.\n> - The second differs between runs.", False),
    ("- Settled 2026-10-01: once the two runs agree.", False),
    # The 4.4 shape undone by the calendar or by a missing outcome (the review of 2026-10-15): a month
    # and day no calendar has, a 29 February in a common year, nothing after the colon, only closing
    # emphasis after it.
    ("- Settled 2026-13-45: the later capture governs.", False),
    ("- Settled 2026-02-29: the later capture governs.", False),
    ("- Settled 2026-10-01:", False),
    ("- **Settled 2026-10-01:**", False),
)


def run_settlement_control():
    """How many planted blocks the rule reads correctly, of how many."""
    markers = marker_pattern(DEFAULT_SETTLED)
    right = sum(1 for block, want in SETTLEMENT_CONTROLS if block_settled(block, markers) is want)
    return right, len(SETTLEMENT_CONTROLS)


def run_self_control(settled_re, thin_re, form):
    """Prove the analyser finds all four kinds, then ask whether the ACTIVE --thin-regex hides one.

    The control runs on the DEFAULT thin-page regex, because what it tests is the analyser, not
    the caller's configuration: an override that misses the synthetic note would otherwise fail
    the run for a reason that has nothing to do with the analyser working. The settled marker
    is the default in both passes, since --settled-markers accepts no other value.
    It runs on the ACTIVE `--unverified-form`, because that one is a counting mode rather
    than a filter, and a control has to vouch for the counting the run actually does.
    The override is still attacked — a second pass under the active --thin-regex reports which
    kinds it swallows, as a warning, so an override that quietly zeroes a kind is visible.
    """
    default, empties, _settled = analyse(SELF_CONTROL_PAGE, marker_pattern(DEFAULT_SETTLED),
                                         re.compile(DEFAULT_THIN, re.I), form)
    caught = [k for k in KINDS if default[k]]
    active = analyse(SELF_CONTROL_PAGE, settled_re, thin_re, form)[0]
    swallowed = [k for k in KINDS if default[k] and not active[k]]
    return caught, swallowed, empties


def assert_vault_root(root):
    """A root must hold raw/ AND wiki/ or the census refuses to run.

    The 2026-08-26 standard, closed for the capture layer and swept here on 2026-09-07: fail
    loud on stderr, never a wrong-tree scan that reports a clean vault on a scan of nothing.
    """
    if not all(os.path.isdir(os.path.join(root, d)) for d in ("raw", "wiki")):
        print(f"PROBE FAILED: {root} is not a vault root (no raw/ or wiki/)", file=sys.stderr)
        raise SystemExit(2)
    return root


def main():
    stdout_utf8()
    ap = argparse.ArgumentParser(description="Page-visible anomaly census for wiki pages.")
    ap.add_argument("--vault", default=".", help="vault root (default: the current directory)")
    ap.add_argument("--pages", nargs="+", help="check exactly these pages instead of the vault")
    ap.add_argument("--settled-markers", default=DEFAULT_SETTLED, metavar=DEFAULT_SETTLED,
                    help="accepts only Settled, the CLAUDE.md 4.4 declaration word, and refuses any "
                         "other value (exit 2): a claim settles only on `Settled YYYY-MM-DD:` with a "
                         "real calendar date and an outcome. Kept so a caller passing Settled keeps "
                         "working")
    ap.add_argument("--thin-regex", default=DEFAULT_THIN,
                    help="regex matching a thin-page note")
    ap.add_argument("--unverified-form", choices=UNVERIFIED_FORMS, default="any",
                    help="count every occurrence of the word (any, the default) or only the "
                         "backticked marker form (backtick)")
    ap.add_argument("--format", choices=("text", "json"), default="text",
                    help="output format (default: text)")
    args = ap.parse_args()

    # The declaration word is fixed (CLAUDE.md 4.4): the switch is refused, never read as a pattern.
    if args.settled_markers != DEFAULT_SETTLED:
        print(f"PROBE FAILED: --settled-markers accepts only {DEFAULT_SETTLED}: a claim settles only on "
              f"the CLAUDE.md 4.4 form `Settled YYYY-MM-DD:` with a real date and an outcome, so "
              f"{args.settled_markers!r} is refused")
        return 2
    settled_re = marker_pattern(DEFAULT_SETTLED)
    try:
        thin_re = re.compile(args.thin_regex, re.I)
    except re.error as exc:
        print(f"PROBE FAILED: bad regex: {exc}")
        return 2

    form = args.unverified_form
    settle_right, settle_total = run_settlement_control()
    if settle_right != settle_total:
        print(f"PROBE FAILED: settlement-control {settle_right}/{settle_total} — the rule misread a "
              f"planted block, so no block it reads as settled can be trusted")
        return 2
    caught, swallowed, control_empties = run_self_control(settled_re, thin_re, form)
    if len(caught) != len(KINDS):
        missed = [k for k in KINDS if k not in caught]
        print(f"PROBE FAILED: anomaly-control {len(caught)}/{len(KINDS)} — "
              f"analyser missed {', '.join(missed)}")
        return 2
    if control_empties != 1:
        print(f"PROBE FAILED: empty-conflict control {control_empties}/1 — the planted empty "
              f"block was not counted, so an empty-block total of zero would prove nothing")
        return 2

    root = os.path.abspath(os.path.expanduser(args.vault))
    if args.pages:
        mode = "pages"
        pages = [os.path.abspath(os.path.expanduser(p)) for p in args.pages]
        missing = [p for p in pages if not os.path.isfile(p)]
        if missing:
            print(f"PROBE FAILED: {len(missing)} named page(s) not on disk: "
                  f"{', '.join(os.path.basename(m) for m in missing)}")
            return 2
    else:
        mode = "vault"
        root = assert_vault_root(root)     # vault mode only: --pages names its own files
        wiki = os.path.join(root, "wiki")
        if not os.path.isdir(wiki):        # unreachable while the root guard runs first
            print(f"PROBE FAILED: no wiki directory under {args.vault}")
            return 2
        # log.md is append-only history, not a page whose anomalies anyone reconciles.
        pages = [p for p in sorted(glob.glob(os.path.join(wiki, "**", "*.md"), recursive=True))
                 if os.path.basename(p) != "log.md"]
        if not pages:
            print("PROBE FAILED: wiki directory holds no Markdown pages")
            return 2

    results, empty_total, settled_total, malformed = {}, 0, 0, []
    for p in pages:
        try:
            rel = os.path.relpath(p, root)
        except ValueError:
            rel = p
        try:
            text = read_text(p)
        except OSError as exc:
            print(f"PROBE FAILED: cannot read {rel}: {exc}")
            return 2
        if unclosed_frontmatter(text):
            malformed.append(rel)
        found, empties, settled = analyse(text, settled_re, thin_re, form)
        empty_total += empties
        settled_total += settled
        if any(found[k] for k in KINDS):
            results[rel] = {k: found[k] for k in KINDS if found[k]}

    summary = {k: sum(len(v.get(k, [])) for v in results.values()) for k in KINDS}
    control = f"{len(caught)}/{len(KINDS)}"

    if args.format == "json":
        print(json.dumps({
            "mode": mode, "root": args.vault, "pages": len(pages),
            "settled_markers": DEFAULT_SETTLED, "thin_regex": args.thin_regex,
            "unverified_form": form,
            "findings": results, "pages_with_findings": len(results),
            "summary": summary, "empty_conflict_blocks": empty_total,
            "settled_conflict_blocks": settled_total,
            "settlement_control": f"{settle_right}/{settle_total}",
            "anomaly_control": control, "empty_conflict_control": control_empties,
            "markers_swallow": swallowed, "malformed_frontmatter": malformed,
        }, indent=2, sort_keys=True))
        return 0

    print(f"anomaly-lister: mode={mode} · root={args.vault} · kinds={','.join(KINDS)} · "
          f"unverified-form={form} · excerpt={EXCERPT_CHARS} chars · format=text")
    print(f"settled-markers={DEFAULT_SETTLED} (fixed: the CLAUDE.md 4.4 form `Settled YYYY-MM-DD:` with a "
          f"real date and an outcome; no other value is accepted)")
    print(f"thin-regex={args.thin_regex}")
    print(f"scanned: {len(pages)} pages (log.md excluded in vault mode)")
    for rel in sorted(results):
        print(rel)
        for kind in KINDS:
            items = results[rel].get(kind)
            if items:
                print(f"  {kind} ({len(items)}) — {items[0]}")
    print("summary: " + " · ".join(f"{k} {summary[k]}" for k in KINDS) +
          f"   (across {len(results)} pages; {empty_total} empty conflict blocks)")
    print(f"anomaly-control: {control} (on the default markers — the analyser's own capability) "
          f"· empty-conflict control: {control_empties}/1")
    print(f"settled conflict blocks: {settled_total} (every claim opens with its own `Settled YYYY-MM-DD:` "
          f"declaration, a real date and an outcome, no open signal) · settlement-control: "
          f"{settle_right}/{settle_total}")
    if swallowed:
        print(f"marker-override warning: the active --thin-regex also hides {', '.join(swallowed)} "
              f"on the control page, so that kind's count here is a floor, not a census")
    if malformed:
        print(f"frontmatter warning: {len(malformed)} page(s) open a --- fence they never close, "
              f"so any frontmatter key there reads as prose and their flagged count is a floor")
        for rel in malformed:
            print("  " + rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
