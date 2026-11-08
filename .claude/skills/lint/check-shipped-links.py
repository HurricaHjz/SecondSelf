#!/usr/bin/env python3
"""check-shipped-links.py — shipped-surface wikilink guard (CLAUDE.md §11 / §12).

Question it answers: does any Markdown file that ships with the public framework carry a [[wikilink]]
that resolves in THIS vault but not in the published copy? Such a link is dead for every installer. It
does not judge links that are dead everywhere (typos, renamed pages): shipped skills use placeholders
such as [[topic]] on purpose, so those are counted on the control line, never flagged.

Surfaces (keyed on the export's own auto-discovery contract, its list_skills / list_agents functions):
every *.md under .claude/skills/ and .claude/agents/, minus vault-shaped content bundled inside a skill
(any path with a wiki/ or raw/ segment below .claude/skills/, i.e. the shipped seed demo, which ships as
vault content and resolves among itself) and minus each skill the exporter's own skip lines keep out of
every public build (read from export_template.sh on every run, so a bare caller gets the same scope as
the publish gate). Root docs (CLAUDE.md, MANUAL.md, README.md) are out of scope:
their [[…]] are naming examples by design, and §12's ship-safe-citation rule governs their citations.
Generator output (what setup.sh writes into a fresh vault) is the installed vault's content, not a
shipped surface.

Names that ship, and are therefore never findings: `index` and `log` (setup.sh creates wiki/index.md and
wiki/log.md in every install) and every page of a bundled example tree (.claude/skills/**/example/**/*.md,
installed by `setup.sh --with-example`).

Links: fenced blocks, inline code spans and HTML comments are not links (the strip_noise rule of
check-links.py); targets resolve the way Obsidian does (alias/heading stripped, a table-escaped pipe's
trailing backslash dropped, path-style by last segment, an explicit .md dropped, case-insensitive),
against page basenames AND frontmatter `aliases:` — an alias resolves here and dies in the published copy
just the same. Known limitation, shared with check-links.py: only three-backtick fences are recognised
(no ~~~, no four-backtick nesting).

Call sites — one implementation, two callers, so they cannot drift:
  lint SKILL.md Step 2g (routine, edit time) · the publish gate's test suite, leg 14 (publish).
Regression fixtures: test_check_shipped_links.sh beside this file (run with bash).

Usage: python3 check-shipped-links.py [--skip-skill NAME]... [--vault ROOT] [VAULT_ROOT]  (default: three levels above this file)
--skip-skill NAME (repeatable) leaves that skill's Markdown out of the surfaces: a skill the publish build
does not ship is no shipped surface. The script already skips every skill the exporter's skip lines name
(.claude/skills/export-template/export_template.sh, lines of the form `[ "$s" = NAME ] && continue`; a tree
without that file skips none), so a caller adds a name only for a skill beyond that list. A name given both
ways counts once on the control line, which counts the skills skipped.
Prints ONE summary line for the lint report, then one "  <file> → [[target]]" line per finding:
  shipped-links: clean (control OK: N surfaces, M wikilinks seen, P wiki pages + aliases = Q names,
                        S shipping names excluded, U targets resolving nowhere here, self-control fired)
  shipped-links: n/a (wiki/ present but empty — no vault-only page can be linked)
  shipped-links: K dead in the published copy (control OK: …)
  shipped-links: PROBE FAILED — <reason>
Exit 0 clean or n/a · 1 findings · 2 PROBE FAILED. Premise failures never read as clean: a root
that is not a vault, i.e. no raw/ + wiki/ (the 2026-08-26 standard, on stderr) → 2; an unknown
option → 2; no shipped surfaces → 2; an unreadable or undecodable surface → 2; the
matcher's self-control (a synthetic surface linking a synthetic page must be caught) silent → 2. An EMPTY
wiki/ is legitimate absence (a fresh install, the published copy itself) → n/a, exit 0.
"""
import glob
import os
import re
import sys

LINK = re.compile(r"\[\[([^\]]+)\]\]")
PROBE = "zzz-shipped-links-self-control"          # synthetic: keys the control on the matcher, not on a vault name
# One exporter skip line, read as the publish gate's leg 14 and lint Step 2g read it.
EXPORT_SKIP = re.compile(r'^[ \t]*\[ "\$s" = ([A-Za-z0-9._-]+) \] && continue[ \t]*$', re.M)


def strip_noise(text):                                     # mirrors check-links.py strip_noise
    text = re.sub(r"```.*?```", " ", text, flags=re.S)     # fenced code blocks
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)    # HTML comments
    text = re.sub(r"`[^`\n]*`", " ", text)                  # inline code spans
    return text


def norm(target):
    """Resolve the way Obsidian does: alias and heading stripped, a table-escaped pipe's trailing
    backslash dropped, path-style links by their last segment, an explicit .md dropped, case-insensitive."""
    t = target.split("|")[0].split("#")[0].strip().rstrip("\\").rsplit("/", 1)[-1]
    if t.lower().endswith(".md"):
        t = t[:-3]
    return t.casefold()


def targets(text):                                         # (raw link text, normalised target)
    return [(m, norm(m)) for m in LINK.findall(strip_noise(text))]


def read(path, strict):
    """A shipped surface must decode (strict); a wiki page only feeds the alias set (replace)."""
    try:
        with open(path, encoding="utf-8", errors="strict" if strict else "replace") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError) as err:
        print(f"shipped-links: PROBE FAILED — cannot read {path}: {err}")
        raise SystemExit(2)


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


def stem(path):
    return os.path.splitext(os.path.basename(path))[0].casefold()


def parse_root(argv):
    """The sibling flag spelling or the historical positional form; anything else is refused.

    A swallowed flag is how a wrong root goes unnoticed: `--vault X` taken as the root scans a
    directory that does not exist and the run reads as a premise failure at best, clean at worst.
    """
    given, skip = None, []
    rest = list(argv[1:])
    while rest:
        arg = rest.pop(0)
        if arg in ("-h", "--help"):
            print("usage: check-shipped-links.py [--skip-skill NAME]... [--vault ROOT] [ROOT]")
            raise SystemExit(0)
        if arg == "--skip-skill" or arg.startswith("--skip-skill="):
            name = arg.split("=", 1)[1] if "=" in arg else (rest.pop(0) if rest else "")
            if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
                print(f"PROBE FAILED: --skip-skill needs a skill name, got {name!r}", file=sys.stderr)
                raise SystemExit(2)
            skip.append(name)
            continue
        if arg == "--vault":
            if not rest:
                print("PROBE FAILED: --vault needs a directory argument", file=sys.stderr)
                raise SystemExit(2)
            arg = rest.pop(0)
        elif arg.startswith("--vault="):
            arg = arg.split("=", 1)[1]
        elif arg.startswith("-"):
            print(f"PROBE FAILED: unknown option {arg} (usage: [--vault ROOT] [ROOT])", file=sys.stderr)
            raise SystemExit(2)
        if given is not None:
            print(f"PROBE FAILED: two roots given ({given} and {arg})", file=sys.stderr)
            raise SystemExit(2)
        given = arg
    return given, skip


def assert_vault_root(root):
    """A root must hold raw/ AND wiki/ or the check refuses to run (2026-08-26 standard):
    fail loud on stderr, never a wrong-tree scan reported as clean."""
    if not all(os.path.isdir(os.path.join(root, d)) for d in ("raw", "wiki")):
        print(f"PROBE FAILED: {root} is not a vault root (no raw/ or wiki/)", file=sys.stderr)
        raise SystemExit(2)
    return root


def export_skips(root):
    """The skills the exporter's skip lines keep out of every public build. A tree with no exporter
    (a fixture) skips none; an exporter whose lines stop matching leaves their links as findings, which
    is the loud side of the failure. An unreadable exporter is a broken premise, through read()."""
    path = os.path.join(root, ".claude", "skills", "export-template", "export_template.sh")
    return EXPORT_SKIP.findall(read(path, strict=True)) if os.path.isfile(path) else []


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    given, skip = parse_root(argv)
    root = os.path.abspath(given) if given else os.path.abspath(os.path.join(here, "..", "..", ".."))
    assert_vault_root(root)
    wiki = os.path.join(root, "wiki")
    if not os.path.isdir(wiki):    # unreachable while the root guard runs first; kept as depth
        print(f"shipped-links: PROBE FAILED — no wiki/ under {root} (wrong vault root?)")
        return 2
    skills = os.path.join(root, ".claude", "skills")
    skip = sorted(set(skip) | set(export_skips(root)))

    def bundled_vault_content(f):                          # seed demo pages: vault-shaped dirs inside a skill
        parts = os.path.relpath(f, skills).split(os.sep)[:-1]
        return "wiki" in parts or "raw" in parts

    def skipped(f):                                        # a skill the caller names as not shipped
        return os.path.relpath(f, skills).split(os.sep)[0] in skip

    surfaces = sorted(f for f in glob.glob(os.path.join(skills, "**", "*.md"), recursive=True)
                      if not bundled_vault_content(f) and not skipped(f))
    surfaces += sorted(glob.glob(os.path.join(root, ".claude", "agents", "*.md")))
    if not surfaces:
        print("shipped-links: PROBE FAILED — no shipped Markdown surfaces under .claude/skills or .claude/agents")
        return 2
    files = glob.glob(os.path.join(wiki, "**", "*.md"), recursive=True)
    if not files:                                          # legitimate absence: a fresh install, the published copy
        print("shipped-links: n/a (wiki/ present but empty — no vault-only page can be linked)")
        return 0
    pages = {stem(f) for f in files}
    for f in files:
        pages.update(a.casefold() for a in page_aliases(read(f, strict=False)))
    ships = {"index", "log"}                               # setup.sh creates both in every install
    ships |= {stem(f) for f in glob.glob(os.path.join(skills, "**", "example", "**", "*.md"), recursive=True)}
    if [t for _, t in targets(f"control [[{PROBE}|alias]] text") if t in pages | {PROBE}] != [PROBE]:
        print("shipped-links: PROBE FAILED — matcher self-control did not fire")
        return 2
    seen, unresolved, findings = 0, 0, []
    for f in surfaces:
        ts = targets(read(f, strict=True))
        seen += len(ts)
        for raw, t in ts:
            if t in ships:
                continue
            if t in pages:
                findings.append((os.path.relpath(f, root), raw))
            else:
                unresolved += 1
    ctl = (f"control OK: {len(surfaces)} surfaces, {seen} wikilinks seen, {len(files)} wiki pages + aliases = "
           f"{len(pages)} names, {len(ships)} shipping names excluded, {unresolved} targets resolving nowhere here, "
           f"self-control fired, {len(skip)} skill(s) skipped as not shipped")
    if findings:
        print(f"shipped-links: {len(findings)} dead in the published copy ({ctl})")
        for f, raw in findings:
            print(f"  {f} → [[{raw}]]")
        return 1
    print(f"shipped-links: clean ({ctl})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
