#!/usr/bin/env bash
# test_export_template.sh — isolated, self-contained tests for export_template.sh.
# Builds a throwaway fake vault + fake git remote under $TMPDIR and exercises every mode.
# NEVER touches the real vault. Run:  bash test_export_template.sh
# Premise guard: this suite needs process substitution. Invoked as `sh <file>` it dies mid-run
# with a raw syntax error and exit 2, and a caller grepping the output for "FAIL" then reads zero
# and calls it green. Probe the CAPABILITY, not the shell name: on macOS
# /bin/sh IS bash, so $BASH_VERSION is set while POSIX mode still disables the feature.
if ! (eval 'cat < <(echo probe)') >/dev/null 2>&1; then
  echo "ERROR: process substitution unavailable (POSIX mode?) — run: bash $0"; exit 2
fi

set -uo pipefail

REALSKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # the real export-template skill (under test)
ROOT="${TMPDIR:-/tmp}/etest.$$"
V="$ROOT/vault"
REMOTE="$ROOT/remote.git"
CLONE="$ROOT/clone"
SCRIPT="$V/.claude/skills/export-template/export_template.sh"
GIT="git -c user.email=t@t -c user.name=test -c commit.gpgsign=false -c init.defaultBranch=main"
EXCLUDED_SKILL="professor-loop"   # the one skill copy_framework() leaves out of build and push (v0.9.6)

PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "    ok   — $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL   — $1"; }
chk(){ if eval "$2" >/dev/null 2>&1; then ok "$1"; else no "$1"; fi; }
hash_of(){ md5 -q "$1" 2>/dev/null || md5sum "$1" 2>/dev/null | cut -d' ' -f1; }

build_fake_vault(){
  rm -rf "$ROOT"
  mkdir -p "$V/.claude/skills" "$V/.obsidian" "$V/wiki/sources" "$V/raw" "$V/assets" "$V/output"
  printf '# CLAUDE (test contract)\n' > "$V/CLAUDE.md"
  printf '# Manual (test)\n' > "$V/MANUAL.md"
  printf '# README (test)\n\n![graph](assets/framework_demo.png)\n\nSee the [Manual](MANUAL.md).\n\nLicence: [LICENSE](LICENSE.md)\n' > "$V/README.md"
  printf 'FAKE-PNG-BYTES\n' > "$V/assets/framework_demo.png"      # README screenshot — force-tracked
  printf 'LOCAL-USER-MEDIA\n' > "$V/assets/my_photo.png"          # user media — must NOT ship
  printf 'MIT License (test)\n' > "$V/LICENSE.md"
  printf 'cff-version: 1.2.0\ntitle: test\n' > "$V/CITATION.cff"
  printf '# Contributing (test — legacy leftover, must never ship)\n' > "$V/CONTRIBUTING.md"
  for f in app core-plugins appearance; do printf '{\n  "x": 1\n}\n' > "$V/.obsidian/$f.json"; done
  printf '{ "colorGroups": [ {"query":"path:wiki/models/","color":1} ], "showOrphans": true, "scale": 0.5, "close": true, "search": "q", "collapse-filter": true }\n' > "$V/.obsidian/graph.json"
  for s in ingest query lint oldskill output gather newskill; do  # 'newskill' tests dynamic discovery
    mkdir -p "$V/.claude/skills/$s"; printf '# %s skill\n' "$s" > "$V/.claude/skills/$s/SKILL.md"
  done
  mkdir -p "$V/.claude/skills/$EXCLUDED_SKILL"   # present in the vault, never shipped
  printf '# excluded skill\n' > "$V/.claude/skills/$EXCLUDED_SKILL/SKILL.md"
  cp -R "$REALSKILL" "$V/.claude/skills/export-template"
  chmod -R u+w "$V/.claude/skills/export-template"   # a copy of a locked core is read-only, and these legs write in it
  # the calendar's shipped hook files, a hook that stays in the vault, the vault's own settings, personal calendars
  mkdir -p "$V/.claude/hooks"
  printf '#!/usr/bin/env python3\nprint("digest")\n' > "$V/.claude/hooks/calendar-digest.py"
  printf '#!/bin/sh\necho suite\n'                   > "$V/.claude/hooks/test_calendar_digest.sh"
  printf '#!/bin/sh\necho local\n'                   > "$V/.claude/hooks/local-only-hook.sh"
  printf '{ "vault": "own settings" }\n'             > "$V/.claude/settings.json"
  printf '# CALENDAR\n- [ ] 2026-01-01 · owner private item\n' > "$V/CALENDAR.md"
  printf '# CALENDAR-done\n'                          > "$V/CALENDAR-done.md"
  # a 'delegate' skill shaped like the real one: a python wrapper, a JSON routing table, a template
  # and a nested slice directory — the shapes the thin-lane path added under .claude/skills/ (2026-09-04).
  # Phase 16 checks they reach the build and stay committable; the skill count above rises with it.
  mkdir -p "$V/.claude/skills/delegate/templates" "$V/.claude/skills/delegate/lane-home-src/compile-core"
  printf '# delegate skill\n'                        > "$V/.claude/skills/delegate/SKILL.md"
  printf '#!/usr/bin/env python3\nprint("wrapper")\n' > "$V/.claude/skills/delegate/lane.py"
  printf '#!/usr/bin/env python3\nprint("fence")\n'   > "$V/.claude/skills/delegate/lane-fence.py"
  printf '{ "schema": 2, "classes": { "writer": { "layer": "core" } } }\n' > "$V/.claude/skills/delegate/routing.json"
  printf '# lane core\n'                              > "$V/.claude/skills/delegate/templates/lane-core.md"
  printf '# compile-core slice\n'                     > "$V/.claude/skills/delegate/lane-home-src/compile-core/SKILL.md"
  # "knowledge" that must NEVER ship or be touched by pull
  printf '# secret note\npersonal data here\n' > "$V/wiki/sources/secret.md"
  printf 'raw source\n' > "$V/raw/source1.md"
  mkdir -p "$V/wiki/user"; printf -- '---\ntitle: "Customisation"\ntype: user\n---\nowner personal prefs\n' > "$V/CUSTOMISATION.md"  # personal config — must NEVER ship
  printf -- '---\ntitle: "Customisation definitions"\n---\nowner personal role defs\n' > "$V/CUSTOMISATION-definitions.md"  # on-demand half — must NEVER ship
  printf '# IDEAS\n- owner private idea\n' > "$V/IDEAS.md"   # personal scratchpad — must NEVER ship
  mkdir -p "$V/attic"; printf '# Attic Manifest\n- [2026-01-01] [[old-note]] retired\n' > "$V/attic/MANIFEST.md"  # cold storage — must NEVER ship
}

setup_published(){   # fake vault + bare remote + clone holding the published framework
  build_fake_vault
  $GIT init -q --bare "$REMOTE"
  $GIT clone -q "$REMOTE" "$CLONE" 2>/dev/null
  bash "$SCRIPT" --push "$CLONE" >/dev/null 2>&1
  ( cd "$CLONE" && $GIT add -A && $GIT commit -qm init && $GIT push -qu origin main ) >/dev/null 2>&1
  # Use the published skill as this synthetic round-trip baseline; the real skill is read-only.
  cp -R "$CLONE/.claude/skills/export-template/." "$V/.claude/skills/export-template/"
}

[ -f "$REALSKILL/export_template.sh" ] || { echo "cannot find export_template.sh next to this test"; exit 2; }

echo "== Phase 1: fresh build =="
build_fake_vault
BUILT="$ROOT/built"
bash "$SCRIPT" "$BUILT" >/dev/null 2>&1
chk "build: README present"                 '[ -f "$BUILT/README.md" ]'
chk "build: README sourced from vault root" 'diff -q "$V/README.md" "$BUILT/README.md"'
chk "build: assets/ screenshot present"     '[ -f "$BUILT/assets/framework_demo.png" ]'
chk "build: LICENSE.md present"             '[ -f "$BUILT/LICENSE.md" ]'
chk "build: LICENSE.md sourced from root"   'diff -q "$V/LICENSE.md" "$BUILT/LICENSE.md"'
chk "build: no legacy no-ext LICENSE"       '[ ! -f "$BUILT/LICENSE" ]'
chk "build: CONTRIBUTING NOT shipped (retired)" '[ ! -f "$BUILT/CONTRIBUTING.md" ]'
chk "build: .gitignore present"             '[ -f "$BUILT/.gitignore" ]'
chk "build: setup.sh present + executable"  '[ -x "$BUILT/setup.sh" ]'
chk "build: 9 skills shipped (auto-discovered, the one exclusion left out)" '[ "$(ls "$BUILT/.claude/skills" | wc -l | tr -d " ")" = 9 ]'
chk "build: the excluded skill is NOT shipped"   '[ ! -e "$BUILT/.claude/skills/$EXCLUDED_SKILL" ]'
chk "build: the excluded skill stays in the vault" '[ -f "$V/.claude/skills/$EXCLUDED_SKILL/SKILL.md" ]'
chk "control: export_template.sh skips exactly this skill" "grep -qF '[ \"\$s\" = $EXCLUDED_SKILL ] && continue' \"\$REALSKILL/export_template.sh\""
chk "build: NEW skill auto-shipped (dynamic)"   '[ -d "$BUILT/.claude/skills/newskill" ]'
chk "build: export-template IS shipped"     '[ -f "$BUILT/.claude/skills/export-template/export_template.sh" ]'
chk "build: export-template payload shipped" '[ -d "$BUILT/.claude/skills/export-template/payload/example" ]'
chk "build: no legacy docs/ folder"         '[ ! -d "$BUILT/docs" ]'
chk "build: user media NOT shipped"         '[ ! -f "$BUILT/assets/my_photo.png" ]'
chk "build: seed demo shipped"             '[ -d "$BUILT/examples/seed" ]'
chk "build: wiki ships empty"               '[ -z "$(find "$BUILT/wiki" -type f ! -name .gitkeep)" ]'
chk "build: raw ships empty"                '[ -z "$(find "$BUILT/raw" -type f ! -name .gitkeep)" ]'
chk "build: NO knowledge files shipped"     '[ ! -e "$BUILT/wiki/sources/secret.md" ] && [ ! -e "$BUILT/raw/source1.md" ]'
chk "build: personal Customisation NOT shipped" '[ ! -e "$BUILT/CUSTOMISATION.md" ]'
chk "build: personal Customisation-definitions NOT shipped" '[ ! -e "$BUILT/CUSTOMISATION-definitions.md" ]'
chk "build: shipped setup.sh seeds Customisation" 'grep -q mk_custom "$BUILT/setup.sh"'
chk "build: shipped setup.sh seeds the definitions half" 'grep -q mk_custom_defs "$BUILT/setup.sh"'
chk "build: shipped gitignore ignores both halves" 'grep -qxF "/CUSTOMISATION-definitions.md" "$REALSKILL/payload/gitignore.txt"'
chk "build: personal IDEAS.md NOT shipped"      '[ ! -e "$BUILT/IDEAS.md" ]'
chk "build: shipped setup.sh seeds IDEAS"       'grep -q mk_ideas "$BUILT/setup.sh"'
chk "build: the calendar hook ships"            '[ -f "$BUILT/.claude/hooks/calendar-digest.py" ]'
chk "build: its suite ships"                    '[ -f "$BUILT/.claude/hooks/test_calendar_digest.sh" ]'
chk "build: a vault-only hook does NOT ship"    '[ ! -e "$BUILT/.claude/hooks/local-only-hook.sh" ]'
chk "build: settings are the payload's plus the generated deny rules" 'python3 -c "import json, sys; a = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2])); b.pop(\"permissions\"); sys.exit(0 if a == b else 1)" "$REALSKILL/payload/settings.json" "$BUILT/.claude/settings.json"'
chk "build: the vault's own settings NOT shipped" '! grep -q "own settings" "$BUILT/.claude/settings.json"'
chk "build: personal CALENDAR.md NOT shipped"   '[ ! -e "$BUILT/CALENDAR.md" ]'
chk "build: personal CALENDAR-done.md NOT shipped" '[ ! -e "$BUILT/CALENDAR-done.md" ]'
chk "build: shipped gitignore ignores both calendars" 'grep -qxF "/CALENDAR.md" "$REALSKILL/payload/gitignore.txt" && grep -qxF "/CALENDAR-done.md" "$REALSKILL/payload/gitignore.txt"'
chk "build: shipped setup.sh seeds the calendar" 'grep -q mk_calendar "$BUILT/setup.sh"'
chk "build: shipped setup.sh seeds the lifecycle register" 'grep -q mk_lifecycle "$BUILT/setup.sh"'
chk "build: publish allowlist ships with skill" '[ -f "$BUILT/.claude/skills/export-template/publish-allowlist.md" ]'
chk "build: attic contents NOT shipped"         '[ ! -e "$BUILT/attic/MANIFEST.md" ]'
chk "build: attic skeleton ships (.gitkeep)"    '[ -f "$BUILT/attic/.gitkeep" ]'
chk "build: shipped setup.sh seeds attic"       'grep -q mk_attic "$BUILT/setup.sh"'
chk "build: no __pycache__ shipped"         '[ -z "$(find "$BUILT" -name __pycache__)" ]'
chk "build: no .DS_Store shipped"           '[ -z "$(find "$BUILT" -name .DS_Store)" ]'
chk "build: graph.json keeps colorGroups"   'grep -q colorGroups "$BUILT/.obsidian/graph.json"'
chk "build: graph.json strips view-state"   '! grep -qE "scale|close|search|collapse-" "$BUILT/.obsidian/graph.json"'
( cd "$BUILT" && $GIT init -q && $GIT add -A ) >/dev/null 2>&1
chk "git: wiki content ignored"             '( cd "$BUILT" && git check-ignore -q wiki/sources/x.md )'
chk "git: raw content ignored"              '( cd "$BUILT" && git check-ignore -q raw/x.md )'
chk "git: output content ignored"           '( cd "$BUILT" && git check-ignore -q output/y.md )'
chk "git: attic content ignored"            '( cd "$BUILT" && git check-ignore -q attic/z.md )'
chk "git: README tracked"                   '( cd "$BUILT" && git ls-files | grep -qx README.md )'
chk "git: CLAUDE tracked"                   '( cd "$BUILT" && git ls-files | grep -qx CLAUDE.md )'
chk "git: screenshot force-tracked"         '( cd "$BUILT" && git ls-files | grep -q "assets/framework_demo.png" )'
chk "git: user media stays ignored"         '( cd "$BUILT" && cp "$V/assets/my_photo.png" assets/ 2>/dev/null; git check-ignore -q assets/my_photo.png )'
chk "git: .gitkeep tracked"                 '( cd "$BUILT" && git ls-files | grep -q ".gitkeep" )'

echo "== Phase 2: mutual exclusion (one direction per run) =="
build_fake_vault
out="$(bash "$SCRIPT" --pull "$ROOT/x" --push "$ROOT/y" 2>&1)"; rc=$?
chk "both directions → nonzero exit"        '[ "$rc" -ne 0 ]'
chk "both directions → clear error"         'echo "$out" | grep -qi "ONE direction"'

echo "== Phase 3: pull preview when in sync =="
setup_published
b_readme="$(hash_of "$V/README.md")"; b_claude="$(hash_of "$V/CLAUDE.md")"
out="$(bash "$SCRIPT" --pull "$CLONE" 2>&1)"
chk "preview: reports already matches"      'echo "$out" | grep -q "already matches"'
chk "preview: announces PREVIEW only"       'echo "$out" | grep -q "PREVIEW only"'
chk "preview: README NOT written"           '[ "$(hash_of "$V/README.md")" = "$b_readme" ]'
chk "preview: CLAUDE NOT written"           '[ "$(hash_of "$V/CLAUDE.md")" = "$b_claude" ]'

echo "== Phase 4: pull preview detects an upstream change, writes nothing =="
setup_published
printf '\nUPSTREAM EDIT\n' >> "$CLONE/README.md"
( cd "$CLONE" && $GIT commit -qam edit && $GIT push -q ) >/dev/null 2>&1
b_readme="$(hash_of "$V/README.md")"
out="$(bash "$SCRIPT" --pull "$CLONE" 2>&1)"
chk "preview: flags README update"          'echo "$out" | grep -qE "update +README"'
chk "preview: still writes nothing"         '[ "$(hash_of "$V/README.md")" = "$b_readme" ]'

echo "== Phase 5: pull --apply updates root docs + assets, pulls new skills, preserves export-template, spares knowledge =="
setup_published
printf '\nUPSTREAM EDIT v2\n' >> "$CLONE/README.md"
printf '# new contributing\n' > "$CLONE/CONTRIBUTING.md"   # legacy repo-side file — retired, must NOT flow home
printf 'NEW LICENSE v2\n' > "$CLONE/LICENSE.md"
mkdir -p "$CLONE/.claude/skills/repoonly"; printf '# repoonly\n' > "$CLONE/.claude/skills/repoonly/SKILL.md"   # exists only upstream
printf '# UPSTREAM HOOK\n' >> "$CLONE/.claude/hooks/calendar-digest.py"
printf '{ "upstream": "settings" }\n' > "$CLONE/.claude/settings.json"
( cd "$CLONE" && $GIT add -A && $GIT commit -qam edit2 && $GIT push -q ) >/dev/null 2>&1
b_secret="$(hash_of "$V/wiki/sources/secret.md")"
bash "$SCRIPT" --pull "$CLONE" --apply >/dev/null 2>&1
chk "apply: README updated at root"         'grep -q "UPSTREAM EDIT v2" "$V/README.md"'
chk "apply: LICENSE.md updated at root"     'grep -q "NEW LICENSE v2" "$V/LICENSE.md"'
chk "apply: the shipped hook updated"       'grep -q "UPSTREAM HOOK" "$V/.claude/hooks/calendar-digest.py"'
chk "apply: settings refreshed in the payload" 'grep -q "upstream" "$V/.claude/skills/export-template/payload/settings.json"'
chk "apply: the vault's own settings untouched" 'grep -q "own settings" "$V/.claude/settings.json"'
chk "apply: CONTRIBUTING NOT pulled (retired)" '! grep -q "new contributing" "$V/CONTRIBUTING.md"'
chk "apply: assets/ screenshot present"     '[ -f "$V/assets/framework_demo.png" ]'
chk "apply: repo-only skill pulled (dynamic)" '[ -d "$V/.claude/skills/repoonly" ]'
chk "apply: user media untouched"           '[ -f "$V/assets/my_photo.png" ]'
chk "apply: demo NOT pulled to vault root"  '[ ! -d "$V/examples" ]'
chk "apply: export-template PRESERVED"      '[ -f "$V/.claude/skills/export-template/export_template.sh" ]'
chk "apply: knowledge untouched"            '[ "$(hash_of "$V/wiki/sources/secret.md")" = "$b_secret" ]'
chk "apply: raw untouched"                  '[ -f "$V/raw/source1.md" ]'

echo "== Phase 6: bytecode / OS junk ignored in the pull diff =="
setup_published
mkdir -p "$V/.claude/skills/oldskill/__pycache__"; printf 'x' > "$V/.claude/skills/oldskill/__pycache__/m.pyc"
printf 'junk' > "$V/.claude/skills/gather/.DS_Store"
out="$(bash "$SCRIPT" --pull "$CLONE" 2>&1)"
chk "junk: oldskill NOT flagged"            '! echo "$out" | grep -q "oldskill"'
chk "junk: gather NOT flagged"              '! echo "$out" | grep -q "gather"'
chk "junk: overall already matches"         'echo "$out" | grep -q "already matches"'

echo "== Phase 7: --with-graph pulls graph.json only =="
setup_published
printf '{ "graph": "v2" }\n' > "$CLONE/.obsidian/graph.json"
printf '{ "app": "v2" }\n'   > "$CLONE/.obsidian/app.json"
( cd "$CLONE" && $GIT commit -qam obs && $GIT push -q ) >/dev/null 2>&1
b_app="$(hash_of "$V/.obsidian/app.json")"
bash "$SCRIPT" --pull "$CLONE" --with-graph --apply >/dev/null 2>&1
chk "graph: graph.json pulled"              'grep -q "v2" "$V/.obsidian/graph.json"'
chk "graph: app.json NOT pulled"            '[ "$(hash_of "$V/.obsidian/app.json")" = "$b_app" ]'

echo "== Phase 8: push → pull round-trip is clean (idempotent) =="
setup_published
out="$(bash "$SCRIPT" --pull "$CLONE" 2>&1)"
chk "roundtrip: no framework changes"       'echo "$out" | grep -q "already matches"'
bash "$SCRIPT" --push "$CLONE" >/dev/null 2>&1
( cd "$CLONE" && $GIT add -A ) >/dev/null 2>&1
chk "roundtrip: re-push yields no staged diff" '[ -z "$(cd "$CLONE" && git diff --cached --name-only)" ]'

echo "== Phase 9: README links resolve; none point to payload =="
build_fake_vault
BUILT="$ROOT/built2"
bash "$SCRIPT" "$BUILT" >/dev/null 2>&1
chk "links: no payload/ reference in README"   '! grep -q "payload/" "$BUILT/README.md"'
miss=0
while IFS= read -r tgt; do [ -e "$BUILT/$tgt" ] || { miss=1; echo "      missing target: $tgt"; }; done \
  < <(grep -oE '\]\([^)]+\)' "$BUILT/README.md" | sed -E 's/^\]\(//; s/\)$//' | grep -vE '^https?://|^#|^mailto:')
chk "links: all relative README links resolve" '[ "$miss" = 0 ]'

echo "== Phase 10: pull self-updates export-template (running script replaced safely) =="
setup_published
printf '\n# UPSTREAM EXPORT-TEMPLATE MARKER\n' >> "$CLONE/.claude/skills/export-template/SKILL.md"
( cd "$CLONE" && $GIT add -A && $GIT commit -qam et && $GIT push -q ) >/dev/null 2>&1
bash "$SCRIPT" --pull "$CLONE" --apply >/dev/null 2>&1; rc=$?
chk "self-update: pull completed cleanly (exit 0)"      '[ "$rc" = 0 ]'
chk "self-update: vault export-template got the change" 'grep -q "UPSTREAM EXPORT-TEMPLATE MARKER" "$V/.claude/skills/export-template/SKILL.md"'
chk "self-update: export_template.sh still present"     '[ -f "$V/.claude/skills/export-template/export_template.sh" ]'

echo "== Phase 11: push removes a stale generated copy of the excluded skill; the vault's copy is untouched =="
setup_published
mkdir -p "$CLONE/.claude/skills/$EXCLUDED_SKILL"; printf 'stale\n' > "$CLONE/.claude/skills/$EXCLUDED_SKILL/SENTINEL.md"
b_excl="$(hash_of "$V/.claude/skills/$EXCLUDED_SKILL/SKILL.md")"
bash "$SCRIPT" --push "$CLONE" >/dev/null 2>&1; rc=$?
chk "push: exits 0 over a destination holding the sentinel"     '[ "$rc" = 0 ]'
chk "push: the sentinel excluded-skill directory is gone"      '[ ! -e "$CLONE/.claude/skills/$EXCLUDED_SKILL" ]'
chk "push: an ordinary skill is present (control)"             '[ -f "$CLONE/.claude/skills/ingest/SKILL.md" ]'
chk "push: export-template is present (control)"               '[ -f "$CLONE/.claude/skills/export-template/export_template.sh" ]'
chk "push: the vault's excluded skill is byte-identical"       '[ "$(hash_of "$V/.claude/skills/$EXCLUDED_SKILL/SKILL.md")" = "$b_excl" ]'

echo "== 13) the REAL vault README's images can actually ship =="
VAULT_ROOT="$(cd "$REALSKILL/../../.." && pwd)"
IMGS=$(grep -oE 'assets/[A-Za-z0-9._-]+\.(png|jpg|jpeg|gif|webp)' "$VAULT_ROOT/README.md" | sort -u)
chk "control: README references at least one assets/ image" '[ -n "$IMGS" ]'
for img in $IMGS; do
  chk "README image exists in vault: $img"            "[ -f \"$VAULT_ROOT/$img\" ]"
  chk "shipped .gitignore un-ignores it: $img"        "grep -qF '!/$img' \"$REALSKILL/payload/gitignore.txt\""
  chk "export copies it (readme_images matches): $img" "grep -oE 'assets/[A-Za-z0-9._-]+\\.(png|jpg|jpeg|gif|webp)' \"$VAULT_ROOT/README.md\" | grep -qx '$img'"
done

echo "== 14) shipped surfaces carry no wikilink to a page that does not ship (shared script: lint/check-shipped-links.py) =="
# One implementation, two callers: lint Step 2g runs this at edit time, this leg at publish — they cannot
# drift. Scope, exclusions and premise guards live in the script. Exit 0 clean · 1 findings ·
# 2 PROBE FAILED.
VROOT="$(cd "$REALSKILL/../../.." && pwd)"
# The skills copy_framework() skips never ship, so the check is told to skip them: the names come from
# the exporter's own skip lines, and the leg below proves they are the one reviewed exclusion.
SL_SKIP=$(sed -n 's/^[[:space:]]*\[ "\$s" = \([A-Za-z0-9._-]*\) \] && continue[[:space:]]*$/\1/p' "$REALSKILL/export_template.sh")
chk "control: the exporter's skip lines name exactly the excluded skill" '[ "$SL_SKIP" = "$EXCLUDED_SKILL" ]'
SL_RC=0; SL_OUT="$(python3 "$VROOT/.claude/skills/lint/check-shipped-links.py" $(for s in $SL_SKIP; do printf -- '--skip-skill %s ' "$s"; done) "$VROOT" 2>&1)" || SL_RC=$?
chk "control: shipped-links probe ran (exit 0/1, never PROBE FAILED)" '[ "$SL_RC" -ne 2 ]'
chk "no shipped surface links a non-shipping wiki page"               '[ "$SL_RC" -eq 0 ]'
[ "$SL_RC" -ne 0 ] && echo "      $SL_OUT"

echo "== 15) every shipped skill is documented in README + MANUAL =="
SKDIR15="$(cd "$REALSKILL/.." && pwd)"            # the real .claude/skills/
VROOT15="$(cd "$REALSKILL/../../.." && pwd)"      # the real vault root
SKILLS15=$(cd "$SKDIR15" && ls -d */ | tr -d '/' | grep -vx "$EXCLUDED_SKILL" | grep -v '^my-')   # the excluded skill and a user's own my- skills never ship
chk "control: shipped skills enumerated"        "[ -n \"$SKILLS15\" ]"
MISS_R15=""; MISS_M15=""
for s in $SKILLS15; do
  grep -qF "| \`$s\` |" "$VROOT15/README.md" || MISS_R15="$MISS_R15 $s"
  grep -qF "\`$s\`"     "$VROOT15/MANUAL.md" || MISS_M15="$MISS_M15 $s"
done
chk "every shipped skill has a README skill-table row" "[ -z \"$MISS_R15\" ]"
chk "every shipped skill is named in MANUAL"           "[ -z \"$MISS_M15\" ]"
[ -n "$MISS_R15" ] && echo "      README missing:$MISS_R15"
[ -n "$MISS_M15" ] && echo "      MANUAL missing:$MISS_M15"
chk "control: probe fails on a fabricated skill" "! grep -qF '| \`no-such-skill\` |' \"$VROOT15/README.md\""

echo "== 16) a skill's nested wrapper, config and slices ship and stay committable =="
# The thin-lane path (2026-09-04) put a python wrapper, a JSON routing table, a template and a
# nested slice tree inside the delegate skill. They ship by the same auto-discovery as any skill
# file; this phase pins that, and pins that no .gitignore rule (a bare *.json, say) quietly drops one.
build_fake_vault
B16="$ROOT/built16"
bash "$SCRIPT" "$B16" >/dev/null 2>&1
( cd "$B16" && $GIT init -q && $GIT add -A ) >/dev/null 2>&1
chk "build: skill wrapper script shipped"        '[ -f "$B16/.claude/skills/delegate/lane.py" ]'
chk "build: skill fence script shipped"          '[ -f "$B16/.claude/skills/delegate/lane-fence.py" ]'
chk "build: skill JSON config shipped"           '[ -f "$B16/.claude/skills/delegate/routing.json" ]'
chk "build: skill template shipped"              '[ -f "$B16/.claude/skills/delegate/templates/lane-core.md" ]'
chk "build: nested slice directory shipped"      '[ -f "$B16/.claude/skills/delegate/lane-home-src/compile-core/SKILL.md" ]'
chk "git: wrapper tracked"                       '( cd "$B16" && git ls-files | grep -qx ".claude/skills/delegate/lane.py" )'
chk "git: JSON config tracked"                   '( cd "$B16" && git ls-files | grep -qx ".claude/skills/delegate/routing.json" )'
chk "git: nested slice tracked"                  '( cd "$B16" && git ls-files | grep -qx ".claude/skills/delegate/lane-home-src/compile-core/SKILL.md" )'
# §11 control: the same check-ignore probe must FIRE on a path that is meant to be ignored, in the
# same directory — otherwise "not ignored" above would also be the answer on a broken probe.
chk "control: check-ignore fires on ignored junk in that same directory" \
    '( cd "$B16" && mkdir -p .claude/skills/delegate/__pycache__ && : > .claude/skills/delegate/__pycache__/x.pyc && git check-ignore -q .claude/skills/delegate/__pycache__/x.pyc )'
chk "build: no lane home (agent state) inside the shipped tree" '[ -z "$(find "$B16" -type d -name "lane-home" -not -name "lane-home-src")" ]'

echo "== 17) the real vault's delegate skill still carries every file the lane path ships =="
DLG17="$(cd "$REALSKILL/.." && pwd)/delegate"
chk "control: the real delegate skill is present" '[ -d "$DLG17" ]'
for f in lane.py lane-fence.py test_lane.sh prices.json routing.json templates/lane-core.md \
         lane-home-src/README.md lane-home-src/compile-core/SKILL.md lane-home-src/reflect-slice/SKILL.md; do
  chk "delegate carries $f" "[ -f \"$DLG17/$f\" ]"
done
chk "control: the same probe fails on a file that does not exist" '[ ! -f "$DLG17/no-such-lane-file.py" ]'
# The lane home is machine-local state, so setup.sh must build it rather than the payload shipping one.
chk "shipped setup.sh invokes the wrapper"       'grep -q "skills/delegate/lane.py" "$REALSKILL/payload/setup.sh"'
chk "shipped setup.sh runs its init step"        'grep -q "init_lane_home" "$REALSKILL/payload/setup.sh"'
chk "shipped setup.sh names the lane home in its output" 'grep -qi "lane home" "$REALSKILL/payload/setup.sh"'
chk "control: the same grep misses a step setup.sh does not have" '! grep -q "init_lane_home_v99" "$REALSKILL/payload/setup.sh"'

echo "== 18) the root citation file ships and pulls beside README and LICENSE =="
build_fake_vault
B18="$ROOT/built18"
bash "$SCRIPT" "$B18" >/dev/null 2>&1
chk "build: CITATION.cff sourced from the vault root" 'diff -q "$V/CITATION.cff" "$B18/CITATION.cff"'
( cd "$B18" && $GIT init -q && $GIT add -A ) >/dev/null 2>&1
chk "git: CITATION.cff tracked"                       '( cd "$B18" && git ls-files | grep -qx CITATION.cff )'
rm -f "$V/CITATION.cff"
out="$(bash "$SCRIPT" "$ROOT/built18b" 2>&1)"; rc=$?
chk "build: a missing root file stops the build"      '[ "$rc" -ne 0 ]'
chk "build: the stop names the missing file"          'echo "$out" | grep -q "CITATION.cff missing"'
setup_published
printf 'cff-version: 1.2.0\ntitle: upstream\n' > "$CLONE/CITATION.cff"
( cd "$CLONE" && $GIT commit -qam cite && $GIT push -q ) >/dev/null 2>&1
out="$(bash "$SCRIPT" --pull "$CLONE" 2>&1)"
chk "preview: flags a changed CITATION.cff"           'echo "$out" | grep -qE "update +CITATION.cff"'
bash "$SCRIPT" --pull "$CLONE" --apply >/dev/null 2>&1
chk "apply: CITATION.cff updated at the vault root"   'grep -q "title: upstream" "$V/CITATION.cff"'
setup_published
( cd "$CLONE" && $GIT rm -q CITATION.cff && $GIT commit -qm "an older repo" && $GIT push -q ) >/dev/null 2>&1
b_cite="$(hash_of "$V/CITATION.cff")"
out="$(bash "$SCRIPT" --pull "$CLONE" 2>&1)"
chk "preview: a repo with no citation file flags nothing for it" '! echo "$out" | grep -q "update  CITATION.cff"'
bash "$SCRIPT" --pull "$CLONE" --apply >/dev/null 2>&1; rc=$?
chk "apply: a repo with no citation file still applies"          '[ "$rc" = 0 ]'
chk "apply: the vault's citation file is left as it was"         '[ "$(hash_of "$V/CITATION.cff")" = "$b_cite" ]'
# An older exporter's one pull leaves the new skill and no root citation file: it copied only the root
# files it knew. That one pull must be enough, so the new exporter's next push carries on from there.
setup_published
printf 'cff-version: 1.2.0\ntitle: upstream\n' > "$CLONE/CITATION.cff"
( cd "$CLONE" && $GIT commit -qam cite && $GIT push -q ) >/dev/null 2>&1
rm -f "$V/CITATION.cff"
out="$(bash "$SCRIPT" --push "$CLONE" 2>&1)"; rc=$?
chk "upgrade: a push needs no second pull"                      '[ "$rc" = 0 ]'
chk "upgrade: the clone keeps its own citation file"            'grep -q "title: upstream" "$CLONE/CITATION.cff"'
chk "upgrade: the push says so, and names the pull that fills the gap" 'echo "$out" | grep -q "NOTE: CITATION.cff is not at the vault root yet" && echo "$out" | grep -q -- "--pull <repo> --apply brings it"'
chk "upgrade: a push writes nothing to the vault"               '[ ! -e "$V/CITATION.cff" ]'
bash "$SCRIPT" --pull "$CLONE" --apply >/dev/null 2>&1; rc=$?
chk "upgrade: the next ordinary pull brings it to the vault"    '[ "$rc" = 0 ] && grep -q "title: upstream" "$V/CITATION.cff"'
rm -f "$V/CITATION.cff"
out="$(bash "$SCRIPT" "$ROOT/built18c" 2>&1)"; rc=$?
chk "upgrade: only a fresh build stops, and it names that pull" '[ "$rc" -ne 0 ] && echo "$out" | grep -q "CITATION.cff missing" && echo "$out" | grep -q -- "--pull <repo> --apply"'

echo "== 19) the strip: a block alone on its lines, and an inline fragment =="
build_fake_vault
mkdir -p "$V/.claude/agents"; printf '# an agent\n' > "$V/.claude/agents/a.md"   # the build's closing listing needs one
cat > "$V/CLAUDE.md" <<'STRIP_FIXTURE'
# Contract

before the block
<!-- vault-local:begin -->
owner-only line one
owner-only line two
<!-- vault-local:end -->
after the block

  <!-- vault-local:begin -->
  an indented owner-only line
  <!-- vault-local:end -->
after the indented block

under the reviewed pattern<!-- vault-local:begin --> (`a-private-page.md`)<!-- vault-local:end --> with its legs clean.
loses recall silently.<!-- vault-local:begin --> Derivation: [[a-private-page]].<!-- vault-local:end --> This replaces it.
last word of a line.<!-- vault-local:begin --> (Evidence: a private
  page across two lines.)<!-- vault-local:end -->
- the next bullet keeps its own line
two<!-- vault-local:begin --> one<!-- vault-local:end --> fragments<!-- vault-local:begin --> two<!-- vault-local:end --> on a line.
STRIP_FIXTURE
B19="$ROOT/built19"
bash "$SCRIPT" "$B19" >/dev/null 2>&1; rc=$?
chk "strip: the build succeeds on the fixture"            '[ "$rc" = 0 ]'
chk "strip: no marker and no owner-only text ships"       '! grep -qE "vault-local|owner-only|a-private-page|a private" "$B19/CLAUDE.md"'
chk "strip: a whole-line block goes with its lines"       'grep -A1 -x "before the block" "$B19/CLAUDE.md" | grep -qx "after the block"'
chk "strip: an indented block goes with its lines"        'grep -B2 -x "after the indented block" "$B19/CLAUDE.md" | grep -qx "after the block"'
chk "strip: an inline fragment keeps the words on both sides apart" 'grep -qx "under the reviewed pattern with its legs clean." "$B19/CLAUDE.md"'
chk "strip: a mid-line sentence keeps its space"          'grep -qx "loses recall silently. This replaces it." "$B19/CLAUDE.md"'
chk "strip: a fragment at a line end keeps the line break" 'grep -A1 -x "last word of a line." "$B19/CLAUDE.md" | grep -qx -- "- the next bullet keeps its own line"'
chk "strip: two fragments on one line"                    'grep -qx "two fragments on a line." "$B19/CLAUDE.md"'
STRIPPY="$V/.claude/skills/export-template/strip_vault_local.py"
chk "strip: --stdout prints what the export wrote"        'python3 "$STRIPPY" --stdout "$V/CLAUDE.md" | cmp -s - "$B19/CLAUDE.md"'
printf '{ "x": "<!-- vault-local:begin --> kept <!-- vault-local:end -->" }\n' > "$ROOT/other.json"
chk "strip: a file type the export does not strip prints unchanged" 'python3 "$STRIPPY" --stdout "$ROOT/other.json" | cmp -s - "$ROOT/other.json"'
printf 'x\n<!-- vault-local:begin -->\ny\n' > "$V/CLAUDE.md"
out="$(bash "$SCRIPT" "$ROOT/built19b" 2>&1)"; rc=$?
chk "strip: an unmatched begin stops the build"           '[ "$rc" -ne 0 ] && echo "$out" | grep -q "PROBE FAILED: unmatched vault-local begin"'
printf 'x\n<!-- vault-local:begin -->\ny\n<!-- vault-local:begin -->\nz\n<!-- vault-local:end -->\n' > "$V/CLAUDE.md"
out="$(bash "$SCRIPT" "$ROOT/built19c" 2>&1)"; rc=$?
chk "strip: a nested block stops the build"               '[ "$rc" -ne 0 ] && echo "$out" | grep -q "PROBE FAILED: nested vault-local block"'
printf 'x and a private<!--\nvault-local:begin --> fragment<!-- vault-local:end -->\n' > "$V/CLAUDE.md"
out="$(bash "$SCRIPT" "$ROOT/built19d" 2>&1)"; rc=$?
chk "strip: a marker a re-wrap split across lines stops the build" '[ "$rc" -ne 0 ] && echo "$out" | grep -q "PROBE FAILED: a vault-local marker split across lines"'
printf 'plain text that names vault-local:begin in prose stays\n' > "$V/CLAUDE.md"
out="$(bash "$SCRIPT" "$ROOT/built19e" 2>&1)"; rc=$?
chk "control: prose naming the marker is no marker"       '[ "$rc" = 0 ] && grep -q "names vault-local:begin in prose" "$ROOT/built19e/CLAUDE.md"'

echo "== 20) every routing row carries a mark, and the owner's own are held back from the public copy =="
build_fake_vault
mkdir -p "$V/.claude/agents"; printf '# an agent\n' > "$V/.claude/agents/a.md"
TABLE20="$V/.claude/skills/delegate/routing.json"
cat > "$TABLE20" <<'ROUTING_FIXTURE'
{ "schema": 2,
  "head": { "layer": "yours", "text": "the owner picks the head" },
  "seats": { "theirs": { "layer": "yours", "text": "the holder's only row" } },
  "rules": [ { "layer": "yours", "from": "a skill", "text": "a choice of the owner" },
             { "layer": "core", "from": "a definition", "text": "a rule with a link (owner, 2 October; [[a-private-page]])." },
             { "layer": "core", "class": "writer", "from": "a definition", "text": "a default that ships" } ],
  "classes": {
    "critic": { "layer": "core", "gate": "local gate words", "cost": { "n": 1 },
                "notes": [ { "layer": "yours", "text": "owner-only note" }, { "layer": "core", "text": "a shipped note" } ] },
    "mine":   { "layer": "yours", "model": { "default": "opus" } },
    "writer": { "layer": "core", "model": { "default": "opus" }, "effort": { "default": "high" } } } }
ROUTING_FIXTURE
B20="$ROOT/built20"
out="$(bash "$SCRIPT" "$B20" 2>&1)"; rc=$?
R20="$B20/.claude/skills/delegate/routing.json"
chk "routing: the build succeeds"                          '[ "$rc" = 0 ]'
chk "routing: a top-level row marked yours is held back"   '! grep -q "the owner picks the head" "$R20"'
chk "routing: a class marked yours is held back"           '! grep -q "\"mine\"" "$R20"'
chk "routing: a list item marked yours is held back"       '! grep -q "owner-only note" "$R20"'
chk "routing: a holder whose rows all stay goes with them" '! grep -q "\"seats\"" "$R20"'
chk "routing: no yours mark reaches the public copy"       '! grep -q "yours" "$R20"'
chk "routing: a rule marked yours is held back"            '! grep -q "a choice of the owner" "$R20"'
chk "routing: a rule marked core ships"                    'grep -q "a default that ships" "$R20"'
chk "routing: a shipped rule's link to a vault page is cut" '! grep -q "a-private-page" "$R20" && grep -q "a rule with a link (owner, 2 October)\." "$R20"'
chk "routing: the vault's own table keeps that link"       'grep -q "a-private-page" "$TABLE20"'
chk "routing: the export names what it held back"          'echo "$out" | grep -q "held back from this copy: head, seats.theirs, rules\[0\], classes.critic.notes\[0\], classes.mine"'
chk "routing: a row marked core ships"                     'grep -q "\"critic\"" "$R20" && grep -q "a shipped note" "$R20"'
chk "routing: a row marked core keeps its defaults"        'grep -q "\"writer\"" "$R20" && grep -q "\"default\": \"opus\"" "$R20" && grep -q "\"default\": \"high\"" "$R20"'
chk "routing: the existing public rewrite still runs"      '! grep -q "local gate words" "$R20" && ! grep -q "\"cost\"" "$R20"'
chk "routing: the vault's own table keeps its rows"        'grep -q "the owner picks the head" "$TABLE20"'
chk "routing: the public copy passes the same check, so its own export runs" 'python3 "$V/.claude/skills/export-template/routing_marks.py" --check "$R20"'
# Each table below must stop the export with exit 2, a line naming the fault, and nothing copied.
refused(){   # $1 the plant, $2 the table, $3 what the stop must say
  printf '%s\n' "$2" > "$TABLE20"
  rm -rf "$ROOT/built20x"
  WANT="$3"
  out="$(bash "$SCRIPT" "$ROOT/built20x" 2>&1)"; rc=$?
  chk "routing: $1 stops the export, exit 2"  '[ "$rc" = 2 ]'
  chk "routing: $1 is named in the stop"      'echo "$out" | grep -qF "PROBE FAILED: $WANT"'
  chk "routing: $1 leaves nothing copied"     '[ ! -e "$ROOT/built20x/CLAUDE.md" ]'
}
refused "a class with no mark" '{ "schema": 2, "classes": { "critic": { "layer": "core" }, "writer": { "model": { "default": "opus" } } } }' "1 routing row(s) carry no mark"
chk "routing: the stop names the unmarked class, and only it" 'echo "$out" | grep -q ": classes.writer; give each" && ! echo "$out" | grep -q "classes.critic"'
refused "a null mark"          '{ "schema": 2, "classes": { "writer": { "layer": null } } }'    "unknown routing mark None at classes.writer"
refused "a mistyped mark"      '{ "schema": 2, "classes": { "mine": { "layer": "your" } } }'    "unknown routing mark 'your' at classes.mine"
refused "a mark from another word list" '{ "schema": 2, "classes": { "mine": { "layer": "user" } } }' "unknown routing mark 'user' at classes.mine"
refused "a mistyped mark on a part of a row" '{ "schema": 2, "classes": { "w": { "layer": "core", "notes": [ { "layer": "Core" } ] } } }' "unknown routing mark 'Core' at classes.w.notes[0]"
refused "a top-level row with no mark" '{ "schema": 2, "head": { "text": "x" }, "classes": { "writer": { "layer": "core" } } }' "1 routing row(s) carry no mark"
chk "routing: the stop names that row"                     'echo "$out" | grep -q ": head; give each"'
refused "a top-level value that cannot carry a mark" '{ "schema": 2, "head_model": "opus", "classes": { "writer": { "layer": "core" } } }' "1 routing row(s) carry no mark"
chk "routing: the stop names that value"                   'echo "$out" | grep -q ": head_model; give each"'
refused "an unmarked note beside a holder's rows" '{ "schema": 2, "seats": { "_": "a choice of the owner", "a": { "layer": "core" } }, "classes": { "writer": { "layer": "core" } } }' "1 routing row(s) carry no mark"
chk "routing: the stop names that note"                    'echo "$out" | grep -q ": seats._; give each"'
refused "a rule with no mark"  '{ "schema": 2, "rules": [ { "layer": "core", "text": "a" }, { "text": "b" } ], "classes": { "writer": { "layer": "core" } } }' "1 routing row(s) carry no mark"
chk "routing: the stop names that rule"                    'echo "$out" | grep -qF ": rules[1]; give each"'
refused "a mark in the frame"  '{ "schema": 2, "preset_model": { "top": "opus", "layer": "core" }, "classes": { "writer": { "layer": "core" } } }' "routing mark at preset_model"
refused "every class marked yours" '{ "schema": 2, "classes": { "mine": { "layer": "yours" } } }' "no class would ship"
refused "a table with no class" '{ "schema": 2 }'                                                "no class would ship"
refused "a held-back class whose definition ships" '{ "schema": 2, "classes": { "a": { "layer": "yours" }, "writer": { "layer": "core" } } }' "classes.a in"
refused "a shipping class losing its default" '{ "schema": 2, "classes": { "writer": { "layer": "core", "model": { "layer": "yours", "default": "opus" } } } }' "classes.writer.model in"
refused "a shipping class losing its grants" '{ "schema": 2, "classes": { "writer": { "layer": "core", "grants": { "layer": "yours", "default": [], "extras": [] } } } }' "classes.writer.grants in"
refused "a shipping class losing its skills" '{ "schema": 2, "classes": { "writer": { "layer": "core", "skills": { "layer": "yours", "default": [], "extras": [] } } } }' "classes.writer.skills in"
refused "a shipping class losing its mcp" '{ "schema": 2, "classes": { "writer": { "layer": "core", "mcp": { "layer": "yours", "default": [], "grantable": [] } } } }' "classes.writer.mcp in"
refused "a table that is not JSON" '{ nope'                                                      "cannot read the routing table"
# A refused build leaves an earlier build in place: the check runs before the build resets its destination.
B20K="$ROOT/built20k"
mkdir -p "$B20K/nested/empty"
printf 'an earlier build\n' > "$B20K/CLAUDE.md"
printf 'a hidden file\n' > "$B20K/.kept"
printf 'non-text \000\001\377 bytes\n' > "$B20K/nested/data.bin"
cp -Rp "$B20K" "$B20K.was"
printf '{ "schema": 2, "classes": { "writer": { "model": { "default": "opus" } } } }\n' > "$TABLE20"
out="$(bash "$SCRIPT" "$B20K" 2>&1)"; rc=$?
chk "routing: an unmarked row stops a build over an earlier build, exit 2" '[ "$rc" = 2 ] && echo "$out" | grep -q "PROBE FAILED: 1 routing row(s) carry no mark"'
chk "routing: the refused build leaves the earlier build byte for byte"    'diff -r "$B20K.was" "$B20K"'
printf '{ "schema": 2, "classes": { "writer": { "layer": "core", "model": { "default": "opus" }, "grants": { "layer": "core", "default": [], "extras": [] } } } }\n' > "$TABLE20"
out="$(bash "$SCRIPT" "$B20K" 2>&1)"; rc=$?
chk "control: with the marks given, the same probe sees the build replace the earlier build" '[ "$rc" = 0 ] && ! diff -r "$B20K.was" "$B20K" && [ ! -e "$B20K/.kept" ]'
chk "control: a required block marked core ships"                          'grep -q "\"grants\"" "$B20K/.claude/skills/delegate/routing.json"'
setup_published
TABLE20="$V/.claude/skills/delegate/routing.json"
printf '{ "schema": 2, "classes": { "writer": { "model": { "default": "opus" } } } }\n' > "$TABLE20"
printf 'a vault edit\n' >> "$V/MANUAL.md"
out="$(bash "$SCRIPT" --push "$CLONE" 2>&1)"; rc=$?
chk "routing: an unmarked row stops a push too, exit 2"    '[ "$rc" = 2 ] && echo "$out" | grep -q "PROBE FAILED: 1 routing row(s) carry no mark"'
chk "routing: a stopped push leaves the clone as it was"   '[ -z "$(git -C "$CLONE" status --porcelain)" ]'
out="$(bash "$SCRIPT" --pull "$CLONE" 2>&1)"; rc=$?
chk "routing: a pull does not read the marks, so an unmarked table cannot block an update" '[ "$rc" = 0 ] && echo "$out" | grep -q "PREVIEW only"'
printf '{ "schema": 2, "classes": { "writer": { "layer": "core", "model": { "default": "opus" } } } }\n' > "$TABLE20"
out="$(bash "$SCRIPT" --push "$CLONE" 2>&1)"; rc=$?
chk "control: with the mark given, the same status probe sees the overlay" '[ "$rc" = 0 ] && git -C "$CLONE" status --porcelain | grep -q "MANUAL.md"'
mv "$V/.claude/skills/export-template/routing_marks.py" "$ROOT/marks.away"
out="$(bash "$SCRIPT" "$ROOT/built20y" 2>&1)"; rc=$?
chk "routing: with the marks script missing the export stops, nothing copied" '[ "$rc" -ne 0 ] && [ ! -e "$ROOT/built20y/CLAUDE.md" ]'
mv "$ROOT/marks.away" "$V/.claude/skills/export-template/routing_marks.py"

echo "== 21) the core list ships, the deny rules follow it, and a user's own names stay out =="
build_fake_vault
mkdir -p "$V/.claude/agents" "$V/.claude/skills/my-own"
printf '# an agent\n' > "$V/.claude/agents/a.md"
printf '# my own skill\n' > "$V/.claude/skills/my-own/SKILL.md"
printf '# my own helper\n' > "$V/.claude/agents/my-helper.md"
printf '#!/bin/sh\n' > "$V/.claude/hooks/my-hook.sh"
printf '{ "rules": [] }\n' > "$V/.claude/routing.local.json"
printf 'my-own\n' > "$V/.claude/sanctioned.local.txt"
printf '{\n  "graph": true,\n  "sync": false,\n  "bases": true\n}' > "$V/.obsidian/core-plugins.json"
B21="$ROOT/built21"
bash "$SCRIPT" "$B21" >/dev/null 2>&1; rc=$?
chk "build: it succeeds with a user's own names in the source"  '[ "$rc" = 0 ]'
chk "build: the core list ships as .claude/core-paths"          'diff -q "$REALSKILL/payload/core-paths.txt" "$B21/.claude/core-paths"'
chk "build: a my- skill stays out of the export"                '[ ! -e "$B21/.claude/skills/my-own" ]'
chk "build: a my- helper stays out of the export"               '[ ! -e "$B21/.claude/agents/my-helper.md" ]'
chk "control: an ordinary helper ships beside it"               '[ -f "$B21/.claude/agents/a.md" ]'
chk "build: a my- hook stays out of the export"                 '[ ! -e "$B21/.claude/hooks/my-hook.sh" ]'
chk "build: the routing overlay never reaches a build"          '[ ! -e "$B21/.claude/routing.local.json" ]'
chk "build: lint's local list never reaches a build"            '[ ! -e "$B21/.claude/sanctioned.local.txt" ]'
chk "build: wiki/experience ships in the skeleton"              '[ -f "$B21/wiki/experience/.gitkeep" ]'
chk "build: the shipped sync value is restored"                 'python3 -c "import json, sys; sys.exit(0 if json.load(open(sys.argv[1]))[\"sync\"] is True else 1)" "$B21/.obsidian/core-plugins.json"'
chk "build: the vault's own sync value stays as it was"         'grep -q "\"sync\": false" "$V/.obsidian/core-plugins.json"'
chk "build: the rest of core-plugins is carried over"           'grep -q "\"bases\": true" "$B21/.obsidian/core-plugins.json"'
( cd "$B21" && $GIT init -q && $GIT add -A ) >/dev/null 2>&1
for p in .claude/routing.local.json .claude/sanctioned.local.txt .claude/skills/my-x/SKILL.md .claude/agents/my-x.md .claude/hooks/my-x.py .claude/settings.local.json CUSTOMISATION.md wiki/x.md; do
  chk "git: a user path is ignored: $p"                         "( cd \"\$B21\" && git check-ignore -q '$p' )"
done
for p in CLAUDE.md MANUAL.md setup.sh .gitignore .claude/settings.json .claude/core-paths .claude/skills/ingest/SKILL.md .claude/agents/a.md .claude/hooks/calendar-digest.py; do
  chk "git: a core path is not ignored: $p"                     "! ( cd \"\$B21\" && git check-ignore -q '$p' )"
done
# The rules are read back by a matcher of this suite's own, against what git tracks in the build, so
# a complete list is not just a list that agrees with its generator.
DENY21="$(python3 - "$B21" <<'DENY_READER'
import fnmatch, json, subprocess, sys
root = sys.argv[1]
rules = json.load(open(root + "/.claude/settings.json"))["permissions"]["deny"]
assert all(r.startswith("Edit(/") and r.endswith(")") for r in rules), rules
pats = [r[len("Edit(/"):-1] for r in rules]
def covered(path):
    return any(path == p or (p.endswith("/**") and path.startswith(p[:-2])) for p in pats)
tracked = subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True, check=True).stdout.split("\n")
specs = [l.strip() for l in open(root + "/.claude/core-paths") if l.strip() and not l.startswith("#")]
core = [p for p in tracked if p and any(p == s or (s.endswith("/") and p.startswith(s)) for s in specs)]
print("core", len(core))
print("uncovered", ",".join(p for p in core if not covered(p)) or "none")
print("mine", ",".join(p for p in (".claude/skills/my-own/SKILL.md", ".claude/agents/my-helper.md", ".claude/hooks/my-hook.sh", "CUSTOMISATION.md", ".claude/settings.local.json") if covered(p)) or "none")
print("control", "covered" if covered("CLAUDE.md") and covered(".claude/skills/ingest/SKILL.md") and not covered(".claude/skills/ingest2/SKILL.md") else "broken")
print("folderwide", ",".join(p for p in pats if p.rstrip("/*") in (".claude/skills", ".claude/agents", ".claude/hooks")) or "none")
DENY_READER
)"
chk "deny: the reader saw core files"                           'echo "$DENY21" | grep -qE "^core [1-9]"'
chk "deny: every tracked core file is covered"                  'echo "$DENY21" | grep -qx "uncovered none"'
chk "deny: no user path is covered"                             'echo "$DENY21" | grep -qx "mine none"'
chk "deny: no rule takes a whole folder, so my- names stay free" 'echo "$DENY21" | grep -qx "folderwide none"'
chk "control: the reader tells a covered path from an uncovered one" 'echo "$DENY21" | grep -qx "control covered"'
SKILL21="$(cd "$B21" && ls -d .claude/skills/*/ | wc -l | tr -d ' ')"
chk "deny: one rule per shipped skill"                          '[ "$(grep -c "Edit(/.claude/skills/" "$B21/.claude/settings.json")" = "$SKILL21" ]'
printf '# one more\n' >> "$V/CLAUDE.md"; mkdir -p "$V/.claude/skills/added"; printf '# added\n' > "$V/.claude/skills/added/SKILL.md"
bash "$SCRIPT" "$ROOT/built21b" >/dev/null 2>&1
chk "deny: a new skill gets its rule with no edit"              'grep -q "Edit(/.claude/skills/added/\*\*)" "$ROOT/built21b/.claude/settings.json"'
sed -i.bak '/^\.claude\/hooks\/$/d' "$V/.claude/skills/export-template/payload/core-paths.txt"
bash "$SCRIPT" "$ROOT/built21c" >/dev/null 2>&1
chk "deny: a line taken off the core list takes its rules with it, with no code change" '! grep -q "Edit(/.claude/hooks/" "$ROOT/built21c/.claude/settings.json" && grep -q "Edit(/.claude/skills/" "$ROOT/built21c/.claude/settings.json"'
printf '# only comments\n' > "$V/.claude/skills/export-template/payload/core-paths.txt"
out="$(bash "$SCRIPT" "$ROOT/built21d" 2>&1)"; rc=$?
chk "deny: an empty core list stops the build, never a copy with no guard" '[ "$rc" = 2 ] && echo "$out" | grep -q "PROBE FAILED: .* gave no deny rule"'
build_fake_vault
mkdir -p "$V/.claude/agents" "$V/.claude/skills/export-template/payload/github/ISSUE_TEMPLATE"; printf '# an agent\n' > "$V/.claude/agents/a.md"
printf 'name: a form\n' > "$V/.claude/skills/export-template/payload/github/ISSUE_TEMPLATE/a.yml"
printf 'plain-listed.py\n# a comment line\ntest_listed.sh\n' > "$V/.claude/skills/export-template/payload/shipped-hooks.txt"
printf '# listed\n' > "$V/.claude/hooks/plain-listed.py"; printf '# listed suite\n' > "$V/.claude/hooks/test_listed.sh"
B21E="$ROOT/built21e"
bash "$SCRIPT" "$B21E" >/dev/null 2>&1
chk "build: payload/github ships as .github"                    '[ -f "$B21E/.github/ISSUE_TEMPLATE/a.yml" ]'
chk "build: the shipped hooks come from the list when it exists" '[ -f "$B21E/.claude/hooks/plain-listed.py" ] && [ -f "$B21E/.claude/hooks/test_listed.sh" ]'
chk "build: a hook off the list stays home"                     '[ ! -e "$B21E/.claude/hooks/calendar-digest.py" ]'
rm -f "$V/.claude/skills/export-template/payload/shipped-hooks.txt"
bash "$SCRIPT" "$ROOT/built21f" >/dev/null 2>&1
chk "build: with no list the calendar's hook still ships"       '[ -f "$ROOT/built21f/.claude/hooks/calendar-digest.py" ] && [ ! -e "$ROOT/built21f/.claude/hooks/plain-listed.py" ]'

echo "== 22) the vault is the clone: an update by git =="
# A release, then a user's vault that IS a clone of it, set up and locked; the next release follows.
UV="$ROOT/uservault"
UPD="$UV/.claude/skills/export-template/export_template.sh"
SNAP="$ROOT.snap"   # built once and restored per leg: a publish is the slow part, and every leg starts from the same one
user_vault(){
  if [ -d "$SNAP" ]; then rm -rf "$ROOT"; cp -Rp "$SNAP" "$ROOT"; return 0; fi
  setup_published
  ( cd "$CLONE" && $GIT commit -q --allow-empty -m one \
    && $GIT tag -a v1.0.0 -m one && $GIT push -q origin main v1.0.0 ) >/dev/null 2>&1
  $GIT clone -q "$REMOTE" "$UV" >/dev/null 2>&1
  ( cd "$UV" && env HOME="$ROOT/home" bash setup.sh >/dev/null 2>&1 )
  cp -Rp "$ROOT" "$SNAP"
}
next_release(){ ( cd "$CLONE" && $GIT add -A && $GIT add -f -A wiki >/dev/null 2>&1; $GIT commit -qm next && $GIT tag -a "$1" -m next && $GIT push -q origin main "$1" ) >/dev/null 2>&1; }
update(){ out="$(env HOME="$ROOT/home" bash "$UPD" --pull "$UV" "$@" 2>&1)"; rc=$?; }
user_vault
chk "fixture: the user's vault is set up and locked"            '[ -z "$(git -C "$UV" status --porcelain)" ] && [ ! -w "$UV/CLAUDE.md" ] && [ -f "$UV/CUSTOMISATION.md" ]'
printf '{ "release": "two" }\n' > "$CLONE/.claude/settings.json"
printf '# rules two\n' > "$CLONE/CLAUDE.md"
printf '# a new page of the skill\n' > "$CLONE/.claude/skills/query/NEW.md"
next_release v1.1.0
update
chk "preview: it writes no working file"                        '[ "$rc" = 0 ] && echo "$out" | grep -q "PREVIEW only" && ! grep -q "rules two" "$UV/CLAUDE.md"'
HEAD22="$(git -C "$UV" rev-parse HEAD)"
update --apply
chk "update: a release that changes the settings file updates a clean vault" '[ "$rc" = 0 ] && grep -q "two" "$UV/.claude/settings.json"'
chk "update: the core reaches the new release"                  'grep -q "rules two" "$UV/CLAUDE.md" && [ "$(git -C "$UV" rev-parse HEAD)" != "$HEAD22" ]'
chk "update: a changed file locks again"                        '[ ! -w "$UV/CLAUDE.md" ]'
chk "update: a new file locks too"                              '[ ! -w "$UV/.claude/skills/query/NEW.md" ]'
chk "update: your layer is untouched"                           '[ -f "$UV/CUSTOMISATION.md" ] && [ -w "$UV/CUSTOMISATION.md" ]'
chk "update: the first status after it is still empty"          '[ -z "$(git -C "$UV" status --porcelain)" ]'
user_vault
printf '{ "x": 2 }\n' > "$CLONE/.obsidian/app.json"
next_release v1.1.0
update --apply
chk "marks: a release that changes a marked file passes when you left it alone" '[ "$rc" = 0 ] && grep -q "2" "$UV/.obsidian/app.json"'
chk "marks: the mark comes back"                                '[ "$(git -C "$UV" ls-files -v .obsidian | grep -c "^S ")" = 4 ]'
user_vault
printf '{ "x": 3 }\n' > "$CLONE/.obsidian/app.json"
next_release v1.1.0
printf '{ "mine": true }\n' > "$UV/.obsidian/app.json"
HEAD22="$(git -C "$UV" rev-parse HEAD)"
update --apply
chk "marks: a marked file you changed is refused, your bytes kept" '[ "$rc" = 1 ] && grep -q "mine" "$UV/.obsidian/app.json" && [ "$(git -C "$UV" rev-parse HEAD)" = "$HEAD22" ]'
chk "marks: and the mark comes back after the refusal"          '[ "$(git -C "$UV" ls-files -v .obsidian | grep -c "^S ")" = 4 ]'
user_vault
mkdir -p "$CLONE/wiki/developments"; printf 'the release page\n' > "$CLONE/wiki/developments/clash.md"
next_release v1.1.0
mkdir -p "$UV/wiki/developments"; printf 'my own page\n' > "$UV/wiki/developments/clash.md"
HEAD22="$(git -C "$UV" rev-parse HEAD)"
update --apply
chk "clash: an ignored file at a path the release adds is refused" '[ "$rc" = 1 ] && [ "$(git -C "$UV" rev-parse HEAD)" = "$HEAD22" ]'
chk "clash: your file is intact"                                'grep -q "my own page" "$UV/wiki/developments/clash.md"'
chk "clash: the failure claims only what it knows"              'echo "$out" | grep -q "the update failed; working files may have changed" && ! echo "$out" | grep -q "nothing changed"'
rm -f "$UV/wiki/developments/clash.md"
update --apply
chk "control: with the file gone the same update passes"        '[ "$rc" = 0 ] && grep -q "the release page" "$UV/wiki/developments/clash.md"'
user_vault
printf '# rules two\n' > "$CLONE/CLAUDE.md"
next_release v1.1.0
( cd "$UV" && env HOME="$ROOT/home" bash setup.sh --unlock >/dev/null 2>&1 ); printf 'my edit\n' >> "$UV/CLAUDE.md"
HEAD22="$(git -C "$UV" rev-parse HEAD)"; H22="$(hash_of "$UV/CLAUDE.md")"
update --apply
chk "dirty: a core file you changed stops the update, atomically" '[ "$rc" = 1 ] && [ "$(git -C "$UV" rev-parse HEAD)" = "$HEAD22" ] && [ "$(hash_of "$UV/CLAUDE.md")" = "$H22" ]'
user_vault
printf '# rules two\n' > "$CLONE/CLAUDE.md"
next_release v1.1.0
( cd "$UV" && $GIT commit -q --allow-empty -m "a commit of my own" ) >/dev/null 2>&1
update --apply
chk "own commits: the refusal names the hand merge"             '[ "$rc" = 1 ] && echo "$out" | grep -q "git merge v1.1.0"'
user_vault
printf '# rules two\n' > "$CLONE/CLAUDE.md"
printf '# query two\n' > "$CLONE/.claude/skills/query/SKILL.md"
next_release v1.1.0
HEAD22="$(git -C "$UV" rev-parse HEAD)"
chmod a-w "$UV/.claude/skills/query"   # a folder git cannot write stops the merge after it has begun
update --apply
chmod u+w "$UV/.claude/skills/query"
chk "midway: a merge stopped partway exits 1 at the old commit"  '[ "$rc" = 1 ] && [ "$(git -C "$UV" rev-parse HEAD)" = "$HEAD22" ]'
chk "control: a working file did change, so nothing changed would be false" 'grep -q "rules two" "$UV/CLAUDE.md"'
chk "midway: the message says working files may have changed"    'echo "$out" | grep -q "the update failed; working files may have changed" && ! echo "$out" | grep -q "nothing changed"'

echo "== 24) a separate clone: a vault that is itself a clone refuses; stale files are listed, never deleted =="
user_vault
printf '# rules two\n' > "$CLONE/CLAUDE.md"
next_release v1.1.0
H24="$(hash_of "$UV/CLAUDE.md")"
out="$(env HOME="$ROOT/home" bash "$UPD" --pull "$CLONE" --apply 2>&1)"; rc=$?
chk "mix: a vault cloned from the release refuses a second clone" '[ "$rc" = 1 ] && echo "$out" | grep -q "this vault is itself a clone of the release"'
chk "mix: the refusal gives the command that works"             'echo "$out" | grep -qF -- "--pull \"$(cd "$UV" && pwd)\" --apply"'
chk "mix: nothing was copied"                                   '[ "$(hash_of "$UV/CLAUDE.md")" = "$H24" ]'
setup_published
mkdir -p "$V/.claude/skills/retired" "$V/.claude/agents"; printf '# gone from the release\n' > "$V/.claude/skills/retired/SKILL.md"; printf '# gone\n' > "$V/.claude/agents/retired-helper.md"
out="$(bash "$SCRIPT" --pull "$CLONE" 2>&1)"
chk "stale: a skill the release dropped is listed"              'echo "$out" | grep -qE "stale +.claude/skills/retired"'
chk "stale: a helper the release dropped is listed"             'echo "$out" | grep -qE "stale +.claude/agents/retired-helper.md"'
chk "stale: the skill the export leaves out is never listed"    '! echo "$out" | grep -q "stale .*$EXCLUDED_SKILL"'
bash "$SCRIPT" --pull "$CLONE" --apply >/dev/null 2>&1; rc=$?
chk "stale: an apply deletes neither"                           '[ "$rc" = 0 ] && [ -f "$V/.claude/skills/retired/SKILL.md" ] && [ -f "$V/.claude/agents/retired-helper.md" ]'
chk "control: a separate vault still pulls"                     'echo "$out" | grep -q "PREVIEW only"'
setup_published
# A second clone moves the release on, so the update starts from the older hook list.
OTHER="$ROOT/other"
$GIT clone -q "$REMOTE" "$OTHER" >/dev/null 2>&1
mkdir -p "$OTHER/.claude/hooks"
printf 'arrives-now.py\n' >> "$OTHER/.claude/skills/export-template/payload/shipped-hooks.txt"
printf '# new in the release\n' > "$OTHER/.claude/hooks/arrives-now.py"; printf '# off the list\n' > "$OTHER/.claude/hooks/off-the-list.py"
( cd "$OTHER" && $GIT add -A && $GIT add -f .claude/hooks && $GIT commit -qm "a new hook" && $GIT push -q origin main ) >/dev/null 2>&1
chk "fixture: the clone still holds the older hook list"        '! grep -q arrives-now "$CLONE/.claude/skills/export-template/payload/shipped-hooks.txt"'
out="$(bash "$SCRIPT" --pull "$CLONE" --apply 2>&1)"; rc=$?
chk "hooks: a hook new in the release arrives in that same update" '[ "$rc" = 0 ] && [ -f "$V/.claude/hooks/arrives-now.py" ]'
chk "control: a hook off the release's list stays out"          '[ -f "$CLONE/.claude/hooks/off-the-list.py" ] && [ ! -e "$V/.claude/hooks/off-the-list.py" ]'

echo "== 25) the last leg: an update moves no byte of the user's layer, and the same check sees one that moved =="
user_vault
printf '# rules two\n' > "$CLONE/CLAUDE.md"
next_release v1.1.0
printf '# my note\n' > "$UV/wiki/my-note.md"; mkdir -p "$UV/.claude/skills/my-own"; printf '# mine\n' > "$UV/.claude/skills/my-own/SKILL.md"
layer_sums(){ git -C "$UV" ls-files -z --others --ignored --exclude-standard | ( cd "$UV" && xargs -0 python3 -B -c 'import hashlib, sys
for p in sorted(sys.argv[1:]):
    with open(p, "rb") as fh:
        print(hashlib.sha256(fh.read()).hexdigest(), p)' ); }
L25="$(layer_sums)"
update --apply
chk "last leg: the update exits 0 and reaches the release"      '[ "$rc" = 0 ] && grep -q "rules two" "$UV/CLAUDE.md"'
chk "last leg: control: the manifest holds the user's files"    'printf "%s\n" "$L25" | grep -q "wiki/my-note.md" && printf "%s\n" "$L25" | grep -q "CUSTOMISATION.md" && printf "%s\n" "$L25" | grep -q ".claude/skills/my-own/SKILL.md"'
chk "last leg: no file of the user's layer moved a byte"        '[ "$(layer_sums)" = "$L25" ]'
printf 'x' >> "$UV/wiki/my-note.md"
chk "control: one byte changed in the same folder is caught"    '[ "$(layer_sums)" != "$L25" ]'

echo
echo "================  RESULT: $PASS passed, $FAIL failed  ================"
rm -rf "$ROOT" "$SNAP"
[ "$FAIL" -eq 0 ]
