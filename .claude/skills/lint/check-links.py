#!/usr/bin/env python3
"""Deterministic wikilink + embed checker for the wiki/ layer.

Shared by `lint` (routine scan) and `deep-lint` (structural pass) so every run applies
identical rules instead of re-deriving an ad-hoc scanner. Rules encoded here:
  - scans wiki/**/*.md; wiki/log.md is EXCLUDED as a link source (append-only history);
  - fenced code blocks, inline code spans and HTML comments are stripped before extraction
    (documentation examples like `[[wikilink]]` are not links);
  - page links resolve the way Obsidian does: wiki page stems -> frontmatter aliases ->
    vault-relative paths (with or without .md) -> any visible file's basename, with or
    without the extension. Obsidian keys its own lookup on the basename *including* the
    extension over every non-dot path in the vault, so a narrower rule reports live links
    as dead ([[index.md]], [[Claude Code.md]], [[choices-quick-reference]] in output/, and
    every attic target all resolve in the app);
  - frontmatter `aliases:` are read as YAML reads them, by the shared reader below: a one-line
    flow list respects quotes (double quotes with backslash escapes, single quotes doubling their
    quote), so a quoted alias carrying a comma stays one alias, and a block list of one-line `-`
    items reads each item the same way. A value spread over more than one line (a wrapped flow
    list or quoted entry, a `|` or `>` block scalar, an item or a value continued below its line),
    a value YAML cannot parse (an unclosed quote or bracket, an empty entry, a nested collection,
    text after a closing quote or bracket, an escape naming no character, a plain entry opening
    with a reserved character or carrying ": "), a mapping, or a repeated `aliases:` key is a
    MALFORMED ALIASES finding and contributes no alias — never a guess, never a traceback;
  - media embeds ![[name.ext]] resolve the way Obsidian resolves a file name: a bare name by
    file name over every visible file in the vault (the same dot-path rule as page links)
    except the attic, which is retired material; a path-qualified name by its path (from the
    vault root, from the embedding page, or as the tail of one visible file's path). No match
    is a DEAD EMBED (a finding); more than one is an AMBIGUOUS EMBED, listed on its own line
    and not a finding, since it renders — qualify it with a path to pin which file shows;
  - frontmatter `sources:` entries that name a vault path are resolved against disk and
    reported separately as DANGLING SOURCES (provenance is a reference, not only prose);
  - a `sources:` entry led by `~` or `/` is OUT-OF-VAULT provenance (a run store, a home
    directory): it is resolved with expanduser and reported as present or as missing in
    its own bucket, never as dangling (known-issues 2026-09-08: two false positives per
    run, and the class grows with every hands-off run report). A missing one is a finding;
  - every raw/**/*.md conversion's frontmatter `converted_from:` names its original, which
    §3.1 keeps beside the conversion: a local value is resolved beside the file, then at its
    vault path; a file of the same basename anywhere else under raw/ means the value is stale
    and the original survives (listed, never a finding); nothing at all is a MISSING ORIGINAL,
    the finding (known-issues 2026-09-09). A URL or prose value is counted, never resolved;
  - prints scan totals as its own positive control (a zero-findings run with zero links
    scanned is a broken probe, per CLAUDE.md §11);
  - refuses a root that is not a vault (no raw/ + wiki/): PROBE FAILED on stderr, exit 2.

Usage (from the vault root):
  python3 .claude/skills/lint/check-links.py [--vault ROOT] [ROOT]
  exit 0 = clean · 1 = findings · 2 = broken premise
"""
import os
import posixpath
import re
import sys
import glob

USAGE = "usage: check-links.py [--vault ROOT] [ROOT]   (exit 0 clean · 1 findings · 2 broken premise)"


def probe_failed(message):
    """One line on stderr, exit 2 — the fail-loud premise convention, so no caller reads a
    refused run as a clean one."""
    print(f"PROBE FAILED: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_root(argv):
    """Take the root from the sibling flag spelling or the historical positional form.

    An unrecognised flag is refused, never swallowed as a root: `--vault X` swallowed would set the
    root to the literal string "--vault", so the scan would open nothing and still print a
    clean bill of health (known-issues 2026-09-06).
    """
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


def assert_vault_root(candidate):
    """A root must hold raw/ AND wiki/ or the scan refuses to run.

    The 2026-08-26 standard closed for gather/capture_write.py: fail loud, never a wrong-tree
    scan that reports a clean vault on a scan of nothing.
    """
    if not all(os.path.isdir(os.path.join(candidate, d)) for d in ("raw", "wiki")):
        probe_failed(f"{candidate} is not a vault root (no raw/ or wiki/)")
    return candidate


root = assert_vault_root(parse_root(sys.argv[1:]))
wiki = os.path.join(root, "wiki")

MEDIA_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf", ".mp3", ".wav", ".mp4", ".mov"}

files = sorted(glob.glob(os.path.join(wiki, "**", "*.md"), recursive=True))
stems = {os.path.splitext(os.path.basename(p))[0] for p in files}


def read_text(path):
    """UTF-8 with a BOM dropped and CRLF normalised; bad bytes replaced, never fatal.
    A BOM or a CRLF line ending defeats the frontmatter match, so the page's aliases go
    uncollected and every link through them reads as dead."""
    with open(path, "rb") as fh:
        raw = fh.read()
    return raw.decode("utf-8-sig", "replace").replace("\r\n", "\n")

# Obsidian's resolver (uniqueFileLookup) is keyed on each visible file's basename INCLUDING the
# extension, across the whole vault; dot-folders are invisible to it. Model the same surface or
# valid links read as dead. Ambiguous basenames are treated as resolving: for a dead-link checker,
# erring permissive avoids false alarms, and Obsidian falls back to path resolution there anyway.
# The same walk indexes media-embed targets: every visible file outside the attic (the attic is
# retired material, so an embed that only the attic could satisfy is dead), keyed on its
# lower-cased basename and on its lower-cased vault-relative path.
ATTIC = "attic"
vault_basenames = set()
embed_by_name, embed_paths = {}, set()
for _dir, _subdirs, _names in os.walk(root):
    _subdirs[:] = [d for d in _subdirs if not d.startswith(".")]
    _rel_dir = os.path.relpath(_dir, root).replace(os.sep, "/")
    _in_attic = _rel_dir == ATTIC or _rel_dir.startswith(ATTIC + "/")
    for _n in _names:
        if not _n.startswith("."):
            vault_basenames.add(_n.lower())
            if not _in_attic:
                _rel = _n if _rel_dir == "." else _rel_dir + "/" + _n
                embed_by_name.setdefault(_n.lower(), []).append(_rel)
                embed_paths.add(_rel.lower())

# --- sources: provenance resolution -------------------------------------------------------
# Classification of one `sources:` entry, in this order (the order matters: an email address
# A prose marker takes precedence over a path-like suffix. Classify URLs first, then explicit
# deletion annotations, prose, outside-vault paths, and relative or extension-named paths.
# Only `path` and `outside` entries are resolved; everything else is counted so a zero is
# auditable.
URL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://")
PROSE_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z ]{0,20}:\s")
EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,8}$")
ANNOTATED_RE = re.compile(r"\((?:deleted|removed|archived|superseded)\b[^)]*\)\s*$", re.I)
SOURCES_KEY_RE = re.compile(r"^sources:", re.M)


def split_flow_list(text):
    """Split a YAML flow list's body on commas OUTSIDE quotes.

    A quoted path may carry commas; splitting inside quotes would invent dangling paths.
    Track quote state so one quoted path remains one entry.
    """
    out, buf, quote = [], "", ""
    for ch in text:
        if quote:
            if ch == quote:
                quote = ""
            buf += ch
        elif ch in "\"'":
            quote = ch
            buf += ch
        elif ch == ",":
            out.append(buf)
            buf = ""
        else:
            buf += ch
    out.append(buf)
    return [v.strip() for v in out if v.strip()]


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


def frontmatter_sources(block):
    """Every `sources:` entry in one frontmatter block, in any of the three shapes the vault
    writes: an inline flow list (possibly wrapped), a block list of `-` items, or a bare
    scalar. Returns (entries, key_present)."""
    if not SOURCES_KEY_RE.search(block):
        return [], False
    flow = re.search(r"^sources:[ \t]*\[(.*?)\]", block, re.M | re.S)
    if flow:
        return split_flow_list(flow.group(1)), True
    listed = re.search(r"^sources:[ \t]*(?:#[^\n]*)?\n((?:[ \t]*-[ \t]*[^\n]+\n?)+)", block, re.M)
    if listed:
        return [v.strip() for v in re.findall(r"^[ \t]*-[ \t]*(.+?)[ \t]*$", listed.group(1), re.M)
                if v.strip()], True
    scalar = re.search(r"^sources:[ \t]+([^\[\n#][^\n]*)$", block, re.M)
    if scalar and scalar.group(1).strip():
        return [scalar.group(1).strip()], True
    return [], True                    # `sources:` with an empty or `[]` value: parsed, no entries


def classify_source(entry):
    """Return (kind, cleaned) for one entry; kind is url · annotated · prose · outside · path."""
    text = entry.strip()
    if len(text) > 1 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    else:
        text = text.strip("\"'").strip()
    if not text:
        return "prose", text
    if URL_RE.match(text):
        return "url", text
    if ANNOTATED_RE.search(text):
        return "annotated", text
    if text[0] in "~/":
        return "outside", text
    if PROSE_KEY_RE.match(text):
        return "prose", text
    if "/" in text or EXT_RE.search(text):
        return "path", text
    return "prose", text


source_pages = source_entries = 0
source_paths = source_urls = source_prose = 0
dangling_sources, annotated_sources, unparsed_sources = [], [], []
outside_present, outside_missing = [], []

aliases, malformed_aliases = {}, []
for p in files:
    head = read_text(p)   # full read — a byte-capped head can silently drop aliases past the cap (§12: a bound needs stated headroom; the link pass re-reads every file in full anyway)
    fm = re.match(r"\A---\n(.*?)\n---", head, re.S)
    if not fm:
        continue
    block = fm.group(1)
    entries, key_present = frontmatter_sources(block)
    if key_present:
        source_pages += 1
        rel_page = os.path.relpath(p, root)
        if not entries:
            unparsed_sources.append(rel_page)
        for entry in entries:
            source_entries += 1
            kind, value = classify_source(entry)
            if kind == "url":
                source_urls += 1
            elif kind == "prose":
                source_prose += 1
            elif kind == "annotated":
                annotated_sources.append(f"{rel_page} · {value}")
            elif kind == "outside":
                # A `~`- or `/`-led entry lives outside the vault: resolve it where it says it
                # is. Present or missing, it is never a dangling VAULT path.
                if os.path.exists(os.path.expanduser(value)):
                    outside_present.append(f"{rel_page} · {value}")
                else:
                    outside_missing.append(f"{rel_page} · {value}")
            else:
                source_paths += 1
                if not os.path.exists(os.path.join(root, value)):
                    dangling_sources.append(f"{rel_page} · {value}")
    page_aliases, alias_error = frontmatter_aliases(block)
    if alias_error:
        raw = block[ALIASES_KEY_RE.search(block).start():].split("\n", 1)[0]
        malformed_aliases.append(f"{os.path.relpath(p, root)} · {raw} ({alias_error})")
    for a in page_aliases:
        aliases[a] = p


def strip_noise(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)      # fenced code blocks
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)     # HTML comments
    text = re.sub(r"`[^`\n]*`", " ", text)                   # inline code spans
    return text


def resolves(target):
    t = target.strip()
    if not t or t.startswith("#"):
        return True                                          # self-heading link
    t = t.split("#", 1)[0].strip()                           # drop heading part
    if t in stems or t in aliases:
        return True
    if "/" in t or t.endswith(".md"):                        # vault-relative path form
        for cand in (t, t + ".md"):
            if os.path.exists(os.path.join(root, cand)):
                return True
    if os.path.exists(os.path.join(root, t + ".md")):        # root doc, e.g. [[CLAUDE]]
        return True
    base = os.path.basename(t).lower()                        # Obsidian basename lookup
    if base in vault_basenames or (base + ".md") in vault_basenames:
        return True
    return False


def resolve_embed(target, page_rel_dir):
    """The visible, non-attic files one media embed target can mean, as vault-relative paths.

    A bare name matches by file name anywhere; a path-qualified one matches from the vault root,
    then from the embedding page's folder, then as the tail of a visible file's path (how
    Obsidian reads a partial path). Case is ignored, as Obsidian's lookup ignores it.
    """
    t = target.split("#", 1)[0].strip().replace("\\", "/").lower()
    name = posixpath.basename(t)
    if "/" not in t:
        return list(embed_by_name.get(name, []))
    for cand in (posixpath.normpath(t.lstrip("/")),
                 posixpath.normpath(posixpath.join(page_rel_dir.lower(), t))):
        if cand in embed_paths:
            return [p for p in embed_by_name.get(name, []) if p.lower() == cand]
    tail = posixpath.normpath(t.lstrip("/"))
    return [p for p in embed_by_name.get(name, []) if p.lower().endswith("/" + tail)]


dead_links, dead_embeds, ambiguous_embeds = [], [], []
links_checked = embeds_checked = 0
for p in files:
    if os.path.basename(p) == "log.md":
        continue
    body = strip_noise(read_text(p))
    for is_embed, target in re.findall(r"(!?)\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]", body):
        target = target.strip().rstrip("\\")   # [[page\|alias]] table-escaped pipes leave a trailing backslash
        ext = os.path.splitext(target.split("#", 1)[0])[1].lower()
        rel = os.path.relpath(p, root)
        if is_embed and ext in MEDIA_EXT:
            embeds_checked += 1
            page_dir = os.path.dirname(rel).replace(os.sep, "/")
            matches = resolve_embed(target, page_dir)
            if not matches:
                dead_embeds.append(f"{rel} -> ![[{target}]]")
            elif len(matches) > 1:
                ambiguous_embeds.append(f"{rel} -> ![[{target}]] ({len(matches)} files: {', '.join(sorted(matches))})")
        else:
            links_checked += 1
            if not resolves(target):
                dead_links.append(f"{rel} -> [[{target}]]")

print(f"SCANNED: {len(files)} pages | {links_checked} page links | {embeds_checked} media embeds "
      f"| {len(stems)} stems | {len(aliases)} aliases   (nonzero totals = probe ran)")
print(f"DEAD LINKS: {len(dead_links)}")
for d in dead_links:
    print("  " + d)
print(f"DEAD EMBEDS: {len(dead_embeds)}")
for d in dead_embeds:
    print("  " + d)
# An ambiguous embed renders (Obsidian picks one of the files), so it is listed, never a finding:
# qualifying the embed with a path pins which file shows.
print(f"AMBIGUOUS EMBEDS: {len(ambiguous_embeds)}   (a bare name more than one visible file carries; listed, not a finding)")
for d in ambiguous_embeds:
    print("  " + d)
print(f"MALFORMED ALIASES: {len(malformed_aliases)}")
for d in malformed_aliases:
    print("  " + d)
print(f"SOURCES SCANNED: {source_pages} pages carry sources: | {source_entries} entries "
      f"| {source_paths} vault paths resolved | {source_urls} URLs | {source_prose} prose "
      f"| {len(annotated_sources)} annotated absences | {len(unparsed_sources)} empty or unparsed "
      f"| {len(outside_present) + len(outside_missing)} out-of-vault"
      "   (nonzero totals = the sources arm ran)")
print(f"DANGLING SOURCES: {len(dangling_sources)}")
for d in dangling_sources:
    print("  " + d)
# Neither list is a finding: an annotated entry declares its own absence, and an empty
# `sources:` carries nothing to resolve. Both are printed so nothing is silently skipped.
for label, items in (("annotated absence", annotated_sources), ("empty or unparsed sources", unparsed_sources)):
    for d in items:
        print(f"  ({label}) {d}")
# Out-of-vault provenance (`~`- or `/`-led) is resolved where it points, with expanduser.
# A present entry is information; a missing one is a finding in its own bucket, never a
# dangling vault path.
print(f"OUT-OF-VAULT SOURCES: {len(outside_present)} present | {len(outside_missing)} missing")
for d in outside_missing:
    print(f"  (out-of-vault missing) {d}")

# --- converted_from: the original beside its conversion (§3.1) ----------------------------
# A conversion in raw/ names its original in `converted_from:`; §3.1 keeps the original and the
# pair moves together, so this arm checks the pair (known-issues 2026-09-09). Classification of one
# value, in this order:
#   url        a scheme form — the capture came from the web, nothing on disk to resolve
#   annotated  the value declares the original gone: "x.pdf (deleted 2026-08-13)"
#   prose      no file extension once a trailing "(…)" note is dropped: a pasted email, a chat
#   local      a file name or path, a trailing note dropped ("x.pdf (arXiv:…)" -> "x.pdf"):
#              resolved beside the conversion, then at its vault path (or with expanduser when
#              led by ~ or /); failing both, a file of the same basename anywhere under raw/
#              (any case) means the value is stale and the original survives — listed, never a
#              finding; nothing at all is a MISSING ORIGINAL, the finding
TRAILING_NOTE_RE = re.compile(r"\s+\([^()]*\)\s*$")
CONVERTED_FROM_RE = re.compile(r"^converted_from:[ \t]*(.*?)[ \t]*$", re.M)
RAW_FM_RE = re.compile(r"\A---\n(.*?)\n---", re.S)
# A bound, not a decider: conversion keys sit in the first lines; a block that has not closed
# inside the bound is re-read whole, so the bound can never silently drop a key.
RAW_HEAD_BYTES = 16384


def classify_original(value):
    """Return (kind, cleaned) for one `converted_from:` value; kind is url · annotated · prose · local."""
    text = value.strip()
    if len(text) > 1 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    if not text:
        return "prose", text
    if URL_RE.match(text):
        return "url", text
    if ANNOTATED_RE.search(text):
        return "annotated", text
    bare = TRAILING_NOTE_RE.sub("", text).strip()
    if bare and EXT_RE.search(bare):
        return "local", bare
    return "prose", text


def raw_frontmatter(path):
    """The frontmatter block of one raw file, or None when the file opens with none."""
    with open(path, "rb") as fh:
        head = fh.read(RAW_HEAD_BYTES)
    text = head.decode("utf-8-sig", "replace").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return None
    m = RAW_FM_RE.match(text)
    if m is None and len(head) == RAW_HEAD_BYTES:
        m = RAW_FM_RE.match(read_text(path))
    return m.group(1) if m else None


raw_md, raw_basenames = [], set()
for _dir, _subdirs, _names in os.walk(os.path.join(root, "raw")):
    _subdirs[:] = sorted(d for d in _subdirs if not d.startswith("."))
    for _n in sorted(_names):
        if _n.startswith("."):
            continue
        raw_basenames.add(_n.lower())
        if _n.endswith(".md"):
            raw_md.append(os.path.join(_dir, _n))

conv_files = conv_local = conv_urls = conv_prose = 0
conv_missing, conv_elsewhere, conv_annotated, conv_unreadable = [], [], [], []
for p in raw_md:
    rel_conv = os.path.relpath(p, root)
    try:
        block = raw_frontmatter(p)
    except OSError as exc:
        conv_unreadable.append(f"{rel_conv} ({exc.__class__.__name__})")
        continue
    m = CONVERTED_FROM_RE.search(block) if block is not None else None
    if not m:
        continue
    conv_files += 1
    kind, value = classify_original(m.group(1))
    if kind == "url":
        conv_urls += 1
        continue
    if kind == "prose":
        conv_prose += 1
        continue
    if kind == "annotated":
        conv_annotated.append(f"{rel_conv} · {value}")
        continue
    conv_local += 1
    if value[0] in "~/":
        candidates = [os.path.expanduser(value)]
    else:
        candidates = [os.path.join(os.path.dirname(p), value)]
        if "/" in value:
            candidates.append(os.path.join(root, value))
    if any(os.path.exists(c) for c in candidates):
        continue
    if os.path.basename(value).lower() in raw_basenames:
        conv_elsewhere.append(f"{rel_conv} · {value}")
    else:
        conv_missing.append(f"{rel_conv} · {value}")

print(f"CONVERSIONS SCANNED: {len(raw_md)} raw .md files | {conv_files} carry converted_from: "
      f"| {conv_local} local | {conv_urls} URLs | {conv_prose} prose | {len(conv_annotated)} annotated absences "
      f"| {len(conv_unreadable)} unreadable   (nonzero raw file total = the conversions arm ran)")
print(f"MISSING ORIGINALS: {len(conv_missing)}")
for d in conv_missing:
    print("  " + d)
# None of these is a finding: a stale value whose original survives elsewhere under raw/, an
# original the value itself declares gone, a raw file that could not be opened. Each prints so
# nothing is silently skipped.
for label, items in (("original found elsewhere under raw/", conv_elsewhere),
                     ("annotated original", conv_annotated),
                     ("unreadable raw file", conv_unreadable)):
    for d in items:
        print(f"  ({label}) {d}")
sys.exit(1 if (dead_links or dead_embeds or malformed_aliases or dangling_sources or outside_missing
               or conv_missing) else 0)
