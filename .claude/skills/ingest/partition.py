#!/usr/bin/env python3
"""Print a disjoint, byte-balanced assignment of converted sources; read only.

--inbox reads every direct *.md file, including native Markdown; neighbouring
originals are not counted again. --ledger reads exactly one run_open inbox list
(path strings or objects with a file field), validates each listed file and uses
its same-stem .md conversion. A listed original and its Markdown are one source;
repeated paths, aliases of a source, or multiple originals for one source fail.
Ledger paths beginning raw/ are vault-relative; bare names are relative to raw/.
Other relative paths are vault-relative. --vault defaults to the installed
script's vault root, three directories above its directory.

Groups contain one exact stem per line, separated by blank lines. Each group is
indivisible. Largest groups/sources go first into the lightest lane; ties use path
order then lane number. --lanes prints exactly N lanes (empty lanes included).
--max-bytes starts with ceil(total bytes / budget) lanes, adding a lane when the
lightest cannot fit the next group. A source/group above the budget fails instead
of silently exceeding it; an explicit --lanes assignment has no byte cap.

Paths in lane lines use shell quoting, so spaces and apostrophes round-trip.
The footer follows a controls line proving exact-once coverage and a planted
duplicate rejected by the same assertion. Exit 0 prints the assignment; exit 2
prints PROBE FAILED for an invalid argument, unreadable input, empty inbox,
malformed ledger, duplicate source, unknown/ambiguous group stem or broken control.
Creates, modifies, moves and deletes nothing. Standard library only; no network.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import shlex
import sys

DEFAULT_MAX_BYTES = 250000  # set by judgement, unmeasured: source budget beside the index slice
VAULT_DEFAULT = Path(__file__).resolve().parents[3]


def fail(message):
    print("PROBE FAILED: " + message)
    raise SystemExit(2)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        fail(message)


def positive_integer(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("expected a positive integer")
    if number < 1:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return number


def file_info(path):
    try:
        if not path.is_file():
            fail("missing file or not a regular file: %s" % path)
        with path.open("rb") as source:
            source.read(1)  # prove readability; sizes are measured from disk, not the ledger
        stat = path.stat()
        if "\n" in str(path) or "\r" in str(path):
            fail("a source path contains a line break: %r" % str(path))
        return (stat.st_dev, stat.st_ino), stat.st_size
    except OSError as error:
        fail("unreadable file %s (%s)" % (path, error))


def ledger_paths(ledger, vault):
    try:
        lines = ledger.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        fail("unreadable ledger %s (%s)" % (ledger, error))
    opened = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            fail("malformed ledger JSON on line %d" % number)
        if not isinstance(event, dict):
            fail("ledger event on line %d is not an object" % number)
        if event.get("event") == "run_open":
            opened.append(event)
    if len(opened) != 1:
        fail("ledger must hold exactly one run_open event")
    inbox = opened[0].get("inbox")
    if not isinstance(inbox, list):
        fail("run_open inbox must be a list")
    paths = []
    for item in inbox:
        name = item.get("file") if isinstance(item, dict) else item
        if not isinstance(name, str) or not name.strip():
            fail("run_open inbox entry must name a non-empty file path")
        path = Path(name).expanduser()
        if not path.is_absolute():
            path = vault / (Path("raw") / path if len(path.parts) == 1 else path)
        paths.append(path.absolute())
    return paths


def sources_from(paths, from_ledger):
    sources, inputs, owners = {}, set(), {}
    for path in paths:
        identity, _size = file_info(path)
        if identity in inputs:
            fail("source seen twice: %s" % path)
        inputs.add(identity)
        converted = path if path.suffix == ".md" else path.with_suffix(".md")
        key, size = file_info(converted)
        canonical = converted.resolve()
        if key in owners:
            old_roles, old_converted = owners[key]
            role = "markdown" if path.suffix == ".md" else "original"
            paired = (from_ledger and canonical == old_converted
                      and role not in old_roles)
            if not paired:
                fail("source seen twice: %s" % path)
            old_roles.add(role)
        else:
            owners[key] = ({"markdown" if path.suffix == ".md" else "original"}, canonical)
            sources[canonical] = size
    if not sources:
        fail("empty inbox: no Markdown sources")
    return sources


def make_units(sources, group_file):
    groups = []
    if group_file is not None:
        try:
            text = group_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            fail("unreadable group file %s (%s)" % (group_file, error))
        current = []
        for line in text.splitlines() + [""]:
            if line.strip():
                current.append(line.strip())
            elif current:
                groups.append(current)
                current = []
        if not groups:
            fail("empty group file")
    stems = {}
    for path in sources:
        stems.setdefault(path.stem, []).append(path)
    units, assigned = [], set()
    for group in groups:
        unit = []
        for stem in group:
            matches = stems.get(stem, [])
            if not matches:
                fail("group names unknown stem: %s" % stem)
            if len(matches) != 1:
                fail("group names ambiguous stem: %s" % stem)
            path = matches[0]
            if path in assigned:
                fail("source seen twice in groups: %s" % stem)
            assigned.add(path)
            unit.append(path)
        units.append(tuple(sorted(unit)))
    units.extend((path,) for path in sources if path not in assigned)
    return sorted(units, key=lambda unit: (-sum(sources[p] for p in unit), unit))


def coverage_problem(expected, lanes):
    counts = Counter(path for lane in lanes for path in lane)
    if set(counts) != set(expected) or any(count != 1 for count in counts.values()):
        return "disjointness assertion failed: every source must occur exactly once"
    return None


def assign(sources, units, lane_count, budget):
    total = sum(sources.values())
    count = lane_count if lane_count is not None else max(1, (total + budget - 1) // budget)
    if budget is not None and any(sum(sources[p] for p in unit) > budget for unit in units):
        fail("a source/group exceeds --max-bytes; increase the budget or use --lanes")
    lanes, sizes = [[] for _ in range(count)], [0] * count
    for unit in units:
        size = sum(sources[path] for path in unit)
        lightest = min(range(len(lanes)), key=lambda index: (sizes[index], index))
        if budget is not None and sizes[lightest] + size > budget:
            lanes.append([])
            sizes.append(0)
            lightest = len(lanes) - 1
        lanes[lightest].extend(unit)
        sizes[lightest] += size
    problem = coverage_problem(sources, lanes)
    if problem:
        fail(problem)
    control = next(iter(sources))
    if (coverage_problem([control], [(control,)]) is not None
            or coverage_problem([control], [(control, control)]) is None
            or coverage_problem([control], [()]) is None):
        fail("coverage control did not reject a duplicate and an omission and accept a clean assignment")
    return lanes, sizes


def main(argv=None):
    parser = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--inbox", type=Path, help="raw root: direct *.md files only")
    source.add_argument("--ledger", type=Path, help="JSONL run ledger: the run_open inbox list")
    sizing = parser.add_mutually_exclusive_group()
    sizing.add_argument("--lanes", type=positive_integer, help="exact number of lanes")
    sizing.add_argument("--max-bytes", type=positive_integer,
                        help="converted bytes per lane (default 250000; set by judgement, unmeasured)")
    parser.add_argument("--group", type=Path, help="stems, one per line; blank lines separate groups")
    parser.add_argument("--vault", type=Path, default=VAULT_DEFAULT,
                        help="base for relative ledger paths (default: installed script's vault)")
    args = parser.parse_args(argv)
    if args.inbox is not None:
        try:
            paths = sorted(p.absolute() for p in args.inbox.iterdir() if p.suffix == ".md" and not p.is_dir())
        except OSError as error:
            fail("unreadable inbox %s (%s)" % (args.inbox, error))
    else:
        paths = ledger_paths(args.ledger, args.vault)
    sources = sources_from(paths, args.ledger is not None)
    units = make_units(sources, args.group)
    budget = None if args.lanes is not None else (args.max_bytes or DEFAULT_MAX_BYTES)
    lanes, sizes = assign(sources, units, args.lanes, budget)
    for number, (lane, size) in enumerate(zip(lanes, sizes), 1):
        print("L%d: %d%s" % (number, size, " " + " ".join(shlex.quote(str(p)) for p in lane) if lane else ""))
    print("controls: sources %d assigned exactly once · duplicate caught · omission caught · clean assignment passed"
          % len(sources))
    print("lanes %d · sources %d · largest lane %d · mean %.2f"
          % (len(lanes), len(sources), max(sizes), sum(sizes) / len(lanes)))


if __name__ == "__main__":
    main()
