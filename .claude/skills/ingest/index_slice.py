#!/usr/bin/env python3
"""index_slice.py - the index slice a parallel compile brief names instead of the Step 4 section read.

For one lane's assigned raws this helper reduces repeated index reads. It prints:
  - the name list of the Step 4 table's five network sections (Entities, Tools, Concepts, Models,
    Benchmarks): every `- [[...]]` target, in CLAUDE.md section 5 `name` mode, so the lane's
    membership recall equals the section read's;
  - in `anchor` form, the full index line of each entry whose page name or `aliases:` value occurs
    verbatim in those raws (case-folded, word-bounded), each followed by a `matched:` line naming the
    term and the raw;
  - `MISSING <name>` for an entry whose page is not on disk (a lint finding, never fatal);
  - the index's sha256 prefix (16 hex, the length the de-dup probe greps; it dates the slice), the
    byte counts, and the control entry, which must be found in the name list.
The head persists the output beside the run ledger as <run>-index-<lane>.txt and names that file in
the brief; any entry outside the anchors is fetched by exact name.

Usage:
  python3 index_slice.py RAW [RAW ...] [--index FILE] [--wiki DIR] [--vault DIR] [--control NAME]
The index defaults to <vault>/wiki/index.md, the vault to three directories above this script, the
wiki to the index's directory; --control defaults to the first `- [[` line under `## Models`, read by
a plain line scan independent of the entry pattern.

A page is looked up as <wiki>/<section directory>/<name>.md, then by file name anywhere in the wiki
(case-folded, the section's own directory first). Aliases come from the page's frontmatter
`aliases:`, inline (`[a, b]`) or as a block list. A name or alias of any length anchors, a
one-character one (R) included, case-folded and word-bounded like every other.
Exit 0 = the slice printed and its control found; 2 = PROBE FAILED: an unreadable or empty index, one
of the five section headings missing, renamed or repeated (they are the Step 4 table's own list, so
a changed layout stops the slicer instead of shrinking its output), zero raws or an unreadable raw, a
control entry absent from the name list, or a planted matcher case that did not behave.
Reads only: it creates, modifies, moves and deletes nothing.
"""
import argparse, hashlib, os, re, sys

SECTIONS = ("Entities", "Tools", "Concepts", "Models", "Benchmarks")
DIRS = {"Entities": "entities", "Tools": "tools", "Concepts": "concepts", "Models": "models", "Benchmarks": "benchmarks"}
HERE = os.path.dirname(os.path.abspath(__file__))
VAULT_DEFAULT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
ENTRY = re.compile(r"^- \[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
MIN_TERM = 1   # every name or alias anchors, as the design promises; a one-letter name costs slice bytes, never recall


def fail(msg):
    print("PROBE FAILED: " + msg)
    sys.exit(2)


def split_sections(text):
    """({heading: [lines, heading line included]}, {heading: count}) for every `## ` heading."""
    sections, counts, cur = {}, {}, None
    for line in text.splitlines(keepends=True):
        m = re.match(r"## (.+?)\s*$", line)
        if m:
            cur = m.group(1)
            counts[cur] = counts.get(cur, 0) + 1
            sections.setdefault(cur, []).append(line)
        elif cur is not None:
            sections[cur].append(line)
    return sections, counts


def page_files(wiki):
    """Case-folded file stem -> paths, for every .md under the wiki."""
    found = {}
    for root, dirs, files in os.walk(wiki):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for f in sorted(files):
            if f.endswith(".md"):
                found.setdefault(f[:-3].casefold(), []).append(os.path.join(root, f))
    return found


def find_page(name, section, wiki, files):
    exact = os.path.join(wiki, DIRS[section], name + ".md")
    if os.path.isfile(exact):
        return exact
    hits = sorted(files.get(name.casefold(), []), key=lambda p: os.sep + DIRS[section] + os.sep not in p)
    return hits[0] if hits else None


def aliases(path):
    """The page frontmatter's `aliases:` values, inline or as a block list."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read(16384).splitlines()
    except OSError:
        return []
    if not lines or lines[0].strip() != "---":
        return []
    out = []
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            break
        m = re.match(r"aliases\s*:\s*(.*)$", lines[i])
        if not m:
            continue
        rest = m.group(1).strip()
        if rest.startswith("["):
            inner = rest[1:rest.rfind("]")] if "]" in rest else rest[1:]
            out += [x.strip().strip("'\"") for x in re.findall(r"\"[^\"]*\"|'[^']*'|[^,]+", inner)]
        elif rest:
            out.append(rest.strip("'\""))
        else:
            for follow in lines[i + 1:]:
                item = re.match(r"\s*-\s+(.*)$", follow)
                if not item:
                    break
                out.append(item.group(1).strip().strip("'\""))
    return [a for a in (x.strip() for x in out) if a]


def matches(term, text_cf):
    """The term occurs in the case-folded text with no word character on either side."""
    t = term.casefold()
    if len(t) < MIN_TERM or t not in text_cf:
        return False
    return re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", text_cf) is not None


def planted():
    """Planted cases through the matcher; returns what did not behave."""
    bad = []
    raw = "We evaluate GPT-4o and ChatGPT on MATH.".casefold()
    if not matches("GPT-4o", raw):
        bad.append("a term present in the raw was not matched")
    if matches("AIME", raw):
        bad.append("a name absent from the raw was matched")
    if matches("GPT", "chatgptx"):
        bad.append("a name inside a longer word was matched")
    if not matches("math", raw):
        bad.append("case folding")
    if not matches("R", "we use r for analysis.") or matches("R", "rust and rl"):
        bad.append("a one-character name alone, or inside a longer word")
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Print one lane's index slice: the five network sections' name list, the index "
                    "lines its raws name (by page name or alias), the index hash and byte counts. Reads only.",
        epilog="Exit 0 slice printed, control found; 2 PROBE FAILED (see the module docstring).")
    ap.add_argument("raws", nargs="*", metavar="RAW", help="the lane's assigned raw files")
    ap.add_argument("--vault", default=VAULT_DEFAULT, help="the vault root (default: three directories above this script)")
    ap.add_argument("--index", default=None, help="the index (default: <vault>/wiki/index.md)")
    ap.add_argument("--wiki", default=None, help="the wiki directory for page lookups (default: the index's directory)")
    ap.add_argument("--control", default=None, help="an entry that must be in the name list (default: the first under ## Models)")
    a = ap.parse_args(argv)

    index = a.index or os.path.join(a.vault, "wiki", "index.md")
    wiki = a.wiki or os.path.dirname(os.path.abspath(index))
    try:
        with open(index, "rb") as fh:
            data = fh.read()
    except OSError as e:
        fail("the index %s is unreadable (%s)" % (index, e))
    if not data.strip():
        fail("the index %s is empty" % index)
    text = data.decode("utf-8", errors="replace")
    sections, counts = split_sections(text)
    for s in SECTIONS:
        if counts.get(s, 0) != 1:
            fail("section heading `## %s` is %s in %s: the five names are the Step 4 table's own list, so a "
                 "changed layout stops the slicer" % (s, "missing or renamed" if not counts.get(s) else
                                                      "repeated %d times" % counts[s], index))
    if not a.raws:
        fail("zero raws: name the lane's assigned raw files")
    raws = []
    for path in a.raws:
        try:
            with open(path, "rb") as fh:
                body = fh.read()
        except OSError as e:
            fail("raw unreadable: %s (%s)" % (path, e))
        raws.append((path, body.decode("utf-8", errors="replace").casefold(), len(body)))
    bad = planted()
    if bad:
        fail("a planted matcher case did not behave: " + "; ".join(bad))

    control = a.control
    if control is None:
        for s in ("Models",) + SECTIONS:
            first = next((line for line in sections[s] if line.startswith("- [[")), None)
            if first:
                control = first[4:].split("]]")[0].split("|")[0].split("#")[0].strip()
                break
    entries = {s: [(m.group(1).strip(), line.rstrip("\r\n")) for line in sections[s] for m in [ENTRY.match(line)] if m]
               for s in SECTIONS}
    names = {name for s in SECTIONS for name, _line in entries[s]}
    if not control or control not in names:
        fail("the control entry %r is not in the name list of the five sections" % control)

    files = page_files(wiki)
    out, names_bytes, anchor_bytes, anchored, missing, alias_pages = [], 0, 0, 0, [], 0
    out.append("## name list (CLAUDE.md section 5 `name` mode: every `[[...]]` target of the five network sections)")
    for s in SECTIONS:
        out.append("### %s (%d)" % (s, len(entries[s])))
        for name, _line in entries[s]:
            out.append(name)
            names_bytes += len(name.encode("utf-8")) + 1
    out.append("## anchors (CLAUDE.md section 5 `anchor` form: the index line of each entry whose name or an "
               "`aliases:` value occurs in the raws, case-folded, word-bounded)")
    for s in SECTIONS:
        block = []
        for name, line in entries[s]:
            page = find_page(name, s, wiki, files)
            als = aliases(page) if page else []
            if page is None:
                missing.append(name)
            alias_pages += bool(als)
            hit = None
            for term, how in [(name, "name")] + [(x, "alias") for x in als]:
                raw_hit = next((os.path.basename(p) for p, text_cf, _n in raws if matches(term, text_cf)), None)
                if raw_hit:
                    hit = (term, how, raw_hit)
                    break
            if hit:
                block += [line, "  matched: %s (%s) in %s" % hit]
                anchor_bytes += len(line.encode("utf-8")) + 1
                anchored += 1
        if block:
            out.append("### %s" % s)
            out += block
    out += ["MISSING %s" % name for name in missing]
    body = "\n".join(out) + "\n"
    five = sum(len(line.encode("utf-8")) for s in SECTIONS for line in sections[s])
    total = sum(len(e) for e in entries.values())
    print("index slice · %s · sha256 %s · raws %d (%d bytes): %s"
          % (index, hashlib.sha256(data).hexdigest()[:16], len(raws), sum(n for _p, _t, n in raws),
             ", ".join(os.path.basename(p) for p, _t, _n in raws)))
    print(body, end="")
    print("bytes: index %d · five sections %d (%.1f %% of the index) · names %d · anchor lines %d · this slice above %d"
          % (len(data), five, 100.0 * five / len(data), names_bytes, anchor_bytes, len(body.encode("utf-8"))))
    print("entries %d · anchored %d · missing %d · pages carrying aliases %d" % (total, anchored, len(missing), alias_pages))
    print("control: `%s` found in the name list" % control)
    print("controls: planted term matched · planted absent name not matched · a name inside a longer word not matched · case folded · a one-character name matched alone and not inside a word")


if __name__ == "__main__":
    main()
