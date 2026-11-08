#!/usr/bin/env python3
"""check-tool-markup.py — tool-call markup of the model harness leaked into wiki pages (lint Step 2).

Stdout-only by construction: it reads pages and prints; it writes no file and edits no page. Its
report goes to stdout; a broken premise goes to stderr, as with lint's other checks.

Why (register entry 2026-09-17): a compile lane ended every page it created with a leaked closing tag
of the harness's tool-call markup, one page with a second leaked tag above it, and the lane's own
output gate passed them all; only the independent verify leg caught them. Three callers run this
check: the compile lane's output gate, over every wiki page the lane created or updated, before its
report; the ingest skill's Step 7 self-check, over the run's whole output set, shared-page changes
applied at merge included; routine lint (and deep-lint, which runs lint's pipeline), over the whole
wiki, report-only. It detects; it never edits a page.

What counts as a tag
  An angle bracket, an optional slash, then an element name that is invoke, parameter,
  function_calls, function_results or content, or that carries the antml namespace prefix (any
  name after it), compared without regard to case, followed by whitespace of any kind, a slash, a
  closing angle bracket or the end of the page. Attributes, a self-closing slash and a missing
  closing bracket change nothing, so a truncated leak still counts. A name that only begins with a
  listed one's letters (parameters, content-type) is another name. A tag spans from its angle
  bracket to the first closing angle bracket after its name (or to the end of the name where none
  follows); that span is what must lie inside code for the tag to be exempt.

The code rule (the strict policy, owner decision of 9 October 2026)
  Only two things are code: the lines inside a plain fence, and a one-line code span in a plain
  paragraph on a line outside every excluded context; neither counts on a line of the page's YAML
  frontmatter (below). Everything else is prose and is scanned, a tag in an HTML comment included.
  The policy takes the visible error: an unusual way of quoting a tag gives a false hit, which is
  rewritten as plain code, never a missed leak. Each condition below therefore only ever removes
  protection.

  Plain fence.
    Opening line: at most three spaces (no tab), then three or more backticks or three or more
      tildes; after a backtick run the rest of the line holds no backtick. Its indentation is k.
    Closing line: the first later line that is, after leading whitespace, a run of the same
      character at least as long followed only by spaces or tabs. It closes the fence when its
      indentation is k to three spaces, no tab. Under an opening line at the margin (k = 0) such a
      run indented four columns or more is ordinary content; otherwise a run at any other
      indentation breaks the fence.
    Every non-blank line before the closing line must be indented at least k columns (a tab
      advancing to the next multiple of four), or the fence is broken.
    The lines strictly between the opening and closing lines are code. The opening line (its info
      string) and the closing line are scanned.
    A fence that is broken or never closed protects nothing, and from its opening line to the end
      of the page nothing is code: no fence opens and no code span protects (a renderer may hold
      those lines as code, where a backtick is literal and pairs with nothing). The same holds from
      a fence-shaped line that is not a plain opening line (one indented by a tab or by four spaces
      or more, or behind a list marker), and from a fence-shaped line that sits inside raw HTML
      (below). A fence-shaped line behind a block-quote marker is simply prose, on a line in an
      excluded context (below).
  One-line code span.
    Prose lines group into paragraphs: maximal runs of consecutive non-blank lines, a plain
      fence's lines ending one. Scanning a paragraph from the left, outside raw HTML and off the
      lines of an HTML stretch (below): a backslash before an ASCII punctuation character makes
      that character literal; a run of n backticks opens a span that the next run of exactly n
      backticks on the same line closes. The text between the two runs is a one-line code span.
    A paragraph's spans are code only when the paragraph is plain: (a) every backtick run in it
      has its closer on its own line (a run left open could pair across lines, which makes a
      multi-line span, or shift every pairing after it); (b) no span holds a pipe (a table cell
      boundary would cut it); (c) outside its spans the paragraph holds no angle bracket followed
      by a non-blank character, and does not begin inside raw HTML (raw HTML, an autolink or a
      comment can swallow a backtick); (d) outside its spans it holds no "](", "][", "[^" and no
      "]:" except as "]]:" (a link destination, a reference label, a footnote or a definition can
      swallow a backtick), and no wikilink (a page name between doubled square brackets) holding a
      backtick; (e) outside its spans it holds no "%%" (an Obsidian comment can swallow a
      backtick). A paragraph failing any of these has no code at all.
    In a plain paragraph a span is code only when its own line lies outside every excluded
      context, the places a renderer may hold as code, where a backtick is literal. A line's opening
      run is the stretch before its first character that is not a space, a tab, a block-quote
      marker (">") or a list marker ("-", "+" or "*", or one to nine digits and "." or ")", each
      followed by a space, a tab or the line end). The excluded contexts: (f) a line whose opening
      run holds a block-quote marker (any block quote, a block-quoted fence included); (g) a line
      whose opening run holds a tab or four spaces in a row (indented code, in a list item or not);
      (h) every line from a fence that is broken or never closed, or from a fence-shaped line that
      opens no plain fence, to the end of the page (above).
  Raw HTML (it never holds code, and decides where fences may open).
    An HTML stretch: from an HTML-block line (one whose first character after its indentation,
      block-quote markers and list markers is an angle bracket followed by a letter, a slash, an
      exclamation mark or a question mark) to the next blank line. A line of a stretch is read as
      HTML, not Markdown: no backslash escape and no backtick run is read on it, so neither can
      hide an opener there, and every angle bracket on it is tried as one.
    A raw region opens, on a line of a stretch or in prose outside a span, at a comment "<!--", a
      processing instruction "<?", a CDATA section "<![CDATA[" or a declaration "<!" and a letter;
      and at the start of an HTML-block line at a pre, script, style or textarea element (its name
      followed by a space, a tab, ">" or the line end). Its end marker: for a comment the first
      "-->" after its "<!" (so "<!-->" and "<!--->" close at once); otherwise the first "?>", "]]>"
      or ">" after its opener, or the first closing tag of any of the four elements. A "<!--" inside
      a processing instruction, a CDATA section, a declaration or an element opens a comment as
      well (a browser ends the first three at their first ">"); one whose "-->" lies outside that
      region carries the region to the page end.
    A region ends at its end marker only where the marker lies on the region's opening line, or
      where the region opens a block at the margin: its opener is the first character of a line
      that no stretch runs into (the line above is blank, absent or outside every stretch), a block
      CommonMark ends at the line holding the marker, blank lines between included. Anywhere else
      the paragraph or block holding the region may end first (at a blank line, at the end of a
      block quote or list item, at a block that interrupts a paragraph), a renderer then passes the
      marker on as escaped text that closes nothing, and the region runs to the end of the page; so
      does a region with no marker. Where a region opened on a line of a stretch ends partway along
      a line, the rest of that line is read as a line of a stretch.
  YAML frontmatter (it never holds code).
    A page opens frontmatter when its first line is three hyphens, the frontmatter delimiter, and the
      frontmatter runs to the first later line of the same shape. Spaces or tabs after the hyphens
      are allowed on either line: a detection, right or wrong, only ever removes protection (below).
      A page with no such later line has no frontmatter and is read as above.
    Frontmatter is YAML, not Markdown: a backticked value is no code span and a block scalar holding
      a fence is no fence, so every tag on its lines, the two delimiter lines included, is scanned.
    A tag after the frontmatter is code only where two readings both hold it as code: the whole page
      read as above, as though the frontmatter were Markdown, and the body read alone from the line
      after the closing delimiter, as though the page began there. The first keeps every condition
      the frontmatter's lines place on the body (a fence left broken, a raw region left open, a
      paragraph run on from the closing delimiter), so the frontmatter rule never protects a line the
      whole-page reading leaves bare; the second keeps a fence opened inside the frontmatter from
      protecting a body line, which a renderer that honours the frontmatter reads afresh.

  Residuals, outside the rule: Obsidian's inline math between dollar signs is not modelled, so a
  backtick inside such math is still paired; a guard on dollar signs would void every paragraph
  that mixes prices with code spans, and Obsidian's exact math rule is not established here. Where a
  comment or an HTML block ends is taken from CommonMark and the HTML parser; Obsidian's own reading
  of either is not established here. An element a browser hides without a comment (a script, a
  template, a hidden attribute) is not followed: only raw regions are. Whether a renderer honours a
  frontmatter block whose YAML it cannot parse, or whose delimiter carries trailing blanks, is not
  established here; the two readings make either answer safe. A clean exit means only "no
  named tag outside code" as defined here: nothing about a truncated page, a stray fence that hides
  prose, or broken frontmatter.

Cost: a page holding no tag opening gets no further pass, and one with frontmatter gets a second pass
over its body; one page is in memory at a time.

Controls, in memory, before any page is read: pages that must fire on a stated line and pages that
must stay quiet, listed on the CONTROL line. A control that misbehaves is PROBE FAILED (exit 2).

Usage (from the vault root):
  python3 .claude/skills/lint/check-tool-markup.py [--vault ROOT] --all
  python3 .claude/skills/lint/check-tool-markup.py [--vault ROOT] --files PAGE [PAGE ...]
  ROOT defaults to the vault this script ships in (the directory holding its .claude/), so a lane
  granted the script and its own pages, but not the vault root, can run it; either way a ROOT
  without raw/ and wiki/ is refused. A relative PAGE resolves against the current directory. Give
  pages as arguments, never through xargs or find -exec, which run nothing on an empty list.
  stdout: `path:line: <tag as found>` per hit (a line ending inside a tag prints as \\n, other
  control characters as \\xNN), `cannot check <path> (<reason>)`, `incomplete scan: <path>
  (<reason>)`, then a CONTROL line, a CANDIDATES line and the summary `tool-markup: <n> pages
  checked · <h> hits ...`.
  stderr: a broken premise only (`PROBE FAILED: ...`), with stdout empty.
  exit 0 clean · 1 hits · 2 a broken premise, a page it cannot check (one it cannot read, or not a
  regular file), an empty selection, or with --all an incomplete scan; 2 takes precedence over hits.

The walk (--all)
  Every entry under wiki/ is classified by a stat that follows symbolic links: a directory is
  entered (each real directory once), any other entry whose name ends in .md, in any case, is a
  page, and anything else is passed over. A directory it cannot list, a listing cut short, and an
  entry it cannot classify (a link whose target is missing, denied or a loop) each print
  `incomplete scan:` and make the exit 2. os.walk is not used: it files an entry whose
  classification fails as a file name, which a page filter would then drop without a word.
"""
import errno
import os
import re
import sys
from bisect import bisect_right
from stat import S_ISDIR, S_ISREG

USAGE = ("usage: check-tool-markup.py [--vault ROOT] (--all | --files PAGE [PAGE ...])   "
         "(exit 0 clean · 1 hits · 2 broken premise, unreadable page, empty selection or incomplete scan)")

NAMES = ("invoke", "parameter", "function_calls", "function_results", "content")
PREFIX = "antml:"
TAG = re.compile("</?(?:" + re.escape(PREFIX) + r"[A-Za-z0-9_.:-]*|" + "|".join(NAMES) + r")(?=[\s/>]|\Z)",
                 re.I)
SHOWN = 300           # characters of a tag printed before it is cut (set by judgement, unmeasured)
TAB_STOP = 4          # CommonMark 0.31.2 section 2.2: a tab advances to the next multiple of four
ASCII_PUNCT = frozenset("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")

# A fence-shaped line: leading whitespace and list markers, then a fence run (a backtick run with
# no backtick after it, or a tilde run). A plain opening line has at most three spaces and nothing
# else before its run.
FENCE_SHAPED = re.compile(r"[ \t]*(?:(?:[-+*]|[0-9]{1,9}[.)])[ \t]+)*(?:`{3,}[^`]*|~{3,}.*)\Z")
# Three spaces, three characters: CommonMark 0.31.2 section 4.5's fence limits, kept as the plain fence's.
PLAIN_OPEN = re.compile(r"( {0,3})(`{3,}(?=[^`]*\Z)|~{3,})")
LIST_MARKER = re.compile(r"(?:[-+*]|[0-9]{1,9}[.)])(?=[ \t]|\Z)")
HTML_BLOCK_NEXT = re.compile(r"[A-Za-z/!?]")
TYPE1_OPEN = re.compile(r"<(?:pre|script|style|textarea)(?=[ \t>\n]|\Z)", re.I)   # the name may end its line
TYPE1_CLOSE = re.compile(r"</(?:pre|script|style|textarea)>", re.I)
FRONTMATTER = re.compile(r"---[ \t]*\Z")              # a frontmatter delimiter line (the docstring's YAML frontmatter)


def probe_failed(message):
    """One line on stderr, exit 2: the lint directory's fail-loud premise convention."""
    print("PROBE FAILED: " + message, file=sys.stderr)
    raise SystemExit(2)


# ------------------------------------------------------------------------------ the reader ----

def leading(line):
    """(columns, has_tab, index of the first non-blank character) of a line's indentation."""
    col, i, tab = 0, 0, False
    while i < len(line) and line[i] in " \t":
        if line[i] == "\t":
            tab = True
            col += TAB_STOP - col % TAB_STOP
        else:
            col += 1
        i += 1
    return col, tab, i


def after_containers(line):
    """Index of the first character after indentation, block-quote markers and list markers."""
    i = 0
    while True:
        j = i
        while j < len(line) and line[j] in " \t":
            j += 1
        if j < len(line) and line[j] == ">":
            i = j + 1
            continue
        m = LIST_MARKER.match(line, j)
        if m:
            i = m.end()
            continue
        return j


def excluded_line(line):
    """True when the line's opening run (indentation, block-quote and list markers) holds a
    block-quote marker, a tab or four spaces in a row: rules (f) and (g) of the code rule."""
    i = 0
    while True:
        j = i
        while j < len(line) and line[j] in " \t":
            j += 1
        if "\t" in line[i:j] or "    " in line[i:j]:
            return True                                    # (g) indented code may start here
        if j < len(line) and line[j] == ">":
            return True                                    # (f) a block quote
        m = LIST_MARKER.match(line, j)
        if not m:
            return False
        i = m.end()


def html_block_line(line):
    p = after_containers(line)
    return line.startswith("<", p) and HTML_BLOCK_NEXT.match(line, p + 1) is not None


def blank(line):
    return not line.strip(" \t")


def fence_close(lines, i, char, length, k):
    """The closing line of the plain fence opened on line i, or None when it is broken or unclosed."""
    for j in range(i + 1, len(lines)):
        t = lines[j]
        if blank(t):
            continue
        col, tab, p = leading(t)
        run = len(t) - p - len(t[p:].lstrip(char)) if t.startswith(char, p) else 0
        if run >= length and blank(t[p + run:]):
            if not tab and k <= col <= 3:
                return j
            if k == 0 and col >= TAB_STOP:
                continue                                   # content under a fence at the margin
            return None                                    # a closer this rule cannot place
        if col < k:
            return None                                    # the fence's container may have ended
    return None


def inner_comments(text, start, end):
    """End offset of the raw region text[start:end] once each comment a "<!--" inside it opens is counted: one whose
    "-->" lies outside the region (or that never closes) carries the region to the page end."""
    pos = start + 1
    while True:
        c = text.find("<!--", pos, end)
        if c < 0:
            return end
        k = text.find("-->", c + 2)
        if k < 0 or k + 3 > end:
            return len(text)
        pos = k + 3


def region_end(text, pos, line_end, block_start, at_margin):
    """End offset (exclusive) of the raw region opening at text[pos], or None where none opens there. line_end ends
    the opener's line; block_start: the opener stands at the start of an HTML-block line, where an element may open;
    at_margin: it opens a block at the margin. A region whose end marker lies past its own line ends there only at
    the margin, and otherwise runs to the page end, as does one with no end marker (the docstring's raw HTML)."""
    if text.startswith("<!--", pos):
        k, n = text.find("-->", pos + 2), 3
    elif text.startswith("<?", pos):
        k, n = text.find("?>", pos + 2), 2
    elif text.startswith("<![CDATA[", pos):
        k, n = text.find("]]>", pos + 9), 3
    elif text.startswith("<!", pos) and pos + 2 < len(text) and text[pos + 2].isascii() and text[pos + 2].isalpha():
        k, n = text.find(">", pos + 2), 1
    elif block_start and TYPE1_OPEN.match(text, pos):
        m = TYPE1_CLOSE.search(text, pos)
        k, n = (-1, 0) if m is None else (m.start(), len(m.group()))
    else:
        return None
    if k < 0:
        return len(text)                                   # no end marker: to the page end
    end = k + n
    if not text.startswith("<!--", pos):
        end = inner_comments(text, pos, end)               # a browser ends "<?", "<![CDATA[" and "<!X" at a ">"
    if end <= line_end or at_margin:
        return end
    return len(text)                                       # the block holding it may end first: to the page end


class Paragraph:
    __slots__ = ("spans", "plain")

    def __init__(self, starts_in_raw):
        self.spans = []
        self.plain = not starts_in_raw


def scan_line(text, base, end, para, raw, block_start_at, protect, html_line, fresh):
    """Scan one prose line text[base:end] left to right; returns the raw region still open, as (its end, whether it
    opened on a line of a stretch), or None. On a line of an HTML stretch (html_line) no backslash escape and no
    backtick run is read: only angle brackets, each tried as an opener. Elsewhere spans join the paragraph's only
    when protect is true (the line lies outside every excluded context); either way they are paired, and their
    guards apply, as on any other line. fresh: no stretch runs into this line, so a region opening at its first
    character opens a block at the margin."""
    pos = base
    while pos < end:
        if raw is not None:
            if raw[0] > end:
                return raw
            # the region ends on this line: the rest of it is HTML too where the region opened on a line of a stretch
            pos, html_line, raw = raw[0], html_line or raw[1], None
            continue
        c = text[pos]
        if html_line and c != "<":
            k = text.find("<", pos, end)                   # HTML, not Markdown: no escape, no backtick run
            pos = end if k < 0 else k
        elif c == "\\" and pos + 1 < end and text[pos + 1] in ASCII_PUNCT:
            pos += 2
        elif c == "`":
            j = pos
            while j < end and text[j] == "`":
                j += 1
            n, q = j - pos, j
            while True:                                    # the next run of exactly n on this line
                q = text.find("`", q, end)
                if q < 0:
                    break
                r = q
                while r < end and text[r] == "`":
                    r += 1
                if r - q == n:
                    break
                q = r
            if q < 0:
                para.plain = False                         # (a) a run with no closer on its line
                pos = j
            else:
                if "|" in text[j:q]:
                    para.plain = False                     # (b) a span holding a pipe
                if protect:
                    para.spans.append((j, q))
                pos = q + n
        elif c == "<":
            if pos + 1 < end and not text[pos + 1].isspace():
                para.plain = False                         # (c) raw HTML, an autolink or a comment
            k = region_end(text, pos, end, pos == block_start_at, fresh and pos == base)
            if k is None:
                pos += 1
            else:
                raw = (k, html_line)
        else:
            two = text[pos:pos + 2]
            if two in ("](", "][", "[^") or (two == "]:" and not (pos > base and text[pos - 1] == "]")):
                para.plain = False                         # (d) link, reference, footnote, definition
            elif two == "[" * 2:                           # a wikilink's opening brackets
                k = text.find("]]", pos + 2, end)
                if k >= 0 and "`" in text[pos + 2:k]:
                    para.plain = False                     # (d) a wikilink holding a backtick
            elif two == "%%":
                para.plain = False                         # (e) an Obsidian comment
            pos += 1
    return raw


def frontmatter_end(lines):
    """Index of the line closing the page's YAML frontmatter, or None where the page opens none."""
    if not lines or not FRONTMATTER.match(lines[0]):
        return None
    for j in range(1, len(lines)):
        if FRONTMATTER.match(lines[j]):
            return j
    return None


def code_map(text, first=0):
    """(lines, line starts, fenced line ranges, code span ranges) of one page under the code rule, the page read
    from line index first as though it began there (the body read alone, after frontmatter)."""
    lines = text.split("\n")
    starts, pos = [], 0
    for line in lines:
        starts.append(pos)
        pos += len(line) + 1
    fenced, spans = [], []
    fences_on, html, raw, para = True, False, None, None   # raw: (end, opened on a line of a stretch) or None

    def close_paragraph():
        if para is not None and para.plain:
            spans.extend(para.spans)

    i = first
    while i < len(lines):
        line, base = lines[i], starts[i]
        if raw is not None and raw[0] <= base:
            raw = None
        in_raw = raw is not None
        if blank(line):
            html = False
            close_paragraph()
            para = None
            i += 1
            continue
        fresh = not html                                   # no stretch runs into this line
        if html_block_line(line):
            html = True
        if FENCE_SHAPED.match(line):
            opening = PLAIN_OPEN.match(line)
            if fences_on and opening and not html and not in_raw:
                run = opening.group(2)
                j = fence_close(lines, i, run[0], len(run), len(opening.group(1)))
                if j is not None:
                    close_paragraph()
                    para = None
                    fenced.append((i + 1, j - 1))          # line indexes of the content
                    i = j + 1
                    continue
            fences_on = False                              # broken, unclosed, or not a plain opening
        if para is None:
            para = Paragraph(in_raw)
        protect = fences_on and not excluded_line(line)    # (h), then (f) and (g)
        raw = scan_line(text, base, base + len(line), para, raw, base + after_containers(line), protect, html,
                        fresh)
        i += 1
    close_paragraph()
    spans.sort()
    return lines, starts, fenced, spans


def tag_end(text, m):
    k = text.find(">", m.end())
    return m.end() if k < 0 else k + 1


def shown(text, start, end):
    """The tag as found: cut at SHOWN characters; a line ending prints as \\n, other controls as \\xNN."""
    piece = text[start:end] if end - start <= SHOWN else text[start:start + SHOWN] + "…"
    return "".join("\\n" if ch == "\n" else ("\\x%02x" % ord(ch) if ord(ch) < 0x20 or ord(ch) == 0x7f else ch)
                   for ch in piece)


def in_code(reading, s, e, first, last):
    """True when the tag text[s:e], on line indexes first to last, lies wholly inside code on one reading."""
    fenced, spans, span_starts = reading
    if any(a <= first and last <= b for a, b in fenced):
        return True
    k = bisect_right(span_starts, s) - 1
    return k >= 0 and spans[k][0] <= s and e <= spans[k][1]


def find_hits(text):
    """[(line number, tag as found)] for every named tag on one page that is not wholly inside code. A tag on a line of
    the YAML frontmatter is never code; one after it must be code on the whole page and on the body read alone."""
    tags = list(TAG.finditer(text))
    if not tags:
        return []
    lines, starts, fenced, spans = code_map(text)
    readings = [(fenced, spans, [a for a, _ in spans])]
    fm = frontmatter_end(lines)
    if fm is not None:
        _, _, body_fenced, body_spans = code_map(text, fm + 1)
        readings.append((body_fenced, body_spans, [a for a, _ in body_spans]))
    hits = []
    for m in tags:
        s, e = m.start(), tag_end(text, m)
        first = bisect_right(starts, s) - 1
        last = bisect_right(starts, e - 1) - 1
        if (fm is None or first > fm) and all(in_code(reading, s, e, first, last) for reading in readings):
            continue
        hits.append((first + 1, shown(text, s, e)))
    return hits


def page_hits(text):
    """(candidates, hits): every named-tag opening on the page, and those outside code."""
    return len(TAG.findall(text)), find_hits(text)


# ------------------------------------------------------------------------------- controls ----

def _tag(name, close=False, attrs="", empty=False):
    """A tag built from its parts, so this file carries no literal one."""
    return "<" + ("/" if close else "") + name + attrs + ("/" if empty else "") + ">"


def control_pages():
    end = _tag("content", close=True)
    tick, ticks, fence, tilde = "`", "``", "```", "~~~"
    firing = [
        ("a trailing closing tag in prose", "# Title\n\nText.\n" + end + "\n", [4]),
        ("a prefixed tag with an unlisted name", "See " + _tag(PREFIX + "other_name", empty=True) + ".\n", [1]),
        ("a tag after a fence never closed", "Text.\n\n" + fence + "\nquoted\n" + end + "\n", [5]),
        ("a tag in a code span over two lines", "A span opens " + tick + "here\n" + end + tick + " there.\n", [2]),
        ("a tag inside an HTML comment", "Text <!-- " + end + " --> text.\n", [1]),
        ("a tag in an indented code block", "Para.\n\n    " + end + "\n", [3]),
        ("a tag in a block-quoted fence", "> " + fence + "\n> " + end + "\n> " + fence + "\n", [2]),
        ("a span after an escaped backtick", "a \\" + tick + end + tick + " b\n", [1]),
        ("a span in a paragraph holding raw HTML", _tag("span", attrs=' title="' + tick + '"') + " " + end
         + " " + tick + "\n", [1]),
        ("a list item's fence met by a deeper closing run", "- item\n  " + fence + "\n     " + fence
         + "\n  " + end + "\n  " + fence + "\n", [4]),
        ("a span after a tilde fence never closed", tilde + "\n" + tick + end + tick + "\n", [2]),
        ("a span in a block-quoted fence", "> " + tilde + "\n> " + tick + end + tick + "\n> " + tilde + "\n", [2]),
        ("a span in indented code", "    " + tick + end + tick + "\n", [1]),
        ("a fenced tag in a comment a backtick hid on an HTML line", "<div>\n" + tick + "<!--" + tick + "\n\n" + tilde
         + "\n" + end + "\n" + tilde + "\n-->\n", [5]),
        ("a spanned tag in a comment an escape hid on an HTML line", "<div>\n\\<!--\n\n" + tick + end + tick
         + "\n-->\n", [4]),
        ("a fenced tag after a comment its HTML block left open", "<div>\n<!--\n\n-->\n\n" + tilde + "\n" + end + "\n"
         + tilde + "\n", [7]),
        ("a fenced tag after a comment a pre element held", "<pre>\n<!--\n</pre>\n\n" + tilde + "\n" + end + "\n"
         + tilde + "\n", [6]),
        ("a fenced tag after an opener on a comment block's closing line", "<!--\n\n--> " + tick + "<!--" + tick
         + "\n\n" + tilde + "\n" + end + "\n" + tilde + "\n", [6]),
        ("a fenced tag in a pre element whose name ends its line", "<pre\n\n" + tilde + "\n" + end + "\n" + tilde
         + "\n</pre>\n", [4]),
        ("a fenced tag after a comment in prose over two lines", "Text <!-- a\nnote -->\n\n" + tilde + "\n" + end
         + "\n" + tilde + "\n", [5]),
        ("a tag in a frontmatter title's code span", "---\ntitle: " + tick + end + tick + "\n---\n", [2]),
        ("a tag in a frontmatter block scalar's tilde fence", "---\ndescription: |\n  " + tilde + "\n  " + end + "\n  "
         + tilde + "\n---\n", [4]),
        ("a body tag under a fence opened at the margin in frontmatter", "---\n" + tilde + "\n---\n" + end + "\n" + tilde
         + "\n", [4]),
    ]
    quiet = [                                              # (label, page, named-tag openings on it)
        ("a backtick fence", fence + "\n" + end + "\n" + fence + "\n", 1),
        ("a tilde fence", tilde + "\n" + end + "\n" + tilde + "\n", 1),
        ("a four-backtick fence holding a shorter run", "````\n" + fence + "\n" + end + "\n" + fence + "\n````\n", 1),
        ("a list item's fence", "- step\n  " + fence + "\n  " + end + "\n  " + fence + "\n", 1),
        ("single- and double-backtick spans", "Quote " + tick + end + tick + " and " + ticks + " " + end + " "
         + ticks + ".\n", 2),
        ("a table cell's span", "| a | b |\n|---|---|\n| x | " + tick + end + tick + " |\n", 1),
        ("names that only begin alike", _tag("parameters") + " " + _tag("content-type") + "\n", 0),
        ("a comment opener in an ordinary paragraph's span", "Text.\n" + tick + "<!--" + tick + "\n\n" + tilde + "\n"
         + end + "\n" + tilde + "\n", 1),
        ("a fenced tag after a comment block at the margin", "<!--\nnote\n\nmore\n-->\n\n" + tilde + "\n" + end + "\n"
         + tilde + "\n", 1),
        ("a fenced tag after a one-line comment in an HTML block", "<div>\n<!-- a note -->\n\n" + tilde + "\n" + end
         + "\n" + tilde + "\n", 1),
        ("a spanned and a fenced tag in the body after frontmatter quoting both shapes", "---\ntitle: " + tick + "x"
         + tick + "\ndescription: |\n  " + tilde + "\n  x\n  " + tilde + "\n---\n\nThe lane wrote " + tick + end + tick
         + ".\n\n" + tilde + "\n" + end + "\n" + tilde + "\n", 2),
        ("a spanned tag under a delimiter that is not on the first line", "\n---\ntitle: " + tick + end + tick
         + "\n---\n", 1),
    ]
    return firing, quiet


def run_controls():
    firing, quiet = control_pages()
    for label, text, lines in firing:
        candidates, hits = page_hits(text)
        if not candidates:
            probe_failed("in-memory control: the tag pattern missed the firing page (%s)" % label)
        if [line for line, _ in hits] != lines:
            probe_failed("in-memory control: the firing page (%s) gave hits on lines %s, want %s"
                         % (label, [line for line, _ in hits], lines))
    for label, text, want in quiet:
        candidates, hits = page_hits(text)
        if candidates != want or hits:
            probe_failed("in-memory control: the quiet page (%s) gave %d candidate(s) and %d hit(s), want "
                         "%d and 0" % (label, candidates, len(hits), want))
    return firing, quiet


# ---------------------------------------------------------------------------------- main ----

def parse_args(argv):
    """(vault, mode, files). An unknown flag or a stray word is refused, never read as the root."""
    vault, mode, files, rest = None, None, [], list(argv)
    while rest:
        arg = rest.pop(0)
        if arg in ("-h", "--help"):
            print(USAGE)
            raise SystemExit(0)
        if arg == "--vault" or arg.startswith("--vault="):
            if "=" in arg:
                value = arg.split("=", 1)[1]
            elif rest:
                value = rest.pop(0)
            else:
                probe_failed("--vault needs a directory argument")
            if vault is not None:
                probe_failed("--vault given twice (%s and %s)" % (vault, value))
            vault = value
        elif arg == "--all":
            if mode == "files":
                probe_failed("--all and --files are two selections: give one")
            mode = "all"
        elif arg == "--files":
            if mode == "all":
                probe_failed("--all and --files are two selections: give one")
            mode = "files"
            while rest and not rest[0].startswith("--"):
                files.append(rest.pop(0))
        else:
            probe_failed("unknown argument %s (%s)" % (arg, USAGE))
    return vault, mode, files


def default_root():
    """The vault this script ships in: <root>/.claude/skills/lint/check-tool-markup.py."""
    here = os.path.abspath(__file__)
    for _ in range(4):
        here = os.path.dirname(here)
    return here


def read_text(path):
    """UTF-8 with a BOM dropped; CRLF and CR read as line endings; bad bytes replaced. Only a regular
    file is read: a pipe would block the read and a device or a directory holds no page."""
    if not S_ISREG(os.stat(path).st_mode):
        raise OSError(errno.EINVAL, "not a regular file")
    with open(path, "rb") as fh:
        raw = fh.read()
    return raw.decode("utf-8-sig", "replace").replace("\r\n", "\n").replace("\r", "\n")


def display(path, root):
    """Vault-relative where the page sits under the root (directory links resolved on both sides,
    so a root reached through a symbolic link still matches), the path as given otherwise."""
    full = os.path.abspath(path)
    real = os.path.join(os.path.realpath(os.path.dirname(full)), os.path.basename(full))
    rel = os.path.relpath(real, os.path.realpath(root))
    return path if rel == os.pardir or rel.startswith(os.pardir + os.sep) else rel


def walk_wiki(wiki, root):
    """(pages, unlisted, unclassified) under wiki/, as the docstring's walk states: the pages in
    order (each directory's own pages by name, then its subdirectories by name), and the problems,
    each (path, reason): directories it could not list, entries it could not classify."""
    pages, unlisted, unclassified, seen = [], [], [], set()
    stack = [wiki]
    while stack:
        top = stack.pop()
        real = os.path.realpath(top)
        if real in seen:
            continue                                       # a directory reached again through a link
        seen.add(real)
        try:
            with os.scandir(top) as listing:
                entries = sorted(listing, key=lambda entry: entry.name)
        except OSError as exc:                             # cannot list, or the listing was cut short
            unlisted.append((display(top, root), exc.strerror or exc.__class__.__name__))
            continue
        subdirs = []
        for entry in entries:
            try:
                mode = entry.stat().st_mode                # follows a symbolic link to its target
            except OSError as exc:
                unclassified.append((display(entry.path, root),
                                     "cannot classify: " + (exc.strerror or exc.__class__.__name__)))
                continue
            if S_ISDIR(mode):
                subdirs.append(entry.path)
            elif entry.name.lower().endswith(".md"):
                pages.append(entry.path)
        stack.extend(reversed(subdirs))
    return pages, unlisted, unclassified


def main(argv):
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except (AttributeError, ValueError):
        pass
    vault, mode, files = parse_args(argv)
    root = vault if vault is not None else default_root()
    if not all(os.path.isdir(os.path.join(root, d)) for d in ("raw", "wiki")):
        probe_failed("%s is not a vault root (no raw/ or wiki/)" % root)
    if mode is None:
        probe_failed("no page selection: give --files PAGE [PAGE ...] or --all (%s)" % USAGE)
    firing, quiet = run_controls()
    root = os.path.abspath(root)

    unlisted, unclassified = [], []
    if mode == "all":
        pages, unlisted, unclassified = walk_wiki(os.path.join(root, "wiki"), root)
        selection = "--all over wiki/"
    else:
        pages, seen = [], set()
        for page in files:
            key = os.path.abspath(page)
            if key not in seen:
                seen.add(key)
                pages.append(page)
        selection = "--files, %d named" % len(pages)

    problems = unlisted + unclassified
    for where, reason in problems:
        print("incomplete scan: %s (%s)" % (where, reason))
    checked = hit_count = hit_pages = cannot = candidates = candidate_pages = 0
    for page in pages:
        where = display(page, root)
        try:
            text = read_text(page)
        except OSError as exc:
            cannot += 1
            print("cannot check %s (%s)" % (where, exc.strerror or exc.__class__.__name__))
            continue
        checked += 1
        found, hits = page_hits(text)
        candidates += found
        candidate_pages += 1 if found else 0
        if hits:
            hit_pages += 1
            hit_count += len(hits)
            for line, tag in hits:
                print("%s:%d: %s" % (where, line, tag))

    reasons = []
    if cannot:
        reasons.append("%d page(s) could not be checked" % cannot)
    if unlisted:
        reasons.append("%d director(ies) could not be entered" % len(unlisted))
    if unclassified:
        reasons.append("%d entr(ies) could not be classified" % len(unclassified))
    if not checked:
        reasons.append("an empty selection decides nothing")
    code = 2 if reasons else (1 if hit_count else 0)
    verdict = {0: "clean: no named tag outside code", 1: "hits"}.get(code, "cannot decide: " + "; ".join(reasons))
    print("CONTROL: in-memory: %d/%d firing pages caught on their lines (%s) · %d/%d quiet pages passed (%s)"
          % (len(firing), len(firing), "; ".join(label for label, _, _ in firing),
             len(quiet), len(quiet), "; ".join(label for label, _, _ in quiet)))
    print("CANDIDATES: %d named-tag opening(s) on %d page(s) · %d of them hits · the rest inside code "
          "(information, never a finding)" % (candidates, candidate_pages, hit_count))
    print("tool-markup: %d pages checked · %d hits on %d pages · %d cannot check · %d incomplete scan · "
          "selection %s · exit %d (%s)" % (checked, hit_count, hit_pages, cannot, len(problems), selection,
                                           code, verdict))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
