#!/usr/bin/env bash
# test_publish_guard.sh — isolated tests for publish_guard.py (the publish gate's payload
# probe, item 121). Builds throwaway payloads under $TMPDIR, git and non-git. NEVER touches
# the real vault or any real repo. Run:  bash test_publish_guard.sh
#
# Covers, per case group: both probes fire on their own class; both stay quiet on the
# legitimate shapes the live payload actually contains; every premise failure exits 2 rather
# than reporting clean; the index — not the working tree — is what the guard reads.
# Group 11 covers probe 4, credential values, against a FAKE store generated per run with a
# fresh random part; every one of its legs also asserts the run's whole output never carries
# that value. No leg reads a real credential store: every call names a fixture vault, whose
# default store is a fixture path, or passes --credentials (group 11's last leg checks this).
# Group 12 covers what can still carry a value out: an escaped copy (an OSError's text, a %r,
# git's quoting, a crash), a store the guard cannot stat, a message printed before the store is
# read, and a value whose backslash readers read differently. Its leak check looks for every
# escaped form of each fake value as well as the raw one; its stub git replays text real git
# produced. Group 8's last legs check the docs claim no more than the guard keeps.
# Group 13 covers --draft: the same probes on one suggestion draft, nothing adjudicated.
#
# Hash gitlink blobs inside the fixture repository so the suite is independent of its caller.
# Group 7d controls this by running the build outside every repository.
# See register entry 2026-09-08 06:35.

set -uo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="$SKILL/publish_guard.py"
# The two cases below call the guard with NO --vault, so it derives one three directories above
# itself: a vault only where this skill sits in one. From a staged copy that derivation lands
# outside any vault and the case fails on a premise it never meant to test, so VAULT_DIR names it —
# defaulting to the same three-up path, the escape test_handsoff.sh's HOOKS_DIR is.
# Both cases also pass --credentials "$NOCRED", an absent fixture path: with VAULT_DIR at a real
# vault the guard's DEFAULT store would be that vault's real one, and no case here reads it.
VAULT_DIR=${VAULT_DIR:-$(cd "$SKILL/../../.." && pwd)}
ROOT="${TMPDIR:-/tmp}/pgtest.$$"
GIT="git -c user.email=t@t -c user.name=test -c commit.gpgsign=false -c init.defaultBranch=main"

# This suite SHIPS inside `.claude/skills/**`, so it sits inside the scope of the guard it
# tests — by design: the guard exempts no file. Every example home path is therefore
# assembled from parts at run time and never written as a literal, or this suite would halt
# the publish on itself.
U="/U""sers"; H="/h""ome"

PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "    ok   — $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL   — $1"; }

# run the guard on $1, capture output in $OUT and exit code in $RC. GUARD_EXTRA adds flags
# for one case; the empty-array form keeps it safe under `set -u` on bash 3.2.
GUARD_EXTRA=()
guard(){ OUT="$(env USER=fxaccount LOGNAME=fxaccount HOME="$FXH" \
                    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
                    python3 "$GUARD" --vault "$FXV" --allowlist "$FXA" \
                    ${GUARD_EXTRA[@]+"${GUARD_EXTRA[@]}"} "$1" 2>&1)"; RC=$?; }

# expect exit code $2 (and, when given, substring $3 in the output) from a run on $1
expect(){ local dir="$1" want="$2" needle="${3:-}" label="$4"
  guard "$dir"
  if [ "$RC" != "$want" ]; then no "$label (exit $RC, wanted $want): $(echo "$OUT" | head -2)"; return; fi
  if [ -n "$needle" ] && ! printf '%s' "$OUT" | grep -q -- "$needle"; then
    no "$label (exit ok, but output lacks '$needle'): $(echo "$OUT" | head -2)"; return; fi
  ok "$label"
}

# a minimal but shape-valid framework payload at $1
make_payload(){ local D="$1"
  mkdir -p "$D/.claude/skills/ingest" "$D/.claude/agents" "$D/assets" "$D/examples/seed/wiki" \
           "$D/wiki/sources" "$D/raw/2-papers" "$D/.obsidian"
  printf '# CLAUDE (test contract)\n' > "$D/CLAUDE.md"
  printf '# Manual (test)\n'          > "$D/MANUAL.md"
  printf '# ingest skill\n'           > "$D/.claude/skills/ingest/SKILL.md"
  printf '# critic\n'                 > "$D/.claude/agents/critic.md"
  printf '{ "colorGroups": [] }\n'    > "$D/.obsidian/graph.json"
  printf '# seed page\n'              > "$D/examples/seed/wiki/index.md"
  : > "$D/wiki/sources/.gitkeep"; : > "$D/raw/2-papers/.gitkeep"; : > "$D/assets/.gitkeep"
}

rm -rf "$ROOT"; mkdir -p "$ROOT"
# Probe 3 derives the owner's strings from a vault, so every case here runs against a FIXTURE
# vault and a fixture allowlist, with the account name, home and git config isolated too.
# Without that the suite would scan its throwaway payloads with the real machine's needles and
# pass or fail differently on every machine — and mutating the shipped allowlist to test a
# malformed one would leave a shipped file broken if a case ever aborted.
FXV="$ROOT/fxv"; FXH="$ROOT/fxhome"; FXA="$ROOT/fx-allowlist.md"
NOCRED="$ROOT/no-credential-store.env"   # never created: the absent store for the VAULT_DIR cases
mkdir -p "$FXV" "$FXH"
printf '# fixture contract\n' > "$FXV/CLAUDE.md"
printf 'marker\n\n## Settings\n- **agent_name**: Zephyrine — what the agent calls itself\n' > "$FXV/CUSTOMISATION.md"
$GIT -C "$FXV" init -q
$GIT -C "$FXV" config user.name "Quillsworth Vaneska"
$GIT -C "$FXV" config user.email "qz9917+ZephyrineQ@example.invalid"
$GIT -C "$FXV" config remote.origin.url "https://example.com/ZephyrineQ/fx.git"
cp "$SKILL/publish-allowlist.md" "$FXA"
# The same invocation as an array, for the two cases that must call the guard with a bad
# argument or none at all. An array, never a string: a flag and its value in one word is a
# wrapper defect.
GUARD_CMD=(env USER=fxaccount LOGNAME=fxaccount HOME="$FXH"
           GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
           python3 "$GUARD" --vault "$FXV" --allowlist "$FXA")


echo "── group 1: the clean payload passes, and says what it scanned ──"
P="$ROOT/clean"; make_payload "$P"
expect "$P" 0 "check: clean" "a clean payload passes"
expect "$P" 0 "control: 7/7 path probes, 3/3 class probes" "the clean line carries its self-control tally"
expect "$P" 0 "no git index" "a non-git payload says its file set came from disk"

echo "── group 2: probe 1 — machine paths ──"
P="$ROOT/p1a"; make_payload "$P"; printf 'OUT=%s/someone/vault/x\n' "$U" > "$P/.claude/skills/ingest/run.sh"
expect "$P" 1 "FINDING machine-path" "an absolute macOS home path in a shipped file halts"
P="$ROOT/p1b"; make_payload "$P"; printf 'HOME_DIR=%s/someone/notes\n' "$H" > "$P/MANUAL.md"
expect "$P" 1 "FINDING machine-path" "an absolute Linux home path halts too"
P="$ROOT/p1c"; make_payload "$P"
printf 'the fixture stamp is "$W%s/.llm-wiki/last-run.txt"\n' "$H" > "$P/.claude/skills/ingest/t.sh"
expect "$P" 0 "check: clean" "a fixture-relative \$W-prefixed home path does NOT halt (the live deep-lint case)"
P="$ROOT/p1d"; make_payload "$P"; printf 'the agent home is ~/.llm-wiki/ under $HOME\n' > "$P/README.md"
expect "$P" 0 "check: clean" "a tilde or \$HOME form does NOT halt"
P="$ROOT/p1e"; make_payload "$P"; printf 'see file://%s/someone/vault/CLAUDE.md\n' "$U" > "$P/README.md"
expect "$P" 1 "FINDING machine-path" "a file:// URL into a home directory halts"
P="$ROOT/p1f"; make_payload "$P"; printf 'see https://example.com%s/guide\n' "$U" > "$P/README.md"
expect "$P" 0 "check: clean" "a URL segment of the same spelling does NOT halt"
# CPython writes the source path behind a marshal LENGTH byte, so
# the character before the path is arbitrary data. A text-style lookbehind swallows it — which
# is why the machine-path rule follows the content class.
P="$ROOT/p1g"; make_payload "$P"
printf 'x\000o%s/someone/vault/repo_pack.py\000' "$U" > "$P/.claude/skills/ingest/repo_pack.pyc"
guard "$P"
if [ "$RC" = 1 ] && printf '%s' "$OUT" | grep -q "FINDING machine-path" \
   && printf '%s' "$OUT" | grep -q "FINDING non-text"; then
  ok "a path behind a marshal length byte halts on BOTH probes"
else no "a path behind a marshal length byte halts on both probes (exit $RC): $(echo "$OUT" | head -3)"; fi
P="$ROOT/p1h"; make_payload "$P"; printf 'the vendor path fragment is repo%s/guide\n' "$U" > "$P/MANUAL.md"
expect "$P" 0 "check: clean" "the SAME preceding byte in a TEXT file stays a fragment, not a halt"

echo "── group 3: probe 2 — non-text files ──"
P="$ROOT/p2a"; make_payload "$P"; printf 'ELF\000\000\000' > "$P/.claude/skills/ingest/helper.so"
expect "$P" 1 "FINDING non-text" "a non-text file under .claude/ halts (no filename list needed)"
P="$ROOT/p2b"; make_payload "$P"; printf 'junk\000\000' > "$P/examples/seed/wiki/thumb.ico"
expect "$P" 1 "FINDING non-text" "a non-text file under examples/ halts too — the scope is not .claude-only"
P="$ROOT/p2c"; make_payload "$P"
printf '\211PNG\r\n\032\n\000\000IHDR' > "$P/assets/framework_demo.png"
printf '\211PNG\r\n\032\n\000\000IHDR' > "$P/assets/hero.png"
expect "$P" 0 "check: clean" "the two intentional assets/*.png screenshots do NOT halt"
P="$ROOT/p2d"; make_payload "$P"; printf '\211PNG\r\n\032\n\000\000' > "$P/.claude/skills/ingest/hero.png"
expect "$P" 1 "FINDING non-text" "the SAME png halts once it sits under .claude/ (scope, not name)"
P="$ROOT/p2e"; make_payload "$P"
expect "$P" 0 "check: clean" "empty .gitkeep placeholders are text, not findings"
P="$ROOT/p2f"; make_payload "$P"
printf 'a page — with an em dash, a curly quote and an emoji 🧹\n' > "$P/.claude/skills/ingest/SKILL.md"
expect "$P" 0 "check: clean" "high UTF-8 bytes are text, not findings"
P="$ROOT/p2g"; make_payload "$P"
python3 -c 'open("'"$P"'/.claude/skills/ingest/big.md","wb").write(b"# doc\n"*3000 + b"\x00tail")'
expect "$P" 0 "check: clean" "a NUL past byte 8000 is text, matching git's own window"

echo "── group 4: premise failures exit 2, never clean ──"
expect "$ROOT/does-not-exist" 2 "PROBE FAILED" "a missing path is a broken premise"
mkdir -p "$ROOT/empty"
expect "$ROOT/empty" 2 "payload holds no files" "an EMPTY payload is a broken premise, not a clean scan"
mkdir -p "$ROOT/partial"; printf '# CLAUDE\n' > "$ROOT/partial/CLAUDE.md"
expect "$ROOT/partial" 2 "not a framework payload" "a payload with no skills is a broken premise"
mkdir -p "$ROOT/noclaude/.claude/skills/x"; printf '# s\n' > "$ROOT/noclaude/.claude/skills/x/SKILL.md"
expect "$ROOT/noclaude" 2 "not a framework payload" "a payload with no CLAUDE.md is a broken premise"
OUT="$("${GUARD_CMD[@]}" "$ROOT/clean/CLAUDE.md" 2>&1)"; RC=$?
if [ "$RC" = 2 ]; then ok "a file rather than a directory is a broken premise"
else no "a file rather than a directory is a broken premise (exit $RC)"; fi
OUT="$("${GUARD_CMD[@]}" 2>&1)"; RC=$?
if [ "$RC" = 2 ]; then ok "a missing argument is a broken premise"
else no "a missing argument is a broken premise (exit $RC)"; fi

echo "── group 5: with a git index, the INDEX is what ships ──"
R="$ROOT/repo"; make_payload "$R"
( cd "$R" && $GIT init -q . && printf '__pycache__/\n*.pyc\n.DS_Store\n' > .gitignore && $GIT add -A ) >/dev/null
expect "$R" 0 "from the index of" "a staged clean payload passes, read from the index"
printf 'OUT=%s/someone/leak\n' "$U" > "$R/.claude/skills/ingest/unstaged.sh"
expect "$R" 2 "stage the payload first" "an UNTRACKED file is refused: the gate would otherwise read the last publish"
( cd "$R" && $GIT add -A ) >/dev/null
expect "$R" 1 "FINDING machine-path" "the same file halts once staged"
( cd "$R" && $GIT rm -q --cached .claude/skills/ingest/unstaged.sh && rm -f .claude/skills/ingest/unstaged.sh ) >/dev/null
printf 'x\000%s/someone/vault/mod.py\000' "$U" > "$R/.claude/skills/ingest/mod.pyc"
expect "$R" 0 "check: clean" "a gitignored .pyc does not ship, so it does not halt"
( cd "$R" && $GIT add -f .claude/skills/ingest/mod.pyc ) >/dev/null
expect "$R" 1 "FINDING non-text" "the incident's real shape — a TRACKED .pyc that .gitignore no longer covers — halts"
( cd "$R" && $GIT rm -q --cached .claude/skills/ingest/mod.pyc && rm -f .claude/skills/ingest/mod.pyc ) >/dev/null
printf 'clean line\n' > "$R/.claude/skills/ingest/edited.sh"
( cd "$R" && $GIT add -A ) >/dev/null
printf 'OUT=%s/someone/after-staging\n' "$U" > "$R/.claude/skills/ingest/edited.sh"
expect "$R" 2 "stage them first" "an edit made AFTER staging is refused — the commit would write the index, not those bytes"
( cd "$R" && $GIT add -A ) >/dev/null
expect "$R" 1 "FINDING machine-path" "…and it halts as soon as it is staged"
( cd "$R" && $GIT rm -q --cached .claude/skills/ingest/edited.sh && rm -f .claude/skills/ingest/edited.sh ) >/dev/null

echo "── group 6: git's own classification cannot be gamed into a false halt ──"
printf '*.md -text -diff\n' > "$R/.gitattributes"
( cd "$R" && $GIT add -A ) >/dev/null
expect "$R" 0 "check: clean" "a .gitattributes '-text' line does NOT make Markdown files halt (shape B's failure mode)"
if ( cd "$R" && $GIT grep -I -e 'CLAUDE' --cached -- 'CLAUDE.md' ) >/dev/null 2>&1; then
  no "control: git itself still greps CLAUDE.md as text under '*.md -text' (the premise this case tests is absent)"
else ok "control: git itself now treats CLAUDE.md as binary — the guard's independence is what kept it clean"; fi
rm -f "$R/.gitattributes"; ( cd "$R" && $GIT add -A ) >/dev/null

echo "── group 7: shapes git can hide ──"
( cd "$R" && ln -sf "$U/someone/vault/CLAUDE.md" .claude/skills/ingest/link.md && $GIT add -A ) >/dev/null
expect "$R" 1 "FINDING machine-path" "a symlink into a home directory halts (its blob is the target path)"
( cd "$R" && $GIT rm -q --cached .claude/skills/ingest/link.md && rm -f .claude/skills/ingest/link.md ) >/dev/null
# Write the gitlink blob inside the fixture repository: git hash-object writes into its
# current repository. Keep stderr visible so a failure explains the premise leg's result.
gitlink_blob(){ ( cd "$R" && $GIT hash-object -w "$ROOT/clean/CLAUDE.md" ) || echo ""; }
SUB="$(gitlink_blob)"
if [ -n "$SUB" ]; then
  ( cd "$R" && $GIT update-index --add --cacheinfo "160000,$SUB,vendor/thing" ) >/dev/null 2>&1
  expect "$R" 1 "FINDING unscannable" "a gitlink (submodule) is REPORTED, never silently unscanned"
  ( cd "$R" && $GIT update-index --force-remove vendor/thing ) >/dev/null 2>&1
else no "could not build the gitlink fixture (premise for the submodule case)"; fi
expect "$R" 0 "check: clean" "the repo is clean again once the fixtures are removed"

echo "── group 7d: the gitlink premise does not depend on the caller's directory ──"
# The same build, run from a directory that is inside no repository: the caller's cwd must never
# decide whether group 7 can run at all.
OUTSIDE="$ROOT/outside"; mkdir -p "$OUTSIDE"
if ( cd "$OUTSIDE" && $GIT rev-parse --is-inside-work-tree ) >/dev/null 2>&1; then
  # Four legs either way, so the total does not move with the premise.
  no "premise: the fixture root is inside no repository (it is inside one — this group cannot test what it claims)"
  no "…so the outside-repo build could not run"
  no "…nor the submodule case from outside a repository"
  no "…nor its clean-again leg"
else
  ok "premise: the fixture root sits inside no repository, so a caller standing there has none"
  SUB="$( cd "$OUTSIDE" && gitlink_blob )"
  if [ -n "$SUB" ]; then
    ok "the gitlink blob is built from a directory inside no repository"
    ( cd "$R" && $GIT update-index --add --cacheinfo "160000,$SUB,vendor/thing" ) >/dev/null 2>&1
    expect "$R" 1 "FINDING unscannable" "…and the submodule case reaches its finding from there too"
    ( cd "$R" && $GIT update-index --force-remove vendor/thing ) >/dev/null 2>&1
    expect "$R" 0 "check: clean" "…and the repo is clean again once that fixture is removed"
  else
    no "the gitlink blob is built from a directory inside no repository (the premise this group tests)"
    no "…so the submodule case from outside a repository could not run"
    no "…nor its clean-again leg"
  fi
fi

# Findings folded from an earlier critic review.
echo "── group 7c: the folded critic findings ──"
P="$ROOT/c1"; make_payload "$P"; printf 'OUT = "D:\\Users\\someone\\vault"\n' > "$P/MANUAL.md"
expect "$P" 1 "FINDING machine-path" "a WINDOWS home path halts too — three roots, not the two this machine uses"
P="$ROOT/c2"; make_payload "$P"; mkdir -p "$P/.claude/skills/ingest/assets"
printf 'ELF\000\000' > "$P/.claude/skills/ingest/assets/evil.so"
expect "$P" 1 "FINDING non-text" "a NESTED assets/ directory does NOT inherit the media exemption"
P="$ROOT/c3"; make_payload "$P"; printf -- '---\nrole: generalist\n---\n' > "$P/CUSTOMISATION.md"
expect "$P" 2 "this is a vault" "the VAULT root is refused: it passes the shape key but is not a payload"
S="$ROOT/c4"; make_payload "$S"; ( cd "$S" && $GIT init -q . ) >/dev/null
expect "$S" 2 "stage the payload first" "an unstaged payload is a broken premise, not a clean scan of the last publish"
( cd "$S" && $GIT add -A ) >/dev/null
expect "$S" 0 "check: clean" "…and it passes once staged"
printf '# edited after staging\n' > "$S/MANUAL.md"
expect "$S" 2 "stage them first" "a tracked file edited after staging is a broken premise"
( cd "$S" && $GIT add -A ) >/dev/null
expect "$S" 0 "check: clean" "…and it passes once restaged"

echo "── group 7b: the file set comes from the right place ──"
# The DEFAULT build directory sits inside the vault's own repo. Keyed on `rev-parse
# --is-inside-work-tree` the guard would ask the OUTER repo for its index and find the build
# untracked, i.e. call a real payload empty. Keyed on a .git entry at the root, it scans the tree.
B="$R/inner-build"; make_payload "$B"
expect "$B" 0 "no git index" "a build directory INSIDE a repo is scanned as a tree, not via the outer index"
PY3="$(command -v python3)"
if [ -n "$PY3" ]; then
  OUT="$(env PATH="" "$PY3" "$GUARD" --vault "$VAULT_DIR" --credentials "$NOCRED" "$R" 2>&1)"; RC=$?
  if [ "$RC" = 2 ] && printf '%s' "$OUT" | grep -q "PROBE FAILED"; then
    ok "a repo whose git cannot run is a broken premise, never a silent disk fallback"
  else no "a repo whose git cannot run is a broken premise (exit $RC): $(echo "$OUT" | head -2)"; fi
  # A payload far larger than a pipe buffer must not deadlock: the sha list is written in
  # chunks and each chunk's blobs are drained before the next is sent.
  BIG="$ROOT/big"; make_payload "$BIG"
  "$PY3" -c 'import sys,os
d = sys.argv[1] + "/.claude/skills/ingest/many"
os.makedirs(d, exist_ok=True)
for i in range(1500): open("%s/f%04d.md" % (d, i), "w").write("# page %d\n" % i)' "$BIG"
  ( cd "$BIG" && $GIT init -q . && $GIT add -A ) >/dev/null 2>&1
  OUT="$("$PY3" -c 'import subprocess,sys
try:
    p = subprocess.run([sys.executable] + sys.argv[1:], timeout=90,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    sys.stdout.write(p.stdout.decode()); sys.exit(p.returncode)
except subprocess.TimeoutExpired:
    print("TIMED OUT"); sys.exit(9)' "$GUARD" "$BIG" --vault "$VAULT_DIR" --credentials "$NOCRED" 2>&1)"; RC=$?
  if [ "$RC" = 0 ] && printf '%s' "$OUT" | grep -q "check: clean"; then
    ok "a 1500-file staged payload scans without deadlocking on cat-file's pipes"
  else no "a 1500-file staged payload scans without deadlocking (exit $RC): $(echo "$OUT" | head -2)"; fi
else no "could not locate python3 for the PATH and scale cases"; fi

echo "── group 9: probe 3 — personal strings ──"
ALL_DEFAULT="$FXA"
# One fixture adjudication set: a permanent entry scoped to one file, a provisional entry
# with a per-file occurrence cap and an expiry.
cat > "$ROOT/al9.md" <<'AL9'
# fixture allowlist
- <licence holder's legal name> :: `LICENSE.md` — the fixture copyright line :: fixture
- <agent name> :: PROVISIONAL, expires at v1.0 — `.claude/skills/ingest/SKILL.md` (2) :: fixture
AL9
FXA="$ROOT/al9.md"
P="$ROOT/p3a"; make_payload "$P"; printf 'contact Vaneska for access\n' > "$P/MANUAL.md"
expect "$P" 1 "FINDING personal-str" "a derived personal string in a file's content halts"
P="$ROOT/p3a2"; make_payload "$P"; printf 'run as fxaccount on the build host\n' > "$P/MANUAL.md"
expect "$P" 1 "no allowlist entry" "a string no entry mentions at all says exactly that"
P="$ROOT/p3b"; make_payload "$P"; printf 'x\n' > "$P/notes-by-vaneska.md"
expect "$P" 1 "hit(s) in name" "a personal string in a file NAME halts, with the branch named"
P="$ROOT/p3c"; make_payload "$P"
printf '\211PNG\r\n\032\n\000\000 Vaneska \000' > "$P/assets/hero.png"
expect "$P" 1 "FINDING personal-str  assets/hero.png" "a personal string in BINARY bytes halts, media directory or not"
P="$ROOT/p3d"; make_payload "$P"; printf 'contact VANESKA and vaneska\n' > "$P/MANUAL.md"
expect "$P" 1 "2 hit(s)" "matching is case-insensitive, and occurrences are counted"
P="$ROOT/p3e"; make_payload "$P"; printf 'no owner strings here at all\n' > "$P/MANUAL.md"
expect "$P" 0 "check: clean" "a payload with no personal string passes"
P="$ROOT/p3f"; make_payload "$P"; printf 'Copyright (c) Quillsworth Vaneska\n' > "$P/LICENSE.md"
expect "$P" 0 "check: clean" "an allowlisted string passes IN the file its entry names"
P="$ROOT/p3g"; make_payload "$P"; printf 'Copyright (c) Quillsworth Vaneska\n' > "$P/MANUAL.md"
expect "$P" 1 "but not in this file" "the SAME string halts in a file the entry does not name"
P="$ROOT/p3h"; make_payload "$P"; printf 'Zephyrine and Zephyrine\n' > "$P/.claude/skills/ingest/SKILL.md"
expect "$P" 0 "check: clean" "a provisional entry passes AT its per-file count"
P="$ROOT/p3i"; make_payload "$P"; printf 'Zephyrine and Zephyrine and Zephyrine\n' > "$P/.claude/skills/ingest/SKILL.md"
expect "$P" 1 "over the cap of 2" "one occurrence over the count halts, naming the cap"
P="$ROOT/p3j"; make_payload "$P"
GUARD_EXTRA=(--release v0.9.9); expect "$P" 0 "check: clean" "a release below a provisional expiry passes"
GUARD_EXTRA=(--release v1.0); expect "$P" 1 "FINDING allowlist-exp" "the release that reaches the expiry halts"
GUARD_EXTRA=(--release v1); expect "$P" 1 "FINDING allowlist-exp" "v1 and v1.0 compare equal, so the grammar cannot be dodged"
GUARD_EXTRA=(--release 2.0.0); expect "$P" 1 "FINDING allowlist-exp" "a later release still halts, with or without the v"
GUARD_EXTRA=(--release nonsense); expect "$P" 2 "does not parse as a version" "an unparseable release is a broken premise"
GUARD_EXTRA=()
expect "$P" 0 "provisional: <agent name> expires at v1.0" "every run reports the pending expiry for the recap"
expect "$P" 0 "corpus control" "the clean line carries the corpus control's hit count"
expect "$P" 0 "string probes" "and the string-probe tally beside the other two"
# The floor, and the owner-local extras file that is exempt from it.
P="$ROOT/p3k"; make_payload "$P"; printf 'the fxv directory and the fxvault\n' > "$P/MANUAL.md"
expect "$P" 0 "check: clean" "a path component below the byte floor is not a needle"
mkdir -p "$FXV/output"; printf '# extras\n\nfxv\n' > "$FXV/output/publish-gate-strings.txt"
expect "$P" 1 "from extra" "a line in the gate-strings file IS a needle, floor or not"
expect "$P" 1 "extra strings: 1 line" "and the run says how many extra lines it read"
rm "$FXV/output/publish-gate-strings.txt"; rmdir "$FXV/output"
expect "$P" 0 "extra strings: none" "with the file gone the run says so, rather than staying silent"
# Inspection, and the negative control for the whole probe.
guard "$P"
if printf '%s' "$OUT" | grep -q "inert:"; then ok "an entry that matched no needle is reported inert"
else no "an entry that matched no needle is reported inert: $(echo "$OUT" | tail -1)"; fi
GUARD_EXTRA=(--print-needles); guard "$P"; GUARD_EXTRA=()
if printf '%s' "$OUT" | grep -q "^needle  Zephyrine .*agent-name"; then ok "--print-needles shows each needle with the class it came from"
else no "--print-needles shows each needle with its class"; fi
if printf '%s' "$OUT" | grep -q "^needle  .*fxaccount"; then ok "the machine account name is derived even though it is not in the vault path"
else no "the machine account name is derived"; fi
if printf '%s' "$OUT" | grep -q "^check: clean" && ! printf '%s' "$OUT" | grep -q "Zephyrine\b.*FINDING"; then
  ok "control: a needle list this long still reports clean on a payload that carries none"
else no "control: a clean payload with many needles"; fi

echo "── group 10: the allowlist is parsed, and every malformed shape exits 2 ──"
printf '# fixture allowlist\n\n- <mystery class> :: `README.md` :: planted\n' > "$ROOT/al10a.md"
FXA="$ROOT/al10a.md"; expect "$P" 2 "unknown placeholder" "an unknown placeholder is a broken premise"
printf '# fixture allowlist\n\n- SomeString :: nowhere in particular :: planted\n' > "$ROOT/al10b.md"
FXA="$ROOT/al10b.md"; expect "$P" 2 "names no file" "an entry naming no file is a broken premise"
printf '# fixture allowlist\n\n- SomeString :: `README.md` (3) :: planted\n' > "$ROOT/al10c.md"
FXA="$ROOT/al10c.md"; expect "$P" 2 "must not carry a per-file count" "a count on a permanent entry is a broken premise"
printf '# fixture allowlist\n\n- S :: PROVISIONAL, expires at v1.0 — `README.md` :: planted\n' > "$ROOT/al10d.md"
FXA="$ROOT/al10d.md"; expect "$P" 2 "needs a per-file count" "a provisional path with no count is a broken premise"
printf '# fixture allowlist\n\n- <agent name> :: PROVISIONAL, expires at v1.0 — `SKILL.md` (1), `ingest/SKILL.md` (3) :: planted\n' > "$ROOT/al10e.md"
P="$ROOT/p3l"; make_payload "$P"; printf 'Zephyrine Zephyrine\n' > "$P/.claude/skills/ingest/SKILL.md"
FXA="$ROOT/al10e.md"
expect "$P" 0 "check: clean" "where two entry paths both cover a file, the LONGEST binds (its cap, not the short one's)"
P="$ROOT/p3k"
printf '# nothing parseable\n' > "$ROOT/al10f.md"
FXA="$ROOT/al10f.md"; expect "$P" 2 "parsed to 0 entries" "an allowlist that parses to nothing is a broken premise"
FXA="$ROOT/al10g.md"; expect "$P" 2 "is missing" "a missing allowlist is a broken premise, not an empty one"
FXA="$ALL_DEFAULT"
# The shipped pair must parse: the fixture must not be hiding a defect in the real files.
OUT="$(env USER=fxaccount LOGNAME=fxaccount HOME="$FXH" GIT_CONFIG_GLOBAL=/dev/null \
        GIT_CONFIG_SYSTEM=/dev/null python3 "$GUARD" --vault "$FXV" --print-needles \
        "$ROOT/p3e" 2>&1)"; RC=$?
if [ "$RC" = 0 ]; then ok "control: the SHIPPED allowlist parses and adjudicates a real run"
else no "control: the shipped allowlist parses (exit $RC): $(echo "$OUT" | head -2)"; fi
printf '# fixture contract\n' > "$ROOT/novault/CLAUDE.md" 2>/dev/null || mkdir -p "$ROOT/novault"
printf '# fixture contract\n' > "$ROOT/novault/CLAUDE.md"
FXV_SAVE="$FXV"; FXV="$ROOT/novault"
expect "$P" 2 "cannot derive the owner's strings" "a vault with no preference layer is a broken premise, never a skipped probe"
mkdir -p "$ROOT/noname"; printf '# c\n' > "$ROOT/noname/CLAUDE.md"; printf 'marker\n\n## Settings\n- **style**: brief\n' > "$ROOT/noname/CUSTOMISATION.md"
FXV="$ROOT/noname"; expect "$P" 2 "no \`agent_name\` line" "a preference layer that lost its agent_name line is a broken premise"
mkdir -p "$ROOT/blankname"; printf '# c\n' > "$ROOT/blankname/CLAUDE.md"; printf 'marker\n\n## Settings\n- **agent_name**:  — blank means none\n' > "$ROOT/blankname/CUSTOMISATION.md"
FXV="$ROOT/blankname"; expect "$P" 0 "check: clean" "a BLANK agent_name is legitimate (setup.sh seeds it blank) and yields no needle"
FXV="$FXV_SAVE"

echo "── group 11: probe 4 — credential values ──"
# The store is FAKE and made here, its value carrying a fresh random part, so no fixed string in
# this file can stand in for it. Every leg below runs expect_withheld: the run's WHOLE output —
# stdout and stderr, on every exit path — must carry neither the value nor its random part.
NONCE="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
FAKEVAL="FAKE-SECRET-$NONCE"
FAKE="$ROOT/fake-credentials.env"
printf '# FAKE store for this suite, not a secret\nFIXTURE_TEST_TOKEN=%s\n' "$FAKEVAL" > "$FAKE"
leaks(){ printf '%s' "$OUT" | grep -q -F -e "$FAKEVAL" -e "$NONCE"; }
expect_withheld(){ local dir="$1" want="$2" needle="${3:-}" label="$4"
  guard "$dir"
  if leaks; then no "$label — the output CARRIES the fake value"; return; fi
  if [ "$RC" != "$want" ]; then no "$label (exit $RC, wanted $want): $(echo "$OUT" | head -2)"; return; fi
  if [ -n "$needle" ] && ! printf '%s' "$OUT" | grep -q -- "$needle"; then
    no "$label (exit ok, but output lacks '$needle'): $(echo "$OUT" | head -2)"; return; fi
  ok "$label"
}
if printf '%s' "$NONCE" | grep -q -E '^[0-9a-f]{32}$'; then ok "premise: the fake value carries a fresh 32-hex random part"
else no "premise: the fake value carries a fresh random part (got ${#NONCE} characters)"; fi
P1="$ROOT/k1"; make_payload "$P1"; printf 'a pasted token: %s\n' "$FAKEVAL" > "$P1/MANUAL.md"
P2="$ROOT/k2"; make_payload "$P2"
GUARD_EXTRA=(--credentials "$FAKE")
expect_withheld "$P1" 1 "FINDING credential    MANUAL.md  1 hit(s) in content" "a payload carrying a credential value halts, naming the file"
expect_withheld "$P1" 1 "the value of FIXTURE_TEST_TOKEN" "…and naming the KEY, never the value"
expect_withheld "$P1" 1 "1 credential value(s) in 1 file(s)" "…and the gate line counts it"
expect_withheld "$P2" 0 "check: clean" "a payload clean of every value passes"
expect_withheld "$P2" 0 "credentials: 1 value(s) checked from NON-DEFAULT (fake-credentials.env)" "…and its line names the store by file name and counts the value checked (the clean result's control)"
expect_withheld "$P2" 0 "5/5 credential probes" "the clean line carries probe 4's self-control tally"
GUARD_EXTRA=(--credentials "$ROOT/absent-store.env")
expect_withheld "$P1" 0 "no credential file at NON-DEFAULT (absent-store.env)" "an ABSENT store checks nothing, says so, and never fails the gate"
GUARD_EXTRA=()
mkdir -p "$FXV/output/user-notes"; cp "$FAKE" "$FXV/output/user-notes/credentials.env"
expect_withheld "$P1" 1 "FINDING credential .*FIXTURE_TEST_TOKEN" "with no flag the store is the vault's output/user-notes/credentials.env"
expect_withheld "$P2" 0 "1 value(s) checked from output/user-notes/credentials.env" "…named by its vault-relative path, never an absolute one"
rm -rf "$FXV/output"
expect_withheld "$P2" 0 "no credential file at output/user-notes/credentials.env" "with the default store gone, the run says so"
GUARD_EXTRA=(--credentials "$FAKE")
P="$ROOT/k3"; make_payload "$P"; printf 'x\n' > "$P/notes-$FAKEVAL.md"
expect_withheld "$P" 1 "hit(s) in name" "a value in a file NAME halts"
expect_withheld "$P" 1 "notes-\[value of FIXTURE_TEST_TOKEN withheld\]\.md" "…and the path is printed with the value replaced by its KEY's label"
P="$ROOT/k4"; make_payload "$P"; printf '\211PNG\r\n\032\n\000\000 %s \000' "$FAKEVAL" > "$P/assets/hero.png"
expect_withheld "$P" 1 "FINDING credential    assets/hero.png" "a value in BINARY bytes halts, media directory included"
P="$ROOT/k5"; make_payload "$P"; printf 'a case-changed copy: %s\n' "$(printf '%s' "$FAKEVAL" | tr 'A-Z' 'a-z')" > "$P/MANUAL.md"
expect_withheld "$P" 0 "check: clean" "matching is literal bytes: a case-changed copy is not the value"
# The line shapes a store can hold: export, double and single quotes, an inline comment, CRLF;
# a value under the floor and an empty one are counted, not scanned.
printf '# fixture store\nexport FIXTURE_EXPORTED="%s-exp"\nFIXTURE_COMMENTED=%s-com # an inline note\nFIXTURE_SINGLE='"'"'%s-sgl'"'"'\nFIXTURE_CRLF=%s-crlf\r\nFIXTURE_SHORT=ab12\nFIXTURE_EMPTY=\n' \
  "$FAKEVAL" "$FAKEVAL" "$FAKEVAL" "$FAKEVAL" > "$ROOT/k6.env"
P="$ROOT/k6"; make_payload "$P"
printf 'exp %s-exp\ncom %s-com\nsgl %s-sgl\ncrlf %s-crlf\nshort ab12\n' "$FAKEVAL" "$FAKEVAL" "$FAKEVAL" "$FAKEVAL" > "$P/MANUAL.md"
GUARD_EXTRA=(--credentials "$ROOT/k6.env")
expect_withheld "$P" 1 "4 credential value(s) in 1 file(s)" "export, both quote styles, an inline comment and CRLF all parse to their bare value"
expect_withheld "$P" 1 "4 value(s) checked from NON-DEFAULT (k6.env) (6 key(s)), 1 below the 6-byte floor, 1 empty" "a value under the floor and an empty one are counted on the line, never silently dropped"
printf 'FIXTURE_OK=%s\nthis line carries %s but no pair\n' "$FAKEVAL" "$FAKEVAL" > "$ROOT/k7.env"
GUARD_EXTRA=(--credentials "$ROOT/k7.env")
expect_withheld "$P2" 2 "line 2 of the credential store is not a KEY=value line" "a line that is not KEY=value is a broken premise named by number, its content never shown"
printf 'FIXTURE_Q="%s\n' "$FAKEVAL" > "$ROOT/k8.env"
GUARD_EXTRA=(--credentials "$ROOT/k8.env")
expect_withheld "$P2" 2 "opens a quote it never closes" "an unclosed quote is a broken premise, its content never shown"
mkdir -p "$ROOT/k9.env"
GUARD_EXTRA=(--credentials "$ROOT/k9.env")
expect_withheld "$P2" 2 "exists but cannot be read" "a store that exists but cannot be read is a broken premise, never a silent skip"
ln -s "$ROOT/nowhere.env" "$ROOT/k10.env"
GUARD_EXTRA=(--credentials "$ROOT/k10.env")
expect_withheld "$P1" 0 "a link whose target is missing" "a link to a missing store is absent: said so, and never a failure"
# Lines that are not findings carry a value too, if a path does: the scanned root, a premise.
GUARD_EXTRA=(--credentials "$FAKE")
P="$ROOT/clone-$FAKEVAL"; make_payload "$P"
expect_withheld "$P" 0 "value of FIXTURE_TEST_TOKEN withheld" "the clean line withholds a value even in the scanned root's own path"
S="$ROOT/repo-$FAKEVAL"; make_payload "$S"; ( cd "$S" && $GIT init -q . ) >/dev/null
expect_withheld "$S" 2 "stage the payload first" "a PROBE FAILED message withholds it too (the root path in an unstaged-tree refusal)"
( cd "$S" && $GIT add -A ) >/dev/null; printf 'token %s\n' "$FAKEVAL" > "$S/MANUAL.md"; ( cd "$S" && $GIT add -A ) >/dev/null
expect_withheld "$S" 1 "FINDING credential    MANUAL.md" "with a git index, a STAGED value halts — the index is what ships"
# A probe-3 needle equal to a value: --print-needles and probe 3's own finding both print needles.
mkdir -p "$FXV/output"; printf '%s\n' "$FAKEVAL" > "$FXV/output/publish-gate-strings.txt"
GUARD_EXTRA=(--credentials "$FAKE" --print-needles)
expect_withheld "$P1" 1 "^needle  \[value of FIXTURE_TEST_TOKEN withheld\]" "diagnostic output (--print-needles) withholds a needle that equals a value"
expect_withheld "$P1" 1 "FINDING personal-str  MANUAL.md .*\[value of FIXTURE_TEST_TOKEN withheld\]" "…and so does probe 3's finding line, which prints its needle"
rm -rf "$FXV/output"
GUARD_EXTRA=()
# A crash: its message quotes a value, and its traceback leaves through the same output path.
OUT="$(env PYTHONDONTWRITEBYTECODE=1 python3 -B -c '
import sys
sys.path.insert(0, sys.argv[1])
import publish_guard as g
def boom(argv):
    g.OUT.arm({sys.argv[2].encode(): ["FIXTURE_TEST_TOKEN"]})
    raise ValueError("a crash whose message quotes " + sys.argv[2])
g.main = boom
sys.exit(g.run(["publish_guard.py"]))' "$SKILL" "$FAKEVAL" 2>&1)"; RC=$?
if [ "$RC" = 2 ] && ! leaks && printf '%s' "$OUT" | grep -q "PROBE FAILED: the guard crashed (ValueError)" \
   && printf '%s' "$OUT" | grep -q "quotes \[value of FIXTURE_TEST_TOKEN withheld\]"; then
  ok "a crash exits 2, never 1, and its traceback withholds the value its message quoted"
else no "a crash exits 2 and withholds the value (exit $RC, leaked: $(leaks && echo yes || echo no))"; fi
# Source shape: one output path. A bare print or a stderr write would bypass the scrub.
if [ "$(grep -c 'print(' "$GUARD")" = 0 ] && [ "$(grep -c 'sys.stderr' "$GUARD")" = 0 ] \
   && [ "$(printf 'x = 1\nprint("y")\nsys.stderr.write("z")\n' | grep -c -e 'print(' -e 'sys.stderr')" = 2 ]; then
  ok "the guard has no print( and no stderr write: every line leaves through OUT (control: the same grep finds both in a planted snippet)"
else no "the guard has $(grep -c 'print(' "$GUARD") print( and $(grep -c 'sys.stderr' "$GUARD") stderr line(s) outside OUT"; fi
# No leg of this suite can reach a real store: every call naming the caller's vault names a store.
VD_PAT='--vault "$VAULT''_DIR"'
N_VD="$(grep -c -F -- "$VD_PAT" "${BASH_SOURCE[0]}")"
N_VD_BARE="$(grep -F -- "$VD_PAT" "${BASH_SOURCE[0]}" | grep -c -v -F -- '--credentials')"
if [ "$N_VD" -ge 2 ] && [ "$N_VD_BARE" = 0 ]; then
  ok "every call that names the caller's vault also names a fixture store ($N_VD calls found — the control)"
else no "a call names the caller's vault without --credentials ($N_VD_BARE of $N_VD), so it could read a real store"; fi
# The guard stores nothing: a content manifest of a READ-ONLY payload copy, the fixture vault, the
# store and this skill directory is identical before and after a run that finds a value.
RO="$ROOT/k-readonly"; cp -R "$P1" "$RO"; chmod -R a-w "$RO" "$FAKE"
manifest(){ python3 -c 'import hashlib,os,sys
for top in sys.argv[1:]:
    tops = [top] if os.path.isfile(top) else sorted(os.path.join(b, f) for b, _d, fs in os.walk(top) for f in fs)
    for p in tops:
        print(hashlib.sha256(open(p, "rb").read()).hexdigest(), p)' "$RO" "$FXV" "$FAKE" "$SKILL"; }
BEFORE="$(manifest)"; GUARD_EXTRA=(--credentials "$FAKE"); guard "$RO"; GUARD_EXTRA=(); AFTER="$(manifest)"
chmod -R u+w "$RO" "$FAKE"
if [ "$RC" = 1 ] && [ -n "$BEFORE" ] && [ "$BEFORE" = "$AFTER" ] && ! leaks; then
  ok "a run that finds a value writes nothing: $(printf '%s\n' "$BEFORE" | wc -l | tr -d ' ') files hash the same before and after, on a read-only copy"
else no "the guard wrote or changed a file, or did not find the value (exit $RC)"; fi
WRITE_RE='open\([^)]*["'"'"'][rb]*[wax+]|os\.(remove|unlink|rename|replace|makedirs|mkdir|rmdir|truncate)|shutil\.|\.write_(text|bytes)'
if [ "$(grep -c -E "$WRITE_RE" "$GUARD")" = 0 ] \
   && [ "$(printf 'open(p, "w")\nopen(q, "ab")\nos.remove(p)\nshutil.copy(a, b)\n' | grep -c -E "$WRITE_RE")" = 4 ]; then
  ok "the guard's source holds no file-write call (control: the same pattern finds all 4 planted ones)"
else no "the guard's source holds $(grep -c -E "$WRITE_RE" "$GUARD") file-write call(s), or the pattern lost its control"; fi

echo "── group 12: escaped copies, an unstattable store, early messages, store readings ──"
# More FAKE values, each carrying this run's random part. The leak check below looks for each
# value raw, backslashes doubled and inside Python's repr (as bytes and as text, the forms an
# OSError and a %r print), and for the random part, which every escaped form carries verbatim.
BSVAL='Bk\sl-'"$NONCE"                                   # a value holding a backslash
printf "FIXTURE_BACKSLASH='%s'\n" "$BSVAL" > "$ROOT/k12.env"
LEAK_FORMS=()
while IFS= read -r f; do LEAK_FORMS+=("$f"); done < <(python3 -c '
import sys
for arg in sys.argv[1:]:
    v = arg.encode("utf-8", "surrogateescape")
    t = v.decode("utf-8", "surrogateescape")
    for f in sorted({v, v.replace(b"\\", b"\\\\"), repr(v)[2:-1].encode("ascii"),
                     repr(t)[1:-1].encode("utf-8", "surrogateescape")}):
        sys.stdout.buffer.write(f + b"\n")' "$FAKEVAL" "$BSVAL")
leaks12(){ local f
  for f in ${LEAK_FORMS[@]+"${LEAK_FORMS[@]}"} "$NONCE"; do
    if printf '%s' "$OUT" | grep -q -F -e "$f"; then return 0; fi
  done
  return 1; }
# Run the guard with exactly the arguments given (GUARD_ENV adds environment), then: no fake
# value in any form, the exit code, and the expected text.
GUARD_ENV=()
expect12(){ local want="$1" needle="$2" label="$3"; shift 3
  OUT="$(env ${GUARD_ENV[@]+"${GUARD_ENV[@]}"} USER=fxaccount LOGNAME=fxaccount HOME="$FXH" \
             GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null python3 "$GUARD" "$@" 2>&1)"; RC=$?
  if leaks12; then no "$label — the output CARRIES a fake value, raw or escaped"; return; fi
  if [ "$RC" != "$want" ]; then no "$label (exit $RC, wanted $want): $(echo "$OUT" | head -2)"; return; fi
  if [ -n "$needle" ] && ! printf '%s' "$OUT" | grep -q -- "$needle"; then
    no "$label (exit ok, but output lacks '$needle'): $(echo "$OUT" | head -2)"; return; fi
  ok "$label"
}
# Identical forms collapse: the plain fake value has 1, the backslash value 2 (raw, and doubled,
# which is also what both reprs give it), so 3 in all.
if [ "${#LEAK_FORMS[@]}" -ge 3 ] && printf '%s\n' "${LEAK_FORMS[@]}" | grep -q -x -F -e "$BSVAL" \
   && printf '%s\n' "${LEAK_FORMS[@]}" | grep -q -F -e 'Bk\\sl-'; then
  ok "premise: the leak check holds ${#LEAK_FORMS[@]} forms of the fake values, the backslash value raw and doubled"
else no "premise: the leak check holds the escaped forms of the fake values (${#LEAK_FORMS[@]} found)"; fi
P2="$ROOT/k2"
# Several legs lock a file or directory with mode 000, which binds every user but root. Checked
# once: where it does not bind, each such leg reports its premise as failed, so the count holds.
: > "$ROOT/k12-lockprobe"; chmod 000 "$ROOT/k12-lockprobe"
if [ -r "$ROOT/k12-lockprobe" ]; then CAN_LOCK=no; else CAN_LOCK=yes; fi
chmod 600 "$ROOT/k12-lockprobe"
locked(){ [ "$CAN_LOCK" = yes ] && return 0
  no "premise: mode 000 does not bind this user (root?), so this leg cannot run: $1"; return 1; }
# An escaped copy of a value is withheld like the raw one, and an OS error gives its reason alone.
P="$ROOT/k12a"; make_payload "$P"; printf 'x\n' > "$P/n-$BSVAL.md"; chmod 000 "$P/n-$BSVAL.md"
L="an unreadable file whose NAME holds a value with a backslash: path withheld raw and escaped, the OS reason alone"
locked "$L" && expect12 2 "cannot read .*/n-\[value of FIXTURE_BACKSLASH withheld\]\.md (Permission denied)$" "$L" \
  --vault "$FXV" --allowlist "$FXA" --credentials "$ROOT/k12.env" "$P"
chmod 600 "$P/n-$BSVAL.md"
# Every escaped form a REAL producer gives two values — an OSError's text, a %r of bytes and of
# text, git's quoting with core.quotePath on and off — leaves the output path withheld.
RICH="$(printf 'Rk\\sl"q'"'"'-\t-%s-\303\251' "$NONCE")"   # a backslash, both quotes, a tab, an e-acute
SQV="$(printf 'Sq\\it'"'"'s-%s' "$NONCE")"                 # a single quote and no double: repr picks "
OUT="$(env PYTHONDONTWRITEBYTECODE=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null python3 -B -c '
import os, shutil, subprocess, sys, tempfile
sys.path.insert(0, sys.argv[1])
import publish_guard as g
vals = [a.encode("utf-8", "surrogateescape") for a in sys.argv[2:4]]
g.OUT.arm({vals[0]: ["FIXTURE_RICH"], vals[1]: ["FIXTURE_SQ"]})
lines = []
for v in vals:
    t = v.decode("utf-8", "surrogateescape")
    lines.append(str(PermissionError(13, "Permission denied", "dir/n-" + t + ".md")))
    lines.append("%r" % (b"dir/n-" + v + b".md",))
    lines.append("%r" % ("dir/n-" + t + ".md",))
    d = tempfile.mkdtemp(dir=sys.argv[4])
    subprocess.run(["git", "-C", d, "init", "-q"], check=True)
    open(os.path.join(d.encode(), b"n-" + v + b".md"), "wb").close()
    for qp in ("true", "false"):
        lines.append(subprocess.run(["git", "-c", "core.quotePath=" + qp, "-C", d, "ls-files",
                                     "--others"], stdout=subprocess.PIPE, check=True)
                     .stdout.decode("utf-8", "surrogateescape").strip())
    shutil.rmtree(d)
for ln in lines:
    g.OUT.emit(ln)' "$SKILL" "$RICH" "$SQV" "$ROOT" 2>&1)"; RC=$?
N_LABELLED="$(printf '%s\n' "$OUT" | grep -c -E 'value of FIXTURE_(RICH|SQ) withheld')"
if [ "$RC" = 0 ] && ! leaks12 && [ "$N_LABELLED" = 10 ]; then
  ok "every escaped form an OSError, a %r and git's quoting give a value is withheld, under its KEY (10 of 10 lines)"
else no "escaped forms from real producers are withheld (exit $RC, leaked: $(leaks12 && echo yes || echo no), labelled $N_LABELLED of 10)"; fi
# A crash on an OSError: its traceback line keeps the reason and loses the escaped path.
OUT="$(env PYTHONDONTWRITEBYTECODE=1 python3 -B -c '
import sys
sys.path.insert(0, sys.argv[1])
import publish_guard as g
def boom(argv):
    g.OUT.arm({sys.argv[2].encode("utf-8", "surrogateescape"): ["FIXTURE_BACKSLASH"]})
    open(sys.argv[3] + "/n-" + sys.argv[2] + ".md", "rb")
g.main = boom
sys.exit(g.run(["publish_guard.py"]))' "$SKILL" "$BSVAL" "$ROOT/k12-nowhere" 2>&1)"; RC=$?
if [ "$RC" = 2 ] && ! leaks12 \
   && printf '%s' "$OUT" | grep -q '^FileNotFoundError: \[Errno 2\] No such file or directory$' \
   && printf '%s' "$OUT" | grep -q "PROBE FAILED: the guard crashed (FileNotFoundError)"; then
  ok "a crash on an OSError prints its traceback with the reason alone: no escaped path reaches the output"
else no "a crash on an OSError withholds the escaped path (exit $RC, leaked: $(leaks12 && echo yes || echo no))"; fi
# git's own words. A stub git answers what the guard asks and replays text REAL git produced:
# git's C-style quoting of a name holding the value, on stderr; then an unparseable index record.
STUB="$ROOT/stub-git"; mkdir -p "$STUB"
cat > "$STUB/git" <<'STUBGIT'
#!/bin/sh
# A stub git: it answers the guard's calls and fails the one under test with $STUB_TEXT.
case " $* " in
  *" config "*) exit 1 ;;
  *" rev-parse "*) echo .git; exit 0 ;;
  *" --others "*)
    if [ "$STUB_MODE" = stderr ]; then
      printf 'fatal: cannot stat %s: Permission denied\n' "$STUB_TEXT" >&2; exit 128
    fi
    exit 0 ;;
  *" diff "*) exit 0 ;;
  *" ls-files "*) printf '%s\000' "$STUB_TEXT"; exit 0 ;;
esac
exit 3
STUBGIT
chmod +x "$STUB/git"
GQ="$ROOT/k12-gitquote"; mkdir -p "$GQ"; ( cd "$GQ" && $GIT init -q . ) >/dev/null
: > "$GQ/n-$BSVAL.md"
QUOTED="$( cd "$GQ" && $GIT -c core.quotePath=true ls-files --others )"
P="$ROOT/k12g"; make_payload "$P"; mkdir -p "$P/.git"
case "$QUOTED" in
  *'\\'*)
    GUARD_ENV=(PATH="$STUB:$PATH" STUB_MODE=stderr STUB_TEXT="$QUOTED")
    expect12 2 'cannot stat "n-\[value of FIXTURE_BACKSLASH withheld\]\.md"' \
      "git's stderr, C-quoting a name that holds a value with a backslash, prints with that copy withheld" \
      --vault "$FXV" --allowlist "$FXA" --credentials "$ROOT/k12.env" "$P" ;;
  *) no "premise: real git quotes a name with a backslash by doubling it (its quoting showed none)" ;;
esac
GUARD_ENV=(PATH="$STUB:$PATH" STUB_MODE=record STUB_TEXT="$(printf 'garbage\tn-%s.md' "$BSVAL")")
expect12 2 'unparseable `git ls-files -s` record ([0-9]* bytes; not shown' \
  "an unparseable git record is reported by its length, never by a repr of the path in it" \
  --vault "$FXV" --allowlist "$FXA" --credentials "$ROOT/k12.env" "$P"
GUARD_ENV=()
# The vault-side read errors: each names its file by a fixed label, and the OS reason alone.
AL12="$ROOT/al-$BSVAL.md"; cp "$FXA" "$AL12"; chmod 000 "$AL12"
L="an unreadable allowlist whose path holds a value: the OS reason alone, never the escaped path"
locked "$L" && expect12 2 "cannot read publish-allowlist.md (Permission denied)$" "$L" \
  --vault "$FXV" --allowlist "$AL12" --credentials "$ROOT/k12.env" "$P2"
chmod 600 "$AL12"
V12="$ROOT/vault-$BSVAL"; mkdir -p "$V12/output"; printf '# c\n' > "$V12/CLAUDE.md"
printf 'marker\n\n## Settings\n- **agent_name**: Zephyrine\n' > "$V12/CUSTOMISATION.md"
chmod 000 "$V12/CUSTOMISATION.md"
L="an unreadable CUSTOMISATION.md in a vault whose path holds a value: the reason alone"
locked "$L" && expect12 2 "cannot read CUSTOMISATION.md (Permission denied)$" "$L" \
  --vault "$V12" --allowlist "$FXA" --credentials "$ROOT/k12.env" "$P2"
chmod 600 "$V12/CUSTOMISATION.md"
printf 'x\n' > "$V12/output/publish-gate-strings.txt"; chmod 000 "$V12/output/publish-gate-strings.txt"
L="an unreadable gate-strings file in that vault: the reason alone"
locked "$L" && expect12 2 "cannot read output/publish-gate-strings.txt (Permission denied)$" "$L" \
  --vault "$V12" --allowlist "$FXA" --credentials "$ROOT/k12.env" "$P2"
chmod 600 "$V12/output/publish-gate-strings.txt"
# Source shape: no handler of an OS error formats the error itself (its text quotes the file
# name escaped); each uses os_reason, or its strerror, errno or type.
AST_CHECK='import ast, sys
OS_TYPES = {"OSError", "IOError", "EnvironmentError", "BrokenPipeError", "PermissionError",
            "FileNotFoundError", "NotADirectoryError", "IsADirectoryError", "Exception",
            "BaseException"}
def caught(t):
    return any(isinstance(n, ast.Name) and n.id in OS_TYPES
               for n in (t.elts if isinstance(t, ast.Tuple) else [t]))
bad = 0
for h in ast.walk(ast.parse(sys.stdin.read())):
    if not (isinstance(h, ast.ExceptHandler) and h.name and h.type is not None and caught(h.type)):
        continue
    safe = set()
    for n in ast.walk(h):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id in ("os_reason", "drop_os_names", "type", "isinstance"):
            safe.update(id(a) for a in n.args)
        if isinstance(n, ast.Attribute) and n.attr in ("strerror", "errno"):
            safe.add(id(n.value))
    bad += sum(1 for n in ast.walk(h) if isinstance(n, ast.Name) and n.id == h.name
               and isinstance(n.ctx, ast.Load) and id(n) not in safe)
sys.stdout.write("%d\n" % bad)'
N_RAW="$(python3 -c "$AST_CHECK" < "$GUARD")"
N_CTL="$(printf 'try:\n    pass\nexcept OSError as err:\n    raise Premise("a (%%s)" %% err)\nexcept (BrokenPipeError, OSError) as err:\n    raise Premise("b (%%s)" %% os_reason(err))\n' | python3 -c "$AST_CHECK")"
if [ "$N_RAW" = 0 ] && [ "$N_CTL" = 1 ]; then
  ok "no OS-error handler formats the error itself, only its reason (control: the same check finds the 1 bad of a planted pair)"
else no "an OS-error handler formats the error itself ($N_RAW found), so an escaped file name can reach a message (control: $N_CTL of 1)"; fi
# A store the guard cannot stat is a broken premise, never an absent one.
mkdir -p "$FXV/output/user-notes"; cp "$FAKE" "$FXV/output/user-notes/credentials.env"; chmod 000 "$FXV/output/user-notes"
L="the DEFAULT store under a directory the guard cannot search exits 2, never passes as absent"
if python3 -c 'import os, sys
try:
    os.stat(sys.argv[1])
except PermissionError:
    sys.exit(0)
sys.exit(1)' "$FXV/output/user-notes/credentials.env"; then
  expect12 2 "credential store output/user-notes/credentials.env cannot be checked (Permission denied)" "$L" \
    --vault "$FXV" --allowlist "$FXA" "$P2"
else no "premise: a store under a mode-000 directory cannot be stat'd here (its stat succeeded): $L"; fi
chmod 700 "$FXV/output/user-notes"; rm -rf "$FXV/output"
mkdir -p "$ROOT/k12-locked"; cp "$FAKE" "$ROOT/k12-locked/store.env"; chmod 000 "$ROOT/k12-locked"
L="an override store under a mode-000 parent exits 2 too"
locked "$L" && expect12 2 "NON-DEFAULT (store.env) cannot be checked (Permission denied)" "$L" \
  --vault "$FXV" --allowlist "$FXA" --credentials "$ROOT/k12-locked/store.env" "$P2"
chmod 700 "$ROOT/k12-locked"
ln -s "$ROOT/k12-loop.env" "$ROOT/k12-loop.env"
expect12 2 "NON-DEFAULT (k12-loop.env) cannot be checked" \
  "a link that loops on itself is a store the guard cannot see: exit 2, not a missing link" \
  --vault "$FXV" --allowlist "$FXA" --credentials "$ROOT/k12-loop.env" "$P2"
expect12 0 "no credential file at NON-DEFAULT (inner.env)" \
  "a path through a regular file is absent, as before: said so, and never a failure" \
  --vault "$FXV" --allowlist "$FXA" --credentials "$ROOT/k12.env/inner.env" "$P2"
# Messages that echo an argument are printed only after the store is read and the output armed.
GF=(--vault "$FXV" --allowlist "$FXA" --credentials "$FAKE")
expect12 2 "missing-\[value of FIXTURE_TEST_TOKEN withheld\] is not a directory" \
  "a root that is not a directory, its path holding a value: the message withholds it" \
  "${GF[@]}" "$ROOT/missing-$FAKEVAL"
expect12 2 "unknown option --bogus-\[value of FIXTURE_TEST_TOKEN withheld\]" \
  "an unknown option carrying a value is withheld" \
  "${GF[@]}" "--bogus-$FAKEVAL" "$P2"
expect12 2 "cannot derive the owner's strings: .*vault-\[value of FIXTURE_TEST_TOKEN withheld\] has no" \
  "a --vault that is not a vault, its path holding a value, is withheld: --credentials is read first" \
  --allowlist "$FXA" --credentials "$FAKE" --vault "$ROOT/vault-$FAKEVAL" "$P2"
expect12 2 "release \[value of FIXTURE_TEST_TOKEN withheld\] does not parse" \
  "an unparseable --release carrying a value is withheld" \
  "${GF[@]}" --release "$FAKEVAL" "$P2"
expect12 2 "more than one directory given (.*second-\[value of FIXTURE_TEST_TOKEN withheld\])" \
  "a second directory argument carrying a value is withheld" \
  "${GF[@]}" "$P2" "$ROOT/second-$FAKEVAL"
# A value with a backslash is read the ways a shell's source and a dotenv reader read it, and as
# written; the payload below carries only the readings the guard's own reading is not.
printf 'FIXTURE_DOLLAR="dl\\$-%s"\nFIXTURE_NEWLINE="nl\\n-%s"\nFIXTURE_QUOTED="qt\\"-%s"\nFIXTURE_UNQUOTED=uq\\x-%s\n' \
  "$NONCE" "$NONCE" "$NONCE" "$NONCE" > "$ROOT/k13.env"
P="$ROOT/k13"; make_payload "$P"
printf 'shell: dl$-%s\ndotenv: nl\n-%s\nas written: qt\\"-%s\nshell, unquoted: uqx-%s\n' \
  "$NONCE" "$NONCE" "$NONCE" "$NONCE" > "$P/MANUAL.md"
GF13=(--vault "$FXV" --allowlist "$FXA" --credentials "$ROOT/k13.env")
expect12 1 "the value of FIXTURE_DOLLAR \[from" \
  'a double-quoted backslash-dollar is caught as a shell reads it (the dollar bare)' "${GF13[@]}" "$P"
expect12 1 "the value of FIXTURE_NEWLINE \[from" \
  'a double-quoted backslash-n is caught as a dotenv reader reads it (a real newline)' "${GF13[@]}" "$P"
expect12 1 "the value of FIXTURE_QUOTED \[from" \
  'an escaped quote is caught as the store writes it (a paste of its line)' "${GF13[@]}" "$P"
expect12 1 "the value of FIXTURE_UNQUOTED \[from" \
  'an unquoted backslash is caught as a shell reads it (the backslash gone)' "${GF13[@]}" "$P"
expect12 1 "4 value(s) checked from NON-DEFAULT (k13.env) (4 key(s)), with 4 other reading(s) of a value with a backslash" \
  "the line counts each value once, and its other readings after it" "${GF13[@]}" "$P"
# Only backslashes are read differently: a value is never cut at a blank into a commoner word.
printf 'FIXTURE_WORDS=Zqwordnine tail-%s\n' "$NONCE" > "$ROOT/k14.env"
P="$ROOT/k14"; make_payload "$P"; printf 'the word Zqwordnine alone\n' > "$P/MANUAL.md"
expect12 0 "credentials: 1 value(s) checked from NON-DEFAULT (k14.env) (1 key(s));" \
  "an unquoted value with a blank is not cut: its first word alone in the payload is no finding" \
  --vault "$FXV" --allowlist "$FXA" --credentials "$ROOT/k14.env" "$P"

echo "── group 13: --draft — the same probes on one suggestion draft ──"
# A copy of the guard in a neutral folder with a seed of its own, so the default agent name is one
# this suite chose, and with no allowlist beside it, so a draft that passes proves none is read.
# Its vault is a fixture too, and every call passes --credentials, so no real store is reachable.
DG="$ROOT/dg"; mkdir -p "$DG/payload"; cp "$GUARD" "$DG/publish_guard.py"
SEEDLINE='- **agent_name**: Seedname — what the agent calls itself (blank = none)'
printf '%s\n' "$SEEDLINE" > "$DG/payload/setup.sh"
fxvault(){ local v="$1" name="$2"
  mkdir -p "$v/output"
  printf '# fixture contract\n' > "$v/CLAUDE.md"
  printf '## Settings\n- **agent_name**: %s — what the agent calls itself\n' "$name" > "$v/CUSTOMISATION.md"
  $GIT -C "$v" init -q
  $GIT -C "$v" config user.name "Quillsworth Vaneska"
  $GIT -C "$v" config user.email "qz9917+ZephyrineQ@example.invalid"
  $GIT -C "$v" config remote.origin.url "https://example.com/ZephyrineQ/fx.git"
}
DV="$ROOT/dv/Folderword"; fxvault "$DV" "Seedname"
printf 'Affiliation Marker Nine\n' > "$DV/output/publish-gate-strings.txt"
D="$ROOT/drafts"; mkdir -p "$D"
printf '# Clearer lint wording\n\n### What should change\nThe lint step could say more.\n\n### Why\nIt reads short.\n\n### Core check\ncore: v0.10.0, unchanged (235 files)\n' > "$D/clean.md"
DRAFT_GUARD="$DG/publish_guard.py"; DRAFT_VAULT="$DV"
draft(){ OUT="$(env USER=fxaccount LOGNAME=fxaccount HOME="$FXH" \
                    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
                    python3 -B "$DRAFT_GUARD" --vault "$DRAFT_VAULT" --credentials "$FAKE" "$@" 2>&1)"; RC=$?; }
# expect exit $1 and, when given, pattern $2 in the output from a draft run; no leg may print the
# fake value, and a run that is not exit 0 may never say clean.
expect13(){ local want="$1" needle="$2" label="$3"; shift 3
  draft "$@"
  if [ "$RC" != "$want" ]; then no "$label (exit $RC, wanted $want): $(echo "$OUT" | head -2)"; return; fi
  if [ -n "$needle" ] && ! printf '%s' "$OUT" | grep -q -- "$needle"; then
    no "$label (exit ok, but output lacks '$needle'): $(echo "$OUT" | head -2)"; return; fi
  if leaks; then no "$label (the output carries the fake value)"; return; fi
  if [ "$want" != 0 ] && printf '%s' "$OUT" | grep -q "check: clean"; then
    no "$label (exit $RC, yet the output says clean)"; return; fi
  ok "$label"
}
expect13 0 "check: clean — scanned draft clean.md" "a clean draft exits 0 and names what it scanned" --draft "$D/clean.md"
expect13 0 "3/3 draft probes" "…with its control: a path, a needle and a value planted at the end of a copy of it" --draft "$D/clean.md"
expect13 0 "no allowlist in draft mode" "…and no allowlist is read: none sits beside this copy of the guard" --draft "$D/clean.md"
expect13 0 "2/2 draft probes" "with no store the control counts the two classes it could plant" --credentials "$ROOT/absent-store.env" --draft "$D/clean.md"
expect13 0 "no credential file at NON-DEFAULT (absent-store.env)" "…and an absent store is said on the line" --credentials "$ROOT/absent-store.env" --draft "$D/clean.md"
draft --draft "$D/clean.md"
if printf '%s' "$OUT" | grep -q -F -- "$ROOT"; then no "a draft's folders stay out of the output: $(echo "$OUT" | head -1)"
else ok "a draft's folders stay out of the output, the owner's path among them"; fi

printf '# t\nOUT=%s/someone/vault/x\n' "$U" > "$D/home-mac.md"
expect13 1 "FINDING machine-path  home-mac.md" "a macOS home path in a draft is caught" --draft "$D/home-mac.md"
printf '# t\nOUT=%s/someone/notes\n' "$H" > "$D/home-linux.md"
expect13 1 "FINDING machine-path" "a Linux home path is caught" --draft "$D/home-linux.md"
printf '# t\nOUT=D:\\Users\\someone\\vault\n' > "$D/home-win.md"
expect13 1 "FINDING machine-path" "a Windows home path is caught" --draft "$D/home-win.md"
# A draft is a person's paste, so its rule reads the spellings their tools print. Every spelling
# below reads clean on the payload's rule, which is what makes each leg a test of the draft's.
WU='\U''sers'; WL='\u''sers'; WC='\U''SERS'; WD='\\U''sers'; WDL='\\u''sers'; WQ='\\\\U''sers'; UL="/u""sers"
spelt(){ printf '# t\nOUT=%s\n' "$2" > "$D/spelt.md"
  expect13 1 "FINDING machine-path  spelt.md" "$1 is caught" --draft "$D/spelt.md"; }
spelt "a Windows home root in lower case" "D:$WL\\someone\\vault"
spelt "a Windows home root in upper case" "D:$WC\\someone\\vault"
spelt "a Unicode account home path" "$U/élodie/notes"
spelt "a Unicode account under the Linux root" "$H/élodie/notes"
spelt "a Unicode account under the Windows root" "D:$WU\\élodie\\notes"
spelt "a Windows path with lower-case forward slashes" "c:$UL/someone/notes"
spelt "a Windows path with doubled backslashes" "\"C:$WD\\\\someone\\\\notes\""
spelt "the same in lower case" "\"c:$WDL\\\\someone\\\\notes\""
spelt "the same escaped once more" "\"C:$WQ\\\\\\\\someone\\\\\\\\notes\""
spelt "a Windows drive under Git Bash" "/c$U/someone/notes"
spelt "a Windows drive under WSL" "/mnt/c$U/someone/notes"
spelt "a Windows drive under Cygwin" "/cygdrive/c$U/someone/notes"
spelt "a macOS home root in lower case" "$UL/someone/notes"
spelt "a file URL with an escaped Unicode account" "file://$U/%C3%A9lodie/notes"
spelt "a home path with escaped slashes" "\"\\$U\\/someone\\/notes\""
spelt "a Windows path with no drive" "cd $WL\\someone\\notes"
# Each must stay quiet, or the wider rule would cry wolf on the words a suggestion uses.
quiet(){ printf '# t\n%s\n' "$2" > "$D/quiet.md"
  expect13 0 "check: clean" "$1 stays quiet" --draft "$D/quiet.md"; }
quiet "a relative path holding a root's word" "see docs$UL/guide and src$H/page"
quiet "a URL segment in lower case" "see https://example.com$UL/guide"
quiet "a fragment behind a variable" "cat \"\$W$H/.llm-wiki/last-run.txt\""
quiet "a shell placeholder" "$U/\$USER/notes and $H/\$USER/notes"
quiet "an angle-bracket placeholder" "$U/<you>/notes and $H/<you>/notes"
quiet "a Windows placeholder" "%USERPROFILE%\\notes and D:$WU\\%USERNAME%\\notes"
quiet "an account already taken out, leaving an ellipsis" "$U/…/notes and D:$WU\\…\\notes"
quiet "a root with no account" "$U/ and $H/"
quiet "a root's words in a sentence" "the users of the home page"
# The separator's bound keeps the scan linear: 16,000 slashes took 3 ms with it and 6.2 s without
# it (measured 5 November 2026), so a limit of 1 s stands well clear of both.
SPAN="$(python3 -B -c 'import sys, time; sys.path.insert(0, sys.argv[1])
import publish_guard as g
start = time.monotonic()
hits = list(g.home_hits(b"/" * 16000, True, draft=True))
print("fast" if not hits and time.monotonic() - start < 1 else "slow")' "$DG" 2>&1)"
if [ "$SPAN" = fast ]; then ok "a long run of slashes costs linear time"
else no "a long run of slashes: $SPAN"; fi
printf '# t\nthe agent home is ~/.llm-wiki/ under $HOME\n' > "$D/home-tilde.md"
expect13 0 "check: clean" "a tilde or \$HOME form stays quiet, as in the payload" --draft "$D/home-tilde.md"
printf '# t\nat the Affiliation Marker Nine lab\n' > "$D/gate.md"
expect13 1 "FINDING personal-str .*\[from extra\]" "a line of the owner's gate-strings file is caught" --draft "$D/gate.md"
printf '# t\na pasted token: %s\n' "$FAKEVAL" > "$D/cred.md"
expect13 1 "FINDING credential .*the value of FIXTURE_TEST_TOKEN" "a credential value is caught, by its KEY and never the value" --draft "$D/cred.md"
printf '# t\nOUT=%s/someone/vault/x\nat the Affiliation Marker Nine lab\ntoken %s\n' "$U" "$FAKEVAL" > "$D/all.md"
draft --draft "$D/all.md"
if [ "$RC" = 1 ] && printf '%s' "$OUT" | grep -q "1 machine path(s), 0 non-text file(s), 1 personal string(s), 1 credential value(s)" \
   && printf '%s' "$OUT" | grep -q "the value of FIXTURE_TEST_TOKEN" && ! leaks; then
  ok "one draft planting a home path, a gate string and a credential is caught on all three"
else no "one draft planting all three (exit $RC): $(echo "$OUT" | tail -3)"; fi
for w in Quillsworth quillsworth qz9917 ZephyrineQ fxaccount Folderword; do
  printf '# t\nsigned %s\n' "$w" > "$D/who.md"
  expect13 1 "FINDING personal-str" "the derived string '$w' is caught, in any case" --draft "$D/who.md"
done
printf 'x\n' > "$D/note-$FAKEVAL.md"
expect13 1 "note-\[value of FIXTURE_TEST_TOKEN withheld\]\.md" "a value in the draft's file NAME is caught and withheld" --draft "$D/note-$FAKEVAL.md"
printf '# t\nbinary\000bytes\n' > "$D/nul.md"
expect13 1 "FINDING non-text" "a draft with NUL bytes is caught as non-text" --draft "$D/nul.md"
# The limits stay as the guard states them: neither of these is a match.
printf '# t\na case-changed copy: %s\n' "$(printf '%s' "$FAKEVAL" | tr 'A-Z' 'a-z')" > "$D/case.md"
draft --draft "$D/case.md"
if [ "$RC" = 0 ]; then ok "stated limit: a case-changed copy of a value is not caught"
else no "stated limit: a case-changed copy (exit $RC)"; fi
printf '# t\nan encoded copy: %s\n' "$(printf '%s' "$FAKEVAL" | base64)" > "$D/enc.md"
expect13 0 "check: clean" "stated limit: a base64 copy of a value is not caught" --draft "$D/enc.md"
limit(){ printf '# t\nOUT=%s\n' "$2" > "$D/limit.md"
  expect13 0 "check: clean" "stated limit: $1 is not read as a path" --draft "$D/limit.md"; }
limit "a home root under another mount" "/var$H/someone/notes"
limit "a home root on a network share" "\\\\server$WL\\someone\\notes"
limit "a path with an escaped drive colon" "file:///c%3A$U/someone/notes"
printf '# t\nOUT=/var%s/fxaccount/notes\n' "$H" > "$D/limit-own.md"
expect13 1 "FINDING personal-str" "…yet the user's own account name there is still a hit" --draft "$D/limit-own.md"

echo "  — the agent name —"
printf '# t\nthe agent, Seedname, could say more\n' > "$D/agent.md"
expect13 0 "the shipped default agent name is no needle" "the default agent name alone is no hit" --draft "$D/agent.md"
DRAFT_VAULT="$ROOT/dv-own/plainfolder"; fxvault "$DRAFT_VAULT" "Zephyrine"
printf '# t\nthe agent, Zephyrine, could say more\n' > "$D/agent-own.md"
expect13 1 "FINDING personal-str .*\[from agent-name\]" "control: a user's own agent name IS a hit" --draft "$D/agent-own.md"
expect13 0 "check: clean" "…and the default stays quiet there too, being no string of that vault" --draft "$D/agent.md"
DRAFT_VAULT="$ROOT/dv-same/Seedname"; fxvault "$DRAFT_VAULT" "Seedname"
expect13 1 "FINDING personal-str .*\[from path-component\]" "a default that is also a folder name stays a hit, from that source alone" --draft "$D/agent.md"
DRAFT_VAULT="$DV"
DG2="$ROOT/dg2"; mkdir -p "$DG2"; cp "$GUARD" "$DG2/publish_guard.py"; DRAFT_GUARD="$DG2/publish_guard.py"
expect13 1 "FINDING personal-str .*\[from agent-name\]" "with no seed to read the agent name stays a needle: stricter, never looser" --draft "$D/agent.md"
expect13 1 "could not be read, so none is dropped" "…and the line says so" --draft "$D/agent.md"
DRAFT_GUARD="$DG/publish_guard.py"
if [ -f "$SKILL/payload/setup.sh" ]; then
  SEED_REAL="$(python3 -B -c 'import sys; sys.path.insert(0, sys.argv[1])
import publish_guard as g
print(g.seeded_agent_name() or "")' "$SKILL" 2>&1)"
  if [ -n "$SEED_REAL" ] && grep -q -F -- "$SEED_REAL" "$SKILL/payload/setup.sh"; then
    ok "the real payload/setup.sh still gives a default agent name to read"
  else no "the real payload/setup.sh gives no default agent name: $SEED_REAL"; fi
else no "payload/setup.sh is missing beside the guard, so the seed cannot be read"; fi

echo "  — broken premises exit 2, never clean —"
expect13 2 "PROBE FAILED: the draft absent.md is not a file" "a draft that is not there" --draft "$D/absent.md"
expect13 2 "PROBE FAILED: the draft drafts is not a file" "a directory given as a draft" --draft "$D"
: > "$D/empty.md"
expect13 2 "PROBE FAILED: the draft empty.md is empty" "an empty draft: clean would be a claim about nothing" --draft "$D/empty.md"
if [ "$(id -u)" != 0 ]; then
  printf 'x\n' > "$D/locked.md"; chmod 000 "$D/locked.md"
  expect13 2 "PROBE FAILED: cannot read the draft locked.md" "a draft that cannot be read" --draft "$D/locked.md"
  chmod 644 "$D/locked.md"
else ok "a draft that cannot be read: not testable as root"; fi
expect13 2 "exists but cannot be read" "a store that cannot be read is never reported clean" --credentials "$ROOT/k9.env" --draft "$D/clean.md"
expect13 2 "not a KEY=value line" "a store that cannot be parsed is never reported clean" --credentials "$ROOT/k7.env" --draft "$D/clean.md"
expect13 2 "PROBE FAILED: cannot derive" "no vault to derive from" --vault "$ROOT/no-such-vault" --draft "$D/clean.md"
expect13 2 "PROBE FAILED: --draft needs a value" "--draft with no file" --draft
expect13 2 "takes no a directory" "--draft beside a directory is refused" --draft "$D/clean.md" "$D"
expect13 2 "takes no --allowlist" "--draft beside --allowlist is refused" --allowlist "$FXA" --draft "$D/clean.md"
expect13 2 "takes no --release" "--draft beside --release is refused" --release v1.0 --draft "$D/clean.md"
expect13 2 "takes no --print-needles" "--draft beside --print-needles is refused" --print-needles --draft "$D/clean.md"
expect13 2 "value of FIXTURE_TEST_TOKEN withheld" "a refusal naming a missing draft withholds a value in its name" --draft "$D/gone-$FAKEVAL.md"
# Fault injection: the needle scan goes blind on the draft alone, past every fixed-buffer control.
# The planted copy must expose it, or the run would print clean over a scan that saw nothing.
OUT="$(env USER=fxaccount LOGNAME=fxaccount HOME="$FXH" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
  python3 -B -c 'import sys; sys.path.insert(0, sys.argv[1])
import publish_guard as g
real = g.scan_needles
g.scan_needles = lambda e, p: {} if e[0][0] == "clean.md" else real(e, p)
sys.exit(g.run(["publish_guard.py", "--vault", sys.argv[2], "--credentials", sys.argv[3], "--draft", sys.argv[4]]))' \
  "$DG" "$DV" "$FAKE" "$D/clean.md" 2>&1)"; RC=$?
if [ "$RC" = 2 ] && printf '%s' "$OUT" | grep -q "PROBE FAILED: draft control failed: a personal string"; then
  ok "a needle scan gone blind on the draft is a broken premise, never clean"
else no "a needle scan gone blind on the draft (exit $RC): $(echo "$OUT" | tail -2)"; fi
# The draft's own path rule goes blind: its fixed controls must say so, and with those stubbed out
# the copy planted through that same rule must, so neither control leans on the payload's rule.
blind_path(){ OUT="$(env USER=fxaccount LOGNAME=fxaccount HOME="$FXH" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
  python3 -B -c 'import re, sys; sys.path.insert(0, sys.argv[1])
import publish_guard as g
g.DRAFT_HOME_TEXT_RE = re.compile(b"zq-matches-nothing")
if sys.argv[5] == "stub":
    g.draft_path_controls = lambda: len(g.DRAFT_PATH_CONTROLS)
sys.exit(g.run(["publish_guard.py", "--vault", sys.argv[2], "--credentials", sys.argv[3], "--draft", sys.argv[4]]))' \
  "$DG" "$DV" "$FAKE" "$D/clean.md" "$1" 2>&1)"; RC=$?; }
blind_path real
if [ "$RC" = 2 ] && printf '%s' "$OUT" | grep -q "PROBE FAILED: draft path control failed"; then
  ok "a draft path rule gone blind is a broken premise, never clean"
else no "a draft path rule gone blind (exit $RC): $(echo "$OUT" | tail -2)"; fi
blind_path stub
if [ "$RC" = 2 ] && printf '%s' "$OUT" | grep -q "PROBE FAILED: draft control failed: a machine path"; then
  ok "…and past those controls the planted copy exposes it, since it runs through the same rule"
else no "the planted copy on a blind draft path rule (exit $RC): $(echo "$OUT" | tail -2)"; fi

echo "  — the last leg: draft mode writes nothing —"
# A sha-256 and mode for every file the runs could reach, before and after. The fixture git
# folders are in the set, since the guard asks git for the vault's identity. Its control changes
# one byte of a file in the same folder under the same permissions, which the check must catch.
manifest(){ python3 -B -c 'import hashlib, os, sys
rows = []
for top in sys.argv[1:]:
    walk = [(top, [], [""])] if os.path.isfile(top) else os.walk(top)
    for base, _dirs, files in walk:
        for name in files:
            p = os.path.join(base, name) if name else base
            with open(p, "rb") as fh:
                rows.append("%s %o %s" % (hashlib.sha256(fh.read()).hexdigest(), os.stat(p).st_mode, p))
print("\n".join(sorted(rows)))' "$@"; }
printf 'a byte to change\n' > "$D/control.md"; chmod 644 "$D/clean.md" "$D/control.md"
BEFORE="$(manifest "$D" "$DV" "$FAKE")"
draft --draft "$D/clean.md"; R1=$RC; O1="$OUT"
draft --draft "$D/all.md"; R2=$RC; O2="$OUT"
AFTER="$(manifest "$D" "$DV" "$FAKE")"
if [ "$R1" = 0 ] && [ "$R2" = 1 ] && printf '%s' "$O1" | grep -q "check: clean" \
   && printf '%s' "$O2" | grep -q "draft FAILED" && [ -n "$BEFORE" ] && [ "$BEFORE" = "$AFTER" ]; then
  ok "a clean run and a failing run gave their exits and left every file byte-identical ($(printf '%s\n' "$BEFORE" | wc -l | tr -d ' ') files)"
else no "the runs left the files byte-identical (exits $R1 and $R2)"; fi
printf 'A byte to change\n' > "$D/control.md"
CHANGED="$(manifest "$D" "$DV" "$FAKE")"
if [ "$AFTER" != "$CHANGED" ]; then ok "control: the check catches one changed byte in the same folder, under the same permissions"
else no "control: the check missed a changed byte"; fi

echo "── group 8: the gate is wired into the publish flow ──"
if grep -q "publish_guard.py" "$SKILL/SKILL.md"; then ok "SKILL.md's publish flow invokes the guard"
else no "SKILL.md's publish flow invokes the guard"; fi
if grep -q "publish_guard.py" "$SKILL/RUNBOOK.md"; then ok "RUNBOOK.md's verify list invokes the guard"
else no "RUNBOOK.md's verify list invokes the guard"; fi
if grep -q "publish_guard_v99.py" "$SKILL/SKILL.md"; then
  no "control: the same grep should MISS a name the skill does not carry"
else ok "control: the same grep misses a name the skill does not carry"; fi
if grep -q "credential value" "$SKILL/SKILL.md" && grep -q "credentials.env" "$SKILL/SKILL.md"; then
  ok "SKILL.md's gate description names the credential-value probe and its store"
else no "SKILL.md's gate description names the credential-value probe and its store"; fi
if grep -q "credential value" "$SKILL/RUNBOOK.md"; then ok "RUNBOOK.md's gate entry names the credential-value probe"
else no "RUNBOOK.md's gate entry names the credential-value probe"; fi
# The docs claim no more than the guard keeps: the 6-byte floor and literal matching stated (a
# case-changed or encoded copy is not caught), and no "every value" overstatement. Wrapped lines
# are joined first, so a phrase split across two lines still counts.
flat(){ tr -s ' \n' '  ' < "$1"; }
claims(){ printf '%s' "$1" | grep -q -F -- "$2" && ! printf '%s' "$1" | grep -q -F -- "$3" \
          && printf '%s' "$1" | grep -q -F -- "case-changed" && printf '%s' "$1" | grep -q -F -- "encoded"; }
if claims "$(flat "$SKILL/SKILL.md")" "withholds every value of 6 bytes or more that it read" "withholds any value it read"; then
  ok "SKILL.md states the floor and the case and encoding limits, and drops 'withholds any value it read'"
else no "SKILL.md states the narrowed guarantee (the floor, case, encoding) and drops the overstatement"; fi
if claims "$(flat "$SKILL/RUNBOOK.md")" "every credential value of 6 bytes or more" "keeps every credential value in"; then
  ok "RUNBOOK.md states the floor and the case and encoding limits, and drops 'keeps every credential value in'"
else no "RUNBOOK.md states the narrowed guarantee (the floor, case, encoding) and drops the overstatement"; fi
if ! claims "a withholds any value it read; withholds every value of 6 bytes or more that it read; case-changed; encoded" \
       "withholds every value of 6 bytes or more that it read" "withholds any value it read" \
   && claims "b withholds every value of 6 bytes or more that it read; case-changed; encoded" \
       "withholds every value of 6 bytes or more that it read" "withholds any value it read"; then
  ok "control: the docs check refuses a text that keeps the overstatement and accepts one without it"
else no "control: the docs check discriminates between the two wordings"; fi

echo
echo "================  RESULT: $PASS passed, $FAIL failed  ================"
rm -rf "$ROOT"
[ "$FAIL" -eq 0 ]
