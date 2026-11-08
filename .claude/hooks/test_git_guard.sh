#!/bin/sh
# test_git_guard.sh — the destructive-git guard, the inline command of the first PreToolUse Bash
# entry in settings.json: a failed input read asks instead of allowing (register 2026-09-30 06:43,
# its failed-capture half; the disguised-spelling half is the guard's stated limit, not tested here).
#
# The suite extracts the guard's command from the settings file and runs it under /bin/sh on JSON
# payloads, with PATH controlled per leg: wrapper scripts that exec the real cat, grep and jq, or
# stubs that fail, in a fixture directory removed on exit. Legs marked (new) fail on the guard as it
# stood before this batch (legs b to d), or on that guard and on the guard as this batch first built
# it (legs e and g, review CR-B7); legs marked (fold) fail only on the guard as first built (an
# inherited errexit: the older guard's greps sat in && lists, so it asked); legs marked (control)
# pass on all three, and on the guard as the first fold left it. Stdout-only: neither the guard nor this
# suite writes outside its fixture directory, and the last leg proves it (a read-only working
# directory's manifest, the settings file's checksum, and a source grep for write verbs whose own
# positive control must hit).
#
# Fold 1 (review CR-B7): (e) an inherited errexit (SHELLOPTS=errexit in the environment, which
# /bin/sh honours) must not end the guard at a failed command before its status is read; (f) set -e
# given through BASH_ENV or ENV runs the same legs wherever /bin/sh reads the variable, and otherwise
# records that it does not, beside a control shell that does; (g) with jq missing, a JSON unicode
# escape in the raw input asks, since it can spell any letter of a verb. The escaped fixtures build
# their backslash at run time (octal 134), so the escape they claim is the escape they carry, and
# leg a asserts their raw bytes and decoded command.
#
# Fold 2 (review CR-B7b finding N1): (i) an inherited pipefail made a grep -q that matched early read
# as a failure: printf, still writing a long command into the pipe grep had closed, died of SIGPIPE
# (141), the pipeline reported that, and the guard asked on an exempt `git checkout -b`. The guard now
# switches errexit, nounset and pipefail off at its start. Leg i runs the reviewer's fixtures (a first
# line, then 16,384 `# filler` lines) under SHELLOPTS=errexit:pipefail:nounset, runs the switches
# alone, and runs the guard under /bin/dash, a shell without pipefail, where the switch must be
# tolerated. Legs marked (fold2) fail on the guard as the first fold left it; legs marked (fold2
# control) pass there and must keep passing, so the fix takes no ask away.
#
# Run:  sh test_git_guard.sh [--settings PATH]
#       default PATH: settings.json one level above this hooks folder, where it lives once installed.
#       Last line: PASS n/n or FAIL k/n. A broken premise prints PROBE FAILED and exits 2.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SETTINGS="$HERE/../settings.json"
while [ $# -gt 0 ]; do
  case "$1" in
    --settings) [ $# -ge 2 ] || { echo "PROBE FAILED: --settings needs a path"; exit 2; }
                SETTINGS="$2"; shift 2 ;;
    *) echo "PROBE FAILED: unknown argument '$1' (usage: sh test_git_guard.sh [--settings PATH])"; exit 2 ;;
  esac
done
[ -f "$SETTINGS" ] || { echo "PROBE FAILED: no settings file at $SETTINGS"; exit 2; }
PY=/usr/local/bin/python3; [ -x "$PY" ] || PY=python3
REAL_CAT=$(command -v cat); REAL_GREP=$(command -v grep); REAL_JQ=$(command -v jq)
for t in "$REAL_CAT" "$REAL_GREP" "$REAL_JQ"; do
  case "$t" in /*) ;; *) echo "PROBE FAILED: the controls need cat, grep and jq on PATH (found '$REAL_CAT', '$REAL_GREP', '$REAL_JQ')"; exit 2 ;; esac
done
F="$(mktemp -d "${TMPDIR:-/tmp}/git-guard.XXXXXX")" || { echo "PROBE FAILED: cannot create fixtures"; exit 2; }
[ -d "$F" ] || { echo "PROBE FAILED: missing fixture directory"; exit 2; }
trap 'chmod -R u+w "$F" 2>/dev/null; rm -rf "$F"' 0
trap 'exit 2' HUP INT TERM
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "  ok   — $1"; }
bad()  { FAIL=$((FAIL+1)); echo "  FAIL — $1"; }
check(){ [ "$2" = "$3" ] && ok "$1" || bad "$1 (want '$3', got '$2')"; }
has()  { case "$2" in *"$3"*) ok "$1" ;; *) bad "$1 (want text containing '$3', got '$2')" ;; esac; }
hashf(){ if command -v md5 >/dev/null 2>&1; then md5 -q "$1"; else md5sum "$1" | cut -d' ' -f1; fi; }
manifest(){ find "$@" -type f | LC_ALL=C sort | while IFS= read -r f; do printf '%s %s\n' "$(hashf "$f")" "$f"; done; }

echo "== setup: the guard from $SETTINGS; fixtures under $F =="
"$PY" -B - "$SETTINGS" "$F/guard.cmd" <<'EXTRACT_END'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
bash = [e for e in (data.get("hooks", {}).get("PreToolUse") or []) if e.get("matcher") == "Bash"]
mark = "Destructive git verb on the vault working tree"
found = [h.get("command", "") for e in bash for h in (e.get("hooks") or []) if mark in h.get("command", "")]
if len(found) != 1:
    print("PROBE FAILED: %d PreToolUse Bash commands carry the guard's ask text, want 1" % len(found))
    sys.exit(2)
first = (bash[0].get("hooks") or [{}])[0].get("command", "") if bash else ""
if first != found[0]:
    print("PROBE FAILED: the guard is not the first PreToolUse Bash entry")
    sys.exit(2)
with open(sys.argv[2], "w", encoding="utf-8") as fh:
    fh.write(found[0])
print("  the guard: the first PreToolUse Bash entry, %d characters" % len(found[0]))
EXTRACT_END
[ $? -eq 0 ] || exit 2
CMD=$(cat "$F/guard.cmd")
# PATH directories: wrappers exec the real tools by absolute path (no link to a system file is made);
# stubs fail on purpose. Each leg's PATH is one of these and nothing else.
mkdir -p "$F/bin-full" "$F/bin-nojq" "$F/bin-jqfail" "$F/bin-nogrep" "$F/bin-grepfail" "$F/bin-exfail" "$F/bin-nocat" \
         "$F/p" "$F/cwd" "$F/home"
wrap(){ printf '#!/bin/sh\nexec "%s" "$@"\n' "$2" > "$1"; chmod 755 "$1"; }
stub(){ printf '#!/bin/sh\nexit %s\n' "$2" > "$1"; chmod 755 "$1"; }
for d in full nojq jqfail grepfail exfail; do wrap "$F/bin-$d/cat" "$REAL_CAT"; done
for d in full nojq jqfail nocat; do wrap "$F/bin-$d/grep" "$REAL_GREP"; done
for d in full nogrep grepfail exfail nocat; do wrap "$F/bin-$d/jq" "$REAL_JQ"; done
wrap "$F/bin-nogrep/cat" "$REAL_CAT"
stub "$F/bin-jqfail/jq" 3
stub "$F/bin-grepfail/grep" 2
# exfail: grep fails (exit 2) only on the checkout -b exemption's pattern and runs for real otherwise
printf '#!/bin/sh\ncase "$*" in *"checkout[[:space:]]+-b"*) exit 2 ;; esac\nexec "%s" "$@"\n' "$REAL_GREP" > "$F/bin-exfail/grep"
chmod 755 "$F/bin-exfail/grep"
[ "$(env -i PATH="$F/bin-full" /bin/sh -c 'printf x | grep -c x; printf "{\"a\":1}" | jq -r .a; printf y | cat')" = "$(printf '1\n1\ny')" ] \
  || { echo "PROBE FAILED: the wrapped cat, grep and jq do not run"; exit 2; }
# payloads, shaped as the harness sends them (compact JSON, the command in tool_input.command)
pl(){ printf '{"session_id":"sid-g","transcript_path":"/t/x.jsonl","cwd":"/w","permission_mode":"default","hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"%s","description":"d"}}' "$2" > "$F/p/$1.json"; }
pl reset 'git reset --hard'
pl ls 'ls'
pl lsla 'ls -la'
pl branch 'git checkout -b x'
pl dashc 'git -C /x reset --hard'
pl checkout 'git checkout -- f'
pl restore 'git restore f'
pl clean 'git clean -fd'
pl status 'git status'
pl upper 'GIT reset --hard'
# JSON unicode escapes: the backslash is made at run time (printf's octal 134), never typed, so the
# fixture carries the escape its label claims (review CR-B7 finding 4)
BS=$(printf '\134')
[ "$BS" = "$(printf '%s' 'x\y' | cut -c2)" ] || { echo "PROBE FAILED: cannot make a backslash"; exit 2; }
pl escaped "${BS}u0067it reset --hard"          # an escaped g hides git from the raw text
pl encoded "git re${BS}u0073et --hard"          # an escaped s hides reset from the raw text
pl literal "printf ${BS}${BS}u00e9"             # a literal backslash-u in the command: serialised as \\u
printf '%s' '{"session_id":"sid-g","hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git reset --hard"}' > "$F/p/malformed.json"
printf '%s' '{"session_id":"sid-g","hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"cmd":"git reset --hard"}}' > "$F/p/nocommand.json"
# the reviewer's long fixtures (review CR-B7b finding N1): a first line, then 16,384 `# filler` lines,
# 147,474 bytes of command after git checkout -b x; newlines made at run time (chr(10)), compact JSON
"$PY" -B - "$F/p" <<'LONG_FIXTURES_END'
import json, os, sys
nl = chr(10)
filler = ("# filler" + nl) * 16384
for name, first in (("longbranch", "git checkout -b x"), ("longreset", "git reset --hard")):
    ev = {"session_id": "sid-g", "transcript_path": "/t/x.jsonl", "cwd": "/w", "permission_mode": "default",
          "hook_event_name": "PreToolUse", "tool_name": "Bash",
          "tool_input": {"command": first + nl + filler, "description": "d"}}
    with open(os.path.join(sys.argv[1], name + ".json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(ev, separators=(",", ":")))
LONG_FIXTURES_END
[ $? -eq 0 ] || { echo "PROBE FAILED: cannot build the long fixtures"; exit 2; }
: > "$F/p/empty.json"
printf '  \n\t \n' > "$F/p/blank.json"
printf 'planted\n' > "$F/cwd/planted.txt"
manifest "$F/cwd" "$F/home" "$F/p" > "$F/manifest.before"
SUM_BEFORE=$(hashf "$SETTINGS")
chmod a-w "$F/cwd" "$F/home"
# guard <bin> <payload file> [VAR=value ...] -> its stdout; exit status = the guard's; stderr kept in $F/err.txt.
# The shell is $SH: /bin/sh, as the harness runs the guard, except in leg i's /bin/dash legs.
SH=/bin/sh
guard(){ b="$1"; p="$2"; shift 2; (cd "$F/cwd" && env -i PATH="$F/bin-$b" HOME="$F/home" ${1+"$@"} "$SH" -c "$CMD" < "$p" 2>"$F/err.txt"); }
dec(){ printf '%s' "$1" | "$PY" -B -c '
import json, sys
raw = sys.stdin.read()
if not raw.strip():
    sys.stdout.write("(silent)"); sys.exit(0)
try:
    h = json.loads(raw)["hookSpecificOutput"]
except (ValueError, KeyError, TypeError):
    sys.stdout.write("(bad json)"); sys.exit(0)
sys.stdout.write("%s|%s|%s" % (h.get("hookEventName"), h.get("permissionDecision"), h.get("permissionDecisionReason")))
'; }
STD="PreToolUse|ask|Destructive git verb on the vault working tree, which routinely holds uncommitted knowledge writes that these verbs discard silently (known-issues 2026-08-23). Prefer a precise inverse edit, test artefacts in /tmp, or another repo via -C."
NONZERO=0
leg(){ OUT=$(guard "$@"); RC=$?; [ "$RC" -eq 0 ] || NONZERO=$((NONZERO+1)); D=$(dec "$OUT"); }

echo "== a. controls: the guard as it stood (pass before and after the fix) =="
leg full "$F/p/reset.json";    check "(control) a plain git reset --hard asks with the existing text" "$D" "$STD"
leg full "$F/p/dashc.json";    check "(control) git -C /x reset --hard asks" "$D" "$STD"
leg full "$F/p/checkout.json"; check "(control) git checkout -- f asks" "$D" "$STD"
leg full "$F/p/restore.json";  check "(control) git restore f asks" "$D" "$STD"
leg full "$F/p/clean.json";    check "(control) git clean -fd asks" "$D" "$STD"
decoded(){ "$PY" -B -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["tool_input"]["command"])' "$1"; }
check "(fixture) the escaped payload's raw bytes carry the escape (\"command\":\"${BS}u0067it reset --hard\") and no plain git" \
      "$(grep -cF "\"command\":\"${BS}u0067it reset --hard\"" "$F/p/escaped.json"):$(grep -c 'git' "$F/p/escaped.json")" "1:0"
check "(fixture) …and decode to the plain command" "$(decoded "$F/p/escaped.json")" "git reset --hard"
check "(fixture) the encoded payload's raw bytes carry re${BS}u0073et and none of checkout, restore, clean or reset" \
      "$(grep -cF "re${BS}u0073et" "$F/p/encoded.json"):$(grep -cE 'checkout|restore|clean|reset' "$F/p/encoded.json")" "1:0"
check "(fixture) …and decode to the plain command" "$(decoded "$F/p/encoded.json")" "git reset --hard"
check "(fixture) the literal payload's raw bytes carry an escaped backslash before u, and decode to a command holding backslash-u" \
      "$(grep -cF "${BS}${BS}u00e9" "$F/p/literal.json"):$(decoded "$F/p/literal.json")" "1:printf ${BS}u00e9"
leg full "$F/p/escaped.json";  check "(control) a JSON-escaped letter is decoded by jq: ${BS}u0067it reset --hard asks" "$D" "$STD"
leg full "$F/p/encoded.json";  check "(control) …and so is git re${BS}u0073et --hard" "$D" "$STD"
leg full "$F/p/literal.json";  check "(control) a command holding a literal backslash-u and no git stays silent while jq works" "$D" "(silent)"
leg full "$F/p/branch.json";   check "(control) git checkout -b x stays silent (the exemption)" "$D" "(silent)"
leg full "$F/p/ls.json";       check "(control) ls stays silent" "$D" "(silent)"
leg full "$F/p/status.json";   check "(control) git status stays silent" "$D" "(silent)"
leg full "$F/p/upper.json" GREP_OPTIONS=-i; check "(control) GREP_OPTIONS=-i still runs the full path: GIT reset --hard asks" "$D" "$STD"
leg full "$F/p/upper.json";    check "(control) …and without GREP_OPTIONS GIT reset --hard stays silent (the case-sensitive skip)" "$D" "(silent)"
leg grepfail "$F/p/lsla.json"; check "(control) a failing grep does not prompt on a command without git (no grep runs)" "$D" "(silent)"

echo "== b. jq missing or failing: the raw input, recall-first, no exemption =="
leg nojq "$F/p/reset.json"
check "(new) jq missing, git reset --hard: asks" "$(printf '%s' "$D" | cut -d'|' -f1,2)" "PreToolUse|ask"
has   "(new) …the reason names the failure: jq was not found" "$D" "jq was not found, and the raw input holds git with checkout, restore, clean or reset"
leg nojq "$F/p/lsla.json";     check "(recall-first precision) jq missing, ls -la: silent, so a missing jq does not prompt on every call" "$D" "(silent)"
leg nojq "$F/p/status.json";   check "(recall-first precision) jq missing, git status: silent (no guarded verb in the raw text)" "$D" "(silent)"
leg nojq "$F/p/branch.json"
check "(new) jq missing, git checkout -b x: asks (no exemption applies in the fallback)" "$(printf '%s' "$D" | cut -d'|' -f1,2)" "PreToolUse|ask"
leg jqfail "$F/p/checkout.json"
check "(new) jq failing (exit 3), git checkout -- f: asks" "$(printf '%s' "$D" | cut -d'|' -f1,2)" "PreToolUse|ask"
has   "(new) …the reason names it: jq failed (exit 3)" "$D" "jq failed (exit 3), and the raw input holds git"
leg full "$F/p/malformed.json"
check "(new) malformed JSON holding git reset --hard: asks" "$(printf '%s' "$D" | cut -d'|' -f1,2)" "PreToolUse|ask"
has   "(new) …the reason names jq's failure on the payload" "$D" "Destructive-git guard: jq failed (exit "
leg full "$F/p/nocommand.json"
check "(new) a parsed payload with no command whose raw text holds git reset --hard: asks" "$(printf '%s' "$D" | cut -d'|' -f1,2)" "PreToolUse|ask"
has   "(new) …the reason names it: jq found no command" "$D" "jq found no command in the hook input"

echo "== c. an empty or unreadable payload asks =="
leg full "$F/p/empty.json";    has "(new) an empty payload asks, named" "$D" "PreToolUse|ask|Destructive-git guard: the hook input was empty"
leg full "$F/p/blank.json";    has "(new) a whitespace-only payload asks, named as empty" "$D" "PreToolUse|ask|Destructive-git guard: the hook input was empty"
leg full "$F/cwd";             has "(new) an unreadable payload (standard input is a directory) asks, named" "$D" "PreToolUse|ask|Destructive-git guard: reading the hook input failed: cat failed (exit 1)"
leg nocat "$F/p/ls.json";      has "(new) cat missing: the payload cannot be read, so it asks, named" "$D" "PreToolUse|ask|Destructive-git guard: reading the hook input failed: cat was not found"

echo "== d. a grep that fails asks rather than allows =="
leg grepfail "$F/p/reset.json"; has "(new) grep failing (exit 2) on git reset --hard: asks, named" "$D" "PreToolUse|ask|Destructive-git guard: grep failed (exit 2) while looking for destructive git verbs"
leg nogrep "$F/p/reset.json";   has "(new) grep missing on git reset --hard: asks, named" "$D" "PreToolUse|ask|Destructive-git guard: grep was not found while looking for destructive git verbs"
leg nogrep "$F/p/status.json";  has "(new) grep missing on git status: asks (the verbs cannot be looked for)" "$D" "PreToolUse|ask|Destructive-git guard: grep was not found"
leg exfail "$F/p/branch.json";  has "(new) grep failing on the checkout -b exemption: asks, named" "$D" "PreToolUse|ask|Destructive-git guard: grep failed (exit 2) while checking the checkout -b exemption"

# errexit_legs <label> VAR=value ...: the legs an inherited errexit must not silence. Every command
# whose failure the guard inspects (cat, jq, the three greps) must leave its status readable.
errexit_legs(){ lab="$1"; shift
  leg full "$F/p/reset.json" "$@";     check "(fold) $lab: a plain git reset --hard asks with the existing text" "$D" "$STD"
  leg full "$F/p/checkout.json" "$@";  check "(fold) $lab: git checkout -- f asks" "$D" "$STD"
  leg full "$F/p/clean.json" "$@";     check "(fold) $lab: git clean -fd asks" "$D" "$STD"
  leg jqfail "$F/p/reset.json" "$@";   has "(new) $lab: jq failing (exit 3) on git reset --hard asks, named" "$D" "PreToolUse|ask|Destructive-git guard: jq failed (exit 3), and the raw input holds git"
  leg nojq "$F/p/reset.json" "$@";     has "(new) $lab: jq missing on git reset --hard asks, named" "$D" "PreToolUse|ask|Destructive-git guard: jq was not found, and the raw input holds git"
  leg grepfail "$F/p/reset.json" "$@"; has "(new) $lab: grep failing (exit 2) on git reset --hard asks, named" "$D" "PreToolUse|ask|Destructive-git guard: grep failed (exit 2) while looking for destructive git verbs"
  leg exfail "$F/p/branch.json" "$@";  has "(new) $lab: grep failing on the checkout -b exemption asks, named" "$D" "PreToolUse|ask|Destructive-git guard: grep failed (exit 2) while checking the checkout -b exemption"
  leg full "$F/cwd" "$@";              has "(new) $lab: an unreadable payload (standard input is a directory) asks, named" "$D" "PreToolUse|ask|Destructive-git guard: reading the hook input failed: cat failed (exit 1)"
  leg full "$F/p/ls.json" "$@";        check "(control) $lab: ls stays silent" "$D" "(silent)"
  leg full "$F/p/branch.json" "$@";    check "(control) $lab: git checkout -b x stays silent (the exemption still applies)" "$D" "(silent)"
}

echo "== e. an inherited errexit cannot silence the guard (review CR-B7 finding 1) =="
# premise, with its control: /bin/sh honours SHELLOPTS=errexit from the environment, so these legs
# are not vacuous
[ "$(env -i PATH="$F/bin-full" SHELLOPTS=errexit /bin/sh -c 'false; echo survived')" = "" ] \
  && [ "$(env -i PATH="$F/bin-full" /bin/sh -c 'false; echo survived')" = "survived" ] \
  || { echo "PROBE FAILED: /bin/sh does not take errexit from SHELLOPTS (or its control failed); leg e would be vacuous"; exit 2; }
echo "  premise: /bin/sh -c stops at a failing command under SHELLOPTS=errexit (control without it: it runs on)"
errexit_legs "SHELLOPTS=errexit" SHELLOPTS=errexit
leg full "$F/p/reset.json" SHELLOPTS=errexit:nounset:pipefail
check "(fold) SHELLOPTS=errexit:nounset:pipefail: a plain git reset --hard asks with the existing text" "$D" "$STD"

echo "== f. set -e given through BASH_ENV or ENV: the same legs wherever /bin/sh reads the variable =="
printf 'set -e\n' > "$F/sete.sh"
for V in BASH_ENV ENV; do
  if [ "$(env -i PATH="$F/bin-full" "$V=$F/sete.sh" /bin/sh -c 'false; echo survived' < /dev/null)" = "survived" ]; then
    ok "(premise) /bin/sh -c does not read $V, so set -e given through it cannot reach the guard"
  else
    echo "  /bin/sh -c reads $V: the errexit legs run with set -e given through it"
    errexit_legs "set -e through $V" "$V=$F/sete.sh"
  fi
done
# controls for the two probes: a shell that does read the variable stops at `false`, so a read is seen
check "…control: /bin/bash -c reads BASH_ENV, and the same startup file stops it at a failing command" \
      "$(env -i PATH="$F/bin-full" BASH_ENV="$F/sete.sh" /bin/bash -c 'false; echo survived' < /dev/null)" ""
check "…control: an interactive /bin/sh reads ENV, and the same startup file stops it at a failing command" \
      "$(env -i PATH="$F/bin-full" ENV="$F/sete.sh" /bin/sh -i -c 'false; echo survived' < /dev/null 2>"$F/err-ctl.txt")" ""

echo "== g. jq missing: a JSON unicode escape in the raw input asks (review CR-B7 finding 3) =="
UASK="PreToolUse|ask|Destructive-git guard: jq was not found, and the raw input holds a JSON unicode escape, which could spell a git verb"
leg nojq "$F/p/encoded.json";  has "(new) jq missing, git re${BS}u0073et --hard (the escape hides reset from the raw text): asks, named" "$D" "$UASK"
leg nojq "$F/p/escaped.json";  has "(new) jq missing, ${BS}u0067it reset --hard (the escape hides git from the raw text): asks, named" "$D" "$UASK"
leg jqfail "$F/p/escaped.json"
has "(new) jq failing (exit 3), ${BS}u0067it reset --hard: asks, named" "$D" "PreToolUse|ask|Destructive-git guard: jq failed (exit 3), and the raw input holds a JSON unicode escape"
leg nojq "$F/p/lsla.json";     check "(control) jq missing, ls -la (no escape, no git): silent" "$D" "(silent)"
leg nojq "$F/p/literal.json"
has "(recall-first cost) jq missing, a command holding a literal backslash-u: asks too (the raw text cannot tell an escaped backslash before u from an escape)" "$D" "$UASK"

echo "== i. an inherited pipefail cannot turn an upstream SIGPIPE into a grep failure (review CR-B7b finding N1) =="
longinfo(){ "$PY" -B -c 'import json, sys
c = json.load(open(sys.argv[1], encoding="utf-8"))["tool_input"]["command"]
lines = c.split(chr(10))
print("%d:%s:%d" % (len(c.encode("utf-8")), lines[0], lines.count("# filler")))' "$1"; }
check "(fixture) the long branch payload decodes to git checkout -b x, then 16,384 filler lines: 147,474 bytes" "$(longinfo "$F/p/longbranch.json")" "147474:git checkout -b x:16384"
check "(fixture) the long reset payload decodes to git reset --hard, then the same filler: 147,473 bytes" "$(longinfo "$F/p/longreset.json")" "147473:git reset --hard:16384"
# premises, with their controls: /bin/sh takes pipefail from SHELLOPTS, and under it the long
# fixture's early grep match is reported as printf's SIGPIPE (status 141; within three tries, since it
# depends on grep exiting while printf still writes), so the legs below are not vacuous
[ "$(env -i PATH="$F/bin-full" SHELLOPTS=pipefail /bin/sh -c 'false | true; echo $?')" = 1 ] \
  && [ "$(env -i PATH="$F/bin-full" /bin/sh -c 'false | true; echo $?')" = 0 ] \
  || { echo "PROBE FAILED: /bin/sh does not take pipefail from SHELLOPTS (or its control failed); leg i would be vacuous"; exit 2; }
SIGP=
for t in 1 2 3; do
  SIGP="$SIGP $(env -i PATH="$F/bin-full" SHELLOPTS=pipefail /bin/sh -c 'C=$(jq -r .tool_input.command); printf "%s" "$C" | grep -q checkout; echo $?' < "$F/p/longbranch.json")"
  case "$SIGP" in *141*) break ;; esac
done
case "$SIGP" in *141*) ;; *) echo "PROBE FAILED: under pipefail the long fixture's early grep match never reported SIGPIPE in 3 tries (statuses:$SIGP); leg i would be vacuous"; exit 2 ;; esac
[ "$(env -i PATH="$F/bin-full" /bin/sh -c 'C=$(jq -r .tool_input.command); printf "%s" "$C" | grep -q checkout; echo $?' < "$F/p/longbranch.json")" = 0 ] \
  || { echo "PROBE FAILED: without pipefail the long fixture's grep did not report its own match"; exit 2; }
echo "  premise: /bin/sh takes pipefail from SHELLOPTS; under it the long fixture's early match reads as printf's SIGPIPE (statuses:$SIGP); without it, grep's own 0"
PF=SHELLOPTS=errexit:pipefail:nounset
leg full "$F/p/longbranch.json" "$PF";    check "(fold2) $PF: the reviewer's fixture, git checkout -b x then the filler, stays silent (the exemption)" "$D" "(silent)"
leg full "$F/p/longbranch.json" SHELLOPTS=pipefail
check "(fold2) SHELLOPTS=pipefail alone, the reviewer's condition: the same fixture stays silent" "$D" "(silent)"
leg full "$F/p/longreset.json" "$PF";     check "(fold2) $PF: its destructive counterpart, git reset --hard then the same filler, asks with the existing text" "$D" "$STD"
leg exfail "$F/p/longbranch.json" "$PF";  has "(fold2) $PF: grep failing on the exemption, long fixture: asks, named for the exemption (grep's own status, not printf's)" "$D" "PreToolUse|ask|Destructive-git guard: grep failed (exit 2) while checking the checkout -b exemption"
leg grepfail "$F/p/longreset.json" "$PF"; has "(fold2 control) $PF: grep failing (exit 2) on the long reset: asks, named" "$D" "PreToolUse|ask|Destructive-git guard: grep failed (exit 2) while looking for destructive git verbs"
leg jqfail "$F/p/longreset.json" "$PF";   has "(fold2 control) $PF: jq failing (exit 3) on the long reset: asks, named" "$D" "PreToolUse|ask|Destructive-git guard: jq failed (exit 3), and the raw input holds git"
leg full "$F/p/ls.json" "$PF";            check "(fold2 control) $PF: ls stays silent" "$D" "(silent)"
leg full "$F/p/longbranch.json";          check "(control) with no inherited option the long fixtures decide as the short ones: the long git checkout -b x stays silent" "$D" "(silent)"
leg full "$F/p/longreset.json";           check "(control) …and the long git reset --hard asks with the existing text" "$D" "$STD"
# the switches themselves: the text before `ask() {` is the guard's prefix. Run alone with a probe body
# under all three options, it must leave each one off (control: the body alone ends at the unset name)
case "$CMD" in *"ask() {"*) PFX=${CMD%%"ask() {"*} ;; *) PFX= ;; esac
BODY='printf "[%s]" "$UNSET_PROBE"; false; false | true; printf "pf=%s" "$?"'
check "(fold2) the guard's prefix, run alone under $PF, switches all three off: an unset name expands empty, a failing command runs on, a failing first stage is not the status" \
      "$(env -i PATH="$F/bin-full" SHELLOPTS=errexit:pipefail:nounset /bin/sh -c "$PFX$BODY" < /dev/null 2>"$F/err-pfx.txt")" "[]pf=0"
check "…control: the probe body alone under $PF ends at the unset name (no output, an error on stderr)" \
      "$(env -i PATH="$F/bin-full" SHELLOPTS=errexit:pipefail:nounset /bin/sh -c "$BODY" < /dev/null 2>"$F/err-pfx.txt"):$([ -s "$F/err-pfx.txt" ] && echo stderr || echo no-stderr)" ":stderr"
# a shell without pipefail: there the switch must be tolerated. /bin/dash (where present and lacking
# pipefail) ends at a bare `set +o pipefail`, since a special built-in's error ends a POSIX shell
if [ -x /bin/dash ] && ! env -i /bin/dash -c 'command set +o pipefail' 2>"$F/err-dash.txt"; then
  check "(premise) /bin/dash lacks pipefail, and a bare set +o pipefail ends it before its next command (the case the switch must tolerate)" \
        "$(env -i /bin/dash -c 'set +o pipefail 2>/dev/null || :; echo survived' 2>"$F/err-dash.txt"; echo "rc=$?")" "rc=2"
  check "(fold2) under /bin/dash after set -eu, the guard's prefix runs on past its pipefail switch and leaves errexit and nounset off" \
        "$(env -i /bin/dash -c "set -eu; $PFX$BODY" < /dev/null 2>"$F/err-dash.txt")" "[]pf=0"
  SH=/bin/dash
  leg full "$F/p/reset.json";      check "(fold2 control) under /bin/dash: git reset --hard asks with the existing text" "$D" "$STD"
  leg full "$F/p/longbranch.json"; check "(fold2 control) under /bin/dash: the long git checkout -b x stays silent" "$D" "(silent)"
  leg full "$F/p/ls.json";         check "(fold2 control) under /bin/dash: ls stays silent" "$D" "(silent)"
  SH=/bin/sh
else
  ok "(premise) no /bin/dash lacking pipefail on this machine, so the switch's tolerance is not exercised here"
fi

echo "== h. every run exits 0; the guard and this suite wrote nothing =="
check "every guard run exited 0 (the decision travels in the JSON)" "$NONZERO" "0"
chmod u+w "$F/cwd" "$F/home"
manifest "$F/cwd" "$F/home" "$F/p" > "$F/manifest.after"
check "the read-only working directory, home and payloads are byte-identical ($(wc -l < "$F/manifest.after" | tr -d ' ') files)" \
      "$(cmp -s "$F/manifest.before" "$F/manifest.after" && echo same || echo differ)" "same"
check "the settings file is unchanged" "$(hashf "$SETTINGS")" "$SUM_BEFORE"
WRITES='>|(^|[^A-Za-z_-])(rm|mv|cp|tee|touch|mkdir|ln|dd|chmod|truncate|install)([^A-Za-z_-]|$)'
check "source grep: the guard holds no redirection (beside 2>/dev/null) and no write verb" \
      "$(printf '%s' "$CMD" | sed 's#2>/dev/null##g' | grep -cE "$WRITES")" "0"
check "…positive control: the same grep hits a planted redirection and a planted rm" \
      "$(printf '%s\n%s\n' 'printf x > /tmp/y' 'rm -f z' | grep -cE "$WRITES")" "2"

echo
echo "fixtures removed on exit: $F"
if [ "$FAIL" -eq 0 ]; then echo "PASS $PASS/$((PASS+FAIL))"; else echo "FAIL $FAIL/$((PASS+FAIL))"; exit 1; fi
