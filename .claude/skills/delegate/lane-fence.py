#!/usr/bin/env python3
"""lane-fence.py — the lane-side PreToolUse(Bash) fence for a headless thin lane.

`--restricted` confines the FILE tools (Read, Grep, Glob, Write, Edit) to the working
directory plus the `--add-dir` grants, and removes Bash unless `--tools` names it. It does
not fence the shell channel: a lane holding Bash can `cat` anything the user can read. This
hook is that missing fence. It is installed only in the lane home's own settings file, which
the wrapper passes with `--settings`, and must never be installed into the vault's settings —
it denies far more than a head session should ever have denied.

It keys on PATHS taken from the spawn environment, never on an agent key: an in-session
PreToolUse event carries `agent_type`, a headless one does not, so the
vault's own `deny-lane-shell-writes.sh` cannot serve a headless lane. The two variables are
written by the wrapper at spawn:

    LLM_WIKI_LANE_GRANTS   os.pathsep-joined absolute directories the lane may READ
    LLM_WIKI_LANE_WRITES   os.pathsep-joined absolute directories the lane may WRITE (may be empty)
    LLM_WIKI_LANE_NETWORK  comma- or whitespace-separated hosts the lane may reach (absent/empty =
                           no network; NOT os.pathsep-joined, which would shred an IPv6 literal);
                           the head role reads the grant file's `network` key instead (D34)

Implicitly granted for reads and writes, whatever the variables say: /tmp (and its resolved
form) and /dev — not $TMPDIR. Lane scratch is sanctioned. Implicitly
granted for reads only: the lane home (the working directory) and executables that already
exist under the system bin directories, so a lane may invoke /usr/bin/grep without the fence
reading that path as data access.

What it denies, in this order, so the reason names the real cause:
  1. an invocation of `claude` (a lane may not spawn lanes, nor escape its own fence);
  N. a network command (`curl`, `wget`, `ssh`, `scp`, `sftp`, `nc`, `telnet`, `ftp`, or an
     interpreter payload importing `urllib`, `requests`, `http.client`, `socket` or `aiohttp`)
     unless the `network` grant names the host it addresses (the first `https?://host` or
     `user@host` token); no `network` grant is no network, a network command with no host token
     under a grant is unresolvable and denied (register 2026-09-07, memory-hunter);
  2. a write channel — redirection, tee, `sed -i` / `perl -i`, or a mutating command word
     (mv, cp, rm, mkdir, rmdir, touch, ln, install, truncate, dd, chmod, chown) — whose
     target is outside the write set, or ANY such channel when the write set is empty
     (temporary roots and /dev excepted). A mutator is judged on ITS OWN segment and on its
     target arguments alone (`mutator_targets`): a compound line's other commands are not its
     targets, and for cp/mv/install/ln the sources are reads, tested by checks 3 and 4. That
     segment and its words are read QUOTE-AWARE (`shell_segments`, N10), so a separator inside a
     quoted argument starts no segment and a mutator word inside another command's quoted prose
     is prose; and an operand that names no file — a chmod mode, a chown or chgrp owner spec, a
     flag's value, a redirection target — is dropped by the SHAPE of the token, never by a list
     of known values, so `chmod 644 644` still reads its second operand as the file it writes;
  3. a relative path token that escapes the working directory (a `..` component);
  4. an absolute path token outside the read grants.

Before any of those four run, the HEREDOC BODIES are removed (`strip_heredocs`, design D33):
`<<` and `<<-`, quoted (`'EOF'`, `"EOF"`) and bare terminators, several heredocs opened on one
command line consumed in marker order, a line equal to the terminator (after `<<-` strips leading
tabs) ending that body there, and an unterminated body running to the end of the text — each as
the shell reads it, so what the fence calls data is what the shell calls data. The command line
carrying the `<<` STAYS: its own redirect targets and command words are checked as before, and a
`>` on that line still denies when its target is outside the write set. A `<<` inside quotes, and
anything after an unquoted `#`, opens no heredoc, so neither can hide a command from the checks.
Checks 3 and 4 — the read side — take their path tokens from `read_tokens`, which reads a quoted
string in this order (`quoted_kind`, D33 as amended by critic C2, N1): content holding a newline or
an OPERATOR character (`|`, `;`, `&`, `<`, `>`, `(`, `)`, a backtick, `^`, a backslash) is payload —
a pattern, a pipeline, a script; content starting with `/`, `~` or `$` is ONE path however many
spaces it holds, tested whole with any glob part cut (`"/x/*.md"` → `/x/`), so a spaced path is
checked rather than split into words that each pass; a `/`-led string in the slash-delimited
PATTERN shape carrying a metacharacter no path or glob has (`'/^## Open/'`, `'/x/{print $2}'`) or
in the address-range shape (`'/a/,/b/p'`) is payload, not a path (N9, `slash_pattern`); any other
whitespace-bearing content is prose and is payload; a bare word is a token like any other. A
`$`-led quoted string takes whatever is GLUED to it as part of the same token (`"$V"/wiki`), the
spelling `"$V/wiki"` and the bare `$V/wiki` both already having passed (N9c). Check 1 keeps the
whole (heredoc-stripped) text and its quoted content, so `python3 -c "... claude ..."` still
denies. Check 2 runs on the QUOTED-STRIPPED text (N9): a `>` inside quotes is not a redirection in
any shell, so scanning it as one would falsely deny a read-only command. A quoted
single-path target survives the strip as a target (`> "/x/y"`), so on the WRITE side (N3, measured
by C2) a redirection, `tee` or mutator target whose text carries `$` or a backtick is still denied
outright: the fence cannot expand it safely or prove that it stays within the write roots.

`--head` (or LLM_WIKI_FENCE_ROLE=head) is the HEAD role, used by .claude/hooks/head-fence.py
(design D34), which imports this module and calls `check()` rather than spawning it (N8): check 1
is off (a head spawns lanes) and a CLEARED command is answered with SILENCE — exit 0, no stdout —
never an explicit `allow`, which the harness reads as auto-approval and which, armed in an attended
session, would bypass every shell prompt the owner still wants (the same rule handsoff-gate.py's
docstring states). `git` gets no rule of its own in either role: it is not a mutator token, so
nothing denies it, and its paths are checked like any other command's. A deny is the same JSON deny
in both roles, and the grants and writes come from the same two variables.

Premise cases, each made to behave rather than to guess:
  - stdin is not JSON, or carries no `tool_input.command` for a Bash call → DENY
    (`lane-fence: hook input unreadable` / `no command in hook input`). Fail-closed: a fence
    that cannot see the command cannot clear it.
  - LLM_WIKI_LANE_GRANTS absent, empty, or all-whitespace → DENY every Bash command
    (`lane-fence: no grants in environment`). This is the case that fires when the hook is
    reached from a session the wrapper did not start, which is exactly when it should.
  - `tool_name` is not Bash → no output, exit 0 (the harness decides). The settings matcher
    already scopes the hook to Bash; this is the belt.
  - an empty or whitespace-only command → allowed with no output: it writes nothing and
    reads nothing.
  - LLM_WIKI_LANE_WRITES absent or empty → a read-only lane: every write channel outside the
    temporary roots denies. Absent is not "unfenced", it is "no writes".
The process exits 0 in every case; a non-zero exit from a PreToolUse hook is a harness error,
not a denial, so it is never used to express one.

A cleared command gets an explicit `allow` decision rather than silence IN THE LANE ROLE. Silence
leaves the command to the ordinary permission flow, and a lane spawned with `--permission-prompts
none` has every would-be prompt turned into a denial, so silence would fence the shell to nothing.
The explicit allow is therefore what makes a granted `cat` run, and it makes this hook the
sole arbiter of the lane's shell — which is why its deny rules are conservative. In the head role
the opposite holds and a cleared command is silent (see `--head` above): the head's session keeps
its ordinary prompts, and an allow there would switch them off.

Every reason begins `lane-fence:` so the wrapper can count fence denials in the lane
transcript apart from the harness's own tool denials.

Residual false-deny class, narrowed by D33 and N9 and stated in what it still is (a retry tax, not
a hole). On the READ side a quoted string is payload or path by its content, so `grep 'see
/etc/hosts' f` is allowed, and a `/`-led PATTERN is payload wherever it carries a regex
metacharacter or is an address range; a pattern made only of letters and slashes (`'/foo/'`,
`'/foo/p'`) carries neither and is therefore still read as a path, so it false-denies outside the
grants — write it with an anchor, a class or a range (`'/^foo/'`, `'/a/,/b/'`) and it is payload.
A quoted glob (`"/x/*.md"`) is a path token, and `* ? [ ]` are for that reason not pattern
metacharacters: reading them as pattern markers would clear `cat "/etc/*"`. What that costs is
the other way round and is accepted: a two-segment path whose file name carries a brace, a bar or
a plus (`"/etc/{a}"`) is read as a pattern and passes unchecked, a file name no vault holds. On
the READ side a LITERAL quoted directory glued to a name (`cat "/x"/y`) is still split into two
tokens, so the tail (`/y`) is tested as a path of its own and false-denies; N9c glues only a
`$`-led string, and the write side reads the same word whole (N10).
A relative mutator target is resolved against the directory a LEADING `cd` moved into, when that
directory is itself inside the write roots (`leading_cd_base`, register 2026-09-08): `cd <dir in W>
&& … ; rm -f x.orig` resolves against that directory instead of the hook's working directory.
The narrowing is bounded to exactly one `cd`, standing first, with a literal
absolute operand and no parentheses in the command, and the resolved path still faces the same write
test, so a target that climbs back out (`../x`) denies as before. NOT changed, and named as the
residue it is: with no such `cd`, a relative target is still measured against the hook's working
directory, so `cd /outside && rm rel` under a cwd inside W is a fail-OPEN this fix does not close.
Fail-closed residues that stay: a mutator whose
target is a variable (`chmod +x "$f"`, `cp a "$D/b"`) is denied, because the fence sees no literal
path to test — a lane writes the literal path; an interpreter's program argument (`sh -c '…'`,
`python3 -c '…'`) keeps its content for the read checks, so a path inside it is tested and an
outside one denies as before D33, while a program passed with no `-c`/`-e` flag (an awk or sed
script) is payload the fence cannot decide; `sh -c '...'` still hides its payload from the
command-word tests. A symlink whose own location (its parent chain resolved, its final component
left as it lies) sits INSIDE a grant is now granted even when its realpath leaves the roots (fix 4,
`within_leaf`), so a venv `bin/python` symlinked to the framework install reads as granted; a token
outside on both readings is denied as before, and a symlinked directory COMPONENT that points out
is still resolved and so still denies. Each of these
fails towards denial; a lane that hits one reports the gap and the head re-spawns it with the grant
(the re-spawn rule), which is the designed recovery. The one direction that is NOT fail-closed is
named, and it is a READ: a quoted target whose variable the fence cannot expand — `cat
"$HOME/Library/Application Support/x"`, `cat "$D/secret"` — is one path token that is not absolute,
so checks 3 and 4 have nothing to test and it passes. Unquoted it always passed too (`tokens_of`
splits on `$`), and the WRITE side of the same shape denies outright (N3), so what remains is a
lane reading through a variable it set itself; the grants, not this fence, are what bound that.
CLASS W COVERS SHELL WRITES. An interpreter's own write is a TRIPWIRE for the literal shape only,
never a complete fence. Check 2b reads the `-c`/`-e` program text and every heredoc
body handed to an interpreter for write-opening calls whose target is a STRING LITERAL — an
`open()` in a write mode (w/a/x), a `Path()` write_text/write_bytes or a `Path().open()` in a write
mode, an `os` replace/rename, or a `shutil` copy/copyfile/move — and checks that literal against the
write roots (the exact call patterns are the regexes below). What it does NOT catch is stated
plainly, because a run's write scope must not be read as enforcing it: a target that is a VARIABLE
or any computed expression; a mode passed by keyword (`mode='w'`) or a raw/format string; a deletion
(`os` remove, `shutil` rmtree) or a child process; a program read from stdin (`python3 - < f.py`) or
from a substitution; and a write composed inside program text at all. A lane or head that must not
write outside W is bound by the GRANTS and the write whitelist, not by this scan.

Check 2c, on a WRITE-LESS lane only, denies a script FILE run by an interpreter (`python3 -B x.py
raw/f.md`) the moment it carries a file argument, UNLESS the script ships under `.claude/skills/`
and honours LLM_WIKI_LANE_WRITES itself (the ingest sanitiser does, exit 5 outside the roots). A
`-m module` run is never a script run. Residue: a shipped skill script that merely NAMES the
variable without enforcing it also clears, and a script carrying no file argument is not policed.

The checker and the hook DIVERGE by design on one command (review F8, h7): `handsoff.py grants --grant
<new path>` names a path outside the current grants, so `check()` alone denies it; only
head-fence.py exempts it, before calling `check()`, and logs it as a `grant-change` event. A lane
never runs that command, so the divergence is the head's alone.
"""

import json
import os
import re
import sys

FENCE = "lane-fence:"

# Command words that mutate the filesystem. Keyed on the basename of a command word, so
# /bin/rm and rm are the same case and a token like /x/rm-notes is not.
MUTATORS = {"mv", "cp", "rm", "rmdir", "mkdir", "touch", "ln", "install",
            "truncate", "dd", "chmod", "chown", "chgrp", "shred", "unlink"}
# Prefix words that stand in front of the real command word.
PREFIXES = {"env", "nohup", "time", "sudo", "doas", "command", "builtin", "exec",
            "xargs", "nice", "ionice", "stdbuf", "then", "do", "else", "elif", "if", "while"}
SYSTEM_BIN = ("/bin/", "/sbin/", "/usr/bin/", "/usr/sbin/", "/usr/libexec/",
              "/usr/local/bin/", "/opt/homebrew/bin/", "/opt/local/bin/")


def decide(action, reason):
    """Print one PreToolUse decision and exit 0. `action` is 'allow' or 'deny'."""
    sys.stdout.write(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": action,
        "permissionDecisionReason": reason}}) + "\n")
    sys.exit(0)


def deny(reason):
    decide("deny", "%s %s" % (FENCE, reason))


def norm(path):
    """Absolute, symlink-resolved, trailing-slash-free — both sides of every comparison."""
    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def roots_from(varname):
    raw = os.environ.get(varname) or ""
    out = []
    for part in raw.split(os.pathsep):
        part = part.strip()
        if part:
            out.append(norm(part))
    return out


def hosts_from(varname):
    """The lane role's network grant, from LLM_WIKI_LANE_NETWORK: hosts separated by COMMAS or
    whitespace, empty or absent meaning no network. The head role reads the grant file's `network`
    key (a JSON list) instead.

    Not `os.pathsep`: on this platform that is a colon, which shreds an IPv6 literal — a grant of
    `2001:db8::1` became the four hosts `2001`, `db8`, `` and `1`, so the address could never be
    named and `curl https://[2001:db8::1]/x` denied under its own grant (review N3). No host carries
    a comma, so commas and whitespace separate without ambiguity."""
    raw = os.environ.get(varname) or ""
    return [host.strip() for host in re.split(r"[,\s]+", raw) if host.strip()]


def within(path, roots):
    path = norm(path)
    for root in roots:
        if path == root or path.startswith(root.rstrip(os.sep) + os.sep):
            return True
    return False


def temp_roots():
    """The sanctioned scratch roots: /dev, /tmp and whatever /tmp resolves to (on this
    platform /private/tmp). $TMPDIR is deliberately NOT among them: on macOS it points at a
    per-user directory under /var/folders that a lane has no standing reason to touch, and
    sanctioning it would silently widen the fence far past the two paths the design names."""
    out = ["/dev", os.path.abspath("/tmp"), norm("/tmp")]
    return sorted(set(r for r in out if r))


def strip_quoted(text):
    """Remove quoted string content before checking shell write channels."""
    return re.sub(r"'[^']*'", " ", re.sub(r'"[^"]*"', " ", text))


# A redirect or `tee` TARGET position: what stands immediately before a quoted string, with every
# earlier quoted content already removed, ends in a redirection operator or a `tee` word.
TARGET_POSITION = re.compile(r"(?:>>?|(?:^|[\s;|&(])tee(?:\s+-a)?)\s*$")


def strip_quoted_for_writes(text):
    """Quoted CONTENT removed BEFORE the write-channel scan (N9), with one exception: a quoted
    string standing in a redirect or `tee` target position whose content `quoted_kind` calls a
    path is kept, unquoted, so `> "/x/y"` is still a target the scan tests and N3 still sees a
    `$` or a backtick in it.

    Strip quoted prose before scanning write targets. Otherwise a quoted redirection symbol
    or placeholder can be misread as shell syntax, and removing a quoted target too late can
    leave unbalanced quotes. The target exception above keeps real destinations visible.
    Every real redirect stays visible: it is written outside quotes, and a quoted target survives
    by the exception above."""
    out, last = [], 0
    for match in re.finditer(r"'[^']*'|\"[^\"]*\"", text):
        out.append(text[last:match.start()])
        content = match.group(0)[1:-1]
        # A target carrying `$` or a backtick is kept whatever `quoted_kind` calls it, so N3 keeps
        # its own reason for `tee "`sub`"` rather than falling through to the bare-`tee` deny.
        keep = quoted_kind(content) == "path" or "$" in content or "`" in content
        if content and keep and TARGET_POSITION.search("".join(out)):
            out.append(" %s " % content)
        else:
            out.append(" ")
        last = match.end()
    out.append(text[last:])
    return "".join(out)


def unquote(text):
    """Remove quote CHARACTERS but keep their content, so a quoted path is still a path."""
    return text.replace('"', " ").replace("'", " ")


# The OPERATOR characters that make a quoted string payload whatever else it holds (D33 as
# amended by critic C2, N1). `^` and the backslash are here so a quoted regex (`'/^x/'`, `'\d+/x'`)
# is payload; `*` and `?` are NOT, so a quoted glob is a path with its glob part cut; `$` is NOT,
# so a quoted `"$HOME/x"` is one path token rather than a hole.
PAYLOAD_OPERATORS = "|;&<>()`^\\\n"
# A quoted string whose content starts with one of these is ONE path however many spaces it holds:
# `"/opt/x/Application Support/y"` is a single argument to the command, not prose.
PATH_STARTS = ("/", "~", "$")
GLOB_CHARS = "*?["
# N9: a slash-led quoted string that is a slash-delimited PATTERN, not a path — a sed address, an
# awk program, a grep expression. Two tests, both required, because `/etc/passwd` fits the shape:
#   SHAPE  one `/…/` part, or a comma-joined pair (`/a/,/b/`), followed by pattern flags and
#          actions only — never a second path separator, which is why a real multi-segment path
#          (`/x/y/z`) cannot match at all.
#   METACHARACTER  something no path and no glob carries. Between the delimiters that is
#          `^ $ { } | + ( ) \`; in the TRAILING part `$` does not count, so `"/etc/$f"` stays the
#          path token it is today and only an awk action (`{print $2}`) is read as a pattern.
# The glob characters `* ? [ ]` are deliberately absent from both sets: a quoted glob is a PATH
# whose glob part is cut (D33), and reading `*` as a pattern marker would clear `cat "/etc/*"`.
PATTERN_PART = r"(?:\\.|[^/\\])*"
PATTERN_TAIL = r"[A-Za-z0-9,;:{}!+=$._ \t-]*"
PATTERN_SHAPE = re.compile(r"/(%s)/(?:\s*,\s*/(%s)/)?(%s)"
                           % (PATTERN_PART, PATTERN_PART, PATTERN_TAIL))
PATTERN_META = "^${}|+()\\"
TAIL_META = "{}|+()"
# Interpreters whose program text arrives as a quoted argument behind -c / -e / -E. Their payload
# is a command line, not prose, so the read checks keep its content: `sh -c "cat /etc/shadow"`
# must deny exactly as the bare `cat` does. Without this the payload rule would open a read hole
# that the fence did not have before D33.
INTERPRETERS = {"sh", "bash", "zsh", "ksh", "dash", "python", "python2", "python3",
                "perl", "ruby", "node", "php", "osascript", "env"}
INTERPRETER_FLAG = re.compile(r"(^|\s)-[A-Za-z]*[ceE]([\s'\"]|$)")
# A quoted string plus whatever is GLUED to its right within the same shell word (N9c). The tail
# stops at whitespace, at a quote and at every shell operator, so it never swallows a command.
QUOTED_WORD = re.compile(r"('[^']*'|\"[^\"]*\")([^\s'\";|&<>()`]*)")


def heredoc_markers(line):
    """Every heredoc terminator opened on one command line, in the order the shell reads their
    bodies: `<<WORD`, `<<-WORD`, `<<'WORD'`, `<<"WORD"`. A `<<` inside quotes opens nothing, a
    here-STRING (`<<<`) is not a heredoc, a backslash-escaped `<` is literal, and an unquoted `#`
    starts a comment — the shell opens no heredoc from a comment, so neither does this, or a
    `# <<EOF` line would let the text beneath it pass unchecked as a body."""
    markers = []
    index, end, quote = 0, len(line), None
    while index < end:
        ch = line[index]
        if quote:
            if ch == quote:
                quote = None
            index += 1
            continue
        if ch in "'\"":
            quote = ch
            index += 1
            continue
        if ch == "\\":
            index += 2
            continue
        if ch == "#" and (index == 0 or line[index - 1] in " \t;|&("):
            break
        if not line.startswith("<<", index) or line.startswith("<<<", index):
            index += 1 if not line.startswith("<<<", index) else 3
            continue
        cursor = index + 2
        dash = cursor < end and line[cursor] == "-"
        cursor += 1 if dash else 0
        while cursor < end and line[cursor] in " \t":
            cursor += 1
        if cursor < end and line[cursor] in "'\"":
            closing = line.find(line[cursor], cursor + 1)
            word = line[cursor + 1:] if closing < 0 else line[cursor + 1:closing]
            cursor = end if closing < 0 else closing + 1
        else:
            chars = []
            while cursor < end and line[cursor] not in " \t;|&<>()":
                if line[cursor] == "\\" and cursor + 1 < end:
                    chars.append(line[cursor + 1])
                    cursor += 2
                    continue
                chars.append(line[cursor])
                cursor += 1
            word = "".join(chars)
        if word:
            markers.append((word, dash))
        index = cursor
    return markers


def strip_heredocs(text):
    """Remove every heredoc BODY, keeping the command lines that open them (design D33). The
    body ends at a line equal to the terminator (leading tabs stripped first for `<<-`), and an
    unterminated body runs to the end of the text — both as the shell reads them, so a body the
    shell never executes is never scanned here, and a line the shell would execute always is."""
    lines = text.split("\n")
    out = []
    index = 0
    while index < len(lines):
        line = lines[index]
        out.append(line)
        index += 1
        for word, dash in heredoc_markers(line):
            while index < len(lines):
                body = lines[index]
                index += 1
                if (body.lstrip("\t") if dash else body) == word:
                    break
    return "\n".join(out)


def slash_pattern(content):
    """True when a `/`-led quoted string is a sed/awk/grep PATTERN rather than a path (N9): the
    slash-delimited shape AND a metacharacter no path or glob carries, or the address-range shape
    `/a/,/b/`, which is a sed range in every script and no one's file name. The whole of the
    content must be the pattern: a trailing path separator, or anything but flags and an action
    after the closing delimiter, and it is a path again."""
    match = PATTERN_SHAPE.fullmatch(content)
    if not match:
        return False
    if match.group(2) is not None:
        return True                       # an address range
    return (any(ch in PATTERN_META for ch in match.group(1))
            or any(ch in TAIL_META for ch in match.group(3)))


def quoted_kind(content):
    """What a quoted string is for the READ checks (D33 as amended, N1 and N9), in this order:
      payload  — its content holds a newline or an operator character: a pattern, a script, a
                 pipeline. It names nothing the command reads.
      payload  — it is `/`-led and `slash_pattern` calls it a pattern: `'/^## Open/'`,
                 `'/x/{print $2}'`, `'/a/,/b/p'`. The shell passes these as patterns, not file paths.
      path     — its content starts with `/`, `~` or `$`: ONE path however many spaces it holds.
      payload  — anything else that holds whitespace: prose, a message, a search string.
      path     — a bare word: `"notes.md"`, checked like any unquoted token."""
    if any(ch in PAYLOAD_OPERATORS for ch in content):
        return "payload"
    if content.startswith("/") and slash_pattern(content):
        return "payload"
    if content.startswith(PATH_STARTS):
        return "path"
    return "payload" if any(ch.isspace() for ch in content) else "path"


def cut_glob(path):
    """A glob is tested by the deepest directory it cannot escape: `/x/*.md` → `/x/`. Cutting at
    the last separator before the first glob character keeps the test honest — the glob may match
    anything under that directory, and nothing above it."""
    hits = [path.find(ch) for ch in GLOB_CHARS if path.find(ch) >= 0]
    if not hits:
        return path
    slash = path.rfind("/", 0, min(hits))
    return path[:slash + 1] if slash >= 0 else path


# N11 (register, 2026-09-06): the PATTERN position of a pattern-taking command. A quoted string
# standing there is what the command searches for, never a file it reads, whatever its content
# looks like. A bare slash-led pattern need not have a closing delimiter; key the decision on the
# command's own grammar — the first operand after the flags, unless a flag already supplied the
# pattern or the program (`-e`, `-f` and their long forms), in which case every operand is a file.
# Only a QUOTED token is exempted: an unquoted pattern keeps today's reading, so the change is
# confined to the false-deny class measured.
PATTERN_COMMANDS = {"grep": "grep", "egrep": "grep", "fgrep": "grep", "zgrep": "grep",
                    "awk": "awk", "gawk": "awk", "mawk": "awk", "nawk": "awk", "sed": "sed"}
# Per family: the short letters that take a value (the glued tail or the next token is then no
# operand), the letters that SUPPLY the pattern or program (no positional pattern remains), and
# the long options of each kind. `-E` is a value flag for gawk (--exec) and a plain switch for
# grep and sed, which is why the tables are per family rather than shared.
PATTERN_FLAGS = {
    "grep": {"value": set("efmABCdD"), "supply": set("ef"),
             "value_long": {"--regexp", "--file", "--max-count", "--after-context",
                            "--before-context", "--context", "--directories", "--devices",
                            "--include", "--exclude", "--exclude-dir", "--exclude-from",
                            "--label", "--binary-files", "--group-separator"},
             "supply_long": {"--regexp", "--file"}},
    "awk":  {"value": set("fFvWeiIlE"), "supply": set("feE"),
             "value_long": {"--file", "--field-separator", "--assign", "--source", "--include",
                            "--load", "--exec"},
             "supply_long": {"--file", "--source", "--exec"}},
    "sed":  {"value": set("efl"), "supply": set("ef"),
             "value_long": {"--expression", "--file", "--line-length"},
             "supply_long": {"--expression", "--file"}},
}
# An interpreter's program flag as ONE shell word: `-c`, `-Bc`, `-e`, or the flag glued to its
# quoted program (`-c"..."`). The same shape INTERPRETER_FLAG reads out of running text.
INTERPRETER_TOKEN = re.compile(r"^-[A-Za-z]*[ceE](['\"]|$)")


def segment_command(words):
    """(index, basename) of a segment's command word, past leading assignments and prefix words;
    (None, None) for a segment made of those alone."""
    index = 0
    while index < len(words):
        word = unquote_token(words[index]).strip()
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word) or word in PREFIXES:
            index += 1
            continue
        return index, os.path.basename(word.rstrip(os.sep))
    return None, None


def interpreter_segment(words):
    """True when THIS segment invokes an interpreter with a program flag (`sh -c`, `python3 -c`,
    `perl -e`): its quoted argument is a command line, so the read checks keep its content and
    the pre-D33 behaviour — a denial — stands for it. Decided per segment (N11): the whole-line
    form would read `grep -c` in one segment against `python3` in another as an interpreter
    payload, tokenise every quoted string of the line and deny an awk pattern as a path (register,
    2026-09-06). A program passed WITHOUT such a flag (an awk or sed script) is payload
    like any other quoted string: the fence cannot decide it, and that residue is named in the
    docstring."""
    index, base = segment_command(words)
    if base not in INTERPRETERS:
        return False
    return any(INTERPRETER_TOKEN.match(word) for word in words[index + 1:])


def carries_interpreter_payload(text):
    """True when any segment of the text is an interpreter segment (kept for callers of the
    whole-text form; the read checks decide per segment)."""
    return any(interpreter_segment(words) for words in shell_segments(text))


def pattern_operand(words):
    """The index of the quoted token standing in the PATTERN position of a pattern-taking command
    (N11), else None: the first operand after the flags, read as the command reads them (a
    value-taking letter consumes its glued tail or the next token; `--` ends the flags; a
    redirection and its target belong to check 2). None as soon as a flag supplied the pattern or
    the program, since every operand is then a file the command reads. Only a quoted token
    qualifies: `grep -v "/log.md:"` is the case; `grep -v /log.md:` keeps today's reading."""
    index, base = segment_command(words)
    family = PATTERN_COMMANDS.get(base)
    if family is None:
        return None
    flags = PATTERN_FLAGS[family]
    i, end_of_flags = index + 1, False
    while i < len(words):
        raw = words[i]
        i += 1
        if raw[:1] in "<>":
            if "&" not in raw and i < len(words):
                i += 1                        # the redirection's target
            continue
        word = unquote_token(raw).strip()
        if not word:
            continue
        if not end_of_flags and word == "--":
            end_of_flags = True
            continue
        if not end_of_flags and word.startswith("-") and word != "-":
            if word.startswith("--"):
                name, sep, _ = word.partition("=")
                if name in flags["supply_long"]:
                    return None
                if not sep and name in flags["value_long"]:
                    i += 1
                continue
            for position in range(1, len(word)):
                letter = word[position]
                if letter in flags["supply"]:
                    return None
                if letter in flags["value"]:
                    if position + 1 >= len(word):
                        i += 1                # the value is the next token
                    break
            continue
        return i - 1 if raw[:1] in "'\"" else None
    return None


def quoted_tokens_marked(word):
    """The read-side reading of ONE shell word (D33, N1, N9, N9c): each quoted span that
    `quoted_kind` calls a path, whole and with its glob part cut; a `$`-led span with the text
    GLUED to it dropped as one token the fence cannot expand — `"$V"/wiki` is the same argument
    as `"$V/wiki"` and as the bare `$V/wiki`, both of which pass, and emitting the tail alone
    made `/wiki` an absolute token of its own and denied a lane's read-only grep (N9c); and
    `tokens_of` over what is left when the quoted spans are removed."""
    paths = []

    def replace(match):
        content, glued = match.group(1)[1:-1], match.group(2)
        kind = quoted_kind(content)
        if kind == "path" and content.startswith("$"):
            return " "
        if kind == "path":
            paths.append(cut_glob(content))
        return " %s " % glued if glued else " "
    rest = QUOTED_WORD.sub(replace, word)
    # A quoted span is a WHOLE word, never a fragment, so it is marked False (a path operand).
    return [(p, False) for p in paths] + tokens_marked(rest)


def quoted_tokens(word):
    """The tokens alone, for callers that do not need the fragment mark."""
    return [token for token, _ in quoted_tokens_marked(word)]


def read_tokens(text):
    """Every path token the read checks (3 and 4) test, read segment by segment from the same
    quote-aware tokens the mutator scan uses (`shell_segments`, N11), so a quote is paired within
    its own word and never across another segment's prose. An interpreter segment's program
    argument (`sh -c '…'`) is a command line, not quoted payload, so that segment's content is
    tokenised as though it were one; in every other segment the quoted token in a pattern-taking
    command's pattern position is payload, and each remaining word is read by `quoted_tokens`."""
    tokens = []
    for words in shell_segments(text):
        if interpreter_segment(words):
            tokens += tokens_marked(" ".join(words))
            continue
        skip = pattern_operand(words)
        for index, word in enumerate(words):
            if index != skip:
                tokens += quoted_tokens_marked(word)
    return tokens


# The characters `tokens_marked` cuts a word at. The GLOB subset matters separately: a token left
# behind by cutting at `*`, `?`, `[` or `]` is still a PATH (the deepest directory a glob cannot
# escape, D33), while a token left behind by cutting at any other metacharacter is a pattern
# FRAGMENT — half of an awk/sed/perl program, not a file name (review F2, register 2026-09-12).
_CUT_CHARS = "|;&<>()`$*?[]{}=,"
_GLOB_CUTS = "*?[]"


def tokens_marked(command):
    """(token, fragment) for every path-ish token: quote characters dropped and the metacharacters
    above turned into separators, so `--file=/etc/x` and `"/etc/x"` both yield /etc/x.

    `fragment` is True when a NON-GLOB metacharacter stood immediately beside the token, i.e. the
    token is the residue of cutting a longer word rather than a word the shell would pass. That is
    distinction between a whole path operand, which the grants must cover, and a token left
    by splitting shell syntax. Cutting at a glob character alone does NOT make a
    fragment, so `cat /etc/*.md` still tests `/etc/` and denies."""
    # A URL is not a filesystem path and its remnants must not be read as one. `https://[2001:db8::1]/x`
    # cuts at the brackets and would leave `/x` standing as an absolute path token, which check 4 then
    # denied even under a grant naming that host (review N3). No filesystem path carries `://`, so the
    # whole URL run is blanked here; the network check reads the raw text and owns the host itself.
    text = re.sub(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s'\"]*", " ", unquote(command))
    out, buf, left = [], [], False
    for ch in text:
        if ch in _CUT_CHARS:
            nonglob = ch not in _GLOB_CUTS
            if buf:
                out.append(("".join(buf), left or nonglob))
                del buf[:]
            left = nonglob
            continue
        if ch.isspace():
            if buf:
                out.append(("".join(buf), left))
                del buf[:]
            left = False
            continue
        buf.append(ch)
    if buf:
        out.append(("".join(buf), left))
    return out


def tokens_of(command):
    """The tokens alone, for callers that do not need the fragment mark (check 1, `command_words`)."""
    return [token for token, _ in tokens_marked(command)]


def unescape_token(token):
    """A token as the SHELL would hand it to the command: a backslash escape reduced to the
    character it escapes, so `/etc/hos\\ts` is tested as `/etc/hosts` (review F2a). Applied before
    every path test; it can only make a token match a real path more often, never less."""
    return re.sub(r"\\(.)", r"\1", token)


def command_words(command):
    """The first real word of each shell segment, plus every token whose basename could name
    a binary — enough to catch `xargs claude` and `find . -exec rm {} ;`."""
    words = []
    for segment in re.split(r"[;&|\n()]+", strip_quoted(command)):
        parts = segment.split()
        index = 0
        while index < len(parts):
            token = parts[index]
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", token) or token in PREFIXES:
                index += 1
                continue
            break
        if index < len(parts):
            words.append(parts[index])
    return words


def head_role(argv=None):
    """The head role: `--head` on the command line, or LLM_WIKI_FENCE_ROLE=head for a caller
    that cannot pass arguments. Anything else is the lane role."""
    argv = sys.argv[1:] if argv is None else argv
    return "--head" in argv or (os.environ.get("LLM_WIKI_FENCE_ROLE") or "").strip() == "head"


# ── register 2026-09-12 (fix 1), as folded after review's F2 ──
# Whether a `/`-led token is a PATTERN fragment or a PATH operand is decided by the tokeniser's
# `fragment` mark (see `tokens_marked`), not by a metacharacter set: a token the shell would hand
# over whole is a path and is tested against the grants; a token left behind by cutting a longer
# word at a non-glob metacharacter is a fragment of an awk/sed/perl program. The old
# SLASH_PATTERN_METACHARS set is retired with this fold: exempting `\` would let `cat /etc/hos\ts`
# (the shell reads `hosts`) clear, and exempting a lone `/` unconditionally would let `ls /`,
# `find / -name …` and `grep -r password /` clear. Backslashes are now unescaped before
# every path test (`unescape_token`).


def within_leaf(path, roots):
    """The SECOND read reading, for a leaf that does NOT yet exist (register 2026-09-10, fix 4, as
    folded after review's F2b): resolve the parent chain — so a `/tmp`→`/private/tmp` prefix and any
    symlinked grant directory match the already-resolved roots — and test the unresolved final
    component against them.

    A leaf that DOES exist is not this function's business and returns False: `within` has already
    resolved it through any symlink, and answering True here would grant whatever the link points
    at. A live symlink must be checked by its resolved target. A venv interpreter that is a live
    symlink out of the grants now denies again, and the remedy is the one the register entry itself
    carries — create the venv with `--copies`."""
    try:
        p = os.path.abspath(os.path.expanduser(path))
        if os.path.lexists(p):
            return False
        parent = os.path.realpath(os.path.dirname(p))
    except OSError:
        return False
    leaf = os.path.join(parent, os.path.basename(p)).rstrip(os.sep) or os.sep
    for root in roots:
        r = root.rstrip(os.sep)
        if leaf == r or leaf.startswith(r + os.sep):
            return True
    return False


def first_separator(text):
    """The operator joining the FIRST segment of `text` to the rest — `&&`, `||`, `;`, `|`, `&` or a
    newline — else None. Quote-aware, so a separator inside quoted prose is not one."""
    index, end, quote = 0, len(text), None
    while index < end:
        ch = text[index]
        if quote:
            if ch == quote:
                quote = None
            index += 1
            continue
        if ch in "'\"":
            quote = ch
            index += 1
            continue
        if ch == "\\":
            index += 2
            continue
        if ch in ";|&\n":
            if text.startswith("&&", index):
                return "&&"
            if text.startswith("||", index):
                return "||"
            return ch
        index += 1
    return None


def leading_cd_base(text):
    """The directory a LEADING `cd` moves into, for resolving a relative mutator target, else None
    (register 2026-09-08).
    The narrowing can only ever turn a false
    DENY into a clear and never the reverse — the caller still tests the resolved path against the
    write roots:
      - no unquoted `(` or `)` anywhere: a `cd` inside a subshell does not outlive it, and
        `shell_segments` discards that structure, so a parenthesised command gets no base at all;
      - exactly ONE `cd` segment, and it is the FIRST segment, so there is no ambiguity about which
        directory a later target is relative to;
      - its single operand is a LITERAL absolute path (no `$`, no backtick) the fence can resolve,
        and that path EXISTS as a directory; a failed `cd` cannot authorise a different write base;
      - the `cd` is joined to what follows by `&&` and nothing else: after `;` or `||` the shell
        runs the rest whatever the `cd` did, so only `&&` guarantees the move happened.
    A `cd` the caller finds is used only when it lies inside the write roots (the caller's test)."""
    if re.search(r"[()]", strip_quoted(text)):
        return None
    if first_separator(text) != "&&":
        return None
    segments = shell_segments(text)
    cd_positions = []
    for position, words in enumerate(segments):
        index, base = segment_command(words)
        if base == "cd":
            cd_positions.append((position, index, words))
    if len(cd_positions) != 1:
        return None
    position, index, words = cd_positions[0]
    if position != 0:
        return None
    operands = []
    for raw in words[index + 1:]:
        if "$" in raw or "`" in raw:
            return None                   # a directory this fence cannot resolve
        word = unquote_token(raw).strip()
        if not word or word.startswith("-"):
            continue
        operands.append(word)
    if len(operands) != 1:
        return None
    target = os.path.expanduser(operands[0])
    if not os.path.isabs(target) or not os.path.isdir(target):
        return None
    return norm(target)


def is_grant_change(command):
    """True only for the vault's OWN grant-widening primitive standing FIRST (register 2026-09-07,
    fix 3, as folded after review's F1). `handsoff.py grants` is the one command that widens a grant,
    and a new path is by definition outside the current grants, so the head fence would otherwise
    deny its own recovery; head-fence.py logs the cleared command as a `grant-change` event.

    The exemption skips every check, so it is keyed to all of these properties:
      - ONE simple command: a single segment, and no `;`, `&`, `|` or newline outside quotes;
      - no substitution anywhere in the text — no backtick, no `$(`, and no redirection operator;
      - the FIRST word is either the `handsoff.py` path itself or an interpreter that runs it, never
        another command with the words appended;
      - the script is the interpreter's first non-flag operand, its basename is `handsoff.py`, and it
        sits under a `.claude/skills/` directory OUTSIDE the temporary roots, so a copy a lane could
        have authored under `/tmp` is not the vault's primitive;
      - the operand right after that script is `grants`."""
    if re.search(r"[;&|\n]", strip_quoted(command)):
        return False
    if re.search(r"[`<>]", strip_quoted(command)) or "$(" in strip_quoted(command):
        return False
    segments = shell_segments(command)
    if len(segments) != 1:
        return False
    words = [unquote_token(raw).strip() for raw in segments[0]]
    words = [word for word in words if word]
    if not words:
        return False
    # review N2: "no substitution anywhere" must mean parameter expansion too: the backtick/`$(` test
    # alone would admit `--grant $NEWDIR` and `${NEWDIR}`, so a `$` in ANY word refuses.
    if any("$" in word for word in words):
        return False
    first = os.path.basename(words[0].rstrip(os.sep))
    if first == "handsoff.py":
        script, rest = words[0], words[1:]
    elif first in INTERPRETERS:
        # review N2: the primitive must be the interpreter's own first OPERAND. A `-c` payload that
        # merely spells the path (`python3 -c <handsoff.py path> grants`) is program text, not the
        # script being run, and never counts.
        letter = PROGRAM_FLAG_LETTER.get(first)
        if letter and any(re.match(r"^-[A-Za-z]*%s" % letter, word) for word in words[1:]):
            return False
        script, rest = None, []
        for index in range(1, len(words)):
            word = words[index]
            if word.startswith("-"):
                continue                  # an interpreter flag (-B, -E …); none here take a file
            script, rest = word, words[index + 1:]
            break
        if script is None or os.path.basename(script.rstrip(os.sep)) != "handsoff.py":
            return False
    else:
        return False
    resolved = norm(script)
    if (os.sep + ".claude" + os.sep + "skills" + os.sep) not in resolved + os.sep:
        return False
    if within(resolved, temp_roots()):
        return False                      # a copy under /tmp is not the vault's own primitive
    return bool(rest) and rest[0] == "grants"


# ── register 2026-09-07 / 2026-09-11, shape (c): an interpreter's OWN file write is invisible to the
# shell-channel scan, and this is the TRIPWIRE for it, not a fence. Read the program text an
# interpreter is handed — the argument behind ITS OWN program flag (PROGRAM_FLAG_LETTER, so `-E` and
# `-Wignore` cannot stand in for `-c`) and any heredoc body — for write-opening calls whose target is
# a STRING LITERAL, and check that literal against the write roots. Everything else is STATED
# RESIDUAL rather than implied cover: a variable or computed target, a keyword mode, a raw or format
# string, a deletion, a child process, and a program read from stdin or a substitution. Comment lines
# in the payload are ignored; a write call written inside a string literal is a known over-deny.
SCRIPT_INTERPRETERS = frozenset({"python", "python2", "python3", "perl", "ruby", "node"})
# The letter that introduces an interpreter's PROGRAM TEXT, per family. Keyed per interpreter
# because the same letter reads differently: `-E` is "ignore environment" to python and "program"
# to perl, and `-Wignore` merely ends in `e` (review F4).
PROGRAM_FLAG_LETTER = {"python": "c", "python2": "c", "python3": "c", "sh": "c", "bash": "c",
                       "zsh": "c", "ksh": "c", "dash": "c", "env": "c",
                       "perl": "e", "ruby": "e", "node": "e", "osascript": "e"}
_OPEN_CALL = re.compile(r"""\bopen\(\s*(?:'([^'\n]*)'|"([^"\n]*)")\s*,\s*(?:'([^'\n]*)'|"([^"\n]*)")""")
_PATH_WRITE = re.compile(r"""\bPath\(\s*(?:'([^'\n]*)'|"([^"\n]*)")\s*\)\s*\.write_(?:text|bytes)\(""")
_PATH_OPEN = re.compile(r"""\bPath\(\s*(?:'([^'\n]*)'|"([^"\n]*)")\s*\)\s*\.open\(\s*(?:'([^'\n]*)'|"([^"\n]*)")""")
_TWO_ARG = re.compile(r"""\b(?:os\.replace|os\.rename|shutil\.copyfile|shutil\.copy2|shutil\.copy|shutil\.move)"""
                      r"""\(\s*(?:'[^'\n]*'|"[^"\n]*"|[^,()]+?)\s*,\s*(?:'([^'\n]*)'|"([^"\n]*)")""")
# Network clients and the network modules an interpreter payload may import (register 2026-09-07,
# memory-hunter; the N class of the permission table). Keyed on the program basename, or an `import`
# in a payload — never on the word `http` appearing as data, so `grep http f` is not a network call.
NETWORK_CMDS = frozenset({"curl", "wget", "ssh", "scp", "sftp", "nc", "telnet", "ftp"})
# A payload reaches the network when it IMPORTS a transport (comma lists and `as` aliases included,
# review F6) or calls one. A bare `import socket` is NOT enough on its own: `socket.gethostname()`
# opens nothing, so the connecting calls are named instead.
NET_PAYLOAD_PATTERNS = (
    re.compile(r"(?:^|[\s;])(?:import|from)\s+[^\n;]*\b(?:urllib|requests|aiohttp|httpx)\b"),
    re.compile(r"(?:^|[\s;])(?:import|from)\s+[^\n;]*\bhttp\.client\b"),
    re.compile(r"(?:^|[\s;])from\s+http\s+import\s+client\b"),
    re.compile(r"__import__\(\s*['\"](?:urllib|requests|aiohttp|httpx|socket|http\.client)"),
    re.compile(r"\bsocket\s*\.\s*(?:socket|create_connection)\s*\("),
    re.compile(r"\brequire\(\s*['\"](?:https?|net|tls)['\"]\s*\)"),
    re.compile(r"(?:^|[\s;])use\s+(?:LWP|HTTP::|IO::Socket|Net::)"),
)


def _first_literal(groups, start):
    """The first non-None of a quoted-pair group (single- then double-quote)."""
    return groups[start] if groups[start] is not None else groups[start + 1]


def _strip_outer_quote(word):
    """Remove ONE matching outer shell quote, keeping any inner quotes: `"call('x','w')"` becomes
    `call('x','w')`, so the write-call and import scans see the payload's own Python string quotes.
    `unquote_token` cannot serve here — it drops every quote, blanking the literals the scan reads."""
    word = word.strip()
    if len(word) >= 2 and word[0] in "'\"" and word[-1] == word[0]:
        return word[1:-1]
    return word


def interpreter_payloads(command):
    """Every interpreter PROGRAM TEXT in `command`: the argument behind an interpreter's `-c`/`-e`/
    `-E` flag, and every heredoc body on a command line whose command is an interpreter (so a body
    fed to `cat` is not read as a program). Bodies are consumed in marker order like `strip_heredocs`,
    so a terminator appearing inside a body ends it there and cannot swallow the rest."""
    payloads = []
    for words in shell_segments(command):
        index, base = segment_command(words)
        if base not in INTERPRETERS:
            continue
        letter = PROGRAM_FLAG_LETTER.get(base)
        if letter is None:
            continue
        for j in range(index + 1, len(words)):
            word = words[j]
            # The PROGRAM flag of THIS interpreter, not the first flag that happens to end in c/e/E.
            # Match the interpreter's program flag, not a flag that merely shares its final letter.
            match = re.match(r"^-[A-Za-z]*%s(.*)$" % letter, word, re.S)
            if not match and word not in ("--eval", "--command"):
                continue
            tail = match.group(1) if match else ""
            if tail:
                payloads.append(_strip_outer_quote(tail))
            elif j + 1 < len(words):
                payloads.append(_strip_outer_quote(words[j + 1]))
            break
    lines = command.split("\n")
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        markers = heredoc_markers(line)
        if not markers:
            continue
        is_interp = any(segment_command(words)[1] in INTERPRETERS for words in shell_segments(line))
        for word, dash in markers:
            body = []
            while index < len(lines):
                current = lines[index]
                index += 1
                if (current.lstrip("\t") if dash else current) == word:
                    break
                body.append(current)
            if is_interp:
                payloads.append("\n".join(body))
    return payloads


def interpreter_write_literals(command):
    """(call, literal target) for every write-opening call in an interpreter payload whose target is
    a string literal (register fix b). Comment lines are dropped first. A variable target matches no
    pattern here and is the stated residual."""
    out = []
    for payload in interpreter_payloads(command):
        text = "\n".join(l for l in payload.split("\n") if not l.lstrip().startswith("#"))
        for match in _OPEN_CALL.finditer(text):
            target, mode = _first_literal(match.groups(), 0), _first_literal(match.groups(), 2)
            if target is not None and mode and any(ch in mode for ch in "wax"):
                out.append(("open", target))
        for match in _PATH_WRITE.finditer(text):
            out.append(("Path.write_text/bytes", _first_literal(match.groups(), 0)))
        for match in _PATH_OPEN.finditer(text):
            target, mode = _first_literal(match.groups(), 0), _first_literal(match.groups(), 2)
            if target is not None and mode and any(ch in mode for ch in "wax"):
                out.append(("Path.open", target))
        for match in _TWO_ARG.finditer(text):
            out.append(("copy/replace", match.group(1) if match.group(1) is not None else match.group(2)))
    return out


def script_honours_writes(script):
    """True when a script FILE ships under a `.claude/skills/` directory AND its text names
    `LLM_WIKI_LANE_WRITES` (it enforces the write roots itself, as the ingest sanitiser does). Read
    once; a missing or unreadable file is False (fail-closed). Keyed on the `.claude/skills/` path
    segment, not a hardcoded vault root, so it ships with the public framework."""
    path = os.path.abspath(os.path.expanduser(script))
    if (os.sep + ".claude" + os.sep + "skills" + os.sep) not in path + os.sep:
        return False
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return "LLM_WIKI_LANE_WRITES" in handle.read()
    except OSError:
        return False


def is_script_path(word):
    """True when an operand is a SCRIPT the interpreter would run: a readable file, or a name ending
    in `.py` or `.sh`. Keyed on the property rather than on position, so a sub-command word (`gate`,
    `register`) is not mistaken for a script (review F5)."""
    resolved = os.path.abspath(os.path.expanduser(word))
    return os.path.isfile(resolved) or word.endswith(".py") or word.endswith(".sh")


# review's N1 retired the old `is_file_operand`, which counted an argument only when it EXISTED or
# carried a path separator. That check misses a not-yet-existing relative file operand.
# For a script that does not ship under `.claude/skills/` and honour the variable, any
# non-option argument that is not an option's value counts as a file operand, whether
# or not it exists. The option's-value exclusion keeps a
# shipped tool's `--lane X` (and a sub-command's flag value) from being read as a file, and it is
# also the residue: a real file written after a value-taking flag (`-o out.md`) is not counted.


def script_file_write_deny(command):
    """A reason to deny, or None: a script FILE run by an interpreter under a WRITE-LESS lane
    (register 2026-09-11). A write inside a script file is invisible to the shell scan, so a lane
    with no write grant could rewrite any readable file through one. Allow a script that ships under
    `.claude/skills/` and honours `LLM_WIKI_LANE_WRITES`; deny any other script the moment it carries
    a file argument. A `-c`/`-e` program is the payload scan's, not this one's; a script with no file
    argument writes nothing to police and is allowed.

    `-m module` runs a module, so this script-file check does not classify its arguments as script-file targets."""
    for words in shell_segments(command):
        index, base = segment_command(words)
        if base not in SCRIPT_INTERPRETERS:
            continue
        rest = words[index + 1:]
        letter = PROGRAM_FLAG_LETTER.get(base, "c")
        if any(re.match(r"^-[A-Za-z]*%s" % letter, unquote_token(word).strip()) for word in rest):
            continue
        script, file_args, module, prev_flag = None, 0, False, False
        for raw in rest:
            word = unquote_token(raw).strip()
            if not word or word == "-":
                continue
            if word.startswith("-"):
                if word in ("-m", "--module") or (word.startswith("-m") and len(word) > 2):
                    module = True
                    break
                prev_flag = "=" not in word    # a `--flag=value` carries its own value
                continue
            if script is None:
                if not is_script_path(word):
                    break                 # a sub-command, not a script the interpreter runs
                script = word
                prev_flag = False
                continue
            if prev_flag:
                prev_flag = False         # this word is the preceding option's value, not a file
                continue
            file_args += 1                # N1: counted whether or not it exists on disk
        if module or script is None:
            continue
        if script_honours_writes(script):
            continue                      # a shipped script that bounds itself by the variable
        if file_args == 0:
            continue                      # nothing named for it to write to
        return ("`%s` runs the script `%s` with a file argument on a lane with no write grant; a "
                "write inside a script file is invisible to this fence, so it is denied unless the "
                "script ships under `.claude/skills/` and honours `LLM_WIKI_LANE_WRITES` "
                "(register 2026-09-11)" % (base, script))
    return None


def is_network_command(body, command):
    """True when the command's program is a network client, when an interpreter payload reaches the
    network, or a payload itself runs a network client, including a shell program string."""
    for words in shell_segments(body):
        _, base = segment_command(words)
        if base in NETWORK_CMDS:
            return True
    for payload in interpreter_payloads(command):
        if any(pattern.search(payload) for pattern in NET_PAYLOAD_PATTERNS):
            return True
        for words in shell_segments(payload):
            _, base = segment_command(words)
            if base in NETWORK_CMDS:
                return True
    return False


def command_hosts(text):
    """EVERY host the text addresses, not just the first (review F6): the host of each
    `https?://[userinfo@]host[:port]` — the userinfo is stripped, so
    `https://api.openalex.org@evil.example.com/` addresses `evil.example.com`, not the name in front
    of the `@` — and the host of each `user@host` token."""
    hosts = []
    for match in re.finditer(r"https?://([^/\s'\"]+)", text):
        authority = match.group(1)
        if "@" in authority:
            authority = authority.rsplit("@", 1)[1]
        # review N3: a bracketed IPv6 literal is taken WHOLE and its port dropped after the `]`.
        # Splitting at the first colon read `https://[2001:db8::1]/x` as the host `[2001`, which
        # denied under a grant naming that very address. A named host keeps its `host:port` reading.
        if authority.startswith("["):
            end = authority.find("]")
            if end > 0:
                host = authority[1:end]
                if host:
                    hosts.append(host)
                continue
        stem, sep, tail = authority.rpartition(":")
        host = stem if (sep and stem and tail.isdigit()) else authority
        if host:
            hosts.append(host)
    for match in re.finditer(r"(?<![A-Za-z0-9._@:/-])[A-Za-z0-9._-]+@([A-Za-z0-9._-]+)", text):
        hosts.append(match.group(1))
    return hosts


def network_operand_hosts(text):
    """The bare hostnames a network CLIENT takes as operands (`curl evil.example.com https://ok/x`
    addresses both). Only operands of a network command count, and only those that carry a dot, no
    path separator, no `@` and no scheme, and that name nothing on disk."""
    hosts = []
    for words in shell_segments(text):
        index, base = segment_command(words)
        if base not in NETWORK_CMDS:
            continue
        for raw in words[index + 1:]:
            word = unquote_token(raw).strip()
            if not word or word.startswith("-") or "://" in word or "@" in word:
                continue
            if os.sep in word or "." not in word:
                continue
            if not os.path.lexists(os.path.abspath(os.path.expanduser(word))):
                hosts.append(word.split(":")[0])
    return hosts


def host_granted(host, network):
    """True when `host` is named in the `network` grant, as an exact match or a subdomain of a listed
    host (`api.x.org` under a grant of `x.org`)."""
    host = host.strip().lower()
    for entry in network:
        listed = str(entry).strip().lower()
        if listed and (host == listed or host.endswith("." + listed)):
            return True
    return False


def check(event, grants, writes, head=False, network=None):
    """The whole decision as a pair — ("deny", reason), ("allow", reason) or ("silent", "") —
    computed, never printed and never exited, so head-fence.py can IMPORT this module and call
    this one function instead of paying a second interpreter start (D34 as amended, N8).
    `grants` and `writes` are lists of real paths; `network` is the run's `network` grant (a list of
    hosts, empty or None meaning no network); `head` selects the head role."""
    network = network or []
    def denial(reason):
        return "deny", "%s %s" % (FENCE, reason)

    if (event.get("tool_name") or "Bash") != "Bash":
        return "silent", ""               # not our channel; the harness decides
    if not grants:
        return denial("no grants in environment (LLM_WIKI_LANE_GRANTS unset or empty) "
                      "— fail-closed")

    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict) or "command" not in tool_input:
        return denial("no command in hook input — fail-closed")
    command = tool_input.get("command") or ""
    if not command.strip():
        return "silent", ""               # writes nothing, reads nothing

    temps = temp_roots()
    read_roots = grants + writes + temps
    write_roots = writes + temps

    # Heredoc bodies are data, whoever wrote them: removed once, before every check (D33). The
    # command lines that opened them stay, so their own redirects and command words are checked.
    body = strip_heredocs(command)

    # 1 — a lane never spawns a lane. Off in the head role: a head spawns lanes for a living.
    if not head:
        for token in tokens_of(body):
            if os.path.basename(token.rstrip(os.sep)) == "claude":
                return denial("a lane may not invoke `claude` (no nested spawns)")

    # N — network (register 2026-09-07, memory-hunter; N class of the permission table). A network
    #     client, or an interpreter payload that imports a network module, is denied unless the run's
    #     `network` grant names the host it addresses. An absent or empty `network` grant means no
    #     network at all; a network command that names no host under a grant is unresolvable.
    if is_network_command(body, command):
        hosts = sorted({h.lower() for h in
                        command_hosts(body) + command_hosts(command) + network_operand_hosts(body)
                        if h})
        if not network:
            return denial("a network command is denied: the run's grants carry no `network` list "
                          "(N class off)%s" % ((" — it addresses `%s`" % ", ".join(hosts)) if hosts else ""))
        if not hosts:
            return denial("a network command under a `network` grant names no host this fence can "
                          "resolve (no `https://host` or `user@host` token) — denied as unresolvable")
        ungranted = [h for h in hosts if not host_granted(h, network)]
        if ungranted:
            return denial("the network host `%s` is not named in the run's `network` grant"
                          % ungranted[0])

    # 2 — write channels. Strip fd duplications, then quoted content (keeping a quoted single-path
    #     target), then redirect/tee targets already inside the write set; deny on what survives.
    stripped = re.sub(r"[0-9]*>&[0-9-]+", " ", body)
    # N9: the quoted content goes FIRST, before any target is looked for, keeping a quoted
    # single-path target as a target. A `>` inside quotes is not a redirection in any shell, and
    # scanning it as one would falsely deny a read-only command.
    stripped = strip_quoted_for_writes(stripped)
    # Sanctioned write channels are removed by TESTING each target with the same path
    # comparison the read side uses, never by matching the root as a literal string: on this
    # platform a temporary root reaches the command unresolved (/var/folders/...) while the
    # environment carries it resolved (/private/var/folders/...), and a literal match would
    # deny a lane writing inside its own whitelist.
    for pattern in (r"(>>?)\s*[\"']?([^\s\"';|&<>]+)",
                    r"(tee)(?:\s+-a)?\s+[\"']?([^\s\"';|&<>]+)"):
        # N3, measured by critic C2: a target carrying a variable or a substitution is denied
        # outright. A dynamic target can resolve outside the write roots. The fence cannot
        # expand it safely, so it refuses it: write the literal path.
        for match in re.finditer(pattern, stripped):
            if "$" in match.group(2) or "`" in match.group(2):
                return denial("the %s target `%s` carries a variable or a substitution, which "
                              "this fence cannot resolve — write the literal path"
                              % ("redirection" if match.group(1) != "tee" else "`tee`",
                                 match.group(2)))
        while True:
            for match in re.finditer(pattern, stripped):
                target = match.group(2)
                if not os.path.isabs(os.path.expanduser(target)):
                    target = os.path.join(os.getcwd(), target)
                if within(target, write_roots):
                    stripped = (stripped[:match.start()] + " " * (match.end() - match.start())
                                + stripped[match.end():])
                    break
            else:
                break
    cd_base = leading_cd_base(body)
    scope = "outside the write whitelist" if writes else "on a lane with no write grant"
    if ">" in stripped:
        return denial("shell redirection %s is denied (writes go to the granted directories, or "
                      "the change comes back as a proposed diff)" % scope)
    if re.search(r"(^|[^A-Za-z0-9_])tee([^A-Za-z0-9_]|$)", stripped):
        return denial("`tee` %s is denied" % scope)
    if re.search(r"(^|[^A-Za-z0-9_])(sed|perl)[^|;&]{0,60}\s-[A-Za-z]*i", stripped):
        return denial("an in-place editor (sed -i / perl -i) %s is denied" % scope)
    for mutator, raw in mutator_targets(body):
        # N3 on the TARGET alone: a variable or a substitution the fence cannot resolve. A source
        # carrying one is a read, and the read side owns it.
        if "$" in raw or "`" in raw:
            return denial("`%s` takes the target `%s`, which carries a variable or a substitution "
                          "this fence cannot resolve — write the literal path (N3)" % (mutator, raw))
        target = cut_glob(unquote(raw).strip())
        if not target:
            continue
        # A relative target is resolved against the directory a LEADING `cd` moved into when that
        # directory is itself inside the write roots (register 2026-09-08), else against the hook's
        # own working directory as before. The `within` test below is unchanged either way, so a
        # target that climbs back out (`../x`) still denies.
        base = cd_base if cd_base is not None and within(cd_base, write_roots) else os.getcwd()
        if not within(target if os.path.isabs(os.path.expanduser(target))
                      else os.path.join(base, target), write_roots):
            return denial("`%s` targets `%s`, which is %s" % (mutator, target, scope))

    # 2b — an interpreter's OWN write (register fix b): a write-opening call in a `-c`/`-e` program
    #      or a heredoc body whose target is a string literal, checked against the write roots. A
    #      variable target is the stated residual. Scanned on the ORIGINAL command, heredocs intact.
    for call, target in interpreter_write_literals(command):
        if not target:
            continue
        # A relative literal takes the same leading-`cd` base as a mutator target (review F8), so
        # a `cd <dir in W>` followed by an interpreter writing a RELATIVE literal clears where the
        # shell would actually write, instead of being measured against the hook's own directory.
        lit_base = cd_base if cd_base is not None and within(cd_base, write_roots) else os.getcwd()
        resolved = (target if os.path.isabs(os.path.expanduser(target))
                    else os.path.join(lit_base, target))
        if not within(resolved, write_roots):
            return denial("an interpreter's `%s` writes `%s`, which is %s — the literal-shape "
                          "tripwire: class W covers shell writes, and a write-opening call whose "
                          "target is a plain literal is checked against the write roots too"
                          % (call, target, scope))

    # 2c — a script FILE run by an interpreter under a WRITE-LESS lane (register 2026-09-11): its
    #      write is invisible to this fence, so a file argument is denied unless the script ships
    #      under `.claude/skills/` and honours the write variable itself.
    if not writes:
        reason = script_file_write_deny(body)
        if reason:
            return denial(reason)

    # 3 and 4 read PATHS: `read_tokens` decides what is a path and what is payload (D33, N1). A
    # `/`-led token that is an awk/sed/perl pattern fragment is dropped here (fix 1), never read as
    # a path — the write side above has already run on the full token set.
    # `read_tokens` returns (token, fragment) pairs: a `/`-led FRAGMENT is the residue of cutting a
    # longer word at a non-glob metacharacter (half an awk/sed/perl program) and is not a path; a
    # token the shell would hand over whole is tested, `ls /` included (review F2a).
    tokens = [(unescape_token(token), fragment) for token, fragment in read_tokens(body)]
    tokens = [(token, fragment) for token, fragment in tokens
              if not (fragment and token.startswith("/"))]

    # 3 — a relative token may not climb out of the working directory.
    for token, _ in tokens:
        if os.path.isabs(os.path.expanduser(token)):
            continue
        if ".." in token.split(os.sep):
            return denial("relative path `%s` escapes the working directory" % token)

    # 4 — an absolute token must sit inside the grants. `git` needs no rule of its own in either
    # role: it is not a mutator token, and its own paths are checked like any other (N8).
    cwd = norm(os.getcwd())
    for token, _ in tokens:
        expanded = os.path.expanduser(token)
        if not os.path.isabs(expanded):
            continue
        if any(expanded.startswith(prefix) for prefix in SYSTEM_BIN) and os.path.exists(expanded):
            continue                      # invoking a system binary is not data access
        if within(expanded, read_roots + [cwd]) or within_leaf(expanded, read_roots + [cwd]):
            continue                      # within_leaf: a symlink sitting inside a grant (fix 4)
        return denial("`%s` is outside the granted directories — report the gap "
                      "(`needs: <path> because <reason>`) instead of working around it" % token)

    # Cleared. A lane gets the explicit allow its permission flow needs; a head gets silence, an
    # explicit allow there being read by the harness as auto-approval (C1 F1).
    return ("silent", "") if head else ("allow", "%s within grants" % FENCE)


# Commands whose LAST non-flag operand is the thing they create; every earlier one is a source,
# which is a READ and is tested by checks 3 and 4, never by the write rule.
SOURCE_AND_TARGET = {"cp", "mv", "install", "ln"}
# The characters that end a segment OUTSIDE quotes, the same set `command_words` splits on.
SEGMENT_SEPARATORS = ";&|\n()"
# Flags that take a VALUE, per command, because the same letter reads differently: `-t` is a
# target DIRECTORY for cp/mv/ln/install and a TIMESTAMP for touch, `-s` a size for truncate and
# "symbolic" for ln. A value is not an operand — `install -m 644 a b` writes b, never a file
# called 644 (N10).
VALUE_FLAGS = {
    "cp":       {"-t", "--target-directory", "-S", "--suffix"},
    "mv":       {"-t", "--target-directory", "-S", "--suffix"},
    "ln":       {"-t", "--target-directory", "-S", "--suffix"},
    "install":  {"-t", "--target-directory", "-m", "--mode", "-o", "--owner", "-g", "--group",
                 "-S", "--suffix", "--strip-program"},
    "mkdir":    {"-m", "--mode"},
    "touch":    {"-r", "--reference", "-t", "-d", "--date", "--time"},
    "truncate": {"-s", "--size", "-r", "--reference"},
    "chmod":    {"--reference"},
    "chown":    {"--reference", "--from"},
    "chgrp":    {"--reference"},
    "shred":    {"-n", "--iterations", "-s", "--size", "--random-source"},
}
# The one value that is itself a WRITE: the directory cp/mv/ln/install copy INTO.
TARGET_DIR_FLAGS = {"-t", "--target-directory"}
# A chmod MODE: octal (one to four digits — three permission triples plus the optional setuid
# digit) or symbolic, comma-joined. Keyed on the token's shape, never on a list of known modes,
# so `chmod 644 644` still reads its SECOND operand as the file it writes.
MODE_SHAPE = re.compile(r"^[0-7]{1,4}$"
                        r"|^[ugoa]*[-+=][rwxXstugo]*(,[ugoa]*[-+=][rwxXstugo]*)*$")


def shell_segments(text):
    """The command's segments, each a list of RAW tokens (quotes still on), split the way the
    shell splits — on `; & | newline ( )` OUTSIDE quotes only, so a separator inside quoted prose
    starts no segment. A quoted span glues to whatever touches it, as the shell joins them into
    one word (`"/x"/y` is one operand); a backslash escapes the next character, so a continued
    line stays one segment; an unterminated quote runs to the end of the text, which keeps the
    write side fail-closed on it. A redirection operator becomes its own token (`>`, `>>`, `2>`,
    `2>&1`) so the operand grammar can drop it together with its target: a redirect target belongs
    to check 2, not to a mutator's operands.

    Heredoc bodies are NOT handled here: `check` strips them once before any check runs, and a
    second strip would let a stripped body's opening line swallow the commands beneath it."""
    segments, tokens, current = [], [], []
    index, end = 0, len(text)

    def close_token():
        if current:
            tokens.append("".join(current))
            del current[:]

    def close_segment():
        close_token()
        if tokens:
            segments.append(list(tokens))
        del tokens[:]

    while index < end:
        char = text[index]
        if char in "'\"":
            closing = text.find(char, index + 1)
            if closing < 0:                   # unterminated: the rest of the text is one word
                current.append(text[index:])
                index = end
                continue
            current.append(text[index:closing + 1])
            index = closing + 1
            continue
        if char == "\\" and index + 1 < end:
            current.append(text[index:index + 2])
            index += 2
            continue
        if char in SEGMENT_SEPARATORS:
            close_segment()
            index += 1
            continue
        if char in "<>":
            if current and "".join(current).isdigit():
                del current[:]                # a file-descriptor number belongs to the operator
            close_token()
            start = index
            while index < end and text[index] in "<>&0123456789-":
                index += 1
            tokens.append(text[start:index])
            continue
        if char.isspace():
            close_token()
            index += 1
            continue
        current.append(char)
        index += 1
    close_segment()
    return segments


def unquote_token(token):
    """One shell WORD with its quoting resolved: quote characters removed rather than blanked
    (`"/x"/y` → `/x/y`, the single path the shell passes) and a backslash escape reduced to what
    it escapes. `unquote` cannot serve here — it blanks a quote into a SPACE, which splits exactly
    the glued word this has to keep whole. A backslash inside single quotes is literal to the
    shell and is unescaped here anyway: the difference is a file name carrying a backslash."""
    return re.sub(r"\\(.)", r"\1", token.replace('"', "").replace("'", ""), flags=re.S)


def flag_reading(command, word):
    """How a dash-led word is read by `command`: (glued value or None, consumes the next token,
    the value is a write TARGET). A short cluster is read as getopt reads it — in `-rft/dir` the
    tail of the first value-taking letter is that letter's argument — and a long option takes its
    value glued behind `=` or from the next token.

    Leftward glue: the shell hands the command ONE word, so a write can hide in the glued
    spelling of a flag whose value is a directory (`cp -t"/dir" src`, `install -t/dir src`), and
    that is the case this returns as a target. Every other glued value is a mode, a size, an
    owner, a suffix or a timestamp, which names no file the command creates, and a glued path
    behind a flag that takes NO value (`rm -rf"/dir"`) is not a write at all: the command reads
    the whole word as options and errors out."""
    takes = VALUE_FLAGS.get(command, set())
    if word.startswith("--"):
        name, sep, glued = word.partition("=")
        if name not in takes:
            return None, False, False
        target = command in SOURCE_AND_TARGET and name in TARGET_DIR_FLAGS
        return (glued, False, target) if sep else (None, True, target)
    for position in range(1, len(word)):
        flag = "-" + word[position]
        if flag in takes:
            target = command in SOURCE_AND_TARGET and flag in TARGET_DIR_FLAGS
            tail = word[position + 1:]
            return (tail, False, target) if tail else (None, True, target)
    return None, False, False


def mutator_operands(command, tokens):
    """(operands, flag-named targets, flags seen) for one mutator's token list — what the command
    reads as its arguments once redirections, flags and their values are taken out. Operands are
    unquoted; an operand that is genuinely empty (`""`) is kept, so a command whose target is an
    empty string keeps today's verdict, while the residue of a backslash-escaped newline is not."""
    operands, flag_targets, flags = [], [], set()
    index, end_of_flags = 0, False
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if token[:1] in "<>":
            # A redirection and its target: check 2 owns both. An operator carrying `&` is a file
            # descriptor duplication (`2>&1`) and takes no following word.
            if "&" not in token and index < len(tokens):
                index += 1
            continue
        word = unquote_token(token).strip()
        if not word:
            if token.strip("'\"") == "":      # a real empty operand, not escape residue
                operands.append("")
            continue
        if not end_of_flags and word == "--":
            end_of_flags = True
            continue
        if not end_of_flags and word.startswith("-") and word != "-":
            glued, consumes, is_target = flag_reading(command, word)
            flags.update(["-" + ch for ch in word[1:]] if not word.startswith("--")
                         else [word.partition("=")[0]])
            if glued and is_target:
                flag_targets.append(glued)
            if consumes and index < len(tokens):
                value = unquote_token(tokens[index]).strip()
                index += 1
                if is_target:
                    flag_targets.append(value)
            continue
        if not end_of_flags and word.startswith("+"):
            continue                          # a `+`-led symbolic mode (`chmod +x`) is no path
        operands.append(word)
    return operands, flag_targets, flags


def mutator_targets(text):
    """(mutator word, target) for every write a mutator command actually makes, scoped to its OWN
    segment and read from its tokens. Quoted prose, quoted command substitutions and a chmod
    mode must not be treated as independent write targets.

    So: segments and words come from `shell_segments`, which is quote-aware, and a mutator word
    inside another command's quoted argument is prose, never a command. A quoted whole token that
    IS an operand stays a target (`cp a "/outside/b"` still denies). A leading `VAR=value`
    assignment and the prefix words (`sudo`, `env`, `xargs`) are stepped over. Operands that name
    no file are dropped by the shape of the token, never by a magic value: a chmod MODE, a
    chown/chgrp owner or group spec, a flag's value, a redirection target. For cp/mv/ln/install
    only the last operand is written, unless `-t` named the target directory (then every operand
    is a source) or `install -d` created all of them; for `dd` only the `of=` operand is a write,
    `if=` being a read that checks 3 and 4 own.

    The target comes back with its quotes already resolved, so the caller's `unquote` is a no-op
    on it while its `$` and backtick test (N3) still sees what the shell would expand."""
    out = []
    for words in shell_segments(text):
        index = 0
        while index < len(words):
            word = unquote_token(words[index]).strip()
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word) or word in PREFIXES:
                index += 1
                continue
            break
        if index >= len(words):
            continue
        mutator = unquote_token(words[index]).strip()
        base = os.path.basename(mutator.rstrip(os.sep))
        if base not in MUTATORS:
            continue
        operands, targets, flags = mutator_operands(base, words[index + 1:])
        if base == "dd":
            # dd's operands are `key=value`: `of=` names the file it writes, `if=` a file it
            # reads, and `bs=`, `count=`, `seek=` name no file at all.
            operands = [operand.partition("=")[2] for operand in operands
                        if operand.partition("=")[0] == "of"]
        else:
            if base == "chmod" and operands and MODE_SHAPE.match(operands[0]):
                operands = operands[1:]       # the first operand is a mode, not a path
            if base in ("chown", "chgrp") and operands and os.sep not in operands[0]:
                # The first operand is the owner or group spec. Keyed on shape: a spec carries no
                # path separator, so `chown --reference=/ref /outside/x` keeps its target.
                operands = operands[1:]
            if base in SOURCE_AND_TARGET:
                if targets:
                    operands = []             # `-t` named the target; every operand is a source
                elif not (base == "install" and flags & {"-d", "--directory"}):
                    operands = operands[-1:]  # only the last is created; the rest are reads
        for target in targets + operands:
            out.append((mutator, target))
    return out


def main():
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else None
    except ValueError:
        event = None
    if not isinstance(event, dict):
        deny("hook input unreadable (no JSON on stdin) — fail-closed")
    action, reason = check(event, roots_from("LLM_WIKI_LANE_GRANTS"),
                           roots_from("LLM_WIKI_LANE_WRITES"), head_role(),
                           hosts_from("LLM_WIKI_LANE_NETWORK"))
    if action == "silent":
        sys.exit(0)
    decide(action, reason)


if __name__ == "__main__":
    main()
