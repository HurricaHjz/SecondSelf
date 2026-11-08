#!/bin/sh
# Test suite for the three context hooks: context-watermark.py, precompact-checkpoint.py and
# handsoff-gate.py (n115 design v1.1; hands-off design v1.0, D1/D2 and §Context bands).
# Every case runs against fixtures under its own mktemp directory, removed on exit, with
# every knob pointed at them; the vault and ~/.llm-wiki/handoffs are never written — legs l and m
# prove it (read-only manifests before and after, the hooks dir manifest, a source grep for
# destructive verbs with its own positive control). Leg g2 exercises the hooks' DEFAULT paths
# under an overridden HOME, so the real home is still untouched. Leg p2 checks head-fence.py's
# whole-command field (register 2026-09-14), leg p3 its line discipline (every character
# splitlines() ends a line at is a space in field five; a lone surrogate keeps its line).
# Run:  sh .claude/hooks/test_context_hooks.sh          (last line: PASS n/n or FAIL k/n)
# Bounds asserted here: 524288 = the hook's TAIL_BYTES; 7168 = its BODY_CAP; 20/40 = its list
# caps; 500 ms = the timing ceiling the build brief set (the design page expects well under 100 ms).
set -u
HOOKS="$(cd "$(dirname "$0")" && pwd)"
WM="$HOOKS/context-watermark.py"; PC="$HOOKS/precompact-checkpoint.py"; HG="$HOOKS/handsoff-gate.py"
PY=/usr/local/bin/python3; [ -x "$PY" ] || PY=python3
F="$(mktemp -d "${TMPDIR:-/tmp}/context-hooks.XXXXXX")" || {
  printf "%s\n" "PROBE FAILED: cannot create context-hook fixtures"; exit 2;
}
[ -d "$F" ] || { printf "%s\n" "PROBE FAILED: missing context-hook fixture directory"; exit 2; }
trap 'rm -rf "$F"' 0
trap 'exit 2' HUP INT TERM
HOME="$F/ambient-home"; export HOME
# Default-path legs must not inherit a live run's arming, window, band or output overrides, nor its
# run, store or cap, which the hard band's last-lead allowance reads (review CR-CAP2 finding 4: a
# head's helpers inherit its environment).
unset AIMYTH_HANDSOFF AIMYTH_STATE_DIR AIMYTH_BANDS AIMYTH_CONTEXT_WINDOW AIMYTH_WATERMARK_LOG
unset AIMYTH_HANDSOFF_RUN LLM_WIKI_STORE AIMYTH_MAX_SUCCESSORS
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "  ok   — $1"; }
bad()  { FAIL=$((FAIL+1)); echo "  FAIL — $1"; }
check(){ [ "$2" = "$3" ] && ok "$1" || bad "$1 (want '$3', got '$2')"; }
probe(){ [ "$2" = "$3" ] || { echo "PROBE FAILED: $1 (want '$3', got '$2')"; exit 2; }; }
hashf(){ if command -v md5 >/dev/null 2>&1; then md5 -q "$1"; else md5sum "$1" | cut -d' ' -f1; fi; }
manifest(){ find "$@" -type f | LC_ALL=C sort | while IFS= read -r f; do printf '%s %s\n' "$(hashf "$f")" "$f"; done; }
sect(){ awk -v h="$2" '$0==h{f=1;next} /^## /{f=0} f' "$1"; }   # body of one ## section
mstat(){ "$PY" -B -c 'import os, sys; print(int(os.stat(sys.argv[1]).st_mtime) if os.path.exists(sys.argv[1]) else "absent")' "$1"; }
iso_ago(){ "$PY" -B -c 'import sys, time; print(time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - float(sys.argv[1]) * 3600)))' "$1"; }
since_label(){ "$PY" -B -c 'import sys, datetime; s = sys.argv[1]; s = s[:-1] + "+00:00" if s.endswith("Z") else s; print(datetime.datetime.fromisoformat(s).astimezone().strftime("%Y-%m-%dT%H:%M%z"))' "$1"; }

SA=sid-a-1111; SB=sid-b-2222; SC=sid-c-3333; SJ=sid-j-4444; SW=sid-w-6666; SR=sid-r-5555
H="$F/state/handoffs"; T_A="$F/projects/proj/$SA.jsonl"; T_E="$F/projects/proj/big.jsonl"
GS="$F/state/gate"   # the gate hook's state dir: its markers and events.log, never the real one
TS_A=$(iso_ago 1); TS_W=$(iso_ago 30); SINCE_A=$(since_label "$TS_A"); SINCE_W=$(since_label "$TS_W")
HEAD_SPAWN_A="## Spawn records (since $SINCE_A)"; HEAD_VAULT_A="## Vault files modified (since $SINCE_A)"
HEAD_SPAWN_NA="## Spawn records (last 24 h — no session start found)"; HEAD_VAULT_NA="## Vault files modified (last 24 h — no session start found)"
BAND1="write the hand-off document at the next item boundary"; BAND2="hand-off band: finish what is in flight and open a new item only where the hands-off gate's fit check allows it (an attended session starts nothing new)"
BAND3="hard band: write the hand-off now and end the session"; START="context: start (no transcript yet)"
# The attended 1M path (unarmed, no AIMYTH_BANDS, default window) carries the fit sum below 900k
# in place of any band text (owner decision of 9 October 2026); $1 is the figure as displayed.
fitx(){ printf 'fit: new work only if %s now + its estimate + 50,000 close-out < 950,000 tokens; state the sum first; no estimate, nothing new; start the close-out by 900,000 tokens' "$1"; }
HOFF="$F/handoffs/$SA-20260905-030000-handoff.md"   # an existing hand-off document a prompt may name
ups(){ printf '{"session_id":"%s","transcript_path":"%s","cwd":"%s","hook_event_name":"UserPromptSubmit","prompt":"hi"}' "$1" "$2" "$3"; }
pcs(){ printf '{"session_id":"%s","transcript_path":"%s","cwd":"%s","hook_event_name":"PreCompact","trigger":"%s","custom_instructions":""}' "$1" "$2" "$3" "$4"; }
ssj(){ printf '{"session_id":"%s","transcript_path":"%s","cwd":"%s","hook_event_name":"SessionStart","source":"%s"}' "$1" "$2" "$3" "$4"; }
upsp(){ printf '{"session_id":"%s","transcript_path":"%s","cwd":"%s","hook_event_name":"UserPromptSubmit","prompt":"%s"}' "$1" "$2" "$3" "$4"; }
ptu(){ printf '{"session_id":"%s","transcript_path":"%s","cwd":"%s","hook_event_name":"PreToolUse","tool_name":"%s","tool_input":%s}' "$1" "$2" "$3" "$4" "$5"; }
# wm/pc: <stdin-json> [VAR=val ...] -> hook stdout; exit status = the hook's. Env goes through
# `env`, never a VAR=x prefix on a function (POSIX sh keeps that past the call). Window and bands
# are NOT set here, so the hook's own defaults are what the band legs test.
wm(){ j="$1"; shift; printf '%s' "$j" | env AIMYTH_PROJECTS_DIR="$F/projects" AIMYTH_WATERMARK_LOG="$F/state/wm/context-watermark.log" ${1+"$@"} "$PY" -B "$WM"; }
pc(){ j="$1"; shift; printf '%s' "$j" | env AIMYTH_STATE_DIR="$H" AIMYTH_INGEST_RUNS="$F/llm/ingest-runs" AIMYTH_SPAWN_RECORDS="$F/llm/spawn-records" AIMYTH_ROLE_STATE_DIR="$F/role" AIMYTH_PROJECTS_DIR="$F/projects" AIMYTH_WATERMARK_LOG="$F/state/wm/context-watermark.log" ${1+"$@"} "$PY" -B "$PC"; }
# gate: AIMYTH_HANDSOFF is emptied FIRST so an ambient arming cannot arm the unarmed legs; a
# caller's later assignment wins (leg i already relies on that ordering for AIMYTH_STATE_DIR).
gate(){ j="$1"; shift; printf '%s' "$j" | env AIMYTH_HANDSOFF= AIMYTH_PROJECTS_DIR="$F/projects" AIMYTH_STATE_DIR="$GS" AIMYTH_CONTEXT_WINDOW=200000 ${1+"$@"} "$PY" -B "$HG"; }
ctxof(){ printf '%s' "$1" | "$PY" -B -c '
import json, sys
raw = sys.stdin.read()
if not raw.strip():
    sys.stdout.write("(no stdout)"); sys.exit(0)
try:
    d = json.loads(raw)
except ValueError:
    sys.stdout.write("(bad json)"); sys.exit(0)
h = d.get("hookSpecificOutput", {})
sys.stdout.write(h.get("hookEventName", "?") + "|" + h.get("additionalContext", "?"))
'; }
dec(){ printf '%s' "$1" | "$PY" -B -c '
import json, sys
raw = sys.stdin.read()
if not raw.strip():
    sys.stdout.write("(silent)"); sys.exit(0)
try:
    d = json.loads(raw)
except ValueError:
    sys.stdout.write("(bad json)"); sys.exit(0)
h = d.get("hookSpecificOutput", {})
sys.stdout.write(h.get("hookEventName", "?") + "|" + h.get("permissionDecision", "?") + "|" + h.get("permissionDecisionReason", "?"))
'; }

echo "== setup: fixtures under $F =="
# The per-invocation fixture directory already exists.
mkdir -p "$F/projects/proj" "$F/elsewhere" "$F/llm/ingest-runs" "$F/llm/spawn-records" "$F/llm-win/spawn-records" "$F/llm-big/spawn-records" "$F/role" \
         "$F/vault/wiki/concepts" "$F/vault/.claude/__pycache__" "$F/vault/output" "$F/decoy" "$F/state" "$H" "$F/home" \
         "$F/hookcopy" "$F/hookcopy-control" "$F/hookalone" "$F/handoffs" "$F/gatealone" "$GS" "$F/home/.aimyth/handoffs"
cat > "$F/mk.py" <<'PYFIX'
import json, os, sys, time
TS = os.environ.get("MK_TS", "2026-09-03T00:00:00.000Z")   # the first record's timestamp = the session start
def user(text, **extra):
    d = {"type": "user", "isSidechain": False, "message": {"role": "user", "content": text}, "uuid": "u", "timestamp": TS}
    d.update(extra); return json.dumps(d)
def assistant(ctx, sidechain=False, model="claude-test-model"):
    a = ctx // 2; b = ctx // 3; c = ctx - a - b   # split across the three fields: a reader summing one is caught
    return json.dumps({"type": "assistant", "isSidechain": sidechain, "message": {"role": "assistant", "model": model,
        "content": [{"type": "text", "text": "reply"}], "usage": {"input_tokens": a, "cache_read_input_tokens": b,
        "cache_creation_input_tokens": c, "output_tokens": 12}}, "uuid": "a", "timestamp": TS})
def synthetic(ctx=0):   # a harness-made record (limit stop): model <synthetic>, usually all-zero usage
    return assistant(ctx, model="<synthetic>")
def other(kind, n=0):
    return json.dumps({"type": kind, "sessionId": "x", "n": n})
def pad(target, current):
    overhead = len(json.dumps({"type": "attachment", "pad": ""})) + 1
    fill = target - current - overhead
    if fill < 0: sys.exit("PROBE FAILED: pad target %d below current size %d" % (target, current))
    return json.dumps({"type": "attachment", "pad": "x" * fill})
def write(out, lines):
    with open(out, "w", encoding="utf-8") as f:
        for ln in lines: f.write(ln + "\n")
    return os.path.getsize(out)
cmd = sys.argv[1]
if cmd == "simple":       # several usage records; the last one sums to ctx; optional exact size
    out, ctx = sys.argv[2], int(sys.argv[3]); target = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    head = [user("hello"), assistant(100000), user("more"), assistant(200000), user("go")]
    tail = [assistant(ctx), user([{"type": "tool_result", "content": "done"}]), other("last-prompt")]
    lines = head + tail
    if target:
        lines = head + [pad(target, sum(len(l.encode()) + 1 for l in lines))] + tail
    print(write(out, lines))
elif cmd == "nousage":
    print(write(sys.argv[2], [user("a"), other("attachment"), user("b"), other("last-prompt")]))
elif cmd == "sidechain":  # the head's record, then a lane's (isSidechain) record after it
    print(write(sys.argv[2], [user("a"), assistant(int(sys.argv[3])), user("b"),
                              assistant(int(sys.argv[4]), sidechain=True), other("last-prompt")]))
elif cmd == "synth":      # a real record, then a synthetic zero-usage limit stop, a synthetic non-zero, a real-model zero-stock record
    print(write(sys.argv[2], [user("a"), assistant(int(sys.argv[3])), user("b"), synthetic(0), synthetic(5), assistant(0), other("last-prompt")]))
elif cmd == "synthonly":  # nothing but synthetic records in the tail
    print(write(sys.argv[2], [user("a"), synthetic(0), user("b"), synthetic(0), other("last-prompt")]))
elif cmd == "outside":    # the only usage record, then >512 kB of filler: it lies outside the tail
    print(write(sys.argv[2], [assistant(424242)] + [user("f" * 4000)] * 300))
elif cmd == "big":        # big <out> <total> <planted> <wrong_tail> <wrong_far>
    out, total, planted, wrong_tail, wrong_far = sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
    filler = user("f" * 4000); fl = len(filler.encode()) + 1
    lines = [assistant(wrong_far)]; cur = len(lines[0].encode()) + 1
    while cur < total - 400 * 1024: lines.append(filler); cur += fl   # inside the 512 kB tail, before the planted record
    wrong_off = cur; lines.append(assistant(wrong_tail)); cur += len(lines[-1].encode()) + 1
    while cur < total - 100 * 1024: lines.append(filler); cur += fl
    planted_off = cur; lines.append(assistant(planted)); cur += len(lines[-1].encode()) + 1
    trail = [  # after the planted record: decoys that carry a "usage" key but are not the head's qualifying record
        json.dumps({"type": "user", "isSidechain": False, "message": {"role": "user", "content": "decoy",
                    "usage": {"input_tokens": 999999, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}}),
        json.dumps({"type": "attachment", "attachment": {"usage": {"input_tokens": 999999}}}),
        assistant(888888, sidechain=True), synthetic(0),
        user([{"type": "tool_result", "content": "t" * 3000}]), other("last-prompt"), other("atis-latch")]
    for t in trail: lines.append(t); cur += len(t.encode()) + 1
    while cur < total - 8192: lines.append(filler); cur += fl
    lines.append(pad(total, cur))
    print("size=%d planted_offset=%d wrong_tail_offset=%d" % (write(out, lines), planted_off, wrong_off))
elif cmd == "bigmd":      # bigmd <out> <head-marker> <tail-marker> <approx-bytes>
    out, head, tail, total = sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
    with open(out, "w", encoding="utf-8") as f:
        f.write(head + "\n" + ("filler line for the cap test\n" * (total // 29)) + tail + "\n")
    print(os.path.getsize(out))
elif cmd == "age":        # age <file> <hours>: set the mtime that many hours back
    t = time.time() - float(sys.argv[3]) * 3600; os.utime(sys.argv[2], (t, t))
elif cmd == "bigspawn":   # bigspawn <dir> <count>: fresh records whose last line is over 300 chars
    d, n = sys.argv[2], int(sys.argv[3])
    for i in range(1, n + 1):
        with open(os.path.join(d, "run-big-%02d.jsonl" % i), "w", encoding="utf-8") as f:
            f.write(json.dumps({"event": "run-open"}) + "\n" + json.dumps({"event": "spawn", "lane": "L%02d" % i, "pad": "S" * 300}) + "\n")
PYFIX
# transcripts (the first record's timestamp is the session start: T_A began 1 h ago, stamped.jsonl 30 h ago)
SZ=$(env MK_TS="$TS_A" "$PY" -B "$F/mk.py" simple "$T_A" 284481 204800); probe "fixture a: exact size" "$SZ" "204800"
probe "fixture a: several usage records" "$(grep -c '"usage"' "$T_A")" "3"
env MK_TS="$TS_W" "$PY" -B "$F/mk.py" simple "$F/projects/proj/stamped.jsonl" 284481 >/dev/null
for c in 590 600 800 900; do "$PY" -B "$F/mk.py" simple "$F/projects/proj/band-$c.jsonl" "$c" >/dev/null; done
"$PY" -B "$F/mk.py" nousage "$F/projects/proj/nousage.jsonl" >/dev/null
: > "$F/projects/proj/empty.jsonl"
# 182000, 170000 and 100000 are 91 %, 85 % and 50 % of the 200k window the gate legs set
for c in 182000 170000 100000; do "$PY" -B "$F/mk.py" simple "$F/projects/proj/ctx-$c.jsonl" "$c" > "$F/state/mk-gate.out"; done
printf 'hand-off\n' > "$HOFF"; printf 'notes\n' > "$F/handoffs/notes.md"; printf 'decoy\n' > "$F/decoy/elsewhere-handoff.md"
"$PY" -B "$F/mk.py" simple "$F/elsewhere/foreign.jsonl" 300000 >/dev/null; cp "$F/elsewhere/foreign.jsonl" "$F/projects/proj/foreign.jsonl"
"$PY" -B "$F/mk.py" sidechain "$F/projects/proj/side.jsonl" 123456 654321 >/dev/null
"$PY" -B "$F/mk.py" synth "$F/projects/proj/synth.jsonl" 700000 >/dev/null
"$PY" -B "$F/mk.py" synthonly "$F/projects/proj/synthonly.jsonl" >/dev/null
"$PY" -B "$F/mk.py" outside "$F/projects/proj/outside.jsonl" >/dev/null
INFO=$("$PY" -B "$F/mk.py" big "$T_E" 2097152 512345 777777 999999)
SIZE=$(printf '%s' "$INFO" | sed 's/.*size=\([0-9]*\).*/\1/'); POFF=$(printf '%s' "$INFO" | sed 's/.*planted_offset=\([0-9]*\).*/\1/'); WOFF=$(printf '%s' "$INFO" | sed 's/.*wrong_tail_offset=\([0-9]*\).*/\1/')
probe "fixture e: exact size" "$SIZE" "2097152"
probe "fixture e: usage-bearing records (3 assistant + 2 decoys + 1 sidechain + 1 synthetic)" "$(grep -c '"usage"' "$T_E")" "7"
ups "$SA" "$T_E" "$F/vault" > "$F/stdin-e.json"
# ingest-run ledgers, spawn records (three dirs: the h set, the window set, the big set), role state
printf '{"event":"run_open","run":"20260903-open"}\n{"event":"checkpoint","lane":"L1","note":"OPEN-RUN-LAST-LINE"}\n' > "$F/llm/ingest-runs/run-20260903-open.jsonl"
printf '{"event":"run_open","run":"20260903-closed"}\n{"event":"run_close","run":"20260903-closed"}\n' > "$F/llm/ingest-runs/run-20260903-closed.jsonl"
printf 'not a ledger\n' > "$F/llm/ingest-runs/notes.txt"
printf '{"event":"run-open"}\n{"event":"spawn","lane":"B1","note":"RECENT-SPAWN-LAST-LINE"}\n' > "$F/llm/spawn-records/run-recent.jsonl"
printf '{"event":"spawn","note":"OLD-SPAWN-LINE"}\n' > "$F/llm/spawn-records/run-old.jsonl"; touch -t 202608010101 "$F/llm/spawn-records/run-old.jsonl"
"$PY" -B -c 'print("{\"event\":\"spawn\",\"pad\":\"" + "L" * 400 + "\"}")' > "$F/llm/spawn-records/run-long.jsonl"
printf '{"event":"spawn","note":"MID-SPAWN-20H"}\n' > "$F/llm-win/spawn-records/run-mid.jsonl"; "$PY" -B "$F/mk.py" age "$F/llm-win/spawn-records/run-mid.jsonl" 20
printf '{"event":"spawn","note":"BEFORE-SPAWN-40H"}\n' > "$F/llm-win/spawn-records/run-before.jsonl"; "$PY" -B "$F/mk.py" age "$F/llm-win/spawn-records/run-before.jsonl" 40
printf '{"event":"spawn","note":"NOW-SPAWN"}\n' > "$F/llm-win/spawn-records/run-now.jsonl"
"$PY" -B "$F/mk.py" bigspawn "$F/llm-big/spawn-records" 25
printf '{"agent": "x", "role": "engineer", "style": "brief", "sid": "%s"}\n' "$SA" > "$F/role/$SA.json"
printf '{"agent": "x", "role": "critic", "style": "brief", "sid": "%s"}\n' "$SR" > "$F/role/$SR.json"
# vault: 70 fresh pages + log.md + .claude + output + CLAUDE.md fresh (74 after T_A's start); Mid.md 20 h old (before T_A's start, after stamped's); Old.md and IDEAS.md old; a .pyc under __pycache__ excluded
i=1; while [ $i -le 70 ]; do printf 'page %s\n' "$i" > "$F/vault/wiki/concepts/Page$i.md"; i=$((i+1)); done
printf 'old\n' > "$F/vault/wiki/concepts/Old.md"; touch -t 202608010101 "$F/vault/wiki/concepts/Old.md"
printf 'mid\n' > "$F/vault/wiki/concepts/Mid.md"; "$PY" -B "$F/mk.py" age "$F/vault/wiki/concepts/Mid.md" 20
printf 'x\n' > "$F/vault/.claude/settings.json"; printf 'pyc\n' > "$F/vault/.claude/__pycache__/x.pyc"
printf 'y\n' > "$F/vault/output/report.md"; printf 'c\n' > "$F/vault/CLAUDE.md"
printf 'i\n' > "$F/vault/IDEAS.md"; touch -t 202608010101 "$F/vault/IDEAS.md"
{ i=1; while [ $i -le 7 ]; do printf '## [2026-09-0%s] framework | Entry %s\n- **Changed**: x\n' "$i" "$i"; i=$((i+1)); done; } > "$F/vault/wiki/log.md"
# planted checkpoints for leg j: two for SJ (old by mtime; new), one name-newest-but-mtime-old decoy for SJ, one for SB (mtime-newest overall)
"$PY" -B "$F/mk.py" bigmd "$H/$SJ-20260901-010100-precompact.md" MARKER-J-OLD TAIL-J-OLD 500 >/dev/null; touch -t 202609010101 "$H/$SJ-20260901-010100-precompact.md"
"$PY" -B "$F/mk.py" bigmd "$H/$SJ-20260903-020000-precompact.md" MARKER-J-NEW TAIL-J-NEW 20000 >/dev/null
"$PY" -B "$F/mk.py" bigmd "$H/$SJ-20260909-000000-precompact.md" MARKER-J-NAMEDECOY TAIL-J-NAMEDECOY 500 >/dev/null; touch -t 202608010101 "$H/$SJ-20260909-000000-precompact.md"
"$PY" -B "$F/mk.py" bigmd "$H/$SB-20260903-030000-precompact.md" MARKER-B TAIL-B 500 >/dev/null
# controls: a sentinel in a decoy dir, a planted destructive line for the source grep, hook copies
printf 'sentinel — must stay byte-identical\n' > "$F/decoy/sentinel.txt"
printf 'import os\nos.remove("x")\n' > "$F/decoy/control.py"
cp "$WM" "$PC" "$HG" "$F/hookcopy/"; cp "$WM" "$F/hookcopy-control/"; cp "$PC" "$F/hookalone/"; cp "$HG" "$F/gatealone/"
# manifests before any hook runs
manifest "$F/projects" "$F/elsewhere" "$F/llm" "$F/llm-win" "$F/llm-big" "$F/role" "$F/vault" "$F/decoy" "$F/handoffs" "$F/mk.py" "$F/stdin-e.json" > "$F/manifest.before"
manifest "$H" > "$F/manifest.planted.before"
manifest "$HOOKS" > "$F/manifest.hooks.before"; find "$HOOKS" -name '*.pyc' | LC_ALL=C sort > "$F/pyc.before"
HOME_HANDOFFS=$(mstat "$HOME/.llm-wiki/handoffs"); HOME_AIMYTH=$(mstat "$HOME/.aimyth/handoffs"); HOME_LOGS=$([ -e "$HOME/.aimyth/logs" ] && echo present || echo absent)
probe "ambient fixture log store starts absent" "$HOME_LOGS" "absent"
probe "read-only manifest is non-empty" "$([ "$(wc -l < "$F/manifest.before" | tr -d ' ')" -gt 100 ] && echo yes || echo no)" "yes"
echo "  fixtures built: $(wc -l < "$F/manifest.before" | tr -d ' ') read-only files; T_A session start $SINCE_A, stamped.jsonl $SINCE_W; home handoffs=$HOME_HANDOFFS"

echo "== a. exact watermark line for a known last-call context and transcript size =="
OUT=$(wm "$(ups "$SA" "$T_A" "$F/vault")"); RC=$?
check "exit 0" "$RC" "0"
check "line: 284481 on a 204800-byte transcript (attended 1M: the fit sum, no band text)" "$(ctxof "$OUT")" "UserPromptSubmit|context: 284,481 tokens (28 % of 1M) · transcript 200.0 kB · $(fitx 284,481)"

echo "== b. default bands 60,80,90: 59, 60, 80 and 90 % of a 1000-token window (env); knob and default guards =="
for pair in "590|59 %|ok" "600|60 %|$BAND1" "800|80 %|$BAND2" "900|90 %|$BAND3"; do
  c=${pair%%|*}; rest=${pair#*|}; p=${rest%%|*}; b=${rest#*|}
  OUT=$(wm "$(ups "$SA" "$F/projects/proj/band-$c.jsonl" "$F/vault")" AIMYTH_CONTEXT_WINDOW=1000)
  check "context $c of 1000 -> $p, '$b'" "$(ctxof "$OUT" | sed 's/ · transcript .* · / · /')" "UserPromptSubmit|context: $c tokens ($p of 1k) · $b"
done
OUT=$(wm "$(ups "$SA" "$F/projects/proj/band-590.jsonl" "$F/vault")" AIMYTH_CONTEXT_WINDOW=1000 AIMYTH_BANDS=30,40)
check "custom bands 30,40: 59 % is the top band" "$(ctxof "$OUT" | sed 's/.* · //')" "$BAND2"
OUT=$(wm "$(ups "$SA" "$F/projects/proj/band-600.jsonl" "$F/vault")" AIMYTH_CONTEXT_WINDOW=1000 AIMYTH_BANDS=bogus 2>"$F/state/bands-err.txt")
check "invalid AIMYTH_BANDS falls back to 60,80,90 (600 -> first band)" "$(ctxof "$OUT" | sed 's/.* · //')" "$BAND1"
check "…and says so on stderr" "$(grep -c 'AIMYTH_BANDS' "$F/state/bands-err.txt")" "1"
OUT=$(wm "$(ups "$SA" "$F/projects/proj/band-600.jsonl" "$F/vault")" AIMYTH_CONTEXT_WINDOW=0)
check "invalid window (0) falls back to 1M" "$(ctxof "$OUT" | sed 's/.*(\(.*\)).*/\1/')" "0 % of 1M"

echo "== c. every unmetered form exits 0 with its reason; a missing or empty transcript is turn 1 =="
OUT=$(wm '{"session_id":"s","cwd":"/nonexistent","hook_event_name":"UserPromptSubmit","prompt":"hi"}'); RC=$?
check "no transcript_path" "$RC:$(ctxof "$OUT")" "0:UserPromptSubmit|context: unmetered (no transcript_path)"
OUT=$(wm "$(ups s "$F/projects/proj/absent.jsonl" x)"); RC=$?
check "file missing (turn 1)" "$RC:$(ctxof "$OUT")" "0:UserPromptSubmit|$START"
OUT=$(wm "$(ups s "$F/projects/proj/empty.jsonl" x)"); RC=$?
check "empty file (turn 1)" "$RC:$(ctxof "$OUT")" "0:UserPromptSubmit|$START"
OUT=$(wm "$(ups s "$F/projects/proj/nousage.jsonl" x)"); RC=$?
check "no usage record at all" "$RC:$(ctxof "$OUT")" "0:UserPromptSubmit|context: unmetered (no qualifying usage record in the tail)"
OUT=$(wm "$(ups s "$F/elsewhere/foreign.jsonl" x)"); RC=$?
check "path outside the projects dir" "$RC:$(ctxof "$OUT")" "0:UserPromptSubmit|context: unmetered (path outside the projects dir)"
OUT=$(wm "$(ups s "$F/projects/proj/foreign.jsonl" x)")
check "control: the same bytes under the projects dir are metered" "$(ctxof "$OUT" | sed 's/ tokens.*//')" "UserPromptSubmit|context: 300,000"

echo "== d. malformed stdin is declared as unmetered (bad stdin); a foreign event injects nothing =="
for s in 'not json' '[]' '' '"str"' '{"hook_event_name":"UserPromptSubmit"'; do
  OUT=$(wm "$s"); RC=$?; check "stdin '$s': declared, exit 0" "$RC:$(ctxof "$OUT")" "0:UserPromptSubmit|context: unmetered (bad stdin)"
done
OUT=$(wm '{"session_id":"s","transcript_path":"'"$T_A"'","hook_event_name":"Stop"}' 2>"$F/state/stop-err.txt"); RC=$?
check "hook_event_name Stop (mis-registration): no stdout, exit 0, noted on stderr" "$RC:$OUT:$(grep -c 'ignoring event Stop' "$F/state/stop-err.txt")" "0::1"

echo "== e. positive control: the planted usage record near the end of a 2 MB transcript is the one found; synthetic and zero-stock records are skipped =="
TAILSTART=$((SIZE - 524288))
[ "$POFF" -gt "$TAILSTART" ] && ok "planted record inside the 512 kB tail (offset $POFF > $TAILSTART of $SIZE)" || bad "planted record outside the tail (offset $POFF)"
[ "$WOFF" -gt "$TAILSTART" ] && ok "wrong-record control also inside the tail (offset $WOFF): a first-in-tail scan would return it" || bad "wrong-record control outside the tail"
[ $((SIZE - POFF)) -gt 8192 ] && ok "planted record is not the last line ($((SIZE - POFF)) bytes follow it): the backward scan must skip records" || bad "planted record is the last line"
OUT=$(wm "$(ups "$SA" "$T_E" "$F/vault")"); L=$(ctxof "$OUT")
check "positive control: the planted figure 512,345 is reported, with the attended fit sum on it" "$L" "UserPromptSubmit|context: 512,345 tokens (51 % of 1M) · transcript 2.0 MB · $(fitx 512,345)"
case "$L" in *777,777*|*999,999*|*888,888*|*" 0 tokens"*) bad "negative control: a wrong record leaked: $L";; *) ok "negative control: neither the earlier in-tail record (777,777), the out-of-tail record (999,999), the decoys, the sidechain record (888,888) nor the trailing synthetic zero record is reported";; esac
probe "outside fixture holds a usage record" "$(grep -c '"usage"' "$F/projects/proj/outside.jsonl")" "1"
OUT=$(wm "$(ups s "$F/projects/proj/outside.jsonl" x)")
check "the only usage record beyond the 512 kB tail -> unmetered (tail-only read is real)" "$(ctxof "$OUT")" "UserPromptSubmit|context: unmetered (no qualifying usage record in the tail)"
OUT=$(wm "$(ups s "$F/projects/proj/side.jsonl" x)")
check "a trailing sidechain record is skipped: the head's 123,456 is reported, not the lane's 654,321" "$(ctxof "$OUT" | sed 's/ tokens.*//')" "UserPromptSubmit|context: 123,456"
probe "synth fixture: four usage records after the user turns" "$(grep -c '"usage"' "$F/projects/proj/synth.jsonl")" "4"
OUT=$(wm "$(ups s "$F/projects/proj/synth.jsonl" x)")
check "a synthetic zero-usage limit stop, a synthetic non-zero record and a real-model zero-stock record after a real 700,000 record: 700,000 reported" "$(ctxof "$OUT" | sed 's/ tokens.*//')" "UserPromptSubmit|context: 700,000"
probe "synthonly fixture holds usage records" "$(grep -c '"usage"' "$F/projects/proj/synthonly.jsonl")" "2"
OUT=$(wm "$(ups s "$F/projects/proj/synthonly.jsonl" x)")
check "only synthetic records in the tail -> unmetered (no qualifying usage record in the tail)" "$(ctxof "$OUT")" "UserPromptSubmit|context: unmetered (no qualifying usage record in the tail)"

echo "== f. timing: the watermark hook on the 2 MB transcript (5 runs, python start-up included) =="
MS=$(env AIMYTH_PROJECTS_DIR="$F/projects" AIMYTH_WATERMARK_LOG="$F/state/wm/context-watermark.log" "$PY" -B - "$PY" "$WM" "$F/stdin-e.json" <<'PYT'
import subprocess, sys, time
py, hook, stdin = sys.argv[1:4]
data = open(stdin, "rb").read()
runs = []
for _ in range(5):
    t = time.perf_counter()
    subprocess.run([py, "-B", hook], input=data, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    runs.append(int((time.perf_counter() - t) * 1000))
runs.sort()
print("%d %d %d" % (runs[0], runs[2], runs[-1]))
PYT
)
set -- $MS; MIN=$1; MED=$2; MAX=$3
[ "$MED" -lt 500 ] && ok "median $MED ms (min $MIN, max $MAX) < 500 ms" || bad "median $MED ms (min $MIN, max $MAX) >= 500 ms"

echo "== g. watermark log: one line, four tab fields, directory created; unmetered appends nothing; unwritable log still injects =="
LOG2="$F/state/wm2/deep/context-watermark.log"
OUT=$(wm "$(ups "$SA" "$T_A" "$F/vault")" AIMYTH_WATERMARK_LOG="$LOG2")
check "log directory created and one line appended" "$([ -f "$LOG2" ] && wc -l < "$LOG2" | tr -d ' ')" "1"
check "four tab-separated fields" "$(awk -F'\t' '{print NF}' "$LOG2")" "4"
check "fields 2-4: session, context, percent" "$(awk -F'\t' '{print $2":"$3":"$4}' "$LOG2")" "$SA:284481:28"
check "field 1 is a timestamp" "$(awk -F'\t' '{print $1}' "$LOG2" | grep -c '^[0-9]\{4\}-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]')" "1"
OUT=$(wm "$(ups "$SA" "$F/projects/proj/empty.jsonl" x)" AIMYTH_WATERMARK_LOG="$LOG2")
check "a start turn (empty transcript) appends nothing" "$(wc -l < "$LOG2" | tr -d ' ')" "1"
: > "$F/state/notadir"
OUT=$(wm "$(ups "$SA" "$T_A" "$F/vault")" AIMYTH_WATERMARK_LOG="$F/state/notadir/x.log" 2>"$F/state/wm-err.txt"); RC=$?
check "unwritable log path: exit 0 and the line is still injected" "$RC:$(ctxof "$OUT" | sed 's/ tokens.*//')" "0:UserPromptSubmit|context: 284,481"
check "…with the failure on stderr" "$(grep -c 'log append failed' "$F/state/wm-err.txt")" "1"

echo "== g2. default paths: the watermark log under HOME/.aimyth/logs, the checkpoint under HOME/.aimyth/handoffs, the hand-off directory handsoff.py and the gate share (HOME overridden to a fixture; the retired cache path is never touched) =="
OUT=$(printf '%s' "$(ups "$SA" "$T_A" "$F/vault")" | env HOME="$F/home" AIMYTH_PROJECTS_DIR="$F/projects" "$PY" -B "$WM"); RC=$?
check "watermark default log: HOME/.aimyth/logs/context-watermark.log, one line" "$RC:$([ -f "$F/home/.aimyth/logs/context-watermark.log" ] && wc -l < "$F/home/.aimyth/logs/context-watermark.log" | tr -d ' ')" "0:1"
check "…and none in the hand-off store, under either name" "$([ -e "$F/home/.aimyth/handoffs/context-watermark.log" ] && echo present || echo absent):$([ -e "$F/home/.llm-wiki/handoffs/context-watermark.log" ] && echo present || echo absent)" "absent:absent"
OUT=$(printf '%s' "$(pcs "$SA" "$T_A" "$F/vault" auto)" | env HOME="$F/home" AIMYTH_PROJECTS_DIR="$F/projects" "$PY" -B "$PC" 2>"$F/state/legacy-diagnostics.txt"); RC=$?
check "checkpoint default state dir: HOME/.aimyth/handoffs" "$RC:$(find "$F/home/.aimyth/handoffs" -name "$SA-*-precompact.md" | wc -l | tr -d ' ')" "0:1"
check "…and none under HOME/.llm-wiki/handoffs (the split default)" "$(find "$F/home" -path '*/.llm-wiki/handoffs/*' -name "$SA-*-precompact.md" | wc -l | tr -d ' ')" "0"
check "nothing under HOME/.cache" "$([ -e "$F/home/.cache" ] && echo present || echo absent)" "absent"

echo "== h. PreCompact writes the checkpoint: seven sections in the short-first order, fixture records, capped lists, log tail, events.log =="
OUT=$(pc "$(pcs "$SA" "$T_A" "$F/vault" auto)" 2>"$F/state/pc-err.txt"); RC=$?
check "exit 0, nothing on stdout" "$RC:$OUT" "0:"
check "exactly one checkpoint for the session" "$(find "$H" -name "$SA-*-precompact.md" -type f | wc -l | tr -d ' ')" "1"
CP=$(find "$H" -name "$SA-*-precompact.md" -type f | head -1)
check "stderr names the path" "$(grep -c "wrote $CP" "$F/state/pc-err.txt")" "1"
check "seven ## sections" "$(grep -c '^## ' "$CP")" "7"
check "section order: short sections first, the two lists last, windows in the headings" "$(grep '^## ' "$CP" | tr '\n' '|')" "## Session|## Instruction|## Log tail|## Role/style state|## Open runs|$HEAD_SPAWN_A|$HEAD_VAULT_A|"
check "header: trigger" "$(grep -c '^- trigger: auto (custom instructions: none)$' "$CP")" "1"
check "header: the context line, computed exactly as hook 1 renders it (attended 1M: the fit sum)" "$(grep -Fxc -e "- context: 284,481 tokens (28 % of 1M) · transcript 200.0 kB · $(fitx 284,481)" "$CP")" "1"
check "open run listed with its path and last line" "$(grep -c "^- $F/llm/ingest-runs/run-20260903-open.jsonl$" "$CP"):$(grep -c 'last: .*OPEN-RUN-LAST-LINE' "$CP")" "1:1"
check "closed run and a non-ledger file not listed" "$(grep -c 'run-20260903-closed\|notes.txt' "$CP")" "0"
check "recent spawn record listed with its last line; the old one not" "$(grep -c 'RECENT-SPAWN-LAST-LINE' "$CP"):$(grep -c 'run-old.jsonl\|OLD-SPAWN-LINE' "$CP")" "1:0"
LRUN=$(awk '{ n = 0; while (match($0, /L+/)) { if (RLENGTH > n) n = RLENGTH; $0 = substr($0, RSTART + RLENGTH) } if (n > m) m = n } END { print m + 0 }' "$CP")
check "a 400-char last line is truncated to 300 (24-char JSON prefix + 276 L + …)" "$LRUN:$(grep -c 'L…$' "$CP")" "276:1"
check "vault list capped at 40 entries" "$(sect "$CP" "$HEAD_VAULT_A" | grep -c '^- ')" "40"
check "…with the overflow line for the other 34" "$(grep -c '^… and 34 more$' "$CP")" "1"
check "old files, a file older than this session's start (Mid.md, 20 h) and __pycache__ excluded" "$(grep -c 'Old.md\|IDEAS.md\|x.pyc\|Mid.md' "$CP")" "0"
check "log tail = the last five ## [ headings, in order, listed without their ## marker" "$(sect "$CP" "## Log tail")" "$(grep '^## \[' "$F/vault/wiki/log.md" | tail -5 | sed 's/^## /- /')"
check "role/style state: raw JSON present" "$(grep -c '"role": "engineer", "style": "brief"' "$CP")" "1"
check "instruction paragraph present" "$(grep -c 'The transcript is not the durable memory' "$CP")" "1"
check "events.log: one line, six tab fields" "$(wc -l < "$H/events.log" | tr -d ' '):$(awk -F'\t' '{print NF}' "$H/events.log")" "1:6"
check "events.log fields: session, event, trigger, context, path" "$(awk -F'\t' '{print $2"|"$3"|"$4"|"$5"|"$6}' "$H/events.log")" "$SA|PreCompact|auto|284481|$CP"

echo "== h2. the windows run from the session's first transcript timestamp, not a fixed 12 h =="
OUT=$(pc "$(pcs "$SW" "$F/projects/proj/stamped.jsonl" "$F/vault" auto)" AIMYTH_SPAWN_RECORDS="$F/llm-win/spawn-records" 2>"$F/state/legacy-diagnostics.txt"); RC=$?
CPW=$(find "$H" -name "$SW-*-precompact.md" -type f | head -1)
check "exit 0, checkpoint written" "$RC:$([ -n "$CPW" ] && echo written)" "0:written"
check "both list headings carry the session start ($SINCE_W)" "$(grep -c "^## Spawn records (since $SINCE_W)$" "$CPW"):$(grep -c "^## Vault files modified (since $SINCE_W)$" "$CPW")" "1:1"
check "a spawn record 20 h old (after the 30 h-old start) is listed: a 12 h window would have dropped it" "$(grep -c 'MID-SPAWN-20H' "$CPW")" "1"
check "a record 40 h old (before the start) is not; a fresh one is" "$(grep -c 'BEFORE-SPAWN-40H' "$CPW"):$(grep -c 'NOW-SPAWN' "$CPW")" "0:1"
check "the 20 h-old vault file enters this session's window: overflow 35, not 34" "$(grep -c '^… and 35 more$' "$CPW")" "1"

echo "== i. PreCompact with a missing transcript, missing cwd and missing record dirs still writes a stub (24 h fallback named); an unwritable state dir fails on stderr only =="
JI='{"session_id":"sid-i-9999","cwd":"'"$F"'/nonexistent-cwd","hook_event_name":"PreCompact","trigger":"manual","custom_instructions":"keep the plan"}'
OUT=$(pc "$JI" AIMYTH_INGEST_RUNS="$F/nodir-runs" AIMYTH_SPAWN_RECORDS="$F/nodir-spawn" 2>"$F/state/pc-err2.txt"); RC=$?
CPI=$(find "$H" -name "sid-i-9999-*-precompact.md" -type f | head -1)
check "exit 0, stub written" "$RC:$([ -n "$CPI" ] && echo written)" "0:written"
check "seven sections in the stub" "$(grep -c '^## ' "$CPI")" "7"
check "no transcript -> both list headings say 'last 24 h — no session start found'" "$(grep -Fxc "$HEAD_SPAWN_NA" "$CPI"):$(grep -Fxc "$HEAD_VAULT_NA" "$CPI")" "1:1"
check "context unmetered in the header" "$(grep -c '^- context: unmetered (no transcript_path)$' "$CPI")" "1"
check "custom instructions carried" "$(grep -c 'custom instructions: keep the plan' "$CPI")" "1"
check "record dirs missing -> n/a with the path" "$(grep -Fc "n/a (directory missing: $F/nodir-" "$CPI")" "2"
check "cwd missing -> vault list n/a" "$(grep -Fxc "n/a (cwd missing: $F/nonexistent-cwd)" "$CPI")" "1"
check "log tail n/a" "$(grep -c '^n/a (no wiki/log.md under ' "$CPI")" "1"
check "role state n/a" "$(grep -c '^n/a (no state file at ' "$CPI")" "1"
check "events.log line carries 'unmetered'" "$(grep -c "sid-i-9999	PreCompact	manual	unmetered	" "$H/events.log")" "1"
OUT=$(pc "$(pcs sid-i2-9998 "$F/projects/proj/empty.jsonl" "$F/vault" auto)" 2>"$F/state/legacy-diagnostics.txt")
CPI2=$(find "$H" -name "sid-i2-9998-*-precompact.md" -type f | head -1)
check "a transcript with no timestamp -> the 24 h fallback heading too" "$(grep -Fxc "$HEAD_SPAWN_NA" "$CPI2")" "1"
: > "$F/state/blocked"
OUT=$(pc "$JI" AIMYTH_STATE_DIR="$F/state/blocked/sub" 2>"$F/state/pc-err3.txt"); RC=$?
check "unwritable state dir: exit 0, no stdout, failure on stderr" "$RC:$OUT:$(grep -c 'checkpoint write failed' "$F/state/pc-err3.txt")" "0::1"
OUT=$(printf '%s' "$JI" | env AIMYTH_STATE_DIR="$F/state/alone" AIMYTH_INGEST_RUNS="$F/nodir-runs" AIMYTH_SPAWN_RECORDS="$F/nodir-spawn" AIMYTH_ROLE_STATE_DIR="$F/role" "$PY" -B "$F/hookalone/precompact-checkpoint.py" 2>"$F/state/legacy-diagnostics.txt"); RC=$?
CPA=$(find "$F/state/alone" -name "sid-i-9999-*-precompact.md" -type f | head -1)
check "watermark module absent beside the hook: header degrades to n/a, checkpoint still written" "$RC:$(grep -c '^- n/a (watermark module unavailable: ' "$CPA")" "0:1"

echo "== j. SessionStart(compact) logs the event and injects the newest checkpoint for THAT session, capped at 7 kB =="
NL0=$(wc -l < "$H/events.log" | tr -d ' ')
OUT=$(pc "$(ssj "$SJ" "$T_A" "$F/vault" compact)"); RC=$?
ctxof "$OUT" > "$F/state/rebrief.txt"
check "exit 0" "$RC" "0"
check "hookEventName SessionStart" "$(head -c 13 "$F/state/rebrief.txt")" "SessionStart|"
check "first line names the newest checkpoint of this session" "$(grep -c "read $H/$SJ-20260903-020000-precompact.md (reproduced below)" "$F/state/rebrief.txt")" "1"
check "newest body present; older, name-newest decoy and other session's absent" "$(grep -c MARKER-J-NEW "$F/state/rebrief.txt"):$(grep -c 'MARKER-J-OLD\|MARKER-J-NAMEDECOY\|MARKER-B' "$F/state/rebrief.txt")" "1:0"
check "7 kB cap: tail of the 20 kB body cut, truncation note present" "$(grep -c TAIL-J-NEW "$F/state/rebrief.txt"):$(grep -c '… \[truncated: [0-9]* of [0-9]* bytes shown; read the file for the rest\]' "$F/state/rebrief.txt")" "0:1"
RB=$(wc -c < "$F/state/rebrief.txt" | tr -d ' ')
[ "$RB" -le $((7168 + 512)) ] && ok "injected text is $RB bytes (<= 7168 body + path line and note)" || bad "injected text is $RB bytes, over the cap"
check "the compact event logged: four fields, source compact" "$(tail -1 "$H/events.log" | awk -F'\t' '{print NF"|"$2"|"$3"|"$4}')" "4|$SJ|SessionStart|compact"
OUT=$(pc "$(ssj "$SC" "$T_A" "$F/vault" compact)"); RC=$?
check "no checkpoint for the session: one line naming session and state dir" "$RC:$(ctxof "$OUT" | grep -c "no checkpoint exists for session $SC in $H")" "0:1"
OUT=$(pc "$(ssj "$SC" "$T_A" "$F/vault" compact)" AIMYTH_STATE_DIR="$F/state/never-before"); RC=$?
check "state dir absent: created for the event log, the line names it, the event logged" "$RC:$(ctxof "$OUT" | grep -c "in $F/state/never-before"):$(grep -c "	$SC	SessionStart	compact$" "$F/state/never-before/events.log")" "0:1:1"
check "events.log in the main state dir grew by exactly the two compact events" "$(( $(wc -l < "$H/events.log" | tr -d ' ') - NL0 ))" "2"

echo "== k. every SessionStart is logged with its source; only compact injects; foreign events and malformed stdin are silent and unlogged =="
NB=$(find "$H" -type f | wc -l | tr -d ' '); NL=$(wc -l < "$H/events.log" | tr -d ' ')
for src in startup resume clear; do
  OUT=$(pc "$(ssj "$SA" "$T_A" "$F/vault" "$src")"); RC=$?; check "source $src: exit 0, no stdout" "$RC:$OUT" "0:"
  check "…logged as ts, session, SessionStart, $src" "$(tail -1 "$H/events.log" | awk -F'\t' '{print NF"|"$2"|"$3"|"$4}')" "4|$SA|SessionStart|$src"
done
OUT=$(pc '{"session_id":"s","hook_event_name":"SessionStart"}'); RC=$?; check "source absent: silent" "$RC:$OUT" "0:"
check "…logged as 'missing'" "$(tail -1 "$H/events.log" | awk -F'\t' '{print $3"|"$4}')" "SessionStart|missing"
OUT=$(pc "$(ups "$SA" "$T_A" "$F/vault")"); RC=$?; check "UserPromptSubmit event through this hook: silent" "$RC:$OUT" "0:"
OUT=$(pc '{"hook_event_name":"Stop"}'); RC=$?; check "Stop event: silent" "$RC:$OUT" "0:"
for s in 'not json' '[]' ''; do OUT=$(pc "$s"); RC=$?; check "malformed stdin '$s': silent exit 0" "$RC:$OUT" "0:"; done
check "events.log grew by exactly the four SessionStart lines; no other state file written" "$(( $(wc -l < "$H/events.log" | tr -d ' ') - NL )):$(find "$H" -type f | wc -l | tr -d ' ')" "4:$NB"

echo "== j2. re-brief cap and order: a ~11 kB real-shaped checkpoint re-briefs with the five short sections intact and the note on the lists =="
OUT=$(pc "$(pcs "$SR" "$T_A" "$F/vault" auto)" AIMYTH_SPAWN_RECORDS="$F/llm-big/spawn-records" 2>"$F/state/legacy-diagnostics.txt"); RC=$?
CPR=$(find "$H" -name "$SR-*-precompact.md" -type f | head -1)
CPRB=$(wc -c < "$CPR" | tr -d ' ')
[ "$CPRB" -ge 10000 ] && ok "positive control: the checkpoint is $CPRB bytes, over the 8,192 cap" || bad "checkpoint only $CPRB bytes: the cap would not bite"
check "spawn list capped at 20 with the overflow line for the other 5" "$(sect "$CPR" "$HEAD_SPAWN_A" | grep -c '^- '):$(grep -c '^… and 5 more$' "$CPR")" "20:1"
OUT=$(pc "$(ssj "$SR" "$T_A" "$F/vault" compact)"); RC=$?; ctxof "$OUT" > "$F/state/rebrief-r.txt"
check "exit 0" "$RC" "0"
for hd in "## Session" "## Instruction" "## Log tail" "## Role/style state" "## Open runs"; do grep -Fxq "$hd" "$F/state/rebrief-r.txt" && ok "re-brief keeps $hd" || bad "re-brief lost $hd"; done
check "…with their content: instruction, fifth log heading, role JSON, open-run last line" "$(grep -c 'The transcript is not the durable memory' "$F/state/rebrief-r.txt"):$(grep -c '^- \[2026-09-07\] framework | Entry 7$' "$F/state/rebrief-r.txt"):$(grep -c '"role": "critic"' "$F/state/rebrief-r.txt"):$(grep -c 'OPEN-RUN-LAST-LINE' "$F/state/rebrief-r.txt")" "1:1:1:1"
check "the cut falls in the lists: the vault section is beyond the cap, the truncation note present" "$(grep -c '^## Vault files modified' "$F/state/rebrief-r.txt"):$(grep -c '… \[truncated: ' "$F/state/rebrief-r.txt")" "0:1"
RBR=$(wc -c < "$F/state/rebrief-r.txt" | tr -d ' ')
[ "$RBR" -le $((7168 + 512)) ] && ok "injected text is $RBR bytes (<= 7168 body + path line and note)" || bad "injected text is $RBR bytes, over the cap"

echo "== n. three edges, two-edge compatibility, the turn-1 start line, the hand-off suffix =="
OUT=$(wm "$(ups "$SA" "$F/projects/proj/band-590.jsonl" "$F/vault")" AIMYTH_CONTEXT_WINDOW=1000 AIMYTH_BANDS=20,30,40)
check "three edges 20,30,40: 59 % is the hard band" "$(ctxof "$OUT" | sed 's|.* · ||')" "$BAND3"
OUT=$(wm "$(ups "$SA" "$F/projects/proj/band-590.jsonl" "$F/vault")" AIMYTH_CONTEXT_WINDOW=1000 AIMYTH_BANDS=20,30,60)
check "…and 59 % under a third edge of 60 is the second band, not the hard one" "$(ctxof "$OUT" | sed 's|.* · ||')" "$BAND2"
OUT=$(wm "$(ups "$SA" "$F/projects/proj/band-900.jsonl" "$F/vault")" AIMYTH_CONTEXT_WINDOW=1000 AIMYTH_BANDS=60,80)
check "two-edge compatibility: 90 % under 60,80 keeps the attended top text" "$(ctxof "$OUT" | sed 's|.* · ||')" "$BAND2"
for bad in 60,70,80,90 80,60 60,0,90 60,80,101 60,,90; do
  OUT=$(wm "$(ups "$SA" "$F/projects/proj/band-900.jsonl" "$F/vault")" AIMYTH_CONTEXT_WINDOW=1000 AIMYTH_BANDS="$bad" 2>"$F/state/bands-bad.txt")
  check "AIMYTH_BANDS=$bad refused, the default used (900 -> the hard band), and said on stderr" "$(ctxof "$OUT" | sed 's|.* · ||'):$(grep -c 'AIMYTH_BANDS' "$F/state/bands-bad.txt")" "$BAND3:1"
done
OUT=$(wm "$(ups "$SA" "$F/projects/proj/absent.jsonl" "$F/vault")"); RC=$?
check "a missing transcript is turn 1, not a fault: the start line, exit 0" "$RC:$(ctxof "$OUT")" "0:UserPromptSubmit|$START"
OUT=$(wm "$(ups "$SA" "$F/projects/proj/empty.jsonl" "$F/vault")")
check "an empty transcript is turn 1 too" "$(ctxof "$OUT")" "UserPromptSubmit|$START"
OUT=$(wm "$(ups s "$F/projects/proj/nousage.jsonl" x)")
check "negative control: a transcript with no usage record stays unmetered, not a start" "$(ctxof "$OUT")" "UserPromptSubmit|context: unmetered (no qualifying usage record in the tail)"
probe "hand-off fixture on disk" "$([ -f "$HOFF" ] && echo yes || echo no)" "yes"
OUT=$(wm "$(upsp "$SA" "$T_A" "$F/vault" "resume from $HOFF and continue")")
check "a prompt naming an existing hand-off: the suffix is appended to the metered line" "$(ctxof "$OUT")" "UserPromptSubmit|context: 284,481 tokens (28 % of 1M) · transcript 200.0 kB · $(fitx 284,481) · hand-off named: $HOFF"
OUT=$(wm "$(upsp "$SA" "$F/projects/proj/absent.jsonl" "$F/vault" "resume from $HOFF")")
check "…and to the turn-1 start line (the successor's first turn: G14)" "$(ctxof "$OUT")" "UserPromptSubmit|$START · hand-off named: $HOFF"
OUT=$(wm "$(upsp "$SA" "$T_A" "$F/vault" "quoted ($HOFF), in a sentence.")")
check "…a bracketed path with trailing punctuation is still found" "$(ctxof "$OUT" | sed 's|.* · ||')" "hand-off named: $HOFF"
OUT=$(wm "$(upsp "$SA" "$T_A" "$F/vault" "resume from $F/handoffs/absent-handoff.md")")
check "negative control: a named hand-off that is not on disk adds nothing" "$(ctxof "$OUT" | grep -c 'hand-off named')" "0"
OUT=$(wm "$(upsp "$SA" "$T_A" "$F/vault" "see $F/handoffs/notes.md and $F/decoy/elsewhere-handoff.md")")
check "negative control: a non-hand-off file in the directory, and a hand-off outside it, add nothing" "$(ctxof "$OUT" | grep -c 'hand-off named')" "0"

echo "== o. handsoff-gate: unarmed silence, the hard band, the bounded-read rule, marker arming, premise failures =="
T91="$F/projects/proj/ctx-182000.jsonl"; T85="$F/projects/proj/ctx-170000.jsonl"; T50="$F/projects/proj/ctx-100000.jsonl"
RD='{"file_path":"x"}'; RD200='{"file_path":"x","limit":200}'; RD500='{"file_path":"x","limit":500}'; RDBAD='{"file_path":"x","limit":"abc"}'
E="$F/state/gate-err.txt"
OUT=$(gate "$(ptu "$SA" "$T91" "$F/vault" Read "$RD")" 2>"$E"); RC=$?
check "unarmed at 91 %: no stdout, exit 0" "$RC:$(dec "$OUT")" "0:(silent)"
check "…and nothing on stderr either" "$(wc -c < "$E" | tr -d ' ')" "0"
OUT=$(gate "$(ptu "$SA" "$T91" "$F/vault" Read "$RD")" AIMYTH_HANDSOFF=1 2>"$E"); RC=$?
check "armed at 91 %: Read denied, exit 0" "$RC:$(dec "$OUT" | cut -d'|' -f1-2)" "0:PreToolUse|deny"
check "…the reason names the figure, the edge and the four allowed commands" "$(dec "$OUT" | grep -c 'hands-off hard band: context 182,000 tokens (91 % of 200k), at or above the 90 % edge.*handsoff.py handoff, handsoff.py successor, handsoff.py boundary, handsoff.py ledger')" "1"
for c in handoff successor boundary ledger; do
  OUT=$(gate "$(ptu "$SA" "$T91" "$F/vault" Bash '{"command":"python3 handsoff.py '"$c"' --run r"}')" AIMYTH_HANDSOFF=1 2>"$E")
  check "armed at 91 %: Bash handsoff.py $c allowed by silence, never an explicit allow" "$(dec "$OUT"):$(wc -c < "$E" | tr -d ' ')" "(silent):0"
done
OUT=$(gate "$(ptu "$SA" "$T91" "$F/vault" Bash '{"command":"ls -la"}')" AIMYTH_HANDSOFF=1 2>"$E")
check "…any other Bash command is denied" "$(dec "$OUT" | cut -d'|' -f2)" "deny"
OUT=$(gate "$(ptu "$SA" "$T91" "$F/vault" Bash '{}')" AIMYTH_HANDSOFF=1 2>"$E")
check "…a Bash call with no command field is denied" "$(dec "$OUT" | cut -d'|' -f2)" "deny"
OUT=$(gate "$(ptu "$SA" "$F/projects/proj/absent.jsonl" "$F/vault" Read "$RD")" AIMYTH_HANDSOFF=1 2>"$E"); RC=$?
check "armed with no transcript: allowed, exit 0" "$RC:$(dec "$OUT")" "0:(silent)"
check "…with the premise failure named on stderr" "$(grep -c 'premise failure: transcript missing; allowing Read' "$E")" "1"
OUT=$(gate "$(ptu "$SA" "$F/projects/proj/nousage.jsonl" "$F/vault" Read "$RD")" AIMYTH_HANDSOFF=1 2>"$E")
check "armed with no usage record: allowed, named on stderr" "$(dec "$OUT"):$(grep -c 'premise failure: no qualifying usage record' "$E")" "(silent):1"
: > "$GS/armed-$SB"
OUT=$(gate "$(ptu "$SB" "$T91" "$F/vault" Read "$RD")" 2>"$E")
check "the marker file arms the session with no environment variable set" "$(dec "$OUT" | cut -d'|' -f2)" "deny"
OUT=$(gate "$(ptu "$SC" "$T91" "$F/vault" Read "$RD")" 2>"$E")
check "negative control: a session with no marker of its own stays silent" "$(dec "$OUT")" "(silent)"
rm -f "$GS/armed-$SB"
OUT=$(gate "$(ptu "$SB" "$T91" "$F/vault" Read "$RD")" 2>"$E")
check "…and removing the marker disarms it" "$(dec "$OUT")" "(silent)"
OUT=$(gate "$(ptu "$SA" "$T85" "$F/vault" Read "$RD")" AIMYTH_HANDSOFF=1 2>"$E")
check "armed at 85 %: a Read with no limit is denied" "$(dec "$OUT" | cut -d'|' -f2)" "deny"
check "…the reason names the bound and the figure" "$(dec "$OUT" | grep -c 'bounded reads only above 80 % under hands-off: pass limit ≤ 400 (this Read: no limit; context 170,000 tokens (85 % of 200k))')" "1"
OUT=$(gate "$(ptu "$SA" "$T85" "$F/vault" Read "$RD200")" AIMYTH_HANDSOFF=1 2>"$E")
check "armed at 85 %: a Read with limit 200 passes untouched" "$(dec "$OUT")" "(silent)"
OUT=$(gate "$(ptu "$SA" "$T85" "$F/vault" Read "$RD500")" AIMYTH_HANDSOFF=1 2>"$E")
check "…a limit of 500 is denied" "$(dec "$OUT" | cut -d'|' -f2)" "deny"
OUT=$(gate "$(ptu "$SA" "$T85" "$F/vault" Read "$RDBAD")" AIMYTH_HANDSOFF=1 2>"$E")
check "…a limit that is not a number bounds nothing and is denied" "$(dec "$OUT" | cut -d'|' -f2)" "deny"
OUT=$(gate "$(ptu "$SA" "$T85" "$F/vault" Read "$RD")" 2>"$E")
check "unarmed at 85 %: the same unbounded Read is untouched" "$(dec "$OUT")" "(silent)"
OUT=$(gate "$(ptu "$SA" "$T50" "$F/vault" Read "$RD")" AIMYTH_HANDSOFF=1 2>"$E")
check "armed at 50 %: below the second band a Read is never touched" "$(dec "$OUT")" "(silent)"
OUT=$(gate "$(ptu "$SA" "$T85" "$F/vault" Bash '{"command":"ls -la"}')" AIMYTH_HANDSOFF=1 2>"$E")
check "armed at 85 %: a Bash call below the hard band is untouched" "$(dec "$OUT")" "(silent)"
OUT=$(gate "$(ptu "$SA" "$T85" "$F/vault" Edit '{"file_path":"x"}')" AIMYTH_HANDSOFF=1 2>"$E")
check "armed at 85 %: the bound is Read's alone, an Edit is untouched" "$(dec "$OUT")" "(silent)"
check "every deny logged: six tab fields — session, handsoff-gate, deny, tool, context" "$(tail -1 "$GS/events.log" | awk -F'\t' '{print NF"|"$2"|"$3"|"$4"|"$5"|"$6}')" "6|$SA|handsoff-gate|deny|Read|170000"
NG=$(wc -l < "$GS/events.log" | tr -d ' ')
OUT=$(gate "$(ptu "$SA" "$T91" "$F/vault" Bash '{"command":"python3 handsoff.py handoff"}')" AIMYTH_HANDSOFF=1 2>"$E")
OUT=$(gate "$(ptu "$SA" "$T50" "$F/vault" Read "$RD")" AIMYTH_HANDSOFF=1 2>"$E")
check "an allowed call logs nothing" "$(( $(wc -l < "$GS/events.log" | tr -d ' ') - NG ))" "0"
: > "$F/state/gate-blocked"
OUT=$(gate "$(ptu "$SA" "$T91" "$F/vault" Read "$RD")" AIMYTH_HANDSOFF=1 AIMYTH_STATE_DIR="$F/state/gate-blocked/sub" 2>"$E")
check "an unwritable state dir does not downgrade the deny" "$(dec "$OUT" | cut -d'|' -f2)" "deny"
check "…and the failed append is on stderr" "$(grep -c 'events.log append failed' "$E")" "1"
for s in 'not json' '[]' ''; do
  OUT=$(gate "$s" AIMYTH_HANDSOFF=1 2>"$E"); RC=$?
  check "payload '$s': allowed, exit 0, premise failure on stderr" "$RC:$(dec "$OUT"):$(grep -c 'premise failure: unreadable payload' "$E")" "0:(silent):1"
done
OUT=$(gate '{"session_id":"s","hook_event_name":"Stop","tool_name":"Read"}' AIMYTH_HANDSOFF=1 2>"$E"); RC=$?
check "a foreign event (mis-registration): silent, noted on stderr, exit 0" "$RC:$(dec "$OUT"):$(grep -c 'ignoring event Stop' "$E")" "0:(silent):1"
OUT=$(gate "$(ptu "$SA" "$T91" "$F/vault" Bash '{"command":"cat big.jsonl"}')" AIMYTH_HANDSOFF=1 AIMYTH_BANDS=60,80 2>"$E")
check "two edges configured: no hard band exists, so the call is allowed" "$(dec "$OUT")" "(silent)"
check "…and the hook says so on stderr" "$(grep -c 'carry no third edge' "$E")" "1"
OUT=$(gate "$(ptu "$SA" "$T91" "$F/vault" Read "$RD")" AIMYTH_HANDSOFF=1 AIMYTH_BANDS=60,80 2>"$E")
check "…the read bound still applies at the second edge" "$(dec "$OUT" | cut -d'|' -f2)" "deny"
OUT=$(printf '%s' "$(ptu "$SA" "$T91" "$F/vault" Read "$RD")" | env AIMYTH_HANDSOFF=1 AIMYTH_STATE_DIR="$GS" AIMYTH_PROJECTS_DIR="$F/projects" AIMYTH_CONTEXT_WINDOW=200000 "$PY" -B "$F/gatealone/handsoff-gate.py" 2>"$E"); RC=$?
check "watermark module absent beside the gate: allowed, exit 0, named on stderr" "$RC:$(dec "$OUT"):$(grep -c 'premise failure: watermark module unavailable' "$E")" "0:(silent):1"
: > "$F/home/.aimyth/handoffs/armed-$SC"
OUT=$(printf '%s' "$(ptu "$SC" "$T91" "$F/vault" Read "$RD")" | env HOME="$F/home" AIMYTH_HANDSOFF= AIMYTH_PROJECTS_DIR="$F/projects" AIMYTH_CONTEXT_WINDOW=200000 "$PY" -B "$HG" 2>"$E")
check "default state dir: a marker under HOME/.aimyth/handoffs arms the session" "$(dec "$OUT" | cut -d'|' -f2)" "deny"
check "…and the deny is logged there" "$(awk -F'\t' '$3=="handsoff-gate"' "$F/home/.aimyth/handoffs/events.log" | wc -l | tr -d ' ')" "1"

echo "== o2. timing: the armed gate on the 2 MB transcript, deny path (5 runs, python start-up included) =="
ptu "$SA" "$T_E" "$F/vault" Read "$RD" > "$F/state/stdin-gate.json"
GMS=$(env AIMYTH_PROJECTS_DIR="$F/projects" AIMYTH_STATE_DIR="$GS" AIMYTH_HANDSOFF=1 AIMYTH_CONTEXT_WINDOW=200000 "$PY" -B - "$PY" "$HG" "$F/state/stdin-gate.json" <<'PYG'
import subprocess, sys, time
py, hook, stdin = sys.argv[1:4]
data = open(stdin, "rb").read()
runs = []
for _ in range(5):
    t = time.perf_counter()
    subprocess.run([py, "-B", hook], input=data, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    runs.append(int((time.perf_counter() - t) * 1000))
runs.sort()
print("%d %d %d" % (runs[0], runs[2], runs[-1]))
PYG
)
set -- $GMS; GMIN=$1; GMED=$2; GMAX=$3
[ "$GMED" -lt 500 ] && ok "gate median $GMED ms (min $GMIN, max $GMAX) under 500 ms, and it runs on every tool call" || bad "gate median $GMED ms (min $GMIN, max $GMAX) at or over 500 ms"

echo "== o3. handsoff-gate: the run's last lead may stop its tasks and close at the hard band (owner decision 2026-10-30); another session, a lead with a successor left and an unreadable count keep the deny =="
# The hook imports handsoff.py (and the lane.py it loads) from the delegate skill beside its own
# folder. The real hook is run where that sibling exists (the installed layout); a staged copy
# without it runs a layout built under $F from the copies beside this suite. Neither present is a
# broken premise, not a clean run.
HGDEL="$HOOKS/../skills/delegate"
if [ -f "$HGDEL/handsoff.py" ] && [ -f "$HGDEL/lane.py" ]; then
  HGO="$HG"
else
  { [ -f "$HOOKS/handsoff.py" ] && [ -f "$HOOKS/lane.py" ]; } || { echo "PROBE FAILED: no handsoff.py and lane.py beside the hooks' delegate folder or beside this suite"; exit 2; }
  mkdir -p "$F/hglayout/hooks" "$F/hglayout/skills/delegate"
  cp "$HG" "$WM" "$F/hglayout/hooks/"
  cp "$HOOKS/handsoff.py" "$HOOKS/lane.py" "$F/hglayout/skills/delegate/"
  HGDEL="$F/hglayout/skills/delegate"; HGO="$F/hglayout/hooks/handsoff-gate.py"
fi
HGSTORE="$F/hg-store"; mkdir -p "$HGSTORE/spawn-records"
HGL=sid-hg-lead-7777; HGX=sid-hg-other-8888; HGN=sid-hg-nopointer-9999; HGR=sid-hg-newer-6666
# Three records: run-hg-last at 3 of 3 (its last head start is HGL's), run-hg-more at 3 of 4, and
# run-hg-bad at 3 used with a grants file of garbage bytes (its cap falls back past a faulty file).
# Three more at exhaustion on the default of 20 (build review RV-CAP finding F5), each with HGL's
# head start last: run-hg-keyless, a readable grants file with no max_successors key (a run that set
# no cap, so the default is its decided cap); run-hg-badval, an unusable value; and run-hg-bad20,
# garbage bytes (each a fault, so undecided).
# Three more of run-hg-last's shape (build review RV-CAP4 finding F1), with run-hg-last itself, HG-1's
# record, as their intact exhausted/current-lead control: run-hg-newer gains a newer lead's
# run-resume (HGR, a session that resumed the run), whole; run-hg-torn the same row torn, its
# closing brace lost as a cut write leaves it; and run-hg-midbad keeps every row whole but gains one
# older line that is JSON and not an object, read_record's other unreadable kind.
"$PY" -B - "$HGSTORE/spawn-records" "$HGL" "$HGR" <<'HGREC'
import json, os, sys, time
d, lead, newer = sys.argv[1], sys.argv[2], sys.argv[3]
stamp = lambda t: time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t))
base = time.time() - 3600
def write(run, cap, used, grants_text=None):
    rows = [{"event": "run-open", "session": "sid-%s-seed" % run, "head": "h", "regime": "multi",
             "regime_src": "owner", "handoff": os.path.join(d, run + "-handoff.md"),
             "detail": "o3 fixture", "pid_src": "none", "session_kind": "seed"}]
    for i in range(used):
        sid = lead if i == used - 1 else "sid-%s-%d" % (run, i)
        rows += [{"event": "head-exit", "band": 60, "pack": True},
                 {"event": "head-successor", "session_id": sid},
                 {"event": "run-resume", "session": sid, "head": "h", "detail": "d", "pid_src": "none"}]
    with open(os.path.join(d, run + ".jsonl"), "w", encoding="utf-8") as fh:
        for k, r in enumerate(rows):
            r.update(ts=stamp(base + k), run=run)
            fh.write(json.dumps(r) + "\n")
    with open(os.path.join(d, run + "-grants.json"), "w", encoding="utf-8") as fh:
        fh.write(grants_text if grants_text is not None else
                 json.dumps({"run": run, "grants": [], "writes": [], "max_successors": cap}))
write("run-hg-last", 3, 3)
write("run-hg-more", 4, 3)
write("run-hg-bad", None, 3, "not json at all\n")
write("run-hg-keyless", None, 20, json.dumps({"run": "run-hg-keyless", "grants": [], "writes": []}))
write("run-hg-badval", None, 20, json.dumps({"run": "run-hg-badval", "grants": [], "writes": [],
                                              "max_successors": "six"}))
write("run-hg-bad20", None, 20, "not json at all\n")
def amend(run, row=None, torn=False, junk_after=None):
    path = os.path.join(d, run + ".jsonl")
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    if row is not None:
        text = json.dumps(dict(row, ts=stamp(base + len(lines)), run=run))
        lines.append(text[:-1] if torn else text)
    if junk_after is not None:
        lines.insert(junk_after, json.dumps(["head-exit", 60]))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
resume = {"event": "run-resume", "session": newer, "head": "h", "detail": "d", "pid_src": "none"}
for run in ("run-hg-newer", "run-hg-torn", "run-hg-midbad"):
    write(run, 3, 3)
amend("run-hg-newer", resume)
amend("run-hg-torn", resume, torn=True)
amend("run-hg-midbad", junk_after=4)
HGREC
printf 'run-hg-last\n' > "$GS/run-$HGL"
# The armed hook with every knob the allowance reads set here; a caller's later assignment wins.
hg(){ j="$1"; shift; printf '%s' "$j" | env AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN= AIMYTH_MAX_SUCCESSORS= \
      LLM_WIKI_STORE="$HGSTORE" AIMYTH_PROJECTS_DIR="$F/projects" AIMYTH_STATE_DIR="$GS" \
      AIMYTH_CONTEXT_WINDOW=200000 ${1+"$@"} "$PY" -B "$HGO"; }
hgcount(){ if [ -f "$GS/events.log" ]; then awk -F'\t' -v a="$1" '$3=="handsoff-gate" && $4==a' "$GS/events.log" | wc -l | tr -d ' '; else echo 0; fi; }
HGTS='{"task_id":"t1"}'
HGCL='{"command":"python3 /fixture/handsoff.py close --run run-hg-last --items 1"}'
LASTLEAD="The run's last lead (no successor left) may also stop its background tasks with TaskStop and close the run with handsoff.py close."
# HG-6's before: the store, the state directory (events.log aside) and the delegate folder's
# listing, __pycache__ included, and the hook copy's bytecode.
manifest "$HGSTORE" > "$F/hg-store.before"
manifest "$GS" | grep -v '/events.log$' > "$F/hg-state.before"
ls -la "$HGDEL" "$HGDEL/__pycache__" 2>&1 | grep -v '^total ' | awk '{print $1, $5, $NF}' > "$F/hg-del.before"
find "$F/hookcopy" -name '__pycache__' | wc -l | tr -d ' ' > "$F/hg-hookcopy.before"

NA=$(hgcount allow-last-lead)
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" TaskStop "$HGTS")" AIMYTH_HANDSOFF_RUN=run-hg-last 2>"$E"); RC=$?
check "HG-1 last lead at 91 %: TaskStop allowed by silence, exit 0" "$RC:$(dec "$OUT")" "0:(silent)"
check "…a stderr note names the clause and the owner decision" "$(grep -c "TaskStop allowed for the run's last lead (successors: 3 of 3 started, none left.*the owner's decision of 2026-10-30" "$E")" "1"
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" Bash "$HGCL")" AIMYTH_HANDSOFF_RUN=run-hg-last 2>"$E"); RC=$?
check "HG-1 last lead at 91 %: Bash handsoff.py close allowed by silence, exit 0" "$RC:$(dec "$OUT")" "0:(silent)"
check "…one allow-last-lead line per allowance in events.log (two calls)" "$(( $(hgcount allow-last-lead) - NA ))" "2"
check "…the events line has six tab fields: session, handsoff-gate, allow-last-lead, tool, context" "$(awk -F'\t' '$4=="allow-last-lead"' "$GS/events.log" | tail -1 | awk -F'\t' '{print NF"|"$2"|"$3"|"$4"|"$5"|"$6}')" "6|$HGL|handsoff-gate|allow-last-lead|Bash|182000"
ND=$(hgcount deny)
OUT=$(hg "$(ptu "$HGX" "$T91" "$F/vault" TaskStop "$HGTS")" AIMYTH_HANDSOFF_RUN=run-hg-last 2>"$E")
check "HG-1b (review CR-CAP2 finding 1) another armed session of the run at 3 of 3: TaskStop denied, the reason naming that it is not the run's current lead and the record's current head session" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c "TaskStop passes at the hard band only for the run's last lead, and this lead is not (successors: 3 of 3 started, none left; this session ($HGX) is not the run's current lead: the record's current head session is $HGL)")" "deny:1"
OUT=$(hg "$(ptu "$HGX" "$T91" "$F/vault" Bash "$HGCL")" AIMYTH_HANDSOFF_RUN=run-hg-last 2>"$E")
check "…and its handsoff.py close is denied the same way" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c 'handsoff.py close passes at the hard band only for the run.s last lead')" "deny:1"
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" TaskStop "$HGTS")" AIMYTH_HANDSOFF_RUN=run-hg-more 2>"$E")
check "HG-2 a lead with a successor left (3 of 4): TaskStop denied, the reason naming the count" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c 'TaskStop passes at the hard band only for the run.s last lead, and this lead is not (successors: 3 of 4 started, 1 left)')" "deny:1"
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" Bash "$HGCL")" AIMYTH_HANDSOFF_RUN=run-hg-more 2>"$E")
check "…its handsoff.py close is denied too, named, and each denial wrote a deny line (four so far in o3)" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c 'handsoff.py close passes at the hard band only for the run.s last lead, and this lead is not (successors: 3 of 4 started, 1 left)'):$(( $(hgcount deny) - ND ))" "deny:1:4"
OUT=$(hg "$(ptu "$HGN" "$T91" "$F/vault" TaskStop "$HGTS")" 2>"$E")
check "HG-3 no environment run and no pointer: denied, the premise named" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c 'whether this lead is the run.s last could not be read (no run: no AIMYTH_HANDSOFF_RUN and no run pointer at')" "deny:1"
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" TaskStop "$HGTS")" AIMYTH_HANDSOFF_RUN=run-hg-none 2>"$E")
check "HG-3 a record that does not exist: denied, the premise named" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c 'could not be read (the run record .*run-hg-none.jsonl is missing)')" "deny:1"
OUT=$(printf '%s' "$(ptu "$HGL" "$T91" "$F/vault" TaskStop "$HGTS")" | env AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=run-hg-last AIMYTH_MAX_SUCCESSORS= LLM_WIKI_STORE="$HGSTORE" AIMYTH_PROJECTS_DIR="$F/projects" AIMYTH_STATE_DIR="$GS" AIMYTH_CONTEXT_WINDOW=200000 "$PY" -B "$F/hookcopy/handsoff-gate.py" 2>"$E")
check "HG-3 the hook copy with no ../skills/delegate/handsoff.py beside it: denied, the premise named" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c 'could not be read (FileNotFoundError')" "deny:1"
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" TaskStop "$HGTS")" AIMYTH_HANDSOFF_RUN=run-hg-bad 2>"$E")
check "HG-3 (review CR-CAP2 finding 6) a grants file whose cap cannot be read: denied, the fault named" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c 'could not be read (successors: 3 of 20 started.*the grants file is unreadable (')" "deny:1"
# Build review RV-CAP4 finding F1: a record with an unreadable line cannot show who leads the run, so
# the allowance is undecided and the deny stands, the premise named; the intact controls keep theirs.
NA3=$(hgcount allow-last-lead); ND3=$(hgcount deny)
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" TaskStop "$HGTS")" AIMYTH_HANDSOFF_RUN=run-hg-torn 2>"$E")
check "HG-3 (build review RV-CAP4 finding F1) 3 of 3 with a newer lead's run-resume torn as the newest row: the previous lead's TaskStop denied, the unreadable line named" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c "TaskStop: whether this lead is the run's last could not be read (the run record .*/run-hg-torn.jsonl has 1 unreadable line(s), any of which may be a newer head start or resume)")" "deny:1"
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" Bash "$HGCL")" AIMYTH_HANDSOFF_RUN=run-hg-torn 2>"$E")
check "…and its handsoff.py close denied the same way" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c "handsoff.py close: whether this lead is the run's last could not be read (the run record .*/run-hg-torn.jsonl has 1 unreadable line(s), any of which may be a newer head start or resume)")" "deny:1"
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" TaskStop "$HGTS")" AIMYTH_HANDSOFF_RUN=run-hg-midbad 2>"$E")
check "HG-3 (RV-CAP4 F1) 3 of 3, every row whole and the lead's head start last, one older line JSON but not an object: TaskStop denied, the unreadable line named" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c "TaskStop: whether this lead is the run's last could not be read (the run record .*/run-hg-midbad.jsonl has 1 unreadable line(s), any of which may be a newer head start or resume)")" "deny:1"
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" Bash "$HGCL")" AIMYTH_HANDSOFF_RUN=run-hg-midbad 2>"$E")
check "…and its handsoff.py close denied the same way" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c "handsoff.py close: whether this lead is the run's last could not be read (the run record .*/run-hg-midbad.jsonl has 1 unreadable line(s), any of which may be a newer head start or resume)")" "deny:1"
check "…the four calls wrote four deny lines and no allow-last-lead line" "$(( $(hgcount deny) - ND3 )):$(( $(hgcount allow-last-lead) - NA3 ))" "4:0"
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" TaskStop "$HGTS")" AIMYTH_HANDSOFF_RUN=run-hg-newer 2>"$E")
check "HG-3's intact control (RV-CAP4 F1): the same newer run-resume whole, so the previous lead's TaskStop is denied, the record's current head session named" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c "TaskStop passes at the hard band only for the run's last lead, and this lead is not (successors: 3 of 3 started, none left; this session ($HGL) is not the run's current lead: the record's current head session is $HGR)")" "deny:1"
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" Bash "$HGCL")" AIMYTH_HANDSOFF_RUN=run-hg-newer 2>"$E")
check "…and its handsoff.py close denied the same way" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c "handsoff.py close passes at the hard band only for the run's last lead, and this lead is not (successors: 3 of 3 started, none left; this session ($HGL) is not the run's current lead: the record's current head session is $HGR)")" "deny:1"
OUT=$(hg "$(ptu "$HGR" "$T91" "$F/vault" TaskStop "$HGTS")" AIMYTH_HANDSOFF_RUN=run-hg-newer 2>"$E"); RC=$?
check "…the newer lead there, the record's current head at 3 of 3: its TaskStop allowed by silence, exit 0" "$RC:$(dec "$OUT")" "0:(silent)"
OUT=$(hg "$(ptu "$HGR" "$T91" "$F/vault" Bash "$HGCL")" AIMYTH_HANDSOFF_RUN=run-hg-newer 2>"$E"); RC=$?
check "…and its handsoff.py close allowed too" "$RC:$(dec "$OUT")" "0:(silent)"
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" TaskStop "$HGTS")" 2>"$E"); RC=$?
check "HG-4 no environment run, the pointer naming run-hg-last for the current lead: TaskStop allowed" "$RC:$(dec "$OUT")" "0:(silent)"
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" TaskStop "$HGTS")" AIMYTH_HANDSOFF_RUN=run-hg-keyless 2>"$E"); RC=$?
check "HG-7 (build review RV-CAP finding F5) a readable grants file with no cap key, 20 of the default 20 used: a decided cap, so the current lead's TaskStop is allowed" "$RC:$(dec "$OUT")" "0:(silent)"
check "…its stderr note names the default and the keyless file as the cap's source" "$(grep -c "TaskStop allowed for the run's last lead (successors: 20 of 20 started, none left (the default (the grants file: readable, no max_successors key; no AIMYTH_MAX_SUCCESSORS))" "$E")" "1"
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" Bash "$HGCL")" AIMYTH_HANDSOFF_RUN=run-hg-keyless 2>"$E"); RC=$?
check "…and its handsoff.py close is allowed too" "$RC:$(dec "$OUT")" "0:(silent)"
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" TaskStop "$HGTS")" AIMYTH_HANDSOFF_RUN=run-hg-badval 2>"$E")
check "HG-8 (RV-CAP F5) an unusable max_successors value at 20 of the fallback 20: undecided, so TaskStop is denied, the fault named" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c "could not be read (successors: 20 of 20 started, none left on a fallback cap.*the grants file is readable, unusable max_successors value 'six')")" "deny:1"
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" Bash "$HGCL")" AIMYTH_HANDSOFF_RUN=run-hg-bad20 2>"$E")
check "…an unreadable grants file at 20 of 20: handsoff.py close denied, undecided, the fault named" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c 'could not be read (successors: 20 of 20 started, none left on a fallback cap.*the grants file is unreadable (')" "deny:1"
OUT=$(hg "$(ptu "$HGL" "$T91" "$F/vault" Read "$RD")" AIMYTH_HANDSOFF_RUN=run-hg-last 2>"$E")
check "HG-5 the last lead at 91 %: a Read is still denied, the static last-lead sentence in its reason" "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c -F "$LASTLEAD")" "deny:1"
check "…and leg o's pattern still matches that reason" "$(dec "$OUT" | grep -c 'hands-off hard band: context 182,000 tokens (91 % of 200k), at or above the 90 % edge.*handsoff.py handoff, handsoff.py successor, handsoff.py boundary, handsoff.py ledger')" "1"
OUT=$(hg "$(ptu "$HGX" "$T85" "$F/vault" TaskStop "$HGTS")" AIMYTH_HANDSOFF_RUN=run-hg-more 2>"$E")
check "HG-5 at 85 %: TaskStop is silent with nothing on stderr (nothing imported)" "$(dec "$OUT"):$(wc -c < "$E" | tr -d ' ')" "(silent):0"
for c in handoff successor boundary ledger; do
  OUT=$(hg "$(ptu "$HGX" "$T91" "$F/vault" Bash '{"command":"python3 handsoff.py '"$c"' --run r"}')" AIMYTH_HANDSOFF_RUN=run-hg-more 2>"$E")
  check "HG-5 at 91 %: handsoff.py $c still silent with nothing on stderr" "$(dec "$OUT"):$(wc -c < "$E" | tr -d ' ')" "(silent):0"
done
manifest "$HGSTORE" > "$F/hg-store.after"
manifest "$GS" | grep -v '/events.log$' > "$F/hg-state.after"
ls -la "$HGDEL" "$HGDEL/__pycache__" 2>&1 | grep -v '^total ' | awk '{print $1, $5, $NF}' > "$F/hg-del.after"
check "HG-6 the store (records, grants files) is byte-identical after the section" "$(cmp -s "$F/hg-store.before" "$F/hg-store.after" && echo same || echo differ)" "same"
check "…the state directory too, events.log's appends aside" "$(cmp -s "$F/hg-state.before" "$F/hg-state.after" && echo same || echo differ)" "same"
check "…the delegate folder's listing, its __pycache__ included, is unchanged (no bytecode from the import)" "$(cmp -s "$F/hg-del.before" "$F/hg-del.after" && echo same || echo differ)" "same"
check "…and no __pycache__ appeared beside the hook copy" "$(find "$F/hookcopy" -name '__pycache__' | wc -l | tr -d ' ')" "$(cat "$F/hg-hookcopy.before")"
check "…positive control: the store manifest sees a planted change" "$(printf 'x\n' >> "$HGSTORE/spawn-records/run-hg-more.jsonl"; manifest "$HGSTORE" | cmp -s "$F/hg-store.before" - && echo same || echo differ)" "differ"

echo "== p. head-fence: unarmed silence, the grant file, the run pointer, N7's deny and its exemption =="
HF="$HOOKS/head-fence.py"
HFS="$F/state/head"                  # the head fence's state dir: markers, run pointers, events.log
HFSTORE="$F/hf-store"                # LLM_WIKI_STORE: <store>/spawn-records/<run>-grants.json
HFV="$F/hf-vault"                    # CLAUDE_PROJECT_DIR: the vault whose delegate skill holds the checker
mkdir -p "$HFS" "$HFSTORE/spawn-records" "$HFV/.claude/skills/delegate" "$F/hf/granted" \
         "$F/hf/writable" "$F/hf-novault" "$F/hfalone" "$F/hflayout/.claude/hooks" \
         "$F/hflayout/.claude/skills/delegate"
# The checker is the single source: beside lane.py when installed, beside this suite when a builder
# runs a staged copy. Neither present is a broken premise, not a clean run.
FENCESRC="$HOOKS/../skills/delegate/lane-fence.py"; [ -f "$FENCESRC" ] || FENCESRC="$HOOKS/lane-fence.py"
[ -f "$FENCESRC" ] || { echo "PROBE FAILED: no lane-fence.py beside the hooks or in the delegate skill"; exit 2; }
cp "$FENCESRC" "$HFV/.claude/skills/delegate/lane-fence.py"
cp "$FENCESRC" "$F/hflayout/.claude/skills/delegate/lane-fence.py"
cp "$HF" "$F/hfalone/head-fence.py"; cp "$HF" "$F/hflayout/.claude/hooks/head-fence.py"
HRUN=run-hf-1; HRUN2=run-hf-2; HRUNX=run-hf-missing; HRUNC=run-hf-corrupt; HRUNE=run-hf-empty
"$PY" -B -c 'import json, sys; json.dump({"grants": [sys.argv[2], "/etc"], "writes": [sys.argv[3]]}, open(sys.argv[1], "w"))' \
      "$HFSTORE/spawn-records/$HRUN-grants.json" "$F/hf/granted" "$F/hf/writable"
"$PY" -B -c 'import json, sys; json.dump({"grants": [sys.argv[2]], "writes": [sys.argv[3]]}, open(sys.argv[1], "w"))' \
      "$HFSTORE/spawn-records/$HRUN2-grants.json" "$F/hf/granted" "$F/hf/writable"
printf 'not json at all\n' > "$HFSTORE/spawn-records/$HRUNC-grants.json"
printf '{}\n' > "$HFSTORE/spawn-records/$HRUNE-grants.json"
HRUNNET=run-hf-net                           # a grants file carrying the new optional `network` key
"$PY" -B -c 'import json, sys; json.dump({"grants": [sys.argv[2]], "writes": [sys.argv[3]], "network": ["api.openalex.org"]}, open(sys.argv[1], "w"))' \
      "$HFSTORE/spawn-records/$HRUNNET-grants.json" "$F/hf/granted" "$F/hf/writable"
printf '%s\n' "$HRUN2" > "$HFS/run-$SB"      # the pointer run-open writes; B-P1 builds that half
# AIMYTH_HANDSOFF and AIMYTH_HANDSOFF_RUN are emptied FIRST so an ambient arming or run cannot
# reach the unarmed legs; a caller's later assignment wins, as the gate helper's does.
hf(){ j="$1"; shift; printf '%s' "$j" | env AIMYTH_HANDSOFF= AIMYTH_HANDSOFF_RUN= \
      AIMYTH_STATE_DIR="$HFS" LLM_WIKI_STORE="$HFSTORE" CLAUDE_PROJECT_DIR="$HFV" \
      ${1+"$@"} "$PY" -B "$HF"; }
HE="$F/state/hf-err.txt"
CIN=$(printf '{"command":"cat /etc/hosts"}')
COUT=$(printf '{"command":"echo x > /etc/hosts"}')
CGIT='{"command":"git status --short"}'
CCLAUDE='{"command":"claude -p do-the-thing"}'
CPLAIN='{"command":"ls -la"}'
CHO='{"command":"python3 handsoff.py grants --run r --write g"}'

OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$CIN")" 2>"$HE"); RC=$?
check "unarmed: no stdout, no stderr, exit 0" "$RC:$(dec "$OUT"):$(wc -c < "$HE" | tr -d ' ')" "0:(silent):0"
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$CIN")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN 2>"$HE"); RC=$?
check "armed, a read the grant file allows: cleared by SILENCE, never an explicit allow" \
      "$RC:$(dec "$OUT"):$(wc -c < "$HE" | tr -d ' ')" "0:(silent):0"
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$CIN")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN2 2>"$HE")
check "…the same read under a run whose grant file omits that root is denied (the file is what decides)" \
      "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c 'outside the granted directories')" "deny:1"
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$COUT")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN 2>"$HE")
check "armed: a write outside W is denied with the fence's own reason" \
      "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c 'lane-fence: shell redirection outside the write whitelist')" "deny:1"
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$CGIT")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN 2>"$HE")
check "armed: git passes silently (it is not a mutator token and needs no rule of its own)" "$(dec "$OUT")" "(silent)"
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$CCLAUDE")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN 2>"$HE")
check "armed: a head may invoke claude (the no-nested-spawn check is off in the head role)" "$(dec "$OUT")" "(silent)"
: > "$HFS/armed-$SB"
OUT=$(hf "$(ptu "$SB" "$T50" "$F/vault" Bash "$CIN")" 2>"$HE")
check "the marker file arms the session, and the run comes from the pointer file (no env)" \
      "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c 'outside the granted directories')" "deny:1"
OUT=$(hf "$(ptu "$SC" "$T50" "$F/vault" Bash "$COUT")" 2>"$HE")
check "negative control: a session with neither marker nor variable stays silent" "$(dec "$OUT")" "(silent)"
rm -f "$HFS/armed-$SB"
NEV=$(awk -F'\t' '$3=="head-fence"' "$HFS/events.log" 2>"$F/state/legacy-diagnostics.txt" | wc -l | tr -d ' ')
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$CPLAIN")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUNX 2>"$HE")
check "N7 armed with no grant file: a plain command is DENIED, the reason naming the file and the recovery" \
      "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c 'grant file is unusable.*handsoff.py grants')" "deny:1"
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$CHO")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUNX 2>"$HE")
check "…and a handsoff.py command runs, silently: the recovery is one command away" "$(dec "$OUT")" "(silent)"
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$CPLAIN")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUNC 2>"$HE")
check "N7 a corrupt grant file: the same deny" "$(dec "$OUT" | cut -d'|' -f2)" "deny"
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$CPLAIN")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUNE 2>"$HE")
check "N7 a grant file with no grants entries: the same deny, named" \
      "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c 'carries no .grants. entries')" "deny:1"
OUT=$(hf "$(ptu "$SW" "$T50" "$F/vault" Bash "$CPLAIN")" AIMYTH_HANDSOFF=1 2>"$HE")
check "N7 armed with no run at all: denied, the missing pointer named" \
      "$(dec "$OUT" | cut -d'|' -f2):$(grep -c 'no AIMYTH_HANDSOFF_RUN and no run pointer' "$HE")" "deny:0"
check "…every deny and every exemption is one events.log line (4 denies + 1 exemption this block)" \
      "$(( $(awk -F'\t' '$3=="head-fence"' "$HFS/events.log" | wc -l | tr -d ' ') - NEV ))" "5"
check "…each carries six tab fields, session and action (the sixth is the whole command)" \
      "$(tail -1 "$HFS/events.log" | awk -F'\t' '{print NF"|"$2"|"$3"|"$4}')" "6|$SW|head-fence|deny-no-grants"
check "…the deny-no-grants line's sixth field is the command as a JSON string" \
      "$(tail -1 "$HFS/events.log" | awk -F'\t' '{print $5"|"$6}')" 'ls -la|"ls -la"'
OUT=$(printf '%s' "$(ptu "$SA" "$T50" "$F/vault" Bash "$CPLAIN")" | env AIMYTH_HANDSOFF=1 \
      AIMYTH_HANDSOFF_RUN=$HRUN AIMYTH_STATE_DIR="$HFS" LLM_WIKI_STORE="$HFSTORE" \
      CLAUDE_PROJECT_DIR="$F/hf-novault" "$PY" -B "$F/hfalone/head-fence.py" 2>"$HE"); RC=$?
check "the checker missing under both roots: ALLOW, exit 0, named on stderr" \
      "$RC:$(dec "$OUT"):$(grep -c 'no lane-fence.py under CLAUDE_PROJECT_DIR' "$HE")" "0:(silent):1"
OUT=$(printf '%s' "$(ptu "$SA" "$T50" "$F/vault" Bash "$CIN")" | env AIMYTH_HANDSOFF=1 \
      AIMYTH_HANDSOFF_RUN=$HRUN2 AIMYTH_STATE_DIR="$HFS" LLM_WIKI_STORE="$HFSTORE" \
      CLAUDE_PROJECT_DIR= "$PY" -B "$F/hflayout/.claude/hooks/head-fence.py" 2>"$HE")
check "with no CLAUDE_PROJECT_DIR the checker is found from the hook's own location" \
      "$(dec "$OUT" | cut -d'|' -f2)" "deny"
for s in 'not json' '[]' ''; do
  OUT=$(hf "$s" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN 2>"$HE"); RC=$?
  check "payload '$s': allowed, exit 0, premise failure on stderr" \
        "$RC:$(dec "$OUT"):$(grep -c 'premise failure: unreadable payload' "$HE")" "0:(silent):1"
done
OUT=$(hf '{"session_id":"s","hook_event_name":"Stop","tool_name":"Bash"}' AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN 2>"$HE"); RC=$?
check "a foreign event (mis-registration): silent, noted on stderr, exit 0" \
      "$RC:$(dec "$OUT"):$(grep -c 'ignoring event Stop' "$HE")" "0:(silent):1"
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash '{}')" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN 2>"$HE")
check "a Bash event carrying no command is denied, fail-closed (the checker's own premise rule)" \
      "$(dec "$OUT" | cut -d'|' -f2)" "deny"
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Read '{"file_path":"/etc/hosts"}')" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN 2>"$HE")
check "a non-Bash tool is not this hook's channel: silent" "$(dec "$OUT")" "(silent)"
check "N8: the hook imports the checker, it does not spawn it (no subprocess in its source)" \
      "$(grep -c 'subprocess' "$HF"):$([ "$(grep -c 'importlib' "$HF")" -gt 0 ] && echo imports || echo none)" "0:imports"

echo "== p2. head-fence logs the whole command (register 2026-09-14): a denied 200-character command holding a tab, a newline and a U+2028 is field six, one ASCII line, decoded back exactly =="
# The tab and the newline fall inside the 80-character head (field five, escaped as before); the
# U+2028 lies beyond it, so only field six can carry it. The payload is ASCII JSON, as the harness sends.
"$PY" -B - "$F/state/p2-command.json" <<'P2MAKE'
import json, sys
cmd = "echo " + "a" * 25 + "\t" + "b" * 28 + "\n" + "echo " + "c" * 50 + " "
tail = " > /etc/hosts"
cmd += "d" * (200 - len(cmd) - len(tail)) + tail
with open(sys.argv[1], "w", encoding="ascii") as fh:
    json.dump({"command": cmd}, fh)
P2MAKE
probe "p2 fixture: a 200-character command with one tab, one newline and one U+2028" \
      "$("$PY" -B -c 'import json, sys; c = json.load(open(sys.argv[1]))["command"]; print("%d|%d|%d|%d" % (len(c), c.count("\t"), c.count("\n"), c.count(" ")))' "$F/state/p2-command.json")" "200|1|1|1"
NEV=$(awk -F'\t' '$3=="head-fence"' "$HFS/events.log" | wc -l | tr -d ' ')
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$(cat "$F/state/p2-command.json")")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN 2>"$HE"); RC=$?
check "p2: the long command is denied (a write outside W), exit 0" \
      "$RC:$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c 'shell redirection outside the write whitelist')" "0:deny:1"
check "p2: …one more head-fence line, and it carries six tab fields" \
      "$(( $(awk -F'\t' '$3=="head-fence"' "$HFS/events.log" | wc -l | tr -d ' ') - NEV )):$(tail -1 "$HFS/events.log" | awk -F'\t' '{print NF"|"$4}')" "1:6|deny"
P2=$("$PY" -B - "$HFS/events.log" "$F/state/p2-command.json" <<'P2READ'
import json, sys
raw = open(sys.argv[1], "rb").read().decode("utf-8")
cmd = json.load(open(sys.argv[2]))["command"]
line = [ln for ln in raw.split("\n") if ln][-1]
cols = line.split("\t")
head = cmd[:80].replace("\t", " ").replace("\n", " ")
out = [str(len(cols)),
       "head-as-before" if len(cols) > 4 and cols[4] == head else "head-differs",
       "whole" if len(cols) > 5 and json.loads(cols[5]) == cmd else "not-whole",
       "ascii" if len(cols) > 5 and cols[5].isascii() else "not-ascii",
       "one-line" if len(raw.splitlines()) == len(raw.rstrip("\n").split("\n")) else "torn"]
print("|".join(out))
P2READ
)
check "p2: field five is the 80-character head escaped as before; field six decodes to the whole command; ASCII only; every line still one line to a splitlines() reader" \
      "$P2" "6|head-as-before|whole|ascii|one-line"

echo "== p3. head-fence field five: a carriage return, a U+2028 and every other character splitlines() ends a line at, inside the first 80 characters, leave one line; a lone surrogate leaves its line (review CR-B7 fold, head items 5 and 6) =="
# The characters are made with chr() in the fixture, never typed. The payload is ASCII JSON; the hook
# decodes the same string from it as from the harness's form.
"$PY" -B - "$F/state/p3-command.json" "$F/state/p4-command.json" <<'P3MAKE'
import json, sys
breaks = "\r" + chr(0x2028) + "\x0b\x0c\x1c\x1d\x1e\x85" + chr(0x2029)   # each one ends a line for splitlines()
p3 = "echo a" + "".join(c + "b" for c in breaks) + " > /etc/hosts"
p4 = "echo s" + chr(0xD800) + "t > /etc/hosts"                        # a lone surrogate, as a JSON escape can carry
for path, cmd in ((sys.argv[1], p3), (sys.argv[2], p4)):
    with open(path, "w", encoding="ascii") as fh:
        json.dump({"command": cmd}, fh)
P3MAKE
probe "p3 fixture: nine line-ending characters inside the first 80; p4 fixture: one lone surrogate" \
      "$("$PY" -B -c 'import json, sys
c3 = json.load(open(sys.argv[1]))["command"]; c4 = json.load(open(sys.argv[2]))["command"]
print("%d|%d|%d" % (len(c3[:80].splitlines()), len(c3) <= 80, sum(1 for ch in c4 if 0xD800 <= ord(ch) <= 0xDFFF)))' "$F/state/p3-command.json" "$F/state/p4-command.json")" "10|1|1"
# fenceline <events.log> <command json> <splitlines() count before>: one summary of the newest line
fenceline(){ "$PY" -B - "$1" "$2" "$3" <<'P3READ'
import json, sys
raw = open(sys.argv[1], "rb").read().decode("utf-8")       # strict: a torn or undecodable log fails here
cmd = json.load(open(sys.argv[2]))["command"]
flat = cmd[:80]
for ch in "\t\n\r\x0b\x0c\x1c\x1d\x1e\x85" + chr(0x2028) + chr(0x2029):
    flat = flat.replace(ch, " ")
flat = flat.encode("utf-8", "backslashreplace").decode("utf-8")
cols = raw.splitlines()[-1].split("\t")
print("|".join([str(len(raw.splitlines()) - int(sys.argv[3])), str(len(cols)), cols[3] if len(cols) > 3 else "?",
                "head-flat" if len(cols) > 4 and cols[4] == flat else "head-differs",
                "whole" if len(cols) > 5 and json.loads(cols[5]) == cmd else "not-whole"]))
P3READ
}
slcount(){ "$PY" -B -c 'import sys; print(len(open(sys.argv[1], "rb").read().decode("utf-8", "replace").splitlines()))' "$1"; }
NSL=$(slcount "$HFS/events.log")
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$(cat "$F/state/p3-command.json")")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN 2>"$HE"); RC=$?
check "p3: the command is denied (a write outside W), exit 0" "$RC:$(dec "$OUT" | cut -d'|' -f2)" "0:deny"
check "p3: exactly one more line to a splitlines() reader, six fields, field five the head with each line-ending character made a space, field six the exact command" \
      "$(fenceline "$HFS/events.log" "$F/state/p3-command.json" "$NSL")" "1|6|deny|head-flat|whole"
NSL=$(slcount "$HFS/events.log")
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$(cat "$F/state/p4-command.json")")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN 2>"$HE"); RC=$?
check "p4: a command holding a lone surrogate is denied, exit 0, nothing on stderr" "$RC:$(dec "$OUT" | cut -d'|' -f2):$(wc -c < "$HE" | tr -d ' ')" "0:deny:0"
check "p4: …and leaves one line: six fields, the surrogate a backslash escape in field five, field six the exact command" \
      "$(fenceline "$HFS/events.log" "$F/state/p4-command.json" "$NSL")" "1|6|deny|head-flat|whole"

echo "== q. head-fence fixes: grant-change exemption + event (register fix 3), the network grant (fix 7) =="
# CR-F F1: the exemption keys on the vault's OWN primitive standing FIRST — a handsoff.py under a
# `.claude/skills/` directory that is not itself under a temporary root, since a copy under /tmp is
# one of the bypasses the fold refuses. $F is an allocated temporary root, so this one
# fixture vault is made under $TMPDIR instead and removed at the end of the block.
QV=$(mktemp -d); mkdir -p "$QV/.claude/skills/delegate"
QHO="$QV/.claude/skills/delegate/handsoff.py"
CGC=$(printf '{"command":"python3 -B %s grants --grant /some/new/path"}' "$QHO")
CGCBAD=$(printf '{"command":"python3 -B %s grants --grant /x; rm -rf /y"}' "$QHO")
# /etc is explicitly granted above, and QHO can be under the implicitly readable cwd.
# An ungranted operand makes this bypass control independent of the chosen temporary root.
CGCWORDS=$(printf '{"command":"cat /context-hooks-ungranted %s grants"}' "$QHO")
CGCTMP='{"command":"python3 /tmp/x/handsoff.py grants"}'
CCURL='{"command":"curl https://api.openalex.org/x"}'
CEVIL='{"command":"curl https://evil.example.com/x"}'
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$CGC")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN 2>"$HE")
check "fix 3: a lone \`handsoff.py grants --grant <new path>\` clears silently, exempt as the recovery" \
      "$(dec "$OUT")" "(silent)"
check "fix 3: …and the self-grant is logged as exactly one \`grant-change\` events.log line" \
      "$(awk -F'\t' '$3=="head-fence" && $4=="grant-change"' "$HFS/events.log" | wc -l | tr -d ' ')" "1"
check "fix 3: …whose sixth field is the whole command as a JSON string (register 2026-09-14)" \
      "$(awk -F'\t' '$3=="head-fence" && $4=="grant-change" {print NF"|"$6}' "$HFS/events.log")" \
      "6|\"python3 -B $QHO grants --grant /some/new/path\""
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$CGCBAD")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN 2>"$HE")
check "fix 3: \`grants\` with a shell mutator appended is two segments, NOT exempt, and denies" \
      "$(dec "$OUT" | cut -d'|' -f2)" "deny"
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$CCURL")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUNNET 2>"$HE")
check "fix 7: curl clears under a grants file whose \`network\` key names the host" "$(dec "$OUT")" "(silent)"
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$CCURL")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN 2>"$HE")
check "fix 7: the same curl denies under a grants file with no \`network\` key" \
      "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c 'no .network. list')" "deny:1"
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$CEVIL")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUNNET 2>"$HE")
check "fix 7: a host the \`network\` key does not name denies (control for the clear above)" \
      "$(dec "$OUT" | cut -d'|' -f2):$(dec "$OUT" | grep -c 'not named in the run')" "deny:1"
# CR-F F1: the two bypasses that mattered most — words appended to another command, and a copy of
# the primitive under a temporary root. Neither may earn the exemption; both are checked as normal.
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$CGCWORDS")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN 2>"$HE")
check "F1: \`handsoff.py grants\` appended to another command earns no exemption and denies" \
      "$(dec "$OUT" | cut -d'|' -f2)" "deny"
OUT=$(hf "$(ptu "$SA" "$T50" "$F/vault" Bash "$CGCTMP")" AIMYTH_HANDSOFF=1 AIMYTH_HANDSOFF_RUN=$HRUN 2>"$HE")
check "F1: a copy of the primitive under /tmp earns no exemption (no grant-change line for it)" \
      "$(awk -F'\t' '$3=="head-fence" && $4=="grant-change"' "$HFS/events.log" | wc -l | tr -d ' ')" "1"
rm -rf "$QV"


echo "== r. attended fit, close reserve and belt; no band or percentage label on the attended path, prompt line and checkpoint header (r12); shared API and hands-off regressions =="
# Python keeps the related prompt sequence and exact-text assertions together. All writes are
# fixture preparation under this invocation's mktemp directory; hooks retain their declared logs.
"$PY" -B - "$HOOKS" "$F" <<'PYATTENDED'
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

hooks, fixtures = map(Path, sys.argv[1:])
root = fixtures / "attended"
readonly = root / "readonly"
state = root / "state"
readonly.mkdir(parents=True)
state.mkdir()
passed = failed = 0

def check(name, actual, expected):
    global passed, failed
    if actual == expected:
        passed += 1
        print("  ok   — " + name)
    else:
        failed += 1
        print("  FAIL — %s (want %r, got %r)" % (name, expected, actual))

def usage(context):
    return json.dumps({"message": {"role": "assistant", "usage": {
        "input_tokens": context // 2,
        "cache_read_input_tokens": context - context // 2}}}) + "\n"

def manifest(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob("*") if p.is_file()}

base = os.environ.copy()
for key in ("AIMYTH_HANDSOFF", "AIMYTH_BANDS", "AIMYTH_CONTEXT_WINDOW"):
    base.pop(key, None)
base.update(AIMYTH_PROJECTS_DIR=str(root), AIMYTH_STATE_DIR=str(state),
            AIMYTH_WATERMARK_LOG=str(state / "watermark.log"),
            HOME=str(root / "home"), PYTHONDONTWRITEBYTECODE="1")

for name in ("context-watermark.py", "handsoff-gate.py", "precompact-checkpoint.py"):
    shutil.copyfile(hooks / name, readonly / name)
# Boundaries and their neighbouring token counts expose flooring errors at 90 and 95 %.
counts = (599999, 600000, 790000, 799999, 800000, 890000, 899999, 900000,
          900001, 910000, 925000, 940000, 949999, 950000, 951000,
          178000, 180000, 182000,
          # r12: about 30, 65 and 85 % of 1M; 30 and 65 % of a 200k window
          300000, 650000, 850000, 60000, 130000)
for context in counts:
    (readonly / (str(context) + ".jsonl")).write_text(usage(context))
(readonly / "unmetered.jsonl").write_text('{"message":{"role":"user"}}\n')
for p in readonly.iterdir():
    p.chmod(0o444)
readonly.chmod(0o555)
before = manifest(readonly)

def call(name, context=None, overrides=None, sid="attended-test", tool="Read", ti=None, path=None):
    env = dict(base)
    for key, value in (overrides or {}).items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    event_name = "UserPromptSubmit" if name == "context-watermark.py" else "PreToolUse"
    event = {"hook_event_name": event_name, "session_id": sid,
             "transcript_path": str(path or readonly / (str(context) + ".jsonl")),
             "tool_name": tool, "tool_input": ti if ti is not None else {"limit": 200}}
    run = subprocess.run([sys.executable, "-B", str(readonly / name)],
                         input=json.dumps(event), text=True, capture_output=True, env=env)
    if run.returncode:
        raise RuntimeError("%s exited %d: %s" % (name, run.returncode, run.stderr))
    output = json.loads(run.stdout)["hookSpecificOutput"] if run.stdout else {}
    return output, run.stderr

def watermark(context, overrides=None, sid="attended-test", path=None):
    output, error = call("context-watermark.py", context, overrides, sid, path=path)
    if "additionalContext" not in output:
        raise RuntimeError("watermark gave no line: " + error)
    return output["additionalContext"].rsplit(" · ", 1)[-1], error

def gate(context=None, overrides=None, sid="attended-test", path=None, ti=None):
    output, error = call("handsoff-gate.py", context, overrides, sid, path=path, ti=ti)
    return output.get("permissionDecision", "silent"), error

legacy = ("ok", "write the hand-off document at the next item boundary",
          "hand-off band: finish what is in flight and open a new item only where the "
          "hands-off gate's fit check allows it (an attended session starts nothing new)",
          "hard band: write the hand-off now and end the session")
full = ("full close-out now: 50,000 tokens remain under the 950,000-token belt; run the "
        "cross-reflection with --yes and record accepted items first, then run the "
        "follow-up check over owner turns after the reflection's copy, then update the "
        "calendar only if a dated item was made or changed, then write the hand-off "
        "and give the next prompt last; stay under the belt")
stop = ("950,000-token belt reached: update the hand-off document and, if the close is pending, "
        "its calendar line; then stop")

def fit(context):
    # The attended 1M path below 900k, at every reading (owner decision of 9 October 2026).
    return ("fit: new work only if %s now + its estimate + 50,000 close-out < 950,000 tokens; "
            "state the sum first; no estimate, nothing new; start the close-out by 900,000 tokens"
            % format(context, ","))

def short(remaining):
    return ("close now: %s tokens remain under the 950,000-token belt, less than the 50,000 "
            "close-out reserve; if the head's share of the close fits, close here in full; if "
            "not, short close: write the hand-off, the next prompt and a calendar line dated "
            "today naming the pending close; the next session runs the cross-reflection over "
            "the saved transcript and the calendar first, then checks its prompt against both "
            "before any work; the rest of the close it runs follows CUSTOMISATION.md's "
            "closing order, follow-up check included" % format(remaining, ","))

try:
    source = (readonly / "context-watermark.py").read_text()
    check("r01 CONTROL+: DEFAULT_BANDS remains (60, 80, 90)",
          len(re.findall(r"^DEFAULT_BANDS = \(60, 80, 90\)", source, re.M)), 1)
    # Below 800k these four once asserted the legacy ok and first-band texts; the attended
    # path now carries the fit sum across the old 60 and 80 % edges alike.
    for context, expected in ((599999, fit(599999)), (600000, fit(600000)),
                              (790000, fit(790000)), (799999, fit(799999)),
                              (800000, fit(800000)), (890000, fit(890000)),
                              (899999, fit(899999)), (900000, full),
                              (900001, short(49999)), (925000, short(25000)),
                              (940000, short(10000)), (949999, short(1)),
                              (950000, stop), (951000, stop)):
        check("r02 attended %s tokens: exact text" % format(context, ","),
              watermark(context), (expected, ""))
    for setting, expected in (("60,80", legacy[2]), ("60,80,90", legacy[3]),
                              ("60,80,95", legacy[2]), ("", legacy[3])):
        check("r03 explicit AIMYTH_BANDS=%r keeps legacy text" % setting,
              watermark(910000, {"AIMYTH_BANDS": setting}), (expected, ""))
    line, error = watermark(910000, {"AIMYTH_BANDS": "bad"})
    check("r03 invalid override retains legacy fallback and diagnostic",
          (line, "invalid; using 60,80,90" in error), (legacy[3], True))
    for context, expected in ((178000, legacy[2]), (180000, legacy[3]), (182000, legacy[3])):
        check("r04 non-1M attended at %d %% keeps legacy text" % (context * 100 // 200000),
              watermark(context, {"AIMYTH_CONTEXT_WINDOW": "200000"}), (expected, ""))
    for context, expected in ((890000, legacy[2]), (900000, legacy[3]), (910000, legacy[3])):
        check("r05 armed watermark at %d %% keeps legacy text" % (context // 10000),
              watermark(context, {"AIMYTH_HANDSOFF": "1"}), (expected, ""))
    marker = state / "armed-marker-test"
    marker.touch()
    check("r06 marker-only watermark at 91 % keeps the hands-off hard text",
          watermark(910000, sid="marker-test"), (legacy[3], ""))
    check("r06 a different session's marker does not arm the attended prompt",
          watermark(910000), (short(40000), ""))
    marker.unlink()
    check("r06 removing the marker restores attended text on the next prompt",
          watermark(910000, sid="marker-test"), (short(40000), ""))
    default_state = root / "home" / ".aimyth" / "handoffs"
    default_state.mkdir(parents=True)
    (default_state / "armed-marker-test").touch()
    check("r06 default marker directory agrees with the gate",
          (watermark(910000, {"AIMYTH_STATE_DIR": None}, "marker-test")[0],
           gate(910000, {"AIMYTH_STATE_DIR": None}, "marker-test")[0]),
          (legacy[3], "deny"))
    # Without token validation, prefixing this id looks up state/armed-../marker-test.
    # Plant that adverse marker so removing validation changes the advice to hands-off.
    invalid_marker = state / "armed-.." / "marker-test"
    invalid_marker.parent.mkdir()
    invalid_marker.touch()
    if not invalid_marker.is_file():
        raise RuntimeError("adverse invalid-token marker is missing")
    check("r06 invalid marker token cannot name a file outside the marker directory",
          watermark(910000, sid="../marker-test"), (short(40000), ""))
    check("r06 HANDSOFF=0 is attended",
          watermark(890000, {"AIMYTH_HANDSOFF": "0"}), (fit(890000), ""))
    for size, readings in ((1000000, (890000, 900000, 910000)),
                           (200000, (178000, 180000, 182000))):
        for settings, expected in (({}, ("silent", "deny", "deny")),
                                   ({"AIMYTH_BANDS": "60,80"}, ("silent",) * 3),
                                   ({"AIMYTH_BANDS": "60,80,95"}, ("silent",) * 3)):
            env = dict(settings, AIMYTH_HANDSOFF="1", AIMYTH_CONTEXT_WINDOW=str(size))
            for context, decision in zip(readings, expected):
                check("r07 gate %s window, %s bands, %d %%: unchanged" %
                      (size, settings.get("AIMYTH_BANDS", "default"), context * 100 // size),
                      gate(context, env)[0], decision)
    check("r07 three-edge override still denies at its own 95 % edge",
          gate(950000, {"AIMYTH_HANDSOFF": "1", "AIMYTH_BANDS": "60,80,95"})[0], "deny")
    decision, error = gate(910000, {"AIMYTH_HANDSOFF": "1", "AIMYTH_BANDS": "60,80"}, ti={})
    check("r07 two-edge override keeps the unbounded-read denial and diagnostic",
          (decision, "carry no third edge" in error), ("deny", True))
    marker.touch()
    for context, decision in ((890000, "silent"), (900000, "deny"), (910000, "deny")):
        check("r08 marker-only gate at %d %%: unchanged" % (context // 10000),
              gate(context, sid="marker-test")[0], decision)
    for env, sid in (({"AIMYTH_HANDSOFF": "1"}, "attended-test"), ({}, "marker-test")):
        decision, error = gate(overrides=env, sid=sid, path=readonly / "unmetered.jsonl")
        check("r08 unmetered armed gate (%s) still allows with its premise diagnostic" % sid,
              (decision, "premise failure: no qualifying usage record" in error), ("silent", True))
    check("r08 unmetered attended prompt remains explicit",
          watermark(None, path=readonly / "unmetered.jsonl"),
          ("context: unmetered (no qualifying usage record in the tail)", ""))
    # Estimated 9k fits: 890k + 9k + 50k = 949k < 950k. Actual 10k reaches the close line.
    growing = root / "underestimated.jsonl"
    growing.write_text(usage(890000))
    check("r09 underestimated item: initial prompt asks for the fit sum",
          watermark(None, path=growing), (fit(890000), ""))
    with growing.open("a") as stream:
        stream.write(usage(900000))
    check("r09 underestimated item: next prompt starts the full close at 900k",
          watermark(None, path=growing), (full, ""))
    with growing.open("a") as stream:
        stream.write(usage(925000))
    check("r09 synthetic jump to 925k: next prompt shortens the close",
          watermark(None, path=growing), (short(25000), ""))
    with growing.open("a") as stream:
        stream.write(usage(951000))
    check("r09 synthetic jump to 951k: next prompt updates only the hand-off",
          watermark(None, path=growing), (stop, ""))
    spec = importlib.util.spec_from_file_location("attended_watermark", readonly / "context-watermark.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    check("r10 shared window() and bands() keep their defaults",
          (module.window(), module.bands()), (1000000, (60, 80, 90)))
    for context, expected in ((890000, legacy[2]), (900000, legacy[3]), (910000, legacy[3])):
        # The import runs in the suite process, whose projects root is set for this call only.
        saved_projects = os.environ.get("AIMYTH_PROJECTS_DIR")
        os.environ["AIMYTH_PROJECTS_DIR"] = str(root)
        try:
            measure = module.measure(str(readonly / (str(context) + ".jsonl")))
        finally:
            if saved_projects is None:
                os.environ.pop("AIMYTH_PROJECTS_DIR", None)
            else:
                os.environ["AIMYTH_PROJECTS_DIR"] = saved_projects
        check("r10 imported measure()/render() at %d %% remain legacy" % (context // 10000),
              (measure.get("context"), module.render(measure).rsplit(" · ", 1)[-1]),
              (context, expected))
    # r12: the attended 1M path drops the 60 and 80 % bands and its percentage labels and keeps the
    # fit sum alone (owner decision of 9 October 2026), on the prompt line and in the checkpoint
    # header. Every r12 leg fails on the hooks before that decision and passes after it: each
    # asserts at least one thing that changed. A scope or regression assertion (an unchanged path,
    # an unchanged figure, a positive control) sits beside its changed twin at the same reading.
    def line_of(context, overrides=None, sid="attended-test"):
        output, error = call("context-watermark.py", context, overrides, sid)
        return output.get("additionalContext", ""), error

    check("r12a attended 300,000 (30 %): the fit sum where the old path said ok",
          watermark(300000), (fit(300000), ""))
    line65, error65 = line_of(650000)
    check("r12b attended 650,000 (65 %): the fit sum, and no first-band hand-off text in the line",
          (line65.rsplit(" · ", 1)[-1], legacy[1] in line65, error65), (fit(650000), False, ""))
    line85 = watermark(850000)[0]
    substance = ("850,000 now", "+ 50,000 close-out <", "950,000 tokens", "new work only if",
                 "state the sum", "nothing new", "start the close-out by 900,000 tokens")
    check("r12c attended 850,000 (85 %): the shortened fit text, exactly",
          line85, fit(850000))
    check("r12c2 attended 850,000 (85 %): every figure and duty of the old fit sum kept, its band "
          "and percentage labels dropped",
          ([s for s in substance if s not in line85], [x for x in ("band", "%") if x in line85]),
          ([], []))
    shape = lambda text, context: text.replace(format(context, ","), "N", 1)
    check("r12c3 one fit text at 30, 65 and 85 %, the figure apart",
          {shape(watermark(c)[0], c) for c in (300000, 650000, 850000)},
          {shape(fit(300000), 300000)})
    r12_marker = state / "armed-r12-marker"
    r12_marker.touch()
    try:
        check("r12d 65 %: armed by AIMYTH_HANDSOFF=1 and by marker keep the first-band text; "
              "the attended twin carries the fit sum",
              (watermark(650000, {"AIMYTH_HANDSOFF": "1"})[0],
               watermark(650000, sid="r12-marker")[0], watermark(650000)[0]),
              (legacy[1], legacy[1], fit(650000)))
    finally:
        r12_marker.unlink()
    check("r12e 65 %: explicit AIMYTH_BANDS 60,80,90 and 60,80 keep the first-band text; "
          "the attended twin carries the fit sum",
          (watermark(650000, {"AIMYTH_BANDS": "60,80,90"})[0],
           watermark(650000, {"AIMYTH_BANDS": "60,80"})[0], watermark(650000)[0]),
          (legacy[1], legacy[1], fit(650000)))
    check("r12f 200k window at 30 and 65 %: ok and the first-band text as before; "
          "the attended 1M twin carries the fit sum",
          (watermark(60000, {"AIMYTH_CONTEXT_WINDOW": "200000"})[0],
           watermark(130000, {"AIMYTH_CONTEXT_WINDOW": "200000"})[0], watermark(650000)[0]),
          (legacy[0], legacy[1], fit(650000)))
    # Every 7,919th token below 900k (a prime stride, so no reading sits on a round edge by
    # construction) plus the old edges and the last reading before the close.
    sweep = sorted(set(range(1, 900000, 7919)) | {599999, 600000, 799999, 800000, 899999})
    wrong = [c for c in sweep if module.render_attended(
        {"context": c, "size": 1}, 1000000, (60, 80, 90)).rsplit(" · ", 1)[-1] != fit(c)]
    check("r12g render_attended at %d readings below 900k: the fit sum at every one" % len(sweep),
          wrong[:3], [])
    tree12 = ast.parse(source)
    segment = lambda name: ast.get_source_segment(source, next(
        n for n in tree12.body if isinstance(n, ast.FunctionDef) and n.name == name))
    edge_ref = re.compile(r"\bDEFAULT_BANDS\b|\bbands\(|\bband\(")
    check("r12h source: render_attended reads no band edge (DEFAULT_BANDS, bands(), band()), "
          "and the same pattern finds the edges render() reads (its positive control)",
          (edge_ref.findall(segment("render_attended")), len(edge_ref.findall(segment("render"))) > 0),
          ([], True))
    check("r12i the hook's docstring names no 80 % trigger and still states the fit sum",
          ("from 80 %" in (module.__doc__ or ""), "fit sum" in (module.__doc__ or "")),
          (False, True))
    m65 = {"context": 650000, "size": 1}
    check("r12j 65 %: the shared render() importers call keeps the first-band text; "
          "render_attended carries the fit sum",
          (module.render(m65, 1000000, (60, 80, 90)).rsplit(" · ", 1)[-1],
           module.render_attended(m65, 1000000, (60, 80, 90)).rsplit(" · ", 1)[-1]),
          (legacy[1], fit(650000)))
    line951, error951 = line_of(951000)
    stops = (watermark(950000)[0], line951.rsplit(" · ", 1)[-1])
    check("r12k attended 950,000 and 951,000: the belt stop names the 950,000-token belt with no "
          "percentage label, the readout keeps its measured (95 % of 1M), and the armed twin at "
          "951,000 keeps the hard-band text",
          (stops, [s for s in stops if "%" in s], "(95 % of 1M)" in line951, error951,
           watermark(951000, {"AIMYTH_HANDSOFF": "1"})[0]),
          ((stop, stop), [], True, "", legacy[3]))
    # Every 7,919th token up to the window, plus the close and belt edges and their neighbours.
    readings = sorted(set(range(1, 1000001, 7919))
                      | {899999, 900000, 900001, 949999, 950000, 950001, 1000000})
    labelled = [c for c in readings if "%" in module.render_attended(
        {"context": c, "size": 1}, 1000000, (60, 80, 90)).rsplit(" · ", 1)[-1]]
    check("r12l render_attended at %d readings up to 1,000,000: no percentage label in any advice "
          "text (the readout's own (N %% of 1M) is a measurement and stays)" % len(readings),
          labelled[:3], [])

    def header(context, overrides=None, sid="r12m-attended"):
        """The context line of the checkpoint precompact-checkpoint.py writes for this session."""
        env = dict(base)
        for key, value in (overrides or {}).items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        event = {"hook_event_name": "PreCompact", "session_id": sid,
                 "transcript_path": str(readonly / (str(context) + ".jsonl")),
                 "cwd": str(root / "no-cwd"), "trigger": "manual", "custom_instructions": ""}
        run = subprocess.run([sys.executable, "-B", str(readonly / "precompact-checkpoint.py")],
                             input=json.dumps(event), text=True, capture_output=True, env=env)
        wrote = re.search(r"^\[precompact-checkpoint\] wrote (.+)$", run.stderr, re.M)
        if run.returncode or run.stdout or not wrote:
            raise RuntimeError("no checkpoint for %s: exit %d, %s" % (sid, run.returncode, run.stderr))
        found = [ln for ln in Path(wrote.group(1)).read_text(encoding="utf-8").splitlines()
                 if ln.startswith("- context:")]
        if len(found) != 1:
            raise RuntimeError("checkpoint header for %s has %d context lines" % (sid, len(found)))
        return found[0][2:]

    r12m_marker = state / "armed-r12m-marker"
    r12m_marker.touch()
    try:
        armed = (header(650000, {"AIMYTH_HANDSOFF": "1"}, "r12m-env"),
                 header(650000, sid="r12m-marker"))
    finally:
        r12m_marker.unlink()
    pairs = {c: (header(c), line_of(c, sid="r12m-attended")[0])
             for c in (300000, 650000, 850000, 951000)}
    check("r12m PreCompact header: an attended session's context line is its prompt line at 30, "
          "65, 85 and 95 % (the fit sum at 65 %, no first-band text); armed by AIMYTH_HANDSOFF=1 "
          "and by marker, the header keeps the first-band text",
          ([c for c, (head, prompt) in sorted(pairs.items()) if head != prompt],
           pairs[650000][0].rsplit(" · ", 1)[-1], [a.rsplit(" · ", 1)[-1] for a in armed]),
          ([], fit(650000), [legacy[1], legacy[1]]))
    # r13: the hand-over rule's texts (register entry 2026-11-01 17:49). A hands-off head opens
    # new items as its gate decides, so the second band never tells it to start nothing new; a close
    # stays with its head while the head's share fits, and a handed-over close carries the calendar
    # line (CLAUDE.md section 11); at the belt, a close still pending takes that line too. Each old
    # text is planted beside the probe, as the probe's control.
    old_band = "hand-off band: finish what is in flight, start nothing new"
    old_short = ("short close now: 25,000 tokens remain under the 950,000-token belt, less than the "
                 "50,000 close-out reserve; write the hand-off and the next prompt now; the next "
                 "session runs the cross-reflection over the saved transcript and the calendar "
                 "first, then checks its prompt against both before any work")
    bars_new_work = lambda text: "start nothing new" in text
    r13_marker = state / "armed-r13-marker"
    r13_marker.touch()
    try:
        armed85 = (watermark(850000, {"AIMYTH_HANDSOFF": "1"})[0], watermark(850000, sid="r13-marker")[0])
        armed_head = (header(850000, {"AIMYTH_HANDSOFF": "1"}, "r13-env"),
                      header(850000, sid="r13-marker"))
    finally:
        r13_marker.unlink()
    check("r13a armed at 85 %, by AIMYTH_HANDSOFF=1 and by marker: new items left to the gate's fit "
          "check, and no bar on new work (the probe's control: it hits the old text)",
          ([bars_new_work(t) for t in armed85], ["fit check allows" in t for t in armed85],
           bars_new_work(old_band)), ([False, False], [True, True], True))
    check("r13b the armed checkpoint header at 85 % carries the same text as the armed prompt line",
          [a.rsplit(" · ", 1)[-1] for a in armed_head], [legacy[2], legacy[2]])
    check("r13c an unarmed reader of the same band text is told it starts nothing new: another "
          "window and an explicit band setting; the attended 1M twin shows no band text",
          ("an attended session starts nothing new" in
           watermark(178000, {"AIMYTH_CONTEXT_WINDOW": "200000"})[0],
           "an attended session starts nothing new" in
           watermark(910000, {"AIMYTH_BANDS": "60,80"})[0],
           "fit check" in watermark(850000)[0]), (True, True, False))
    handed_on = lambda text: ("if the head's share of the close fits, close here in full" in text
                              and "a calendar line dated today naming the pending close" in text)
    above = sorted(set(range(900001, 950000, 7919)) | {900001, 949999})
    wrong13 = [c for c in above if not handed_on(module.render_attended(
        {"context": c, "size": 1}, 1000000, (60, 80, 90)).rsplit(" · ", 1)[-1])]
    check("r13d attended at %d readings above 900k and under the belt: the close stays here while "
          "the head's share fits, and a handed-over close writes the calendar line (the probe's "
          "control: it rejects the old text)" % len(above), (wrong13[:3], handed_on(old_short)),
          ([], False))
    clauses = lambda text: ("head's share" in text, "a calendar line dated today" in text)
    check("r13e the full close at exactly 900,000 and the belt stop at 950,000 stay apart from the "
          "short close: neither carries its head-share clause or its dated calendar line (the "
          "probe's control: it hits both in the short close)",
          (clauses(watermark(900000)[0]), clauses(watermark(950000)[0]), clauses(short(25000))),
          ((False, False), (False, False), (True, True)))
    doc13 = module.__doc__ or ""
    check("r13f the docstring states both new texts and neither old one (the probe's control: "
          "the same search finds the old band text in the planted line)",
          ("fit check allows" in doc13, "head's share of the close fits" in doc13,
           "start nothing new" in doc13, "start nothing new" in old_band), (True, True, False, True))
    old_stop = "950,000-token belt reached: update the hand-off document only, then stop"
    takes_line = lambda text: "if the close is pending, its calendar line" in text
    says_only = lambda text: "document only" in text
    at_belt = (watermark(950000)[0], watermark(951000)[0])
    check("r13g at the belt, at 950,000 and 951,000: a close still pending takes its calendar line, "
          "and the text no longer says the hand-off document only (the probe's control: it "
          "tells the old text apart)",
          ([takes_line(t) for t in at_belt], [says_only(t) for t in at_belt],
           takes_line(old_stop), says_only(old_stop)),
          ([True, True], [False, False], False, True))
    flat13 = " ".join(doc13.split())
    old_order = "at the 950,000-token belt update only the hand-off and stop"
    check("r13h the docstring states the belt's calendar line and not the old order (the probe's "
          "control: the same search hits the old order)",
          ("if the close is pending, its calendar line" in flat13,
           "update only the hand-off" in flat13, "update only the hand-off" in old_order),
          (True, False, True))
    # Both the old hard-band output and new advice run from copies that cannot be edited.
    # The existing watermark append is sent to the null device for this no-write invocation.
    check("r11 read-only invocation still emits the attended fit advice",
          watermark(890000, {"AIMYTH_WATERMARK_LOG": os.devnull}), (fit(890000), ""))
    check("r11 read-only checksum manifest unchanged", manifest(readonly), before)
    control = state / "checksum-control"
    control.write_text("before")
    old = manifest(state)
    control.write_text("after")
    check("r11 checksum control catches a planted write", manifest(state) != old, True)
    tree = ast.parse(source)
    added = "\n".join(ast.get_source_segment(source, node) for node in tree.body
                      if isinstance(node, ast.FunctionDef) and node.name in ("attended", "render_attended"))
    writes = re.compile(r"\bopen\([^\n]*[\"'][wax][+b]?[\"']|\.(?:write\w*|mkdir|makedirs|"
                        r"touch|unlink|remove|rename|replace|rmdir|rmtree|move|copy\w*)\s*\(")
    check("r11 source grep: attended selection and rendering have no write patterns",
          len(writes.findall(added)), 0)
    check("r11 source grep positive control catches a write-mode open and a write",
          len(writes.findall('open("x", "w").write("control")')), 2)
    check("r11 source grep control sees the hook's existing declared log writer",
          bool(writes.search(ast.get_source_segment(source, next(node for node in tree.body
               if isinstance(node, ast.FunctionDef) and node.name == "append_log")))), True)
except Exception as error:
    print("PROBE FAILED: attended fixtures or invocation: %s" % error)
    sys.exit(2)
finally:
    readonly.chmod(0o755)
    for p in readonly.iterdir():
        p.chmod(0o644)

(state / "counts").write_text("%d %d\n" % (passed, failed))
PYATTENDED
RC=$?
[ "$RC" -eq 0 ] || { echo "PROBE FAILED: attended regression block exited $RC"; exit 2; }
read ATTENDED_PASS ATTENDED_FAIL < "$F/attended/state/counts"
PASS=$((PASS + ATTENDED_PASS)); FAIL=$((FAIL + ATTENDED_FAIL))

echo "== l. no-write-outside-state-dir: read-only fixtures, planted checkpoints, the sentinel and the real home path are untouched =="
manifest "$F/projects" "$F/elsewhere" "$F/llm" "$F/llm-win" "$F/llm-big" "$F/role" "$F/vault" "$F/decoy" "$F/handoffs" "$F/mk.py" "$F/stdin-e.json" > "$F/manifest.after"
check "read-only fixture manifest identical ($(wc -l < "$F/manifest.after" | tr -d ' ') files)" "$(cmp -s "$F/manifest.before" "$F/manifest.after" && echo same || echo differ)" "same"
check "sentinel byte-identical" "$(grep -c "$(hashf "$F/decoy/sentinel.txt") $F/decoy/sentinel.txt" "$F/manifest.before")" "1"
manifest "$H" | grep -v '/events.log$' | grep -v "/$SA-\|/sid-i-9999-\|/sid-i2-9998-\|/$SW-\|/$SR-" > "$F/manifest.planted.after"
check "planted checkpoints byte-identical (hooks only add files and append events.log)" "$(cmp -s "$F/manifest.planted.before" "$F/manifest.planted.after" && echo same || echo differ)" "same"
check "real ~/.llm-wiki/handoffs untouched" "$(mstat "$HOME/.llm-wiki/handoffs")" "$HOME_HANDOFFS"
check "real ~/.aimyth/handoffs (the gate's own default) untouched" "$(mstat "$HOME/.aimyth/handoffs")" "$HOME_AIMYTH"
check "no log store leaked into the ambient fixture home" "$([ -e "$HOME/.aimyth/logs" ] && echo present || echo absent)" "$HOME_LOGS"
check "control: g2 created its fixture log store" "$([ -e "$F/home/.aimyth/logs" ] && echo present || echo absent)" "present"
# Where the fifth hook is not shipped, these two legs run on the four hooks that are.
[ -n "${TT-}" ] || check "source grep: no destructive verb in any hook" "$(grep -cE 'os\.remove|os\.unlink|rmtree|os\.rename|shutil\.move|\.unlink\(|os\.rmdir' "$WM" "$PC" "$HG" "$HF" | tr '\n' ' ')" "$WM:0 $PC:0 $HG:0 $HF:0 "
check "…positive control: the same grep hits the planted line" "$(grep -cE 'os\.remove|os\.unlink|rmtree|os\.rename|shutil\.move|\.unlink\(|os\.rmdir' "$F/decoy/control.py")" "1"
[ -n "${TT-}" ] || check "write-mode opens are exactly the declared ones (1 log append; 1 checkpoint write + 1 events append; 1 deny append; 1 events append)" "$(grep -c 'open(.*"[aw]"' "$WM"):$(grep -c 'open(.*"[aw]"' "$PC"):$(grep -c 'open(.*"[aw]"' "$HG"):$(grep -c 'open(.*"[aw]"' "$HF")" "1:2:1:1"

echo "== m. the hooks directory is unchanged; no bytecode is written beside the hooks even without -B =="
manifest "$HOOKS" > "$F/manifest.hooks.after"; find "$HOOKS" -name '*.pyc' | LC_ALL=C sort > "$F/pyc.after"
check ".claude/hooks manifest identical" "$(cmp -s "$F/manifest.hooks.before" "$F/manifest.hooks.after" && echo same || echo differ)" "same"
check "no new .pyc under .claude/hooks" "$(cmp -s "$F/pyc.before" "$F/pyc.after" && echo same || echo differ)" "same"
OUT=$(printf '%s' "$(pcs "$SA" "$T_A" "$F/vault" auto)" | env -u PYTHONDONTWRITEBYTECODE AIMYTH_STATE_DIR="$F/state/handoffs-copy" AIMYTH_INGEST_RUNS="$F/llm/ingest-runs" AIMYTH_SPAWN_RECORDS="$F/llm/spawn-records" AIMYTH_ROLE_STATE_DIR="$F/role" AIMYTH_PROJECTS_DIR="$F/projects" AIMYTH_WATERMARK_LOG="$F/state/wm/context-watermark.log" "$PY" "$F/hookcopy/precompact-checkpoint.py" 2>"$F/state/legacy-diagnostics.txt")
check "production invocation (no -B) of the copied hook wrote a checkpoint" "$(find "$F/state/handoffs-copy" -name "$SA-*-precompact.md" | wc -l | tr -d ' ')" "1"
check "…and left no __pycache__ beside the copies" "$(find "$F/hookcopy" -name '__pycache__' | wc -l | tr -d ' ')" "0"
OUT=$(printf '%s' "$(ptu "$SA" "$T91" "$F/vault" Read "$RD")" | env -u PYTHONDONTWRITEBYTECODE AIMYTH_HANDSOFF=1 AIMYTH_STATE_DIR="$F/state/gate-copy" AIMYTH_PROJECTS_DIR="$F/projects" AIMYTH_CONTEXT_WINDOW=200000 "$PY" "$F/hookcopy/handsoff-gate.py" 2>"$F/state/gate-err.txt")
check "production invocation (no -B) of the copied gate denies and still leaves no __pycache__" "$(dec "$OUT" | cut -d'|' -f2):$(find "$F/hookcopy" -name '__pycache__' | wc -l | tr -d ' ')" "deny:0"
# These calls unset PYTHONDONTWRITEBYTECODE: an inherited export would make the guards vacuous and the bytecode control fail.
env -u PYTHONDONTWRITEBYTECODE "$PY" -c 'import importlib.util, sys; p=sys.argv[1]; s=importlib.util.spec_from_file_location("cw", p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)' "$F/hookcopy-control/context-watermark.py"
check "positive control: the same import without the guard does write __pycache__ here" "$(find "$F/hookcopy-control" -name '__pycache__' | wc -l | tr -d ' ')" "1"

echo
echo "fixtures removed on exit: $F"
if [ "$FAIL" -eq 0 ]; then echo "PASS $PASS/$((PASS+FAIL))"; else echo "FAIL $FAIL/$((PASS+FAIL))"; exit 1; fi
