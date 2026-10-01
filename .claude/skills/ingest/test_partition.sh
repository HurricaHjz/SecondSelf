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
rejects("P32 oversized source", ["--inbox", raw, "--max-bytes", 100], "exceeds --max-bytes")
group.write_text("source-00\nsource-12\n")
rejects("P33 oversized group", ["--inbox", raw, "--max-bytes", 300, "--group", group], "exceeds --max-bytes")
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
check("P47 an extra lane opens when the byte lower bound cannot pack whole sources",
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

# Enable part 8 checks when its independent text diff is installed.
if os.environ.get("INGEST_TEXT_CHECKS") == "1":
    # Text controls are tested beside the installed helper, without needing a stage twin.
    skill = (here / "SKILL.md").read_text()
    pacing = skill.split("## Pacing", 1)[1].split("## ", 1)[0]
    parallel = skill.split("## Parallel mode", 1)[1].split("\n1.", 1)[0]
    template = (here.parent / "delegate" / "templates" / "brief-compile.md").read_text()
    check("T01 retired count trigger absent; one-lane control present", not re.search("≥6 independent sources|≤5 stays|≲5 files", pacing + parallel)
          and "one-lane" in pacing and "source-size" in pacing)
    check("T02 one-lane budget, serial batch and verify path present", all(s in pacing for s in
          ["250000", "set by judgement, unmeasured", "serially", "Step 7", "Verify step", "Routing", "no claims", "no merge", "no conflict lane"]))
    check("T03 spawner slot covers one-lane shared writes, sorting and verification", all(s in template.split("<!-- Spawner:", 1)[1]
          for s in ["one-lane", "serially", "shared pages", "index lines", "log entry", "Step 7", "one verify lane"]))
    check("T04 partition step names the script assertion", "partition.py" in skill and "the script asserts" in skill)
    precedence = ("**Execution precedence:** the delegation regime governs whether a lane runs at all; "
                  "Pacing governs the lane shape once a lane is warranted.")
    def precedence_probe(body):
        return subprocess.run(["grep", "-F", "-x", "--", precedence], input=body,
                              capture_output=True, text=True)
    present = precedence_probe(pacing)
    check("T05 F2 execution precedence sentence found by exact grep", present.returncode == 0
          and present.stdout == precedence + "\n" and not present.stderr)
    removed = precedence_probe(pacing.replace(precedence + "\n", ""))
    check("T06 F2 removed precedence sentence fails the same probe", removed.returncode == 1
          and not removed.stdout and not removed.stderr and present.returncode == 0)
    counter_case = ("A two-source batch under `single`, with no owner lane request and no instrument-rule reason, "
                    "is compiled by the head; the same fitting batch under `multi`, or with an explicit owner lane request, "
                    "uses `one-lane` unless the owner chooses `parallel`.")
    check("T07 F2 single, multi and explicit-owner counter-cases are settled", counter_case in pacing
          and "when no pacing shape has been chosen" in pacing
          and "registries where the ingest exception is not granted" in pacing)
    note = template.split("ONE-LANE BATCH:", 1)[1].split("\n", 1)[0]
    check("T08 F2 template and parallel preamble name execution before shape", all(s in note for s in
          ["execution precedence", "the delegation regime governs whether a lane runs at all",
           "then Pacing governs its shape", "per-source `auto` sequence"])
          and "the delegation regime first determines whether a lane is warranted" in parallel)

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
           run("--inbox", ro / "raw", "--lanes", 0, helper=ro / "partition.py")]
check("W01 read-only copy succeeds and broken premise fails", [r.returncode for r in results] == [0, 0, 2], str(results))
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
print("%s %d/%d" % ("FAIL" if failed else "PASS", failed if failed else passed, passed + failed))
sys.exit(bool(failed))
PARTITION_SUITE_PY
