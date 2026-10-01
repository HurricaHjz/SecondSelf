#!/usr/bin/env python3
"""check_register.py — two consistency checks over the known-issues register (lint Step 2).

Stdout-only by construction: reads the register, prints, writes nothing.

Why (known-issues 2026-09-07): an entry under `## Open` can carry a closed status in its own text,
and two headings can name one defect at one `file:line`, so the open count reads too high. The
register's writers are hand edits and a helper, and nothing else scans the file. The
checks key on the two observables:
  1. CLOSED STATUS UNDER OPEN: an entry under `## Open` carrying a `**Status**:` whose value
     begins with a closing word, `closed`, `fixed` or `resolved` (any case, emphasis ignored;
     the register closes entries in all three words). A dated status fact (`**Status 2026-09-02
     …**:`) and a `**Severity/status**:` line are not that line, and a closing word later in
     the value (`open — not yet fixed`, `unresolved`) is not a closing status.
  2. SHARED LOCATORS: two entries under `## Open` citing one `file:line` locator (a path whose
     last segment carries a file extension, a colon and a line number: `ingest/SKILL.md:435`).
     Two locators are one when the line numbers agree and one path equals the other or ends with
     it segment by segment, at least a folder and a file in common (`ingest/SKILL.md:435` and
     `.claude/skills/ingest/SKILL.md:435`). A match on the bare file name alone (`SKILL.md:147`
     beside `delegate/SKILL.md:147`) is listed as POSSIBLE, never a finding, since many
     surfaces share a file name. Closed entries are left out of the pairing because line numbers
     drift as files change, so a closed entry's locator names an older text; the number of
     locators an Open entry shares with a Closed one prints as information.
Entry headings (`### `) inside fenced code blocks, such as the register's format example, are
not entries.

Controls, in memory, before the scan: a register holding a closed Status under `## Open` and two
Open entries citing one locator in two spellings must produce one finding of each kind, and a
closed Status under `## Closed` must not be one. A control that does not behave is PROBE FAILED
(exit 2).

Usage (from the vault root):
  python3 .claude/skills/lint/check_register.py [--vault ROOT] [--register FILE]
  exit 0 = clean, or n/a when the vault has no register yet (CLAUDE.md §12: a missing register
  is not an error) · 1 = findings · 2 = broken premise (not a vault root, a named register file
  missing, an unreadable register, no `## Open` heading, a control that did not behave)
"""
import os
import re
import sys

USAGE = ("usage: check_register.py [--vault ROOT] [--register FILE]   "
         "(exit 0 clean or n/a · 1 findings · 2 broken premise)")
REGISTER_REL = "wiki/developments/known-issues.md"

SECTION_RE = re.compile(r"^##[ \t]+(.+?)[ \t]*$")          # `### x` never matches: `#` is not a blank
ENTRY_RE = re.compile(r"^###[ \t]+(.+?)[ \t]*$")
FENCE_RE = re.compile(r"^[ \t]*(```|~~~)")
STATUS_RE = re.compile(r"\*\*Status\*\*:[ \t]*(.*)")
# The three words the register closes an entry with; the word must open the Status value.
CLOSED_RE = re.compile(r"^[*_`\s]*(?:closed|fixed|resolved)\b", re.I)
OPEN_SECTION_RE = re.compile(r"^open\b", re.I)
CLOSED_SECTION_RE = re.compile(r"^closed\b", re.I)
LOCATOR_RE = re.compile(
    r"(?<![\w.~/@-])(~?/?(?:[\w.@-]+/)*[\w@-][\w.@-]*\.[A-Za-z][A-Za-z0-9]{0,4}):(\d+)(?!\d)")

CONTROL_REGISTER = """# Register

```
### [YYYY-MM-DD] <surface> — <short title> (minor)
- **Status**: closed — the format example inside a fence is not an entry: `x/y.md:1`
```

## Open

### [2026-01-02] a skill — the same defect, filed a second time (minor)
- **Where observed**: a run · `skills/example/SKILL.md:12`
- **Status**: open — fix shape: one line, not yet fixed or resolved

### [2026-01-01] a skill — the defect (minor)
- **Where observed**: a run · `.claude/skills/example/SKILL.md:12` and `x/y.md:1`
- **Status**: closed 2026-01-03 — fixed, and the entry was never moved

### [2026-01-04] a hook — fixed and left under Open (minor)
- **Severity**: minor. **Status**: Fixed same day — the entry was never moved

### [2026-01-05] a script — resolved and left under Open (minor)
- **Status**: *resolved* 2026-01-06 — the entry was never moved

## Closed

### [2025-12-01] another surface — closed where it belongs (minor)
- **Status**: closed 2025-12-02 — fixed
"""


def probe_failed(message):
    print(f"PROBE FAILED: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_args(argv):
    """(vault, register, file_mode). An unknown flag is refused, never read as a root."""
    vault, register, rest = None, None, list(argv)
    while rest:
        arg = rest.pop(0)
        if arg in ("-h", "--help"):
            print(USAGE)
            raise SystemExit(0)
        if arg in ("--vault", "--register"):
            if not rest:
                probe_failed(f"{arg} needs an argument")
            value = rest.pop(0)
        elif arg.startswith("--vault=") or arg.startswith("--register="):
            arg, value = arg.split("=", 1)
        else:
            probe_failed(f"unknown argument {arg} ({USAGE})")
        if arg == "--vault":
            vault = value
        else:
            register = value
    return vault, register


def read_text(path):
    """UTF-8 with a BOM dropped and CRLF normalised; bad bytes replaced, never fatal."""
    with open(path, "rb") as fh:
        raw = fh.read()
    return raw.decode("utf-8-sig", "replace").replace("\r\n", "\n")


def parse(text):
    """(entries, sections): each entry a dict with its section, heading line, title, Status
    lines [(line, value)] and locators {(path, line_no): line seen}."""
    entries, sections, section, current, in_fence = [], [], None, None, False
    for n, line in enumerate(text.split("\n"), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        s = SECTION_RE.match(line)
        if s:
            section = s.group(1).strip()
            sections.append(section)
            current = None
            continue
        e = ENTRY_RE.match(line)
        if e:
            current = {"section": section, "line": n, "title": e.group(1), "status": [], "locators": {}}
            entries.append(current)
        if current is None:
            continue
        if not e:
            for sm in STATUS_RE.finditer(line):
                current["status"].append((n, sm.group(1).strip()))
        for lm in LOCATOR_RE.finditer(line):
            current["locators"].setdefault((lm.group(1), int(lm.group(2))), n)
    return entries, sections


def in_section(entry, pattern):
    return entry["section"] is not None and bool(pattern.match(entry["section"]))


def segments(path):
    return [s for s in path.replace("\\", "/").lstrip("~").split("/") if s not in ("", ".")]


def same_locator(a, b):
    """'exact' · 'suffix' · 'basename' · None for two (path, line) locators."""
    (pa, la), (pb, lb) = a, b
    if la != lb:
        return None
    sa, sb = segments(pa), segments(pb)
    if sa == sb:
        return "exact"
    short, longer = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    if not short or longer[-len(short):] != short:
        return None
    return "suffix" if len(short) >= 2 else "basename"


def check(text):
    """(entries, sections, closed_under_open, shared, possible, open_closed_shared)."""
    entries, sections = parse(text)
    opened = [e for e in entries if in_section(e, OPEN_SECTION_RE)]
    closed = [e for e in entries if in_section(e, CLOSED_SECTION_RE)]
    closed_under_open = [(e, ln, value) for e in opened for ln, value in e["status"] if CLOSED_RE.match(value)]
    shared, possible = [], []
    for i, a in enumerate(opened):
        for b in opened[i + 1:]:
            for la in a["locators"]:
                for lb in b["locators"]:
                    kind = same_locator(la, lb)
                    if kind in ("exact", "suffix"):
                        shared.append((la, lb, a, b))
                    elif kind == "basename":
                        possible.append((la, lb, a, b))
    open_closed_shared = sum(
        1 for a in opened for b in closed for la in a["locators"] for lb in b["locators"]
        if same_locator(la, lb) in ("exact", "suffix"))
    return entries, sections, closed_under_open, shared, possible, open_closed_shared


def show(text, width):
    return text if len(text) <= width else text[:width - 3] + "..."


def locator_text(loc):
    return f"{loc[0]}:{loc[1]}"


def main():
    vault, register = parse_args(sys.argv[1:])
    if register is None:
        root = vault if vault else "."
        if not all(os.path.isdir(os.path.join(root, d)) for d in ("raw", "wiki")):
            probe_failed(f"{root} is not a vault root (no raw/ or wiki/)")
        register = os.path.join(root, REGISTER_REL)
        label = REGISTER_REL
        if not os.path.exists(register):
            print(f"register-check: n/a (no {REGISTER_REL} — nothing captured yet; CLAUDE.md §12 "
                  f"recreates it at capture time)")
            return 0
    else:
        label = register
        if not os.path.isfile(register):
            probe_failed(f"{register} is not a file")

    # Controls first: a parser that cannot see a closed Status or a shared locator must never
    # print a clean register.
    _, _, c_closed, c_shared, _, _ = check(CONTROL_REGISTER)
    control_titles = ("the defect (minor)", "fixed and left under Open", "resolved and left under Open")
    if len(c_closed) != 3 or not all(any(t in e["title"] for e, _, _ in c_closed) for t in control_titles):
        probe_failed("the in-memory control's closed, fixed and resolved Status lines under ## Open were not "
                     "each caught exactly once (or an open Status naming those words later, a closed Status "
                     "under ## Closed, or one inside the fenced example, was)")
    if len(c_shared) != 1:
        probe_failed("the in-memory control's two Open entries citing one file:line in two spellings "
                     "were not paired exactly once")

    try:
        text = read_text(register)
    except OSError as exc:
        probe_failed(f"cannot read {register}: {exc}")
    entries, sections, closed_under_open, shared, possible, open_closed_shared = check(text)
    if not any(OPEN_SECTION_RE.match(s) for s in sections):
        probe_failed(f"{label} has no `## Open` heading — not a register this check can read")
    opened = [e for e in entries if in_section(e, OPEN_SECTION_RE)]
    closed = [e for e in entries if in_section(e, CLOSED_SECTION_RE)]
    other = len(entries) - len(opened) - len(closed)
    status_lines = sum(len(e["status"]) for e in entries)
    open_locators = sum(len(e["locators"]) for e in opened)

    print(f"REGISTER: {label} | {len(opened)} entries under ## Open · {len(closed)} under ## Closed · "
          f"{other} elsewhere | {status_lines} **Status**: lines read | {open_locators} file:line "
          f"locators in Open entries   (nonzero entry total = the probe ran)")
    print("CONTROL: in-memory register: a closed, a fixed and a resolved Status under ## Open -> each caught; "
          "an open Status naming those words later -> not a finding; two Open entries citing one file:line in "
          "two spellings -> paired; a closed Status under ## Closed and inside the fenced format example -> "
          "not a finding")
    print(f"CLOSED STATUS UNDER OPEN: {len(closed_under_open)}")
    for e, ln, value in closed_under_open:
        print(f"  {label}:{ln} · {show(e['title'], 90)} · **Status**: {show(value, 60)}")
    print(f"SHARED LOCATORS: {len(shared)} pair(s) of Open entries citing one file:line")
    for la, lb, a, b in shared:
        print(f"  {locator_text(la)} = {locator_text(lb)} · {label}:{a['line']} {show(a['title'], 60)} "
              f"| {label}:{b['line']} {show(b['title'], 60)}")
    print(f"POSSIBLE: {len(possible)} pair(s) sharing only a bare file name and line (information, never a finding)")
    for la, lb, a, b in possible:
        print(f"  {locator_text(la)} ~ {locator_text(lb)} · {label}:{a['line']} | {label}:{b['line']}")
    print(f"INFO: {open_closed_shared} locator(s) an Open entry shares with a Closed one "
          f"(line numbers drift as files change; never a finding)")
    return 1 if (closed_under_open or shared) else 0


if __name__ == "__main__":
    sys.exit(main())
