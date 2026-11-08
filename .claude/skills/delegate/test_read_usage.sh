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
# window, alone or before real windows (`Download 42% complete`), a token glued to a letter
# (`x-7%`), a whole token above 100 after a valid window, an Astra window whose used percent is
# null, a string or out of range) prints `could not read` and exits 1, while valid figures at the
# edges (0, 100, a decimal, a dash with a space before a figure) with the live text's trailing notes
# are read; a bad bound is a usage error (exit 2);
# the head-role fence clears the reader's own command and still denies the `claude -p '/usage'` form
# it replaces (the control); and the last legs prove the suite and the reader wrote nothing beside
# the script: a checksum-and-mode manifest of this directory before and after, with a planted
# same-length change as its control, and a scan of the reader's source for write calls whose own
# planted control must hit.
#
# Run:  sh test_read_usage.sh          (from anywhere; it finds read-usage.py beside itself)
# The last line is PASS n/n or FAIL k/n; a broken premise prints PROBE FAILED and exits 2.
set -u

HERE=$(cd "$(dirname "$0")" && pwd) || { echo 'PROBE FAILED: cannot locate the test directory'; echo 'FAIL 1/1'; exit 2; }
PY=${PYTHON:-python3}
R="$HERE/read-usage.py"
FENCE="$HERE/lane-fence.py"
command -v "$PY" >/dev/null || { echo "PROBE FAILED: no $PY on PATH"; echo 'FAIL 1/1'; exit 2; }
[ -f "$R" ] || { echo "PROBE FAILED: no read-usage.py beside the suite ($HERE)"; echo 'FAIL 1/1'; exit 2; }
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
import json, sys, time
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
        else:
            result = {"rateLimits": {"something": "else"}}
        print(json.dumps({"id": 2, "result": result}))
    sys.stdout.flush()
CODEX_SERVER_END
for mode in ok odd silent null string range; do
  printf '#!/bin/sh\n[ "$1" = "app-server" ] || { echo "stand-in: unexpected arguments: $*" >&2; exit 9; }\nexec "%s" -B "%s" %s\n' \
    "$(command -v "$PY")" "$W/bin/codex-server.py" "$mode" > "$W/bin/codex-$mode"
done
chmod 755 "$W/bin/claude-ok" "$W/bin/claude-fail" "$W/bin/claude-odd" "$W/bin/claude-live" \
  "$W/bin/claude-unavailable" "$W/bin/claude-headings" "$W/bin/claude-partial" \
  "$W/bin/claude-signed" "$W/bin/claude-download" "$W/bin/claude-plus" "$W/bin/claude-minus" \
  "$W/bin/claude-before" "$W/bin/claude-glued" "$W/bin/claude-big" "$W/bin/claude-edges" \
  "$W/bin/codex-ok" "$W/bin/codex-odd" "$W/bin/codex-silent" "$W/bin/codex-null" "$W/bin/codex-string" \
  "$W/bin/codex-range"

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
# A planted same-length change in a scratch copy must show in the manifest: the control that the
# comparison can see a change at all.
mkdir -p "$W/manifest-control"
printf 'before\n' > "$W/manifest-control/witness.txt"
M1=$(manifest "$W/manifest-control")
printf 'after!\n' > "$W/manifest-control/witness.txt"
M2=$(manifest "$W/manifest-control")
AFTER=$(manifest "$HERE")
if [ "$M1" != "$M2" ] && [ "$BEFORE" = "$AFTER" ]; then
  ok "the script directory's checksum-and-mode manifest is unchanged after every leg (control: a planted same-length change showed)"
else no "the manifest  [control differs: $([ "$M1" != "$M2" ] && echo yes || echo no); directory unchanged: $([ "$BEFORE" = "$AFTER" ] && echo yes || echo no)]"; fi

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
