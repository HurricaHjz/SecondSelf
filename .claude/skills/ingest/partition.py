#!/usr/bin/env python3
"""Print a disjoint, size-ruled assignment of converted sources to helpers; read only.

--inbox reads every direct *.md file, including native Markdown; neighbouring
originals are not counted again. --ledger reads exactly one run_open inbox list
(path strings or objects with a file field), validates each listed file and uses
its same-stem .md conversion. A listed original and its Markdown are one source;
repeated paths, aliases of a source, or multiple originals for one source fail.
Ledger paths beginning raw/ are vault-relative; bare names are relative to raw/.
Other relative paths are vault-relative. --vault defaults to the installed
script's vault root, three directories above its directory.

Groups contain one exact stem per line, separated by blank lines. Each group is
indivisible. A unit is one source or one group, sized in converted bytes.

The size rule. PACK, the packing budget, is --max-bytes. CEILING, the most one
helper may hold, is share x window x bytes per token rounded down to whole bytes:
--ceiling-share in (0, 1], --window-tokens (the compile model's context window)
and 4 bytes per token; 800000 bytes with the defaults. No helper holds more than
CEILING, so the effective budget is min(PACK, CEILING). Units at or below it are
packed largest first, each into the first helper it fits (equal sizes in path
order); a unit above it and at or below CEILING gets a helper of its own and is
never refused. A source above CEILING is not assigned: a split: line names it,
its bytes and the ceiling with its derivation. A group above CEILING is not
assigned: a group-over-ceiling: line names every member and the total. The
script never splits a source or a group. The plan header prints PACK, CEILING
with its derivation, and the effective budget.

--lanes prints exactly N helpers, empty ones included, with PACK at its default:
units above the effective budget take one each and the rest go largest first to
the least-loaded remaining helper (ties use path order, then helper number). It
fails only when a helper would exceed the effective budget, printing a lower
bound and first fit's helper count as an upper bound, never as the needed count.

Paths in lane, split: and group-over-ceiling: lines use shell quoting, so spaces
and apostrophes round-trip; text after an unquoted # is commentary. The footer
follows a controls line proving every source placed exactly once (in one helper
or one reported line) and a planted duplicate and omission rejected by the same
assertion. Exit 0 prints a full plan; exit 3 prints a plan with one or more
split: or group-over-ceiling: lines, every other unit still planned; exit 2
prints PROBE FAILED for an invalid argument, unreadable input, empty inbox,
malformed ledger, duplicate source, unknown/ambiguous group stem, a --lanes
count the rule cannot meet, or a broken control.
Creates, modifies, moves and deletes nothing. Standard library only; no network.
"""

import argparse
from collections import Counter
from decimal import Decimal, localcontext
from fractions import Fraction
import json
import math
from pathlib import Path
import shlex
import sys

# PACK; set by judgement, unmeasured: small sources share one helper's fixed cost (lane core, slices, brief).
DEFAULT_MAX_BYTES = 250000
# The compile model's context window in tokens: the figure the harness reports for opus 5.5.
DEFAULT_WINDOW_TOKENS = 1000000
# Set by judgement, unmeasured: a helper also holds the lane core, its slices, the pages it writes and its
# checks, so it keeps a reserve as the context belt does.
DEFAULT_CEILING_SHARE = "0.2"
BYTES_PER_TOKEN = 4  # set by judgement, unmeasured, for English prose and Markdown
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


def ceiling_share(value):
    try:
        share = Fraction(value)
    except (ValueError, ZeroDivisionError):
        raise argparse.ArgumentTypeError("expected a ceiling share in (0, 1]")
    if not 0 < share <= 1:
        raise argparse.ArgumentTypeError("expected a ceiling share in (0, 1]")
    return share


def share_text(share):
    """The exact share as a plain decimal where it terminates, else as p/q."""
    denominator = share.denominator
    for factor in (2, 5):
        while denominator % factor == 0:
            denominator //= factor
    if denominator != 1:
        return "%d/%d" % (share.numerator, share.denominator)
    with localcontext() as ctx:
        # p / (2^a 5^b) needs at most digits(p) + digits(5^max(a,b)) significant digits, and
        # digits(5^max(a,b)) <= 3 * digits(denominator), so this precision makes the division exact
        ctx.prec = len(str(share.numerator)) + 4 * len(str(share.denominator)) + 2
        return format(Decimal(share.numerator) / Decimal(share.denominator), "f")


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
    """Every unit, largest first with ties in path order, and the set of units that are groups."""
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
    units, grouped, assigned = [], set(), set()
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
        grouped.add(units[-1])
    units.extend((path,) for path in sources if path not in assigned)
    return sorted(units, key=lambda unit: (-sum(sources[p] for p in unit), unit)), grouped


def coverage_problem(expected, lanes):
    counts = Counter(path for lane in lanes for path in lane)
    if set(counts) != set(expected) or any(count != 1 for count in counts.values()):
        return "disjointness assertion failed: every source must occur exactly once"
    return None


def first_fit(sources, units, budget):
    """Largest first, each unit into the first helper it fits; a unit above the budget opens its own."""
    lanes, sizes = [], []
    for unit in units:
        size = sum(sources[path] for path in unit)
        for index, load in enumerate(sizes):
            if load + size <= budget:
                break
        else:
            lanes.append([])
            sizes.append(0)
            index = len(lanes) - 1
        lanes[index].extend(unit)
        sizes[index] += size
    return lanes, sizes


def by_count(sources, units, count, budget):
    """Exactly count helpers: units above the budget alone, the rest to the least-loaded other helper."""
    unit_sizes = [sum(sources[path] for path in unit) for unit in units]
    alone = [index for index, size in enumerate(unit_sizes) if size > budget]
    shared = [index for index, size in enumerate(unit_sizes) if size <= budget]
    rest = sum(unit_sizes[index] for index in shared)
    lower = len(alone) + ((max(1, -(-rest // budget)) if budget else 1) if shared else 0)
    upper = len(first_fit(sources, units, budget)[0])
    bounds = ("at least %d helpers are needed (a lower bound); first fit plans %d "
              "(an upper bound, not the needed count)" % (lower, upper))
    if len(alone) > count or (shared and len(alone) == count):
        fail("--lanes %d cannot meet the effective budget of %d bytes: %d unit(s) above it need a "
             "helper each%s; %s" % (count, budget, len(alone),
                                    " and %d more unit(s) need another" % len(shared) if shared else "",
                                    bounds))
    lanes = [list(units[index]) for index in alone] + [[] for _ in range(count - len(alone))]
    sizes = [unit_sizes[index] for index in alone] + [0] * (count - len(alone))
    for index in shared:
        lightest = min(range(len(alone), count), key=lambda lane: (sizes[lane], lane))
        if sizes[lightest] + unit_sizes[index] > budget:
            fail("--lanes %d cannot meet the effective budget of %d bytes: the balanced assignment "
                 "would put %d bytes in one helper; %s"
                 % (count, budget, sizes[lightest] + unit_sizes[index], bounds))
        lanes[lightest].extend(units[index])
        sizes[lightest] += unit_sizes[index]
    return lanes, sizes


def quoted(paths):
    return " ".join(shlex.quote(str(path)) for path in paths)


def main(argv=None):
    parser = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--inbox", type=Path, help="raw root: direct *.md files only")
    source.add_argument("--ledger", type=Path, help="JSONL run ledger: the run_open inbox list")
    sizing = parser.add_mutually_exclusive_group()
    sizing.add_argument("--lanes", type=positive_integer,
                        help="exact number of helpers; PACK stays at its default")
    sizing.add_argument("--max-bytes", type=positive_integer,
                        help="PACK, the packing budget: converted bytes small units may share in one helper "
                             "(default 250000; set by judgement, unmeasured)")
    parser.add_argument("--window-tokens", type=positive_integer,
                        help="the compile model's context window in tokens (default 1000000, the figure the "
                             "harness reports for opus 5.5)")
    parser.add_argument("--ceiling-share", type=ceiling_share,
                        help="share of that window one helper may hold, in (0, 1] "
                             "(default 0.2; set by judgement, unmeasured)")
    parser.add_argument("--group", type=Path, help="stems, one per line; blank lines separate groups")
    parser.add_argument("--vault", type=Path, default=VAULT_DEFAULT,
                        help="base for relative ledger paths (default: installed script's vault)")
    args = parser.parse_args(argv)
    pack = args.max_bytes or DEFAULT_MAX_BYTES
    window = args.window_tokens or DEFAULT_WINDOW_TOKENS
    share = args.ceiling_share if args.ceiling_share is not None else ceiling_share(DEFAULT_CEILING_SHARE)
    ceiling = math.floor(share * window * BYTES_PER_TOKEN)  # exact rational arithmetic, rounded down
    budget = min(pack, ceiling)
    derivation = "share %s × window %d tokens × %d bytes per token" % (share_text(share), window, BYTES_PER_TOKEN)
    if args.inbox is not None:
        try:
            paths = sorted(p.absolute() for p in args.inbox.iterdir() if p.suffix == ".md" and not p.is_dir())
        except OSError as error:
            fail("unreadable inbox %s (%s)" % (args.inbox, error))
    else:
        paths = ledger_paths(args.ledger, args.vault)
    sources = sources_from(paths, args.ledger is not None)
    units, grouped = make_units(sources, args.group)
    planned, splits, over = [], [], []
    for unit in units:
        if sum(sources[path] for path in unit) <= ceiling:
            planned.append(unit)
        else:
            (over if unit in grouped else splits).append(unit)
    if args.lanes is not None:
        lanes, sizes = by_count(sources, planned, args.lanes, budget)
    else:
        lanes, sizes = first_fit(sources, planned, budget)
    problem = coverage_problem(sources, lanes + splits + over)
    if problem:
        fail(problem)
    control = next(iter(sources))
    if (coverage_problem([control], [(control,)]) is not None
            or coverage_problem([control], [(control, control)]) is None
            or coverage_problem([control], [()]) is None):
        fail("coverage control did not reject a duplicate and an omission and accept a clean assignment")
    print("pack: %d bytes (--max-bytes; default %d, set by judgement, unmeasured)" % (pack, DEFAULT_MAX_BYTES))
    print("ceiling: %d bytes = %s, rounded down (share: --ceiling-share, default %s, set by judgement, unmeasured; "
          "window: --window-tokens, the compile model's context window, default %d; bytes per token: set by "
          "judgement, unmeasured)" % (ceiling, derivation, DEFAULT_CEILING_SHARE, DEFAULT_WINDOW_TOKENS))
    print("budget: %d bytes = min(pack %d, ceiling %d); a unit above it gets a helper of its own, "
          "a unit above the ceiling is reported" % (budget, pack, ceiling))
    for number, (lane, size) in enumerate(zip(lanes, sizes), 1):
        print("L%d: %d%s" % (number, size, " " + quoted(lane) if lane else ""))
    for unit in splits:
        size = sources[unit[0]]
        print("split: %d %s  # stem %s · %d bytes above the ceiling of %d bytes (%s) · not compiled this run; "
              "kept in the inbox until a parts procedure exists" % (size, quoted(unit), unit[0].stem, size, ceiling,
                                                                     derivation))
    for unit in over:
        total = sum(sources[path] for path in unit)
        print("group-over-ceiling: %d %s  # members %d: %s · %d bytes above the ceiling of %d bytes (%s) · not "
              "planned and never split; give the group a larger-window model or release the grouping, with the "
              "reason recorded" % (total, quoted(unit), len(unit),
                                   " · ".join("%s %d" % (path.stem, sources[path]) for path in unit),
                                   total, ceiling, derivation))
    reported = sum(len(unit) for unit in splits + over)
    print("controls: sources %d assigned exactly once%s · duplicate caught · omission caught · clean assignment passed"
          % (len(sources) - reported, " · sources %d reported exactly once, none also assigned" % reported
             if reported else ""))
    print("lanes %d · sources %d · largest lane %d · mean %.2f%s"
          % (len(lanes), len(sources), max(sizes, default=0), sum(sizes) / len(lanes) if lanes else 0,
             " · split %d · group-over-ceiling %d (members %d)"
             % (len(splits), len(over), sum(len(unit) for unit in over)) if reported else ""))
    if reported:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
