#!/usr/bin/env python3
"""check-experience-reach.py — do experience pages and their pointers still meet (lint Step 2h).

Stdout-only by construction: reads, prints, writes nothing.

Why: an experience page is read only through a pointer at the step where its feature decides, so a
pointer lost in a skill edit shows no symptom until a fault repeats. Each page's header declares its
readers (`**Read by:**`, a backticked path and its step in brackets); this check pairs every
declaration with a pointer in that file under that step, and every pointer with a page that
declares it.

Warnings: a page without a header or a reader; a page name outside plain kebab-case; a pointer
missing, malformed or outside its declared step; a pointer to a missing page; an undeclared reader;
a page named outside a pointer; a read of the whole folder by a glob. A step pointer opens its line
with `**Experience:**` and names one page; a brief pointer ends `copied verbatim:`. A line of
CLAUDE.md or CUSTOMISATION.md naming a page counts as an always-on pointer, its declared phrase on
the same line. Fences and HTML comments never count. Placement inside the step stays with the
critic and the recall probe: this check compares files, never whether a model reads a page.

Scope: the selected pages; CLAUDE.md, CUSTOMISATION.md (absent is fine unless a page declares it,
CLAUDE.md section 13), CUSTOMISATION-definitions.md, MANUAL.md and README.md; `.md`, `.py` and `.sh`
files under `.claude/`, except test files; folder READMEs outside `raw/`, `wiki/`, `attic/`, `.git/`
and `.claude/`; and every further reader a page declares (`~/` is read through the home folder).
Recognition is narrower than Obsidian: an exact short link `[[name]]`, an exact file name, or the
selected path. A deleted page's short link escapes pairing, so a retirement sweeps its pointers.

Control, in memory, before the scan: a clean page and pointer must pair with no warning; the same
page with its pointer gone must warn; a folder glob must warn. A control that does not behave is
PROBE FAILED (exit 2).

The always-on list prints at five pairs: set by judgement, unmeasured, reviewed on the lifecycle
row's date. A pointer joins at most five source lines: parser headroom over the longest form, which
wraps to three lines at 100 columns, not a page limit.

Usage (from the vault root):
  python3 .claude/skills/lint/check-experience-reach.py [--vault ROOT] [--selection SEL]
  SEL: a vault-relative folder ending in `/` (default wiki/experience/), or exact page paths
  separated by commas.
  exit 0 = no warning · 1 = warnings · 2 = broken premise (not a vault root, an unknown flag, a
  required surface unreadable, a control that did not behave)
"""
import os
import re
import sys
from pathlib import Path

USAGE = ("usage: check-experience-reach.py [--vault ROOT] [--selection SEL]   "
         "(exit 0 no warning · 1 warnings · 2 broken premise)")
DEFAULT_SELECTION = "wiki/experience/"
ALWAYS_ON = ("CLAUDE.md", "CUSTOMISATION.md")
ROOT_DOCS = ("CUSTOMISATION-definitions.md", "MANUAL.md", "README.md")
JOIN_LINES = 5
LIST_ALWAYS_ON_AT = 5
MARKER = re.compile(r"^\s*(?:[-*+]\s+|[0-9]+[.)]\s+|>\s*|#+\s*)?\*\*Experience:\*\*")
CONTINUE_STOP = re.compile(r"^\s*(?:[-*+]\s|[0-9]+[.)]\s|>|#|\||\*\*[A-Z][^*]*:\*\*)")


def path_pattern(selection):
    selected = selection.split(",")
    folders = [x for x in selected if x.endswith("/")]
    exact = [x for x in selected if not x.endswith("/")]
    body = "|".join([re.escape(x) + r"[A-Za-z0-9-]+\.md" for x in folders]
                    + [re.escape(x) for x in exact])
    return re.compile(r"(?<![A-Za-z0-9_./-])(?:" + body + r")(?![A-Za-z0-9_-]|\.[A-Za-z0-9])", re.I)


def folder_glob_pattern(selection):
    """A glob over a selected folder: the folder, then a star or a brace, in any surface."""
    folders = [x for x in selection.split(",") if x.endswith("/")]
    if not folders:
        return None
    body = "|".join(re.escape(x) for x in folders)
    return re.compile(r"(?<![A-Za-z0-9_./-])(?:" + body + r")\**[*{]")


def visible_lines(text):
    """(line number, text outside comments) for each line, a multi-line comment spanning lines."""
    comment = False
    for number, raw in enumerate(text.splitlines(), 1):
        visible = ""
        while raw:
            if comment:
                at = raw.find("-->")
                if at < 0:
                    break
                raw, comment = raw[at + 3:], False
            else:
                at = raw.find("<!--")
                if at < 0:
                    visible += raw
                    break
                visible += raw[:at]
                raw, comment = raw[at + 4:], True
        yield number, visible, comment


def analyse(pages, surfaces, unreadable, selection):
    """The comparison, on texts already read. `pages` maps a page path to its text (None for a
    name refused before reading is recorded separately); `surfaces` maps a surface path to its
    text; `unreadable` is the set of surfaces that could not be read. Returns the warnings, the
    totals and the number of pairs matched."""
    paths = path_pattern(selection)
    globs = folder_glob_pattern(selection)
    warnings = []
    stems = {Path(page).stem: page for page in pages}
    declarations = []
    pointers = {}

    def warn(text):
        warnings.append(text)

    def named(text):
        found = [m.group() for m in paths.finditer(text)]
        rest = paths.sub(" ", text)
        for stem, page in stems.items():
            link = r"\[\[" + re.escape(stem) + r"(?:\.md)?(?:\]\]|\\?\||#)"
            file = r"(?<![A-Za-z0-9_/-])" + re.escape(stem) + r"\.md(?![A-Za-z0-9_-]|\.[A-Za-z0-9])"
            if re.search(link, rest) or re.search(file, rest):
                found.append(page)
        return list(dict.fromkeys(found))

    def mention(surface, text, line):
        for page in named(text):
            warn("unsupported mention: %s line %d names %s outside a pointer" % (surface, line, page))

    for page, text in sorted(pages.items()):
        header = next((l for l in text.splitlines()
                       if "**Feature:**" in l and "**Read by:**" in l), "")
        if not header:
            warn("no header line: %s" % page)
            continue
        field = header.split("**Read by:**", 1)[1].split(" · **", 1)[0]
        readers = 0
        for part in field.split(";"):
            m = re.fullmatch(r"\s*`([^`]+)`\s*(?:\((.*)\))?\s*", part)
            if not m:
                if part.strip():
                    warn("malformed reader declaration: %s: %s" % (page, part.strip()))
                continue
            reader, step = m.group(1), (m.group(2) or "").strip().strip('"“”')
            if not step:
                warn("reader declared without its step: %s -> %s" % (page, reader))
            declarations.append((page, reader, step))
            readers += 1
        if not readers:
            warn("no reader declared: %s" % page)

    def record(surface, page, line, context, kind):
        pointers.setdefault((surface, page), []).append((line, context, kind))

    def flush(surface, unit):
        if not unit:
            return
        text, line, context = unit
        text = re.sub(r"\s+", " ", text)
        m = paths.search(text)
        if not m:
            warn("pointer names no page: %s line %d" % (surface, line))
            return
        page = m.group()
        head, rest = text[:m.start()], text[m.end():]
        end = re.search(r" whole\.| copied verbatim:", rest)
        kind = ("step" if end.group() == " whole." else "brief") if end else "step"
        record(surface, page, line, context, kind)
        if not end or (kind == "step" and "and before changing how it is made" not in head):
            warn("pointer form: %s -> %s (its exact wording is missing)" % (surface, page))
        if end:
            if paths.search(rest[:end.end()]):
                warn("pointer form: %s line %d names more than one page" % (surface, line))
            mention(surface, rest[end.end():], line)

    for surface, text in sorted(surfaces.items()):
        fence, unit, ulines, quote = False, None, 0, False
        headings = {}
        for number, v, in_comment in visible_lines(text):
            if re.match(r"^\s*(```|~~~)", v):
                flush(surface, unit)
                unit = None
                fence = not fence
                continue
            if fence:
                continue
            if globs and globs.search(v):
                warn("whole-folder read: %s line %d" % (surface, number))
            if surface in ALWAYS_ON:
                for page in named(v):
                    record(surface, page, number, v, "always-on")
                continue
            if MARKER.match(v):
                flush(surface, unit)
                unit = (v, number, " | ".join(headings[k] for k in sorted(headings)))
                ulines, quote = 1, bool(re.match(r"^\s*>", v))
                continue
            if unit:
                if quote:
                    v = re.sub(r"^\s*>\s?", "", v)
                if in_comment or ulines >= JOIN_LINES or not v.strip() or CONTINUE_STOP.match(v):
                    flush(surface, unit)
                    unit = None
                else:
                    unit = (unit[0] + " " + v.strip(), unit[1], unit[2])
                    ulines += 1
                    continue
            heading = re.match(r"^\s*(#+)\s", v) if surface.endswith(".md") else None
            if heading:
                level = len(heading.group(1))
                headings = {k: val for k, val in headings.items() if k < level}
                headings[level] = v
            mention(surface, v, number)
        flush(surface, unit)

    matched = 0
    for page, reader, step in declarations:
        locations = pointers.get((reader, page), [])
        if reader in unreadable:
            warn("reader unreadable: %s (declared by %s)" % (reader, page))
        elif not locations:
            warn("pointer missing: %s -> %s" % (reader, page))
        elif not step:
            continue
        elif any(kind == "brief" or
                 re.search(r"(?<![A-Za-z0-9])" + re.escape(step) + r"(?![A-Za-z0-9])", context)
                 for _, context, kind in locations):
            matched += 1
        else:
            where = "; ".join("line %d" % line + (' under "%s"' % context if context else " under no heading")
                              for line, context, _ in locations)
            warn('pointer outside its declared step: %s -> %s (declared "%s"; found at %s)'
                 % (reader, page, step, where))
    for reader, page in pointers:
        if page not in pages:
            warn("page missing: %s -> %s" % (reader, page))
        elif not any(p == page and r == reader for p, r, _ in declarations):
            warn("undeclared reader: %s -> %s" % (reader, page))
    always_on = sum(surface in ALWAYS_ON for surface, _ in pointers)
    return warnings, {"pages": len(pages), "declarations": len(declarations),
                      "pointers": len(pointers), "matched": matched, "always_on": always_on}


def control():
    """The in-memory control: (ok, text)."""
    page_path = "wiki/experience/alpha.md"
    page = ("**Feature:** alpha · **Moment:** m · **Read by:** `.claude/skills/x/SKILL.md` "
            "(Step 4) · **Multi-agent pattern:** one agent\n")
    pointer = ("### Step 4 — Decide\n**Experience:** before the decision, and before changing how "
               "it is made, read `wiki/experience/alpha.md` whole.\n")
    clean, totals = analyse({page_path: page}, {".claude/skills/x/SKILL.md": pointer}, set(),
                            DEFAULT_SELECTION)
    lost, _ = analyse({page_path: page}, {".claude/skills/x/SKILL.md": "### Step 4 — Decide\n"},
                      set(), DEFAULT_SELECTION)
    glob, _ = analyse({page_path: page},
                      {".claude/skills/x/SKILL.md": pointer + "cat wiki/experience/*.md\n"},
                      set(), DEFAULT_SELECTION)
    good = (not clean and totals["matched"] == 1 and any("pointer missing" in w for w in lost)
            and any("whole-folder read" in w for w in glob))
    return good, "control: a clean pair stayed silent; a lost pointer and a folder glob warned"


def parse_args(argv):
    vault, selection = ".", DEFAULT_SELECTION
    args = list(argv)
    while args:
        flag = args.pop(0)
        if flag in ("--vault", "--selection") and args:
            value = args.pop(0)
            if flag == "--vault":
                vault = value
            else:
                selection = value
        else:
            print(USAGE, file=sys.stderr)
            sys.exit(2)
    return vault, selection


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def main(argv):
    vault, selection = parse_args(argv)
    root = Path(vault).resolve()
    if not (root / "raw").is_dir() or not (root / "wiki").is_dir():
        print("PROBE FAILED: %s is not a vault root (no raw/ or wiki/)" % root, file=sys.stderr)
        return 2
    selected = selection.split(",")
    if not all(x and not x.startswith(("/", "~")) and ".." not in Path(x).parts for x in selected):
        print("PROBE FAILED: a selection names vault-relative pages or folders", file=sys.stderr)
        return 2
    good, text = control()
    print(text if good else "PROBE FAILED: " + text)
    if not good:
        return 2

    failed, warnings_before = [], []
    names = set()
    for item in selected:
        if item.endswith("/"):
            names.update(p.relative_to(root).as_posix() for p in (root / item).glob("*.md")
                         if p.is_file())
        else:
            names.add(item)
    pages = {}
    for page in sorted(names):
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", Path(page).stem):
            warnings_before.append("page name outside plain kebab-case: %s" % page)
            continue
        try:
            pages[page] = read_text(root / page)
        except (OSError, UnicodeError):
            warnings_before.append("page unreadable: %s" % page)

    declared = set()
    for text in pages.values():
        header = next((l for l in text.splitlines()
                       if "**Feature:**" in l and "**Read by:**" in l), "")
        declared.update(re.findall(r"`([^`]+)`", header.split("**Read by:**", 1)[1].split(" · **", 1)[0])
                        if header else [])

    names = set(ALWAYS_ON) | set(ROOT_DOCS) | declared
    claude = root / ".claude"
    if claude.is_dir():
        for p in claude.rglob("*"):
            if p.is_file() and p.suffix in (".md", ".py", ".sh") and not p.name.startswith("test_"):
                names.add(p.relative_to(root).as_posix())
    for directory, dirs, files in os.walk(root):
        if Path(directory) == root:
            dirs[:] = [d for d in dirs if d not in ("raw", "wiki", "attic", ".git", ".claude")]
        if "README.md" in files:
            names.add((Path(directory) / "README.md").relative_to(root).as_posix())

    surfaces, unreadable = {}, set()
    for name in sorted(names):
        path = Path(name).expanduser() if name.startswith("~/") else root / name
        try:
            surfaces[name] = read_text(path)
        except (OSError, UnicodeError):
            unreadable.add(name)
            if name in declared:
                continue
            if name == "CLAUDE.md":
                failed.append("cannot read CLAUDE.md")
            elif name not in ALWAYS_ON and name not in ROOT_DOCS:
                failed.append("cannot read %s" % name)

    warnings, totals = analyse(pages, surfaces, unreadable, selection)
    warnings = warnings_before + warnings
    for w in warnings:
        print("WARN " + w)
    for f in failed:
        print("PROBE FAILED: " + f)
    print("experience reach: surfaces %d · pages %d · readers declared %d · pointers found %d · "
          "pairs matched %d · warnings %d · always-on pointers %d"
          % (len(surfaces), totals["pages"], totals["declarations"], totals["pointers"],
             totals["matched"], len(warnings), totals["always_on"]))
    if totals["always_on"] >= LIST_ALWAYS_ON_AT:
        print("LIST always-on pointers: review their placement against the rule in force "
              "(five set by judgement, unmeasured)")
    if failed:
        return 2
    if warnings:
        return 1
    if not pages and not totals["pointers"]:
        print("experience reach: no pages and no pointers (a state; nothing compared)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
