#!/usr/bin/env python3
"""Report source pages that admit conversion damage in prose while carrying no conversion flag.

Stdout-only by construction: reads pages, prints, writes nothing.

Why (known-issues 2026-09-08, ingest Step 0 conversions): a source page can record a damaged
conversion — in a `depth:` comment, a sentence in the summary, a note that the verbatim quotation
is unavailable — without raising a `flagged:` line. deep-lint's Step 2 reads the
flag channel and nothing else, so a damage admission written as prose is invisible to it. This
probe keys on the observable, the damage vocabulary, never on a named file:
    collapsed · lost inter-word spaces · inter-word · space-restored · run-together ·
    run together · verbatim quotation is unavailable · lost every chart · lost every figure ·
    lost every table · charts lost · figures lost
A page under wiki/sources/ whose frontmatter (any line, comments included) or body matches one
of those, case-insensitively, while its frontmatter carries no CONVERSION flag, is a finding.
The negative is keyed on the flag's own text: a `flagged:` line counts only when its value
carries the word `conversion` (`source conversion suspect …`, `conversion damage …`); a flag
about something else (`flagged: 2026-09-01 stale pricing table`) does not mask an admission,
since deep-lint would resolve that flag without ever reading the conversion. Fenced code, code
spans and HTML comments are NOT stripped: a comment is exactly where such an admission hides,
and a quotation of the vocabulary inside a source page is worth a look too.

Not an admission (known-issues 2026-09-09: a name-collision note ending "must not be collapsed"
was one standing false finding on every routine lint). Two observables suppress a line, and a
suppressed line is listed under SUPPRESSED with its reason, never counted as a finding, so a
marker that hides a genuine admission stays visible to the reader:
  - the page-side marker `<!-- lint: not a conversion admission -->` anywhere on the line;
  - a negation directly before the term: `not`, `never` or an `n't` contraction, with at most one
    form of `be` or `get` between (`not collapsed`, `must not be collapsed`, `isn't run
    together`). The guard is keyed on adjacency, never on the sentence: in "the conversion did
    not keep spacing and collapsed the columns" the term still fires, and a later un-negated
    term on a line whose first term is negated still fires.

Terminal state (ingest Step 0, 3c): a conversion flag is resolved when a repaired conversion
scored `clean` joins the page's `sources:` and the page's `## Summary` ends with a dated
Provenance sentence naming the repair file and the quotation check. That sentence necessarily
admits the old damage (it says what was repaired), so an admission line that also carries the
words `repaired conversion` is RESOLVED: counted under its own line, listed, never a finding.

Controls, in memory, before the scan: the damage sentence with no flag must be caught; the same
page with a conversion `flagged:` must not be a finding; with a non-conversion `flagged:` it must
be caught again; its admission line rewritten as a Provenance sentence naming a repaired
conversion must read resolved; an admission line carrying the marker must read suppressed; and a
negated term must read suppressed while its un-negated twin is caught. Every result prints, and a
control that fails is a PROBE FAILED (exit 2). The scan totals print as the positive control on
the count.

Usage (from the vault root):
  python3 .claude/skills/lint/check_flag_admissions.py [--vault ROOT] [ROOT]
  exit 0 = clean · 1 = findings · 2 = broken premise (not a vault root, no wiki/sources/, no
  page in it, a control that did not fire)
"""
import os
import re
import sys

USAGE = ("usage: check_flag_admissions.py [--vault ROOT] [ROOT]   "
         "(exit 0 clean · 1 findings · 2 broken premise)")

VOCABULARY = re.compile(
    r"\bcollapsed\b"
    r"|\blost inter-word spaces\b"
    r"|\binter-word\b"
    r"|\bspace-restored\b"
    r"|\brun-together\b"
    r"|\brun together\b"
    r"|\bverbatim quotation is unavailable\b"
    r"|\blost every chart\b"
    r"|\blost every figure\b"
    r"|\blost every table\b"
    r"|\bcharts lost\b"
    r"|\bfigures lost\b",
    re.I,
)
FM_RE = re.compile(r"\A---[ \t]*\n(.*?\n)---[ \t]*(?:\n|\Z)", re.S)
FLAGGED_LINE_RE = re.compile(r"^flagged:[ \t]*(.*?)[ \t]*$", re.M)
CONVERSION_FLAG_RE = re.compile(r"\bconversion\b", re.I)      # `conversion` or `source conversion`
RESOLVED_RE = re.compile(r"\brepaired conversion\b", re.I)
MARKER_RE = re.compile(r"<!--\s*lint:\s*not a conversion admission\s*-->", re.I)
# Matched against the text BEFORE one vocabulary hit: the negation, at most one form of be/get,
# then only emphasis, code or quote marks up to the term.
NEGATED_BEFORE_RE = re.compile(
    r"(?:\bnot|\bnever|n't)[*_]*\s+"
    r"(?:[*_]*(?:be|been|being|is|was|were|are|get|gets|got|gotten)[*_]*\s+)?"
    r"[*_`\"']*$",
    re.I,
)

CONTROL_PAGE = (
    "---\ntitle: \"Control\"\ntype: source\nconfidence: medium\n"
    "depth: standard # the conversion is run-together in places\n---\n\n"
    "## Summary\nThe source conversion collapsed inter-word spaces, so the verbatim quotation is unavailable.\n"
)
CONTROL_FLAGGED = CONTROL_PAGE.replace("confidence: medium\n",
                                       "confidence: medium\nflagged: 2026-01-01 source conversion suspect\n")
CONTROL_OTHER_FLAG = CONTROL_PAGE.replace("confidence: medium\n",
                                          "confidence: medium\nflagged: 2026-01-01 stale pricing table, re-read\n")
CONTROL_RESOLVED = (
    "---\ntitle: \"Control\"\ntype: source\nconfidence: medium\n---\n\n"
    "## Summary\nProvenance (2026-01-02): compiled from a damaged conversion (run-together prose); "
    "repaired conversion `raw/2-papers/example-repair.md` (clean); quotation check: 3 confirmed, 1 corrected, 0 unverifiable.\n"
)
CONTROL_MARKED = (
    "---\ntitle: \"Control\"\ntype: source\nconfidence: medium\n---\n\n"
    "## Summary\nThe source conversion collapsed inter-word spaces. <!-- lint: not a conversion admission -->\n"
)
CONTROL_NEGATED = (
    "---\ntitle: \"Control\"\ntype: source\nconfidence: medium\n---\n\n"
    "## Summary\nThe two project names are near-homographs and must not be collapsed.\n"
)
CONTROL_UNNEGATED = CONTROL_NEGATED.replace("must not be collapsed", "were collapsed by the conversion")


def probe_failed(message):
    print(f"PROBE FAILED: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_root(argv):
    """The sibling flag spelling or the historical positional form; an unknown flag is
    refused, never swallowed as a root (known-issues 2026-09-06)."""
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


def scan_page(text):
    """(has_flag, has_conversion_flag, hits, resolved, suppressed): hits and resolved are (line
    number, matched term, line) over the whole page, the `flagged:` lines themselves excluded from
    matching; a matching line that also names a repaired conversion goes to resolved; a line
    carrying the page-side marker, or whose every term is negated, goes to suppressed as (line
    number, term, line, reason)."""
    fm = FM_RE.match(text)
    flags = FLAGGED_LINE_RE.findall(fm.group(1)) if fm else []
    has_flag = bool(flags)
    has_conversion_flag = any(CONVERSION_FLAG_RE.search(v) for v in flags)
    hits, resolved, suppressed = [], [], []
    for n, line in enumerate(text.split("\n"), 1):
        if line.startswith("flagged:"):
            continue
        matches = list(VOCABULARY.finditer(line))
        if not matches:
            continue
        if MARKER_RE.search(line):
            suppressed.append((n, matches[0].group(0), line.strip(), "marker"))
            continue
        live = [m for m in matches if not NEGATED_BEFORE_RE.search(line[:m.start()])]
        if not live:
            suppressed.append((n, matches[0].group(0), line.strip(), "negation"))
            continue
        entry = (n, live[0].group(0), line.strip())
        (resolved if RESOLVED_RE.search(line) else hits).append(entry)
    return has_flag, has_conversion_flag, hits, resolved, suppressed


def show(line):
    return line if len(line) <= 120 else line[:117] + "..."


def main():
    root = parse_root(sys.argv[1:])
    if not all(os.path.isdir(os.path.join(root, d)) for d in ("raw", "wiki")):
        probe_failed(f"{root} is not a vault root (no raw/ or wiki/)")
    sources = os.path.join(root, "wiki", "sources")
    if not os.path.isdir(sources):
        probe_failed(f"{sources} does not exist — nothing to scan")

    # Controls first: a probe whose regex cannot fire must never print a clean scan.
    flag_c, conv_c, hits_c, res_c, sup_c = scan_page(CONTROL_PAGE)
    flag_f, conv_f, hits_f, res_f, sup_f = scan_page(CONTROL_FLAGGED)
    flag_o, conv_o, hits_o, res_o, sup_o = scan_page(CONTROL_OTHER_FLAG)
    flag_r, conv_r, hits_r, res_r, sup_r = scan_page(CONTROL_RESOLVED)
    _, _, hits_m, res_m, sup_m = scan_page(CONTROL_MARKED)
    _, _, hits_n, res_n, sup_n = scan_page(CONTROL_NEGATED)
    _, _, hits_u, res_u, sup_u = scan_page(CONTROL_UNNEGATED)
    if flag_c or conv_c or not hits_c or res_c or sup_c:
        probe_failed("the in-memory control page (damage prose, no flagged: key) was not caught")
    if not flag_f or not conv_f or not hits_f:
        probe_failed("the conversion-flagged control page was not read as flagged")
    if not flag_o or conv_o or not hits_o:
        probe_failed("the control page with a non-conversion flag was not read as an unmasked admission")
    if flag_r or hits_r or len(res_r) != 1:
        probe_failed("the control page naming a repaired conversion was not read as resolved")
    if hits_m or res_m or [s[3] for s in sup_m] != ["marker"]:
        probe_failed("the control line carrying the page-side marker was not read as suppressed")
    if hits_n or res_n or [s[3] for s in sup_n] != ["negation"]:
        probe_failed("the control line with a negated term (must not be collapsed) was not read as suppressed")
    if len(hits_u) != 1 or sup_u:
        probe_failed("the un-negated twin of the negation control was not caught")

    pages = []
    for dirpath, dirnames, filenames in os.walk(sources):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if name.endswith(".md"):
                pages.append(os.path.join(dirpath, name))
    if not pages:
        probe_failed(f"{sources} holds no .md page")

    flagged = conversion_flagged = matched = 0
    findings, resolved_pages, suppressed_pages = [], [], []
    for path in pages:
        try:
            text = read_text(path)
        except OSError as exc:
            probe_failed(f"cannot read {path}: {exc}")
        has_flag, has_conv, hits, resolved, suppressed = scan_page(text)
        flagged += has_flag
        conversion_flagged += has_conv
        matched += bool(hits or resolved or suppressed)
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        if resolved:
            resolved_pages.append((rel, resolved))
        if suppressed:
            suppressed_pages.append((rel, suppressed))
        if hits and not has_conv:
            findings.append((rel, hits))

    print(f"SCANNED: {len(pages)} pages under wiki/sources/ | {flagged} carry flagged: "
          f"({conversion_flagged} conversion) | {matched} match the damage vocabulary   "
          f"(nonzero page total = probe ran)")
    print(f"CONTROL: in-memory page admitting damage without flagged: -> caught "
          f"({len(hits_c)} term(s): {', '.join(sorted({h[1].lower() for h in hits_c}))}); "
          f"with a conversion flagged: -> not a finding; with a non-conversion flagged: -> caught; "
          f"its admission rewritten as a Provenance sentence naming a repaired conversion -> resolved; "
          f"an admission line carrying the page-side marker -> suppressed; "
          f"a negated term (must not be collapsed) -> suppressed, its un-negated twin -> caught")
    n_res = sum(len(r) for _, r in resolved_pages)
    print(f"RESOLVED: {n_res} line(s) on {len(resolved_pages)} page(s) — an admission that also names "
          f"a repaired conversion (the terminal state; never a finding)")
    for rel, entries in resolved_pages:
        for n, term, line in entries:
            print(f"  {rel}:{n} · {term} · {show(line)}")
    n_sup = sum(len(s) for _, s in suppressed_pages)
    n_marker = sum(1 for _, s in suppressed_pages for e in s if e[3] == "marker")
    print(f"SUPPRESSED: {n_sup} line(s) on {len(suppressed_pages)} page(s) — {n_marker} by the page-side "
          f"marker, {n_sup - n_marker} by a negation before the term (listed, never a finding)")
    for rel, entries in suppressed_pages:
        for n, term, line, why in entries:
            print(f"  ({why}) {rel}:{n} · {term} · {show(line)}")
    print(f"ADMISSIONS WITHOUT FLAG: {len(findings)}")
    for rel, hits in findings:
        for n, term, line in hits:
            print(f"  {rel}:{n} · {term} · {show(line)}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
