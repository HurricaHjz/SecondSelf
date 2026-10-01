#!/usr/bin/env python3
"""Score a Markdown conversion for source damage — ingest Step 0's guard.

Stdout-only: this script reads conversions and their PDFs, calls `pdftotext` with its output
on stdout, and writes no file anywhere. It never modifies, creates, moves or deletes anything.

This scorer detects collapsed line structure and lost inter-word spaces before compilation.
Its `suspect` verdict supplies the
# References: known-issues 2026-09-08.
observable Step 0 records as `flagged:` on the source page (never a prose note).

THE FIVE MEASURES (four text arms plus optional PDF recovery; per file; the body is every line below the YAML frontmatter, or the whole
file when there is no frontmatter)
  short-lines %   the share of NON-BLANK body lines whose stripped content is one character
                  or less, over all non-blank body lines. A blank line is a paragraph break in
                  every Markdown conversion and is counted on neither side; a line of one
                  character is what the structural collapse produces (a word or glyph per line).
  run-together %  the share of Latin word tokens that carry an internal lower-to-upper case
                  join or are longer than LONG_TOKEN letters, over all Latin word tokens, after
                  the exclusions below. Token rule, exactly: a token is a maximal run of Latin
                  letters (a letter is Latin when its Unicode name starts with `LATIN`, so the
                  ligature glyphs a PDF leaves count; a digit, an underscore, a hyphen, an
                  apostrophe, punctuation or a letter of another script ends a token — a CJK run
                  is never a token and never a hit). A token counts as run-together when (a) any
                  lower-case character is immediately followed by an upper-case one, or (b) it
                  has more than LONG_TOKEN letters. Rule (a) catches `algorithmsWe propose`,
                  rule (b) catches `thepolicygradientmethod`; a legitimate CamelCase identifier
                  or a 19-letter word is a false hit, and the derived threshold absorbs that
                  floor. Excluded from numerator and denominator alike, because they are not
                  prose and their tokens are not evidence about the prose: (1) fenced code
                  blocks (a line opening with three or more backticks or tildes to the matching
                  closer, or to the end of the file when unclosed, as CommonMark reads it);
                  (2) angle-bracket tags with everything inside the brackets (`<` up to the next
                  `>`, tag name, attributes and attribute values — the `<latexit sha1_base64="…">`
                  blobs a LaTeXML page leaves live there); (3) base64-shaped blobs — a maximal run
                  of 40 or more characters from the base64 and URL-safe alphabet
                  (`A–Z a–z 0–9 + / = _ -`) that carries at least one letter, at least one digit
                  and a run of six or more consecutive characters none of which is a vowel
                  (`a e i o u y`, either case). Space-stripped prose with a year or a table
                  number inside it keeps a vowel every few letters and so survives the blob rule;
                  base64, hex digests and data-URI payloads do not. The 40 and the six are set by
                  judgement, unmeasured (an English word runs six consonants only in rarities
                  such as `rhythms`, which the `y` clause absorbs). `n/a` on a non-Latin-majority
                  body: when most letters after the exclusions are outside the Latin script there
                  are no inter-word spaces to lose, and the verdict rests on the other measures.
                  `n/a` too when the body holds no word token at all (see exit 2).
  long-run /1k    runs of 25 or more ASCII Latin letters (`[A-Za-z]{25,}`) per 1,000
                  whitespace-separated words of the body — the ingest skill's own Step 0 probe
                  (a), the same rule with none of the exclusions above, so the two agree on what
                  they count. The skill reads the whole file; this scorer reads the body.
                  Fires when the rate crosses its threshold AND the body holds
                  at least LONG_RUN_FLOOR runs — the skill's own floor, set by judgement,
                  unmeasured, which keeps a very short capture off the gate. `n/a` on a
                  non-Latin-majority body for the reason given above (the skill's 3b makes the
                  same CJK carve-out for its chars-per-word mean).
  readable-words  word-letter share: ASCII letters inside runs of four or more letters
                  divided by all ASCII letters in the body. YAML frontmatter contributes
                  neither numerator nor denominator. Digits, punctuation and markup padding
                  bytes are not ASCII letters and cannot dilute this share. All body ASCII
                  letters count, including those in code or tags; unlike run-together, this arm
                  does not use prose exclusions. A long run still contributes all its letters:
                  joined-word damage remains the other arms' job. This is a word-shape proxy,
                  not a dictionary or proof of meaningful prose. It is n/a on a non-Latin-majority
                  body or with no ASCII letters. A diacritic-heavy Latin-script body (Vietnamese,
                  where few words carry four plain ASCII letters in a row) reads destroyed under
                  this proxy: such captures are outside its validated scope. A
                  Unicode-letter run count needs local calibration. Zero share is `damage: destroyed`; a low
                  non-zero share is `damage: damaged`; both keep `suspect` and exit 3.
  recovery        sentence recovery against `pdftotext` (flow order, no `-layout`) when a
                  sibling PDF exists: the fraction of pdftotext sentences of MIN_SENTENCE_WORDS
                  words or more that are found verbatim in the conversion after whitespace
                  normalisation (every run of whitespace on either side collapsed to one space,
                  the text lower-cased and NFKC-normalised so a ligature glyph and its letters
                  compare equal). A sentence is a maximal run of text ended by `.`, `!` or `?`
                  followed by whitespace, and counts when it has MIN_SENTENCE_WORDS or more
                  whitespace-separated words. The PDF is the file `converted_from:` names when
                  that value is a local `.pdf` name beside the conversion, else `<stem>.pdf`
                  beside it; with neither the measure is `n/a (no sibling PDF)`. `pdftotext` is
                  optional and serves this measure only: when the binary is absent the measure
                  reads `n/a (pdftotext absent)`, when it exits non-zero or times out it reads
                  `n/a (pdftotext failed: <first stderr line>)`, and in every `n/a` case the
                  verdict rests on the other four text measures and the exit code is 0 or 3, never 2.
                  The reference must itself be readable: a scanned PDF's text layer can be glyph
                  soup that no conversion holds. Before the comparison the pdftotext text is
                  judged on two measures, and it is unreadable only when BOTH fire: the
                  readable-words arm below (its measure, its Latin-majority test and its cut) reads
                  it below that cut, AND its letter density (letters of any script per character)
                  is below REFERENCE_LETTER_DENSITY. Unreadable, the measure reads
                  `n/a (reference unreadable (readable-words <share>, letter density <density>))`,
                  and with no letter at all `n/a (reference unreadable (no letters))`, so it never
                  adds `recovery` to the reasons. A short readable reference can have a low
                  word-letter share and normal letter density; a destroyed layer holds almost no letter. A value
                  equal to either cut is readable, as for the arm itself; an empty reference keeps
                  `n/a (pdftotext yielded no sentence of 6 words)`; a reference the arm reads n/a
                  (non-Latin-majority) is compared as before. Reusing the share cut on the
                  reference is set by judgement, unmeasured for a new corpus.

SCOPE (printed per file as `scope: pdf` or `scope: other`, with the evidence in brackets)
  The thresholds are derived on PDF conversions of papers, so `pdf` is the scope they were
  measured in. A file is `pdf` when any of three facts holds: `converted_from:` names a `.pdf`
  (a local file name or a URL whose path ends in `.pdf`); a `.pdf` sibling with the file's own
  stem exists; or `converted_by:` names one of the ingest skill's two document-conversion
  routes (`markitdown`, `agent`), the routes a PDF can reach `raw/` by. Everything else — a
  defuddle, Jina, curl or gh capture of a web page — is `other`. The scope never changes the
  verdict: a `suspect` outside the derivation scope is still printed and still exits 3, and
  the ingest skill decides what to do with it (its Step 0 text: a `suspect` on `other` is
  reported in the run report and raises no `flagged:` line by itself). Why not
  `converted_from:` alone: a damaged file can record the paper's abstract URL there, not the
  PDF the agent downloaded and converted, and the engine is the one remaining observable that
  says a converter ran. The engine names are the skill's
  own routes, listed in one tuple (DOCUMENT_CONVERTERS); a route the skill adds later is added
  there, and until it is, a conversion by an unlisted engine reads `other` — reported, never
  silent.

VERDICT  `suspect` when any measure crosses its threshold, else `clean`. Every output line
prints the five measured values, the threshold each was judged against, and the scope.

THRESHOLDS — derived, never set by eye. Rule: for each measure, the threshold is the midpoint
of the gap between the worst-scoring known-clean file (the negatives' maximum for the three
upper-tail rates, their minimum for recovery and readable-words) and the nearest known-damaged file beyond it — the loosest
cut that admits no known-clean file, with half the gap as headroom on each side. A measure
with no damaged file beyond the worst clean one gets no threshold (`n/a`: it does not
separate) and the verdict rests on the others. Run `--derive DIR --positives FILE` to print
the derivation, and `--distribution DIR` for the percentiles behind it.

Compatibility thresholds
------------------------
The shipped constants retain the existing behaviour. Their selection is set by judgement,
unmeasured for a new corpus. Use `--derive DIR --positives FILE` for the original four
measures and `--derive-readable DIR --positives FILE` for readable-words. Keep the labelled
corpus and its boundary measurements locally; re-derive affected cuts when it changes.
The recovery arm combines readable-word share and letter density so neither measure alone
can reject short readable prose. A `--thresholds` override is printed on the summary line.
provenance together. A `--thresholds` override is printed on the summary line.

USAGE
  python3 -B conversion_score.py FILE [FILE …]             score files (or every .md in a DIR)
  python3 -B conversion_score.py --distribution DIR        percentiles of each measure over DIR
  python3 -B conversion_score.py --derive DIR --positives FILE
                                                           threshold derivation (FILE lists the
                                                           known-damaged conversions, one path
                                                           per line; matched on the basename)
  python3 -B conversion_score.py --derive-readable DIR --positives FILE
                                                           derive readable-words alone; FILE
                                                           lists known destroyed captures
  --thresholds SHORT,RUN,RECOVERY,LONGRUN[,READABLE]
                                    override thresholds (a bare `-` keeps one, `off` disables
                                    one); four values keep the derived readable-word cut.
                                    READABLE is the word-letter share in [0, 1]; recorded on the summary.
  CONVERSION_SCORE_PDFTOTEXT        environment: the pdftotext binary to use (default: PATH,
                                    then the usual Homebrew locations); tests point it away

EXIT  0 every file clean · 3 any file suspect · 2 premise failure (an unreadable or empty
file, a body with no word token, a directory with no `.md`, a positives entry not found in
DIR, a malformed option). A missing or failing `pdftotext` is not a premise failure.
"""
import os
import math
import re
import sys
import unicodedata
import subprocess
from functools import lru_cache

# --- derived thresholds (see the docstring for the derivation) ---------------------------
THRESHOLD_SHORT = 57.57    # suspect ABOVE; compatibility default, set by judgement, unmeasured for a new corpus
THRESHOLD_RUN = 4.41       # run-together % : suspect when ABOVE
THRESHOLD_RECOVERY = 0.15  # recovery       : suspect when BELOW
THRESHOLD_LONG_RUN = 6.56  # long-run /1k   : suspect when ABOVE (and LONG_RUN_FLOOR runs or more)
THRESHOLD_READABLE = 0.367 # suspect BELOW; compatibility default, set by judgement, unmeasured for a new corpus
DERIVED_ON = "compatibility defaults; re-derive on a labelled local corpus"

LONG_TOKEN = 18            # rule (b): more than this many letters — set by judgement, unmeasured
LONG_RUN_FLOOR = 10        # long-run fires only with this many runs — the skill's floor, set by judgement, unmeasured
MIN_SENTENCE_WORDS = 6     # a pdftotext sentence counts from this many words — set by judgement, unmeasured
PDFTOTEXT_TIMEOUT_S = 120  # bound on one pdftotext call — a timeout, set by judgement, unmeasured; a hit reads n/a
BLOB_MIN_CHARS = 40        # base64-shaped blob: at least this long — set by judgement, unmeasured
BLOB_NO_VOWEL_RUN = 6      # …and a run of this many non-vowels — set by judgement, unmeasured
DOCUMENT_CONVERTERS = ("markitdown", "agent")   # the ingest skill's document-conversion routes (scope pdf)
REFERENCE_LETTER_DENSITY = 0.306  # compatibility default; set by judgement, unmeasured for a new corpus

LETTER_RUN_RE = re.compile(r"[^\W\d_]+")
LONG_RUN_RE = re.compile(r"[A-Za-z]{25,}")       # the ingest skill's Step 0 probe (a), verbatim
READABLE_RUN_RE = re.compile(r"[A-Za-z]{4,}")   # four-letter proxy specified above; set by judgement, unmeasured
SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")
WS_RE = re.compile(r"\s+")
FM_RE = re.compile(r"\A---[ \t]*\r?\n(.*?\r?\n)---[ \t]*\r?\n", re.S)
CONVERTED_FROM_RE = re.compile(r"^converted_from:[ \t]*(.+?)[ \t]*$", re.M)
CONVERTED_BY_RE = re.compile(r"^converted_by:[ \t]*(.+?)[ \t]*$", re.M)
URL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://")
TAG_RE = re.compile(r"<[A-Za-z!/?][^<>]*>")
BLOB_RE = re.compile(r"[A-Za-z0-9+/=_\-]{%d,}" % BLOB_MIN_CHARS)
NO_VOWEL_RUN_RE = re.compile(r"[^aeiouyAEIOUY]{%d}" % BLOB_NO_VOWEL_RUN)
DIGIT_RE = re.compile(r"\d")
LETTER_RE = re.compile(r"[A-Za-z]")

USAGE = ("usage: conversion_score.py [--thresholds S,R,C,L[,A]] FILE|DIR … | --distribution DIR | "
         "--derive DIR --positives FILE | --derive-readable DIR --positives FILE "
         "(exit 0 clean · 3 suspect · 2 premise failure)\n"
         "Measures: short-lines, run-together, long-run, recovery, readable-words.\n"
         "A: readable-words, letters in runs of four or more divided by all ASCII body letters; "
         "suspect below the derived cut, damage destroyed at zero, damaged otherwise.\n"
         "Four threshold values keep the readable-words cut; a fifth overrides it; - keeps, off disables. "
         "Numeric values must be finite and non-negative; readable-words is a share in [0, 1].\n"
         "--derive uses the original four measures; --derive-readable uses the separately labelled "
         "destroyed-capture corpus and prints both boundary files.\n"
         "Recovery: n/a (reference unreadable (readable-words <share>, letter density <density>)) when the "
         "pdftotext text layer itself reads below the readable-words cut AND below the reference letter-density "
         "cut (a scanned PDF's glyph soup), n/a (reference unreadable (no letters)) when it holds no letter; "
         "the verdict then rests on the four text arms.")


def probe_failed(message):
    print(f"PROBE FAILED: {message}", file=sys.stderr)
    raise SystemExit(2)


# --- reading ----------------------------------------------------------------------------
def read_text(path):
    """UTF-8 with a BOM dropped and CRLF normalised; bad bytes replaced, never fatal."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        probe_failed(f"cannot read {path}: {exc}")
    return raw.decode("utf-8-sig", "replace").replace("\r\n", "\n")


def split_frontmatter(text):
    """(frontmatter or '', body)."""
    m = FM_RE.match(text)
    if not m:
        return "", text
    return m.group(1), text[m.end():]


@lru_cache(maxsize=None)
def is_latin(ch):
    return unicodedata.name(ch, "").startswith("LATIN")


# --- exclusions (run-together only) -----------------------------------------------------
def strip_fences(body):
    """Drop fenced code blocks: from a line opening with ``` or ~~~ to the matching closer,
    or to the end of the file when the fence is never closed (CommonMark's reading)."""
    out, fence = [], None
    for line in body.split("\n"):
        s = line.lstrip()
        if fence is None:
            if s.startswith("```") or s.startswith("~~~"):
                fence = s[:3]
                continue
            out.append(line)
        elif s.startswith(fence):
            fence = None
    return "\n".join(out)


def is_blob(chunk):
    return (bool(DIGIT_RE.search(chunk)) and bool(LETTER_RE.search(chunk))
            and bool(NO_VOWEL_RUN_RE.search(chunk)))


def strip_blobs(text):
    return BLOB_RE.sub(lambda m: " " if is_blob(m.group(0)) else m.group(0), text)


def prose_text(body):
    """The body with fenced code, angle-bracket tags and base64-shaped blobs excluded."""
    return strip_blobs(TAG_RE.sub(" ", strip_fences(body)))


# --- measures ---------------------------------------------------------------------------
def short_line_share(body):
    """(share %, short, non-blank) over non-blank body lines."""
    lines = [ln.strip() for ln in body.split("\n")]
    nonblank = [ln for ln in lines if ln]
    short = sum(1 for ln in nonblank if len(ln) <= 1)
    return (100.0 * short / len(nonblank) if nonblank else 0.0), short, len(nonblank)


def latin_tokens(text):
    """(tokens, letters, latin_letters): maximal runs of Latin letters, and the letter census
    the Latin-majority test rests on."""
    tokens = []
    letters = latin = 0
    for run in LETTER_RUN_RE.findall(text):
        letters += len(run)
        if run.isascii():
            latin += len(run)
            tokens.append(run)
            continue
        cur = []
        for ch in run:
            if is_latin(ch):
                latin += 1
                cur.append(ch)
            elif cur:
                tokens.append("".join(cur))
                cur = []
        if cur:
            tokens.append("".join(cur))
    return tokens, letters, latin


def is_run_together(tok):
    if len(tok) > LONG_TOKEN:
        return True
    if tok.islower() or tok.isupper() or tok.istitle():
        return False            # no lower-to-upper join is possible in these shapes
    return any(a.islower() and b.isupper() for a, b in zip(tok, tok[1:]))


def run_together_share(body):
    """(share % or None, hits, tokens, latin_majority, any_token, note) over the prose text;
    the note says why the share is n/a."""
    tokens, letters, latin = latin_tokens(prose_text(body))
    any_token = bool(LETTER_RUN_RE.search(body))
    latin_majority = letters > 0 and latin * 2 >= letters
    if not latin_majority:
        return None, 0, len(tokens), False, any_token, "non-Latin-majority text: no inter-word spaces to lose"
    if not tokens:
        return None, 0, 0, True, any_token, "no prose token outside the exclusions"
    hits = sum(1 for tok in tokens if is_run_together(tok))
    return 100.0 * hits / len(tokens), hits, len(tokens), True, any_token, None


def long_run_rate(body, latin_majority):
    """(rate per 1,000 words or None, runs, words) — the skill's probe (a) on the body."""
    runs = len(LONG_RUN_RE.findall(body))
    words = len(body.split()) or 1
    if not latin_majority:
        return None, runs, words
    return runs * 1000.0 / words, runs, words


def readable_word_share(body, latin_majority):
    """(share or None, letters in runs of four or more, all ASCII body letters)."""
    if not body:
        probe_failed("readable-words requires a non-empty body")
    word_letters = sum(len(run) for run in READABLE_RUN_RE.findall(body))
    letters = len(LETTER_RE.findall(body))
    return (word_letters / letters if latin_majority and letters else None), word_letters, letters


def readable_controls():
    """Same-run positive and negative controls for the new arm, using its derived cut."""
    destroyed = readable_word_share("a b c 123 !", True)[0]
    prose = "Readable words support a clear account of the research."
    clean = readable_word_share(prose, True)[0]
    _, body = split_frontmatter("---\ntitle: Readable words in a title\n---\na b c 123 !")
    if not (destroyed == 0 and destroyed < THRESHOLD_READABLE < clean
            and readable_word_share(body, True)[0] == 0
            and readable_word_share(prose + " | 0123456789 -- $ {} [] ", True)[0] == clean):
        probe_failed("readable-words controls did not discriminate")
    return "controls: readable-words zero-run body caught; readable prose passed; frontmatter excluded; non-letter padding ignored"


def normalise(text):
    return WS_RE.sub(" ", unicodedata.normalize("NFKC", text)).strip().lower()


def find_pdftotext():
    override = os.environ.get("CONVERSION_SCORE_PDFTOTEXT")
    if override:
        return override if os.path.isfile(override) and os.access(override, os.X_OK) else None
    for d in os.environ.get("PATH", "").split(os.pathsep) + ["/opt/homebrew/bin", "/usr/local/bin"]:
        cand = os.path.join(d, "pdftotext")
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def converted_from(frontmatter):
    m = CONVERTED_FROM_RE.search(frontmatter)
    return m.group(1).strip().strip("\"'") if m else ""


def names_pdf(value):
    """True when a converted_from: value names a .pdf — a local name, or a URL whose path
    (query and fragment dropped) ends in .pdf."""
    if not value:
        return False
    path = value.split("?", 1)[0].split("#", 1)[0] if URL_RE.match(value) else value
    return path.lower().endswith(".pdf")


def sibling_pdf(path, frontmatter):
    """The PDF `converted_from:` names when it is a local .pdf beside the conversion, else
    <stem>.pdf beside it, else None."""
    here = os.path.dirname(os.path.abspath(path))
    named = converted_from(frontmatter)
    if named.lower().endswith(".pdf") and not URL_RE.match(named):
        cand = named if os.path.isabs(named) else os.path.join(here, named)
        if os.path.isfile(cand):
            return cand
    stem = os.path.splitext(os.path.basename(path))[0]
    cand = os.path.join(here, stem + ".pdf")
    return cand if os.path.isfile(cand) else None


def scope_of(frontmatter, pdf):
    """('pdf' | 'other', evidence)."""
    if names_pdf(converted_from(frontmatter)):
        return "pdf", "converted_from names a PDF"
    if pdf:
        return "pdf", "sibling PDF"
    m = CONVERTED_BY_RE.search(frontmatter)
    engine = m.group(1).strip().strip("\"'") if m else ""
    first = re.match(r"[A-Za-z][A-Za-z0-9_\-]*", engine)
    first = first.group(0).lower() if first else ""
    if first in DOCUMENT_CONVERTERS:
        return "pdf", f"converted_by {first}"
    if engine:
        return "other", f"web capture, converted_by {engine[:24]}"
    return "other", "no converted_by and no PDF evidence"


def pdf_text(pdf, exe):
    """(text or None, reason): pdftotext's flow-order text layer, decoded; None with the reason
    when pdftotext fails or times out."""
    try:
        proc = subprocess.run([exe, "-enc", "UTF-8", pdf, "-"], capture_output=True, timeout=PDFTOTEXT_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return None, f"pdftotext failed: timed out after {PDFTOTEXT_TIMEOUT_S} s"
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"pdftotext failed: {str(exc).splitlines()[0][:120] if str(exc) else type(exc).__name__}"
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        first = err[0][:120] if err else f"exit {proc.returncode}, no stderr"
        return None, f"pdftotext failed: {first}"
    return proc.stdout.decode("utf-8", "replace"), None


def pdf_sentences(text):
    """pdftotext sentences of MIN_SENTENCE_WORDS words or more, normalised."""
    out = []
    for sent in SENTENCE_END_RE.split(normalise(text)):
        sent = sent.strip()
        if len(sent.split(" ")) >= MIN_SENTENCE_WORDS:
            out.append(sent)
    return out


def letter_density(text):
    """Letters (maximal runs of the scorer's letter class, any script) per character of text."""
    return sum(len(run) for run in LETTER_RUN_RE.findall(text)) / len(text) if text else 0.0


def reference_unreadable(text):
    """The reason the pdftotext reference cannot serve the recovery arm, or None when it can.

    Two measures must BOTH read the reference as destroyed, because either alone misfires:
    (1) the conversion's own readable-words arm (readable_word_share, with the same
    Latin-majority test) below its cut, THRESHOLD_READABLE, reused here by judgement,
    unmeasured for a new corpus; alone it can flag short plain prose. Combine it with
    (2) letter_density below REFERENCE_LETTER_DENSITY: a destroyed text layer holds few letters,
    while readable prose mostly holds letters. Equality to either cut remains readable.
    is readable, as it is for the arm itself (suspect only BELOW). The baked cuts apply whatever
    `--thresholds` sets for the conversion's own arm, so an override never re-enables a
    comparison against a destroyed text layer. An empty or whitespace-only reference is not
    judged here: it yields no sentence and keeps that reason. A reference with no letter at all
    (so density 0; Unicode letters, so a CJK layer is not letterless) reads unreadable. A
    reference the arm reads n/a (non-Latin-majority, or Latin letters with no ASCII letter) is
    compared as before.
    """
    if not text.strip():
        return None
    if not LETTER_RUN_RE.search(text):
        return "reference unreadable (no letters)"
    _, letters, latin = latin_tokens(prose_text(text))   # the arm's Latin-majority census
    share = readable_word_share(text, letters > 0 and latin * 2 >= letters)[0]
    if share is None or share >= THRESHOLD_READABLE:
        return None
    density = letter_density(text)
    if density >= REFERENCE_LETTER_DENSITY:
        return None
    return f"reference unreadable (readable-words {share:.3f}, letter density {density:.3f})"


def recovery_fraction(body, pdf, exe):
    """(fraction or None, found, total, reason) — None with a reason when pdftotext fails, when
    its text layer is itself unreadable (reference_unreadable), or when it yields no sentence to
    look for."""
    text, reason = pdf_text(pdf, exe)
    if text is None:
        return None, 0, 0, reason
    reason = reference_unreadable(text)
    if reason:
        return None, 0, 0, reason
    sentences = pdf_sentences(text)
    if not sentences:
        return None, 0, 0, f"pdftotext yielded no sentence of {MIN_SENTENCE_WORDS} words"
    conv = normalise(body)
    found = sum(1 for s in sentences if s in conv)
    return found / len(sentences), found, len(sentences), None


def score_file(path, exe_cache):
    """Every measure for one file; premise failures exit 2 here."""
    text = read_text(path)
    if not text.strip():
        probe_failed(f"{path} is empty")
    fm, body = split_frontmatter(text)
    if not body.strip():
        probe_failed(f"{path} has no body below its frontmatter")
    short, n_short, n_lines = short_line_share(body)
    run, n_hits, n_tokens, latin, any_token, run_note = run_together_share(body)
    if not any_token:
        probe_failed(f"{path} holds no word token")
    long_run, n_runs, n_words = long_run_rate(body, latin)
    readable, n_word_letters, n_ascii_letters = readable_word_share(body, latin)
    pdf = sibling_pdf(path, fm)
    scope, evidence = scope_of(fm, pdf)
    rec = None
    found = total = 0
    if pdf is None:
        rec_note = "no sibling PDF"
    else:
        if "exe" not in exe_cache:
            exe_cache["exe"] = find_pdftotext()
        if not exe_cache["exe"]:
            rec_note = "pdftotext absent"
        else:
            rec, found, total, rec_note = recovery_fraction(body, pdf, exe_cache["exe"])
    return {
        "path": path, "short": short, "n_short": n_short, "n_lines": n_lines,
        "run": run, "n_hits": n_hits, "n_tokens": n_tokens, "latin": latin, "run_note": run_note,
        "long_run": long_run, "n_runs": n_runs, "n_words": n_words,
        "pdf": pdf, "recovery": rec, "found": found, "total": total, "rec_note": rec_note,
        "readable": readable, "n_word_letters": n_word_letters, "n_ascii_letters": n_ascii_letters,
        "scope": scope, "scope_evidence": evidence,
    }


def verdict(m, t_short, t_run, t_rec, t_long, t_readable=THRESHOLD_READABLE):
    reasons = []
    if t_short is not None and m["short"] > t_short:
        reasons.append("short-lines")
    if t_run is not None and m["run"] is not None and m["run"] > t_run:
        reasons.append("run-together")
    if t_long is not None and m["long_run"] is not None and m["long_run"] > t_long and m["n_runs"] >= LONG_RUN_FLOOR:
        reasons.append("long-run")
    if t_rec is not None and m["recovery"] is not None and m["recovery"] < t_rec:
        reasons.append("recovery")
    if t_readable is not None and m["readable"] is not None and m["readable"] < t_readable:
        reasons.append("readable-words")
    return ("suspect" if reasons else "clean"), reasons


def fmt_threshold(value, unit=""):
    return "n/a" if value is None else f"{value:g}{unit}"


def render(m, t_short, t_run, t_rec, t_long, t_readable=THRESHOLD_READABLE):
    v, reasons = verdict(m, t_short, t_run, t_rec, t_long, t_readable)
    ts = fmt_threshold(t_short, " %")
    tr = fmt_threshold(t_run, " %")
    tc = fmt_threshold(t_rec)
    tl = fmt_threshold(t_long, " /1k")
    short = f"short-lines {m['short']:.1f} % ({'>' if 'short-lines' in reasons else '<='} {ts}; {m['n_short']}/{m['n_lines']} lines)"
    if m["run"] is None:
        run = f"run-together n/a ({m['run_note']})"
    else:
        run = f"run-together {m['run']:.1f} % ({'>' if 'run-together' in reasons else '<='} {tr}; {m['n_hits']}/{m['n_tokens']} tokens)"
    if m["long_run"] is None:
        long_run = "long-run n/a (non-Latin-majority text)"
    else:
        long_run = f"long-run {m['long_run']:.1f} /1k ({'>' if 'long-run' in reasons else '<='} {tl}; {m['n_runs']} runs/{m['n_words']} words)"
    if m["recovery"] is None:
        rec = f"recovery n/a ({m['rec_note']})"
    else:
        rec = f"recovery {m['recovery']:.2f} ({'<' if 'recovery' in reasons else '>='} {tc}; {m['found']}/{m['total']} sentences)"
    if m["readable"] is None:
        readable = "readable-words n/a (non-Latin-majority text)"
    else:
        ta = fmt_threshold(t_readable)
        sign = "<" if "readable-words" in reasons else ">="
        readable = (f"readable-words {m['readable']:.3f} ({sign} {ta}; "
                    f"{m['n_word_letters']}/{m['n_ascii_letters']} ASCII letters)")
    damage = (" · damage: destroyed" if m["n_word_letters"] == 0 else " · damage: damaged") if "readable-words" in reasons else ""
    return (f"{v:7s} {m['path']} · {short} · {run} · {long_run} · {rec} · scope: {m['scope']} "
            f"({m['scope_evidence']}) · {readable}{damage}")


# --- corpus helpers --------------------------------------------------------------------
def md_files(directory):
    if not os.path.isdir(directory):
        probe_failed(f"{directory} is not a directory")
    files = sorted(os.path.join(directory, n) for n in os.listdir(directory)
                   if n.lower().endswith(".md") and os.path.isfile(os.path.join(directory, n)))
    if not files:
        probe_failed(f"{directory} holds no .md file")
    return files


def percentile(values, p):
    """Linear interpolation between the two nearest ranks (the NumPy default)."""
    s = sorted(values)
    if not s:
        return None
    k = (len(s) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


MEASURES = (("short-lines %", "short", True, 1),
            ("run-together %", "run", True, 1),
            ("long-run /1k", "long_run", True, 1),
            ("recovery", "recovery", False, 2),
            ("readable-words", "readable", False, 3))


def distribution(directory):
    files = md_files(directory)
    cache = {}
    rows = [score_file(f, cache) for f in files]
    scopes = sum(1 for r in rows if r["scope"] == "pdf")
    control = readable_controls()
    print(f"DISTRIBUTION over {directory}: {len(rows)} files ({scopes} scope pdf, {len(rows) - scopes} other)   "
          f"(percentiles by linear interpolation)")
    print(f"{'measure':16s} {'n':>10s} {'min':>7s} {'p10':>7s} {'p25':>7s} {'p50':>7s} {'p75':>7s} {'p90':>7s} {'max':>7s}")
    for label, key, _, digits in MEASURES:
        vals = [r[key] for r in rows if r[key] is not None]
        na = len(rows) - len(vals)
        n = f"{len(vals)}" + (f" ({na} n/a)" if na else "")
        cells = [percentile(vals, p) for p in (0, 10, 25, 50, 75, 90, 100)]
        print(f"{label:16s} {n:>10s} " + " ".join(f"{c:7.{digits}f}" if c is not None else f"{'n/a':>7s}" for c in cells))
    print(control)
    return 0


def separate(neg, pos, higher_is_worse):
    """(threshold, caught, worst_negative, nearest_positive): the midpoint of the gap between
    the worst negative and the nearest positive beyond it; threshold None when nothing lies
    beyond. neg and pos are (value, path) pairs."""
    if not neg or not pos:
        return None, 0, None, None
    if higher_is_worse:
        worst = max(neg)
        beyond = [p for p in pos if p[0] > worst[0]]
        nearest = min(beyond) if beyond else None
    else:
        worst = min(neg)
        beyond = [p for p in pos if p[0] < worst[0]]
        nearest = max(beyond) if beyond else None
    if nearest is None:
        return None, 0, worst, None
    return (worst[0] + nearest[0]) / 2.0, len(beyond), worst, nearest


def derive(directory, positives_file, readable_only=False):
    files = md_files(directory)
    try:
        with open(positives_file, encoding="utf-8") as fh:
            listed = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
    except OSError as exc:
        probe_failed(f"cannot read positives {positives_file}: {exc}")
    if not listed:
        probe_failed(f"{positives_file} lists no positive")
    by_base = {os.path.basename(f): f for f in files}
    missing = [p for p in listed if os.path.basename(p) not in by_base]
    if missing:
        probe_failed(f"{len(missing)} positive(s) not found in {directory}: {', '.join(missing[:5])}")
    pos_set = {os.path.basename(p) for p in listed}
    cache = {}
    rows = [score_file(f, cache) for f in files]
    pos_rows = [r for r in rows if os.path.basename(r["path"]) in pos_set]
    neg_rows = [r for r in rows if os.path.basename(r["path"]) not in pos_set]
    if readable_only and (not any(r["readable"] is not None for r in pos_rows)
                          or not any(r["readable"] is not None for r in neg_rows)):
        probe_failed("readable-words derivation needs usable positive and negative shares")
    control = readable_controls()
    print(f"DERIVATION over {directory}: {len(rows)} files · positives {len(pos_rows)} (from {positives_file}) "
          f"· negatives {len(neg_rows)} · scope pdf {sum(1 for r in rows if r['scope'] == 'pdf')} "
          f"(positives {sum(1 for r in pos_rows if r['scope'] == 'pdf')})")
    print("rule: threshold = midpoint of the gap between the worst known-clean value and the nearest "
          "known-damaged value beyond it (the loosest cut admitting no known-clean file); no positive "
          "beyond the worst negative = the measure does not separate (n/a)")
    thresholds = {}
    base = os.path.basename
    measures = MEASURES[-1:] if readable_only else MEASURES[:-1]
    if readable_only:
        print("arm: readable-words only; negatives mean not destroyed, not free of other damage")
        print("limitation: re-derive this cut when another destroyed capture appears")
    else:
        print("arms: original four only; readable-words requires its separate destroyed-capture corpus")
    for label, key, worse_high, _ in measures:
        digits = 3 if key == "readable" else 2  # word-letter cut has three decimals; original cuts have two
        pos = [(r[key], base(r["path"])) for r in pos_rows if r[key] is not None]
        neg = [(r[key], base(r["path"])) for r in neg_rows if r[key] is not None]
        na_pos, na_neg = len(pos_rows) - len(pos), len(neg_rows) - len(neg)
        t, caught, worst, nearest = separate(neg, pos, worse_high)
        thresholds[key] = t
        rng = lambda v: f"{min(v)[0]:.{digits}f}–{max(v)[0]:.{digits}f}" if v else "n/a"
        sign = ">" if worse_high else "<"
        if t is None:
            cut = "n/a — does not separate at zero false positives"
        else:
            cut = f"{sign} {t:.{digits}f} (midpoint of the gap {worst[0]:.{digits}f} → {nearest[0]:.{digits}f})"
        print(f"  {label:15s} positives {rng(pos)} ({len(pos)}" + (f", {na_pos} n/a" if na_pos else "") +
              f") · negatives {rng(neg)} ({len(neg)}" + (f", {na_neg} n/a" if na_neg else "") +
              f") · caught {caught}/{len(pos)} · threshold {cut}")
        if worst is not None:
            others = sorted((v for v in neg if v[1] != worst[1]), reverse=worse_high)
            next_worst = others[0] if others else None
            print(f"  {'':15s} worst clean {worst[1]} ({worst[0]:.{digits}f})"
                  + (f" · next-worst clean {next_worst[1]} ({next_worst[0]:.{digits}f})" if next_worst else "")
                  + (f" · nearest damaged {nearest[1]} ({nearest[0]:.{digits}f})" if nearest else ""))
        if readable_only and t is not None:
            print(f"  boundaries: {worst[1]} {worst[0]:.15f} · {nearest[1]} {nearest[0]:.15f} "
                  f"· midpoint {t:.15f} · half-gap margin {abs(worst[0] - nearest[0]) / 2:.15f}")
    tp = fp = fn = tn = 0
    wrong = []
    for r in rows:
        v, _ = verdict(r, thresholds.get("short"), thresholds.get("run"), thresholds.get("recovery"), thresholds.get("long_run"), thresholds.get("readable"))
        is_pos = base(r["path"]) in pos_set
        if v == "suspect" and is_pos:
            tp += 1
        elif v == "suspect":
            fp += 1
            wrong.append(f"false positive: {r['path']}")
        elif is_pos:
            fn += 1
            wrong.append(f"false negative: {r['path']}")
        else:
            tn += 1
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    label = "readable-words verdict" if readable_only else "combined verdict"
    print(f"{label} at these thresholds: suspect {tp + fp} · clean {tn + fn} · true positives {tp} "
          f"· false positives {fp} · false negatives {fn} · precision {prec:.3f} · recall {rec:.3f}")
    print("misclassified: " + ("(none)" if not wrong else "; ".join(wrong)))
    baked = ((THRESHOLD_READABLE,) if readable_only
             else (THRESHOLD_SHORT, THRESHOLD_RUN, THRESHOLD_RECOVERY, THRESHOLD_LONG_RUN))
    keys = ("readable",) if readable_only else ("short", "run", "recovery", "long_run")
    digits = 3 if readable_only else 2  # same rounding as the selected constants
    derived = tuple(None if thresholds[k] is None else round(thresholds[k], digits) for k in keys)
    same = baked == derived
    print(f"baked-in thresholds {tuple(fmt_threshold(b) for b in baked)} "
          f"{'match' if same else 'DIFFER FROM'} the derived {tuple(fmt_threshold(d) for d in derived)}"
          + (f" (rounded to {digits} decimals)" if same else " — update the selected constants and their provenance together"))
    print(control)
    return 0


# --- entry ------------------------------------------------------------------------------
def parse_thresholds(spec):
    parts = spec.split(",")
    if len(parts) not in (4, 5):
        probe_failed(f"--thresholds wants SHORT,RUN,RECOVERY,LONGRUN[,READABLE], got {spec!r}")
    if len(parts) == 4:
        parts.append("-")
    out = []
    for part, default in zip(parts, (THRESHOLD_SHORT, THRESHOLD_RUN, THRESHOLD_RECOVERY, THRESHOLD_LONG_RUN, THRESHOLD_READABLE)):
        part = part.strip()
        if part in ("", "-"):
            out.append(default)
        elif part.lower() in ("n/a", "none", "off"):
            out.append(None)
        else:
            try:
                value = float(part)
            except ValueError:
                probe_failed(f"--thresholds value {part!r} is not a number")
            if not math.isfinite(value) or value < 0:
                probe_failed(f"--thresholds value {part!r} must be finite and non-negative")
            if len(out) == 4 and value > 1:  # fifth field: a share is bounded by one
                probe_failed(f"--thresholds readable-words value {part!r} must be in [0, 1]")
            out.append(value)
    return tuple(out)


def main(argv):
    args = list(argv)
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    if args[0] == "--distribution":
        if len(args) != 2:
            probe_failed("--distribution takes exactly one directory")
        return distribution(args[1])
    if args[0] in ("--derive", "--derive-readable"):
        if len(args) != 4 or args[2] != "--positives":
            probe_failed(args[0] + " DIR --positives FILE")
        return derive(args[1], args[3], readable_only=args[0] == "--derive-readable")
    thresholds = (THRESHOLD_SHORT, THRESHOLD_RUN, THRESHOLD_RECOVERY, THRESHOLD_LONG_RUN, THRESHOLD_READABLE)
    override = None
    if args[0] == "--thresholds":
        if len(args) < 3:
            probe_failed("--thresholds needs a value and at least one file")
        override = args[1]
        thresholds = parse_thresholds(override)
        args = args[2:]
    if any(a.startswith("-") for a in args):
        probe_failed(f"unknown option in {args} ({USAGE})")
    targets = []
    for a in args:
        if os.path.isdir(a):
            targets.extend(md_files(a))
        else:
            targets.append(a)
    t_short, t_run, t_rec, t_long, t_readable = thresholds
    control = readable_controls()
    cache = {}
    suspect = 0
    scopes = {"pdf": 0, "other": 0}
    for path in targets:
        m = score_file(path, cache)
        line = render(m, t_short, t_run, t_rec, t_long, t_readable)
        if line.startswith("suspect"):
            suspect += 1
        scopes[m["scope"]] += 1
        print(line)
    source = f"override {override!r}" if override else f"derived {DERIVED_ON}"
    print(f"SCORED: {len(targets)} file(s) · clean {len(targets) - suspect} · suspect {suspect} · "
          f"scope pdf {scopes['pdf']} | other {scopes['other']} · "
          f"thresholds short-lines > {fmt_threshold(t_short, ' %')} | run-together > {fmt_threshold(t_run, ' %')} "
          f"| long-run > {fmt_threshold(t_long, ' /1k')} | recovery < {fmt_threshold(t_rec)} ({source}) "
          f"| readable-words < {fmt_threshold(t_readable)} (validate on a separately labelled local corpus)")
    print(control)
    return 3 if suspect else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
