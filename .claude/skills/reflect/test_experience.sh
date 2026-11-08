#!/usr/bin/env bash
# test_experience.sh — regression fixtures for the experience checks: the reach check (lint Step 2h),
# the monthly line (deep-lint Step 4a), the use counter (reflect Step 7) and the recall probe's
# scorer and copy. Each check warns or prints; none blocks, so each leg is a case that must fire and
# a case that must not, on a fixture under a fresh mktemp -d. The vault is never touched, no model
# is called, and every fixture is removed at exit. Each script's own stdout-only claim is tested on
# a checksum of its fixture before and after.
# Run:  bash test_experience.sh      (exit 0 = every leg passed)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REACH="$HERE/../lint/check-experience-reach.py"
LINE="$HERE/../deep-lint/experience-line.py"
USES="$HERE/experience-uses.py"
PROBE="$HERE/recall-probe.py"
PY="python3 -B"
TMP="$(mktemp -d)" || exit 2
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); printf '    ok   — %s\n' "$1"; }
no(){ FAIL=$((FAIL+1)); printf '  FAIL   — %s\n' "$1"; }
# has <name> <expected exit> <pattern> <command...>: the exit and a line matching the pattern
has(){ local name="$1" want="$2" pat="$3"; shift 3; local out rc
  out="$("$@" 2>&1)"; rc=$?
  if [ "$rc" = "$want" ] && printf '%s\n' "$out" | grep -q -- "$pat"; then ok "$name"
  else no "$name (exit $rc, wanted $want; pattern: $pat)"; printf '%s\n' "$out" | tail -4 | sed 's/^/        /'; fi; }
# hasnt <name> <expected exit> <pattern> <command...>: the exit, and no line matching the pattern
hasnt(){ local name="$1" want="$2" pat="$3"; shift 3; local out rc
  out="$("$@" 2>&1)"; rc=$?
  if [ "$rc" = "$want" ] && ! printf '%s\n' "$out" | grep -q -- "$pat"; then ok "$name"
  else no "$name (exit $rc, wanted $want; must not show: $pat)"; printf '%s\n' "$out" | tail -4 | sed 's/^/        /'; fi; }

mkvault(){ # a two-page vault: alpha by a step pointer, beta by an always-on pointer
  local v="$1"; rm -rf "$v"; mkdir -p "$v/raw" "$v/wiki/experience" "$v/wiki/developments" "$v/.claude/skills/x"
  printf '# schema\n' > "$v/CLAUDE.md"
  printf -- '- **When I leave**: before judging, read [[beta]] whole.\n' > "$v/CUSTOMISATION.md"
  printf '**Feature:** alpha · **Moment:** m · **Read by:** `.claude/skills/x/SKILL.md` (Step 4) · **Multi-agent pattern:** one agent\n' > "$v/wiki/experience/alpha.md"
  printf '**Feature:** beta · **Moment:** m · **Read by:** `CUSTOMISATION.md` ("When I leave") · **Multi-agent pattern:** one agent\n' > "$v/wiki/experience/beta.md"
  printf '### Step 4 — Decide\n\n**Experience:** before the decision, and before changing how it is made, read `wiki/experience/alpha.md` whole.\n\n### Step 5 — Next\n\nOther text.\n\n### Step 5b — Last\n\nMore.\n' > "$v/.claude/skills/x/SKILL.md"
}
sum(){ (cd "$1" && find . -type f -print0 | sort -z | xargs -0 shasum -a 256 | shasum -a 256); }

printf '\n--- reach check ---\n'
V="$TMP/v"; mkvault "$V"; before="$(sum "$V")"
has "a clean vault pairs both pages and stays silent" 0 'pages 2 · readers declared 2 · pointers found 2 · pairs matched 2 · warnings 0' $PY "$REACH" --vault "$V"
[ "$before" = "$(sum "$V")" ] && ok "the reach check writes nothing" || no "the reach check wrote to its fixture"
mkvault "$V"; printf 'gone\n' > "$V/.claude/skills/x/SKILL.md"
has "a lost pointer warns" 1 'WARN pointer missing: .claude/skills/x/SKILL.md -> wiki/experience/alpha.md' $PY "$REACH" --vault "$V"
mkvault "$V"; printf '### Step 9 — Elsewhere\n\n**Experience:** before the decision, and before changing how it is made, read `wiki/experience/alpha.md` whole.\n' > "$V/.claude/skills/x/SKILL.md"
has "a pointer under the wrong step warns" 1 'WARN pointer outside its declared step' $PY "$REACH" --vault "$V"
mkvault "$V"; sed -i '' 's/(Step 4)/(Step 5)/' "$V/wiki/experience/alpha.md"; printf '### Step 5b — Last\n\n**Experience:** before the decision, and before changing how it is made, read `wiki/experience/alpha.md` whole.\n' > "$V/.claude/skills/x/SKILL.md"
has "Step 5 does not match Step 5b" 1 'WARN pointer outside its declared step' $PY "$REACH" --vault "$V"
mkvault "$V"; rm "$V/wiki/experience/alpha.md"
has "a pointer to a missing page warns" 1 'WARN page missing: .claude/skills/x/SKILL.md -> wiki/experience/alpha.md' $PY "$REACH" --vault "$V"
mkvault "$V"; mkdir -p "$V/.claude/skills/y"; printf '### Step 1\n\n**Experience:** before it, and before changing how it is made, read `wiki/experience/alpha.md` whole.\n' > "$V/.claude/skills/y/SKILL.md"
has "an undeclared reader warns" 1 'WARN undeclared reader: .claude/skills/y/SKILL.md' $PY "$REACH" --vault "$V"
mkvault "$V"; cp "$V/wiki/experience/alpha.md" "$V/wiki/experience/Bad_Name.md"
has "a name outside kebab-case warns" 1 'kebab-case' $PY "$REACH" --vault "$V"
mkvault "$V"; printf 'no header\n' > "$V/wiki/experience/alpha.md"
has "a page with no header warns" 1 'WARN no header line' $PY "$REACH" --vault "$V"
mkvault "$V"; printf 'See wiki/experience/alpha.md for it.\n' >> "$V/.claude/skills/x/SKILL.md"
has "a page named outside a pointer warns" 1 'WARN unsupported mention' $PY "$REACH" --vault "$V"
mkvault "$V"; printf 'cat wiki/experience/*.md\n' >> "$V/.claude/skills/x/SKILL.md"
has "a whole-folder glob warns" 1 'WARN whole-folder read' $PY "$REACH" --vault "$V"
mkvault "$V"; printf 'The bound covers `wiki/experience/` and `wiki/experience/<feature>.md`.\n' >> "$V/.claude/skills/x/SKILL.md"
hasnt "a plain folder mention is no read" 0 'WARN' $PY "$REACH" --vault "$V"
mkvault "$V"; printf '### Step 4 — Decide\n\n<!-- **Experience:** before the decision, and before changing how it is made, read `wiki/experience/alpha.md` whole. -->\n' > "$V/.claude/skills/x/SKILL.md"
has "a pointer inside a comment does not count" 1 'WARN pointer missing' $PY "$REACH" --vault "$V"
mkvault "$V"; printf '### Step 4 — Decide\n\n```\n**Experience:** before the decision, and before changing how it is made, read `wiki/experience/alpha.md` whole.\n```\n' > "$V/.claude/skills/x/SKILL.md"
has "a pointer inside a fence does not count" 1 'WARN pointer missing' $PY "$REACH" --vault "$V"
mkvault "$V"; printf '### Step 4 — Decide\n\n**Experience:** before the decision, and before changing\nhow it is made, read `wiki/experience/alpha.md`\nwhole.\n' > "$V/.claude/skills/x/SKILL.md"
has "a pointer wrapped across lines pairs" 0 'pairs matched 2' $PY "$REACH" --vault "$V"
mkvault "$V"; printf '### Step 4 — Decide\n\n**Experience:** read `wiki/experience/alpha.md` when you like.\n' > "$V/.claude/skills/x/SKILL.md"
has "a pointer without its form warns" 1 'WARN pointer form' $PY "$REACH" --vault "$V"
mkvault "$V"; printf 'Other line.\n' > "$V/CUSTOMISATION.md"
has "a lost always-on pointer warns" 1 'WARN pointer missing: CUSTOMISATION.md' $PY "$REACH" --vault "$V"
mkvault "$V"; rm "$V/CUSTOMISATION.md"
has "an absent CUSTOMISATION.md a page declares warns, never a crash" 1 'WARN reader unreadable: CUSTOMISATION.md' $PY "$REACH" --vault "$V"
V2="$TMP/v2"; rm -rf "$V2"; mkdir -p "$V2/raw" "$V2/wiki" "$V2/.claude"; printf '# schema\n' > "$V2/CLAUDE.md"
has "no pages and no pointers prints a state" 0 'a state; nothing compared' $PY "$REACH" --vault "$V2"
has "a fresh vault without CUSTOMISATION.md is no failure" 0 'warnings 0' $PY "$REACH" --vault "$V2"
mkdir -p "$TMP/notvault"
has "a root that is no vault exits 2" 2 'not a vault root' $PY "$REACH" --vault "$TMP/notvault"
has "an unknown flag exits 2" 2 'usage:' $PY "$REACH" --nonsense
mkvault "$V"; mkdir -p "$V/.claude/skills/z"; printf 'the path wiki/experience/alpha.md in a test\n' > "$V/.claude/skills/z/test_z.sh"
hasnt "a test file is out of scope" 0 'WARN' $PY "$REACH" --vault "$V"
mkvault "$V"; for n in 1 2 3 4 5; do printf '**Feature:** p%s · **Moment:** m · **Read by:** `CUSTOMISATION.md` ("When I leave") · **Multi-agent pattern:** one agent\n' "$n" > "$V/wiki/experience/p$n.md"; printf -- '- **When I leave** %s: read [[p%s]] whole.\n' "$n" "$n" >> "$V/CUSTOMISATION.md"; done
has "five always-on pointers list a placement review" 0 'LIST always-on pointers' $PY "$REACH" --vault "$V"

printf '\n--- monthly line ---\n'
mkline(){ local v="$1"; rm -rf "$v"; mkdir -p "$v/raw" "$v/wiki/experience" "$v/wiki/developments"
  printf '| experience pages (`wiki/experience/`; a group name) | text |\n' > "$v/wiki/developments/check-lifecycle.md"
  printf '## [2026-01-01] deep-lint | a run\n- **Changed**: nothing\n' > "$v/wiki/log.md"
  printf '**Feature:** a · **Moment:** m · **Read by:** `x` (y) · **Multi-agent pattern:** one agent\n\n## Rules\nE1. Do it. (lesson · 2099-01-01 · taught · [[x]])\n\n## Measures\n**Measures:** reach changed 2026-01-01 · probe 2026-01-02 on a in b, no gross failure · entry added 2026-01-01 · uses 0 and repeats 0 since 2026-01-01 · last label E1\n' > "$v/wiki/experience/a.md"; }
L="$TMP/l"; mkline "$L"; before="$(sum "$L")"
has "a first run lists growth as unmeasured" 0 'LIST growth unmeasured' $PY "$LINE" --vault "$L"
hasnt "a clean page lists nothing else" 0 'LIST [^g]' $PY "$LINE" --vault "$L"
[ "$before" = "$(sum "$L")" ] && ok "the monthly line writes nothing" || no "the monthly line wrote to its fixture"
payload="$($PY "$LINE" --vault "$L" | sed -n 's/^BASELINE-APPEND //p')"
[ -n "$payload" ] && ok "a clean run prints its baseline" || no "no baseline printed"
{ printf '## [2026-02-01] deep-lint | a completed run\n%s\n' "$payload"; } >> "$L/wiki/log.md"
hasnt "the next run measures from that baseline" 0 'growth unmeasured' $PY "$LINE" --vault "$L"
printf '## [2026-03-01] deep-lint | a follow-up\n- **Changed**: nothing\n' >> "$L/wiki/log.md"
has "a later section without a bullet is named and skipped" 0 'BASELINE-SKIPPED ## \[2026-03-01\]' $PY "$LINE" --vault "$L"
sed -i '' 's/^E1\. Do it\./E1. Do it, and more than before./' "$L/wiki/experience/a.md"
has "growth lists the reworded label" 0 'entries reworded: E1' $PY "$LINE" --vault "$L"
printf '## [2026-04-01] deep-lint | a broken run\n- **Experience baselines**: {not json\n' >> "$L/wiki/log.md"
has "a malformed latest baseline stays unmeasured" 0 'growth unmeasured: wiki/experience/a.md (malformed latest baseline)' $PY "$LINE" --vault "$L"
mkline "$L"; payload="$($PY "$LINE" --vault "$L" | sed -n 's/^BASELINE-APPEND //p')"; printf '## [2026-02-01] deep-lint | a completed run\n%s\n' "$payload" >> "$L/wiki/log.md"
sed -i '' 's/(lesson · 2099-01-01/(owner · 2026-01-01/' "$L/wiki/experience/a.md"
has "a lesson relabelled owner lists" 0 'owner entry new since the baseline' $PY "$LINE" --vault "$L"
mkline "$L"; sed -i '' 's/(lesson · 2099-01-01/(owner · 2026-01-01/' "$L/wiki/experience/a.md"
payload="$($PY "$LINE" --vault "$L" | sed -n 's/^BASELINE-APPEND //p')"
printf '## [2026-02-01] deep-lint | a completed run\n%s\n' "$payload" >> "$L/wiki/log.md"
hasnt "an unchanged owner entry lists nothing" 0 'owner entry' $PY "$LINE" --vault "$L"
sed -i '' 's/^E1\. Do it\./E1. Do it differently./' "$L/wiki/experience/a.md"
has "a changed owner entry lists, whatever the size" 0 'owner entry changed since the baseline' $PY "$LINE" --vault "$L"
sed -i '' 's/^E1\. Do it differently\./E1. Do it./; s/(owner · 2026-01-01/(lesson · 2099-01-01/' "$L/wiki/experience/a.md"
has "a relabelled owner entry lists" 0 'owner entry relabelled since the baseline' $PY "$LINE" --vault "$L"
sed -i '' '/^E1\. /d' "$L/wiki/experience/a.md"
has "a removed owner entry lists" 0 'owner entry gone since the baseline' $PY "$LINE" --vault "$L"
mkline "$L"; sed -i '' 's/(lesson · 2099-01-01/(owner · 2026-01-01 provisional/' "$L/wiki/experience/a.md"
has "a provisional owner entry lists" 0 'owner entry dated provisional' $PY "$LINE" --vault "$L"
mkline "$L"; sed -i '' 's/(lesson · 2099-01-01/(lesson · 2020-01-01/' "$L/wiki/experience/a.md"
has "a lesson with no date in twelve months lists" 0 'no date in twelve months' $PY "$LINE" --vault "$L"
mkline "$L"; sed -i '' 's/probe 2026-01-02 on a in b, no gross failure/probe not yet run/' "$L/wiki/experience/a.md"
has "a probe not yet run lists as due" 0 'probe older than the last reach change' $PY "$LINE" --vault "$L"
mkline "$L"; sed -i '' 's/no gross failure/gross failure: it never read the page/' "$L/wiki/experience/a.md"
has "a gross failure lists" 0 'probe saw gross failure' $PY "$LINE" --vault "$L"
mkline "$L"; sed -i '' 's/last label E1/last label E0/' "$L/wiki/experience/a.md"
has "an entry above the last label lists" 0 'above the last label issued' $PY "$LINE" --vault "$L"
mkline "$L"; sed -i '' 's/^E1\. //' "$L/wiki/experience/a.md"
has "a page with no labelled entry lists" 0 'no entry in the label form' $PY "$LINE" --vault "$L"
mkline "$L"; sed -i '' 's/ · last label E1//' "$L/wiki/experience/a.md"
has "a Measures line without its last label lists" 0 'without its last label' $PY "$LINE" --vault "$L"
mkline "$L"; rm "$L/wiki/experience/a.md"
has "no pages prints a state" 0 'no pages (a state' $PY "$LINE" --vault "$L"
has "a root that is no vault exits 2" 2 'not a vault root' $PY "$LINE" --vault "$TMP/notvault"
mkline "$L"; rm "$L/wiki/log.md"
has "an unreadable log exits 2 and withholds its baseline" 2 'PROBE FAILED: cannot read wiki/log.md' $PY "$LINE" --vault "$L"
hasnt "a failed run prints no baseline" 2 'BASELINE-APPEND' $PY "$LINE" --vault "$L"

printf '\n--- use counter ---\n'
U="$TMP/u"; rm -rf "$U"; mkdir -p "$U/raw" "$U/wiki/experience"; printf 'x\n' > "$U/wiki/experience/alpha.md"; printf 'x\n' > "$U/wiki/experience/beta.md"
T="$TMP/turns.md"
cat > "$T" <<'TURNS'
# Transcript extraction · session s

## turn 1 · human · t

the page (alpha) says so

## turn 2 · assistant · tool calls · t

- Read: /v/wiki/experience/alpha.md

## turn 3 · assistant · t

I read the page (alpha) and applied its entries on one thing and another (E1 and E2).

- Bash: echo I read the page (alpha)

## turn 4 · assistant · t

- Read: a prose bullet naming the page (beta), none applied.

Then more prose.

## turn 5 · assistant · tool calls · t

- Bash: echo the page (alpha) again

## turn 6 · assistant · tool calls · t

- Read: /v/wiki/experience/beta.md
TURNS
before="$(sum "$U")"
has "a prose note counts, with its labels" 0 'NOTE alpha turn 3 t (E1 E2)' $PY "$USES" --vault "$U" --turns "$T" --notes
has "tool lines and a human quotation do not count" 0 'COUNT alpha: uses 1, of them none applied 0 (tool-line hits set aside: 2)' $PY "$USES" --vault "$U" --turns "$T"
has "a prose bullet shaped like a tool line stays prose" 0 'NOTE beta turn 4 t (none applied)' $PY "$USES" --vault "$U" --turns "$T" --notes
[ "$before" = "$(sum "$U")" ] && ok "the use counter writes nothing" || no "the use counter wrote to its fixture"
hasnt "--from-turn skips a counted span" 0 'NOTE alpha' $PY "$USES" --vault "$U" --turns "$T" --from-turn 3 --notes
has "--from-turn prints what it scanned" 0 'turns scanned 3 of 6 (from turn 3)' $PY "$USES" --vault "$U" --turns "$T" --from-turn 3
printf '## turn 1 · assistant · tool calls · t\n\n- Read: /v/wiki/experience/alpha.md\n' > "$TMP/t1.md"
has "a read with no note is a mismatch" 0 'MISMATCH alpha: read with no note' $PY "$USES" --vault "$U" --turns "$TMP/t1.md"
printf '## turn 1 · assistant · t\n\nThe page (alpha) is a page we might discuss.\n' > "$TMP/t2b.md"
hasnt "a sentence merely discussing a page is no note" 0 'NOTE alpha' $PY "$USES" --vault "$U" --turns "$TMP/t2b.md" --notes
printf '## turn 1 · assistant · t\n\nI read the leave page (alpha) first.\n' > "$TMP/t2c.md"
has "a note saying only that it read the page counts" 0 'NOTE alpha' $PY "$USES" --vault "$U" --turns "$TMP/t2c.md" --notes
printf '## turn 1 · assistant · t\n\nThe helper read the page (alpha) and applied its entry (E1).\n' > "$TMP/t2.md"
has "a note with no read is a mismatch" 0 'MISMATCH alpha: note with no read' $PY "$USES" --vault "$U" --turns "$TMP/t2.md"
printf 'no headings here\n' > "$TMP/t3.md"
has "an extraction with no turn headings exits 2" 2 'no turn headings' $PY "$USES" --vault "$U" --turns "$TMP/t3.md"
has "a missing extraction exits 2" 2 'cannot read' $PY "$USES" --vault "$U" --turns "$TMP/none.md"
has "neither --turns nor --all exits 2" 2 'usage:' $PY "$USES" --vault "$U"
has "both --turns and --all exits 2" 2 'usage:' $PY "$USES" --vault "$U" --turns "$T" --all
has "a missing transcript folder exits 2" 2 'no transcript folder' $PY "$USES" --vault "$U" --all --projects "$TMP/noproject"

printf '\n--- use counter, monthly sweep ---\n'
PJ="$TMP/projects/-fixture"; mkdir -p "$PJ"
note(){ printf '{"type":"assistant","timestamp":"%s","message":{"role":"assistant","content":[{"type":"text","text":"%s"}]}}\n' "$1" "$2"; }
{ printf '{"type":"user","timestamp":"2026-03-01T10:00:00.000Z","message":{"role":"user","content":"hello"}}\n'
  note 2026-03-01T10:01:00.000Z 'I read the page (alpha) and applied its entry on one thing (E1).'
  note 2026-03-03T10:01:00.000Z 'I read the page (alpha) and applied its entry on another (E2).'; } > "$PJ/aaaa1111-0000-4000-8000-000000000001.jsonl"
touch -t 202603031200 "$PJ/aaaa1111-0000-4000-8000-000000000001.jsonl"
printf '**Measures:** reach changed 2026-03-02 · uses 0 and repeats 0 since 2026-03-02\n' > "$U/wiki/experience/alpha.md"
has "a note before a page's date is left out" 0 'COUNT alpha: uses 1' $PY "$USES" --vault "$U" --all --projects "$PJ"
first="$($PY "$USES" --vault "$U" --all --projects "$PJ" | grep '^COUNT')"; second="$($PY "$USES" --vault "$U" --all --projects "$PJ" | grep '^COUNT')"
[ "$first" = "$second" ] && ok "a rerun prints the same count" || no "a rerun changed the count"
printf '**Measures:** reach changed 2026-01-01 · uses 0 and repeats 0 since 2026-01-01\n' > "$U/wiki/experience/alpha.md"
has "both notes count from an older date" 0 'COUNT alpha: uses 2' $PY "$USES" --vault "$U" --all --projects "$PJ"
has "a page older than the oldest transcript prints a gap" 0 'GAP alpha: its count starts 2026-01-01' $PY "$USES" --vault "$U" --all --projects "$PJ"
{ printf '{"type":"assistant","timestamp":"2026-03-04T10:00:00.000Z","message":{"role":"assistant","content":[{"type":"tool_use","id":"r","name":"Read","input":{"file_path":"/v/wiki/experience/alpha.md"}}]}}\n'; } > "$PJ/bbbb2222-0000-4000-8000-000000000002.jsonl"
has "a read with no note shows per session, whatever other sessions noted" 0 'MISMATCH alpha: read with no note in session bbbb2222' $PY "$USES" --vault "$U" --all --projects "$PJ"
rm -f "$PJ/bbbb2222-0000-4000-8000-000000000002.jsonl"
{ printf '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"I read the page (alpha) and applied it (E1)."}]}}\n'; } > "$PJ/cccc3333-0000-4000-8000-000000000003.jsonl"
has "a note in an undated turn is counted apart" 0 'undated notes 1' $PY "$USES" --vault "$U" --all --projects "$PJ"
rm -f "$PJ/cccc3333-0000-4000-8000-000000000003.jsonl"
printf 'x\n' > "$PJ/dddd4444-0000-4000-8000-000000000004.jsonl"; chmod 000 "$PJ/dddd4444-0000-4000-8000-000000000004.jsonl"
has "an unread session prints UNREAD and a lower bound" 0 'UNREAD dddd4444' $PY "$USES" --vault "$U" --all --projects "$PJ"
chmod 644 "$PJ/dddd4444-0000-4000-8000-000000000004.jsonl"; rm -f "$PJ/dddd4444-0000-4000-8000-000000000004.jsonl"

printf '\n--- recall probe, scorer and copy ---\n'
stream(){ # stream <file> <tool json or empty> <final text>
  { [ -n "$2" ] && printf '{"type":"assistant","message":{"content":[%s]}}\n' "$2"
    printf '{"type":"assistant","message":{"content":[{"type":"text","text":%s}]}}\n' "\"$3\""
    printf '{"type":"result","result":%s,"total_cost_usd":0.1}\n' "\"$3\""; } > "$1"; }
R='{"type":"tool_use","name":"Read","input":{"file_path":"/c/wiki/experience/alpha.md"}}'
R2='{"type":"tool_use","name":"Read","input":{"file_path":"/c/wiki/experience/beta.md"}}'
G='{"type":"tool_use","name":"Glob","input":{"pattern":"wiki/experience/*.md"}}'
GR='{"type":"tool_use","name":"Grep","input":{"pattern":"x","path":"wiki/experience","output_mode":"content"}}'
GN='{"type":"tool_use","name":"Grep","input":{"pattern":"x","path":"wiki/experience","output_mode":"files_with_matches"}}'
S="$TMP/s.jsonl"
stream "$S" "$R" 'Done, I read the page (alpha).'
has "a fitting task that reads its page and notes it passes" 0 '^PASS' $PY "$PROBE" --score "$S" --kind fitting --page alpha
stream "$S" "$R,$R2" 'Done (alpha).'
has "reading another page fails" 1 'read another page: beta' $PY "$PROBE" --score "$S" --kind fitting --page alpha
stream "$S" "$R,$G" 'Done (alpha).'
has "a glob listing the folder's names passes" 0 '^PASS' $PY "$PROBE" --score "$S" --kind fitting --page alpha
stream "$S" "$R,$GN" 'Done (alpha).'
has "a names-only grep over the folder passes" 0 '^PASS' $PY "$PROBE" --score "$S" --kind fitting --page alpha
stream "$S" "$R,$GR" 'Done (alpha).'
has "a content grep over the folder fails" 1 'folder touched' $PY "$PROBE" --score "$S" --kind fitting --page alpha
stream "$S" "" 'Done (alpha).'
has "a task that never read its page fails" 1 'did not read alpha' $PY "$PROBE" --score "$S" --kind fitting --page alpha
stream "$S" "$R" 'Done.'
has "a fitting reply with no use note fails" 1 'no use note' $PY "$PROBE" --score "$S" --kind fitting --page alpha
cat > "$S" <<'STREAM'
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"g1","name":"Grep","input":{"pattern":"headline"}}]}}
{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"g1","content":"wiki/experience/alpha.md:3: a headline"}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"r1","name":"Read","input":{"file_path":"/c/wiki/experience/alpha.md"}}]}}
{"type":"result","result":"Done (alpha)."}
STREAM
has "a page first surfaced by a content search fails" 1 'not through its pointer' $PY "$PROBE" --score "$S" --kind fitting --page alpha
cat > "$S" <<'STREAM'
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"g1","name":"Glob","input":{"pattern":"wiki/**/alpha*.md"}}]}}
{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"g1","content":"wiki/experience/alpha.md"}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"r1","name":"Read","input":{"file_path":"/c/wiki/experience/alpha.md"}}]}}
{"type":"result","result":"Done (alpha)."}
STREAM
has "a glob on the page's own name is its pointer's route" 0 '^PASS' $PY "$PROBE" --score "$S" --kind fitting --page alpha
cat > "$S" <<'STREAM'
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"k1","name":"Read","input":{"file_path":"/c/.claude/skills/x/SKILL.md"}}]}}
{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"k1","content":"read `wiki/experience/alpha.md` whole."}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"r1","name":"Read","input":{"file_path":"/c/wiki/experience/alpha.md"}}]}}
{"type":"result","result":"Done (alpha)."}
STREAM
has "a page named in a skill it read came through its pointer" 0 '^PASS' $PY "$PROBE" --score "$S" --kind fitting --page alpha
stream "$S" "" 'An answer.'
has "an unrelated task that touches nothing passes" 0 '^PASS' $PY "$PROBE" --score "$S" --kind unrelated
stream "$S" "$R" 'An answer.'
has "an unrelated task that reads a page fails" 1 'unrelated task needs none' $PY "$PROBE" --score "$S" --kind unrelated
stream "$S" "$R" 'Two lines.'
has "a helper leg needs its read and no note in the reply" 0 '^PASS' $PY "$PROBE" --score "$S" --kind helper --page alpha
BG='{"type":"tool_use","name":"Grep","input":{"pattern":"x","glob":"{wiki/experience,wiki/syntheses}/*.md","output_mode":"content"}}'
stream "$S" "$R,$BG" 'Done (alpha).'
has "a content grep through a brace glob fails" 1 'folder touched' $PY "$PROBE" --score "$S" --kind fitting --page alpha
cat > "$S" <<'STREAM'
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"g1","name":"Grep","input":{"pattern":"headline"}}]}}
{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"g1","content":"index.md:3: [[alpha]] a headline"}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"r1","name":"Read","input":{"file_path":"/c/wiki/experience/alpha.md"}}]}}
{"type":"result","result":"Done (alpha)."}
STREAM
has "a page surfaced as a wikilink by a search fails" 1 'not through its pointer' $PY "$PROBE" --score "$S" --kind fitting --page alpha
printf '{"type":"assistant","message":{"content":[]}}\n' > "$S"
has "a stream with no result record exits 2" 2 'no result record' $PY "$PROBE" --score "$S" --kind unrelated
printf '{"decoys":["dee"],"tasks":[{"id":"U1","kind":"unrelated","prompt":"hi"}]}' > "$TMP/tasks.json"
C="$TMP/c"; mkvault "$V"; mkdir -p "$V/.claude/hooks"; printf '{}' > "$V/.claude/settings.json"; printf '## Experience\n\n- [[alpha]] — a.\n' > "$V/wiki/index.md"; before="$(sum "$V")"
has "a dry run prints the headless call" 0 'DRY U1 unrelated: claude -p' $PY "$PROBE" --vault "$V" --tasks "$TMP/tasks.json" --out "$C" --dry-run
[ "$before" = "$(sum "$V")" ] && ok "the probe leaves the vault untouched" || no "the probe changed its vault"
[ -f "$C/copy/wiki/experience/dee.md" ] && ok "the decoy sits in the copy" || no "no decoy in the copy"
[ ! -f "$V/wiki/experience/dee.md" ] && ok "the decoy stays out of the vault" || no "the decoy reached the vault"
grep -q '\[\[dee\]\]' "$C/copy/wiki/index.md" && ok "the copy's index lists the decoy" || no "the copy's index lacks the decoy"
[ ! -e "$C/copy/.claude/settings.json" ] && [ ! -e "$C/copy/.claude/hooks" ] && ok "the copy carries no settings or hooks" || no "settings or hooks reached the copy"
mkdir -p "$V/wiki/developments"; printf '{}' > "$V/wiki/developments/experience-recall-tasks.json"; C2="$TMP/c2"
has "a second dry run builds its copy" 0 'DRY U1' $PY "$PROBE" --vault "$V" --tasks "$TMP/tasks.json" --out "$C2" --dry-run
[ ! -e "$C2/copy/wiki/developments/experience-recall-tasks.json" ] && ok "the tasks file stays out of the copy" || no "the tasks file reached the copy"
printf '{"tasks":[{"id":"F","kind":"fitting","page":"beta","prompt":"p"}]}' > "$TMP/t3.json"
has "the no-pointer arm removes the pointer from the copy" 0 'DRY F fitting' $PY "$PROBE" --vault "$V" --tasks "$TMP/t3.json" --without-pointer beta --out "$TMP/c3" --dry-run
grep -q 'beta' "$TMP/c3/copy/CUSTOMISATION.md" && no "the pointer stayed in the copy" || ok "the pointer left the copy"
grep -q 'beta' "$V/CUSTOMISATION.md" && ok "the pointer stayed in the vault" || no "the arm changed the vault"
printf '{"tasks":[{"id":"F","kind":"fitting","page":"nosuch","prompt":"p"}]}' > "$TMP/t4.json"
has "an arm with no pointer to remove exits 2" 2 'no pointer to nosuch' $PY "$PROBE" --vault "$V" --tasks "$TMP/t4.json" --without-pointer nosuch --out "$TMP/c4" --dry-run
printf '{"decoys":["dee"],"fixture_pointers":[{"page":"dee","file":".claude/skills/x/SKILL.md","heading":"### Step 5 — Next","decision":"the next step"}],"tasks":[{"id":"U1","kind":"unrelated","prompt":"hi"}]}' > "$TMP/t5.json"
has "a fixture pointer goes under its step in the copy" 0 'DRY U1' $PY "$PROBE" --vault "$V" --tasks "$TMP/t5.json" --out "$TMP/c5" --dry-run
grep -q 'wiki/experience/dee.md' "$TMP/c5/copy/.claude/skills/x/SKILL.md" && ok "the fixture pointer sits in the copy's skill" || no "no fixture pointer in the copy"
grep -q 'wiki/experience/dee.md' "$V/.claude/skills/x/SKILL.md" && no "the fixture pointer reached the vault" || ok "the fixture pointer stayed out of the vault"
printf '{"fixture_pointers":[{"page":"dee","file":".claude/skills/x/SKILL.md","heading":"### No such step","decision":"d"}],"tasks":[{"id":"U1","kind":"unrelated","prompt":"hi"}]}' > "$TMP/t6.json"
has "a fixture heading not found exits 2" 2 'fixture heading not found once' $PY "$PROBE" --vault "$V" --tasks "$TMP/t6.json" --out "$TMP/c6" --dry-run
printf '{"tasks":[{"id":"X","kind":"odd","prompt":"p"}]}' > "$TMP/bad.json"
has "a malformed task exits 2" 2 'malformed task' $PY "$PROBE" --vault "$V" --tasks "$TMP/bad.json" --dry-run
has "a root that is no vault exits 2" 2 'not a vault root' $PY "$PROBE" --vault "$TMP/notvault" --tasks "$TMP/tasks.json"

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
