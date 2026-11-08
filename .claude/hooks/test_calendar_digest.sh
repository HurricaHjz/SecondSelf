#!/bin/sh
# Tests for calendar-digest.py: overdue, due today, due in 7 and 8 days, ticked, withdrawn, approximate,
# a time on a clock-change day, a long overdue list under the cap with the remainder named, a malformed line,
# an absent file, an unreadable file, a planted line that must show and one that must not, and the same
# digest on a second run (resume / compaction restart are stateless re-runs).
set -u
HOOK="$(cd "$(dirname "$0")" && pwd)/calendar-digest.py"
PY=python3
T="2026-10-25"   # a clock-change Sunday (BST ends) as the fixed "today"
fail=0; pass=0
ok()   { pass=$((pass+1)); }
bad()  { fail=$((fail+1)); echo "FAIL: $1"; }
check() { # $1 description, $2 expected-substring, $3 output
  case "$3" in *"$2"*) ok ;; *) bad "$1 (expected: $2)";; esac; }
absent() { # $1 description, $2 forbidden-substring, $3 output
  case "$3" in *"$2"*) bad "$1 (must not contain: $2)";; *) ok ;; esac; }

D=$(mktemp -d); trap 'rm -rf "$D"' EXIT
cat > "$D/CALENDAR.md" <<'EOF'
# CALENDAR
## Items
- [ ] 2026-10-05 · overdue twenty days · OLD-ITEM
- [ ] 2026-10-24 16:00 · overdue yesterday with a time · YESTERDAY-ITEM
- [ ] 2026-10-25 01:30 · due today, a time on the clock-change day · TODAY-ITEM
- [ ] 2026-10-28 · due in three days · PLANTED-SHOW
- [ ] 2026-11-01 · due in seven days, the edge · EDGE-ITEM
- [ ] 2026-11-02 · due in eight days · PLANTED-HIDE
- [x] 2026-10-26 · ticked, must not show · TICKED-ITEM
- [-] 2026-10-26 · withdrawn, must not show · WITHDRAWN-ITEM
- [ ] when Fable 5.5 is out · approximate · APPROX-ITEM
- [ ] ~2026-11 · approximate month · APPROX-MONTH
- [?] 2026-10-26 · malformed mark · MALFORMED-ITEM
- [ ]
- plain bullet, not an item
EOF
OUT=$(CLAUDE_PROJECT_DIR="$D" CALENDAR_DIGEST_TODAY="$T" $PY "$HOOK")
check "header counts" "2 overdue · 3 due within 7 days · 2 approximate-dated · 2 malformed" "$OUT"
check "overdue old" "overdue: 2026-10-05 · overdue twenty days · OLD-ITEM" "$OUT"
check "overdue yesterday" "overdue: 2026-10-24 16:00" "$OUT"
check "due today on the clock-change day" "due: 2026-10-25 01:30" "$OUT"
check "planted must show" "PLANTED-SHOW" "$OUT"
check "edge day 7 shows" "EDGE-ITEM" "$OUT"
absent "day 8 hidden" "PLANTED-HIDE" "$OUT"
absent "ticked hidden" "TICKED-ITEM" "$OUT"
absent "withdrawn hidden" "WITHDRAWN-ITEM" "$OUT"
absent "approximate not listed as due" "APPROX-ITEM" "$OUT"
absent "malformed not listed" "MALFORMED-ITEM" "$OUT"
OUT2=$(CLAUDE_PROJECT_DIR="$D" CALENDAR_DIGEST_TODAY="$T" $PY "$HOOK")
[ "$OUT" = "$OUT2" ] && ok || bad "second run (resume) differs from the first"

# absent file: one line
D2=$(mktemp -d); OUT=$(CLAUDE_PROJECT_DIR="$D2" $PY "$HOOK"); rm -rf "$D2"
check "absent file one line" "CALENDAR.md absent" "$OUT"
[ "$(printf '%s\n' "$OUT" | wc -l | tr -d ' ')" = "1" ] && ok || bad "absent file printed more than one line"

# unreadable file: one line naming the error
D3=$(mktemp -d); printf -- '- [ ] 2026-10-25 · x\n' > "$D3/CALENDAR.md"; chmod 000 "$D3/CALENDAR.md"
OUT=$(CLAUDE_PROJECT_DIR="$D3" CALENDAR_DIGEST_TODAY="$T" $PY "$HOOK"); chmod 644 "$D3/CALENDAR.md"; rm -rf "$D3"
case "$OUT" in *"unreadable"*|*"2026-10-25"*) ok ;; *) bad "unreadable file not reported: $OUT";; esac

# long overdue list: everything that fits, the remainder named, output under the cap
D4=$(mktemp -d); { echo "## Items"; i=1; while [ $i -le 400 ]; do printf -- '- [ ] 2026-09-%02d · overdue item number %d with some words to take space · [[page-%d]]\n' $(( (i % 28) + 1 )) $i $i; i=$((i+1)); done; } > "$D4/CALENDAR.md"
OUT=$(CLAUDE_PROJECT_DIR="$D4" CALENDAR_DIGEST_TODAY="$T" $PY "$HOOK"); rm -rf "$D4"
check "long list header" "400 overdue" "$OUT"
check "long list remainder named" "more line(s): read CALENDAR.md" "$OUT"
BYTES=$(printf '%s' "$OUT" | wc -c | tr -d ' ')
[ "$BYTES" -le 10000 ] && ok || bad "output over the hook limit: $BYTES bytes"
[ "$BYTES" -ge 8000 ] && ok || bad "output far under the cap, lines were cut too early: $BYTES bytes"

# the live file: parses, exits 0, header present (a copy not yet through setup.sh has none: one line says so)
OUT=$(CLAUDE_PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)" $PY "$HOOK"); rc=$?
[ "$rc" = "0" ] && ok || bad "live run exit $rc"
case "$OUT" in *"calendar ("*|*"CALENDAR.md absent"*) ok ;; *) bad "live header: $OUT";; esac

echo "calendar-digest: $pass passed, $fail failed"
[ "$fail" = "0" ]
