#!/usr/bin/env python3
"""recapture-compare.py — what differs between a raw capture and a fresh re-capture (deep-lint Step 5).

Stdout-only by construction: it reads two local files and prints; it writes no file, edits no page
and never touches the network. The capture itself stays with the agent's normal capture path.

Why (register entry of 2026-08-28, the freshness ladder and CDN-served documentation): a page that
serves neither `Last-Modified` nor `ETag` gives Step 5's cheap probes nothing to read, so the only
way to learn whether it changed is to capture it again and compare. A similarity ratio cannot be the
judge: on a long page one changed figure moves it less than render noise does. So this script gives
no verdict on freshness. It lists every differing run, and the reader judges each: a changed fact,
figure, URL, requirement or instruction is material and the page re-ingests; layout, whitespace,
counters and render dates are not.

The compare is literal. Each file's leading frontmatter block (a first line `---`, closed by the next
line `---`; spaces or tabs may follow either) is dropped, and the rest is compared line by line,
character for character. No Markdown is read: no whitespace, emphasis, link or code rule can hide a
change, so render noise shows as runs to read, never as silence. The bytes are read as UTF-8, a byte
that is not UTF-8 kept as a character of its own (printed <U+DC80> to <U+DCFF>), so two different bad
bytes never compare equal. Lines are split at LF alone, so a body line keeps the carriage return it
ends in: a body that differs from another only in its line ends (CRLF against LF) differs on each such
line, the carriage return printed <U+000D>. Only in the frontmatter, which is never compared, are a
carriage return and a byte-order mark read past: a fence line may end in CR, the opening fence may
follow a byte-order mark at the start of the file, and each frontmatter line is read without the CR it
ends in, so a frontmatter written in CRLF is still recognised, its engine field read and the block
dropped. In a body a byte-order mark is a character like any other (printed <U+FEFF>).
Runs are found by Python's difflib over whole lines. Past HEURISTIC_FROM lines of difference its
popular-line heuristic is on, a cost bound: it moves where runs begin and end, never whether a line
that differs is listed, since a line outside every run sits in a stretch matched identical.

Usage:
  python3 .claude/skills/deep-lint/recapture-compare.py --raw <raw file> --fresh <fresh capture>

Refusals (each a line `CANNOT COMPARE: <why>`, exit 2), checked before anything is compared:
  - either file is missing, is not a regular file or cannot be read, or both paths name one file;
  - either body holds nothing but whitespace once its frontmatter is dropped (a capture that returned
    nothing is not an unchanged page);
  - either file's engine field is absent or is not one plain word, or the two words differ.
    The engine field is one of ENGINE_FIELDS, read in one form only: a frontmatter line that opens
    with the field's name and a colon, then spaces or tabs and the value (trailing spaces and tabs
    dropped). The value must be a plain word: a letter, then letters, digits, `.`, `_`, `+` or `-`,
    and not a word YAML reads as null or a boolean (null, true, false, yes, no, on, off, y, n, in any
    case). Anything else is refused with its reason, never interpreted: an empty value, a quoted or
    commented value, a value that continues on an indented line below, an engine field written twice
    or in two of the fields, or a frontmatter line that may write one in another form (quoted, indented,
    no space after the colon, inside another value). The two words are compared exactly, case
    included: a cross-engine compare reads render noise as change (the register's pilot of
    2 September: 0.947 similarity across engines on identical content, 0.996 within one engine).

Output (stdout):
  a `recapture-compare:` line naming both files, the engine field each carries and the line where
  each body starts; the `control:` lines; then `IDENTICAL: ...` (exit 0) or
  `DIFFERS: <n> differing runs · <a> shown in full · <b> shown in part · <c> not shown` (exit 1),
  each run shown, an `UNREAD:` line and the reading rule.
  A run is a maximal stretch of lines that differs, with its raw lines and its fresh lines. A run that
  puts k lines in place of k lines pairs them in order and prints each pair together, with the
  character where the pair first differs; any other run prints its raw lines, then its fresh lines.
  Every character that does not print, other than a plain space, is printed as <U+XXXX>, and so is
  each space at the end of a line, so a whitespace-only change can be read. A pair that may still
  print alike (equal once Unicode compatibility-normalised: a composed and a decomposed accent, say)
  says so; the comparison itself never normalises.
  Bounds (each set by judgement, unmeasured):
  - at most RUN_LINES lines a side, or RUN_LINES pairs, are printed for one run;
  - at most LINE_CHARS printed characters of one line. Where a pair does not fit, each of its lines is
    printed from CONTEXT_CHARS before the first character where the two differ to CONTEXT_CHARS after
    the last, and the counts left out are stated: that text is the same in both lines at the same
    place, so leaving it out hides no difference;
  - runs are printed in order until RUN_CAP are shown or the next would take the printed runs past
    OUTPUT_CHARS; every later run is counted not shown, with the raw and fresh line where it starts.
  A run with a line cut, or with lines or pairs left out, is shown in part, and its header says what
  was left out. A run shown in part and a run not shown are both UNREAD: the `UNREAD:` line counts and
  names them, so the reader reads them in the two files before judging the page, or reports the page
  unadjudicated with that count.
  A broken premise (the in-memory control misbehaving) is `PROBE FAILED: <what>`, exit 2.

Control, in memory, on every run before the files are read: a change in frontmatter only, and the same
frontmatter written in CRLF after a byte-order mark, must give 0 runs; a changed figure, a trailing
space, a carriage return ending one line and a change deep inside a long line must give exactly 1 run
each, shown in full, with the changed text printed; a run longer than RUN_LINES lines a side must be
shown in part; an engine field that is empty, null, quoted, commented, two words or continued below
must name no engine while plain names still name theirs, in a CRLF frontmatter too.
"""
import argparse
import difflib
import os
import re
import sys
import unicodedata
from stat import S_ISREG

# The provenance fields that name a capture engine. converted_by is the vault's field; the other two
# appear on a few older captures.
ENGINE_FIELDS = ("converted_by", "conversion_engine", "converter")
RUN_CAP = 40          # runs printed before the rest are counted. Set by judgement, unmeasured.
RUN_LINES = 6         # lines a side, or pairs, printed for one run. Set by judgement, unmeasured.
LINE_CHARS = 300      # printed characters of one line. Set by judgement, unmeasured.
CONTEXT_CHARS = 60    # characters either side of where a long pair differs. Set by judgement, unmeasured.
# The printed runs stop before passing OUTPUT_CHARS. Set by judgement, unmeasured: about 15,000 tokens,
# what one reading can hold. Headroom: one run prints at most about 6,200 characters (a header of at
# most about 200, then RUN_LINES pairs of two lines, each line at most a prefix of about 60, two notes of
# about 60 and LINE_CHARS of text, so 6 * 2 * 480 = 5,760, and the line saying how many were left out),
# so the first run always fits and RUN_CAP binds first unless runs are long.
OUTPUT_CHARS = 60000
# Printed characters of a path or a refused value: a bound only, far above an ordinary path.
VALUE_CHARS = 300
# Above this many lines on the longer side of what differs, difflib's popular-line heuristic is on: a line
# repeated often (a blank line, a fence) can then no longer anchor a match, though matches still extend
# over it. A cost bound, measured on 12 October 2026 on the worst shape found (a quarter of the lines blank,
# every other line changed): with the heuristic off the compare took 0.24 s at 1,000 lines a side, 1.9 s
# at 2,000 and 15.9 s at 4,000, growing with the cube of the length; with it on, under 0.01 s. On pages
# with 60 scattered changes, 8,000 and 20,000 lines long, both settings gave identical runs.
HEURISTIC_FROM = 1000

FENCE_LINE_RE = re.compile(r"---[ \t]*\r?")
BYTE_ORDER_MARK = "\ufeff"
FIELD_RE = re.compile(r"(converted_by|conversion_engine|converter):(?:[ \t]+(.*?))?[ \t]*")
LOOSE_FIELD_RE = re.compile(r"(?<![A-Za-z0-9_])[\"']?(?:converted_by|conversion_engine|converter)[\"']?[ \t]*:")
PLAIN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9._+-]*")
YAML_WORDS = frozenset(("null", "true", "false", "yes", "no", "on", "off", "y", "n"))


def read_text(path):
    """The file's text exactly as read: UTF-8, a byte that is not UTF-8 kept apart, nothing dropped or
    replaced (line ends and any byte-order mark stay; split() reads past them in the frontmatter only)."""
    if not S_ISREG(os.stat(path).st_mode):
        raise OSError("not a regular file")
    with open(path, "rb") as handle:
        raw = handle.read()
    return raw.decode("utf-8", "surrogateescape")


def split(text):
    """(frontmatter lines or None, body lines, the file line number of the first body line). Lines are
    split at LF alone, so a body line keeps the CR it ends in. The frontmatter is the one place a CR or a
    byte-order mark is read past: a byte-order mark before the opening fence, a CR ending a fence line,
    and the CR each frontmatter line ends in, so CRLF frontmatter is recognised and its fields read."""
    lines = text.split("\n")
    first = lines[0][len(BYTE_ORDER_MARK):] if lines[0].startswith(BYTE_ORDER_MARK) else lines[0]
    if FENCE_LINE_RE.fullmatch(first):
        for k in range(1, len(lines)):
            if FENCE_LINE_RE.fullmatch(lines[k]):
                return [line[:-1] if line.endswith("\r") else line for line in lines[1:k]], lines[k + 1:], k + 2
    return None, lines, 1


def engine_of(front):
    """(word, field, file line, why): the plain engine word with why None, or word None and why."""
    if front is None:
        return None, None, None, "it has no frontmatter block (a first line --- closed by another), so no engine field"
    found, odd = [], []
    for k, line in enumerate(front):
        match = FIELD_RE.fullmatch(line)
        if match:
            found.append((k, match.group(1), match.group(2) or ""))
        elif LOOSE_FIELD_RE.search(line):
            odd.append(k)
    if odd:
        return None, None, odd[0] + 2, ("its frontmatter line %d may write an engine field in a form this script "
                                        "does not read (quoted, indented, no space after the colon, or inside "
                                        "another value)" % (odd[0] + 2))
    if not found:
        return None, None, None, "its frontmatter has none of the engine fields (%s)" % ", ".join(ENGINE_FIELDS)
    if len(found) > 1:
        return None, None, found[0][0] + 2, ("its frontmatter writes an engine field %d times (lines %s), where "
                                             "one is needed" % (len(found), ", ".join(str(k + 2) for k, _, _ in found)))
    k, field, value = found[0]
    below = next((line for line in front[k + 1:] if line.strip()), "")
    if below[:1] in (" ", "\t"):
        why = "its value continues on the indented line below"
    elif not value:
        why = "it is empty"
    elif not PLAIN_WORD_RE.fullmatch(value):
        why = "it is not one plain word (a letter, then letters, digits, . _ + or -)"
    elif value.lower() in YAML_WORDS:
        why = "YAML reads it as null or a boolean, not a name"
    else:
        return value, field, k + 2, None
    return None, field, k + 2, why


def common_prefix(a, b):
    """The length of the longest common start of two strings."""
    lo, hi = 0, min(len(a), len(b))
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if a[:mid] == b[:mid]:
            lo = mid
        else:
            hi = mid - 1
    return lo


def common_suffix(a, b, limit):
    """The length, at most `limit`, of the longest common end of two strings."""
    lo, hi = 0, limit
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if a[len(a) - mid:] == b[len(b) - mid:]:
            lo = mid
        else:
            hi = mid - 1
    return lo


def differing_runs(old, new):
    """Every maximal differing stretch of two line lists, as (i1, i2, j1, j2): old[i1:i2] became new[j1:j2].
    The lines both lists share at their start and end are set aside first, which changes no run. A line
    lands outside a run only inside a stretch difflib matched, and a matched stretch is identical on both
    sides, so where runs begin and end can vary but no differing line is ever left out of one."""
    limit = min(len(old), len(new))
    start = 0
    while start < limit and old[start] == new[start]:
        start += 1
    end = 0
    while end < limit - start and old[len(old) - 1 - end] == new[len(new) - 1 - end]:
        end += 1
    a, b = old[start:len(old) - end], new[start:len(new) - end]
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=max(len(a), len(b)) > HEURISTIC_FROM)
    return [(i1 + start, i2 + start, j1 + start, j2 + start)
            for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]


def tokens(text, at_end):
    """Each character of `text` as printed: one that does not print, other than a plain space, as
    <U+XXXX>, and where the text ends its line, each space at its end too."""
    keep = len(text.rstrip(" ")) if at_end else len(text)
    for i, ch in enumerate(text):
        if (ch == " " and i < keep) or (ch != " " and ch.isprintable()):
            yield ch
        else:
            yield "<U+%04X>" % ord(ch)


def fit(text, at_end, limit=LINE_CHARS):
    """(printed text, characters of `text` left out): as many whole characters as fit in `limit`."""
    out, used = [], 0
    for i, token in enumerate(tokens(text, at_end)):
        if used + len(token) > limit:
            return "".join(out), len(text) - i
        out.append(token)
        used += len(token)
    return "".join(out), 0


def shown_value(text):
    """A path or a refused value as printed, bounded."""
    printed, left = fit(text, True, VALUE_CHARS)
    return printed + (" [cut: %d more characters not shown]" % left if left else "")


def cut_note(left):
    return " [cut: %d more characters not shown]" % left if left else ""


def where(first, lo, hi):
    """Where one side of a run sits, in file line numbers."""
    if hi - lo == 1:
        return "line %d" % (first + lo)
    if hi > lo:
        return "lines %d-%d" % (first + lo, first + hi - 1)
    return "nothing, after line %d" % (first + lo - 1) if lo else "nothing, at the start of the body"


def show_pair(a, b, raw_no, fresh_no):
    """(printed lines, how many of the lines printed were cut) for one pair of lines in a run."""
    if a == b:              # a repeated line inside a run, possible where the popular-line heuristic is on
        printed, left = fit(a, True)
        return ["  = raw %d · fresh %d (the same in both): %s%s" % (raw_no, fresh_no, printed, cut_note(left))], \
            (1 if left else 0)
    p = common_prefix(a, b)
    whole_a, left_a = fit(a, True)
    whole_b, left_b = fit(b, True)
    if not left_a and not left_b:
        body_a, body_b, cuts = whole_a, whole_b, 0
    else:
        s = common_suffix(a, b, min(len(a), len(b)) - p)
        lo, tail = max(0, p - CONTEXT_CHARS), max(0, s - CONTEXT_CHARS)
        bodies, cuts = [], 0
        for text in (a, b):
            printed, left = fit(text[lo:len(text) - tail], tail == 0)
            bodies.append(("[%d characters before, the same in both] " % lo if lo else "") + printed
                          + cut_note(left) + (" [%d characters after, the same in both]" % tail if tail else ""))
            cuts += 1 if left else 0
        body_a, body_b = bodies
    lines = ["  - raw %d: %s" % (raw_no, body_a),
             "  + fresh %d (differs from character %d): %s" % (fresh_no, p + 1, body_b)]
    if unicodedata.normalize("NFKC", body_a) == unicodedata.normalize("NFKC", body_b):
        lines.append("    (these two lines may print alike: they differ in characters that look the same, such as "
                     "a composed and a decomposed accent; read them in the files)")
    return lines, cuts


def show_run(number, old, new, run, old_first, new_first):
    """(printed lines, shown in full) for one run."""
    i1, i2, j1, j2 = run
    body, left_out, cuts = [], [], 0
    if i2 - i1 == j2 - j1:
        pairs = i2 - i1
        for k in range(min(pairs, RUN_LINES)):
            lines, cut = show_pair(old[i1 + k], new[j1 + k], old_first + i1 + k, new_first + j1 + k)
            body.extend(lines)
            cuts += cut
        if pairs > RUN_LINES:
            left_out.append("%d more pairs not shown" % (pairs - RUN_LINES))
            body.append("  ... " + left_out[-1])
    else:
        for label, seq, lo, hi, first, sign in (("raw", old, i1, i2, old_first, "-"),
                                                ("fresh", new, j1, j2, new_first, "+")):
            for k in range(lo, min(hi, lo + RUN_LINES)):
                printed, left = fit(seq[k], True)
                body.append("  %s %s %d: %s%s" % (sign, label, first + k, printed, cut_note(left)))
                cuts += 1 if left else 0
            if hi - lo > RUN_LINES:
                left_out.append("%d more %s lines not shown" % (hi - lo - RUN_LINES, label))
                body.append("  ... " + left_out[-1])
    if cuts:
        left_out.append("%d line%s cut" % (cuts, "" if cuts == 1 else "s"))
    status = "SHOWN IN PART: " + ", ".join(left_out) if left_out else "shown in full"
    header = "- run %d · raw %s · fresh %s · %d line%s became %d · %s" % (
        number, where(old_first, i1, i2), where(new_first, j1, j2), i2 - i1, "" if i2 - i1 == 1 else "s",
        j2 - j1, status)
    return [header] + body, not left_out


def compare(old, new, old_first, new_first):
    """(runs, shown, why stopped): every run, the (number, lines, in full) of those printed, and why
    printing stopped before the last run (None where every run is printed)."""
    runs = differing_runs(old, new)
    shown, used, stopped = [], 0, None
    for number, run in enumerate(runs, start=1):
        if len(shown) == RUN_CAP:
            stopped = "past the cap of %d runs" % RUN_CAP
            break
        lines, full = show_run(number, old, new, run, old_first, new_first)
        size = sum(len(line) + 1 for line in lines)
        if used + size > OUTPUT_CHARS:
            stopped = "past the %d-character output limit" % OUTPUT_CHARS
            break
        shown.append((number, lines, full))
        used += size
    return runs, shown, stopped


def run_control():
    """The in-memory control: None when it behaves, else what went wrong."""
    long_line = " ".join("word%d" % k for k in range(400))
    base = ("---\nconverted_by: engine\nconverted_on: 2026-01-01\n---\n# Limits\n\nThe limit is 32 tokens "
            "per call.\n\n" + long_line + "\n")
    crlf_front = BYTE_ORDER_MARK + base.replace("\n", "\r\n", 4)   # its four frontmatter lines in CRLF, the body LF
    cases = (("a change in frontmatter only", base.replace("2026-01-01", "2026-02-02"), 0, True, None),
             ("the frontmatter written in CRLF after a byte-order mark", crlf_front, 0, True, None),
             ("a changed figure", base.replace(" 32 ", " 64 "), 1, True, "64"),
             ("a trailing space", base.replace("per call.", "per call. "), 1, True, "<U+0020>"),
             ("a carriage return ending one line", base.replace("per call.\n", "per call.\r\n"), 1, True,
              "<U+000D>"),
             ("a change deep inside a long line", base.replace("word350 ", "word350X "), 1, True, "word350X"),
             ("a run longer than RUN_LINES lines a side", base.replace("# Limits\n", "# Limits\n" + "added\n" *
                                                                         (RUN_LINES + 1)), 1, False, None))
    old_front, old, old_first = split(base)
    for label, text, want_runs, want_full, want_text in cases:
        _front, new, new_first = split(text)
        runs, shown, stopped = compare(old, new, old_first, new_first)
        if len(runs) != want_runs:
            return "%s gave %d runs, want %d" % (label, len(runs), want_runs)
        if runs and (stopped or len(shown) != 1 or shown[0][2] != want_full):
            return "%s was not shown %s" % (label, "in full" if want_full else "in part")
        if want_text and not any(want_text in line for line in shown[0][1][1:]):
            return "%s did not print the changed text %r" % (label, want_text)
    for value, want in (("", None), ("null", None), ("NULL", None), ("true", None), ('"engine"', None),
                        ("engine # note", None), ("two words", None), ("3d", None), ("~", None),
                        ("engine", "engine"), ("curl+markitdown", "curl+markitdown"), ("jina-reader", "jina-reader")):
        got = engine_of(["converted_by: " + value if value else "converted_by:"])[0]
        if got != want:
            return "an engine field of %r read as %r, want %r" % (value, got, want)
    for front in (["converted_by: engine", "  continued"], ["converted_by: engine", "converter: engine"],
                  ['"converted_by": engine'], ["converted_by:engine"], ["  converted_by: engine"]):
        if engine_of(front)[0] is not None:
            return "the frontmatter %r named an engine" % (front,)
    if engine_of(old_front)[0] != "engine":
        return "the control's own engine field did not read"
    if engine_of(split(crlf_front)[0])[0] != "engine":
        return "the engine field of the frontmatter written in CRLF did not read"
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Show every line that differs between a raw capture and a fresh re-capture by the same "
                    "engine, literally (read-only; prints, never writes; gives no freshness verdict).")
    parser.add_argument("--raw", required=True, help="the raw file the page was compiled from")
    parser.add_argument("--fresh", required=True, help="the fresh capture, made with the raw's engine")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")

    problem = run_control()
    if problem:
        print("PROBE FAILED: the in-memory control: " + problem)
        return 2

    reasons, loaded = [], {}
    for label, path in (("the raw file", args.raw), ("the fresh capture", args.fresh)):
        if not os.path.lexists(path):
            reasons.append("%s %s does not exist" % (label, shown_value(path)))
            continue
        try:
            loaded[label] = split(read_text(path))
        except OSError as exc:
            reasons.append("%s %s cannot be read (%s)" % (label, shown_value(path), exc.strerror or exc.args[0]))
            continue
        if not "".join(loaded[label][1]).strip():
            reasons.append("%s %s holds nothing but whitespace once its frontmatter is dropped: a capture that "
                           "returned nothing is not an unchanged page" % (label, shown_value(path)))
    if len(loaded) == 2 and os.path.samefile(args.raw, args.fresh):
        reasons.append("the raw file and the fresh capture are one file, so the compare would show nothing")
    engines = {}
    for label, (front, _body, _first) in loaded.items():
        engines[label] = engine_of(front)
        word, field, line, why = engines[label]
        if why:
            named = (" (its %s, line %d)" % (field, line)) if field else ""
            reasons.append("%s names no plain engine%s: %s" % (label, named, why))
    words = [engines[label][0] for label in ("the raw file", "the fresh capture") if label in engines]
    if len(words) == 2 and words[0] and words[1] and words[0] != words[1]:
        reasons.append('the engines differ (raw "%s", fresh "%s"): re-capture with the raw\'s engine and record '
                       "it exactly, since a cross-engine compare reads render noise as change"
                       % (shown_value(words[0]), shown_value(words[1])))
    if reasons:
        for reason in reasons:
            print("CANNOT COMPARE: " + reason)
        return 2

    (_rf, old, old_first), (_ff, new, new_first) = loaded["the raw file"], loaded["the fresh capture"]
    raw_engine, fresh_engine = engines["the raw file"], engines["the fresh capture"]
    print("recapture-compare: raw %s (%s: %s; body from line %d) · fresh %s (%s: %s; body from line %d) · "
          "compared literally, line by line, frontmatter dropped"
          % (shown_value(args.raw), raw_engine[1], shown_value(raw_engine[0]), old_first,
             shown_value(args.fresh), fresh_engine[1], shown_value(fresh_engine[0]), new_first))
    print("control: in memory, a change in frontmatter only, and the frontmatter written in CRLF after a "
          "byte-order mark, gave 0 runs; a changed figure, a trailing space, a carriage return ending one line "
          "and a change deep inside a long line gave 1 run each, shown in full; a run longer than %d lines a "
          "side was shown in part (fired)" % RUN_LINES)
    print("control: in memory, engine fields that were empty, null, quoted, commented, two words, continued "
          "below, written twice or without the space after the colon named no engine; plain names did, in a "
          "CRLF frontmatter too (fired)")

    runs, shown, stopped = compare(old, new, old_first, new_first)
    if not runs:
        print("IDENTICAL: the two bodies match line for line, character for character (frontmatter not compared)")
        return 0
    partial = [number for number, _lines, full in shown if not full]
    hidden = len(runs) - len(shown)
    print("DIFFERS: %d differing run%s · %d shown in full · %d shown in part · %d not shown"
          % (len(runs), "" if len(runs) == 1 else "s", len(shown) - len(partial), len(partial), hidden))
    for _number, lines, _full in shown:
        for line in lines:
            print(line)
    unread = len(partial) + hidden
    if not unread:
        print("UNREAD: none: every differing run is shown in full above")
    else:
        parts = []
        if partial:
            parts.append("shown in part: run%s %s" % ("" if len(partial) == 1 else "s",
                                                       ", ".join(str(n) for n in partial)))
        if hidden:
            i1, _i2, j1, _j2 = runs[len(shown)]
            which = ("run %d" % len(runs)) if hidden == 1 else ("runs %d to %d" % (len(shown) + 1, len(runs)))
            parts.append("not shown, %s: %s, from raw line %d · fresh line %d on"
                         % (stopped, which, old_first + i1, new_first + j1))
        print("UNREAD: %d run%s (%s): read %s in the two files at those lines before judging the page, or "
              "report the page unadjudicated with this count" % (unread, "" if unread == 1 else "s",
                                                                 "; ".join(parts), "it" if unread == 1 else "them"))
    print("read every run: a changed fact, figure, URL, requirement or instruction is material and the page "
          "re-ingests; layout, whitespace, counters and render dates are not")
    return 1


if __name__ == "__main__":
    sys.exit(main())
