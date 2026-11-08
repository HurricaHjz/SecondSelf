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
  1. an invocation of `claude` (a lane may not spawn lanes, nor escape its own fence); the
     PATTERN words of a search command (grep and its family, rg) are not read for it, since a search
     runs nothing it matches (Kc37755f0), while an awk or sed program is program text and is read;
  N. a network command (`curl`, `wget`, `ssh`, `scp`, `sftp`, remote `rsync`, `nc`, `telnet`, `ftp`, or an
     interpreter payload importing `urllib`, `requests`, `http.client`, `socket` or `aiohttp`)
     unless the `network` grant names every identified connection host; no `network` grant is no network, a network command with no host token
     under a grant is unresolvable and denied (register 2026-09-07, memory-hunter). The separated
     value of a curl or wget option that names a file or a datum (`-o x.md`, `--header …`) is no
     host (Kb2a266d1, `NETWORK_VALUE_FLAGS`); an endpoint option's value (`--url`, a proxy,
     `--connect-to`) and any option not on that list keep the host reading. Explicit curl/wget
     configuration, wget input lists and curl alternative-service caches are unresolvable and
     denied even beside a granted URL: their contents can name further machines;
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
     of known values, so `chmod 644 644` still reads its second operand as the file it writes.
     Curl/wget file options face the same write test, as does the download directory for remote
     names (wget's default). Curl's write-out file directives are checked too; an indirect or
     computed format is unresolvable. A documented standard-output target creates no file;
  3. a relative path token that escapes the working directory (a `..` component);
  4. an absolute path token outside the read grants.

Between checks 1 and N, the ssh-family classifier separates local shell I/O, then returns
connection hosts, local reads, local writes and unresolved syntax. Local copy endpoints and
option files retain their grants. Literal remote operands and simple double-quoted parameters
after a fixed SSH host are remote data, exempt from local path and host scans. Local program
substitution, unknown options and unseen explicit configuration refuse. Plain shell program
wrappers share this reading; unsupported wrappers refuse. Each preceding controlling literal
`cd <absolute directory> &&` supplies its following segments' base before permissions are tested.

Before any of those four run, the HEREDOC BODIES are removed (`strip_heredocs`, design D33):
`<<` and `<<-`, quoted (`'EOF'`, `"EOF"`) and bare terminators, several heredocs opened on one
command line consumed in marker order, a line equal to the terminator (after `<<-` strips leading
tabs) ending that body there, and an unterminated body running to the end of the text — each as
the shell reads the terminator. For ssh-family lines, unquoted heredoc substitution is separately
refused as unresolved local evaluation; protected bodies remain data. The command line
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
denies, less a search command's pattern words (`search_pattern_indices`); a pattern word holding a
command substitution, and an rg call carrying an option that runs a program, are read all the same.
Check 2 runs on the QUOTED-STRIPPED text (N9): a `>` inside quotes is not a redirection in
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
  - the unplaced-read logger's premises fail (not a real hook event, no run-id-shaped run, no
    run record in the store, a blank command) → it writes nothing and the decision stands. A
    failed append is noted beside the log and the decision stands; every file the logger opens
    is opened non-blocking and must be a regular file, so no open can hold a decision back.
The process exits 0 in every case (the report mode exits 0, 1 or 2); a non-zero exit from a
PreToolUse hook is a harness error, not a denial, so it is never used to express one.

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
a plus (`"/etc/{a}"`) is read as a pattern and passes unchecked, a file name no vault holds. An
UNQUOTED glob word is read whole and judged by its deepest literal directory (`glob_bound`,
Kef9c30da): `ls -d /x/*/` tests `/x/`, and `/x/*/f.md` tests `/x/`, never the `/` or `/f.md` a cut
at the `*` used to leave. A glob with a component after its first glob character that is `..` or
dot-led keeps the split reading and fails closed. What the bound does not see is named: the names a
glob matches are not resolved before the test, so a symlink inside the bound directory is judged by
that directory. The inline-program literal half stays a residue, fail-closed by design: a `/` or
`~` string literal inside a `-c` program is read as a path and false-denies outside the grants. On
the READ side a LITERAL quoted directory glued to a name (`cat "/x"/y`) is still split into two
tokens, so the tail (`/y`) is tested as a path of its own and false-denies; N9c glues only a
`$`-led string, and the write side reads the same word whole (N10).
Relative local targets use the directory of their own command segment. A preceding literal
absolute `cd ... &&` establishes that base independently of its permissions, then the resolved
target faces the read or write grants. Earlier operands retain their earlier base. Ambiguous,
variable or subshell directory changes cannot establish permission for relative targets.
Fail-closed residues that stay: a mutator whose
target is a variable (`chmod +x "$f"`, `cp a "$D/b"`) is denied, because the fence sees no literal
path to test — a lane writes the literal path; an interpreter's program argument (`sh -c '…'`,
`python3 -c '…'`) keeps its content for the read checks, so a path inside it is tested and an
outside one denies as before D33, while a program passed with no `-c`/`-e` flag (an awk or sed
script) is payload the fence cannot decide; `sh -c '...'` still hides its payload from the
command-word tests. A path token is judged by its REALPATH (`within`); the second reading
(`within_leaf`, fix 4 as narrowed on 14 September after review F2b) serves only a leaf that does
NOT exist yet, testing its resolved parent chain with the final component as written, so a file a
command is about to create under a symlinked grant directory (`/tmp` → `/private/tmp`) clears. A leaf
that EXISTS, a live symlink included, is judged by its resolved target alone: a symlink sitting
inside a grant but pointing outside the roots is denied, so a venv `bin/python` symlinked to an
interpreter outside the grants is refused (create the venv with `--copies`, or grant the
interpreter's real location), and a symlinked directory COMPONENT that points out is resolved and
so denies too. Each of these
fails towards denial; a lane that hits one reports the gap and the head re-spawns it with the grant
(the re-spawn rule), which is the designed recovery. The one direction that is NOT fail-closed is
named, and it is a READ: a quoted target whose variable the fence cannot expand — `cat
"$HOME/Library/Application Support/x"`, `cat "$D/secret"` — is one path token that is not absolute,
so checks 3 and 4 have nothing to test and it passes. Unquoted it always passed too (`tokens_of`
splits on `$`), and the WRITE side of the same shape denies outright (N3), so what remains is a
lane reading through a variable it set itself; the grants, not this fence, are what bound that.
Such a read is LOGGED, never refused (the owner's decision of 23 October 2026: log these reads,
and refuse only if the logs later show real reads outside a helper's folders). After a command
is cleared (the lane's `allow` in `main`, the head's silence in head-fence.py),
`record_unplaced_reads` scans it with `unplaced_reads`: a parameter, command substitution,
arithmetic, brace or ANSI-C expansion this fence cannot place, and shell code handed to `eval`,
`alias` or `trap` or to a shell by `-c`, heredoc, here-string or pipe. A command holding one
gains one JSON line in `<store>/spawn-records/<run>-unplaced-reads.jsonl` (`<store>` is
LLM_WIKI_STORE or ~/.llm-wiki; `<run>` is LLM_WIKI_LANE_RUN, or the head's run in
head-fence.py). Each writer session also leaves one TRACE line on its first cleared command,
marked by an empty file `<LLM_WIKI_PROGRESS_DIR or /tmp>/<run>-unplaced-reads-seen-<16 hex>`,
so the close can tell a writer with nothing to log from one that never ran. The writer writes
only for a real PreToolUse event, a run-id-shaped run, a regular file at
`<store>/spawn-records/<run>.jsonl` and a non-blank command. A failed append is noted in
`<run>-unplaced-reads.failed` beside the log and on stderr, and the decision stands. The close
reads the log with `lane-fence.py --unplaced-reads <run> [--limit N]`, stdout only and
read-only: exit 0 complete, 1 incomplete (a premise warning; a low count is then no clean
result), 2 probe failed (no log, or one that cannot be read). The log holds command text, never
a variable's value; whether a logged read left its helper's folders is the reader's judgement.
A suite that sends this checker an event whose `hook_event_name` is `PreToolUse` points
LLM_WIKI_STORE at a fixture holding no live run record, so none of its legs can write a real
run's log.
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

import hashlib
import json
import os
import re
import stat
import sys
import time
from datetime import datetime

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


def glob_bound(word):
    """The deepest literal directory of an unquoted glob WORD (Kef9c30da), or None when the word
    cannot be bounded that way: a component at or after the first glob character that is `..`, or
    that starts with a dot (escaped or not) and carries a glob character, may name a parent entry in
    some shells, so the directory before the glob would no longer be a bound. The caller then keeps
    the split reading, which tests each piece as a path of its own and so fails closed."""
    hits = [word.find(ch) for ch in GLOB_CHARS if word.find(ch) >= 0]
    if not hits:
        return word
    slash = word.rfind("/", 0, min(hits))
    for part in word[slash + 1:].split("/"):
        if part == ".." or (part.lstrip("\\").startswith(".") and any(ch in part for ch in GLOB_CHARS)):
            return None
    return cut_glob(word)


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


# Kc37755f0: the SEARCH commands whose pattern check 1 does not read as a command word. A search
# pattern is text the command matches and never runs, so `grep -n '"claude"' f` invokes nothing. Only
# search commands are here: an awk or sed PROGRAM can run commands (awk's `system()` and pipes,
# sed's `e`), so it is program text like `python3 -c`, and check 1 keeps reading it.
SEARCH_COMMANDS = {"grep": "grep", "egrep": "grep", "fgrep": "grep", "zgrep": "grep", "rg": "rg"}
# Per family: the letters and long options whose value IS a pattern (`-e`), those whose value is a
# file of patterns (`-f`; the file name stays visible), and every other value-taking option, so the
# positional pattern is found where the command finds it. A value option missing from a table can
# only move the skip onto that option's value, never onto a word the command runs.
SEARCH_FLAGS = {
    "grep": {"pattern": set("e"), "pattern_long": {"--regexp"},
             "value": PATTERN_FLAGS["grep"]["value"], "supply": PATTERN_FLAGS["grep"]["supply"],
             "value_long": PATTERN_FLAGS["grep"]["value_long"],
             "supply_long": PATTERN_FLAGS["grep"]["supply_long"]},
    "rg":   {"pattern": set("e"), "pattern_long": {"--regexp"},
             "value": set("efgtTmABCEjMdr"), "supply": set("ef"),
             "value_long": {"--regexp", "--file", "--glob", "--iglob", "--type", "--type-not",
                            "--type-add", "--type-clear", "--max-count", "--after-context",
                            "--before-context", "--context", "--encoding", "--threads",
                            "--max-columns", "--max-depth", "--max-filesize", "--replace",
                            "--color", "--colors", "--context-separator", "--path-separator",
                            "--sort", "--sortr", "--engine", "--ignore-file", "--pre-glob",
                            "--field-context-separator", "--field-match-separator",
                            "--dfa-size-limit", "--regex-size-limit", "--hyperlink-format"},
             "supply_long": {"--regexp", "--file"}},
}
# rg options whose value is a program rg runs: a segment carrying one gets no skip at all.
SEARCH_EXEC_OPTIONS = {"rg": ("--pre", "--hostname-bin")}


def search_pattern_indices(words):
    """The indices of a search command's PATTERN words in one segment (Kc37755f0): the values of
    `-e`/`--regexp`, and the first operand after the flags when no option supplied the pattern.
    Empty for any other command, for an rg segment carrying an option that runs a program, and for
    any word holding a command substitution (`$(` or a backtick), which the shell runs before the
    search starts."""
    index, base = segment_command(words)
    family = SEARCH_COMMANDS.get(base)
    if family is None:
        return set()
    plain = [unquote_token(raw).strip() for raw in words]
    exec_options = SEARCH_EXEC_OPTIONS.get(family, ())
    if exec_options and any(word.startswith(exec_options) for word in plain):
        return set()                          # `--pre-glob` shares the prefix: no skip, fail-closed
    flags = SEARCH_FLAGS[family]
    out, supplied, positional = set(), False, False
    i, end_of_flags = index + 1, False
    while i < len(words):
        raw, word = words[i], plain[i]
        i += 1
        if raw[:1] in "<>":
            if "&" not in raw and i < len(words):
                i += 1                        # the redirection's target
            continue
        if not word:
            continue
        if not end_of_flags and word == "--":
            end_of_flags = True
            continue
        if not end_of_flags and word.startswith("-") and word != "-":
            if word.startswith("--"):
                name, sep, _ = word.partition("=")
                if name in flags["pattern_long"]:
                    supplied = True
                    if sep:
                        out.add(i - 1)
                    elif i < len(words):
                        out.add(i)
                        i += 1
                    continue
                if name in flags["supply_long"]:
                    supplied = True
                if not sep and name in flags["value_long"]:
                    i += 1
                continue
            for position in range(1, len(word)):
                letter = word[position]
                if letter not in flags["value"]:
                    continue
                glued = position + 1 < len(word)
                if letter in flags["pattern"]:
                    supplied = True
                    if glued:
                        out.add(i - 1)
                    elif i < len(words):
                        out.add(i)
                        i += 1
                else:
                    if letter in flags["supply"]:
                        supplied = True
                    if not glued:
                        i += 1                # the value is the next token
                break
            continue
        if not positional:
            positional = True
            if not supplied:
                out.add(i - 1)
    return {j for j in out if "$(" not in words[j] and "`" not in words[j]}


def remote_search_view(body):
    """Classify search patterns inside fully literal SSH remote-command operands.

    SSH joins its remote arguments with spaces before the remote shell parses them.
    Only that literal grammar supplies a pattern exemption; locally evaluated words
    retain their original spelling for check 1 and the later SSH boundary checks.
    Local redirections and actual remote program words remain visible.
    """
    changes = []
    for segment in ssh_shell_words(body):
        words = [item[0] for item in segment]
        remote_indices = []
        _, _, _, errors = ssh_family_info(words, remote_indices=remote_indices)
        if errors or not remote_indices:
            continue
        remote_words = [ssh_literal(words[index]) for index in remote_indices]
        if any(error for _, error in remote_words):
            continue
        remote = shell_segments(" ".join(value for value, _ in remote_words))
        skips = [search_pattern_indices(part) for part in remote]
        if not any(skips):
            continue
        replacement = "\n".join(" ".join(word for index, word in enumerate(part) if index not in skip)
                                for part, skip in zip(remote, skips))
        for offset, index in enumerate(remote_indices):
            _, start, end = segment[index]
            changes.append((start, end, replacement if offset == 0 else ""))
    for start, end, replacement in sorted(changes, reverse=True):
        body = body[:start] + replacement + body[end:]
    return body


def check1_text(body):
    """The text check 1 reads: the heredoc-stripped command, with the pattern words of every search
    command blanked (Kc37755f0). Unchanged, byte for byte, when no segment is a search command with a
    pattern word."""
    body = remote_search_view(body)
    segments = shell_segments(body)
    skips = [search_pattern_indices(words) for words in segments]
    if not any(skips):
        return body
    return "\n".join(" ".join(word for j, word in enumerate(words) if j not in skip)
                     for words, skip in zip(segments, skips))


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
    return [(p, False) for p in paths] + tokens_marked(rest, whole_globs=True)


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
            tokens += tokens_marked(" ".join(words), whole_globs=True)
            continue
        skip = pattern_operand(words)
        command_index, _ = segment_command(words)
        for index, word in enumerate(words):
            if command_index is not None and index < command_index and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word):
                _, error = ssh_literal(word)
                if error is None:
                    continue              # A literal environment value is data, not a local read.
            if index != skip:
                tokens += quoted_tokens_marked(word)
    return tokens


# The characters `tokens_marked` cuts a word at. The GLOB subset matters separately: a token left
# behind by cutting at `*`, `?`, `[` or `]` is still a PATH (the deepest directory a glob cannot
# escape, D33), while a token left behind by cutting at any other metacharacter is a pattern
# FRAGMENT — half of an awk/sed/perl program, not a file name (review F2, register 2026-09-12).
_CUT_CHARS = "|;&<>()`$*?[]{}=,"
_GLOB_CUTS = "*?[]"


def tokens_marked(command, whole_globs=False):
    """(token, fragment) for every path-ish token: quote characters dropped and the metacharacters
    above turned into separators, so `--file=/etc/x` and `"/etc/x"` both yield /etc/x.

    `fragment` is True when a NON-GLOB metacharacter stood immediately beside the token, i.e. the
    token is the residue of cutting a longer word rather than a word the shell would pass. That is
    distinction between a whole path operand, which the grants must cover, and a token left
    by splitting shell syntax. Cutting at a glob character alone does NOT make a
    fragment, so `cat /etc/*.md` still tests `/etc/` and denies.

    `whole_globs` (the read checks, Kef9c30da): a glob character does not cut the word. The word is
    read WHOLE and judged by `glob_bound`, its deepest literal directory, as `cut_glob` states:
    `ls -d /x/*/` tests `/x/`, never a lone `/` left after the `*`, and `/x/*/f.md` tests `/x/`, never
    `/f.md`. A word `glob_bound` cannot bound keeps the split reading below. Check 1 does not use this
    mode: its test is on names, and the split reading is what shows it a name inside a glob."""
    # A URL is not a filesystem path and its remnants must not be read as one. `https://[2001:db8::1]/x`
    # cuts at the brackets and would leave `/x` standing as an absolute path token, which check 4 then
    # denied even under a grant naming that host (review N3). No filesystem path carries `://`, so the
    # whole URL run is blanked here; the network check reads the raw text and owns the host itself.
    text = re.sub(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s'\"]*", " ", unquote(command))
    cuts = "".join(ch for ch in _CUT_CHARS if ch not in _GLOB_CUTS) if whole_globs else _CUT_CHARS
    out, buf, left = [], [], False

    def close(right):
        token = "".join(buf)
        del buf[:]
        if whole_globs and any(ch in token for ch in _GLOB_CUTS):
            bound = glob_bound(token)
            if bound is not None:
                out.append((bound, left or right))
                return
            parts = tokens_marked(token)  # the split reading, for a word with no bound
            if parts and token[0] not in _GLOB_CUTS:
                parts[0] = (parts[0][0], parts[0][1] or left)
            if parts and token[-1] not in _GLOB_CUTS:
                parts[-1] = (parts[-1][0], parts[-1][1] or right)
            out.extend(parts)
            return
        out.append((token, left or right))

    for ch in text:
        if ch in cuts:
            nonglob = ch not in _GLOB_CUTS
            if buf:
                close(nonglob)
            left = nonglob
            continue
        if ch.isspace():
            if buf:
                close(False)
            left = False
            continue
        buf.append(ch)
    if buf:
        close(False)
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


CURRENT_DIRECTORY = object()


def command_base_segments(text, initial_base=CURRENT_DIRECTORY):
    """Pair each segment with its preceding controlling literal directory.

    Resolution never tests permissions. Only an existing absolute literal `cd ... &&`
    establishes a new base. Ambiguous changes leave subsequent relative paths unresolved;
    earlier segments retain their own base. Subshell directory changes are not modelled.
    """
    segments = ssh_shell_words(text)
    base = os.getcwd() if initial_base is CURRENT_DIRECTORY else initial_base
    has_cd = any(segment_command([word[0] for word in segment])[1] == "cd"
                 for segment in segments)
    subshell = has_cd and bool(re.search(r"[()]", strip_quoted(text)))
    previous_end = 0
    stable_base = base
    seen_cd, or_chain = False, False
    for number, segment in enumerate(segments):
        start, end = segment[0][1], segment[-1][2]
        preceding_text = text[previous_end:start]
        preceding = preceding_text.strip() or ("\n" if "\n" in preceding_text else "")
        if preceding in (";", "\n", "&"):
            or_chain = False
        if "||" in preceding:
            or_chain = True
        if seen_cd and preceding in (";", "\n"):
            base = stable_base
        if subshell or (seen_cd and preceding in ("&", "||")):
            base = stable_base = None
        yield segment, base
        words = [word[0] for word in segment]
        index, client = segment_command(words)
        if client == "cd":
            seen_cd = True
            next_start = segments[number + 1][0][1] if number + 1 < len(segments) else len(text)
            following = text[end:next_start].strip()
            operands = words[index + 1:]
            if operands[:1] == ["--"]:
                operands = operands[1:]
            target, error = ssh_literal(operands[0]) if len(operands) == 1 else (None, "missing directory")
            if (not subshell and not or_chain and following == "&&" and preceding not in ("|", "|&", "&")
                    and not error and os.path.isabs(target) and os.path.isdir(target)):
                base = norm(target)
                # Preserve the established existing-directory premise for an unconditional
                # literal cd; a conditionally skipped cd cannot outlive its AND-list.
                stable_base = base if preceding in ("", ";", "\n") else None
            else:
                base = stable_base = None
        previous_end = end


def resolve_command_path(path, base):
    """An absolute path or a relative path against a known base; None never grants access."""
    expanded = os.path.expanduser(path)
    if os.path.isabs(expanded):
        return expanded
    return os.path.join(base, path) if base is not None else None


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


SSH_FAMILY = frozenset({"ssh", "scp", "sftp", "rsync"})
SHELL_PROGRAMS = frozenset({"sh", "bash", "zsh", "ksh", "dash"})


def ssh_shell_words(text):
    """Segments of (raw word, start, end), retaining quotes and local evaluation.

    This bounded lexer never evaluates text. A substitution stays in its word so that
    the literal reader can refuse it, rather than losing its shell provenance.
    """
    segments, words = [], []
    i, size = 0, len(text)
    while i < size:
        if text[i].isspace() and text[i] != "\n":
            i += 1
            continue
        if text[i] in ";&|\n()":
            if words:
                segments.append(words)
                words = []
            i += 1
            continue
        start = i
        if text[i] in "<>":
            while i < size and text[i] in "<>&0123456789-":
                i += 1
        else:
            quote, depth = None, 0
            while i < size:
                ch = text[i]
                if ch == "\\" and quote != "'":
                    i = min(i + 2, size)
                    continue
                if quote:
                    if ch == quote:
                        quote = None
                    i += 1
                    continue
                if ch in "'\"`":
                    quote = ch
                    i += 1
                    continue
                if text.startswith("$(", i):
                    depth += 1
                    i += 2
                    continue
                if depth:
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                    i += 1
                    continue
                if ch.isspace() or ch in ";&|()<>":
                    break
                i += 1
        words.append((text[start:i], start, i))
    if words:
        segments.append(words)
    return segments


def ssh_literal(raw, remote_data=False):
    """Decode a protected shell word; refuse unresolved local evaluation.

    Single quotes protect every byte. Double quotes protect glob syntax but not
    command substitution. Only remote data after a fixed SSH host may retain simple
    double-quoted parameters: their substituted text has no local file or program
    effect. The returned parameter spelling is never used to resolve a local path.
    Unquoted expansion syntax is deliberately not evaluated.
    """
    value, quote, i = [], None, 0
    while i < len(raw):
        ch = raw[i]
        if quote == "'":
            if ch == "'":
                quote = None
            else:
                value.append(ch)
        elif ch == "\\":
            if i + 1 >= len(raw):
                return None, "unresolved trailing shell escape"
            nxt = raw[i + 1]
            if quote == '"' and nxt not in '$`"\\\n':
                value.append("\\")
            if nxt != "\n":
                value.append(nxt)
            i += 1
        elif ch in "'\"" and (quote is None or ch == quote):
            quote = None if quote else ch
        elif ch == "$" and quote == '"' and remote_data:
            parameter = re.match(r"\$(?:[A-Za-z_][A-Za-z0-9_]*|[0-9@*#?$!-]|"
                                 r"\{(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+|[@*#?$!-])\})", raw[i:])
            if parameter is None:
                return None, "unresolved local evaluation in `%s`" % raw
            value.append(parameter.group(0))
            i += len(parameter.group(0)) - 1
        elif ch in "$`" or (quote is None and ch in "*?[]{}~!"):
            return None, "unresolved local evaluation in `%s`" % raw
        else:
            value.append(ch)
        i += 1
    if quote:
        return None, "unresolved unterminated shell quote"
    return "".join(value), None


def ssh_local_io(words, arg_indices=None):
    """Separate shell I/O before identifying any remote operands."""
    args, reads, writes, errors = [], [], [], []
    i = 0
    while i < len(words):
        raw = words[i]
        i += 1
        if not re.match(r"^[0-9]*[<>]", raw):
            # The lexer may leave an fd number just before its operator.
            if raw.isdigit() and i < len(words) and re.match(r"^[<>]", words[i]):
                continue
            args.append(raw)
            if arg_indices is not None:
                arg_indices.append(i - 1)
            continue
        op = re.sub(r"^[0-9]+", "", raw)
        if re.fullmatch(r"[<>]&[0-9-]+", op):
            continue
        if op not in ("<", ">", ">>", "<<", "<<-", "<<<"):
            errors.append("unresolved local redirection `%s`" % raw)
            continue
        if i == len(words):
            errors.append("missing local redirection target for `%s`" % raw)
            continue
        target, error = ssh_literal(words[i])
        i += 1
        if error:
            errors.append(error)
        elif not target:
            errors.append("missing local redirection target for `%s`" % raw)
        elif op == "<":
            reads.append(("shell input", target))
        elif op in (">", ">>"):
            writes.append(("shell redirection", target))
        # Here-doc delimiters and literal here-strings are data, not file paths.
    return args, reads, writes, errors


def ssh_host(value, port=False):
    """A literal host/userinfo authority, including bracketed IPv6."""
    if "@" in value:
        user, value = value.rsplit("@", 1)
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", user):
            return None
    if value.startswith("["):
        match = re.fullmatch(r"\[([0-9A-Fa-f:.]+)\](?::([0-9]+))?", value)
        if not match or (match.group(2) and not port):
            return None
        return match.group(1)
    if port and ":" in value:
        value, sep, number = value.rpartition(":")
        if not sep or not number.isdigit():
            return None
    return value.lower() if re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", value) else None


def ssh_endpoint(value, client):
    """Return (host, local path, error); never call unrecognised remote syntax local."""
    if "://" in value:
        scheme, rest = value.split("://", 1)
        if (client == "rsync" and scheme == "rsync") or (client in {"scp", "sftp"} and scheme == client):
            authority, slash, path = rest.partition("/")
            host = ssh_host(authority, port=True)
            if host and (slash or client == "sftp"):
                return host, None, None
        return None, None, "unresolved %s URI endpoint `%s`" % (client, value)
    # An explicit relative/absolute local path may itself contain a colon.
    if value.startswith(("/", "./", "../")):
        return None, value, None
    match = re.match(r"^((?:[^@/:]+@)?\[[^\]]+\]|[^/:]+)(::?)(.*)$", value, re.S)
    if match:
        host = ssh_host(match.group(1))
        if host and (match.group(2) == ":" or client == "rsync"):
            return host, None, None
        return None, None, "unresolved %s remote endpoint `%s`" % (client, value)
    if ":" in value or "[" in value or "]" in value:
        return None, None, "unresolved %s remote endpoint `%s`" % (client, value)
    if client == "sftp":
        host = ssh_host(value)
        return (host, None, None) if host else (None, None, "unresolved sftp host `%s`" % value)
    return None, value, None


# Closed option grammars: an absent entry is an unresolved effect, never an ignored flag.
SSH_OPTIONS = {
    "ssh": (set("46AaCfGgKkMNnqsTtVvXxYy"), set("BbcDEeFIiJLlmOoPpQRSWw")),
    "scp": (set("346ABCOpqRrsTv"), set("cDFiJloPSX")),
    "sftp": (set("46aACfpqrv"), set("BbcDFiJloPRSsX")),
}
SSH_READ_SETTINGS = frozenset({"identityfile", "certificatefile", "userknownhostsfile", "globalknownhostsfile"})
SSH_DATA_SETTINGS = frozenset({
    "batchmode", "stricthostkeychecking", "connecttimeout", "connectionattempts",
    "serveraliveinterval", "serveralivecountmax", "loglevel", "identitiesonly",
    "preferredauthentications", "passwordauthentication", "pubkeyauthentication",
    "compression", "tcpkeepalive", "requesttty", "addressfamily", "port", "user",
    "hostkeyalgorithms", "kexalgorithms", "ciphers", "macs", "numberofpasswordprompts",
    "forwardagent", "forwardx11", "exitonforwardfailure", "clearallforwardings",
})
RSYNC_DATA_LONG = frozenset({"--bwlimit", "--timeout", "--contimeout", "--port", "--block-size",
                            "--max-size", "--min-size", "--chmod", "--usermap", "--groupmap",
                            "--chown", "--exclude", "--include", "--out-format", "--info", "--debug"})
RSYNC_FLAGS_LONG = frozenset({"--archive", "--recursive", "--verbose", "--quiet", "--compress",
                             "--progress", "--partial", "--delete", "--delete-before", "--delete-after",
                             "--delete-during", "--delete-delay", "--delete-excluded", "--dry-run",
                             "--checksum", "--times", "--perms", "--owner", "--group", "--links",
                             "--hard-links", "--numeric-ids", "--stats", "--human-readable",
                             "--itemize-changes", "--whole-file", "--update", "--ignore-existing",
                             "--existing", "--size-only", "--inplace", "--append", "--append-verify",
                             "--no-inc-recursive", "--protect-args", "--secluded-args"})


def ssh_config_paths(text, key):
    """Accept only a configuration spelling whose filenames need no client decoding.

    The outer shell has already decoded -o's argument. Retained quotes and escapes
    belong to SSH's different configuration grammar, not to the local filename.
    Refuse them rather than turn a quoted absolute path into a relative one. Only
    known-host settings accept a list; identity and certificate settings take one
    filename. The admitted separators are ASCII spaces/tabs and one optional '='.
    """
    match = re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(?:[ \t]*=[ \t]*|[ \t]+)(.*)", text, re.S)
    val = match.group(1).strip(" \t") if match else ""
    if (not val or any(ch in val for ch in "\"'\\%$~`*?[]{}#=")
            or any((ch.isspace() and ch not in " \t") or ord(ch) < 32 and ch != "\t"
                   or ord(ch) == 127 for ch in val)):
        return [], "unresolved ssh -o %s option file configuration grammar `%s`" % (key, text)
    paths = re.split(r"[ \t]+", val)
    if key in {"identityfile", "certificatefile"} and len(paths) != 1:
        return [], "unresolved ssh -o %s option file: expected one filename" % key
    return paths, None


def ssh_family_info(words, remote_indices=None):
    """One segment, four results: connection hosts, local reads, local writes, unresolved syntax.

    Every returned path is already a decoded literal; the caller applies the grants.
    Remote data is exempt only after local shell effects and client options are classified.
    """
    arg_indices = []
    args, reads, writes, errors = ssh_local_io(words, arg_indices=arg_indices)
    index, client = segment_command(args)
    hosts = []
    if client not in SSH_FAMILY:
        return hosts, reads, writes, errors
    for raw in args[:index]:
        _, error = ssh_literal(raw)
        if error:
            errors.append(error)
    program, error = ssh_literal(args[index])
    if error:
        errors.append(error)
    elif "/" in program:
        reads.append(("client program", program))

    def value(raw, remote_data=False):
        result, error = ssh_literal(raw, remote_data=remote_data)
        if error:
            errors.append(error)
        return result

    def connection(authority, option, port=False):
        host = ssh_host(authority, port=port)
        if host:
            hosts.append(host)
        else:
            errors.append("unresolved %s host `%s`" % (option, authority))

    def option_path(origin, path, writing=False):
        # These options receive argv filenames, with no configuration unquoting.
        # Keep literal quote/backslash/space bytes. The shared resolver expands
        # leading '~', so refuse that spelling rather than check another filename.
        if not path or path.startswith("~") or any(ord(ch) < 32 or ord(ch) == 127 for ch in path):
            errors.append("unresolved %s option file `%s`" % (origin, path))
        else:
            (writes if writing else reads).append((origin, path))

    def setting(text):
        parts = re.split(r"[=\s]+", text, maxsplit=1)
        if len(parts) != 2 or not parts[1]:
            errors.append("missing ssh -o option value")
            return
        key, val = parts[0].lower(), parts[1]
        if key == "proxyjump":
            if val != "none":
                for jump in val.split(","):
                    connection(jump, "jump", port=True)
        elif key == "hostname":
            connection(val, "effective destination")
        elif key in SSH_READ_SETTINGS:
            paths, error = ssh_config_paths(text, key)
            if error:
                errors.append(error)
            reads.extend(("ssh -o " + key, path) for path in paths)
        elif key in SSH_DATA_SETTINGS:
            return
        else:
            errors.append("unresolved ssh -o %s option (configuration or local program effects)" % parts[0])

    operands, i, options = [], index + 1, True
    while i < len(args):
        raw = args[i]
        i += 1
        word = value(raw)
        if word is None:
            continue
        if options and word == "--":
            options = False
            continue
        if not options or not word.startswith("-") or word == "-":
            operands.append(word)
            if client in {"ssh", "sftp"}:
                # SSH stops option parsing at its destination. These are remote words.
                for remote in args[i:]:
                    value(remote, remote_data=(client == "ssh"))
                if client == "ssh" and remote_indices is not None:
                    remote_indices.extend(arg_indices[i:])
                if client == "sftp" and i < len(args):
                    errors.append("unresolved extra sftp operands")
                break
            continue
        if client == "rsync":
            if word.startswith("--"):
                name, equals, supplied = word.partition("=")
                if name in RSYNC_FLAGS_LONG and not equals:
                    continue
                if name not in RSYNC_DATA_LONG | {"--rsh", "--rsync-path", "--log-file", "--files-from", "--include-from", "--exclude-from", "--password-file"}:
                    errors.append("unresolved rsync option `%s`" % name)
                    continue
                if not equals:
                    if i >= len(args):
                        errors.append("missing rsync option value for `%s`" % name)
                        continue
                    supplied = value(args[i])
                    i += 1
            else:
                supplied, name = None, None
                for j, letter in enumerate(word[1:], 1):
                    if letter in "eBfMT":
                        name = {"e": "--rsh", "B": "--block-size"}.get(letter, "unsupported -" + letter)
                        supplied = word[j + 1:]
                        if not supplied:
                            if i >= len(args):
                                errors.append("missing rsync option value for `-%s`" % letter)
                                break
                            supplied = value(args[i])
                            i += 1
                        break
                    if letter not in "avzrtplogDHAXSxWnqcuIRLPihs":
                        errors.append("unresolved rsync option `-%s`" % letter)
                if name is None:
                    continue
            if supplied is None:
                continue
            if name == "--rsh":
                # Rsync splits a command string using its own grammar, not a shell.
                # Admit only the common literal subset; quoting, escapes, operators
                # and expansions cannot be decoded exactly by the shell reader.
                if (not supplied or any(ch in supplied for ch in "\"'\\$`;&|()<>*?[]{}~!")
                        or any((ch.isspace() and ch != " ") or ord(ch) < 32
                               or ord(ch) == 127 for ch in supplied)):
                    errors.append("unresolved rsync --rsh transport grammar")
                    continue
                transport = ssh_shell_words(supplied)
                if len(transport) != 1 or not transport[0] or transport[0][0][0] != "ssh":
                    errors.append("unresolved rsync --rsh local program (only plain ssh is supported)")
                else:
                    # A sentinel supplies the destination, which rsync supplies at runtime.
                    transport_words = [item[0] for item in transport[0]] + ["transport.invalid"]
                    remote = []
                    hs, rs, ws, es = ssh_family_info(transport_words, remote_indices=remote)
                    if remote or not hs or hs[-1] != "transport.invalid":
                        es.append("unresolved rsync --rsh destination or missing option value")
                    # The destination is appended last by the SSH classifier. Remove
                    # only that occurrence: a real option host may have the same name.
                    hosts.extend(hs[:-1] if hs and hs[-1] == "transport.invalid" else hs)
                    reads.extend(rs)
                    writes.extend(ws)
                    errors.extend(es)
            elif name in {"--files-from", "--include-from", "--exclude-from", "--password-file"}:
                if supplied.startswith(":") or (name == "--files-from" and ":" in supplied):
                    errors.append("unresolved rsync option file `%s`" % supplied)
                else:
                    option_path("rsync " + name, supplied)
            elif name == "--log-file":
                option_path("rsync --log-file", supplied, writing=True)
            elif name == "--rsync-path":
                pass                      # The remote server program is remote data.
            elif name not in RSYNC_DATA_LONG:
                errors.append("unresolved rsync option `%s`" % name)
            continue
        flags, taking = SSH_OPTIONS[client]
        if word.startswith("--"):
            errors.append("unresolved %s option `%s`" % (client, word))
            continue
        for j, letter in enumerate(word[1:], 1):
            if letter in taking:
                supplied = word[j + 1:]
                if not supplied:
                    if i >= len(args):
                        errors.append("missing %s option value for `-%s`" % (client, letter))
                        break
                    supplied = value(args[i])
                    i += 1
                if supplied is None:
                    break
                if letter == "o":
                    setting(supplied)
                elif letter == "J":
                    for jump in supplied.split(","):
                        connection(jump, "jump", port=True)
                elif letter == "i" or (client == "sftp" and letter == "b"):
                    if letter == "i" and any(c in supplied for c in "%$~"):
                        errors.append("unresolved ssh option file `%s`" % supplied)
                    else:
                        option_path(client + " -" + letter, supplied)
                elif client == "ssh" and letter == "E":
                    option_path("ssh -E log", supplied, writing=True)
                elif letter == "F":
                    errors.append("unresolved %s -F configuration file" % client)
                elif (client == "ssh" and letter in "DILORSWw") or (client in {"scp", "sftp"} and letter in "DSs"):
                    errors.append("unresolved %s -%s option (local program or further connection)" % (client, letter))
                elif letter not in ("BbcelmPpQ" if client == "ssh" else "BclPRX"):
                    errors.append("unresolved %s -%s option" % (client, letter))
                break
            if letter not in flags:
                errors.append("unresolved %s option `-%s`" % (client, letter))
    if client == "ssh":
        if not operands:
            errors.append("unresolved ssh: missing destination host")
        else:
            destination = operands[0]
            if destination.startswith("ssh://"):
                connection(destination[len("ssh://"):].rstrip("/"), "destination", port=True)
            else:
                connection(destination, "destination")
    elif client == "sftp":
        if not operands:
            errors.append("unresolved sftp: missing destination host")
        else:
            host, _, error = ssh_endpoint(operands[0], client)
            if error:
                errors.append(error)
            elif host:
                hosts.append(host)
            else:
                errors.append("unresolved sftp destination host")
    else:
        if len(operands) < 2:
            errors.append("unresolved %s: missing source or destination endpoint" % client)
        for j, operand in enumerate(operands):
            host, path, error = ssh_endpoint(operand, client)
            if error:
                errors.append(error)
            elif host:
                hosts.append(host)
            elif path:
                (writes if j == len(operands) - 1 else reads).append((client + " endpoint", path))
    return hosts, reads, writes, errors


def ssh_command_view(text, initial_base=CURRENT_DIRECTORY):
    """Mask classified remote segments, retaining independent local command checks.

    Returns the local view and the four classifier collections. Shell program strings
    are recursively read only when they contain a supported client invocation.
    """
    edits, hosts, reads, writes, errors = [], [], [], [], []
    active = False
    def local_paths(paths, base, kind):
        resolved = []
        for origin, path in paths:
            target = resolve_command_path(path, base)
            if target is None:
                errors.append("unresolved local %s base after compound or missing cd" % kind)
            else:
                resolved.append((origin, target))
        return resolved

    for segment, base in command_base_segments(text, initial_base):
        words = [item[0] for item in segment]
        args, _, _, _ = ssh_local_io(words)
        index, client = segment_command(args)
        if index is not None:
            for raw in args[:index]:
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", raw):
                    _, error = ssh_literal(raw)
                    if error:
                        errors.append(error)
        if client in SSH_FAMILY:
            hs, rs, ws, es = ssh_family_info(words)
            hosts.extend(hs)
            reads.extend(local_paths(rs, base, "read"))
            writes.extend(local_paths(ws, base, "write"))
            errors.extend(es)
            edits.append((segment[0][1], segment[-1][2], ":"))
            active = True
        elif client in SHELL_PROGRAMS and index is not None:
            tail = args[index + 1:]
            flag = re.match(r"^-[lexu]*c(.*)$", tail[0], re.S) if tail else None
            if flag and (flag.group(1) or len(tail) >= 2):
                raw_payload = flag.group(1) or tail[1]
                payload, error = ssh_literal(raw_payload)
                if payload is not None:
                    view, hs, rs, ws, es, used = ssh_command_view(payload, base)
                    if used:
                        hosts.extend(hs)
                        reads.extend(rs)
                        writes.extend(ws)
                        errors.extend(es)
                        wrapper, wrapper_error = ssh_literal(args[index])
                        if wrapper_error:
                            errors.append(wrapper_error)
                        elif "/" in wrapper:
                            reads.extend(local_paths([("client program", wrapper)], base, "read"))
                        for raw in tail[1 if flag.group(1) else 2:]:
                            _, extra_error = ssh_literal(raw)
                            if extra_error:
                                errors.append(extra_error)
                        _, outer_rs, outer_ws, outer_es = ssh_local_io(words)
                        reads.extend(local_paths(outer_rs, base, "read"))
                        writes.extend(local_paths(outer_ws, base, "write"))
                        errors.extend(outer_es)
                        # Flatten only wrappers with no directory changes: their cwd is inherited.
                        if any(segment_command([t[0] for t in s])[1] == "cd" for s in ssh_shell_words(payload)):
                            errors.append("unresolved shell wrapper write base after cd")
                        edits.append((segment[0][1], segment[-1][2], view))
                        active = True
                elif any(ssh_command_view(p)[5] for p in interpreter_payloads(" ".join(args))):
                    errors.append(error or "unresolved shell wrapper local evaluation")
            else:
                for payload in interpreter_payloads(" ".join(args)):
                    if ssh_command_view(payload)[5]:
                        errors.append("unresolved ssh-family shell wrapper grammar")
        elif client in INTERPRETERS:
            for payload in interpreter_payloads(" ".join(args)):
                if ssh_command_view(payload)[5]:
                    errors.append("unresolved ssh-family interpreter wrapper grammar")
        elif args and os.path.basename(unquote_token(args[0])) in PREFIXES:
            if any(unquote_token(raw) in SSH_FAMILY for raw in args[1:]):
                errors.append("unresolved ssh-family command wrapper options")
    for start, end, replacement in reversed(edits):
        text = text[:start] + replacement + text[end:]
    return text, hosts, reads, writes, errors, active


def ssh_heredoc_error(command):
    """An unquoted local heredoc can substitute even when its consumer is remote."""
    lines, i = command.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        i += 1
        markers = heredoc_markers(line)
        if not markers:
            continue
        words = [word[0] for segment in ssh_shell_words(line) for word in segment]
        raw_markers = [words[j + 1] for j, word in enumerate(words[:-1]) if word in ("<<", "<<-")]
        if len(raw_markers) != len(markers):
            return "unresolved local heredoc delimiter grammar"
        for raw, (marker, dash) in zip(raw_markers, markers):
            protected = any(ch in raw for ch in "'\"\\")
            ended = False
            while i < len(lines):
                text = lines[i]
                i += 1
                if (text.lstrip("\t") if dash else text) == marker:
                    ended = True
                    break
                if not protected:
                    j = 0
                    while j < len(text):
                        if text[j] == "\\":
                            j += 2
                            continue
                        if text[j] in "$`":
                            return "unresolved local evaluation in unquoted heredoc input"
                        j += 1
            if not ended:
                return "unresolved unterminated local heredoc input"
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


# Kb2a266d1: the options of curl and wget whose VALUE names a local file or a datum (an output file,
# a header, a method, a time), never a machine the client connects to. Such a value is skipped as a
# host candidate, so `curl -o x.md https://h/x` addresses `h` alone. An ALLOWLIST: an option missing
# from it keeps the old reading (its value may be read as a host, which fails closed), and every
# option whose value is an endpoint — `--url`, a proxy, `--connect-to`, `--resolve`, `--doh-url`,
# wget's `-e` (a wgetrc command, which can set a proxy) — is left off it deliberately. Configuration
# and address-list inputs are refused by NETWORK_INDIRECT_OPTIONS, not skipped as harmless data.
NETWORK_VALUE_FLAGS = {
    "curl": {"short": set("oDcbTdFHAeuXwmrCyYzQEtU"),
             "long": {"--output", "--output-dir", "--dump-header", "--cookie", "--cookie-jar",
                      "--upload-file", "--data", "--data-ascii", "--data-binary",
                      "--data-raw", "--data-urlencode", "--json", "--form", "--form-string",
                      "--header", "--proxy-header", "--user-agent", "--referer", "--user",
                      "--proxy-user", "--request", "--write-out", "--max-time",
                      "--connect-timeout", "--range", "--continue-at", "--speed-time",
                      "--speed-limit", "--time-cond", "--quote", "--cert", "--cert-type", "--key",
                      "--key-type", "--cacert", "--capath", "--crlfile", "--telnet-option",
                      "--retry", "--retry-delay", "--retry-max-time", "--limit-rate",
                      "--max-filesize", "--max-redirs", "--stderr", "--trace", "--trace-ascii",
                      "--libcurl", "--etag-save", "--etag-compare", "--hsts",
                      "--netrc-file", "--expect100-timeout", "--keepalive-time",
                      "--oauth2-bearer", "--url-query", "--variable"}},
    "wget": {"short": set("OoaPUtTwQ"),
             "long": {"--output-document", "--output-file", "--append-output",
                      "--directory-prefix", "--user-agent", "--header",
                      "--post-data", "--post-file", "--body-data", "--body-file", "--method",
                      "--tries", "--timeout", "--wait", "--quota", "--limit-rate", "--user",
                      "--password", "--http-user", "--http-password", "--load-cookies",
                      "--save-cookies", "--ca-certificate", "--certificate", "--private-key",
                      "--referer", "--level", "--accept", "--reject", "--hsts-file",
                      "--rejected-log", "--warc-file"}},
}

# These values carry more addresses or settings, so a URL elsewhere in the command proves
# nothing about their destinations. --alt-svc is also a file write, but check N refuses it first.
NETWORK_INDIRECT_OPTIONS = {
    "curl": {"-K", "--config", "--alt-svc"},
    "wget": {"-i", "--input-file", "--config", "-e", "--execute"},
}
NETWORK_FILE_OPTIONS = {
    "curl": {"-o", "--output", "--output-dir", "-D", "--dump-header", "-c", "--cookie-jar",
             "--trace", "--trace-ascii", "--stderr", "--libcurl", "--etag-save", "--hsts",
             "--alt-svc"},
    "wget": {"-O", "--output-document", "-o", "--output-file", "-a", "--append-output",
             "-P", "--directory-prefix", "--save-cookies", "--hsts-file", "--rejected-log",
             "--warc-file"},
}
# Only options for which '-' denotes standard output get that exemption. A directory named '-'
# and wget's log options still name files. '%' denotes standard error for curl's trace options.
NETWORK_STDOUT_OPTIONS = {
    "curl": {"-o", "--output", "-D", "--dump-header", "-c", "--cookie-jar", "--trace",
             "--trace-ascii", "--stderr", "--libcurl", "--etag-save"},
    "wget": {"-O", "--output-document"},
}


def network_client_options(base, words):
    """Literal option names and values, including glued values and short clusters.

    This reading serves the deny/write checks. The narrower network_value_skips reading is
    unchanged: a clustered option's separated value still remains a host candidate. Known
    non-output values are consumed too, so a header or user agent containing '-K' is data.
    """
    def value_of(raw):
        try:
            parsed = record_words(raw)
        except ValueError:
            return raw                       # malformed/expanded text stays visible, fail-closed
        return parsed[0][1] if len(parsed) == 1 and parsed[0][0] == "word" else raw

    table = NETWORK_VALUE_FLAGS[base]
    takes = ({"-" + letter for letter in table["short"]} | table["long"] |
             NETWORK_INDIRECT_OPTIONS[base] | NETWORK_FILE_OPTIONS[base])
    if base == "curl":
        takes |= {"-x", "--proxy", "--preproxy", "--url", "--connect-to", "--resolve", "--doh-url"}
    options, i = [], 0
    while i < len(words):
        raw = words[i]
        i += 1
        if raw[:1] in "<>":
            if "&" not in raw:
                i += 1
            continue
        word = value_of(raw)
        if word == "--":
            break
        if not word.startswith("-") or word == "-":
            continue
        if word.startswith("--"):
            name, sep, value = word.partition("=")
            if not sep:
                value = None
                if name in takes and i < len(words):
                    value = value_of(words[i])
                    i += 1
            options.append((name, value))
            continue
        for position in range(1, len(word)):
            name, value = "-" + word[position], None
            if name in takes:
                value = word[position + 1:] or None
                if value is None and i < len(words):
                    value = value_of(words[i])
                    i += 1
                options.append((name, value))
                break
            options.append((name, value))
    return options


def network_client_calls(body, command):
    """Curl/wget options in shell segments and in the interpreter payloads check N already reads."""
    calls = []
    for text in [body] + list(interpreter_payloads(command)):
        for words in shell_segments(text):
            index, base = segment_command(words)
            if base in NETWORK_VALUE_FLAGS:
                calls.append((base, network_client_options(base, words[index + 1:])))
    return calls


def network_file_targets(calls):
    """File/directory targets plus any unresolved write format. Never read config or run a client.

    All named outputs are tested, even when a later flag overrides them. Directory outputs bound
    server-chosen names. Curl's final output directory within a transfer prefixes explicit output
    names regardless of option order, including names beginning with '/'. WARC names have generated
    suffixes, so their parent must be writable.
    """
    transfers = []
    for base, options in calls:
        current = []
        for option in options:
            if base == "curl" and option[0] in {"--next", "-:"}:
                transfers.append((base, current))
                current = []
            else:
                current.append(option)
        transfers.append((base, current))
    targets = []
    for base, options in transfers:
        directory = "."
        output_directory = None
        if base == "curl":
            for name, value in options:
                if name == "--output-dir":
                    output_directory = value
            if output_directory is not None:
                directory = output_directory
        default_name = base == "wget"
        for name, value in options:
            label = base + " " + name
            if name in NETWORK_FILE_OPTIONS[base]:
                if value is None or (not value and name != "--hsts"):
                    return [], label + " has no literal file target — denied as unresolvable"
                if base == "wget" and name in {"-P", "--directory-prefix"}:
                    directory = value
                if base == "wget" and name in {"-O", "--output-document"}:
                    default_name = False
                if value == "-" and name in NETWORK_STDOUT_OPTIONS[base]:
                    continue
                if base == "curl" and ((name == "--hsts" and not value) or
                                       (name in {"--trace", "--trace-ascii"} and value == "%")):
                    continue
                # URL-glob captures in output names cannot be resolved from this option alone.
                if base == "curl" and name in {"-o", "--output"} and re.search(r"#\d", value):
                    return [], label + " contains a URL-glob capture — denied as unresolvable"
                if name == "--warc-file" and ("$" in value or "`" in value):
                    return [], label + " prefix is computed — denied as unresolvable"
                target = (os.path.dirname(value) or ".") if name == "--warc-file" else value
                if base == "curl" and name in {"-o", "--output"} and output_directory is not None:
                    # curl prefixes even an absolute filename: os.path.join would discard the
                    # directory in that case and test a different target from the client's.
                    target = output_directory + "/" + value
                targets.append((label, target))
            if base == "curl" and name in {"-O", "--remote-name", "--remote-name-all"}:
                default_name = True
            if base == "curl" and name in {"-w", "--write-out"}:
                if value is None or value.startswith("@") or "$" in value or "`" in value:
                    return [], label + " format is indirect or missing — denied as unresolvable"
                for directive in re.finditer(r"%output\{([^}]*)\}", value):
                    target = directive.group(1).removeprefix(">>")
                    if not target or any(char in target for char in "%{}"):
                        return [], label + " file target is computed — denied as unresolvable"
                    targets.append((label, target))
                if "%output{" in re.sub(r"%output\{[^}]*\}", "", value):
                    return [], label + " file directive is incomplete — denied as unresolvable"
        if default_name:
            targets.append((base + " download directory", directory))
    return targets, None


def network_value_skips(base, words):
    """The indices of words that are the separated VALUE of an allowlisted curl or wget option
    (`NETWORK_VALUE_FLAGS`): a lone short option (`-o x.md`) or a long one (`--output x.md`). A glued
    value (`-ox.md`, `--output=x.md`) is part of its dash-led word, which is never a host candidate
    anyway. A short CLUSTER (`-sSo x.md`) skips nothing: getopt may give an earlier letter the rest of
    the cluster as its value, so its next word keeps the old reading (a false deny, fail-closed)."""
    table = NETWORK_VALUE_FLAGS.get(base)
    skips = set()
    if table is None:
        return skips
    i = 0
    while i < len(words):
        word = unquote_token(words[i]).strip()
        i += 1
        if word == "--":
            break
        if not word.startswith("-") or word == "-":
            continue
        if word.startswith("--"):
            name, sep, _ = word.partition("=")
            if not sep and name in table["long"] and i < len(words):
                skips.add(i)
                i += 1
            continue
        if len(word) == 2 and word[1] in table["short"] and i < len(words):
            skips.add(i)
            i += 1
    return skips


def network_operand_hosts(text):
    """The bare hostnames a network CLIENT takes as operands (`curl evil.example.com https://ok/x`
    addresses both). Only operands of a network command count, and only those that carry a dot, no
    path separator, no `@` and no scheme, and that name nothing on disk. The separated value of an
    allowlisted curl or wget option is no operand (Kb2a266d1): `-o x.md` names a file."""
    hosts = []
    for words in shell_segments(text):
        index, base = segment_command(words)
        if base not in NETWORK_CMDS:
            continue
        operands = words[index + 1:]
        skips = network_value_skips(base, operands)
        for position, raw in enumerate(operands):
            if position in skips:
                continue
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


# The record writer has a closed argument grammar. These paths and options follow
# vault-writes.py: LOG_REL, REGISTER_REL, atomic_write and build_parser. Register writes
# read the followed leaf, lock the directory, create an unpredictable temporary sibling, then
# replace the directory entry. A file-only grant therefore cannot authorise a register operation.
# `register add` requires --why-not-fixed-now; `ideas annotate` is left out on purpose, so no
# lane gains IDEAS authority (the suite checks both against the writer's own parser).
RECORD_OPTIONS = {
    ("log-append",): (
        {"--vault", "--action", "--title", "--changed", "--conflicts"},
        {"--date", "--extra"}),
    ("register", "add"): (
        {"--vault", "--date", "--surface", "--symptom", "--cause", "--why-not-fixed-now", "--severity",
         "--status"},
        {"--where"}),
    ("register", "close"): (
        {"--vault", "--match", "--date", "--status"}, set()),
    ("register", "annotate"): (
        {"--vault", "--match", "--kind", "--note"}, {"--by", "--date"}),
}
RECORD_TARGETS = {"log-append": ("wiki", "log.md"),
                  "register": ("wiki", "developments", "known-issues.md")}
RECORD_NAME = "vault-writes.py"


class RecordWriterGrantError(ValueError):
    """An admitted writer operation lacks its target or temporary-directory grant."""


def record_words(text):
    """Literal shell words with source spans: (kind, value, start, end, literal).

    Single quotes preserve every byte. Double quotes remove a backslash only before
    dollar, backtick, double quote, backslash or newline. Adjacent spans concatenate;
    whitespace inside quotes remains significant. Expansions are marked, never run.
    Operators remain separate so exceptions can attach to argument occurrences.
    This is deliberately a bounded grammar, not a shell evaluator.
    """
    out, i = [], 0
    while i < len(text):
        if text[i] in " \t":
            i += 1
            continue
        if text[i] == "#":
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
            continue
        start = i
        if text[i] in ";&|\n<>()":
            i += 1
            if text[start:i] in ("&", "|") and text[i:i + 1] == text[start:i]:
                i += 1
            out.append(("op", text[start:i], start, i, True))
            continue
        value, quote, literal, quoted = [], None, True, False
        while i < len(text):
            ch = text[i]
            if quote == "'":
                if ch == "'":
                    quote = None
                else:
                    value.append(ch)
                i += 1
                continue
            if ch == "\\":
                if i + 1 == len(text):
                    raise ValueError("unfinished shell escape")
                nxt = text[i + 1]
                if quote == '"' and nxt not in '$`"\\\n':
                    value.append("\\")
                    i += 1
                    continue
                if nxt != "\n":
                    value.append(nxt)
                i += 2
                continue
            if quote == '"':
                if ch == '"':
                    quote = None
                else:
                    if ch in "$`":
                        literal = False
                    value.append(ch)
                i += 1
                continue
            if ch in "'\"":
                quote = ch
                quoted = True
                i += 1
                continue
            if ch in " \t\n;&|<>()":
                break
            # Expansion syntax outside quotes is unsupported, including zsh globbing,
            # history, brace and tilde expansion. Quoted spellings are ordinary data.
            if ch in "$`*?[]{}~!^":
                literal = False
            value.append(ch)
            i += 1
        if quote:
            raise ValueError("unfinished shell quote")
        if value or quoted:
            out.append(("word", "".join(value), start, i, literal))
    return out


def record_deployment():
    """Trusted vault and writer, from this checker's deployment, never from --vault.

    The head imports the checker in .claude/skills/delegate. lane.py init copies it
    into the lane home and records its source and both hashes in the adjacent init
    manifest. A copied checker needs that exact provenance and unchanged source bytes;
    an absent, malformed or stale manifest refuses the exception. The manifest has
    the same deployment trust as the hook itself, not command-supplied authority.
    """
    deployed = os.path.realpath(__file__)
    source = deployed

    def in_layout(path):
        return path.endswith(os.sep + os.path.join(".claude", "skills", "delegate", "lane-fence.py"))

    if not in_layout(source):
        manifest = os.path.join(os.path.dirname(deployed), ".lane-home-state.json")
        with open(manifest, encoding="utf-8") as handle:
            state = json.load(handle)
        entry = state["lane-fence.py"]
        source = entry["source"]
        if not isinstance(source, str) or not os.path.isabs(source):
            raise ValueError("invalid checker provenance")
        source = os.path.realpath(source)
        if not in_layout(source):
            raise ValueError("checker source is outside the deployment layout")
        with open(deployed, "rb") as handle:
            copied_sha = hashlib.sha256(handle.read()).hexdigest()
        with open(source, "rb") as handle:
            source_sha = hashlib.sha256(handle.read()).hexdigest()
        if not (copied_sha == source_sha == entry["src_sha"] == entry["out_sha"]):
            raise ValueError("checker provenance hashes disagree")
    delegate = os.path.dirname(source)
    vault = os.path.dirname(os.path.dirname(os.path.dirname(delegate)))
    writer = os.path.join(delegate, RECORD_NAME)
    # The deployed writer must be a real sibling, not a link escaping to another script.
    if os.path.realpath(writer) != writer or not os.path.isfile(writer):
        raise ValueError("deployed record writer is missing or redirected")
    return vault, writer


def record_python(program):
    """A Python executable in the hook's environment, not an arbitrary same-named file.

    Bare names use the first PATH match, then face the same identity check as absolute
    paths. System-bin launchers and the running checker's interpreter are supported;
    relative paths and a PATH shadow under a scratch directory are refused.
    """
    if os.sep not in program:
        for directory in os.get_exec_path():
            candidate = os.path.join(directory, program)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                program = candidate
                break
        else:
            return False
    if not os.path.isabs(program):
        return False
    if not re.fullmatch(r"python3(?:\.[0-9]+)?|python", os.path.basename(program)):
        return False
    lexical = os.path.abspath(program)
    if program != lexical:
        return False                      # do not collapse symlink/.. paths lexically
    system = os.path.dirname(lexical) + os.sep in SYSTEM_BIN
    current = lexical == os.path.abspath(sys.executable)
    return (system or current) and os.path.isfile(program) and os.access(program, os.X_OK)


def record_arguments(words, script_at, vault, writes):
    """Validate one verified invocation and return only its exempt argument spans.

    No abbreviations, unknown flags, duplicate scalar options or dynamic values.
    --extra alone is repeatable, matching argparse's append action. Help still needs
    a selected operation and one --vault with that operation's full write scope.
    Top-level help has no selected target and receives no exception.
    """
    args = words[script_at + 1:]
    key = tuple(w[1] for w in args[:2]) if args and args[0][1] == "register" else tuple(w[1] for w in args[:1])
    if key not in RECORD_OPTIONS:
        raise ValueError("unsupported record-writer operation")
    required, optional = RECORD_OPTIONS[key]
    values, spans = {}, [words[script_at]]
    i = len(key)
    while i < len(args):
        word = args[i]
        name, equals, value = word[1].partition("=")
        if name in ("--help", "-h", "--dry-run"):
            if equals or name in values:
                raise ValueError("malformed or repeated writer switch")
            values[name] = True
            i += 1
            continue
        if name not in required | optional:
            raise ValueError("unknown or abbreviated writer option")
        if name in values and name != "--extra":
            raise ValueError("repeated writer option")
        if equals:
            spans.append(word)
        else:
            i += 1
            # A value may open with "- " (a note, a symptom or a change line written as a list
            # item): no option string holds a space, so argparse never reads such a word as an
            # option and the writer takes it as a value. Any other leading dash still refuses.
            if i >= len(args) or (args[i][1].startswith("-") and not args[i][1].startswith("- ")):
                raise ValueError("missing writer option value")
            value = args[i][1]
            spans.append(args[i])
        values[name] = value
        i += 1
    root = values.get("--vault")
    if not root or not os.path.isabs(root) or os.path.realpath(root) != vault:
        raise ValueError("--vault must name the trusted vault literally and absolutely")
    if not (values.get("--help") or values.get("-h")) and required - values.keys():
        raise ValueError("missing required writer options")
    relative = RECORD_TARGETS[key[0]]
    target = os.path.join(root, *relative)
    if not within(target, writes):
        raise RecordWriterGrantError("record-writer target outside the write whitelist: " + target)
    if key != ("log-append",):
        directory = os.path.realpath(os.path.dirname(target))
        if not within(directory, writes):
            raise RecordWriterGrantError("register temporary-file directory outside the write whitelist: " + directory)
        # Directory coverage includes the replaced entry even when its followed leaf
        # points elsewhere; target coverage above separately checks that followed leaf.
    return spans


def record_writer_view(command, writes):
    """Mask admitted writer arguments; refuse only an admitted operation's missing grant.

    Only the verified script, root and typed data occurrences are masked. The caller
    still runs every ordinary check on every remaining segment, without wider roots.
    Compound syntax is limited to literal simple commands joined by ;, &&, || or |.
    Any other premise failure leaves the entire command unchanged with no reason, so
    ordinary checks decide it. Heredocs, substitutions, wrappers and unsupported grammar
    confer no exception; no segment is partially masked. No shell is executed here.
    """
    body = strip_heredocs(command)
    # A conservative hint survives adjacent quoting and escapes, including malformed
    # input. It is only a reason to try admission, never sufficient for an exception.
    hint = RECORD_NAME in re.sub(r"['\"\\]", "", body)
    try:
        words = record_words(body)
    except (ValueError, TypeError):
        return command, None
    # Also recognise an alias whose destination has the writer's name. Such an alias
    # gains no exception if it leads to a counterfeit script, even with reads.
    hint = hint or any(w[0] == "word" and os.path.isabs(w[1]) and "\x00" not in w[1]
                       and os.path.basename(os.path.realpath(w[1])) == RECORD_NAME for w in words)
    try:
        vault, writer = record_deployment()
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return command, None

    def writer_word(word):
        value = word[1]
        return (RECORD_NAME in value or
                (word[0] == "word" and os.path.isabs(value) and "\x00" not in value
                 and (os.path.realpath(value) == writer or
                      os.path.basename(os.path.realpath(value)) == RECORD_NAME)))

    if not hint and not any(writer_word(w) for w in words):
        return command, None
    try:
        if command != body:
            raise ValueError("heredocs with a writer invocation are unsupported")
        if any(not w[4] or "\x00" in w[1] for w in words):
            raise ValueError("writer commands require literal shell words")
        segments, current = [], []
        for word in words:
            if word[0] == "op":
                if word[1] not in (";", "&&", "||", "|", "\n"):
                    raise ValueError("unsupported shell structure around writer")
                if current:
                    segments.append(current)
                    current = []
                elif word[1] != "\n":
                    raise ValueError("missing command around writer separator")
            else:
                current.append(word)
        if current:
            segments.append(current)
        elif words and words[-1][1] in ("&&", "||", "|"):
            raise ValueError("unfinished writer pipeline or compound")
        def invokes_writer(segment):
            # A pathname reused as cat/ls/printf data is not an executable occurrence.
            # It keeps its ordinary read check, even beside an eligible writer call.
            return (writer_word(segment[0]) or
                    (os.path.basename(segment[0][1]) not in {"printf", "cat", "ls"}
                     and any(writer_word(w) for w in segment)))

        spans, grant_failure = [], None
        last_writer = max((i for i, s in enumerate(segments) if invokes_writer(s)), default=-1)
        has_pipe = any(w[0] == "op" and w[1] == "|" for w in words)
        for position, segment in enumerate(segments):
            first = segment[0][1]
            if (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", first) or first in PREFIXES
                    or first in {"cd", "export", "unset", "set", "typeset", "declare", "local",
                                 "readonly", "alias", "unalias", "hash", "eval", "source", "."}):
                raise ValueError("shell state changes or wrappers around writer are unsupported")
            if not invokes_writer(segment):
                companion = os.path.basename(first)
                if companion not in ({"printf", "cat", "ls", "tee"} | MUTATORS | NETWORK_CMDS):
                    raise ValueError("unsupported companion command around writer")
                if companion == "printf" and any(w[1].startswith("-v") for w in segment[1:]):
                    raise ValueError("printf variable assignment around writer is unsupported")
                if companion not in {"printf", "cat", "ls"} and (position < last_writer or has_pipe):
                    raise ValueError("a companion could change writer targets before execution")
                continue
            if os.path.isabs(first) and os.path.realpath(first) == writer:
                script_at = 0
                # The deployed script uses env python3; its PATH lookup needs the same
                # check as an explicit Python call, including scratch shadow refusal.
                if not record_python("python3"):
                    raise ValueError("untrusted direct writer interpreter")
            else:
                if not record_python(first):
                    raise ValueError("untrusted writer invocation or interpreter")
                script_at = 1
                # Explicit zero-arity switches only. -c/-m, option clusters and value
                # flags such as -W/-X are unsupported, not skipped speculatively.
                while script_at < len(segment) and segment[script_at][1] in ("-B", "-E", "-I"):
                    script_at += 1
                if script_at < len(segment) and segment[script_at][1] == "--":
                    script_at += 1
                if script_at >= len(segment):
                    raise ValueError("missing writer script operand")
                script = segment[script_at][1]
                if not os.path.isabs(script) or os.path.realpath(script) != writer:
                    raise ValueError("script operand is not the trusted record writer")
            try:
                spans.extend(record_arguments(segment, script_at, vault, writes))
            except RecordWriterGrantError as exc:
                # Finish checking every segment's grammar before imposing a grant
                # denial. A later premise failure cancels the whole writer rule.
                if grant_failure is None:
                    grant_failure = exc
        if grant_failure is not None:
            raise grant_failure
        if not spans:
            return command, None          # data occurrences confer no exception
        view = command
        for word in sorted(spans, key=lambda w: w[2], reverse=True):
            view = view[:word[2]] + "record-argument" + view[word[3]:]
        return view, None
    except RecordWriterGrantError as exc:
        return command, "record writer: " + str(exc)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return command, None


def check(event, grants, writes, head=False, network=None):
    """The whole decision as a pair — ("deny", reason), ("allow", reason) or ("silent", "") —
    computed, never printed and never exited, so head-fence.py can IMPORT this module and call
    this one function instead of paying a second interpreter start (D34 as amended, N8).
    `grants` and `writes` are lists of real paths; `network` is the run's `network` grant (a list of
    hosts, empty or None meaning no network); `head` selects the head role."""
    network = network or []
    def denial(reason):
        return "deny", "%s %s" % (FENCE, reason)

    if not isinstance(event, dict):
        return denial("hook input unreadable — fail-closed")
    if (event.get("tool_name") or "Bash") != "Bash":
        return "silent", ""               # not our channel; the harness decides
    if not grants:
        return denial("no grants in environment (LLM_WIKI_LANE_GRANTS unset or empty) "
                      "— fail-closed")

    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict) or "command" not in tool_input:
        return denial("no command in hook input — fail-closed")
    command = tool_input.get("command")
    if not isinstance(command, str):
        return denial("non-text command in hook input — fail-closed")
    if not command.strip():
        return "silent", ""               # writes nothing, reads nothing

    temps = temp_roots()
    read_roots = grants + writes + temps
    write_roots = writes + temps

    # Admitted writer operations need their grants even with broad read access. Every
    # other premise failure leaves the command unmasked for the ordinary checks below.
    command, writer_reason = record_writer_view(command, writes)
    if writer_reason:
        return denial(writer_reason)

    # Heredoc bodies are data, whoever wrote them: removed once, before every check (D33). The
    # command lines that opened them stay, so their own redirects and command words are checked.
    body = strip_heredocs(command)

    # 1 — a lane never spawns a lane. Off in the head role: a head spawns lanes for a living.
    if not head:
        for token in tokens_of(check1_text(body)):
            if os.path.basename(token.rstrip(os.sep)) == "claude":
                return denial("a lane may not invoke `claude` (no nested spawns)")

    original_body = body
    body, ssh_hosts, ssh_reads, ssh_writes, ssh_errors, ssh_active = ssh_command_view(body)
    if ssh_errors:
        return denial(ssh_errors[0])
    if ssh_active:
        heredoc_error = ssh_heredoc_error(command)
        if heredoc_error:
            return denial(heredoc_error)
    for kind, paths, roots in (("write", ssh_writes, write_roots),
                               ("read", ssh_reads, read_roots + [norm(os.getcwd())])):
        for origin, target in paths:
            if origin == "client program" and any(target.startswith(p) for p in SYSTEM_BIN) and os.path.exists(target):
                continue
            if not within(target, roots):
                return denial("%s local %s `%s` is outside the %s grants" % (origin, kind, target, kind))
    # The original is still needed for interpreter heredocs. Only replace literal shell
    # program strings which the classifier actually read; remote data never enters check N.
    local_command = command
    inline_payloads = interpreter_payloads(original_body)
    for payload in interpreter_payloads(command):
        local_payload, _, _, _, errors, used = ssh_command_view(payload)
        if used:
            if errors:
                return denial(errors[0])
            if not ssh_active or payload not in inline_payloads:
                return denial("unresolved ssh-family interpreter or heredoc wrapper grammar")
            local_command = local_command.replace(payload, local_payload)
    network_text = body if ssh_active else local_command
    client_calls = network_client_calls(body, local_command)

    # N — network (register 2026-09-07, memory-hunter; N class of the permission table). A network
    #     client, or an interpreter payload that imports a network module, is denied unless the run's
    #     `network` grant names the host it addresses. An absent or empty `network` grant means no
    #     network at all; a network command that names no host under a grant is unresolvable.
    if ssh_hosts or is_network_command(body, local_command):
        hosts = sorted({h.lower() for h in
                        ssh_hosts + command_hosts(body) + command_hosts(network_text) + network_operand_hosts(body)
                        if h})
        if not network:
            return denial("a network command is denied: the run's grants carry no `network` list "
                          "(N class off)%s" % ((" — it addresses `%s`" % ", ".join(hosts)) if hosts else ""))
        for base, options in client_calls:
            for name, _ in options:
                if name in NETWORK_INDIRECT_OPTIONS[base]:
                    return denial("`%s %s` can supply further network addresses or settings "
                                  "— denied as unresolvable" % (base, name))
        if not hosts:
            return denial("a network command under a `network` grant names no host this fence can "
                          "resolve (no `https://host` or `user@host` token) — denied as unresolvable")
        ungranted = [h for h in hosts if not host_granted(h, network)]
        if ungranted:
            return denial("the network host `%s` is not named in the run's `network` grant"
                          % ungranted[0])

    # 2 — write channels. Strip fd duplications, then quoted content (keeping a quoted single-path
    #     target), then redirect/tee targets already inside the write set; deny on what survives.
    scope = "outside the write whitelist" if writes else "on a lane with no write grant"
    local_segments = [(body[words[0][1]:words[-1][2]], base)
                      for words, base in command_base_segments(body)]
    for segment_text, base in local_segments:
        stripped = re.sub(r"[0-9]*>&[0-9-]+", " ", segment_text)
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
                    target = resolve_command_path(target, base)
                    if target is None:
                        return denial("unresolved local write base after compound or missing cd")
                    if within(target, write_roots):
                        stripped = (stripped[:match.start()] + " " * (match.end() - match.start())
                                    + stripped[match.end():])
                        break
                else:
                    break
        scope = "outside the write whitelist" if writes else "on a lane with no write grant"
        if ">" in stripped:
            return denial("shell redirection %s is denied (writes go to the granted directories, or "
                          "the change comes back as a proposed diff)" % scope)
        if re.search(r"(^|[^A-Za-z0-9_])tee([^A-Za-z0-9_]|$)", stripped):
            return denial("`tee` %s is denied" % scope)
        if re.search(r"(^|[^A-Za-z0-9_])(sed|perl)[^|;&]{0,60}\s-[A-Za-z]*i", stripped):
            return denial("an in-place editor (sed -i / perl -i) %s is denied" % scope)
    targets = []
    remaining_calls = list(client_calls)
    for segment_text, base in local_segments:
        calls = network_client_calls(segment_text, segment_text)
        for call in calls:
            if call in remaining_calls:
                remaining_calls.remove(call)
        file_targets, file_reason = network_file_targets(calls)
        if file_reason:
            return denial(file_reason)
        targets.extend((name, raw, cut_glob(unquote(raw).strip()), base)
                       for name, raw in mutator_targets(segment_text))
        # A shell wrapper with its own directory changes needs a separate grammar.
        nested_cd = any(segment_command(words)[1] == "cd"
                        for payload in interpreter_payloads(segment_text)
                        for words in shell_segments(payload))
        targets.extend((name, target, target, None if nested_cd else base)
                       for name, target in file_targets)
    # Interpreter heredoc bodies are absent from local_segments, but their client outputs
    # remain write targets. Only a unique header base can resolve their relative names.
    if remaining_calls:
        header_bases = {base for text, base in local_segments if heredoc_markers(text)}
        inherited = next(iter(header_bases)) if len(header_bases) == 1 else None
        if any(segment_command(words)[1] == "cd"
               for payload in interpreter_payloads(local_command) for words in shell_segments(payload)):
            inherited = None
        file_targets, file_reason = network_file_targets(remaining_calls)
        if file_reason:
            return denial(file_reason)
        targets.extend((name, target, target, inherited) for name, target in file_targets)
    for mutator, raw, target, base in targets:
        # N3 on the TARGET alone: a variable or a substitution the fence cannot resolve. A source
        # carrying one is a read, and the read side owns it.
        if "$" in raw or "`" in raw:
            return denial("`%s` takes the target `%s`, which carries a variable or a substitution "
                          "this fence cannot resolve — write the literal path (N3)" % (mutator, raw))
        if not target:
            continue
        resolved = resolve_command_path(target, base)
        if resolved is None:
            return denial("unresolved local write base after compound or missing cd")
        if not within(resolved, write_roots):
            return denial("`%s` targets `%s`, which is %s" % (mutator, target, scope))

    # 2b — an interpreter's OWN write (register fix b): a write-opening call in a `-c`/`-e` program
    #      or a heredoc body whose target is a string literal, checked against the write roots. A
    #      variable target is the stated residual. Scanned on the ORIGINAL command, heredocs intact.
    for call, target in interpreter_write_literals(local_command):
        if not target:
            continue
        interpreter_body = strip_heredocs(local_command)
        contexts = [(interpreter_body[words[0][1]:words[-1][2]], base)
                    for words, base in command_base_segments(interpreter_body)]
        matching = [base for text, base in contexts
                    if (call, target) in interpreter_write_literals(text)]
        if not matching:
            matching = [base for text, base in contexts if heredoc_markers(text)]
        # Multiple matching payloads all have to grant the target; an unknown base refuses.
        resolved_targets = [resolve_command_path(target, base) for base in matching or [None]]
        if any(path is None for path in resolved_targets):
            return denial("unresolved local interpreter write base after compound or missing cd")
        resolved = next((path for path in resolved_targets if not within(path, write_roots)), resolved_targets[0])
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
            continue                      # within_leaf: a leaf not yet created, by its parent (fix 4)
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


# --------------------------------------------------------------------------------------------------
# Unplaced reads: logged, never refused (owner decision of 23 October 2026). A cleared command whose
# read target this checker cannot place (a parameter, a substitution, arithmetic, a brace or ANSI-C
# expansion, or shell code handed to a builtin or a shell) gains one line in the run's log. Nothing
# here changes a decision: the callers run it only after `check()` has cleared the command, and
# every file it opens is opened non-blocking and must be a regular file.
# The numbers below are bounds that decide nothing; each was set by judgement, with its headroom noted.
UNPLACED_LOG_SUFFIX = "-unplaced-reads.jsonl"
UNPLACED_NOTE_SUFFIX = "-unplaced-reads.failed"
UNPLACED_SEEN_INFIX = "-unplaced-reads-seen-"
UNPLACED_LINE_CAP = 4096          # one line, one appending write; a typical line is about 160 bytes
UNPLACED_LOG_CAP = 8 * 1024 * 1024        # per run: room for 2,048 lines of the largest size
UNPLACED_NOTE_CAP = 64 * 1024             # failure notes per run: some 300 lines of about 200 bytes
# Both caps are SOFT. An append tests the size it sees and then writes, so W appends whose tests
# overlap can all pass and end the file up to (W - 1) * UNPLACED_LINE_CAP bytes past its cap (eight
# overlapping appends at the cap, measured: 28,672 bytes past). The report therefore reads a log or a
# note whole up to its cap plus UNPLACED_READ_SLACK, and of a larger file only that many bytes, saying
# so: a file the writer can produce always reads, as INCOMPLETE, never as a probe failure.
UNPLACED_READ_SLACK = 256 * UNPLACED_LINE_CAP   # 257 overlapping appends, far more hook processes
                                                # than one run holds at once: set by judgement
UNPLACED_WORD_CAP = 200           # characters per logged word, then a cut mark
UNPLACED_WORDS_CAP = 8            # words per line; `n` keeps the uncut count
UNPLACED_COMMAND_CAP = 2000       # characters of the command per line, half the line cap
UNPLACED_RECORD_CAP = 64 * 1024 * 1024    # a run record read by the report; a night's record is under 1 MiB
UNPLACED_COPY_CAP = 16 * 1024 * 1024      # a checker copy read by the report; this file is about 0.2 MiB
UNPLACED_LIST_CAP = 10            # lane ids named in one warning, then "and <m> more"
UNPLACED_HEAD_STARTS = {"head-successor": "session_id", "head-resumed": "session_id",
                        "run-resume": "session", "run-open": "session"}   # the run-record events that
#   name a head session, and the field naming it, as handsoff.py's run_heads counts them: the
#   supervisor's two starts and the head's own two. A run-open marked `session_kind: seed` is a
#   launcher's placeholder that never ran, so it expects no trace; every other start names its head.
RUN_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")
UNPLACED_NAME_START = re.compile(r"[A-Za-z_]")
UNPLACED_SPECIALS = "0123456789@*#?$!-"
UNPLACED_NUMERIC_ONLY = re.compile(r'^(?:"?(?:\$[?#$!-]|\$\{[?#$!-]\})"?)+$')
UNPLACED_ARITH_ONLY = re.compile(r'^"?(?:\$\(\((?:(?!\$\(|`).)*\)\)|\$\[(?:(?!\$\(|`).)*\])"?$', re.S)
UNPLACED_PRINTERS = frozenset({"echo", "printf"})
UNPLACED_CODE_WORDS = frozenset({"eval", "alias", "trap"})               # S1
UNPLACED_SHELL_FLAG = re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")             # S2: a one-dash cluster holding c
UNPLACED_SHELL_VALUE = re.compile(r"^(?:[-+][A-Za-z]*[oO]|--rcfile|--init-file)$")   # its value follows
UNPLACED_DESCRIPTOR_OP = re.compile(r"[<>]&[0-9-]+")


def strip_shell_comments(text, steps=None):
    """The text with every shell comment removed: an unquoted `#` that starts a word runs to its
    newline, which is kept. Quotes, backticks and a backslash escape are honoured. Pure."""
    steps = steps if steps is not None else [0]
    out, i, n, quote = [], 0, len(text), None
    while i < n:
        steps[0] += 1
        c = text[i]
        if quote == "'":
            out.append(c)
            quote = None if c == "'" else quote
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            out.append(text[i:i + 2])
            i += 2
            continue
        if quote in ('"', "`"):
            out.append(c)
            quote = None if c == quote else quote
            i += 1
            continue
        if c in "'\"`":
            quote = c
            out.append(c)
            i += 1
            continue
        if c == "#" and (i == 0 or text[i - 1] in " \t\n;&|()<>"):
            while i < n and text[i] != "\n":
                steps[0] += 1
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _unplaced_skip_to(word, i, ch, steps):
    """The index after the next `ch` from `i` (or the end), one forward pass."""
    n = len(word)
    while i < n and word[i] != ch:
        steps[0] += 1
        i += 1
    return min(i + 1, n)


def _unplaced_close(word, i, opener, closer, steps):
    """From word[i] == opener, the index after its matching closer, and whether a `$(` or a
    backtick stands inside (one pass, quotes honoured)."""
    depth, quote, n, sub = 0, None, len(word), False
    while i < n:
        steps[0] += 1
        c = word[i]
        if quote == "'":
            if c == "'":
                quote = None
        elif c == "\\":
            i += 1
        elif quote == '"':
            if c == '"':
                quote = None
            elif c == "`" or (c == "$" and word[i + 1:i + 2] == "("):
                sub = True
        elif c in "'\"":
            quote = c
        elif c == "`" or (c == "$" and word[i + 1:i + 2] == "("):
            sub = True
        elif c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return i + 1, sub
        i += 1
    return n, sub


def unplaced_forms(word, steps=None):
    """The unplaced forms U1-U5 in one raw word (a set of their names), detected outside single
    quotes and not after a backslash. Linear: a `$(`, `${`, `$[` or backtick jumps to its end, and
    a brace is tested with one pass to the next brace. Pure."""
    steps = steps if steps is not None else [0]
    found, i, n, quote = set(), 0, len(word), None
    while i < n:
        steps[0] += 1
        c = word[i]
        if quote == "'":
            if c == "'":
                quote = None
            i += 1
            continue
        if c == "\\":
            i += 2
            continue
        if c == "'" and quote is None:
            quote = "'"
            i += 1
            continue
        if c == '"':
            quote = None if quote == '"' else '"'
            i += 1
            continue
        if c == "`":
            found.add("U2")
            i = _unplaced_skip_to(word, i + 1, "`", steps)
            continue
        if c == "$":
            nxt = word[i + 1:i + 2]
            if nxt == "'" and quote is None:                    # U5, ANSI-C quoting
                j = i + 2
                while j < n and word[j] != "'":
                    steps[0] += 1
                    if word[j] == "\\":
                        found.add("U5")
                        j += 1
                    j += 1
                i = j + 1
                continue
            if word.startswith("$((", i):                       # U3, arithmetic
                found.add("U3")
                i, sub = _unplaced_close(word, i + 1, "(", ")", steps)
                if sub:
                    found.add("U2")
                continue
            if nxt == "[":                                      # U3, the older $[ ... ] spelling
                found.add("U3")
                i, sub = _unplaced_close(word, i + 1, "[", "]", steps)
                if sub:
                    found.add("U2")
                continue
            if nxt == "(":                                      # U2, command substitution
                found.add("U2")
                i, _ = _unplaced_close(word, i + 1, "(", ")", steps)
                continue
            if nxt == "{":                                      # U1, braced
                found.add("U1")
                i = _unplaced_skip_to(word, i + 2, "}", steps)
                continue
            if nxt and (UNPLACED_NAME_START.match(nxt) or nxt in UNPLACED_SPECIALS):   # U1
                found.add("U1")
                i += 2
                while nxt not in UNPLACED_SPECIALS and i < n and (word[i].isalnum() or word[i] == "_"):
                    steps[0] += 1
                    i += 1
                continue
            i += 1
            continue
        if c == "{" and quote is None:                          # U4: one pass to the next brace
            j, mark, quoted = i + 1, False, False
            while j < n and word[j] not in "{}":
                steps[0] += 1
                ch = word[j]
                if ch == "," or (ch == "." and word[j + 1:j + 2] == "."):
                    mark = True
                elif ch in "'\"":
                    quoted = True
                j += 1
            if j < n and word[j] == "}" and mark and not quoted:
                found.add("U4")
        i += 1
    return found


def heredoc_bodies(command, steps=None):
    """[(protected, [body lines])] for every heredoc, in order, read the way `ssh_heredoc_error`
    reads them: a raw marker holding a quote or a backslash is protected. When the markers cannot be
    aligned with the line's words, every body is read as unprotected (the broad reading). Pure."""
    steps = steps if steps is not None else [0]
    lines, i, out = command.split("\n"), 0, []
    while i < len(lines):
        line = lines[i]
        i += 1
        steps[0] += 1
        markers = heredoc_markers(line)
        if not markers:
            continue
        words = [word[0] for segment in ssh_shell_words(line) for word in segment]
        raw = [words[j + 1] for j, word in enumerate(words[:-1]) if word in ("<<", "<<-")]
        protected = ([any(ch in r for ch in "'\"\\") for r in raw] if len(raw) == len(markers)
                     else [False] * len(markers))
        for (marker, dash), prot in zip(markers, protected):
            body = []
            while i < len(lines):
                text = lines[i]
                i += 1
                steps[0] += 1
                if (text.lstrip("\t") if dash else text) == marker:
                    break
                body.append(text)
            out.append((prot, body))
    return out


def _unplaced_substitution_line(text, steps):
    """True when a heredoc body line holds an unescaped `$(` or a backtick."""
    j = 0
    while j < len(text):
        steps[0] += 1
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == "`" or text.startswith("$(", j):
            return True
        j += 1
    return False


def _unplaced_piped(text, previous, first):
    """True when the separator text before a segment is a pipe (`|` or `|&`)."""
    gap = "".join(ch for ch in text[previous:first] if not ch.isspace() and ch not in "()")
    return gap in ("|", "|&")


def unplaced_reads(command, steps=None):
    """[(kind, word)] for every word of `command` that names a read this checker cannot place:
    the forms U1-U5 less the exclusions X1-X6, shell code (S1-S3) and heredoc substitutions. Pure:
    it reads and writes nothing. `steps`, a one-element list, counts the new walkers' visits."""
    steps = steps if steps is not None else [0]
    text = strip_shell_comments(strip_heredocs(command), steps)
    out, feeds_heredoc, previous_end = [], False, 0
    for segment in ssh_shell_words(text):
        words = [item[0] for item in segment]
        piped = _unplaced_piped(text, previous_end, segment[0][1])
        previous_end = segment[-1][2]
        ci, base = segment_command(words)
        skip = set()
        if not (base == "rg" and any(unquote_token(w).strip() == "--files" for w in words)):
            pattern = pattern_operand(words)                    # X3, except rg --files (no pattern)
            if pattern is not None:
                skip.add(pattern)
            skip |= search_pattern_indices(words)
        # S2 and S3: one forward pass over the segment's words.
        code, armed, want, value, stdin_shell = {}, None, False, False, None
        for j, w in enumerate(words):
            steps[0] += 1
            plain = unquote_token(w).strip()
            if want:
                if value:
                    value = False
                    continue
                if plain[:1] in "-+" and len(plain) > 1:
                    value = bool(UNPLACED_SHELL_VALUE.match(plain))
                    continue
                code[j] = (armed == ci and interpreter_segment(words))
                want, armed = False, None
                continue
            if (os.path.basename(plain.rstrip("/")) in SHELL_PROGRAMS and w[:1] not in "<>"
                    and j not in skip and base not in UNPLACED_PRINTERS):
                armed, stdin_shell = j, j
                continue
            if armed is not None and UNPLACED_SHELL_FLAG.match(plain):
                want, stdin_shell = True, None
                continue
        if stdin_shell is not None and piped:
            out.append(("shell-code", words[stdin_shell]))      # S3: its program arrives on the pipe
        op = None
        for j, w in enumerate(words):
            steps[0] += 1
            if w[:1] in "<>":
                op = None if UNPLACED_DESCRIPTOR_OP.fullmatch(w) else w
                if op in ("<<", "<<-") and stdin_shell is not None:
                    feeds_heredoc = True                         # S3: a heredoc feeds a shell
                continue
            this_op, op = op, None
            if this_op == "<<<" and stdin_shell is not None:
                out.append(("shell-code", w))                   # S3: a here-string feeds a shell
                continue
            if j in code:
                if not code[j] or "$" in w or "`" in w:
                    out.append(("shell-code", w))               # S2
                continue
            if (base in UNPLACED_CODE_WORDS and ci is not None and j > ci and this_op is None
                    and (base != "trap" or j == ci + 1)):       # S1: trap's code is its first argument
                out.append(("shell-code", w))
                continue
            forms = unplaced_forms(w, steps)
            if not forms:
                continue
            if this_op is not None:
                if this_op.startswith(">") or this_op.startswith("&>") or this_op in ("<<", "<<-"):
                    continue                                    # X5, X6
                if this_op == "<<<" and "U2" not in forms:
                    continue                                    # X5
                out.append(("input", w) if this_op != "<<<" else ("operand", w))
                continue
            assignment = (ci is None or j < ci)
            if "U2" not in forms:
                if assignment:
                    continue                                    # X1
                if base in UNPLACED_PRINTERS or j in skip:
                    continue                                    # X2, X3
                if UNPLACED_NUMERIC_ONLY.match(w) or UNPLACED_ARITH_ONLY.match(w):
                    continue                                    # X4
            out.append(("program" if j == ci else "assignment" if assignment else "operand", w))
    bodies = heredoc_bodies(command, steps)
    if feeds_heredoc:
        out += [("shell-code", "\n".join(body)) for _, body in bodies]
    else:
        out += [("heredoc", line) for prot, body in bodies if not prot
                for line in body if _unplaced_substitution_line(line, steps)]
    return out


def unplaced_store():
    """The run store, derived as head-fence.py and lane.py derive it."""
    return os.path.realpath(os.path.expanduser(os.environ.get("LLM_WIKI_STORE") or "~/.llm-wiki"))


def unplaced_notes_dir():
    """Where a writer session's marker goes: the run-scoped scratch folder lane.py uses."""
    return os.environ.get("LLM_WIKI_PROGRESS_DIR") or "/tmp"


def unplaced_lane_who():
    """`lane:<id>` for a lane's line, `lane:?` when the id is not a run-id-shaped string."""
    lane = os.environ.get("LLM_WIKI_LANE_ID") or ""
    return "lane:" + (lane if RUN_ID.fullmatch(lane) else "?")


def _unplaced_line(obj):
    """One encoded line of at most UNPLACED_LINE_CAP bytes: halve `cmd`, then drop `reads`
    pairs from the end, then shorten `cwd`; `n` is never cut."""
    while True:
        data = (json.dumps(obj, ensure_ascii=True, separators=(",", ":")) + "\n").encode("ascii")
        if len(data) <= UNPLACED_LINE_CAP:
            return data
        obj["cut"] = True
        if obj["cmd"]:
            obj["cmd"] = obj["cmd"][:len(obj["cmd"]) // 2]
        elif obj["reads"]:
            obj["reads"].pop()
        else:
            obj["cwd"] = obj["cwd"][:64]


def _unplaced_warn(message):
    """One stderr line; never raises."""
    try:
        sys.stderr.write("[unplaced-reads] %s\n" % message)
    except Exception:
        pass


def _unplaced_first_in_session(notes, run, who, sid):
    """True when this call made the session's marker, so this is its first cleared command."""
    tag = hashlib.sha256(("%s\n%s" % (who, sid)).encode("utf-8", "backslashreplace")).hexdigest()[:16]
    try:
        _unplaced_append(os.path.join(notes, run + UNPLACED_SEEN_INFIX + tag), b"", 0, exclusive=True)
        return True
    except OSError:             # a later command of this session, or no marker possible: no trace
        return False


def _unplaced_append(path, data, cap, exclusive=False):
    """The ONLY function in this file that opens a file for writing: a non-blocking, no-follow
    append to a regular file, one write of one whole line. Returns "ok" or "capped"; raises
    OSError on any failure, a non-regular file and a short write included."""
    flags = (os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
             | getattr(os, "O_CLOEXEC", 0) | (os.O_EXCL if exclusive else 0))
    fd = os.open(path, flags, 0o600)
    try:
        status = os.fstat(fd)
        if not stat.S_ISREG(status.st_mode):
            raise OSError("not a regular file")
        if not data:
            return "ok"
        if status.st_size + len(data) > cap:
            return "capped"
        if os.write(fd, data) != len(data):
            raise OSError("short write")
        return "ok"
    finally:
        os.close(fd)


def record_unplaced_reads(event, store, run, who):
    """Log-only: append the run's line for one CLEARED command, and the writer session's trace on
    its first one. Never raises and never prints to stdout; returns a short status for tests."""
    try:
        if not isinstance(event, dict) or event.get("hook_event_name") != "PreToolUse":
            return "skip: not a hook event"
        tool_input = event.get("tool_input")
        command = tool_input.get("command") if isinstance(tool_input, dict) else None
        if not isinstance(command, str) or not command.strip():
            return "skip: no command"
        if not isinstance(run, str) or not RUN_ID.fullmatch(run):
            return "skip: no run id"
        records = os.path.join(store, "spawn-records")
        if not os.path.isfile(os.path.join(records, run + ".jsonl")):
            return "skip: no run record"
        try:
            reads = unplaced_reads(command)
        except Exception as exc:
            reads = [("scan-error", type(exc).__name__)]
        sid = event.get("session_id")
        sid = sid if isinstance(sid, str) and RUN_ID.fullmatch(sid) else "?"
        first = _unplaced_first_in_session(unplaced_notes_dir(), run, who, sid)
        if not reads and not first:
            return "ok: nothing to log"
        cut, words = False, []
        for kind, word in reads[:UNPLACED_WORDS_CAP]:
            if len(word) > UNPLACED_WORD_CAP:
                word, cut = word[:UNPLACED_WORD_CAP] + "…", True
            words.append([kind, word])
        cwd = event.get("cwd")
        if not isinstance(cwd, str):
            try:
                cwd = os.getcwd()
            except OSError:
                cwd = "?"
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        obj = {"v": 1, "ts": stamp, "who": who, "sid": sid, "cwd": cwd[:512], "n": len(reads),
               "reads": words, "cmd": command[:UNPLACED_COMMAND_CAP] if reads else "",
               "cut": (cut or len(reads) > UNPLACED_WORDS_CAP or len(cwd) > 512
                       or (bool(reads) and len(command) > UNPLACED_COMMAND_CAP))}
        data = _unplaced_line(obj)
        log = os.path.join(records, run + UNPLACED_LOG_SUFFIX)
        try:
            status = _unplaced_append(log, data, UNPLACED_LOG_CAP)
            return ("ok" if reads else "ok: trace") if status == "ok" else status
        except OSError as exc:
            note = (json.dumps({"v": 1, "ts": stamp, "who": who, "error": "%s: %s" % (type(exc).__name__, exc),
                                "n": len(reads)}, ensure_ascii=True) + "\n").encode("ascii")
            try:
                _unplaced_append(os.path.join(records, run + UNPLACED_NOTE_SUFFIX), note, UNPLACED_NOTE_CAP)
                _unplaced_warn("append failed at %s (%s); noted beside it" % (log, exc))
                return "failed: noted"
            except OSError as exc2:
                _unplaced_warn("append failed at %s (%s) and its note failed (%s)" % (log, exc, exc2))
                return "failed: lost"
    except Exception as exc:      # the belt: nothing here may change a decision
        _unplaced_warn("skipped (%s)" % type(exc).__name__)
        return "failed: belt"


def _unplaced_read(path, limit, prefix=False):
    """The ONLY function in this file that opens the report's files: read-only, non-blocking,
    no-follow, regular files only. By default the file must hold at most `limit` bytes, else OSError.
    With `prefix`, it returns (at most the first `limit` bytes, whether more followed) and size is
    never an error, so a log its writers took past the soft cap still reads. Raises OSError otherwise."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    try:
        status = os.fstat(fd)
        if not stat.S_ISREG(status.st_mode):
            raise OSError("not a regular file")
        if status.st_size > limit and not prefix:
            raise OSError("larger than %d bytes" % limit)
        chunks, total = [], 0
        while total <= limit:                   # at most limit + 1 bytes are ever held
            block = os.read(fd, min(1 << 20, limit + 1 - total))
            if not block:
                break
            chunks.append(block)
            total += len(block)
        data = b"".join(chunks)
        if not prefix:
            if total > limit:
                raise OSError("larger than %d bytes" % limit)
            return data
        return data[:limit], total > limit
    finally:
        os.close(fd)


def _unplaced_names(items):
    items = sorted(items)
    shown = ", ".join(items[:UNPLACED_LIST_CAP])
    return shown + (" and %d more" % (len(items) - UNPLACED_LIST_CAP) if len(items) > UNPLACED_LIST_CAP else "")


def _unplaced_record_flaw(event):
    """Why one parsed run-record event cannot be counted for coverage, or None: it names no event,
    it is a lane-open naming no lane, or it is a head start (UNPLACED_HEAD_STARTS) naming no
    run-id-shaped session. Each such line could hide a writer the report would otherwise expect.
    A seed run-open is no head start, whatever it names, so its session is not judged."""
    kind = event.get("event")
    if not isinstance(kind, str) or not kind:
        return "names no event"
    if kind == "lane-open" and not (isinstance(event.get("lane"), str) and event.get("lane")):
        return "is a lane-open naming no lane"
    if kind == "run-open" and event.get("session_kind") == "seed":
        return None
    key = UNPLACED_HEAD_STARTS.get(kind)
    if key is not None and not (isinstance(event.get(key), str) and RUN_ID.fullmatch(event.get(key))):
        return "is a %s naming no session in `%s`" % (kind, key)
    return None


def _unplaced_head_sessions(events):
    """The head sessions the run record names (UNPLACED_HEAD_STARTS), first-seen order, each once:
    a head-successor and the run-resume its head writes share one session by design. A seed run-open
    never ran, so it names no head; a later head start naming the same session still does."""
    sessions = []
    for e in events:
        kind = e.get("event")
        key = UNPLACED_HEAD_STARTS.get(kind) if isinstance(kind, str) else None
        if kind == "run-open" and e.get("session_kind") == "seed":
            continue
        sid = e.get(key) if key is not None else None
        if isinstance(sid, str) and RUN_ID.fullmatch(sid) and sid not in sessions:
            sessions.append(sid)
    return sessions


def _unplaced_claude_lanes(events):
    """(expected, exempt): the Claude lanes the run record shows as opened that may have cleared a
    shell command, and those it shows could not have (no Bash, or a close with no cleared one)."""
    opened, codex, no_bash, quiet = set(), set(), set(), set()
    for e in events:
        lane, kind = e.get("lane"), e.get("event")
        if not isinstance(lane, str) or not lane:
            continue
        if e.get("harness") == "codex" or str(e.get("mechanism", "")).startswith("codex-lane.py"):
            codex.add(lane)
        if kind == "lane-open":
            opened.add(lane)
            tools = e.get("tools")
            if isinstance(tools, list) and "Bash" not in tools:
                no_bash.add(lane)
            else:
                no_bash.discard(lane)
        elif kind == "lane-closed":
            denials = e.get("denials") if isinstance(e.get("denials"), dict) else {}
            allows, transcript = denials.get("fence_allows"), e.get("transcript")
            if type(allows) is int and allows == 0 and isinstance(transcript, str) and transcript:
                quiet.add(lane)
            else:
                quiet.discard(lane)
    return opened - codex - no_bash - quiet, ((no_bash | quiet) & opened) - codex


def report_unplaced_reads(run, limit=60):
    """The close report: stdout only, read-only. Returns the exit code: 0 complete, 1 incomplete,
    2 probe failed. The last line is exactly one VERDICT or PROBE FAILED line."""
    if not isinstance(run, str) or not RUN_ID.fullmatch(run):
        print("PROBE FAILED: %r is not a run id" % (run,))
        return 2
    store = unplaced_store()
    records = os.path.join(store, "spawn-records")
    log = os.path.join(records, run + UNPLACED_LOG_SUFFIX)
    print("UNPLACED-READS run=%s log=%s" % (run, log))
    if not os.path.lexists(log):
        print("PROBE FAILED: no log at %s: no writer left a line for this run, or the log was removed; "
              "nothing can be concluded" % log)
        return 2
    bound = UNPLACED_LOG_CAP + UNPLACED_READ_SLACK
    try:
        raw, overfull = _unplaced_read(log, bound, prefix=True)
    except OSError as exc:
        print("PROBE FAILED: cannot read %s (%s: %s); nothing can be concluded" % (log, type(exc).__name__, exc))
        return 2
    if overfull:                                 # keep the whole lines before the bound; the rest is not read
        cut = raw.rfind(b"\n")
        raw = raw[:cut + 1] if cut >= 0 else raw
    lines, torn = [], 0
    for chunk in raw.split(b"\n"):
        if not chunk:
            continue
        try:
            obj = json.loads(chunk)
            if not isinstance(obj, dict) or obj.get("v") != 1 or type(obj.get("n")) is not int:
                raise ValueError
            lines.append(obj)
        except (ValueError, RecursionError):
            torn += 1
    entries = [e for e in lines if e["n"] >= 1]
    warnings, notes_line = [], []
    if torn:
        warnings.append("%d unreadable line(s)" % torn)
    if not lines and not torn:
        warnings.append("the log is empty: no writer left a line")
    errors = sum(1 for e in entries for pair in (e.get("reads") if isinstance(e.get("reads"), list) else [])
                 if isinstance(pair, list) and pair[:1] == ["scan-error"])
    if errors:
        warnings.append("%d scan error(s)" % errors)
    if len(raw) >= UNPLACED_LOG_CAP - UNPLACED_LINE_CAP:
        warnings.append("cap reached: later entries dropped, counts are lower bounds")
    if overfull:
        warnings.append("the log runs past this reader's %d-byte bound (appends overlapping at the soft cap): "
                        "only its first %d bytes were read" % (bound, len(raw)))
    failed = os.path.join(records, run + UNPLACED_NOTE_SUFFIX)
    if os.path.lexists(failed):
        try:
            notes, more = _unplaced_read(failed, UNPLACED_NOTE_CAP + UNPLACED_READ_SLACK, prefix=True)
            count = len([l for l in (notes[:notes.rfind(b"\n") + 1] if more else notes).split(b"\n") if l])
            warnings.append("%s%d write failure note(s) in %s" % ("at least " if more else "", count, failed))
        except OSError as exc:
            warnings.append("write failure notes unreadable at %s (%s)" % (failed, exc))
    own = os.path.realpath(__file__)
    lane_copy = os.path.join(os.environ.get("LLM_WIKI_LANE_HOME") or os.path.join(store, "lane-home"),
                             "lane-fence.py")
    head_hook = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(own))), "hooks", "head-fence.py")
    if os.path.realpath(lane_copy) == own:
        warnings.append("this reporter is the lane-home copy: lane logging not compared")
    else:
        try:
            if (hashlib.sha256(_unplaced_read(own, UNPLACED_COPY_CAP)).digest()
                    != hashlib.sha256(_unplaced_read(lane_copy, UNPLACED_COPY_CAP)).digest()):
                warnings.append("the lane-home checker differs from this one: lanes may not have logged")
        except OSError as exc:
            warnings.append("lane-home checker unreadable (%s): lane logging not confirmed" % exc)
    head_present = os.path.isfile(head_hook)
    if not head_present:
        notes_line.append("head-fence.py not beside this checker: its install time and the head's coverage not checked")
    events, first, flaws = None, None, []
    try:
        rows = [(number, c) for number, c in
                enumerate(_unplaced_read(os.path.join(records, run + ".jsonl"), UNPLACED_RECORD_CAP).split(b"\n"), 1)
                if c.strip()]
        events = []
        for index, (number, chunk) in enumerate(rows):
            # A line that cannot be counted is never skipped silently: torn, it may have been the
            # lane-open or head start that names a writer the log lacks (it is named below).
            try:
                obj = json.loads(chunk)
            except (ValueError, RecursionError):
                flaws.append("line %d does not parse" % number)
                continue
            if not isinstance(obj, dict):
                flaws.append("line %d is not a JSON object" % number)
                continue
            events.append(obj)
            if index == 0:
                first = obj
            why = _unplaced_record_flaw(obj)
            if why:
                flaws.append("line %d %s" % (number, why))
    except OSError as exc:
        events = None
        warnings.append("run record unreadable (%s): install time, lane and head coverage not checked" % exc)
    if flaws:
        warnings.append("%d run record line(s) cannot be counted, so a lane or head session may be missing: %s"
                        % (len(flaws), "; ".join(flaws[:UNPLACED_LIST_CAP])
                           + (" and %d more" % (len(flaws) - UNPLACED_LIST_CAP) if len(flaws) > UNPLACED_LIST_CAP else "")))
    if events is not None:
        try:
            opened = datetime.strptime(first["ts"], "%Y-%m-%dT%H:%M:%S%z").timestamp()
            hooks = [own, lane_copy] + ([head_hook] if head_present else [])
            if [p for p in hooks if os.path.getmtime(p) > opened]:
                warnings.append("the logger was installed after the run opened (%s): earlier commands were not logged"
                                % first["ts"])
        except (KeyError, TypeError, ValueError, OSError) as exc:
            warnings.append("run-open time unreadable (%s): install time not checked" % type(exc).__name__)
        seen = {str(e.get("who", ""))[5:] for e in lines if str(e.get("who", "")).startswith("lane:")}
        expected, exempt = _unplaced_claude_lanes(events)
        missing = expected - seen
        if exempt - seen:
            notes_line.append("not expected to log: %s" % _unplaced_names(exempt - seen))
        if missing:
            warnings.append("%d Claude lane(s) left no line in the log though they may have cleared a command: %s"
                            % (len(missing), _unplaced_names(missing)))
        if head_present and not any(e.get("who") == "head" for e in lines):
            warnings.append("no line from the head: its commands were not logged (an unarmed head never logs, "
                            "and a head hook without the logger does not either)")
        elif head_present:
            # Per session: one head session's trace must not stand in for another's absence.
            traced = {str(e.get("sid")) for e in lines if e.get("who") == "head"}
            untraced = [s for s in _unplaced_head_sessions(events) if s not in traced]
            if untraced:
                warnings.append("%d head session(s) the run record names left no line in the log though they may "
                                "have cleared a command: %s" % (len(untraced), _unplaced_names(untraced)))
    distinct = {}
    for e in entries:
        reads = e.get("reads") if isinstance(e.get("reads"), list) else []
        d = distinct.setdefault(str(e.get("cmd", "")), {"n": 0, "first": str(e.get("ts", "?")), "who": set(),
                                                         "reads": reads})
        d["n"] += 1
        d["who"].add(str(e.get("who", "?")))
    writers = sorted({str(e.get("who", "?")) for e in lines})
    print("premises: %s" % ("; ".join(warnings + notes_line) if warnings or notes_line else "all hold"))
    print("entries: %d in %d distinct command(s) · trace lines: %d · writers seen: %d%s"
          % (len(entries), len(distinct), len(lines) - len(entries), len(writers),
             " (%s)" % _unplaced_names(writers) if writers else ""))
    print("coverage: not covered by this log: Codex lanes; programs read from files; aliases and functions "
          "from start-up files; interpreter-internal reads; names taken from input; zsh-only expansions; "
          "commands the head hook lets through as broken machinery")
    for cmd, d in sorted(distinct.items(), key=lambda kv: kv[1]["first"])[:limit]:
        pairs = [p for p in d["reads"] if isinstance(p, list) and len(p) == 2][:6]
        print("[%dx] %s %s · %s" % (d["n"], d["first"], ",".join(sorted(d["who"])),
                                         "; ".join("%s %s" % (k, str(w)[:80]) for k, w in pairs)))
        print("    $ %s" % " ".join(cmd.split())[:240])
    if len(distinct) > limit:
        print("(%d more distinct commands not shown; the full log is the file above)" % (len(distinct) - limit))
    if warnings:
        print("VERDICT: INCOMPLETE (%d premise warning(s)) · %d recorded — a low count here is not a clean result"
              % (len(warnings), len(entries)))
        return 1
    print("VERDICT: complete · %s" % ("none recorded" if not entries else
          "%d recorded reads through an expansion; each needs judgement on whether it left its helper's folders"
          % len(entries)))
    return 0


def unplaced_reads_cli(argv):
    """`--unplaced-reads RUN [--limit N]`: the close report. Reads no stdin."""
    run, limit, rest = None, 60, list(argv)
    while rest:
        word = rest.pop(0)
        if word == "--limit" and rest and rest[0].isdigit():
            limit = int(rest.pop(0))
        elif run is None and not word.startswith("--"):
            run = word
        else:
            run = None
            break
    if run is None:
        print("PROBE FAILED: usage: lane-fence.py --unplaced-reads RUN [--limit N]")
        return 2
    try:
        return report_unplaced_reads(run, limit)
    except Exception as exc:      # the last line is always a verdict or a probe failure
        print("PROBE FAILED: the report raised %s: %s; nothing can be concluded" % (type(exc).__name__, exc))
        return 2


def main():
    if sys.argv[1:2] == ["--unplaced-reads"]:
        sys.exit(unplaced_reads_cli(sys.argv[2:]))   # the close report: reads no stdin
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
    if action == "allow":
        # Log-only (owner decision 2026-10-23): before `decide`, which exits. Nothing here may
        # change the decision, so even SystemExit and KeyboardInterrupt are caught.
        try:
            record_unplaced_reads(event, unplaced_store(), os.environ.get("LLM_WIKI_LANE_RUN"),
                                  unplaced_lane_who())
        except BaseException as exc:
            _unplaced_warn("skipped in main (%s)" % type(exc).__name__)
    if action == "silent":
        sys.exit(0)
    decide(action, reason)


if __name__ == "__main__":
    main()
