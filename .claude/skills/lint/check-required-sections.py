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

Controls, in memory, before the scan: a development page with no `## Sources Used` must be
caught; the same page carrying the heading only inside a fenced block must still be caught; with
the heading present it must not be; a research-depth source page carrying `## Citation` and
`## Related` must be clean, the same page without `## Related` must be caught for `## Related` alone,
and the same page with `## Citation` renamed must be checked against the full source row. A control
that does not behave is PROBE FAILED (exit 2).

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

CONTROL_MISSING = ("---\ntitle: \"Control\"\ntype: development\nconfidence: medium\n---\n\n"
                   "## Design\nA design with no sources section.\n\n## Related\n- the hub page\n")
CONTROL_FENCED = CONTROL_MISSING + "\n```\n## Sources Used\n```\n"
CONTROL_PRESENT = CONTROL_MISSING + "\n## Sources Used\n- the hub page\n"
CONTROL_TEMPLATE = ("---\ntitle: \"Control\"\ntype: source\ndepth: research\nconfidence: medium\n---\n\n"
                    "## Citation\nA reference.\n\n## Research Question\nA question.\n\n## Related\n- the hub page\n")
CONTROL_TEMPLATE_NORELATED = CONTROL_TEMPLATE.replace("\n## Related\n- the hub page\n", "\n")
CONTROL_UNSHAPED = CONTROL_TEMPLATE.replace("## Citation\n", "## Reference\n")


def probe_failed(message):
    print(f"PROBE FAILED: {message}", file=sys.stderr)
    raise SystemExit(2)


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
    template_total = 0
    for path in pages:
        try:
            text = read_text(path)
        except OSError as exc:
            probe_failed(f"cannot read {os.path.relpath(path, root)} ({exc.__class__.__name__})")
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
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
