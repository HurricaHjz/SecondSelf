#!/usr/bin/env python3
"""test_pass_order.py: the suite for pass_order.py, on fixtures it builds in a temporary folder
(tempfile, which honours TMPDIR) and removes at the end. Python 3 standard library only.

    python3 -B test_pass_order.py [CASE ...]

Each case writes a reviewer's run record in the shape the wrapper records it (a Codex event log:
JSON lines of thread.started, turn.started, item.started and item.completed, turn.completed) and
runs pass_order.py as its own process. The suite ends `PASS n/n`, or names each failure and ends
`FAIL k/n` with a non-zero exit. Case names given as arguments select a subset for iterating: the
suite prints its selection and refuses a misspelt name.

The cases are the design note's tests for the list (option S, revision 7, 13 October 2026), with
revision 6's two, as revision 7 reads them: T5's truncation test over the event log, a framed
input (every record cut after each whole line is caught, giving no list, or gives exactly the whole
record's output; a cut accepted with another output is FAIL, since revision 7 keeps the stated
limit for unframed Markdown pages alone, so a record holds one turn and a second turn is outside
the grammar), and the record looked at by its own metadata (a metadata error is never "the record
does not exist"):
- T1, the two acceptance runs' records (structural copies, below): exactly the nine commands
  before the first-pass message, verbatim, in start order, one per execution;
- T2, a command after the message is not listed, and one begun before it and finished after it
  is;
- T3, a record with no first-pass message, a cut-off message and a complete message with zero
  findings;
- T4, unreadable, truncated and malformed evidence: `could not read` naming the record and the
  event's log line, a non-zero exit and no list;
- T8, no output line, exit code or file of the tool claims a verdict on the first pass: every
  output of every case is searched (Fixture.run), with the search's own controls in one case;
- T10, the retirement: the verdict tests of the held build are retired, and the evidence
  invariants they carried (start order, one entry per execution, boundary semantics, malformed
  fields named) survive with neutral assertions; RETIRED below maps each held case to its fate,
  and a case checks the map;
- T11, lossless listing: two commands that differ only in a literal escape-looking text beside a
  real control character print differently, decoding each print (with this suite's own decoder)
  recovers its command exactly, and a command with nothing hidden prints byte for byte; no output
  of the tool holds a character a terminal could hide (every output is searched, in Fixture.run);
and the list's other duties (file changes apart, --whole-run, verbatim text, the exit codes, the
controls) and a last leg proving it writes nothing.
"""

import hashlib
import importlib.util
import io
import contextlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "pass_order.py")
TIMEOUT_S = 60   # set by judgement, unmeasured: a fixture run takes well under a second
INDENT = "    "
FINDINGS = ("PASS 1 FINDINGS\nP1-1 a stale rule: CLAUDE.md:3 says x; it matters because y\n"
            "P1-2 a contradiction: z\nEND PASS 1: 2 findings")
# The commands before the first-pass message in each acceptance run's record, counted by hand from
# the original records: nine in each (the second design check's count, which the third confirmed).
HAND_COUNT = 9

# T8: what a verdict on the first pass looks like. A line matching any of these, in any output of
# the tool, fails the case that produced it.
VERDICT_PATTERNS = (
    r"(?i)\bblind",
    r"PASS-ORDER",
    r"\bCLEAR\b",
    r"\bUNDECIDED\b",
    r"(?i)\bfirst[- ]pass\b.{0,40}\b(was|is|were)\b.{0,20}\b(independent|clean|unseen|"
    r"uncontaminated)\b",
)
SEARCHED = {"outputs": 0, "lines": 0}


class Failure(Exception):
    pass


def check(condition, message):
    if not condition:
        raise Failure(message)


def verdict_lines(text):
    return [line for line in text.splitlines()
            if any(re.search(pattern, line) for pattern in VERDICT_PATTERNS)]


# ------------------------------------------------------------------ the fixture --------------

class Fixture(object):
    """A folder for run records; every run's output is searched for a verdict (T8)."""

    def __init__(self, root):
        self.root = root
        self.logs = os.path.join(root, "logs")
        os.makedirs(self.logs)
        self.count = 0

    def log(self, events, name=None):
        self.count += 1
        path = os.path.join(self.logs, name or "events-%d.log" % self.count)
        lines = [e if isinstance(e, str) else json.dumps(e) for e in events]
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + ("\n" if lines else ""))
        return path

    def run(self, events_path, *extra, **options):
        command = [sys.executable, "-B", SCRIPT]
        if options.get("events", True):
            command += ["--events", events_path]
        done = subprocess.run(command + list(extra), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=TIMEOUT_S)
        # read as bytes and decoded strictly, with no newline translation, so that a carriage
        # return or any other character a terminal could hide reaches the check below as it is
        stdout, stderr = done.stdout.decode("utf-8"), done.stderr.decode("utf-8")
        SEARCHED["outputs"] += 1
        SEARCHED["lines"] += len(stdout.split("\n")) - 1
        hits = verdict_lines(stdout + "\n" + stderr)
        check(not hits, "T8: an output of the tool reads as a verdict on the first pass: %r" % hits)
        check(not hidden(stdout), "item 1: an output of the tool holds %d character(s) a terminal "
              "could hide, the first %r" % (len(hidden(stdout)), hidden(stdout)[:1]))
        return done.returncode, stdout, stderr

    def check_log(self, events, *extra):
        return self.run(self.log(events), *extra)


START = [{"type": "thread.started", "thread_id": "t-1"}, {"type": "turn.started"}]
END = [{"type": "turn.completed", "usage": {"input_tokens": 1}}]


def message(n, text):
    return {"type": "item.completed",
            "item": {"id": "item_%d" % n, "type": "agent_message", "text": text}}


def wrapped(text):
    """A command's text as the wrapper records it: `/bin/zsh -lc` and the script, POSIX-quoted."""
    return "/bin/zsh -lc %s" % shlex.quote(text)


def command(n, text, output="", phase="both", status="completed", exit_code=0, raw=False):
    """A command's events in the wrapper's shape (raw: the text is the whole command field)."""
    full = text if raw else wrapped(text)
    started = {"type": "item.started",
               "item": {"id": "item_%d" % n, "type": "command_execution", "command": full,
                        "aggregated_output": "", "exit_code": None, "status": "in_progress"}}
    completed = {"type": "item.completed",
                 "item": {"id": "item_%d" % n, "type": "command_execution", "command": full,
                          "aggregated_output": output, "exit_code": exit_code, "status": status}}
    return {"both": [started, completed], "started": [started], "completed": [completed]}[phase]


def change(n, path, kind="update"):
    item = {"id": "item_%d" % n, "type": "file_change", "changes": [{"path": path, "kind": kind}]}
    return [{"type": "item.started", "item": dict(item, status="in_progress")},
            {"type": "item.completed", "item": dict(item, status="completed")}]


def cat(path):
    return "/bin/cat %s" % shlex.quote(path)


ENTRY_RE = re.compile(
    r"^(?P<noun>command|later command|file change|later file change) (?P<index>\d+) of "
    r"(?P<total>\d+): (?P<id>\S+) · started at log line (?P<start>\d+) · completed at log line "
    r"(?P<done>\d+) \((?P<outcome>[^)]*)\) · (?P<lines>\d+) line\(s\), (?P<chars>\d+) "
    r"character\(s\)(?: · ESCAPED: (?P<escaped>\d+) character\(s\) a terminal could hide written "
    r"\\xHH, \\uHHHH or \\UHHHHHHHH, and every backslash doubled)?$")
# what a terminal could hide or redraw (a newline and a tab aside): no output line may hold one
HIDING = ("Cc", "Cf", "Co", "Cs", "Cn", "Zl", "Zp")


def hidden(text):
    return [char for char in text if char not in "\n\t" and unicodedata.category(char) in HIDING]


def unescape(shown):
    """This suite's own decoder of an entry its header marks ESCAPED, written apart from the
    tool's so that a fault the two shared could not pass: `\\\\` is one backslash, and `\\x`,
    `\\u` and `\\U` give the character of two, four or eight lower-case hex digits; any other
    backslash fails the case."""
    out, at = [], 0
    while at < len(shown):
        if shown[at] != "\\":
            out.append(shown[at])
            at += 1
            continue
        kind = shown[at + 1:at + 2]
        if kind == "\\":
            out.append("\\")
            at += 2
            continue
        width = {"x": 2, "u": 4, "U": 8}.get(kind, 0)
        digits = shown[at + 2:at + 2 + width]
        check(width and len(digits) == width and all(c in "0123456789abcdef" for c in digits),
              "a backslash at %d of %r starts no escape" % (at, shown))
        out.append(chr(int(digits, 16)))
        at += 2 + width
    return "".join(out)


def parse(out):
    """The output's parts: its first line, the entries (each with its printed text rebuilt from
    its indented lines, as `shown`, and the command it stands for, as `text`: the printed text
    itself, or for an entry marked ESCAPED the printed text decoded), and the lines of each other
    kind."""
    lines = out.splitlines()
    result = {"first": lines[0] if lines else "", "entries": [], "lines": lines}
    for key, prefix in (("boundary", "boundary: "), ("not_boundary", "not a boundary: "),
                        ("near", "near miss: "), ("unread", "could not read: "),
                        ("record", "record: "), ("controls", "controls: "), ("count", "count: "),
                        ("changes", "file changes before the first-pass message: "),
                        ("later_changes", "file changes after the first-pass message: ")):
        result[key] = [line for line in lines if line.startswith(prefix)]
    index = 0
    while index < len(lines):
        match = ENTRY_RE.match(lines[index])
        if not match:
            index += 1
            continue
        count = int(match.group("lines"))
        block = lines[index + 1:index + 1 + count]
        check(len(block) == count and all(row.startswith(INDENT) for row in block),
              "entry %r: its %d indented line(s) are not all there: %r" % (lines[index], count,
                                                                          block))
        entry = dict(match.groupdict())
        entry["shown"] = "\n".join(row[len(INDENT):] for row in block)
        entry["escaped"] = int(entry["escaped"] or 0)
        entry["text"] = unescape(entry["shown"]) if entry["escaped"] else entry["shown"]
        result["entries"].append(entry)
        index += 1 + count
    return result


def listed(out, noun="command"):
    return [e for e in parse(out)["entries"] if e["noun"] == noun]


# ------------------------------------------------------------------ the acceptance records ---
# Structural copies of the event logs of the two acceptance runs of 12 October 2026, kept outside
# this folder with the run's records: the first (126 lines, sha256 46dcc142d16139012c95545716ef6a9
# 2fdcab9b5671be769ae2366e767d2cd86) and the second (124 lines, sha256 a289857c389eb6027077a011306d
# 7fc77733fe883261b817741fb22f8167fb7a). Every event is kept in order, with every item id, type,
# status and exit code, and every command's text byte for byte, except that the frozen copies'
# folder reads /acceptance-fixture/input and the CONTROL+ heading, the load marker and the negative
# token are renamed; outputs, the usage object, the thread id and the agent messages' prose are not
# copied (the first-pass message keeps its lines, its P1- ids and its END line). Each copy was
# checked against its original under those substitutions alone when it was made. Built by
# copy_bytes below, each copy's sha256 is pinned; a change to a table fails the case that checks it.

REAL1_EVENTS = """
thread turn m:item_0 s:item_1 c:item_1:completed:0 s:item_2 c:item_2:completed:0 s:item_3
s:item_4 c:item_3:completed:0 c:item_4:completed:0 s:item_5 c:item_5:completed:0 s:item_6
c:item_6:completed:0 m:item_7 s:item_8 c:item_8:completed:0 s:item_9 c:item_9:completed:0
s:item_10 c:item_10:completed:0 b:item_11 s:item_12 c:item_12:completed:0 s:item_13
c:item_13:completed:0 s:item_14 c:item_14:completed:0 s:item_15 c:item_15:completed:0 s:item_16
s:item_17 c:item_16:completed:0 c:item_17:completed:0 m:item_18 s:item_19 s:item_20
c:item_19:completed:0 c:item_20:completed:0 s:item_21 c:item_21:completed:0 s:item_22
c:item_22:completed:0 s:item_23 s:item_24 s:item_25 c:item_23:completed:0 c:item_24:completed:0
c:item_25:completed:0 s:item_26 c:item_26:completed:0 s:item_27 c:item_27:completed:0 s:item_28
c:item_28:completed:0 s:item_29 c:item_29:completed:0 s:item_30 c:item_30:completed:0 m:item_31
s:item_32 c:item_32:completed:0 s:item_33 c:item_33:completed:0 s:item_34 c:item_34:completed:0
s:item_35 c:item_35:completed:0 s:item_36 c:item_36:completed:0 s:item_37 c:item_37:completed:0
s:item_38 c:item_38:completed:0 m:item_39 s:item_40 c:item_40:completed:0 s:item_41
c:item_41:completed:0 s:item_42 c:item_42:completed:0 s:item_43 c:item_43:completed:0 s:item_44
c:item_44:completed:0 s:item_45 c:item_45:completed:0 s:item_46 c:item_46:completed:0 m:item_47
s:item_48 c:item_48:completed:0 s:item_49 c:item_49:completed:0 s:item_50 c:item_50:completed:0
s:item_51 c:item_51:completed:0 s:item_52 c:item_52:completed:0 s:item_53 c:item_53:completed:0
s:item_54 c:item_54:completed:0 s:item_55 c:item_55:completed:0 s:item_56 s:item_57
c:item_56:completed:0 c:item_57:completed:0 s:item_58 c:item_58:completed:0 s:item_59
c:item_59:completed:0 s:item_60 c:item_60:completed:0 m:item_61 s:item_62 c:item_62:completed:0
s:item_63 c:item_63:completed:0 s:item_64 c:item_64:completed:0 m:item_65 done
""".split()
REAL1_COMMANDS = {
    'item_1': (
        "/bin/zsh -lc '/usr/bin/wc -l -c /acceptance-fixture/input/CLAUDE"
        ".md'"
    ),
    'item_2': (
        "/bin/zsh -lc '/usr/bin/nl -ba /acceptance-fixture/input/CLAUDE.m"
        "d'"
    ),
    'item_3': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 1 && NR <= 200 {printf \\"%5d\\\\'
        't%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/CLAUDE.md"'
    ),
    'item_4': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 201 && NR <= 380 {printf \\"%5d'
        '\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/CLAUDE.md"'
    ),
    'item_5': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 381 && NR <= 570 {printf \\"%5d'
        '\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/CLAUDE.md"'
    ),
    'item_6': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 571 && NR <= 754 {printf \\"%5d'
        '\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/CLAUDE.md"'
    ),
    'item_8': (
        '/bin/zsh -lc "rg --no-ignore -n -F -e \'## 8. Section heading\' -e'
        " 'na0000000000000000' -e 'LOAD-MARKER-v1' /acceptance-fixture/in"
        'put/CLAUDE.md"'
    ),
    'item_9': (
        '/bin/zsh -lc "/usr/bin/python3 -B -c \'from pathlib import Path; '
        'p=Path(\\"/acceptance-fixture/input/CLAUDE.md\\"); s=p.read_text()'
        '; lines=s.splitlines(); positive=\\"## 8. Section heading\\"; nega'
        'tive=\\"na0000000000000000\\"; print(\\"files_read=1; lines=\\"+str('
        'len(lines))+\\"; bytes=\\"+str(len(s.encode()))); print(\\"CONTROL+'
        ' count=\\"+str(s.count(positive))+\\"; lines=\\"+str([i for i,x in '
        'enumerate(lines,1) if positive in x])); print(\\"negative_control'
        '_count=\\"+str(s.count(negative))); print(\\"marker_present_withou'
        't_import=\\"+str(\\"LOAD-MARKER-v1\\" in s.rsplit(\\"@CUSTOMISATION.'
        'md\\",1)[0])); begins=[i for i,x in enumerate(lines,1) if x==\\"<"'
        '\'!-- vault-local:begin -->"]; ends=[i for i,x in enumerate(lines'
        ',1) if x=="<!-- vault-local:end -->"]; print("local_blocks="+str'
        '(len(begins))+"; closing_markers="+str(len(ends))); print("repea'
        'ted_contract_clauses="+str({x:s.count(x) for x in ["**Read it by'
        ' need, in four modes.**", "**Keep the entry small**", "- **Adopt'
        'ed add-ons**", "**Adoption clause (2026-09-05):**"]})); print("l'
        'ocal_block_body_bytes="+str(sum(len(("\'"\\\\n\\".join(lines[a:b-1])'
        '+\\"\\\\n\\").encode()) for a,b in zip(begins,ends))))\'"'
    ),
    'item_10': (
        '/bin/zsh -lc "/usr/bin/awk \'BEGIN {positive=\\"## 8. Section head'
        'ing\\"; negative=\\"na0000000000000000\\"} {lines++; if (index("\'$0'
        ',positive)) {pos++; print "CONTROL+ " FILENAME ":" FNR ":" $0} i'
        'f (index($0,negative)) neg++; if (index($0,"LOAD-MARKER-v1")) {m'
        'arker++; print "schema_marker_line=" FNR} if ($0=="<!-- vault-lo'
        'cal:begin -->") begins++; if ($0=="<!-- vault-local:end -->") en'
        'ds++; if (index($0,"**Read it by need, in four modes.**")) routi'
        'ng++; if (index($0,"**Keep the entry small**")) logshape++; if ('
        'index($0,"- **Adopted add-ons**")) addons++; if (index($0,"**Ado'
        'ption clause (2026-09-05):**")) adoption++} END {print "files_re'
        'ad=1; lines=" lines; print "CONTROL+ count=" pos+0; print "negat'
        'ive_control_matching_lines=" neg+0; print "schema_marker_count="'
        ' marker+0; print "local_blocks=" begins+0 "; closing_markers=" e'
        'nds+0; print "routing_clause_count=" routing+0 "; log_shape_clau'
        'se_count=" logshape+0 "; addon_clause_count=" addons+0 "; adopti'
        'on_clause_count=" adoption+0; if (pos!=1 || lines!=754) exit 2}\''
        '"\' /acceptance-fixture/input/CLAUDE.md"'
    ),
    'item_12': (
        "/bin/zsh -lc '/usr/bin/wc -l -c /acceptance-fixture/input/known-"
        'issues.md /acceptance-fixture/input/check-lifecycle.md /acceptan'
        "ce-fixture/input/deep-lint-latest.md'"
    ),
    'item_13': (
        "/bin/zsh -lc '/usr/bin/nl -ba /acceptance-fixture/input/deep-lin"
        "t-latest.md'"
    ),
    'item_14': (
        "/bin/zsh -lc '/usr/bin/nl -ba /acceptance-fixture/input/check-li"
        "fecycle.md'"
    ),
    'item_15': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 1 && NR <= 100 {printf \\"%5d\\\\'
        't%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issues.md'
        '"'
    ),
    'item_16': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 101 && NR <= 200 {printf \\"%5d'
        '\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issues.'
        'md"'
    ),
    'item_17': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 201 && NR <= 300 {printf \\"%5d'
        '\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issues.'
        'md"'
    ),
    'item_19': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 301 && NR <= 400 {printf \\"%5d'
        '\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issues.'
        'md"'
    ),
    'item_20': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 401 && NR <= 500 {printf \\"%5d'
        '\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issues.'
        'md"'
    ),
    'item_21': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 501 && NR <= 600 {printf \\"%5d'
        '\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issues.'
        'md"'
    ),
    'item_22': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 601 && NR <= 700 {printf \\"%5d'
        '\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issues.'
        'md"'
    ),
    'item_23': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 776 && NR <= 850 {printf \\"%5d'
        '\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issues.'
        'md"'
    ),
    'item_24': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 701 && NR <= 775 {printf \\"%5d'
        '\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issues.'
        'md"'
    ),
    'item_25': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 630 && NR <= 659 {printf \\"%5d'
        '\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issues.'
        'md"'
    ),
    'item_26': (
        '/bin/zsh -lc "/usr/bin/awk \'NR == 629 || (NR >= 851 && NR <= 950'
        ') {printf \\"%5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/inpu'
        't/known-issues.md"'
    ),
    'item_27': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 951 && NR <= 1050 {printf \\"%5'
        'd\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issues'
        '.md"'
    ),
    'item_28': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 969 && NR <= 1037 {printf \\"%5'
        'd\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issues'
        '.md"'
    ),
    'item_29': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 1051 && NR <= 1150 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_30': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 1151 && NR <= 1250 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_32': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 1251 && NR <= 1350 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_33': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 1351 && NR <= 1450 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_34': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 1390 && NR <= 1395 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_35': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 1451 && NR <= 1525 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_36': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 1526 && NR <= 1625 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_37': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 1626 && NR <= 1725 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_38': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 1726 && NR <= 1825 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_40': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 1826 && NR <= 1925 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_41': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 1926 && NR <= 2025 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_42': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 2026 && NR <= 2125 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_43': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 2126 && NR <= 2225 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_44': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 2226 && NR <= 2325 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_45': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 2326 && NR <= 2425 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_46': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 2426 && NR <= 2525 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_48': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 2526 && NR <= 2625 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_49': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 2626 && NR <= 2725 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_50': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 2726 && NR <= 2825 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_51': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 2826 && NR <= 2925 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_52': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 2926 && NR <= 3025 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_53': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 3026 && NR <= 3125 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_54': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 3126 && NR <= 3225 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_55': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 3226 && NR <= 3325 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_56': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 3290 && NR <= 3300 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_57': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 3326 && NR <= 3360 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_58': (
        '/bin/zsh -lc "/usr/bin/awk \'NR >= 3361 && NR <= 3396 {printf \\"%'
        '5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known-issue'
        's.md"'
    ),
    'item_59': (
        '/bin/zsh -lc "rg --no-ignore -n -i -o -e \'LOAD-MARKER-v1|never r'
        'e-read|re-reads|rewrite the link|When unsure|Markdown report|eve'
        'ry report|vault-local blocks|public twins\' -e \'"\'^## Open$\'"\' -e'
        ' \'"\'^## Closed$\'"\' -e \'"\'^## 8\'"\\\\. Section heading"\'$\'"\' /accep'
        'tance-fixture/input/CLAUDE.md /acceptance-fixture/input/known-is'
        'sues.md /acceptance-fixture/input/deep-lint-latest.md"'
    ),
    'item_60': (
        '/bin/zsh -lc "/usr/bin/awk \'BEGIN {p[1]=\\"LOAD-MARKER-v1\\";p[2]='
        '\\"never re-read\\";p[3]=\\"re-reads\\";p[4]=\\"rewrite the link\\";p['
        '5]=\\"When unsure\\";p[6]=\\"Markdown report\\";p[7]=\\"every report\\'
        '";p[8]=\\"vault-local blocks\\";p[9]=\\"public twins\\"} FNR==1 {fil'
        'es++} {seen[FILENAME]++; if (FILENAME ~ /CLAUDE.md"\'$/) {if ($0='
        '="## 8. Section heading") {control++;print "CONTROL+ " FILENAME '
        '":" FNR ":" $0} if (index($0,"na0000000000000000")) negative++; '
        'next} if ($0=="## Open" || $0=="## Closed") {sectioncontrols++; '
        'print "comparison_control " FILENAME ":" FNR ":" $0} for(i=1;i<='
        '9;i++) if(index(tolower($0),tolower(p[i]))) counts[i]++} END {pr'
        'int "files_scanned=" files;for(f in seen) print "lines_scanned "'
        ' f "=" seen[f];print "CONTROL+ count=" control+0 "; comparison_s'
        'ection_controls=" sectioncontrols+0;print "negative_control_occu'
        'rrences_in_reading_list=" negative+0;for(i=1;i<=9;i++) print "co'
        'mparison_matching_lines [" p[i] "]=" counts[i]+0;if(control!=1 |'
        '| sectioncontrols!=2) exit 2}\'"\' /acceptance-fixture/input/CLAUD'
        'E.md /acceptance-fixture/input/known-issues.md /acceptance-fixtu'
        're/input/deep-lint-latest.md"'
    ),
    'item_62': (
        '/bin/zsh -lc "/usr/bin/awk \'NR < 754 {scanned++;if("\'$0=="## 8. '
        'Section heading"){control++;print "CONTROL+ " FILENAME ":" FNR "'
        ':" $0}if(index($0,"LOAD-MARKER-v1")){marker++;print "marker_with'
        'out_import " FILENAME ":" FNR ":" $0}if(index($0,"na000000000000'
        '0000"))negative++}END{print "schema_prefix_lines=" scanned "; CO'
        'NTROL+=" control+0 "; marker_without_import=" marker+0 "; negati'
        've=" negative+0;if(scanned!=753 || control!=1 || marker!=1)exit '
        '2}\'"\' /acceptance-fixture/input/CLAUDE.md"'
    ),
    'item_63': (
        '/bin/zsh -lc "/usr/bin/awk \'NR==1550 || NR==1557 || NR==1562 || '
        'NR==1622 || NR==1628 {printf \\"%5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acce'
        'ptance-fixture/input/known-issues.md"'
    ),
    'item_64': (
        '/bin/zsh -lc "/usr/bin/awk \'NR==1038 || (NR>=290 && NR<=294) || '
        '(NR>=597 && NR<=601) || (NR>=727 && NR<=731) || (NR>=1680 && NR<'
        '=1684) || (NR>=2141 && NR<=2145) || (NR>=3079 && NR<=3083) {prin'
        'tf \\"%5d\\\\t%s\\\\n\\", NR, "\'$0}\'"\' /acceptance-fixture/input/known'
        '-issues.md"'
    ),
}

REAL1_BOUNDARY = (
    "PASS 1 FINDINGS\n\n" + "".join("P1-%d (finding text not copied)\n\n" % n for n in range(1, 8))
    + "Due items: none supplied.\nUnregistered items: none supplied.\n\nEND PASS 1: 7 findings")
REAL1_SHA256 = "39564357feb98fabcc3d5fe3991527771fd2b61a4c1ac5732a50b93d54e9afe3"

REAL2_EVENTS = """
thread turn m:item_0 s:item_1 c:item_1:completed:0 s:item_2 s:item_3 c:item_2:completed:0
c:item_3:completed:0 m:item_4 s:item_5 c:item_5:completed:0 s:item_6 c:item_6:completed:0
s:item_7 c:item_7:completed:0 s:item_8 c:item_8:completed:0 m:item_9 s:item_10
c:item_10:completed:0 s:item_11 c:item_11:completed:0 b:item_12 s:item_13 c:item_13:completed:0
s:item_14 c:item_14:completed:0 s:item_15 s:item_16 c:item_15:completed:0 c:item_16:completed:0
s:item_17 c:item_17:completed:0 m:item_18 s:item_19 c:item_19:completed:0 s:item_20
c:item_20:completed:0 s:item_21 c:item_21:completed:0 s:item_22 c:item_22:completed:0 s:item_23
c:item_23:completed:0 s:item_24 c:item_24:completed:0 s:item_25 c:item_25:completed:0 s:item_26
c:item_26:completed:0 m:item_27 s:item_28 c:item_28:completed:0 s:item_29 c:item_29:completed:0
s:item_30 c:item_30:completed:0 s:item_31 c:item_31:completed:0 s:item_32 s:item_33
c:item_32:completed:0 c:item_33:completed:0 s:item_34 c:item_34:completed:0 s:item_35
c:item_35:completed:0 m:item_36 s:item_37 c:item_37:completed:0 s:item_38 c:item_38:completed:0
s:item_39 c:item_39:completed:0 s:item_40 c:item_40:completed:0 s:item_41 c:item_41:completed:0
m:item_42 s:item_43 c:item_43:completed:0 s:item_44 c:item_44:completed:0 s:item_45
c:item_45:completed:0 s:item_46 c:item_46:completed:0 s:item_47 c:item_47:completed:0 s:item_48
c:item_48:completed:0 s:item_49 c:item_49:completed:0 s:item_50 c:item_50:completed:0 s:item_51
c:item_51:completed:0 m:item_52 s:item_53 c:item_53:completed:0 s:item_54 c:item_54:completed:0
s:item_55 c:item_55:completed:0 s:item_56 c:item_56:completed:0 s:item_57 c:item_57:completed:0
s:item_58 c:item_58:completed:0 s:item_59 c:item_59:completed:0 s:item_60 c:item_60:completed:0
m:item_61 s:item_62 s:item_63 c:item_63:completed:0 c:item_62:completed:0 s:item_64
c:item_64:completed:0 m:item_65 done
""".split()
REAL2_COMMANDS = {
    'item_1': "/bin/zsh -lc '/usr/bin/nl -ba /acceptance-fixture/input/CLAUDE.md'",
    'item_2': (
        '/bin/zsh -lc "/usr/bin/sed -n \'200,390{=;p;}\' /acceptance-fixture/inpu'
        't/CLAUDE.md"'
    ),
    'item_3': (
        '/bin/zsh -lc "/usr/bin/sed -n \'391,580{=;p;}\' /acceptance-fixture/inpu'
        't/CLAUDE.md"'
    ),
    'item_5': (
        '/bin/zsh -lc "/usr/bin/sed -n \'581,754{=;p;}\' /acceptance-fixture/inpu'
        't/CLAUDE.md"'
    ),
    'item_6': (
        '/bin/zsh -lc "/usr/bin/sed -n \'1,199{=;p;}\' /acceptance-fixture/input/'
        'CLAUDE.md"'
    ),
    'item_7': (
        '/bin/zsh -lc "rg --no-ignore --fixed-strings --line-number -e \'## 8. S'
        "ection heading' -e 'na0000000000000000' /acceptance-fixture/input/CLAU"
        'DE.md"'
    ),
    'item_8': (
        '/bin/zsh -lc "/usr/bin/python3 -c \'from pathlib import Path; p=Path(\\"'
        '/acceptance-fixture/input/CLAUDE.md\\"); t=p.read_text(); lines=t.split'
        'lines(); print(\\"files_read=1 lines=\\"+str(len(lines))+\\" utf8_bytes=\\'
        '"+str(len(t.encode()))); print(\\"CONTROL+ heading_count=\\"+str(t.count'
        '(\\"## 8. Section heading\\"))); print(\\"negative_token_count=\\"+str(t.c'
        'ount(\\"na0000000000000000\\"))); print(\\"load_marker_occurrences=\\"+str'
        '(t.count(\\"LOAD-MARKER-v1\\"))); pairs=[(192,194),(348,350),(435,437),('
        '676,678)]; import difflib; total=0; print(\\"pair | identical_word_toke'
        'ns | total_words_first | total_words_second\\");\nfor a,b in pairs:\n x=l'
        'ines[a-1].split(); y=lines[b-1].split(); n=sum(m.size for m in difflib'
        '.SequenceMatcher(None,x,y,autojunk=False).get_matching_blocks()); tota'
        'l+=n; print(str(a)+\\"/\\"+str(b)+\\" | \\"+str(n)+\\" | \\"+str(len(x))+\\" '
        '| \\"+str(len(y)))\nprint(\\"identical_word_tokens_across_selected_pairs='
        '\\"+str(total)); print(\\"line_435_is_exact_prefix_of_437=\\"+str(lines[4'
        '36].startswith(lines[434])))\'"'
    ),
    'item_10': "/bin/zsh -lc '/usr/bin/wc -l -c /acceptance-fixture/input/CLAUDE.md'",
    'item_11': (
        '/bin/zsh -lc "/usr/bin/awk \'index("\'$0,"## 8. Section heading") {posit'
        'ive++; print "CONTROL+ line " NR ": " $0} index($0,"na0000000000000000'
        '") {negative++} index($0,"LOAD-MARKER-v1") {marker++; print "marker li'
        'ne " NR ": " $0} NR==435 {base=$0; words=NF} NR==437 {print "line_435_'
        'exact_prefix_of_437=" (index($0,base)==1 ? "true" : "false"); print "d'
        'uplicated_whitespace_words=" words} END {print "files_read=1 lines=" N'
        'R; print "CONTROL+ count=" positive+0; print "negative_token_count=" n'
        'egative+0; print "load_marker_count=" marker+0}\'"\' /acceptance-fixture'
        '/input/CLAUDE.md"'
    ),
    'item_13': (
        "/bin/zsh -lc '/usr/bin/wc -l -c /acceptance-fixture/input/known-issues"
        '.md /acceptance-fixture/input/check-lifecycle.md /acceptance-fixture/i'
        "nput/deep-lint-latest.md'"
    ),
    'item_14': (
        "/bin/zsh -lc '/usr/bin/nl -ba /acceptance-fixture/input/check-lifecycl"
        "e.md'"
    ),
    'item_15': (
        "/bin/zsh -lc '/usr/bin/nl -ba /acceptance-fixture/input/deep-lint-late"
        "st.md'"
    ),
    'item_16': (
        '/bin/zsh -lc "/usr/bin/sed -n \'1,160{=;p;}\' /acceptance-fixture/input/'
        'known-issues.md"'
    ),
    'item_17': (
        '/bin/zsh -lc "/usr/bin/sed -n \'161,420{=;p;}\' /acceptance-fixture/inpu'
        't/known-issues.md"'
    ),
    'item_19': (
        '/bin/zsh -lc "/usr/bin/sed -n \'250,305{=;p;}\' /acceptance-fixture/inpu'
        't/known-issues.md"'
    ),
    'item_20': (
        '/bin/zsh -lc "/usr/bin/sed -n \'421,550{=;p;}\' /acceptance-fixture/inpu'
        't/known-issues.md"'
    ),
    'item_21': (
        '/bin/zsh -lc "/usr/bin/sed -n \'551,680{=;p;}\' /acceptance-fixture/inpu'
        't/known-issues.md"'
    ),
    'item_22': (
        '/bin/zsh -lc "/usr/bin/sed -n \'623,634{=;p;}\' /acceptance-fixture/inpu'
        't/known-issues.md"'
    ),
    'item_23': (
        '/bin/zsh -lc "/usr/bin/sed -n \'681,780{=;p;}\' /acceptance-fixture/inpu'
        't/known-issues.md"'
    ),
    'item_24': (
        '/bin/zsh -lc "/usr/bin/sed -n \'781,880{=;p;}\' /acceptance-fixture/inpu'
        't/known-issues.md"'
    ),
    'item_25': (
        '/bin/zsh -lc "/usr/bin/sed -n \'881,980{=;p;}\' /acceptance-fixture/inpu'
        't/known-issues.md"'
    ),
    'item_26': (
        '/bin/zsh -lc "/usr/bin/sed -n \'981,1060{=;p;}\' /acceptance-fixture/inp'
        'ut/known-issues.md"'
    ),
    'item_28': (
        '/bin/zsh -lc "/usr/bin/sed -n \'1061,1160{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_29': (
        '/bin/zsh -lc "/usr/bin/sed -n \'1161,1240{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_30': (
        '/bin/zsh -lc "/usr/bin/sed -n \'1241,1340{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_31': (
        '/bin/zsh -lc "/usr/bin/sed -n \'1341,1440{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_32': (
        '/bin/zsh -lc "/usr/bin/sed -n \'1402{=;p;}\' /acceptance-fixture/input/k'
        'nown-issues.md"'
    ),
    'item_33': (
        '/bin/zsh -lc "/usr/bin/sed -n \'1441,1540{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_34': (
        '/bin/zsh -lc "/usr/bin/sed -n \'1480,1499{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_35': (
        '/bin/zsh -lc "/usr/bin/sed -n \'1541,1610{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_37': (
        '/bin/zsh -lc "/usr/bin/sed -n \'1611,1680{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_38': (
        '/bin/zsh -lc "/usr/bin/sed -n \'1681,1750{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_39': (
        '/bin/zsh -lc "/usr/bin/sed -n \'1751,1820{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_40': (
        '/bin/zsh -lc "/usr/bin/sed -n \'1821,1910{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_41': (
        '/bin/zsh -lc "/usr/bin/sed -n \'1911,2000{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_43': (
        '/bin/zsh -lc "/usr/bin/sed -n \'2001,2090{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_44': (
        '/bin/zsh -lc "/usr/bin/sed -n \'2091,2180{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_45': (
        '/bin/zsh -lc "/usr/bin/sed -n \'2181,2270{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_46': (
        '/bin/zsh -lc "/usr/bin/sed -n \'2271,2360{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_47': (
        '/bin/zsh -lc "/usr/bin/sed -n \'2361,2450{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_48': (
        '/bin/zsh -lc "/usr/bin/sed -n \'2451,2540{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_49': (
        '/bin/zsh -lc "/usr/bin/sed -n \'2541,2630{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_50': (
        '/bin/zsh -lc "/usr/bin/sed -n \'2631,2720{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_51': (
        '/bin/zsh -lc "/usr/bin/sed -n \'2721,2810{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_53': (
        '/bin/zsh -lc "/usr/bin/sed -n \'2811,2900{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_54': (
        '/bin/zsh -lc "/usr/bin/sed -n \'2901,2990{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_55': (
        '/bin/zsh -lc "/usr/bin/sed -n \'2991,3080{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_56': (
        '/bin/zsh -lc "/usr/bin/sed -n \'3081,3170{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_57': (
        '/bin/zsh -lc "/usr/bin/sed -n \'3171,3260{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_58': (
        '/bin/zsh -lc "/usr/bin/sed -n \'3261,3350{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_59': (
        '/bin/zsh -lc "/usr/bin/sed -n \'3351,3444{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_60': (
        '/bin/zsh -lc "/usr/bin/sed -n \'3374,3379{=;p;}\' /acceptance-fixture/in'
        'put/known-issues.md"'
    ),
    'item_62': (
        '/bin/zsh -lc "/usr/bin/awk \'NR==17 || (NR>=30 && NR<=60) || (NR>=355 &'
        '& NR<=368) || NR==1463 || (NR>=1596 && NR<=1610) || (NR>=2189 && NR<=2'
        '193) || (NR>=2711 && NR<=2715) {print NR \\":\\" "\'$0}\'"\' /acceptance-fi'
        'xture/input/known-issues.md"'
    ),
    'item_63': (
        '/bin/zsh -lc "rg --no-ignore --line-number --ignore-case -e \'"\'^# Know'
        'n Issues\'"\' -e \'Markdown report|report inbox|every report|report desti'
        "nations|LOAD-MARKER-v1' /acceptance-fixture/input/known-issues.md /acc"
        'eptance-fixture/input/deep-lint-latest.md"'
    ),
    'item_64': (
        '/bin/zsh -lc "/usr/bin/awk \'FNR==1 {files++; print \\"FILE \\" FILENAME}'
        ' {lines[FILENAME]=FNR} "\'$0=="## 8. Section heading" {positive++; prin'
        't "CONTROL+ " FILENAME ":" FNR} $0=="## Open" || $0=="## Closed" {prin'
        't "SECTION " FILENAME ":" FNR ":" $0} FILENAME=="/acceptance-fixture/i'
        'nput/CLAUDE.md" && index($0,"na0000000000000000") {negative++} END {fo'
        'r (f in lines) print "LINES " lines[f] " " f; print "files_read=" file'
        's; print "CONTROL+ count=" positive+0; print "reading_list_negative_to'
        'ken_count=" negative+0}\'"\' /acceptance-fixture/input/CLAUDE.md /accept'
        'ance-fixture/input/known-issues.md /acceptance-fixture/input/check-lif'
        'ecycle.md /acceptance-fixture/input/deep-lint-latest.md"'
    ),
}
REAL2_BOUNDARY = (
    'PASS 1 FINDINGS\n\nP1-1 (finding text not copied)\n\nP1-2 (finding text no'
    't copied)\n\nP1-3 (finding text not copied)\n\nP1-4 (finding text not copi'
    'ed)\n\nP1-5 (finding text not copied)\n\nDue items: none supplied.\nUnregis'
    'tered items: none supplied.\n\nEND PASS 1: 5 findings\n'
)
REAL2_SHA256 = "3283c56bf87d9daf2565d00c5236c8d4ab6a9cce11853638e825439216a91afb"

ACCEPTANCE = (
    # name, events, commands, boundary text, sha256, hand-listed earlier ids, boundary (id, line)
    ("the first acceptance run", "REAL1", ["item_1", "item_2", "item_3", "item_4", "item_5",
                                           "item_6", "item_8", "item_9", "item_10"],
     ("item_11", 23), 126),
    ("the second acceptance run", "REAL2", ["item_1", "item_2", "item_3", "item_5", "item_6",
                                            "item_7", "item_8", "item_10", "item_11"],
     ("item_12", 24), 124),
)


def copy_bytes(prefix):
    """An acceptance record's structural copy, generated from its table."""
    events, commands, boundary = (globals()[prefix + suffix]
                                  for suffix in ("_EVENTS", "_COMMANDS", "_BOUNDARY"))
    lines = []
    for token in events:
        parts = token.split(":")
        if token == "thread":
            event = {"type": "thread.started", "thread_id": "thread-fixture"}
        elif token == "turn":
            event = {"type": "turn.started"}
        elif token == "done":
            event = {"type": "turn.completed", "usage": {}}
        elif parts[0] in ("m", "b"):
            event = {"type": "item.completed", "item": {
                "id": parts[1], "type": "agent_message",
                "text": boundary if parts[0] == "b" else "(agent message: its text not copied)"}}
        elif parts[0] == "s":
            event = {"type": "item.started", "item": {
                "id": parts[1], "type": "command_execution", "command": commands[parts[1]],
                "aggregated_output": "", "exit_code": None, "status": "in_progress"}}
        else:
            event = {"type": "item.completed", "item": {
                "id": parts[1], "type": "command_execution", "command": commands[parts[1]],
                "aggregated_output": "", "exit_code": int(parts[3]), "status": parts[2]}}
        lines.append(json.dumps(event))
    return ("\n".join(lines) + "\n").encode("utf-8")


# ------------------------------------------------------------------ cases --------------------

def case_listed_before_message(fx):
    """T1's shape on a small record: the commands started before the first-pass message are listed
    whole, in start order, with the count and the record's path; the boundary line names the
    message; a command after it is not listed; the record and controls lines are printed."""
    path = fx.log(START + command(1, cat("/v/CLAUDE.md")) + command(2, "/usr/bin/wc -l /v/a.md")
                  + [message(3, FINDINGS)] + command(4, cat("/v/late.md")) + END)
    code, out, _ = fx.run(path)
    result = parse(out)
    check(code == 0 and result["first"] == "COMMANDS BEFORE THE FIRST-PASS MESSAGE: 2 · record %s"
          % path, "exit %d: %r" % (code, result["first"]))
    check([(e["id"], e["text"]) for e in listed(out)]
          == [("item_1", wrapped(cat("/v/CLAUDE.md"))), ("item_2", wrapped("/usr/bin/wc -l "
                                                                           "/v/a.md"))],
          "the entries: %r" % listed(out))
    check(result["boundary"] == ["boundary: item_3, the first complete first-pass message, "
                                 "completed at log line 7 · its last line `END PASS 1: 2 "
                                 "findings` · 2 distinct P1- id(s), matching its count"],
          "the boundary line: %r" % result["boundary"])
    check(result["count"] == ["count: 2 command(s) started before the first-pass message, each "
                              "listed once, in the order it started, from the record %s" % path],
          "the count line: %r" % result["count"])
    check("item_4" not in out and "late.md" not in out, "a command after the message was listed")
    check(result["record"] and result["controls"], "the record or controls line is missing")


def case_spanning_and_late(fx):
    """T2: a command started before the message and finished after it is listed, at its start;
    a planted command after the message is not listed (the control: --whole-run lists it, apart)."""
    path = fx.log(START + command(1, cat("/v/spans.md"), phase="started") + [message(2, FINDINGS)]
                  + command(1, cat("/v/spans.md"), phase="completed")
                  + command(3, cat("/v/late.md")) + END)
    code, out, _ = fx.run(path)
    entries = listed(out)
    check(code == 0 and [(e["id"], e["start"], e["done"]) for e in entries]
          == [("item_1", "3", "5")], "the spanning command: %d %r" % (code, entries))
    check(parse(out)["boundary"][0].startswith("boundary: item_2, the first complete first-pass "
                                               "message, completed at log line 4"),
          "the boundary: %r" % parse(out)["boundary"])
    check("late.md" not in out, "the command after the message was listed: %r" % out[:600])
    code, out, _ = fx.run(path, "--whole-run")
    check(code == 0 and [e["id"] for e in listed(out)] == ["item_1"]
          and [e["id"] for e in listed(out, "later command")] == ["item_3"]
          and "COMMANDS AFTER THE FIRST-PASS MESSAGE (--whole-run): 1 · record %s" % path in out,
          "the control under --whole-run: %d %r" % (code, out[:800]))


def case_start_order_and_executions(fx):
    """T10's invariants: entries come in the order each command started, never the order they
    completed, and one entry per execution: the same text run twice is listed twice."""
    same = cat("/v/a.md")
    path = fx.log(START + command(1, same, phase="started") + command(2, cat("/v/b.md"),
                                                                      phase="started")
                  + command(2, cat("/v/b.md"), phase="completed")
                  + command(1, same, phase="completed")
                  + [message(3, "a progress note")] + command(4, same)
                  + [message(5, FINDINGS)] + END)
    code, out, _ = fx.run(path)
    entries = listed(out)
    check(code == 0 and [(e["id"], e["start"]) for e in entries]
          == [("item_1", "3"), ("item_2", "4"), ("item_4", "8")],
          "the order of start, or the executions: %d %r" % (code, entries))
    check(entries[0]["text"] == entries[2]["text"] == wrapped(same)
          and parse(out)["first"].startswith("COMMANDS BEFORE THE FIRST-PASS MESSAGE: 3 ·"),
          "the text run twice was not listed twice: %r" % entries)


VERBATIM = (
    "/usr/bin/python3 -c 'import sys\nfor a in sys.argv[1:]:\n    print(open(a).read())' /v/x.md",
    "/usr/bin/awk '{printf \"%5d\\t%s\\n\", NR, $0}' /v/x.md",
    "/usr/bin/grep -n \"quoted 'mixed' text\" '/v/a b.md'",
    "/bin/cat /v/café—notes.md",
    "/bin/cat /v/x.md\n",
)


def case_verbatim_text(fx):
    """Each entry is the record's command text exactly, line for line: newlines, quotes,
    backslashes, a tab, accented and long-dash characters, a trailing newline and an unwrapped
    command print byte for byte, the header naming no encoding. A command holding a character a
    terminal could hide or redraw (an escape, a right-to-left override) prints in the declared
    encoding, which its header names with the count, and decodes back to the command."""
    events = list(START)
    for number, text in enumerate(VERBATIM, 1):
        events += command(number, text)
    events += command(6, "/bin/cat /v/plain.md\t/v/tabbed.md", raw=True)
    events += command(7, "/bin/cat /v/x.md\x1b[2K‮md.y", raw=True)
    events += [message(8, FINDINGS)] + END
    code, out, _ = fx.run(fx.log(events))
    entries = listed(out)
    check(code == 0 and len(entries) == 7, "exit %d, %d entries" % (code, len(entries)))
    for entry, text in zip(entries, [wrapped(t) for t in VERBATIM]
                           + ["/bin/cat /v/plain.md\t/v/tabbed.md"]):
        check(entry["shown"] == text and entry["escaped"] == 0
              and int(entry["chars"]) == len(text), "not byte for byte: %r for %r"
              % (entry["shown"], text))
    escaped = entries[6]
    check(escaped["escaped"] == 2 and escaped["shown"] == "/bin/cat /v/x.md\\x1b[2K\\u202emd.y"
          and escaped["text"] == "/bin/cat /v/x.md\x1b[2K‮md.y"
          and int(escaped["chars"]) == len(escaped["text"]), "the hidden characters: %r" % escaped)


# T11: the third build review's pair (a literal `\x1b` text before a real escape, and the reverse),
# which the first build printed alike, then commands mixing backslashes, escape-looking text and
# characters a terminal could hide, with some that hold nothing hidden and must print byte for byte
LOSSLESS_PAIR = ("/bin/echo \\x1b\x1b", "/bin/echo \x1b\\x1b")
LOSSLESS = LOSSLESS_PAIR + (
    "\\", "\\\\", "\\x1b", "\x1b", "\\\\x1b", "\\\x1b", "a\u202eb", "a\\u202eb", "\U000e0001",
    "\\U000e0001", "/bin/cat /v/a.md\x00", "/bin/cat /v/a.md\r/bin/cat /v/b.md", "tab\there\\t",
    "line\nline\\n\x0b", "\u2028x", "x\\u2028", "caf\u00e9 \\ \u00e9", "\\x\\u\\U\\")


def case_lossless_listing(fx):
    """T11, item 1 (the third build review's fourth finding): the review's two commands, which
    differ only in a literal escape-looking text beside a real escape character, print differently,
    each list as a whole, and each print decodes back to its command exactly; across commands
    mixing backslashes, escape-looking text and hidden characters, no two print alike and every
    print recovers its command; a command with nothing a terminal could hide prints byte for byte,
    its header naming no encoding, backslashes and all."""
    lists = []
    for text in LOSSLESS_PAIR:
        code, out, _ = fx.check_log(START + command(1, text, raw=True) + [message(2, FINDINGS)] + END)
        entries = listed(out)
        check(code == 0 and len(entries) == 1 and entries[0]["escaped"] == 1
              and entries[0]["text"] == text and entries[0]["shown"] != text,
              "%r: exit %d, %r" % (text, code, entries))
        lists.append([line for line in out.splitlines() if not line.startswith(("record: ",
                                                                                "COMMANDS BEFORE",
                                                                                "count: "))])
    check(lists[0] != lists[1], "the review's pair printed alike: %r" % lists)
    events = list(START)
    for number, text in enumerate(LOSSLESS, 1):
        events += command(number, text, raw=True)
    code, out, _ = fx.check_log(events + [message(len(LOSSLESS) + 1, FINDINGS)] + END)
    entries = listed(out)
    check(code == 0 and [e["text"] for e in entries] == list(LOSSLESS),
          "a print did not recover its command: %r" % [(e["shown"], t) for e, t in
                                                       zip(entries, LOSSLESS) if e["text"] != t])
    prints = [(e["shown"], e["escaped"]) for e in entries]
    check(len(set(prints)) == len(prints), "two commands printed alike: %r"
          % [p for p in prints if prints.count(p) > 1])
    plain = [(e, t) for e, t in zip(entries, LOSSLESS) if not hidden(t)]
    check(len(plain) >= 8 and all(e["escaped"] == 0 and e["shown"] == t for e, t in plain),
          "a command with nothing hidden was not printed byte for byte: %r"
          % [(e["shown"], t) for e, t in plain if e["shown"] != t or e["escaped"]])
    check(all(e["escaped"] == len(hidden(t)) for e, t in zip(entries, LOSSLESS) if hidden(t)),
          "an escaped entry's header miscounts its hidden characters")


def case_names_printed_safely(fx):
    """Item 1: an item id and a field name taken from the record that hold a character a terminal
    could hide print as their quoted repr, in an entry's header and in a could-not-read line, never
    raw (Fixture.run searches every output for such a character); a plain id prints as itself."""
    odd = "item_1\x1b[2K"
    events = command(1, cat("/v/a.md"))
    for event in events:
        event["item"]["id"] = odd
    code, out, _ = fx.check_log(START + events + command(2, cat("/v/b.md"))
                                + [message(3, FINDINGS)] + END)
    check(code == 0 and [e["id"] for e in listed(out)] == [repr(odd), "item_2"],
          "the ids as printed: %d %r" % (code, [e["id"] for e in listed(out)]))
    events = command(9, cat("/v/a.md"))
    events[0]["item"]["cwd\x1b"] = "/v"
    path = fx.log(START + events + [message(1, FINDINGS)] + END)
    out = unread_case(fx, path)
    check(any("holds fields outside the grammar (%s)" % repr("cwd\x1b") in row
              for row in parse(out)["unread"]), "the field name: %r" % parse(out)["unread"])


def case_no_first_pass_message(fx):
    """T3: a record with no first-pass message says so by name, prints no list and exits 3; a
    message that only resembles the heading is named as a near miss; a record with no item at all
    has no message either."""
    path = fx.log(START + [message(1, "I will read the slice.")] + command(2, cat("/v/a.md")) + END)
    code, out, _ = fx.run(path)
    check(code == 3 and parse(out)["first"] == "NO FIRST-PASS MESSAGE: %s holds no complete "
          "first-pass message among its 1 sent agent message(s); no list" % path,
          "no message: %d %r" % (code, out[:400]))
    check(not parse(out)["entries"] and "COMMANDS BEFORE" not in out and "a.md" not in out,
          "a list was printed with no message: %r" % out[:600])
    code, out, _ = fx.check_log(START + [message(1, "## PASS 1 FINDINGS\nP1-1 x\nEND PASS 1: 1 "
                                                    "finding")] + command(2, cat("/v/a.md")) + END)
    check(code == 3 and parse(out)["near"] == ["near miss: item_1 (log line 3), its first line "
                                               "'## PASS 1 FINDINGS' only resembles the heading"],
          "the near miss: %d %r" % (code, parse(out)["near"]))
    code, out, _ = fx.check_log(START + END)
    check(code == 3 and "among its 0 sent agent message(s)" in out, "no item: %d %r"
          % (code, out[:300]))


def case_cut_off_message_not_boundary(fx):
    """T3: a message under the heading cut off before its END line is not a boundary, and neither
    is one whose END line miscounts its ids: each is named on a `not a boundary:` line, the next
    complete message is the boundary, and the commands before it, those between included, are
    listed. A cut-off message with no complete one after it leaves no first-pass message."""
    for text, why in (("PASS 1 FINDINGS\nP1-1 x\nP1-2 y", "a message cut off before its end"),
                      ("PASS 1 FINDINGS\nP1-1 x\nEND PASS 1: 2 findings",
                       "its last line counts 2 finding(s), but it holds 1 distinct P1- id(s)")):
        path = fx.log(START + command(1, cat("/v/a.md")) + [message(2, text)]
                      + command(3, cat("/v/b.md")) + [message(4, FINDINGS)]
                      + command(5, cat("/v/c.md")) + END)
        code, out, _ = fx.run(path)
        result = parse(out)
        check(code == 0 and [e["id"] for e in listed(out)] == ["item_1", "item_3"],
              "%r: the commands before the complete message: %d %r" % (text, code, listed(out)))
        check(result["boundary"][0].startswith("boundary: item_4, the first complete first-pass "
                                               "message, completed at log line 8")
              and len(result["not_boundary"]) == 1
              and result["not_boundary"][0].startswith("not a boundary: item_2 (log line 5) "
                                                       "begins with `PASS 1 FINDINGS`, but ")
              and why in result["not_boundary"][0],
              "%r: the boundary lines: %r %r" % (text, result["boundary"], result["not_boundary"]))
    code, out, _ = fx.check_log(START + command(1, cat("/v/a.md"))
                                + [message(2, "PASS 1 FINDINGS\nP1-1 x")] + END)
    check(code == 3 and "NO FIRST-PASS MESSAGE" in out and "not a boundary: item_2" in out
          and not parse(out)["entries"], "a cut-off message alone: %d %r" % (code, out[:500]))


def case_zero_findings_boundary(fx):
    """T3: a complete first-pass message with zero findings is a boundary, and the commands before
    it are listed as usual; so is one finding counted in the singular."""
    for text, ids in (("PASS 1 FINDINGS\nDue items: none.\nEND PASS 1: 0 findings", 0),
                      ("PASS 1 FINDINGS\nP1-1 x\nEND PASS 1: 1 finding", 1)):
        code, out, _ = fx.check_log(START + command(1, cat("/v/a.md")) + command(2, cat("/v/b.md"))
                                    + [message(3, text)] + END)
        check(code == 0 and [e["id"] for e in listed(out)] == ["item_1", "item_2"]
              and "%d distinct P1- id(s), matching its count" % ids in out,
              "%r: %d %r" % (text, code, out[:500]))


def case_header_must_be_exact(fx):
    """Only a first line that is exactly the heading counts: the heading later in the text, or
    with a colon, bold marks or another case, is no boundary, and each is named as a near miss."""
    for text in ("PASS 1 FINDINGS:\nP1-1 x\nEND PASS 1: 1 finding",
                 "**PASS 1 FINDINGS**\nP1-1 x\nEND PASS 1: 1 finding",
                 "Here they are.\nPASS 1 FINDINGS\nP1-1 x\nEND PASS 1: 1 finding",
                 "pass 1 findings\nP1-1 x\nEND PASS 1: 1 finding"):
        code, out, _ = fx.check_log(START + [message(1, text)] + command(2, cat("/v/a.md")) + END)
        check(code == 3 and parse(out)["near"] and parse(out)["near"][0].startswith(
            "near miss: item_1 (log line 3), "), "%r: %d %r" % (text, code, out[:400]))


def case_near_miss_before_boundary_only(fx):
    """A message that resembles the first-pass message is named as a near miss when it comes
    before the boundary, where it may have been meant as the message; after the boundary it is
    not named, since the final report repeats the first-pass list under its own heading."""
    report = "## Report\n\n## Pass 1 findings\nPASS 1 FINDINGS\nP1-1 x\nEND PASS 1: 1 finding"
    code, out, _ = fx.check_log(START + [message(1, "**PASS 1 FINDINGS**\nP1-1 x")]
                                + command(2, cat("/v/a.md")) + [message(3, FINDINGS)]
                                + [message(4, report)] + END)
    check(code == 0 and parse(out)["near"] == ["near miss: item_1 (log line 3), its first line "
                                               "'**PASS 1 FINDINGS**' only resembles the heading"]
          and [e["id"] for e in listed(out)] == ["item_2"],
          "the near misses: %d %r" % (code, parse(out)["near"]))


def unread_case(fx, path, *expected):
    """A run that cannot read the record: exit 1, the COULD NOT READ line, each expected `could
    not read:` line, and no list."""
    code, out, _ = fx.run(path)
    result = parse(out)
    check(code == 1 and result["first"].startswith("COULD NOT READ: %s" % path)
          and result["first"].endswith("; no list"), "%s: %d %r" % (path, code, out[:400]))
    for line in expected:
        check(line in result["unread"], "%s: %r is not among %r" % (path, line, result["unread"]))
    check(not result["entries"] and "COMMANDS BEFORE" not in out and not result["boundary"],
          "%s: a list was printed: %r" % (path, out[:600]))
    return out


def case_unreadable_record(fx):
    """T4: a record that is missing, empty, blank, a folder, or (for any user but root) of mode
    000 gives `could not read` naming the record, exit 1 and no list."""
    cases = [(os.path.join(fx.logs, "absent.log"), "the record does not exist"),
             (fx.log([], name="empty.log"), "the record is empty"),
             (fx.log(["", "   "], name="blank.log"), "the record is empty")]
    folder = os.path.join(fx.logs, "a-folder.log")
    os.mkdir(folder)
    cases.append((folder, "the record cannot be opened (Is a directory)"))
    for path, why in cases:
        unread_case(fx, path, "could not read: %s: %s; no event was read" % (path, why))
    if os.geteuid() != 0:
        locked = fx.log(START + [message(1, FINDINGS)] + END, name="locked.log")
        os.chmod(locked, 0)
        try:
            unread_case(fx, locked, "could not read: %s: the record cannot be opened (Permission "
                                    "denied); no event was read" % locked)
        finally:
            os.chmod(locked, stat.S_IRUSR | stat.S_IWUSR)


def case_truncated_record(fx):
    """T4: a truncated record (cut before its final turn completes, ending on a torn line, a later
    turn left open, or a command never completed) gives `could not read` at the event's log line,
    exit 1 and no list; and (revision 7: the event log is a framed input, its one turn closing the
    record) so does a record that goes on past its turn with a whole second turn, which a cut
    between the turns would otherwise drop unseen. The control: the record completed in its one
    turn is listed."""
    # the body's lines: 1-2 the thread and turn, 3-4 item_1, 5 the message, 6-7 item_3
    body = START + command(1, cat("/v/a.md")) + [message(2, FINDINGS)] + command(3, cat("/v/b.md"))
    path = fx.log(body)
    unread_case(fx, path, "could not read: %s, log line 7: truncated: the turn started at log line "
                          "2 never completes, and the record stops at log line 7" % path)
    torn = fx.log(body + [json.dumps(END[0])[:-9]])
    out = unread_case(fx, torn, "could not read: %s, log line 8: truncated: the turn started at log "
                                "line 2 never completes, and the record stops at log line 8" % torn)
    check(any(line.startswith("could not read: %s, log line 8: an envelope that does not parse"
                              % torn) for line in parse(out)["unread"]),
          "the torn line is not named at its position: %r" % parse(out)["unread"])
    second = fx.log(body + END + [{"type": "turn.started"}] + command(4, cat("/v/c.md")))
    unread_case(fx, second, "could not read: %s, log line 11: truncated: the turn started at log "
                            "line 9 never completes, and the record stops at log line 11" % second)
    never = fx.log(body + command(4, cat("/v/c.md"), phase="started") + END)
    unread_case(fx, never, "could not read: %s, log line 8: item_4 starts at log line 8 and never "
                           "completes" % never)
    two = fx.log(body + END + [{"type": "turn.started"}] + command(4, cat("/v/c.md")) + END)
    unread_case(fx, two, "could not read: %s, log line 9: a second turn (the first started at log "
                         "line 2): a reviewer's record holds one turn, so a record that goes on "
                         "past it is outside the grammar" % two)
    code, out, _ = fx.check_log(body + END)
    check(code == 0 and [e["id"] for e in listed(out)] == ["item_1"],
          "the completed control: %d %r" % (code, out[:400]))


def case_malformed_evidence(fx):
    """T4: an event whose relevant fields are missing or malformed, before the message or after
    it, gives `could not read` naming the record and the event's log line, exit 1 and no list: a
    command event without its command text (on either event, or empty), an envelope that does not
    parse, one that is not an object, an event or item with no type or an unknown one, a field
    outside the grammar or one missing, a key given twice, an item with no id, a message without
    its text and a file change without its changes."""
    bare = {"id": "item_9", "type": "command_execution", "aggregated_output": "",
            "exit_code": None, "status": "in_progress"}
    done = dict(bare, exit_code=0, status="completed")
    hidden = json.dumps(command(9, cat("/v/a.md"), phase="completed")[0])
    twice = hidden[:-1] + ', "item": %s}' % json.dumps(command(9, cat("/v/b.md"),
                                                               phase="completed")[0]["item"])
    with_cwd = command(9, cat("/v/a.md"))
    with_cwd[0] = json.loads(json.dumps(with_cwd[0]))
    with_cwd[0]["item"]["cwd"] = "/v"
    # each plant with what must be named, at its first event's log line unless a second number
    # gives the plant's event that carries the defect
    plants = (
        ([{"type": "item.started", "item": bare}, {"type": "item.completed", "item": done}],
         "item_9, a command event without its command text"),
        (command(9, cat("/v/a.md"), phase="started") + [{"type": "item.completed",
                                                         "item": done}],
         "item_9, a command event without its command text", 1),
        (command(9, "   ", raw=True), "item_9, a command event without its command text"),
        (["{torn line"], "an envelope that does not parse as a JSON event"),
        (['["a list"]'], "an envelope that is not a JSON object"),
        ([{"item": {"id": "x", "type": "command_execution", "command": "/bin/cat /v/a.md"}}],
         "an event with no type"),
        ([{"type": "turn.failed", "error": {"message": "x"}}],
         "an event of unknown type 'turn.failed'"),
        ([{"type": "item.completed", "item": {"id": "item_9", "text": "x"}}], "an item with no type"),
        ([{"type": "item.completed", "item": {"id": "item_9", "type": "reasoning", "text": "x"}}],
         "an item of unknown type 'reasoning'"),
        (with_cwd, "item_9, a command_execution item, holds fields outside the grammar (cwd)"),
        ([{"type": "item.completed", "item": {"id": "item_9", "type": "agent_message"}}],
         "item_9, a sent agent message without its text"),
        ([{"type": "item.started", "item": {"id": "item_9", "type": "file_change",
                                            "status": "in_progress"}}],
         "item_9, a file change without its changes"),
        # the third build review's fourth finding: a file change holding one path that is an
        # integer, in both its events, once crashed the report; it is malformed evidence
        ([{"type": phase, "item": {"id": "item_9", "type": "file_change", "status": status,
                                   "changes": [{"path": "/v/a.md", "kind": "update"},
                                               {"path": 7, "kind": "update"}]}}
          for phase, status in (("item.started", "in_progress"), ("item.completed", "completed"))],
         "item_9, a file change whose path is not absolute"),
        ([{"type": "item.completed", "item": {"type": "agent_message", "text": "x"}}],
         "a agent_message item with no id"),
        ([{"type": "item.completed"}], "an item event with no item"),
        ([twice], "duplicate key 'item'"),
        # NaN is not JSON: a parser that took it would read an envelope no JSON reader agrees on
        (['{"type": "item.completed", "item": {"id": "item_9", "type": "agent_message", '
          '"text": "x", "n": NaN}}'], "an envelope that does not parse as a JSON event (NaN is "
                                      "not JSON)"),
    )
    for entry in plants:
        plant, expected = entry[0], entry[1]
        offset = entry[2] if len(entry) > 2 else 0
        for where in ("before", "after"):
            events = (START + (plant if where == "before" else []) + [message(1, FINDINGS)]
                      + (plant if where == "after" else []) + command(2, cat("/v/a.md")) + END)
            path = fx.log(events)
            line = (3 if where == "before" else 4) + offset
            out = unread_case(fx, path)
            check(any(row.startswith("could not read: %s, log line %d: " % (path, line))
                      and expected in row for row in parse(out)["unread"]),
                  "%r %s the message: not named at log line %d: %r"
                  % (expected, where, line, parse(out)["unread"]))


def case_changed_evidence(fx):
    """T4, T10: an item's command that changes across its events, an item whose type changes, an
    id used again after its completion and an item started twice each give `could not read` at
    the later event's log line, so no entry stands for more than one execution. The control:
    ordinary status, output and exit-code updates (a completed and a failed command) are listed."""
    path = fx.log(START + command(1, cat("/v/register.md"), phase="started")
                  + command(1, cat("/v/a.md"), phase="completed") + [message(2, FINDINGS)] + END)
    unread_case(fx, path, "could not read: %s, log line 4: item_1 changes its command between log "
                          "line 3 and log line 4" % path)
    path = fx.log(START + command(1, cat("/v/a.md"), phase="started") + change(1, "/v/a.md")[1:]
                  + [message(2, FINDINGS)] + END)
    out = unread_case(fx, path)
    check(any("item_1 changes its type from command_execution" in row
              for row in parse(out)["unread"]), "a changed type: %r" % parse(out)["unread"])
    path = fx.log(START + command(1, cat("/v/a.md")) + command(1, cat("/v/a.md"))
                  + [message(2, FINDINGS)] + END)
    out = unread_case(fx, path)
    check(any("item_1 has an event after its completion at log line 4" in row
              for row in parse(out)["unread"]), "a reused id: %r" % parse(out)["unread"])
    path = fx.log(START + command(1, cat("/v/a.md"), phase="started")
                  + command(1, cat("/v/a.md")) + [message(2, FINDINGS)] + END)
    out = unread_case(fx, path)
    check(any("item_1 starts again (first at log line 3)" in row for row in parse(out)["unread"]),
          "a second start: %r" % parse(out)["unread"])
    code, out, _ = fx.check_log(START + command(1, cat("/v/a.md"), output="many lines\n" * 20)
                                + command(2, "/bin/cat /nowhere/x.md", output="No such file",
                                          status="failed", exit_code=1)
                                + [message(3, FINDINGS)] + END)
    entries = listed(out)
    check(code == 0 and [(e["id"], e["outcome"]) for e in entries]
          == [("item_1", "completed, exit 0"), ("item_2", "failed, exit 1")],
          "ordinary updates: %d %r" % (code, out[:600]))


def case_file_changes_listed_apart(fx):
    """A file change before the message is listed apart, verbatim, with its own count, and the
    command count is unchanged; one after it is not listed (the control: --whole-run lists it)."""
    path = fx.log(START + command(1, cat("/v/a.md")) + change(2, "/v/wrote.md", kind="add")
                  + [message(3, FINDINGS)] + change(4, "/v/later.md") + END)
    code, out, _ = fx.run(path)
    changes = listed(out, "file change")
    check(code == 0 and [e["id"] for e in listed(out)] == ["item_1"]
          and parse(out)["first"].startswith("COMMANDS BEFORE THE FIRST-PASS MESSAGE: 1 ·"),
          "the commands: %d %r" % (code, out[:400]))
    check(parse(out)["changes"] == ["file changes before the first-pass message: 1"]
          and [(e["id"], json.loads(e["text"])) for e in changes]
          == [("item_2", [{"kind": "add", "path": "/v/wrote.md"}])] and "later.md" not in out,
          "the file changes: %r" % changes)
    code, out, _ = fx.run(path, "--whole-run")
    check([e["id"] for e in listed(out, "later file change")] == ["item_4"]
          and parse(out)["later_changes"] == ["file changes after the first-pass message: 1"],
          "the later file change under --whole-run: %r" % out[-600:])


def case_output_is_not_a_command(fx):
    """A command's output that quotes paths is not a command: the entry is the command's text, and
    the output appears nowhere."""
    code, out, _ = fx.check_log(START + command(1, cat("/v/a.md"), output="see /v/register.md")
                                + [message(2, FINDINGS)] + END)
    check(code == 0 and [e["text"] for e in listed(out)] == [wrapped(cat("/v/a.md"))]
          and "register.md" not in out, "an output was listed: %r" % out[:400])


def case_whole_run(fx):
    """--whole-run adds every command started after the message, in start order, in a list of its
    own with its count, for the smoke test on frozen copies; the earlier list is unchanged; without
    the flag no later command appears."""
    path = fx.log(START + command(1, cat("/v/a.md")) + [message(2, FINDINGS)]
                  + command(3, cat("/v/frozen/register.md"), phase="started")
                  + command(4, cat("/v/live/register.md"))
                  + command(3, cat("/v/frozen/register.md"), phase="completed") + END)
    code, plain, _ = fx.run(path)
    code_w, whole, _ = fx.run(path, "--whole-run")
    check(code == code_w == 0 and listed(plain) == listed(whole)
          and "register.md" not in plain, "the earlier list: %r %r" % (plain[:300], whole[:300]))
    later = listed(whole, "later command")
    check([(e["id"], e["text"]) for e in later]
          == [("item_3", wrapped(cat("/v/frozen/register.md"))),
              ("item_4", wrapped(cat("/v/live/register.md")))]
          and "count: 2 command(s) started after the first-pass message" in whole,
          "the later list: %r" % later)


def case_acceptance_records(fx):
    """T1: on the structural copy of each acceptance run's record (its sha256 checked), the list
    holds exactly the commands before the first-pass message: verbatim, in start order, one per
    execution, the count equal to the hand count recorded above (nine), the boundary at the
    message the design checks named; under --whole-run, every later command in start order."""
    for name, prefix, earlier, (boundary_id, boundary_line), total in ACCEPTANCE:
        data = copy_bytes(prefix)
        digest = hashlib.sha256(data).hexdigest()
        check(digest == globals()[prefix + "_SHA256"], "%s: the copy is not the pinned one: %s"
              % (name, digest))
        path = os.path.join(fx.logs, "%s.log" % prefix.lower())
        with open(path, "wb") as handle:
            handle.write(data)
        commands = globals()[prefix + "_COMMANDS"]
        code, out, _ = fx.run(path)
        entries = listed(out)
        check(code == 0 and len(earlier) == HAND_COUNT
              and parse(out)["first"] == "COMMANDS BEFORE THE FIRST-PASS MESSAGE: %d · record %s"
              % (HAND_COUNT, path), "%s: %d %r" % (name, code, parse(out)["first"]))
        check([e["id"] for e in entries] == earlier,
              "%s: the listed items %r, by hand %r" % (name, [e["id"] for e in entries], earlier))
        check([e["text"] for e in entries] == [commands[i] for i in earlier]
              and all(e["escaped"] == 0 for e in entries), "%s: a text is not verbatim" % name)
        starts = [int(e["start"]) for e in entries]
        check(starts == sorted(starts) and len(set(starts)) == len(starts),
              "%s: not in start order: %r" % (name, starts))
        check(parse(out)["boundary"][0].startswith(
            "boundary: %s, the first complete first-pass message, completed at log line %d"
            % (boundary_id, boundary_line)), "%s: the boundary %r" % (name, parse(out)["boundary"]))
        check(parse(out)["record"] and parse(out)["record"][0].startswith(
            "record: %s · %d line(s) · 1 turn(s)" % (path, total)), "%s: the record line %r"
              % (name, parse(out)["record"]))
        code, out, _ = fx.run(path, "--whole-run")
        later = [e["id"] for e in listed(out, "later command")]
        expected = [i for i in commands if i not in earlier]
        check(code == 0 and later == sorted(expected, key=lambda i: [
            t for t in globals()[prefix + "_EVENTS"] if t.startswith("s:")].index("s:" + i)),
              "%s: the later list %r" % (name, later))


def cut_record(fx, data, name, extra=(), patch=None):
    """T5 (revision 7), the event log's part: the record `data` (bytes) cut after each whole line
    in turn and listed in this process, each cut classified against the whole record's output:
    `caught` (no list: could not read, or no first-pass message), `harmless` (exactly the whole
    record's output), or `FAIL` (a list that differs: an event log is a framed input, so no cut of
    it is the limit, which revision 7 keeps for unframed Markdown pages alone). Returns
    [(lines kept, class)]."""
    path = os.path.join(fx.logs, name)
    lines = data.split(b"\n")
    check(lines[-1] == b"", "%s does not end with a newline" % name)

    def run(body):
        with open(path, "wb") as handle:
            handle.write(body)
        module = load_tool()
        if patch:
            patch(module)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = module.main(["--events", path] + list(extra))
        return code, buffer.getvalue()
    whole = run(data)
    check(whole[0] == 0, "%s: the whole record gave exit %d" % (name, whole[0]))
    found = []
    for kept in range(len(lines) - 1):
        code, out = run(b"".join(line + b"\n" for line in lines[:kept]))
        found.append((kept, "caught" if code != 0 else "harmless" if out == whole[1] else "FAIL"))
    return found


def late_commands():
    """A one-turn record of 10 lines whose first-pass message comes before two later commands: what
    --whole-run lists after the message, which a cut would shorten."""
    return (START + command(1, cat("/v/a.md")) + [message(2, FINDINGS)]
            + command(3, cat("/v/b.md")) + command(4, "/usr/bin/wc -l /v/c.md") + END)


def case_truncation_every_line(fx):
    """T5 (revision 7), the event log's part (test_slice.py cuts the picker's and the recorder's
    inputs): an event log is a framed input, its one turn completing on its last line, so each
    record cut after every whole line in turn gives no list (could not read, exit 1) or exactly the
    whole record's output; any other cut is FAIL, and there is no limit. Over the two acceptance
    runs' structural copies (126 and 124 lines, every cut caught) and a one-turn record with
    commands after its message, plain and with --whole-run (whose later list a cut would shorten);
    a two-turn record, which revision 6 read whole and whose cut between its turns it called the
    limit, is refused whole (truncated_record). The planted control, a reader that accepts a record
    however it ends (its in-run controls off, so the harness alone must find it), makes the harness
    find cuts it lists wrongly: FAILs."""
    late = ("\n".join(json.dumps(e) for e in late_commands()) + "\n").encode()
    records = [("real1.log", copy_bytes("REAL1"), ()), ("real2.log", copy_bytes("REAL2"), ()),
               ("late.log", late, ()), ("late-whole-run.log", late, ("--whole-run",))]
    counts = {}
    for name, data, extra in records:
        found = cut_record(fx, data, name, extra)
        counts[name] = dict((k, sum(1 for _, kind in found if kind == k))
                            for k in ("caught", "harmless", "FAIL"))
        check(not [kept for kept, kind in found if kind == "FAIL"],
              "%s: cuts neither caught nor harmless: %r"
              % (name, [kept for kept, kind in found if kind == "FAIL"]))
    # every cut of a one-turn record is caught: 126 and 124 lines, so 126 and 124 cuts (none to 125
    # or 123 lines kept), and the planted record's 10 lines, 10 cuts each way
    check(counts["real1.log"]["caught"] == 126 and counts["real2.log"]["caught"] == 124
          and counts["late.log"]["caught"] == 10 and counts["late-whole-run.log"]["caught"] == 10,
          "the counts: %r" % counts)

    def accepting(module):
        original = module.analyse

        def analyse(lines):
            record = original(lines)
            record.problems = []
            return record
        module.analyse = analyse
        module.run_controls = lambda: "switched off"
    found = cut_record(fx, copy_bytes("REAL1"), "control.log", (), accepting)
    check(any(kind == "FAIL" for _, kind in found),
          "the planted accepting reader gave no FAIL: %r" % found[:10])


def case_record_looked_at(fx):
    """Item 6's sweep, pass_order.py's one acquisition: a record whose metadata cannot be read is
    said to be so, never "the record does not exist" (which would send the head looking for a
    record that is there); for any user but root, a record in a folder that can be listed but not
    searched. The controls: a missing record does not exist, a folder cannot be opened."""
    path = fx.log(START + [message(1, FINDINGS)] + END, name="kept.log")
    module = load_tool()
    real_lstat = os.lstat

    def lstat(target, *args, **kwargs):
        if target == path:
            raise PermissionError(13, "Permission denied (planted)", target)
        return real_lstat(target, *args, **kwargs)
    os.lstat = lstat
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            code = module.main(["--events", path])
    finally:
        os.lstat = real_lstat
    out = buffer.getvalue()
    check(code == 1 and "the record could not be looked at (Permission denied (planted))" in out
          and "does not exist" not in out, "the planted metadata error: %d %r" % (code, out[:400]))
    if os.geteuid() != 0:
        locked = os.path.join(fx.root, "locked")
        os.makedirs(locked)
        inside = os.path.join(locked, "record.log")
        with open(inside, "w", encoding="utf-8") as handle:
            handle.write("\n".join(json.dumps(e) for e in START + [message(1, FINDINGS)] + END)
                         + "\n")
        os.chmod(locked, stat.S_IRUSR)
        try:
            code, out, _ = fx.run(inside)
        finally:
            os.chmod(locked, stat.S_IRWXU)
        check(code == 1 and "could not be looked at" in out and "does not exist" not in out,
              "a record it cannot look at: %d %r" % (code, out[:400]))
    unread_case(fx, os.path.join(fx.logs, "absent.log"), "could not read: %s: the record does not "
                "exist; no event was read" % os.path.join(fx.logs, "absent.log"))


def case_bad_arguments(fx):
    """No --events, an unknown flag, and the retired --source each print PROBE FAILED and exit 2,
    with no list."""
    path = fx.log(START + [message(1, FINDINGS)] + END)
    for extra, events in (((), False), (("--sauce", "x"), True), (("--source", "/v/x.md"), True)):
        code, out, _ = fx.run(path, *extra, events=events)
        check(code == 2 and out.startswith("PROBE FAILED: bad arguments")
              and "COMMANDS BEFORE" not in out, "%r: %d %r" % (extra, code, out))


def case_exit_codes_documented(fx):
    """Each outcome has its own exit code, as the docstring documents: the list 0, could not read
    1, PROBE FAILED 2, no first-pass message 3."""
    codes = {}
    codes["listed"] = fx.check_log(START + [message(1, FINDINGS)] + END)[0]
    codes["could not read"] = fx.check_log(START + [message(1, FINDINGS)])[0]
    codes["probe"] = fx.run(fx.log(START + END), "--sauce")[0]
    codes["no message"] = fx.check_log(START + [message(1, "x")] + END)[0]
    check(codes == {"listed": 0, "could not read": 1, "probe": 2, "no message": 3},
          "the exit codes: %r" % codes)
    with open(SCRIPT, encoding="utf-8") as handle:
        doc = handle.read().split('"""')[1]
    exits = doc.split("EXIT CODES", 1)[1]
    for line in ("- 0: the list printed", "- 1: could not read", "- 2: PROBE FAILED",
                 "- 3: no first-pass message"):
        check(line in exits, "the docstring does not document %r" % line)


def load_tool():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("pass_order_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case_controls_line(fx):
    """Every outcome prints the controls line, whose plants cover the listing, the grammar and the
    lossless listing; the controls catch a broken reader: with the listing made to drop a command,
    the grammar made to accept everything, the listing's encoding made to leave backslashes as
    they are (the first build's, which printed two commands alike), or (revision 7) the grammar
    made to read a record with a whole second turn as whole again (revision 6's), run in this
    process, the tool prints PROBE FAILED and exits 2."""
    for events in (START + [message(1, FINDINGS)] + END, START + [message(1, FINDINGS)],
                   START + [message(1, "x")] + END):
        code, out, _ = fx.check_log(events)
        check(re.search(r"^controls: a planted record listed its 4 earlier commands whole, in start "
                        r"order .*; [1-9]\d* planted damaged records each gave could-not-read "
                        r"problems; .*; [1-9]\d* planted texts with hidden characters and "
                        r"backslashes .* printed apart and each decoded back, and a text with "
                        r"nothing hidden printed byte for byte$", out, re.M),
              "%d: the controls line %r" % (code, parse(out)["controls"]))
    path = fx.log(START + [message(1, FINDINGS)] + END)
    for name, attribute in (("actions", "actions"), ("analyse", "analyse"), ("encode", "encode"),
                            ("turns", "analyse")):
        module = load_tool()
        original = getattr(module, attribute)
        if name == "actions":
            setattr(module, name, lambda *args: original(*args)[1:])
        elif name == "encode":
            def lossy(text, module=module):
                shown = "".join(module.escape(c) if module.hides(c) else c for c in text)
                return shown, sum(1 for c in text if module.hides(c))
            setattr(module, name, lossy)
        elif name == "turns":   # revision 6's grammar: a whole later turn read as more record
            def many_turns(lines, original=original):
                record = original(lines)
                record.problems = [p for p in record.problems if "a second turn" not in p[1]]
                return record
            setattr(module, attribute, many_turns)
        else:
            def accepting(lines, original=original):
                record = original(lines)
                record.problems = []
                return record
            setattr(module, name, accepting)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = module.main(["--events", path])
        check(code == 2 and buffer.getvalue().startswith("PROBE FAILED: "),
              "a broken %s passed the controls: %d %r" % (name, code, buffer.getvalue()[:300]))


def case_no_verdict_claim(fx):
    """T8: no output line, exit code or file of the tool claims a verdict on the first pass. Every
    output of every case is searched as it is made (Fixture.run); this case proves the search
    catches planted verdicts (the old check's verdict lines among them) and passes the tool's own
    lines, runs each outcome once more, and searches the docstring, whose exit codes name what
    was printed, never what the first pass read. The tool writes no file (the last leg)."""
    planted = ("PASS-ORDER CLEAR: a valid log; this shows no literal mention, not a blind first "
               "pass", "PASS-ORDER UNDECIDED: the log is invalid", "the first pass was blind",
               "the first pass was independent", "a first-pass that is clean", "verdict: CLEAR")
    caught = [line for line in planted if verdict_lines(line)]
    check(len(caught) >= len(planted) - 1 and "the first pass was blind" in caught
          and planted[0] in caught, "the search misses a planted verdict: %r"
          % sorted(set(planted) - set(caught)))
    passed = ("COMMANDS BEFORE THE FIRST-PASS MESSAGE: 9 · record /x.log",
              "NO FIRST-PASS MESSAGE: /x.log holds no complete first-pass message",
              "COULD NOT READ: /x.log; no list", "an unclear note")
    check(not [line for line in passed if verdict_lines(line)],
          "the search flags the tool's own lines: %r" % [l for l in passed if verdict_lines(l)])
    before = SEARCHED["outputs"]
    for events in (START + command(1, cat("/v/a.md")) + [message(2, FINDINGS)] + END,
                   START + [message(1, FINDINGS)], START + [message(1, "x")] + END):
        fx.check_log(events)
    check(SEARCHED["outputs"] - before == 3 and SEARCHED["lines"] > 0,
          "the outputs were not searched: %r" % SEARCHED)
    with open(SCRIPT, encoding="utf-8") as handle:
        doc = handle.read().split('"""')[1]
    check(not verdict_lines(doc.split("EXIT CODES", 1)[1]) and not verdict_lines(doc),
          "the docstring holds a verdict line: %r" % verdict_lines(doc))
    done = subprocess.run([sys.executable, "-B", SCRIPT, "--help"], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True, timeout=TIMEOUT_S)
    check(done.returncode == 0 and "--whole-run" in done.stdout and not verdict_lines(done.stdout),
          "the help text: %r" % done.stdout[:400])


# T10: the held build's 34 cases, each retired with the verdict it asserted or kept as the case
# that now carries its evidence invariant with a neutral assertion.
RETIRED = {
    "message_first_clear": "listed_before_message",
    "source_named_first": "retired: matched sources to give a verdict",
    "source_by_file_name": "retired: read relative paths to give a verdict",
    "started_before_sent": "spanning_and_late",
    "missing_message": "no_first_pass_message",
    "header_must_be_exact": "header_must_be_exact",
    "boundary_format": "cut_off_message_not_boundary",
    "forbidden_named": "retired: matched forbidden paths to give a verdict",
    "other_file_same_name": "retired: matched sources to give a verdict",
    "file_change_on_source": "file_changes_listed_apart",
    "folder_search": "retired: matched tree searches to give a verdict",
    "glob_unresolved": "retired: graded commands by the shell grammar",
    "unreadable_log_never_passes": "unreadable_record",
    "unparseable_counted": "malformed_evidence",
    "no_source_at_all": "retired: asserted that the second pass was observed",
    "torn_line_after_message_forbid": "truncated_record",
    "item_without_evidence": "malformed_evidence",
    "event_without_type": "malformed_evidence",
    "unknown_types_undecided": "malformed_evidence",
    "command_changes_across_events": "changed_evidence",
    "log_cut_before_final_turn": "truncated_record",
    "brace_expansion_unresolved": "retired: graded commands by the shell grammar",
    "unresolved_forms": "retired: graded commands by the shell grammar",
    "plain_commands_not_referred": "verbatim_text",
    "unresolved_scope_and_forbid": "whole_run",
    "relative_paths_and_cd": "retired: read working folders to give a verdict",
    "real_acceptance_log": "acceptance_records",
    "verdicts_and_exit_codes": "exit_codes_documented",
    "bad_arguments": "bad_arguments",
    "spaced_vault": "retired: matched sources to give a verdict",
    "output_is_not_a_command": "output_is_not_a_command",
    "evidence_and_controls": "controls_line",
    "fixtures_honour_tmpdir": "fixtures_honour_tmpdir",
    "writes_nothing": "writes_nothing",
}
INVARIANTS = {"start order": "start_order_and_executions",
              "one entry per execution": "start_order_and_executions",
              "boundary semantics": "cut_off_message_not_boundary",
              "malformed fields named": "malformed_evidence"}


def case_retirement_map(fx):
    """T10: every one of the held build's 34 cases is retired or kept, each kept one naming a case
    of this suite, and each invariant the design note names has its case here."""
    names = set(name for name, _ in CASES)
    check(len(RETIRED) == 34, "the map holds %d held cases, 34 expected" % len(RETIRED))
    kept = dict((k, v) for k, v in RETIRED.items() if not v.startswith("retired: "))
    check(all(v in names for v in kept.values()), "a kept case is missing: %r"
          % sorted(v for v in kept.values() if v not in names))
    check(all(v in names for v in INVARIANTS.values()) and len(INVARIANTS) == 4,
          "an invariant has no case: %r" % INVARIANTS)
    check(len(kept) >= 20 and len(RETIRED) - len(kept) >= 10,
          "%d kept, %d retired" % (len(kept), len(RETIRED) - len(kept)))


def case_fixtures_honour_tmpdir(fx):
    """The fixtures live under the temporary folder TMPDIR names (tempfile.gettempdir)."""
    root = os.path.realpath(tempfile.gettempdir())
    check(os.path.realpath(fx.root).startswith(root + os.sep), "the fixture is not under %s" % root)
    if os.environ.get("TMPDIR"):
        check(root == os.path.realpath(os.environ["TMPDIR"]), "tempfile ignored TMPDIR")


WRITE_PATTERNS = (
    r"\bopen\([^)]*,\s*['\"][rbt]*[wax+]",
    r"\bos\.fdopen\(",
    r"\bos\.(replace|rename|renames|remove|unlink|rmdir|removedirs|mkdir|makedirs|chmod|chown"
    r"|truncate|symlink|link|utime)\(",
    r"\bshutil\.",
    r"\btempfile\.",
    r"\.write_(text|bytes)\(",
    r"\bjson\.dump\(",
    r"\bsubprocess\.",
)
READ_PATTERN = r"\bopen\([^)]*,\s*['\"]rb['\"]"


def write_hits(source):
    return [(number, line) for number, line in enumerate(source.splitlines(), 1)
            if any(re.search(p, line) for p in WRITE_PATTERNS)]


def tree_manifest(top):
    entries = []
    for dirpath, dirnames, filenames in os.walk(top):
        dirnames.sort()
        entries.append(("dir", os.path.relpath(dirpath, top), stat.S_IMODE(os.stat(dirpath).st_mode)))
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            with open(path, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            entries.append(("file", os.path.relpath(path, top), digest,
                            stat.S_IMODE(os.stat(path).st_mode)))
    return entries


def case_writes_nothing(fx):
    """pass_order.py writes nothing: a read-only copy of its records is unchanged byte for byte
    after a listed, a could-not-read and a no-message run, and its source holds no write pattern
    (the grep's controls: a planted write is caught, and the source's one read is found)."""
    copy = os.path.join(fx.root, "copy")
    os.makedirs(os.path.join(copy, "logs"))
    for name, events in (("listed.log", START + command(1, cat("/v/a.md")) + [message(2, FINDINGS)]
                          + END),
                         ("unread.log", START + [message(1, FINDINGS)]),
                         ("nomessage.log", START + command(1, cat("/v/a.md")) + END)):
        with open(os.path.join(copy, "logs", name), "w", encoding="utf-8") as handle:
            handle.write("\n".join(json.dumps(e) for e in events) + "\n")
    paths = [copy] + [os.path.join(d, n) for d, ds, fs in os.walk(copy) for n in ds + fs]
    for path in paths:
        os.chmod(path, os.stat(path).st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    try:
        before = tree_manifest(copy)
        # the copy holds 3 records and 2 folders, 5 entries (counted from the fixture), so a
        # manifest of 4 entries or fewer means the walk missed part of it
        check(len(before) > 4, "the manifest saw only %d entries" % len(before))
        results = [fx.run(os.path.join(copy, "logs", name))[0]
                   for name in ("listed.log", "unread.log", "nomessage.log")]
        after = tree_manifest(copy)
    finally:
        for path in paths:
            os.chmod(path, os.stat(path).st_mode | stat.S_IWUSR)
    check(results == [0, 1, 3], "the runs on the read-only copy gave %r, [0, 1, 3] expected"
          % results)
    check(before == after, "the read-only copy changed: %r" % sorted(set(after) ^ set(before))[:5])
    with open(SCRIPT, encoding="utf-8") as handle:
        source = handle.read()
    check(write_hits("x = open(p, 'w')\nos.replace(a, b)\n") == [(1, "x = open(p, 'w')"),
                                                               (2, "os.replace(a, b)")],
          "the write-pattern grep misses a planted write")
    check(len(re.findall(READ_PATTERN, source)) >= 1, "the control: the grep found no read in the "
          "source, so it may not be reading it")
    check(not write_hits(source), "a write pattern in pass_order.py: %r" % write_hits(source))


CASES = [(name[5:], function) for name, function in sorted(globals().items())
         if name.startswith("case_") and callable(function)]
CASES.sort(key=lambda entry: entry[1].__code__.co_firstlineno)


def printable(error):
    """A failure's message as printed: a lone surrogate (as a faulty build may print one) is
    written as its escape, so the suite's own output stays UTF-8."""
    return str(error).encode("utf-8", "backslashreplace").decode("utf-8")


def main(argv):
    names = [name for name, _ in CASES]
    wanted = argv[1:]
    unknown = [name for name in wanted if name not in names]
    if unknown:
        print("REFUSED: no case named %s; the cases: %s" % (", ".join(unknown), ", ".join(names)))
        return 2
    selected = [entry for entry in CASES if not wanted or entry[0] in wanted]
    print("selected %d of %d case(s): %s" % (len(selected), len(CASES),
                                              "all" if not wanted else ", ".join(wanted)))
    if not os.path.isfile(SCRIPT):
        print("PROBE FAILED: pass_order.py not found beside the suite at %s" % SCRIPT)
        return 2
    top = tempfile.mkdtemp(prefix="test-pass-order-")
    failures = []
    try:
        for index, (name, function) in enumerate(selected):
            root = os.path.join(top, "%02d-%s" % (index, name))
            os.makedirs(root)
            try:
                function(Fixture(root))
                print("ok   %s" % name)
            except Failure as failure:
                failures.append(name)
                print("FAIL %s: %s" % (name, printable(failure)))
            except Exception as error:   # a crash in a case is a failure, never a pass
                failures.append(name)
                print("FAIL %s: %s: %s" % (name, type(error).__name__, printable(error)))
    finally:
        shutil.rmtree(top, ignore_errors=False)
    print("searched %d output(s), %d line(s), for a verdict on the first pass (T8)"
          % (SEARCHED["outputs"], SEARCHED["lines"]))
    if failures:
        print("FAIL %d/%d (%s)" % (len(failures), len(selected), ", ".join(failures)))
        return 1
    print("PASS %d/%d" % (len(selected), len(selected)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
