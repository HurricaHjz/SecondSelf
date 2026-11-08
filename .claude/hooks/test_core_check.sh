#!/bin/sh
# test_core_check.sh — core-check.py: what must warn, what must not, and what cannot finish.
#
# Every case runs on a fixture clone under its own mktemp directory, removed on exit: a small release
# tagged v0.1.0, with the shape a set-up copy has. Git comes from PATH, or from a stub in the fixture
# directory that fails, hangs or slows one named step and otherwise runs the real git. HOME and git's
# global and system settings are fixture-only. The hook is stdout-only, and leg g proves it: `.git/index`
# stays byte-identical across a run with stale stat data, a checksum manifest of the whole clone stays
# the same, and each of those two has a control the same check must catch. Each source grep has a
# positive control.
#
# Bounds asserted here: 8 seconds is the hook's one deadline, 10 seconds the limit of the hook's
# settings line, and 3 seconds the stub's delay: under any bound of 5 seconds a call, so only a
# deadline across the calls can stop it. 5 names is the hook's cap on the line, 120 characters a name.
#
# Run:  sh .claude/hooks/test_core_check.sh     Last line: PASS n/n or FAIL k/n. A broken premise
#       prints PROBE FAILED and exits 2. It used 31 seconds of CPU and took three and a half minutes
#       at a load average of 18, 16 seconds of that the deadline legs.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
HOOK="$HERE/core-check.py"
[ -f "$HOOK" ] || { echo "PROBE FAILED: no core-check.py beside this suite"; exit 2; }
PY=$(command -v python3); REAL_GIT=$(command -v git)
for t in "$PY" "$REAL_GIT"; do
  case "$t" in /*) ;; *) echo "PROBE FAILED: the suite needs python3 and git on PATH (found '$PY', '$REAL_GIT')"; exit 2 ;; esac
done
F="$(mktemp -d "${TMPDIR:-/tmp}/core-check.XXXXXX")" || { echo "PROBE FAILED: cannot create fixtures"; exit 2; }
[ -d "$F" ] || { echo "PROBE FAILED: missing fixture directory"; exit 2; }
trap 'chmod -R u+w "$F" 2>/dev/null; rm -rf "$F"' 0
trap 'exit 2' HUP INT TERM
HOME="$F/home"; mkdir -p "$HOME"; export HOME
GIT_CONFIG_NOSYSTEM=1; GIT_CONFIG_GLOBAL=/dev/null; export GIT_CONFIG_NOSYSTEM GIT_CONFIG_GLOBAL
GIT_AUTHOR_NAME=fixture; GIT_AUTHOR_EMAIL=fixture@example.invalid
GIT_COMMITTER_NAME=fixture; GIT_COMMITTER_EMAIL=fixture@example.invalid
export GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY CLAUDE_PROJECT_DIR

PASS=0; FAIL=0; RUNS=0; NONZERO=0; NOTONE=0; NOISY=0
ok()   { PASS=$((PASS+1)); echo "  ok   — $1"; }
bad()  { FAIL=$((FAIL+1)); echo "  FAIL — $1"; }
check(){ [ "$2" = "$3" ] && ok "$1" || bad "$1 (want '$3', got '$2')"; }
has()  { case "$2" in *"$3"*) ok "$1" ;; *) bad "$1 (want text containing '$3', got '$2')" ;; esac; }
lacks(){ case "$2" in *"$3"*) bad "$1 (found '$3' in '$2')" ;; *) ok "$1" ;; esac; }
manifest(){ (cd "$1" && find . -type f -print | LC_ALL=C sort | while IFS= read -r f; do printf '%s %s\n' "$(cksum < "$f")" "$f"; done); }
core_count(){ git -C "$R" ls-files -- CLAUDE.md setup.sh .claude/settings.json .claude/core-paths .claude/hooks .claude/agents .claude/skills | wc -l | tr -d ' '; }

# The release every fixture copies, tagged v0.1.0. The list keeps a comment, a blank line and folders
# written with a trailing slash, as the shipped list does.
T="$F/template"
mkdir -p "$T/.claude/hooks" "$T/.claude/agents" "$T/.claude/skills/query" "$T/wiki/concepts" "$T/examples"
cat > "$T/.claude/core-paths" <<'LIST_END'
# the fixture's core
CLAUDE.md
setup.sh

.claude/settings.json
.claude/core-paths
.claude/hooks/
.claude/agents/
.claude/skills/
LIST_END
printf '# rules\n' > "$T/CLAUDE.md"
printf '#!/bin/sh\nexit 0\n' > "$T/setup.sh"; chmod 755 "$T/setup.sh"
printf '# readme\n' > "$T/README.md"
printf 'demo\n' > "$T/examples/demo.md"
printf '{"permissions": {"deny": ["Edit(/CLAUDE.md)"], "allow": ["Bash(ls)"]}, "hooks": {"SessionStart": []}}\n' > "$T/.claude/settings.json"
printf -- '---\nname: helper\ndescription: A fixture helper.\nmodel: opus\neffort: high\n---\nBody of the helper.\nmodel: a line of the product\n' > "$T/.claude/agents/helper.md"
printf 'skill\n' > "$T/.claude/skills/query/SKILL.md"
printf 'space\n' > "$T/.claude/skills/query/with space.md"
cp "$HOOK" "$T/.claude/hooks/core-check.py"
printf '/wiki/**\n/.claude/settings.local.json\n/.claude/skills/my-*/\n/.claude/agents/my-*.md\n__pycache__/\n' > "$T/.gitignore"
printf 'page\n' > "$T/wiki/concepts/page.md"
git -C "$T" init -q
git -C "$T" add -A
git -C "$T" commit -qm release
git -C "$T" tag -a v0.1.0 -m v0.1.0
# A fresh copy of that release at $F/$1; sets R.
mkrepo() {
  R="$F/$1"
  chmod -R u+w "$R" 2>/dev/null; rm -rf "$R"
  cp -Rp "$T" "$R"
}
commit_all(){ git -C "$R" add -A && git -C "$R" commit -qm "$1"; }

STARTUP='{"hook_event_name":"SessionStart","source":"startup"}'
# run [NAME=VALUE ...]: the hook on $R as a fresh start, with the tallies every run feeds. Sets OUT, RC.
tally(){
  RUNS=$((RUNS+1))
  [ "$RC" -eq 0 ] || NONZERO=$((NONZERO+1))
  [ ! -s "$F/stderr" ] || NOISY=$((NOISY+1))
}
run(){
  OUT=$(printf '%s' "$STARTUP" | env CLAUDE_PROJECT_DIR="$R" "$@" "$PY" -B "$HOOK" 2>"$F/stderr"); RC=$?
  tally
  [ "$(printf '%s\n' "$OUT" | wc -l | tr -d ' ')" = 1 ] && [ -n "$OUT" ] || NOTONE=$((NOTONE+1))
}
# stdin_run TEXT: the same with TEXT on stdin, for the source legs.
stdin_run(){
  OUT=$(printf '%s' "$1" | env CLAUDE_PROJECT_DIR="$R" "$PY" -B "$HOOK" 2>"$F/stderr"); RC=$?
  tally
}
DIFFER_TAIL='Tell the owner in your first reply; a bug report carries this line.'
UNCHECKED_TAIL='Tell the owner in your first reply; MANUAL.md, "Updating", says what to do.'
unchanged(){ check "$1" "$OUT" "core: ${2:-v0.1.0}, unchanged ($(core_count) files)"; }
warns()    { check "$1" "$OUT" "core: ${4:-v0.1.0}, $2 file(s) differ from the release: $3. $DIFFER_TAIL"; }
unchecked(){ check "$1" "$OUT" "core: not checked ($2). $UNCHECKED_TAIL"; }

mkdir -p "$F/stub"
{
  printf '#!/bin/sh\n'
  printf "REAL='%s'\n" "$REAL_GIT"
  cat <<'STUB_END'
# Fixture stub. STUB_STEP names one git step; STUB_MODE fail or hang applies to it. STUB_SLOW delays
# every call. STUB_LOG collects this stub's process numbers, STUB_CHILD those of its hanging child.
[ -z "${STUB_LOG-}" ] || printf '%s\n' "$$" >> "$STUB_LOG"
step=
for a in "$@"; do
  case "$a" in
    rev-parse|describe|ls-files|status|diff|cat-file) step=$a; break ;;
  esac
done
[ -z "${STUB_SLOW-}" ] || sleep "$STUB_SLOW"
if [ -n "$step" ] && [ "$step" = "${STUB_STEP-}" ]; then
  case "${STUB_MODE-}" in
    fail) echo "fatal: /ho""me/someone/private-folder: stub failure" >&2; exit 128 ;;
    hang) sleep 300 & printf '%s\n' "$!" >> "$STUB_CHILD"; wait; exit 0 ;;
  esac
fi
exec "$REAL" "$@"
STUB_END
} > "$F/stub/git"
chmod +x "$F/stub/git"
SPATH="$F/stub:$PATH"

echo "== setup: the hook at $HOOK; fixtures under $F =="
mkrepo work
run
check "(probe) the fixture is a clean release: one line, exit 0, nothing on stderr" "$RC:$(printf '%s' "$OUT" | cut -c1-21):$(wc -c < "$F/stderr" | tr -d ' ')" "0:core: v0.1.0, unchang:0"
[ "$(core_count)" -gt 5 ] || { echo "PROBE FAILED: the fixture's core has $(core_count) files"; exit 2; }

echo "== a. must not warn =="
mkrepo work; run
unchanged "clean: unchanged, with a count made apart from the hook ($(core_count) files)"
mkrepo work; git -C "$R" tag -d v0.1.0 >/dev/null; git -C "$R" tag v0.1.0; run
unchanged "a lightweight tag reads the same as an annotated one"
mkrepo work; printf 'mine\n' >> "$R/README.md"; printf 'x\n' > "$R/notes.txt"; rm "$R/examples/demo.md"; run
unchanged "a change outside the core: an edited README, a new root file, a deleted example"
mkrepo work; printf 'mine\n' >> "$R/README.md"; commit_all outside; run
unchanged "a commit on top that touches only files outside the core"
mkrepo work; mkdir -p "$R/.claude/skills/my-own"; printf 'own\n' > "$R/.claude/skills/my-own/SKILL.md"
printf 'own\n' > "$R/.claude/agents/my-helper.md"; printf '{}\n' > "$R/.claude/settings.local.json"; printf 'p\n' > "$R/wiki/concepts/new.md"; run
unchanged "the user's layer: an own skill, an own helper, local settings, a wiki page"
mkrepo work; mkdir -p "$R/.claude/hooks/__pycache__"; printf 'x\n' > "$R/.claude/hooks/__pycache__/x.pyc"; run
unchanged "an ignored file inside a core folder"
mkrepo work; git -C "$R" ls-files -z -- CLAUDE.md setup.sh .claude/hooks .claude/skills | (cd "$R" && xargs -0 chmod a-w); run
unchanged "a locked core: write bits off, the mode alone is no difference"
check "…control: the fixture really is locked" "$( [ -w "$R/CLAUDE.md" ] && echo writable || echo locked)" "locked"
mkrepo work; printf 'more\n' >> "$R/CLAUDE.md"; commit_all next; git -C "$R" tag -a v0.2.0 -m v0.2.0; run
unchanged "a later release: its tag is the one compared, so its own core change reads unchanged" "v0.2.0"
mkrepo work; git -C "$R" tag nightly; git -C "$R" tag v2-mine; git -C "$R" tag v0.2.0-rc1; run
unchanged "a tag that is no release is passed over"

echo "== a2. only a derived line moved =="
DEF=.claude/agents/helper.md
mkrepo work; "$PY" -B -c 'import sys; p=sys.argv[1]; b=open(p).read().replace("model: opus","model: sonnet",1); open(p,"w").write(b)' "$R/$DEF"; run
unchanged "the frontmatter's model: line moved"
mkrepo work; "$PY" -B -c 'import sys; p=sys.argv[1]; b=open(p).read().replace("effort: high","effort: low",1); open(p,"w").write(b)' "$R/$DEF"; run
unchanged "the frontmatter's effort: line moved"
mkrepo work; "$PY" -B -c 'import sys; p=sys.argv[1]; b=open(p).read().replace("effort: high\n","",1); open(p,"w").write(b)' "$R/$DEF"; run
unchanged "the effort: line removed, which the throttle can do"
mkrepo work; "$PY" -B -c 'import sys; p=sys.argv[1]; b=open(p).read().replace("model: opus","model: sonnet  # a kept comment",1); open(p,"w").write(b)' "$R/$DEF"; commit_all throttle; run
unchanged "a derived line committed on top: the content still decides"

echo "== a3. permissions.allow is the user's; the rest of the settings is not =="
ST=.claude/settings.json
setjson(){ "$PY" -B -c 'import json, sys; p, code = sys.argv[1:3]; d = json.load(open(p)); exec(code); open(p, "w").write(json.dumps(d, indent=2) + "\n")' "$R/$ST" "$1"; }
mkrepo work; setjson 'd["permissions"]["allow"].append("Bash(git status)")'; run
unchanged "an always-allow answer added to permissions.allow"
mkrepo work; setjson 'del d["permissions"]["allow"]'; run
unchanged "permissions.allow removed"
mkrepo work; setjson 'pass'; run
unchanged "the same settings in a new layout: compared as data, not bytes"
mkrepo work; setjson 'd["permissions"]["allow"].append("Bash(ls -la)")'; commit_all approval; run
unchanged "an allow line committed on top"
mkrepo work; printf '{"hooks": {"SessionStart": []}}\n' > "$R/$ST"; commit_all noblock; git -C "$R" tag -a v0.2.0 -m v0.2.0
setjson 'd["permissions"] = {"allow": ["Bash(ls)"]}'; run
unchanged "a release with no permissions block: an allow list added is still the user's" "v0.2.0"
mkrepo work; setjson 'd["permissions"]["deny"].append("Edit(/x)")'; run
warns "the deny list in the same block stays checked: an added line warns" 1 "$ST"
mkrepo work; setjson 'd["permissions"]["deny"] = []'; run
warns "…and an emptied deny list warns" 1 "$ST"
mkrepo work; setjson 'del d["permissions"]["deny"]'; run
warns "…and a deleted deny list warns" 1 "$ST"
mkrepo work; setjson 'd["permissions"]["deny"] = []; d["permissions"]["allow"].append("Bash(rm)")'; run
warns "…and an allow line cannot cover a deny change made with it" 1 "$ST"
mkrepo work; setjson 'd["permissions"]["defaultMode"] = "bypassPermissions"'; run
warns "another key in the permissions block warns" 1 "$ST"
mkrepo work; setjson 'd["permissions"]["ask"] = ["Bash(ls)"]'; run
warns "…and so does an ask list" 1 "$ST"
mkrepo work; setjson 'd["hooks"]["SessionStart"].append({"hooks": []})'; run
warns "a change to the hooks block warns" 1 "$ST"
mkrepo work; setjson 'd["env"] = {"X": "1"}'; run
warns "a new top-level key warns" 1 "$ST"
mkrepo work; printf 'not json\n' > "$R/$ST"; run
warns "settings that no longer parse warn" 1 "$ST"
mkrepo work; printf '[]\n' > "$R/$ST"; run
warns "settings that are not an object warn" 1 "$ST"
mkrepo work; rm "$R/$ST"; run
warns "deleted settings warn" 1 "$ST"

echo "== a4. the working contents decide: git's two steps only name the candidates =="
RS=.claude/skills/query/SKILL.md
mkrepo work; printf 'edit\n' >> "$R/CLAUDE.md"; commit_all ontop; git -C "$R" show v0.1.0:CLAUDE.md > "$R/CLAUDE.md"; run
unchanged "an edit committed on top, then the release's contents put back on disk"
check "…control: git still names that file on both steps, so only its contents clear it" "$(git -C "$R" status --porcelain -- CLAUDE.md):$(git -C "$R" diff --name-only v0.1.0 HEAD -- CLAUDE.md)" " M CLAUDE.md:CLAUDE.md"
printf 'other\n' >> "$R/CLAUDE.md"; run
warns "…and a real edit in that same state still warns" 1 "CLAUDE.md"
mkrepo work; printf 'edit\n' >> "$R/$RS"; commit_all ontop; git -C "$R" show "v0.1.0:$RS" > "$R/$RS"; printf 'edit\n' >> "$R/setup.sh"; run
warns "a file put back beside a real edit: only the edit is named" 1 "setup.sh"
mkrepo work; git -C "$R" rm -q setup.sh; commit_all drop; git -C "$R" show v0.1.0:setup.sh > "$R/setup.sh"; run
unchanged "a file a commit removed, put back with the release's contents"
mkrepo work; printf 'x\n' > "$R/.claude/skills/query/added.md"; commit_all add; run
warns "a file a commit added, still on disk" 1 ".claude/skills/query/added.md"
rm "$R/.claude/skills/query/added.md"; run
unchanged "a file a commit added and the disk no longer holds: absent, as in the release"
mkrepo work; chmod a-x "$R/setup.sh"; run
unchanged "the execute bit alone moved: the comparison is of contents"
check "…control: git does list that file" "$(git -C "$R" status --porcelain -- setup.sh)" " M setup.sh"
mkrepo work; cp "$R/CLAUDE.md" "$R/elsewhere.md"; rm "$R/CLAUDE.md"; ln -s elsewhere.md "$R/CLAUDE.md"; run
warns "a link in place of a core file, to a copy of its contents: a link is not those contents" 1 "CLAUDE.md"
mkrepo work; printf -- '---\nname: query\nmodel: opus\n---\nBody.\n' > "$R/$RS"; commit_all frontmatter; git -C "$R" tag -a v0.2.0 -m v0.2.0
"$PY" -B -c 'import sys; p=sys.argv[1]; b=open(p).read().replace("model: opus","model: sonnet",1); open(p,"w").write(b)' "$R/$RS"; run
warns "a model: line moved in a file that is no definition: the exception is the definitions' alone" 1 "$RS" "v0.2.0"
mkrepo work; printf 'edit\n' >> "$R/setup.sh"; rm -rf "$R/.claude/skills/query"; printf 'x\n' > "$R/.claude/skills/query"; commit_all swap
git -C "$R" show v0.1.0:setup.sh > "$R/setup.sh"; run
warns "a file committed where the release held a folder: git's reply for the folder is stepped over, so the file after it still reads as put back" 3 ".claude/skills/query, .claude/skills/query/SKILL.md, .claude/skills/query/with space.md"
mkrepo work; printf 'x\n' > "$R/.claude/skills/query/a blob"; run
warns "a new file named with a space and the word blob: git's missing reply is read as one" 1 ".claude/skills/query/a blob"
CR=$(printf '\r'); mkrepo work; cp "$R/$RS" "$R/$RS$CR"; run
warns "a new name ending in a carriage return, with the contents of the file git would answer for" 1 "$RS?"

echo "== b. must warn =="
mkrepo work; printf 'edit\n' >> "$R/CLAUDE.md"; run
warns "an edit" 1 "CLAUDE.md"
mkrepo work; rm "$R/.claude/skills/query/SKILL.md"; run
warns "a deletion" 1 ".claude/skills/query/SKILL.md"
mkrepo work; printf 'x\n' > "$R/.claude/skills/query/extra.md"; run
warns "a new file in a core folder" 1 ".claude/skills/query/extra.md"
mkrepo work; mkdir -p "$R/.claude/skills/mine"; printf 'x\n' > "$R/.claude/skills/mine/SKILL.md"; run
warns "a skill made without the prefix is a new file in a core folder" 1 ".claude/skills/mine/SKILL.md"
mkrepo work; printf 'edit\n' >> "$R/CLAUDE.md"; commit_all candidate; git -C "$R" tag -a v0.2.0-rc1 -m candidate; run
warns "a release candidate is no release, so a core change under its tag still warns" 1 "CLAUDE.md"
mkrepo work; printf 'edit\n' >> "$R/CLAUDE.md"; commit_all ontop; run
warns "an edit committed on top: status alone cannot see it" 1 "CLAUDE.md"
check "…control: status is empty here, so only the tree diff found it" "$(git -C "$R" status --porcelain)" ""
mkrepo work; git -C "$R" rm -q setup.sh; commit_all drop; run
warns "a whole list line's file removed by a commit: a difference, not a broken list" 1 "setup.sh"
mkrepo work; git -C "$R" update-index --assume-unchanged CLAUDE.md; run
warns "a core file flagged assume-unchanged, with no edit" 1 "CLAUDE.md"
mkrepo work; printf 'edit\n' >> "$R/CLAUDE.md"; git -C "$R" update-index --assume-unchanged CLAUDE.md; run
warns "…and with an edit the flag hides" 1 "CLAUDE.md"
check "…control: the flag does hide it from status" "$(git -C "$R" status --porcelain)" ""
mkrepo work; printf 'edit\n' >> "$R/CLAUDE.md"; git -C "$R" update-index --skip-worktree CLAUDE.md; run
warns "a core file flagged skip-worktree" 1 "CLAUDE.md"
mkrepo work; printf 'edit\n' >> "$R/.claude/skills/query/with space.md"; run
warns "a core path with a space is one name" 1 ".claude/skills/query/with space.md"
NAIVE=.claude/skills/query/naïve.md
mkrepo work; printf 'x\n' > "$R/$NAIVE"; run
warns "a core path outside ASCII is printed as itself, unquoted" 1 "$NAIVE"
mkrepo work; git -C "$R" mv .claude/skills/query/SKILL.md .claude/skills/query/RENAMED.md; run
warns "a rename reads as both of its names" 2 ".claude/skills/query/RENAMED.md, .claude/skills/query/SKILL.md"
mkrepo work; printf 'x' >> "$R/$DEF"; run
warns "a definition's body edited" 1 "$DEF"
mkrepo work; "$PY" -B -c 'import sys; p=sys.argv[1]; b=open(p).read().replace("a line of the product","a changed line",1); open(p,"w").write(b)' "$R/$DEF"; run
warns "a model: line in the body is the product's, so it warns" 1 "$DEF"
mkrepo work; "$PY" -B -c 'import sys; p=sys.argv[1]; b=open(p).read().replace("A fixture helper.","Changed.",1); open(p,"w").write(b)' "$R/$DEF"; run
warns "a frontmatter line other than the derived two" 1 "$DEF"
mkrepo work; "$PY" -B -c 'import sys; p=sys.argv[1]; b=open(p).read().replace("model: opus","model: sonnet",1).replace("Body of","Edited",1); open(p,"w").write(b)' "$R/$DEF"; run
warns "a derived line moved together with the body: the body still warns" 1 "$DEF"
mkrepo work; rm "$R/$DEF"; run
warns "a deleted definition" 1 "$DEF"
mkrepo work; i=1; while [ $i -le 7 ]; do printf 'x\n' > "$R/.claude/skills/query/n$i.md"; i=$((i+1)); done; run
warns "seven files: five names and the rest counted" 7 ".claude/skills/query/n1.md, .claude/skills/query/n2.md, .claude/skills/query/n3.md, .claude/skills/query/n4.md, .claude/skills/query/n5.md and 2 more"
mkrepo work; "$PY" -B -c 'import sys; p=sys.argv[1]; b=open(p).read().replace(".claude/hooks/\n","",1); open(p,"w").write(b)' "$R/.claude/core-paths"; run
warns "the list narrowed: it names itself, so the narrowing shows" 1 ".claude/core-paths"
mkrepo work; "$PY" -B -c 'import sys; p=sys.argv[1]; b=open(p).read().replace(".claude/core-paths\n","",1); open(p,"w").write(b)' "$R/.claude/core-paths"; run
warns "the list's own line taken out: it is checked against itself regardless" 1 ".claude/core-paths"

echo "== b2. a flag warns whatever the file's name and whatever its contents =="
for FLAG in assume-unchanged skip-worktree; do
  mkrepo work; git -C "$R" update-index "--$FLAG" "$DEF"; run
  warns "a definition flagged $FLAG, with no edit" 1 "$DEF"
  mkrepo work; "$PY" -B -c 'import sys; p=sys.argv[1]; b=open(p).read().replace("model: opus","model: sonnet",1); open(p,"w").write(b)' "$R/$DEF"; git -C "$R" update-index "--$FLAG" "$DEF"; run
  warns "a definition flagged $FLAG, only a derived line moved" 1 "$DEF"
  mkrepo work; git -C "$R" update-index "--$FLAG" "$ST"; run
  warns "settings flagged $FLAG, with no edit" 1 "$ST"
  mkrepo work; setjson 'd["permissions"]["allow"].append("Bash(git status)")'; git -C "$R" update-index "--$FLAG" "$ST"; run
  warns "settings flagged $FLAG, only permissions.allow moved" 1 "$ST"
done
mkrepo work; git -C "$R" update-index --assume-unchanged "$DEF"; printf 'edit\n' >> "$R/$RS"; run
warns "a flagged definition beside a plain edit: both named, in order" 2 "$DEF, $RS"
mkrepo work; printf 'edit\n' >> "$R/CLAUDE.md"; commit_all ontop; git -C "$R" show v0.1.0:CLAUDE.md > "$R/CLAUDE.md"; git -C "$R" update-index --assume-unchanged CLAUDE.md; run
warns "a flagged file put back to the release's contents: the flag still warns" 1 "CLAUDE.md"

echo "== c. cannot finish: each says not checked, and none says unchanged =="
mkrepo work; rm -rf "$R/.git"; run
unchecked "no git record: a ZIP download" "this copy has no git record of a release"
mkrepo outer; mkdir -p "$R/vault/.claude"; printf 'CLAUDE.md\n' > "$R/vault/.claude/core-paths"; printf 'x\n' > "$R/vault/CLAUDE.md"; commit_all nested; git -C "$R" tag -a v0.2.0 -m v0.2.0
R="$F/outer/vault"; run
unchecked "a folder inside some other repository: that repository's tag says nothing about this copy" "this copy has no git record of a release"
mkrepo work; git -C "$R" tag -d v0.1.0 >/dev/null; run
unchecked "no tag: a template copy" "no release tag in this copy's history"
mkrepo work; git -C "$R" tag -d v0.1.0 >/dev/null; git -C "$R" tag nightly; run
unchecked "…and a tag that is no release is no tag" "no release tag in this copy's history"
mkrepo work; rm "$R/.claude/core-paths"; run
unchecked "no list: the maintainer's own vault" "no core list in this folder"
mkrepo work; : > "$R/.claude/core-paths"; run
unchecked "an empty list" "the core list is empty"
mkrepo work; printf '# only a comment\n\n' > "$R/.claude/core-paths"; run
unchecked "a list of comments alone" "the core list is empty"
mkrepo work; printf '\377\376\n' > "$R/.claude/core-paths"; run
unchecked "a list that is not text" "the core list could not be read"
mkrepo work; printf 'no/such/path\n' > "$R/.claude/core-paths"; run
unchecked "a pathspec matching nothing" "a line of the core list matches nothing git tracks"
mkrepo work; printf 'CLAUDE.md\nno/such/path\n' > "$R/.claude/core-paths"; run
unchecked "…one line of several matching nothing: the check cannot vouch for it" "a line of the core list matches nothing git tracks"
mkrepo work; printf 'setup.sh\n.claude/core-paths\n' > "$R/.claude/core-paths"; git -C "$R" rm -q --cached setup.sh .claude/core-paths; git -C "$R" commit -qm untrack; run
unchecked "every listed path removed by commits: nothing tracked is left to count" "the core list matches no tracked file"
mkrepo work; run PATH="$F/empty"
unchecked "git missing from PATH" "git is not installed"
R="$F/no-such-folder"; run
unchecked "a project folder that does not exist" "no core list in this folder"
mkrepo work; printf 'edit\n' >> "$R/CLAUDE.md"
run PATH="$SPATH" STUB_STEP=rev-parse STUB_MODE=fail
unchecked "git rev-parse exits 128, the clone's .git present" "git rev-parse failed with exit 128"
run PATH="$SPATH" STUB_STEP=describe STUB_MODE=fail
unchecked "git describe exits 128" "no release tag in this copy's history"
run PATH="$SPATH" STUB_STEP=ls-files STUB_MODE=fail
unchecked "git ls-files exits 128" "git ls-files failed with exit 128"
run PATH="$SPATH" STUB_STEP=status STUB_MODE=fail
unchecked "git status exits 128: an edit on disk does not turn it into a warning or an unchanged" "git status failed with exit 128"
lacks "…git's own error text, which can hold a home path, stays off the line" "$OUT" "private-folder"
run PATH="$SPATH" STUB_STEP=diff STUB_MODE=fail
unchecked "git diff exits 128" "git diff failed with exit 128"
mkrepo work; "$PY" -B -c 'import sys; p=sys.argv[1]; b=open(p).read().replace("model: opus","model: sonnet",1); open(p,"w").write(b)' "$R/$DEF"
run PATH="$SPATH" STUB_STEP=cat-file STUB_MODE=fail
unchecked "git cat-file exits 128: a derived line cannot be told from an edit" "git cat-file failed with exit 128"
mkrepo work; printf 'edit\n' >> "$R/CLAUDE.md"; commit_all ontop; git -C "$R" show v0.1.0:CLAUDE.md > "$R/CLAUDE.md"
run PATH="$SPATH" STUB_STEP=cat-file STUB_MODE=fail
unchecked "…nor a file put back from an edit, so no unchanged rests on a reply that never came" "git cat-file failed with exit 128"

echo "== d. one deadline across the calls =="
mkrepo work
T0=$(date +%s); : > "$F/stub.log"; : > "$F/child.log"
run PATH="$SPATH" STUB_STEP=status STUB_MODE=hang STUB_LOG="$F/stub.log" STUB_CHILD="$F/child.log"
T1=$(date +%s)
unchecked "a git that hangs: the line still comes" "git took too long"
check "…inside the hook's 10-second limit, and not before the deadline ($((T1-T0)) s)" "$([ $((T1-T0)) -ge 7 ] && [ $((T1-T0)) -lt 10 ] && echo inside || echo outside)" "inside"
gone(){ n=0; while [ $n -lt 20 ]; do kill -0 "$1" 2>/dev/null || { echo gone; return; }; sleep 0.1; n=$((n+1)); done; echo running; }
check "…the hanging stub's child was killed with it, so nothing outlives the hook" "$(gone "$(cat "$F/child.log")")" "gone"
T0=$(date +%s)
run PATH="$SPATH" STUB_SLOW=3
T1=$(date +%s)
unchecked "every call takes 3 seconds: each passes any 5-second bound, and the deadline across them stops the run" "git took too long"
check "…inside the 10-second limit ($((T1-T0)) s), where five such calls would take 15" "$([ $((T1-T0)) -lt 10 ] && echo inside || echo outside)" "inside"

echo "== e. fresh starts only =="
mkrepo work; printf 'edit\n' >> "$R/CLAUDE.md"
EXPECT="core: v0.1.0, 1 file(s) differ from the release: CLAUDE.md. $DIFFER_TAIL"
stdin_run '{"source":"startup"}';  check "source startup: the line" "$RC:$OUT" "0:$EXPECT"
stdin_run '{"source":"clear"}';    check "source clear: the line, since the context starts afresh" "$RC:$OUT" "0:$EXPECT"
stdin_run '{"hook_event_name":"SessionStart"}'; check "no source field: the line" "$RC:$OUT" "0:$EXPECT"
stdin_run '';                      check "empty stdin: the line" "$RC:$OUT" "0:$EXPECT"
stdin_run 'not json';              check "malformed stdin: the line" "$RC:$OUT" "0:$EXPECT"
stdin_run '[1, 2]';                check "stdin that is not an object: the line" "$RC:$OUT" "0:$EXPECT"
stdin_run '{"source": 7}';         check "a source that is not a string: the line" "$RC:$OUT" "0:$EXPECT"
: > "$F/stub.log"
OUT=$(printf '%s' '{"source":"resume"}' | env CLAUDE_PROJECT_DIR="$R" PATH="$SPATH" STUB_LOG="$F/stub.log" "$PY" -B "$HOOK" 2>"$F/stderr"); RC=$?; tally
check "source resume: silent, exit 0" "$RC:$OUT" "0:"
check "…and it ran no git at all" "$(wc -l < "$F/stub.log" | tr -d ' ')" "0"
stdin_run '{"source":"compact"}';  check "source compact: silent, exit 0" "$RC:$OUT" "0:"
OUT=$(env CLAUDE_PROJECT_DIR="$R" "$PY" -B "$HOOK" --report </dev/null 2>"$F/stderr"); RC=$?; tally
check "--report: the same line" "$RC:$OUT" "0:$EXPECT"
OUT=$(printf '%s' '{"source":"resume"}' | env CLAUDE_PROJECT_DIR="$R" "$PY" -B "$HOOK" --report 2>"$F/stderr"); RC=$?; tally
check "…whatever stdin says" "$RC:$OUT" "0:$EXPECT"
OUT=$(cd "$F" && printf '%s' "$STARTUP" | "$PY" -B "$R/.claude/hooks/core-check.py" 2>"$F/stderr"); RC=$?; tally
check "no CLAUDE_PROJECT_DIR, run from elsewhere: the root comes from the hook's own place" "$RC:$OUT" "0:$EXPECT"

echo "== f. the line stays one safe line =="
mkrepo work; NL=$(printf 'a\nb.md'); printf 'x\n' > "$R/.claude/skills/query/$NL"; run
warns "a name holding a newline stays on the one line" 1 ".claude/skills/query/a?b.md"
mkrepo work; LONG=$("$PY" -B -c 'print("n" * 200)'); printf 'x\n' > "$R/.claude/skills/query/$LONG"; run
has "a long name is cut at 120 characters" "$OUT" "$(printf '%s' ".claude/skills/query/$LONG" | cut -c1-120). $DIFFER_TAIL"
mkrepo other; OTHER="$R"; mkrepo work; printf 'edit\n' >> "$R/CLAUDE.md"
run GIT_DIR="$OTHER/.git" GIT_WORK_TREE="$OTHER" GIT_INDEX_FILE="$OTHER/.git/index"
warns "an inherited GIT_DIR cannot turn this copy's edit into another clone's unchanged" 1 "CLAUDE.md"
check "…control: with the same settings plain git does read the other clone" "$(env GIT_DIR="$OTHER/.git" GIT_WORK_TREE="$OTHER" GIT_INDEX_FILE="$OTHER/.git/index" git -C "$R" status --porcelain)" ""

echo "== g. it changes nothing, and every run kept the contract =="
mkrepo work; touch -t 202001010101 "$R/CLAUDE.md"
SUM_INDEX=$(cksum < "$R/.git/index"); run
unchanged "stale stat data: still unchanged, by content"
check ".git/index is byte-identical after the run" "$(cksum < "$R/.git/index")" "$SUM_INDEX"
git -C "$R" status --porcelain >/dev/null
check "…control: a plain git status does rewrite it here" "$([ "$(cksum < "$R/.git/index")" = "$SUM_INDEX" ] && echo same || echo rewritten)" "rewritten"
mkrepo work; : > "$R/.git/index.lock"; run; rm "$R/.git/index.lock"
unchanged "another git holding index.lock: the check still finishes"
mkrepo work; printf 'edit\n' >> "$R/CLAUDE.md"; rm "$R/.claude/skills/query/SKILL.md"; printf 'x\n' > "$R/.claude/skills/query/extra.md"
manifest "$R" > "$F/manifest.before"; run
manifest "$R" > "$F/manifest.after"
has "a run on a tree with an edit, a deletion and a new file reports them" "$OUT" "3 file(s) differ"
check "the whole clone, .git included, is byte-identical after the run ($(wc -l < "$F/manifest.after" | tr -d ' ') files)" "$(cmp -s "$F/manifest.before" "$F/manifest.after" && echo same || echo differ)" "same"
printf 'x' >> "$R/.git/description"; manifest "$R" > "$F/manifest.control"
check "…control: one byte changed beside the index, the same manifest catches it" "$(cmp -s "$F/manifest.before" "$F/manifest.control" && echo same || echo differ)" "differ"
WRITES='open\([^)]*["'"'"'][wax+]|os\.(remove|unlink|rename|replace|mkdir|makedirs|rmdir|chmod|utime|symlink|link)\(|shutil\.(move|copy|rmtree)|write_text|write_bytes'
check "source grep: the hook holds no file-writing call" "$(grep -cE "$WRITES" "$HOOK")" "0"
check "…positive control: the same grep hits planted lines" "$(printf '%s\n%s\n%s\n' 'open(p, "w")' 'os.remove(p)' 'shutil.move(a, b)' | grep -cE "$WRITES")" "3"
VERBS='"(add|commit|update-index|checkout|restore|reset|merge|pull|fetch|push|stash|clean|gc|config|tag)"'
check "source grep: the hook names no git step that writes" "$(grep -cE "$VERBS" "$HOOK")" "0"
check "…positive control: the same grep hits planted steps" "$(printf '%s\n%s\n' 'git(root, "update-index")' 'git(root, "merge")' | grep -cE "$VERBS")" "2"
check "…second control: the six steps it does name are found by the same shape" "$(grep -oE '"(status|diff|describe|ls-files|rev-parse|cat-file)"' "$HOOK" | LC_ALL=C sort -u | wc -l | tr -d ' ')" "6"
check "every run exited 0 ($RUNS runs)" "$NONZERO" "0"
check "every run but the silent ones printed exactly one line" "$NOTONE" "0"
check "no run wrote to stderr" "$NOISY" "0"

echo
echo "fixtures removed on exit: $F"
if [ "$FAIL" -eq 0 ]; then echo "PASS $PASS/$((PASS+FAIL))"; else echo "FAIL $FAIL/$((PASS+FAIL))"; exit 1; fi
