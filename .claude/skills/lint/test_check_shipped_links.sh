#!/usr/bin/env bash
# test_check_shipped_links.sh — regression fixtures for check-shipped-links.py (lint Step 2g; the publish
# gate's test suite leg 14 calls the same script). Builds throwaway trees under $TMPDIR; NEVER touches the
# vault. Run:  bash test_check_shipped_links.sh   (exit 0 = all pass; each case names what it protects).
set -uo pipefail
S="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/check-shipped-links.py"
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "    ok   — $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL   — $1"; }
F="$(mktemp -d)"; trap 'rm -rf "$F"' EXIT
# Every fixture root carries raw/ as well as wiki/: the script applies the 2026-08-26 root
# assertion (a root without both is refused with exit 2 on stderr), so a fixture without raw/
# would exercise the guard instead of the case each leg names. The wrong-root leg below keeps
# its own case by removing wiki/ from a root that does have raw/.
fresh(){ rm -rf "$F"; mkdir -p "$F/raw" "$F/wiki/x" "$F/.claude/skills/t" "$F/.claude/agents" "$F/.claude/skills/x/payload/example/wiki"
  printf 'x\n' > "$F/wiki/x/Alpha.md"
  printf -- '---\ntitle: "Beta"\naliases: [Bee, "B two"]\n---\nx\n' > "$F/wiki/Beta.md"
  printf -- '---\naliases:\n  - Gam\n---\nx\n' > "$F/wiki/x/Gamma.md"; }
# expect <name> <exit> <finding-lines> <regex the first line must match>
expect(){ local name="$1" want_rc="$2" want_dead="$3" pat="$4" out rc first dead
  out="$(python3 "$S" "$F" 2>&1)"; rc=$?; first="${out%%$'\n'*}"; dead="$(printf '%s\n' "$out" | grep -c '→')"
  if [ "$rc" = "$want_rc" ] && [ "$dead" = "$want_dead" ] && printf '%s' "$first" | grep -Eq -- "$pat"; then ok "$name"
  else no "$name  [exit $rc, findings $dead: $first]"; fi; }
sk(){ printf '%s\n' "$1" > "$F/.claude/skills/t/SKILL.md"; }

fresh; sk 'see [[Alpha]] and [[Beta|b]] and [[Delta]]'; printf 'lane [[Alpha#h]]\n' > "$F/.claude/agents/a.md"
expect "planted links in a skill file and an agent definition are findings" 1 3 'dead'
fresh; sk $'```\n[[Alpha]]\n```\n`[[Beta]]` <!-- [[Alpha]] --> [[Nope]]'
expect "links inside fences, code spans and comments are not links" 0 0 '^shipped-links: clean'
fresh; printf '[[Alpha]]\n' > "$F/.claude/skills/x/payload/example/wiki/seed.md"; sk 't'
expect "vault-shaped content bundled in a skill is not a surface" 0 0 'clean.*0 wikilinks seen'
fresh; printf '[[Beta]]\n' > "$F/.claude/skills/t/templates.md"
expect "every skill Markdown file is in scope, not only SKILL.md" 1 1 'dead'
fresh; rm -rf "$F/wiki"; sk '[[Alpha]]'
expect "no wiki/ directory is a broken premise (wrong root), never clean" 2 0 'PROBE FAILED'
fresh; rm -f "$F/wiki/x/"*.md "$F/wiki/"*.md; sk '[[Alpha]]'
expect "an empty wiki/ (fresh install, the published copy) is n/a, exit 0" 0 0 '^shipped-links: n/a'
fresh; rm -rf "$F/.claude"
expect "no shipped surfaces is a broken premise" 2 0 'PROBE FAILED'
fresh; sk $'[[x/Alpha]] [[beta]] [[Alpha.md]] ![[Beta]]\n| rule | [[Alpha\\|the alpha page]] |'
expect "path-style, case, .md, embed and table-escaped-pipe forms all resolve" 1 5 'dead'
fresh; sk '[[Alphabet]] [[x]] [[Alpha 2]]'
expect "near-miss names are not findings" 0 0 'clean'
fresh; sk '[[Bee]] [[b two|x]] [[gam]]'
expect "inline and block-list frontmatter aliases resolve, any case" 1 3 'dead'
# An inline alias list is read as YAML reads it (check-links.py's reader, kept identical here): a quoted
# alias carrying a comma is one name, and the fragment after its comma is no name at all.
fresh; printf -- '---\ntitle: "Delta"\naliases: ["Delta, Inc.", Dee]\n---\nx\n' > "$F/wiki/Delta.md"; sk '[[Delta, Inc.]] [[Inc.]]'
DOUT="$(python3 "$S" "$F" 2>&1)"; rc=$?
if [ "$rc" = 1 ] && printf '%s\n' "$DOUT" | grep -qF '→ [[Delta, Inc.]]' && ! printf '%s\n' "$DOUT" | grep -qF '→ [[Inc.]]' \
   && printf '%s\n' "$DOUT" | grep -q '^shipped-links: 1 dead'
then ok "a quoted alias carrying a comma is one name; the fragment after the comma is none"
else no "a quoted alias carrying a comma is one name  [exit $rc: $DOUT]"; fi
# A malformed list gives no name and never a traceback (closed review of 2026-10-11): text after the
# closing bracket, and an escape naming no character. A shipped link to either list's alias is then a
# target resolving nowhere here, never a finding; the link to a real page stays one.
fresh; printf -- '---\ntitle: "Epsilon"\naliases: [Eps] trailing\n---\nx\n' > "$F/wiki/Epsilon.md"
printf -- '---\ntitle: "Zeta"\naliases: ["\\U00110000", Zed]\n---\nx\n' > "$F/wiki/Zeta.md"; sk '[[Eps]] [[Zed]] [[Alpha]]'
MOUT="$(python3 "$S" "$F" 2>&1)"; rc=$?
if [ "$rc" = 1 ] && printf '%s\n' "$MOUT" | grep -q '^shipped-links: 1 dead' && ! printf '%s\n' "$MOUT" | grep -qF '→ [[Eps]]' \
   && ! printf '%s\n' "$MOUT" | grep -qF '→ [[Zed]]' && ! printf '%s\n' "$MOUT" | grep -q 'Traceback'
then ok "a malformed alias list (text after ], an escape naming no character) gives no name and no traceback"
else no "a malformed alias list gives no name and no traceback  [exit $rc: $MOUT]"; fi
# A value spread over more than one line is malformed too (second review of 2026-10-11): a flow list followed
# by a `- ` line, and a block item continued by text below it, give no name; the link to a real page stays one.
fresh; printf -- '---\ntitle: "Eta"\naliases: [Eta-one]\n- Eta-two\nupdated: 2026-10-11\n---\nx\n' > "$F/wiki/Eta.md"
printf -- '---\ntitle: "Theta"\naliases:\n  - Theta-one\n    more\nupdated: 2026-10-11\n---\nx\n' > "$F/wiki/Theta.md"
sk '[[Eta-one]] [[Eta-two]] [[Theta-one]] [[Theta-one more]] [[Alpha]]'
SOUT="$(python3 "$S" "$F" 2>&1)"; rc=$?
if [ "$rc" = 1 ] && printf '%s\n' "$SOUT" | grep -q '^shipped-links: 1 dead' && ! printf '%s\n' "$SOUT" | grep -qF '→ [[Eta-one]]' \
   && ! printf '%s\n' "$SOUT" | grep -qF '→ [[Theta-one more]]' && ! printf '%s\n' "$SOUT" | grep -q 'Traceback'
then ok "a value spread over more than one line (a - line under a flow list, text under an item) gives no name and no traceback"
else no "a value spread over more than one line gives no name and no traceback  [exit $rc: $SOUT]"; fi
fresh; printf 'i\n' > "$F/wiki/index.md"; printf 'l\n' > "$F/wiki/log.md"; printf 's\n' > "$F/wiki/Seed.md"; printf 's\n' > "$F/.claude/skills/x/payload/example/wiki/Seed.md"; sk '[[index.md]] [[log]] [[seed]]'
expect "index, log and bundled example pages ship, so links to them are not findings" 0 0 'clean.*3 shipping names excluded'
fresh; sk '[[no-such-page]] [[Alpha]]'
expect "a link dead in both copies is counted on the control line, not flagged" 1 1 '1 targets resolving nowhere here'
fresh; printf 'bad \xff byte [[Alpha]]\n' > "$F/.claude/skills/t/SKILL.md"
expect "an undecodable shipped surface is a broken premise, not a finding" 2 0 'PROBE FAILED.*cannot read'
fresh; printf 'bad \xff byte\n' > "$F/wiki/x/Odd.md"; sk '[[Alpha]]'
expect "an undecodable wiki page is tolerated (aliases only)" 1 1 'dead'
fresh; printf 'x\n' > "$F/wiki/#odd|name].md"; sk '[[Alpha]]'
expect "the self-control does not depend on vault page names" 1 1 'dead'
fresh; printf -- '---\r\naliases: [Cee]\r\n---\r\nx\r\n' > "$F/wiki/Crlf.md"; sk '[[cee]]'
expect "CRLF frontmatter aliases resolve" 1 1 'dead'
fresh; sk 'x'; mv "$F/.claude/skills/t/SKILL.md" "$F/.claude/skills/t/SKILL.md.bak"; python3 "$S" /nonexistent >/dev/null 2>&1; rc=$?
[ "$rc" = 2 ] && ok "a nonexistent root is a broken premise" || no "a nonexistent root is a broken premise [exit $rc]"
# The 2026-08-26 root assertion, swept across the lint directory 2026-09-07: raw/ AND wiki/ or
# refuse. A root holding shipped surfaces and pages but no raw/ is not a vault.
fresh; rm -rf "$F/raw"; sk '[[Alpha]]'; GOUT="$(python3 "$S" "$F" 2>&1)"; rc=$?
if [ "$rc" = 2 ] && printf '%s' "$GOUT" | grep -q 'is not a vault root (no raw/ or wiki/)'; then ok "a root with no raw/ is refused, never scanned"
else no "a root with no raw/ is refused [exit $rc: $GOUT]"; fi
# Positive control for the refusal above, on the same run: the same tree with raw/ back scans.
fresh; sk '[[Alpha]]'; COUT="$(python3 "$S" "$F" 2>&1)"; rc=$?
if [ "$rc" -ne 2 ] && printf '%s' "$COUT" | grep -q 'shipped-links:'; then ok "control: the same fixture WITH raw/ still scans (exit $rc)"
else no "control: the same fixture with raw/ still scans [exit $rc: $COUT]"; fi
# A skill the exporter's skip lines keep out of every public build is no shipped surface, for a bare
# caller too: lint's helper slice and the parity runner call this script with the root alone.
# The agent file keeps one shipped surface in each tree: with every surface skipped, the no-surfaces premise fires.
exporter(){ mkdir -p "$F/.claude/skills/export-template"; printf '%s\n' "$1" > "$F/.claude/skills/export-template/export_template.sh"; printf 'plain\n' > "$F/.claude/agents/a.md"; }
SKIPLINE='    [ "$s" = t ] && continue'
fresh; sk '[[Alpha]]'; exporter "$SKIPLINE"
expect "a skill the exporter's skip line names is not a surface, on a bare run" 0 0 'clean.*1 skill\(s\) skipped as not shipped'
# Same run's control: the skip reaches that skill alone, so a shipped skill's link beside it is still caught.
mkdir -p "$F/.claude/skills/u"; printf '[[Beta]]\n' > "$F/.claude/skills/u/SKILL.md"
expect "control: a skill the skip line does not name is still scanned" 1 1 'dead.*1 skill\(s\) skipped as not shipped'
fresh; sk '[[Alpha]]'; exporter '    # [ "$s" = t ] && continue'
expect "control: a commented-out skip line skips nothing" 1 1 'dead.*0 skill\(s\) skipped as not shipped'
fresh; sk '[[Alpha]]'; exporter '    [ "$s" = t ] && echo continue'
expect "control: a line of another shape skips nothing" 1 1 'dead.*0 skill\(s\) skipped as not shipped'
fresh; sk '[[Alpha]]'
expect "control: a tree with no exporter skips nothing" 1 1 'dead.*0 skill\(s\) skipped as not shipped'
fresh; sk '[[Alpha]]'; exporter "$SKIPLINE"; XOUT="$(python3 "$S" --skip-skill t "$F" 2>&1)"; rc=$?
if [ "$rc" = 0 ] && printf '%s' "$XOUT" | grep -q '1 skill(s) skipped as not shipped'; then ok "a skill named by the exporter and by --skip-skill counts once"
else no "a skill named both ways counts once  [exit $rc: $XOUT]"; fi
fresh; sk '[[Alpha]]'; mkdir -p "$F/.claude/skills/u"; printf '[[Beta]]\n' > "$F/.claude/skills/u/SKILL.md"; exporter "$SKIPLINE"
YOUT="$(python3 "$S" --skip-skill u "$F" 2>&1)"; rc=$?
if [ "$rc" = 0 ] && printf '%s' "$YOUT" | grep -q '2 skill(s) skipped as not shipped'; then ok "--skip-skill adds to the exporter's list and never replaces it"
else no "--skip-skill adds to the exporter's list  [exit $rc: $YOUT]"; fi
fresh; sk '[[Alpha]]'; mkdir -p "$F/.claude/skills/export-template"; printf 'bad \xff byte\n' > "$F/.claude/skills/export-template/export_template.sh"
expect "an undecodable exporter is a broken premise, never a run with no skips" 2 0 'PROBE FAILED.*cannot read'
echo "================  RESULT: $PASS passed, $FAIL failed  ================"
[ "$FAIL" -eq 0 ]
