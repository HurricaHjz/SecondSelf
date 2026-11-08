#!/usr/bin/env python3
"""check-orphans.py — inbound-link (orphan) census for the wiki layer.

Mechanises the one link check the lint skill still leaves to the agent
("Orphans are agent-checked", lint SKILL.md Step 2). A page is an ORPHAN when no
OTHER page carries a resolving page link to it. Exempt from being reported:
`index.md`, `log.md`, and every page under `maps/` — Maps of Content are
navigational entry points by design, not orphans.

Link rules are the ones in this directory's check-links.py, applied identically:
  - fenced code blocks, inline code spans and HTML comments are stripped first,
    so documentation examples are not links;
  - `log.md` is excluded as a link SOURCE (append-only history), so a page linked
    only from the log is still an orphan;
  - media embeds are classified by the same extension set, so an embedded image
    is never counted as a page link;
  - targets resolve as Obsidian does: page stems -> frontmatter aliases ->
    vault-relative paths (with or without .md) -> basename, case-insensitively;
  - the alias form and the section form both credit the same page;
  - a page linking to itself does not make itself non-orphan.
check-links.py is a top-level script — it reads argv and calls sys.exit while
being imported — so those rules are REPLICATED here rather than imported. The
suite beside this file runs both scripts over one fixture and fails if their link
counts diverge, which is what keeps the replica honest; exposing those rules as
functions there would retire the replica altogether.

Two deliberate differences from that replica, both narrower than they look:
  - RESOLUTION stops at the wiki layer. check-links.py asks only "does this
    target exist anywhere in the vault", because a link into assets/ or output/
    is live; an inbound-link census instead has to credit a wiki PAGE, so a
    target outside the wiki credits nothing. Link COUNTING is identical, which
    is what the suite's agreement leg asserts against check-links.py.
  - Bytes are decoded permissively, a BOM is dropped and CRLF is normalised, so a
    CRLF page's frontmatter aliases are still read. check-links.py reads strict
    UTF-8 without normalising, so those aliases are invisible to it and an aliased
    CRLF page reads as dead there; giving it the same reader removes the difference.

`index.md` counts as a link source, because the rule this implements is the graph
rule (no isolated nodes) and the catalogue is a node like any other. That makes
the bare orphan count weak on its own, so the run also reports how many pages the
catalogue alone reaches: an "index-only" page is one nothing but the catalogue
points at. That is information, not a finding.

A broken premise prints one plain `PROBE FAILED: …` line on stdout and exits 2
whatever `--format` says, so a JSON consumer keys on the exit code, never on
parsing that line.

Stdout only: this script never creates, modifies, moves or deletes a file.

Usage:
  python3 check-orphans.py [--vault ROOT] [--format text|json]
  exit 0 = the probe ran (findings or none) · exit 2 = broken premise
"""
import argparse
import glob
import json
import os
import re
import sys

# Obsidian treats these embed targets as media rather than page transclusions; kept
# byte-identical to check-links.py so both scripts classify a link the same way.
MEDIA_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf",
             ".mp3", ".wav", ".mp4", ".mov"}

LINK_RE = re.compile(r"(!?)\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]")


def stdout_utf8():
    """Make stdout encode any page name or separator this script prints.

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

    A BOM or a CRLF line ending would otherwise defeat the `\\A---\\n` frontmatter match and
    silently drop that page's aliases, which would report an aliased page as an orphan.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    return raw.decode("utf-8-sig", "replace").replace("\r\n", "\n")


def strip_noise(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)      # fenced code blocks
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)     # HTML comments
    text = re.sub(r"`[^`\n]*`", " ", text)                  # inline code spans
    return text


def frontmatter_block(text):
    m = re.match(r"\A---\n(.*?)\n---", text, re.S)
    return m.group(1) if m else ""


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


def collect_aliases(pages, texts):
    """alias -> page path through check-links.py's reader above: a quoted alias may carry a
    comma, and a malformed list gives none (check-links.py reports it)."""
    aliases = {}
    for p in pages:
        block = frontmatter_block(texts[p])
        if not block:
            continue
        for a in frontmatter_aliases(block)[0]:
            aliases[a] = p
    return aliases


def build_indexes(pages):
    stems, lower_stems = {}, {}
    for p in pages:
        s = os.path.splitext(os.path.basename(p))[0]
        stems.setdefault(s, []).append(p)
        lower_stems.setdefault(s.lower(), []).append(p)
    return stems, lower_stems


def resolve(target, root, stems, lower_stems, aliases, page_set):
    """Return the wiki pages a link target credits (empty when it leaves the wiki layer).

    Resolution order mirrors check-links.py exactly: stem, alias, vault-relative path,
    root doc, then case-folded basename. A stem shared by several pages credits all of
    them — the permissive reading check-links.py already takes for ambiguous basenames.
    """
    t = target.strip().rstrip("\\")     # a table-escaped pipe leaves a trailing backslash
    if not t or t.startswith("#"):
        return []                        # self-heading link
    t = t.split("#", 1)[0].strip()
    if not t:
        return []
    if t in stems:
        return stems[t]
    if t in aliases:
        return [aliases[t]]
    if "/" in t or t.endswith(".md"):
        for cand in (t, t + ".md"):
            full = os.path.normpath(os.path.join(root, cand))
            if full in page_set:
                return [full]
            if os.path.exists(full):
                return []                # resolves, but outside the wiki layer
    full = os.path.normpath(os.path.join(root, t + ".md"))
    if full in page_set:
        return [full]
    if os.path.exists(full):
        return []
    base = os.path.basename(t).lower()
    for key in (base, os.path.splitext(base)[0]):
        if key in lower_stems:
            return lower_stems[key]
    return []


def is_exempt(rel):
    """index.md, log.md and every maps/ page are never reported as orphans."""
    parts = rel.split(os.sep)
    return parts[-1] in ("index.md", "log.md") or (len(parts) > 1 and parts[1] == "maps")


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
    ap = argparse.ArgumentParser(description="Orphan (no-inbound-link) census for the wiki layer.")
    ap.add_argument("--vault", default=".", help="vault root (default: the current directory)")
    ap.add_argument("--format", choices=("text", "json"), default="text",
                    help="output format (default: text)")
    args = ap.parse_args()

    root = assert_vault_root(os.path.abspath(os.path.expanduser(args.vault)))
    wiki = os.path.join(root, "wiki")
    if not os.path.isdir(wiki):   # unreachable while the root guard runs first; kept as depth
        print(f"PROBE FAILED: no wiki directory under {args.vault} (wrong root?)")
        return 2

    pages = sorted(os.path.normpath(p) for p in
                   glob.glob(os.path.join(wiki, "**", "*.md"), recursive=True))
    if not pages:
        print("PROBE FAILED: wiki directory holds no Markdown pages")
        return 2

    try:
        texts = {p: read_text(p) for p in pages}
    except OSError as exc:
        print(f"PROBE FAILED: cannot read a wiki page: {exc}")
        return 2
    page_set = set(pages)
    stems, lower_stems = build_indexes(pages)
    aliases = collect_aliases(pages, texts)

    index_path = os.path.normpath(os.path.join(wiki, "index.md"))
    inbound = {p: set() for p in pages}
    links_scanned = embeds_skipped = 0
    for src in pages:
        if os.path.basename(src) == "log.md":
            continue                      # append-only history is not a link source
        body = strip_noise(texts[src])
        for is_embed, target in LINK_RE.findall(body):
            head = target.split("#", 1)[0].strip().rstrip("\\")
            if is_embed and os.path.splitext(head)[1].lower() in MEDIA_EXT:
                embeds_skipped += 1
                continue                  # media embed, not a page link
            links_scanned += 1
            for tgt in resolve(target, root, stems, lower_stems, aliases, page_set):
                if tgt != src:            # a self-link is not an inbound link
                    inbound[tgt].add(src)

    if links_scanned == 0:
        print("PROBE FAILED: zero page links scanned (nothing to census)")
        return 2

    candidates = [p for p in pages if not is_exempt(os.path.relpath(p, root))]
    orphans = sorted(os.path.relpath(p, root) for p in candidates if not inbound[p])
    with_inbound = sum(1 for p in pages if inbound[p])
    index_only = sorted(os.path.relpath(p, root) for p in candidates
                        if inbound[p] == {index_path})

    if args.format == "json":
        print(json.dumps({
            "root": args.vault,
            "pages": len(pages),
            "candidates": len(candidates),
            "exempt": len(pages) - len(candidates),
            "links_scanned": links_scanned,
            "embeds_skipped": embeds_skipped,
            "orphans": orphans,
            "orphan_count": len(orphans),
            "inbound_control": with_inbound,
            "index_only": index_only,
        }, indent=2, sort_keys=True))
        return 0

    print(f"check-orphans: root={args.vault} · exempt=index.md,log.md,maps/ · "
          f"log.md excluded as a link source · format=text")
    print(f"scanned: {len(pages)} pages · {links_scanned} page links · "
          f"{len(stems)} stems · {len(aliases)} aliases   (nonzero totals = the probe ran)")
    print(f"orphans: {len(orphans)} (of {len(candidates)} pages; exempt index/log/maps) · "
          f"inbound-control: {with_inbound} pages carry >=1 inbound link")
    for o in orphans:
        print("  " + o)
    print(f"index-only inbound: {len(index_only)} pages reached by the catalogue alone (information, not a finding)")
    for p in index_only:
        print("  " + p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
