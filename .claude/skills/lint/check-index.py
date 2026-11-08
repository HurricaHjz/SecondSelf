#!/usr/bin/env python3
"""Index-consistency census: wiki/index.md against the pages on disk.

Lint Step 1's index comparison, as a script rather than an agent Read of the index plus a glob
and a hand comparison — the "re-derive a count by hand" the lint Routing note forbids. This is that comparison as a
script, so the agent reads a report instead of counting.

The rules are deep-lint's, not new ones: `.claude/skills/deep-lint/audit-pools.py` already
computes index consistency, and this script reuses its definitions so the two cannot drift.
  - the index is `wiki/index.md`; the pages are every `wiki/**/*.md` except `wiki/index.md`
    and `wiki/log.md` (matched on the relative path, so a nested page called index.md
    elsewhere under wiki/ is still a page — audit-pools.py's INDEX_REL / LOG_REL rule);
  - an index ENTRY is a list line whose first item is a wikilink, then an em-dashed line of
    description — the format the index's own header states; fenced blocks, inline code spans
    and HTML comments are stripped first, so the example in that header, which is written
    inside a code span, is not read as an entry;
  - a target resolves the way Obsidian resolves it: on the basename, with or without the
    `.md` extension, case-folded (audit-pools.py's link_key);
  - a page's frontmatter `aliases:` count as resolutions on BOTH sides — an entry naming an
    alias is not dangling, and a page registered under an alias is not unindexed. (Deliberate
    departure: audit-pools.py applies aliases to the dangling side only, which reports a page
    registered under its alias as unindexed. The banner says the alias rule is on.)

Three lists, each with its count:
  UNINDEXED   pages on disk that no index entry registers;
  DANGLING    index entries whose target is no page on disk (nor any alias);
  DUPLICATE   the same target registered by more than one entry.

`SCANNED: <pages> pages · <entries> index entries` is the run's own positive control (§11):
zero findings with a zero scanned count is a broken probe, never a clean index.

A broken premise prints one plain `PROBE FAILED: …` line and exits 2 — a root that is not a
vault (no raw/ + wiki/, on stderr, the 2026-08-26 standard), a missing wiki/index.md, an
index that registers nothing, no pages on disk, an unreadable page. An unknown option is
refused with exit 2 rather than ignored.

Stdout only: this script never creates, modifies, moves or deletes a file.

Usage:
  python3 check-index.py [--vault ROOT]
  exit 0 = the probe ran (findings or none) · exit 2 = broken premise
"""
import argparse
import glob
import os
import re
import sys

INDEX_REL = "wiki/index.md"
LOG_REL = "wiki/log.md"
ENTRY_RE = re.compile(r"^[ \t]*[-*][ \t]*!?\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]", re.M)


def stdout_utf8():
    """Make stdout encode any page name this script prints.

    Without it an ascii stdout (PYTHONIOENCODING, a bare C locale on some builds) turns a
    unicode page name into a traceback and exit 1, which reads as neither a finding nor a
    probe failure.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


def assert_vault_root(root):
    """A root must hold raw/ AND wiki/ or the census refuses to run.

    The 2026-08-26 standard, closed for the capture layer and swept across this directory on
    2026-09-07: fail loud on stderr, never a wrong-tree scan reported as a clean index.
    """
    if not all(os.path.isdir(os.path.join(root, d)) for d in ("raw", "wiki")):
        print(f"PROBE FAILED: {root} is not a vault root (no raw/ or wiki/)", file=sys.stderr)
        raise SystemExit(2)
    return root


def read_text(path):
    """Read a file as UTF-8, dropping a BOM and normalising CRLF; bad bytes are replaced.

    A BOM or a CRLF line ending would otherwise defeat the frontmatter match and drop that
    page's aliases, which would report a registered page as dangling.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    return raw.decode("utf-8-sig", "replace").replace("\r\n", "\n")


def strip_noise(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)      # fenced code blocks
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)     # HTML comments
    text = re.sub(r"`[^`\n]*`", " ", text)                  # inline code spans
    return text


def link_key(target):
    """Obsidian resolves on the basename, with or without the extension (audit-pools.py)."""
    key = os.path.basename(target.strip().rstrip("\\").split("#", 1)[0].strip()).casefold()
    return key[:-3] if key.endswith(".md") else key


# The alias reader below is kept byte-identical to check-links.py's (the lint suite compares them).
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


ALIASES_KEY_RE = re.compile(r"^aliases[ \t]*:", re.M)


def frontmatter_aliases(block):
    """(aliases, reason) for one frontmatter block: `aliases:` read as YAML reads it, a one-line flow
    list on the key's line or the line below it, or a block list of one-line `-` items, empty and
    null entries dropped. A reason means the value is malformed, spread over more than one line (a
    block scalar, a wrapped list, an item continued below), a mapping, or the key repeats: it gives
    no alias, never a guess. No key, a null, an empty value and a single one-line scalar give none
    and no reason."""
    keys = list(ALIASES_KEY_RE.finditer(block))
    if not keys:
        return [], None
    if len(keys) > 1:
        return [], "a duplicated aliases: key"
    kind, values, reason = parse_key_value(block, keys[0].end())
    if reason:
        return [], reason
    if kind == "map":
        return [], "a mapping, not a list"
    if kind != "seq":
        return [], None
    return [v.strip() for v in values if v is not None and v.strip()], None


def page_aliases(text):
    """Frontmatter aliases through check-links.py's reader above: a quoted alias may carry a
    comma, and a malformed list gives none (check-links.py reports it)."""
    fm = re.match(r"\A---\n(.*?)\n---", text, re.S)
    if not fm:
        return []
    return frontmatter_aliases(fm.group(1))[0]


def main():
    stdout_utf8()
    ap = argparse.ArgumentParser(
        description="Index-consistency census: wiki/index.md against the pages on disk.")
    ap.add_argument("--vault", default=".", help="vault root (default: the current directory)")
    args = ap.parse_args()

    root = assert_vault_root(os.path.abspath(os.path.expanduser(args.vault)))
    index_path = os.path.join(root, "wiki", "index.md")
    if not os.path.isfile(index_path):
        print(f"PROBE FAILED: no {INDEX_REL} under {root}")
        return 2

    paths = sorted(os.path.normpath(p) for p in
                   glob.glob(os.path.join(root, "wiki", "**", "*.md"), recursive=True))
    try:
        texts = {p: read_text(p) for p in paths}
    except OSError as exc:
        print(f"PROBE FAILED: cannot read a wiki page: {exc}")
        return 2

    # stem -> every page carrying it. Two folders may hold the same stem (a benchmark page and
    # its source page, say); a stem -> one-path map drops all but one, and an unindexed sibling
    # then disappears from the finding instead of being reported (audit-pools.py's note).
    on_disk, names, aliased = {}, {}, {}
    for p in paths:
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        if rel in (INDEX_REL, LOG_REL):
            continue
        stem = link_key(rel)
        on_disk.setdefault(stem, []).append(rel)
        names.setdefault(stem, []).append(rel)
        for alias in page_aliases(texts[p]):
            key = link_key(alias)
            names.setdefault(key, []).append(rel)
            aliased.setdefault(rel, []).append(key)
    pages_on_disk = sum(len(rels) for rels in on_disk.values())
    if not pages_on_disk:
        print("PROBE FAILED: wiki directory holds no pages besides the two registries")
        return 2

    entries = [link_key(t) for t in ENTRY_RE.findall(strip_noise(texts[index_path]))]
    if not entries:
        print(f"PROBE FAILED: {INDEX_REL} registers no page — the index probe is broken")
        return 2
    registered = set(entries)

    unindexed = sorted(rel for stem, rels in on_disk.items() for rel in rels
                       if stem not in registered
                       and not any(a in registered for a in aliased.get(rel, [])))
    dangling = sorted(name for name in registered if name not in names)
    duplicates = sorted({name for name in entries if entries.count(name) > 1})
    shared = sorted(stem for stem, rels in on_disk.items() if len(rels) > 1)

    print(f"SCANNED: {pages_on_disk} pages · {len(entries)} index entries "
          f"({len(registered)} distinct targets; frontmatter aliases count as a resolution "
          "on both sides)   (nonzero totals = probe ran)")
    print(f"UNINDEXED PAGES: {len(unindexed)}")
    for rel in unindexed:
        print("  " + rel)
    print(f"DANGLING INDEX ENTRIES: {len(dangling)}")
    for name in dangling:
        print("  " + name)
    print(f"DUPLICATE INDEX ENTRIES: {len(duplicates)}")
    for name in duplicates:
        print(f"  {name} · {entries.count(name)} entries")
    # Information, not a finding: one entry registers every page sharing that stem, so a shared
    # stem is where "registered" covers more than one file.
    print(f"shared stems (information, not a finding): {len(shared)}")
    for stem in shared:
        print(f"  {stem} · {', '.join(on_disk[stem])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
