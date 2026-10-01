#!/usr/bin/env python3
"""sanitise.py — the ingest skill's Step 0 sanitiser for a converted source (2026-09-10).

Replaces the `perl -i` one-liner the skill carried until 2026-09-10, which the lane fence
denies under a write grant (it refuses in-place editors). Same three edits, applied until
nothing changes, with the invariant checks built in; the suite's perl oracle is the
independent check (`test_sanitise.sh`).

One pass, in the perl line's order:
  1. strip control bytes  [\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f]
  2. defang MarkItDown's stray links: `[text](bareword)` -> `text (bareword)`; a target that
     contains `://` or starts with `#` or `mailto` is a real link and is kept unchanged
  3. break wikilink brackets: `[[` -> `[ [` and `]]` -> `] ]`
Passes repeat until a pass changes nothing (the fixpoint). A single pass leaves residues on
nested input (`[[[x]]]` -> `[ [[x] ]]`, still a wikilink; `[[a](b)](c)` leaves a fresh
bareword link); on ordinary MarkItDown output one pass is the fixpoint, so the result there is
byte-identical to the single-pass perl line it replaces.
Bytes outside those edits are preserved (surrogateescape round-trip, so a non-UTF-8 byte
survives untouched); the file's mode is preserved. The file is rewritten only after every
invariant below holds, through a temp file in the same directory and os.replace; one
`PASS <file>` line per file carries the before/after counts. A file that needs no change is
left untouched and still prints PASS.

Invariants (a broken one is a sanitiser defect: exit 3, nothing written):
  - the passes converged (MAX_PASSES below)
  - control bytes after == 0
  - `[[` and `]]` after == 0
  - bareword links after == 0 (every remaining `[text](target)` has a real target)
  - real-link tails `](<real target>)` after >= before (no kept link lost; a defang beside a
    tail can turn that tail real by removing the `[` its target began with, so the count may rise)
  - byte delta == -(control bytes) - (bareword defangs) + (`[[` breaks) + (`]]` breaks)

Write grants: an interpreter running a script file is a read to the lane fence, so its writes
are invisible there. When `LLM_WIKI_LANE_WRITES` is present in the environment (the fence sets
it for every lane; empty for a read-only lane) this script writes only inside those roots and
refuses any other file with exit 5, file untouched. Absent (an attended head), no restriction.
Exit 2: a path that is missing, a directory, unreadable, or in a directory that cannot be
written. Exit 4: bad arguments. `--dry-run` prints the PASS/FAIL line and writes nothing.

Usage: python3 -B .claude/skills/ingest/sanitise.py raw/<stem>.md [more files] [--dry-run]
"""
import os
import re
import stat
import sys

CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
LINK = re.compile(r"\[([^\]\n]*)\]\(([^)\n]*)\)")
TAIL = re.compile(r"\]\(([^)\n]*)\)")
# Adjacent bracket runs converge logarithmically; a nesting chain of depth d takes d + 1
# passes. The 50-pass safety bound is set by judgement, unmeasured for a new corpus.
MAX_PASSES = 50
WRITES_VAR = "LLM_WIKI_LANE_WRITES"


def is_real(target):
    return ("://" in target) or target.startswith("#") or target.startswith("mailto")


def norm(path):
    """As the lane fence normalises: absolute, symlink-resolved, trailing-slash-free."""
    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def within(path, roots):
    path = norm(path)
    for root in roots:
        if path == root or path.startswith(root.rstrip(os.sep) + os.sep):
            return True
    return False


def write_roots():
    """None when the fence variable is absent (no restriction); else the list, possibly empty."""
    if WRITES_VAR not in os.environ:
        return None
    return [norm(p) for p in os.environ[WRITES_VAR].split(os.pathsep) if p.strip()]


def one_pass(text):
    """The perl line once: (out, bareword defangs, `[[` breaks, `]]` breaks)."""
    out = CTRL.sub("", text)
    bare = [0]

    def defang(m):
        t, u = m.group(1), m.group(2)
        if is_real(u):
            return "[%s](%s)" % (t, u)
        bare[0] += 1
        return "%s (%s)" % (t, u)

    out = LINK.sub(defang, out)
    opens = out.count("[[")
    out = out.replace("[[", "[ [")
    closes = out.count("]]")
    out = out.replace("]]", "] ]")
    return out, bare[0], opens, closes


def transform(text):
    """Passes to the fixpoint: (out, totals dict, passes, converged)."""
    totals = {"bare": 0, "opens": 0, "closes": 0}
    cur = text
    for n in range(1, MAX_PASSES + 1):
        nxt, bare, opens, closes = one_pass(cur)
        totals["bare"] += bare
        totals["opens"] += opens
        totals["closes"] += closes
        if nxt == cur:
            return cur, totals, n, True
        cur = nxt
    return cur, totals, MAX_PASSES, False


def counts(text):
    links = LINK.findall(text)
    return {
        "bytes": len(text.encode("utf-8", "surrogateescape")),
        "ctrl": len(CTRL.findall(text)),
        "links": len(links),
        "bare_links": sum(1 for _, u in links if not is_real(u)),
        "real_tails": sum(1 for u in TAIL.findall(text) if is_real(u)),
        "dbl_open": text.count("[["),
        "dbl_close": text.count("]]"),
    }


def check(before, after, totals, converged):
    """Every invariant, each named on failure. `before` is measured on the control-stripped
    input, so the real-tail count is not disturbed by a control byte inside a target."""
    fails = []
    if not converged:
        fails.append("no fixpoint within %d passes" % MAX_PASSES)
    if after["ctrl"] != 0:
        fails.append("control bytes remain: %d" % after["ctrl"])
    if after["dbl_open"] or after["dbl_close"]:
        fails.append("`[[`/`]]` remain: %d/%d" % (after["dbl_open"], after["dbl_close"]))
    if after["bare_links"] != 0:
        fails.append("bareword links remain: %d" % after["bare_links"])
    if after["real_tails"] < before["real_tails"]:
        fails.append("real-link tails %d -> %d (a kept link was lost)"
                     % (before["real_tails"], after["real_tails"]))
    expected = -before["ctrl_original"] - totals["bare"] + totals["opens"] + totals["closes"]
    if after["bytes"] - before["bytes_original"] != expected:
        fails.append("byte delta %d, expected %d"
                     % (after["bytes"] - before["bytes_original"], expected))
    return fails


def sanitise(path, dry_run):
    if not os.path.isfile(path):
        print("FAIL %s: not a file" % path)
        return 2
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except OSError as exc:
        print("FAIL %s: unreadable (%s)" % (path, exc))
        return 2
    roots = write_roots()
    if roots is not None and not dry_run and not within(path, roots):
        print("FAIL %s: outside the lane's write grants (%s=%s) · file untouched"
              % (path, WRITES_VAR, os.environ.get(WRITES_VAR) or "<empty>"))
        return 5
    text = raw.decode("utf-8", "surrogateescape")
    stripped = CTRL.sub("", text)
    before = counts(stripped)
    before["ctrl_original"] = len(CTRL.findall(text))
    before["bytes_original"] = len(raw)
    out, totals, passes, converged = transform(text)
    after = counts(out)
    fails = check(before, after, totals, converged)
    summary = ("bytes %d→%d · control %d→0 · links %d→%d (real tails %d) · bareword defanged %d · "
               "wikilink brackets broken %d · passes %d"
               % (before["bytes_original"], after["bytes"], before["ctrl_original"],
                  before["links"], after["links"], after["real_tails"], totals["bare"],
                  totals["opens"] + totals["closes"], passes))
    if fails:
        print("FAIL %s: %s · %s · file untouched" % (path, "; ".join(fails), summary))
        return 3
    changed = out != text
    if changed and not dry_run:
        data = out.encode("utf-8", "surrogateescape")
        tmp = os.path.join(os.path.dirname(os.path.abspath(path)),
                           ".%s.sanitise-tmp" % os.path.basename(path))
        try:
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.chmod(tmp, mode)
            os.replace(tmp, path)
        except OSError as exc:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            print("FAIL %s: cannot write (%s) · file untouched" % (path, exc))
            return 2
    state = "unchanged" if not changed else ("would write (dry run)" if dry_run else "written")
    print("PASS %s: %s · %s" % (path, state, summary))
    return 0


def main(argv):
    dry_run = "--dry-run" in argv
    paths = [a for a in argv if a != "--dry-run"]
    if not paths or any(a.startswith("-") for a in paths):
        print("usage: sanitise.py <file> [more files] [--dry-run]")
        return 4
    worst = 0
    for p in paths:
        worst = max(worst, sanitise(p, dry_run))
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
