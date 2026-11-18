#!/bin/sh
# test_handback_count.sh — regression suite for handback-count.py (delegate skill, the Handback counter).
#
# Every fixture is written under one `mktemp -d` and removed at exit. The script is stdout only, so
# the last leg checks that every fixture, and the script's own folder, is byte-identical after all the
# runs, with a control that changes one byte of a fixture under the same permissions.
#
# Controls: every leg that asserts a zero or a clean result sits beside a leg that plants the fault and
# proves the same probe fires. Expected counts are hand-derived from the fixtures below, never read
# from the script.
#
# The reproduction of a measured week runs only where its data is given, since the mapping names one
# vault's reports and the counts are that vault's:
#   HANDBACK_MAPPING=<mapping.json> HANDBACK_EXPECT='<day>=<n>,<day>=<n>,...' [HANDBACK_REPORTS=<dir>]
#   (the reports folder defaults to output/reports in the vault three folders above this file).
#
# Run:  sh test_handback_count.sh      (last line: PASS n/n or FAIL k/n; exit 0 only when clean)
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
S="$HERE/handback-count.py"
VAULT=${VAULT_DIR:-$(cd "$HERE/../../.." && pwd)}      # .claude/skills/delegate -> vault root
PY="${PYTHON:-python3}"
PASS=0
FAIL=0
ok() { PASS=$((PASS + 1)); echo "  ok   — $1"; }
no() { FAIL=$((FAIL + 1)); echo "FAIL   — $1"; }
eq() { if [ "$2" = "$3" ]; then ok "$1"; else no "$1 (got '$2', want '$3')"; fi; }

W=$(mktemp -d "${TMPDIR:-/tmp}/suite.XXXXXX")
OUT="$W/out.txt"
cleanup() { chmod -R u+rw "$W" >/dev/null 2>&1; rm -rf "$W"; }
trap cleanup EXIT
[ -f "$S" ] || { echo "PROBE FAILED: no handback-count.py at $S"; echo "FAIL 1/1"; exit 2; }

run() { "$@" >"$OUT" 2>&1; RC=$?; }
has() { if grep -qF -- "$2" "$OUT"; then ok "$1"; else no "$1 (stdout lacks '$2')"; fi; }
hasnot() { if grep -qF -- "$2" "$OUT"; then no "$1 (stdout still holds '$2')"; else ok "$1"; fi; }
summary() { grep '^HANDBACK SUMMARY' "$OUT" | sed 's/^HANDBACK SUMMARY //'; }
field() { summary | tr ' ' '\n' | grep "^$1=" | cut -d= -f2; }

# A manifest of names, modes, sizes and sha256 under one folder, by a parser of its own (never the
# script under test); an unreadable file is listed by mode and size.
manifest() {
  "$PY" -I -B -c '
import hashlib, os, sys
root = sys.argv[1]
for d, dirs, files in sorted(os.walk(root)):
    dirs.sort()
    for f in sorted(files):
        p = os.path.join(d, f)
        st = os.lstat(p)
        try:
            with open(p, "rb") as fh:
                h = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            h = "unreadable"
        print(os.path.relpath(p, root), oct(st.st_mode), st.st_size, h)
' "$1"
}

FX="$W/fx"
mkdir -p "$FX/reports"

cat >"$FX/today.md" <<'FXEND'
# Morning list

## Decide
- **1. Pick the venue for the talk.** text
  - (a) option
- **2. Keep the old cover image.** text

## Approve
**3. Install the parser repair.** body
- For it: detail

## Your to-dos
- **4. Sign the travel form.**

## Undo if you disagree
- **5. Moved the meeting notes.**

## Done
- Nothing else.
FXEND

cat >"$FX/earlier.md" <<'FXEND'
# Yesterday's list
## Approve
- **9. Install the parser repair.** body
## Decide
- **8. Choose the poster size.** body
FXEND

cat >"$FX/other.md" <<'FXEND'
# Another day's list
## Decide
- **8. Choose the poster size.** body
FXEND

cat >"$FX/part2.md" <<'FXEND'
# Second part
## Decide
- **1. Pick the venue for the talk.** again
FXEND

cat >"$FX/selfrepeat.md" <<'FXEND'
# One part
## Decide
- **1. Pick the venue for the talk.** text
- **2. Pick the venue for the talk.** again, in the same part
FXEND

cat >"$FX/weekly.md" <<'FXEND'
# List
## Decide
- **1. Pick the venue.** text
## Approve
- **2. Install the repair.** body
### For the weekly review
- **3. Rename the tools folder.** body
- **4. Retire the old check.** body
### Smaller ones
- **5. Merge the two notes.** body
- **6. The weekly review checks the backup.** body
## For Sunday's weekly review
- **7. Decide: split the skill.** body
## Done
- **Coming to the weekly review, not asked today:** the larger step
FXEND

cat >"$FX/waiting.md" <<'FXEND'
# List
## Decide
- **1. Pick the venue.** text
- 4 items still wait from Monday: [the list](waiting-list.md)
- **Still waiting from Monday, not asked again**: 3 items
- For it: this still waits on the printer
## Approve
- **2. Install the repair.** body
FXEND

cat >"$FX/xref.md" <<'FXEND'
# List
## Approve
- **6. The build settings, if you take (a) in Decide 2.** body
## Your to-dos
- **7. Only on Saturday, if you take (a) in Decide 2.** body
- **K1. Decide: the poster size.** body
FXEND

# C21: the day before weekly.md, two items held for the weekly review; today 3 is still held and
# "Pick the venue." is put to the owner as new.
cat >"$FX/weekly-yesterday.md" <<'FXEND'
# Yesterday
## For the weekly review
- **3. Rename the tools folder.** body
- **8. Pick the venue.** body
FXEND

# C23: a numbered item that says "still waits" beside a link stays an item; the unnumbered linked
# line is still the waiting line.
cat >"$FX/waiting-item.md" <<'FXEND'
# List
## Decide
- **1. Choose the printer.** It still waits on the [quote](q.md)
- **2. Pick the venue.** text
- 4 items still wait from Monday: [the list](waiting-list.md)
FXEND

cat >"$FX/nogroups.md" <<'FXEND'
# Notes

Some prose about the week.
- a list line
FXEND

cat >"$FX/emptygroups.md" <<'FXEND'
# List
## Decide
- None.
## Approve
- Nothing.
## Your to-dos
- None from this run.
FXEND

# E2's own planted Handback for its parser (12 November 2026): 8 items, details, None, Undo, Done
# and settled lines left out — the copied parser must still read it the same way.
cat >"$FX/e2sample.md" <<'FXEND'
# R
## Decide
- **1. One.** text
  - (a) opt
- **2. Two.** text
### Sub heading
- **3. Three.**
## Approve
**4. Para item.** body
- For it: detail
- Options: detail
**5. Second para.** body
## Your to-dos
- None from this close.
## Undo if you disagree
- **6. Not an item.**
## Topic
- **K1. Decide: inline.** x
- **E9. Your to-do, inline.** y
- **F2. Settled.** z
**Approve**
- **7. Bold-label group.**
**Done**
- **8. Done item.**
FXEND

cat >"$FX/reports/r1.md" <<'FXEND'
# Report one
## Decide
- **1. First choice.** x
## Approve
- **2. First approval.** x
## Run two's part
## Decide
- **3. Second choice.** x
- **4. Third choice.** x
## Your to-dos
- **5. A form.** x
FXEND

cat >"$FX/reports/r2.md" <<'FXEND'
## Approve
- **1. Second approval.** x
- **2. Third approval.** x
FXEND

cat >"$FX/reports/r3.md" <<'FXEND'
## Decide
- **1. Pick a date.** x
## For the weekly review
- **2. Rename a folder.** x
FXEND

cat >"$FX/mapping.json" <<'FXEND'
{"mornings": {
 "d1": {"reports": [{"file": "r1.md", "lines": [1, 5]}]},
 "d2": {"reports": [{"file": "r1.md", "lines": [6, 100000]}, {"file": "r2.md"}]},
 "d3": {"reports": []},
 "d4": {"reports": [{"file": "r3.md"}]}
}}
FXEND

cat >"$FX/map-missing.json" <<'FXEND'
{"mornings": {"d1": {"reports": [{"file": "r1.md"}, {"file": "r9.md"}]}}}
FXEND
printf '%s\n' '{"mornings": {"d1": {"reports": [{"file": "r2.md", "lines": "1-5"}]}}}' >"$FX/map-badlines.json"
printf '%s\n' '{"mornings": ' >"$FX/map-notjson.json"
printf '%s\n' '{"days": {}}' >"$FX/map-nomornings.json"

cp "$FX/today.md" "$FX/locked.md"
chmod 000 "$FX/locked.md"
LOCKED_UNREADABLE=yes
if [ -r "$FX/locked.md" ]; then LOCKED_UNREADABLE=no; fi

manifest "$FX" >"$W/before.txt"
ls -a "$HERE" >"$W/here-before.txt"

echo "handback-count.py suite"

# ---- C1: a clean single Handback; the built-in control printed ----
run "$PY" -B "$S" "$FX/today.md"
eq "C1 a clean Handback exits 0" "$RC" "0"
has "C1 the built-in control is printed and passes" "control: the planted two-part Handback gives"
eq "C1 counts by group (hand-derived: Decide 2, Approve 1, To-do 1)" "$(field decide)/$(field approve)/$(field todo)/$(field items)" "2/1/1/4"
eq "C1 nothing put twice" "$(field put_twice)" "0"
hasnot "C1 no traceback" "Traceback"
run "$PY" -B -c 'raise ValueError("planted")'
has "C1 control: the traceback probe fires on a planted traceback" "Traceback"

# ---- C2/C3: an earlier item put again as new is flagged; a single one is not ----
run "$PY" -B "$S" "$FX/today.md" --earlier "$FX/earlier.md"
eq "C2 an earlier item put again exits 1" "$RC" "1"
has "C2 the repeat is named, with both places" "PUT TWICE (put again as new): Approve 3 \"Install the parser repair.\""
has "C2 the earlier place is named" "earlier.md:3"
eq "C2 put_twice counts it once" "$(field put_twice)" "1"
run "$PY" -B "$S" "$FX/today.md" --earlier "$FX/other.md"
eq "C3 an earlier file without the item: exit 0" "$RC" "0"
eq "C3 a single item is not flagged (control: C2's same probe fired)" "$(field put_twice)" "0"
hasnot "C3 no PUT TWICE line" "PUT TWICE"

# ---- C4/C5: put twice across two parts of one Handback; not within one part ----
run "$PY" -B "$S" "$FX/today.md" "$FX/part2.md"
eq "C4 two parts putting one item: exit 1" "$RC" "1"
has "C4 named as put twice within the Handback" "PUT TWICE (within this Handback): Decide 1 \"Pick the venue for the talk.\""
eq "C4 both parts counted (Decide 3)" "$(field decide)/$(field put_twice)" "3/1"
run "$PY" -B "$S" "$FX/selfrepeat.md"
eq "C5 a repeat inside one part is not paired (the documented rule; control: C4)" "$(field put_twice)/$RC" "0/0"

# ---- C6/C7: items sent to the weekly review are counted apart ----
run "$PY" -B "$S" "$FX/weekly.md"
eq "C6 weekly review: 3 and 4 (nested heading), 7 (its own heading), the Done line" "$(field weekly_review)" "4"
eq "C6 the items put to the owner exclude them (Decide 1, Approve 3)" "$(field decide)/$(field approve)/$(field items)" "1/3/4"
has "C6 the Done line is listed under the weekly review" "weekly.md:15"
has "C6 an inline Decide inside the weekly-review group stays there" "weekly.md:13 7 Decide: split the skill."
run "$PY" -B "$S" "$FX/today.md"
eq "C7 a Handback with no weekly-review group counts 0 (control: C6)" "$(field weekly_review)" "0"
run "$PY" -B "$S" "$FX/weekly.md"
has "C7 control: item 3 of the nested heading is listed by file and line" "weekly.md:7 3 Rename the tools folder."
hasnot "C7 an Approve item naming the weekly review (item 6, line 11) stays Approve" "weekly.md:11"

# ---- C8: the waiting line is never counted as new ----
run "$PY" -B "$S" "$FX/waiting.md"
eq "C8 two waiting lines (one with a link, one with its bold lead)" "$(field waiting_lines)" "2"
eq "C8 neither is counted as new (Decide 1, Approve 1)" "$(field decide)/$(field approve)/$(field items)" "1/1/2"
has "C8 the linked line is listed" "waiting.md:4"
hasnot "C8 a mid-sentence 'still waits' with no link is no waiting line" "waiting.md:6"

# ---- C9: a cross-reference to a numbered item moves nothing; an inline marker still does ----
run "$PY" -B "$S" "$FX/xref.md"
eq "C9 Approve 1, To-do 1, and K1 moved to Decide by its marker" "$(field decide)/$(field approve)/$(field todo)" "1/1/1"

# ---- C10-C13: broken premises print PROBE FAILED and exit 2 ----
run "$PY" -B "$S" "$FX/absent.md"
eq "C10 a missing report exits 2" "$RC" "2"
has "C10 it prints PROBE FAILED and the path" "PROBE FAILED: cannot read $FX/absent.md"
if [ "$LOCKED_UNREADABLE" = yes ]; then
  run "$PY" -B "$S" "$FX/locked.md"
  eq "C11 an unreadable report exits 2" "$RC" "2"
  has "C11 it prints PROBE FAILED, cannot read" "PROBE FAILED: cannot read $FX/locked.md"
else
  echo "  skip — C11: chmod 000 leaves the file readable here (running as root), so the leg proves nothing"
fi
run "$PY" -B "$S" "$FX/today.md" --earlier "$FX/absent-earlier.md"
eq "C12 a missing earlier file exits 2" "$RC" "2"
has "C12 it prints PROBE FAILED" "PROBE FAILED: cannot read $FX/absent-earlier.md"
run "$PY" -B "$S" "$FX/nogroups.md"
eq "C13 a file naming no group and giving no item exits 2" "$RC" "2"
has "C13 it says why" "names none of the Handback's groups"
run "$PY" -B "$S" "$FX/emptygroups.md"
eq "C13 a Handback whose groups hold nothing exits 0 (control: the same check)" "$RC" "0"
eq "C13 and counts zero items" "$(field items)" "0"
run "$PY" -B "$S" "$FX/today.md" "$FX/today.md"
eq "C13 the same part given twice exits 2" "$RC" "2"
has "C13 it says so" "is given twice"

# ---- C14/C15: the mapping mode ----
run "$PY" -B "$S" --mapping "$FX/mapping.json" --reports "$FX/reports"
eq "C14 a mapping with no repeat exits 0" "$RC" "0"
has "C14 d1, lines 1-5 of r1: Decide 1, Approve 1" "| d1 | 1 | 1 | 1 | 0 | 2 | 0 | 0 | 0 |"
has "C14 d2, the rest of r1 and r2: Decide 2, Approve 2, To-do 1" "| d2 | 2 | 2 | 2 | 1 | 5 | 0 | 0 | 0 |"
has "C14 d3, no report: a zero row" "| d3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |"
has "C14 d4: Decide 1 and one item for the weekly review" "| d4 | 1 | 1 | 0 | 0 | 1 | 1 | 0 | 0 |"
eq "C14 the summary" "$(summary)" "mornings=4 reports=4 decide=4 approve=3 todo=1 items=8 weekly_review=1 waiting_lines=0 put_twice=0"
run "$PY" -B "$S" --mapping "$FX/map-missing.json" --reports "$FX/reports"
eq "C15 a mapped report missing exits 2" "$RC" "2"
has "C15 it prints PROBE FAILED and the path" "PROBE FAILED: cannot read $FX/reports/r9.md"
run "$PY" -B "$S" --mapping "$FX/map-badlines.json" --reports "$FX/reports"
eq "C15 a line range that is not [first, last] exits 2" "$RC" "2"
has "C15 it says so" "has a \"lines\" value that is not [first, last]"
hasnot "C15 and prints no traceback (control: C1's planted traceback)" "Traceback"
run "$PY" -B "$S" --mapping "$FX/map-notjson.json" --reports "$FX/reports"
eq "C15 a mapping that is not JSON exits 2" "$RC" "2"
run "$PY" -B "$S" --mapping "$FX/map-nomornings.json" --reports "$FX/reports"
eq "C15 a mapping with no mornings exits 2" "$RC" "2"
run "$PY" -B "$S" --mapping "$FX/absent.json" --reports "$FX/reports"
eq "C15 a missing mapping exits 2" "$RC" "2"
run "$PY" -B "$S" --mapping "$FX/mapping.json" --reports "$FX/no-such-folder"
eq "C15 a missing reports folder exits 2" "$RC" "2"

# ---- C16: E2's planted Handback reads as E2's parser read it ----
run "$PY" -B "$S" "$FX/e2sample.md"
eq "C16 E2's sample: Decide 4 (1, 2, 3, K1), Approve 3 (4, 5, 7), To-do 1 (E9)" "$(field decide)/$(field approve)/$(field todo)/$(field items)" "4/3/1/8"

# ---- C17: the built-in control guards: a copy whose planted text is altered refuses ----
mkdir "$W/broken"
"$PY" -I -B -c '
import sys
src = open(sys.argv[1], encoding="utf-8").read()
old = "\"## Your to-dos\", \"- **5. Sign the form.**\""
if src.count(old) != 1:
    sys.exit("anchor count %d" % src.count(old))
open(sys.argv[2], "w", encoding="utf-8").write(src.replace(old, "\"## Your notes\", \"- **5. Sign the form.**\""))
' "$S" "$W/broken/handback-count.py"
RC_EDIT=$?
eq "C17 the control's anchor occurs once in the script" "$RC_EDIT" "0"
run "$PY" -B "$W/broken/handback-count.py" "$FX/today.md"
eq "C17 a broken control exits 2" "$RC" "2"
has "C17 it prints PROBE FAILED" "PROBE FAILED: the built-in planted Handback gives"

# ---- C18: the reproduction of a measured week, where its data is given ----
if [ -n "${HANDBACK_MAPPING:-}" ]; then
  REPORTS=${HANDBACK_REPORTS:-$VAULT/output/reports}
  run "$PY" -B "$S" --mapping "$HANDBACK_MAPPING" --reports "$REPORTS"
  if [ "$RC" = 0 ] || [ "$RC" = 1 ]; then ok "C18 the mapping runs (exit $RC)"; else no "C18 the mapping runs (exit $RC)"; fi
  hasnot "C18 no PROBE FAILED" "PROBE FAILED"
  for pair in $(printf '%s' "${HANDBACK_EXPECT:-}" | tr ',' ' '); do
    day=${pair%%=*}
    want=${pair#*=}
    got=$(awk -F'|' -v d="$day" '{ gsub(/ /, "", $2) } $2 == d { gsub(/ /, "", $7); print $7 }' "$OUT")
    eq "C18 morning $day: items" "$got" "$want"
  done
  [ -n "${HANDBACK_EXPECT:-}" ] || no "C18 HANDBACK_EXPECT is empty: nothing to compare"
else
  echo "  skip — C18: HANDBACK_MAPPING not set (the reproduction runs only on a vault's own mapping)"
fi

# ---- C20: every file after --earlier is an earlier file (the usage line's FILE ...) ----
run "$PY" -B "$S" "$FX/today.md" --earlier "$FX/other.md" "$FX/earlier.md"
eq "C20 every file after --earlier is earlier" "$(field reports)/$(field earlier_files)/$RC" "1/2/1"
has "C20 so the repeat is put again as new, not within the Handback" "PUT TWICE (put again as new): Approve 3 \"Install the parser repair.\""
run "$PY" -B "$S" --earlier "$FX/other.md" "$FX/today.md"
eq "C20 an earlier file given first leaves no report: exit 2" "$RC" "2"
has "C20 it says so" "PROBE FAILED: no report given"
run "$PY" -B "$S" "$FX/today.md" "$FX/part2.md" --earlier "$FX/other.md"
eq "C20 must not fire: the files before --earlier stay parts of today" "$(field reports)/$(field earlier_files)" "2/1"
run "$PY" -B "$S" "$FX/today.md" --earlier "$FX/other.md" --earlier "$FX/earlier.md"
eq "C20 must not fire: the flag given once per file reads the same" "$(field reports)/$(field earlier_files)/$RC" "1/2/1"
run "$PY" -B "$S" "$FX/today.md" --earlier
eq "C20 --earlier with no file exits 2" "$RC" "2"
has "C20 it says so" "PROBE FAILED: --earlier needs a value"

# ---- C21: a weekly-review item is counted, never paired ----
run "$PY" -B "$S" "$FX/weekly.md" --earlier "$FX/weekly-yesterday.md"
eq "C21 a held item now put as new is flagged; one still held is not" "$(field put_twice)" "1"
has "C21 control: the held item put as new is named" "PUT TWICE (put again as new): Decide 1 \"Pick the venue.\""
hasnot "C21 the held item is not paired" "Weekly review 3 \"Rename the tools folder.\" ("
eq "C21 the weekly-review count is unchanged (C6)" "$(field weekly_review)" "4"

# ---- C22: an earlier file the parser cannot read is refused, never a silent none ----
run "$PY" -B "$S" "$FX/today.md" --earlier "$FX/nogroups.md"
eq "C22 an earlier file naming no group exits 2 (control: C3)" "$RC" "2"
has "C22 it says why" "names none of the Handback's groups"
run "$PY" -B "$S" "$FX/today.md" --earlier "$FX/emptygroups.md"
eq "C22 must not fire: an earlier list that keeps its groups' headings, empty, is read" "$RC/$(field earlier_items)" "0/0"

# ---- C23: a numbered item that says "still waits" beside a link is an item ----
run "$PY" -B "$S" "$FX/waiting-item.md"
eq "C23 the numbered item stays an item; one waiting line" "$(field decide)/$(field waiting_lines)" "2/1"
hasnot "C23 the numbered item is not listed as a waiting line" "waiting-item.md:3"
has "C23 must not fire: the unnumbered linked line is still the waiting line" "waiting-item.md:5"

# ---- C19: the script wrote nothing: fixtures and its own folder byte-identical ----
manifest "$FX" >"$W/after.txt"
ls -a "$HERE" >"$W/here-after.txt"
if cmp -s "$W/before.txt" "$W/after.txt"; then ok "C19 every fixture byte-identical after all runs ($(wc -l <"$W/before.txt" | tr -d ' ') files, sha256 and mode)"; else no "C19 a fixture changed: $(diff "$W/before.txt" "$W/after.txt" | head -3)"; fi
if cmp -s "$W/here-before.txt" "$W/here-after.txt"; then ok "C19 no file appeared beside the script"; else no "C19 the script's folder changed: $(diff "$W/here-before.txt" "$W/here-after.txt" | head -3)"; fi
"$PY" -I -B -c '
import sys
p = sys.argv[1]
b = bytearray(open(p, "rb").read())
b[2] = ord("X") if b[2] != ord("X") else ord("Y")
open(p, "r+b").write(bytes(b))
' "$FX/today.md"
manifest "$FX" >"$W/control.txt"
if cmp -s "$W/before.txt" "$W/control.txt"; then no "C19 control: a one-byte change under the same permissions went unseen"; else ok "C19 control: a one-byte change to a fixture under the same permissions is caught"; fi

TOTAL=$((PASS + FAIL))
echo
if [ "$FAIL" -eq 0 ]; then echo "PASS $PASS/$TOTAL"; exit 0; fi
echo "FAIL $FAIL/$TOTAL"
exit 1
