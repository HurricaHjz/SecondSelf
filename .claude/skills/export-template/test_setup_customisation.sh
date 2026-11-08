#!/usr/bin/env bash
# test_setup_customisation.sh — unit tests for setup.sh seeding the customisation layer.
# Runs the shipped payload/setup.sh in an isolated temp dir; NEVER touches the real vault.
# Run:  bash test_setup_customisation.sh
# Premise guard: this suite needs process substitution. Invoked as `sh <file>` it dies mid-run
# with a raw syntax error and exit 2, and a caller grepping the output for "FAIL" then reads zero
# and calls it green. Probe the CAPABILITY, not the shell name: on macOS
# /bin/sh IS bash, so $BASH_VERSION is set while POSIX mode still disables the feature.
if ! (eval 'cat < <(echo probe)') >/dev/null 2>&1; then
  echo "ERROR: process substitution unavailable (POSIX mode?) — run: bash $0"; exit 2
fi

set -uo pipefail
PAY="$(cd "$(dirname "${BASH_SOURCE[0]}")/payload" && pwd)/setup.sh"
VAULT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ROOT="${TMPDIR:-/tmp}/setuptest.$$"
CUST="CUSTOMISATION.md"
DEFS="CUSTOMISATION-definitions.md"
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "    ok   — $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL   — $1"; }
hash_of(){ md5 -q "$1" 2>/dev/null || md5sum "$1" 2>/dev/null | cut -d' ' -f1; }
fresh(){ rm -rf "$ROOT"; mkdir -p "$ROOT"; cp "$PAY" "$ROOT/setup.sh"; chmod u+w "$ROOT/setup.sh"; }   # isolated: setup.sh cd's to its own dir
GIT="git -c user.email=t@t -c user.name=test -c commit.gpgsign=false -c init.defaultBranch=main"
mode_of(){ python3 -c 'import os, stat, sys; print(oct(stat.S_IMODE(os.stat(sys.argv[1]).st_mode))[2:])' "$1"; }
chk(){ if eval "$2" >/dev/null 2>&1; then ok "$1"; else no "$1"; fi; }

[ -f "$PAY" ] || { echo "cannot find payload/setup.sh"; exit 2; }

echo "== 1) setup.sh parses =="
if bash -n "$PAY"; then ok "valid bash syntax"; else no "syntax error"; fi

echo "== 2) plain init seeds a valid Customisation =="
fresh; ( cd "$ROOT" && bash setup.sh >/dev/null 2>&1 )
[ -f "$ROOT/$CUST" ]                          && ok "init creates $CUST"                  || no "init did not create $CUST"
grep -q '^- \*\*style\*\*: balanced' "$ROOT/$CUST" 2>/dev/null && ok "style knob seeded in ## Settings" || no "style knob missing from ## Settings"
grep -q '^## Settings' "$ROOT/$CUST" 2>/dev/null && ok "## Settings block present" || no "## Settings block missing"
sed -n '/^---$/,/^---$/p' "$ROOT/$CUST" | grep -qE '^(style|role|agent_name|language):' && no "knob still in frontmatter (import strips YAML)" || ok "no knob left in frontmatter"
grep -q '^### balanced'       "$ROOT/$CUST" 2>/dev/null && ok "default style defined in CORE" || no "default style has no ### section in core"
[ -f "$ROOT/$DEFS" ]                          && ok "init creates $DEFS (on-demand half)"  || no "init did not create $DEFS"
grep -q '^### detailed'       "$ROOT/$DEFS" 2>/dev/null && ok "detailed style in definitions file" || no "detailed style missing from $DEFS"
grep -q '^### shortest'       "$ROOT/$DEFS" 2>/dev/null && ok "shortest style in definitions file" || no "shortest style missing from $DEFS"
grep -q '^### brief'          "$ROOT/$DEFS" 2>/dev/null && ok "brief style in definitions file"    || no "brief style missing from $DEFS"
grep -q '^### detailed'       "$ROOT/$CUST" 2>/dev/null && no "detailed leaked into core (split broken)" || ok "core carries no non-default style (split holds)"
grep -q 'Definitions split'   "$ROOT/$CUST" 2>/dev/null && ok "Definitions-split rule seeded in core" || no "Definitions-split rule missing from core"
grep -q 'one canonical home per definition' "$ROOT/$CUST" 2>/dev/null && ok "block-move rule seeded" || no "block-move rule missing"
DUP=$(comm -12 <(grep '^### ' "$ROOT/$CUST" 2>/dev/null | sort) <(grep '^### ' "$ROOT/$DEFS" 2>/dev/null | sort))
[ -z "$DUP" ]                                 && ok "no ### heading duplicated across the pair" || no "duplicated heading(s): $DUP"
grep -q '\[\[About Me\]\]'    "$ROOT/$CUST" 2>/dev/null && ok "Related links [[About Me]] (no orphan)" || no "missing ## Related backlink"
grep -q '^- \*\*role\*\*: generalist' "$ROOT/$CUST" 2>/dev/null && ok "role knob seeded in ## Settings" || no "role knob missing from ## Settings"
grep -q '^- \*\*throttle\*\*: auto' "$ROOT/$CUST" 2>/dev/null && ok "throttle knob seeded in ## Settings (auto, the default preset from 2026-09-08)" || no "throttle knob missing from ## Settings"
grep -q '^- \*\*breadth\*\*: standard' "$ROOT/$CUST" 2>/dev/null && ok "breadth knob seeded in ## Settings" || no "breadth knob missing from ## Settings"
grep -q '^- \*\*delegation\*\*: auto' "$ROOT/$CUST" 2>/dev/null && ok "delegation knob seeded in ## Settings (auto is the default)" || no "delegation knob missing from ## Settings"
grep -q '^## Roles'           "$ROOT/$CUST" 2>/dev/null && ok "Roles section present"                  || no "Roles section missing"
grep -q "^### generalist" "$ROOT/$CUST" 2>/dev/null && ok "role seeded in core: generalist (default)" || no "role missing from core: generalist"
for r in researcher engineer tutor examiner; do
  grep -q "^### $r" "$ROOT/$DEFS" 2>/dev/null && ok "role seeded in definitions: $r" || no "role missing from definitions: $r"
done
grep -q "^### researcher" "$ROOT/$CUST" 2>/dev/null && no "researcher leaked into core (split broken)" || ok "core carries no non-default role (split holds)"
grep -Eq '^- overrides[ :]' "$ROOT/$CUST" && no "retired override syntax still seeded" || ok "no marked-override lines (mechanism retired 2026-08-17)"
grep -q 'no role may change the active style' "$ROOT/$CUST" 2>/dev/null && ok "roles-never-change-style clause seeded" || no "clause missing"
grep -q 'offer the full report' "$ROOT/$DEFS" 2>/dev/null && ok "examiner compression-notice line seeded" || no "notice line missing"
grep -q 'status line'         "$ROOT/$CUST" 2>/dev/null && ok "status-line rule shipped"               || no "status-line rule missing"
grep -q "never the agent's internal reasoning" "$ROOT/$CUST" 2>/dev/null && ok "reasoning-invariance clause shipped" || no "reasoning-invariance clause missing"
grep -q 'plainness and fluency hold on every style' "$ROOT/$CUST" 2>/dev/null && ok "plainness holds on every rung (one-dimension ladder, 2026-09-04)" || no "plainness preamble missing"
grep -q 'two dimensions that move together' "$ROOT/$CUST" 2>/dev/null && no "retired two-dimension sentence still seeded" || ok "control: the retired two-dimension sentence is absent"
grep -q '| Axis | Knob | Governs |' "$ROOT/$CUST" 2>/dev/null && no "retired axis table still seeded (cut BC-6, 7 November 2026)" || ok "control: the axis table, cut by BC-6, is absent"
grep -q '^### customised' "$ROOT/$CUST" 2>/dev/null && ok "customised span seeded (№56)" || no "customised span missing"
grep -q 'a claim, never a label' "$ROOT/$CUST" 2>/dev/null && ok "status-line claim rule seeded (№56)" || no "status-line claim rule missing"
T=$(( $(grep -c 'Test:' "$ROOT/$CUST" 2>/dev/null || echo 0) + $(grep -c 'Test:' "$ROOT/$DEFS" 2>/dev/null || echo 0) ))
[ "$T" -ge 6 ] && ok "per-style Test clauses seeded across the pair ($T lines)" || no "Test clauses missing ($T lines across pair, need >=6)"
RAW=$(python3 -c "
import re,sys
s=open('$ROOT/$CUST').read()
b=re.sub(r'\A---\n.*?\n---\n','',s,flags=re.S); b=re.sub(r'<!--.*?-->','',b,flags=re.S); b=re.sub(r'\`[^\`]*\`','',b)
print(len(re.findall(r'<[a-zA-Z][\w-]*>',b)))" 2>/dev/null || echo 99)
[ "$RAW" = 0 ]                                && ok "no raw HTML-parsed tokens in rendered prose"      || no "$RAW raw <tag> token(s) leak into rendered prose"
grep -q 'CUSTOMISATION-LOADED-v1'     "$ROOT/$CUST" 2>/dev/null && ok "load marker seeded"                  || no "load marker missing"
grep -q '^@CUSTOMISATION\.md' "$VAULT/CLAUDE.md" && ok "shipped CLAUDE.md imports the preference layer" || no "CLAUDE.md import line missing"
# Preference validity is determined by the semantic checks.
if grep -q "Four invariants hold across the ladder" "$ROOT/CUSTOMISATION.md" && grep -q "filed work is never restated" "$ROOT/CUSTOMISATION.md"; then ok "fourth invariant (no-restatement) seeded"; else no "fourth invariant missing from seeded CUSTOMISATION"; fi
# Reference: №56.

echo "== 2b) definitions half is idempotent too =="
printf '\nMY DEFS EDIT\n' >> "$ROOT/$DEFS"
B2=$(hash_of "$ROOT/$DEFS"); ( cd "$ROOT" && bash setup.sh >/dev/null 2>&1 ); A2=$(hash_of "$ROOT/$DEFS")
[ "$A2" = "$B2" ]                             && ok "re-run preserves definitions edits"   || no "re-run overwrote definitions file"

echo "== 3) re-run is idempotent (never overwrites user edits) =="
fresh; ( cd "$ROOT" && bash setup.sh >/dev/null 2>&1 ); printf '\nMY EDIT\n' >> "$ROOT/$CUST"
B=$(hash_of "$ROOT/$CUST"); ( cd "$ROOT" && bash setup.sh >/dev/null 2>&1 ); A=$(hash_of "$ROOT/$CUST")
[ "$A" = "$B" ]                               && ok "re-run preserves user edits"          || no "re-run overwrote user edits"

echo "== 4) --reset preserves Customisation (user config) but blanks registries =="
fresh; ( cd "$ROOT" && bash setup.sh >/dev/null 2>&1 ); printf '\nMY EDIT\n' >> "$ROOT/$CUST"
B=$(hash_of "$ROOT/$CUST"); ( cd "$ROOT" && bash setup.sh --reset >/dev/null 2>&1 ); A=$(hash_of "$ROOT/$CUST")
[ "$A" = "$B" ]                               && ok "--reset keeps Customisation"          || no "--reset clobbered Customisation"
[ -f "$ROOT/wiki/index.md" ] && [ -f "$ROOT/wiki/log.md" ] && ok "--reset re-creates registries" || no "--reset missing registries"

echo "== 5) --reset seeds Customisation when absent =="
fresh; ( cd "$ROOT" && bash setup.sh --reset >/dev/null 2>&1 )
[ -f "$ROOT/$CUST" ]                          && ok "--reset seeds if missing"             || no "--reset did not seed"
[ -f "$ROOT/$DEFS" ]                          && ok "--reset seeds definitions half too"   || no "--reset did not seed $DEFS"

echo "== 6) --with-example seeds Customisation =="
fresh; ( cd "$ROOT" && bash setup.sh --with-example >/dev/null 2>&1 )
[ -f "$ROOT/$CUST" ]                          && ok "--with-example seeds Customisation"   || no "--with-example did not seed"
[ -f "$ROOT/$DEFS" ]                          && ok "--with-example seeds definitions half" || no "--with-example did not seed $DEFS"

echo "== 7) mk_log seeds the full action list incl. deep-lint =="
fresh; ( cd "$ROOT" && bash setup.sh >/dev/null 2>&1 )
grep -q 'deep-lint' "$ROOT/wiki/log.md"       && ok "log.md action list includes deep-lint" || no "log.md missing deep-lint"

echo "== 8) IDEAS.md scratchpad seeded =="
[ -f "$ROOT/IDEAS.md" ]                                    && ok "init seeds IDEAS.md at vault root"      || no "IDEAS.md not seeded"
grep -q '^## 📋 Overview' "$ROOT/IDEAS.md" 2>/dev/null     && ok "Overview table section present"         || no "Overview section missing"
grep -q 'ignores this file in normal runs' "$ROOT/IDEAS.md" 2>/dev/null && ok "ignore-by-default rule stated" || no "ignore rule missing"
printf '\n- my idea\n' >> "$ROOT/IDEAS.md"
B=$(hash_of "$ROOT/IDEAS.md"); ( cd "$ROOT" && bash setup.sh >/dev/null 2>&1 ); A=$(hash_of "$ROOT/IDEAS.md")
[ "$A" = "$B" ]                                            && ok "re-run preserves owner's IDEAS edits"   || no "re-run overwrote IDEAS.md"

echo "== 9) setup.sh builds the lane home headless lanes run from =="
# The lane home is machine-local state outside the vault, so setup builds it rather than the payload
# shipping one. Three cases, because a step that runs a wrapper has three outcomes: no wrapper (a vault
# on an older framework), the wrapper succeeding, the wrapper failing its own premise (a brand-new vault
# has no confidence-rubric page to slice). In all three setup must finish and say what happened, since
# a bootstrap that aborts on an optional extra leaves the user with no registries at all.
LW=".claude/skills/delegate/lane.py"
fresh; OUT9="$( cd "$ROOT" && bash setup.sh 2>&1 )"; RC9=$?
[ "$RC9" = 0 ]                                 && ok "no wrapper: setup still succeeds"            || no "no wrapper: setup exited $RC9"
echo "$OUT9" | grep -qi 'lane home skipped'    && ok "no wrapper: says the lane home was skipped"  || no "no wrapper: silent about the lane home"
[ -f "$ROOT/wiki/index.md" ]                   && ok "no wrapper: the registries were still seeded" || no "no wrapper: registries missing"

fresh; mkdir -p "$ROOT/.claude/skills/delegate"
printf '#!/usr/bin/env python3\nimport sys\nprint("lane home: /tmp/fixture-lane-home")\nprint("  created      lane-fence.py")\nsys.exit(0)\n' > "$ROOT/$LW"
OUT9B="$( cd "$ROOT" && bash setup.sh 2>&1 )"; RC9B=$?
[ "$RC9B" = 0 ]                                && ok "wrapper ok: setup succeeds"                   || no "wrapper ok: setup exited $RC9B"
echo "$OUT9B" | grep -q 'lane home ready'      && ok "wrapper ok: setup reports the lane home ready" || no "wrapper ok: no lane-home line in output"
echo "$OUT9B" | grep -q 'fixture-lane-home'    && ok "wrapper ok: setup shows where it was built"    || no "wrapper ok: location not shown"

fresh; mkdir -p "$ROOT/.claude/skills/delegate"
printf '#!/usr/bin/env python3\nimport sys\nsys.stderr.write("lane.py: PROBE FAILED: cannot read the confidence rubric page\\n")\nsys.exit(2)\n' > "$ROOT/$LW"
OUT9C="$( cd "$ROOT" && bash setup.sh 2>&1 )"; RC9C=$?
[ "$RC9C" = 0 ]                                && ok "wrapper fails: setup still succeeds (exit 0)"  || no "wrapper fails: setup exited $RC9C"
echo "$OUT9C" | grep -q 'lane home not created' && ok "wrapper fails: setup says so plainly"         || no "wrapper fails: failure swallowed"
echo "$OUT9C" | grep -q 'PROBE FAILED'         && ok "wrapper fails: the wrapper's own reason is shown" || no "wrapper fails: reason hidden"
echo "$OUT9C" | grep -q "python3 $LW init"     && ok "wrapper fails: the recovery command is printed" || no "wrapper fails: no recovery command"
[ -f "$ROOT/wiki/index.md" ]                   && ok "wrapper fails: the registries were still seeded" || no "wrapper fails: registries missing"
# §11 control: these greps must be able to miss — a line setup.sh never prints must not match.
echo "$OUT9C" | grep -q 'lane home ready'      && no "control failed: 'ready' matched a failing run" || ok "control: the success line does not match a failing run"

echo "== 10) the seed's defaults for other users (public-version rows A3, A6, A7, A20) =="
fresh; ( cd "$ROOT" && bash setup.sh >/dev/null 2>&1 )
grep -q '^- \*\*agent_name\*\*: ai''Myth ' "$ROOT/$CUST" 2>/dev/null && ok "the default agent name is seeded (a user can change it)" || no "default agent name missing"
grep -q 'keep each bullet.s name when you change its text' "$ROOT/$CUST" 2>/dev/null && ok "the starter rules say their names are load-bearing" || no "starter-rules note missing"
# Every rule a shipped text names in CUSTOMISATION.md has a bullet of that name in the seed, so no pointer dangles.
for rule in 'Decisions are asked in one pattern' 'Provisional choices' 'New features: search first, discuss first' \
            'Routing and rounds' 'Rounds are judged by progress, not counted' 'Stopped designs' 'Hand-over and reflection' \
            'Planned jobs go on through a successor' 'Session hand-off after a queue item' 'Transcripts' 'Safety-FP posture'; do
  grep -qF -- "- **$rule**:" "$ROOT/$CUST" 2>/dev/null && ok "seed names the rule: $rule" || no "seed lacks the rule: $rule"
done
grep -qF -- '- **No such rule**:' "$ROOT/$CUST" 2>/dev/null && no "control failed: the probe matched a rule the seed lacks" || ok "control: the same probe misses a rule the seed lacks"
grep -q 'in the same turn, the source named' "$ROOT/$CUST" 2>/dev/null && ok "the current-state clause is seeded (CLAUDE.md §13 cites it)" || no "current-state clause missing"
grep -q 'a report you asked to be walked through' "$ROOT/$CUST" 2>/dev/null && ok "the styles invariant carries its walk-through exception" || no "styles exception missing"
grep -q 'names the armed wait doing it' "$ROOT/$CUST" 2>/dev/null && ok "the monitoring clause is seeded" || no "monitoring clause missing"
grep -q 'never on a proxy' "$ROOT/$CUST" 2>/dev/null && ok "the eligibility clause is seeded" || no "eligibility clause missing"
grep -q 'expects one machine per vault' "$ROOT/$CUST" 2>/dev/null && grep -q 'earns an exact skip' "$ROOT/$CUST" 2>/dev/null && ok "the register's one-machine rule and skip rule are stated" || no "register rule missing"
grep -q 'where the anchor hook is installed, the agent opens it' "$ROOT/$CUST" 2>/dev/null && ok "set-span is conditional on the hook" || no "set-span still unconditional"
grep -q "<style> · <delegation>" "$ROOT/$CUST" 2>/dev/null && ok "the status line names the delegation knob" || no "status line still names mode"
grep -q 'Proactively improve when you spot room' "$ROOT/$DEFS" 2>/dev/null && ok "engineer: the current improvement line is seeded" || no "engineer improvement line stale"
grep -q 'propose-only, never implement without an explicit go' "$ROOT/$DEFS" 2>/dev/null && no "engineer: the old improvement line is still seeded" || ok "control: the old engineer line is gone"
grep -q 'approved scope never bounds what is proposed' "$ROOT/$DEFS" 2>/dev/null && ok "engineer: the current best-design line is seeded" || no "engineer best-design line stale"
grep -q 'on the owner.s yes to an archive it prepared' "$ROOT/attic/MANIFEST.md" 2>/dev/null && ok "attic manifest states the current rule" || no "attic manifest stale"
grep -q 'never opens the attic' "$ROOT/attic/MANIFEST.md" 2>/dev/null && no "attic manifest keeps the old wording" || ok "control: the old attic wording is gone"
# A shipped seed names no wiki page that only one vault has.
grep -qE '\[\[(owner-rulings-history|stopped-designs-rule|routing-table|model-safety-fp-isolation|funding-opportunities)\]\]' "$ROOT/$CUST" 2>/dev/null && no "the seed links a page a fresh vault lacks" || ok "the starter rules link no vault-only page"

echo "== 11) the seeds of the deferred features: present, listed, and yours once seeded =="
fresh; ( cd "$ROOT" && bash setup.sh >/dev/null 2>&1 )
KI="$ROOT/wiki/developments/known-issues.md"; SM="$ROOT/wiki/developments/stale-marks.md"; RH="$ROOT/wiki/developments/owner-rulings-history.md"
chk "seed: known-issues has its two sections"          'grep -qx "## Open" "$KI" && grep -qx "## Closed" "$KI"'
chk "seed: known-issues states its entry format"       'grep -qF "### [YYYY-MM-DD] <surface>" "$KI"'
chk "seed: the stale-marks method page"                'grep -qx "## Who marks" "$SM" && grep -qx "## Who clears it" "$SM"'
chk "seed: the rulings-history page"                   'grep -q "old wording moves here" "$RH"'
chk "seed: wiki/experience exists"                     '[ -d "$ROOT/wiki/experience" ]'
chk "seed: output/reports exists"                      '[ -d "$ROOT/output/reports" ]'
for p in check-lifecycle known-issues stale-marks owner-rulings-history; do
  chk "seed: $p has its registry line"                 "grep -qF '[[$p]]' \"\$ROOT/wiki/index.md\""
done
for f in "$KI" "$SM" "$RH"; do
  n="${f##*/}"
  chk "seed: $n carries the schema frontmatter"        "head -12 \"$f\" | grep -q '^confidence: ' && head -12 \"$f\" | grep -q '^audited: ' && head -12 \"$f\" | grep -q '^type: development'"
  chk "seed: $n has a Related section with a link"     "sed -n '/^## Related/,\$p' \"$f\" | grep -q '\[\['"
done
# A seed links only pages a fresh vault holds.
SEEDLINKS=$(cat "$KI" "$SM" "$RH" | grep -oE '\[\[[^]]+\]\]' | sort -u | tr -d '[]')
chk "control: the seeds link at least three pages"     '[ "$(printf "%s\n" "$SEEDLINKS" | grep -c .)" -ge 3 ]'
MISSING=""
for l in $SEEDLINKS; do [ -f "$ROOT/wiki/developments/$l.md" ] || MISSING="$MISSING $l"; done
chk "seed: every link in a seed resolves in a fresh vault" '[ -z "$MISSING" ]'
[ -z "$MISSING" ] || echo "      links to nothing:$MISSING"
IDX1=$(grep -c . "$ROOT/wiki/index.md")
printf '\nMY NOTE\n' >> "$KI"; printf '\nMY NOTE\n' >> "$SM"; printf '\nMY NOTE\n' >> "$RH"
HK=$(hash_of "$KI"); HS=$(hash_of "$SM"); HR=$(hash_of "$RH")
( cd "$ROOT" && bash setup.sh >/dev/null 2>&1 )
chk "seed: a re-run keeps an edit to known-issues"     '[ "$(hash_of "$KI")" = "$HK" ]'
chk "seed: a re-run keeps an edit to stale-marks"      '[ "$(hash_of "$SM")" = "$HS" ]'
chk "seed: a re-run keeps an edit to the rulings page" '[ "$(hash_of "$RH")" = "$HR" ]'
chk "seed: a re-run adds no second registry line"      '[ "$(grep -c . "$ROOT/wiki/index.md")" = "$IDX1" ]'
printf 'changed\n' >> "$KI"
chk "control: the same hash sees a changed page"       '[ "$(hash_of "$KI")" != "$HK" ]'
OUT11=$(cd "$ROOT" && env PATH=/usr/bin:/bin bash setup.sh 2>&1)
chk "seed: no codex on PATH gets one line saying GPT helpers are optional" 'echo "$OUT11" | grep -q "GPT helpers off"'
mkdir -p "$ROOT/stubbin"; printf '#!/bin/sh\nexit 0\n' > "$ROOT/stubbin/codex"; chmod +x "$ROOT/stubbin/codex"
OUT11=$(cd "$ROOT" && env PATH="$ROOT/stubbin:/usr/bin:/bin" bash setup.sh 2>&1)
chk "control: with a codex on PATH the line is absent" '! echo "$OUT11" | grep -q "GPT helpers off"'

echo "== 12) the lock: a clone's core is read-only, and your layer is not =="
# A small published framework: real setup.sh, real core list, real ignore file, one tracked script, one
# definition, the settings file and the four Obsidian files.
UP="$ROOT/up.git"; W="$ROOT/work"; C="$ROOT/clone"
make_release(){
  rm -rf "$ROOT"; mkdir -p "$W/.claude/skills/query" "$W/.claude/agents" "$W/.claude/hooks" "$W/.obsidian" "$W/examples"
  cp "$PAY" "$W/setup.sh"; cp "$(dirname "$PAY")/gitignore.txt" "$W/.gitignore"; cp "$(dirname "$PAY")/core-paths.txt" "$W/.claude/core-paths"
  printf '* text=auto\n' > "$W/.gitattributes"; printf '# rules\n' > "$W/CLAUDE.md"; printf '# manual\n' > "$W/MANUAL.md"; printf '# readme\n' > "$W/README.md"
  printf '# skill\n' > "$W/.claude/skills/query/SKILL.md"; printf '#!/bin/sh\necho hi\n' > "$W/.claude/skills/query/run.sh"
  printf -- '---\nmodel: opus\neffort: high\n---\nbody\n' > "$W/.claude/agents/helper.md"
  printf '# hook\n' > "$W/.claude/hooks/a-hook.py"; printf '{ "hooks": {} }\n' > "$W/.claude/settings.json"
  for f in graph app core-plugins appearance; do printf '{ "x": 1 }\n' > "$W/.obsidian/$f.json"; done
  printf '# an example\n' > "$W/examples/e.md"
  chmod -R u+w "$W"; chmod 755 "$W/setup.sh" "$W/.claude/skills/query/run.sh"
  $GIT init -q --bare "$UP"
  ( cd "$W" && $GIT init -q && $GIT add -A && $GIT commit -qm v1 && $GIT tag -a v1.0.0 -m v1 && $GIT remote add origin "$UP" && $GIT push -q -u origin main --tags ) >/dev/null 2>&1
  $GIT clone -q "$UP" "$C" >/dev/null 2>&1
}
core_modes(){ ( cd "$C" && git ls-files -z | xargs -0 python3 -c 'import os, stat, sys
for p in sys.argv[1:]: print(oct(stat.S_IMODE(os.stat(p).st_mode))[2:], p)' ); }
any_write_bit(){ core_modes | grep -v -e ' README.md$' -e ' examples/' -e ' .obsidian/' -e ' .claude/agents/' -e ' .claude/settings.json$' | grep -vE '^(444|555) ' ; }
make_release
chk "control: a new clone's core is writable before setup"   '[ "$(mode_of "$C/CLAUDE.md")" = 644 ]'
OUT12=$(cd "$C" && env HOME="$ROOT/hm" bash setup.sh 2>&1); RC12=$?
chk "lock: setup exits 0"                                    '[ "$RC12" = 0 ]'
chk "lock: setup says how many it locked"                    'echo "$OUT12" | grep -q "core locked: [0-9]* read-only files"'
chk "lock: no tool complained on the way"                    '! echo "$OUT12" | grep -qE "^(chmod|git|bash|setup.sh):"'
chk "lock: a core text file is 0444"                         '[ "$(mode_of "$C/CLAUDE.md")" = 444 ]'
chk "lock: a core skill is 0444"                             '[ "$(mode_of "$C/.claude/skills/query/SKILL.md")" = 444 ]'
chk "lock: a tracked script keeps its execute bit, at 0555"  '[ "$(mode_of "$C/.claude/skills/query/run.sh")" = 555 ] && [ "$(mode_of "$C/setup.sh")" = 555 ]'
chk "lock: every locked core file has no write bit"          '[ -z "$(any_write_bit)" ]'
chk "lock: a helper definition stays writable for the throttle" '[ "$(mode_of "$C/.claude/agents/helper.md")" = 644 ]'
chk "lock: the settings file stays writable for an always-allow answer" '[ "$(mode_of "$C/.claude/settings.json")" = 644 ]'
chk "lock: a shipped file that is not core stays writable"   '[ "$(mode_of "$C/README.md")" = 644 ]'
chk "lock: your own layer stays writable"                    '[ "$(mode_of "$C/CUSTOMISATION.md")" = 644 ] && [ "$(mode_of "$C/wiki/index.md")" = 644 ]'
chk "lock: folders stay writable, so a pull cannot stop halfway" '[ -w "$C/.claude/skills/query" ] && [ -w "$C/.claude" ]'
chk "lock: the first git status is empty"                    '[ -z "$(git -C "$C" status --porcelain)" ]'
chk "lock: the four Obsidian files carry the mark"           '[ "$(git -C "$C" ls-files -v .obsidian | grep -c "^S ")" = 4 ]'
chk "lock: the post-merge hook is in place"                  '[ -x "$C/.git/hooks/post-merge" ] && grep -q "setup.sh --lock" "$C/.git/hooks/post-merge"'
printf '{ "changed": 1 }\n' > "$C/.obsidian/graph.json"
chk "lock: a change to a marked Obsidian file stays out of status" '[ -z "$(git -C "$C" status --porcelain)" ]'
printf '{ "x": 1 }\n' > "$C/.obsidian/graph.json"
state_of(){ core_modes; git -C "$C" ls-files -v .obsidian; hash_of "$C/.git/hooks/post-merge"; }
S12="$(state_of)"
( cd "$C" && env HOME="$ROOT/hm" bash setup.sh >/dev/null 2>&1 )
chk "lock: a second run changes nothing"                     '[ "$(state_of)" = "$S12" ]'
OUT12=$(cd "$C" && bash setup.sh --unlock 2>&1)
chk "unlock: says what it did"                               'echo "$OUT12" | grep -q "core unlocked: [0-9]* files writable"'
chk "unlock: restores the owner write bit only"              '[ "$(mode_of "$C/CLAUDE.md")" = 644 ] && [ "$(mode_of "$C/.claude/skills/query/run.sh")" = 755 ]'
( cd "$C" && bash setup.sh --lock >/dev/null 2>&1 )
chk "lock: --unlock then --lock round-trips"                 '[ "$(state_of)" = "$S12" ]'
chk "control: the state probe sees an unlocked core"         '( cd "$C" && bash setup.sh --unlock >/dev/null 2>&1 ); [ "$(state_of)" != "$S12" ]'
( cd "$C" && bash setup.sh --lock >/dev/null 2>&1 )
printf '# rules v2\n' > "$W/CLAUDE.md"; printf '# new\n' > "$W/.claude/skills/query/NEW.md"
( cd "$W" && $GIT add -A && $GIT commit -qm v2 && $GIT push -q ) >/dev/null 2>&1
env HOME="$ROOT/hm" git -C "$C" pull -q --ff-only >/dev/null 2>&1; RC12=$?
chk "pull: a plain git pull passes through locked files"     '[ "$RC12" = 0 ] && grep -q "v2" "$C/CLAUDE.md"'
chk "pull: the changed file is locked again"                 '[ "$(mode_of "$C/CLAUDE.md")" = 444 ]'
chk "pull: the new file is locked too"                       '[ "$(mode_of "$C/.claude/skills/query/NEW.md")" = 444 ]'
make_release
printf '#!/bin/sh\necho mine\n' > "$C/.git/hooks/post-merge"; chmod +x "$C/.git/hooks/post-merge"
HOOK12=$(hash_of "$C/.git/hooks/post-merge")
OUT12=$(cd "$C" && env HOME="$ROOT/hm" bash setup.sh 2>&1)
chk "hook: a post-merge hook of yours is left alone"         '[ "$(hash_of "$C/.git/hooks/post-merge")" = "$HOOK12" ]'
chk "hook: setup says so"                                    'echo "$OUT12" | grep -q "your own post-merge hook is left alone"'
chk "hook: the core still locks"                             '[ "$(mode_of "$C/CLAUDE.md")" = 444 ]'
make_release
rm -f "$C/.claude/core-paths"
OUT12=$(cd "$C" && env HOME="$ROOT/hm" bash setup.sh 2>&1); RC12=$?
chk "no list: the core stays unlocked and setup says so, exit 0" '[ "$RC12" = 0 ] && echo "$OUT12" | grep -q "core not locked — cannot read" && [ "$(mode_of "$C/CLAUDE.md")" = 644 ]'
make_release
printf '# only comments\n' > "$C/.claude/core-paths"
OUT12=$(cd "$C" && env HOME="$ROOT/hm" bash setup.sh 2>&1)
chk "empty list: the core stays unlocked and setup says so"  'echo "$OUT12" | grep -q "matches no tracked file" && [ "$(mode_of "$C/CLAUDE.md")" = 644 ]'
make_release
mkdir -p "$ROOT/stubbin"; printf '#!/bin/sh\nexit 1\n' > "$ROOT/stubbin/chmod"; /bin/chmod +x "$ROOT/stubbin/chmod"
OUT12=$(cd "$C" && env HOME="$ROOT/hm" PATH="$ROOT/stubbin:$PATH" bash setup.sh 2>&1); RC12=$?
chk "chmod fails: setup says the core is not fully locked, exit 0" '[ "$RC12" = 0 ] && echo "$OUT12" | grep -q "core not fully locked"'
chk "chmod fails: it never claims the lock"                  '! echo "$OUT12" | grep -q "✓ core locked"'
fresh; OUT12=$(cd "$ROOT" && bash setup.sh 2>&1); RC12=$?
chk "no git: setup says so and exits 0"                      '[ "$RC12" = 0 ] && echo "$OUT12" | grep -q "core not locked — this folder is not a git clone"'
make_release
mkdir -p "$C/inner"; cp "$PAY" "$C/inner/setup.sh"; chmod u+w "$C/inner/setup.sh"; printf 'x\n' > "$C/inner/.claude-core"; mkdir -p "$C/inner/.claude"; cp "$(dirname "$PAY")/core-paths.txt" "$C/inner/.claude/core-paths"
OUT12=$(cd "$C/inner" && env HOME="$ROOT/hm" bash setup.sh 2>&1)
chk "nested: a copy inside another repository locks nothing" 'echo "$OUT12" | grep -q "not a git clone" && [ "$(mode_of "$C/CLAUDE.md")" = 644 ]'

echo "== 13) kits: --enable and --disable round-trip your local settings =="
fresh; mkdir -p "$ROOT/.claude/hooks"
KITS="$ROOT/.claude/hooks/optional-hooks.json"; LOCAL="$ROOT/.claude/settings.local.json"
printf '%s\n' '{ "ingest-check": { "hooks": { "Stop": [ { "hooks": [ { "type": "command", "command": "a-check" } ] } ] } }, "hands-off": { "hooks": { "PreToolUse": [ { "matcher": "Bash", "hooks": [ { "type": "command", "command": "a-gate" } ] } ] } } }' > "$KITS"
same_json(){ python3 -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1])) == json.load(open(sys.argv[2])) else 1)' "$1" "$2"; }
OUT13=$(cd "$ROOT" && bash setup.sh --enable ingest-check 2>&1); RC13=$?
chk "kit: --enable exits 0 and says so"                      '[ "$RC13" = 0 ] && echo "$OUT13" | grep -q "ingest-check on"'
chk "kit: the entry is in the local settings"                'grep -q "a-check" "$LOCAL"'
( cd "$ROOT" && bash setup.sh --enable ingest-check >/dev/null 2>&1 )
chk "kit: a second --enable adds no second entry"            '[ "$(grep -c "a-check" "$LOCAL")" = 1 ]'
OUT13=$(cd "$ROOT" && bash setup.sh --disable ingest-check 2>&1)
chk "kit: --disable from no settings of yours leaves no file" '[ ! -e "$LOCAL" ] && echo "$OUT13" | grep -q "ingest-check off"'
printf '%s\n' '{ "permissions": { "allow": ["Bash(ls)"] }, "hooks": { "Stop": [ { "hooks": [ { "type": "command", "command": "my-own" } ] } ] } }' > "$LOCAL"
cp "$LOCAL" "$ROOT/local.was"
( cd "$ROOT" && bash setup.sh --enable ingest-check >/dev/null 2>&1; bash setup.sh --enable hands-off >/dev/null 2>&1 )
chk "kit: --enable keeps your own hook and permissions"      'grep -q "my-own" "$LOCAL" && grep -q "Bash(ls)" "$LOCAL" && grep -q "a-check" "$LOCAL" && grep -q "a-gate" "$LOCAL"'
chk "control: the same compare sees the enabled file differ" '! same_json "$LOCAL" "$ROOT/local.was"'
( cd "$ROOT" && bash setup.sh --disable hands-off >/dev/null 2>&1; bash setup.sh --disable ingest-check >/dev/null 2>&1 )
chk "kit: --disable round-trips your settings"               'same_json "$LOCAL" "$ROOT/local.was"'
printf '{ not json\n' > "$LOCAL"; HL=$(hash_of "$LOCAL")
OUT13=$(cd "$ROOT" && bash setup.sh --enable ingest-check 2>&1); RC13=$?
chk "kit: a malformed local file is refused, unchanged"      '[ "$RC13" = 2 ] && echo "$OUT13" | grep -q "not valid JSON" && [ "$(hash_of "$LOCAL")" = "$HL" ]'
rm -f "$LOCAL"
OUT13=$(cd "$ROOT" && bash setup.sh --enable no-such-kit 2>&1); RC13=$?
chk "kit: an unknown kit is refused and the known ones named" '[ "$RC13" = 1 ] && echo "$OUT13" | grep -q "no kit named no-such-kit" && echo "$OUT13" | grep -q "hands-off"'
rm -f "$KITS"
OUT13=$(cd "$ROOT" && bash setup.sh --enable hands-off 2>&1); RC13=$?
chk "kit: a copy with no kit file refuses in words"          '[ "$RC13" = 1 ] && echo "$OUT13" | grep -q "offers no kit" && [ ! -e "$LOCAL" ]'
OUT13=$(cd "$ROOT" && bash setup.sh --enable 2>&1); RC13=$?
chk "kit: --enable with no name prints the usage"            '[ "$RC13" = 1 ] && echo "$OUT13" | grep -q "usage: bash setup.sh --enable"'
# A release changed a kit's words, so the entry installed earlier no longer equals its definition.
printf '%s\n' '{ "ingest-check": { "hooks": { "Stop": [ { "hooks": [ { "type": "command", "command": "sh \".claude/hooks/a-check.sh\" --v2", "timeout": 10 } ] } ] } }, "hands-off": { "hooks": { "PreToolUse": [ { "matcher": "Bash", "hooks": [ { "type": "command", "command": "sh \".claude/hooks/a-gate.py\" --v2" } ] } ] } } }' > "$KITS"
kit_local(){ printf '{ "permissions": { "allow": ["Bash(ls)"] }, "hooks": { "Stop": [ %s, { "hooks": [ { "type": "command", "command": "my-own" } ] } ] } }\n' "$1" > "$LOCAL"; }
one_hook(){ printf '{ "hooks": [ { "type": "command", "command": "sh \\".claude/hooks/%s\\"" } ] }' "$1"; }
disable_check(){ OUT13=$(cd "$ROOT" && bash setup.sh --disable ingest-check 2>&1); RC13=$?; }
kit_local "$(one_hook a-check.sh)"
chk "fixture: the older entry is in the local settings"      'python3 -c "import json, sys; json.load(open(sys.argv[1]))" "$LOCAL" && grep -q "a-check" "$LOCAL"'
HL=$(hash_of "$LOCAL"); disable_check
chk "kit: after an upgrade --disable refuses an older entry, unchanged" '[ "$RC13" = 1 ] && echo "$OUT13" | grep -q "older or edited kit entries may remain" && [ "$(hash_of "$LOCAL")" = "$HL" ]'
kit_local '{ "hooks": [ { "type": "command", "command": "sh \".claude/hooks/a-check.sh\" --v2", "timeout": 10 } ] }'
disable_check
chk "kit: an entry equal to its definition goes"             '[ "$RC13" = 0 ] && echo "$OUT13" | grep -q "ingest-check off" && ! grep -q "a-check" "$LOCAL"'
chk "kit: and keeps your own hook and permissions"           'grep -q "my-own" "$LOCAL" && grep -q "Bash(ls)" "$LOCAL"'
HL=$(hash_of "$LOCAL"); disable_check
chk "kit: with your own hook left, a kit that is off says so" '[ "$RC13" = 0 ] && echo "$OUT13" | grep -q "already off" && [ "$(hash_of "$LOCAL")" = "$HL" ]'
kit_local '{ "hooks": [ { "type": "command", "command": "sh \".claude/hooks/a-check.sh\"; sh .claude/hooks/my-notes.sh" } ] }'
HL=$(hash_of "$LOCAL"); disable_check
chk "kit: one command that runs a kit hook and one of yours is refused, unchanged" '[ "$RC13" = 1 ] && echo "$OUT13" | grep -q "older or edited kit entries may remain" && [ "$(hash_of "$LOCAL")" = "$HL" ]'
kit_local '{ "hooks": [ { "type": "command", "command": "sh \".claude/hooks/a-check.sh\" --v2", "timeout": 10 } ] }, { "hooks": [ { "type": "command", "command": "sh \".claude/hooks/a-check-old-name.sh\"" } ] }'
HL=$(hash_of "$LOCAL"); disable_check
chk "kit: a current entry beside an unlisted hook file is refused whole, unchanged" '[ "$RC13" = 1 ] && echo "$OUT13" | grep -q "older or edited kit entries may remain" && [ "$(hash_of "$LOCAL")" = "$HL" ]'
kit_local '{ "hooks": [ { "type": "command", "command": "sh \".claude/hooks/a-check.sh\"" }, { "type": "command", "command": "my-wrapper" } ] }'
HL=$(hash_of "$LOCAL"); disable_check
chk "kit: an entry that also runs something of yours is refused, unchanged" '[ "$RC13" = 1 ] && echo "$OUT13" | grep -q "older or edited kit entries may remain" && [ "$(hash_of "$LOCAL")" = "$HL" ]'
kit_local "$(one_hook a-check-old-name.sh)"
HL=$(hash_of "$LOCAL"); disable_check
chk "kit: a hook file no kit lists is never reported off"    '[ "$RC13" = 1 ] && echo "$OUT13" | grep -q "older or edited kit entries may remain" && [ "$(hash_of "$LOCAL")" = "$HL" ]'
kit_local "$(one_hook my-hook.sh)"
HL=$(hash_of "$LOCAL"); disable_check
chk "control: your own my- hook never reads as an older kit's" '[ "$RC13" = 0 ] && echo "$OUT13" | grep -q "already off" && [ "$(hash_of "$LOCAL")" = "$HL" ]'
kit_local "$(one_hook a-gate.py)"
HL=$(hash_of "$LOCAL"); disable_check
chk "control: another kit's entry stays when this one goes off" '[ "$RC13" = 0 ] && echo "$OUT13" | grep -q "already off" && [ "$(hash_of "$LOCAL")" = "$HL" ]'
rm -f "$LOCAL"

echo "== 14) form-entry: a template the person installs, and generic text =="
TPL="$(dirname "$PAY")/automode-form-entry.template.json"
chk "template: it parses"                                    'python3 -c "import json, sys; json.load(open(sys.argv[1]))" "$TPL"'
chk "template: both lists keep the default rules"            'python3 -c "import json, sys; a = json.load(open(sys.argv[1]))[\"autoMode\"]; sys.exit(0 if a[\"allow\"][0] == a[\"environment\"][0] == \"\$defaults\" else 1)" "$TPL"'
chk "template: it holds the three places a user fills"       'grep -q "{{WHO_YOU_ARE}}" "$TPL" && grep -q "{{YOUR_SITES}}" "$TPL" && grep -q "{{YOUR_SIGN_IN_PAGES}}" "$TPL"'
# Assembled, so this file itself stays free of them. The list is the owner rule's own personal words.
PERSONAL="$(printf '%s|' 'Ox''ford' 'ox''.ac.uk' 'DPh''il' 'Univ''ersity' 'ai''Myth' ' hims''elf' ' h''is ' ' h''e ')"; PERSONAL="${PERSONAL%|}"
chk "template: it carries no personal string"                '! grep -qE "$PERSONAL" "$TPL"'
chk "control: the same probe hits a planted personal string" 'printf "a student at Ox""ford\n" | grep -qE "$PERSONAL"'
fresh; mkdir -p "$ROOT/.claude/skills/export-template/payload" "$ROOT/hm/.claude"
cp "$TPL" "$ROOT/.claude/skills/export-template/payload/"
SET="$ROOT/hm/.claude/settings.json"; printf '{\n  "model": "opus"\n}\n' > "$SET"; chmod 600 "$SET"; HS14=$(hash_of "$SET")
OUT14=$(cd "$ROOT" && env HOME="$ROOT/hm" bash setup.sh --enable form-entry 2>&1 </dev/null); RC14=$?
chk "form-entry: with no terminal it refuses"                '[ "$RC14" = 1 ] && echo "$OUT14" | grep -q "requires manual installation of the supplied template"'
chk "form-entry: the settings file stays byte-identical"     '[ "$(hash_of "$SET")" = "$HS14" ]'
chk "form-entry: and no backup appeared"                     '[ "$(ls "$ROOT/hm/.claude" | grep -c bak)" = 0 ]'
( cd "$ROOT" && env HOME="$ROOT/hm" bash setup.sh </dev/null >/dev/null 2>&1 )
chk "form-entry: plain setup never installs it"              '[ "$(hash_of "$SET")" = "$HS14" ]'
# A terminal shows an interaction, not who authorised it, so a pseudo-terminal typing yes gets the same refusal.
TERM_DRIVER="$ROOT/term.py"
cat > "$TERM_DRIVER" <<'TERM_FIXTURE'
import os, pty, sys, time
home, root, *answers = sys.argv[1:]
pid, fd = pty.fork()
if pid == 0:
    os.chdir(root)
    os.environ["HOME"] = home
    os.execvp("bash", ["bash", "setup.sh", "--enable", "form-entry"])
out, left, last = b"", list(answers), time.time()
while True:
    try:
        chunk = os.read(fd, 4096)
    except OSError:
        break
    if not chunk:
        break
    out += chunk
    if left and (chunk.rstrip().endswith(b"?") or chunk.rstrip().endswith(b":")):
        os.write(fd, left.pop(0).encode() + b"\n")
_, status = os.waitpid(pid, 0)
sys.stdout.write(out.decode("utf-8", "replace"))
sys.exit(os.WEXITSTATUS(status))
TERM_FIXTURE
OUT14=$(python3 "$TERM_DRIVER" "$ROOT/hm" "$ROOT" "a tester" "the forms site" "the sign-in page" "yes" 2>&1); RC14=$?
chk "form-entry: a terminal and a typed yes are refused the same" '[ "$RC14" = 1 ] && echo "$OUT14" | grep -q "requires manual installation of the supplied template"'
chk "form-entry: and the settings file stays byte-identical"  '[ "$(hash_of "$SET")" = "$HS14" ] && [ "$(ls "$ROOT/hm/.claude" | grep -c bak)" = 0 ]'
chk "form-entry: the refusal names the template and the undo" 'echo "$OUT14" | grep -q "payload/automode-form-entry.template.json" && echo "$OUT14" | grep -q "claude auto-mode reset"'
chk "form-entry: no line of setup.sh writes the rule"        '! grep -q "\"autoMode\"\]" "$PAY" && ! grep -q "settings.json.bak\|shutil.copy2(settings" "$PAY"'
chk "control: the same probe hits a line that writes the rule" 'printf "current[\"autoMode\"] = section\nshutil.copy2(settings, backup)\n" > "$ROOT/writes.txt" && grep -q "\"autoMode\"\]" "$ROOT/writes.txt" && grep -q "settings.json.bak\|shutil.copy2(settings" "$ROOT/writes.txt"'
OUT14=$(cd "$ROOT" && bash setup.sh --disable form-entry 2>&1)
chk "form-entry: --disable sends you to the undo, writing nothing" 'echo "$OUT14" | grep -q "claude auto-mode reset" && [ "$(hash_of "$SET")" = "$HS14" ]'

echo "== 15) --backup: your layer leaves by its own git folder, and the clone stays a clone =="
make_release
( cd "$C" && env HOME="$ROOT/hm" bash setup.sh >/dev/null 2>&1 )
printf '# my note\n' > "$C/wiki/my-note.md"; mkdir -p "$C/.claude/skills/my-own"; printf '# mine\n' > "$C/.claude/skills/my-own/SKILL.md"
printf 'junk\n' > "$C/wiki/.DS_Store"
$GIT init -q --bare "$ROOT/private.git"
GIT_HEAD_BEFORE=$(git -C "$C" rev-parse HEAD); INDEX_BEFORE=$(hash_of "$C/.git/index"); STATUS_BEFORE=$(git -C "$C" status --porcelain)
backup(){ env HOME="$ROOT/hm" GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t LLM_WIKI_STORE="$ROOT/store" bash "$C/setup.sh" --backup "$@" 2>&1; }
OUT15=$(backup "$ROOT/private.git"); RC15=$?
in_backup(){ git -C "$ROOT/private.git" ls-tree -r main --name-only | grep -qxF -- "$1"; }
chk "backup: exits 0 and names its folder"                   '[ "$RC15" = 0 ] && echo "$OUT15" | grep -q "your layer is backed up"'
chk "backup: a wiki page reaches the private repository"     'in_backup wiki/my-note.md'
chk "backup: your preferences reach it"                      'in_backup CUSTOMISATION.md'
chk "backup: your own skill reaches it"                      'in_backup .claude/skills/my-own/SKILL.md'
chk "backup: a core file stays out"                          '! in_backup CLAUDE.md'
chk "backup: junk stays out"                                 '! in_backup wiki/.DS_Store'
chk "control: the same probe finds a file that is there"     'in_backup wiki/index.md'
chk "backup: the clone gained no commit"                     '[ "$(git -C "$C" rev-parse HEAD)" = "$GIT_HEAD_BEFORE" ]'
chk "backup: the clone's index is byte-identical"            '[ "$(hash_of "$C/.git/index")" = "$INDEX_BEFORE" ]'
chk "backup: the clone's status is unchanged"                '[ "$(git -C "$C" status --porcelain)" = "$STATUS_BEFORE" ]'
chk "backup: the clone gained no remote"                     '[ "$(git -C "$C" remote)" = origin ]'
chk "backup: the backup's git folder sits outside the vault" '[ -n "$(ls -d "$ROOT"/store/backups/*.git)" ] && [ ! -e "$C/.git/backup" ]'
printf '# second note\n' > "$C/wiki/second.md"; rm -f "$C/wiki/my-note.md"
OUT15=$(backup); RC15=$?
chk "backup: a later run needs no URL and takes the change"  '[ "$RC15" = 0 ] && in_backup wiki/second.md'
chk "backup: a page you deleted leaves the next backup"      '! in_backup wiki/my-note.md'
printf '# rules v2\n' > "$W/CLAUDE.md"
( cd "$W" && $GIT add -A && $GIT commit -qm v2 && $GIT tag -a v1.1.0 -m v2 && $GIT push -q --tags origin main ) >/dev/null 2>&1
git -C "$C" fetch -q --tags >/dev/null 2>&1
env HOME="$ROOT/hm" git -C "$C" merge -q --ff-only v1.1.0 >/dev/null 2>&1; RC15=$?
chk "backup: after a backup the update still fast-forwards"  '[ "$RC15" = 0 ] && grep -q "v2" "$C/CLAUDE.md"'
OUT15=$(backup "$UP"); RC15=$?
chk "backup: the clone's own remote is refused"              '[ "$RC15" = 1 ] && echo "$OUT15" | grep -q "your notes never go there"'
OUT15=$(backup "$(printf '%s' "$UP" | sed 's/\.git$//')/"); RC15=$?
chk "backup: that address in another spelling is refused too" '[ "$RC15" = 1 ] && echo "$OUT15" | grep -q "your notes never go there"'
chk "control: the private address is not this clone's remote" '[ "$(git -C "$ROOT/private.git" rev-parse --is-bare-repository)" = true ] && [ "$(git -C "$C" remote get-url origin)" != "$ROOT/private.git" ]'
OUT15=$(env HOME="$ROOT/nobackuphome" LLM_WIKI_STORE="$ROOT/store2" bash "$C/setup.sh" --backup 2>&1); RC15=$?
chk "backup: the first run with no URL prints the usage"     '[ "$RC15" = 1 ] && echo "$OUT15" | grep -q "usage: bash setup.sh --backup"'

echo "== 16) every rule shipped text cites from the preference file exists in the seed =="
# Shipped text points at the seeded CUSTOMISATION.md by a bullet's name. A name it cites that the seed
# lacks points a public user at nothing. The names are read from the shipped text after the export's
# strip, never listed here, so a new citation is checked with no edit to this file.
cited_names(){ python3 -B - "${2:-$VAULT}" "$1" "$(dirname "$PAY")/../strip_vault_local.py" <<'CITED'
import os, re, subprocess, sys
vault, seed_path, strip = sys.argv[1:4]
seed = open(seed_path, encoding="utf-8").read()
names = re.findall(r"^\s*- \*\*([^*]+?)[.:]?\*\*", seed, re.M) + re.findall(r"^#+ (.+)$", seed, re.M)
files = [os.path.join(vault, "CLAUDE.md"), os.path.join(vault, "MANUAL.md")]
for root, dirs, entries in os.walk(os.path.join(vault, ".claude", "skills")):
    dirs[:] = [d for d in dirs if d not in ("__pycache__", "professor-loop", "payload") and not d.startswith("my-")]
    files += [os.path.join(root, n) for n in entries if n.endswith((".md", ".py")) and not n.startswith("test_")]
quoted = re.compile(r"CUSTOMISATION\.md(?:'s|,)?(?: [A-Za-z]+){0,3}[ ,(]+[\"“]([^\"”\n]{3,70})[\"”]")
bare = re.compile(r"CUSTOMISATION\.md's ([A-Z][\w-]+)(?: posture)? (?:rule|bullet)")
cited = {}
for path in files:
    run = subprocess.run([sys.executable, "-B", strip, "--stdout", path], capture_output=True, text=True, errors="replace")
    if run.returncode:
        print("PROBE FAILED: the strip could not read %s" % path)
        sys.exit(2)
    text = re.sub(r"\s*\n\s*", " ", run.stdout)
    for pattern in (quoted, bare):
        for match in pattern.finditer(text):
            cited.setdefault(match.group(1), os.path.relpath(path, vault))
if len(cited) < 5:
    print("PROBE FAILED: only %d cited names found, so the citation pattern no longer reads the shipped text" % len(cited))
    sys.exit(2)
missing = sorted(n for n in cited if not any(n in have for have in names))
for name in missing:
    print("%s: cites '%s'" % (cited[name], name))
print("cited %d, missing %d" % (len(cited), len(missing)))
sys.exit(1 if missing else 0)
CITED
}
fresh; ( cd "$ROOT" && bash setup.sh >/dev/null 2>&1 )
OUT16=$(cited_names "$ROOT/$CUST"); RC16=$?
chk "cited: every name shipped text cites has its place in the seed" '[ "$RC16" = 0 ]'
[ "$RC16" = 0 ] || echo "$OUT16" | sed 's/^/      /'
python3 -c 'import re, sys; p = sys.argv[1]; t = open(p, encoding="utf-8").read(); n = re.sub(r"(?m)^- \*\*Transcripts\*\*:.*\n", "", t); assert n != t; open(p, "w", encoding="utf-8").write(n)' "$ROOT/$CUST"
OUT16=$(cited_names "$ROOT/$CUST"); RC16=$?
chk "cited: a seed with a cited name removed fails, naming it" '[ "$RC16" = 1 ] && echo "$OUT16" | grep -q "cites .Transcripts."'
fresh; ( cd "$ROOT" && bash setup.sh >/dev/null 2>&1 )
python3 -c 'import re, sys; p = sys.argv[1]; t = open(p, encoding="utf-8").read(); n = re.sub(r"(?m)^- \*\*New features: search first, discuss first\*\*:.*\n", "", t); assert n != t; open(p, "w", encoding="utf-8").write(n)' "$ROOT/$CUST"
OUT16=$(cited_names "$ROOT/$CUST"); RC16=$?
chk "cited: a citation with no possessive is read, and its removal fails" '[ "$RC16" = 1 ] && echo "$OUT16" | grep -q "cites .New features: search first, discuss first."'
# A small tree of its own, since the suite never plants a file in the vault it reads.
FV="$ROOT/citing"; mkdir -p "$FV/.claude/skills/ordinary" "$FV/.claude/skills/my-private"
printf -- '- **Aa rule**: x\n- **Bb rule**: x\n- **Cc rule**: x\n- **Dd rule**: x\n- **Ee rule**: x\n' > "$ROOT/cite-seed.md"
printf 'CUSTOMISATION.md "Aa rule", CUSTOMISATION.md "Bb rule", CUSTOMISATION.md "Cc rule", CUSTOMISATION.md "Dd rule", CUSTOMISATION.md "Ee rule".\n' > "$FV/CLAUDE.md"
printf '# manual\n' > "$FV/MANUAL.md"; printf '# ordinary\n' > "$FV/.claude/skills/ordinary/SKILL.md"
printf 'See CUSTOMISATION.md "Zz private rule".\n' > "$FV/.claude/skills/my-private/SKILL.md"
OUT16=$(cited_names "$ROOT/cite-seed.md" "$FV"); RC16=$?
chk "cited: a my- skill never ships, so its citation is not read" '[ "$RC16" = 0 ] && ! echo "$OUT16" | grep -q "Zz private"'
printf 'NAME = "CUSTOMISATION.md" OTHER = "not a citation"\n' > "$FV/.claude/skills/ordinary/tool.py"
OUT16=$(cited_names "$ROOT/cite-seed.md" "$FV"); RC16=$?
chk "cited: a file name in a quoted string is no citation"   '[ "$RC16" = 0 ]'
cp "$FV/.claude/skills/my-private/SKILL.md" "$FV/.claude/skills/ordinary/SKILL.md"
OUT16=$(cited_names "$ROOT/cite-seed.md" "$FV"); RC16=$?
chk "control: the same citation in a shipped skill fails, naming it" '[ "$RC16" = 1 ] && echo "$OUT16" | grep -q "cites .Zz private rule."'

echo "== 17) the last leg: setup's verbs move no byte of a file, and the same check sees one that moved =="
make_release
( cd "$C" && env HOME="$ROOT/hm" bash setup.sh >/dev/null 2>&1 )
printf '# my note\n' > "$C/wiki/my-note.md"
$GIT init -q --bare "$ROOT/private2.git"
tree_sums(){ python3 -B - "$C" <<'SUMS'
import hashlib, os, sys
root = sys.argv[1]
for folder, dirs, files in os.walk(root):
    dirs[:] = sorted(d for d in dirs if d != ".git")
    for name in sorted(files):
        path = os.path.join(folder, name)
        with open(path, "rb") as fh:
            print(hashlib.sha256(fh.read()).hexdigest(), os.path.relpath(path, root))
SUMS
}
M17="$(tree_sums)"
RC17=""
for verb in "" --lock --unlock --lock "--backup $ROOT/private2.git"; do
  ( cd "$C" && env HOME="$ROOT/hm" LLM_WIKI_STORE="$ROOT/store17" GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t bash setup.sh $verb >/dev/null 2>&1 ); RC17="$RC17$?"
done
chk "last leg: control: the manifest lists files"            '[ "$(printf "%s\n" "$M17" | grep -c .)" -ge 20 ]'
chk "last leg: every verb exited 0"                          '[ "$RC17" = 00000 ]'
chk "last leg: no file in the tree moved a byte"             '[ "$(tree_sums)" = "$M17" ]'
chk "last leg: the core is locked at the end"                '[ "$(mode_of "$C/CLAUDE.md")" = 444 ]'
printf 'x' >> "$C/wiki/my-note.md"
chk "control: one byte changed beside the notes is caught"   '[ "$(tree_sums)" != "$M17" ]'
printf '# my note\n' > "$C/wiki/my-note.md"
chk "control: put back, the manifest matches again"          '[ "$(tree_sums)" = "$M17" ]'
chmod u+w "$C/.claude/skills/query/SKILL.md"; printf 'x' >> "$C/.claude/skills/query/SKILL.md"; chmod a-w "$C/.claude/skills/query/SKILL.md"
chk "control: one byte changed in a locked core file, its mode put back, is caught" '[ "$(tree_sums)" != "$M17" ] && [ "$(mode_of "$C/.claude/skills/query/SKILL.md")" = 444 ]'

echo
echo "================  RESULT: $PASS passed, $FAIL failed  ================"
rm -rf "$ROOT"
[ "$FAIL" -eq 0 ]
