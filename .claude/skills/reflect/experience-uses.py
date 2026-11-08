#!/usr/bin/env python3
"""experience-uses.py — count experience pages' use notes (deep-lint Step 4a).

Stdout-only by construction, apart from temporary extractions it removes: it writes nothing to the
vault. The head writes `Measures` itself, by anchored edit: this script finds, the head judges.

Input: `turns.md` from `handsoff.py extract-transcript`, or with `--all` every session transcript the
harness still holds, each extracted in turn. A use note is one plain clause in the
session's own prose naming a page with its exact name in brackets, as the page's preamble asks
(`I read the leave page (owner-away) and applied its entry on what to weigh (E1)`). So a hit counts
only in an assistant turn's prose, in a sentence that names a label or says it read or applied the
page, which keeps out a sentence that merely discusses one. Human turns are set aside, since the owner quoting a page is no
use; so is every tool line, including the trailing tool lines of a prose turn, since a note a shell
command writes is a record, not the session's prose. A `- Read:` line naming a page is evidence of
reading, never a use. Text the extraction never carries (tool results, skill text, thinking) cannot
count by construction.

For each page it prints the count, as `COUNT <page>: uses N`, which deep-lint sets as `uses` where
it is larger than the stored value, never adding, with the labels named and how often; two mismatches, a read with no note and a
note with no read, the second perhaps a helper's restated note whose read sits in its own record;
and with `--notes`, each hit's turn, labels and sentence, and each `- Read:` line. A note before a
page's `uses ... since` date is left out, since a reach change restarts that page's count.

`--from-turn K` counts turns after K only. `--all` counts each page's notes from its `uses ... since`
date across every transcript still held, and prints the count; deep-lint sets `uses` to the larger
of the page's value and that count, never adding, so a rerun changes nothing and no note counts
twice. The harness removes old transcripts (the oldest found on 7 November 2026 was 30 days old;
reviewed on the lifecycle row's date), so `uses` stops growing past that window: a `GAP` line says so
for a page whose date is older than the oldest transcript. A session that cannot be read prints
`UNREAD` and only lowers the figure. A read with no note prints per session, so a note elsewhere
cannot hide it. A helper's own notes sit in its own transcript, which this leaves out: the head's
restatement is what counts.

Control, in memory, before the scan: a fixture extraction with one prose note, one tool-line note
and one human quotation must count one. A control that does not behave is PROBE FAILED (exit 2).

Usage (from the vault root):
  python3 .claude/skills/reflect/experience-uses.py --turns FILE [--vault ROOT] [--from-turn K] [--notes]
  python3 .claude/skills/reflect/experience-uses.py --all [--vault ROOT] [--projects P] [--notes]
  exit 0 = counted (a count of zero prints its scan totals, and an unread session prints UNREAD) ·
  2 = broken premise (not a vault root, an unknown flag, an unreadable extraction, an extraction
  with no turn headings, no transcript folder, a failed control)
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

USAGE = ("usage: experience-uses.py --turns FILE [--vault ROOT] [--from-turn K] [--notes] | "
         "--all [--vault ROOT] [--projects DIR] [--notes]")
FOLDER = "wiki/experience"
TURN = re.compile(r"^## turn (\d+) · (human|assistant(?: · tool calls)?) · (.*)$")
TOOL_LINE = re.compile(r"^- (?:[A-Z][A-Za-z]*|mcp__[A-Za-z0-9_]+)(?:: .*)?$")
LABELS = re.compile(r"\b([A-Z][0-9]+)\b")
DATED = re.compile(r"^\d{4}-\d\d-\d\d")


def split_turns(text):
    """[(number, role, lines, stamp)] in file order; text above the first heading is the header."""
    turns, current = [], None
    for line in text.splitlines():
        m = TURN.match(line)
        if m:
            current = (int(m.group(1)), m.group(2), [], m.group(3).strip())
            turns.append(current)
        elif current is not None:
            current[2].append(line)
    return turns


def prose_and_tools(lines):
    """A turn's prose lines and its tool lines. The extraction puts a turn's tool lines under its
    prose, so only the trailing run of tool-shaped lines is tool lines: a prose bullet that looks
    like one in mid-text stays prose."""
    end = len(lines)
    while end and not lines[end - 1].strip():
        end -= 1
    start = end
    while start and (TOOL_LINE.match(lines[start - 1]) or not lines[start - 1].strip()):
        start -= 1
    tools = [l for l in lines[start:end] if l.strip()]
    return lines[:start], tools


def sentences(text):
    return re.split(r"(?<=[.!?])\s+(?=[A-Z(\[`*])", text)


def page_starts(root, stems):
    """Each page's `uses ... since` date: a reach change restarts its count."""
    out = {}
    for stem in stems:
        try:
            text = (root / FOLDER / (stem + ".md")).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            text = ""
        m = re.search(r"uses \d+ and repeats \d+ since (\d{4}-\d\d-\d\d)", text)
        out[stem] = m.group(1) if m else ""
    return out


def analyse(turns, stems, from_turn=0, starts=None):
    """{stem: {'notes': [(turn, labels, none, sentence, stamp)], 'reads': [turn]}}, and totals. A
    note in an undated turn cannot be placed against a page's date, so it counts as undated."""
    starts = starts or {}
    found = {s: {"notes": [], "reads": [], "tool_hits": 0} for s in stems}
    totals = {"turns": 0, "assistant": 0, "human": 0, "tool_lines": 0, "undated": 0}
    for number, role, lines, stamp in turns:
        if number <= from_turn:
            continue
        totals["turns"] += 1
        if role == "human":
            totals["human"] += 1
            continue
        totals["assistant"] += 1
        prose, tools = (([], [l for l in lines if l.strip()]) if role.endswith("tool calls")
                        else prose_and_tools(lines))
        totals["tool_lines"] += len(tools)
        for line in tools:
            for stem in stems:
                if line.startswith("- Read:") and re.search(
                        r"(?<![A-Za-z0-9_-])" + re.escape(stem) + r"\.md\b", line):
                    found[stem]["reads"].append(number)
                elif "(%s)" % stem in line:
                    found[stem]["tool_hits"] += 1
        for sentence in sentences(" ".join(l.strip() for l in prose if l.strip())):
            for stem in stems:
                if "(%s)" % stem not in sentence or not (
                        LABELS.search(sentence) or re.search(r"\b(?:read|applied)\b", sentence, re.I)):
                    continue
                if starts.get(stem) and not DATED.match(stamp):
                    totals["undated"] += 1
                    continue
                if starts.get(stem) and stamp[:10] < starts[stem]:
                    continue
                labels = sorted(set(LABELS.findall(sentence)))
                found[stem]["notes"].append((number, labels, "none applied" in sentence.lower(),
                                             sentence.strip(), stamp))
    return found, totals


def control():
    text = ("# header\n\n## turn 1 · human · t\n\nthe page (alpha) says so\n\n"
            "## turn 2 · assistant · t\n\nI read the page (alpha) and applied its entry (E1).\n\n"
            "- Bash: echo the page (alpha) was read\n\n"
            "## turn 3 · assistant · tool calls · t\n\n- Read: /v/wiki/experience/alpha.md\n")
    found, _ = analyse(split_turns(text), ["alpha"])
    a = found["alpha"]
    return (len(a["notes"]) == 1 and a["notes"][0][1] == ["E1"] and a["reads"] == [3]
            and a["tool_hits"] == 1)


def parse_args(argv):
    options = {"vault": ".", "turns": None, "from_turn": 0, "all": False, "projects": None,
               "notes": False}
    names = {"--vault": "vault", "--turns": "turns", "--from-turn": "from_turn",
             "--projects": "projects"}
    args = list(argv)
    while args:
        flag = args.pop(0)
        if flag == "--notes":
            options["notes"] = True
        elif flag == "--all":
            options["all"] = True
        elif flag in names and args:
            options[names[flag]] = args.pop(0)
        else:
            print(USAGE, file=sys.stderr)
            sys.exit(2)
    try:
        options["from_turn"] = int(options["from_turn"])
    except ValueError:
        print(USAGE, file=sys.stderr)
        sys.exit(2)
    if bool(options["turns"]) == bool(options["all"]):
        print(USAGE, file=sys.stderr)
        sys.exit(2)
    return options


def projects_dir(root):
    """The harness's transcript folder for a vault: its path, non-alphanumerics as dashes."""
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(root))


def sweep(root, stems, projects):
    """Count across every held transcript, each page from its own date. Returns (found, totals,
    sessions, oldest transcript date, sessions that could not be read, per-session misses)."""
    tool = Path(__file__).resolve().parent.parent / "delegate" / "handsoff.py"
    starts = page_starts(root, stems)
    found = {s: {"notes": [], "reads": [], "tool_hits": 0} for s in stems}
    totals = {"turns": 0, "assistant": 0, "human": 0, "tool_lines": 0, "undated": 0}
    sessions, oldest, failed, misses = 0, None, [], []
    files = sorted(Path(projects).glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if files:
        oldest = min(p.stat().st_mtime for p in files)
    with tempfile.TemporaryDirectory(prefix="experience-uses-") as scratch:
        for path in files:
            out = os.path.join(scratch, path.stem)
            done = subprocess.run([sys.executable, "-B", str(tool), "extract-transcript", "--session",
                                   path.stem, "--out", out, "--projects-root",
                                   str(Path(projects).parent)],
                                  capture_output=True, text=True)
            turns_file = Path(out) / "turns.md"
            if done.returncode != 0 or not turns_file.is_file():
                failed.append(path.stem)
                continue
            turns = split_turns(turns_file.read_text(encoding="utf-8", errors="replace"))
            part, count = analyse(turns, stems, 0, starts)
            sessions += 1
            for key in totals:
                totals[key] += count[key]
            for stem in stems:
                for name in ("notes", "reads"):
                    found[stem][name] += part[stem][name]
                found[stem]["tool_hits"] += part[stem]["tool_hits"]
                if part[stem]["reads"] and not part[stem]["notes"]:
                    misses.append((stem, path.stem))
    return found, totals, sessions, oldest, failed, misses, starts


def report(stems, found, notes, per_session=None):
    for stem in stems:
        page = found[stem]
        for number, labels, none, sentence, stamp in page["notes"] if notes else []:
            what = "none applied" if none else (" ".join(labels) or "no label named")
            print("NOTE %s turn %d %s (%s): %s" % (stem, number, stamp[:10], what, sentence[:240]))
        for number in page["reads"] if notes else []:
            print("READ %s turn %d" % (stem, number))
        if page["reads"] and not page["notes"] and per_session is None:
            print("MISMATCH %s: read with no note (turns %s)"
                  % (stem, " ".join(map(str, page["reads"]))))
        if page["notes"] and not page["reads"] and per_session is None:
            print("MISMATCH %s: note with no read in this session (a helper's restated note "
                  "reads elsewhere)" % stem)
        if page["notes"] or page["reads"]:
            none = sum(1 for n in page["notes"] if n[2])
            named = {}
            for note in page["notes"]:
                for label in note[1]:
                    named.setdefault(label, []).append(note[4][:10])
            tally = ", ".join("%s ×%d (last %s)" % (k, len(v), max(v)) for k, v in sorted(named.items()))
            print("COUNT %s: uses %d, of them none applied %d (tool-line hits set aside: %d)%s"
                  % (stem, len(page["notes"]), none, page["tool_hits"],
                     "; labels " + tally if tally else ""))


def main(argv):
    options = parse_args(argv)
    root = Path(options["vault"]).resolve()
    if not (root / "raw").is_dir() or not (root / "wiki").is_dir():
        print("PROBE FAILED: %s is not a vault root (no raw/ or wiki/)" % root, file=sys.stderr)
        return 2
    if not control():
        print("PROBE FAILED: the in-memory control did not behave")
        return 2
    print("control: a prose note counted; a tool line and a human quotation did not")
    stems = sorted(p.stem for p in (root / FOLDER).glob("*.md") if p.is_file())
    if options["all"]:
        projects = Path(options["projects"]) if options["projects"] else projects_dir(root)
        if not projects.is_dir():
            print("PROBE FAILED: no transcript folder at %s" % projects)
            return 2
        found, totals, sessions, oldest, failed, misses, starts = sweep(root, stems, projects)
        report(stems, found, options["notes"], misses)
        for stem, session in misses:
            print("MISMATCH %s: read with no note in session %s" % (stem, session))
        for session in failed:
            print("UNREAD %s: its extraction failed, so the count is a lower bound" % session)
        print("experience uses: pages %d · sessions %d · unread %d · turns scanned %d · assistant %d · "
              "human %d · tool lines %d · notes %d · undated notes %d"
              % (len(stems), sessions, len(failed), totals["turns"], totals["assistant"],
                 totals["human"], totals["tool_lines"], sum(len(found[s]["notes"]) for s in stems),
                 totals["undated"]))
        if oldest:
            import datetime
            first = datetime.date.fromtimestamp(oldest).isoformat()
            print("oldest transcript: %s" % first)
            for stem in stems:
                if starts.get(stem) and starts[stem] < first:
                    print("GAP %s: its count starts %s, the oldest transcript is %s, so it is a "
                          "lower bound" % (stem, starts[stem], first))
        return 0
    try:
        text = Path(options["turns"]).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print("PROBE FAILED: cannot read %s: %s" % (options["turns"], exc))
        return 2
    turns = split_turns(text)
    if not turns:
        print("PROBE FAILED: no turn headings in %s" % options["turns"])
        return 2
    found, totals = analyse(turns, stems, options["from_turn"], page_starts(root, stems))
    report(stems, found, options["notes"])
    print("experience uses: pages %d · turns scanned %d of %d (from turn %d) · assistant %d · "
          "human %d · tool lines %d · notes %d"
          % (len(stems), totals["turns"], len(turns), options["from_turn"], totals["assistant"],
             totals["human"], totals["tool_lines"], sum(len(found[s]["notes"]) for s in stems)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
