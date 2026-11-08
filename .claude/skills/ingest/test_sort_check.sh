#!/bin/sh
# test_sort_check.sh — suite for sort_check.py, the ingest Step 6 sort check (pre, post, links).
# Every fixture sits under one mktemp -d and is removed on exit; the vault is never touched. The
# fixture's raw stem equals its source slug and nine page lines link that stem bare, the shape in
# which a link-aware move rewrites bare links into path links. The sort is run as Step 6 states it:
# pre over every file, its plan recorded in the ledger as a `sort_planned` checkpoint before any
# move, `mv -n` for each MOVE line, the printed post command, and a `sorted` ledger line only after
# post exits 0. An interrupted sort is recovered as Step 6 states it, from the ledger alone: the
# recorded plan read back with a parser, pre over the complete pair with its recorded prefixes, then
# the same moves, post and record. The last legs prove the script writes nothing.
# Run:  sh test_sort_check.sh [path/to/sort_check.py]      (last line PASS n/n or FAIL k/n)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
S=${1:-"$HERE/sort_check.py"}
PY=${PYTHON:-python3}
export PYTHONDONTWRITEBYTECODE=1
T=$(mktemp -d "${TMPDIR:-/tmp}/sort-check-suite.XXXXXX")
trap 'chmod -R u+w "$T"; rm -rf "$T"' EXIT HUP INT TERM
PASS=0; FAIL=0
ok() { PASS=$((PASS+1)); echo "ok   $1"; }
no() { FAIL=$((FAIL+1)); echo "FAIL $1"; }
has() { case "$1" in *"$2"*) return 0;; esac; return 1; }
count() { printf '%s\n' "$1" | grep -c -- "$2"; }
manifest() { find "$1" -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum | LC_ALL=C sort; }
HOME_BEFORE=$(manifest "$HERE")

# build <dir>: a fixture vault whose raw pair example-lab.md / example-lab.pdf sits in the inbox and whose
# source page shares the raw stem; nine page lines link that stem bare, with no path.
build() {
  "$PY" -B - "$1" <<'PY_BUILD_FIXTURE'
import os, sys
root = sys.argv[1]
o, c = "[" * 2, "]" * 2
files = {
    "raw/example-lab.md": "---\nconverted_from: example-lab.pdf\nconverted_by: markitdown\n---\n\n# Example Lab\n\nA lab.\n",
    "raw/example-lab.pdf": "%PDF-1.4 fixture bytes\n",
    "wiki/sources/example-lab.md": "---\ntitle: \"Source: Example Lab\"\nsources: [raw/4-webinfo/example-lab.md, raw/4-webinfo/example-lab.pdf]\n---\n\n## Related\n- " + o + "Example Lab" + c + "\n",
    "wiki/entities/Example Lab.md": "## Key Points\n- Compiled in " + o + "example-lab" + c + ".\n- Its source page: " + o + "example-lab|the capture" + c + ".\n",
    "wiki/index.md": "## Sources\n- " + o + "example-lab" + c + " — the lab's page\n## Entities\n- " + o + "Example Lab" + c + " — a lab, see " + o + "example-lab" + c + "\n",
    "wiki/concepts/Alpha.md": "See " + o + "example-lab" + c + ".\n",
    "wiki/concepts/Beta.md": "See " + o + "example-lab|EXAMPLE" + c + ".\n",
    "wiki/models/Gamma.md": "## Appears in\n- " + o + "example-lab" + c + "\n",
    "wiki/maps/home.md": "| page | note |\n|---|---|\n| " + o + "example-lab\\|EXAMPLE" + c + " | lab |\n",
    "wiki/developments/delta.md": "Embedded: !" + o + "example-lab" + c + "\n",
}
for rel, text in files.items():
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
for folder in ("raw/2-papers", "raw/4-webinfo"):
    os.makedirs(os.path.join(root, folder), exist_ok=True)
PY_BUILD_FIXTURE
  printf '{"event":"run_open","run":"run-fixture"}\n' > "$1/ledger.jsonl"
}
sorted_lines() { grep -c '"stage":"sorted"' "$1/ledger.jsonl"; }
# The ledger line Step 6 appends before any move, in the skill's own printf format (S30a pins the two
# together); record_plan <vault> <plan> fills its slots for the fixture.
PLAN_FORMAT='{"ts":"%s","event":"checkpoint","run":"<run>","lane":"<lane>","stage":"sort_planned","source":"<source>","post":%s}\n'
record_plan() {
  printf "$(printf '%s' "$PLAN_FORMAT" | sed 's/<run>/run-fixture/; s/<lane>/head/; s|<source>|raw/example-lab.md|')" "$(date +%FT%R%z)" "$2" >> "$1/ledger.jsonl"
}
# sort_run <vault> <pairs...>: Step 6's procedure. pre over every member (a recovery passes the recorded
# plan, each member with its prefix); the plan recorded before any move; mv -n for each MOVE line; the
# post command pre printed; a sorted line only after post exits 0. Returns 1 at the first step that does
# not pass.
sort_run() {
  SV=$1; shift
  POST=""; POSTCMD=""; PLAN=""
  PRE=$("$PY" -B "$S" pre --vault "$SV" "$@"); PRC=$?
  [ "$PRC" -eq 0 ] || return 1
  PLAN=$(printf '%s\n' "$PRE" | sed -n 's/^plan: //p')
  [ -n "$PLAN" ] || return 1
  record_plan "$SV" "$PLAN"
  printf '%s\n' "$PRE" | sed -n 's/^MOVE \(.*\) -> \(.*\) sha256:[0-9a-f]*$/\1|\2/p' > "$T/moves.txt"
  while IFS='|' read -r src dst; do (cd "$SV" && mv -n "$src" "$dst"); done < "$T/moves.txt"
  POSTCMD=$(printf '%s\n' "$PRE" | sed -n 's/^post: //p')
  POST=$(eval "$POSTCMD"); PORC=$?
  [ "$PORC" -eq 0 ] || return 1
  printf '{"event":"checkpoint","stage":"sorted","source":"raw/example-lab.md"}\n' >> "$SV/ledger.jsonl"
}
# recorded_plan <vault>: the post list of the last sort_planned checkpoint for the source, read back from
# the ledger with a parser (a malformed line skipped), one member per line: all a resumed sorter whose
# context is gone has. Exit 1 when the ledger holds no plan.
recorded_plan() {
  "$PY" -B - "$1/ledger.jsonl" raw/example-lab.md <<'PY_RECORDED_PLAN'
import json, sys
plan = None
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        event = json.loads(line)
    except ValueError:
        continue
    if isinstance(event, dict) and event.get("stage") == "sort_planned" and event.get("source") == sys.argv[2]:
        plan = event.get("post")
if not (isinstance(plan, list) and plan and all(isinstance(member, str) for member in plan)):
    sys.exit(1)
print("\n".join(plan))
PY_RECORDED_PLAN
}
# resume_run <vault>: Step 6's recovery from the ledger alone: pre over every member of the recorded plan
# with its recorded prefix, then the moves, post and record as sort_run does. It reads nothing the
# interrupted run held in shell variables.
resume_run() {
  PRE=""; POST=""
  RPLAN=$(recorded_plan "$1") || return 1
  set -f; OLD_IFS=$IFS; IFS='
'
  set -- "$1" $RPLAN
  IFS=$OLD_IFS; set +f
  sort_run "$@"
}
PAIR="raw/example-lab.md=raw/4-webinfo/example-lab.md raw/example-lab.pdf=raw/4-webinfo/example-lab.pdf"

echo '--- a plain sort of a raw whose stem equals a source slug ---'
V="$T/vault"; build "$V"
WIKI_BEFORE=$(manifest "$V/wiki")
OUT=$("$PY" -B "$S" pre --vault "$V" $PAIR); RC=$?
if [ "$RC" -eq 0 ] && [ "$(count "$OUT" '^MOVE ')" -eq 2 ] && [ "$(count "$OUT" '^post: ')" -eq 1 ] && has "$OUT" "controls: "; then ok "S01 pre over both members of the pair: exit 0, two MOVE lines with their hashes, one post command"; else no "S01 pre: rc=$RC: $OUT"; fi
PLAN1=$(printf '%s\n' "$OUT" | sed -n 's/^plan: //p')
MOVES1=$(printf '%s\n' "$OUT" | sed -n 's/^MOVE \(.*\) -> \(.*\) sha256:\([0-9a-f]*\)$/\1=\2@\3/p')
PLANNED1=$(printf '%s' "$PLAN1" | "$PY" -B -c 'import json, sys; print("\n".join(json.load(sys.stdin)))' 2>&1)
if [ -n "$PLAN1" ] && [ "$PLANNED1" = "$MOVES1" ] && [ "$(count "$PLANNED1" '@[0-9a-f]\{16\}$')" -eq 2 ] && has "$OUT" "$(printf '%s\n' "$MOVES1" | tr '\n' ' ' | sed 's/ $//')"; then ok "S01a pre prints the plan: a JSON list of both members with the prefixes of its MOVE lines, the same pairs its post command names"; else no "S01a plan line: $PLAN1 / $PLANNED1"; fi
sort_run "$V" $PAIR; SRC_RC=$?
if [ "$SRC_RC" -eq 0 ] && [ "$(manifest "$V/wiki")" = "$WIKI_BEFORE" ] && [ -f "$V/raw/4-webinfo/example-lab.md" ] && [ -f "$V/raw/4-webinfo/example-lab.pdf" ] && [ ! -e "$V/raw/example-lab.md" ]; then ok "S02 the plain mv -n sort leaves every wiki page byte-identical and both files at their destinations"; else no "S02 plain sort: rc=$SRC_RC"; fi
if has "$POST" "sort: files 2 · moved 2 · not moved 0 · mismatched 0" && has "$POST" "path-links: pages 8 · wikilinks 11 · hits 0" && has "$POST" "· hits 0"; then ok "S03 post: both moves verified, the whole-wiki scan read 8 pages and 11 wikilinks and found 0 path links"; else no "S03 post: $POST"; fi
if [ "$(sorted_lines "$V")" -eq 1 ]; then ok "S04 exactly one sorted line, appended after post exited 0"; else no "S04 sorted lines: $(sorted_lines "$V")"; fi
ORDER=$(grep -o '"stage":"[a-z_]*"' "$V/ledger.jsonl" | tr '\n' ' ')
if [ "$ORDER" = '"stage":"sort_planned" "stage":"sorted" ' ] && [ "$(recorded_plan "$V")" = "$MOVES1" ]; then ok "S04a the plan was recorded ahead of the sorted line, one sort_planned checkpoint holding both members as pre planned them"; else no "S04a ledger order: $ORDER"; fi

echo '--- the nine rewrites a link-aware move makes ---'
"$PY" -B - "$V" <<'PY_PLANT_REWRITES'
import os, sys
root = sys.argv[1]
o, c = "[" * 2, "]" * 2
rewrites = {
    "wiki/entities/Example Lab.md": [(o + "example-lab" + c, o + "raw/4-webinfo/example-lab" + c), (o + "example-lab|", o + "raw/4-webinfo/example-lab.md|")],
    "wiki/index.md": [(o + "example-lab" + c + " — the", o + "wiki/sources/example-lab|example-lab" + c + " — the"), ("see " + o + "example-lab" + c, "see " + o + "wiki/sources/example-lab" + c)],
    "wiki/concepts/Alpha.md": [(o + "example-lab" + c, o + "wiki/sources/example-lab" + c)],
    "wiki/concepts/Beta.md": [(o + "example-lab|", o + "wiki/sources/example-lab|")],
    "wiki/models/Gamma.md": [(o + "example-lab" + c, o + "wiki/sources/example-lab#Summary" + c)],
    "wiki/maps/home.md": [(o + "example-lab\\|", o + "wiki/sources/example-lab\\|")],
    "wiki/developments/delta.md": [("!" + o + "example-lab" + c, "!" + o + "wiki/sources/example-lab.md" + c)],
}
done = 0
for rel, pairs in rewrites.items():
    path = os.path.join(root, rel)
    text = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert text.count(old) == 1, (rel, old)
        text = text.replace(old, new, 1)
        done += 1
    open(path, "w", encoding="utf-8").write(text)
print(done)
PY_PLANT_REWRITES
OUT=$("$PY" -B "$S" links --vault "$V"); RC=$?
if [ "$RC" -eq 1 ] && [ "$(count "$OUT" '^PATHLINK ')" -eq 9 ] && has "$OUT" "· hits 9"; then ok "S05 nine planted path links (two into raw/, seven into wiki/, two of them index lines): exit 1, nine PATHLINK lines"; else no "S05 rewrites: rc=$RC: $OUT"; fi
if has "$OUT" "PATHLINK wiki/index.md:2: " && has "$OUT" "PATHLINK wiki/index.md:4: " && has "$OUT" "PATHLINK wiki/entities/Example Lab.md:2: " && has "$OUT" 'PATHLINK wiki/maps/home.md:3: '; then ok "S06 each hit names its page and line, a table cell's escaped pipe included"; else no "S06 locators: $OUT"; fi

echo '--- code is not counted ---'
V2="$T/code"; build "$V2"
printf '%s\n' 'Quoted: `[''[raw/4-webinfo/example-lab]]` and ``[''[wiki/sources/example-lab]]``.' '```' '[''[raw/4-webinfo/example-lab]]' '```' '~~~~' '[''[wiki/sources/example-lab]]' '~~~~' 'And [''[example-lab]] bare.' > "$V2/wiki/concepts/Code.md"
OUT=$("$PY" -B "$S" links --vault "$V2"); RC=$?
BASE_LINKS=$(printf '%s\n' "$OUT" | sed -n 's/.*wikilinks \([0-9]*\) .*/\1/p')
if [ "$RC" -eq 0 ] && has "$OUT" "· hits 0" && [ "$BASE_LINKS" -eq 12 ]; then ok "S07 path links in code spans and fenced blocks are not counted; the bare link beside them is (12 wikilinks, 0 hits)"; else no "S07 code: rc=$RC links=$BASE_LINKS: $OUT"; fi

echo '--- an occupied destination is refused and never overwritten ---'
V3="$T/occupied"; build "$V3"
printf 'an earlier, different capture\n' > "$V3/raw/4-webinfo/example-lab.md"
OLD=$(shasum "$V3/raw/4-webinfo/example-lab.md" | cut -c1-40)
OUT=$("$PY" -B "$S" pre --vault "$V3" $PAIR); RC=$?
if [ "$RC" -eq 1 ] && has "$OUT" "REFUSED raw/example-lab.md -> raw/4-webinfo/example-lab.md: destination exists" && has "$OUT" "never overwritten" && has "$OUT" "WAITS raw/example-lab.pdf -> raw/4-webinfo/example-lab.pdf" && [ "$(count "$OUT" '^MOVE ')" -eq 0 ] && [ "$(count "$OUT" '^post: ')" -eq 0 ]; then ok "S08 pre refuses the whole sort over an occupied destination: exit 1, no MOVE line for either member, no post command"; else no "S08 occupied: rc=$RC: $OUT"; fi
sort_run "$V3" $PAIR; RC=$?
if [ "$RC" -eq 1 ] && [ "$(shasum "$V3/raw/4-webinfo/example-lab.md" | cut -c1-40)" = "$OLD" ] && [ -f "$V3/raw/example-lab.md" ] && [ -f "$V3/raw/example-lab.pdf" ] && [ ! -e "$V3/raw/4-webinfo/example-lab.pdf" ] && [ "$(sorted_lines "$V3")" -eq 0 ]; then ok "S09 the procedure moves neither member, the existing bytes are unchanged and no sorted line is written"; else no "S09 occupied procedure: rc=$RC sorted=$(sorted_lines "$V3")"; fi
(cd "$V3" && mv -n raw/example-lab.md raw/4-webinfo/example-lab.md)
if [ "$(shasum "$V3/raw/4-webinfo/example-lab.md" | cut -c1-40)" = "$OLD" ] && [ -f "$V3/raw/example-lab.md" ]; then ok "S10 control: mv -n itself leaves an occupied destination's bytes alone on this platform (the second guard)"; else no "S10 mv -n overwrote the destination"; fi
OUT=$("$PY" -B "$S" post --vault "$V3" "raw/example-lab.md=raw/4-webinfo/example-lab.md@$("$PY" -B -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()[:16])' "$V3/raw/example-lab.md")"); RC=$?
if [ "$RC" -eq 1 ] && has "$OUT" "NOT MOVED raw/example-lab.md -> raw/4-webinfo/example-lab.md: source still present"; then ok "S11 post after a refused move reads NOT MOVED (exit 1), so nothing is recorded as sorted"; else no "S11 post on refused: rc=$RC: $OUT"; fi

echo '--- an interrupted pair, finished from its recorded plan ---'
V4="$T/interrupted"; build "$V4"
PRE=$("$PY" -B "$S" pre --vault "$V4" $PAIR); RC=$?
PAIRPOST=$(printf '%s\n' "$PRE" | sed -n 's/^post: //p')
record_plan "$V4" "$(printf '%s\n' "$PRE" | sed -n 's/^plan: //p')"
(cd "$V4" && mv -n raw/example-lab.pdf raw/4-webinfo/example-lab.pdf)
PDF_SHA=$(printf '%s\n' "$PRE" | sed -n 's/^MOVE raw\/example-lab.pdf -> .* sha256:\([0-9a-f]*\)$/\1/p')
MD_SHA=$(printf '%s\n' "$PRE" | sed -n 's/^MOVE raw\/example-lab.md -> .* sha256:\([0-9a-f]*\)$/\1/p')
OUT=$(eval "$PAIRPOST"); PRC=$?
GOT_SHA=$("$PY" -B -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()[:16])' "$V4/raw/4-webinfo/example-lab.pdf")
if [ "$RC" -eq 0 ] && [ "$PRC" -eq 1 ] && has "$OUT" "NOT MOVED raw/example-lab.md -> raw/4-webinfo/example-lab.md: source still present" && has "$OUT" "MOVED raw/example-lab.pdf -> raw/4-webinfo/example-lab.pdf: sha256:$PDF_SHA" && has "$OUT" "moved 1 · not moved 1"; then ok "S12 post after a half-moved pair: exit 1, the unmoved member NOT MOVED, the moved one MOVED"; else no "S12 interrupted: pre=$RC post=$PRC: $OUT"; fi
if [ -n "$PDF_SHA" ] && [ "$GOT_SHA" = "$PDF_SHA" ] && [ -f "$V4/raw/example-lab.md" ] && [ "$(sorted_lines "$V4")" -eq 0 ]; then ok "S13 the moved member keeps its recorded bytes, the other stays in the inbox, and no sorted line is written"; else no "S13 interrupted state: sha=$GOT_SHA want=$PDF_SHA sorted=$(sorted_lines "$V4")"; fi
RPLAN=$(recorded_plan "$V4"); RPRC=$?
if [ "$RPRC" -eq 0 ] && [ -n "$MD_SHA" ] && [ -n "$PDF_SHA" ] && [ "$RPLAN" = "raw/example-lab.md=raw/4-webinfo/example-lab.md@$MD_SHA
raw/example-lab.pdf=raw/4-webinfo/example-lab.pdf@$PDF_SHA" ]; then ok "S13a the recorded plan survives the interruption: the ledger's sort_planned checkpoint, read back with a parser, holds both members with the prefixes pre printed"; else no "S13a recorded plan: rc=$RPRC: $RPLAN"; fi
resume_run "$V4"; RC=$?
if [ "$RC" -eq 0 ] && has "$PRE" "IN PLACE raw/example-lab.pdf -> raw/4-webinfo/example-lab.pdf sha256:$PDF_SHA" && has "$PRE" "MOVE raw/example-lab.md -> raw/4-webinfo/example-lab.md sha256:$MD_SHA" && has "$POST" "sort: files 2 · moved 2 · not moved 0 · mismatched 0" && [ "$(sorted_lines "$V4")" -eq 1 ]; then ok "S14 recovery from the ledger alone: pre over the complete recorded pair reads the moved PDF IN PLACE and moves the rest, and its post verifies both members before the one sorted line"; else no "S14 recovery: rc=$RC sorted=$(sorted_lines "$V4"): $PRE / $POST"; fi
printf 'tampered\n' > "$V4/raw/4-webinfo/example-lab.pdf"
OUT=$(eval "$PAIRPOST"); PRC=$?
if [ "$PRC" -eq 1 ] && has "$OUT" "MISMATCH raw/example-lab.pdf -> raw/4-webinfo/example-lab.pdf: destination sha256:"; then ok "S15 a destination whose bytes changed after the move reads MISMATCH (exit 1)"; else no "S15 mismatch: rc=$PRC: $OUT"; fi

echo '--- a recovery that must not complete ---'
# interrupt <vault>: a fresh fixture, pre over the pair, its plan recorded, then only the PDF moved.
interrupt() {
  build "$1"
  IPRE=$("$PY" -B "$S" pre --vault "$1" $PAIR)
  record_plan "$1" "$(printf '%s\n' "$IPRE" | sed -n 's/^plan: //p')"
  (cd "$1" && mv -n raw/example-lab.pdf raw/4-webinfo/example-lab.pdf)
}
V7="$T/changed"; interrupt "$V7"
printf 'changed after the move\n' > "$V7/raw/4-webinfo/example-lab.pdf"
CHANGED=$(shasum "$V7/raw/4-webinfo/example-lab.pdf" | cut -c1-40)
resume_run "$V7"; RC=$?
if [ "$RC" -eq 1 ] && has "$PRE" "REFUSED raw/example-lab.pdf -> raw/4-webinfo/example-lab.pdf: moved member changed since the plan" && [ "$(count "$PRE" '^MOVE ')" -eq 0 ] && [ -f "$V7/raw/example-lab.md" ] && [ ! -e "$V7/raw/4-webinfo/example-lab.md" ] && [ "$(shasum "$V7/raw/4-webinfo/example-lab.pdf" | cut -c1-40)" = "$CHANGED" ] && [ "$(sorted_lines "$V7")" -eq 0 ]; then ok "S14a a member moved before the interruption and changed since: the recovery's pre refuses the whole pair, nothing moves, the changed bytes stay, no sorted line"; else no "S14a changed member: rc=$RC sorted=$(sorted_lines "$V7"): $PRE"; fi
V8="$T/missing"; interrupt "$V8"
rm "$V8/raw/4-webinfo/example-lab.pdf"
resume_run "$V8"; RC=$?
if [ "$RC" -eq 1 ] && has "$PRE" "REFUSED raw/example-lab.pdf -> raw/4-webinfo/example-lab.pdf: member missing: neither in the inbox nor at its destination" && [ -f "$V8/raw/example-lab.md" ] && [ ! -e "$V8/raw/4-webinfo/example-lab.md" ] && [ "$(sorted_lines "$V8")" -eq 0 ]; then ok "S14b a member moved before the interruption and gone since: refused, the inbox member stays, no sorted line"; else no "S14b missing member: rc=$RC sorted=$(sorted_lines "$V8"): $PRE"; fi
V9="$T/altered"; interrupt "$V9"
printf 'edited in the inbox\n' >> "$V9/raw/example-lab.md"
resume_run "$V9"; RC=$?
if [ "$RC" -eq 1 ] && has "$PRE" "REFUSED raw/example-lab.md -> raw/4-webinfo/example-lab.md: source changed since the plan" && [ -f "$V9/raw/example-lab.md" ] && [ "$(sorted_lines "$V9")" -eq 0 ]; then ok "S14c a member still in the inbox but changed since the plan: refused too, no sorted line"; else no "S14c altered inbox member: rc=$RC: $PRE"; fi
V10="$T/bothmoved"; build "$V10"
IPRE=$("$PY" -B "$S" pre --vault "$V10" $PAIR)
record_plan "$V10" "$(printf '%s\n' "$IPRE" | sed -n 's/^plan: //p')"
(cd "$V10" && mv -n raw/example-lab.md raw/4-webinfo/example-lab.md && mv -n raw/example-lab.pdf raw/4-webinfo/example-lab.pdf)
resume_run "$V10"; RC=$?
if [ "$RC" -eq 0 ] && [ "$(count "$PRE" '^IN PLACE ')" -eq 2 ] && [ "$(count "$PRE" '^MOVE ')" -eq 0 ] && has "$POST" "moved 2 · not moved 0" && [ "$(sorted_lines "$V10")" -eq 1 ]; then ok "S14d stopped after both moves but before post: both members IN PLACE, the post over the pair passes, one sorted line"; else no "S14d both moved: rc=$RC: $PRE / $POST"; fi

echo '--- broken premises exit 2, never a pass ---'
V5="$T/premise"; build "$V5"
run2() { OUT=$("$PY" -B "$S" "$@"); RC=$?; }
mkdir -p "$T/nowiki/raw"; run2 links --vault "$T/nowiki"
if [ "$RC" -eq 2 ] && has "$OUT" "PROBE FAILED: " && has "$OUT" "no wiki/ folder"; then ok "S16 a vault without wiki/: exit 2"; else no "S16 no wiki: rc=$RC: $OUT"; fi
mkdir -p "$T/nolinks/raw" "$T/nolinks/wiki"; printf 'plain text\n' > "$T/nolinks/wiki/page.md"; run2 links --vault "$T/nolinks"
if [ "$RC" -eq 2 ] && has "$OUT" "no wikilink at all"; then ok "S17 pages with no wikilink at all: exit 2 (the scan searched nothing)"; else no "S17 no links: rc=$RC: $OUT"; fi
mkdir -p "$T/nopages/raw" "$T/nopages/wiki"; run2 links --vault "$T/nopages"
if [ "$RC" -eq 2 ] && has "$OUT" "no Markdown page under wiki/"; then ok "S18 no page under wiki/: exit 2"; else no "S18 no pages: rc=$RC: $OUT"; fi
chmod 000 "$V5/wiki/concepts/Alpha.md"; run2 links --vault "$V5"; chmod 644 "$V5/wiki/concepts/Alpha.md"
if [ "$RC" -eq 2 ] && has "$OUT" "unreadable page, never skipped"; then ok "S19 an unreadable page: exit 2, never skipped"; else no "S19 unreadable: rc=$RC: $OUT"; fi
V6="$T/symlinked"; build "$V6"
mkdir -p "$T/outside/notes"
printf '%s\n' 'Linked from outside: [''[raw/4-webinfo/example-lab]].' > "$T/outside/notes/Outside.md"
ln -s "$T/outside/notes" "$V6/wiki/linked-notes"
run2 links --vault "$V6"
if [ "$RC" -eq 2 ] && has "$OUT" "PROBE FAILED: " && has "$OUT" "wiki/linked-notes (symlinked folder)" && ! has "$OUT" "path-links:"; then ok "S19a a symlinked folder holding a path link fails the probe (exit 2, naming it), never a clean scan"; else no "S19a symlinked folder: rc=$RC: $OUT"; fi
rm "$V6/wiki/linked-notes"; cp -R "$T/outside/notes" "$V6/wiki/linked-notes"
run2 links --vault "$V6"
if [ "$RC" -eq 1 ] && has "$OUT" "PATHLINK wiki/linked-notes/Outside.md:1: " && has "$OUT" "· hits 1"; then ok "S19b control: the same folder copied in as an ordinary folder is read, and its path link found (exit 1)"; else no "S19b ordinary folder: rc=$RC: $OUT"; fi
rm -rf "$V6/wiki/linked-notes"
ln -s "$T/outside/notes/Outside.md" "$V6/wiki/concepts/Linked.md"
run2 links --vault "$V6"
if [ "$RC" -eq 1 ] && has "$OUT" "PATHLINK wiki/concepts/Linked.md:1: " && has "$OUT" "· hits 1"; then ok "S19c a symlinked page is read through its link, its path link found under the link's own path (exit 1)"; else no "S19c symlinked page: rc=$RC: $OUT"; fi
rm "$V6/wiki/concepts/Linked.md"
ln -s "$T/outside/notes/Absent.md" "$V6/wiki/concepts/Gone.md"
ln -s .. "$V6/wiki/concepts/loop"
run2 links --vault "$V6"
if [ "$RC" -eq 2 ] && has "$OUT" "wiki/concepts/Gone.md (dangling symlink)" && has "$OUT" "wiki/concepts/loop (symlinked folder)"; then ok "S19d a dangling symlink and a symlinked folder that loops back to wiki/ fail the probe (exit 2), each named"; else no "S19d dangling and loop: rc=$RC: $OUT"; fi
rm "$V6/wiki/concepts/Gone.md" "$V6/wiki/concepts/loop"
run2 links --vault "$V6"
if [ "$RC" -eq 0 ] && has "$OUT" "· hits 0"; then ok "S19e control: with the links removed the same fixture scans clean (exit 0)"; else no "S19e clean again: rc=$RC: $OUT"; fi
run2 pre --vault "$V5" raw/example-lab.md
if [ "$RC" -eq 2 ] && has "$OUT" "want SOURCE=DESTINATION"; then ok "S20 a malformed pair: exit 2"; else no "S20 malformed: rc=$RC: $OUT"; fi
run2 pre --vault "$V5" raw/4-webinfo/x.md=raw/2-papers/x.md
if [ "$RC" -eq 2 ] && has "$OUT" "not a file directly in raw/"; then ok "S21 a source outside the inbox: exit 2"; else no "S21 source outside inbox: rc=$RC: $OUT"; fi
run2 pre --vault "$V5" raw/example-lab.md=raw/elsewhere.md
if [ "$RC" -eq 2 ] && has "$OUT" "not in a folder under raw/"; then ok "S22 a destination in the inbox itself: exit 2"; else no "S22 destination at the root: rc=$RC: $OUT"; fi
run2 pre --vault "$V5" raw/example-lab.md=../outside/example-lab.md
if [ "$RC" -eq 2 ] && has "$OUT" "not in a folder under raw/"; then ok "S23 a destination outside raw/: exit 2"; else no "S23 outside raw: rc=$RC: $OUT"; fi
run2 post --vault "$V5" raw/example-lab.md=raw/4-webinfo/example-lab.md@zz
if [ "$RC" -eq 2 ] && has "$OUT" "want SOURCE=DESTINATION@SHA"; then ok "S24 post with a malformed hash: exit 2"; else no "S24 post hash: rc=$RC: $OUT"; fi
run2 pre --vault "$V5"
if [ "$RC" -eq 2 ] && has "$OUT" "nothing to check"; then ok "S25 pre naming no file: exit 2"; else no "S25 empty pre: rc=$RC: $OUT"; fi
run2 pre --vault "$V5" raw/example-lab.md=raw/9-none/example-lab.md
if [ "$RC" -eq 1 ] && has "$OUT" "destination folder missing"; then ok "S26 a destination folder that does not exist refuses the sort (exit 1)"; else no "S26 missing folder: rc=$RC: $OUT"; fi
run2 pre --vault "$V5" raw/absent.md=raw/2-papers/absent.md
if [ "$RC" -eq 1 ] && has "$OUT" "source missing"; then ok "S27 a source that does not exist refuses the sort (exit 1)"; else no "S27 missing source: rc=$RC: $OUT"; fi
cp "$S" "$T/sabotaged.py"
chmod u+w "$T/sabotaged.py"   # a copy of a read-only source is read-only, and the next step rewrites it
"$PY" -B - "$T/sabotaged.py" <<'PY_SABOTAGE'
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
planted = '[raw/x/y]]'
assert text.count(planted) == 1
open(path, "w", encoding="utf-8").write(text.replace(planted, '[x/y]]', 1))
PY_SABOTAGE
OUT=$("$PY" -B "$T/sabotaged.py" links --vault "$V5"); RC=$?
if [ "$RC" -eq 2 ] && has "$OUT" "PROBE FAILED: path-link controls failed"; then ok "S28 a sabotaged built-in control stops the run (exit 2)"; else no "S28 sabotaged control: rc=$RC: $OUT"; fi

echo '--- the skill and the compile brief carry the procedure ---'
SKILL="$HERE/SKILL.md"
BRIEF="$HERE/../delegate/templates/brief-compile.md"
STEP6=$(sed -n '/^### Step 6/,/^### Step 7/p' "$SKILL")
if [ -n "$STEP6" ] && ! has "$STEP6" "use \`obsidian-cli\` or a shell \`mv\`" && has "$STEP6" "never the link-aware \`obsidian-cli\` move"; then ok "S29 Step 6 no longer offers the link-aware move"; else no "S29 Step 6 still offers obsidian-cli for the sort"; fi
if has "$STEP6" "sort_check.py pre --vault" && has "$STEP6" "mv -n <source> <destination>" && has "$STEP6" "Only its exit 0 lets the \`sorted\` checkpoints be appended" && has "$STEP6" "never overwritten"; then ok "S30 Step 6 names the pre check, the no-clobber move, the post check before sorted, and the refusal"; else no "S30 Step 6 procedure text"; fi
if has "$STEP6" "printf '$PLAN_FORMAT'" && has "$STEP6" "Before any move, append the plan to the run ledger as one \`sort_planned\` checkpoint" && has "$STEP6" "never re-planned from the members still in the inbox" && has "$STEP6" "the \`post\` list of the last \`sort_planned\` checkpoint for the source, read with a parser" && has "$STEP6" "as \`IN PLACE\`" && ! has "$STEP6" "by running \`pre\` again over the members still in the inbox" && grep -qF '`registered` (Step 5) → `sort_planned` (Step 6, before any move) → `sorted` (Step 6)' "$SKILL"; then ok "S30a Step 6 records the plan before any move in the fixture's own printf format, finishes an interrupted pair from it, says where it lives when the context is gone, and the ledger's stage list carries sort_planned"; else no "S30a Step 6 plan record and recovery text"; fi
if has "$STEP6" "Its exit 0 shows that every move the plan names completed (each source gone, each destination present with the recorded sha256 prefix) and that no wiki page carries a path link" && has "$STEP6" "it does not check that the plan names both members of every converted pair. That duty sits with the paired-move rule above, checked by the sorter before \`pre\` (step 1)." && has "$STEP6" "\`pre\` checks only the files it is given and never looks for a pair member left out" && has "$STEP6" "list the \`converted_from:\` of each conversion the sort names and name the original it records in the same plan" && has "$STEP6" "move the original AND its converted \`.md\` together" && ! has "$STEP6" "over the whole pair again"; then ok "S30c Step 6 claims for post's exit 0 only what post tests (the named moves and the path-link scan), says it does not test pair coverage, and puts that duty on the paired-move rule, checked by the sorter from converted_from: before pre"; else no "S30c Step 6 narrowed post claim and the pair duty"; fi
if grep -qF "sorts fully merged raw pairs by Step 6's checked procedure" "$SKILL"; then ok "S31 the parallel merge-close sort points at the checked procedure"; else no "S31 parallel step 6 pointer"; fi
if grep -qF 'A lane granted sorting follows the ingest skill'"'"'s Step 6 sort procedure' "$BRIEF" && grep -qF 'SORT CHECK: a headless lane granted sorting also takes' "$BRIEF"; then ok "S32 the compile brief's Sorting slot and spawner note carry the procedure and its grant"; else no "S32 compile brief sorting text"; fi
if grep -qF 'It reports each `plan:` list `pre` prints under `## Controls`, and finishes a pair that stopped part-way by `pre` over that whole plan, each member with its recorded prefix, never by re-planning what is left in the inbox.' "$BRIEF"; then ok "S32a the compile brief's Sorting slot has a sorting lane report its plan and finish a stopped pair from the whole plan"; else no "S32a compile brief recovery text"; fi

# G44: a raw already filed takes a scripted path (--re-sort), with the same planned move and sha256 checks.
RS="$T/resort"; mkdir -p "$RS"; build "$RS"; mkdir -p "$RS/raw/duplicates"
mv -n "$RS/raw/example-lab.md" "$RS/raw/4-webinfo/example-lab.md"
out=$("$PY" -B "$S" pre --vault "$RS" raw/4-webinfo/example-lab.md=raw/duplicates/example-lab.md 2>&1); rc=$?
if [ "$rc" -eq 2 ] && has "$out" "not a file directly in raw/"; then ok "R1 without --re-sort a filed source stays refused as outside the inbox (exit 2)"
else no "R1 a filed source without --re-sort  [exit $rc: $out]"; fi
out=$("$PY" -B "$S" pre --re-sort --vault "$RS" raw/4-webinfo/example-lab.md=raw/duplicates/example-lab.md 2>&1); rc=$?
SHA=$(shasum -a 256 "$RS/raw/4-webinfo/example-lab.md" | cut -c1-16)
if [ "$rc" -eq 0 ] && has "$out" "MOVE raw/4-webinfo/example-lab.md -> raw/duplicates/example-lab.md sha256:$SHA" && has "$out" "--re-sort"; then ok "R2 --re-sort pre plans the filed raw's move with its sha256 and a post that carries the flag"
else no "R2 --re-sort pre  [exit $rc: $out]"; fi
if has "$out" "NAMES wiki/sources/example-lab.md: raw/4-webinfo/example-lab.md" && [ "$(count "$out" '^NAMES ')" -eq 1 ]; then ok "R3 --re-sort pre names the one page whose sources: holds the old path"
else no "R3 NAMES  [$out]"; fi
out2=$("$PY" -B "$S" pre --re-sort --vault "$RS" raw/example-lab.pdf=raw/duplicates/example-lab.pdf 2>&1); rc=$?
if [ "$rc" -eq 2 ] && has "$out2" "not in a folder under raw/"; then ok "R4 --re-sort refuses an inbox source: that file takes the plain sort (exit 2)"
else no "R4 inbox source under --re-sort  [exit $rc: $out2]"; fi
out2=$("$PY" -B "$S" pre --re-sort --vault "$RS" raw/4-webinfo/example-lab.md=raw/4-webinfo/renamed.md 2>&1); rc=$?
if [ "$rc" -eq 2 ] && has "$out2" "stays in one folder"; then ok "R5 --re-sort refuses a move inside one folder (exit 2)"
else no "R5 same-folder re-sort  [exit $rc: $out2]"; fi
: > "$RS/raw/duplicates/occupied.md"
out2=$("$PY" -B "$S" pre --re-sort --vault "$RS" raw/4-webinfo/example-lab.md=raw/duplicates/occupied.md 2>&1); rc=$?
if [ "$rc" -eq 1 ] && has "$out2" "destination exists" && ! has "$out2" "MOVE "; then ok "R6 --re-sort refuses an occupied destination and prints no MOVE (exit 1)"
else no "R6 occupied destination  [exit $rc: $out2]"; fi
rm -f "$RS/raw/duplicates/occupied.md"
POST=$(printf '%s\n' "$out" | "$PY" -B -c 'import shlex,sys
for l in sys.stdin:
    if l.startswith("post: "): print(" ".join(shlex.quote(p) for p in shlex.split(l[6:])))')
out2=$(eval "$POST" 2>&1); rc=$?
if [ "$rc" -eq 1 ] && has "$out2" "NOT MOVED"; then ok "R7 --re-sort post before the move reads NOT MOVED (exit 1)"
else no "R7 post before the move  [exit $rc: $out2]"; fi
mv -n "$RS/raw/4-webinfo/example-lab.md" "$RS/raw/duplicates/example-lab.md"
out2=$(eval "$POST" 2>&1); rc=$?
if [ "$rc" -eq 0 ] && has "$out2" "MOVED raw/4-webinfo/example-lab.md -> raw/duplicates/example-lab.md: sha256:$SHA"; then ok "R8 --re-sort post after the move reads MOVED with the planned sha256 (exit 0)"
else no "R8 post after the move  [exit $rc: $out2]"; fi
printf 'changed\n' >> "$RS/raw/duplicates/example-lab.md"
out2=$(eval "$POST" 2>&1); rc=$?
if [ "$rc" -eq 1 ] && has "$out2" "MISMATCH"; then ok "R9 --re-sort post reads a changed file as MISMATCH (exit 1)"
else no "R9 mismatch  [exit $rc: $out2]"; fi
out2=$("$PY" -B "$S" pre --vault "$RS" raw/example-lab.pdf=raw/2-papers/example-lab.pdf 2>&1); rc=$?
if [ "$rc" -eq 0 ] && ! has "$out2" "NAMES " && ! has "$out2" "--re-sort"; then ok "R10 control: the plain inbox sort prints no NAMES line and no flag (exit 0)"
else no "R10 plain sort control  [exit $rc: $out2]"; fi
out2=$("$PY" -B "$S" links --re-sort --vault "$RS" 2>&1); rc=$?
if [ "$rc" -eq 2 ]; then ok "R11 links refuses --re-sort (exit 2)"
else no "R11 links --re-sort  [exit $rc: $out2]"; fi

echo '--- stdout-only proof (must run last) ---'
RO="$T/readonly"; build "$RO"
PRE=$("$PY" -B "$S" pre --vault "$RO" $PAIR)
POSTCMD=$(printf '%s\n' "$PRE" | sed -n 's/^post: //p')
RSPECS=$(printf '%s\n' "$PRE" | sed -n 's/^MOVE \(.*\) -> \(.*\) sha256:\([0-9a-f]*\)$/\1=\2@\3/p' | tr '\n' ' ')
chmod -R a-w "$RO"
BEFORE=$(manifest "$RO")
"$PY" -B "$S" pre --vault "$RO" $PAIR > /dev/null; r1=$?
eval "$POSTCMD" > /dev/null; r2=$?
"$PY" -B "$S" links --vault "$RO" > /dev/null; r3=$?
"$PY" -B "$S" pre --vault "$RO" $RSPECS > /dev/null; r4=$?
AFTER=$(manifest "$RO")
chmod -R u+w "$RO"
NFILES=$(printf '%s\n' "$BEFORE" | grep -c '^[0-9a-f]\{40\}  ')
if [ "$r1 $r2 $r3 $r4" = "0 1 0 0" ]; then ok "S33 every mode runs against a chmod -R a-w copy, a recovery pre over the recorded pair included (exits 0 1 0 0: post reads NOT MOVED, nothing moved)"; else no "S33 read-only exits $r1 $r2 $r3 $r4"; fi
if [ "$NFILES" -ge 11 ] && [ "$BEFORE" = "$AFTER" ]; then ok "S34 the read-only copy's checksum manifest is unchanged ($NFILES files)"; else no "S34 manifest changed or too small ($NFILES files)"; fi
if [ "$(manifest "$HERE")" = "$HOME_BEFORE" ]; then ok "S35 the script home is byte-identical to its pre-run baseline (no bytecode cache)"; else no "S35 the script home changed during the suite"; fi
if "$PY" -B - "$S" <<'PY_WRITE_GREP'
import re, sys
pats = [r"""open\([^)]*,\s*['"][rwxabt+]*[wax+][rwxabt+]*['"]""", r"\.write(?:_text|_bytes)?\s*\(",
        r"\bos\.(?:replace|rename|renames|remove|unlink|mkdir|makedirs|rmdir|symlink|link|truncate|chmod|utime)\(",
        r"\bshutil\.", r"\bsubprocess\b|\bos\.system\(|\bos\.popen\(", r"\.(?:touch|unlink|mkdir|rename|replace|chmod)\s*\(\s*[^)'\"]"]
controls = ['open(p, "w")', "fh.write(x)", "os.rename(a, b)", "shutil.move(a, b)", "subprocess.run(x)", "p.unlink(x)"]
src = open(sys.argv[1], encoding="utf-8").read()
dead = [p for p, c in zip(pats, controls) if not re.search(p, c)]
hits = [m.group(0) for p in pats for m in re.finditer(p, src)]
print("  source grep: %d patterns, dead %d, hits %d %s" % (len(pats), len(dead), len(hits), hits[:3]))
sys.exit(0 if not dead and not hits else 1)
PY_WRITE_GREP
then ok "S36 no write, move or delete pattern in the script's source (6 patterns, each matched on its own control line)"; else no "S36 source grep: a write pattern hit, or a pattern missed its control"; fi

N=$((PASS + FAIL))
printf '\n'
if [ "$FAIL" -eq 0 ]; then printf 'PASS %d/%d\n' "$PASS" "$N"; else printf 'FAIL %d/%d\n' "$FAIL" "$N"; fi
[ "$FAIL" -eq 0 ]
