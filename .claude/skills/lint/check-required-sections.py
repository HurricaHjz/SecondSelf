#!/usr/bin/env python3
"""check-required-sections.py — the level-2 sections the table below requires per page type (lint Step 2).

Stdout-only by construction: reads pages, prints, writes nothing.

This probe enforces the section-structure contract independently of the links, orphans,
index and conflict checks (known-issues 2026-09-03). The required sections are:
  concept · entity · tool    -> ## Related
  model · benchmark          -> ## Appears in
  source                     -> ## Summary · ## Key Takeaways · ## Related
                                (a research-depth page carrying ## Citation: ## Related alone)
  synthesis · development    -> ## Sources Used
  map                        -> exempt (a navigational hub)
It is a subset of CLAUDE.md §4.3: `## Definition`, `## Key Points`, a model's or benchmark's
`## Related` and the `user` type's `## Related` are not checked. Any other `type:` (user, index,
log, a value outside §4.1) and a page with no frontmatter or no `type:` are counted on the scan
line, never checked. A section counts when a level-2 heading's text equals the name,
case-insensitively, outside fenced code blocks and HTML comments; a deeper heading, a heading
inside a fence and a bold line do not count. One finding line per page names its type, its
`depth:` where it carries one (so a reader sees whether a template, not a page, explains a whole
group), and every required section it lacks.

Research-depth pages (CLAUDE.md §4.3, the owner's clause of 2026-09-14): a `type: source` page at
`depth: research` may carry the ingest skill's research template sections in place of `## Summary`
and `## Key Takeaways`; `## Related` stays mandatory (the no-orphans rule). The ingest research
template opens with `## Citation`, and its genre note replaces only the paper-shaped middle sections,
so `## Citation` stays on both variants. This check therefore reads `depth:` before judging a page's
sections: a research-depth source page carrying a level-2 `## Citation` is required to carry
`## Related` alone, and is a finding only without it. The key is that property, never a list of
pages: a source page at another depth, or a research-depth page without a level-2 `## Citation`, is
checked against the full source row.

Provenance (CLAUDE.md §4.1: `sources:` is required on source and synthesis pages; register entry
of 2026-09-15): a `type: source` or `type: synthesis` page whose frontmatter `sources:` does not
parse to at least one non-empty entry is a finding, listed under `EMPTY SOURCES:` and setting the
same exit code as a missing section. The value is read with its YAML type by the shared reader
below (the one check-links.py reads aliases with), never as text. Empty means: the key absent;
`[]`, on the key's line or below a bare key; `null`, `~` or an empty value with no list under it;
a list whose every entry is an empty string (`[""]`, `- ''`), `null`, `~`, a blank `-` item or a
comment-only item. Never passing either: a mapping (`{}`, on the key's line or below it), a
nested collection, a value spread over more than one line (the second review of 2026-10-11: a flow
list or a quoted value wrapped over lines, a `|` or `>` block scalar, a `-` item with a line below
it deeper than the items, a `-` line or a deeper line continuing a one-line value), and a value
YAML cannot read (an unclosed quote or bracket, an empty entry between commas, an escape YAML
refuses or one naming no character, text after a closing quote or bracket, a duplicated `sources:`
key). Each is named on its line. A one-line flow list (`[a, "b, c"]`, on the key's line or the line
below it), a block list of one-line `-` items and a single one-line scalar path each pass with one
non-empty entry. A development page is outside this rule (§4.1 names source and synthesis only),
and no other type is read for it.

Whole block (register entry of 2026-09-15, its residual): the reader above is written by hand and
reads one key, so it can pass a block YAML refuses (`sources:[a]`, a tab before a list, a stray line
after a flow list, a broken line under another key). Each page's whole frontmatter block is therefore
read by PyYAML's BaseLoader as well, the reader the ingest lookup uses, and a block it refuses, that
is not a mapping, or that opens with a `---` line and never closes is listed under `MALFORMED
FRONTMATTER:`, setting the same exit code. This leg has no other reader, so where PyYAML cannot be
imported the check stops with `PROBE FAILED` and exit 2 before any list prints, and never reads clean.

Controls, in memory, before the scan: a development page with no `## Sources Used` must be
caught; the same page carrying the heading only inside a fenced block must still be caught; with
the heading present it must not be; a research-depth source page carrying `## Citation` and
`## Related` must be clean, the same page without `## Related` must be caught for `## Related` alone,
and the same page with `## Citation` renamed must be checked against the full source row; for
provenance, a synthesis page with `sources: []` and a source page with no `sources:` must be caught,
the same pages with a flow list and with a block list must pass, and a synthesis page with
`sources: {}`, with `[]` below a bare `sources:`, with an invalid escape, with a flow list followed
by a `- ` line, with a block item continued by an indented key and with a `|` block scalar must be
caught. A control that does not behave is PROBE FAILED (exit 2).

Usage (from the vault root):
  python3 .claude/skills/lint/check-required-sections.py [--vault ROOT]
  exit 0 = clean · 1 = findings ·
  2 = broken premise (not a vault root, no wiki page, an unreadable page, a control that did not
  behave)
"""
import collections
import os
import re
import sys

USAGE = ("usage: check-required-sections.py [--vault ROOT]   "
         "(exit 0 clean · 1 findings · 2 broken premise)")

REQUIRED = {
    "concept": ("Related",), "entity": ("Related",), "tool": ("Related",),
    "model": ("Appears in",), "benchmark": ("Appears in",),
    "source": ("Summary", "Key Takeaways", "Related"),
    "synthesis": ("Sources Used",), "development": ("Sources Used",),
}
EXEMPT = ("map",)
# The research-depth key (CLAUDE.md section 4.3, 2026-09-14): the page type, the depth and the section the
# ingest research template opens with; such a page is required to carry ## Related alone.
TEMPLATE_TYPE, TEMPLATE_DEPTH, TEMPLATE_SECTION = "source", "research", "Citation"
TEMPLATE_REQUIRED = ("Related",)
FM_RE = re.compile(r"\A---[ \t]*\n(.*?\n)---[ \t]*(?:\n|\Z)", re.S)
TYPE_RE = re.compile(r"^type:[ \t]*[\"']?([A-Za-z-]+)", re.M)
DEPTH_RE = re.compile(r"^depth:[ \t]*[\"']?([A-Za-z-]+)", re.M)
H2_RE = re.compile(r"^##[ \t]+(.+?)[ \t#]*$")
FENCE_RE = re.compile(r"^[ \t]*(```|~~~)")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)

# Provenance (CLAUDE.md §4.1): the page types that must carry `sources:`, and the entry texts that
# count as no entry at all.
SOURCES_TYPES = ("source", "synthesis")
SOURCES_KEY_RE = re.compile(r"^sources[ \t]*:", re.M)
NULL_WORDS = ("null", "~")
# The YAML reader below is kept byte-identical to check-links.py's (the lint suite compares them).

YAML_ESCAPES = {'"': '"', "\\": "\\", "/": "/", " ": " ", "0": "\0", "a": "\a", "b": "\b",
                "t": "\t", "\t": "\t", "n": "\n", "v": "\v", "f": "\f", "r": "\r", "e": "\x1b",
                "N": "\x85", "_": "\xa0", "L": chr(0x2028), "P": chr(0x2029)}
YAML_HEX_ESCAPES = {"x": 2, "u": 4, "U": 8}
PLAIN_RESERVED = "@`&*!|>%{}[]"
YAML_NULLS = ("null", "Null", "NULL", "~")


def line_end(text, j):
    """The index of the line break ending the line that holds text[j], or len(text)."""
    end = text.find("\n", j)
    return len(text) if end == -1 else end


def line_rest(text, j):
    """None when text[j:] up to the end of its line holds only blanks or a comment (a `#` after a
    blank), else the text it holds: YAML allows nothing else after a closed value."""
    rest = text[j:line_end(text, j)]
    tail = rest.lstrip(" \t")
    if not tail or (tail.startswith("#") and len(tail) < len(rest)):
        return None
    return tail


def next_content(text, j):
    """The index where the first line at or after text[j] holding more than blanks or a comment
    starts, or len(text)."""
    n = len(text)
    while j < n:
        end = line_end(text, j)
        body = text[j:end].lstrip(" \t")
        if body and not body.startswith("#"):
            return j
        j = end + 1
    return n


def is_item(body):
    """True when a line, its indentation removed, opens a block-list `-` item."""
    return body[:1] == "-" and body[1:2] in ("", " ", "\t")


def parse_quoted(text, i):
    """Decode the YAML quoted scalar whose opening quote is text[i], which must close on its own
    line: (value, end, None), `end` the index after its closing quote, or (None, i, reason). Double
    quotes take YAML's backslash escapes, and a \\x, \\u or \\U escape must name a Unicode character
    (no surrogate, nothing past U+10FFFF); single quotes double their quote. A line break before the
    closing quote, a backslash ending the line among them, is a reason: a value spans one line, so a
    quoted scalar YAML would fold over lines is malformed here, never folded."""
    quote, n = text[i], len(text)
    kind = "double" if quote == '"' else "single"
    j, buf = i + 1, []
    while j < n:
        ch = text[j]
        if ch == quote:
            if quote == "'" and j + 1 < n and text[j + 1] == "'":
                buf.append("'")
                j += 2
                continue
            return "".join(buf), j + 1, None
        if ch == "\n" or (quote == '"' and ch == "\\" and text[j + 1:j + 2] == "\n"):
            return None, i, f"an unclosed {kind} quote at the end of its line (a value spans one line)"
        if quote == '"' and ch == "\\":
            code = text[j + 1] if j + 1 < n else ""
            if code in YAML_HEX_ESCAPES:
                width = YAML_HEX_ESCAPES[code]
                digits = text[j + 2:j + 2 + width]
                if len(digits) != width or not all(c in "0123456789abcdefABCDEF" for c in digits):
                    return None, i, "a bad hexadecimal escape in a double-quoted value"
                point = int(digits, 16)
                if point > 0x10FFFF or 0xD800 <= point <= 0xDFFF:
                    return None, i, "an escape naming no Unicode character in a double-quoted value"
                buf.append(chr(point))
                j += 2 + width
                continue
            if code not in YAML_ESCAPES:
                return None, i, "an unknown escape in a double-quoted value"
            buf.append(YAML_ESCAPES[code])
            j += 2
            continue
        buf.append(ch)
        j += 1
    return None, i, f"an unclosed {kind} quote"


def read_flow_sequence(text, i, pairs=False):
    """Read the YAML flow sequence whose `[` is text[i], which must close on its own line: (values,
    reason, end), `end` the index after the closing bracket (or where reading stopped), reason None
    when the list is sound.

    A quoted entry is read by parse_quoted; a plain entry runs to the next comma or the closing
    bracket, a ` #` starting a comment, and a plain null (null, Null, NULL, ~) is None. A trailing
    comma is allowed, and after the closing bracket the line may hold only blanks or a comment. A
    line ending before the closing bracket (a comment inside the brackets reaches it too) is a
    reason: a value spans one line. Anything YAML would refuse or read as something other than a
    list of strings is a reason, never repaired; with pairs=True a plain entry carrying ": " (a
    one-pair mapping to YAML) is kept as its text."""
    values, eol = [], line_end(text, i)
    i += 1
    open_line = "no closing ] on its line (a value spans one line)"

    def skip(j):
        while j < eol and text[j] in " \t":
            j += 1
        return j

    def close(j):
        return values, (None if line_rest(text, j + 1) is None else "text after the closing ]"), j + 1

    while True:
        i = skip(i)
        if i >= eol or (text[i] == "#" and text[i - 1] in " \t[,"):
            return values, open_line, i
        ch = text[i]
        if ch == "]":
            return close(i)
        if ch == ",":
            return values, "an empty entry between commas", i
        if ch in "[{":
            return values, "a nested collection", i
        if ch in "\"'":
            value, i, reason = parse_quoted(text, i)
            if reason:
                return values, reason, i
        else:
            if ch in PLAIN_RESERVED:
                return values, f"a plain entry opening with {ch!r}, which YAML reserves", i
            follow = text[i + 1:i + 2]
            if (ch in "-?:" and follow in ("", " ", "\t", "\n")) or (ch in "?:" and follow in (",", "]")):
                return values, f"a plain entry opening with {ch!r} as an indicator, which YAML reads as structure", i
            j = i
            while j < eol and text[j] not in ",]" and not (text[j] == "#" and text[j - 1] in " \t"):
                if text[j] in "[{}":
                    return values, "a bracket inside a plain entry", i
                j += 1
            value = text[i:j].rstrip(" \t")
            if not pairs and (": " in value + " " or ":\t" in value):
                return values, "': ' inside a plain entry, which YAML reads as a mapping", i
            value = None if value in YAML_NULLS else value
            i = j
        values.append(value)
        i = skip(i)
        if i >= eol or (text[i] == "#" and text[i - 1] in " \t"):
            return values, open_line, i
        if text[i] == ",":
            i += 1
            continue
        if text[i] == "]":
            return close(i)
        return values, "text after a quoted entry", i


def parse_flow_sequence(text, i=0, pairs=False):
    """Parse the YAML flow sequence whose `[` is text[i]: (values, None) or (values so far, reason),
    as read_flow_sequence reads it."""
    values, reason, _end = read_flow_sequence(text, i, pairs)
    return values, reason


def parse_value(text, i, pairs=False, entry=False):
    """Read the YAML value that starts at text[i], blanks before it skipped: (kind, value, reason,
    end), `end` the line break ending the line the value opens on (or len(text)): a value spans one
    line.

    kind is "empty" (nothing, or only a comment, before the line's end), "null" (null, Null, NULL,
    ~), "str" (a quoted scalar), "plain" (a plain scalar), "seq" (a flow sequence, `value` its
    entries), "map" (a flow mapping, which no caller reads as a list) or "block" (a `|` or `>`
    block scalar, always with a reason: its text sits on the lines below). A value YAML would
    refuse, or one this reader does not resolve (an anchor, an alias, a tag), is a reason. A plain
    value carrying ": " is a mapping to YAML: a reason, unless `pairs` is set and the value is an
    `entry` of a list, which then keeps it as its text."""
    n = len(text)
    while i < n and text[i] in " \t":
        i += 1
    if i >= n or text[i] in "\n#":
        return "empty", None, None, line_end(text, i)
    ch = text[i]
    if ch == "[":
        values, reason, end = read_flow_sequence(text, i, pairs)
        return "seq", values, reason, line_end(text, end)
    if ch == "{":
        return "map", None, None, line_end(text, i)
    if ch in "\"'":
        value, end, reason = parse_quoted(text, i)
        if not reason and line_rest(text, end) is not None:
            reason = "text after a quoted value"
        return "str", value, reason, line_end(text, end)
    if ch in "|>":
        return "block", None, f"a {ch} block scalar, whose text spans the lines below (a value spans one line)", line_end(text, i)
    if ch in PLAIN_RESERVED or ch == ",":
        return "str", None, f"a value opening with {ch!r}, which YAML reserves or reads as an anchor, alias or tag", line_end(text, i)
    if ch in "-?:" and text[i + 1:i + 2] in ("", " ", "\t", "\n"):
        return "str", None, f"a value opening with {ch!r} as an indicator, which YAML reads as structure", line_end(text, i)
    end = line_end(text, i)
    value = re.split(r"[ \t]#", text[i:end], maxsplit=1)[0].rstrip(" \t")
    if (": " in value + " " or ":\t" in value) and not (pairs and entry):
        return "str", None, "': ' inside a plain value, which YAML reads as a mapping", end
    if value in YAML_NULLS:
        return "null", None, None, end
    return "plain", value, None, end


def parse_block_sequence(text, i, pairs=False):
    """Read the block list whose first `-` item opens the line at text[i]: (values, reason, end),
    `end` the index where the first line after the list starts (or len(text)), reason None when the
    list is sound. Each item is one line, its value read by parse_value; a null or empty item gives
    None. A nested collection or a block scalar in an item, any line deeper than the items (a value
    written below its `-`, a continuation, an indented key: a value spans one line), a line at the
    items' indentation that is not an item and an item shallower than the first are reasons. The
    list ends at the first line, blank and comment lines aside, shallower than its items."""
    values, n = [], len(text)
    indent = None
    while i < n:
        end = line_end(text, i)
        line = text[i:end]
        body = line.lstrip(" \t")
        lead = len(line) - len(body)
        if not body or body.startswith("#"):
            i = end + 1
            continue
        if indent is None:
            indent = lead
        if is_item(body) and lead == indent:
            kind, value, reason, end = parse_value(text, i + lead + 1, pairs, entry=True)
            if reason:
                return values, reason, i
            if kind in ("seq", "map"):
                return values, "a nested collection in a - item", i
            values.append(value if kind in ("str", "plain") else None)
        elif lead > indent:
            return values, "a line below a - item, deeper than the items (a value spans one line)", i
        elif lead == indent and indent > 0:
            return values, "a line at the list's indentation that is not a - item", i
        elif is_item(body):
            return values, "a - item shallower than the list", i
        else:
            return values, None, i
        i = end + 1
    return values, None, n


def parse_key_value(text, j, pairs=False):
    """Read the value of the mapping key whose colon ends at text[j], the key standing at the start
    of its line: on the key's own line or, when that holds nothing, on the one deeper line or the
    `-` items below it. (kind, value, reason) as parse_value gives them, a block list counting as a
    "seq". The value spans one line, a block list one line per item: the first line below it,
    blank and comment lines aside, must start at the left margin and open no `-` item, or it
    continues the value, which is then malformed (the second review of 2026-10-11)."""
    kind, value, reason, end = parse_value(text, j, pairs)
    after = end + 1
    if kind == "empty":
        k = next_content(text, after)
        if k >= len(text):
            return "empty", None, None
        if is_item(text[k:line_end(text, k)].lstrip(" \t")):
            kind = "seq"
            value, reason, after = parse_block_sequence(text, k, pairs)
        elif text[k] not in " \t":
            return "empty", None, None
        else:
            kind, value, reason, end = parse_value(text, k, pairs)
            after = end + 1
    if not reason:
        k = next_content(text, after)
        if k < len(text) and text[k] in " \t":
            reason = "text below the value, deeper than its key"
        elif k < len(text) and is_item(text[k:line_end(text, k)]):
            reason = "a - line below the value, which continues it"
    return kind, value, reason


def empty_entry(value):
    """True for an entry that names nothing: null, an empty string, `~` or the word null."""
    return value is None or value.strip() == "" or value.strip().lower() in NULL_WORDS


def sources_problem(block):
    """None when one frontmatter block's `sources:` parses to at least one non-empty entry, else
    the reason it counts as empty or unreadable (the docstring's list). The value is read by the
    shared YAML reader above, so its type decides: a list (flow or block) needs one non-empty
    entry, a scalar must name something, and a mapping, a nested collection, a value spread over
    more than one line (a block scalar included) or a value YAML cannot read never passes."""
    keys = list(SOURCES_KEY_RE.finditer(block))
    if not keys:
        return "no sources: key"
    if len(keys) > 1:
        return "a duplicated sources: key"
    key = keys[0]
    shown = re.split(r"[ \t]#", block[key.end():line_end(block, key.end())], maxsplit=1)[0].strip()
    kind, value, reason = parse_key_value(block, key.end(), pairs=True)
    if reason:
        return f"sources: {reason}"
    if kind == "seq":
        if not value:
            return "sources: []"
        return None if any(not empty_entry(v) for v in value) else "sources: a list of empty entries"
    if kind == "map":
        return "sources: a mapping, not a list"
    if kind == "empty":
        return "sources: an empty value with no list under it"
    if kind in ("str", "plain") and not empty_entry(value):
        return None
    return f"sources: {shown} (a null or empty value)" if shown else "sources: a null or empty value"


def provenance_problem(text):
    """(type, reason) for a source or synthesis page whose `sources:` counts as empty, else
    (type, None); a page of any other type, or with no frontmatter, is never read for it."""
    fm = FM_RE.match(text)
    if not fm:
        return None, None
    tm = TYPE_RE.search(fm.group(1))
    ptype = tm.group(1).lower() if tm else None
    if ptype not in SOURCES_TYPES:
        return ptype, None
    return ptype, sources_problem(fm.group(1))

CONTROL_MISSING = ("---\ntitle: \"Control\"\ntype: development\nconfidence: medium\n---\n\n"
                   "## Design\nA design with no sources section.\n\n## Related\n- the hub page\n")
CONTROL_FENCED = CONTROL_MISSING + "\n```\n## Sources Used\n```\n"
CONTROL_PRESENT = CONTROL_MISSING + "\n## Sources Used\n- the hub page\n"
CONTROL_TEMPLATE = ("---\ntitle: \"Control\"\ntype: source\ndepth: research\nconfidence: medium\n---\n\n"
                    "## Citation\nA reference.\n\n## Research Question\nA question.\n\n## Related\n- the hub page\n")
CONTROL_TEMPLATE_NORELATED = CONTROL_TEMPLATE.replace("\n## Related\n- the hub page\n", "\n")
CONTROL_UNSHAPED = CONTROL_TEMPLATE.replace("## Citation\n", "## Reference\n")
CONTROL_SYN_EMPTY = ("---\ntitle: \"Control\"\ntype: synthesis\nconfidence: medium\nsources: []\n---\n\n"
                     "## Answer\nx\n\n## Sources Used\n- the hub page\n")
CONTROL_SRC_ABSENT = CONTROL_TEMPLATE
PROVENANCE_CONTROLS = (
    (CONTROL_SYN_EMPTY, True, "synthesis page with sources: []"),
    (CONTROL_SRC_ABSENT, True, "source page with no sources:"),
    (CONTROL_SYN_EMPTY.replace("sources: []", "sources: [raw/1-articles/a.md, \"raw/2-papers/b, c.md\"]"),
     False, "synthesis page with a flow list"),
    (CONTROL_SRC_ABSENT.replace("confidence: medium\n", "confidence: medium\nsources:\n  - raw/1-articles/a.md\n"),
     False, "source page with a block list"),
    # Typed reading (register entry of 2026-09-15, the review that followed it): a mapping, an empty
    # list written below a bare key and an escape YAML refuses each passed a text-only reader.
    (CONTROL_SYN_EMPTY.replace("sources: []", "sources: {}"), True, "synthesis page with sources: {}"),
    (CONTROL_SYN_EMPTY.replace("sources: []", "sources:\n  []"), True, "synthesis page with [] below a bare sources:"),
    (CONTROL_SYN_EMPTY.replace("sources: []", "sources: \"\\q\""), True, "synthesis page whose sources: carries an invalid escape"),
    # One line per value (the second review of 2026-10-11): a value continued below its line, and a
    # block scalar, each passed a reader that folded lines.
    (CONTROL_SYN_EMPTY.replace("sources: []", "sources: [raw/1-articles/a.md]\n- raw/1-articles/b.md"), True,
     "synthesis page whose sources: flow list is followed by a - line"),
    (CONTROL_SYN_EMPTY.replace("sources: []", "sources:\n  - raw/1-articles/a.md\n    note: value"), True,
     "synthesis page whose sources: item is continued by an indented key"),
    (CONTROL_SYN_EMPTY.replace("sources: []", "sources: |\n  raw/1-articles/a.md"), True,
     "synthesis page whose sources: is a block scalar"),
)


def probe_failed(message):
    print(f"PROBE FAILED: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_yaml():
    """PyYAML. The whole-block leg has no other reader, so anything raised on the import is a failed
    premise: ImportError where PyYAML is absent, anything else where an install is broken."""
    try:
        import yaml
    except Exception as exc:
        probe_failed(f"PyYAML cannot be imported by {sys.executable or 'this python3'} ({exc.__class__.__name__}: {exc}); "
                     "the whole-block leg has no other reader, so install PyYAML for this python3 or run lint with one "
                     "that has it")
    missing = [part for part in ("load", "BaseLoader", "YAMLError") if not hasattr(yaml, part)]
    if missing:
        probe_failed(f"the module yaml at {getattr(yaml, '__file__', 'an unknown path')} lacks {', '.join(missing)}, "
                     "which the whole-block leg uses")
    return yaml


def block_refused(block, yaml):
    """Why a real YAML parser refuses one whole frontmatter block, or None when it reads a mapping.
    BaseLoader keeps every scalar a string, so nothing here depends on a value's type."""
    try:
        document = yaml.load(block, Loader=yaml.BaseLoader)
    except (yaml.YAMLError, ValueError, OverflowError, RecursionError) as exc:
        # an escape naming no character raises ValueError from PyYAML, never a YAMLError
        mark = getattr(exc, "problem_mark", None)
        where = f" at line {mark.line + 1} of the block" if mark else ""
        return f"{getattr(exc, 'problem', None) or 'does not parse'}{where}"
    return None if isinstance(document, dict) else "not a mapping"


# The forms the hand-written reader passes and YAML refuses (a differential on 97 forms, 2026-11-03),
# and one sound block: the leg's same-run control.
BLOCK_CONTROLS = (("title: x\nsources:[a]\n", True), ("sources: [a]\nbad\n", True), ("sources:\n\t- a\n", True),
                  ("foo: [x\nsources: [a]\n", True), ("title: \"x\"\nsources: [a, \"b, c\"]\n", False))
OPEN_RE, CLOSE_RE = re.compile(r"\A---[ \t]*\n"), re.compile(r"^---[ \t]*$", re.M)
# A block that never closes, and the three shapes that must not read as one: closed, closed and empty, and no block.
UNCLOSED_CONTROLS = (("---\ntitle: x\n\n## Related\n", True), ("---\ntitle: x\n---\n\n## Related\n", False),
                     ("---\n---\n", False), ("## Related\n", False))


def block_unclosed(text):
    """Whether a page opens a frontmatter block with a line --- that no later line --- closes. Such a page
    has no frontmatter for the readers here, so it would otherwise count as a page with no type."""
    opened = OPEN_RE.match(text)
    return bool(opened) and CLOSE_RE.search(text, opened.end()) is None


def parse_root(argv):
    """`--vault ROOT` or a positional root; an unknown flag is refused, never read as the root."""
    root, rest = None, list(argv)
    while rest:
        arg = rest.pop(0)
        if arg in ("-h", "--help"):
            print(USAGE)
            raise SystemExit(0)
        if arg == "--vault":
            if not rest:
                probe_failed("--vault needs a directory argument")
            arg = rest.pop(0)
        elif arg.startswith("--vault="):
            arg = arg.split("=", 1)[1]
        elif arg.startswith("-"):
            probe_failed(f"unknown option {arg} ({USAGE})")
        if root is not None:
            probe_failed(f"two roots given ({root} and {arg})")
        root = arg
    return root if root else "."


def read_text(path):
    """UTF-8 with a BOM dropped and CRLF normalised; bad bytes replaced, never fatal."""
    with open(path, "rb") as fh:
        raw = fh.read()
    return raw.decode("utf-8-sig", "replace").replace("\r\n", "\n")


def sections(body):
    """Casefolded level-2 heading texts outside fenced blocks and HTML comments."""
    found, fence = set(), False
    for line in COMMENT_RE.sub("", body).split("\n"):
        if FENCE_RE.match(line):
            fence = not fence
            continue
        if fence:
            continue
        m = H2_RE.match(line)
        if m:
            found.add(m.group(1).strip().casefold())
    return found


def check_page(text):
    """(type or None, depth or None, missing section names, template-shaped) for one page."""
    fm = FM_RE.match(text)
    if not fm:
        return None, None, (), False
    tm, dm = TYPE_RE.search(fm.group(1)), DEPTH_RE.search(fm.group(1))
    ptype = tm.group(1).lower() if tm else None
    depth = dm.group(1).lower() if dm else None
    have = sections(text[fm.end():])
    template = ptype == TEMPLATE_TYPE and depth == TEMPLATE_DEPTH and TEMPLATE_SECTION.casefold() in have
    required = TEMPLATE_REQUIRED if template else REQUIRED.get(ptype, ())
    missing = tuple(name for name in required if name.casefold() not in have)
    return ptype, depth, missing, template


def main():
    root = parse_root(sys.argv[1:])
    if not all(os.path.isdir(os.path.join(root, d)) for d in ("raw", "wiki")):
        probe_failed(f"{root} is not a vault root (no raw/ or wiki/)")

    if check_page(CONTROL_MISSING)[2] != ("Sources Used",):
        probe_failed("the in-memory development page with no ## Sources Used was not caught")
    if check_page(CONTROL_FENCED)[2] != ("Sources Used",):
        probe_failed("the in-memory page carrying ## Sources Used only inside a fence was not caught")
    if check_page(CONTROL_PRESENT)[2] != ():
        probe_failed("the in-memory page carrying ## Sources Used was read as missing it")
    if check_page(CONTROL_TEMPLATE)[2:] != ((), True):
        probe_failed("the in-memory research-depth source page carrying ## Citation and ## Related was not read as clean")
    if check_page(CONTROL_TEMPLATE_NORELATED)[2:] != (("Related",), True):
        probe_failed("the in-memory research-depth source page carrying ## Citation without ## Related was not caught")
    if check_page(CONTROL_UNSHAPED)[2:] != (("Summary", "Key Takeaways"), False):
        probe_failed("the in-memory research-depth source page without ## Citation was not checked against the full source row")
    for text, empty, what in PROVENANCE_CONTROLS:
        if (provenance_problem(text)[1] is not None) != empty:
            probe_failed(f"the in-memory {what} was read as {'carrying a source' if empty else 'empty'}")

    yaml = load_yaml()
    for block, refused in BLOCK_CONTROLS:
        if (block_refused(block, yaml) is not None) != refused:
            probe_failed(f"the in-memory block {block!r} was read as {'sound' if refused else 'refused'}")
    for page, unclosed in UNCLOSED_CONTROLS:
        if block_unclosed(page) != unclosed:
            probe_failed(f"the in-memory page {page!r} was read as {'closed' if unclosed else 'never closing'}")

    pages = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "wiki")):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if name.endswith(".md") and not name.startswith("."):
                pages.append(os.path.join(dirpath, name))
    if not pages:
        probe_failed(f"{os.path.join(root, 'wiki')} holds no .md page")

    checked, exempt, unchecked = collections.Counter(), 0, collections.Counter()
    findings, by_type, by_depth = [], collections.Counter(), collections.defaultdict(collections.Counter)
    template_total = provenance_total = 0
    empty_sources, malformed_blocks = [], []
    blocks_read = 0
    for path in pages:
        try:
            text = read_text(path)
        except OSError as exc:
            probe_failed(f"cannot read {os.path.relpath(path, root)} ({exc.__class__.__name__})")
        block = FM_RE.match(text)
        refused = None
        if block:
            blocks_read += 1
            refused = block_refused(block.group(1), yaml)
        elif block_unclosed(text):
            blocks_read += 1
            refused = "a frontmatter block that opens with --- and never closes"
        if refused:
            malformed_blocks.append((os.path.relpath(path, root).replace(os.sep, "/"), refused))
        prov_type, problem = provenance_problem(text)
        if prov_type in SOURCES_TYPES:
            provenance_total += 1
            if problem:
                empty_sources.append((os.path.relpath(path, root).replace(os.sep, "/"), prov_type, problem))
        ptype, depth, missing, template = check_page(text)
        if ptype in REQUIRED:
            checked[ptype] += 1
        elif ptype in EXEMPT:
            exempt += 1
        else:
            unchecked[ptype if ptype else "no type"] += 1
        template_total += 1 if template else 0
        if not missing:
            continue
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        findings.append((rel, ptype, depth, missing))
        by_type[ptype] += 1
        by_depth[ptype][depth if depth else "no depth"] += 1

    n_checked = sum(checked.values())
    if n_checked == 0:
        probe_failed("no page carries a type this check covers — a scan of nothing is not a clean vault")
    fmt = lambda counter: " · ".join(f"{k} {v}" for k, v in sorted(counter.items()))
    print(f"SCANNED: {len(pages)} pages | {n_checked} checked ({fmt(checked)}) | {exempt} maps exempt | "
          f"{sum(unchecked.values())} not checked ({fmt(unchecked) or 'none'})   (nonzero checked total = probe ran)")
    print("CONTROL: in-memory development page with no ## Sources Used -> caught; the heading only inside "
          "a fence -> caught; with the heading -> not a finding; a research-depth source page with ## Citation "
          "and ## Related -> clean, without ## Related -> caught, without ## Citation -> checked against the "
          "full source row")
    n_sections = sum(len(f[3]) for f in findings)
    breakdown = " · ".join(
        f"{t} {by_type[t]} ({fmt(by_depth[t])})" if set(by_depth[t]) != {"no depth"} else f"{t} {by_type[t]}"
        for t in sorted(by_type))
    print(f"MISSING REQUIRED SECTIONS: {len(findings)} page(s) · {n_sections} section(s)"
          + (f" | by type: {breakdown}" if findings else ""))
    for rel, ptype, depth, missing in findings:
        kind = f"{ptype} (depth {depth})" if depth else ptype
        print(f"  {rel} · {kind} · " + ", ".join(f"## {m}" for m in missing))
    print(f"RESEARCH-DEPTH TEMPLATE PAGES: {template_total} {TEMPLATE_TYPE} page(s) at depth {TEMPLATE_DEPTH} carry "
          f"## {TEMPLATE_SECTION} and are judged on ## Related alone (CLAUDE.md section 4.3, 2026-09-14)")
    print(f"EMPTY SOURCES: {len(empty_sources)} page(s) of {provenance_total} source and synthesis pages read "
          f"(CLAUDE.md section 4.1: sources: must parse to at least one non-empty entry)")
    for rel, ptype, problem in empty_sources:
        print(f"  {rel} · {ptype} · {problem}")
    print("CONTROL (provenance): in-memory synthesis page with sources: [] -> caught; a source page with no "
          "sources: -> caught; the same pages with a flow list and with a block list -> not findings; "
          "sources: {}, [] below a bare key and an invalid escape -> caught; a value continued below its "
          "line (a - line under a flow list, an indented key under an item) and a block scalar -> caught")
    print(f"MALFORMED FRONTMATTER: {len(malformed_blocks)} page(s) of {blocks_read} frontmatter blocks read by "
          f"PyYAML (nonzero total = the leg ran)")
    for rel, refused in malformed_blocks:
        print(f"  {rel} · {refused}")
    print(f"CONTROL (whole block): {sum(r for _b, r in BLOCK_CONTROLS)} in-memory blocks the hand-written reader "
          "passes -> refused; a sound block -> read; a block that never closes -> caught")
    return 1 if (findings or empty_sources or malformed_blocks) else 0


if __name__ == "__main__":
    sys.exit(main())
