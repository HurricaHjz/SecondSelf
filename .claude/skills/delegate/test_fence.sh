#!/bin/sh
# Regression cases for shell fencing and path handling.
#
# Every guard change gets a MUST-FIRE leg (a planted case the fence must deny) and a MUST-NOT-FIRE
# leg (a read-only or in-scope case it must clear), plus a premise-failure leg (CLAUDE.md §12).
# A leg's target sits INSIDE the read grants wherever the leg is about the write side, so check 4
# cannot mask it and the leg measures the rule it names (review F7). Fixtures live under one mktemp -d
# the suite removes; the last blocks prove the fence wrote nothing but its log, note and markers
# (inside the fixture) and, when a pre-fold checker is given, report its fail count as the suite's
# own positive control.
#
# Run:  sh test_fence.sh                     (last line: PASS n/n or FAIL k/n)
#       sh test_fence.sh --fence F           (test a copy of the fence elsewhere)
#       FENCE_PRISTINE=<old lane-fence.py> sh test_fence.sh   (adds differential and control runs)
#       FENCE_RECORDED_HELPER=<replay-recorded.sh> sh test_fence.sh   (adds helper controls)
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
FENCE="$HERE/lane-fence.py"
PY="${PYTHON:-python3}"
while [ $# -gt 0 ]; do
  case "$1" in
    --fence) shift; FENCE="${1:-}" ;;
    *) echo "usage: sh test_fence.sh [--fence PATH]" >&2; exit 2 ;;
  esac
  shift
done
[ -f "$FENCE" ] || { echo "PROBE FAILED: no lane-fence.py at $FENCE"; exit 2; }
export PYTHONDONTWRITEBYTECODE=1
FENCE_BEFORE=$("$PY" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$FENCE")

PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  ok   — $1"; }
no(){ FAIL=$((FAIL+1)); echo "FAIL   — $1"; }

F=$(mktemp -d) || { echo "PROBE FAILED: mktemp -d failed"; exit 2; }
cleanup(){ chmod -R u+w "$F" >/dev/null 2>&1; rm -rf "$F"; }
trap cleanup EXIT INT TERM
# K3dc64067: the fixture root is resolved ONCE, to its real path, before any command is built.
# mktemp on some platforms returns a path through a symlinked prefix (/var → /private/var); the
# fence and the recorded-replay helper resolve their vault and writer arguments, so a command built
# from the unresolved spelling names a different path from the one they compare against.
F_MKTEMP="$F"
F_REAL=$(cd "$F" && pwd -P) || { echo "PROBE FAILED: the fixture root could not be resolved"; exit 2; }
[ -n "$F_REAL" ] && [ -d "$F_REAL" ] || { echo "PROBE FAILED: the fixture root resolved to nothing"; exit 2; }
F="$F_REAL"
# The unplaced-read logger writes only for a run its store knows. The store and the scratch folder
# are this fixture's and the run and lane ids are cleared, so no leg can reach a live run's log, even
# when the suite runs inside a lane (N04). Legs that set their own store keep overriding it.
unset LLM_WIKI_LANE_RUN LLM_WIKI_LANE_ID
LLM_WIKI_STORE="$F/store"; LLM_WIKI_PROGRESS_DIR="$F/notes"; export LLM_WIKI_STORE LLM_WIKI_PROGRESS_DIR
mkdir -p "$F/store" "$F/notes"

# --- fixtures. $F comes from mktemp, which on this platform lands under $TMPDIR (/var/folders),
# NOT /tmp, so $F is not a sanctioned temp root and an "outside the grants" path can be denied.
mkdir -p "$F/granted/wt" "$F/granted/v/.claude/skills/ingest" "$F/writable" "$F/elsewhere"
printf 'INSIDE\n'    > "$F/granted/inside.txt"
printf 'section\n'   > "$F/granted/main.tex"
printf 'INDEX\n'     > "$F/granted/index.md"
printf '{"a":1}\n'   > "$F/granted/data.json"
printf 'ELSEWHERE\n' > "$F/elsewhere/outside.txt"
# fix 4 / review F2b: a symlink that SITS inside a grant but POINTS outside it must now DENY (its
# target is what a read reaches); a two-node loop must not crash the checker either way.
ln -s "$F/elsewhere/outside.txt" "$F/granted/link.txt"
ln -s "$F/granted/loopb" "$F/granted/loopa"
ln -s "$F/granted/loopa" "$F/granted/loopb"
ln -s "$F/elsewhere/loopd" "$F/elsewhere/loopc"
ln -s "$F/elsewhere/loopc" "$F/elsewhere/loopd"
# fix 6: a script that ships under .claude/skills and honours the write variable, a scratch one, and
# a shipped-looking tool that takes a SUB-COMMAND rather than a file.
printf 'import os\nos.environ["LLM_WIKI_LANE_WRITES"]\n' > "$F/granted/v/.claude/skills/ingest/sanitise.py"
printf 'open("x", "w")\n' > "$F/granted/scratch.py"
printf 'import sys\nprint(sys.argv)\n' > "$F/granted/tool.py"

G="$F/granted"; W="$F/writable"

# The checker, called as the wrapper calls it. name, want(allow|deny|silent), command,
# [grants=$G], [writes=""], [network=""], [role=""], [cwd="."], [boundary=""], [operand=""].
fence(){
  NAME="$1"; WANT="$2"; CMD="$3"; FG="${4-$G}"; FW="${5-}"; FN="${6-}"; ROLE="${7-}"; FCWD="${8-.}"
  BOUNDARY="${9-}"; OPERAND="${10-}"
  # FCWD is the working directory of the CHECKER process (default `.`). A leg about a RELATIVE
  # target must set it outside every write root, or the suite's own cwd would clear it for free.
  OUT=$(printf '%s' "$("$PY" - "$CMD" <<'FENCE_JSON_TERMINATOR'
import json, sys
print(json.dumps({"tool_name": "Bash", "tool_input": {"command": sys.argv[1]}}))
FENCE_JSON_TERMINATOR
)" | (cd "$FCWD" && env LLM_WIKI_LANE_GRANTS="$FG" LLM_WIKI_LANE_WRITES="$FW" \
        LLM_WIKI_LANE_NETWORK="$FN" "$PY" "$FENCE" $ROLE))
  RC=$?
  if [ "$RC" != 0 ]; then no "fence exited $RC on: $NAME"; return; fi
  GOT=silent
  printf '%s' "$OUT" | grep -q '"permissionDecision": "deny"'  && GOT=deny
  printf '%s' "$OUT" | grep -q '"permissionDecision": "allow"' && GOT=allow
  REASON_RC=0
  if [ -n "$BOUNDARY" ] || [ -n "$OPERAND" ]; then
    "$PY" - "$OUT" "$BOUNDARY" "$OPERAND" <<'FENCE_REASON_TERMINATOR'
import json, re, sys
try:
    reason = json.loads(sys.argv[1])['hookSpecificOutput']['permissionDecisionReason']
    boundary, operand = sys.argv[2:]
    matches = bool(re.search(boundary, reason, re.I)) and operand in reason
except (ValueError, KeyError, TypeError, re.error) as exc:
    print('PROBE FAILED: refusal reason could not be checked: ' + str(exc))
    sys.exit(2)
sys.exit(0 if matches else 1)
FENCE_REASON_TERMINATOR
    REASON_RC=$?
    [ "$REASON_RC" != 2 ] || exit 2
  fi
  if [ "$GOT" = "$WANT" ] && [ "$REASON_RC" = 0 ]; then ok "$WANT: $NAME"
  else no "$NAME  [want $WANT, got $GOT: $OUT]"; fi
}

# Commands carrying backslashes or regex literals are built through a QUOTED heredoc (no expansion,
# backslashes literal), then the granted path is substituted in, so the fence receives exact bytes.
sub(){ printf '%s' "$1" | sed "s#GRANTED#$G#g"; }
AWK_EXACT=$(sub "$(cat <<'RAW_TERMINATOR'
awk '/\\section\{Discussion\}/{p=1} /\\section\{Conclusion\}/{p=0} p' GRANTED/main.tex
RAW_TERMINATOR
)")
AWK_SHC=$(sub "$(cat <<'RAW_TERMINATOR'
sh -c "awk '/\\section\{Discussion\}/{p=1} p' GRANTED/main.tex"
RAW_TERMINATOR
)")
AWK_UNQUOTED=$(sub "$(cat <<'RAW_TERMINATOR'
awk /\\section\{Discussion\}/{p=1} GRANTED/main.tex
RAW_TERMINATOR
)")
PY_RE=$(sub "$(cat <<'RAW_TERMINATOR'
python3 -c "import re; print(re.findall(r'/\\section\{D\}/', open('GRANTED/main.tex').read()))"
RAW_TERMINATOR
)")
ESC_HOSTS=$(cat <<'RAW_TERMINATOR'
cat /etc/hos\ts
RAW_TERMINATOR
)
ESC_SHC=$(cat <<'RAW_TERMINATOR'
sh -c 'cat /etc/hos\ts'
RAW_TERMINATOR
)

echo "== fix 1 + review F2a: a /-led token is a path when the shell hands it over WHOLE =="
fence "1 must-not-fire: the entry's exact awk pattern in a granted dir clears" allow "$AWK_EXACT"
fence "1 must-not-fire (fails on pristine): the same awk pattern behind sh -c clears" allow "$AWK_SHC"
fence "1 must-not-fire (fails on pristine): the unquoted awk pattern clears"    allow "$AWK_UNQUOTED"
fence "1 must-not-fire (fails on pristine): a python -c regex literal clears"   allow "$PY_RE"
fence "1 must-fire: a bare read of /etc/hosts outside the grants denies"        deny  "cat /etc/hosts"
fence "F2a must-fire: a WHOLE lone / is a path operand — ls / denies"           deny  "ls /"
fence "F2a must-fire: find / -name denies"                                      deny  "find / -name '*.pem'"
fence "F2a must-fire: grep -r password / denies"                                deny  "grep -r password /"
fence "F2a must-fire: a backslash-escaped path is unescaped before the test"    deny  "$ESC_HOSTS"
fence "F2a must-fire: the same inside an sh -c payload"                         deny  "$ESC_SHC"
fence "F2a must-fire: a glob cut leaves a PATH, not a fragment — cat /etc/*.md denies" \
      deny "cat /etc/*.md"
fence "1 control: an awk pattern does not blind check 4 — an outside FILE operand still denies" \
      deny "awk '{print}' /etc/passwd"
fence "1 premise (zero-match pattern): an anchored empty pattern is no path and clears" \
      allow "grep '/^\$/' $G/inside.txt"

echo "== fix 2: the delimiter shapes (a quoted whole / is now a path operand: named residue) =="
fence "2 must-not-fire: an unquoted awk -F/ field print clears"  allow "awk -F/ '{print \$NF}' $G/main.tex"
fence "2 residue (accepted with F2a): a QUOTED whole '/' separator is a path operand and denies" \
      deny "ls $G | cut -d'/' -f2"
fence "2 must-not-fire: a sed s#…# path-strip delimiter clears"  allow "ls $G | sed -e 's#$G/##'"
fence "2 must-fire: an outside FILE operand past a separator still denies" \
      deny "awk -F/ '{print \$2}' $F/elsewhere/outside.txt"
fence "2 control: the field pipe writing outside the write roots still denies (check 2)" \
      deny "ls $G | awk -F/ '{print \$2}' > $F/elsewhere/o.txt" "$G" "$W"

echo "== block 2R: sanitised regression shapes, not reconstructions of truncated events =="
REPLAY="${FENCE_REPLAY_JSON:-$HERE/test_fence_replay.json}"
[ -f "$REPLAY" ] || { echo "PROBE FAILED: replay fixture missing at $REPLAY"; exit 2; }
RN=$("$PY" -c 'import json,sys; print(len(json.load(open(sys.argv[1], encoding="utf-8"))))' "$REPLAY")
[ "$RN" = 12 ] || { echo "PROBE FAILED: replay fixture holds $RN texts, expected 12"; exit 2; }
# The fixture carries placeholder tokens, never a captured path. Each token maps to a synthetic root
# under $F/replay, and those roots exist, because the fence tests a leading cd and a leaf by
# existence; the grants are the synthetic twins of the roots the shapes were first run under.
RV="$F/replay/vault"; RH="$F/replay/home"; RS="$RH/.llm-wiki"; RP="$F/replay/plant"
mkdir -p "$RV/.claude/skills/delegate" "$RS/spawn-records" "$RS/hooks" "$RH/.claude/projects" "$RP"
RG="$RV:$RS/spawn-records:$RS/hooks:$RH/.claude/projects"
RW="$RV/.claude/skills/delegate:$RS/hooks:$RS/spawn-records"
RJSON="$F/replay/replay.json"
replay_set(){ # fixture, out: refuse an unknown or surviving token, else write the substituted set
  "$PY" - "$1" "$2" "$RV" "$RH" "$RS" <<'REPLAY_SET_TERMINATOR'
import json, re, sys
src, out, vault, home, store = sys.argv[1:6]
MAP = {"@@VAULT@@": vault, "@@HOME@@": home, "@@STORE@@": store, "@@PROJECT_KEY@@": "fixture-project"}
TOKEN = re.compile(r"@@[A-Z_]+@@")
texts = json.load(open(src, encoding="utf-8"))
if any(e.get("provenance") != "sanitised regression shape; not an exact replay of a truncated event"
       or e.get("expected_head") not in ("silent", "deny") for e in texts):
    print("PROBE FAILED: replay provenance or expectation missing")
    sys.exit(2)
unknown = sorted({t for e in texts for k in ("full", "result") for t in TOKEN.findall(e[k])} - set(MAP))
if unknown:
    print("PROBE FAILED: unknown replay token(s) " + ", ".join(unknown))
    sys.exit(2)
for e in texts:
    for k in ("full", "result"):
        for token in sorted(MAP, key=len, reverse=True):
            e[k] = e[k].replace(token, MAP[token])
        if TOKEN.search(e[k]):
            print("PROBE FAILED: a replay token survived substitution at " + e["ts"])
            sys.exit(2)
with open(out, "w", encoding="utf-8") as fh:
    json.dump(texts, fh)
REPLAY_SET_TERMINATOR
}
replay_scan(){ # fixture: count captured home paths, their dash-encoded form, per-user task roots, unknown tokens
  "$PY" - "$1" <<'REPLAY_SCAN_TERMINATOR'
import json, re, sys
KNOWN = {"@@VAULT@@", "@@HOME@@", "@@STORE@@", "@@PROJECT_KEY@@"}
HOME_PATH = re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+|[A-Za-z]:\\Users\\")
ENCODED = re.compile(r"-(?:Users|home)-[A-Za-z0-9._]")
TASK_ROOT = re.compile(r"/tmp/claude-[0-9]+/")
TOKEN = re.compile(r"@@[A-Z_]+@@")
n = 0
for e in json.load(open(sys.argv[1], encoding="utf-8")):
    for k in ("full", "result"):
        n += len(HOME_PATH.findall(e[k])) + len(ENCODED.findall(e[k])) + len(TASK_ROOT.findall(e[k]))
        n += len([t for t in TOKEN.findall(e[k]) if t not in KNOWN])
print(n)
REPLAY_SCAN_TERMINATOR
}
"$PY" - "$REPLAY" "$RP" <<'REPLAY_PLANT_TERMINATOR'
import json, os, sys
texts = json.load(open(sys.argv[1], encoding="utf-8"))
home_root = "/" + "Us" + "ers"   # assembled: this suite ships, and a literal home path halts the publish gate
planted = {"path.json": (0, "full", " " + home_root + "/example/vault"),
           "encoded.json": (1, "full", " -" + "Us" + "ers-example-vault"),
           "taskroot.json": (2, "full", " /private/tmp/claude-" + "4242" + "/x"),
           "token.json": (2, "result", " @@UNKNOWN@@")}
for name, (i, key, extra) in planted.items():
    copy = [dict(e) for e in texts]
    copy[i][key] += extra
    with open(os.path.join(sys.argv[2], name), "w", encoding="utf-8") as fh:
        json.dump(copy, fh)
REPLAY_PLANT_TERMINATOR
C0=$(replay_scan "$REPLAY"); C1=$(replay_scan "$RP/path.json")
C2=$(replay_scan "$RP/encoded.json"); C3=$(replay_scan "$RP/token.json"); C4=$(replay_scan "$RP/taskroot.json")
if [ "$C0" = 0 ] && [ "${C1:-0}" -ge 1 ] && [ "${C2:-0}" -ge 1 ] && [ "${C3:-0}" -ge 1 ] && [ "${C4:-0}" -ge 1 ]; then
  ok "the fixture carries no captured home path, encoded home path, per-user task root or unknown token (controls: planted $C1, $C2, $C4, $C3)"
else no "fixture sanitisation scan  [fixture $C0; planted path $C1, encoded path $C2, task root $C4, token $C3]"; fi
TOUT=$(replay_set "$RP/token.json" "$F/replay/refused.json"); TRC=$?
if [ "$TRC" = 2 ] && printf '%s' "$TOUT" | grep -q 'unknown replay token'; then
  ok "an injected unknown token makes the replay set refuse (exit 2)"
else no "unknown-token refusal  [exit $TRC: $TOUT]"; fi
replay_set "$REPLAY" "$RJSON" || { echo "PROBE FAILED: the replay set could not be prepared"; exit 2; }
replay(){ # ts, want(silent|deny)
  RTS="$1"; RWANT="$2"
  RJ=$("$PY" - "$RJSON" "$RTS" <<'REPLAY_JSON_TERMINATOR'
import json, sys
texts = json.load(open(sys.argv[1], encoding="utf-8"))
hit = [e for e in texts if e["ts"] == sys.argv[2]]
if len(hit) != 1:
    sys.stderr.write("PROBE FAILED: %s matched %d texts\n" % (sys.argv[2], len(hit))); sys.exit(2)
print(json.dumps({"tool_name": "Bash", "tool_input": {"command": hit[0]["full"]}}))
REPLAY_JSON_TERMINATOR
) || { no "replay $RTS: fixture lookup failed"; return; }
  OUT=$(printf '%s' "$RJ" | (cd "$F/elsewhere" && env LLM_WIKI_LANE_GRANTS="$RG" \
        LLM_WIKI_LANE_WRITES="$RW" LLM_WIKI_LANE_NETWORK="" "$PY" "$FENCE" --head))
  GOT=silent
  printf '%s' "$OUT" | grep -q '"permissionDecision": "deny"'  && GOT=deny
  printf '%s' "$OUT" | grep -q '"permissionDecision": "allow"' && GOT=allow
  if [ "$GOT" = "$RWANT" ]; then ok "replay $RTS → $GOT (as required)"
  else no "replay $RTS  [want $RWANT, got $GOT: $(printf '%s' "$OUT" | cut -c1-160)]"; fi
}
replay "2000-01-01T00:00:01Z" silent
replay "2000-01-01T00:00:02Z" silent
for RT in 03 04 05 06 07 08 09 10 11 12; do
  replay "2000-01-01T00:00:${RT}Z" deny
done

echo "== block 2C + review F3: the leading-cd narrowing, attacked on its own premises =="
fence "2C must-not-fire (fails on pristine): a relative target after cd into W clears" \
      allow "cd $W && rm -f handsoff.py.orig" "$G" "$W" "" "" "$F/elsewhere"
fence "F3 must-fire: a cd into a directory that does NOT exist grants no base (; joiner)" \
      deny "cd $F/nope-crf; rm -f handsoff.py.orig" "$G" "$W" "" "" "$F/elsewhere"
fence "F3 must-fire: the same with a || true joiner" \
      deny "cd $F/nope-crf || true; rm -f handsoff.py.orig" "$G" "$W" "" "" "$F/elsewhere"
fence "F3 must-fire: even with && the base needs a directory that exists" \
      deny "cd $F/nope-crf && rm -f handsoff.py.orig" "$G" "$W" "" "" "$F/elsewhere"
fence "F3 must-fire: a ; joiner after a real cd grants no base (the shell runs the rest regardless)" \
      deny "cd $W; rm -f handsoff.py.orig" "$G" "$W" "" "" "$F/elsewhere"
fence "2C must-fire: the same shape climbing back out of W with .. still denies" \
      deny "cd $W && rm -f ../elsewhere/x" "$G" "$W" "" "" "$F/elsewhere"
fence "2C premise (subshell): a cd inside parentheses grants no base" \
      deny "( cd $W && rm -f y.orig )" "$G" "$W" "" "" "$F/elsewhere"
fence "2C premise (variable cd): a cd the fence cannot resolve grants no base" \
      deny "cd \"\$D\" && rm -f z.orig" "$G" "$W" "" "" "$F/elsewhere"
fence "2C premise (cd outside W): a cd into a dir outside the write roots grants no base" \
      deny "cd $G && rm -f w.orig" "$G" "$W" "" "" "$F/elsewhere"
fence "2C premise (two cds): more than one cd is ambiguous, so no base is taken" \
      deny "cd $W && cd $G && rm -f v.orig" "$G" "$W" "" "" "$F/elsewhere"

echo "== fix 4 + review F2b: a leaf that EXISTS is read through its symlink =="
fence "F2b must-fire: a symlink inside a grant pointing OUT is denied by its target" \
      deny "cat $G/link.txt"
fence "4 must-fire: the outside target named directly denies"  deny "cat $F/elsewhere/outside.txt"
fence "4 must-not-fire: a leaf that does not exist yet is tested by its parent and clears" \
      allow "cat $G/not-created-yet.md"
fence "4 premise (symlink loop inside a grant): no crash, and the decision is a valid one" \
      allow "cat $G/loopa"
fence "4 premise (symlink loop outside the grants): no crash, denied as outside" \
      deny "cat $F/elsewhere/loopc"

echo "== fix 5 (tripwire, shape c) + review F4: the literal shape only =="
fence "5 must-fire: a heredoc open() in write mode outside W denies" \
      deny "$(printf 'python3 - <<%s\nopen(%s%s/out.md%s, %sw%s)\n%s' "'PY'" "'" "$G" "'" "'" "'" "PY")" "$G" "$W"
fence "5 must-not-fire: the same open() inside W clears" \
      allow "$(printf 'python3 - <<%s\nopen(%s%s/a.md%s, %sw%s)\n%s' "'PY'" "'" "$W" "'" "'" "'" "PY")" "$G" "$W"
fence "5 must-fire (target inside R, outside W): -c open() in write mode denies" \
      deny "python3 -c \"open('$G/out.md', 'a')\"" "$G" "$W"
fence "F4 must-fire: -E before -c no longer defeats the tripwire" \
      deny "python3 -E -c \"open('$G/out.md','w')\"" "$G" "$W"
fence "F4 must-fire: -Wignore before -c no longer defeats it either" \
      deny "python3 -Wignore -c \"open('$G/out.md','w')\"" "$G" "$W"
fence "5 must-fire: Path().write_text on a literal inside R, outside W denies" \
      deny "python3 -c \"from pathlib import Path; Path('$G/out.md').write_text('x')\"" "$G" "$W"
fence "5 must-not-fire: a payload that only reads clears"  allow "python3 -c \"open('$G/inside.txt')\"" "$G" "$W"
fence "5 must-not-fire: a read-mode open clears"           allow "python3 -c \"open('$G/inside.txt','r')\"" "$G" "$W"
fence "5 residue (stated, shape c): a variable target is invisible to the tripwire" \
      allow "python3 -c \"p='$G/out.md'; open(p, 'w')\"" "$G" "$W"
fence "5 premise (open inside a comment): a commented-out write is ignored" \
      allow "$(printf 'python3 - <<%s\n# open(%s%s/out.md%s, %sw%s)\nprint(1)\n%s' "'PY'" "'" "$G" "'" "'" "'" "PY")" "$G" "$W"
fence "5 premise (terminator inside body): a body line equal to the marker ends it" \
      deny "$(printf 'python3 - <<%s\nprint(1)\nPY\ncat %s/elsewhere/outside.txt\n%s' "'PY'" "$F" "PY")" "$G" "$W"
fence "F8 must-not-fire: a relative literal takes the leading-cd base too" \
      allow "cd $W && python3 -c \"open('note.md','w')\"" "$G" "$W" "" "" "$F/elsewhere"

echo "== fix 6 + review F5: a script operand is a file, a -m operand is a module =="
fence "F5 must-not-fire: the lane core's own markitdown recipe clears on a write-less lane" \
      allow "python3 -m markitdown $G/main.tex -o /tmp/x.md" "$G" ""
fence "F5 must-not-fire: python3 -m json.tool over a granted file clears" \
      allow "python3 -m json.tool $G/data.json" "$G" ""
fence "F5 must-not-fire: a sub-command operand is not a file argument, on a script that honours the variable" \
      allow "python3 -B $G/v/.claude/skills/ingest/sanitise.py gate --run r" "$G" ""
# review N1 tightened this: on a script that does NOT ship under `.claude/skills/` and honour the
# variable, ANY argument counts, a bare sub-command word included. That is the fold's intent (a
# scratch script must not be handed a name to write), and it is stated here rather than left to be
# discovered: a write-less lane running such a tool with any argument is denied.
fence "N1 must-fire: the same sub-command word on a NON-shipped script now denies" \
      deny "python3 -B $G/tool.py gate --run r" "$G" ""
fence "6 must-fire (fails on pristine): a scratch script with a file argument denies" \
      deny "python3 -B $G/scratch.py $G/inside.txt" "$G" ""
fence "6 must-not-fire: a .claude/skills script honouring the variable clears" \
      allow "python3 -B $G/v/.claude/skills/ingest/sanitise.py $G/inside.txt" "$G" ""
fence "6 premise (no file argument): the same scratch script with no file arg clears" \
      allow "python3 -B $G/scratch.py" "$G" ""
fence "6 premise (-c is the payload scan's, not 2c's)" allow "python3 -c \"print(1)\"" "$G" ""

echo "== fix 7 + review F6: class N, every host, userinfo, and payload recursion =="
fence "7 must-fire: curl with no network grant denies"  deny "curl https://api.openalex.org/x" "$G" "" ""
fence "7 must-not-fire: curl under a grant naming the host clears" \
      allow "curl https://api.openalex.org/x" "$G" "" "api.openalex.org"
fence "F6 must-fire: sh -c 'curl …' no longer hides the client" \
      deny "sh -c 'curl https://evil.example.com/x'" "$G" "" ""
fence "F6 must-fire: bash -c \"curl …\" likewise"  deny "bash -c \"curl https://evil.example.com\"" "$G" "" ""
fence "F6 must-fire: a comma import list reaches the transport" \
      deny "python3 -c \"import os, urllib.request; urllib.request.urlopen('https://e.com')\"" "$G" "" ""
fence "F6 must-fire: __import__ of a transport" deny "python3 -c \"__import__('urllib.request')\"" "$G" "" ""
fence "F6 must-fire: node require('https')"     deny "node -e \"require('https').get('https://e.com')\"" "$G" "" ""
fence "F6 must-fire: perl use LWP"              deny "perl -e 'use LWP::Simple; get(q{https://e.com})'" "$G" "" ""
fence "F6 must-fire: EVERY host is checked, not the first" \
      deny "curl evil.example.com https://api.openalex.org/x" "$G" "" "api.openalex.org"
fence "F6 must-fire: userinfo before @ is not the host" \
      deny "curl https://api.openalex.org@evil.example.com/" "$G" "" "api.openalex.org"
fence "F6 must-not-fire: socket.gethostname() opens nothing and clears" \
      allow "python3 -c \"import socket; print(socket.gethostname())\"" "$G" "" ""
fence "7 must-not-fire: grep http … is a word, not a command" allow "grep http $G/index.md" "$G" "" ""
fence "7 premise (no host token under a grant): unresolvable, denied" \
      deny "curl -X POST" "$G" "" "api.openalex.org"
fence "7 control: a plain read under a network grant clears" allow "cat $G/inside.txt" "$G" "" "api.openalex.org"

echo "== review fold: N1 a bare argument counts, N2 no expansion in the exemption, N3 IPv6 hosts =="
# N1 — relative-file operands: an argument that does not exist on disk and carries no
# separator must still be counted.
fence "N1 must-fire: a bare relative argument counts even though it does not exist" \
      deny "python3 -B $G/scratch.py somename" "$G" ""
fence "N1 must-fire: the same with a dotted name" \
      deny "python3 -B $G/scratch.py out.md" "$G" ""
fence "N1 must-not-fire: an option's VALUE is not a file operand" \
      allow "python3 -B $G/scratch.py --lane X" "$G" ""
fence "N1 must-not-fire: a shipped script honouring the variable clears with a flag value" \
      allow "python3 -B $G/v/.claude/skills/ingest/sanitise.py --lane X" "$G" ""
fence "N1 must-not-fire: a shipped script honouring the variable clears with a file too" \
      allow "python3 -B $G/v/.claude/skills/ingest/sanitise.py $G/inside.txt" "$G" ""
fence "N1 control: the module recipes still clear (a -m operand is never a script)" \
      allow "python3 -m json.tool $G/data.json" "$G" ""

# N2 — the exemption is head-side, so it is asserted on the property itself rather than through
# check(): `is_grant_change` must refuse any word carrying `$`, and a `-c` payload that merely
# spells the primitive's path is program text, not the script being run.
mkdir -p "$G/v/.claude/skills/delegate"
printf 'print(1)\n' > "$G/v/.claude/skills/delegate/handsoff.py"
QHO="$G/v/.claude/skills/delegate/handsoff.py"
grantchange(){ # name, want(yes|no), command
  GNAME="$1"; GWANT="$2"; GCMD="$3"
  GOT=$("$PY" - "$FENCE" "$GCMD" <<'GRANTCHANGE_TERMINATOR'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("lf", sys.argv[1])
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
print("yes" if module.is_grant_change(sys.argv[2]) else "no")
GRANTCHANGE_TERMINATOR
)
  if [ "$GOT" = "$GWANT" ]; then ok "$GWANT: $GNAME"
  else no "$GNAME  [want $GWANT, got $GOT]"; fi
}
grantchange "N2 must-not-fire: the real primitive still earns the exemption" yes "$QHO grants --grant /some/new/path"
grantchange "N2 must-not-fire: the interpreter form still earns it" yes "python3 -B $QHO grants --on-limit stop"
grantchange "N2 must-fire: a \$VAR argument refuses the exemption" no "$QHO grants --grant \$NEWDIR"
grantchange "N2 must-fire: a \${VAR} argument refuses it too" no "$QHO grants --grant \${NEWDIR}"
grantchange "N2 must-fire: a -c payload spelling the path is not the primitive" no "python3 -c $QHO grants"
grantchange "N2 control: an appended mutator still refuses" no "$QHO grants --grant /x; rm -rf /y"

# N3 — a bracketed IPv6 authority split at its first colon would read the host as `[2001` and deny
# under a grant naming that very address.
fence "N3 must-not-fire: a bracketed IPv6 host clears under a grant naming it" \
      allow "curl https://[2001:db8::1]/x" "$G" "" "2001:db8::1"
fence "N3 must-fire: the same IPv6 host denies with no network grant" \
      deny "curl https://[2001:db8::1]/x" "$G" "" ""
fence "N3 premise: a named host with a port still parses to the host" \
      allow "curl https://evil.example.com:8443/x" "$G" "" "evil.example.com"
fence "N3 control: a named host with a port is still checked against the grant" \
      deny "curl https://evil.example.com:8443/x" "$G" "" "api.openalex.org"

# >>> batch 9 legs (K3dc64067, K23b12c39, Kef9c30da, Kc37755f0, Kb2a266d1)
echo "== batch 9: fixture root, symlink docstring, glob words, search patterns, curl values =="
if [ "$F" = "$(cd "$F" && pwd -P)" ]; then
  ok "K3dc64067 premise: the fixture root is its own real path before any command is built"
else no "K3dc64067 premise: the fixture root is not its real path  [$F]"; fi
# K23b12c39: the narrowed symlink rule, pinned. A venv-shaped interpreter that is a live symlink out
# of the grants is refused by its target; the same venv made with --copies is a file inside the grant.
mkdir -p "$G/venv/bin" "$G/venvc/bin" "$F/elsewhere/bin"
printf '#!/bin/sh\n' > "$F/elsewhere/bin/python3"
ln -s "$F/elsewhere/bin/python3" "$G/venv/bin/python"
printf '#!/bin/sh\n' > "$G/venvc/bin/python"
fence "K23b12c39 must-fire (pinned): a venv bin/python symlinked out of the grants is refused" \
      deny "$G/venv/bin/python -c 'print(1)'" "$G" "" "" "" "." 'outside the granted directories' "$G/venv/bin/python"
fence "K23b12c39 must-not-fire: the same venv made with --copies clears" \
      allow "$G/venvc/bin/python -c 'print(1)'"
DOC_N=$(grep -c 'reads as granted' "$FENCE"); DOC_PLANT="$F/planted-doc.py"
{ cat "$FENCE"; printf '# a symlinked venv interpreter reads as granted\n'; } > "$DOC_PLANT"
DOC_C=$(grep -c 'reads as granted' "$DOC_PLANT")
if [ "$DOC_N" = 0 ] && [ "${DOC_C:-0}" -ge 1 ]; then
  ok "K23b12c39 docstring: the fence no longer says a symlink out of the grants 'reads as granted' (control: planted copy $DOC_C)"
else no "K23b12c39 docstring  [fence $DOC_N, planted $DOC_C]"; fi
# Kef9c30da: a glob word is read whole and judged by its deepest literal directory.
mkdir -p "$G/s1" "$G/s2" "$F/elsewhere/s3"
printf 'one\n' > "$G/s1/f.md"; printf 'two\n' > "$G/s2/f.md"; printf 'three\n' > "$F/elsewhere/s3/f.md"
fence "Kef9c30da must-not-fire: a granted glob ending in / clears" allow "ls -d $G/*/"
fence "Kef9c30da must-not-fire: a granted glob followed by a file clears" allow "cat $G/*/f.md"
fence "Kef9c30da must-not-fire: the same glob inside an sh -c payload clears" allow "sh -c 'ls -d $G/*/'"
fence "Kef9c30da must-fire: ls /etc/*/ still denies" deny "ls /etc/*/" \
      "$G" "" "" "" "." 'outside the granted directories' '/etc/'
fence "Kef9c30da must-fire: an ungranted glob followed by a file denies" deny "cat $F/elsewhere/*/f.md" \
      "$G" "" "" "" "." 'outside the granted directories' "$F/elsewhere/"
fence "Kef9c30da must-fire: a dot-led glob component keeps the split reading and denies" \
      deny "cat $G/.*/f.md" "$G" "" "" "" "." 'outside the granted directories' '/f.md'
fence "Kef9c30da residue (stated, fail-closed): a lone / literal in an inline program still denies" \
      deny "python3 -c \"print('/'.join(['a', 'b']))\"" "$G" "" "" "" "." 'outside the granted directories' '`/`'
# Kc37755f0: check 1 skips a search command's pattern words, and nothing that can run a program.
fence "Kc37755f0 must-not-fire: a grep whose pattern holds the quoted program name clears" \
      allow "grep -n '\"claude\"' $G/index.md"
fence "Kc37755f0 must-not-fire: the -e form clears" allow "grep -e claude $G/index.md"
fence "Kc37755f0 must-not-fire: an rg pattern clears" allow "rg -n 'claude -p' $G"
fence "Kc37755f0 must-fire: claude -p hi still denies" deny "claude -p hi" \
      "$G" "" "" "" "." 'no nested spawns' 'claude'
fence "Kc37755f0 must-fire: python3 -c naming claude still denies" \
      deny "python3 -c \"import subprocess; subprocess.run(['claude', '-p', 'hi'])\"" \
      "$G" "" "" "" "." 'no nested spawns' 'claude'
fence "Kc37755f0 must-fire: xargs claude still denies" deny "printf x | xargs claude" \
      "$G" "" "" "" "." 'no nested spawns' 'claude'
fence "Kc37755f0 must-fire: a search piped into claude still denies" deny "grep -l x $G/index.md | xargs claude" \
      "$G" "" "" "" "." 'no nested spawns' 'claude'
fence "Kc37755f0 must-fire: a pattern word holding a command substitution is still read" \
      deny "grep \"\$(claude -p hi)\" $G/index.md" "$G" "" "" "" "." 'no nested spawns' 'claude'
fence "Kc37755f0 must-fire: an awk program is program text and is still read" \
      deny "awk 'BEGIN{system(\"claude -p hi\")}'" "$G" "" "" "" "." 'no nested spawns' 'claude'
fence "Kc37755f0 must-fire: an rg option that runs a program gets no skip" deny "rg --pre claude x $G" \
      "$G" "" "" "" "." 'no nested spawns' 'claude'
# Kb2a266d1: the value of a curl or wget file option is no host; an endpoint option's value still is.
NETG="api.openalex.org"
fence "Kb2a266d1 must-not-fire: curl -o x.md clears under a grant naming the URL's host" \
      allow "curl -o x.md https://api.openalex.org/x" "$G" "$W" "$NETG" "" "$W"
fence "Kb2a266d1 must-not-fire: the long --output form clears" \
      allow "curl --output x.md https://api.openalex.org/x" "$G" "$W" "$NETG" "" "$W"
fence "Kb2a266d1 must-not-fire: wget -O x.md clears" \
      allow "wget -O x.md https://api.openalex.org/x" "$G" "$W" "$NETG" "" "$W"
fence "Kb2a266d1 must-fire: a bare curl evil.example.com still denies" \
      deny "curl evil.example.com" "$G" "$W" "$NETG" "" "$W" 'network host.*not named' 'evil.example.com'
fence "Kb2a266d1 must-fire: -o x.md beside a bare ungranted host denies" \
      deny "curl -o x.md evil.example.com" "$G" "$W" "$NETG" "" "$W" 'network host.*not named' 'evil.example.com'
fence "Kb2a266d1 must-fire: a proxy value is still a host" \
      deny "curl -x evil.example.com:8080 https://api.openalex.org/x" "$G" "$W" "$NETG" "" "$W" 'network host.*not named' 'evil.example.com'
fence "Kb2a266d1 must-fire: the value of --url is still a host" \
      deny "curl --url evil.example.com https://api.openalex.org/x" "$G" "$W" "$NETG" "" "$W" 'network host.*not named' 'evil.example.com'
fence "Kb2a266d1 must-fire: wget -e (a wgetrc command) keeps its value a host candidate" \
      deny "wget -e http_proxy=evil.example.com:8080 https://api.openalex.org/x" "$G" "$W" "$NETG" "" "$W" 'denied as unresolvable' 'wget -e'
fence "Kb2a266d1 must-fire: with no network grant, curl -o x.md still denies" \
      deny "curl -o x.md https://api.openalex.org/x" "$G" "$W" "" "" "$W" 'no `network` list' 'api.openalex.org'
# The actual harness faces planted JSON, so a decision-only implementation fails these controls.
# Each probe runs in a subshell: its expected failure cannot change the suite's own counters.
REASON_CHECKER="$FENCE"
FENCE="$F/planted-reason.py"
cat > "$FENCE" <<'FENCE_REASON_PLANT_END'
import json, os
print(json.dumps({'hookSpecificOutput': {'permissionDecision': 'deny',
    'permissionDecisionReason': os.environ['FENCE_REASON_PLANT']}}))
FENCE_REASON_PLANT_END
for REASON_KIND in correct write wrong-host missing-network-write; do
  case "$REASON_KIND" in
    correct) FENCE_REASON_PLANT='the network host `evil.example.com` is not named in the network grant' ;;
    write) FENCE_REASON_PLANT='target `x.md` is outside the write whitelist' ;;
    wrong-host) FENCE_REASON_PLANT='the network host `other.example.invalid` is not named in the network grant' ;;
    missing-network-write) FENCE_REASON_PLANT='target `x.md` is outside the write whitelist' ;;
  esac
  export FENCE_REASON_PLANT
  if [ "$REASON_KIND" = missing-network-write ]; then
    REASON_PROBE=$(fence 'planted missing-network reason' deny "curl -o x.md https://api.openalex.org/x" \
                  "$G" "$W" "" "" "$W" 'no `network` list' 'api.openalex.org')
  else
    REASON_PROBE=$(fence 'planted host reason' deny 'curl -o x.md evil.example.com' \
                  "$G" "$W" "$NETG" "" "$W" 'network host.*not named' 'evil.example.com')
  fi
  REASON_PROBE_RC=$?
  [ "$REASON_PROBE_RC" = 0 ] || { echo "PROBE FAILED: planted reason harness exited $REASON_PROBE_RC"; exit 2; }
  if [ "$REASON_KIND" = correct ]; then
    if printf '%s\n' "$REASON_PROBE" | grep -q '^  ok '; then
      ok 'refusal reason control: the named network boundary passes'
    else no "refusal reason control: the named network boundary failed [$REASON_PROBE]"; fi
  elif printf '%s\n' "$REASON_PROBE" | grep -q '^FAIL '; then
    ok "refusal reason control: $REASON_KIND cannot satisfy the network leg"
  else no "refusal reason control: $REASON_KIND satisfied the network leg [$REASON_PROBE]"; fi
done
unset FENCE_REASON_PLANT
FENCE="$REASON_CHECKER"
# >>> batch 9 fold legs: indirect network inputs, client writes, check-1 pins
cat > "$F/fold-tests.py" <<'FOLD_CLIENT_TEST_END'
import hashlib
import importlib.util
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

source, fixture = map(Path, sys.argv[1:])
ro = fixture / 'fold-ro'
ro.mkdir()
checker = ro / 'lane-fence.py'
shutil.copyfile(source, checker)
readable, writable = ro / 'readable', ro / 'writable'
readable.mkdir()
writable.mkdir()
(readable / 'f.md').write_text('sentinel\n')
(readable / 'settings').write_text('url = https://ungranted.example.invalid/\n')
(writable / 'out-link').symlink_to(readable / 'f.md')
spec = importlib.util.spec_from_file_location('fold_fence', checker)
lf = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(lf)
except Exception as exc:
    print('PROBE FAILED: fold checker could not be imported: ' + str(exc))
    sys.exit(2)
if lf.within(str(ro), lf.temp_roots()):
    print('PROBE FAILED: fold fixtures overlap implicit write permissions')
    sys.exit(2)

def manifest():
    entries = {}
    for path in sorted(ro.rglob('*')):
        if path.is_symlink():
            value = ('link', os.readlink(path))
        elif path.is_file():
            value = ('file', path.stat().st_mode, hashlib.sha256(path.read_bytes()).hexdigest())
        else:
            value = ('directory', path.stat().st_mode)
        entries[str(path.relative_to(ro))] = value
    return entries

for path in ro.rglob('*'):
    if not path.is_symlink():
        path.chmod(0o555 if path.is_dir() else 0o444)
ro.chmod(0o555)
before = manifest()
passed = failed = 0
groups = {}

def result(group, label, good, detail=''):
    global passed, failed
    counts = groups.setdefault(group, [0, 0])
    counts[0 if good else 1] += 1
    if good:
        passed += 1
        print('  ok   — ' + group + ': ' + label)
    else:
        failed += 1
        print('FAIL   — ' + group + ': ' + label + ' [' + detail + ']')

q = lambda value: shlex.quote(str(value))
host = 'allowed.example.invalid'
url = 'https://' + host + '/f.md'

def case(group, label, command, allow=False, reason=None, cwd=readable, writes=None, roles=(False, True), operand=None):
    writes = [str(writable)] if writes is None else list(map(str, writes))
    original = os.getcwd()
    try:
        os.chdir(cwd)
        for head in roles:
            wanted = ('silent' if head else 'allow') if allow else 'deny'
            try:
                decision, why = lf.check({'tool_name': 'Bash', 'tool_input': {'command': command}},
                                         [str(ro)], writes, head=head, network=[host])
            except Exception as exc:
                decision, why = 'exception', repr(exc)
            result(group, ('head ' if head else 'lane ') + label,
                   decision == wanted and (reason is None or reason in why) and (operand is None or operand in why), repr((decision, why)))
    finally:
        os.chdir(original)

# Fold 1: the same grant and visible URL accompany every opaque input, so denial must name
# unresolvability, not an absent network grant or an unrelated read/write failure.
for client, options in [('curl', ['-K', '--config', '--alt-svc']),
                        ('wget', ['-i', '--input-file', '--config', '-e', '--execute'])]:
    for option in options:
        value = str(readable / 'settings')
        forms = [option + ' ' + q(value), option + ('=' if option.startswith('--') else '') + q(value)]
        if not option.startswith('--'):
            forms.append(('-s' if client == 'curl' else '-q') + option[1:] + q(value))
        for form in forms:
            case('fold-1', client + ' refuses ' + form, client + ' ' + form + ' ' + url,
                 reason='denied as unresolvable', cwd=writable)
case('fold-1', 'configuration alone remains unresolvable', 'curl -K ' + q(readable / 'settings'),
     reason='denied as unresolvable')
case('fold-1', 'configuration in an interpreter payload is refused',
     'sh -c ' + q('curl --config ' + q(readable / 'settings') + ' ' + url),
     reason='denied as unresolvable')
case('fold-1', 'literal output stays usable', 'curl -o x.md ' + url, True, cwd=writable)
case('fold-1', 'option-shaped header is data', 'curl -H --config ' + url, True)
case('fold-1', 'joined user-agent is data', 'curl --user-agent=--config ' + url, True)
case('fold-1', 'wget user-agent is data', 'wget -U --execute ' + url, True, cwd=writable)

# Fold 2: every explicit target sits inside READ scope; the denied path lacks only WRITE scope.
# The cwd is writable here so wget's implicit download cannot mask the named-output check.
file_options = {
    'curl': ['-o', '--output', '--output-dir', '-D', '--dump-header', '-c', '--cookie-jar',
             '--trace', '--trace-ascii', '--stderr', '--libcurl', '--etag-save', '--hsts'],
    'wget': ['-O', '--output-document', '-o', '--output-file', '-a', '--append-output',
             '-P', '--directory-prefix', '--save-cookies', '--hsts-file', '--rejected-log', '--warc-file'],
}
for client, options in file_options.items():
    for option in options:
        for joined in (False, True):
            for root, allow in ((readable, False), (writable, True)):
                target = root / 'x.md'
                separator = ('=' if option.startswith('--') else '') if joined else ' '
                form = option + separator + q(target)
                case('fold-2', client + ' ' + form, client + ' ' + form + ' ' + url, allow,
                     reason=None if allow else 'outside the write whitelist', cwd=writable)

for client, form in [('curl', '-sSo'), ('wget', '-qO')]:
    for root, allow in ((readable, False), (writable, True)):
        # Glued cluster values exercise write parsing without changing the old host-skip rule.
        case('fold-2', client + ' glued cluster in ' + root.name,
             client + ' ' + form + q(root / 'x.md') + ' ' + url, allow,
             reason=None if allow else 'outside the write whitelist', cwd=writable)
for client, option in [('curl', '-o'), ('curl', '--output'), ('wget', '-O'), ('wget', '--output-document')]:
    case('fold-2', client + ' standard output ' + option, client + ' ' + option + ' - ' + url,
         True, writes=[])
case('fold-2', 'curl without output options is unchanged', 'curl -s ' + url, True, writes=[])
case('fold-2', 'relative output without a write grant denies', 'curl -o x.md ' + url,
     reason='no write grant', writes=[])
case('fold-2', 'relative output in a writable cwd clears', 'curl -o x.md ' + url, True, cwd=writable)
case('fold-2', 'relative output after a granted leading cd clears',
     'cd ' + q(writable) + ' && curl -o x.md ' + url, True)
case('fold-2', 'relative output cannot climb out after cd',
     'cd ' + q(writable) + ' && curl -o ../readable/x.md ' + url, reason='outside the write whitelist')
case('fold-2', 'symlink output is checked by destination',
     'curl -o ' + q(writable / 'out-link') + ' ' + url, reason='outside the write whitelist')
case('fold-2', 'dynamic output is unresolvable', 'curl -o "$OUTPUT" ' + url,
     reason='carries a variable or a substitution')
case('fold-2', 'missing output value is unresolvable', 'curl ' + url + ' --output',
     reason='denied as unresolvable')
case('fold-2', 'URL-glob output capture is unresolvable', 'curl -o ' + q(writable / '#1.md') + ' ' + url,
     reason='denied as unresolvable')
case('fold-2', 'computed WARC prefix is unresolvable', 'wget --warc-file "$NAME" ' + url,
     reason='denied as unresolvable', cwd=writable)
case('fold-2', 'quoted spaced output clears', 'curl --output=' + q(writable / 'a space.md') + ' ' + url, True)
case('fold-2', 'quoted apostrophe output is a literal target',
     'curl --output=' + q(writable / "owner's.md") + ' ' + url, True)
case('fold-2', 'a file grant does not cover its spaced sibling',
     'curl -o ' + q(writable / 'x.md ') + ' ' + url, reason='outside the write whitelist',
     writes=[writable / 'x.md'])
case('fold-2', 'output in an interpreter payload is checked',
     'sh -c ' + q('curl -o ' + q(readable / 'x.md') + ' ' + url), reason='outside the write whitelist')

for client, flags in [('curl', '-O'), ('curl', '--remote-name'), ('curl', '--remote-name-all'), ('wget', '')]:
    for cwd, allow in ((readable, False), (writable, True)):
        case('fold-2', client + ' default name ' + flags + ' in ' + cwd.name,
             client + ' ' + flags + ' ' + url, allow,
             reason=None if allow else 'download directory', cwd=cwd)
case('fold-2', 'curl remote names use the output directory',
     'curl -O --output-dir ' + q(writable) + ' ' + url, True)
case('fold-2', 'wget default names use the directory prefix', 'wget -P ' + q(writable) + ' ' + url, True)
for separator in ('--next', '-:'):
    prefix = 'curl -O --output-dir ' + q(writable) + ' ' + url + ' ' + separator + ' -O '
    case('fold-2', 'next transfer resets its output directory: ' + separator, prefix + url,
         reason='download directory')
    case('fold-2', 'next transfer can name its own writable directory: ' + separator,
         prefix + '--output-dir ' + q(writable) + ' ' + url, True)
case('fold-2', 'wget log output does not suppress its default download',
     'wget -o ' + q(writable / 'log') + ' ' + url, reason='download directory')
case('fold-2', 'a directory named dash is still a directory',
     'curl --output-dir - -O ' + url, reason='no write grant', writes=[])
case('fold-2', 'trace standard error has no file target', 'curl --trace % ' + url, True, writes=[])
case('fold-2', 'empty HSTS cache names no file', 'curl --hsts "" ' + url, True, writes=[])
for root, allow in ((readable, False), (writable, True)):
    for append in ('', '>>'):
        form = '%output{' + append + str(root / 'x.md') + '}%{http_code}'
        case('fold-2', 'write-out ' + append + ' in ' + root.name,
             'curl --write-out ' + q(form) + ' ' + url, allow,
             reason=None if allow else 'outside the write whitelist')
for form in ('@format', '$FORMAT', '%output{%{url.host}}', '%output{}', '%output{unfinished'):
    case('fold-2', 'unresolved write-out ' + form, 'curl -w ' + q(form) + ' ' + url,
         reason='denied as unresolvable')
case('fold-2', 'ordinary write-out is standard output', 'curl -w "%{http_code}" ' + url, True, writes=[])

# Fold 3 pins existing behaviour. Heredoc DATA stays data; a command on its opening line or
# after its terminator is still checked. Only lane mode has the no-nested-spawn rule.
for tail in ('; claude -p hi', ' && claude -p hi', ' | xargs claude', '; (claude -p hi)',
             '; echo `claude -p hi`', '; echo $(claude -p hi)',
             '; claude <<EOF\nhi\nEOF\n', '; cat <<EOF\nhi\nEOF\nclaude -p hi'):
    case('fold-3', 'skipped pattern preserves ' + repr(tail), 'grep x f' + tail,
         reason='no nested spawns', roles=(False,))
case('fold-3', 'quoted program-name pattern clears', 'grep -n \'"claude"\' f', True, roles=(False,))
case('fold-3', 'heredoc data after grep stays data', 'grep x f; cat <<EOF\nclaude\nEOF\n',
     True, roles=(False,))
for command in ('awk \'BEGIN{system("claude -p hi")}\'', 'sed \'e claude -p hi\' f'):
    case('fold-3', 'search narrowing preserves program text: ' + command, command,
         reason='no nested spawns', roles=(False,))


def compose_case(label, command, allow, reason=None, operand=None, cwd=readable):
    case('F3-4', label, command, allow, reason, cwd=cwd, operand=operand)

for output in ('-o result', '--output=result', '-oresult'):
    for ordering in (0, 1):
        # Two orders derive from placing the output directory before/after the filename.
        parts = ['--output-dir ' + q(writable), output]
        if ordering:
            parts.reverse()
        compose_case(output + ' order ' + str(ordering), 'curl ' + ' '.join(parts) + ' ' + url, True)
compose_case('joined output directory', 'curl --output-dir=' + q(writable) + ' -o result ' + url, True)
compose_case('relative output directory', 'curl --output-dir writable -o result ' + url, True, cwd=ro)
compose_case('filename containing a space', 'curl --output-dir ' + q(writable) + ' -o "a space" ' + url, True)
compose_case('absolute filename remains prefixed',
     'curl --output-dir ' + q(writable) + ' -o ' + q(readable / 'absolute') + ' ' + url, True)
compose_case('last directory wins before filename',
     'curl --output-dir ' + q(writable / 'earlier') + ' --output-dir ' + q(writable) + ' -o result ' + url,
     True)
compose_case('last directory wins after filename',
     'curl --output-dir ' + q(writable / 'earlier') + ' -o result --output-dir ' + q(writable) + ' ' + url,
     True)
for separator in ('--next', '-:'):
    prefix = 'curl --output-dir ' + q(writable) + ' -o first ' + url + ' ' + separator + ' '
    compose_case('transfer reset denies relative filename ' + separator, prefix + '-o second ' + url,
         False, 'outside the write whitelist', 'second')
    compose_case('next transfer owns its directory ' + separator,
         prefix + '-o second --output-dir ' + q(writable) + ' ' + url, True)
    compose_case('second directory does not change first transfer ' + separator,
         'curl -o first ' + url + ' ' + separator + ' --output-dir ' + q(writable) + ' -o second ' + url,
         False, 'outside the write whitelist', 'first')
for name in ('../readable/escaped', '/../../readable/escaped'):
    compose_case('composed escape ' + name, 'curl --output-dir ' + q(writable) + ' -o ' + q(name) + ' ' + url,
         False, 'outside the write whitelist', name)
compose_case('relative output without directory is outside writes', 'curl -o result ' + url,
     False, 'outside the write whitelist', 'result')
compose_case('relative output in writable cwd', 'curl -o result ' + url, True, cwd=writable)
compose_case('absolute output without directory', 'curl -o ' + q(writable / 'result') + ' ' + url, True)
compose_case('absolute outside output without directory', 'curl -o ' + q(readable / 'result') + ' ' + url,
     False, 'outside the write whitelist', str(readable / 'result'))
compose_case('stdout with output directory', 'curl --output-dir ' + q(writable) + ' -o - ' + url, True)
compose_case('stdout without output directory', 'curl -o - ' + url, True)
compose_case('header output keeps its own base',
     'curl --output-dir ' + q(writable) + ' -o result -D header ' + url,
     False, 'outside the write whitelist', 'header')
compose_case('write-out target keeps its own base',
     'curl --output-dir ' + q(writable) + ' -o result -w ' + q('%output{log}') + ' ' + url,
     False, 'outside the write whitelist', 'log')
compose_case('remote name uses directory', 'curl -O --output-dir ' + q(writable) + ' ' + url, True)
compose_case('remote name without directory is outside writes', 'curl -O ' + url,
     False, 'outside the write whitelist', 'download directory')
compose_case('missing directory refuses', 'curl -o result ' + url + ' --output-dir',
     False, 'has no literal file target', '--output-dir')
compose_case('empty directory refuses', 'curl --output-dir "" -o result ' + url,
     False, 'has no literal file target', '--output-dir')
compose_case('variable directory refuses', 'curl --output-dir "$DEST" -o result ' + url,
     False, 'carries a variable or a substitution', '$DEST')

# Direct composition controls distinguish the final directory from every conservative directory
# permission check, and pin curl's absolute-filename concatenation rather than os.path.join.
for label, options, expected in (
    ('final directory is used for earlier filename',
     [('--output-dir', 'old'), ('-o', 'name'), ('--output-dir', 'new')], 'new/name'),
    ('absolute filename is prefixed', [('--output-dir', 'base'), ('-o', '/name')], 'base//name'),
):
    targets, reason = lf.network_file_targets([('curl', options)])
    result('F3-4', label, reason is None and ('curl -o', expected) in targets, repr((targets, reason)))

# Last leg: every decision above ran on a read-only copy; neither clients nor supplied commands
# ran. The manifest and the source grep each have their own positive control on this run.
after = manifest()
result('fold-controls', 'read-only checksum manifest unchanged', bool(before) and before == after,
       'entries=' + str(len(before)))
plant = dict(after)
plant['sentinel'] = ('file', 0o444, 'changed')
result('fold-controls', 'checksum positive control catches a changed entry', before != plant)
pattern = r'''open\([^)]*['"][wax]|write_(text|bytes)[ \t]*\(|\b(subprocess|Popen)\b|\bshutil\.|os\.(remove|unlink|rename|replace|mkdir|makedirs|rmdir|symlink)\b'''
for label, text, wanted in [('source has no write calls', checker.read_text(), 1),
                            ('source-grep positive control', 'open("x", "w")\n', 0)]:
    scan = subprocess.run(['grep', '-nE', pattern], input=text, text=True, capture_output=True)
    if scan.returncode not in (0, 1) or scan.stderr:
        print('PROBE FAILED: fold source grep failed: ' + scan.stderr)
        sys.exit(2)
    result('fold-controls', label, scan.returncode == wanted and bool(scan.stdout) == (wanted == 0),
           repr((scan.returncode, scan.stdout)))
for group, counts in groups.items():
    print('FOLD_GROUP', group, 'PASS', counts[0], 'FAIL', counts[1])
print('FOLD_COUNTS', passed, failed)
FOLD_CLIENT_TEST_END
FOLD_OUT=$("$PY" -B "$F/fold-tests.py" "$FENCE" "$F")
FOLD_RC=$?
printf '%s\n' "$FOLD_OUT"
[ "$FOLD_RC" = 0 ] || { echo "PROBE FAILED: fold checks exited $FOLD_RC"; exit 2; }
FOLD_COUNTS=$(printf '%s\n' "$FOLD_OUT" | tail -1)
case "$FOLD_COUNTS" in
  'FOLD_COUNTS '*) FOLD_PASS=$(printf '%s\n' "$FOLD_COUNTS" | awk '{print $2}')
                  FOLD_FAIL=$(printf '%s\n' "$FOLD_COUNTS" | awk '{print $3}') ;;
  *) echo "PROBE FAILED: fold checks omitted their counts"; exit 2 ;;
esac
PASS=$((PASS + FOLD_PASS)); FAIL=$((FAIL + FOLD_FAIL))
# <<< batch 9 fold legs
# <<< batch 9 legs

echo "== record writer: identity, literal arguments, computed targets and both roles =="
cat > "$F/record-tests.py" <<'RECORD_WRITER_TEST_END'
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

source, here, fixture = map(Path, sys.argv[1:])
ro = fixture / 'record-ro'
vault = ro / "vault's space"
delegate = vault / '.claude' / 'skills' / 'delegate'
delegate.mkdir(parents=True)
checker = delegate / 'lane-fence.py'
writer = delegate / 'vault-writes.py'
shutil.copyfile(source, checker)
shutil.copyfile(here / 'vault-writes.py', writer)
helper_source = os.environ.get('FENCE_RECORDED_HELPER')
replay_helper = None
if helper_source:
    if not Path(helper_source).is_file():
        print('PROBE FAILED: recorded replay helper is missing')
        sys.exit(2)
    replay_helper = ro / 'replay-recorded.sh'
    shutil.copyfile(helper_source, replay_helper)
log = vault / 'wiki' / 'log.md'
register = vault / 'wiki' / 'developments' / 'known-issues.md'
register.parent.mkdir(parents=True)
log.write_text('log sentinel\n')
register.write_text('## Open\n\n## Closed\n')
(vault / 'wiki' / 'index.md').write_text('index sentinel\n')
(vault / 'IDEAS.md').write_text('ideas sentinel\n')
outside = ro / 'outside'
outside.mkdir()
(outside / 'target.md').write_text('outside sentinel\n')
fake = outside / 'vault-writes.py'
fake.write_text('raise RuntimeError("must never execute")\n')
fake_python = outside / 'python3'
fake_python.symlink_to(sys.executable)
alias = ro / 'writer-alias'
alias.symlink_to(writer)
bad_alias = ro / 'bad-writer-alias'
bad_alias.symlink_to(fake)
root_alias = ro / 'root-alias'
root_alias.symlink_to(vault, target_is_directory=True)
copied = ro / 'lane-home'
copied.mkdir()
shutil.copyfile(checker, copied / checker.name)
digest = hashlib.sha256(checker.read_bytes()).hexdigest()
state = {'lane-fence.py': {'source': str(checker), 'src_sha': digest, 'out_sha': digest}}
(copied / '.lane-home-state.json').write_text(json.dumps(state))
for variant in ('missing', 'broken', 'stale', 'wrong-source'):
    home = ro / variant
    home.mkdir()
    shutil.copyfile(checker, home / checker.name)
    if variant != 'missing':
        data = json.loads(json.dumps(state))
        if variant == 'stale':
            data['lane-fence.py']['src_sha'] = 'mismatched'
        if variant == 'wrong-source':
            data['lane-fence.py']['source'] = str(fake)
        (home / '.lane-home-state.json').write_text('[' if variant == 'broken' else json.dumps(data))
for variant in ('log-link', 'register-link', 'script-link', 'missing-writer'):
    root_dir = ro / variant
    script_dir = root_dir / '.claude' / 'skills' / 'delegate'
    script_dir.mkdir(parents=True)
    shutil.copyfile(checker, script_dir / checker.name)
    if variant == 'script-link':
        (script_dir / writer.name).symlink_to(fake)
    elif variant != 'missing-writer':
        shutil.copyfile(writer, script_dir / writer.name)
    (root_dir / 'wiki' / 'developments').mkdir(parents=True)
    for name, target in [('log-link', root_dir / 'wiki' / 'log.md'),
                         ('register-link', root_dir / 'wiki' / 'developments' / 'known-issues.md')]:
        if variant == name:
            target.symlink_to(outside / 'target.md')
        else:
            target.write_text('target sentinel\n')

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

lf = load(checker, 'record_fence')
decoder = load(here / 'lane-fence.py', 'record_decoder')
writer_module = load(writer, 'record_writer_parser')
if lf.within(str(vault), lf.temp_roots()) or lf.within(os.getcwd(), [str(ro)]):
    print('PROBE FAILED: writer fixtures or checker cwd overlap implicit permissions')
    sys.exit(2)
shells = [p for p in ('/bin/sh', '/bin/zsh') if os.path.isfile(p)]
if not shells:
    print('PROBE FAILED: no shell for the literal-argument control')
    sys.exit(2)

passed = failed = 0
def check(name, condition, detail=''):
    global passed, failed
    if condition:
        passed += 1
        print('  ok   — ' + name)
    else:
        failed += 1
        print('FAIL   — ' + name + (' [' + detail + ']' if detail else ''))

# A checksum manifest of a READ-ONLY copy before and after another full admission/denial
# pass proves the checker writes nothing. Symlink destinations and directory modes are
# included; a changed sentinel is the manifest's own positive control on the same run.
def manifest(root):
    entries = {}
    for path in sorted(root.rglob('*')):
        key = str(path.relative_to(root))
        if path.is_symlink():
            entries[key] = ('link', os.readlink(path))
        elif path.is_file():
            entries[key] = ('file', path.stat().st_mode, hashlib.sha256(path.read_bytes()).hexdigest())
        else:
            entries[key] = ('directory', path.stat().st_mode)
    return entries

for path in ro.rglob('*'):
    if not path.is_symlink():
        path.chmod(0o555 if path.is_dir() or path == writer else 0o444)
ro.chmod(0o555)
before = manifest(ro)

check('writer target constants agree with the actual writer',
      writer_module.LOG_REL == os.path.join('wiki', 'log.md') and
      writer_module.REGISTER_REL == os.path.join('wiki', 'developments', 'known-issues.md'))

# The fence's closed grammar against the writer's own parser, operation by operation: a flag
# added to the writer and not here (Batch 10's required --why-not-fixed-now) would otherwise
# refuse every correct call, and a verb added there would never be admitted.
def writer_operations(parser, path=()):
    subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    if not subs:
        return {path: {s for a in parser._actions for s in a.option_strings
                       if s.startswith('--') and s not in ('--help', '--dry-run')}}
    found = {}
    for name, child in subs[0].choices.items():
        found.update(writer_operations(child, path + (name,)))
    return found
writer_ops = writer_operations(writer_module.build_parser())
check('the fence grammar names exactly the writer options, operation by operation',
      all(writer_ops.get(key) == required | optional for key, (required, optional) in lf.RECORD_OPTIONS.items()),
      repr({key: sorted(writer_ops.get(key, set()) ^ (r | o)) for key, (r, o) in lf.RECORD_OPTIONS.items()}))
check('every writer operation is admitted, but for ideas annotate, which is left out on purpose',
      set(writer_ops) - set(lf.RECORD_OPTIONS) == {('ideas', 'annotate')}, repr(sorted(set(writer_ops))))
check('each admitted operation writes the target the writer derives',
      getattr(lf, 'RECORD_TARGETS', None) == {
          'log-append': tuple(writer_module.LOG_REL.split(os.sep)),
          'register': tuple(writer_module.REGISTER_REL.split(os.sep))},
      repr(getattr(lf, 'RECORD_TARGETS', None)))

q = lambda value: shlex.quote(str(value))
prefix = 'python3 -B ' + q(writer)
root = '--vault ' + q(vault)
fields = '--action framework --title literal --changed x --conflicts none'
log_call = prefix + ' log-append ' + root + ' ' + fields
add_fields = '--date 2000-01-01 --surface x --symptom x --cause x --why-not-fixed-now x --severity minor --status open'
add_call = prefix + ' register add ' + root + ' ' + add_fields
close_call = prefix + ' register close ' + root + ' --date 2000-01-01 --match x --status closed'
annotate_call = prefix + ' register annotate ' + root + ' --match x --kind Status --note noted'
log_writes = [str(log)]
register_writes = [str(register.parent)]
all_writes = log_writes + register_writes
narrow_reads = [str(outside)]
broad_reads = [str(ro)]

def arguments_match(command):
    # Substitute a harmless printer for execution, retaining ALL original argument
    # spellings (including the original executable word). Probe each simple segment
    # on each available shell. No writer, mutator or supplied script is executed.
    segments, current = [], []
    for word in decoder.record_words(command):
        if word[0] == 'op':
            if current:
                segments.append(current)
                current = []
        else:
            if not word[4]:
                raise ValueError('a non-literal reached an admission printer')
            current.append(word)
    if current:
        segments.append(current)
    printer = q(sys.executable) + ' -B -c ' + q('import json,sys; print(json.dumps(sys.argv[1:]))')
    for segment in segments:
        raw = ' '.join(command[w[2]:w[3]] for w in segment)
        expected = [w[1] for w in segment]
        for shell in shells:
            argv = [shell] + (['-f'] if shell.endswith('zsh') else [])
            run = subprocess.run(argv + ['-c', printer + ' ' + raw], text=True, capture_output=True)
            if run.returncode or run.stderr or json.loads(run.stdout) != expected:
                return False, repr((shell, expected, run.stdout, run.stderr, run.returncode))
    return True, ''

def case(name, command, writes, allow=False, reads=None, module=None, reason=None, probe=True):
    module = module or lf
    reads = narrow_reads if reads is None else reads
    for head in (False, True):
        want = ('silent' if head else 'allow') if allow else 'deny'
        try:
            result, why = module.check({'tool_name': 'Bash', 'tool_input': {'command': command}},
                                       [module.norm(p) for p in reads],
                                       [module.norm(p) for p in writes], head=head)
        except Exception as exc:
            result, why = 'exception', repr(exc)
        check(('head' if head else 'lane') + ': ' + name,
              result == want and (reason is None or reason in why), repr((result, why)))
    if allow and probe:
        try:
            matches, detail = arguments_match(command)
        except Exception as exc:
            matches, detail = False, repr(exc)
        check('shell argv: ' + name, matches, detail)


class_three = []
def ordinary(module, command, reads, writes, head):
    # Run the same checker on the original command with only writer admission disabled.
    # The pre-fold positive-control run has no writer view to disable.
    view = getattr(module, 'record_writer_view', None)
    if view is not None:
        module.record_writer_view = lambda command, writes: (command, None)
    try:
        return module.check({'tool_name': 'Bash', 'tool_input': {'command': command}},
                            [module.norm(p) for p in reads],
                            [module.norm(p) for p in writes], head=head)
    finally:
        if view is not None:
            module.record_writer_view = view


def fallback(name, command, writes, reads=None, module=None, allow=False):
    module = module or lf
    reads = broad_reads if reads is None else reads
    class_three.append((name, command, module))
    view = getattr(module, 'record_writer_view', None)
    check('no writer exception or partial masking: ' + name,
          view is None or view(command, writes) == (command, None))
    for shape, grants in [('covered reads', reads), ('narrow reads', narrow_reads)]:
        for head in (False, True):
            expected = ordinary(module, command, grants, writes, head)
            actual = module.check({'tool_name': 'Bash', 'tool_input': {'command': command}},
                                  [module.norm(p) for p in grants],
                                  [module.norm(p) for p in writes], head=head)
            want = 'silent' if head else 'allow'
            check(('head' if head else 'lane') + ' fallback ' + shape + ': ' + name +
                  (' (must-fire)' if expected[0] == 'deny' else ' (must-not-fire)'),
                  actual == expected and 'record writer:' not in actual[1] and
                  (not allow or shape != 'covered reads' or actual[0] == want),
                  repr((actual, expected)))

# All admitted writer spellings are compared to shell-produced argv above.
case('literal Python log with only log scope', log_call, log_writes, True)
case('direct executable log', log_call.replace(prefix, q(writer), 1), log_writes, True)
case('absolute Python executable with execution read grant', log_call.replace('python3', q(sys.executable), 1),
     log_writes, True, reads=narrow_reads + [sys.executable])
case('equals root option', log_call.replace(root, '--vault=' + q(vault)), log_writes, True)
case('explicit Python zero-arity flags', log_call.replace('python3 -B', 'python3 -E -I -B --'), log_writes, True)
case('root alias resolved to deployment', log_call.replace(root, '--vault ' + q(root_alias)), log_writes, True)
case('script alias resolved to deployment', log_call.replace(q(writer), q(alias)), log_writes, True)
case('adjacent quoted root spans', log_call.replace(root, '--vault ' + q(vault.parent) + '/' + q(vault.name)), log_writes, True)
escaped_root = ''.join('\\' + ch if ch in " '\"\\" else ch for ch in str(vault))
case('unquoted escaped root characters', log_call.replace(root, '--vault ' + escaped_root), log_writes, True)
case('shell line continuation between arguments', log_call.replace(' log-append ', ' \\\nlog-append '), log_writes, True)
case('register add with temporary-directory coverage', add_call, register_writes, True)
case('register close with temporary-directory coverage', close_call, register_writes, True)
case('register annotate with temporary-directory coverage', annotate_call, register_writes, True)
case('covered preview', log_call + ' --dry-run', log_writes, True)
case('covered operation help', prefix + ' log-append ' + root + ' --help', log_writes, True)
case('covered register help', prefix + ' register close ' + root + ' --help', register_writes, True)
case('harmless appended printf', log_call + "; printf '%s' ok", log_writes, True)
case('harmless conditional printf', log_call + " && printf '%s' ok", log_writes, True)
case('harmless pipe to cat', log_call + ' | cat', log_writes, True)
case('harmless printf before writer', "printf '%s' ok; " + log_call, log_writes, True)
case('separate granted read of the script retains ordinary access', log_call + '; cat ' + q(writer), log_writes,
     True, reads=broad_reads)
case('covered sequential mutator after writer retains its checks', log_call + '; touch ' + q(outside / 'target.md'),
     log_writes + [str(outside / 'target.md')], True)
case('both eligible calls independently covered', log_call + '; ' + close_call, all_writes, True)
case('copied lane checker with init provenance', log_call, log_writes, True,
     module=load(copied / checker.name, 'copied_fence'))

prose = ["owner's \"record\"; touch /outside", r'literal\backslash', '  significant whitespace  ',
         '/outside/path-looking-description', '$HOME and $(literal) and `literal`', 'line one\nline two',
         'braces {one,two} and a glob *?[x]']
for number, value in enumerate(prose):
    command = log_call.replace('--title literal', '--title ' + q(value))
    case('literal prose ' + str(number + 1), command, log_writes, True)
escaped_title = r'''"owner's \"record\"; touch /outside"'''
case('double-quoted escaped quotation', log_call.replace('--title literal', '--title ' + escaped_title), log_writes, True)
case('double-quoted literal dollar and backslash',
     log_call.replace('--title literal', r'--title "\$literal \\ literal\q"'), log_writes, True)
case('path-looking typed changed value', log_call.replace('--changed x', '--changed /outside/description'), log_writes, True)
case('repeatable extras and equals prose', log_call + ' --extra=A:one --extra ' + q('B: /outside'), log_writes, True)

# A value may open with '- ' under every admitted operation, in the separate and the equals form:
# no option string holds a space, so argparse reads such a word as a value (the writer's own parser
# is asked below). Plain values stay admitted; -x and --x in a value position still refuse.
import contextlib
import io
import re
for label, call, option, plain, dashed, writes in [
        ('register annotate', annotate_call, '--note', 'noted', '- reproduced twice', register_writes),
        ('register add', add_call, '--symptom', 'x', '- fails on a second run', register_writes),
        ('log-append', log_call, '--changed', 'x', '- the register entry', log_writes)]:
    pattern = ' ' + re.escape(option + ' ' + plain) + '(?= |$)'
    if len(re.findall(pattern, call)) != 1:
        print('PROBE FAILED: the dash-led value legs need ' + repr(option + ' ' + plain) + ' once in the '
              + label + ' call')
        sys.exit(2)
    for kind, value in [('plain', plain), ('dash-led', dashed)]:
        for form, spelled in [('separate', ' ' + option + ' ' + q(value)), ('equals', ' ' + option + '=' + q(value))]:
            name = label + ' ' + option + ', ' + kind + ' value, ' + form + ' form'
            command = re.sub(pattern, lambda match: spelled, call)
            case(name, command, writes, True)
            if kind == 'dash-led':
                errors = io.StringIO()
                try:
                    with contextlib.redirect_stderr(errors):
                        parsed = writer_module.build_parser().parse_args(shlex.split(command)[3:])
                    read = getattr(parsed, option[2:].replace('-', '_'), None)
                except SystemExit as exc:
                    read = 'exit ' + repr(exc.code) + ': ' + errors.getvalue().strip()[-160:]
                check('the writer parser reads the value: ' + name, read == value, repr(read))
    for shape in ('-x', '--x'):
        fallback(label + ' ' + option + ' ' + shape + ' in a value position is never a value',
                 re.sub(pattern, lambda match: ' ' + option + ' ' + shape, call), writes)
fallback('a dash-led word in an option position is still no option', log_call + ' ' + q('- stray'), log_writes)

for title, writes in [('no writes', []), ('unrelated write', [str(vault / 'wiki' / 'index.md')])]:
    for form in (root, '--vault=' + q(vault)):
        case(title + ' with readable script/root and ' + form.split()[0], log_call.replace(root, form),
             writes, reads=broad_reads, reason='record-writer target outside')
    case(title + ' preview', log_call + ' --dry-run', writes, reads=broad_reads)
    case(title + ' help', prefix + ' log-append ' + root + ' --help', writes, reads=broad_reads)
fallback('top-level help has no covered operation', prefix + ' --help', [], allow=True)
fallback('grep of the writer file is data', 'grep -n LOG_REL ' + q(writer), [], allow=True)
fallback('sed of the writer file is data', "sed -n '1p' " + q(writer), [], allow=True)
fallback('head of the writer file is data', 'head -n 1 ' + q(writer), [], allow=True)
fallback('head ideas annotate with its file write grant', prefix + ' ideas annotate --file ' +
         q(vault / 'IDEAS.md') + ' --item 1 --note x', [str(vault / 'IDEAS.md')], allow=True)
case('register file alone cannot cover temporary sibling', add_call, [str(register)], reads=broad_reads,
     reason='temporary-file directory')
fallback('register add without its required reason', add_call.replace(' --why-not-fixed-now x', ''),
         register_writes)
case('one guessed temporary filename cannot cover siblings', close_call,
     [str(register), str(register.parent / '.vault-writes-fixed.tmp')], reads=broad_reads,
     reason='temporary-file directory')
case('second writer target is independently checked', log_call + '; ' + close_call, log_writes, reads=broad_reads)

for label, replacement in [
    ('duplicate separated', root + ' ' + root),
    ('duplicate mixed', root + ' --vault=' + q(outside)),
    ('duplicate reverse order', '--vault=' + q(outside) + ' ' + root),
    ('abbreviated separated', '--va ' + q(vault)),
    ('abbreviated equals', '--va=' + q(vault)),
    ('empty root', "--vault ''"),
    ('trailing root whitespace', '--vault ' + q(str(vault) + ' ')),
    ('unquoted root carriage return is significant', root + '\r'),
    ('dynamic root', '--vault "$V"'),
    ('relative root', '--vault .'),
    ('different readable root', '--vault ' + q(outside)),
    ('missing root value', '--vault')]:
    fallback(label, log_call.replace(root, replacement), log_writes)
fallback('unknown writer option', log_call + ' --mystery x', log_writes)
fallback('missing required field', log_call.replace('--title literal', ''), log_writes)
fallback('a value opening with a dash and no space is never a value', log_call.replace('--title literal', '--title -x'),
         log_writes)
fallback('a value opening with a double dash is never a value', log_call.replace('--title literal', '--title --x'),
         log_writes)
fallback('duplicate scalar field', log_call + ' --title repeated', log_writes)
fallback('wrong subcommand', log_call.replace('log-append', 'log-replace'), all_writes)
fallback('ideas never gains record authority', prefix + ' ideas annotate --file ' + q(vault / 'IDEAS.md') +
     ' --item 1 --note x', all_writes, reads=broad_reads)

for label, replacement in [
    ('counterfeit writer', q(fake)), ('outward script alias', q(bad_alias)),
    ('single-quoted backslash retained in script name', q(str(writer).replace('vault-writes', r'vault\-writes'))),
    ('script trailing whitespace retained', q(str(writer) + ' '))]:
    fallback(label, log_call.replace(q(writer), replacement), log_writes)
fallback('counterfeit interpreter', log_call.replace('python3', q(fake_python), 1), log_writes)
# Condition 2: substitute each executable/script position while keeping its target
# readable and the log writable. Only the checker sees these command strings.
substituted_writer = q(writer.parent) + '/"$(printf %s ' + writer.name + ')"'
for label, command in [
    ('condition 2 substituted script operand', log_call.replace(q(writer), substituted_writer, 1)),
    ('condition 2 substituted direct writer programme', log_call.replace(prefix, substituted_writer, 1)),
    ('condition 2 substituted interpreter programme', log_call.replace('python3', '"$(printf %s python3)"', 1))]:
    fallback(label, command, log_writes)
fallback('Python -c camouflage', log_call.replace('python3 -B', 'python3 -c'), log_writes)
fallback('Python -m camouflage', log_call.replace('python3 -B', 'python3 -m'), log_writes)
fallback('Python value-option camouflage', log_call.replace('python3 -B', 'python3 -W'), log_writes)
fallback('unmodelled Python switch', log_call.replace('python3 -B', 'python3 -X dev'), log_writes)
fallback('env wrapper', 'env ' + log_call, log_writes)
fallback('command wrapper', 'command ' + log_call, log_writes)
fallback('leading assignment', 'FLAG=x ' + log_call, log_writes)
fallback('preceding PATH assignment', 'PATH=/outside; ' + log_call, log_writes)
fallback('preceding printf variable assignment', "printf -v PATH '%s' /outside; " + log_call, log_writes)
link_change = 'ln -sf ' + q(outside / 'target.md') + ' ' + q(log)
fallback('covered mutator before writer confers no exception', link_change + '; ' + log_call, log_writes)
fallback('covered pipeline mutator confers no exception', log_call + ' | ' + link_change, log_writes)
for variant in ('missing', 'broken', 'stale', 'wrong-source'):
    fallback('copied deployment ' + variant, log_call, log_writes,
             module=load(ro / variant / checker.name, 'fence_' + variant))
for variant in ('log-link', 'register-link', 'script-link', 'missing-writer'):
    root_dir = ro / variant
    script_dir = root_dir / '.claude' / 'skills' / 'delegate'
    original = add_call if variant == 'register-link' else log_call
    command = original.replace(q(writer), q(script_dir / writer.name)).replace(q(vault), q(root_dir))
    if variant in ('script-link', 'missing-writer'):
        fallback('symlink/premise control ' + variant, command, [str(root_dir / 'wiki')],
                 module=load(script_dir / checker.name, 'fence_' + variant))
    else:
        case('symlink/premise control ' + variant, command, [str(root_dir / 'wiki')], reads=broad_reads,
             module=load(script_dir / checker.name, 'fence_' + variant), reason='record-writer target outside')

for label, tail in [
    ('appended same-root read still checked', '; ls ' + q(vault)),
    ('appended same-script read still checked', '; cat ' + q(writer)),
    ('appended semicolon write', '; touch ' + q(outside / 'target.md')),
    ('appended conditional write', ' && touch ' + q(outside / 'target.md')),
    ('pipe into uncovered tee', ' | tee ' + q(outside / 'target.md')),
    ('output redirection', ' > ' + q(outside / 'target.md')),
    ('input redirection', ' < ' + q(outside / 'target.md')),
    ('network companion', ' ; curl https://ungranted.invalid/')]:
    if label in ('pipe into uncovered tee', 'output redirection', 'input redirection'):
        fallback(label, log_call + tail, log_writes)
    else:
        case(label, log_call + tail, log_writes, reads=narrow_reads)
for label, title in [
    ('double-quoted command substitution', '"$(touch ' + q(outside / 'target.md') + ')"'),
    ('backtick substitution', '"`touch ' + q(outside / 'target.md') + '`"'),
    ('parameter expansion', '"${VALUE:-x}"'),
    ('arithmetic expansion', '"$((1+1))"'),
    ('unquoted glob', '*'), ('ANSI-C quoting', "$'literal'"),
    ('unterminated quote', "'unfinished")]:
    fallback(label, log_call.replace('--title literal', '--title ' + title), log_writes)
fallback('subshell', '(' + log_call + ')', log_writes)
fallback('background operator', log_call + ' &', log_writes)
fallback('unfinished pipeline', log_call + ' |', log_writes)
fallback('NUL in literal writer argument', log_call + " --extra 'A:\x00'", log_writes)
case('non-string hook command', ['writer'], log_writes, reads=broad_reads)
for malformed in (None, False, 0, [], {}):
    case('empty non-string hook command ' + repr(malformed), malformed, log_writes, reads=broad_reads)
fallback('writer with unquoted heredoc substitution', log_call + '\ncat <<END\n$(touch ' +
     q(outside / 'target.md') + ')\nEND', log_writes, reads=broad_reads)
fallback('writer decoy in heredoc grants no following read', "cat <<'END'\n" + log_call +
     '\nEND\nls ' + q(vault), log_writes)
fallback('writer decoy in heredoc grants no following write', "cat <<'END'\n" + log_call +
     '\nEND\ntouch ' + q(outside / 'target.md'), log_writes, reads=broad_reads)
# This ordinary quoted heredoc is data under the existing rule; its shell printer
# is cat itself, fed a known literal sentinel, never the planted writer command.
heredoc = "cat <<'END'\n" + log_call + '\nEND'
fallback('ordinary quoted heredoc keeps ordinary handling', heredoc, [], allow=True)
run = subprocess.run(['/bin/sh', '-c', heredoc], text=True, capture_output=True)
check('shell data: ordinary quoted heredoc', run.returncode == 0 and run.stdout == log_call + '\n' and not run.stderr)

# A failure anywhere cancels both earlier masking and a pending missing-grant denial.
unsupported = prefix + ' --help'
for label, command in [
    ('eligible then unsupported writer', log_call + '; ' + unsupported),
    ('unsupported then eligible writer', unsupported + '; ' + log_call),
    ('eligible then writer file as grep data', log_call + '; grep LOG_REL ' + q(writer)),
    ('unsupported companion command', log_call + '; true')]:
    fallback(label, command, log_writes)
for label, command in [('missing grant then unsupported writer', log_call + '; ' + unsupported),
                       ('unsupported writer then missing grant', unsupported + '; ' + log_call)]:
    fallback(label, command, [])

for label, command, writes in [('target', log_call, []),
                               ('temporary directory', add_call, [str(register)]),
                               ('grammar', unsupported, [])]:
    try:
        # Production passes real paths (record_deployment, roots_from); so does this leg.
        lf.record_arguments(lf.record_words(command), 2, lf.norm(str(vault)), [lf.norm(w) for w in writes])
    except Exception as exc:
        error_type = getattr(lf, 'RecordWriterGrantError', None)
        check('distinct writer grant exception: ' + label,
              error_type is not None and isinstance(exc, ValueError) and
              isinstance(exc, error_type) == (label != 'grammar'), type(exc).__name__)
    else:
        check('distinct writer grant exception: ' + label, False, 'no exception')

# Option B: no variable-write or variable-program admission is added. A variable read
# remains allowed; all plan counterexamples still refuse on their existing write side.
variable_read = 'S=' + q(outside) + '; cat "$S/target.md"'
case('existing variable-read control', variable_read, [], True, reads=broad_reads, probe=False)
run = subprocess.run(['/bin/sh', '-c', 'S=' + q(outside) + '; printf \'%s\' "$S/target.md"'], text=True, capture_output=True)
check('shell argv: existing variable-read control', run.returncode == 0 and run.stdout == str(outside / 'target.md'))
variable_cases = [
    'false && S=/tmp; rm "$S/x"', '(S=/tmp); rm "$S/x"', "S=/tmp; rm '$S/x'",
    'S=/tmp; typeset -L1 S; rm "$S/x"', 'S=/tmp; printf -v S /outside; rm "$S/x"',
    'S=/tmp /usr/bin/true; export S; rm "$S/x"', 'S=\'\'; rm "${S:-/outside}/x"',
    'S=(/tmp); rm "$S/x"', 'for S in /tmp; do rm "$S/x"; done',
    'f(){ S=/tmp; }; f; rm "$S/x"', "cat <<'END'\nS=/tmp\nEND\nrm \"$S/x\"",
    'REF=S; S=/tmp; rm "${(P)REF}/x"', 'S=/tmp; rm ${~S}/x',
    'S=/outside; rm "$S/x"', 'rm "$S/x"; S=/tmp',
]
for number, command in enumerate(variable_cases):
    case('option B counterexample ' + str(number + 1), command, log_writes, reads=broad_reads)
# The short variable-program shape alone already clears the old checker. A truncated
# event cannot establish which unseen operand caused its recorded refusal. Preserve
# this measured limitation under option B rather than inventing a new variable rule.
variable_program = 'S=/outside; /bin/sh $S/hs decision --run fixture'
case('existing variable-program residue unchanged', variable_program, log_writes, True,
     reads=broad_reads, probe=False)
printer = q(sys.executable) + ' -B -c ' + q('import json,sys; print(json.dumps(sys.argv[1:]))')
run = subprocess.run(['/bin/sh', '-c', 'S=/outside; ' + printer + ' /bin/sh $S/hs decision --run fixture'],
                     text=True, capture_output=True)
check('shell argv: existing variable-program residue', run.returncode == 0 and not run.stderr and
      json.loads(run.stdout) == ['/bin/sh', '/outside/hs', 'decision', '--run', 'fixture'])

# Actual CLI and head-hook integration. Both stores and every logged denial are fixtures.
state_dir = fixture / 'record-state'
store = state_dir / 'store'
(store / 'spawn-records').mkdir(parents=True)
grant_file = store / 'spawn-records' / 'fixture-grants.json'
grant_file.write_text(json.dumps({'grants': broad_reads, 'writes': log_writes}))
hook = here.parent.parent / 'hooks' / 'head-fence.py'
environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', LLM_WIKI_LANE_GRANTS=os.pathsep.join(broad_reads),
                   LLM_WIKI_LANE_WRITES=os.pathsep.join(log_writes), LLM_WIKI_LANE_NETWORK='',
                   LLM_WIKI_FENCE_ROLE='', LLM_WIKI_STORE=str(store), AIMYTH_STATE_DIR=str(state_dir),
                   CLAUDE_PROJECT_DIR=str(vault), AIMYTH_HANDSOFF='1', AIMYTH_HANDSOFF_RUN='fixture')
fallback('malformed CLI command', log_call + " '", log_writes)
for label, command, want in [('covered', log_call, 'allow'), ('uncovered', add_call, 'deny'),
                              ('malformed', log_call + " '", None)]:
    event = json.dumps({'session_id': 'fixture', 'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
                        'tool_input': {'command': command}})
    for role, script, tail in [('lane CLI', checker, []), ('head CLI', checker, ['--head']), ('head hook', hook, [])]:
        run = subprocess.run([sys.executable, '-B', str(script)] + tail, input=event, text=True,
                             capture_output=True, env=environment)
        decision = 'silent' if not run.stdout else json.loads(run.stdout)['hookSpecificOutput']['permissionDecision']
        expected = 'silent' if want == 'allow' and role != 'lane CLI' else want
        if want is None:
            expected = ordinary(lf, command, broad_reads, log_writes, role != 'lane CLI')[0]
        check(role + ': ' + label, run.returncode == 0 and not run.stderr and decision == expected,
              repr((run.returncode, decision, run.stderr)))

# Include the saved writer regression shape as well as every fallback call above.
# Its expected replay decisions stay unchanged; the command is only checked, never run.
for record in json.loads((fixture / 'replay' / 'replay.json').read_text()):
    if writer.name in record['full']:
        fallback('saved writer regression ' + record['ts'], record['full'], log_writes)

pristine_path = os.environ.get('FENCE_PRISTINE')
if pristine_path:
    if not Path(pristine_path).is_file():
        print('PROBE FAILED: FENCE_PRISTINE is not a checker file')
        sys.exit(2)
    pristine = load(Path(pristine_path), 'pre_fold_fence')
    shapes = [('head', broad_reads, [str(vault / 'IDEAS.md')], True),
              ('whole-vault read and one write folder', [str(vault)], register_writes, False),
              ('lane without writes', [str(vault)], [], False)]
    comparisons, mismatches = 0, []
    for name, command, module in class_three:
        for shape, reads, writes, head in shapes:
            event = {'tool_name': 'Bash', 'tool_input': {'command': command}}
            actual = module.check(event, [module.norm(p) for p in reads],
                                  [module.norm(p) for p in writes], head=head)
            expected = pristine.check(event, [pristine.norm(p) for p in reads],
                                      [pristine.norm(p) for p in writes], head=head)
            comparisons += 1
            if actual != expected:
                mismatches.append((name, shape, actual, expected))
    check('class-3 differential matches the pre-fold checker',
          bool(class_three) and comparisons == len(class_three) * len(shapes) and not mismatches,
          repr(mismatches))
    print('DIFFERENTIAL %d commands x %d grant shapes = %d decisions; %d mismatches' %
          (len(class_three), len(shapes), comparisons, len(mismatches)))
    # The ordinary comparison must detect the missing admission on the pre-fold checker.
    control_event = {'tool_name': 'Bash', 'tool_input': {'command': log_call}}
    control_reads = [lf.norm(p) for p in narrow_reads]
    control_writes = [lf.norm(p) for p in log_writes]
    control_candidate = lf.check(control_event, control_reads, control_writes)
    control_pristine = pristine.check(control_event, control_reads, control_writes)
    check('differential positive control detects admitted log exception',
          control_candidate[0] == 'allow' and control_pristine[0] == 'deny',
          repr((control_candidate, control_pristine)))
else:
    print('SKIP class-3 differential: FENCE_PRISTINE is not set (%d commands collected)' % len(class_three))

case('read-only copy admitted control', log_call, log_writes, True)
case('read-only copy uncovered control', add_call, log_writes, reads=broad_reads)
if replay_helper:
    # Pass saved commands on stdin so the shipped helper contains no private record.
    # Every invocation imports a checker; none executes the supplied shell command.
    def replay_run(text=log_call + '\n', writes=log_writes, head=False, args=None, omit=None, reads=narrow_reads):
        env = dict(environment, LLM_WIKI_LANE_GRANTS=os.pathsep.join(reads),
                   LLM_WIKI_LANE_WRITES=os.pathsep.join(writes),
                   LLM_WIKI_FENCE_ROLE='head' if head else '')
        if omit:
            env.pop(omit)
        return subprocess.run(['/bin/sh', str(replay_helper)] +
                              (list(map(str, args)) if args is not None else [str(checker), str(vault)]),
                              input=text, text=True, capture_output=True, env=env)

    for label, text, writes, head, want in [
        ('covered lane', log_call + '\n', log_writes, False, 'allow'),
        ('covered head', log_call + '\n', log_writes, True, 'silent'),
        ('uncovered target', log_call + '\n', [], False, 'deny'),
        ('saved shell-file preamble', '#!/bin/sh\n# Recorded command\n\n' + log_call + '\n', log_writes, False, 'allow')]:
        run = replay_run(text, writes, head)
        try:
            result = json.loads(run.stdout.removeprefix('REPLAY '))
        except ValueError:
            result = {}
        check('recorded replay: ' + label, run.returncode == 0 and not run.stderr and
              result.get('decision') == want and
              result.get('command_sha256') == hashlib.sha256(log_call.encode('utf-8')).hexdigest(),
              repr((run.returncode, run.stdout, run.stderr)))

    for label, options in [
        ('missing arguments', {'args': []}),
        ('missing checker', {'args': [ro / 'absent.py', vault]}),
        ('wrong checker type', {'args': [outside, vault]}),
        ('missing vault', {'args': [checker, ro / 'absent']}),
        ('missing grants environment', {'omit': 'LLM_WIKI_LANE_GRANTS'}),
        ('empty read grants', {'reads': []}),
        ('missing writes environment', {'omit': 'LLM_WIKI_LANE_WRITES'}),
        ('no recorded command', {'text': '# comment only\n'}),
        ('two recorded commands', {'text': log_call + '\n' + log_call + '\n'}),
        ('malformed shell quotation', {'text': log_call + " '\n"}),
        ('different writer root', {'args': [checker, outside]}),
        ('different root argument', {'text': log_call.replace(root, '--vault ' + q(outside))}),
        ('different operation', {'text': add_call}),
        ('unimportable checker', {'args': [log, vault]}),
        ('checker import failure', {'args': [fake, vault]})]:
        run = replay_run(**options)
        check('recorded replay premise: ' + label,
              run.returncode == 2 and run.stdout.startswith('PROBE FAILED: ') and not run.stderr,
              repr((run.returncode, run.stdout, run.stderr)))

    # Source grep has its own planted control; the read-only manifest below covers
    # the helper and the vault sentinels across every admitted/refused replay above.
    write_pattern = (r'''open\([^)]*['"][wax]|write_(text|bytes)[ \t]*\(|'''
                     r'\.(unlink|rename|replace|mkdir|rmdir|touch|symlink_to|chmod)[ \t]*\(|'
                     r'\b(subprocess|Popen|shutil)\b|os\.(system|popen|remove|unlink|rename|replace|mkdir|makedirs|rmdir|symlink)\b|'
                     r'\b(eval|exec)[ \t]*\(|^[ \t]*(rm|mv|cp|touch|mkdir|tee)[ \t]').replace(r'\t', '\t')
    # grep returns 1 for no match and 0 for the planted match; any scan error fails.
    for label, source_text, want in [
        ('no write or command-execution patterns', replay_helper.read_text(), 1),
        ('write-pattern positive control', 'open("x", "w")\n', 0)]:
        scan = subprocess.run(['grep', '-nE', write_pattern], input=source_text, text=True, capture_output=True)
        check('recorded replay source: ' + label,
              scan.returncode == want and not scan.stderr and bool(scan.stdout) == (want == 0),
              repr((scan.returncode, scan.stdout, scan.stderr)))
else:
    print('  note — no FENCE_RECORDED_HELPER given: recorded replay helper controls were not run')
after = manifest(ro)
check('read-only copy checksum manifest unchanged', bool(before) and before == after,
      'entries=' + str(len(before)))
planted = dict(after)
planted['sentinel'] = ('file', 0o444, 'different')
check('checksum manifest positive control detects a changed entry', before != planted)
print('RECORD_COUNTS', passed, failed)
RECORD_WRITER_TEST_END
RECORD_OUT=$("$PY" -B "$F/record-tests.py" "$FENCE" "$HERE" "$F")
RECORD_RC=$?
printf '%s\n' "$RECORD_OUT"
[ "$RECORD_RC" = 0 ] || { echo "PROBE FAILED: writer matrix exited $RECORD_RC"; exit 2; }
RECORD_COUNTS=$(printf '%s\n' "$RECORD_OUT" | tail -1)
case "$RECORD_COUNTS" in
  'RECORD_COUNTS '*) RECORD_PASS=$(printf '%s\n' "$RECORD_COUNTS" | awk '{print $2}')
                    RECORD_FAIL=$(printf '%s\n' "$RECORD_COUNTS" | awk '{print $3}') ;;
  *) echo "PROBE FAILED: writer matrix omitted its counts"; exit 2 ;;
esac
PASS=$((PASS + RECORD_PASS)); FAIL=$((FAIL + RECORD_FAIL))

# SSH_MATRIX_BEGIN
# Decision probes only: none of the shell commands in this matrix is executed.
# Labels are measured against the immutable checker captured before this repair.
cat > "$F/ssh-tests.py" <<'SSH_FAMILY_TEST_END'
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

source, fixture = map(Path, sys.argv[1:])
ro = fixture / 'ssh-ro'
ro.mkdir()
checker = ro / 'lane-fence.py'
shutil.copyfile(source, checker)
readable, writable, outside, working = [ro / name for name in ('readable', 'writable', 'outside', 'cwd')]
for directory in (readable, writable, outside, working):
    directory.mkdir()
for directory in (readable, outside):
    (directory / 'input.txt').write_text('sentinel\n')
(readable / 'identity').write_text('fixture key, never used\n')
(readable / 'known_hosts').write_text('fixture hosts, never used\n')
(readable / 'config').write_text('ProxyCommand false\n')
(writable / 'link.txt').symlink_to(readable / 'input.txt')

def manifest():
    entries = {}
    for path in sorted(ro.rglob('*')):
        if path.is_symlink():
            value = ('link', os.readlink(path))
        elif path.is_file():
            value = ('file', path.stat().st_mode, hashlib.sha256(path.read_bytes()).hexdigest())
        else:
            value = ('directory', path.stat().st_mode)
        entries[str(path.relative_to(ro))] = value
    return entries

for path in ro.rglob('*'):
    if not path.is_symlink():
        path.chmod(0o555 if path.is_dir() else 0o444)
ro.chmod(0o555)
before = manifest()
spec = importlib.util.spec_from_file_location('ssh_fence', checker)
lf = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(lf)
except Exception as exc:
    print('PROBE FAILED: SSH checker could not be imported: ' + str(exc))
    sys.exit(2)
if lf.within(str(ro), lf.temp_roots()) or lf.within(str(working), [str(writable)]):
    print('PROBE FAILED: SSH fixtures overlap implicit or cwd write permissions')
    sys.exit(2)
os.chdir(working)
q = shlex.quote
R, W, U = map(str, (readable, writable, outside))
rf, wf, uf = [str(directory / 'input.txt') for directory in (readable, writable, outside)]
H, X, J, IP = ('allowed.example.invalid', 'outside.example.invalid',
                'jump.example.invalid', '2001:db8::1')
HOST = r'network|host'
READ = r'read|grant|whitelist'
WRITE = r'write|writing|writable|writability'
UNRESOLVED = r'unresolv|unsupported|missing|incomplete|ambig|cannot|unknown|local evaluation'
# Filled from measured must-pass/must-refuse outcomes on the prefold checker.
# Baseline SHA256: b2c65e29705c2a361ca22d8cd12094804028709a697f88e277a34b4c497e8872
DIFFERENTIATORS = {
    'assignment-double-head',
    'assignment-double-lane',
    'assignment-local-evaluation-head',
    'assignment-local-evaluation-lane',
    'assignment-single-head',
    'assignment-single-lane',
    'assignment-then-read-head',
    'assignment-then-read-lane',
    'bare-path-head',
    'bare-path-lane',
    'cd-append-head',
    'cd-append-lane',
    'cd-compound-head',
    'cd-compound-lane',
    'cd-missing-head',
    'cd-missing-lane',
    'cd-nonexistent-head',
    'cd-nonexistent-lane',
    'cd-overwrite-head',
    'cd-overwrite-lane',
    'cd-subshell-head',
    'cd-subshell-lane',
    'cd-tee-head',
    'cd-tee-lane',
    'cd-variable-head',
    'cd-variable-lane',
    'config-unseen-head',
    'config-unseen-lane',
    'dotted-data-head',
    'dotted-data-lane',
    'effective-host-granted-head',
    'effective-host-granted-lane',
    'email-data-head',
    'email-data-lane',
    'here-string-literal-head',
    'here-string-literal-lane',
    'here-string-substitution-head',
    'here-string-substitution-lane',
    'heredoc-local-evaluation-head',
    'heredoc-local-evaluation-lane',
    'heredoc-missing-terminator-head',
    'heredoc-missing-terminator-lane',
    'identity-client-expansion-head',
    'identity-client-expansion-lane',
    'jump-glued-ungranted-head',
    'jump-glued-ungranted-lane',
    'jump-option-glued-ungranted-head',
    'jump-option-glued-ungranted-lane',
    'jump-option-granted-head',
    'jump-option-granted-lane',
    'local-backtick-head',
    'local-backtick-lane',
    'local-process-substitution-head',
    'local-process-substitution-lane',
    'local-substitution-head',
    'local-substitution-lane',
    'missing-identity-head',
    'missing-identity-lane',
    'missing-o-value-head',
    'missing-o-value-lane',
    'missing-port-head',
    'missing-port-lane',
    'missing-scp-destination-head',
    'missing-scp-destination-lane',
    'option-known-hosts-outside-head',
    'option-known-hosts-outside-lane',
    'option-log-outside-head',
    'option-log-outside-lane',
    'option-provider-program-head',
    'option-provider-program-lane',
    'proxy-command-head',
    'proxy-command-lane',
    'remote-parent-path-head',
    'remote-parent-path-lane',
    'rsync-custom-rsh-head',
    'rsync-custom-rsh-lane',
    'rsync-daemon-missing-network-head',
    'rsync-daemon-missing-network-lane',
    'rsync-daemon-ungranted-head',
    'rsync-daemon-ungranted-lane',
    'rsync-exclude-outside-head',
    'rsync-exclude-outside-lane',
    'rsync-files-outside-head',
    'rsync-files-outside-lane',
    'rsync-include-outside-head',
    'rsync-include-outside-lane',
    'rsync-ipv6-uri-deny-head',
    'rsync-ipv6-uri-deny-lane',
    'rsync-local-readonly-head',
    'rsync-local-readonly-lane',
    'rsync-log-readonly-head',
    'rsync-log-readonly-lane',
    'rsync-password-outside-head',
    'rsync-password-outside-lane',
    'rsync-readonly-destination-head',
    'rsync-readonly-destination-lane',
    'rsync-rsh-jump-deny-head',
    'rsync-rsh-jump-deny-lane',
    'rsync-shell-wrapper-deny-head',
    'rsync-shell-wrapper-deny-lane',
    'rsync-ssh-missing-network-head',
    'rsync-ssh-missing-network-lane',
    'rsync-ssh-ungranted-head',
    'rsync-ssh-ungranted-lane',
    'rsync-unresolved-remote-head',
    'rsync-unresolved-remote-lane',
    'rsync-uri-missing-network-head',
    'rsync-uri-missing-network-lane',
    'rsync-uri-ungranted-head',
    'rsync-uri-ungranted-lane',
    'rsync-wrapper-arg0-missing-network-head',
    'rsync-wrapper-arg0-missing-network-lane',
    'rsync-wrapper-glued-missing-network-head',
    'rsync-wrapper-glued-missing-network-lane',
    'scp-download-head',
    'scp-download-lane',
    'scp-ipv6-head',
    'scp-ipv6-lane',
    'scp-ipv6-ungranted-head',
    'scp-ipv6-ungranted-lane',
    'scp-malformed-endpoint-head',
    'scp-malformed-endpoint-lane',
    'scp-readonly-destination-head',
    'scp-readonly-destination-lane',
    'scp-readonly-no-writes-head',
    'scp-readonly-no-writes-lane',
    'scp-ungranted-endpoint-head',
    'scp-ungranted-endpoint-lane',
    'scp-ungranted-source-head',
    'scp-ungranted-source-lane',
    'scp-upload-head',
    'scp-upload-lane',
    'symlink-destination-head',
    'symlink-destination-lane',
    'unknown-rsync-option-head',
    'unknown-rsync-option-lane',
    'unknown-scp-option-head',
    'unknown-scp-option-lane',
    'unknown-ssh-option-head',
    'unknown-ssh-option-lane',
    'unsupported-env-wrapper-head',
    'unsupported-env-wrapper-lane',
    'unsupported-shell-wrapper-head',
    'unsupported-shell-wrapper-lane',
    'url-data-head',
    'url-data-lane',
}
passed = failed = 0
# Review-fold labels measured against prefold-3 SHA256 804ae016fcaf4d8f8f911d8192925e0d97975c7c9fa96e1f57e0256bd40e3c7e
FOLD3_DIFFERENTIATORS = {
    'background-cd-head',
    'background-cd-lane',
    'curl-output-readonly-cd-head',
    'curl-output-readonly-cd-lane',
    'curl-remote-name-readonly-cd-head',
    'curl-remote-name-readonly-cd-lane',
    'curl-trace-readonly-cd-head',
    'curl-trace-readonly-cd-lane',
    'earlier-interpreter-keeps-writable-base-head',
    'earlier-interpreter-keeps-writable-base-lane',
    'earlier-write-keeps-writable-base-head',
    'earlier-write-keeps-writable-base-lane',
    'heredoc-client-readonly-head',
    'heredoc-client-readonly-lane',
    'heredoc-interpreter-readonly-head',
    'heredoc-interpreter-readonly-lane',
    'interpreter-readonly-cd-head',
    'interpreter-readonly-cd-lane',
    'local-write-lane',
    'mid-command-curl-head',
    'mid-command-curl-lane',
    'mid-command-interpreter-head',
    'mid-command-interpreter-lane',
    'mid-command-redirect-head',
    'mid-command-redirect-lane',
    'mid-command-rsync-head',
    'mid-command-rsync-lane',
    'mid-command-scp-head',
    'mid-command-scp-lane',
    'missing-curl-head',
    'missing-curl-lane',
    'missing-wget-head',
    'missing-wget-lane',
    'multiple-controlled-directories-head',
    'multiple-controlled-directories-lane',
    'mutator-readonly-cd-head',
    'mutator-readonly-cd-lane',
    'newline-after-skipped-cd-head',
    'newline-after-skipped-cd-lane',
    'or-curl-head',
    'or-curl-lane',
    'or-wget-head',
    'or-wget-lane',
    'parameter-all-arguments-head',
    'parameter-all-arguments-lane',
    'parameter-background-head',
    'parameter-background-lane',
    'parameter-braced-all-head',
    'parameter-braced-all-lane',
    'parameter-braced-head',
    'parameter-braced-lane',
    'parameter-braced-positional-head',
    'parameter-braced-positional-lane',
    'parameter-braced-status-head',
    'parameter-braced-status-lane',
    'parameter-count-head',
    'parameter-count-lane',
    'parameter-flags-head',
    'parameter-flags-lane',
    'parameter-host-control-head',
    'parameter-host-control-lane',
    'parameter-joined-arguments-head',
    'parameter-joined-arguments-lane',
    'parameter-joined-literal-head',
    'parameter-joined-literal-lane',
    'parameter-local-read-head',
    'parameter-local-read-lane',
    'parameter-local-write-head',
    'parameter-local-write-lane',
    'parameter-named-head',
    'parameter-named-lane',
    'parameter-option-host-head',
    'parameter-option-host-lane',
    'parameter-positional-head',
    'parameter-positional-lane',
    'parameter-process-head',
    'parameter-process-lane',
    'parameter-status-head',
    'parameter-status-lane',
    'parameter-wrapper-head',
    'parameter-wrapper-lane',
    'parameter-write-control-head',
    'parameter-write-control-lane',
    'recorded-shape-encoded-spec-head',
    'recorded-shape-encoded-spec-lane',
    'recorded-shape-escaped-status-head',
    'recorded-shape-escaped-status-lane',
    'recorded-shape-job-id-head',
    'recorded-shape-job-id-lane',
    'recorded-shape-score-ids-head',
    'recorded-shape-score-ids-lane',
    'remote-and-local-pattern-lane',
    'remote-bare-arguments-lane',
    'remote-double-quoted-lane',
    'remote-following-search-lane',
    'remote-grep-lane',
    'remote-grep-long-lane',
    'remote-grep-option-lane',
    'remote-infix-output-lane',
    'remote-parameter-head',
    'remote-parameter-lane',
    'remote-rg-lane',
    'remote-rg-quoted-lane',
    'remote-two-searches-lane',
    'separate-parameter-words-head',
    'separate-parameter-words-lane',
    'separate-read-lane',
    'sequence-curl-head',
    'sequence-curl-lane',
    'sequence-wget-head',
    'sequence-wget-lane',
    'skipped-and-cd-head',
    'skipped-and-cd-lane',
    'skipped-or-cd-head',
    'skipped-or-cd-lane',
    'stderr-pipeline-cd-head',
    'stderr-pipeline-cd-lane',
    'subshell-curl-head',
    'subshell-curl-lane',
    'subshell-wget-head',
    'subshell-wget-lane',
    'ungranted-host-lane',
    'variable-curl-head',
    'variable-curl-lane',
    'variable-wget-head',
    'variable-wget-lane',
    'wget-default-readonly-cd-head',
    'wget-default-readonly-cd-lane',
    'wget-output-readonly-cd-head',
    'wget-output-readonly-cd-lane',
}
# Measured from the immediate predecessor failures, one key per failing leg.
FOLD4_DIFFERENTIATORS = {
    'certificatefile-backslash-granted-head',
    'certificatefile-backslash-granted-lane',
    'certificatefile-backslash-outside-head',
    'certificatefile-backslash-outside-lane',
    'certificatefile-control-head',
    'certificatefile-control-lane',
    'certificatefile-equals-quoted-plain-granted-head',
    'certificatefile-equals-quoted-plain-granted-lane',
    'certificatefile-equals-quoted-plain-outside-head',
    'certificatefile-equals-quoted-plain-outside-lane',
    'certificatefile-equals-quoted-spaces-granted-head',
    'certificatefile-equals-quoted-spaces-granted-lane',
    'certificatefile-equals-quoted-spaces-outside-head',
    'certificatefile-equals-quoted-spaces-outside-lane',
    'certificatefile-extra-equals-head',
    'certificatefile-extra-equals-lane',
    'certificatefile-glob-head',
    'certificatefile-glob-lane',
    'certificatefile-malformed-quote-head',
    'certificatefile-malformed-quote-lane',
    'certificatefile-multiple-granted-head',
    'certificatefile-multiple-granted-lane',
    'certificatefile-multiple-outside-head',
    'certificatefile-multiple-outside-lane',
    'certificatefile-single-quotes-granted-head',
    'certificatefile-single-quotes-granted-lane',
    'certificatefile-single-quotes-outside-head',
    'certificatefile-single-quotes-outside-lane',
    'certificatefile-space-quoted-plain-granted-head',
    'certificatefile-space-quoted-plain-granted-lane',
    'certificatefile-space-quoted-plain-outside-head',
    'certificatefile-space-quoted-plain-outside-lane',
    'certificatefile-space-quoted-spaces-granted-head',
    'certificatefile-space-quoted-spaces-granted-lane',
    'certificatefile-space-quoted-spaces-outside-head',
    'certificatefile-space-quoted-spaces-outside-lane',
    'globalknownhostsfile-backslash-granted-head',
    'globalknownhostsfile-backslash-granted-lane',
    'globalknownhostsfile-backslash-outside-head',
    'globalknownhostsfile-backslash-outside-lane',
    'globalknownhostsfile-control-head',
    'globalknownhostsfile-control-lane',
    'globalknownhostsfile-equals-quoted-plain-granted-head',
    'globalknownhostsfile-equals-quoted-plain-granted-lane',
    'globalknownhostsfile-equals-quoted-plain-outside-head',
    'globalknownhostsfile-equals-quoted-plain-outside-lane',
    'globalknownhostsfile-equals-quoted-spaces-granted-head',
    'globalknownhostsfile-equals-quoted-spaces-granted-lane',
    'globalknownhostsfile-equals-quoted-spaces-outside-head',
    'globalknownhostsfile-equals-quoted-spaces-outside-lane',
    'globalknownhostsfile-extra-equals-head',
    'globalknownhostsfile-extra-equals-lane',
    'globalknownhostsfile-glob-head',
    'globalknownhostsfile-glob-lane',
    'globalknownhostsfile-malformed-quote-head',
    'globalknownhostsfile-malformed-quote-lane',
    'globalknownhostsfile-single-quotes-granted-head',
    'globalknownhostsfile-single-quotes-granted-lane',
    'globalknownhostsfile-single-quotes-outside-head',
    'globalknownhostsfile-single-quotes-outside-lane',
    'globalknownhostsfile-space-quoted-plain-granted-head',
    'globalknownhostsfile-space-quoted-plain-granted-lane',
    'globalknownhostsfile-space-quoted-plain-outside-head',
    'globalknownhostsfile-space-quoted-plain-outside-lane',
    'globalknownhostsfile-space-quoted-spaces-granted-head',
    'globalknownhostsfile-space-quoted-spaces-granted-lane',
    'globalknownhostsfile-space-quoted-spaces-outside-head',
    'globalknownhostsfile-space-quoted-spaces-outside-lane',
    'identityfile-backslash-granted-head',
    'identityfile-backslash-granted-lane',
    'identityfile-backslash-outside-head',
    'identityfile-backslash-outside-lane',
    'identityfile-control-head',
    'identityfile-control-lane',
    'identityfile-equals-quoted-plain-granted-head',
    'identityfile-equals-quoted-plain-granted-lane',
    'identityfile-equals-quoted-plain-outside-head',
    'identityfile-equals-quoted-plain-outside-lane',
    'identityfile-equals-quoted-spaces-granted-head',
    'identityfile-equals-quoted-spaces-granted-lane',
    'identityfile-equals-quoted-spaces-outside-head',
    'identityfile-equals-quoted-spaces-outside-lane',
    'identityfile-extra-equals-head',
    'identityfile-extra-equals-lane',
    'identityfile-glob-head',
    'identityfile-glob-lane',
    'identityfile-malformed-quote-head',
    'identityfile-malformed-quote-lane',
    'identityfile-multiple-granted-head',
    'identityfile-multiple-granted-lane',
    'identityfile-multiple-outside-head',
    'identityfile-multiple-outside-lane',
    'identityfile-single-quotes-granted-head',
    'identityfile-single-quotes-granted-lane',
    'identityfile-single-quotes-outside-head',
    'identityfile-single-quotes-outside-lane',
    'identityfile-space-quoted-plain-granted-head',
    'identityfile-space-quoted-plain-granted-lane',
    'identityfile-space-quoted-plain-outside-head',
    'identityfile-space-quoted-plain-outside-lane',
    'identityfile-space-quoted-spaces-granted-head',
    'identityfile-space-quoted-spaces-granted-lane',
    'identityfile-space-quoted-spaces-outside-head',
    'identityfile-space-quoted-spaces-outside-lane',
    'rsync-exclude-control-unresolved-head',
    'rsync-exclude-control-unresolved-lane',
    'rsync-exclude-empty-unresolved-head',
    'rsync-exclude-empty-unresolved-lane',
    'rsync-exclude-tilde-unresolved-head',
    'rsync-exclude-tilde-unresolved-lane',
    'rsync-files-colon-absolute-literal-granted-head',
    'rsync-files-colon-absolute-literal-granted-lane',
    'rsync-files-colon-absolute-literal-outside-head',
    'rsync-files-colon-absolute-literal-outside-lane',
    'rsync-files-colon-host-granted-head',
    'rsync-files-colon-host-granted-lane',
    'rsync-files-colon-host-outside-head',
    'rsync-files-colon-host-outside-lane',
    'rsync-files-control-unresolved-head',
    'rsync-files-control-unresolved-lane',
    'rsync-files-empty-unresolved-head',
    'rsync-files-empty-unresolved-lane',
    'rsync-files-tilde-unresolved-head',
    'rsync-files-tilde-unresolved-lane',
    'rsync-include-control-unresolved-head',
    'rsync-include-control-unresolved-lane',
    'rsync-include-empty-unresolved-head',
    'rsync-include-empty-unresolved-lane',
    'rsync-include-tilde-unresolved-head',
    'rsync-include-tilde-unresolved-lane',
    'rsync-log-control-unresolved-head',
    'rsync-log-control-unresolved-lane',
    'rsync-log-empty-unresolved-head',
    'rsync-log-empty-unresolved-lane',
    'rsync-log-tilde-unresolved-head',
    'rsync-log-tilde-unresolved-lane',
    'rsync-password-control-unresolved-head',
    'rsync-password-control-unresolved-lane',
    'rsync-password-empty-unresolved-head',
    'rsync-password-empty-unresolved-lane',
    'rsync-password-tilde-unresolved-head',
    'rsync-password-tilde-unresolved-lane',
    'scp-certificatefile-glued-quoted-granted-head',
    'scp-certificatefile-glued-quoted-granted-lane',
    'scp-certificatefile-glued-quoted-outside-head',
    'scp-certificatefile-glued-quoted-outside-lane',
    'scp-globalknownhostsfile-glued-quoted-granted-head',
    'scp-globalknownhostsfile-glued-quoted-granted-lane',
    'scp-globalknownhostsfile-glued-quoted-outside-head',
    'scp-globalknownhostsfile-glued-quoted-outside-lane',
    'scp-identity-control-unresolved-head',
    'scp-identity-control-unresolved-lane',
    'scp-identity-empty-unresolved-head',
    'scp-identity-empty-unresolved-lane',
    'scp-identityfile-glued-quoted-granted-head',
    'scp-identityfile-glued-quoted-granted-lane',
    'scp-identityfile-glued-quoted-outside-head',
    'scp-identityfile-glued-quoted-outside-lane',
    'scp-userknownhostsfile-glued-quoted-granted-head',
    'scp-userknownhostsfile-glued-quoted-granted-lane',
    'scp-userknownhostsfile-glued-quoted-outside-head',
    'scp-userknownhostsfile-glued-quoted-outside-lane',
    'sftp-batch-control-unresolved-head',
    'sftp-batch-control-unresolved-lane',
    'sftp-batch-empty-unresolved-head',
    'sftp-batch-empty-unresolved-lane',
    'sftp-batch-tilde-unresolved-head',
    'sftp-batch-tilde-unresolved-lane',
    'sftp-certificatefile-glued-quoted-granted-head',
    'sftp-certificatefile-glued-quoted-granted-lane',
    'sftp-certificatefile-glued-quoted-outside-head',
    'sftp-certificatefile-glued-quoted-outside-lane',
    'sftp-globalknownhostsfile-glued-quoted-granted-head',
    'sftp-globalknownhostsfile-glued-quoted-granted-lane',
    'sftp-globalknownhostsfile-glued-quoted-outside-head',
    'sftp-globalknownhostsfile-glued-quoted-outside-lane',
    'sftp-identity-control-unresolved-head',
    'sftp-identity-control-unresolved-lane',
    'sftp-identity-empty-unresolved-head',
    'sftp-identity-empty-unresolved-lane',
    'sftp-identityfile-glued-quoted-granted-head',
    'sftp-identityfile-glued-quoted-granted-lane',
    'sftp-identityfile-glued-quoted-outside-head',
    'sftp-identityfile-glued-quoted-outside-lane',
    'sftp-userknownhostsfile-glued-quoted-granted-head',
    'sftp-userknownhostsfile-glued-quoted-granted-lane',
    'sftp-userknownhostsfile-glued-quoted-outside-head',
    'sftp-userknownhostsfile-glued-quoted-outside-lane',
    'ssh-certificatefile-glued-quoted-granted-head',
    'ssh-certificatefile-glued-quoted-granted-lane',
    'ssh-certificatefile-glued-quoted-outside-head',
    'ssh-certificatefile-glued-quoted-outside-lane',
    'ssh-globalknownhostsfile-glued-quoted-granted-head',
    'ssh-globalknownhostsfile-glued-quoted-granted-lane',
    'ssh-globalknownhostsfile-glued-quoted-outside-head',
    'ssh-globalknownhostsfile-glued-quoted-outside-lane',
    'ssh-identity-control-unresolved-head',
    'ssh-identity-control-unresolved-lane',
    'ssh-identity-empty-unresolved-head',
    'ssh-identity-empty-unresolved-lane',
    'ssh-identityfile-glued-quoted-granted-head',
    'ssh-identityfile-glued-quoted-granted-lane',
    'ssh-identityfile-glued-quoted-outside-head',
    'ssh-identityfile-glued-quoted-outside-lane',
    'ssh-log-control-unresolved-head',
    'ssh-log-control-unresolved-lane',
    'ssh-log-empty-unresolved-head',
    'ssh-log-empty-unresolved-lane',
    'ssh-log-tilde-unresolved-head',
    'ssh-log-tilde-unresolved-lane',
    'ssh-userknownhostsfile-glued-quoted-granted-head',
    'ssh-userknownhostsfile-glued-quoted-granted-lane',
    'ssh-userknownhostsfile-glued-quoted-outside-head',
    'ssh-userknownhostsfile-glued-quoted-outside-lane',
    'transport-backslash-granted-head',
    'transport-backslash-granted-lane',
    'transport-backslash-outside-head',
    'transport-backslash-outside-lane',
    'transport-concatenated-quotes-granted-head',
    'transport-concatenated-quotes-granted-lane',
    'transport-concatenated-quotes-outside-head',
    'transport-concatenated-quotes-outside-lane',
    'transport-config-quotes-granted-head',
    'transport-config-quotes-granted-lane',
    'transport-config-quotes-outside-head',
    'transport-config-quotes-outside-lane',
    'transport-destination-collision-head',
    'transport-destination-collision-lane',
    'transport-destination-collision-option-head',
    'transport-destination-collision-option-lane',
    'transport-destination-collision-terminator-head',
    'transport-destination-collision-terminator-lane',
    'transport-double-quotes-granted-head',
    'transport-double-quotes-granted-lane',
    'transport-double-quotes-outside-head',
    'transport-double-quotes-outside-lane',
    'transport-escaped-space-host-head',
    'transport-escaped-space-host-lane',
    'transport-expansion-head',
    'transport-expansion-lane',
    'transport-glob-head',
    'transport-glob-lane',
    'transport-option-host-hostname-outside-head',
    'transport-option-host-hostname-outside-lane',
    'transport-option-host-jump-outside-head',
    'transport-option-host-jump-outside-lane',
    'transport-option-host-proxyjump-outside-head',
    'transport-option-host-proxyjump-outside-lane',
    'transport-single-quotes-granted-head',
    'transport-single-quotes-granted-lane',
    'transport-single-quotes-outside-head',
    'transport-single-quotes-outside-lane',
    'transport-trailing-operator-head',
    'transport-trailing-operator-lane',
    'userknownhostsfile-backslash-granted-head',
    'userknownhostsfile-backslash-granted-lane',
    'userknownhostsfile-backslash-outside-head',
    'userknownhostsfile-backslash-outside-lane',
    'userknownhostsfile-control-head',
    'userknownhostsfile-control-lane',
    'userknownhostsfile-equals-quoted-plain-granted-head',
    'userknownhostsfile-equals-quoted-plain-granted-lane',
    'userknownhostsfile-equals-quoted-plain-outside-head',
    'userknownhostsfile-equals-quoted-plain-outside-lane',
    'userknownhostsfile-equals-quoted-spaces-granted-head',
    'userknownhostsfile-equals-quoted-spaces-granted-lane',
    'userknownhostsfile-equals-quoted-spaces-outside-head',
    'userknownhostsfile-equals-quoted-spaces-outside-lane',
    'userknownhostsfile-extra-equals-head',
    'userknownhostsfile-extra-equals-lane',
    'userknownhostsfile-glob-head',
    'userknownhostsfile-glob-lane',
    'userknownhostsfile-malformed-quote-head',
    'userknownhostsfile-malformed-quote-lane',
    'userknownhostsfile-single-quotes-granted-head',
    'userknownhostsfile-single-quotes-granted-lane',
    'userknownhostsfile-single-quotes-outside-head',
    'userknownhostsfile-single-quotes-outside-lane',
    'userknownhostsfile-space-quoted-plain-granted-head',
    'userknownhostsfile-space-quoted-plain-granted-lane',
    'userknownhostsfile-space-quoted-plain-outside-head',
    'userknownhostsfile-space-quoted-plain-outside-lane',
    'userknownhostsfile-space-quoted-spaces-granted-head',
    'userknownhostsfile-space-quoted-spaces-granted-lane',
    'userknownhostsfile-space-quoted-spaces-outside-head',
    'userknownhostsfile-space-quoted-spaces-outside-lane',
}
groups = {}
quiet = io.StringIO()

def result(group, key, label, good, detail=''):
    global passed, failed
    counts = groups.setdefault(group, [0, 0])
    counts[0 if good else 1] += 1
    passed += bool(good)
    failed += not good
    if group.startswith('F4-'):
        kind = 'fold4 differentiator' if key in FOLD4_DIFFERENTIATORS else 'fold4 control'
    elif group.startswith(('F2', 'F6', 'F3-')) or key.startswith('remote-parameter-'):
        kind = 'fold3 differentiator' if key in FOLD3_DIFFERENTIATORS else 'fold3 control'
    else:
        kind = 'differentiator' if key in DIFFERENTIATORS else 'control'
    print(('  ok   — ' if good else 'FAIL   — ') + group + ' [' + kind + '] ' + key + ': ' + label +
          (('  [' + detail + ']') if not good else ''))

def case(group, key, command, allow=True, boundary='', names=(), network=None, writes=None,
         reads=None, roles=(False, True)):
    network = [H] if network is None else network
    writes = [W] if writes is None else writes
    reads = [R] if reads is None else reads
    for head in roles:
        with contextlib.redirect_stdout(quiet):
            try:
                got = lf.check({'tool_name': 'Bash', 'tool_input': {'command': command}},
                               [lf.norm(path) for path in reads], [lf.norm(path) for path in writes],
                               head=head, network=network)
            except Exception as exc:
                print('PROBE FAILED: SSH checker raised: ' + repr(exc), file=sys.stderr)
                sys.exit(2)
        want = ('silent' if head else 'allow') if allow else 'deny'
        good = got[0] == want
        if not allow:
            good = good and bool(re.search(boundary, got[1], re.I)) and all(name in got[1] for name in names)
        case_key = key + ('-head' if head else '-lane')
        result(group, case_key, command, good, 'want=' + want + ' got=' + repr(got))

# S1: quoting determines whether an operand is remote data or local shell evaluation.
for key, payload in (
    ('quoted-path', "'cat /remote/reports/input.txt'"),
    ('bare-path', 'cat /remote/reports/input.txt'),
    ('double-quoted-path', '"cat /remote/reports/input.txt"'),
    ('protected-expansion', "'printf %s $HOME /remote/*.txt $(id) " + chr(96) + "id" + chr(96) + "'"),
    ('quoted-glob', '"cat /remote/*.txt"')):
    case('S1', key, 'ssh ' + H + ' ' + payload)
case('S1', 'remote-pipe', 'ssh ' + H + " 'cat /remote/input.txt' | head -1")
case('S1', 'piped-remote', 'cat ' + q(rf) + ' | ssh ' + H + " 'cat /remote/input.txt'")
case('S1', 'separate-local-read', 'ssh ' + H + " 'cat /remote/input.txt'; cat " + q(uf), False, READ, (U,))
case('S1', 'local-glob', 'ssh ' + H + ' cat ' + q(U) + '/*.txt', False, r'read|grant|local evaluation|unresolv')
case('S1', 'local-substitution', 'ssh ' + H + ' "$(cat ' + q(uf) + ')"', False, r'local evaluation|unresolv|read')
case('S1', 'local-backtick', 'ssh ' + H + ' "' + chr(96) + 'cat ' + q(uf) + chr(96) + '"',
     False, r'local evaluation|unresolv|read')
case('S1', 'remote-parameter', 'ssh ' + H + ' "$UNRESOLVED/input.txt"')
case('S1', 'local-process-substitution', 'ssh ' + H + ' cat <(cat ' + q(uf) + ')', False, UNRESOLVED)

case('S1', 'escaped-remote-dollar', 'ssh ' + H + r' printf %s \$HOME')
case('S1', 'remote-parent-path', 'ssh ' + H + ' cat ../remote/input.txt')

# S2: only connection operands contribute hosts; a later local command is independent.
for key, data in (('dotted-data', 'results.json'), ('manifest-data', '/remote/manifest.json'),
                  ('email-data', 'reader@data.example.invalid'), ('url-data', 'https://data.example.invalid/result')):
    case('S2', key, 'ssh ' + H + ' ' + q('printf %s ' + data))
case('S2', 'local-curl-host', 'ssh ' + H + " 'printf %s results.json'; curl https://" + X + '/', False, HOST, (X,))
case('S2', 'local-piped-curl', 'ssh ' + H + " 'printf %s results.json' | curl https://" + X + '/', False, HOST, (X,))

# S3: endpoint grammar and source/read versus destination/write permissions.
case('S3', 'scp-upload', 'scp ' + q(rf) + ' ' + H + ':/remote/input.txt')
case('S3', 'scp-download', 'scp ' + H + ':/remote/input.txt ' + q(wf))
case('S3', 'scp-user-endpoint', 'scp ' + q(rf) + ' reader@' + H + ':/remote/input.txt')
case('S3', 'scp-ipv6', 'scp ' + q(rf) + ' ' + q('reader@[' + IP + ']:/remote/input.txt'), network=[IP])
case('S3', 'scp-ipv6-ungranted', 'scp ' + q(rf) + ' ' + q('[' + IP + ']:/remote/input.txt'), False, HOST, (IP,))
case('S3', 'scp-ungranted-source', 'scp ' + q(uf) + ' ' + H + ':/remote/input.txt', False, READ, (U,))
case('S3', 'scp-readonly-destination', 'scp ' + H + ':/remote/input.txt ' + q(rf), False, WRITE)
case('S3', 'scp-readonly-no-writes', 'scp ' + H + ':/remote/input.txt ' + q(rf), False, WRITE, writes=[])
case('S3', 'scp-ungranted-endpoint', 'scp ' + q(rf) + ' ' + X + ':/remote/input.txt', False, HOST, (X,))
case('S3', 'scp-malformed-endpoint', 'scp ' + q(rf) + " '[broken:/remote/input.txt'", False, r'endpoint|bracket|IPv6')
case('S3', 'sftp-bare-host', 'sftp ' + H)
case('S3', 'sftp-user-host', 'sftp reader@' + H)
case('S3', 'sftp-ungranted-host', 'sftp ' + X, False, HOST, (X,))

# S4: local transfers need no network grant; every supported remote form does.
case('S4', 'rsync-local', 'rsync -a ' + q(rf) + ' ' + q(wf), network=[])
for key, endpoint in (('ssh', H + ':/remote/input.txt'), ('daemon', H + '::module/input.txt'),
                      ('uri', 'rsync://' + H + '/module/input.txt')):
    case('S4', 'rsync-' + key + '-download', 'rsync -a ' + q(endpoint) + ' ' + q(wf))
    case('S4', 'rsync-' + key + '-upload', 'rsync -a ' + q(rf) + ' ' + q(endpoint))
    case('S4', 'rsync-' + key + '-missing-network', 'rsync -a ' + q(endpoint) + ' ' + q(wf), False,
         r'network', network=[])
    case('S4', 'rsync-' + key + '-ungranted', 'rsync -a ' + q(endpoint.replace(H, X)) + ' ' + q(wf),
         False, HOST, (X,))
case('S4', 'rsync-shell-wrapper', 'sh -c ' + q('rsync -a ' + H + ':/remote/input.txt ' + q(wf)))
case('S4', 'rsync-shell-wrapper-deny', 'sh -c ' + q('rsync -a rsync://' + X + '/module/input.txt ' + q(wf)),
     False, HOST, (X,))
case('S4', 'rsync-env-wrapper', 'env MODE=literal rsync -a ' + H + ':/remote/input.txt ' + q(wf))
case('S4', 'rsync-unresolved-remote', 'rsync -a "rsync://$UNKNOWN/module/input.txt" ' + q(wf), False, UNRESOLVED)
case('S4', 'rsync-readonly-destination', 'rsync -a ' + H + ':/remote/input.txt ' + q(rf), False, WRITE)
case('S4', 'rsync-local-readonly', 'rsync -a ' + q(rf) + ' ' + q(str(readable / 'copy.txt')), False, WRITE, network=[])
case('S4', 'rsync-ungranted-source', 'rsync -a ' + q(uf) + ' ' + q(wf), False, READ, (U,), network=[])
case('S4', 'rsync-ipv6', 'rsync -a ' + q('[' + IP + ']:/remote/input.txt') + ' ' + q(wf), network=[IP])

case('S4', 'rsync-ipv6-daemon', 'rsync -a ' + q('[' + IP + ']::module/input.txt') + ' ' + q(wf), network=[IP])
case('S4', 'rsync-ipv6-uri', 'rsync -a ' + q('rsync://[' + IP + ']/module/input.txt') + ' ' + q(wf), network=[IP])
case('S4', 'rsync-ipv6-uri-deny', 'rsync -a ' + q('rsync://[' + IP + ']/module/input.txt') + ' ' + q(wf),
     False, HOST, (IP,))

for key, wrapper in (
    ('glued', 'sh -c' + q('rsync -a ' + H + ':/remote/input.txt ' + q(wf))),
    ('arg0', 'sh -c ' + q('rsync -a ' + H + ':/remote/input.txt ' + q(wf)) + ' literal-arg0')):
    case('S4', 'rsync-wrapper-' + key, wrapper)
    case('S4', 'rsync-wrapper-' + key + '-missing-network', wrapper, False, r'network', network=[])

case('S4', 'wrapper-program-readable', q(str(readable / 'sh')) + ' -c ' +
     q('rsync -a ' + H + ':/remote/input.txt ' + q(wf)))
case('S4', 'wrapper-program-outside', q(str(outside / 'sh')) + ' -c ' +
     q('rsync -a ' + H + ':/remote/input.txt ' + q(wf)), False, READ, (U,))

# S5: literal assignment values are data; assignments do not mask the next command.
for key, value in (('bare', '/remote/prefix'), ('single', "'/remote/prefix'"),
                   ('double', '"/remote/prefix"'), ('protected', "'$HOME/remote/*'")):
    case('S5', 'assignment-' + key, 'REMOTE_PREFIX=' + value + ' ssh ' + H + " 'cat /remote/input.txt'")
case('S5', 'assignment-local-evaluation', 'REMOTE_PREFIX="$(cat ' + q(uf) + ')" ssh ' + H + ' true',
     False, r'local evaluation|unresolv|read')
case('S5', 'assignment-then-read', "REMOTE_PREFIX='/remote/prefix' cat " + q(uf), False, READ, (U,))

# S6: one leading absolute cd supplies the base of local relative writes.
for key, suffix in (('overwrite', '> result.txt'), ('append', '>> result.txt'), ('tee', '| tee result.txt')):
    case('S6', 'cd-' + key, 'cd ' + q(W) + ' && ssh ' + H + ' true ' + suffix)
case('S6', 'cd-escape', 'cd ' + q(W) + ' && ssh ' + H + ' true > ../readable/result.txt', False, WRITE)
case('S6', 'cd-missing', 'cd && ssh ' + H + ' true > result.txt', False, r'directory|cd|base|unresolv')
case('S6', 'cd-variable', 'cd "$UNKNOWN" && ssh ' + H + ' true > result.txt', False, r'directory|cd|base|unresolv')
case('S6', 'cd-nonexistent', 'cd ' + q(str(ro / 'absent')) + ' && ssh ' + H + ' true > result.txt', False,
     r'directory|cd|base|unresolv')
case('S6', 'cd-compound', 'cd ' + q(W) + '; ssh ' + H + ' true > result.txt', False, r'base|compound|unresolv')
case('S6', 'cd-subshell', '(cd ' + q(W) + ' && ssh ' + H + ' true) > result.txt', False, r'base|subshell|unresolv')

# S7: option values have independent read, write and network effects.
for key, options in (('port-spaced', '-p 2222'), ('port-glued', '-p2222'), ('port-option', '-o Port=2222'),
                     ('user-spaced', '-l reader'), ('user-glued', '-lreader'), ('batch-option', '-o BatchMode=yes')):
    case('S7', 'option-' + key, 'ssh ' + options + ' ' + H + ' true')
case('S7', 'option-identity-read', 'ssh -i ' + q(str(readable / 'identity')) + ' ' + H + ' true')
case('S7', 'option-identity-glued', 'ssh -i' + q(str(readable / 'identity')) + ' ' + H + ' true')
case('S7', 'option-known-hosts-read', 'ssh -o ' + q('UserKnownHostsFile=' + str(readable / 'known_hosts')) + ' ' + H + ' true')
case('S7', 'option-identity-outside', 'ssh -i ' + q(uf) + ' ' + H + ' true', False, READ, (U,))
case('S7', 'option-known-hosts-outside', 'ssh -o ' + q('UserKnownHostsFile=' + uf) + ' ' + H + ' true', False, READ, (U,))
case('S7', 'option-log-write', 'ssh -E ' + q(wf) + ' ' + H + ' true')
case('S7', 'option-log-outside', 'ssh -E ' + q(rf) + ' ' + H + ' true', False, WRITE)
for key, jump in (('jump-spaced', '-J ' + J), ('jump-glued', '-J' + J),
                  ('jump-user-port', '-J reader@' + J + ':2222'),
                  ('jump-option', '-o ProxyJump=' + J), ('jump-option-glued', '-oProxyJump=' + J)):
    case('S7', key + '-granted', 'ssh ' + jump + ' ' + H + ' true', network=[H, J])
    case('S7', key + '-ungranted', 'ssh ' + jump + ' ' + H + ' true', False, HOST, (J,))
case('S7', 'multiple-jumps', 'ssh -J ' + J + ',' + X + ' ' + H + ' true', False, HOST, (X,), network=[H, J])
case('S7', 'destination-host', 'ssh ' + X + ' true', False, HOST, (X,))
case('S7', 'effective-host-granted', 'ssh -o HostName=' + H + ' ' + H + ' true')
case('S7', 'effective-host-ungranted', 'ssh -o HostName=' + X + ' ' + H + ' true', False, HOST, (X,))
case('S7', 'config-unseen', 'ssh -F ' + q(str(readable / 'config')) + ' ' + H + ' true', False, r'config|unresolv')
case('S7', 'proxy-command', 'ssh -o ' + q('ProxyCommand=cat ' + rf) + ' ' + H + ' true', False,
     r'ProxyCommand|local program|unresolv')
case('S7', 'rsync-plain-rsh', 'rsync -e ssh ' + q(rf) + ' ' + H + ':/remote/input.txt')
case('S7', 'rsync-rsh-options', 'rsync --rsh=' + q('ssh -p 2222 -J ' + J) + ' ' + q(rf) + ' ' + H + ':/remote/input.txt', network=[H, J])
case('S7', 'rsync-rsh-jump-deny', 'rsync -e ' + q('ssh -J ' + J) + ' ' + q(rf) + ' ' + H + ':/remote/input.txt', False, HOST, (J,))
case('S7', 'rsync-custom-rsh', 'rsync -e ' + q('sh -c true') + ' ' + q(rf) + ' ' + H + ':/remote/input.txt', False,
     r'rsh|local program|unresolv')

case('S7', 'option-cipher', 'ssh -c aes256-ctr ' + H + ' true')
case('S7', 'option-provider-program', 'ssh -I ' + q(str(readable / 'identity')) + ' ' + H + ' true',
     False, r'local program|provider|PKCS|unresolved.*-I')
case('S7', 'rsync-log-write', 'rsync --log-file=' + q(wf) + ' ' + q(rf) + ' ' + H + ':/remote/input.txt')
case('S7', 'rsync-log-readonly', 'rsync --log-file=' + q(rf) + ' ' + q(rf) + ' ' + H + ':/remote/input.txt', False, WRITE)
for key, option in (('files', '--files-from'), ('include', '--include-from'), ('exclude', '--exclude-from'),
                     ('password', '--password-file')):
    case('S7', 'rsync-' + key + '-read', 'rsync ' + option + '=' + q(rf) + ' ' + q(R) + ' ' + H + ':/remote/')
    case('S7', 'rsync-' + key + '-outside', 'rsync ' + option + '=' + q(uf) + ' ' + q(R) + ' ' + H + ':/remote/',
         False, READ, (U,))

case('S7', 'identity-client-expansion', 'ssh -i ' + q('~/key') + ' ' + H + ' true',
     False, r'option file|client|expansion|unresolv')

# S8: malformed/unknown syntax fails for its boundary under a present grant.
case('S8', 'complete-command', 'ssh ' + H + ' true')
case('S8', 'missing-network', 'ssh ' + H + ' true', False, r'no.*network|network.*(?:missing|grant|off)', network=[])
case('S8', 'hostless', 'ssh', False, r'host|destination')
case('S8', 'missing-port', 'ssh -p', False, r'option.*(value|missing|incomplete)|(?:value|missing|incomplete).*option')
case('S8', 'missing-identity', 'ssh -i', False, r'option.*(value|missing|incomplete)|(?:value|missing|incomplete).*option')
case('S8', 'missing-o-value', 'ssh -o', False, r'option.*(value|missing|incomplete)|(?:value|missing|incomplete).*option')
case('S8', 'unknown-ssh-option', 'ssh -Z ' + H + ' true', False, r'option')
case('S8', 'unknown-scp-option', 'scp -Z ' + q(rf) + ' ' + H + ':/remote/input.txt', False, r'option')
case('S8', 'unknown-rsync-option', 'rsync --unrecognised ' + q(rf) + ' ' + H + ':/remote/input.txt', False, r'option')
case('S8', 'unresolved-host', 'ssh "$UNKNOWN" true', False, UNRESOLVED)
case('S8', 'missing-scp-destination', 'scp ' + H + ':/remote/input.txt', False, r'endpoint|destination|operand')

case('S8', 'unsupported-shell-wrapper', 'sh -ic ' + q('rsync -a ' + H + ':/remote/input.txt ' + q(wf)),
     False, r'wrapper|shell')
case('S8', 'unsupported-env-wrapper', 'env -i rsync -a ' + H + ':/remote/input.txt ' + q(wf),
     False, r'wrapper|env')

# S9: local redirections remain local in every supported position.
case('S9', 'local-read-and-write', 'ssh ' + H + ' cat < ' + q(rf) + ' > ' + q(wf))
case('S9', 'input-before-command', '< ' + q(rf) + ' ssh ' + H + ' cat > ' + q(wf))
case('S9', 'input-before-host', 'ssh < ' + q(rf) + ' ' + H + ' cat > ' + q(wf))
case('S9', 'remote-quoted-redirect', 'ssh ' + H + " 'cat </remote/input.txt >/remote/output.txt'")
case('S9', 'local-input-ungranted', 'ssh ' + H + ' cat < ' + q(uf), False, READ, (U,))
case('S9', 'local-input-ungranted-leading', '< ' + q(uf) + ' ssh ' + H + ' cat', False, READ, (U,))
case('S9', 'local-input-ungranted-middle', 'ssh < ' + q(uf) + ' ' + H + ' cat', False, READ, (U,))
case('S9', 'fd-input-ungranted', 'ssh ' + H + ' cat 0< ' + q(uf), False, READ, (U,))
for key, operator in (('overwrite', '>'), ('append', '>>'), ('tee', '| tee')):
    case('S9', 'local-' + key + '-granted', 'ssh ' + H + ' true ' + operator + ' ' + q(wf))
    case('S9', 'local-' + key + '-readonly', 'ssh ' + H + ' true ' + operator + ' ' + q(rf), False, WRITE)
case('S9', 'here-string-literal', 'ssh ' + H + " cat <<< '/remote/input.txt'")
case('S9', 'here-string-substitution', 'ssh ' + H + ' cat <<< "$(cat ' + q(uf) + ')"', False,
     r'local evaluation|unresolv|read')
case('S9', 'symlink-destination', 'scp ' + H + ':/remote/input.txt ' + q(str(writable / 'link.txt')), False, WRITE)

case('S9', 'fd-duplication', 'ssh ' + H + ' cat < ' + q(rf) + ' > ' + q(wf) + ' 2>&1')
case('S9', 'output-before-command', '> ' + q(wf) + ' ssh ' + H + ' true')
case('S9', 'output-before-command-readonly', '> ' + q(rf) + ' ssh ' + H + ' true', False, WRITE)
case('S9', 'output-before-host', 'ssh > ' + q(wf) + ' ' + H + ' true')
case('S9', 'output-before-host-readonly', 'ssh > ' + q(rf) + ' ' + H + ' true', False, WRITE)

case('S9', 'heredoc-protected-evaluation', 'ssh ' + H + " cat <<'END'\n$HOME $(cat " + q(uf) +
     ') ' + chr(96) + 'id' + chr(96) + '\nEND')
case('S9', 'heredoc-unquoted-literal', 'ssh ' + H + ' cat <<END\nliteral /remote/input.txt\nEND')
case('S9', 'heredoc-local-evaluation', 'ssh ' + H + ' cat <<END\n$(cat ' + q(uf) + ')\nEND',
     False, r'local evaluation')
case('S9', 'heredoc-missing-terminator', 'ssh ' + H + ' cat <<END\nliteral\n',
     False, r'unterminated|terminator|heredoc')

# S10: the exemption composes with existing glob, pattern and network repairs.
case('S10', 'combined-granted-glob', 'cat ' + q(R) + '/*.txt; ssh ' + H + " 'cat /remote/input.txt'")
case('S10', 'combined-ungranted-glob', 'cat ' + q(U) + '/*.txt; ssh ' + H + " 'cat /remote/input.txt'", False, READ, (U,))
case('S10', 'combined-pattern', "grep 'claude' " + q(rf) + '; ssh ' + H + ' true')
case('S10', 'combined-nested-invocation', "grep 'claude' " + q(rf) + '; ssh ' + H + ' true; claude -p hello',
     False, r'nested|invoke.*claude', roles=(False,))
case('S10', 'combined-curl-output', 'ssh ' + H + ' true; curl -o ' + q(wf) + ' https://' + H + '/')
case('S10', 'combined-curl-host', 'ssh ' + H + ' true; curl -o ' + q(wf) + ' https://' + X + '/', False, HOST, (X,))
case('S10', 'combined-wget-output', 'ssh ' + H + ' true; wget -O ' + q(wf) + ' https://' + H + '/')
case('S10', 'combined-wget-host', 'ssh ' + H + ' true; wget -O ' + q(wf) + ' https://' + X + '/', False, HOST, (X,))

# Review fold: remote data, command bases and remote search composition.
def remote_cases(case, H, X, R, W, U, rf, wf, uf, q):
    """Cases also embedded in the full suite's SSH matrix."""
    for key, parameter in (
        ('named', '$NAME'), ('braced', '${NAME}'), ('positional', '$1'),
        ('braced-positional', '${12}'), ('status', '$?'), ('count', '$#'),
        ('all-arguments', '$@'), ('joined-arguments', '$*'), ('process', '$$'),
        ('background', '$!'), ('flags', '$-'), ('braced-all', '${@}'),
        ('braced-status', '${?}'), ('joined-literal', 'pre${NAME}post')):
        case('F2', 'parameter-' + key, 'ssh ' + H + ' "printf %s ' + parameter + '"')
    for key, remote in (
        ('job-id', 'squeue -j $JID'), ('encoded-spec', 'python submit.py --spec $B64'),
        ('score-ids', 'SCORE_IDS=$ids bash -s'),
        ('escaped-status', r'python submit.py --spec $B64; echo \$?')):
        case('F2', 'recorded-shape-' + key, 'ssh ' + H + ' "' + remote + '"')
    case('F2', 'separate-parameter-words', 'ssh ' + H + ' printf %s "$A" "${B}"')
    case('F2', 'parameter-wrapper', 'sh -c ' + q('ssh ' + H + ' "printf %s $NAME"'))
    unresolved = r'local evaluation|unresolv'
    for key, operand in (
        ('unquoted', '$NAME'), ('unquoted-braced', '${NAME}'),
        ('mixed-unquoted', '"$NAME"$OTHER'), ('default-value', '"${NAME:-value}"'),
        ('assignment', '"${NAME=value}"'), ('indirect', '"${!NAME}"'),
        ('array', '"${NAME[1]}"'), ('arithmetic', '"$((1+1))"'),
        ('substitution', '"$(cat ' + q(uf) + ')"'),
        ('backtick', '"' + chr(96) + 'cat ' + q(uf) + chr(96) + '"')):
        case('F2', 'refuse-' + key, 'ssh ' + H + ' cat ' + operand, False, unresolved)
    case('F2', 'refuse-process-substitution', 'ssh ' + H + ' cat <(cat ' + q(uf) + ')',
         False, r'local redirection', ('<',))
    case('F2', 'host-parameter', 'ssh "$HOST" "printf %s $NAME"', False, unresolved)
    case('F2', 'option-parameter', 'ssh -i "$IDENTITY" ' + H + ' "printf %s $NAME"', False, unresolved)
    case('F2', 'endpoint-parameter', 'scp "' + H + ':$NAME" ' + q(wf), False, unresolved)
    case('F2', 'rsync-destination-parameter', 'rsync -a ' + H + ':/remote/input.txt "$DEST"', False, unresolved)
    case('F2', 'parameter-local-read', 'ssh ' + H + ' "cat $NAME" < ' + q(uf), False, r'read|grant', (U,))
    case('F2', 'parameter-local-write', 'ssh ' + H + ' "cat $NAME" > ' + q(rf), False, r'write|writ', (R,))
    case('F2', 'parameter-write-control', 'ssh ' + H + ' "cat $NAME" > ' + q(wf))
    case('F2', 'parameter-host-control', 'ssh ' + X + ' "cat $NAME"', False, r'host|network', (X,))
    case('F2', 'parameter-option-host', 'ssh -J ' + X + ' ' + H + ' "cat $NAME"', False, r'host|network', (X,))

    for key, remote in (
        ('grep', 'grep claude f'), ('rg', 'rg claude f'), ('grep-option', 'grep -e claude f'),
        ('grep-glued', 'grep -eclaude f'), ('grep-long', 'grep --regexp=claude f'),
        ('rg-quoted', 'rg "claude" f'), ('two-searches', 'grep claude f | rg claude'),
        ('following-search', 'true; grep claude f')):
        case('F6', 'remote-' + key, 'ssh ' + H + ' ' + q(remote))
    case('F6', 'remote-bare-arguments', 'ssh ' + H + ' grep claude f')
    case('F6', 'remote-double-quoted', 'ssh ' + H + ' "grep claude f"')
    case('F6', 'remote-infix-output', 'ssh ' + H + ' grep > ' + q(wf) + ' claude f')
    case('F6', 'remote-and-local-pattern', 'grep claude ' + q(rf) + '; ssh ' + H + " 'grep claude f'")
    nested = r'nested|invoke.*claude'
    for key, remote in (
        ('direct', 'claude -p hello'), ('after-search', 'grep claude f; claude -p hello'),
        ('and-search', 'grep claude f && claude -p hello'),
        ('xargs', 'grep claude f | xargs claude'),
        ('remote-substitution', 'grep "$(claude -p hello)" f'),
        ('remote-backtick', 'grep "' + chr(96) + 'claude -p hello' + chr(96) + '" f'),
        ('execution-option', 'rg --pre claude pattern f')):
        case('F6', 'refuse-' + key, 'ssh ' + H + ' ' + q(remote), False, nested, roles=(False,))
    case('F6', 'local-substitution', 'ssh ' + H + ' "grep $(claude -p hello) f"',
         False, nested, roles=(False,))
    case('F6', 'separate-invocation', 'ssh ' + H + " 'grep claude f'; claude -p hello",
         False, nested, roles=(False,))
    case('F6', 'separate-read', 'ssh ' + H + " 'grep claude f'; cat " + q(uf), False, r'read|grant', (U,))
    case('F6', 'local-write', 'ssh ' + H + " 'grep claude f' > " + q(rf), False, r'write|writ', (R,))
    case('F6', 'ungranted-host', 'ssh ' + X + " 'grep claude f'", False, r'host|network', (X,))
remote_cases(case, H, X, R, W, U, rf, wf, uf, q)

# These are checker inputs only. Both roles run against the read-only SSH fixture.
def base_case(group, key, command, allow=True, boundary='', names=(), cwd=working, **kwargs):
    previous = os.getcwd()
    try:
        os.chdir(cwd)
        case(group, key, command, allow, boundary, names, **kwargs)
    finally:
        os.chdir(previous)

client_url = 'https://' + H + '/input.txt'
for key, directory, allow in (('readonly', R, False), ('writable', W, True)):
    base_case('F3-1', 'heredoc-client-' + key,
              'cd ' + q(directory) + " && sh <<'END'\ncurl -o result.txt " + client_url + '\nEND',
              allow, WRITE, cwd=writable)
    base_case('F3-1', 'heredoc-interpreter-' + key,
              'cd ' + q(directory) + " && python3 <<'END'\nopen('result.txt','w')\nEND",
              allow, WRITE, cwd=writable)
for key, command in (
    ('curl-output', 'curl -o result.txt ' + client_url),
    ('wget-output', 'wget -O result.txt ' + client_url),
    ('curl-remote-name', 'curl -O ' + client_url),
    ('wget-default', 'wget ' + client_url),
    ('curl-trace', 'curl --trace trace.txt ' + client_url),
    ('mutator', 'touch result.txt'),
    ('interpreter', 'python3 -c ' + chr(34) + "open('result.txt','w')" + chr(34)),
    ('redirection', 'printf x > result.txt'),
    ('tee', 'printf x | tee result.txt'),
):
    base_case('F3-1', key + '-readonly-cd', 'cd ' + q(R) + ' && ' + command,
              False, WRITE, cwd=writable)
    base_case('F3-1', key + '-writable-cd', 'cd ' + q(W) + ' && ' + command,
              cwd=readable)
for key, change in (
    ('variable', 'cd "$DIRECTORY" && '),
    ('sequence', 'cd ' + q(W) + '; '),
    ('or', 'cd ' + q(W) + ' || '),
    ('missing', 'cd ' + q(str(ro / 'absent')) + ' && '),
    ('subshell', '(cd ' + q(W) + ' && true); '),
):
    for client in ('curl -o result.txt ', 'wget -O result.txt '):
        base_case('F3-1', key + '-' + client.split()[0], change + client + client_url,
                  False, r'base|unresolv', cwd=writable)

base_case('F3-3', 'unconditional-cd-keeps-sequence-base', 'cd ' + q(W) + ' && true; curl -o result.txt ' + client_url, cwd=readable)
base_case('F3-3', 'unconditional-cd-keeps-newline-base', 'cd ' + q(W) + ' && true\ncurl -o result.txt ' + client_url, cwd=readable)
base_case('F3-3', 'mid-command-scp', 'printf ready; cd ' + q(R) + ' && scp input.txt ' + H + ':/remote/input.txt')
base_case('F3-3', 'mid-command-rsync', 'printf ready && cd ' + q(R) + ' && rsync input.txt ' + H + ':/remote/input.txt')
base_case('F3-3', 'mid-command-redirect', 'printf ready; cd ' + q(W) + ' && ssh ' + H + ' true > result.txt')
base_case('F3-3', 'mid-command-curl', 'printf ready; cd ' + q(W) + ' && curl -o result.txt ' + client_url)
base_case('F3-3', 'mid-command-interpreter', 'printf ready; cd ' + q(W) + ' && python3 -c ' + chr(34) + "open('result.txt','w')" + chr(34))
base_case('F3-3', 'earlier-write-keeps-writable-base', 'curl -o result.txt ' + client_url + '; cd ' + q(R) + ' && scp input.txt ' + H + ':/remote/input.txt', cwd=writable)
base_case('F3-3', 'earlier-write-keeps-readonly-base', 'curl -o result.txt ' + client_url + '; cd ' + q(W) + ' && ssh ' + H + ' true', False, WRITE, cwd=readable)
base_case('F3-3', 'earlier-interpreter-keeps-writable-base', 'python3 -c ' + chr(34) + "open('result.txt','w')" + chr(34) + '; cd ' + q(R) + ' && scp input.txt ' + H + ':/remote/input.txt', cwd=writable)
base_case('F3-3', 'earlier-scp-write-keeps-readonly-base', 'scp ' + H + ':/remote/input.txt result.txt; cd ' + q(W) + ' && true', False, WRITE, cwd=readable)
base_case('F3-3', 'multiple-controlled-directories', 'cd ' + q(W) + ' && curl -o result.txt ' + client_url + ' && cd ' + q(R) + ' && scp input.txt ' + H + ':/remote/input.txt')
base_case('F3-3', 'mid-command-escape', 'printf ready; cd ' + q(W) + ' && scp ' + H + ':/remote/input.txt ../readable/result.txt', False, WRITE)
base_case('F3-3', 'mid-command-variable', 'printf ready; cd "$DIRECTORY" && scp input.txt ' + H + ':/remote/input.txt', False, r'base|unresolv')
base_case('F3-3', 'mid-command-subshell', 'printf ready; (cd ' + q(R) + ' && scp input.txt ' + H + ':/remote/input.txt)', False, r'base|unresolv')
for key, prefix in (
    ('skipped-or-cd', 'true || cd ' + q(W) + ' && '),
    ('skipped-and-cd', 'false && cd ' + q(W) + ' && true; '),
    ('background-cd', 'cd ' + q(W) + ' && true & '),
    ('stderr-pipeline-cd', 'true |& cd ' + q(W) + ' && '),
    ('newline-after-skipped-cd', 'false && cd ' + q(W) + ' && true\n'),
):
    base_case('F3-3', key, prefix + 'curl -o result.txt ' + client_url, False, r'base|unresolv', cwd=readable)

# FOLD4_OPTIONS_BEGIN
# Fourth review fold: preserve the distinction between shell and client grammars.
def fold4_client(client, options):
    if client == 'ssh':
        return 'ssh ' + options + ' ' + H + ' true'
    if client == 'scp':
        return 'scp ' + options + ' ' + q(rf) + ' ' + H + ':/remote/input.txt'
    return 'sftp ' + options + ' ' + H


config_boundary = r'unresolv.*(?:ssh|configuration|setting|option file)'
for setting in ('IdentityFile', 'CertificateFile', 'UserKnownHostsFile', 'GlobalKnownHostsFile'):
    setting_key = setting.lower()
    # Four settings x two separators x two filename forms x two grants x two roles.
    for separator_key, separator in (('equals', '='), ('space', ' ')):
        for path_key, suffix in (('plain', '/key'), ('spaces', '/key file')):
            for grant_key, directory in (('granted', R), ('outside', U)):
                value = setting + separator + '"' + directory + suffix + '"'
                case('F4-1', setting_key + '-' + separator_key + '-quoted-' + path_key + '-' + grant_key,
                     fold4_client('ssh', '-o ' + q(value)), False, config_boundary, (setting_key,))
        for grant_key, path, allow in (('granted', rf, True), ('outside', uf, False)):
            case('F4-1', setting_key + '-' + separator_key + '-ordinary-' + grant_key,
                 fold4_client('ssh', '-o ' + q(setting + separator + path)), allow, READ, (U,) if not allow else ())
    for spelling, make_value in (
        ('single-quotes', lambda path: "'" + path + "'"),
        ('backslash', lambda path: path + r'\ file'),
    ):
        for grant_key, directory in (('granted', R), ('outside', U)):
            case('F4-1', setting_key + '-' + spelling + '-' + grant_key,
                 fold4_client('ssh', '-o ' + q(setting + '=' + make_value(directory + '/key'))),
                 False, config_boundary, (setting_key,))
    for key, value in (('control', R + '/key\nfile'), ('glob', R + '/key*')):
        case('F4-1', setting_key + '-' + key,
             fold4_client('ssh', '-o ' + q(setting + '=' + value)), False, config_boundary, (setting_key,))
    for grant_key, path, allow in (('granted', rf, True), ('outside', uf, False)):
        case('F4-1', setting_key + '-spaced-equals-ordinary-' + grant_key,
             fold4_client('ssh', '-o ' + q(setting + ' = ' + path)), allow, READ, (U,) if not allow else ())
    for key, text in (('missing', setting), ('empty', setting + '=')):
        case('F4-1', setting_key + '-' + key,
             fold4_client('ssh', '-o ' + q(text)), False, r'missing.*ssh.*option.*value')
    for key, text in (('malformed-quote', setting + '="' + R + '/key'),
                      ('extra-equals', setting + '==' + rf)):
        case('F4-1', setting_key + '-' + key,
             fold4_client('ssh', '-o ' + q(text)), False, config_boundary, (setting_key,))
    multiple_allowed = setting_key in {'userknownhostsfile', 'globalknownhostsfile'}
    for grant_key, second in (('granted', R + '/known_hosts'), ('outside', uf)):
        allow = multiple_allowed and grant_key == 'granted'
        boundary = READ if multiple_allowed else config_boundary
        names = (U,) if multiple_allowed and not allow else ((setting_key,) if not allow else ())
        case('F4-1', setting_key + '-multiple-' + grant_key,
             fold4_client('ssh', '-o ' + q(setting + '=' + R + '/identity ' + second)),
             allow, boundary, names)
        if multiple_allowed:
            case('F4-1', setting_key + '-tab-list-' + grant_key,
                 fold4_client('ssh', '-o ' + q(setting + '=' + R + '/identity\t' + second)),
                 allow, boundary, names)
    # Glued -o values retain this grammar in ssh, scp and sftp.
    for client in ('ssh', 'scp', 'sftp'):
        for grant_key, directory in (('granted', R), ('outside', U)):
            case('F4-1', client + '-' + setting_key + '-glued-quoted-' + grant_key,
                 fold4_client(client, '-o' + q(setting + ' "' + directory + '/key file"')),
                 False, config_boundary, (setting_key,))

# The remaining admitted file options receive literal argv values. Quotes and
# backslashes which survived the shell belong to the filename, as do spaces.
fold4_argv_options = (
    ('ssh-identity', 'ssh', '-i', 'read'),
    ('scp-identity', 'scp', '-i', 'read'),
    ('sftp-identity', 'sftp', '-i', 'read'),
    ('sftp-batch', 'sftp', '-b', 'read'),
    ('ssh-log', 'ssh', '-E', 'write'),
    ('rsync-files', 'rsync', '--files-from', 'read'),
    ('rsync-include', 'rsync', '--include-from', 'read'),
    ('rsync-exclude', 'rsync', '--exclude-from', 'read'),
    ('rsync-password', 'rsync', '--password-file', 'read'),
    ('rsync-log', 'rsync', '--log-file', 'write'),
)


def fold4_argv_command(client, option, path, attached=False):
    options = option + ('=' if attached and option.startswith('--') else '' if attached else ' ') + q(path)
    if client == 'rsync':
        return 'rsync ' + options + ' ' + q(rf) + ' ' + H + ':/remote/input.txt'
    return fold4_client(client, options)


for option_key, client, option, access in fold4_argv_options:
    allowed_directory = R if access == 'read' else W
    boundary = READ if access == 'read' else WRITE
    # Ten options x four literal filenames x two grants x two roles; each admitted
    # filename also carries one exact-path classifier check, independent of grants.
    for spelling, basename in (('spaces', 'key file'), ('double-quote', 'key"file'),
                               ('single-quote', "key'file"), ('backslash', r'key\file')):
        for grant_key, directory, allow in (('granted', allowed_directory, True), ('outside', U, False)):
            path = directory + '/' + basename
            command = fold4_argv_command(client, option, path)
            case('F4-2', option_key + '-' + spelling + '-' + grant_key,
                 command, allow, boundary, (U,) if not allow else ())
            if allow:
                segments = lf.ssh_shell_words(command)
                if len(segments) != 1:
                    print('PROBE FAILED: literal filename fixture split into shell commands', file=sys.stderr)
                    sys.exit(2)
                classified = lf.ssh_family_info([word[0] for word in segments[0]])
                collection = classified[1 if access == 'read' else 2]
                exact = not classified[3] and path in [candidate for _, candidate in collection]
                result('F4-2', option_key + '-' + spelling + '-exact',
                       'literal argv path retained exactly: ' + repr(path), exact, repr(classified))
    for grant_key, directory, allow in (('granted', allowed_directory, True), ('outside', U, False)):
        case('F4-2', option_key + '-attached-' + grant_key,
             fold4_argv_command(client, option, directory + '/key file', attached=True),
             allow, boundary, (U,) if not allow else ())
    case('F4-2', option_key + '-tilde-unresolved',
         fold4_argv_command(client, option, '~/key'), False, r'unresolv.*(?:file|path|tilde|expansion)')
    for key, path in (('empty', ''), ('control', allowed_directory + '/key\nfile')):
        case('F4-2', option_key + '-' + key + '-unresolved',
             fold4_argv_command(client, option, path), False, r'unresolv.*(?:file|path)')

# A colon gives --files-from its separate host:path source grammar. Its local
# subset refuses every colon; the other options retain literal internal colons.
for grant_key, directory in (('granted', R), ('outside', U)):
    for key, path in (('host', H + ':' + directory + '/input.txt'),
                       ('leading', ':' + directory + '/input.txt'),
                       ('absolute-literal', directory + '/key:literal')):
        case('F4-2', 'rsync-files-colon-' + key + '-' + grant_key,
             fold4_argv_command('rsync', '--files-from', path),
             False, r'unresolv.*rsync.*option file')
for option_key, option, access in (('include', '--include-from', 'read'), ('exclude', '--exclude-from', 'read'),
                                   ('password', '--password-file', 'read'), ('log', '--log-file', 'write')):
    for grant_key, directory, allow in (('granted', R if access == 'read' else W, True), ('outside', U, False)):
        path = directory + '/key:literal'
        command = fold4_argv_command('rsync', option, path)
        case('F4-2', 'rsync-' + option_key + '-literal-colon-' + grant_key,
             command, allow, READ if access == 'read' else WRITE, (U,) if not allow else ())
        if allow:
            segments = lf.ssh_shell_words(command)
            classified = lf.ssh_family_info([word[0] for word in segments[0]])
            collection = classified[1 if access == 'read' else 2]
            result('F4-2', 'rsync-' + option_key + '-literal-colon-exact',
                   'literal internal colon retained exactly: ' + repr(path),
                   not classified[3] and path in [candidate for _, candidate in collection], repr(classified))

# Existing refusals retain their reason when the value contains client quotes.
for client, option in (('ssh', '-F'), ('scp', '-F'), ('sftp', '-F'), ('ssh', '-S'),
                       ('ssh', '-I'), ('scp', '-S'), ('sftp', '-S'), ('sftp', '-s')):
    case('F4-2', client + '-' + option[1:] + '-quoted-refusal',
         fold4_client(client, option + ' ' + q('"' + R + '/key file"')),
         False, r'unresolv.*(?:configuration|local program|connection|option)', (option,))

# Rsync tokenises its transport itself. The supported intersection is a plain
# whitespace-separated SSH command; retained quoting or escapes are unresolved.
transport_boundary = r'unresolv.*rsync.*(?:rsh|transport|grammar)'
for key, transport in (
    ('plain', 'ssh'),
    ('port', 'ssh -p 2222'),
    ('identity', 'ssh -i ' + rf),
    ('setting', 'ssh -o IdentityFile=' + rf),
):
    case('F4-3', 'transport-' + key,
         'rsync --rsh=' + q(transport) + ' ' + q(rf) + ' ' + H + ':/remote/input.txt')
for grant_key, directory in (('granted', R), ('outside', U)):
    for key, transport in (
        ('double-quotes', 'ssh -i "' + directory + '/key file"'),
        ('single-quotes', "ssh -i '" + directory + "/key file'"),
        ('backslash', 'ssh -i ' + directory + r'/key\ file'),
        ('config-quotes', 'ssh -o IdentityFile="' + directory + '/key"'),
        ('concatenated-quotes', 'ssh -i ' + directory + '/ke"y"'),
    ):
        case('F4-3', 'transport-' + key + '-' + grant_key,
             'rsync -e ' + q(transport) + ' ' + q(rf) + ' ' + H + ':/remote/input.txt',
             False, transport_boundary)
for key, transport in (
    ('operator', 'ssh; true'),
    ('expansion', 'ssh -i $IDENTITY'),
    ('glob', 'ssh -i ' + R + '/key*'),
    ('control', 'ssh\n-p 2222'),
    ('trailing-operator', 'ssh -i ' + rf + ';'),
    ('escaped-space-host', 'ssh -i ' + rf + r'\ ' + X),
    ('tab-host', 'ssh -i ' + rf + '\t' + X),
):
    case('F4-3', 'transport-' + key,
         'rsync --rsh=' + q(transport) + ' ' + q(rf) + ' ' + H + ':/remote/input.txt',
         False, transport_boundary)
for key, transport in (('identity', 'ssh -i ' + uf), ('setting', 'ssh -o IdentityFile=' + uf)):
    case('F4-3', 'transport-plain-' + key + '-outside',
         'rsync -e ' + q(transport) + ' ' + q(rf) + ' ' + H + ':/remote/input.txt', False, READ, (U,))

# A supplied transport destination must not consume rsync's runtime destination;
# an option host equal to the internal placeholder remains a real network effect.
for key, transport in (
    ('ordinary', 'ssh ' + H),
    ('collision', 'ssh transport.invalid'),
    ('collision-option', 'ssh transport.invalid -i ' + uf),
    ('collision-terminator', 'ssh -- transport.invalid'),
):
    case('F4-3', 'transport-destination-' + key,
         'rsync -e ' + q(transport) + ' ' + q(rf) + ' ' + H + ':/remote/input.txt',
         False, transport_boundary)
for key, option in (
    ('hostname', '-o HostName=transport.invalid'),
    ('jump', '-J transport.invalid'),
    ('proxyjump', '-o ProxyJump=transport.invalid'),
):
    command = 'rsync -e ' + q('ssh ' + option) + ' ' + q(rf) + ' ' + H + ':/remote/input.txt'
    case('F4-3', 'transport-option-host-' + key + '-granted', command, network=[H, 'transport.invalid'])
    case('F4-3', 'transport-option-host-' + key + '-outside', command, False, HOST, ('transport.invalid',))

# FOLD4_OPTIONS_END

# Final legs verify read-only execution, with controls on this same run.
result('controls', 'quiet-checker', 'checker decisions produce no unexpected stdout', quiet.getvalue() == '', quiet.getvalue())
planted_stdout = io.StringIO()
with contextlib.redirect_stdout(planted_stdout):
    print('planted output')
result('controls', 'quiet-positive', 'stdout detector catches a planted line', bool(planted_stdout.getvalue()))

after = manifest()
result('controls', 'manifest-unchanged', 'read-only copy checksum manifest is unchanged', bool(before) and before == after)
planted = dict(after)
planted['sentinel'] = ('file', 0o444, 'different')
result('controls', 'manifest-positive', 'checksum manifest detects a planted change', before != planted)
# The raw descriptor calls count as writes too (os.open, os.write). The checker's one writer,
# _unplaced_append, is scanned by N02 below, which requires every write hit to lie inside it; so here
# its span and the read-only os.open line of _unplaced_read are blanked by name (a checker without
# them is scanned whole), and planted copies prove that both new families, and the blanking, hit.
write_pattern = (r"open\([^)]*['\"][wax]|\bos\.(remove|unlink|rename|replace|mkdir|makedirs|rmdir)\b|"
                 r'\bshutil\.|\b(subprocess|Popen)\b|\bos\.symlink\b|\bos\.open\(|\bos\.write\(')


def logger_writer_blanked(text):
    rows = text.split('\n')

    def span(name):
        start = next((i for i, row in enumerate(rows) if row.startswith('def ' + name + '(')), None)
        if start is None:
            return set()
        end = next((i for i in range(start + 1, len(rows)) if rows[i].startswith('def ')), len(rows))
        return set(range(start, end))
    blank = span('_unplaced_append') | {i for i in span('_unplaced_read') if 'os.open(' in rows[i]
                                        and 'O_RDONLY' in rows[i]
                                        and not re.search(r'O_WRONLY|O_RDWR|O_APPEND|O_CREAT', rows[i])}
    return '\n'.join('' if i in blank else row for i, row in enumerate(rows))


def planted_in_reader(text, line):
    rows = text.split('\n')
    at = next((i for i, row in enumerate(rows) if row.startswith('def _unplaced_read(')), None)
    return '\n'.join(rows[:at + 1] + [line] + rows[at + 1:]) if at is not None else line + '\n' + text


checker_text = checker.read_text()
for key, label, source_text, want in (
        ('write-grep-clean', 'source write-pattern grep with planted positive control',
         logger_writer_blanked(checker_text), 1),
        ('write-grep-positive', 'source write-pattern grep with planted positive control', 'open("x", "w")\n', 0),
        ('write-grep-positive-os-open', 'a planted os.open call hits the write pattern',
         'fd = os.open("x", os.O_WRONLY)\n', 0),
        ('write-grep-positive-os-write', 'a planted os.write call hits the write pattern', 'os.write(fd, b"x")\n', 0),
        ('write-grep-positive-outside-writer', 'an os.write planted outside the logger\'s writer survives the blanking',
         logger_writer_blanked('os.write(1, b"")\n' + checker_text), 0),
        ('write-grep-positive-reader-write', 'a writing os.open planted in the report\'s reader survives the blanking',
         logger_writer_blanked(planted_in_reader(checker_text, '    os.open(path, os.O_WRONLY)')), 0)):
    scan = subprocess.run(['grep', '-nE', write_pattern], input=source_text, text=True, capture_output=True)
    result('controls', key, label,
           scan.returncode == want and not scan.stderr and bool(scan.stdout) == (want == 0),
           repr((scan.returncode, scan.stdout, scan.stderr)))
for group, counts in groups.items():
    print('SSH_GROUP', group, 'PASS', counts[0], 'FAIL', counts[1])
print('SSH_COUNTS', passed, failed)
SSH_FAMILY_TEST_END
SSH_OUT=$("$PY" -B "$F/ssh-tests.py" "$FENCE" "$F")
SSH_RC=$?
printf '%s\n' "$SSH_OUT"
[ "$SSH_RC" = 0 ] || { echo "PROBE FAILED: SSH checks exited $SSH_RC"; exit 2; }
SSH_COUNTS=$(printf '%s\n' "$SSH_OUT" | tail -1)
case "$SSH_COUNTS" in
  'SSH_COUNTS '*) SSH_PASS=$(printf '%s\n' "$SSH_COUNTS" | awk '{print $2}')
                 SSH_FAIL=$(printf '%s\n' "$SSH_COUNTS" | awk '{print $3}') ;;
  *) echo "PROBE FAILED: SSH checks omitted their counts"; exit 2 ;;
esac
PASS=$((PASS + SSH_PASS)); FAIL=$((FAIL + SSH_FAIL))
# SSH_MATRIX_END

# UNPLACED_READS_BEGIN
echo "== unplaced reads: logged, never refused =="
# N04: every leg below runs with the run id cleared and the store at this fixture, except where the
# block sets them itself.
echo "  note — LLM_WIKI_LANE_RUN=${LLM_WIKI_LANE_RUN-<unset>} LLM_WIKI_STORE=${LLM_WIKI_STORE-<unset>}"
if [ -z "${LLM_WIKI_LANE_RUN+x}" ] && [ "${LLM_WIKI_STORE:-}" = "$F/store" ] && [ "${LLM_WIKI_PROGRESS_DIR:-}" = "$F/notes" ]; then
  ok "N04: the run id is unset and the store and scratch folder are this fixture's"
else no "N04: a leg could reach a live run's log  [run=${LLM_WIKI_LANE_RUN-<unset>} store=${LLM_WIKI_STORE-<unset>}]"; fi
cat > "$F/unplaced-tests.py" <<'UNPLACED_READS_TEST_END'
import concurrent.futures
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

# Unplaced reads: logged, never refused (owner decision 2026-10-23). Every leg needs behaviour only
# the logging checker has (a log line, a trace, a note, a report verdict or a sentinel), so the
# pristine-copy control fails them; a missing function or a crash fails its own leg, never the block.
fence_path, hook_path, root = sys.argv[1:4]
sys.dont_write_bytecode = True
pristine_path = os.environ.get('FENCE_PRISTINE') or None
passed = failed = 0


def result(lid, label, good, detail=''):
    global passed, failed
    passed += bool(good)
    failed += not good
    print(('  ok   — ' if good else 'FAIL   — ') + 'unplaced ' + lid + ': ' + label
          + ('' if good else '  [' + str(detail)[:400] + ']'))


class Missing(Exception):
    pass


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lf = load('unplaced_fence', fence_path)
pristine = load('unplaced_pristine', pristine_path) if pristine_path and os.path.isfile(pristine_path) else None


def need(name):
    value = getattr(lf, name, None)
    if value is None:
        raise Missing('the checker has no ' + name)
    return value


FX = os.path.join(root, 'unplaced')
RUN, LANE, SID, HSID = 'fixture-run', 'L1', 'sid-1', 'sid-h'
R, O, WD, CWD = (os.path.join(FX, p) for p in ('granted', 'elsewhere', 'writable', 'cwd'))
S, N, LH, STATE = (os.path.join(FX, p) for p in ('store', 'notes', 'lanehome', 'state'))


def REC(*parts):
    return os.path.join(S, 'spawn-records', *parts)


LOG, NOTE = REC(RUN + '-unplaced-reads.jsonl'), REC(RUN + '-unplaced-reads.failed')
LINE_CAP, LOG_CAP = 4096, 8 * 1024 * 1024

# CASES_BEGIN (the build reads this table to record today's decisions from the base copy)
MUST_LOG = [
    ('L01', 'B=' + O + '/outside.txt; strings "$B"', 'operand'), ('L02', 'strings "$B"', 'operand'),
    ('L03', 'cat ' + O + '/outside.txt$X', 'operand'), ('L04', 'cat "$(cat ' + O + '/outside.txt)"', 'operand'),
    ('L05', 'cat ' + O + '/outside.txt$((0))', 'operand'), ('L06', 'cat ' + O + '/{outside.txt,none}', 'operand'),
    ('L07', "cat $'\\x2f'" + O[1:] + '/outside.txt', 'operand'), ('L08', "sh -c 'cat \"$F\"'", 'shell-code'),
    ('L09', "eval 'cat " + O + "/outside.txt'", 'shell-code'),
    ('L10', 'find ' + R + " -exec sh -c 'cat " + O + "/outside.txt' \\;", 'shell-code'),
    ('L11', 'cat <<EOF\n$(cat ' + O + '/outside.txt)\nEOF', 'heredoc'), ('L12', 'cat < "$F"', 'input'),
    ('L13', '"$P" ' + R + '/inside.txt', 'program'), ('L14', 'X=$(cat "$F")', 'assignment'),
    ('L15', "# don't\ncat \"$F\"", 'operand'), ('L16', 'cd "$D" && cat x', 'operand'),
    ('L17', 'echo "$(cat ' + O + '/outside.txt)"', 'operand'), ('L18', 'X="$(cat ' + O + '/outside.txt)"', 'assignment'),
    ('L19a', 'cat 2>&1 "$F"', 'operand'), ('L19b', 'cat <&- "$F"', 'operand'),
    ('L20', "bash <<'EOF'\ncat " + O + '/outside.txt\nEOF', 'shell-code'), ('L21', 'bash <<EOF\ncat "$F"\nEOF', 'shell-code'),
    ('L22', "bash <<< 'cat " + O + "/outside.txt'", 'shell-code'), ('L23', "echo 'cat " + O + "/outside.txt' | sh", 'shell-code'),
    ('L24', "sh -o pipefail -c 'cat \"$F\"'", 'shell-code'),
    ('L25', "timeout 5 sh -o pipefail -c 'cat " + O + "/outside.txt'", 'shell-code'),
    ('L26', "bash -cx 'cat " + O + "/outside.txt'", 'shell-code'), ('L27', 'rg --files "$D"', 'operand'),
    ('L28', 'cat ' + O + '/outside.txt$[0]', 'operand'), ('L29', "trap 'cat " + O + "/outside.txt' EXIT", 'shell-code'),
    ('L30', "alias c='cat \"$F\"'", 'shell-code'),
]
MUST_NOT_LOG = [
    ('Q01', 'cat ' + R + '/inside.txt'), ('Q02', "awk '{print $1}' " + R + '/inside.txt'), ('Q03', 'echo "$X"'),
    ('Q04', '[ $? -eq 0 ] && echo ok'), ('Q05', 'grep -n "$PAT" ' + R + '/inside.txt'), ('Q06', 'X=$Y; echo ok'),
    ('Q07', 'sleep $((N*60))'), ('Q08', 'cat \\$HOME/x'), ('Q09', "cat <<'EOF'\n$(cat " + O + '/outside.txt)\nEOF'),
    ('Q10', "sh -c 'cat " + R + "/inside.txt'"), ('Q11', 'bash ' + R + '/script.sh'), ('Q12', 'sleep $[N*60]'),
    ('Q13', 'rg -n "$PAT" ' + R + '/inside.txt'), ('Q14', 'cat ' + R + '/inside.txt | grep -c bash'),
]
STILL_REFUSED = [('D01', 'strings ' + O + '/outside.txt'), ('D02', 'cat "$F" > "$OUT"'), ('D03', 'X="$Y" cat x')]
# CASES_END
SENTINEL = 'strings "$B"'                     # L02, the must-log command the premise legs use


def manifest(top, skip=None):
    out = {}
    for base, dirs, files in os.walk(top):
        if skip and os.path.realpath(base) == os.path.realpath(skip):
            dirs[:] = []
            continue
        dirs.sort()
        for name in sorted(dirs) + sorted(files):
            p = os.path.join(base, name)
            if skip and os.path.realpath(p) == os.path.realpath(skip):
                continue
            st = os.lstat(p)
            digest = None
            if stat.S_ISREG(st.st_mode):
                try:
                    with open(p, 'rb') as h:
                        digest = hashlib.sha256(h.read()).hexdigest()
                except OSError as exc:
                    digest = 'unreadable ' + type(exc).__name__
            elif stat.S_ISLNK(st.st_mode):
                digest = 'link ' + os.readlink(p)
            out[p] = (st.st_mode, digest)
    return out


def ts_at(seconds, zone=None):
    return (datetime.fromtimestamp(seconds, zone) if zone else datetime.fromtimestamp(seconds).astimezone()
            ).strftime('%Y-%m-%dT%H:%M:%S%z')


def write_record(first_ts=None, lanes=(('L1', True, 2),), extra=()):
    rows = [{'ts': first_ts or ts_at(time.time() + 2), 'run': RUN, 'event': 'run-open', 'session': HSID}]
    for lane, bash, allows in lanes:
        rows.append({'ts': 'x', 'run': RUN, 'lane': lane, 'event': 'lane-open',
                     'tools': ['Read', 'Bash'] if bash else ['Read', 'Grep']})
        if allows is not None:
            rows.append({'ts': 'x', 'run': RUN, 'lane': lane, 'event': 'lane-closed',
                         'denials': {'fence': 0, 'fence_allows': allows}, 'transcript': '/x/%s.jsonl' % lane})
    rows += list(extra)
    with open(REC(RUN + '.jsonl'), 'w') as h:
        h.write(''.join(json.dumps(r) + '\n' for r in rows))


def setup(**record):
    os.chdir(root)
    if os.path.lexists(FX):
        for base, dirs, _ in os.walk(FX):
            for d in dirs:
                p = os.path.join(base, d)
                if not os.path.islink(p):
                    os.chmod(p, 0o700)
        shutil.rmtree(FX)
    for d in (R, O, WD, CWD, REC(), N, LH, STATE):
        os.makedirs(d)
    for path, body in ((os.path.join(R, 'inside.txt'), 'INSIDE\n'), (os.path.join(R, 'script.sh'), 'echo hi\n'),
                       (os.path.join(O, 'outside.txt'), 'OUTSIDE\n')):
        with open(path, 'w') as h:
            h.write(body)
    with open(REC(RUN + '-grants.json'), 'w') as h:
        h.write(json.dumps({'grants': [R], 'writes': [WD]}))
    shutil.copyfile(fence_path, os.path.join(LH, 'lane-fence.py'))
    os.utime(os.path.join(LH, 'lane-fence.py'), (time.time() - 120, time.time() - 120))
    write_record(**record)
    os.chdir(CWD)
    os.environ.update(LLM_WIKI_STORE=S, LLM_WIKI_PROGRESS_DIR=N, LLM_WIKI_LANE_HOME=LH, LLM_WIKI_LANE_GRANTS=R,
                      LLM_WIKI_LANE_WRITES=WD, LLM_WIKI_LANE_NETWORK='', LLM_WIKI_FENCE_ROLE='',
                      LLM_WIKI_LANE_RUN=RUN, LLM_WIKI_LANE_ID=LANE)


def lines():
    if not os.path.isfile(LOG) or os.path.islink(LOG):
        return []
    with open(LOG, 'rb') as h:
        return [json.loads(l) for l in h.read().split(b'\n') if l]


def event(cmd, sid=SID, hook=True):
    e = {'session_id': sid, 'cwd': CWD, 'tool_name': 'Bash', 'tool_input': {'command': cmd}}
    if hook:
        e['hook_event_name'] = 'PreToolUse'
    return e


def composed(action, reason):
    if action == 'silent':
        return ''
    return json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': action,
                                              'permissionDecisionReason': reason}}) + '\n'


def today(module, cmd, role):
    """The decision bytes without any logger: what the hook prints for this command today."""
    head = role == 'head'
    return composed(*module.check(event(cmd), [module.norm(R)], [module.norm(WD)], head=head))


def run_lane(cmd, sid=SID, hook=True, run=RUN, module=None):
    """The lane hook in-process: the checker's own main(), stdin and argv swapped. (stdout, stderr, exit)."""
    module = module or lf
    saved_run = os.environ.get('LLM_WIKI_LANE_RUN')
    if run is None:
        os.environ.pop('LLM_WIKI_LANE_RUN', None)
    else:
        os.environ['LLM_WIKI_LANE_RUN'] = run
    out, err, code = io.StringIO(), io.StringIO(), 'returned'
    saved = sys.stdin, sys.argv
    sys.stdin, sys.argv = io.StringIO(json.dumps(event(cmd, sid, hook))), [fence_path]
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                module.main()
            except SystemExit as exc:
                code = exc.code
    finally:
        sys.stdin, sys.argv = saved
        if saved_run is None:
            os.environ.pop('LLM_WIKI_LANE_RUN', None)
        else:
            os.environ['LLM_WIKI_LANE_RUN'] = saved_run
    return out.getvalue(), err.getvalue(), code


def run_head(cmd, sid=HSID, hook=True, run=RUN):
    """The head hook's wiring in-process (check, then the guarded recorder on anything but deny).
    The real hook is driven as a process by H1, H2 and P09."""
    e = event(cmd, sid, hook)
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        action, reason = lf.check(e, [lf.norm(R)], [lf.norm(WD)], head=True)
        if action == 'deny':
            sys.stdout.write(composed(action, reason))
        else:
            recorder = getattr(lf, 'record_unplaced_reads', None)
            if recorder is not None:
                try:
                    recorder(e, S, run, 'head')
                except BaseException as exc:
                    sys.stderr.write('[head-fence] unplaced-reads skipped (%s)\n' % type(exc).__name__)
    return out.getvalue(), err.getvalue()


def run_role(cmd, role, **kw):
    if role == 'lane':
        out, err, code = run_lane(cmd, **kw)
        return out, err, code
    out, err = run_head(cmd, **kw)
    return out, err, 0


def baseline(cmd, role):
    """The decision bytes to match: the pristine checker's when FENCE_PRISTINE is set, else today()."""
    if pristine is not None and role == 'lane':
        return run_lane(cmd, sid='sid-base', run='', module=pristine)[0]
    return today(pristine or lf, cmd, role)


def report(**env):
    fn = need('report_unplaced_reads')
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = fn(RUN, 60)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return rc, buf.getvalue()


def composed_lines(out):
    return [l for l in out.splitlines() if not l.startswith('    $ ') and not l.startswith('[')]


def none_count(out):
    return sum(l.count('none') for l in composed_lines(out))


def last(out):
    return out.splitlines()[-1] if out.strip() else ''


def leg(lid, label, fn):
    try:
        good, detail = fn()
    except Exception as exc:          # a missing function or a crash fails this leg, never the block
        good, detail = False, 'raised %s: %s' % (type(exc).__name__, exc)
    result(lid, label, good, detail)


IDENTITY = []                          # (case, role, stdout identical to the baseline, an L case logged)


def must_log(cid, cmd, kind):
    def fn():
        for role, who in (('lane', 'lane:' + LANE), ('head', 'head')):
            setup()
            want = baseline(cmd, role)
            out, err, code = run_role(cmd, role)
            got = lines()
            IDENTITY.append((cid, role, out == want, any(l.get('n', 0) >= 1 for l in got)))
            cleared = '"permissionDecision": "allow"' in out if role == 'lane' else out == ''
            if out != want or not cleared or code != 0:
                return False, '%s decision changed: %r vs today %r (exit %r)' % (role, out, want, code)
            if not (len(got) == 1 and got[0].get('n', 0) >= 1 and got[0].get('who') == who
                    and kind in [k for k, _ in got[0].get('reads', [])] and not err):
                return False, '%s: want one %s entry, got %r stderr %r' % (role, kind, got, err)
        return True, ''
    return fn


def must_not_log(cid, cmd):
    def fn():
        for role, who in (('lane', 'lane:' + LANE), ('head', 'head')):
            setup()
            want = baseline(cmd, role)
            out, err, code = run_role(cmd, role)
            got = lines()
            IDENTITY.append((cid, role, out == want, None))
            cleared = '"permissionDecision": "allow"' in out if role == 'lane' else out == ''
            if out != want or not cleared or code != 0:
                return False, '%s decision changed: %r vs today %r' % (role, out, want)
            if not (len(got) == 1 and got[0].get('n') == 0 and got[0].get('reads') == [] and got[0].get('cmd') == ''
                    and got[0].get('who') == who and not err):
                return False, '%s: want exactly one trace line, got %r stderr %r' % (role, got, err)
        return True, ''
    return fn


def still_refused(cmd):
    def fn():
        for role in ('lane', 'head'):
            setup()
            want = baseline(cmd, role)
            out, err, code = run_role(cmd, role)
            if out != want or '"permissionDecision": "deny"' not in out or os.path.lexists(LOG):
                return False, '%s: want today\'s deny and no log, got %r %r' % (role, out, lines())
            run_role(SENTINEL, role)                    # the sentinel: the logger is live in this fixture
            got = lines()
            if not (len(got) == 1 and got[0].get('n') == 1):
                return False, '%s: the sentinel L02 wrote %r' % (role, got)
        return True, ''
    return fn


def watched():
    """Everything this block must leave alone: the suite fixture outside the block's own folder, and
    the checker and hook files under test."""
    found = manifest(root, skip=FX)
    for path in (fence_path, hook_path):
        with open(path, 'rb') as h:
            found[path] = (os.lstat(path).st_mode, hashlib.sha256(h.read()).hexdigest())
    return found


print('UNPLACED fence=%s pristine=%s' % (fence_path, pristine_path or 'none given'))
outside_before = watched()
for cid, cmd, kind in MUST_LOG:
    leg(cid, 'must-log (%s), both roles: today\'s decision bytes and one %s entry' % (cid, kind), must_log(cid, cmd, kind))
for cid, cmd in MUST_NOT_LOG:
    leg(cid, 'must-not-log (%s), both roles: today\'s decision bytes and only the session trace' % cid,
        must_not_log(cid, cmd))
for cid, cmd in STILL_REFUSED:
    leg(cid, 'still refused (%s), both roles: today\'s deny, no log; the L02 sentinel then logs' % cid, still_refused(cmd))


def note_lines():
    if not os.path.isfile(NOTE):
        return []
    with open(NOTE) as h:
        return h.read().splitlines()


def p01():
    for role in ('lane', 'head'):
        setup()
        os.mkdir(LOG)
        want = baseline(SENTINEL, role)
        out, err, code = run_role(SENTINEL, role)
        if out != want or code != 0 or err.count('\n') != 1 or not err.startswith('[unplaced-reads]') or len(note_lines()) != 1:
            return False, '%s: %r %r %r' % (role, out, err, note_lines())
    return True, ''


def p02():
    victim = os.path.join(R, 'victim.txt')
    with open(victim, 'w') as h:
        h.write('UNCHANGED\n')
    os.symlink(victim, LOG)
    out, err, _ = run_role(SENTINEL, 'head')
    with open(victim) as h:
        body = h.read()
    return out == '' and body == 'UNCHANGED\n' and len(note_lines()) == 1, (out, body, err, note_lines())


def nothing_written():
    return (not os.path.lexists(LOG) and not os.path.lexists(NOTE) and not os.listdir(N))


def p03():
    os.rename(REC(RUN + '.jsonl'), REC(RUN + '.away'))
    out, err, _ = run_role(SENTINEL, 'lane')
    quiet_record = nothing_written() and not err and '"allow"' in out
    os.rename(REC(RUN + '.away'), REC(RUN + '.jsonl'))
    shutil.move(REC(), os.path.join(S, 'records-away'))
    out, err, _ = run_role(SENTINEL, 'lane')
    quiet_folder = (not os.path.lexists(REC()) and not os.listdir(N) and not err and '"allow"' in out)
    shutil.move(os.path.join(S, 'records-away'), REC())
    run_role(SENTINEL, 'lane')
    got = lines()
    return quiet_record and quiet_folder and len(got) == 1 and got[0].get('n') == 1, (quiet_record, quiet_folder, got)


def p04():
    out, err, _ = run_lane(SENTINEL, hook=False)
    bare = nothing_written() and not err and '"allow"' in out
    run_lane(SENTINEL)
    got = lines()
    return bare and len(got) == 1 and got[0].get('n') == 1, (bare, got)


def p05():
    quiet = True
    for bad in (None, '', '../x'):
        out, err, _ = run_lane(SENTINEL, run=bad)
        quiet = quiet and nothing_written() and not err and '"allow"' in out
    run_lane(SENTINEL)
    got = lines()
    return quiet and len(got) == 1 and got[0].get('n') == 1, (quiet, got)


def p06():
    need('record_unplaced_reads')
    saved = lf.unplaced_reads

    def boom(command, steps=None):
        raise IndexError('planted')
    lf.unplaced_reads = boom
    try:
        out, err, code = run_lane(SENTINEL)
    finally:
        lf.unplaced_reads = saved
    got = lines()
    return (out == baseline(SENTINEL, 'lane') and code == 0 and len(got) == 1
            and got[0].get('reads') == [ ['scan-error', 'IndexError'] ], (out, got))


def p07():
    os.mkdir(LOG)
    os.mkdir(NOTE)
    out, err, code = run_lane(SENTINEL)
    store_after = sorted(os.listdir(REC()))
    unchanged = (os.path.isdir(LOG) and not os.listdir(LOG) and os.path.isdir(NOTE) and not os.listdir(NOTE)
                 and store_after == sorted([RUN + '.jsonl', RUN + '-grants.json', os.path.basename(LOG), os.path.basename(NOTE)]))
    return (out == baseline(SENTINEL, 'lane') and code == 0 and err.count('\n') == 1 and 'note failed' in err
            and unchanged, (out, err, store_after))


def p08():
    with open(LOG, 'wb') as h:
        h.write(b'x' * (LOG_CAP - 10))
    run_lane(SENTINEL)
    size = os.path.getsize(LOG)
    rc, out = report()
    return size == LOG_CAP - 10 and rc == 1 and 'cap reached' in out, (size, rc, out[-200:])


def hook_tree(name, checker_source, plant=None):
    """A fixture project holding a copy of the checker (planted when asked) and of the head hook."""
    project = os.path.join(FX, 'tree-' + name, 'project')
    os.makedirs(os.path.join(project, '.claude', 'skills', 'delegate'))
    os.makedirs(os.path.join(project, '.claude', 'hooks'))
    with open(checker_source, encoding='utf-8') as h:
        text = h.read()
    if plant:
        anchor = '\nif __name__ == "__main__":\n'
        if text.count(anchor) != 1:
            raise Missing('the checker has no single main guard to plant before')
        text = text.replace(anchor, '\n' + plant + anchor, 1)
    checker = os.path.join(project, '.claude', 'skills', 'delegate', 'lane-fence.py')
    with open(checker, 'w', encoding='utf-8') as h:
        h.write(text)
    hook = os.path.join(project, '.claude', 'hooks', 'head-fence.py')
    shutil.copyfile(hook_path, hook)
    return checker, hook, project


def lane_env(**more):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', LLM_WIKI_LANE_GRANTS=R, LLM_WIKI_LANE_WRITES=WD,
               LLM_WIKI_LANE_NETWORK='', LLM_WIKI_FENCE_ROLE='', LLM_WIKI_LANE_RUN=RUN, LLM_WIKI_LANE_ID=LANE,
               LLM_WIKI_STORE=S, LLM_WIKI_PROGRESS_DIR=N)
    env.update(more)
    return env


def head_env(project, **more):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', LLM_WIKI_STORE=S, AIMYTH_STATE_DIR=STATE,
               AIMYTH_HANDSOFF='1', AIMYTH_HANDSOFF_RUN=RUN, CLAUDE_PROJECT_DIR=project, LLM_WIKI_PROGRESS_DIR=N)
    env.update(more)
    return env


def proc(argv, stdin_text, env):
    return subprocess.run(argv, input=stdin_text, text=True, capture_output=True, cwd=CWD, env=env, timeout=60)


PLANT = ('def record_unplaced_reads(event, store, run, who):\n'
         '    with open(os.environ["UNPLACED_SENTINEL"], "a") as handle:\n'
         '        handle.write(who + " " + os.environ["UNPLACED_RAISE"] + "\\n")\n'
         '    if os.environ["UNPLACED_RAISE"] == "SystemExit":\n'
         '        raise SystemExit(3)\n'
         '    raise RuntimeError("planted")\n')


def p09():
    checker, hook, project = hook_tree('planted', fence_path, PLANT)
    sentinel = os.path.join(FX, 'sentinel.txt')
    lane_want = baseline(SENTINEL, 'lane')
    problems = []
    for kind in ('RuntimeError', 'SystemExit'):
        lane = proc([sys.executable, '-B', checker], json.dumps(event(SENTINEL)),
                    lane_env(UNPLACED_SENTINEL=sentinel, UNPLACED_RAISE=kind))
        if lane.returncode != 0 or lane.stdout != lane_want:
            problems.append(('lane', kind, lane.returncode, lane.stdout, lane.stderr))
        head = proc([sys.executable, '-B', hook], json.dumps(event(SENTINEL, HSID)),
                    head_env(project, UNPLACED_SENTINEL=sentinel, UNPLACED_RAISE=kind))
        if head.returncode != 0 or head.stdout != '' or head.stderr.count('[head-fence]') != 1:
            problems.append(('head', kind, head.returncode, head.stdout, head.stderr))
    written = open(sentinel).read().splitlines() if os.path.isfile(sentinel) else []
    return not problems and len(written) == 4, (problems, written)


def p10():
    if not IDENTITY:
        return False, 'no L or Q case ran'
    differs = [(c, r) for c, r, same, _ in IDENTITY if not same]
    unlogged = [(c, r) for c, r, _, logged in IDENTITY if logged is False]
    cases = {c for c, _, _, _ in IDENTITY}
    return (not differs and not unlogged and len(cases) == len(MUST_LOG) + len(MUST_NOT_LOG),
            (differs[:4], unlogged[:4], len(cases)))


CHILD = ('import importlib.util,json,sys\n'
         'spec=importlib.util.spec_from_file_location("lfc",sys.argv[1]); m=importlib.util.module_from_spec(spec); '
         'spec.loader.exec_module(m)\n')


def child(code, *args):
    """A child with a 5-second limit (set by judgement: a non-blocking open returns in milliseconds, a
    blocking one never), so a regression to a blocking open fails its leg instead of hanging the suite."""
    t0 = time.monotonic()
    try:
        r = subprocess.run([sys.executable, '-I', '-B', '-c', CHILD + code, fence_path] + list(args),
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5, env=lane_env())
        return time.monotonic() - t0, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return None, 'timed out', ''


RECORD_CHILD = ('print(m.record_unplaced_reads(json.loads(sys.argv[2]), sys.argv[3], sys.argv[4], "lane:L1"))\n')


def p11():
    os.mkfifo(LOG)
    took, out, err = child(RECORD_CHILD, json.dumps(event(SENTINEL)), S, RUN)
    return took is not None and took < 5 and 'failed: noted' in out and len(note_lines()) == 1, (took, out, err)


def p12():
    os.mkdir(LOG)
    os.mkfifo(NOTE)
    took, out, err = child(RECORD_CHILD, json.dumps(event(SENTINEL)), S, RUN)
    return (took is not None and took < 5 and 'failed: lost' in out and err.count('\n') == 1
            and err.startswith('[unplaced-reads]'), (took, out, err))


def p13():
    q01 = MUST_NOT_LOG[0][1]
    run_lane(q01, sid='sid-1')
    one = len(lines())
    run_lane(q01, sid='sid-1')
    two = len(lines())
    run_lane(q01, sid='sid-2')
    got = lines()
    return (one == 1 and two == 1 and [l.get('sid') for l in got] == ['sid-1', 'sid-2']
            and all(l.get('n') == 0 for l in got), got)


def p14():
    q01 = MUST_NOT_LOG[0][1]
    tag = hashlib.sha256(('lane:%s\n%s' % (LANE, SID)).encode()).hexdigest()[:16]
    open(os.path.join(N, RUN + '-unplaced-reads-seen-' + tag), 'w').close()      # the planted marker
    run_lane(q01, sid=SID)
    run_head(q01)
    got = lines()
    rc, out = report()
    return (not any(l.get('who') == 'lane:' + LANE for l in got) and any(l.get('who') == 'head' for l in got)
            and rc == 1 and '1 Claude lane(s) left no line' in out and LANE in out, (got, rc, out[-240:]))


def p15():
    blocked = os.path.join(FX, 'notes-is-a-file')
    open(blocked, 'w').close()
    os.environ['LLM_WIKI_PROGRESS_DIR'] = blocked
    try:
        out, err, _ = run_lane(MUST_NOT_LOG[0][1])
        quiet = not lines() and not err and out == baseline(MUST_NOT_LOG[0][1], 'lane')
        run_lane(SENTINEL)
    finally:
        os.environ['LLM_WIKI_PROGRESS_DIR'] = N
    got = lines()
    return quiet and len(got) == 1 and got[0].get('n') == 1, (quiet, got)


def p16():
    out, err = run_head('   ')
    quiet = out == '' and nothing_written() and not err
    run_head(SENTINEL)
    got = lines()
    return quiet and len(got) == 1 and got[0].get('n') == 1 and got[0].get('who') == 'head', (quiet, got)


def padded_line(n, size=LINE_CAP):
    """One valid head line of exactly `size` bytes (a trace when n is 0, else an L02 entry)."""
    obj = {'v': 1, 'ts': 't', 'who': 'head', 'sid': HSID, 'cwd': '/', 'n': n,
           'reads': [ ['operand', '"$B"'] ] if n else [], 'cmd': SENTINEL if n else '', 'cut': False, 'pad': ''}
    obj['pad'] = 'x' * (size - len((json.dumps(obj, separators=(',', ':')) + '\n').encode()))
    data = (json.dumps(obj, separators=(',', ':')) + '\n').encode()
    if len(data) != size:
        raise Missing('a padded line of %d bytes could not be made' % size)
    return data


def p17():
    """The check's interleaving: eight appends whose size tests all see the log one line under its cap."""
    append, cap = need('_unplaced_append'), need('UNPLACED_LOG_CAP')
    clean_log()                                   # a trace from each writer, so only the cap can warn
    line = padded_line(0)
    with open(LOG, 'ab') as h:
        h.write(b'\n' * (cap - LINE_CAP - os.path.getsize(LOG)))
    barrier, workers, original = threading.Barrier(8), set(), os.fstat

    def gated(fd):
        status = original(fd)
        if threading.current_thread().name in workers:
            barrier.wait(timeout=10)
        return status

    def one(_):
        workers.add(threading.current_thread().name)
        return append(LOG, line, cap)
    lf.os.fstat = gated
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            statuses = list(pool.map(one, range(8)))
    finally:
        lf.os.fstat = original
    size = os.path.getsize(LOG)
    rc, out = report()
    return (statuses == ['ok'] * 8 and size > cap and rc == 1 and 'cap reached' in out
            and 'PROBE FAILED' not in out and 'INCOMPLETE' in last(out),
            ('statuses', statuses, 'bytes past the cap', size - cap, rc, out[-300:]))


def p18():
    """A log past the reader's bound: its first bound bytes are read (whole lines), the rest named."""
    bound = need('UNPLACED_LOG_CAP') + need('UNPLACED_READ_SLACK')
    clean_log()
    entry = padded_line(1, 512)
    with open(LOG, 'ab') as h:
        h.write(b'\n' * (bound - 5 - len(entry) - os.path.getsize(LOG)) + entry + entry + entry)
    size = os.path.getsize(LOG)
    rc, out = report()
    return (size > bound and rc == 1 and 'cap reached' in out and "runs past this reader's" in out
            and 'PROBE FAILED' not in out and '\nentries: 1 ' in out and 'INCOMPLETE' in last(out),
            (size, bound, rc, out[-400:]))


def p19():
    """A failure-note file past its read bound is counted from the bytes read, never 'unreadable'."""
    bound = need('UNPLACED_NOTE_CAP') + need('UNPLACED_READ_SLACK')
    clean_log()
    note = b'{"v":1,"ts":"t","who":"head","error":"OSError: planted","n":1}\n'
    with open(NOTE, 'wb') as h:
        h.write(note * (bound // len(note) + 3))
    rc, out = report()
    return (rc == 1 and 'at least %d write failure note(s)' % (bound // len(note)) in out
            and 'unreadable' not in out and 'PROBE FAILED' not in out, (rc, out[-300:]))


for lid, label, fn in (
        ('P01', 'a directory at the log path: decision unchanged, one stderr line, one note (both roles)', p01),
        ('P02', 'a symlink at the log path is never followed: the victim unchanged, one note', p02),
        ('P03', 'no run record, or no spawn-records folder: nothing written; restored, one entry', p03),
        ('P04', 'a bare payload with no hook_event_name writes nothing; the hook event writes one entry', p04),
        ('P05', 'LLM_WIKI_LANE_RUN unset, empty or ../x writes nothing; the fixture run writes one entry', p05),
        ('P06', 'the scan raises: the decision stands and one scan-error line is written', p06),
        ('P07', 'log and note both unwritable: the decision stands, one stderr line naming the failed note', p07),
        ('P08', 'a log 10 bytes under its cap: nothing appended; the report says cap reached', p08),
        ('P09', 'a recorder raising RuntimeError or SystemExit past its guard changes no decision (real hooks)', p09),
        ('P11', 'a named pipe at the log path: returns within 5 s, noted', p11),
        ('P12', 'a named pipe at the note path and a directory at the log: returns within 5 s, lost', p12),
        ('P13', 'one trace per writer session (sid-1 twice, then sid-2)', p13),
        ('P14', 'a planted marker suppresses the lane trace, and the report names the lane', p14),
        ('P15', 'no marker can be made: no trace and no stderr; an entry is still written', p15),
        ('P16', 'a blank head command writes nothing; L02 then writes one head entry', p16)):
    setup()
    leg(lid, label, fn)
leg('P10', 'stdout identity for every L and Q case in both roles%s, and every L case logged'
    % (' against FENCE_PRISTINE' if pristine else ' against the decision composed without the logger'), p10)


def clean_log(entries=0, head=True, lane=True):
    q01 = MUST_NOT_LOG[0][1]
    if lane:
        run_lane(q01, sid=SID)
    if head:
        run_head(q01)
    for k in range(entries):
        run_head('strings "$B%d"' % (k % 2))


def r01():
    clean_log(entries=3)
    rc, out = report()
    return rc == 0 and last(out).startswith('VERDICT: complete \u00b7 3 recorded') and 'in 2 distinct command(s)' in out, (rc, out[-300:])


def r02():
    clean_log()
    rc, out = report()
    return rc == 0 and last(out) == 'VERDICT: complete \u00b7 none recorded' and none_count(out) == 1, (rc, out[-300:])


def r03():
    rc, out = report()
    return rc == 2 and last(out).startswith('PROBE FAILED: no log') and none_count(out) == 0, (rc, out)


def r04():
    os.mkdir(LOG)
    rc1, out1 = report()
    os.rmdir(LOG)
    clean_log()
    os.chmod(LOG, 0)
    try:
        rc2, out2 = report()
    finally:
        os.chmod(LOG, 0o600)
    return (rc1 == 2 and rc2 == 2 and last(out1).startswith('PROBE FAILED: cannot read')
            and last(out2).startswith('PROBE FAILED: cannot read') and none_count(out1 + out2) == 0, (rc1, out1[-120:], rc2, out2[-120:]))


def r05():
    clean_log(entries=1)
    with open(LOG, 'ab') as h:
        h.write(b'{"v":1,"ts":"2026')
    rc, out = report()
    return rc == 1 and '1 unreadable line(s)' in out and 'INCOMPLETE' in last(out) and '\nentries: 1 ' in out, (rc, out[-260:])


def r06():
    clean_log()
    with open(NOTE, 'w') as h:
        h.write('{"v":1}\n')
    rc, out = report()
    return rc == 1 and '1 write failure note(s)' in out and none_count(out) == 0, (rc, out[-260:])


def r07():
    clean_log()
    other = os.path.join(FX, 'otherhome')
    os.mkdir(other)
    with open(os.path.join(other, 'lane-fence.py'), 'w') as h:
        h.write('# an older checker\n')
    os.utime(os.path.join(other, 'lane-fence.py'), (time.time() - 120, time.time() - 120))
    rc, out = report(LLM_WIKI_LANE_HOME=other)
    return rc == 1 and 'lane-home checker differs' in out and 'INCOMPLETE' in last(out), (rc, out[-260:])


def r08():
    write_record(first_ts='2000-01-01T00:00:00+0000')
    clean_log()
    rc, out = report()
    return rc == 1 and 'installed after the run opened' in out, (rc, out[-260:])


def r09():
    fn = need('report_unplaced_reads')
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn('../etc', 60)
    out = buf.getvalue()
    return rc == 2 and out.startswith("PROBE FAILED: '../etc' is not a run id"), (rc, out)


def r10():
    clean_log()
    with open(LOG, 'a') as h:
        h.write(json.dumps({'v': 1, 'ts': 't', 'who': 'head', 'sid': 's', 'cwd': '/', 'n': 1,
                            'reads': [ ['scan-error', 'IndexError'] ], 'cmd': 'x', 'cut': False}) + '\n')
    rc, out = report()
    return rc == 1 and '1 scan error(s)' in out, (rc, out[-260:])


def r11():
    clean_log(entries=3)
    before = manifest(FX)
    rc, out = report()
    after = manifest(FX)
    tail = [l for l in out.splitlines() if l.startswith(('VERDICT:', 'PROBE FAILED:'))]
    return bool(before) and before == after and len(tail) == 1 and last(out) == tail[0], (before == after, tail)


def r12():
    write_record(lanes=(('L1', True, 2), ('L2', True, 1)))
    clean_log()
    rc, out = report()
    return rc == 1 and '1 Claude lane(s) left no line' in out and 'L2' in out, (rc, out[-260:])


def r13():
    results = []
    for lanes, extra in (((('L1', True, 2), ('L2', False, None)), ()),
                         ((('L1', True, 2), ('L2', True, 0)), ()),
                         ((('L1', True, 2), ('L2', True, 1)),
                          ({'ts': 'x', 'run': RUN, 'lane': 'L2', 'event': 'lane-spawned', 'harness': 'codex'},))):
        setup(lanes=lanes, extra=extra)
        clean_log()
        rc, out = report()
        results.append((rc, last(out), 'not expected to log: L2' in out))
    return (all(rc == 0 and tail.startswith('VERDICT: complete') for rc, tail, _ in results)
            and [named for _, _, named in results] == [True, True, False], results)


def three_files():
    own = os.path.realpath(fence_path)
    hook = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(own))), 'hooks', 'head-fence.py')
    return own, os.path.join(LH, 'lane-fence.py'), hook


def r14():
    clean_log(head=False)
    rc, out = report()
    if os.path.isfile(three_files()[2]):
        return rc == 1 and 'no line from the head' in out, (rc, out[-260:])
    return (rc == 0 and 'head-fence.py not beside this checker' in out and 'no line from the head' not in out,
            ('no head-fence.py beside the checker', rc, out[-260:]))


def r15():
    clean_log()
    newest = max(os.path.getmtime(p) for p in three_files() if os.path.isfile(p))
    stamp = ts_at(newest + 1800, timezone(timedelta(hours=-11)))
    with open(REC(RUN + '.jsonl')) as h:
        rows = h.read().splitlines()
    first = json.loads(rows[0])
    first['ts'] = stamp
    with open(REC(RUN + '.jsonl'), 'w') as h:
        h.write('\n'.join([json.dumps(first)] + rows[1:]) + '\n')
    rc, out = report()
    return rc == 0 and last(out).startswith('VERDICT: complete') and 'installed after' not in out, (stamp, rc, out[-260:])


REPORT_CHILD = 'rc=m.report_unplaced_reads(sys.argv[2], 60); print("rc", rc)\n'


def r16():
    os.mkfifo(LOG)
    need('report_unplaced_reads')
    took, out, err = child(REPORT_CHILD, RUN)
    return (took is not None and took < 5 and 'rc 2' in out and 'PROBE FAILED: cannot read' in out
            and 'not a regular file' in out, (took, out[-260:], err[-200:]))


def r17():
    open(LOG, 'w').close()
    rc, out = report()
    return rc == 1 and 'the log is empty' in out, (rc, out[-260:])


def r18():
    clean_log()
    run = subprocess.run([sys.executable, '-B', fence_path, '--unplaced-reads', RUN], stdin=subprocess.DEVNULL,
                         capture_output=True, text=True, cwd=CWD, timeout=60, env=lane_env())
    return (run.returncode in (0, 1, 2) and 'hookSpecificOutput' not in run.stdout
            and last(run.stdout).startswith(('VERDICT:', 'PROBE FAILED:')), (run.returncode, run.stdout[-200:], run.stderr[-200:]))


def write_rows(rows, newline_at_end=True):
    """The fixture run record from rows: a dict is written as one JSON line, a string as given."""
    with open(REC(RUN + '.jsonl'), 'w') as h:
        h.write('\n'.join(json.dumps(r) if isinstance(r, dict) else r for r in rows) + ('\n' if newline_at_end else ''))


def run_open_row():
    return {'ts': ts_at(time.time() + 60), 'run': RUN, 'event': 'run-open', 'session': HSID}


def lane_open_row(lane):
    return {'ts': 'x', 'run': RUN, 'lane': lane, 'event': 'lane-open', 'tools': ['Read', 'Bash']}


def premises(out):
    return next((l for l in out.splitlines() if l.startswith('premises: ')), '')


def r19():
    """The check's case: L1's lane-open cut mid-line, the log holding the head's trace only."""
    clean_log(lane=False)
    whole = json.dumps(lane_open_row('L1'))
    write_rows([run_open_row(), whole])
    rc_whole, out_whole = report()
    write_rows([run_open_row(), whole[:-1]])
    rc, out = report()
    return (rc_whole == 1 and '1 Claude lane(s) left no line' in out_whole and 'L1' in premises(out_whole)
            and rc == 1 and 'line 2 does not parse' in premises(out) and 'INCOMPLETE' in last(out)
            and not last(out).startswith('VERDICT: complete'), (rc_whole, premises(out_whole), rc, out[-300:]))


def r20():
    """The valid twin of R19: the same record with the line whole and L1's trace in the log."""
    clean_log()
    write_rows([run_open_row(), lane_open_row('L1')])
    rc, out = report()
    return rc == 0 and last(out) == 'VERDICT: complete · none recorded', (rc, out[-300:])


def r21():
    """Every other shape of a line the report cannot count: each is INCOMPLETE and named by its line."""
    clean_log()
    torn = json.dumps(lane_open_row('L2'))[:-1]
    cases = [('a torn line mid-record', [run_open_row(), torn, lane_open_row('L1')], True, 'line 2 does not parse'),
             ('a torn last line with no newline', [run_open_row(), lane_open_row('L1'), torn], False, 'line 3 does not parse'),
             ('a line that is not an object', [run_open_row(), lane_open_row('L1'), '["lane-open", "L2"]'], True,
              'line 3 is not a JSON object'),
             ('a lane-open naming no lane', [run_open_row(), lane_open_row('L1'), {'event': 'lane-open', 'tools': ['Bash']}],
              True, 'line 3 is a lane-open naming no lane'),
             ('a head start naming no session', [run_open_row(), lane_open_row('L1'), {'event': 'head-successor', 'pid': 7}],
              True, 'line 3 is a head-successor naming no session'),
             ('an object naming no event', [run_open_row(), lane_open_row('L1'), {'lane': 'L2', 'tools': ['Bash']}], True,
              'line 3 names no event')]
    results = []
    for label, rows, newline_at_end, phrase in cases:
        write_rows(rows, newline_at_end)
        rc, out = report()
        results.append((label, rc == 1 and phrase in premises(out) and 'INCOMPLETE' in last(out), rc, premises(out)[:160]))
    write_rows([run_open_row(), lane_open_row('L1')])
    rc, out = report()
    control = rc == 0 and last(out) == 'VERDICT: complete · none recorded'
    return control and all(good for _, good, _, _ in results), ([r for r in results if not r[1]][:3], control, rc)


def tree_report():
    """The report from a copy of the checker with the head hook beside it, so the head premises apply
    wherever the checker under test lives (--fence elsewhere included)."""
    checker, _, _ = hook_tree('report', fence_path)
    fn = getattr(load('unplaced_tree_report', checker), 'report_unplaced_reads', None)
    if fn is None:
        raise Missing('the checker has no report_unplaced_reads')
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(RUN, 60)
    return rc, buf.getvalue()


def two_sessions(second_traced):
    clean_log()                                   # traces from L1 and the head session sid-h
    if second_traced:
        run_head(MUST_NOT_LOG[0][1], sid='sid-second')
    write_rows([run_open_row(), lane_open_row('L1'),
                {'ts': 'x', 'run': RUN, 'event': 'head-successor', 'session_id': HSID},
                {'ts': 'x', 'run': RUN, 'event': 'run-resume', 'session': HSID},
                {'ts': 'x', 'run': RUN, 'event': 'head-successor', 'session_id': 'sid-second'},
                {'ts': 'x', 'run': RUN, 'event': 'run-resume', 'session': 'sid-second'}])
    return tree_report()


def r22():
    rc, out = two_sessions(False)
    return (rc == 1 and '1 head session(s) the run record names left no line in the log' in premises(out)
            and premises(out).rstrip().endswith(': sid-second') and 'INCOMPLETE' in last(out), (rc, premises(out)[:300]))


def r23():
    rc, out = two_sessions(True)
    return rc == 0 and last(out) == 'VERDICT: complete · none recorded', (rc, out[-300:])


def one_more_head(row, traced):
    """The report on a record whose one further head start is `row`; sid-other is traced only when asked."""
    clean_log()
    if traced:
        run_head(MUST_NOT_LOG[0][1], sid='sid-other')
    write_rows([run_open_row(), lane_open_row('L1'),
                {'ts': 'x', 'run': RUN, 'event': 'head-successor', 'session_id': HSID}, row])
    return tree_report()


def r24():
    rc, out = one_more_head({'ts': 'x', 'run': RUN, 'event': 'head-resumed', 'session_id': 'sid-other'}, False)
    return (rc == 1 and '1 head session(s) the run record names left no line in the log' in premises(out)
            and premises(out).rstrip().endswith(': sid-other') and 'INCOMPLETE' in last(out), (rc, premises(out)[:300]))


def r25():
    rc, out = one_more_head({'ts': 'x', 'run': RUN, 'event': 'run-open', 'session': 'sid-other'}, False)
    return (rc == 1 and '1 head session(s) the run record names left no line in the log' in premises(out)
            and premises(out).rstrip().endswith(': sid-other') and 'INCOMPLETE' in last(out), (rc, premises(out)[:300]))


def r26a():
    rc, out = one_more_head({'ts': 'x', 'run': RUN, 'event': 'head-resumed', 'session_id': 'sid-other'}, True)
    return rc == 0 and last(out) == 'VERDICT: complete · none recorded', (rc, out[-300:])


def r26b():
    rc, out = one_more_head({'ts': 'x', 'run': RUN, 'event': 'run-open', 'session': 'sid-other'}, True)
    return rc == 0 and last(out) == 'VERDICT: complete · none recorded', (rc, out[-300:])


def r27():
    rc, out = one_more_head({'ts': 'x', 'run': RUN, 'event': 'run-open', 'session': 'sid-other', 'session_kind': 'seed'}, False)
    return rc == 0 and last(out) == 'VERDICT: complete · none recorded', (rc, premises(out)[:300])


def r28():
    results = []
    for row, phrase in (({'ts': 'x', 'run': RUN, 'event': 'head-resumed', 'pid': 7}, 'is a head-resumed naming no session'),
                        ({'ts': 'x', 'run': RUN, 'event': 'run-open', 'session': ['not', 'a', 'name']}, 'is a run-open naming no session')):
        clean_log()
        write_rows([run_open_row(), lane_open_row('L1'), row])
        rc, out = report()
        results.append(rc == 1 and phrase in premises(out))
    return all(results), results


def r06_control():
    """R-control: the opening head and lane both have traces."""
    clean_log()
    write_rows([run_open_row(), lane_open_row('L1')])
    rc, out = tree_report()
    return (rc == 0 and premises(out) == 'premises: all hold'
            and last(out) == 'VERDICT: complete · none recorded', (rc, premises(out), last(out)))


def a06(kind, key, fields):
    control, control_detail = r22()
    results = []
    for extra in fields:
        setup()
        clean_log()
        row = dict(extra, event=kind)
        row[key] = 'sid-second'
        write_rows([run_open_row(), lane_open_row('L1'), row])
        rc, out = tree_report()
        expected = ('premises: 1 head session(s) the run record names left no line in the log though they may '
                    'have cleared a command: sid-second')
        results.append((rc == 1 and premises(out) == expected and 'INCOMPLETE' in last(out),
                        rc, premises(out), last(out)))
        setup()
        clean_log()
        run_head(MUST_NOT_LOG[0][1], sid='sid-second')
        write_rows([run_open_row(), lane_open_row('L1'), row])
        rc, out = tree_report()
        results.append((rc == 0 and premises(out) == 'premises: all hold'
                        and last(out) == 'VERDICT: complete · none recorded', rc, premises(out), last(out)))
    return control and all(r[0] for r in results), ('R22', control, control_detail, results)


def c06seed():
    control, control_detail = r22()
    results = []
    # Seed exclusion applies to validation as well as collection, including a missing or invalid id.
    for fields in ({'session': 'sid-second'}, {}, {'session': None}, {'session': '/'}, {'session': []}):
        setup()
        clean_log()
        row = dict(fields, event='run-open', session_kind='seed')
        write_rows([run_open_row(), lane_open_row('L1'), row])
        rc, out = tree_report()
        good = (rc == 0 and premises(out) == 'premises: all hold'
                and last(out) == 'VERDICT: complete · none recorded'
                and need('_unplaced_record_flaw')(row) is None
                and need('_unplaced_head_sessions')([row]) == [])
        results.append((good, rc, premises(out), last(out)))
    return control and all(r[0] for r in results), ('R22', control, control_detail, results)


def c06dedup():
    control, control_detail = r22()
    setup()
    clean_log()
    starts = [{'event': 'head-successor', 'session_id': HSID},
              {'event': 'head-resumed', 'session_id': HSID},
              {'event': 'run-resume', 'session': HSID},
              {'event': 'run-open', 'session': HSID}]
    write_rows([run_open_row(), lane_open_row('L1')] + starts + starts)
    rc, out = tree_report()
    sessions = need('_unplaced_head_sessions')(starts + starts)
    ordered = need('_unplaced_head_sessions')(
        [{'event': 'head-successor', 'session_id': 'sid-second'}] + starts
        + [{'event': 'run-resume', 'session': 'sid-second'}])
    return (control and rc == 0 and premises(out) == 'premises: all hold'
            and last(out) == 'VERDICT: complete · none recorded'
            and sessions == [HSID] and ordered == ['sid-second', HSID],
            ('R22', control, control_detail, rc, premises(out), sessions, ordered))


def p06control():
    control, control_detail = r06_control()
    setup()
    clean_log()
    write_rows([run_open_row(), lane_open_row('L1'), {'event': 'head-successor'}])
    rc, out = tree_report()
    return (control and rc == 1 and 'line 3 is a head-successor naming no session in `session_id`' in premises(out)
            and 'INCOMPLETE' in last(out), ('R-control', control, control_detail, rc, premises(out)))


def p06(kind, key):
    control, control_detail = p06control()
    results = []
    for fields in ({}, {key: None}, {key: ''}, {key: '/'}, {key: []}, {key: {}}, {key: True}):
        setup()
        clean_log()
        write_rows([run_open_row(), lane_open_row('L1'), dict(fields, event=kind)])
        rc, out = tree_report()
        phrase = 'line 3 is a %s naming no session in `%s`' % (kind, key)
        results.append((rc == 1 and phrase in premises(out) and 'INCOMPLETE' in last(out), rc, premises(out)))
    return control and all(r[0] for r in results), ('P06control', control, control_detail, results)


def p06torn():
    control, control_detail = r06_control()
    setup()
    clean_log()
    torn = json.dumps({'event': 'head-resumed', 'session_id': 'sid-second'})[:-1]
    write_rows([run_open_row(), lane_open_row('L1'), torn], newline_at_end=False)
    rc, out = tree_report()
    return (control and rc == 1 and 'line 3 does not parse' in premises(out) and 'INCOMPLETE' in last(out),
            ('R-control', control, control_detail, rc, premises(out)))


def n06_readonly():
    """The warning reporter reads a frozen fixture; the checksum and grep controls run beside it."""
    clean_log()
    write_rows([run_open_row(), lane_open_row('L1'),
                {'event': 'head-resumed', 'session_id': 'sid-second'},
                {'event': 'run-open', 'session_kind': 'seed'}])
    checker, _, _ = hook_tree('readonly-report', fence_path)
    module = load('unplaced_readonly_report', checker)
    control_path = os.path.join(FX, 'n06-manifest-control.txt')
    with open(control_path, 'wb') as handle:
        handle.write(b'a')
    modes = {}
    for base, dirs, files in os.walk(FX):
        for path in [base] + [os.path.join(base, name) for name in files]:
            mode = stat.S_IMODE(os.stat(path).st_mode)
            modes[path] = mode
            os.chmod(path, mode & ~0o222)
    try:
        before = manifest(FX)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = module.report_unplaced_reads(RUN, 60)
        out = buf.getvalue()
        after = manifest(FX)
        os.chmod(control_path, modes[control_path])
        with open(control_path, 'r+b') as handle:
            handle.write(b'b')
        os.chmod(control_path, modes[control_path] & ~0o222)
        changed = manifest(FX)
    finally:
        for path, mode in modes.items():
            os.chmod(path, mode)
    with open(checker, encoding='utf-8') as handle:
        text = handle.read()
    start, end = text.index('def _unplaced_names('), text.index('def unplaced_reads_cli(')
    pattern = (r"open\([^)]*['\"][wax]|write_(text|bytes)[ \t]*\(|"
               r'\b(subprocess|Popen|shutil)\b|os\.(system|popen|remove|unlink|rename|replace|mkdir|makedirs|'
               r'rmdir|symlink|write|open)\b')
    scans = []
    for source, expected in ((text[start:end], 1), ('open("x", "w")\n', 0)):
        scan = subprocess.run(['grep', '-nE', pattern], input=source, text=True, capture_output=True)
        if scan.returncode not in (0, 1) or scan.stderr:
            print('PROBE FAILED: Entry 06 write-pattern grep: ' + scan.stderr)
            raise SystemExit(2)
        scans.append(scan.returncode == expected and bool(scan.stdout) == (expected == 0))
    return (bool(before) and before == after and before != changed and all(scans)
            and rc == 1 and premises(out).rstrip().endswith(': sid-second') and 'INCOMPLETE' in last(out),
            (len(before), before == after, before != changed, scans, rc, premises(out)))


for lid, label, fn in (
        ('R01', '3 head entries over 2 commands: complete, 3 recorded, 2 distinct', r01),
        ('R02', 'traces only: exactly "VERDICT: complete \u00b7 none recorded", the one clean verdict', r02),
        ('R03', 'no log: PROBE FAILED, never a count, and no "none"', r03),
        ('R04', 'a directory, or mode 000, at the log path: PROBE FAILED cannot read', r04),
        ('R05', 'a torn final line: counted, INCOMPLETE', r05),
        ('R06', 'a failure note: INCOMPLETE, and no "none"', r06),
        ('R07', 'a differing lane-home copy: INCOMPLETE', r07),
        ('R08', 'the logger installed after the run opened: INCOMPLETE', r08),
        ('R09', 'the run id ../etc: PROBE FAILED', r09),
        ('R10', 'one scan-error entry: INCOMPLETE', r10),
        ('R11', 'the report writes nothing (fixture manifest), and its last line is its one verdict', r11),
        ('R12', 'a Claude lane with no line: INCOMPLETE, named', r12),
        ('R13', 'no Bash, a quiet close, or a Codex lane: complete; the first two named as not expected', r13),
        ('R14', 'no line from the head: INCOMPLETE (when head-fence.py stands beside the checker)', r14),
        ('R15', 'the run-open time read with its UTC offset (-1100): complete', r15),
        ('R16', 'a named pipe at the log path: the report returns within 5 s, PROBE FAILED', r16),
        ('R17', 'an empty log: INCOMPLETE', r17),
        ('R18', 'the CLI with empty stdin: a verdict or a probe failure, never a hook decision', r18),
        ('R19', 'a torn lane-open line in the run record (the check\'s case): INCOMPLETE naming line 2, never '
                '"complete · none recorded"; whole, the same line names L1', r19),
        ('R20', 'the same record with the line whole and every writer traced: complete', r20),
        ('R21', 'six shapes of a run-record line that cannot be counted are each INCOMPLETE, named by line '
                '(control: the clean record is complete)', r21),
        ('R22', 'two head sessions on the run record, one traced: INCOMPLETE naming the untraced one only', r22),
        ('R23', 'two head sessions on the run record, both traced: complete', r23),
        ('R24', 'an untraced head-resumed session warns, as a head-successor does: INCOMPLETE naming it', r24),
        ('R25', 'an untraced non-seed run-open session warns: INCOMPLETE naming it', r25),
        ('R26a', 'control: the head-resumed session, traced, is complete', r26a),
        ('R26b', 'control: the run-open session, traced, is complete', r26b),
        ('R27', 'a seed run-open, which never ran, expects no trace: complete', r27),
        ('R28', 'a head-resumed naming no session, and a run-open with a malformed one, are named flaws', r28),
        ('A06a', 'untraced head-resumed is named; traced twin is complete (control: R22)',
         lambda: a06('head-resumed', 'session_id', ({}, {'session_kind': 'seed'}))),
        ('A06b', 'untraced non-seed run-open is named; exact seed spelling only (control: R22)',
         lambda: a06('run-open', 'session', tuple({'session_kind': value}
                                                for value in ('head', 'Seed', 'seed ', '', None, [])))),
        ('A06c', 'untraced run-open with no session_kind is named; traced twin is complete (control: R22)',
         lambda: a06('run-open', 'session', ({},))),
        ('C06seed', 'seed run-open is excluded from validation and collection (control: R22)', c06seed),
        ('C06dedup', 'all four start forms count once, in first-seen order (control: R22)', c06dedup),
        ('P06a', 'head-resumed with a missing or invalid session is INCOMPLETE (control: P06control)',
         lambda: p06('head-resumed', 'session_id')),
        ('P06b', 'non-seed run-open with a missing or invalid session is INCOMPLETE (control: P06control)',
         lambda: p06('run-open', 'session')),
        ('P06control', 'head-successor missing its session is INCOMPLETE (control: R-control)', p06control),
        ('P06torn', 'torn head start is INCOMPLETE, naming its row (control: R-control)', p06torn),
        ('N06', 'read-only report manifest and write-pattern grep, each with a positive control', n06_readonly)):
    setup()
    leg(lid, label, fn)

# The soft caps: these legs need clean_log, so they run after the report legs.
for lid, label, fn in (
        ('P17', 'eight appends whose size tests overlap at the soft cap overshoot it, and the report still reads '
                'the log: INCOMPLETE, cap reached, never PROBE FAILED', p17),
        ('P18', 'a log past the reader\'s bound: its whole lines before the bound are read and counted, the rest '
                'named; INCOMPLETE, never PROBE FAILED', p18),
        ('P19', 'a failure-note file past its read bound: "at least <n>" notes, never unreadable', p19)):
    setup()
    leg(lid, label, fn)

PATHO = [("'{' repeated", '{'), ("'{,' repeated", '{,'), ("'$(' repeated", '$('), ('backticks', '`'),
         ('double quotes', '"'), ('unterminated single quote', None), ('backslashes', '\\'),
         ("'$x' repeated", '$x'), ("'2>&1 ' repeated", '2>&1 ')]


def text_of(unit, size):
    return "cat '" + 'a' * (size - 5) if unit is None else 'cat ' + unit * ((size - 4) // len(unit))


def c01():
    scan = need('unplaced_reads')
    bound = 8   # visits per character: about three times the largest measured (2.70), set by judgement
    worst = 0.0
    for label, unit in PATHO:
        text = text_of(unit, 50000)
        steps = [0]
        scan(text, steps)
        worst = max(worst, steps[0] / len(text))
        start = time.perf_counter()
        scan(text_of(unit, 200000))
        print('  measure — %-26s visits/char %.2f; %.1f ms at 200,000 characters'
              % (label, steps[0] / len(text), (time.perf_counter() - start) * 1e3))
    corpus = [c for _, c, _ in MUST_LOG] + [c for _, c in MUST_NOT_LOG]
    start = time.perf_counter()
    for text in corpus:
        scan(text)
    print('  measure — scan mean %.1f us over the %d L and Q commands' % ((time.perf_counter() - start) / len(corpus) * 1e6, len(corpus)))
    control = text_of('{', 20000)
    planted = [0]
    for i, ch in enumerate(control):            # a planted quadratic walker: what the bound must catch
        planted[0] += 1
        if ch == '{':
            planted[0] += len(control) - i - 1
    return worst <= bound and planted[0] / len(control) > bound, (worst, planted[0] / len(control))


leg('C01', 'the scan makes at most 8 visits per character on nine pathological inputs (control: a quadratic walker exceeds it)', c01)


def h_case(cmd, entry):
    checker, hook, project = hook_tree('real', fence_path)
    lane_want = (proc([sys.executable, '-B', pristine_path], json.dumps(event(cmd)), lane_env(LLM_WIKI_LANE_RUN='')).stdout
                 if pristine else today(lf, cmd, 'lane'))
    lane = proc([sys.executable, '-B', fence_path], json.dumps(event(cmd)), lane_env())
    head = proc([sys.executable, '-B', hook], json.dumps(event(cmd, HSID)), head_env(project))
    problems = []
    if lane.returncode != 0 or lane.stdout != lane_want or '"allow"' not in lane.stdout:
        problems.append(('lane', lane.returncode, lane.stdout, lane.stderr))
    if head.returncode != 0 or head.stdout != '' or head.stderr:
        problems.append(('head', head.returncode, head.stdout, head.stderr))
    if pristine:
        _, twin_hook, twin_project = hook_tree('pristine', pristine_path)
        twin = proc([sys.executable, '-B', twin_hook], json.dumps(event(cmd, 'sid-twin')), head_env(twin_project))
        if twin.returncode != 0 or twin.stdout != '':
            problems.append(('pristine head twin', twin.returncode, twin.stdout))
    got = lines()
    whos = sorted(l.get('who') for l in got)
    if entry:
        good = whos == ['head', 'lane:' + LANE] and all(l.get('n', 0) >= 1 for l in got)
    else:
        good = whos == ['head', 'lane:' + LANE] and all(l.get('n') == 0 for l in got)
    return not problems and good, (problems, got)


setup()
leg('H1', 'L02 through the real lane hook (F\'s CLI) and the real head hook: same decision bytes, one entry each',
    lambda: h_case(SENTINEL, True))
setup()
leg('H2', 'Q01 through the same two hooks: same decision bytes, one trace line per role',
    lambda: h_case(MUST_NOT_LOG[0][1], False))

os.chdir(root)
outside_after = watched()
result('MAN', 'nothing outside this block\'s fixture changed: the checker, the hook and %d other suite fixture entries'
       % (len(outside_before) - 2), bool(outside_before) and outside_before == outside_after,
       sorted(k for k in set(outside_before) | set(outside_after) if outside_before.get(k) != outside_after.get(k))[:4])
planted_manifest = dict(outside_after)
planted_manifest[os.path.join(root, 'sentinel')] = (0o100644, 'changed')
result('MAN+', 'control: the manifest detects a planted change', planted_manifest != outside_before)
print('UNPLACED_COUNTS', passed, failed)
UNPLACED_READS_TEST_END
UNPLACED_OUT=$("$PY" -B "$F/unplaced-tests.py" "$FENCE" "$HERE/../../hooks/head-fence.py" "$F" </dev/null)
UNPLACED_RC=$?
printf '%s\n' "$UNPLACED_OUT"
# A crash or a missing count is a FAIL here, never PROBE FAILED: the pristine-copy control must reach
# its own last line on a checker that has none of the functions these legs need.
UNPLACED_COUNTS=$(printf '%s\n' "$UNPLACED_OUT" | tail -1)
case "$UNPLACED_COUNTS" in
  'UNPLACED_COUNTS '*) UNPLACED_PASS=$(printf '%s\n' "$UNPLACED_COUNTS" | awk '{print $2}')
                       UNPLACED_FAIL=$(printf '%s\n' "$UNPLACED_COUNTS" | awk '{print $3}') ;;
  *) UNPLACED_PASS=0; UNPLACED_FAIL=0; no "unplaced block ended without its counts (exit $UNPLACED_RC)" ;;
esac
[ "$UNPLACED_RC" = 0 ] || no "unplaced block exited $UNPLACED_RC"
PASS=$((PASS + UNPLACED_PASS)); FAIL=$((FAIL + UNPLACED_FAIL))
# UNPLACED_READS_END

# HOOK_GRANTS_BEGIN
# The actual hook loads synthetic grant files; submitted shell commands are never executed.
# Hook event logs go to the disposable fixture, outside the read-only input copy.
HOOK_OUT=$(python3 -B - "$HERE/../../hooks/head-fence.py" "$FENCE" "$F" <<'HOOK_GRANTS_TEST_END'
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

hook_source, checker_source, fixture = map(Path, sys.argv[1:])
if not hook_source.is_file() or not checker_source.is_file():
    print('PROBE FAILED: hook grant matrix requires the hook and checker files')
    sys.exit(2)
ro = fixture / 'hook-ro'
project = ro / 'project'
checker = project / '.claude' / 'skills' / 'delegate' / 'lane-fence.py'
checker.parent.mkdir(parents=True)
shutil.copyfile(checker_source, checker)
hook = ro / 'head-fence.py'
shutil.copyfile(hook_source, hook)
readable, writable, outside, cwd = [ro / part for part in ('readable', 'writable', 'outside', 'cwd')]
for directory in (readable, writable, outside, cwd):
    directory.mkdir()
    (directory / 'input.txt').write_text('sentinel\n')
# These fixture checkers establish that invalid grants never reach checker loading, and retain
# the owner's existing machinery-failure behaviour for otherwise valid grants.
tripwire = ro / 'tripwire' / '.claude' / 'skills' / 'delegate' / 'lane-fence.py'
tripwire.parent.mkdir(parents=True)
tripwire.write_text('raise RuntimeError("checker import reached")\n')
raising = ro / 'raising' / '.claude' / 'skills' / 'delegate' / 'lane-fence.py'
raising.parent.mkdir(parents=True)
raising.write_text('def norm(p): return p\ndef check(*a, **k): raise RuntimeError("checker call reached")\n')
for entry in ro.rglob('*'):
    entry.chmod(0o555 if entry.is_dir() else 0o444)
ro.chmod(0o555)

def manifest():
    return {str(p.relative_to(ro)): (p.stat().st_mode,
            hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
            for p in [ro, *sorted(ro.rglob('*'))]}

before = manifest()
state = fixture / 'hook-state'
store = state / 'store'
(store / 'spawn-records').mkdir(parents=True)
grant_file = store / 'spawn-records' / 'fixture-grants.json'
log = state / 'events.log'
environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', LLM_WIKI_STORE=str(store),
                   AIMYTH_STATE_DIR=str(state), AIMYTH_HANDSOFF='1', AIMYTH_HANDSOFF_RUN='fixture',
                   CLAUDE_PROJECT_DIR=str(project))
valid = {'grants': [str(readable), str(writable)], 'writes': [str(writable)],
         'network': ['allowed.invalid']}
q = shlex.quote
inside_read = 'cat ' + q(str(readable / 'input.txt'))
inside_write = 'touch ' + q(str(writable / 'output.txt'))
outside_read = 'cat ' + q(str(outside / 'input.txt'))
outside_write = 'touch ' + q(str(readable / 'output.txt'))
passed = failed = 0
groups = {}

def result(group, label, good, detail=''):
    global passed, failed
    counts = groups.setdefault(group, [0, 0])
    counts[0 if good else 1] += 1
    passed += bool(good)
    failed += not good
    print(('  ok   — ' if good else 'FAIL   — ') + 'hook ' + group + ': ' + label +
          ('' if good else ' ' + detail))

def run_hook(command, data=valid, payload=None, selected_project=project, raw_grants=None):
    grant_file.write_text(json.dumps(data) if raw_grants is None else raw_grants)
    event = json.dumps({'hook_event_name': 'PreToolUse', 'session_id': 'fixture', 'tool_name': 'Bash',
                        'tool_input': {'command': command}}) if payload is None else payload
    return subprocess.run([sys.executable, '-B', str(hook)], input=event, text=True,
                          capture_output=True, cwd=cwd,
                          env=dict(environment, CLAUDE_PROJECT_DIR=str(selected_project)))

def decision(run, expected, boundary=''):
    if run.returncode or run.stderr:
        return False
    if expected == 'silent':
        return run.stdout == ''
    try:
        output = json.loads(run.stdout)['hookSpecificOutput']
        return (output['hookEventName'] == 'PreToolUse' and output['permissionDecision'] == 'deny'
                and bool(re.search(boundary, output['permissionDecisionReason'])))
    except (ValueError, KeyError, TypeError):
        return False

def case(group, label, command, data=valid, expected='silent', boundary='', selected_project=project):
    run = run_hook(command, data, selected_project=selected_project)
    good = decision(run, expected, boundary)
    if good and expected == 'deny' and group in ('containers', 'members', 'paths', 'hosts', 'ordering'):
        row = log.read_text().splitlines()[-1].split('\t')
        good = len(row) == 6 and row[3] == 'deny-no-grants' and json.loads(row[5]) == command
    result(group, label, good, repr((run.returncode, run.stdout, run.stderr)))

# Required overturn: three fields x five malformed shapes x two commands (benign and escape).
# Additional empty containers, booleans and mixed list members cover falsey and coercion edges.
for key in valid:
    value = valid[key][0]
    escape = {'grants': outside_read, 'writes': outside_write, 'network': 'ssh a true'}[key]
    malformed = [('string', value), ('object', {value: True}), ('number', 7), ('null', None),
                 ('non-string member', [value, 7]), ('empty string container', ''),
                 ('empty object', {}), ('zero', 0), ('boolean', False)]
    for label, bad in malformed:
        for command_label, command in [('ordinary', inside_read), ('escape', escape)]:
            data = dict(valid, **{key: bad})
            case('containers', key + ' ' + label + ' ' + command_label, command, data, 'deny',
                 r'grant file .*invalid `' + key + '`')
    for label, bad in [('empty', ''), ('blank', ' \t'), ('null', None), ('boolean', True),
                       ('object', {}), ('nested list', [])]:
        data = dict(valid, **{key: [value, bad]})
        case('members', key + ' ' + label, inside_read, data, 'deny', r'grant file .*invalid `' + key + '`')
    case('ordering', key + ' validates before checker loading', inside_read,
         dict(valid, **{key: value}), 'deny', r'grant file .*invalid `' + key + '`', ro / 'tripwire')

for key in ('grants', 'writes'):
    for label, bad in [('relative', 'relative/path'), ('home expansion', '~/path'),
                       ('NUL', '/bad\0path'), ('unencodable', '/bad\ud800path')]:
        case('paths', key + ' ' + label, inside_read, dict(valid, **{key: [valid[key][0], bad]}),
             'deny', r'grant file .*invalid `' + key + '`')
for bad in ('https://allowed.invalid', 'reader@allowed.invalid', 'allowed.invalid:22', '/path',
            '*.invalid', 'allowed invalid', ' allowed.invalid', 'allowed.invalid ',
            'bad..invalid', '-bad.invalid', 'bad-.invalid', '[2001:db8::1]', 'bad\0.invalid',
            'a' * 64 + '.invalid', '.'.join(['a' * 63] * 4), 'fe80::1%bad host', 'fe80::1%eth0'):
    case('hosts', repr(bad), inside_read, dict(valid, network=[valid['network'][0], bad]),
         'deny', r'grant file .*invalid `network`')

for label, command, expected, boundary in [
    ('granted read', inside_read, 'silent', ''),
    ('outside read', outside_read, 'deny', r'outside.*grant|grant.*outside'),
    ('granted write', inside_write, 'silent', ''),
    ('outside write within reads', outside_write, 'deny', r'write'),
    ('granted host', 'ssh allowed.invalid true', 'silent', ''),
    ('outside host', 'ssh other.invalid true', 'deny', r'network|host')]:
    case('valid', label, command, expected=expected, boundary=boundary)
for host, endpoint in [('localhost', 'localhost'), ('api-1.example.invalid', 'api-1.example.invalid'),
                       ('API.EXAMPLE.INVALID', 'api.example.invalid'), ('example.invalid.', 'example.invalid.'),
                       ('192.0.2.1', '192.0.2.1'), ('2001:db8::1', '[2001:db8::1]'),
                       ('a' * 63 + '.invalid', 'a' * 63 + '.invalid'),
                       ('.'.join(['a' * 63] * 3 + ['a' * 61]), '.'.join(['a' * 63] * 3 + ['a' * 61]))]:
    case('valid', 'host ' + host, 'curl https://' + endpoint + '/', dict(valid, network=[host]))
for key in ('writes', 'network'):
    for label, data in [('omitted', {k: v for k, v in valid.items() if k != key}),
                        ('empty', dict(valid, **{key: []}))]:
        case('defaults', key + ' ' + label + ' read', inside_read, data)
        command = inside_write if key == 'writes' else 'ssh allowed.invalid true'
        case('defaults', key + ' ' + label + ' refusal', command, data, 'deny', r'write|network')
for label, data in [('omitted', {k: v for k, v in valid.items() if k != 'grants'}),
                    ('empty', dict(valid, grants=[]))]:
    case('defaults', 'grants ' + label, inside_read, data, 'deny', r'grant file .*no `grants`')
case('valid', 'absolute path containing a space accepted', inside_read,
     dict(valid, writes=[str(writable / 'space name')]))

# Ten interpreter recursion limits triggered the C JSON parser's separate nesting bound on
# Python 3.13. Denial must also hold on a decoder that can parse the nested non-string member.
depth = 10 * sys.getrecursionlimit()
deep = '{"grants": ' + json.dumps(valid['grants']) + ', "writes": ' + '[' * depth + '0' + ']' * depth + '}'
for label, raw_grants, boundary in [('malformed JSON', '{', r'grant file .*unusable'),
                                   ('non-object JSON', '[]', r'grant file .*not an object'),
                                   ('excessively nested field', deep, r'grant file .*(?:unusable|invalid `writes`)')]:
    run = run_hook(inside_read, raw_grants=raw_grants)
    result('parsing', label, decision(run, 'deny', boundary),
           repr((run.returncode, run.stdout, run.stderr)))

# Pin the existing recovery and owner-reserved failure directions without widening their scope.
run = run_hook('handsoff.py grants --help', dict(valid, grants=None))
result('retained', 'malformed grant recovery exemption', run.returncode == 0 and not run.stdout
       and 'allowing this' in run.stderr)
for label, payload, selected_project, reason in [
    ('unreadable payload', '{', project, 'unreadable payload'),
    ('missing checker', None, ro / 'absent', 'no lane-fence.py'),
    ('unimportable checker', None, ro / 'tripwire', 'checker import reached'),
    ('raising checker', None, ro / 'raising', 'checker call reached')]:
    run = run_hook(inside_read, payload=payload, selected_project=selected_project)
    result('retained', label, run.returncode == 0 and not run.stdout
           and 'allowing the call' in run.stderr and reason in run.stderr)

# Last legs: no changes to read-only inputs, and no writes in the new validation functions.
# The pre-existing hook logger deliberately writes only the separate disposable state directory.
after = manifest()
result('controls', 'read-only checksum manifest unchanged', bool(before) and before == after,
       'entries=' + str(len(before)))
planted = dict(after)
planted['sentinel'] = (0o444, 'changed')
result('controls', 'manifest positive control detects change', before != planted)
text = hook.read_text()
tree = ast.parse(text)
validation = '\n'.join(ast.get_source_segment(text, node) for node in tree.body
                       if isinstance(node, ast.FunctionDef) and node.name in ('load_grants', 'grant_host'))
if not validation or 'def load_grants(' not in validation:
    print('PROBE FAILED: hook validation source was not found for the write scan')
    sys.exit(2)
write_pattern = (r"open\([^)]*['\"][wax]|write_(text|bytes)[ \t]*\(|"
                 r'\.(unlink|rename|replace|mkdir|rmdir|touch|symlink_to|chmod)[ \t]*\(|'
                 r'\b(subprocess|Popen|shutil)\b|os\.(system|popen|remove|unlink|rename|replace|mkdir|makedirs|rmdir|symlink)\b')
for label, source_text, want in [('validation source has no write patterns', validation, 1),
                                ('write-pattern positive control', 'open("x", "w")\n', 0)]:
    scan = subprocess.run(['grep', '-nE', write_pattern], input=source_text, text=True, capture_output=True)
    if scan.returncode not in (0, 1) or scan.stderr:
        print('PROBE FAILED: hook write-pattern grep failed: ' + scan.stderr)
        sys.exit(2)
    result('controls', label, scan.returncode == want and bool(scan.stdout) == (want == 0))
for group, counts in groups.items():
    print('HOOK_GROUP', group, 'PASS', counts[0], 'FAIL', counts[1])
print('HOOK_COUNTS', passed, failed)
HOOK_GRANTS_TEST_END
)
HOOK_RC=$?
printf '%s\n' "$HOOK_OUT"
[ "$HOOK_RC" = 0 ] || { echo "PROBE FAILED: hook grant checks exited $HOOK_RC"; exit 2; }
HOOK_COUNTS=$(printf '%s\n' "$HOOK_OUT" | tail -1)
case "$HOOK_COUNTS" in
  'HOOK_COUNTS '*) HOOK_PASS=$(printf '%s\n' "$HOOK_COUNTS" | awk '{print $2}')
                  HOOK_FAIL=$(printf '%s\n' "$HOOK_COUNTS" | awk '{print $3}') ;;
  *) echo "PROBE FAILED: hook grant checks omitted their counts"; exit 2 ;;
esac
PASS=$((PASS + HOOK_PASS)); FAIL=$((FAIL + HOOK_FAIL))
# HOOK_GRANTS_END

echo "== the fence wrote only its log, note and markers, and writes only through _unplaced_append =="
AFTER=$("$PY" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$FENCE")
if [ "$FENCE_BEFORE" = "$AFTER" ]; then ok "the fence's own bytes are unchanged after every call above"
else no "the fence source changed during the run  [before $FENCE_BEFORE after $AFTER]"; fi
# N02: the write families now include the raw descriptor calls the logger uses. Every hit must lie in
# _unplaced_append, the logger's one writer, apart from a read-only os.open( in _unplaced_read; at
# least one must lie in _unplaced_append. Keeping the old leg green by evasion would hide the writer.
scan_writes(){ N=0
  for pat in 'open\([^)]*['"'"'"][wax]' '\bos\.(remove|unlink|rename|replace|mkdir|makedirs|rmdir)\b' \
             '\bshutil\.' '\b(subprocess|Popen)\b' '\bos\.symlink\b' \
             '\bos\.open\(' '\bos\.write\(' '\bO_APPEND\b' '\bO_CREAT\b'; do
    grep -qE -- "$pat" "$1" && N=$((N + 1))
  done
  echo "$N"
}
PLANT="$F/planted-fence.py"
{ cat "$FENCE"; printf '\nopen("x","w")\nos.remove("x")\nshutil.copy("x","y")\nsubprocess.run([])\nos.symlink("a","b")\nos.open("x", 0)\nos.write(1, b"")\nos.O_APPEND | os.O_CREAT\n'; } > "$PLANT"
FW_N=$(scan_writes "$FENCE"); PW_N=$(scan_writes "$PLANT")
SPANS=$("$PY" -B - "$FENCE" "$PLANT" <<'FENCE_WRITE_SPANS_END'
import re, sys
PATTERNS = [r"open\([^)]*['\"][wax]", r'\bos\.(remove|unlink|rename|replace|mkdir|makedirs|rmdir)\b',
            r'\bshutil\.', r'\b(subprocess|Popen)\b', r'\bos\.symlink\b', r'\bos\.open\(', r'\bos\.write\(',
            r'\bO_APPEND\b', r'\bO_CREAT\b']
def span(lines, name):
    start = next((i for i, l in enumerate(lines) if l.startswith('def ' + name + '(')), None)
    if start is None:
        return None
    return start, next((i for i in range(start + 1, len(lines)) if lines[i].startswith('def ')), len(lines))
def scan(path):
    lines = open(path, encoding='utf-8').read().split('\n')
    w, r = span(lines, '_unplaced_append'), span(lines, '_unplaced_read')
    if w is None or r is None:
        return None
    inside, outside, families = 0, [], set()
    for i, line in enumerate(lines):
        for k, p in enumerate(PATTERNS):
            if not re.search(p, line):
                continue
            if w[0] <= i < w[1]:
                inside += 1
            elif not (r[0] <= i < r[1] and k == 5):
                outside.append(i + 1)
                families.add(k)
    reader = '\n'.join(lines[r[0]:r[1]])
    reader_ok = 'O_RDONLY' in reader and not re.search(r'O_WRONLY|O_RDWR|O_APPEND|O_CREAT|os\.write\(', reader)
    return inside, outside, reader_ok, len(families)
fence, plant = scan(sys.argv[1]), scan(sys.argv[2])
if fence is None or plant is None:
    print('SPANS bad: no _unplaced_append or _unplaced_read in the fence')
else:
    good = fence[0] >= 1 and not fence[1] and fence[2] and plant[3] == len(PATTERNS)
    print('SPANS %s: %d hit(s) inside _unplaced_append, %d outside %s, reader read-only %s; planted copy hits %d of %d families outside'
          % ('ok' if good else 'bad', fence[0], len(fence[1]), fence[1][:5], fence[2], plant[3], len(PATTERNS)))
FENCE_WRITE_SPANS_END
)
case "$SPANS" in
  "SPANS ok:"*) if [ "$PW_N" = 9 ]; then ok "the fence writes only through _unplaced_append (${SPANS#SPANS ok: }; grep: planted $PW_N of 9)"
                else no "the fence writes only through _unplaced_append  [$SPANS; grep: fence $FW_N of 9, planted $PW_N of 9]"; fi ;;
  *) no "the fence writes only through _unplaced_append  [$SPANS; grep: fence $FW_N of 9, planted $PW_N of 9]" ;;
esac
# N05: the logger's source never writes stdout, exits or decides; a print or an exit there would
# change what the harness reads. The planted copy puts both inside the span.
NOEXIT=$("$PY" -B - "$FENCE" <<'FENCE_NO_EXIT_END'
import re, sys
lines = open(sys.argv[1], encoding='utf-8').read().split('\n')
start = next((i for i, l in enumerate(lines) if l.startswith('def strip_shell_comments(')), None)
end = next((i for i, l in enumerate(lines) if l.startswith('def _unplaced_read(')), None)
if start is None or end is None or end <= start:
    print('NOEXIT bad: no span from strip_shell_comments to _unplaced_read')
    sys.exit(0)
bad = r'\bsys\.exit\b|\bexit\(|\bquit\(|\bos\._exit\b|\bprint\(|\bsys\.stdout\b|\bdecide\(|\bdeny\('
span = lines[start:end]
hits = [l.strip() for l in span if re.search(bad, l)]
planted = span[:1] + ['    print(1)', '    sys.exit(0)'] + span[1:]
control = sum(1 for l in planted if re.search(bad, l)) - len(hits)
print('NOEXIT %s: %d lines, %d hit(s) %s; planted control %d of 2'
      % ('ok' if not hits and control == 2 else 'bad', len(span), len(hits), hits[:2], control))
FENCE_NO_EXIT_END
)
case "$NOEXIT" in
  "NOEXIT ok:"*) ok "N05: the logger never prints, exits or decides (${NOEXIT#NOEXIT ok: })" ;;
  *) no "N05: the logger's source span  [$NOEXIT]" ;;
esac

# --- review F7: the suite's own positive control. The same legs run against the PRE-FOLD checker must
# FAIL in numbers; a suite that passes on both checkers is measuring nothing. Skipped (with a note)
# when no pre-fold checker is given, and never recursive.
if [ -n "${FENCE_PRISTINE:-}" ] && [ -z "${FENCE_CONTROL_RUN:-}" ]; then
  if [ -f "$FENCE_PRISTINE" ]; then
    CTL=$(env FENCE_CONTROL_RUN=1 sh "$0" --fence "$FENCE_PRISTINE" 2>&1 | tail -1)
    CTLN=$(printf '%s' "$CTL" | sed -n 's/^FAIL \([0-9]*\)\/.*/\1/p')
    if [ -n "$CTLN" ] && [ "$CTLN" -gt 0 ]; then
      ok "control: the same legs on the pre-fold checker fail $CTLN of them (they measure behaviour, not nothing)"
    else no "control: the pre-fold checker did not fail these legs  [$CTL]"; fi
  else no "control: FENCE_PRISTINE set but not a file  [$FENCE_PRISTINE]"; fi
else
  [ -n "${FENCE_CONTROL_RUN:-}" ] || echo "  note — no FENCE_PRISTINE given: the pre-fold control run was not made"
fi

echo
if [ "$FAIL" -eq 0 ]; then echo "PASS $PASS/$((PASS+FAIL))"; else echo "FAIL $FAIL/$((PASS+FAIL))"; exit 1; fi
