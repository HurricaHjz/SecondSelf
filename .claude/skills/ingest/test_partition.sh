#!/bin/sh
# Every fixture lives beneath mktemp and is removed, including after a failed leg.
# Usage: sh test_partition.sh [path/to/partition.py]
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
PARTITION_SCRIPT=${1:-"$HERE/partition.py"}
PARTITION_FIXTURE=$(mktemp -d "${TMPDIR:-/tmp}/partition-suite.XXXXXX") || exit 2
trap 'chmod -R u+w "$PARTITION_FIXTURE"; rm -rf "$PARTITION_FIXTURE"' EXIT HUP INT TERM
"${PYTHON:-python3}" -B - "$PARTITION_SCRIPT" "$PARTITION_FIXTURE" "$HERE" <<'PARTITION_SUITE_PY'
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
script, root, here = map(lambda p: Path(p).resolve(), sys.argv[1:])
passed = failed = 0


def check(leg, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print("ok   %s" % leg)
    else:
        failed += 1
        print("FAIL %s: %s" % (leg, detail))


def run(*args, helper=script):
    return subprocess.run([sys.executable, str(helper), *map(str, args)],
                          capture_output=True, text=True)


def rejects(leg, args, message):
    result = run(*args)
    check(leg, result.returncode == 2 and result.stdout.startswith("PROBE FAILED: ")
          and message in result.stdout and not result.stderr, result.stdout + result.stderr)


def assignment(result):
    return [(int(tokens[1]), tokens[2:]) for line in result.stdout.splitlines()
            if re.match(r"L\d+:", line) for tokens in [shlex.split(line)]]


def manifest(directory):
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob("*") if path.is_file()}


def ledger(name, items):
    path = root / name
    path.write_text(json.dumps({"event": "run_open", "inbox": items}) + "\n")
    return path


raw = root / "raw"
raw.mkdir()
# Thirteen descending sizes exercise the design's four-lane, 20% acceptance bound.
sizes = list(range(100, 230, 10))
for i, size in enumerate(sizes):
    (raw / ("source-%02d.md" % i)).write_bytes(b"x" * size)
(raw / "source-00.pdf").write_bytes(b"original")
(raw / "orphan.bin").write_bytes(b"binary")
(raw / "nested").mkdir()
(raw / "nested" / "ignored.md").write_bytes(b"nested")
files = sorted(raw.glob("*.md"))
result = run("--inbox", raw, "--lanes", 4)
lanes = assignment(result)
flat = [p for _size, paths in lanes for p in paths]
check("P01 thirteen sources, four lanes, exact coverage", result.returncode == 0
      and len(lanes) == 4 and len(flat) == len(set(flat)) == 13
      and set(flat) == set(map(str, files)), result.stdout + result.stderr)
mean = sum(sizes) / 4
check("P02 lane sizes within 20% of mean (design acceptance bound)",
      bool(lanes) and all(abs(size - mean) <= mean * 0.20 for size, _paths in lanes), result.stdout)
check("P03 native Markdown counted; originals and nested files excluded",
      sum(size for size, _paths in lanes) == sum(sizes), result.stdout)
check("P04 exact byte counts and footer", all(size == sum(Path(p).stat().st_size for p in paths)
      for size, paths in lanes) and result.stdout.splitlines()[-1]
      == "lanes 4 · sources 13 · largest lane %d · mean %.2f" % (max(s for s, _p in lanes), mean))
check("P05 zero duplicates with same-run planted controls", "assigned exactly once · duplicate caught · omission caught · clean assignment passed" in result.stdout)
check("P06 deterministic assignment", run("--inbox", raw, "--lanes", 4).stdout == result.stdout)
budget = run("--inbox", raw, "--max-bytes", 500)
check("P07 byte budget obeyed with exact coverage", budget.returncode == 0
      and all(size <= 500 for size, _paths in assignment(budget))
      and sorted(p for _s, ps in assignment(budget) for p in ps) == sorted(flat), budget.stdout)
default = run("--inbox", raw)
check("P08 default budget matches explicit 250000", default.returncode == 0
      and default.stdout == run("--inbox", raw, "--max-bytes", 250000).stdout)
group = root / "groups.txt"
group.write_text("source-00\nsource-12\n\nsource-02\nsource-07\n")
grouped = run("--inbox", raw, "--lanes", 4, "--group", group)
group_sets = [set(Path(p).stem for p in ps) for _s, ps in assignment(grouped)]
check("P09 groups move whole; ungrouped sources remain", grouped.returncode == 0
      and any({"source-00", "source-12"} <= g for g in group_sets)
      and any({"source-02", "source-07"} <= g for g in group_sets)
      and sum(map(len, group_sets)) == 13, grouped.stdout)
entry = ledger("paths.jsonl", [str(p) for p in files])
check("P10 ledger path strings use measured disk bytes", run("--ledger", entry, "--lanes", 4).stdout == result.stdout)
entry = ledger("objects.jsonl", [{"file": str(p), "bytes": -1} for p in files]
               + [{"file": str(raw / "source-00.pdf")}])
check("P11 ledger objects coalesce original plus Markdown", run("--ledger", entry, "--lanes", 4).stdout == result.stdout)
reverse = ledger("reverse.jsonl", [str(raw / "source-00.pdf"), *map(str, files)])
check("P12 pair order does not alter the assignment", run("--ledger", reverse, "--lanes", 4).stdout == result.stdout)
relative = ledger("relative.jsonl", ["raw/" + p.name if i % 2 else p.name for i, p in enumerate(files)])
check("P13 relative ledger paths resolve through --vault", run("--ledger", relative, "--vault", root, "--lanes", 4).stdout == result.stdout)
special = root / "special"
special.mkdir()
(special / "a & b's source.md").write_text("é")
quoted = run("--inbox", special, "--lanes", 1)
check("P14 quoted output round-trips spaces, ampersands and apostrophes; bytes not characters",
      assignment(quoted) == [(2, [str(special / "a & b's source.md")])], quoted.stdout)
(special / "empty.md").touch()
empty_source = run("--inbox", special, "--lanes", 4)
check("P15 zero-byte source and empty lanes retain exact coverage controls", empty_source.returncode == 0
      and len(assignment(empty_source)) == 4 and "sources 2" in empty_source.stdout
      and "duplicate caught" in empty_source.stdout)
rejects("P16 duplicate ledger source", ["--ledger", ledger("duplicate.jsonl", [str(files[0])] * 2)], "source seen twice")
empty = root / "empty"
empty.mkdir()
rejects("P17 empty inbox", ["--inbox", empty], "empty inbox")
rejects("P18 missing inbox", ["--inbox", root / "absent"], "unreadable inbox")
rejects("P19 missing ledger file", ["--ledger", root / "absent.jsonl"], "unreadable ledger")
rejects("P20 missing listed source", ["--ledger", ledger("missing.jsonl", [str(raw / "absent.md")])], "missing file")
rejects("P21 missing conversion", ["--ledger", ledger("binary.jsonl", [str(raw / "orphan.bin")])], "missing file")
group.write_text("unknown\n")
rejects("P22 unknown grouped stem", ["--inbox", raw, "--group", group], "unknown stem")
group.write_text("source-00\n\nsource-00\n")
rejects("P23 duplicate grouped stem", ["--inbox", raw, "--group", group], "source seen twice")
rejects("P24 missing group file", ["--inbox", raw, "--group", root / "absent.txt"], "unreadable group file")
group.write_text("")
rejects("P25 empty group file", ["--inbox", raw, "--group", group], "empty group file")
rejects("P26 incompatible sizing flags", ["--inbox", raw, "--lanes", 4, "--max-bytes", 500], "not allowed")
for leg, flag, value in [("P27", "--lanes", "0"), ("P28", "--max-bytes", "-1"), ("P29", "--lanes", "four")]:
    rejects(leg + " invalid size", ["--inbox", raw, flag, value], "positive integer")
rejects("P30 no source selector", [], "required")
rejects("P31 two source selectors", ["--inbox", raw, "--ledger", entry], "not allowed")
# P32 and P33 updated by the size rule: a unit above the packing budget is the defect closed (it was
# refused); it now gets a helper of its own, never refused, and the plan exits 0.
above = run("--inbox", raw, "--max-bytes", 100)
check("P32 sources above the packing budget each get a helper of their own, never refused", above.returncode == 0
      and sorted((n, ps) for n, ps in assignment(above) if n > 100) == sorted(
          (Path(p).stat().st_size, [p]) for p in map(str, files) if Path(p).stat().st_size > 100)
      and "PROBE FAILED" not in above.stdout, above.stdout)
group.write_text("source-00\nsource-12\n")
grouped_above = run("--inbox", raw, "--max-bytes", 300, "--group", group)
check("P33 a group above the packing budget gets a helper of its own, whole", grouped_above.returncode == 0
      and (320, [str(raw / "source-00.md"), str(raw / "source-12.md")]) in assignment(grouped_above)
      and all(n <= 300 for n, ps in assignment(grouped_above)
              if ps != [str(raw / "source-00.md"), str(raw / "source-12.md")]), grouped_above.stdout)
for leg, text, message in [
        ("P34", "", "exactly one run_open"),
        ("P35", "not JSON\n", "malformed ledger"),
        ("P36", "[]\n", "not an object"),
        ("P37", '{"event":"run_open","inbox":{}}\n', "must be a list"),
        ("P38", '{"event":"run_open","inbox":[]}\n', "empty inbox"),
        ("P39", '{"event":"run_open","inbox":[{}]}\n', "non-empty file path"),
        ("P40", '{"event":"run_open","inbox":[]}\n' * 2, "exactly one run_open")]:
    bad = root / "bad.jsonl"
    bad.write_text(text)
    rejects(leg + " invalid ledger premise", ["--ledger", bad], message)
alias = raw / "alias.md"
alias.symlink_to(files[0])
rejects("P41 source alias rejected", ["--inbox", raw], "source seen twice")
alias.unlink()
os.link(files[0], alias)
rejects("P42 hard-linked source rejected", ["--inbox", raw], "source seen twice")
alias.unlink()
alias.symlink_to(raw / "absent.md")
rejects("P43 broken source link rejected", ["--inbox", raw], "missing file")
alias.unlink()
(raw / "source-00.txt").write_text("second original")
rejects("P44 two originals for one Markdown source rejected", ["--ledger", ledger("originals.jsonl",
        [str(files[0]), str(raw / "source-00.pdf"), str(raw / "source-00.txt")])], "source seen twice")
other = root / "other"
other.mkdir()
(other / files[0].name).write_text("different source")
ambiguous = ledger("ambiguous.jsonl", [str(files[0]), str(other / files[0].name)])
rejects("P45 ambiguous group stem rejected", ["--ledger", ambiguous, "--group", group], "ambiguous stem")
help_result = run("--help")
check("P46 help states budget provenance and read-only contract", help_result.returncode == 0
      and "set by judgement, unmeasured" in " ".join(help_result.stdout.split()) and "read only" in help_result.stdout)
packing = root / "packing"
packing.mkdir()
for name in ["a", "b", "c"]:
    (packing / (name + ".md")).write_bytes(b"x" * 6)
packed = run("--inbox", packing, "--max-bytes", 10)
# P47 retitled: first fit replaced the byte-lower-bound start; the behaviour it guards is unchanged.
check("P47 an extra helper opens when whole sources cannot pack within the budget",
      packed.returncode == 0 and [n for n, _ps in assignment(packed)] == [6, 6, 6], packed.stdout)
zero = root / "zero"
zero.mkdir()
(zero / "zero.md").touch()
zero_result = run("--inbox", zero)
check("P48 an all-zero-byte inbox keeps one lane, its source and controls", zero_result.returncode == 0
      and "lanes 1 · sources 1 · largest lane 0 · mean 0.00" in zero_result.stdout
      and "duplicate caught" in zero_result.stdout)
oversized = root / "oversized"
oversized.mkdir()
(oversized / "large.md").write_bytes(b"x" * (250000 + 1))  # the default budget plus one byte
check("P49 explicit lane count permits sources above the default byte budget",
      run("--inbox", oversized, "--lanes", 1).returncode == 0)
linebreak = zero / "broken\nname.md"
linebreak.write_text("body")
rejects("P50 source path cannot break the one-line output", ["--inbox", zero], "line break")
linebreak.unlink()
bad.write_bytes(b"\xff")
rejects("P51 invalid ledger encoding", ["--ledger", bad], "unreadable ledger")
group.write_bytes(b"\xff")
rejects("P52 invalid group encoding", ["--inbox", raw, "--group", group], "unreadable group file")

# The size rule. PACK = 250000 and CEILING = 0.2 × 1000000 × 4 = 800000 bytes by default; each leg
# below fails on the partitioner that refused a unit above its budget.
def plan(result):
    """Helpers, split: lines and group-over-ceiling: lines of one run, paths unquoted."""
    reported = {"split": [], "group-over-ceiling": []}
    for line in result.stdout.splitlines():
        kind = line.split(":", 1)[0]
        if kind in reported:
            tokens = shlex.split(line, comments=True)
            reported[kind].append((int(tokens[1]), tokens[2:]))
    return assignment(result), reported["split"], reported["group-over-ceiling"]


def inbox(name, sizes):
    directory = root / name
    directory.mkdir()
    for stem, size in sizes.items():
        (directory / (stem + ".md")).write_bytes(b"x" * size)
    return directory


def md(directory, *stems):
    return [str(directory / (stem + ".md")) for stem in stems]


def line(result, prefix):
    return next((text for text in result.stdout.splitlines() if text.startswith(prefix)), "")


DERIVATION = "share 0.2 × window 1000000 tokens × 4 bytes per token"
d = inbox("n01", {"big": 300000, "s1": 1000, "s2": 2000, "s3": 3000})
r = run("--inbox", d)
check("N01 a 300000-byte source among small ones gets a helper of its own; exit 0, no refusal",
      r.returncode == 0 and plan(r) == ([(300000, md(d, "big")), (6000, md(d, "s3", "s2", "s1"))], [], []),
      r.stdout)
d = inbox("n02", {"f%d" % i: 60000 for i in range(5)})
r = run("--inbox", d)
check("N02 five sources of 60000 bytes pack as 240000 plus 60000, no helper above 250000",
      r.returncode == 0 and plan(r) == ([(240000, md(d, "f0", "f1", "f2", "f3")), (60000, md(d, "f4"))], [], []),
      r.stdout)
d = inbox("n03", {"big chapter's book": 900000, "a": 1000, "b": 2000})
r = run("--inbox", d)
split_line = line(r, "split: ")
check("N03 a 900000-byte source is reported by a split: line with the ceiling's derivation; the rest planned; exit 3",
      r.returncode == 3 and plan(r) == ([(3000, md(d, "b", "a"))], [(900000, md(d, "big chapter's book"))], [])
      and all(s in split_line for s in ["stem big chapter's book", "900000 bytes above the ceiling of 800000 bytes",
                                       DERIVATION, "not compiled this run; it stays in the inbox and is named in the run's report"])
      # N03 updated with the update count: the parts procedure is retired (known-issues, closed 2026-11-20),
      # so the line no longer promises one.
      and "split by chapter before compiling" not in split_line and "parts procedure" not in split_line
      and "controls: sources 2 assigned exactly once · sources 1 reported exactly once, none also assigned"
      " · duplicate caught · omission caught · clean assignment passed" in r.stdout
      and r.stdout.splitlines()[-1].endswith(" · split 1 · group-over-ceiling 0 (members 0)"), r.stdout)
r = run("--inbox", d, "--window-tokens", 2000000)
check("N04 the same source with --window-tokens 2000000 gets a helper of its own; exit 0 (the ceiling follows the window)",
      r.returncode == 0 and plan(r) == ([(900000, md(d, "big chapter's book")), (3000, md(d, "b", "a"))], [], [])
      and line(r, "ceiling: ").startswith("ceiling: 1600000 bytes = share 0.2 × window 2000000 tokens"), r.stdout)
d = inbox("n05", {"g1": 150000, "g2": 150000, "s": 1000})
grouping = root / "n05-groups.txt"
grouping.write_text("g1\ng2\n")
r = run("--inbox", d, "--group", grouping)
check("N05 a group above PACK gets a helper of its own, whole; exit 0",
      r.returncode == 0 and plan(r) == ([(300000, md(d, "g1", "g2")), (1000, md(d, "s"))], [], []), r.stdout)
d = inbox("n06", {"h1": 450000, "h2": 450000, "s": 1000})
grouping = root / "n06-groups.txt"
grouping.write_text("h1\nh2\n")
r = run("--inbox", d, "--group", grouping)
group_line = line(r, "group-over-ceiling: ")
loose = run("--inbox", d)
check("N06 a group above CEILING gets a group-over-ceiling: line naming every member and the total; not planned; exit 3",
      r.returncode == 3 and plan(r) == ([(1000, md(d, "s"))], [], [(900000, md(d, "h1", "h2"))])
      and all(s in group_line for s in ["members 2: h1 450000 · h2 450000", "900000 bytes above the ceiling of 800000",
                                       "never split", "larger-window model", "release the grouping"])
      and "split:" not in group_line and not any(t.startswith("split:") for t in r.stdout.splitlines())
      and loose.returncode == 0
      and plan(loose) == ([(450000, md(d, "h1")), (450000, md(d, "h2")), (1000, md(d, "s"))], [], []),
      r.stdout + loose.stdout)
d = inbox("n07", {"a": 260000, "b": 270000, "c": 280000})
r = run("--inbox", d, "--lanes", 2)
check("N07 --lanes 2 with three units above PACK fails, naming three as the needed lower bound",
      r.returncode == 2 and r.stdout.startswith("PROBE FAILED: --lanes 2 cannot meet the effective budget of 250000")
      and "3 unit(s) above it need a helper each" in r.stdout and "at least 3 helpers are needed" in r.stdout
      and "first fit plans 3 (an upper bound, not the needed count)" in r.stdout and not r.stderr, r.stdout)
review = {"p150": 150000, "p125": 125000, "p75": 75000, "q1": 50000, "q2": 50000, "q3": 50000}
d = inbox("n08", review)
two = run("--inbox", d, "--lanes", 2)
default_plan = run("--inbox", d)
check("N08 the review's fixture plans --lanes 2 as two helpers of 250000, where first fit uses three",
      two.returncode == 0 and [n for n, _ps in assignment(two)] == [250000, 250000]
      and sorted(p for _n, ps in assignment(two) for p in ps) == sorted(md(d, *review))
      and default_plan.returncode == 0 and [n for n, _ps in assignment(default_plan)] == [225000, 225000, 50000],
      two.stdout + default_plan.stdout)
one = run("--inbox", d, "--lanes", 1)
check("N09 --lanes 1 on that fixture fails with a lower bound of two and first fit's three as an upper bound",
      one.returncode == 2 and one.stdout.startswith("PROBE FAILED: ")
      and "the balanced assignment would put 275000 bytes in one helper" in one.stdout
      and "at least 2 helpers are needed (a lower bound); first fit plans 3 (an upper bound, not the needed count)"
      in one.stdout, one.stdout)
d = inbox("n10", {"a": 150000, "b": 100000})
equal = run("--inbox", d)
d2 = inbox("n10b", {"a": 150001, "b": 100000})
above = run("--inbox", d2)
d3 = inbox("n10c", {"p": 250000, "q": 10})
alone = run("--inbox", d3)
d4 = inbox("n10d", {"p": 250001, "q": 10})
over = run("--inbox", d4)
check("N10 PACK boundary: units totalling 250000 share; one byte above opens a helper; a unit of 250001 stands alone",
      [x.returncode for x in (equal, above, alone, over)] == [0, 0, 0, 0]
      and plan(equal)[0] == [(250000, md(d, "a", "b"))]
      and plan(above)[0] == [(150001, md(d2, "a")), (100000, md(d2, "b"))]
      and plan(alone)[0] == [(250000, md(d3, "p")), (10, md(d3, "q"))]
      and plan(over)[0] == [(250001, md(d4, "p")), (10, md(d4, "q"))],
      equal.stdout + above.stdout + alone.stdout + over.stdout)
d = inbox("n11", {"c": 800000})
at = run("--inbox", d)
d2 = inbox("n11b", {"c": 800001})
beyond = run("--inbox", d2)
check("N11 CEILING boundary: 800000 bytes gets a helper of its own (exit 0); 800001 bytes is a split: line (exit 3)",
      at.returncode == 0 and plan(at) == ([(800000, md(d, "c"))], [], [])
      and beyond.returncode == 3 and plan(beyond) == ([], [(800001, md(d2, "c"))], []), at.stdout + beyond.stdout)
d = inbox("n12", {"u1": 100000, "u2": 100000, "w": 160000})
small = run("--inbox", d, "--window-tokens", 200000)
d2 = inbox("n12b", {"w": 160001})
small_over = run("--inbox", d2, "--window-tokens", 200000)
check("N12 a smaller window: CEILING 160000 below PACK caps packing; 160000 alone; 160001 reported",
      small.returncode == 0 and line(small, "budget: ").startswith("budget: 160000 bytes = min(pack 250000, ceiling 160000)")
      and plan(small) == ([(160000, md(d, "w")), (100000, md(d, "u1")), (100000, md(d, "u2"))], [], [])
      and small_over.returncode == 3 and plan(small_over) == ([], [(160001, md(d2, "w"))], []),
      small.stdout + small_over.stdout)
d = inbox("n13", {"big": 900000, "s": 1000})
r = run("--inbox", d, "--max-bytes", 1000000)
check("N13 ceiling first: with --max-bytes 1000000 a 900000-byte unit is still reported, never packed",
      r.returncode == 3 and plan(r) == ([(1000, md(d, "s"))], [(900000, md(d, "big"))], [])
      and line(r, "budget: ").startswith("budget: 800000 bytes = min(pack 1000000, ceiling 800000)"), r.stdout)
for value in ["0", "-0.1", "1.5", "1.0000001", "abc", "nan", "inf", "1/0"]:
    rejects("N14 invalid ceiling share %s" % value, ["--inbox", d, "--ceiling-share", value],
            "argument --ceiling-share: expected a ceiling share in (0, 1]")
for value in ["0", "-5", "1.5", "big"]:
    rejects("N15 invalid window %s" % value, ["--inbox", d, "--window-tokens", value],
            "argument --window-tokens: expected a positive integer")
r = run("--inbox", d, "--ceiling-share", 1)
check("N16 share 1, the closed end of (0, 1], is accepted: CEILING 4000000 plans the 900000-byte unit",
      r.returncode == 0 and line(r, "ceiling: ").startswith("ceiling: 4000000 bytes = share 1 × window 1000000 tokens")
      and plan(r) == ([(900000, md(d, "big")), (1000, md(d, "s"))], [], []), r.stdout)
d = inbox("n17", {"fits": 116, "over": 117})
exact = run("--inbox", d, "--ceiling-share", "0.29", "--window-tokens", 100)
down = run("--inbox", d, "--ceiling-share", "0.3", "--window-tokens", 7)
check("N17 CEILING is exact and rounded down: 0.29 × 100 × 4 = 116 (floating point gives 115); 0.3 × 7 × 4 = 8.4 gives 8",
      exact.returncode == 3 and line(exact, "ceiling: ").startswith("ceiling: 116 bytes = share 0.29 × window 100 tokens")
      and plan(exact) == ([(116, md(d, "fits"))], [(117, md(d, "over"))], [])
      and down.returncode == 3 and line(down, "ceiling: ").startswith("ceiling: 8 bytes = share 0.3 × window 7 tokens")
      and len(plan(down)[1]) == 2, exact.stdout + down.stdout)
d = inbox("n18", {"a": 21, "b": 30})
every = run("--inbox", d, "--window-tokens", 25)
every_lanes = run("--inbox", d, "--window-tokens", 25, "--lanes", 2)
check("N18 every unit above CEILING: no helper, a split: line each, exit 3; --lanes 2 prints two empty helpers",
      every.returncode == 3 and plan(every) == ([], [(30, md(d, "b")), (21, md(d, "a"))], [])
      and "controls: sources 0 assigned exactly once · sources 2 reported exactly once" in every.stdout
      and every.stdout.splitlines()[-1] == "lanes 0 · sources 2 · largest lane 0 · mean 0.00 · split 2 · "
      "group-over-ceiling 0 (members 0)"
      and every_lanes.returncode == 3 and plan(every_lanes) == ([(0, []), (0, [])], [(30, md(d, "b")), (21, md(d, "a"))], []),
      every.stdout + every_lanes.stdout)
d = inbox("n19", {"big": 900000, "a": 1000, "b": 2000})
r = run("--inbox", d, "--lanes", 2)
check("N19 --lanes still reports a unit above CEILING and plans the rest; exit 3",
      r.returncode == 3 and plan(r) == ([(2000, md(d, "b")), (1000, md(d, "a"))], [(900000, md(d, "big"))], []), r.stdout)
r = run("--inbox", raw)
SHIPPED_BASIS = "set by judgement for English prose and Markdown, unmeasured on paper captures"
BASIS = SHIPPED_BASIS
check("N20 the plan header prints PACK, CEILING with its derivation, and the effective budget",
      r.returncode == 0 and r.stdout.splitlines()[:3] == [
          "pack: 250000 bytes (--max-bytes; default 250000, set by judgement, unmeasured)",
          "ceiling: 800000 bytes = " + DERIVATION + ", rounded down (share: --ceiling-share, default 0.2, set by "
          "judgement, unmeasured; window: --window-tokens, the compile model's context window, default 1000000; "
          "bytes per token: " + BASIS + ")",
          "budget: 250000 bytes = min(pack 250000, ceiling 800000); a unit above it gets a helper of its own, "
          "a unit above the ceiling is reported"], r.stdout)
# The export removes each vault-local block as whole comment-marker lines (export-template's strip): the program
# so stripped must still run, and its ceiling line must state the shipped figure with no vault's record.
STRIP = re.compile(r"^[ \t]*# +<!-- *vault-local:begin *-->[ \t]*\n.*?^[ \t]*# +<!-- *vault-local:end *-->[ \t]*(?:\n|$)",
                   re.S | re.M)
shipped = root / "n20-shipped-partition.py"
shipped.write_text(STRIP.sub("", script.read_text()))
s = run("--inbox", raw, helper=shipped)
check("N20 stripped of its vault-local blocks, as the export ships it, the program runs and its ceiling line states the shipped figure alone",
      s.returncode == 0 and line(s, "ceiling: ").endswith("; bytes per token: " + SHIPPED_BASIS + ")")
      and "known-issues" not in s.stdout and not s.stderr, s.stdout + s.stderr)
check("N21 help documents the ceiling flags, the split: and group-over-ceiling: lines and exit 3",
      all(s in " ".join(help_result.stdout.split()) for s in
          ["--window-tokens", "--ceiling-share", "in (0, 1]", "split: line", "group-over-ceiling: line",
           "exit 3 prints a plan", "min(PACK, CEILING)", "never splits a source or a group"]), help_result.stdout)

# The update count (known-issues 2026-11-20 06:29 d): an update compile also reads its earlier version and its
# existing page, so --update counts them in the unit's size; an update above the ceiling is planned alone at the
# alone share, and one above that waits. Each V leg fails on the partitioner that had no --update.
def earlier(name, sizes):
    """Earlier files outside the inbox: {stem: [bytes, ...]} -> {stem: [paths]}."""
    directory = root / (name + "-earlier")
    directory.mkdir()
    found = {}
    for stem, lengths in sizes.items():
        found[stem] = []
        for k, size in enumerate(lengths):
            path = directory / ("%s-%d.md" % (stem, k))
            path.write_bytes(b"y" * size)
            found[stem].append(path)
    return found


def update_file(name, entries, text=None):
    path = root / (name + "-updates.txt")
    path.write_text(text if text is not None else "".join(
        shlex.quote(stem) + " " + " ".join(shlex.quote(str(p)) for p in paths) + "\n" for stem, paths in entries.items()))
    return path


def alone_lines(result):
    return [(int(tokens[1]), tokens[2:]) for text in result.stdout.splitlines() if re.match(r"A\d+:", text)
            for tokens in [shlex.split(text, comments=True)]]


def reported(result, prefix):
    return [(int(tokens[1]), tokens[2:]) for text in result.stdout.splitlines() if text.startswith(prefix + ": ")
            for tokens in [shlex.split(text, comments=True)]]


d = inbox("v01", {"a": 100000, "b": 100000})
old = earlier("v01", {"a": [100000, 20000], "b": [100000, 20000]})
r = run("--inbox", d)
check("V01 control: without --update the two update sources pack as one helper of 200000 (the miscount)",
      r.returncode == 0 and plan(r) == ([(200000, md(d, "a", "b"))], [], []), r.stdout)
r = run("--inbox", d, "--update", update_file("v01", old))
check("V01 with --update each counts 220000 and the two take a helper each",
      r.returncode == 0 and plan(r) == ([(220000, md(d, "a")), (220000, md(d, "b"))], [], []), r.stdout)
d = inbox("v02", {"p%d" % i: 150000 for i in range(4)})
old = earlier("v02", {"p%d" % i: [140000, 15000] for i in range(4)})
r = run("--inbox", d, "--max-bytes", 800000, "--update", update_file("v02", old))
check("V02 the C-CAP-1 shape at --max-bytes 800000: four updates of 305000 counted plan as two helpers of 610000",
      r.returncode == 0 and [size for size, _ in plan(r)[0]] == [610000, 610000], r.stdout)
d = inbox("v03", {"big": 300000, "s": 1000})
old = earlier("v03", {"big": [300000, 250000]})
r = run("--inbox", d, "--update", update_file("v03", old))
a_line = line(r, "A1: ")
check("V03 an update counted at 850000 is planned alone (A1), not in a lane; exit 0; its comment gives the parts",
      r.returncode == 0 and alone_lines(r) == [(850000, md(d, "big"))] and plan(r) == ([(1000, md(d, "s"))], [], [])
      and all(s in a_line for s in ["update of big", "new 300000 + earlier 550000 bytes", "above the ceiling of 800000",
                                    "planned alone", "share 0.3 (limit 1200000 bytes)", "its verifier serves it alone"])
      and line(r, "alone: ").startswith("alone: 1200000 bytes = share 0.3 × window 1000000 tokens × 4 bytes per token")
      and "both versions in view" in line(r, "alone: ") and "lanes 1 · sources 2" in r.stdout and " · alone 1" in r.stdout, r.stdout)
r = run("--inbox", d)
check("V03 control: the same source without --update plans at 300000 in a helper of its own",
      r.returncode == 0 and plan(r)[0][0] == (300000, md(d, "big")) and not alone_lines(r), r.stdout)
d = inbox("v04", {"huge": 600000, "s": 1000})
old = earlier("v04", {"huge": [600000, 50000]})
r = run("--inbox", d, "--update", update_file("v04", old))
w_line = line(r, "wait: ")
check("V04 an update counted at 1250000, above the alone limit, waits: a wait: line, no lane or A line; exit 3",
      r.returncode == 3 and reported(r, "wait") == [(1250000, md(d, "huge"))] and not alone_lines(r)
      and plan(r) == ([(1000, md(d, "s"))], [], [])
      and all(s in w_line for s in ["update of huge", "new 600000 + earlier 650000 bytes", "above the alone limit of 1200000",
                                    "would not fit its helper's limit even alone", "name it in the run's report"])
      and " · wait 1" in r.stdout and "parts procedure" not in r.stdout, r.stdout)
r = run("--inbox", d, "--update", update_file("v04b", old), "--alone-share", "0.5")
check("V06 --alone-share 0.5 raises the limit to 2000000, so the same update is planned alone; exit 0",
      r.returncode == 0 and alone_lines(r) == [(1250000, md(d, "huge"))] and "limit 2000000 bytes" in r.stdout, r.stdout)
rejects("V06 an --alone-share equal to the ceiling share is refused", ["--inbox", d, "--alone-share", "0.2"],
        "--alone-share 0.2 must exceed the ceiling share 0.2")
rejects("V06 an --alone-share above 1 is refused", ["--inbox", d, "--alone-share", "1.5"], "ceiling share in (0, 1]")
r = run("--inbox", d, "--ceiling-share", "0.5")
check("V06 control: a ceiling share raised above the alone default is not refused (the alone default follows it)",
      r.returncode == 0, r.stdout)
d = inbox("v05", {"novel": 900000, "s": 1000})
r = run("--inbox", d)
check("V05 a new source above the ceiling: split:, it stays in the inbox, no parts procedure named; exit 3",
      r.returncode == 3 and "it stays in the inbox and is named in the run's report" in line(r, "split: ")
      and "parts procedure" not in r.stdout and not alone_lines(r), r.stdout)
d = inbox("v07", {"a": 100000, "b": 100000, "c": 5000})
old = earlier("v07", {"a": [100000, 20000], "b": [100000, 20000]})
r = run("--inbox", d)
check("V07 with no --update the header says none were named, after the three size lines",
      r.returncode == 0 and r.stdout.splitlines()[3] == "updates: none named (--update absent): every unit is sized by its "
      "own converted bytes, as a new compile" and not line(r, "alone: "), r.stdout)
r = run("--inbox", d, "--update", update_file("v07", old))
check("V07 with --update the header counts the sources and earlier files, and prints the alone: line",
      r.returncode == 0 and r.stdout.splitlines()[3] == "updates: 2 sources sized with 4 earlier files (+240000 bytes) from --update"
      and r.stdout.splitlines()[4].startswith("alone: 1200000 bytes"), r.stdout)
check("V09 accounting: the printed sizes sum to the source bytes plus the earlier files the fixture wrote",
      sum(size for size, _ in plan(r)[0]) == 205000 + 240000, r.stdout)
# The controls clause "sizes add up" compared the plan's count with itself (review advice A6): it is gone, and
# V09 above is the sum check, made from the fixture's own byte counts.
check("V14 the controls line makes no size-accounting claim; the sum is V09's, made from the fixture's byte counts",
      r.returncode == 0 and line(r, "controls: ") and "sizes add up" not in r.stdout and "earlier-file bytes counted" not in r.stdout,
      r.stdout)
r0 = run("--inbox", d)
check("V09 control: the same sum over the plan that leaves the earlier files out does not add up",
      r0.returncode == 0 and sum(size for size, _ in plan(r0)[0]) == 205000 != 205000 + 240000, r0.stdout)
# Premise failures of --update: each exits 2 with PROBE FAILED and prints no plan.
d = inbox("v08", {"a": 1000, "b": 1000})
old = earlier("v08", {"a": [500]})
unreadable = root / "v08-unreadable.md"; unreadable.write_text("z"); unreadable.chmod(0)
cases = [("a missing earlier file", "a " + shlex.quote(str(root / "v08-absent.md")) + "\n", "missing file or not a regular file"),
         ("a directory named as an earlier file", "a " + shlex.quote(str(root)) + "\n", "missing file or not a regular file"),
         ("an unreadable earlier file", "a " + shlex.quote(str(unreadable)) + "\n", "unreadable file"),
         ("an empty --update file", "", "empty --update file"),
         ("a comments-only --update file", "# none\n\n", "empty --update file"),
         ("a stem with no earlier file", "a\n", "names a and no earlier file"),
         ("an unknown stem", "zz " + shlex.quote(str(old["a"][0])) + "\n", "--update names unknown stem: zz"),
         ("a stem on two lines", ("a " + shlex.quote(str(old["a"][0])) + "\n") * 2, "--update names stem a on two lines"),
         ("an earlier file that is an inbox source", "a " + shlex.quote(str(d / "b.md")) + "\n", "is one of this run's inbox sources"),
         ("an unbalanced quote", "a '" + str(old["a"][0]) + "\n", "--update line 1 does not parse")]
for n, (label, text, message) in enumerate(cases):
    rejects("V08 --update refuses " + label, ["--inbox", d, "--update", update_file("v08-%d" % n, {}, text)], message)
rejects("V08 an unreadable --update file is refused", ["--inbox", d, "--update", root / "v08-no-such-updates.txt"],
        "unreadable --update file")
unreadable.chmod(0o644)
amb = root / "v08amb"; (amb / "raw" / "x").mkdir(parents=True); (amb / "raw" / "y").mkdir(parents=True)
(amb / "raw" / "x" / "same.md").write_text("one"); (amb / "raw" / "y" / "same.md").write_text("two")
(amb / "led.jsonl").write_text(json.dumps({"event": "run_open", "inbox": ["raw/x/same.md", "raw/y/same.md"]}) + "\n")
rejects("V08 an ambiguous stem (two inbox sources named same) is refused",
        ["--ledger", amb / "led.jsonl", "--vault", amb, "--update", update_file("v08amb", {}, "same " + shlex.quote(str(old["a"][0])) + "\n")],
        "--update names ambiguous stem: same")
d = inbox("v10", {"a": 300000, "b": 100000, "c": 100000})
old = earlier("v10", {"b": [100000]})
r = run("--inbox", d, "--lanes", 3, "--update", update_file("v10", old))
check("V10 --lanes 3 keeps the exact count with the earlier file counted: 300000 alone, then 200000 and 100000",
      r.returncode == 0 and plan(r) == ([(300000, md(d, "a")), (200000, md(d, "b")), (100000, md(d, "c"))], [], []), r.stdout)
r = run("--inbox", d, "--lanes", 2, "--update", update_file("v10b", old))
check("V10 --lanes 2 on that load fails with the bounds message (b and c share 300000, above the budget)",
      r.returncode == 2 and "a lower bound" in r.stdout and "300000 bytes in one helper" in r.stdout, r.stdout)
d = inbox("v10c", {"big": 300000, "s": 1000})
old = earlier("v10c", {"big": [300000, 250000]})
r = run("--inbox", d, "--lanes", 2, "--update", update_file("v10c", old))
check("V10 an alone unit stays outside the --lanes count: two lanes printed, one of them empty, and A1",
      r.returncode == 0 and len(plan(r)[0]) == 2 and alone_lines(r) == [(850000, md(d, "big"))], r.stdout)
d = inbox("v11", {"g1": 300000, "g2": 300000})
old = earlier("v11", {"g1": [300000]})
groups = root / "v11-groups.txt"; groups.write_text("g1\ng2\n")
r = run("--inbox", d, "--group", groups, "--update", update_file("v11", old))
check("V11 a group whose member has an update counts it, and over the ceiling prints group-over-ceiling:, never A or wait:; exit 3",
      r.returncode == 3 and plan(r)[2] == [(900000, md(d, "g1", "g2"))] and not alone_lines(r) and not line(r, "wait: ")
      and "g1 600000" in line(r, "group-over-ceiling: "), r.stdout)
lv = root / "v12vault"; (lv / "raw" / "2-papers").mkdir(parents=True); (lv / "wiki" / "sources").mkdir(parents=True)
(lv / "raw" / "x.md").write_bytes(b"n" * 100000)
(lv / "raw" / "2-papers" / "x-v1.md").write_bytes(b"o" * 90000); (lv / "wiki" / "sources" / "x.md").write_bytes(b"p" * 10000)
(lv / "led.jsonl").write_text(json.dumps({"event": "run_open", "inbox": ["x.md"]}) + "\n")
r = run("--ledger", lv / "led.jsonl", "--vault", lv, "--update", update_file("v12", {}, "x raw/2-papers/x-v1.md wiki/sources/x.md\n"))
check("V12 ledger mode reads --update paths relative to --vault and counts them",
      r.returncode == 0 and plan(r)[0] == [(200000, [str(lv / "raw" / "x.md")])]
      and "update: x +100000 " + str(lv / "raw" / "2-papers" / "x-v1.md") + " " + str(lv / "wiki" / "sources" / "x.md") in r.stdout, r.stdout)
d = inbox("v13", {"a": 100000, "b": 100000})
shared_page = root / "v13-shared-page.md"; shared_page.write_bytes(b"q" * 30000)
r = run("--inbox", d, "--update", update_file("v13", {"a": [shared_page], "b": [shared_page]}))
check("V13 an earlier file named for two units is counted in each, and both update: lines name it",
      r.returncode == 0 and sorted(size for size, _ in plan(r)[0]) == [130000, 130000]
      and r.stdout.count(str(shared_page)) == 2, r.stdout)
r = run("--inbox", d, "--update", update_file("v13b", {"a": [shared_page, shared_page]}))
check("V13 a file named twice within one unit counts once (a 130000 packs with b 100000)",
      r.returncode == 0 and "update: a +30000 " in r.stdout and plan(r)[0] == [(230000, md(d, "a", "b"))]
      and "1 sources sized with 1 earlier files (+30000 bytes)" in r.stdout, r.stdout)
# The updates: header counts as the plan counts (review advice A7): a file shared by two members of one group
# counts once in that unit, and a file named for two separate units counts in each.
d = inbox("v15", {"g1": 100000, "g2": 100000})
v15_groups = root / "v15-groups.txt"; v15_groups.write_text("g1\ng2\n")
v15_page = root / "v15-shared-page.md"; v15_page.write_bytes(b"q" * 30000)
r = run("--inbox", d, "--group", v15_groups, "--update", update_file("v15", {"g1": [v15_page], "g2": [v15_page]}))
check("V15 a file shared by two members of one group: the header counts it once (+30000), as the group's size does",
      r.returncode == 0 and plan(r)[0] == [(230000, md(d, "g1", "g2"))]
      and line(r, "updates: ") == "updates: 2 sources sized with 1 earlier files (+30000 bytes) from --update", r.stdout)
r = run("--inbox", d, "--update", update_file("v15b", {"g1": [v15_page], "g2": [v15_page]}))
check("V15 control: the same file named for two separate units counts in each, in the header (+60000) and the plan",
      r.returncode == 0 and sum(size for size, _ in plan(r)[0]) == 260000
      and line(r, "updates: ") == "updates: 2 sources sized with 2 earlier files (+60000 bytes) from --update", r.stdout)

# Enable part 8 checks when its independent text diff is installed.
if os.environ.get("INGEST_TEXT_CHECKS") == "1":
    # Text controls are tested beside the installed helper, without needing a stage twin.
    skill = (here / "SKILL.md").read_text()
    pacing = skill.split("## Pacing", 1)[1].split("## ", 1)[0]
    parallel = skill.split("## Parallel mode", 1)[1].split("\n1.", 1)[0]
    # INGEST_DELEGATE_TEMPLATES names the templates directory where a staged copy has none beside it.
    templates = Path(os.environ.get("INGEST_DELEGATE_TEMPLATES") or here.parent / "delegate" / "templates")
    template = (templates / "brief-compile.md").read_text()
    check("T01 retired count trigger absent; one-lane control present", not re.search("≥6 independent sources|≤5 stays|≲5 files", pacing + parallel)
          and "one-lane" in pacing and "source-size" in pacing)
    # T02 updated by the size rule: the budget's figure and label moved to the one statement in Partition
    # (T09), so Pacing must point there instead of restating them.
    check("T02 one-lane budget pointer (the effective budget min(PACK, CEILING) in both Pacing copies), serial batch and verify path present", all(s in pacing for s in
          ["effective packing budget", "**Parallel mode**, step 1 (Partition)", "serially", "Step 7", "Verify step", "Routing", "no claims", "no merge", "no conflict lane"])
          and pacing.count("min(`PACK`, `CEILING`)") >= 2 and "budget is the packing budget `PACK`" not in pacing
          and "250000" not in pacing)
    check("T03 spawner slot covers one-lane shared writes, sorting and verification", all(s in template.split("<!-- Spawner:", 1)[1]
          for s in ["one-lane", "serially", "shared pages", "index lines", "log entry", "Step 7", "one verify lane"]))
    check("T04 partition step names the script assertion", "partition.py" in skill and "the script asserts" in skill)
    # T05 to T08 pin the ingest batch rule as Guided judgement: a lane by default, a small batch in the
    # head with its reason recorded, the Verify step on either unless the pre-flight says why not.
    precedence = ('**Execution precedence:** a batch compiles in a lane by default; the owner’s word, else the head’s pre-flight judgement, chooses the one-lane or parallel shape. The head may compile a small batch itself where the instrument rule favours it, as for a few short sources that fit its context with room to spare; the pre-flight records that reason, and the owner’s word on a batch’s shape holds over either default. The **Verify step** runs on a batch the head compiles as it does on a lane’s, unless that batch’s pre-flight records why it need not.')
    def precedence_probe(body):
        return subprocess.run(["grep", "-F", "-x", "--", precedence], input=body,
                              capture_output=True, text=True)
    present = precedence_probe(pacing)
    check("T05 F2 execution precedence sentence found by exact grep", present.returncode == 0
          and present.stdout == precedence + "\n" and not present.stderr)
    removed = precedence_probe(pacing.replace(precedence + "\n", ""))
    check("T06 F2 removed precedence sentence fails the same probe", removed.returncode == 1
          and not removed.stdout and not removed.stderr and present.returncode == 0)
    counter_case = ("A two-source batch compiled in a lane under `single` uses `one-lane` where the bytes the size rule counts fit the source budget, "
                    "with its standing instrument-rule reason recorded in the pre-flight; the owner’s word or the head’s "
                    "pre-flight judgement can select `parallel`. The same batch under `multi` follows the same shape rule.")
    check("T07 F2 single, multi and explicit-owner counter-cases are settled", counter_case in pacing
          and "The head may compile a small batch itself" in pacing
          and "registries where the ingest exception is not granted" in pacing)
    def retired_in(text):
        return [s for s in ("every batch compiles in a lane", "very batch compiles in a lane", "no head-compile exception",
                            "does not get by default", "compiled in lanes, with the run pausing") if s in text]
    heading = re.search(r"(?m)^## Verify step \(.*$", skill)
    check("T07a Approve 5's restatements follow it: the old statements are gone, and the Verify step's heading covers a batch the head compiled",
          not retired_in(skill + template) and heading is not None and "a batch the head compiled" in heading.group(0)
          and "unless that batch's pre-flight records why it need not" in heading.group(0), str(retired_in(skill + template)))
    check("T07b control: the same probe fires on the rule's old wording put back in the skill",
          bool(retired_in(skill.replace("a batch compiles in a lane by default", "every batch compiles in a lane", 1))))
    note = template.split("ONE-LANE BATCH:", 1)[1].split("\n", 1)[0]
    check("T08 F2 template and parallel preamble name execution before shape", all(s in note for s in
          ["batch precedence: a batch compiles in a lane by default", "to the single-source path",
           "chooses one-lane or parallel", "per-source `auto` sequence"])
          and "A batch compiled in a lane follows the precedence in **Pacing**" in parallel)
    partition_step = skill.split("1. **Partition", 1)[1].split("**Then the brief check", 1)[0]
    # T09 updated with the update count: the retired parts procedure's phrases leave the rule, and the
    # outcomes for an oversize update (planned alone, or waiting) join it.
    rule = ["**The size rule** (stated here once; every other mention points here)",
            "`PACK` is `--max-bytes` (default 250000 bytes, set by judgement, unmeasured",
            "`--ceiling-share` (default 0.2, set by judgement, unmeasured", "`--window-tokens` (the compile model's context window",
            "4 bytes per token (set by judgement, unmeasured), which is 800000 bytes by default",
            "min(`PACK`, `CEILING`)", "never refused and never split", "first fit's count as an upper bound",
            "exit 3 is a plan", "**A `split:` line**", "this run does not compile it", "leaves it in the inbox",
            "The parts procedure for such a source is retired", "**An `A<n>:` line**", "`--alone-share`",
            "**A `wait:` line**", "the run's log entry",
            "**A `group-over-ceiling:` line**", "never splits a group", "larger-window model", "release the grouping",
            "on the group's members alone"]
    missing = [s for s in rule if s not in partition_step]
    withdrawn = [s for s in ("part 1's helper owns the source page", "exactly one part", "split by chapter before compiling",
                             "It is compiled only once a parts procedure exists")
                 if s in skill]
    once = [(n, skill.count(n), partition_step.count(n)) for n in ("250000", "800000")]
    check("T09 the size rule is stated once, in Partition, with its split: deferral and group-over-ceiling: handling; the withdrawn parts procedure is gone",
          not missing and not withdrawn and all(total == inside >= 1 for _n, total, inside in once),
          str(missing) + str(withdrawn) + str(once))
    verifier = skill.split("3. **Verifier lane**", 1)[1].split("**Shadow coverage", 1)[0]
    check("T10 verifier grouping bounds whole-raw bytes by the verifier model's CEILING; the fixed six is gone",
          all(s in verifier for s in ["raw bytes one verifier may need to read whole", "that verifier model's `CEILING`",
                                      "every compile still checked"])
          and "up to six compile lanes" not in skill and "a seventh opens" not in skill, verifier[:400])

    def update_clause(step):
        """The update count's clause: the earlier files named with --update, under the everything-in-view principle."""
        return all(s in step for s in ["A compile needs everything in view", "`--update <file>`",
                                       "that paper's earlier converted version and its existing source page",
                                       "a source it does not name is sized as a new compile"])
    check("T11 the size rule names the update count and its principle; the retired parts-procedure promise is gone",
          update_clause(partition_step) and "It is compiled only once a parts procedure exists" not in skill
          and "the verifier of an `A<n>:` unit serving it alone" in verifier, partition_step[:300])
    check("T11 control: the same probe fails on the step with the update clause taken out",
          not update_clause(partition_step.replace("`--update <file>`", "", 1)))

else:
    print("text checks skipped (INGEST_TEXT_CHECKS unset)")

# Last legs: read-only copies, before/after manifests, and source grep with controls.
ro = root / "readonly"
ro.mkdir()
shutil.copytree(raw, ro / "raw")
shutil.copy(script, ro / "partition.py")
(ro / "groups.txt").write_text("source-00\nsource-12\n")
(ro / "ledger.jsonl").write_text(json.dumps({"event": "run_open", "inbox": ["raw/" + p.name for p in files]}) + "\n")
for p in sorted(ro.rglob("*"), reverse=True):
    p.chmod(0o555 if p.is_dir() else 0o444)
ro.chmod(0o555)
before = manifest(ro)
home_before = manifest(here)
results = [run("--inbox", ro / "raw", "--lanes", 4, helper=ro / "partition.py"),
           run("--ledger", ro / "ledger.jsonl", "--vault", ro, "--max-bytes", 500, "--group", ro / "groups.txt", helper=ro / "partition.py"),
           run("--inbox", ro / "raw", "--lanes", 0, helper=ro / "partition.py"),
           run("--inbox", ro / "raw", "--window-tokens", 50, helper=ro / "partition.py")]
# W01 updated by the size rule: the exit-3 path (a 40-byte ceiling reports every source) is proven write-free too.
check("W01 read-only copy succeeds, broken premise fails and a split plan exits 3",
      [r.returncode for r in results] == [0, 0, 2, 3] and results[3].stdout.count("\nsplit: ") == 13, str(results))
after = manifest(ro)
check("W02 checksum manifests unchanged, with non-empty file controls", bool(before) and before == after
      and bool(home_before) and home_before == manifest(here), "copy files %d; source files %d" % (len(before), len(home_before)))
print("  manifest controls: copy files %d · source files %d" % (len(before), len(home_before)))
patterns = [r'''(?:open|\.open)\([^)]*['"][rwxabt+]*[wax+][rwxabt+]*['"]''',
            r"\.write(?:_text|_bytes)?\(",
            r"\.(?:replace|rename|remove|unlink|mkdir|makedirs|rmdir|symlink|symlink_to|link|touch|truncate|chmod)\(",
            r"\bshutil\.", r"\bsubprocess\b|\bos\.(?:system|popen)\("]
controls = ['p.open("wb")', 'p.write_text(x)', 'p.unlink()', 'shutil.copy(a,b)', 'subprocess.run(x)']
source = script.read_text()
dead = [p for p, c in zip(patterns, controls) if not re.search(p, c)]
hits = [m.group(0) for p in patterns for m in re.finditer(p, source)]
print("  source grep: patterns %d · dead %d · hits %d" % (len(patterns), len(dead), len(hits)))
check("W03 source write-pattern grep is zero; every pattern hits its positive control", not dead and not hits, str(hits))
# W04: the --update plans (packed, alone, waiting) on a read-only copy write nothing; a byte changed there is caught.
ro4 = root / "readonly-update"
(ro4 / "inbox").mkdir(parents=True)
(ro4 / "earlier").mkdir()
shutil.copy(script, ro4 / "partition.py")
for stem, size in (("u1", 100000), ("u2", 300000), ("u3", 600000)):
    (ro4 / "inbox" / (stem + ".md")).write_bytes(b"x" * size)
    (ro4 / "earlier" / (stem + "-v1.md")).write_bytes(b"y" * {"u1": 100000, "u2": 550000, "u3": 650000}[stem])
(ro4 / "packed.txt").write_text("u1 earlier/u1-v1.md\n")
(ro4 / "alone.txt").write_text("u1 earlier/u1-v1.md\nu2 earlier/u2-v1.md\n")
(ro4 / "wait.txt").write_text("u1 earlier/u1-v1.md\nu2 earlier/u2-v1.md\nu3 earlier/u3-v1.md\n")
for p in sorted(ro4.rglob("*"), reverse=True):
    p.chmod(0o555 if p.is_dir() else 0o444)
ro4.chmod(0o555)
before4 = manifest(ro4)
codes4 = [run("--inbox", ro4 / "inbox", "--vault", ro4, "--update", ro4 / name, helper=ro4 / "partition.py").returncode
          for name in ("packed.txt", "alone.txt", "wait.txt")]
after4 = manifest(ro4)
victim4 = ro4 / "packed.txt"
ro4.chmod(0o755); victim4.chmod(0o644)
victim4.write_bytes(b"X" + victim4.read_bytes()[1:])
victim4.chmod(0o444); ro4.chmod(0o555)
check("W04 --update plans on a read-only copy exit 0, 0 and 3 with the manifest unchanged; a byte changed there is caught",
      codes4 == [0, 0, 3] and before4 == after4 and len(before4) == 10 and manifest(ro4) != before4,
      "codes %s · files %d" % (codes4, len(before4)))
ro4.chmod(0o755)
for p in ro4.rglob("*"):
    p.chmod(0o755 if p.is_dir() else 0o644)
print("%s %d/%d" % ("FAIL" if failed else "PASS", failed if failed else passed, passed + failed))
sys.exit(bool(failed))
PARTITION_SUITE_PY
