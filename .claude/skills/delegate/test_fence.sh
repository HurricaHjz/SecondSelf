#!/bin/sh
# Regression cases for shell fencing and path handling.
#
# Every guard change gets a MUST-FIRE leg (a planted case the fence must deny) and a MUST-NOT-FIRE
# leg (a read-only or in-scope case it must clear), plus a premise-failure leg (CLAUDE.md §12).
# A leg's target sits INSIDE the read grants wherever the leg is about the write side, so check 4
# cannot mask it and the leg measures the rule it names (review F7). Fixtures live under one mktemp -d
# the suite removes; the last blocks prove the fence wrote nothing and, when a pre-fold checker is
# given, report its fail count as the suite's own positive control.
#
# Run:  sh test_fence.sh                     (last line: PASS n/n or FAIL k/n)
#       sh test_fence.sh --fence F           (test a copy of the fence elsewhere)
#       FENCE_PRISTINE=<old lane-fence.py> sh test_fence.sh   (adds the control run)
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

F=$(mktemp -d)
cleanup(){ chmod -R u+w "$F" >/dev/null 2>&1; rm -rf "$F"; }
trap cleanup EXIT INT TERM

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
# [grants=$G], [writes=""], [network=""], [role=""], [cwd="."].
fence(){
  NAME="$1"; WANT="$2"; CMD="$3"; FG="${4-$G}"; FW="${5-}"; FN="${6-}"; ROLE="${7-}"; FCWD="${8-.}"
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
  if [ "$GOT" = "$WANT" ]; then ok "$WANT: $NAME"
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

echo "== block 2R: twelve sanitised head-fence command shapes =="
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

echo "== the fence wrote nothing, and its source calls no write =="
AFTER=$("$PY" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$FENCE")
if [ "$FENCE_BEFORE" = "$AFTER" ]; then ok "the fence's own bytes are unchanged after every call above"
else no "the fence source changed during the run  [before $FENCE_BEFORE after $AFTER]"; fi
scan_writes(){ N=0
  for pat in 'open\([^)]*['"'"'"][wax]' '\bos\.(remove|unlink|rename|replace|mkdir|makedirs|rmdir)\b' \
             '\bshutil\.' '\b(subprocess|Popen)\b' '\bos\.symlink\b'; do
    grep -qE -- "$pat" "$1" && N=$((N + 1))
  done
  echo "$N"
}
PLANT="$F/planted-fence.py"
{ cat "$FENCE"; printf '\nopen("x","w")\nos.remove("x")\nshutil.copy("x","y")\nsubprocess.run([])\nos.symlink("a","b")\n'; } > "$PLANT"
FW_N=$(scan_writes "$FENCE"); PW_N=$(scan_writes "$PLANT")
if [ "$FW_N" = 0 ] && [ "$PW_N" = 5 ]; then
  ok "no write-call family appears in the fence source (control: all 5 hit in a planted copy)"
else no "fence write-call scan  [fence $FW_N of 5, planted $PW_N of 5]"; fi

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
