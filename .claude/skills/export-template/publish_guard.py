#!/usr/bin/env python3
"""publish_guard.py — the publish gate's payload probe (items 121 and 132, 2026-09-06).

Scans the payload that will ACTUALLY ship for four leak classes, and halts the publish like
any other gate failure:

  probe 1  machine paths      an absolute path into a per-machine home root (macOS, Linux or
                              Windows) anywhere in any file, binary content included.
  probe 2  non-text files     a file that is not source text, anywhere outside the payload's
                              declared media directory (assets/).
  probe 3  personal strings   any string identifying THIS owner, in a file's name or its
                              bytes, unless publish-allowlist.md adjudicates that string in
                              that file. The needles are derived at run time and never
                              stored, since storing them would ship them: the agent name from
                              the vault's CUSTOMISATION.md, the git identity (name tokens,
                              email local-part tokens, the origin URL's owner segment) of the
                              vault and of the scanned repo, every component of the vault's
                              absolute path, the machine account name, and any extra line in
                              the owner-local output/publish-gate-strings.txt.
  probe 4  credential values  any VALUE of 6 bytes or more in the owner's credential store (the
                              vault's output/user-notes/credentials.env, `KEY=value` lines),
                              as literal bytes in a file's name or its bytes — for a value with
                              a backslash, in every reading a shell or a dotenv reader gives it.
                              Read at run time, held in memory only, never written; a finding
                              names the KEY and the file, and every line this script prints
                              passes one output path (Withheld) that replaces each such value
                              it read, raw or in the escaped forms Python and git quote it in,
                              with a label naming its KEY. Neither caught nor withheld: a
                              shorter value, a case-changed copy, an encoded copy (base64,
                              URL-encoding). An absent store checks nothing and says so; it
                              never fails the gate.

Why both, and why here: the public payload ships `.claude/skills/**` wholesale, so anything
that lands in a skill directory ships by default. A tracked `.pyc` file can carry the owner's
absolute vault path in its bytecode; `.gitignore` cannot help once a file is tracked, and
`strip_junk()` in
export_template.sh keys on three file NAMES (__pycache__, *.pyc, .DS_Store), so the next
artefact class slips past it. This gate keys on the observable property instead — what the
bytes are, and where in the payload they sit — so it needs no list to maintain.

Ship-truth: with a git work tree the file set and the file CONTENTS both come from the
INDEX (`ls-files -s` + `cat-file --batch`), which is exactly what a commit writes; an
unstaged edit between overlay and gate therefore cannot make the guard scan a tree that
differs from the publish. A symlink's blob holds its target, so a symlink into a home
directory is caught by probe 1. Without a git work tree (a fresh build directory) the tree
is walked on disk and the output says so.

Probe 3 replaces the hand-run personal-strings gate of the export-template SKILL.md, which
depended on the operator recalling every derivation source; a hand run can omit the
punctuation-led components of the vault path and miss a fixture hit. Its rules follow
publish-allowlist.md, which is parsed rather than read: an entry names the files it covers, a
permanent entry is uncapped inside them, a provisional entry carries a per-file OCCURRENCE
count and an expiry release, and a placeholder key covers a derivation class so the shipped
allowlist never has to quote personal data.

Usage:
  python3 publish_guard.py [--vault <vault>] [--allowlist <file>] [--credentials <file>]
                           [--release <ver>] [--print-needles] <repo-clone-or-build-dir>
  python3 publish_guard.py [--vault <vault>] [--credentials <file>] --draft <file>

  --vault        the vault probe 3 derives from; default is three directories above this
                 script. --allowlist likewise defaults to the file beside it, and an override
                 of either is named on the gate's own output line.
  --credentials  the credential store probe 4 reads; default is the vault's
                 output/user-notes/credentials.env. It exists so the suite can point the
                 probe at a FAKE store; an override is named on the output line by its file
                 name only.
  --release      the candidate version: a provisional allowlist entry whose expiry it has
                 reached becomes a finding. Without it every run still reports the pending
                 expiries, for the recap to check against the version it derives.
  --print-needles  print the derived needles and their sources to the terminal, for
                 inspection during an adjudication. Never part of the gate's own output.
  --draft        one file in place of a payload: a suggestion draft, before a person files it
                 as a public issue (the suggest skill). The same probes read its name and its
                 bytes, and the path probe reads more spellings than a payload's, since a draft
                 is a person's paste: the macOS and Windows root in any case, either slash,
                 doubled or escaped, an account above ASCII, one escaped in a file URL, and a
                 Windows drive as Git Bash, WSL or Cygwin shows it. Not read as a path: a home
                 root under any other mount or on a network share, and a path encoded further
                 than that. The personal-string probe still reads the user's own names there.
                 Nothing adjudicates a hit there, so --allowlist, --release,
                 --print-needles and a directory are refused beside it, and the default agent
                 name the shipped setup.sh seeds is no needle, since it identifies nobody. A hit
                 warns: a person decides, and nothing files by itself. A draft that is empty or
                 cannot be read is exit 2.

Exit codes follow throttle.py's gate convention:
  0  clean  — one line naming what was scanned AND the self-control tally
  1  findings — the publish halts; every finding printed with its evidence
  2  broken premise — one `PROBE FAILED:` line, never a clean report

Premise failures (all exit 2, never a silent pass): the path is missing or not a directory;
the file set is empty; the set is not a framework payload (no CLAUDE.md, or no file under
.claude/skills/); any git command fails or a blob reads short; any self-control fails; no
vault is found and none is given; CUSTOMISATION.md has lost its agent_name line; the
allowlist is missing, unreadable, parses to zero entries, or holds an entry that names no
file, an unknown placeholder, a count on a permanent entry, a missing count on a provisional
one, or two paths covering one payload file; the corpus control matches nothing; the
credential store cannot be checked (its stat is refused, as under a directory the guard cannot
search), exists but cannot be read, holds a line that is not `KEY=value`, or opens a quote it
never closes (each named by line number only, never by content); the guard itself crashes (its
traceback passes the same output path, so a crash cannot print a value either). An OSError is
reported by its reason alone, never its text, which quotes the file name in escaped form.

Suite: test_publish_guard.sh beside this file.
"""

import getpass
import os
import re
import subprocess
import sys
import traceback

MEDIA_ROOT = "assets/"      # the payload's declared media directory (SPEC.md): the README
                            # images live here and the shipped .gitignore force-tracks them.
NUL_WINDOW = 8000           # git's own text/binary window, so both classifiers agree
MAX_SHOWN = 40              # per probe, so a broken payload cannot flood the gate output
BATCH = 200                 # shas per `cat-file --batch` write (see read_index)

# An absolute path into a per-machine home root, matched two ways because context differs
# with content class — the property the guard already computes for probe 2.
#   TEXT: the negative lookbehind is load-bearing. A path preceded by a path character is a
#   fragment, not an absolute path: "$W" + the Linux home root is a fixture path in
#   deep-lint/style-rerun/test_style_rerun.sh, and a URL segment of the same spelling is a
#   URL. `/` stays OUT of the exclusion class, so a `file://` URL into a home root still fires.
#   BYTES: no lookbehind. In a non-text file the preceding byte is data, not context — a
#   bytecode file can carry its path behind a marshal length byte ('o'), which the text
#   lookbehind silently swallows, so without this split the guard would miss the exact artefact
#   it was built for.
#   ROOTS: all three a home directory can have — the macOS, Linux and Windows ones. Keying
#   on the two this machine happens to use is the "instance constant" failure §12 warns
#   about; a contributor's fixture is as public as ours (critic finding, 2026-09-06).
_POSIX = rb"/(?:Users|home)/[A-Za-z0-9._-]+"
_WIN = rb"[A-Za-z]:\\Users\\[A-Za-z0-9._-]+"
HOME_TEXT_RE = re.compile(rb"(?<![A-Za-z0-9._$~-])" + _POSIX + rb"|" + _WIN)
HOME_BYTES_RE = re.compile(_POSIX + rb"|" + _WIN)

# A draft is a person's paste rather than a payload, so its rule reads the spellings a person's
# tools print, and the payload's two rules above stay as they are. It matches all they match.
#   SEPARATORS: either slash, up to four, since JSON and Python's repr double a backslash, escaping
#   that doubles it again, and some JSON writers escape a slash. The bound also keeps the scan
#   linear: unbounded, a run of 16,000 slashes took 6.2 s against 3 ms (measured 5 November 2026).
#   CASE: the macOS and Windows root in any case, since those file systems ignore case by default.
#   The Linux root stays exact: that file system keeps case, so another case is another folder.
#   ACCOUNT: any byte above ASCII, and a percent escape, the only way a file URL carries such a
#   name. A placeholder stays quiet: `$`, `<` and a `%` without two hex digits are not account
#   characters, and an ellipsis in the account's place is a name already taken out.
#   MOUNTS: a Windows drive as a POSIX shell shows it (Git Bash, WSL, Cygwin).
#   Not read: see --draft in the header above.
_D_SEP = rb"[\\/]{1,4}"
_D_ACCOUNT = rb"(?!\xe2\x80\xa6)(?:[A-Za-z0-9._\x80-\xff-]|%[0-9A-Fa-f]{2})+"
_D_USERS = rb"(?i:Users)"
_D_MOUNT = rb"(?:(?:(?:mnt|cygdrive)" + _D_SEP + rb")?[A-Za-z]" + _D_SEP + rb")?"
_DRAFT_ROOT = _D_SEP + rb"(?:" + _D_MOUNT + _D_USERS + rb"|home)" + _D_SEP + _D_ACCOUNT
_DRAFT_DRIVE = rb"[A-Za-z]:" + _D_SEP + _D_USERS + _D_SEP + _D_ACCOUNT
DRAFT_HOME_TEXT_RE = re.compile(rb"(?<![A-Za-z0-9._$~-])" + _DRAFT_ROOT + rb"|" + _DRAFT_DRIVE)
DRAFT_HOME_BYTES_RE = re.compile(_DRAFT_ROOT + rb"|" + _DRAFT_DRIVE)

# This file SHIPS inside `.claude/skills/**`, so it is inside its own scan scope — by design:
# the guard exempts nothing, because an exemption is the hole the next artefact walks through.
# Every example home path below is therefore ASSEMBLED at import time, never written as a
# literal, so the invariant stays absolute: no shipped file contains an absolute home path.
# (Written as literals, this file and its suite would halt the publish on themselves.)
_U = "/U" + "sers"
_H = "/h" + "ome"

# Self-controls: every run proves both probes can still fire and still stay quiet.
# Each row is (buffer, treat-as-text, must-match).
PATH_CONTROLS = (
    (('OUT = "%s/example/vault/wiki"' % _U).encode(), True, True),    # a machine path fires
    (('cat "$W%s/.llm-wiki/last-run.txt"' % _H).encode(), True, False),  # a fragment does not
    (b'the agent home is ~/.llm-wiki/ and $HOME/notes', True, False),  # tilde/var forms do not
    (('see https://example.com%s/guide' % _U).encode(), True, False),  # a URL segment does not
    (('\x6f%s/example/vault/mod.py' % _U).encode("latin-1"), False, True),  # bytes behind a
    (('\x6f%s/example/vault/mod.py' % _U).encode("latin-1"), True, False),  # length byte: the
    (b'OUT = "D:' + b'\\Users\\example\\vault"', True, True),   # the Windows home root fires
)                                              # binary rule fires, the text rule rightly does not
CLASS_CONTROLS = (
    (b"\x89PNG\r\n\x1a\n\x00\x00", False),   # NUL-bearing bytes are not text
    (b"", True),                             # an empty file (.gitkeep) IS text
    (b"# a plain source line\n", True),      # ordinary source is text
)

# ── probe 3: personal strings ────────────────────────────────────────────────
# The strings that identify THIS owner are derived at run time from the vault beside this
# script, never stored, because storing them would ship them. Deriving them also puts the
# derivation under test, which is the half the hand-run gate kept losing (a hand run that omits
# the punctuation-led components of the vault path misses a fixture hit).
MIN_NEEDLE = 4              # bytes. Set by judgement against the live needle set, whose
                            # shortest member is 5 bytes. The floor drops the generic short
                            # components a system or temp root contributes (var, tmp, usr,
                            # opt, lib, a single-letter mount) and keeps every owner string
                            # this vault derives. A deliberately short string belongs in the
                            # gate-strings file, which is exempt from the floor.
ALLOWLIST_NAME = "publish-allowlist.md"                  # adjudications, beside this script
GATE_STRINGS_REL = "output/publish-gate-strings.txt"     # owner-local extras, never shipped
CONTROL_NEEDLE = b"CLAUDE.md"   # check_payload_shape asserts this path is in the payload, so
                                # any pass that iterated the corpus at all matches it once.
# The home-root markers are probe 1's own grammar (_POSIX's alternation), so this is one
# source of truth, not a second instance constant. They are the OS's word rather than the
# owner's and identify nobody outside path context, which probe 1 owns. The account name that
# FOLLOWS the marker stays a needle, and a vault outside a home root loses nothing.
HOME_MARKERS = ("Users", "home")
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)   # tokens of a person name or an email local part
DRIVE_RE = re.compile(r"^[A-Za-z]:$")
ORIGIN_RE = re.compile(r"(?:://[^/]+/|:)([^/]+)/[^/]+?(?:\.git)?/?$")
AGENT_NAME_RE = re.compile(r"^[ \t]*-[ \t]*\*\*agent_name\*\*[ \t]*:(.*)$", re.M)

# An allowlist key is a literal string or a placeholder standing for a derivation class,
# because the allowlist SHIPS and may not quote personal data. Every class is expressible, so
# an adjudication never has to fall back to writing the string out.
PLACEHOLDERS = {
    "<agent name>": "agent-name",
    "<repo owner handle>": "origin-owner",
    "<licence holder's legal name>": "name-token",
    "<owner email token>": "email-token",
    "<machine account name>": "account",
    "<vault path component>": "path-component",
    "<extra gate string>": "extra",
}
ENTRY_RE = re.compile(r"^-[ \t]+(.+?)[ \t]+::[ \t]+(.+?)[ \t]+::[ \t]+(.+)$", re.M)
ALLOW_PATH_RE = re.compile(r"`([^`]+)`(?:[ \t]*\((\d+)\))?")
EXPIRY_RE = re.compile(r"PROVISIONAL.{0,40}?expires at (v?[0-9][0-9.]*)", re.I | re.S)
VERSION_RE = re.compile(r"^v?([0-9]+(?:\.[0-9]+)*)$")

# ── probe 4: credential values ───────────────────────────────────────────────
# The owner's secrets live in one owner-local store of `KEY=value` lines inside the vault,
# never shipped. The probe reads the VALUES at run time and looks for each one, as literal
# bytes, in every payload file's name and content. A value is never stored, logged or printed:
# it is held in memory for the run, a finding names its KEY, and every printed line passes
# Withheld below, which replaces any value the run has read before the line leaves the process.
CREDENTIALS_REL = "output/user-notes/credentials.env"   # owner-local, never shipped
MIN_CREDENTIAL = 6          # bytes. Set by judgement, unmeasured: a shorter value (a PIN, an
                            # `admin`-style user name, a yes/no flag) is ordinary payload text,
                            # so scanning it would halt every publish on a coincidence that no
                            # allowlist may adjudicate. Values under the floor are counted on
                            # every run, never silently dropped.
CRED_KEY_RE = re.compile(rb"^[A-Za-z_][A-Za-z0-9_]*$")
CRED_COMMENT_RE = re.compile(rb"\s#")    # in an UNQUOTED value, whitespace then `#` opens a
                                         # comment. Cutting there keeps a substring of the true
                                         # value, so a leak of the whole value is still caught.
# How the readers of an env file undo a backslash, where they part (see value_readings).
# Inside double quotes a POSIX shell's `source` undoes \$ \` \" \\ and keeps any other
# backslash; a dotenv reader undoes \\ \' \" and the C escapes \a \b \f \n \r \t \v; the two
# agree on \" and \\ only, which is the guard's own reading. Inside single quotes a shell undoes
# nothing and a dotenv reader undoes \\ and \'.
DQ_COMMON = {b'"': b'"', b"\\": b"\\"}
DQ_SHELL = {b'"': b'"', b"\\": b"\\", b"$": b"$", b"`": b"`"}
DQ_DOTENV = {b'"': b'"', b"\\": b"\\", b"'": b"'", b"a": b"\x07", b"b": b"\x08",
             b"f": b"\x0c", b"n": b"\n", b"r": b"\r", b"t": b"\t", b"v": b"\x0b"}
SQ_DOTENV = {b"\\": b"\\", b"'": b"'"}
# git's C-style path quoting: these bytes get a letter or a backslash; any other control byte,
# DEL and (with core.quotePath on, git's default) every byte from 0x80 up is written in octal.
C_QUOTE = {0x07: b"\\a", 0x08: b"\\b", 0x09: b"\\t", 0x0a: b"\\n", 0x0b: b"\\v",
           0x0c: b"\\f", 0x0d: b"\\r", 0x22: b'\\"', 0x5c: b"\\\\"}


class Premise(Exception):
    """A broken premise: one PROBE FAILED line and exit 2, never a clean report."""


def os_reason(err):
    """What an OSError says, without the file name its text would quote.

    str() of an OSError quotes the file name in Python's escaped form (a backslash doubled, a
    control byte as \\x01), which an exact-bytes scrub can miss. Every message here names its
    file itself, so the reason (`Permission denied`) is all it needs from the error.
    """
    return err.strerror or type(err).__name__


def drop_os_names(err):
    """Delete the file names every OSError in a crash's chain carries, so a traceback prints each
    one's reason alone, as os_reason does for a premise message."""
    seen, stack = set(), [err]
    while stack:
        e = stack.pop()
        if e is None or id(e) in seen:
            continue
        seen.add(id(e))
        if isinstance(e, OSError):
            for attr in ("filename", "filename2"):
                try:
                    delattr(e, attr)
                except (AttributeError, TypeError):
                    pass
        stack.extend((e.__cause__, e.__context__))
        stack.extend(getattr(e, "exceptions", ()))


def c_quoted(value, high_octal):
    """`value` as git's C-style path quoting writes it, with core.quotePath on or off."""
    out = bytearray()
    for b in value:
        if b in C_QUOTE:
            out += C_QUOTE[b]
        elif b < 0x20 or b == 0x7f or (high_octal and b >= 0x80):
            out += b"\\%03o" % b
        else:
            out.append(b)
    return bytes(out)


def escaped_forms(value):
    """Every escaped form a message can quote `value` in, other than its raw bytes.

    A message that quotes a path rarely quotes it raw: an OSError and a `%r` print Python's repr,
    and git prints C-style quoting; each escapes a backslash, a quote, a control byte and (some)
    non-ASCII. Each maps a character on its own, so the escaped value is a substring of the
    escaped path that holds it — except for the quote a repr picks for the WHOLE string, which is
    why the forms under both quote choices are taken: a suffix that forces each choice is repr'd
    with the value and its own escaped form cut off again.
    """
    text = value.decode("utf-8", "surrogateescape")
    forms = [value.replace(b"\\", b"\\\\"),
             repr(value + b"'\"")[2:-1][:-3].encode("ascii"),          # bytes, '-quoted
             repr(text + "'\"")[1:-1][:-3].encode("utf-8", "surrogateescape"),   # text, '-quoted
             c_quoted(value, True), c_quoted(value, False)]
    if b'"' not in value:              # a string holding ' and no " is repr'd inside "…"
        forms.append(repr(value + b"'")[2:-1][:-1].encode("ascii"))
        forms.append(repr(text + "'")[1:-1][:-1].encode("utf-8", "surrogateescape"))
    return [f for f in dict.fromkeys(forms) if f != value]


class Withheld:
    """The one output path. Every line this script prints goes through `emit`.

    Once `arm` has been handed the run's credential values, `scrub` replaces each occurrence of
    any of them with a label naming its KEY, longest first in one pass, and then checks the
    result: a line that still carries one (only possible if replacements abut into one) is
    withheld whole. Each value is armed raw AND in every escaped form of it (escaped_forms) under
    the same label, because an OSError, a `%r` and git's stderr quote a path in escaped form and
    an exact-bytes match would miss that copy. That makes the guarantee structural rather than
    per call site: a finding line, a payload path that carries a value in a file NAME, a probe-3
    needle that happens to equal a value, the scanned root's own path, a premise message and a
    crash traceback all leave through here. Values sit in this object's memory for the life of
    the process and are written nowhere. Values under MIN_CREDENTIAL are not armed: at that
    length a value is ordinary text, the premise of the floor, so the guard can tell neither a
    leak nor a print of one. Matching is literal, so a case-changed or encoded copy (base64,
    URL-encoding) is not withheld either.
    """

    WITHHELD_LINE = b"[line withheld: it would have carried a credential value]"

    def __init__(self):
        self._labels = {}
        self._pattern = None

    def arm(self, values):
        """`values` is {value bytes: [KEY, ...]}; replaces any earlier arming."""
        labels = {v: ("[value of %s withheld]" % "/".join(keys)).encode("ascii")
                  for v, keys in values.items()}
        for v in values:                  # every raw value first, so where an escaped form of
            for form in escaped_forms(v):  # one equals another's raw bytes, the raw KEY names it
                labels.setdefault(form, labels[v])
        self._labels = labels
        order = sorted(labels, key=len, reverse=True)
        self._pattern = re.compile(b"|".join(re.escape(v) for v in order)) if order else None

    def scrub(self, data):
        if self._pattern is None:
            return data
        data = self._pattern.sub(lambda m: self._labels[m.group()], data)
        if any(v in data for v in self._labels):
            return self.WITHHELD_LINE
        return data

    def emit(self, line):
        data = self.scrub(line.encode("utf-8", "surrogateescape"))
        out = getattr(sys.stdout, "buffer", None)
        if out is None:                       # a stream with no byte layer: text, same bytes
            sys.stdout.write(data.decode("utf-8", "replace") + "\n")
            sys.stdout.flush()
            return
        out.write(data + b"\n")
        out.flush()


OUT = Withheld()


def is_text(blob):
    """git's own rule, applied to our bytes: a NUL in the first NUL_WINDOW bytes."""
    return b"\x00" not in blob[:NUL_WINDOW]


def first_nul(blob):
    return blob[:NUL_WINDOW].find(b"\x00")


def run_git(root, args):
    """Run one git command under `root`; any non-zero exit is a broken premise."""
    cmd = ["git", "-C", root] + args
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as err:
        raise Premise("cannot run git (%s)" % os_reason(err))
    if p.returncode != 0:
        # git's own words are kept: they carry the remedy (a refused safe.directory, a locked
        # index). A path in them is C-quoted, a form Withheld arms, and decoding them with
        # surrogateescape hands the scrub the very bytes git wrote rather than a replaced copy.
        raise Premise("`%s` exited %d: %s"
                      % (" ".join(cmd), p.returncode,
                         p.stderr.decode("utf-8", "surrogateescape").strip()[:200]))
    return p.stdout


def has_index(root):
    """Is THIS directory a repository whose index will be committed?

    Keyed on a `.git` entry at the root itself (a directory, or a file for a linked work
    tree), never on `rev-parse --is-inside-work-tree`: the default build directory sits
    INSIDE the vault repo, where rev-parse says yes and `ls-files` then returns the vault's
    tracked paths under that prefix — none, since the build is gitignored — so the guard
    would call a real payload empty. A build tree has no `.git` of its own; a publish clone
    does. When one exists, git must work: falling back to the disk here would silently
    change what the gate scanned.
    """
    if not os.path.exists(os.path.join(root, ".git")):
        return False
    try:
        p = subprocess.run(["git", "-C", root, "rev-parse", "--git-dir"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as err:
        raise Premise("%s has a .git entry but git will not run (%s)" % (root, os_reason(err)))
    if p.returncode != 0:
        raise Premise("%s has a .git entry but `git rev-parse` exited %d"
                      % (root, p.returncode))
    return True


def read_index(root):
    """Yield (path, mode, blob) for every staged entry — the bytes a commit would write."""
    out = run_git(root, ["ls-files", "-s", "-z"])
    entries = []
    for rec in out.split(b"\0"):
        if not rec:
            continue
        meta, _, path = rec.partition(b"\t")
        bits = meta.split()
        if len(bits) < 3 or not path:
            raise Premise("unparseable `git ls-files -s` record (%d bytes; not shown, since the "
                          "path in it may carry a value)" % len(rec))
        entries.append((path.decode("utf-8", "surrogateescape"),
                        bits[0].decode(), bits[1].decode()))
    if not entries:
        return []
    # gitlinks (submodules) have no blob to read — reported, never silently skipped.
    blobs = [e for e in entries if e[1] != "160000"]
    proc = subprocess.Popen(["git", "-C", root, "cat-file", "--batch"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    result = []
    # Chunked on purpose: writing every sha at once deadlocks a large payload — git stops
    # reading stdin while its own stdout pipe is full of blob bytes nobody is draining yet.
    # A chunk of shas is a few KB, always smaller than the pipe buffer, and its responses are
    # read before the next chunk is written, so neither side can block.
    for i in range(0, len(blobs), BATCH):
        chunk = blobs[i:i + BATCH]
        try:
            proc.stdin.write(("\n".join(sha for _, _, sha in chunk) + "\n").encode())
            proc.stdin.flush()
        except (BrokenPipeError, OSError) as err:
            raise Premise("`git cat-file --batch` closed its input early (%s)" % os_reason(err))
        for path, mode, sha in chunk:
            header = proc.stdout.readline()
            if not header:
                raise Premise("`git cat-file --batch` ended early at %s" % path)
            parts = header.split()
            if len(parts) != 3 or parts[1] != b"blob":
                raise Premise("`git cat-file --batch` answered %r for %s" % (header[:80], path))
            size = int(parts[2])
            blob = proc.stdout.read(size)
            if len(blob) != size:
                raise Premise("short read for %s (%d of %d bytes)" % (path, len(blob), size))
            proc.stdout.read(1)          # the trailing newline cat-file adds
            result.append((path, mode, blob))
    proc.stdin.close()
    proc.stdout.close()
    proc.wait()
    if proc.returncode != 0:
        raise Premise("`git cat-file --batch` exited %d" % proc.returncode)
    for path, mode, _sha in entries:
        if mode == "160000":
            result.append((path, mode, None))   # unreadable by construction
    return result


def read_tree(root):
    """No index: walk the directory. Used for a fresh build dir, which is not a repo."""
    result = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in sorted(files):
            full = os.path.join(base, name)
            if os.path.islink(full):
                target = os.readlink(full)
                result.append((os.path.relpath(full, root), "120000", target.encode()))
                continue
            try:
                with open(full, "rb") as fh:
                    result.append((os.path.relpath(full, root), "100644", fh.read()))
            except OSError as err:
                raise Premise("cannot read %s (%s)" % (full, os_reason(err)))
    return result


def home_hits(blob, text, draft=False):
    """Machine-path matches in one file. The rule follows the content class (see the regexes)."""
    if draft:
        return (DRAFT_HOME_TEXT_RE if text else DRAFT_HOME_BYTES_RE).finditer(blob)
    return (HOME_TEXT_RE if text else HOME_BYTES_RE).finditer(blob)


# ── probe 3, derivation ──────────────────────────────────────────────────────

def path_components(path):
    """The owner's own components of an absolute path, in order.

    A leading drive letter and a leading home-root marker are the machine's, not the owner's
    (see HOME_MARKERS); everything from the account name onward is the owner's. Components
    are kept VERBATIM and never split: splitting a punctuation-led component into its word
    would fire on ordinary prose while adding no personal string: the component is the
    personal shape, and probe 1 already owns the full-path form.
    """
    comps = [c for c in re.split(r"[\\/]+", path) if c]
    if comps and DRIVE_RE.match(comps[0]):
        comps = comps[1:]
    if comps and comps[0] in HOME_MARKERS:
        comps = comps[1:]
    return comps


def name_tokens(text):
    """Word tokens of a person name or an email local part.

    Tokenised where a path component is not, because the whole string is useless as a needle
    and one of its tokens is the string that leaks: a legal name carries titles and brackets,
    an email local part joins an id to a handle. A whitespace split would keep the brackets
    and never match the bare given name — the case DERIVATION_CONTROLS pins.
    """
    return TOKEN_RE.findall(text)


def origin_owners(urls):
    """The owner segment of each remote URL, both the https and the ssh spelling."""
    out = []
    for url in urls:
        m = ORIGIN_RE.search(url.strip())
        if m:
            out.append(m.group(1))
    return out


def read_agent_name(vault):
    """The `agent_name` value from the vault's CUSTOMISATION.md Settings list.

    A missing line is a broken premise (the file's shape changed under us); a present and
    blank one is legitimate — a user may clear it — and yields no needle.
    """
    path = os.path.join(vault, "CUSTOMISATION.md")
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as err:
        raise Premise("cannot read CUSTOMISATION.md (%s)" % os_reason(err))
    value = agent_name_value(text)
    if value is None:
        raise Premise("CUSTOMISATION.md has no `agent_name` line in its Settings list — "
                      "the preference layer's shape changed, so the agent name cannot be derived")
    return value


def agent_name_value(text):
    """The `agent_name` value in a Settings list's text, or None where the line is absent."""
    m = AGENT_NAME_RE.search(text)
    if not m:
        return None
    return re.split(r"\s[—-]\s", m.group(1).strip(), maxsplit=1)[0].strip()


def seeded_agent_name():
    """The default `agent_name` the shipped setup.sh seeds, or None where it cannot be read.

    Read from payload/setup.sh beside this script and never stored here, so a changed default
    needs no edit. None keeps the agent name a needle, which is the stricter scan.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "payload", "setup.sh")
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return agent_name_value(fh.read()) or None
    except OSError:
        return None


def git_identity(root):
    """(name tokens, email local-part tokens, origin owners) from one repository's config.

    Read from the vault AND from the scanned repo: the clone is what commits the payload, so
    its identity is as publishable as the vault's. A directory with no git config contributes
    nothing rather than failing — an unset identity is legitimate.
    """
    def cfg(key):
        try:
            p = subprocess.run(["git", "-C", root, "config", "--get", key],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError:
            return ""
        return p.stdout.decode("utf-8", "replace").strip() if p.returncode == 0 else ""
    names = name_tokens(cfg("user.name"))
    email = cfg("user.email")
    local = name_tokens(email.split("@", 1)[0]) if email else []
    urls = [u for u in (cfg("remote.origin.url"), cfg("remote.origin.pushurl")) if u]
    return names, local, origin_owners(urls)


def account_names():
    """The machine account name, which a vault outside a home root would not otherwise yield."""
    out = []
    try:
        out.append(getpass.getuser())
    except Exception:
        pass
    home = os.path.basename(os.path.expanduser("~").rstrip("/\\"))
    if home:
        out.append(home)
    return out


def read_gate_strings(vault):
    """Extra needles the owner keeps outside the vault's derivable surfaces.

    Affiliation, a second handle, an ORCID: strings only the owner can name. The file is
    owner-local and never shipped; absent is normal and reported, unreadable is a premise
    failure, and its lines are exempt from MIN_NEEDLE because the owner wrote them on purpose.
    """
    path = os.path.join(vault, GATE_STRINGS_REL)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError as err:
        raise Premise("cannot read %s (%s)" % (GATE_STRINGS_REL, os_reason(err)))
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def derive_needles(vault, repos):
    """{needle.lower(): (text, {source classes})} — every owner string, with where it came from.

    A needle can arise from two sources (the agent name that is also the vault directory; the
    handle that is also an email token), so sources are a SET and an allowlist placeholder
    matches when its class is anywhere in that set. Anything else would make a clean payload
    halt on a needle whose entry named the other source.
    """
    found = {}
    dropped = []

    def add(text, source):
        text = (text or "").strip()
        if not text:
            return
        if source != "extra" and len(text.encode("utf-8")) < MIN_NEEDLE:
            dropped.append(text)
            return
        key = text.lower()
        if key not in found:
            found[key] = [text, set()]
        found[key][1].add(source)

    add(read_agent_name(vault), "agent-name")
    for root in repos:
        names, local, owners = git_identity(root)
        for t in names:
            add(t, "name-token")
        for t in local:
            add(t, "email-token")
        for t in owners:
            add(t, "origin-owner")
    for form in {os.path.abspath(vault), os.path.realpath(vault)}:
        for c in path_components(form):
            add(c, "path-component")
    for a in account_names():
        add(a, "account")
    extra = read_gate_strings(vault)
    for s in (extra or []):
        add(s, "extra")
    return ({k: (v[0], frozenset(v[1])) for k, v in found.items()},
            sorted(set(dropped)), extra)


# ── probe 3, matching ────────────────────────────────────────────────────────

def needle_pattern(needles):
    """One alternation, longest first, every needle escaped.

    Longest first because per-file caps are per needle: with a short needle ahead of a longer
    one that contains it, every hit is attributed to the short needle and the long one's cap
    is never tested.
    """
    if not needles:
        return None
    parts = sorted(needles, key=len, reverse=True)
    return re.compile(b"|".join(re.escape(p.encode("utf-8")) for p in parts), re.IGNORECASE)


def scan_needles(entries, pattern):
    """{(needle.lower(), path): [count, first offset, sample, in name, in content]}.

    Both branches matter: a personal string leaks as readily through a file NAME as through
    its bytes, and through a compiled artefact's bytes as readily as through source text.
    """
    hits = {}
    if pattern is None:
        return hits

    def record(path, blob, in_name):
        for m in pattern.finditer(blob):
            key = (m.group().decode("utf-8", "replace").lower(), path)
            row = hits.get(key)
            if row is None:
                hits[key] = [1, m.start(), m.group().decode("utf-8", "replace"),
                             in_name, not in_name]
            else:
                row[0] += 1
                if in_name:
                    row[3] = True
                else:
                    row[4] = True

    for path, _mode, blob in entries:
        record(path, path.encode("utf-8", "surrogateescape"), True)
        if blob is not None:
            record(path, blob, False)
    return hits


# ── probe 3, the allowlist ───────────────────────────────────────────────────

def parse_version(text):
    m = VERSION_RE.match(text.strip())
    if not m:
        return None
    return tuple(int(x) for x in m.group(1).split("."))


def version_at_least(candidate, expiry):
    """True when the candidate release has reached the expiry, v1.0 and v1.0.0 comparing equal."""
    n = max(len(candidate), len(expiry))
    return candidate + (0,) * (n - len(candidate)) >= expiry + (0,) * (n - len(expiry))


def read_allowlist(path):
    """Parse the adjudications. Every rule the file states about itself is enforced here.

    Each entry names the FILES it covers, permanent entries included: a permanent allowance
    that floated free of its files would let the owner's name spread from the LICENSE line it
    was adjudicated for into any file that later quoted it, and still report clean.
    """
    if not os.path.exists(path):
        raise Premise("%s is missing — a publish cannot be adjudicated without it" % ALLOWLIST_NAME)
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as err:
        raise Premise("cannot read %s (%s)" % (ALLOWLIST_NAME, os_reason(err)))
    entries = []
    for key, where, why in ENTRY_RE.findall(text):
        key = key.strip()
        if key.startswith("<") and key.endswith(">") and key not in PLACEHOLDERS:
            raise Premise("%s entry `%s` names an unknown placeholder — the known ones are %s"
                          % (ALLOWLIST_NAME, key, ", ".join(sorted(PLACEHOLDERS))))
        paths = {}
        for p, count in ALLOW_PATH_RE.findall(where):
            paths[p.strip("/")] = int(count) if count else None
        if not paths:
            raise Premise("%s entry `%s` names no file in backticks — an allowance with no "
                          "file cannot be scoped" % (ALLOWLIST_NAME, key))
        m = EXPIRY_RE.search(where)
        expiry = parse_version(m.group(1)) if m else None
        provisional = m is not None
        if provisional and expiry is None:
            raise Premise("%s entry `%s` is provisional but its expiry release does not parse"
                          % (ALLOWLIST_NAME, key))
        missing = [p for p, c in paths.items() if (c is None) == provisional]
        if missing:
            raise Premise("%s entry `%s`: %s %s a per-file count"
                          % (ALLOWLIST_NAME, key, ", ".join(sorted(missing)),
                             "needs" if provisional else "must not carry"))
        entries.append({"key": key, "placeholder": PLACEHOLDERS.get(key),
                        "provisional": provisional, "expiry": expiry,
                        "expiry_text": m.group(1) if m else "", "paths": paths, "why": why})
    if not entries:
        raise Premise("%s parsed to 0 entries — its format changed and every adjudication "
                      "would silently stop applying" % ALLOWLIST_NAME)
    return entries


def entry_cap(entry, path):
    """The cap this entry sets for one payload file, or None when it does not cover it.

    Suffix matching is anchored on a path component, so an entry naming a file never covers a
    different file whose name merely ends with those characters.
    """
    # A literal key writes its own string into this file, so the entry covers its key inside
    # the file that declares it. Not an exemption: it is scoped to the one string the entry
    # already adjudicates, and any OTHER personal string reaching the allowlist still halts.
    # An entry with a literal key would otherwise halt the publish on the allowlist itself.
    if not entry["placeholder"] and (path == ALLOWLIST_NAME or path.endswith("/" + ALLOWLIST_NAME)):
        return -1
    # Longest suffix wins, and the binding is unambiguous by construction: two DISTINCT
    # entry paths of equal length cannot both be component-anchored suffixes of one payload
    # path, so a tie needs no rule, and no ambiguity check sits here: a branch that can never
    # run is worse than none, because it reads as a hazard someone handled.
    best = None
    for p, count in entry["paths"].items():
        if path == p or path.endswith("/" + p):
            if best is None or len(p) > len(best[0]):
                best = (p, count)
    if best is None:
        return None
    return (best[1] if entry["provisional"] else -1)     # -1 = covered, uncapped


def adjudicate(hits, needles, entries):
    """Split probe 3's hits into allowed and unallowed, and count each entry's use."""
    unallowed, used = [], {i: 0 for i in range(len(entries))}
    allowed_total = 0
    for (needle, path), row in sorted(hits.items()):
        count, off, sample, in_name, in_content = row
        sources = needles.get(needle, ("", frozenset()))[1]
        verdict = None
        for i, entry in enumerate(entries):
            if entry["placeholder"]:
                if entry["placeholder"] not in sources:
                    continue
            elif entry["key"].lower() != needle:
                continue
            cap = entry_cap(entry, path)
            if cap is None:
                verdict = verdict or ("scope", entry)
                continue
            if cap == -1 or count <= cap:
                used[i] += count
                verdict = ("allowed", entry)
                break
            verdict = ("cap", entry, cap)
        if verdict and verdict[0] == "allowed":
            allowed_total += count
            continue
        where = "name" if in_name and not in_content else \
                ("content" if in_content and not in_name else "name+content")
        if verdict and verdict[0] == "cap":
            why = "over the cap of %d in `%s`" % (verdict[2], verdict[1]["key"])
        elif verdict and verdict[0] == "scope":
            why = "`%s` allows this string, but not in this file" % verdict[1]["key"]
        else:
            why = "no allowlist entry"
        unallowed.append((path, off, sample, count, where,
                          ",".join(sorted(sources)) or "?", why))
    return unallowed, used, allowed_total


# ── probe 4, the credential store ────────────────────────────────────────────

def unescape(text, table):
    """`text` read left to right as one reader reads it: a backslash and the byte after it are
    one unit, which becomes `table`'s entry for that byte, or stays as written when it has none."""
    out, i = bytearray(), 0
    while i < len(text):
        unit = text[i:i + 2]
        if unit[:1] == b"\\" and len(unit) == 2:
            out += table.get(unit[1:], unit)
            i += 2
        else:
            out += text[i:i + 1]
            i += 1
    return bytes(out)


def shell_unquoted(text):
    """An unquoted value's backslashes as a POSIX shell's `source` reads them: each quotes the
    byte after it and is itself dropped (a lone last one continues the line, so it goes too)."""
    out, i = bytearray(), 0
    while i < len(text):
        if text[i:i + 1] == b"\\":
            out += text[i + 1:i + 2]
            i += 2
        else:
            out += text[i:i + 1]
            i += 1
    return bytes(out)


def value_readings(text, quote):
    """Every value the common readers of an env file can hold for one line's value `text`, the
    guard's own reading first, without repeats.

    The readers are a POSIX shell's `source` and a dotenv reader (the escapes each undoes are
    listed above DQ_COMMON), plus the text as written, which is what a paste of the store's own
    line carries. They agree on a value with no backslash: that value has one reading. Where they
    part, every reading is scanned and armed, so a leak or a print of the value is caught
    whichever of these readers holds it. Only backslashes are read differently: a reading made
    by cutting a value (a shell ending an unquoted value at a blank) would be a shorter, commoner
    string, and could halt a publish on a word the payload rightly carries.
    """
    if quote == b'"':
        forms = (unescape(text, DQ_COMMON), text, unescape(text, DQ_SHELL),
                 unescape(text, DQ_DOTENV))
    elif quote == b"'":
        forms = (text, unescape(text, SQ_DOTENV))
    else:
        forms = (text, shell_unquoted(text))
    return tuple(dict.fromkeys(forms))


def parse_credentials(data):
    """[(KEY, readings)] from the bytes of a `KEY=value` store, in file order.

    Blank lines and `#` lines are skipped; an `export ` prefix is dropped; a value in single or
    double quotes is taken up to its closing quote (inside double quotes a backslash and the byte
    after it are one unit, so `\\"` never closes one); an unquoted value is cut at an inline
    comment. `readings` is value_readings of what is left. What that guarantees: whichever of
    the readers value_readings names holds the value, the value is one of the readings or
    contains one (a cut at an inline comment or at a closing quote keeps a prefix), so a paste of
    it is caught. Not modelled, and so scanned only as those readings give it: a `$` expansion
    or command substitution, a quote inside an unquoted word, a shell ending an unquoted value
    at a blank, and a reader that ends a quoted value at a different quote. A line the guard
    cannot read is a broken premise named by its NUMBER only: its bytes may be a value, so no
    message carries them.
    """
    pairs = []
    lines = data.split(b"\n")
    if lines and lines[0].startswith(b"\xef\xbb\xbf"):
        lines[0] = lines[0][3:]
    for n, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s or s.startswith(b"#"):
            continue
        if s.startswith(b"export ") or s.startswith(b"export\t"):
            s = s[len(b"export"):].lstrip()
        key, sep, value = s.partition(b"=")
        key = key.strip()
        if not sep or not CRED_KEY_RE.match(key):
            raise Premise("line %d of the credential store is not a KEY=value line, so the guard "
                          "cannot tell what it holds (its content is not shown: it may be a value)"
                          % n)
        value = value.strip()
        quote = value[:1]
        if quote in (b'"', b"'"):
            end, i = -1, 1
            while i < len(value):
                if quote == b'"' and value[i:i + 1] == b"\\":
                    i += 2
                    continue
                if value[i:i + 1] == quote:
                    end = i
                    break
                i += 1
            if end < 0:
                raise Premise("line %d of the credential store opens a quote it never closes — a "
                              "value spanning lines cannot be read (its content is not shown)" % n)
            text = value[1:end]
        else:
            quote, text = b"", value
            m = CRED_COMMENT_RE.search(text)
            if m:
                text = text[:m.start()].rstrip()
        pairs.append((key.decode("ascii"), value_readings(text, quote)))
    return pairs


def read_credentials(path, label):
    """(pairs, note) from the store at `path`; pairs is None when there is no store.

    Absent is normal — a fresh clone has no store — and is said on the output line, never a
    failure. Absent means the system SAYS so: no such file, or a path component that is not a
    directory. A link whose target is missing is absent too, and the note says which. A store
    whose presence cannot be checked (its stat refused, as under a directory the guard cannot
    search) or that exists but cannot be read is a broken premise: a publish must not pass over
    secrets the gate could not see, and os.path.exists, which returns False on a refused stat,
    cannot tell that store from an absent one. `label` is what the messages name (the
    vault-relative default, or the file name of an override), so no message carries an owner
    path.
    """
    try:
        os.stat(path)
    except (FileNotFoundError, NotADirectoryError):
        if os.path.islink(path):
            return None, "no credential file at %s (a link whose target is missing)" % label
        return None, "no credential file at %s" % label
    except OSError as err:
        raise Premise("the credential store %s cannot be checked (%s) — a store the gate cannot "
                      "see is never taken as absent" % (label, os_reason(err)))
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as err:
        raise Premise("the credential store %s exists but cannot be read (%s) — the gate cannot "
                      "see the values it must keep out" % (label, os_reason(err)))
    return parse_credentials(data), None


def credential_values(pairs):
    """({reading: [KEY, ...]} for every reading at or above MIN_CREDENTIAL, count of keys whose
    every reading is under the floor, count of empty values).

    Grouped by reading, because two keys can hold one secret and a finding names them all.
    """
    values, short, empty = {}, 0, 0
    for key, readings in pairs:
        if not readings[0]:
            empty += 1
            continue
        kept = [r for r in readings if len(r) >= MIN_CREDENTIAL]
        if not kept:
            short += 1
        for r in kept:
            keys = values.setdefault(r, [])
            if key not in keys:
                keys.append(key)
    return values, short, empty


def scan_credentials(entries, values):
    """[(path, KEY names, count, first offset, where)] for every file carrying a value.

    Literal bytes, case-sensitive: a secret is a literal and its leak is a paste. Both branches,
    as probe 3: a file NAME and a file's bytes, binary and media files included. The readings
    that name the same KEY(s) are one alternation, longest first, so a file carrying a value read
    two ways gives one row and one paste counts once. Nothing here keeps a matched byte, so no
    row can carry a value.
    """
    found = []
    if not values:
        return found
    groups = {}
    for value, keys in values.items():
        groups.setdefault("/".join(keys), []).append(value)
    patterns = [(label, re.compile(b"|".join(re.escape(v)
                                             for v in sorted(vs, key=len, reverse=True))))
                for label, vs in sorted(groups.items())]
    for path, _mode, blob in entries:
        name = path.encode("utf-8", "surrogateescape")
        for label, pattern in patterns:
            in_name = [m.start() for m in pattern.finditer(name)]
            in_body = [m.start() for m in pattern.finditer(blob)] if blob is not None else []
            if not (in_name or in_body):
                continue
            off = in_name[0] if in_name else in_body[0]
            where = "name+content" if in_name and in_body else ("name" if in_name else "content")
            found.append((path, label, len(in_name) + len(in_body), off, where))
    return sorted(found)


# Probe 3's controls come in two halves, because its incident class was a DERIVATION
# omission, not a matching failure: the first half pins what the derivation returns for
# fixture inputs, the second pins the matcher. Every home path below is assembled, never
# written as a literal, for the reason given above PATH_CONTROLS.
_EX = _U + "/exampleacct/Cloud-Store99/@Lab/@work/MyVault"
DERIVATION_CONTROLS = (
    ("path components", lambda: path_components(_EX),
     ["exampleacct", "Cloud-Store99", "@Lab", "@work", "MyVault"]),
    ("path components, no home root", lambda: path_components("/srv/data/@Lab/MyVault"),
     ["srv", "data", "@Lab", "MyVault"]),
    ("name tokens", lambda: name_tokens("Ada (Byron) Lovelace"), ["Ada", "Byron", "Lovelace"]),
    ("email local tokens", lambda: name_tokens("12345678+SomeHandle"), ["12345678", "SomeHandle"]),
    ("origin owners", lambda: origin_owners(["https://example.com/SomeHandle/a-repo.git",
                                             "git@example.com:Other-Handle/b.git"]),
     ["SomeHandle", "Other-Handle"]),
)
# (needles, buffer, expected match count) — the matcher itself.
STRING_CONTROLS = (
    (["Lovelace"], b"see Lovelace and lovelace", 2),      # fires, case-insensitively
    (["Lovelace"], b"see Babbage", 0),                    # stays quiet on an absent needle
    (["a.c"], b"abc and a.c", 1),                         # a needle is a literal, not a regex
    (["Ada", "Ada-Lovelace"], b"Ada-Lovelace", 1),        # longest first: one hit, the long one
)


def self_controls():
    """Prove all three probes still fire and still stay quiet. A failure is a broken premise."""
    path_ok = 0
    for buf, text, should_match in PATH_CONTROLS:
        if bool(list(home_hits(buf, text))) == should_match:
            path_ok += 1
        else:
            raise Premise("machine-path control failed on %r (text=%s, expected match=%s)"
                          % (buf[:60], text, should_match))
    class_ok = 0
    for buf, should_be_text in CLASS_CONTROLS:
        if is_text(buf) == should_be_text:
            class_ok += 1
        else:
            raise Premise("text-class control failed on %r (expected text=%s)"
                          % (buf[:20], should_be_text))
    string_ok = 0
    for label, fn, expected in DERIVATION_CONTROLS:
        got = fn()
        if got == expected:
            string_ok += 1
        else:
            raise Premise("derivation control `%s` returned %r, expected %r" % (label, got, expected))
    for needles, buf, expected in STRING_CONTROLS:
        got = sum(1 for _ in needle_pattern(needles).finditer(buf))
        if got == expected:
            string_ok += 1
        else:
            raise Premise("string-match control failed on %r (%d matches, expected %d)"
                          % (buf[:40], got, expected))
    # Both branches of the corpus scan, on a synthetic corpus: the needle in a file NAME, and
    # the needle in a file's BYTES behind a NUL so the entry is binary. A scan that lost
    # either branch would still match the real payload's guaranteed path hit and look fine.
    probe = scan_needles([("dir/name-" + CONTROL_NEEDLE.decode(), "100644", b"nothing here"),
                          ("dir/blob.bin", "100644", b"\x00\x00" + CONTROL_NEEDLE)],
                         needle_pattern([CONTROL_NEEDLE.decode()]))
    branches = {p: row for (_n, p), row in probe.items()}
    name_row = branches.get("dir/name-" + CONTROL_NEEDLE.decode())
    blob_row = branches.get("dir/blob.bin")
    if not (name_row and name_row[3]) or not (blob_row and blob_row[4]):
        raise Premise("corpus-branch control failed: the scan matched %s, so one of its two "
                      "branches (file name, file bytes) did not run" % sorted(branches))
    string_ok += 2
    return path_ok, class_ok, string_ok


# Probe 4's controls run on every invocation, store or no store, so a run that found no store
# still proves the probe could have fired. Every value below is synthetic and public.
CRED_FIXTURE = (b"\xef\xbb\xbf# a comment line\n"
                b"\n"
                b"export EXAMPLE_ONE=\"quoted value-111\"\r\n"
                b"EXAMPLE_TWO=plain-value-222 # an inline note\n"
                b"EXAMPLE_THREE='single value-333' # a note after the quote\n"
                b"EXAMPLE_FOUR=\n"
                b"EXAMPLE_FIVE=abc\n"
                b"EXAMPLE_SIX=\"esc \\\"q\\\" value-666\"\n"
                b"EXAMPLE_SEVEN=plain-value-222\n"
                b"EXAMPLE_EIGHT=\"a\\$b\\nc\\\\d-888\"\n"
                b"EXAMPLE_NINE=un\\quoted value-999\n")
CRED_EXPECTED = [("EXAMPLE_ONE", (b"quoted value-111",)), ("EXAMPLE_TWO", (b"plain-value-222",)),
                 ("EXAMPLE_THREE", (b"single value-333",)), ("EXAMPLE_FOUR", (b"",)),
                 ("EXAMPLE_FIVE", (b"abc",)),
                 ("EXAMPLE_SIX", (b'esc "q" value-666', b'esc \\"q\\" value-666')),
                 ("EXAMPLE_SEVEN", (b"plain-value-222",)),
                 # one value four ways: the guard's reading, as written, a shell's, a dotenv's
                 ("EXAMPLE_EIGHT", (b"a\\$b\\nc\\d-888", b"a\\$b\\nc\\\\d-888",
                                    b"a$b\\nc\\d-888", b"a\\$b\nc\\d-888")),
                 # unquoted: as written, and as a shell reads it (the backslash gone, the blank
                 # kept: a cut reading would be a commoner string)
                 ("EXAMPLE_NINE", (b"un\\quoted value-999", b"unquoted value-999"))]
CRED_KEPT = sorted({r for _k, rs in CRED_EXPECTED for r in rs} - {b"", b"abc"})  # the floor
                                                         # drops the empty value and the 3-byte one
CRED_MALFORMED = b"OK_KEY=fine-value-1\nthis line has no pair at all\n"
CRED_CONTROL_COUNT = 5      # parse (every reading), malformed line, floor, scan (both branches
                            # + the quiet case-changed copy), withhold (escaped copies too) —
                            # one per check below


def credential_controls():
    """Prove probe 4 parses, floors, fires on both branches, stays quiet, and withholds."""
    if parse_credentials(CRED_FIXTURE) != CRED_EXPECTED:
        raise Premise("credential-parse control failed: the synthetic store parsed to %d pair(s) "
                      "that differ from the %d expected" % (len(parse_credentials(CRED_FIXTURE)),
                                                            len(CRED_EXPECTED)))
    try:
        parse_credentials(CRED_MALFORMED)
        refusal = None
    except Premise as err:
        refusal = str(err)
    if refusal is None:
        raise Premise("credential-parse control failed: a line with no `=` was accepted")
    if "line 2" not in refusal or "no pair" in refusal:
        raise Premise("credential-parse control failed: a malformed line was not named by its "
                      "number alone")
    values, short, empty = credential_values(CRED_EXPECTED)
    if sorted(values) != CRED_KEPT or (short, empty) != (1, 1) \
            or values[b"plain-value-222"] != ["EXAMPLE_TWO", "EXAMPLE_SEVEN"]:
        raise Premise("credential-floor control failed: %d value(s), %d short, %d empty"
                      % (len(values), short, empty))
    # Both branches, and the quiet case: a value in a file NAME, a value behind a NUL in a
    # file's BYTES, and the same value case-changed, which is not a match (literal bytes).
    rows = scan_credentials([("dir/notes-plain-value-222.txt", "100644", b"nothing here"),
                             ("dir/blob.bin", "100644", b"\x00\x00quoted value-111"),
                             ("dir/other.md", "100644", b"PLAIN-VALUE-222 in another case")],
                            values)
    got = [(p, k, w) for p, k, _c, _o, w in rows]
    if got != [("dir/blob.bin", "EXAMPLE_ONE", "content"),
               ("dir/notes-plain-value-222.txt", "EXAMPLE_TWO/EXAMPLE_SEVEN", "name")]:
        raise Premise("credential-scan control failed: the synthetic corpus gave %d row(s), "
                      "not the 2 expected (one per branch, none on the case-changed copy)" % len(got))
    # The output path: a line carrying a value leaves with the KEY and without the value — raw,
    # or escaped as a message quotes it: a backslash reading doubled (an OSError's text, git's
    # quoting) and the dotenv reading repr'd (its newline written \n).
    probe = Withheld()
    probe.arm(values)
    line = probe.scrub(b"FINDING credential    dir/notes-plain-value-222.txt  quoted value-111 "
                       b"'a\\\\$b\\\\nc\\\\d-888' 'a\\\\$b\\nc\\\\d-888'")
    if any(v in line for v in values) or b"\\" in line or b"EXAMPLE_ONE" not in line \
            or b"EXAMPLE_TWO/EXAMPLE_SEVEN" not in line or line.count(b"EXAMPLE_EIGHT") != 2:
        raise Premise("credential-withhold control failed: a scrubbed line still carries a "
                      "value, raw or escaped, or lost its KEY")
    return CRED_CONTROL_COUNT


def check_staged(root):
    """The index must already hold the payload, or the gate scans the LAST publish.

    Run before `git add -A`, the guard would read a stale index and report clean on a tree
    nobody staged. Both halves are needed: `--others` catches a payload never added, `diff`
    catches a tracked file edited after the overlay.
    """
    others = run_git(root, ["ls-files", "--others", "--exclude-standard", "-z"])
    if others.strip(b"\0"):
        n = len([x for x in others.split(b"\0") if x])
        raise Premise("%d file(s) in %s are untracked — stage the payload first "
                      "(`git add -A`), or the gate reads the previous publish" % (n, root))
    try:
        # Submodules are excluded: a gitlink's worktree state is not part of the bytes this
        # payload ships, and the scan reports the entry as unscannable either way.
        p = subprocess.run(["git", "-C", root, "diff", "--quiet", "--ignore-submodules=all"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as err:
        raise Premise("cannot run git diff (%s)" % os_reason(err))
    if p.returncode == 1:
        raise Premise("tracked files in %s differ from the index — stage them first "
                      "(`git add -A`), or the gate scans bytes that will not ship" % root)
    if p.returncode != 0:
        raise Premise("`git diff --quiet` exited %d in %s" % (p.returncode, root))


def check_payload_shape(paths):
    """Keyed on the payload's observable shape, so an empty or partial tree cannot pass."""
    if not paths:
        raise Premise("payload holds no files — nothing was scanned")
    if "CLAUDE.md" not in paths:
        raise Premise("no CLAUDE.md at the payload root — not a framework payload")
    if not any(p.startswith(".claude/skills/") for p in paths):
        raise Premise("no file under .claude/skills/ — not a framework payload")
    # The vault itself also has CLAUDE.md and .claude/skills/, so the two checks above pass
    # on it. A payload never carries the owner's preference layer (SPEC.md, STRIP list), so
    # its presence says this tree is a vault, not something about to be published.
    if "CUSTOMISATION.md" in paths:
        raise Premise("CUSTOMISATION.md is present — this is a vault, not a publish payload")


def scan(entries, draft=False):
    machine, nontext, unreadable = [], [], []
    for path, mode, blob in entries:
        if blob is None:
            unreadable.append(path)
            continue
        text = is_text(blob)
        for m in home_hits(blob, text, draft=draft):
            machine.append((path, m.start(), m.group().decode("utf-8", "replace")))
        if path.startswith(MEDIA_ROOT):
            continue                      # the declared media directory: images belong here
        if not text:
            nontext.append((path, len(blob), first_nul(blob)))
    return machine, nontext, unreadable


def needle_summary(needles, dropped):
    """The needle count and classes for a summary line: counts and class names, never a needle."""
    by_source = {}
    for _text, sources in needles.values():
        for s in sources:
            by_source[s] = by_source.get(s, 0) + 1
    return ("%d needle(s) from %d class(es) [%s]%s"
            % (len(needles), len(by_source),
               ", ".join("%s %d" % (k, v) for k, v in sorted(by_source.items())),
               (", %d below the %d-byte floor" % (len(dropped), MIN_NEEDLE)) if dropped else ""))


def credential_summary(note, pairs, values, short, empty, label):
    """Probe 4's clause of the summary line, so the recap, which quotes that line, carries it too.

    Counts and the store's vault-relative name only (an override by its file name), never a value.
    """
    if note:
        return "; credentials: %s — 0 values checked" % note
    # A value counts once, by the guard's own reading; the other readings of a value with a
    # backslash (value_readings) are counted after it, so the line still adds up when
    # readers disagree.
    firsts = {rs[0] for _k, rs in pairs if any(r in values for r in rs)}
    others = len(set(values) - firsts)
    return ("; credentials: %d value(s) checked from %s (%d key(s))%s%s%s"
            % (len(firsts), label, len(pairs),
               (", %d below the %d-byte floor" % (short, MIN_CREDENTIAL)) if short else "",
               (", %d empty" % empty) if empty else "",
               (", with %d other reading(s) of a value with a backslash" % others)
               if others else ""))


def emit_findings(machine, nontext, unreadable, unallowed, expired, leaked, release=None):
    """One FINDING line per hit, each probe capped at MAX_SHOWN, through the one output path."""
    for path, off, hit in machine[:MAX_SHOWN]:
        OUT.emit("FINDING machine-path  %s  byte %d: %s" % (path, off, hit))
    if len(machine) > MAX_SHOWN:
        OUT.emit("FINDING machine-path  … and %d more" % (len(machine) - MAX_SHOWN))
    for path, size, nul in nontext[:MAX_SHOWN]:
        OUT.emit("FINDING non-text      %s  %d bytes, first NUL at byte %d" % (path, size, nul))
    if len(nontext) > MAX_SHOWN:
        OUT.emit("FINDING non-text      … and %d more" % (len(nontext) - MAX_SHOWN))
    for path in unreadable[:MAX_SHOWN]:
        OUT.emit("FINDING unscannable   %s  gitlink (submodule): no blob to read" % path)
    for path, off, sample, count, where, sources, why in unallowed[:MAX_SHOWN]:
        OUT.emit("FINDING personal-str  %s  %d hit(s) in %s, first at byte %d: %s "
                 "[from %s] — %s" % (path, count, where, off, sample, sources, why))
    if len(unallowed) > MAX_SHOWN:
        OUT.emit("FINDING personal-str  … and %d more" % (len(unallowed) - MAX_SHOWN))
    for key, ver in expired:
        OUT.emit("FINDING allowlist-exp %s  provisional entry `%s` expires at %s and this "
                 "publish is %s — remove it or re-adjudicate" % (ALLOWLIST_NAME, key, ver, release))
    # The KEY and the file, never the value; a value in the file NAME is withheld by OUT.
    for path, keys, count, off, where in leaked[:MAX_SHOWN]:
        OUT.emit("FINDING credential    %s  %d hit(s) in %s, first at byte %d: the value of "
                 "%s [from the credential store] — remove it from the payload; no allowlist "
                 "applies" % (path, count, where, off, keys))
    if len(leaked) > MAX_SHOWN:
        OUT.emit("FINDING credential    … and %d more" % (len(leaked) - MAX_SHOWN))


# ── draft mode ───────────────────────────────────────────────────────────────
# A suggestion draft is one file a person is about to make public. The probes are the payload
# gate's own, run on that file; only the frame differs, because a draft has no index, no
# allowlist and no payload shape to assert. The path probe alone reads wider (see the regexes).

# The draft rule's self-controls, shaped as PATH_CONTROLS and assembled for the same reason.
_UL = _U.lower()
DRAFT_PATH_CONTROLS = (
    (('OUT = "%s/example/vault"' % _U).encode(), True, True),      # the payload's spellings fire
    (('OUT = "%s/example/vault"' % _H).encode(), True, True),
    (b'OUT = "D:' + b'\\Users\\example\\vault"', True, True),
    (b'OUT = "d:' + b'\\users\\example\\vault"', True, True),      # a root in any case
    (('OUT = "%s/example/vault"' % _UL).encode(), True, True),
    (('OUT = "d:%s/example/vault"' % _UL).encode(), True, True),   # a forward slash on a drive
    (b'"D:' + b'\\\\Users\\\\example\\\\vault"', True, True),      # a doubled backslash
    (b'"D:' + b'\\\\\\\\Users\\\\\\\\example"', True, True),       # the same escaped once more
    (('"\\%s\\/example\\/vault"' % _U).encode(), True, True),      # an escaped slash
    (('OUT = "%s/éxample/vault"' % _U).encode("utf-8"), True, True),  # an account above ASCII
    (('file://%s/%%C3%%A9xample/vault' % _U).encode(), True, True),  # the same in a file URL
    (('OUT = "/c%s/example/vault"' % _U).encode(), True, True),    # a drive under Git Bash,
    (('OUT = "/mnt/c%s/example/vault"' % _U).encode(), True, True),        # under WSL
    (('OUT = "/cygdrive/c%s/example/vault"' % _U).encode(), True, True),   # and under Cygwin
    (('\x6f%s/example/vault/mod.py' % _U).encode("latin-1"), False, True),  # the binary rule fires
    (('\x6f%s/example/vault/mod.py' % _U).encode("latin-1"), True, False),  # the text rule does not
    (('cat "$W%s/.llm-wiki/last-run.txt"' % _H).encode(), True, False),   # a fragment does not
    (b'the agent home is ~/.llm-wiki/ and $HOME/notes', True, False),     # tilde/var forms do not
    (('see https://example.com%s/guide' % _UL).encode(), True, False),    # a URL segment does not
    (('see docs%s/guide' % _UL).encode(), True, False),            # a relative path does not
    (('%s/$USER/notes and %s/<you>/notes' % (_U, _H)).encode(), True, False),  # placeholders do not
    (('%s/%%s/notes' % _U).encode(), True, False),                 # a `%` that is no escape does not
    (('%s/…/notes' % _U).encode("utf-8"), True, False),       # an account elided does not
    (('%s/ and %s/' % (_U, _H)).encode(), True, False),            # a root with no account does not
)


def draft_path_controls():
    """Prove the draft's path rule on fixed buffers, as self_controls proves the payload's."""
    path_ok = 0
    for buf, text, should_match in DRAFT_PATH_CONTROLS:
        if bool(list(home_hits(buf, text, draft=True))) == should_match:
            path_ok += 1
        else:
            raise Premise("draft path control failed on %r (text=%s, expected match=%s)"
                          % (buf[:60], text, should_match))
    return path_ok


def read_draft(path):
    """The one entry a draft gives the probes: (its file name, a mode, its bytes).

    Only the file's own name is kept: the folders above it never reach an issue, and scanning them
    would hit on the vault's path every time. A draft that is not a readable file with bytes in it
    is a broken premise, since "clean" would then be a claim about nothing.
    """
    name = os.path.basename(path.rstrip("/\\")) or path
    if not os.path.isfile(path):
        raise Premise("the draft %s is not a file" % name)
    try:
        with open(path, "rb") as fh:
            blob = fh.read()
    except OSError as err:
        raise Premise("cannot read the draft %s (%s)" % (name, os_reason(err)))
    if not blob:
        raise Premise("the draft %s is empty — nothing was scanned" % name)
    return (name, "100644", blob)


def draft_needles(vault):
    """derive_needles for a draft: the vault's strings, less the shipped default agent name.

    The default identifies nobody, and a suggestion about the framework may well say it. Only its
    agent-name source goes: a string that also comes from another source stays a needle, and so
    does a user's own agent name, which can identify them. Returns the needles, the strings under
    the floor, the extra lines and a clause saying what happened to the agent name.
    """
    needles, dropped, extra = derive_needles(vault, [vault])
    default = seeded_agent_name()
    if default is None:
        return needles, dropped, extra, "the seed's agent name could not be read, so none is dropped"
    key = default.lower()
    text, sources = needles.get(key, ("", frozenset()))
    if "agent-name" in sources:
        if len(sources) == 1:
            del needles[key]
        else:
            needles[key] = (text, sources - {"agent-name"})
    return needles, dropped, extra, "the shipped default agent name is no needle as such"


def draft_controls(entry, pattern, needle, values):
    """Plant each class at the end of a copy of the draft: each scan's count must rise.

    The self-controls prove the probes on fixed buffers; this proves them on this run's own bytes,
    with this run's own pattern and values, to the file's last byte. The planted value stays in
    memory and no message carries it.
    """
    name, mode, blob = entry
    probes = [("machine path", (_U + "/control/path").encode(),
               lambda e: len(scan(e, draft=True)[0])),
              ("personal string", needle.encode("utf-8"),
               lambda e: sum(row[0] for row in scan_needles(e, pattern).values()))]
    if values:
        probes.append(("credential value", next(iter(values)),
                       lambda e: sum(row[2] for row in scan_credentials(e, values))))
    for label, plant, count in probes:
        if count([(name, mode, blob + b"\n" + plant + b"\n")]) <= count([entry]):
            raise Premise("draft control failed: a %s planted at the end of a copy of the draft "
                          "was not caught, so a clean result would mean nothing" % label)
    return len(probes)


def check_draft(draft, vault, cred_values, cred_line):
    """--draft: the payload probes on one file, nothing adjudicated. Exit codes as main's."""
    entry = read_draft(draft)
    needles, dropped, extra, agent_clause = draft_needles(vault)
    if not needles:
        raise Premise("no owner string could be derived from the vault, so a clean result would "
                      "be a claim about an empty set")
    pattern = needle_pattern([n[0] for n in needles.values()])
    path_ok, class_ok, string_ok = self_controls()
    cred_ok = credential_controls()
    draft_path_ok = draft_path_controls()
    draft_ok = draft_controls(entry, pattern, next(iter(needles.values()))[0], cred_values)

    machine, nontext, unreadable = scan([entry], draft=True)
    unallowed, _used, _allowed = adjudicate(scan_needles([entry], pattern), needles, [])
    unallowed = [row[:6] + ("a person reads this hit",) for row in unallowed]
    leaked = scan_credentials([entry], cred_values)

    name, _mode, blob = entry
    strings_line = ("personal-strings: %s; %s; no allowlist in draft mode; extra strings: %s%s"
                    % (needle_summary(needles, dropped), agent_clause,
                       "none" if extra is None else "%d line(s)" % len(extra), cred_line))
    if machine or nontext or unallowed or leaked:
        emit_findings(machine, nontext, unreadable, unallowed, [], leaked)
        OUT.emit("draft FAILED: %d machine path(s), %d non-text file(s), %d personal string(s), "
                 "%d credential value(s) — scanned %s (%d bytes). Nothing is filed: a person reads "
                 "each hit. A word from a folder name may be benign; a credential value is removed. "
                 "Run this again after any edit."
                 % (len(machine), len(nontext), len(unallowed),
                    len({k for _p, k, _c, _o, _w in leaked}), name, len(blob)))
        OUT.emit(strings_line)
        return 1
    OUT.emit("check: clean — scanned draft %s (%d bytes); 0 machine paths, 0 non-text files, "
             "0 personal strings, 0 credential values (control: %d/%d path probes, %d/%d class "
             "probes, %d/%d string probes, %d/%d credential probes, %d/%d draft path probes, "
             "%d/%d draft probes)"
             % (name, len(blob), path_ok, len(PATH_CONTROLS), class_ok, len(CLASS_CONTROLS),
                string_ok, len(DERIVATION_CONTROLS) + len(STRING_CONTROLS) + 2,
                cred_ok, CRED_CONTROL_COUNT, draft_path_ok, len(DRAFT_PATH_CONTROLS),
                draft_ok, draft_ok))
    OUT.emit(strings_line)
    return 0


def find_vault(override):
    """The vault whose owner strings probe 3 derives: three directories up, or --vault.

    Probes 1 and 2 need only a payload; probe 3 needs the owner's preference layer and path.
    A vault that cannot be found is a broken premise rather than a skipped probe, because a
    skip would print `check: clean` over a scan that never searched for a personal string.
    """
    cand = override or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                    "..", "..", ".."))
    missing = [f for f in ("CLAUDE.md", "CUSTOMISATION.md")
               if not os.path.exists(os.path.join(cand, f))]
    if missing:
        raise Premise("cannot derive the owner's strings: %s has no %s. Pass --vault <path> "
                      "to point at the vault this payload was built from."
                      % (cand, " or ".join(missing)))
    return cand


def parse_args(argv):
    """The arguments, plus the first argument error as a Premise, or None.

    The error is RETURNED, never raised: its message can echo an argument, and an argument can
    carry a value, so main raises it only once the store is read and the output path armed. The
    rest of the line is still parsed, so a --credentials after a bad argument is honoured.
    """
    root = vault = release = allowlist = credentials = draft = error = None
    show_needles = False
    rest = argv[1:]
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--print-needles":
            show_needles = True
        elif a in ("--vault", "--release", "--allowlist", "--credentials", "--draft"):
            if i + 1 >= len(rest):
                error = error or Premise("%s needs a value" % a)
            else:
                i += 1
                if a == "--vault":
                    vault = rest[i]
                elif a == "--release":
                    release = rest[i]
                elif a == "--credentials":
                    credentials = rest[i]
                elif a == "--draft":
                    draft = rest[i]
                else:
                    allowlist = rest[i]
        elif a.startswith("--"):
            error = error or Premise("unknown option %s" % a)
        elif root is None:
            root = a
        else:
            error = error or Premise("more than one directory given (%s and %s)" % (root, a))
        i += 1
    if error is None and draft is not None:
        beside = [flag for flag, given in (("a directory", root), ("--allowlist", allowlist),
                                           ("--release", release), ("--print-needles", show_needles))
                  if given]
        if beside:
            error = Premise("--draft reads one file and adjudicates nothing, so it takes no %s"
                            % " and no ".join(beside))
    if error is None and root is None and draft is None:
        error = Premise("usage: publish_guard.py [--vault <vault>] [--allowlist <file>] "
                        "[--credentials <file>] [--release <ver>] [--print-needles] "
                        "<repo-clone-or-build-dir>, or: publish_guard.py [--vault <vault>] "
                        "[--credentials <file>] --draft <file>")
    if error is None and release is not None and parse_version(release) is None:
        error = Premise("--release %s does not parse as a version" % release)
    return root, vault, release, allowlist, show_needles, credentials, draft, error


def main(argv):
    root, vault_arg, release, allow_arg, show_needles, cred_arg, draft, arg_error = parse_args(argv)
    # Probe 4 reads its store FIRST and arms the output path before ANY line can be printed:
    # an argument error, a vault that is not one and a root that is not a directory can each
    # echo a path or an argument that carries a value, so each is raised only after the arming.
    # Only a run that cannot reach its store at all (no --credentials and no vault to find it
    # in) prints unarmed — and that run has read no value, so it holds none to withhold. A
    # store that cannot be checked, read or parsed is reported by its label and the OS reason
    # or a line number, never its content.
    try:
        vault, vault_error = find_vault(vault_arg), None
    except Premise as err:
        vault, vault_error = None, err
    if cred_arg is not None or vault is not None:
        cred_path = cred_arg or os.path.join(vault, CREDENTIALS_REL)
        cred_label = ("NON-DEFAULT (%s)" % os.path.basename(cred_path)) if cred_arg \
            else CREDENTIALS_REL
        cred_pairs, cred_note = read_credentials(cred_path, cred_label)
        cred_values, cred_short, cred_empty = credential_values(cred_pairs or [])
        OUT.arm(cred_values)
    for err in (arg_error, vault_error):
        if err is not None:
            raise err
    cred_line = credential_summary(cred_note, cred_pairs, cred_values, cred_short, cred_empty,
                                   cred_label)
    if draft is not None:
        return check_draft(draft, vault, cred_values, cred_line)
    if not os.path.isdir(root):
        raise Premise("%s is not a directory" % root)
    root = os.path.abspath(root)
    # --allowlist exists so the suite can exercise a malformed adjudication file without
    # mutating the shipped one; an override is named on the gate's own output line, because a
    # publish run that quietly used a different adjudication set would be invisible in the recap.
    allow_path = allow_arg or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           ALLOWLIST_NAME)
    entries_allow = read_allowlist(allow_path)
    needles, dropped, extra = derive_needles(vault, [vault, root])
    path_ok, class_ok, string_ok = self_controls()
    cred_ok = credential_controls()
    if show_needles:
        for key in sorted(needles):
            OUT.emit("needle  %-28s  %s" % (needles[key][0], ",".join(sorted(needles[key][1]))))

    indexed = has_index(root)
    if indexed:
        check_staged(root)
    entries = read_index(root) if indexed else read_tree(root)
    check_payload_shape({p for p, _m, _b in entries})
    machine, nontext, unreadable = scan(entries)

    control = sum(row[0] for row in scan_needles(entries, needle_pattern([CONTROL_NEEDLE.decode()])).values())
    if control == 0:
        raise Premise("the corpus control matched nothing across %d files — the scan searched "
                      "nothing, so a clean result would be a claim about an empty set" % len(entries))
    unallowed, used, allowed_total = adjudicate(
        scan_needles(entries, needle_pattern([n[0] for n in needles.values()])), needles, entries_allow)
    # No allowlist reaches probe 4: a credential value in the payload is removed, never adjudicated.
    leaked = scan_credentials(entries, cred_values)

    expired = []
    for i, entry in enumerate(entries_allow):
        if entry["provisional"] and release is not None \
                and version_at_least(parse_version(release), entry["expiry"]):
            expired.append((entry["key"], entry["expiry_text"]))

    scanned = len(entries)
    total = sum(len(b) for _p, _m, b in entries if b is not None)
    source = ("the index of %s" % root) if indexed \
             else ("the on-disk tree at %s (no git index)" % root)
    # Public-safe by construction: counts and class names only, never a needle and never the
    # vault path — this line is quoted in the publish recap.
    strings_line = ("personal-strings: %s; %d allowlisted "
                    "hit(s), %d entr(ies) of %d used%s; extra strings: %s"
                    % (needle_summary(needles, dropped),
                       allowed_total, sum(1 for v in used.values() if v), len(entries_allow),
                       "" if all(used.values()) else
                       " (inert: %s)" % ", ".join(entries_allow[i]["key"]
                                                  for i, v in sorted(used.items()) if not v),
                       "none" if extra is None else "%d line(s)" % len(extra)))
    strings_line += cred_line
    if allow_arg:
        strings_line += "; allowlist: NON-DEFAULT (%s)" % os.path.basename(allow_path)
    pending = ["%s expires at %s" % (e["key"], e["expiry_text"])
               for e in entries_allow if e["provisional"]]
    if pending:
        strings_line += "; provisional: " + "; ".join(pending)

    if machine or nontext or unreadable or unallowed or expired or leaked:
        emit_findings(machine, nontext, unreadable, unallowed, expired, leaked, release)
        OUT.emit("gate FAILED: %d machine path(s), %d non-text file(s) outside %s, %d unscannable, "
                 "%d unallowlisted personal string(s), %d expired allowlist entr(ies), %d "
                 "credential value(s) in %d file(s) — scanned %d files (%d bytes) from %s. "
                 "The publish halts."
                 % (len(machine), len(nontext), MEDIA_ROOT, len(unreadable), len(unallowed),
                    len(expired), len({k for _p, k, _c, _o, _w in leaked}),
                    len({p for p, _k, _c, _o, _w in leaked}), scanned, total, source))
        OUT.emit(strings_line)
        return 1

    OUT.emit("check: clean — scanned %d files (%d bytes) from %s; 0 machine paths, "
             "0 non-text files outside %s, 0 unallowlisted personal strings, 0 credential values "
             "(control: %d/%d path probes, %d/%d class probes, %d/%d string probes, "
             "%d/%d credential probes, corpus control %d hits)"
             % (scanned, total, source, MEDIA_ROOT, path_ok, len(PATH_CONTROLS),
                class_ok, len(CLASS_CONTROLS), string_ok,
                len(DERIVATION_CONTROLS) + len(STRING_CONTROLS) + 2,
                cred_ok, CRED_CONTROL_COUNT, control))
    OUT.emit(strings_line)
    return 0


def run(argv):
    """main() behind the one output path. A premise prints its PROBE FAILED line through OUT;
    a crash prints its traceback through OUT too, and exits 2 — a broken premise, never the
    findings code 1 an uncaught exception would otherwise share, and never a pass. Every OSError
    in the crash's chain loses its file names first (drop_os_names), so its line prints the
    reason alone and no escaped copy of a path reaches the scrub."""
    try:
        return main(argv)
    except Premise as err:
        OUT.emit("PROBE FAILED: %s" % err)
        return 2
    except Exception as err:
        drop_os_names(err)
        for ln in traceback.format_exc().rstrip("\n").split("\n"):
            OUT.emit(ln)
        OUT.emit("PROBE FAILED: the guard crashed (%s) — a crash is a broken premise, never a "
                 "pass" % type(err).__name__)
        return 2


if __name__ == "__main__":
    sys.exit(run(sys.argv))
