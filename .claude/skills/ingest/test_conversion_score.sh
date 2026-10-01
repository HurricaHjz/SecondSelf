#!/bin/sh
# test_conversion_score.sh — suite for conversion_score.py, ingest Step 0's conversion scorer.
# Every fixture is built under one mktemp -d in /tmp and removed at exit; the vault is never
# touched. The final legs are the stdout-only proof: a read-only copy of the fixture set with a
# checksum manifest before and after every flag the script takes, the script home compared with
# its pre-run baseline, and a source grep for write patterns whose own control must hit.
#
# Run:  sh .claude/skills/ingest/test_conversion_score.sh      (exit 0 = every leg passed)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SCORE="$HERE/conversion_score.py"
PY=python3

PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); printf '    ok   — %s\n' "$1"; }
no(){ FAIL=$((FAIL+1)); printf '  FAIL   — %s\n' "$1"; }
eq(){ if [ "$2" = "$3" ]; then ok "$1"; else no "$1  [want '$2', got '$3']"; fi; }
has(){ printf '%s\n' "$2" | grep -c -- "$1"; }   # has <pattern> <text>: matching lines

T="$(mktemp -d "${TMPDIR:-/tmp}/convscore.XXXXXX")"
trap 'chmod -R u+w "$T"; rm -rf "$T"' EXIT
F="$T/fixture"; mkdir -p "$F" "$T/nomd" "$T/withpdf"
ERR="$T/stderr.txt"
printf 'not markdown\n' > "$T/nomd/readme.txt"

manifest(){ find "$1" -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum | LC_ALL=C sort; }
hashes(){ printf '%s\n' "$1" | grep -c '^[0-9a-f]\{40\}  '; }
START_H="$(manifest "$HERE")"

# The original four derived thresholds (asserted verbatim below, so a silent edit of
# one constant fails the suite until the docstring and this file are updated together).
TS='57\.57 %'; TR='4\.41 %'; TL='6\.56 /1k'; TC='0\.15'

# ---------------------------------------------------------------- fixtures
PROSE='The policy gradient method estimates the direction of improvement from sampled trajectories and applies a clipped update so that the new policy stays close to the old one. Each iteration collects a batch of episodes, computes advantages with a learned value function, and runs several epochs of minibatch optimisation on the surrogate objective. The clipping range bounds the ratio between the new and the old policy, which keeps the update conservative without a separate constraint. Empirically this simple recipe matches or exceeds the trust region method on continuous control tasks while being far easier to implement and tune. The authors also report results on discrete action benchmarks where the same objective works without modification.'

# clean: ordinary prose, a URL source converted by markitdown (scope pdf by engine), no PDF beside it
printf -- '---\nconverted_from: https://example.org/paper\nconverted_by: markitdown\nconverted_on: 2026-01-01\n---\n\n# A clean conversion\n\n%s\n\n%s\n' "$PROSE" "$PROSE" > "$F/clean.md"

# collapsed: the structural collapse — one character per line for most of the body
{ printf -- '---\nconverted_by: markitdown\n---\n\n# Collapsed\n\n'
  i=0; while [ $i -lt 45 ]; do printf 'a\n'; i=$((i+1)); done
  printf 'One ordinary line survives in the middle.\n\n'
  i=0; while [ $i -lt 15 ]; do printf 'b\n'; i=$((i+1)); done
  printf 'A second ordinary line survives at the end.\n'; } > "$F/collapsed.md"

# joined: sound lines, inter-word spaces lost on a share of the words (a lower-to-upper join
# or a run of more than 18 letters), well above the derived threshold
"$PY" - "$F/joined.md" "$PROSE" <<'PYFIX'
import sys
path, prose = sys.argv[1], sys.argv[2]
words = prose.split()
out, i = [], 0
while i < len(words):
    if i % 4 == 0 and i + 1 < len(words):          # join every fourth pair: "methodEstimates"
        out.append(words[i] + words[i + 1][0].upper() + words[i + 1][1:]); i += 2
    else:
        out.append(words[i]); i += 1
body = " ".join(out)
open(path, "w", encoding="utf-8").write("---\nconverted_by: markitdown\n---\n\n# Joined\n\n" + body + "\n\n" + body + "\n")
PYFIX

# runs: the SoK shape — a run-together share well under its threshold, but twelve runs of 25+
# letters in 1,100 words (the skill's probe (a) rate above its threshold). runs-few: the same
# rate from two runs in 110 words — under the skill's ten-run floor, so it must not fire.
"$PY" - "$F/runs.md" "$F/runs-few.md" "$PROSE" <<'PYFIX'
import re, sys
runs_path, few_path, prose = sys.argv[1], sys.argv[2], sys.argv[3]
def build(copies, joins):
    words = (prose.split() * copies)
    out, i, made = [], 0, 0
    while i < len(words):
        if made < joins and i % 90 == 0:
            run, k = "", 0
            while len(run) < 25 and i + k < len(words):
                run += re.sub(r"[^A-Za-z]", "", words[i + k]).lower(); k += 1
            out.append(run); i += k; made += 1
        else:
            out.append(words[i]); i += 1
    assert made == joins, made
    return " ".join(out)
open(runs_path, "w", encoding="utf-8").write("---\nconverted_from: https://example.org/abs/1\nconverted_by: markitdown\n---\n\n# Runs\n\n" + build(10, 12) + "\n")
open(few_path, "w", encoding="utf-8").write("---\nconverted_from: https://example.org/abs/2\nconverted_by: markitdown\n---\n\n# Few runs\n\n" + build(1, 2) + "\n")
PYFIX

# exclusions: the same 100 CamelCase identifiers inside a fence (must not count) and outside
# one (the positive control: they would fire); a tag carrying a base64 attribute; a bare blob;
# and space-stripped prose that carries digits, which the blob rule must keep as evidence
"$PY" - "$F" "$PROSE" <<'PYFIX'
import sys
d, prose = sys.argv[1], sys.argv[2]
idents = " ".join(f"BetaMessageParam{i} ContentBlockDeltaEvent{i}" for i in range(50))
# the same three-token heading as clean.md, so the token counts compare exactly
head = "---\nconverted_from: https://example.org/docs\nconverted_by: markitdown\n---\n\n# A clean conversion\n\n"
open(f"{d}/excl-fence.md", "w", encoding="utf-8").write(head + prose + "\n\n```python\n" + idents + "\n```\n\n" + prose + "\n")
open(f"{d}/excl-fence-control.md", "w", encoding="utf-8").write(head + prose + "\n\n" + idents + "\n\n" + prose + "\n")
blob = "Zx9Qw7Kp2Lm4Rt8Vn3Bc6Fd1Hg5Jk0Pq7Sz2Wx4Tn3Mr8Vb5Ng2Kl7Xz1Qw9" * 3
open(f"{d}/excl-tag.md", "w", encoding="utf-8").write(head + prose + '\n\n<latexit sha1_base64="' + blob + '">someInlineMath</latexit> <div class="someCamelCaseClass anotherCamelCaseName">\n\n' + prose + "\n")
open(f"{d}/excl-blob.md", "w", encoding="utf-8").write(head + prose + "\n\n" + blob + " " + blob + "\n\n" + prose + "\n")
damaged = " ".join(f"Table{i}showsthattheproposedmethodoutperformsthebaseline" for i in range(1, 21))
open(f"{d}/digits-prose.md", "w", encoding="utf-8").write(head + prose + "\n\n" + damaged + "\n\n" + prose + "\n")
PYFIX

# cjk: a non-Latin-majority body (no inter-word spaces to lose); cjk-mixed: English prose with
# CJK sentences making some 40 % of the letters — Latin-majority, scored on the Latin tokens
CJK='策略梯度方法从采样的轨迹中估计改进方向，并施加裁剪更新，使新策略与旧策略保持接近。每次迭代收集一批回合，用学习到的价值函数计算优势，并在替代目标上运行若干轮小批量优化。裁剪范围限制了新旧策略之间的比率，从而在没有单独约束的情况下保持更新的保守性。实验表明这一简单方法在连续控制任务上与信赖域方法相当或更好，同时更容易实现和调参。'
printf -- '---\nconverted_by: markitdown\n---\n\n# 中文转换\n\n%s\n\n%s\n' "$CJK" "$CJK" > "$F/cjk.md"
printf -- '---\nconverted_by: markitdown\n---\n\n# Mixed\n\n%s\n\n%s\n\n%s\n\n%s\n' "$PROSE" "$CJK" "$PROSE" "$CJK" > "$F/cjk-mixed.md"

# scope fixtures: a URL ending in .pdf under a web engine, a web capture, and no provenance at all
printf -- '---\nconverted_from: https://example.org/files/paper.pdf?download=1\nconverted_by: jina\n---\n\n# URL PDF\n\n%s\n' "$PROSE" > "$F/scope-url-pdf.md"
printf -- '---\nconverted_from: https://example.org/page\nconverted_by: defuddle\n---\n\n# Web\n\n%s\n' "$PROSE" > "$F/scope-web.md"
printf -- '# No provenance\n\n%s\n' "$PROSE" > "$F/scope-none.md"

# the PDF pair: a minimal one-page PDF carrying three sentences of six words or more, one
# conversion that holds them (recovery 1.00) and one that holds other prose (recovery 0.00),
# a conversion whose converted_from: names a PDF under a different stem, and a clean .md beside
# a garbage .pdf (pdftotext must fail on it, and the verdict must rest on the other measures)
"$PY" - "$T/withpdf" <<'PYFIX'
import os, sys
d = sys.argv[1]
lines = ["The quick brown fox jumps over the lazy dog today.",
         "A second sentence with more than six words sits here.",
         "The third sentence also carries more than six words in total."]
def esc(s): return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
content = "BT /F1 12 Tf 72 720 Td 16 TL " + " ".join("(%s) Tj T*" % esc(l) for l in lines) + " ET"
objs = ["<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        "<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
out = "%PDF-1.4\n"; offsets = []
for i, o in enumerate(objs, 1):
    offsets.append(len(out)); out += "%d 0 obj\n%s\nendobj\n" % (i, o)
xref = len(out)
out += "xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
for off in offsets: out += "%010d 00000 n \n" % off
out += "trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
for name in ("good.pdf", "bad.pdf", "other-name.pdf"):
    open(os.path.join(d, name), "wb").write(out.encode("latin-1"))
open(os.path.join(d, "garbage.pdf"), "wb").write(b"%PDF-1.4\ngarbage that is not a pdf body\n")
prose = " ".join(lines)
open(os.path.join(d, "good.md"), "w").write("---\nconverted_by: markitdown\n---\n\n# Good\n\n" + prose + "\n")
open(os.path.join(d, "bad.md"), "w").write("---\nconverted_by: markitdown\n---\n\n# Bad\n\nEntirely different prose that shares no sentence with the document it claims to convert, written at some length so that the body is not empty.\n")
open(os.path.join(d, "named.md"), "w").write("---\nconverted_from: other-name.pdf\nconverted_by: markitdown\n---\n\n# Named\n\n" + prose + "\n")
open(os.path.join(d, "garbage.md"), "w").write("---\nconverted_by: markitdown\n---\n\n# Garbage PDF beside a clean conversion\n\n" + prose + "\n")
PYFIX

: > "$F/empty.md"
printf -- '---\nconverted_by: markitdown\n---\n' > "$F/fm-only.md"
mkdir -p "$F/only-good"; cp "$F/clean.md" "$F/only-good/clean.md"; cp "$F/cjk.md" "$F/only-good/cjk.md"
mkdir -p "$F/mixed"; cp "$F/clean.md" "$F/collapsed.md" "$F/joined.md" "$F/cjk.md" "$F/mixed/"
cp "$T/withpdf/good.md" "$T/withpdf/good.pdf" "$T/withpdf/bad.md" "$T/withpdf/bad.pdf" "$F/mixed/"

score(){ "$PY" -B "$SCORE" "$@" 2>"$ERR"; }
tokens(){ printf '%s\n' "$1" | sed -n 's/.*run-together [0-9.]* % ([<>=]* [0-9.]* %; [0-9]*\/\([0-9]*\) tokens).*/\1/p'; }

echo '--- verdicts ---'
OUT="$(score "$F/collapsed.md")"; rc=$?
eq "a collapsed conversion (one-character lines) is suspect, exit 3" "3" "$rc"
eq "  the short-line share is the reason, printed with its threshold" "1" "$(has "^suspect .*short-lines [89][0-9]\.[0-9] % (> $TS" "$OUT")"
eq "  its run-together share is below threshold (single letters are not joins)" "1" "$(has "run-together 0\.0 % (<= $TR" "$OUT")"
eq "  its long-run rate is zero" "1" "$(has "long-run 0\.0 /1k (<= $TL; 0 runs/" "$OUT")"
eq "  recovery is n/a with no sibling PDF" "1" "$(has 'recovery n/a (no sibling PDF)' "$OUT")"

OUT="$(score "$F/joined.md")"; rc=$?
eq "a run-together conversion (joined words) is suspect, exit 3" "3" "$rc"
eq "  the run-together share is the reason, printed with its threshold" "1" "$(has "^suspect .*run-together [1-9][0-9]\.[0-9] % (> $TR" "$OUT")"
eq "  its short-line share is below threshold" "1" "$(has "short-lines 0\.0 % (<= $TS" "$OUT")"

OUT="$(score "$F/clean.md")"; rc=$?
eq "a clean conversion reads clean, exit 0" "0" "$rc"
eq "  the verdict line retains the original four measures and the scope" "1" "$(has "^clean .*short-lines 0\.0 % (<= $TS.*run-together 0\.0 % (<= $TR.*long-run 0\.0 /1k (<= $TL.*recovery n/a (no sibling PDF) · scope: pdf (converted_by markitdown)" "$OUT")"
eq "  the public summary retains all five operational thresholds" "1" "$(has "^SCORED: 1 file(s) · clean 1 · suspect 0 · scope pdf 1 | other 0 · thresholds short-lines > $TS | run-together > $TR | long-run > $TL | recovery < $TC (.*) | readable-words < 0\.367 " "$OUT")"
CLEAN_TOKENS="$(tokens "$OUT")"
eq "  (arm) the clean file's token count is read for the exclusion legs" "1" "$(printf '%s\n' "$CLEAN_TOKENS" | grep -c '^[1-9][0-9]*$')"

OUT="$(score "$F/cjk.md")"; rc=$?
eq "a non-Latin-majority conversion takes n/a on run-together and says why" "1" "$(has 'run-together n/a (non-Latin-majority text: no inter-word spaces to lose)' "$OUT")"
eq "  and n/a on long-run" "1" "$(has 'long-run n/a (non-Latin-majority text)' "$OUT")"
eq "  and its verdict rests on the other measures (clean, exit 0)" "0-1" "$rc-$(has '^clean ' "$OUT")"

echo '--- the long-run measure (the skill probe (a), register entry H1) ---'
OUT="$(score "$F/runs.md")"; rc=$?
eq "twelve 25-letter runs in 1,100 words: suspect on long-run alone, exit 3" "3-1" "$rc-$(has "^suspect .*long-run 1[0-9]\.[0-9] /1k (> $TL; 12 runs/" "$OUT")"
eq "  while its run-together share stays under threshold (the share alone would miss it)" "1" "$(has "run-together [0-3]\.[0-9] % (<= $TR" "$OUT")"
OUT="$(score "$F/runs-few.md")"; rc=$?
eq "two runs in 110 words: the rate is over threshold but under the ten-run floor, so clean" "0-1" "$rc-$(has "^clean .*long-run [1-9][0-9]\.[0-9] /1k (<= $TL; 2 runs/" "$OUT")"

echo '--- exclusions from the run-together measure (register entry M3) ---'
OUT="$(score "$F/excl-fence-control.md")"; rc=$?
eq "control: 100 CamelCase identifiers in the open fire the run-together share (exit 3)" "3-1" "$rc-$(has "^suspect .*run-together [1-9][0-9]\.[0-9] % (> $TR; 100/" "$OUT")"
OUT="$(score "$F/excl-fence.md")"; rc=$?
eq "the same identifiers inside a fenced code block are excluded: clean, 0 hits" "0-1" "$rc-$(has "^clean .*run-together 0\.0 % (<= $TR; 0/" "$OUT")"
eq "  and excluded from the denominator too (the token count equals the clean file's)" "$CLEAN_TOKENS" "$(tokens "$OUT")"
OUT="$(score "$F/excl-tag.md")"; rc=$?
eq "an angle-bracket tag with a base64 attribute and CamelCase class names is excluded whole; the element's text content is prose and stays (one token, one hit)" "0-$((CLEAN_TOKENS + 1))-1" "$rc-$(tokens "$OUT")-$(has "run-together 0\.[0-9] % (<= $TR; 1/" "$OUT")"
OUT="$(score "$F/excl-blob.md")"; rc=$?
eq "a bare base64-shaped blob is excluded from both sides" "0-$CLEAN_TOKENS" "$rc-$(tokens "$OUT")"
OUT="$(score "$F/digits-prose.md")"; rc=$?
eq "space-stripped prose carrying digits is NOT a blob (it keeps its vowels): still suspect" "3-1" "$rc-$(has "^suspect .*run-together [4-9]\.[0-9] % (> $TR; 20/" "$OUT")"
OUT="$(score "$F/cjk-mixed.md")"; rc=$?
eq "English prose with some 40 % CJK letters is scored on its Latin tokens only: 0.0 %, clean" "0-1" "$rc-$(has "^clean .*run-together 0\.0 % (<= $TR" "$OUT")"

echo '--- scope (derived on PDF conversions of papers) ---'
OUT="$(score "$F/scope-url-pdf.md")"; rc=$?
eq "converted_from: a URL whose path ends in .pdf (query dropped) reads scope: pdf" "1" "$(has 'scope: pdf (converted_from names a PDF)' "$OUT")"
OUT="$(score "$F/scope-web.md")"; rc=$?
eq "a defuddle capture of a web page reads scope: other" "1" "$(has 'scope: other (web capture, converted_by defuddle)' "$OUT")"
OUT="$(score "$F/scope-none.md")"; rc=$?
eq "no provenance and no PDF evidence reads scope: other, and is still scored" "0-1" "$rc-$(has '^clean .*scope: other (no converted_by and no PDF evidence)' "$OUT")"
OUT="$(score "$T/withpdf/good.md")"; rc=$?
eq "a sibling PDF reads scope: pdf" "1" "$(has 'scope: pdf (sibling PDF)' "$OUT")"
OUT="$(score "$F/scope-web.md" "$F/clean.md")"; rc=$?
eq "the summary line tallies the scopes" "1" "$(has '^SCORED: 2 file(s) · clean 2 · suspect 0 · scope pdf 1 | other 1' "$OUT")"

echo '--- recovery against pdftotext ---'
OUT="$(score "$T/withpdf/good.md")"; rc=$?
eq "a conversion holding every pdftotext sentence recovers 1.00 and reads clean" "0-1" "$rc-$(has "^clean .*recovery 1\.00 (>= $TC; 3/3 sentences)" "$OUT")"
OUT="$(score "$T/withpdf/bad.md")"; rc=$?
eq "a conversion holding none of them recovers 0.00 and is suspect on recovery alone" "3-1" "$rc-$(has "^suspect .*run-together 0\.0 % (<= $TR.*recovery 0\.00 (< $TC; 0/3 sentences)" "$OUT")"
OUT="$(score "$T/withpdf/named.md")"; rc=$?
eq "the PDF converted_from: names is used when it exists beside the conversion" "0-1" "$rc-$(has "^clean .*recovery 1\.00 (>= $TC; 3/3 sentences)" "$OUT")"

echo '--- pdftotext optional: absent or failing is n/a, never a premise failure (register entry M6) ---'
OUT="$(env CONVERSION_SCORE_PDFTOTEXT="$T/no-such-binary" "$PY" -B "$SCORE" "$T/withpdf/good.md" 2>"$ERR")"; rc=$?
eq "pdftotext missing while a sibling PDF exists: recovery n/a with the reason, clean, exit 0" "0-1" "$rc-$(has '^clean .*recovery n/a (pdftotext absent)' "$OUT")"
OUT="$(env CONVERSION_SCORE_PDFTOTEXT="$T/no-such-binary" "$PY" -B "$SCORE" "$T/withpdf/bad.md" 2>"$ERR")"; rc=$?
eq "  the verdict then rests on the other four text measures (the bad conversion reads clean without recovery)" "0-1" "$rc-$(has '^clean .*recovery n/a (pdftotext absent)' "$OUT")"
eq "  nothing on stderr" "0" "$(wc -c < "$ERR" | tr -d ' ')"
OUT="$(score "$T/withpdf/garbage.md")"; rc=$?
eq "a garbage PDF beside a clean .md: pdftotext fails, recovery n/a with its first stderr line, exit 0" "0-1" "$rc-$(has '^clean .*recovery n/a (pdftotext failed: [A-Za-z][^)]*)' "$OUT")"
OUT="$(score "$T/withpdf")"; rc=$?
eq "  control: the directory run still exits 3 on the bad conversion, with four files scored" "3-1" "$rc-$(has '^SCORED: 4 file(s) · clean 3 · suspect 1' "$OUT")"

echo '--- premise failures ---'
OUT="$(score "$F/empty.md")"; rc=$?
eq "an empty file is a premise failure (exit 2, no stdout, PROBE FAILED on stderr)" "2--1" "$rc-$OUT-$(grep -c 'PROBE FAILED: .*is empty' "$ERR")"
OUT="$(score "$F/fm-only.md")"; rc=$?
eq "a file with frontmatter and no body is a premise failure" "2-1" "$rc-$(grep -c 'PROBE FAILED: .*no body' "$ERR")"
OUT="$(score "$T/nomd")"; rc=$?
eq "a directory with no .md is a premise failure" "2-1" "$rc-$(grep -c 'PROBE FAILED: .*holds no .md file' "$ERR")"
OUT="$(score "$T/absent/none.md")"; rc=$?
eq "an unreadable file is a premise failure" "2-1" "$rc-$(grep -c 'PROBE FAILED: cannot read' "$ERR")"
OUT="$(score --deep "$F/clean.md")"; rc=$?
eq "an unknown flag is refused (exit 2), never read as a file" "2-1" "$rc-$(grep -c 'PROBE FAILED: unknown option' "$ERR")"
OUT="$(score --thresholds 1,2,3 "$F/clean.md")"; rc=$?
eq "a --thresholds with three values is refused (four or five values required)" "2-1" "$rc-$(grep -c 'PROBE FAILED: --thresholds wants SHORT,RUN,RECOVERY,LONGRUN' "$ERR")"

echo '--- exit codes over a directory ---'
OUT="$(score "$F/only-good")"; rc=$?
eq "every file clean: exit 0 with the tally" "0-1" "$rc-$(has '^SCORED: 2 file(s) · clean 2 · suspect 0 · scope pdf 2 | other 0' "$OUT")"
OUT="$(score "$F/mixed")"; rc=$?
eq "any file suspect: exit 3 with the tally (6 files, 3 suspect)" "3-1" "$rc-$(has '^SCORED: 6 file(s) · clean 3 · suspect 3' "$OUT")"
eq "  one verdict line per file" "6" "$(has '^\(clean\|suspect\) ' "$OUT")"

echo '--- negative controls: overrides that hide a measure ---'
OUT="$(score --thresholds 100,-,-,-,off "$F/collapsed.md")"; rc=$?
eq "with the short-line threshold set to 100 % the collapsed fixture reads clean (the measure is what decides)" "0-1" "$rc-$(has '^clean .*short-lines [89][0-9]\.[0-9] % (<= 100 %' "$OUT")"
eq "  the override is recorded on the summary line" "1" "$(has "^SCORED: .*thresholds short-lines > 100 % .*(override '100,-,-,-,off')" "$OUT")"
OUT="$(score "$F/collapsed.md")"; rc=$?
eq "  restored: the derived thresholds catch it again (exit 3)" "3-1" "$rc-$(has '^suspect ' "$OUT")"
OUT="$(score --thresholds -,-,-,off "$F/runs.md")"; rc=$?
eq "with the long-run measure switched off the SoK-shaped fixture reads clean (the brief's negative control)" "0-1" "$rc-$(has '^clean .*long-run 1[0-9]\.[0-9] /1k (<= n/a' "$OUT")"
OUT="$(score "$F/runs.md")"; rc=$?
eq "  restored: suspect again (exit 3)" "3-1" "$rc-$(has '^suspect ' "$OUT")"
OUT="$(score --thresholds -,-,off,- "$T/withpdf/bad.md")"; rc=$?
eq "a measure switched off ('off') prints n/a as its threshold and no longer decides" "0-1" "$rc-$(has '^clean .*recovery 0\.00 (>= n/a' "$OUT")"

echo '--- distribution and derivation ---'
OUT="$(score --distribution "$F/mixed")"; rc=$?
eq "--distribution prints the percentile table over every .md in the directory, with the scope tally" "0-1" "$rc-$(has '^DISTRIBUTION over .*: 6 files (6 scope pdf, 0 other)' "$OUT")"
eq "  each original measure retains min p10 p25 p50 p75 p90 max" "4" "$(has '^\(short-lines %\|run-together %\|long-run /1k\|recovery\) ' "$OUT")"
eq "  the recovery row states its n/a count" "1" "$(has '^recovery  *2 (4 n/a)' "$OUT")"
printf 'raw/2-papers/collapsed.md\nraw/2-papers/joined.md\nraw/2-papers/bad.md\n' > "$T/positives.txt"
OUT="$(score --derive "$F/mixed" --positives "$T/positives.txt")"; rc=$?
eq "--derive prints ranges, thresholds and the combined precision and recall" "0-1" "$rc-$(has '^combined verdict at these thresholds: suspect 3 · clean 3 · true positives 3 · false positives 0 · false negatives 0 · precision 1\.000 · recall 1\.000' "$OUT")"
eq "  the positives are matched on the basename of a vault-relative path" "1" "$(has '^DERIVATION over .*: 6 files · positives 3 (from ' "$OUT")"
eq "  each of the original four measures states the gap its threshold is the midpoint of, or that it does not separate" "4" "$(has '^  \(short-lines %\|run-together %\|long-run /1k\|recovery\) .*\(midpoint of the gap\|does not separate\)' "$OUT")"
eq "  the worst and next-worst clean files are named for every original measure with a negative" "4" "$(has '^ *worst clean [^ ]*\.md (' "$OUT")"
eq "  a fixture-derived cut is compared with the baked-in one and the difference is said" "1" "$(has '^baked-in thresholds .*DIFFER FROM the derived' "$OUT")"
printf 'raw/2-papers/no-such-file.md\n' > "$T/positives-bad.txt"
OUT="$(score --derive "$F/mixed" --positives "$T/positives-bad.txt")"; rc=$?
eq "a positive not found in the directory is a premise failure" "2-1" "$rc-$(grep -c 'PROBE FAILED: 1 positive(s) not found' "$ERR")"

echo '--- readable-words: word-letter share, the fourth text arm ---'
"$PY" -B - "$T" "$SCORE" "$PROSE" <<'PYREADABLE'
import importlib.util, math, sys
from pathlib import Path
folder = Path(sys.argv[1]) / "readable"
folder.mkdir()
spec = importlib.util.spec_from_file_location("scorer", sys.argv[2])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
# Both embedded cases use the same synthetic body size, set by judgement, unmeasured;
# the repetition count is the ceiling of target bytes divided by the seed's byte length.
size = 10000
glyphs = "a ab abc 12345 | -- ! \n"
body = (glyphs * math.ceil(size / len(glyphs)))[:size]
prose = (sys.argv[3] + "\n")
clean_body = (prose * math.ceil(size / len(prose)))[:size]
head = "---\ntitle: A perfectly readable source title\nconverted_by: markitdown\n---\n"
(folder / "destroyed.md").write_text(head + body)
(folder / "control.md").write_text(head + clean_body)
(folder / "damaged.md").write_text("word " + "a " * 100)  # 4 / (4 + 100) word-letter share
(folder / "digits.md").write_text("1234567890\n" * 20)
(folder / "fragments.md").write_text("abc中def")  # two three-letter runs; six ASCII letters
# Neighbouring ASCII-letter counts straddle the derived cut with the same 400 word letters.
base = "word " * 100
word_letters = 4 * 100
at_or_above = math.floor(word_letters / module.THRESHOLD_READABLE)
for name, letters in (("above", at_or_above), ("below", at_or_above + 1)):
    (folder / (name + ".md")).write_text(base + "a " * (letters - word_letters))
(folder / "equal.md").write_text("word a a a a")  # 4 / 8 ASCII letters = 0.5 exactly
# One padding row per prose byte deliberately outweighs the readable text; no row adds a letter.
padding = "| 1234567890 -- $ {} [] |\n" * len(clean_body)
(folder / "padded.md").write_text(head + clean_body + padding)
# Keep the derivation fixture free of digits-only premise cases and label its destroyed class.
calibration = Path(sys.argv[1]) / "readable-derive"
calibration.mkdir()
for name in ("destroyed.md", "control.md"):
    (calibration / name).write_bytes((folder / name).read_bytes())
(Path(sys.argv[1]) / "readable-positives.txt").write_text("destroyed.md\n")
PYREADABLE
READABLE="$T/readable"
OUT="$(score "$READABLE/destroyed.md")"; rc=$?
eq 'R3-destroyed: zero readable-word letters fire despite a readable YAML title' '3-1' "$rc-$(has '^suspect .*readable-words 0\.000 (< 0\.367; 0/.*damage: destroyed' "$OUT")"
eq 'R3-controls: same-run damaged and clean controls discriminate' '1' "$(has '^controls: readable-words zero-run body caught; readable prose passed; frontmatter excluded; non-letter padding ignored' "$OUT")"
OUT="$(score "$READABLE/damaged.md")"; rc=$?
eq 'R3-damaged: low non-zero word-letter share fires as damaged' '3-1' "$rc-$(has '^suspect .*readable-words .*damage: damaged' "$OUT")"
OUT="$(score "$READABLE/digits.md")"; rc=$?
eq 'R3-digits: digits only are a broken premise, never clean' '2--1' "$rc-$OUT-$(grep -c 'PROBE FAILED: .*holds no word token' "$ERR")"
OUT="$(score "$F/empty.md")"; rc=$?
eq 'R3-empty: empty input remains a broken premise' '2--1' "$rc-$OUT-$(grep -c 'PROBE FAILED: .*is empty' "$ERR")"
OUT="$(score "$READABLE/above.md")"; rc=$?
eq 'R3-boundary-clean: share just above the cut stays clean with its control' '0-1-1' "$rc-$(has '^clean .*readable-words' "$OUT")-$(has '^controls: readable-words zero-run body caught' "$OUT")"
OUT="$(score "$READABLE/below.md")"; rc=$?
eq 'R3-boundary-damaged: one extra short-run letter crosses the share cut' '3-1' "$rc-$(has '^suspect .*damage: damaged' "$OUT")"
OUT="$(score --thresholds off,off,off,off,0.5 "$READABLE/equal.md")"; rc=$?
eq 'R3-equality: share equal to the cut is clean' '0-1' "$rc-$(has '^clean .*readable-words 0\.500 (>= 0\.5; 4/8 ASCII letters)' "$OUT")"
OUT="$(score --thresholds off,off,off,off "$READABLE/destroyed.md")"; rc=$?
eq 'R3-legacy-override: four threshold values keep the readable-words arm' '3-1' "$rc-$(has '^suspect .*readable-words 0\.000' "$OUT")"
OUT="$(score --thresholds -,-,-,-,off "$READABLE/destroyed.md")"; rc=$?
eq 'R3-disabled-control: disabling only the share arm restores the old clean result' '0-1' "$rc-$(has '^clean .*readable-words 0\.000 (>= n/a' "$OUT")"
OUT="$(score "$F/cjk.md")"; rc=$?
eq 'R3-language-scope: non-Latin-majority text takes n/a, staying clean' '0-1' "$rc-$(has '^clean .*readable-words n/a (non-Latin-majority text)' "$OUT")"
OUT="$(score "$READABLE/fragments.md")"; rc=$?
eq 'R3-fragments: non-ASCII letters separate short fragments rather than joining a readable run' '3-1' "$rc-$(has '^suspect .*readable-words 0\.000 (< 0\.367; 0/6 ASCII letters)' "$OUT")"
OUT="$(score --help)"; rc=$?
eq 'R3-help: the new arm, formula, severity and override are named' '0-1-1-1' "$rc-$(has '^Measures: .*readable-words' "$OUT")-$(has 'all ASCII body letters' "$OUT")-$(has 'fifth overrides' "$OUT")"
if printf '%s\n' "$OUT" | grep -q 'letters in runs of four or more divided by all ASCII body letters'; then ok 'R3-help-definition: the word-letter share formula is explicit'; else no 'R3-help-definition'; fi
for bad in nan inf -1 letters; do
  OUT="$(score --thresholds "-,-,-,-,$bad" "$F/clean.md")"; rc=$?
  eq "R3-threshold-premise: $bad is refused" '2-1' "$rc-$(grep -c 'PROBE FAILED: --thresholds value' "$ERR")"
done
OUT="$(score --thresholds -,-,-,-,1.1 "$F/clean.md")"; rc=$?
eq 'F3-share-range: an override above one is refused' '2-1' "$rc-$(grep -c 'PROBE FAILED: --thresholds readable-words value' "$ERR")"
OUT="$(score --distribution "$F/mixed")"; rc=$?
eq 'R3-distribution: the new row carries a language n/a census' '0-1' "$rc-$(has '^readable-words .* (1 n/a)' "$OUT")"
OUT="$(score --derive-readable "$T/readable-derive" --positives "$T/readable-positives.txt")"; rc=$?
eq 'R3-derive: the destroyed class sets its own midpoint cut' '0-1' "$rc-$(has '^  readable-words .*threshold < .*midpoint of the gap' "$OUT")"
eq 'F3-boundaries: derivation names both boundary files and the half-gap margin' '1' "$(has '^  boundaries: control\.md .*destroyed\.md .*half-gap margin' "$OUT")"
eq 'F3-corpus-separation: readable derivation contains only the requested arm' '1-0' "$(has '^arm: readable-words only' "$OUT")-$(has '^  short-lines % ' "$OUT")"
DERIVATION="$("$PY" -B - "$T/readable-derive" "$OUT" <<'PY_DERIVATION_CONTROL'
import re, sys
from decimal import Decimal
from pathlib import Path
root, output = Path(sys.argv[1]), sys.argv[2]
def share(name):
    body = re.sub(r"\A---\n.*?\n---\n", "", (root / name).read_text(), count=1, flags=re.S)
    letters = len(re.findall(r"[A-Za-z]", body))
    words = sum(map(len, re.findall(r"[A-Za-z]{4,}", body)))
    return Decimal(words) / Decimal(letters)
clean, damaged = share("control.md"), share("destroyed.md")
expected = (clean, damaged, (clean + damaged) / 2, abs(clean - damaged) / 2)
# One unit in the reported fifteen-decimal place covers formatting round-off.
tolerance = Decimal("0.000000000000001")
def valid(text):
    match = re.search(r"^  boundaries: control\.md ([0-9.]+) · destroyed\.md ([0-9.]+) · midpoint ([0-9.]+) · half-gap margin ([0-9.]+)$", text, re.M)
    return bool(match) and all(abs(Decimal(got) - want) <= tolerance
                               for got, want in zip(match.groups(), expected))
planted = re.sub(r"(· midpoint )[0-9.]+", r"\g<1>9.0", output, count=1)
print("ok control caught" if valid(output) and not valid(planted)
      else "PROBE FAILED: derived boundary or planted midpoint control")
PY_DERIVATION_CONTROL
)"
eq 'R3-derivation-provenance: boundary shares, midpoint and margin match the supplied fixture; a false midpoint fails' 'ok control caught' "$DERIVATION"
OUT="$(score --derive "$F/mixed" --positives "$T/positives.txt")"; rc=$?
eq 'F3-original-derivation: the older corpus cannot set readable-words' '0-1-0' "$rc-$(has '^arms: original four only' "$OUT")-$(has '^  readable-words ' "$OUT")"
OUT="$(score --derive-readable "$T/readable-derive")"; rc=$?
eq 'F3-derive-premise: missing option arguments fail closed' '2-1' "$rc-$(grep -c 'PROBE FAILED: --derive-readable DIR --positives FILE' "$ERR")"
OUT="$(score --derive-readable "$T/readable-derive" --positives "$T/absent-positives.txt")"; rc=$?
eq 'F3-derive-premise: missing labels fail closed' '2-1' "$rc-$(grep -c 'PROBE FAILED: cannot read positives' "$ERR")"
: > "$T/empty-positives.txt"
OUT="$(score --derive-readable "$T/readable-derive" --positives "$T/empty-positives.txt")"; rc=$?
eq 'F3-derive-premise: empty labels fail closed' '2-1' "$rc-$(grep -c 'PROBE FAILED: .*lists no positive' "$ERR")"
OUT="$(score --derive-readable "$T/readable-derive" --positives "$T/positives-bad.txt")"; rc=$?
eq 'F3-derive-premise: an absent positive fails closed' '2-1' "$rc-$(grep -c 'PROBE FAILED: 1 positive(s) not found' "$ERR")"
printf 'control.md\ndestroyed.md\n' > "$T/all-positives.txt"
OUT="$(score --derive-readable "$T/readable-derive" --positives "$T/all-positives.txt")"; rc=$?
eq 'F3-derive-premise: no negative class fails closed' '2-1' "$rc-$(grep -c 'PROBE FAILED: readable-words derivation needs usable positive and negative shares' "$ERR")"
printf 'cjk.md\n' > "$T/cjk-positive.txt"
OUT="$(score --derive-readable "$F/mixed" --positives "$T/cjk-positive.txt")"; rc=$?
eq 'F3-derive-premise: no usable positive share fails closed' '2-1' "$rc-$(grep -c 'PROBE FAILED: readable-words derivation needs usable positive and negative shares' "$ERR")"
OUT="$(score "$READABLE/control.md" "$READABLE/padded.md")"; rc=$?
eq 'F1-F4-padding: readable prose remains clean when numeric and markup rows outweigh it' '0-1' "$rc-$(has '^SCORED: 2 file(s) · clean 2 · suspect 0' "$OUT")"
SHARE_ROWS="$(printf '%s\n' "$OUT" | sed -n 's/^clean .* · readable-words \([^;]*\); \([^)]*\)).*/\1; \2/p')"
SHARES="$(printf '%s\n' "$SHARE_ROWS" | sort -u)"
eq 'F2-padding-invariance: both verdicts retain the same letter count and share' '2-1' "$(printf '%s\n' "$SHARE_ROWS" | grep -c '^[0-9].*ASCII letters')-$(printf '%s\n' "$SHARES" | grep -c '^[0-9].*ASCII letters')"
OUT="$(score "$READABLE/destroyed.md" "$READABLE/control.md")"; rc=$?
eq 'R3-capture-pair: embedded glyph soup fires while the readable control stays clean' '3-1-1-1' "$rc-$(has '^suspect .*damage: destroyed' "$OUT")-$(has '^clean .*readable-words' "$OUT")-$(has '^SCORED: 2 file(s) · clean 1 · suspect 1' "$OUT")"
BODY_SIZES="$("$PY" -B - "$SCORE" "$READABLE/destroyed.md" "$READABLE/control.md" <<'PYSIZES'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("scorer", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print("-".join(str(len(module.split_frontmatter(module.read_text(p))[1].encode("utf-8"))) for p in sys.argv[2:]))
PYSIZES
)"
# Each body has the 10,000-byte target set in the fixture generator, excluding its YAML header.
eq 'F7-capture-size: embedded fixtures reproduce the approximately 10 kB body class' '10000-10000' "$BODY_SIZES"
# Real captures are an optional add-on; the mandatory embedded pair above always runs.
DAMAGE_CASE=${CONVERSION_SCORE_DAMAGED_FILE:-}
CLEAN_CASE=${CONVERSION_SCORE_CLEAN_FILE:-}
if [ -z "$DAMAGE_CASE$CLEAN_CASE" ]; then
  printf '%s\n' 'R3-real-capture-pair skipped (env unset)'
elif [ -f "$DAMAGE_CASE" ] && [ -f "$CLEAN_CASE" ]; then
  OUT="$(score "$DAMAGE_CASE" "$CLEAN_CASE")"; rc=$?
  eq 'R3-real-capture-pair: supplied destroyed capture fires while the readable control stays clean' '3-1-1-1' "$rc-$(has '^suspect .*damage: destroyed' "$OUT")-$(has '^clean .*readable-words' "$OUT")-$(has '^SCORED: 2 file(s) · clean 1 · suspect 1' "$OUT")"
  printf '%s\n' "$OUT"
else
  no 'R3-real-capture-pair: both external capture paths must be readable files'
fi
if grep -q 'recovery n/a · scope pdf · readable-words 0.950' "$HERE/SKILL.md"; then ok 'F7-step-eight: readable-words follows recovery and scope in the example'; else no 'F7-step-eight'; fi

echo '--- recovery: the pdftotext reference must itself be readable (register minor, 2026-09-17; fold of the critic finding) ---'
# A reference is unreadable only when its readable-words share is below that arm's cut AND its
# letter density (letters per character) is below the reference density cut, pinned here as TD.
# Real PDFs through the real pdftotext: scanned (a /Differences font whose glyph names map to no
# character, so pdftotext emits control bytes as a scanned layer does, with one two-letter group
# per line: share 0, density near 0.04) and lossy (three short-word born-digital sentences: share
# 13/81 = 0.160, density 81/115 = 0.704, which the share alone misread). The fake pdftotext prints
# the .txt beside the named PDF, so each boundary reference's census is exact by construction.
TD='0.306'
RR="$T/refread"; mkdir -p "$RR"
printf '#!/bin/sh\n# fake pdftotext: argv is -enc UTF-8 PDF -\ncat "${3%%.pdf}.txt"\n' > "$T/fake-pdftotext"
chmod +x "$T/fake-pdftotext"
"$PY" -B - "$RR" "$PROSE" <<'PYREFREAD'
import re, sys
from pathlib import Path
d, prose = Path(sys.argv[1]), sys.argv[2]
head = "---\nconverted_by: markitdown\n---\n\n# Reference fixture\n\n"
def pdf(lines, font):
    content = "BT /F1 12 Tf 72 720 Td 16 TL " + " ".join("(%s) Tj T*" % s for s in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            "<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content), font]
    out, offsets = "%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out)); out += "%d 0 obj\n%s\nendobj\n" % (i, o)
    xref = len(out)
    out += "xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + "".join("%010d 00000 n \n" % off for off in offsets)
    out += "trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return out.encode("latin-1")
helvetica = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
# codes 1-8 and 14-21 only: 9-13 would read as whitespace
codes = list(range(1, 9)) + list(range(14, 22))
names = " ".join("/glyph%s" % chr(65 + i) for i in range(21))
soup_font = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding << /Type /Encoding /Differences [1 %s] >> >>" % names
soup = [" ".join("".join("\\%03o" % codes[(line + group + k) % len(codes)] for k in range(3)) for group in range(10)) + " ab." for line in range(12)]
(d / "scanned.pdf").write_bytes(pdf(soup, soup_font))
(d / "scanned.md").write_text(head + prose + "\n")
lossy = ["We fit a sum of two terms to the data.", "The map is one to one and its rank is two.", "Let the sum of the two be one."]
(d / "lossy.pdf").write_bytes(pdf(lossy, helvetica))
(d / "lossy.md").write_text(head + prose + "\n")
def sentences(words):
    cut = len(words) - len(words) % 6
    groups = [words[i:i + 6] for i in range(0, cut, 6)]
    groups[-1].extend(words[cut:])
    return "\n".join(" ".join(g) + "." for g in groups) + "\n"
def exact(words, total):
    filler = []
    while len(sentences(words + filler + ["9999"])) <= total:
        filler.append("9999")
    text = sentences(words + filler)
    text = text[:-2] + "9" * (total - len(text)) + ".\n"   # pad the last word with digits
    assert len(text) == total, (len(text), total)
    return text
share_words = lambda long_run, extra: [long_run] + ["word"] * 90 + ["abc"] * 211 + extra   # 1,000 letters
cases = {"share-at-cut": exact(share_words("abcdefg", []), 5000),        # 367 / 1000; density 1000 / 5000
         "share-below-cut": exact(share_words("abcdef", ["a"]), 5000),   # 366 / 1000; density 1000 / 5000
         "density-at-cut": exact(["ab"] * 153, 1000),                    # 306 letters / 1000 characters
         "density-below-cut": exact(["ab"] * 152 + ["a"], 1000),         # 305 letters / 1000 characters
         "empty": "", "no-letters": "12 34 56 78 90 11. \x01\x02 \x03 \x04 \x05 \x06 \x07.\n",
         "cjk": "策略 梯度 方法 从 采样 的 轨迹 中 估计.\n"}
for name, text in cases.items():
    (d / (name + ".pdf")).write_bytes(b"%PDF-1.4\nplaceholder read by the fake pdftotext only\n")
    (d / (name + ".txt")).write_text(text, encoding="utf-8")
    body = prose
    if name == "cjk":
        body = "策略梯度方法从采样的轨迹中估计改进方向，并施加裁剪更新，使新策略与旧策略保持接近。" * 3
    (d / (name + ".md")).write_text(head + body + "\n", encoding="utf-8")
PYREFREAD
CENSUS="$("$PY" -B - "$SCORE" "$RR" "$TD" <<'PYCENSUS'
import importlib.util, re, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("scorer", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
cut = float(sys.argv[3])
side = lambda value, bound: "equal" if value == bound else "below" if value < bound else "above"
cells = []
for name in ("share-at-cut", "share-below-cut", "density-at-cut", "density-below-cut"):
    text = (Path(sys.argv[2]) / (name + ".txt")).read_text(encoding="utf-8")
    share, word_letters, letters = module.readable_word_share(text, True)
    density_letters = sum(len(run) for run in re.findall(r"[^\W\d_]+", text))   # counted by the suite itself, not the scorer
    cells.append("%s share %d/%d %s, density %d/%d %s" % (name, word_letters, letters, side(share, module.THRESHOLD_READABLE),
                 density_letters, len(text), side(density_letters / len(text), cut)))
print("; ".join(cells))
PYCENSUS
)"
eq '(arm) M2 reference census: each boundary reference sits exactly where its leg says' 'share-at-cut share 367/1000 equal, density 1000/5000 below; share-below-cut share 366/1000 below, density 1000/5000 below; density-at-cut share 0/306 below, density 306/1000 equal; density-below-cut share 0/305 below, density 305/1000 below' "$CENSUS"
eq 'M2-density-cut-pinned: the scorer retains the independently tested density cut and a judgement label' '1' "$(grep -c "^REFERENCE_LETTER_DENSITY = $TD  # .*set by judgement, unmeasured" "$SCORE")"
OUT="$(score "$RR/scanned.md")"; rc=$?
eq 'M2-scanned-reference: a real PDF whose text layer is control bytes leaves recovery n/a naming both measures, and the verdict follows the four text arms (clean, exit 0)' '0-1-0' "$rc-$(has '^clean .*recovery n/a (reference unreadable (readable-words 0\.000, letter density 0\.0[0-9][0-9])) · scope: pdf' "$OUT")-$(has 'recovery 0\.00' "$OUT")"
OUT="$(score "$RR/lossy.md")"; rc=$?
eq 'M2-lossy-short-prose: the critic case, three short-word born-digital sentences (share 0.160) the conversion lost, keeps numeric recovery and reads suspect' '3-1-0' "$rc-$(has "^suspect .*recovery 0\.00 (< $TC; 0/3 sentences)" "$OUT")-$(has 'reference unreadable' "$OUT")"
OUT="$(score --thresholds -,-,1,- "$RR/scanned.md")"; rc=$?
eq 'M2-never-a-reason: with the recovery cut raised to 1 an unreadable reference still adds no recovery reason' '0-1' "$rc-$(has '^clean .*recovery n/a (reference unreadable' "$OUT")"
OUT="$(score --thresholds -,-,-,-,off "$RR/scanned.md")"; rc=$?
eq 'M2-override-uncoupled: switching the conversion arm off leaves the reference judged against the baked cuts' '0-1' "$rc-$(has '^clean .*recovery n/a (reference unreadable (readable-words 0\.000, letter density 0\.0[0-9][0-9]))' "$OUT")"
OUT="$(score "$T/withpdf/bad.md" "$T/withpdf/good.md")"; rc=$?
eq 'M2-must-not-fire: a born-digital PDF keeps a numeric recovery, still suspect when the conversion lost the sentences' '3-1-1-0' "$rc-$(has "^suspect .*bad\.md .*recovery 0\.00 (< $TC; 0/3 sentences)" "$OUT")-$(has "^clean .*good\.md .*recovery 1\.00 (>= $TC; 3/3 sentences)" "$OUT")-$(has 'reference unreadable' "$OUT")"
fake(){ env CONVERSION_SCORE_PDFTOTEXT="$T/fake-pdftotext" "$PY" -B "$SCORE" "$@" 2>"$ERR"; }
OUT="$(fake "$RR/share-at-cut.md")"; rc=$?
eq 'M2-share-at-cut: share exactly at its cut (density below its own) is readable, so recovery stays numeric' '3-1-0' "$rc-$(has "^suspect .*recovery 0\.00 (< $TC; 0/[0-9]* sentences)" "$OUT")-$(has 'reference unreadable' "$OUT")"
OUT="$(fake "$RR/share-below-cut.md")"; rc=$?
eq 'M2-share-below-cut: one letter moved from a long run to a short one, with density below its cut: n/a naming both' '0-1' "$rc-$(has '^clean .*recovery n/a (reference unreadable (readable-words 0\.366, letter density 0\.200))' "$OUT")"
OUT="$(fake "$RR/density-at-cut.md")"; rc=$?
eq 'M2-density-at-cut: density exactly at its cut (share 0) is readable, so recovery stays numeric' '3-1-0' "$rc-$(has "^suspect .*recovery 0\.00 (< $TC; 0/[0-9]* sentences)" "$OUT")-$(has 'reference unreadable' "$OUT")"
OUT="$(fake "$RR/density-below-cut.md")"; rc=$?
eq 'M2-density-below-cut: one letter fewer puts density under its cut: n/a naming both' '0-1' "$rc-$(has '^clean .*recovery n/a (reference unreadable (readable-words 0\.000, letter density 0\.305))' "$OUT")"
OUT="$(fake "$RR/empty.md")"; rc=$?
eq 'M2-empty-reference: an empty text layer keeps the no-sentence reason, never a premise failure' '0-1-0-0' "$rc-$(has '^clean .*recovery n/a (pdftotext yielded no sentence of 6 words)' "$OUT")-$(has 'reference unreadable' "$OUT")-$(wc -c < "$ERR" | tr -d ' ')"
OUT="$(fake "$RR/no-letters.md")"; rc=$?
eq 'M2-no-letters: a text layer of digits and control bytes with no letter reads unreadable' '0-1' "$rc-$(has '^clean .*recovery n/a (reference unreadable (no letters))' "$OUT")"
OUT="$(fake "$RR/cjk.md")"; rc=$?
eq 'M2-non-latin-reference: a CJK reference, which the arm reads n/a, is compared as before (numeric recovery)' '3-1-0' "$rc-$(has '^suspect .*recovery 0\.00 (< 0\.15; 0/1 sentences)' "$OUT")-$(has 'reference unreadable' "$OUT")"
OUT="$(env CONVERSION_SCORE_PDFTOTEXT="$T/no-such-binary" "$PY" -B "$SCORE" "$RR/scanned.md" 2>"$ERR")"; rc=$?
eq 'M2-pdftotext-absent: with the binary missing the existing reason stands before any reference is read' '0-1' "$rc-$(has '^clean .*recovery n/a (pdftotext absent)' "$OUT")"
OUT="$(score --help)"; rc=$?
eq 'M2-help-and-skill: public help and documentation state the two-measure unreadable-reference rule' '1-1-1' "$(has '^Recovery: n/a (reference unreadable (readable-words <share>, letter density <density>))' "$OUT")-$(grep -c 'The recovery arm combines readable-word share and letter density' "$SCORE")-$(grep -c 'both readable-word share and letter density fall below their cuts' "$HERE/SKILL.md")"
# The owner's scanned pair is an optional add-on, like the real capture pair above.
SCANNED_CASE=${CONVERSION_SCORE_SCANNED_FILE:-}
if [ -z "$SCANNED_CASE" ]; then
  printf '%s\n' 'M2-real-scanned-pair skipped (env unset)'
elif [ -f "$SCANNED_CASE" ]; then
  OUT="$(score "$SCANNED_CASE")"; rc=$?
  eq 'M2-real-scanned-pair: the supplied scanned conversion reads recovery n/a naming both measures, verdict on the four text arms' '0-1' "$rc-$(has '^clean .*recovery n/a (reference unreadable (readable-words [0-9.]*, letter density [0-9.]*))' "$OUT")"
  printf '%s\n' "$OUT"
else
  no 'M2-real-scanned-pair: the supplied scanned conversion must be a readable file'
fi

echo '--- deciding numbers carry their derivation or the words set by judgement ---'
LABELS="$("$PY" -B - "$SCORE" <<'PY_OPERATIONAL_LABELS'
import ast, sys
from pathlib import Path
source = Path(sys.argv[1]).read_text(encoding="utf-8")
required = {"LONG_TOKEN", "LONG_RUN_FLOOR", "MIN_SENTENCE_WORDS", "PDFTOTEXT_TIMEOUT_S",
            "BLOB_MIN_CHARS", "BLOB_NO_VOWEL_RUN", "READABLE_RUN_RE", "REFERENCE_LETTER_DENSITY"}
phrase = "set by judgement, unmeasured"
def missing(text):
    lines = text.splitlines()
    assignments = {node.targets[0].id: node for node in ast.parse(text).body
                   if isinstance(node, ast.Assign) and len(node.targets) == 1
                   and isinstance(node.targets[0], ast.Name)}
    return sorted(name for name in required if name not in assignments
                  or phrase not in lines[assignments[name].lineno - 1])
lines = source.splitlines()
control = next(i for i, line in enumerate(lines) if line.startswith("LONG_TOKEN = "))
lines[control] = lines[control].replace(phrase, "control label removed")
planted = missing("\n".join(lines))
bad = missing(source)
print("ok control LONG_TOKEN" if not bad and "LONG_TOKEN" in planted
      else "PROBE FAILED: missing=%s control=%s" % (bad, planted))
PY_OPERATIONAL_LABELS
)"
eq "every required operational judgement constant is labelled; a removed label is caught" "ok control LONG_TOKEN" "$LABELS"
DEFAULTS="$("$PY" -B - "$SCORE" <<'PY_OPERATIONAL_DEFAULTS'
import ast, sys
from pathlib import Path
expected = {"THRESHOLD_SHORT": 57.57, "THRESHOLD_RUN": 4.41, "THRESHOLD_RECOVERY": 0.15,
            "THRESHOLD_LONG_RUN": 6.56, "THRESHOLD_READABLE": 0.367}
assignments = {node.targets[0].id: node.value for node in ast.parse(Path(sys.argv[1]).read_text()).body
               if isinstance(node, ast.Assign) and len(node.targets) == 1
               and isinstance(node.targets[0], ast.Name)}
bad = [name for name, value in expected.items()
       if name not in assignments or ast.literal_eval(assignments[name]) != value]
print("ok" if not bad else "PROBE FAILED: changed defaults " + ", ".join(bad))
PY_OPERATIONAL_DEFAULTS
)"
eq "the five operational thresholds retain their independent expected values" "ok" "$DEFAULTS"

echo '--- stdout-only proof (must run last) ---'
RO="$T/readonly"; cp -R "$F/mixed" "$RO"; cp "$T/withpdf/garbage.md" "$T/withpdf/garbage.pdf" "$RO/"
cp "$READABLE/destroyed.md" "$READABLE/damaged.md" "$RO/"
cp "$RR/scanned.md" "$RR/scanned.pdf" "$RR/lossy.md" "$RR/lossy.pdf" "$RO/"
BEFORE="$(manifest "$RO")"
chmod -R a-w "$RO"
score "$RO" > /dev/null; r1=$?
score "$RO/good.md" > /dev/null; r2=$?
score --distribution "$RO" > /dev/null; r3=$?
score --derive "$RO" --positives "$T/positives.txt" > /dev/null; r4=$?
score --thresholds 100,-,-,-,off "$RO/collapsed.md" > /dev/null; r5=$?
score --thresholds -,-,-,-,off "$RO/destroyed.md" > /dev/null; r7=$?
RO_READABLE="$(score "$RO/destroyed.md")"; r8=$?
score --derive-readable "$RO" --positives "$T/readable-positives.txt" > /dev/null; r9=$?
env CONVERSION_SCORE_PDFTOTEXT="$T/no-such-binary" "$PY" -B "$SCORE" "$RO/good.md" > /dev/null 2>"$ERR"; r6=$?
chmod -R u+w "$RO"
AFTER="$(manifest "$RO")"
eq "every mode runs against a chmod -R a-w copy (exits 3 0 0 0 0 0)" "3 0 0 0 0 0" "$r1 $r2 $r3 $r4 $r5 $r6"
eq "R3-readonly: enabled and disabled share keep their verdicts and control" "0-3-1-1" "$r7-$r8-$(has 'damage: destroyed' "$RO_READABLE")-$(has '^controls: readable-words zero-run body caught' "$RO_READABLE")"
eq "F3-readonly-derivation: separate readable-words mode reads the protected copy" "0" "$r9"
if [ "$(hashes "$BEFORE")" -ge 10 ] && [ "$BEFORE" = "$AFTER" ]; then ok "the read-only copy's checksum manifest is unchanged after every mode ($(hashes "$BEFORE") files)"
else no "the read-only copy's checksum manifest is unchanged  [$(hashes "$BEFORE") before, $(hashes "$AFTER") after]"; fi
END_H="$(manifest "$HERE")"
if [ "$(hashes "$END_H")" -ge 2 ] && [ "$START_H" = "$END_H" ]; then ok "the script home is byte-identical to its pre-run baseline"
else no "the script home is byte-identical to its pre-run baseline"; fi
# Source grep: every write pattern, each matched on its own control line so a dead pattern
# cannot vouch for the list. The scorer's one subprocess is pdftotext with `-` (stdout) as
# its output argument, asserted separately.
npat(){ pat="$1"; shift; grep -oE -- "$pat" "$@" | wc -l | tr -d ' '; }
CTL="$(printf '%s\n' 'open("x", "w")' 'p.write_text(s)' 'q.write_bytes(b)' 'os.remove(p)' 'os.unlink(p)' \
  'os.rename(a, b)' 'os.replace(a, b)' 'os.mkdir(d)' 'os.rmdir(d)' 'os.makedirs(d)' 'shutil.copy(a, b)' \
  'tempfile.mkdtemp()' 'os.system(c)' 'os.popen(c)' 'print(x, file=open("f", "w"))')"
hits=0; dead=""
for pat in 'open\([^)]*["'"'"'][wax]' 'write_text' 'write_bytes' 'os\.remove' 'os\.unlink' 'os\.rename' \
           'os\.replace' 'os\.mkdir' 'os\.rmdir' 'makedirs' 'shutil\.' 'tempfile' 'os\.system' 'os\.popen' \
           'print\(.*file=open'; do
  hits=$((hits + $(npat "$pat" "$SCORE")))
  if [ "$(printf '%s\n' "$CTL" | npat "$pat" -)" -eq 0 ]; then dead="$dead $pat"; fi
done
if [ -n "$dead" ]; then no "every write pattern matches its own control line  [dead:$dead]"
elif [ "$hits" -eq 0 ]; then ok "no write pattern appears in the scorer's source (15 patterns, each matched on its own control line)"
else no "no write pattern appears in the scorer's source  [$hits hit(s)]"; fi
SUB="$(grep -c 'subprocess\.run(' "$SCORE")"; SUBOUT="$(grep -c 'subprocess\.run(\[exe, "-enc", "UTF-8", pdf, "-"\]' "$SCORE")"
eq "the only subprocess call is pdftotext with stdout as its output" "1-1" "$SUB-$SUBOUT"

N=$((PASS + FAIL))
printf '\n'
if [ "$FAIL" -eq 0 ]; then printf 'PASS %d/%d\n' "$PASS" "$N"; else printf 'FAIL %d/%d\n' "$FAIL" "$N"; fi
[ "$FAIL" -eq 0 ]
