#!/usr/bin/env bash
# test_check_tool_markup.sh — regression fixtures for check-tool-markup.py, the read-only check for tool-call
# markup of the model harness leaked into wiki pages, under the strict code rule (owner decision of 9 October
# 2026: only the lines inside a plain fence and a one-line code span in a plain paragraph, on a line outside the
# excluded contexts and the page's YAML frontmatter, are code; everything else is scanned, so an unusual quotation gives a visible false hit,
# never a missed leak; a line of an HTML stretch is read as HTML, so no backtick or backslash hides a comment opener,
# and a raw region whose end is unsure runs to the page end), and its walk, which makes any directory it cannot list
# and any entry it cannot classify an incomplete scan (exit 2), never a silent skip. Its callers are
# exercised too: the compile lane's output gate (the delegate skill's templates/brief-compile.md and its
# compile-core slice), the ingest skill's Step 7 self-check, routine lint, and deep-lint's pass of lint's
# pipeline. Each caller leg reads the command and the page selection from the caller's own text, runs it over a
# planted page set with a firing, a non-firing and an indeterminate case, and maps the exit to the verdict that
# same text states, so an edit that breaks a command or narrows a selection fails here. Every leg that expects
# no hit also requires a run that completed (its exit and its summary line's page count), so empty output from a
# failed run never passes.
#
# Every fixture is built under a fresh mktemp -d and removed at exit; no vault is touched. Every tag a fixture
# carries is built here from its parts (tg, tc and ts below), so this file holds no literal one. Every quiet case
# runs beside a twin that must fire, in the same invocation. The last legs are the stdout-only proof: checksum
# manifests of a read-only fixture copy and of the script home before and after, a source grep for write
# patterns with each pattern matched on its own control line, and a grep proving no hand-written file carries a
# literal named tag.
#
# Run:  bash test_check_tool_markup.sh      (ends PASS n/n or FAIL k/n; exit 0 = every leg passed)
set -uo pipefail

HOME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS="$(cd "$HOME_DIR/.." && pwd)"
TM="$HOME_DIR/check-tool-markup.py"
LINT_TEXT="$HOME_DIR/SKILL.md"
DEEP_TEXT="$SKILLS/deep-lint/SKILL.md"
STEP7_TEXT="$SKILLS/ingest/SKILL.md"
BRIEF_TEXT="$SKILLS/delegate/templates/brief-compile.md"
CORE_TEXT="$SKILLS/delegate/lane-home-src/compile-core/SKILL.md"

PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); printf '    ok   — %s\n' "$1"; }
no(){ FAIL=$((FAIL+1)); printf '  FAIL   — %s\n' "$1"; }
# eq <name> <expected> <actual>
eq(){ if [ "$2" = "$3" ]; then ok "$1"; else no "$1  [want '$2', got '$3']"; fi; }

W="$(mktemp -d)"
ERRF="$W/stderr.txt"
cleanup(){ chmod -R u+rwX "$W"; rm -rf "$W"; }
trap cleanup EXIT

manifest(){ find "$1" -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum | LC_ALL=C sort; }
# hashes <manifest> — how many hashed files a manifest actually holds (two empty manifests compare equal).
hashes(){ printf '%s\n' "$1" | grep -c '^[0-9a-f]\{40\}  '; }
START_H="$(manifest "$HOME_DIR")"

# ---------------------------------------------------------------------------------- builders
LT='<'
tg(){ printf '%s%s%s>' "$LT" "$1" "${2:-}"; }        # an opening tag:      tg NAME [ATTRIBUTES]
tc(){ printf '%s%s%s>' "$LT" '/' "$1"; }             # a closing tag:       tc NAME
ts(){ printf '%s%s%s/>' "$LT" "$1" "${2:-}"; }       # a self-closing tag:  ts NAME [ATTRIBUTES]
NS='antml:'                                         # the namespace prefix, as a word
B1='`'; B2='``'; B3='```'; B4='````'; T3='~~~'
ATTR_TICK=' name="`"'                               # an attribute value holding a backtick
FF="$(printf '\f')"                                 # a form feed
TAB="$(printf '\t')"                               # a tab

newvault(){ rm -rf "$1"; mkdir -p "$1/raw" "$1/wiki/sources" "$1/wiki/concepts" "$1/wiki/developments"
  printf -- '# raw capture\nfixture provenance file.\n' > "$1/raw/capture.md"; }
page(){ local f="$1"; shift; mkdir -p "$(dirname "$f")"; printf '%s\n' "$@" > "$f"; }
with_script(){ mkdir -p "$1/.claude/skills/lint"; cp "$TM" "$1/.claude/skills/lint/check-tool-markup.py"; }

run(){ OUT="$(python3 -B "$TM" "$@" 2>"$ERRF")"; RC=$?; }
nhits(){ printf '%s\n' "$OUT" | grep -cE ':[0-9]+: <'; }
has(){ printf '%s\n' "$OUT" | grep -qxF -- "$1"; }
mentions(){ printf '%s\n' "$OUT" | grep -qF -- "$1"; }
checked(){ printf '%s\n' "$OUT" | sed -n 's/^tool-markup: \([0-9][0-9]*\) pages checked.*/\1/p'; }
# lines_of <vault-relative page> — the hit lines reported for one page, space-separated
lines_of(){ printf '%s\n' "$OUT" | sed -n "s#^$1:\([0-9][0-9]*\): .*#\1#p" | tr '\n' ' ' | sed 's/ $//'; }
verdict(){ if [ "$1" = 0 ]; then printf 'passed'; else printf 'failed'; fi; }

V1="$W/v1"; newvault "$V1"

printf '\n--- the strict policy, each must-flag case beside its must-not-flag twin in one run ---\n'
# pair NAME TWIN-HITS DESCRIPTION — the quiet page and its twin, one run that completes over both pages (its
# summary line counts 2 checked, so a crash or a refused run cannot pass as quiet); the twin alone fires.
pair(){ local nm="$1" want="$2" desc="$3" qh th
  run --vault "$V1" --files "$V1/wiki/quiet/$nm.md" "$V1/wiki/quiet/$nm-twin.md"
  qh=$(printf '%s\n' "$OUT" | grep -cF -- "wiki/quiet/$nm.md:")
  th=$(printf '%s\n' "$OUT" | grep -cF -- "wiki/quiet/$nm-twin.md:")
  if [ "$RC" = 1 ] && [ "$(checked)" = 2 ] && [ "$qh" = 0 ] && [ "$th" = "$want" ]; then ok "quiet: $desc (0 hits; its twin gives $th on the same run)"
  else no "quiet: $desc  [exit $RC, $(checked) checked, quiet page $qh hits, twin $th, want $want]"; fi; }
page "$V1/wiki/quiet/plain-fence.md" "Quoted:" "" "$B3" "$(tc content)" "$B3" "" "After."
page "$V1/wiki/quiet/plain-fence-twin.md" "Quoted:" "" "$B3" "$(tc content)" "" "After."
pair plain-fence 1 "a tag in a plain fence; the twin's fence is never closed, so it protects nothing"
page "$V1/wiki/quiet/tilde-fence.md" "Quoted:" "" "$T3" "$(tc content)" "$T3" "" "After."
page "$V1/wiki/quiet/tilde-fence-twin.md" "Quoted:" "" "$T3" "$(tc content)" "" "After."
pair tilde-fence 1 "a tag in a closed tilde fence; the twin's tilde fence is never closed, so it protects nothing"
# The third review's three inputs: a one-line span in a context the policy scans. Each quiet page holds the same
# quotation in an ordinary paragraph; its twin holds the review's input, where backticks must not protect.
page "$V1/wiki/quiet/span-after-unclosed.md" "${B1}$(tc content)${B1}"
page "$V1/wiki/quiet/span-after-unclosed-twin.md" "$T3" "${B1}$(tc content)${B1}"
pair span-after-unclosed 1 "a tag quoted in a one-line span in an ordinary paragraph; the twin's same span follows a tilde fence never closed"
page "$V1/wiki/quiet/span-quoted-fence.md" "${B1}$(tc content)${B1}"
page "$V1/wiki/quiet/span-quoted-fence-twin.md" "> $T3" "> ${B1}$(tc content)${B1}" "> $T3"
pair span-quoted-fence 1 "a tag quoted in a one-line span in an ordinary paragraph; the twin's same span sits in a block-quoted fence"
page "$V1/wiki/quiet/span-indented.md" "${B1}$(tc content)${B1}"
page "$V1/wiki/quiet/span-indented-twin.md" "    ${B1}$(tc content)${B1}"
pair span-indented 1 "a tag quoted in a one-line span in an ordinary paragraph; the twin's same span is four spaces in, as indented code"
page "$V1/wiki/quiet/one-line-span.md" "The lane wrote ${B1}$(tc content)${B1} at the end."
page "$V1/wiki/quiet/one-line-span-twin.md" "The lane wrote ${B1}the" "$(tc content)${B1} at the end."
pair one-line-span 1 "a tag in a one-line code span; the twin's span is spread over two lines"
page "$V1/wiki/quiet/comment-in-fence.md" "$B3" "<!-- $(tc content) -->" "$B3"
page "$V1/wiki/quiet/comment-in-fence-twin.md" "Text." "" "<!-- $(tc content) -->"
pair comment-in-fence 1 "an HTML comment quoted in a plain fence; the twin's tag sits inside a live HTML comment"
page "$V1/wiki/quiet/indented.md" "Para." "" "$B3" "$(tc content)" "$B3"
page "$V1/wiki/quiet/indented-twin.md" "Para." "" "    $(tc content)"
pair indented 1 "a tag in a plain fence; the twin's tag is in an indented code block"
page "$V1/wiki/quiet/quote-fence.md" "$B3" "$(tc content)" "$B3"
page "$V1/wiki/quiet/quote-fence-twin.md" "> $B3" "> $(tc content)" "> $B3"
pair quote-fence 1 "a tag in a plain fence; the twin's fence is block-quoted"
page "$V1/wiki/quiet/prose-leak.md" "## Related" "- a related page" "${B1}$(tc content)${B1}"
page "$V1/wiki/quiet/prose-leak-twin.md" "## Related" "- a related page" "$(tc content)"
pair prose-leak 1 "a quoted closing tag; the twin carries the real leak in prose (the recorded incident's trailing line)"
page "$V1/wiki/quiet/no-tags.md" "# A page" "" "Text with ${B1}code${B1}, a fence below and an HTML comment." "" "$B3" "x" "$B3" "<!-- a note -->"
page "$V1/wiki/quiet/no-tags-twin.md" "# A page" "" "Text with a leak $(tg invoke ' name="Write"') in it."
pair no-tags 1 "a page with no tags at all"
run --vault "$V1" --files "$V1/wiki/quiet/no-tags.md"
if [ "$RC" = 0 ] && [ "$(checked)" = 1 ] && mentions "CANDIDATES: 0 named-tag opening(s) on 0 page(s)" && mentions "exit 0 (clean: no named tag outside code)" && mentions "CONTROL: in-memory: "
then ok "the page with no tags alone: exit 0, 1 page checked, 0 candidates, the clean verdict beside the in-memory controls"
else no "the page with no tags alone  [exit $RC: $OUT]"; fi

printf '\n--- firing: every named family in both forms, self-closing and with attributes ---\n'
FAM_DESC=(); FAM_TAG=()
fam(){ FAM_DESC+=("$1"); FAM_TAG+=("$2"); }
for n in content invoke parameter function_calls function_results; do
  fam "an opening $n tag" "$(tg "$n")"
  fam "a closing $n tag" "$(tc "$n")"
  fam "a self-closing $n tag" "$(ts "$n")"
  fam "an opening $n tag with an attribute" "$(tg "$n" ' name="x"')"
done
fam "an opening tag carrying the antml prefix, with an attribute" "$(tg "${NS}invoke" ' name="Bash"')"
fam "a closing tag carrying the antml prefix" "$(tc "${NS}parameter")"
fam "a self-closing tag carrying the antml prefix and a name outside the five" "$(ts "${NS}other_name")"
fam "an opening tag carrying the antml prefix, a dotted name outside the five and an attribute" "$(tg "${NS}x.sample-2" ' n="1"')"
fam "a self-closing parameter tag with an attribute" "$(ts parameter ' name="command"')"
fam "an opening parameter tag with two attributes" "$(tg parameter " name='command' data-x=1")"
fam "an opening function_calls tag in capitals" "$(tg FUNCTION_CALLS)"
FAM_LINES=("# Families" "")
for k in "${!FAM_TAG[@]}"; do FAM_LINES+=("Case $((k + 1)): ${FAM_TAG[$k]} in prose."); done
page "$V1/wiki/cases/families.md" "${FAM_LINES[@]}"
run --vault "$V1" --files "$V1/wiki/cases/families.md"
eq "the families page exits 1, one hit per planted line (${#FAM_TAG[@]})" "1-${#FAM_TAG[@]}" "$RC-$(nhits)"
for k in "${!FAM_TAG[@]}"; do
  if has "wiki/cases/families.md:$((k + 3)): ${FAM_TAG[$k]}"; then ok "fires, line and tag as found: ${FAM_DESC[$k]}"
  else no "fires: ${FAM_DESC[$k]}  [no 'wiki/cases/families.md:$((k + 3)): ...' line]"; fi
done

printf '\n--- firing: the recorded incident, comments, indented text, attribute backticks, quoted fences ---\n'
page "$V1/wiki/sources/incident-source.md" "---" 'title: "Source: An Incident"' "type: source" "depth: standard" \
  "confidence: high" "---" "" "## Summary" "A summary of the source." "" "## Key Takeaways" "- A takeaway." "" \
  "$(tc invoke)" "" "## Related" "- a related page" "$(tc content)"
run --vault "$V1" --files "$V1/wiki/sources/incident-source.md"
eq "the incident's closing invoke line mid-page and trailing closing content line (lines 14 and 18)" "1:14 18" "$RC:$(lines_of wiki/sources/incident-source.md)"
printf '%s\n\n%s' "Text." "$(tc content)" > "$V1/wiki/sources/incident-no-newline.md"
run --vault "$V1" --files "$V1/wiki/sources/incident-no-newline.md"
eq "a trailing closing content tag with no final newline (line 3)" "1:3" "$RC:$(lines_of wiki/sources/incident-no-newline.md)"
page "$V1/wiki/cases/comment.md" "Prose <!-- $(tc content) --> prose." "" "<!--" "$(tc invoke)" "-->"
run --vault "$V1" --files "$V1/wiki/cases/comment.md"
eq "a named tag inside an inline and inside a block HTML comment (lines 1 and 4)" "1:1 4" "$RC:$(lines_of wiki/cases/comment.md)"
page "$V1/wiki/cases/comment-span.md" "<!-- ${B1}$(tc content)${B1} -->" "" "Text <!-- a" "" "${B1}$(tc invoke)${B1}" "" "-->"
run --vault "$V1" --files "$V1/wiki/cases/comment-span.md"
eq "a code span inside an HTML comment, one-line and across blank lines, protects nothing (lines 1 and 5)" "1:1 5" "$RC:$(lines_of wiki/cases/comment-span.md)"
page "$V1/wiki/cases/indented.md" "A paragraph." "" "    $(tc content)" "" "Another paragraph" "    $(tc invoke)"
run --vault "$V1" --files "$V1/wiki/cases/indented.md"
eq "a named tag in four-space-indented text, indented code and a continuation line (lines 3 and 6)" "1:3 6" "$RC:$(lines_of wiki/cases/indented.md)"
page "$V1/wiki/cases/tick-attribute.md" "$(tg invoke "$ATTR_TICK")x${B1} and more"
run --vault "$V1" --files "$V1/wiki/cases/tick-attribute.md"
if [ "$RC" = 1 ] && has "wiki/cases/tick-attribute.md:1: $(tg invoke "$ATTR_TICK")"; then
  ok "a tag whose attribute value holds a backtick, a backtick later on the line: the tag fires, as found"
else no "a tag whose attribute value holds a backtick fires  [exit $RC: $OUT]"; fi
page "$V1/wiki/cases/quote-fences.md" "> $B3" "> one" "> $B3" "$(tc content)" "> $B3" "> two" "> $B3"
run --vault "$V1" --files "$V1/wiki/cases/quote-fences.md"
eq "a raw closing content tag between two block-quoted fenced blocks (line 4)" "1:4" "$RC:$(lines_of wiki/cases/quote-fences.md)"
page "$V1/wiki/cases/quote-fences-in.md" "> $B3" "> $(tc content)" "> $B3"
run --vault "$V1" --files "$V1/wiki/cases/quote-fences-in.md"
eq "a tag inside a block-quoted fence is not in a plain fence (line 2)" "1:2" "$RC:$(lines_of wiki/cases/quote-fences-in.md)"

printf '\n--- not firing, each beside a twin that must fire in the same invocation ---\n'
DETAILS=("$(tg details)" "$(tg summary)More$(tc summary)" "" "Body text with a line$(tg br)break." "" "$(tc details)")
page "$V1/wiki/quiet/details.md" "${DETAILS[@]}"
page "$V1/wiki/quiet/details-twin.md" "${DETAILS[@]}" "" "$(tc content)"
pair details 1 "a details block with its summary and closing tag (negative control: the twin adds a constructed closing content tag)"
page "$V1/wiki/quiet/br-table.md" "| Model | Notes |" "|---|---|" "| A | one$(tg br)two |"
page "$V1/wiki/quiet/br-table-twin.md" "| Model | Notes |" "|---|---|" "| A | one$(tc content)two |"
pair br-table 1 "a line-break tag in a table"
page "$V1/wiki/quiet/comment.md" "Prose <!-- an ordinary note with $(tg span) inside --> prose."
page "$V1/wiki/quiet/comment-twin.md" "Prose <!-- a note holding $(tc content) --> prose."
pair comment 1 "an HTML comment holding no named tag"
EVERY=()
for n in content invoke parameter function_calls function_results; do EVERY+=("$(tg "$n" ' name="x"')" "$(tc "$n")" "$(ts "$n")"); done
EVERY+=("$(tg "${NS}invoke" ' name="x"')" "$(tc "${NS}invoke")" "$(ts "${NS}other_name")")
NE=${#EVERY[@]}
page "$V1/wiki/quiet/fence-backtick.md" "Quoted:" "" "$B3" "${EVERY[@]}" "$B3" "" "After."
page "$V1/wiki/quiet/fence-backtick-twin.md" "Quoted:" "" "${EVERY[@]}" "" "After."
pair fence-backtick "$NE" "a triple-backtick fence quoting every family in all three forms ($NE tags)"
page "$V1/wiki/quiet/fence-tilde.md" "Quoted:" "" "$T3" "${EVERY[@]}" "$T3" "" "After."
page "$V1/wiki/quiet/fence-tilde-twin.md" "Quoted:" "" "${EVERY[@]}" "" "After."
pair fence-tilde "$NE" "a tilde fence quoting every family"
page "$V1/wiki/quiet/fence-long.md" "$B4" "$B3" "${EVERY[@]}" "$B3" "$B4"
page "$V1/wiki/quiet/fence-long-twin.md" "$B3" "$B3" "${EVERY[@]}" "$B3" "$B4"
pair fence-long "$NE" "a four-backtick fence holding a shorter backtick run (the twin's three-backtick fence closes on it)"
page "$V1/wiki/quiet/fence-list.md" "- a step:" "  $B3" "  $(tc content)" "  $B3" "- the next step"
page "$V1/wiki/quiet/fence-list-twin.md" "- a step:" "  $B3" "  $(tc content)" "$B3" "- the next step"
pair fence-list 1 "a list item's fence, closed at its own indentation (the twin's closing line at the margin may end the item first, so it protects nothing)"
page "$V1/wiki/quiet/fence-deep-closer.md" "$B3" "    $B3" "$(tc content)" "$B3"
page "$V1/wiki/quiet/fence-deep-closer-twin.md" "- item" "  $B3" "     $B3" "  $(tc content)" "  $B3"
pair fence-deep-closer 1 "under a fence at the margin a run indented four spaces is content (the twin's list-item fence meets a deeper run, which may close it, so nothing is protected)"
page "$V1/wiki/quiet/inline-code.md" "Quoted ${B1}$(tc content)${B1} and ${B2}$(tc invoke)${B2} and ${B2} a ${B1} $(tg parameter ' name="x"') ${B2} here."
page "$V1/wiki/quiet/inline-code-twin.md" "Quoted $(tc content) and $(tc invoke) and a $(tg parameter ' name="x"') here."
pair inline-code 3 "inline code quoting tags with single and double backtick delimiters"
page "$V1/wiki/quiet/table-span.md" "| a | b |" "|---|---|" "| x | ${B1}$(tc content)${B1} |"
page "$V1/wiki/quiet/table-span-twin.md" "| a | b |" "|---|---|" "| x | ${B1}$(tc content) | y${B1} |"
pair table-span 1 "a tag quoted in a table cell's span (the twin's span holds a pipe, which a cell boundary would cut)"
WO='[''['; WC=']'']'                                 # a wikilink's brackets, built so this file holds none
page "$V1/wiki/quiet/wikilink.md" "See ${WO}Some Page${WC} and ${B1}$(tc content)${B1}."
page "$V1/wiki/quiet/wikilink-twin.md" "See ${WO}Some${B1}Page${WC} and $(tc content) ${B1}."
pair wikilink 1 "a wikilink beside a quoted tag (the twin's wikilink holds a backtick, so its pairing is not trusted)"
page "$V1/wiki/quiet/html-then-fence.md" "$(tg details)" "" "$B3" "$(tc content)" "$B3" "" "$(tc details)"
page "$V1/wiki/quiet/html-then-fence-twin.md" "$(tg details)" "$B3" "$(tc content)" "$B3" "" "$(tc details)"
pair html-then-fence 1 "a plain fence after an HTML block and a blank line (the twin's fence sits inside the HTML block)"
page "$V1/wiki/quiet/look-alikes.md" "Tags $(tg parameters) and $(tg content-type) and $(tc parameters) are other names."
page "$V1/wiki/quiet/look-alikes-twin.md" "Tags $(tg parameter) and $(tg content-type) and $(tc parameters) are other names."
pair look-alikes 1 "a parameters tag and a content-type tag (names that only begin alike)"
page "$V1/wiki/quiet/comment-apart.md" "<!-- a note -->" "" "The lane wrote ${B1}$(tc content)${B1}."
page "$V1/wiki/quiet/comment-apart-twin.md" "<!-- a note -->" "The lane wrote ${B1}$(tc content)${B1}."
pair comment-apart 1 "a span in a paragraph a blank line away from an HTML comment (the twin's comment shares the paragraph, so its spans are not trusted)"

printf '\n--- code boundaries: the strict rule at its edges ---\n'
# probe NAME WANT DESCRIPTION LINE... — WANT is the space-separated hit lines, empty for none. The run must
# complete: exit 0 with no hit or 1 with hits, and a summary line counting the page checked, so empty output
# from a failed run never reads as quiet.
probe(){ local nm="$1" want="$2" desc="$3" rc=1; shift 3
  [ -n "$want" ] || rc=0
  page "$V1/wiki/probe/$nm.md" "$@"; run --vault "$V1" --files "$V1/wiki/probe/$nm.md"
  eq "boundary: $desc" "$rc-1-$want" "$RC-$(checked)-$(lines_of "wiki/probe/$nm.md")"; }
probe tilde-closed "" "a tag inside a closed tilde fence" "$T3" "$(tc content)" "$T3"
probe tilde-unclosed "2" "a tag after a tilde fence never closed fires (end of page closes no fence)" "$T3" "$(tc content)"
probe double-span "" "a tag inside a double-backtick span" "x ${B2} $(tc content) ${B2} y"
probe two-line-span "2" "a tag inside a code span across two lines fires (reversed from the first build)" "a ${B1}b" "$(tc content)${B1} c"
probe two-line-shift "2" "a span left open on one line shifts the pairing of the next, so its spans protect nothing" "a ${B1}b" "${B1}$(tc content)${B1} c"
probe two-line-double "2" "a double-backtick run left open pairs on the next line, around a one-line span there" "x ${B2} y" "${B1}$(tc content)${B1} z ${B2}"
probe obsidian-comment "1" "an Obsidian comment may hold a backtick, so the paragraph's spans protect nothing" "%% ${B1} %% $(tc content) ${B1}"
probe tick-attr "1" "a tag whose attribute value holds a backtick, then a backtick" "$(tg invoke "$ATTR_TICK")x${B1}"
probe long-fence "" "a four-backtick fence holding a shorter run and a tag" "$B4" "q $B3 r" "$B3" "$(tc content)" "$B4"
probe tilde-not-by-ticks "6" "a tilde fence is not closed by backticks" "$T3" "$(tc content)" "$B3" "$(tc content)" "$T3" "$(tc content)"
probe longer-closer "4" "a longer fence closes a shorter one" "$B3" "$(tc content)" "$B4" "after $(tc content)"
probe closer-indented "" "a closing line indented up to three spaces closes a fence at the margin" "$B3" "$(tc content)" "   $B3"
probe closer-trailing "2 4" "a closing line followed by other text closes nothing, so the fence never closes and protects nothing" "$B3" "$(tc content)" "$B3 x" "$(tc content)"
probe list-fence "3 4" "a list item's fence its container ends is never closed, so it protects nothing (reversed in part)" "- item" "  $B3" "  $(tc content)" "$(tc invoke)"
probe opener-indented-4 "2" "a run indented four spaces is no plain fence" "    $B3" "$(tc content)" "    $B3"
probe opener-tab "2" "a run behind a tab is no plain fence" "${TAB}$B3" "$(tc content)" "${TAB}$B3"
probe opener-list "2" "a run behind a list marker is no plain fence" "- $B3" "  $(tc content)" "  $B3"
probe disturbed-after "5" "after a fence-shaped line that is no plain opening line, no fence opens again" "    $B3" "x" "" "$B3" "$(tc content)" "$B3"
probe unclosed-then-pair "4" "after a fence never closed, a later pair of fence lines protects nothing" "$B4" "x" "$B3" "$(tc content)" "$B3"
probe html-not-fence "3" "fence lines inside an HTML block are not a fence" "$(tg div)" "$B3" "$(tc content)" "$B3" "$(tc div)"
probe html-no-span "2" "a span inside an HTML block protects nothing" "$(tg details)" "${B1}$(tc content)${B1}" "$(tc details)"
probe comment-fence "3" "fence lines inside an HTML comment are not a fence" "<!--" "$B3" "$(tc content)" "$B3" "-->"
probe pre-block "3" "a span inside a pre block across a blank line protects nothing" "$(tg pre)" "" "${B1}$(tc content)${B1}" "" "$(tc pre)"
probe escaped-tick "1" "a backslash-escaped backtick opens no span" "a \\${B1}$(tc content)${B1} b"
probe escaped-shift "1" "an escaped backtick leaves the rest of its run to pair, which shifts the spans after it" "\\${B2} a ${B1} $(tc content) ${B1} b"
probe cell-ends-span "3" "a table cell ends a span" "| a | b |" "|---|---|" "| ${B1}x | $(tc content) | y${B1} |"
probe link-tick "1" "a link destination may hold a backtick, so the paragraph's spans protect nothing" "[l](u${B1}) $(tc content) ${B1}"
probe html-tick "1" "an ordinary tag's attribute may hold a backtick, so the paragraph's spans protect nothing" "$(tg span "$ATTR_TICK") $(tc content) ${B1}"
probe comment-tick "1" "an inline comment holds its backtick, and the paragraph's spans protect nothing" "Text <!-- ${B1} --> $(tc content) ${B1}"
probe autolink-tick "1" "an autolink may hold a backtick" "<x${B1}@y.z> $(tc content) ${B1}"
# The same two mid-line, where the line is prose, not a line of an HTML stretch: only rule (c) voids the span there.
probe html-tick-midline "1" "an ordinary tag mid-line whose attribute holds a backtick voids the paragraph's spans (rule c)" "Text $(tg span "$ATTR_TICK") $(tc content) ${B1}"
probe autolink-tick-midline "1" "an email autolink mid-line holding a backtick voids the paragraph's spans (rule c)" "Text <x${B1}@y.z> $(tc content) ${B1}"
probe footnote-tick "1" "a footnote label may hold a backtick" "a[^x${B1}] $(tc content) ${B1}"
probe frontmatter "2" "a tag in frontmatter" "---" "title: x $(tc content)" "---"
probe heading-span "" "a tag quoted in a heading's code span" "# Head ${B1}$(tc content)${B1}"
probe info-string "1" "a fence's info string is scanned (reversed from the first build)" "${B3}$(tc content)" "body" "$B3"
probe table-pipe-tag "3" "a table row whose tag holds a pipe in an attribute value" "| a | b |" "|---|---|" "| a | $(tg invoke ' name="x|y"') |"
probe table-cell-span "" "a tag quoted in a table cell's code span" "| a |" "|---|" "| ${B1}$(tc content)${B1} |"
probe table-escaped-pipe "3" "a span holding an escaped pipe protects nothing (reversed from the first build)" "| a |" "|---|" "| ${B1}$(tg invoke ' name="x\|y"')${B1} |"
probe surplus-cell "" "a span in a cell past the header's count is still a one-line span (reversed from the first build)" "| a |" "|---|" "| x | ${B1}$(tc content)${B1} |"
probe definition-title "1" "a reference definition's title holding a span-like quotation" "[a]: /url \"${B1} $(tc content) ${B1}\""
probe link-title "1" "an inline link's title holding the same" "[a](/url \"${B1} $(tc content) ${B1}\")"
probe definition-title-lines "2" "a reference definition's title across two lines" "[a]: /url \"one" "${B1} $(tc content) ${B1}\""
probe definition-then-span "2" "a paragraph opening with a definition is not plain (reversed from the first build)" "[a]: /url" "Some ${B1}$(tc content)${B1} text."
probe reference-label "1 3" "a full reference link's label and a definition's label" "See [x][${B1}$(tc content)${B1}] here." "" "[${B1}$(tc content)${B1}]: /u"
probe reference-undefined "1" "a full reference link's label fires whether or not a definition matches it (reversed)" "See [x][${B1}$(tc content)${B1}] here."
probe definition-fresh-line "3" "a definition holding a lone backtick, then a span across lines" "[${B1}]: /x" "    ${B1}" "$(tc content)${B1}"
probe colon-dash-span "3" "a span over a one-cell line and a line of colons and dashes is two lines long (reversed)" "a ${B1}" ":---" "$(tc content)${B1}"
probe colon-dash-piped "3" "the same under a header row holding a pipe" "| a ${B1}" ":---" "$(tc content)${B1}"
printf 'One.\r\n\r\n%s\r\n' "$(tc content)" > "$V1/wiki/probe/crlf.md"
run --vault "$V1" --files "$V1/wiki/probe/crlf.md"
eq "boundary: a CRLF page reports the source line (3)" "1-1-3" "$RC-$(checked)-$(lines_of wiki/probe/crlf.md)"
printf '\357\273\277%s\n' "$(tc content)" > "$V1/wiki/probe/bom.md"
run --vault "$V1" --files "$V1/wiki/probe/bom.md"
eq "boundary: a page opening with a byte-order mark (line 1)" "1-1-1" "$RC-$(checked)-$(lines_of wiki/probe/bom.md)"
page "$V1/wiki/probe/two-line-tag.md" "a $(printf '%sinvoke' "$LT")" 'name="x"> b'
run --vault "$V1" --files "$V1/wiki/probe/two-line-tag.md"
if [ "$RC" = 1 ] && [ "$(checked)" = 1 ] && has "wiki/probe/two-line-tag.md:1: $(printf '%sinvoke\\nname="x">' "$LT")"; then ok "a tag spanning a line ending is reported on its first line, the line ending shown as \\n"
else no "a tag spanning a line ending  [$OUT]"; fi
page "$V1/wiki/probe/truncated.md" "The page ends in a cut tag $(printf '%s/content' "$LT")"
run --vault "$V1" --files "$V1/wiki/probe/truncated.md"
eq "boundary: a tag cut off before its closing bracket still fires (line 1)" "1-1-1" "$RC-$(checked)-$(lines_of wiki/probe/truncated.md)"

printf '\n--- excluded contexts: a one-line span on such a line protects nothing ---\n'
# Rules (f), (g) and (h) of the docstring: a block quote, an opening run holding a tab or four spaces in a row, and
# every line from a fence that opened no plain fence to the end of the page. Each quiet case runs beside a twin.
probe third-unclosed-tilde "2" "third review, finding 2: a one-line span after a tilde fence never closed" "$T3" "${B1}$(tc content)${B1}"
probe third-quoted-fence "2" "third review, finding 2: a one-line span inside a block-quoted fence" "> $T3" "> ${B1}$(tc content)${B1}" "> $T3"
probe third-indented "1" "third review, finding 2: a one-line span four spaces in, as indented code" "    ${B1}$(tc content)${B1}"
probe unclosed-backtick-span "4" "a one-line span after a backtick fence never closed, a blank line apart (rule h)" "$B3" "x" "" "${B1}$(tc content)${B1}"
probe after-indented-run-span "4" "a one-line span after a fence run four spaces in (rule h)" "    $B3" "x" "" "${B1}$(tc content)${B1}"
probe after-item-run-span "4" "a one-line span after a fence run behind a list marker (rule h)" "- $B3" "  x" "" "${B1}$(tc content)${B1}"
probe after-comment-run-span "5" "a one-line span after a fence run inside an HTML comment (rule h)" "<!--" "$B3" "-->" "" "${B1}$(tc content)${B1}"
probe quote-para-span "1" "a one-line span in a block quote's paragraph (rule f: any block quote)" "> The lane wrote ${B1}$(tc content)${B1}."
probe quote-in-item-span "1" "a one-line span in a block quote inside a list item (rule f)" "- > ${B1}$(tc content)${B1}"
probe tab-item-span "2" "a one-line span on a nested list item indented by a tab (rule g)" "- item" "${TAB}- nested ${B1}$(tc content)${B1}"
probe four-item-span "2" "a one-line span on a nested list item four spaces in (rule g)" "- item" "    - nested ${B1}$(tc content)${B1}"
probe item-code-span "1" "a one-line span in a list item that opens with indented code, five spaces after its marker (rule g)" "-     ${B1}$(tc content)${B1}"
probe item-tab-span "1" "a one-line span behind a list marker and a tab (rule g)" "-${TAB}${B1}$(tc content)${B1}"
page "$V1/wiki/quiet/after-closed-fence.md" "$B3" "x" "$B3" "" "${B1}$(tc content)${B1}"
page "$V1/wiki/quiet/after-closed-fence-twin.md" "$B3" "x" "" "${B1}$(tc content)${B1}"
pair after-closed-fence 1 "a one-line span after a closed plain fence (the twin's fence is never closed, so nothing after it is code)"
page "$V1/wiki/quiet/before-unclosed.md" "a ${B1}$(tc content)${B1}" "$T3" "b"
page "$V1/wiki/quiet/before-unclosed-twin.md" "$T3" "a ${B1}$(tc content)${B1}" "b"
pair before-unclosed 1 "a one-line span on the line above a tilde fence never closed (the twin's span follows the fence)"
page "$V1/wiki/quiet/three-spaces.md" "   ${B1}$(tc content)${B1}"
page "$V1/wiki/quiet/three-spaces-twin.md" "    ${B1}$(tc content)${B1}"
pair three-spaces 1 "a one-line span three spaces in (the twin's four spaces may be indented code)"
page "$V1/wiki/quiet/item-span.md" "- item ${B1}$(tc content)${B1}" "  - nested ${B1}$(tc content)${B1}"
page "$V1/wiki/quiet/item-span-twin.md" "- item ${B1}$(tc content)${B1}" "    - nested ${B1}$(tc content)${B1}"
pair item-span 1 "one-line spans in a list item and in a nested item two spaces in (the twin's nested item is four spaces in)"
page "$V1/wiki/quiet/lazy-after-quote.md" "> A quoted note" "the lane wrote ${B1}$(tc content)${B1}."
page "$V1/wiki/quiet/lazy-after-quote-twin.md" "> A quoted note" "> the lane wrote ${B1}$(tc content)${B1}."
pair lazy-after-quote 1 "a one-line span on a line after a block-quote line: only its own line's opening run counts (the twin's line carries the marker)"

printf '\n--- YAML frontmatter: never code; a body tag must be code on the page read whole and on the body read alone ---\n'
# The two must-flag shapes of the frontmatter finding: a backticked tag in the title, and a tilde fence around a tag in a
# description block scalar. Each page carries nothing else that would flag and is checked alone.
# fmleg NAME LINE DESCRIPTION LINE... — exit 1, one page checked, exactly one hit, listed on LINE with the tag as found.
fmleg(){ local nm="$1" want="$2" desc="$3"; shift 3
  page "$V1/wiki/frontmatter/$nm.md" "$@"; run --vault "$V1" --files "$V1/wiki/frontmatter/$nm.md"
  if [ "$RC" = 1 ] && [ "$(checked)" = 1 ] && [ "$(nhits)" = 1 ] && has "wiki/frontmatter/$nm.md:$want: $(tc content)"
  then ok "frontmatter, must flag: $desc (exit 1, listed on line $want as found)"
  else no "frontmatter, must flag: $desc  [exit $RC, $(checked) checked, $(nhits) hit(s): $OUT]"; fi; }
fmleg title-span 2 "a closing content tag in backticks in the title" \
  "---" "title: ${B1}$(tc content)${B1}" "type: concept" "---" "" "## Definition" "A fixture page."
fmleg block-fence 4 "a closing content tag in a tilde fence inside a description block scalar" \
  "---" "description: |" "  $T3" "  $(tc content)" "  $T3" 'title: "Fixture"' "---" "" "## Definition" "A fixture page."
# The quiet body controls: the same two quoting shapes kept in the frontmatter without a tag, the tag quoted as plain
# code in the body. Each stays exit 0 checked alone with its one tag seen, and runs beside a twin whose body quotation
# is broken (the span's backticks dropped; the fence's closing line dropped), which must fire on the same run.
# fmquiet NAME — the quiet page alone: exit 0, one page checked, no hit, one named-tag opening seen.
fmquiet(){ local nm="$1" desc="$2"
  run --vault "$V1" --files "$V1/wiki/quiet/$nm.md"
  eq "frontmatter, quiet alone: $desc" "0-1-0-1" "$RC-$(checked)-$(nhits)-$(printf '%s\n' "$OUT" | sed -n 's/^CANDIDATES: \([0-9][0-9]*\) named-tag.*/\1/p')"; }
page "$V1/wiki/quiet/fm-body-span.md" "---" "title: ${B1}x${B1}" "type: concept" "---" "" "The lane wrote ${B1}$(tc content)${B1}."
page "$V1/wiki/quiet/fm-body-span-twin.md" "---" "title: ${B1}x${B1}" "type: concept" "---" "" "The lane wrote $(tc content)."
pair fm-body-span 1 "a tag in a one-line span in a body paragraph after frontmatter quoting a backticked title (the twin's tag is in prose)"
fmquiet fm-body-span "a tag in a one-line span in a body paragraph after frontmatter stays exit 0"
page "$V1/wiki/quiet/fm-body-fence.md" "---" "description: |" "  $T3" "  x" "  $T3" "---" "" "$T3" "$(tc content)" "$T3"
page "$V1/wiki/quiet/fm-body-fence-twin.md" "---" "description: |" "  $T3" "  x" "  $T3" "---" "" "$T3" "$(tc content)"
pair fm-body-fence 1 "a tag in a plain fence in the body after frontmatter holding a fenced block scalar (the twin's body fence is never closed)"
fmquiet fm-body-fence "a tag in a plain fence in the body after frontmatter stays exit 0"
# The two readings. The body read alone: a fence opened at the margin inside the frontmatter protects no body line. The
# page read whole: a comment the frontmatter leaves open still unprotects the body, so the rule never protects a line
# the whole-page reading leaves bare (a false hit by design, as before the rule).
fmleg margin-fence 4 "a body tag under a fence opened at the margin inside the frontmatter (the body read alone)" \
  "---" "$T3" "---" "$(tc content)" "$T3"
probe fm-comment-kept "6" "a fenced body tag after frontmatter holding a comment opener still fires (the page read whole)" \
  "---" "note: <!--" "---" "" "$T3" "$(tc content)" "$T3"
# Where frontmatter is: the first line and a later closing line, both three hyphens. A page whose delimiter is not on
# its first line, or whose frontmatter never closes, has none and is read as Markdown, where the span is plain code.
page "$V1/wiki/quiet/fm-not-first.md" "" "---" "title: ${B1}$(tc content)${B1}" "---"
page "$V1/wiki/quiet/fm-not-first-twin.md" "---" "title: ${B1}$(tc content)${B1}" "---"
pair fm-not-first 1 "a spanned tag under a delimiter on the second line (the twin's delimiter is on the first line, so its title is frontmatter)"
page "$V1/wiki/quiet/fm-unclosed.md" "---" "title: ${B1}$(tc content)${B1}" "" "Text."
page "$V1/wiki/quiet/fm-unclosed-twin.md" "---" "title: ${B1}$(tc content)${B1}" "---" "" "Text."
pair fm-unclosed 1 "a spanned tag after an opening delimiter never closed (the twin's frontmatter closes)"
fmleg trailing-blanks 2 "delimiters carrying trailing blanks still open and close frontmatter" \
  "--- " "title: ${B1}$(tc content)${B1}" "---${TAB}"
printf '\357\273\277---\r\ntitle: %s%s%s\r\n---\r\n' "$B1" "$(tc content)" "$B1" > "$V1/wiki/frontmatter/bom-crlf.md"
run --vault "$V1" --files "$V1/wiki/frontmatter/bom-crlf.md"
if [ "$RC" = 1 ] && [ "$(checked)" = 1 ] && [ "$(nhits)" = 1 ] && has "wiki/frontmatter/bom-crlf.md:2: $(tc content)"
then ok "frontmatter, must flag: a page saved with a byte-order mark and CRLF line endings (exit 1, listed on line 2 as found)"
else no "frontmatter, must flag: a page saved with a byte-order mark and CRLF line endings  [exit $RC: $OUT]"; fi

printf '\n--- raw HTML: a line of an HTML stretch is read as HTML, and a region whose end is unsure runs to the page end ---\n'
# The fourth review's three variants: a comment opener that a backtick or a backslash hid on an HTML line, then, after a
# blank line, a fenced or spanned tag a browser renders inside that comment. Each variant must fire on one page checked
# alone. Each plain-code control is the same page with its HTML lines made ordinary prose, where the backticked opener
# is a code span and the escaped one plain text, so the same quotation is plain code: it must stay quiet on one page
# checked alone, and its variant, checked alone by the same script, must fire (the control's positive control).
cands(){ printf '%s\n' "$OUT" | sed -n 's/^CANDIDATES: \([0-9][0-9]*\) named-tag.*/\1/p'; }
# rawleg NAME WANT DESCRIPTION LINE... — one page alone: exit 1 on the WANT line, one page checked, its one tag seen.
rawleg(){ local nm="$1" want="$2" desc="$3"; shift 3
  page "$V1/wiki/raw/$nm.md" "$@"; run --vault "$V1" --files "$V1/wiki/raw/$nm.md"
  eq "raw HTML: $desc" "1-1-$want-1" "$RC-$(checked)-$(lines_of "wiki/raw/$nm.md")-$(cands)"; }
# rawctl NAME VARIANT WANT DESCRIPTION LINE... — the control page alone: exit 0, one page checked, its one tag seen and
# exempt; then its VARIANT alone: exit 1 on the WANT line, one page checked.
rawctl(){ local nm="$1" var="$2" want="$3" desc="$4" q v; shift 4
  page "$V1/wiki/raw/$nm.md" "$@"
  run --vault "$V1" --files "$V1/wiki/raw/$nm.md"; q="$RC-$(checked)-$(lines_of "wiki/raw/$nm.md")-$(cands)"
  run --vault "$V1" --files "$V1/wiki/raw/$var.md"; v="$RC-$(checked)-$(lines_of "wiki/raw/$var.md")"
  eq "raw HTML: $desc" "0-1--1 1-1-$want" "$q $v"; }
rawleg review4-tilde "5" "fourth review, the tilde-fence variant: a backticked comment opener on an HTML line, then a fenced tag after a blank line, fires" \
  "<div>" "${B1}<!--${B1}" "" "$T3" "$(tc content)" "$T3" "-->" "" "</div>"
rawleg review4-span "4" "fourth review, the one-line-span variant: the same opener, then a tag in a one-line span, fires" \
  "<div>" "${B1}<!--${B1}" "" "${B1}$(tc content)${B1}" "-->" "" "</div>"
rawleg review4-backslash "4" "fourth review, the backslash variant: an escaped comment opener on an HTML line, then a spanned tag, fires" \
  "<div>" "\\<!--" "" "${B1}$(tc content)${B1}" "-->" "" "</div>"
rawctl review4-tilde-control review4-tilde "5" "control: the tilde-fence variant with its HTML lines made prose stays quiet (its variant fires on line 5)" \
  "Text." "${B1}<!--${B1}" "" "$T3" "$(tc content)" "$T3" "-->" "" "End."
rawctl review4-span-control review4-span "4" "control: the one-line-span variant with its HTML lines made prose stays quiet (its variant fires on line 4)" \
  "Text." "${B1}<!--${B1}" "" "${B1}$(tc content)${B1}" "-->" "" "End."
rawctl review4-backslash-control review4-backslash "4" "control: the backslash variant with its HTML lines made prose stays quiet (its variant fires on line 4)" \
  "Text." "\\<!--" "" "${B1}$(tc content)${B1}" "-->" "" "End."
# Neighbouring corners of the same kind, each quiet page beside its firing twin in one run (2 pages checked): the quiet
# page closes its region where a renderer surely does; the twin leaves the close in doubt, or opens a comment where a
# browser does, and must fire on the stated line.
corner(){ local nm="$1" want="$2" desc="$3"
  run --vault "$V1" --files "$V1/wiki/raw/$nm.md" "$V1/wiki/raw/$nm-twin.md"
  eq "raw HTML: $desc" "1-2--$want" "$RC-$(checked)-$(lines_of "wiki/raw/$nm.md")-$(lines_of "wiki/raw/$nm-twin.md")"; }
page "$V1/wiki/raw/closer-escaped.md" "<div>" "<!-- a note -->" "" "$T3" "$(tc content)" "$T3"
page "$V1/wiki/raw/closer-escaped-twin.md" "<div>" "<!--" "" "-->" "" "$T3" "$(tc content)" "$T3"
corner closer-escaped "7" "a comment its HTML block leaves open is closed by no escaped -->, so the fence after it fires (the quiet page closes its comment on its own line)"
page "$V1/wiki/raw/end-line.md" "<!--" "" "-->" "${B1}<!--${B1}" "" "$T3" "$(tc content)" "$T3"
page "$V1/wiki/raw/end-line-twin.md" "<!--" "" "--> ${B1}<!--${B1}" "" "$T3" "$(tc content)" "$T3"
corner end-line "6" "the rest of a comment block's closing line is HTML, so a backticked opener there opens a comment (on the next line it is a code span)"
page "$V1/wiki/raw/quote-ends.md" "> <div><!-- a note --></div>" "" "$T3" "$(tc content)" "$T3"
page "$V1/wiki/raw/quote-ends-twin.md" "> <div>" "> <!--" "-->" "" "$T3" "$(tc content)" "$T3"
corner quote-ends "6" "a block quote that ends before its comment's --> leaves the comment open (the quiet page closes it on its own line)"
page "$V1/wiki/raw/pre-comment.md" "<pre>" "<!-- a note -->" "</pre>" "" "$T3" "$(tc content)" "$T3"
page "$V1/wiki/raw/pre-comment-twin.md" "<pre>" "<!--" "</pre>" "" "$T3" "$(tc content)" "$T3"
corner pre-comment "6" "a comment opened inside a pre element swallows its closing tag and the fence after (the quiet page's closes inside)"
page "$V1/wiki/raw/pi-comment.md" "<?x ?>" "" "$T3" "$(tc content)" "$T3"
page "$V1/wiki/raw/pi-comment-twin.md" "<?x > <!-- ?>" "" "$T3" "$(tc content)" "$T3"
corner pi-comment "4" "a browser ends a processing instruction at its first >, so an opener after that opens a comment (the quiet page's instruction holds none)"
page "$V1/wiki/raw/pre-name.md" "<pre" "</pre>" "" "$T3" "$(tc content)" "$T3"
page "$V1/wiki/raw/pre-name-twin.md" "<pre" "" "$T3" "$(tc content)" "$T3" "</pre>"
corner pre-name "4" "a pre element whose name ends its line holds raw HTML to its closing tag (the quiet page closes it before the fence)"
page "$V1/wiki/raw/margin-block.md" "<!--" "a note" "" "more" "-->" "" "$T3" "$(tc content)" "$T3"
page "$V1/wiki/raw/margin-block-twin.md" "<div>" "<!--" "a note" "" "more" "-->" "" "$T3" "$(tc content)" "$T3"
corner margin-block "9" "a comment block at the margin ends at its -->, blank lines included, so the fence after is code; under an HTML line the blank line ends the block first"
page "$V1/wiki/raw/prose-one-line.md" "Text <!-- a note -->" "" "$T3" "$(tc content)" "$T3"
page "$V1/wiki/raw/prose-one-line-twin.md" "Text <!-- a" "note -->" "" "$T3" "$(tc content)" "$T3"
corner prose-one-line "5" "a comment in prose that spans lines runs to the page end, a false hit by design (on one line it ends at its -->)"
page "$V1/wiki/raw/prose-rejected.md" "Text <!-- a -->" "<pre>" "x" "</pre>" "" "$T3" "$(tc content)" "$T3"
page "$V1/wiki/raw/prose-rejected-twin.md" "Text <!-- a" "<pre>" "-->" "" "${B1}<!--${B1}" "</pre>" "" "$T3" "$(tc content)" "$T3"
corner prose-rejected "9" "a pre block that cuts a paragraph short voids the comment opened in it and opens its own: why a comment in prose over lines runs to the page end"
page "$V1/wiki/raw/item-pre.md" "- <pre>x</pre>" "" "$T3" "$(tc content)" "$T3"
page "$V1/wiki/raw/item-pre-twin.md" "- <pre>" "<!--" "  </pre>" "" "$T3" "$(tc content)" "$T3" "-->"
corner item-pre "6" "a list item's end cuts its pre block short, and a comment block at the margin then holds the fence (the quiet page's element closes on its own line)"

printf '\n--- the earlier reviews: their inputs under the strict rule ---\n'
# The first and the second review's inputs. Under the strict rule the reader no
# longer decides any of them: each either fires as a tag outside code or fires as an unusual quotation.
probe review1-pipe-in-tag "3" "first review, finding 1: a table row whose tag holds a pipe" "| a | b |" "|---|---|" "| a | $(tg invoke ' name="x|y"') |"
probe review1-definition "1" "first review, finding 1: a reference definition's title" "[a]: /url \"${B1} $(tc content) ${B1}\""
probe review1b-colon-dash "3" "first review, finding 2: a span over a pipe-less colon-dash line is two lines long, so it fires" "a ${B1}" ":---" "$(tc content)${B1}"
probe review2-formfeed-close "1" "second review, finding 1: a closing tag with a form feed before its bracket" "Text $(printf '%s/content%s>' "$LT" "$FF") end."
probe review2-formfeed-open "1" "second review, finding 1: a self-closing tag with a form feed before its attribute" "Text $(printf '%sinvoke%scommand="x"/>' "$LT" "$FF") end."
probe review2-two-newlines "1" "second review, finding 1: a tag in a comment, two line endings inside the tag" "<!-- $(printf '%sinvoke' "$LT")" "" "name=\"x\"> -->"
probe review2-nested-link "1" "second review, finding 2: a span in a nested link's apparent title fires as an unusual quotation" "[a [b](u)](v \"${B1}$(tc content)${B1}\")"
probe review2-table-html "4" "second review, finding 2: a span after a tag row under a table fires as an unusual quotation" "| a |" "|---|" "$(tg span)" "${B1}$(tc content)${B1}"
probe review2-gap "2" "second review, its gap: a span left open above a table row fires, with no reader to reconcile" "${B1}" "$(tc content)" "| x ${B1} |" "---"

printf '\n--- cannot decide: unreadable and missing pages, empty selections, a denied subtree ---\n'
UNR="$V1/wiki/cases/unreadable.md"; page "$UNR" "Text."; chmod 000 "$UNR"
if [ -r "$UNR" ]; then no "premise: chmod 000 denies a read (a superuser run cannot test unreadable pages)"
else
  run --vault "$V1" --files "$UNR"
  eq "an unreadable page: cannot check, 0 pages checked, exit 2, never clean" "2-1-0-0" "$RC-$(printf '%s\n' "$OUT" | grep -c '^cannot check wiki/cases/unreadable.md (')-$(checked)-$(printf '%s\n' "$OUT" | grep -c 'clean')"
  run --vault "$V1" --files "$V1/wiki/sources/incident-source.md" "$UNR"
  eq "exit 2 takes precedence over hits: the hits still print, the exit is 2" "2-2" "$RC-$(nhits)"
fi
run --vault "$V1" --files "$V1/wiki/cases/no-such-page.md"
eq "a missing page: cannot check, exit 2" "2-1" "$RC-$(printf '%s\n' "$OUT" | grep -c '^cannot check wiki/cases/no-such-page.md (')"
run --vault "$V1" --files
eq "an empty --files selection prints 0 pages checked and exits 2, never clean" "2-0-1-0" "$RC-$(checked)-$(printf '%s\n' "$OUT" | grep -c 'an empty selection decides nothing')-$(printf '%s\n' "$OUT" | grep -c 'clean')"
EV="$W/empty-wiki"; newvault "$EV"
run --vault "$EV" --all
eq "--all over a wiki holding no page: 0 pages checked, exit 2, never clean" "2-0-0" "$RC-$(checked)-$(printf '%s\n' "$OUT" | grep -c 'clean')"
DV="$W/denied"; newvault "$DV"
page "$DV/wiki/concepts/A.md" "Clean."; page "$DV/wiki/sources/B.md" "Clean."; page "$DV/wiki/sources/C.md" "$(tc content)"
chmod 000 "$DV/wiki/sources"
if [ -r "$DV/wiki/sources" ]; then no "premise: chmod 000 denies a directory listing"
else
  run --vault "$DV" --all
  eq "--all with a subtree it cannot enter beside a readable page: incomplete scan, exit 2, 1 page checked" \
    "2-1-1" "$RC-$(printf '%s\n' "$OUT" | grep -c '^incomplete scan: wiki/sources (')-$(checked)"
fi
chmod 755 "$DV/wiki/sources"
run --vault "$DV" --all
eq "control: the same tree once enterable: 3 pages checked, the subtree's hit found, exit 1" "1-3-1" "$RC-$(checked)-$(nhits)"
# An entry whose classification fails: a link to a directory whose parent denies search, so a stat through the link
# is refused. A walk that files such an entry as a file name drops it (no .md suffix) and reports clean.
LKV="$W/link-vault"; newvault "$LKV"; page "$LKV/wiki/concepts/A.md" "Clean."
page "$W/outside/locked/sub/linked-page.md" "Text." "" "$(tc content)"
ln -s "$W/outside/locked/sub" "$LKV/wiki/linked"
chmod 000 "$W/outside/locked"
python3 -B -c 'import os, sys; os.stat(sys.argv[1])' "$LKV/wiki/linked" 2>"$ERRF"; src=$?
if [ "$src" = 0 ] || ! grep -q 'PermissionError' "$ERRF"; then no "premise: a stat through the link is denied  [exit $src: $(tail -1 "$ERRF")]"
else
  run --vault "$LKV" --all
  eq "--all with a linked directory it cannot classify (the stat through the link denied): incomplete scan, exit 2, 1 page checked, never clean" \
    "2-1-1-0" "$RC-$(printf '%s\n' "$OUT" | grep -c '^incomplete scan: wiki/linked (cannot classify: ')-$(checked)-$(printf '%s\n' "$OUT" | grep -c 'clean')"
fi
chmod 755 "$W/outside/locked"
run --vault "$LKV" --all
eq "control: the same link once its target is reachable: 2 pages checked, the linked page's planted tag found, exit 1" \
  "1-2-1-1" "$RC-$(checked)-$(nhits)-$(printf '%s\n' "$OUT" | grep -c 'linked/linked-page.md:3: ')"
ODV="$W/odd-entries"; newvault "$ODV"; page "$ODV/wiki/concepts/A.md" "Clean."
ln -s "$W/no-such-target" "$ODV/wiki/gone"; ln -s loop "$ODV/wiki/loop"
run --vault "$ODV" --all
eq "--all with a link whose target is missing and a link to itself: two entries it cannot classify, exit 2, never clean" \
  "2-1-1-1-0" "$RC-$(printf '%s\n' "$OUT" | grep -c '^incomplete scan: wiki/gone (cannot classify: ')-$(printf '%s\n' "$OUT" | grep -c '^incomplete scan: wiki/loop (cannot classify: ')-$(checked)-$(printf '%s\n' "$OUT" | grep -c 'clean')"
rm -f "$ODV/wiki/gone" "$ODV/wiki/loop"
ln -s /dev/null "$ODV/wiki/device.md"
run --vault "$ODV" --all
eq "--all with an entry named as a page that is no regular file (a link to a device): cannot check, exit 2" \
  "2-1-1" "$RC-$(printf '%s\n' "$OUT" | grep -c '^cannot check wiki/device.md (not a regular file)')-$(checked)"
rm -f "$ODV/wiki/device.md"
run --vault "$ODV" --all
eq "control: the same tree without its odd entries: exit 0, 1 page checked, no incomplete scan" "0-1-0" "$RC-$(checked)-$(printf '%s\n' "$OUT" | grep -c '^incomplete scan')"
run --vault "$V1" --files /dev/null
eq "--files naming a device: cannot check (not a regular file), 0 pages checked, exit 2" "2-1-0" \
  "$RC-$(printf '%s\n' "$OUT" | grep -c '^cannot check /dev/null (not a regular file)')-$(checked)"
# A listing cut short cannot be planted on a real file system: an in-process substitute for os.scandir fails the
# read of wiki/sources after its first entry, as a failing directory read would; the control reads every entry.
CUT="$W/cut-vault"; newvault "$CUT"; page "$CUT/wiki/concepts/A.md" "Clean."
page "$CUT/wiki/sources/B.md" "Clean."; page "$CUT/wiki/sources/C.md" "$(tc content)"
cut_run(){ OUT="$(python3 -B - "$TM" "$CUT" "$1" 2>"$ERRF" <<'PYCUT'
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("check_tool_markup", sys.argv[1])
ctm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctm)
root, cut = sys.argv[2], sys.argv[3] == "cut"
real_scandir = os.scandir

class CutShort:
    """os.scandir over the real directory; with cut, listing a directory named sources fails after one entry."""
    def __init__(self, path):
        self.path, self.inner = path, real_scandir(path)
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        self.inner.close()
    def __iter__(self):
        for n, entry in enumerate(self.inner):
            if cut and n == 1 and os.path.basename(self.path) == "sources":
                raise OSError(5, "Input/output error")
            yield entry

os.scandir = CutShort
sys.exit(ctm.main(["--vault", root, "--all"]))
PYCUT
)"; RC=$?; }
cut_run cut
eq "--all with a listing cut short: incomplete scan, exit 2, 1 page checked, never clean" "2-1-1-0" \
  "$RC-$(printf '%s\n' "$OUT" | grep -c '^incomplete scan: wiki/sources (Input/output error)')-$(checked)-$(printf '%s\n' "$OUT" | grep -c 'clean')"
cut_run whole
eq "control: the same substitute reading every entry: 3 pages checked, the hit found, exit 1" "1-3-1" "$RC-$(checked)-$(nhits)"

printf '\n--- broken premises: stderr only, stdout empty, exit 2 ---\n'
NV="$W/notavault"; mkdir -p "$NV/docs"; printf 'a directory that is not a vault\n' > "$NV/docs/readme.md"
# premise NAME PATTERN ARGS... — exit 2, nothing on stdout, one PROBE FAILED line on stderr matching PATTERN.
premise(){ local nm="$1" pat="$2" gout grc; shift 2
  gout="$(python3 -B "$TM" "$@" 2>"$ERRF")"; grc=$?
  if [ "$grc" = 2 ] && [ -z "$gout" ] && [ "$(grep -c "^PROBE FAILED: .*$pat" "$ERRF")" = 1 ] && [ "$(wc -l < "$ERRF" | tr -d ' ')" = 1 ]
  then ok "$nm (exit 2, one PROBE FAILED line on stderr, stdout empty)"
  else no "$nm  [exit $grc, stdout '$gout', stderr '$(head -1 "$ERRF")']"; fi; }
premise "--all on a root that is not a vault is refused" 'is not a vault root (no raw/ or wiki/)' --vault "$NV" --all
premise "--files on a root that is not a vault is refused" 'is not a vault root (no raw/ or wiki/)' --vault "$NV" --files "$NV/docs/readme.md"
premise "an unknown flag is refused, never read as the root" 'unknown argument --deep' --vault "$V1" --deep --all
premise "a stray word is refused, never read as a page or a root" 'unknown argument' --vault "$V1" "$V1/wiki/cases/comment.md"
premise "two selections are refused" 'two selections' --vault "$V1" --all --files "$V1/wiki/cases/comment.md"
premise "no selection is refused" 'no page selection' --vault "$V1"
premise "--vault with no directory is refused" '--vault needs a directory' --vault
run --vault "$V1" --files "$V1/wiki/cases/comment.md"
if [ "$RC" = 1 ] && [ -n "$OUT" ] && [ ! -s "$ERRF" ]; then ok "control: the same script scans a fixture vault on the same run (exit 1, stdout, empty stderr)"
else no "control: the same script scans a fixture vault  [exit $RC]"; fi
DR="$W/default-root"; newvault "$DR"; with_script "$DR"; page "$DR/wiki/concepts/X.md" "$(tc content)"
OUT="$( (cd "$W" && python3 -B "$DR/.claude/skills/lint/check-tool-markup.py" --all) 2>"$ERRF")"; RC=$?
eq "with no --vault the root is the vault the script ships in (run from outside it)" "1-1" "$RC-$(lines_of wiki/concepts/X.md)"
NDR="$W/no-vault-home"; with_script "$NDR"
gout="$( (cd "$DR" && python3 -B "$NDR/.claude/skills/lint/check-tool-markup.py" --all) 2>"$ERRF")"; grc=$?
if [ "$grc" = 2 ] && [ -z "$gout" ] && grep -q 'is not a vault root (no raw/ or wiki/)' "$ERRF"; then ok "a script shipped outside a vault refuses its default root, even run from inside a vault"
else no "a script shipped outside a vault refuses its default root  [exit $grc]"; fi

printf '\n--- caller 1: the compile lane output gate (brief-compile.md, the compile-core slice) ---\n'
# span_cmd FILE — the code spans in FILE that call the script with python3, delimiters dropped.
span_cmd(){ grep -oE '`python3 [^`]*check-tool-markup\.py[^`]*`' "$1" | tr -d '`'; }
CV="$W/compile-vault"; newvault "$CV"; with_script "$CV"
LANEHOME="$W/lane-home"; mkdir -p "$LANEHOME"
NEWSRC="$CV/wiki/sources/new-source.md"; UPD="$CV/wiki/concepts/Updated Network.md"; UNT="$CV/wiki/concepts/Untouched Page.md"
page "$NEWSRC" "---" 'title: "Source: New"' "type: source" "---" "" "## Summary" \
  "The source quotes ${B1}$(tc content)${B1} as code, which is legitimate." "" "## Related" "- a link"
updated(){ page "$UPD" "---" 'title: "Updated Network"' "type: concept" "---" "" "## Definition" \
  "A concept page the lane updated." "$1" "" "## Related" "- a link"; }
page "$UNT" "A page the lane never touched." "" "$(tc invoke)"
run --vault "$CV" --files "$UNT"
eq "premise: the untouched page outside the lane's selection carries a hit when checked alone" "1" "$RC"
# selection FILE — the gate's selection as the caller text states it: the words after "followed by" in the
# sentence naming the command, to that sentence's end, with line breaks and indentation folded.
selection(){ tr '\n' ' ' < "$1" | tr -s ' ' | grep -oE 'check-tool-markup\.py --files` followed by [^.]*\.' | sed 's/^.*followed by //'; }
# lane_pages CLAUSE — the pages the lane passes to the gate, chosen by the clause's own words, never by this suite:
# a fixture page goes in when the clause names how the lane touched it (created, updated; a clause naming neither
# takes every page, untouched ones included) and, where the clause names page kinds (source, network), its kind.
lane_pages(){ local words life=0 kind=0; words=" $(printf '%s' "$1" | tr -c 'A-Za-z' ' ') "; SEL=()
  names(){ case "$words" in *" $1 "*) return 0 ;; *) return 1 ;; esac; }
  { names created || names updated; } && life=1
  { names source || names network; } && kind=1
  pick(){ { [ "$life" = 0 ] || names "$1"; } && { [ "$kind" = 0 ] || names "$2"; } && SEL+=("$3"); return 0; }
  pick created source "$NEWSRC"; pick updated network "$UPD"; pick untouched network "$UNT"; }
# gate TEMPLATE [PAGE ...] — the instructed command with its vault slot filled, run from a lane home outside the
# vault (a headless lane's working directory), over the pages the text's selection names (SEL) and any extra.
gate(){ local tpl="$1" cmd words; shift
  cmd="${tpl//'{{vault root}}'/$CV}"; cmd="${cmd//'<vault root>'/$CV}"
  read -r -a words <<< "$cmd"
  OUT="$( (cd "$LANEHOME" && "${words[@]}" ${SEL[@]+"${SEL[@]}"} "$@") 2>"$ERRF")"; RC=$?; }
gate_legs(){ local label="$1" text="$2" rule="$3" tpl clause
  tpl="$(span_cmd "$text")"
  eq "$label names exactly one command for the check" "1" "$(printf '%s\n' "$tpl" | grep -c 'check-tool-markup')"
  eq "$label states the gate's verdict rule ('$rule')" "1" "$(grep -cF -- "$rule" "$text")"
  eq "$label states the handling of a hit: a real leak removed, a false alarm requoted as plain code" "1-1" \
    "$(tr '\n' ' ' < "$text" | tr -s ' ' | grep -ciF 'remove a real leak')-$(tr '\n' ' ' < "$text" | tr -s ' ' | grep -ciF "false alarm's quotation")"
  clause="$(selection "$text")"
  eq "$label states its selection: every page created or updated, source and network alike, none it did not touch" "1-1-1" \
    "$(printf '%s\n' "$clause" | grep -c 'created or updated')-$(printf '%s\n' "$clause" | grep -c 'source and network')-$(printf '%s\n' "$clause" | grep -c 'did not touch')"
  lane_pages "$clause"
  updated "$(tc content)"
  gate "$tpl"
  if [ "$RC" = 1 ] && [ "$(verdict "$RC")" = failed ] && [ "$(checked)" = 2 ] && has "wiki/concepts/Updated Network.md:8: $(tc content)" && ! mentions "Untouched Page"
  then ok "$label, firing: over the pages its selection names, a tag on an updated network page fails the gate; the untouched page is not reported"
  else no "$label, firing  [selection '$clause', ${#SEL[@]} page(s), exit $RC: $OUT]"; fi
  updated "The lane quotes ${B1}$(tc content)${B1} in code."
  gate "$tpl"
  if [ "$RC" = 0 ] && [ "$(verdict "$RC")" = passed ] && [ "$(checked)" = 2 ] && ! mentions "Untouched Page"
  then ok "$label, quiet: the tag requoted as plain code, the gate passes over the 2 pages its selection names"
  else no "$label, quiet  [${#SEL[@]} page(s), exit $RC: $OUT]"; fi
  gate "$tpl" "$CV/wiki/concepts/Named But Not Written.md"
  if [ "$RC" = 2 ] && [ "$(verdict "$RC")" = failed ] && mentions "cannot check wiki/concepts/Named But Not Written.md ("
  then ok "$label, cannot decide: a page in the selection that cannot be read fails the gate (exit 2)"
  else no "$label, cannot decide  [exit $RC: $OUT]"; fi; }
gate_legs "brief-compile.md" "$BRIEF_TEXT" "Any non-zero exit fails the output gate."
gate_legs "the compile-core slice" "$CORE_TEXT" "Any non-zero exit is a failed output gate"
# A headless lane runs the command under the delegate skill's fence, whose compile class grants `wiki` and the
# raws: the instructed command must clear it with one file grant on the script, and the same command must be
# refused without that grant (the control). Not counted where the delegate skill is not installed beside lint.
FENCE="$SKILLS/delegate/lane-fence.py"
fence_says(){ (cd "$LANEHOME" && python3 -B - "$FENCE" "$1" "$2" "$3" <<'PYFENCE_Q'
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("lane_fence", sys.argv[1])
fence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fence)
event = {"tool_name": "Bash", "tool_input": {"command": sys.argv[2]}}
print(fence.check(event, json.loads(sys.argv[3]), json.loads(sys.argv[4]))[0])
PYFENCE_Q
); }
if [ -f "$FENCE" ]; then
  CVR="$(cd "$CV" && pwd -P)"
  WRITES="$(printf '["%s/wiki"]' "$CVR")"
  for text in "$BRIEF_TEXT" "$CORE_TEXT"; do
    tpl="$(span_cmd "$text")"; cmd="${tpl//'{{vault root}}'/$CVR}"; cmd="${cmd//'<vault root>'/$CVR}"
    cmd="$cmd \"$CVR/wiki/sources/new-source.md\" \"$CVR/wiki/concepts/Updated Network.md\""
    with="$(fence_says "$cmd" "$(printf '["%s/wiki", "%s/.claude/skills/lint/check-tool-markup.py"]' "$CVR" "$CVR")" "$WRITES")"
    without="$(fence_says "$cmd" "$(printf '["%s/wiki"]' "$CVR")" "$WRITES")"
    eq "the delegate fence admits $(basename "$(dirname "$text")")/$(basename "$text")'s command under the compile grants plus a file grant on the script, and refuses it without (control)" "allow-deny" "$with-$without"
  done
else
  printf '    n/a  — the delegate skill is not installed beside lint: the fence legs are not run (not counted)\n'
fi

printf '\n--- caller 2: the ingest skill Step 7 self-check, over the run output set after the merge ---\n'
SV="$W/step7-vault"; newvault "$SV"; with_script "$SV"; MARK="$W/run.marker"
page "$SV/wiki/concepts/Untouched Page.md" "A page no lane and no merge wrote." "" "$(tc invoke)"
page "$SV/wiki/concepts/Shared Page.md" "---" 'title: "Shared Page"' "type: concept" "---" "" "## Definition" \
  "A shared concept." "" "## Appears in" "- an older source"
page "$SV/wiki/index.md" "# Index" "- an older entry"; page "$SV/wiki/log.md" "# Log"
touch -t 201901010000 "$SV/wiki/concepts/Untouched Page.md" "$SV/wiki/concepts/Shared Page.md" "$SV/wiki/index.md" "$SV/wiki/log.md"
touch -t 202001010000 "$MARK"
# The command, the manifest, the verdict and when the set is taken all come from the text: a text that never says
# the manifest is taken again after the merge has its set taken once, before the merge.
STEP7_CMD="$(span_cmd "$STEP7_TEXT")"
STEP7_LINE="$(grep -E '^6\. No page of the run' "$STEP7_TEXT")"
MAN="$(printf '%s\n' "$STEP7_LINE" | grep -oE "\`find <vault>/wiki -name '\*\.md' -newer <marker>\`" | tr -d '`')"
MAN_CMD="${MAN//'<vault>'/$SV}"; MAN_CMD="${MAN_CMD//'<marker>'/$MARK}"
AFTER_MERGE="$(printf '%s\n' "$STEP7_LINE" | grep -c 'taken again after the merge')"
take_set(){ SET=(); while IFS= read -r p; do SET+=("$p"); done < <(bash -c "$MAN_CMD"); }
run_step7(){ local words; read -r -a words <<< "$STEP7_CMD"
  OUT="$( (cd "$SV" && "${words[@]}" ${SET[@]+"${SET[@]}"}) 2>"$ERRF")"; RC=$?; }
step7(){ take_set; run_step7; }
# The run: the lane's pages and registry lines, then the head's merge applies a shared-page diff with patch.
page "$SV/wiki/sources/run-source.md" "---" 'title: "Source: Run"' "type: source" "---" "" "## Summary" "Clean." "" "## Related" "- a link"
page "$SV/wiki/concepts/Lane Concept.md" "A concept the lane created." "" "## Related" "- a link"
printf -- '- the run entry\n' >> "$SV/wiki/index.md"; printf -- '## [2026-01-01] ingest | fixture\n' >> "$SV/wiki/log.md"
[ "$AFTER_MERGE" = 1 ] || take_set
cp "$SV/wiki/concepts/Shared Page.md" "$W/shared.before"
{ cat "$W/shared.before"; printf -- '- the run source\n\n%s\n' "$(tc content)"; } > "$W/shared.after"
diff -u "$W/shared.before" "$W/shared.after" > "$W/shared.diff"
patch -s "$SV/wiki/concepts/Shared Page.md" < "$W/shared.diff"; prc=$?
eq "premise: the head's merge applied the shared-page diff with patch" "0" "$prc"
[ "$AFTER_MERGE" = 1 ] && take_set
run_step7
eq "ingest Step 7 names exactly one command for the check" "1" "$(printf '%s\n' "$STEP7_CMD" | grep -c 'check-tool-markup')"
eq "Step 7 names the Verify step's manifest as the way to list the set" "1" "$(printf '%s\n' "$MAN" | grep -c 'newer')"
eq "Step 7 states its verdict rule" "1" "$(printf '%s\n' "$STEP7_LINE" | grep -c 'A non-zero exit therefore fails this step')"
eq "Step 7 states the handling of a hit: a real leak removed, a false alarm rewritten as plain code" "1-1" \
  "$(printf '%s\n' "$STEP7_LINE" | grep -c 'remove a real leak')-$(printf '%s\n' "$STEP7_LINE" | grep -c 'a false alarm (a tag quoted in a way the check.s strict rule does not count as code) is rewritten as plain code')"
eq "Step 7's set holds each shared-page change applied at merge, the manifest taken again after the merge" "1-1" \
  "$(printf '%s\n' "$STEP7_LINE" | grep -c 'each shared-page change applied at merge')-$AFTER_MERGE"
SETS="$(printf '%s\n' ${SET[@]+"${SET[@]}"} | sed "s#^$SV/##" | LC_ALL=C sort | tr '\n' '|')"
eq "the set, taken when the text says: the lane's pages, the applied shared page, index and log; not the untouched page" \
  "wiki/concepts/Lane Concept.md|wiki/concepts/Shared Page.md|wiki/index.md|wiki/log.md|wiki/sources/run-source.md|" "$SETS"
if [ "$RC" = 1 ] && [ "$(verdict "$RC")" = failed ] && [ "$(checked)" = 5 ] && has "wiki/concepts/Shared Page.md:13: $(tc content)" && ! mentions "Untouched Page"
then ok "Step 7, firing: the tag the merge applied to a shared page fails the self-check"
else no "Step 7, firing  [exit $RC: $OUT]"; fi
page "$SV/wiki/concepts/Shared Page.md" "$(sed '$d' "$W/shared.after")"
step7
if [ "$RC" = 0 ] && [ "$(verdict "$RC")" = passed ] && [ "$(checked)" = 5 ]; then ok "Step 7, quiet: the tag removed, the self-check passes over the 5-page set"
else no "Step 7, quiet  [exit $RC: $OUT]"; fi
chmod 000 "$SV/wiki/concepts/Lane Concept.md"
step7
if [ "$RC" = 2 ] && [ "$(verdict "$RC")" = failed ] && mentions "cannot check wiki/concepts/Lane Concept.md ("
then ok "Step 7, cannot decide: a page of the set that cannot be read fails the self-check (exit 2)"
else no "Step 7, cannot decide  [exit $RC: $OUT]"; fi
chmod 644 "$SV/wiki/concepts/Lane Concept.md"
touch "$MARK"
step7
if [ "$RC" = 2 ] && [ "$(checked)" = 0 ] && [ "${#SET[@]}" = 0 ]; then ok "Step 7, cannot decide: a manifest that lists nothing prints 0 pages checked and fails (exit 2)"
else no "Step 7, an empty set  [exit $RC, ${#SET[@]} listed: $OUT]"; fi

printf '\n--- caller 3: routine lint, --all, report-only; deep-lint runs the same command ---\n'
LV="$W/lint-vault"; newvault "$LV"; with_script "$LV"
page "$LV/wiki/sources/a-source.md" "A source quoting ${B1}$(tc content)${B1} as code."
page "$LV/wiki/concepts/C.md" "A concept."
page "$LV/wiki/developments/dev-note.md" "# A development note" "" "Text." "" "$(tc invoke)" "" "More text."
LINT_CMD="$(span_cmd "$LINT_TEXT")"
DEEP_CMD="$(span_cmd "$DEEP_TEXT")"
eq "lint SKILL.md names exactly one command for the check" "1" "$(printf '%s\n' "$LINT_CMD" | grep -c 'check-tool-markup')"
eq "lint SKILL.md makes the check report-only, a cannot-decide never clean" "1" \
  "$(grep -F -- 'check-tool-markup.py --vault . --all' "$LINT_TEXT" | grep -F 'report-only' | grep -cF 'reported as a finding, never as clean')"
eq "lint SKILL.md states the handling: the agent removes a real leak and rewrites a false alarm's quotation as plain code" "1" \
  "$(grep -F -- 'check-tool-markup.py --vault . --all' "$LINT_TEXT" | grep -F 'the agent removes a real leak' | grep -cF "rewrites a false alarm's quotation as plain code")"
eq "lint's report format carries the tool-markup line" "1" "$(grep -cF '`tool-markup: clean / N hits on M pages / cannot decide`' "$LINT_TEXT")"
eq "deep-lint SKILL.md names exactly one command for the check, the same as lint's" "1-$LINT_CMD" "$(printf '%s\n' "$DEEP_CMD" | grep -c 'check-tool-markup')-$DEEP_CMD"
eq "deep-lint SKILL.md states the handling and carries the tool-markup line in its report" "1-1-1" \
  "$(tr '\n' ' ' < "$DEEP_TEXT" | tr -s ' ' | grep -cF 'remove a real leak')-$(tr '\n' ' ' < "$DEEP_TEXT" | tr -s ' ' | grep -cF "rewrite a false alarm's quotation as plain code")-$(grep -c '^- tool-markup: clean / N hits on M pages' "$DEEP_TEXT")"
lint_run(){ local words; read -r -a words <<< "$1"; OUT="$( (cd "$LV" && "${words[@]}") 2>"$ERRF")"; RC=$?; }
DEV_BEFORE="$(shasum < "$LV/wiki/developments/dev-note.md")"
lint_run "$LINT_CMD"
if [ "$RC" = 1 ] && has "wiki/developments/dev-note.md:5: $(tc invoke)" && [ "$(checked)" = 3 ] \
   && [ "$(shasum < "$LV/wiki/developments/dev-note.md")" = "$DEV_BEFORE" ]
then ok "lint, firing: a page outside wiki/sources is listed as a finding (exit 1, 3 pages checked) and left unchanged"
else no "lint, firing  [exit $RC: $OUT]"; fi
lint_run "$DEEP_CMD"
if [ "$RC" = 1 ] && has "wiki/developments/dev-note.md:5: $(tc invoke)" && [ "$(checked)" = 3 ]
then ok "deep-lint, firing: its command lists the same hit over the same 3 pages"
else no "deep-lint, firing  [exit $RC: $OUT]"; fi
page "$LV/wiki/developments/dev-note.md" "# A development note" "" "Text." "" "${B1}$(tc invoke)${B1}" "" "More text."
lint_run "$LINT_CMD"
eq "lint, quiet: the tag requoted as plain code, exit 0 over 3 pages" "0-3" "$RC-$(checked)"
chmod 000 "$LV/wiki/developments"
lint_run "$LINT_CMD"
eq "lint, cannot decide: a subtree it cannot enter is an incomplete scan (exit 2), never clean" "2-1-0" \
  "$RC-$(printf '%s\n' "$OUT" | grep -c '^incomplete scan: wiki/developments (')-$(printf '%s\n' "$OUT" | grep -c 'clean')"
chmod 755 "$LV/wiki/developments"

printf '\n--- stdout-only proof and source hygiene (must run last) ---\n'
RO="$W/readonly"; rm -rf "$RO"; cp -R "$LV" "$RO"
page "$RO/wiki/concepts/Hit.md" "$(tc content)"
BEFORE="$(manifest "$RO")"
chmod -R a-w "$RO"
python3 -B "$TM" --vault "$RO" --all > /dev/null; r1=$?
python3 -B "$TM" --vault "$RO" --files "$RO/wiki/concepts/Hit.md" > /dev/null; r2=$?
python3 -B "$TM" --vault "$RO" --files "$RO/wiki/concepts/C.md" > /dev/null; r3=$?
python3 -B "$TM" --vault "$RO" --files "$RO/wiki/concepts/Absent.md" > /dev/null; r4=$?
python3 -B "$RO/.claude/skills/lint/check-tool-markup.py" --all > /dev/null; r5=$?
chmod -R u+w "$RO"
AFTER="$(manifest "$RO")"
eq "every mode runs against a chmod -R a-w vault copy (exits: --all, hit, clean, missing, default root)" "1 1 0 2 1" "$r1 $r2 $r3 $r4 $r5"
if [ "$(hashes "$AFTER")" -ge 5 ] && [ "$BEFORE" = "$AFTER" ]; then ok "the read-only copy's checksum manifest is unchanged ($(hashes "$AFTER") files)"
else no "the read-only copy's checksum manifest is unchanged  [$(hashes "$BEFORE") before, $(hashes "$AFTER") after]"; fi
# grep -c drops the file name on a single file, so count matches with -o | wc -l.
npat(){ local pat="$1"; shift; grep -oE -- "$pat" "$@" | wc -l | tr -d ' '; }
CTL_LINES="$(printf '%s\n' \
  'open("x", "w")' 'p.write_text(s)' 'os.remove(p)' 'os.unlink(p)' 'os.rename(a, b)' \
  'os.mkdir(d)' 'os.makedirs(d)' 'shutil.copy(a, b)' 'subprocess.run(c)' 'tempfile.mkdtemp()' \
  'print(x, file=open("f", "w"))' 'io.open(p, "w")' 'pathlib.Path(p)' 'q.write_bytes(b)' \
  'os.open(p, flags)' 'os.fdopen(fd)' 'os.system(c)' 'os.popen(c)' 'os.replace(a, b)' 'os.rmdir(d)')"
hits=0; dead=""
for pat in 'open\([^)]*["'"'"'][wax]' 'write_text' 'write_bytes' 'os\.remove' 'os\.unlink' \
           'os\.rename' 'os\.replace' 'os\.mkdir' 'os\.rmdir' 'makedirs' 'shutil\.' \
           'subprocess' 'tempfile' 'pathlib' 'io\.open' 'os\.open' 'os\.fdopen' \
           'os\.system' 'os\.popen' 'print\(.*file=open'; do
  hits=$((hits + $(npat "$pat" "$TM")))
  if [ "$(printf '%s\n' "$CTL_LINES" | npat "$pat" -)" -eq 0 ]; then dead="$dead $pat"; fi
done
if [ -n "$dead" ]; then no "every write pattern matches its own control line  [dead:$dead]"
elif [ "$hits" -eq 0 ]; then ok "no write pattern appears in the script source (20 patterns, each matched on its own control line)"
else no "no write pattern appears in the script source  [$hits hit(s)]"; fi
TAGPAT='</?(invoke|parameter|function_calls|function_results|content|antml:[A-Za-z_]+)([[:space:]/>]|$)'
lit=$(( $(npat "$TAGPAT" "$TM") + $(npat "$TAGPAT" "${BASH_SOURCE[0]}") + $(npat "$TAGPAT" "$LINT_TEXT") \
      + $(npat "$TAGPAT" "$DEEP_TEXT") + $(npat "$TAGPAT" "$STEP7_TEXT") + $(npat "$TAGPAT" "$BRIEF_TEXT") \
      + $(npat "$TAGPAT" "$CORE_TEXT") ))
ctl=$(printf '%s\n' "$(tc content)" | npat "$TAGPAT" -)
eq "no hand-written file carries a literal named tag (the script, this suite, the five caller texts; control 1)" "0-1" "$lit-$ctl"
END_H="$(manifest "$HOME_DIR")"
if [ "$(hashes "$END_H")" -ge 3 ] && [ "$START_H" = "$END_H" ]; then ok "the script home is byte-identical to its pre-run baseline ($(hashes "$END_H") files)"
else no "the script home is byte-identical to its pre-run baseline  [a run left a trace beside the scripts, or the manifest came back empty]"; fi

N=$((PASS + FAIL))
printf '\n'
if [ "$FAIL" -eq 0 ]; then printf 'PASS %d/%d\n' "$PASS" "$N"; else printf 'FAIL %d/%d\n' "$FAIL" "$N"; fi
[ "$FAIL" -eq 0 ]
