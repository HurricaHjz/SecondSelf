#!/bin/bash
# Suite for ted_cue_check.py: synthetic TED pages and captures, one case per exit class.
# Run: bash .claude/skills/ingest/test_ted_cue_check.sh   (exit 0 only when every case passes)
here="$(cd "$(dirname "$0")" && pwd)"
check="$here/ted_cue_check.py"
py="${PYTHON:-python3}"
d="$(mktemp -d)"
trap 'rm -rf "$d"' EXIT
fail=0; n=0

page() {  # page <file> <json cues array>
  printf '<html><head><script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"transcriptData":{"translation":{"paragraphs":[{"cues":%s}]}}}}}</script></head><body></body></html>\n' "$2" > "$1"
}

expect() {  # expect <name> <want exit> <want text> <page> <capture>
  n=$((n+1))
  out="$("$py" -I "$check" "$4" "$5")"; got=$?
  if [ "$got" = "$2" ] && printf '%s\n' "$out" | grep -qF -- "$3"; then
    echo "PASS $1 (exit $got)"
  else
    echo "FAIL $1: exit $got, want $2 with '$3'; output: $out"; fail=$((fail+1))
  fi
}

page "$d/p3.html" '[{"text":"Most people come here,"},{"text":"because they have\nsucceeded."},{"text":"(Laughter)"}]'
printf 'MOST people come here -- because they HAVE succeeded! (laughter)\n' > "$d/full.md"
printf 'Most people come here, because they have succeeded.\n' > "$d/short.md"
printf '<html><body>no data here</body></html>\n' > "$d/plain.html"
page "$d/p0.html" '[]'
: > "$d/empty.md"

expect all-present        0 'missing 0'                 "$d/p3.html"    "$d/full.md"
expect last-line-missing  3 'MISSING: (Laughter)'       "$d/p3.html"    "$d/short.md"
expect no-transcript-data 2 'PROBE FAILED: no transcript data' "$d/plain.html" "$d/full.md"
expect empty-transcript   2 'PROBE FAILED: the TED page carries an empty transcript' "$d/p0.html" "$d/full.md"
expect empty-capture      2 'PROBE FAILED: the capture is empty' "$d/p3.html" "$d/empty.md"
expect missing-file       2 'PROBE FAILED: cannot read' "$d/p3.html"    "$d/nonexistent.md"

# Review round 1 (14 Oct 2026): partial-word matches and malformed cues must not pass.
page "$d/pcan.html" '[{"text":"We can."}]'
printf 'We cannot.\n' > "$d/cannot.md"
page "$d/phe.html" '[{"text":"he speaks"}]'
printf 'she speaks\n' > "$d/she.md"
page "$d/pnotext.html" '[{"text":"First line."},{"other":"Lost final line."}]'
page "$d/pnull.html" '[{"text":"First line."},{"text":null}]'
page "$d/pint.html" '[{"text":"First line."},{"text":7}]'
printf 'First line.\n' > "$d/first.md"
expect partial-word-cannot 3 'MISSING: We can.'        "$d/pcan.html"    "$d/cannot.md"
expect partial-word-she    3 'MISSING: he speaks'      "$d/phe.html"     "$d/she.md"
expect cue-without-text    2 'carry no text'           "$d/pnotext.html" "$d/first.md"
expect cue-text-null       2 'carry no text'           "$d/pnull.html"   "$d/first.md"
expect cue-text-integer    2 'carry no text'           "$d/pint.html"    "$d/first.md"

# Review round 2 (14 Oct 2026): contractions must not match, blank cues are a broken premise.
printf "We can't.\n" > "$d/cant.md"
printf 'We can\xe2\x80\x99t.\n' > "$d/cant-curly.md"
printf 'WE CAN!\n' > "$d/canbang.md"
page "$d/pim.html" '[{"text":"I\u0027m here."}]'
printf 'I\xe2\x80\x99m here\n' > "$d/im-curly.md"
page "$d/pblank.html" '[{"text":"First line."},{"text":""}]'
page "$d/pspace.html" '[{"text":"First line."},{"text":"   "}]'
page "$d/pnote.html" '[{"text":"First line."},{"text":"\u266a"}]'
expect contraction-straight 3 'MISSING: We can.'      "$d/pcan.html"   "$d/cant.md"
expect contraction-curly    3 'MISSING: We can.'      "$d/pcan.html"   "$d/cant-curly.md"
expect harmless-punctuation 0 'missing 0'             "$d/pcan.html"   "$d/canbang.md"
expect apostrophe-styles    0 'missing 0'             "$d/pim.html"    "$d/im-curly.md"
expect blank-cue            2 'carry no text'         "$d/pblank.html" "$d/first.md"
expect whitespace-cue       2 'carry no text'         "$d/pspace.html" "$d/first.md"
expect symbol-only-cue      0 'TED cues 1 · missing 0' "$d/pnote.html"  "$d/first.md"

echo "suite: $n cases · $((n-fail)) pass · $fail fail"
[ "$fail" = 0 ]
