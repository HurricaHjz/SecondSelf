#!/usr/bin/env python3
"""handback-count.py: counts the items a Handback puts to its owner, by group; flags an item put twice;
counts the items sent to the weekly review. Stdout only: it reads the files it is given and writes none.

usage:
  handback-count.py REPORT [REPORT ...] [--earlier FILE ...]
      REPORT: the parts of one day's Handback (one file, or the parts the main session folds).
      --earlier: earlier Handbacks, or a waiting list that keeps the groups' headings; a file that names
      no group and gives no item is refused, since nothing could be checked against it. Every file after
      --earlier, up to the next option, is an earlier file, so the parts of today come before it. An
      item of REPORT whose title matches one of theirs is flagged as put again as new.
  handback-count.py --mapping FILE [--reports DIR]
      FILE maps mornings to reports, as {"mornings": {"<day>": {"reports": [{"file": "<name>",
      "lines": [first, last]}]}}} ("lines" optional); DIR defaults to output/reports in the vault three
      folders above this script. Prints one row per morning, the reports of a morning taken as its parts.

What counts (the parser below):
- An item is a Decide, Approve or To-do item, found by the rules in `items`. Undo and Done are not items.
- An item sent to the weekly review is one under a heading or bold label naming the weekly review, or a
  list line outside any Decide, Approve or To-do group whose own bold lead names it. It is counted apart
  and is not among the items put to the owner. A line listing several items in prose counts once.
- A waiting line is a list line that says what "still waits" (the one line that counts what still
  waits and links the list): the words in its bold lead, or anywhere on a line that carries a link. It
  is listed apart and never counted as a new item. A numbered item (a bold lead opening with its
  number) is an item even when it says "still waits".
- Put twice: two items whose titles share at least half their words of four or more letters (Jaccard
  0.5, the threshold E2's carried-item measure used; set by judgement there, unmeasured as a classifier),
  or whose titles are identical. Between two of the given parts (two items of one part are never
  paired), and between a part and an --earlier file. An item that matches several is flagged once,
  against its best match. Title matching is a floor: an item reworded past the threshold is missed.
  Weekly-review items are counted, never paired. An earlier weekly-review item stays among the earlier
  items, so one held then and put as new now is flagged.

Every run first parses a planted Handback built into this file and checks the result (the positive
control for any zero it prints); a mismatch is a broken premise.

Exit: 0 counted, nothing flagged; 1 counted, an item flagged as put twice; 2 PROBE FAILED (a missing or
unreadable report, earlier file or mapping; a report or earlier file that names none of the Handback's
groups and gives no item; the built-in control failing).
"""
import collections
import json
import os
import re
import sys

# ---- the parser: E2's handbacklib (12 November 2026), copied whole; additions marked "added" ----
# Its rules, as E2 wrote them:
# - A group (Decide, Approve, To-do) opens at a heading (`#`..`####`) or a bold-only label line
#   (`**Decide**`, `**Approve** (...)`) naming it. A deeper heading that names no group keeps the group open
#   (`### For the study discussion` under `## Decide`); a heading at the group's level or above that names
#   no group closes it, and so does a label line naming something else (`**Undo if you disagree**`).
# - Candidate items are column-0 lines inside a group: list lines (`- `, `* `, `N. `) and paragraph lines that
#   open with a bold numbered lead (`**3. Close a gap ...**`). A list line outside any group still counts when
#   its own bold lead names the group (`- **K1. Decide: ...**`, `- **E9. Your to-do, ...**`).
# - Within one stretch of a group, if any candidate has a bold lead, the candidates without one are detail
#   lines (`- For it: ...`, `- Options: ...`) and are dropped. A line saying only "None" or "Nothing" is no item.
#   Indented lines are options or detail, never items. Fenced code is skipped.
# Added: an inline group name followed by a number is a cross-reference, not a marker, and moves no item
# (on E2's mapping it moves none; on the Handback of 12 November it put an Approve and a To-do item under
# Decide). Added: the weekly-review group. A heading or label naming the weekly review opens it, ahead of any
# other group the same words name; nested under a Decide, Approve or To-do heading it closes back to that
# group at the next heading of its level that names no group. Inside it an inline Decide, Approve or
# To-do lead does not move the item out. Outside every group, a bold lead naming it makes the line one.

GROUP_RX = re.compile(r"(?i)\b(decide|decisions? for (you|him)|approve|approvals?|your to-?dos?|to-?dos?|what needs (you|your word))\b")
HEADING_RX = re.compile(r"^(#{1,4})\s+(.*)$")
LABEL_RX = re.compile(r"^\*\*([^*]+)\*\*\s*(\(.*\))?\s*:?\s*$")
ITEM_RX = re.compile(r"^(?:-|\*|\d+\.)\s+(.*)$")
PARA_RX = re.compile(r"^\*\*([A-Z]{0,3}\d+[a-z]?\..*?)\*\*")
LEAD_RX = re.compile(r"^\*\*(.+?)\*\*")
NUM_RX = re.compile(r"^([A-Z]{0,3}\d+(?:\.\d+)?[a-z]?)[.:)]\s*")
WEEKLY_RX = re.compile(r"(?i)\bweekly review\b")          # added
WEEKLY = "Weekly review"                                    # added
WAITING_RX = re.compile(r"(?i)\bstill wait")                # added
LINK_RX = re.compile(r"\]\(|\[\[")                          # added: a Markdown or wiki link
NAMED_RX = re.compile(r"(?i)\b(decide|decisions?|approve|approvals?|to-?dos?|undo|done|weekly review)\b")  # added


def norm_group(text):
    t = text.lower()
    if "decide" in t or "decision" in t or "what needs" in t:
        return "Decide"
    if "approv" in t:
        return "Approve"
    if "to-do" in t or "todo" in t or "to do" in t:
        return "To-do"
    return None


def _label(lead_t, body):
    num = NUM_RX.match(lead_t)
    label = num.group(1) if num else ""
    title = (lead_t[num.end():] if num else lead_t) or body[:80]
    return label, title.strip().rstrip(":").strip()


def items(text):
    """[(group, label, title, line_no)]; group is Decide, Approve, To-do or the weekly review."""
    out = []
    group, glevel = None, 9
    outer = None                                            # added: the group a weekly-review heading sits in
    stretch = []
    in_code = False

    def flush():
        if stretch:
            if any(b for (_, _, _, _, b) in stretch):
                keep = [s for s in stretch if s[4]]
            else:
                keep = stretch
            out.extend((g, l, t, n) for (g, l, t, n, _) in keep)
            stretch.clear()

    for n, line in enumerate(text.split("\n"), 1):
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        h = HEADING_RX.match(line)
        if h:
            level = len(h.group(1))
            g = GROUP_RX.search(h.group(2))
            if WEEKLY_RX.search(h.group(2)):                # added: the weekly-review heading
                flush()
                if group == WEEKLY and level > glevel:
                    continue
                outer = (group, glevel) if group is not None and group != WEEKLY and level > glevel else None
                group, glevel = WEEKLY, level
            elif g and norm_group(g.group(0)):
                flush()
                group, glevel = norm_group(g.group(0)), level
                outer = None                                # added
            elif group is not None and level > glevel:
                flush()
            elif outer is not None and level > outer[1]:    # added: back to the enclosing group
                flush()
                group, glevel = outer
                outer = None
            else:
                flush()
                group, glevel = None, 9
                outer = None                                # added
            continue
        if not line.startswith((" ", "\t", "-", "*")) or LABEL_RX.match(line.strip() or "x"):
            lab = LABEL_RX.match(line.strip()) if line.strip().startswith("**") else None
            if lab and not PARA_RX.match(line):
                flush()
                if WEEKLY_RX.search(lab.group(1)):          # added: the weekly-review label
                    group = WEEKLY
                else:
                    g = GROUP_RX.match(lab.group(1).strip())
                    group = norm_group(g.group(0)) if g else None
                glevel = 9
                outer = None                                # added
                continue
        if line.startswith((" ", "\t")):
            continue
        para = PARA_RX.match(line)
        m = ITEM_RX.match(line)
        if not (m or para):
            continue
        body = m.group(1).strip() if m else line.strip()
        if re.match(r"(?i)^(none|nothing)\b", body):
            continue
        lead = LEAD_RX.match(body)
        lead_t = lead.group(1) if lead else ""
        g = group
        # added: "(?!\s*\d)", so a cross-reference ("if you take (a) in Decide 2") moves no item
        inline = re.search(r"(?i)\b(decide|approve|your to-?do)\b(?!\s*\d)", lead_t)
        if inline and group != WEEKLY:                      # added: "and group != WEEKLY"
            g = norm_group(inline.group(1))
        elif g is None and lead and WEEKLY_RX.search(lead_t):   # added
            g = WEEKLY
        if g is None:
            continue
        label, title = _label(lead_t, body)
        stretch.append((g, label, title, n, bool(lead)))
    flush()
    return out

# ---- end of the parser ----


def names_a_group(text):
    """True when a heading or bold label outside fenced code names one of the Handback's groups."""
    in_code = False
    for line in text.split("\n"):
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        h = HEADING_RX.match(line)
        lab = LABEL_RX.match(line.strip()) if line.strip().startswith("**") else None
        part = h.group(2) if h else (lab.group(1) if lab else None)
        if part is not None and NAMED_RX.search(part):
            return True
    return False


def words(t):
    return {w for w in re.findall(r"[a-z]{4,}", t.lower())}


def same_item(a, b):
    """Jaccard of the two titles' long words, or 1.0 for identical titles; None below the threshold."""
    wa, wb = words(a), words(b)
    if wa and wb:
        j = len(wa & wb) / len(wa | wb)
        return j if j >= 0.5 else None
    na, nb = re.sub(r"\W+", " ", a.lower()).strip(), re.sub(r"\W+", " ", b.lower()).strip()
    return 1.0 if na and na == nb else None


class ProbeFailed(Exception):
    pass


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError) as err:
        why = getattr(err, "strerror", None) or str(err)
        raise ProbeFailed("cannot read %s (%s: %s)" % (path, err.__class__.__name__, why))


def waiting_lines(lines, lo, hi):
    """Column-0 list or bold-lead lines outside fenced code, in [lo, hi], that say what still waits:
    "still wait" in the line's bold lead, or anywhere in a line that also carries a link (the one line
    "counts what still waits and links the list"). A mid-sentence "still waits" in a detail line with
    no link is not one (on E2's mapping the only bare hit was such a line), and nor is a numbered item.

    Found apart from `items`, whose detail-line rule drops a waiting line that has no bold lead."""
    out = []
    in_code = False
    for n, line in enumerate(lines, 1):
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not lo <= n <= hi:
            continue
        m = ITEM_RX.match(line)
        if not (m or LEAD_RX.match(line)):
            continue
        lead = LEAD_RX.match(m.group(1).strip() if m else line)
        if lead and NUM_RX.match(lead.group(1)):            # a numbered item is an item, never a waiting line
            continue
        if (lead and WAITING_RX.search(lead.group(1))) or (WAITING_RX.search(line) and LINK_RX.search(line)):
            out.append(n)
    return out


def classify(path, text, lo=1, hi=10 ** 9, premise=True):
    """The items of one report (or one line range of it), split into new, weekly-review and waiting."""
    lines = text.split("\n")
    new, weekly = [], []
    held = waiting_lines(lines, lo, hi)
    waiting = [{"file": path, "line": n, "group": "", "label": "", "title": lines[n - 1].strip()} for n in held]
    for g, label, title, n in items(text):
        if not lo <= n <= hi or n in held:
            continue
        rec = {"file": path, "line": n, "group": g, "label": label, "title": title}
        if g == WEEKLY:
            weekly.append(rec)
        else:
            new.append(rec)
    if premise and not (new or weekly or waiting):
        if not names_a_group("\n".join(lines[lo - 1:hi])):
            where = "" if (lo, hi) == (1, 10 ** 9) else " lines %d-%d" % (lo, hi)
            raise ProbeFailed("%s%s names none of the Handback's groups (Decide, Approve, Your to-dos, Undo "
                              "if you disagree, Done, the weekly review) and gives no item: not a Handback, "
                              "so its zero means nothing" % (path, where))
    return new, weekly, waiting


def twice(today, earlier):
    """Flags: each item of today matched against an item of another part of today (once per pair) or
    against an earlier item. Two items of one part are never paired: within one file the writer's own
    numbering separates them, and on E2's mapping such pairs were 5 of the 6 flagged and none was the same
    item (the builder's reading of the titles, 14 November 2026)."""
    flags = []
    flagged = set()
    for i, a in enumerate(today):
        if id(a) in flagged:
            continue
        best = None
        for b in today[i + 1:]:
            if id(b) in flagged or b["file"] == a["file"]:
                continue
            j = same_item(a["title"], b["title"])
            if j is not None and (best is None or j > best[0]):
                best = (j, b)
        if best:
            flags.append(("within", a, best[1], best[0]))
            flagged.add(id(a))
            flagged.add(id(best[1]))
    for a in today:
        if id(a) in flagged:
            continue
        best = None
        for b in earlier:
            j = same_item(a["title"], b["title"])
            if j is not None and (best is None or j > best[0]):
                best = (j, b)
        if best:
            flags.append(("earlier", a, best[1], best[0]))
            flagged.add(id(a))
    return flags


CONTROL_TODAY = "\n".join([
    "# Planted Handback", "## Decide", "- **1. Pick the venue.** text", "  - (a) option",
    "- **2. Keep the old cover.** text", "- 3 items still wait from Monday: [list](waiting.md)",
    "## Approve", "**3. Install the repair.** body", "- For it: detail",
    "### For the weekly review", "- **4. Rename the tool folder.** body", "## Your to-dos", "- **5. Sign the form.**",
    "- **8. Keep the old cover.** again, in the same part", "## Undo if you disagree", "- **6. Moved the notes.**",
    "## Done", "- **Coming to the weekly review, not asked today:** the larger step",
])
CONTROL_PART = "\n".join(["# Second part", "## Your to-dos", "- **7. Pick the venue.** again"])
CONTROL_EARLIER = "\n".join(["# Earlier", "## Approve", "- **9. Install the repair.** body"])


def control():
    """The built-in planted Handback: the positive control every run carries."""
    new, weekly, waiting = classify("<control>", CONTROL_TODAY)
    new += classify("<control-part>", CONTROL_PART)[0]
    old = classify("<control-earlier>", CONTROL_EARLIER)[0]
    flags = twice(new, old)
    got = (sorted((x["group"], x["label"]) for x in new), sorted(x["line"] for x in weekly),
           [x["line"] for x in waiting], sorted((k, a["label"], b["label"]) for k, a, b, _ in flags))
    want = ([("Approve", "3"), ("Decide", "1"), ("Decide", "2"), ("To-do", "5"), ("To-do", "7"), ("To-do", "8")],
            [11, 18], [6], [("earlier", "3", "9"), ("within", "1", "7")])
    if got != want:
        raise ProbeFailed("the built-in planted Handback gives %r, not %r: the parser no longer reads the "
                          "shape it was written for" % (got, want))
    return ("control: the planted two-part Handback gives Decide 2, Approve 1, To-do 3, weekly review 2, "
            "waiting line 1, put twice 2 (one across its parts, one against its earlier file; the repeat "
            "inside one part not paired), as expected")


def cell(t):
    return t.replace("|", "/").replace("\n", " ")


def count_row(name, new, weekly, waiting):
    c = collections.Counter(x["group"] for x in new)
    return "| %s | %d | %d | %d | %d | %d | %d |" % (name, c["Decide"], c["Approve"], c["To-do"], len(new),
                                                     len(weekly), len(waiting))


def flag_line(kind, a, b, j):
    what = "within this Handback" if kind == "within" else "put again as new"
    return "- PUT TWICE (%s): %s %s \"%s\" (%s:%d) matches %s %s \"%s\" (%s:%d), Jaccard %.2f" % (
        what, a["group"], a["label"], cell(a["title"][:90]), a["file"], a["line"], b["group"], b["label"],
        cell(b["title"][:90]), b["file"], b["line"], j)


def print_list(title, recs):
    print("\n### %s" % title)
    if not recs:
        print("none")
    for x in recs:
        print("- %s:%d %s %s" % (x["file"], x["line"], x["label"], cell(x["title"][:110])))


def main_reports(reports, earlier):
    print("## Handback count (handback-count.py)")
    print(control())
    seen = {}
    for p in reports + earlier:
        key = os.path.realpath(p)
        if key in seen:
            raise ProbeFailed("%s is given twice (as %s and %s): every item of it would match itself" % (
                key, seen[key], p))
        seen[key] = p
    texts = [(p, read(p)) for p in reports]
    old_texts = [(p, read(p)) for p in earlier]
    print("\n| report | Decide | Approve | To-do | items | weekly review | waiting lines |")
    print("|---|---|---|---|---|---|---|")
    all_new, all_weekly, all_waiting = [], [], []
    for p, t in texts:
        new, weekly, waiting = classify(p, t)
        print(count_row(cell(p), new, weekly, waiting))
        all_new += new
        all_weekly += weekly
        all_waiting += waiting
    print(count_row("**total**", all_new, all_weekly, all_waiting))
    old = []
    for p, t in old_texts:
        n_, w_, _ = classify(p, t)
        old += n_ + w_
    flags = twice(all_new, old)
    print("\n### Items put twice")
    print("\n".join(flag_line(*f) for f in flags) if flags else "none")
    print_list("Sent to the weekly review (counted apart; not put to the owner today)", all_weekly)
    print_list("Waiting lines (not counted as new)", all_waiting)
    c = collections.Counter(x["group"] for x in all_new)
    print("\nHANDBACK SUMMARY reports=%d decide=%d approve=%d todo=%d items=%d weekly_review=%d waiting_lines=%d "
          "put_twice=%d earlier_files=%d earlier_items=%d" % (len(texts), c["Decide"], c["Approve"], c["To-do"],
                                                             len(all_new), len(all_weekly), len(all_waiting),
                                                             len(flags), len(old_texts), len(old)))
    return 1 if flags else 0


def main_mapping(mapping, reports_dir):
    print("## Handback count by morning (handback-count.py; mapping: %s)" % os.path.basename(mapping))
    print(control())
    try:
        M = json.loads(read(mapping))
    except ValueError as err:
        raise ProbeFailed("mapping %s is not JSON (%s)" % (mapping, err))
    mornings = M.get("mornings") if isinstance(M, dict) else None
    if not isinstance(mornings, dict) or not mornings:
        raise ProbeFailed("mapping %s holds no \"mornings\" object" % mapping)
    if not os.path.isdir(reports_dir):
        raise ProbeFailed("no reports folder at %s" % reports_dir)
    print("\n| morning | reports | Decide | Approve | To-do | items | weekly review | waiting lines | put twice |")
    print("|---|---|---|---|---|---|---|---|---|")
    total = collections.Counter()
    cache = {}
    flag_lines = []
    for day, v in mornings.items():
        rs = v.get("reports") if isinstance(v, dict) else None
        if not isinstance(rs, list):
            raise ProbeFailed("morning %s has no \"reports\" list" % day)
        new, weekly, waiting = [], [], []
        for r in rs:
            if not isinstance(r, dict) or not isinstance(r.get("file"), str):
                raise ProbeFailed("morning %s has a report entry with no \"file\"" % day)
            p = os.path.join(reports_dir, r["file"])
            rng = r.get("lines", [1, 10 ** 9])
            if not (isinstance(rng, list) and len(rng) == 2 and all(type(x) is int for x in rng)):
                raise ProbeFailed("morning %s: %s has a \"lines\" value that is not [first, last]" % (day, r["file"]))
            if p not in cache:
                cache[p] = read(p)
            lo, hi = rng
            n_, w_, t_ = classify(r["file"], cache[p], lo, hi)
            new += n_
            weekly += w_
            waiting += t_
        flags = twice(new, [])
        flag_lines += ["%s %s" % (day, flag_line(*f)[2:]) for f in flags]
        c = collections.Counter(x["group"] for x in new)
        row = {"reports": len(rs), "Decide": c["Decide"], "Approve": c["Approve"], "To-do": c["To-do"],
               "items": len(new), "weekly": len(weekly), "waiting": len(waiting), "twice": len(flags)}
        total.update(row)
        print("| %s | %d | %d | %d | %d | %d | %d | %d | %d |" % ((day,) + tuple(row[k] for k in (
            "reports", "Decide", "Approve", "To-do", "items", "weekly", "waiting", "twice"))))
    print("| **total** | %d | %d | %d | %d | %d | %d | %d | %d |" % tuple(total[k] for k in (
        "reports", "Decide", "Approve", "To-do", "items", "weekly", "waiting", "twice")))
    print("\n### Items put twice within a morning")
    print("\n".join("- " + x for x in flag_lines) if flag_lines else "none")
    print("\nHANDBACK SUMMARY mornings=%d reports=%d decide=%d approve=%d todo=%d items=%d weekly_review=%d "
          "waiting_lines=%d put_twice=%d" % (len(mornings), total["reports"], total["Decide"], total["Approve"],
                                             total["To-do"], total["items"], total["weekly"], total["waiting"],
                                             total["twice"]))
    return 1 if total["twice"] else 0


def usage(msg):
    print("PROBE FAILED: %s" % msg)
    print(__doc__.split("\n\n")[1])
    return 2


def main(argv):
    reports, earlier, mapping, reports_dir = [], [], None, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            print(__doc__)
            return 0
        if a == "--earlier":
            j = i + 1
            while j < len(argv) and not argv[j].startswith("--"):
                earlier.append(argv[j])
                j += 1
            if j == i + 1:
                return usage("--earlier needs a value")
            i = j
            continue
        if a in ("--mapping", "--reports"):
            if i + 1 >= len(argv):
                return usage("%s needs a value" % a)
            if a == "--mapping":
                mapping = argv[i + 1]
            else:
                reports_dir = argv[i + 1]
            i += 2
            continue
        if a.startswith("--"):
            return usage("unknown option %s" % a)
        reports.append(a)
        i += 1
    try:
        if mapping:
            if reports or earlier:
                return usage("--mapping takes no report and no --earlier")
            vault = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir,
                                                 os.pardir))
            return main_mapping(mapping, reports_dir or os.path.join(vault, "output", "reports"))
        if not reports:
            return usage("no report given")
        return main_reports(reports, earlier)
    except ProbeFailed as err:
        print("PROBE FAILED: %s" % err)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
