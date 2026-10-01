#!/bin/bash
# test_codex_lane.sh — the shim suite for codex-lane.py: a fake `codex` that emits the documented
# JSONL events under a chosen mode, a throwaway run store, and one assertion block per case.
# Usage: sh .claude/skills/delegate/test_codex_lane.sh            (no live model call)
# Every case prints PASS or FAIL with its name; the script exits 1 on any FAIL.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
ADAPTER="$HERE/codex-lane.py"
T="$(mktemp -d /tmp/codex-lane-suite-XXXXXX)"
export LLM_WIKI_STORE="$T/store"
export AIMYTH_VIEWER=none
export CODEX_SHIM_ARGS="$T/shim-args.txt"
export CODEX_SHIM_PROMPT="$T/shim-prompt.txt"
mkdir -p "$T/bin" "$T/work" "$T/extra" "$T/store/spawn-records"
TR="$(cd "$T" && pwd -P)"     # the real path: the adapter records real paths (/private/tmp on macOS)
FAILS=0; PASSES=0
export PYTHONDONTWRITEBYTECODE=1
cleanup(){ chmod -R u+w "$T"; rm -rf "$T"; }
trap cleanup EXIT INT TERM
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

COMMON=(--codex "$T/bin/codex" --class critic --brief "$T/brief.md" --cwd "$T/work" --reason "(a) suite" --choice-reason "suite pick" --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60 --report-words 50)

pass() { PASSES=$((PASSES+1)); echo "PASS $1"; }
fail() { echo "FAIL $1: $2"; FAILS=$((FAILS+1)); }

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

# 7 malformed line tolerated and counted
CODEX_SHIM_MODE=malformed "$PY" "$ADAPTER" spawn --run run-suite --lane L4 "${COMMON[@]}" >/dev/null 2>&1; rc=$?
if [ $rc -eq 0 ] && [ "$(field "$REC" L4 lane-closed exit_class)" = '"completed"' ] && [ "$(field "$REC" L4 lane-closed events_unparseable)" = "1" ]; then pass "malformed line"; else fail "malformed line" "rc=$rc"; fi

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
# The supervisor's beat passes no --delegation flag. Under a vault whose Settings line reads `auto`
# an unflagged call is refused (the twin, on a plain resume), so the beat must carry the regime its
# lane-open recorded. The fixture vault is the real one's .claude tree beside its own Settings file.
VROOT="${CLAUDE_PROJECT_DIR:-$(cd "$HERE/../../.." && pwd)}"
mkdir -p "$T/autovault"; ln -s "$VROOT/.claude" "$T/autovault/.claude"
printf '## Settings\n- **delegation**: auto — the fixture line\n' > "$T/autovault/CUSTOMISATION.md"
NBEATS=$(count "$REC" L1 hold-beat); NRES2=$(count "$REC" L1 lane-resumed)
CODEX_SHIM_MODE=ok CLAUDE_PROJECT_DIR="$T/autovault" "$PY" "$ADAPTER" resume --run run-suite --lane L1 --brief "$T/follow.md" --codex "$T/bin/codex" --viewer none --silence-s 0 --deadline-s 60 >/dev/null 2>"$T/auto-resume.err"; rc1=$?
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-ok CLAUDE_PROJECT_DIR="$T/autovault" "$PY" "$ADAPTER" resume --run run-suite --lane L1 --beat --codex "$T/bin/codex" --viewer none >"$T/auto-beat.txt" 2>&1; rc2=$?
if [ $rc1 -eq 2 ] && grep -q 'delegation regime unresolved' "$T/auto-resume.err" && [ "$(count "$REC" L1 lane-resumed)" = "$NRES2" ] \
   && [ $rc2 -eq 0 ] && [ "$(count "$REC" L1 hold-beat)" = "$((NBEATS + 1))" ] && [ "$(field "$REC" L1 hold-beat ok)" = true ] \
   && [ "$(field "$REC" L1 hold-beat carried_from_open.delegation)" = '"single (head)"' ] \
   && [ "$(field "$REC" L1 hold-beat by)" = '"hand"' ]; then pass "beat: under a Settings line reading auto an unflagged resume is refused (must fire) while an unflagged beat carries the lane-open's recorded regime and runs, as the supervisor's call must"; else fail "beat under delegation auto" "rc=$rc1/$rc2 $(cat "$T/auto-resume.err" | head -2) $(cat "$T/auto-beat.txt" | head -3)"; fi
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
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-ultra "$PY" "$ADAPTER" spawn --run run-suite --lane U1 "${COMMON[@]}" --effort ultra --config features.multi_agent=true >/dev/null 2>&1; rc1=$?
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-ultra "$PY" "$ADAPTER" resume --run run-suite --lane U1 --brief "$T/follow.md" --codex "$T/bin/codex" --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60 >"$T/u1.txt" 2>&1; rc2=$?
order_ok=$("$PY" -c 'import sys; s = open(sys.argv[1]).read(); f = s.find("features.multi_agent=false"); t = s.find("features.multi_agent=true"); print("yes" if 0 <= f < t else "no")' "$CODEX_SHIM_ARGS")
if [ $rc1 -eq 0 ] && [ $rc2 -eq 0 ] && grep -q -- 'model_reasoning_effort="ultra"' "$CODEX_SHIM_ARGS" && [ "$order_ok" = yes ] \
   && grep -q -- 'resume thread-ultra -' "$CODEX_SHIM_ARGS" && [ "$(field "$REC" U1 lane-resumed effort)" = '"ultra"' ] \
   && [ "$(field "$REC" U1 lane-open config_extra)" = '["features.multi_agent=true"]' ] \
   && [ "$(field "$REC" U1 lane-resumed carried_from_open.config)" = '["features.multi_agent=true"]' ]; then pass "resume re-declares the spawn's ultra and features.multi_agent=true (after the default false)"; else fail "resume re-declares effort and config" "rc=$rc1/$rc2 order=$order_ok effort=$(field "$REC" U1 lane-resumed effort) $(head -3 "$T/u1.txt")"; fi
CODEX_SHIM_MODE=ok CODEX_SHIM_THREAD=thread-ultra "$PY" "$ADAPTER" resume --run run-suite --lane U1 --brief "$T/follow.md" --codex "$T/bin/codex" --effort max --delegation single --delegation-src head --viewer none --silence-s 0 --deadline-s 60 >/dev/null 2>&1; rc=$?
if [ $rc -eq 0 ] && grep -q -- 'model_reasoning_effort="max"' "$CODEX_SHIM_ARGS" && ! grep -q -- 'model_reasoning_effort="ultra"' "$CODEX_SHIM_ARGS" \
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
if [ $rc -eq 0 ] && printf '%s' "$out" | grep -q -- 'features.multi_agent=true' && printf '%s' "$out" | grep -q -- 'model_reasoning_effort="ultra"' \
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
if [ $rc -eq 3 ] && grep -q '^orphaned: lane run-w/WO' "$T/w5.txt" && [ "$(wc -l < "$T/watch-rec3.jsonl" | tr -d ' ')" = 2 ]; then pass "watch on a lane whose wrapper has gone with no close exits 3, names kill, and writes nothing"; else fail "watch on an orphaned lane" "rc=$rc $(cat "$T/w5.txt")"; fi
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
            for p in root.rglob('*')}
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
          and "cannot check lane ids" in err and before==manifest())
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
SOURCE_AFTER=$(shasum "$ADAPTER" "$HERE/lane.py" "$0")
if [ "$SOURCE_BEFORE" = "$SOURCE_AFTER" ] && [ -n "$SOURCE_BEFORE" ]; then pass "W2-C06 shipped sources unchanged"; else fail "W2-C06 source manifest" "changed"; fi
TOTAL=$((PASSES+FAILS))
if [ $FAILS -eq 0 ]; then echo "PASS $PASSES/$TOTAL"; exit 0; else echo "FAIL $FAILS/$TOTAL"; exit 1; fi
