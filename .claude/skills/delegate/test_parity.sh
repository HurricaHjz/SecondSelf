#!/bin/sh
# test_parity.sh — the suite for parity.py.   Run:  sh .claude/skills/delegate/test_parity.sh
#
# Every leg runs a real subcommand against a fixture under one /tmp root and asserts the observable
# output and the exit code. Each guard is attacked as well as exercised: a planted case that must be
# caught, a clean case that must pass, and two closing legs proving the script wrote nothing outside
# its own --out root (a checksum manifest of the read-only fixture vault and of the two shipped
# skill directories, before and after, plus a source sweep for write patterns whose own positive
# control must hit). Each invocation creates a private temporary root and removes only that root
# on exit, including its dot-entries. Last line: PASS n/n, or FAIL k/n.
set -u

HERE=$(cd -- "$(dirname -- "$0")" && pwd)
PY=${PARITY_PY:-$HERE/parity.py}
SKILLS=$(dirname "$HERE")
# The parity script, lint scripts and lane wrapper sit beside this skill. A staged copy of the suite (a lane's
# working copy under /tmp) is not beside them, so each may also be named by an environment
# variable; a missing lint directory is a broken premise, never a quiet skip.
LINT=${PARITY_LINT_DIR:-$SKILLS/lint}
LANE=${PARITY_LANE_PY:-$HERE/lane.py}
if [ "${1:-}" != --fixture-only ] && [ ! -d "$LINT" ]; then
  printf 'PROBE FAILED: no lint script directory at %s (name it with PARITY_LINT_DIR)\n' "$LINT"
  printf 'FAIL 1/1\n'
  exit 2
fi
if [ ! -f "$PY" ]; then
  printf 'PROBE FAILED: no parity script at %s (name it with PARITY_PY)\n' "$PY"
  printf 'FAIL 1/1\n'
  exit 2
fi
ROOT=$(mktemp -d "${TMPDIR:-/tmp}/b6-parity-suite.XXXXXX") || {
  printf 'PROBE FAILED: could not create the parity fixture root\n'
  printf 'FAIL 1/1\n'
  exit 2
}
# Only this invocation owns ROOT. EXIT also runs after any of the signal handlers.
trap 'rm -rf -- "$ROOT"' 0
trap 'exit 1' HUP INT TERM
PARITY_SUITE_ROOT=$ROOT
export PARITY_SUITE_ROOT
O="$ROOT/out.txt"
B="$ROOT/brief-lint.md"

pass=0
fail=0
ok() { pass=$((pass + 1)); printf 'ok   %s\n' "$1"; }
no() { fail=$((fail + 1)); printf 'FAIL %s\n' "$1"; }

make_dir() {
  python3 -B -c "
import os, sys
os.makedirs(sys.argv[1], exist_ok=True)
" "$1"
}

manifest() {
  python3 -B -c "
import hashlib, os, sys
rows = []
for root in sys.argv[1:]:
    for dirpath, dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            p = os.path.join(dirpath, name)
            try:
                digest = hashlib.sha256(open(p, 'rb').read()).hexdigest()
            except OSError:
                digest = 'unreadable'
            rows.append(digest + ' ' + os.path.relpath(p, root))
print(chr(10).join(sorted(rows)))
" "$@"
}

run() {
  want=$1; label=$2; shift 2
  PYTHONDONTWRITEBYTECODE=1 python3 -B "$PY" "$@" > "$ROOT/out.txt" 2>&1
  got=$?
  if [ "$got" -eq "$want" ]; then ok "$label (exit $got)"; else no "$label (exit $got, wanted $want)"; fi
}

has() { if grep -q -- "$2" "$O"; then ok "$1"; else no "$1 — not in output: $2"; fi; }
infile() { if grep -q -- "$2" "$3"; then ok "$1"; else no "$1"; fi; }
hasnt() { if grep -q -- "$2" "$O"; then no "$1 — output carries: $2"; else ok "$1"; fi; }
notinfile() { if grep -q -- "$2" "$3"; then no "$1 — $3 carries: $2"; else ok "$1"; fi; }
skip() { printf 'skip %s — %s\n' "$1" "$2"; }
# The arm-leak check of a judge's brief (register 2026-10-04 13:01). Path tokens go first: a run
# of characters holding a `/`, between whitespace, quotes, backticks or brackets, names a file,
# and a scratch folder named CR-HOST-B2 is not an arm. What is left is searched for an arm id as
# a standalone token (A or B and digits, with no letter, digit, `_` or `-` either side) and for
# the arm words. Exit 0 with the hits on stdout when the file names an arm, 1 when it names none.
arm_named() {
  python3 -B -c '
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
bare = re.sub(r"[^\s`\x27\x22()<>\[\]{},;]*/[^\s`\x27\x22()<>\[\]{},;]*", " ", text)
hits = re.findall(r"(?<![A-Za-z0-9_-])[AB][0-9]+(?![A-Za-z0-9_-])|arm-a|arm-b|thin arm", bare)
print(" ".join(hits))
raise SystemExit(0 if hits else 1)
' "$1"
}

# --fixture-only exercises the directory and mapping contract without the lint dependencies.
# The same legs also run in the full suite. Every refusal checks both status and explanation.
fixture_membership() {
  python3 -B - "$PY" "$ROOT" <<'PARITY_MEMBERSHIP_END'
import hashlib, json, os, re, stat, subprocess, sys
from pathlib import Path

script = Path(sys.argv[1]).resolve()
root = Path(sys.argv[2]) / "membership"
root.mkdir()
results = []

def check(label, good):
    results.append(bool(good))
    print(("ok   " if good else "FAIL ") + label)

def manifest(paths):
    files = [p for root in paths for p in (sorted(root.rglob("*")) if root.is_dir() else [root])
             if p.is_file()]
    return [(str(p), hashlib.sha256(p.read_bytes()).hexdigest(), stat.S_IMODE(p.stat().st_mode))
            for p in files]

def invoke(*args):
    return subprocess.run([sys.executable, "-B", str(script), *map(str, args)],
                          capture_output=True, text=True)

def build(name):
    return invoke("fixture", "--arm-a", root / "one", "--arm-b", root / "two",
                  "--out", root / name, "--seed", "1")

def brief(name):
    return invoke("judge-brief", "--fixture", root / name / "fixture",
                  "--truth", root / "truth", "--out", root / (name + ".md"), "--rubric", "lint")

def refused(result, reason):
    return result.returncode == 2 and result.stdout.startswith("PROBE FAILED: ") and reason in result.stdout

for name, content in (("one", "A1 head\n"), ("two", "B1 thin\n")):
    (root / name).mkdir()
    (root / name / "result.md").write_text(content)
(root / "truth").mkdir()
(root / "truth/truth.md").write_text("SCANNED: 2 pages\n")
protected = [script, root / "one", root / "two", root / "truth"]
before = manifest(protected)

result = build("clean")
check("ordinary build: zero leaks with a nonzero source control", result.returncode == 0 and
      re.search(r"control: leak sweep 0 hits over the fixture, [1-9][0-9]* over", result.stdout))
snapshot = manifest([root / "clean"])
result = brief("clean")
check("ordinary brief: exactly the two mapped ids, with blindness control", result.returncode == 0 and
      "2 artefacts" in result.stdout and "0 hits on the brief and 2 on a planted marker" in result.stdout)
check("ordinary brief leaves its fixture and mapping unchanged", snapshot == manifest([root / "clean"]))

for name, planted in (("leftover", "art-99.md"), ("empty", None), ("hidden", ".leftover")):
    directory = root / name / "fixture"
    directory.mkdir(parents=True)
    if planted:
        (directory / planted).write_text("leftover\n")
    snapshot = manifest([root / name])
    result = build(name)
    check("build refuses existing %s directory without changing it" % name,
          refused(result, "fresh fixture directory") and snapshot == manifest([root / name]))

mutations = ("extra", "hidden", "missing", "directory", "symlink", "no-mapping",
             "bad-json", "bad-table", "empty-table", "bad-id")
for mutation in mutations:
    name = "judge-" + mutation
    built = build(name)
    fixture = root / name / "fixture"
    mapping = root / name / "mapping.json"
    expected = "fixture files differ from mapping"
    if mutation in ("extra", "hidden"):
        (fixture / ("art-99.md" if mutation == "extra" else ".extra")).write_text("added later\n")
    elif mutation in ("missing", "directory", "symlink"):
        path = fixture / "art-1.md"
        path.unlink()
        if mutation == "directory":
            path.mkdir()
        elif mutation == "symlink":
            path.symlink_to(fixture / "art-2.md")
        if mutation != "missing":
            expected = "not a regular file"
    elif mutation == "no-mapping":
        mapping.unlink()
        expected = "fixture mapping"
    elif mutation == "bad-json":
        mapping.write_text("{")
        expected = "invalid fixture mapping"
    else:
        value = {"bad-table": [], "empty-table": {}, "bad-id": {"../outside": {}}}[mutation]
        mapping.write_text(json.dumps({"neutral_to_arm": value}))
        expected = "no valid neutral_to_arm table"
    snapshot = manifest([root / name])
    result = brief(name)
    check("judge refuses %s without a brief or input changes" % mutation,
          built.returncode == 0 and refused(result, expected) and
          not (root / (name + ".md")).exists() and snapshot == manifest([root / name]))

check("protected inputs and helper are byte-identical after all commands", before == manifest(protected))
witness = root / "one/result.md"
mode = stat.S_IMODE(witness.stat().st_mode)
with witness.open("r+b") as fh:
    fh.write(b"!")
check("manifest catches one byte in the same input folder under unchanged permissions",
      before != manifest(protected) and stat.S_IMODE(witness.stat().st_mode) == mode)
failed = len(results) - sum(results)
print("FAIL %d/%d" % (failed, len(results)) if failed else "PASS %d/%d" % (len(results), len(results)))
raise SystemExit(1 if failed else 0)
PARITY_MEMBERSHIP_END
}

if [ "${1:-}" = --fixture-only ]; then
  fixture_membership
  exit $?
fi

# ---------------------------------------------------------------- fixture tree
make_dir "$ROOT/arm-one"
make_dir "$ROOT/arm-two"
make_dir "$ROOT/vault/wiki"
make_dir "$ROOT/vault/raw"     # the lint root guard (2026-09-07) wants raw/ beside wiki/
# The synthetic vault has no search index; declare the optional index disabled.
touch "$ROOT/vault/.qmd-off"
make_dir "$ROOT/vault/.claude/skills/demo"
make_dir "$ROOT/vault/.claude/agents"
make_dir "$ROOT/emptylint"

cat > "$ROOT/arm-one/lint.md" <<'ARTEFACT_A1'
# Lint artefact A1
Produced by the synthetic head of run run-20990101-fixture, session 00000000-0000-4000-8000-000000000001,
at 2099-01-01T04:12:00Z on vendor-opus-5. The head read the pages itself; no lane, no pack.
DEAD LINKS: 0 and DEAD EMBEDS: 0 by my own count.
ARTEFACT_A1

cat > "$ROOT/arm-one/query.md" <<'ARTEFACT_A2'
# Query artefact A2
Written 2026-09-05 04:20 by the same head. Costs by phase are cited from the run record.
ARTEFACT_A2

cat > "$ROOT/arm-two/lint.md" <<'ARTEFACT_B1'
# Lint artefact B1
Produced by a synthetic thin head in run run-20990101-fixture at 04:31 with a lint lane and a hunter pack,
model fable-5-1, session 0000000b. Counts copied from the scripts.
ARTEFACT_B1

cat > "$ROOT/arm-two/query.md" <<'ARTEFACT_B2'
# Query artefact B2
The thin arm answered from a pack of pointers, 2026-09-05 04:35, no page read whole.
ARTEFACT_B2

cat > "$ROOT/vault/wiki/index.md" <<'VAULT_INDEX'
---
title: "Index"
type: index
confidence: high
---
The catalogue links [[page-one]] and [[page-two]].
VAULT_INDEX

cat > "$ROOT/vault/wiki/page-one.md" <<'VAULT_P1'
---
title: "Page one"
type: source
confidence: medium
---
Page one links to [[page-two]] and states that the run cost 42.00 dollars by phase.
The three waste classes were idle minutes, over-cap reports and denials.
VAULT_P1

cat > "$ROOT/vault/wiki/page-two.md" <<'VAULT_P2'
---
title: "Page two"
type: source
confidence: medium
---
Page two links back to [[page-one]] and records the phase costs in a table.
VAULT_P2

cat > "$ROOT/vault/.claude/skills/demo/SKILL.md" <<'VAULT_SKILL'
---
name: demo
description: a shipped surface so the shipped-links check has something to scan
---
This surface cites the page named page-one in code font, never as a link.
VAULT_SKILL

cat > "$ROOT/vault/.claude/agents/demo-agent.md" <<'VAULT_AGENT'
---
name: demo-agent
description: a shipped definition so the agents arm of the shipped-links check is not empty
---
Nothing here links anywhere.
VAULT_AGENT

cat > "$ROOT/record.jsonl" <<'RECORD'
{"ts": "2026-09-05T04:00+0100", "event": "run-open", "run": "run-x", "session": "arm-one"}
{"ts": "2026-09-05T04:05+0100", "event": "gate", "run": "run-x", "lane": "arm-one", "context": 100000}
{"ts": "2026-09-05T04:20+0100", "event": "gate", "run": "run-x", "lane": "arm-one", "context": 300000}
{"ts": "2026-09-05T04:35+0100", "event": "gate", "run": "run-x", "lane": "arm-one", "context": 500000}
{"ts": "2026-09-05T04:06+0100", "event": "gate", "run": "run-x", "lane": "arm-two", "context": 80000}
{"ts": "2026-09-05T04:21+0100", "event": "gate", "run": "run-x", "lane": "arm-two", "context": 140000}
{"ts": "2026-09-05T04:36+0100", "event": "gate", "run": "run-x", "lane": "arm-two", "context": 200000}
RECORD

# The meter fixtures copy the metering script's own line shape, whose separator is built here
# rather than written literally (a bare separator in this file reads as a path to the lane fence).
python3 -B -c "
import os
root = os.environ['PARITY_SUITE_ROOT']
s = ' ' + chr(47) + ' '
share = 'fable share: head %s out' + s + '%s flow' + s + '%s peak'
billed = 'billed (list, prices 2026-09-01): head \$%s . lanes %s . session \$%s . rewrites 0'
nl = chr(10)
open(root + '/meter-a.txt', 'w').write(
    share % ('120,000', '3,110,000', '412,000') + nl + billed % ('2.40', 'not scanned', '2.40') + nl)
open(root + '/meter-b.txt', 'w').write(
    share % ('90,000', '1,900,000', '210,000') + nl + billed % ('1.10', '\$0.40', '1.50') + nl)
open(root + '/meter-unmetered.txt', 'w').write(
    'fable share: unmetered (no transcript for this session)' + nl)
"

manifest "$ROOT/vault" "$LINT" "$HERE" > "$ROOT/manifest-before.txt"

if fixture_membership; then ok "fixture membership regression legs"; else no "fixture membership regression legs"; fi

# ---------------------------------------------------------------- 1 fixture, clean run
run 0 "fixture builds the blind fixture" fixture --run run-x --arm-a "$ROOT/arm-one" \
  --arm-b "$ROOT/arm-two" --out "$ROOT/fx" --seed 7
has "fixture reports four artefacts, two per arm" "fixture: 4 artefacts (2 per arm)"
has "fixture reports its redaction counts" "^redactions: "
has "fixture reports a leak sweep with a nonzero source control" "control: leak sweep 0 hits"
n=$(ls "$ROOT/fx/fixture" | grep -c '^art-')
if [ "$n" -eq 4 ]; then ok "four neutral artefacts written"; else no "four neutral artefacts written (saw $n)"; fi
if [ -f "$ROOT/fx/mapping.json" ]; then ok "the mapping sits outside the fixture directory"; else no "no mapping written"; fi
m=$(ls "$ROOT/fx/fixture" | grep -c 'mapping')
if [ "$m" -eq 0 ]; then ok "no mapping inside the granted fixture directory"; else no "a mapping leaked into the fixture directory"; fi

# ---------------------------------------------------------------- 2 blindness, planted markers
SWEEP='run-20990101-fixture|00000000-0000-4000-8000-000000000001|0000000b|fable-5-1|vendor-opus|thin|pack|[0-9]{4}-[0-9]{2}-[0-9]{2}'
leaks=$(grep -R -l -E "$SWEEP" "$ROOT/fx/fixture" | wc -l | tr -d ' ')
src=$(grep -R -l -E "$SWEEP" "$ROOT/arm-one" "$ROOT/arm-two" | wc -l | tr -d ' ')
if [ "$leaks" -eq 0 ]; then ok "planted markers are gone from the fixture (negative control)"; else no "planted markers survive in $leaks fixture file(s)"; fi
if [ "$src" -gt 0 ]; then ok "the same sweep hits $src source file(s) (positive control)"; else no "the sweep hit nothing in the sources — the control did not fire"; fi
a1=$(grep -R -l 'A1' "$ROOT/fx/fixture" | wc -l | tr -d ' ')
if [ "$a1" -eq 0 ]; then ok "arm artefact ids are mapped away"; else no "an arm artefact id survives in the fixture"; fi

# ---------------------------------------------------------------- 3 fixture premise failures
run 2 "fixture refuses a missing arm directory" fixture --arm-a "$ROOT/nope" \
  --arm-b "$ROOT/arm-two" --out "$ROOT/fx2"
has "the missing arm is named" "PROBE FAILED: arm a directory not found"

make_dir "$ROOT/arm-short"
cat > "$ROOT/arm-short/only.md" <<'SHORT'
One artefact only, written 2026-09-05 by a lane.
SHORT
run 2 "fixture refuses unequal artefact counts" fixture --arm-a "$ROOT/arm-one" \
  --arm-b "$ROOT/arm-short" --out "$ROOT/fx3"
has "the unequal counts are named" "different artefact counts"

make_dir "$ROOT/bland-a"
make_dir "$ROOT/bland-b"
cat > "$ROOT/bland-a/x.md" <<'BLAND_A'
nothing worth redacting in me
BLAND_A
cat > "$ROOT/bland-b/x.md" <<'BLAND_B'
nor in me either
BLAND_B
run 2 "fixture refuses when its leak-sweep control cannot fire" fixture \
  --arm-a "$ROOT/bland-a" --arm-b "$ROOT/bland-b" \
  --out "$ROOT/fx4"
has "the silent control is named" "leak-sweep control did not fire"

run 2 "fixture refuses an empty arm directory" fixture --arm-a "$ROOT/emptylint" \
  --arm-b "$ROOT/arm-two" --out "$ROOT/fx5"
has "the empty arm is named" "holds no artefact matching"

# ---------------------------------------------------------------- 4 truth, clean run
run 0 "truth runs the five lint checks" truth --vault "$ROOT/vault" \
  --lint-dir "$LINT" --out "$ROOT/tr"
has "truth names its five checks" "truth: 5 checks"
has "truth prints a headline control per check" "^control: check-links"
for label in check-links check-orphans check-shipped-links check-qmd-registry tier-cap-check; do
  infile "the truth file carries $label" "## $label" "$ROOT/tr/truth.md"
done
infile "the truth file carries a headline count verbatim" 'DEAD LINKS:' "$ROOT/tr/truth.md"

# ---------------------------------------------------------------- 5 truth premise failures
run 2 "truth refuses a lint directory with no scripts" truth --vault "$ROOT/vault" \
  --lint-dir "$ROOT/emptylint" --out "$ROOT/tr2"
has "the missing script is named" "PROBE FAILED: lint script not found"
if [ -f "$ROOT/tr2/truth.md" ]; then no "an aborted truth run left a truth file"; else ok "an aborted truth run leaves no truth file"; fi

run 2 "truth refuses a vault with no wiki directory" truth --vault "$ROOT/arm-one" \
  --lint-dir "$LINT" --out "$ROOT/tr3"
has "the wrong root is named" "no wiki directory under"

# ---------------------------------------------------------------- 6 query truth
run 0 "truth builds the query truth" truth --vault "$ROOT/vault" --lint-dir "$LINT" \
  --out "$ROOT/tr" --query-pages wiki/page-one.md wiki/page-two.md \
  --query-grep 'phase' --query-grep 'waste classes'
has "the query truth counts its matched lines" "query-truth: 2 page(s)"
infile "the query truth carries the frontmatter title" 'title: Page one' "$ROOT/tr/query-truth.md"
infile "the query truth carries path and line locators" 'page-one.md:' "$ROOT/tr/query-truth.md"

run 2 "truth refuses a query pattern that matches nothing" truth --vault "$ROOT/vault" \
  --lint-dir "$LINT" --out "$ROOT/tr4" --query-pages wiki/page-one.md \
  --query-grep 'zzz-no-such-phrase'
has "the empty pattern is named" "matched no line in any named page"

run 2 "truth refuses a query page that is not there" truth --vault "$ROOT/vault" \
  --lint-dir "$LINT" --out "$ROOT/tr5" --query-pages wiki/absent.md --query-grep 'phase'
has "the absent page is named" "query page not found"

# ---------------------------------------------------------------- 7 judge brief
run 0 "judge-brief composes the lint brief" judge-brief --fixture "$ROOT/fx/fixture" \
  --truth "$ROOT/tr" --out "$ROOT/brief-lint.md" --rubric lint \
  --lane J1 --run run-x
has "judge-brief reports its controls" "blindness sweep 0 hits"
has "judge-brief reports every slot filled" "slots: 8 filled, no placeholder left"
for slot in TASK SCOPE REGISTRIES GRANTS DECISIONS VERIFICATION CONDUCT REPORT; do
  infile "the brief carries the $slot slot" "^$slot$" "$B"
done
infile "the brief states the score line format" 'SCORE ART-ID accuracy=N completeness=N citations=N' "$B"
infile "the brief carries a positive-control line" 'CONTROL+: ' "$B"
# D37 and D39: a bare rubric line the judge echoes, a bare control-plus line with nothing after the
# file path, and a separate negative-control line. The one-line `Controls: positive … negative …`
# form fails: the wrapper splits the control-plus line on its last ' in ', so prose after the path
# would be read as part of the path.
infile "the brief carries the bare rubric line the score step groups on" '^RUBRIC: lint$' "$B"
infile "the control-plus line starts its own line" '^CONTROL+: ' "$B"
infile "the negative control is a separate line" '^Negative control: ' "$B"
infile "the brief tells the judge to echo the rubric line first" 'FIRST line of your report is the bare line' "$B"
has "judge-brief reports the two mechanical lines" "^lines: 1 bare"
ctl=$(python3 -B -c "
import re, sys
found = re.findall(r'(?m)^CONTROL[+]: (.+)\$', open(sys.argv[1]).read())
if len(found) != 1:
    print('control lines: %d' % len(found)); raise SystemExit
body = found[0]
cut = body.rfind(' in ')                      # the wrapper splits on the LAST ' in '
path = body[cut + 4:] if cut != -1 else ''
print('ok' if path and path == path.strip() and path.endswith('truth.md') else 'tail=%r' % path)
" "$B")
if [ "$ctl" = ok ]; then ok "the control line ends at the truth file with nothing after it"; else no "the control line is malformed ($ctl)"; fi
badctl=$(python3 -B -c "
import re
line = 'CONTROL+: a phrase in /tmp/x/truth.md  (report the line you found it on)'
body = re.match(r'^CONTROL[+]: (.+)\$', line).group(1)
path = body[body.rfind(' in ') + 4:]
print('caught' if not path.endswith('truth.md') else 'missed')
")
if [ "$badctl" = caught ]; then ok "the same check catches a planted trailing clause (positive control)"; else no "the control-line check passed a planted trailing clause"; fi
# The pin itself: the wrapper's own parser, run for real on the generated brief. A dry run spawns
# nothing and writes nothing (it prints what it would write). `--reason` is required at every spawn,
# dry runs included, and is checked before any record line, so an omitted one refuses with exit 2
# and this leg's parser is never reached (2026-09-07). The letter is (a) independence because the
# parity judge is a blind lane: it is the instrument rule this spawn is opened under, not a token
# added to satisfy the wrapper, and the leg's intent — the wrapper's own control parser run on the
# generated brief — is unchanged.
if [ -f "$LANE" ]; then
  # A dry run makes no model call; its positive estimate is set by judgement, unmeasured.
  PYTHONDONTWRITEBYTECODE=1 python3 -B "$LANE" init --home "$ROOT/lane-home" > "$ROOT/init.txt" 2>&1
  home_rc=$?
  if [ "$home_rc" -eq 0 ]; then ok "the parser fixture has an initialised lane home"; else no "lane-home fixture init failed (exit $home_rc)"; fi
  PYTHONDONTWRITEBYTECODE=1 python3 -B "$LANE" spawn --dry-run --home "$ROOT/lane-home" --expect-usd 1 --model opus --effort max --choice-reason "fixture: exercise the Claude wrapper parser" --run run-x --lane J1 \
    --class critic --brief "$B" --grant "$ROOT/fx/fixture" \
    --grant "$ROOT/tr" --grants-only --delegation single --delegation-src head \
    --reason "(a) independence: the parity judge scores the fixture blind to its arm" \
    > "$ROOT/dry.txt" 2>&1
  dry=$?
  if [ "$dry" -eq 0 ]; then ok "the spawn wrapper accepts the brief on a dry run (exit 0)"; else no "the spawn wrapper refused the brief (exit $dry)"; fi
  infile "the wrapper's control parser lands on the truth file" 'truth.md", "matches"' "$ROOT/dry.txt"
  infile "the wrapper counted a nonzero match (positive control)" '"matches": [1-9]' "$ROOT/dry.txt"
  notinfile "the parsed control file carries no trailing prose" 'truth.md (report' "$ROOT/dry.txt"
else
  skip "the spawn wrapper's own control parser on this brief" "no lane.py at $LANE (name it with PARITY_LANE_PY); the regex legs above stand in"
fi
phrase=$(python3 -B -c "
import re, sys
m = re.search(r'CONTROL[+]: (.+?) in ', open(sys.argv[1]).read())
print(m.group(1) if m else '')
" "$B")
if [ -n "$phrase" ] && grep -qF "$phrase" "$ROOT/tr/truth.md"; then ok "the control phrase really occurs in the truth file"; else no "the control phrase is not in the truth file"; fi
# The arm check reads ids as tokens outside paths (arm_named); 7c below plants a path that must
# pass and a disclosure that must fail, the positive control for this clean result.
if armhit=$(arm_named "$B"); then no "the brief names an arm: $armhit"; else ok "the brief names no arm (blind)"; fi

run 0 "judge-brief composes the query brief" judge-brief --fixture "$ROOT/fx/fixture" \
  --truth "$ROOT/tr" --out "$ROOT/brief-query.md" --rubric query
has "the query brief leaves the spawner its placeholders" "placeholders left for the spawner"
infile "the query brief carries its own bare rubric line" '^RUBRIC: query$' "$ROOT/brief-query.md"
notinfile "the query brief does not carry the other rubric's key" '^RUBRIC: lint$' "$ROOT/brief-query.md"

run 2 "judge-brief refuses a marker that would unblind the judge" judge-brief \
  --fixture "$ROOT/fx/fixture" --truth "$ROOT/tr" \
  --out "$ROOT/brief-bad.md" --rubric lint --arm-marker fixture
has "the leaking marker is named" "the judge would not be blind"

run 2 "judge-brief refuses a missing truth file" judge-brief --fixture "$ROOT/fx/fixture" \
  --truth "$ROOT/emptylint" --out "$ROOT/brief-bad2.md" --rubric lint
has "the missing truth file is named" "truth file for rubric lint not found"

run 2 "judge-brief refuses an empty fixture" judge-brief --fixture "$ROOT/emptylint" \
  --truth "$ROOT/tr" --out "$ROOT/brief-bad3.md" --rubric lint
has "the empty fixture's missing mapping is named" "fixture mapping"

# ---------------------------------------------------------------- 7b id blindness: token, not path
# Planted input: the same fixture reached under two directory names carrying an arm-id-shaped pair,
# store-b6 (lowercase) and store-B6 (uppercase, inside a path component). Both briefs must compose.
# A sweep that folds case, or that reads a path as an id, refuses them, and the gate then stalls on
# a store path whose letters nobody chose for their meaning. Two controls keep the narrowing honest:
# a bare id in the identity line is still a refusal, and the fixture is untouched either way.
make_dir "$ROOT/store-b6/fixture"
make_dir "$ROOT/store-B6/fixture"
cp "$ROOT/fx/fixture/"*.md "$ROOT/store-b6/fixture/"
cp "$ROOT/fx/fixture/"*.md "$ROOT/store-B6/fixture/"
cp "$ROOT/fx/mapping.json" "$ROOT/store-b6/mapping.json"
cp "$ROOT/fx/mapping.json" "$ROOT/store-B6/mapping.json"
manifest "$ROOT/store-B6" > "$ROOT/blind-before.txt"

run 0 "judge-brief accepts a fixture path whose directory carries a lowercase b6" judge-brief \
  --fixture "$ROOT/store-b6/fixture" --truth "$ROOT/tr" \
  --out "$ROOT/brief-b6.md" --rubric lint --lane J1 --run run-x
run 0 "judge-brief accepts a fixture path whose directory carries an uppercase B6" judge-brief \
  --fixture "$ROOT/store-B6/fixture" --truth "$ROOT/tr" \
  --out "$ROOT/brief-B6.md" --rubric lint --lane J1 --run run-x
has "the sweep still ran on the B6 brief" "blindness sweep 0 hits"
b6lines=$(grep -c 'B6' "$ROOT/brief-B6.md")
loose=$(grep 'B6' "$ROOT/brief-B6.md" | grep -c -v '/')
if [ "$b6lines" -gt 0 ] && [ "$loose" -eq 0 ]; then ok "each of the $b6lines B6 line(s) in that brief is a path line, none a bare id (the nonzero count is the control)"; else no "the B6 brief carries $b6lines B6 line(s), $loose of them without a path"; fi
if grep -q -E 'arm-a|arm-b|thin arm' "$ROOT/brief-B6.md"; then no "the B6 brief names an arm"; else ok "the B6 brief still names no arm"; fi
manifest "$ROOT/store-B6" > "$ROOT/blind-after.txt"
if cmp -s "$ROOT/blind-before.txt" "$ROOT/blind-after.txt"; then ok "the artefact under the B6 directory is byte-identical after the sweep (negative control)"; else no "the blindness sweep changed a file under the B6 directory"; fi
run 2 "judge-brief still refuses a bare arm id outside a path" judge-brief \
  --fixture "$ROOT/store-B6/fixture" --truth "$ROOT/tr" \
  --out "$ROOT/brief-bad4.md" --rubric lint --lane A1 --run run-x
has "the bare id is named as the leak (positive control for the narrowed marker)" "the judge would not be blind"

# ---------------------------------------------------------------- 7c the arm check: token, not path
# The suite's own arm check (arm_named, the brief leg above) read the B2 of a scratch folder named
# CR-HOST-B2 as an arm (register 2026-10-04 13:01). Two planted briefs on the shape of the
# generated one: a path holding B2 must pass, and a sentence disclosing arm B2 must still fail.
ALD="$ROOT/arm-leak"
make_dir "$ALD"
cat > "$ALD/brief-path.md" <<'BRIEF_PATH'
You are gate-judge (definition: .claude/agents/gate-judge.md), lane J1 of run run-x.
Read: `/tmp/CR-HOST-B2/x` (the fixture artefacts) and `/tmp/CR-HOST-B2/x/tr` (the truth files).
CONTROL+: SCANNED: 3 pages | 4 page links in /tmp/CR-HOST-B2/x/tr/truth.md
BRIEF_PATH
cat > "$ALD/brief-arm.md" <<'BRIEF_ARM'
You are gate-judge (definition: .claude/agents/gate-judge.md), lane J1 of run run-x.
Read: `/tmp/CR-HOST-B2/x` (the fixture artefacts) and `/tmp/CR-HOST-B2/x/tr` (the truth files).
These artefacts come from arm B2, the thinner of the two.
BRIEF_ARM
cat > "$ALD/brief-lane.md" <<'BRIEF_LANE'
You are gate-judge, lane A1 of run run-x; score the fixture at /tmp/store-A1/fixture.
BRIEF_LANE
if hit=$(arm_named "$ALD/brief-path.md"); then no "AL01 a brief naming /tmp/CR-HOST-B2/x reads as naming an arm: $hit"; else ok "AL01 (must fire) a brief naming /tmp/CR-HOST-B2/x passes the arm check: the B2 inside a path is not an arm"; fi
if hit=$(arm_named "$ALD/brief-arm.md"); then ok "AL02 (must not fire) a brief disclosing \"arm B2\" beside the same path still fails the arm check ($hit)"; else no "AL02 the arm check passed a brief that discloses arm B2"; fi
hit=$(arm_named "$ALD/brief-lane.md")
if [ "$hit" = "A1" ]; then ok "AL03 (must fire) a bare id outside a path (lane A1) fails the check as exactly one hit: the A1 of the path beside it is not counted"; else no "AL03 the arm check on a bare lane A1 beside a path holding A1 read: '$hit'"; fi

# ---------------------------------------------------------------- 8 score
python3 -B -c "
import os
root = os.environ['PARITY_SUITE_ROOT']
import json
mapping = json.load(open(root + '/fx/mapping.json'))
rows = sorted(mapping['neutral_to_arm'].items())
a = [k for k, v in rows if v['arm'] == 'a']
b = [k for k, v in rows if v['arm'] == 'b']
one, two = ['RUBRIC: lint'], ['RUBRIC: lint']
for art in a:
    one.append('SCORE %s accuracy=7 completeness=7 citations=7 note=fine' % art)
    two.append('SCORE %s accuracy=7 completeness=7 citations=7 note=fine' % art)
for i, art in enumerate(b):
    one.append('SCORE %s accuracy=%d completeness=8 citations=8 note=fine' % (art, 6 if i == 0 else 8))
    two.append('SCORE %s accuracy=8 completeness=8 citations=8 note=fine' % art)
nl = chr(10)
open(root + '/judge-one.md', 'w').write(nl.join(one) + nl)
open(root + '/judge-two.md', 'w').write(nl.join(two) + nl)
open(root + '/judge-bad.md', 'w').write('no score lines at all' + nl)
open(root + '/judge-unknown.md', 'w').write('RUBRIC: lint' + nl + 'SCORE art-99 accuracy=5 completeness=5 citations=5 note=x' + nl)
open(root + '/judge-range.md', 'w').write('RUBRIC: lint' + nl + 'SCORE %s accuracy=44 completeness=5 citations=5 note=x' % a[0] + nl)
"

run 0 "score compares the arms without a record" score --report "$ROOT/judge-one.md" \
  --report "$ROOT/judge-two.md" --mapping "$ROOT/fx/mapping.json" \
  --meter-a "$ROOT/meter-a.txt" --meter-b "$ROOT/meter-b.txt" \
  --spend-a 2.40 --spend-b 1.50 --judge-spend 0.90 --judge-spend 0.95
has "score prints the table header" "^parity table: 2 judge(s)"
has "score prints an arm row with its peak and flow" "^arm-a · mean "
has "score marks the thin arm" "arm-b (thin)"
has "score prints the per-judge spend" "^judge spend: "
has "score flags the split dimension with its rubric" "^split: .* accuracy (lint) 6/8"
has "score recommends a third judge, naming the artefact and dimension" "^third-judge: recommended for .* accuracy (lint: 6 vs 8)"
has "score holds the lever while the context is unmeasured" "hold-lever — context per item unmeasured"

run 0 "score uses the gate events when a record is given" score \
  --report "$ROOT/judge-one.md" --report "$ROOT/judge-two.md" \
  --mapping "$ROOT/fx/mapping.json" --meter-a "$ROOT/meter-a.txt" \
  --meter-b "$ROOT/meter-b.txt" --record "$ROOT/record.jsonl" \
  --arm-a-key arm-one --arm-b-key arm-two
has "the deprecated shared record still gives the context per item" "context per item 200,000 (3 gate events, shared record)"
has "score passes when the thin arm is not lower and its context per item is" "^parity: pass"

run 2 "score refuses a report with no score lines" score --report "$ROOT/judge-bad.md" \
  --mapping "$ROOT/fx/mapping.json" --meter-a "$ROOT/meter-a.txt" \
  --meter-b "$ROOT/meter-b.txt"
has "the empty report is named" "carries no SCORE line"

run 2 "score refuses an id the mapping does not carry" score \
  --report "$ROOT/judge-unknown.md" --mapping "$ROOT/fx/mapping.json" \
  --meter-a "$ROOT/meter-a.txt" --meter-b "$ROOT/meter-b.txt"
has "the unknown id is named" "an id the mapping does not carry"

run 2 "score refuses a score outside the range" score --report "$ROOT/judge-range.md" \
  --mapping "$ROOT/fx/mapping.json" --meter-a "$ROOT/meter-a.txt" \
  --meter-b "$ROOT/meter-b.txt"
has "the out-of-range score is named" "outside 0 to 10"

run 2 "score refuses an unmetered arm" score --report "$ROOT/judge-one.md" \
  --mapping "$ROOT/fx/mapping.json" --meter-a "$ROOT/meter-unmetered.txt" \
  --meter-b "$ROOT/meter-b.txt"
has "the unmetered meter is named" "is unmetered"

run 2 "score refuses a record with too few gate events" score \
  --report "$ROOT/judge-one.md" --mapping "$ROOT/fx/mapping.json" \
  --meter-a "$ROOT/meter-a.txt" --meter-b "$ROOT/meter-b.txt" \
  --record "$ROOT/record.jsonl" --arm-a-key no-such-arm --arm-b-key arm-two
has "the missing gate events are named" "a per-item context needs at"

# ---------------------------------------------------------------- 8b unknown id before coverage
# Planted input: a report scoring three of the four mapped artefacts plus art-99, an id the mapping
# does not carry. Both guards fire on it, and the unknown id must be the one named: a coverage
# message would send the caller hunting the judge that dropped an artefact, while the report which
# invented an id went unmentioned. The last leg is the coverage guard's own positive control.
python3 -B -c "
import os
root = os.environ['PARITY_SUITE_ROOT']
import json
mapping = json.load(open(root + '/fx/mapping.json'))
arts = sorted(mapping['neutral_to_arm'])
lines = ['RUBRIC: lint'] + ['SCORE %s accuracy=7 completeness=7 citations=7 note=fine' % a for a in arts[:-1]]
nl = chr(10)
open(root + '/judge-gap-only.md', 'w').write(nl.join(lines) + nl)
lines.append('SCORE art-99 accuracy=5 completeness=5 citations=5 note=planted unknown id')
open(root + '/judge-unknown-gap.md', 'w').write(nl.join(lines) + nl)
"
run 2 "score names the unknown id when an artefact is also unscored" score \
  --report "$ROOT/judge-unknown-gap.md" --mapping "$ROOT/fx/mapping.json" \
  --meter-a "$ROOT/meter-a.txt" --meter-b "$ROOT/meter-b.txt"
has "the planted unknown id is the failure named" "does not carry: art-99"
hasnt "no coverage message masks the unknown id" "no judge scored"
run 2 "score still catches an artefact no judge scored" score \
  --report "$ROOT/judge-gap-only.md" --mapping "$ROOT/fx/mapping.json" \
  --meter-a "$ROOT/meter-a.txt" --meter-b "$ROOT/meter-b.txt"
has "the unscored artefact is named (positive control for the coverage guard)" "no judge scored"

# ---------------------------------------------------------------- 8c rubric grouping (D37)
# Planted input: two lint judges and two query judges, each scoring the artefacts of its own rubric.
# The truth of the fixture, computed by hand from the numbers written below: per rubric, arm a lint
# 7.00 (all sevens) and query 8.00 (all eights); arm b lint 8.50 (accuracy 9, completeness 8,
# citations (9+8)/2) and query 8.00. Over the two rubrics: arm a 7.50, arm b 8.25, where a reading
# that pooled the judges would print 4.17 and 5.08 from the mixed pool. Every per-rubric
# mean differs from its arm's mixed mean, so a grouping that silently pooled the judges again would
# print a different number in at least one row.
python3 -B -c "
import os
root = os.environ['PARITY_SUITE_ROOT']
import json
mapping = json.load(open(root + '/fx/mapping.json'))
rows = mapping['neutral_to_arm']
def pick(arm, stem):
    return [k for k, v in rows.items()
            if v['arm'] == arm and v['source'].endswith(stem + '.md')][0]
al, aq = pick('a', 'lint'), pick('a', 'query')
bl, bq = pick('b', 'lint'), pick('b', 'query')
nl = chr(10)
def line(art, acc, comp, cit):
    return 'SCORE %s accuracy=%d completeness=%d citations=%d note=fine' % (art, acc, comp, cit)
def write(name, lines):
    open(root + '/' + name, 'w').write(nl.join(lines) + nl)
write('jl-1.md', ['RUBRIC: lint', line(al, 7, 7, 7), line(bl, 9, 8, 9)])
write('jl-2.md', ['RUBRIC: lint', line(al, 7, 7, 7), line(bl, 9, 8, 8)])
write('jq-1.md', ['RUBRIC: query', line(aq, 8, 8, 8), line(bq, 8, 8, 8)])
write('jq-2.md', ['RUBRIC: query', line(aq, 8, 8, 8), line(bq, 8, 8, 8)])
# The reports that must never reach a mean: no rubric line, and a rubric no brief carries. Both
# score every artefact 1, so pooling either would move every printed figure.
ones = [line(a, 1, 1, 1) for a in (al, aq, bl, bq)]
write('jn-none.md', ['## Scores'] + ones)
write('jn-banana.md', ['RUBRIC: banana'] + ones)
write('jn-two.md', ['RUBRIC: lint', 'RUBRIC: query', line(al, 7, 7, 7), line(bl, 9, 8, 9)])
write('jn-repeat.md', ['RUBRIC: lint', line(al, 7, 7, 7), 'RUBRIC: lint', line(bl, 9, 8, 9)])
open(root + '/jn-empty.md', 'w').write('')
# The split fixture: two lint judges 2 points apart on one artefact's accuracy (must fire), and a
# lint pair and a query pair 3 points apart on another artefact's accuracy (must not fire: two
# rubrics are two tests, and a third judge would settle nothing).
write('js-lint-1.md', ['RUBRIC: lint', line(al, 7, 7, 7), line(bl, 8, 8, 8)])
write('js-lint-2.md', ['RUBRIC: lint', line(al, 9, 7, 7), line(bl, 8, 8, 8)])
write('js-query-1.md', ['RUBRIC: query', line(bl, 5, 8, 8), line(aq, 8, 8, 8), line(bq, 8, 8, 8)])
write('js-query-2.md', ['RUBRIC: query', line(bl, 5, 8, 8), line(aq, 8, 8, 8), line(bq, 8, 8, 8)])
open(root + '/ids.sh', 'w').write(
    nl.join(['A_LINT=' + al, 'A_QUERY=' + aq, 'B_LINT=' + bl, 'B_QUERY=' + bq]) + nl)
# One record per arm (D37): the same gate series as the shared record, split into its two files,
# plus a record whose events carry no gate at all.
src = [json.loads(l) for l in open(root + '/record.jsonl') if l.strip()]
for arm, lane in (('a', 'arm-one'), ('b', 'arm-two')):
    kept = [e for e in src if e.get('lane') == lane]
    open(root + '/record-' + arm + '.jsonl', 'w').write(
        nl.join(json.dumps(e) for e in kept) + nl)
open(root + '/record-nogates.jsonl', 'w').write(
    nl.join(json.dumps(e) for e in src if e.get('event') != 'gate') + nl)
print('grouping fixtures written')
"
. "$ROOT/ids.sh"


run 0 "score groups four judges by their echoed rubric" score --report "$ROOT/jl-1.md" --report "$ROOT/jl-2.md" --report "$ROOT/jq-1.md" --report "$ROOT/jq-2.md" --mapping "$ROOT/fx/mapping.json" --meter-a "$ROOT/meter-a.txt" --meter-b "$ROOT/meter-b.txt" --record-a "$ROOT/record-a.jsonl" --record-b "$ROOT/record-b.jsonl"
has "the header counts the judges per rubric" "^parity table: 4 judge(s) over 2 rubric(s) (lint 2 · query 2)"
has "arm a's lint mean is the planted 7.00" "^arm-a rubric lint · mean 7.00"
has "arm a's query mean is the planted 8.00" "^arm-a rubric query · mean 8.00"
has "arm b's lint mean is the planted 8.50" "^arm-b rubric lint · mean 8.50"
has "arm b's query mean is the planted 8.00" "^arm-b rubric query · mean 8.00"
has "arm a's mean over the rubrics is the planted 7.50" "^arm-a · mean 7.50 "
has "arm b's mean over the rubrics is the planted 8.25" "^arm-b (thin) · mean 8.25 "
hasnt "no mixed pool: arm a never scores its lint rubric's 7.00 overall" "^arm-a · mean 7.00 "
hasnt "no mixed pool: arm b never scores its lint rubric's 8.50 overall" "^arm-b (thin) · mean 8.50 "
has "each arm's context per item comes from its own record" "context per item 200,000 (3 gate events, own record)"
has "the other arm's context comes from the other record" "context per item 60,000 (3 gate events, own record)"
has "the verdict applies the rule per rubric and overall" "^parity: pass — arm-b is not lower on any rubric (lint 8.50 against 7.00 · query 8.00 against 8.00) nor overall (8.25 against 7.50)"
hasnt "no third judge is recommended on an unsplit fixture" "third-judge"

run 0 "score lists a report with no rubric line as unscored" score --report "$ROOT/jl-1.md" --report "$ROOT/jl-2.md" --report "$ROOT/jq-1.md" --report "$ROOT/jq-2.md" \
  --report "$ROOT/jn-none.md" --mapping "$ROOT/fx/mapping.json" --meter-a "$ROOT/meter-a.txt" --meter-b "$ROOT/meter-b.txt" --record-a "$ROOT/record-a.jsonl" --record-b "$ROOT/record-b.jsonl"
has "the unscored report is named with its reason" "^unscored (no RUBRIC line): $ROOT/jn-none.md"
has "the unscored report's four score lines are counted" "its 4 score line(s) enter no mean"
has "the arm means are unmoved by it (it scored everything 1)" "^arm-a · mean 7.50 "
has "the other arm's mean is unmoved too" "^arm-b (thin) · mean 8.25 "
has "the judge count still names four scored judges" "^parity table: 4 judge(s) over 2 rubric(s)"

run 0 "score lists a rubric no brief carries as unscored" score --report "$ROOT/jl-1.md" --report "$ROOT/jl-2.md" --report "$ROOT/jq-1.md" --report "$ROOT/jq-2.md" \
  --report "$ROOT/jn-banana.md" --mapping "$ROOT/fx/mapping.json" --meter-a "$ROOT/meter-a.txt" --meter-b "$ROOT/meter-b.txt" --record-a "$ROOT/record-a.jsonl" --record-b "$ROOT/record-b.jsonl"
has "the unknown rubric is named with the briefed ones" "^unscored (unknown rubric 'banana'; the briefed rubrics are lint, query)"
has "the unknown rubric moves no mean" "^arm-b (thin) · mean 8.25 "

run 2 "score refuses a report carrying two rubric lines" score \
  --report "$ROOT/jn-two.md" --mapping "$ROOT/fx/mapping.json" --meter-a "$ROOT/meter-a.txt" --meter-b "$ROOT/meter-b.txt"
has "the ambiguous grouping is named with both rubrics" "carries 2 RUBRIC lines naming lint, query"

run 0 "score accepts a report that repeats one rubric line" score --report "$ROOT/jl-1.md" --report "$ROOT/jl-2.md" --report "$ROOT/jq-1.md" --report "$ROOT/jq-2.md" \
  --report "$ROOT/jn-repeat.md" --mapping "$ROOT/fx/mapping.json" --meter-a "$ROOT/meter-a.txt" --meter-b "$ROOT/meter-b.txt" --record-a "$ROOT/record-a.jsonl" --record-b "$ROOT/record-b.jsonl"
has "the repeat is reported as a note" "^note: $ROOT/jn-repeat.md repeats its RUBRIC line 2 times (all lint)"
has "the repeating judge is counted as a lint judge" "^parity table: 5 judge(s) over 2 rubric(s) (lint 3 · query 2)"

run 2 "score refuses an empty report" score --report "$ROOT/jn-empty.md" --mapping "$ROOT/fx/mapping.json" --meter-a "$ROOT/meter-a.txt" --meter-b "$ROOT/meter-b.txt"
has "the empty report is named" "carries no SCORE line"

run 2 "score refuses a report set with no groupable rubric at all" score \
  --report "$ROOT/jn-none.md" --report "$ROOT/jn-banana.md" --mapping "$ROOT/fx/mapping.json" --meter-a "$ROOT/meter-a.txt" --meter-b "$ROOT/meter-b.txt"
has "both reasons are listed" "every judge report is unscored"

run 0 "score splits within a rubric and not across" score \
  --report "$ROOT/js-lint-1.md" --report "$ROOT/js-lint-2.md" \
  --report "$ROOT/js-query-1.md" --report "$ROOT/js-query-2.md" \
  --mapping "$ROOT/fx/mapping.json" --meter-a "$ROOT/meter-a.txt" --meter-b "$ROOT/meter-b.txt" --record-a "$ROOT/record-a.jsonl" --record-b "$ROOT/record-b.jsonl"
has "the within-rubric split names artefact, dimension and rubric" "^third-judge: recommended for $A_LINT accuracy (lint: 7 vs 9)"
hasnt "the cross-rubric gap of 3 points recommends nothing" "third-judge: recommended for $B_LINT"
hasnt "and no split line is printed for it either" "^split: $B_LINT accuracy"

run 2 "score refuses both record forms at once" score --report "$ROOT/jl-1.md" --report "$ROOT/jl-2.md" --report "$ROOT/jq-1.md" --report "$ROOT/jq-2.md" --mapping "$ROOT/fx/mapping.json" --meter-a "$ROOT/meter-a.txt" --meter-b "$ROOT/meter-b.txt" --record-a "$ROOT/record-a.jsonl" --record-b "$ROOT/record-b.jsonl" \
  --record "$ROOT/record.jsonl"
has "the two record forms are named as alternatives" "are alternatives"

run 2 "score refuses a per-arm record with no gate event in it" score --report "$ROOT/jl-1.md" --report "$ROOT/jl-2.md" --report "$ROOT/jq-1.md" --report "$ROOT/jq-2.md" --mapping "$ROOT/fx/mapping.json" --meter-a "$ROOT/meter-a.txt" --meter-b "$ROOT/meter-b.txt" \
  --record-a "$ROOT/record-nogates.jsonl"
has "the empty record is named with its path and count" "record-nogates.jsonl carries 0 gate event(s) for arm a"

run 0 "score --help documents both record forms" score --help
has "the deprecated flag says so" "deprecated (design D37)"
has "the per-arm flags are documented" "arm a's own run record"
hasnt "the pre-D37 help string is gone (negative control)" "run record whose gate events carry the context figures"

# ---------------------------------------------------------------- 9 nothing written outside
manifest "$ROOT/vault" "$LINT" "$HERE" > "$ROOT/manifest-after.txt"
if cmp -s "$ROOT/manifest-before.txt" "$ROOT/manifest-after.txt"; then
  ok "the fixture vault and both shipped skill directories are byte-identical after the run"
else
  no "a file changed outside the --out roots"
fi
mb=$(wc -l < "$ROOT/manifest-before.txt" | tr -d ' ')
if [ "$mb" -gt 10 ]; then ok "the manifest control covers $mb files (nonzero, so the comparison means something)"; else no "the manifest covered $mb files — it proves nothing"; fi

writers=$(grep -c 'open(target, "w"' "$PY")
if [ "$writers" -eq 1 ]; then ok "parity.py has exactly one write site"; else no "parity.py has $writers write sites, wanted 1"; fi
WRITEPAT="open\([^)]*, *[\"']w|shutil|os\.remove|os\.rename|os\.unlink|rmtree"
strays=$(grep -c -E "$WRITEPAT" "$PY")
if [ "$strays" -eq 1 ]; then ok "no write pattern outside that one site"; else no "$strays write patterns in parity.py, wanted 1"; fi
selfctl=$(grep -c -E "$WRITEPAT" "$0")
if [ "$selfctl" -gt 0 ]; then ok "the write-pattern sweep hits $selfctl line(s) in this suite (positive control)"; else no "the write-pattern sweep found nothing anywhere — it is broken"; fi

# Change one byte in the very fixture just checked, without changing its permissions.
if python3 -B -c '
import sys
with open(sys.argv[1], "r+b") as fh:
    fh.write(b"!")
' "$ROOT/vault/wiki/index.md"; then
  if manifest "$ROOT/vault" "$LINT" "$HERE" > "$ROOT/manifest-control.txt" &&
     ! cmp -s "$ROOT/manifest-before.txt" "$ROOT/manifest-control.txt"; then
    ok "the manifest catches a one-byte change in the same folder under unchanged permissions"
  else
    no "the manifest missed the planted one-byte change"
  fi
else
  no "the manifest control could not change its fixture byte"
fi

# ---------------------------------------------------------------- result
total=$((pass + fail))
if [ "$fail" -eq 0 ]; then printf 'PASS %s/%s\n' "$pass" "$total"; else printf 'FAIL %s/%s\n' "$fail" "$total"; fi
if [ "$fail" -eq 0 ]; then exit 0; else exit 1; fi
