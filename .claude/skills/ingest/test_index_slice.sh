#!/bin/bash
# test_index_slice.sh — index_slice.py, the index slice a parallel compile brief names (design extension
# 2026-09-13, part 3): the GPT/GPT-4o anchor that must fire, the AIME line that must not, alias forms,
# the word boundary, MISSING, the premise failures, and the stdout-only proof.
# Every fixture sits under one mktemp -d in /tmp and is removed on success; the vault is never touched.
# Usage: bash test_index_slice.sh [path/to/index_slice.py]   (default: beside this script)
set -u
export LC_ALL=C
HERE=$(cd "$(dirname "$0")" && pwd)
S=${1:-"$HERE/index_slice.py"}
PY=${PYTHON:-python3}
T=$(mktemp -d /tmp/index-slice-suite.XXXXXX)
PASS=0; FAIL=0
ok() { PASS=$((PASS+1)); echo "ok   $1"; }
no() { FAIL=$((FAIL+1)); echo "FAIL $1"; }
has() { case "$1" in *"$2"*) return 0;; esac; return 1; }
manifest() { find "$1" -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum | LC_ALL=C sort; }
HOME_BEFORE="$(manifest "$HERE")"

V="$T/vault"; W="$V/wiki"
mkdir -p "$W/models" "$W/benchmarks" "$W/concepts" "$W/entities" "$W/tools" "$T/raws"
cat > "$W/index.md" <<'IDXEOF'
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
- [[Ghost Page]] — an entry whose page is missing
## Models
<!-- LLMs -->
- [[GPT]] — OpenAI's model family
- [[Qwen]] — Alibaba's model family
## Benchmarks
- [[AIME]] — a maths competition benchmark
## Concepts
- [[Calibration]] — agreement of stated confidence with accuracy
## Syntheses
- [[an-answer]] — a filed answer
IDXEOF
printf -- '---\ntitle: GPT\ntype: model\naliases: [GPT-4o, "ChatGPT"]\n---\n## Definition\nx\n' > "$W/models/GPT.md"
printf -- '---\ntitle: Qwen\ntype: model\naliases:\n  - Qwen2.5\n  - Tongyi Qianwen\n---\n## Definition\nx\n' > "$W/models/Qwen.md"
printf -- '---\ntitle: AIME\ntype: benchmark\naliases: [American Invitational Mathematics Examination]\n---\n## Definition\nx\n' > "$W/benchmarks/AIME.md"
printf -- '---\ntitle: Calibration\ntype: concept\n---\n## Definition\nx\n' > "$W/concepts/Calibration.md"
printf -- '---\ntitle: Example Lab\ntype: entity\n---\n' > "$W/entities/Example Lab.md"
printf -- '---\ntitle: markitdown\ntype: tool\n---\n' > "$W/tools/markitdown.md"
printf 'We fine-tune GPT-4o on a maths set and report CALIBRATION error.\n' > "$T/raws/r1.md"
printf 'An assistant such as ChatGPT answered; recalibration was not studied.\n' > "$T/raws/r2.md"
printf 'The Qwen2.5 checkpoints were used.\n' > "$T/raws/r3.md"
run() { OUT=$("$PY" -B "$S" --index "$W/index.md" "$@" 2>&1); RC=$?; }

echo '--- must fire: GPT-4o in the raw anchors the GPT line ---'
run "$T/raws/r1.md"
if [ $RC -eq 0 ] && printf '%s\n' "$OUT" | grep -qxF -- "- [[GPT]] — OpenAI's model family"; then ok "the GPT index line is in the slice verbatim, in anchor form"; else no "GPT anchor: rc=$RC: $OUT"; fi
if printf '%s\n' "$OUT" | grep -qxF "  matched: GPT-4o (alias) in r1.md" || printf '%s\n' "$OUT" | grep -qxF "  matched: GPT (name) in r1.md"; then ok "the anchor names the term that matched and the raw"; else no "matched line: $OUT"; fi
if has "$OUT" 'control: `GPT` found in the name list'; then ok "the control entry is found on the same run"; else no "control line: $OUT"; fi
if printf '%s\n' "$OUT" | grep -qxF -- "- [[Calibration]] — agreement of stated confidence with accuracy"; then ok "matching is case-folded (CALIBRATION anchors Calibration)"; else no "case fold: $OUT"; fi

echo '--- must not fire: AIME, which the raw never names ---'
if ! printf '%s\n' "$OUT" | grep -qF -- "- [[AIME]]"; then ok "the AIME line is absent from the anchors"; else no "AIME anchored: $OUT"; fi
if printf '%s\n' "$OUT" | sed -n '/^### Benchmarks (1)$/,/^### /p' | grep -qx 'AIME'; then ok "AIME is present in the name list"; else no "AIME name list: $OUT"; fi
if has "$OUT" "entries 7 · anchored 2 · missing 1"; then ok "counts: 7 entries in the five sections, 2 anchored, 1 missing"; else no "counts: $OUT"; fi
if ! printf '%s\n' "$OUT" | grep -qx 'an-answer' && ! printf '%s\n' "$OUT" | grep -qx 'paper-a'; then ok "entries outside the five sections are not in the name list"; else no "section scope: $OUT"; fi

echo '--- aliases and the word boundary ---'
run "$T/raws/r2.md"
if printf '%s\n' "$OUT" | grep -qxF "  matched: ChatGPT (alias) in r2.md"; then ok "an inline quoted alias anchors (ChatGPT, where the name GPT sits inside a longer word)"; else no "inline alias: $OUT"; fi
if ! printf '%s\n' "$OUT" | grep -qF -- "- [[Calibration]]"; then ok "word-bounded: recalibration does not anchor Calibration"; else no "boundary: $OUT"; fi
run "$T/raws/r3.md"
if printf '%s\n' "$OUT" | grep -qxF "  matched: Qwen2.5 (alias) in r3.md"; then ok "a block-list alias anchors (Qwen2.5)"; else no "block alias: $OUT"; fi
mkdir -p "$T/noalias/models"; cp "$W/index.md" "$T/noalias/index.md"; printf -- '---\ntitle: GPT\n---\n' > "$T/noalias/models/GPT.md"
OUT=$("$PY" -B "$S" --index "$T/noalias/index.md" "$T/raws/r2.md" 2>&1); RC=$?
if [ $RC -eq 0 ] && ! printf '%s\n' "$OUT" | grep -qF -- "- [[GPT]]"; then ok "without the alias, ChatGPT does not anchor GPT (the alias leg above is the alias's doing)"; else no "no-alias control: rc=$RC: $OUT"; fi
run "$T/raws/r1.md" "$T/raws/r2.md" "$T/raws/r3.md"
if [ $RC -eq 0 ] && has "$OUT" "MISSING Ghost Page" && has "$OUT" "anchored 3 · missing 1"; then ok "a missing page prints MISSING and is never fatal; three raws anchor three entries"; else no "MISSING/multi-raw: rc=$RC: $OUT"; fi

echo '--- hash and byte counts ---'
run "$T/raws/r1.md"
WANT=$(shasum -a 256 "$W/index.md" | cut -c1-16)
if has "$OUT" "sha256 $WANT"; then ok "the printed sha256 prefix equals shasum's first 16 hex"; else no "hash: want $WANT: $OUT"; fi
FIVE=$("$PY" - "$W/index.md" <<'PYEOF'
import sys
keep, total = False, 0
for line in open(sys.argv[1], "rb"):
    if line.startswith(b"## "):
        keep = line[3:].strip() in (b"Entities", b"Tools", b"Concepts", b"Models", b"Benchmarks")
    if keep:
        total += len(line)
print(total)
PYEOF
)
if has "$OUT" "five sections $FIVE ("; then ok "the five sections' byte count matches an independent count ($FIVE)"; else no "section bytes: want $FIVE: $OUT"; fi

echo '--- review: a one-character name anchors when it stands alone ---'
mkdir -p "$T/rwiki/tools"
printf -- '---\ntitle: Index\n---\n## Entities\n- [[Example Lab]] — a lab\n## Tools\n- [[R]] — a statistics language\n## Concepts\n- [[Calibration]] — a concept\n## Models\n- [[GPT]] — a model family\n## Benchmarks\n- [[AIME]] — a benchmark\n' > "$T/rwiki/index.md"
printf -- '---\ntitle: R\ntype: tool\n---\n' > "$T/rwiki/tools/R.md"
printf 'We use R for analysis.\n' > "$T/raws/r4.md"
printf 'We use Rust and RL throughout.\n' > "$T/raws/r5.md"
OUT=$("$PY" -B "$S" --index "$T/rwiki/index.md" "$T/raws/r4.md" 2>&1); RC=$?
if [ $RC -eq 0 ] && printf '%s\n' "$OUT" | grep -qxF -- "- [[R]] — a statistics language" && printf '%s\n' "$OUT" | grep -qxF "  matched: R (name) in r4.md"; then ok "R anchors when the raw names it on its own (exit 0)"; else no "R alone: rc=$RC: $OUT"; fi
OUT=$("$PY" -B "$S" --index "$T/rwiki/index.md" "$T/raws/r5.md" 2>&1); RC=$?
if [ $RC -eq 0 ] && ! printf '%s\n' "$OUT" | grep -qF -- "- [[R]]"; then ok "R stays out of the anchors when it occurs only inside other words (Rust, RL)"; else no "R inside words: rc=$RC: $OUT"; fi

echo '--- premise failures ---'
sed 's/^## Models$/## Model/' "$W/index.md" > "$T/renamed.md"
OUT=$("$PY" -B "$S" --index "$T/renamed.md" --wiki "$W" "$T/raws/r1.md" 2>&1); RC=$?
if [ $RC -eq 2 ] && has "$OUT" 'PROBE FAILED: section heading `## Models` is missing or renamed'; then ok "a renamed section heading: exit 2"; else no "renamed: rc=$RC: $OUT"; fi
{ cat "$W/index.md"; printf '## Tools\n- [[x]] — y\n'; } > "$T/repeated.md"
OUT=$("$PY" -B "$S" --index "$T/repeated.md" --wiki "$W" "$T/raws/r1.md" 2>&1); RC=$?
if [ $RC -eq 2 ] && has "$OUT" "repeated 2 times"; then ok "a repeated section heading: exit 2"; else no "repeated: rc=$RC: $OUT"; fi
: > "$T/empty.md"
OUT=$("$PY" -B "$S" --index "$T/empty.md" "$T/raws/r1.md" 2>&1); RC=$?
if [ $RC -eq 2 ] && has "$OUT" "is empty"; then ok "an empty index: exit 2"; else no "empty index: rc=$RC: $OUT"; fi
run
if [ $RC -eq 2 ] && has "$OUT" "zero raws"; then ok "zero raws: exit 2"; else no "zero raws: rc=$RC: $OUT"; fi
run "$T/raws/no-such.md"
if [ $RC -eq 2 ] && has "$OUT" "raw unreadable"; then ok "a missing raw: exit 2"; else no "missing raw: rc=$RC: $OUT"; fi
run --control "Not An Entry" "$T/raws/r1.md"
if [ $RC -eq 2 ] && has "$OUT" "the control entry 'Not An Entry' is not in the name list"; then ok "a control entry absent from the name list: exit 2"; else no "absent control: rc=$RC: $OUT"; fi
OUT=$("$PY" -B "$S" --index "$T/no-index.md" "$T/raws/r1.md" 2>&1); RC=$?
if [ $RC -eq 2 ] && has "$OUT" "is unreadable"; then ok "an unreadable index: exit 2"; else no "unreadable index: rc=$RC: $OUT"; fi

echo '--- stdout-only proof (must run last) ---'
RO="$T/readonly"; mkdir -p "$RO"; cp -R "$V" "$T/raws" "$RO/"; chmod -R a-w "$RO"
BEFORE="$(manifest "$RO")"
"$PY" -B "$S" --index "$RO/vault/wiki/index.md" "$RO/raws/r1.md" "$RO/raws/r2.md" > /dev/null 2>&1; r1=$?
"$PY" -B "$S" --index "$RO/vault/wiki/index.md" "$RO/raws/no-such.md" > /dev/null 2>&1; r2=$?
chmod -R u+w "$RO"
AFTER="$(manifest "$RO")"
if [ "$r1 $r2" = "0 2" ]; then ok "modes against a chmod -R a-w copy exit as expected (0 2)"; else no "read-only modes exited $r1 $r2"; fi
NFILES=$(printf '%s\n' "$BEFORE" | grep -c '^[0-9a-f]\{40\}  ')
if [ "$NFILES" -ge 8 ] && [ "$BEFORE" = "$AFTER" ]; then ok "the read-only copy's checksum manifest is unchanged ($NFILES files)"; else no "read-only manifest changed or too small ($NFILES files)"; fi
if [ "$(manifest "$HERE")" = "$HOME_BEFORE" ]; then ok "the script home is byte-identical to its pre-run baseline"; else no "the script home changed during the suite"; fi
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
if [ "$FAIL" -eq 0 ]; then rm -rf "$T"; printf 'PASS %d/%d\n' "$PASS" "$N"; else printf 'work dir %s\nFAIL %d/%d\n' "$T" "$FAIL" "$N"; fi
[ "$FAIL" -eq 0 ]
