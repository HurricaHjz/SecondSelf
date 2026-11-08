#!/bin/bash
# test_brief_preflight.sh — brief_preflight.py, the parallel ingest's brief check (design extension
# 2026-09-13, part 4): a mangled-path mechanism replayed on a fixture (must fail on (a) and (c)), the
# correctly filled twin (must pass), one leg per check, the premise failures, and the stdout-only proof.
# Every fixture sits under one mktemp -d in /tmp and is removed on exit; the vault is never touched.
# Usage: bash test_brief_preflight.sh [path/to/brief_preflight.py]   (default: beside this script)
#   LANE_FENCE=<lane-fence.py>  the fence the real-fence leg imports (default: ../delegate/lane-fence.py).
#   The fence sanctions every /tmp path as a write root, so a fixture append can never be denied by it:
#   the deny leg uses a stub of the same shape, and the real fence's deny is the script's own same-run
#   control, which queries a root outside /tmp on every run with a headless lane.
set -u
export LC_ALL=C
HERE=$(cd "$(dirname "$0")" && pwd)
S=${1:-"$HERE/brief_preflight.py"}
PY=${PYTHON:-python3}
FENCE=${LANE_FENCE:-"$HERE/../delegate/lane-fence.py"}
T=$(mktemp -d "${TMPDIR:-/tmp}/brief-preflight-suite.XXXXXX")
trap 'chmod -R u+w "$T"; rm -rf "$T"' EXIT HUP INT TERM
PASS=0; FAIL=0
ok() { PASS=$((PASS+1)); echo "ok   $1"; }
no() { FAIL=$((FAIL+1)); echo "FAIL $1"; }
has() { case "$1" in *"$2"*) return 0;; esac; return 1; }
manifest() { find "$1" -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum | LC_ALL=C sort; }
HOME_BEFORE="$(manifest "$HERE")"

V="$T/vault"; H="$T/home"; R="$H/.agent-wiki/ingest-runs"; B="$T/briefs"
mkdir -p "$V/wiki/sources" "$V/raw" "$R" "$B"
cat > "$V/wiki/index.md" <<'IDXEOF'
---
title: Index
---
# Index
## Sources
- [[paper-a]] — a paper
## Entities
- [[Example Lab]] — a lab
## Tools
- [[markitdown]] — a converter
## Models
- [[GPT]] — a model family
- [[Qwen]] — a model family
## Benchmarks
- [[AIME]] — a maths benchmark
## Concepts
- [[Calibration]] — a concept
IDXEOF
printf '# Paper A\n\nBody.\n' > "$V/raw/paper-a.md"
OPEN='{"ts":"2026-01-01T10:00+0000","event":"run_open","run":"run-fx-1","pacing":"parallel","inbox":[]}'
PRE='{"ts":"2026-01-01T10:05+0000","event":"preflight","run":"run-fx-1","lane":"head","briefs":2,"failures":2,"controls":"ok"}'
printf '%s\n%s\n' "$OPEN" "$PRE" > "$R/run-fx-1.jsonl"
printf '%s\n' "$OPEN" > "$R/run-fx-2.jsonl"
printf '%s\n%s\n' "$PRE" "$OPEN" > "$R/run-fx-3.jsonl"
printf 'not json\n' > "$R/run-fx-4.jsonl"

# The template filled correctly: the ledger under the fixture home, vault-relative tokens that resolve.
cat > "$B/L1.md" <<'BRIEFEOF'
You are wiki-compile (definition: .claude/agents/wiki-compile.md), lane L1 of run
run-fx-1 · model opus · effort xhigh.

SCOPE
- Reading list: your assigned source raw/paper-a.md + the index slice ~/.agent-wiki/ingest-runs/run-fx-1-index-L1.txt
- File whitelist (create/edit): wiki/sources/paper-a.md
LEDGER & CLAIMS
- Run ledger ~/.agent-wiki/ingest-runs/run-fx-1.jsonl: shell-append only (`printf '%s\n' '<json>' >>`)
BRIEFEOF
cat > "$B/V1.md" <<'BRIEFEOF'
You are verifier (definition: .claude/agents/verifier.md), lane V1 of run
run-fx-1 · model opus · effort high — the ingest Verify step, read-only.

SCOPE
- Raw: raw/paper-a.md
- M0 outputs: ~/.agent-wiki/ingest-runs/run-fx-1-m0-L1.txt
BRIEFEOF
run() { OUT=$(env HOME="$H" "$PY" -B "$S" --vault "$V" "$@" 2>&1); RC=$?; }

echo '--- must not fire: the correctly filled template ---'
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1.md" "$B/V1.md"
if [ $RC -eq 0 ] && has "$OUT" "summary: briefs 2 · failed 0 ·" && ! has "$OUT" "FAIL ("; then ok "clean brief pair: exit 0, failed 0, no FAIL line"; else no "clean brief pair: rc=$RC: $OUT"; fi
if has "$OUT" "controls: (a) absent parent caught"; then ok "clean run: the synthetic absent-parent control failed on the same run"; else no "clean run: no control line: $OUT"; fi

echo '--- must fire: a head-side rewrite replayed on the fixture ---'
"$PY" - "$V" "$H" "$B/L1.md" "$B/L1-mangled.md" <<'PYEOF'
import re, sys
vault, home, src, dst = sys.argv[1:5]
text = open(src, encoding="utf-8").read().replace("~/", home + "/")
# vault-relative raw/ and wiki/ rewritten to the vault's absolute path, with a look-behind that admits
# the `-` of `.agent-wiki/` (a head-side rewrite's shape)
text = re.sub(r"(?<![\w/.])(raw|wiki)/", vault + r"/\1/", text)
with open(dst, "w", encoding="utf-8") as fh:
    fh.write(text)
PYEOF
MANGLED="$H/.agent-$V/wiki/ingest-runs/run-fx-1.jsonl"
if grep -qF "$MANGLED" "$B/L1-mangled.md"; then ok "replay premise: the ledger token reads <home>/.agent-<vault>/wiki/ingest-runs/..."; else no "replay premise: mangled token absent from the replayed brief"; fi
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-mangled.md"
if [ $RC -eq 1 ] && has "$OUT" "FAIL (a) L1 line 8: parent directory" && has "$OUT" "$MANGLED"; then ok "replay: fails (a) on the mangled ledger token"; else no "replay (a): rc=$RC: $OUT"; fi
if has "$OUT" "FAIL (c) L1 not proven: (a) or (b) failed first"; then ok "replay: fails (c), unproven because (a) failed first"; else no "replay (c): $OUT"; fi
if has "$OUT" "FAIL (b) L1 ledger path $MANGLED differs"; then ok "replay: (b) also fires, the mangled path differing from the run's ledger"; else no "replay (b): $OUT"; fi
if has "$OUT" "controls: (a) absent parent caught"; then ok "replay: the controls line printed on the same run"; else no "replay: no controls line"; fi
if [ ! -e "$H/.agent-" ]; then ok "replay: nothing was created at the mangled path (no append attempted)"; else no "replay: $H/.agent- exists"; fi

echo '--- (a) unfilled slots ---'
sed 's#run-fx-1-index-L1.txt#run-<run>-index-<lane>.txt#; s#wiki/sources/paper-a.md#{{vault root}}/wiki/sources/paper-a.md#' "$B/L1.md" > "$B/L1-slot.md"
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-slot.md"
if [ $RC -eq 1 ] && has "$OUT" "FAIL (a) L1 line 5: unfilled slot: ~/.agent-wiki/ingest-runs/run-<run>-index-<lane>.txt"; then ok "(a) an angle slot in a path token fails"; else no "(a) angle slot: rc=$RC: $OUT"; fi
if has "$OUT" "unfilled slot: {{vault_root}}/wiki/sources/paper-a.md"; then ok "(a) a curly slot holding a space fails as one token"; else no "(a) curly slot: $OUT"; fi

echo '--- (b) one ledger path ---'
sed 's#run-fx-1.jsonl#run-fx-2.jsonl#; s#lane L1 of run#lane L3 of run#' "$B/L1.md" > "$B/L3.md"
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1.md" "$B/L3.md"
if [ $RC -eq 1 ] && has "$OUT" "FAIL (b) L3 ledger path ~/.agent-wiki/ingest-runs/run-fx-2.jsonl differs" && ! has "$OUT" "FAIL (b) L1" && has "$OUT" "failed 1 ·"; then ok "(b) a brief naming another run's ledger fails; its sibling passes"; else no "(b): rc=$RC: $OUT"; fi
if has "$OUT" "FAIL (c) L3 not proven"; then ok "(b) the differing brief gets no (c) read at its path"; else no "(b) then (c): $OUT"; fi
sed '/Run ledger/d' "$B/L1.md" > "$B/L1-noledger.md"
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-noledger.md"
if [ $RC -eq 1 ] && has "$OUT" "FAIL (b) L1 a wiki-compile brief carries no run-ledger path"; then ok "(b) a compile brief with no ledger path fails"; else no "(b) no ledger: rc=$RC: $OUT"; fi

echo '--- (c) the append proof ---'
sed 's#run-fx-1#run-fx-2#g' "$B/L1.md" > "$B/L1-run2.md"
run --ledger "$R/run-fx-2.jsonl" --in-session all "$B/L1-run2.md"
if [ $RC -eq 1 ] && has "$OUT" "FAIL (c) L1 no preflight event after run_open (line 1) at ~/.agent-wiki/ingest-runs/run-fx-2.jsonl" && ! has "$OUT" "FAIL (a)" && ! has "$OUT" "FAIL (b)"; then ok "(c) no preflight event: fails with (a) and (b) passing"; else no "(c) missing event: rc=$RC: $OUT"; fi
if has "$OUT" "NEXT: (a), (b), (d) and (e) pass for every brief; append the preflight event at ~/.agent-wiki/ingest-runs/run-fx-2.jsonl"; then ok "(c) the NEXT line names the brief's literal path for the head's append"; else no "(c) NEXT line: $OUT"; fi
sed 's#run-fx-1#run-fx-3#g' "$B/L1.md" > "$B/L1-run3.md"
run --ledger "$R/run-fx-3.jsonl" --in-session all "$B/L1-run3.md"
if [ $RC -eq 1 ] && has "$OUT" "FAIL (c) L1 no preflight event after run_open (line 2)"; then ok "(c) a preflight event before run_open does not count"; else no "(c) order: rc=$RC: $OUT"; fi

echo '--- (d) the fence ---'
printf 'command:\n  claude -p\nenvironment:\n  LLM_WIKI_LANE=1\n  LLM_WIKI_LANE_GRANTS=%s:%s\n  LLM_WIKI_LANE_WRITES=%s\n' "$V" "$R" "$R" > "$T/dry-ok.txt"
printf 'command:\n  claude -p\nenvironment:\n  LLM_WIKI_LANE=1\n  LLM_WIKI_LANE_GRANTS=%s:%s\n  LLM_WIKI_LANE_WRITES=%s\n' "$V" "$R" "$V/wiki" > "$T/dry-nowrite.txt"
: > "$T/dry-refused.txt"
if [ -f "$FENCE" ]; then
  run --ledger "$R/run-fx-1.jsonl" --fence "$FENCE" --dry-run L1="$T/dry-ok.txt" --in-session V1 "$B/L1.md" "$B/V1.md"
  if [ $RC -eq 0 ] && has "$OUT" "fence queried 1 · headless 1 · in-session 1" && has "$OUT" "(d) the pinned 'allow' observed inside the write roots and deny outside them"; then ok "(d) real fence: the headless lane's append is allowed, and the same-run control saw allow and deny"; else no "(d) real fence: rc=$RC: $OUT"; fi
else
  no "(d) real fence: no lane-fence.py at $FENCE (set LANE_FENCE)"
fi
cat > "$T/stub-fence.py" <<'PYEOF'
import os
def check(event, grants, writes, head=False, network=None):
    target = os.path.realpath(os.path.expanduser(event["tool_input"]["command"].rsplit(">>", 1)[-1].strip()))
    if any(target == w or target.startswith(w.rstrip("/") + "/") for w in writes):
        return ("allow", "lane-fence: within grants")
    return ("deny", "lane-fence: stub, outside the write roots")
PYEOF
run --ledger "$R/run-fx-1.jsonl" --fence "$T/stub-fence.py" --dry-run L1="$T/dry-nowrite.txt" "$B/L1.md"
if [ $RC -eq 1 ] && has "$OUT" "FAIL (d) L1 check() answers deny for the lane's own append at ~/.agent-wiki/ingest-runs/run-fx-1.jsonl: lane-fence: stub, outside the write roots"; then ok "(d) a deny for the lane's own append fails the brief"; else no "(d) deny: rc=$RC: $OUT"; fi
run --ledger "$R/run-fx-1.jsonl" --fence "$T/stub-fence.py" --dry-run L1="$T/dry-nowrite.txt" "$B/L1-mangled.md"
if [ $RC -eq 1 ] && has "$OUT" "FAIL (d) L1 not proven: (a) or (b) failed first" && has "$OUT" "fence queried 0"; then ok "(d) not queried at an unproven path, and counted failed"; else no "(d) unproven: rc=$RC: $OUT"; fi
printf 'def check(event, grants, writes, head=False, network=None):\n    return ("silent", "")\n' > "$T/silent-fence.py"
run --ledger "$R/run-fx-1.jsonl" --fence "$T/silent-fence.py" --dry-run L1="$T/dry-ok.txt" "$B/L1.md"
if [ $RC -eq 2 ] && has "$OUT" "PROBE FAILED: a same-run control did not behave: (d) an append inside the write roots did not get the pinned 'allow'"; then ok "(d) a check() whose answers changed shape stops the run, exit 2"; else no "(d) changed shape: rc=$RC: $OUT"; fi
run --ledger "$R/run-fx-1.jsonl" --fence "$T/stub-fence.py" --dry-run L1="$T/dry-refused.txt" "$B/L1.md"
if [ $RC -eq 2 ] && has "$OUT" "carries no LLM_WIKI_LANE_GRANTS line: the wrapper refused"; then ok "(d) premise: a dry-run refusal (empty output) is exit 2"; else no "(d) refusal: rc=$RC: $OUT"; fi
run --ledger "$R/run-fx-1.jsonl" "$B/L1.md"
if [ $RC -eq 2 ] && has "$OUT" "lane L1 is named neither by --dry-run"; then ok "(d) premise: a lane named neither headless nor in-session is exit 2"; else no "(d) unnamed lane: rc=$RC: $OUT"; fi
run --ledger "$R/run-fx-1.jsonl" --fence "$T/no-such-fence.py" --dry-run L1="$T/dry-ok.txt" "$B/L1.md"
if [ $RC -eq 2 ] && has "$OUT" "does not import"; then ok "(d) premise: a fence that does not import is exit 2"; else no "(d) no fence: rc=$RC: $OUT"; fi
# The verify lane's open and close are the head's to write (the verifier definition bans the lane's
# own append), so a headless verify brief whose lane cannot append passes (d); a compile brief cannot.
{ cat "$B/V1.md"; printf -- '- Run ledger, read for the slices: ~/.agent-wiki/ingest-runs/run-fx-1.jsonl\n'; } > "$B/V2.md"
run --ledger "$R/run-fx-1.jsonl" --fence "$T/stub-fence.py" --dry-run V1="$T/dry-nowrite.txt" "$B/V2.md"
if [ $RC -eq 0 ] && has "$OUT" "(d) exempt: a verify brief" && has "$OUT" "fence queried 0" && has "$OUT" "(d) exempt 1" && ! has "$OUT" "FAIL (d)"; then ok "(d) K1a12a51f a headless verify brief whose lane cannot append passes, exempt, its fence not asked"; else no "(d) K1a12a51f verify brief exempt: rc=$RC: $OUT"; fi
run --ledger "$R/run-fx-1.jsonl" --fence "$T/stub-fence.py" --dry-run L1="$T/dry-nowrite.txt" --dry-run V1="$T/dry-nowrite.txt" "$B/L1.md" "$B/V2.md"
if [ $RC -eq 1 ] && has "$OUT" "FAIL (d) L1 check() answers deny for the lane's own append" && ! has "$OUT" "FAIL (d) V1" && has "$OUT" "fence queried 1" && has "$OUT" "failed 1 ·"; then ok "(d) K1a12a51f a compile brief that cannot append still fails (d) on the same run, beside the exempt verify brief"; else no "(d) K1a12a51f compile beside verify: rc=$RC: $OUT"; fi

echo '--- (e) index sections ---'
{ cat "$B/L1.md"; printf -- '- Also read wiki/index.md in section mode for the `## Entities` and `## Models` headings\n'; } > "$B/L1-named.md"
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-named.md"
if [ $RC -eq 1 ] && has "$OUT" "FAIL (e) L1 line 9 names index sections \`## Entities\`, \`## Models\`"; then ok "(e) a reading list naming index sections fails"; else no "(e) named: rc=$RC: $OUT"; fi
{ cat "$B/L1.md"; printf -- '- [[GPT]] — a model family\n- [[Qwen]] — a model family\n'; } > "$B/L1-pasted.md"
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-pasted.md"
if [ $RC -eq 1 ] && has "$OUT" "FAIL (e) L1 carries every entry line of index section \`## Models\` (2 lines)"; then ok "(e) a brief carrying one section whole fails"; else no "(e) pasted: rc=$RC: $OUT"; fi
{ cat "$B/L1.md"; printf -- '- [[GPT]] — a model family\n'; } > "$B/L1-oneline.md"
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-oneline.md"
if [ $RC -eq 0 ] && ! has "$OUT" "FAIL (e)"; then ok "(e) one line of a two-line section is not the section whole"; else no "(e) one line: rc=$RC: $OUT"; fi

echo '--- review: quoted paths holding a space, and a section named on the line after the index ---'
mkdir -p "$V/raw/with space"
{ cat "$B/L1.md"; printf -- '- Also read "%s/raw/valid space/missing/thing.md"\n' "$V"; } > "$B/L1-quoted-missing.md"
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-quoted-missing.md"
if [ $RC -eq 1 ] && has "$OUT" "FAIL (a) L1 line 9: parent directory $V/raw/valid space/missing does not exist: $V/raw/valid space/missing/thing.md"; then ok "N8-C1 a quoted path holding a space is tested whole, and its missing parent fails (a)"; else no "N8-C1 quoted path, missing parent: rc=$RC: $OUT"; fi
{ cat "$B/L1.md"; printf -- '- Also read "%s/raw/with space/thing.md"\n' "$V"; } > "$B/L1-quoted-valid.md"
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-quoted-valid.md"
if [ $RC -eq 0 ] && has "$OUT" "failed 0 ·" && has "$OUT" "ampersand paths tested whole"; then ok "N8-C2 a valid quoted path holding a space passes with its control"; else no "N8-C2 quoted path, valid: rc=$RC: $OUT"; fi
mkdir -p "$V/A & B"
{ cat "$B/L1.md"; printf -- '- Also read "%s/A & B/missing/file.md"\n' "$V"; } > "$B/L1-ampersand-missing.md"
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-ampersand-missing.md"
if [ $RC -eq 1 ] && has "$OUT" "FAIL (a) L1 line 9: parent directory $V/A & B/missing does not exist: $V/A & B/missing/file.md"; then ok "N8-F1 quoted ampersand path with missing parent fails whole (truncated parent exists)"; else no "N8-F1 quoted ampersand: rc=$RC: $OUT"; fi
{ cat "$B/L1.md"; printf -- '- Also read "%s/A & B/file.md"\n' "$V"; } > "$B/L1-ampersand-valid.md"
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-ampersand-valid.md"
if [ $RC -eq 0 ] && has "$OUT" "failed 0 ·" && has "$OUT" "ampersand paths tested whole"; then ok "N8-C3 valid quoted ampersand path passes with its control"; else no "N8-C3 valid ampersand: rc=$RC: $OUT"; fi
for quote in "'" '`'; do
  { cat "$B/L1.md"; printf -- '- Also read %s%s/A & B/missing/file.md%s\n' "$quote" "$V" "$quote"; } > "$B/L1-ampersand-other.md"
  run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-ampersand-other.md"
  if [ $RC -eq 1 ] && has "$OUT" "parent directory $V/A & B/missing does not exist: $V/A & B/missing/file.md"; then ok "N8-F2 missing ampersand parent fails with quote $quote"; else no "N8-F2 quote $quote: rc=$RC: $OUT"; fi
  { cat "$B/L1.md"; printf -- '- Also read %s%s/A & B/file.md%s\n' "$quote" "$V" "$quote"; } > "$B/L1-ampersand-other.md"
  run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-ampersand-other.md"
  if [ $RC -eq 0 ] && has "$OUT" "failed 0 ·" && has "$OUT" "ampersand paths tested whole"; then ok "N8-C4 valid ampersand parent passes with quote $quote and control"; else no "N8-C4 quote $quote: rc=$RC: $OUT"; fi
done

echo '--- pass-three quote and backtick regressions ---'
for quote in '"' "'"; do
  { cat "$B/L1.md"; printf -- '%s %s%s/raw/with space/missing/file.md%s; %s\n' "- Read the owner's" "$quote" "$V" "$quote" "it's absent."; } > "$B/L1-prose-missing.md"
  run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-prose-missing.md"
  if [ $RC -eq 1 ] && has "$OUT" "parent directory $V/raw/with space/missing does not exist: $V/raw/with space/missing/file.md"; then ok "N1-M prose apostrophes cannot hide missing path with quote $quote"; else no "N1-M quote $quote: rc=$RC: $OUT"; fi
  { cat "$B/L1.md"; printf -- '%s %s%s/raw/with space/file.md%s; %s\n' "- Read the owner's" "$quote" "$V" "$quote" "it's present."; } > "$B/L1-prose-valid.md"
  run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-prose-valid.md"
  if [ $RC -eq 0 ] && has "$OUT" "failed 0 ·" && has "$OUT" "prose apostrophes ignored"; then ok "N1-C prose apostrophes preserve valid path with quote $quote and control"; else no "N1-C quote $quote: rc=$RC: $OUT"; fi
done
{ cat "$B/L1.md"; printf -- '%s "%s/raw/with space/missing/file.md"%s\n' "- Read 'the owner's" "$V" "'; it's absent."; } > "$B/L1-nested-missing.md"
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-nested-missing.md"
if [ $RC -eq 1 ] && has "$OUT" "parent directory $V/raw/with space/missing does not exist"; then ok "N1-N nested double-quoted missing path outranks surrounding single quotes"; else no "N1-N nested quotes: rc=$RC: $OUT"; fi
{ cat "$B/L1.md"; printf -- '%s "%s/raw/with space/file.md"%s\n' "- Read 'the owner's" "$V" "'; it's present."; } > "$B/L1-nested-valid.md"
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-nested-valid.md"
if [ $RC -eq 0 ] && has "$OUT" "failed 0 ·" && has "$OUT" "prose apostrophes ignored"; then ok "N1-V nested double-quoted valid path passes with control"; else no "N1-V nested quotes: rc=$RC: $OUT"; fi
for prefix in "$V/" './' '../vault/'; do
  { cat "$B/L1.md"; printf -- '- Read `%sA & B/missing/file.md`\n' "$prefix"; } > "$B/L1-bare-missing.md"
  run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-bare-missing.md"
  if [ $RC -eq 1 ] && has "$OUT" "A & B/missing does not exist: ${prefix}A & B/missing/file.md"; then ok "N2-M original bare backtick missing path fails whole ($prefix)"; else no "N2-M bare backticks: rc=$RC: $OUT"; fi
  { cat "$B/L1.md"; printf -- '- Read `%sA & B/file.md`\n' "$prefix"; } > "$B/L1-bare-valid.md"
  run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-bare-valid.md"
  if [ $RC -eq 0 ] && has "$OUT" "failed 0 ·" && has "$OUT" "bare backtick paths kept whole"; then ok "N2-C original bare backtick valid path passes with control ($prefix)"; else no "N2-C bare backticks: rc=$RC: $OUT"; fi
done

echo '--- quoted literals and command spans: critic findings 1 and 3 ---'
run --help
FOLD_HELP=$(printf '%s\n' "$OUT" | tr '\n' ' ')
if [ $RC -eq 0 ] && has "$FOLD_HELP" "Double/single-quoted paths stay whole" && has "$FOLD_HELP" "backtick command separators split paths"; then ok "F13-H help states literal-quote and command-span behaviour"; else no "F13-H help: rc=$RC: $OUT"; fi
mkdir -p "$V/A & B -draft" "$V/bin"
for quote in '"' "'"; do
  { cat "$B/L1.md"; printf -- '- Read %s%s/A & B -draft/missing/file.md%s\n' "$quote" "$V" "$quote"; } > "$B/L1-draft-missing.md"
  run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-draft-missing.md"
  if [ $RC -eq 1 ] && has "$OUT" "parent directory $V/A & B -draft/missing does not exist: $V/A & B -draft/missing/file.md"; then ok "F1-M quoted -draft missing parent fails whole with quote $quote"; else no "F1-M quote $quote: rc=$RC: $OUT"; fi
  { cat "$B/L1.md"; printf -- '- Read %s%s/A & B -draft/file.md%s\n' "$quote" "$V" "$quote"; } > "$B/L1-draft-valid.md"
  run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-draft-valid.md"
  if [ $RC -eq 0 ] && has "$OUT" "failed 0 ·" && has "$OUT" "quoted -draft paths tested whole"; then ok "F1-C quoted -draft valid parent passes with quote $quote and control"; else no "F1-C quote $quote: rc=$RC: $OUT"; fi
  FOLD_LITERAL_ROOT="$V/"'A & B -draft | alt; $name > end'
  mkdir -p "$FOLD_LITERAL_ROOT"
  { cat "$B/L1.md"; printf -- '- Read %s%s/file.md%s\n' "$quote" "$FOLD_LITERAL_ROOT" "$quote"; } > "$B/L1-operators-valid.md"
  run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-operators-valid.md"
  if [ $RC -eq 0 ] && has "$OUT" "failed 0 ·" && has "$OUT" "quoted -draft paths tested whole"; then ok "F1-L quoted shell punctuation remains literal with quote $quote"; else no "F1-L quote $quote: rc=$RC: $OUT"; fi
  { cat "$B/L1.md"; printf -- '- Read %s%s/missing/file.md%s\n' "$quote" "$FOLD_LITERAL_ROOT" "$quote"; } > "$B/L1-operators-missing.md"
  run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-operators-missing.md"
  if [ $RC -eq 1 ] && has "$OUT" "parent directory $FOLD_LITERAL_ROOT/missing does not exist"; then ok "F1-P quoted punctuation missing parent fails with quote $quote"; else no "F1-P quote $quote: rc=$RC: $OUT"; fi
done
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1.md"
FOLD_BASE_TOKENS=$(printf '%s\n' "$OUT" | sed -n 's/.*path tokens \([0-9][0-9]*\).*/\1/p')
if [ $RC -eq 0 ] && [ -n "$FOLD_BASE_TOKENS" ] && has "$OUT" "command spans split"; then
  ok "F3-P command test baseline has path tokens and same-run separator controls"
  FOLD_COMMAND_TOKENS=$((FOLD_BASE_TOKENS + 2)) # the two command paths added below
  for separator in '&&' '&' '|' '||' ';'; do
    { cat "$B/L1.md"; printf -- '- Check `%s/bin/check %s %s/bin/compile`\n' "$V" "$separator" "$V"; } > "$B/L1-command-valid.md"
    run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-command-valid.md"
    if [ $RC -eq 0 ] && has "$OUT" "path tokens $FOLD_COMMAND_TOKENS ·" && has "$OUT" "failed 0 ·" && has "$OUT" "command spans split"; then ok "F3-C separate command paths pass for $separator with control"; else no "F3-C $separator: rc=$RC: $OUT"; fi
    { cat "$B/L1.md"; printf -- '- Check `%s/bin/check%s%s/bin/compile`\n' "$V" "$separator" "$V"; } > "$B/L1-command-tight.md"
    run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-command-tight.md"
    if [ $RC -eq 0 ] && has "$OUT" "path tokens $FOLD_COMMAND_TOKENS ·" && has "$OUT" "command spans split"; then ok "F3-T command paths split without spaces for $separator"; else no "F3-T $separator: rc=$RC: $OUT"; fi
    { cat "$B/L1.md"; printf -- '- Check `%s/bin/check %s %s/bin/missing/compile`\n' "$V" "$separator" "$V"; } > "$B/L1-command-missing.md"
    run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-command-missing.md"
    if [ $RC -eq 1 ] && has "$OUT" "parent directory $V/bin/missing does not exist: $V/bin/missing/compile"; then ok "F3-M second command path missing parent fails for $separator"; else no "F3-M $separator: rc=$RC: $OUT"; fi
  done
  { cat "$B/L1.md"; printf -- '- Check `%s/A & B/file.md && "%s/bin/compile"`\n' "$V" "$V"; } > "$B/L1-command-mixed.md"
  run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-command-mixed.md"
  if [ $RC -eq 0 ] && has "$OUT" "path tokens $FOLD_COMMAND_TOKENS ·" && has "$OUT" "bare backtick paths kept whole"; then ok "N2-Q bare ampersand component and quoted command target both pass"; else no "N2-Q mixed paths: rc=$RC: $OUT"; fi
  { cat "$B/L1.md"; printf -- '- Check `%s/A & B/missing/file.md && "%s/bin/compile"`\n' "$V" "$V"; } > "$B/L1-command-mixed.md"
  run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-command-mixed.md"
  if [ $RC -eq 1 ] && has "$OUT" "A & B/missing does not exist: $V/A & B/missing/file.md"; then ok "N2-F missing bare path remains whole before a quoted command target"; else no "N2-F mixed paths: rc=$RC: $OUT"; fi
  { cat "$B/L1.md"; printf -- '- Check `"%s/bin/check" & %s/A & B/file.md`\n' "$V" "$V"; } > "$B/L1-command-mixed.md"
  run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-command-mixed.md"
  if [ $RC -eq 0 ] && has "$OUT" "path tokens $FOLD_COMMAND_TOKENS ·" && has "$OUT" "bare backtick paths kept whole"; then ok "N2-R quoted command target and bare ampersand component both pass"; else no "N2-R mixed paths: rc=$RC: $OUT"; fi
  { cat "$B/L1.md"; printf -- '- Check `"%s/bin/check" & %s/A & B/missing/file.md`\n' "$V" "$V"; } > "$B/L1-command-mixed.md"
  run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-command-mixed.md"
  if [ $RC -eq 1 ] && has "$OUT" "A & B/missing does not exist: $V/A & B/missing/file.md"; then ok "N2-S missing bare path remains whole after a quoted command target"; else no "N2-S mixed paths: rc=$RC: $OUT"; fi
else
  no "F3-P no valid command-test baseline: rc=$RC: $OUT"
fi
{ cat "$B/L1.md"; printf -- '- Also read wiki/index.md in section mode for\n  ## Models\n'; } > "$B/L1-nextline.md"
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1-nextline.md"
if [ $RC -eq 1 ] && has "$OUT" "FAIL (e) L1 line 10 names index section \`## Models\`"; then ok "a section named on the line after wiki/index.md fails (e)"; else no "section on the next line: rc=$RC: $OUT"; fi
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1.md"
if [ $RC -eq 0 ] && has "$OUT" "failed 0 ·"; then ok "the index-slice brief still passes"; else no "index-slice brief: rc=$RC: $OUT"; fi

echo '--- column-collapsed table clause in generated briefs ---'
if "$PY" -B - "$HERE" "$T" <<'PYTABLETEST' > "$T/table-results.txt"
import re, subprocess, sys
from pathlib import Path
here, temp = map(Path, sys.argv[1:])
templates = here.parent / "delegate-templates"
if not templates.is_dir():
    templates = here.parent / "delegate/templates"
clause = ("A cell from a column-collapsed table is quoted only with its row and column labels "
          "verified in the raw, never with a superlative or a row label the table does not print.")
def normalise(text):
    return " ".join(text.split())
def carries_clause(text):
    return clause in normalise(text)
def leg(name, passed):
    print(("OK " if passed else "FAIL ") + name)
for name in ("brief-compile.md", "brief-ingest-verify.md"):
    template = (templates / name).read_text()
    # Use the actual spawn body, remove spawner comments and fill every curly slot.
    body = template.split("\n```\n")[1]
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    generated = re.sub(r"\{\{.*?\}\}", lambda match: "fixture", body, flags=re.S)
    path = temp / ("generated-" + name)
    path.write_text(generated)
    generated = path.read_text()
    leg("R2-generated-" + name, "{{" not in generated and carries_clause(generated))
    removed = generated.replace(clause, "")
    leg("R2-absence-" + name, removed != generated and not carries_clause(removed))
    for required in ("row and column labels", "verified in the raw", "superlative", "row label the table does not print"):
        leg("R2-missing-" + required + "-" + name,
            not carries_clause(generated.replace(required, "omitted")))
    if name == "brief-ingest-verify.md":
        leg("R2-named-check-and-spot-checks", "Named check — column-collapsed table labels" in generated
            and "spot-check quoted cells against the raw" in generated
            and "whole-raw confirmation" in generated)
leg("R2-research-template", carries_clause((here / "SKILL.md").read_text()))
leg("R2-empty-premise", not carries_clause("") and carries_clause(clause))
asserted = '  universal over them ("every row", "the only method").'
result = subprocess.run(["grep", "-qxF", asserted, str(templates / "brief-compile.md")], capture_output=True, text=True)
leg("F5-original-physical-line", result.returncode == 0 and not result.stderr)
mutated = (templates / "brief-compile.md").read_text().replace(asserted + "\n", asserted + " appended clause\n")
result = subprocess.run(["grep", "-qxF", asserted], input=mutated, capture_output=True, text=True)
leg("F5-appended-clause-control", result.returncode == 1 and not result.stderr)
skill = (here / "SKILL.md").read_text()
leg("F7-table-rule-all-depths", "\n**Table quotations, all depths:** " + clause in skill
    and "\n  - **Table quotations, all depths:**" not in skill)
PYTABLETEST
then
  while IFS=' ' read -r result label; do
    if [ "$result" = OK ]; then ok "$label"; else no "$label"; fi
  done < "$T/table-results.txt"
else
  cat "$T/table-results.txt"
  no 'R2 generated-brief harness failed'
fi

echo '--- batch clauses: fidelity, verifier events and the chunked index read ---'
if "$PY" -B - "$HERE" "$T" <<'PYBATCHTEXT' > "$T/batch-text-results.txt"
import re, sys
from pathlib import Path
here, temp = map(Path, sys.argv[1:])
templates = here.parent / "delegate-templates"
if not templates.is_dir():
    templates = here.parent / "delegate/templates"
def normalise(text):
    return " ".join(text.split())
def body(name):
    """The spawn body a lane receives: spawner comments removed, every slot filled."""
    spawn = (templates / name).read_text().split("\n```\n")[1]
    spawn = re.sub(r"<!--.*?-->", "", spawn, flags=re.S)
    return re.sub(r"\{\{.*?\}\}", "fixture", spawn, flags=re.S)
def leg(name, passed):
    print(("OK " if passed else "FAIL ") + name)
compile_body, verify_body, hunter_body = body("brief-compile.md"), body("brief-ingest-verify.md"), body("brief-hunter.md")
skill = (here / "SKILL.md").read_text()
query = (here.parent / "query/SKILL.md").read_text()
clauses = [
    ("K8690e3fa-whole-source-universal", 'A statement about what a whole source contains or lacks ("the only figures are …", "the paper never discusses …") is a universal too: it rests on a grep of the whole raw, its pattern and hit count stated beside it, never on recall of the reading.', [compile_body]),
    ("K7eecda29-word-absent-from-collapsed-cell", "A word or unit absent from a collapsed cell is never supplied: the cell is quoted as printed and the gap marked `unverified`.", [compile_body, skill]),
    ("K7e51d58b-related-gloss-tables", "A `## Related` gloss that says where a metric or method appears lists the tables or sections it rests on, each one checked in the raw.", [compile_body]),
    ("Kc5337707-attribute-of-named-work", "An attribute of a named work, person or organisation (a novel, a paper, a startup, a professor) comes from the raw or is left out.", [compile_body]),
    ("K61ff0d78-vault-state-command-and-scope", 'A vault-state sentence names the exact command and the scope it ran over; "wiki/" in such a sentence means the whole tree, so a count taken over your index slice or the pages you read names that narrower scope instead.', [compile_body]),
    ("K88d02fb9-comparison-and-identifier", "A comparison with other sources, sibling captures included, names the check behind it, and no attribute is inferred from an identifier such as a path or a host name.", [compile_body]),
    ("Kf6b428da-chunked-whole-read", "An index past one Read call's limit is read whole in consecutive offsets to the end, the lines read checked against `wc -l wiki/index.md`, never stopped at a refused or truncated first chunk.", [query, hunter_body]),
]
for name, clause, carriers in clauses:
    for i, text in enumerate(carriers, 1):
        present = normalise(clause) in normalise(text)
        removed = text.replace(clause, "")
        leg("%s carrier %d: present, and a copy without it fails the same probe" % (name, i),
            present and normalise(clause) not in normalise(removed))
leg("K88d02fb9-identifier-count: the compile template names an identifier exactly once",
    (templates / "brief-compile.md").read_text().count("identifier") == 1)
leg("K7eecda29-table-rule-line-intact: the collapsed-cell sentence extends the all-depths table rule",
    "If the raw does not let you verify the labels, report the cell as unverifiable and omit the attributed figure. A word or unit absent from a collapsed cell is never supplied" in skill)
# The fidelity plant left formal work (the owner's rule of 26 October 2026): no brief a lane receives holds one.
verify_flat, skill_flat = normalise(verify_body), normalise(skill)
leg("plant-gone-from-the-verify-body", "plant" not in verify_flat.lower())
leg("plant-gone-from-the-compile-body", "plant" not in normalise(compile_body).lower())
leg("plant-gone-control: the same probe hits a copy that keeps the slot", "plant" in (verify_flat + " - Plant: a claim").lower())
# K1a12a51f: the head writes the verifier's open and close; the verify brief asks for no append.
verify_step = skill.split("## Verify step", 1)[1].split("\n## ", 1)[0]
leg("K1a12a51f-skill-head-writes-verifier-events", 'appends the verifier\'s `lane_open` (`role: verify`) and `lane_close`' in verify_step
    and '"written_by": "head"' in verify_step and "exempts verify briefs from its check (d)" in verify_step)
leg("K1a12a51f-skill-preflight-d-exempt", "a verify brief is exempt: the head appends the verifier's `lane_open` and `lane_close`" in skill_flat)
leg("K1a12a51f-verify-brief-no-append", '"written_by": "head"' in verify_body and "you append nothing to the run ledger" in verify_body
    and "role: verify" in verify_body)
leg("K1a12a51f-compile-spawner-note", "A verify brief is exempt from the fence check" in (templates / "brief-compile.md").read_text())
PYBATCHTEXT
then
  while IFS=' ' read -r result label; do
    if [ "$result" = OK ]; then ok "$label"; else no "$label"; fi
  done < "$T/batch-text-results.txt"
else
  cat "$T/batch-text-results.txt"
  no 'batch clause harness failed'
fi

echo '--- premise failures ---'
run --ledger "$R/run-fx-1.jsonl" --in-session all
if [ $RC -eq 2 ] && has "$OUT" "PROBE FAILED: zero briefs matched"; then ok "zero briefs: exit 2"; else no "zero briefs: rc=$RC: $OUT"; fi
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/no-such-brief.md"
if [ $RC -eq 2 ] && has "$OUT" "PROBE FAILED: brief unreadable"; then ok "unreadable brief: exit 2"; else no "unreadable brief: rc=$RC: $OUT"; fi
run --ledger "$R/no-such-run.jsonl" --in-session all "$B/L1.md"
if [ $RC -eq 2 ] && has "$OUT" "is missing or unreadable"; then ok "missing ledger: exit 2"; else no "missing ledger: rc=$RC: $OUT"; fi
run --ledger "$R/run-fx-4.jsonl" --in-session all "$B/L1.md"
if [ $RC -eq 2 ] && has "$OUT" "holds no parseable event (1 malformed lines)"; then ok "unparseable ledger: exit 2"; else no "unparseable ledger: rc=$RC: $OUT"; fi
printf '{"ts":"2026-01-01T10:00+0000","event":"lane_open","lane":"L1"}\n' > "$R/run-fx-5.jsonl"
run --ledger "$R/run-fx-5.jsonl" --in-session all "$B/L1.md"
if [ $RC -eq 2 ] && has "$OUT" "holds no run_open event"; then ok "a ledger without run_open: exit 2"; else no "no run_open: rc=$RC: $OUT"; fi
printf 'You are wiki-compile, lane L7 of run run-fx-1 · model opus · effort xhigh.\n\nNo roots named here at all.\n' > "$B/L7-noroots.md"
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L7-noroots.md"
if [ $RC -eq 2 ] && has "$OUT" "carries no path token at all"; then ok "a brief with no roots (no path token): exit 2"; else no "no roots: rc=$RC: $OUT"; fi
printf 'A note with raw/paper-a.md but no first line naming a lane.\n' > "$B/nolane.md"
run --ledger "$R/run-fx-1.jsonl" --in-session all "$B/nolane.md"
if [ $RC -eq 2 ] && has "$OUT" "names no lane on its first line"; then ok "a brief naming no lane: exit 2"; else no "no lane: rc=$RC: $OUT"; fi
mkdir -p "$T/emptyvault/wiki"; : > "$T/emptyvault/wiki/index.md"
OUT=$(env HOME="$H" "$PY" -B "$S" --vault "$T/emptyvault" --ledger "$R/run-fx-1.jsonl" --in-session all "$B/L1.md" 2>&1); RC=$?
if [ $RC -eq 2 ] && has "$OUT" "holds no \`## \` section"; then ok "an empty index: exit 2"; else no "empty index: rc=$RC: $OUT"; fi

echo '--- claims checkpoint shape (mandatory lane assertion) ---'
if "$PY" -B - "$HERE" "$T" <<'PYCLAIMTEST' > "$T/claims-results.txt"
import hashlib, json, os, re, subprocess, sys
from pathlib import Path
here, temp = map(Path, sys.argv[1:])
# Flat stage names and installed delegate layout are both supported.
core = here.parent / "compile-core/SKILL.md"
brief = here.parent / "delegate-templates/brief-compile.md"
if not core.is_file():
    core = here.parent / "delegate/lane-home-src/compile-core/SKILL.md"
if not brief.is_file():
    brief = here.parent / "delegate/templates/brief-compile.md"
text = core.read_text()
blocks = re.findall(r"```python\n(# claims-shape assertion:.*?)\n```", text, re.S)
if len(blocks) != 1:
    raise RuntimeError("exactly one claims-shape assertion required")
code = blocks[0]
def leg(name, passed):
    print(("OK " if passed else "FAIL ") + name)
example_lines = []
for carrier in (core, brief):
    examples = [json.loads(line.strip().strip('`')) for line in carrier.read_text().splitlines()
                if line.strip().startswith('`{"event":"checkpoint"')]
    example_lines.extend(examples)
    leg("R1-example " + carrier.name, len(examples) == 1
        and examples[0].get("stage") == "claims_emitted"
        and examples[0].get("claims") == [] and examples[0].get("claims_count") == 0)
base = {"event": "checkpoint", "stage": "claims_emitted", "lane": "compile", "source": "raw/paper.md"}
claim = {"name": "Example"}
fixtures = temp / "claims-readonly"
fixtures.mkdir()
cases = [
    ("integer", [dict(base, claims=1, claim_objects=[claim])], 2, "claims must be a list"),
    ("objects", [dict(base, claims=[claim], claims_count=1)], 0, "objects 1 · invalid 0"),
    ("empty-list", [dict(base, claims=[], claims_count=0)], 0, "objects 0 · invalid 0"),
    ("missing-key", [dict(base, claim_objects=[claim])], 2, "claims must be a list"),
    ("null", [dict(base, claims=None)], 2, "claims must be a list"),
    ("string-member", [dict(base, claims=["Example"])], 2, "claims must be a list"),
    ("empty-object", [dict(base, claims=[{}])], 2, "claims must be a list"),
    ("blank-name", [dict(base, claims=[{"name": " "}])], 2, "claims must be a list"),
    ("wrong-count", [dict(base, claims=[claim], claims_count=0)], 2, "claims_count must equal"),
    ("boolean-count", [dict(base, claims=[claim], claims_count=True)], 2, "claims_count must equal"),
    ("empty-ledger", [], 2, "no claims_emitted checkpoint"),
    ("wrong-lane", [dict(base, lane="sibling", claims=[])], 2, "no claims_emitted checkpoint"),
    ("wrong-source", [dict(base, source="raw/other.md", claims=[])], 2, "no claims_emitted checkpoint"),
    ("earlier-bad", [dict(base, claims=1), dict(base, claims=[])], 2, "claims must be a list"),
    ("non-object", [[]], 2, "not an object"),
]
for name, rows, _, _ in cases:
    (fixtures / (name + ".jsonl")).write_text("".join(json.dumps(row) + "\n" for row in rows))
(fixtures / "torn.jsonl").write_text('{"event":')
cases += [("torn", [], 2, "cannot check ledger"), ("missing", [], 2, "cannot check ledger")]
def manifest():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in fixtures.iterdir()}
before = manifest()
for path in fixtures.iterdir():
    path.chmod(0o444)
fixtures.chmod(0o555)
for name, _, status, phrase in cases:
    result = subprocess.run([sys.executable, "-B", "-c", code, str(fixtures / (name + ".jsonl")),
                             "compile", "raw/paper.md"], capture_output=True, text=True)
    leg("R1-" + name, result.returncode == status and phrase in result.stdout
        and "controls: integer claims rejected" in result.stdout
        and (status != 2 or "PROBE FAILED:" in result.stdout) and not result.stderr)
result = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True)
leg("R1-missing-arguments", result.returncode == 2 and "PROBE FAILED:" in result.stdout)
# The assertion's own read-only proof, beside the helper proof below.
leg("R1-readonly-manifest", bool(before) and before == manifest())
patterns = [(r"open\([^)]*,\s*['\"][^'\"]*[wax+]", 'open(p, "w")'),
            (r"\.write(?:_text|_bytes)?\(", "p.write_text(s)"),
            (r"\b(?:os|shutil)\.(?:replace|rename|remove|unlink|mkdir|makedirs|rmdir|copy|move)", "os.remove(p)"),
            (r"\bsubprocess\b|\bos\.(?:system|popen)\(", "subprocess.run(x)")]
leg("R1-source-write-grep", all(re.search(p, control) for p, control in patterns)
    and not any(re.search(p, code) for p, _ in patterns))
fixtures.chmod(0o755)
verify = brief.with_name("brief-ingest-verify.md").read_text()
required = re.findall(r"grep -qxE '([^']+)'", verify)
forbidden = re.findall(r"grep -qE '([^']+)'", verify)
if len(required) != 1 or len(forbidden) != 1:
    raise RuntimeError("one required and one forbidden claims-shape grep required")
def report_ok(report):
    section = re.search(r"^## Controls\n(.*?)(?=^## |\Z)", report, re.M | re.S)
    text = section[1] if section else ""
    yes = subprocess.run(["grep", "-qxE", required[0]], input=text, capture_output=True, text=True)
    no = subprocess.run(["grep", "-qE", forbidden[0]], input=text, capture_output=True, text=True)
    if yes.returncode not in (0, 1) or no.returncode not in (0, 1):
        raise RuntimeError("claims-shape report grep failed")
    return yes.returncode == 0 and no.returncode == 1
valid_line = "claims-shape: checkpoints 1 · objects 2 · invalid 0\n"
report_cases = [
    ("present", "## Controls\n" + valid_line, True),
    ("missing", "## Controls\ncontrols: assertion omitted\n", False),
    ("invalid-two", "## Controls\n" + valid_line.replace("invalid 0", "invalid 2"), False),
    ("mixed-results", "## Controls\n" + valid_line + valid_line.replace("invalid 0", "invalid 2"), False),
    ("wrong-section", "## Findings\n" + valid_line + "## Controls\ncontrols: missing\n", False),
    ("empty-report", "", False),
    ("zero-checkpoints", "## Controls\n" + valid_line.replace("checkpoints 1", "checkpoints 0"), False),
]
for name, report, expected in report_cases:
    leg("F6-report-" + name, report_ok(report) == expected)
# A lane-report evidence failure is `shape: fail` on the verify record, never a `claims` count, and a
# refuted fact whose object still applies is listed under `flagged_facts` (the merge planner's rule,
# 2026-09-21). Each carrier is pinned here; the retired `claims 1` wording fails every leg.
leg("F6-verifier-consumer", "shape: fail" in verify and "scores `claims 1`" not in verify
    and "names the compile lane" not in verify and "name the compile lane" in verify and "- Compile report:" in verify)
locator_rows = [row for row in verify.splitlines() if "**Named check — claims locator evidence" in row]
leg("F6-locator-consumer", len(locator_rows) == 1 and "shape: fail" in locator_rows[0]
    and "claims 1" not in locator_rows[0] and "it never adds to `claims`" in locator_rows[0])
leg("F6-flagged-facts", "`flagged_facts` (name · lane · fact · fix)" in verify)
leg("F6-shape-line-placement", "`shape: fail` on its own line directly above that scores line, never inside it" in verify)
compile_text = brief.read_text()
notes = [row for row in compile_text.splitlines()
         if row.startswith(("`## Controls` (parallel mode):", "The same section carries the claims-locator check"))]
leg("F6-compile-report-notes", len(notes) == 2 and "`claims 1`" not in compile_text
    and all("`shape: fail`, never a `claims` count" in row for row in notes))
skill_text = (here / "SKILL.md").read_text()
leg("F6-skill-step-8", "the event's `shape: fail` field, never into `claims`" in skill_text
    and "the verify event lists it under `flagged_facts` (name · lane · fact · fix)" in skill_text)
for carrier in (core, brief):
    leg("F6-report-location-" + carrier.name,
        "final report under a `## Controls` heading" in carrier.read_text())
PYCLAIMTEST
then
  while IFS=' ' read -r result label; do
    if [ "$result" = OK ]; then ok "$label"; else no "$label"; fi
  done < "$T/claims-results.txt"
else
  cat "$T/claims-results.txt"
  no 'R1 assertion harness failed'
fi

echo '--- stdout-only proof (must run last) ---'
RO="$T/readonly"; mkdir -p "$RO"; cp -R "$V" "$H" "$B" "$RO/"; cp "$T/dry-ok.txt" "$T/stub-fence.py" "$RO/"
chmod -R a-w "$RO"
BEFORE="$(manifest "$RO")"
RO1=$(env HOME="$RO/home" "$PY" -B "$S" --vault "$RO/vault" --ledger "$RO/home/.agent-wiki/ingest-runs/run-fx-1.jsonl" --in-session all "$RO/briefs/L1.md" "$RO/briefs/V1.md" 2>&1); r1=$?
RO2=$(env HOME="$RO/home" "$PY" -B "$S" --vault "$RO/vault" --ledger "$RO/home/.agent-wiki/ingest-runs/run-fx-1.jsonl" --in-session all "$RO/briefs/L1-mangled.md" 2>&1); r2=$?
RO3=$(env HOME="$RO/home" "$PY" -B "$S" --vault "$RO/vault" --ledger "$RO/home/.agent-wiki/ingest-runs/run-fx-2.jsonl" --fence "$RO/stub-fence.py" --dry-run L1="$RO/dry-ok.txt" "$RO/briefs/L1-run2.md" 2>&1); r3=$?
RO4=$(env HOME="$RO/home" "$PY" -B "$S" --vault "$RO/vault" --ledger "$RO/home/.agent-wiki/ingest-runs/run-fx-1.jsonl" 2>&1); r4=$?
RO5=$(env HOME="$RO/home" "$PY" -B "$S" --vault "$RO/vault" --ledger "$RO/home/.agent-wiki/ingest-runs/run-fx-1.jsonl" --in-session all "$RO/briefs/L1-ampersand-missing.md" 2>&1); r5=$?
RO6=$(env HOME="$RO/home" "$PY" -B "$S" --vault "$RO/vault" --ledger "$RO/home/.agent-wiki/ingest-runs/run-fx-1.jsonl" --in-session all "$RO/briefs/L1-ampersand-valid.md" 2>&1); r6=$?
RO7=$(env HOME="$RO/home" "$PY" -B "$S" --vault "$RO/vault" --ledger "$RO/home/.agent-wiki/ingest-runs/run-fx-1.jsonl" --in-session all "$RO/briefs/L1-draft-missing.md" 2>&1); r7=$?
RO8=$(env HOME="$RO/home" "$PY" -B "$S" --vault "$RO/vault" --ledger "$RO/home/.agent-wiki/ingest-runs/run-fx-1.jsonl" --in-session all "$RO/briefs/L1-draft-valid.md" "$RO/briefs/L1-command-valid.md" 2>&1); r8=$?
RO9=$(env HOME="$RO/home" "$PY" -B "$S" --vault "$RO/vault" --ledger "$RO/home/.agent-wiki/ingest-runs/run-fx-1.jsonl" --in-session all "$RO/briefs/L1-prose-missing.md" "$RO/briefs/L1-bare-missing.md" 2>&1); r9=$?
RO10=$(env HOME="$RO/home" "$PY" -B "$S" --vault "$RO/vault" --ledger "$RO/home/.agent-wiki/ingest-runs/run-fx-1.jsonl" --in-session all "$RO/briefs/L1-prose-valid.md" "$RO/briefs/L1-bare-valid.md" 2>&1); r10=$?
chmod -R u+w "$RO"
AFTER="$(manifest "$RO")"
if [ "$r1 $r2 $r3 $r4" = "0 1 1 2" ]; then ok "modes against a chmod -R a-w copy exit as expected (0 1 1 2)"; else no "read-only modes exited $r1 $r2 $r3 $r4: $RO1 $RO2 $RO3 $RO4"; fi
if [ "$r5 $r6" = "1 0" ] && has "$RO5" "A & B/missing" && has "$RO6" "ampersand paths tested whole"; then ok "N8-W1 read-only ampersand cases fail and pass with the control"; else no "N8-W1 read-only exits $r5 $r6: $RO5 $RO6"; fi
if [ "$r7 $r8" = "1 0" ] && has "$RO7" "A & B -draft/missing" && has "$RO8" "command spans split"; then ok "F13-W read-only quoted-draft and command-span cases keep their results"; else no "F13-W read-only exits $r7 $r8: $RO7 $RO8"; fi
if [ "$r9 $r10" = "1 0" ] && has "$RO9" "missing does not exist" && has "$RO10" "prose apostrophes ignored, bare backtick paths kept whole"; then ok "N12-W read-only prose and bare-backtick cases keep failures, passes and controls"; else no "N12-W read-only exits $r9 $r10: $RO9 $RO10"; fi
NFILES=$(printf '%s\n' "$BEFORE" | grep -c '^[0-9a-f]\{40\}  ')
if [ "$NFILES" -ge 10 ] && [ "$BEFORE" = "$AFTER" ]; then ok "the read-only copy's checksum manifest is unchanged ($NFILES files)"; else no "read-only manifest changed or too small ($NFILES files)"; fi
if [ "$(manifest "$HERE")" = "$HOME_BEFORE" ]; then ok "the script home is byte-identical to its pre-run baseline (no bytecode cache written)"; else no "the script home changed during the suite"; fi
if "$PY" - "$S" <<'PYEOF'
import re, sys
pats = [r"""open\([^)]*,\s*['"][rwxabt+]*[wax+][rwxabt+]*['"]""", r"\.write(?:_text|_bytes)?\(",
        r"\bos\.(?:replace|rename|remove|unlink|mkdir|makedirs|rmdir|symlink|link|truncate|chmod)\(",
        r"\bshutil\.", r"\bsubprocess\b|\bos\.system\(|\bos\.popen\("]
controls = ['open(p, "w")', "fh.write(x)", "os.replace(a, b)", "shutil.copy(a, b)", "subprocess.run(x)"]
src = open(sys.argv[1], encoding="utf-8").read()
dead = [p for p, c in zip(pats, controls) if not re.search(p, c)]
hits = [m.group(0) for p in pats for m in re.finditer(p, src)]
print("  source grep: %d patterns, dead %d, hits %d %s" % (len(pats), len(dead), len(hits), hits[:3]))
sys.exit(0 if not dead and not hits else 1)
PYEOF
then ok "no write pattern in the script's source (5 patterns, each matched on its own control line)"; else no "source grep: a write pattern hit, or a pattern missed its control"; fi

N=$((PASS + FAIL))
printf '\n'
if [ "$FAIL" -eq 0 ]; then printf 'PASS %d/%d\n' "$PASS" "$N"; else printf 'FAIL %d/%d\n' "$FAIL" "$N"; fi
[ "$FAIL" -eq 0 ]
