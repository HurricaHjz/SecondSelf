#!/bin/bash
# test_codex_lane.sh — the shim suite for codex-lane.py: a fake `codex` that emits the documented
# JSONL events under a chosen mode, a throwaway run store, and one assertion block per case.
# Usage: sh .claude/skills/delegate/test_codex_lane.sh            (no live model call)
# Every case prints PASS or FAIL with its name; the script exits 1 on any FAIL.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
ADAPTER="$HERE/codex-lane.py"
# A partial staged checkout cannot establish a clean suite result.
MISSING=0
for dependency in lane.py routing.json templates/lane-core.md handsoff.py test_fix_c.py test_a3.py probe_fix_c.py fixtures-fix-c.json test_codex_effort.py; do
  if [ ! -s "$HERE/$dependency" ]; then
    printf 'PROBE FAILED: suite dependency missing: %s\n' "$HERE/$dependency"
    MISSING=$((MISSING+1))
  fi
done
if [ "$MISSING" -ne 0 ]; then printf 'FAIL 1/1\n'; exit 2; fi
# CR-A3-1 M2 (depth/spec): never place suite fixtures in the caller's run store.
T="$(mktemp -d "${AIMYTH_TEST_ROOT:-${TMPDIR:-/tmp}}/codex-lane-suite-XXXXXX")" || exit 2
export LLM_WIKI_STORE="$T/store"
export AIMYTH_VIEWER=none
export CODEX_SHIM_ARGS="$T/shim-args.txt"
export CODEX_SHIM_PROMPT="$T/shim-prompt.txt"
mkdir -p "$T/bin" "$T/work" "$T/extra" "$T/store/spawn-records"
TR="$(cd "$T" && pwd -P)"     # Resolve aliases before comparing the adapter's recorded paths.
# The suite's own home (register 2026-10-04 10:45): the adapter's lookups under the home directory —
# Codex's global instructions under CODEX_HOME or ~/.codex, lane.py's trust entry and projects root —
# land in this fixture, never the machine's real stores. REAL_HOME is kept for the trace leg's control.
REAL_HOME=$HOME
mkdir -p "$T/homes/fixture/.codex/sessions" "$T/homes/fixture/.claude/projects"
export HOME="$T/homes/fixture" CODEX_HOME="$T/homes/fixture/.codex"   # one level down: no fixture folder is a sibling of the home
FAILS=0; PASSES=0
export PYTHONDONTWRITEBYTECODE=1
cleanup(){ chmod -R u+w "$T"; rm -rf "$T"; }
trap cleanup EXIT INT TERM
# CR-A3-1b F4: Codex fixtures may use platform scratch but must be outside vault and cwd grants.
"$PY" - "$T" "${CLAUDE_PROJECT_DIR:-}" "$HERE" <<'FIXTURE_PREMISE_END' || exit 2
from pathlib import Path
import sys
root = Path(sys.argv[1]).resolve()
grants = [Path(value).resolve() for value in sys.argv[2:] if value]
if any(root == grant or grant in root.parents for grant in grants):
    print("PROBE FAILED: out-of-grant fixtures are inside a granted root; set AIMYTH_TEST_ROOT", file=sys.stderr)
    raise SystemExit(2)
FIXTURE_PREMISE_END
SOURCE_BEFORE=$(shasum "$ADAPTER" "$HERE/lane.py" "$0")

cat > "$T/bin/codex" <<'SHIM'
#!/bin/bash
# a fake codex: `--version`, then the JSONL events of the mode in CODEX_SHIM_MODE
if [ "${1:-}" = "--version" ]; then echo "codex-cli 0.0.0-shim"; exit 0; fi
out=""; prev=""; cwd=""
for a in "$@"; do
  if [ "$prev" = "-o" ]; then out="$a"; fi
  if [ "$prev" = "-C" ]; then cwd="$a"; fi
  prev="$a"
done
printf '%s\n' "$*" > "$CODEX_SHIM_ARGS"
if [ -n "${CODEX_SHIM_MARKER:-}" ]; then
  if [ -f "$CODEX_SHIM_MARKER" ]; then cat "$CODEX_SHIM_MARKER" > "$CODEX_SHIM_MARKER_OUT"
  else printf 'absent\n' > "$CODEX_SHIM_MARKER_OUT"; fi
fi
if [ -n "${CODEX_SHIM_ORDER:-}" ]; then printf 'LANE pid=%s\n' "$$" >> "$CODEX_SHIM_ORDER"; fi
cat > "$CODEX_SHIM_PROMPT"
mode="${CODEX_SHIM_MODE:-ok}"
tid="${CODEX_SHIM_THREAD:-01a0-shim-thread}"
ok_tail() {
  printf '%s\n' '{"type":"turn.started"}'
  printf '%s\n' '{"type":"item.completed","item":{"type":"agent_message","text":"REPORT-OK-'"$tid"'"}}'
  printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":40,"cache_write_input_tokens":0,"output_tokens":7,"reasoning_output_tokens":3}}'
  if [ -n "$out" ]; then printf 'REPORT-OK-%s\n' "$tid" > "$out"; fi
}
case "$mode" in
  ok)        printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'; ok_tail; exit 0;;
  failed)    printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'; printf '%s\n' '{"type":"turn.started"}'
             printf '%s\n' '{"type":"turn.failed","error":{"message":"safety monitor ended the task"}}'; exit 1;;
  limit)     printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'
             printf '%s\n' '{"type":"error","message":"usage limit reached for this plan"}'; exit 1;;
  malformed) printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'; printf '%s\n' 'this is not json {'; ok_tail; exit 0;;
  empty)     exit 0;;
  blank|blankfile) printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'; printf '%s\n' '{"type":"turn.started"}'
             printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":50,"cached_input_tokens":0,"cache_write_input_tokens":0,"output_tokens":0,"reasoning_output_tokens":0}}'
             if [ "$mode" = blankfile ]; then printf 'OTHER LANE REPORT\n' > "$out"; fi; exit 0;;
  exit1)     printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'; exit 1;;
  slow)      printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'; sleep "${CODEX_SHIM_SLEEP:-8}"; ok_tail; exit 0;;
  denied)    printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'
             printf '%s\n' '{"type":"item.completed","item":{"type":"command_execution","command":"touch /etc/x","aggregated_output":"touch: /etc/x: Operation not permitted","exit_code":1}}'
             ok_tail; exit 0;;
  twoturns)  printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'
             printf '%s\n' '{"type":"turn.started"}'
             printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":40,"cache_write_input_tokens":0,"output_tokens":7,"reasoning_output_tokens":3}}'
             printf '%s\n' '{"type":"item.completed","item":{"type":"agent_message","text":"REPORT-OK-'"$tid"'"}}'
             printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":150,"cached_input_tokens":120,"cache_write_input_tokens":0,"output_tokens":2,"reasoning_output_tokens":1}}'
             if [ -n "$out" ]; then printf 'REPORT-OK-%s\n' "$tid" > "$out"; fi; exit 0;;
  nousage|badusage|zero)   # F7: a completed turn without a usage object, with a malformed one, with a measured zero
             printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}' '{"type":"turn.started"}'
             printf '%s\n' '{"type":"item.completed","item":{"type":"agent_message","text":"REPORT-OK-'"$tid"'"}}'
             case "$mode" in
               nousage)  printf '%s\n' '{"type":"turn.completed"}' ;;
               badusage) printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":"lots","cached_input_tokens":0,"output_tokens":7}}' ;;
               zero)     printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":0,"cached_input_tokens":0,"cache_write_input_tokens":0,"output_tokens":0,"reasoning_output_tokens":0}}' ;;
             esac
             if [ -n "$out" ]; then printf 'REPORT-OK-%s\n' "$tid" > "$out"; fi; exit 0;;
  thenfail)  printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'; ok_tail   # F7: a completed turn, then a failed one
             printf '%s\n' '{"type":"turn.started"}' '{"type":"turn.failed","error":{"message":"a later turn failed"}}'; exit 1;;
  thenstop)  printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'; ok_tail   # F7: a completed turn, then a turn the wrapper stops
             printf '%s\n' '{"type":"turn.started"}'; sleep "${CODEX_SHIM_SLEEP:-30}"; exit 0;;
  thenerror) printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'; ok_tail   # F7 finding 5: then a turn a provider error ends, no turn.failed
             printf '%s\n' '{"type":"turn.started"}' '{"type":"error","message":"stream error: the provider closed the connection"}'; exit 1;;
  thensignal) printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'; ok_tail  # F7 finding 5: then a turn cut by a signal from outside the wrapper
             printf '%s\n' '{"type":"turn.started"}'; kill -TERM $$; sleep 5; exit 0;;
  thenexit)  printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'; ok_tail; exit 1;;   # F7 finding 5: then a failure with no turn seen in flight
  negusage|overflow|oddvalues)   # F7 finding 1: a completed turn, then one whose usage carries a negative, an overflowing or a non-integer count
             printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'; ok_tail; printf '%s\n' '{"type":"turn.started"}'
             case "$mode" in
               negusage)  printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":-200,"cached_input_tokens":0,"output_tokens":2}}' ;;
               overflow)  printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":1e309,"cached_input_tokens":0,"output_tokens":2}}' ;;
               oddvalues) printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":true,"cached_input_tokens":7.5,"output_tokens":"9"}}' ;;
             esac; exit 0;;
  emptyusage|zerothennone)   # F7 finding 4: an empty usage object (no measurement); a measured zero beside a turn without usage
             printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}' '{"type":"turn.started"}'
             printf '%s\n' '{"type":"item.completed","item":{"type":"agent_message","text":"REPORT-OK-'"$tid"'"}}'
             if [ "$mode" = emptyusage ]; then printf '%s\n' '{"type":"turn.completed","usage":{}}'
             else printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":0,"cached_input_tokens":0,"output_tokens":0}}' '{"type":"turn.completed"}'; fi
             if [ -n "$out" ]; then printf 'REPORT-OK-%s\n' "$tid" > "$out"; fi; exit 0;;
  badtype)   # lines that must never cost the close: a type that is not a string, and a nesting too deep to decode
             printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}' '{"type":5}' '{"type":["item.completed"]}'
             printf '%100000s' '' | tr ' ' '['; printf '%100000s' '' | tr ' ' ']'; printf '\n'
             ok_tail; exit 0;;
  badbytes)  # a byte that is not UTF-8, then the turn's usage: the reading must go on past it
             printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}' '{"type":"turn.started"}'
             printf '{"type":"item.completed","item":{"type":"agent_message","text":"a byte that is not UTF-8: \377"}}\n'
             printf '%s\n' '{"type":"item.completed","item":{"type":"agent_message","text":"REPORT-OK-'"$tid"'"}}'
             printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":40,"cache_write_input_tokens":0,"output_tokens":7,"reasoning_output_tokens":3}}'
             if [ -n "$out" ]; then printf 'REPORT-OK-%s\n' "$tid" > "$out"; fi; exit 0;;
  beatneg|beatstr)   # CR-ADD3 finding 1, a beat's malformed streams: 100/90 then a negative input; numeric strings
             printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}' '{"type":"turn.started"}'
             printf '%s\n' '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}'
             if [ "$mode" = beatneg ]; then
               printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":90,"output_tokens":1}}' '{"type":"turn.started"}'
               printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":-200,"cached_input_tokens":0,"output_tokens":1}}'
             else printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":"100","cached_input_tokens":"90","output_tokens":"1"}}'; fi
             exit 0;;
  reconnect401|reconnect401text|blankfail|reconnectok)   # the decisive error (register 2026-09-26 00:16): retries first, the cause last
             printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'
             [ "$mode" = reconnectok ] || printf '%s\n' '{"type":"turn.started"}'
             if [ "$mode" = reconnect401text ]; then printf '%s\n' '{"type":"item.completed","item":{"type":"agent_message","text":"PARTIAL-WORK-'"$tid"'"}}'; fi
             for i in 1 2 3 4 5 6; do printf '{"type":"error","message":"Reconnecting... %d/5 (stream disconnected before completion: websocket closed by server before response.completed)"}\n' "$i"; done
             case "$mode" in
               reconnect401|reconnect401text) printf '%s\n' '{"type":"turn.failed","error":{"message":"unexpected status 401 Unauthorized: Incorrect API key provided"}}'; exit 1;;
               blankfail) printf '%s\n' '{"type":"error","message":"unexpected status 401 Unauthorized: Incorrect API key provided"}' '{"type":"turn.failed","error":{}}'; exit 1;;
               reconnectok) ok_tail; exit 0;;
             esac;;
  catfile)   seen=$(tr '\n' ' ' < "$cwd/${CODEX_SHIM_CAT:-no-such-file}")
             printf '%s\n' '{"type":"thread.started","thread_id":"'"$tid"'"}'
             printf '{"type":"item.completed","item":{"type":"agent_message","text":"SEEN %s"}}\n' "$seen"
             printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":10,"cached_input_tokens":0,"cache_write_input_tokens":0,"output_tokens":2,"reasoning_output_tokens":0}}'
             if [ -n "$out" ]; then printf 'SEEN %s\n' "$seen" > "$out"; fi; exit 0;;
  *)         echo "shim: unknown mode $mode" >&2; exit 9;;
esac
SHIM
chmod +x "$T/bin/codex"

printf 'Reply with the single word OK.\nCONTROL+: LANE CORE in %s\n' "$HERE/templates/lane-core.md" > "$T/brief.md"
printf 'Follow-up: repeat the word.\n' > "$T/follow.md"
printf 'A brief whose control cannot hit.\nCONTROL+: zzz-no-such-phrase-zzz in %s\n' "$HERE/templates/lane-core.md" > "$T/badcontrol.md"

# Existing command and beat assertions use max; omitted effort has its own regression below.
COMMON=(--codex "$T/bin/codex" --class critic --brief "$T/brief.md" --cwd "$T/work" --reason "(a) suite" --choice-reason "suite pick" --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60 --report-words 50 --effort max)

pass() { PASSES=$((PASSES+1)); echo "PASS $1"; }
fail() { echo "FAIL $1: $2"; FAILS=$((FAILS+1)); }

mkdir "$T/effort-regression"
if "$PY" -B "$HERE/test_codex_effort.py" --fixture-root "$T/effort-regression"; then
  pass "routing effort regression"
else
  fail "routing effort regression" "see result lines above"
fi

# record reader: prints the requested field of the last event of a kind for a lane
field() { # record lane event field
  "$PY" - "$1" "$2" "$3" "$4" <<'PYEOF'
import json, sys
path, lane, kind, key = sys.argv[1:5]
value = None
for line in open(path, encoding="utf-8"):
    line = line.strip()
    if not line: continue
    e = json.loads(line)
    if e.get("lane") == lane and e.get("event") == kind:
        v = e
        for part in key.split("."):
            v = v.get(part) if isinstance(v, dict) else None
        value = v
print(json.dumps(value))
PYEOF
}
count() { # record lane event
  "$PY" - "$1" "$2" "$3" <<'PYEOF'
import json, sys
path, lane, kind = sys.argv[1:4]
n = 0
for line in open(path, encoding="utf-8"):
    line = line.strip()
    if line and json.loads(line).get("lane") == lane and json.loads(line).get("event") == kind: n += 1
print(n)
PYEOF
}
REC="$T/store/spawn-records/run-suite.jsonl"

# 1 dry run, read-only
out="$("$PY" "$ADAPTER" spawn --run run-suite --lane D1 "${COMMON[@]}" --dry-run 2>&1)"; rc=$?
if [ $rc -eq 0 ] && printf '%s' "$out" | grep -q -- "-a never exec --ignore-user-config" && printf '%s' "$out" | grep -q -- "-s read-only" \
   && printf '%s' "$out" | grep -q -- "model_reasoning_effort=\\\\\"max\\\\\"\|model_reasoning_effort=\"max\"" && printf '%s' "$out" | grep -q -- "--skip-git-repo-check" \
   && printf '%s' "$out" | grep -q -- "--json -o" && ! printf '%s' "$out" | grep -q -- "--add-dir" && [ ! -f "$REC" ]; then pass "dry-run read-only"; else fail "dry-run read-only" "rc=$rc $out"; fi

# 2 dry run with writes: workspace-write, the extra directory as --add-dir, not the cwd
out="$("$PY" "$ADAPTER" spawn --run run-suite --lane D2 "${COMMON[@]}" --write "$T/work" --write "$T/extra" --dry-run 2>&1)"; rc=$?
if [ $rc -eq 0 ] && printf '%s' "$out" | grep -q -- "-s workspace-write" && printf '%s' "$out" | grep -q -- "--add-dir $TR/extra" \
   && ! printf '%s' "$out" | grep -q -- "--add-dir $TR/work"; then pass "dry-run workspace-write"; else fail "dry-run workspace-write" "$out"; fi

# 3 refusals, each exit 2 and no record
for case in "cwd-outside-writes:--write $T/extra" "no-reason-letter:--reason nothing" "no-choice-reason:--choice-reason  " "unknown-effort:--effort turbo" "unknown-model:--model gpt-9" "bad-control:--brief $T/badcontrol.md"; do
  name="${case%%:*}"; extra="${case#*:}"
  # shellcheck disable=SC2086
  "$PY" "$ADAPTER" spawn --run run-suite --lane R1 "${COMMON[@]}" $extra --dry-run >/dev/null 2>"$T/err.txt"; rc=$?
  if [ $rc -eq 2 ] && [ ! -f "$REC" ]; then pass "refusal $name"; else fail "refusal $name" "rc=$rc $(cat "$T/err.txt")"; fi
done

# 4 ok: the record, the report, the prompt, the argv
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-ok "$PY" "$ADAPTER" spawn --run run-suite --lane L1 "${COMMON[@]}" >"$T/out1.txt" 2>&1; rc=$?
if [ $rc -eq 0 ] && [ "$(field "$REC" L1 lane-open harness)" = '"codex"' ] && [ "$(field "$REC" L1 lane-open sandbox)" = '"read-only"' ] \
   && [ "$(field "$REC" L1 lane-spawned pid)" != "null" ] && [ "$(field "$REC" L1 lane-session session_id)" = '"thread-ok"' ] \
   && [ "$(field "$REC" L1 lane-closed exit_class)" = '"completed"' ] && [ "$(field "$REC" L1 lane-closed usage.input_tokens)" = "100" ] \
   && [ "$(field "$REC" L1 lane-closed usage.output_tokens)" = "7" ] && [ "$(field "$REC" L1 lane-closed total_cost_usd)" = "null" ] \
   && [ "$(field "$REC" L1 lane-closed cost_src)" = '"codex-plan"' ] && [ "$(field "$REC" L1 lane-closed session_id)" = '"thread-ok"' ] \
   && grep -q "REPORT-OK-thread-ok" "$T/store/spawn-records/run-suite-report-L1.md" \
   && grep -q "ROLE DEFINITION" "$CODEX_SHIM_PROMPT" && grep -q "LANE CORE" "$CODEX_SHIM_PROMPT" && grep -q "CODEX LANE ADDENDUM" "$CODEX_SHIM_PROMPT" \
   && grep -q "Reply with the single word OK" "$CODEX_SHIM_PROMPT" && grep -q -- "-o $TR/store/spawn-records/run-suite-report-L1.md" "$CODEX_SHIM_ARGS" \
   && [ -f "$T/store/spawn-records/run-suite-events-L1.log" ] && [ "$(count "$REC" L1 lane-closed)" = "1" ] \
   && [ "$(ls "$T/store/spawn-records/" | grep -c 'events.*\.jsonl$')" = "0" ]; then pass "ok run"; else fail "ok run" "rc=$rc $(cat "$T/out1.txt")"; fi

# 5 failed → exit 3, the error kept
CODEX_SHIM_MODE=failed "$PY" "$ADAPTER" spawn --run run-suite --lane L2 "${COMMON[@]}" >/dev/null 2>&1; rc=$?
if [ $rc -eq 3 ] && [ "$(field "$REC" L2 lane-closed exit_class)" = '"failed"' ] && field "$REC" L2 lane-closed error | grep -q "safety monitor"; then pass "failed run"; else fail "failed run" "rc=$rc $(field "$REC" L2 lane-closed exit_class)"; fi

# 6 limit → exit 6
CODEX_SHIM_MODE=limit "$PY" "$ADAPTER" spawn --run run-suite --lane L3 "${COMMON[@]}" >/dev/null 2>&1; rc=$?
if [ $rc -eq 6 ] && [ "$(field "$REC" L3 lane-closed exit_class)" = '"limit"' ]; then pass "limit run"; else fail "limit run" "rc=$rc"; fi

# E2/E5 migration: malformed evidence is retained and disclosed, never certified clean.
CODEX_SHIM_MODE=malformed "$PY" "$ADAPTER" spawn --run run-suite --lane L4 "${COMMON[@]}" >/dev/null 2>&1; rc=$?
if [ $rc -eq 3 ] && [ "$(field "$REC" L4 lane-closed exit_class)" = '"evidence-incomplete"' ] && [ "$(field "$REC" L4 lane-closed events_unparseable)" = "1" ]; then pass "E5 malformed line closes uncertain with its count"; else fail "malformed line" "rc=$rc"; fi

# 8 empty output → failed
CODEX_SHIM_MODE=empty "$PY" "$ADAPTER" spawn --run run-suite --lane L5 "${COMMON[@]}" >/dev/null 2>&1; rc=$?
if [ $rc -eq 3 ] && [ "$(field "$REC" L5 lane-closed exit_class)" = '"failed"' ] && field "$REC" L5 lane-closed error | grep -q "no turn.completed"; then pass "empty output"; else fail "empty output" "rc=$rc"; fi

# 8b a completed turn with no report text → class empty (the round's "returns nothing" case)
CODEX_SHIM_MODE=blank "$PY" "$ADAPTER" spawn --run run-suite --lane L5b "${COMMON[@]}" >/dev/null 2>&1; rc=$?
if [ $rc -eq 3 ] && [ "$(field "$REC" L5b lane-closed exit_class)" = '"empty"' ] && [ "$(field "$REC" L5b lane-closed usage.input_tokens)" = "50" ]; then pass "empty class"; else fail "empty class" "rc=$rc $(field "$REC" L5b lane-closed exit_class)"; fi

# 8c a staged blind copy: the excluded name is absent, the rest present, the cwd is the copy
mkdir -p "$T/proj/keep" "$T/proj/review-fixture" "$T/proj/.git"; echo k > "$T/proj/keep/a.md"; echo secret > "$T/proj/review-fixture/R1.md"; echo g > "$T/proj/.git/HEAD"
out="$("$PY" "$ADAPTER" spawn --run run-suite --lane S1 --codex "$T/bin/codex" --class critic --brief "$T/brief.md" --stage-from "$T/proj" --stage-exclude review-fixture --reason "(a) suite" --choice-reason "suite pick" --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60 --dry-run 2>&1)"; rc=$?
STAGE="$TR/store/spawn-records/run-suite-cwd-S1"
if [ $rc -eq 0 ] && printf '%s' "$out" | grep -q -- "-C $STAGE " && printf '%s' "$out" | grep -q '"stage_files": 1' && printf '%s' "$out" | grep -q -- "features.multi_agent=false" && printf '%s' "$out" | grep -q -- "features.apps=false"; then pass "staged copy (dry run)"; else fail "staged copy (dry run)" "rc=$rc $out"; fi
CODEX_SHIM_MODE=ok "$PY" "$ADAPTER" spawn --run run-suite --lane S2 --codex "$T/bin/codex" --class critic --brief "$T/brief.md" --stage-from "$T/proj" --stage-exclude review-fixture --reason "(a) suite" --choice-reason "suite pick" --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60 >/dev/null 2>&1; rc=$?
STAGE2="$TR/store/spawn-records/run-suite-cwd-S2"
if [ $rc -eq 0 ] && [ -f "$STAGE2/keep/a.md" ] && [ ! -e "$STAGE2/review-fixture" ] && [ ! -e "$STAGE2/.git" ] && [ "$(field "$REC" S2 lane-open cwd)" = "\"$STAGE2\"" ] && grep -q "Your working directory is $STAGE2" "$CODEX_SHIM_PROMPT"; then pass "staged copy (live shim)"; else fail "staged copy (live shim)" "rc=$rc cwd=$(field "$REC" S2 lane-open cwd)"; fi

# 9 non-zero exit with no turn → failed
CODEX_SHIM_MODE=exit1 "$PY" "$ADAPTER" spawn --run run-suite --lane L6 "${COMMON[@]}" >/dev/null 2>&1; rc=$?
if [ $rc -eq 3 ] && [ "$(field "$REC" L6 lane-closed exit_class)" = '"failed"' ]; then pass "exit 1"; else fail "exit 1" "rc=$rc"; fi

# 10 stall: silence 2 s against an 8 s sleep → exit 5 with a stall event
CODEX_SHIM_MODE=slow CODEX_SHIM_SLEEP=8 "$PY" "$ADAPTER" spawn --run run-suite --lane L7 --codex "$T/bin/codex" --class critic --brief "$T/brief.md" --cwd "$T/work" --reason "(a) suite" --choice-reason "suite pick" --delegation single --delegation-src head --viewer none --silence-s 2 --deadline-s 60 >/dev/null 2>&1; rc=$?
if [ $rc -eq 5 ] && [ "$(field "$REC" L7 lane-closed exit_class)" = '"stall"' ] && [ "$(count "$REC" L7 stall)" = "1" ]; then pass "stall"; else fail "stall" "rc=$rc $(field "$REC" L7 lane-closed exit_class)"; fi

# 11 deadline: 2 s against an 8 s sleep, silence off → exit 3, class deadline
CODEX_SHIM_MODE=slow CODEX_SHIM_SLEEP=8 "$PY" "$ADAPTER" spawn --run run-suite --lane L8 --codex "$T/bin/codex" --class critic --brief "$T/brief.md" --cwd "$T/work" --reason "(a) suite" --choice-reason "suite pick" --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 2 >/dev/null 2>&1; rc=$?
if [ $rc -eq 3 ] && [ "$(field "$REC" L8 lane-closed exit_class)" = '"deadline"' ]; then pass "deadline"; else fail "deadline" "rc=$rc $(field "$REC" L8 lane-closed exit_class)"; fi

# 12 a denied command is counted, the run still completes
CODEX_SHIM_MODE=denied "$PY" "$ADAPTER" spawn --run run-suite --lane L9 "${COMMON[@]}" >/dev/null 2>&1; rc=$?
if [ $rc -eq 0 ] && [ "$(field "$REC" L9 lane-closed sandbox_denials)" = "1" ] && [ "$(field "$REC" L9 lane-closed items.command_execution)" = "1" ]; then pass "denial counted"; else fail "denial counted" "rc=$rc"; fi

# 13 resume: the recorded thread id goes to `resume <id> -`; lane-resumed and a second close
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-ok "$PY" "$ADAPTER" resume --run run-suite --lane L1 --brief "$T/follow.md" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60 >"$T/out2.txt" 2>&1; rc=$?
if [ $rc -eq 0 ] && grep -q -- "resume thread-ok -" "$CODEX_SHIM_ARGS" && [ "$(count "$REC" L1 lane-resumed)" = "1" ] && [ "$(count "$REC" L1 lane-closed)" = "2" ] \
   && [ "$(field "$REC" L1 lane-closed resumed_from)" = '"thread-ok"' ] && grep -q "Follow-up" "$CODEX_SHIM_PROMPT"; then pass "resume"; else fail "resume" "rc=$rc $(cat "$T/out2.txt")"; fi

# 13b the held-lane beat (2026-09-17): resume --beat on the resumed L1 thread. The
# shim's argv, its prompt file, the record and the store listing carry every claim; each clean
# leg has its must-fire twin.
NRES=$(count "$REC" L1 lane-resumed); NCLOSE=$(count "$REC" L1 lane-closed)
NFILES=$(ls "$T/store/spawn-records" | grep -c 'run-suite-report-L1\|run-suite-prompt-L1')
NEVENTS=$(grep -c '"type":"thread.started"' "$T/store/spawn-records/run-suite-events-L1.log")
rm -f "$CODEX_SHIM_ARGS" "$CODEX_SHIM_PROMPT"
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-ok AIMYTH_BEAT_BY=supervisor "$PY" "$ADAPTER" resume --run run-suite --lane L1 --beat --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >"$T/beat1.txt" 2>&1; rc=$?
if [ $rc -eq 0 ] && grep -q -- "resume thread-ok -" "$CODEX_SHIM_ARGS" && ! grep -q -- " -o " "$CODEX_SHIM_ARGS" \
   && [ "$(cat "$CODEX_SHIM_PROMPT")" = "beat: reply with the single word ok" ] \
   && [ "$(count "$REC" L1 hold-beat)" = 1 ] && [ "$(field "$REC" L1 hold-beat ok)" = true ] \
   && [ "$(field "$REC" L1 hold-beat harness)" = '"codex"' ] && [ "$(field "$REC" L1 hold-beat by)" = '"supervisor"' ] \
   && [ "$(field "$REC" L1 hold-beat usage.cached_input_tokens)" = 40 ] && [ "$(field "$REC" L1 hold-beat usage.input_tokens)" = 100 ] \
   && [ "$(field "$REC" L1 hold-beat usage.cache_read_share)" = 0.4 ] && [ "$(field "$REC" L1 hold-beat config_match)" = true ] \
   && [ "$(field "$REC" L1 hold-beat total_cost_usd)" = null ] && [ "$(field "$REC" L1 hold-beat cost_src)" = '"codex-plan"' ] \
   && [ "$(count "$REC" L1 lane-resumed)" = "$NRES" ] && [ "$(count "$REC" L1 lane-closed)" = "$NCLOSE" ] \
   && [ "$(ls "$T/store/spawn-records" | grep -c 'run-suite-report-L1\|run-suite-prompt-L1')" = "$NFILES" ] \
   && [ "$(grep -c '"type":"thread.started"' "$T/store/spawn-records/run-suite-events-L1.log")" = "$((NEVENTS + 1))" ] \
   && grep -q -- "-m gpt-6-astra" "$CODEX_SHIM_ARGS" && grep -q -- 'model_reasoning_effort="max"' "$CODEX_SHIM_ARGS" \
   && grep -q '^beat run-suite/L1: codex gpt-6-astra·max · ok ·' "$T/beat1.txt"; then pass "beat: resume --beat resumes the recorded thread under the lane-open's model and effort with the fixed line on stdin and no -o, writes no lane-resumed, lane-closed, report or pass file, appends its events to the lane's events log, and records hold-beat ok with the turn's usage, unpriced"; else fail "beat" "rc=$rc $(cat "$T/beat1.txt") args=$(cat "$CODEX_SHIM_ARGS" 2>/dev/null)"; fi
OPEN_SHA=$(field "$REC" L1 lane-open config_sha256); RES_SHA=$(field "$REC" L1 lane-resumed config_sha256); BEAT_SHA=$(field "$REC" L1 hold-beat config_sha256)
if [ "$OPEN_SHA" != null ] && [ -n "$OPEN_SHA" ] && [ "$OPEN_SHA" = "$RES_SHA" ] && [ "$OPEN_SHA" = "$BEAT_SHA" ]; then pass "beat: config_sha256 is one and the same on lane-open, lane-resumed and hold-beat (the spawn's, the resume's and the beat's resolved command lines agree outside -o, the resume pair and the prompt marker)"; else fail "beat config hash" "open $OPEN_SHA resumed $RES_SHA beat $BEAT_SHA"; fi
"$PY" - "$REC" "$T/rec-sha.jsonl" <<'PYEOF'
import json, sys
out = []
for line in open(sys.argv[1], encoding="utf-8"):
    if not line.strip():
        continue
    e = json.loads(line)
    if e.get("event") == "lane-open" and e.get("lane") == "L1":
        e["config_sha256"] = "0" * 64
    out.append(e)
open(sys.argv[2], "w", encoding="utf-8").write("".join(json.dumps(e) + "\n" for e in out))
PYEOF
rm -f "$CODEX_SHIM_ARGS"
CODEX_SHIM_MODE=ok "$PY" "$ADAPTER" resume --run run-suite --lane L1 --beat --record "$T/rec-sha.jsonl" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >/dev/null 2>"$T/beat-sha.err"; rc=$?
if [ $rc -eq 2 ] && grep -q 'differs from the lane-open' "$T/beat-sha.err" && [ ! -f "$CODEX_SHIM_ARGS" ] && [ "$(count "$T/rec-sha.jsonl" L1 hold-beat)" = 1 ]; then pass "beat (must fire): a lane-open whose config_sha256 differs from the resolved command line is refused (exit 2) before codex runs, and nothing is written"; else fail "beat config mismatch" "rc=$rc $(cat "$T/beat-sha.err")"; fi
CODEX_SHIM_MODE=ok "$PY" "$ADAPTER" resume --run run-suite --lane L1 --beat --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none --dry-run >"$T/beat-dry.txt" 2>&1; rc=$?
if [ $rc -eq 0 ] && grep -q 'no report, no pass file' "$T/beat-dry.txt" && grep -q 'resume thread-ok -' "$T/beat-dry.txt" && [ "$(count "$REC" L1 hold-beat)" = 1 ] && [ ! -f "$CODEX_SHIM_ARGS" ]; then pass "beat: --dry-run prints the command and the fixed prompt and writes nothing"; else fail "beat dry run" "rc=$rc $(cat "$T/beat-dry.txt")"; fi
# the premises, each exit 2 and nothing written: no recorded thread, a brief beside --beat, a
# running lane, a limit close, a lapsed window, a stage refresh, a worker
printf '%s\n' '{"ts":"2026-09-13T01:00:00+0100","run":"run-nb","lane":"NB","event":"lane-open","harness":"codex","model":"gpt-6-astra","effort":"max","class":"critic","cwd":"'"$T/work"'","reason":"(a) suite","choice_reason":"suite"}' > "$T/rec-nb.jsonl"
"$PY" "$ADAPTER" resume --run run-nb --lane NB --beat --record "$T/rec-nb.jsonl" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >/dev/null 2>"$T/b1.err"; rc1=$?
"$PY" "$ADAPTER" resume --run run-suite --lane L1 --beat --brief "$T/follow.md" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >/dev/null 2>"$T/b2.err"; rc2=$?
printf '%s\n' '{"ts":"2026-09-13T01:00:00+0100","run":"run-rb","lane":"RB","event":"lane-open","harness":"codex","model":"gpt-6-astra","effort":"max","class":"critic","cwd":"'"$T/work"'","reason":"(a) suite","choice_reason":"suite"}' \
  '{"ts":"2026-09-13T01:00:01+0100","run":"run-rb","lane":"RB","event":"lane-session","harness":"codex","session_id":"thread-rb","pid":1}' > "$T/rec-rb.jsonl"
"$PY" "$ADAPTER" resume --run run-rb --lane RB --beat --record "$T/rec-rb.jsonl" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >/dev/null 2>"$T/b3.err"; rc3=$?
"$PY" "$ADAPTER" resume --run run-suite --lane L3 --beat --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >/dev/null 2>"$T/b4.err"; rc4=$?
"$PY" - "$REC" "$T/rec-old.jsonl" <<'PYEOF'
import json, sys, time
old = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() - 7200))
out = []
for line in open(sys.argv[1], encoding="utf-8"):
    if not line.strip():
        continue
    e = json.loads(line)
    if e.get("lane") != "L1":
        continue
    if e.get("event") == "hold-beat":
        continue
    if e.get("event") == "lane-closed":
        e["ts"] = old
    out.append(e)
open(sys.argv[2], "w", encoding="utf-8").write("".join(json.dumps(e) + "\n" for e in out))
PYEOF
"$PY" "$ADAPTER" resume --run run-suite --lane L1 --beat --record "$T/rec-old.jsonl" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >/dev/null 2>"$T/b5.err"; rc5=$?
"$PY" "$ADAPTER" resume --run run-suite --lane L1 --beat --stage-from "$T/proj" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >/dev/null 2>"$T/b6.err"; rc6=$?
"$PY" "$ADAPTER" resume --run run-suite --lane L1 --beat --detach --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >/dev/null 2>"$T/b7.err"; rc7=$?
if [ $rc1 -eq 2 ] && grep -q 'no recorded Codex session id' "$T/b1.err" && [ $rc2 -eq 2 ] && grep -q 'takes no --brief' "$T/b2.err" \
   && [ $rc3 -eq 2 ] && grep -q 'no lane-closed after its latest start' "$T/b3.err" && [ $rc4 -eq 2 ] && grep -q 'closed limit' "$T/b4.err" \
   && [ $rc5 -eq 2 ] && grep -q 'nothing is warm to beat' "$T/b5.err" && [ $rc6 -eq 2 ] && grep -q 'takes no --stage-from' "$T/b6.err" \
   && [ $rc7 -eq 2 ] && grep -q 'takes no --stage-from and no --detach' "$T/b7.err" \
   && [ "$(count "$REC" L1 hold-beat)" = 1 ] && [ "$(count "$T/rec-old.jsonl" L1 hold-beat)" = 0 ] && [ "$(count "$T/rec-rb.jsonl" RB hold-beat)" = 0 ]; then pass "beat (premises, must fire): no recorded thread, a brief beside --beat, a running lane, a limit close, a lapsed window, a stage refresh and a worker are each refused (exit 2) with nothing written"; else fail "beat premises" "$rc1 $rc2 $rc3 $rc4 $rc5 $rc6 $rc7: $(cat "$T/b1.err" "$T/b2.err" "$T/b3.err" "$T/b4.err" "$T/b5.err" "$T/b6.err" "$T/b7.err" | tr '\n' '|' | cut -c1-700)"; fi
# F9 (register 2026-09-30 18:22; fix plan addendum F9, version 2): a resume with neither --delegation nor
# --delegation-src carries the lane-open's recorded pair, the regime and its source together, as the supervisor's
# unflagged beat always has, and records the pair it used on lane-resumed. The earlier assertion that an unflagged
# resume under a Settings line reading `auto` must refuse is replaced by these legs: the fix makes it succeed. The
# fixture vaults are the real one's .claude tree beside their own Settings file.
VROOT="${CLAUDE_PROJECT_DIR:-$(cd "$HERE/../../.." && pwd)}"
mkdir -p "$T/autovault" "$T/singlevault"; ln -s "$VROOT/.claude" "$T/autovault/.claude"; ln -s "$VROOT/.claude" "$T/singlevault/.claude"
printf '## Settings\n- **delegation**: auto — the fixture line\n' > "$T/autovault/CUSTOMISATION.md"
printf '## Settings\n- **delegation**: single — the fixture line\n' > "$T/singlevault/CUSTOMISATION.md"
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-dg "$PY" "$ADAPTER" spawn --run run-suite --lane DG "${COMMON[@]}" >/dev/null 2>&1; rc0=$?
mode_of() { # record lane event -> "mode|mode_src|mode_from|carried delegation" of the lane's last such event
  "$PY" - "$1" "$2" "$3" <<'MODE_OF_END'
import json, sys
found = "absent"
for line in open(sys.argv[1], encoding="utf-8"):
    row = json.loads(line)
    if row.get("lane") == sys.argv[2] and row.get("event") == sys.argv[3]:
        found = "%s|%s|%s|%s" % (row.get("mode"), row.get("mode_src"), row.get("mode_from"),
                                 (row.get("carried_from_open") or {}).get("delegation"))
print(found)
MODE_OF_END
}
NRES=$(count "$REC" DG lane-resumed)
rm -f "$CODEX_SHIM_ARGS"
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-dg CLAUDE_PROJECT_DIR="$T/autovault" "$PY" "$ADAPTER" resume --run run-suite --lane DG --brief "$T/follow.md" --codex "$T/bin/codex" --viewer none --silence-s 0 --deadline-s 60 >"$T/f9-1.txt" 2>&1; rc=$?
if [ $rc0 -eq 0 ] && [ $rc -eq 0 ] && [ "$(count "$REC" DG lane-resumed)" = "$((NRES + 1))" ] && grep -q -- "resume thread-dg -" "$CODEX_SHIM_ARGS" \
   && [ "$(mode_of "$REC" DG lane-resumed)" = "single|head|the lane-open's recorded pair (carried)|single (head)" ]; then pass "F9-C01 under a Settings line reading auto, a resume with neither delegation flag carries the lane-open's recorded pair (single, head) together, runs, and records the pair and its origin on lane-resumed"; else fail "F9-C01 the inherited pair" "rc=$rc0/$rc $(mode_of "$REC" DG lane-resumed) $(head -3 "$T/f9-1.txt")"; fi
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-dg CLAUDE_PROJECT_DIR="$T/autovault" "$PY" "$ADAPTER" resume --run run-suite --lane DG --brief "$T/follow.md" --codex "$T/bin/codex" --delegation multi --delegation-src owner --viewer none --silence-s 0 --deadline-s 60 >"$T/f9-2.txt" 2>&1; rc=$?
if [ $rc -eq 0 ] && [ "$(count "$REC" DG lane-resumed)" = "$((NRES + 2))" ] \
   && [ "$(mode_of "$REC" DG lane-resumed)" = "multi|owner|--delegation|None" ]; then pass "F9-C02 a complete explicit pair wins over the recorded one (multi, owner, from --delegation) and nothing is marked carried"; else fail "F9-C02 the explicit pair" "rc=$rc $(mode_of "$REC" DG lane-resumed) $(head -3 "$T/f9-2.txt")"; fi
NRES=$(count "$REC" DG lane-resumed); BEFORE=$(shasum "$REC" | cut -d' ' -f1)
for partial in "--delegation multi" "--delegation-src owner"; do
  rm -f "$CODEX_SHIM_ARGS"
  # shellcheck disable=SC2086
  CODEX_SHIM_MODE=ok CLAUDE_PROJECT_DIR="$T/autovault" "$PY" "$ADAPTER" resume --run run-suite --lane DG --brief "$T/follow.md" --codex "$T/bin/codex" $partial --viewer none --silence-s 0 --deadline-s 60 >/dev/null 2>"$T/f9-partial.err"; rc=$?
  if [ $rc -eq 2 ] && grep -q 'go together' "$T/f9-partial.err" && [ ! -f "$CODEX_SHIM_ARGS" ] && [ "$(shasum "$REC" | cut -d' ' -f1)" = "$BEFORE" ]; then pass "F9-C03 a partial override ($partial alone) is refused (exit 2): the resolver wants the pair, nothing is written and no Codex process starts"; else fail "F9-C03 the partial override $partial" "rc=$rc $(cat "$T/f9-partial.err")"; fi
done
# an unusable recorded pair: a lane whose lane-open carries no pair, then a regime nobody can run
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-dgu "$PY" "$ADAPTER" spawn --run run-dgu --lane DGU "${COMMON[@]}" --record "$T/rec-dgu.jsonl" >/dev/null 2>&1; rc0=$?
f9plant() { # record, how: drop | auto
  "$PY" - "$1" "$2" <<'F9_PLANT_END'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
for row in rows:
    if row.get("event") == "lane-open":
        if sys.argv[2] == "drop":
            row.pop("mode", None); row.pop("mode_src", None)
        else:
            row["mode"], row["mode_src"] = "auto", "owner"
open(sys.argv[1], "w", encoding="utf-8").write("".join(json.dumps(r) + "\n" for r in rows))
F9_PLANT_END
}
for how in drop auto; do
  f9plant "$T/rec-dgu.jsonl" "$how"; BEFORE=$(shasum "$T/rec-dgu.jsonl" | cut -d' ' -f1); rm -f "$CODEX_SHIM_ARGS"
  CODEX_SHIM_MODE=ok CLAUDE_PROJECT_DIR="$T/autovault" "$PY" "$ADAPTER" resume --run run-dgu --lane DGU --record "$T/rec-dgu.jsonl" --brief "$T/follow.md" --codex "$T/bin/codex" --viewer none --silence-s 0 --deadline-s 60 >/dev/null 2>"$T/f9-unusable.err"; rc=$?
  if [ $rc0 -eq 0 ] && [ $rc -eq 2 ] && grep -q 'delegation regime unresolved' "$T/f9-unusable.err" && [ ! -f "$CODEX_SHIM_ARGS" ] \
     && [ "$(shasum "$T/rec-dgu.jsonl" | cut -d' ' -f1)" = "$BEFORE" ] && [ ! -e "$T/store/spawn-records/run-dgu-report-DGU-pass2.md" ]; then pass "F9-C04 an unusable recorded pair ($how) with the Settings line unresolved (auto) is refused (exit 2) before any write or process: the record unchanged, no pass file, no Codex call"; else fail "F9-C04 the unusable pair ($how)" "rc=$rc0/$rc $(cat "$T/f9-unusable.err")"; fi
done
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-dgu CLAUDE_PROJECT_DIR="$T/singlevault" "$PY" "$ADAPTER" resume --run run-dgu --lane DGU --record "$T/rec-dgu.jsonl" --brief "$T/follow.md" --codex "$T/bin/codex" --viewer none --silence-s 0 --deadline-s 60 >"$T/f9-5.txt" 2>&1; rc=$?
if [ $rc -eq 0 ] && [ "$(mode_of "$T/rec-dgu.jsonl" DGU lane-resumed)" = "single|owner|the Settings \`delegation\` line|None" ]; then pass "F9-C05 the control: the same unusable recorded pair under a Settings line reading single resumes on the Settings regime (source owner), so the refusal above is keyed on the unresolved line"; else fail "F9-C05 the Settings fallback" "rc=$rc $(mode_of "$T/rec-dgu.jsonl" DGU lane-resumed) $(head -3 "$T/f9-5.txt")"; fi
NBEATS=$(count "$REC" L1 hold-beat)
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-ok CLAUDE_PROJECT_DIR="$T/autovault" "$PY" "$ADAPTER" resume --run run-suite --lane L1 --beat --codex "$T/bin/codex" --viewer none >"$T/auto-beat.txt" 2>&1; rc2=$?
if [ $rc2 -eq 0 ] && [ "$(count "$REC" L1 hold-beat)" = "$((NBEATS + 1))" ] && [ "$(field "$REC" L1 hold-beat ok)" = true ] \
   && [ "$(field "$REC" L1 hold-beat carried_from_open.delegation)" = '"single (head)"' ] \
   && [ "$(field "$REC" L1 hold-beat by)" = '"hand"' ]; then pass "F9-C06 beat: under a Settings line reading auto an unflagged beat carries the lane-open's recorded regime and runs, as the supervisor's call must"; else fail "F9-C06 beat under delegation auto" "rc=$rc2 $(cat "$T/auto-beat.txt" | head -3)"; fi
CODEX_SHIM_MODE=failed "$PY" "$ADAPTER" resume --run run-suite --lane L1 --beat --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >"$T/beat-fail.txt" 2>&1; rc=$?
if [ $rc -eq 3 ] && [ "$(count "$REC" L1 hold-beat)" = 3 ] && [ "$(field "$REC" L1 hold-beat ok)" = false ] && [ "$(field "$REC" L1 hold-beat exit_class)" = '"failed"' ] \
   && field "$REC" L1 hold-beat error | grep -q 'safety monitor' && grep -q 'FAILED (failed)' "$T/beat-fail.txt" && [ "$(count "$REC" L1 lane-closed)" = "$NCLOSE" ]; then pass "beat (must fire): a failed turn is recorded once with ok false, its exit class and the error, no lane-closed is written, and the wrapper exits 3"; else fail "beat failure" "rc=$rc ok=$(field "$REC" L1 hold-beat ok) class=$(field "$REC" L1 hold-beat exit_class) $(cat "$T/beat-fail.txt")"; fi

# 13c (critic F7, 2026-09-17): the beat's usage line says what it summed and keeps each turn's own
# figures, because whether the CLI reports per-turn usage or a running thread total is unmeasured —
# a sum reads the same either way, so no cached-share bar may rest on it yet. The shim emits two
# turns: the sum is 250 input, and the two turns stand beside it unmerged.
CODEX_SHIM_MODE=twoturns CODEX_SHIM_THREAD=thread-ok "$PY" "$ADAPTER" resume --run run-suite --lane L1 --beat --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >"$T/beat-turns.txt" 2>&1; rc=$?
TURNS=$("$PY" - "$REC" <<'TURNS_END'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
beats = [r for r in rows if r.get("event") == "hold-beat" and r.get("lane") == "L1"]
usage = (beats[-1].get("usage") or {}) if beats else {}
turns = usage.get("turns") or []
basis = beats[-1].get("usage_basis") or ""
print("%s %s %s %s %s" % (len(turns),
                       [t.get("input_tokens") for t in turns],
                       usage.get("input_tokens"),
                       "measured" if "not a running total over the thread, so the cached" in basis else "no basis",
                       "retention-open" if "RETENTION at a beat's interval" in basis and "stays unmeasured" in basis else "no caveat"))
TURNS_END
)
if [ $rc -eq 0 ] && [ "$TURNS" = "2 [100, 150] 250 measured retention-open" ]; then pass "beat (critic F7, folded by review finding 4): the hold-beat carries each turn.completed's own figures beside the sum and a usage_basis that states the invocation semantics — this invocation's own turn, not a running total over the thread — while keeping the one thing still open, the prompt cache's retention at a beat's interval"; else fail "beat usage basis" "rc=$rc turns=[$TURNS] $(head -3 "$T/beat-turns.txt")"; fi
# the retired wording is gone from the shipped adapter, and the comment beside usage_basis states the measured reading
if [ "$(grep -c 'per-turn or cumulative' "$ADAPTER")" = 0 ] && [ "$(grep -c 'is UNMEASURED, so the' "$ADAPTER")" = 0 ] \
   && [ "$(grep -c "Sum each completed turn's own" "$ADAPTER")" = 1 ] \
   && [ "$(grep -c 'cache retention at a future beat interval is unmeasured' "$ADAPTER")" = 1 ]; then pass "beat (review finding 4): the adapter no longer says the per-turn-or-cumulative semantics are unmeasured, and the comment beside usage_basis states the per-invocation sum and the unmeasured retention (controls: both phrases present)"; else fail "usage basis sweep" "retired=$(grep -c 'per-turn or cumulative' "$ADAPTER")/$(grep -c 'is UNMEASURED, so the' "$ADAPTER") stated=$(grep -c "Sum each completed turn's own" "$ADAPTER")/$(grep -c 'cache retention at a future beat interval is unmeasured' "$ADAPTER")"; fi
# the control: a one-turn beat carries one entry and the same basis, never a missing key
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-ok "$PY" "$ADAPTER" resume --run run-suite --lane L1 --beat --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >/dev/null 2>&1; rc=$?
ONE=$("$PY" - "$REC" <<'ONE_END'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
beats = [r for r in rows if r.get("event") == "hold-beat" and r.get("lane") == "L1"]
usage = (beats[-1].get("usage") or {}) if beats else {}
print("%s %s" % (len(usage.get("turns") or []), (beats[-1].get("usage_basis") or "").split(";")[0]))
ONE_END
)
if [ $rc -eq 0 ] && [ "$ONE" = "1 summed over this invocation's 1 turn.completed event(s)" ]; then pass "beat (the control): a one-turn beat carries one per-turn entry and the same basis line, which names the count it summed"; else fail "beat usage basis control" "rc=$rc [$ONE]"; fi

# 13d (critic F4, 2026-09-17; review finding 2, 2026-09-18): the session claim is lane.py's
# advisory lock, shared by both wrappers, so a Codex resume cannot cross a beat on the same
# thread. A live process HOLDING the lock refuses a beat and a real resume alike, with nothing
# written; a lock whose holder has gone, and a marker of the earlier pid form, both block nothing.
CXMARK="$T/store/spawn-records/run-suite-L1-beat.pid"
CXLOCK="$CXMARK.lock"
cxlockstate() { "$PY" - "$HERE/lane.py" "$CXMARK" <<'CXLOCKSTATE_END'
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("lane_cx", sys.argv[1])
lane = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lane)
pid, kind = lane.session_holder(sys.argv[2])
print("free" if pid is None else "held %s %s" % (pid, kind))
CXLOCKSTATE_END
}
cxholder_start() { # $1 lock, $2 ready, $3 stop: a real holder of the advisory lock
  rm -f "$2" "$3"
  "$PY" - "$1" "$2" "$3" <<'CXHOLDER_END' &
import fcntl
import os
import sys
import time

lock, ready, stop = sys.argv[1:4]
fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o644)
fcntl.flock(fd, fcntl.LOCK_EX)
os.ftruncate(fd, 0)
os.write(fd, ("%d beat 2026-09-18T06:00:00+0100\n" % os.getpid()).encode("utf-8"))
os.fsync(fd)
with open(ready, "w", encoding="utf-8") as handle:
    handle.write("%d\n" % os.getpid())
while not os.path.exists(stop):
    time.sleep(0.05)
CXHOLDER_END
  CXHOLDER_PID=$!
  i=0
  while [ ! -f "$2" ] && [ "$i" -lt 200 ]; do sleep 0.05; i=$((i + 1)); done
}
cxholder_stop() { : > "$1"; wait "$CXHOLDER_PID" 2>/dev/null || :; }
cxholder_start "$CXLOCK" "$T/cxholder-ready" "$T/cxholder-stop"
BEFORE=$(shasum "$REC" | cut -d' ' -f1)
CODEX_SHIM_MODE=ok "$PY" "$ADAPTER" resume --run run-suite --lane L1 --beat --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >/dev/null 2>"$T/cxm1.err"; rc1=$?
CODEX_SHIM_MODE=ok "$PY" "$ADAPTER" resume --run run-suite --lane L1 --brief "$T/follow.md" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >/dev/null 2>"$T/cxm2.err"; rc2=$?
AFTER=$(shasum "$REC" | cut -d' ' -f1)
CXHELD=$(cxlockstate)
cxholder_stop "$T/cxholder-stop"
if [ $rc1 -eq 2 ] && [ $rc2 -eq 2 ] && grep -q 'beat is in flight' "$T/cxm1.err" && grep -q 'beat is in flight' "$T/cxm2.err" \
   && grep -q 'two-processes-on-one-session fault' "$T/cxm2.err" && [ "$BEFORE" = "$AFTER" ] \
   && printf '%s' "$CXHELD" | grep -q '^held [0-9]* beat$'; then pass "beat (critic F4 and review finding 2, must fire): while a live process holds the advisory lock, a Codex beat and a real Codex resume of that lane are both refused (exit 2, nothing written), and an outside reader sees the holder's pid and kind"; else fail "codex session lock" "rc=$rc1/$rc2 record $BEFORE/$AFTER state '$CXHELD' $(cat "$T/cxm1.err" "$T/cxm2.err" | tr '\n' '|' | cut -c1-300)"; fi
# the controls: a lock file its holder has released, and a bare pid marker of the earlier form
sleep 30 & MPID=$!
printf '%s %s\n' "$MPID" "2026-09-17T06:00:00+0100" > "$CXMARK"
NB_BEFORE=$(count "$REC" L1 hold-beat)
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-ok "$PY" "$ADAPTER" resume --run run-suite --lane L1 --beat --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >/dev/null 2>"$T/cxm3.err"; rc=$?
CXFREE=$(cxlockstate)
kill "$MPID" 2>/dev/null || :
wait "$MPID" 2>/dev/null || :
rm -f "$CXMARK"
if [ $rc -eq 0 ] && [ -e "$CXLOCK" ] && [ "$CXFREE" = "free" ] && [ "$(count "$REC" L1 hold-beat)" = "$((NB_BEFORE + 1))" ]; then pass "beat (the controls): a lock file whose holder has gone — released by the kernel, so nothing has to be removed — and a bare <run>-<lane>-beat.pid of the earlier form holding a LIVE pid both block nothing, and the beat proceeds and is recorded"; else fail "codex released lock" "rc=$rc lock $([ -e "$CXLOCK" ] && echo present || echo gone) state '$CXFREE' $(head -2 "$T/cxm3.err")"; fi

# 13e (review finding 2, 2026-09-18): the real Codex resume CLAIMS the session immediately
# before it writes its lane-resumed line, so a beat that took the session during the preparation
# is turned back at the door. The shim reads the locked file mid-call: it holds this resume's pid
# and the word resume, and the lock is free again when the call returns.
rm -f "$T/shim-marker.txt"
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-ok CODEX_SHIM_MARKER="$CXLOCK" CODEX_SHIM_MARKER_OUT="$T/shim-marker.txt" \
  "$PY" "$ADAPTER" resume --run run-suite --lane L1 --brief "$T/follow.md" --codex "$T/bin/codex" \
  --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60 >"$T/cxm4.txt" 2>&1; rc=$?
MSEEN=$(cat "$T/shim-marker.txt" 2>/dev/null || printf 'no marker file\n')
if [ $rc -eq 0 ] && printf '%s' "$MSEEN" | grep -qE '^[0-9]+ resume ' && [ "$(cxlockstate)" = "free" ] && [ ! -e "$CXMARK" ]; then pass "beat (review finding 2): a real Codex resume claims the shared advisory lock for the length of its call — the shim read its pid and the word resume from the locked file — and the kernel releases it on return, so a beat arriving meanwhile is refused by the same lock that refuses a second beat"; else fail "codex resume lock" "rc=$rc saw '$MSEEN' state '$(cxlockstate)' bare marker $([ -e "$CXMARK" ] && echo yes || echo no): $(head -3 "$T/cxm4.txt")"; fi

# F7 (register 2026-09-30 10:56, its accounting component; fix plan addendum F7, version 2): the close accounts in four
# states. One leg per event stream, each reading the rendered close line and the stored lane-closed record: no
# completed turn (missing: unknown), a completed turn without usage and one with a malformed usage object (an
# incomplete subtotal), a measured zero (complete, 0, never unknown), two completed turns (complete, summed),
# completed then failed, and completed then stopped by the wrapper (each an incomplete subtotal, the sum kept).
f7rec() { # lane -> "state complete in cached out | reasons" of the lane's last close
  "$PY" - "$REC" "$1" <<'F7REC_END'
import json, sys
close = {}
for line in open(sys.argv[1], encoding="utf-8"):
    row = json.loads(line)
    if row.get("lane") == sys.argv[2] and row.get("event") == "lane-closed":
        close = row
u = close.get("usage") or {}
print("%s %s %s %s %s | %s" % (close.get("usage_state"), close.get("usage_complete"), u.get("input_tokens"),
                               u.get("cached_input_tokens"), u.get("output_tokens"), "; ".join(close.get("usage_incomplete") or [])))
F7REC_END
}
f7leg() { # name lane mode want-record want-line-fragment [extra flags...]
  NAME="$1"; LN="$2"; MODE="$3"; WANT="$4"; FRAG="$5"; shift 5
  CODEX_SHIM_MODE="$MODE" CODEX_SHIM_SLEEP=30 "$PY" "$ADAPTER" spawn --run run-suite --lane "$LN" "${COMMON[@]}" "$@" >"$T/f7-$LN.txt" 2>&1
  F7_RC=$?
  GOT=$(f7rec "$LN"); LINE=$(grep "^lane run-suite/$LN · " "$T/f7-$LN.txt")
  if [ "$MODE" = badtype ]; then
    [ "$F7_RC" -eq 3 ] && [ "$(field "$REC" "$LN" lane-closed disposition.phase)" = '"awaiting-head"' ] || GOT="wrong recovery status/disposition: $F7_RC $GOT"
  fi
  if [ "$GOT" = "$WANT" ] && printf '%s' "$LINE" | grep -qF -- "$FRAG"; then pass "$NAME"; else fail "$NAME" "record [$GOT] want [$WANT]; line [$LINE]"; fi
}
f7leg "F7-C01 no completed turn: usage missing, the close line reads unknown and the record keeps a zero subtotal with usage_complete false" \
  F7A failed "missing False 0 0 0 | no completed turn reported usage" " · 0 turns · in unknown (cached unknown) · out unknown · report "
f7leg "F7-C02 (finding 4) a completed turn carrying no usage object reported no usage: missing, the close line reads unknown, never an incomplete zero, and the record keeps its zero subtotal" \
  F7B nousage "missing False 0 0 0 | no completed turn reported usage; 1 completed turn(s) carried no usage object" " · 1 turns · in unknown (cached unknown) · out unknown · report "
f7leg "F7-C03 a malformed usage object (a token count that is not a number): an incomplete subtotal of what parsed, never a measurement" \
  F7C badusage "incomplete False 0 0 7 | 1 usage object(s) malformed" " · in 0 (cached 0) · out 7 (incomplete subtotal: 1 usage object(s) malformed) · report "
f7leg "F7-C04 a measured zero is complete and shown as 0, never unknown" \
  F7D zero "zero True 0 0 0 | " " · 1 turns · in 0 (cached 0) · out 0 · report "
f7leg "F7-C05 two completed turns: complete usage, the sum of both turns" \
  F7E twoturns "complete True 250 160 9 | " " · 2 turns · in 250 (cached 160) · out 9 · report "
f7leg "F7-C06 a completed turn then a failed one: the completed turn's subtotal kept and marked incomplete" \
  F7F thenfail "incomplete False 100 40 7 | 1 turn(s) failed with usage unreported" " · failed · " --deadline-s 60
f7leg "F7-C07 a completed turn then a stop by the wrapper (the deadline): the subtotal kept and marked incomplete" \
  F7G thenstop "incomplete False 100 40 7 | the wrapper stopped the run (deadline)" "in 100 (cached 40) · out 7 (incomplete subtotal: the wrapper stopped the run (deadline)) · report " --deadline-s 3
if grep -qF "in 100 (cached 40) · out 7 (incomplete subtotal: 1 turn(s) failed with usage unreported)" "$T/f7-F7F.txt" \
   && grep -qF " · deadline · " "$T/f7-F7G.txt" && [ "$(grep -h '^lane run-suite/F7[DE] · ' "$T/f7-F7D.txt" "$T/f7-F7E.txt" | grep -c .)" = 2 ] \
   && ! grep -h '^lane run-suite/F7[DE] · ' "$T/f7-F7D.txt" "$T/f7-F7E.txt" | grep -q 'unknown\|incomplete'; then pass "F7-C08 the incomplete subtotal is rendered beside its figures for the failed stream, the stopped stream closes deadline, and neither the measured zero nor the complete sum says unknown or incomplete (the controls)"; else fail "F7-C08 the rendered controls" "$(grep '^lane ' "$T/f7-F7F.txt" "$T/f7-F7G.txt" "$T/f7-F7D.txt" "$T/f7-F7E.txt" | tr '\n' '|')"; fi
out=$("$PY" "$ADAPTER" watch --run run-suite --lane F7A --appear-s 0 2>&1); rc=$?
OLDCLOSE=$("$PY" - "$ADAPTER" <<'F7_OLD_CLOSE_END'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("f7_old_close", sys.argv[1])
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
text = adapter.usage_text
print(text({"usage": {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "calls": 0}, "usage_complete": False}),
      "|", text({"usage": {"input_tokens": 9, "cached_input_tokens": 1, "output_tokens": 2, "calls": 2}, "usage_complete": False}),
      "|", text({"usage": {"input_tokens": 9, "cached_input_tokens": 1, "output_tokens": 2, "calls": 1}, "usage_complete": True}),
      "|", text({"exit_class": "killed"}))
F7_OLD_CLOSE_END
)
if [ $rc -eq 2 ] && printf '%s' "$out" | grep -qF "in unknown (cached unknown) · out unknown" \
   && [ "$OLDCLOSE" = "in unknown (cached unknown) · out unknown | in 9 (cached 1) · out 2 (incomplete subtotal) | in 9 (cached 1) · out 2 | in unknown (cached unknown) · out unknown" ]; then pass "F7-C09 watch renders a stored close the same way, and a close written before usage_state reads from usage_complete and the turn count (no turn: unknown; a killed subtotal: incomplete; complete: the figures; a kill-written close with no usage: unknown)"; else fail "F7-C09 watch and the older closes" "rc=$rc [$OLDCLOSE] $(printf '%s' "$out" | head -1)"; fi
# The hold-beat path is unchanged: the beat keeps its own usage_complete rule, which handsoff.py's hold verdict reads.
# A beat over the no-usage stream still reads complete there, so its verdict says the whole input read 0 tokens, and
# never "the wrapper recorded usage_complete false", which is what a leak of the close's new rule would show.
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-f7h "$PY" "$ADAPTER" spawn --run run-suite --lane F7H "${COMMON[@]}" >/dev/null 2>&1; rc0=$?
CODEX_SHIM_MODE=nousage CODEX_SHIM_THREAD=thread-f7h "$PY" "$ADAPTER" resume --run run-suite --lane F7H --beat --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >/dev/null 2>&1; rc1=$?
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-f7h "$PY" "$ADAPTER" resume --run run-suite --lane F7H --beat --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >/dev/null 2>&1; rc2=$?
VERDICT=$("$PY" - "$HERE/handsoff.py" "$ADAPTER" "$REC" <<'F7_BEAT_VERDICT_END'
import importlib.util, inspect, json, sys
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
sys.dont_write_bytecode = True
handsoff = load("f7_handsoff", sys.argv[1])
adapter = load("f7_adapter", sys.argv[2])
rows = [json.loads(l) for l in open(sys.argv[3], encoding="utf-8") if l.strip()]
beats = [r for r in rows if r.get("lane") == "F7H" and r.get("event") == "hold-beat"]
verdicts = handsoff.hold_verdict_rows(rows, lane="F7H")
source = inspect.getsource(adapter.run_beat)
print(len(beats), [b.get("usage_complete") for b in beats], [b.get("usage", {}).get("input_tokens") for b in beats],
      [v.get("verdict") for v in verdicts], "usage_complete false" not in " ".join(str(v.get("note")) for v in verdicts),
      "whole input reads 0 tokens" in str(verdicts[0].get("note")) if verdicts else None,
      "close_usage" not in source and "usage_complete=(not killed_by) and parsed[\"turns_completed\"] > 0" in source)
F7_BEAT_VERDICT_END
)
case "$VERDICT" in
  "2 [True, True] [0, 100] ['open', "*"] True True True")
    if [ $rc0 -eq 0 ] && [ $rc1 -eq 0 ] && [ $rc2 -eq 0 ]; then pass "F7-C10 the hold-beat path is unchanged: a beat over the no-usage stream keeps usage_complete true under its own rule, so handsoff.py's hold verdict reads open on a 0-token whole input (never 'usage_complete false'), an ordinary beat reads its 100 tokens, and run_beat does not call the close accounting"; else fail "F7-C10 the beat verdict" "rc=$rc0/$rc1/$rc2 [$VERDICT]"; fi ;;
  *) fail "F7-C10 the beat verdict" "rc=$rc0/$rc1/$rc2 [$VERDICT]" ;;
esac
# F7, review CR-ADD2 (findings 1, 4 and 5): a later turn that ends without turn.failed, a count that is not a
# non-negative integer, and usage evidence that is no measurement; then malformed-stream holds.
f7leg "F7-C11 (finding 5) a completed turn, then a turn a provider error ends with no turn.failed (exit 1): the turn that started and never finished leaves the subtotal incomplete, never complete" \
  F7K thenerror "incomplete False 100 40 7 | 1 turn(s) started and never finished (process exit 1)" "in 100 (cached 40) · out 7 (incomplete subtotal: 1 turn(s) started and never finished (process exit 1)) · report "
f7leg "F7-C12 (finding 5) a completed turn, then a turn cut by a signal from outside the wrapper (exit -15): incomplete, never complete" \
  F7L thensignal "incomplete False 100 40 7 | 1 turn(s) started and never finished (process exit -15)" "(incomplete subtotal: 1 turn(s) started and never finished (process exit -15)) · report "
f7leg "F7-C13 (finding 5) a completed turn, then a process failure with no turn seen in flight: the subtotal is not affirmed whole, the exit named" \
  F7M thenexit "incomplete False 100 40 7 | the process exited 1 after its last completed turn" "(incomplete subtotal: the process exited 1 after its last completed turn) · report "
f7leg "F7-C14 (finding 1) a negative count never joins the sum: the valid turn's subtotal is kept, never turned negative, and marked incomplete" \
  F7N negusage "incomplete False 100 40 9 | 1 usage object(s) malformed" "in 100 (cached 40) · out 9 (incomplete subtotal: 1 usage object(s) malformed) · report "
f7leg "F7-C15 (finding 1) an overflowing count (1e309) never joins the sum and never prevents the close: the close is written, the subtotal kept and marked incomplete" \
  F7O overflow "incomplete False 100 40 9 | 1 usage object(s) malformed" "in 100 (cached 40) · out 9 (incomplete subtotal: 1 usage object(s) malformed) · report "
f7leg "F7-C16 (finding 1) a bool, a float and a numeric string never join the sum, so the subtotal is never overstated: the valid turn's figures kept and marked incomplete" \
  F7P oddvalues "incomplete False 100 40 7 | 1 usage object(s) malformed" "in 100 (cached 40) · out 7 (incomplete subtotal: 1 usage object(s) malformed) · report "
f7leg "F7-C17 (finding 4) an empty usage object is no measurement: usage missing, the close line reads unknown, the zero subtotal kept on the record" \
  F7Q emptyusage "missing False 0 0 0 | no completed turn reported usage; 1 usage object(s) malformed" " · 1 turns · in unknown (cached unknown) · out unknown · report "
f7leg "F7-C18 (finding 4) a measured zero beside a turn without usage is a partial subtotal of 0: distinct from unknown and from a complete zero" \
  F7R zerothennone "incomplete False 0 0 0 | 1 completed turn(s) carried no usage object" " · 2 turns · in 0 (cached 0) · out 0 (incomplete subtotal: 1 completed turn(s) carried no usage object) · report "
# CR-A3-1 L4 (depth), E5: this deliberately reverses the base's clean-completion tolerance.
# Malformed events retain measured usage and the factual close, but return 3 awaiting head judgement.
f7leg "F7-C19 malformed event types or undecodable nesting preserve usage but close evidence-incomplete, returning 3 awaiting the head" \
  F7S badtype "complete True 100 40 7 | " " · evidence-incomplete · "
f7leg "F7-C20 a byte that is not UTF-8 never ends the reading: the events after it reach the close and the turn's usage is complete" \
  F7T badbytes "complete True 100 40 7 | " " · completed · "
F7STRICT=$("$PY" - "$REC" <<'F7_STRICT_END'
import json, sys
def refuse(name):
    raise ValueError("a non-standard JSON constant: %s" % name)
lanes = ("F7N", "F7O", "F7P", "F7S", "F7T")
closes = {}
for text in open(sys.argv[1], encoding="utf-8"):
    row = json.loads(text, parse_constant=refuse)
    if row.get("lane") in lanes and row.get("event") == "lane-closed":
        closes[row["lane"]] = row
print(sorted(closes), closes.get("F7S", {}).get("events_unparseable"), [closes[k].get("usage", {}).get("input_tokens") for k in sorted(closes)])
F7_STRICT_END
)
if [ "$F7STRICT" = "['F7N', 'F7O', 'F7P', 'F7S', 'F7T'] 1 [100, 100, 100, 100, 100]" ]; then pass "F7-C21 (finding 1) every malformed stream above closed once, its record line standard JSON, its input subtotal the valid turn's 100 and never below it (the deep line counted unparseable)"; else fail "F7-C21 the malformed streams' closes" "[$F7STRICT]"; fi
# F7, review CR-ADD3 (finding 1): the close's stricter reading must never reach the beat. The hold-beat path is unchanged
# (fix plan addendum F7), so a beat records what it always recorded, malformed streams included, and handsoff.py's hold
# verdict reads it as it always did. The close reads its stream with parse_close_events; the beat keeps parse_events.
f7beat() { # shim mode -> "rc beats input cached complete verdict | note" for lane F7H's newest beat after one over that stream
  CODEX_SHIM_MODE="$1" CODEX_SHIM_THREAD=thread-f7h "$PY" "$ADAPTER" resume --run run-suite --lane F7H --beat --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >"$T/f7-beat-$1.txt" 2>&1
  "$PY" - "$HERE/handsoff.py" "$REC" "$?" <<'F7_BEAT_READ_END'
import importlib.util, json, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("f7_beat_handsoff", sys.argv[1])
handsoff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handsoff)
rows = [json.loads(line) for line in open(sys.argv[2], encoding="utf-8") if line.strip()]
beats = [row for row in rows if row.get("lane") == "F7H" and row.get("event") == "hold-beat"]
verdicts = handsoff.hold_verdict_rows(rows, lane="F7H")
beat, verdict = (beats[-1] if beats else {}), (verdicts[-1] if verdicts else {})
usage = beat.get("usage") or {}
print("%s %d %s %s %s %s | %s" % (sys.argv[3], len(beats), usage.get("input_tokens"), usage.get("cached_input_tokens"),
                                   beat.get("usage_complete"), verdict.get("verdict"), verdict.get("note")))
F7_BEAT_READ_END
}
GOT=$(f7beat beatneg)
if [ "$GOT" = "0 3 -100 90 True open | unmeasured: usage.input_tokens is -100" ]; then pass "F7-C22 (CR-ADD3 finding 1; rewritten, as it had accepted the changed beat sums) a beat over 100/90 then a negative input records the sum the beat always recorded, input -100 beside cached 90 under its own usage_complete true, and handsoff.py's hold verdict reads open naming the invalid input, never the cache hit the close's stricter sum would give"; else fail "F7-C22 the beat over a negative count" "[$GOT] want [0 3 -100 90 True open | unmeasured: usage.input_tokens is -100] $(tail -2 "$T/f7-beat-beatneg.txt" | tr '\n' ' ')"; fi
GOT=$(f7beat beatstr)
if [ "$GOT" = "0 4 100 90 True hit | " ]; then pass "F7-C23 (CR-ADD3 finding 1) a beat over numeric-string counts records 100 and 90 as the beat always read them, and the hold verdict reads hit as it did before F7, never the 0-token open the close's stricter sum would give"; else fail "F7-C23 the beat over numeric strings" "[$GOT] want [0 4 100 90 True hit | ] $(tail -2 "$T/f7-beat-beatstr.txt" | tr '\n' ' ')"; fi
# The differential and the review's own harness, in process: the beat's reading against the pre-F7 one (its code below)
# over valid and malformed streams; then the actual run_beat with its process and record writes replaced.
"$PY" - "$ADAPTER" "$HERE/handsoff.py" "$T" > "$T/f7-diff.log" 2>&1 <<'F7_BEAT_DIFF_END'
import importlib.util, inspect, json, os, re, sys
sys.dont_write_bytecode = True
adapter_path, handsoff_path, root = sys.argv[1:4]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
adapter = load("f7_diff_adapter", adapter_path)
handsoff = load("f7_diff_handsoff", handsoff_path)
def check(name, cond, detail=""):
    print(("OK " if cond else "BAD ") + name + ("" if cond else "  [%s]" % detail), flush=True)
# codex-lane.py's parse_events as installed before fix F7, its code verbatim (its comments left out): the oracle for
# every figure a beat reads.
PRE_F7 = r'''
def parse_events(lines):
    """Everything the close line reports, from the JSONL events Codex printed. Every line is
    parsed with json.loads; an unparseable one is counted, never grepped for meaning."""
    out = {"records": 0, "unparseable": 0, "turns_completed": 0, "turns_failed": 0,
           "errors": [], "items": {}, "last_message": "", "session_id": None,
           "sandbox_denials": 0, "commands": 0, "turn_usage": [],
           "usage": {"input_tokens": 0, "cached_input_tokens": 0, "cache_write_input_tokens": 0,
                     "output_tokens": 0, "reasoning_output_tokens": 0}}
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        out["records"] += 1
        try:
            event = json.loads(raw)
        except ValueError:
            out["unparseable"] += 1
            continue
        if not isinstance(event, dict):
            out["unparseable"] += 1
            continue
        kind = event.get("type") or ""
        if kind == "thread.started":
            out["session_id"] = event.get("thread_id") or event.get("id") or out["session_id"]
        elif kind == "turn.completed":
            out["turns_completed"] += 1
            usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
            for key in out["usage"]:
                try:
                    out["usage"][key] += int(usage.get(key) or 0)
                except (TypeError, ValueError):
                    pass
            if len(out["turn_usage"]) < TURN_USAGE_KEEP:
                out["turn_usage"].append(
                    {key: usage.get(key) for key in
                     ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                      "output_tokens")})
        elif kind == "turn.failed":
            out["turns_failed"] += 1
            error = event.get("error")
            out["errors"].append(str(error.get("message") if isinstance(error, dict) else error))
        elif kind == "error":
            out["errors"].append(str(event.get("message") or event.get("error") or raw[:300]))
        elif kind.startswith("item."):
            item = event.get("item") if isinstance(event.get("item"), dict) else {}
            itype = str(item.get("type") or "unknown")
            if kind == "item.completed":
                out["items"][itype] = out["items"].get(itype, 0) + 1
            if itype == "agent_message" and kind == "item.completed":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    out["last_message"] = text.strip()
            if itype == "command_execution" and kind == "item.completed":
                out["commands"] += 1
                output = str(item.get("aggregated_output") or item.get("output") or "")
                if DENIAL_RE.search(output):
                    out["sandbox_denials"] += 1
    return out
'''
SUM = 'out["usage"][key] += int(usage.get(key) or 0)'
# the planted control: the same reading with the close's strict sum, the rule the round-2 fold gave the beat too
STRICT = PRE_F7.replace(SUM, 'value = usage.get(key)\n                    out["usage"][key] += value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0')
def reading(source):
    namespace = {"json": json, "DENIAL_RE": adapter.DENIAL_RE, "TURN_USAGE_KEEP": adapter.TURN_USAGE_KEEP}
    exec(source, namespace)
    return namespace["parse_events"]
if SUM not in PRE_F7 or STRICT == PRE_F7:
    print("PROBE FAILED: the planted control could not be built from the pre-F7 reading")
    sys.exit(2)
pre_f7, planted = reading(PRE_F7), reading(STRICT)
OK = '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":90,"cache_write_input_tokens":0,"output_tokens":7,"reasoning_output_tokens":3}}'
def tc(usage):
    return '{"type":"turn.completed","usage":%s}' % usage
STREAMS = {
    "valid": ['{"type":"thread.started","thread_id":"t1"}', '{"type":"turn.started"}', OK],
    "no-usage": ['{"type":"turn.started"}', '{"type":"turn.completed"}'],
    "empty-usage": [tc("{}")],
    "negative": [OK, tc('{"input_tokens":-200,"cached_input_tokens":0,"output_tokens":2}')],
    "numeric-strings": [tc('{"input_tokens":"100","cached_input_tokens":"90","output_tokens":"7"}')],
    "bool": [tc('{"input_tokens":true,"cached_input_tokens":true,"output_tokens":1}')],
    "float": [tc('{"input_tokens":100.9,"cached_input_tokens":90.5,"output_tokens":7}')],
    "overflow": [OK, tc('{"input_tokens":1e309,"cached_input_tokens":0,"output_tokens":2}')],
    "negative-overflow": [tc('{"input_tokens":-1e309,"cached_input_tokens":0,"output_tokens":2}')],
    "nan": [tc('{"input_tokens":NaN,"cached_input_tokens":0,"output_tokens":2}')],
    "word": [tc('{"input_tokens":"lots","cached_input_tokens":0,"output_tokens":7}')],
    "nulls": [tc('{"input_tokens":null,"cached_input_tokens":null,"output_tokens":null}')],
    "list-usage": [tc("[1,2]")],
    "list-values": [tc('{"input_tokens":[100],"cached_input_tokens":{},"output_tokens":7}')],
    "string-usage": [tc('"lots"')],
    "type-int": ['{"type":5}', OK],
    "type-list": ['{"type":["item.completed"]}', OK],
    "type-zero": ['{"type":0}', OK],
    "deep": ["[" * 100000 + "]" * 100000, OK],
    "not-json": ["this is not json {", OK],
    "array-line": ["[1,2,3]", OK],
    "failed": ['{"type":"turn.started"}', '{"type":"turn.failed","error":{"message":"boom"}}'],
    "error-event": [OK, '{"type":"error","message":"stream error"}'],
    "items": ['{"type":"item.completed","item":{"type":"agent_message","text":"REPORT"}}',
              '{"type":"item.completed","item":{"type":"command_execution","aggregated_output":"Operation not permitted"}}', OK],
}
BEAT_KEYS = ("usage", "turns_completed", "turn_usage", "session_id", "last_message", "errors", "records",
             "turns_failed", "unparseable")      # what run_beat and classify read from the parse
def outcome(parse, lines):
    try:
        out = parse([line + "\n" for line in lines])
    except Exception as exc:
        return "raises " + type(exc).__name__
    return json.dumps({key: out.get(key) for key in BEAT_KEYS}, sort_keys=True, default=repr)
differ = [name for name, lines in STREAMS.items() if outcome(adapter.parse_events, lines) != outcome(pre_f7, lines)]
caught = [name for name, lines in STREAMS.items() if outcome(planted, lines) != outcome(pre_f7, lines)]
check("F7-C24 (CR-ADD3 finding 1, the differential) the beat's parse_events matches the pre-F7 reading, its code verbatim in this leg, on all %d streams, valid and malformed (a negative, numeric strings, a bool, a float, 1e309 and -1e309, NaN, a word, nulls, lists, a non-string type, a nesting too deep to decode, a line that is not JSON): every figure the beat and its hold verdict read is equal, and where the pre-F7 reading fails it fails the same way" % len(STREAMS),
      len(STREAMS) == 24 and not differ, "streams that differ: %s" % differ)
check("F7-C24b the differential's control: a planted reading with the close's strict sum (the round-2 fold's rule for the beat) is caught on the negative, numeric-string, bool, float and overflowing streams",
      {"negative", "numeric-strings", "bool", "float", "overflow"} <= set(caught), "caught only %s" % caught)
beat_source, close_source = inspect.getsource(adapter.run_beat), inspect.getsource(adapter.run_lane)
def calls(source, name):
    return bool(re.search(r"\b%s\(" % name, source))
check("F7-C24c separate beat accounting and stop evidence: run_lane calls parse_close_events; run_beat keeps parse_events usage and classifies parse_close_events",
      calls(close_source, "parse_close_events") and not calls(close_source, "parse_events")
      and calls(beat_source, "parse_events") and calls(beat_source, "parse_close_events")
      and 'classify(killed_by, decision,' in beat_source and 'dict(parsed["usage"],' in beat_source
      and calls("x = parse_events(lines)", "parse_events"), "run_lane %s, run_beat %s" % (
          [n for n in ("parse_events", "parse_close_events") if calls(close_source, n)],
          [n for n in ("parse_events", "parse_close_events") if calls(beat_source, n)]))
MSG = '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}'
BEATS = [("100/90 then -200/0", [MSG, tc('{"input_tokens":100,"cached_input_tokens":90,"output_tokens":1}'),
                                 tc('{"input_tokens":-200,"cached_input_tokens":0,"output_tokens":1}')]),
         ("numeric strings", [MSG, tc('{"input_tokens":"100","cached_input_tokens":"90","output_tokens":"1"}')]),
         ("valid", [MSG, tc('{"input_tokens":100,"cached_input_tokens":90,"output_tokens":1}')]),
         ("no usage", [MSG, '{"type":"turn.completed"}'])]
# E1 migration: exercise the actual beat owner and fixture provider, rather than bypassing ownership.
spec=importlib.util.spec_from_file_location("a3_native_fixtures",os.path.join(os.path.dirname(adapter_path),"test_a3.py"))
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
seen=[]
for name,lines in BEATS:
    fixture=fixtures.Fixture(os.path.dirname(adapter_path),root)
    try:
        fixture.scenario("codex",fixtures.events_for("codex","clean"))
        assert fixture.run(fixture.command("codex")).returncode==0
        fixture.scenario("codex",[json.loads(line) for line in lines])
        result=fixture.run(fixture.command("codex","resume",["--beat"]))
        assert result.returncode==0,(result.stdout,result.stderr)
        written=[row for row in fixture.snapshot()["record"] if row.get("event")=="hold-beat"]
        rows=handsoff.hold_verdict_rows(written);usage=written[-1]["usage"]
        seen.append((name,usage.get("input_tokens"),usage.get("cached_input_tokens"),
                     rows[-1]["verdict"],rows[-1]["note"]))
    finally:
        fixture.cleanup()
check("F7-C25 (CR-ADD3 finding 1, the review's executed counterexample) the actual run_beat, its process and record writes replaced, then handsoff.py's hold verdict: 100/90 then -200/0 records -100 and reads open naming usage.input_tokens, never a hit; numeric strings record 100/90 and read hit as before F7; the valid control reads hit and the no-usage control open on 0 tokens",
      seen == [("100/90 then -200/0", -100, 90, "open", "unmeasured: usage.input_tokens is -100"),
               ("numeric strings", 100, 90, "hit", ""), ("valid", 100, 90, "hit", ""),
               ("no usage", 0, 0, "open", "unmeasured: the call's whole input reads 0 tokens")], "%r" % seen)
F7_BEAT_DIFF_END
F7DIFF_RC=$?
while IFS= read -r line; do
  case "$line" in
    'OK '*) pass "${line#OK }" ;;
    'BAD '*) fail "${line#BAD }" "beat differential" ;;
    *) printf '%s\n' "$line" ;;
  esac
done < "$T/f7-diff.log"
if [ "$F7DIFF_RC" != 0 ] || [ "$(grep -c '^OK \|^BAD ' "$T/f7-diff.log")" != 4 ]; then
  fail "F7-C24/C25 the beat differential" "PROBE FAILED: the harness exited $F7DIFF_RC with $(grep -c '^OK \|^BAD ' "$T/f7-diff.log") of 4 legs reported"
fi

# W2: each pass has its own report, including a failed/empty resumed pass.
# The stub thread label changes the body; the adapter still resumes the recorded thread.
for turn in first second third; do
  printf 'Prompt for %s.\n' "$turn" > "$T/pass-$turn.md"
  if [ "$turn" = first ]; then
    CODEX_SHIM_THREAD="$turn" "$PY" "$ADAPTER" spawn --run fixture-reports --lane P "${COMMON[@]}" --brief "$T/pass-$turn.md" >"$T/pass-$turn.log" 2>&1
  else
    CODEX_SHIM_THREAD="$turn" "$PY" "$ADAPTER" resume --run fixture-reports --lane P --brief "$T/pass-$turn.md" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60 >"$T/pass-$turn.log" 2>&1
  fi
  rc=$?
  if [ "$rc" = 0 ]; then pass "W2-C01 $turn pass completes"; else fail "W2-C01 $turn pass" "rc=$rc $(cat "$T/pass-$turn.log")"; fi
done
REPORT_CHECK=$("$PY" - "$ADAPTER" <<'REPORT_PATH_CHECK_END'
import importlib.util, json, pathlib, sys
spec=importlib.util.spec_from_file_location("adapter",sys.argv[1])
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
paths=adapter.store_paths("fixture-reports","P")
records=[json.loads(line) for line in pathlib.Path(paths["record"]).read_text().splitlines()]
reports=[pathlib.Path(e["report"]) for e in records if e.get("event")=="lane-closed"]
first=pathlib.Path(paths["report"])
want=[first,first.with_name(first.stem+"-pass2.md"),first.with_name(first.stem+"-pass3.md")]
assert reports==want
assert [p.read_text().strip() for p in reports]==["REPORT-OK-first","REPORT-OK-second","REPORT-OK-third"]
assert len({p.read_bytes() for p in reports})==3
prompts=[pathlib.Path(e["prompt_file"]) for e in records if e.get("event") in ("lane-open","lane-resumed")]
assert len(prompts)==3 and len(set(prompts))==3
assert all("Prompt for %s." % turn in p.read_text() for p,turn in zip(prompts,("first","second","third")))
assert len({p.read_bytes() for p in prompts})==3
# Each prompt pointer retains its own pass, and the events log appends all passes.
assert pathlib.Path(paths["events"]).read_text().count('"type":"thread.started"')==3
print(str(reports[-1]))
REPORT_PATH_CHECK_END
); rc=$?
if [ "$rc" = 0 ] && [ -n "$REPORT_CHECK" ]; then pass "W2-C02 F3-C01 three reports and prompts retain their own paths and bytes, events append"; else fail "W2-C02 report retention" "$REPORT_CHECK"; fi
out=$("$PY" "$ADAPTER" watch --run fixture-reports --lane P --appear-s 0 --report-words 50 2>&1); rc=$?
if [ "$rc" = 2 ] && printf '%s' "$out" | grep -qF "$REPORT_CHECK" && printf '%s' "$out" | grep -qF 'REPORT-OK-third'; then
  pass "W2-C03 watch prints latest report path and contents"
else fail "W2-C03 watch latest report" "rc=$rc $out"; fi
CODEX_SHIM_MODE=blank "$PY" "$ADAPTER" resume --run fixture-reports --lane P --brief "$T/follow.md" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60 >"$T/pass-blank.log" 2>&1; rc=$?
if [ "$rc" = 3 ] && grep -qF 'empty' "$T/pass-blank.log" && ! grep -qF 'REPORT-OK-third' "$T/pass-blank.log" && grep -qF 'REPORT-OK-third' "$REPORT_CHECK"; then
  pass "W2-C04 empty resume cannot borrow the previous report"
else fail "W2-C04 empty resume" "rc=$rc $(cat "$T/pass-blank.log")"; fi

# F1: reserved identities, pre-existing paths and response-only empty classification.
"$PY" - "$ADAPTER" "$T" <<'COLLISION_REPLAY_END' >"$T/collision-replay.log" 2>&1
import importlib.util, json, os, pathlib, subprocess, sys
script,root=map(pathlib.Path,sys.argv[1:])
spec=importlib.util.spec_from_file_location("collision_adapter",script)
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
def check(name,condition):print(("OK " if condition else "BAD ")+name,flush=True)
def run(args,mode="ok"):
    p=subprocess.run([sys.executable,str(script)]+list(map(str,args)),text=True,capture_output=True,
                     env=dict(os.environ,CODEX_SHIM_MODE=mode))
    return p.returncode,p.stdout,p.stderr
common=["--codex",root / "bin" / "codex","--reason","(a) collision fixture","--choice-reason","fixture",
        "--delegation","single","--delegation-src","head","--viewer","none","--silence-s",0]
source=root / "collision-source";source.mkdir();(source / "data.txt").write_text("old\n")
spawn=["spawn","--run","fixture-guard","--lane","B","--class","critic","--brief",root / "brief.md",
       "--stage-from",source,"--stage-writable"]+common
rc,out,err=run(spawn);assert rc==0,(out,err)
paths=adapter.store_paths("fixture-guard","B");record=pathlib.Path(paths["record"])
initial=record.read_bytes();first=pathlib.Path(paths["report"]);body=first.read_bytes()
opened=next(json.loads(line) for line in record.read_text().splitlines() if json.loads(line).get("event")=="lane-open")
staged=pathlib.Path(opened["cwd"]);(source / "data.txt").write_text("new\n")
for identifier in ("B-pass2","B-pass0","B-pass02","B-pass123","B-PASS1","B-Pass02"):
    rc,out,err=run(spawn+["--lane",identifier,"--dry-run"])
    check("F1-C01 reserved suffix %s refuses before staging" % identifier,rc==2
          and "reserved per-pass suffix" in err and identifier in err and record.read_bytes()==initial)
for identifier in ("B-rx","B-r2-next","B-resume-note","B-R1","B-resume-1","B-passx","B-pass2-next"):
    rc,out,err=run(spawn+["--lane",identifier,"--dry-run"])
    check("F1-C02 non-reserved id %s stays valid" % identifier,rc==0 and '"lane": "%s"'%identifier in out)
resume=["resume","--run","fixture-guard","--lane","B","--brief",root / "follow.md"]+common
report=pathlib.Path(adapter.lane.pass_report_path(paths["report"],2))
prompt=pathlib.Path(adapter.lane.pass_report_path(paths["prompt"],2))
for target in (report,prompt):
    for shape in ("file","directory","dangling-link"):
        if shape=="file":target.write_text("other owner bytes\n")
        elif shape=="directory":target.mkdir()
        else:target.symlink_to(root / "missing-control-target")
        rc,out,err=run(resume+["--stage-from",source])
        other=prompt if target==report else report
        check("F1-C03 existing %s %s refuses before writes and refresh" % (target.name,shape),
              rc==2 and "per-pass path already exists" in err and str(target) in err
              and record.read_bytes()==initial and not other.exists()
              and (staged / "data.txt").read_text()=="old\n"
              and (target.read_text()=="other owner bytes\n" if shape=="file" else os.path.lexists(target)))
        if shape=="directory":target.rmdir()
        else:target.unlink()
for mode in ("blank","blankfile"):
    rc,out,err=run(resume,mode)
    close=next(json.loads(line) for line in reversed(record.read_text().splitlines()) if json.loads(line).get("event")=="lane-closed")
    check("F1-C04 empty response %s cannot borrow report bytes" % mode,
          rc==3 and close["exit_class"]=="empty" and first.read_bytes()==body
          and "OTHER LANE REPORT" not in pathlib.Path(close["report"]).read_text())
COLLISION_REPLAY_END
COLRC=$?
while IFS= read -r line; do
  case "$line" in
    'OK '*) pass "${line#OK }" ;;
    'BAD '*) fail "${line#BAD }" "replay assertion" ;;
    *) printf '%s\n' "$line" ;;
  esac
done < "$T/collision-replay.log"
if [ "$COLRC" != 0 ]; then fail "F1 collision replay premise" "exit $COLRC"; fi

# 14 detach --no-wait: returns at once; the worker closes the lane
out="$(CODEX_SHIM_MODE=ok "$PY" "$ADAPTER" spawn --run run-suite --lane L10 "${COMMON[@]}" --detach --no-wait 2>&1)"; rc=$?
waited=0; while [ $waited -lt 30 ] && [ "$(count "$REC" L10 lane-closed)" != "1" ]; do sleep 1; waited=$((waited+1)); done
if [ $rc -eq 0 ] && printf '%s' "$out" | grep -q "detached pid" && [ "$(field "$REC" L10 lane-closed exit_class)" = '"completed"' ] && [ "$(field "$REC" L10 lane-spawned detached)" = "true" ]; then pass "detach"; else fail "detach" "rc=$rc $out"; fi

# 15 kill: a detached slow lane, killed by name → class killed, exactly one close
CODEX_SHIM_MODE=slow CODEX_SHIM_SLEEP=60 "$PY" "$ADAPTER" spawn --run run-suite --lane L11 "${COMMON[@]}" --detach --no-wait >/dev/null 2>&1
waited=0; while [ $waited -lt 20 ] && [ "$(count "$REC" L11 lane-spawned)" != "1" ]; do sleep 1; waited=$((waited+1)); done
sleep 1
"$PY" "$ADAPTER" kill --run run-suite --lane L11 --reason "suite kill" >/dev/null 2>&1; rc=$?
sleep 2
if [ $rc -eq 0 ] && [ "$(count "$REC" L11 lane-closed)" = "1" ] && [ "$(field "$REC" L11 lane-closed exit_class)" = '"killed"' ]; then pass "kill"; else fail "kill" "rc=$rc closes=$(count "$REC" L11 lane-closed) class=$(field "$REC" L11 lane-closed exit_class)"; fi

# ---- kifix 2026-09-13 ------------------------------------------------------------------------------
# 17 resume re-declares the spawn's effort and --config overrides (register 2026-09-13 04:11)
out="$(CODEX_SHIM_MODE=ok "$PY" "$ADAPTER" spawn --run run-suite --lane UR "${COMMON[@]}" --effort ultra --dry-run 2>&1)"; rc=$?
if [ $rc -eq 2 ] && printf '%s' "$out" | grep -q -- '--effort must be one of low, medium, high, xhigh, max$'; then pass "a spawn at the retired ultra is refused, naming the ladder (DW-20261102-1)"; else fail "the retired ultra" "rc=$rc $(printf '%s' "$out" | tail -1)"; fi
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-u1 "$PY" "$ADAPTER" spawn --run run-suite --lane U1 "${COMMON[@]}" --effort xhigh --config features.multi_agent=true >/dev/null 2>&1; rc1=$?
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-u1 "$PY" "$ADAPTER" resume --run run-suite --lane U1 --brief "$T/follow.md" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60 >"$T/u1.txt" 2>&1; rc2=$?
order_ok=$("$PY" -c 'import sys; s = open(sys.argv[1]).read(); f = s.find("features.multi_agent=false"); t = s.find("features.multi_agent=true"); print("yes" if 0 <= f < t else "no")' "$CODEX_SHIM_ARGS")
if [ $rc1 -eq 0 ] && [ $rc2 -eq 0 ] && grep -q -- 'model_reasoning_effort="xhigh"' "$CODEX_SHIM_ARGS" && [ "$order_ok" = yes ] \
   && grep -q -- 'resume thread-u1 -' "$CODEX_SHIM_ARGS" && [ "$(field "$REC" U1 lane-resumed effort)" = '"xhigh"' ] \
   && [ "$(field "$REC" U1 lane-open config_extra)" = '["features.multi_agent=true"]' ] \
   && [ "$(field "$REC" U1 lane-resumed carried_from_open.config)" = '["features.multi_agent=true"]' ]; then pass "resume re-declares the spawn's xhigh and features.multi_agent=true (after the default false)"; else fail "resume re-declares effort and config" "rc=$rc1/$rc2 order=$order_ok effort=$(field "$REC" U1 lane-resumed effort) $(head -3 "$T/u1.txt")"; fi
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-u1 "$PY" "$ADAPTER" resume --run run-suite --lane U1 --brief "$T/follow.md" --codex "$T/bin/codex" --effort max --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60 >/dev/null 2>&1; rc=$?
if [ $rc -eq 0 ] && grep -q -- 'model_reasoning_effort="max"' "$CODEX_SHIM_ARGS" && ! grep -q -- 'model_reasoning_effort="xhigh"' "$CODEX_SHIM_ARGS" \
   && grep -q -- '-c features.multi_agent=true' "$CODEX_SHIM_ARGS" && [ "$(field "$REC" U1 lane-resumed carried_from_open.effort)" = 'null' ]; then pass "a resume's own --effort wins and the recorded config is still carried"; else fail "a resume's own --effort" "rc=$rc $(cat "$CODEX_SHIM_ARGS")"; fi
"$PY" - "$REC" "$T/legacy.jsonl" <<'PYEOF'
import json, sys
out = []
for line in open(sys.argv[1], encoding="utf-8"):
    event = json.loads(line)
    if event.get("lane") != "U1":
        continue
    if event.get("event") == "lane-open":
        event.pop("config_extra", None)
    out.append(event)
open(sys.argv[2], "w", encoding="utf-8").write("".join(json.dumps(e) + "\n" for e in out))
PYEOF
out="$("$PY" "$ADAPTER" resume --run run-suite --lane U1 --record "$T/legacy.jsonl" --brief "$T/follow.md" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none --dry-run 2>&1)"; rc=$?
if [ $rc -eq 0 ] && printf '%s' "$out" | grep -q -- 'features.multi_agent=true' && printf '%s' "$out" | grep -q -- 'model_reasoning_effort="xhigh"' \
   && printf '%s' "$out" | grep -q '"config_src": "lane-open config_overrides after the default block"'; then pass "a lane-open from before config_extra still carries its overrides, read after the default block"; else fail "the legacy lane-open's overrides" "rc=$rc $out"; fi
"$PY" - "$T/legacy.jsonl" "$T/legacy-bad.jsonl" <<'PYEOF'
import json, sys
out = []
for line in open(sys.argv[1], encoding="utf-8"):
    event = json.loads(line)
    if event.get("event") == "lane-open":
        event["config_overrides"] = ["bogus.key=1"] + event["config_overrides"]
    out.append(event)
open(sys.argv[2], "w", encoding="utf-8").write("".join(json.dumps(e) + "\n" for e in out))
PYEOF
out="$("$PY" "$ADAPTER" resume --run run-suite --lane U1 --record "$T/legacy-bad.jsonl" --brief "$T/follow.md" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none --dry-run 2>&1)"; rc=$?
if [ $rc -eq 0 ] && ! printf '%s' "$out" | grep -q -- 'features.multi_agent=true' && printf '%s' "$out" | grep -q 'do not start with the default block; no --config carried'; then pass "a config_overrides list not starting with the default block carries no --config, and one line says so"; else fail "the unreadable overrides list" "rc=$rc $out"; fi

# 18 resume --stage-from refreshes the lane's staged copy in place (register 2026-09-11 23:37)
mkdir -p "$T/proj2/keep"; printf 'old\n' > "$T/proj2/keep/a.md"
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-s3 "$PY" "$ADAPTER" spawn --run run-suite --lane S3 --codex "$T/bin/codex" --class critic --brief "$T/brief.md" --stage-from "$T/proj2" --stage-writable --reason "(a) suite" --choice-reason "suite pick" --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60 >/dev/null 2>&1; rc1=$?
STAGE3="$TR/store/spawn-records/run-suite-cwd-S3"
printf 'the lane wrote this\n' > "$STAGE3/lane-note.md"
printf 'new\n' > "$T/proj2/keep/a.md"; printf 'added\n' > "$T/proj2/keep/b.md"
CODEX_SHIM_MODE=catfile CODEX_SHIM_CAT=keep/a.md CODEX_SHIM_THREAD=thread-s3 "$PY" "$ADAPTER" resume --run run-suite --lane S3 --brief "$T/follow.md" --stage-from "$T/proj2" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60 >"$T/s3.txt" 2>&1; rc2=$?
if [ $rc1 -eq 0 ] && [ $rc2 -eq 0 ] && [ "$(cat "$STAGE3/keep/a.md")" = new ] && [ -f "$STAGE3/keep/b.md" ] && [ -f "$STAGE3/lane-note.md" ] \
   && grep -q '^SEEN new' "$T/store/spawn-records/run-suite-report-S3-pass2.md" && grep -q -- "-C $STAGE3 " "$CODEX_SHIM_ARGS" \
   && [ "$(field "$REC" S3 lane-resumed cwd)" = "\"$STAGE3\"" ] && [ "$(field "$REC" S3 lane-resumed stage.refreshed.replaced)" = 1 ] \
   && [ "$(field "$REC" S3 lane-resumed stage.refreshed.added)" = 1 ] && [ "$(field "$REC" S3 lane-resumed stage.refreshed.kept_only_in_copy)" = 1 ]; then pass "resume --stage-from refreshes the staged copy in place: the resumed lane reads the changed file at the same path, and the lane's own file stays"; else fail "resume --stage-from refresh" "rc=$rc1/$rc2 a=$(cat "$STAGE3/keep/a.md") $(head -3 "$T/s3.txt")"; fi
nres=$(count "$REC" L1 lane-resumed)
"$PY" "$ADAPTER" resume --run run-suite --lane L1 --brief "$T/follow.md" --stage-from "$T/proj2" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none >/dev/null 2>"$T/err18.txt"; rc=$?
if [ $rc -eq 2 ] && grep -q "recorded cwd $TR/work is not one" "$T/err18.txt" && [ "$(count "$REC" L1 lane-resumed)" = "$nres" ]; then pass "resume --stage-from on a lane that was never staged is refused, naming its cwd, and writes nothing"; else fail "resume --stage-from refusal" "rc=$rc $(cat "$T/err18.txt")"; fi
# F9: the delegation pair is resolved before the stage refresh, so an unusable recorded pair under an unresolved
# Settings line refuses with the staged copy untouched (the refresh would otherwise copy the changed source in).
"$PY" - "$REC" "$T/rec-s3u.jsonl" <<'S3_UNUSABLE_END'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
out = []
for row in rows:
    if row.get("lane") != "S3":
        continue
    if row.get("event") == "lane-open":
        row.pop("mode", None); row.pop("mode_src", None)
    out.append(row)
open(sys.argv[2], "w", encoding="utf-8").write("".join(json.dumps(r) + "\n" for r in out))
S3_UNUSABLE_END
printf 'newest\n' > "$T/proj2/keep/a.md"; BEFORE=$(shasum "$T/rec-s3u.jsonl" | cut -d' ' -f1); rm -f "$CODEX_SHIM_ARGS"
CODEX_SHIM_MODE=ok CLAUDE_PROJECT_DIR="$T/autovault" "$PY" "$ADAPTER" resume --run run-suite --lane S3 --record "$T/rec-s3u.jsonl" --brief "$T/follow.md" --stage-from "$T/proj2" --codex "$T/bin/codex" --viewer none --silence-s 0 --deadline-s 60 >/dev/null 2>"$T/f9-s3.err"; rc=$?
if [ $rc -eq 2 ] && grep -q 'delegation regime unresolved' "$T/f9-s3.err" && [ "$(cat "$STAGE3/keep/a.md")" = new ] \
   && [ "$(shasum "$T/rec-s3u.jsonl" | cut -d' ' -f1)" = "$BEFORE" ] && [ ! -f "$CODEX_SHIM_ARGS" ]; then pass "F9-C07 an unusable recorded pair on a staged lane refuses (exit 2) before the stage refresh: the staged copy keeps its old bytes, the record is unchanged and no Codex process starts"; else fail "F9-C07 the refusal before the refresh" "rc=$rc stage=$(cat "$STAGE3/keep/a.md") $(cat "$T/f9-s3.err")"; fi

# 19 watch returns on the close after the latest open or resume (register 2026-09-10 07:31)
sleep 120 & WPID=$!
WREC="$T/watch-rec.jsonl"
"$PY" - "$WREC" "$WPID" <<'PYEOF'
import json, sys
path, pid = sys.argv[1], int(sys.argv[2])
rows = [{"ts": "2026-09-13T01:00:00+0100", "run": "run-w", "lane": "WL", "event": "lane-open", "harness": "codex", "model": "gpt-6-astra", "effort": "ultra"},
        {"ts": "2026-09-13T01:00:01+0100", "run": "run-w", "lane": "WL", "event": "lane-spawned", "pid": pid, "wrapper_pid": pid},
        {"ts": "2026-09-13T01:05:00+0100", "run": "run-w", "lane": "WL", "event": "lane-closed", "exit_class": "completed", "exit_code": 0},
        {"ts": "2026-09-13T01:10:00+0100", "run": "run-w", "lane": "WL", "event": "lane-resumed", "harness": "codex", "model": "gpt-6-astra", "effort": "ultra"},
        {"ts": "2026-09-13T01:10:01+0100", "run": "run-w", "lane": "WL", "event": "lane-respawned", "pid": pid, "wrapper_pid": pid}]
with open(path, "w", encoding="utf-8") as handle:
    handle.write("".join(json.dumps(row) + "\n" for row in rows))
PYEOF
"$PY" "$ADAPTER" watch --run run-w --lane WL --record "$WREC" --poll-s 0.5 --appear-s 1 --max-wait-s 30 >"$T/w1.txt" 2>&1 &
WATCHER=$!
sleep 3
alive3=no; if kill -0 "$WATCHER" 2>"$T/kill0.err"; then alive3=yes; fi
printf '%s\n' '{"ts": "2026-09-13T01:20:00+0100", "run": "run-w", "lane": "WL", "event": "lane-closed", "exit_class": "limit", "exit_code": 6}' >> "$WREC"
wait "$WATCHER"; rc=$?
if [ "$alive3" = yes ] && [ $rc -eq 6 ] && grep -q ' · limit · ' "$T/w1.txt"; then pass "watch waits past the earlier close for the close after the resume and exits with its code (6, limit)"; else fail "watch after a resume" "alive at 3 s=$alive3 rc=$rc $(cat "$T/w1.txt")"; fi
"$PY" "$ADAPTER" watch --run run-w --lane WL --record "$WREC" --poll-s 0.5 --appear-s 1 >"$T/w2.txt" 2>&1; rc=$?
if [ $rc -eq 2 ] && grep -q 'already closed (limit' "$T/w2.txt" && grep -q ' · limit · ' "$T/w2.txt"; then pass "watch on a lane whose latest call has closed prints that close and exits 2 after --appear-s"; else fail "watch on a closed lane" "rc=$rc $(cat "$T/w2.txt")"; fi
head -2 "$WREC" > "$T/watch-rec2.jsonl"
"$PY" "$ADAPTER" watch --run run-w --lane WL --record "$T/watch-rec2.jsonl" --poll-s 0.5 --appear-s 1 --max-wait-s 2 >"$T/w3.txt" 2>&1; rc=$?
if [ $rc -eq 8 ] && grep -q '^still-running: lane run-w/WL' "$T/w3.txt"; then pass "watch returns still-running (exit 8) after --max-wait-s"; else fail "watch still-running" "rc=$rc $(cat "$T/w3.txt")"; fi
"$PY" "$ADAPTER" watch --run run-w --lane NOPE --record "$WREC" --appear-s 1 >"$T/w4.txt" 2>&1; rc=$?
if [ $rc -eq 2 ] && grep -q 'is unknown in' "$T/w4.txt"; then pass "watch on an unknown lane is refused (exit 2)"; else fail "watch on an unknown lane" "rc=$rc $(cat "$T/w4.txt")"; fi
sh -c 'exit 0' & GONE=$!; wait "$GONE"
printf '%s\n' '{"ts": "2026-09-13T01:00:00+0100", "run": "run-w", "lane": "WO", "event": "lane-open"}' \
  "{\"ts\": \"2026-09-13T01:00:01+0100\", \"run\": \"run-w\", \"lane\": \"WO\", \"event\": \"lane-spawned\", \"pid\": $GONE, \"wrapper_pid\": $GONE}" > "$T/watch-rec3.jsonl"
"$PY" "$ADAPTER" watch --run run-w --lane WO --record "$T/watch-rec3.jsonl" --poll-s 0.2 --appear-s 1 --max-wait-s 30 >"$T/w5.txt" 2>&1; rc=$?
if [ $rc -eq 3 ] && grep -q '^orphaned: lane run-w/WO' "$T/w5.txt" && [ "$(wc -l < "$T/watch-rec3.jsonl" | tr -d ' ')" = 2 ]; then pass "watch on a lane whose wrapper has gone with no close exits 3, names explicit reconciliation, and writes nothing"; else fail "watch on an orphaned lane" "rc=$rc $(cat "$T/w5.txt")"; fi
kill "$WPID" 2>"$T/kill0.err"

# 20 a detached spawn's caller opens the console before the worker exists (register 2026-09-09 11:21)
cat > "$T/bin/viewer-order.sh" <<'VIEWER_ORDER'
#!/bin/sh
printf 'OPENER ppid=%s\n' "$PPID" >> "$CODEX_SHIM_ORDER"
exit 0
VIEWER_ORDER
chmod +x "$T/bin/viewer-order.sh"
ORDER="$T/order.txt"; : > "$ORDER"
OREC="$T/store/spawn-records/run-order.jsonl"
out="$(env -u AIMYTH_VIEWER AIMYTH_VIEWER_CMD="$T/bin/viewer-order.sh" CODEX_SHIM_ORDER="$ORDER" CODEX_SHIM_MODE=ok "$PY" "$ADAPTER" spawn --run run-order --lane O1 --codex "$T/bin/codex" --class critic --brief "$T/brief.md" --cwd "$T/work" --reason "(a) suite" --choice-reason "suite pick" --delegation single --delegation-src head --viewer terminal --silence-s 0 --deadline-s 60 --detach --no-wait 2>"$T/o1.err")"; rc=$?
opid=$(printf '%s\n' "$out" | sed -n 's/^detached pid \([0-9][0-9]*\) .*$/\1/p')
waited=0; while [ $waited -lt 30 ] && ! { [ -f "$OREC" ] && [ "$(count "$OREC" O1 lane-closed)" = "1" ]; }; do sleep 1; waited=$((waited+1)); done
first=$(sed -n 1p "$ORDER"); second=$(sed -n 2p "$ORDER")
if [ $rc -eq 0 ] && [ -n "$opid" ] && [ "$(grep -c '^OPENER ' "$ORDER")" = 1 ] && printf '%s' "$first" | grep -q '^OPENER ppid=' \
   && [ "$first" != "OPENER ppid=$opid" ] && printf '%s' "$second" | grep -q '^LANE ' \
   && grep -q 'viewer none · no window' "$T/store/spawn-records/run-order-detached-O1.log"; then pass "a detached spawn's caller runs the opener once, before the lane starts and not from the worker, and the worker runs under --viewer none"; else fail "the opener's call order" "rc=$rc worker=$opid order=$(tr '\n' '|' < "$ORDER") err=$(head -2 "$T/o1.err" | tr '\n' ' ')"; fi

# F8 (register 2026-09-29 16:57; fix plan addendum F8, version 2): the caller already ran prepare before its detach;
# the repair is the acknowledgement. --detach --no-wait waits, bounded, for THIS call's own lane-open or lane-resumed,
# matched on the worker's pid as wrapper_pid after the record's length at the detach. CLI legs use the real worker;
# the outcome legs plant one (the interpreter the caller starts is replaced), so each outcome is forced.
tfield() { # record lane event field: a tolerant read, since the worker may be appending while it runs
  "$PY" - "$1" "$2" "$3" "$4" <<'TFIELD_END'
import json, sys
value = None
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        row = json.loads(line)
    except ValueError:
        continue
    if row.get("lane") == sys.argv[2] and row.get("event") == sys.argv[3]:
        value = row.get(sys.argv[4])
print(json.dumps(value))
TFIELD_END
}
out="$(CODEX_SHIM_MODE=ok "$PY" "$ADAPTER" spawn --run run-suite --lane F8X "${COMMON[@]}" --brief "$T/badcontrol.md" --detach --no-wait 2>"$T/f8x.err")"; rc=$?
if [ $rc -eq 2 ] && [ -z "$out" ] && grep -q 'PROBE FAILED' "$T/f8x.err" && grep -q 'zzz-no-such-phrase-zzz' "$T/f8x.err" \
   && [ ! -e "$T/store/spawn-records/run-suite-detached-F8X.log" ] && [ "$(count "$REC" F8X lane-open)" = 0 ]; then pass "F8-C01 a refused spawn under --detach --no-wait (a control that cannot hit) exits 2 in the caller, prints no detached line and starts no worker (no detach log, no lane-open)"; else fail "F8-C01 the refused detached spawn" "rc=$rc out=[$out] $(tail -1 "$T/f8x.err")"; fi
NRES=$(count "$REC" L1 lane-resumed)
out="$(CODEX_SHIM_MODE=ok "$PY" "$ADAPTER" resume --run run-suite --lane L1 --brief "$T/follow.md" --codex "$T/bin/codex" --delegation multi --viewer none --detach --no-wait 2>"$T/f8y.err")"; rc=$?
if [ $rc -eq 2 ] && [ -z "$out" ] && grep -q 'go together' "$T/f8y.err" && [ ! -e "$T/store/spawn-records/run-suite-detached-L1.log" ] \
   && [ "$(count "$REC" L1 lane-resumed)" = "$NRES" ]; then pass "F8-C02 a refused resume under --detach --no-wait (one delegation flag alone) exits 2 in the caller, prints no detached line and starts no worker"; else fail "F8-C02 the refused detached resume" "rc=$rc out=[$out] $(tail -1 "$T/f8y.err")"; fi
out="$(CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-f8a "$PY" "$ADAPTER" spawn --run run-suite --lane F8A "${COMMON[@]}" --detach --no-wait 2>"$T/f8a.err")"; rc=$?
apid=$(printf '%s\n' "$out" | sed -n 's/^detached pid \([0-9][0-9]*\) (log .*)$/\1/p')
AT=$(tfield "$REC" F8A lane-open wrapper_pid)
waited=0; while [ $waited -lt 30 ] && [ "$(count "$REC" F8A lane-closed)" != "1" ]; do sleep 1; waited=$((waited+1)); done
if [ $rc -eq 0 ] && [ -n "$apid" ] && [ "$(printf '%s\n' "$out" | grep -c .)" = 1 ] && [ "$AT" = "$apid" ] \
   && [ "$(tfield "$REC" F8A lane-closed exit_class)" = '"completed"' ]; then pass "F8-C03 a detached spawn prints its one detached line only once the record holds this call's lane-open, written by the printed worker pid (wrapper_pid), and the worker runs the lane to completed"; else fail "F8-C03 the acknowledged detached spawn" "rc=$rc out=[$out] lane-open wrapper_pid at return $AT"; fi
out="$(CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-f8a "$PY" "$ADAPTER" resume --run run-suite --lane F8A --brief "$T/follow.md" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60 --detach --no-wait 2>"$T/f8ar.err")"; rc=$?
rpid=$(printf '%s\n' "$out" | sed -n 's/^detached pid \([0-9][0-9]*\) (log .*)$/\1/p')
AT=$(tfield "$REC" F8A lane-resumed wrapper_pid)
waited=0; while [ $waited -lt 30 ] && [ "$(count "$REC" F8A lane-closed)" != "2" ]; do sleep 1; waited=$((waited+1)); done
if [ $rc -eq 0 ] && [ -n "$rpid" ] && [ "$AT" = "$rpid" ] && [ "$rpid" != "$apid" ] && [ "$(tfield "$REC" F8A lane-closed exit_class)" = '"completed"' ]; then pass "F8-C04 a detached resume prints its detached line only once the record holds a lane-resumed written by the printed worker pid (not the spawn's), and the resumed call completes"; else fail "F8-C04 the acknowledged detached resume" "rc=$rc out=[$out] lane-resumed wrapper_pid at return $AT"; fi
# COLUMNS wide enough that argparse never wraps a help text, so no phrase is broken at a hyphen
HLP=$( (COLUMNS=4000 "$PY" "$ADAPTER" spawn --help; COLUMNS=4000 "$PY" "$ADAPTER" resume --help) 2>&1 | tr '\n' ' ' | tr -s ' ')
HLPN=0
for phrase in "THIS call's own lane-open" "THIS call's own lane-resumed" "a refusal exits 2 and starts no worker" \
              "print its log tail and exit non-zero" 'print `detached pid N, unconfirmed after S s` and exit 4, the worker left running' \
              "the acknowledgement bound in seconds (default 60, lane.py's; a waiting limit, not a stall controller)" \
              "on resume, with neither flag, the lane-open's recorded pair is carried and recorded on lane-resumed"; do
  printf '%s' "$HLP" | grep -qF -- "$phrase" && HLPN=$((HLPN + 1))
done
if [ "$HLPN" = 7 ]; then pass "F8-C05 the spawn and resume help state the four outcomes and the 60 s bound, and resume's names the carried delegation pair (F9)"; else fail "F8-C05 the help text" "$HLPN of 7 phrases"; fi
cat > "$T/bin/fake-worker.py" <<'FAKE_WORKER_END'
#!/usr/bin/env python3
"""A planted detached worker for the F8 legs: the caller under test starts it in place of the interpreter.
It records its argv in FAKE_WORKER_ARGV and acts on FAKE_WORKER_MODE: ack-open and ack-resumed write this
call's line after FAKE_WORKER_DELAY s and linger; refuse exits 2 with a planted refusal; other-resumed writes a
lane-resumed under a foreign pid and sleeps; unreadable makes the record unreadable and sleeps; silent sleeps."""
import json, os, sys, time
argv = sys.argv[1:]
while argv and not argv[0].endswith(".py"):
    argv = argv[1:]
args = argv[2:]
def flag(name):
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None
with open(os.environ["FAKE_WORKER_ARGV"], "w", encoding="utf-8") as handle:
    handle.write("\n".join(argv) + "\n")
record, lane_id, run = flag("--record"), flag("--lane"), flag("--run")
mode = os.environ.get("FAKE_WORKER_MODE", "silent")
def line(event, **extra):
    row = dict({"ts": "2026-10-09T03:00:00+0100", "run": run, "lane": lane_id, "event": event, "planted": True}, **extra)
    with open(record, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
if mode == "refuse":
    sys.stderr.write("codex-lane.py: PROBE FAILED: a planted worker refusal\n")
    sys.exit(2)
if mode in ("ack-open", "ack-resumed"):
    time.sleep(float(os.environ.get("FAKE_WORKER_DELAY", "0.5")))
    if mode == "ack-open":
        line("lane-open", session_id=flag("--session-id"), wrapper_pid=os.getpid())
    else:
        line("lane-resumed", wrapper_pid=os.getpid())
    time.sleep(float(os.environ.get("FAKE_WORKER_LINGER", "1")))
    sys.exit(0)
if mode == "other-resumed":
    line("lane-resumed", wrapper_pid=os.getpid() + 100000)
if mode == "unreadable":
    if not os.path.exists(record):
        open(record, "a").close()
    os.chmod(record, 0)
time.sleep(float(os.environ.get("FAKE_WORKER_SLEEP", "30")))
FAKE_WORKER_END
chmod +x "$T/bin/fake-worker.py"
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-f8cr "$PY" "$ADAPTER" spawn --run run-f8cr --lane F8CR "${COMMON[@]}" --record "$T/rec-f8cr.jsonl" >/dev/null 2>&1
"$PY" - "$ADAPTER" "$T/bin/fake-worker.py" "$T" "$T/bin/codex" "$T/brief.md" "$T/follow.md" "$T/work" >"$T/f8c-forced.log" 2>&1 <<'F8C_FORCED_OUTCOMES_END'
import contextlib, importlib.util, io, json, os, re, shutil, signal, sys, time
adapter_path, fake, root, shim, brief, follow, work = sys.argv[1:8]
spec = importlib.util.spec_from_file_location("codex_f8", adapter_path)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
argv_file = os.path.join(root, "f8c-worker-argv.txt")
os.environ["FAKE_WORKER_ARGV"] = argv_file
def check(name, cond, detail=""):
    print(("OK " if cond else "BAD ") + name + ("" if cond else "  [%s]" % detail), flush=True)
def call(argv, mode, **env):
    if os.path.exists(argv_file):
        os.remove(argv_file)
    saved = dict(os.environ)
    os.environ["FAKE_WORKER_MODE"] = mode
    os.environ.update({k: str(v) for k, v in env.items()})
    out, err = io.StringIO(), io.StringIO()
    argv = [str(a) for a in argv]
    real = (sys.executable, sys.argv)
    sys.executable, sys.argv = fake, [adapter_path] + argv
    began = time.monotonic()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = adapter.main(argv)
            except SystemExit as exc:
                rc = exc.code
    finally:
        sys.executable, sys.argv = real
        os.environ.clear()
        os.environ.update(saved)
    return rc, out.getvalue(), err.getvalue(), time.monotonic() - began
def running(pid):
    try:
        return os.waitpid(pid, os.WNOHANG) == (0, 0)
    except ChildProcessError:
        return False
def stop(pid):
    try:
        os.kill(pid, signal.SIGTERM)
        os.waitpid(pid, 0)
    except (OSError, ChildProcessError):
        pass
def rows(path):
    out = []
    try:
        for text in open(path, encoding="utf-8"):
            try:
                out.append(json.loads(text))
            except ValueError:
                pass
    except OSError:
        pass
    return out
def pid_of(text, unconfirmed=False):
    m = re.fullmatch(r"detached pid (\d+), unconfirmed after (\d+) s\n" if unconfirmed
                     else r"detached pid (\d+) \(log (.+)\)\n", text)
    return (int(m.group(1)), m.group(2)) if m else (None, None)
common = ["--codex", shim, "--delegation", "single", "--delegation-src", "head", "--viewer", "none",
          "--silence-s", "0", "--deadline-s", "60"]
def spawn_args(lane_id, wait, no_wait=True):
    return (["spawn", "--run", "run-f8c", "--lane", lane_id, "--class", "critic", "--brief", brief, "--cwd", work,
             "--reason", "(a) F8 forced outcome", "--choice-reason", "suite pick",
             "--record", os.path.join(root, "rec-f8c-%s.jsonl" % lane_id)] + common
            + ["--detach"] + (["--no-wait"] if no_wait else []) + ["--ack-wait-s", str(wait)])
base_record = os.path.join(root, "rec-f8cr.jsonl")
def resume_args(case, wait):
    record = os.path.join(root, "rec-f8cr-%s.jsonl" % case)
    shutil.copyfile(base_record, record)
    return record, (["resume", "--run", "run-f8cr", "--lane", "F8CR", "--brief", follow, "--record", record] + common
                    + ["--detach", "--no-wait", "--ack-wait-s", str(wait)])
rc, out, err, took = call(spawn_args("C1", 10), "ack-open", FAKE_WORKER_DELAY=1.0)
pid, log = pid_of(out)
opened = [r for r in rows(os.path.join(root, "rec-f8c-C1.jsonl")) if r.get("event") == "lane-open"]
check("F8-CS1 spawn, acknowledged: detached pid N (log L), exit 0, only after a lane-open written by pid N (a 1 s planted delay waited out)",
      rc == 0 and pid is not None and took >= 1.0 and [r.get("wrapper_pid") for r in opened] == [pid], "rc %r out %r took %.2f opened %r" % (rc, out, took, opened))
announced = [(pid, err)]
if pid:
    stop(pid)
rc, out, err, took = call(spawn_args("C2", 10), "refuse")
check("F8-CS2 spawn, the worker exits first: exit 2 (its own code), no detached line, its log tail with the planted refusal",
      rc == 2 and out == "" and "a planted worker refusal" in err and "exited 2 before writing this call's lane-open" in err, "rc %r out %r err %r" % (rc, out, err[-300:]))
rc, out, err, took = call(spawn_args("C3", 2), "silent")
pid, after = pid_of(out, unconfirmed=True)
alive = running(pid) if pid else False
check("F8-CS3 spawn, unconfirmed: a live worker with no lane-open within --ack-wait-s 2 prints detached pid N, unconfirmed after 2 s, exits 4 and is left running",
      rc == 4 and after == "2" and alive and "did not appear within 2 s" in err, "rc %r out %r alive %r" % (rc, out, alive))
announced.append((pid, err))
check("F8-CS6 (finding 2, the swap's timeout path) the caller names its worker on stderr before it waits (codex-lane.py: worker pid N started), the N its outcome line prints, acknowledged and unconfirmed alike, so a caller stopped mid-wait still names the process that may yet start the lane",
      len(announced) == 2 and all(p is not None and ("codex-lane.py: worker pid %d started (log " % p) in e for p, e in announced),
      repr([(p, e[:200]) for p, e in announced]))
if pid:
    stop(pid)
rc, out, err, took = call(spawn_args("C4", 2), "unreadable")
pid, after = pid_of(out, unconfirmed=True)
check("F8-CS4 spawn, unconfirmed: an unreadable record is reported as unreadable (exit 4), never as acknowledged or absent",
      rc == 4 and pid is not None and running(pid) and "cannot be read" in err, "rc %r out %r err %r" % (rc, out, err[-300:]))
if pid:
    stop(pid)
os.chmod(os.path.join(root, "rec-f8c-C4.jsonl"), 0o644)
rc, out, err, took = call(spawn_args("C5", 10, no_wait=False), "refuse")
check("F8-CS5 the waiting form (--detach alone): a worker that exits before acknowledging returns its own code with its log tail and no detached line",
      rc == 2 and out == "" and "a planted worker refusal" in err, "rc %r out %r err %r" % (rc, out, err[-300:]))
record, argv_r = resume_args("R1", 10)
rc, out, err, took = call(argv_r, "ack-resumed", FAKE_WORKER_DELAY=1.0)
pid, log = pid_of(out)
mine = [r for r in rows(record) if r.get("event") == "lane-resumed" and r.get("wrapper_pid") == pid]
check("F8-CR1 resume, acknowledged: exit 0 only after a lane-resumed whose wrapper_pid is the printed worker pid (a 1 s planted delay waited out)",
      rc == 0 and pid is not None and took >= 1.0 and len(mine) == 1, "rc %r out %r took %.2f mine %r" % (rc, out, took, mine))
if pid:
    stop(pid)
record, argv_r = resume_args("R2", 10)
rc, out, err, took = call(argv_r, "refuse")
check("F8-CR2 resume, the worker exits first: exit 2, no detached line, its log tail and the missing lane-resumed named",
      rc == 2 and out == "" and "a planted worker refusal" in err and "exited 2 before writing this call's lane-resumed" in err, "rc %r out %r err %r" % (rc, out, err[-300:]))
record, argv_r = resume_args("R3", 2)
rc, out, err, took = call(argv_r, "silent")
pid, after = pid_of(out, unconfirmed=True)
check("F8-CR3 resume, unconfirmed: a live worker with no lane-resumed within 2 s exits 4, left running",
      rc == 4 and after == "2" and pid is not None and running(pid), "rc %r out %r" % (rc, out))
if pid:
    stop(pid)
record, argv_r = resume_args("R4", 2)
rc, out, err, took = call(argv_r, "other-resumed")
pid, after = pid_of(out, unconfirmed=True)
foreign = [r for r in rows(record) if r.get("event") == "lane-resumed" and r.get("planted")]
check("F8-CR4 resume: a lane-resumed under another wrapper_pid is not this call's acknowledgement (exit 4), and neither is the spawn's own lane-open already on the record",
      rc == 4 and pid is not None and len(foreign) == 1 and foreign[0].get("wrapper_pid") != pid
      and any(r.get("event") == "lane-open" for r in rows(record)), "rc %r out %r foreign %r" % (rc, out, foreign))
if pid:
    stop(pid)
record, argv_r = resume_args("R5", 2)
rc, out, err, took = call(argv_r, "unreadable")
pid, after = pid_of(out, unconfirmed=True)
check("F8-CR5 resume, unconfirmed: an unreadable record is reported as such (exit 4), the worker left running",
      rc == 4 and pid is not None and running(pid) and "cannot be read" in err, "rc %r out %r err %r" % (rc, out, err[-300:]))
if pid:
    stop(pid)
os.chmod(record, 0o644)
F8C_FORCED_OUTCOMES_END
F8CRC=$?
while IFS= read -r line; do
  case "$line" in
    'OK '*) pass "${line#OK }" ;;
    'BAD '*) fail "${line#BAD }" "forced outcome" ;;
    *) printf '%s\n' "$line" ;;
  esac
done < "$T/f8c-forced.log"
if [ "$F8CRC" != 0 ] || [ "$(grep -c '^OK \|^BAD ' "$T/f8c-forced.log")" != 11 ]; then fail "F8 forced outcomes" "PROBE FAILED: the harness exited $F8CRC with $(grep -c '^OK \|^BAD ' "$T/f8c-forced.log") of 11 legs reported"; fi
# Finding 8 (review CR-ADD2): the wrapper's own words match the bounded watch and the acknowledged start. The watch help
# names its bound; the module text no longer says a watch blocks until the close, nor that an acknowledged detached
# resume writes its lane-resumed after it returns, and it names the worker announcement. Control: the same search over a
# planted copy finds both retired phrases.
CXHELP=$( (COLUMNS=4000 "$PY" "$ADAPTER" --help) 2>&1 | tr '\n' ' ' | tr -s ' ')
CXDOC=$("$PY" - "$ADAPTER" <<'CX_DOC_END'
import ast, re, sys
doc = re.sub(r"\s+", " ", ast.get_docstring(ast.parse(open(sys.argv[1], encoding="utf-8").read())) or "")
stale = ("blocks until", "a moment after it returns")
planted = doc + " A watch blocks until the close; a resume writes its line a moment after it returns."
print(sum(p in doc for p in stale), sum(p in planted for p in stale), "bounded by `--max-wait-s`" in doc,
      "an acknowledged one wrote it before returning" in doc, "worker pid N started (log L)" in doc)
CX_DOC_END
)
if [ "$CXDOC" = "0 2 True True True" ] && printf '%s' "$CXHELP" | grep -qF "still-running (exit 8, not a close) after --max-wait-s, 570 s by default, and --max-wait-s 0 waits without bound" \
   && ! printf '%s' "$CXHELP" | grep -qF "block until"; then pass "F8-C07 (finding 8) the watch help states its bound (still-running, exit 8, not a close, after 570 s by default; --max-wait-s 0 for none) and the module text drops 'blocks until' and 'a moment after it returns' while naming the worker announcement (control: a planted copy hits both phrases)"; else fail "F8-C07 the restatements" "[$CXDOC] $(printf '%s' "$CXHELP" | grep -o 'watch  *wait.\{0,160\}' | head -1)"; fi

# 21 a spawn onto a closed run warns and proceeds (register 2026-09-03): a run-close with no later
# run-open or run-resume, whatever else follows it; a run-resume after the close clears it
RCREC="$T/runclosed.jsonl"
printf '%s\n' '{"ts": "2026-09-13T01:38:20+0100", "run": "run-rc", "event": "run-open"}' '{"ts": "2026-09-13T01:38:21+0100", "run": "run-rc", "event": "run-close"}' '{"ts": "2026-09-13T03:42:43+0100", "run": "run-rc", "event": "observation", "what": "a note after the close"}' > "$RCREC"
out="$("$PY" "$ADAPTER" spawn --run run-rc --lane RC1 "${COMMON[@]}" --record "$RCREC" --dry-run 2>&1)"; rc=$?
rclines=$(grep -c . "$RCREC")
printf '%s\n' '{"ts": "2026-09-13T03:50:00+0100", "run": "run-rc", "event": "run-resume", "session": "s2"}' >> "$RCREC"
out2="$("$PY" "$ADAPTER" spawn --run run-rc --lane RC2 "${COMMON[@]}" --record "$RCREC" --dry-run 2>&1)"; rc2=$?
if [ $rc -eq 0 ] && [ "$rclines" = 3 ] && printf '%s' "$out" | grep -q "codex-lane.py: warning: run run-rc is closed: its run-close at 2026-09-13T01:38:21+0100 has no later run-open or run-resume (1 event(s) since)" \
   && [ $rc2 -eq 0 ] && ! printf '%s' "$out2" | grep -q 'is closed: its run-close'; then pass "a spawn onto a closed run warns and proceeds with an observation after the close (the dry run adds no line); a run-resume after the close clears it"; else fail "the closed-run warning" "rc=$rc/$rc2 lines=$rclines $out"; fi

# 22 a brief carrying a doubled root is refused before any record line (register 2026-09-09 19:03)
printf 'Append the ledger at /%s/example/.llm-/%s/example/demo/wiki/run.jsonl\n' Users Users > "$T/brief-dbl.md"
"$PY" "$ADAPTER" spawn --run run-suite --lane DB1 --codex "$T/bin/codex" --class critic --brief "$T/brief-dbl.md" --cwd "$T/work" --reason "(a) suite" --choice-reason "suite pick" --delegation single --delegation-src head --viewer none --dry-run >"$T/dbl.out" 2>"$T/dbl.err"; rc=$?
if [ $rc -eq 2 ] && grep -q 'line 1 carries a doubled root' "$T/dbl.err" && [ "$(count "$REC" DB1 lane-open)" = 0 ]; then pass "a brief carrying a doubled root is refused (exit 2, the line named, no record line)"; else fail "the doubled-root refusal" "rc=$rc $(cat "$T/dbl.err")"; fi
printf 'Append the ledger at ~/.llm-/%s/example/demo/wiki/run.jsonl\n' Users > "$T/brief-dbl2.md"
"$PY" "$ADAPTER" spawn --run run-suite --lane DB2 --codex "$T/bin/codex" --class critic --brief "$T/brief-dbl2.md" --cwd "$T/work" --reason "(a) suite" --choice-reason "suite pick" --delegation single --delegation-src head --viewer none --dry-run >"$T/dbl2.out" 2>"$T/dbl2.err"; rc=$?
if [ $rc -eq 2 ] && grep -q 'line 1 carries a doubled root' "$T/dbl2.err" && [ "$(count "$REC" DB2 lane-open)" = 0 ]; then pass "a brief whose doubled root has a ~ lead is refused the same way (the property, not a home lead)"; else fail "the ~-led doubled-root refusal" "rc=$rc $(cat "$T/dbl2.err")"; fi

# 16 every record line parses (the whole file, json.loads per line)
if "$PY" -c "
import json,sys
n=0
for l in open('$REC'):
    l=l.strip()
    if l: json.loads(l); n+=1
print(n); sys.exit(0 if n>=20 else 1)" >/dev/null; then pass "record parses"; else fail "record parses" "a line failed json.loads"; fi

# Casefold collision fold: fixtures use only the existing stub and temporary root.
"$PY" - "$ADAPTER" "$T" <<'CASEFOLD_GUARD_SUITE_END' > "$T/casefold-guards.log" 2>&1
import contextlib, hashlib, importlib.util, inspect, io, json, os, pathlib, re, subprocess, sys
from unittest import mock
script, parent = map(pathlib.Path, sys.argv[1:3])
root=parent / "casefold-guards"; root.mkdir()
(root / "work").mkdir(); (root / "source").mkdir()
(root / "source" / "data.txt").write_text("original stage bytes\n")
(root / "brief.md").write_text("Fixture brief.\nCONTROL+: LANE CORE in %s\n" % (script.parent / "templates" / "lane-core.md"))
(root / "follow.md").write_text("Distinct follow-up brief.\n")
os.environ["LLM_WIKI_STORE"]=str(root / "store")
os.environ["STUB_REPORT"]="fixture retained report"
os.environ["CODEX_SHIM_MODE"]="ok"
spec=importlib.util.spec_from_file_location("casefold_wrapper",script)
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
CODEX = True
core=adapter.lane if CODEX else adapter
label="C" if CODEX else "L"
if CODEX:
    common=["--codex",parent / "bin" / "codex","--class","critic","--stage-from",root / "source","--stage-writable",
            "--choice-reason","fixture","--delegation","single","--delegation-src","head"]
else:
    routing,home,projects=map(pathlib.Path,sys.argv[3:])
    common=["--class","verifier","--home",home,"--routing",routing,"--projects-root",projects,
            "--expect-usd","2","--grants-only","--grant",root]
common += ["--brief",root / "brief.md","--reason","(a) casefold fixture","--viewer","none","--silence-s","0"]
def check(number, name, condition):
    print(("OK " if condition else "BAD ")+"FOLD1-"+label+number+" "+name,flush=True)
def invoke(args, legacy=False):
    args=list(map(str,args))
    if not legacy:
        p=subprocess.run([sys.executable,str(script)]+args,text=True,capture_output=True)
        return p.returncode,p.stdout,p.stderr
    # Plant a conflicting identity: only the suffix validator is disabled for this fixture.
    out,err=io.StringIO(),io.StringIO()
    with mock.patch.object(core,"require_lane_id"),contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
        try: rc=adapter.cmd_spawn(adapter.build_parser().parse_args(args))
        except SystemExit as exc: rc=exc.code
    return rc,out.getvalue(),err.getvalue()
def spawn(run, identifier="B", extra=(), legacy=False):
    return invoke(["spawn","--run",run,"--lane",identifier]+common+list(extra),legacy)
def resume(run, identifier="B"):
    args=["resume","--run",run,"--lane",identifier,"--brief",root / "follow.md","--viewer","none","--silence-s","0"]
    if CODEX: args += ["--codex",parent / "bin" / "codex","--stage-from",root / "source","--delegation","single","--delegation-src","head"]
    else: args += ["--home",home,"--projects-root",projects]
    return invoke(args)
def manifest():
    return {str(p.relative_to(root)):("link",os.readlink(p)) if p.is_symlink() else
            ("file",hashlib.sha256(p.read_bytes()).hexdigest()) if p.is_file() else ("directory",)
            for p in root.rglob('*') if not (
                (p.is_dir() and p.name.endswith('.jsonl.a3')) or
                (p.parent.name.endswith('.jsonl.a3') and re.fullmatch(r'[0-9a-f]{64}\.lock',p.name)
                 and p.is_file() and p.stat().st_size == 0))}
# A3 semantic migration: E1 retains stable, empty lifetime gates even after a rejected
# preflight. Their presence is permitted; every content-bearing file remains in the manifest.
lock_control=root / "manifest-control.jsonl.a3"
lock_control.mkdir()
lock_file=lock_control / ("f"*64+".lock")
manifest_before=manifest()
lock_file.touch()
empty_lock_ignored=manifest()==manifest_before
lock_file.write_text("planted unexpected gate payload")
check("A3","only empty lifetime-lock metadata is exempt; planted bytes are detected",
      empty_lock_ignored and manifest()!=manifest_before)
lock_file.unlink();lock_control.rmdir()
def pointers(run):
    record=pathlib.Path(adapter.store_paths(run,"B")["record"])
    events=[json.loads(line) for line in record.read_text().splitlines()]
    return {e[key]:pathlib.Path(e[key]).read_bytes() for e in events for key in
            ("report","prompt_file" if CODEX else "brief_copy") if e.get(key)}
def intact(saved):return all(pathlib.Path(p).read_bytes()==body for p,body in saved.items())
run="fixture-case-forward"
rc,out,err=spawn(run);check("01","spawn B control",rc==0)
rc,out,err=resume(run);check("02","resume B control",rc==0)
saved=pointers(run)
for identifier in ("B-pass2","B-pass02","b-PASS3","B-PaSs02"):
    for flags in ((),("--dry-run",),("--detach","--no-wait")):
        before=manifest();rc,out,err=spawn(run,identifier,flags)
        check("03","reserved %s %s preserves all pointers" % (identifier,flags),rc==2
              and "reserved per-pass suffix" in err and identifier in err and not out
              and before==manifest() and intact(saved))
for identifier in ("B","b"):
    before=manifest();rc,out,err=spawn(run,identifier,("--detach","--no-wait"))
    check("04","recorded identity %s refuses before writes or staging" % identifier,rc==2
          and "case-equivalent to existing lane" in err and before==manifest() and intact(saved) and not out)
rc,out,err=spawn(run,"Fresh");check("05","fresh identity spawns and old pointers remain intact",rc==0 and intact(saved))
rc,out,err=spawn(run,"DetachedFresh",("--detach",))
check("05","fresh detached identity spawns and old pointers remain intact",rc==0 and intact(saved))
run="fixture-case-reverse"
rc,out,err=spawn(run,"B-PASS2",legacy=True)
check("06","planted spawn B-PASS2 planted by disabling only suffix validation",rc==0)
rc,out,err=spawn(run);check("07","spawn B after planted B-PASS2 control",rc==0)
saved=pointers(run);before=manifest();rc,out,err=resume(run)
check("08","resume B refuses case-equivalent legacy destination and preserves pointers",rc==2
      and "per-pass path already exists" in err and "case-equivalent destination" in err
      and before==manifest() and intact(saved) and not out)
# Every spawn-owned destination, with the record absent, including non-regular entries.
run="fixture-case-destinations"
paths=adapter.store_paths(run,"Target")
keys=("report","prompt","input_dir","events","stderr","detach_log") if CODEX else ("report","appended","definition_copy","settings","input_dir","detach_log")
destinations=[(key,pathlib.Path(paths[key])) for key in keys]
if CODEX:destinations.append(("stage",pathlib.Path(paths["store"]) / (run+"-cwd-Target")))
for key,target in destinations:
    target=target.with_name(target.name.upper())
    for shape in ("file","directory","dangling-link"):
        if shape=="file":target.write_text("pre-existing owner bytes\n")
        elif shape=="directory":target.mkdir()
        else:target.symlink_to(root / "missing-target")
        before=manifest();rc,out,err=spawn(run,"Target",("--detach","--no-wait"))
        check("09","%s %s refuses before record, worker or stage refresh" % (key,shape),rc==2
              and "per-pass path already exists" in err and str(target) in err
              and before==manifest() and not out)
        if shape=="directory":target.rmdir()
        else:target.unlink()
# A record collision must refuse even when there are no destination artefacts to detect.
record=pathlib.Path(paths["record"])
record.write_text(json.dumps({"event":"lane-open","lane":"RecordOnly"})+'\n')
before=manifest();rc,out,err=spawn(run,"recordonly")
check("10","record-only casefold collision refuses",rc==2 and "case-equivalent to existing lane" in err and before==manifest())
for text in ('{torn\n','[]\n'):
    record.write_text(text);before=manifest();rc,out,err=spawn(run,"Unused")
    check("11","broken record refuses with a named premise",rc==2 and "PROBE FAILED:" in err
          and ("cannot check lane ids" in err or "damaged record row" in err) and before==manifest())
for state in ("empty","missing"):
    if state=="empty":record.write_text("")
    else:record.unlink()
    # Ordinary spawns also prove the empty/missing record is a valid premise.
    rc,out,err=spawn(run,"Valid-"+state)
    check("12",state+" record accepts a fresh identity",rc==0)
# Simulated listings exercise the guard independently of the host's case behaviour.
def guarded(fn,*args):
    err=io.StringIO()
    with contextlib.redirect_stderr(err):
        try: fn(*args);return 0,err.getvalue()
        except SystemExit as exc:return exc.code,err.getvalue()
for listing,want in ((["REPORT-B-PASS2.MD"],2),(["unrelated.md"],0),([],0)):
    with mock.patch.object(core.os,"listdir",return_value=listing):
        rc,err=guarded(core.require_absent_paths,[str(root / "report-B-pass2.md")])
    check("13","case-sensitive listing control %r" % listing,rc==want and (want==0 or "case-equivalent" in err))
for error,want in ((FileNotFoundError("missing parent"),0),(PermissionError("unreadable parent"),2),(NotADirectoryError("parent is a file"),2)):
    with mock.patch.object(core.os,"listdir",side_effect=error):
        rc,err=guarded(core.require_absent_paths,[str(root / "absent.md")])
    check("14","directory premise %s" % type(error).__name__,rc==want and (want==0 or "PROBE FAILED:" in err))
with mock.patch("builtins.open",side_effect=PermissionError("unreadable record")):
    rc,err=guarded(core.require_new_lane_id,"B",str(record))
check("15","unreadable record refuses",rc==2 and "cannot check lane ids" in err)
# Current critic folds: dry preflight ownership and the compatible pass namespace.
def fold_check(finding, number, name, condition):
    print(("OK " if condition else "BAD ")+"P2-"+finding+"-"+label+number+" "+name,flush=True)
def events(run):
    path=pathlib.Path(adapter.store_paths(run,"B")["record"])
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
def stage_path(run, identifier):
    paths=adapter.store_paths(run,identifier)
    return pathlib.Path(paths["store"]) / (run+"-cwd-"+identifier) if CODEX else pathlib.Path(paths["input_dir"])
run="fixture-preflight"
before=manifest();rc,out,err=spawn(run,"Dry",("--dry-run",))
fold_check("STAGE","01","fresh dry run leaves no directory or record",rc==0 and before==manifest()
           and not stage_path(run,"Dry").exists() and not events(run))
rc,out,err=spawn(run,"Dry")
fold_check("STAGE","02","same-id execution after dry run succeeds with one lane-open",rc==0
           and sum(e.get("event")=="lane-open" for e in events(run))==1)
run="fixture-empty-stage"
target=stage_path(run,"Empty");target.mkdir();before=manifest()
rc,out,err=spawn(run,"Empty")
if CODEX:
    fold_check("STAGE","03","exact empty stage is reusable",rc==0
               and sum(e.get("event")=="lane-open" for e in events(run))==1)
else:
    fold_check("STAGE","03","Claude empty input directory remains an artefact",rc==2
               and "per-pass path already exists" in err and before==manifest() and not events(run))
    target.rmdir()
for shape in ("non-empty-directory","file","dangling-link","directory-link","case-equivalent-empty"):
    run="fixture-stage-refusal-"+shape;target=stage_path(run,"Blocked")
    if shape=="non-empty-directory":target.mkdir();(target / "owned.txt").write_text("retained\n")
    elif shape=="file":target.write_text("retained\n")
    elif shape=="dangling-link":target.symlink_to(root / "absent-stage-link")
    elif shape=="directory-link":target.symlink_to(root / "work",target_is_directory=True)
    else:target=target.with_name(target.name.upper());target.mkdir()
    before=manifest();rc,out,err=spawn(run,"Blocked")
    fold_check("STAGE","04",shape+" refuses without modification",rc==2
               and "per-pass path already exists" in err and str(target) in err and not out
               and before==manifest() and not events(run))
run="fixture-stage-report-owner";paths=adapter.store_paths(run,"Blocked")
target=stage_path(run,"Blocked");target.mkdir()
report=pathlib.Path(paths["report"]);report.write_text("original report pointer\n")
before=manifest();rc,out,err=spawn(run,"Blocked")
fold_check("STAGE","05","existing report still refuses beside an empty directory",rc==2
           and str(report) in err and before==manifest() and not events(run))
run="fixture-failed-preflight";empty_brief=root / "empty-brief.md";empty_brief.write_text("")
before=manifest();rc,out,err=spawn(run,"Retry",("--brief",empty_brief,"--dry-run"))
fold_check("STAGE","06","failed dry preflight releases its empty directory",rc==2
           and "brief file is empty" in err and before==manifest() and not events(run))
rc,out,err=spawn(run,"Retry")
fold_check("STAGE","07","valid retry after failed preflight succeeds once",rc==0
           and sum(e.get("event")=="lane-open" for e in events(run))==1)
# The shared helper allows only explicitly named exact empty stages, in both adapters.
empty_stage=root / "helper-empty-stage";empty_stage.mkdir();before=manifest()
rc,err=guarded(core.require_absent_paths,[str(empty_stage)],[str(empty_stage)])
rc2,err2=guarded(core.require_absent_paths,[str(empty_stage)])
fold_check("STAGE","08","empty-stage opt-in passes and ordinary empty directory refuses",rc==0 and rc2==2
           and "per-pass path already exists" in err2 and before==manifest())
real_listdir=core.os.listdir
for failure in (PermissionError("unreadable empty-stage contents"),NotADirectoryError("stage changed type")):
    def listing(path):
        if os.path.abspath(path)==str(empty_stage):raise failure
        return real_listdir(path)
    with mock.patch.object(core.os,"listdir",side_effect=listing):
        rc,err=guarded(core.require_absent_paths,[str(empty_stage)],[str(empty_stage)])
    fold_check("STAGE","09","empty-stage premise "+type(failure).__name__,rc==2
               and "cannot check empty stage directory" in err and before==manifest())
for failure in (PermissionError("unreadable stage metadata"),FileNotFoundError("stage vanished")):
    with mock.patch.object(core.os,"lstat",side_effect=failure):
        rc,err=guarded(core.require_absent_paths,[str(empty_stage)],[str(empty_stage)])
    fold_check("STAGE","10","stage metadata premise "+type(failure).__name__,rc==2
               and "cannot check empty stage directory" in err and before==manifest())
for names in ([empty_stage.name,empty_stage.name.upper()],[empty_stage.name.upper(),empty_stage.name]):
    def listing(path):
        return names if os.path.abspath(path)==str(root) else real_listdir(path)
    with mock.patch.object(core.os,"listdir",side_effect=listing):
        rc,err=guarded(core.require_absent_paths,[str(empty_stage)],[str(empty_stage)])
    fold_check("STAGE","11","exact empty stage cannot hide a second case-equivalent entry",rc==2
               and "case-equivalent destination" in err and before==manifest())
if CODEX:
    run="fixture-cleanup-premise";target=stage_path(run,"Cleanup")
    original_rmdir=adapter.os.rmdir
    def deny_final_cleanup(path,*args,**kwargs):
        if os.path.abspath(path)==str(target) and not kwargs:
            raise PermissionError("fixture cleanup denial")
        return original_rmdir(path,*args,**kwargs)
    args=adapter.build_parser().parse_args(list(map(str,["spawn","--run",run,"--lane","Cleanup"]+common+["--dry-run"])))
    with mock.patch.object(adapter.os,"rmdir",side_effect=deny_final_cleanup):
        rc,err=guarded(adapter.cmd_spawn,args)
    fold_check("STAGE","12","cleanup failure is a named exit-2 premise without a record",rc==2
               and "cannot remove empty dry-run stage" in err and "fixture cleanup denial" in err
               and target.is_dir() and not list(target.iterdir()) and not events(run))
    rc,out,err=spawn(run,"Cleanup")
    fold_check("STAGE","13","retry reuses an interrupted empty stage",rc==0
               and sum(e.get("event")=="lane-open" for e in events(run))==1)
run="fixture-compatible-identities"
for identifier in ("B-R1","CRIT-R6","LV-r0","LV-r1","LV-r2","LV-r3","B-resume-1","B-ReSuMe-02"):
    rc,out,err=spawn(run,identifier)
    fold_check("SUFFIX","01",identifier+" spawns",rc==0)
    saved=pointers(run);rc,out,err=resume(run,identifier)
    latest=next((e for e in reversed(events(run)) if e.get("event")=="lane-closed" and e.get("lane")==identifier),{})
    start=next((e for e in reversed(events(run)) if e.get("event")=="lane-resumed" and e.get("lane")==identifier),{})
    key="prompt_file" if CODEX else "brief_copy"
    fold_check("SUFFIX","02",identifier+" resumes with pass2 pointers",rc==0 and intact(saved)
               and str(latest.get("report","")).endswith("-report-"+identifier+"-pass2.md")
               and str(start.get(key,"")).endswith("-"+identifier+"-pass2.md"))
# A lower-case planted pass identity exercises the other collision spelling too.
run="fixture-case-reverse-lower"
rc,out,err=spawn(run,"B-pass2",legacy=True)
fold_check("SUFFIX","03","planted B-pass2 first completes",rc==0)
rc,out,err=spawn(run);saved=pointers(run);before=manifest()
rc2,out2,err2=resume(run)
fold_check("SUFFIX","04","B resume refuses lower-case planted pass and retains pointers",rc==0 and rc2==2
           and "per-pass path already exists" in err2 and before==manifest() and intact(saved))
# The read-only guard helpers cannot mutate their inputs, with both controls on this run.
record.write_text(json.dumps({"event":"lane-open","lane":"Present"})+'\n')
before=manifest()
for p in root.rglob('*'):
    if p.is_file() and not p.is_symlink():p.chmod(0o444)
for p in root.rglob('*'):
    if p.is_dir() and not p.is_symlink():p.chmod(0o555)
root.chmod(0o555)
rc,err=guarded(core.require_new_lane_id,"Absent",str(record))
rc2,err2=guarded(core.require_absent_paths,[str(root / "unused.md")])
check("16","guard checks leave read-only-copy checksum manifest unchanged",rc==rc2==0 and before==manifest() and bool(before))
record.chmod(0o644);record.write_text(record.read_text()+'\n')
check("17","manifest positive control catches a planted byte",before!=manifest())
write_pattern=re.compile(r'\b(?:write_atomic|append_record|write_text|write_bytes|unlink|remove|rename|replace|mkdir|makedirs|rmdir|rmtree|copyfile)\(|open\([^\n]*,[ ]*[\"\x27][wax]')
source='\n'.join(inspect.getsource(getattr(core,name)) for name in ("require_new_lane_id","require_absent_paths"))
check("18","write-source grep zero with planted write control",not write_pattern.search(source)
      and bool(write_pattern.search('write_atomic(path, text)')) and bool(write_pattern.search('os.rmdir(path)'))
      and not write_pattern.search('read_text(path)'))
CASEFOLD_GUARD_SUITE_END
CASE_RC=$?
while IFS= read -r line; do
  case "$line" in
    'OK '*) pass "${line#OK }" ;;
    'BAD '*) fail "${line#BAD }" "casefold assertion" ;;
    *) printf '%s\n' "$line" ;;
  esac
done < "$T/casefold-guards.log"
if [ "$CASE_RC" != 0 ]; then fail "casefold guard premise" "exit $CASE_RC"; fi

# W2 containment: read-only code, brief and record copies stay byte-identical under dry resume.
CONTAIN=$("$PY" - "$ADAPTER" "$T" <<'CODEX_CONTAINMENT_END'
import hashlib, importlib.util, json, os, pathlib, re, shutil, subprocess, sys
source,root=map(pathlib.Path,sys.argv[1:])
spec=importlib.util.spec_from_file_location("contain_adapter",source)
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
paths=adapter.store_paths("fixture-reports","P")
copy=root / "read-only-copy";copy.mkdir()
for p in (source,source.with_name("lane.py"),root / "follow.md",pathlib.Path(paths["record"])):
    shutil.copy2(p,copy / p.name)
def manifest():
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in copy.iterdir() if p.is_file()}
before=manifest()
for p in copy.iterdir():p.chmod(0o444)
copy.chmod(0o555)
# The copied adapter sits in a temp directory, so its own three-levels-up vault lookup finds no
# class definitions; the vault is passed explicitly (the environment wins, else the real adapter's
# vault, else the flat-stage root), the way lane.vault_root() reads it (in-place run, 2026-09-16).
vault_env=os.environ.get("CLAUDE_PROJECT_DIR") or next((str(c) for c in (source.resolve().parents[3],source.resolve().parents[2])
                                                          if (c / ".claude" / "agents" / "critic.md").is_file()),str(source.resolve().parents[3]))
result=subprocess.run([sys.executable,str(copy / source.name),"resume","--run","fixture-reports","--lane","P",
                       "--record",str(copy / pathlib.Path(paths["record"]).name),"--brief",str(copy / "follow.md"),
                       "--codex",str(root / "bin" / "codex"),"--delegation","single","--delegation-src","head",
                       "--viewer","none","--dry-run"],text=True,capture_output=True,
                      env=dict(os.environ,CLAUDE_PROJECT_DIR=vault_env))
assert result.returncode==0,(result.stdout,result.stderr)
assert before==manifest() and len(before)==4
copy.chmod(0o755);p=copy / "follow.md";p.chmod(0o644);p.write_text("control changed byte\n")
assert before!=manifest()
pattern=re.compile(r'\b(?:write_atomic|append_record)\(')
assert pattern.search(source.read_text()) and pattern.search('write_atomic(path, text)')
assert not pattern.search('read_text(path)')
print("unchanged 4 files; manifest control hit; write-source control hit; read-only source control zero")
CODEX_CONTAINMENT_END
); rc=$?
if [ "$rc" = 0 ]; then pass "W2-C05 $CONTAIN"; else fail "W2-C05 containment" "$CONTAIN"; fi
# Background wait: accelerated clock, real record reads, inherited watch results and no-write controls.
echo "== wait =="
"$PY" - "$ADAPTER" "$T" >"$T/wait-cases.log" 2>&1 <<'WAIT_SUITE_END'
import builtins, contextlib, hashlib, importlib.util, inspect, io, json, os
import pathlib, re, shutil, subprocess, sys, time, types
from unittest.mock import patch

source, parent = map(pathlib.Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location("wait_suite", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
codex = source.name == "codex-lane.py"
core = module.lane if codex else module
root = parent / "wait-cases"
root.mkdir()
os.environ["LLM_WIKI_STORE"] = str(root / "store")
os.environ["LLM_WIKI_PROGRESS_DIR"] = str(root / "progress")
record = root / "record.jsonl"
report = root / "report.md"
report.write_text("LATEST-PASS-REPORT\n")
old_report = root / "old-report.md"
old_report.write_text("EARLIER-PASS-REPORT\n")
session = "fixture-wait-session"
base = {"run": "fixture-wait", "lane": "W", "session_id": session}
opened = dict(base, event="lane-open", model="gpt-6-astra" if codex else "opus",
              effort="xhigh", **{"class": "verifier"}, cwd=str(root),
              projects_root=str(root / "projects"))
spawned = dict(base, event="lane-spawned", pid=os.getpid(), wrapper_pid=os.getpid())
def close(kind="completed", path=report):
    return dict(base, event="lane-closed", exit_class=kind,
                exit_code=core.EXIT_CODES.get(kind, 3), report=str(path))
def seed(rows):
    record.write_text("".join(json.dumps(row) + "\n" for row in rows))
def append(row):
    with record.open("a") as handle:
        handle.write(json.dumps(row) + "\n")
def check(name, condition, detail=""):
    print(("OK " if condition else "BAD ") + "WAIT " + name + (": " + detail if detail else ""))

class Clock:
    # Two simulated seconds replace 570 (scale 285:1); no production timing changes.
    bound = 2
    poll = 1
    def __init__(self, events=()):
        self.elapsed = 0
        self.epoch = time.time()
        self.events = list(events)
        # A missing close fails promptly; allowance is set by judgement, unmeasured.
        self.ceiling = 20
    def time(self):
        return self.epoch + self.elapsed
    def sleep(self, seconds):
        self.elapsed += seconds
        if self.elapsed > self.ceiling:
            raise AssertionError("wait missed its fixture close or named error")
        while self.events and self.events[0][0] <= self.elapsed:
            _, action = self.events.pop(0)
            action()

def invoke(command, clock=None, extra=()):
    args = [str(source), command, "--run", base["run"], "--lane", base["lane"],
            "--record", str(record), "--appear-s", "0", "--poll-s", str(Clock.poll), *extra]
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(sys, "argv", args))
        stack.enter_context(contextlib.redirect_stdout(stdout))
        stack.enter_context(contextlib.redirect_stderr(stderr))
        if clock is not None:
            fake = types.SimpleNamespace(time=clock.time, sleep=clock.sleep, strftime=time.strftime)
            stack.enter_context(patch.object(core, "time", fake))
            if module is not core:
                stack.enter_context(patch.object(module, "time", fake))
            stack.enter_context(patch.object(core, "WATCH_MAX_WAIT_S", Clock.bound))
        try:
            code = module.main()
        except SystemExit as exc:
            code = exc.code
    return code, stdout.getvalue(), stderr.getvalue()

check("default watch bound control", core.WATCH_MAX_WAIT_S == 570)
seed([opened, spawned])
args = module.build_parser().parse_args(["wait", "--run", base["run"], "--lane", base["lane"]])
bad = invoke("wait", extra=("--max-wait-s", "1"))
check("wait has no time-bound option", args.max_wait_s == 0 and bad[0] == 2
      and "unrecognized arguments: --max-wait-s" in bad[2])

for kind in ("completed", "stall", "killed", "limit"):
    results = []
    for command in ("watch", "wait"):
        seed([opened, spawned])
        clock = Clock([(Clock.poll, lambda: append(close(kind)))])
        results.append(invoke(command, clock))
    expected = core.EXIT_CODES.get(kind, 3) if codex else 0
    check(kind + " close matches watch output and exit", results[0] == results[1]
          and results[1][0] == expected and " · " + kind + " · " in results[1][1]
          and "LATEST-PASS-REPORT" in results[1][1], "exit %s" % results[1][0])

seed([opened, spawned, close()])
watch, wait = invoke("watch"), invoke("wait")
check("already-closed lane matches watch", watch == wait and wait[0] == 2
      and "already closed" in wait[2] and "LATEST-PASS-REPORT" in wait[1])
seed([opened, spawned, close()])
result = invoke("wait", extra=("--lane", "UNKNOWN"))
check("unknown lane is named", result[0] == 2 and "is unknown" in result[2])
result = invoke("wait", extra=("--record", str(root / "missing.jsonl")))
check("unknown record is named", result[0] == 2 and "no " in result[2]
      and "record at" in result[2])

# Append at EOF inside the real record reader, after it obtained its running snapshot.
seed([opened, spawned])
real_open = builtins.open
race_hit = []
class RacingReader:
    def __init__(self, handle):
        self.handle = handle
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        self.handle.close()
    def __iter__(self):
        for line in self.handle:
            yield line
        if not race_hit:
            race_hit.append(True)
            append(close())
def racing_open(path, mode="r", *args, **kwargs):
    handle = real_open(path, mode, *args, **kwargs)
    return RacingReader(handle) if str(path) == str(record) and mode == "r" else handle
with patch.object(builtins, "open", racing_open):
    result = invoke("wait", Clock())
check("record race: close appended during read", race_hit == [True] and result[0] == 0
      and "LATEST-PASS-REPORT" in result[1])

seed([opened, spawned])
encoded = json.dumps(close()) + "\n"
split = len(encoded) // 2
with record.open("a") as handle:
    handle.write(encoded[:split])
def finish_line():
    with record.open("a") as handle:
        handle.write(encoded[split:])
result = invoke("wait", Clock([(Clock.poll, finish_line)]))
check("torn close retried until complete", result[0] == 0 and "LATEST-PASS-REPORT" in result[1])

resumed = dict(base, event="lane-resumed", wrapper_pid=os.getpid())
respawned = dict(spawned, event="lane-respawned")
for pending in (False, True):
    seed([opened, spawned, close(path=old_report)] + ([] if pending else [resumed, respawned]))
    def resume():
        append(resumed)
        append(respawned)
    events = ([(Clock.poll, resume)] if pending else []) + [(2 * Clock.poll, lambda: append(close("limit")))]
    clock = Clock(events)
    result = invoke("wait", clock, ("--appear-s", str(2 * Clock.poll)))
    check("pending detached resume" if pending else "latest resumed pass only",
          result[0] == (6 if codex else 0) and clock.elapsed >= 2 * Clock.poll
          and "LATEST-PASS-REPORT" in result[1] and "EARLIER-PASS-REPORT" not in result[1])

# Both commands observe the SAME running record. The later close is four test bounds away,
# so watch returns first and wait itself must remain attached longer than one old bound.
seed([opened, spawned])
clock = Clock([(4 * Clock.bound, lambda: append(close()))])
watch = invoke("watch", clock)
after_watch = clock.elapsed
no_close = not any(row.get("event") == "lane-closed" for row in core.load_record(str(record)))
wait = invoke("wait", clock)
check("past old bound: watch still-running, wait later close", watch[0] == 8
      and "still-running" in watch[1] and no_close and wait[0] == 0
      and "LATEST-PASS-REPORT" in wait[1] and "still-running" not in wait[1]
      and clock.elapsed - after_watch > Clock.bound,
      "watch at %s; wait at %s; bound %s simulated seconds" % (after_watch, clock.elapsed, Clock.bound))

seed([opened, spawned])
if not codex:
    transcript = root / "projects" / core.dashed(str(root)) / (session + ".jsonl")
    transcript.parent.mkdir(parents=True)
    transcript.write_text(json.dumps({"type": "assistant", "message": {
        "content": [{"type": "text", "text": "ORPHAN-REPORT"}], "usage": {}}}) + "\n")
with patch.object(core, "pid_alive", return_value=False):
    result = invoke("wait", Clock())
rows = core.load_record(str(record))
if codex:
    check("orphaned wrapper named without writes", result[0] == 3
          and "orphaned:" in result[1] and "wrapper pid" in result[1] and rows == [opened, spawned])
else:
    check("legacy orphan requires explicit reconciliation without a close", result[0] == 3
          and "orphaned:" in result[1] and "explicit head reconciliation" in result[1]
          and rows == [opened, spawned])

if not codex:
    seed([opened, spawned])
    with patch.object(core, "silence_of", return_value=(2, "silent", 1)), \
            patch.object(core, "kill_pid_group", side_effect=lambda pid: append(close("stall"))) as kill:
        result = invoke("wait", Clock(), ("--silence-s", "1"))
    check("explicit silence threshold returns stall", result[0] == 5
          and kill.call_args.args == (spawned["pid"],)
          and any(row.get("event") == "stall" for row in core.load_record(str(record))))

# Subcommand help itself names the fresh hand-off and the two exceptions.
with patch.object(sys, "argv", [str(source), "resume", "--help"]), \
        contextlib.redirect_stdout(io.StringIO()) as help_output:
    try:
        module.main()
    except SystemExit as exc:
        assert exc.code == 0
help_text = " ".join(help_output.getvalue().split())
policy = ("fresh helper", "compact hand-off", "usage limit", "on disk and checked", "panel's round 2")
check("resume help names fresh helper and both exceptions", help_text.startswith("usage:")
      and "--brief BRIEF" in help_text and all(word in help_text for word in policy))
if not codex:
    seed([opened, spawned, close()])
    args = module.build_parser().parse_args(["advise", "--run", base["run"], "--lane", base["lane"],
                                           "--record", str(record)])
    with contextlib.redirect_stdout(io.StringIO()) as advice:
        code = module.cmd_advise(args)
    text = advice.getvalue()
    check("completed advice: fresh helper, compact hand-off, both exceptions", code == 0
          and text.startswith("advise: restart") and all(word in text for word in policy)
          and all(word in text for word in ("report's path", "findings to fold", "held files", "must not change"))
          and "inside its window for a follow-up" not in text)

# Last legs: actual CLI calls on a read-only copy; no mock can hide a write here.
readonly = root / "readonly"
readonly.mkdir()
for path in {source, source.with_name("lane.py")}:
    shutil.copy2(path, readonly / path.name)
copied_report = readonly / "report.md"
shutil.copy2(report, copied_report)
copied_record = readonly / "record.jsonl"
copied_record.write_text("".join(json.dumps(row) + "\n" for row in [opened, spawned, close(path=copied_report)]))
def manifest():
    return {str(path.relative_to(readonly)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in readonly.rglob("*") if path.is_file()}
before = manifest()
for path in readonly.iterdir():
    path.chmod(0o444)
readonly.chmod(0o555)
result = subprocess.run([sys.executable, "-B", str(readonly / source.name), "wait", "--run", base["run"],
                         "--lane", base["lane"], "--record", str(copied_record), "--appear-s", "0", "--format", "json"],
                        capture_output=True, text=True, timeout=10)  # ceiling set by judgement, unmeasured
payload = json.loads(result.stdout)
check("read-only copy: zero checksum changes", result.returncode == 2 and bool(before)
      and before == manifest() and (payload if codex else payload["close"])["exit_class"] == "completed",
      "%d files" % len(before))
copied_record.chmod(0o644)
with copied_record.open("a") as handle:
    handle.write("\n")
check("checksum positive control catches planted byte", before != manifest())
pattern = re.compile(r'\b(?:write_atomic|append_record|write_text|write_bytes|unlink|remove|rename|replace|mkdir|makedirs|rmdir|rmtree|copyfile)\(|open\([^\n]*,[ ]*[\"\x27][wax]')
check("new wait entry point write-source grep zero", not pattern.search(inspect.getsource(module.cmd_wait))
      and bool(pattern.search('append_record(path, row)')) and bool(pattern.search('open(path, "w")'))
      and not pattern.search('load_record(path)'))
WAIT_SUITE_END
WAIT_RC=$?
while IFS= read -r line; do
  case "$line" in
    'OK '*) pass "${line#OK }" ;;
    'BAD '*) fail "${line#BAD }" "wait assertion" ;;
    *) printf '%s\n' "$line" ;;
  esac
done < "$T/wait-cases.log"
if [ "$WAIT_RC" != 0 ]; then fail "PROBE FAILED: wait suite exited $WAIT_RC" "wait premise"; fi

# AW-C · the keep-awake process beside each codex process (owner decision of 2026-10-09; lane.py's
#        "Keeping the host awake", through lane.start_awake). A stand-in takes /usr/bin/caffeinate's
#        place through AIMYTH_CAFFEINATE: one line per start (its pid, its arguments, where its
#        standard streams point, whether it leads a session of its own), then, by AWAKE_STANDIN_MODE,
#        watch (wait for the -w pid to go, as caffeinate does), exit (leave at once with status 1)
#        or hold (stay AWAKE_STANDIN_HOLD_S seconds whatever the lane does). Every AW-C leg fails on
#        an adapter that starts no keep-awake process.
AWBIN="$T/bin/caffeinate-standin"
cat > "$AWBIN" <<'AWAKE_STANDIN_END'
#!/usr/bin/env python3
"""caffeinate stand-in for the AW-C legs: one line per start, then watch, exit or hold."""
import os, stat, sys, time
NULL = os.stat(os.devnull)
def where(fd):
    try:
        st = os.fstat(fd)
    except OSError:
        return "closed"
    return "null" if stat.S_ISCHR(st.st_mode) and st.st_rdev == NULL.st_rdev else "other"
args, mode = sys.argv[1:], os.environ.get("AWAKE_STANDIN_MODE", "watch")
with open(os.environ["AWAKE_STANDIN_LOG"], "a") as handle:
    handle.write("pid=%d args=%s stdin=%s stdout=%s stderr=%s session=%s mode=%s\n" % (
        os.getpid(), " ".join(args), where(0), where(1), where(2),
        "own" if os.getsid(0) == os.getpid() else "shared", mode))
if mode == "exit":
    sys.exit(1)
if mode == "hold":
    time.sleep(float(os.environ.get("AWAKE_STANDIN_HOLD_S", "60")))
    sys.exit(0)
pid = int(args[args.index("-w") + 1]) if "-w" in args[:-1] else 0
waited = 0.0
while pid and waited < 600:      # a bound, so no stand-in outlives the suite; set by judgement
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        break
    except PermissionError:
        pass
    time.sleep(0.1)
    waited += 0.1
with open(os.environ["AWAKE_STANDIN_LOG"], "a") as handle:
    handle.write("gone pid=%d watched=%d\n" % (os.getpid(), pid))
AWAKE_STANDIN_END
chmod +x "$AWBIN"
AWREC="$T/store/spawn-records/run-awake.jsonl"
AWREP="$T/store/spawn-records/run-awake-report"
awfacts(){ # lane -> the lane's event kinds in order, then its LAST pass's process, keep-awake and close
  "$PY" - "$AWREC" "$1" <<'AWAKE_FACTS_END'
import json, sys
kinds, spawned, awake, closed = [], {}, {}, {}
try:
    rows = open(sys.argv[1], encoding="utf-8").readlines()
except OSError:
    rows = []
for line in rows:
    try:
        row = json.loads(line)
    except ValueError:
        continue
    if row.get("lane") != sys.argv[2]:
        continue
    kinds.append(str(row.get("event")))
    if row.get("event") in ("lane-spawned", "lane-respawned"):
        spawned = row
    elif row.get("event") == "lane-awake":
        awake = row
    elif row.get("event") == "lane-closed":
        closed = row
print("kinds " + " ".join(kinds))
print("spawned pid=%s wrapper=%s" % (spawned.get("pid"), spawned.get("wrapper_pid")))
print("awake %s caffeinate=%s watched=%s wrapper=%s detached=%s harness=%s" % (
    awake.get("awake"), awake.get("caffeinate_pid"), awake.get("watched_pid"),
    awake.get("wrapper_pid"), awake.get("detached"), awake.get("harness")))
print("command " + " ".join(str(part) for part in awake.get("command") or []))
print("note %s" % awake.get("note"))
print("closed %s %s %s" % (closed.get("exit_class"), closed.get("exit_code"), closed.get("process_exit")))
AWAKE_FACTS_END
}
awpid(){ # facts, key -> the pid after `spawned pid=` (key pid) or after its `wrapper=` (key wrapper)
  case "$2" in
    pid) printf '%s\n' "$1" | sed -n 's/^spawned pid=\([0-9][0-9]*\) wrapper=.*$/\1/p' ;;
    wrapper) printf '%s\n' "$1" | sed -n 's/^spawned pid=[0-9][0-9]* wrapper=\([0-9][0-9]*\)$/\1/p' ;;
  esac
}
awstandin(){ # stand-in log -> the pid of its first start, nothing when it never started. It waits for
  # the start line, bounded at 10 s (100 polls of 0.1 s): the stand-in writes it as its first act, but
  # a shim lane can close before a freshly written script has started (a run of the twin lane.py leg
  # read an absent log); the bound is set by judgement, unmeasured.
  n=0
  while [ $n -lt 100 ] && ! { [ -f "$1" ] && grep -q '^pid=' "$1"; }; do sleep 0.1; n=$((n + 1)); done
  [ -f "$1" ] && sed -n 's/^pid=\([0-9][0-9]*\) args=.*$/\1/p' "$1" | head -1
}
awlog(){ [ -f "$1" ] && tr '\n' '|' < "$1" || printf 'absent'; }
SPAWN_KINDS='kinds lane-open lane-spawned lane-awake lane-session lane-closed'

# AW-C01 · a foreground spawn
env AIMYTH_CAFFEINATE="$AWBIN" AWAKE_STANDIN_MODE=watch AWAKE_STANDIN_LOG="$T/awc1.log" CODEX_SHIM_MODE=ok \
    CODEX_SHIM_THREAD=thread-awc1 "$PY" "$ADAPTER" spawn --run run-awake --lane AC1 "${COMMON[@]}" >"$T/awc1.out" 2>&1; rc1=$?
F1=$(awfacts AC1); P1=$(awpid "$F1" pid); W1=$(awpid "$F1" wrapper); S1=$(awstandin "$T/awc1.log")
if [ $rc1 -eq 0 ] && [ -n "$P1" ] && [ -n "$S1" ] && [ "$(grep -c '^pid=' "$T/awc1.log")" = 1 ] \
   && grep -q "^pid=$S1 args=-i -w $P1 stdin=" "$T/awc1.log" \
   && printf '%s\n' "$F1" | grep -qxF "$SPAWN_KINDS" \
   && printf '%s\n' "$F1" | grep -qxF "awake started caffeinate=$S1 watched=$P1 wrapper=$W1 detached=False harness=codex" \
   && printf '%s\n' "$F1" | grep -qxF "command $AWBIN -i -w $P1" \
   && printf '%s\n' "$F1" | grep -qxF 'closed completed 0 0'; then
  pass "AW-C01 a foreground spawn starts the keep-awake process once, with -i -w <the codex process's pid> (the stand-in's own argv); lane-awake follows lane-spawned (before lane-session): started, the stand-in's pid as caffeinate_pid, the codex pid as watched_pid"
else fail "AW-C01 the foreground keep-awake start" "rc=$rc1 $(printf '%s' "$F1" | tr '\n' '|') stand-in: $(awlog "$T/awc1.log")"; fi

# AW-C02 · it runs apart and leaves by itself (bounded at 5 s, 50 polls of 0.1 s: the stand-in polls
#          every 0.1 s and the codex process was reaped before the spawn returned; set by judgement)
gone=0; n=0
while [ -n "$S1" ] && [ $n -lt 50 ]; do
  if grep -qx "gone pid=$S1 watched=$P1" "$T/awc1.log"; then gone=1; break; fi
  sleep 0.1; n=$((n + 1))
done
if [ -n "$S1" ] && grep -qx "pid=$S1 args=-i -w $P1 stdin=null stdout=null stderr=null session=own mode=watch" "$T/awc1.log" \
   && [ $gone -eq 1 ]; then
  pass "AW-C02 the keep-awake process runs apart from the adapter — stdin, stdout and stderr on /dev/null, a session of its own — and left by itself once the codex process had gone"
else fail "AW-C02 the keep-awake process's streams, session and exit" "gone=$gone stand-in: $(awlog "$T/awc1.log")"; fi

# AW-C03 · a detached spawn (the waiting form): the worker starts it beside its own codex process
out="$(env AIMYTH_CAFFEINATE="$AWBIN" AWAKE_STANDIN_MODE=watch AWAKE_STANDIN_LOG="$T/awc3.log" CODEX_SHIM_MODE=ok \
       CODEX_SHIM_THREAD=thread-awc3 "$PY" "$ADAPTER" spawn --run run-awake --lane AC3 "${COMMON[@]}" --detach 2>"$T/awc3.err")"; rc3=$?
D3=$(printf '%s\n' "$out" | sed -n 's/^detached pid \([0-9][0-9]*\) .*$/\1/p' | head -1)
F3=$(awfacts AC3); P3=$(awpid "$F3" pid); S3=$(awstandin "$T/awc3.log")
if [ $rc3 -eq 0 ] && [ -n "$D3" ] && [ -n "$P3" ] && [ -n "$S3" ] \
   && grep -qx "pid=$S3 args=-i -w $P3 stdin=null stdout=null stderr=null session=own mode=watch" "$T/awc3.log" \
   && printf '%s\n' "$F3" | grep -qxF "spawned pid=$P3 wrapper=$D3" \
   && printf '%s\n' "$F3" | grep -qxF "awake started caffeinate=$S3 watched=$P3 wrapper=$D3 detached=True harness=codex" \
   && printf '%s\n' "$F3" | grep -qxF "$SPAWN_KINDS" && printf '%s\n' "$F3" | grep -qxF 'closed completed 0 0'; then
  pass "AW-C03 a detached spawn's worker (pid $D3) starts the keep-awake process beside its codex process: -i -w <the codex pid>, and lane-awake carries the worker's pid as wrapper_pid and detached true"
else fail "AW-C03 the detached keep-awake start" "rc=$rc3 worker='$D3' $(printf '%s' "$F3" | tr '\n' '|') stand-in: $(awlog "$T/awc3.log") err: $(tail -2 "$T/awc3.err" | tr '\n' '|')"; fi

# AW-C04 · an absent binary: skipped with the why, and the spawn runs as ever
AWNO="$T/aw-absent/caffeinate"
env AIMYTH_CAFFEINATE="$AWNO" AWAKE_STANDIN_LOG="$T/awc4.log" CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-awc4 \
    "$PY" "$ADAPTER" spawn --run run-awake --lane AC4 "${COMMON[@]}" >"$T/awc4.out" 2>&1; rc4=$?
F4=$(awfacts AC4); P4=$(awpid "$F4" pid)
if [ $rc4 -eq 0 ] && [ -n "$P4" ] && [ ! -e "$T/awc4.log" ] && printf '%s\n' "$F4" | grep -qxF "$SPAWN_KINDS" \
   && printf '%s\n' "$F4" | grep -q "^awake skipped caffeinate=None watched=$P4 wrapper=[0-9][0-9]* detached=False harness=codex\$" \
   && printf '%s\n' "$F4" | grep -qF "note no caffeinate at $AWNO (another platform, or a missing binary): the host may sleep while pid $P4 runs" \
   && printf '%s\n' "$F4" | grep -qxF 'closed completed 0 0' && grep -q 'REPORT-OK-thread-awc4' "$AWREP-AC4.md"; then
  pass "AW-C04 an absent caffeinate is skipped with a note naming the path (lane-awake: skipped, no caffeinate_pid) and the spawn still runs to a completed close with its report"
else fail "AW-C04 the absent binary" "rc=$rc4 $(printf '%s' "$F4" | tr '\n' '|') $(head -2 "$T/awc4.out" | tr '\n' '|')"; fi

# AW-C05 · a binary that fails at exec (executable, but no program: exec format error)
mkdir -p "$T/aw-bad"; printf 'not a program\n' > "$T/aw-bad/caffeinate-badexec"; chmod 755 "$T/aw-bad/caffeinate-badexec"
env AIMYTH_CAFFEINATE="$T/aw-bad/caffeinate-badexec" CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-awc5 \
    "$PY" "$ADAPTER" spawn --run run-awake --lane AC5 "${COMMON[@]}" >"$T/awc5.out" 2>&1; rc5=$?
F5=$(awfacts AC5)
if [ $rc5 -eq 0 ] && printf '%s\n' "$F5" | grep -q '^awake skipped caffeinate=None ' \
   && printf '%s\n' "$F5" | grep -q '^note caffeinate did not start (OSError: .*): the host may sleep while pid [0-9][0-9]* runs' \
   && printf '%s\n' "$F5" | grep -qxF "$SPAWN_KINDS" && printf '%s\n' "$F5" | grep -qxF 'closed completed 0 0'; then
  pass "AW-C05 a caffeinate that fails at exec is skipped with the why in the note, and the spawn runs to a completed close"
else fail "AW-C05 the unstartable binary" "rc=$rc5 $(printf '%s' "$F5" | tr '\n' '|')"; fi

# AW-C06 · a keep-awake process that dies at once (exit status 1) while the codex process runs on for
#          2 s changes nothing about the lane's result; AW-C01's lane, with the normal stand-in, is the control.
env AIMYTH_CAFFEINATE="$AWBIN" AWAKE_STANDIN_MODE=exit AWAKE_STANDIN_LOG="$T/awc6.log" CODEX_SHIM_MODE=slow CODEX_SHIM_SLEEP=2 \
    CODEX_SHIM_THREAD=thread-awc1 "$PY" "$ADAPTER" spawn --run run-awake --lane AC6 "${COMMON[@]}" >"$T/awc6.out" 2>&1; rc6=$?
F6=$(awfacts AC6); P6=$(awpid "$F6" pid); S6=$(awstandin "$T/awc6.log")
if [ $rc6 -eq $rc1 ] && [ $rc6 -eq 0 ] && [ -n "$S6" ] \
   && grep -qx "pid=$S6 args=-i -w $P6 stdin=null stdout=null stderr=null session=own mode=exit" "$T/awc6.log" \
   && ! grep -q '^gone ' "$T/awc6.log" \
   && printf '%s\n' "$F6" | grep -qxF "awake started caffeinate=$S6 watched=$P6 wrapper=$(awpid "$F6" wrapper) detached=False harness=codex" \
   && [ "$(printf '%s\n' "$F6" | grep '^closed ')" = "$(printf '%s\n' "$F1" | grep '^closed ')" ] \
   && [ "$(printf '%s\n' "$F6" | grep '^kinds ')" = "$(printf '%s\n' "$F1" | grep '^kinds ')" ] \
   && cmp -s "$AWREP-AC6.md" "$AWREP-AC1.md"; then
  pass "AW-C06 a keep-awake process that dies at once leaves the lane's result as the control's (AW-C01): exit 0, the same close class, codes and events, a byte-identical report"
else fail "AW-C06 the early death" "rc=$rc6 vs $rc1 $(printf '%s' "$F6" | tr '\n' '|') stand-in: $(awlog "$T/awc6.log")"; fi

# AW-C07 · it never blocks the adapter: a stand-in holding on for 60 s after the lane (set by judgement:
#          far above a shim spawn's few seconds) is still running when the spawn's output capture
#          returns, so neither the capture's stdout nor the codex process's stdin (the shim reads it
#          to its end) waited on it. Control on the same probe: the stand-in run with the capture's own
#          stdout (a 2 s hold) makes the capture wait and is gone when it returns.
t0=$(date +%s)
out="$(env AIMYTH_CAFFEINATE="$AWBIN" AWAKE_STANDIN_MODE=hold AWAKE_STANDIN_LOG="$T/awc7.log" CODEX_SHIM_MODE=ok \
       CODEX_SHIM_THREAD=thread-awc7 "$PY" "$ADAPTER" spawn --run run-awake --lane AC7 "${COMMON[@]}" 2>&1)"; rc7=$?
t1=$(date +%s)
S7=$(awstandin "$T/awc7.log"); L7=""; [ -n "$S7" ] && L7=$(ps -p "$S7" -o pid= | tr -d ' ')
[ -n "$L7" ] && kill "$S7"
F7=$(awfacts AC7)
c0=$(date +%s)
ctl="$(env AWAKE_STANDIN_MODE=hold AWAKE_STANDIN_HOLD_S=2 AWAKE_STANDIN_LOG="$T/awc7c.log" "$AWBIN" -i -w $$)"
c1=$(date +%s)
SC=$(awstandin "$T/awc7c.log"); LC=""; [ -n "$SC" ] && LC=$(ps -p "$SC" -o pid= | tr -d ' ')
if [ $rc7 -eq 0 ] && [ -n "$S7" ] && [ "$L7" = "$S7" ] \
   && grep -qx "pid=$S7 args=-i -w $(awpid "$F7" pid) stdin=null stdout=null stderr=null session=own mode=hold" "$T/awc7.log" \
   && printf '%s\n' "$F7" | grep -qxF 'closed completed 0 0' \
   && [ -n "$SC" ] && [ -z "$LC" ] && [ $((c1 - c0)) -ge 2 ] \
   && grep -qx "pid=$SC args=-i -w $$ stdin=[a-z]* stdout=other stderr=[a-z]* session=shared mode=hold" "$T/awc7c.log"; then
  pass "AW-C07 the keep-awake process never blocks the adapter: the spawn returned in $((t1 - t0)) s with its 60 s stand-in still running (control: a stand-in holding the capture's stdout made it wait $((c1 - c0)) s and was gone at return)"
else fail "AW-C07 the adapter waited on its keep-awake process" "rc=$rc7 $((t1 - t0)) s alive '$L7' of '$S7'; control $((c1 - c0)) s alive '$LC'; stand-in: $(awlog "$T/awc7.log")"; fi

# AW-C08 · a resume starts it beside the resumed codex process, after lane-respawned
env AIMYTH_CAFFEINATE="$AWBIN" AWAKE_STANDIN_MODE=watch AWAKE_STANDIN_LOG="$T/awc8.log" CODEX_SHIM_MODE=ok \
    CODEX_SHIM_THREAD=thread-awc1 "$PY" "$ADAPTER" resume --run run-awake --lane AC1 --brief "$T/follow.md" \
    --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60 \
    >"$T/awc8.out" 2>&1; rc8=$?
F8=$(awfacts AC1); P8=$(awpid "$F8" pid); S8=$(awstandin "$T/awc8.log")
if [ $rc8 -eq 0 ] && [ -n "$P8" ] && [ "$P8" != "$P1" ] && [ -n "$S8" ] \
   && grep -qx "pid=$S8 args=-i -w $P8 stdin=null stdout=null stderr=null session=own mode=watch" "$T/awc8.log" \
   && printf '%s\n' "$F8" | grep -qxF "$SPAWN_KINDS lane-resumed lane-respawned lane-awake lane-session lane-closed" \
   && printf '%s\n' "$F8" | grep -qxF "awake started caffeinate=$S8 watched=$P8 wrapper=$(awpid "$F8" wrapper) detached=False harness=codex" \
   && printf '%s\n' "$F8" | grep -qxF 'closed completed 0 0'; then
  pass "AW-C08 a resume starts the keep-awake process beside the resumed codex process: -i -w <the lane-respawned pid>, its lane-awake after lane-respawned"
else fail "AW-C08 the resumed keep-awake start" "rc=$rc8 $(printf '%s' "$F8" | tr '\n' '|') stand-in: $(awlog "$T/awc8.log") $(tail -2 "$T/awc8.out" | tr '\n' '|')"; fi

# AW-C09–AW-C13 · the held-lane beat (review CR-AWAKE finding 1: "each helper keeps the Mac awake while
#          it runs" carries no beat exemption). `resume --beat` starts the keep-awake process beside
#          the beat's codex process under the same rules and, its record contract being one hold-beat
#          line, carries the state on that line as added fields (awake, caffeinate_pid, watched_pid,
#          and note when skipped), never a lane-awake line. Each beat runs on its own fresh copy of
#          this section's record (lane AC1, resumed by AW-C08 and closed), so every copy starts from
#          the same lines; the shim logs its own pid to CODEX_SHIM_ORDER, so the model pid is read
#          apart from the adapter's record. AW-C09's beat, with the watching stand-in, is the control
#          for the others' result.
AWCB_BASE=$(grep -c . "$AWREC")
awcbeat(){ # leg, stand-in binary, stand-in mode, then any extra environment (NAME=value) -> one beat on a
  #          fresh copy of the record; sets BO (its output) and BRC (its exit code)
  bl="$1"; bb="$2"; bm="$3"; shift 3
  rm -rf "$T/awcb-$bl"; mkdir -p "$T/awcb-$bl"; cp "$AWREC" "$T/awcb-$bl/rec.jsonl"
  BO="$(env AIMYTH_CAFFEINATE="$bb" AWAKE_STANDIN_MODE="$bm" AWAKE_STANDIN_LOG="$T/awcb-$bl/standin.log" \
        CODEX_SHIM_ORDER="$T/awcb-$bl/order" CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-awc1 "$@" \
        "$PY" "$ADAPTER" resume --run run-awake --lane AC1 --beat --record "$T/awcb-$bl/rec.jsonl" \
        --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none 2>&1)"; BRC=$?
}
awcbfacts(){ # leg -> the kinds the beat added to its copy, the model pid the shim logged, then the
  #            hold-beat's keep-awake fields and its result fields (sorted JSON, for comparison)
  "$PY" - "$T/awcb-$1/rec.jsonl" "$AWCB_BASE" "$T/awcb-$1/order" <<'AWAKE_BEAT_FACTS_END'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
added = rows[int(sys.argv[2]):]
try:
    order = [l.split("=", 1)[1].strip() for l in open(sys.argv[3], encoding="utf-8") if l.startswith("LANE pid=")]
except OSError:
    order = []
beat = added[-1] if added and added[-1].get("event") == "hold-beat" else {}
print("added " + " ".join(str(r.get("event")) for r in added))
print("model " + " ".join(order))
print("awake %s caffeinate=%s watched=%s note=%s" % (beat.get("awake"), beat.get("caffeinate_pid"),
      beat.get("watched_pid"), "present" if "note" in beat else "absent"))
print("note %s" % beat.get("note"))
keys = ("n", "ok", "exit_class", "exit_code", "process_exit", "num_turns", "usage", "usage_complete",
        "reply", "error", "errors", "events_records", "limit_signal", "killed_by", "config_match",
        "by", "session_id", "cost_src", "total_cost_usd", "harness")
print("result " + json.dumps({k: beat.get(k) for k in keys}, sort_keys=True))
AWAKE_BEAT_FACTS_END
}
awcbmodel(){ printf '%s\n' "$1" | sed -n 's/^model \([0-9][0-9]*\)$/\1/p'; }
awcbresult(){ printf '%s\n' "$1" | grep '^result '; }
awcbsummary(){ # the beat's summary line with its duration masked, the one figure that differs run to run
  printf '%s\n' "$1" | sed -n 's/^\(beat run-awake\/AC1: .*\) · [0-9][0-9.]* s · \(.*\)$/\1 · <d> s · \2/p'; }

# AW-C09 · a beat starts it once beside its codex process, apart from the adapter, and it leaves by
#          itself (the wait bounded at 5 s as AW-C02's, set by judgement)
awcbeat C09 "$AWBIN" watch
BO9=$BO; BRC9=$BRC; BF9=$(awcbfacts C09); BP9=$(awcbmodel "$BF9"); BS9=$(awstandin "$T/awcb-C09/standin.log")
gone=0; n=0
while [ -n "$BS9" ] && [ $n -lt 50 ]; do
  if grep -qx "gone pid=$BS9 watched=$BP9" "$T/awcb-C09/standin.log"; then gone=1; break; fi
  sleep 0.1; n=$((n + 1))
done
if [ $BRC9 -eq 0 ] && [ -n "$BP9" ] && [ -n "$BS9" ] && [ "$(grep -c '^pid=' "$T/awcb-C09/standin.log")" = 1 ] \
   && grep -qx "pid=$BS9 args=-i -w $BP9 stdin=null stdout=null stderr=null session=own mode=watch" "$T/awcb-C09/standin.log" \
   && printf '%s\n' "$BF9" | grep -qxF 'added hold-beat' && [ $gone -eq 1 ]; then
  pass "AW-C09 a beat starts the keep-awake process once, with -i -w <the codex pid the shim logged>, apart from the adapter (/dev/null streams, a session of its own) and gone by itself after; the record gains its one hold-beat line and no lane-awake line"
else fail "AW-C09 the beat's keep-awake start" "rc=$BRC9 $(printf '%s' "$BF9" | tr '\n' '|') gone=$gone stand-in: $(awlog "$T/awcb-C09/standin.log") $(printf '%s' "$BO9" | head -2 | tr '\n' '|')"; fi

# AW-C10 · the hold-beat line carries the keep-awake state as added fields, beside its usual ones
if [ -n "$BS9" ] && [ -n "$BP9" ] \
   && printf '%s\n' "$BF9" | grep -qxF "awake started caffeinate=$BS9 watched=$BP9 note=absent" \
   && printf '%s\n' "$BF9" | grep -q '^result .*"exit_class": "completed".*"harness": "codex".*"ok": true' \
   && printf '%s\n' "$BO9" | grep -q '^beat run-awake/AC1: codex .* · ok · '; then
  pass "AW-C10 the beat's hold-beat line carries the keep-awake state as added fields — awake started, the stand-in's pid as caffeinate_pid, the codex pid as watched_pid, no note — beside its usual fields (ok true, completed, harness codex) and its usual summary line"
else fail "AW-C10 the hold-beat keep-awake fields" "$(printf '%s' "$BF9" | tr '\n' '|')"; fi

# AW-C11 · an absent binary: skipped with the why on the same one line, and the beat's result is the control's
awcbeat C11 "$AWNO" watch
BF11=$(awcbfacts C11); BP11=$(awcbmodel "$BF11")
if [ $BRC -eq $BRC9 ] && [ $BRC -eq 0 ] && [ -n "$BP11" ] && [ ! -e "$T/awcb-C11/standin.log" ] \
   && printf '%s\n' "$BF11" | grep -qxF 'added hold-beat' \
   && printf '%s\n' "$BF11" | grep -qxF "awake skipped caffeinate=None watched=$BP11 note=present" \
   && printf '%s\n' "$BF11" | grep -qF "note no caffeinate at $AWNO (another platform, or a missing binary): the host may sleep while pid $BP11 runs" \
   && [ "$(awcbresult "$BF11")" = "$(awcbresult "$BF9")" ] \
   && [ -n "$(awcbsummary "$BO")" ] && [ "$(awcbsummary "$BO")" = "$(awcbsummary "$BO9")" ]; then
  pass "AW-C11 a beat with no caffeinate is skipped with a note naming the path on its one hold-beat line (awake skipped, no caffeinate_pid, the codex pid as watched_pid), and the beat's result is the control's (AW-C09): exit 0, the same ok, class, codes, usage and reply, the same summary line"
else fail "AW-C11 the beat's absent binary" "rc=$BRC vs $BRC9 $(printf '%s' "$BF11" | tr '\n' '|') $(printf '%s' "$BO" | head -2 | tr '\n' '|')"; fi

# AW-C12 · a keep-awake process that dies at once (exit status 1) while the codex process runs on for
#          2 s changes nothing about the beat's result (AW-C09 the control)
awcbeat C12 "$AWBIN" exit CODEX_SHIM_MODE=slow CODEX_SHIM_SLEEP=2
BF12=$(awcbfacts C12); BP12=$(awcbmodel "$BF12"); BS12=$(awstandin "$T/awcb-C12/standin.log")
if [ $BRC -eq $BRC9 ] && [ -n "$BP12" ] && [ -n "$BS12" ] \
   && grep -qx "pid=$BS12 args=-i -w $BP12 stdin=null stdout=null stderr=null session=own mode=exit" "$T/awcb-C12/standin.log" \
   && ! grep -q '^gone ' "$T/awcb-C12/standin.log" \
   && printf '%s\n' "$BF12" | grep -qxF 'added hold-beat' \
   && printf '%s\n' "$BF12" | grep -qxF "awake started caffeinate=$BS12 watched=$BP12 note=absent" \
   && [ "$(awcbresult "$BF12")" = "$(awcbresult "$BF9")" ] \
   && [ -n "$(awcbsummary "$BO")" ] && [ "$(awcbsummary "$BO")" = "$(awcbsummary "$BO9")" ]; then
  pass "AW-C12 a keep-awake process that dies at once leaves the beat's result as the control's (AW-C09): the same exit, ok, class, codes, usage, reply and summary line"
else fail "AW-C12 the beat's early death" "rc=$BRC vs $BRC9 $(printf '%s' "$BF12" | tr '\n' '|') stand-in: $(awlog "$T/awcb-C12/standin.log")"; fi

# AW-C13 · it never blocks the beat: a stand-in that holds on for 60 s (AW-C07's, whose control on this
#          same run shows the probe catches a held stream) is still running when the beat returns
t0=$(date +%s)
awcbeat C13 "$AWBIN" hold
t1=$(date +%s)
BS13=$(awstandin "$T/awcb-C13/standin.log"); L13=""; [ -n "$BS13" ] && L13=$(ps -p "$BS13" -o pid= | tr -d ' ')
[ -n "$L13" ] && kill "$BS13"
BF13=$(awcbfacts C13); BP13=$(awcbmodel "$BF13")
if [ $BRC -eq 0 ] && [ -n "$BS13" ] && [ "$L13" = "$BS13" ] && [ -n "$BP13" ] \
   && grep -qx "pid=$BS13 args=-i -w $BP13 stdin=null stdout=null stderr=null session=own mode=hold" "$T/awcb-C13/standin.log" \
   && printf '%s\n' "$BF13" | grep -qxF "awake started caffeinate=$BS13 watched=$BP13 note=absent" \
   && [ "$(awcbresult "$BF13")" = "$(awcbresult "$BF9")" ]; then
  pass "AW-C13 the keep-awake process never blocks the beat: the beat returned in $((t1 - t0)) s with its 60 s stand-in still running, and its result is the control's (AW-C09)"
else fail "AW-C13 the beat waited on its keep-awake process" "rc=$BRC $((t1 - t0)) s alive '$L13' of '$BS13'; $(printf '%s' "$BF13" | tr '\n' '|') stand-in: $(awlog "$T/awcb-C13/standin.log")"; fi

# ============================== Batch 4: staging, the write scope, the decisive error ===========
# The staged copy's ownership (register 2026-09-22 21:55), the empty stage's removal (2026-09-16 12:46),
# `<<STAGED_COPY>>` (2026-09-25 04:3x), a verifier or builder's write scope (2026-09-23 18:0x), the
# decisive error (2026-09-26 00:16), the report control (2026-09-20 01:58), declared inputs and web work
# (2026-09-14 00:06, 2026-09-20 17:01) and the suite's own home (2026-10-04 10:45). Every refusal leg
# checks exit 2 and no record line; every clean claim carries its control on the same run.
REC4="$T/store/spawn-records/run-b4c.jsonl"
SR4="$T/store/spawn-records"
B4C=(--codex "$T/bin/codex" --reason "(a) suite" --choice-reason "suite pick" --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60)
mkdir -p "$T/b4src/sub" "$T/b4brief"
printf 'PHRASE-IN-COPY\n' > "$T/b4src/x.md"
printf 'SECRET-EXCLUDED\n' > "$T/b4src/excluded.md"
printf 'deep\n' > "$T/b4src/sub/y.md"
printf 'OUTSIDE-TOKEN\n' > "$T/b4outside.txt"
: > "$T/b4src/empty.md"
ln -s "$T/b4outside.txt" "$T/b4src/link-out.md"
b4brief(){ printf '%b' "$2" > "$T/b4brief/$1.md"; echo "$T/b4brief/$1.md"; }
b4spawn(){ # lane, brief, extra... -> B4O, B4RC
  L=$1; BR=$2; shift 2
  B4O=$("$PY" "$ADAPTER" spawn --run run-b4c --lane "$L" --class critic --brief "$BR" "${B4C[@]}" "$@" 2>&1); B4RC=$?; }
lanes_in(){ if [ ! -f "$REC4" ]; then echo 0; return; fi
  "$PY" -c 'import json,sys; print(sum(1 for l in open(sys.argv[1]) if l.strip() and json.loads(l).get("lane")==sys.argv[2]))' "$REC4" "$1"; }

# B4C-S · the staged copy: checked on the copy, owned by one attempt, never left by a refusal -------
B=$(b4brief s01bad 'x\nCONTROL+: NOPE-PHRASE in <<STAGED_COPY>>/x.md\n')
b4spawn S01 "$B" --stage-from "$T/b4src"
if [ $B4RC -eq 2 ] && printf '%s' "$B4O" | grep -q 'matches nothing' && [ ! -e "$SR4/run-b4c-cwd-S01" ] && [ "$(lanes_in S01)" = 0 ]; then
  pass "B4C-S01 a staged control that misses refuses after the copy is made and removes the copy: no per-pass directory, no record line"
else fail "B4C-S01 the refused staged control" "rc=$B4RC $(ls "$SR4" | grep S01) $B4O"; fi
B=$(b4brief s01ok 'x\nCONTROL+: PHRASE-IN-COPY in <<STAGED_COPY>>/x.md\nRead <<STAGED_COPY>>/x.md before anything else.\n')
CODEX_SHIM_MODE=ok b4spawn S01 "$B" --stage-from "$T/b4src"
PF=$(field "$REC4" S01 lane-open prompt_file | tr -d '"')
if [ $B4RC -eq 0 ] && [ -d "$SR4/run-b4c-cwd-S01" ] && grep -q "Read $TR/store/spawn-records/run-b4c-cwd-S01/x.md before anything else" "$PF" \
   && grep -q "Read $TR/store/spawn-records/run-b4c-cwd-S01/x.md before anything else" "$CODEX_SHIM_PROMPT" \
   && [ "$(field "$REC4" S01 lane-open staged_copy_token)" = "2" ] \
   && [ "$(field "$REC4" S01 lane-open controls_checked)" = "[{\"phrase\": \"PHRASE-IN-COPY\", \"file\": \"$TR/store/spawn-records/run-b4c-cwd-S01/x.md\", \"matches\": 1, \"staged\": true}]" ]; then
  pass "B4C-S02 the retry under the same lane id passes: the control is checked on the copy, <<STAGED_COPY>> becomes the stage path in the prompt the lane receives and the recorded prompt file, counted on lane-open"
else fail "B4C-S02 the retry and the substitution" "rc=$B4RC token=$(field "$REC4" S01 lane-open staged_copy_token) controls=$(field "$REC4" S01 lane-open controls_checked) $B4O"; fi
mkdir -p "$T/b4src-bad"; printf 'fine\n' > "$T/b4src-bad/a.md"; printf 'locked\n' > "$T/b4src-bad/z-unreadable.md"; chmod 000 "$T/b4src-bad/z-unreadable.md"
B=$(b4brief s03 'x\n')
b4spawn S03 "$B" --stage-from "$T/b4src-bad"
chmod 644 "$T/b4src-bad/z-unreadable.md"
if [ $B4RC -eq 2 ] && printf '%s' "$B4O" | grep -q 'staging .* failed' && printf '%s' "$B4O" | grep -q 'the partial copy was removed' \
   && [ ! -e "$SR4/run-b4c-cwd-S03" ] && [ "$(lanes_in S03)" = 0 ]; then
  pass "B4C-S03 a copy that fails part-way is removed before the refusal: no stage, no record line"
else fail "B4C-S03 the failed copy" "rc=$B4RC $(ls "$SR4" | grep S03) $B4O"; fi
b4spawn S03 "$B" --stage-from "$T/b4src-bad"
[ $B4RC -eq 0 ] && pass "B4C-S03b the retry under the same lane id passes once the source reads (the control)" || fail "B4C-S03b retry" "rc=$B4RC $B4O"
B=$(b4brief s04 'x\nCONTROL+: PHRASE-IN-COPY in <<STAGED_COPY>>/x.md\n')
mkdir "$SR4/run-b4c-cwd-S04"
b4spawn S04 "$B" --stage-from "$T/b4src" --dry-run
if [ $B4RC -eq 0 ] && printf '%s' "$B4O" | grep -q '"staged": true' && [ -d "$SR4/run-b4c-cwd-S04" ] \
   && [ -z "$(ls -A "$SR4/run-b4c-cwd-S04")" ] && [ "$(lanes_in S04)" = 0 ]; then
  pass "B4C-S04 a dry run checks the control on the real copy, then removes it and puts back the empty stage directory it found"
else fail "B4C-S04 the dry run" "rc=$B4RC $(ls -A "$SR4/run-b4c-cwd-S04" 2>&1 | head -3) $B4O"; fi
B=$(b4brief s05 'x\nCONTROL+: SECRET-EXCLUDED in <<STAGED_COPY>>/excluded.md\n')
b4spawn S05 "$B" --stage-from "$T/b4src" --stage-exclude excluded.md
if [ $B4RC -eq 2 ] && printf '%s' "$B4O" | grep -q 'not found in the staged copy' && [ ! -e "$SR4/run-b4c-cwd-S05" ]; then
  pass "B4C-S05 a control on a file the copy excludes refuses: it is never checked through its original"
else fail "B4C-S05 the excluded file" "rc=$B4RC $B4O"; fi
B=$(b4brief s06 'x\nCONTROL+: OUTSIDE-TOKEN in <<STAGED_COPY>>/link-out.md\n')
b4spawn S06 "$B" --stage-from "$T/b4src"
if [ $B4RC -eq 2 ] && printf '%s' "$B4O" | grep -q 'leaves the staged copy' && [ ! -e "$SR4/run-b4c-cwd-S06" ]; then
  pass "B4C-S06 a token-derived control through a link out of the copy refuses: it cannot certify the copy"
else fail "B4C-S06 the escaping link" "rc=$B4RC $B4O"; fi
B=$(b4brief s07 'x\nCONTROL+: X in <<STAGED_COPY>>/../x.md\n')
b4spawn S07 "$B" --stage-from "$T/b4src"
[ $B4RC -eq 2 ] && printf '%s' "$B4O" | grep -q 'leaves the staged copy' && pass "B4C-S07 a token-derived path climbing out with .. refuses" || fail "B4C-S07 the .. path" "rc=$B4RC $B4O"
B=$(b4brief s08 'x\nCONTROL+: X in <<STAGED_COPY>>/x.md\n')
b4spawn S08 "$B" --cwd "$T/work" --dry-run
[ $B4RC -eq 2 ] && printf '%s' "$B4O" | grep -q 'names a staged copy, and this spawn has none' && pass "B4C-S08 a token with no copy to name refuses" || fail "B4C-S08 the unresolved token" "rc=$B4RC $B4O"
B=$(b4brief s08b 'x\nThe staged copy will sit at <<STAGED_COPY>> in a later round.\n')
b4spawn S08b "$B" --cwd "$T/work" --dry-run
[ $B4RC -eq 0 ] && printf '%s' "$B4O" | grep -q 'mentions <<STAGED_COPY>> 1 time(s) and no staged copy applies; left as written' \
  && pass "B4C-S08b a prose mention with no copy is left as written with one line saying so (the control for B4C-S08)" || fail "B4C-S08b prose mention" "rc=$B4RC $B4O"
B=$(b4brief s09 "x\nREAD+: $T/b4src/excluded.md\n")
b4spawn S09 "$B" --stage-from "$T/b4src" --stage-exclude excluded.md
if [ $B4RC -eq 2 ] && printf '%s' "$B4O" | grep -q 'does not exist in the staged copy' && [ ! -e "$SR4/run-b4c-cwd-S09" ]; then
  pass "B4C-S09 a declared input inside the stage source is checked as its staged version: one the copy excludes refuses"
else fail "B4C-S09 the staged input" "rc=$B4RC $B4O"; fi
B=$(b4brief s09b "x\nREAD+: $T/b4src/empty.md\n")
b4spawn S09b "$B" --stage-from "$T/b4src"
[ $B4RC -eq 2 ] && printf '%s' "$B4O" | grep -q 'empty (0 bytes)' && [ ! -e "$SR4/run-b4c-cwd-S09b" ] \
  && pass "B4C-S09b a zero-byte staged input refuses with its path and leaves no copy" || fail "B4C-S09b the empty staged input" "rc=$B4RC $B4O"
B=$(b4brief s09c "x\nREAD+: $T/b4src/sub/y.md\n")
b4spawn S09c "$B" --stage-from "$T/b4src" --dry-run
[ $B4RC -eq 0 ] && printf '%s' "$B4O" | grep -q '"staged": true' && pass "B4C-S09c an included, non-empty staged input passes (the control for B4C-S09)" || fail "B4C-S09c the staged input" "rc=$B4RC $B4O"
# A detached caller checks its copy and removes it before the worker, which makes and checks its own.
B=$(b4brief s10bad 'x\nCONTROL+: NOPE-PHRASE in <<STAGED_COPY>>/x.md\n')
b4spawn S10 "$B" --stage-from "$T/b4src" --detach --no-wait
if [ $B4RC -eq 2 ] && [ ! -e "$SR4/run-b4c-cwd-S10" ] && [ ! -e "$SR4/run-b4c-detached-S10.log" ] && [ "$(lanes_in S10)" = 0 ]; then
  pass "B4C-S10 a detached spawn's staged control refuses in the caller: no copy, no worker, no record line"
else fail "B4C-S10 the detached refusal" "rc=$B4RC $(ls "$SR4" | grep S10) $B4O"; fi
B=$(b4brief s10ok 'x\nCONTROL+: PHRASE-IN-COPY in <<STAGED_COPY>>/x.md\n')
CODEX_SHIM_MODE=ok b4spawn S10 "$B" --stage-from "$T/b4src" --detach
if [ $B4RC -eq 0 ] && [ -d "$SR4/run-b4c-cwd-S10" ] && [ "$(field "$REC4" S10 lane-closed exit_class)" = '"completed"' ] \
   && [ "$(field "$REC4" S10 lane-open controls_checked)" = "[{\"phrase\": \"PHRASE-IN-COPY\", \"file\": \"$TR/store/spawn-records/run-b4c-cwd-S10/x.md\", \"matches\": 1, \"staged\": true}]" ]; then
  pass "B4C-S10b a detached staged spawn completes on the worker's own checked copy, recorded on its lane-open (the control for B4C-S10)"
else fail "B4C-S10b the detached spawn" "rc=$B4RC $(field "$REC4" S10 lane-closed exit_class) $B4O"; fi
# A resumed staged pass resolves the token to its recorded copy.
B=$(b4brief s11 'Continue.\nCONTROL+: PHRASE-IN-COPY in <<STAGED_COPY>>/x.md\nYour copy is <<STAGED_COPY>>.\n')
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-s01 "$PY" "$ADAPTER" resume --run run-b4c --lane S01 --brief "$B" --codex "$T/bin/codex" \
  --viewer none --silence-s 0 --deadline-s 60 >"$T/b4c-s11.out" 2>&1; RC=$?
if [ $RC -eq 0 ] && grep -q "Your copy is $TR/store/spawn-records/run-b4c-cwd-S01\." "$CODEX_SHIM_PROMPT" \
   && [ "$(field "$REC4" S01 lane-resumed controls_checked)" = "[{\"phrase\": \"PHRASE-IN-COPY\", \"file\": \"$TR/store/spawn-records/run-b4c-cwd-S01/x.md\", \"matches\": 1, \"staged\": true}]" ]; then
  pass "B4C-S11 a resumed staged pass resolves <<STAGED_COPY>> to its recorded copy, in its controls and its prompt"
else fail "B4C-S11 the resumed token" "rc=$RC $(cat "$T/b4c-s11.out" | head -3)"; fi

# B4C-U · the empty stage: rmdir only ---------------------------------------------------------------
B=$(b4brief u01 'x\n')
mkdir "$SR4/run-b4c-cwd-U01" && chflags uchg "$SR4/run-b4c-cwd-U01"
b4spawn U01 "$B" --stage-from "$T/b4src"
chflags nouchg "$SR4/run-b4c-cwd-U01"
if [ $B4RC -eq 2 ] && printf '%s' "$B4O" | grep -q 'PROBE FAILED: cannot remove the empty stage' && ! printf '%s' "$B4O" | grep -q Traceback \
   && [ "$(lanes_in U01)" = 0 ]; then
  pass "B4C-U01 an immutable (chflags uchg) empty stage refuses with PROBE FAILED, exit 2, no traceback and no record line"
else fail "B4C-U01 the immutable stage" "rc=$B4RC $B4O"; fi
CODEX_SHIM_MODE=ok b4spawn U01 "$B" --stage-from "$T/b4src"
[ $B4RC -eq 0 ] && [ -f "$SR4/run-b4c-cwd-U01/x.md" ] && pass "B4C-U01b the same empty stage, its flag cleared, is reused (the control)" || fail "B4C-U01b reuse" "rc=$B4RC $B4O"
mkdir -p "$SR4/run-b4c-cwd-U02"; printf 'a late file\n' > "$SR4/run-b4c-cwd-U02/late.txt"
B4U=$("$PY" - "$ADAPTER" "$T/b4src" <<'B4_STAGE_RACE_END'
import argparse, importlib.util, io, os, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("codex_lane_under_test", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
err, saved = io.StringIO(), sys.stderr
sys.stderr = err
try:
    module.stage_copy(argparse.Namespace(stage_from=sys.argv[2], run="run-b4c", lane="U02", record=None,
                                         stage_exclude=None, dry_run=False))
    out = "staged"
except SystemExit as exc:
    out = "exit%s" % exc.code
finally:
    sys.stderr = saved
print(out, "rmdir-refused" if "cannot remove the empty stage" in err.getvalue() else "other")
B4_STAGE_RACE_END
)
if [ "$B4U" = "exit2 rmdir-refused" ] && [ -f "$SR4/run-b4c-cwd-U02/late.txt" ]; then
  pass "B4C-U02 a file that appears in the stage after the caller's guard makes the worker's rmdir refuse, and the file survives"
else fail "B4C-U02 the late file" "$B4U $(ls "$SR4/run-b4c-cwd-U02" 2>&1)"; fi
# A source that holds the stage would be copied into itself: refused before any copy. The copy is
# replaced by a recorder in this process, so code that lacks the check records a call instead of
# copying the store into itself.
B4O3=$("$PY" - "$ADAPTER" "$T/store" <<'B4_STAGE_OVERLAP_END'
import argparse, importlib.util, io, os, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("codex_lane_overlap", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
calls = []
module.shutil.copytree = lambda *a, **k: calls.append(a)
err, saved = io.StringIO(), sys.stderr
sys.stderr = err
try:
    module.stage_copy(argparse.Namespace(stage_from=sys.argv[2], run="run-b4c", lane="U03", record=None,
                                         stage_exclude=None, dry_run=False))
    out = "staged"
except SystemExit as exc:
    out = "exit%s" % exc.code
finally:
    sys.stderr = saved
print(out, "overlap" if "overlap" in err.getvalue() else "other", "copies=%d" % len(calls))
B4_STAGE_OVERLAP_END
)
if [ "$B4O3" = "exit2 overlap copies=0" ] && [ ! -e "$SR4/run-b4c-cwd-U03" ]; then
  pass "B4C-U03 a --stage-from that holds the stage itself refuses before any copy (exit 2, the overlap named)"
else fail "B4C-U03 the overlapping source" "$B4O3"; fi

# ============================== the Batch 4 launcher fold (review CR-B4L) ==========================
# Finding 1: a losing staging attempt never touches the files another attempt put at the stage.
# Finding 8: an interrupted copy leaves nothing the attempt owned, and a same-id retry passes.
# Finding 2: one resolution for the check, the record and the brief the lane receives. Finding 9: a
# process that never starts gives its report controls a verdict. Each leg drives the real spawn path:
# codex-lane.py's own main in this process, its copy step patched, or the command line itself.
mkdir -p "$T/lfsrc/sub"
printf 'LF-ONE\n' > "$T/lfsrc/a.md"; printf 'LF-TWO\n' > "$T/lfsrc/b.md"; printf 'LF-THREE\n' > "$T/lfsrc/sub/c.md"
LFB=$(b4brief lf 'x\nCONTROL+: LF-ONE in <<STAGED_COPY>>/a.md\n')
lf_inproc(){ # mode lane -> "<outcome> stage:<what the stage path holds> attempts:<n> probe:<PROBE FAILED|none>"
  "$PY" - "$ADAPTER" "$1" "$2" "$T/lfsrc" "$LFB" "$T/bin/codex" "$SR4" <<'B4LF_INPROC_END'
import importlib.util, io, os, shutil, sys
sys.dont_write_bytecode = True
adapter, mode, lane_id, src, brief, codex, store = sys.argv[1:8]
spec = importlib.util.spec_from_file_location("codex_lane_lf_" + mode, adapter)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
stage = os.path.join(store, "run-b4c-cwd-" + lane_id)
real_copytree = shutil.copytree
competitor = {"competitor.txt": "COMPETITOR-BYTES-1", os.path.join("deep", "theirs.md"): "COMPETITOR-BYTES-2"}
def racing(source, dest, *a, **k):
    # Another attempt wins the race: its populated copy lands at the stage path just before this copy.
    shutil.copytree = real_copytree
    for rel, body in competitor.items():
        os.makedirs(os.path.dirname(os.path.join(stage, rel)), exist_ok=True)
        with open(os.path.join(stage, rel), "w") as handle:
            handle.write(body + "\n")
    return real_copytree(source, dest, *a, **k)
def interrupting(source, dest, *a, **k):
    # An interrupt arrives once one file has been copied.
    shutil.copytree = real_copytree
    copied = []
    def copy(s, d, *aa, **kk):
        if copied:
            raise KeyboardInterrupt
        copied.append(d)
        return shutil.copy2(s, d)
    k["copy_function"] = copy
    return real_copytree(source, dest, *a, **k)
shutil.copytree = racing if mode == "race" else interrupting
err, saved = io.StringIO(), sys.stderr
sys.stderr = err
try:
    code = module.main(["spawn", "--run", "run-b4c", "--lane", lane_id, "--class", "critic", "--brief", brief,
                        "--stage-from", src, "--codex", codex, "--reason", "(a) suite", "--choice-reason", "suite pick",
                        "--delegation", "single", "--delegation-src", "head", "--viewer", "none",
                        "--silence-s", "0", "--deadline-s", "60"])
    out = "returned%s" % code
except SystemExit as exc:
    out = "exit%s" % exc.code
except KeyboardInterrupt:
    out = "interrupted"
finally:
    sys.stderr = saved
    shutil.copytree = real_copytree
rows = []
if os.path.isdir(stage):
    for base, dirs, names in os.walk(stage):
        for name in names:
            path = os.path.join(base, name)
            with open(path) as handle:
                rows.append("%s=%s" % (os.path.relpath(path, stage), handle.read().strip()))
held = ",".join(sorted(rows)) if rows else ("empty" if os.path.isdir(stage) else "absent")
attempts = [n for n in os.listdir(store) if n.startswith(".run-b4c-cwd-%s.attempt-" % lane_id)]
print(out, "stage:" + held, "attempts:%d" % len(attempts), "probe:" + ("PROBE-FAILED" if "PROBE FAILED" in err.getvalue() else "none"))
B4LF_INPROC_END
}
LF1=$(lf_inproc race RACE1)
if [ "$LF1" = "exit2 stage:competitor.txt=COMPETITOR-BYTES-1,deep/theirs.md=COMPETITOR-BYTES-2 attempts:0 probe:PROBE-FAILED" ] \
   && [ "$(lanes_in RACE1)" = 0 ]; then
  pass "B4LF-01 a losing staging attempt, whose stage another attempt filled just before its copy, refuses (exit 2, PROBE FAILED, no record line): every competing byte survives and its own copy is gone"
else fail "B4LF-01 the staging race" "$LF1 lines=$(lanes_in RACE1)"; fi
CODEX_SHIM_MODE=ok b4spawn RACE2 "$LFB" --stage-from "$T/lfsrc"
if [ $B4RC -eq 0 ] && [ -f "$SR4/run-b4c-cwd-RACE2/sub/c.md" ] && [ -z "$(ls -A "$SR4" | grep '^\.run-b4c-cwd-RACE2\.attempt-')" ]; then
  pass "B4LF-01b the same spawn with no competitor stages and completes, leaving no attempt directory (the control for B4LF-01)"
else fail "B4LF-01b the uncontested spawn" "rc=$B4RC $B4O"; fi
# An interrupt after one copied file, with an empty stage left by an earlier attempt and another lane's
# stage and a store file beside it: what the attempt owned goes, everything that was there stays.
mkdir -p "$SR4/run-b4c-cwd-INT1" "$SR4/run-b4c-cwd-KEEP8"
printf 'KEEP-8\n' > "$SR4/run-b4c-cwd-KEEP8/keep.txt"; printf 'KEEP-9\n' > "$SR4/run-b4c-keep9.txt"
LF8=$(lf_inproc interrupt INT1)
if [ "$LF8" = "interrupted stage:empty attempts:0 probe:none" ] && [ "$(lanes_in INT1)" = 0 ] \
   && grep -qx 'KEEP-8' "$SR4/run-b4c-cwd-KEEP8/keep.txt" && grep -qx 'KEEP-9' "$SR4/run-b4c-keep9.txt"; then
  pass "B4LF-08 an interrupt after one copied file leaves nothing the attempt owned and no record line; the empty stage it found, another lane's stage and a store file survive"
else fail "B4LF-08 the interrupted copy" "$LF8 lines=$(lanes_in INT1)"; fi
CODEX_SHIM_MODE=ok b4spawn INT1 "$LFB" --stage-from "$T/lfsrc"
if [ $B4RC -eq 0 ] && [ -f "$SR4/run-b4c-cwd-INT1/sub/c.md" ] && [ "$(field "$REC4" INT1 lane-closed exit_class)" = '"completed"' ]; then
  pass "B4LF-08b a same-id retry after the interrupt stages and completes"
else fail "B4LF-08b the retry" "rc=$B4RC $B4O"; fi

# Finding 2. A fixture vault holds the stage source, so one input can be declared absolute and
# vault-relative; its critic definition is the real one, through the vault's link.
mkdir -p "$T/lfvault/panel/sub"; ln -s "$VROOT/.claude" "$T/lfvault/.claude"
printf 'PANEL-X\n' > "$T/lfvault/panel/x.md"; printf 'PANEL-Y\n' > "$T/lfvault/panel/sub/y.md"
printf 'PANEL-EXCLUDED\n' > "$T/lfvault/panel/excluded.md"
LFVR=$(cd "$T/lfvault" && pwd -P)
lf2(){ # lane, brief text, extra... -> B4O, B4RC (a spawn on the fixture vault, staged from its panel without excluded.md)
  L=$1; BR=$(b4brief "lf2-$1" "$2"); shift 2
  B4O=$(CODEX_SHIM_MODE=ok CLAUDE_PROJECT_DIR="$T/lfvault" "$PY" "$ADAPTER" spawn --run run-b4c --lane "$L" --class critic --brief "$BR" \
        "${B4C[@]}" --stage-from "$T/lfvault/panel" --stage-exclude excluded.md "$@" 2>&1); B4RC=$?; }
lf2in(){ # lane -> "<line of the prompt's READ+> | <inputs_checked path made relative to the lane's stage>, staged=<bool>"
  "$PY" - "$REC4" "$1" "$SR4/run-b4c-cwd-$1" <<'B4LF_INPUTS_END'
import json, os, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
opened = [r for r in rows if r.get("lane") == sys.argv[2] and r.get("event") == "lane-open"]
if not opened:
    print("no lane-open")
    sys.exit(0)
r = opened[-1]
prompt = open(r["prompt_file"], encoding="utf-8").read()
reads = [l.strip() for l in prompt.splitlines() if "READ+:" in l]
stage = os.path.realpath(sys.argv[3])
inputs = r.get("inputs_checked") or [{}]
rel = os.path.relpath(inputs[0].get("path", ""), stage) if inputs[0].get("path") else "none"
print("%s | %s, staged=%s, declarations=%d" % (" / ".join(reads).replace(stage, "<STAGE>"), rel, inputs[0].get("staged"),
                                               len(r.get("staged_declarations") or [])))
B4LF_INPUTS_END
}
lf2 LF2A "x\nREAD+: $T/lfvault/panel/x.md\n"; LF2A_RC=$B4RC
lf2 LF2R 'x\nREAD+: panel/x.md\n'; LF2R_RC=$B4RC
LF2A=$(lf2in LF2A); LF2R=$(lf2in LF2R)
if [ $LF2A_RC -eq 0 ] && [ $LF2R_RC -eq 0 ] && [ "$LF2A" = 'READ+: <STAGE>/x.md | x.md, staged=True, declarations=1' ] && [ "$LF2R" = "$LF2A" ]; then
  pass "B4LF-02 an absolute and a vault-relative declaration of one source file name the same staged file in the prompt the lane receives and in inputs_checked (staged), and the record names the rewritten line"
else fail "B4LF-02 the canonical input" "abs rc=$LF2A_RC [$LF2A] rel rc=$LF2R_RC [$LF2R]"; fi
lf2 LF2B "x\nREAD+: $T/lfvault/panel/excluded.md\n"; LF2B_RC=$B4RC; LF2B_O=$B4O
lf2 LF2C 'x\nREAD+: panel/excluded.md\n'
if [ $LF2B_RC -eq 2 ] && [ $B4RC -eq 2 ] && printf '%s' "$LF2B_O" | grep -q 'does not exist in the staged copy' \
   && printf '%s' "$B4O" | grep -q 'does not exist in the staged copy' && [ "$(lanes_in LF2B)" = 0 ] && [ "$(lanes_in LF2C)" = 0 ] \
   && [ ! -e "$SR4/run-b4c-cwd-LF2B" ] && [ ! -e "$SR4/run-b4c-cwd-LF2C" ]; then
  pass "B4LF-02b an excluded input refuses whether declared absolute or vault-relative (exit 2, no record line, no copy left)"
else fail "B4LF-02b the excluded input" "abs rc=$LF2B_RC rel rc=$B4RC: $(printf '%s' "$B4O" | tail -1)"; fi
lf2 LF2D "x\nREAD+: $T/lfvault/panel/\n"
LF2D=$(lf2in LF2D)
LF2DP=$(field "$REC4" LF2D lane-open prompt_file | tr -d '"')
if [ $B4RC -eq 0 ] && [ "$LF2D" = 'READ+: <STAGE>/ | ., staged=True, declarations=1' ] && [ ! -e "$SR4/run-b4c-cwd-LF2D/excluded.md" ] \
   && [ -f "$SR4/run-b4c-cwd-LF2D/x.md" ] && ! grep -q "$T/lfvault/panel\|$LFVR/panel" "$LF2DP"; then
  pass "B4LF-02c a declared source directory is delivered as the staged copy, which lacks the excluded sibling: the source never reaches the lane's reading list"
else fail "B4LF-02c the delivered reading scope" "rc=$B4RC [$LF2D] $(grep -n 'lfvault' "$LF2DP" | head -2)"; fi
# A resumed staged pass reads the follow-up brief's source paths as its recorded copy's.
B=$(b4brief lf2res 'Continue.\nREAD+: panel/sub/y.md\n')
LF2E=$(CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-lf2a CLAUDE_PROJECT_DIR="$T/lfvault" "$PY" "$ADAPTER" resume --run run-b4c --lane LF2A \
       --brief "$B" --codex "$T/bin/codex" --viewer none --silence-s 0 --deadline-s 60 2>&1); LF2E_RC=$?
LF2EI=$(field "$REC4" LF2A lane-resumed inputs_checked)
B=$(b4brief lf2resx 'Continue.\nREAD+: panel/excluded.md\n')
NRES=$(count "$REC4" LF2A lane-resumed)
LF2F=$(CODEX_SHIM_MODE=ok CLAUDE_PROJECT_DIR="$T/lfvault" "$PY" "$ADAPTER" resume --run run-b4c --lane LF2A \
       --brief "$B" --codex "$T/bin/codex" --viewer none --silence-s 0 --deadline-s 60 2>&1); LF2F_RC=$?
if [ $LF2E_RC -eq 0 ] && grep -q "READ+: $TR/store/spawn-records/run-b4c-cwd-LF2A/sub/y.md" "$CODEX_SHIM_PROMPT" \
   && [ "$LF2EI" = "[{\"line\": 2, \"path\": \"$TR/store/spawn-records/run-b4c-cwd-LF2A/sub/y.md\", \"kind\": \"file\", \"bytes\": 8, \"staged\": true}]" ] \
   && [ $LF2F_RC -eq 2 ] && printf '%s' "$LF2F" | grep -q 'does not exist in the staged copy' && [ "$(count "$REC4" LF2A lane-resumed)" = "$NRES" ]; then
  pass "B4LF-02d a resumed staged pass checks, records and delivers a vault-relative source path as its recorded copy's file, and refuses an excluded one with nothing written"
else fail "B4LF-02d the resumed pass" "rc=$LF2E_RC/$LF2F_RC inputs=$LF2EI $(printf '%s' "$LF2F" | tail -1)"; fi

# Finding 9. The executable answers `--version` and then takes its own execute bit away, so the
# process start that follows fails with the OSError a broken install raises.
mkdir -p "$T/bin-lf"
printf '#!/bin/sh\nif [ "${1:-}" = "--version" ]; then echo "codex-cli 0.0.0-shim"; chmod -x "$0"; exit 0; fi\nexit 0\n' > "$T/bin-lf/codex"
chmod +x "$T/bin-lf/codex"
B=$(b4brief lf09 'x\nCONTROL+: REPORT-OK in <<REPORT>>\n')
"$PY" "$ADAPTER" spawn --run run-b4c --lane LF09 --class critic --brief "$B" --cwd "$T/work" --codex "$T/bin-lf/codex" \
  --reason "(a) suite" --choice-reason "suite pick" --delegation single --delegation-src head --viewer none --silence-s 0 \
  --deadline-s 60 >"$T/lf09.out" 2>"$T/lf09.err"; LF09_RC=$?
LF09V=$(field "$REC4" LF09 lane-closed controls_deferred | "$PY" -c 'import json,sys; v=json.load(sys.stdin) or [{}]; print(v[0].get("result"), "spawn-failed" in str(v[0].get("why")))')
if [ $LF09_RC -eq 3 ] && [ "$(field "$REC4" LF09 lane-closed exit_class)" = '"spawn-failed"' ] && [ "$LF09V" = "unverified True" ] \
   && grep -q 'could not start the lane process' "$T/lf09.err" && grep -q 'report controls UNVERIFIED 1 of 1' "$T/lf09.err"; then
  pass "B4LF-09 a Codex process that cannot start closes spawn-failed with its pending report control unverified, on the close line and stderr, the exit still 3"
else fail "B4LF-09 the failed start" "rc=$LF09_RC verdict=$LF09V $(tr '\n' '|' < "$T/lf09.err" | cut -c1-300)"; fi
# G59: a Codex close names its harness and marks what plan usage leaves out (register 2026-10-13 06:43),
# the failed start included, and the fields beside the marks stay as they were.
G59NA=$(field "$REC4" LF09 lane-closed not_applicable)
if [ "$(field "$REC4" LF09 lane-closed harness)" = '"codex"' ] \
   && printf '%s' "$G59NA" | grep -q '"soft_usd": "plan usage is never priced' && printf '%s' "$G59NA" | grep -q '"denials.fence": "a Codex lane has no fence channel' \
   && ! printf '%s' "$G59NA" | grep -q 'sandbox'; then
  pass "G59 a Codex close names its harness and marks the soft line and the constant channels not applicable, never its sandbox channel"
else fail "G59 the Codex close" "$(field "$REC4" LF09 lane-closed harness) $G59NA"; fi
chmod +x "$T/bin-lf/codex"

# ============================== the second launcher fold (review CR-B4L2) =========================
# Finding 1: the rename into place, each removal of a copy at the stage path and a refresh that
# copies hold the stage's one lock (`.<run>-cwd-<lane>.lock` beside the stage), and a removal empties
# only the directory it checked. lf2_stage drives the module under test in this process: this
# attempt's copy is made and released by the real stage_copy and Stage.release. The competitor is a
# second process running the module's own stage_copy (it takes the lock), or a rename made here that
# ignores the lock; each publishes right after this attempt's identity check returns. A held lock is
# taken here on the lock file, with the module's wait bound cut to one second.
mkdir -p "$T/lf2empty" "$T/lf2comp/deep"
printf 'COMPETITOR-BYTES-1\n' > "$T/lf2comp/competitor.txt"; printf 'COMPETITOR-BYTES-2\n' > "$T/lf2comp/deep/theirs.md"
lf2_stage(){ # mode lane [refresh source] [refresh brief] -> one line of outcomes
  env CODEX_SHIM_MODE=ok "$PY" - "$ADAPTER" "$1" "$2" "$SR4" "$T/lf2empty" "$T/lfsrc" "$T/lf2comp" "$LFB" "$T/bin/codex" "$T" \
    "${3:-}" "${4:-}" <<'B4LF2_STAGE_END'
import argparse, fcntl, importlib.util, io, os, subprocess, sys, time
sys.dont_write_bytecode = True
adapter, mode, lane_id, store, empty_src, full_src, comp_src, brief, codex, scratch, refresh_src, refresh_brief = sys.argv[1:13]
spec = importlib.util.spec_from_file_location("codex_lane_lf2_" + mode.replace("-", "_"), adapter)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
store = os.path.realpath(store)                  # the module records and names real paths
stage = os.path.join(store, "run-b4c-cwd-" + lane_id)
lock_path = os.path.join(store, ".run-b4c-cwd-%s.lock" % lane_id)   # beside the stage: the name the fix gives it
COMPETITOR = r'''
import argparse, importlib.util, os, sys
sys.dont_write_bytecode = True
adapter, lane_id, src, marker = sys.argv[1:5]
spec = importlib.util.spec_from_file_location("codex_lane_lf2_competitor", adapter)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
if hasattr(module, "fcntl"):
    real = module.fcntl
    class Watched(object):
        LOCK_EX, LOCK_NB, LOCK_UN = real.LOCK_EX, real.LOCK_NB, real.LOCK_UN
        @staticmethod
        def flock(fd, op):
            try:
                return real.flock(fd, op)
            except OSError:
                open(marker, "w").close()      # this attempt is waiting on the stage lock
                raise
    module.fcntl = Watched
try:
    module.stage_copy(argparse.Namespace(stage_from=src, run="run-b4c", lane=lane_id, record=None,
                                         stage_exclude=None, dry_run=False))
    print("published")
except SystemExit as exc:
    print("exit%s" % exc.code)
'''
def ns(src):
    return argparse.Namespace(stage_from=src, run="run-b4c", lane=lane_id, record=None, stage_exclude=None, dry_run=False)
def holds(path):
    if not os.path.isdir(path):
        return "absent"
    rows = []
    for base, dirs, names in os.walk(path):
        for name in names:
            with open(os.path.join(base, name)) as handle:
                rows.append("%s=%s" % (os.path.relpath(os.path.join(base, name), path), handle.read().strip()))
    return ",".join(sorted(rows)) or "empty"
def attempts():
    return len([n for n in os.listdir(store) if n.startswith(".run-b4c-cwd-%s.attempt-" % lane_id)])
def take_lock():
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return fd
def quiet(call):
    err, saved = io.StringIO(), (sys.stdout, sys.stderr)
    sys.stdout, sys.stderr = io.StringIO(), err
    try:
        value = call()
        outcome = "returned%s" % (value if isinstance(value, int) else "")
    except SystemExit as exc:
        outcome = "exit%s" % exc.code
    finally:
        sys.stdout, sys.stderr = saved
    return outcome, err.getvalue()
def main_args(*words):
    return list(words) + ["--codex", codex, "--viewer", "none", "--silence-s", "0", "--deadline-s", "60"]
out = []
if mode in ("locked", "raw"):
    a = module.stage_copy(ns(empty_src))          # this attempt's copy, an empty tree, in place
    marker = os.path.join(scratch, "lf2-waiting-" + lane_id)
    fired, proc = [], []
    def compete():
        fired.append(1)
        if mode == "raw":     # a writer that ignores the lock renames its populated copy onto the path
            theirs = os.path.join(store, ".lf2-raw-" + lane_id)
            os.makedirs(os.path.join(theirs, "deep"))
            for rel, body in (("competitor.txt", "COMPETITOR-BYTES-1"), (os.path.join("deep", "theirs.md"), "COMPETITOR-BYTES-2")):
                with open(os.path.join(theirs, rel), "w") as handle:
                    handle.write(body + "\n")
            os.rename(theirs, stage)
            return
        # another attempt publishes through the module's own stage_copy, in a second process: this
        # waits until it has published or is seen waiting on the stage lock
        proc.append(subprocess.Popen([sys.executable, "-c", COMPETITOR, adapter, lane_id, comp_src, marker],
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True))
        deadline = time.monotonic() + 30
        while proc[0].poll() is None and not os.path.exists(marker) and time.monotonic() < deadline:
            time.sleep(0.02)
    real_check = module.Stage.holds_copy
    def hooked(self):
        result = real_check(self)
        if result and self is a and not fired:
            compete()                                 # right after the identity check returned
        return result
    module.Stage.holds_copy = hooked
    left = a.release()
    module.Stage.holds_copy = real_check
    comp = "none"
    if proc:
        try:
            text, _ = proc[0].communicate(timeout=120)
            comp = (text.strip().splitlines() or ["silent"])[-1]
        except subprocess.TimeoutExpired:
            proc[0].kill()
            comp = "hung"
    out = ["release:" + ("ok" if left is None else "refused"), "competitor:" + comp,
           "waited:" + ("yes" if os.path.exists(marker) else "no"), "fired:%d" % len(fired),
           "stage:" + holds(stage), "attempts:%d" % attempts()]
elif mode == "uncontested":
    a = module.stage_copy(ns(full_src))
    left = a.release()
    out = ["release:" + ("ok" if left is None else "refused"), "stage:" + holds(stage)]
    os.makedirs(stage)          # an empty stage found in place: the copy replaces it, and its removal leaves it empty
    a = module.stage_copy(ns(full_src))
    filled = holds(stage)
    left = a.release()
    out += ["found-empty: filled:" + filled, "release:" + ("ok" if left is None else "refused"),
            "stage:" + holds(stage), "attempts:%d" % attempts(),
            "lock-file:" + ("left" if os.path.lexists(lock_path) else "none")]
elif mode == "held-release":
    a = module.stage_copy(ns(full_src))
    fd = take_lock()
    module.STAGE_LOCK_WAIT_S = 1
    began = time.monotonic()
    left = a.release()
    waited = time.monotonic() - began
    kept = holds(stage)
    os.close(fd)                # the lock is free again: the same release now removes the copy
    again = a.release()
    out = ["release:" + ("refused" if left else "ok"),
           "named:" + ("yes" if left and lock_path in left and "nothing at the stage path" in left else "no"),
           "bounded:" + ("yes" if 0.9 <= waited < 10 else "no(%.1fs)" % waited), "kept:" + kept,
           "then:" + ("ok" if again is None else "refused"), "stage:" + holds(stage)]
elif mode == "held-dry-run":
    module.STAGE_LOCK_WAIT_S = 1
    real_print, held = module.print_dry_run, []
    def printing(prep, line):
        real_print(prep, line)
        held.append(take_lock())  # the copy is in place and checked; its removal comes next
    module.print_dry_run = printing
    outcome, err = quiet(lambda: module.main(main_args(
        "spawn", "--run", "run-b4c", "--lane", lane_id, "--class", "critic", "--brief", brief, "--stage-from", full_src,
        "--reason", "(a) suite", "--choice-reason", "suite pick", "--delegation", "single", "--delegation-src", "head",
        "--dry-run")))
    for fd in held:
        os.close(fd)
    out = [outcome, "said:" + ("yes" if "the dry run's nothing at the stage path" in err and lock_path in err else "no"),
           "stage:" + holds(stage), "attempts:%d" % attempts()]
elif mode == "held-publish":
    os.makedirs(stage)          # an empty stage the copy would replace
    inode = os.lstat(stage).st_ino
    fd = take_lock()
    module.STAGE_LOCK_WAIT_S = 1
    outcome, err = quiet(lambda: module.stage_copy(ns(full_src)))
    os.close(fd)
    out = [outcome, "said:" + ("yes" if "putting a staged copy in place was not done" in err and lock_path in err else "no"),
           "stage:" + holds(stage), "same-dir:" + ("yes" if os.path.isdir(stage) and os.lstat(stage).st_ino == inode else "no"),
           "attempts:%d" % attempts()]
elif mode == "held-refresh":
    fd = take_lock()
    module.STAGE_LOCK_WAIT_S = 1
    outcome, err = quiet(lambda: module.main(main_args(
        "resume", "--run", "run-b4c", "--lane", lane_id, "--brief", refresh_brief, "--stage-from", refresh_src)))
    os.close(fd)
    out = [outcome, "said:" + ("yes" if "refreshing the staged copy from" in err and lock_path in err else "no"),
           "stage:" + holds(stage)]
print(" ".join(out))
B4LF2_STAGE_END
}
LF21=$(lf2_stage locked LF2L1)
if [ "$LF21" = "release:ok competitor:published waited:yes fired:1 stage:competitor.txt=COMPETITOR-BYTES-1,deep/theirs.md=COMPETITOR-BYTES-2 attempts:0" ]; then
  pass "B4LF2-01 another attempt that puts its populated copy in place right after this attempt's identity check, by the module's own rename in a second process, waits on the stage lock and lands once this attempt's copy has gone: every competing byte survives"
else fail "B4LF2-01 a competitor through the lock" "$LF21"; fi
LF21B=$(lf2_stage raw LF2L2)
if [ "$LF21B" = "release:ok competitor:none waited:no fired:1 stage:competitor.txt=COMPETITOR-BYTES-1,deep/theirs.md=COMPETITOR-BYTES-2 attempts:0" ]; then
  pass "B4LF2-01b a writer that ignores the lock and renames its populated copy onto the path right after the identity check keeps every byte: the removal empties only the directory it checked"
else fail "B4LF2-01b a competitor outside the lock" "$LF21B"; fi
LF21C=$(lf2_stage uncontested LF2L3)
if [ "$LF21C" = "release:ok stage:absent found-empty: filled:a.md=LF-ONE,b.md=LF-TWO,sub/c.md=LF-THREE release:ok stage:empty attempts:0 lock-file:none" ]; then
  pass "B4LF2-01c uncontested, the release still removes this attempt's copy, leaves an empty stage it found as it found it, and leaves no lock file (the control for B4LF2-01 and 01b)"
else fail "B4LF2-01c the uncontested release" "$LF21C"; fi
LF21D=$(lf2_stage held-release LF2L4)
if [ "$LF21D" = "release:refused named:yes bounded:yes kept:a.md=LF-ONE,b.md=LF-TWO,sub/c.md=LF-THREE then:ok stage:absent" ]; then
  pass "B4LF2-01d with the stage lock held elsewhere, the release refuses within its bound, names the lock and deletes nothing; once the lock is free the same release removes the copy"
else fail "B4LF2-01d the held lock at a release" "$LF21D"; fi
LF21E=$(lf2_stage held-dry-run LF2L5)
if [ "$LF21E" = "exit2 said:yes stage:a.md=LF-ONE,b.md=LF-TWO,sub/c.md=LF-THREE attempts:0" ] && [ "$(lanes_in LF2L5)" = 0 ]; then
  pass "B4LF2-01e a dry run whose removal meets a held stage lock exits 2 with PROBE FAILED naming the lock, removes nothing and writes no record line"
else fail "B4LF2-01e the held lock at a dry run's removal" "$LF21E lines=$(lanes_in LF2L5)"; fi
LF21F=$(lf2_stage held-publish LF2L6)
if [ "$LF21F" = "exit2 said:yes stage:empty same-dir:yes attempts:0" ]; then
  pass "B4LF2-01f with the stage lock held elsewhere, putting a copy in place refuses within its bound: the empty stage found there is the same directory, still empty, and the attempt's own copy is gone"
else fail "B4LF2-01f the held lock at publication" "$LF21F"; fi
# A refresh that copies holds the lock as well: a lane staged from lf2ref/, whose b.md then changes.
mkdir -p "$T/lf2ref"; printf 'LF-ONE\n' > "$T/lf2ref/a.md"; printf 'LF2-B-OLD\n' > "$T/lf2ref/b.md"
CODEX_SHIM_MODE=ok b4spawn LF2RF "$(b4brief lf2rf 'x\n')" --stage-from "$T/lf2ref"; LF2RF_RC=$B4RC
printf 'LF2-B-NEW\n' > "$T/lf2ref/b.md"
LF2RFB=$(b4brief lf2rf-refresh 'Refresh.\n')
NRF=$(count "$REC4" LF2RF lane-resumed)
LF21G=$(lf2_stage held-refresh LF2RF "$T/lf2ref" "$LF2RFB")
NRF2=$(count "$REC4" LF2RF lane-resumed)
env CODEX_SHIM_MODE=ok "$PY" "$ADAPTER" resume --run run-b4c --lane LF2RF --brief "$LF2RFB" --stage-from "$T/lf2ref" --codex "$T/bin/codex" \
  --viewer none --silence-s 0 --deadline-s 60 >"$T/lf2rf.out" 2>&1; LF2RF2_RC=$?
if [ $LF2RF_RC -eq 0 ] && [ "$LF21G" = "exit2 said:yes stage:a.md=LF-ONE,b.md=LF2-B-OLD" ] && [ "$NRF2" = "$NRF" ] \
   && [ $LF2RF2_RC -eq 0 ] && grep -qx 'LF2-B-NEW' "$SR4/run-b4c-cwd-LF2RF/b.md"; then
  pass "B4LF2-01g a resume's refresh that meets a held stage lock refuses within its bound with nothing refreshed and no record line; with the lock free the same refresh copies (its control)"
else fail "B4LF2-01g the held lock at a refresh" "spawn rc=$LF2RF_RC [$LF21G] lines $NRF->$NRF2 control rc=$LF2RF2_RC $(tail -1 "$T/lf2rf.out")"; fi

# Finding 2. A lane spawned from the fixture vault's panel/ (excluded.md left out), its copy then
# refreshed from panelB/ by a recorded resume, which carries the exclusion. An ordinary resume
# afterwards reads a panelB/ path, absolute or vault-relative, as the copy's file: checked, recorded
# and delivered there, while panelB/'s excluded file refuses. panel/ stays mapped as well (the
# control: a mapping that followed the refresh alone would hand over the spawn source's excluded file).
mkdir -p "$T/lfvault/panelB/sub"
printf 'PANELB-BX\n' > "$T/lfvault/panelB/bx.md"; printf 'PANELB-BY\n' > "$T/lfvault/panelB/sub/by.md"
printf 'PANELB-EXCLUDED\n' > "$T/lfvault/panelB/excluded.md"
lf2 LF2G 'x\n'; LF2G_RC=$B4RC
B=$(b4brief lf2g-refresh 'Refresh.\n')
env CODEX_SHIM_MODE=ok CLAUDE_PROJECT_DIR="$T/lfvault" "$PY" "$ADAPTER" resume --run run-b4c --lane LF2G --brief "$B" \
  --stage-from "$T/lfvault/panelB" --codex "$T/bin/codex" --viewer none --silence-s 0 --deadline-s 60 >"$T/lf2g-refresh.out" 2>&1; LF2GR_RC=$?
lf2res(){ # lane, brief name, brief text -> LF2O, LF2RC (an ordinary resume on the fixture vault)
  BR=$(b4brief "$2" "$3")
  LF2O=$(env CODEX_SHIM_MODE=ok CLAUDE_PROJECT_DIR="$T/lfvault" "$PY" "$ADAPTER" resume --run run-b4c --lane "$1" --brief "$BR" \
         --codex "$T/bin/codex" --viewer none --silence-s 0 --deadline-s 60 2>&1); LF2RC=$?; }
lf2rin(){ # lane -> "<the prompt's READ+ lines> | <inputs_checked[0] relative to the stage>, staged=<bool>, declarations=<n>" of its latest lane-resumed
  "$PY" - "$REC4" "$1" "$SR4/run-b4c-cwd-$1" <<'B4LF2_RESUMED_END'
import json, os, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
resumed = [r for r in rows if r.get("lane") == sys.argv[2] and r.get("event") == "lane-resumed"]
if not resumed:
    print("no lane-resumed")
    sys.exit(0)
r = resumed[-1]
prompt = open(r["prompt_file"], encoding="utf-8").read()
reads = [l.strip() for l in prompt.splitlines() if "READ+:" in l]
stage = os.path.realpath(sys.argv[3])
inputs = r.get("inputs_checked") or [{}]
rel = os.path.relpath(inputs[0].get("path", ""), stage) if inputs[0].get("path") else "none"
print("%s | %s, staged=%s, declarations=%d" % (" / ".join(reads).replace(stage, "<STAGE>"), rel, inputs[0].get("staged"),
                                               len(r.get("staged_declarations") or [])))
B4LF2_RESUMED_END
}
lf2res LF2G lf2g-rel 'Continue.\nREAD+: panelB/bx.md\n'; LF2G1_RC=$LF2RC; LF2G1=$(lf2rin LF2G)
lf2res LF2G lf2g-abs "Continue.\nREAD+: $T/lfvault/panelB/sub/by.md\n"; LF2G2_RC=$LF2RC; LF2G2=$(lf2rin LF2G)
if [ $LF2G_RC -eq 0 ] && [ $LF2GR_RC -eq 0 ] && [ $LF2G1_RC -eq 0 ] && [ $LF2G2_RC -eq 0 ] \
   && [ "$LF2G1" = 'READ+: <STAGE>/bx.md | bx.md, staged=True, declarations=1' ] \
   && [ "$LF2G2" = 'READ+: <STAGE>/sub/by.md | sub/by.md, staged=True, declarations=1' ]; then
  pass "B4LF2-02 after a spawn from panel/ and a recorded refresh from panelB/, an ordinary resume checks, records and delivers a panelB/ input, vault-relative or absolute, as the copy's file"
else fail "B4LF2-02 the refreshed source" "rc=$LF2G_RC/$LF2GR_RC/$LF2G1_RC/$LF2G2_RC rel [$LF2G1] abs [$LF2G2] $(tail -1 "$T/lf2g-refresh.out")"; fi
NRESG=$(count "$REC4" LF2G lane-resumed)
lf2res LF2G lf2g-xrel 'Continue.\nREAD+: panelB/excluded.md\n'; LF2X1_RC=$LF2RC; LF2X1=$LF2O
lf2res LF2G lf2g-xabs "Continue.\nREAD+: $T/lfvault/panelB/excluded.md\n"; LF2X2_RC=$LF2RC; LF2X2=$LF2O
if [ $LF2X1_RC -eq 2 ] && [ $LF2X2_RC -eq 2 ] && printf '%s' "$LF2X1" | grep -q 'does not exist in the staged copy' \
   && printf '%s' "$LF2X2" | grep -q 'does not exist in the staged copy' && [ "$(count "$REC4" LF2G lane-resumed)" = "$NRESG" ] \
   && [ ! -e "$SR4/run-b4c-cwd-LF2G/excluded.md" ]; then
  pass "B4LF2-02b panelB/'s excluded file, declared vault-relative or absolute, refuses on that resume (exit 2, no record line): the copy lacks it"
else fail "B4LF2-02b the refreshed source's excluded file" "rc=$LF2X1_RC/$LF2X2_RC $(printf '%s' "$LF2X1" | tail -1) | $(printf '%s' "$LF2X2" | tail -1)"; fi
lf2res LF2G lf2g-arel 'Continue.\nREAD+: panel/excluded.md\n'; LF2A1_RC=$LF2RC; LF2A1=$LF2O
lf2res LF2G lf2g-akeep 'Continue.\nREAD+: panel/x.md\n'; LF2A2_RC=$LF2RC; LF2A2=$(lf2rin LF2G)
if [ $LF2A1_RC -eq 2 ] && printf '%s' "$LF2A1" | grep -q 'does not exist in the staged copy' && [ $LF2A2_RC -eq 0 ] \
   && [ "$LF2A2" = 'READ+: <STAGE>/x.md | x.md, staged=True, declarations=1' ]; then
  pass "B4LF2-02c after the refresh the spawn's own source stays mapped: panel/'s excluded file still refuses and its included file is the copy's (the control for B4LF2-02)"
else fail "B4LF2-02c the spawn's source after a refresh" "rc=$LF2A1_RC/$LF2A2_RC $(printf '%s' "$LF2A1" | tail -1) [$LF2A2]"; fi
# The record reading itself: the lane-open's source, then each refresh that copied into the same copy;
# a refresh that only counted, an ordinary resume, another stage and another lane are passed over, and
# a source met again moves to its latest place.
LF2S=$("$PY" - "$ADAPTER" "$T" <<'B4LF2_SOURCES_END'
import importlib.util, json, os, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("codex_lane_lf2_sources", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
record = os.path.join(sys.argv[2], "lf2-sources.jsonl")
stage = os.path.join(sys.argv[2], "store", "spawn-records", "run-x-cwd-L")
def line(event, lane="L", stage_rec=None):
    return {"event": event, "lane": lane, "stage": stage_rec}
rows = [line("lane-open", stage_rec={"staged_from": "/src/A", "stage_dir": stage}),
        line("lane-resumed", stage_rec={"staged_from": "/src/B", "stage_dir": stage, "refreshed": {"copied": True}}),
        line("lane-resumed", stage_rec={"staged_from": "/src/C", "stage_dir": stage, "refreshed": {"copied": False}}),
        line("lane-resumed"),
        line("lane-resumed", stage_rec={"staged_from": "/src/D", "stage_dir": stage + "-other", "refreshed": {"copied": True}}),
        line("lane-resumed", lane="M", stage_rec={"staged_from": "/src/E", "stage_dir": stage, "refreshed": {"copied": True}}),
        line("lane-resumed", stage_rec={"staged_from": "/src/A", "stage_dir": stage, "refreshed": {"copied": True}})]
with open(record, "w") as handle:
    for row in rows:
        handle.write(json.dumps(row) + "\n")
reader = getattr(module, "recorded_stage_sources", None)
print(reader(record, "L", stage) if reader else "no reader")
B4LF2_SOURCES_END
)
if [ "$LF2S" = "['/src/B', '/src/A']" ]; then
  pass "B4LF2-02d the copy's sources by the record: the lane-open's, then each refresh that copied into that copy, a source met again in its latest place; an uncopied refresh, an ordinary resume, another stage and another lane add none"
else fail "B4LF2-02d the recorded sources" "$LF2S"; fi

# ============================== the third launcher fold (review CR-B4L3) ==========================
# Finding 3: the stage lock's bound holds on every retry. A controlled clock advances ten seconds a
# reading, and the lock file's identity reads as replaced on each take (or on the first only).
mkdir -p "$T/lf3lock"
LF3L=$("$PY" - "$ADAPTER" "$T/lf3lock" <<'B4LF3_LOCK_END'
import importlib.util, os, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("codex_lane_lf3_lock", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
# Each case has a stage path of its own, so the second never meets what the first left (a loop stopped
# by this harness keeps its descriptor, and with it the lock).
dests = {None: os.path.join(sys.argv[2], "run-x-cwd-L"), 1: os.path.join(sys.argv[2], "run-x-cwd-M")}
real_os, real_time = module.os, module.time
class Clock(object):
    def __init__(self):
        self.t = 1000.0
    def monotonic(self):
        self.t += 10.0
        return self.t
    def sleep(self, seconds):
        self.t += seconds
    def __getattr__(self, name):
        return getattr(real_time, name)
class Replaced(object):
    def __init__(self, times):
        self.times, self.n, self.lock = times, 0, module.stage_lock_path(dests[times])
    def lstat(self, path, *a, **k):
        info = real_os.lstat(path, *a, **k)
        if path == self.lock and (self.times is None or self.n < self.times):
            self.n += 1
            if self.n > 500:
                raise RuntimeError("never refused")
            class Other(object):
                st_dev, st_ino = info.st_dev, info.st_ino + 1
            return Other()
        return info
    def __getattr__(self, name):
        return getattr(real_os, name)
def take(times):
    module.os, module.time = Replaced(times), Clock()
    entered = []
    try:
        with module.stage_lock(dests[times], "a controlled test"):
            entered.append(1)
        outcome = "taken"
    except module.StageLockRefused:
        outcome = "refused"
    except RuntimeError:
        outcome = "looped"
    finally:
        tries = module.os.n
        module.os, module.time = real_os, real_time
    return "%s entered:%d tries:%s" % (outcome, len(entered), "few" if tries <= 10 else tries)
always = take(None)
once = take(1)
print("always:" + always, "once:" + once,
      "lock-file:" + ("left" if os.path.lexists(module.stage_lock_path(dests[1])) else "none"))
B4LF3_LOCK_END
)
case "$LF3L" in
  "always:refused entered:0 tries:few "*) pass "B4LF3-08 a lock whose file reads as replaced on every take, under a clock that passes the bound, refuses within a few tries without entering what it guards" ;;
  *) fail "B4LF3-08 the replaced-file retries" "$LF3L" ;;
esac
case "$LF3L" in
  *" once:taken entered:1 tries:few lock-file:none") pass "B4LF3-08b one replaced-file retry, then an uncontested take: the lock is taken, the guarded step runs and the lock file goes with the lock (the control for B4LF3-08)" ;;
  *) fail "B4LF3-08b the single retry" "$LF3L" ;;
esac

# B4C-W · a verifier or builder spawn has a write scope, or says --read-only -------------------------
B=$(b4brief w01 'x\n')
"$PY" "$ADAPTER" spawn --run run-b4c --lane W01 --class verifier --brief "$B" "${B4C[@]}" --stage-from "$T/b4src" >"$T/b4c-w01.out" 2>&1; RC=$?
if [ $RC -eq 2 ] && grep -q 'no write scope' "$T/b4c-w01.out" && [ ! -e "$SR4/run-b4c-cwd-W01" ] && [ "$(lanes_in W01)" = 0 ]; then
  pass "B4C-W01 a verifier with no write scope refuses before staging and before any record line"
else fail "B4C-W01 the read-only verifier" "rc=$RC $(cat "$T/b4c-w01.out")"; fi
"$PY" "$ADAPTER" spawn --run run-b4c --lane W02 --class builder --brief "$B" "${B4C[@]}" --cwd "$T/work" >"$T/b4c-w02.out" 2>&1; RC=$?
[ $RC -eq 2 ] && grep -q 'no write scope' "$T/b4c-w02.out" && pass "B4C-W02 a builder with no write scope refuses the same way" || fail "B4C-W02 builder" "rc=$RC $(cat "$T/b4c-w02.out")"
"$PY" "$ADAPTER" spawn --run run-b4c --lane W03 --class verifier --brief "$B" "${B4C[@]}" --cwd "$T/work" --read-only --dry-run >"$T/b4c-w03.out" 2>&1; RC=$?
if [ $RC -eq 0 ] && [ "$(head -1 "$T/b4c-w03.out")" = "class: verifier · sandbox: read-only (--read-only)" ] && grep -q '"read_only": true' "$T/b4c-w03.out"; then
  pass "B4C-W03 --read-only admits a verifier read-only on purpose: the dry run's first line states the class and sandbox, and the record carries read_only"
else fail "B4C-W03 --read-only" "rc=$RC $(head -2 "$T/b4c-w03.out")"; fi
"$PY" "$ADAPTER" spawn --run run-b4c --lane W04 --class builder --brief "$B" "${B4C[@]}" --stage-from "$T/b4src" --stage-writable --dry-run >"$T/b4c-w04.out" 2>&1; RC=$?
"$PY" "$ADAPTER" spawn --run run-b4c --lane W05 --class verifier --brief "$B" "${B4C[@]}" --cwd "$T/work" --write "$T/work" --dry-run >"$T/b4c-w05.out" 2>&1; RC5=$?
if [ $RC -eq 0 ] && [ "$(head -1 "$T/b4c-w04.out")" = "class: builder · sandbox: workspace-write" ] \
   && [ $RC5 -eq 0 ] && [ "$(head -1 "$T/b4c-w05.out")" = "class: verifier · sandbox: workspace-write" ]; then
  pass "B4C-W04 a builder with --stage-writable and a verifier with --write pass, each sandbox workspace-write on the first line (the controls for B4C-W01 and W02)"
else fail "B4C-W04 the writable spawns" "rc=$RC/$RC5 $(head -1 "$T/b4c-w04.out") | $(head -1 "$T/b4c-w05.out")"; fi
"$PY" "$ADAPTER" spawn --run run-b4c --lane W06 --class builder --brief "$B" "${B4C[@]}" --cwd "$T/work" --write "$T/work" --read-only --dry-run >"$T/b4c-w06.out" 2>&1; RC=$?
[ $RC -eq 2 ] && grep -q 'drop one of them' "$T/b4c-w06.out" && pass "B4C-W06 --read-only beside --write refuses: it cannot leave a writable addition active" || fail "B4C-W06 the contradiction" "rc=$RC $(cat "$T/b4c-w06.out")"
"$PY" "$ADAPTER" spawn --run run-b4c --lane W07 --class critic --brief "$B" "${B4C[@]}" --cwd "$T/work" --dry-run >"$T/b4c-w07.out" 2>&1; RC=$?
[ $RC -eq 0 ] && [ "$(head -1 "$T/b4c-w07.out")" = "class: critic · sandbox: read-only" ] && pass "B4C-W07 a critic spawn is unaffected" || fail "B4C-W07 critic" "rc=$RC $(head -1 "$T/b4c-w07.out")"
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-w08 "$PY" "$ADAPTER" spawn --run run-b4c --lane W08 --class verifier --brief "$B" "${B4C[@]}" --cwd "$T/work" --read-only >/dev/null 2>&1
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-w08 "$PY" "$ADAPTER" resume --run run-b4c --lane W08 --beat --codex "$T/bin/codex" --viewer none >"$T/b4c-w08b.out" 2>&1; RCB=$?
"$PY" "$ADAPTER" resume --run run-b4c --lane W08 --brief "$T/follow.md" --codex "$T/bin/codex" --viewer none --write "$T/work" --silence-s 0 --deadline-s 60 >"$T/b4c-w08r.out" 2>&1; RCR=$?
if [ $RCB -eq 0 ] && [ $RCR -eq 2 ] && grep -q 'spawned --read-only' "$T/b4c-w08r.out"; then
  pass "B4C-W08 a no-work beat of a read-only verifier is unaffected, and a resume cannot add a write scope to it"
else fail "B4C-W08 the beat and the resume" "beat=$RCB resume=$RCR $(cat "$T/b4c-w08r.out" | head -2)"; fi

# B4C-E · the decisive error leads the close --------------------------------------------------------
B=$(b4brief e01 'x\n')
for m in reconnect401 reconnect401text blankfail reconnectok; do
  CODEX_SHIM_MODE=$m CODEX_SHIM_THREAD=thread-$m b4spawn "E-$m" "$B" --cwd "$T/work"
  printf '%s\n' "$B4O" > "$T/b4c-e-$m.out"
done
E1=$(field "$REC4" E-reconnect401 lane-closed error); E1T=$(field "$REC4" E-reconnect401 lane-closed errors_total)
E1L=$(field "$REC4" E-reconnect401 lane-closed errors | "$PY" -c 'import json,sys; e=json.load(sys.stdin); print(len(e), "401" in e[-1], "Reconnecting... 1/5" not in "".join(e))')
if [ "$E1" = '"unexpected status 401 Unauthorized: Incorrect API key provided"' ] && [ "$E1T" = "7" ] && [ "$E1L" = "5 True True" ] \
   && grep -q '^lane run-b4c/E-reconnect401 .* error: unexpected status 401' "$T/b4c-e-reconnect401.out" \
   && grep -q '(no report text: unexpected status 401' "$SR4/run-b4c-report-E-reconnect401.md"; then
  pass "B4C-E01 six reconnects then a 401 turn.failed: the close line, the summary and the saved report name the 401; the error tail keeps the last five of seven"
else fail "B4C-E01 the decisive error" "error=$E1 total=$E1T tail=$E1L $(grep '^lane ' "$T/b4c-e-reconnect401.out")"; fi
E2R="$SR4/run-b4c-report-E-reconnect401text.md"
if head -1 "$E2R" | grep -q '^(codex-lane.py: this pass closed failed — unexpected status 401' && grep -qx 'PARTIAL-WORK-thread-reconnect401text' "$E2R"; then
  pass "B4C-E02 with assistant text before the failure, the saved report opens with the decisive error and keeps the lane's text whole below it"
else fail "B4C-E02 the report with text" "$(head -3 "$E2R" | tr '\n' '|')"; fi
E3=$(field "$REC4" E-blankfail lane-closed error); E3B=$(field "$REC4" E-blankfail lane-closed turns_failed_blank)
if [ "$E3" = '"turn failed with no error text"' ] && [ "$E3B" = "1" ] && ! grep -q 'None' "$SR4/run-b4c-report-E-blankfail.md"; then
  pass "B4C-E03 an empty final turn.failed error remains unknown and never borrows the earlier retry's error"
else fail "B4C-E03 the empty terminal error" "error=$E3 blank=$E3B $(cat "$SR4/run-b4c-report-E-blankfail.md")"; fi
[ "$(field "$REC4" E-reconnectok lane-closed exit_class)" = '"completed"' ] && [ "$(field "$REC4" E-reconnectok lane-closed error)" = "null" ] \
  && pass "B4C-E04 reconnects followed by a completed turn stay completed, with no error (the control)" || fail "B4C-E04 recovered stream" "$(field "$REC4" E-reconnectok lane-closed exit_class)"

# B4C-D · a control on this pass's report, checked at the close --------------------------------------
B=$(b4brief d01 'x\nCONTROL+: REPORT-OK in <<REPORT>>\n')
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-d01 b4spawn D01 "$B" --cwd "$T/work"
D1P=$(field "$REC4" D01 lane-open controls_pending | "$PY" -c 'import json,sys; p=json.load(sys.stdin); print(p[0]["report"].rsplit("/",1)[-1], p[0]["phrase"])')
D1V=$(field "$REC4" D01 lane-closed controls_deferred | "$PY" -c 'import json,sys; v=json.load(sys.stdin); print(v[0]["result"], v[0]["matches"])')
if [ $B4RC -eq 0 ] && [ "$D1P" = "run-b4c-report-D01.md REPORT-OK" ] && [ "$D1V" = "checked 1" ] && printf '%s' "$B4O" | grep -q 'report controls checked 1 of 1'; then
  pass "B4C-D01 a control on <<REPORT>> is pending at the spawn and checked at the close on this pass's response"
else fail "B4C-D01 the report control" "rc=$B4RC pending=$D1P verdict=$D1V"; fi
B=$(b4brief d02 'x\nCONTROL+: NOT-IN-THE-REPORT in <<REPORT>>\n')
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-d02 b4spawn D02 "$B" --cwd "$T/work"
D2V=$(field "$REC4" D02 lane-closed controls_deferred | "$PY" -c 'import json,sys; v=json.load(sys.stdin); print(v[0]["result"])')
[ "$D2V" = "failed" ] && printf '%s' "$B4O" | grep -q 'report controls FAILED 1 of 1' && pass "B4C-D02 a phrase the response lacks fails the control (the control for B4C-D01)" || fail "B4C-D02 the missing phrase" "$D2V"
B=$(b4brief d03 'x\nCONTROL+: PARTIAL-WORK in <<REPORT>>\n')
CODEX_SHIM_MODE=reconnect401text CODEX_SHIM_THREAD=thread-d03 b4spawn D03 "$B" --cwd "$T/work"
D3V=$(field "$REC4" D03 lane-closed controls_deferred | "$PY" -c 'import json,sys; v=json.load(sys.stdin); print(v[0]["result"])')
[ "$D3V" = "unverified" ] && pass "B4C-D03 a failed pass's report control stays unverified, though its partial text carries the phrase" || fail "B4C-D03 the failed pass" "$D3V"
B=$(b4brief d04 'x\nCONTROL+: no report text in <<REPORT>>\n')
CODEX_SHIM_MODE=blank CODEX_SHIM_THREAD=thread-d04 b4spawn D04 "$B" --cwd "$T/work"
D4V=$(field "$REC4" D04 lane-closed controls_deferred | "$PY" -c 'import json,sys; v=json.load(sys.stdin); print(v[0]["result"])')
grep -q '(no report text' "$SR4/run-b4c-report-D04.md" && [ "$D4V" = "unverified" ] \
  && pass "B4C-D04 the wrapper's own placeholder never satisfies a report control: unverified" || fail "B4C-D04 the placeholder" "$D4V"
B=$(b4brief d05 'x\nCONTROL+: OTHER LANE REPORT in <<REPORT>>\n')
CODEX_SHIM_MODE=blankfile CODEX_SHIM_THREAD=thread-d05 b4spawn D05 "$B" --cwd "$T/work"
D5V=$(field "$REC4" D05 lane-closed controls_deferred | "$PY" -c 'import json,sys; v=json.load(sys.stdin); print(v[0]["result"])')
[ "$D5V" = "unverified" ] && pass "B4C-D05 a file the CLI or anyone else leaves at the report path never stands in for this pass's response" || fail "B4C-D05 the planted file" "$D5V"

# B4C-R · declared inputs and web work ----------------------------------------------------------------
: > "$T/b4empty.txt"
B=$(b4brief r01 "x\nREAD+: $T/b4empty.txt\n")
b4spawn R01 "$B" --cwd "$T/work" --dry-run
[ $B4RC -eq 2 ] && printf '%s' "$B4O" | grep -q "/b4empty.txt is empty (0 bytes)" && pass "B4C-R01 a zero-byte declared input refuses with its path" || fail "B4C-R01 the empty input" "rc=$B4RC $B4O"
B=$(b4brief r02 'x\nWEB+: check every cited page\n')
b4spawn R02 "$B" --cwd "$T/work" --dry-run
RC2=$B4RC; O2=$B4O
b4spawn R03 "$B" --cwd "$T/work" --search --dry-run
if [ $RC2 -eq 2 ] && printf '%s' "$O2" | grep -q 'pass --search' && [ $B4RC -eq 0 ]; then
  pass "B4C-R02 declared web work needs --search (shell --network is no stand-in), and passes with it"
else fail "B4C-R02 web work" "rc=$RC2/$B4RC $O2"; fi

# B4C-K · the suite's own home: no read of the machine's real stores -----------------------------------
mkdir -p "$T/trace-site"
cat > "$T/trace-site/sitecustomize.py" <<'B4_TRACE_SITE_END'
import os, sys
_roots = [r for r in os.environ.get("B4_TRACE_ROOTS", "").split(os.pathsep) if r]
_log = os.environ.get("B4_TRACE_LOG")
if _roots and _log:
    _roots = sorted(set(_roots + [os.path.realpath(r) for r in _roots]))
    def _hit(path):
        if isinstance(path, int):
            return None
        try:
            p = os.path.abspath(os.fsdecode(path))
        except (TypeError, ValueError):
            return None
        for root in _roots:
            if p == root or p.startswith(root.rstrip("/") + "/"):
                return p
        return None
    def _note(kind, p):
        with open(_log, "a") as handle:
            handle.write("%d %s %s\n" % (os.getpid(), kind, p))
    def _audit(event, args):
        if event in ("open", "os.listdir", "os.scandir", "glob.glob") and args:
            p = _hit(args[0])
            if p:
                _note(event, p)
                raise PermissionError(13, "blocked by the suite's read trace", p)
    sys.addaudithook(_audit)
    def _wrap(fn, kind):
        def inner(path, *a, **k):
            p = _hit(path)
            if p:
                _note(kind, p)
                raise PermissionError(13, "blocked by the suite's read trace", p)
            return fn(path, *a, **k)
        return inner
    os.stat, os.lstat, os.access = _wrap(os.stat, "stat"), _wrap(os.lstat, "lstat"), _wrap(os.access, "access")
B4_TRACE_SITE_END
TROOTS="$REAL_HOME/.claude.json:$REAL_HOME/.claude:$REAL_HOME/.codex:$REAL_HOME/.llm-wiki/spawn-records:$REAL_HOME/.llm-wiki/handoffs:$REAL_HOME/.llm-wiki/lane-home"
B=$(b4brief k01 'x\n')
: > "$T/trace-claim.log"; : > "$T/trace-control.log"
env PYTHONPATH="$T/trace-site${PYTHONPATH:+:$PYTHONPATH}" B4_TRACE_ROOTS="$TROOTS" B4_TRACE_LOG="$T/trace-claim.log" CODEX_SHIM_MODE=ok \
  "$PY" "$ADAPTER" spawn --run run-b4c --lane K01 --class critic --brief "$B" "${B4C[@]}" --stage-from "$T/b4src" >"$T/b4c-k01.out" 2>&1; RC=$?
env PYTHONPATH="$T/trace-site${PYTHONPATH:+:$PYTHONPATH}" B4_TRACE_ROOTS="$TROOTS" B4_TRACE_LOG="$T/trace-claim.log" \
  "$PY" "$ADAPTER" watch --run run-b4c --lane K01 --appear-s 1 >/dev/null 2>&1
env -u CODEX_HOME HOME="$REAL_HOME" PYTHONPATH="$T/trace-site${PYTHONPATH:+:$PYTHONPATH}" B4_TRACE_ROOTS="$TROOTS" B4_TRACE_LOG="$T/trace-control.log" \
  "$PY" "$ADAPTER" spawn --run run-b4c --lane K00 --class critic --brief "$B" "${B4C[@]}" --cwd "$T/work" --dry-run >/dev/null 2>&1
if [ $RC -eq 0 ] && [ ! -s "$T/trace-claim.log" ] && grep -q '\.codex' "$T/trace-control.log"; then
  pass "B4C-K01 under the suite's fixture HOME and CODEX_HOME a staged spawn and a watch read nothing of the real stores, while the same adapter under the real HOME is caught looking for Codex's global instructions there ($(wc -l < "$T/trace-control.log" | tr -d ' ') blocked: the control)"
else fail "B4C-K01 the read trace" "rc=$RC claim: $(head -3 "$T/trace-claim.log" | tr '\n' '|') control: $(wc -l < "$T/trace-control.log" | tr -d ' ') lines"; fi

# The spawn hold (register 2026-10-14 01:33 b): the same check through this wrapper, both modes.
"$PY" -B "$HERE/test_decisions_spawn.py" --wrappers "$HERE" --fixture-root "$T" --part codex > "$T/decisions-spawn.log" 2>&1
DSPAWN_RC=$?
while IFS= read -r line; do
  case "$line" in
    'OK '*) pass "${line#OK }" ;;
    'BAD '*) fail "${line#BAD }" "spawn hold assertion" ;;
    'PROBE FAILED:'*) fail "$line" "spawn hold premise" ;;
  esac
done < "$T/decisions-spawn.log"
if [ "$DSPAWN_RC" != 0 ] && ! grep -q '^BAD ' "$T/decisions-spawn.log"; then
  fail "spawn hold harness failed" "$(tail -3 "$T/decisions-spawn.log")"
fi

# Fix (c): public terminal evidence, recovery and preserved A3 ownership.
"$PY" -B "$HERE/test_fix_c.py" --wrappers "$HERE" --fixture-root "$T" --part codex > "$T/fix-c.log" 2>&1
FIXC_RC=$?
while IFS= read -r line; do
  case "$line" in
    'OK '*) pass "${line#OK }" ;;
    'BAD '*) fail "${line#BAD }" "fix (c) assertion" ;;
    'PROBE FAILED:'*) fail "$line" "fix (c) premise" ;;
  esac
done < "$T/fix-c.log"
if [ "$FIXC_RC" != 0 ] && ! grep -q '^BAD ' "$T/fix-c.log"; then
  fail "fix (c) harness failed" "$(tail -3 "$T/fix-c.log")"
fi

# The item bars (register 2026-11-05 12:41): what --item records through this wrapper.
"$PY" -B "$HERE/test_item_bars.py" --wrappers "$HERE" --fixture-root "$T" --part codex > "$T/item-bars.log" 2>&1
IBARS_RC=$?
while IFS= read -r line; do
  case "$line" in
    'OK '*) pass "${line#OK }" ;;
    'BAD '*) fail "${line#BAD }" "item bars assertion" ;;
    'PROBE FAILED:'*) fail "$line" "item bars premise" ;;
  esac
done < "$T/item-bars.log"
if [ "$IBARS_RC" != 0 ] && ! grep -q '^BAD ' "$T/item-bars.log"; then
  fail "item bars harness failed" "$(tail -3 "$T/item-bars.log")"
fi

SOURCE_AFTER=$(shasum "$ADAPTER" "$HERE/lane.py" "$0")
if [ "$SOURCE_BEFORE" = "$SOURCE_AFTER" ] && [ -n "$SOURCE_BEFORE" ]; then pass "W2-C06 shipped sources unchanged"; else fail "W2-C06 source manifest" "changed"; fi
TOTAL=$((PASSES+FAILS))
if [ $FAILS -eq 0 ]; then echo "PASS $PASSES/$TOTAL"; exit 0; else echo "FAIL $FAILS/$TOTAL"; exit 1; fi
