#!/bin/sh
# test_vault_writes.sh — regression suite for vault-writes.py (delegate skill, the vault
# writes a head composes by hand).
#
# Every fixture is a throwaway vault under one `mktemp -d`: a short log, a register with an
# Open and a Closed section, and an IDEAS file. The live vault is never named here and never
# touched: every path below hangs off $W (the temporary directory) or $HERE (this file own
# directory, read only). A leg that asserts a clean or empty result carries the planted case
# that proves the same probe fires, and the last group proves the script wrote nothing but
# the file it was pointed at.
#
# Run:  sh test_vault_writes.sh      (last line: PASS n/n or FAIL k/n; exit 0 only when clean)
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
S="$HERE/vault-writes.py"
PY="${PYTHON:-python3}"
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE
# A helper carries its write grants in LLM_WIKI_LANE_WRITES, and the writer then bounds every write by them.
# Every leg below runs as the lead, the variable absent, unless it sets the variable itself. The lead is
# also without the names lane.py sets beside it (LANE_MARKERS in the writer), since the variable absent
# beside any of them is a helper whose grants cannot be read; a run of this suite inside a helper
# therefore clears them too.
unset LLM_WIKI_LANE_WRITES LLM_WIKI_LANE LLM_WIKI_LANE_ID LLM_WIKI_LANE_GRANTS
PASS=0
FAIL=0
# Updated 2026-10-12 (Batch 10): `register add` requires --why-not-fixed-now, so every existing
# add below passes this text; it names no clock time and carries no backtick.
WN="a named blocker, written by the suite"
ok() { PASS=$((PASS + 1)); echo "  ok   — $1"; }
no() { FAIL=$((FAIL + 1)); echo "FAIL   — $1"; }
eq() { if [ "$2" = "$3" ]; then ok "$1"; else no "$1 (got '$2', want '$3')"; fi; }

W=$(mktemp -d)
OUT="$W/out.txt"
cleanup() { chmod -R u+w "$W" >/dev/null 2>&1; rm -rf "$W"; }
trap cleanup EXIT

[ -f "$S" ] || { echo "PROBE FAILED: no vault-writes.py at $S"; echo "FAIL 1/1"; exit 2; }
command -v "$PY" >/dev/null 2>&1 || { echo "PROBE FAILED: no $PY on PATH"; echo "FAIL 1/1"; exit 2; }

run() { "$@" >"$OUT" 2>&1; RC=$?; }
vw() { run "$PY" -B "$S" "$@"; }
has() { if grep -qF -- "$2" "$OUT"; then ok "$1"; else no "$1 (stdout lacks '$2')"; fi; }
hasnot() { if grep -qF -- "$2" "$OUT"; then no "$1 (stdout still holds '$2')"; else ok "$1"; fi; }
fhas() { if grep -qF -- "$3" "$2"; then ok "$1"; else no "$1 ($2 lacks '$3')"; fi; }
fhasnot() { if grep -qF -- "$3" "$2"; then no "$1 ($2 holds '$3')"; else ok "$1"; fi; }
nlines() { awk 'END { print NR }' "$1"; }
count() { grep -cF -- "$2" "$1" || true; }
fmatch() { if grep -Eq -- "$3" "$2"; then ok "$1"; else no "$1 ($2 holds no line matching /$3/)"; fi; }
fnomatch() { if grep -Eq -- "$3" "$2"; then no "$1 ($2 holds a line matching /$3/)"; else ok "$1"; fi; }

# The clock legs. Every stamp below is read from the same clock the script under test reads,
# so a leg that asserts an exact stamp reads the clock either side of the call and accepts
# both: the minute may tick between the two processes, and a leg that failed one time in
# sixty would be read as a defect. `eq2` is that pair.
eq2() {
	if [ "$2" = "$3" ] || [ "$2" = "$4" ]; then ok "$1"
	else no "$1 (got '$2', want '$3' or '$4')"; fi
}
now_hm() { "$PY" -B -c 'import time; print(time.strftime("%H:%M"))'; }
now_min() { "$PY" -B -c 'import time; print(time.localtime().tm_min)'; }
now_zone() { "$PY" -B -c 'import time; print(time.strftime("%Z") or time.strftime("%z"))'; }
# An hour that is neither the clock's own nor the hour before it, at any hour of the day:
# the planted token of every mismatch leg, computed at run time so the suite is stable at
# 23:5x as at 00:0x.
plant_hour() { "$PY" -B -c 'import time; print("%02d" % ((time.localtime().tm_hour + 3) % 24))'; }
prev_hour() { "$PY" -B -c 'import time; print("%02d" % ((time.localtime().tm_hour - 1) % 24))'; }
# A SECOND offending hour, distinct from plant_hour's, for the leg that needs two tokens at
# once. The primitive's tolerance is one hour wide and one-sided: `GRACE_MINUTES = 10`
# (vault-writes.py:127) with `if clock_minute < GRACE_MINUTES and token_hour == (clock_hour -
# 1) % HOURS: return False` (vault-writes.py:195), so only the offset -1 (i.e. +23) is ever
# forgiven, and only while the clock's minute is under ten. The arithmetic: an offset k is
# safe at every minute of the hour when k mod 24 is neither 0 (the clock's own hour) nor 23
# (the hour the grace forgives). plant_hour takes k=+3 and this takes k=+5: both are outside
# the tolerance at every minute, and the two differ, so the two tokens are distinct hours and
# the leg's two warning lines do not depend on the clock. (A `$(prev_hour):45` stamp would go
# silent whenever the run began at a minute under ten.)
other_hour() { "$PY" -B -c 'import time; print("%02d" % ((time.localtime().tm_hour + 5) % 24))'; }
# Streams kept apart: the warning is specified as a stderr line, and stdout stays the one
# line a head reads. $SOUT and $SERR hold them.
SOUT="$W/stdout.txt"
SERR="$W/stderr.txt"
vws() { "$PY" -B "$S" "$@" >"$SOUT" 2>"$SERR"; RC=$?; }

# The fixture: a vault root at $1/vault, an IDEAS file at $1/IDEAS.md.
fixture() {
	d="$1"
	rm -rf "$d"
	mkdir -p "$d/vault/wiki/developments"
	cat > "$d/vault/wiki/log.md" <<'LOG_END'
# Log

## [2026-09-01] lint | an older entry
- **Changed**: nothing at all
- **Conflicts**: none

LOG_END
	cat > "$d/vault/wiki/developments/known-issues.md" <<'REG_END'
# Known Issues

**Entry format** (append under `## Open`, newest first):

## Open

### [2026-09-05] alpha surface — the first one (minor)
- **Where observed**: run A · one path
- **Symptom**: it broke observably
- **Suspected cause**: inference, marked as such
- **Status**: open — fix shape: alpha

### [2026-09-04] beta surface — the middle one (medium)
- **Where observed**: run B · another path
- **Symptom**: it slipped
- **Severity**: medium (a false alarm only). **Status**: open — fix shape: beta

### [2026-09-03] gamma surface — no status bullet at all (minor)
- **Where observed**: run C
- **Symptom**: it stalled

### [2026-09-02] epsilon surface — the last open one (major)
- **Where observed**: run E
- **Symptom**: it doubled
- **Suspected cause**: confirmed: a doubled span
- **Status**: open — fix shape: epsilon

## Closed

### [2026-09-01] delta surface — closed long ago (minor)
- **Status**: closed 2026-09-01 — done

## Related

- nothing here
REG_END
	cat > "$d/IDEAS.md" <<'IDEAS_END'
# IDEAS

<!-- live items only (todo · idea · monitor); archived rows leave this table -->

- **№11** a short item
- **№119** the big one (D-0.9) *(agent 2026-09-03: numbered at maintenance)*
- **№1190** a decoy with a longer number
- **№7** the first twin
- **№7** the second twin
IDEAS_END
}

VAULT="$W/fix/vault"
LOG="$VAULT/wiki/log.md"
REG="$VAULT/wiki/developments/known-issues.md"
IDEAS="$W/fix/IDEAS.md"

fixture "$W/fix"
# Premise checks: a mangled fixture must not read as a clean run.
[ "$(count "$IDEAS" '- **№119**')" = "1" ] || { echo "PROBE FAILED: the fixture IDEAS file has no single №119 bullet (encoding?)"; echo "FAIL 1/1"; exit 2; }
[ "$(count "$REG" '## Open')" = "2" ] || { echo "PROBE FAILED: the fixture register does not carry its Open heading twice (heading + prose)"; echo "FAIL 1/1"; exit 2; }

echo "== log-append =="

cp "$LOG" "$W/log.before"
vw log-append --vault "$VAULT" --action framework --title "a title" --changed "one file" --conflicts "none" --date 2026-09-05
eq "L1 exit 0" "$RC" "0"
eq "L2 one line of output" "$(nlines "$OUT")" "1"
eq "L3 the ok line names the heading line" "$(cat "$OUT")" "ok log-append $LOG:7"
eq "L4 the heading landed on line 7" "$(awk 'NR==7' "$LOG")" "## [2026-09-05] framework | a title"
eq "L5 the Changed bullet follows it" "$(awk 'NR==8' "$LOG")" "- **Changed**: one file"
# Updated 2026-09-08: the Clock bullet the primitive stamps now sits between the two, so the
# Conflicts bullet moved from line 9 to line 10. Its own legs are the K group below.
fmatch "L6 the Clock bullet follows that" "$LOG" '^- \*\*Clock\*\*: [0-9]{2}:[0-9]{2} .+$'
eq "L6b the Conflicts bullet is last" "$(awk 'NR==10' "$LOG")" "- **Conflicts**: none"
eq "L7 exactly one blank line above the heading" "$(awk 'NR==6' "$LOG")" ""
head -c "$(wc -c < "$W/log.before" | awk '{print $1}')" "$LOG" > "$W/log.head"
if cmp -s "$W/log.before" "$W/log.head"; then ok "L8 every byte before the append is unchanged"; else no "L8 the append rewrote earlier bytes"; fi
printf 'x' >> "$W/log.head"
if cmp -s "$W/log.before" "$W/log.head"; then no "L8c the byte comparison cannot see a change"; else ok "L8c control: the same comparison catches a planted byte"; fi

fixture "$W/fix"
vw log-append --vault "$VAULT" --action synthesis --title "extras" --changed "c" --conflicts "none" --extra "Delegation: lane B3 (fable)" --extra "Meter: billed 1.00" --date 2026-09-05
eq "L9 exit 0 with two extras" "$RC" "0"
# Updated 2026-09-08: the Clock bullet leads the extras, so the caller's two moved down one
# line each and the entry is one line longer (was 9, 10, 11 and 12).
eq "L10 the first extra sits under the Clock bullet" "$(awk 'NR==10' "$LOG")" "- **Delegation**: lane B3 (fable)"
eq "L11 the second extra follows it" "$(awk 'NR==11' "$LOG")" "- **Meter**: billed 1.00"
eq "L12 Conflicts stays last" "$(awk 'NR==12' "$LOG")" "- **Conflicts**: none"
eq "L13 a blank line closes the entry" "$(awk 'END { print NR }' "$LOG")" "13"

fixture "$W/fix"
vw log-append --vault "$VAULT" --action reflect --title "t" --changed "c" --conflicts "none"
eq "L14 an unknown action is refused" "$RC" "2"
eq "L15 one error line only" "$(nlines "$OUT")" "1"
has "L16 it names the allowed set" "is none of: ingest gather synthesis"
vw log-append --vault "$VAULT" --action lint --title "$(printf 'two\nlines')" --changed "c" --conflicts "none"
eq "L17 a line break in a title is refused" "$RC" "2"
has "L18 it says why" "carries a line break"
vw log-append --vault "$VAULT" --action lint --title "t" --changed "   " --conflicts "none"
eq "L19 an empty --changed is refused" "$RC" "2"
has "L20 it names the argument" "--changed is empty"
vw log-append --vault "$VAULT" --action lint --title "t" --changed "c" --conflicts "none" --extra "no colon here"
eq "L21 an --extra without a colon is refused" "$RC" "2"
has "L22 it says what it wanted" "is not 'Key: value'"
vw log-append --vault "$VAULT" --action lint --title "t" --changed "c" --conflicts "none" --date 2026-13-40
eq "L23 an impossible date is refused" "$RC" "2"
has "L24 it names the date" "2026-13-40"
vw log-append --vault "$W/nowhere" --action lint --title "t" --changed "c" --conflicts "none"
eq "L25 a missing log file is refused" "$RC" "2"
has "L26 it names the path it wanted" "no file at $W/nowhere/wiki/log.md"

echo "== log-append: the blank-line separator =="

fixture "$W/fix"
printf '%s' "$(cat "$LOG")" > "$W/log.nonl"
cp "$W/log.nonl" "$LOG"
vw log-append --vault "$VAULT" --action lint --title "after a bare line" --changed "c" --conflicts "none" --date 2026-09-05
eq "L27 a log with no trailing newline still appends" "$RC" "0"
eq "L28 the reported line is the heading" "$(cat "$OUT")" "ok log-append $LOG:7"
eq "L29 the last old line is intact" "$(awk 'NR==5' "$LOG")" "- **Conflicts**: none"
eq "L30 exactly one blank line separates them" "$(awk 'NR==6' "$LOG")" ""
eq "L31 the heading is on the reported line" "$(awk 'NR==7' "$LOG")" "## [2026-09-05] lint | after a bare line"

fixture "$W/fix"
printf '%s\n' "$(cat "$LOG")" > "$W/log.onenl"
cp "$W/log.onenl" "$LOG"
vw log-append --vault "$VAULT" --action lint --title "after one newline" --changed "c" --conflicts "none" --date 2026-09-05
eq "L32 a log ending in a single newline appends" "$RC" "0"
eq "L33 one blank line is inserted, not two" "$(awk 'NR==6' "$LOG")" ""
eq "L34 the heading follows immediately" "$(awk 'NR==7' "$LOG")" "## [2026-09-05] lint | after one newline"

fixture "$W/fix"
cp "$LOG" "$W/log.dry"
vw log-append --vault "$VAULT" --action lint --title "dry" --changed "c" --conflicts "none" --date 2026-09-05 --dry-run
eq "L35 a dry run exits 0" "$RC" "0"
has "L36 it says dry-run and where the entry would land" "dry-run log-append $LOG:7"
has "L37 it shows the heading it would write" "| ## [2026-09-05] lint | dry"
if cmp -s "$W/log.dry" "$LOG"; then ok "L38 the dry run wrote nothing"; else no "L38 the dry run changed the log"; fi

echo "== register add =="

# SURFACE_TAG_TESTS_BEGIN
# The rejected calls are real writes against a read-only fixture, not just dry runs.
# All severity tags are covered; an ordinary parenthesis and an inner tag remain valid.
python3 -B - "$S" "$W" > "$W/surface-tags.txt" 2>&1 <<'PY_SURFACE_TAGS'
from datetime import date
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

script = Path(sys.argv[1])
passed = failed = 0


def check(label, good):
    global passed, failed
    if good:
        passed += 1
        print("ok " + label)
    else:
        failed += 1
        print("FAIL " + label)


def manifest(root):
    return [(str(p.relative_to(root)), p.stat().st_mtime_ns,
             hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "directory")
            for p in [root, *sorted(root.rglob("*"))]]


with tempfile.TemporaryDirectory(prefix="surface-tags-", dir=sys.argv[2]) as tmp:
    root = Path(tmp)
    directory = root / "wiki/developments"
    directory.mkdir(parents=True)
    register = directory / "known-issues.md"
    register.write_text("# Issues\n\n## Open\n\n## Closed\n", encoding="utf-8")
    original = manifest(root)
    register.chmod(0o444)
    directory.chmod(0o555)
    try:
        tags = ["(" + tag + ")" for tag in ("blocking", "major", "medium", "minor")]
        tags += ["(Minor)", "(MAJOR)", "( minor )", "(minor).",
                 "(blocking · major · minor)", "( BLOCKING · MAJOR · MINOR )."]
        for tag in tags:
            for tail, dry in (("", []), ("  ", ["--dry-run"])):
                r = subprocess.run([sys.executable, "-B", str(script), "register", "add", "--vault", str(root),
                    "--date", date.today().isoformat(),
                    "--surface", "fixture " + tag + tail, "--severity", "minor",
                    "--symptom", "fixture symptom", "--cause", "fixture cause", "--status", "open",
                    "--why-not-fixed-now", "fixture blocker", *dry], capture_output=True, text=True)
                check("ST1 %s%s refuses with one line naming its tag, writing nothing" % (tag, " dry" if dry else ""),
                      r.returncode == 2 and len(r.stdout.splitlines()) == 1 and not r.stderr
                      and "--surface" in r.stdout and tag.rstrip(".") in r.stdout
                      and "nothing written" in r.stdout and manifest(root) == original)
    finally:
        directory.chmod(0o755)
        register.chmod(0o644)
    for surface in ("lane.py (fallback)", "fixture (minor) followed by details",
                    "fixture (Minor). followed by details", "fixture (blocking · major · minor) followed by details"):
        r = subprocess.run([sys.executable, "-B", str(script), "register", "add", "--vault", str(root),
            "--date", date.today().isoformat(),
            "--surface", surface, "--severity", "minor", "--symptom", "fixture symptom",
            "--cause", "fixture cause", "--status", "open", "--why-not-fixed-now", "fixture blocker"],
            capture_output=True, text=True)
        check("ST2 allowed parenthesis: " + surface,
              r.returncode == 0 and len(r.stdout.splitlines()) == 1 and not r.stderr
              and surface + " (minor)" in register.read_text(encoding="utf-8"))
    check("ST3 manifest control detects the allowed writes", manifest(root) != original)
print("PASS %d/%d" % (passed, passed + failed) if not failed else "FAIL %d/%d" % (failed, passed + failed))
raise SystemExit(1 if failed else 0)
PY_SURFACE_TAGS
surface_rc=$?
if [ "$surface_rc" -gt 1 ]; then cat "$W/surface-tags.txt"; echo 'PROBE FAILED: surface-tag fixtures did not finish'; exit 2; fi
while IFS= read -r result; do
  case "$result" in
    'ok '*) ok "${result#ok }" ;;
    'FAIL '*/*|'PASS '*/*) : ;;
    'FAIL '*) no "${result#FAIL }" ;;
    *) cat "$W/surface-tags.txt"; echo 'PROBE FAILED: unexpected surface-tag output'; exit 2 ;;
  esac
done < "$W/surface-tags.txt"
# SURFACE_TAG_TESTS_END

fixture "$W/fix"
cp "$REG" "$W/reg.before"
T0=$(now_hm)
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "zeta surface — a new one" --symptom "it refused" --cause "inference: a guess" --severity minor --status "open — fix shape: zeta" --where "run Z · one path"
T1=$(now_hm)
eq "R1 exit 0" "$RC" "0"
eq "R2 one line of output" "$(nlines "$OUT")" "1"
eq "R3 the ok line names the heading line" "$(cat "$OUT")" "ok register-add $REG:7"
# Updated 2026-09-08: the heading carries the clock's time beside the caller's date.
eq2 "R4 the heading carries date, time, surface and severity" "$(awk 'NR==7' "$REG")" "### [2026-09-05 $T0] zeta surface — a new one (minor)" "### [2026-09-05 $T1] zeta surface — a new one (minor)"
eq "R5 Where observed" "$(awk 'NR==8' "$REG")" "- **Where observed**: run Z · one path"
eq "R6 Symptom" "$(awk 'NR==9' "$REG")" "- **Symptom**: it refused"
eq "R7 Suspected cause" "$(awk 'NR==10' "$REG")" "- **Suspected cause**: inference: a guess"
# Updated 2026-10-12 (Batch 10): the Why not fixed now bullet now sits on line 11, between
# Suspected cause and Status (its own leg is W3b below), so Status moved from line 11 to 12, the
# blank line from 12 to 13, the old first entry from 13 to 14, and R12's window grew by a line.
eq "R8 Status verbatim" "$(awk 'NR==12' "$REG")" "- **Status**: open — fix shape: zeta"
eq "R9 one blank line under the new entry" "$(awk 'NR==13' "$REG")" ""
eq "R10 the old first entry follows it" "$(awk 'NR==14' "$REG")" "### [2026-09-05] alpha surface — the first one (minor)"
eq "R11 the Open heading still has its blank line" "$(awk 'NR==6' "$REG")" ""
awk 'NR<7 || NR>13' "$REG" > "$W/reg.rest"
if cmp -s "$W/reg.before" "$W/reg.rest"; then ok "R12 every other byte of the register is unchanged"; else no "R12 the insert disturbed the rest of the file"; fi
awk 'NR!=13' "$W/reg.before" > "$W/reg.mangled"
if cmp -s "$W/reg.mangled" "$W/reg.rest"; then no "R12c the comparison cannot see a dropped line"; else ok "R12c control: the same comparison catches a dropped line"; fi
eq "R13 no temp file is left beside the target" "$(ls -a "$VAULT/wiki/developments" | grep -c 'vault-writes' || true)" "0"

fixture "$W/fix"
T0=$(now_hm)
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "eta surface — no where" --symptom "s" --cause "c" --severity blocking --status "open — fix shape: eta"
T1=$(now_hm)
eq "R14 blocking is accepted as a severity" "$RC" "0"
eq "R15 the Where bullet is omitted, not invented" "$(awk 'NR==8' "$REG")" "- **Symptom**: s"
# Updated 2026-09-08: the stamped heading shape.
eq2 "R16 the heading carries blocking" "$(awk 'NR==7' "$REG")" "### [2026-09-05 $T0] eta surface — no where (blocking)" "### [2026-09-05 $T1] eta surface — no where (blocking)"

fixture "$W/fix"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "s" --symptom "s" --cause "c" --severity critical --status "open"
eq "R17 an unknown severity is refused" "$RC" "2"
has "R18 it names the allowed set" "is none of: blocking major medium minor"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "$(printf 'two\nlines')" --symptom "s" --cause "c" --severity minor --status "open"
eq "R19 a line break in the surface is refused" "$RC" "2"
has "R20 it says why" "carries a line break"

fixture "$W/fix"
cp "$REG" "$W/reg.dry"
T0=$(now_hm)
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "theta" --symptom "s" --cause "c" --severity minor --status "open" --dry-run
T1=$(now_hm)
eq "R21 a dry run exits 0" "$RC" "0"
# Updated 2026-09-08: a dry run shows the stamp the write would carry, not a bare date.
if grep -qF -- "| ### [2026-09-05 $T0] theta (minor)" "$OUT" || grep -qF -- "| ### [2026-09-05 $T1] theta (minor)" "$OUT"
then ok "R22 it shows the stamped heading it would write"
else no "R22 it shows the stamped heading it would write (got '$(cat "$OUT")')"; fi
if cmp -s "$W/reg.dry" "$REG"; then ok "R23 the dry run wrote nothing"; else no "R23 the dry run changed the register"; fi

echo "== register: the section anchors =="

fixture "$W/fix"
printf '\n## Open\n' >> "$REG"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "s" --symptom "s" --cause "c" --severity minor --status "open"
eq "R24 a second Open heading is refused" "$RC" "2"
has "R25 it names the count it found" "'## Open' is 2 lines of the register, not 1"

fixture "$W/fix"
awk '$0 != "## Closed"' "$REG" > "$W/reg.noclosed"
cp "$W/reg.noclosed" "$REG"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "s" --symptom "s" --cause "c" --severity minor --status "open"
eq "R26 a missing Closed heading is refused" "$RC" "2"
has "R27 it names the count it found" "'## Closed' is 0 lines of the register, not 1"

fixture "$W/fix"
printf '# Inverted\n\n## Closed\n\n### [2026-09-01] delta surface — closed (minor)\n- **Status**: closed\n\n## Open\n\n### [2026-09-05] alpha surface — first (minor)\n- **Status**: open\n' > "$REG"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "s" --symptom "s" --cause "c" --severity minor --status "open"
eq "R28 Closed above Open is refused" "$RC" "2"
has "R29 it names both lines" "'## Closed' (line 3) sits above '## Open' (line 8)"

echo "== register close =="

fixture "$W/fix"
BEFORE_LINES=$(nlines "$REG")
T0=$(now_hm)
vw register close --vault "$VAULT" --match "beta surface" --date 2026-09-05 --status "closed by the suite"
T1=$(now_hm)
eq "C1 exit 0" "$RC" "0"
eq "C2 one line of output" "$(nlines "$OUT")" "1"
eq "C3 the ok line names the new position" "$(cat "$OUT")" "ok register-close $REG:25"
eq "C4 the entry now heads the Closed section" "$(awk 'NR==25' "$REG")" "### [2026-09-04] beta surface — the middle one (medium)"
eq "C5 its bullets moved with it, byte for byte" "$(awk 'NR==26' "$REG")" "- **Where observed**: run B · another path"
# Updated 2026-09-08: the status fact inside the dated suffix now opens with the clock stamp
# `closed DATE HH:MM — ` (the caller's text carried no date of its own).
eq2 "C6 the combined Severity and Status line is dated and stamped in place" "$(awk 'NR==28' "$REG")" "- **Severity**: medium (a false alarm only). **Status**: open — fix shape: beta *(2026-09-05: closed 2026-09-05 $T0 — closed by the suite)*" "- **Severity**: medium (a false alarm only). **Status**: open — fix shape: beta *(2026-09-05: closed 2026-09-05 $T1 — closed by the suite)*"
eq "C7 the old Closed entry follows it" "$(awk 'NR==30' "$REG")" "### [2026-09-01] delta surface — closed long ago (minor)"
eq "C8 the heading exists exactly once in the file" "$(count "$REG" 'beta surface — the middle one')" "1"
eq "C9 the entry is gone from the Open section" "$(awk 'NR>=5 && NR<23' "$REG" | grep -cF 'beta surface' || true)" "0"
eq "C10 the file neither grew nor shrank" "$(nlines "$REG")" "$BEFORE_LINES"
eq "C11 gamma still sits under Open" "$(awk 'NR==13' "$REG")" "### [2026-09-03] gamma surface — no status bullet at all (minor)"
eq "C12 the Related section is untouched" "$(awk 'NR==35' "$REG")" "- nothing here"

fixture "$W/fix"
T0=$(now_hm)
vw register close --vault "$VAULT" --match "epsilon surface" --date 2026-09-05 --status "closed last"
T1=$(now_hm)
eq "C13 the last Open entry closes too" "$RC" "0"
eq "C14 it lands at the top of Closed" "$(cat "$OUT")" "ok register-close $REG:24"
eq "C15 the Closed heading is intact above it" "$(awk 'NR==22' "$REG")" "## Closed"
# Updated 2026-09-08: the stamped status fact inside the dated suffix.
eq2 "C16 its Status bullet carries the dated, stamped suffix" "$(awk 'NR==28' "$REG")" "- **Status**: open — fix shape: epsilon *(2026-09-05: closed 2026-09-05 $T0 — closed last)*" "- **Status**: open — fix shape: epsilon *(2026-09-05: closed 2026-09-05 $T1 — closed last)*"
eq "C17 the file neither grew nor shrank" "$(nlines "$REG")" "35"

fixture "$W/fix"
vw register close --vault "$VAULT" --match "no such entry" --date 2026-09-05 --status "x"
eq "C18 no match is refused" "$RC" "2"
has "C19 it names the count" "matches 0 entry headings under '## Open', not 1"
vw register close --vault "$VAULT" --match "surface" --date 2026-09-05 --status "x"
eq "C20 an ambiguous match is refused" "$RC" "2"
has "C21 it names the count" "matches 4 entry headings under '## Open', not 1"
vw register close --vault "$VAULT" --match "delta surface" --date 2026-09-05 --status "x"
eq "C22 an entry that is already closed is not found under Open" "$RC" "2"
has "C23 it names the count" "matches 0 entry headings"
vw register close --vault "$VAULT" --match "gamma surface" --date 2026-09-05 --status "x"
eq "C24 an entry with no Status bullet is refused" "$RC" "2"
has "C25 it names what it could not find" "carries 0 '**Status**' lines, not 1"

fixture "$W/fix"
cp "$REG" "$W/reg.dryclose"
vw register close --vault "$VAULT" --match "beta surface" --date 2026-09-05 --status "x" --dry-run
eq "C26 a dry run exits 0" "$RC" "0"
has "C27 it shows the entry it would move" "dry-run register-close $REG:25"
has "C28 it says how much moves" "| moved 4 lines to the top of '## Closed'"
if cmp -s "$W/reg.dryclose" "$REG"; then ok "C29 the dry run wrote nothing"; else no "C29 the dry run changed the register"; fi

echo "== ideas annotate =="

fixture "$W/fix"
cp "$IDEAS" "$W/ideas.before"
T0=$(now_hm)
vw ideas annotate --file "$IDEAS" --item 119 --note "hands-off primitives shipped" --date 2026-09-05
T1=$(now_hm)
eq "I1 exit 0" "$RC" "0"
eq "I2 one line of output" "$(nlines "$OUT")" "1"
eq "I3 the ok line names the bullet line" "$(cat "$OUT")" "ok ideas-annotate $IDEAS:6"
# Updated 2026-09-08: the note prefix is `*(agent DATE HH:MM: …)*`; every other rule of the
# shape (appended after the existing note, italic parentheses, one line) is unchanged, and
# the older note already on the bullet keeps its own dateless form.
eq2 "I4 the stamped note is appended after the existing one" "$(awk 'NR==6' "$IDEAS")" "- **№119** the big one (D-0.9) *(agent 2026-09-03: numbered at maintenance)* *(agent 2026-09-05 $T0: hands-off primitives shipped)*" "- **№119** the big one (D-0.9) *(agent 2026-09-03: numbered at maintenance)* *(agent 2026-09-05 $T1: hands-off primitives shipped)*"
awk 'NR!=6' "$IDEAS" > "$W/ideas.rest"
awk 'NR!=6' "$W/ideas.before" > "$W/ideas.restbefore"
if cmp -s "$W/ideas.restbefore" "$W/ideas.rest"; then ok "I5 no other line changed"; else no "I5 another line changed"; fi
eq "I6 the shorter neighbour is untouched" "$(awk 'NR==5' "$IDEAS")" "- **№11** a short item"
eq "I7 the longer neighbour is untouched" "$(awk 'NR==7' "$IDEAS")" "- **№1190** a decoy with a longer number"
# Updated 2026-09-08: the marker counted is the stamped prefix, so the leg still counts one
# note and would now miss an unstamped one.
eq "I8 exactly one stamped agent note was added" "$(count "$IDEAS" '(agent 2026-09-05 ')" "1"
eq "I8b and no unstamped one" "$(count "$IDEAS" '(agent 2026-09-05:')" "0"
eq "I8c control: the same probe counts the fixture's own dateless note" "$(count "$IDEAS" '(agent 2026-09-03:')" "1"

fixture "$W/fix"
vw ideas annotate --file "$IDEAS" --item 999 --note "n" --date 2026-09-05
eq "I9 an item that is not there is refused" "$RC" "2"
has "I10 it names the marker and the count" "begins 0 lines of"
vw ideas annotate --file "$IDEAS" --item 7 --note "n" --date 2026-09-05
eq "I11 a doubled item is refused" "$RC" "2"
has "I12 it names the count" "begins 2 lines of"
vw ideas annotate --file "$IDEAS" --item 11a --note "n"
eq "I13 an item that is not a number is refused" "$RC" "2"
has "I14 it says so" "is not a number"
vw ideas annotate --file "$W/no-such-ideas.md" --item 119 --note "n"
eq "I15 a missing file is refused" "$RC" "2"
has "I16 it names the path" "no file at $W/no-such-ideas.md"
vw ideas annotate --file "$IDEAS" --item 119 --note "$(printf 'two\nlines')"
eq "I17 a line break in the note is refused" "$RC" "2"
has "I18 it says why" "carries a line break"

fixture "$W/fix"
cp "$IDEAS" "$W/ideas.dry"
vw ideas annotate --file "$IDEAS" --item 119 --note "n" --date 2026-09-05 --dry-run
eq "I19 a dry run exits 0" "$RC" "0"
has "I20 it shows the line it would write" "dry-run ideas-annotate $IDEAS:6"
if cmp -s "$W/ideas.dry" "$IDEAS"; then ok "I21 the dry run wrote nothing"; else no "I21 the dry run changed the file"; fi

echo "== the clock: log-append =="

fixture "$W/fix"
Z=$(now_zone)
T0=$(now_hm)
vws log-append --vault "$VAULT" --action framework --title "clocked" --changed "c" --conflicts "none" --date 2026-09-05
T1=$(now_hm)
eq "K1 exit 0" "$RC" "0"
fmatch "K2 the heading keeps its schema shape, with no time inside it" "$LOG" '^## \[2026-09-05\] framework \| clocked$'
eq2 "K3 the Clock bullet carries the clock's time and its own zone" "$(awk 'NR==9' "$LOG")" "- **Clock**: $T0 $Z" "- **Clock**: $T1 $Z"
eq "K4 it sits between Changed and Conflicts" "$(awk 'NR==8 || NR==10' "$LOG" | tr '\n' '|')" "- **Changed**: c|- **Conflicts**: none|"
eq "K5 exactly one Clock bullet in the entry" "$(count "$LOG" '- **Clock**: ')" "1"
eq "K6 a text naming no time warns about nothing" "$(nlines "$SERR")" "0"

fixture "$W/fix"
PLANT="$(plant_hour):3x"
T0=$(now_hm)
vws log-append --vault "$VAULT" --action framework --title "written at $PLANT" --changed "c" --conflicts "none" --date 2026-09-05
T1=$(now_hm)
eq "K7 control: the same stderr probe catches a planted mismatch" "$(nlines "$SERR")" "1"
eq2 "K8 the warning names the token and the clock's reading" "$(cat "$SERR")" "clock: the note names $PLANT, the clock reads $T0" "clock: the note names $PLANT, the clock reads $T1"
eq "K9 a warning is not a refusal" "$RC" "0"
eq "K10 stdout still carries the one line a head reads" "$(nlines "$SOUT")" "1"
fhas "K11 and it is the ok line" "$SOUT" "ok log-append $LOG:7"
eq "K12 the write proceeded" "$(count "$LOG" "| written at $PLANT")" "1"

fixture "$W/fix"
PLANT="$(plant_hour):3x"
vws log-append --vault "$VAULT" --action framework --title "t" --changed "again at $PLANT" --conflicts "and at $PLANT" --extra "Meter: $PLANT" --date 2026-09-05
eq "K13 one token in three arguments earns one line, not three" "$(nlines "$SERR")" "1"
PLANT2="$(other_hour):45"
vws log-append --vault "$VAULT" --action framework --title "t" --changed "at $PLANT" --conflicts "c" --extra "Meter: $PLANT2" --date 2026-09-05
eq "K14 two distinct offending tokens earn two lines" "$(nlines "$SERR")" "2"
# K14's own premise: the two planted tokens really are two distinct hours, so a leg reading
# two lines is reading one line each and not one token twice. K13 above is the control for
# the other direction — one token in three arguments reads one line.
if [ "${PLANT%%:*}" != "${PLANT2%%:*}" ]; then
	ok "K14b the two planted tokens name different hours ($PLANT and $PLANT2)"
else
	no "K14b the two planted tokens name the same hour ($PLANT and $PLANT2)"
fi

fixture "$W/fix"
cp "$LOG" "$W/log.clockdry"
PLANT="$(plant_hour):3x"
T0=$(now_hm)
vws log-append --vault "$VAULT" --action framework --title "dry at $PLANT" --changed "c" --conflicts "none" --date 2026-09-05 --dry-run
T1=$(now_hm)
eq "K15 a dry run warns the same way" "$(nlines "$SERR")" "1"
if grep -qF -- "| - **Clock**: $T0 $Z" "$SOUT" || grep -qF -- "| - **Clock**: $T1 $Z" "$SOUT"
then ok "K16 and shows the stamp the write would carry"
else no "K16 and shows the stamp the write would carry (got '$(cat "$SOUT")')"; fi
if cmp -s "$W/log.clockdry" "$LOG"; then ok "K17 the warned dry run wrote nothing"; else no "K17 the warned dry run changed the log"; fi

echo "== the clock: register add =="

fixture "$W/fix"
PLANT="$(plant_hour):3x"
T0=$(now_hm)
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "kappa surface — a timed one" --symptom "seen at $PLANT" --cause "c" --severity minor --status "open — since $PLANT" --where "run K"
T1=$(now_hm)
eq "K18 exit 0" "$RC" "0"
fmatch "K19 the heading carries the date and a clock time" "$REG" '^### \[2026-09-05 [0-9]{2}:[0-9]{2}\] kappa surface — a timed one \(minor\)$'
eq2 "K20 the time is the clock's own" "$(awk 'NR==7' "$REG")" "### [2026-09-05 $T0] kappa surface — a timed one (minor)" "### [2026-09-05 $T1] kappa surface — a timed one (minor)"
eq "K21 the token repeated in two arguments earns one warning" "$(nlines "$SERR")" "1"
eq "K22 stdout is still one line" "$(nlines "$SOUT")" "1"

fixture "$W/fix"
NOW=$(now_hm)
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "lambda surface" --symptom "seen at $NOW" --cause "c" --severity minor --status "open — x" --where "and again at $NOW"
eq "K23 a token at the clock's own reading is silent" "$(nlines "$SERR")" "0"
eq "K24 the entry was still written" "$RC" "0"
PLANT="$(plant_hour):3x"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "mu surface" --symptom "seen at $PLANT" --cause "c" --severity minor --status "open — x"
eq "K25 control: the same silence probe fires on a planted hour" "$(nlines "$SERR")" "1"

fixture "$W/fix"
cp "$REG" "$W/reg.clockdry"
PLANT="$(plant_hour):3x"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "nu surface" --symptom "at $PLANT" --cause "c" --severity minor --status "open — x" --dry-run
eq "K26 a dry run warns" "$(nlines "$SERR")" "1"
fmatch "K27 and shows the stamped heading" "$SOUT" '^\| ### \[2026-09-05 [0-9]{2}:[0-9]{2}\] nu surface \(minor\)$'
if cmp -s "$W/reg.clockdry" "$REG"; then ok "K28 the warned dry run wrote nothing"; else no "K28 the warned dry run changed the register"; fi

echo "== the clock: register close =="

fixture "$W/fix"
T0=$(now_hm)
vws register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "the fix shipped"
T1=$(now_hm)
eq "K29 an old-shape heading still closes by --match" "$RC" "0"
eq2 "K30 a status with no date of its own takes the whole stamp" "$(grep -F -- 'fix shape: alpha' "$REG")" "- **Status**: open — fix shape: alpha *(2026-09-05: closed 2026-09-05 $T0 — the fix shipped)*" "- **Status**: open — fix shape: alpha *(2026-09-05: closed 2026-09-05 $T1 — the fix shipped)*"
eq "K31 no second 'closed' was introduced" "$(count "$REG" 'closed closed')" "0"
eq "K31c control: the same probe sees a planted doubling" "$(printf 'closed closed 2026-09-05\n' | grep -cF 'closed closed')" "1"

fixture "$W/fix"
T0=$(now_hm)
vws register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed 2026-09-05 — the fix shipped"
T1=$(now_hm)
eq2 "K32 a status already opening 'closed DATE' takes the time after that date" "$(grep -F -- 'fix shape: alpha' "$REG")" "- **Status**: open — fix shape: alpha *(2026-09-05: closed 2026-09-05 $T0 — the fix shipped)*" "- **Status**: open — fix shape: alpha *(2026-09-05: closed 2026-09-05 $T1 — the fix shipped)*"
eq "K33 the caller's own 'closed' is not repeated" "$(count "$REG" 'closed 2026-09-05')" "1"

fixture "$W/fix"
PLANT="$(plant_hour):3x"
vws register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed 2026-09-05 $PLANT — the fix shipped"
eq "K34 a status already carrying a time keeps it, byte for byte" "$(count "$REG" "closed 2026-09-05 $PLANT — the fix shipped")" "1"
eq "K35 and the disagreeing hour is what the warning says" "$(nlines "$SERR")" "1"
fhas "K36 the warning names that token" "$SERR" "clock: the note names $PLANT,"

fixture "$W/fix"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "xi surface — added timed" --symptom "s" --cause "c" --severity minor --status "open — x"
eq "K37 the entry to close is written with the new heading shape" "$RC" "0"
fmatch "K37b its heading carries a time" "$REG" '^### \[2026-09-05 [0-9]{2}:[0-9]{2}\] xi surface — added timed \(minor\)$'
vws register close --vault "$VAULT" --match "xi surface" --date 2026-09-05 --status "done"
eq "K38 --match finds a heading of the new shape too" "$RC" "0"
fhas "K39 the closed entry sits under the Closed heading" "$SOUT" "ok register-close $REG:"
eq "K40 it left the Open section" "$(awk '/^## Open/, /^## Closed/' "$REG" | grep -cF 'xi surface' || true)" "0"
eq "K40c control: the same window probe still sees an entry that stayed open" "$(awk '/^## Open/, /^## Closed/' "$REG" | grep -cF 'gamma surface' || true)" "1"

fixture "$W/fix"
cp "$REG" "$W/reg.closedry"
PLANT="$(plant_hour):3x"
vws register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed at $PLANT" --dry-run
eq "K41 a dry run warns" "$(nlines "$SERR")" "1"
fmatch "K42 and shows the stamped status fact" "$SOUT" '^\| - \*\*Status\*\*: open — fix shape: alpha \*\(2026-09-05: closed 2026-09-05 [0-9]{2}:[0-9]{2} — closed at '"$PLANT"'\)\*$'
if cmp -s "$W/reg.closedry" "$REG"; then ok "K43 the warned dry run wrote nothing"; else no "K43 the warned dry run changed the register"; fi

echo "== the clock: ideas annotate =="

fixture "$W/fix"
T0=$(now_hm)
vws ideas annotate --file "$IDEAS" --item 11 --note "a plain note" --date 2026-09-05
T1=$(now_hm)
eq "K44 exit 0" "$RC" "0"
fmatch "K45 the note prefix carries the date and the clock's time" "$IDEAS" '^- \*\*№11\*\* a short item \*\(agent 2026-09-05 [0-9]{2}:[0-9]{2}: a plain note\)\*$'
eq2 "K46 the time is the clock's own" "$(awk 'NR==5' "$IDEAS")" "- **№11** a short item *(agent 2026-09-05 $T0: a plain note)*" "- **№11** a short item *(agent 2026-09-05 $T1: a plain note)*"
eq "K47 the note names no time of its own, so nothing is warned" "$(nlines "$SERR")" "0"
PLANT="$(plant_hour):3x"
vws ideas annotate --file "$IDEAS" --item 119 --note "a note about $PLANT" --date 2026-09-05
eq "K48 control: the same silence probe fires on a planted hour" "$(nlines "$SERR")" "1"
eq "K49 the note was written all the same" "$(count "$IDEAS" "a note about $PLANT")" "1"
eq "K50 stdout is still one line" "$(nlines "$SOUT")" "1"

fixture "$W/fix"
cp "$IDEAS" "$W/ideas.clockdry"
PLANT="$(plant_hour):3x"
vws ideas annotate --file "$IDEAS" --item 11 --note "dry at $PLANT" --date 2026-09-05 --dry-run
eq "K51 a dry run warns" "$(nlines "$SERR")" "1"
fmatch "K52 and shows the stamped line" "$SOUT" '\| - \*\*№11\*\* a short item \*\(agent 2026-09-05 [0-9]{2}:[0-9]{2}: dry at '"$PLANT"'\)\*'
if cmp -s "$W/ideas.clockdry" "$IDEAS"; then ok "K53 the warned dry run wrote nothing"; else no "K53 the warned dry run changed the file"; fi

echo "== the clock: the token and the grace =="

# The wall clock cannot be moved, so the two rules that depend on it are exercised through
# the module's own functions with the clock passed in. Each string below carries its own
# positive control: the same probe that returns 0 for a case it must pass returns 1 for one
# it must catch, in the same run.
TOKENS=$("$PY" -B -c '
import importlib.util, sys, time
spec = importlib.util.spec_from_file_location("vwmod", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
now = time.struct_time((2026, 9, 8, 9, 30, 0, 0, 0, -1))   # 09:30, mid-hour
print(",".join(mod.clock_tokens(now, [
    "twice at 21:3x and again 21:3x",   # caught once: the rounded Mx form, deduplicated
    "at 19:52:29 exactly",              # caught once: 19:52, and 52:29 is not a second token
    "at 08:07 this morning",            # caught: a zero-padded morning hour
    "at 8:07 this morning",             # silent since 2026-09-13: a one-digit hour (K58-K60)
    "at 09:30 now", "at 09:05 too",     # silent: the clock own hour
    "PASS 139/139", "1300 hours",       # silent: no token at all
    "at 25:00", "x09:30x",              # silent: not an hour, and not a token in a word
])))
' "$S")
# Updated 2026-09-13: the hour is anchored on two digits (K58-K60), so `8:07` is silent;
# `08:07` now carries the morning case, and the own-hour and in-a-word cases are zero-padded so
# each stays silent for its own reason rather than for the one-digit rule.
eq "K54 the token regex catches what it must and skips what it must not" "$TOKENS" "21:3x,19:52,08:07"

GRACE=$("$PY" -B -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("vwmod", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
cases = [(9, 9, 30), (8, 9, 5), (8, 9, 9), (8, 9, 10), (8, 9, 30),
         (23, 0, 5), (23, 0, 30), (12, 9, 5)]
print("".join("1" if mod.hour_disagrees(t, h, m) else "0" for t, h, m in cases))
' "$S")
# clock hour · previous hour at minute 5 and 9 · previous hour at minute 10 and 30 · the
# midnight wrap either side of the grace · an unrelated hour inside the grace.
eq "K55 the ten-minute grace, hour by hour" "$GRACE" "00011011"
eq "K56 the grace bound is the constant the file documents" "$("$PY" -B -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("vwmod", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(mod.GRACE_MINUTES)
' "$S")" "10"

fixture "$W/fix"
# The live clock against the grace: under minute ten the previous hour passes, at or past it
# the same token is warned. Reading the minute either side of the call keeps the leg honest
# when the minute turns during it.
M0=$(now_min)
PREV="$(prev_hour):45"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "omicron surface" --symptom "an event at $PREV" --cause "c" --severity minor --status "open — x"
M1=$(now_min)
GOT=$(nlines "$SERR")
if [ "$M0" -lt 10 ] && [ "$M1" -lt 10 ]; then
	eq "K57 the previous hour is silent inside the grace (clock minute $M0)" "$GOT" "0"
elif [ "$M0" -ge 10 ] && [ "$M1" -ge 10 ]; then
	eq "K57 the previous hour is warned outside the grace (clock minute $M0)" "$GOT" "1"
else
	eq2 "K57 the grace boundary turned during the call (minute $M0 to $M1)" "$GOT" "0" "1"
fi

echo "== the clock: a meter's model count is not a clock (2026-09-13) =="

# The register entry of 2026-09-09 15:27: a Mechanism bullet carrying a meter's model count
# `claude-opus-5:88` must not print `clock: the note names 5:88`. K58 replays such a meter
# segment; K59 is its control on the same text, a real wrong clock beside it.
fixture "$W/fix"
METER_TEXT='fable share: head 12,345 out · lanes 23,456 out (claude-opus-5:88) · share 34.5%; billed (list) head $1.23 · lanes $2.34 · session $3.57'
vws log-append --vault "$VAULT" --action ingest --title "model count" --changed "c" --conflicts "none" --extra "Mechanism: $METER_TEXT" --date 2026-09-05
eq "K58 the meter's model count claude-opus-5:88 warns about nothing" "$(nlines "$SERR")" "0"
eq "K58b and the entry was written" "$(count "$LOG" "(claude-opus-5:88)")" "1"
PLANT="$(plant_hour):3x"
vws log-append --vault "$VAULT" --action ingest --title "model count" --changed "written at $PLANT" --conflicts "none" --extra "Mechanism: $METER_TEXT" --date 2026-09-05
eq "K59 control: a real wrong clock beside the same meter text still warns, once" "$(nlines "$SERR")" "1"
fhas "K59b and the warning names the clock, not the model count" "$SERR" "clock: the note names $PLANT,"

# K60 — the meter's other line shapes, through the module with the clock passed in (09:30, an
# hour every token below disagrees with, so a silent one is silent on its shape alone). K60c
# runs the same silent list through the pattern shipped until 2026-09-13: it must catch some,
# or K60 proves nothing.
SHAPES=$("$PY" -B -c '
import importlib.util, re, sys, time
spec = importlib.util.spec_from_file_location("vwmod", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
now = time.struct_time((2026, 9, 8, 9, 30, 0, 0, 0, -1))
silent = [
    "lanes 123,456 out (claude-opus-5:88)",                   # a meter model count
    "(<synthetic>:4, claude-fable-5-1:35, claude-opus-5:956)", # counts on three id shapes
    "tool uses/call head 1.87 lanes 1.37",                    # ratios carry no colon
    "models opus-15:30, gpt-5.10:12 · efforts high:12, max:20",
    "window: 2026-09-10T12:00:00+01:00 -> 2026-09-10T13:44:05-05:00",
    "at 5:88 and 7:30",                                       # one-digit hours, a minute over 59
    "rewrites 3 ($23.08) · picks: verifier m a9 r0 l0 · e a9 r0 l0",
]
caught = ["at 22:58-23:04 BST", "(13:44)", "at 21:3x"]
old = re.compile(r"(?<![0-9A-Za-z:])([0-9]{1,2}):([0-9][0-9x])(?![0-9A-Za-z])")
print("silent=" + ",".join(mod.clock_tokens(now, silent)))
print("caught=" + ",".join(mod.clock_tokens(now, caught)))
print("old=%d" % sum(len(old.findall(text)) for text in silent))
' "$S")
eq "K60 every meter line shape names no clock token" "$(printf '%s\n' "$SHAPES" | sed -n 's/^silent=//p')" ""
eq "K60b control: the same call catches both ends of a range, a bracketed time and a rounded one" "$(printf '%s\n' "$SHAPES" | sed -n 's/^caught=//p')" "22:58,23:04,13:44,21:3x"
eq "K60c control: the pattern shipped until 2026-09-13 reads 8 clocks in the same silent list" "$(printf '%s\n' "$SHAPES" | sed -n 's/^old=//p')" "8"

echo "== the payload: a shell's traces (2026-09-13) =="

# A shell substitution can remove a backticked token from a double-quoted payload.
# Check odd backtick counts and captured shell errors; a clean loss leaves neither trace.
# See register entry of 2026-09-10 19:59.
fixture "$W/fix"
vws log-append --vault "$VAULT" --action lint --title "t" --changed "control \`Bregman\` 7 hits" --conflicts "none" --date 2026-09-05
eq "B1 a balanced code span warns about nothing" "$(nlines "$SERR")" "0"
vws log-append --vault "$VAULT" --action lint --title "t" --changed "control \`Bregman 7 hits" --conflicts "none" --date 2026-09-05
eq "B2 control: one backtick left open earns one line" "$(nlines "$SERR")" "1"
fhas "B2b it names the argument and the count" "$SERR" "payload: --changed carries 1 backtick, an odd count"
eq "B2c a warning is not a refusal" "$RC" "0"
eq "B2d the write proceeded" "$(count "$LOG" "control \`Bregman 7 hits")" "1"
vws log-append --vault "$VAULT" --action lint --title "t" --changed "c" --conflicts "none" --extra "Probe: control zsh: command not found: Bregman 7 hits" --date 2026-09-05
eq "B3 a captured 'command not found' earns one line" "$(nlines "$SERR")" "1"
fhas "B3b it names the extra by its key" "$SERR" "payload: --extra Probe carries 'command not found'"
eq "B3c and the write proceeded" "$RC$(count "$LOG" "Probe**: control zsh: command not found")" "01"
vws log-append --vault "$VAULT" --action lint --title "t" --changed "the grep found nothing, and the file was not found" --conflicts "none" --date 2026-09-05
eq "B4 ordinary prose saying 'not found' warns about nothing" "$(nlines "$SERR")" "0"
vws log-append --vault "$VAULT" --action lint --title "odd \`title" --changed "one \` here" --conflicts "and \`\`\` there" --extra "K: \`a\` and \`b\` and \`c" --date 2026-09-05
eq "B5 each odd argument earns its own line (title, changed, conflicts, extra)" "$(nlines "$SERR")" "4"

fixture "$W/fix"
cp "$LOG" "$W/log.payloaddry"
vws log-append --vault "$VAULT" --action lint --title "t" --changed "control \`Bregman 7 hits" --conflicts "none" --date 2026-09-05 --dry-run
eq "B6 a dry run warns the same way" "$(nlines "$SERR")" "1"
if cmp -s "$W/log.payloaddry" "$LOG"; then ok "B6b the warned dry run wrote nothing"; else no "B6b the warned dry run changed the log"; fi

# B7 — the 2026-09-10 text itself, double-quoted through a POSIX shell as the caller wrote it.
# The token and both backticks are gone before the script runs, so its stderr stays silent: the
# clean loss is the caller discipline's case, and this leg pins that limit rather than hiding it.
# Controls on the same run: the shell reported the unknown command on its own stderr, and the
# entry shipped the double space the register quotes.
fixture "$W/fix"
cat >"$W/replay.sh" <<'REPLAY_PAYLOAD_END'
"$1" -B "$2" log-append --vault "$3" --action lint --title "replay" --changed "control `Bregman` 7 hits" --conflicts "none" --date 2026-09-05 2>"$4"
REPLAY_PAYLOAD_END
sh "$W/replay.sh" "$PY" "$S" "$VAULT" "$SERR" >"$SOUT" 2>"$W/shell-stderr.txt"
eq "B7 the clean loss leaves no trace the script can read: its stderr is silent" "$(nlines "$SERR")" "0"
eq "B7b control: the entry shipped the double space where the token was" "$(count "$LOG" "control  7 hits")" "1"
fhas "B7c control: the shell itself reported the unknown command" "$W/shell-stderr.txt" "not found"

echo "== the clock: the time attached to a date is a citation (Batch 10) =="

# The register entry of 2026-10-01 13:46: every clock token a note cited (`the owner's rule of
# 2026-09-30 13:54`) was warned, so the warning was always false and trained the head to read
# past it. The time attached to a date (the token directly after it, and the far end of a range
# written from it) is now skipped; every other token still warns, in a dated argument too.
# The register's example is 13:54; the planted hour keeps the leg at another hour on every run.
fixture "$W/fix"
CITED="$(plant_hour):54"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "sigma surface — a cited time" --symptom "s" --cause "c" --severity minor --status "seen 2026-09-30 $CITED"
eq "K61 (must fire) a time after a date in the same argument (seen 2026-09-30 $CITED) prints no clock line" "$(grep -c '^clock:' "$SERR" || true)" "0"
eq "K61b and the entry was written" "$RC$(count "$REG" "seen 2026-09-30 $CITED")" "01"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "tau surface — a bare time" --symptom "s" --cause "c" --severity minor --status "seen at $CITED"
eq "K62 (must not fire) the same time with no date (at $CITED) still warns, once" "$(grep -c '^clock:' "$SERR" || true)" "1"
fhas "K62b the warning names that token" "$SERR" "clock: the note names $CITED,"

# K63 — the shapes the 2026-10-01 entry recorded, through the module with the clock passed in
# (09:30, an hour every token below disagrees with). K63c is its control: the same strings with
# their dates removed are all caught, so each silent token is silent for its date alone.
# Updated 2026-10-12: only the time attached to a date is silent, so the second time of
# `21:26 and 03:40`, joined by `and` rather than written as a range, is now caught.
CITES=$("$PY" -B -c '
import importlib.util, re, sys, time
spec = importlib.util.spec_from_file_location("vwmod", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
now = time.struct_time((2026, 9, 8, 9, 30, 0, 0, 0, -1))
texts = [
    "a limit of the approach (the rule of 2026-09-30 13:54)",   # silent: right after a date
    "the same class as the entries of 2026-09-30 21:26 and 03:40",  # 21:26 silent, 03:40 caught: no range
    "the head told the owner at about 11:35",                   # caught: no date
    "corrected in the reply of 12:0x, see 2026-09-23 16:2x",    # 12:0x caught, 16:2x silent
    "2026-09-30", "at 17:45",                                   # caught: the date is another argument
]
print("kept=" + ",".join(mod.clock_tokens(now, texts)))
undated = [re.sub(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", "", text) for text in texts]
print("undated=" + ",".join(mod.clock_tokens(now, undated)))
' "$S")
eq "K63 only the time attached to a date is skipped: a later token of the same argument is kept" "$(printf '%s\n' "$CITES" | sed -n 's/^kept=//p')" "03:40,11:35,12:0x,17:45"
eq "K63c control: with the dates removed the same call catches all seven" "$(printf '%s\n' "$CITES" | sed -n 's/^undated=//p')" "13:54,21:26,03:40,11:35,12:0x,16:2x,17:45"

# K64 — a register close's own `closed DATE HH:MM` stamp claims the close's time, not a past one,
# so its time is still checked although it follows a date (K34 to K36 above); a dated citation
# later in the same status is skipped.
fixture "$W/fix"
PLANT="$(plant_hour):3x"
PLANT2="$(other_hour):45"
vws register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed 2026-09-05 $PLANT — as the entry of 2026-09-30 $PLANT2 foresaw"
eq "K64 a close's own stamp is checked and the dated citation behind it is not: one line" "$(nlines "$SERR")" "1"
fhas "K64b and that line names the stamp's time" "$SERR" "clock: the note names $PLANT,"

# K65 — a present-time slip later in a dated argument: the citation keeps its date's exemption and
# the later token is checked. Two planted hours keep both tokens away from the clock on every run.
fixture "$W/fix"
CITED="$(plant_hour):54"
NOWT="$(other_hour):00"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "upsilon surface — a cited time and a present one" --symptom "s" --cause "c" --severity minor --status "seen 2026-09-30 $CITED; now filing at $NOWT"
eq "K65 a later token in a dated argument (seen 2026-09-30 $CITED; now filing at $NOWT) warns, once" "$(grep -c '^clock:' "$SERR" || true)" "1"
fhas "K65b the warning names the later token" "$SERR" "clock: the note names $NOWT,"
fhasnot "K65c guard: and not the time attached to the date" "$SERR" "clock: the note names $CITED,"
eq "K65d guard: a warning is not a refusal, the entry was written" "$RC$(count "$REG" "now filing at $NOWT")" "01"

# K66 — the same rule through the module at a fixed clock (17:30): the mixed example names 12:00
# alone; the dated citation, and a range written from it with `to`, an en dash, a hyphen or a
# spaced en dash (the forms the vault writes ranges in), stay quiet; a bare time still warns; and
# a token that is not the time attached to its date is checked: a word or a comma between them,
# a second time joined by `and`, a time after an em dash (a clause break, never a range here).
NARROW=$("$PY" -B -c '
import importlib.util, sys, time
spec = importlib.util.spec_from_file_location("vwmod", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
now = time.struct_time((2026, 9, 30, 17, 30, 0, 0, 0, -1))
def names(texts):
    return ",".join(mod.clock_tokens(now, texts))
print("mixed=" + names(["seen 2026-09-30 13:54; now filing at 12:00"]))
print("cited=" + names(["seen 2026-09-30 13:54"]))
print("ranges=" + names(["seen 2026-09-30 13:54 to 14:10", "seen 2026-09-30 13:54–14:10",
                         "seen 2026-09-30 13:54-14:10", "seen 2026-09-30 13:54 – 14:10"]))
print("bare=" + names(["seen at 13:54"]))
print("apart=" + names(["seen 2026-09-30 at 13:54", "the run of 2026-09-30, then 14:10 to 14:20",
                        "2026-09-30 13:54 and 15:05", "2026-09-30 13:54 — 16:05 now"]))
' "$S")
eq "K66 the mixed example at 17:30 (seen 2026-09-30 13:54; now filing at 12:00) names 12:00 alone" "$(printf '%s\n' "$NARROW" | sed -n 's/^mixed=//p')" "12:00"
eq "K66b guard: the dated citation alone stays quiet" "$(printf '%s\n' "$NARROW" | sed -n 's/^cited=//p')" ""
eq "K66c guard: a range written from the dated time stays quiet (to, en dash, hyphen, spaced en dash)" "$(printf '%s\n' "$NARROW" | sed -n 's/^ranges=//p')" ""
eq "K66d control: a bare at 13:54 still warns" "$(printf '%s\n' "$NARROW" | sed -n 's/^bare=//p')" "13:54"
eq "K66e a token not attached to its date is checked (a word or a comma between, and, an em dash)" "$(printf '%s\n' "$NARROW" | sed -n 's/^apart=//p')" "13:54,14:10,14:20,15:05,16:05"

echo "== log-append: an --extra already shaped as a bullet (Batch 10) =="

# The register entry of 2026-10-03 00:25: --extra '- **Local-first**: no' wrote
# `- **- **Local-first****: no` into the append-only log and printed ok.
fixture "$W/fix"
cp "$LOG" "$W/log.bullet"
vw log-append --vault "$VAULT" --action framework --title "t" --changed "c" --conflicts "none" --extra '- **Local-first**: no' --date 2026-09-05
eq "X1 (must fire) an --extra key shaped as a bullet (- **Local-first**) is refused" "$RC" "2"
has "X2 the one error line names the key" "error log-append: --extra key '- **Local-first**' is already shaped as a bullet"
eq "X2b one line of output" "$(nlines "$OUT")" "1"
if cmp -s "$W/log.bullet" "$LOG"; then ok "X3 the refused call left log.md byte-identical"; else no "X3 the refused call changed log.md"; fi
vw log-append --vault "$VAULT" --action framework --title "t" --changed "c" --conflicts "none" --extra '**Local-first**: no' --date 2026-09-05
eq "X4 a bold key without the dash is refused too" "$RC" "2"
vw log-append --vault "$VAULT" --action framework --title "t" --changed "c" --conflicts "none" --extra '- Local-first: no' --date 2026-09-05
eq "X5 a dashed key without the bold is refused too" "$RC" "2"
if cmp -s "$W/log.bullet" "$LOG"; then ok "X5b neither refusal wrote a byte"; else no "X5b a refusal changed log.md"; fi
vw log-append --vault "$VAULT" --action framework --title "t" --changed "c" --conflicts "none" --extra 'Local-first: no' --date 2026-09-05
eq "X6 (must not fire) the bare --extra 'Local-first: no' still appends" "$RC" "0"
eq "X6b as one well-formed bullet" "$(count "$LOG" '- **Local-first**: no')" "1"
eq "X6c and no doubled bullet anywhere in the log" "$(count "$LOG" '- **- **')" "0"
eq "X6d control: the same count sees a planted doubled bullet" "$(printf -- '- **- **Local-first****: no\n' | grep -cF -- '- **- **')" "1"
vw log-append --vault "$VAULT" --action framework --title "t" --changed "c" --conflicts "none" --extra 'Note: a **bold** word - and a dash' --date 2026-09-05
eq "X7 (must not fire) bold and a dash inside the value are the caller's text and append" "$RC" "0"

# ================================ Batch 10 checks (2026-10-12) ================================
# The legs below are the claims of Batch 10's new checks (entries 6 and 7 of the plan, the
# K0820e80e residual, and the review findings folded into them). A leg named `control:` proves its
# probe can fire; one named `guard:` pins a behaviour the code before these checks already had (it
# passes there too); one named `limit:` shows a documented limit that holds before and after.
# Every other leg here fails on the code before these checks.
# minute_pair: the clock's minute and the next one, as `HH:MM HH:MM`, read in ONE call. Read in two
# calls, a minute boundary between them gave M0 and M0+2, and an add landing in M0+1 found no
# planted stamp (S7 and S7b failed once in five runs of the same text).
minute_pair() { "$PY" -B -c 'import datetime; n = datetime.datetime.now(); print(n.strftime("%H:%M"), (n + datetime.timedelta(minutes=1)).strftime("%H:%M"))'; }
inopen() { awk '/^## Open/{f=1} /^## Closed/{f=0} f' "$REG" | grep -cF -- "$1" || true; }
inclosed() { awk '/^## Closed/{f=1} f' "$REG" | grep -cF -- "$1" || true; }
stamp_of() { grep -F -- "] $1" "$REG" | sed -n 's/^### \[\([^]]*\)\].*/\1/p' | head -n 1; }
same_file() { if cmp -s "$2" "$3"; then ok "$1"; else no "$1 ($3 changed)"; fi; }
# unchanged COPY FILE: `same` when FILE still equals COPY, else `changed` — folded into a refusal's
# own leg, so that "refused, for its reason, writing nothing" is one claim.
unchanged() { if cmp -s "$1" "$2"; then echo same; else echo changed; fi; }
temps_in() { find "$1" -name '.vault-writes-*' | wc -l | tr -d ' '; }
# plant_heads LINE STAMP...: one heading and one Status per stamp, inserted before line LINE.
plant_heads() {
	"$PY" -B -c 'import sys
path, at, stamps = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
with open(path, encoding="utf-8") as handle:
    lines = handle.read().split("\n")
block = []
for stamp in stamps:
    block += ["### [%s] planted heading (minor)" % stamp, "- **Status**: open", ""]
lines[at - 1:at - 1] = block
with open(path, "w", encoding="utf-8") as handle:
    handle.write("\n".join(lines))
' "$REG" "$@"
}
# plant_lines LINE TEXT...: the lines given, verbatim, inserted before line LINE.
plant_lines() {
	"$PY" -B -c 'import sys
path, at, new = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
with open(path, encoding="utf-8") as handle:
    lines = handle.read().split("\n")
lines[at - 1:at - 1] = new
with open(path, "w", encoding="utf-8") as handle:
    handle.write("\n".join(lines))
' "$REG" "$@"
}

echo "== register add: why not fixed now (D21 (a)) =="

fixture "$W/fix"
cp "$REG" "$W/reg.before"
vw register add --vault "$VAULT" --date 2026-09-05 --surface "why surface" --symptom "s" --cause "c" --severity minor --status "open"
eq "W1 an add without --why-not-fixed-now is refused in one line naming the field and the rule, writing nothing" "$RC$(nlines "$OUT")$(grep -c -- 'error register-add: --why-not-fixed-now is missing: an entry parks a defect only for a named reason' "$OUT")$(unchanged "$W/reg.before" "$REG")" "211same"
vw register add --vault "$VAULT" --why-not-fixed-now "" --date 2026-09-05 --surface "why surface" --symptom "s" --cause "c" --severity minor --status "open"
eq "W2 an empty reason is refused, writing nothing" "$RC$(grep -c -- 'error register-add: --why-not-fixed-now is empty' "$OUT")$(unchanged "$W/reg.before" "$REG")" "21same"
vw register add --vault "$VAULT" --why-not-fixed-now "   " --date 2026-09-05 --surface "why surface" --symptom "s" --cause "c" --severity minor --status "open"
eq "W2b a reason of spaces only is refused, writing nothing" "$RC$(grep -c -- 'error register-add: --why-not-fixed-now is empty' "$OUT")$(unchanged "$W/reg.before" "$REG")" "21same"
vw register add --vault "$VAULT" --why-not-fixed-now "$(printf '\t')" --date 2026-09-05 --surface "why surface" --symptom "s" --cause "c" --severity minor --status "open"
eq "W2c a reason of a tab only is refused, writing nothing" "$RC$(grep -c -- 'error register-add: --why-not-fixed-now is empty' "$OUT")$(unchanged "$W/reg.before" "$REG")" "21same"
vw register add --vault "$VAULT" --why-not-fixed-now "$(printf 'two\nlines')" --date 2026-09-05 --surface "why surface" --symptom "s" --cause "c" --severity minor --status "open"
eq "W4 a reason with a line break is refused, writing nothing" "$RC$(grep -c -- '--why-not-fixed-now carries a line break' "$OUT")$(unchanged "$W/reg.before" "$REG")" "21same"
vw register add --vault "$VAULT" --why-not-fixed-now "$(printf 'two\rlines')" --date 2026-09-05 --surface "why surface" --symptom "s" --cause "c" --severity minor --status "open"
eq "W4b a reason with a carriage return is refused, writing nothing" "$RC$(grep -c -- '--why-not-fixed-now carries a line break' "$OUT")$(unchanged "$W/reg.before" "$REG")" "21same"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "why surface" --symptom "s" --cause "c" --severity minor --status "open — fix shape: why" --where "run W"
eq "W3 an add with the reason is written" "$RC" "0"
eq "W3b the reason is its own bullet between Suspected cause and Status" "$(awk 'NR>=10 && NR<=12' "$REG" | tr '\n' '|')" "- **Suspected cause**: c|- **Why not fixed now**: $WN|- **Status**: open — fix shape: why|"
eq "W3c exactly one reason bullet in the file" "$(count "$REG" '- **Why not fixed now**: ')" "1"
PLANT="$(plant_hour):3x"
vws register add --vault "$VAULT" --why-not-fixed-now "blocked until $PLANT" --date 2026-09-05 --surface "why clock" --symptom "s" --cause "c" --severity minor --status "open"
eq "W5 the reason is scanned for clock tokens like every text argument" "$RC$(nlines "$SERR")" "01"
fhas "W5b the warning names the token" "$SERR" "clock: the note names $PLANT,"
vw register add --help
eq "W6 the help names the field and says it is required" "$(grep -c -- '^  --why-not-fixed-now REASON' "$OUT")$(grep -c 'required: the named reason' "$OUT")" "11"
fixture "$W/fix"
cp "$REG" "$W/reg.wdry"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "why dry" --symptom "s" --cause "c" --severity minor --status "open" --dry-run
eq "W7 a dry run shows the reason's bullet and writes nothing" "$RC$(grep -cF -- "| - **Why not fixed now**: $WN" "$OUT")$(unchanged "$W/reg.wdry" "$REG")" "01same"

echo "== register add: the cause-kind word, tested or observed (2026-11-14) =="
fixture "$W/fix"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "kind observed" --symptom "s" --cause "a guess from the log" --cause-kind observed --severity minor --status "open"
eq "CK1 --cause-kind observed puts the one word before the cause" "$RC$(count "$REG" '- **Suspected cause**: observed: a guess from the log')" "01"
fixture "$W/fix"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "kind tested" --symptom "s" --cause "a rerun showed it" --cause-kind tested --severity minor --status "open"
eq "CK2 --cause-kind tested puts that word instead" "$RC$(count "$REG" '- **Suspected cause**: tested: a rerun showed it')" "01"
fixture "$W/fix"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "kind absent" --symptom "s" --cause "plain cause" --severity minor --status "open"
eq "CK3 control: without --cause-kind the field keeps its old shape, with no kind word in the file" "$RC$(count "$REG" '- **Suspected cause**: plain cause')$(grep -cE -- '^- \*\*Suspected cause\*\*: (tested|observed): ' "$REG")" "010"
fixture "$W/fix"; cp "$REG" "$W/reg.ck4"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "kind guessed" --symptom "s" --cause "c" --cause-kind guessed --severity minor --status "open"
eq "CK4 a kind other than tested or observed is refused, writing nothing" "$RC$(grep -c -- '--cause-kind: invalid choice' "$OUT")$(unchanged "$W/reg.ck4" "$REG")" "21same"
fixture "$W/fix"; cp "$REG" "$W/reg.ck5"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "kind dry" --symptom "s" --cause "c" --cause-kind observed --severity minor --status "open" --dry-run
eq "CK5 a dry run shows the cause with its word and writes nothing" "$RC$(grep -cF -- '- **Suspected cause**: observed: c' "$OUT")$(unchanged "$W/reg.ck5" "$REG")" "01same"
vw register add --help
eq "CK6 the help names the option and its two words" "$(grep -c -- '^  --cause-kind {tested,observed}' "$OUT")" "1"

echo "== register add: one stamp, one entry (K7c56f8cc) =="

fixture "$W/fix"
MM=$(minute_pair); M0=${MM% *}; M1=${MM#* }
plant_heads 7 "2026-09-05 $M0" "2026-09-05 $M1"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "sigma surface" --symptom "s" --cause "c" --severity minor --status "open"
eq "S1 an add in a minute whose stamp another heading carries is written" "$RC" "0"
eq2 "S1b it takes the suffix b inside the brackets" "$(awk 'NR==7' "$REG")" "### [2026-09-05 $M0 b] sigma surface (minor)" "### [2026-09-05 $M1 b] sigma surface (minor)"
eq "S1c guard: a suffix is routine, not a warning: stderr stays silent and stdout is the one ok line" "$(nlines "$SERR")$(nlines "$SOUT")" "01"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "tau surface" --symptom "s" --cause "c" --severity minor --status "open"
eq "S2 two entries added in one minute carry two different stamps" "$(test -n "$(stamp_of 'sigma surface')" && test "$(stamp_of 'sigma surface')" != "$(stamp_of 'tau surface')" && echo distinct)" "distinct"
eq "S2b the four stamps of that date (two planted, two added) are four, and none repeats" "$(sed -n 's/^### \[\(2026-09-05 [^]]*\)\].*/\1/p' "$REG" | wc -l | tr -d ' ')$(sed -n 's/^### \[\(2026-09-05 [^]]*\)\].*/\1/p' "$REG" | sort | uniq -d | wc -l | tr -d ' ')" "40"

fixture "$W/fix"
MM=$(minute_pair); M0=${MM% *}; M1=${MM#* }
plant_heads 30 "2026-09-05 $M0" "2026-09-05 $M1"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "upsilon surface" --symptom "s" --cause "c" --severity minor --status "open"
eq2 "S3 a stamp carried only under Closed counts too" "$(awk 'NR==7' "$REG")" "### [2026-09-05 $M0 b] upsilon surface (minor)" "### [2026-09-05 $M1 b] upsilon surface (minor)"
fixture "$W/fix"
MM=$(minute_pair); M0=${MM% *}; M1=${MM#* }
printf '%s\n' '---' 'title: closed entries' '---' '' '## Closed entries' "### [2026-09-05 $M0] swept heading (minor)" '- **Status**: closed' '' "### [2026-09-05 $M1] swept heading (minor)" '- **Status**: closed' > "$VAULT/wiki/developments/known-issues-closed.md"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "psi surface" --symptom "s" --cause "c" --severity minor --status "open"
eq2 "S3c a stamp carried only on the closed page, where the sweep moved its entry, counts too" "$(awk 'NR==7' "$REG")" "### [2026-09-05 $M0 b] psi surface (minor)" "### [2026-09-05 $M1 b] psi surface (minor)"
rm -f "$VAULT/wiki/developments/known-issues-closed.md"
fixture "$W/fix"
MM=$(minute_pair); M0=${MM% *}; M1=${MM#* }
plant_heads 7 "2026-09-05 $M0" "2026-09-05 $M1"
cp "$REG" "$W/reg.sdry"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "phi surface" --symptom "s" --cause "c" --severity minor --status "open" --dry-run
eq "S4 a dry run shows the suffixed stamp and writes nothing" "$(grep -cE "^\| ### \[2026-09-05 ($M0|$M1) b\] phi surface \(minor\)$" "$SOUT")$(unchanged "$W/reg.sdry" "$REG")" "1same"

STAMPS=$("$PY" -B -c '
import contextlib, importlib.util, io, sys
spec = importlib.util.spec_from_file_location("vwmod", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
def stamp(lines):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            return mod.unique_stamp("register-add", lines, "2026-09-05", "07:48")
        except SystemExit:
            said = out.getvalue()
            return "REFUSED:" + ("cannot read" if "cannot read" in said else "heads" if "already heads" in said
                                 else "every suffix" if "every suffix" in said else said.strip())
def heads(stamps):
    return ["# R", "## Open"] + ["### [%s] x (minor)" % h for h in stamps] + ["## Closed"]
B = "2026-09-05 07:48"
cases = [
    [],                                              # free: the bare stamp
    [B],                                             # taken once: b
    [B, B + " b"],                                   # b taken too: c
    [B] + [B + " " + s for s in "bcdefghijklmnopqrstuvwxyz"],   # every suffix taken: refused
    [B, B],                                          # two headings with one stamp: refused
    [B, B + " b", B + " b"],                         # a doubled suffixed stamp: refused
    ["2026-09-05 07:48b"], ["2026-09-05 07:48:31"], ["2026-09-05 07:48 bb"], ["2026-09-05 07:48 B"],
    ["2026-09-05 07:47", "2026-09-05 07:47"],        # another minute shared twice stops nothing
    ["2026-09-05 07:4x"],                            # a rounded stamp is another text
    ["2026-09-05  07:48"],                           # spacing inside the brackets is normalised
    ["2026-09-06 07:48"],                            # another date
]
print("|".join(stamp(heads(c)) for c in cases))
raw = [
    ["### [2026-09-05 07:48"],                       # the candidate minute, the bracket never closed
    ["### [2026-09-05 07:48 unfinished title"],      # the same, with text after it
    ["### [2026-09-05  07:48 b"],                    # a suffix, never closed, spacing aside
    ["### [2026-09-05 07:47 unfinished"],            # another minute, never closed: not this minute
    ["### [2026-09-05 07:4"],                        # not the candidate minute at all
    ["### 2026-09-05 07:48 no bracket"],             # no bracket: not a stamp heading
]
print("|".join(stamp(["# R", "## Open"] + c + ["## Closed"]) for c in raw))
' "$S" 2>&1)
eq "S5 the stamp rule, case by case (free, b, c, all taken, doubled, doubled suffix, four unreadable forms, another minute, rounded, spacing, another date)" "$(printf '%s\n' "$STAMPS" | sed -n 1p)" "2026-09-05 07:48|2026-09-05 07:48 b|2026-09-05 07:48 c|REFUSED:every suffix|REFUSED:heads|REFUSED:heads|REFUSED:cannot read|REFUSED:cannot read|REFUSED:cannot read|REFUSED:cannot read|2026-09-05 07:48|2026-09-05 07:48|2026-09-05 07:48 b|2026-09-05 07:48"
eq "S5b a candidate-minute heading whose bracket never closes refuses; an unclosed heading of another minute, or none of a stamp, stops nothing" "$(printf '%s\n' "$STAMPS" | sed -n 2p)" "REFUSED:cannot read|REFUSED:cannot read|REFUSED:cannot read|2026-09-05 07:48|2026-09-05 07:48|2026-09-05 07:48"

fixture "$W/fix"
plant_heads 7 "2026-08-01 12:00" "2026-08-01 12:00"
T0=$(now_hm)
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "chi surface — beside an old shared stamp" --symptom "s" --cause "c" --severity minor --status "open"
T1=$(now_hm)
eq2 "S6 an unrelated historical stamp shared by two headings stops nothing: the add takes the bare stamp" "$RC$(awk 'NR==7' "$REG")" "0### [2026-09-05 $T0] chi surface — beside an old shared stamp (minor)" "0### [2026-09-05 $T1] chi surface — beside an old shared stamp (minor)"

fixture "$W/fix"
MM=$(minute_pair); M0=${MM% *}; M1=${MM#* }
plant_heads 7 "2026-09-05 $M0" "2026-09-05 $M1"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "omega surface" --symptom "s" --cause "c" --severity minor --status "open"
STAMP=$(stamp_of 'omega surface')
BARE=${STAMP% b}
vw register close --vault "$VAULT" --match "[$BARE]" --date 2026-09-05 --status "closed by its bare stamp"
eq "S7 --match with the bare stamp and its bracket names the bare entry alone, never the suffixed one" "$RC$(inclosed "[$BARE] planted heading")$(inopen 'omega surface')" "011"
vw register close --vault "$VAULT" --match "[$STAMP]" --date 2026-09-05 --status "closed by its suffixed stamp"
eq "S7b --match with the suffixed stamp names the suffixed entry" "$RC$(inclosed 'omega surface')$(test "$STAMP" != "$BARE" && echo suffixed)" "01suffixed"

echo "== register add: what the stamp check does when it cannot tell =="

fixture "$W/fix"
MM=$(minute_pair); M0=${MM% *}; M1=${MM#* }
plant_heads 7 "2026-09-05 $M0" "2026-09-05 $M0" "2026-09-05 $M1" "2026-09-05 $M1"
cp "$REG" "$W/reg.doubled"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "chi surface" --symptom "s" --cause "c" --severity minor --status "open"
eq "U4 an add into a minute whose stamp already heads two entries is refused (it names none of them), writing nothing" "$RC$(grep -c 'already heads 2 entries, so it names none of them' "$OUT")$(unchanged "$W/reg.doubled" "$REG")" "21same"
fixture "$W/fix"
MM=$(minute_pair); M0=${MM% *}; M1=${MM#* }
plant_heads 7 "2026-09-05 ${M0}b" "2026-09-05 ${M1}b"
cp "$REG" "$W/reg.glued"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "psi surface" --symptom "s" --cause "c" --severity minor --status "open"
eq "U5 a heading carrying the same minute in a form the check cannot read refuses the add, writing nothing" "$RC$(grep -c 'this check cannot read' "$OUT")$(unchanged "$W/reg.glued" "$REG")" "21same"
fixture "$W/fix"
MM=$(minute_pair); M0=${MM% *}; M1=${MM#* }
plant_lines 7 "### [2026-09-05 $M0 unfinished heading" "- **Status**: open" "" "### [2026-09-05 $M1 unfinished heading" "- **Status**: open" ""
cp "$REG" "$W/reg.unclosed"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "psi surface" --symptom "s" --cause "c" --severity minor --status "open"
eq "U6 a heading of the same minute whose bracket never closes refuses the add, naming it, writing nothing" "$RC$(grep -c 'never closes its bracket' "$OUT")$(unchanged "$W/reg.unclosed" "$REG")" "21same"

echo "== register close: the lines an entry owns (K0820e80e) =="

# A register holding each shape the live register carries, and the three a close must refuse:
# an entry an unheaded one-line entry follows, a dated Recurrence after a blank line, a one-line
# entry given a heading later (a date-led first bullet and indented lines), an entry holding a
# bold date-first bullet, one holding a second Symptom (a lost heading), one whose Status sits
# below a plain paragraph.
xfixture() {
	rm -rf "$1"
	mkdir -p "$1/vault/wiki/developments"
	cat > "$1/vault/wiki/developments/known-issues.md" <<'XREG_END'
# Known Issues

## Open

### [2026-09-10 10:00] first surface — an unheaded bullet follows it (minor)
- **Where observed**: run F
- **Symptom**: s1
- **Suspected cause**: c1
- **Status**: open — fix shape: first

- 2026-09-09 · surface: an unheaded one-line entry · symptom: it would be swept

### [2026-09-10 09:00] second surface — a recurrence after a blank line (minor)
- **Symptom**: s2
- **Status**: open — fix shape: second

- **Recurrence 2026-10-09 00:37 BST (session x):** it came back
### [2026-09-10 08:00] third surface — a one-line entry given a heading later (major)
- 2026-09-08 07:3x · surface: a legacy entry · symptom: one line
  - Recurrence 5 October 2026, written 16:37 BST: an indented sub-bullet
  - Recurrence 5 October 2026, written 23:40 BST: another indented line
- **Status**: as the line above states

### [2026-09-10 07:00] fourth surface — a bold date-first bullet below its fields (minor)
- **Symptom**: s4
- **Status**: open — fix shape: fourth

- **2026-09-25 12:57 BST · blind panels · another entry's body.** Symptom: it would be swept
### [2026-09-10 06:00] fifth surface — two Symptom fields (minor)
- **Symptom**: s5
- **Status**: open — fix shape: fifth
- **Symptom**: a second entry's symptom, its heading lost
- **Status 2026-09-11 (a dated note):** not a Status line

### [2026-09-10 05:00] sixth surface — a paragraph above its Status (minor)
a plain paragraph that is none of the entry's own lines
- **Status**: open — fix shape: sixth

## Closed

### [2026-09-01 12:00] closed surface — done long ago (minor)
- **Status**: closed 2026-09-01 — done
XREG_END
}
# A second register for the Status structure: two Status fields under one heading, a Status field
# below an unheaded entry that follows an entry with its own Status, and a field whose text only
# quotes the marker beside a combined Severity and Status line.
yfixture() {
	rm -rf "$1"
	mkdir -p "$1/vault/wiki/developments"
	cat > "$1/vault/wiki/developments/known-issues.md" <<'YREG_END'
# Known Issues

## Open

### [2026-09-11 10:00] seventh surface — two Status fields (minor)
- **Symptom**: s7
- **Status**: open — fix shape: seventh
- **Status**: open — a second entry's status, its heading lost

### [2026-09-11 09:00] eighth surface — a Status below an unheaded entry (minor)
- **Symptom**: s8
- **Status**: open — fix shape: eighth

- 2026-09-09 · surface: an unheaded one-line entry · symptom: s
- **Status**: open — whose is this?

### [2026-09-11 08:00] ninth surface — a field that quotes the marker (minor)
- **Symptom**: s9 names the **Status** marker in its own text
- **Severity**: minor (quoted). **Status**: open — fix shape: ninth

## Closed

### [2026-09-01 12:00] closed surface — done long ago (minor)
- **Status**: closed 2026-09-01 — done
YREG_END
}

xfixture "$W/fix"
[ "$(nlines "$REG")" = "42" ] || { echo "PROBE FAILED: the extent fixture does not hold its 42 lines"; echo "FAIL 1/1"; exit 2; }
vws register close --vault "$VAULT" --match "first surface" --date 2026-09-05 --status "closed by the suite"
eq "XT1 an entry an unheaded one-line entry follows closes, and the unheaded entry stays under Open" "$RC$(inopen '- 2026-09-09 · surface: an unheaded one-line entry')" "01"
eq "XT1c guard: the closed entry left Open for Closed" "$(inopen 'first surface')$(inclosed 'first surface')" "01"
eq "XT1d stderr names the line left in place" "$(cat "$SERR")" "extent: line 11 below this entry is not its own and stays under '## Open'"
eq "XT1e the ok line names the top of Closed after a five-line move" "$(cat "$SOUT")" "ok register-close $REG:35"
eq "XT1f guard: the file neither grew nor shrank" "$(nlines "$REG")" "42"
xfixture "$W/fix"
vw register close --vault "$VAULT" --match "first surface" --date 2026-09-05 --status "x" --dry-run
has "XT7 a dry run says how many lines move" "| moved 5 lines to the top of '## Closed'"
has "XT7b and which line stays" "| line 11 below this entry is not its own and stays under '## Open'"

xfixture "$W/fix"
vw register close --vault "$VAULT" --match "second surface" --date 2026-09-05 --status "x"
eq "XT2 guard: a dated Recurrence after a blank line moves with its entry" "$RC$(inopen 'it came back')$(inclosed 'it came back')" "001"
xfixture "$W/fix"
vw register close --vault "$VAULT" --match "third surface" --date 2026-09-05 --status "x"
eq "XT3 guard: a date-led first bullet and its indented lines move with their entry" "$RC$(inopen 'an indented sub-bullet')$(inclosed 'an indented sub-bullet')$(inclosed 'another indented line')" "0011"

xfixture "$W/fix"
cp "$REG" "$W/reg.x"
vw register close --vault "$VAULT" --match "fourth surface" --date 2026-09-05 --status "x"
eq "XT4 an entry holding a bold date-first bullet is refused, naming the line, writing nothing" "$RC$(grep -c 'holds another entry at line 28 (a bullet opening with a date below the first' "$OUT")$(unchanged "$W/reg.x" "$REG")" "21same"
cp "$W/reg.x" "$REG"   # each refusal leg starts from the same bytes, so one cannot leak into the next
vw register close --vault "$VAULT" --match "fifth surface" --date 2026-09-05 --status "x"
eq "XT5 an entry holding a second Symptom field is refused, naming it, writing nothing" "$RC$(grep -c "holds another entry at line 32 (a second 'Symptom' field: two entries under one heading)" "$OUT")$(unchanged "$W/reg.x" "$REG")" "21same"
cp "$W/reg.x" "$REG"   # each refusal leg starts from the same bytes, so one cannot leak into the next
vw register close --vault "$VAULT" --match "sixth surface" --date 2026-09-05 --status "x"
eq "XT6 an entry whose Status sits below a plain paragraph is refused, saying where, writing nothing" "$RC$(grep -c "carries a '\*\*Status\*\*' field at line 37, below line 36, which is not one of its own lines" "$OUT")$(unchanged "$W/reg.x" "$REG")" "21same"

EXTENTS=$("$PY" -B -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("vwmod", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
lines = ["## Open", "### [A] a", "- **Symptom**: s", "- **Status**: open", "",
         "- 2026-09-09 · an unheaded entry", "",
         "### [B] b", "- **Status**: open", "", "- **Recurrence 2026-10-09:** again",
         "### [C] c", "- 2026-09-08 · legacy", "  - an indented line", "- **Status**: as above", "",
         "### [D] d", "- **Status**: open", "- **2026-09-25 12:57 · another entry.**", "",
         "## Closed"]
out = []
for name, start in (("A", 1), ("B", 7), ("C", 11), ("D", 16)):
    last, cut = mod.entry_extent(lines, start, 20)
    foreign = mod.foreign_line(lines, start, last)
    out.append("%s=%d/%d/%s" % (name, last, cut, foreign[0] if foreign else "-"))
print(" ".join(out))
' "$S" 2>&1)
eq "XT8 the extent rule through the module: last own line, cut and foreign line per entry" "$EXTENTS" "A=3/5/- B=10/11/- C=14/16/- D=18/20/18"

yfixture "$W/fix"
[ "$(nlines "$REG")" = "24" ] || { echo "PROBE FAILED: the Status-structure fixture does not hold its 24 lines"; echo "FAIL 1/1"; exit 2; }
cp "$REG" "$W/reg.y"
vw register close --vault "$VAULT" --match "seventh surface" --date 2026-09-05 --status "x"
eq "XT9 guard: an entry with two Status fields is refused as ambiguous, writing nothing" "$RC$(grep -c 'Status' "$OUT")$(unchanged "$W/reg.y" "$REG")" "21same"
eq "XT9b the refusal names the second Status field as another entry's" "$(grep -c "holds another entry at line 8 (a second 'Status' field: two entries under one heading)" "$OUT")" "1"
cp "$W/reg.y" "$REG"   # each refusal leg starts from the same bytes, so one cannot leak into the next
vw register close --vault "$VAULT" --match "eighth surface" --date 2026-09-05 --status "x"
eq "XT10 guard: a Status field below an unheaded entry under the same heading is refused, writing nothing" "$RC$(grep -c 'Status' "$OUT")$(unchanged "$W/reg.y" "$REG")" "21same"
eq "XT10b the refusal names that field and the line above it that is not the entry's own" "$(grep -c "carries a '\*\*Status\*\*' field at line 15, below line 14, which is not one of its own lines" "$OUT")" "1"
cp "$W/reg.y" "$REG"   # each refusal leg starts from the same bytes, so one cannot leak into the next
T0=$(now_hm)
vw register close --vault "$VAULT" --match "ninth surface" --date 2026-09-05 --status "closed though a field quotes the marker"
T1=$(now_hm)
eq "XT11 a field whose text only quotes the **Status** marker is not a second Status: the entry closes" "$RC$(inclosed 'ninth surface')$(inopen 'ninth surface')" "010"
eq2 "XT11b and the combined Severity and Status line is the one dated" "$(grep -F -- 'fix shape: ninth' "$REG")" "- **Severity**: minor (quoted). **Status**: open — fix shape: ninth *(2026-09-05: closed 2026-09-05 $T0 — closed though a field quotes the marker)*" "- **Severity**: minor (quoted). **Status**: open — fix shape: ninth *(2026-09-05: closed 2026-09-05 $T1 — closed though a field quotes the marker)*"

echo "== register annotate =="

xfixture "$W/fix"
Z=$(now_zone)
T0=$(now_hm)
vws register annotate --vault "$VAULT" --match "second surface" --kind Recurrence --by "run Z" --note "it came back again" --date 2026-09-05
T1=$(now_hm)
eq "N1 an Open entry takes a dated note" "$RC" "0"
eq "N1b the ok line names the note's line, after the entry's last own line" "$(cat "$SOUT")" "ok register-annotate $REG:18"
eq2 "N1c the note carries the kind, the date, the clock's time and zone, and who wrote it" "$(awk 'NR==18' "$REG")" "- **Recurrence 2026-09-05 $T0 $Z (run Z):** it came back again" "- **Recurrence 2026-09-05 $T1 $Z (run Z):** it came back again"
eq "N1d the next entry's heading follows it" "$(awk 'NR==19' "$REG")" "### [2026-09-10 08:00] third surface — a one-line entry given a heading later (major)"
xfixture "$W/fix"
T0=$(now_hm)
vw register annotate --vault "$VAULT" --match "first surface" --kind Status --note "checked again" --date 2026-09-05
T1=$(now_hm)
eq2 "N2 a Status write replaces the entry's one Status field in place; without --by the stamp omits it" "$(awk 'NR==9' "$REG")" "- **Status**: checked again (set 2026-09-05 $T0 $Z)" "- **Status**: checked again (set 2026-09-05 $T1 $Z)"
eq "N2b the unheaded entry still follows after one blank line" "$(awk 'NR==10 || NR==11' "$REG" | tr '\n' '|')" "|- 2026-09-09 · surface: an unheaded one-line entry · symptom: it would be swept|"
vw register close --vault "$VAULT" --match "first surface" --date 2026-09-05 --status "closed after a note"
eq "N8 the entry still closes, the close dating its one replaced Status field" "$RC$(inclosed '- **Status**: checked again (set 2026-09-05 ')$(inclosed ' *(2026-09-05: closed 2026-09-05 ')$(inopen 'checked again')" "0110"
xfixture "$W/fix"
cp "$REG" "$W/reg.n"
vw register annotate --vault "$VAULT" --match "second surface" --kind Note --note "n"
eq "N3 an unknown kind is refused, writing nothing" "$RC$(grep -c -- "--kind 'Note' is none of: Status Recurrence Correction" "$OUT")$(unchanged "$W/reg.n" "$REG")" "21same"
vw register annotate --vault "$VAULT" --match "surface" --kind Status --note "n"
eq "N4 an ambiguous match is refused, writing nothing" "$RC$(grep -c "'surface' matches 6 entry headings under '## Open', not 1" "$OUT")$(unchanged "$W/reg.n" "$REG")" "21same"
vw register annotate --vault "$VAULT" --match "no such entry" --kind Status --note "n"
eq "N4b a match naming no heading is refused, writing nothing" "$RC$(grep -c "'no such entry' matches 0 entry headings under '## Open', not 1" "$OUT")$(unchanged "$W/reg.n" "$REG")" "21same"
vw register annotate --vault "$VAULT" --match "closed surface" --kind Status --note "n"
eq "N7 a Closed entry is not annotated: the match reads Open only" "$RC$(grep -c "matches 0 entry headings under '## Open'" "$OUT")$(unchanged "$W/reg.n" "$REG")" "21same"
vw register annotate --vault "$VAULT" --match "fourth surface" --kind Status --note "n"
eq "N5 an entry holding another entry is refused, writing nothing" "$RC$(grep -c 'holds another entry at line 28' "$OUT")$(unchanged "$W/reg.n" "$REG")" "21same"
cp "$W/reg.n" "$REG"   # each refusal leg starts from the same bytes, so one cannot leak into the next
vw register annotate --vault "$VAULT" --match "fifth surface" --kind Status --note "n"
eq "N5b an entry holding a second Symptom field is refused, writing nothing" "$RC$(grep -c "holds another entry at line 32 (a second 'Symptom' field" "$OUT")$(unchanged "$W/reg.n" "$REG")" "21same"
cp "$W/reg.n" "$REG"   # each refusal leg starts from the same bytes, so one cannot leak into the next
vw register annotate --vault "$VAULT" --match "sixth surface" --kind Status --note "n"
eq "N12 an entry whose Status sits below a plain paragraph is refused as close refuses it, writing nothing" "$RC$(grep -c "carries a '\*\*Status\*\*' field at line 37, below line 36, which is not one of its own lines" "$OUT")$(unchanged "$W/reg.n" "$REG")" "21same"
cp "$W/reg.n" "$REG"   # each refusal leg starts from the same bytes, so one cannot leak into the next
vw register annotate --vault "$VAULT" --match "second surface" --kind Status --note "$(printf 'two\nlines')"
eq "N10 a note with a line break is refused, writing nothing" "$RC$(grep -c -- '--note carries a line break' "$OUT")$(unchanged "$W/reg.n" "$REG")" "21same"
vw register annotate --vault "$VAULT" --match "second surface" --kind Status --note "$(printf 'two\rlines')"
eq "N10b a note with a carriage return is refused, writing nothing" "$RC$(grep -c -- '--note carries a line break' "$OUT")$(unchanged "$W/reg.n" "$REG")" "21same"
vw register annotate --vault "$VAULT" --match "second surface" --kind Status --note "the **Status**: line was stale"
eq "N14 a note carrying the field marker **Status**: (which the register's lint reads as a Status) is refused, writing nothing" "$RC$(grep -c -- "--note carries the field marker '\*\*Status\*\*:'" "$OUT")$(unchanged "$W/reg.n" "$REG")" "21same"
vw register annotate --vault "$VAULT" --match "second surface" --kind Status --by "x **Status**: y" --note "n"
eq "N14b so is a --by carrying it" "$RC$(grep -c -- "--by carries the field marker" "$OUT")$(unchanged "$W/reg.n" "$REG")" "21same"
vw register annotate --vault "$VAULT" --match "second surface" --kind Correction --note "dry" --dry-run
eq "N6 a dry run names the line the note would take, writing nothing" "$RC$(grep -c "^dry-run register-annotate $REG:18$" "$OUT")$(unchanged "$W/reg.n" "$REG")" "01same"
PLANT="$(plant_hour):3x"
vws register annotate --vault "$VAULT" --match "second surface" --kind Status --note "seen at $PLANT"
eq "N9 the note is scanned for clock tokens, and still written: stderr is two lines, one clock: and one replaced:" "$RC$(nlines "$SERR")$(grep -c '^clock:' "$SERR")$(grep -c '^replaced:' "$SERR")$(inopen "seen at $PLANT")" "02111"
xfixture "$W/fix"
vw register annotate --vault "$VAULT" --match "second surface" --kind Status --note "the **Status** field above and the **Symptom** text were stale"
eq "N13 a note quoting the field names **Status** and **Symptom** is written" "$RC$(inopen 'the **Status** field above and the **Symptom** text were stale')" "01"
T0=$(now_hm)
vw register close --vault "$VAULT" --match "second surface" --date 2026-09-05 --status "closed after a quoting note"
T1=$(now_hm)
eq "N13b and the entry stays closable: the close dates its one Status field" "$RC$(inclosed 'second surface')$(inclosed 'the **Status** field above')" "011"
eq "N13c the dated line is the one Status field, which holds the quoting note" "$(inclosed '- **Status**: the **Status** field above and the **Symptom** text were stale (set ')$(grep -F -- '- **Status**: the **Status** field above' "$REG" | grep -c -F -- ' — closed after a quoting note)*')$(grep -c -F -- 'fix shape: second' "$REG")" "110"
yfixture "$W/fix"
cp "$REG" "$W/reg.ny"
vw register annotate --vault "$VAULT" --match "seventh surface" --kind Status --note "n"
eq "N15 an entry with two Status fields is refused as close refuses it, writing nothing" "$RC$(grep -c "holds another entry at line 8 (a second 'Status' field" "$OUT")$(unchanged "$W/reg.ny" "$REG")" "21same"
cp "$W/reg.ny" "$REG"   # each refusal leg starts from the same bytes, so one cannot leak into the next
vw register annotate --vault "$VAULT" --match "eighth surface" --kind Status --note "n"
eq "N16 a Status field below an unheaded entry refuses the note as it refuses the close, writing nothing" "$RC$(grep -c "field at line 15, below line 14" "$OUT")$(unchanged "$W/reg.ny" "$REG")" "21same"

echo "== register annotate --kind Status: one status per open entry (stale-information design, item 3) =="

# xrepl FILE OLD NEW: an exact replacement that must find its text exactly once (prepl, below, is
# defined later in this file); XNL is a line break inside a replacement.
XNL=$(printf '\nx'); XNL=${XNL%x}
xrepl() {
	"$PY" -B -c 'import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit("xrepl: %r found %d times in %s" % (old, text.count(old), path))
open(path, "w", encoding="utf-8").write(text.replace(old, new))' "$1" "$2" "$3" || no "fixture edit: $2 (not found exactly once)"
}

xfixture "$W/fix"; cp "$REG" "$W/reg.s0"
vw register annotate --vault "$VAULT" --match "second surface" --kind Status --note "blocked on the fixture; the lead proposes the fix on 1 October" --by lead --date 2026-09-05
vws register annotate --vault "$VAULT" --match "second surface" --kind Status --note "unblocked; the fix lands next run" --by lead --date 2026-09-06
entry_of() { awk -v m="$1" 'index($0, m) && /^### /{f=1; next} /^#/{f=0} f' "$REG"; }
eq "NS1 after two status writes the entry holds one status, the newer" "$RC$(entry_of 'second surface' | grep -c -- '^- \*\*Status')$(entry_of 'second surface' | grep -c -F -- '- **Status**: unblocked; the fix lands next run (set 2026-09-06 ')$(grep -c -F 'blocked on the fixture' "$REG")" "0110"
eq "NS2 no other line changed: one line differs from the fixture, in place, and the line count holds" "$(diff "$W/reg.s0" "$REG" | grep -c '^>')$(diff "$W/reg.s0" "$REG" | grep -c '^<')$( [ "$(nlines "$REG")" = "$(nlines "$W/reg.s0")" ] && echo same-count)" "11same-count"
eq "NS3 the Recurrence note beside it is untouched" "$(entry_of 'second surface' | grep -c -F -- '- **Recurrence 2026-10-09 00:37 BST (session x):** it came back')" "1"
eq "NS4 stderr names the status it replaced" "$(grep -c -F -- "replaced: the Status of " "$SERR")$(grep -c -F -- 'read: blocked on the fixture' "$SERR")" "11"
eq "NS5 the ok line names the field's line, which keeps its place" "$(sed 's#.*/##' "$SOUT")" "known-issues.md:15"
xfixture "$W/fix"
xrepl "$REG" "- **Status**: open — fix shape: second" "- **Status**: open — fix shape: second$XNL- **Status 2026-09-12 10:00 BST (session y):** an earlier dated layer"
cp "$REG" "$W/reg.s1"
vw register annotate --vault "$VAULT" --match "second surface" --kind Status --note "the one status now" --date 2026-09-05
eq "NS6 a dated Status note the entry already holds stays as it is: only the field is rewritten (folding it is a clean's work)" "$RC$(entry_of 'second surface' | grep -c -F -- '- **Status 2026-09-12 10:00 BST (session y):** an earlier dated layer')$(entry_of 'second surface' | grep -c -F -- '- **Status**: the one status now (set 2026-09-05 ')$(diff "$W/reg.s1" "$REG" | grep -c '^<')" "0111"
yfixture "$W/fix"; cp "$REG" "$W/reg.s2"
vw register annotate --vault "$VAULT" --match "ninth surface" --kind Status --note "open — the combined line's status" --date 2026-09-05
eq "NS7 on a combined Severity and Status line only the Status part is rewritten" "$RC$(grep -c -F -- '- **Severity**: minor (quoted). **Status**: open — the combined line'"'"'s status (set 2026-09-05 ' "$REG")$(grep -c -F 'fix shape: ninth' "$REG")$(diff "$W/reg.s2" "$REG" | grep -c '^<')" "0101"
xfixture "$W/fix"
xrepl "$REG" "- **Status**: open — fix shape: sixth" "- **Symptom**: s6"
xrepl "$REG" "a plain paragraph that is none of the entry's own lines$XNL" ""
cp "$REG" "$W/reg.s3"
vw register annotate --vault "$VAULT" --match "sixth surface" --kind Status --note "n"
eq "NS8 an entry with no Status field is refused for a Status write, writing nothing" "$RC$(grep -c "carries 0 '\*\*Status\*\*' fields, not 1, so there is no one status to replace" "$OUT")$(unchanged "$W/reg.s3" "$REG")" "21same"
vw register annotate --vault "$VAULT" --match "sixth surface" --kind Correction --note "the symptom was s6" --date 2026-09-05
eq "NS9 control: the same entry still takes a Correction note, appended, removing nothing" "$RC$(grep -c -F -- '- **Correction 2026-09-05 ' "$REG")$(diff "$W/reg.s3" "$REG" | grep -c '^<')" "010"
xfixture "$W/fix"; cp "$REG" "$W/reg.s4"
vw register annotate --vault "$VAULT" --match "second surface" --kind Status --note "dry" --dry-run
eq "NS10 a dry run of a Status write names the field's line and writes nothing" "$RC$(grep -c "^dry-run register-annotate $REG:15$" "$OUT")$(grep -c -F -- '| - **Status**: dry (set ' "$OUT")$(unchanged "$W/reg.s4" "$REG")" "011same"

echo "== concurrent writers: the check, the lock and the window (D21 (a)) =="

# The driver runs the script in process and lets "another writer" act at a chosen point between the
# script's read and its replace. Points: inside the temporary-file step (before the check), inside
# the check (after its re-read, before its last look), and after the last look (the window). Modes
# that break the lock (no flock, a failing flock, an unopenable directory), a lock held by the
# driver itself, two overlapping processes, and a process killed while holding the lock follow.
cat > "$W/driver.py" <<'DRIVER_PY_END'
import contextlib
import errno
import fcntl
import hashlib
import importlib.util
import io
import os
import sys
import tempfile
import time


def load(path):
    spec = importlib.util.spec_from_file_location("vw_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def call(module, argv):
    out, err, code = io.StringIO(), io.StringIO(), 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = module.main(argv) or 0
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 2
        except Exception as exc:
            code = "EXC-" + type(exc).__name__
    return code, out.getvalue()


REAL_REPLACE = os.replace


def replace_meanwhile(path):
    with open(path, "rb") as handle:
        data = handle.read()
    marker = b"## Open\n\n"
    added = "### [2026-09-06 10:00] concurrent surface — added meanwhile (minor)\n- **Status**: open\n\n"
    new = data.replace(marker, marker + added.encode("utf-8"), 1) if marker in data else data + b"written meanwhile\n"
    with open(path + ".other", "wb") as handle:
        handle.write(new)
    REAL_REPLACE(path + ".other", path)


def append_meanwhile(path):
    with open(path, "ab") as handle:
        handle.write(b"appended meanwhile by another writer\n")


def same_meanwhile(path):
    with open(path, "rb") as handle:
        data = handle.read()
    with open(path + ".other", "wb") as handle:
        handle.write(data)
    REAL_REPLACE(path + ".other", path)


def gone_meanwhile(path):
    os.unlink(path)


def unreadable_meanwhile(path):
    os.chmod(path, 0)


def temps(path):
    return sum(1 for name in os.listdir(os.path.dirname(path)) if name.startswith(".vault-writes-"))


def wait_for(paths, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(os.path.exists(p) for p in paths):
            return True
        time.sleep(0.02)
    return False


def touch(path):
    if path:
        with open(path, "a"):
            pass


class FlockFails(object):
    """A stand-in for fcntl whose flock fails with one errno, as a filesystem that refuses it."""
    LOCK_EX, LOCK_NB, LOCK_UN = fcntl.LOCK_EX, fcntl.LOCK_NB, fcntl.LOCK_UN

    def __init__(self, code):
        self.code = code

    def flock(self, descriptor, operation):
        raise OSError(self.code, os.strerror(self.code))


script, mode = sys.argv[1], sys.argv[2]
if mode == "waitfor":
    sys.exit(0 if wait_for(sys.argv[3].split(","), float(sys.argv[4])) else 1)
target, argv = sys.argv[3], sys.argv[4:]
module = load(script)
PLANTS = {"replace": replace_meanwhile, "append": append_meanwhile, "same": same_meanwhile,
          "gone": gone_meanwhile, "unreadable": unreadable_meanwhile}
if mode in PLANTS or mode == "none":
    planted, real = [], tempfile.mkstemp

    def mkstemp(*args, **kwargs):
        if mode in PLANTS and not planted:
            PLANTS[mode](target)
            planted.append(sha(target) if os.path.exists(target) and mode != "unreadable" else "-")
            if mode == "unreadable":
                os.chmod(target, 0o644)
                planted[0] = sha(target)
                os.chmod(target, 0)
        return real(*args, **kwargs)

    tempfile.mkstemp = mkstemp
    code, out = call(module, argv)
    if mode == "unreadable" and os.path.exists(target):
        os.chmod(target, 0o644)
    print("RC=%s" % code)
    print("PLANTED=%d" % len(planted))
    print("KEPT=%s" % ("yes" if planted and os.path.exists(target) and sha(target) == planted[0] else "no"))
    print("GONE=%s" % ("yes" if not os.path.exists(target) else "no"))
    print("TEMPS=%d" % temps(target))
    sys.stdout.write(out)
elif mode in ("verify-replace", "verify-append"):
    plant = replace_meanwhile if mode == "verify-replace" else append_meanwhile
    planted = []
    if hasattr(module, "last_look"):
        real_look = module.last_look

        def look(path):
            if not planted:
                plant(target)
                planted.append(sha(target))
            return real_look(path)

        module.last_look = look
        hook = "last_look"
    else:
        # Code with no verification step: the closest point between its read and its replace.
        real_mkstemp = tempfile.mkstemp

        def mkstemp(*args, **kwargs):
            if not planted:
                plant(target)
                planted.append(sha(target))
            return real_mkstemp(*args, **kwargs)

        tempfile.mkstemp = mkstemp
        hook = "mkstemp"
    code, out = call(module, argv)
    print("RC=%s" % code)
    print("HOOK=%s" % hook)
    print("PLANTED=%d" % len(planted))
    print("KEPT=%s" % ("yes" if planted and sha(target) == planted[0] else "no"))
    print("TEMPS=%d" % temps(target))
    sys.stdout.write(out)
elif mode == "late":
    marker = b"written late by another writer\n"
    landed = []

    def late_replace(src, dst, *args, **kwargs):
        if not landed and os.path.abspath(dst) == os.path.abspath(target):
            with open(target, "ab") as handle:
                handle.write(marker)
            landed.append(1)
        return REAL_REPLACE(src, dst, *args, **kwargs)

    os.replace = late_replace
    code, out = call(module, argv)
    os.replace = REAL_REPLACE
    with open(target, "rb") as handle:
        data = handle.read()
    print("RC=%s" % code)
    print("LANDED=%d" % len(landed))
    print("LOST=%s" % ("yes" if landed and marker not in data else "no"))
    sys.stdout.write(out)
elif mode == "nofcntl" or mode.startswith("flockerr:") or mode == "lockdir":
    before = sha(target)
    if mode == "nofcntl":
        module.fcntl = None
    elif mode == "lockdir":
        real_open, refused = os.open, []
        directory = os.path.dirname(os.path.abspath(target))

        def refusing_open(path, flags, *args, **kwargs):
            if not refused and os.path.abspath(path) == directory and flags == os.O_RDONLY:
                refused.append(1)
                raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), path)
            return real_open(path, flags, *args, **kwargs)

        os.open = refusing_open
    else:
        module.fcntl = FlockFails(getattr(errno, mode.split(":", 1)[1]))
    code, out = call(module, argv)
    print("RC=%s" % code)
    print("UNCHANGED=%s" % ("yes" if sha(target) == before else "no"))
    print("TEMPS=%d" % temps(target))
    sys.stdout.write(out)
elif mode in ("lock", "lock-dry"):
    module.LOCK_WAIT = 0.3
    holder = os.open(os.path.dirname(target), os.O_RDONLY)
    fcntl.flock(holder, fcntl.LOCK_EX)
    before = sha(target)
    started = time.monotonic()
    code, out = call(module, argv)
    spent = time.monotonic() - started
    print("RC=%s" % code)
    print("UNCHANGED=%s" % ("yes" if sha(target) == before else "no"))
    print("WAITED=%s" % ("yes" if spent >= 0.25 else "no"))
    sys.stdout.write(out)
    os.close(holder)
    code, out = call(module, argv)
    print("AFTER=%s" % code)
elif mode == "twice":
    cut = argv.index("--")
    module.LOCK_WAIT = 0.3
    first, _ = call(module, argv[:cut])
    second, _ = call(module, argv[cut + 1:])
    print("RC1=%s" % first)
    print("RC2=%s" % second)
elif mode == "hold":
    # Pause inside the temporary-file step (the lock held, nothing yet created) until released.
    paused, release, real = os.environ["DRIVE_PAUSED"], os.environ["DRIVE_RELEASE"], tempfile.mkstemp
    held = []

    def mkstemp(*args, **kwargs):
        if not held:
            held.append(1)
            touch(paused)
            if not wait_for([release], 30):
                os._exit(3)
        return real(*args, **kwargs)

    tempfile.mkstemp = mkstemp
    code, out = call(module, argv)
    print("RC=%s" % code)
    sys.stdout.write(out)
elif mode == "contend":
    blocked, done, real_flock = os.environ["DRIVE_BLOCKED"], os.environ["DRIVE_DONE"], fcntl.flock

    def flock(descriptor, operation):
        try:
            return real_flock(descriptor, operation)
        except BlockingIOError:
            touch(blocked)
            raise

    fcntl.flock = flock
    code, out = call(module, argv)
    touch(done)
    print("RC=%s" % code)
    sys.stdout.write(out)
elif mode == "second-replace":
    # Another writer changes text of DRIVE_PLANT_PATH (DRIVE_PLANT_OLD to DRIVE_PLANT_NEW, by its own
    # rename) as this run makes its second temporary file: the open line changed between a close's renames.
    plant_path = os.environ["DRIVE_PLANT_PATH"]
    old_text, new_text = os.environ["DRIVE_PLANT_OLD"].encode("utf-8"), os.environ["DRIVE_PLANT_NEW"].encode("utf-8")
    calls, planted, real = [], [], tempfile.mkstemp

    def mkstemp(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2 and not planted:
            with open(plant_path, "rb") as handle:
                data = handle.read()
            if data.count(old_text) == 1:
                with open(plant_path + ".other", "wb") as handle:
                    handle.write(data.replace(old_text, new_text))
                REAL_REPLACE(plant_path + ".other", plant_path)
                planted.append(1)
        return real(*args, **kwargs)

    tempfile.mkstemp = mkstemp
    code, out = call(module, argv)
    print("RC=%s" % code)
    print("PLANTED=%d" % len(planted))
    sys.stdout.write(out)
elif mode in ("appendto", "second"):
    # Another writer appends DRIVE_PLANT_TEXT to DRIVE_PLANT_PATH as this run makes its first
    # (appendto) or its second (second: the second write of a close) temporary file.
    plant_path, plant_text = os.environ["DRIVE_PLANT_PATH"], os.environ["DRIVE_PLANT_TEXT"].encode("utf-8")
    calls, planted, real = [], [], tempfile.mkstemp
    before = sha(target)

    def mkstemp(*args, **kwargs):
        calls.append(1)
        if len(calls) == (1 if mode == "appendto" else 2) and not planted:
            with open(plant_path, "ab") as handle:
                handle.write(plant_text)
            planted.append(1)
        return real(*args, **kwargs)

    tempfile.mkstemp = mkstemp
    code, out = call(module, argv)
    with open(plant_path, "rb") as handle:
        kept = plant_text in handle.read()
    print("RC=%s" % code)
    print("PLANTED=%d" % len(planted))
    print("UNCHANGED=%s" % ("yes" if sha(target) == before else "no"))
    print("PLANTKEPT=%s" % ("yes" if kept else "no"))
    print("TEMPS=%d" % temps(target))
    sys.stdout.write(out)
elif mode == "crash":
    # The run dies right after its first rename, as a kill between a close's two writes would.
    def crash_replace(src, dst, *args, **kwargs):
        REAL_REPLACE(src, dst, *args, **kwargs)
        os._exit(9)

    os.replace = crash_replace
    call(module, argv)
    sys.exit(0)
elif mode in ("log-between", "log-noeol", "log-replace", "hold-log"):
    # A point inside the log append, after its probe through the open descriptor (the lock held):
    # another writer appends there (log-between), replaces the log by rename (log-replace), or
    # the run pauses until released (hold-log).
    real_probe = module.log_probe
    marker = b"## [2026-09-06] lint | appended meanwhile by another writer\n\n"
    if mode == "log-noeol":
        marker = b"a fragment another writer left with no newline"
    acted = []

    def probe(fd):
        found = real_probe(fd)
        if not acted:
            acted.append(1)
            if mode in ("log-between", "log-noeol"):
                with open(target, "ab") as handle:
                    handle.write(marker)
            elif mode == "log-replace":
                with open(target, "rb") as handle:
                    data = handle.read()
                with open(target + ".other", "wb") as handle:
                    handle.write(data)
                REAL_REPLACE(target + ".other", target)
            else:
                touch(os.environ["DRIVE_PAUSED"])
                if not wait_for([os.environ["DRIVE_RELEASE"]], 30):
                    os._exit(3)
        return found

    module.log_probe = probe
    out, err, code = io.StringIO(), io.StringIO(), 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = module.main(argv) or 0
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 2
    with open(target, "rb") as handle:
        data = handle.read()
    print("RC=%s" % code)
    print("ACTED=%d" % len(acted))
    print("KEPT=%s" % ("yes" if marker in data else "no"))
    print("READBACK=%d" % err.getvalue().count("readback:"))
    sys.stdout.write(out.getvalue())
DRIVER_PY_END
drive() { "$PY" -B "$W/driver.py" "$S" "$@" >"$OUT" 2>&1; RC=$?; }
field() { sed -n "s/^$1=//p" "$OUT" | head -n 1; }

fixture "$W/fix"
drive replace "$REG" register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "q surface — beside another writer" --symptom "s" --cause "c" --severity minor --status "open"
eq "Q1 register add: an entry another writer added between the read and the replace refuses, saying why, and the register stays as that writer left it" "$(field RC)$(grep -c 'changed on disk since this run read it' "$OUT")$(field KEPT)" "21yes"
eq "Q1d guard: no temporary file is left beside it" "$(field TEMPS)" "0"
eq "Q1e control: the other writer's change did land during the run" "$(field PLANTED)" "1"
eq "Q1f the error is one line" "$(grep -c '^error ' "$OUT")" "1"
fixture "$W/fix"
drive append "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed beside another writer"
eq "Q2 register close: an append in place by another writer refuses, keeping it, leaving no temporary file" "$(field RC)$(field KEPT)$(field TEMPS)" "2yes0"
has "Q2b it says the file changed on disk" "changed on disk since this run read it"
fixture "$W/fix"
drive replace "$REG" register annotate --vault "$VAULT" --match "alpha surface" --kind Status --note "noted beside another writer"
eq "Q3 register annotate: a replace by another writer refuses and is kept, leaving no temporary file" "$(field RC)$(field KEPT)$(field TEMPS)" "2yes0"
fixture "$W/fix"
drive replace "$IDEAS" ideas annotate --file "$IDEAS" --item 119 --note "noted beside another writer" --date 2026-09-05
eq "Q5 ideas annotate: a change by another writer refuses and is kept, leaving no temporary file" "$(field RC)$(field KEPT)$(field TEMPS)" "2yes0"
fixture "$W/fix"
drive none "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed alone"
eq "Q6 control: the same driver with no other writer lets the close through" "$(field RC)$(field PLANTED)$(inclosed 'alpha surface')" "001"
fixture "$W/fix"
drive same "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed after a rewrite of the same bytes"
eq "Q7 guard: a rewrite of the same bytes completed before the last look is no change, so the close goes through" "$(field RC)$(field PLANTED)$(inclosed 'alpha surface')" "011"
fixture "$W/fix"
drive verify-replace "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed while another writer replaced the file"
eq "Q15 a replace by another writer inside the check (after its re-read, before its last look) refuses and is kept, leaving no temporary file" "$(field RC)$(field KEPT)$(field TEMPS)$(grep -c 'changed on disk while this run read it again' "$OUT")" "2yes01"
eq "Q15c control: the other writer acted at the last look" "$(field HOOK)$(field PLANTED)" "last_look1"
fixture "$W/fix"
drive verify-append "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed while another writer appended"
eq "Q16 an append in place inside the check refuses and is kept, leaving no temporary file" "$(field RC)$(field KEPT)$(field TEMPS)$(grep -c 'changed on disk while this run read it again' "$OUT")" "2yes01"
fixture "$W/fix"
drive gone "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed after the file was removed"
eq "Q17 a register removed between the read and the re-read refuses: none is recreated and no temporary file is left" "$(field RC)$(field GONE)$(field TEMPS)$(grep -c 'it is gone since this run read it' "$OUT")" "2yes01"
fixture "$W/fix"
if [ "$(id -u)" = "0" ]; then
	echo "  --   Q18 skipped: running as root, an unreadable file would still be read"
else
	drive unreadable "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed after the file became unreadable"
	eq "Q18 a register unreadable at the re-read refuses, its bytes kept, no temporary file left" "$(field RC)$(field KEPT)$(field TEMPS)$(grep -c 'it cannot be read again' "$OUT")" "2yes01"
fi
fixture "$W/fix"
drive late "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed as another writer wrote late"
eq "Q14 limit: a write landing after the last look, inside the rename's window, is overwritten and the close reports ok (the window the docstring states)" "$(field RC)$(field LANDED)$(field LOST)" "01yes"

fixture "$W/fix"
drive lock "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed after a wait"
eq "Q8 a lock another run holds past LOCK_WAIT refuses, writing nothing" "$(field RC)$(field UNCHANGED)$(field WAITED)" "2yesyes"
has "Q8b it says another run holds the lock" "another run of this tool has held the lock on"
eq "Q8c once the lock is free the same close goes through" "$(field AFTER)" "0"
fixture "$W/fix"
drive lock-dry "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "dry" --dry-run
eq "Q9 guard: a dry run takes no lock, so it answers at once" "$(field RC)$(field WAITED)" "0no"
fixture "$W/fix"
drive twice "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "first" -- register close --vault "$VAULT" --match "beta surface" --date 2026-09-05 --status "second"
eq "Q10 guard: a run releases its lock, so two writes in one process both go through" "$(field RC1)$(field RC2)" "00"
fixture "$W/fix"
drive nofcntl "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed with no flock"
eq "Q11 a platform without flock refuses before reading or writing anything" "$(field RC)$(grep -c 'this platform has no flock' "$OUT")$(field UNCHANGED)$(field TEMPS)" "21yes0"
for code in EOPNOTSUPP ENOLCK EIO; do
	fixture "$W/fix"
	drive "flockerr:$code" "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed with a failing flock"
	eq "Q12 a flock that fails with $code (unsupported locking, no locks left, an I/O error) refuses, writing nothing" "$(field RC)$(grep -c 'cannot lock' "$OUT")$(field UNCHANGED)$(field TEMPS)" "21yes0"
done
fixture "$W/fix"
drive lockdir "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed with an unopenable directory"
eq "Q13 a directory that cannot be opened to lock refuses, writing nothing" "$(field RC)$(grep -c 'cannot open .* to lock it' "$OUT")$(field UNCHANGED)$(field TEMPS)" "21yes0"
fixture "$W/fix"
drive nofcntl "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "dry with no flock" --dry-run
eq "Q11c control: a dry run takes no lock, so it still answers without flock" "$(field RC)$(field UNCHANGED)" "0yes"

# Two real processes overlapping on one register: the first holds the lock inside its write; the
# second must wait for it, then read the register as the first left it, so both closes land.
fixture "$W/fix"
rm -f "$W/q19.paused" "$W/q19.release" "$W/q19.blocked" "$W/q19.done"
env DRIVE_PAUSED="$W/q19.paused" DRIVE_RELEASE="$W/q19.release" "$PY" -B "$W/driver.py" "$S" hold "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "closed by the first of two runs" >"$W/q19a.out" 2>&1 &
Q19A=$!
"$PY" -B "$W/driver.py" "$S" waitfor "$W/q19.paused" 20
env DRIVE_BLOCKED="$W/q19.blocked" DRIVE_DONE="$W/q19.done" "$PY" -B "$W/driver.py" "$S" contend "$REG" register close --vault "$VAULT" --match "beta surface" --date 2026-09-05 --status "closed by the second of two runs" >"$W/q19b.out" 2>&1 &
Q19B=$!
"$PY" -B "$W/driver.py" "$S" waitfor "$W/q19.blocked,$W/q19.done" 20
Q19W=$(test -e "$W/q19.blocked" && echo waited || echo nowait)
touch "$W/q19.release"
wait "$Q19A"
wait "$Q19B"
eq "Q19 two overlapping processes: the second waits for the first's lock, and both closes land" "$(sed -n 's/^RC=//p' "$W/q19a.out")$(sed -n 's/^RC=//p' "$W/q19b.out")$Q19W$(inclosed 'alpha surface')$(inclosed 'beta surface')" "00waited11"
eq "Q19c control: the first process did pause inside its write while the second ran" "$(test -e "$W/q19.paused" && echo paused)" "paused"

# A process killed while it holds the lock: the lock dies with it, so the next run writes at once.
fixture "$W/fix"
rm -f "$W/q20.paused" "$W/q20.release"
env DRIVE_PAUSED="$W/q20.paused" DRIVE_RELEASE="$W/q20.release" "$PY" -B "$W/driver.py" "$S" hold "$REG" register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "never written" >"$W/q20a.out" 2>&1 &
Q20A=$!
"$PY" -B "$W/driver.py" "$S" waitfor "$W/q20.paused" 20
kill -9 "$Q20A"
# The shell's own notice of the killed job goes to wait's stderr, kept here rather than in the run.
wait "$Q20A" 2>"$W/q20.wait"
Q20K=$?
vw register close --vault "$VAULT" --match "beta surface" --date 2026-09-05 --status "closed after the holder died"
eq "Q20 guard: a run killed while holding the lock releases it, so the next run writes at once, and the killed run left nothing behind" "$RC$(inclosed 'beta surface')$(inopen 'alpha surface')$(temps_in "$VAULT/wiki/developments")" "0110"
eq "Q20c control: the holder was paused inside its write and then killed (wait status 137)" "$(test -e "$W/q20.paused" && echo paused)$Q20K" "paused137"

echo "== what the checks do when they cannot tell =="

fixture "$W/fix"
rm "$REG"
vw register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "x"
eq "U1 guard: a missing register is refused, and none is created" "$RC$(grep -c "no file at $REG" "$OUT")$(test -e "$REG" && echo created || echo absent)" "21absent"
fixture "$W/fix"
if [ "$(id -u)" = "0" ]; then
	echo "  --   U2 skipped: running as root, an unreadable file would still be read"
else
	chmod 000 "$REG"
	vw register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "x"
	chmod 600 "$REG"
	eq "U2 an unreadable register is refused by name, not as a bare system error" "$RC$(grep -c "^error register-close: cannot read $REG: Permission denied$" "$OUT")" "21"
	vw register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "x"
	eq "U2c control: the same close on the same register made readable again goes through" "$RC" "0"
fi
fixture "$W/fix"
cp "$REG" "$W/reg.utf8"
printf '\377\n' >> "$REG"
vw register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "x"
eq "U3 guard: a register that is not UTF-8 is refused" "$RC$(grep -c 'is not UTF-8' "$OUT")" "21"
cp "$W/reg.utf8" "$REG"
vw register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "x"
eq "U3c control: the same close without the stray byte goes through" "$RC" "0"

echo "== what the primitives may touch =="

# A sha256 manifest of every file under a tree, one line each: the proof that a run changed
# the file it named and nothing else.
manifest() {
	"$PY" -B -c 'import hashlib, os, sys
root = sys.argv[1]
for base, dirs, files in os.walk(root):
    for name in sorted(files):
        path = os.path.join(base, name)
        with open(path, "rb") as handle:
            print(hashlib.sha256(handle.read()).hexdigest(), os.path.relpath(path, root))
' "$1" | sort
}
changed_paths() { diff "$1" "$2" | awk '$1 == "<" || $1 == ">" { print $NF }' | sort -u | tr '\n' ' '; }

fixture "$W/fix"
manifest "$W/fix" > "$W/man.before"
vw log-append --vault "$VAULT" --action framework --title "sweep" --changed "c" --conflicts "none" --date 2026-09-05
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "iota — swept" --symptom "s" --cause "c" --severity minor --status "open"
vw register close --vault "$VAULT" --match "alpha surface" --date 2026-09-05 --status "swept"
vw ideas annotate --file "$IDEAS" --item 119 --note "swept" --date 2026-09-05
manifest "$W/fix" > "$W/man.after"
eq "E1 the four verbs changed the three files they were pointed at, and no other" "$(changed_paths "$W/man.before" "$W/man.after")" "IDEAS.md vault/wiki/developments/known-issues.md vault/wiki/log.md "
touch "$W/fix/planted-by-the-suite.txt"
manifest "$W/fix" > "$W/man.planted"
eq "E1c control: the same manifest catches a file the suite planted" "$(changed_paths "$W/man.after" "$W/man.planted")" "planted-by-the-suite.txt "
eq "E2 no atomic-write temp file survives the run" "$(find "$W/fix" -name '.vault-writes-*' | wc -l | tr -d ' ')" "0"
touch "$W/fix/.vault-writes-planted.tmp"
eq "E2c control: the same probe sees a planted temp file" "$(find "$W/fix" -name '.vault-writes-*' | wc -l | tr -d ' ')" "1"

# A warning is not a write: the manifest around a warned run, and around a warned dry run.
fixture "$W/fix"
manifest "$W/fix" > "$W/man.warned.before"
PLANT="$(plant_hour):3x"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "pi — warned" --symptom "at $PLANT" --cause "c" --severity minor --status "open"
manifest "$W/fix" > "$W/man.warned.after"
eq "E2d a warned write still touches only the file it was pointed at" "$(changed_paths "$W/man.warned.before" "$W/man.warned.after")" "vault/wiki/developments/known-issues.md "
eq "E2e control: the warning did fire on that run" "$(nlines "$SERR")" "1"

fixture "$W/fix"
manifest "$W/fix" > "$W/man.dry.before"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "rho — warned dry" --symptom "at $PLANT" --cause "c" --severity minor --status "open" --dry-run
manifest "$W/fix" > "$W/man.dry.after"
eq "E2f a warned dry run touches nothing at all" "$(changed_paths "$W/man.dry.before" "$W/man.dry.after")" ""
eq "E2g control: that dry run warned too" "$(nlines "$SERR")" "1"

# The two shipped files travel with the public framework: no owner path, no wikilink. Both
# patterns are built at run time so that this file does not fail its own probe.
SELF="$HERE/$(basename "$0")"
SLASH=$(printf '\057')
OWNER_PAT="${SLASH}Users${SLASH}"
LINK_PAT=$(printf '%s%s' '[' '[')
eq "E3 the script names no absolute owner path" "$(grep -c "$OWNER_PAT" "$S" || true)" "0"
eq "E4 the suite names no absolute owner path" "$(grep -c "$OWNER_PAT" "$SELF" || true)" "0"
eq "E5 the script carries no wikilink" "$(grep -cF "$LINK_PAT" "$S" || true)" "0"
eq "E6 the suite carries no wikilink" "$(grep -cF "$LINK_PAT" "$SELF" || true)" "0"
printf '%ssomebody%svault %sa-page]]\n' "$OWNER_PAT" "$SLASH" "$LINK_PAT" > "$W/hygiene-control.txt"
eq "E6c control: the same two greps hit a planted line" "$(grep -c "$OWNER_PAT" "$W/hygiene-control.txt")$(grep -cF "$LINK_PAT" "$W/hygiene-control.txt")" "11"

eq "E7 the script under test leaves no bytecode of its own" "$(find "$HERE" -name 'vault_writes*.pyc' | wc -l | tr -d ' ')" "0"
mkdir -p "$W/fix/__pycache__"
touch "$W/fix/__pycache__/vault_writes.cpython-planted.pyc"
eq "E7c control: the same probe sees a planted bytecode file" "$(find "$W/fix" -name 'vault_writes*.pyc' | wc -l | tr -d ' ')" "1"

fixture "$W/fix"
if [ "$(id -u)" = "0" ]; then
	echo "  --   E8 skipped: running as root, a read-only directory would not refuse"
else
	chmod 500 "$VAULT/wiki/developments"
	vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "s" --symptom "s" --cause "c" --severity minor --status "open"
	eq "E8 a read-only target directory is refused, not a traceback" "$RC" "2"
	eq "E9 one error line only" "$(nlines "$OUT")" "1"
	has "E10 it names the failure" "error vault-writes:"
	chmod 700 "$VAULT/wiki/developments"
	eq "E11 the register is unchanged after the refusal" "$(count "$REG" '### [')" "5"
fi

vw log-append --help
eq "E12 log-append has help" "$RC" "0"
has "E13 the help names the vault argument" "--vault"
vw register close --help
eq "E14 the nested verb has help too" "$RC" "0"
# DH1 (register 2026-11-10 23:50 b): register add and close --help say --date is the date only and the tool stamps the
# time; annotate's own --date line is the control that the probe reads a help line. Spaces and line breaks are dropped
# first, so argparse's wrapping at any width cannot split the phrase.
vw register add --help
DH_ADD=$(tr -d ' \n' < "$OUT" | grep -c -- '--dateDATEthedateonly,YYYY-MM-DD;thetoolstampsthetime')
vw register close --help
DH_CLOSE=$(tr -d ' \n' < "$OUT" | grep -c -- '--dateDATEthedateonly,YYYY-MM-DD;thetoolstampsthetime')
vw register annotate --help
DH_CTL=$(tr -d ' \n' < "$OUT" | grep -c -- '--dateDATEYYYY-MM-DD;todaywhenabsent')
eq "DH1 register add and close --help say --date takes the date only, YYYY-MM-DD, and the tool stamps the time (control: annotate's --date line)" "$DH_ADD$DH_CLOSE$DH_CTL" "111"
vw
eq "E15 no verb at all is refused" "$RC" "2"
vw register
eq "E16 a bare register is refused" "$RC" "2"

# Batch 10: the new verb touches only the file it is pointed at, and has help.
fixture "$W/fix"
manifest "$W/fix" > "$W/man.new.before"
vw register annotate --vault "$VAULT" --match "alpha surface" --kind Status --note "swept"
manifest "$W/fix" > "$W/man.new.after"
eq "E1b register annotate changed the one file it was pointed at, and no other" "$(changed_paths "$W/man.new.before" "$W/man.new.after")" "vault/wiki/developments/known-issues.md "
vw register annotate --help
eq "E18 register annotate has help naming its kinds" "$RC$(grep -c 'one of: Status Recurrence Correction' "$OUT")" "01"

# The writer has two sanctioned mutation sites. This source sweep complements the manifests:
# refusal and dry-run paths must not grow a separate write site; the planted stray must hit.
python3 -B - "$S" > "$W/write-sites.txt" 2>&1 <<'PY_WRITE_SITES'
import ast
from pathlib import Path
import re
import sys

pattern = re.compile(r'''open\([^)]*["'][wax]|os\.(?:replace|rename|remove|unlink|makedirs|mkdir|rmdir|chmod|utime|truncate)\('''
                     r'''|shutil\.|(?<!stdout)(?<!stderr)\.write(?:_text|_bytes)?\(|\.(?:touch|unlink)\(''')


def scan(source):
    spans = [(n.lineno, n.end_lineno) for n in ast.walk(ast.parse(source))
             if isinstance(n, ast.FunctionDef) and n.name in ("atomic_write", "cmd_log_append")]
    inside = stray = 0
    for number, line in enumerate(source.splitlines(), 1):
        if pattern.search(line):
            if any(lo <= number <= hi for lo, hi in spans):
                inside += 1
            else:
                stray += 1
    return inside, stray


inside, stray = scan(Path(sys.argv[1]).read_text(encoding="utf-8"))
control_inside, control_stray = scan('open(p, "w")\nos.replace(a, b)\nshutil.rmtree(d)\nhandle.write(x)\n')
print("write sites: sanctioned=%d stray=%d; control stray=%d" % (inside, stray, control_stray))
raise SystemExit(0 if inside > 0 and stray == 0 and control_inside == 0 and control_stray == 4 else 1)
PY_WRITE_SITES
if [ "$?" -eq 0 ]; then ok "E19 write-pattern sweep finds only sanctioned sites; the planted stray control hits"
else no "E19 write-pattern sweep: $(cat "$W/write-sites.txt")"; fi

echo "== decided work: the fixture pages (2026-11-12) =="

# The two decided-work pages, shaped as the vault's own: frontmatter, an intro, To build with a
# blank line inside it, Later on purpose, How this page works carrying the format's own example
# line, and a closed page with a misplaced closed line above Sources Used and `## Closed` last.
dfixture() {
	fixture "$1"
	cat > "$1/vault/wiki/developments/decided-work.md" <<'DW_END'
---
title: "Decided work"
type: development
updated: 2026-09-05
---

# Decided work

One line for each decision leaving work to build; a closed line moves to the closed page.

## To build

- [ ] **DW-20260905-1** · alpha work · decided 5 September 2026 ("go with alpha and all the rest", 10:00:00 GMT, fixture session) · to build
- [ ] **DW-20260905-2** · beta work · decided 5 September 2026 (fixture decision 2) · blocked: a fixture reason · other homes: the fixture register

- [ ] **DW-20260904-1** · gamma work, after a blank line · decided 4 September 2026 (fixture decision 3) · in run-fixture, item 2

## Later on purpose

- [ ] **DW-20260901-1** · delta work · decided 1 September 2026 (fixture decision 4) · later: v9 ("not before v9", 09:00:00 GMT, fixture session)

## How this page works

- **A line.** Example: `- [ ] **DW-29991231-1** · rename a test file · decided 31 December 2999 (fixture decision 1) · to build`.
- **Closing.** First count the id on the closed page.

## Sources Used

- the fixture

## Related

- the closed page
DW_END
	cat > "$1/vault/wiki/developments/decided-work-done.md" <<'DONE_END'
---
title: "Decided work: closed lines"
---

# Decided work: closed lines

Append-only closing history.

- [x] **DW-20260801-1** · a misplaced closed line · decided 1 August 2026 (fixture) · to build · built 2 August 2026: done

## Sources Used

- the open page

## Related

- the open page

## Closed
- [x] **DW-20260905-3** · epsilon work · decided 5 September 2026 (fixture decision 5) · to build · built 6 September 2026: done (closed 10:00 GMT by fixture)
- [-] **DW-20260902-1** · zeta work · decided 2 September 2026 (fixture) · to build · retired 3 September 2026: its purpose is gone
DONE_END
}
DW="$VAULT/wiki/developments/decided-work.md"
DONE="$VAULT/wiki/developments/decided-work-done.md"
DEV="$VAULT/wiki/developments"
NL=$(printf '\nx'); NL=${NL%x}
fsha() { "$PY" -B -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"; }
both_sha() { echo "$(fsha "$DW")$(fsha "$DONE")"; }
today_long() { "$PY" -B -c 'import time; t = time.localtime(); m = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"); print("%d %s %d" % (t.tm_mday, m[t.tm_mon - 1], t.tm_year))'; }
tomorrow() { "$PY" -B -c 'import datetime; print((datetime.date.today() + datetime.timedelta(days=1)).isoformat())'; }
oks() { sed 's#[^ (]*/##g' "$SOUT"; }
bold_count() { grep -c -F -- "**$2**" "$1" || true; }
# prepl FILE OLD NEW: an exact replacement that must find its text exactly once.
prepl() {
	"$PY" -B - "$1" "$2" "$3" <<'PREPL_END'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit("prepl: %r found %d times in %s" % (old, text.count(old), path))
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PREPL_END
	[ $? -eq 0 ] || no "fixture edit: '$2' was not found exactly once"
}
# dref NAME WANT -- ARGS...: a decided call that must refuse, exit 2, one stdout line saying WANT,
# and leave both pages byte for byte as they were.
dref() {
	name="$1"; want="$2"; shift 3
	before=$(both_sha)
	vws decided "$@"
	if [ "$RC" = 2 ] && [ "$(nlines "$SOUT")" = 1 ] && grep -qF -- "$want" "$SOUT" && [ "$(both_sha)" = "$before" ]; then ok "$name"
	else no "$name (rc $RC, stdout '$(head -c 300 "$SOUT")', pages $( [ "$(both_sha)" = "$before" ] && echo same || echo CHANGED))"; fi
}

dfixture "$W/fix"
[ "$(grep -c '^## To build$' "$DW")$(grep -c '^## Closed$' "$DONE")$(bold_count "$DONE" DW-20260905-3)$(awk 'NR==13' "$DW" | cut -c1-23)" = "111- [ ] **DW-20260905-1**" ] || { echo "PROBE FAILED: the decided-work fixture pages are not as written"; echo "FAIL 1/1"; exit 2; }

echo "== decided add =="

dfixture "$W/fix"; cp "$DW" "$W/dw.orig"; cp "$DONE" "$W/done.orig"
T0=$(now_hm); Z=$(now_zone); TL=$(today_long)
vws decided add --vault "$VAULT" --date 2026-09-05 --work "omega work" --locator "fixture decision 9" --state "to build" --by run-suite
T1=$(now_hm)
eq "DA1 an add takes the next id over both pages (1 and 2 open, 3 closed, so 4) and names it with the line" "$RC$(oks)" "0ok decided-add decided-work.md:13 DW-20260905-4"
eq "DA1b and prints no notice for a clean page and a locator with no quoted words" "$(nlines "$SERR")" "0"
eq2 "DA2 the line: id, work, the decided date with its locator, the state, and the clock's recorded stamp with today's date" "$(awk 'NR==13' "$DW")" "- [ ] **DW-20260905-4** · omega work · decided 5 September 2026 (fixture decision 9) · to build · recorded by run-suite at $T0 $Z on $TL" "- [ ] **DW-20260905-4** · omega work · decided 5 September 2026 (fixture decision 9) · to build · recorded by run-suite at $T1 $Z on $TL"
eq "DA3 the page gains exactly one line, the first under To build, its heading and blank line kept above it" "$(diff "$W/dw.orig" "$DW" | grep -c '^>')$(diff "$W/dw.orig" "$DW" | grep -c '^<')|$(awk 'NR==11' "$DW")|$(awk 'NR==12' "$DW")|$(awk 'NR==14' "$DW" | cut -c1-23)" "10|## To build||- [ ] **DW-20260905-1**"
eq "DA3b the closed page is untouched and no temporary file is left" "$(cmp -s "$W/done.orig" "$DONE" && echo same)$(temps_in "$DEV")" "same0"
dfixture "$W/fix"; grep -v -F -- '**DW-20260905-3**' "$DONE" > "$W/done.cut"; cp "$W/done.cut" "$DONE"
vws decided add --vault "$VAULT" --date 2026-09-05 --work "omega work" --locator "fixture decision 9" --state "to build" --by run-suite
eq "DA1c control: with the closed page's id 3 removed the same add takes 3, so the closed page was read" "$RC$(oks)" "0ok decided-add decided-work.md:13 DW-20260905-3"
dfixture "$W/fix"; prepl "$DW" "· blocked: a fixture reason" "· blocked: a fixture reason, as DW-20260905-9 says"
vws decided add --vault "$VAULT" --date 2026-09-05 --work "omega work" --locator "fixture decision 9" --state "to build" --by run-suite
eq "DA4 an id cited on another line (DW-20260905-9) is never reused: the add takes 10" "$RC$(oks)" "0ok decided-add decided-work.md:13 DW-20260905-10"
dfixture "$W/fix"; T0=$(now_hm)
vws decided add --vault "$VAULT" --date "$(date +%Y-%m-%d)" --work "today's work" --locator "fixture decision 10" --state "blocked: his word" --home "other homes: the suite" --by run-suite
T1=$(now_hm); TODAY_ID="DW-$(date +%Y%m%d)-1"
eq2 "DA5 a decision of today takes id 1 of its date and no date in its recorded stamp; a --home is its own field" "$(awk 'NR==13' "$DW")" "- [ ] **$TODAY_ID** · today's work · decided $TL (fixture decision 10) · blocked: his word · other homes: the suite · recorded by run-suite at $T0 $Z" "- [ ] **$TODAY_ID** · today's work · decided $TL (fixture decision 10) · blocked: his word · other homes: the suite · recorded by run-suite at $T1 $Z"

# What it refuses, each with both pages left byte for byte as they were.
dfixture "$W/fix"; printf '\n## To build\n' >> "$DW"
dref "DA6a two '## To build' headings refuse" "'## To build' is 2 lines of decided-work.md, not 1" -- add --vault "$VAULT" --date 2026-09-05 --work w --locator l --state "to build" --by b
dfixture "$W/fix"; prepl "$DW" "## To build" "## To make"
dref "DA6b no '## To build' heading refuses" "'## To build' is 0 lines of decided-work.md" -- add --vault "$VAULT" --date 2026-09-05 --work w --locator l --state "to build" --by b
dfixture "$W/fix"; prepl "$DW" "## To build" "## SWAP"; prepl "$DW" "## Later on purpose" "## To build"; prepl "$DW" "## SWAP" "## Later on purpose"
dref "DA6c Later on purpose above To build refuses" "are out of order" -- add --vault "$VAULT" --date 2026-09-05 --work w --locator l --state "to build" --by b
dfixture "$W/fix"; prepl "$DW" "- [ ] **DW-20260904-1**" "### a stray heading${NL}- [ ] **DW-20260904-1**"
dref "DA6d another heading inside the open range refuses" "is a heading inside the open range" -- add --vault "$VAULT" --date 2026-09-05 --work w --locator l --state "to build" --by b
dfixture "$W/fix"
dref "DA6e a Later state refuses: a line goes under Later only on his quoted word" "is a Later state" -- add --vault "$VAULT" --date 2026-09-05 --work w --locator l --state 'later: v9 ("not yet", 09:00:00 GMT, fixture)' --by b
dref "DA6f a state the page does not list refuses" "is none of the page's states" -- add --vault "$VAULT" --date 2026-09-05 --work w --locator l --state "whenever" --by b
dref "DA6g ' · ' in --work refuses: it would make another field" "--work carries the field separator" -- add --vault "$VAULT" --date 2026-09-05 --work "a · b" --locator l --state "to build" --by b
dref "DA6h '**' in --work refuses: it could forge a bold id" "--work carries '**'" -- add --vault "$VAULT" --date 2026-09-05 --work "a **DW-20260905-9** b" --locator l --state "to build" --by b
dref "DA6i a line break in --work refuses" "--work carries a line break" -- add --vault "$VAULT" --date 2026-09-05 --work "a${NL}b" --locator l --state "to build" --by b
dref "DA6j a decision dated after the clock's date refuses" "is after the clock's date" -- add --vault "$VAULT" --date "$(tomorrow)" --work w --locator l --state "to build" --by b
dref "DA6k ' · ' in --by refuses (finding 4)" "--by carries the field separator" -- add --vault "$VAULT" --date 2026-09-05 --work w --locator l --state "to build" --by "run · x"
dref "DA6l '**' in --by refuses (finding 4)" "--by carries '**'" -- add --vault "$VAULT" --date 2026-09-05 --work w --locator l --state "to build" --by "**DW-20260905-9**"
dref "DA6m ' · ' in --locator refuses" "--locator carries the field separator" -- add --vault "$VAULT" --date 2026-09-05 --work w --locator "a · b" --state "to build" --by b
dref "DA6n ' · ' in a --home refuses" "--home carries the field separator" -- add --vault "$VAULT" --date 2026-09-05 --work w --locator l --state "to build" --home "a · b" --by b
dfixture "$W/fix"; "$PY" -B -c 'import sys
path = sys.argv[1]
data = open(path, "rb").read().replace(b"\n", b"\r\n")
open(path, "wb").write(data)' "$DW"
dref "DA6p a page with CRLF line endings refuses: the structure check compares whole lines (finding 9)" "'## To build' is 0 lines of decided-work.md" -- add --vault "$VAULT" --date 2026-09-05 --work w --locator l --state "to build" --by b
dfixture "$W/fix"; rm "$DONE"; cp "$DW" "$W/dw.orig"
vws decided add --vault "$VAULT" --date 2026-09-05 --work w --locator l --state "to build" --by b
eq "DA6o a missing closed page refuses: its ids are a premise of the choice, and none is created" "$RC$(grep -c "no file at $DONE" "$SOUT")$(cmp -s "$W/dw.orig" "$DW" && echo same)$(test -e "$DONE" && echo created || echo absent)" "21sameabsent"

dfixture "$W/fix"
"$PY" -B - "$DW" <<'EMPTY_END'
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
start, end = text.index("## To build\n"), text.index("## Later on purpose\n")
open(path, "w", encoding="utf-8").write(text[:start] + "## To build\n\n" + text[end:])
EMPTY_END
vws decided add --vault "$VAULT" --date 2026-09-05 --work "first of an empty section" --locator l --state "to build" --by b
eq "DA7 an empty To build section: the heading, its blank line, the new line, one blank line, the next heading" "$RC|$(awk 'NR==11' "$DW")|$(awk 'NR==12' "$DW")|$(awk 'NR==13' "$DW" | cut -c1-23)|$(awk 'NR==14' "$DW")|$(awk 'NR==15' "$DW")" "0|## To build||- [ ] **DW-20260905-4**||## Later on purpose"

dfixture "$W/fix"; prepl "$DW" "- [ ] **DW-20260901-1**" "- [ ] **DW-20260904-1** · a second copy · decided 4 September 2026 (f) · to build${NL}- [ ] **DW-20260901-1**"
vws decided add --vault "$VAULT" --date 2026-09-05 --work w --locator l --state "to build" --by b
eq "DA8 an id already on two lines is named on stderr and stops nothing (the page's Malformed rule makes it a repair)" "$RC$(grep -c '^malformed: DW-20260904-1 is carried by 2 lines' "$SERR")" "01"
dfixture "$W/fix"
vws decided add --vault "$VAULT" --date 2026-09-05 --work w --locator '"go with alpha and all the rest", 10:00:00 GMT, fixture session' --state "to build" --by b
eq "DA9 his quoted words already on a line are named on stderr, the add going ahead (a later recorder adds a locator instead)" "$RC$(grep -c '^duplicate: his words "go with alpha and all the rest" already stand on decided-work.md:13' "$SERR")" "01"
dfixture "$W/fix"
vws decided add --vault "$VAULT" --date 2026-09-05 --work w --locator '"words that stand on no line at all", 11:00:00 GMT' --state "to build" --by b
eq "DA9c control: quoted words found on no line name nothing" "$RC$(grep -c '^duplicate' "$SERR" || true)" "00"

PLANT="$(plant_hour):3x"
dfixture "$W/fix"
vws decided add --vault "$VAULT" --date 2026-09-05 --work "filed at $PLANT" --locator l --state "to build" --by b
eq "DA10 a wrong clock in --work warns once, and the add goes ahead" "$RC$(grep -c '^clock:' "$SERR")" "01"
dfixture "$W/fix"
vws decided add --vault "$VAULT" --date 2026-09-05 --work w --locator "his words at $PLANT" --state "to build" --by b
eq "DA10b --locator is a citation and is not scanned" "$RC$(grep -c '^clock:' "$SERR" || true)" "00"
dfixture "$W/fix"
vws decided add --vault "$VAULT" --date 2026-09-05 --work "his words of $(plant_hour):41:07 GMT" --locator l --state "to build" --by b
eq "DA10c a time with seconds is a citation and is not scanned (finding 10)" "$RC$(grep -c '^clock:' "$SERR" || true)" "00"
dfixture "$W/fix"
vws decided add --vault "$VAULT" --date 2026-09-05 --work "his words of $(plant_hour):41 GMT" --locator l --state "to build" --by b
eq "DA10d control: the same time without seconds is scanned and warns" "$RC$(grep -c '^clock:' "$SERR")" "01"

dfixture "$W/fix"; before=$(both_sha)
vws decided add --vault "$VAULT" --date 2026-09-05 --work "omega work" --locator "fixture decision 9" --state "to build" --by run-suite --dry-run
eq "DA11 a dry run writes nothing and shows the line at its place" "$RC$( [ "$(both_sha)" = "$before" ] && echo same)$(sed -n '1p' "$SOUT" | sed 's#.*/##')$(grep -c '^| - \[ \] \*\*DW-20260905-4\*\* · omega work' "$SOUT")" "0samedecided-work.md:131"

echo "== decided status =="

dfixture "$W/fix"; cp "$DW" "$W/dw.orig"; T0=$(now_hm)
vws decided status --vault "$VAULT" --id DW-20260905-2 --note "a fixture note" --by run-suite
T1=$(now_hm)
eq "DS1 a status lands on the one line for its id" "$RC$(oks)" "0ok decided-status decided-work.md:14"
eq2 "DS1b the clause closes that line: the clock's date, time and zone, who, the note" "$(awk 'NR==14' "$DW")" "- [ ] **DW-20260905-2** · beta work · decided 5 September 2026 (fixture decision 2) · blocked: a fixture reason · other homes: the fixture register · status $TL, $T0 $Z (run-suite): a fixture note" "- [ ] **DW-20260905-2** · beta work · decided 5 September 2026 (fixture decision 2) · blocked: a fixture reason · other homes: the fixture register · status $TL, $T1 $Z (run-suite): a fixture note"
eq "DS1c exactly one line changed" "$(diff "$W/dw.orig" "$DW" | grep -c '^>')$(diff "$W/dw.orig" "$DW" | grep -c '^<')" "11"
cp "$DW" "$W/dw.one"; T0=$(now_hm)
vws decided status --vault "$VAULT" --id DW-20260905-2 --note "a second note" --by run-suite
T1=$(now_hm)
eq2 "DS1d a second status replaces the first: the line keeps one status clause (stale-information design, item 4)" "$(awk 'NR==14' "$DW")" "- [ ] **DW-20260905-2** · beta work · decided 5 September 2026 (fixture decision 2) · blocked: a fixture reason · other homes: the fixture register · status $TL, $T0 $Z (run-suite): a second note" "- [ ] **DW-20260905-2** · beta work · decided 5 September 2026 (fixture decision 2) · blocked: a fixture reason · other homes: the fixture register · status $TL, $T1 $Z (run-suite): a second note"
eq "DS1e stderr names the clause it replaced, and no other line changed" "$(grep -c -F -- 'replaced: DW-20260905-2 held 1 status clause, now one: status ' "$SERR")$(grep -c -F -- 'a fixture note' "$SERR")$(diff "$W/dw.one" "$DW" | grep -c '^<')" "111"
dfixture "$W/fix"
prepl "$DW" "· other homes: the fixture register" "· other homes: the fixture register · recorded by f at 10:00 GMT · status 6 September 2026 (by hand): an undated-time clause · status 7 September 2026, 09:00 GMT (f): a timed clause"
vws decided status --vault "$VAULT" --id DW-20260905-2 --note "the one status" --by run-suite
eq "DS1f a line holding two status clauses keeps one: both go, the new one is last, the recorded field stays" "$RC$(awk 'NR==14' "$DW" | grep -o ' · status ' | wc -l | tr -d ' ')$(awk 'NR==14' "$DW" | grep -c -F -- ' · recorded by f at 10:00 GMT · status ')$(awk 'NR==14' "$DW" | grep -c -F -- '(run-suite): the one status')$(grep -c -F -- 'held 2 status clauses, now one' "$SERR")" "01111"
eq "DS1f2 with no other field among the status clauses no kept: line is written (must not)" "$(grep -c '^kept:' "$SERR")" "0"
dfixture "$W/fix"
prepl "$DW" "· other homes: the fixture register" "· other homes: the fixture register · recorded by f at 10:00 GMT · status 6 September 2026 (by hand): a first clause · his choice of 7 September 2026 for the reader · status 8 September 2026, 09:00 GMT (f): a second clause"
vws decided status --vault "$VAULT" --id DW-20260905-2 --note "the one status" --by run-suite
eq "DS1g a field standing among the status clauses is kept, before the new clause, and named on stderr (kept:)" "$RC$(awk 'NR==14' "$DW" | grep -c -F -- ' · recorded by f at 10:00 GMT · his choice of 7 September 2026 for the reader · status ')$(grep -c '^kept: DW-20260905-2: ' "$SERR")$(grep '^kept:' "$SERR" | grep -c -F -- 'his choice of 7 September 2026 for the reader')$(grep -c -F -- 'held 2 status clauses, now one' "$SERR")" "01111"
dfixture "$W/fix"
vws decided status --vault "$VAULT" --id DW-20260901-1 --note "still later" --by run-suite
eq "DS2 a Later line takes a status too" "$RC$(oks)" "0ok decided-status decided-work.md:20"
dfixture "$W/fix"
dref "DS3a an id on no line refuses" "DW-20260905-9 is on no line of the open page; nothing written" -- status --vault "$VAULT" --id DW-20260905-9 --note n --by b
dref "DS3b a closed id refuses, naming its closed copy" "DW-20260905-3 is on no line of the open page: it is closed at decided-work-done.md:20" -- status --vault "$VAULT" --id DW-20260905-3 --note n --by b
dref "DS3c a misplaced closed line counts too (the closed page is read whole)" "it is closed at decided-work-done.md:9" -- status --vault "$VAULT" --id DW-20260801-1 --note n --by b
dref "DS3d ' · ' in --note refuses" "--note carries the field separator" -- status --vault "$VAULT" --id DW-20260905-2 --note "a · b" --by b
dref "DS3e '**' in --note refuses" "--note carries '**'" -- status --vault "$VAULT" --id DW-20260905-2 --note "see **DW-20260905-9**" --by b
dref "DS3f ' · ' in --by refuses (finding 4)" "--by carries the field separator" -- status --vault "$VAULT" --id DW-20260905-2 --note n --by "run · x"
dref "DS3g '**' in --by refuses (finding 4)" "--by carries '**'" -- status --vault "$VAULT" --id DW-20260905-2 --note n --by "**DW-20260905-9**"
dref "DS3h an id with a leading zero is no id" "is not DW-YYYYMMDD-n" -- status --vault "$VAULT" --id DW-20260905-02 --note n --by b
dfixture "$W/fix"; prepl "$DW" "- [ ] **DW-20260901-1**" "- [ ] **DW-20260905-2** · a second copy · decided 5 September 2026 (f) · to build${NL}- [ ] **DW-20260901-1**"
dref "DS3i an id on two lines refuses: two identities" "DW-20260905-2 is carried by 2 lines of the open page (lines 14, 20)" -- status --vault "$VAULT" --id DW-20260905-2 --note n --by b
dfixture "$W/fix"; prepl "$DW" "- **Closing.** First count the id on the closed page." "- **Closing.** First count the id on the closed page.${NL}- [ ] **DW-20260801-2** · a misplaced open line · decided 1 August 2026 (f) · to build"
dref "DS3j a line outside the open range refuses as misplaced" "stands outside the open range" -- status --vault "$VAULT" --id DW-20260801-2 --note n --by b
dfixture "$W/fix"; prepl "$DW" "- [ ] **DW-20260905-2**" "- [x] **DW-20260905-2**"
dref "DS3k a line carrying the id that is not its open line refuses" "carries DW-20260905-2 but is not its open line" -- status --vault "$VAULT" --id DW-20260905-2 --note n --by b
dfixture "$W/fix"; before=$(both_sha)
vws decided status --vault "$VAULT" --id DW-20260905-2 --note n --by b --dry-run
eq "DS4 a dry run writes nothing" "$RC$( [ "$(both_sha)" = "$before" ] && echo same)$(grep -c '^dry-run decided-status ' "$SOUT")" "0same1"

echo "== decided state (finding 5) =="

dfixture "$W/fix"; cp "$DW" "$W/dw.orig"; T0=$(now_hm)
vws decided state --vault "$VAULT" --id DW-20260905-2 --state "in run-suite, item 4" --note "taken by the plan of record" --by run-suite
T1=$(now_hm)
eq "DS5 a state edit lands on the one line for its id" "$RC$(oks)" "0ok decided-state decided-work.md:14"
eq2 "DS5b field 4 is replaced and the status clause gives the note alone, not the earlier state (stale-information design, item 4)" "$(awk 'NR==14' "$DW")" "- [ ] **DW-20260905-2** · beta work · decided 5 September 2026 (fixture decision 2) · in run-suite, item 4 · other homes: the fixture register · status $TL, $T0 $Z (run-suite): taken by the plan of record" "- [ ] **DW-20260905-2** · beta work · decided 5 September 2026 (fixture decision 2) · in run-suite, item 4 · other homes: the fixture register · status $TL, $T1 $Z (run-suite): taken by the plan of record"
eq "DS5c exactly one line changed" "$(diff "$W/dw.orig" "$DW" | grep -c '^>')$(diff "$W/dw.orig" "$DW" | grep -c '^<')" "11"
vws decided state --vault "$VAULT" --id DW-20260905-2 --state "to build: released by the suite" --note "released again" --by run-suite
eq "DS5d a second state edit keeps one status clause, the newer, and no earlier state in it" "$RC$(awk 'NR==14' "$DW" | grep -o ' · status ' | wc -l | tr -d ' ')$(awk 'NR==14' "$DW" | grep -c -F -- '(run-suite): released again')$(awk 'NR==14' "$DW" | grep -c -F -- 'earlier state')" "0110"
dfixture "$W/fix"
vws decided state --vault "$VAULT" --id DW-20260904-1 --state "to build: released by run-suite's close" --note "released at the close" --by run-suite
eq "DS6 a returned line takes 'to build: REASON'" "$RC$(awk 'NR==16' "$DW" | grep -c ' · to build: released by run-suite.s close · status ')" "01"
dfixture "$W/fix"
vws decided state --vault "$VAULT" --id DW-20260901-1 --state 'later: v10 ("not before v10", 09:30:00 GMT, fixture session)' --note "his trigger moved" --by run-suite
eq "DS7 a Later line takes a new Later state" "$RC$(awk 'NR==20' "$DW" | grep -c ' · later: v10 ')" "01"
dfixture "$W/fix"
dref "DS7b a Later line refuses any other state: moving it back is not a state edit" "is not a Later state" -- state --vault "$VAULT" --id DW-20260901-1 --state "to build" --note n --by b
dref "DS7c a To build line refuses a Later state" "is a Later state" -- state --vault "$VAULT" --id DW-20260905-2 --state 'later: v9 ("x y z", 09:00:00 GMT, f)' --note n --by b
dref "DS7d the same state again refuses" "already reads 'in run-fixture, item 2'" -- state --vault "$VAULT" --id DW-20260904-1 --state "in run-fixture, item 2" --note n --by b
dref "DS7e an elsewhere state without its word or rule refuses" "is none of the page's states" -- state --vault "$VAULT" --id DW-20260905-2 --state "elsewhere: a holder" --note n --by b
dref "DS7f '**' in --by refuses (finding 4)" "--by carries '**'" -- state --vault "$VAULT" --id DW-20260905-2 --state "to build" --note n --by "**DW-20260905-9**"
dfixture "$W/fix"; prepl "$DW" "· blocked: a fixture reason" "· planned for 8 September"
dref "DS7g a field 4 the page does not list refuses: the verb cannot tell what it replaces" "field 4 of line 14 reads 'planned for 8 September'" -- state --vault "$VAULT" --id DW-20260905-2 --state "to build" --note n --by b
dfixture "$W/fix"; before=$(both_sha)
vws decided state --vault "$VAULT" --id DW-20260905-2 --state "to build" --note n --by b --dry-run
eq "DS8 a dry run writes nothing" "$RC$( [ "$(both_sha)" = "$before" ] && echo same)$(grep -c '^dry-run decided-state ' "$SOUT")" "0same1"

echo "== decided close =="

dfixture "$W/fix"; cp "$DW" "$W/dw.orig"; cp "$DONE" "$W/done.orig"; T0=$(now_hm)
vws decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence "built and tested by the suite" --by run-suite
T1=$(now_hm)
eq "DC1 a close (count 0) lands the closed line last on the closed page and names where the open copy was" "$RC$(oks)" "0ok decided-close decided-work-done.md:22 (open copy removed from decided-work.md:14)"
eq2 "DC1b the closed line: the complete open line, boxed [x], then the closing clause with the clock's stamp" "$(tail -n 1 "$DONE")" "- [x] **DW-20260905-2** · beta work · decided 5 September 2026 (fixture decision 2) · blocked: a fixture reason · other homes: the fixture register · built $TL: built and tested by the suite (closed $T0 $Z by run-suite)" "- [x] **DW-20260905-2** · beta work · decided 5 September 2026 (fixture decision 2) · blocked: a fixture reason · other homes: the fixture register · built $TL: built and tested by the suite (closed $T1 $Z by run-suite)"
eq "DC1c the closed page gains one line and loses none; the open page loses the one line and gains none" "$(diff "$W/done.orig" "$DONE" | grep -c '^>')$(diff "$W/done.orig" "$DONE" | grep -c '^<')$(diff "$W/dw.orig" "$DW" | grep -c '^<')$(diff "$W/dw.orig" "$DW" | grep -c '^>')" "1010"
eq "DC1d the id is on the closed page once, on the open page never, and no temporary file is left" "$(bold_count "$DONE" DW-20260905-2)$(bold_count "$DW" DW-20260905-2)$(temps_in "$DEV")" "100"
dfixture "$W/fix"; cp "$DW" "$W/dw.orig"
vws decided close --vault "$VAULT" --id DW-20260904-1 --kind built --evidence e --by run-suite
eq "DC2 a line between two blank lines goes with one of them, so no double blank is left" "$RC$(diff "$W/dw.orig" "$DW" | grep -c '^<')$(diff "$W/dw.orig" "$DW" | grep -c '^>')|$(awk 'NR==15' "$DW")|$(awk 'NR==16' "$DW")" "020||## Later on purpose"
dfixture "$W/fix"
vws decided close --vault "$VAULT" --id DW-20260905-1 --kind retired --evidence "its purpose is met by DW-20260905-2's work" --by run-suite
eq "DC3 a retired line is boxed [-]" "$RC$(tail -n 1 "$DONE" | grep -c "^- \[-\] \*\*DW-20260905-1\*\* · alpha work · .* · retired $TL: its purpose is met")" "01"
dfixture "$W/fix"
vws decided close --vault "$VAULT" --id DW-20260901-1 --kind dropped --evidence '"drop it now" (12:00:00 GMT, fixture session)' --by run-suite
eq "DC3b a Later line closes, and a dropped line carries his words, boxed [-]" "$RC$(tail -n 1 "$DONE" | grep -c "^- \[-\] \*\*DW-20260901-1\*\* · delta work .* · dropped $TL: \"drop it now\" (12:00:00 GMT, fixture session) (closed ")$(bold_count "$DW" DW-20260901-1)" "010"
dfixture "$W/fix"
dref "DC3c a dropped close without his quoted words refuses" "a dropped line's --evidence is his words" -- close --vault "$VAULT" --id DW-20260901-1 --kind dropped --evidence "no longer wanted" --by b

# Count 1: the closed line is there already (a half-close, or a close written by hand).
BODY=$(awk 'NR==14' "$W/dw.orig" | cut -c7-)
dfixture "$W/fix"; printf -- '- [x] %s · built 7 September 2026: earlier evidence (closed 10:00 GMT by fixture)\n' "$BODY" >> "$DONE"; cp "$DONE" "$W/done.one"; cp "$DW" "$W/dw.orig"
dref "DC4 (FX5) count 1 with other closing evidence refuses as a repair: the Closing rule confirms the same decision, work and closing evidence" "closes DW-20260905-2 with the evidence 'earlier evidence', not this run's 'other evidence'" -- close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence "other evidence" --by run-suite
dfixture "$W/fix"; cp "$W/done.one" "$DONE"
vws decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence "earlier evidence" --by run-suite
eq "DC4c (FX5 control) count 1 with the same box, kind and evidence: only the open copy goes, the closed page untouched, nothing on stderr" "$RC$(cmp -s "$W/done.one" "$DONE" && echo same)$(bold_count "$DW" DW-20260905-2)$(diff "$W/dw.orig" "$DW" | grep -c '^<')$(nlines "$SERR")" "0same010"
dfixture "$W/fix"; printf -- '- [-] %s · retired 7 September 2026: gone\n' "$BODY" >> "$DONE"
dref "DC5 count 1 with another box refuses as a repair (finding 3)" "closes DW-20260905-2 with [-], not the [x] that --kind built writes" -- close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by b
dref "DC6 count 1 with the same box but another kind refuses as a repair (finding 3)" "not 'dropped DATE: …' as --kind asks" -- close --vault "$VAULT" --id DW-20260905-2 --kind dropped --evidence '"drop" (12:00:00 GMT, f)' --by b
dfixture "$W/fix"; printf -- '- [x] %s · built 7 September 2026: e\n' "$(printf '%s' "$BODY" | sed 's/beta work/beta works/')" >> "$DONE"
dref "DC7 count 1 with another body refuses: not the same decision and work" "with a body that differs from the open copy at character" -- close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by b
dfixture "$W/fix"; printf -- '- [x] %s · built 7 September 2026: e\n- [x] %s · built 7 September 2026: e\n' "$BODY" "$BODY" >> "$DONE"
dref "DC8 count 2 refuses as a repair" "DW-20260905-2 is carried by 2 lines of decided-work-done.md" -- close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by b
dfixture "$W/fix"; prepl "$DONE" "## Closed" "## Shut"
dref "DC9a a closed page without '## Closed' refuses" "'## Closed' is 0 lines of decided-work-done.md" -- close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by b
dfixture "$W/fix"; printf '\n## Closed\n' >> "$DONE"
dref "DC9b '## Closed' twice refuses" "'## Closed' is 2 lines of decided-work-done.md" -- close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by b
dfixture "$W/fix"; printf '\n## Notes\n' >> "$DONE"
dref "DC9c a heading below '## Closed' refuses: the append would land under it" "is a heading below '## Closed'" -- close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by b
dfixture "$W/fix"
dref "DC10 an id already closed refuses, naming its closed copy" "it is closed at decided-work-done.md:20" -- close --vault "$VAULT" --id DW-20260905-3 --kind built --evidence e --by b
dref "DC11a ' · ' in --by refuses (finding 4)" "--by carries the field separator" -- close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by "run · x"
dref "DC11b '**' in --by refuses (finding 4)" "--by carries '**'" -- close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by "**DW-20260905-9**"
dref "DC11c ' · ' in --evidence refuses" "--evidence carries the field separator" -- close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence "a · b" --by b
dfixture "$W/fix"; before=$(both_sha)
vws decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by b --dry-run
eq "DC12 a dry run writes nothing to either page" "$RC$( [ "$(both_sha)" = "$before" ] && echo same)$(grep -c '^dry-run decided-close ' "$SOUT")" "0same1"

echo "== decided writes beside another writer, and the race (D21 (a), extended) =="

dfixture "$W/fix"
drive replace "$DW" decided add --vault "$VAULT" --date 2026-09-05 --work "q work" --locator q --state "to build" --by run-suite
eq "DQ1 decided add: a change between the read and the replace refuses, keeps that change, leaves no temporary file" "$(field RC)$(field KEPT)$(field TEMPS)$(field PLANTED)$(grep -c 'changed on disk since this run read it' "$OUT")" "2yes011"
dfixture "$W/fix"
drive none "$DW" decided add --vault "$VAULT" --date 2026-09-05 --work "q work" --locator q --state "to build" --by run-suite
eq "DQ1c control: the same driver with no other writer lets the add through" "$(field RC)$(field PLANTED)$(bold_count "$DW" DW-20260905-4)" "001"
dfixture "$W/fix"
DRIVE_PLANT_PATH="$DONE"; DRIVE_PLANT_TEXT="- [x] **DW-20260905-7** · closed meanwhile · decided 5 September 2026 (f) · to build · built 6 September 2026: x${NL}"; export DRIVE_PLANT_PATH DRIVE_PLANT_TEXT
drive appendto "$DW" decided add --vault "$VAULT" --date 2026-09-05 --work "q work" --locator q --state "to build" --by run-suite
eq "DQ2 decided add: an id of its date landing on the closed page before the last look refuses, the open page untouched (finding 9)" "$(field RC)$(field UNCHANGED)$(field PLANTKEPT)$(field TEMPS)$(grep -c 'now carries DW-20260905-7, at or above the id this run chose (DW-20260905-4)' "$OUT")" "2yesyes01"
dfixture "$W/fix"
DRIVE_PLANT_TEXT="a line with no id, written meanwhile${NL}"; export DRIVE_PLANT_TEXT
drive appendto "$DW" decided add --vault "$VAULT" --date 2026-09-05 --work "q work" --locator q --state "to build" --by run-suite
eq "DQ2c control: another change of the closed page stops nothing: the premise is a fact, not its bytes" "$(field RC)$(field PLANTED)$(bold_count "$DW" DW-20260905-4)" "011"
dfixture "$W/fix"
drive append "$DW" decided status --vault "$VAULT" --id DW-20260905-2 --note n --by b
eq "DQ3 decided status: an append in place by another writer refuses and is kept, leaving no temporary file" "$(field RC)$(field KEPT)$(field TEMPS)" "2yes0"
dfixture "$W/fix"
drive verify-replace "$DW" decided state --vault "$VAULT" --id DW-20260905-2 --state "to build" --note n --by b
eq "DQ3b decided state: a replace inside the check refuses and is kept" "$(field RC)$(field KEPT)$(field TEMPS)$(field HOOK)" "2yes0last_look"

# The half-close: the open page changes between the close's two renames.
dfixture "$W/fix"
DRIVE_PLANT_PATH="$DW"; DRIVE_PLANT_TEXT="written between the two renames${NL}"; export DRIVE_PLANT_PATH DRIVE_PLANT_TEXT
drive second "$DW" decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by run-suite
eq "DQ4 a close whose open page changes after its first rename: exit 2, the closed line kept, the open copy kept, and the error says how to finish" "$(field RC)$(field PLANTED)$(bold_count "$DONE" DW-20260905-2)$(bold_count "$DW" DW-20260905-2)$(grep -c 'the closed line landed at .*decided-work-done.md:22, but .* so the open copy stays at .*decided-work.md:14. Re-run the same command' "$OUT")" "21111"
vws decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by run-suite
eq "DQ4b the same command run again converges: one closed copy, no open copy, the other writer's line kept" "$RC$(bold_count "$DONE" DW-20260905-2)$(bold_count "$DW" DW-20260905-2)$(count "$DW" 'written between the two renames')$(temps_in "$DEV")" "01010"

# The crash: the run dies right after its first rename (finding 3).
dfixture "$W/fix"
"$PY" -B "$W/driver.py" "$S" crash "$DW" decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by run-suite >"$OUT" 2>&1
CRASH=$?
eq "DQ5c control: the run died after its first rename (exit 9), the closed line landed and the open copy stayed" "$CRASH$(bold_count "$DONE" DW-20260905-2)$(bold_count "$DW" DW-20260905-2)" "911"
vws decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by run-suite
eq "DQ5 after the crash the same command converges: one closed copy, no open copy, no temporary file" "$RC$(bold_count "$DONE" DW-20260905-2)$(bold_count "$DW" DW-20260905-2)$(temps_in "$DEV")" "0100"

# Two real processes: two adds of one date, the first paused inside its write with the lock held.
dfixture "$W/fix"
rm -f "$W/dr1.paused" "$W/dr1.release" "$W/dr1.blocked" "$W/dr1.done"
env DRIVE_PAUSED="$W/dr1.paused" DRIVE_RELEASE="$W/dr1.release" "$PY" -B "$W/driver.py" "$S" hold "$DW" decided add --vault "$VAULT" --date 2026-09-05 --work "first of two" --locator q --state "to build" --by run-suite >"$W/dr1a.out" 2>&1 &
DR1A=$!
"$PY" -B "$W/driver.py" "$S" waitfor "$W/dr1.paused" 20
env DRIVE_BLOCKED="$W/dr1.blocked" DRIVE_DONE="$W/dr1.done" "$PY" -B "$W/driver.py" "$S" contend "$DW" decided add --vault "$VAULT" --date 2026-09-05 --work "second of two" --locator q --state "to build" --by run-suite >"$W/dr1b.out" 2>&1 &
DR1B=$!
"$PY" -B "$W/driver.py" "$S" waitfor "$W/dr1.blocked,$W/dr1.done" 20
DR1W=$(test -e "$W/dr1.blocked" && echo waited || echo nowait)
touch "$W/dr1.release"
wait "$DR1A"
wait "$DR1B"
eq "DR1 two overlapping adds of one date: the second waits, then both land with ids 4 and 5, each once" "$(sed -n 's/^RC=//p' "$W/dr1a.out")$(sed -n 's/^RC=//p' "$W/dr1b.out")$DR1W$(grep -c -F '**DW-20260905-4** · first of two' "$DW")$(grep -c -F '**DW-20260905-5** · second of two' "$DW")" "00waited11"
eq "DR1c control: the first process did pause inside its write" "$(test -e "$W/dr1.paused" && echo paused)" "paused"

# Two real processes closing one id: the first lands, the second reads it closed and refuses.
dfixture "$W/fix"
rm -f "$W/dr2.paused" "$W/dr2.release" "$W/dr2.blocked" "$W/dr2.done"
env DRIVE_PAUSED="$W/dr2.paused" DRIVE_RELEASE="$W/dr2.release" "$PY" -B "$W/driver.py" "$S" hold "$DW" decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence first --by run-suite >"$W/dr2a.out" 2>&1 &
DR2A=$!
"$PY" -B "$W/driver.py" "$S" waitfor "$W/dr2.paused" 20
env DRIVE_BLOCKED="$W/dr2.blocked" DRIVE_DONE="$W/dr2.done" "$PY" -B "$W/driver.py" "$S" contend "$DW" decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence second --by run-suite >"$W/dr2b.out" 2>&1 &
DR2B=$!
"$PY" -B "$W/driver.py" "$S" waitfor "$W/dr2.blocked,$W/dr2.done" 20
DR2W=$(test -e "$W/dr2.blocked" && echo waited || echo nowait)
touch "$W/dr2.release"
wait "$DR2A"
wait "$DR2B"
eq "DR2 two overlapping closes of one id: the first lands, the second waits and refuses, and the closed page carries the id once" "$(sed -n 's/^RC=//p' "$W/dr2a.out")$(sed -n 's/^RC=//p' "$W/dr2b.out")$DR2W$(grep -c 'is on no line of the open page: it is closed at decided-work-done.md:22' "$W/dr2b.out")$(bold_count "$DONE" DW-20260905-2)" "02waited11"
eq "DR2c control: the first process did pause, and the line closed is the first's" "$(test -e "$W/dr2.paused" && echo paused)$(grep -c -F ': first (closed ' "$DONE")$(grep -c -F ': second (closed ' "$DONE" || true)" "paused10"

dfixture "$W/fix"
drive late "$DW" decided add --vault "$VAULT" --date 2026-09-05 --work "late" --locator q --state "to build" --by run-suite
eq "DL1 limit: a write landing after the last look, inside the rename's window, is overwritten and the add reports ok (the window the docstring states)" "$(field RC)$(field LANDED)$(field LOST)" "01yes"
dfixture "$W/fix"; done_before=$(fsha "$DONE")
drive lock "$DW" decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by b
eq "DL2 a lock another run holds past LOCK_WAIT refuses a close, writing neither page; once free it goes through" "$(field RC)$(field UNCHANGED)$(field WAITED)$( [ "$(sed -n 's/^AFTER=//p' "$OUT")" = 0 ] && echo after)" "2yesyesafter"
eq "DL2b it says another run holds the lock" "$(grep -c 'another run of this tool has held the lock on' "$OUT")" "1"
dfixture "$W/fix"
drive nofcntl "$DW" decided status --vault "$VAULT" --id DW-20260905-2 --note n --by b
eq "DL3 a platform without flock refuses a decided write before reading or writing" "$(field RC)$(grep -c 'this platform has no flock' "$OUT")$(field UNCHANGED)$(field TEMPS)" "21yes0"
dfixture "$W/fix"
rm -f "$W/dl4.paused" "$W/dl4.release"
env DRIVE_PAUSED="$W/dl4.paused" DRIVE_RELEASE="$W/dl4.release" "$PY" -B "$W/driver.py" "$S" hold "$DW" decided add --vault "$VAULT" --date 2026-09-05 --work "never written" --locator q --state "to build" --by b >"$W/dl4a.out" 2>&1 &
DL4A=$!
"$PY" -B "$W/driver.py" "$S" waitfor "$W/dl4.paused" 20
kill -9 "$DL4A"
wait "$DL4A" 2>"$W/dl4.wait"
DL4K=$?
vws decided add --vault "$VAULT" --date 2026-09-05 --work "after the holder died" --locator q --state "to build" --by b
eq "DL4 a decided run killed while holding the lock releases it: the next add writes at once, the killed one left nothing" "$RC$(count "$DW" 'never written')$(grep -c -F '**DW-20260905-4** · after the holder died' "$DW")$(temps_in "$DEV")" "0010"
eq "DL4c control: the holder was paused inside its write and then killed (wait status 137)" "$(test -e "$W/dl4.paused" && echo paused)$DL4K" "paused137"

echo "== log-append: the lock, the probe through the open descriptor, the read-back (finding 2) =="

fixture "$W/fix"
drive log-between "$LOG" log-append --vault "$VAULT" --action lint --title "logged beside another writer" --changed c --conflicts none --date 2026-09-05
REAL=$(grep -n -F '## [2026-09-05] lint | logged beside another writer' "$LOG" | cut -d: -f1)
FOREIGN=$(grep -n -F 'appended meanwhile by another writer' "$LOG" | cut -d: -f1)
eq "LG1 another program's append between the probe and the write: the entry lands after it, nothing lost, ok at the real line with one readback line, exit 0" "$(field RC)$(field ACTED)$(field KEPT)$(field READBACK)$(count "$LOG" '| logged beside another writer')$( [ "$FOREIGN" -lt "$REAL" ] && echo after)$(grep -c "^ok log-append .*log.md:$REAL\$" "$OUT")" "01yes11after1"
fixture "$W/fix"
vws log-append --vault "$VAULT" --action lint --title "logged alone" --changed c --conflicts none --date 2026-09-05
eq "LG1c control: alone, the append reports the line it landed on and prints nothing on stderr" "$RC$(nlines "$SERR")$(grep -c "log.md:$(grep -n -F '| logged alone' "$LOG" | cut -d: -f1)\$" "$SOUT")" "001"
fixture "$W/fix"
drive log-replace "$LOG" log-append --vault "$VAULT" --action lint --title "logged into a replaced log" --changed c --conflicts none --date 2026-09-05
eq "LG2 a log replaced after the open: the entry is not in the log as it stands, and the error says so" "$(field RC)$(field ACTED)$(count "$LOG" '| logged into a replaced log')$(grep -c 'the entry is not in the log as it now stands' "$OUT")" "2101"
vws log-append --vault "$VAULT" --action lint --title "logged into a replaced log" --changed c --conflicts none --date 2026-09-05
eq "LG2b the re-run it asks for writes the entry once" "$RC$(count "$LOG" '| logged into a replaced log')" "01"

fixture "$W/fix"
rm -f "$W/lg3.paused" "$W/lg3.release" "$W/lg3.blocked" "$W/lg3.done"
env DRIVE_PAUSED="$W/lg3.paused" DRIVE_RELEASE="$W/lg3.release" "$PY" -B "$W/driver.py" "$S" hold-log "$LOG" log-append --vault "$VAULT" --action lint --title "first of two appends" --changed c --conflicts none --date 2026-09-05 >"$W/lg3a.out" 2>&1 &
LG3A=$!
"$PY" -B "$W/driver.py" "$S" waitfor "$W/lg3.paused" 20
env DRIVE_BLOCKED="$W/lg3.blocked" DRIVE_DONE="$W/lg3.done" "$PY" -B "$W/driver.py" "$S" contend "$LOG" log-append --vault "$VAULT" --action lint --title "second of two appends" --changed c --conflicts none --date 2026-09-05 >"$W/lg3b.out" 2>&1 &
LG3B=$!
"$PY" -B "$W/driver.py" "$S" waitfor "$W/lg3.blocked,$W/lg3.done" 20
LG3W=$(test -e "$W/lg3.blocked" && echo waited || echo nowait)
touch "$W/lg3.release"
wait "$LG3A"
wait "$LG3B"
L1=$(grep -n -F '| first of two appends' "$LOG" | cut -d: -f1)
L2=$(grep -n -F '| second of two appends' "$LOG" | cut -d: -f1)
eq "LG3 two overlapping appends: the second waits for the first's lock, both land whole, each ok line names its own line" "$(sed -n 's/^RC=//p' "$W/lg3a.out")$(sed -n 's/^RC=//p' "$W/lg3b.out")$LG3W$(grep -c "log.md:$L1\$" "$W/lg3a.out")$(grep -c "log.md:$L2\$" "$W/lg3b.out")$(sed -n 's/^READBACK=//p' "$W/lg3a.out")" "00waited110"
eq "LG3b one blank line between the first entry's Conflicts bullet and the second heading" "$(awk -v a="$L2" 'NR==a-2 || NR==a-1' "$LOG" | tr '\n' '|')" "- **Conflicts**: none||"
eq "LG3c control: the first process did pause inside its probe with the lock held" "$(test -e "$W/lg3.paused" && echo paused)" "paused"
fixture "$W/fix"
drive lock "$LOG" log-append --vault "$VAULT" --action lint --title "held" --changed c --conflicts none --date 2026-09-05
eq "LG4 a lock another run holds past LOCK_WAIT refuses the append, writing nothing; once free it goes through" "$(field RC)$(field UNCHANGED)$(field WAITED)$(sed -n 's/^AFTER=//p' "$OUT")" "2yesyes0"
fixture "$W/fix"
drive lock-dry "$LOG" log-append --vault "$VAULT" --action lint --title "held" --changed c --conflicts none --date 2026-09-05 --dry-run
eq "LG5 a dry-run append takes no lock, so it answers at once" "$(field RC)$(field WAITED)" "0no"
fixture "$W/fix"
drive nofcntl "$LOG" log-append --vault "$VAULT" --action lint --title "no flock" --changed c --conflicts none --date 2026-09-05
eq "LG6 a platform without flock refuses the append (Q3: refuse, as every other write)" "$(field RC)$(grep -c 'this platform has no flock' "$OUT")$(field UNCHANGED)" "21yes"
fixture "$W/fix"
rm -f "$W/lg7.paused" "$W/lg7.release"
env DRIVE_PAUSED="$W/lg7.paused" DRIVE_RELEASE="$W/lg7.release" "$PY" -B "$W/driver.py" "$S" hold-log "$LOG" log-append --vault "$VAULT" --action lint --title "never appended" --changed c --conflicts none --date 2026-09-05 >"$W/lg7a.out" 2>&1 &
LG7A=$!
"$PY" -B "$W/driver.py" "$S" waitfor "$W/lg7.paused" 20
kill -9 "$LG7A"
wait "$LG7A" 2>"$W/lg7.wait"
LG7K=$?
vws log-append --vault "$VAULT" --action lint --title "after the holder died" --changed c --conflicts none --date 2026-09-05
eq "LG7 an append killed while holding the lock releases it: the next append writes at once, and nothing of the killed one landed" "$RC$(count "$LOG" 'never appended')$(count "$LOG" '| after the holder died')" "001"
eq "LG7c control: the holder was paused inside its probe and then killed (wait status 137)" "$(test -e "$W/lg7.paused" && echo paused)$LG7K" "paused137"
fixture "$W/fix"
if [ "$(id -u)" = "0" ]; then
	echo "  --   LG8 skipped: running as root, an unreadable log would still open"
else
	chmod 000 "$LOG"
	vws log-append --vault "$VAULT" --action lint --title "unopenable" --changed c --conflicts none --date 2026-09-05
	chmod 600 "$LOG"
	eq "LG8 a log that cannot be opened to append refuses by name, writing nothing" "$RC$(grep -c 'cannot open .*log.md to append' "$SOUT")$(count "$LOG" 'unopenable')" "210"
fi

echo "== what the decided verbs and the log append may touch =="

dfixture "$W/fix"
manifest "$W/fix" > "$W/man.d0"
vw decided add --vault "$VAULT" --date 2026-09-05 --work "swept" --locator q --state "to build" --by b
vw decided status --vault "$VAULT" --id DW-20260905-1 --note "swept" --by b
vw decided state --vault "$VAULT" --id DW-20260905-2 --state "to build" --note "swept" --by b
manifest "$W/fix" > "$W/man.d1"
eq "EP1 add, status and state changed the open page and no other file" "$(changed_paths "$W/man.d0" "$W/man.d1")" "vault/wiki/developments/decided-work.md "
vw decided close --vault "$VAULT" --id DW-20260905-1 --kind built --evidence "swept" --by b
manifest "$W/fix" > "$W/man.d2"
eq "EP2 a close changed the two decided-work pages and no other file" "$(changed_paths "$W/man.d1" "$W/man.d2")" "vault/wiki/developments/decided-work-done.md vault/wiki/developments/decided-work.md "
vw log-append --vault "$VAULT" --action lint --title "swept" --changed c --conflicts none --date 2026-09-05
manifest "$W/fix" > "$W/man.d3"
eq "EP3 the log append changed the log and no other file" "$(changed_paths "$W/man.d2" "$W/man.d3")" "vault/wiki/log.md "
eq "EP4 no temporary file survives the decided writes" "$(find "$W/fix" -name '.vault-writes-*' | wc -l | tr -d ' ')" "0"
MODE0=$(ls -l "$REG" | cut -c1-10)
"$PY" -B -c 'import sys
with open(sys.argv[1], "r+b") as handle:
    handle.seek(2)
    byte = handle.read(1)
    handle.seek(2)
    handle.write(bytes([byte[0] ^ 1]))' "$REG"
manifest "$W/fix" > "$W/man.d4"
eq "EP4c control: one byte changed in a sibling of the same folder under the same permissions is caught" "$(changed_paths "$W/man.d3" "$W/man.d4")$( [ "$(ls -l "$REG" | cut -c1-10)" = "$MODE0" ] && echo samemode)" "vault/wiki/developments/known-issues.md samemode"

vw decided add --help
eq "EP5 decided add has help naming its locator" "$RC$(grep -c -- 'where his words are' "$OUT")" "01"
vw decided
eq "EP6 a bare decided is refused" "$RC" "2"

echo "== fixes from the independent check (2026-11-12) =="

# FX2: a line keeps its own terminator. One line of the open page ends in CRLF (the rest LF); each verb
# must leave that CR as the line's last byte, never mid-line. crs FILE prints "mid,end": lines with a
# CR before their end, lines ending in one.
crs() { "$PY" -B -c 'import sys
lines = open(sys.argv[1], "rb").read().split(b"\n")
print("%d,%d" % (sum(1 for l in lines if b"\r" in l[:-1]), sum(1 for l in lines if l.endswith(b"\r"))))' "$1"; }
crlf_line() { "$PY" -B - "$DW" "$1" <<'CRLF_END'
import sys
path, ident = sys.argv[1], sys.argv[2]
lines = open(path, "rb").read().split(b"\n")
hits = [i for i, l in enumerate(lines) if l.startswith(("- [ ] **%s** " % ident).encode())]
assert len(hits) == 1, hits
lines[hits[0]] += b"\r"
open(path, "wb").write(b"\n".join(lines))
CRLF_END
}
dfixture "$W/fix"; crlf_line DW-20260905-2
[ "$(crs "$DW")" = "0,1" ] || no "FX2 premise: the planted page carries one CRLF line (got $(crs "$DW"))"
vws decided status --vault "$VAULT" --id DW-20260905-2 --note "a status on a CRLF line" --by run-suite
eq "FX2a status on a page with one CRLF line keeps the CR as that line's last byte, never mid-line" "$RC$(crs "$DW")$(awk 'NR==14' "$DW" | grep -c 'a status on a CRLF line.$')" "00,11"
dfixture "$W/fix"; crlf_line DW-20260905-2
vws decided state --vault "$VAULT" --id DW-20260905-2 --state "to build" --note "a state on a CRLF line" --by run-suite
eq "FX2b state on a page with one CRLF line keeps the CR as that line's last byte, and field 4 holds no CR" "$RC$(crs "$DW")$(awk 'NR==14' "$DW" | grep -c ' · to build · other homes')" "00,11"
dfixture "$W/fix"; crlf_line DW-20260905-2
vws decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence "a close of a CRLF line" --by run-suite
eq "FX2c close of a CRLF line: the closed copy keeps the CR as its last byte, none mid-line; the open copy goes whole" "$RC$(crs "$DONE")|$(crs "$DW")$(bold_count "$DW" DW-20260905-2)" "00,1|0,00"
dfixture "$W/fix"; printf -- '- [x] %s · built 7 September 2026: e\r\n' "$BODY" >> "$DONE"
vws decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by run-suite
eq "FX2d control: count 1 where the closed line ends in CRLF is confirmed as the same line, not refused for its CR" "$RC$(bold_count "$DW" DW-20260905-2)" "00"

# FX3: a value may not start or end with the field separator, and the composed line's field count is
# asserted before any write.
dfixture "$W/fix"
dref "FX3a an add's --by ending with the separator refuses: 'recorded by x · at …' would gain a field" "--by starts or ends with the field separator" -- add --vault "$VAULT" --date 2026-09-05 --work w --locator l --state "to build" --by "run-suite ·"
dref "FX3b a status --note starting with the separator refuses: ': · x' would gain a field" "--note starts or ends with the field separator" -- status --vault "$VAULT" --id DW-20260905-2 --note "· x" --by b
dref "FX3c a state --note ending with the separator refuses" "--note starts or ends with the field separator" -- state --vault "$VAULT" --id DW-20260905-2 --state "to build" --note "x ·" --by b
dref "FX3d a close --evidence starting with the separator refuses" "--evidence starts or ends with the field separator" -- close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence "· x" --by b
"$PY" -B - "$S" >"$OUT" 2>&1 <<'FIELDS_END'
import importlib.util, io, contextlib, sys
spec = importlib.util.spec_from_file_location("vw_fields", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
out = io.StringIO()
code = 0
with contextlib.redirect_stdout(out):
    try:
        module.check_fields("decided-add", "- [ ] **DW-20260905-9** · w · x · decided d (l) · to build · recorded by b", 5, "new line")
    except SystemExit as exc:
        code = exc.code
print("RC=%s" % code)
print(out.getvalue().strip())
FIELDS_END
eq "FX3e the field-count guard refuses a composed line with a field more than its template gives it" "$(field RC)$(grep -c 'would have 6 fields, not the 5 its template gives it' "$OUT")" "21"

# FX4: an entry pushed later behind bytes that end mid-line is glued to them: exit 2, "landed but
# malformed", and never a plain ok that a caller would leave as it is.
fixture "$W/fix"
drive log-noeol "$LOG" log-append --vault "$VAULT" --action lint --title "logged behind a fragment" --changed c --conflicts none --date 2026-09-05
eq "FX4 an entry glued behind another writer's unfinished line: exit 2, 'landed but malformed; append a correction', the entry there once, their bytes kept" "$(field RC)$(field ACTED)$(field KEPT)$(grep -c 'the entry landed but malformed' "$OUT")$(grep -c 'append a correction entry, never a re-run' "$OUT")$(count "$LOG" '| logged behind a fragment')$(grep -c '^ok log-append' "$OUT" || true)" "21yes1110"
fixture "$W/fix"
drive log-between "$LOG" log-append --vault "$VAULT" --action lint --title "logged behind a whole line" --changed c --conflicts none --date 2026-09-05
eq "FX4c control: behind a newline-ended append the same shift is still ok, with its readback line" "$(field RC)$(field READBACK)" "01"

# FX6: the half-close message says what a re-run does when the open line itself changed, and it does that.
dfixture "$W/fix"
DRIVE_PLANT_PATH="$DW"; DRIVE_PLANT_TEXT="written between the two renames${NL}"; export DRIVE_PLANT_PATH DRIVE_PLANT_TEXT
drive second "$DW" decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by run-suite
eq "FX6a the half-close error says the re-run refuses as a repair if the open line changed meanwhile" "$(field RC)$(grep -c 'if the open line itself has changed since (a status added, say), the re-run refuses as a repair' "$OUT")" "21"
dfixture "$W/fix"
DRIVE_PLANT_PATH="$DW"; DRIVE_PLANT_OLD="· other homes: the fixture register"; DRIVE_PLANT_NEW="· other homes: the fixture register · status 6 September 2026 (fixture): added meanwhile"; export DRIVE_PLANT_PATH DRIVE_PLANT_OLD DRIVE_PLANT_NEW
drive second-replace "$DW" decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by run-suite
FX6RC=$(field RC); FX6P=$(field PLANTED)
dref "FX6b and so it is: after a status lands on the open line between the renames, the re-run refuses as a repair" "with a body that differs from the open copy" -- close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by run-suite
eq "FX6c control: that run was a half-close, the status landed on the open line between its renames" "$FX6RC$FX6P$(bold_count "$DONE" DW-20260905-2)$(count "$DW" 'added meanwhile')" "2111"

# FX7: the other line-break characters are refused in every argument, the existing verbs' too.
i=0
for spec in 'a\342\200\250b|U+2028' 'a\342\200\251b|U+2029' 'a\302\205b|U+0085' 'a\013b|VT' 'a\014b|FF'; do
	i=$((i + 1))
	value=$(printf "${spec%%|*}"); label=${spec##*|}
	dfixture "$W/fix"
	dref "FX7.$i a decided add whose --work carries $label refuses" "--work carries $label" -- add --vault "$VAULT" --date 2026-09-05 --work "$value" --locator l --state "to build" --by b
done
fixture "$W/fix"; cp "$LOG" "$W/log.fx7"
vws log-append --vault "$VAULT" --action lint --title "$(printf 'a\342\200\250b')" --changed c --conflicts none --date 2026-09-05
eq "FX7.6 an existing verb refuses it too: log-append's --title carrying U+2028, the log untouched" "$RC$(grep -c 'carries U+2028' "$SOUT")$(cmp -s "$W/log.fx7" "$LOG" && echo same)" "21same"
fixture "$W/fix"
vws log-append --vault "$VAULT" --action lint --title "a title with a plain · and no break" --changed c --conflicts none --date 2026-09-05
eq "FX7c control: a plain argument still goes through" "$RC" "0"

echo "== inside a helper: the write grants bound every writing verb (2026-11-12) =="

# A helper carries its write grants in LLM_WIKI_LANE_WRITES (lane.py sets it for every lane it spawns; empty
# when read-only); the lead does not. vh GRANTS ARGS... runs the writer inside such a helper.
vh() { GRANTS="$1"; shift; env LLM_WIKI_LANE_WRITES="$GRANTS" "$PY" -B "$S" "$@" >"$SOUT" 2>"$SERR"; RC=$?; }
# The remedy every refusal for want of a grant ends with: the helper reports the gap, never edits its environment.
REPORTGAP='report the missing grant (`needs: <path> because <reason>`)'
pages_sha() { echo "$(fsha "$REG")$(fsha "$DW")$(fsha "$DONE")$(fsha "$IDEAS")$(fsha "$LOG")"; }
# gw_refused NAME TARGET GRANTS -- ARGS...: inside a helper holding GRANTS, the call refuses, exit 2, one
# stdout line naming TARGET and the grant list, every fixture page byte for byte as it was, no temp file.
gw_refused() {
	name="$1"; target="$2"; grants="$3"; shift 4
	dfixture "$W/fix"; before=$(pages_sha)     # each refusal on a fresh fixture
	vh "$grants" "$@"
	if [ "$RC" = 2 ] && [ "$(nlines "$SOUT")" = 1 ] \
	   && grep -qF -- "$target is outside this helper's write grants ($grants); nothing written; $REPORTGAP" "$SOUT" \
	   && [ "$(pages_sha)" = "$before" ] && [ "$(temps_in "$VAULT")" = 0 ]; then ok "$name"
	else no "$name (rc $RC, stdout '$(head -c 300 "$SOUT")', pages $( [ "$(pages_sha)" = "$before" ] && echo same || echo CHANGED))"; fi
}
WD="$VAULT/wiki/developments"
D1="--date 2026-09-05"
dfixture "$W/fix"
gw_refused "GW1 register add inside a helper granted wiki/log.md only refuses, naming the register" "$REG" "$LOG" -- register add --vault "$VAULT" --why-not-fixed-now "$WN" $D1 --surface "gw surface" --symptom s --cause c --severity minor --status open
gw_refused "GW2 register close inside that helper refuses" "$REG" "$LOG" -- register close --vault "$VAULT" --match "alpha surface" $D1 --status "closed by a helper"
gw_refused "GW3 register annotate inside that helper refuses" "$REG" "$LOG" -- register annotate --vault "$VAULT" --match "alpha surface" --kind Status --note "a helper's note"
gw_refused "GW4 ideas annotate inside that helper refuses, naming the IDEAS file" "$IDEAS" "$LOG" -- ideas annotate --file "$IDEAS" --item 119 --note "a helper's note" $D1
gw_refused "GW5 decided add inside that helper refuses, naming the open page" "$DW" "$LOG" -- decided add --vault "$VAULT" $D1 --work w --locator l --state "to build" --by helper
gw_refused "GW6 decided status inside that helper refuses" "$DW" "$LOG" -- decided status --vault "$VAULT" --id DW-20260905-2 --note n --by helper
gw_refused "GW7 decided state inside that helper refuses" "$DW" "$LOG" -- decided state --vault "$VAULT" --id DW-20260905-2 --state "to build" --note n --by helper
gw_refused "GW8 decided close inside that helper refuses" "$DW" "$LOG" -- decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by helper
gw_refused "GW8b decided close inside a helper granted the open page only refuses, naming the closed page it would also write" "$DONE" "$DW" -- decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by helper
gw_refused "GW8c a dry run refuses inside that helper as the real run would: it previews the run it stands for" "$DW" "$LOG" -- decided add --vault "$VAULT" $D1 --work w --locator l --state "to build" --by helper --dry-run

# The helper's own writes go through (controls, the same on the writer before this change).
dfixture "$W/fix"
vh "$LOG" log-append --vault "$VAULT" --action lint --title "a helper's own entry" --changed c --conflicts none $D1
eq "GW9 control: the same helper's log-append is allowed, the entry written once" "$RC$(count "$LOG" "| a helper's own entry")" "01"
dfixture "$W/fix"
vh "$LOG:$VAULT/wiki/index.md:$VAULT/wiki/sources" log-append --vault "$VAULT" --action ingest --title "an ingest lane's entry" --changed c --conflicts none $D1
eq "GW9b control: an ingest-exception helper (log, index and its pages granted, CLAUDE.md 2.2) appends its log entry" "$RC$(count "$LOG" "| an ingest lane's entry")" "01"
dfixture "$W/fix"
vh "$WD" register add --vault "$VAULT" --why-not-fixed-now "$WN" $D1 --surface "gw granted" --symptom s --cause c --severity minor --status open
eq "GW10 control: a helper granted wiki/developments may register add" "$RC$(count "$REG" 'gw granted')" "01"
dfixture "$W/fix"
vh "$WD" decided close --vault "$VAULT" --id DW-20260905-2 --kind built --evidence e --by helper
eq "GW10b control: a helper granted wiki/developments may close a decided-work line (both pages in it)" "$RC$(bold_count "$DONE" DW-20260905-2)$(bold_count "$DW" DW-20260905-2)" "010"
dfixture "$W/fix"
vh "$REG" register annotate --vault "$VAULT" --match "alpha surface" --kind Status --note "a granted note"
eq "GW10c control: a grant on the register file itself covers it" "$RC$(count "$REG" 'a granted note')" "01"

# The lead (the variable absent) is unchanged: every verb writes where no grant names it.
dfixture "$W/fix"
env -u LLM_WIKI_LANE_WRITES "$PY" -B "$S" register add --vault "$VAULT" --why-not-fixed-now "$WN" $D1 --surface "lead surface" --symptom s --cause c --severity minor --status open >"$OUT" 2>&1; L1=$?
env -u LLM_WIKI_LANE_WRITES "$PY" -B "$S" register annotate --vault "$VAULT" --match "alpha surface" --kind Status --note "lead note" >"$OUT" 2>&1; L2=$?
env -u LLM_WIKI_LANE_WRITES "$PY" -B "$S" register close --vault "$VAULT" --match "beta surface" $D1 --status "closed by the lead" >"$OUT" 2>&1; L3=$?
env -u LLM_WIKI_LANE_WRITES "$PY" -B "$S" ideas annotate --file "$IDEAS" --item 119 --note "lead note" $D1 >"$OUT" 2>&1; L4=$?
env -u LLM_WIKI_LANE_WRITES "$PY" -B "$S" decided add --vault "$VAULT" $D1 --work "lead work" --locator l --state "to build" --by lead >"$OUT" 2>&1; L5=$?
env -u LLM_WIKI_LANE_WRITES "$PY" -B "$S" decided status --vault "$VAULT" --id DW-20260905-2 --note "lead status" --by lead >"$OUT" 2>&1; L6=$?
env -u LLM_WIKI_LANE_WRITES "$PY" -B "$S" decided state --vault "$VAULT" --id DW-20260904-1 --state "to build" --note "lead state" --by lead >"$OUT" 2>&1; L7=$?
env -u LLM_WIKI_LANE_WRITES "$PY" -B "$S" decided close --vault "$VAULT" --id DW-20260905-1 --kind built --evidence "lead close" --by lead >"$OUT" 2>&1; L8=$?
env -u LLM_WIKI_LANE_WRITES "$PY" -B "$S" log-append --vault "$VAULT" --action lint --title "lead entry" --changed c --conflicts none $D1 >"$OUT" 2>&1; L9=$?
eq "GW11 control: the lead (no LLM_WIKI_LANE_WRITES) writes with every verb, as before" "$L1$L2$L3$L4$L5$L6$L7$L8$L9$(count "$REG" 'lead surface')$(count "$IDEAS" 'lead note')$(count "$DW" 'lead status')$(count "$LOG" '| lead entry')" "0000000001111"

# An empty or unreadable variable refuses (fail-closed): a helper whose grants cannot be read writes nothing.
# Each verb runs on a fresh fixture; its refusal names the file the write would change and prints the value
# whole, as repr() gives it.
EMPTYMSG="this run is inside a helper whose LLM_WIKI_LANE_WRITES is empty (''), so it holds no write grant; nothing written"
refused=0; kept=0
for spec in "log-append --vault $VAULT --action lint --title t --changed c --conflicts none $D1|$LOG" \
            "register add --vault $VAULT --why-not-fixed-now x $D1 --surface s --symptom s --cause c --severity minor --status open|$REG" \
            "register close --vault $VAULT --match alpha $D1 --status s|$REG" \
            "register annotate --vault $VAULT --match alpha --kind Status --note n|$REG" \
            "ideas annotate --file $IDEAS --item 119 --note n $D1|$IDEAS" \
            "decided add --vault $VAULT $D1 --work w --locator l --state to-build --by b|$DW" \
            "decided status --vault $VAULT --id DW-20260905-2 --note n --by b|$DW" \
            "decided state --vault $VAULT --id DW-20260905-2 --state to-build --note n --by b|$DW" \
            "decided close --vault $VAULT --id DW-20260905-2 --kind built --evidence e --by b|$DW, $DONE"; do
	call=${spec%|*}; target=${spec##*|}
	dfixture "$W/fix"; before=$(pages_sha)
	# shellcheck disable=SC2086
	env LLM_WIKI_LANE_WRITES= "$PY" -B "$S" $call >"$OUT" 2>&1
	[ "$?" = 2 ] && grep -qF -- "$target: $EMPTYMSG" "$OUT" && refused=$((refused + 1))
	[ "$(pages_sha)" = "$before" ] && kept=$((kept + 1))
done
eq "GW12 an empty LLM_WIKI_LANE_WRITES refuses every one of the nine writing verbs, each refusal naming its target, each fresh fixture untouched" "$refused$kept" "99"
LONGV=$(printf 'relative/%0150d' 0)
for spec in 'wiki/log.md|a relative path' ':::|separators only' " $LOG|a padded path" "$LOG:relative/x|a relative path beside an absolute one" "$LONGV|a 159-character relative value, printed whole"; do
	value=${spec%%|*}; label=${spec##*|}
	dfixture "$W/fix"; before=$(pages_sha)
	RV=$("$PY" -B -c 'import sys; print(repr(sys.argv[1]))' "$value")
	env LLM_WIKI_LANE_WRITES="$value" "$PY" -B "$S" log-append --vault "$VAULT" --action lint --title t --changed c --conflicts none $D1 >"$OUT" 2>&1; GRC=$?
	eq "GW13 a garbled LLM_WIKI_LANE_WRITES ($label) refuses, naming the log and printing the value whole as repr gives it, writing nothing" "$GRC$(grep -c -F -- "$LOG: this run is inside a helper whose LLM_WIKI_LANE_WRITES" "$OUT")$(grep -c -F -- "($RV)" "$OUT")$( [ "$(pages_sha)" = "$before" ] && echo same)" "211same"
done

# A target that is itself a symbolic link: inside a helper it is refused whatever it points to, and the link is
# left as it is, since a write would rename over the link's own path in its own folder. A folder reached
# through a link is followed, and a grant given through a linked spelling covers what it resolves to.
# P4a: --vault given as a link to the vault, the grant on the real folder.
dfixture "$W/fix"; rm -f "$W/vaultlink"; ln -s "$VAULT" "$W/vaultlink"
vh "$WD" register add --vault "$W/vaultlink" --why-not-fixed-now "$WN" $D1 --surface "through a linked vault folder" --symptom s --cause c --severity minor --status open
eq "GW14-P4a control: a granted file reached through a linked vault folder is allowed, the write landing in the granted file" "$RC$(count "$REG" 'through a linked vault folder')$(test -L "$W/vaultlink" && echo link)$(test -L "$REG" || echo file)" "01linkfile"
# P4b: --vault the real vault, the grant spelled through the linked vault folder.
dfixture "$W/fix"; rm -f "$W/vaultlink"; ln -s "$VAULT" "$W/vaultlink"
vh "$W/vaultlink/wiki/developments" register add --vault "$VAULT" --why-not-fixed-now "$WN" $D1 --surface "under a grant spelled through a link" --symptom s --cause c --severity minor --status open
eq "GW14-P4b control: a grant spelled through a linked vault folder covers the folder it resolves to" "$RC$(count "$REG" 'under a grant spelled through a link')" "01"
# P4c: an ungranted vault whose wiki/developments is a folder link to the granted folder, the grant given on the
# real folder and then on the linked spelling. A folder reached through a link is followed: the write lands in the
# real folder and the folder link stays.
for spelling in real linked; do
	dfixture "$W/fix"; rm -rf "$W/uvault"; mkdir -p "$W/uvault/wiki"; ln -s "$WD" "$W/uvault/wiki/developments"
	if [ "$spelling" = real ]; then GRANT="$WD"; else GRANT="$W/uvault/wiki/developments"; fi
	vh "$GRANT" register add --vault "$W/uvault" --why-not-fixed-now "$WN" $D1 --surface "through a linked folder ($spelling grant)" --symptom s --cause c --severity minor --status open
	eq "GW14-P4c control ($spelling grant): an ungranted vault whose wiki/developments links to the granted folder writes into the real folder, the folder link intact" "$RC$(count "$REG" "through a linked folder ($spelling grant)")$(test -L "$W/uvault/wiki/developments" && echo link)$(test -L "$REG" || echo file)" "01linkfile"
done
# P4d: a file link in an ungranted folder to the granted register. Refused: a write would rename over the link's
# own path in the ungranted folder.
dfixture "$W/fix"; rm -rf "$W/linkvault"; mkdir -p "$W/linkvault/wiki/developments"
ln -s "$REG" "$W/linkvault/wiki/developments/known-issues.md"; before=$(pages_sha)
vh "$WD" register add --vault "$W/linkvault" --why-not-fixed-now "$WN" $D1 --surface "through a link" --symptom s --cause c --severity minor --status open
eq "GW14-P4d a register add whose target is a link in an ungranted folder pointing into the granted one is refused, the link intact, nothing written" "$RC$(grep -c 'is a symbolic link (to ' "$SOUT")|$(test -L "$W/linkvault/wiki/developments/known-issues.md" && echo link)|$( [ "$(readlink "$W/linkvault/wiki/developments/known-issues.md")" = "$REG" ] && echo same-target)|$( [ "$(pages_sha)" = "$before" ] && echo pages-same)|$(find "$W/linkvault" -name '.vault-writes-*' | wc -l | tr -d ' ')" "21|link|same-target|pages-same|0"
dfixture "$W/fix"; rm -rf "$W/linkvault2"; mkdir -p "$W/linkvault2/wiki/developments"
ln -s "$DW" "$W/linkvault2/wiki/developments/decided-work.md"; before=$(pages_sha)
vh "$WD" decided status --vault "$W/linkvault2" --id DW-20260905-2 --note "through a link" --by helper
eq "GW14-P4d2 a decided status whose open page is such a link is refused the same way, the link intact" "$RC$(grep -c 'is a symbolic link (to ' "$SOUT")|$(test -L "$W/linkvault2/wiki/developments/decided-work.md" && echo link)|$( [ "$(pages_sha)" = "$before" ] && echo pages-same)" "21|link|pages-same"
# P4e: ungranted/wiki/log.md a file link to the granted log, the grant on the granted log, log-append --vault
# ungranted. Refused, like P4d: inside a helper any linked target is refused, so a link planted in an ungranted
# folder never stands in for a granted file. (log-append appends through the link rather than renaming over it,
# so here the refusal is that uniform rule, not a replace.)
dfixture "$W/fix"; rm -rf "$W/uvault2"; mkdir -p "$W/uvault2/wiki"; ln -s "$LOG" "$W/uvault2/wiki/log.md"; before=$(pages_sha)
vh "$LOG" log-append --vault "$W/uvault2" --action lint --title "through a log link" --changed c --conflicts none $D1
eq "GW14-P4e a log-append whose log is a file link in an ungranted folder to the granted log is refused, the link intact, the log unchanged" "$RC$(grep -c 'is a symbolic link (to ' "$SOUT")|$(test -L "$W/uvault2/wiki/log.md" && echo link)|$( [ "$(readlink "$W/uvault2/wiki/log.md")" = "$LOG" ] && echo same-target)|$( [ "$(pages_sha)" = "$before" ] && echo pages-same)" "21|link|same-target|pages-same"
dfixture "$W/fix"; rm -rf "$W/linkvault"; mkdir -p "$W/linkvault/wiki/developments"
ln -s "$REG" "$W/linkvault/wiki/developments/known-issues.md"
env -u LLM_WIKI_LANE_WRITES "$PY" -B "$S" register add --vault "$W/linkvault" --why-not-fixed-now "$WN" $D1 --surface "the lead through a link" --symptom s --cause c --severity minor --status open >"$OUT" 2>&1; LRC=$?
eq "GW14-lead control: the lead (no variable) writes through a linked target as before" "$LRC$(grep -c 'the lead through a link' "$W/linkvault/wiki/developments/known-issues.md")" "01"

# GW15: a helper whose grant variable is absent. lane.py sets LLM_WIKI_LANE, LLM_WIKI_LANE_ID and
# LLM_WIKI_LANE_GRANTS beside LLM_WIKI_LANE_WRITES; a helper that removes the variable alone has not left the
# helper, so every verb refuses: one line naming the target and ending with the report it owes its head.
ABSENTMSG="this run is inside a helper whose LLM_WIKI_LANE_WRITES is absent, so its grants cannot be read; nothing written; $REPORTGAP"
dfixture "$W/fix"; before=$(pages_sha)
env -u LLM_WIKI_LANE_WRITES LLM_WIKI_LANE=1 LLM_WIKI_LANE_RUN=run-suite LLM_WIKI_LANE_ID=gw LLM_WIKI_LANE_GRANTS="$W" "$PY" -B "$S" register add --vault "$VAULT" --why-not-fixed-now "$WN" $D1 --surface "a helper without its variable" --symptom s --cause c --severity minor --status open >"$SOUT" 2>"$SERR"; RC=$?
eq "GW15a register add in a helper environment as lane.py sets it, the grant variable removed, refuses: one line naming the register, ending with the report, nothing written" "$RC$(nlines "$SOUT")$(grep -c -F -- "$REG: $ABSENTMSG" "$SOUT")$( [ "$(pages_sha)" = "$before" ] && echo same)$(temps_in "$VAULT")" "211same0"
refused=0; kept=0
for marker in "LLM_WIKI_LANE=1" "LLM_WIKI_LANE_ID=gw" "LLM_WIKI_LANE_GRANTS=$W"; do
	dfixture "$W/fix"; before=$(pages_sha)
	env -u LLM_WIKI_LANE_WRITES "$marker" "$PY" -B "$S" log-append --vault "$VAULT" --action lint --title "one marker alone" --changed c --conflicts none $D1 >"$OUT" 2>&1
	[ "$?" = 2 ] && grep -qF -- "$LOG: $ABSENTMSG" "$OUT" && refused=$((refused + 1))
	[ "$(pages_sha)" = "$before" ] && kept=$((kept + 1))
done
eq "GW15b any one of the three names alone, the grant variable absent, refuses log-append, the log untouched (3 names)" "$refused$kept" "33"
dfixture "$W/fix"; before=$(pages_sha)
env -u LLM_WIKI_LANE_WRITES LLM_WIKI_LANE=1 LLM_WIKI_LANE_ID=gw "$PY" -B "$S" decided add --vault "$VAULT" $D1 --work w --locator l --state "to build" --by helper >"$SOUT" 2>&1; R1=$?; G1=$(grep -c -F -- "$DW: $ABSENTMSG" "$SOUT")
env -u LLM_WIKI_LANE_WRITES LLM_WIKI_LANE=1 LLM_WIKI_LANE_ID=gw "$PY" -B "$S" decided add --vault "$VAULT" $D1 --work w --locator l --state "to build" --by helper --dry-run >"$SOUT" 2>&1; R2=$?; G2=$(grep -c -F -- "$DW: $ABSENTMSG" "$SOUT")
eq "GW15c decided add, and its dry run, refuse the same way in such a helper, the pages untouched" "$R1$G1$R2$G2$( [ "$(pages_sha)" = "$before" ] && echo same)" "2121same"
dfixture "$W/fix"; before=$(pages_sha)
env -u LLM_WIKI_LANE_WRITES -u LLM_WIKI_LANE_GRANTS LLM_WIKI_LANE=1 LLM_WIKI_LANE_RUN=run-suite LLM_WIKI_LANE_ID=gw LLM_WIKI_LANE_HARNESS=codex "$PY" -B "$S" log-append --vault "$VAULT" --action lint --title "a codex helper's entry" --changed c --conflicts none $D1 >"$OUT" 2>&1; CRC=$?
eq "GW15d a Codex helper's environment as codex-lane.py sets it (two of the names, no grant variable) is refused too, the log untouched" "$CRC$(grep -c -F -- "$LOG: $ABSENTMSG" "$OUT")$( [ "$(pages_sha)" = "$before" ] && echo same)" "21same"
dfixture "$W/fix"
env -u LLM_WIKI_LANE_WRITES -u LLM_WIKI_LANE -u LLM_WIKI_LANE_ID -u LLM_WIKI_LANE_GRANTS LLM_WIKI_LANE_RUN=run-suite LLM_WIKI_LANE_PROGRESS="$W/progress" LLM_WIKI_LANE_HOME="$W/home" "$PY" -B "$S" register add --vault "$VAULT" --why-not-fixed-now "$WN" $D1 --surface "a lead beside other lane names" --symptom s --cause c --severity minor --status open >"$OUT" 2>&1; LRC=$?
eq "GW15e control: a lead's environment (none of the three names, other LLM_WIKI_LANE_ names set) writes as before" "$LRC$(count "$REG" 'a lead beside other lane names')" "01"
# The refusal points at the report, not at the variable: no `NAME=value` a helper could copy onto its command line.
dfixture "$W/fix"
vh "$LOG" register add --vault "$VAULT" --why-not-fixed-now "$WN" $D1 --surface s --symptom s --cause c --severity minor --status open
eq "GW15f the outside-the-grants refusal ends with the report and carries no LLM_WIKI_LANE_WRITES= assignment" "$RC$(grep -c -F -- "; $REPORTGAP" "$SOUT")$(grep -c -F -- 'LLM_WIKI_LANE_WRITES=' "$SOUT")" "210"
dfixture "$W/fix"
env LLM_WIKI_LANE_WRITES= "$PY" -B "$S" log-append --vault "$VAULT" --action lint --title t --changed c --conflicts none $D1 >"$OUT" 2>&1; ERC=$?
eq "GW15g the empty-variable refusal ends with the report too" "$ERC$(grep -c -F -- "$EMPTYMSG; $REPORTGAP" "$OUT")" "21"

# GW16: a target with a second hard link. Inside a helper granted only a folder of its own, a hard link there to
# the vault's log (or register) would let an append (or a read) reach a file the grants do not name, so it is
# refused, the links left as they are; a plain file is written, and the lead is unchanged.
nlink() { "$PY" -B -c 'import os, sys; print(os.stat(sys.argv[1]).st_nlink)' "$1"; }
dfixture "$W/fix"; rm -rf "$W/hl"; mkdir -p "$W/hl/v/wiki"; ln "$LOG" "$W/hl/v/wiki/log.md"; before=$(pages_sha)
vh "$W/hl" log-append --vault "$W/hl/v" --action lint --title "through a hard link" --changed c --conflicts none $D1
eq "GW16a log-append whose log is a hard link to the vault's log, in a folder the helper was granted, is refused, the log unchanged, both names kept" "$RC$(nlines "$SOUT")$(grep -c 'has 2 hard links' "$SOUT")|$( [ "$(pages_sha)" = "$before" ] && echo pages-same)|$(nlink "$LOG")$(nlink "$W/hl/v/wiki/log.md")" "211|pages-same|22"
dfixture "$W/fix"; rm -rf "$W/hl"; mkdir -p "$W/hl/v/wiki/developments"; ln "$REG" "$W/hl/v/wiki/developments/known-issues.md"; before=$(pages_sha)
vh "$W/hl" register add --vault "$W/hl/v" --why-not-fixed-now "$WN" $D1 --surface "through a hard link" --symptom s --cause c --severity minor --status open
eq "GW16b register add whose register is such a hard link is refused the same way, nothing written, no temp file" "$RC$(grep -c 'has 2 hard links' "$SOUT")|$( [ "$(pages_sha)" = "$before" ] && echo pages-same)|$(nlink "$REG")|$(temps_in "$W/hl")" "21|pages-same|2|0"
dfixture "$W/fix"; rm -rf "$W/hl"; mkdir -p "$W/hl/v/wiki"; cp "$LOG" "$W/hl/v/wiki/log.md"; before=$(pages_sha)
vh "$W/hl" log-append --vault "$W/hl/v" --action lint --title "into a plain copy" --changed c --conflicts none $D1
eq "GW16c control: the same helper appends to a plain file there (one link), the vault's log unchanged" "$RC$(count "$W/hl/v/wiki/log.md" '| into a plain copy')$(nlink "$W/hl/v/wiki/log.md")$( [ "$(pages_sha)" = "$before" ] && echo pages-same)" "011pages-same"
dfixture "$W/fix"; rm -rf "$W/hl"; mkdir -p "$W/hl/v/wiki"; ln "$LOG" "$W/hl/v/wiki/log.md"
env -u LLM_WIKI_LANE_WRITES "$PY" -B "$S" log-append --vault "$W/hl/v" --action lint --title "the lead through a hard link" --changed c --conflicts none $D1 >"$OUT" 2>&1; LRC=$?
eq "GW16d control: the lead (no variable) appends through a hard link as before" "$LRC$(count "$LOG" '| the lead through a hard link')" "01"

TOTAL=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ]; then
	echo "PASS $PASS/$TOTAL"
	exit 0
fi
echo "FAIL $FAIL/$TOTAL"
exit 1
