#!/bin/sh
# test_grants_ledger.sh — regression suite for grants-ledger.py (delegate skill, the grants ledger).
#
# Every fixture is a throwaway run store under one `mktemp -d` (records and kept brief copies laid out
# as lane.py lays them out), removed at exit; the script reads it through LLM_WIKI_STORE. The script is
# stdout only, so the last leg checks that the store, and the script's own folder, is byte-identical
# after all the runs, with a control that changes one byte of a brief copy under the same permissions.
#
# Controls: every leg that asserts a clean result sits beside a leg that plants the fault and proves
# the same probe fires. Expected rows and statuses are hand-derived from the fixtures below.
#
# One real record can be read too, read-only, where it is named: LEDGER_RUN=<run id> (the store is
# $LLM_WIKI_STORE, else ~/.llm-wiki); its rows are checked against the record's lane-open lines counted
# by a grep of their own.
#
# Run:  sh test_grants_ledger.sh      (last line: PASS n/n or FAIL k/n; exit 0 only when clean)
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
S="$HERE/grants-ledger.py"
PY="${PYTHON:-python3}"
PASS=0
FAIL=0
ok() { PASS=$((PASS + 1)); echo "  ok   — $1"; }
no() { FAIL=$((FAIL + 1)); echo "FAIL   — $1"; }
eq() { if [ "$2" = "$3" ]; then ok "$1"; else no "$1 (got '$2', want '$3')"; fi; }

REAL_STORE=${LLM_WIKI_STORE:-}
# The script reads the store through realpath (as lane.py does), so the fixture paths are real paths
# too: on a system where the temporary folder sits behind a link, the printed paths still match.
W=$(cd "$(mktemp -d "${TMPDIR:-/tmp}/suite.XXXXXX")" && pwd -P)
[ -n "$W" ] && [ -d "$W" ] || { echo "PROBE FAILED: no temporary folder"; echo "FAIL 1/1"; exit 2; }
OUT="$W/out.txt"
cleanup() { chmod -R u+rw "$W" >/dev/null 2>&1; rm -rf "$W"; }
trap cleanup EXIT
[ -f "$S" ] || { echo "PROBE FAILED: no grants-ledger.py at $S"; echo "FAIL 1/1"; exit 2; }

run() { "$@" >"$OUT" 2>&1; RC=$?; }
has() { if grep -qF -- "$2" "$OUT"; then ok "$1"; else no "$1 (stdout lacks '$2')"; fi; }
hasnot() { if grep -qF -- "$2" "$OUT"; then no "$1 (stdout still holds '$2')"; else ok "$1"; fi; }
summary() { grep '^LEDGER SUMMARY' "$OUT" | sed 's/^LEDGER SUMMARY //'; }
field() { summary | tr ' ' '\n' | grep "^$1=" | cut -d= -f2; }
row() { grep -F "| $1 |" "$OUT" | head -1; }

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

ST="$W/store/spawn-records"
for l in A B C D E F I K L; do mkdir -p "$ST/fx-run-in-$l"; done
copy() { printf '%s' "$ST/fx-run-in-$1/fx-run-brief-$1.md"; }

cat >"$(copy A)" <<'FXEND'
You are a builder.

TASK
Build the thing.

GRANTS (the run's record of what this lane was given)
DECISIONS: none bear on this task.
- Bounds: the plan's row; the hard limits of the run.
- Pushed: lesson L3, because the seat cannot read the lessons page.
- Held by the reviewer: lesson L7.
- Left out on purpose: the drafts, so the work stays independent.
- Second seat: none.
- Read: the vault. Write: the package folder.

REPORT: short.
FXEND

cat >"$(copy B)" <<'FXEND'
TASK
Build the thing. Bounds are named in prose only.

REPORT: short.
FXEND

cat >"$(copy C)" <<'FXEND'
TASK
Build the thing.

GRANTS
Read: the vault and the stage folder. Write: the stage folder only.

VERIFICATION
- the tests pass.
FXEND

cp "$(copy A)" "$(copy D)"

cat >"$(copy E)" <<'FXEND'
TASK
Quote the template:
```
GRANTS
- Bounds: b
- Pushed: p
- Held by the reviewer: h
- Left out on purpose: l
- Second seat: s
```
REPORT: short.
FXEND

cat >"$(copy F)" <<'FXEND'
GRANTS
- Bounds: the plan's row.
- Pushed: none.
- Second seat:

REPORT: short.
FXEND

cat >"$(copy I)" <<'FXEND'
GRANTS
Read: the vault.

Later the full block:

GRANTS
- **Bounds:** the plan's row.
- **Pushed:** none.
- **Held by the reviewer:** none.
- **Left out on purpose:** the drafts,
  so the work stays independent.
- **Second seat:** one critic, by the contract ground.
FXEND
cp "$(copy A)" "$ST/fx-run-in-A/fx-run-brief-A-pass1.md"

# L16: a template's GRANTS block sent with three slots unfilled, in the two slot shapes the brief
# templates use; and a filled block whose text holds single braces and a heredoc marker, no slot.
cat >"$(copy K)" <<'FXEND'
TASK
Build the thing.

GRANTS
- Bounds: {{the job page's Bounds and lesson index (path)}}
- Pushed: none.
- Held by the reviewer: none.
- Left out on purpose: {{what, and why | none}}
- Second seat: <<GRANTS_SECOND_SEAT>>

REPORT: short.
FXEND

cat >"$(copy L)" <<'FXEND'
TASK
Build the thing.

GRANTS
- Bounds: the plan's row; paths written as {run}/pkg, never as a slot.
- Pushed: none.
- Held by the reviewer: none.
- Left out on purpose: the heredoc form cat <<'FX', which the fence refuses.
- Second seat: none.

REPORT: short.
FXEND

{
  printf '{"event": "run-open", "run": "fx-run"}\n'
  for l in A B C D E F; do
    printf '{"event": "lane-open", "run": "fx-run", "lane": "%s", "brief": "/elsewhere/%s.md", "brief_copy": "%s"}\n' "$l" "$l" "$(copy $l)"
  done
  printf '{"event": "lane-open", "run": "fx-run", "lane": "G", "brief": "/elsewhere/G.md"}\n'
  printf '{"event": "lane-open", "run": "fx-run", "lane": "H", "brief_copy": "%s"}\n' "$ST/fx-run-in-H/fx-run-brief-H.md"
  printf '{"event": "lane-resumed", "run": "fx-run", "lane": "A", "brief_copy": "%s"}\n' "$ST/fx-run-in-A/fx-run-brief-A-pass1.md"
  printf '{"event": "lane-open", "run": "fx-run", "lane": "I", "brief_copy": "%s"}\n' "$(copy I)"
  printf '%s\n' '{"event": "lane-open", "lane": "J", "brief_copy": '
} >"$ST/fx-run.jsonl"

{
  printf '{"event": "run-open", "run": "fx-clean"}\n'
  printf '{"event": "lane-open", "run": "fx-clean", "lane": "A", "brief_copy": "%s"}\n' "$(copy A)"
  printf '{"event": "lane-open", "run": "fx-clean", "lane": "I", "brief_copy": "%s"}\n' "$(copy I)"
} >"$ST/fx-clean.jsonl"

printf '{"event": "run-open", "run": "fx-none"}\n{"event": "run-close", "run": "fx-none"}\n' >"$ST/fx-none.jsonl"

chmod 000 "$(copy D)"
LOCKED_UNREADABLE=yes
if [ -r "$(copy D)" ]; then LOCKED_UNREADABLE=no; fi

manifest "$W/store" >"$W/before.txt"
ls -a "$HERE" >"$W/here-before.txt"

echo "grants-ledger.py suite"

# ---- L1-L9: the planted record, one lane per case ----
run env LLM_WIKI_STORE="$W/store" "$PY" -B "$S" --run fx-run
eq "L1 a record with warnings exits 1" "$RC" "1"
has "L1 the built-in control is printed and passes" "control: the planted briefs read five fields, old form"
hasnot "L1 no traceback" "Traceback"
SAVED="$W/l1.txt"
cp "$OUT" "$SAVED"
run "$PY" -B -c 'raise ValueError("planted")'
has "L1 control: the traceback probe fires on a planted traceback" "Traceback"
cp "$SAVED" "$OUT"
eq "L1 one row per lane-open; the resumed pass adds none (A B C D E F G H I)" "$(field rows)" "9"
case "$(row A)" in
  *"| five fields | the plan's row; the hard limits of the run. | lesson L3, because the seat cannot read the lessons page. | lesson L7. | the drafts, so the work stays independent. | none. |"*)
    ok "L1 lane A: five fields, each whole, in order" ;;
  *) no "L1 lane A's row: $(row A)" ;;
esac
case "$(row A)" in
  *"DECISIONS: none bear on this task. / - Read: the vault. Write: the package folder."*) ok "L1 lane A: the block's other lines kept" ;;
  *) no "L1 lane A's other lines: $(row A)" ;;
esac
hasnot "L1 lane A carries no warning" "lane A,"
has "L2 a brief with no GRANTS line is warned, by name" "WARNING: no GRANTS line: lane B, $(copy B)"
has "L3 the old free form is listed as old form" "WARNING: old form, none of the five fields: lane C, $(copy C)"
case "$(row C)" in
  *"| old form |"*"Read: the vault and the stage folder. Write: the stage folder only."*) ok "L3 the old form's free text is kept in its row" ;;
  *) no "L3 lane C's row: $(row C)" ;;
esac
if [ "$LOCKED_UNREADABLE" = yes ]; then
  has "L4 an unreadable copy prints cannot read, never silence" "WARNING: cannot read the brief copy of lane D: $(copy D)"
  case "$(row D)" in *"| cannot read |"*) ok "L4 its row says cannot read" ;; *) no "L4 lane D's row: $(row D)" ;; esac
else
  echo "  skip — L4: chmod 000 leaves the copy readable here (running as root), so the leg proves nothing"
fi
has "L5 a GRANTS only inside a code fence counts as absent" "WARNING: no GRANTS line: lane E, $(copy E) (a GRANTS inside a code fence, line 4, counts as absent)"
has "L6 a block short of fields names them (an empty field counts as missing)" "WARNING: GRANTS lacks Held by the reviewer, Left out on purpose, Second seat (block at line 1): lane F"
has "L7 a lane-open with no brief copy is warned" "WARNING: no brief copy recorded: lane G"
has "L7 a brief copy that is gone prints cannot read" "WARNING: cannot read the brief copy of lane H"
has "L8 a record line that cannot be read is warned, by number" "WARNING: cannot read record line 12 of $ST/fx-run.jsonl"
case "$(row I)" in
  *"| five fields | the plan's row. | none. | none. | the drafts, so the work stays independent. | one critic, by the contract ground. |"*)
    ok "L9 of two blocks the full one is read; bold names and a continuation line parse" ;;
  *) no "L9 lane I's row: $(row I)" ;;
esac
eq "L9 the summary" "$(summary)" "records=1 record_lines=12 rows=9 five_fields=2 lacks=1 old_form=1 no_grants=2 cannot_read=2 no_copy=1 warnings=8"

# ---- L10: the must-not-fire record: five fields everywhere, no warning ----
run env LLM_WIKI_STORE="$W/store" "$PY" -B "$S" --run fx-clean
eq "L10 a clean record exits 0" "$RC" "0"
eq "L10 two rows, both five fields, no warning (control: L2's same probe fired)" "$(field rows)/$(field five_fields)/$(field warnings)" "2/2/0"
hasnot "L10 no WARNING line" "WARNING"

# ---- L11: --brief, for a brief about to be sent ----
run "$PY" -B "$S" --brief "$(copy A)"
eq "L11 a brief with the five fields: exit 0, no warning" "$RC/$(field warnings)" "0/0"
run "$PY" -B "$S" --brief "$(copy B)"
eq "L11 a brief without the block: exit 1" "$RC" "1"
has "L11 and the warning names it" "WARNING: no GRANTS line: lane (brief), $(copy B)"

# ---- L12: broken premises print PROBE FAILED and exit 2 ----
run env LLM_WIKI_STORE="$W/store" "$PY" -B "$S" --run fx-absent
eq "L12 a missing record exits 2" "$RC" "2"
has "L12 it prints PROBE FAILED, cannot read the record" "PROBE FAILED: cannot read the record $ST/fx-absent.jsonl"
run env LLM_WIKI_STORE="$W/store" "$PY" -B "$S" --run fx-none
eq "L12 a record with no lane-open exits 2" "$RC" "2"
has "L12 it says so" "holds no lane-open line (2 lines read)"
run env LLM_WIKI_STORE="$W/store" "$PY" -B "$S" --run ../fx-run
eq "L12 a run id with a path in it exits 2" "$RC" "2"
run "$PY" -B "$S"
eq "L12 no argument exits 2" "$RC" "2"
run "$PY" -B "$S" --run
eq "L12 --run with no value exits 2" "$RC" "2"

# ---- L13: the built-in control guards: a copy whose planted brief is altered refuses ----
mkdir "$W/broken"
"$PY" -I -B -c '
import sys
src = open(sys.argv[1], encoding="utf-8").read()
old = "\"TASK\", \"```\", \"GRANTS\""
if src.count(old) != 1:
    sys.exit("anchor count %d" % src.count(old))
open(sys.argv[2], "w", encoding="utf-8").write(src.replace(old, "\"TASK\", \"\", \"GRANTS\""))
' "$S" "$W/broken/grants-ledger.py"
eq "L13 the control's anchor occurs once in the script" "$?" "0"
run "$PY" -B "$W/broken/grants-ledger.py" --brief "$(copy A)"
eq "L13 a broken control exits 2" "$RC" "2"
has "L13 it prints PROBE FAILED" "PROBE FAILED: the built-in planted briefs read"

# ---- L14: one real record, read-only, where it is named ----
if [ -n "${LEDGER_RUN:-}" ]; then
  if [ -n "$REAL_STORE" ]; then RS="$REAL_STORE"; else RS="$HOME/.llm-wiki"; fi
  REC="$RS/spawn-records/$LEDGER_RUN.jsonl"
  OPENS=$(grep -c '"event": *"lane-open"' "$REC")
  if [ "${OPENS:-0}" -gt 0 ]; then ok "L14 control: the record's own grep counts $OPENS lane-open lines"; else no "L14 control: no lane-open line found by grep in $REC"; fi
  run env LLM_WIKI_STORE="$RS" "$PY" -B "$S" --run "$LEDGER_RUN"
  if [ "$RC" = 0 ] || [ "$RC" = 1 ]; then ok "L14 the real record reads (exit $RC)"; else no "L14 the real record reads (exit $RC)"; fi
  eq "L14 one row per lane-open line" "$(field rows)" "$OPENS"
  echo "       $(summary)"
else
  echo "  skip — L14: LEDGER_RUN not set (no real record named)"
fi

# ---- L16: a field still holding a template slot counts as missing ----
run "$PY" -B "$S" --brief "$(copy K)"
eq "L16 a block with unfilled slots exits 1, one warning" "$RC/$(field lacks)/$(field warnings)" "1/1/1"
has "L16 the warning names the three slotted fields" "WARNING: GRANTS lacks Bounds, Left out on purpose, Second seat (block at line 4): lane (brief), $(copy K)"
run "$PY" -B "$S" --brief "$(copy L)"
eq "L16 must not fire: a filled block with braces and a heredoc marker in its text" "$RC/$(field five_fields)/$(field warnings)" "0/1/0"

# ---- L17: the ledger says which helpers it cannot see ----
run env LLM_WIKI_STORE="$W/store" "$PY" -B "$S" --run fx-clean
has "L17 a record's ledger says in-session helpers are not listed" "Helpers spawned in-session keep no brief copy and are not listed: this ledger covers the record's lanes only."
eq "L17 the line is no warning: the clean record still exits 0 (L10)" "$RC/$(field warnings)" "0/0"
run "$PY" -B "$S" --brief "$(copy A)"
hasnot "L17 must not fire: --brief alone reads no record, so the line is not printed" "Helpers spawned in-session"

# ---- L15: the script wrote nothing: the store and its own folder byte-identical ----
manifest "$W/store" >"$W/after.txt"
ls -a "$HERE" >"$W/here-after.txt"
if cmp -s "$W/before.txt" "$W/after.txt"; then ok "L15 every record and brief copy byte-identical after all runs ($(wc -l <"$W/before.txt" | tr -d ' ') files, sha256 and mode)"; else no "L15 the store changed: $(diff "$W/before.txt" "$W/after.txt" | head -3)"; fi
if cmp -s "$W/here-before.txt" "$W/here-after.txt"; then ok "L15 no file appeared beside the script"; else no "L15 the script's folder changed: $(diff "$W/here-before.txt" "$W/here-after.txt" | head -3)"; fi
"$PY" -I -B -c '
import sys
p = sys.argv[1]
b = bytearray(open(p, "rb").read())
b[2] = ord("X") if b[2] != ord("X") else ord("Y")
open(p, "r+b").write(bytes(b))
' "$(copy A)"
manifest "$W/store" >"$W/control.txt"
if cmp -s "$W/before.txt" "$W/control.txt"; then no "L15 control: a one-byte change under the same permissions went unseen"; else ok "L15 control: a one-byte change to a brief copy under the same permissions is caught"; fi

TOTAL=$((PASS + FAIL))
echo
if [ "$FAIL" -eq 0 ]; then echo "PASS $PASS/$TOTAL"; exit 0; fi
echo "FAIL $FAIL/$TOTAL"
exit 1
