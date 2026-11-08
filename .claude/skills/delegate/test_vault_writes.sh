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
next_hm() { "$PY" -B -c 'import datetime; print((datetime.datetime.now() + datetime.timedelta(minutes=1)).strftime("%H:%M"))'; }
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

echo "== register add: one stamp, one entry (K7c56f8cc) =="

fixture "$W/fix"
M0=$(now_hm)
M1=$(next_hm)
plant_heads 7 "2026-09-05 $M0" "2026-09-05 $M1"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "sigma surface" --symptom "s" --cause "c" --severity minor --status "open"
eq "S1 an add in a minute whose stamp another heading carries is written" "$RC" "0"
eq2 "S1b it takes the suffix b inside the brackets" "$(awk 'NR==7' "$REG")" "### [2026-09-05 $M0 b] sigma surface (minor)" "### [2026-09-05 $M1 b] sigma surface (minor)"
eq "S1c guard: a suffix is routine, not a warning: stderr stays silent and stdout is the one ok line" "$(nlines "$SERR")$(nlines "$SOUT")" "01"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "tau surface" --symptom "s" --cause "c" --severity minor --status "open"
eq "S2 two entries added in one minute carry two different stamps" "$(test -n "$(stamp_of 'sigma surface')" && test "$(stamp_of 'sigma surface')" != "$(stamp_of 'tau surface')" && echo distinct)" "distinct"
eq "S2b the four stamps of that date (two planted, two added) are four, and none repeats" "$(sed -n 's/^### \[\(2026-09-05 [^]]*\)\].*/\1/p' "$REG" | wc -l | tr -d ' ')$(sed -n 's/^### \[\(2026-09-05 [^]]*\)\].*/\1/p' "$REG" | sort | uniq -d | wc -l | tr -d ' ')" "40"

fixture "$W/fix"
M0=$(now_hm)
M1=$(next_hm)
plant_heads 30 "2026-09-05 $M0" "2026-09-05 $M1"
vws register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "upsilon surface" --symptom "s" --cause "c" --severity minor --status "open"
eq2 "S3 a stamp carried only under Closed counts too" "$(awk 'NR==7' "$REG")" "### [2026-09-05 $M0 b] upsilon surface (minor)" "### [2026-09-05 $M1 b] upsilon surface (minor)"
fixture "$W/fix"
M0=$(now_hm)
M1=$(next_hm)
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
M0=$(now_hm)
M1=$(next_hm)
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
M0=$(now_hm)
M1=$(next_hm)
plant_heads 7 "2026-09-05 $M0" "2026-09-05 $M0" "2026-09-05 $M1" "2026-09-05 $M1"
cp "$REG" "$W/reg.doubled"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "chi surface" --symptom "s" --cause "c" --severity minor --status "open"
eq "U4 an add into a minute whose stamp already heads two entries is refused (it names none of them), writing nothing" "$RC$(grep -c 'already heads 2 entries, so it names none of them' "$OUT")$(unchanged "$W/reg.doubled" "$REG")" "21same"
fixture "$W/fix"
M0=$(now_hm)
M1=$(next_hm)
plant_heads 7 "2026-09-05 ${M0}b" "2026-09-05 ${M1}b"
cp "$REG" "$W/reg.glued"
vw register add --vault "$VAULT" --why-not-fixed-now "$WN" --date 2026-09-05 --surface "psi surface" --symptom "s" --cause "c" --severity minor --status "open"
eq "U5 a heading carrying the same minute in a form the check cannot read refuses the add, writing nothing" "$RC$(grep -c 'this check cannot read' "$OUT")$(unchanged "$W/reg.glued" "$REG")" "21same"
fixture "$W/fix"
M0=$(now_hm)
M1=$(next_hm)
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
eq2 "N2 without --by the note omits it, and lands above the unheaded entry that follows" "$(awk 'NR==10' "$REG")" "- **Status 2026-09-05 $T0 $Z:** checked again" "- **Status 2026-09-05 $T1 $Z:** checked again"
eq "N2b the unheaded entry still follows after one blank line" "$(awk 'NR==11 || NR==12' "$REG" | tr '\n' '|')" "|- 2026-09-09 · surface: an unheaded one-line entry · symptom: it would be swept|"
vw register close --vault "$VAULT" --match "first surface" --date 2026-09-05 --status "closed after a note"
eq "N8 the noted entry still closes: a dated Status note is not its Status line" "$RC$(inclosed '- **Status**: open — fix shape: first *(2026-09-05: closed 2026-09-05 ')$(inclosed 'checked again')$(inopen 'checked again')" "0110"
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
eq "N9 the note is scanned for clock tokens, and still written" "$RC$(nlines "$SERR")$(inopen "seen at $PLANT")" "011"
xfixture "$W/fix"
vw register annotate --vault "$VAULT" --match "second surface" --kind Status --note "the **Status** field above and the **Symptom** text were stale"
eq "N13 a note quoting the field names **Status** and **Symptom** is written" "$RC$(inopen 'the **Status** field above and the **Symptom** text were stale')" "01"
T0=$(now_hm)
vw register close --vault "$VAULT" --match "second surface" --date 2026-09-05 --status "closed after a quoting note"
T1=$(now_hm)
eq "N13b and the entry stays closable: the close dates its one Status field" "$RC$(inclosed 'second surface')$(inclosed 'the **Status** field above')" "011"
eq2 "N13c the dated line is the Status field, not the note, and the quoting note moved with it" "$(grep -F -- 'fix shape: second' "$REG")|$(inclosed 'the **Status** field above and the **Symptom** text were stale')" "- **Status**: open — fix shape: second *(2026-09-05: closed 2026-09-05 $T0 — closed after a quoting note)*|1" "- **Status**: open — fix shape: second *(2026-09-05: closed 2026-09-05 $T1 — closed after a quoting note)*|1"
yfixture "$W/fix"
cp "$REG" "$W/reg.ny"
vw register annotate --vault "$VAULT" --match "seventh surface" --kind Status --note "n"
eq "N15 an entry with two Status fields is refused as close refuses it, writing nothing" "$RC$(grep -c "holds another entry at line 8 (a second 'Status' field" "$OUT")$(unchanged "$W/reg.ny" "$REG")" "21same"
cp "$W/reg.ny" "$REG"   # each refusal leg starts from the same bytes, so one cannot leak into the next
vw register annotate --vault "$VAULT" --match "eighth surface" --kind Status --note "n"
eq "N16 a Status field below an unheaded entry refuses the note as it refuses the close, writing nothing" "$RC$(grep -c "field at line 15, below line 14" "$OUT")$(unchanged "$W/reg.ny" "$REG")" "21same"

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

TOTAL=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ]; then
	echo "PASS $PASS/$TOTAL"
	exit 0
fi
echo "FAIL $FAIL/$TOTAL"
exit 1
