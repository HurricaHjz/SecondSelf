#!/bin/bash
# The suite for rule_register.py: its wording check, its one weekly pass, its seed, its page and its
# clean-up listing. Every fixture is an invented sentence under a mktemp folder this suite removes;
# no real wording is read or held. It ends PASS n/n or FAIL k/n.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
TOOL="$HERE/rule_register.py"
export PYTHONDONTWRITEBYTECODE=1
WORK="$(mktemp -d)"
export LLM_WIKI_STORE="$WORK/machine-store"   # the machine-local store, kept off the real one
cleanup_work() { chmod -R u+rwX "$WORK" 2>/dev/null; rm -rf "$WORK"; }
trap cleanup_work EXIT
V="$WORK/v"
OUT="$WORK/out.txt"
total=0
failed=0
rc=0

run() { python3 -B "$TOOL" "$@" >"$OUT" 2>&1; rc=$?; }

# expect NAME RC [+must-hold | -must-not-hold]...
expect() {
  local name="$1" want="$2" problem=""
  shift 2
  [ "$rc" -eq "$want" ] || problem="exit $rc, wanted $want"
  local item
  for item in "$@"; do
    case "$item" in
      +*) grep -qF -- "${item#+}" "$OUT" || problem="$problem; missing: ${item#+}" ;;
      -*) if grep -qF -- "${item#-}" "$OUT"; then problem="$problem; present: ${item#-}"; fi ;;
    esac
  done
  verdict "$name" "$problem"
}

verdict() {
  total=$((total + 1))
  if [ -z "$2" ]; then
    echo "ok $total - $1"
  else
    failed=$((failed + 1))
    echo "not ok $total - $1: $2"
    sed -n '1,25p' "$OUT" | cut -c1-200 | sed 's/^/    /'
  fi
}

# replace FILE OLD NEW: an exact replacement that must find its text exactly once.
replace() {
  python3 -B - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit("replace: %r found %d times in %s" % (old, text.count(old), path))
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
  [ $? -eq 0 ] || verdict "fixture edit: $2" "the text to replace was not found exactly once"
}

# set_rows PY: edit the fixture's data with a Python expression over `rows`, `data` and `by`.
edit_data() {
  python3 -B - "$V/wiki/developments/rule-register-data.json" "$1" <<'PY'
import json, sys
path, code = sys.argv[1:3]
data = json.load(open(path, encoding="utf-8"))
rows = data["rows"]
by = {row["id"]: row for row in rows}
exec(code)
json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
PY
}

KETTLE='**Keep the kettle warm (owner, 2 March 2026)**: the kettle stays on the low ring while tea is being made.'
VISITOR='Every visitor signs the green book before the second door.'
GATE='The garden gate stays open in summer.'
WRAPPED_ONE='A long framework rule that wraps across two lines in this fixture so that the comparison'
WRAPPED_TWO='must join it before it can match the stored row text here.'
MARKER_LINE='`CUSTOMISATION-LOADED-v1` — load marker. This line proves the file was read at the start of a session.'
PAGE_RULE='Fixture pages keep one rule here (owner, 5 March 2026).'

fresh() {
  chmod -R u+rwX "$V" 2>/dev/null
  rm -rf "$V"
  mkdir -p "$V/wiki/developments" "$V/wiki/sources" "$V/raw" "$V/attic" "$V/output/user-notes" "$V/output/reports" \
    "$V/.claude/skills/fix" "$V/.claude/agents" "$V/.claude/hooks"
  cat >"$V/CUSTOMISATION.md" <<EOF
---
title: Customisation
---

$MARKER_LINE

## Settings
- $KETTLE
- $GATE

## Visitors
- $VISITOR
EOF
  cat >"$V/CLAUDE.md" <<EOF
# Fixture contract

## Reading
- $WRAPPED_ONE
  $WRAPPED_TWO
EOF
  cat >"$V/CALENDAR.md" <<'EOF'
# Calendar
- Sunday: the weekly review names run-20200101-namedincal.
EOF
  cat >"$V/wiki/developments/fixture-rules.md" <<EOF
---
title: "Fixture rules"
type: development
sources: [raw/one.md, "raw/two.md", attic/cold.md, output/user-notes/credentials.env, raw/absent.md]
flagged: "2020-01-01 a test flag whose words clear on 1 February 2020 when read."
---
## Rules
- $PAGE_RULE

## Related
Names \`.claude/skills/fix/tool.py\` and \`attic/cold.md\`, and names run-20200101-namedinpage.
EOF
  cat >"$V/wiki/sources/ahead.md" <<'EOF'
---
title: "Ahead"
flagged: "2020-02-02 a flag that clears on 2099-01-01."
---
Body.
EOF
  cat >"$V/wiki/sources/eventful.md" <<'EOF'
---
title: "Eventful"
flagged: "2020-03-03 the capture lost its table. Clears when the table is captured again."
---
Body.
EOF
  cat >"$V/wiki/sources/unflagged.md" <<'EOF'
---
title: "Unflagged"
sources: [raw/one.md]
---
A body line reading flagged: never counted, and clears on 2001-01-01 in the prose.
EOF
  cat >"$V/wiki/log.md" <<'EOF'
# Log
Dated record line: an invented sentence that only the log holds.
EOF
  cat >"$V/wiki/developments/owner-rulings-history.md" <<'EOF'
# History
Only the history holds this retired sentence about the blue door.
EOF
  cat >"$V/wiki/developments/known-issues.md" <<'EOF'
# Known issues
Only the defect register holds this sentence about the broken hinge.
EOF
  printf 'one\n' >"$V/raw/one.md"
  printf 'two\n' >"$V/raw/two.md"
  printf 'cold\n' >"$V/attic/cold.md"
  printf 'SECRET=x\n' >"$V/output/user-notes/credentials.env"
  printf 'print("tool")\n' >"$V/.claude/skills/fix/tool.py"
  printf '# Skill\nSome step text.\n' >"$V/.claude/skills/fix/SKILL.md"
  printf '# Helper\nA helper definition.\n' >"$V/.claude/agents/helper.md"
  printf '# hook\nprint("hook")\n' >"$V/.claude/hooks/h.py"
  printf '# Output\nWhat this folder holds.\n' >"$V/output/README.md"
  KETTLE="$KETTLE" VISITOR="$VISITOR" GATE="$GATE" WRAPPED="$WRAPPED_ONE $WRAPPED_TWO" MARKER_LINE="$MARKER_LINE" PAGE_RULE="$PAGE_RULE" \
    python3 -B - "$V/wiki/developments/rule-register-data.json" <<'PY'
import json, os, sys
env = os.environ
def row(rid, home, section, text, **more):
    base = {"id": rid, "map_row": rid.split("#")[0], "home": {"file": home, "section": section}, "text": text,
            "wording": "agent", "approved": [], "whose": "product", "layer": "core", "shape": "guided",
            "moment": "always-on", "kept_by": "text", "pointers": [], "carriers": [],
            "origin": {"kind": "not recorded", "dates": []}}
    base.update(more)
    return base
rows = [
    row("R1#0-0", "CUSTOMISATION.md", "Settings", env["KETTLE"], wording="approved-record", shape="fixed",
        failure="a cold kettle", whose="owner", layer="user", approved=[{"text": env["KETTLE"], "record": {"file": "fixture"}}]),
    row("R2#0-0", "CUSTOMISATION.md", "Visitors", env["VISITOR"], wording="approved-record", whose="owner", layer="user",
        approved=[{"text": env["VISITOR"], "record": {"file": "fixture"}}]),
    row("R3#0-0", "CUSTOMISATION.md", "Settings", env["GATE"]),
    row("R4#0-0", "CLAUDE.md", "Reading", env["WRAPPED"]),
    row("R5#0-0", "CUSTOMISATION.md", None, env["MARKER_LINE"]),
    row("R6#0-0", "wiki/developments/fixture-rules.md", "Rules", env["PAGE_RULE"], moment="page-pointer"),
]
json.dump({"schema_version": 1, "trial": False, "page": {"created": "2020-01-01", "audited": "2020-01-01", "confidence": "medium"},
           "rule_holding_pages": [], "rows": rows}, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
PY
}

DOC="$V/wiki/developments/rule-register-data.json"

# ---- the wording check: its first step ----------------------------------------------------------
fresh; run wording-check --vault "$V"
expect "clean: the control line stands apart and nothing is missed" 0 \
  "+CONTROL: load marker found in CUSTOMISATION.md; a sentence and its one-word copy, both in memory: 1 match, 1 miss" \
  "+WORDING: 2 approved wordings: 2 in their homes, 0 missed" "-MISS" "-PROBE FAILED"

fresh; replace "$V/CUSTOMISATION.md" "$MARKER_LINE" "A line with no marker left."; run wording-check --vault "$V"
expect "the load marker gone: could not check, with no result" 2 \
  "+PROBE FAILED: could not check: the load marker is not at the top of CUSTOMISATION.md" "-WORDING:" "-all clear" "-MISS"

fresh; printf '\n## Later\n%s\n' "$MARKER_LINE" >"$WORK/tail"; replace "$V/CUSTOMISATION.md" "$MARKER_LINE" "No marker at the top."
cat "$WORK/tail" >>"$V/CUSTOMISATION.md"; run wording-check --vault "$V"
expect "the marker found only below the first section is not at the top" 2 "+could not check" "-WORDING:"

fresh; rm "$V/CUSTOMISATION.md"; run wording-check --vault "$V"
expect "the marker file gone: could not check" 2 "+could not check: CUSTOMISATION.md cannot be read" "-WORDING:"

control_broken() {
  fresh
  python3 -B - "$HERE" "$V" "$1" >"$OUT" 2>&1 <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import rule_register
rule_register.matches = {"always": lambda n, h: True, "never": lambda n, h: False}[sys.argv[3]]
sys.exit(rule_register.main(["wording-check", "--vault", sys.argv[2]]))
PY
  rc=$?
}
control_broken always
expect "a comparison that always matches: could not check" 2 "+could not check: the comparison gave a match on the sentence and a match" "-WORDING:" "-MISS"
control_broken never
expect "a comparison that never matches: could not check" 2 "+could not check: the comparison gave a miss on the sentence and a miss" "-WORDING:"

fresh; replace "$V/CUSTOMISATION.md" "This line proves the file was read at the start of a session." "Quinces ripen slowly behind the northern wall of a fixture."
python3 -B - "$HERE" "$V" >"$OUT" 2>&1 <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import rule_register
seen, real = [], rule_register.matches
def recording(needle, hay):
    seen.append(needle)
    return real(needle, hay)
rule_register.matches = recording
ok, line = rule_register.prove_control(rule_register.Vault(sys.argv[2]))
sentence, copy = seen[0], seen[1]
a, b = sentence.split(" "), copy.split(" ")
one_word = len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1
print(ok, len(seen), "Quinces" in sentence, one_word)
source = open(rule_register.__file__, encoding="utf-8").read()
sys.exit(0 if ok and len(seen) == 2 and "Quinces" in sentence and one_word and "Quinces" not in source else 1)
PY
rc=$?
expect "the control's sentence comes from the marker line read at run time, its copy differs by one word, and neither is in source" 0 "+True 2 True True"

# ---- the wording check: what exactly means ------------------------------------------------------
fresh
cat >"$V/CUSTOMISATION.md" <<EOF
---
title: Customisation
---

$MARKER_LINE

## Settings
    - **Keep the kettle   warm (owner, 2 March 2026)**: the kettle
      stays on the low ring
      while tea is being made.
- $GATE

## Visitors
* Every visitor signs the green
      book before the second door.
EOF
run wording-check --vault "$V"
expect "re-wrapped, with runs of spaces and list indentation: still in its home" 0 "+2 in their homes, 0 missed" "-MISS"

fresh; replace "$V/CUSTOMISATION.md" "the green book" "the green-
  book"; run wording-check --vault "$V"
expect "a line broken after a hyphen joins with no space, so a changed hyphen is seen" 0 "+1 missed" "+green-book"

fresh; edit_data 'by["R2#0-0"]["approved"][0]["text"] = "Every visitor signs the green-book before the second door."; by["R2#0-0"]["text"] = by["R2#0-0"]["approved"][0]["text"]'; replace "$V/CUSTOMISATION.md" "the green book" "the green-
  book"; run wording-check --vault "$V"
expect "a hyphenated word re-wrapped at its hyphen still matches" 0 "+2 in their homes" "-MISS"

fresh; replace "$V/CUSTOMISATION.md" "the green book" "the red book"; run wording-check --vault "$V"
expect "one word changed: a miss with stored text, home text and the difference" 0 \
  "+MISS R2#0-0 · CUSTOMISATION.md § Visitors" "+A miss goes to the owner, who chooses" "+stored: $VISITOR" "+home:   - Every visitor signs the red book before the second door." \
  "+[-green-] {+red+}" "+1 missed"

fresh; replace "$V/CUSTOMISATION.md" "second door." "second door!"; run wording-check --vault "$V"
expect "a punctuation mark changed: a miss" 0 "+MISS R2#0-0" "+1 missed"

fresh; replace "$V/CUSTOMISATION.md" "Every visitor" "every visitor"; run wording-check --vault "$V"
expect "a capital changed: a miss" 0 "+MISS R2#0-0"

fresh; replace "$V/CUSTOMISATION.md" "**Keep the kettle warm (owner, 2 March 2026)**" "Keep the kettle warm (owner, 2 March 2026)"; run wording-check --vault "$V"
expect "an emphasis mark removed: a miss" 0 "+MISS R1#0-0"

fresh; replace "$V/CUSTOMISATION.md" "Every visitor signs the green book before the second door." "Every visitor signs the green book before the second door.Then"; run wording-check --vault "$V"
expect "control for the boundary: punctuation closes the wording, so text after it is no change" 0 "+2 in their homes"

fresh; edit_data 'by["R2#0-0"]["approved"][0]["text"] = "Every visitor signs the green book before the second door"'; replace "$V/CUSTOMISATION.md" "second door." "second doorway."; run wording-check --vault "$V"
expect "a word extended past the wording's end: a miss" 0 "+MISS R2#0-0"

fresh; replace "$V/CUSTOMISATION.md" "- $VISITOR" "<!-- How to: $VISITOR -->"; run wording-check --vault "$V"
expect "a rule whose home is a how-to comment inside its section stands in its home" 0 "+2 in their homes" "-MISS"

fresh; printf -- '---\ndescription: %s\n---\nBody.\n' "$VISITOR" >"$V/.claude/agents/helper.md"; edit_data 'by["R2#0-0"]["home"] = {"file": ".claude/agents/helper.md", "section": None}'; replace "$V/CUSTOMISATION.md" "- $VISITOR" ""; run wording-check --vault "$V"
expect "a rule whose home is a helper definition's frontmatter stands in its home" 0 "+2 in their homes" "-MISS"

fresh; replace "$V/CUSTOMISATION.md" "signs the green book" "signs the <!-- vault-local:begin -->green<!-- vault-local:end --> book"; run wording-check --vault "$V"
expect "inline vault-local markers are read past" 0 "+2 in their homes" "-MISS"

# A row's home is its file and section: where a row names a section, the wording must stand inside it.
fresh; replace "$V/CUSTOMISATION.md" "## Visitors" "## Guests"; run wording-check --vault "$V"
expect "a renamed section is a miss, which says the words stand outside it" 0 "+MISS R2#0-0 · CUSTOMISATION.md § Visitors" "+these words stand whole in this file, outside this section" "+1 in their homes, 1 missed (1 of them standing outside their named section)"

misplaced() {
  fresh; edit_data 'data["trial"] = False'
  replace "$V/CUSTOMISATION.md" "- $VISITOR" "- Every visitor signs the red book before the second door."
  replace "$V/CUSTOMISATION.md" "- $GATE" "- $GATE
- $VISITOR"
}
misplaced; run wording-check --vault "$V"
expect "the section changed while another holds the original: a miss, its diff the section's, and outside an install it only lists" 0 "+MISS R2#0-0" "+[-green-] {+red+}" "+these words stand whole in this file, outside this section" "+1 in their homes, 1 missed" "-BLOCKED"
misplaced; run wording-check --vault "$V" --installed-only "R2"
expect "the same case inside an install fails it" 1 "+BLOCKED: R2#0-0" "+this fails the install"
misplaced; run wording-check --vault "$V" --trial --installed-only "R2"
expect "the same case in the trial state is logged" 0 "+TRIAL: would have blocked the install: R2#0-0" "+the trial state blocks nothing"

fresh; edit_data 'data["trial"] = False'; replace "$V/CUSTOMISATION.md" "- $VISITOR" "### At the front door
- $VISITOR"; run wording-check --vault "$V" --installed-only "R2"
expect "a nested heading inside the section: still in its home, and nothing fails" 0 "+2 in their homes" "-MISS" "+nothing fails the install"

fresh; replace "$V/CUSTOMISATION.md" "## Visitors" "## Visitors
### Visitors
A nested heading of the same name.
### At the door"; run wording-check --vault "$V"
expect "a nested heading of the same name leaves the outer section whole" 0 "+2 in their homes" "-MISS"

fresh; replace "$V/CUSTOMISATION.md" "- $VISITOR" "## Elsewhere
### Deeper still
- $VISITOR"; run wording-check --vault "$V"
expect "below the next heading of the section's level: outside it" 0 "+MISS R2#0-0" "+1 of them standing outside"

fresh; replace "$V/CUSTOMISATION.md" "- $VISITOR" "<!--
## Not a heading
-->
- $VISITOR"; run wording-check --vault "$V"
expect "a heading-like line in a comment closes nothing" 0 "+2 in their homes" "-MISS"

fresh; replace "$V/CUSTOMISATION.md" "- $VISITOR" "\`\`\`
## Not a heading
\`\`\`
- $VISITOR"; run wording-check --vault "$V"
expect "a heading-like line in a fence closes nothing" 0 "+2 in their homes" "-MISS"

fresh; replace "$V/CUSTOMISATION.md" "- $VISITOR" ""; replace "$V/CUSTOMISATION.md" "- $GATE" "- $GATE
<!--
## Visitors
- $VISITOR
-->"; run wording-check --vault "$V"
expect "a line reading as the section's heading inside a comment opens nothing" 0 "+MISS R2#0-0" "+1 of them standing outside"

fresh; replace "$V/CUSTOMISATION.md" "- $VISITOR" ""; replace "$V/CUSTOMISATION.md" "- $GATE" "- $GATE
\`\`\`
## Visitors
- $VISITOR
\`\`\`"; run wording-check --vault "$V"
expect "a line reading as the section's heading inside a fence opens nothing" 0 "+MISS R2#0-0" "+1 of them standing outside"

fresh; python3 -B - "$V/CUSTOMISATION.md" <<'PY_INNER'
import sys
text = open(sys.argv[1], encoding="utf-8").read()
open(sys.argv[1], "w", encoding="utf-8", newline="").write(text.replace("\n", "\r\n"))
PY_INNER
run wording-check --vault "$V"
expect "a file with Windows line ends: its sections read the same" 0 "+2 in their homes" "-MISS"

fresh; edit_data 'by["R2#0-0"]["home"]["section"] = None'; replace "$V/CUSTOMISATION.md" "- $VISITOR" ""; replace "$V/CUSTOMISATION.md" "- $GATE" "- $GATE
- $VISITOR"; run wording-check --vault "$V"
expect "control: a row naming no section is compared with its whole file" 0 "+2 in their homes" "-MISS"

fresh; replace "$V/CUSTOMISATION.md" "- $VISITOR" ""; printf '\n## Dated owner notes\n- %s\n' "$VISITOR" >>"$V/CUSTOMISATION.md"; edit_data 'by["R2#0-0"]["home"]["section"] = "Dated owner notes"'; run wording-check --vault "$V"
expect "a section that is the dated owner notes holds nothing the check reads" 0 "+MISS R2#0-0"

# ---- the wording check: dated records and where it reads ----------------------------------------
fresh; edit_data 'by["R2#0-0"]["approved"][0]["text"] = "Only the history holds this retired sentence about the blue door."'; run wording-check --vault "$V"
expect "a wording only the rulings history holds is a miss: the history is never searched" 0 "+MISS R2#0-0"

fresh; edit_data 'by["R2#0-0"]["approved"][0]["text"] = "Only the defect register holds this sentence about the broken hinge."'; run wording-check --vault "$V"
expect "a wording only the defect register holds is a miss" 0 "+MISS R2#0-0"

fresh; edit_data 'by["R2#0-0"]["approved"][0]["text"] = "Dated record line: an invented sentence that only the log holds."'; run wording-check --vault "$V"
expect "a wording only the log holds is a miss" 0 "+MISS R2#0-0"

for dated in wiki/log.md wiki/developments/owner-rulings-history.md wiki/developments/known-issues.md output/reports/x.md notes/run-decisions.md handoffs/a.md; do
  fresh; edit_data "by['R2#0-0']['home']['file'] = '$dated'"; run wording-check --vault "$V"
  expect "a row naming $dated as its home is refused, never read" 0 "+REFUSED R2#0-0" "+1 refused homes" "-MISS"
done

fresh
cat >"$V/wiki/developments/noted.md" <<'EOF'
---
title: "Noted"
---
## Current text
Some current text.

## Dated owner notes

### 2020-01-01 — a note
> The owner's words about the silver spoon, in a note.

## Related
Back to the current text.
EOF
edit_data 'by["R2#0-0"]["home"] = {"file": "wiki/developments/noted.md", "section": "Current text"}; by["R2#0-0"]["approved"][0]["text"] = "The owner'"'"'s words about the silver spoon, in a note."'
run wording-check --vault "$V"
expect "a wording only a dated owner note holds is a miss: notes are never searched" 0 "+MISS R2#0-0"

fresh; edit_data 'by["R2#0-0"]["home"]["file"] = "wiki/developments/fixture-rules.md"'; chmod 000 "$V/wiki/log.md"; run wording-check --vault "$V"
expect "a wording not in the home its row names is a miss, though it stands elsewhere, and an unreadable other file is never touched" 0 "+MISS R2#0-0" "-PROBE FAILED"

fresh; edit_data 'by["R2#0-0"]["home"]["file"] = None'; run wording-check --vault "$V"
expect "a row that names no home is refused" 0 "+REFUSED R2#0-0"

fresh; edit_data 'by["R2#0-0"]["home"]["file"] = "attic/cold.md"; by["R2#0-0"]["approved"][0]["text"] = "cold"'; chmod 000 "$V/attic/cold.md"; run wording-check --vault "$V"
expect "a row naming the attic as home is refused unread" 0 "+REFUSED R2#0-0"

# ---- the wording check: a noted difference ------------------------------------------------------
fresh; replace "$V/CUSTOMISATION.md" "the green book" "the red book"
edit_data 'by["R2#0-0"]["noted"] = [{"date": "2020-06-01", "words": "leave it", "home_text": "Every visitor signs the red book before the second door."}]'
run wording-check --vault "$V"
expect "a noted difference is not listed again" 0 "+1 noted differences" "+0 missed" "-MISS"
replace "$V/CUSTOMISATION.md" "the red book" "the black book"; run wording-check --vault "$V"
expect "a noted difference that changes again is listed" 0 "+MISS R2#0-0" "+0 noted differences"

# ---- the wording check: not applicable, and a page without its data -----------------------------
fresh; rm "$DOC"; run wording-check --vault "$V"
expect "no data file and no page, as in a fresh public copy: not applicable" 0 "+not applicable" "-CONTROL" "-could not check"

fresh; rm "$DOC"; printf 'page\n' >"$V/wiki/developments/rule-register.md"; run wording-check --vault "$V"
expect "the page present with its data gone: could not check, never not applicable" 2 "+could not check: the page exists but its data file is gone" "-not applicable"

fresh; printf '{broken' >"$DOC"; run wording-check --vault "$V"
expect "a torn data file: could not check" 2 "+could not check: the data file cannot be read"

fresh; edit_data 'data["rows"] = []'; run wording-check --vault "$V"
expect "a data file with no rows: the control runs and 0 wordings are checked" 0 "+CONTROL:" "+WORDING: 0 approved wordings" "-all clear"

# ---- the wording check inside an install --------------------------------------------------------
fresh; replace "$V/CUSTOMISATION.md" "the green book" "the red book"; edit_data 'data["trial"] = False'
run wording-check --vault "$V" --installed-only "R2#0-0"
expect "trial off: a miss on a text just placed fails the install" 1 "+BLOCKED: R2#0-0" "+this fails the install"

run wording-check --vault "$V" --installed-only "R1#0-0"
expect "trial off: a miss on a text not just placed is listed and fails nothing" 0 "+MISS R2#0-0" "-BLOCKED" "+nothing fails the install"

printf '# placed\nR1#0-0\nR2\n' >"$WORK/placed.txt"; run wording-check --vault "$V" --installed-only "$WORK/placed.txt"
expect "LIST as a file, a map row's id naming its spans" 1 "+BLOCKED: R2#0-0" "+2 listed"

: >"$WORK/none.txt"; run wording-check --vault "$V" --installed-only "$WORK/none.txt"
expect "an empty LIST: nothing placed, nothing fails, the control still runs" 0 "+CONTROL:" "+0 listed"

run wording-check --vault "$V" --installed-only "nonsense-id"
expect "a LIST none of whose rows is in the register: could not check" 2 "+could not check: listed rows absent from the register: nonsense-id" "-INSTALL:"

run wording-check --vault "$V" --installed-only "R1,nonsense-id"
expect "a LIST with a known row and an unknown one: could not check, naming the unknown, never a pass" 2 "+could not check: listed rows absent from the register: nonsense-id" "-nothing fails the install" "-all clear" "-INSTALL:"

run wording-check --vault "$V" --trial --installed-only "R1,nonsense-id"
expect "the same mixed LIST in the trial state: logged, and it blocks nothing" 0 "+could not check: listed rows absent" "+TRIAL: would have blocked the install: could not check"

run wording-check --vault "$V" --installed-only "R1,R3"
expect "control: a complete LIST of known rows still passes" 0 "+2 listed as just placed, holding 1 approved wordings: 0 of them missed" "+nothing fails the install" "-could not check"

run wording-check --vault "$V" --installed-only "$WORK/gone/placed.txt"
expect "a LIST path that is no file: could not check" 2 "+could not check: the installed list"

run wording-check --vault "$V" --trial --installed-only "R2#0-0"
expect "--trial: logs what it would have blocked and blocks nothing" 0 "+trial state on" "+TRIAL: would have blocked the install: R2#0-0" "+the trial state blocks nothing" "-BLOCKED"

edit_data 'data["trial"] = True'; run wording-check --vault "$V" --installed-only "R2#0-0"
expect "the data's trial state on holds with no flag" 0 "+TRIAL: would have blocked the install: R2#0-0" "-BLOCKED"

edit_data 'del data["trial"]'; run wording-check --vault "$V" --installed-only "R2#0-0"
expect "a data file silent on the trial state counts as on" 0 "+TRIAL: would have blocked the install: R2#0-0"

fresh; edit_data 'data["trial"] = False'; replace "$V/CUSTOMISATION.md" "$MARKER_LINE" "No marker."; run wording-check --vault "$V" --installed-only "R2#0-0"
expect "a could not check inside an install fails it" 2 "+could not check" "-TRIAL"

run wording-check --vault "$V" --trial --installed-only "R2#0-0"
expect "a could not check in the trial state is logged as what it would have blocked" 0 "+could not check" "+TRIAL: would have blocked the install: could not check"

fresh; printf '{torn' >"$DOC"; run wording-check --vault "$V" --installed-only "R2#0-0"
expect "a torn data file inside an install tells no trial state, so it fails the install" 2 "+could not check: the data file cannot be read" "-TRIAL"

run wording-check --vault "$V" --trial --installed-only "R2#0-0"
expect "a torn data file with the flag on is logged" 0 "+TRIAL: would have blocked the install: could not check"

fresh; rm "$DOC"; printf 'page\n' >"$V/wiki/developments/rule-register.md"; run wording-check --vault "$V" --trial
expect "the page with no data, in the trial state: logged" 0 "+could not check" "+TRIAL: would have blocked"

fresh; replace "$V/CUSTOMISATION.md" "the green book" "the red book"; run wording-check --vault "$V"
expect "outside an install it only lists" 0 "+MISS R2#0-0" "-BLOCKED" "-TRIAL" "-INSTALL:"

# A row called approved that holds no wording would pass having compared nothing.
fresh; edit_data 'data["trial"] = False; by["R2#0-0"]["approved"] = []'; run wording-check --vault "$V"
expect "a row called approved with no wording: could not check, its control apart, no result" 2 "+CONTROL:" "+could not check: approved rows hold no wording to compare: R2#0-0" "-WORDING:" "-all clear"
run wording-check --vault "$V" --installed-only "R1"
expect "the same inside an install, whichever row is listed" 2 "+could not check: approved rows hold no wording" "-nothing fails the install"
run wording-check --vault "$V" --trial --installed-only "R1"
expect "the same in the trial state: logged" 0 "+could not check: approved rows hold no wording" "+TRIAL: would have blocked the install: could not check"
run weekly --vault "$V"
expect "the same in the pass: could not check, every other listing still runs" 2 "+PROBE FAILED: could not check: approved rows hold no wording" "+wording_missed=could-not-check" "+COPIES ·" "-WORDING:"
fresh; edit_data 'data["trial"] = False; by["R2#0-0"]["approved"] = []; by["R2#0-0"]["check"] = "reading-only"'; run wording-check --vault "$V" --installed-only "R1"
expect "control: a row moved into data is checked by reading only, so it may hold none" 0 "+WORDING: 1 approved wordings: 1 in their homes" "+nothing fails the install" "-could not check"

# What else a LIST may name a row by, each still checked; a retired row has nothing to compare.
fresh; edit_data 'data["trial"] = False; data["retired_rows"] = ["R9"]'; run wording-check --vault "$V" --installed-only "R1,R9"
expect "a row the seed names as retired is known, with nothing to compare" 0 "+2 listed as just placed" "+nothing fails the install" "-could not check"
fresh; edit_data 'data["trial"] = False; by["R2#0-0"]["merged_from"] = ["R8"]; by["R2#0-0"]["carries"] = ["W-8"]'; replace "$V/CUSTOMISATION.md" "the green book" "the red book"
run wording-check --vault "$V" --installed-only "R8"
expect "a row merged into another names it, and its miss fails the install" 1 "+BLOCKED: R2#0-0"
run wording-check --vault "$V" --installed-only "W-8"
expect "a waiting text a row carries names it, and its miss fails the install" 1 "+BLOCKED: R2#0-0"

# Approved words whose home is a dated record: listed, not checked, with the reason.
listed_row() {
  fresh
  edit_data 'data["trial"] = False; row = by["R2#0-0"]; row["home"] = {"file": "wiki/developments/known-issues.md", "section": None}; row["listed"], row["approved"] = row["approved"], []; row["wording"] = "listed, not checked"; row["wording_reason"] = "its home is a dated record"'
}
listed_row; chmod 000 "$V/wiki/developments/known-issues.md"; run wording-check --vault "$V"
expect "a row listed, not checked is said with its reason, its home unread" 0 "+LISTED R2#0-0 · listed, not checked: its home is a dated record" "+1 rows listed, not checked" "+WORDING: 1 approved wordings: 1 in their homes" "-MISS" "-REFUSED"
run wording-check --vault "$V" --installed-only "R2"
expect "it fails no install" 0 "+LISTED R2#0-0" "+holding 0 approved wordings: 0 of them missed, 0 refused; 1 rows listed, not checked" "+nothing fails the install" "-BLOCKED"
chmod 644 "$V/wiki/developments/known-issues.md"
run wording-check --vault "$V" --trial --installed-only "R2"
expect "and the trial state would have blocked nothing for it" 0 "+1 rows listed, not checked" "-TRIAL: would have blocked"
run weekly --vault "$V"
expect "the pass only counts it, since its reason does not change" 0 "+1 rows listed, not checked" "-LISTED R2#0-0"
run weekly --vault "$V" --full
expect "and --full lists it" 0 "+LISTED R2#0-0 · listed, not checked: its home is a dated record"
run generate --vault "$V"; cp "$V/wiki/developments/rule-register.md" "$OUT"; rc=0
expect "the page counts it, and says what the status means" 0 "+1 listed, not checked" "+\`listed, not checked\`: the approved words stand in a dated record"
listed_row; edit_data 'del by["R2#0-0"]["wording_reason"]'; run wording-check --vault "$V" --installed-only "R2"
expect "listed with no reason: could not check" 2 "+could not check: rows are listed, not checked with no dated record for a home, no reason, or a wording to compare: R2#0-0"
listed_row; edit_data 'by["R2#0-0"]["home"]["file"] = "CUSTOMISATION.md"'; run wording-check --vault "$V" --installed-only "R2"
expect "listed with an ordinary file for a home, a way to switch the check off: could not check" 2 "+could not check: rows are listed, not checked"
listed_row; edit_data 'by["R2#0-0"]["approved"] = by["R2#0-0"]["listed"]'; run wording-check --vault "$V" --installed-only "R2"
expect "listed while holding a wording to compare: could not check" 2 "+could not check: rows are listed, not checked"

fresh; edit_data 'data["trial"] = False; by["R2#0-0"]["home"]["file"] = "wiki/log.md"'; run wording-check --vault "$V" --installed-only "R2"
expect "trial off: a just-placed row whose home is refused could not be checked, so it fails the install" 1 "+BLOCKED: R2#0-0 · wiki/log.md" "+1 refused" "+this fails the install"
run wording-check --vault "$V" --installed-only "R1"
expect "trial off: a refused row not just placed fails nothing" 0 "+REFUSED R2#0-0" "-BLOCKED" "+nothing fails the install"
edit_data 'data["trial"] = True'; run wording-check --vault "$V" --installed-only "R2"
expect "the trial state logs a refused row and blocks nothing" 0 "+TRIAL: would have blocked the install: R2#0-0" "+the trial state blocks nothing"

# ---- the coverage check -------------------------------------------------------------------------
fresh; run weekly --vault "$V"
expect "clean pass: each listing at zero carries its control" 0 \
  "+COVERAGE 1 · always-on rule sentences with no register row: 0 (control: 5 blocks read in 2 files, 5 row texts located there)" \
  "+COVERAGE 2 · register rows whose text has left its home: 0 (control: 6 of 6 compared rows found at home" \
  "+COVERAGE 3 · fixed rules that name no failure: 0 (control: 1 fixed or mechanism rows read of 6, 1 naming one)" \
  "+COPIES · full copies of an approved wording on forward-facing files: 0" "+2 found at their homes" "-PROBE FAILED" "+SUMMARY "

fresh; printf -- '- A rule added since the seed has no row at all.\n' >>"$V/CUSTOMISATION.md"; run weekly --vault "$V"
expect "a sentence added in an always-on file is listed with its place" 0 "+no register row: 1" "+NOROW CUSTOMISATION.md:" "+§ Visitors · - A rule added since the seed has no row at all."

fresh; replace "$V/CUSTOMISATION.md" "- $GATE" "- $GATE A new sentence stands beside the kept span."; run weekly --vault "$V"
expect "a sentence inserted beside a kept span is listed, the span itself not" 0 "+no register row: 1" "+A new sentence stands beside the kept span." "-NOROW CUSTOMISATION.md:9 § Settings · - The garden"

fresh; edit_data 'rows.append(dict(by["R3#0-0"], id="R8#0-0", text="```yaml\ncode: block row\n```"))'; replace "$V/CUSTOMISATION.md" "## Settings" "## Settings
\`\`\`yaml
code: block row
\`\`\`
"; run weekly --vault "$V"
expect "a code-block row, fences and all, covers its lines" 0 "+no register row: 0"

fresh; replace "$V/CUSTOMISATION.md" "## Settings" "## Settings
\`\`\`
tree entry naming a folder
\`\`\`
| Head one | Head two |
|---|---|
| a table row with words | stays listed |

---
"; run weekly --vault "$V"
expect "fence lines, rules and table headers are no rule; a fenced line and a table row are" 0 "+no register row: 2" "+tree entry naming a folder" "+a table row with words" "-Head one" "-NOROW CUSTOMISATION.md:8 § Settings · \`\`\`"

fresh; edit_data 'by["R3#0-0"]["pointers"] = []; by["R3#0-0"]["home"] = {"file": "wiki/developments/fixture-rules.md", "section": "Rules"}; by["R3#0-0"]["from"] = {"file": "CUSTOMISATION.md", "section": "Settings"}'
run weekly --vault "$V"
expect "a moved row still at its source says its move may have been sent back" 0 "+has left its home: 1" "+LEFT R3#0-0" "+still at its source CUSTOMISATION.md" "+no register row: 1"

fresh; replace "$V/CUSTOMISATION.md" "- $GATE" "- A pointer sentence names the page instead."
edit_data 'by["R3#0-0"]["home"] = {"file": "wiki/developments/fixture-rules.md", "section": "Rules"}; by["R3#0-0"]["from"] = {"file": "CUSTOMISATION.md"}; by["R3#0-0"]["pointers"] = [{"file": "CUSTOMISATION.md", "text": "A pointer sentence names the page instead."}]'
printf -- '- %s\n' "$GATE" >>"$V/wiki/developments/fixture-rules.md"; run weekly --vault "$V"
expect "a pointer a move left behind counts as covered" 0 "+no register row: 0" "+has left its home: 0"

fresh; replace "$V/CUSTOMISATION.md" "- $GATE" "- The garden gate shuts in summer."; run weekly --vault "$V"
expect "a row whose text changed has left its home, and the new text has no row" 0 "+LEFT R3#0-0" "+its text is gone from the home" "+no register row: 1"

fresh; cat >>"$V/wiki/developments/fixture-rules.md" <<'EOF'

## Dated owner notes
### 2020-01-01 — a note
> Words of a note that a row names as its home.
EOF
edit_data 'rows.append(dict(by["R6#0-0"], id="R7#0-0", text="Words of a note that a row names as its home."))'; run weekly --vault "$V"
expect "the coverage check, no wording check, finds a row's text in an owner note" 0 "+has left its home: 0"

fresh; edit_data 'by["R3#0-0"]["home"]["file"] = "wiki/developments/no-such-page.md"'; run weekly --vault "$V"
expect "a row whose home is gone is listed" 0 "+LEFT R3#0-0" "+the home cannot be read"

fresh; edit_data 'by["R3#0-0"]["check"] = "reading-only"; by["R3#0-0"]["home"] = {"file": "x/routing.json", "entry": "a row"}; by["R3#0-0"]["text"] = "words no file holds"'; replace "$V/CUSTOMISATION.md" "- $GATE" ""
run weekly --vault "$V"
expect "a text moved into data is checked by reading only, never compared" 0 "+has left its home: 0" "+1 rows moved into data"

fresh; edit_data 'by["R3#0-0"]["shape"] = "fixed"; by["R3#0-0"]["failure"] = "none named"; by["R4#0-0"]["shape"] = "mechanism"; by["R5#0-0"]["shape"] = "fixed"; by["R5#0-0"]["failure"] = ""'; run weekly --vault "$V"
expect "fixed rules naming no failure are listed: empty, none named, and a mechanism" 0 "+name no failure: 3" "+NOFAIL R3#0-0 · fixed" "+NOFAIL R4#0-0 · mechanism" "+NOFAIL R5#0-0 · fixed" "-NOFAIL R1"

fresh; edit_data 'rows[:] = [r for r in rows if r["id"] == "R2#0-0"]'; replace "$V/CUSTOMISATION.md" "$VISITOR" "Nothing like the stored words."; run weekly --vault "$V"
expect "no row found at its home: a broken premise, reported apart, and the pass still lists" 2 "+PROBE FAILED: none of 1 compared rows" "+FLAGS ·" "+SUMMARY "

fresh; run weekly --vault "$V"
expect "no baseline: nothing is called unchanged" 0 "+COVERAGE 4 · rule-holding pages and READMEs changed: no baseline yet" "+OLDER RULINGS · no baseline yet" "+SOURCES · no baseline yet" "+rule_files_changed=no-baseline" "-changed since the audit"

fresh; run record-audit --vault "$V" --today 2020-07-01
expect "record-audit writes the baseline" 0 "+record-audit 2020-07-01:"
grep -q '"rule_files"' "$DOC"; rc=$?; expect "the baseline sits in the data's audit block" 0
run weekly --vault "$V"
expect "after the baseline: nothing changed, with controls" 0 "+changed since the audit of 2020-07-01: 0 changed, 0 new, 0 gone (control: 2 files fingerprinted, 2 unchanged)" "+newer dated rulings beside older ones since the audit of 2020-07-01: 0" "+cited or named files changed since the audit of 2020-07-01: 0"

# Fingerprints use neither file dates nor git: a touch is no change; a change hidden behind an old date is.
printf 'readme changed\n' >"$V/output/README.md"; touch -t 200001010000 "$V/output/README.md"; touch "$V/raw/two.md"; run weekly --vault "$V"
expect "a changed README with its date set back is listed; a touched source is not" 0 "+1 changed, 0 new, 0 gone" "+CHANGED output/README.md" "-CHANGED raw/two.md"
python3 -B - "$TOOL" >"$OUT" 2>&1 <<'PY'
import re, sys
source = open(sys.argv[1], encoding="utf-8").read()
def body(name):
    start = source.index("def %s(" % name)
    end = source.find("\ndef ", start + 1)
    return source[start:end]
dates = re.compile(r"mtime|ctime|\.stat\(|lstat|subprocess|\bgit\b")
scanned = [n for n in ("fingerprint", "fingerprints_of", "compare_prints", "cited_files", "list_sources", "list_rule_holding", "cmd_record_audit") if dates.search(body(n))]
control = bool(dates.search(body("tree_stats")))
calls = re.findall(r"subprocess\.run\(\[([^\]]*)\]", source)
print("hits", scanned, "control", control, "calls", calls)
sys.exit(0 if not scanned and control and calls == ['"du", "-sk", path'] else 1)
PY
rc=$?
expect "fingerprint code reads no file date and no git, the same scan hits the clean-up's age test, and du is the only program called" 0 "+hits [] control True"

mkdir -p "$V/output/new-folder"; printf 'hello\n' >"$V/output/new-folder/README.md"; rm "$V/output/README.md"; run weekly --vault "$V"
expect "a new README and a gone one are listed" 0 "+NEW output/new-folder/README.md" "+GONE output/README.md"

fresh; run record-audit --vault "$V" --today 2020-07-01
printf 'edited\n' >"$V/wiki/developments/fixture-rules.md"; run weekly --vault "$V"
expect "a rule-holding page changed is listed" 0 "+CHANGED wiki/developments/fixture-rules.md"

fresh; edit_data 'data["rule_holding_pages"] = ["wiki/sources/ahead.md"]'; run record-audit --vault "$V" --today 2020-07-01
printf 'edited\n' >>"$V/wiki/sources/ahead.md"; run weekly --vault "$V"
expect "a page the data names as rule-holding is watched" 0 "+CHANGED wiki/sources/ahead.md"

fresh; run record-audit --vault "$V" --today 2020-07-01
edit_data 'data["audit"]["rule_files"] = {k: "0" * 64 for k in data["audit"]["rule_files"]}; data["audit"]["sources"] = {}'; run weekly --vault "$V"
expect "a wholesale fingerprint change is listed as changed, each file" 0 "+2 changed"

fresh; run record-audit --vault "$V" --today 2020-07-01
edit_data 'data["audit"]["sources"] = {"gone/elsewhere.md": "0" * 64}; data["audit"]["rule_files"] = {"gone/else.md": "0" * 64}'; run weekly --vault "$V"
expect "no recorded fingerprint matching any file: a broken premise" 2 "+PROBE FAILED: none of the 1 recorded fingerprints"

# ---- the older-rulings listing ------------------------------------------------------------------
fresh; run record-audit --vault "$V" --today 2020-07-01
replace "$V/CUSTOMISATION.md" "- $GATE" "- $GATE
- **The kettle may boil (owner, 9 July 2026)**: the kettle may boil once tea is made."
run weekly --vault "$V"
expect "a newer dated ruling beside an older one is listed as a pair" 0 "+since the audit of 2020-07-01: 1," "+NEWER CUSTOMISATION.md:" "+§ Settings · 2026-07-09" "+beside 1 older, closest: 2026-03-02"

run record-audit --vault "$V" --today 2020-07-08; run weekly --vault "$V"
expect "once recorded, it comes up no more" 0 "+since the audit of 2020-07-08: 0,"

fresh; run record-audit --vault "$V" --today 2020-07-01
replace "$V/CUSTOMISATION.md" "- $VISITOR" "- $VISITOR
- **Visitors may leave (owner, 9 July 2026)**: they sign out too."
run weekly --vault "$V"
expect "a first dated ruling in a home with no older one is no pair" 0 "+since the audit of 2020-07-01: 0," "-NEWER"

fresh; run record-audit --vault "$V" --today 2020-07-01
replace "$V/CUSTOMISATION.md" "- $GATE" "- $GATE
- **Older words (owner, 1 January 2020)**: filed late."
run weekly --vault "$V"
expect "a ruling dated before all others in its home is no newer ruling" 0 "+since the audit of 2020-07-01: 0," "-NEWER CUSTOMISATION.md"

fresh; run record-audit --vault "$V" --today 2020-07-01
replace "$V/CUSTOMISATION.md" "- $GATE" "- $GATE
- **Later words (owner, 9 July 2026)**: a first bullet."
run record-audit --vault "$V" --today 2020-07-02
replace "$V/CUSTOMISATION.md" "a first bullet." "a first bullet reworded with no new marker."; run weekly --vault "$V"
expect "a bullet reworded under the same marker is no new ruling" 0 "+since the audit of 2020-07-02: 0,"
replace "$V/CUSTOMISATION.md" "- $GATE" "- $GATE
- **Later words (owner, 9 July 2026)**: a second bullet with the very same marker."
run weekly --vault "$V"
expect "a second bullet with the same marker is seen, since the count rose" 0 "+a second bullet with the very same marker"

fresh; replace "$V/CUSTOMISATION.md" "(owner, 2 March 2026)" "(a plain note)"; replace "$V/wiki/developments/fixture-rules.md" "(owner, 5 March 2026)" "(a plain note)"; edit_data 'rows[:] = [r for r in rows if r["id"] in ("R3#0-0", "R4#0-0")]'; run weekly --vault "$V"
expect "no dated ruling read anywhere: a broken premise, never zero" 2 "+PROBE FAILED: no dated ruling was read"

# ---- the copies listing -------------------------------------------------------------------------
fresh; printf 'A step quoting it: %s\n' "$VISITOR" >>"$V/.claude/skills/fix/SKILL.md"; run weekly --vault "$V"
expect "a full copy in a skill is listed" 0 "+forward-facing files: 1" "+COPY R2#0-0 · .claude/skills/fix/SKILL.md"
for place in .claude/agents/helper.md .claude/hooks/h.py output/README.md CLAUDE.md; do
  fresh; printf 'Quoting: %s\n' "$VISITOR" >>"$V/$place"; run weekly --vault "$V"
  expect "a full copy in $place is listed" 0 "+COPY R2#0-0 · $place"
done

fresh; mkdir -p "$LLM_WIKI_STORE/hooks"; printf '# Quoting: %s\n' "$VISITOR" >"$LLM_WIKI_STORE/hooks/machine.py"; run weekly --vault "$V"
expect "a full copy in a machine-local hook is listed" 0 "+forward-facing files: 1" "+hooks/machine.py"
rm -rf "$LLM_WIKI_STORE"

fresh; printf 'Short words: %s\n' "$VISITOR" >>"$V/wiki/sources/unflagged.md"; printf '%s\n' "$VISITOR" >"$V/output/reports/x.md"; run weekly --vault "$V"
expect "a copy on a wiki page or report is no forward-facing copy" 0 "+forward-facing files: 0" "-COPY"

fresh; printf 'Partly: Every visitor signs the green book.\n' >>"$V/.claude/skills/fix/SKILL.md"; run weekly --vault "$V"
expect "a partial copy is not listed" 0 "+forward-facing files: 0" "-COPY"

fresh; edit_data 'by["R2#0-0"]["approved"][0]["text"] = "Five words only stand here."'; replace "$V/CUSTOMISATION.md" "- $VISITOR" "- Five words only stand here."; printf 'Five words only stand here.\n' >>"$V/.claude/agents/helper.md"; run weekly --vault "$V"
expect "a short wording's copy is listed too" 0 "+COPY R2#0-0 · .claude/agents/helper.md"

fresh; printf 'A step quoting it: "%s"\n' "$VISITOR" >>"$V/.claude/skills/fix/SKILL.md"; printf 'And in brackets (%s) too.\n' "$VISITOR" >>"$V/.claude/agents/helper.md"; run weekly --vault "$V"
expect "a copy a quote mark or a bracket abuts is listed" 0 "+forward-facing files: 2" "+COPY R2#0-0 · .claude/skills/fix/SKILL.md" "+COPY R2#0-0 · .claude/agents/helper.md"

fresh; printf 'Short of it: Every visitor signs the green book before the third door.\n' >>"$V/.claude/skills/fix/SKILL.md"; run weekly --vault "$V"
expect "control: the same words with the last changed share the key and are no copy" 0 "+forward-facing files: 0" "-COPY"

fresh; printf 'A carrier: %s\n' "$VISITOR" >>"$V/.claude/agents/helper.md"; edit_data 'by["R2#0-0"]["carriers"] = [".claude/agents/helper.md"]'; run weekly --vault "$V"
expect "a declared carrier that agrees is compared, not listed" 0 "+forward-facing files: 0" "+differing from their home: 0 of 1" "-COPY"

fresh; printf 'A carrier: Every visitor signs the blue book before the second door.\n' >>"$V/.claude/agents/helper.md"; edit_data 'by["R2#0-0"]["carriers"] = [".claude/agents/helper.md"]'; run weekly --vault "$V"
expect "a declared carrier that differs is listed with the difference" 0 "+differing from their home: 1 of 1" "+CARRIER R2#0-0 · .claude/agents/helper.md differs" "+{+blue+}"

fresh; edit_data 'by["R2#0-0"]["carriers"] = [".claude/agents/no-such.md"]'; run weekly --vault "$V"
expect "a declared carrier that is gone is listed" 0 "+CARRIER R2#0-0" "+(no similar text there)"

# ---- flags ----------------------------------------------------------------------------------------
fresh; run weekly --vault "$V" --today 2020-06-01
expect "a flag past its date is due; its own opening date does not count; a date ahead waits; an event is listed" 0 \
  "+FLAGS · 3 read: 1 due by a date that has passed, 1 naming a date ahead, 1 naming an event, for the review to judge whether it has passed, 0 with no clause" \
  "+DUE wiki/developments/fixture-rules.md · cleared by 2020-02-01" \
  "+EVENT wiki/sources/eventful.md · Clears when the table is captured again" "-wiki/sources/ahead.md" "-wiki/sources/unflagged.md" "+flags_due=1 flags_event=1 flags_no_clause=0"

fresh; printf -- '---\ntitle: "N"\nflagged: "2020-01-01 re-ingest before quoting this page."\n---\nBody.\n' >"$V/wiki/sources/noclause.md"; run weekly --vault "$V" --today 2020-06-01
expect "a flag with no clause saying what clears it is said to have none, and is read" 0 "+1 with no clause" "+NOCLAUSE wiki/sources/noclause.md · 2020-01-01 re-ingest"

run weekly --vault "$V" --today 2020-01-15
expect "a flag whose date has not come is not due" 0 "+0 due by a date that has passed, 2 naming a date ahead"

fresh; replace "$V/wiki/sources/ahead.md" "a flag that clears on 2099-01-01." "words. Clears on 2020-01-02."; run weekly --vault "$V" --today 2020-06-01
expect "the method's form, Clears on a date, comes up when due" 0 "+DUE wiki/sources/ahead.md · cleared by 2020-01-02"

# Each flag comes up once, when it is due: record-audit records what came up, and then it is only counted.
fresh; run weekly --vault "$V" --today 2020-06-01
expect "the first pass that sees them lists the due flag and the event flag" 0 "+DUE wiki/developments/fixture-rules.md" "+EVENT wiki/sources/eventful.md" "+2 listed here, 0 listed at an earlier audit" "+flags_listed=2"
run weekly --vault "$V" --today 2020-06-08
expect "with nothing recorded yet, a second pass lists them again, so none is lost before the audit is walked through" 0 "+DUE wiki/developments/fixture-rules.md" "+EVENT wiki/sources/eventful.md"
run record-audit --vault "$V" --today 2020-06-08
expect "record-audit records them, and names each it records for the first time" 0 "+2 flags recorded" "+flags recorded for the first time, or with new text; each should be one the pass listed: wiki/developments/fixture-rules.md, wiki/sources/eventful.md"
python3 -B - "$DOC" >"$OUT" 2>&1 <<'PY'
import json, sys
flags = json.load(open(sys.argv[1], encoding="utf-8"))["audit"]["flags"]
print(sorted(flags))
sys.exit(0 if sorted(flags) == ["wiki/developments/fixture-rules.md", "wiki/sources/eventful.md"] and all(len(v) == 16 for v in flags.values()) else 1)
PY
rc=$?; expect "they sit in the data's audit block, and the flag with a date ahead does not" 0
run weekly --vault "$V" --today 2020-06-15
expect "after the record they are only counted: nothing repeats, the count stays whole" 0 "-DUE wiki/" "-EVENT wiki/" "+0 listed here, 2 listed at an earlier audit" "+flags_due=1 flags_event=1 flags_no_clause=0 flags_listed=0" "+1 due by a date that has passed, 1 naming a date ahead, 1 naming an event"
run record-audit --vault "$V" --today 2020-06-15
expect "a second record-audit has nothing new to name" 0 "+2 flags recorded" "-recorded for the first time"
run weekly --vault "$V" --today 2020-06-22
expect "nor does a later week list them" 0 "-DUE wiki/" "-EVENT wiki/" "+0 listed here, 2 listed at an earlier audit"
run weekly --vault "$V" --today 2020-06-22 --all-flags
expect "the review can still ask for the whole list, the flag with a date ahead still waiting" 0 "+DUE wiki/developments/fixture-rules.md" "+EVENT wiki/sources/eventful.md" "+2 listed here, 0 listed at an earlier audit" "-wiki/sources/ahead.md"
replace "$V/wiki/sources/eventful.md" "the capture lost its table. Clears when the table is captured again." "the capture lost its figure. Clears when the figure is captured again."
run weekly --vault "$V" --today 2020-06-22
expect "a flag whose text changes is listed again, and only it" 0 "+EVENT wiki/sources/eventful.md · Clears when the figure is captured again" "-DUE wiki/" "+1 listed here, 1 listed at an earlier audit"
run record-audit --vault "$V" --today 2020-06-22; run weekly --vault "$V" --today 2020-06-29
expect "once recorded with its new text it is only counted again" 0 "-EVENT wiki/" "+0 listed here, 2 listed at an earlier audit"
replace "$V/wiki/sources/eventful.md" 'flagged: "2020-03-03 the capture lost its figure. Clears when the figure is captured again."' 'flagged: "2020-03-03 the capture lost  its figure. Clears when the figure is
  captured again."'
run weekly --vault "$V" --today 2020-06-29
expect "a flag only re-wrapped is the same flag" 0 "-EVENT wiki/" "+0 listed here, 2 listed at an earlier audit"

fresh; run record-audit --vault "$V" --today 2020-01-15
run weekly --vault "$V" --today 2020-01-16
expect "a date ahead at the audit is neither listed nor recorded" 0 "+0 listed here" "-DUE wiki/" "+2 naming a date ahead"
run weekly --vault "$V" --today 2020-02-05
expect "so it comes up once its date has passed" 0 "+DUE wiki/developments/fixture-rules.md · cleared by 2020-02-01" "+1 listed here, 1 listed at an earlier audit" "-EVENT wiki/"
run record-audit --vault "$V" --today 2020-03-01; run weekly --vault "$V" --today 2020-03-08
expect "and once recorded it is only counted, though still due" 0 "-DUE wiki/" "+1 due by a date that has passed" "+0 listed here, 2 listed at an earlier audit"

fresh; run record-audit --vault "$V" --today 2020-06-08; run record-audit --vault "$V" --today 2020-06-15; run weekly --vault "$V" --today 2020-07-05
expect "a recorded flag stays counted for 27 days from its listing, a later record not restarting them" 0 "-EVENT wiki/" "-DUE wiki/" "+0 listed here, 2 listed at an earlier audit"
run weekly --vault "$V" --today 2020-07-06
expect "a flag still on its page comes up again 28 days after it was listed, so a pending event is not lost" 0 "+EVENT wiki/sources/eventful.md" "+DUE wiki/developments/fixture-rules.md" "+2 listed here, 0 listed at an earlier audit"
run record-audit --vault "$V" --today 2020-07-06; run weekly --vault "$V" --today 2020-07-13
expect "recording that listing starts its 28 days again" 0 "-EVENT wiki/" "-DUE wiki/" "+0 listed here, 2 listed at an earlier audit"
fresh; printf -- '---\ntitle: "N"\nflagged: "2020-01-01 re-ingest before quoting this page."\n---\nBody.\n' >"$V/wiki/sources/noclause.md"; run record-audit --vault "$V" --today 2020-06-01; run weekly --vault "$V" --today 2020-06-08
expect "a no-clause flag too is listed once" 0 "-NOCLAUSE wiki/" "+1 with no clause" "+flags_no_clause=1 flags_listed=0"
python3 -B - "$V/wiki/sources/noclause.md" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
open(sys.argv[1], "w", encoding="utf-8").write(re.sub(r"^flagged:.*\n", "", text, flags=re.M))
PY
run record-audit --vault "$V" --today 2020-06-08; printf -- '---\ntitle: "N"\nflagged: "2020-01-01 re-ingest before quoting this page."\n---\nBody.\n' >"$V/wiki/sources/noclause.md"; run weekly --vault "$V" --today 2020-06-15
expect "a flag cleared at one audit and set again is new" 0 "+NOCLAUSE wiki/sources/noclause.md"

fresh; python3 -B - "$DOC" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
data["audit"] = {"at": "2020-01-01", "rule_files": {}, "sources": {}, "rulings": {}}
json.dump(data, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False)
PY
run weekly --vault "$V" --today 2020-06-01
expect "an audit block from before this record lists every flag once" 0 "+DUE wiki/developments/fixture-rules.md" "+EVENT wiki/sources/eventful.md"

fresh; for f in wiki/developments/fixture-rules.md wiki/sources/ahead.md wiki/sources/eventful.md; do python3 -B - "$V/$f" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
open(sys.argv[1], "w", encoding="utf-8").write(re.sub(r"^flagged:.*\n", "", text, flags=re.M))
PY
done; run weekly --vault "$V"
expect "no flags: zero, with the pages read as control" 0 "+FLAGS · 0 read" "+(control: 7 wiki pages read)"

fresh; python3 -B - "$V/wiki/sources/eventful.md" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read()
open(sys.argv[1], "w", encoding="utf-8").write(text.replace('Clears when the table is captured again."', 'Clears when the table is captured again."\nbody-only: x').replace("---\ntitle", "---\ntitle", 1))
PY
for i in $(seq 1 60); do printf -- '---\ntitle: "F%s"\nflagged: "2020-01-01 words that need a reading."\n---\nBody.\n' "$i" >"$V/wiki/sources/f$i.md"; done; run weekly --vault "$V"
expect "the flags listing is never capped, since the review reads each" 0 "+NOCLAUSE wiki/sources/f9.md" "+NOCLAUSE wiki/sources/f60.md" "-and 20 more"

fresh; for i in $(seq 1 60); do printf -- '- Rule %s added with no row at all here.\n' "$i" >>"$V/CUSTOMISATION.md"; done; run weekly --vault "$V"
expect "another listing shows its cap, its count whole" 0 "+no register row: 60" "+… and 20 more (--full lists them)"
run weekly --vault "$V" --full
expect "--full lists them all" 0 "+Rule 60 added" "-and 20 more"

# ---- sources changed since their last audit -------------------------------------------------------
fresh; run record-audit --vault "$V" --today 2020-07-01; printf 'one changed\n' >"$V/raw/one.md"; touch -t 200001010000 "$V/raw/one.md"; run weekly --vault "$V"
expect "a cited source changed is listed with the pages citing it, its date set back or not" 0 "+files changed since the audit of 2020-07-01: 1, naming 2 pages" "+CHANGED raw/one.md ← 2 pages: wiki/developments/fixture-rules.md, wiki/sources/unflagged.md"

fresh; run record-audit --vault "$V" --today 2020-07-01; printf 'print("changed")\n' >"$V/.claude/skills/fix/tool.py"; run weekly --vault "$V"
expect "a file a page names in its body is listed" 0 "+CHANGED .claude/skills/fix/tool.py ← 1 pages: wiki/developments/fixture-rules.md"

fresh; run record-audit --vault "$V" --today 2020-07-01; rm "$V/raw/two.md"; run weekly --vault "$V"
expect "a cited source gone is listed" 0 "+GONE raw/two.md"

fresh; printf 'x' >"$V/.DS_Store"; printf 'Names `.DS_Store` here.\n' >>"$V/wiki/sources/unflagged.md"; run record-audit --vault "$V" --today 2020-07-01
grep -q 'DS_Store' "$DOC"; rc=$?; expect "a folder's system file a page names is never fingerprinted" 1

fresh; chmod 000 "$V/attic/cold.md" "$V/output/user-notes/credentials.env"; run record-audit --vault "$V" --today 2020-07-01
expect "the attic and credentials named by a page: never fingerprinted, no failure" 0 "+record-audit"
grep -qE 'attic/cold|credentials' "$DOC"; rc=$?; expect "neither appears in the recorded fingerprints" 1
run weekly --vault "$V"
expect "the pass runs with both unreadable" 0 "-PROBE FAILED" "-attic/cold" "-credentials"
chmod 644 "$V/attic/cold.md" "$V/output/user-notes/credentials.env"

fresh; python3 -B - "$V/wiki/developments/fixture-rules.md" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
open(sys.argv[1], "w", encoding="utf-8").write(re.sub(r"^sources:.*\n", 'sources: [raw/nothing-here.md]\n', text, flags=re.M))
PY
python3 -B - "$V/wiki/sources/unflagged.md" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
open(sys.argv[1], "w", encoding="utf-8").write(re.sub(r"^sources:.*\n", 'sources: [raw/nothing-here.md]\n', text, flags=re.M))
PY
rm "$V/.claude/skills/fix/tool.py"; run weekly --vault "$V"
expect "pages cite sources and none resolves: a broken premise" 2 "+PROBE FAILED: pages cite sources but none of them resolved"

# ---- the one pass, as a whole -------------------------------------------------------------------
fresh; rm "$DOC"; run weekly --vault "$V" --today 2020-06-01
expect "no data, as in a fresh public copy: the flags list and the rest says not applicable" 0 "+WORDING · not applicable" "+COVERAGE, OLDER RULINGS and COPIES · not applicable" "+SOURCES · not applicable" "+DUE wiki/developments/fixture-rules.md" "-PROBE FAILED" "+no audit block records a listing, so these come up at every pass"

fresh; rm -rf "$V/wiki" "$DOC"; run weekly --vault "$V"
expect "a fresh copy with no wiki pages at all: not applicable, exit 0" 0 "+FLAGS · not applicable (no wiki pages)" "-PROBE FAILED"

fresh; replace "$V/CUSTOMISATION.md" "the green book" "the red book"; printf 'Copied: %s\n' "$KETTLE" >>"$V/.claude/agents/helper.md"; run weekly --vault "$V"
expect "misses and listings stop no work: exit 0, with the summary's counts" 0 "+wording_missed=1" "+copies=1" "+SUMMARY "

fresh; replace "$V/CUSTOMISATION.md" "$MARKER_LINE" "No marker."; run weekly --vault "$V" --today 2020-06-01
expect "could not check in the pass: said, exit 2, every other listing still runs, and no result is claimed" 2 "+PROBE FAILED: could not check" "+wording_missed=could-not-check" "+DUE wiki/developments/fixture-rules.md" "+COPIES ·" "-WORDING:"

fresh; rm "$DOC"; printf 'page\n' >"$V/wiki/developments/rule-register.md"; run weekly --vault "$V"
expect "the page with its data gone, in the pass: could not check" 2 "+PROBE FAILED: could not check: the page exists"

# ---- seed ------------------------------------------------------------------------------------------
seed_fixture() {
  SEED="$WORK/seed"; rm -rf "$SEED"; mkdir -p "$SEED"
  python3 -B - "$SEED" <<'PY'
import json, sys
out = sys.argv[1]
AGENT_STATUS = "ai" + "myth"   # the rule list's value, joined here since the agent's name never ships in a file
def sentences(text, parts):
    spans, at = [], 0
    for part in parts:
        spans.append([at, at + len(part)])
        at += len(part)
    assert at == len(text), (at, len(text))
    return spans
def rule(rid, file, heading, parts, **more):
    text = "".join(parts)
    base = {"id": rid, "kind": "rule", "file": file, "heading_path": heading, "text": text,
            "sentences": sentences(text, parts), "marks": [], "wording": AGENT_STATUS}
    base.update(more)
    return base
rules = [
    rule("U-1", "CUSTOMISATION.md", "# T > ## Alpha", ["- First kept sentence. ", "Second moved sentence. ", "Third retired sentence.\n"]),
    rule("U-2", "CUSTOMISATION.md", "# T > ## Beta", ["- **Lead (owner, 2 March 2026)**: an approved first sentence. ", "An unmarked second sentence. ", "**Later (owner, 4 April 2026)**: a marked sentence with no record.\n"], marks=[0, 2], mark_text="owner", wording="marked", ruling_dates=["2026-03-02", "2026-04-04"]),
    rule("U-3", "CUSTOMISATION.md", "# T > ## Beta", ["- **Words (owner, 5 May 2026)**: approved words a designer would reword.\n"], marks=[0], mark_text="owner", wording="marked"),
    rule("U-4", "CUSTOMISATION.md", "# T > ## Beta", ["- **Seam (owner, 6 June 2026)**: approved words with a seam here.\n"], marks=[0], mark_text="owner", wording="marked"),
    rule("U-5", "CUSTOMISATION.md", "# T > ## Gamma", ["A clause for the merge. "]),
    rule("U-6", "CUSTOMISATION.md", "# T > ## Gamma", ["Another clause for it. "]),
    rule("U-7", "CUSTOMISATION.md", "# T > ## Gamma", ["Plain words reworded in place.\n"]),
    rule("U-8", "CUSTOMISATION.md", "# T > ## Gamma", ["A routing clause.\n"]),
    rule("U-9", "CUSTOMISATION.md", "# T > ## Gamma", ["Left out by every designer.\n"]),
    rule("U-10", "CUSTOMISATION.md", "# T > ## Gamma", ["An owner clause for a proposed merge.\n"]),
    {"id": "W-1", "name": "a waiting text", "text": "A waiting text with its approval.", "sentences": [[0, 33]], "wording": "approved-record", "record": {"file": "decisions", "locator": "1"}},
    {"id": "W-2", "name": "another", "text": "An agent-worded waiting text.", "sentences": [[0, 29]], "wording": AGENT_STATUS},
    {"id": "X-BC-1.1", "file": "wiki/x.md", "text": "Gone text.", "sentences": [[0, 10]], "status": "gone"},
    {"id": "C-NR", "kind": "non-rule", "file": "CLAUDE.md", "text": "## Heading\n"},
]
common = {"principle": "2", "whose": "product", "layer": "core", "shape": "guided", "moment": "always-on"}
lines = [
    dict(common, row="U-1", s=[0, 0], action="keep"),
    dict(common, row="U-1", s=[1, 1], action="move", to={"file": "wiki/developments/routing-table.md", "section": "## The table"}, pointer="See the routing table.", shape="fixed", failure="a stale route", reason="principle 6", sure="sure"),
    dict(common, row="U-1", s=[2, 2], action="retire", ended_by="a later ruling", reason="ended"),
    dict(common, row="U-2", s=[0, 0], action="keep", whose="owner", layer="user"),
    dict(common, row="U-2", s=[1, 2], action="move", to={"new_page": "wiki/developments/new.md", "type": "development"}, pointer="", pointer_why="none is needed", reason="r"),
    dict(common, row="U-3", s=[0, 0], action="reword", new="Proposed new words.", diffs=[], proposal=True, disagree="stale", reason="r"),
    dict(common, row="U-4", s=[0, 0], action="reword", new="**Seam (owner, 6 June 2026)**: approved words with a seam there.", diffs=[], seam=True, reason="r"),
    dict(common, row="U-5", s=[0, 0], action="merge", merge_id="M1", reason="r"),
    dict(common, row="U-6", s=[0, 0], action="merge", merge_id="M1", reason="r"),
    dict(common, merge_id="M1", new="One merged clause.", sources=[{"row": "U-5", "s": [0, 0]}, {"row": "U-6", "s": [0, 0]}], diffs={}, to={"file": "CLAUDE.md", "after": "Anchor words."}, pointer="See CLAUDE.md.", reason="r"),
    dict(common, row="U-7", s=[0, 0], action="reword", new="Plain words after their reword.", diffs=[], reason="r"),
    dict(common, row="U-8", s=[0, 0], action="move", to={"data": ".claude/skills/delegate/routing.json", "entry": "a row"}, pointer="", pointer_why="none", reason="r"),
    dict(common, row="U-10", s=[0, 0], action="merge", merge_id="M2", reason="r"),
    dict(common, merge_id="M2", new="A merge that stays a proposal.", sources=[{"row": "U-10", "s": [0, 0]}], diffs={}, proposal=True, to={"file": "CLAUDE.md", "section": "x"}, reason="r"),
    dict(common, row="W-1", s=[0, 0], action="file", to={"file": "CLAUDE.md", "section": "## Rules"}, reason="r"),
    dict(common, row="W-2", s=[0, 0], action="file", to={"file": "CLAUDE.md", "section": "## Rules"}, reason="r"),
    dict(common, row="X-NEW-1", file="wiki/y.md", old="A designer's own rule here.", s=[0, 0], action="keep"),
    dict(common, row="X-BC-1.1", s=[0, 0], action="keep"),
]
tracing = [
    {"row": "U-2", "sentence": 0, "status": "approved-record", "record": "a dated yes", "file": "history", "locator": "L1", "quote": "yes"},
    {"row": "U-2", "sentence": 2, "status": "approved-untraced"},
    {"row": "U-3", "sentence": 0, "status": "approved-record", "record": "a dated yes"},
    {"row": "U-4", "sentence": 0, "status": "approved-record", "record": "a dated yes"},
]
for name, data in (("rules", rules), ("map", lines), ("tracing", tracing)):
    with open("%s/%s.jsonl" % (out, name), "w", encoding="utf-8") as stream:
        for item in data:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")
PY
}

seed_fixture; run seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" --today 2020-01-01
expect "seed prints its summary and names what it could not place, its exit clean with no anomaly" 0 "+seed: 13 rows" "+1 spans retired" "+unplaced: U-9" "+0 anomalies"
python3 -B "$TOOL" seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" --today 2020-01-01 >"$SEED/doc.json" 2>/dev/null
seed_check() {
  python3 -B - "$SEED/doc.json" "$1" >"$OUT" 2>&1 <<'PY'
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
rows = {row["id"]: row for row in doc["rows"]}
try:
    ok = eval(sys.argv[2])
except Exception as error:
    print("error", repr(error)); sys.exit(1)
if not ok:
    print(json.dumps(rows, indent=0)[:1200])
sys.exit(0 if ok else 1)
PY
  rc=$?
}
seed_check 'doc["trial"] is True and doc["schema_version"] == 1'; expect "seed: the trial state starts on" 0
seed_check 'rows["U-1#0-0"]["home"] == {"file": "CUSTOMISATION.md", "section": "Alpha"} and rows["U-1#0-0"]["text"] == "- First kept sentence."'; expect "seed: a keep stays at its home, cut by its sentence offsets" 0
seed_check 'rows["U-1#1-1"]["home"] == {"file": "wiki/developments/routing-table.md", "section": "The table"} and rows["U-1#1-1"]["from"]["file"] == "CUSTOMISATION.md" and rows["U-1#1-1"]["text"] == "Second moved sentence." and rows["U-1#1-1"]["pointers"] == [{"file": "CUSTOMISATION.md", "text": "See the routing table."}] and rows["U-1#1-1"]["failure"] == "a stale route"'; expect "seed: a move names its new home, its source and its pointer" 0
seed_check '"U-1#2-2" not in rows'; expect "seed: a retired span has no row" 0
seed_check 'rows["U-2#0-0"]["wording"] == "approved-record" and rows["U-2#0-0"]["approved"][0]["text"] == "- **Lead (owner, 2 March 2026)**: an approved first sentence." and rows["U-2#0-0"]["approved"][0]["record"]["locator"] == "L1"'; expect "seed: a traced sentence is approved with its record" 0
seed_check 'rows["U-2#1-2"]["wording"] == "approved-untraced" and rows["U-2#1-2"]["approved"] == [] and rows["U-2#1-2"]["home"]["file"] == "wiki/developments/new.md"'; expect "seed: an untraced mark stays untraced and is not checked word for word; a new page is a home" 0
seed_check 'rows["U-3#0-0"]["home"]["file"] == "CUSTOMISATION.md" and rows["U-3#0-0"]["text"].endswith("would reword.") and "Proposed" not in json.dumps(rows["U-3#0-0"]) and rows["U-3#0-0"]["proposal"] is True and rows["U-3#0-0"]["disagree"] == "stale" and rows["U-3#0-0"]["approved"]'; expect "seed: a proposed reword of approved text leaves its words and its home" 0
seed_check 'rows["U-4#0-0"]["text"].endswith("a seam there.") and rows["U-4#0-0"]["approved"][0]["text"].endswith("a seam there.") and rows["U-4#0-0"]["approved"][0]["seam"] is True'; expect "seed: a seam's approved wording is the seamed text" 0
seed_check 'rows["M1"]["text"] == "One merged clause." and rows["M1"]["home"]["file"] == "CLAUDE.md" and rows["M1"]["merged_from"] == ["U-5", "U-6"] and "U-5#0-0" not in rows and "U-6#0-0" not in rows'; expect "seed: a merge is one row at its receiving home" 0
seed_check '"M2" not in rows and "U-10#0-0" in rows and rows["U-10#0-0"]["text"] == "An owner clause for a proposed merge."'; expect "seed: a merge that stays a proposal leaves its source" 0
seed_check 'rows["U-7#0-0"]["text"] == "Plain words after their reword." and rows["U-7#0-0"]["wording"] == "agent"'; expect "seed: a reword of the agent's words takes the new text" 0
seed_check 'rows["U-8#0-0"]["check"] == "reading-only" and rows["U-8#0-0"]["home"] == {"file": ".claude/skills/delegate/routing.json", "entry": "a row"}'; expect "seed: a clause moved into data is marked for reading only" 0
seed_check 'rows["W-1#0-0"]["wording"] == "approved-record" and rows["W-1#0-0"]["approved"][0]["text"] == "A waiting text with its approval." and rows["W-2#0-0"]["wording"] == "agent" and rows["W-1#0-0"]["home"]["section"] == "Rules"'; expect "seed: a filed text keeps its status and takes its home" 0
seed_check 'rows["X-NEW-1#0-0"]["home"]["file"] == "wiki/y.md" and rows["X-NEW-1#0-0"]["text"] == "A designer'"'"'s own rule here."'; expect "seed: a designer's own row is taken from its old text" 0
seed_check '"X-BC-1.1#0-0" not in rows'; expect "seed: a gone row is not placed" 0
seed_check 'all(len(r["text_sha256"]) == 64 for r in rows.values())'; expect "seed: every row keeps its text's fingerprint, for a core file's check" 0

python3 -B - "$SEED/rules.jsonl" <<'PY'
import json, sys
rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
for row in rows:
    if row["id"] == "U-1":
        row["sentences"] = list([start, end - 1] for start, end in row["sentences"])
open(sys.argv[1], "w", encoding="utf-8").write("".join(json.dumps(r) + "\n" for r in rows))
PY
python3 -B "$TOOL" seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" >"$SEED/doc.json" 2>/dev/null
seed_check 'rows["U-1#1-1"]["text"] == "Second moved sentence."'; expect "seed: offsets that end inclusively cut the same text" 0

seed_fixture; rm "$SEED/tracing.jsonl"; run seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl"
expect "seed with its tracing missing: a broken premise, no document" 2 "+PROBE FAILED: seed input is missing" "-schema_version"

seed_fixture; : >"$SEED/map.jsonl"; run seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl"
expect "seed with an empty map: a broken premise" 2 "+PROBE FAILED: the rule list or the map holds no rows"

seed_fixture; manifest_before="$(ls -A "$SEED" | tr '\n' ' ')"; rm -rf "$WORK/cwd"; mkdir -p "$WORK/cwd"
(cd "$WORK/cwd" && python3 -B "$TOOL" seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" >"$OUT" 2>&1)
[ "$(ls -A "$SEED" | tr '\n' ' ')" = "$manifest_before" ] && [ -z "$(ls -A "$WORK/cwd")" ]; rc=$?; expect "seed with no --out writes nothing, in its inputs' folder or the working folder" 0
run seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" --out "$SEED/out.json"
expect "seed --out writes a new data file" 0 "+seed: wrote"
[ -s "$SEED/out.json" ]; rc=$?; expect "its file exists" 0
stat -f %Lp "$SEED/out.json" 2>/dev/null >"$OUT" || stat -c %a "$SEED/out.json" >"$OUT"; rc=0; expect "the data file holds the owner's wordings, so it is private" 0 "+600"
run seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" --out "$SEED/out.json"
expect "seed --out refuses a path that exists" 2 "+PROBE FAILED: " "+already exists"

seed_fixture; python3 -B - "$SEED" <<'PY'
import json, sys
lines = [json.loads(line) for line in open(sys.argv[1] + "/map.jsonl", encoding="utf-8")]
open(sys.argv[1] + "/map-a.jsonl", "w", encoding="utf-8").write("".join(json.dumps(line) + "\n" for line in lines[:4]))
open(sys.argv[1] + "/map-b.jsonl", "w", encoding="utf-8").write("".join(json.dumps(line) + "\n" for line in lines[4:]))
PY
python3 -B "$TOOL" seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" >"$SEED/whole.json" 2>/dev/null
python3 -B "$TOOL" seed --map "$SEED/map-a.jsonl,$SEED/map-b.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" >"$SEED/commas.json" 2>/dev/null
python3 -B "$TOOL" seed --map "$SEED/map-a.jsonl" "$SEED/map-b.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" >"$SEED/spaces.json" 2>/dev/null
[ -s "$SEED/whole.json" ] && cmp -s "$SEED/whole.json" "$SEED/commas.json" && cmp -s "$SEED/whole.json" "$SEED/spaces.json"; rc=$?; expect "seed --map takes its files joined by commas or by spaces, the same rows from each" 0

seed_fixture; printf '{"row": "U-9", "s": [0, 0], "action": "move", "to": {"section": "## Nowhere"}, "reason": "r", "whose": "product", "layer": "core", "shape": "guided", "moment": "always-on"}\n' >>"$SEED/map.jsonl"
run seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl"
expect "a move with no receiving file is said, its row stays at its source, and an anomaly left is no clean exit" 1 "+U-9: a move with no receiving file, kept at its source" '+"id": "U-9#0-0"' "-unplaced: U-9" "+1 anomalies"

seed_fixture; printf '{"row": "U-99", "s": [0, 0], "action": "keep", "whose": "product", "layer": "core", "shape": "guided", "moment": "always-on"}\n' >>"$SEED/map.jsonl"
run seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" --out "$SEED/anomalous.json"
expect "a map row the list does not hold: said, the document still written, and no clean exit" 1 "+U-99: the map names a row the list does not hold" "+seed: wrote"

# A skill's steps, listed by section: a row names the place and holds no text.
fresh; seed_fixture
cat >"$V/.claude/skills/fix/SKILL.md" <<'EOF'
# Skill
## First step
Words.
```
## not a heading, inside a fence
```
### A deeper heading
## Second step
Words (owner, 1 June 2020).
EOF
rm "$DOC"; run seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" --skill-sections --vault "$V" --out "$DOC"
expect "seed --skill-sections adds a row per level-two section, none from a fence" 0 "+seed: 15 rows from 18 map lines and 2 skill sections"
python3 -B "$TOOL" seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" --skill-sections --vault "$V" >"$SEED/doc.json" 2>/dev/null
seed_check 'rows[".claude/skills/fix/SKILL.md § First step"]["home"] == {"file": ".claude/skills/fix/SKILL.md", "section": "First step"} and rows[".claude/skills/fix/SKILL.md § Second step"]["moment"] == "skill-step" and rows[".claude/skills/fix/SKILL.md § First step"]["text"] == "" and sum(1 for r in rows.values() if r.get("section_row")) == 2'; expect "seed: a section row names the file and section and holds no text" 0
run seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" --today 2020-01-01 --vault "$V"
expect "with no flag, seed takes no sections" 0 "+and 0 skill sections"
fresh; rm -rf "$V/.claude/skills"; run seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" --skill-sections --vault "$V"
expect "--skill-sections finding no section: a broken premise" 2 "+PROBE FAILED: --skill-sections found no section"
fresh; printf '# Skill\n## First step\n## Second step\nWords (owner, 1 June 2020) and more (owner, 2 June 2021).\n' >"$V/.claude/skills/fix/SKILL.md"; edit_data 'rows.extend({"id": ".claude/skills/fix/SKILL.md § %s" % name, "map_row": None, "home": {"file": ".claude/skills/fix/SKILL.md", "section": name}, "section_row": True, "text": "", "wording": "agent", "approved": []} for name in ("First step", "Second step"))'
run record-audit --vault "$V" --today 2020-07-01
grep -q 'fix/SKILL.md.*[0-9a-f]\{64\}' "$DOC"; rc=$?; expect "a section row does not make its skill a rule-holding page" 1
run weekly --vault "$V"
expect "a section row that stands is compared, found and lists nothing, and adds no dated ruling" 0 "+has left its home: 0 (control: 8 of 8 compared rows" "-LEFT " "+(control: 2 dated rulings read in 2 homes"
replace "$V/.claude/skills/fix/SKILL.md" "## First step" "## The first step"; run weekly --vault "$V"
expect "a section renamed or gone is listed, its text never looked for" 0 "+has left its home: 1" "+LEFT .claude/skills/fix/SKILL.md § First step · its section has left .claude/skills/fix/SKILL.md"
run generate --vault "$V"; cp "$V/wiki/developments/rule-register.md" "$OUT"; expect "a section row shows on the page, with no text" 0 "+| .claude/skills/fix/SKILL.md § Second step | Second step | - |" "+**A skill section's row.**"

# A known edit: the reword installs a waiting text, so its words and its approval are the W row's.
known_fixture() {
  SEED="$WORK/seed"; rm -rf "$SEED"; mkdir -p "$SEED"
  python3 -B - "$SEED" <<'PY'
import json, sys
out = sys.argv[1]
AGENT_STATUS = "ai" + "myth"   # the rule list's value, joined here since the agent's name never ships in a file
NOTE = "settled by the reviews, not approved word for word"
RECORD = {"file": "decisions", "line": 8, "quote": "yes"}
def rule(rid, parts, heading="# T > ## Alpha", file="CUSTOMISATION.md", **more):
    text = "".join(parts)
    spans, at = [], 0
    for part in parts:
        spans.append([at, at + len(part)])
        at += len(part)
    base = {"id": rid, "kind": "rule", "file": file, "heading_path": heading, "text": text, "sentences": spans, "marks": [], "wording": AGENT_STATUS}
    base.update(more)
    return base
def waiting(rid, text, **more):
    base = {"id": rid, "kind": "rule", "form": "waiting", "file": None, "known_edit": False, "text": text, "sentences": [[0, len(text)]], "wording": AGENT_STATUS, "marks": [], "status": "located"}
    base.update(more)
    return base
rules = [
    rule("U-20", ["- **Old lead (owner, 1 May 2026)**: the old approved words stand here. "], marks=[0], wording="marked"),
    rule("U-21", ["The old marked words of a closing order. "], marks=[0], wording="marked"),
    rule("U-22", ["Agent words a settled text replaces. "]),
    rule("U-23", ["Agent words a settled agent text replaces. "]),
    rule("U-27", ["A retired row whole. "]),
    rule("U-28", ["Half of it retires. ", "Half of it stays. "]),
    waiting("W-20", "**New lead (owner, 2 June 2026)**: the approved known edit", wording="approved-record", record=RECORD),
    waiting("W-21", "the settled closing order, marked (owner, 3 November 2026).", known_edit=True, approval_note=NOTE),
    waiting("W-22", "The approved words a row of the agent's takes.", wording="approved-record", record=RECORD),
    waiting("W-23", "The settled words in the agent's own wording.", known_edit=True),
    waiting("W-24", "The approved words a designer's row takes.", wording="approved-record", record=RECORD),
    waiting("W-25", "A text a part stages for itself.", placed_by="part known", home_file="wiki/developments/staged.md"),
    waiting("W-26", "An approved text a part stages.", wording="approved-record", record=RECORD, home_file="wiki/developments/staged.md"),
    waiting("W-27", "A text not installed, held as a proposal.", home_file="CUSTOMISATION.md"),
    waiting("W-29", "", status="not-found", home_file="CUSTOMISATION.md", sentences=[]),
    waiting("W-31", "Approved words dated <install date> here.", wording="approved-record", record=RECORD),
    waiting("W-32", "The approved words a merge carries.", wording="approved-record", record=RECORD),
    waiting("W-33", "Words a reword carries by its link alone.", home_file="CUSTOMISATION.md"),
    rule("U-30", ["A clause for the carrying merge. "]),
    rule("U-31", ["Another clause for it. "]),
    rule("U-32", ["A clause the linked reword replaces. "]),
    {"id": "X-30", "part": "out-of-home", "kind": "rule", "file": "wiki/developments/known-issues.md", "heading_path": None, "text": "- **Symptom**: the owner said: keep it short.\n", "sentences": [[0, 46]], "marks": [0], "wording": "marked"},
    {"id": "X-31", "part": "out-of-home", "kind": "rule", "file": "wiki/developments/known-issues.md", "heading_path": None, "text": "- **Fix**: words with no record of approval.\n", "sentences": [[0, 45]], "marks": [], "wording": AGENT_STATUS},
]
common = {"principle": "2", "whose": "owner", "layer": "user", "shape": "guided", "moment": "always-on", "reason": "r"}
lines = [
    dict(common, row="U-20", s=[0, 0], action="reword", new="- **New lead (owner, 2 June 2026)**: the approved known edit, and the words of its source.\n", known_edit="W-20", group_with=["W-20"], diffs=[]),
    dict(common, row="W-20", s=[0, 0], action="keep"),
    dict(common, row="U-21", s=[0, 0], action="reword", new="the settled closing order, marked (owner, 3 November 2026). ", known_edit="W-21", group_with=["W-21"], diffs=[]),
    dict(common, row="W-21", s=[0, 0], action="keep"),
    dict(common, row="U-22", s=[0, 0], action="reword", new="The approved words a row of the agent's takes.", known_edit="W-22", diffs=[]),
    dict(common, row="W-22", s=[0, 0], action="keep"),
    dict(common, row="U-23", s=[0, 0], action="reword", new="The settled words in the agent's own wording.", known_edit="W-23", diffs=[]),
    dict(common, row="W-23", s=[0, 0], action="keep"),
    dict(common, row="X-NEW-2", file="wiki/developments/lifecycle.md", old="An old line of a page.", action="reword", new="The approved words a designer's row takes.", known_edit="W-24", diffs=[]),
    dict(common, row="W-24", s=[0, 0], action="keep"),
    dict(common, row="W-25", s=[0, 0], action="keep"),
    dict(common, row="W-26", s=[0, 0], action="keep", proposal=True),
    dict(common, row="W-27", s=[0, 0], action="file", to={"file": "CUSTOMISATION.md", "section": "## Alpha"}, proposal=True),
    dict(common, row="W-29", action="file", to={"file": "CUSTOMISATION.md", "section": "## Alpha"}, new="- The map's own words for a text with none."),
    dict(common, row="W-31", s=[0, 0], action="file", to={"file": "CUSTOMISATION.md", "section": "## Alpha"}, new="Approved words dated 4 November 2026 here."),
    dict(common, row="U-27", s=[0, 0], action="retire", ended_by="a later ruling"),
    dict(common, row="U-28", s=[0, 0], action="retire", ended_by="a later ruling"),
    dict(common, row="U-28", s=[1, 1], action="keep"),
    dict(common, row="U-30", s=[0, 0], action="merge", merge_id="M3"),
    dict(common, row="U-31", s=[0, 0], action="merge", merge_id="M3"),
    dict(common, merge_id="M3", new="One clause. The approved words a merge carries.", sources=[{"row": "U-30", "s": [0, 0]}, {"row": "U-31", "s": [0, 0]}], group_with=["W-32"], diffs={}, to={"file": "CLAUDE.md", "section": "## Reading"}),
    dict(common, row="W-32", s=[0, 0], action="keep"),
    dict(common, row="U-32", s=[0, 0], action="reword", new="The words the linked reword puts in.", group_with=["W-33"], diffs=[]),
    dict(common, row="W-33", s=[0, 0], action="keep"),
    dict(common, row="X-30", s=[0, 0], action="keep"),
    dict(common, row="X-31", s=[0, 0], action="keep"),
]
tracing = [
    {"row": "U-20", "sentence": 0, "status": "approved-record", "record": "the old yes", "quote": "old"},
    {"row": "U-21", "sentence": 0, "status": "approved-untraced"},
    {"row": "X-30", "sentence": 0, "status": "approved-record", "record": "a dated yes", "quote": "keep it short"},
]
for name, data in (("rules", rules), ("map", lines), ("tracing", tracing)):
    with open("%s/%s.jsonl" % (out, name), "w", encoding="utf-8") as stream:
        for item in data:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")
PY
}
known_fixture; run seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" --today 2020-01-01
expect "known edits, carried texts and a dated home leave no anomaly, with the counts to show it" 0 "+0 anomalies" "+1 listed, not checked" "+7 waiting texts carried by another row" "+1 waiting texts proposed and not placed" "+proposed, no row until each has a home: W-27"
python3 -B "$TOOL" seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" --today 2020-01-01 >"$SEED/doc.json" 2>/dev/null
seed_check 'rows["U-20#0-0"]["wording"] == "approved-record" and rows["U-20#0-0"]["text"] == "- **New lead (owner, 2 June 2026)**: the approved known edit, and the words of its source." and [a["text"] for a in rows["U-20#0-0"]["approved"]] == ["**New lead (owner, 2 June 2026)**: the approved known edit"] and rows["U-20#0-0"]["approved"][0]["record"]["quote"] == "yes" and rows["U-20#0-0"]["known_edit"] == "W-20"'; expect "seed: an approved known edit takes its wording and record from its W row, and the row's text is the new text" 0
seed_check 'rows["U-20#0-0"]["home"] == {"file": "CUSTOMISATION.md", "section": "Alpha"} and "the old yes" not in json.dumps(rows["U-20#0-0"])'; expect "seed: it stays in its row's home, and the old words' record does not pass to the new words" 0
seed_check 'rows["U-21#0-0"]["wording"] == "approved-untraced" and rows["U-21#0-0"]["approved"] == [] and rows["U-21#0-0"]["text"].startswith("the settled closing") and "not approved word for word" in rows["U-21#0-0"]["wording_note"]'; expect "seed: a known edit its W row does not approve word for word is checked by nothing, its marked words stay marked, and the note says why" 0
seed_check 'rows["U-22#0-0"]["wording"] == "approved-record" and rows["U-22#0-0"]["approved"][0]["text"] == "The approved words a row of the agent'"'"'s takes."'; expect "seed: an approved known edit on a row of the agent's words is checked all the same" 0
seed_check 'rows["U-23#0-0"]["wording"] == "agent" and rows["U-23#0-0"]["approved"] == []'; expect "seed: a known edit in the agent's wording on the agent's row stays the agent's" 0
seed_check 'rows["X-NEW-2#0-0"]["wording"] == "approved-record" and rows["X-NEW-2#0-0"]["home"]["file"] == "wiki/developments/lifecycle.md" and rows["X-NEW-2#0-0"]["approved"][0]["known_edit"] == "W-24"'; expect "seed: a designer's own row takes an approved known edit too" 0
seed_check 'not any(rows.get(name + "#0-0") for name in ("W-20", "W-21", "W-22", "W-23", "W-24", "W-32", "W-33"))'; expect "seed: a carried waiting text has no row of its own, so no row is left with no home" 0
seed_check 'rows["U-20#0-0"]["carries"] == ["W-20"] and rows["M3"]["carries"] == ["W-32"] and rows["U-32#0-0"]["carries"] == ["W-33"]'; expect "seed: the row that carries a waiting text says so, so a LIST may name it by that text" 0
seed_check 'rows["M3"]["wording"] == "approved-record" and rows["M3"]["approved"][0]["text"] == "The approved words a merge carries."'; expect "seed: a merge carrying an approved text whole checks it" 0
seed_check 'rows["U-32#0-0"]["approved"] == [] and rows["U-32#0-0"]["wording"] == "agent"'; expect "seed: a link alone, its words not held whole, approves nothing" 0
seed_check 'rows["W-25#0-0"]["home"]["file"] == "wiki/developments/staged.md" and rows["W-25#0-0"]["wording"] == "agent" and rows["W-26#0-0"]["home"]["file"] == "wiki/developments/staged.md" and rows["W-26#0-0"]["approved"][0]["text"] == "An approved text a part stages."'; expect "seed: a waiting text a part stages stays at the home its row states, checked if approved" 0
seed_check '"W-27#0-0" not in rows'; expect "seed: a waiting text only proposed has no home yet, so no row" 0
seed_check 'rows["W-29#0-0"]["text"] == "- The map'"'"'s own words for a text with none." and rows["W-29#0-0"]["home"]["section"] == "Alpha" and rows["W-29#0-0"]["wording"] == "agent"'; expect "seed: a file span with its own words gives its row those words, though the list found no text" 0
seed_check 'rows["W-31#0-0"]["text"] == "Approved words dated 4 November 2026 here." and rows["W-31#0-0"]["approved"][0]["text"] == "Approved words dated 4 November 2026 here."'; expect "seed: a filed text with its placeholder filled is checked as it installs" 0
seed_check 'all((r.get("home") or {}).get("file") for r in rows.values())'; expect "seed: every row names a home" 0
seed_check 'rows["X-30#0-0"]["wording"] == "listed, not checked" and rows["X-30#0-0"]["approved"] == [] and rows["X-30#0-0"]["listed"][0]["text"].endswith("keep it short.") and "known-issues.md, is a dated record" in rows["X-30#0-0"]["wording_reason"]'; expect "seed: approved words in a dated record are listed, not checked, with the reason, and kept on the row" 0
seed_check 'rows["X-31#0-0"]["wording"] == "agent" and "wording_reason" not in rows["X-31#0-0"]'; expect "seed: control: a row with no approved words in the same dated record is untouched" 0
seed_check 'doc["retired_rows"] == ["U-27"]'; expect "seed: a row whose every span retired is named; one with a span left is not" 0
seed_check '"U-27#0-0" not in rows and rows["U-28#1-1"]["text"] == "Half of it stays."'; expect "seed: the retired spans have no row, and the kept span does" 0

known_fixture; printf '{"row": "U-32", "s": [0, 0], "action": "reword", "new": "Words that only link to it.", "group_with": ["W-22"], "diffs": [], "whose": "product", "layer": "core", "shape": "guided", "moment": "always-on"}\n{"row": "W-22", "s": [0, 0], "action": "keep", "whose": "owner", "layer": "user", "shape": "guided", "moment": "always-on"}\n' >"$SEED/map.jsonl"
run seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl"
expect "an approved text only linked to, held whole by no row, would go unchecked: an anomaly" 1 "+W-22: approved, and no row that carries it holds it word for word, so nothing would check it"

# Round trip, on the check: a known edit's approved words are compared, not the old words.
fresh; known_fixture; rm "$DOC"; python3 -B "$TOOL" seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" --out "$DOC" >/dev/null 2>&1
edit_data 'data["trial"] = False'
cat >"$V/CUSTOMISATION.md" <<EOF
$MARKER_LINE

## Alpha
- **Old lead (owner, 1 May 2026)**: the old approved words stand here.
EOF
run wording-check --vault "$V" --installed-only "U-20"
expect "before it installs, with the old words in its home, the known edit is a miss, so a failed install is seen" 1 "+BLOCKED: U-20#0-0" "+stored: **New lead (owner, 2 June 2026)**: the approved known edit"
replace "$V/CUSTOMISATION.md" "- **Old lead (owner, 1 May 2026)**: the old approved words stand here." "- **New lead (owner, 2 June 2026)**: the approved known edit, and the words of its source."
run wording-check --vault "$V" --installed-only "W-20"
expect "once installed it stands in its home, the list naming it by its W row" 0 "+holding 1 approved wordings: 0 of them missed" "+nothing fails the install"
run wording-check --vault "$V" --installed-only "U-27,X-30"
expect "a LIST naming a retired row and a row in a dated record fails no install" 0 "+2 listed as just placed, holding 0 approved wordings: 0 of them missed, 0 refused; 1 rows listed, not checked" "+nothing fails the install"

# The anomalies still stand: each planted, each said, each no clean exit.
known_fixture; printf '{"row": "U-21", "s": [0, 0], "action": "reword", "new": "Words with no mark at all.", "diffs": [], "whose": "owner", "layer": "user", "shape": "guided", "moment": "always-on"}\n' >"$SEED/map.jsonl"
run seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl"
expect "a reword of owner-marked text with no proposal, seam or known edit: an anomaly, its row kept at its source" 1 "+U-21: a reword of owner-marked text with no proposal or seam mark, kept at its source" "+1 anomalies" "+The old marked words of a closing order."
known_fixture; printf '{"row": "U-21", "s": [0, 0], "action": "reword", "new": "Words.", "known_edit": "W-404", "diffs": [], "whose": "owner", "layer": "user", "shape": "guided", "moment": "always-on"}\n' >"$SEED/map.jsonl"
run seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl"
expect "a known edit naming no waiting text: an anomaly" 1 "+U-21: its known edit W-404 is no waiting text in the list, kept at its source"
known_fixture; printf '{"row": "U-21", "s": [0, 0], "action": "reword", "new": "Words that leave out what it installs.", "known_edit": "W-21", "diffs": [], "whose": "owner", "layer": "user", "shape": "guided", "moment": "always-on"}\n' >"$SEED/map.jsonl"
run seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl"
expect "a known edit whose new text does not hold its W row word for word: an anomaly" 1 "+U-21: its new text does not hold its known edit W-21 word for word, kept at its source"
known_fixture; printf '{"row": "W-27", "s": [0, 0], "action": "keep", "whose": "owner", "layer": "user", "shape": "guided", "moment": "always-on"}\n' >"$SEED/map.jsonl"
python3 -B - "$SEED/rules.jsonl" <<'PY'
import json, sys
rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
for row in rows:
    if row["id"] == "W-27":
        del row["home_file"]
open(sys.argv[1], "w", encoding="utf-8").write("".join(json.dumps(r) + "\n" for r in rows))
PY
run seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl"
expect "a waiting text kept with no home and nothing carrying it: an anomaly, and no row" 1 "+W-27: kept with no home to stay in and nothing carrying it" '-"id": "W-27#0-0"'

# Round trip: the seeded rows, read back by the pass against homes that hold them.
fresh; seed_fixture
cat >"$V/CUSTOMISATION.md" <<EOF
$MARKER_LINE

## Alpha
- First kept sentence. See the routing table.

## Beta
- **Lead (owner, 2 March 2026)**: an approved first sentence.
EOF
rm "$DOC"; python3 -B "$TOOL" seed --map "$SEED/map.jsonl" --rules "$SEED/rules.jsonl" --tracing "$SEED/tracing.jsonl" --out "$DOC" >/dev/null 2>&1
run wording-check --vault "$V"
expect "round trip: a seeded wording found in its home; others listed as misses" 0 "+CONTROL:" "+MISS U-3#0-0" "+MISS U-4#0-0" "+MISS W-1#0-0" "-MISS U-2#0-0"

# ---- generate ---------------------------------------------------------------------------------------
fresh; edit_data 'data["rows"] = []'; run generate --vault "$V" --today 2020-02-02
PAGE="$V/wiki/developments/rule-register.md"
expect "generate from an empty data file writes the page" 0 "+generate: wrote"
cp "$PAGE" "$OUT"; expect "the empty page carries the schema's frontmatter, its sections and a wikilink" 0 '+title: "Rule register"' "+type: development" "+confidence: medium" "+audited: 2020-01-01" "+created: 2020-01-01" "+updated: 2020-02-02" "+## Sources Used" "+## Related" "+[[check-lifecycle]]" "+No rows yet." "+0 rows" "+**When a rule changes.**" "+trial state"

fresh; run generate --vault "$V" --today 2020-02-02; cp "$PAGE" "$WORK/page1"; run generate --vault "$V" --today 2020-02-02; cmp -s "$PAGE" "$WORK/page1"; rc=$?; expect "generate is deterministic" 0
cp "$PAGE" "$OUT"; expect "the page lists each row with the plan's columns, its files by layer and counts" 0 "+| R1#0-0 | Settings | always-on | owner | user | fixed | a cold kettle |" "+### CUSTOMISATION.md" "+### wiki/developments/fixture-rules.md" "+| CUSTOMISATION.md | 2 | 2 | 0 |" "+6 rows: 2 approved with a record"

fresh; edit_data 'by["R3#0-0"]["text"] = "A pipe | and a [[wikilink]] in the text."'; run generate --vault "$V"; cp "$PAGE" "$OUT"; expect "a row's text cannot break the table or plant a link" 0 '+A pipe \| and a [wikilink] in the text.' "-[[wikilink]]"

fresh; run generate --vault "$V"; run weekly --vault "$V"; expect "the page in step with its data" 0 "+PAGE · in step with its data"
edit_data 'by["R3#0-0"]["layer"] = "user"'; run weekly --vault "$V"; expect "the page out of step is said" 0 "+PAGE · out of step"
fresh; run weekly --vault "$V"; expect "the page absent is said" 0 "+PAGE · absent"

fresh; rm "$DOC"; run generate --vault "$V"; expect "generate with no data writes no page" 0 "+not applicable"
[ ! -e "$PAGE" ]; rc=$?; expect "and no page exists" 0
fresh; printf '{torn' >"$DOC"; run generate --vault "$V"; expect "generate on a torn data file: a broken premise, no page" 2 "+PROBE FAILED"
[ ! -e "$PAGE" ]; rc=$?; expect "and no page exists after it" 0

fresh; run record-audit --vault "$V"; cp "$DOC" "$WORK/doc1"; run generate --vault "$V"; cmp -s "$DOC" "$WORK/doc1"; rc=$?; expect "generate leaves the data as it was" 0
fresh; run generate --vault "$V"; cp "$PAGE" "$WORK/p"; run record-audit --vault "$V"; run weekly --vault "$V"; expect "a recorded audit leaves the page in step: rows alone are its digest" 0 "+PAGE · in step"
fresh; run generate --vault "$V"; run record-audit --vault "$V" --today 2020-07-01; run record-audit --vault "$V" --today 2020-07-02; run weekly --vault "$V"
expect "the data file the page names is no changed source, though every audit changes it" 0 "+cited or named files changed since the audit of 2020-07-02: 0," "-rule-register-data.json ←"
grep -F 'rule-register-data.json' "$PAGE" >"$OUT"; rc=$?; expect "control: the page does name its data file" 0 "+rule-register-data.json"
fresh; replace "$V/wiki/developments/fixture-rules.md" "sources: [raw/one.md," "sources: [wiki/developments/rule-register-data.json, raw/one.md,"; run record-audit --vault "$V" --today 2020-07-01; run record-audit --vault "$V" --today 2020-07-02; run weekly --vault "$V"
expect "the data file a page cites in its frontmatter is no changed source either" 0 "+cited or named files changed since the audit of 2020-07-02: 0," "-rule-register-data.json ←"
python3 -B - "$DOC" >"$OUT" 2>&1 <<'PY'
import json, sys
sources = json.load(open(sys.argv[1], encoding="utf-8"))["audit"]["sources"]
print(sorted(sources))
sys.exit(0 if "wiki/developments/rule-register-data.json" not in sources and "raw/one.md" in sources else 1)
PY
rc=$?; expect "it is not fingerprinted, and the unrelated source beside it still is" 0 "+raw/one.md"
fresh; edit_data 'by["R3#0-0"]["text"] = "Words (owner, 7 May 2020) in a row."'; replace "$V/CUSTOMISATION.md" "- $GATE" "- Words (owner, 7 May 2020) in a row."; run generate --vault "$V"; run in-place --vault "$V"
expect "the register's own page is no rule-holding page, though it repeats a ruling" 0 "-CANDIDATE wiki/developments/rule-register.md"
grep -F '(owner, 7 May 2020)' "$PAGE" >"$OUT"; rc=$?; expect "control: the page does repeat it" 0 "+Words (owner, 7 May 2020)"
fresh; rm "$DOC"; run record-audit --vault "$V"; expect "record-audit with no data: not applicable" 0 "+not applicable"
[ ! -e "$DOC" ]; rc=$?; expect "and it creates none" 0
fresh; chmod 600 "$DOC"; run record-audit --vault "$V"; stat -f %Lp "$DOC" 2>/dev/null >"$OUT" || stat -c %a "$DOC" >"$OUT"; rc=0; expect "record-audit keeps the data's mode" 0 "+600"

# ---- rules already in place -------------------------------------------------------------------------
fresh; printf '%s\n' '- Keep the ladder dry (owner ruling, 8 August 2020).' >>"$V/output/README.md"; run in-place --vault "$V"
expect "in-place lists a dated rule on a README, and leaves a row's text alone" 0 "+CANDIDATE output/README.md:" "+· dated · - Keep the ladder dry" "-Fixture pages keep one rule" "+1 dated,"

fresh; printf '%s\n' '- Keep the ladder dry.' '- Keep the shed locked (owner ruling, 8 August 2020).' >>"$V/output/README.md"; run in-place --vault "$V"
expect "an undated rule on a README is listed beside the dated one" 0 "+· plain · - Keep the ladder dry." "+· dated · - Keep the shed locked" "+1 dated,"

fresh; printf -- '---\ntitle: "Unmarked"\ntype: development\n---\nClose the gate at dusk.\n\nNo session may never skip the bolt.\n' >"$V/wiki/developments/unmarked.md"; run in-place --vault "$V"
expect "a framework page with no date mark, no row and nothing naming it comes into the inventory, its rules listed" 0 "+CANDIDATE wiki/developments/unmarked.md:" "+· plain · Close the gate at dusk." "+· rule word · No session may never skip the bolt." "+in the framework's folders"

fresh; printf -- '---\ntitle: "Pointed"\n---\nWipe the bench each night.\n' >"$V/wiki/sources/pointed.md"; printf -- '---\ntitle: "Linked"\n---\nOil the hinge each spring.\n' >"$V/wiki/sources/linked.md"; printf 'See `wiki/sources/pointed.md` at this step, and %slinked]].\n' '[[' >>"$V/.claude/skills/fix/SKILL.md"; run in-place --vault "$V"
expect "a page outside those folders that a forward-facing file names, by path or by link, comes in too" 0 "+· plain · Wipe the bench each night." "+· plain · Oil the hinge each spring." "+2 named by a forward-facing file"

fresh; printf -- '---\ntitle: "Other"\n---\nThe paper says that a model must never overfit.\n' >"$V/wiki/sources/other.md"; run in-place --vault "$V"
expect "a page of the outside world's words is left out, and the count says it holds a rule word" 0 "-CANDIDATE wiki/sources/other.md" "+wiki/sources 4 (2 with a rule word)"
expect "the inventory says how each page came in and what it leaves out" 0 "+INVENTORY · how each came in:" "+a README" "+a row's home" "+INVENTORY · left out of the 8 wiki pages read: 3 records and registries, and 4 others:"

fresh; replace "$V/wiki/sources/unflagged.md" "never counted" "uncounted"; run in-place --vault "$V"
expect "no page read holds a rule word: the sorting is unproved, never a clean list" 2 "+PROBE FAILED: no page read holds a rule word"

fresh; printf 'One catalogue line: the owner ruled on this on 2020-05-05 in a run.\n' >"$V/wiki/index.md"; run in-place --vault "$V"
expect "the catalogue is no rule-holding page, though a line reads as a ruling" 0 "-CANDIDATE wiki/index.md" "+4 records and registries"
run record-audit --vault "$V" --today 2020-07-01; python3 -B - "$DOC" >"$OUT" 2>&1 <<'PY'
import json, sys
print(sorted(json.load(open(sys.argv[1], encoding="utf-8"))["audit"]["rule_files"]))
PY
rc=$?; expect "so a pass does not list it as a changed rule page each week, the others still recorded" 0 "-wiki/index.md" "+wiki/developments/fixture-rules.md"

fresh; edit_data 'rows.append(dict(by["R6#0-0"], id="R7#0-0", home={"file": ".claude/skills/fix/SKILL.md", "section": None}, text="Some step text."))'; printf 'A plain step.\n\nWords here (owner, 1 June 2020) and on.\n\nA later plain step.\n' >>"$V/.claude/skills/fix/SKILL.md"; run in-place --vault "$V"
expect "a skill that is a row's home gives only its dated rulings: its steps are listed by section" 0 "+CANDIDATE .claude/skills/fix/SKILL.md:" "+Words here (owner, 1 June 2020)" "-A later plain step."

fresh; edit_data 'data["rule_holding_pages"] = [".claude/agents/helper.md"]'; printf 'Sharpen the saw.\n' >>"$V/.claude/agents/helper.md"; run in-place --vault "$V"
expect "a file the data names as rule-holding is read whole" 0 "+Sharpen the saw." "+1 named by the data"

fresh; printf '%s\n' 'Keep the shed locked (owner, 9 September 2020).' >>"$V/wiki/sources/unflagged.md"; run in-place --vault "$V"
expect "in-place finds a page with a dated ruling" 0 "+CANDIDATE wiki/sources/unflagged.md:" "+Keep the shed locked"
printf 'A ruling only the log holds (owner, 1 May 2020).\n' >>"$V/wiki/log.md"; run in-place --vault "$V"
expect "in-place leaves dated records out" 0 "-wiki/log.md"

# ---- the clean-up's listing -----------------------------------------------------------------------
store_fixture() {
  fresh
  ST="$WORK/store"; chmod -R u+rwX "$ST" 2>/dev/null; rm -rf "$ST"
  mkdir -p "$ST/stages/run-20200101-old" "$ST/stages/run-20200101-namedincal" "$ST/stages/run-20200101-namedinpage" \
    "$ST/stages/run-20200101-recent" "$ST/stages/run-20200101-staged/new" "$ST/stages/run-20200101-staged/base" \
    "$ST/stages/run-20200101-installed/install" "$ST/stages/run-20200101-batch" "$ST/spawn-records" "$ST/handoffs" "$ST/backups/hold1" \
    "$WORK/projects"
  printf 'x%.0s' $(seq 1 2048) >"$ST/stages/run-20200101-old/f"
  printf 'x' >"$ST/stages/run-20200101-namedincal/f"
  printf 'x' >"$ST/stages/run-20200101-namedinpage/f"
  printf 'x' >"$ST/stages/run-20200101-recent/f"
  printf 'x' >"$ST/stages/run-20200101-staged/new/f"
  printf 'x' >"$ST/stages/run-20200101-installed/install/record.jsonl"
  printf 'x' >"$ST/stages/run-20200101-batch/f"
  printf 'x' >"$ST/spawn-records/run-20200101-helper-report-A.md"
  printf 'x' >"$ST/spawn-records/run-20200101-helper.jsonl"
  printf 'x' >"$ST/spawn-records/run-20200101-namedinpage-report-B.md"
  printf 'x' >"$ST/handoffs/abcd1234-20200101-handoff.md"
  printf 'x' >"$ST/backups/hold1/f"
  printf 'x' >"$ST/credentials.env"
  printf 'x' >"$WORK/projects/11111111-aaaa.jsonl"
  printf 'x' >"$WORK/projects/22222222-bbbb.jsonl"
  printf 'See session 22222222 in the record.\n' >>"$V/wiki/sources/unflagged.md"
  find "$ST" "$WORK/projects" -exec touch -t 202001010000 {} +
  touch "$ST/stages/run-20200101-recent/f"
}
store_fixture; run cleanup --vault "$V" --store "$ST" --projects "$WORK/projects"
expect "the clean-up reports sizes and lists each old record nothing names, with its size" 0 \
  "+SIZE stages ·" "+SIZE spawn-records ·" "+SIZE handoffs ·" \
  "+LIST run folder · run-20200101-old ·" "+KiB · last changed 2020-01-01" \
  "+LIST batch store · run-20200101-batch" "+LIST helper records · run-20200101-helper ·" \
  "+LIST hand-off file · abcd1234-20200101-handoff.md" "+LIST session transcript · 11111111-aaaa.jsonl"
expect "the clean-up keeps what a calendar line or wiki page names, and what is recent" 0 "-· run-20200101-namedincal" "-· run-20200101-namedinpage" "-· run-20200101-recent" "-22222222-bbbb"
expect "the clean-up holds back a backup or a staged package for the session to settle" 0 "+HELD run folder · run-20200101-staged" "+HELD run folder · run-20200101-installed" "+HELD install backup · hold1" "-LIST run folder · run-20200101-staged"
expect "the clean-up never names the credentials file" 0 "-credentials"
[ -d "$ST/stages/run-20200101-old" ] && [ -f "$ST/handoffs/abcd1234-20200101-handoff.md" ]; rc=$?; expect "the clean-up deletes nothing" 0

store_fixture; run cleanup --vault "$V" --store "$ST" --no-transcripts
expect "the clean-up can leave transcripts unread" 0 "+TRANSCRIPTS · not read" "-session transcript"

store_fixture; run cleanup --vault "$V" --store "$ST" --projects "$WORK/projects" --days 100000
expect "nothing older than the window: nothing listed" 0 "+OLD RECORDS · 0 listed"

store_fixture; cat >"$V/wiki/developments/known-issues.md" <<'EOF'
# Known issues
## Open
### an open entry naming run-20200101-batch
## Closed
### a closed entry naming run-20200101-old
EOF
printf 'run-20200101-helper was here.\n' >>"$V/wiki/log.md"; run cleanup --vault "$V" --store "$ST" --no-transcripts
expect "an open register entry keeps a record; a closed entry and the log do not" 0 "-· run-20200101-batch" "+LIST run folder · run-20200101-old" "+LIST helper records · run-20200101-helper"

store_fixture; rm "$V/CALENDAR.md"; run cleanup --vault "$V" --store "$ST" --projects "$WORK/projects"
expect "the calendar unread: nothing can be called unnamed" 2 "+PROBE FAILED: the calendar was not read"

store_fixture; rm -rf "$V/wiki"; run cleanup --vault "$V" --store "$ST" --projects "$WORK/projects"
expect "no wiki read: nothing can be called unnamed" 2 "+PROBE FAILED: no wiki page was read"

store_fixture; printf '# Calendar\n' >"$V/CALENDAR.md"; python3 -B - "$V/wiki/developments/fixture-rules.md" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read()
open(sys.argv[1], "w", encoding="utf-8").write(text.replace("run-20200101-namedinpage", "nothing"))
PY
python3 -B - "$V/wiki/sources/unflagged.md" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8").read()
open(sys.argv[1], "w", encoding="utf-8").write(text.replace("22222222", "nothing"))
PY
run cleanup --vault "$V" --store "$ST" --projects "$WORK/projects"
expect "old records and no name found anywhere: a broken premise, so it deletes nothing safely" 2 "+PROBE FAILED: none of the"

# ---- ship-safe ------------------------------------------------------------------------------------
# Derived, never held here: this machine's account name; and the agent's name, where the suite runs inside a vault.
ACCOUNT="$(id -un)"
AGENT_NAME="$(sed -n 's/^- \*\*agent_name\*\*: \([^ ]*\).*/\1/p' "$HERE/../../../CUSTOMISATION.md" 2>/dev/null)"
ship_grep() { grep -nE "/Use""rs/|/home/[a-z]|\[\[[a-z]" "$1"; grep -nF -e "$ACCOUNT" -e "${AGENT_NAME:-$ACCOUNT}" "$1"; }
ship_grep "$TOOL" >"$OUT"; [ -s "$OUT" ]; rc=$?; expect "the tool holds no home path, account name, agent name or literal wikilink" 1
grep -vF 'ship_grep' "$0" | grep -vE '\[\[(check-lifecycle|wikilink)\]\]' >"$WORK/suite-body"; ship_grep "$WORK/suite-body" >"$OUT"; [ -s "$OUT" ]; rc=$?; expect "the suite holds none either, its two fixture links apart" 1
{ cat "$TOOL"; printf '# %s/someone/vault\n' "/Use""rs"; } >"$WORK/planted.py"; ship_grep "$WORK/planted.py" >"$OUT"; [ -s "$OUT" ]; rc=$?; expect "control: the same grep catches a planted home path" 0
{ cat "$TOOL"; printf '# %s\n' "$ACCOUNT"; } >"$WORK/planted-b.py"; ship_grep "$WORK/planted-b.py" >"$OUT"; [ -s "$OUT" ]; rc=$?; expect "control: the same grep catches this machine's account name" 0
grep -c 'CUSTOMISATION-LOADED-v1' "$TOOL" >"$OUT"; rc=$?; expect "the marker the check looks for is a product line, held once" 0 "+1"
grep -ci 'all clear' "$TOOL" >"$OUT"; rc=$?; expect "the tool has no words for all clear: a check that cannot run says could not check" 1 "+0"
{ cat "$TOOL"; printf '# all clear\n'; } >"$WORK/planted-c.py"; grep -ci 'all clear' "$WORK/planted-c.py" >"$OUT"; rc=$?; expect "control: the same grep catches those words planted" 0 "+1"

fresh; python3 -B "$TOOL" seed --map /dev/null --rules /dev/null --tracing /dev/null >/dev/null 2>&1
python3 -B - "$TOOL" "$DOC" >"$OUT" 2>&1 <<'PY'
import json, sys
source = open(sys.argv[1], encoding="utf-8").read()
words = [w["text"] for row in json.load(open(sys.argv[2], encoding="utf-8"))["rows"] for w in row["approved"]]
hits = [w for w in words if w in source]
print(len(words), "wordings", len(hits), "in source")
sys.exit(1 if hits or not words else 0)
PY
rc=$?; expect "no approved wording stands in the tool's source" 0 "+2 wordings 0 in source"
{ cat "$TOOL"; printf '# %s\n' "$VISITOR"; } >"$WORK/planted2.py"
python3 -B - "$WORK/planted2.py" "$DOC" >"$OUT" 2>&1 <<'PY'
import json, sys
source = open(sys.argv[1], encoding="utf-8").read()
words = [w["text"] for row in json.load(open(sys.argv[2], encoding="utf-8"))["rows"] for w in row["approved"]]
sys.exit(1 if [w for w in words if w in source] else 0)
PY
rc=$?; expect "control: the same test catches a wording planted in source" 1

# ---- the last leg: the listing commands write nothing ---------------------------------------------
store_fixture; run record-audit --vault "$V" --today 2020-07-01; printf 'one changed\n' >"$V/raw/one.md"; seed_fixture
if command -v shasum >/dev/null; then SUM="shasum -a 256"; else SUM="sha256sum"; fi
# shellcheck disable=SC2086
manifest() { (cd "$1" && find . -print | LC_ALL=C sort && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 $SUM); }
COPY="$WORK/readonly"; rm -rf "$COPY"; mkdir -p "$COPY"; cp -R "$V" "$COPY/v"; cp -R "$ST" "$COPY/store"; cp -R "$SEED" "$COPY/seed"; cp -R "$WORK/projects" "$COPY/projects"
chmod 600 "$COPY/v/attic/cold.md"
mkdir -p "$COPY/cwd"   # the working folder for each run, read-only too, so a stray relative write fails
manifest "$COPY" >"$WORK/before.txt"
chmod -R a-w "$COPY"
wrote=""
for command in "wording-check" "wording-check --trial --installed-only R2" "weekly" "weekly --full" "weekly --all-flags" "in-place"; do
  # shellcheck disable=SC2086
  (cd "$COPY/cwd" && python3 -B "$TOOL" $command --vault "$COPY/v" >"$OUT" 2>&1) || wrote="$wrote; $command exit $?"
done
(cd "$COPY/cwd" && python3 -B "$TOOL" cleanup --vault "$COPY/v" --store "$COPY/store" --projects "$COPY/projects" >"$OUT" 2>&1) || wrote="$wrote; cleanup exit $?"
(cd "$COPY/cwd" && python3 -B "$TOOL" seed --map "$COPY/seed/map.jsonl" --rules "$COPY/seed/rules.jsonl" --tracing "$COPY/seed/tracing.jsonl" >/dev/null 2>"$OUT") || wrote="$wrote; seed exit $?"
chmod -R u+w "$COPY"
manifest "$COPY" >"$WORK/after.txt"
cmp -s "$WORK/before.txt" "$WORK/after.txt" || wrote="$wrote; the manifest changed"
[ -s "$WORK/before.txt" ] || wrote="$wrote; the manifest is empty"
verdict "on a read-only copy, every listing command runs and the checksum manifest is unchanged" "$wrote"

write_scan() {
  python3 -B - "$1" >"$OUT" 2>&1 <<'PY'
import re, sys
lines = open(sys.argv[1], encoding="utf-8").read().split("\n")
pattern = re.compile(r'open\([^)]*["\'][wax]b?["\']|os\.(?:replace|rename|remove|unlink|rmdir|mkdir|makedirs|chmod|truncate|link|symlink|utime)\b|shutil\.|\.write\(|write_text|write_bytes|\.unlink\(|"(?:mv|rm|cp|tee|touch|mkdir)"')
inside, depth, hits_in, hits_out = False, 0, 0, []
for number, line in enumerate(lines, 1):
    if line.startswith("def "):
        inside = line.startswith("def write_atomic")
    if pattern.search(line) and "sys.stdout.write" not in line:
        if inside:
            hits_in += 1
        else:
            hits_out.append((number, line.strip()))
print("in write_atomic", hits_in, "elsewhere", len(hits_out), hits_out[:5])
sys.exit(0 if hits_in and not hits_out else 1)
PY
  rc=$?
}
write_scan "$TOOL"; expect "the only write patterns in source sit inside write_atomic, and the scan hits them there" 0 "+elsewhere 0"
{ cat "$TOOL"; printf 'def stray():\n    open("x", "w")\n'; } >"$WORK/planted3.py"; write_scan "$WORK/planted3.py"; expect "control: the scan catches a stray write" 1 "+elsewhere 1"
grep -n 'write_atomic(' "$TOOL" | grep -v 'def write_atomic' | wc -l | tr -d ' ' >"$OUT"; rc=0; expect "three callers only: generate, record-audit and seed --out" 0 "+3"

echo
if [ "$failed" -eq 0 ]; then
  echo "PASS $total/$total"
  exit 0
fi
echo "FAIL $failed/$total"
exit 1
