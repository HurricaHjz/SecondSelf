#!/bin/sh
# test_read_usage.sh — the suite for read-usage.py (delegate skill: the hands-off run's usage row).
#
# The reader starts two outside programs, `claude -p /usage` and `codex app-server`. This suite never
# starts either: USAGE_CLAUDE_BIN and USAGE_CODEX_BIN point at stand-ins written into one mktemp -d
# directory, which the suite removes. Legs: both windows read and printed, in the stand-in's shape and
# in the shape a live reading printed (a window's heading and figure on one line); each kind of
# reading the script must refuse to guess (a failed exit, an unrecognised shape, a missing program, a
# silent server past its bound, a notice that usage limits are unavailable, window headings with no
# figure, a figure with a sign (`-1%`, `+4%`, a Unicode minus), a progress line that names no usage
# window, alone or before real windows (`Download 42% complete`), a window heading followed only by
# such a line, with or without an unavailable-usage notice between them, a token glued to a letter
# (`x-7%`), a whole token above 100 after a valid window, an Astra window whose used percent is
# absent, null, a string or out of range) prints `could not read` and exits 1, while valid figures at the
# edges (0, 100, a decimal, a dash with a space before a figure) with the live text's trailing notes,
# and a real `4% used` whose line says its reset time is unavailable, are read; a bad bound is a
# usage error (exit 2);
# the head-role fence clears the reader's own command and still denies the `claude -p '/usage'` form
# it replaces (the control); and the last legs prove the suite and the reader wrote nothing beside
# the script: a checksum-and-mode manifest of this directory before and after, with a planted
# same-length change as its control, and a scan of the reader's source for write calls whose own
# planted control must hit.
#
# Run:  sh test_read_usage.sh          (from anywhere; it finds read-usage.py beside itself)
# READ_USAGE_PY and READ_USAGE_FENCE may name staged readers and a separate fence checker.
# The last line is PASS n/n or FAIL k/n; a broken premise prints PROBE FAILED and exits 2.
set -u

HERE=$(cd "$(dirname "$0")" && pwd) || { echo 'PROBE FAILED: cannot locate the test directory'; echo 'FAIL 1/1'; exit 2; }
PY=${PYTHON:-python3}
R=${READ_USAGE_PY:-$HERE/read-usage.py}
FENCE=${READ_USAGE_FENCE:-$HERE/lane-fence.py}
command -v "$PY" >/dev/null || { echo "PROBE FAILED: no $PY on PATH"; echo 'FAIL 1/1'; exit 2; }
[ -f "$R" ] || { echo "PROBE FAILED: no usage reader at $R"; echo 'FAIL 1/1'; exit 2; }
export PYTHONDONTWRITEBYTECODE=1

W=$(mktemp -d "${TMPDIR:-/tmp}/read-usage-suite.XXXXXXXX") || { echo 'PROBE FAILED: cannot create a fixture directory'; echo 'FAIL 1/1'; exit 2; }
cleanup() { rm -rf "$W"; }
trap cleanup EXIT INT TERM

PASS=0; FAIL=0
ok() { PASS=$((PASS + 1)); echo "  ok   — $1"; }
no() { FAIL=$((FAIL + 1)); echo "FAIL   — $1"; }

# The manifest of the script's own directory, taken before any leg runs (the last legs compare it).
manifest() { "$PY" -B - "$1" <<'READ_USAGE_MANIFEST_END'
import hashlib, os, sys
root = sys.argv[1]
for base, dirs, files in os.walk(root):
    dirs[:] = sorted(d for d in dirs if d != "__pycache__")
    for name in sorted(files):
        p = os.path.join(base, name)
        with open(p, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        print("%s %o %s" % (digest, os.stat(p).st_mode & 0o777, os.path.relpath(p, root)))
READ_USAGE_MANIFEST_END
}
BEFORE=$(manifest "$HERE")
[ -n "$BEFORE" ] || { echo 'PROBE FAILED: the manifest of the script directory is empty'; echo 'FAIL 1/1'; exit 2; }

# ------------------------------------------------------------------ the stand-ins ----
mkdir -p "$W/bin"
cat > "$W/bin/claude-ok" <<'CLAUDE_OK_END'
#!/bin/sh
[ "$1" = "-p" ] && [ "$2" = "/usage" ] || { echo "stand-in: unexpected arguments: $*" >&2; exit 9; }
printf '\033[1mCurrent session\033[0m\n  4%% used · resets 4am (Europe/London)\nCurrent week (all models)\n  17%% used · resets Oct 15\nnothing else\n'
CLAUDE_OK_END
cat > "$W/bin/claude-fail" <<'CLAUDE_FAIL_END'
#!/bin/sh
echo "stand-in: not logged in" >&2
exit 1
CLAUDE_FAIL_END
cat > "$W/bin/claude-odd" <<'CLAUDE_ODD_END'
#!/bin/sh
printf 'Hello there\nNo figures today\n'
CLAUDE_ODD_END
# A live reading's shape: each window's heading and figure on one line (three windows).
cat > "$W/bin/claude-live" <<'CLAUDE_LIVE_END'
#!/bin/sh
[ "$1" = "-p" ] && [ "$2" = "/usage" ] || { echo "stand-in: unexpected arguments: $*" >&2; exit 9; }
printf 'Current session: 34%% used · resets Oct 5 at 8pm (Europe/London)\nCurrent week (all models): 67%% used · resets Oct 8 at 7am (Europe/London)\nCurrent week (one model): 5%% used · resets Oct 8 at 7am (Europe/London)\n'
CLAUDE_LIVE_END
# Exit 0 with no figure: a notice, headings alone, and a pair whose first heading has no figure.
cat > "$W/bin/claude-unavailable" <<'CLAUDE_UNAVAILABLE_END'
#!/bin/sh
printf 'Usage limits unavailable for this session\n'
CLAUDE_UNAVAILABLE_END
cat > "$W/bin/claude-unavailable-download" <<'CLAUDE_UNAVAILABLE_DOWNLOAD_END'
#!/bin/sh
printf 'Usage limits unavailable for this session\nDownload 42%% complete\n'
CLAUDE_UNAVAILABLE_DOWNLOAD_END
cat > "$W/bin/claude-pending-unavailable" <<'CLAUDE_PENDING_UNAVAILABLE_END'
#!/bin/sh
printf 'Current session\nUsage limits unavailable\nDownload 42%% complete\n'
CLAUDE_PENDING_UNAVAILABLE_END
cat > "$W/bin/claude-worded-unavailable" <<'CLAUDE_WORDED_UNAVAILABLE_END'
#!/bin/sh
printf 'Current session\n%s\nDownload 42%% complete\n' "$USAGE_NOTICE"
CLAUDE_WORDED_UNAVAILABLE_END
cat > "$W/bin/claude-reset-unavailable" <<'CLAUDE_RESET_UNAVAILABLE_END'
#!/bin/sh
printf 'Current session: 4%% used\nReset time unavailable\n'
CLAUDE_RESET_UNAVAILABLE_END
cat > "$W/bin/claude-reset-unavailable-inline" <<'CLAUDE_RESET_UNAVAILABLE_INLINE_END'
#!/bin/sh
printf 'Current session usage: 4%% used; reset time unavailable\n'
CLAUDE_RESET_UNAVAILABLE_INLINE_END
cat > "$W/bin/claude-reset-clause" <<'CLAUDE_RESET_CLAUSE_END'
#!/bin/sh
printf 'Current session usage: 4%% used; reset times for usage limits are unavailable\n'
CLAUDE_RESET_CLAUSE_END
cat > "$W/bin/claude-borrow" <<'CLAUDE_BORROW_END'
#!/bin/sh
printf 'Current session\nDownload 42%% complete\n'
CLAUDE_BORROW_END
cat > "$W/bin/claude-headings" <<'CLAUDE_HEADINGS_END'
#!/bin/sh
printf 'Current session\nCurrent week (all models)\n'
CLAUDE_HEADINGS_END
cat > "$W/bin/claude-partial" <<'CLAUDE_PARTIAL_END'
#!/bin/sh
printf 'Current session\nCurrent week (all models)\n  17%% used · resets Oct 15\n'
CLAUDE_PARTIAL_END
# Exit 0 with a figure that is no real window figure: a sign (the review's case, a plus, a Unicode
# minus), a progress line that names no window (the review's case, alone and before real windows),
# a token glued to a letter, and a whole token above 100 on a line after a valid window.
cat > "$W/bin/claude-signed" <<'CLAUDE_SIGNED_END'
#!/bin/sh
printf 'Current session: -1%% used\n'
CLAUDE_SIGNED_END
cat > "$W/bin/claude-download" <<'CLAUDE_DOWNLOAD_END'
#!/bin/sh
printf 'Download 42%% complete\n'
CLAUDE_DOWNLOAD_END
cat > "$W/bin/claude-plus" <<'CLAUDE_PLUS_END'
#!/bin/sh
printf 'Current session: +4%% used · resets 4am\nCurrent week (all models): 17%% used · resets Oct 15\n'
CLAUDE_PLUS_END
cat > "$W/bin/claude-minus" <<'CLAUDE_MINUS_END'
#!/bin/sh
printf 'Current session: \342\210\2224%% used · resets 4am\nCurrent week (all models): 17%% used · resets Oct 15\n'
CLAUDE_MINUS_END
cat > "$W/bin/claude-before" <<'CLAUDE_BEFORE_END'
#!/bin/sh
printf 'Download 42%% complete\nCurrent session: 4%% used · resets 4am\nCurrent week (all models): 17%% used · resets Oct 15\n'
CLAUDE_BEFORE_END
cat > "$W/bin/claude-glued" <<'CLAUDE_GLUED_END'
#!/bin/sh
printf 'Current session: x-7%% used · resets 4am\nCurrent week (all models): 17%% used · resets Oct 15\n'
CLAUDE_GLUED_END
cat > "$W/bin/claude-big" <<'CLAUDE_BIG_END'
#!/bin/sh
printf 'Current session: 4%% used · resets 4am\n  of which 1000%% extra\nCurrent week (all models): 17%% used · resets Oct 15\n'
CLAUDE_BIG_END
# Valid readings at the edges: 0, 100 and a decimal figure; a dash with a space before a figure (a
# separator, never a sign); the recorded live shape with its trailing notes, which name no window.
cat > "$W/bin/claude-edges" <<'CLAUDE_EDGES_END'
#!/bin/sh
printf 'Current session - 0%% used · resets 4am\nCurrent week (all models): 100%% used · resets Oct 15\nCurrent week (one model): 4.5%% used · resets Oct 15\nWhat'"'"'s contributing to your limits usage?\nApproximate, based on local sessions on this machine\n'
CLAUDE_EDGES_END
# The Codex stand-in speaks the app-server's line protocol: it answers `initialize` (id 1) and
# `account/rateLimits/read` (id 2), each reply one JSON line; its first argument picks the case.
cat > "$W/bin/codex-server.py" <<'CODEX_SERVER_END'
import copy, json, sys, time
mode = sys.argv[1]
if mode == "silent":
    time.sleep(30)
    sys.exit(0)
for line in sys.stdin:
    try:
        msg = json.loads(line)
    except ValueError:
        continue
    if msg.get("id") == 1:
        print(json.dumps({"method": "note", "params": {}}))          # a notification to skip
        print(json.dumps({"id": 1, "result": {"userAgent": "stand-in"}}))
    elif msg.get("id") == 2:
        if mode == "ok":
            result = {"rateLimits": {"primary": {"usedPercent": 19, "windowDurationMins": 10080,
                                                  "resetsAt": 1791955800}}}
        elif mode in ("null", "string", "range"):
            used = {"null": None, "string": "19", "range": 150}[mode]
            result = {"rateLimits": {"primary": {"usedPercent": used, "windowDurationMins": 10080,
                                                  "resetsAt": 1791955800}}}
        elif mode.startswith("live"):
            # The supplied live shape: two copies of the primary, null secondaries and
            # two reset credits. Figures, durations and timestamps come from that sample.
            limit = {"limitId": "codex", "limitName": None,
                     "primary": {"usedPercent": 32, "windowDurationMins": 10080,
                                 "resetsAt": 1794588090},
                     "secondary": None,
                     "credits": {"hasCredits": True, "unlimited": False, "balance": "fixture"},
                     "individualLimit": None, "spendControlReached": False,
                     "planType": "fixture", "rateLimitReachedType": None}
            result = {"rateLimits": limit, "rateLimitsByLimitId": {"codex": copy.deepcopy(limit)},
                      "rateLimitResetCredits": {"availableCount": 2, "credits": [
                          {"id": "first", "resetType": "fixture", "status": "fixture",
                           "grantedAt": 1793476701, "expiresAt": 1796068701,
                           "title": "fixture", "description": "fixture"},
                          {"id": "second", "resetType": "fixture", "status": "fixture",
                           "grantedAt": 1793572292, "expiresAt": 1796164292,
                           "title": "fixture", "description": "fixture"}]},
                      "accountId": "fixture", "rateLimitUpsell": None}
            if mode == "live-missing-primary":
                del result["rateLimits"]["primary"]["usedPercent"]
            elif mode == "live-missing-secondary":
                # Five hours, converted to minutes; the other windows remain valid.
                result["rateLimits"]["secondary"] = {"windowDurationMins": 5 * 60,
                                                     "resetsAt": 1794588090}
            elif mode == "live-missing-mapped":
                del result["rateLimitsByLimitId"]["codex"]["primary"]["usedPercent"]
            elif mode == "live-no-credits":
                del result["rateLimitResetCredits"]
        elif mode == "minutes-missing":
            # Review V1: describe() reads windowMinutes as a length too, so a window given that
            # way without a used percent must be refused like a windowDurationMins one.
            result = {"rateLimits": {"primary": {"usedPercent": 32, "windowMinutes": 10080},
                                     "secondary": {"windowMinutes": 300, "resetsAt": 1794588090}}}
        elif mode == "used-only":
            # Both accepted spellings still identify windows without a duration.
            result = {"windows": [{"usedPercent": 0}, {"used_percent": 100}]}
        else:
            result = {"rateLimits": {"something": "else"}}
        print(json.dumps({"id": 2, "result": result}))
    sys.stdout.flush()
CODEX_SERVER_END
for mode in ok odd silent null string range live live-no-credits \
  live-missing-primary live-missing-secondary live-missing-mapped minutes-missing used-only; do
  printf '#!/bin/sh\n[ "$1" = "app-server" ] || { echo "stand-in: unexpected arguments: $*" >&2; exit 9; }\nexec "%s" -B "%s" %s\n' \
    "$(command -v "$PY")" "$W/bin/codex-server.py" "$mode" > "$W/bin/codex-$mode"
done
chmod 755 "$W/bin/claude-ok" "$W/bin/claude-fail" "$W/bin/claude-odd" "$W/bin/claude-live" \
  "$W/bin/claude-unavailable" "$W/bin/claude-unavailable-download" \
  "$W/bin/claude-pending-unavailable" "$W/bin/claude-reset-unavailable" \
  "$W/bin/claude-reset-unavailable-inline" "$W/bin/claude-worded-unavailable" \
  "$W/bin/claude-reset-clause" "$W/bin/claude-borrow" \
  "$W/bin/claude-headings" "$W/bin/claude-partial" \
  "$W/bin/claude-signed" "$W/bin/claude-download" "$W/bin/claude-plus" "$W/bin/claude-minus" \
  "$W/bin/claude-before" "$W/bin/claude-glued" "$W/bin/claude-big" "$W/bin/claude-edges" \
  "$W/bin/codex-ok" "$W/bin/codex-odd" "$W/bin/codex-silent" "$W/bin/codex-null" "$W/bin/codex-string" \
  "$W/bin/codex-range" "$W/bin/codex-live" "$W/bin/codex-live-no-credits" \
  "$W/bin/codex-live-missing-primary" "$W/bin/codex-live-missing-secondary" \
  "$W/bin/codex-live-missing-mapped" "$W/bin/codex-minutes-missing" "$W/bin/codex-used-only"

run() { # env pairs then arguments; output to $W/out, exit code to RC
  RC=0
  env "$@" > "$W/out" 2> "$W/err" || RC=$?
}

# ------------------------------------------------------------------ the readings ----
run USAGE_CLAUDE_BIN="$W/bin/claude-ok" USAGE_CODEX_BIN="$W/bin/codex-ok" "$PY" -B "$R"
if [ "$RC" = 0 ] && [ "$(grep -c '' "$W/out")" = 2 ] \
   && grep -q '^claude-usage: Current session / 4% used · resets 4am (Europe/London) / Current week (all models) / 17% used · resets Oct 15$' "$W/out" \
   && grep -q '^astra-usage: 7 d window 19% used, resets ' "$W/out"; then
  ok "both windows read and printed, one line each, exit 0 (the ANSI codes stripped; the line with no figure dropped)"
else no "both windows  [exit $RC: $(tr '\n' '|' < "$W/out") $(tr '\n' '|' < "$W/err")]"; fi

run USAGE_CLAUDE_BIN="$W/bin/claude-fail" USAGE_CODEX_BIN="$W/bin/codex-ok" "$PY" -B "$R"
if [ "$RC" = 1 ] && grep -q '^claude-usage: could not read (exit 1; stand-in: not logged in)$' "$W/out" \
   && grep -q '^astra-usage: 7 d window 19% used' "$W/out"; then
  ok "a failed claude reading prints could not read with its exit and stderr, exit 1, the other window still read"
else no "the failed claude reading  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CLAUDE_BIN="$W/bin/claude-odd" "$PY" -B "$R" --only claude
if [ "$RC" = 1 ] && grep -q '^claude-usage: could not read (unrecognised output: Hello there / No figures today)$' "$W/out" \
   && [ "$(grep -c '' "$W/out")" = 1 ]; then
  ok "claude output with no window figure is unrecognised, never guessed (exit 1, one line under --only claude)"
else no "the unrecognised claude output  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CODEX_BIN="$W/bin/codex-odd" "$PY" -B "$R" --only astra
if [ "$RC" = 1 ] && grep -q '^astra-usage: could not read (unrecognised result shape: ' "$W/out"; then
  ok "an app-server result with no used-percent figure is unrecognised, never guessed (exit 1)"
else no "the unrecognised app-server result  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

# A reading must carry real window figures: each case below exits 0 from
# the program it stands in for, so only the reader's own check can refuse it.
run USAGE_CLAUDE_BIN="$W/bin/claude-live" USAGE_CODEX_BIN="$W/bin/codex-ok" "$PY" -B "$R"
if [ "$RC" = 0 ] && [ "$(grep -c '' "$W/out")" = 2 ] \
   && grep -q '^claude-usage: Current session: 34% used · resets Oct 5 at 8pm (Europe/London) / Current week (all models): 67% used · resets Oct 8 at 7am (Europe/London) / Current week (one model): 5% used · resets Oct 8 at 7am (Europe/London)$' "$W/out" \
   && grep -q '^astra-usage: 7 d window 19% used, resets ' "$W/out"; then
  ok "a reading in the live shape (each heading and its figure on one line, three windows) is read, exit 0"
else no "the live-shape reading  [exit $RC: $(tr '\n' '|' < "$W/out") $(tr '\n' '|' < "$W/err")]"; fi

run USAGE_CLAUDE_BIN="$W/bin/claude-unavailable" "$PY" -B "$R" --only claude
if [ "$RC" = 1 ] && [ "$(grep -c '' "$W/out")" = 1 ] \
   && grep -q '^claude-usage: could not read (a window with no figure: Usage limits unavailable for this session)$' "$W/out"; then
  ok "a notice that usage limits are unavailable is unread, never a reading (exit 1)"
else no "the unavailable notice  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

# Only a figure written `N% used` fills a window, so a later unrelated percentage never fills a
# window whose usage is unavailable, whatever the notice says (reviews CR2 and CR3 of
# run-20261108-auditfix2; the notice wordings below are CR3's and the staged build's, and the
# reader keeps no list of them).
run USAGE_CLAUDE_BIN="$W/bin/claude-unavailable-download" "$PY" -B "$R" --only claude
if [ "$RC" = 1 ] && [ "$(cat "$W/out")" = 'claude-usage: could not read (a window with no figure: Usage limits unavailable for this session)' ]; then
  ok "unavailable-download: an unavailable notice cannot borrow an unrelated later percentage (exit 1)"
else no "unavailable-download  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

for mode in pending-unavailable borrow; do
  run USAGE_CLAUDE_BIN="$W/bin/claude-$mode" "$PY" -B "$R" --only claude
  if [ "$RC" = 1 ] && [ "$(cat "$W/out")" = 'claude-usage: could not read (a window with no figure: Current session)' ]; then
    ok "$mode: a window heading cannot borrow a later 'Download 42% complete' (exit 1)"
  else no "$mode  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi
done

for notice in 'Usage is unavailable' 'Limits are unavailable' 'Usage: unavailable' \
  'Usage limits are currently unavailable' 'Usage is temporarily unavailable' 'Usage limit unavailable'; do
  run USAGE_CLAUDE_BIN="$W/bin/claude-worded-unavailable" USAGE_NOTICE="$notice" "$PY" -B "$R" --only claude
  if [ "$RC" = 1 ] && [ "$(cat "$W/out")" = 'claude-usage: could not read (a window with no figure: Current session)' ]; then
    ok "$notice: the pending window stays empty before a later percentage (exit 1)"
  else no "$notice  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi
done

run USAGE_CLAUDE_BIN="$W/bin/claude-reset-clause" "$PY" -B "$R" --only claude
if [ "$RC" = 0 ] && [ "$(cat "$W/out")" = 'claude-usage: Current session usage: 4% used; reset times for usage limits are unavailable' ]; then
  ok "a real 4% figure is read when its line says reset times for usage limits are unavailable (exit 0)"
else no "the reset-times clause  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CLAUDE_BIN="$W/bin/claude-reset-unavailable" "$PY" -B "$R" --only claude
if [ "$RC" = 0 ] && grep -q '^claude-usage: Current session: 4% used / Reset time unavailable$' "$W/out"; then
  ok "control: an unavailable reset time does not invalidate a real usage figure (exit 0)"
else no "the unavailable reset-time control  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CLAUDE_BIN="$W/bin/claude-reset-unavailable-inline" "$PY" -B "$R" --only claude
if [ "$RC" = 0 ] && [ "$(cat "$W/out")" = 'claude-usage: Current session usage: 4% used; reset time unavailable' ]; then
  ok "a real 4% usage figure is read when its reset time is unavailable on the same line (exit 0)"
else no "the same-line unavailable reset time  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CLAUDE_BIN="$W/bin/claude-headings" "$PY" -B "$R" --only claude
if [ "$RC" = 1 ] && grep -q '^claude-usage: could not read (a window with no figure: Current session)$' "$W/out"; then
  ok "window headings with no figures are unread (exit 1)"
else no "the headings with no figures  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CLAUDE_BIN="$W/bin/claude-partial" "$PY" -B "$R" --only claude
if [ "$RC" = 1 ] && grep -q '^claude-usage: could not read (a window with no figure: Current session)$' "$W/out"; then
  ok "a heading whose figure is missing is unread although a later window has one (exit 1)"
else no "the partial reading  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

# A per-cent token is read whole and a reading must name a usage window: each case below exits 0
# from the program it stands in for and carries a figure, so only the reader's check refuses it.
run USAGE_CLAUDE_BIN="$W/bin/claude-signed" "$PY" -B "$R" --only claude
if [ "$RC" = 1 ] && [ "$(grep -c '' "$W/out")" = 1 ] \
   && grep -q '^claude-usage: could not read (a figure with a sign (-1%): Current session: -1% used)$' "$W/out"; then
  ok "'Current session: -1% used' is unread, never read as 1% (exit 1)"
else no "the signed figure  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CLAUDE_BIN="$W/bin/claude-download" "$PY" -B "$R" --only claude
if [ "$RC" = 1 ] && [ "$(grep -c '' "$W/out")" = 1 ] \
   && grep -q '^claude-usage: could not read (a figure outside any usage window: Download 42% complete)$' "$W/out"; then
  ok "'Download 42% complete', which names no usage window, is unread (exit 1)"
else no "the progress line  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CLAUDE_BIN="$W/bin/claude-plus" "$PY" -B "$R" --only claude
if [ "$RC" = 1 ] && grep -q '^claude-usage: could not read (a figure with a sign (+4%): Current session: +4% used · resets 4am)$' "$W/out"; then
  ok "a figure with a plus sign is unread although every other window reads (exit 1)"
else no "the plus sign  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CLAUDE_BIN="$W/bin/claude-minus" "$PY" -B "$R" --only claude
if [ "$RC" = 1 ] && grep -q '^claude-usage: could not read (a figure with a sign (.*4%): Current session: .*4% used · resets 4am)$' "$W/out"; then
  ok "a figure with a Unicode minus sign (U+2212) is unread (exit 1)"
else no "the Unicode minus  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CLAUDE_BIN="$W/bin/claude-before" "$PY" -B "$R" --only claude
if [ "$RC" = 1 ] && grep -q '^claude-usage: could not read (a figure outside any usage window: Download 42% complete)$' "$W/out"; then
  ok "a progress figure before the first usage window is unread although the windows that follow read (exit 1)"
else no "the figure before any window  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CLAUDE_BIN="$W/bin/claude-glued" "$PY" -B "$R" --only claude
if [ "$RC" = 1 ] && grep -q '^claude-usage: could not read (a token that is no whole figure (x-7%): Current session: x-7% used · resets 4am)$' "$W/out"; then
  ok "a token glued to a letter and a dash (x-7%) is read whole and refused, never read as 7% (exit 1)"
else no "the glued token  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CLAUDE_BIN="$W/bin/claude-big" "$PY" -B "$R" --only claude
if [ "$RC" = 1 ] && grep -q '^claude-usage: could not read (a figure out of range (1000%): of which 1000% extra)$' "$W/out"; then
  ok "a whole token above 100 on a line after a valid window is refused, never passed over (exit 1)"
else no "the four-digit token  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CLAUDE_BIN="$W/bin/claude-edges" USAGE_CODEX_BIN="$W/bin/codex-ok" "$PY" -B "$R"
if [ "$RC" = 0 ] && [ "$(grep -c '' "$W/out")" = 2 ] \
   && grep -q "^claude-usage: Current session - 0% used · resets 4am / Current week (all models): 100% used · resets Oct 15 / Current week (one model): 4.5% used · resets Oct 15 / What's contributing to your limits usage? / Approximate, based on local sessions on this machine\$" "$W/out" \
   && grep -q '^astra-usage: 7 d window 19% used, resets ' "$W/out"; then
  ok "control: valid Claude figures at the edges (0, 100, 4.5; a spaced dash, no sign) with the live text's trailing notes, and a valid Astra window, are read (exit 0)"
else no "the edge readings  [exit $RC: $(tr '\n' '|' < "$W/out") $(tr '\n' '|' < "$W/err")]"; fi

run USAGE_CODEX_BIN="$W/bin/codex-null" "$PY" -B "$R" --only astra
if [ "$RC" = 1 ] && ! grep -q 'None' "$W/out" \
   && grep -q '^astra-usage: could not read (a window whose used percent is not a figure from 0 to 100: {"usedPercent": null' "$W/out"; then
  ok "an Astra window whose used percent is null is unread, never None% used (exit 1)"
else no "the null used percent  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CODEX_BIN="$W/bin/codex-string" "$PY" -B "$R" --only astra
if [ "$RC" = 1 ] && grep -q '^astra-usage: could not read (a window whose used percent is not a figure from 0 to 100: {"usedPercent": "19"' "$W/out"; then
  ok "an Astra used percent given as a string is unread (exit 1)"
else no "the string used percent  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CODEX_BIN="$W/bin/codex-range" "$PY" -B "$R" --only astra
if [ "$RC" = 1 ] && grep -q '^astra-usage: could not read (a window whose used percent is not a figure from 0 to 100: {"usedPercent": 150' "$W/out"; then
  ok "an Astra used percent above 100 is unread (exit 1)"
else no "the out-of-range used percent  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

# ------------------------------------------------------- duration-marked windows ----
run USAGE_CODEX_BIN="$W/bin/codex-live" "$PY" -B "$R" --only astra
LIVE_RC=$RC
LIVE_OUTPUT=$(cat "$W/out")
LIVE_WINDOW=${LIVE_OUTPUT#astra-usage: }
LIVE_WINDOW=${LIVE_WINDOW%% · *}
# Exactly two windows: primary under rateLimits and its copy under rateLimitsByLimitId.
if [ "$RC" = 0 ] && [ "$(grep -c '' "$W/out")" = 1 ] \
   && grep -q '^astra-usage: 7 d window 32% used, resets ' "$W/out" \
   && [ "$LIVE_OUTPUT" = "astra-usage: $LIVE_WINDOW · $LIVE_WINDOW" ]; then
  ok "control: the live result's two valid windows read 32% with null secondaries (exit 0)"
else no "the live app-server shape  [exit $RC: $LIVE_OUTPUT]"; fi

run USAGE_CODEX_BIN="$W/bin/codex-live-no-credits" "$PY" -B "$R" --only astra
if [ "$RC" = 0 ] && [ "$LIVE_RC" = 0 ] && [ "$(cat "$W/out")" = "$LIVE_OUTPUT" ]; then
  ok "reset-credit items with grantedAt and expiresAt add no windows (same reading with and without credits)"
else no "the reset-credit control  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

for mode in live-missing-primary live-missing-secondary live-missing-mapped; do
  case "$mode" in
    live-missing-secondary) MINS=$((5 * 60)) ;;
    *) MINS=$((7 * 24 * 60)) ;;
  esac
  run USAGE_CODEX_BIN="$W/bin/codex-$mode" "$PY" -B "$R" --only astra
  if [ "$RC" = 1 ] && [ "$(grep -c '' "$W/out")" = 1 ] \
     && grep -Fqx "astra-usage: could not read (a window whose used percent is not a figure from 0 to 100: {\"windowDurationMins\": $MINS, \"resetsAt\": 1794588090})" "$W/out"; then
    ok "$mode: a duration-marked window without usedPercent is named and refused despite valid neighbours (exit 1)"
  else no "$mode  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi
done

run USAGE_CODEX_BIN="$W/bin/codex-minutes-missing" "$PY" -B "$R" --only astra
if [ "$RC" = 1 ] && [ "$(grep -c '' "$W/out")" = 1 ] \
   && grep -Fqx 'astra-usage: could not read (a window whose used percent is not a figure from 0 to 100: {"windowMinutes": 300, "resetsAt": 1794588090})' "$W/out"; then
  ok "minutes-missing: a window whose length is windowMinutes and which has no usedPercent is named and refused (exit 1)"
else no "minutes-missing  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CODEX_BIN="$W/bin/codex-used-only" "$PY" -B "$R" --only astra
if [ "$RC" = 0 ] \
   && grep -Fqx 'astra-usage: length unstated window 0% used, reset unstated · length unstated window 100% used, reset unstated' "$W/out"; then
  ok "control: usedPercent and used_percent still identify windows without a duration (exit 0)"
else no "the used-percent-only windows  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

run USAGE_CLAUDE_BIN="$W/bin/no-such-claude" "$PY" -B "$R" --only claude
if [ "$RC" = 1 ] && grep -q '^claude-usage: could not read (.*no-such-claude is not executable)$' "$W/out"; then
  ok "a program that is not there prints could not read and names it (exit 1)"
else no "the missing program  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

T0=$("$PY" -c 'import time; print(int(time.time()))')
run USAGE_CODEX_BIN="$W/bin/codex-silent" "$PY" -B "$R" --only astra --timeout-s 2
T1=$("$PY" -c 'import time; print(int(time.time()))')
if [ "$RC" = 1 ] && grep -q '^astra-usage: could not read (timed out waiting for response 1' "$W/out" \
   && [ $((T1 - T0)) -le 12 ]; then
  ok "a silent app-server ends at the bound with could not read (exit 1, $((T1 - T0)) s against a 2 s bound plus the 5 s stop grace)"
else no "the silent app-server  [exit $RC after $((T1 - T0)) s: $(tr '\n' '|' < "$W/out")]"; fi

run "$PY" -B "$R" --timeout-s 0
if [ "$RC" = 2 ] && grep -q '^PROBE FAILED: --timeout-s must be positive$' "$W/out"; then
  ok "a bound of zero is a usage error (exit 2, PROBE FAILED), never a reading"
else no "the zero bound  [exit $RC: $(tr '\n' '|' < "$W/out")]"; fi

# ------------------------------------------------------------- the head-role fence ----
# The head fence imports lane-fence.py's checker in head mode; the shell form is the same check.
# Grants: the reader's own directory and /tmp (a head's default read grants hold the vault root, so
# a narrower grant is the stricter case). A cleared command is SILENCE (exit 0, no output); the
# control is the command the reader replaces, which the fence must deny on the same run.
if [ -f "$FENCE" ]; then
  fence() { # $1 command; prints the fence's stdout, exit code in FRC
    FRC=0
    "$PY" -B - "$1" > "$W/fence.json" <<'READ_USAGE_EVENT_END' || FRC=$?
import json, sys
print(json.dumps({"tool_name": "Bash", "tool_input": {"command": sys.argv[1]}}))
READ_USAGE_EVENT_END
    env LLM_WIKI_LANE_GRANTS="$HERE:/tmp:$W" LLM_WIKI_LANE_WRITES="$W" "$PY" -B "$FENCE" --head < "$W/fence.json" > "$W/fence.out" 2>&1 || FRC=$?
  }
  fence "python3 $R --only both"
  if [ "$FRC" = 0 ] && [ ! -s "$W/fence.out" ]; then
    ok "the head-role fence clears the reader's command (silence, exit 0)"
  else no "the head-role fence on the reader's command  [exit $FRC: $(cat "$W/fence.out")]"; fi
  fence "claude -p '/usage'"
  if [ "$FRC" = 0 ] && grep -q '"deny"' "$W/fence.out" && grep -q 'lane-fence:' "$W/fence.out"; then
    ok "control: the same fence denies claude -p '/usage', the form the reader replaces"
  else no "the fence control  [exit $FRC: $(cat "$W/fence.out")]"; fi
else
  no "the head-role fence legs: no lane-fence.py beside the suite ($HERE)"
fi

# ------------------------------------------------------------- wrote nothing ----
# A protected fixture in the same folder and under the same permissions is unchanged by the
# reader; then a one-byte change there must be caught by the same manifest comparison.
M1=$(manifest "$W/bin")
run USAGE_CODEX_BIN="$W/bin/codex-live" "$PY" -B "$R" --only astra
ASTRA_RC=$RC
ASTRA_OUTPUT=$(cat "$W/out")
run USAGE_CLAUDE_BIN="$W/bin/claude-ok" "$PY" -B "$R" --only claude
M2=$(manifest "$W/bin")
CONTROL_RC=0
"$PY" -B - "$W/bin/claude-ok" <<'READ_USAGE_BYTE_CONTROL_END' || CONTROL_RC=$?
import sys
with open(sys.argv[1], "r+b") as fh:
    fh.write(b"!")
READ_USAGE_BYTE_CONTROL_END
M3=$(manifest "$W/bin")
AFTER=$(manifest "$HERE")
if [ "$RC" = 0 ] && grep -q '^claude-usage: Current session / 4% used' "$W/out" \
   && [ "$ASTRA_RC" = 0 ] && [ "$ASTRA_OUTPUT" = "$LIVE_OUTPUT" ] \
   && [ "$CONTROL_RC" = 0 ] && [ "$M1" = "$M2" ] && [ "$M2" != "$M3" ] && [ "$BEFORE" = "$AFTER" ]; then
  ok "the script directory and stand-ins are unchanged (control: one byte in the same stand-in folder under unchanged permissions was caught)"
else no "the checksum-and-mode manifest or its one-byte control failed"; fi

SCAN=$("$PY" -B - "$R" <<'READ_USAGE_SCAN_END'
import re, sys
# The builtin open with a write, append or create mode (never Popen, which starts a process);
# the other write calls by name.
WRITE = re.compile(r"(?<![\w.])open\([^)]*,\s*(mode\s*=\s*)?['\"][^'\"]*[wax+]|\.write_(text|bytes)\(|"
                   r"os\.(open|remove|unlink|rename|replace|makedirs|mkdir|rmdir|chmod)\(|shutil\.(copy|move|rmtree)|tempfile\.")
src = open(sys.argv[1], encoding="utf-8").read().split("\n")
hits = [n + 1 for n, line in enumerate(src) if WRITE.search(line)]
planted = WRITE.search("    open(path, 'w').write(text)")
popen = WRITE.search('    proc = subprocess.Popen([binary, "app-server"], stdin=subprocess.PIPE)')
print("hits %s control %s popen %s" % (",".join(map(str, hits)) or "none", "hit" if planted else "missed",
                                       "hit" if popen else "quiet"))
READ_USAGE_SCAN_END
)
if [ "$SCAN" = "hits none control hit popen quiet" ]; then
  ok "the reader's source holds no file-write call (controls: a planted open(..., 'w') line hit; a Popen line stayed quiet)"
else no "the source scan  [$SCAN]"; fi

TOTAL=$((PASS + FAIL))
if [ "$FAIL" = 0 ]; then echo "PASS $PASS/$TOTAL"; exit 0; fi
echo "FAIL $FAIL/$TOTAL"; exit 1
