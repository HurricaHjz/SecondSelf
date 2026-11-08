#!/usr/bin/env python3
"""experience-line.py — the monthly listing of experience pages (deep-lint Step 4a).

Stdout-only by construction: reads, prints, writes nothing. For each selected page it prints its
entries, owner entries and bytes, and it lists a page with no entry in the label form inside
`## Rules`, an entry without its source label and date, a missing multi-agent field, a missing
lifecycle row, an absent `Measures` core field, a probe older than the last reach change, a probe
that saw gross failure, a probe naming another Claude Code major version than the installed one, an
entry above the last label issued, an `owner` entry still dated `provisional`, an `owner` entry
changed, removed or relabelled since the last baseline whatever the page's size, and a lesson with
no date in twelve months (set by judgement, unmeasured; reviewed on the lifecycle row's date).
Further `Measures` fields are ignored. `updated:` is never read, since a records-only edit moves it.

Growth. The latest deep-lint section of `wiki/log.md` carrying a `- **Experience baselines**:`
bullet supplies each page's bytes and entry digests; later deep-lint sections without one are named
and skipped. A malformed or partial latest bullet leaves growth unmeasured rather than borrowing an
older run. The run's own bullet is printed after `BASELINE-APPEND`, only when every read succeeded;
the deep-lint run appends it to its log entry at completion. Digests are the first 16 hexadecimal
characters of SHA-256 over an entry's text before its source bracket: compact change indicators,
never proof of identity. A baseline also keeps the labels of its `owner` entries and a digest of
each whole line, so a relabel cannot pass as an unchanged entry.

Control, in memory, before the scan: a clean page must list nothing, the same page without its
entries must list. A control that does not behave is PROBE FAILED (exit 2).

Usage (from the vault root):
  python3 .claude/skills/deep-lint/experience-line.py [--vault ROOT] [--selection SEL]
  exit 0 = listings or none · 2 = broken premise (not a vault root, an unknown flag, an unreadable
  page or log, a control that did not behave)
"""
import calendar
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

USAGE = ("usage: experience-line.py [--vault ROOT] [--selection SEL]   "
         "(exit 0 listings or none · 2 broken premise)")
DEFAULT_SELECTION = "wiki/experience/"
LIFECYCLE = "wiki/developments/check-lifecycle.md"
LOG = "wiki/log.md"
BULLET = "- **Experience baselines**: "


def entries(text):
    """{label: line} for the label-form lines inside `## Rules`, and nowhere else."""
    rules, found = False, {}
    for line in text.splitlines():
        if line.startswith("## "):
            rules = line.strip() == "## Rules"
            continue
        m = re.match(r"^([A-Z][0-9]+)\. ", line) if rules else None
        if m:
            found[m.group(1)] = line
    return found


def idea(line):
    return re.split(r"\((?:owner|lesson) · \d{4}-\d\d-\d\d", line, maxsplit=1)[0]


def digest(line):
    return hashlib.sha256(idea(line).encode()).hexdigest()[:16]


def whole(line):
    return hashlib.sha256(line.encode()).hexdigest()[:16]


def owner_changes(page, rules, was):
    """Each `owner` entry of the baseline that is gone, changed or no longer `owner`."""
    out = []
    kept_labels = was.get("owners") or {}
    for label, line in rules.items():
        if "(owner · " in line and label not in kept_labels:
            out.append("owner entry new since the baseline: %s entry %s" % (page, label))
    for label, kept in kept_labels.items():
        line = rules.get(label)
        if line is None:
            out.append("owner entry gone since the baseline: %s entry %s" % (page, label))
        elif "(owner · " not in line:
            out.append("owner entry relabelled since the baseline: %s entry %s" % (page, label))
        elif whole(line) != kept:
            out.append("owner entry changed since the baseline: %s entry %s" % (page, label))
    return out


def harness_major():
    """Claude Code's installed major version, or '' where it cannot be read."""
    try:
        done = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.match(r"\s*(\d+)\.", done.stdout or "")
    return m.group(1) if m else ""


def date_after(text, key):
    m = re.search(re.escape(key) + r"(\d{4}-\d\d-\d\d)", text)
    return m.group(1) if m else ""


def page_listings(page, text, cutoff):
    """The listings one page's text earns, by its own content alone."""
    out = []
    rules = entries(text)
    for label, line in rules.items():
        source = re.search(r"\((owner|lesson) · (\d{4}-\d\d-\d\d)( provisional)?(?: ·|\))", line)
        if not source:
            out.append("entry without its source label and date: %s entry %s" % (page, label))
            continue
        if source.group(1) == "owner":
            if source.group(3):
                out.append("owner entry dated provisional, awaiting his decision: %s entry %s"
                           % (page, label))
        else:
            latest = max(re.findall(r"\d{4}-\d\d-\d\d", line))
            if latest < cutoff:
                out.append("lesson with no date in twelve months: %s entry %s (latest %s)"
                           % (page, label, latest))
    if not rules:
        out.append("no entry in the label form (E1. or A1.) inside ## Rules: %s" % page)
    if not any("**Feature:**" in l and "**Multi-agent pattern:**" in l for l in text.splitlines()):
        out.append("no multi-agent field: %s" % page)
    measures = next((l for l in text.splitlines() if l.startswith("**Measures:**")), "")
    if not measures:
        out.append("no Measures line: %s" % page)
        return out
    fields = measures.removeprefix("**Measures:**").strip().split(" · ")

    def field(key):
        return next((s for s in fields if s.startswith(key)), "")
    reach, probe = date_after(field("reach changed "), "reach changed "), date_after(field("probe "), "probe ")
    added = date_after(field("entry added "), "entry added ")
    if not reach:
        out.append("Measures line without its reach-changed date: %s" % page)
    if not added:
        out.append("Measures line without its entry-added date: %s" % page)
    if not re.fullmatch(r"uses [0-9]+ and repeats [0-9]+ since \d{4}-\d\d-\d\d", field("uses ")):
        out.append("Measures line without its uses-and-repeats count: %s" % page)
    if not field("probe "):
        out.append("Measures line without its probe field: %s" % page)
    if reach and (not probe or probe < reach):
        out.append("probe older than the last reach change: %s (probe %s, reach changed %s)"
                   % (page, probe or "none", reach))
    if "gross failure:" in field("probe "):
        out.append("probe saw gross failure: %s" % page)
    last = field("last label ")
    if not last:
        out.append("Measures line without its last label issued: %s" % page)
        return out
    tops = {}
    for letter, number in re.findall(r"\b([A-Z])([0-9]+)\b", last):
        tops[letter] = max(int(number), tops.get(letter, 0))
    for label in rules:
        if int(label[1:]) > tops.get(label[0], 0):
            out.append("entry labelled above the last label issued: %s entry %s (%s)"
                       % (page, label, last))
    return out


def control():
    good_page = ("**Feature:** a · **Moment:** m · **Read by:** `x` (y) · **Multi-agent pattern:** "
                 "one agent\n\n## Rules\nE1. Do it. (lesson · 2099-01-01 · taught · [[x]])\n\n"
                 "## Measures\n**Measures:** reach changed 2026-01-01 · probe 2026-01-02 on a in b, "
                 "no gross failure · entry added 2026-01-01 · uses 0 and repeats 0 since 2026-01-01"
                 " · last label E1\n")
    silent = not page_listings("a.md", good_page, "2000-01-01")
    fires = any("no entry" in x for x in page_listings(
        "a.md", good_page.replace("E1. Do it.", "Do it."), "2000-01-01"))
    return silent and fires


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def usable(record):
    return (isinstance(record, dict) and type(record.get("bytes")) is int and record["bytes"] >= 0
            and isinstance(record.get("entries"), dict)
            and all(re.fullmatch(r"[A-Z][0-9]+", k) and isinstance(v, str)
                    and re.fullmatch(r"[0-9a-f]{16}", v) for k, v in record["entries"].items()))


def latest_baseline(log, today):
    """(baseline or None, the reason it is None, skipped headings)."""
    sections = re.split(r"(?=^## \[)", log, flags=re.M)
    deep = [s for s in sections if re.match(r"^## \[[^\n]+\] deep-lint \|", s)]
    skipped, previous = [], None
    for section in reversed(deep):
        if any(line.startswith(BULLET.rstrip()) for line in section.splitlines()):
            previous = section
            break
        skipped.append(section.splitlines()[0])
    if not previous:
        return None, "no previous completed deep-lint baseline", skipped
    payloads = [l[len(BULLET):] for l in previous.splitlines() if l.startswith(BULLET)]
    if len(payloads) != 1:
        return None, "the latest section does not carry exactly one baseline", skipped
    try:
        candidate = json.loads(payloads[0], object_pairs_hook=unique_object)
        if candidate.get("version") != 1 or candidate.get("complete") is not True:
            raise ValueError("not a complete version-1 baseline")
        dt.date.fromisoformat(candidate["date"])
        if candidate["date"] > today.isoformat():
            raise ValueError("future baseline")
        if not isinstance(candidate.get("pages"), dict):
            raise ValueError("no pages map")
    except (ValueError, TypeError, KeyError, AttributeError):
        return None, "malformed latest baseline", skipped
    return candidate, "", skipped


def parse_args(argv):
    options = {"--vault": ".", "--selection": DEFAULT_SELECTION}
    args = list(argv)
    while args:
        flag = args.pop(0)
        if flag in options and args:
            options[flag] = args.pop(0)
        else:
            print(USAGE, file=sys.stderr)
            sys.exit(2)
    return options["--vault"], options["--selection"]


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
    if not control():
        print("PROBE FAILED: the in-memory control did not behave")
        return 2
    print("control: a clean page listed nothing; a page without entries listed")
    pages = set()
    for item in selected:
        if item.endswith("/"):
            pages.update(p.relative_to(root).as_posix() for p in (root / item).glob("*.md")
                         if p.is_file())
        else:
            pages.add(item)
    if not pages:
        print("experience deep-lint: no pages (a state; nothing listed)")
        return 0
    today = dt.date.today()
    day = min(today.day, calendar.monthrange(today.year - 1, today.month)[1])
    cutoff = today.replace(year=today.year - 1, day=day).isoformat()
    failures, listings = [], []

    def listed(text):
        listings.append(text)
        print("LIST " + text)

    try:
        lifecycle = (root / LIFECYCLE).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        lifecycle = None
        failures.append("cannot read %s, so no lifecycle row was checked" % LIFECYCLE)
    try:
        log = (root / LOG).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        log = ""
        failures.append("cannot read %s" % LOG)
    baseline, reason, skipped = latest_baseline(log, today)
    if baseline:
        for heading in skipped:
            print("BASELINE-SKIPPED %s (no Experience baselines bullet)" % heading)
    elif skipped:
        print("BASELINE-SKIPPED %d earlier deep-lint sections carry no bullet" % len(skipped))
    current = {"version": 1, "complete": True, "date": today.isoformat(),
               "selection": selection, "pages": {}}
    major = harness_major()
    if not major:
        print("harness version unread: no probe's seat was compared")
    seen = {}
    for page in sorted(pages):
        try:
            data = (root / page).read_bytes()
            text = data.decode("utf-8")
        except (OSError, UnicodeError):
            failures.append("cannot read %s" % page)
            continue
        rules = entries(text)
        owners = sum(1 for line in rules.values() if re.search(r"\(owner · ", line))
        print("PAGE %s: %d entries (%d owner), %d bytes" % (page, len(rules), owners, len(data)))
        seen[page] = hashlib.sha256(data).hexdigest()
        now_entries = {label: digest(value) for label, value in rules.items()}
        owner_lines = {label: whole(line) for label, line in rules.items() if "(owner · " in line}
        current["pages"][page] = {"bytes": len(data), "entries": now_entries, "owners": owner_lines}
        was = baseline["pages"].get(page) if baseline else None
        if not usable(was):
            why = "page absent or malformed in the latest baseline" if baseline else reason
            listed("growth unmeasured: %s (%s)" % (page, why))
        else:
            print("BASELINE %s: deep-lint %s, %d bytes" % (page, baseline["date"], was["bytes"]))
            if len(data) > was["bytes"]:
                added = ", ".join(l for l in now_entries if l not in was["entries"]) or "none"
                reworded = ", ".join(l for l in now_entries if l in was["entries"]
                                     and now_entries[l] != was["entries"][l]) or "none"
                listed("grew against deep-lint baseline %s: %s (%d to %d bytes; entries added: %s; "
                       "entries reworded: %s; judge a trim)"
                       % (baseline["date"], page, was["bytes"], len(data), added, reworded))
            for item in owner_changes(page, rules, was):
                listed(item)
        for item in page_listings(page, text, cutoff):
            listed(item)
        probe = next((l for l in text.splitlines() if l.startswith("**Measures:**")), "")
        named_major = re.search(r"Claude Code (\d+)", probe)
        if major and named_major and named_major.group(1) != major:
            listed("probe names Claude Code %s, installed %s: %s" % (named_major.group(1), major, page))
        if lifecycle is not None and page not in lifecycle and \
                not any(s in lifecycle for s in selected if s.endswith("/")):
            listed("no lifecycle row naming %s: %s" % (selection, page))
    for page, expected in seen.items():
        try:
            actual = hashlib.sha256((root / page).read_bytes()).hexdigest()
        except OSError:
            actual = None
        if actual != expected:
            failures.append("page changed during read: %s" % page)
    if not failures:
        print("BASELINE-APPEND " + BULLET + json.dumps(current, ensure_ascii=False, sort_keys=True,
                                                       separators=(",", ":")))
    for f in failures:
        print("PROBE FAILED: " + f)
    print("experience deep-lint: pages %d · listed %d" % (len(pages), len(listings)))
    return 2 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
