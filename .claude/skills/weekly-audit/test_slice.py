#!/usr/bin/env python3
"""test_slice.py: the suite for slice.py and for the procedure texts beside it (AUDIT.md and
brief-audit.md), on fixtures it builds in a temporary folder (tempfile, which honours TMPDIR) and
removes at the end. Python 3 standard library only.

    python3 -B test_slice.py [CASE ...]

Each case builds its own world (a vault, a tools folder, a hooks folder, a slices.json made by
`slice.py --init` as the install makes it, and a folder for manifests and reports) and runs
slice.py with every path named, as its own process or, for an injection, in this process, so no
case reads or writes the live vault or the slices.json beside the script. The suite ends
`PASS n/n`, or names each failure and ends `FAIL k/n` with a non-zero exit. Case names given as
arguments select a subset for iterating: the suite prints its selection and refuses a misspelt
name.

The cases: the design's Tests bullets (sections 2 and 3) that concern slice.py; the refusals; the
hold-out of the second pass's sources (with the register slice's list run end to end through
pass_order.py); the record's own guarantees, the install and the baseline the audit read; and the
design note of option S (revision 7, 13 October 2026, which records the stop of the whole-input
proof for unframed Markdown and its provisional replacement, and folds the third build review).
Revision 7's cases: the truncation test reclassified (every text input cut after each whole line,
each cut caught, harmless, the limit (an unframed Markdown page left structurally valid, judged by
this suite's own reading of the structural rules) or FAIL (structurally invalid input accepted, or
a framed input, the report, JSON, a deep-lint entry's frame, accepted when cut), with planted
lenient readers as its controls and the third build review's three interior cuts classed); the
removed heuristics (a heading after the last lifecycle table, the standing-rules count, a closing
field on the log's last entry, and with them the register's closing section and the empty-heading
rule) turned into unframed_pages_limit, where each such shape reads as the stated limit; the
pick's `limit:` lines and AUDIT.md's statement of the limit (audit_states_the_limit); the hash
scan's backstop (backstop_cut_reads_changed); path lines with their exact characters (T6 (i),
report_paths_exact); deep-lint's fields complete with a value (comparison_sources_fail_closed); a
broken symbolic link where an owed path is looked at (broken_link_stays_owed); and the deletion
check that tells an absent path from a folder with nothing left to read (deleted_entries_controls).
The replacement's first review (CR-AUDIT8), folded: a fence closes only on a line holding its bare
marker, in every consumer of the reader and in this suite's own (fences_closed, the truncation
world's closed examples and the in-run plants of controls_line; F1); the truncation classifier
decides structure and frame before an equal outcome may call a cut harmless, and each lenient
reader's named cuts must each be FAIL (truncation_every_line; F2); and step 6's check of a deleted
path accepts what step 3's does (deleted_entries_controls; F3). The replacement's second review
(CR-AUDIT9), folded as revision 7's amendment: an HTML comment is read as text in every Markdown
acquisition and in this suite's own reader, so a comment neither hides a line nor leaves a page
open (comments_read_as_text, CR-AUDIT9's escaped backtick and code span over three lines among
its shapes), and a backtick line whose info string holds a backtick opens no fence, by CommonMark's
rule (fences_closed, the truncation world and the in-run plants); each case, leg or plant that
expected a comment to hide or to fail is retired or converted in RETIRED_R7A, with its reason.
Revision 8 (spec-D18.md, the owner's decision D18 of 13 October 2026) removes every hand-written
Markdown structure reader from slice.py. The four inputs where a misread would be silent (the
report's coverage section, the lifecycle tables, the register and deep-lint's entry in the log)
are read by literal-line protocols over their raw lines, and this suite checks each against its
protocol with its own raw reading (structure_problem, written apart from slice.py, with no fence
or comment filtering): coverage_raw_protocol, lifecycle_raw_protocol, raw_inputs_read_every_line,
the register's and the log's new legs in comparison_sources_fail_closed, and
protocols_agree_with_reference, where the two readings must give the same verdict on a planted
corpus and every line cut of it. The section lists of CLAUDE.md and
CUSTOMISATION.md are read by markdown-it-py 4.2.0 through slice.py's adapter alone, its projection
(section locations and lifecycle keys) compared with expected lists written here by hand for
adversarial fixtures (section_adapter_projection), its missing or unimportable package making the
inventory UNKNOWN (section_adapter_dependency), and no other code importing the package
(adapter_alone_imports_markdown_it); the live files are compared in the build's evidence, since no
case reads the vault. The review cases CR-AUDIT10's F1 and F2 and CR-AUDIT-B finding 1's
counterexample and its list-fence counterpart run end to end (review_counterexamples). Coverage
covers every mandatory input, the requirement files and the second-pass sources beside the reading
list (coverage_mandatory_inputs, CR-AUDIT-B finding 2's end-to-end case); the two inline hooks
are named groups (named_groups_inline_hooks); and the procedure, the brief and the code state the
same rules (texts_one_set_of_rules). The truncation test reads each raw page by its protocol and
each standing-rules file by its hand-written sections, a cut that leaves a section hidden by what
it left open being lexer-hidden evidence, never the limit. RETIRED_D18 maps each case, leg or
plant revision 8 retired or converted, with its reason.
CR-AUDIT11's fold (B-AUDIT12), one case per finding, each failing on B-AUDIT11's build: a latest
deep-lint heading damaged while its kind still stands before its title (its bracket left open, the
review's plant, among the forms) fails the source with no fallback to the older entry, this
suite's reading rejecting it too, and a next heading behind a list marker ends the entry
(deeplint_latest_heading_damaged, F1); a requirement file absent at the pick stays among the
mandatory inputs and leaves the audit incomplete, owed nothing (absent_requirement_incomplete, F2);
the register is a comparison source whatever its phase, and the recovery for a missing or unclear
section names every mandatory input (comparison_status_any_phase, F3); and no list contributor
puts a second-pass source into pass 1, each pick's manifest accepted by its recorder
(log_never_in_pass_one, F4). The registry, inventory, controls, agreement-corpus, manifest-shape
and text cases follow (the requirement files' acquisition, F1's shapes and plants, the version-6
manifest refused, the texts' new shared rules); no case, leg or plant is retired.
CR-AUDIT12's fold (B-AUDIT13), one case per finding of this suite's, each failing on B-AUDIT12's
build: a requirement file's role judged apart from every route by which its path reaches the
reading list, so that one absent leaves the pick incomplete as an owed deletion (the review's
route), through a due row and through the rotating part as well, the deletion keeping its own
rules (requirement_role_apart, F1); and a due row's file printed in the spelling of the roots the
audit was given and owed by its hash key whatever that spelling, so that an omission never lets
an unread file's hash into the first baseline (aliased_root_same_debt, F3). The installer's F2 is
test_install_audit.py's. The head's choice that a retired row needs no Next review, its other
checks staying, is retired_row_needs_no_next_review, with its in-run plants caught in
controls_line; the texts' new shared rules join texts_one_set_of_rules. No case, leg or plant is
retired.
CR-AUDIT13's fold (B-AUDIT14), one case per finding of this suite's, each failing on B-AUDIT13's
build: an owed entry's files found before the held sources leave the reading list, so that a file
of a folder owed from an earlier audit, held for the second pass and named unread, keeps the
folder owed and its own earlier hash, in an ordinary week and in the register's own, while reading
every file of it discharges it (held_member_keeps_debt, F2; the manifest, version 8, names those
held files, and B-AUDIT13's version 7 is refused); and this suite's lifecycle reading cutting a
table line's cells at unescaped pipes only, by its own specification, so that it and slice.py give
the same verdict on the review's two escaped-pipe tables and their controls, which join the
agreement corpus, and the classifier calls the ten-cell one FAIL when accepted
(escaped_pipes_read_alike, F3; its failing build is B-AUDIT13's suite reading, table_cells). The
installer's F1 is test_install_audit.py's. The texts' new shared rule joins
texts_one_set_of_rules. No case, leg or plant is retired.
CR-AUDIT14's fold (B-AUDIT15), its F1, failing on B-AUDIT14's build: the record credits only the
slice whose reading its manifest represents, so any slice other than the one the manifest's pick
chose is refused before anything is committed, the line naming the pick's slice, while the pick's
own slice records as before, the rotation counting that attempt alone, and a hooks-and-monitors
pick with its settings file absent stays incomplete (record_refuses_other_slice, the review's
probes). record_atomic's leg that recorded another slice with a warning is a refusal now
(RETIRED_R14); record_refuses_older_manifest, adapter_alone_imports_markdown_it and the
independent inventory's runs (inventory_run) named another slice than their pick's only in
passing, and now name their pick's, their legs unchanged. The texts' new shared rule joins
texts_one_set_of_rules. The review's F2 concerns the installer, which the head has retired from
the install, and is not folded here; no case of this suite is retired.
Revision 6's cases stay: the declared WHOLE_INPUT table, absence
established (an owed file whose metadata is refused while its folder lists it stays owed), the
sweep of every error read as absence and of the refusals that named one wrongly, the
`END NOT READ` terminator (T6 (h)), the
commit after the read-back (real failed opens of the temporary state, its cut at every line, a
refusal after the commit), the content controls over existing files only, UNKNOWN part headers
and the escaped printing of hidden characters. The earlier ones:
- T5, completeness fail-closed for every acquisition: each registered acquisition of the pick, one
  at a time, failing, returning unknown and never reporting, and each of the record's own (the
  premises, slices.json, the manifest and the coverage) likewise, each recorded incomplete with
  its reason; the lifecycle page missing, unreadable, with no table and with a damaged one (a
  header alone, a broken or missing separator, a torn row, rows cut off, a fence left open), a
  valid empty table being no failure; a root removed between its check and its walk in each
  acquisition that walks it; the comparison sources (the register, and deep-lint's entry in
  wiki/log.md) missing, unreadable, undecodable after a valid heading and unusable, withholding
  `new kind`; the controls (one due row, a readable empty root) and the recoveries; and the
  independent inventory, a pick and a record run under a file-open audit hook (sys.addaudithook)
  that fails when a file is opened outside a registered acquisition, with a planted unregistered
  read and a planted misplaced read that must each make it fail;
- whole input (item 6, the sweep of every acquisition for lenient decoding or partial success):
  undecodable bytes, a key given twice or a NaN in slices.json or a manifest, a heading after the
  `## Not read` section, a fenced block never closed, a name that is not valid UTF-8, and lines
  split at characters other than a newline;
- T6, coverage from the reviewer's `## Not read` section: (a) to (i), (g) the deletion rule, (h)
  the terminator, (i) exact path characters;
- T7, rotation by attempt with debt carried;
- T8, no output of the tool and no line of AUDIT.md reads as a verdict on the first pass (every
  output is searched as it is made);
- T9's suite part: AUDIT.md's table names the four outcomes and the register-as-slice rule (the
  head applies the table to the five planted lists of acceptance-T9.md);
- items 8 and 9, the procedure texts' settled points, with the brief's plain-command wording;
and a last leg proving the pick writes nothing. RETIRED below maps each held case this revision
replaced, RETIRED_R7 each case of revision 6 that revision 7's replacement turned into another,
and RETIRED_R7A each case, leg or plant revision 7's amendment retired or converted, with its
reason. pass_order.py has its own suite, test_pass_order.py.
"""

import ast
import contextlib
import datetime
import hashlib
import importlib.util
import io
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
SLICE = os.path.join(HERE, "slice.py")
PASS_ORDER = os.path.join(HERE, "pass_order.py")
AUDIT_MD = os.path.join(HERE, "AUDIT.md")
BRIEF_MD = os.path.join(HERE, "brief-audit.md")
NESTED_SKILL = ".claude/skills/alpha/lane-home-src/inner/SKILL.md"
FINDINGS = "PASS 1 FINDINGS\nP1-1 a stale entry: x\nEND PASS 1: 1 findings"
HEADER = ("| Item | Kind | Purpose | Guards | Cost per run | Last real catch | State | Retire when "
          "| Re-arm when | Next review |")
SEPARATOR = "|" + "---|" * 10
TODAY = "2026-10-18"
PAST = "2026-01-01T00:00:00+00:00"   # a record time safely before any manifest a case takes
TIMEOUT_S = 120   # set by judgement, unmeasured: a fixture pick takes well under a second
NONE_READ = "## Not read\nnone\nEND NOT READ: 0\n"
# The fixture's register and log, each structurally valid: the register's `## Open` and `## Closed`
# sections (a further section after them, as the vault's pages have); each log entry a heading and
# its complete `Changed` and `Conflicts` fields (the latest deep-lint entry is lines 11 to 14)
REGISTER_TEXT = ("# Register\n\n## Open\n- entry\n\n## Closed\n- an old entry, fixed\n\n"
                 "## Related\n- the design page\n")
LOG_TEXT = ("# Log\n\n## [2026-09-01] deep-lint | first\n- **Changed**: a\n- **Conflicts**: none\n\n"
            "## [2026-09-02] ingest | x\n- **Changed**: b\n- **Conflicts**: none\n\n"
            "## [2026-10-02] deep-lint | second\n- **Changed**: c\n- **Clock**: 06:23 BST\n"
            "- **Conflicts**: none\n\n## [2026-10-03] query | y\n- **Changed**: d\n"
            "- **Conflicts**: none\n")
DEEPLINT_LINES = "log.md lines 11-14 (the deep-lint entry of 2026-10-02)"
# what follows the lifecycle table on the fixture's page, as on the vault's: a further section
# (revision 7 requires nothing after a table; the page is unframed Markdown)
LIFECYCLE_TAIL = "\n## Related\n- the design page\n"
# T8: what a verdict on the first pass looks like (the same patterns as test_pass_order.py)
VERDICT_PATTERNS = (
    r"(?i)\bblind",
    r"PASS-ORDER",
    r"\bCLEAR\b",
    r"\bUNDECIDED\b",
    r"(?i)\bfirst[- ]pass\b.{0,40}\b(was|is|were)\b.{0,20}\b(independent|clean|unseen|"
    r"uncontaminated)\b",
)
SEARCHED = {"outputs": 0}


class Failure(Exception):
    pass


def check(condition, message):
    if not condition:
        raise Failure(message)


def verdict_lines(text):
    return [line for line in text.splitlines()
            if any(re.search(pattern, line) for pattern in VERDICT_PATTERNS)]


def searched(out):
    """T8: every output of the tool is searched for a verdict on the first pass as it is made; and
    no output of it may hold a character a terminal could hide (its lines are split at newlines)."""
    SEARCHED["outputs"] += 1
    hits = verdict_lines(out)
    check(not hits, "T8: an output of slice.py reads as a verdict on the first pass: %r" % hits)
    hiding = hidden(out.replace("\n", ""))
    check(not hiding, "an output of the tool holds %d character(s) a terminal could hide, the "
          "first %r" % (len(hiding), hiding[:1]))
    return out


def load_slice():
    """A fresh copy of slice.py loaded in this process, for the injection cases; no bytecode is
    written beside it."""
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("slice_under_test", SLICE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


NAMED = []


def named_groups():
    """slice.py's NAMED_GROUPS, read from the script itself, so that the fixture's rows follow the
    list when the install adds to it (the inline hooks, by the held README's install step)."""
    if not NAMED:
        NAMED.extend(load_slice().NAMED_GROUPS)
    return tuple(NAMED)


def plant_outcome(target, mode):
    """A patch making the acquisition named `target` fail, return unknown, or never report."""
    def patch(module):
        original = module.Acquisition.done

        def done(self):
            if self.name == target:
                if mode == "never":
                    return None
                if mode == "failed":
                    self.fail("/planted/" + target.replace(" ", "-"), "a planted failure")
                else:
                    self.unknown("a planted unknown result")
            return original(self)
        module.Acquisition.done = done
    return patch


# ------------------------------------------------------------------ the fixture world --------

class World(object):
    """A vault, a tools folder holding weekly-audit/, a hooks folder, a slices.json made by
    --init, and an `out` folder for manifests and reports."""

    def __init__(self, root, init=True):
        self.root = root
        self.vault = os.path.join(root, "vault")
        self.tools = os.path.join(root, "tools")
        self.hooks = os.path.join(root, "hooks")
        self.out = os.path.join(root, "out")
        self.state = os.path.join(self.tools, "weekly-audit", "slices.json")
        self.manifests = 0
        files = {
            # HTML comments as the live file holds them, one-line markers, and one over three
            # lines holding text but no heading (a comment is text: comments_read_as_text)
            "vault/CLAUDE.md": ("# Schema\n\n## 1. One\nrule one\n\n## 2. Two\nrule two\n\n"
                                "```markdown\n## [YYYY-MM-DD] ingest | Short title\n```\n\n"
                                "<!-- a marker:begin -->\nrule two, kept\n<!-- a marker:end -->\n"
                                "<!--\na note held in a comment\n-->\n\n## 3. Three\nrule three\n"),
            "vault/CUSTOMISATION.md": "# Prefs\n\n## Settings\nstyle: x\n\n## Roles\nr\n",
            "vault/CUSTOMISATION-definitions.md": "# Definitions\n",
            "vault/.claude/settings.json": "{}\n",
            "vault/.claude/skills/alpha/SKILL.md": "# alpha\n",
            "vault/.claude/skills/alpha/run.py": "print('alpha')\n",
            "vault/.claude/skills/alpha/test_alpha.sh": "echo ok\n",
            "vault/.claude/skills/alpha/__pycache__/run.cpython.pyc": "cache\n",
            "vault/.claude/skills/alpha/run.py.bak-1": "old\n",
            "vault/.claude/skills/alpha/lane-home-src/inner/SKILL.md": "# inner\n",
            "vault/.claude/skills/beta/SKILL.md": "# beta\n",
            "vault/.claude/skills/beta/test_beta.py": "print('ok')\n",
            "vault/.claude/hooks/gate.py": "print('gate')\n",
            "vault/.claude/hooks/test_gate.sh": "echo ok\n",
            "vault/wiki/developments/known-issues.md": REGISTER_TEXT,
            "vault/wiki/developments/design.md": "# Design\n",
            "vault/wiki/log.md": LOG_TEXT,
            "tools/thing.py": "print('thing')\n",
            "tools/watch/wait.sh": "sleep 1\n",
            "tools/pin/node_modules/dep/index.js": "module.exports = 1\n",
            "tools/weekly-audit/README.md": "# readme\n",
            "hooks/guard.py": "print('guard')\n",
            "hooks/test_guard.sh": "echo ok\n",
            "hooks/data.jsonl": "{}\n",
            "hooks/guard.py.bak-2": "old\n",
        }
        for rel, text in files.items():
            self.write(rel, text)
        os.makedirs(self.out)
        self.lifecycle(self.every_item_row())
        if init:
            code, out, err = self.run("--init")
            check(code == 0 and out.startswith("INITIALISED: "), "--init failed (%d): %s %s"
                  % (code, out, err))

    def path(self, rel):
        return os.path.join(self.root, *rel.split("/"))

    def write(self, rel, text):
        path = self.path(rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def argv(self, extra, today=TODAY):
        return (["--vault", self.vault, "--tools", self.tools, "--hooks", self.hooks, "--state",
                 self.state, "--today", today] + list(extra))

    def run(self, *extra, **options):
        command = [sys.executable, "-B", SLICE]
        if options.get("vault", True):
            command += ["--vault", self.vault]
        command += ["--tools", self.tools, "--hooks", self.hooks,
                    "--state", options.get("state", self.state),
                    "--today", options.get("today", TODAY)] + list(extra)
        env = dict(os.environ)
        for name in ("CLAUDE_PROJECT_DIR", "LLM_WIKI_VAULT"):
            env.pop(name, None)
        done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                              timeout=TIMEOUT_S)
        # read as bytes and decoded strictly, with no newline translation, so that a carriage
        # return or any other character a terminal could hide reaches searched() as it is
        return (done.returncode, searched(done.stdout.decode("utf-8")),
                done.stderr.decode("utf-8", "backslashreplace"))

    def in_process(self, *extra, **options):
        """A run of slice.py in this process, with `patch` applied to its module first."""
        module = load_slice()
        if options.get("patch"):
            options["patch"](module)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = module.main(self.argv(extra, options.get("today", TODAY)))
        return code, searched(buffer.getvalue())

    def manifest_path(self):
        self.manifests += 1
        return os.path.join(self.out, "manifest-%d.json" % self.manifests)

    def report(self, not_read=None, text=None):
        """A reviewer's report ending in its `## Not read` section: `none`, or the given paths."""
        self.manifests += 1
        path = os.path.join(self.out, "report-%d.md" % self.manifests)
        if text is None:
            text = ("# Report\n\n## Read\nk of N\n\n## Gaps\nnone\n\n"
                    + ("## Not read\n%s\nEND NOT READ: %d\n" % ("\n".join(not_read), len(not_read))
                       if not_read else NONE_READ))
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def pick(self, today=TODAY, *extra):
        """A pick that writes its manifest; returns (manifest path, output)."""
        manifest = self.manifest_path()
        code, out, err = self.run("--manifest-out", manifest, *extra, today=today)
        check(code in (0, 3) and os.path.isfile(manifest), "the pick with --manifest-out failed "
              "(%d): %s %s" % (code, out[-300:], err))
        return manifest, out

    def record(self, slice_name, findings=0, today="2026-10-11", manifest=None, not_read=None):
        """The audit's record as the procedure makes it: a pick with --manifest-out, then
        --record with that manifest and the reviewer's report (`none` unless paths are given)."""
        if manifest is None:
            manifest, _ = self.pick(today)
        code, out, err = self.run("--record", slice_name, "--findings", str(findings),
                                  "--manifest", manifest, "--report", self.report(not_read),
                                  today=today)
        check(code == 0, "--record %s failed (%d): %s %s" % (slice_name, code, out, err))
        return out

    def lifecycle(self, rows, header=HEADER):
        body = "\n".join([header, SEPARATOR] + list(rows))
        return self.write("vault/wiki/developments/check-lifecycle.md",
                          "---\ntitle: Check lifecycle\n---\n\n# Check lifecycle\n\n" + body + "\n"
                          + LIFECYCLE_TAIL)

    def state_data(self):
        with open(self.state, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def set_state(self, data):
        with open(self.state, "w", encoding="utf-8") as handle:
            json.dump(data, handle)

    def set_audits(self, audits):
        """Audits as (slice, date, findings) or (slice, date, findings, complete); an incomplete
        one carries a planted reason, as a record stores it."""
        data = self.state_data()
        data["audits"] = [{"date": a[1], "slice": a[0], "findings": a[2], "recorded": PAST,
                           "manifest_taken": PAST, "complete": a[3] if len(a) > 3 else True,
                           "reasons": [] if len(a) < 4 or a[3] else ["a planted reason"]}
                          for a in audits]
        self.set_state(data)

    def inject(self, function, root, *extra):
        """R5: a pick run in this process, with `root` (a required root) moved away while the
        named function of slice.py runs and restored straight after, so it was there when the
        pick began and is back before any record. Returns (exit, output)."""
        module = load_slice()
        original = getattr(module, function)
        moved = root + ".gone"

        def gone_while_read(*args, **kwargs):
            os.rename(root, moved)
            try:
                return original(*args, **kwargs)
            finally:
                os.rename(moved, root)

        setattr(module, function, gone_while_read)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = module.main(self.argv(extra))
        check(os.path.lexists(root) and not os.path.lexists(moved), "the injection did not restore "
              "%s" % root)
        return code, searched(buffer.getvalue())

    def inject_walk(self, acquisition, root, *extra, **options):
        """T5, the third build review's race: a pick run in this process, with `root` moved away
        inside the named acquisition, after every check made before it and immediately before
        that acquisition's own walk of it, and restored straight after that walk. Returns (exit,
        output); the injection must have fired once."""
        module = load_slice()
        original = module.walk_files
        moved = root + ".gone"
        fired = []

        def walk(top, errors, *args, **kwargs):
            step = module.ACTIVE[-1].name if module.ACTIVE else None
            if top == root and step == acquisition and not fired:
                fired.append(step)
                os.rename(root, moved)
                try:
                    return original(top, errors, *args, **kwargs)
                finally:
                    os.rename(moved, root)
            return original(top, errors, *args, **kwargs)

        module.walk_files = walk
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = module.main(self.argv(extra, options.get("today", TODAY)))
        check(fired == [acquisition], "the injection into %s did not fire once: %r"
              % (acquisition, fired))
        check(os.path.lexists(root) and not os.path.lexists(moved), "the injection did not restore "
              "%s" % root)
        return code, searched(buffer.getvalue())

    def every_item_row(self, skip=()):
        items = [".claude/skills/alpha/test_alpha.sh", ".claude/skills/beta/test_beta.py",
                 ".claude/hooks/gate.py", ".claude/hooks/test_gate.sh",
                 os.path.join(self.hooks, "guard.py"), os.path.join(self.hooks, "test_guard.sh"),
                 os.path.join(self.tools, "watch", "wait.sh"),
                 "CLAUDE.md §1", "CLAUDE.md §2", "CLAUDE.md §3",
                 "CUSTOMISATION.md §Settings", "CUSTOMISATION.md §Roles",
                 ".claude/skills/alpha/SKILL.md", NESTED_SKILL,
                 ".claude/skills/beta/SKILL.md"] + list(named_groups())
        return [row(item) for item in items if item not in skip]


def row(item, kind="suite", state="active", next_review="2026-12-01", retire="the failure ends",
        purpose="keeps x", guards="the x failure", cells=None):
    values = [item, kind, purpose, guards, "1 s", "not recorded before 2026-10-11", state, retire,
              "x returns", next_review]
    if cells is not None:
        values = values[:cells]
    return "| " + " | ".join(values) + " |"


ESCAPED_MARK = "escaped: "
# what a terminal could hide or redraw (a tab aside): no output line of slice.py may hold one
HIDING = ("Cc", "Cf", "Co", "Cs", "Cn", "Zl", "Zp")


def hidden(text):
    return [char for char in text if char != "\t" and unicodedata.category(char) in HIDING]


def unescape(shown):
    """This suite's own decoder of a line slice.py prints after `escaped: `, written apart from the
    tool's so that a fault the two shared could not pass: `\\\\` is one backslash, and `\\x`, `\\u`
    and `\\U` give the character of two, four or eight lower-case hex digits; any other backslash
    fails the case."""
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


def raw_lines(out):
    """The lines slice.py meant, each `escaped: ` line decoded, the ESCAPED note left out; output
    split at newlines only, since an escaped line holds none."""
    lines = []
    for line in out.split("\n"):
        if line.startswith("ESCAPED: "):
            continue
        lines.append(unescape(line[len(ESCAPED_MARK):]) if line.startswith(ESCAPED_MARK)
                     else line)
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def parse(out):
    """The pick's output as parts: the slice, the reading list by part, the due, malformed and
    missing lines, the held and removed lines, the INCOMPLETE and OWED lines, and the summary.
    Each `escaped: ` line is read as the line it stands for (raw_lines)."""
    result = {"slice": None, "parts": {}, "due": [], "why": [], "malformed": [], "missing": [],
              "held": [], "removed": [], "summary": None, "controls": None, "incomplete": [],
              "owed": [], "headers": {}, "requirements": []}
    section, part = None, None
    for line in raw_lines(out):
        if line.startswith("slice: "):
            result["slice"] = line.split()[1]
        elif line.startswith("READING LIST"):
            section = "reading"
        elif line.startswith("REQUIREMENT FILES ("):
            section = "requirements"
        elif section == "requirements" and line.startswith("/"):
            result["requirements"].append(line)
        elif section == "reading" and line.startswith("-- "):
            part = line[3:].split(":")[0].split(" ")[0]
            result["parts"][part] = []
            result["headers"][part] = line
        elif section == "reading" and line.startswith("/"):
            result["parts"][part].append(line)
        elif line == "":
            section = None
        elif line.startswith("DUE ROWS"):
            section = "due"
        elif line.startswith("MALFORMED ROWS"):
            section = "malformed"
        elif line.startswith("MISSING ROWS"):
            section = "missing"
        elif line.startswith("INCOMPLETE ("):
            section = "incomplete"
        elif line.startswith("OWED ("):
            section = "owed"
        elif section in ("due", "malformed", "missing", "incomplete", "owed") \
                and line.startswith("- "):
            result[section].append(line[2:])
        elif section == "due" and line.startswith("    due: "):
            result["why"].append(line[9:])
        elif line.startswith("held for the second pass"):
            result["held"].append(line.split(": ", 1)[1])
        elif line.startswith("removed (not in the reading list): "):
            result["removed"].append(line.split(": ", 1)[1])
        elif line.startswith("SUMMARY: "):
            result["summary"] = line
        elif line.startswith("CONTROLS: "):
            result["controls"] = line
    return result


def reading(result):
    return [p for paths in result["parts"].values() for p in paths]


def printed_sources(out):
    """The second-pass sources a pick printed: the path on each `- ` line of its SECOND-PASS
    SOURCES block (a deep-lint line's path before its line range)."""
    lines = out.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("SECOND-PASS SOURCES")]
    check(len(starts) == 1, "%d SECOND-PASS SOURCES blocks" % len(starts))
    listed = []
    for line in lines[starts[0] + 1:]:
        if not line:
            break
        if line.startswith("- "):
            rest = line.split(": ", 1)[1]
            match = re.match(r"(/.*?\.md)(?= lines | \(|$)", rest)
            listed.append(match.group(1) if match else rest)
    return listed


def event_log(path, steps):
    """A Codex event log in the wrapper's shape: ("read", path) is a command that cats the path,
    ("message", text) a sent agent message, each its own item in order."""
    events = [{"type": "thread.started", "thread_id": "t-1"}, {"type": "turn.started"}]
    for number, (kind, value) in enumerate(steps, 1):
        ident = "item_%d" % number
        if kind == "message":
            events.append({"type": "item.completed",
                           "item": {"id": ident, "type": "agent_message", "text": value}})
            continue
        command = "/bin/zsh -lc \"/bin/cat '%s'\"" % value
        for phase, status, code in (("item.started", "in_progress", None),
                                    ("item.completed", "completed", 0)):
            events.append({"type": phase, "item": {"id": ident, "type": "command_execution",
                                                   "command": command, "aggregated_output": "",
                                                   "exit_code": code, "status": status}})
    events.append({"type": "turn.completed", "usage": {"input_tokens": 1}})
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(json.dumps(e) for e in events) + "\n")
    return path


def run_pass_order(events):
    """pass_order.py over a log: (exit, its output)."""
    done = subprocess.run([sys.executable, "-B", PASS_ORDER, "--events", events],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                          timeout=TIMEOUT_S)
    return done.returncode, searched(done.stdout)


def has(paths, suffix):
    return any(p.replace(os.sep, "/").endswith(suffix) for p in paths)


def digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def status_of(manifest, name):
    found = [a["status"] for a in manifest["acquisitions"] if a["name"] == name]
    check(len(found) == 1, "the manifest holds %d acquisition(s) named %r" % (len(found), name))
    return found[0]


def tree_manifest(top):
    """Every folder and file under `top`: its relative path, mode and (for a file) its hash."""
    entries = []
    for dirpath, dirnames, filenames in os.walk(top):
        dirnames.sort()
        entries.append(("dir", os.path.relpath(dirpath, top), stat.S_IMODE(os.stat(dirpath).st_mode)))
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            entries.append(("file", os.path.relpath(path, top), digest(path),
                            stat.S_IMODE(os.stat(path).st_mode)))
    return entries


def refused_unchanged(world, extra, expected, before):
    """A refused run: exit 2, its reason, nothing recorded, slices.json byte for byte the same."""
    code, out, _ = world.run(*extra)
    check(code == 2 and out.startswith("REFUSED") and expected in out,
          "%r: exit %d, %r expected in %s" % (extra, code, expected, out[:300]))
    check("RECORDED" not in out and "READING LIST" not in out, "work went on after the refusal")
    check(digest(world.state) == before, "%r changed slices.json" % (extra,))


def unreadable(world, rel):
    """Make one fixture file unreadable to the pick (mode 000, or a dangling link as root, whom
    mode 000 does not stop); returns the function that restores it with its content unchanged."""
    path = world.path(rel)
    with open(path, "rb") as handle:
        content = handle.read()
    if os.geteuid() == 0:
        os.unlink(path)
        os.symlink(path + ".nowhere", path)

        def restore():
            os.unlink(path)
            with open(path, "wb") as handle:
                handle.write(content)
    else:
        os.chmod(path, 0)

        def restore():
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    return restore


@contextlib.contextmanager
def refused_metadata(paths, calls=("lstat", "stat")):
    """A metadata error, planted in this process: os.lstat and os.stat (those named in `calls`)
    raise PermissionError for the given paths alone while the block runs, as they would under a
    folder that can be listed but not searched. os.path.isdir, isfile, exists, lexists and islink
    go through these calls, so a reader that turns an error into "not there" meets the plant."""
    targets = set(os.path.abspath(p) for p in paths)
    saved = dict((name, getattr(os, name)) for name in calls)

    def make(name):
        real = saved[name]

        def call(path, *args, **kwargs):
            if isinstance(path, (str, bytes)) and not kwargs.get("dir_fd") \
                    and os.path.abspath(os.fsdecode(path)) in targets:
                raise PermissionError(13, "Permission denied (planted)", os.fsdecode(path))
            return real(path, *args, **kwargs)
        return call
    for name in calls:
        setattr(os, name, make(name))
    try:
        yield
    finally:
        for name, real in saved.items():
            setattr(os, name, real)


@contextlib.contextmanager
def unsearchable(folder):
    """A folder that can be listed but not searched (mode r--), so each name in it is listed while
    its metadata cannot be read: the file system's own metadata error. Restored after the block."""
    os.chmod(folder, stat.S_IRUSR)
    try:
        yield
    finally:
        os.chmod(folder, stat.S_IRWXU)


def hooks_hashes(world):
    return dict((k, v) for k, v in world.state_data()["baseline"]["hashes"].items()
                if k.startswith("hooks/"))


def due_row_world(world):
    """The fixture with one due lifecycle row (gate.py, overdue) and a recorded baseline."""
    rows = world.every_item_row(skip=(".claude/hooks/gate.py",))
    rows.append(row(".claude/hooks/gate.py", kind="hook", next_review="2026-10-04"))
    world.lifecycle(rows)
    world.record("standing-rules")
    return rows


# ------------------------------------------------------------------ cases --------------------

def case_touched_unchanged_not_listed(world):
    """Design 2, Tests: a file touched with unchanged content is not listed; a changed one is."""
    world.record("standing-rules")
    touched = world.path("vault/.claude/skills/alpha/run.py")
    later = os.stat(touched).st_mtime + 86400
    os.utime(touched, (later, later))
    world.write("vault/wiki/developments/design.md", "# Design\n\nchanged this week\n")
    world.write("vault/.claude/skills/beta/new.py", "print('new')\n")
    os.remove(world.path("tools/thing.py"))
    code, out, _ = world.run()
    result = parse(out)
    changed = result["parts"].get("changed", [])
    check(code == 0, "exit %d, 0 expected" % code)
    check(not has(changed, "alpha/run.py"), "the touched, unchanged file was listed")
    check(has(changed, "developments/design.md"), "the changed file was not listed")
    check(has(changed, "beta/new.py"), "the new file was not listed")
    check(has(result["removed"], "tools/thing.py") and not has(reading(result), "thing.py"),
          "the removed file was not reported apart from the reading list")
    check("1 changed, 1 new, 1 removed" in out, "the changed counts are wrong")


def case_missing_state_refuses(world):
    """S6, design 2, Tests: with no slices.json after install, a pick and a record refuse, saying
    that --init is the install step and a missing file is a continuity failure, and create
    nothing."""
    manifest, _ = world.pick()
    report = world.report()
    os.remove(world.state)
    folder = sorted(os.listdir(os.path.dirname(world.state)))
    for extra in ((), ("--record", "standing-rules", "--findings", "0", "--manifest", manifest,
                       "--report", report)):
        code, out, _ = world.run(*extra)
        check(code == 2 and out.startswith("REFUSED: there is no slices.json"),
              "%r with no slices.json: %d %s" % (extra, code, out[:300]))
        flat = " ".join(out.split())
        check("`slice.py --init` is the install step" in flat
              and "continuity failure" in flat and "never a fresh start" in flat,
              "the refusal does not name the install step and the continuity failure: %s" % flat)
        check("READING LIST" not in out and "RECORDED" not in out, "work went on after it")
        check(sorted(os.listdir(os.path.dirname(world.state))) == folder,
              "the refusal created something: %r" % os.listdir(os.path.dirname(world.state)))


def case_init_creates_then_first_pick(world):
    """S6: --init creates slices.json with no audits and no baseline; the first pick after it lists
    no changed files and says the baseline is recorded at this audit, and changes nothing."""
    os.remove(world.state)
    code, out, _ = world.run("--init")
    check(code == 0 and out.startswith("INITIALISED: %s" % world.state), "--init: %d %s"
          % (code, out))
    data = world.state_data()
    check(data["version"] == 4 and data["audits"] == [] and data["baseline"] is None
          and data["owed"] == []
          and datetime.datetime.fromisoformat(data["initialised"]).tzinfo is not None,
          "the initialised slices.json: %r" % data)
    check(not [n for n in os.listdir(os.path.dirname(world.state)) if n.endswith(".tmp")],
          "--init left a temporary file")
    before = digest(world.state)
    code, out, _ = world.run()
    result = parse(out)
    check(code == 0, "exit %d, 0 expected" % code)
    check(result["parts"].get("changed") == [], "the changed part is not empty")
    check("the baseline is recorded at this audit" in " ".join(out.split()),
          "the first-baseline line is missing")
    check("changed none: baseline recorded at this audit" in result["summary"], "the summary")
    check(digest(world.state) == before, "the first pick changed slices.json")


def case_default_paths_outside_the_skill(world):
    """Run from its shipped home with no path named, --init keeps the state in the run store and writes
    nothing beside the script, whose folder ships. The folder is setup.sh's to make, so with none there
    it refuses and makes nothing; a second --init refuses too."""
    skill = os.path.join(world.root, "copy", ".claude", "skills", "weekly-audit")
    os.makedirs(skill)
    script = os.path.join(skill, "slice.py")
    shutil.copy2(SLICE, script)
    store = os.path.join(world.root, "fresh-store")
    env = dict(os.environ, LLM_WIKI_STORE=store)
    for name in ("CLAUDE_PROJECT_DIR", "LLM_WIKI_VAULT"):
        env.pop(name, None)
    run = lambda *extra: subprocess.run([sys.executable, "-B", script] + list(extra), env=env,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        universal_newlines=True)
    state = os.path.join(store, "tools", "weekly-audit", "slices.json")
    absent = run("--init")
    check(absent.returncode == 2 and "PROBE FAILED" in absent.stdout and not os.path.exists(store),
          "--init with no folder made: %d %s" % (absent.returncode, absent.stdout))
    os.makedirs(os.path.dirname(state))
    done = run("--init")
    check(done.returncode == 0 and done.stdout.startswith("INITIALISED: %s" % state),
          "--init with no path named: %d %s" % (done.returncode, done.stdout))
    check(os.listdir(skill) == ["slice.py"], "--init wrote beside the script: %r" % os.listdir(skill))
    again = run("--init")
    check(again.returncode == 2 and again.stdout.startswith("REFUSED: %s exists" % state),
          "a second --init: %d %s" % (again.returncode, again.stdout))


def case_second_init_refuses(world):
    """S6: a second --init refuses and leaves slices.json as it was, records included."""
    world.record("standing-rules")
    before = digest(world.state)
    code, out, _ = world.run("--init")
    check(code == 2 and out.startswith("REFUSED: %s exists" % world.state), "a second --init: %d %s"
          % (code, out))
    check(digest(world.state) == before, "a second --init changed slices.json")
    check(not [n for n in os.listdir(os.path.dirname(world.state)) if n.endswith(".tmp")],
          "a refused --init left a temporary file")
    for extra in (("--init", "--record", "tools", "--findings", "0"), ("--init", "--manifest-out",
                                                                       world.manifest_path())):
        code, out, _ = world.run(*extra)
        check(code == 2 and "--init takes no" in out, "%r: %d %s" % (extra, code, out))


def case_least_recently_attempted(world):
    """Design 2, Tests, item 7: the least recently attempted rotating slice is picked, and a slice
    never attempted comes first."""
    world.record("standing-rules")
    world.set_audits([("standing-rules", "2026-09-01", 0), ("skill:alpha", "2026-09-08", 0),
                      ("skill:beta", "2026-08-25", 0), ("register", "2026-09-15", 0),
                      ("hooks-and-monitors", "2026-09-22", 0), ("tools", "2026-09-29", 0)])
    check(parse(world.run()[1])["slice"] == "skill:beta", "the oldest attempt was not picked")
    world.set_audits([("standing-rules", "2026-09-01", 0), ("skill:alpha", "2026-09-08", 0),
                      ("skill:beta", "2026-08-25", 0), ("register", "2026-09-15", 0),
                      ("hooks-and-monitors", "2026-09-22", 0)])
    check(parse(world.run()[1])["slice"] == "tools", "a never-attempted slice did not come first")


def case_ties_by_findings_then_changes(world):
    """Ties on the last attempt's date go to more changed files, then more findings, then order."""
    world.record("standing-rules")
    base = [("skill:alpha", "2026-09-08", 0), ("register", "2026-09-15", 0),
            ("hooks-and-monitors", "2026-09-22", 0), ("tools", "2026-09-29", 0)]
    world.set_audits(base + [("standing-rules", "2026-08-25", 0), ("skill:beta", "2026-08-25", 0)])
    check(parse(world.run()[1])["slice"] == "standing-rules", "rotation order did not break a tie")
    world.set_audits(base + [("standing-rules", "2026-08-25", 0), ("skill:beta", "2026-08-25", 5)])
    check(parse(world.run()[1])["slice"] == "skill:beta", "findings did not break a tie")
    with open(world.path("vault/CLAUDE.md"), encoding="utf-8") as handle:
        text = handle.read()
    world.write("vault/CLAUDE.md", text + "\nmore\n")
    check(parse(world.run()[1])["slice"] == "standing-rules", "changes did not break a tie")


def case_due_and_missing_always_included(world):
    """Design 2, Tests: due rows and unregistered inventory items are always in the slice."""
    world.record("standing-rules")
    world.set_audits([("hooks-and-monitors", "2026-10-11", 0), ("tools", "2026-10-11", 0),
                      ("skill:alpha", "2026-10-11", 0), ("skill:beta", "2026-10-11", 0),
                      ("register", "2026-10-11", 0)])
    guard = os.path.join(world.hooks, "guard.py")
    rows = [r for r in world.every_item_row(skip=(guard, ".claude/skills/beta/test_beta.py"))]
    rows.append(row(guard, kind="hook", next_review="2026-10-01"))
    world.lifecycle(rows)
    code, out, _ = world.run()
    result = parse(out)
    check(code == 0, "exit %d, 0 expected" % code)
    check(result["slice"] == "standing-rules", "the fixture did not pick standing-rules")
    check(has(result["parts"].get("due", []), "hooks/guard.py"), "the due row's file is missing")
    check(has(result["parts"].get("unregistered", []), "beta/test_beta.py"),
          "the unregistered item's file is missing")


def case_missing_rows_listed_then_cleared(world):
    """Design 3, Tests: a missing text-group row and a missing script row are both listed, and
    neither once their rows exist; a new unregistered script is listed."""
    world.lifecycle(world.every_item_row(skip=("CLAUDE.md §2",
                                               ".claude/skills/alpha/test_alpha.sh")))
    result = parse(world.run()[1])
    check(any(m.startswith("CLAUDE.md §2 |") for m in result["missing"]),
          "the text group with no row was not listed: %r" % result["missing"])
    check(any(m.startswith(".claude/skills/alpha/test_alpha.sh |") for m in result["missing"]),
          "the script with no row was not listed")
    check(len(result["missing"]) == 2, "unexpected missing rows %r" % result["missing"])
    world.lifecycle(world.every_item_row())
    code, out, _ = world.run()
    result = parse(out)
    check(code == 0 and result["missing"] == [] and "MISSING ROWS (0" in out,
          "rows listed as missing once they exist: %r" % result["missing"])
    world.write("vault/.claude/skills/beta/test_gamma.sh", "echo new\n")
    result = parse(world.run()[1])
    check([m.split(" |")[0] for m in result["missing"]] == [".claude/skills/beta/test_gamma.sh"],
          "a new unregistered script was not listed: %r" % result["missing"])


def case_overdue_unchanged_appears(world):
    """Design 3, Tests: an overdue row whose files have not changed still appears."""
    world.record("standing-rules")
    rows = world.every_item_row(skip=(".claude/hooks/gate.py",))
    rows.append(row(".claude/hooks/gate.py", kind="hook", next_review="2026-10-04"))
    world.lifecycle(rows)
    result = parse(world.run()[1])
    check(result["parts"].get("changed") == [], "files changed in the fixture")
    check(any(d.startswith(".claude/hooks/gate.py |") for d in result["due"]),
          "the overdue row is missing")
    check(any(w.startswith("overdue by 14 d") for w in result["why"]), "why %r" % result["why"])
    check(has(result["parts"].get("due", []), ".claude/hooks/gate.py"),
          "the overdue row's file is not in the reading list")


def case_not_yet_due_absent(world):
    """Design 3, Tests: a row not yet due does not appear; a retired row is never due."""
    rows = world.every_item_row(skip=(".claude/hooks/gate.py", ".claude/hooks/test_gate.sh"))
    rows.append(row(".claude/hooks/gate.py", kind="hook", next_review="2026-10-19"))
    rows.append(row(".claude/hooks/test_gate.sh", state="retired", next_review="2026-01-01"))
    world.lifecycle(rows)
    result = parse(world.run()[1])
    check(result["due"] == [] and result["parts"].get("due") == [],
          "a row not yet due, or a retired row, appeared: %r" % result["due"])


def case_due_by_state_and_order(world):
    """Review due and quarantined rows are due whatever their date; overdue rows come first."""
    rows = world.every_item_row(skip=(".claude/hooks/gate.py", ".claude/hooks/test_gate.sh",
                                      ".claude/skills/beta/test_beta.py", "CLAUDE.md §1"))
    rows += [row(".claude/hooks/gate.py", state="review due", next_review="2026-12-01"),
             row(".claude/hooks/test_gate.sh", state="quarantined", next_review="2026-12-01"),
             row(".claude/skills/beta/test_beta.py", next_review="2026-10-18"),
             row("CLAUDE.md §1", kind="text", next_review="2026-09-01")]
    world.lifecycle(rows)
    result = parse(world.run()[1])
    order = [d.split(" |")[0] for d in result["due"]]
    check(order == ["CLAUDE.md §1", ".claude/skills/beta/test_beta.py",
                    ".claude/hooks/gate.py", ".claude/hooks/test_gate.sh"],
          "due order %r" % order)
    check(has(result["parts"].get("due", []), "/vault/CLAUDE.md"),
          "a text-group row did not resolve to its file")


def case_malformed_rows_listed(world):
    """Design 3, Tests: a row with no review date is listed as malformed, and so is each other
    malformation; a due row that is malformed is listed as due and flagged."""
    rows = world.every_item_row()
    rows += [row("no-date.sh", next_review=""), row("no-retire.sh", retire="—"),
             row("bad-kind.sh", kind="gadget"), row("short.sh", cells=9),
             row("bad-date.sh", next_review="2026-13-01"), row("bad-state.sh", state="paused"),
             row("due-flagged.sh", next_review="2026-10-01", retire="")]
    world.lifecycle(rows)
    code, out, _ = world.run()
    result = parse(out)
    names = dict((m.split(" |")[0], m) for m in result["malformed"])
    check(code == 0, "exit %d" % code)
    for name, reason in (("no-date.sh", "no Next review"), ("no-retire.sh", "no Retire when"),
                         ("bad-kind.sh", "Kind 'gadget'"), ("short.sh", "9 cells"),
                         ("bad-date.sh", "not a YYYY-MM-DD date"), ("bad-state.sh", "State 'paused'")):
        check(name in names and reason in names[name], "%s not listed with %r: %r"
              % (name, reason, names.get(name)))
    check(any("MALFORMED: no Retire when" in w for w in result["why"]),
          "the due, malformed row was not flagged: %r" % result["why"])


def case_unreadable_state_refuses(world):
    """Design 2, Tests: an unreadable or malformed slices.json refuses rather than starting over,
    the first build's format included, and so does each part-read the third build review's sweep
    found: a key given twice (which a lenient reader settles by keeping its last value), a NaN, an
    audit whose completeness disagrees with its reasons, and undecodable bytes."""
    manifest, _ = world.pick()
    world.record("standing-rules", manifest=manifest)
    report = world.report()
    good = world.state_data()
    bad_count = {"version": 4, "initialised": PAST, "baseline": None, "owed": [],
                 "audits": [{"date": "2026-10-11", "slice": "tools", "findings": -1,
                             "recorded": PAST, "manifest_taken": PAST, "complete": True,
                             "reasons": []}]}
    bad_owed = dict(good, owed=[{"entry": "elsewhere/x.py", "since": "2026-10-11"}])
    first_build = {"version": 1, "audits": [], "hashes": {}, "hashes_date": "2026-10-11"}
    second_build = {"version": 2, "initialised": PAST, "audits": [], "baseline": None}
    fifth_build = dict(good, version=3, audits=[dict((k, v) for k, v in a.items()
                                                     if k != "reasons") for a in good["audits"]])
    disagrees = dict(good, audits=[dict(a, complete=True, reasons=["a reason"])
                                   for a in good["audits"]])
    # the key given twice: a stray history first, the real one after, which a lenient reader keeps
    twice = '{"audits": [], ' + json.dumps(good)[1:]
    for content in (twice, json.dumps(good).replace('"findings": 0', '"findings": NaN', 1),
                    "{not json", json.dumps(bad_count), json.dumps(bad_owed),
                    json.dumps(first_build), json.dumps(second_build), json.dumps(fifth_build),
                    json.dumps(disagrees)):
        with open(world.state, "w", encoding="utf-8") as handle:
            handle.write(content)
        before = digest(world.state)
        for extra in ((), ("--record", "tools", "--findings", "1", "--manifest", manifest,
                           "--report", report)):
            code, out, _ = world.run(*extra)
            check(code == 2 and out.startswith("REFUSED: slices.json is malformed"),
                  "a malformed slices.json did not refuse (%d): %s" % (code, out[:200]))
            check("READING LIST" not in out and "RECORDED" not in out, "work went on after it")
            check(digest(world.state) == before, "the malformed slices.json was changed")
    with open(world.state, "wb") as handle:
        handle.write(json.dumps(good).encode("utf-8")[:-1] + b' \xff}')
    code, out, _ = world.run()
    check(code == 2 and out.startswith("REFUSED: slices.json is unreadable") and "not UTF-8" in out,
          "undecodable bytes in slices.json did not refuse (%d): %s" % (code, out[:200]))
    os.remove(world.state)
    os.mkdir(world.state)
    code, out, _ = world.run()
    check(code == 2 and out.startswith("REFUSED: slices.json is unreadable"),
          "a slices.json that cannot be read did not refuse (%d): %s" % (code, out[:200]))
    os.rmdir(world.state)
    if os.geteuid() != 0:
        world.write("tools/weekly-audit/slices.json", "{}")
        os.chmod(world.state, 0)
        try:
            code, out, _ = world.run()
        finally:
            os.chmod(world.state, stat.S_IRUSR | stat.S_IWUSR)
        check(code == 2 and out.startswith("REFUSED: slices.json is unreadable"),
              "an unreadable slices.json did not refuse (%d): %s" % (code, out[:200]))


def case_fenced_heading_not_a_group(world):
    """Text groups are the top-level sections markdown-it reads (the fixture's fenced example of a
    log entry heading is no section; its HTML comments hold no heading-like line, and
    section_adapter_projection plants the shapes that do), and every SKILL.md under .claude/skills
    at any depth (F5); the named groups come last (F4), the two inline hooks among them."""
    world.lifecycle([])
    result = parse(world.run()[1])
    groups = [m.split(" |")[0] for m in result["missing"] if m.endswith("| text group")]
    check(groups == ["CLAUDE.md §1", "CLAUDE.md §2", "CLAUDE.md §3",
                     "CUSTOMISATION.md §Settings", "CUSTOMISATION.md §Roles",
                     ".claude/skills/alpha/SKILL.md", NESTED_SKILL, ".claude/skills/beta/SKILL.md"],
          "text groups %r" % groups)
    named = ["%s | named group" % name for name in named_groups()]
    check("reflection controls | named group" in named
          and result["missing"][-len(named):] == named,
          "the named groups are not last: %r" % result["missing"][-len(named):])
    check("hook 4" in result["controls"] and "watch tool 1" in result["controls"]
          and "test script 2" in result["controls"] and "text group 8" in result["controls"]
          and "named group %d" % len(named) in result["controls"]
          and "sections read: CLAUDE.md 3, CUSTOMISATION.md 2" in result["controls"],
          "inventory %r" % result["controls"])


def case_exclusions_not_hashed(world):
    """S4: __pycache__ and node_modules folders, *.bak* and .DS_Store files and slices.json itself
    are never hashed, never count as changes and never enter the inventory or a reading list; the
    dependency pin files beside node_modules stay hashed, so a pin change is listed."""
    for rel, text in (("tools/pin/package.json", '{"name": "pin"}\n'),
                      ("tools/pin/package-lock.json", '{"lockfileVersion": 3}\n'),
                      ("tools/pin/node_modules/dep/package.json", '{"name": "dep"}\n'),
                      ("vault/.claude/skills/alpha/node_modules/dep/test_dep.py", "x = 1\n"),
                      ("hooks/node_modules/x/cli.sh", "echo x\n"),
                      ("tools/watch/node_modules/w/run.py", "x = 1\n"),
                      ("hooks/.DS_Store", "finder\n"), ("vault/.claude/.DS_Store", "finder\n"),
                      ("tools/watch/.DS_Store", "finder\n")):
        world.write(rel, text)
    world.record("standing-rules")
    world.record("skill:alpha", today="2026-10-12")
    for rel in ("vault/.claude/skills/alpha/__pycache__/run.cpython.pyc",
                "vault/.claude/skills/alpha/run.py.bak-1", "hooks/guard.py.bak-2",
                "tools/pin/node_modules/dep/index.js", "tools/pin/node_modules/dep/package.json",
                "vault/.claude/skills/alpha/node_modules/dep/test_dep.py",
                "hooks/.DS_Store", "vault/.claude/.DS_Store"):
        world.write(rel, "changed\n")
    world.set_audits([(s, "2026-10-12", 0) for s in ("standing-rules", "skill:alpha", "skill:beta",
                                                     "register", "tools")])
    code, out, _ = world.run()
    result = parse(out)
    check(code == 0, "exit %d" % code)
    check(result["parts"].get("changed") == [] and "0 changed, 0 new, 0 removed" in out,
          "an excluded file counted as a change: %r" % result["parts"].get("changed"))
    keys = world.state_data()["baseline"]["hashes"]
    check(not any("__pycache__" in k or ".bak" in k or k.endswith("slices.json")
                  or "node_modules" in k or k.endswith(".DS_Store") for k in keys),
          "an excluded file was hashed: %r" % [k for k in keys if "node_modules" in k
                                               or ".DS_Store" in k])
    check("tools/pin/package.json" in keys and "tools/pin/package-lock.json" in keys,
          "a dependency pin file was not hashed")
    check(result["missing"] == [], "a vendored script entered the inventory: %r" % result["missing"])
    check(result["slice"] == "hooks-and-monitors", "the fixture picked %s" % result["slice"])
    check(not any("node_modules" in p or p.endswith(".DS_Store") for p in reading(result)),
          "a vendored or stray file entered the reading list: %r" % reading(result))
    check(re.search(r"skipped __pycache__ [1-9]\d* folder\(s\), node_modules [1-9]\d* folder\(s\), "
                    r"\*\.bak\* [1-9]\d* file\(s\), \.DS_Store [1-9]\d* file\(s\)",
                    result["controls"]), "the skip counts (the control) %r" % result["controls"])
    world.write("tools/pin/package-lock.json", '{"lockfileVersion": 3, "changed": true}\n')
    result = parse(world.run()[1])
    check([p.replace(os.sep, "/").split("/tools/")[-1] for p in result["parts"].get("changed", [])]
          == ["pin/package-lock.json"], "a pin change was not listed alone: %r"
          % result["parts"].get("changed"))


def case_second_pass_sources_held(world):
    """The register and the lifecycle page stay out of the reading list, changed or not, unless
    the slice is the register itself; deep-lint's latest entry is located."""
    world.lifecycle(world.every_item_row())
    world.record("standing-rules")
    world.write("vault/wiki/developments/known-issues.md", REGISTER_TEXT.replace("- entry",
                                                                                "- new"))
    world.lifecycle(world.every_item_row() + [row("late.sh")])
    world.set_audits([("standing-rules", "2026-10-11", 0), ("register", "2026-10-11", 0)])
    code, out, _ = world.run()
    result = parse(out)
    check(result["slice"] == "skill:alpha", "fixture picked %s" % result["slice"])
    check(not has(reading(result), "known-issues.md") and not has(reading(result),
                                                                  "check-lifecycle.md"),
          "a second-pass source entered the reading list")
    check(has(result["held"], "known-issues.md") and has(result["held"], "check-lifecycle.md"),
          "the held, changed sources were not named: %r" % result["held"])
    check(DEEPLINT_LINES in out, "deep-lint's latest entry was not located")
    world.set_audits([(s, "2026-10-11", 0) for s in ("standing-rules", "skill:alpha", "skill:beta",
                                                     "hooks-and-monitors", "tools")])
    result = parse(world.run()[1])
    check(result["slice"] == "register", "fixture picked %s" % result["slice"])
    check(has(reading(result), "known-issues.md") and reading(result).count(
        os.path.join(world.vault, "wiki", "developments", "known-issues.md")) == 1,
          "the register slice does not read the register exactly once")
    check(not has(reading(result), "check-lifecycle.md"), "the lifecycle page entered pass 1")


def case_record_atomic(world):
    """--record writes the audit and the manifest's hashes through a temporary file and a replace,
    leaves no temporary file, and refuses a repeat, an unknown slice, a slice other than the one
    the manifest's pick chose (CR-AUDIT14 F1: refused before anything is committed, naming the
    pick's slice, never recorded with a warning) and bad counts; each record names its pick's
    slice."""
    manifest, _ = world.pick()
    refused_unchanged(world, ("--record", "skill:alpha", "--findings", "3", "--manifest", manifest,
                              "--report", world.report()),
                      "the manifest's pick chose slice standing-rules", digest(world.state))
    out = world.record("standing-rules", findings=3, today=TODAY, manifest=manifest)
    check("RECORDED: 2026-10-18 · slice standing-rules · findings 3" in out
          and not [line for line in out.splitlines() if line.startswith("warning")], out)
    data = world.state_data()
    taken = load(manifest)["taken"]
    audits = data["audits"]
    check(len(audits) == 1 and dict((k, audits[0][k]) for k in ("date", "slice", "findings"))
          == {"date": TODAY, "slice": "standing-rules", "findings": 3}
          and audits[0]["manifest_taken"] == taken
          and datetime.datetime.fromisoformat(audits[0]["recorded"])
          > datetime.datetime.fromisoformat(taken), "audits %r" % audits)
    check(data["baseline"]["taken"] == taken and "vault/CLAUDE.md" in data["baseline"]["hashes"],
          "the manifest was not stored as the baseline")
    for folder in (os.path.dirname(world.state), world.out):
        check(not [n for n in os.listdir(folder) if n.endswith(".tmp")],
              "a temporary file was left in %s" % folder)
    before = digest(world.state)
    report = world.report()
    for extra, expected in ((("--record", "standing-rules", "--findings", "1", "--manifest",
                              manifest, "--report", report), "already recorded"),
                            (("--record", "skil:alpha", "--findings", "1", "--manifest", manifest,
                              "--report", report), "nearest: skill:alpha"),
                            (("--findings", "1"), "go together"),
                            (("--record", "standing-rules", "--findings", "-1", "--manifest",
                              manifest, "--report", report), "0 or more"),
                            (("--record", "standing-rules", "--findings", "x"), "invalid int"),
                            (("--manifest", manifest), "--manifest goes with --record"),
                            (("--report", report), "--report goes with --record"),
                            (("--record", "standing-rules", "--findings", "0", "--manifest",
                              manifest), "--record needs --report"),
                            (("--record", "standing-rules", "--findings", "0", "--manifest",
                              manifest, "--report", report, "--manifest-out",
                              world.manifest_path()), "goes with a pick")):
        refused_unchanged(world, extra, expected, before)
    # the pick of 2026-10-25 comes round to skill:alpha, standing-rules being attempted
    out = world.record("skill:alpha", findings=0, today="2026-10-25")
    check("changed since the pick, so not in this baseline (the next pick lists them): 0 changed, "
          "0 new, 0 removed" in out, out)


def case_manifest_out_writes_one_path(world):
    """S5: --manifest-out makes the pick write its manifest (time, roots, slice, every file's
    hash, its acquisitions, its reading list, its slices, (D18) its requirement files and
    second-pass sources, (CR-AUDIT11 F3) its comparison sources whatever their phase, and
    (CR-AUDIT13 F2) each owed entry's files held for the second pass, version 8) to that one path
    and nothing else,
    after every acquisition has reported; without it the pick names no manifest; a folder that
    does not exist, or a path inside a hashed root, is refused with nothing written."""
    before = tree_manifest(world.root)
    manifest = os.path.join(world.out, "m.json")
    code, out, _ = world.run("--manifest-out", manifest)
    after = tree_manifest(world.root)
    check(code == 0 and "manifest: written to %s" % manifest in out, "the pick: %d %s"
          % (code, out[:300]))
    extra = sorted(set(after) - set(before))
    check(len(after) == len(before) + 1 and len(extra) == 1
          and extra[0][:2] == ("file", os.path.join("out", "m.json")),
          "the pick wrote other than its one manifest: %r" % (sorted(set(after) ^ set(before)),))
    data = load(manifest)
    check(sorted(data) == ["acquisitions", "comparison", "complete", "date", "hashes", "kind",
                           "labels_limited", "owed", "reading", "requirements", "roots", "slice",
                           "slices", "sources", "taken", "unread", "version"]
          and data["version"] == 8, "manifest keys %r, version %r" % (sorted(data),
                                                                     data["version"]))
    result = parse(out)
    check(data["complete"] is True and data["unread"] == [] and data["labels_limited"] is False
          and "acquisitions all ok" in result["summary"]
          and all(a["status"] == "ok" for a in data["acquisitions"]),
          "a pick that read everything is not marked complete: %r %r"
          % (data["complete"], data["acquisitions"]))
    check("after all %d acquisitions reported" % len(data["acquisitions"]) in out
          and len(data["acquisitions"]) >= 14, "the manifest line does not say every acquisition "
          "reported first: %r" % [l for l in out.splitlines() if l.startswith("manifest:")])
    check(data["version"] == 8 and data["owed"] == [] and data["reading"] == reading(result)
          and data["slices"] == ["standing-rules", "skill:alpha", "skill:beta", "register",
                                 "hooks-and-monitors", "tools"],
          "the manifest's version, owed, reading list or slices: %r %r %r" % (
              data["version"], data["reading"], data["slices"]))
    check(data["roots"] == {"vault": world.vault, "tools": world.tools, "hooks": world.hooks}
          and data["slice"] == result["slice"] and data["date"] == TODAY
          and datetime.datetime.fromisoformat(data["taken"]).tzinfo is not None,
          "the manifest's time, roots or slice: %r" % dict((k, data[k]) for k in data
                                                            if k != "hashes"))
    check(data["hashes"].get("vault/CLAUDE.md") == digest(world.path("vault/CLAUDE.md"))
          and data["hashes"].get("hooks/guard.py") == digest(world.path("hooks/guard.py")),
          "the manifest's hashes are not the files' sha256")
    code, out, _ = world.run()
    check(code == 0 and "manifest: none written (no --manifest-out)" in out, "the plain pick")
    before = tree_manifest(world.root)
    for path, expected in ((os.path.join(world.root, "nowhere", "m.json"), "does not exist"),
                           (world.path("tools/weekly-audit/m.json"), "inside the hashed root"),
                           (world.state, "slices.json itself"), (world.out, "is a folder")):
        code, out, _ = world.run("--manifest-out", path)
        check(code == 2 and expected in out, "--manifest-out %s: %d %s" % (path, code, out[:200]))
    check(tree_manifest(world.root) == before, "a refused --manifest-out wrote something")


def case_changed_between_pick_and_record_listed(world):
    """S5, design 2, Tests: the baseline is what the audit read, so a file changed between the
    pick and the record (a fix made during the dispositions) is listed at the next pick."""
    manifest, _ = world.pick(today="2026-10-11")
    world.write("vault/CLAUDE.md", "# Schema\n\n## 1. One\nrule one, fixed\n")
    world.write("vault/.claude/skills/beta/fix.py", "print('fix')\n")
    out = world.record("standing-rules", today="2026-10-11", manifest=manifest)
    check("(the next pick lists them): 1 changed, 1 new, 0 removed" in out,
          "the record did not name what changed after the pick: %s" % out)
    result = parse(world.run()[1])
    changed = result["parts"].get("changed", [])
    check(has(changed, "vault/CLAUDE.md") and has(changed, "beta/fix.py") and len(changed) == 2,
          "the fix made after the pick is not listed at the next pick: %r" % changed)


def case_record_refuses_without_manifest(world):
    """S5: --record with no --manifest refuses and leaves slices.json unchanged."""
    world.pick()
    before = digest(world.state)
    refused_unchanged(world, ("--record", "standing-rules", "--findings", "0"),
                      "--record needs --manifest", before)


def case_record_refuses_other_roots(world):
    """S5: a manifest taken over other roots refuses and leaves slices.json unchanged; the same
    manifest recorded over its own roots is accepted (the control)."""
    other = world.path("hooks-elsewhere")
    os.makedirs(other)
    with open(os.path.join(other, "other.py"), "w", encoding="utf-8") as handle:
        handle.write("print('other')\n")
    manifest, _ = world.pick(TODAY, "--hooks", other)
    report = world.report()
    before = digest(world.state)
    refused_unchanged(world, ("--record", "standing-rules", "--findings", "0", "--manifest",
                              manifest, "--report", report), "was taken over other roots (hooks",
                      before)
    code, out, _ = world.run("--record", "standing-rules", "--findings", "0", "--manifest",
                             manifest, "--report", report, "--hooks", other)
    check(code == 0 and out.startswith("RECORDED"), "the control record over its own roots: %d %s"
          % (code, out[:200]))


def case_record_refuses_older_manifest(world):
    """S5: a manifest taken before the last record refuses and leaves slices.json unchanged; a
    manifest taken after it is accepted (the control). Each run names its own manifest's slice
    (CR-AUDIT14 F1), so the refusal has one cause: the first manifest's standing-rules, and the
    second pick's skill:alpha, standing-rules being attempted."""
    first, _ = world.pick(today="2026-10-11")
    world.record("standing-rules", today="2026-10-11", manifest=first)
    second, _ = world.pick()
    report = world.report()
    before = digest(world.state)
    refused_unchanged(world, ("--record", "standing-rules", "--findings", "0", "--manifest",
                              first, "--report", report), "before the last record", before)
    code, out, _ = world.run("--record", "skill:alpha", "--findings", "0", "--manifest", second,
                             "--report", report)
    check(code == 0 and out.startswith("RECORDED"), "the control record: %d %s" % (code, out[:200]))


def case_record_refuses_unreadable_manifest(world):
    """S5: a manifest that is missing, not JSON, of the wrong shape, holding a bad hash, a folder
    or unreadable, or one whose completeness disagrees with its acquisitions, refuses and leaves
    slices.json unchanged, and so does each part-read the third build review's sweep found: a key
    given twice, a NaN, undecodable bytes, and an earlier build's manifest version (B-AUDIT11's
    version 6, which named no comparison source by itself, and B-AUDIT13's version 7, whose owed
    entries named no file held for the second pass, among them), one whose comparison sources
    disagree with its sources' own marks, and one whose owed entry names no held files, or holds
    as held a path that is no second-pass source; the good one is accepted (the control)."""
    good, _ = world.pick()
    data = load(good)
    failed = [dict(a, status="failed") if a["name"] == "rotation" else a
              for a in data["acquisitions"]]
    variants = [# the third build review's sweep: a key given twice, which a lenient reader settles
                # by keeping its last value (here, a complete manifest after an incomplete one)
                (os.path.join(world.out, "twice.json"),
                 '{"complete": false, ' + json.dumps(data)[1:], "is given twice"),
                (os.path.join(world.out, "nan.json"),
                 json.dumps(data).replace('"complete": true', '"complete": NaN', 1),
                 "NaN is not JSON"),
                (os.path.join(world.out, "absent.json"), None, "the manifest is unreadable"),
                (os.path.join(world.out, "torn.json"), '{"version": 1, "kind"',
                 "the manifest is malformed"),
                (os.path.join(world.out, "shape.json"),
                 json.dumps(dict((k, v) for k, v in data.items() if k != "taken")),
                 "the manifest is malformed"),
                (os.path.join(world.out, "hash.json"),
                 json.dumps(dict(data, hashes=dict(data["hashes"], **{"vault/CLAUDE.md": "xyz"}))),
                 "not sha256 hex"),
                (os.path.join(world.out, "slices.json"),
                 json.dumps({"version": 2, "audits": [], "baseline": None, "initialised": PAST}),
                 "the manifest is malformed"),
                (os.path.join(world.out, "partial.json"),
                 json.dumps(dict(data, complete=False, unread=[])), "says complete false"),
                (os.path.join(world.out, "claims.json"),
                 json.dumps(dict(data, complete=True, unread=["hooks/guard.py"])),
                 "says complete true"),
                (os.path.join(world.out, "claims-ok.json"),
                 json.dumps(dict(data, acquisitions=failed)), "says complete true"),
                (os.path.join(world.out, "stray.json"),
                 json.dumps(dict(data, complete=False, unread=["elsewhere/x.py"])),
                 "not a list of hash keys"),
                (os.path.join(world.out, "owed.json"), json.dumps(dict(data, owed="hooks/")),
                 "its owed is not a list"),
                (os.path.join(world.out, "v3.json"),
                 json.dumps(dict((k, v) for k, v in data.items()
                                 if k not in ("acquisitions", "reading", "slices",
                                              "labels_limited")), sort_keys=True).replace(
                     '"version": %d' % data["version"], '"version": 3'),
                 "the manifest is malformed"),
                # the first build's version-4 manifest, whose owed entries say nothing of deletion
                (os.path.join(world.out, "v4.json"),
                 json.dumps(dict(data, version=4)), "the manifest is malformed"),
                # B-AUDIT11's version-6 manifest, which named no comparison source by itself
                # (CR-AUDIT11 F3), and a comparison list disagreeing with the sources' own marks
                (os.path.join(world.out, "v6.json"),
                 json.dumps(dict((k, v) for k, v in data.items() if k != "comparison"),
                            sort_keys=True).replace('"version": %d' % data["version"],
                                                    '"version": 6'),
                 "the manifest is malformed"),
                (os.path.join(world.out, "comparison.json"), json.dumps(dict(data, comparison=[])),
                 "its comparison sources are not a list"),
                # B-AUDIT13's version-7 manifest, whose owed entries named no file held for the
                # second pass (CR-AUDIT13 F2), and an owed entry in that shape
                (os.path.join(world.out, "v7.json"), json.dumps(dict(data, version=7)),
                 "the manifest is malformed"),
                (os.path.join(world.out, "held.json"), json.dumps(dict(data, owed=[
                    {"entry": "hooks/guard.py", "files": [], "acquired": True,
                     "deleted": False}])), "its owed is not a list"),
                (os.path.join(world.out, "held-off.json"), json.dumps(dict(data, owed=[
                    {"entry": "hooks/guard.py", "files": [], "held": [data["reading"][0]],
                     "acquired": True, "deleted": False}])), "its owed is not a list")]
    for path, text, _ in variants:
        if text is not None:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
    folder = os.path.join(world.out, "folder.json")
    os.mkdir(folder)
    variants.append((folder, None, "the manifest is unreadable"))
    undecodable = os.path.join(world.out, "undecodable.json")
    with open(undecodable, "wb") as handle:
        handle.write(json.dumps(data).encode("utf-8")[:-1] + b' \xff}')
    variants.append((undecodable, None, "not UTF-8"))
    report = world.report()
    before = digest(world.state)
    for path, _, expected in variants:
        refused_unchanged(world, ("--record", "standing-rules", "--findings", "0", "--manifest",
                                  path, "--report", report), expected, before)
    if os.geteuid() != 0:
        locked = os.path.join(world.out, "locked.json")
        shutil.copyfile(good, locked)
        os.chmod(locked, 0)
        try:
            refused_unchanged(world, ("--record", "standing-rules", "--findings", "0",
                                      "--manifest", locked, "--report", report),
                              "the manifest is unreadable", before)
        finally:
            os.chmod(locked, stat.S_IRUSR | stat.S_IWUSR)
    code, out, _ = world.run("--record", "standing-rules", "--findings", "0", "--manifest", good,
                             "--report", report)
    check(code == 0 and out.startswith("RECORDED"), "the control record: %d %s" % (code, out[:200]))


def case_probe_failures(world):
    """A broken premise prints PROBE FAILED and exits 2, never a clean result."""
    code, out, _ = world.run(vault=False)
    check(code == 2 and out.startswith("PROBE FAILED: no vault"), "no vault: %d %s" % (code, out))
    world.record("standing-rules")
    data = world.state_data()
    data["baseline"]["hashes"] = {"vault/elsewhere.md": "0" * 64}
    world.set_state(data)
    code, out, _ = world.run()
    check(code == 2 and out.startswith("PROBE FAILED: no path in the stored baseline"),
          "a baseline over other roots: %d %s" % (code, out[:200]))
    code, out, _ = world.run("--hooks", os.path.join(world.root, "nowhere"))
    check(code == 2 and "PROBE FAILED: --hooks" in out, "a missing --hooks: %d" % code)


def case_group_name_row(world):
    """A due row naming a group with no file is listed with a note, and nothing breaks."""
    world.lifecycle(world.every_item_row() + [row("reflection controls", kind="controls",
                                                  next_review="2026-10-01")])
    code, out, _ = world.run()
    result = parse(out)
    check(code == 0, "exit %d" % code)
    check(any(d.startswith("reflection controls |") for d in result["due"])
          and any("a group name" in w for w in result["why"]), "why %r" % result["why"])


def case_register_slice_sources(world):
    """F1's integration, with the verdict retired: when the slice is the register, it is the first
    pass's object and no second-pass source, so a register-slice pick prints only the lifecycle
    page and deep-lint's entry and says why; an ordinary slice prints the register too. A log
    that reads the register before the PASS 1 FINDINGS message comes back from pass_order.py as
    a list holding that read, verbatim, for the head, whose table (AUDIT.md, step 6) reads it as
    slice reading in the register's week and as earlier answers in an ordinary one."""
    dev = os.path.join(world.vault, "wiki", "developments")
    register, lifecycle = (os.path.join(dev, n) for n in ("known-issues.md", "check-lifecycle.md"))
    log_md = os.path.join(world.vault, "wiki", "log.md")
    events = event_log(os.path.join(world.root, "logs", "register-slice.log"),
                       [("read", register), ("message", FINDINGS), ("read", lifecycle)])
    world.record("standing-rules")
    world.set_audits([(s, "2026-10-11", 0) for s in ("standing-rules", "skill:alpha", "skill:beta",
                                                     "hooks-and-monitors", "tools")])
    code, out, _ = world.run()
    check(code == 0 and parse(out)["slice"] == "register", "the fixture picked %s (%d)"
          % (parse(out)["slice"], code))
    check(printed_sources(out) == [lifecycle, log_md], "the register slice's sources %r"
          % printed_sources(out))
    check("not a second-pass source: the register %s" % register in out,
          "the register slice does not say why the register is no source")
    code, listed = run_pass_order(events)
    check(code == 0 and listed.startswith("COMMANDS BEFORE THE FIRST-PASS MESSAGE: 1 ·")
          and "/bin/cat '%s'" % register in listed and lifecycle not in listed.split("count:")[0],
          "the register-slice log's list: %d %r" % (code, listed[:500]))
    world.set_audits([(s, "2026-10-11", 0) for s in ("register", "skill:alpha", "skill:beta",
                                                     "hooks-and-monitors", "tools")]
                     + [("standing-rules", "2026-10-04", 0)])
    code, out, _ = world.run()
    check(parse(out)["slice"] == "standing-rules", "the fixture picked %s" % parse(out)["slice"])
    check(printed_sources(out) == [register, lifecycle, log_md], "an ordinary slice's sources %r"
          % printed_sources(out))
    check("order check:" not in out, "the retired order check line survives")
    table = audit_table()
    check("In a week whose rotating part is the register, reading the register is slice reading."
          in table.get("independent", ""), "the table's register-as-slice rule: %r" % table)


def case_required_root_unreadable_refuses(world):
    """F2: a required root that cannot be read or is missing is a broken premise: PROBE FAILED,
    exit 2, no slice printed and no manifest written; a record refuses the same way and leaves
    slices.json as it was. The review's fixture: an unreadable hooks root."""
    good, _ = world.pick()
    report = world.report()
    before = digest(world.state)
    manifest = os.path.join(world.out, "refused.json")
    legs = []
    if os.geteuid() != 0:
        legs.append(("the hooks root unreadable", world.hooks, None))
    legs += [("CUSTOMISATION.md missing", world.path("vault/CUSTOMISATION.md"), "away"),
             ("wiki/developments missing", world.path("vault/wiki/developments"), "away")]
    for name, path, how in legs:
        moved = path + ".away"
        if how is None:
            os.chmod(path, 0)
        else:
            os.rename(path, moved)
        try:
            pick = world.run("--manifest-out", manifest)
            record = world.run("--record", "standing-rules", "--findings", "0", "--manifest", good,
                               "--report", report)
        finally:
            if how is None:
                os.chmod(path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH
                         | stat.S_IXOTH)
            else:
                os.rename(moved, path)
        for verb, (code, out, _) in (("pick", pick), ("record", record)):
            check(code == 2 and out.startswith("PROBE FAILED: the required root %s" % path)
                  and "READING LIST" not in out and "RECORDED" not in out,
                  "%s, the %s: %d %s" % (name, verb, code, out[:300]))
        check(not os.path.lexists(manifest), "%s: a manifest was written" % name)
        check(digest(world.state) == before, "%s: the record changed slices.json" % name)
    check(len(legs) >= 2, "no leg ran")


def case_unreadable_file_incomplete(world):
    """F2: a file the scan cannot read makes the pick incomplete: exit 3, never 0; the changed
    files read UNKNOWN, never none; INCOMPLETE names the hash scan that failed and the file; the
    manifest says complete: false and lists it as unread. A dangling link is unreadable to every
    user, a file of mode 000 to any but root. The control: once the files read again, the same
    pick is complete, exit 0."""
    world.record("standing-rules")
    dangling = world.path("vault/.claude/skills/beta/dangling.py")
    os.symlink(world.path("vault/.claude/skills/beta/nowhere.py"), dangling)
    guard = os.path.join(world.hooks, "guard.py")
    expected = ["vault/.claude/skills/beta/dangling.py"]
    locked = os.geteuid() != 0
    if locked:
        os.chmod(guard, 0)
        expected.insert(0, "hooks/guard.py")
    manifest = world.manifest_path()
    try:
        code, out, _ = world.run("--manifest-out", manifest)
    finally:
        if locked:
            os.chmod(guard, stat.S_IRUSR | stat.S_IWUSR)
    result = parse(out)
    check(code == 3, "exit %d, 3 expected (never 0): %s" % (code, result["summary"]))
    check("CHANGED FILES since the baseline of 2026-10-11: UNKNOWN" in out
          and "changed UNKNOWN (%d path(s) unread" % len(expected) in result["summary"],
          "the changed files did not read UNKNOWN: %s" % result["summary"])
    check(any(line.startswith("hash scan: vault/.claude: failed: ") and dangling in line
              for line in result["incomplete"])
          and (not locked or any(line.startswith("hash scan: hooks: failed: ") and guard in line
                                 for line in result["incomplete"])),
          "the INCOMPLETE block %r" % result["incomplete"])
    check("0 removed among the rest" in result["summary"], "an unread file was read as removed")
    data = load(manifest)
    check(data["complete"] is False and data["unread"] == sorted(expected)
          and not any(key in data["hashes"] for key in expected),
          "the manifest: complete %r, unread %r" % (data["complete"], data["unread"]))
    os.remove(dangling)
    code, out, _ = world.run("--manifest-out", manifest)
    data = load(manifest)
    check(code == 0 and data["complete"] is True and data["unread"] == []
          and "acquisitions all ok" in parse(out)["summary"],
          "the control: %d %s" % (code, out[-300:]))


def case_text_group_unreadable_incomplete(world):
    """F2: a standing-text group whose sections cannot be read (CUSTOMISATION.md not UTF-8), come
    out empty (no top-level section), or cannot be decided (D18: a section markdown-it reads
    inside a fenced block never closed or an HTML comment never closed, where a reader stopping
    there would find only the sections above it) fails the inventory: exit 3, the missing rows read
    UNKNOWN rather than none, and the manifest lists the file as unread. The control: with its
    sections readable the same pick is complete, with no missing row."""
    for text in (b"# Prefs\n\n## Settings\n\xff\xfe style\n", b"# Prefs\n\nno section here\n",
                 b"# Prefs\n\n## Settings\nstyle: x\n```text\n\n## Roles\nr\n",
                 b"# Prefs\n\n## Settings\nstyle: x\n<!--\n\n## Roles\nr\n"):
        with open(world.path("vault/CUSTOMISATION.md"), "wb") as handle:
            handle.write(text)
        manifest = world.manifest_path()
        code, out, _ = world.run("--manifest-out", manifest)
        result = parse(out)
        check(code == 3, "%r: exit %d, 3 expected: %s" % (text[-20:], code, result["summary"]))
        check("MISSING ROWS: UNKNOWN" in out and "MISSING ROWS (" not in out
              and "missing rows UNKNOWN" in result["summary"],
              "%r: the missing rows did not read UNKNOWN: %s" % (text[-20:], result["summary"]))
        check(any(line.startswith("inventory: failed: ") and "CUSTOMISATION.md" in line
                  for line in result["incomplete"]),
              "%r: the INCOMPLETE block %r" % (text[-20:], result["incomplete"]))
        data = load(manifest)
        check(data["complete"] is False and data["unread"] == ["vault/CUSTOMISATION.md"],
              "%r: the manifest's complete %r, unread %r" % (text[-20:], data["complete"],
                                                            data["unread"]))
    world.write("vault/CUSTOMISATION.md", "# Prefs\n\n## Settings\nstyle: x\n\n## Roles\nr\n")
    code, out, _ = world.run()
    check(code == 0 and "MISSING ROWS (0 " in out and "acquisitions all ok" in parse(out)["summary"],
          "the control: %d %s" % (code, parse(out)["summary"]))


def case_undecodable_name_unread(world):
    """The third build review's sweep: a file or folder name that is not valid UTF-8 comes back
    from a listing with its bad bytes escaped as lone surrogates (PEP 383), so a lenient walk would
    hash and list the file under that escaped name. The folder holding it is unread instead: each
    walk of it fails, the pick is incomplete (exit 3), the manifest's unread holds the folder, no
    key holds a lone surrogate, and nothing printed does. The name is planted in the listings, in
    this process, since this platform's file system refuses such names: once in a skill folder's
    walk, once in the skills folder's listing, which fails the rotation's listing. The control:
    without the plant the same pick is complete."""
    world.record("standing-rules")
    alpha, skills = world.path("vault/.claude/skills/alpha"), world.path("vault/.claude/skills")
    planted = os.fsdecode(b"bad\xffname.py")
    check(any(0xdc80 <= ord(c) <= 0xdcff for c in planted), "the plant holds no escaped byte")
    real_walk, real_listdir = os.walk, os.listdir

    def walk(top, *args, **kwargs):
        for dirpath, dirnames, filenames in real_walk(top, *args, **kwargs):
            yield dirpath, dirnames, filenames + ([planted] if dirpath == alpha else [])

    def listdir(path="."):
        return real_listdir(path) + ([planted] if path == skills else [])

    for name, patch, expected, acquisition in (
            ("a name in a skill folder", ("walk", walk), "vault/.claude/skills/alpha/",
             "hash scan: vault/.claude"),
            ("a name in the skills folder", ("listdir", listdir), "vault/.claude/skills/",
             "rotation")):
        manifest = world.manifest_path()
        setattr(os, patch[0], patch[1])
        try:
            code, out = world.in_process("--manifest-out", manifest)
        finally:
            os.walk, os.listdir = real_walk, real_listdir
        data = load(manifest)
        keys = list(data["hashes"]) + data["unread"]
        check(code == 3 and data["complete"] is False and expected in data["unread"]
              and status_of(data, acquisition) == "failed"
              and all(not any(0xd800 <= ord(c) <= 0xdfff for c in k) for k in keys)
              and not any(0xd800 <= ord(c) <= 0xdfff for c in out)
              and any("not valid UTF-8" in line for line in parse(out)["incomplete"]),
              "%s: exit %d, unread %r: %s" % (name, code, data["unread"], out[-600:]))
    code, out = world.in_process()
    check(code == 0 and "acquisitions all ok" in parse(out)["summary"],
          "the control: %d %s" % (code, parse(out)["summary"]))


def case_errors_never_read_as_absent(world):
    """The third build review's sweep: a walk or a look that meets an error never reads it as
    nothing there. A symbolic link to a folder below a root, which no walk follows, is unread
    (the pick incomplete, the link's folder key in the manifest's unread), never silently skipped;
    for any user but root, a skill folder whose SKILL.md cannot be looked at fails the rotation's
    listing, where os.path.isfile would have dropped the skill, and a due row naming a file that
    cannot be looked at fails the due rows' files, where it would have read "not found on disk".
    The controls: with each mended, the same pick is complete, the due row's file listed."""
    world.record("standing-rules")
    target = world.path("linked-target")
    os.makedirs(target)
    world.write("linked-target/hidden.md", "# below a link\n")
    link = world.path("vault/.claude/skills/alpha/linked")
    os.symlink(target, link)
    manifest = world.manifest_path()
    code, out, _ = world.run("--manifest-out", manifest)
    data = load(manifest)
    check(code == 3 and "vault/.claude/skills/alpha/linked/" in data["unread"]
          and status_of(data, "hash scan: vault/.claude") == "failed"
          and any("a symbolic link to a folder" in line for line in parse(out)["incomplete"]),
          "the symbolic link: exit %d, unread %r" % (code, data["unread"]))
    os.remove(link)
    code, out, _ = world.run()
    check(code == 0 and "acquisitions all ok" in parse(out)["summary"],
          "the link removed: %d %s" % (code, parse(out)["summary"]))
    if os.geteuid() == 0:
        return   # mode 000 does not stop root: the two legs below need another user
    beta = world.path("vault/.claude/skills/beta")
    os.chmod(beta, 0)
    manifest = world.manifest_path()
    try:
        code, out, _ = world.run("--manifest-out", manifest)
    finally:
        os.chmod(beta, stat.S_IRWXU)
    data = load(manifest)
    check(code == 3 and status_of(data, "rotation") == "failed"
          and any(line.startswith("rotation: failed: ") and "SKILL.md" in line
                  for line in parse(out)["incomplete"]),
          "the unreadable skill folder: exit %d, %r" % (code, parse(out)["incomplete"]))
    external = world.path("external")
    os.makedirs(external)
    check_path = world.write("external/check.sh", "echo check\n")
    rows = world.every_item_row() + [row(check_path, next_review="2026-10-01")]
    world.lifecycle(rows)
    os.chmod(external, 0)
    manifest = world.manifest_path()
    try:
        code, out, _ = world.run("--manifest-out", manifest)
    finally:
        os.chmod(external, stat.S_IRWXU)
    data = load(manifest)
    check(code == 3 and status_of(data, "due rows' files") == "failed"
          and any("could not be looked at" in why for why in parse(out)["why"]),
          "the due row's file that cannot be looked at: exit %d, %r" % (code, parse(out)["why"]))
    code, out, _ = world.run()
    check(code == 0 and [os.path.realpath(p) for p in parse(out)["parts"].get("due", [])]
          == [os.path.realpath(check_path)],
          "the control: %d %r" % (code, parse(out)["parts"].get("due")))


def case_line_breaks_are_newlines(world):
    """The third build review's sweep: lines are split at newlines only. A form feed and a Unicode
    line separator inside a lifecycle row's cell, which str.splitlines would take for line breaks
    (tearing the row, ending its table there and losing the row's due date), leave the row whole,
    due and listed; a form feed on the first line of wiki/log.md leaves deep-lint's entry at the
    line numbers an editor shows (11 to 14)."""
    rows = due_row_world(world)
    rows[-1] = rows[-1].replace("| keeps x |", "| keeps\x0cx y |")
    check(" " in rows[-1], "the plant did not take")
    world.lifecycle(rows)
    with open(world.path("vault/wiki/log.md"), encoding="utf-8") as handle:
        text = handle.read()
    world.write("vault/wiki/log.md", text.replace("# Log\n", "# Log \x0c page one\n", 1))
    code, out, _ = world.run()
    result = parse(out)
    check(code == 0 and has(result["parts"].get("due", []), ".claude/hooks/gate.py")
          and any(d.startswith(".claude/hooks/gate.py |") for d in result["due"])
          and DEEPLINT_LINES in out,
          "exit %d, due %r: %s" % (code, result["parts"].get("due"), out[-600:]))


def case_record_keeps_unread_hash(world):
    """F2: --record with an incomplete manifest records the audit's date, slice and findings, but
    never advances the baseline over what its pick could not read: an unread file keeps its earlier
    hash and an unread file with none stays absent, and the record prints each. At the next pick
    the unread file, unchanged, is not listed as changed but is owed, the new one is listed as
    new, and a later change to the unread file is listed."""
    world.record("standing-rules")
    old = world.state_data()["baseline"]["hashes"]["hooks/guard.py"]
    files = (("hooks/guard.py", "print('guard')\n"), ("hooks/fresh.py", "print('fresh')\n"))
    world.write(*files[1])
    as_root = os.geteuid() == 0   # mode 000 does not stop root: a dangling link stands in
    for rel, _ in files:
        if as_root:
            os.unlink(world.path(rel))
            os.symlink(world.path(rel) + ".nowhere", world.path(rel))
        else:
            os.chmod(world.path(rel), 0)
    manifest = world.manifest_path()
    try:
        code, out, _ = world.run("--manifest-out", manifest)
    finally:
        for rel, text in files:
            if as_root:
                os.unlink(world.path(rel))
                world.write(rel, text)
            else:
                os.chmod(world.path(rel), stat.S_IRUSR | stat.S_IWUSR)
    check(code == 3 and os.path.isfile(manifest), "the pick: %d %s" % (code, out[-300:]))
    code, out, _ = world.run("--record", "skill:alpha", "--findings", "2", "--manifest", manifest,
                             "--report", world.report())
    check(code == 0 and out.startswith("RECORDED: %s · slice skill:alpha · findings 2" % TODAY),
          "the record: %d %s" % (code, out[:300]))
    data = world.state_data()
    check(dict((k, data["audits"][-1][k]) for k in ("date", "slice", "findings"))
          == {"date": TODAY, "slice": "skill:alpha", "findings": 2}, "the audit %r"
          % data["audits"][-1])
    hashes = data["baseline"]["hashes"]
    check(hashes.get("hooks/guard.py") == old, "the unread file's earlier hash was not kept: %r"
          % hashes.get("hooks/guard.py"))
    check("hooks/fresh.py" not in hashes, "an unread file with no earlier hash entered the baseline")
    check("kept: hooks/guard.py (its hash from the baseline of 2026-10-11)" in out
          and "absent: hooks/fresh.py" in out, "the record did not print what it kept: %s" % out)
    result = parse(world.run(today="2026-10-25")[1])
    changed = result["parts"].get("changed", [])
    check(not has(changed, "hooks/guard.py") and has(changed, "hooks/fresh.py"),
          "the next pick, before any change: %r" % changed)
    check(has(result["parts"].get("owed", []), "hooks/guard.py"),
          "R5: the unread file, back unchanged, lost its owed reading: %r"
          % result["parts"].get("owed"))
    world.write("hooks/guard.py", "print('guard, changed after the audit')\n")
    result = parse(world.run(today="2026-10-25")[1])
    check(has(result["parts"].get("changed", []), "hooks/guard.py"),
          "a later change to the unread file was not listed: %r" % result["parts"].get("changed"))


def case_root_gone_before_hashes(world):
    """R5: a required root there when the pick began and gone when the hash scan reads it (the
    hooks folder, moved away for that acquisition alone) makes the pick incomplete, exit 3: the
    changed files read UNKNOWN, INCOMPLETE names the hooks' hash scan, and the manifest says
    complete false with hooks/ unread. Restored before the record, the root cannot erase the
    failure: the record stores an incomplete audit, keeps the hooks' earlier hashes and owes
    hooks/, and the next pick lists the hooks' files under "owed from an earlier audit" though
    none changed. The control: the same pick with nothing gone is complete."""
    world.record("standing-rules")
    before = hooks_hashes(world)
    check(len(before) == 3, "the fixture's hooks hashes: %r" % sorted(before))
    code, out, _ = world.run()
    check(code == 0 and "acquisitions all ok" in parse(out)["summary"], "the control: %d %s"
          % (code, parse(out)["summary"]))
    manifest = world.manifest_path()
    code, out = world.inject("hash_roots", world.hooks, "--manifest-out", manifest)
    result = parse(out)
    check(code == 3, "exit %d, 3 expected (never 0): %s" % (code, result["summary"]))
    check("CHANGED FILES since the baseline of 2026-10-11: UNKNOWN" in out
          and "changed UNKNOWN" in result["summary"], "the changed files: %s" % result["summary"])
    check(any(line.startswith("hash scan: hooks: failed: ") and "missing at the hash scan" in line
              and "the changed files" in line for line in result["incomplete"]),
          "the INCOMPLETE block %r" % result["incomplete"])
    data = load(manifest)
    check(data["complete"] is False and data["unread"] == ["hooks/"]
          and not any(k.startswith("hooks/") for k in data["hashes"]),
          "the manifest: complete %r, unread %r" % (data["complete"], data["unread"]))
    slice_name = result["slice"]
    code, out, _ = world.run("--record", slice_name, "--findings", "1", "--manifest", manifest,
                             "--report", world.report())
    check(code == 0 and "· INCOMPLETE ·" in out.splitlines()[0]
          and "kept: hooks/ (3 earlier hash(es) below it kept)" in out
          and "INCOMPLETE AUDIT" in out and "owed: hooks/ (since %s)" % TODAY in out,
          "the record after the root came back: %d %s" % (code, out))
    data = world.state_data()
    check(data["audits"][-1]["complete"] is False and hooks_hashes(world) == before
          and data["owed"] == [{"entry": "hooks/", "since": TODAY}],
          "the stored audit, the hooks' hashes or the owed list: %r %r"
          % (data["audits"][-1], data["owed"]))
    result = parse(world.run(today="2026-10-25")[1])
    owed = result["parts"].get("owed", [])
    check(sorted(os.path.basename(p) for p in owed) == ["data.jsonl", "guard.py", "test_guard.sh"]
          and result["parts"].get("changed") == [],
          "the next pick: owed %r, changed %r" % (owed, result["parts"].get("changed")))
    check(result["owed"] == ["hooks/ (owed since %s): 3 file(s) on the reading list" % TODAY],
          "the OWED block %r" % result["owed"])


def case_root_gone_before_rotation(world):
    """R5: the hooks root gone while the rotation lists its slices, and back for every other
    acquisition: the rotation's choice and files read UNKNOWN, exit 3, with a `rotation: UNKNOWN`
    line and INCOMPLETE naming the rotation, and the manifest says complete false; the rotating
    part lacks the hooks' files. The control: the same rotation read whole holds them and is
    complete."""
    world.record("standing-rules")
    world.set_audits([(s, "2026-10-11", 0) for s in ("standing-rules", "skill:alpha",
                                                     "skill:beta", "register", "tools")])
    code, out, _ = world.run()
    result = parse(out)
    check(code == 0 and result["slice"] == "hooks-and-monitors"
          and has(result["parts"].get("rotating", []), "hooks/guard.py"),
          "the control: %d %s %r" % (code, result["slice"], result["parts"].get("rotating")))
    manifest = world.manifest_path()
    code, out = world.inject("rotation", world.hooks, "--manifest-out", manifest)
    result = parse(out)
    check(code == 3 and "rotation: UNKNOWN" in out, "exit %d: %s" % (code, out[:400]))
    check(any(line.startswith("rotation: failed: ") and "at the rotation listing" in line
              and "the rotation (the slice chosen and its files)" in line
              for line in result["incomplete"]), "the INCOMPLETE block %r" % result["incomplete"])
    check(not has(result["parts"].get("rotating", []), "hooks/guard.py"),
          "the rotating part read the gone root: %r" % result["parts"].get("rotating"))
    data = load(manifest)
    check(data["complete"] is False and data["unread"] == ["hooks/"],
          "the manifest: %r %r" % (data["complete"], data["unread"]))


def case_root_gone_before_inventory(world):
    """R5: the hooks root gone while the inventory reads it: the missing rows read UNKNOWN, never
    none, exit 3, INCOMPLETE naming the inventory; the changed files, read before it, stay known.
    The control: with the hooks there, the same pick lists 0 missing rows and is complete."""
    world.record("standing-rules")
    code, out, _ = world.run()
    check(code == 0 and "MISSING ROWS (0 " in out, "the control: %d %s" % (code, out[-300:]))
    code, out = world.inject("inventory", world.hooks)
    result = parse(out)
    check(code == 3 and "MISSING ROWS: UNKNOWN" in out and "MISSING ROWS (" not in out
          and "missing rows UNKNOWN" in result["summary"],
          "the missing rows: %d %s" % (code, result["summary"]))
    check(any(line.startswith("inventory: failed: ") and "at the inventory" in line
              and "the missing rows" in line for line in result["incomplete"]),
          "the INCOMPLETE block %r" % result["incomplete"])
    check("CHANGED FILES since the baseline of 2026-10-11: 0 changed, 0 new, 0 removed" in out,
          "the changed files, read before the inventory, did not stay known")


def case_root_removed_between_check_and_walk(world):
    """T5, the third build review's second finding: the hooks root there when the pick began
    (the premises read it) and moved away inside each acquisition that walks it, after every
    check and immediately before that acquisition's own walk, then restored, is recorded by the
    walk itself: the hash scan, the rotation listing and the inventory each fail, the manifest
    and the record read incomplete, and hooks/ is owed. The control (the empty-root case below
    covers the readable empty root): with nothing moved the pick is complete."""
    world.record("standing-rules")
    saved = world.state_data()
    for number, acquisition in enumerate(("hash scan: hooks", "rotation", "inventory")):
        world.set_state(saved)
        today = "2026-10-%d" % (19 + number)
        manifest = world.manifest_path()
        code, out = world.inject_walk(acquisition, world.hooks, "--manifest-out", manifest,
                                      today=today)
        data = load(manifest)
        check(code == 3 and data["complete"] is False and status_of(data, acquisition) == "failed"
              and "hooks/" in data["unread"],
              "%s: %d complete %r unread %r" % (acquisition, code, data["complete"],
                                                data["unread"]))
        check(any(line.startswith("%s: failed: " % acquisition) and "it is missing at" in line
                  for line in parse(out)["incomplete"]), "%s: the INCOMPLETE block %r"
              % (acquisition, parse(out)["incomplete"]))
        out = world.record(data["slice"], today=today, manifest=manifest)
        stored = world.state_data()
        check(stored["audits"][-1]["complete"] is False and "INCOMPLETE AUDIT" in out
              and {"entry": "hooks/", "since": today} in stored["owed"],
              "%s: the record %r %r" % (acquisition, stored["audits"][-1], stored["owed"]))
    world.set_state(saved)
    code, out, _ = world.run(today="2026-10-25")
    check(code == 0 and "acquisitions all ok" in parse(out)["summary"],
          "the control: %d %s" % (code, parse(out)["summary"]))


def case_empty_folder_and_optional_root(world):
    """R5's controls: a readable empty required folder (the hooks root, emptied) is read, never
    unread, and the absent optional root (CUSTOMISATION-definitions.md) is never a failure: both
    picks are complete, exit 0, with no INCOMPLETE block."""
    for name in os.listdir(world.hooks):
        os.remove(os.path.join(world.hooks, name))
    check(os.listdir(world.hooks) == [], "the hooks root is not empty")
    code, out, _ = world.run()
    result = parse(out)
    check(code == 0 and "acquisitions all ok" in result["summary"] and not result["incomplete"]
          and "INCOMPLETE" not in out, "an empty readable folder: %d %s" % (code, out[-400:]))
    os.remove(world.path("vault/CUSTOMISATION-definitions.md"))
    code, out, _ = world.run()
    result = parse(out)
    check(code == 0 and "1 optional root(s) absent" in result["controls"]
          and "acquisitions all ok" in result["summary"] and "INCOMPLETE" not in out,
          "the absent optional root: %d %s" % (code, out[-400:]))


def case_every_acquisition_fails_closed(world):
    """T5: every registered acquisition, one at a time, failing, returning unknown and never
    reporting (each planted in this process), leaves the manifest incomplete, with that
    acquisition's outcome named, and the record of that audit incomplete; the lifecycle rows short
    lend no row to the due part. The control: every acquisition succeeding, with one due lifecycle
    row, completes and lists the row's file."""
    due_row_world(world)
    saved = world.state_data()
    manifest = world.manifest_path()
    code, out, _ = world.run("--manifest-out", manifest)
    control = load(manifest)
    check(code == 0 and control["complete"] is True
          and has(parse(out)["parts"].get("due", []), ".claude/hooks/gate.py"),
          "the control with one due row: %d %r" % (code, control["complete"]))
    names = [a["name"] for a in control["acquisitions"]]
    for expected in ("premises", "slices.json", "hash scan: vault/.claude", "hash scan: hooks",
                     "hash scan: vault/CUSTOMISATION-definitions.md", "owed content", "rotation",
                     "lifecycle rows", "inventory", "due rows' files",
                     "comparison source: the register", "comparison source: deep-lint",
                     "requirement files"):
        check(expected in names, "the registry lacks %r: %r" % (expected, names))
    check(len(names) == 17, "%d acquisitions registered, 17 expected (2 premises and state, 7 "
          "roots, 8 more, the requirement files' among them: CR-AUDIT11 F2): %r"
          % (len(names), names))
    day = datetime.date(2026, 10, 18)
    for name in names:
        for mode, status in (("failed", "failed"), ("unknown", "unknown"),
                             ("never", "never reported")):
            world.set_state(saved)
            day += datetime.timedelta(days=1)
            manifest = world.manifest_path()
            code, out = world.in_process("--manifest-out", manifest, today=day.isoformat(),
                                         patch=plant_outcome(name, mode))
            data = load(manifest)
            check(code == 3 and data["complete"] is False and status_of(data, name) == status
                  and sum(1 for a in data["acquisitions"] if a["status"] != "ok") == 1,
                  "%s %s: exit %d, complete %r, outcomes %r" % (
                      name, mode, code, data["complete"],
                      [(a["name"], a["status"]) for a in data["acquisitions"]
                       if a["status"] != "ok"]))
            check(any(line.startswith("%s: %s: " % (name, status)) for line in
                      parse(out)["incomplete"]), "%s %s: the INCOMPLETE block %r"
                  % (name, mode, parse(out)["incomplete"]))
            # an acquisition that did not succeed lends no part of its result: the lifecycle
            # rows short, the due row's file is not listed though the page itself read whole
            check(name != "lifecycle rows" or parse(out)["parts"].get("due") == [],
                  "%s %s: the due part used rows of a short acquisition: %r"
                  % (name, mode, parse(out)["parts"].get("due")))
            out = world.record(data["slice"], today=day.isoformat(), manifest=manifest)
            check(world.state_data()["audits"][-1]["complete"] is False
                  and "INCOMPLETE AUDIT" in out and "INCOMPLETE MANIFEST" in out,
                  "%s %s: the record read complete: %s" % (name, mode, out[:400]))


# the record's own acquisitions made before it writes, in the order it makes them
RECORDER = ("premises", "slices.json", "manifest", "coverage")


def case_recorder_acquisitions_fail_closed(world):
    """T5, item 6 (the third build review's first finding): each of the record's own acquisitions
    made before it writes (the premises, slices.json, the manifest and the reviewer's coverage),
    failing, returning unknown and never reporting in turn (each planted in this process), makes
    the record incomplete, its reason stored with the audit and printed, and moves nothing the
    record cannot vouch for: with the coverage short, every reading-list file counts as not read
    (each owed, its earlier hash kept, the owed entry it lists not discharged); with any other one
    short, the baseline stays as it was and no owed entry is discharged. The control, the same
    record with every acquisition succeeding, is complete with no reason, discharges the listed
    owed entry and advances the baseline. A read-back of the new state that fails, returns unknown
    or never reports is refused before the commit, exit 2, slices.json byte for byte unchanged (the
    case commit_after_read_back plants real failed opens too); a diagnostic rescan after the commit
    that returns unknown or never reports is said (UNKNOWN in part), never read as nothing changed
    since the pick."""
    world.record("standing-rules")
    restore = unreadable(world, "hooks/guard.py")
    manifest = world.manifest_path()
    try:
        code, out, _ = world.run("--manifest-out", manifest, today="2026-10-12")
    finally:
        restore()
    world.record(parse(out)["slice"], today="2026-10-12", manifest=manifest)
    design = world.path("vault/wiki/developments/design.md")
    key = "vault/wiki/developments/design.md"
    old = world.state_data()["baseline"]["hashes"][key]
    world.write("vault/wiki/developments/design.md", "# Design\n\nchanged this week\n")
    manifest, out = world.pick(today="2026-10-13")
    data = load(manifest)
    guard = world.path("hooks/guard.py")
    check(data["complete"] is True and guard in data["reading"] and design in data["reading"]
          and world.state_data()["owed"] == [{"entry": "hooks/guard.py", "since": "2026-10-12"}],
          "the fixture: %r %r" % (data["complete"], world.state_data()["owed"]))
    saved = world.state_data()
    record = ("--record", data["slice"], "--findings", "0", "--manifest", manifest)
    for name in RECORDER:
        for mode, status in (("failed", "failed"), ("unknown", "unknown"),
                             ("never", "never reported")):
            world.set_state(saved)
            code, out = world.in_process(*(record + ("--report", world.report())),
                                         today="2026-10-13", patch=plant_outcome(name, mode))
            stored = world.state_data()
            audit = stored["audits"][-1]
            check(code == 0 and audit["complete"] is False and len(audit["reasons"]) == 1
                  and audit["reasons"][0].startswith("the record's own acquisition %s did not "
                                                     "succeed (%s: " % (name, status))
                  and "· INCOMPLETE ·" in out.splitlines()[0] and "INCOMPLETE AUDIT" in out
                  and "RECORD INCOMPLETE: its own acquisition %s did not succeed: %s"
                  % (name, status) in out,
                  "%s %s: exit %d, the audit %r: %s" % (name, mode, code, audit, out[:600]))
            owed = [e["entry"] for e in stored["owed"]]
            if name == "coverage":
                check("hooks/guard.py" in owed and key in owed
                      and stored["baseline"]["hashes"][key] == old
                      and "owed: discharged" not in out and "coverage: UNKNOWN" in out,
                      "%s %s: the coverage short: owed %r, hash %s" % (
                          name, mode, owed, stored["baseline"]["hashes"][key][:12]))
            else:
                check(stored["baseline"] == saved["baseline"] and owed == ["hooks/guard.py"]
                      and "owed: discharged" not in out and "BASELINE KEPT whole" in out,
                      "%s %s: the record moved what it cannot vouch for: owed %r, %s"
                      % (name, mode, owed, out[:600]))
    world.set_state(saved)
    code, out = world.in_process(*(record + ("--report", world.report())), today="2026-10-13")
    stored = world.state_data()
    check(code == 0 and stored["audits"][-1]["complete"] is True
          and stored["audits"][-1]["reasons"] == [] and stored["owed"] == []
          and stored["baseline"]["hashes"][key] == digest(design)
          and "owed: discharged 1 entry, listed by this audit's pick and read: hooks/guard.py"
          in out, "the control: %d %r %s" % (code, stored["audits"][-1], out[:600]))
    for mode in ("failed", "unknown", "never"):
        # revision 6: the read-back comes before the commit, so it refuses with nothing replaced
        world.set_state(saved)
        before = digest(world.state)
        code, out = world.in_process(*(record + ("--report", world.report())),
                                     today="2026-10-13",
                                     patch=plant_outcome("slices.json read back", mode))
        check(code == 2 and out.startswith("REFUSED: the new state, written to a temporary file "
                                           "beside slices.json, did not read back as written")
              and out.rstrip().endswith("slices.json unchanged") and digest(world.state) == before
              and not [n for n in os.listdir(os.path.dirname(world.state)) if n.endswith(".tmp")],
              "the read-back %s: %d %s" % (mode, code, out[:300]))
    # the diagnostic rescan after the write: one that does not succeed is said, never read as
    # nothing changed since the pick
    for mode, status in (("unknown", "unknown"), ("never", "never reported")):
        world.set_state(saved)
        code, out = world.in_process(*(record + ("--report", world.report())),
                                     today="2026-10-13", patch=plant_outcome("rescan: hooks", mode))
        check(code == 0 and "UNKNOWN in part (1 rescan(s) did not succeed" in out
              and "rescan did not succeed (not compared): rescan: hooks: %s" % status in out,
              "the rescan %s: %d %s" % (mode, code, out[-500:]))


def case_lifecycle_failures_incomplete(world):
    """T5, the second design check's first finding: the lifecycle page missing, unreadable (not
    UTF-8, and of mode 000 for any user but root) or without its table leaves the due and missing
    rows UNKNOWN, the manifest incomplete and the record incomplete, never "nothing due"; after
    each, the next successful pick restores the due-row selection. The control: the readable page
    with one due row completes."""
    rows = due_row_world(world)
    page = world.path("vault/wiki/developments/check-lifecycle.md")
    away = os.path.join(world.root, "lifecycle-away.md")   # outside every hashed root
    code, out, _ = world.run()
    check(code == 0 and has(parse(out)["parts"].get("due", []), ".claude/hooks/gate.py"),
          "the control: %d %r" % (code, parse(out)["parts"].get("due")))

    def not_utf8():
        with open(page, "ab") as handle:
            handle.write(b"\xff\xfe\n")

    legs = [("missing", lambda: os.rename(page, away), lambda: os.rename(away, page), "failed"),
            ("not UTF-8", not_utf8, lambda: world.lifecycle(rows), "failed"),
            ("without its table", lambda: world.lifecycle(rows, header=HEADER.replace("| Guards ",
                                                                                     "")),
             lambda: world.lifecycle(rows), "unknown")]
    if os.geteuid() != 0:
        legs.append(("of mode 000", lambda: os.chmod(page, 0),
                     lambda: os.chmod(page, stat.S_IRUSR | stat.S_IWUSR), "failed"))
    for number, (name, spoil, mend, status) in enumerate(legs):
        today = "2026-10-%d" % (19 + 2 * number)
        spoil()
        try:
            manifest = world.manifest_path()
            code, out, _ = world.run("--manifest-out", manifest, today=today)
        finally:
            mend()
        data = load(manifest)
        check(code == 3 and "DUE ROWS: UNKNOWN" in out and "MISSING ROWS: UNKNOWN" in out
              and "DUE ROWS (" not in out and data["complete"] is False
              and status_of(data, "lifecycle rows") == status,
              "%s: exit %d, complete %r: %s" % (name, code, data["complete"], out[-500:]))
        out = world.record(data["slice"], today=today, manifest=manifest)
        check(world.state_data()["audits"][-1]["complete"] is False and "INCOMPLETE AUDIT" in out,
              "%s: the record read complete" % name)
        code, out, _ = world.run(today="2026-10-%d" % (20 + 2 * number))
        check(code == 0 and has(parse(out)["parts"].get("due", []), ".claude/hooks/gate.py"),
              "%s: the next successful pick did not restore the due row: %d %r"
              % (name, code, parse(out)["parts"].get("due")))


def case_damaged_table_unknown(world):
    """T5, item 6 (the third build review's third finding): a lifecycle table counts only with its
    header, its separator row and a body that parses. A header alone (the review's plant: the
    header and a newline), a header among text, a broken separator, no separator, a torn row cut
    before its closing pipe, rows cut off from their table by a blank line, and (D18, the raw
    protocol) a damaged lifecycle header and a row inside a block quote each give UNKNOWN: due and
    missing rows UNKNOWN, the lifecycle rows' outcome unknown and named as a damaged table, the
    manifest and the record incomplete; the restored page then restores the due-row selection.
    The controls: the valid page with one due row completes and lists the row's file, and so does
    the same page ending on its table, with no heading after it (revision 7: a page structurally
    valid, never refused, which revision 6's heading rule called damaged), and the same page with a
    fenced block left open below the table (D18: raw lines, a fence is text; B-AUDIT10 called it
    damage, RETIRED_D18); a header and separator with no rows is a valid empty table, complete,
    with no due row and every inventory item missing, unlike a damaged one."""
    rows = due_row_world(world)
    front = "---\ntitle: Check lifecycle\n---\n\n# Check lifecycle\n\n"
    body = [HEADER, SEPARATOR] + rows
    page = "vault/wiki/developments/check-lifecycle.md"
    check(rows[-1].startswith("| .claude/hooks/gate.py |"), "the due row is not the last")
    tail = LIFECYCLE_TAIL   # each variant keeps the page's further section, so that its own
                            # damage is the only difference from the valid page
    variants = (("a header alone", front + HEADER + "\n" + tail),
                ("a header among text", front + HEADER + "\n\nNo table follows.\n" + tail),
                ("a broken separator", front + "\n".join([HEADER, "|---|---|"] + rows) + "\n"
                 + tail),
                ("no separator", front + "\n".join([HEADER] + rows) + "\n" + tail),
                ("a torn row", front + "\n".join(body[:-1] + [body[-1][:-5]]) + "\n" + tail),
                ("rows cut off by a blank line",
                 front + "\n".join(body[:5] + [""] + body[5:]) + "\n" + tail),
                # short rows cut off, which only the rows-in-no-table rule can catch (ten-cell
                # rows cut off read as a damaged lifecycle header too)
                ("short rows cut off by a blank line",
                 front + "\n".join(body + ["", row("short.sh", cells=9), row("shorter.sh", cells=9)])
                 + "\n" + tail),
                ("a damaged lifecycle header (one column renamed)",
                 front + "\n".join([HEADER.replace("| Guards ", "| Guarded ")] + body[1:]) + "\n"
                 + tail),
                ("a row inside a block quote", front + "\n".join(body) + "\n\n> " + body[-1] + "\n"
                 + tail))
    day = datetime.date(2026, 10, 18)
    code, out, _ = world.run()
    check(code == 0 and has(parse(out)["parts"].get("due", []), ".claude/hooks/gate.py"),
          "the control: %d %r" % (code, parse(out)["parts"].get("due")))
    for name, text in (("ending on its table", front + "\n".join(body) + "\n"),
                       ("with a fenced block left open below its table (raw lines: text)",
                        front + "\n".join(body) + "\n" + tail + "```text\nan example\n")):
        world.write(page, text)   # each valid, read whole
        code, out, _ = world.run()
        check(code == 0 and has(parse(out)["parts"].get("due", []), ".claude/hooks/gate.py")
              and "lifecycle rows parsed %d" % len(rows) in parse(out)["controls"],
              "the page %s: %d %r" % (name, code, parse(out)["parts"].get("due")))
    world.lifecycle(rows)
    for name, text in variants:
        day += datetime.timedelta(days=1)
        world.write(page, text)
        manifest = world.manifest_path()
        code, out, _ = world.run("--manifest-out", manifest, today=day.isoformat())
        data = load(manifest)
        check(code == 3 and "DUE ROWS: UNKNOWN" in out and "MISSING ROWS: UNKNOWN" in out
              and "DUE ROWS (" not in out and data["complete"] is False
              and status_of(data, "lifecycle rows") == "unknown"
              and not has(parse(out)["parts"].get("due", []), ".claude/hooks/gate.py")
              and any(line.startswith("lifecycle rows: unknown: ") and "damaged table" in line
                      for line in parse(out)["incomplete"]),
              "%s: exit %d, complete %r: %s" % (name, code, data["complete"], out[-700:]))
        out = world.record(data["slice"], today=day.isoformat(), manifest=manifest)
        check(world.state_data()["audits"][-1]["complete"] is False and "INCOMPLETE AUDIT" in out,
              "%s: the record read complete: %s" % (name, out[:300]))
        world.lifecycle(rows)
        day += datetime.timedelta(days=1)
        code, out, _ = world.run(today=day.isoformat())
        check(code == 0 and has(parse(out)["parts"].get("due", []), ".claude/hooks/gate.py"),
              "%s: the restored page did not restore the due row: %d %r"
              % (name, code, parse(out)["parts"].get("due")))
    world.lifecycle([])
    manifest = world.manifest_path()
    code, out, _ = world.run("--manifest-out", manifest, today=day.isoformat())
    result = parse(out)
    check(code == 0 and load(manifest)["complete"] is True and "DUE ROWS (0:" in out
          and "lifecycle rows parsed 0" in result["controls"]
          and len(result["missing"]) == int(re.search(r"inventory (\d+) \(",
                                                      result["controls"]).group(1)),
          "the valid empty table: %d %s" % (code, out[-700:]))


def case_comparison_sources_fail_closed(world):
    """T5, the third design check's first finding and the third, fourth and fifth build reviews'
    second and third: deep-lint's entry in wiki/log.md missing, unreadable, absent from the log,
    followed by undecodable bytes (a valid deep-lint heading surviving above them), a heading alone,
    one followed by an unclosed fenced fragment, one cut before its Conflicts field and one without
    its Changed field, and (revision 7, the fifth build review's F3) one whose fields are torn
    prefixes (the review's plant), look-alike names, or complete forms with no value, and (D18, the
    raw protocol) a malformed latest deep-lint heading, which never falls back to the older entry,
    and an entry whose fields stand after a malformed heading, never borrowed; and the register
    missing, unreadable, undecodable, without its sections, or (D18) with its `## Open` heading
    given twice by an example in a code block or its `## Closed` before its `## Open`: each makes
    the pick and the record incomplete and prints LABELS LIMITED, so that no finding can be
    labelled `new kind`; recovery restores the comparison input. The controls: both readable, the
    pick completes with the deep-lint entry located and no limit; a newer entry in the complete
    forms with a value, `none` among them, and a further field after its Conflicts (the live log's
    Meter field) is selected, complete, with no limit; and (D18) a register and a log each with a
    fenced block never closed are whole, raw lines reading no fence."""
    world.record("standing-rules")
    log_md, register = world.path("vault/wiki/log.md"), world.path(
        "vault/wiki/developments/known-issues.md")
    with open(log_md, encoding="utf-8") as handle:
        log_text = handle.read()
    with open(register, encoding="utf-8") as handle:
        register_text = handle.read()
    code, out, _ = world.run()
    check(code == 0 and "LABELS LIMITED" not in out and "the deep-lint entry of 2026-10-02" in out,
          "the control: %d %s" % (code, out[-500:]))
    # the complete forms, each with a value (`none` too), and a field after Conflicts: whole
    later = ("\n## [2026-10-13] deep-lint | later\n- **Changed**: e\n- **Clock**: 06:00 BST\n"
             "- **Conflicts**: none\n- **Meter**: billed (planted)\n")
    with open(log_md, "w", encoding="utf-8") as handle:
        handle.write(log_text + later)
    manifest = world.manifest_path()
    code, out, _ = world.run("--manifest-out", manifest, today="2026-10-18")
    check(code == 0 and "LABELS LIMITED" not in out and load(manifest)["complete"] is True
          and "log.md lines 20-24 (the deep-lint entry of 2026-10-13)" in out,
          "the complete forms with a field after Conflicts: %d %s" % (code, out[-600:]))
    # D18: raw lines read no fence, so a fence left open in either source is text, both whole
    for path, text in ((log_md, log_text + "\n```text\nan example\n"),
                       (register, register_text + "\n```text\nan example\n")):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        manifest = world.manifest_path()
        code, out, _ = world.run("--manifest-out", manifest, today="2026-10-18")
        check(code == 0 and "LABELS LIMITED" not in out and load(manifest)["complete"] is True
              and "the deep-lint entry of 2026-10-02" in out,
              "%s with a fence left open: %d %s" % (os.path.basename(path), code, out[-600:]))
    with open(log_md, "w", encoding="utf-8") as handle:
        handle.write(log_text)
    with open(register, "w", encoding="utf-8") as handle:
        handle.write(register_text)

    def as_folder(path):
        os.remove(path)
        os.mkdir(path)

    def restore(path, text):
        if os.path.isdir(path):
            os.rmdir(path)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def damage(path, text):
        with open(path, "wb") as handle:
            handle.write(text.encode("utf-8") + b"\xff\xfe damaged\n")

    def damage_inside(path, text):
        """Undecodable bytes inside the latest deep-lint entry's own Changed bullet, the entry
        otherwise whole: only strict decoding can fail it (replaced, the entry would read whole)."""
        data = text.encode("utf-8")
        check(data.count(b"- **Changed**: c\n") == 1, "the plant's anchor")
        with open(path, "wb") as handle:
            handle.write(data.replace(b"- **Changed**: c\n", b"- **Changed**: c \xff\xfe\n"))

    legs = (("deep-lint", "missing", lambda: os.remove(log_md), "failed"),
            ("deep-lint", "unreadable", lambda: as_folder(log_md), "failed"),
            ("deep-lint", "with no deep-lint entry", lambda: restore(log_md, "# Log\n\n## [2026-10-"
                                                                     "02] ingest | x\n"),
             "unknown"),
            ("deep-lint", "undecodable after a valid heading", lambda: damage(log_md, log_text),
             "failed"),
            ("deep-lint", "undecodable inside its whole latest entry",
             lambda: damage_inside(log_md, log_text), "failed"),
            ("the register", "missing", lambda: os.remove(register), "failed"),
            ("the register", "unreadable", lambda: as_folder(register), "failed"),
            ("the register", "without its sections", lambda: restore(register, "# Register\n"),
             "unknown"),
            ("the register", "undecodable", lambda: damage(register, register_text), "failed"),
            # D18, the raw protocol: an example quoting `## Open` in a code block is a second
            # heading, and a Closed before the Open is no register's shape
            ("the register", "with its `## Open` heading given twice (an example in a code block)",
             lambda: restore(register, register_text + "\n```text\n## Open\n- an example\n```\n"),
             "unknown"),
            ("the register", "with its `## Closed` before its `## Open`",
             lambda: restore(register, "# Register\n\n## Closed\n- old\n\n## Open\n- new\n"),
             "unknown"),
            # revision 6, the fourth build review's third finding, as revision 7 restates it: a
            # deep-lint entry counts only with its heading and its two complete fields
            ("deep-lint", "a heading alone (the review's plant)",
             lambda: restore(log_md, "## [2026-10-12] deep-lint |\n"), "failed"),
            ("deep-lint", "a heading followed by an unclosed fenced fragment (raw lines: no field)",
             lambda: restore(log_md, log_text + "\n## [2026-10-12] deep-lint | late\n```text\n"
                                                "partial\n"), "failed"),
            # D18: a malformed latest deep-lint heading fails, never falling back to the older
            # entry of 2026-10-02; fields after a malformed entry heading are never borrowed
            ("deep-lint", "a malformed latest heading (no `|`), no fallback to the older entry",
             lambda: restore(log_md, log_text + "\n## [2026-10-12] deep-lint\n- **Changed**: e\n"
                                                "- **Conflicts**: none\n"), "failed"),
            ("deep-lint", "a malformed latest heading (no space after `##`)",
             lambda: restore(log_md, log_text + "\n##[2026-10-12] deep-lint | late\n"
                                                "- **Changed**: e\n- **Conflicts**: none\n"),
             "failed"),
            ("deep-lint", "its fields after a malformed entry heading, never borrowed",
             lambda: restore(log_md, log_text + "\n## [2026-10-12] deep-lint | late\n"
                                                "- **Clock**: 06:00 BST\n##[2026-10-12] ingest | y\n"
                                                "- **Changed**: e\n- **Conflicts**: none\n"),
             "failed"),
            ("deep-lint", "an entry cut before its Conflicts bullet",
             lambda: restore(log_md, log_text + "\n## [2026-10-12] deep-lint | late\n"
                                                "- **Changed**: e\n- **Clock**: 06:00 BST\n"),
             "failed"),
            ("deep-lint", "an entry without its Changed bullet",
             lambda: restore(log_md, log_text + "\n## [2026-10-12] deep-lint | late\n"
                                                "- **Clock**: 06:00 BST\n- **Conflicts**: none\n"),
             "failed"),
            # revision 7, the fifth build review's third finding: each field in its complete form,
            # followed by a value; a torn prefix, a look-alike name or an empty field is none
            ("deep-lint", "torn field prefixes (the review's plant)",
             lambda: restore(log_md, log_text + "\n## [2026-10-13] deep-lint | x\n- **Changed\n"
                                                "- **Conflicts\n"), "failed"),
            ("deep-lint", "look-alike field names",
             lambda: restore(log_md, log_text + "\n## [2026-10-13] deep-lint | x\n"
                                                "- **Changed-not-the-field**: e\n"
                                                "- **Conflicts-not-the-field**: none\n"), "failed"),
            ("deep-lint", "a Changed field with no value",
             lambda: restore(log_md, log_text + "\n## [2026-10-13] deep-lint | x\n- **Changed**:\n"
                                                "- **Conflicts**: none\n"), "failed"),
            ("deep-lint", "a Conflicts field with no value",
             lambda: restore(log_md, log_text + "\n## [2026-10-13] deep-lint | x\n"
                                                "- **Changed**: e\n- **Conflicts**:   \n"),
             "failed"))
    check("\n## [2026-10-02] deep-lint | second\n" in log_text, "the log has no valid heading")
    for number, (source, name, spoil, status) in enumerate(legs):
        today = (datetime.date(2026, 10, 19) + datetime.timedelta(days=2 * number)).isoformat()
        spoil()
        try:
            manifest = world.manifest_path()
            code, out, _ = world.run("--manifest-out", manifest, today=today)
        finally:
            restore(log_md, log_text)
            restore(register, register_text)
        data = load(manifest)
        label = "comparison source: %s" % source
        check(code == 3 and data["complete"] is False and data["labels_limited"] is True
              and status_of(data, label) == status and "LABELS LIMITED" in out
              and "none of its findings can be labelled `new kind`" in out,
              "%s %s: exit %d, complete %r, limited %r: %s" % (
                  source, name, code, data["complete"], data["labels_limited"], out[-700:]))
        check(not any(entry.endswith(("log.md", "known-issues.md")) for entry in data["unread"]),
              "%s %s: a comparison source was made owed content: %r" % (source, name,
                                                                        data["unread"]))
        # D18: a deep-lint leg never falls back to the older, whole entry of 2026-10-02
        check(source != "deep-lint" or "the deep-lint entry of 2026-10-02" not in out,
              "%s %s: the older entry was read in the latest's place: %s" % (source, name,
                                                                             out[-500:]))
        out = world.record(data["slice"], today=today, manifest=manifest)
        check(world.state_data()["audits"][-1]["complete"] is False and "LABELS LIMITED" in out,
              "%s %s: the record: %s" % (source, name, out[:400]))
        code, out, _ = world.run(today=(datetime.date(2026, 10, 20) + datetime.timedelta(
            days=2 * number)).isoformat())
        check(code == 0 and "LABELS LIMITED" not in out
              and "the deep-lint entry of 2026-10-02" in out,
              "%s %s: the recovery: %d %s" % (source, name, code, out[-400:]))


# D18's raw protocols: the shapes a fence or comment reader once interpreted, each now a page's text
# like any other for the four raw consumers (the register, the lifecycle page, the log and the
# report). The page endings that leave a fence open (which a fence reader refused), the same shapes
# closed, and the comment shapes the earlier readers misread (CR-AUDIT8's and CR-AUDIT9's).
FENCE_ENDINGS = (("an ordinary unclosed fence", "```python\nx\n"),
                 ("a false fence closer (CR-AUDIT8's register ending)",
                  "```python\nx\n```not-close\n"),
                 ("a bare marker after a backtick line whose info string holds a backtick",
                  "``` not `a` fence\n```\nx\n"),
                 ("a tilde fence whose info string holds a backtick", "~~~ `x`\ny\n"))
CLOSED_FENCES = ("```python\nx\n```not-close\n```  \n~~~\n## not a heading\n~~~\t\n"
                 "~~~ `x`\n## not a heading either\n~~~\n````\n```\n## not one either\n````\n"
                 "``` this line quotes `code`, so it is text\n")
COMMENT_SHAPES = (
    ("CR-AUDIT9 F1: an opening after an escaped backtick", "text \\` <!-- open `\n"),
    ("CR-AUDIT9 F2: an opening inside a code span over three lines",
     "text `example\nliteral <!-- is code\nend`\n"),
    ("CR-AUDIT8 F1: an opening after text, never closed", "text <!-- cut here\n"),
    ("CR-AUDIT8 F1: an opening after a comment closed on its line",
     "<!-- closed --> <!-- cut here\n"),
    ("an opening alone on its line, never closed", "<!--\n"),
    ("a closing alone on its line", "-->\n"),
    ("an opener quoted as code (the live register's shape)", "a quoted opener, `<!--`, is code\n"),
    # CR-AUDIT10's two hiding shapes, each closed: a list fence (F1) and fence markers inside
    # comments (F2), which a fence reader read as a fence opened and left open
    ("CR-AUDIT10 F1: a list fence, closed inside its item", "- ```\n  ```\n\n"),
    ("CR-AUDIT10 F2: a fence marker inside a comment", "<!--\n```\n-->\n\n"))


def page_consumers():
    """Each raw Markdown page a pick reads by its literal-line protocol (D18): (its page, its
    acquisition, the kind the suite reads it as, the anchor before which a control's shapes go,
    and what a whole pick must have read from it)."""
    return (
        (REGISTER_REL, "comparison source: the register", "register", "## Closed\n",
         lambda out, result: "LABELS LIMITED" not in out),
        (LIFECYCLE_REL, "lifecycle rows", "lifecycle", HEADER,
         lambda out, result: has(result["parts"].get("due", []), ".claude/hooks/gate.py")),
        (LOG_REL, "comparison source: deep-lint", "log", "## [2026-10-02] deep-lint | second\n",
         lambda out, result: "the deep-lint entry of 2026-10-02" in out
         and "LABELS LIMITED" not in out))


def consumer_pages(world):
    """{page: its whole text} for the raw pages of page_consumers and the two standing-rules
    files, as the fixture holds them."""
    original = {}
    for rel in [entry[0] for entry in page_consumers()] + ["vault/CLAUDE.md",
                                                           "vault/CUSTOMISATION.md"]:
        with open(world.path(rel), encoding="utf-8") as handle:
            original[rel] = handle.read()
    return original


def shapes_before(original, rel, anchor, shapes):
    """The page `rel` with `shapes` put just before its one line (or lines) `anchor`."""
    check(original[rel].count(anchor) == 1, "the control's anchor %r" % anchor)
    return original[rel].replace(anchor, shapes + anchor)


def pick_page(world, rel, text, original, today=TODAY):
    """(exit, output, manifest) of a pick with the page `rel` holding `text`, put back after."""
    world.write(rel, text)
    manifest = world.manifest_path()
    try:
        code, out, _ = world.run("--manifest-out", manifest, today=today)
    finally:
        world.write(rel, original[rel])
    return code, out, load(manifest)


def case_raw_inputs_read_every_line(world):
    """D18, item 2, and CR-AUDIT-B finding 3's first sentence: the four raw consumers read every
    raw line, interpreting no fence and no comment. In the register, the lifecycle page and the
    log, each of FENCE_ENDINGS (an ordinary unclosed fence, a false closer, a bare marker after a
    backtick-info line, a tilde fence holding a backtick) at the page's end, CLOSED_FENCES, and each
    of COMMENT_SHAPES (CR-AUDIT8's, CR-AUDIT9's and CR-AUDIT10's) just before a part the consumer
    needs leave the pick complete (exit 0) with that part read, and this suite's raw reading
    (structure_problem) finds each page whole. What stands inside a comment or a fenced block is read
    as if neither were there: the register's `## Closed` section inside a comment and after a fence
    left open, the lifecycle table with its due row inside a fenced block and inside a comment, and a
    newer deep-lint entry inside a comment and inside a fenced block. So a fence or a comment can
    neither hide evidence from these consumers nor break a page for them. The reviewer's report
    holding each shape before its `## Not read` section, and one whose section follows a fence left
    open or a comment's opening never closed, is recorded complete."""
    rows = due_row_world(world)
    original = consumer_pages(world)
    check(rows[-1].startswith("| .claude/hooks/gate.py |"), "the due row")
    for rel, acquisition, kind, anchor, holds in page_consumers():
        texts = [("ending in %s" % name, original[rel] + ending) for name, ending in FENCE_ENDINGS]
        texts.append(("holding the closed fence shapes",
                      shapes_before(original, rel, anchor, CLOSED_FENCES)))
        texts += [("holding %s" % name, shapes_before(original, rel, anchor, shape))
                  for name, shape in COMMENT_SHAPES]
        for name, text in texts:
            check(structure_problem(kind, text) is None, "the suite's raw reading over %s %s: %r"
                  % (rel, name, structure_problem(kind, text)))
            code, out, data = pick_page(world, rel, text, original)
            result = parse(out)
            check(code == 0 and data["complete"] is True and status_of(data, acquisition) == "ok"
                  and data["labels_limited"] is False and holds(out, result),
                  "%s %s: exit %d, complete %r, %s %s: %r" % (
                      rel, name, code, data["complete"], acquisition,
                      status_of(data, acquisition), result["incomplete"]))
    # what stands inside a comment or a fence is read as if neither were there
    front = "---\ntitle: Check lifecycle\n---\n\n# Check lifecycle\n\n"
    table = "\n".join([HEADER, SEPARATOR] + rows)

    def register_read(out, result, data):
        return status_of(data, "comparison source: the register") == "ok" \
            and "LABELS LIMITED" not in out

    def table_read(out, result, data):
        return has(result["parts"].get("due", []), ".claude/hooks/gate.py") \
            and "lifecycle rows parsed %d" % len(rows) in result["controls"]

    def entry_read(out, result, data):
        return "the deep-lint entry of 2026-10-13" in out and "LABELS LIMITED" not in out
    later = "## [2026-10-13] deep-lint | inside\n- **Changed**: e\n- **Conflicts**: none\n"
    inside = (
        (REGISTER_REL, "the register's Closed section inside a comment",
         original[REGISTER_REL].replace("## Closed\n", "<!-- kept for the record\n## Closed\n")
         .replace("## Related\n", "-->\n## Related\n"), "register", register_read),
        (REGISTER_REL, "the register's Closed section after a fence left open",
         original[REGISTER_REL].replace("## Closed\n", "```text\n## Closed\n"), "register",
         register_read),
        (LIFECYCLE_REL, "the lifecycle table inside a fenced block",
         front + "```text\n" + table + "\n```\n" + LIFECYCLE_TAIL, "lifecycle", table_read),
        (LIFECYCLE_REL, "the lifecycle table inside a comment",
         front + "<!--\n" + table + "\n-->\n" + LIFECYCLE_TAIL, "lifecycle", table_read),
        (LOG_REL, "a newer deep-lint entry inside a comment",
         original[LOG_REL] + "<!--\n" + later + "-->\n", "log", entry_read),
        (LOG_REL, "a newer deep-lint entry inside a fenced block",
         original[LOG_REL] + "```text\n" + later + "```\n", "log", entry_read))
    for rel, name, text, kind, holds in inside:
        check(structure_problem(kind, text) is None, "the suite's raw reading over %s: %r"
              % (name, structure_problem(kind, text)))
        code, out, data = pick_page(world, rel, text, original)
        result = parse(out)
        check(code == 0 and data["complete"] is True and holds(out, result, data),
              "%s: exit %d, complete %r: %r %s" % (name, code, data["complete"],
                                                   result["incomplete"], out[-500:]))
    # the reviewer's report: each shape before its `## Not read` section is recorded complete
    manifest, out = world.pick(today=TODAY)
    data = load(manifest)
    saved = world.state_data()
    reports = [(name, "# Report\n\n" + shape + NONE_READ)
               for name, shape in COMMENT_SHAPES + FENCE_ENDINGS + (("the closed fence shapes",
                                                                     CLOSED_FENCES),)]
    reports += [("a section after a comment's opening never closed",
                 "# Report\n\n<!--\n" + NONE_READ),
                ("a section after a fence left open", "# Report\n\n```text\nan example\n"
                 + NONE_READ)]
    for name, text in reports:
        check(structure_problem("report", text) is None,
              "the suite's raw reading over a report holding %s: %r" % (name, structure_problem(
                  "report", text)))
        world.set_state(saved)
        code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest",
                                 manifest, "--report", world.report(text=text))
        check(code == 0 and "says none" in out
              and world.state_data()["audits"][-1]["complete"] is True,
              "a report holding %s: %d %s" % (name, code, out[:300]))


def case_coverage_raw_protocol(world):
    """D18, item 2, and CR-AUDIT-B's first acceptance area: the coverage declaration is counted on
    raw lines over the whole report. Exactly one line declaring `## Not read` is required (its
    grammar: a `#` heading whose text begins with `not read`, in any case, after any spaces, `>`
    marks or list markers). A second one inside an ordinary fence, a list fence, a block quote or a
    comment, an indented example of the section, a draft section, and CR-AUDIT10's two reports (F1:
    two conflicting sections around list fences; F2: around fence markers inside comments, both of
    which B-AUDIT10 recorded complete, discharging the debt) each refuse the record with slices.json
    byte for byte unchanged; so do a lone declaration in another form (`### Not read`, a quoted or
    listed one), a second closing line before the heading or after the section, and the missing,
    empty, malformed, cut and miscounted sections of report_refused and report_cut_refused. The
    controls: a lone declaration after a fence left open, after CR-AUDIT10's list fence and after
    its comment fences, each read, record complete (the closed list and comment shapes keep their
    validity), the list-fence report holding its one omission records it owed, and a mention of the
    heading inside a sentence is no declaration; exact path characters stay (report_paths_exact)."""
    world.record("standing-rules")
    world.write("vault/wiki/developments/design.md", "# Design\n\nchanged this week\n")
    manifest, out = world.pick(today=TODAY)
    data = load(manifest)
    first = world.path("vault/wiki/developments/design.md")
    check(first in data["reading"], "the fixture's changed file %r" % data["reading"])
    saved = world.state_data()
    before = digest(world.state)
    owes = "## Not read\n%s\nEND NOT READ: 1\n" % first
    end = "END NOT READ: %d\n"
    refused = (
        ("a second declaration inside an ordinary fence", "# Report\n\n```\n" + owes + "```\n\n"
         + NONE_READ, "holds 2 sections"),
        ("a second declaration inside a list fence",
         "# Report\n\n- ```\n  ## Not read\n  %s\n  END NOT READ: 1\n  ```\n\n" % first
         + NONE_READ, "holds 2 sections"),
        ("a second declaration in a block quote",
         "# Report\n\n> ## Not read\n> %s\n> END NOT READ: 1\n\n" % first + NONE_READ,
         "holds 2 sections"),
        ("a second declaration in a comment", "# Report\n\n<!--\n" + owes + "-->\n\n" + NONE_READ,
         "holds 2 sections"),
        ("an indented example of the section", "# Report\n\nThe template:\n\n    ## Not read\n"
         "    none\n\n" + NONE_READ, "holds 2 sections"),
        ("a draft section before the last", "# Report\n\n## Not read (draft)\n%s\n\n" % first
         + NONE_READ, "holds 2 sections"),
        ("CR-AUDIT10 F1: two sections around list fences",
         "- ```\n  ```\n\n" + owes + "\n- ```\n  ```\n\n" + NONE_READ, "holds 2 sections"),
        ("CR-AUDIT10 F2: two sections around fence markers inside comments",
         "<!--\n```\n-->\n\n" + owes + "\n<!--\n```\n-->\n\n" + NONE_READ, "holds 2 sections"),
        ("a lone declaration at another level", "# Report\n\n### Not read\nnone\n" + end % 0,
         "the nearest heading is '### Not read'"),
        ("a lone declaration in a block quote", "# Report\n\n> ## Not read\nnone\n" + end % 0,
         "the nearest heading is '> ## Not read'"),
        ("a lone declaration in a list item", "# Report\n\n- ## Not read\nnone\n" + end % 0,
         "the nearest heading is '- ## Not read'"),
        ("a closing line before the heading", "# Report\n\n" + end % 0 + "\n" + NONE_READ,
         "before its `## Not read` heading"),
        ("a quoted closing line after the section", "# Report\n\n" + NONE_READ + "> " + end % 0,
         "after its closing `END NOT READ` line"))
    for name, text, expected in refused:
        check(structure_problem("report", text) is not None,
              "the suite's raw reading accepts %s" % name)
        refused_unchanged(world, ("--record", data["slice"], "--findings", "0", "--manifest",
                                  manifest, "--report", world.report(text=text)), expected, before)
        check(not [n for n in os.listdir(os.path.dirname(world.state)) if n.endswith(".tmp")],
              "%s left a temporary file" % name)
    accepted = (
        ("a lone declaration after a fence left open", "# Report\n\n```text\nan example\n"
         + NONE_READ),
        ("a lone declaration after CR-AUDIT10's list fence", "# Report\n\n- ```\n  ```\n\n"
         + NONE_READ),
        ("a lone declaration after CR-AUDIT10's comment fences", "# Report\n\n<!--\n```\n-->\n\n"
         + NONE_READ),
        ("a mention of the heading inside a sentence", "# Report\n\nThe `## Not read` section "
         "ends this report.\n\n" + NONE_READ))
    for name, text in accepted:
        check(structure_problem("report", text) is None,
              "the suite's raw reading refuses %s" % name)
        world.set_state(saved)
        code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest",
                                 manifest, "--report", world.report(text=text))
        check(code == 0 and "says none" in out
              and world.state_data()["audits"][-1]["complete"] is True,
              "%s: %d %s" % (name, code, out[:300]))
    world.set_state(saved)
    code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest", manifest,
                             "--report", world.report(text="- ```\n  ```\n\n" + owes))
    stored = world.state_data()
    check(code == 0 and stored["audits"][-1]["complete"] is False
          and {"entry": "vault/wiki/developments/design.md", "since": TODAY} in stored["owed"],
          "the list-fence report with its one omission: %d %r %s" % (code, stored["owed"],
                                                                     out[:400]))


def case_lifecycle_raw_protocol(world):
    """D18, item 2, and CR-AUDIT-B's second acceptance area for the lifecycle page: every raw line
    is examined, so a torn row cannot disappear. CR-AUDIT10 F1's plant (a valid empty table, then a
    torn table between list fences, which B-AUDIT10 accepted, the pick complete) and its F2
    counterpart (fence markers inside comments) each make the page UNKNOWN (due and missing rows
    UNKNOWN, the manifest and the record incomplete), and so does an example row quoted in a code
    block (rows in no table); a due row inside a fenced block, or after the list and comment shapes,
    is read and due. The controls: the intact page, the valid empty table alone, and the list and
    comment shapes with a whole table after them each complete."""
    rows = due_row_world(world)
    page = LIFECYCLE_REL
    front = "---\ntitle: Check lifecycle\n---\n\n# Check lifecycle\n\n"
    empty = "\n".join([HEADER, SEPARATOR]) + "\n\n"
    torn = "\n".join([HEADER, SEPARATOR, rows[-1][:-6]]) + "\n\n"
    whole = "\n".join([HEADER, SEPARATOR] + rows) + "\n\n"
    list_fence, comment_fence = "- ```\n  ```\n\n", "<!--\n```\n-->\n\n"
    damaged = (("CR-AUDIT10 F1: an empty table, then a torn table between list fences",
                front + empty + list_fence + torn + list_fence + LIFECYCLE_TAIL),
               ("CR-AUDIT10 F2: an empty table, then a torn table between comment fences",
                front + empty + comment_fence + torn + comment_fence + LIFECYCLE_TAIL),
               ("an example row quoted in a code block (rows in no table)",
                front + whole + "```text\n" + rows[0] + "\n```\n" + LIFECYCLE_TAIL))
    day = datetime.date(2026, 10, 18)
    for name, text in damaged:
        day += datetime.timedelta(days=1)
        check(structure_problem("lifecycle", text) is not None,
              "the suite's raw reading accepts %s" % name)
        world.write(page, text)
        manifest = world.manifest_path()
        code, out, _ = world.run("--manifest-out", manifest, today=day.isoformat())
        data = load(manifest)
        check(code == 3 and "DUE ROWS: UNKNOWN" in out and "MISSING ROWS: UNKNOWN" in out
              and data["complete"] is False and status_of(data, "lifecycle rows") == "unknown",
              "%s: exit %d, complete %r: %s" % (name, code, data["complete"], out[-600:]))
        out = world.record(data["slice"], today=day.isoformat(), manifest=manifest)
        check(world.state_data()["audits"][-1]["complete"] is False and "INCOMPLETE AUDIT" in out,
              "%s: the record read complete" % name)
    read = (("the intact page", front + whole + LIFECYCLE_TAIL, True),
            ("a due row inside a fenced block", front + "```text\n" + whole + "```\n"
             + LIFECYCLE_TAIL, True),
            ("a whole table after CR-AUDIT10's list fence", front + list_fence + whole
             + LIFECYCLE_TAIL, True),
            ("a whole table after CR-AUDIT10's comment fences", front + comment_fence + whole
             + LIFECYCLE_TAIL, True),
            ("the valid empty table alone", front + empty + LIFECYCLE_TAIL, False))
    for name, text, due in read:
        day += datetime.timedelta(days=1)
        check(structure_problem("lifecycle", text) is None,
              "the suite's raw reading refuses %s: %r" % (name, structure_problem("lifecycle",
                                                                                  text)))
        world.write(page, text)
        manifest = world.manifest_path()
        code, out, _ = world.run("--manifest-out", manifest, today=day.isoformat())
        result = parse(out)
        check(code == 0 and load(manifest)["complete"] is True
              and has(result["parts"].get("due", []), ".claude/hooks/gate.py") == due,
              "%s: exit %d, due %r: %s" % (name, code, result["parts"].get("due"), out[-600:]))
    world.lifecycle(rows)


# THE SECTION ADAPTER's acceptance (D18; CR-AUDIT-B finding 1 and its third acceptance area):
# adversarial fixtures, each with its expected section list written here by hand as (line, heading)
# pairs, or None where the adapter must refuse (UNKNOWN: unsupported or undecidable syntax). They
# cover comment and fence interactions, lists, block quotes, fence-marker variants, a front matter
# and the heading forms. The lifecycle keys are derived by expected_key, written apart from
# slice.py's group_key; markdown-it never supplies an expected value.
ADAPTER_FIXTURES = (
    ("CR-AUDIT-B finding 1's counterexample: comments holding fence markers around a section",
     "## Existing\n<!--\n```\n-->\n## New rule\nA standing requirement.\n<!--\n```\n-->\n",
     [(1, "Existing"), (5, "New rule")]),
    ("fence markers inside a one-line comment", "## A\n<!-- ``` -->\n## B\n", [(1, "A"), (3, "B")]),
    ("a fence holding a comment opener", "## A\n```\n<!--\n```\n## B\n", [(1, "A"), (5, "B")]),
    ("a comment opened after text, no block", "## A\ntext <!-- cut here\n## B\n",
     [(1, "A"), (3, "B")]),
    ("CR-AUDIT9 F1: an escaped backtick before a comment's opening",
     "## A\ntext \\` <!-- open `\n## B\n", [(1, "A"), (3, "B")]),
    ("CR-AUDIT9 F2: a code span over three lines holding an opening",
     "## A\ntext `example\nliteral <!-- is code\nend`\n## B\n", [(1, "A"), (5, "B")]),
    ("an unclosed comment hiding a section", "## A\n<!--\n## B\n", None),
    ("a closed comment holding a section", "## A\n<!--\n## B\n-->\n## C\n", None),
    ("an HTML block holding a section", "## A\n<details>\n## B\n</details>\n", None),
    ("CR-AUDIT-B finding 1's list-fence counterpart",
     "## Existing\n- ```\n  ```\n\n## New rule\nA standing requirement.\n- ```\n  ```\n",
     [(1, "Existing"), (5, "New rule")]),
    ("a list item holding a closed fence with a heading-like line",
     "## A\n- ```\n  ## B\n  ```\n## C\n", [(1, "A"), (5, "C")]),
    ("a list fence left open hiding a heading-like line", "## A\n- ```\n  ## B\n\n## C\n", None),
    ("a level-2 heading in a list item", "## A\n- ## B\n", None),
    ("a section straight after a list item", "## A\n- item\n## B\n", [(1, "A"), (3, "B")]),
    ("a level-2 heading in a block quote", "## A\n> ## B\n", None),
    ("a block quote holding a fence with a heading-like line",
     "## A\n> ```\n> ## B\n> ```\n## C\n", [(1, "A"), (5, "C")]),
    ("a section straight after a block quote", "## A\n> quoted\n## B\n", [(1, "A"), (3, "B")]),
    ("a tilde fence", "## A\n~~~\n## B\n~~~\n## C\n", [(1, "A"), (5, "C")]),
    ("a backtick fence holding a tilde marker", "## A\n```\n~~~\n## B\n```\n## C\n",
     [(1, "A"), (6, "C")]),
    ("a longer fence a shorter marker cannot close", "## A\n````\n```\n## B\n````\n## C\n",
     [(1, "A"), (6, "C")]),
    ("a false closer, text after its marker", "## A\n```\n## B\n```not-close\n```\n## C\n",
     [(1, "A"), (6, "C")]),
    ("a closer three spaces in", "## A\n```\n## B\n   ```\n## C\n", [(1, "A"), (5, "C")]),
    ("a closer four spaces in, which closes nothing", "## A\n```\n## B\n    ```\n## C\n", None),
    ("a backtick line whose info string holds a backtick, no fence",
     "## A\n``` not `a` fence\n## B\n", [(1, "A"), (3, "B")]),
    ("a bare marker after such a line, left open", "## A\n``` not `a` fence\n```\n## B\n", None),
    ("a marker four spaces in, indented code and no fence", "## A\n    ```\n## B\n",
     [(1, "A"), (3, "B")]),
    ("a fence whose info string names a language, holding a log template",
     "## A\n```markdown\n## [YYYY-MM-DD] ingest | x\n```\n## B\n", [(1, "A"), (5, "B")]),
    ("a front matter set aside", "---\ntitle: x\n---\n\n## A\n", [(5, "A")]),
    ("a front matter never closed", "---\ntitle: x\n## A\n", None),
    ("a front matter holding a heading-like line", "---\n## x\n---\n## A\n", None),
    ("ATX forms: closing hashes, a tab after the marker, three spaces in",
     "## A ##\n##\tB\n   ## C\n", [(1, "A"), (2, "B"), (3, "C")]),
    ("a setext level-2 heading", "## A\nB\n---\n", None),
    ("a thematic break after a blank line", "## A\ntext\n\n---\n## B\n", [(1, "A"), (5, "B")]),
    ("an empty level-2 heading", "## A\n##\n", [(1, "A"), (2, "")]),
    ("`##` with no space after it, no heading", "## A\n##B\n", [(1, "A")]),
    ("CRLF line endings", "## A\r\n```\r\n## B\r\n```\r\n## C\r\n", [(1, "A"), (5, "C")]),
    ("a carriage return that ends no line", "## A\rtext\n## B\n", None),
    ("no section", "# Title\ntext\n", None))
# CLAUDE.md's sections are keyed by their number (written here by hand too)
NUMBERED_FIXTURES = (
    ("numbered sections around a fenced example", "## 1. One\n```\n## 2. Two\n```\n## 3. Three\n",
     [(1, "1. One"), (5, "3. Three")]),
    ("the counterexample with numbered sections",
     "## 1. Existing\n<!--\n```\n-->\n## 2. New rule\nx\n<!--\n```\n-->\n",
     [(1, "1. Existing"), (5, "2. New rule")]))
# corpus coverage, recorded (counted by hand from the two tables above): 25 unnumbered fixtures
# hold sections, 22 of them two each, the ATX forms three, the front matter and `##B` one each
# (22 x 2 + 3 + 1 + 1 = 49), each compared as CLAUDE.md and as CUSTOMISATION.md (98), and the two
# numbered fixtures two each (4): 102 locations and keys in all; 13 fixtures are written refused
ADAPTER_COMPARED, ADAPTER_REFUSED = 102, 13


def expected_key(file_name, heading):
    """The lifecycle key a section written by hand registers, by this suite's own rule: CLAUDE.md's
    by its leading number when the heading has one, every other by its heading, in any case."""
    number = re.match(r"^(\d+)\.?(?:\s|$)", heading)
    if file_name == "CLAUDE.md" and number:
        return ("group", "claude.md", number.group(1))
    return ("group", file_name.lower(), heading.strip().casefold())


def case_section_adapter_projection(world):
    """D18, item 3, and CR-AUDIT-B's third acceptance area: the adapter's projection (section
    locations and lifecycle keys) equals the expected list written by hand for each adversarial
    fixture of ADAPTER_FIXTURES and NUMBERED_FIXTURES, read as CLAUDE.md and as CUSTOMISATION.md;
    a successful partial list fails, and each fixture written as unsupported or undecidable comes
    back UNKNOWN (no list, a syntax reason). Ordinary supported sections succeed. The corpus
    coverage is recorded (ADAPTER_COMPARED locations and keys, ADAPTER_REFUSED refusals). The
    oracle's dependency, markdown-it-py for this interpreter, missing fails the case, never skips
    it. Through real picks: CR-AUDIT-B's counterexample and its list-fence counterpart added to the
    fixture's CLAUDE.md give the complete inventory (its section 4, which no row enrols, listed as a
    missing row; with a row for it, none), where B-AUDIT10's reader hid section 4 and so listed no
    missing row; the same shapes with the comment left open read UNKNOWN, the pick incomplete."""
    module = load_slice()
    probe = module.standing_sections("## A\n")
    check(len(probe) == 3 and probe[2] != "parser",
          "the oracle's dependency: markdown-it-py %s cannot be imported by this interpreter (%s), "
          "so the adapter's acceptance cannot run: a failure, never a skip"
          % (module.MARKDOWN_IT_VERSION, probe[1]))
    compared, refused = 0, 0
    for name, text, expected in ADAPTER_FIXTURES + NUMBERED_FIXTURES:
        got = module.standing_sections(text)
        check(len(got) == 3, "%s: the adapter returned %r" % (name, got))
        if expected is None:
            check(got[0] is None and got[2] == "syntax" and got[1],
                  "%s: UNKNOWN written by hand, the adapter gave %r" % (name, got))
            refused += 1
            continue
        check(got[1] is None and got[2] is None, "%s: the adapter refused it: %r" % (name, got[1]))
        files = ("CLAUDE.md",) if (name, text, expected) in NUMBERED_FIXTURES \
            else ("CLAUDE.md", "CUSTOMISATION.md")
        for file_name in files:
            projection = [(line, key) for (line, _), (_, key)
                          in zip(got[0], module.section_groups(file_name, got[0]))]
            wanted = [(line, expected_key(file_name, heading)) for line, heading in expected]
            check(len(got[0]) == len(module.section_groups(file_name, got[0]))
                  and projection == wanted,
                  "%s, read as %s: the adapter's projection %r, %r written by hand"
                  % (name, file_name, projection, wanted))
            compared += len(wanted)
    check((compared, refused) == (ADAPTER_COMPARED, ADAPTER_REFUSED),
          "the corpus coverage: %d locations and keys compared, %d refusals; %d and %d recorded"
          % (compared, refused, ADAPTER_COMPARED, ADAPTER_REFUSED))
    # through real picks
    world.record("standing-rules")
    with open(world.path("vault/CLAUDE.md"), encoding="utf-8") as handle:
        claude = handle.read()
    rows = world.every_item_row()
    shapes = (("CR-AUDIT-B's counterexample", "<!--\n```\n-->\n## 4. New rule\nA standing "
               "requirement.\n<!--\n```\n-->\n"),
              ("its list-fence counterpart", "- ```\n  ```\n\n## 4. New rule\nA standing "
               "requirement.\n- ```\n  ```\n"))
    for number, (name, shape) in enumerate(shapes):
        world.write("vault/CLAUDE.md", claude + "\n" + shape)
        world.lifecycle(rows)
        code, out, _ = world.run(today="2026-10-%d" % (19 + 2 * number))
        result = parse(out)
        check(code == 0 and result["missing"] == ["CLAUDE.md §4 | text group"]
              and "sections read: CLAUDE.md 4, CUSTOMISATION.md 2" in result["controls"],
              "%s: exit %d, missing %r: %s" % (name, code, result["missing"], out[-500:]))
        world.lifecycle(rows + [row("CLAUDE.md §4", kind="text")])
        code, out, _ = world.run(today="2026-10-%d" % (20 + 2 * number))
        check(code == 0 and parse(out)["missing"] == [],
              "%s with its row: exit %d, missing %r" % (name, code, parse(out)["missing"]))
    world.write("vault/CLAUDE.md", claude + "\n<!--\n```\n## 4. New rule\nA standing requirement.\n")
    world.lifecycle(rows)
    manifest = world.manifest_path()
    code, out, _ = world.run("--manifest-out", manifest, today="2026-10-25")
    result = parse(out)
    check(code == 3 and "MISSING ROWS: UNKNOWN" in out and "CLAUDE.md §4 | text group"
          not in result["missing"] and status_of(load(manifest), "inventory") == "failed",
          "the comment left open: exit %d, missing %r: %s" % (code, result["missing"], out[-500:]))
    world.write("vault/CLAUDE.md", claude)


def python_run(command, env_extra=None, timeout=TIMEOUT_S):
    """(exit, stdout) of a command run with the environment, CLAUDE_PROJECT_DIR and LLM_WIKI_VAULT
    left out, plus `env_extra`; stdout read as bytes and decoded strictly."""
    env = dict(os.environ)
    for name in ("CLAUDE_PROJECT_DIR", "LLM_WIKI_VAULT", "PYTHONPATH"):
        env.pop(name, None)
    env.update(env_extra or {})
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                          timeout=timeout)
    return done.returncode, searched(done.stdout.decode("utf-8"))


def case_section_adapter_dependency(world):
    """D18, item 3: markdown-it-py missing (the same interpreter run with no site-packages, `-S`,
    where the package lives: the premise is checked first), unimportable (a planted package that
    raises as it imports) or of another version (a planted 9.9.9) makes the section inventory
    UNKNOWN (the inventory's outcome unknown, its reason naming the package), MISSING ROWS UNKNOWN
    and the pick incomplete (exit 3), never a fallback to another reader: no text group is listed,
    and nothing is owed for the two files, which read whole. (That the in-run section plants then
    say they could not run, rather than refusing the pick, is controls_line's.) The record of that pick, a fresh --init and pass_order.py run under `-S` too, each
    succeeding without the package. The control: the same pick with the installed package
    completes."""
    world.record("standing-rules")
    code, _ = python_run([sys.executable, "-S", "-c", "import markdown_it"])
    check(code != 0, "the premise: markdown-it-py is still importable under -S")
    planted = {}
    for name, body in (("raises", "raise RuntimeError('a planted markdown-it-py that cannot be "
                                  "imported')\n"),
                       ("other version", "__version__ = '9.9.9'\n")):
        folder = os.path.join(world.root, "planted-%s" % name.replace(" ", "-"))
        os.makedirs(os.path.join(folder, "markdown_it"))
        with open(os.path.join(folder, "markdown_it", "__init__.py"), "w", encoding="utf-8") as h:
            h.write(body)
        planted[name] = folder
    legs = (("missing (-S)", ["-S"], None, "ModuleNotFoundError"),
            ("unimportable", [], {"PYTHONPATH": planted["raises"]}, "RuntimeError"),
            ("of another version", [], {"PYTHONPATH": planted["other version"]},
             "version 9.9.9, not 4.2.0"))
    for number, (name, flags, env, reason) in enumerate(legs):
        today = "2026-10-%d" % (19 + 2 * number)
        manifest = world.manifest_path()
        code, out = python_run([sys.executable] + flags + ["-B", SLICE]
                               + world.argv(["--manifest-out", manifest], today), env)
        data, result = load(manifest), parse(out)
        check(code == 3 and data["complete"] is False and status_of(data, "inventory") == "unknown"
              and any(line.startswith("inventory: unknown: ") and "markdown-it-py" in line
                      and reason in line for line in result["incomplete"])
              and "MISSING ROWS: UNKNOWN" in out
              and not any(m.endswith("| text group") for m in result["missing"])
              and not any(e in ("vault/CLAUDE.md", "vault/CUSTOMISATION.md")
                          for e in data["unread"]),
              "%s: exit %d, inventory %s: %r %s" % (name, code, status_of(data, "inventory"),
                                                    result["incomplete"], out[-500:]))
        code, out = python_run([sys.executable] + flags + ["-B", SLICE] + world.argv(
            ["--record", data["slice"], "--findings", "0", "--manifest", manifest, "--report",
             world.report()], today), env)
        check(code == 0 and out.startswith("RECORDED") and "INCOMPLETE" in out.splitlines()[0],
              "%s: the record without the package: %d %s" % (name, code, out[:300]))
    state = os.path.join(world.root, "fresh", "slices.json")
    os.makedirs(os.path.dirname(state))
    code, out = python_run([sys.executable, "-S", "-B", SLICE, "--init", "--state", state])
    check(code == 0 and out.startswith("INITIALISED"), "--init without the package: %d %s"
          % (code, out[:200]))
    events = event_log(os.path.join(world.root, "logs", "no-package.log"),
                       [("read", world.path("vault/CLAUDE.md")), ("message", FINDINGS)])
    code, out = python_run([sys.executable, "-S", "-B", PASS_ORDER, "--events", events])
    check(code == 0 and out.startswith("COMMANDS BEFORE THE FIRST-PASS MESSAGE: 1"),
          "pass_order.py without the package: %d %s" % (code, out[:200]))
    code, out = python_run([sys.executable, "-B", SLICE] + world.argv([], "2026-10-30"))
    check(code == 0 and "acquisitions all ok" in parse(out)["summary"],
          "the control with the installed package: %d %s" % (code, out[-300:]))


def markdown_it_imports(source):
    """[(the function holding it, or `<module>`, its line)] of each place `source` imports
    markdown-it-py: an import statement naming markdown_it or a module below it, or a call of
    __import__ or importlib.import_module with a string naming one."""
    found = []

    def visit(node, owner):
        for child in ast.iter_child_nodes(node):
            inner = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                     ast.ClassDef)) else owner
            names = []
            if isinstance(child, ast.Import):
                names = [alias.name for alias in child.names]
            elif isinstance(child, ast.ImportFrom):
                names = [child.module or ""]
            elif isinstance(child, ast.Call) and getattr(child.func, "id", getattr(
                    child.func, "attr", None)) in ("__import__", "import_module"):
                names = [arg.value for arg in child.args if isinstance(arg, ast.Constant)
                         and isinstance(arg.value, str)]
            if any(name.split(".")[0] == "markdown_it" for name in names):
                found.append((owner, child.lineno))
            visit(child, inner)
    visit(ast.parse(source), "<module>")
    return found


IMPORT_CHILD = r'''
import contextlib, importlib.util, io, json, sys
sys.dont_write_bytecode = True
args = json.loads(sys.argv[1])
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
module = load(args["slice"], "slice_under_imports")
order = load(args["pass_order"], "order_under_imports")
adapter = module.standing_sections.__code__
current, events = {"run": None}, []
def hook(event, hook_args):
    if event != "import" or str(hook_args[0]).split(".")[0] != "markdown_it":
        return
    frame, inside = sys._getframe(1), False
    while frame is not None and not inside:
        inside = frame.f_code is adapter
        frame = frame.f_back
    events.append([current["run"], str(hook_args[0]), inside])
sys.addaudithook(hook)
codes = []
for label, argv in args["runs"]:
    current["run"] = label
    for name in [n for n in list(sys.modules) if n.split(".")[0] == "markdown_it"]:
        del sys.modules[name]
    with contextlib.redirect_stdout(io.StringIO()):
        codes.append((order if label == "pass_order" else module).main(argv))
sys.stdout.write(json.dumps({"codes": codes, "events": events}))
'''


def case_adapter_alone_imports_markdown_it(world):
    """D18, item 3, and CR-AUDIT-B's fifth acceptance area as spec-D18.md reads it: no production
    path but the adapter imports markdown-it-py. Statically, the one place slice.py imports it is
    standing_sections and pass_order.py imports it nowhere (the scan's control: a planted source
    importing it three ways is found three times). At run time, a pick, a record, an --init and
    pass_order.py run in a child process under an `import` audit hook, the package unloaded before
    each run: every load of markdown_it or a module below it happens with standing_sections on the
    call stack, the pick loads it (the control), and the record, the --init and pass_order.py load
    none of it."""
    with open(SLICE, encoding="utf-8") as handle:
        sites = markdown_it_imports(handle.read())
    with open(PASS_ORDER, encoding="utf-8") as handle:
        order_sites = markdown_it_imports(handle.read())
    planted = ("import markdown_it\n\ndef f():\n    from markdown_it.main import MarkdownIt\n"
               "    return __import__('markdown_it')\n")
    check(len(markdown_it_imports(planted)) == 3, "the scan's control: %r"
          % markdown_it_imports(planted))
    check([owner for owner, _ in sites] == ["standing_sections"] and order_sites == [],
          "markdown-it-py is imported at %r in slice.py and %r in pass_order.py; only "
          "standing_sections may" % (sites, order_sites))
    world.record("standing-rules")
    # the record names the slice the child's pick chooses (CR-AUDIT14 F1: it refuses any other),
    # which a plain pick over the same state and date says first, writing nothing
    chosen = parse(world.run()[1])["slice"]
    manifest, report = world.manifest_path(), world.report()
    state = os.path.join(world.root, "fresh", "slices.json")
    os.makedirs(os.path.dirname(state))
    events = event_log(os.path.join(world.root, "logs", "imports.log"),
                       [("read", world.path("vault/CLAUDE.md")), ("message", FINDINGS)])
    runs = [("pick", world.argv(["--manifest-out", manifest])),
            ("record", world.argv(["--record", chosen, "--findings", "0", "--manifest",
                                   manifest, "--report", report])),
            ("init", ["--init", "--state", state]), ("pass_order", ["--events", events])]
    done = subprocess.run([sys.executable, "-B", "-c", IMPORT_CHILD,
                           json.dumps({"slice": SLICE, "pass_order": PASS_ORDER, "runs": runs})],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                          timeout=TIMEOUT_S)
    check(done.returncode == 0, "the import child failed: %s" % done.stderr[-600:])
    result = json.loads(done.stdout)
    check(load(manifest)["slice"] == chosen, "the child's pick chose %s, the plain pick %s"
          % (load(manifest)["slice"], chosen))
    check(result["codes"] == [0, 0, 0, 0], "the runs' exit codes %r" % result["codes"])
    loads = dict((label, [e for e in result["events"] if e[0] == label]) for label, _ in runs)
    check(loads["pick"] and all(e[2] for e in loads["pick"]),
          "the pick's loads of markdown-it-py: %d, outside the adapter %r"
          % (len(loads["pick"]), [e[1] for e in loads["pick"] if not e[2]][:5]))
    check(not loads["record"] and not loads["init"] and not loads["pass_order"],
          "markdown-it-py loaded by the record, --init or pass_order.py: %r"
          % [(e[0], e[1]) for e in result["events"] if e[0] != "pick"][:5])


def case_coverage_mandatory_inputs(world):
    """D18, item 4, and CR-AUDIT-B finding 2, end to end: the pick records every mandatory input in
    its phase (the reading list and the requirement files, pass 1; the second-pass sources,
    pass 2), and the coverage declaration may name any of them. With the pick complete and the
    register acquired ok, a report naming the register (a comparison source) is accepted, records
    the audit incomplete with that reason, says LABELS LIMITED (no `new kind`), owes nothing for it
    and advances the slice files' baseline; a report naming a requirement file (CLAUDE.md) or the
    lifecycle page is accepted and records the audit incomplete, its labels not limited; naming
    wiki/log.md limits them; a path in no mandatory set is refused with slices.json unchanged.
    Pass 1 never sees a second-pass source: for every rotating part the reading list and the
    requirement files hold none of them. The requirement files follow the slice (CLAUDE.md for
    every slice, .claude/settings.json for the hooks and monitors, none listed apart in the
    standing rules' week, both being its files)."""
    world.record("standing-rules")
    world.set_audits([("standing-rules", "2026-10-11", 0)])
    vault = world.vault
    register, lifecycle, log_md = (world.path(rel) for rel in (REGISTER_REL, LIFECYCLE_REL,
                                                             LOG_REL))
    claude = world.path("vault/CLAUDE.md")
    world.write("vault/.claude/skills/alpha/SKILL.md", "# alpha, changed\n")   # its baseline moves
    manifest, out = world.pick(today=TODAY)
    data, result = load(manifest), parse(out)
    check(data["complete"] is True and data["slice"] == "skill:alpha"
          and status_of(data, "comparison source: the register") == "ok"
          and data["requirements"] == [claude] and result["requirements"] == [claude]
          and data["sources"] == [{"path": register, "comparison": True},
                                  {"path": lifecycle, "comparison": False},
                                  {"path": log_md, "comparison": True}],
          "the pick's mandatory inputs: %r %r %r" % (data["slice"], data["requirements"],
                                                     data["sources"]))
    saved, before = world.state_data(), digest(world.state)
    stray = world.path("vault/.claude/skills/beta/test_beta.py")   # in no mandatory set this week
    check(stray not in data["reading"] + data["requirements"]
          and saved["baseline"]["hashes"]["vault/.claude/skills/alpha/SKILL.md"]
          != data["hashes"]["vault/.claude/skills/alpha/SKILL.md"], "the fixture's premises")
    legs = ((register, True, "the second-pass source %s (pass 2), a comparison source" % register),
            (log_md, True, "the second-pass source %s (pass 2), a comparison source" % log_md),
            (lifecycle, False, "the second-pass source %s (pass 2)" % lifecycle),
            (claude, False, "the requirement file %s (pass 1)" % claude))
    for path, limited, reason in legs:
        world.set_state(saved)
        text = "# Report\n\n## Not read\n%s\nEND NOT READ: 1\n" % path
        code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest",
                                 manifest, "--report", world.report(text=text))
        stored = world.state_data()
        audit = stored["audits"][-1]
        check(code == 0 and audit["complete"] is False
              and audit["reasons"] == ["the reviewer did not read %s" % reason
                                       + (", so the audit's labels are limited" if limited
                                          else "")]
              and ("LABELS LIMITED: the reviewer did not read the comparison source(s) %s" % path
                   in out) == limited and ("LABELS LIMITED" in out) == limited
              and stored["owed"] == saved["owed"]
              and stored["baseline"]["hashes"]["vault/.claude/skills/alpha/SKILL.md"]
              == data["hashes"]["vault/.claude/skills/alpha/SKILL.md"],
              "naming %s: exit %d, the audit %r, owed %r: %s" % (path, code, audit,
                                                                 stored["owed"], out[:700]))
    world.set_state(saved)
    refused_unchanged(world, ("--record", data["slice"], "--findings", "0", "--manifest", manifest,
                              "--report", world.report(text="## Not read\n%s\nEND NOT READ: 1\n"
                                                       % stray)),
                      "nor one of its requirement files or second-pass sources", before)
    # pass 1 never sees a second-pass source, whatever the rotating part
    seen = []
    for number, name in enumerate(data["slices"]):
        world.set_audits([(other, "2026-10-%02d" % (1 + i), 0)
                          for i, other in enumerate(data["slices"]) if other != name])
        manifest, out = world.pick(today="2026-10-%d" % (19 + number))
        picked, result = load(manifest), parse(out)
        sources = [source["path"] for source in picked["sources"]]
        first_pass = picked["reading"] + picked["requirements"]
        check(picked["slice"] == name and not set(sources) & set(first_pass)
              and result["requirements"] == picked["requirements"]
              and (name == "register") == (register not in sources),
              "%s: pass 1 holds a second-pass source: %r" % (name, set(sources) & set(first_pass)))
        seen.append((name, [os.path.relpath(p, vault) for p in picked["requirements"]]))
    expected = dict((name, ["CLAUDE.md"]) for name in data["slices"])
    expected.update({"standing-rules": [], "hooks-and-monitors": ["CLAUDE.md",
                                                                  ".claude/settings.json"]})
    check(dict(seen) == expected, "the requirement files by slice: %r" % seen)


def case_named_groups_inline_hooks(world):
    """D18, item 6 (the held README's install step; the lifecycle register's review CR-LIFE,
    finding 1): NAMED_GROUPS holds the two hooks defined inline in .claude/settings.json under their
    lifecycle names, beside the reflection controls, so the install edits no code; each is listed
    as a missing named group while no row names it, and not once its row is back."""
    names = named_groups()
    check(names == ("reflection controls",
                    "experience pages (wiki/experience/; a group name)",
                    ),
          "NAMED_GROUPS: %r" % (names,))
    for name in names[1:]:
        world.lifecycle(world.every_item_row(skip=(name,)))
        result = parse(world.run()[1])
        check(result["missing"] == ["%s | named group" % name], "%s with no row: %r"
              % (name, result["missing"]))
    world.lifecycle(world.every_item_row())
    check(parse(world.run()[1])["missing"] == [], "the named groups with their rows")


def case_review_counterexamples(world):
    """The former failure cases, end to end on this build: CR-AUDIT10's F1 (a report whose two
    `## Not read` sections stand around list fences, the first owing a file, the second `none`)
    and F2 (around fence markers inside comments), each of which B-AUDIT10 recorded complete,
    discharging the debt and advancing the baseline, now refuse with slices.json byte for byte
    unchanged, while their controls (the list-fence and comment-fence reports with one section)
    record as written; CR-AUDIT10's lifecycle plant (a valid empty table, then a torn table between
    list fences, which B-AUDIT10 took for a complete pick) and its comment-fence form now leave the
    pick incomplete; and CR-AUDIT-B finding 1's counterexample and its list-fence counterpart in
    CLAUDE.md give the complete inventory, or, with the comment left open, UNKNOWN, never a
    successful partial one (section_adapter_projection holds the fixtures themselves)."""
    world.record("standing-rules")
    world.write("vault/wiki/developments/design.md", "# Design\n\nchanged this week\n")
    manifest, out = world.pick(today=TODAY)
    data = load(manifest)
    owed = world.path("vault/wiki/developments/design.md")
    check(owed in data["reading"], "the fixture's owed path")
    saved = world.state_data()
    for name, gap in (("F1, list fences", "- ```\n  ```\n\n"),
                      ("F2, fence markers inside comments", "<!--\n```\n-->\n\n")):
        report = (gap + "## Not read\n%s\nEND NOT READ: 1\n\n" % owed + gap + "## Not read\nnone\n"
                  "END NOT READ: 0\n")
        world.set_state(saved)
        refused_unchanged(world, ("--record", data["slice"], "--findings", "0", "--manifest",
                                  manifest, "--report", world.report(text=report)),
                          "holds 2 sections", digest(world.state))
        world.set_state(saved)
        code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest",
                                 manifest, "--report", world.report(
                                     text=gap + "## Not read\n%s\nEND NOT READ: 1\n" % owed))
        check(code == 0 and {"entry": "vault/wiki/developments/design.md", "since": TODAY}
              in world.state_data()["owed"], "%s, its control with one section: %d %s"
              % (name, code, out[:300]))
        world.set_state(saved)
    rows = world.every_item_row()
    front = "---\ntitle: Check lifecycle\n---\n\n# Check lifecycle\n\n"
    for number, (name, gap) in enumerate((("F1, list fences", "- ```\n  ```\n\n"),
                                          ("F2, comment fences", "<!--\n```\n-->\n\n"))):
        world.write(LIFECYCLE_REL, front + "\n".join([HEADER, SEPARATOR]) + "\n\n" + gap
                    + "\n".join([HEADER, SEPARATOR] + rows[:-1] + [rows[-1][:-4]]) + "\n\n"
                    + gap + LIFECYCLE_TAIL)
        manifest = world.manifest_path()
        code, out, _ = world.run("--manifest-out", manifest, today="2026-10-%d" % (19 + number))
        check(code == 3 and status_of(load(manifest), "lifecycle rows") == "unknown"
              and "DUE ROWS: UNKNOWN" in out, "the lifecycle plant, %s: exit %d: %s"
              % (name, code, out[-400:]))
    world.lifecycle(rows)
    with open(world.path("vault/CLAUDE.md"), encoding="utf-8") as handle:
        claude = handle.read()
    for number, (name, shape, complete) in enumerate((
            ("finding 1's counterexample", "<!--\n```\n-->\n## 4. New rule\nx\n<!--\n```\n-->\n",
             True),
            ("its list-fence counterpart", "- ```\n  ```\n\n## 4. New rule\nx\n- ```\n  ```\n",
             True),
            ("the counterexample with its first comment left open", "<!--\n```\n## 4. New rule\nx\n",
             False))):
        world.write("vault/CLAUDE.md", claude + "\n" + shape)
        manifest = world.manifest_path()
        code, out, _ = world.run("--manifest-out", manifest, today="2026-10-%d" % (23 + number))
        result = parse(out)
        if complete:
            check(code == 0 and "CLAUDE.md §4 | text group" in result["missing"]
                  and "sections read: CLAUDE.md 4" in result["controls"],
                  "%s: exit %d, missing %r" % (name, code, result["missing"]))
        else:
            check(code == 3 and status_of(load(manifest), "inventory") == "failed"
                  and "MISSING ROWS: UNKNOWN" in out
                  and "CLAUDE.md §4 | text group" not in result["missing"],
                  "%s: exit %d, missing %r: %s" % (name, code, result["missing"], out[-400:]))
    world.write("vault/CLAUDE.md", claude)


# CR-AUDIT13 F3's tables: another table, after a page's lifecycle table, whose first cell holds an
# escaped pipe (`a \| b`), its header of nine cells (an ordinary table) and of ten (a damaged
# lifecycle header), and their controls with no escaped pipe: (the table, its header's cells,
# whether a page holding it after a valid empty lifecycle table is whole), each written by hand.
ESCAPED_PIPE_TABLES = (
    ("| a \\| b | c | d | e | f | g | h | i | j |\n" + "|---" * 9 + "|\n", 9, True),
    ("| a \\| b | c | d | e | f | g | h | i | j | k |\n" + "|---" * 10 + "|\n", 10, False),
    ("| a b | c | d | e | f | g | h | i | j |\n" + "|---" * 9 + "|\n", 9, True),
    ("| a b | c | d | e | f | g | h | i | j | k |\n" + "|---" * 10 + "|\n", 10, False))


# The corpus on which slice.py's four raw protocols and this suite's readings of them must agree
# (D18, CR-AUDIT-B finding 3: supported-input disagreements fail acceptance): every shape the
# cases plant, put at a page's end and before the part its reader needs, each text cut after every
# whole line too.
def agreement_shapes():
    """The corpus's shapes (a function, since RAW_EXAMPLES is defined further down), CR-AUDIT13
    F3's escaped-pipe tables and their controls among them."""
    return tuple(shape for _, shape in FENCE_ENDINGS + COMMENT_SHAPES) + tuple(
        shape for shape, _, _ in ESCAPED_PIPE_TABLES) + (
        CLOSED_FENCES, RAW_EXAMPLES, "```text\n## Open\n```\n", "> ## Open\n", "## Closed\n",
        "##  Open \n", "## Open (12)\n", "##[2026-10-20] deep-lint | x\n",
        "## [2026-10-20] deep-lint\n", "### [2026-10-20] Deep Lint | x\n",
        "## [2026-10-20] deeplint | x\n",
        "## [2026-10-21] deep-lint | y\n- **Changed**: x\n- **Conflicts**: none\n",
        # CR-AUDIT11 F1: damaged latest headings whose kind still stands before the title, a list
        # marker before a heading (a deep-lint one, and a next one that must end the entry), and a
        # title alone naming deep-lint
        "## [2026-10-20 deep-lint | x\n", "## 2026/10/20 deep-lint | x\n",
        "## [2026-10-20] | deep-lint | x\n", "## deep-lint | x\n",
        "- ## [2026-10-20] deep-lint | x\n- **Changed**: x\n- **Conflicts**: none\n",
        "## [2026-10-21] deep-lint | y\n- **Changed**: x\n- ## [2026-10-21] ingest | z\n"
        "- **Conflicts**: none\n", "1. ## [2026-10-21] ingest | z\n",
        "## [2026-10-21] framework | deep-lint follow-ups\n",
        "- **Changed**: x\n- **Conflicts**: none\n", "- **Changed\n", "| x |\n", "> | x |\n",
        "\t| x |\n", HEADER.replace("| Guards ", "| Guarded ") + "\n" + SEPARATOR + "\n",
        "| a | b |\n|---|---|\n", "## Not read\nnone\nEND NOT READ: 0\n", "> ## Not read\n",
        "    ## Not read\n", "## not read (draft)\n", "END NOT READ: 0\n", "> END NOT READ: 1\n",
        "/end/not/read.md\n", "##\tNot\tread\n", "- ## Not Read\n", "## Notes: not read\n")


def agreement_corpus(base, anchor):
    """The base text with each agreement_shapes() shape at its end and just before `anchor`, the base
    itself, and every whole-line cut of each."""
    shapes = agreement_shapes()
    texts = [base] + [base + shape for shape in shapes]
    if anchor:
        check(base.count(anchor) == 1, "the corpus anchor %r" % anchor)
        texts += [base.replace(anchor, shape + anchor) for shape in shapes]
    cut = []
    for text in texts:
        parts = text.split("\n")
        cut += [prefix(parts, kept) for kept in range(len(parts))]
    return texts + cut


def case_protocols_agree_with_reference(world):
    """D18, item 5, and CR-AUDIT-B finding 3: slice.py's four raw protocols (parse_not_read,
    parse_lifecycle, register_problem, deeplint_entry) and this suite's readings of them
    (structure_problem, written apart, in another shape, with no fence or comment filtering) give
    the same verdict, whole or not, on every input of the corpus (agreement_corpus over the
    fixture's register, log, lifecycle page and two reports, each agreement_shapes() shape at the end
    and before the part read, and every whole-line cut of each). A disagreement fails the case. The
    control: the corpus holds inputs of both verdicts for every protocol, so neither reading can pass
    it by agreeing on one answer."""
    module = load_slice()
    rows = [row(".claude/hooks/gate.py", kind="hook", next_review="2026-10-04")]
    lifecycle = ("---\ntitle: Check lifecycle\n---\n\n# Check lifecycle\n\n"
                 + "\n".join([HEADER, SEPARATOR] + rows) + "\n" + LIFECYCLE_TAIL)
    paths = ["/v/a.md", "/v/b.md", "/end/not/read.md"]

    def production(kind, text):
        lines = module.text_lines(text)
        if kind == "register":
            return module.register_problem(lines) is None
        if kind == "lifecycle":
            _, tables, damage = module.parse_lifecycle(lines)
            return tables > 0 and not damage
        if kind == "log":
            start, _, _, problem = module.deeplint_entry(lines)
            return start is not None and problem is None
        return module.parse_not_read(text, paths)[1] is None
    corpora = (("register", REGISTER_TEXT, "## Closed\n"), ("log", LOG_TEXT,
                                                            "## [2026-10-02] deep-lint | second\n"),
               ("lifecycle", lifecycle, HEADER),
               ("report", "# Report\n\n## Gaps\nnone\n\n## Not read\n/v/a.md\nEND NOT READ: 1\n",
                "## Not read\n"), ("report", "# Report\n\n" + NONE_READ, "## Not read\n"))
    for kind, base, anchor in corpora:
        verdicts, disagree = set(), []
        for text in agreement_corpus(base, anchor):
            mine, theirs = production(kind, text), structure_problem(kind, text) is None
            verdicts.add(mine)
            if mine != theirs:
                disagree.append((text[-160:], mine, structure_problem(kind, text)))
        check(not disagree, "%s: slice.py and this suite's reading disagree on %d input(s), the "
              "first %r" % (kind, len(disagree), disagree[:1]))
        check(verdicts == {True, False}, "the control: the %s corpus holds one verdict only %r"
              % (kind, verdicts))


def case_texts_one_set_of_rules(world):
    """D18, item 5, and CR-AUDIT-B finding 3's last sentence: the production contract (slice.py's
    docstring and its protocols' own), the report template (brief-audit.md), the procedure
    (AUDIT.md) and the tests state the same rules. AUDIT.md's Reading protocols section names the
    five readings, and each states, as slice.py does, what a record is, what makes it whole and
    torn, and how an example is read; the coverage's one-declaration rule, its once-each line in the
    brief, and its refusal in AUDIT.md's step 10 agree; the requirement files and second-pass
    sources are nameable in all three; markdown-it-py 4.2.0 is named as the section reader alone,
    with UNKNOWN for what it cannot decide, in the code, the procedure and the install; and no text
    still promises a fence or a comment closed or interpreted by hand. CR-AUDIT11's fold: the
    deep-lint heading in any form (its kind before its title), the absent requirement file listed
    with the pick incomplete, the register a comparison source in its own week, the recovery naming
    every mandatory input, and the second-pass sources kept from every list, each stated alike.
    CR-AUDIT12's fold: the requirement file's role judged apart from whatever lists its path, the
    printed paths in the spelling given and the debt's key whatever that spelling, and a retired
    row needing no Next review, its other checks staying, each stated alike. CR-AUDIT13's fold: an
    owed entry's files held for the second pass counted among its files, one of them named keeping
    the entry owed and its earlier hash, stated alike in the code, the procedure and the brief's
    spawner notes. CR-AUDIT14's fold: the record refusing any slice other than the one its
    manifest's pick chose, before anything is committed and naming that slice, stated alike in the
    code and the procedure (the brief names no slice to record)."""
    source = read_text(SLICE)
    audit, brief = read_text(AUDIT_MD), read_text(BRIEF_MD)
    flat_audit, flat_brief, flat_source = flat(audit), flat(brief), flat(source)
    protocols = audit_sections().get("Reading protocols", "")
    for name in ("**The reviewer's coverage section**", "**The lifecycle tables**",
                 "**The register**", "**Deep-lint's latest entry**",
                 "**The section lists of CLAUDE.md and CUSTOMISATION.md**"):
        check(name in protocols, "AUDIT.md's Reading protocols lack %s" % name)
    check(all(word in flat(protocols) for word in ("Whole", "Torn", "Examples", "record")),
          "AUDIT.md's protocols do not each say what a record is, whole, torn and an example")
    for function in ("parse_not_read", "parse_lifecycle", "register_problem", "deeplint_entry",
                     "standing_sections"):
        doc = flat(ast.get_docstring(next(node for node in ast.walk(ast.parse(source))
                                          if isinstance(node, ast.FunctionDef)
                                          and node.name == function)) or "")
        check(all(word in doc for word in ("Whole", "Examples")) or function == "standing_sections"
              and "declared supported syntax" in doc, "%s's docstring states no protocol"
              % function)
    pairs = (
        ("exactly one such line in the whole report is required, and it must be exactly "
         "`## Not read`", flat_audit),
        ("Exactly one is required, and it must be exactly `## Not read`", flat_source),
        ("Write the heading `## Not read` and the `END NOT READ` line once each, there and nowhere "
         "else in your report", flat_brief),
        ("a report in which a second line declares `## Not read` or reads as a closing line, "
         "wherever it stands", flat_audit),
        ("name too each requirement file and each step-6 source you did not read in full",
         flat_brief),
        ("A requirement file or a second-pass source named there is owed nothing and is a reason "
         "the audit is incomplete", flat_audit),
        ("a requirement file or a second-pass source named is no debt", flat_source),
        ("the REQUIREMENT FILES block", flat_brief), ("the REQUIREMENT FILES block", flat_audit),
        ("markdown-it-py 4.2.0", flat_audit), ("markdown-it-py 4.2.0", flat_source),
        ("never a fallback to another reader", flat_audit),
        ("no other reader ever stands in for it", flat_source),
        ("no older entry is read in its place", flat_source),
        ("no older entry is ever read", flat_audit),
        ("a damaged lifecycle header", flat_audit), ("a damaged lifecycle header", flat_source),
        # CR-AUDIT11's fold: the deep-lint heading in any form (F1), an absent requirement file
        # (F2), the comparison sources whatever their phase and the recovery's every mandatory
        # input (F3), and the second-pass sources held from every list contributor (F4)
        ("standing before the heading's first `|` or as its first word", flat_audit),
        ("standing before the heading's first `|`, or as its first word", flat_source),
        ("A requirement file of the slice that is absent at the pick stays listed", flat_audit),
        ("one absent at the pick listed too, the pick incomplete", flat_source),
        ("One absent at the pick is still listed", flat_brief),
        ("in its own week the register is a reading-list file, owed when named like any other, "
         "and still a comparison source", flat_audit),
        ("whichever pass reads it, the register in its own week included", flat_source),
        ("the register in its own week too, where it is a reading-list path", flat_brief),
        ("names every mandatory input of the pick", flat_audit),
        ("never enter the reading list or the requirement files, whatever names them",
         flat_audit),
        ("never enter the reading list or the requirement files", flat_source),
        # CR-AUDIT12's fold: a requirement file's role judged apart from what lists its path
        # (F1), the caller's spelling and the debt's key whatever the spelling (F3), and the
        # head's choice that a retired row needs no Next review
        ("its role judged apart from what lists its path", flat_source),
        ("whatever else lists its path: when the reading list holds it already", flat_audit),
        ("When the reading list holds its path already", flat_brief),
        ("a due row's files too, never by their real path", flat_source),
        ("Every path the pick prints is spelled under the roots as they were given", flat_audit),
        ("whatever spelling of the root the pick or the record was given", flat_source),
        ("A file is kept by its place under its root, whatever spelling of the vault's path the "
         "pick or the record was given", flat_audit),
        ("A whole row with no Next review (a retired row excepted)", flat_source),
        ("A retired row is never due, so it needs no Next review; its other checks stay",
         flat_audit),
        # CR-AUDIT13's fold: an owed entry's files held for the second pass count among its files
        # (F2)
        ("its files held for the second pass included. An entry's files are found before the held "
         "sources leave the reading list", flat_source),
        ("one named under `## Not read` keeps the entry owed and its own earlier hash, whatever "
         "the week's phase", flat_source),
        ("the reviewer read all of it, its files held for the second pass included: one of them "
         "named under `## Not read` keeps the entry owed and that file's earlier hash, whatever "
         "the week's phase", flat_audit),
        ("the entry stays owed when the report names one of them", flat_audit),
        ("a step-6 source that an earlier audit's owed entry holds (the register under an owed "
         "folder, say) keeps that entry owed when named", flat_brief),
        # CR-AUDIT14's fold: the record credits only the slice its manifest's pick chose (F1)
        ("It refuses as well, before anything is committed, any slice other than the one the "
         "manifest's pick chose, and names that slice", flat_source),
        ("the rotation counts as attempted only the slice the manifest represents", flat_source),
        ("The record refuses any other slice before anything is written, and names the "
         "manifest's", flat_audit),
        ("the rotation counts as attempted only the slice the manifest represents", flat_audit),
        ("an unknown slice, or any slice other than the one the manifest's pick chose (the line "
         "names that slice)", flat_audit))
    for phrase, text in pairs:
        check(phrase in text, "a text lacks %r" % phrase)
    for text, name in ((flat_audit, "AUDIT.md"), (flat_brief, "brief-audit.md")):
        for promise in ("every fence closed", "a comment is read as text", "closed fences",
                        "fence left open fails"):
            check(promise not in text, "%s still says %r" % (name, promise))
    check("outside_fences" not in source and "FENCE_RE" not in source,
          "slice.py still holds its fence reader")


# ------------------------------------------------------------------ CR-AUDIT11's findings -----

def case_deeplint_latest_heading_damaged(world):
    """CR-AUDIT11 F1 (D18's area `Raw lifecycle, register and log`: a malformed latest deep-lint
    entry cannot disappear or trigger fallback to older evidence, and required fields cannot be
    borrowed across raw entry boundaries). The review's own text (an entry of 2026-10-01, then a
    latest heading whose bracket is left open), which B-AUDIT11 read as the older entry, gives the
    damaged heading, malformed, never the older one, and this suite's own reading rejects it too.
    In the fixture's log a latest deep-lint heading damaged so that its kind still stands before its
    title (its bracket left open, a date in another shape, a stray `|` before its kind, no date, a
    list marker before it) is the latest heading and fails the acquisition: the pick incomplete
    (exit 3) with LABELS LIMITED, the older entry of 2026-10-02 never read in its place, and the
    record incomplete with LABELS LIMITED. An entry ends at a line that begins with `#` after any
    container prefix, list markers included, so a next heading behind a list marker (or an ordered
    one) lends its Conflicts field to no entry before it. The controls: the intact log, a later
    entry of another kind whose title names deep-lint, and a later whole entry each give a complete
    pick with the right entry and no limit, this suite's reading agreeing; the log restored after
    the damaged ones gives a complete pick again."""
    module = load_slice()
    review = ("## [2026-10-01] deep-lint | old\n- **Changed**: old\n- **Conflicts**: none\n"
              "## [2026-10-02 deep-lint | latest\n")
    got = module.deeplint_entry(module.text_lines(review))
    check(got[0] == 4 and got[2] is None and got[3] is not None,
          "the review's text: deeplint_entry gives %r; its damaged latest heading, line 4, "
          "malformed, expected, never the older entry" % (got,))
    check(structure_problem("log", review) is not None,
          "this suite's reading accepts the review's text")
    world.record("standing-rules")
    with open(world.path(LOG_REL), encoding="utf-8") as handle:
        log_text = handle.read()
    fields = "- **Changed**: e\n- **Conflicts**: none\n"
    controls = (
        ("the intact log", "", "the deep-lint entry of 2026-10-02"),
        ("a later entry of another kind whose title names deep-lint",
         "## [2026-10-13] framework | deep-lint follow-ups\n- **Changed**: f\n"
         "- **Conflicts**: none\n", DEEPLINT_LINES),
        ("a later whole entry", "## [2026-10-12] deep-lint | later\n" + fields,
         "log.md lines 20-22 (the deep-lint entry of 2026-10-12)"))
    damaged = (
        ("its bracket left open (the review's plant)",
         "## [2026-10-12 deep-lint | latest\n" + fields),
        ("a date in another shape", "## 2026/10/12 deep-lint | latest\n" + fields),
        ("a stray `|` before its kind", "## [2026-10-12] | deep-lint | latest\n" + fields),
        ("no date", "## deep-lint | latest\n" + fields),
        ("a list marker before it", "- ## [2026-10-12] deep-lint | latest\n" + fields),
        ("its Conflicts field after a next heading behind a list marker (the review's boundary "
         "probe)", "## [2026-10-12] deep-lint | latest\n- **Changed**: e\n"
         "- ## [2026-10-13] ingest | y\n- **Conflicts**: none\n"),
        ("its Conflicts field after a next heading behind an ordered-list marker",
         "## [2026-10-12] deep-lint | latest\n- **Changed**: e\n1. ## [2026-10-13] ingest | y\n"
         "- **Conflicts**: none\n"))
    day = datetime.date(2026, 10, 19)
    try:
        for name, tail, expected in controls:
            text = log_text + ("\n" + tail if tail else "")
            check(structure_problem("log", text) is None, "this suite's reading refuses the "
                  "control, %s: %s" % (name, structure_problem("log", text)))
            world.write(LOG_REL, text)
            manifest = world.manifest_path()
            code, out, _ = world.run("--manifest-out", manifest, today=day.isoformat())
            day += datetime.timedelta(days=1)
            check(code == 0 and load(manifest)["complete"] is True and expected in out
                  and "LABELS LIMITED" not in out,
                  "the control, %s: exit %d: %s" % (name, code, out[-500:]))
        for number, (name, tail) in enumerate(damaged):
            text = log_text + "\n" + tail
            check(structure_problem("log", text) is not None, "this suite's reading accepts a log "
                  "whose latest deep-lint entry has %s" % name)
            world.write(LOG_REL, text)
            manifest = world.manifest_path()
            code, out, _ = world.run("--manifest-out", manifest, today=day.isoformat())
            data = load(manifest)
            check(code == 3 and data["complete"] is False and data["labels_limited"] is True
                  and status_of(data, "comparison source: deep-lint") == "failed"
                  and "LABELS LIMITED" in out and "the deep-lint entry of 2026-10-02" not in out,
                  "a latest deep-lint entry with %s: exit %d, complete %r, limited %r: %s"
                  % (name, code, data["complete"], data["labels_limited"], out[-700:]))
            if number in (0, 5):   # the review's two probes, each recorded too
                out = world.record(data["slice"], today=day.isoformat(), manifest=manifest)
                check(world.state_data()["audits"][-1]["complete"] is False
                      and "LABELS LIMITED" in out, "%s: the record: %s" % (name, out[:500]))
            day += datetime.timedelta(days=1)
    finally:
        world.write(LOG_REL, log_text)
    code, out, _ = world.run(today=day.isoformat())
    check(code == 0 and "the deep-lint entry of 2026-10-02" in out and "LABELS LIMITED" not in out,
          "the log restored: exit %d: %s" % (code, out[-400:]))


def case_absent_requirement_incomplete(world):
    """CR-AUDIT11 F2 (D18 item 4: coverage includes every mandatory requirement file, and finding
    2's omissions are representable and prevent completion). In the hooks-and-monitors week the
    slice's requirement file `.claude/settings.json`, absent at the pick (no file at its path, the
    hash scan's walk of `.claude/` read whole), stays among the manifest's requirement files and in
    the REQUIREMENT FILES block, and the pick is incomplete (exit 3): its `requirement files`
    acquisition returns unknown, named in the INCOMPLETE block, with no label limit and nothing
    unread. A report naming the file under `## Not read` is accepted and records the audit
    incomplete with that reason and the pick's; one saying `none` records it incomplete too, with
    the pick's reason. Neither owes anything for it (no slice debt for a requirement-only
    omission). The control: the file restored, the pick completes with it listed, and `none`
    records the audit complete."""
    world.record("standing-rules")
    world.set_audits([(s, "2026-10-11", 0) for s in ("standing-rules", "skill:alpha",
                                                     "skill:beta", "register", "tools")])
    settings, claude = world.path("vault/.claude/settings.json"), world.path("vault/CLAUDE.md")
    with open(settings, encoding="utf-8") as handle:
        kept = handle.read()
    os.remove(settings)
    manifest = world.manifest_path()
    code, out, _ = world.run("--manifest-out", manifest)
    data, result = load(manifest), parse(out)
    short = [(a["name"], a["status"]) for a in data["acquisitions"] if a["status"] != "ok"]
    check(data["slice"] == "hooks-and-monitors", "the fixture picked %s" % data["slice"])
    check(code == 3 and data["complete"] is False and data["requirements"] == [claude, settings]
          and result["requirements"] == [claude, settings] and data["labels_limited"] is False
          and data["unread"] == [] and short == [("requirement files", "unknown")]
          and any(line.startswith("requirement files: unknown: ") and settings in line
                  for line in result["incomplete"]),
          "the pick with %s absent: exit %d, complete %r, requirements %r, short %r: %s"
          % (settings, code, data["complete"], data["requirements"], short, out[-700:]))
    saved = world.state_data()
    pick_reason = ("its pick was incomplete: 1 acquisition(s) did not succeed (requirement files: "
                   "unknown)")
    record = ("--record", "hooks-and-monitors", "--findings", "0", "--manifest", manifest)
    for name, report, reasons in (
            ("naming it", "# Report\n\n## Not read\n%s\nEND NOT READ: 1\n" % settings,
             [pick_reason, "the reviewer did not read the requirement file %s (pass 1)"
              % settings]),
            ("saying none", None, [pick_reason])):
        world.set_state(saved)
        code, out, _ = world.run(*(record + ("--report", world.report(text=report))))
        stored = world.state_data()
        audit = stored["audits"][-1]
        check(code == 0 and audit["complete"] is False and audit["reasons"] == reasons
              and stored["owed"] == saved["owed"] and "LABELS LIMITED" not in out,
              "the record %s: exit %d, the audit %r, owed %r: %s"
              % (name, code, audit if code == 0 else None, stored["owed"], out[:600]))
    world.write("vault/.claude/settings.json", kept)
    world.set_state(saved)
    manifest = world.manifest_path()
    code, out, _ = world.run("--manifest-out", manifest)
    data = load(manifest)
    check(code == 0 and data["complete"] is True and data["requirements"] == [claude, settings]
          and parse(out)["requirements"] == [claude, settings],
          "the control, the file restored: exit %d, complete %r: %s" % (code, data["complete"],
                                                                        out[-500:]))
    code, out, _ = world.run("--record", "hooks-and-monitors", "--findings", "0", "--manifest",
                             manifest, "--report", world.report())
    audit = world.state_data()["audits"][-1]
    check(code == 0 and audit["complete"] is True and audit["reasons"] == [],
          "the control's record: exit %d, the audit %r: %s" % (code, audit, out[:400]))


def recovery_section(out):
    """The `## Not read` section AUDIT.md's step 10 prescribes when a report's own section is
    missing or unclear, built from a pick's printed output as the head builds it: every path line
    of its READING LIST and REQUIREMENT FILES blocks, as printed, and the path on each `- ` line of
    its SECOND-PASS SOURCES block, closed by its count."""
    paths, block = [], None
    for line in out.split("\n"):
        if line.startswith("READING LIST ("):
            block = "reading"
        elif line.startswith("REQUIREMENT FILES ("):
            block = "requirements"
        elif not line:
            block = None
        elif block and line.startswith(("/", ESCAPED_MARK)):
            paths.append(line)
    paths += printed_sources(out)
    return "## Not read\n%s\nEND NOT READ: %d\n" % ("\n".join(paths), len(paths))


def entry_of(world, path):
    """The owed entry a record makes for a reading-list path: its hash key, `<root>/<path below
    it>`, whether the path is spelled under the root as given or through its real path (the
    record's key_for finds the key either way: CR-AUDIT12 F3)."""
    for label, base in (("vault", world.vault), ("tools", world.tools), ("hooks", world.hooks)):
        for top in (base, os.path.realpath(base)):
            if path.startswith(top + os.sep):
                return label + "/" + os.path.relpath(path, top).replace(os.sep, "/")
    return path


def case_comparison_status_any_phase(world):
    """CR-AUDIT11 F3 (D18 item 4: an unread comparison source limits novelty labels regardless of
    its successful acquisition at pick time, each mandatory input retaining its assigned phase).
    The register is a comparison source whatever its phase. In its own week it is a reading-list
    file (pass 1), changed since the baseline: a report naming it is accepted, keeps its slice debt
    (owed, its earlier hash kept), records the audit incomplete with the count's reason and the
    comparison's, and says LABELS LIMITED, as in an ordinary week, where it is a second-pass source;
    the manifest names it among its comparison sources in both. The recovery AUDIT.md's step 10
    prescribes for a section missing or unclear names every mandatory input, each as the pick
    printed it (the procedure's text says so); applied to an ordinary pick's printed output, it
    records the audit incomplete with a reason for every omission (the reading list's count, each
    requirement file, each second-pass source), says LABELS LIMITED and owes the whole reading list.
    The control: an ordinary `none` declaration still records the audit complete."""
    world.record("standing-rules")
    register, log_md = world.path(REGISTER_REL), world.path(LOG_REL)
    key = "vault/wiki/developments/known-issues.md"
    old = world.state_data()["baseline"]["hashes"][key]
    world.write(REGISTER_REL, REGISTER_TEXT.replace("- entry\n", "- entry, changed\n"))
    world.set_audits([(s, "2026-10-11", 0) for s in ("standing-rules", "skill:alpha", "skill:beta",
                                                     "hooks-and-monitors", "tools")])
    manifest, _ = world.pick(today=TODAY)
    data = load(manifest)
    check(data["slice"] == "register" and data["complete"] is True
          and data["reading"].count(register) == 1
          and register not in [s["path"] for s in data["sources"]],
          "the register's week: slice %s, complete %r" % (data["slice"], data["complete"]))
    code, out, _ = world.run("--record", "register", "--findings", "0", "--manifest", manifest,
                             "--report", world.report(text="# Report\n\n## Not read\n%s\n"
                                                      "END NOT READ: 1\n" % register))
    stored = world.state_data()
    audit = stored["audits"][-1] if code == 0 else None
    check(code == 0 and audit["complete"] is False
          and audit["reasons"] == ["the reviewer did not read 1 file(s)",
                                   "the reviewer did not read the comparison source %s (pass 1, "
                                   "on this audit's reading list), so the audit's labels are "
                                   "limited" % register]
          and "LABELS LIMITED: the reviewer did not read the comparison source(s) %s" % register
          in out and {"entry": key, "since": TODAY} in stored["owed"]
          and stored["baseline"]["hashes"][key] == old,
          "the register named in its own week: exit %d, the audit %r, owed %r: %s"
          % (code, audit, stored["owed"], out[:700]))
    check(data.get("comparison") == [register, log_md], "the register's week: the manifest's "
          "comparison sources %r" % (data.get("comparison"),))
    # an ordinary week: the register a second-pass source, a comparison source as before (marked
    # attempted, since its kept hash makes it changed, which would win it the tie)
    world.set_audits([("standing-rules", "2026-10-11", 0), ("register", "2026-10-11", 0)])
    manifest, pick_out = world.pick(today="2026-10-19")
    data = load(manifest)
    saved = world.state_data()
    check(data["slice"] == "skill:alpha" and data["complete"] is True
          and data.get("comparison") == [register, log_md]
          and [s["path"] for s in data["sources"]] == [register, world.path(LIFECYCLE_REL), log_md],
          "an ordinary week: slice %s, comparison %r" % (data["slice"], data.get("comparison")))
    code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest", manifest,
                             "--report", world.report(text="# Report\n\n## Not read\n%s\n"
                                                      "END NOT READ: 1\n" % register),
                             today="2026-10-19")
    audit = world.state_data()["audits"][-1]
    check(code == 0 and audit["reasons"] == ["the reviewer did not read the second-pass source %s "
                                             "(pass 2), a comparison source, so the audit's labels "
                                             "are limited" % register]
          and "LABELS LIMITED: the reviewer did not read the comparison source(s) %s" % register
          in out and world.state_data()["owed"] == saved["owed"],
          "the register named in an ordinary week: exit %d: %s" % (code, out[:600]))
    # the recovery of step 10, as AUDIT.md prescribes it, applied to the pick's printed output
    step10 = audit_steps().get(10, "")
    check("record from a copy whose `## Not read` section names every mandatory input of the pick"
          in step10 and "lists every reading-list file, closed by its count" not in step10,
          "AUDIT.md's step 10 recovery does not name every mandatory input: %r"
          % step10[step10.find("When the section is missing"):][:400])
    world.set_state(saved)
    code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest", manifest,
                             "--report", world.report(text="# Report\n\n"
                                                      + recovery_section(pick_out)),
                             today="2026-10-19")
    stored = world.state_data()
    audit = stored["audits"][-1] if code == 0 else None
    reasons = (["the reviewer did not read %d file(s)" % len(data["reading"])]
               + ["the reviewer did not read the requirement file %s (pass 1)" % path
                  for path in data["requirements"]]
               + ["the reviewer did not read the second-pass source %s (pass 2)%s"
                  % (s["path"], ", a comparison source, so the audit's labels are limited"
                     if s["comparison"] else "") for s in data["sources"]])
    owed = [e["entry"] for e in stored["owed"]]
    check(code == 0 and audit["complete"] is False and audit["reasons"] == reasons
          and "LABELS LIMITED" in out and data["reading"] and data["requirements"]
          and all(entry_of(world, path) in owed for path in data["reading"]),
          "the recovery: exit %d, the audit %r, owed %r: %s" % (code, audit, owed, out[:700]))
    world.set_state(saved)
    code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest", manifest,
                             "--report", world.report(), today="2026-10-19")
    audit = world.state_data()["audits"][-1]
    check(code == 0 and audit["complete"] is True and audit["reasons"] == []
          and "LABELS LIMITED" not in out, "the control, `none`: exit %d: %s" % (code, out[:400]))


def case_log_never_in_pass_one(world):
    """CR-AUDIT11 F4 (D18 item 4: neither change exposes second-pass sources during pass 1, each
    mandatory input retaining its assigned phase). No contributor to the reading list puts a
    second-pass source into pass 1. Due lifecycle rows naming wiki/log.md, the `wiki` folder (whose
    walk holds the log, the register and the lifecycle page), the register and the lifecycle page
    leave the log, the lifecycle page and (in an ordinary week) the register off the reading list
    and the requirement files, the log staying a second-pass source and the folder's other file
    listed; an owed entry naming the log (an absolute path, as a record owes a path outside the
    hashed roots) leaves it off too. Each pick's manifest is accepted by its recorder (a `none`
    report records it, exit 0). The register's slice-week exception holds: in its own week the due
    row naming it leaves it on the reading list once, the log and the lifecycle page still off.
    Paths are compared by their real paths, so that a source reached by any spelling counts
    (B-AUDIT11 listed a due row's files by their real path, the sources by the vault's spelling,
    which differ wherever the vault's path passes through a link, as macOS puts /tmp behind one;
    since CR-AUDIT12 F3 every list keeps the spelling given). The world is built under its root's
    real path, as on the live vault, so that the recorder's own check of its manifest (no source on
    the reading list, compared by spelling) bites as it would there."""
    world = World(os.path.join(os.path.realpath(world.root), "real"))
    world.record("standing-rules")
    real = os.path.realpath
    log_md, register, lifecycle = (real(world.path(rel)) for rel in (LOG_REL, REGISTER_REL,
                                                                     LIFECYCLE_REL))
    design = real(world.path("vault/wiki/developments/design.md"))
    world.lifecycle(world.every_item_row() + [
        row(item, kind="text", next_review="2026-10-04")
        for item in ("wiki/log.md", "wiki", "wiki/developments/known-issues.md",
                     "wiki/developments/check-lifecycle.md")])
    weeks = (("an ordinary week", [("standing-rules", "2026-10-11", 0)], TODAY),
             ("the register's week", [(s, "2026-10-11", 0) for s in (
                 "standing-rules", "skill:alpha", "skill:beta", "hooks-and-monitors", "tools")],
              "2026-10-19"))
    for week, audits, today in weeks:
        world.set_audits(audits)
        manifest = world.manifest_path()
        code, out, _ = world.run("--manifest-out", manifest, today=today)
        data = load(manifest)
        first_pass = [real(p) for p in data["reading"] + data["requirements"]]
        own = data["slice"] == "register"
        check(code == 0 and data["complete"] is True and own == (week == "the register's week")
              and log_md not in first_pass and lifecycle not in first_pass
              and first_pass.count(register) == (1 if own else 0) and design in first_pass
              and log_md in [real(s["path"]) for s in data["sources"]],
              "%s: exit %d, slice %s; the log, the lifecycle page and the register in pass 1: %r"
              % (week, code, data["slice"], [p for p in first_pass
                                             if p in (log_md, lifecycle, register)]))
        code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest",
                                 manifest, "--report", world.report(), today=today)
        check(code == 0, "%s: the recorder refused its own pick's manifest: %s" % (week, out[:400]))
    world.lifecycle(world.every_item_row())
    world.set_audits([("standing-rules", "2026-10-11", 0)])
    state = world.state_data()
    state["owed"] = [{"entry": world.path(LOG_REL), "since": "2026-10-11"}]
    world.set_state(state)
    manifest = world.manifest_path()
    code, out, _ = world.run("--manifest-out", manifest, today="2026-10-20")
    data = load(manifest)
    first_pass = [real(p) for p in data["reading"] + data["requirements"]]
    check(code == 0 and log_md not in first_pass
          and [o["entry"] for o in data["owed"]] == [world.path(LOG_REL)],
          "an owed entry naming the log: exit %d, the log in pass 1 %r: %s"
          % (code, log_md in first_pass, out[-500:]))
    code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest", manifest,
                             "--report", world.report(), today="2026-10-20")
    check(code == 0, "an owed entry naming the log: the recorder refused its own pick's manifest: "
          "%s" % out[:400])


# ------------------------------------------------------------------ CR-AUDIT12's findings -----

def hooks_week(world):
    """The hooks-and-monitors slice next in line: every other rotating part attempted."""
    world.set_audits([(s, "2026-10-11", 0) for s in ("standing-rules", "skill:alpha",
                                                     "skill:beta", "register", "tools")])


def case_requirement_role_apart(world):
    """CR-AUDIT12 F1 (D18 item 4; CR-AUDIT11 F2's overturn: the absent requirement prevents
    completion whether it appears among the requirement files or on the reading list). A
    requirement file's role is judged apart from every route by which the same path reaches the
    reading list. In the hooks-and-monitors week `.claude/settings.json` reaches it:
    - as an owed deletion (the review's route: owed from an earlier audit, deleted since its
      baseline): the pick is incomplete (exit 3), its `requirement files` acquisition unknown and
      named in the INCOMPLETE block, the path once on the reading list, in the deleted part, with a
      note, and not repeated among the requirement files. The deletion keeps its rules: a `none`
      report records the audit incomplete with the pick's reason, discharges the deletion and
      records the path absent; a report naming it records the audit incomplete and keeps it owed,
      with its earlier hash. The next pick, nothing owed, lists the absent file among the
      requirement files, still incomplete. The control: the file restored (still owed), the pick
      and a `none` record complete;
    - by a due row: one naming the file lists it in the due part, its role ok and the pick
      complete (the control), and with the file absent the row finds nothing, the file is listed
      among the requirement files and the pick is incomplete; one naming a folder that holds a
      link to the file lists the link, whose real path is the file's: the role ok while the file
      is there, unknown when it is absent;
    - by the rotating part: a link to the file in the vault's hooks folder is on the list in the
      rotating part, the role ok while the file is there, unknown when it is absent.
    No pick owes anything for the role itself."""
    world.record("standing-rules")
    hooks_week(world)
    settings, claude = world.path("vault/.claude/settings.json"), world.path("vault/CLAUDE.md")
    key, real = "vault/.claude/settings.json", os.path.realpath(settings)
    with open(settings, encoding="utf-8") as handle:
        kept = handle.read()
    clean = world.state_data()
    reason = ("its pick was incomplete: 1 acquisition(s) did not succeed (requirement files: "
              "unknown)")

    def role_pick(label, part, absent, today=TODAY):
        """A pick of the hooks week, checked: its requirement role unknown exactly when the file
        is absent, never owed, and the file's real path once on the reading list, in `part`, and
        not among the requirement files, or (no part) among them and off the list."""
        manifest = world.manifest_path()
        code, out, _ = world.run("--manifest-out", manifest, today=today)
        data, result = load(manifest), parse(out)
        role = status_of(data, "requirement files")
        held = [p for p in data["reading"] if os.path.realpath(p) == real]
        there = [p for p in result["parts"].get(part, []) if os.path.realpath(p) == real]
        check(data["slice"] == "hooks-and-monitors" and role == ("unknown" if absent else "ok")
              and any(line.startswith("requirement files: unknown: ") and settings in line
                      for line in result["incomplete"]) == absent
              and key not in data["unread"]
              and (len(held) == len(there) == 1 and data["requirements"] == [claude]
                   and result["requirements"] == [claude] if part
                   else not held and data["requirements"] == [claude, settings]),
              "%s: exit %d, slice %s, requirement files %s, on the reading list %r, requirements "
              "%r: %s" % (label, code, data["slice"], role, held, data["requirements"],
                          out[-700:]))
        return manifest, out, code, data

    # the review's route: an owed deletion
    world.set_state(dict(clean, owed=[{"entry": key, "since": "2026-10-11"}]))
    os.remove(settings)
    manifest, out, code, data = role_pick("an owed deletion, the file absent", "deleted", True)
    check(code == 3 and data["complete"] is False
          and [(a["name"], a["status"]) for a in data["acquisitions"] if a["status"] != "ok"]
          == [("requirement files", "unknown")]
          and data["owed"] == [{"entry": key, "files": [settings], "held": [], "acquired": True,
                                "deleted": True}]
          and "note: the requirement file %s is absent at this pick: the reading list holds it "
          "already, where it stays" % settings in out,
          "an owed deletion: exit %d, complete %r, owed %r: %s" % (code, data["complete"],
                                                                   data["owed"], out[-700:]))
    saved = world.state_data()
    record = ("--record", "hooks-and-monitors", "--findings", "0", "--manifest", manifest)
    code, out, _ = world.run(*(record + ("--report", world.report())))
    after_none = world.state_data()
    audit = after_none["audits"][-1] if code == 0 else None
    check(code == 0 and audit["complete"] is False and audit["reasons"] == [reason]
          and after_none["owed"] == [] and key not in after_none["baseline"]["hashes"],
          "an owed deletion, `none`: exit %d, the audit %r, owed %r: %s"
          % (code, audit, after_none["owed"], out[:600]))
    world.set_state(saved)
    code, out, _ = world.run(*(record + ("--report", world.report(
        text="# Report\n\n## Not read\n%s\nEND NOT READ: 1\n" % settings))))
    stored = world.state_data()
    audit = stored["audits"][-1] if code == 0 else None
    check(code == 0 and audit["complete"] is False
          and audit["reasons"] == [reason, "the reviewer did not read 1 file(s)"]
          and stored["owed"] == saved["owed"]
          and stored["baseline"]["hashes"].get(key) == saved["baseline"]["hashes"][key],
          "an owed deletion, named: exit %d, the audit %r, owed %r: %s"
          % (code, audit, stored["owed"], out[:600]))
    world.set_state(after_none)
    hooks_week(world)
    _, out, code, data = role_pick("the next pick, nothing owed, the file absent", None, True,
                                   today="2026-10-25")
    check(code == 3 and data["complete"] is False, "the next pick: exit %d" % code)
    world.write("vault/.claude/settings.json", kept)
    world.set_state(saved)
    manifest, out, code, data = role_pick("the control, the file restored and owed", "owed",
                                          False)
    code_r, out_r, _ = world.run("--record", "hooks-and-monitors", "--findings", "0",
                                 "--manifest", manifest, "--report", world.report())
    stored = world.state_data()
    check(code == 0 and data["complete"] is True and code_r == 0
          and stored["audits"][-1]["complete"] is True and stored["owed"] == [],
          "the control: pick exit %d, record exit %d, owed %r: %s"
          % (code, code_r, stored["owed"], out_r[:400]))
    # a due row: naming the file itself, then a folder holding a link to it
    world.set_state(clean)
    world.lifecycle(world.every_item_row() + [row(".claude/settings.json", kind="text",
                                                  next_review="2026-10-04")])
    _, out, code, data = role_pick("a due row naming the file, the file there", "due", False)
    check(code == 0 and data["complete"] is True, "a due row's control: exit %d" % code)
    os.remove(settings)
    _, out, code, data = role_pick("a due row naming the file, the file absent", None, True)
    check(code == 3 and any("not found on disk" in why for why in parse(out)["why"]),
          "a due row naming the absent file: exit %d, %r" % (code, parse(out)["why"]))
    world.write("vault/.claude/settings.json", kept)
    digest_kept = hashlib.sha256(kept.encode("utf-8")).hexdigest()
    for label, folder, item, part in (
            ("a due row naming a folder that holds a link to the file", ".claude/links",
             ".claude/links", "due"),
            ("a link to the file in the vault's hooks folder", ".claude/hooks", None,
             "rotating")):
        link = world.path("vault/%s/settings-link.json" % folder)
        os.makedirs(os.path.dirname(link), exist_ok=True)
        os.symlink(os.path.join("..", "settings.json"), link)
        state = json.loads(json.dumps(clean))   # the link in the baseline: no changed file
        state["baseline"]["hashes"]["vault/%s/settings-link.json" % folder] = digest_kept
        world.set_state(state)
        world.lifecycle(world.every_item_row() + ([row(item, kind="text",
                                                       next_review="2026-10-04")]
                                                  if item else []))
        _, out, code, data = role_pick("%s, the file there" % label, part, False)
        check(code == 0 and data["complete"] is True, "%s, the control: exit %d: %s"
              % (label, code, out[-500:]))
        os.remove(settings)
        _, out, code, data = role_pick("%s, the file absent" % label, part, True)
        check(code == 3, "%s, the file absent: exit %d" % (label, code))
        world.write("vault/.claude/settings.json", kept)
        os.remove(link)


def spelled_through(world, root):
    """The same world with every path spelled under `root`, another spelling of its root (a
    symbolic link to it): one set of files, two spellings. Its manifests and reports take other
    names than the world's own, in the same folder."""
    other = World.__new__(World)
    other.__dict__.update(world.__dict__)
    other.root = root
    other.vault, other.tools, other.hooks, other.out = (os.path.join(root, name) for name in
                                                        ("vault", "tools", "hooks", "out"))
    other.state = os.path.join(other.tools, "weekly-audit", "slices.json")
    other.manifests = world.manifests + 1000
    return other


def case_aliased_root_same_debt(world):
    """CR-AUDIT12 F3 (R7 item 5: an unread file with no earlier hash stays absent from the
    baseline; T6 (c)): a due row's file keeps its debt identity and its baseline omission whatever
    spelling of the roots the audit is given, while the printed paths keep the spelling given.
    First audits that differ only in that spelling (the roots' real path, and a symbolic link to
    them made here, so the case holds wherever the temporary folder lies), each with two due rows,
    one naming wiki/developments/design.md and one naming the hooks folder's guard.py by an
    absolute path through the link (the other spelling than the pick's in half the runs), and a
    report naming both files under `## Not read` as the pick printed them: every path the pick
    prints lies under the spelling of the roots it was given, both due rows' files included; each
    record leaves the audit incomplete, owes each file by its hash key, never by an absolute path,
    and keeps both out of the first baseline. A record given the other spelling than its pick's,
    either way round, owes the same keys. The control: a later reading discharges the debts, and
    the files' hashes then enter the baseline."""
    top = os.path.realpath(world.root)
    real = World(os.path.join(top, "real"))
    os.symlink(os.path.join(top, "real"), os.path.join(top, "alias"))
    alias = spelled_through(real, os.path.join(top, "alias"))
    fresh = real.state_data()   # --init's: no audit, no baseline
    keys = ["vault/wiki/developments/design.md", "hooks/guard.py"]
    real.lifecycle(real.every_item_row(skip=(os.path.join(real.hooks, "guard.py"),))
                   + [row("wiki/developments/design.md", kind="text", next_review="2026-10-04"),
                      row(os.path.join(alias.hooks, "guard.py"), kind="hook",
                          next_review="2026-10-04")])
    for label, picker, recorder in (("the real path", real, real), ("a link to it", alias, alias),
                                    ("picked through the link, recorded by the real path",
                                     alias, real),
                                    ("picked by the real path, recorded through the link", real,
                                     alias)):
        real.set_state(fresh)
        manifest = picker.manifest_path()
        code, out, _ = picker.run("--manifest-out", manifest)
        data, result = load(manifest), parse(out)
        files = [picker.path("vault/wiki/developments/design.md"), os.path.join(picker.hooks,
                                                                                 "guard.py")]
        due = result["parts"].get("due") or []
        check(code == 0 and [os.path.realpath(p) for p in due]
              == [os.path.realpath(p) for p in files],
              "%s: the due rows' files: exit %d, due %r" % (label, code, due))
        # named as the pick printed them, as a reviewer names them (the review's probe)
        code_r, out_r, _ = recorder.run("--record", data["slice"], "--findings", "0", "--manifest",
                                        manifest, "--report", recorder.report(
                                            text="# Report\n\n## Not read\n%s\nEND NOT READ: 2\n"
                                            % "\n".join(due)))
        stored = real.state_data()
        audit = stored["audits"][-1] if code_r == 0 else None
        check(code_r == 0 and audit["complete"] is False
              and sorted(o["entry"] for o in stored["owed"]) == sorted(keys)
              and not set(keys) & set(stored["baseline"]["hashes"])
              and all("absent: %s" % key in out_r for key in keys),
              "%s: the omissions owed %r, their unread hashes in the first baseline %r: exit %d: %s"
              % (label, stored["owed"], sorted(set(keys) & set(stored["baseline"]["hashes"])),
                 code_r, out_r[:600]))
        printed = reading(result) + result["requirements"]
        check(due == files and all(p in data["reading"] for p in files) and printed
              and all(p.startswith(picker.root + os.sep) for p in printed),
              "%s: the pick's paths do not keep the spelling of the roots it was given (%s): %r"
              % (label, picker.root, [p for p in printed
                                      if not p.startswith(picker.root + os.sep)]))
    manifest = alias.manifest_path()
    code, out, _ = alias.run("--manifest-out", manifest, today="2026-10-25")
    data = load(manifest)
    code, out, _ = alias.run("--record", data["slice"], "--findings", "0", "--manifest", manifest,
                             "--report", alias.report(), today="2026-10-25")
    stored = real.state_data()
    check(code == 0 and alias.path("vault/wiki/developments/design.md") in data["reading"]
          and os.path.join(alias.hooks, "guard.py") in data["reading"]
          and stored["owed"] == [] and set(keys) <= set(stored["baseline"]["hashes"]),
          "the control, a later reading: exit %d, owed %r: %s" % (code, stored["owed"], out[:500]))


def case_retired_row_needs_no_next_review(world):
    """The head's choice of 14 October 2026, from the lifecycle page's own rule that a retired row
    is never due: a retired row needs no Next review. One with none, with an empty mark (`—` as
    the live page's retired watcher row has it, or `-`), or with its State in another letter case,
    is neither due nor malformed. Every other row keeps the rule: an active row with no Next review
    is malformed, and a review-due and a quarantined row with none are due by their state and
    flagged MALFORMED. A retired row's other checks stay: with no Retire when, a Kind outside its
    set, a Next review that is not a date, or nine cells, it is still malformed, for that reason
    alone."""
    rows = world.every_item_row()
    rows += [row("retired-none.sh", state="retired", next_review=""),
             row("retired-watch.sh", kind="watcher", state="retired", next_review="—"),
             row("retired-hyphen.sh", state="retired", next_review="-"),
             row("retired-case.sh", state="Retired", next_review=""),
             row("active-none.sh", next_review=""),
             row("review-none.sh", state="review due", next_review=""),
             row("quarantined-none.sh", state="quarantined", next_review=""),
             row("retired-no-retire.sh", state="retired", next_review="", retire="—"),
             row("retired-bad-kind.sh", kind="gadget", state="retired", next_review=""),
             row("retired-bad-date.sh", state="retired", next_review="2026-13-01"),
             row("retired-short.sh", state="retired", cells=9)]
    world.lifecycle(rows)
    code, out, _ = world.run()
    result = parse(out)
    malformed = dict((m.split(" | ")[0], m.split(" | ", 2)[2]) for m in result["malformed"])
    due = [d.split(" |")[0] for d in result["due"]]
    expected = {"active-none.sh": "no Next review", "retired-no-retire.sh": "no Retire when",
                "retired-bad-kind.sh": "Kind 'gadget' is not one of suite, hook, monitor, "
                                       "watcher, controls, text",
                "retired-bad-date.sh": "Next review '2026-13-01' is not a YYYY-MM-DD date",
                "retired-short.sh": "9 cells, 10 expected"}
    check(code == 0 and malformed == expected,
          "the malformed rows: %r, %r expected" % (malformed, expected))
    check(due == ["review-none.sh", "quarantined-none.sh"]
          and all("MALFORMED: no Next review" in why for why in result["why"]),
          "the due rows: %r, why %r" % (due, result["why"]))
    for name in ("retired-none.sh", "retired-watch.sh", "retired-hyphen.sh", "retired-case.sh"):
        check(name not in out, "the retired row %s with no Next review is listed: %s"
              % (name, [line for line in out.splitlines() if name in line]))


# ------------------------------------------------------------------ CR-AUDIT13's findings -----

def case_held_member_keeps_debt(world):
    """CR-AUDIT13 F2 (R7 item 5; AUDIT.md, step 10: an owed entry is discharged only when this
    audit's pick listed its content and the reviewer read all of it): an owed entry's files are
    found before the held sources leave the reading list, so a file of it held for the second pass
    counts among them. Folder debt made as the review made it: the hash scan's walk of
    wiki/developments/ fails (the folder gone at that walk), the pick is incomplete, and its record
    owes the folder and keeps the earlier hashes below it, the register's among them (the register
    changed since). In an ordinary week, the listing back, the pick is complete, keeps the held
    sources out of pass 1 (the register and the lifecycle page on neither the reading list nor the
    requirement files) and lists the folder's other file as owed. The review's probe, a report
    naming the register unread: the audit is incomplete, its labels limited, the folder stays owed
    (said so, and no `owed: discharged`), nothing else is owed (the register itself is owed
    nothing), and the register keeps its earlier hash. The manifest's owed entry names the folder's
    two held files apart, as the sources spell them, and the OWED block counts them. The controls:
    a `none` report discharges the folder and advances the register's hash (reading every file of
    it permits discharge); a report naming only the requirement file CLAUDE.md leaves the audit
    incomplete, discharges the folder and owes nothing for the requirement file; in the register's
    own week, the register on the reading list, naming it keeps the folder owed and the register's
    earlier hash, as before; and an owed entry naming the register alone stays owed in an ordinary
    week under a `none` report, its one file held (an entry with no file listed, as before)."""
    world.record("standing-rules")
    register, lifecycle = world.path(REGISTER_REL), world.path(LIFECYCLE_REL)
    design, claude = world.path("vault/wiki/developments/design.md"), world.path("vault/CLAUDE.md")
    folder, key = world.path("vault/wiki/developments"), "vault/wiki/developments/"
    register_key = "vault/wiki/developments/known-issues.md"
    old = world.state_data()["baseline"]["hashes"][register_key]
    world.write(REGISTER_REL, REGISTER_TEXT.replace("- entry\n", "- entry, changed\n"))
    # the folder debt, made legitimately: the folder gone at its own hash scan's walk
    manifest = world.manifest_path()
    code, out = world.inject_walk("hash scan: vault/wiki/developments", folder, "--manifest-out",
                                  manifest, today="2026-10-12")
    data = load(manifest)
    check(code == 3 and data["unread"] == [key], "the failed listing: exit %d, unread %r"
          % (code, data["unread"]))
    world.record(data["slice"], today="2026-10-12", manifest=manifest)
    made = world.state_data()
    check(made["owed"] == [{"entry": key, "since": "2026-10-12"}]
          and made["baseline"]["hashes"].get(register_key) == old,
          "the folder debt: owed %r, the register's hash kept %r"
          % (made["owed"], made["baseline"]["hashes"].get(register_key) == old))
    # an ordinary week (the register attempted, so its change does not win it the tie)
    world.set_audits([("standing-rules", "2026-10-11", 0), ("register", "2026-10-12", 0)])
    saved = world.state_data()
    manifest = world.manifest_path()
    code, pick_out, _ = world.run("--manifest-out", manifest, today="2026-10-19")
    data, result = load(manifest), parse(pick_out)
    real = os.path.realpath
    first_pass = [real(p) for p in data["reading"] + data["requirements"] + reading(result)
                  + result["requirements"]]
    check(code == 0 and data["complete"] is True and data["slice"] == "skill:alpha"
          and result["parts"].get("owed") == [design] and data["requirements"] == [claude]
          and real(register) not in first_pass and real(lifecycle) not in first_pass,
          "an ordinary week: exit %d, slice %s, the owed part %r, the held sources in pass 1 %r"
          % (code, data["slice"], result["parts"].get("owed"),
             [p for p in first_pass if p in (real(register), real(lifecycle))]))
    record = ("--record", "skill:alpha", "--findings", "0", "--manifest", manifest)
    # the review's probe: the report names the register, held in this week, unread
    code, out, _ = world.run(*(record + ("--report", world.report(
        text="# Report\n\n## Not read\n%s\nEND NOT READ: 1\n" % register))), today="2026-10-19")
    stored = world.state_data()
    audit = stored["audits"][-1] if code == 0 else None
    check(code == 0 and audit["complete"] is False and "LABELS LIMITED" in out
          and stored["owed"] == saved["owed"] and "owed: discharged" not in out
          and stored["baseline"]["hashes"].get(register_key) == old
          and "kept: %s" % register_key in out
          and "  owed: %s (since 2026-10-12): stays owed, since the reviewer did not read 1 of its "
          "2 file(s) held for the second pass" % key in out,
          "the review's probe, the register named: exit %d, the audit %r, owed %r, the register's "
          "earlier hash kept %r: %s" % (code, audit, stored["owed"],
                                        stored["baseline"]["hashes"].get(register_key) == old,
                                        out[:900]))
    owed_entry = [o for o in data["owed"] if o["entry"] == key]
    check(owed_entry == [{"entry": key, "files": [design], "held": [register, lifecycle],
                          "acquired": True, "deleted": False}]
          and any(line.startswith("%s (owed since 2026-10-12): 1 file(s) on the reading list, and "
                                  "2 held for the second pass" % key) for line in result["owed"]),
          "the manifest's owed entry %r, the OWED block %r" % (owed_entry, result["owed"]))
    # the controls: every file read; a requirement file named; the register's own week
    world.set_state(saved)
    code, out, _ = world.run(*(record + ("--report", world.report())), today="2026-10-19")
    stored = world.state_data()
    check(code == 0 and stored["audits"][-1]["complete"] is True and stored["owed"] == []
          and stored["baseline"]["hashes"].get(register_key) == digest(register)
          and "owed: discharged 1 entry, listed by this audit's pick and read: %s" % key in out,
          "the control, `none`: exit %d, owed %r: %s" % (code, stored["owed"], out[:600]))
    world.set_state(saved)
    code, out, _ = world.run(*(record + ("--report", world.report(
        text="# Report\n\n## Not read\n%s\nEND NOT READ: 1\n" % claude))), today="2026-10-19")
    stored = world.state_data()
    check(code == 0 and stored["audits"][-1]["complete"] is False and stored["owed"] == []
          and "owed: discharged 1 entry" in out,
          "the control, the requirement file named: exit %d, owed %r: %s"
          % (code, stored["owed"], out[:600]))
    world.set_state(saved)
    world.set_audits([(s, "2026-10-12", 0) for s in ("standing-rules", "skill:alpha",
                                                     "skill:beta", "hooks-and-monitors", "tools")])
    manifest = world.manifest_path()
    code, out, _ = world.run("--manifest-out", manifest, today="2026-10-20")
    data = load(manifest)
    owed_entry = [o for o in data["owed"] if o["entry"] == key]
    check(code == 0 and data["slice"] == "register" and len(owed_entry) == 1
          and register in owed_entry[0]["files"] and owed_entry[0]["held"] == [lifecycle],
          "the register's week: exit %d, slice %s, the owed entry %r" % (code, data["slice"],
                                                                         owed_entry))
    code, out, _ = world.run("--record", "register", "--findings", "0", "--manifest", manifest,
                             "--report", world.report(text="# Report\n\n## Not read\n%s\n"
                                                      "END NOT READ: 1\n" % register),
                             today="2026-10-20")
    stored = world.state_data()
    check(code == 0 and stored["owed"] == saved["owed"]
          and stored["baseline"]["hashes"].get(register_key) == old,
          "the register's week, the register named: exit %d, owed %r: %s"
          % (code, stored["owed"], out[:600]))
    world.set_state(dict(saved, owed=[{"entry": register_key, "since": "2026-10-12"}]))
    manifest = world.manifest_path()
    code, out, _ = world.run("--manifest-out", manifest, today="2026-10-21")
    data = load(manifest)
    code_r, out_r, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest",
                                 manifest, "--report", world.report(), today="2026-10-21")
    check(code == 0 and data["slice"] == "skill:alpha"
          and data["owed"] == [{"entry": register_key, "files": [], "held": [register],
                                "acquired": True, "deleted": False}]
          and code_r == 0 and world.state_data()["owed"] == [{"entry": register_key,
                                                              "since": "2026-10-12"}]
          and "stays owed, since its pick listed none of its content" in out_r,
          "an owed entry naming the register alone: exit %d, owed %r, then %r: %s"
          % (code, data["owed"], world.state_data()["owed"], out_r[:500]))


def case_escaped_pipes_read_alike(world):
    """CR-AUDIT13 F3 (D18's area `Raw lifecycle, register and log`, and item 5: supported-input
    disagreements fail acceptance): this suite's lifecycle reading cuts a table line's cells at
    unescaped pipes only, a pipe with a backslash just before it being text of its cell, by its own
    specification (table_cells), never slice.py's code. Its counts equal those written here by
    hand for lines of escaped and plain pipes. The review's two cases, an intact empty lifecycle
    table followed by another table whose first cell holds `a \\| b`, of nine cells (an ordinary
    table: the page whole) and of ten (a damaged lifecycle header: the page torn), and their
    controls without the escaped pipe, each get the verdict written here from slice.py's
    parse_lifecycle and from this suite's reading alike; the four tables stand in the agreement
    corpus (protocols_agree_with_reference), at a page's end and before its table, each cut after
    every line. The truncation classifier, given a reader that accepted a page with the whole
    page's outcome, calls the ten-cell page FAIL (malformed input accepted, never harmless) and
    the nine-cell page harmless, and the same of their controls."""
    module = load_slice()
    for line, expected in (("| a \\| b | c |", 2), ("| a | b | c |", 3), ("|a\\|b|", 1),
                           ("| a | b \\|", 2), ("| \\| |", 1), ("||", 1), ("| a || b |", 3),
                           ("\t| a | b |  ", 2)):
        check(len(table_cells(line)) == expected,
              "this suite's reading cuts %r into %d cell(s) %r; %d written by hand"
              % (line, len(table_cells(line)), table_cells(line), expected))
    front = ("---\ntitle: Check lifecycle\n---\n\n# Check lifecycle\n\n%s\n%s\n\n"
             % (HEADER, SEPARATOR))
    same = ("the whole input's outcome",)
    for shape, cells, whole in ESCAPED_PIPE_TABLES:
        page = front + shape + LIFECYCLE_TAIL
        _, tables, damage = module.parse_lifecycle(module.text_lines(page))
        mine, theirs = tables > 0 and not damage, structure_problem("lifecycle", page)
        check(mine is whole and (theirs is None) is whole
              and len(table_cells(shape.split("\n")[0])) == cells,
              "a valid empty lifecycle table, then %r: slice.py %s, this suite's reading %s (%s); "
              "%s expected" % (shape.split("\n")[0], "whole" if mine else "torn",
                               "whole" if theirs is None else "torn", theirs,
                               "whole" if whole else "torn"))
        got = classify("ok", same, same, "lifecycle", page)
        check(got == ("harmless" if whole else "FAIL"),
              "the classifier calls the page holding %r, accepted with the whole outcome, %s"
              % (shape.split("\n")[0], got))
    shapes = agreement_shapes()
    check(all(shape in shapes for shape, _, _ in ESCAPED_PIPE_TABLES),
          "the agreement corpus lacks the review's escaped-pipe tables")


# ------------------------------------------------------------------ CR-AUDIT14's finding ------

def case_record_refuses_other_slice(world):
    """CR-AUDIT14 F1 (R7 item 6: the audit is recorded complete only when the reviewer read every
    item of its slice; AUDIT.md, step 10: `<slice>` is the slice of step 1): the record credits
    only the slice whose reading its manifest represents. The review's probes, on a complete
    standing-rules pick whose reading list holds only CLAUDE.md and CUSTOMISATION.md, with a
    `none` report: every other slice of the rotation named by --record (the review's tools and
    skill:alpha first) is refused before anything is committed (exit 2, its line naming the
    manifest's slice, slices.json byte for byte the same, no temporary file left), and so is
    hooks-and-monitors named on a complete standing-rules pick taken with .claude/settings.json
    absent (the review's complete hooks audit, its requirement file never read); a name that is
    no slice is refused as before, its line naming the manifest's slice too. The controls: the
    pick's own slice records complete, with no warning line (slice.py holds the post-commit
    warning nowhere now); the rotation credits only that attempt (the audits hold standing-rules
    alone, and the next pick comes round to skill:alpha); and the matching hooks-and-monitors
    pick with settings.json absent stays incomplete (exit 3), its own slice recorded incomplete
    with the pick's reason, while standing-rules named on that manifest is refused, its line
    naming hooks-and-monitors."""
    claude, custom = world.path("vault/CLAUDE.md"), world.path("vault/CUSTOMISATION.md")
    settings = world.path("vault/.claude/settings.json")
    folder = os.path.dirname(world.state)

    def refused(extra, chose, before, today=TODAY):
        code, out, _ = world.run(*extra, today=today)
        check(code == 2 and out.startswith("REFUSED") and "RECORDED" not in out
              and "the manifest's pick chose slice %s" % chose in out
              and "slices.json unchanged" in out,
              "%r: exit %d, a refusal naming the manifest's slice %s expected: %s"
              % (extra, code, chose, out[:400]))
        check(digest(world.state) == before, "%r changed slices.json" % (extra,))
        check(not [n for n in os.listdir(folder) if n.endswith(".tmp")],
              "%r left a temporary file in %s" % (extra, folder))
    manifest, _ = world.pick()
    data = load(manifest)
    check(data["slice"] == "standing-rules" and data["complete"] is True
          and sorted(data["reading"]) == sorted([claude, custom]) and data["requirements"] == [],
          "the review's pick: slice %s, complete %r, reading %r, requirements %r"
          % (data["slice"], data["complete"], data["reading"], data["requirements"]))
    others = ["tools", "skill:alpha"] + [s for s in data["slices"]
                                          if s not in ("standing-rules", "tools", "skill:alpha")]
    check(len(others) == 5 and sorted(others + ["standing-rules"]) == sorted(data["slices"]),
          "the rotation's other slices %r of %r" % (others, data["slices"]))
    report = world.report()
    before = digest(world.state)
    for other in others + ["not-a-slice"]:
        refused(("--record", other, "--findings", "0", "--manifest", manifest, "--report",
                 report), "standing-rules", before)
    # the review's absent-settings probe: hooks-and-monitors named on a standing-rules pick
    with open(settings, encoding="utf-8") as handle:
        kept = handle.read()
    os.remove(settings)
    absent, _ = world.pick()
    data = load(absent)
    check(data["slice"] == "standing-rules" and data["complete"] is True
          and settings not in data["reading"] + data["requirements"],
          "the standing-rules pick with %s absent: slice %s, complete %r, requirements %r"
          % (settings, data["slice"], data["complete"], data["requirements"]))
    refused(("--record", "hooks-and-monitors", "--findings", "0", "--manifest", absent, "--report",
             report), "standing-rules", before)
    world.write("vault/.claude/settings.json", kept)
    # the controls: the pick's own slice records, and the rotation credits that attempt alone
    code, out, _ = world.run("--record", "standing-rules", "--findings", "0", "--manifest",
                             manifest, "--report", report)
    stored = world.state_data()
    check(code == 0 and out.startswith("RECORDED: %s · slice standing-rules · findings 0 · "
                                       "complete" % TODAY)
          and not [line for line in out.splitlines() if line.startswith("warning")]
          and [(a["slice"], a["complete"]) for a in stored["audits"]] == [("standing-rules", True)],
          "the control, the pick's own slice: exit %d, audits %r: %s"
          % (code, stored["audits"], out[:500]))
    check("is recorded\"" not in read_text(SLICE),
          "slice.py still holds the warning said after recording another slice than the pick's")
    code, out, _ = world.run(today="2026-10-25")
    check(code == 0 and parse(out)["slice"] == "skill:alpha",
          "the next pick, after the refusals and the control: exit %d, slice %s"
          % (code, parse(out)["slice"]))
    # the absent-settings control: the matching hooks-and-monitors pick stays incomplete
    os.remove(settings)
    world.set_audits([(s, "2026-10-11", 0) for s in ("standing-rules", "skill:alpha",
                                                     "skill:beta", "register", "tools")])
    hooks_manifest = world.manifest_path()
    code, out, _ = world.run("--manifest-out", hooks_manifest, today="2026-10-25")
    data = load(hooks_manifest)
    check(code == 3 and data["slice"] == "hooks-and-monitors" and data["complete"] is False
          and settings in data["requirements"],
          "the matching hooks pick with %s absent: exit %d, slice %s, complete %r, requirements %r"
          % (settings, code, data["slice"], data["complete"], data["requirements"]))
    refused(("--record", "standing-rules", "--findings", "0", "--manifest", hooks_manifest,
             "--report", report), "hooks-and-monitors", digest(world.state), today="2026-10-25")
    code, out, _ = world.run("--record", "hooks-and-monitors", "--findings", "0", "--manifest",
                             hooks_manifest, "--report", report, today="2026-10-25")
    audit = world.state_data()["audits"][-1]
    check(code == 0 and audit["slice"] == "hooks-and-monitors" and audit["complete"] is False
          and audit["reasons"] == ["its pick was incomplete: 1 acquisition(s) did not succeed "
                                   "(requirement files: unknown)"],
          "the absent-settings control's record: exit %d, the audit %r: %s"
          % (code, audit, out[:500]))
    world.write("vault/.claude/settings.json", kept)


# Each part of the pick's output that rests on an unframed Markdown page, and the start of the
# `limit:` line that must end its block (slice.py's LIMIT_LINES, read here by their words).
LIMIT_STARTS = (("DUE ROWS", "limit: the lifecycle page is read by its structure alone"),
                ("MISSING ROWS", "limit: CLAUDE.md and CUSTOMISATION.md are read for their "
                                 "sections by their structure alone"),
                ("SECOND-PASS SOURCES", "limit: the register (its `## Open` and `## Closed` "
                                        "sections) and wiki/log.md"))


def limit_lines(out):
    """{part heading: its `limit:` line} for each part of a pick's output whose block (from its
    heading to the blank line that closes it) ends with the limit line expected of it."""
    lines = raw_lines(out)
    found = {}
    for part, start in LIMIT_STARTS:
        heads = [i for i, line in enumerate(lines) if line.startswith(part)]
        if len(heads) != 1:
            continue
        end = next((i for i in range(heads[0], len(lines)) if lines[i] == ""), len(lines))
        if lines[end - 1].startswith(start):
            found[part] = lines[end - 1]
    return found


def cut_after(text, anchor):
    """The text cut after the one whole line that is exactly `anchor`."""
    lines = text.split("\n")
    check(lines.count(anchor) == 1, "the cut's anchor %r occurs %d time(s)"
          % (anchor, lines.count(anchor)))
    return "\n".join(lines[:lines.index(anchor) + 1]) + "\n"


def cut_before(text, anchor):
    """The text cut before the one whole line that is exactly `anchor`."""
    lines = text.split("\n")
    check(lines.count(anchor) == 1, "the cut's anchor %r occurs %d time(s)"
          % (anchor, lines.count(anchor)))
    return "\n".join(lines[:lines.index(anchor)]) + "\n"


LIFECYCLE_REL = "vault/wiki/developments/check-lifecycle.md"
REGISTER_REL = "vault/wiki/developments/known-issues.md"
LOG_REL = "vault/wiki/log.md"


# The shapes the truncation world adds at the end of each of its five pages (D18), each page whole
# with them: a fenced block holding a heading-like line, a list fence closed inside its item
# (CR-AUDIT10 F1's shape) and a comment over three lines. The four raw consumers read them as text,
# so every cut through them is accepted. For the two standing-rules files the adapter reads them
# by markdown-it: a cut just after EXAMPLE_OPENER, LIST_OPENER or COMMENT_OPEN leaves a block open
# that hides no heading-like line (a valid shorter file, harmless or the limit), while a cut just
# after EXAMPLE_HEADING leaves that line hidden in a fence left open: lexer-hidden evidence, which
# the adapter must refuse (caught) and which the classifier never calls the limit.
EXAMPLE_OPENER = "```text"
EXAMPLE_HEADING = "## An example heading, in a fenced block"
LIST_OPENER = "- ```"
COMMENT_OPEN = "<!-- an example comment, over three lines"
RAW_EXAMPLES = ("\n" + EXAMPLE_OPENER + "\n" + EXAMPLE_HEADING + "\n```\n\n" + LIST_OPENER
                + "\n  ```\n\n" + COMMENT_OPEN + "\na note\nthat closes here -->\n")
# Written by hand for the truncation world's two standing-rules files (limit_world with examples):
# their sections, as heading lines, and the heading-like lines that stand inside a fenced example
# (each followed by its closing marker, ```), which are no section. The classifier's oracle for
# these files: never the adapter, never markdown-it.
STANDING_SECTIONS = {"vault/CLAUDE.md": ("## 1. One", "## 2. Two", "## 3. Three", "## 4. Four"),
                     "vault/CUSTOMISATION.md": ("## Settings", "## Roles")}
STANDING_EXAMPLES = {"vault/CLAUDE.md": ("## [YYYY-MM-DD] ingest | Short title", EXAMPLE_HEADING),
                     "vault/CUSTOMISATION.md": (EXAMPLE_HEADING,)}


def example_cuts(text):
    """{shape: lines kept just after its line} of a page ending in RAW_EXAMPLES: `fence opener`,
    `list opener` and `comment opener`, three cuts that leave a block open hiding no heading-like
    line, and `hidden heading`, the cut that leaves EXAMPLE_HEADING inside a fence left open."""
    lines = text.split("\n")
    anchors = (("fence opener", EXAMPLE_OPENER), ("hidden heading", EXAMPLE_HEADING),
               ("list opener", LIST_OPENER), ("comment opener", COMMENT_OPEN))
    check(all(lines.count(anchor) == 1 for _, anchor in anchors), "the raw examples' anchors")
    return dict((name, lines.index(anchor) + 1) for name, anchor in anchors)


def standing_reading(rel, whole, kept):
    """(the sections a cut of `whole` keeping `kept` lines holds, by STANDING_SECTIONS, or None
    when a heading-like line of STANDING_EXAMPLES stands in a fence the cut left open): this
    suite's reading of a cut standing-rules file, the oracle the classifier uses. A section is kept
    when its heading line is; an example's line is hidden when the cut keeps it but not the closing
    marker after it."""
    lines = whole.split("\n")
    for example in STANDING_EXAMPLES[rel]:
        check(lines.count(example) == 1, "the example %r" % example)
        at = lines.index(example)
        closer = next(i for i in range(at + 1, len(lines)) if lines[i] == "```")
        if at < kept <= closer:
            return None
    for heading in STANDING_SECTIONS[rel]:
        check(lines.count(heading) == 1, "the section %r" % heading)
    return [heading for heading in STANDING_SECTIONS[rel] if lines.index(heading) < kept]


def limit_world(world, meter=False, examples=False):
    """The third build review's interior-cut fixture: a lifecycle page with two tables under their
    own top-level headings, the due row (gate.py, overdue) in the second; CLAUDE.md with a further
    line in its enrolled section 3, then a section 4 no row enrols (a missing row); a log whose last
    entry (a query) carries a Run field after its Conflicts (the live log's shape), then a newer
    deep-lint entry (with `meter`, carrying a Meter field after its Conflicts, a live shape too);
    with `examples`, the register and CUSTOMISATION.md too, and each of the five pages ending in
    RAW_EXAMPLES; and a recorded baseline. Returns {rel: whole text}."""
    rows = world.every_item_row(skip=(".claude/hooks/gate.py",))
    due = row(".claude/hooks/gate.py", kind="hook", next_review="2026-10-04")
    with open(world.path("vault/CLAUDE.md"), encoding="utf-8") as handle:
        claude = handle.read()
    check(claude.count("rule three\n") == 1
          and LOG_TEXT.count("- **Changed**: d\n- **Conflicts**: none\n") == 1,
          "the fixture's anchors")
    whole = {LIFECYCLE_REL: ("---\ntitle: Check lifecycle\n---\n\n# Check lifecycle\n\n"
                             "## Suites\n\n" + "\n".join([HEADER, SEPARATOR] + rows)
                             + "\n\n## Hooks\n\n"
                             + "\n".join([HEADER, SEPARATOR, due]) + "\n" + LIFECYCLE_TAIL),
             "vault/CLAUDE.md": (claude.replace("rule three\n", "rule three\nrule three "
                                                "continuation\n") + "\n## 4. Four\nrule four\n"),
             LOG_REL: (LOG_TEXT.replace("- **Changed**: d\n- **Conflicts**: none\n",
                                        "- **Changed**: d\n- **Conflicts**: none\n"
                                        "- **Run**: run-x\n")
                       + "\n## [2026-10-13] deep-lint | newer\n- **Changed**: e\n"
                         "- **Conflicts**: none\n"
                       + ("- **Meter**: billed (planted)\n" if meter else ""))}
    if examples:
        whole[REGISTER_REL] = REGISTER_TEXT
        with open(world.path("vault/CUSTOMISATION.md"), encoding="utf-8") as handle:
            whole["vault/CUSTOMISATION.md"] = handle.read()
        whole = dict((rel, text + RAW_EXAMPLES) for rel, text in whole.items())
    for rel, text in whole.items():
        world.write(rel, text)
    world.record("standing-rules")
    return whole


def case_unframed_pages_limit(world):
    """Item 6 (revision 7), the provisional replacement, and T5's reclassification: the heuristics
    that claimed more than an unframed Markdown page's structure shows are removed (a heading after
    the last lifecycle table, the standing-rules count taken from lifecycle rows, a closing field
    on the log's last entry, and with them the register's closing section and the empty-heading
    rule), and each shape they refused or missed now reads as the stated limit: the acquisition
    succeeds, the pick completes (exit 0, the manifest complete, no LABELS LIMITED), its result is
    the shorter page's, and every part resting on such a page ends with its `limit:` line. The
    third build review's three interior cuts: the lifecycle page cut just after its second
    top-level heading (its due row lost), CLAUDE.md cut inside its enrolled section 3 (section 4's
    missing row lost), and the log cut after a query entry's Conflicts, before its Run field (the
    newer deep-lint entry lost, the older selected). The removed rules' own shapes: the log ending
    on a Run field after its last entry's Conflicts (the newer entry lost; the live log's shape,
    which the last-entry rule refused), the lifecycle page cut after a whole row with nothing after
    it (its later rows and table lost), the register
    ending on its Closed section, CLAUDE.md ending on an empty heading, CUSTOMISATION.md cut before
    its enrolled Roles section, and a stale row enrolling a section CLAUDE.md does not hold (which
    made every pick incomplete). The control: the whole pages give the whole results."""
    whole = limit_world(world)
    with open(world.path("vault/CUSTOMISATION.md"), encoding="utf-8") as handle:
        custom = handle.read()
    due_row = row(".claude/hooks/gate.py", kind="hook", next_review="2026-10-04")
    stale = row("CLAUDE.md §9", kind="text")

    def due(result):
        return has(result["parts"].get("due", []), ".claude/hooks/gate.py")

    def four_missing(result):
        return "CLAUDE.md §4 | text group" in result["missing"]

    legs = (("the lifecycle page cut just after its second top-level heading", LIFECYCLE_REL,
             cut_after(whole[LIFECYCLE_REL], "## Hooks"),
             lambda result, out: not due(result) and "DUE ROWS (0:" in out),
            ("CLAUDE.md cut inside its enrolled section 3", "vault/CLAUDE.md",
             cut_after(whole["vault/CLAUDE.md"], "rule three"),
             lambda result, out: not four_missing(result)
             and "sections read: CLAUDE.md 3, CUSTOMISATION.md 2" in result["controls"]),
            ("the log cut after a query entry's Conflicts, before its Run field", LOG_REL,
             cut_before(whole[LOG_REL], "- **Run**: run-x"),
             lambda result, out: "the deep-lint entry of 2026-10-02" in out),
            ("the log ending on a field after its last entry's Conflicts (the newer entry lost)",
             LOG_REL, cut_before(whole[LOG_REL], "## [2026-10-13] deep-lint | newer"),
             lambda result, out: "the deep-lint entry of 2026-10-02" in out),
            ("the lifecycle page cut after a whole row, nothing after it", LIFECYCLE_REL,
             cut_after(whole[LIFECYCLE_REL], row(".claude/hooks/test_gate.sh")),
             lambda result, out: not due(result) and "DUE ROWS (0:" in out
             and "lifecycle rows parsed 3;" in result["controls"]),
            ("the register ending on its Closed section", REGISTER_REL,
             REGISTER_TEXT.split("\n## Related")[0] + "\n",   # a source, or the week's slice
             lambda result, out: not any("UNKNOWN" in line for line in raw_lines(out)
                                         if world.path(REGISTER_REL) in line)),
            ("CLAUDE.md ending on an empty heading", "vault/CLAUDE.md",
             cut_after(whole["vault/CLAUDE.md"], "## 4. Four"),
             lambda result, out: four_missing(result)
             and "sections read: CLAUDE.md 4, CUSTOMISATION.md 2" in result["controls"]),
            ("CUSTOMISATION.md cut before its enrolled Roles section", "vault/CUSTOMISATION.md",
             custom.split("## Roles")[0],
             lambda result, out: "sections read: CLAUDE.md 4, CUSTOMISATION.md 1"
             in result["controls"]),
            ("a stale row enrolling a section CLAUDE.md does not hold", LIFECYCLE_REL,
             whole[LIFECYCLE_REL].replace(due_row + "\n", due_row + "\n" + stale + "\n"),
             lambda result, out: due(result)))
    check(whole[LIFECYCLE_REL].count(due_row + "\n") == 1, "the stale row's anchor")
    for number, (name, rel, text, holds) in enumerate(legs):
        world.write(rel, text)
        manifest = world.manifest_path()
        try:
            code, out, _ = world.run("--manifest-out", manifest, today="2026-10-%d" % (19 + number))
        finally:
            world.write(rel, whole.get(rel, custom if rel == "vault/CUSTOMISATION.md"
                                       else REGISTER_TEXT))
        data, result = load(manifest), parse(out)
        check(code == 0 and data["complete"] is True and "LABELS LIMITED" not in out
              and "acquisitions all ok" in result["summary"]
              and sorted(limit_lines(out)) == sorted(p for p, _ in LIMIT_STARTS)
              and holds(result, out),
              "%s: exit %d, complete %r, limit lines %r: %r %s" % (
                  name, code, data["complete"], sorted(limit_lines(out)), result["incomplete"],
                  out[-900:]))
    code, out, _ = world.run(today="2026-10-30")
    result = parse(out)
    check(code == 0 and due(result) and four_missing(result)
          and "the deep-lint entry of 2026-10-13" in out
          and "sections read: CLAUDE.md 4, CUSTOMISATION.md 2" in result["controls"],
          "the whole pages: %d %s" % (code, out[-900:]))


def case_backstop_cut_reads_changed(world):
    """Item 6 (revision 7), the stated limit's backstop: a page cut after its baseline, left
    structurally valid and so read whole by its acquisition (the pick completes), reads as changed
    at the next pick by the hash scan. CLAUDE.md and CUSTOMISATION.md, each cut short after the
    audit that set the baseline, are listed as changed and so are on the reading list, where the
    reviewer reads them; the lifecycle page and the register, cut likewise, are named on their
    `held for the second pass` lines in an ordinary week, and in the register's own week the
    register is on the reading list as changed. wiki/log.md, which no root hashes, shows no change
    (it is on no list), and the pick's limit line names step 7's label check as its only backstop.
    The control: the pick before any cut lists none of them as changed."""
    world.record("standing-rules")
    rels = ("vault/CLAUDE.md", "vault/CUSTOMISATION.md", LIFECYCLE_REL, REGISTER_REL, LOG_REL)
    texts = {}
    for rel in rels:
        with open(world.path(rel), encoding="utf-8") as handle:
            texts[rel] = handle.read()
    code, out, _ = world.run(today="2026-10-19")
    result = parse(out)
    check(code == 0 and not result["parts"].get("changed") and not result["held"],
          "the control: %d %r %r" % (code, result["parts"].get("changed"), result["held"]))
    last_row = world.every_item_row()[-1]
    cuts = {"vault/CLAUDE.md": texts["vault/CLAUDE.md"].split("## 3. Three")[0],
            "vault/CUSTOMISATION.md": texts["vault/CUSTOMISATION.md"].split("## Roles")[0],
            LIFECYCLE_REL: texts[LIFECYCLE_REL].split(last_row)[0],
            REGISTER_REL: texts[REGISTER_REL].split("\n## Related")[0] + "\n",
            LOG_REL: texts[LOG_REL].split("## [2026-10-02]")[0]}
    check(all(len(cuts[rel]) < len(texts[rel]) for rel in rels), "the cuts")
    for rel, text in cuts.items():
        world.write(rel, text)
    # an ordinary week: the register attempted lately, so another slice comes round
    world.set_audits([("standing-rules", "2026-10-11", 0), ("register", "2026-10-12", 0)])
    manifest, out = world.pick(today="2026-10-20")
    result, data = parse(out), load(manifest)
    changed = result["parts"].get("changed", [])
    check(data["complete"] is True and "LABELS LIMITED" not in out
          and world.path("vault/CLAUDE.md") in changed
          and world.path("vault/CUSTOMISATION.md") in changed
          and world.path("vault/CLAUDE.md") in data["reading"]
          and sorted(result["held"]) == sorted([world.path(LIFECYCLE_REL),
                                                world.path(REGISTER_REL)])
          and not any(path.endswith("log.md") for path in reading(result) + result["held"])
          and "the deep-lint entry of 2026-09-01" in out
          and "the only one for wiki/log.md, which is not hashed" in limit_lines(out).get(
              "SECOND-PASS SOURCES", ""),
          "the cut pages: changed %r, held %r: %s" % (changed, result["held"], out[-900:]))
    # the register's own week: every other slice attempted lately, so the register comes round
    world.set_audits([(name, "2026-10-%d" % (10 + i), 0) for i, name in enumerate(data["slices"])
                      if name != "register"])
    code, out, _ = world.run(today="2026-10-21")
    result = parse(out)
    check(code == 0 and result["slice"] == "register"
          and world.path(REGISTER_REL) in result["parts"].get("changed", [])
          and result["held"] == [world.path(LIFECYCLE_REL)],
          "the register's own week: %d %s %r %r" % (code, result["slice"],
                                                    result["parts"].get("changed"),
                                                    result["held"]))


def case_commit_after_read_back(world):
    """T5, item 6 (the fourth build review's fourth finding): the record writes the new state to a
    temporary file beside slices.json, reads it back and checks it, and only then replaces
    slices.json in one step. Real failed opens of that temporary file (made unreadable, for any user
    but root; removed before it is read), the file cut at every line boundary, and a folder that
    refuses the temporary file (for any user but root) each refuse the record: exit 2, a REFUSED
    line saying, truly, that slices.json is unchanged, slices.json byte for byte as before and no
    temporary file left. A refusal raised after the replace (planted in the rescan) is said as what
    it is, PROBE FAILED with slices.json written and holding the record, never "unchanged". The
    control: a record whose read-back succeeds replaces slices.json, and no line of it says
    unchanged."""
    world.record("standing-rules")
    manifest, out = world.pick(today="2026-10-12")
    slice_name = parse(out)["slice"]
    saved = world.state_data()
    folder = os.path.dirname(world.state)
    record = ("--record", slice_name, "--findings", "0", "--manifest", manifest)
    seen = {}

    def at_read_back(how):
        """A patch: `how(path)` done to the temporary state just before the record reads it."""
        def patch(module):
            real = module.read_text

            def read_text(path):
                if os.path.dirname(path) == folder and path.endswith(".tmp"):
                    with open(path, "rb") as handle:
                        seen["lines"] = handle.read().count(b"\n")
                    how(path)
                return real(path)
            module.read_text = read_text
        return patch

    def refused_unchanged_here(name, patch):
        world.set_state(saved)
        before = digest(world.state)
        code, out = world.in_process(*(record + ("--report", world.report())), today="2026-10-12",
                                     patch=patch)
        check(code == 2 and out.startswith("REFUSED") and "slices.json unchanged" in out
              and digest(world.state) == before and "RECORDED" not in out
              and not [n for n in os.listdir(folder) if n.endswith(".tmp")],
              "%s: exit %d, %s" % (name, code, out[:400]))

    def cut(lines):
        def how(path):
            with open(path, "rb") as handle:
                kept = handle.read().split(b"\n")[:lines]
            with open(path, "wb") as handle:
                handle.write(b"".join(line + b"\n" for line in kept))
        return how
    refused_unchanged_here("the temporary file removed before it is read",
                           at_read_back(os.remove))
    if os.geteuid() != 0:
        refused_unchanged_here("the temporary file unreadable", at_read_back(
            lambda path: os.chmod(path, 0)))
        os.chmod(folder, stat.S_IRUSR | stat.S_IXUSR)
        try:
            refused_unchanged_here("a folder that refuses the temporary file", None)
        finally:
            os.chmod(folder, stat.S_IRWXU)
    total = seen["lines"]
    check(total > 10, "the temporary state holds only %d line(s)" % total)
    for lines in range(total):
        refused_unchanged_here("the temporary file cut after %d of its %d lines" % (lines, total),
                               at_read_back(cut(lines)))

    def raising_rescan(module):
        real = module.hash_roots

        def hash_roots(registry, vault, tools, hooks, state_filter, step="hash scan"):
            if step == "rescan":
                raise module.Refusal("REFUSED: a planted failure after the commit; slices.json "
                                     "unchanged")
            return real(registry, vault, tools, hooks, state_filter, step)
        module.hash_roots = hash_roots
    world.set_state(saved)
    code, out = world.in_process(*(record + ("--report", world.report())), today="2026-10-12",
                                 patch=raising_rescan)
    check(code == 2 and out.startswith("PROBE FAILED: slices.json was written at %s and holds this "
                                       "record" % world.state)
          and "unchanged" not in out and len(world.state_data()["audits"]) == len(saved["audits"]) + 1,
          "a refusal after the commit: %d %s" % (code, out[:400]))
    world.set_state(saved)
    code, out = world.in_process(*(record + ("--report", world.report())), today="2026-10-12")
    check(code == 0 and out.startswith("RECORDED") and "unchanged" not in out
          and len(world.state_data()["audits"]) == len(saved["audits"]) + 1
          and not [n for n in os.listdir(folder) if n.endswith(".tmp")],
          "the control: %d %s" % (code, out[:400]))


INVENTORY_CHILD = r'''
import contextlib, importlib.util, io, json, os, sys
sys.dont_write_bytecode = True
args = json.loads(sys.argv[1])
spec = importlib.util.spec_from_file_location("slice_under_inventory", args["slice"])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
interpreter = tuple(sorted(set(os.path.join(os.path.realpath(p), "")
                               for p in (sys.prefix, sys.base_prefix, sys.exec_prefix))))
events = []
def hook(event, hook_args):
    if event == "open":
        path, mode, flags = hook_args
        if not isinstance(path, str):
            return
        if isinstance(mode, str):
            kind = "write" if any(c in mode for c in "wax+") else "read"
        else:
            kind = "write" if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT) else "read"
    elif event in ("os.listdir", "os.scandir"):
        path = hook_args[0] if hook_args and hook_args[0] is not None else "."
        if not isinstance(path, str):
            return
        kind = "read"
    else:
        return
    real = os.path.realpath(path)
    if real.startswith(interpreter):
        return
    step = module.ACTIVE[-1] if module.ACTIVE else None
    events.append([event, real, kind, step.kind if step else None, step.name if step else None])
if args["plant"] == "unregistered":
    original = module.do_pick
    def planted(registry, vault, *rest):
        with open(os.path.join(vault, "wiki", "log.md"), "r", encoding="utf-8") as handle:
            handle.read()
        return original(registry, vault, *rest)
    module.do_pick = planted
elif args["plant"] == "misplaced":
    sections = module.top_sections
    def planted_sections(path):
        with open(os.path.join(os.path.dirname(path), "wiki", "log.md"), "r",
                  encoding="utf-8") as handle:
            handle.read()
        return sections(path)
    module.top_sections = planted_sections
sys.addaudithook(hook)
codes = []
for argv in args["runs"]:
    with contextlib.redirect_stdout(io.StringIO()):
        codes.append(module.main(argv))
sys.stdout.write(json.dumps({"codes": codes, "events": events}))
'''


def inventory_run(world, plant, today):
    """A pick and a record run in a child process under a file-open audit hook: (exit codes,
    events), each event (audit event, real path, read or write, the step's kind, its name). The
    record names the slice the child's pick chooses (CR-AUDIT14 F1: it refuses any other), which a
    plain pick over the same state and date says first, in this process, writing nothing."""
    chosen = parse(world.run(today=today)[1])["slice"]
    manifest, report = world.manifest_path(), world.report()
    runs = [world.argv(["--manifest-out", manifest], today),
            world.argv(["--record", chosen, "--findings", "0", "--manifest", manifest,
                        "--report", report], today)]
    done = subprocess.run([sys.executable, "-B", "-c", INVENTORY_CHILD,
                           json.dumps({"slice": SLICE, "plant": plant, "runs": runs})],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                          timeout=TIMEOUT_S)
    check(done.returncode == 0, "the inventory child failed: %s" % done.stderr[-600:])
    result = json.loads(done.stdout)
    check(load(manifest)["slice"] == chosen, "the inventory child's pick chose %s, the plain pick "
          "%s" % (load(manifest)["slice"], chosen))
    return result["codes"], result["events"], manifest, report


def scope_of(world, name, manifest, report):
    """What an acquisition may read: its own root, file or files (real paths)."""
    real = os.path.realpath
    roots = [real(os.path.join(world.vault, rel)) for rel in (".claude", "CLAUDE.md",
                                                              "CUSTOMISATION.md",
                                                              "CUSTOMISATION-definitions.md",
                                                              "wiki/developments")]
    roots += [real(world.tools), real(world.hooks)]
    # revision 6: the read-back reads the new state's temporary file beside slices.json, never
    # slices.json itself, before the commit
    temporary = os.path.join(real(os.path.dirname(world.state)), "." + os.path.basename(world.state)
                             + ".")
    fixed = {"premises": roots, "slices.json": [real(world.state)],
             "slices.json read back": [temporary], "manifest": [real(manifest)],
             "coverage": [real(report)], "owed content": roots, "rotation": roots,
             "inventory": roots, "due rows' files": roots,
             "lifecycle rows": [real(world.path("vault/wiki/developments/check-lifecycle.md"))],
             "comparison source: the register": [real(world.path(
                 "vault/wiki/developments/known-issues.md"))],
             "comparison source: deep-lint": [real(world.path("vault/wiki/log.md"))]}
    if name in fixed:
        return fixed[name]
    step, _, rel = name.partition(": ")
    if step in ("hash scan", "rescan"):
        label, _, below = rel.partition("/")
        base = {"vault": world.vault, "tools": world.tools, "hooks": world.hooks}[label]
        return [real(os.path.join(base, below) if below else base)]
    return []


def within(path, scope):
    """Whether a path lies in a scope: a root or file (its path, or below it), or a temporary
    file's stem (a prefix ending in `.`, matched with the `.tmp` its name ends in)."""
    return any(path == top or path.startswith(top.rstrip(os.sep) + os.sep)
               or (top.endswith(".") and path.startswith(top) and path.endswith(".tmp")
                   and os.sep not in path[len(top):]) for top in scope)


def case_independent_inventory(world):
    """T5, the independent inventory: a pick and a record run under a file-open audit hook
    (sys.addaudithook), which sees every file opened and every folder listed. The control: every
    read lies inside a registered acquisition and within what that acquisition is declared to
    read, and every write inside a write; the reads reach every acquisition of the manifest. A
    planted unregistered read (wiki/log.md read outside any acquisition, the class of the third
    design check's deep-lint lookup) makes the inventory fail, and so does a planted misplaced
    read (wiki/log.md read inside the inventory)."""
    world.record("standing-rules")
    codes, events, manifest, report = inventory_run(world, "none", TODAY)
    check(codes == [0, 0], "the control's exit codes %r" % codes)
    reads = [e for e in events if e[2] == "read"]
    writes = [e for e in events if e[2] == "write"]
    outside = [e for e in reads if e[3] != "acquisition"]
    check(len(reads) >= 20 and len(writes) >= 2, "the hook saw %d reads and %d writes"
          % (len(reads), len(writes)))
    check(not outside, "a file was opened outside a registered acquisition: %r" % outside[:5])
    check(all(e[3] == "write" for e in writes), "a write outside a write step: %r"
          % [e for e in writes if e[3] != "write"][:5])
    stray = [e for e in reads if not within(e[1], scope_of(world, e[4], manifest, report))]
    check(not stray, "a read outside its acquisition's scope: %r" % stray[:5])
    names = set(e[4] for e in reads)
    for name in [a["name"] for a in load(manifest)["acquisitions"]] + ["manifest", "coverage"]:
        if name in ("rotation", "due rows' files", "owed content", "requirement files"):
            continue   # these may read nothing new (the rotation lists through walks: below; the
            # requirement files' acquisition reads nothing itself, the hash scan having seen them)
        check(name in names, "no read was seen inside %r: %r" % (name, sorted(names)))
    check(any(e[4] == "rotation" and e[0] in ("os.scandir", "os.listdir") for e in reads),
          "no listing was seen inside the rotation")
    for plant, rule in (("unregistered", "outside any acquisition"),
                        ("misplaced", "outside its acquisition's scope")):
        codes, events, manifest, report = inventory_run(
            world, plant, "2026-10-%d" % (27 if plant == "unregistered" else 28))
        log_reads = [e for e in events if e[2] == "read" and e[1].endswith(os.path.join(
            "wiki", "log.md"))]
        if plant == "unregistered":
            caught = [e for e in log_reads if e[3] != "acquisition"]
        else:
            caught = [e for e in log_reads if not within(e[1], scope_of(world, e[4], manifest,
                                                                        report))]
        check(caught, "the planted %s read of wiki/log.md was not caught (%s): %r"
              % (plant, rule, log_reads))


def case_owed_not_listed_stays_owed(world):
    """T6 (a), the third build review's third finding: an owed reading that is not listed in the
    slice stays owed. Its content gone from the owed acquisition alone (the review's race) fails
    that acquisition, so the pick is incomplete, and the record keeps the entry; restored
    unchanged, it is listed as owed and the reading discharges it (the control). An owed file
    gone for good is a deletion under revision 5 (case owed_deleted_discharged)."""
    world.record("standing-rules")
    guard = world.path("hooks/guard.py")
    restore = unreadable(world, "hooks/guard.py")
    manifest = world.manifest_path()
    try:
        code, out, _ = world.run("--manifest-out", manifest, today="2026-10-12")
    finally:
        restore()
    check(code == 3, "the incomplete pick: %d" % code)
    world.record(parse(out)["slice"], today="2026-10-12", manifest=manifest)
    check(world.state_data()["owed"] == [{"entry": "hooks/guard.py", "since": "2026-10-12"}],
          "the owed list %r" % world.state_data()["owed"])
    manifest = world.manifest_path()
    code, out = world.inject_walk("owed content", guard, "--manifest-out", manifest,
                                  today="2026-10-13")
    data = load(manifest)
    check(code == 3 and status_of(data, "owed content") == "failed"
          and not has(reading(parse(out)), "hooks/guard.py"),
          "the owed content gone at its own acquisition: %d %r" % (code, data["acquisitions"]))
    out = world.record(data["slice"], today="2026-10-13", manifest=manifest)
    check(world.state_data()["owed"] == [{"entry": "hooks/guard.py", "since": "2026-10-12"}]
          and "owed: discharged" not in out, "an owed reading never listed was discharged: %s" % out)
    # the restored-unchanged control: back in place, unchanged, it is listed as owed and the
    # reading discharges it
    manifest, out = world.pick(today="2026-10-14")
    result = parse(out)
    check(load(manifest)["complete"] is True and result["parts"].get("owed") == [guard]
          and not has(result["parts"].get("changed", []), "hooks/guard.py"),
          "the restored, unchanged content: owed %r, changed %r"
          % (result["parts"].get("owed"), result["parts"].get("changed")))
    out = world.record(result["slice"], today="2026-10-14", manifest=manifest)
    check("owed: discharged 1 entry" in out and world.state_data()["owed"] == [],
          "the restored, unchanged content listed and read was not discharged: %s" % out)


def case_owed_deleted_discharged(world):
    """T6 (g), item 5's deletion rule (the third build review's specification gap): an owed file
    deleted for good, its root read cleanly, is listed in the slice as deleted since its baseline,
    in its own part of the reading list, and the OWED block and the removed line say so, while a
    file deleted that was not owed stays a removed line apart from the reading list, as before.
    Named under `## Not read`, it stays owed with its earlier hash. Not named, it is discharged and
    the baseline records it as absent, so its later reappearance is selected as changed. The same
    path under a root that fails (the hooks root gone at its hash scan) is no deletion: the owed
    content fails, the path stays owed and its hash is kept. An owed folder whose files are all
    gone, and an owed path outside the hashed roots in a folder that can be listed, are listed and
    discharged alike."""
    world.record("standing-rules")
    guard = world.path("hooks/guard.py")
    with open(guard, "rb") as handle:
        content = handle.read()
    restore = unreadable(world, "hooks/guard.py")
    manifest = world.manifest_path()
    try:
        code, out, _ = world.run("--manifest-out", manifest, today="2026-10-12")
    finally:
        restore()
    world.record(parse(out)["slice"], today="2026-10-12", manifest=manifest)
    saved = world.state_data()
    check(saved["owed"] == [{"entry": "hooks/guard.py", "since": "2026-10-12"}]
          and "hooks/guard.py" in saved["baseline"]["hashes"], "the owed entry %r" % saved["owed"])
    os.remove(guard)
    os.remove(world.path("tools/thing.py"))
    manifest, out = world.pick(today="2026-10-13")
    result, data = parse(out), load(manifest)
    check(data["complete"] is True and result["parts"].get("deleted") == [guard]
          and not has(result["parts"].get("owed", []), "guard.py")
          and guard in data["reading"] and data["owed"] == [
              {"entry": "hooks/guard.py", "files": [guard], "held": [], "acquired": True,
               "deleted": True}],
          "the deletion listed: %r %r" % (result["parts"], data["owed"]))
    check(any(line.startswith("hooks/guard.py (owed since 2026-10-12): deleted since its "
                              "baseline") for line in result["owed"])
          and "removed, and owed from an earlier audit, so on the reading list as deleted: %s"
          % guard in out and "removed (not in the reading list): %s" % world.path("tools/thing.py")
          in out and not has(reading(result), "thing.py"),
          "the OWED block or the removed lines: %r %s" % (result["owed"], out[-900:]))
    out = world.record(data["slice"], today="2026-10-13", manifest=manifest, not_read=[guard])
    stored = world.state_data()
    check(stored["owed"] == saved["owed"] and stored["audits"][-1]["complete"] is False
          and stored["baseline"]["hashes"].get("hooks/guard.py")
          == saved["baseline"]["hashes"]["hooks/guard.py"]
          and "tools/thing.py" not in stored["baseline"]["hashes"],
          "named under `## Not read`: %r %s" % (stored["owed"], out[:500]))
    world.set_state(saved)
    out = world.record(data["slice"], today="2026-10-13", manifest=manifest)
    stored = world.state_data()
    check(stored["owed"] == [] and stored["audits"][-1]["complete"] is True
          and "hooks/guard.py" not in stored["baseline"]["hashes"]
          and "owed: discharged 1 entry deleted since its baseline" in out,
          "not named: %r %s" % (stored["owed"], out[:700]))
    with open(guard, "wb") as handle:
        handle.write(content)
    result = parse(world.run(today="2026-10-20")[1])
    check(has(result["parts"].get("changed", []), "hooks/guard.py"),
          "the reappearance was not selected as changed: %r" % result["parts"].get("changed"))
    os.remove(guard)
    world.set_state(saved)
    manifest = world.manifest_path()
    code, out = world.inject_walk("hash scan: hooks", world.hooks, "--manifest-out", manifest,
                                  today="2026-10-21")
    data, result = load(manifest), parse(out)
    check(code == 3 and data["complete"] is False and not result["parts"].get("deleted")
          and status_of(data, "owed content") == "failed"
          and data["owed"] == [{"entry": "hooks/guard.py", "files": [], "held": [],
                                "acquired": False, "deleted": False}],
          "under a failed root: %d %r" % (code, data["owed"]))
    out = world.record(data["slice"], today="2026-10-21", manifest=manifest)
    stored = world.state_data()
    check({"entry": "hooks/guard.py", "since": "2026-10-12"} in stored["owed"]
          and stored["baseline"]["hashes"].get("hooks/guard.py")
          == saved["baseline"]["hashes"]["hooks/guard.py"] and "owed: discharged" not in out,
          "under a failed root the path was discharged: %r %s" % (stored["owed"], out[:500]))
    world.set_state(saved)
    beta = world.path("vault/.claude/skills/beta")
    outside = world.path("elsewhere")
    os.makedirs(outside)
    planted = dict(saved, owed=[{"entry": "vault/.claude/skills/beta/", "since": "2026-10-12"},
                                {"entry": os.path.join(outside, "gone.md"), "since": "2026-10-12"}])
    world.set_state(planted)
    shutil.rmtree(beta)
    manifest, out = world.pick(today="2026-10-22")
    result, data = parse(out), load(manifest)
    check(data["complete"] is True
          and result["parts"].get("deleted") == [beta + "/", os.path.join(outside, "gone.md")],
          "the deleted folder and outside path: %r %r" % (result["parts"].get("deleted"),
                                                          data["owed"]))
    out = world.record(data["slice"], today="2026-10-22", manifest=manifest)
    stored = world.state_data()
    check(stored["owed"] == [] and not any(k.startswith("vault/.claude/skills/beta/")
                                           for k in stored["baseline"]["hashes"]),
          "the folder and outside deletions: %r %s" % (stored["owed"], out[:600]))


def case_absence_established(world):
    """T5 and T6 (g), item 5 (the fourth build review's first finding): absence is established,
    never read from an error. An owed file outside the hashed roots whose metadata cannot be read
    while its folder still lists its name (the review's plant: lstat and stat refused, the listing
    holding the name) is no deletion: the owed content fails, the pick and the record are
    incomplete and the entry stays owed. Planted in this process (any user) and, for any user but
    root, on the file system itself (its folder readable, not searchable). The controls: the same
    path truly absent is a deletion, listed and discharged; one whose folder is unsearchable and
    holds no such name stays owed too (its metadata cannot be read); back and readable, the file is
    listed as owed content."""
    world.record("standing-rules")
    external = world.path("external")
    os.makedirs(external)
    secret = world.write("external/secret.md", "# secret\n")
    saved = dict(world.state_data(), owed=[{"entry": secret, "since": "2026-10-12"}])
    world.set_state(saved)

    def failed_and_kept(code, out, data, what, today):
        check(code == 3 and data["complete"] is False
              and status_of(data, "owed content") == "failed"
              and data["owed"] == [{"entry": secret, "files": [], "held": [], "acquired": False,
                                    "deleted": False}]
              and not parse(out)["parts"].get("deleted")
              and any(line.startswith("owed content: failed: ") and "could not be looked at" in line
                      for line in parse(out)["incomplete"]),
              "%s: the pick: exit %d, owed %r: %s" % (what, code, data["owed"], out[-600:]))
        out = world.record(data["slice"], today=today, manifest=world.last_manifest)
        stored = world.state_data()
        check(stored["owed"] == saved["owed"] and stored["audits"][-1]["complete"] is False
              and "owed: discharged" not in out,
              "%s: the record discharged it: %r %s" % (what, stored["owed"], out[:500]))
        world.set_state(saved)

    world.last_manifest = world.manifest_path()
    with refused_metadata([secret]):
        code, out = world.in_process("--manifest-out", world.last_manifest, today="2026-10-13")
    failed_and_kept(code, out, load(world.last_manifest), "metadata refused in this process",
                    "2026-10-13")
    if os.geteuid() != 0:   # mode r-- stops no root
        world.last_manifest = world.manifest_path()
        with unsearchable(external):
            check(os.listdir(external) == ["secret.md"], "the plant: the folder does not list it")
            code, out, _ = world.run("--manifest-out", world.last_manifest, today="2026-10-14")
        failed_and_kept(code, out, load(world.last_manifest), "its folder unsearchable",
                        "2026-10-14")
    # the controls: back and readable, it is owed content on the reading list
    manifest, out = world.pick(today="2026-10-15")
    check(load(manifest)["complete"] is True and parse(out)["parts"].get("owed") == [secret],
          "readable: %r" % parse(out)["parts"])
    # there, though nothing of it is listed (a name the scans skip): no deletion either
    world.set_state(dict(saved, owed=[{"entry": "hooks/.DS_Store", "since": "2026-10-12"}]))
    world.write("hooks/.DS_Store", "finder\n")
    manifest, out = world.pick(today="2026-10-15")
    data = load(manifest)
    check(data["owed"] == [{"entry": "hooks/.DS_Store", "files": [], "held": [], "acquired": True,
                            "deleted": False}] and not parse(out)["parts"].get("deleted"),
          "a skipped name that is there was taken for a deletion: %r" % data["owed"])
    os.remove(world.path("hooks/.DS_Store"))
    world.set_state(saved)
    # truly absent: its own metadata reports it missing, so it is a deletion, discharged
    os.remove(secret)
    manifest, out = world.pick(today="2026-10-16")
    data = load(manifest)
    check(data["complete"] is True and parse(out)["parts"].get("deleted") == [secret]
          and data["owed"][0]["deleted"] is True, "truly absent: %r" % data["owed"])
    out = world.record(data["slice"], today="2026-10-16", manifest=manifest)
    check(world.state_data()["owed"] == [] and "owed: discharged 1 entry deleted" in out,
          "truly absent, not discharged: %s" % out[:500])


def case_broken_link_stays_owed(world):
    """T5 and T6 (g), item 6 (the fifth build review's fourth finding): a symbolic link whose target
    is missing, where an owed path is looked at, is there but unreadable. Where the owed path
    itself is such a link (the review's plant, outside the hashed roots, which no hash scan reads)
    and where an owed folder outside them holds one, the owed content fails, the pick and the
    record are incomplete, the link is never listed as owed content to read, and the entry stays
    owed. The controls stay distinct: a readable link (to a file that is there) is owed content on
    the reading list, complete; the same path truly absent is a deletion, listed and discharged.
    The walk itself, given such a link as the path it walks, records it as an error and gives no
    file (whatever walks it: a root, an owed path, a folder of the inventory), while a readable
    link gives its file and an absent path nothing, with no error."""
    world.record("standing-rules")
    external = world.path("external")
    folder = os.path.join(external, "folder")
    os.makedirs(folder)
    target = world.write("external/target.md", "# target\n")
    kept = world.write("external/folder/kept.md", "# kept\n")
    link = os.path.join(external, "broken.md")
    os.symlink(os.path.join(external, "nowhere.md"), link)
    inner = os.path.join(folder, "inner.md")
    os.symlink(os.path.join(folder, "nowhere.md"), inner)
    saved = world.state_data()
    module = load_slice()
    readable = os.path.join(external, "readable.md")
    os.symlink(target, readable)
    walks = []
    for path in (link, readable, os.path.join(external, "absent.md")):
        errors = []
        walks.append((module.walk_files(path, errors), [e[1] for e in errors]))
    os.remove(readable)
    check(walks[0][0] == [] and len(walks[0][1]) == 1
          and "symbolic link whose target is missing" in walks[0][1][0]
          and walks[1] == ([readable], []) and walks[2] == ([], []),
          "the walk of a link to nothing, a readable link and an absent path: %r" % walks)
    legs = (("the owed path itself (the review's plant)", link, []),
            ("a link inside an owed folder", folder + "/", [kept]))
    for number, (name, entry, listed) in enumerate(legs):
        today = "2026-10-%d" % (13 + number)
        world.set_state(dict(saved, owed=[{"entry": entry, "since": "2026-10-12"}]))
        manifest = world.manifest_path()
        code, out, _ = world.run("--manifest-out", manifest, today=today)
        data, result = load(manifest), parse(out)
        check(code == 3 and data["complete"] is False
              and status_of(data, "owed content") == "failed"
              and data["owed"][0]["acquired"] is False and data["owed"][0]["deleted"] is False
              and result["parts"].get("owed", []) == listed and not result["parts"].get("deleted")
              and not any(path in (link, inner) for path in data["reading"])
              and any(line.startswith("owed content: failed: ")
                      and "symbolic link whose target is missing" in line
                      for line in result["incomplete"]),
              "%s: exit %d, owed %r, parts %r: %r" % (name, code, data["owed"], result["parts"],
                                                      result["incomplete"]))
        out = world.record(data["slice"], today=today, manifest=manifest)
        stored = world.state_data()
        check({"entry": entry, "since": "2026-10-12"} in stored["owed"]
              and stored["audits"][-1]["complete"] is False and "owed: discharged" not in out,
              "%s: the record discharged it: %r %s" % (name, stored["owed"], out[:500]))
    # the controls: a readable link is owed content to read; a path truly absent is a deletion
    good = os.path.join(external, "good.md")
    os.symlink(target, good)
    gone = os.path.join(external, "gone.md")
    world.set_state(dict(saved, owed=[{"entry": good, "since": "2026-10-12"},
                                      {"entry": gone, "since": "2026-10-12"}]))
    manifest, out = world.pick(today="2026-10-16")
    data, result = load(manifest), parse(out)
    check(data["complete"] is True and status_of(data, "owed content") == "ok"
          and result["parts"].get("owed") == [good] and result["parts"].get("deleted") == [gone],
          "the controls: %r %r" % (result["parts"], data["owed"]))
    out = world.record(data["slice"], today="2026-10-16", manifest=manifest)
    check(world.state_data()["owed"] == [] and "owed: discharged" in out,
          "the controls' record: %r %s" % (world.state_data()["owed"], out[:500]))


def case_metadata_errors_never_absence(world):
    """Item 6, the sweep of every call that could turn an error into "not there": a planted
    metadata error (lstat and stat refused for one path, in this process) is a failed acquisition
    at each site, never absence: the optional root (never "absent"), an empty skills folder (the
    rotation and the inventory fail, never "no skills"), a hook with no script suffix (the
    inventory fails, never dropping it), a symbolic link to a folder (unread, never followed as a
    folder), a due row naming a link to nothing (the due rows' files fail, never "not found"), and
    the lifecycle page, the register and the log (each failed as unreadable, never "missing"). The
    control: the same pick with nothing planted is complete."""
    world.record("standing-rules")
    code, out = world.in_process()
    check(code == 0 and "acquisitions all ok" in parse(out)["summary"], "the control: %d %s"
          % (code, parse(out)["summary"]))
    optional = world.path("vault/CUSTOMISATION-definitions.md")
    runner = world.write("hooks/runner", "#!/bin/sh\necho run\n")
    os.chmod(runner, stat.S_IRWXU)
    rows = world.every_item_row() + [row(runner, kind="hook")]
    world.lifecycle(rows)
    target = world.path("linked-target")
    os.makedirs(target)
    world.write("linked-target/below.md", "# below a link\n")
    link = world.path("vault/.claude/skills/alpha/linked")
    code, out = world.in_process()
    check(code == 0, "the control with a scriptless hook enrolled: %d %s" % (code, out[-400:]))
    legs = (("the optional root", [optional], "hash scan: vault/CUSTOMISATION-definitions.md",
             "could not be looked at"),
            ("a hook with no script suffix", [runner], "inventory", "whether it is a script"),
            ("a symbolic link to a folder", [link], "hash scan: vault/.claude",
             "could not be looked at"),
            ("the lifecycle page", [world.path("vault/wiki/developments/check-lifecycle.md")],
             "lifecycle rows", "unreadable (Permission denied"),
            ("the register", [world.path("vault/wiki/developments/known-issues.md")],
             "comparison source: the register", "unreadable (Permission denied"),
            ("the log", [world.path("vault/wiki/log.md")], "comparison source: deep-lint",
             "unreadable (Permission denied"))
    real_open = open
    for number, (name, paths, acquisition, reason) in enumerate(legs):
        manifest = world.manifest_path()
        if paths == [link]:
            os.symlink(target, link)   # read as unread without the plant too; with it, never followed

        def refused_open(module, paths=paths):
            def opener(path, *args, **kwargs):
                if isinstance(path, str) and os.path.abspath(path) in paths:
                    raise PermissionError(13, "Permission denied (planted)", path)
                return real_open(path, *args, **kwargs)
            module.open = opener   # the open the script's reads go through
        try:
            with refused_metadata(paths):
                code, out = world.in_process(
                    "--manifest-out", manifest, today="2026-10-%d" % (19 + number),
                    patch=refused_open if acquisition in (
                        "lifecycle rows", "comparison source: the register",
                        "comparison source: deep-lint") else None)
        finally:
            if paths == [link]:
                os.remove(link)
        data = load(manifest)
        check(code == 3 and data["complete"] is False and status_of(data, acquisition) == "failed"
              and any(line.startswith(acquisition + ": failed: ") and reason in line
                      for line in parse(out)["incomplete"])
              and "1 optional root(s) absent" not in (parse(out)["controls"] or "")
              and "is MISSING" not in out and "(MISSING)" not in out
              and not any("alpha/linked/" in key for key in data["hashes"]),
              "%s: exit %d, %s: %r" % (name, code, acquisition, parse(out)["incomplete"]))
    # a skill's SKILL.md that is a link to nothing: the rotation fails, never drops the skill as
    # one with no SKILL.md (the link is there; what it names cannot be read)
    skill_file = world.path("vault/.claude/skills/beta/SKILL.md")
    os.remove(skill_file)
    os.symlink(world.path("vault/.claude/skills/beta/nowhere.md"), skill_file)
    manifest = world.manifest_path()
    code, out = world.in_process("--manifest-out", manifest, today="2026-10-25")
    data = load(manifest)
    check(code == 3 and status_of(data, "rotation") == "failed"
          and any(line.startswith("rotation: failed: ") and skill_file in line
                  for line in parse(out)["incomplete"]),
          "a SKILL.md linked to nothing: %d %r" % (code, [(a["name"], a["status"])
                                                         for a in data["acquisitions"]]))
    os.remove(skill_file)
    world.write("vault/.claude/skills/beta/SKILL.md", "# beta\n")
    # an empty skills folder whose metadata cannot be read: never "no skills"
    for name in ("alpha", "beta"):
        shutil.rmtree(world.path("vault/.claude/skills/" + name))
    world.lifecycle([r for r in world.every_item_row() if ".claude/skills/" not in r]
                    + [row(runner, kind="hook")])
    code, out = world.in_process(today="2026-10-26")
    check(code == 0, "the empty skills folder control: %d %s" % (code, out[-400:]))
    skills = world.path("vault/.claude/skills")
    manifest = world.manifest_path()
    with refused_metadata([skills]):
        code, out = world.in_process("--manifest-out", manifest, today="2026-10-27")
    data = load(manifest)
    check(code == 3 and status_of(data, "rotation") == "failed"
          and status_of(data, "inventory") == "failed" and "vault/.claude/skills/" in data["unread"],
          "the skills folder: %d %r" % (code, [(a["name"], a["status"]) for a in data["acquisitions"]
                                             if a["status"] != "ok"]))


def case_refusals_name_the_error(world):
    """Item 6's sweep, the refusals: a path that cannot be looked at is said to be so, never
    refused as missing, and never let through as absent. slices.json whose metadata cannot be read
    is no continuity failure (`there is no slices.json` would send the head to restore a file that
    is there); --init over one is refused, never run over it; --hooks under a folder that cannot be
    searched could not be looked at, never "not a folder"; --manifest-out cannot name the path of
    an absent optional root (the manifest would become that root) nor a path whose metadata cannot
    be read. The folder for slices.json, a required root, the vault's CLAUDE.md and the folder for
    --manifest-out whose metadata cannot be read are each said so, never called missing; and a
    temporary state the record could not remove after a refusal is named in the refusal, never
    read as removed. Planted in this process, and on the file system for any user but root."""
    world.record("standing-rules")
    before = digest(world.state)
    with refused_metadata([world.state]):
        code, out = world.in_process()
    check(code == 2 and out.startswith("REFUSED: slices.json could not be looked at")
          and "there is no slices.json" not in out and digest(world.state) == before,
          "slices.json's metadata refused: %d %s" % (code, out[:300]))
    if os.geteuid() != 0:
        with unsearchable(os.path.dirname(world.state)):
            code, out, _ = world.run()
        check(code == 2 and out.startswith("REFUSED: slices.json could not be looked at")
              and "continuity failure" not in out,
              "slices.json in a folder that cannot be searched: %d %s" % (code, out[:300]))
    os.remove(world.state)
    with refused_metadata([world.state]):
        code, out = world.in_process("--init")
    check(code == 2 and "could not be looked at" in out and not os.path.lexists(world.state),
          "--init over a path whose metadata is refused: %d %s" % (code, out[:300]))
    code, out, _ = world.run("--init")
    check(code == 0, "the --init control: %d %s" % (code, out))
    world.record("standing-rules")
    if os.geteuid() != 0:
        locked = world.path("locked")
        os.makedirs(os.path.join(locked, "hooks"))
        with unsearchable(locked):
            code, out, _ = world.run("--hooks", os.path.join(locked, "hooks"))
        check(code == 2 and "PROBE FAILED: --hooks" in out and "could not be looked at" in out
              and "is not a folder" not in out, "--hooks it cannot look at: %d %s" % (code, out))
    optional = world.path("vault/CUSTOMISATION-definitions.md")
    os.remove(optional)
    code, out, _ = world.run("--manifest-out", optional)
    check(code == 2 and "lies inside the hashed root" in out and not os.path.lexists(optional),
          "--manifest-out at the absent optional root: %d %s" % (code, out[:300]))
    manifest = world.manifest_path()
    with refused_metadata([manifest]):
        code, out = world.in_process("--manifest-out", manifest)
    check(code == 2 and "could not be looked at" in out and not os.path.lexists(manifest),
          "--manifest-out whose metadata is refused: %d %s" % (code, out[:300]))
    # the premises and the folders a run is given: each error told as an error, never as missing
    state_folder, developments = os.path.dirname(world.state), world.path("vault/wiki/developments")
    for name, paths, extra, expected, wrong in (
            ("the folder for slices.json", [state_folder], (),
             "PROBE FAILED: the folder for slices.json, %s, could not be looked at" % state_folder,
             "does not exist"),
            ("a required root", [developments], (),
             "PROBE FAILED: the required root %s could not be looked at" % developments,
             "is missing"),
            ("the vault's CLAUDE.md", [world.path("vault/CLAUDE.md")], (),
             "PROBE FAILED: the vault's CLAUDE.md could not be looked at", "holds no CLAUDE.md"),
            ("the folder for --manifest-out", [world.out],
             ("--manifest-out", os.path.join(world.out, "m.json")),
             "REFUSED: the folder for --manifest-out, %s, could not be looked at" % world.out,
             "does not exist")):
        with refused_metadata(paths):
            code, out = world.in_process(*extra)
        check(code == 2 and out.startswith(expected) and wrong not in out,
              "%s whose metadata is refused: %d %s" % (name, code, out[:300]))
    # a temporary state that cannot be removed after a refusal is said, never read as removed
    before = digest(world.state)
    folder = os.path.dirname(world.state)
    real_unlink = os.unlink

    def unlink(path, *args, **kwargs):
        name = os.path.basename(os.fsdecode(path))
        if name.startswith(".slices.json.") and name.endswith(".tmp"):
            raise PermissionError(13, "Permission denied (planted)", path)
        return real_unlink(path, *args, **kwargs)
    manifest, out = world.pick(today="2026-10-12")
    os.unlink = unlink
    try:
        code, out = world.in_process("--record", parse(out)["slice"], "--findings", "0",
                                     "--manifest", manifest, "--report", world.report(),
                                     today="2026-10-12",
                                     patch=plant_outcome("slices.json read back", "failed"))
    finally:
        os.unlink = real_unlink
    left = [n for n in os.listdir(folder) if n.endswith(".tmp")]
    check(code == 2 and out.startswith("REFUSED") and "slices.json unchanged" in out
          and "a temporary file was left at" in out and len(left) == 1
          and digest(world.state) == before, "a temporary file left after a refusal: %d %r %s"
          % (code, left, out[:400]))
    for name in left:
        os.remove(os.path.join(folder, name))


def case_listed_owed_not_read(world):
    """T6 (b) and (d): a listed owed file the reviewer names under `## Not read` stays owed, with
    its first date, and the audit is recorded incomplete; the control, a report saying `none` over
    a complete manifest, records the audit complete and discharges the listed owed reading."""
    world.record("standing-rules")
    guard = world.path("hooks/guard.py")
    restore = unreadable(world, "hooks/guard.py")
    manifest = world.manifest_path()
    try:
        code, out, _ = world.run("--manifest-out", manifest, today="2026-10-12")
    finally:
        restore()
    world.record(parse(out)["slice"], today="2026-10-12", manifest=manifest)
    manifest, out = world.pick(today="2026-10-13")
    check(load(manifest)["complete"] is True and parse(out)["parts"].get("owed") == [guard],
          "the owed file is not listed: %r" % parse(out)["parts"].get("owed"))
    out = world.record(parse(out)["slice"], today="2026-10-13", manifest=manifest,
                       not_read=[guard])
    data = world.state_data()
    check(data["audits"][-1]["complete"] is False and "INCOMPLETE AUDIT" in out
          and "the reviewer did not read 1 file(s)" in out
          and data["owed"] == [{"entry": "hooks/guard.py", "since": "2026-10-12"}]
          and "stays owed, since the reviewer did not read 1 of its 1 file(s)" in out,
          "a listed owed file left unread: %r %s" % (data["owed"], out))
    manifest, out = world.pick(today="2026-10-14")
    check(load(manifest)["complete"] is True and parse(out)["parts"].get("owed") == [guard],
          "the owed file is not listed again: %r" % parse(out)["parts"].get("owed"))
    out = world.record(parse(out)["slice"], today="2026-10-14", manifest=manifest)
    check(world.state_data()["audits"][-1]["complete"] is True
          and "owed: discharged 1 entry, listed by this audit's pick and read: hooks/guard.py"
          in out and world.state_data()["owed"] == [], "the control: %s" % out)


def case_new_debt_from_not_read(world):
    """T6 (c), the second design check's fourth finding: a listed file with no earlier debt (here
    changed this week), named under `## Not read`, becomes owed, keeps its old baseline, appears
    in the next pick with nothing further changed, and is discharged, its baseline advanced, by
    a later reading."""
    world.record("standing-rules")
    design = world.path("vault/wiki/developments/design.md")
    old = world.state_data()["baseline"]["hashes"]["vault/wiki/developments/design.md"]
    world.write("vault/wiki/developments/design.md", "# Design\n\nchanged this week\n")
    new = digest(design)
    manifest, out = world.pick()
    check(parse(out)["parts"].get("changed") == [design], "the changed file %r"
          % parse(out)["parts"].get("changed"))
    out = world.record(parse(out)["slice"], today=TODAY, manifest=manifest, not_read=[design])
    data = world.state_data()
    check(data["audits"][-1]["complete"] is False
          and data["owed"] == [{"entry": "vault/wiki/developments/design.md", "since": TODAY}]
          and data["baseline"]["hashes"]["vault/wiki/developments/design.md"] == old
          and "kept: vault/wiki/developments/design.md" in out and "newly owed" in out,
          "new debt: %r %r" % (data["owed"], out))
    result = parse(world.run(today="2026-10-25")[1])
    check(has(reading(result), "developments/design.md")
          and result["owed"] == ["vault/wiki/developments/design.md (owed since %s): 1 file(s) on "
                                 "the reading list" % TODAY],
          "the next unchanged pick: %r %r" % (reading(result), result["owed"]))
    out = world.record(result["slice"], today="2026-10-25")
    data = world.state_data()
    check(data["owed"] == [] and "owed: discharged 1 entry" in out
          and data["baseline"]["hashes"]["vault/wiki/developments/design.md"] == new,
          "the later reading: %r %s" % (data["owed"], out))


def case_report_refused(world):
    """T6 (e) and (f), the third design check's second finding: a report without the `## Not read`
    section, or one naming a path outside the slice, an empty section, a line that is neither a
    slice path nor `none`, `none` beside a path, two such sections, a heading only near it, and a
    report that cannot be read are each refused, with slices.json byte for byte unchanged; so are
    the part-reads the third build review's sweep found: a heading after the section (which a
    reader stopping there would read only in part, crediting what follows it as read) and
    undecodable bytes; and (D18) a fenced example of the section, which raw lines count as a second
    declaration. The controls: `none` and a slice path are recorded. (A section after a fenced
    block never closed, which the fence reader refused, is read on raw lines: coverage_raw_protocol,
    RETIRED_D18.)"""
    manifest, out = world.pick()
    data = load(manifest)
    first, second = data["reading"][0], data["reading"][1]
    before = digest(world.state)
    end = "END NOT READ: %d\n"
    variants = (("# Report\n## Read\nall read\n", "holds no section headed exactly `## Not read`"),
                ("## Not read\n/elsewhere/x.md\n" + end % 1, "not on this audit's reading list"),
                ("## Not read\n\n## Gaps\nnone\n", "section is empty"),
                ("# Report\n\n## Not read\n", "section is empty"),
                ("# Report\n\n## Not read\n" + end % 0, "section is empty"),
                ("## Not read\n- %s\n" % first + end % 1,
                 "neither a reading-list path nor the single word"),
                ("## Not read\nNone\n" + end % 0, "neither a reading-list path nor the single word"),
                ("## Not read\nnone\n%s\n" % first + end % 1, "puts `none` beside 1 other line(s)"),
                ("## Not read\nnone\n\n## Not read\nnone\n", "holds 2 sections"),
                ("## Not Read\nnone\n" + end % 0, "the nearest heading is '## Not Read'"),
                ("## Not read\n%s\n### owed\n%s\n" % (first, second) + end % 2,
                 "is not the report's last"),
                ("## Not read\nnone\n" + end % 0 + "\n## Afterword\n%s was skimmed\n" % second,
                 "is not the report's last"),
                ("```\n## Not read\n/x\n```\n" + NONE_READ, "holds 2 sections"))
    for text, expected in variants:
        refused_unchanged(world, ("--record", data["slice"], "--findings", "0", "--manifest",
                                  manifest, "--report", world.report(text=text)), expected, before)
    refused_unchanged(world, ("--record", data["slice"], "--findings", "0", "--manifest",
                              manifest, "--report", os.path.join(world.out, "absent.md")),
                      "cannot be read", before)
    damaged = os.path.join(world.out, "damaged-report.md")
    with open(damaged, "wb") as handle:
        handle.write(b"# Report\n\xff\xfe\n" + NONE_READ.encode("utf-8"))
    refused_unchanged(world, ("--record", data["slice"], "--findings", "0", "--manifest",
                              manifest, "--report", damaged), "cannot be read", before)
    code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest", manifest,
                             "--report", world.report(text="# Report\n\n" + NONE_READ))
    check(code == 0 and "says none" in out, "the control `none`: %d %s" % (code, out[:300]))
    manifest, out = world.pick(today="2026-10-25")
    data = load(manifest)
    code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest", manifest,
                             "--report", world.report(not_read=[data["reading"][0]]),
                             today="2026-10-25")
    check(code == 0 and "not read: %s" % data["reading"][0] in out,
          "the control with a slice path: %d %s" % (code, out[:300]))


def case_report_cut_refused(world):
    """T6 (h), item 5 (the fourth build review's second finding): the `## Not read` section closes
    with `END NOT READ: <n>`, n its path lines (0 with `none`). A report naming two owed, listed
    files cut after its first whole path line (which the earlier grammar read as complete, crediting
    the second file as read and advancing its baseline), the same section cut before its END line,
    one whose END line miscounts (both ways), one with a line after it, `none` closed with a count
    other than 0, and `none` with no END line are each refused, slices.json byte for byte
    unchanged and no temporary file left. The controls: the whole report records both files owed
    with their earlier hashes kept; `none` with `END NOT READ: 0` records complete."""
    world.record("standing-rules")
    design = world.path("vault/wiki/developments/design.md")
    world.write("vault/wiki/developments/design.md", "# Design\n\nchanged this week\n")
    world.write("vault/CUSTOMISATION.md", "# Prefs\n\n## Settings\nstyle: y\n\n## Roles\nr\n")
    custom = world.path("vault/CUSTOMISATION.md")
    saved = world.state_data()
    old = saved["baseline"]["hashes"]
    manifest, out = world.pick(today="2026-10-12")
    data = load(manifest)
    check(design in data["reading"] and custom in data["reading"], "the fixture: %r"
          % data["reading"])
    head = "# Report\n\n## Gaps\nnone\n\n## Not read\n"
    whole = head + "%s\n%s\nEND NOT READ: 2\n" % (design, custom)
    cuts = (("cut after its first whole path line", head + "%s\n" % design),
            ("cut before its END line", head + "%s\n%s\n" % (design, custom)),
            ("an END line counting one", head + "%s\n%s\nEND NOT READ: 1\n" % (design, custom)),
            ("an END line counting three", head + "%s\n%s\nEND NOT READ: 3\n" % (design, custom)),
            ("a line after its END line", head + "%s\nEND NOT READ: 1\n%s\n" % (design, custom)),
            ("none closed with a count of 1", head + "none\nEND NOT READ: 1\n"),
            ("none with no END line", head + "none\n"))
    before = digest(world.state)
    for name, text in cuts:
        code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest",
                                 manifest, "--report", world.report(text=text), today="2026-10-12")
        check(code == 2 and out.startswith("REFUSED") and "END NOT READ" in out
              and digest(world.state) == before and "RECORDED" not in out
              and not [n for n in os.listdir(os.path.dirname(world.state)) if n.endswith(".tmp")],
              "%s: exit %d, %s" % (name, code, out[:400]))
    code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest", manifest,
                             "--report", world.report(text=whole), today="2026-10-12")
    stored = world.state_data()
    check(code == 0 and stored["audits"][-1]["complete"] is False
          and sorted(e["entry"] for e in stored["owed"])
          == ["vault/CUSTOMISATION.md", "vault/wiki/developments/design.md"]
          and stored["baseline"]["hashes"]["vault/wiki/developments/design.md"]
          == old["vault/wiki/developments/design.md"]
          and stored["baseline"]["hashes"]["vault/CUSTOMISATION.md"]
          == old["vault/CUSTOMISATION.md"], "the whole report: %d %r" % (code, stored["owed"]))
    world.set_state(saved)
    code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest", manifest,
                             "--report", world.report(text=head + "none\nEND NOT READ: 0\n"),
                             today="2026-10-12")
    check(code == 0 and world.state_data()["audits"][-1]["complete"] is True,
          "the `none` control: %d %s" % (code, out[:300]))


def case_report_paths_exact(world):
    """T6 (i), item 5 (the fifth build review's first finding): path lines keep their exact
    characters, only the newline removed. Of two listed files whose names differ only by a trailing
    space, both changed since the baseline, a report naming either exactly as the reading list
    prints it keeps exactly that file's debt and old hash, while the other is read: not owed, its
    baseline advanced; the next pick with nothing further changed lists the named one alone, as
    owed. A path line with a space put before it, or added after a path, is refused with
    slices.json byte for byte unchanged. The control: whitespace around control syntax (the
    heading, `none`, the END line) is forgiven, and the report records complete."""
    rel = "vault/wiki/developments/notes.md"
    plain, spaced = world.write(rel, "# notes\n"), world.write(rel + " ", "# notes, spaced\n")
    key, spaced_key = rel, rel + " "
    world.record("standing-rules")
    saved = world.state_data()
    old = saved["baseline"]["hashes"]
    check(key in old and spaced_key in old, "the fixture's baseline: %r" % sorted(old))
    world.write(rel, "# notes, changed\n")
    world.write(rel + " ", "# notes, spaced, changed\n")
    manifest, out = world.pick(today="2026-10-12")
    data = load(manifest)
    check(plain in data["reading"] and spaced in data["reading"] and plain in raw_lines(out)
          and spaced in raw_lines(out), "the two printed paths: %r" % data["reading"])
    for named, other, named_key, other_key in ((spaced, plain, spaced_key, key),
                                               (plain, spaced, key, spaced_key)):
        world.set_state(saved)
        code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest",
                                 manifest, "--report", world.report(
                                     text="# Report\n\n## Not read\n%s\nEND NOT READ: 1\n" % named),
                                 today="2026-10-12")
        stored = world.state_data()
        check(code == 0 and stored["owed"] == [{"entry": named_key, "since": "2026-10-12"}]
              and stored["audits"][-1]["complete"] is False
              and stored["baseline"]["hashes"][named_key] == old[named_key]
              and stored["baseline"]["hashes"][other_key] == digest(other) != old[other_key],
              "naming %r: exit %d, owed %r: %s" % (named, code, stored["owed"], out[:500]))
        result = parse(world.run(today="2026-10-19")[1])
        check(named in reading(result) and other not in reading(result)
              and result["owed"] == ["%s (owed since 2026-10-12): 1 file(s) on the reading list"
                                     % named_key],
              "the next pick after naming %r: %r %r" % (named, reading(result), result["owed"]))
    world.set_state(saved)
    before = digest(world.state)
    for text in ("## Not read\n %s\nEND NOT READ: 1\n" % plain,
                 "## Not read\n%s  \nEND NOT READ: 1\n" % plain):
        refused_unchanged(world, ("--record", data["slice"], "--findings", "0", "--manifest",
                                  manifest, "--report", world.report(text=text),
                                  "--today", "2026-10-12"),
                          "REFUSED: the report", before)
    code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest", manifest,
                             "--report", world.report(text="# Report\n\n## Not read  \n  none \n"
                                                           "  END NOT READ: 0  \n"),
                             today="2026-10-12")
    check(code == 0 and world.state_data()["audits"][-1]["complete"] is True,
          "the control (whitespace around control syntax): %d %s" % (code, out[:300]))


def case_rotation_moves_on_with_omissions(world):
    """T7, the second design check's second finding: four successive audits that each leave an
    item of the slice unread (the earlier omissions left unread again) select other rotating parts
    in turn, keep every omission owed, and record each audit incomplete; the completed control
    rotates through the same parts, each complete, owing nothing."""
    weeks = ("2026-10-04", "2026-10-11", "2026-10-18", "2026-10-25")
    control = World(os.path.join(world.root, "control"))
    chosen, completed = [], []
    for week in weeks:
        manifest, out = world.pick(today=week)
        result = parse(out)
        chosen.append(result["slice"])
        rotating = result["parts"]["rotating"]
        check(rotating, "%s: the rotating part %s is empty" % (week, result["slice"]))
        owed = [world.path(e["entry"]) for e in world.state_data()["owed"]]
        omitted = [p for p in reading(result) if p in owed] + [rotating[0]]
        check(len(omitted) == len(owed) + 1, "%s: an earlier omission is not on the reading list: "
              "%r" % (week, omitted))
        world.record(result["slice"], today=week, manifest=manifest, not_read=omitted)
        manifest, out = control.pick(today=week)
        completed.append(parse(out)["slice"])
        control.record(parse(out)["slice"], today=week, manifest=manifest)
    check(chosen == ["standing-rules", "skill:alpha", "skill:beta", "register"],
          "the rotating parts under repeated omissions: %r" % chosen)
    data = world.state_data()
    check([a["complete"] for a in data["audits"]] == [False] * 4,
          "the audits: %r" % [a["complete"] for a in data["audits"]])
    check([(e["entry"], e["since"]) for e in data["owed"]]
          == [("vault/CLAUDE.md", weeks[0]), ("vault/.claude/skills/alpha/SKILL.md", weeks[1]),
              ("vault/.claude/skills/beta/SKILL.md", weeks[2]),
              ("vault/wiki/developments/known-issues.md", weeks[3])],
          "the omissions owed: %r" % data["owed"])
    check(completed == chosen and all(a["complete"] for a in control.state_data()["audits"])
          and control.state_data()["owed"] == [], "the completed control: %r %r"
          % (completed, control.state_data()["owed"]))


def case_owed_listed_until_read(world):
    """R5 under item 5: content left unread is owed, and every later pick lists it under "owed
    from an earlier audit", even restored unchanged, until the reviewer reads it: a later audit
    that is itself incomplete still discharges the owed file it listed and its reviewer read, and
    owes what its own pick could not read; a complete audit then discharges that (the control)."""
    world.record("standing-rules")
    guard = os.path.join(world.hooks, "guard.py")
    restore = unreadable(world, "hooks/guard.py")
    manifest = world.manifest_path()
    try:
        code, out, _ = world.run("--manifest-out", manifest)
    finally:
        restore()
    check(code == 3, "the first incomplete pick: %d" % code)
    world.record(parse(out)["slice"], today=TODAY, manifest=manifest)
    result = parse(world.run(today="2026-10-25")[1])
    check(result["parts"].get("owed") == [guard]
          and not has(result["parts"].get("changed", []), "hooks/guard.py"),
          "after one incomplete audit: owed %r, changed %r"
          % (result["parts"].get("owed"), result["parts"].get("changed")))
    restore = unreadable(world, "vault/.claude/skills/beta/test_beta.py")
    manifest = world.manifest_path()
    try:
        code, out, _ = world.run("--manifest-out", manifest, today="2026-10-25")
    finally:
        restore()
    check(code == 3 and parse(out)["parts"].get("owed") == [guard],
          "the second incomplete pick: %d" % code)
    out = world.record(parse(out)["slice"], today="2026-10-25", manifest=manifest)
    owed = [e["entry"] for e in world.state_data()["owed"]]
    check(owed == ["vault/.claude/skills/beta/test_beta.py"]
          and "owed: discharged 1 entry, listed by this audit's pick and read: hooks/guard.py"
          in out, "after a second incomplete audit, owed %r: %s" % (owed, out))
    result = parse(world.run(today="2026-11-01")[1])
    check(has(result["parts"].get("owed", []), "beta/test_beta.py"),
          "the owed part after two incomplete audits: %r" % result["parts"].get("owed"))
    manifest = world.manifest_path()
    code, out, _ = world.run("--manifest-out", manifest, today="2026-11-01")
    check(code == 0, "the complete pick: %d %s" % (code, out[-300:]))
    out = world.record(parse(out)["slice"], today="2026-11-01", manifest=manifest)
    check("owed: discharged 1 entry" in out and world.state_data()["owed"] == [],
          "the complete audit did not discharge the owed entry: %s" % out)
    out = world.run(today="2026-11-08")[1]
    result = parse(out)
    check(result["parts"].get("owed") == [] and result["owed"] == [] and "OWED (0 entries" in out,
          "the pick after the reading still owes: %r" % result["parts"].get("owed"))


def case_named_group_listed_then_cleared(world):
    """F4: a named group (the fixed list of groups with no file of their own, starting with
    reflection controls) is listed as missing while no row names it, and not once a row does."""
    world.lifecycle(world.every_item_row(skip=("reflection controls",)))
    code, out, _ = world.run()
    result = parse(out)
    check(code == 0 and result["missing"] == ["reflection controls | named group"],
          "the named group with no row: %d %r" % (code, result["missing"]))
    check("named group %d" % len(named_groups()) in result["controls"],
          "the inventory count %r" % result["controls"])
    world.lifecycle(world.every_item_row())
    result = parse(world.run()[1])
    check(result["missing"] == [], "the named group with its row: %r" % result["missing"])


def case_nested_skill_file_enrolled(world):
    """F5: every SKILL.md under .claude/skills, at any depth, is a standing-text item by its
    vault-relative path: a nested skill file with no row is listed, and not once its row exists."""
    world.lifecycle(world.every_item_row(skip=(NESTED_SKILL,)))
    result = parse(world.run()[1])
    check(result["missing"] == [NESTED_SKILL + " | text group"],
          "the nested skill file with no row: %r" % result["missing"])
    check(has(result["parts"].get("unregistered", []), NESTED_SKILL),
          "its file is not on the reading list")
    world.lifecycle(world.every_item_row())
    result = parse(world.run()[1])
    check(result["missing"] == [], "the nested skill file with its row: %r" % result["missing"])


def fence_filtered(lines):
    """The lines with every fenced block's lines blanked, as B-AUDIT10's fence reader read them
    (this suite's own copy of that reader's rules, kept only to plant its faults back: an opening
    up to three spaces in, three or more backticks whose rest holds none, or tildes; a closing of
    the same character, at least as long, with only spaces or tabs after it). A list item's
    indented closer opens a fence here, and a marker inside a comment is a marker, as there: the
    routes of CR-AUDIT10's F1 and F2."""
    shown, fence = [], None
    for line in lines:
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence is not None:
            if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence) \
                    and not marker.group(2).strip(" \t\r"):
                fence = None
            shown.append("")
            continue
        if marker and (marker.group(1)[0] == "~" or "`" not in marker.group(2)):
            fence = marker.group(1)
            shown.append("")
            continue
        shown.append(line)
    return shown


def case_controls_line(world):
    """Every pick prints its controls (the in-memory plants caught, the registry's, the tables' and
    the whole-input plants among them) and one summary line; the controls catch a broken registry
    (one counting a planted failure as complete), a lifecycle reader that counts a damaged table as
    whole, and a JSON reader that keeps the last of a key given twice, each run in this process:
    PROBE FAILED, exit 2. They catch the earlier builds' lenient readers too, B-AUDIT7's among them
    (revision 7): path lines stripped, deep-lint field prefixes taken for fields, and the heading
    heuristic put back, which refuses a structurally valid page ending on its table. Revision 8
    (D18): B-AUDIT10's fence filtering put back in front of each raw consumer (the coverage, the
    lifecycle page, the register and the log, each patched here with this suite's own fence filter,
    so that CR-AUDIT10's list fence and comment fences hide lines again) and the section adapter
    with its accounting removed must each fail the in-run controls too, and with markdown-it-py
    unimportable the section plants say they could not run, never refusing the pick, which is
    incomplete (exit 3), its inventory UNKNOWN. The head's choice of 14 October 2026: the old rule
    that a retired row needs a Next review too, and the exception widened until a retired row's
    other checks drop, each put back, fail the controls. (B-AUDIT8's fence reading,
    B-AUDIT8's comment reading and B-AUDIT9's fence opener patched a reader that no longer exists:
    RETIRED_D18.)"""
    code, out, _ = world.run()
    result = parse(out)
    for phrase in ("changed plant caught", "missing-row plant caught", "skip plants caught",
                   "unread plants caught",
                   "section plants caught, by markdown-it-py 4.2.0 (12: CR-AUDIT-B's "
                   "counterexample and its list-fence counterpart read whole; a fenced example no "
                   "section; a section hidden by a comment or a fence left open, a commented one, a "
                   "setext and a nested level-2 heading UNKNOWN)",
                   "rotation plants caught (an incomplete attempt moves the rotation on",
                   "registry plants caught", "coverage plants caught (32, on raw lines: a section "
                   "cut after a whole line, a wrong count, and a second declaration in a code "
                   "block, a list fence, between comment fences, in a block quote and in a comment "
                   "among them)",
                   "whole-input plants caught (a key given twice and a NaN refused",
                   "absence plants caught (a metadata error never absent; no deletion unless its "
                   "absence is established)",
                   "entry plants caught, on raw lines (a deep-lint heading alone, over a fragment, "
                   "with a field torn, misnamed, empty or borrowed across a malformed heading or "
                   "one behind a list marker, or a malformed latest heading, its bracket left open "
                   "or behind a list marker among them, and a register without its Closed section, "
                   "with a heading twice or its Closed first, are not whole; a field after "
                   "Conflicts, a log ending on a later entry's heading and a register ending on its "
                   "Closed section are structurally valid, the limit; a later heading whose title "
                   "alone names deep-lint is no deep-lint heading; a fence or a comment's opening "
                   "is text)",
                   "printing plants caught (8 lines: hidden characters escaped and decoded back, "
                   "plain lines byte for byte)",
                   "malformed plants caught (3: no Next review; a retired row with none, not "
                   "malformed; a retired row with no Retire when)",
                   "table plants caught, on raw lines (a whole row, an empty table, another table, "
                   "a page ending on its table and a table after a fence marker read; a header "
                   "alone, a broken separator, a torn row, rows in no table, a damaged header, a "
                   "quoted row, and a torn table after a list fence or comment fences each "
                   "damaged)",
                   "acquisitions 17 registered, 17 ok"):
        check(result["controls"] and phrase in result["controls"], "controls lack %r: %r"
              % (phrase, result["controls"]))
    check(out.count("SUMMARY: ") == 1 and result["summary"].startswith("SUMMARY: slice "),
          "the summary line")

    def broken(module):
        module.Registry.complete = lambda self: True
    code, out = world.in_process(patch=broken)
    check(code == 2 and out.startswith("PROBE FAILED: the registry counted"),
          "a broken registry passed the controls: %d %s" % (code, out[:300]))

    # D18: with markdown-it-py unimportable (in this process, for one pick), the section plants say
    # they could not run, the inventory, which needs the same parser, reading UNKNOWN; they never
    # refuse the pick, which stays an incomplete one (exit 3)
    saved = sys.modules.get("markdown_it")
    sys.modules["markdown_it"] = None   # an import of it now raises ImportError
    try:
        code, out = world.in_process(today="2026-10-19")
    finally:
        if saved is None:
            del sys.modules["markdown_it"]
        else:
            sys.modules["markdown_it"] = saved
    check(code == 3 and "section plants not run: markdown-it-py could not be imported" in out
          and "PROBE FAILED" not in out and "MISSING ROWS: UNKNOWN" in out,
          "the section plants with markdown-it-py unimportable: %d %s" % (code, out[-500:]))

    # the earlier builds' lenient readers, put back in this process, must each fail the controls
    def header_counts(module):
        whole = module.parse_lifecycle
        module.parse_lifecycle = lambda lines: whole(lines)[:2] + ([],)

    def lenient_json(module):
        module.strict_json = json.loads

    def heading_suffices(module):   # B-AUDIT6's deep-lint rule: any surviving heading
        whole = module.deeplint_entry
        module.deeplint_entry = lambda lines: whole(lines)[:3] + (None,)

    def cut_coverage(module):   # B-AUDIT6's coverage: no terminator, any whole prefix read
        whole = module.parse_not_read
        module.parse_not_read = lambda text, reading: whole(
            text if "END NOT READ" in text else text.rstrip("\n") + "\nEND NOT READ: %d\n"
            % sum(1 for l in text.split("## Not read", 1)[-1].split("\n")
                  if l.strip().startswith("/")), reading)

    def error_absent(module):   # B-AUDIT6's walk: an error looking at a path read as absence
        look = module.look
        module.look = lambda path, follow=True, lstat=None, stat=None: (
            ("absent", None) if look(path, follow, lstat, stat)[0] == "error"
            else look(path, follow, lstat, stat))

    def stripped_paths(module):   # B-AUDIT7's coverage: path lines stripped (CR-AUDIT7 F1)
        whole = module.parse_not_read
        module.parse_not_read = lambda text, reading: whole("\n".join(
            line.strip() if line.strip().startswith("/") else line
            for line in text.split("\n")), reading)

    def prefix_fields(module):   # B-AUDIT7's deep-lint fields: a prefix sufficed (CR-AUDIT7 F3)
        module.CHANGED_RE = re.compile(r"^- \*\*Changed\b")
        module.CONFLICTS_RE = re.compile(r"^- \*\*Conflicts\b")

    def heading_required(module):   # B-AUDIT7's heuristic: a top-level heading after the tables
        whole = module.parse_lifecycle

        def parse_lifecycle(lines):
            rows, tables, damage = whole(lines)
            last = max([n for n, line in enumerate(lines, 1) if line.strip().startswith("|")]
                       or [0])
            if tables and not any(n > last and re.match(r"^#{1,2}(\s|$)", line)
                                  for n, line in enumerate(lines, 1)):
                damage = damage + [(last, "no top-level heading after the last table")]
            return rows, tables, damage
        module.parse_lifecycle = parse_lifecycle

    # D18: B-AUDIT10's fence filtering put back in front of each raw consumer, by this suite's own
    # filter (fence_filtered); and the section adapter with its accounting removed
    def filtered_coverage(module):
        whole = module.parse_not_read
        module.parse_not_read = lambda text, paths: whole(
            "\n".join(fence_filtered(text.split("\n"))), paths)

    def filtered_lifecycle(module):
        whole = module.parse_lifecycle
        module.parse_lifecycle = lambda lines: whole(fence_filtered(lines))

    def filtered_register(module):
        whole = module.register_problem
        module.register_problem = lambda lines: whole(fence_filtered(lines))

    def filtered_deeplint(module):
        whole = module.deeplint_entry
        module.deeplint_entry = lambda lines: whole(fence_filtered(lines))

    def unaccounted_adapter(module):
        module.SECTION_LOOK_RE = re.compile(r"(?!)")

    def retired_needs_date(module):   # B-AUDIT12's rule: a retired row needed a Next review too
        whole = module.assess

        def assess(row, today):
            due, malformed = whole(row, today)
            if module.empty(row.get("next_review")) and "no Next review" not in malformed:
                malformed = ["no Next review"] + malformed
            return due, malformed
        module.assess = assess

    def retired_unchecked(module):   # the exception widened: a retired row's other checks dropped
        whole = module.assess
        module.assess = lambda row, today: (
            (None, []) if " ".join((row.get("state") or "").lower().split()) == "retired"
            else whole(row, today))
    for patch, expected in ((retired_needs_date, "PROBE FAILED: a planted retired row with no "
                                                 "Next review was called malformed"),
                            (retired_unchecked, "PROBE FAILED: a planted retired row with no "
                                                "Next review was called malformed, or its other "
                                                "checks were dropped"),
                            (header_counts, "PROBE FAILED: the lifecycle reader took a planted "
                                            "damaged table as whole"),
                            (filtered_coverage, "PROBE FAILED: the coverage parser misread a "
                                                "planted report"),
                            (filtered_lifecycle, "PROBE FAILED: the lifecycle reader"),
                            (filtered_register, "PROBE FAILED: the register reader took a planted "
                                                "register"),
                            (filtered_deeplint, "PROBE FAILED: the deep-lint reader took a planted "
                                                "heading alone"),
                            (unaccounted_adapter, "PROBE FAILED: the section adapter misread a "
                                                  "planted text"),
                            (lenient_json, "PROBE FAILED: a planted part-read input was read as "
                                           "whole"),
                            (heading_suffices, "PROBE FAILED: the deep-lint reader took a planted "
                                               "heading alone"),
                            (cut_coverage, "PROBE FAILED: the coverage parser misread a planted "
                                           "report"),
                            (error_absent, "PROBE FAILED: a planted metadata error was read as "
                                           "absence"),
                            (stripped_paths, "PROBE FAILED: the coverage parser misread a planted "
                                             "report"),
                            (prefix_fields, "PROBE FAILED: the deep-lint reader took a planted "
                                            "heading alone"),
                            (heading_required, "PROBE FAILED: the lifecycle reader misread a "
                                               "planted whole page")):
        code, out = world.in_process(patch=patch)
        check(code == 2 and out.startswith(expected), "a lenient reader passed the controls: %d %s"
              % (code, out[:300]))


def case_fixtures_honour_tmpdir(world):
    """The fixtures live under the temporary folder TMPDIR names (tempfile.gettempdir)."""
    root = os.path.realpath(tempfile.gettempdir())
    check(os.path.realpath(world.root).startswith(root + os.sep), "the fixture is not under %s"
          % root)
    if os.environ.get("TMPDIR"):
        check(root == os.path.realpath(os.environ["TMPDIR"]), "tempfile ignored TMPDIR")


def case_unknown_part_headers(world):
    """The fourth build review's observation, folded: a reading-list part whose acquisition did not
    succeed says UNKNOWN in its header (and in the summary), never a bare `(0)`, while DUE ROWS or
    MISSING ROWS say UNKNOWN: each acquisition a part rests on, planted to fail in turn, marks
    exactly the parts that rest on it. The control: a complete pick marks none."""
    world.record("standing-rules")
    code, out = world.in_process()
    headers = parse(out)["headers"]
    check(code == 0 and sorted(headers) == ["changed", "deleted", "due", "owed", "rotating",
                                            "unregistered"]
          and not any("UNKNOWN" in h for h in headers.values())
          and all(re.search(r" \(\d+\)$", h) for h in headers.values()),
          "the control: %d %r" % (code, headers))
    for number, (name, parts) in enumerate((("hash scan: hooks", ["changed"]),
                                            ("owed content", ["owed", "deleted"]),
                                            ("rotation", ["rotating"]),
                                            ("lifecycle rows", ["due", "unregistered"]),
                                            ("inventory", ["unregistered"]),
                                            ("due rows' files", ["due"]))):
        code, out = world.in_process(today="2026-10-%d" % (19 + number),
                                     patch=plant_outcome(name, "failed"))
        result = parse(out)
        marked = sorted(p for p, h in result["headers"].items() if "UNKNOWN" in h)
        check(code == 3 and marked == sorted(parts)
              and all("%s did not succeed" % name in result["headers"][p] for p in parts)
              and not any(h.endswith(" (0)") for p, h in result["headers"].items() if p in parts)
              and all(re.search(r"\b%s UNKNOWN \(\d+ listed\)" % p, result["summary"])
                      for p in parts),
              "%s: exit %d, headers %r, summary %s" % (name, code, result["headers"],
                                                       result["summary"]))


def case_hidden_characters_escaped(world):
    """The fourth build review's observation, folded under item 1's rule: paths and lifecycle cells
    slice.py prints use the command list's reversible encoding when they hold a character a
    terminal could hide. Files named with an escape, a right-to-left override and a newline, and a
    due row whose Purpose holds an escape sequence, print as `escaped: ` lines after the declaring
    `ESCAPED:` line: no output holds such a character (World.run searches every output), each
    escaped line decodes back (with this suite's own decoder) to the path or row, and the manifest
    holds the raw paths. A report naming such a path under `## Not read` as printed is accepted and
    owes that path; named raw, it is accepted too. The control: a plain path prints byte for byte."""
    rows = due_row_world(world)
    rows[-1] = rows[-1].replace("| keeps x |", "| keeps\x1b[2Kx |")
    world.lifecycle(rows)
    names = ("esc\x1bname.md", "rlo‮name.md", "line\nbreak.md")
    planted = [world.write("vault/.claude/skills/alpha/" + name, "# planted\n") for name in names]
    plain = world.write("vault/.claude/skills/alpha/plain.md", "# plain\n")
    manifest = world.manifest_path()
    code, out, _ = world.run("--manifest-out", manifest)
    lines = out.split("\n")
    escaped = [line for line in lines if line.startswith("escaped: ")]
    note = [i for i, line in enumerate(lines) if line.startswith("ESCAPED: ")]
    result = parse(out)
    data = load(manifest)
    check(code == 0 and len(note) == 1 and note[0] < lines.index(escaped[0])
          and all(path in reading(result) and path in data["reading"] for path in planted)
          and plain in lines and plain in reading(result)
          and any(d.startswith(".claude/hooks/gate.py |") and "keeps\x1b[2Kx" in d
                  for d in result["due"]),
          "exit %d, %d escaped line(s), note %r: %r" % (code, len(escaped), note, escaped[:3]))
    check(len(escaped) >= len(planted) + 1 and all("\\x1b" in e or "\\u202e" in e or "\\x0a" in e
                                                   for e in escaped),
          "the escaped lines: %r" % escaped)
    printed = [line for line in escaped if unescape(line[len("escaped: "):]) in planted]
    check(len(printed) == len(planted), "not every planted path printed escaped: %r" % printed)
    saved = world.state_data()
    for form, line in (("as printed", printed[0]), ("raw", unescape(printed[0][len("escaped: "):]))):
        world.set_state(saved)
        text = "# Report\n\n## Not read\n%s\nEND NOT READ: 1\n" % line
        code, out, _ = world.run("--record", data["slice"], "--findings", "0", "--manifest",
                                 manifest, "--report", world.report(text=text))
        raw = unescape(printed[0][len("escaped: "):])
        key = "vault/" + os.path.relpath(raw, world.vault)
        check(code == 0 and {"entry": key, "since": TODAY} in world.state_data()["owed"],
              "the report naming it %s: %d %r %s" % (form, code, world.state_data()["owed"],
                                                     out[:400]))


def case_whole_input_declared(world):
    """Item 6 (revision 6, restated by revision 7), the declared table: every acquisition states in
    the code the structural rules its input must meet. Each acquisition a pick and a record
    register (the read-back of the new state and the rescan among them) has its row in slice.py's
    WHOLE_INPUT, and every row there names an acquisition one of them registers; the planted
    control, an acquisition with no row, is caught. Revision 7: no row names a removed heuristic
    (a heading after a table or section, a count of enrolled sections, a closing field or last
    line), the four acquisitions that read unframed Markdown pages (UNFRAMED) each name the limit
    in their rows and no other row does, and the pick declares its three `limit:` lines. Revision 8
    (D18): no row promises a fence or a comment closed, each raw consumer's row (the lifecycle
    rows, the two comparison sources and the coverage) says it reads raw lines, and the inventory's
    row names markdown-it-py and the adapter's declared syntax."""
    module = load_slice()
    names = []
    original = module.Registry.acquire

    def acquire(self, name, what, affects):
        if what != "a plant":   # the in-run controls' registry plants are no acquisition
            names.append(name)
        return original(self, name, what, affects)
    module.Registry.acquire = acquire
    world.record("standing-rules")
    manifest = world.manifest_path()
    with contextlib.redirect_stdout(io.StringIO()):
        codes = [module.main(world.argv(["--manifest-out", manifest])),
                 module.main(world.argv(["--record", "skill:alpha", "--findings", "0", "--manifest",
                                         manifest, "--report", world.report()]))]
    check(codes == [0, 0], "the pick and the record: %r" % codes)
    names = sorted(set(names))
    lacking = [n for n in names if module.whole_input_row(n) is None]
    unused = [row[0] for row in module.WHOLE_INPUT
              if not any(n == row[0] or (row[0].endswith(": ") and n.startswith(row[0]))
                         for n in names)]
    check(not lacking and not unused and len(names) >= 20,
          "%d acquisitions; with no WHOLE_INPUT row %r; rows naming none %r" % (len(names), lacking,
                                                                              unused))
    check(module.whole_input_row("a planted acquisition") is None
          and module.whole_input_row("rescan: hooks") is not None,
          "the planted control: an acquisition with no row was not caught")
    # revision 7: each row names only rules its structure decides; the four acquisitions that read
    # an unframed Markdown page say so, and no row names a removed heuristic
    rows = dict(module.WHOLE_INPUT)
    heuristics = ("after the last table", "heading (`#` or `##`) after", "enrols", "(the count)",
                  "last entry", "bullet as its last line", "closing with", "followed by another")
    check(not [(name, h) for name, text in rows.items() for h in heuristics if h in text],
          "a WHOLE_INPUT row names a removed heuristic: %r"
          % [(name, h) for name, text in rows.items() for h in heuristics if h in text])
    # revision 8 (D18): no fence or comment is interpreted by hand, so no row promises one closed;
    # each raw consumer's row says it reads raw lines, and the inventory's names the adapter
    raw = ("lifecycle rows", module.COMPARISON[0], module.COMPARISON[1], "coverage")
    check(not [name for name, text in rows.items()
               if "comment left open" in text or "fence left open" in text]
          and all("raw lines, every one read" in rows[name] for name in raw)
          and "markdown-it-py 4.2.0" in rows["inventory"]
          and "adapter's declared syntax" in rows["inventory"],
          "a WHOLE_INPUT row promises a fence or comment closed, a raw consumer's row does not "
          "say it reads raw lines, or the inventory's does not name the adapter: %r"
          % dict((name, rows[name]) for name in raw + ("inventory",)))
    unframed = [name for name, pages in module.UNFRAMED]
    check(sorted(unframed) == sorted(["lifecycle rows", "inventory", module.COMPARISON[0],
                                      module.COMPARISON[1]])
          and all("THE LIMIT" in rows[name] for name in unframed)
          and not [name for name in rows if name not in unframed and "THE LIMIT" in rows[name]],
          "the unframed acquisitions and their rows: %r" % unframed)
    check(sorted(module.LIMIT_LINES) == ["due rows", "missing rows", "sources"]
          and all(line.startswith("limit: ") for line in module.LIMIT_LINES.values()),
          "the pick's limit lines: %r" % sorted(module.LIMIT_LINES))


# ------------------------------------------------------------------ the truncation test -------

def prefix(parts, lines):
    """The first `lines` whole lines of a text split at its newlines (its last part empty)."""
    return "".join(part + "\n" for part in parts[:lines])


def removed_from(parts, lines):
    """The first non-blank line a cut after `lines` lines removes, or None."""
    return next((part for part in parts[lines:-1] if part.strip()), None)


def pick_outcome(world, acquisition, value, patch=None):
    """(the named acquisition's outcome, what the pick derived from it) of one pick in this
    process."""
    manifest = world.manifest_path()
    code, out = world.in_process("--manifest-out", manifest, patch=patch)
    check(code in (0, 3) and os.path.isfile(manifest), "a truncation's pick: %d %s" % (code,
                                                                                   out[-300:]))
    return status_of(load(manifest), acquisition), value(world, parse(out), out)


def lifecycle_value(world, result, out):
    return (result["due"], result["why"], result["malformed"], result["missing"],
            re.search(r"lifecycle rows parsed \S+", result["controls"] or "").group(0))


def register_value(world, result, out):
    """The register's note, and the text of the two sections its acquisition reads (it returns no
    content of its own, so what it vouches for is compared), each without its trailing newlines."""
    path = world.path(REGISTER_REL)
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    sections = re.split(r"(?m)^(?=## )", text)
    # its note, as a second-pass source or (when a cut makes it the changed slice) as the slice
    notes = [re.sub(r"^.*?%s" % re.escape(path), "", line) for line in raw_lines(out)
             if line.startswith(("- the register: ", "not a second-pass source: the register"))]
    notes = [re.search(r"\(([^()]*)\)$", n).group(1) if re.search(r"\(([^()]*)\)$", n) else ""
             for n in notes]
    return (notes, [s.rstrip("\n") for s in sections if s.startswith(("## Open", "## Closed"))])


def deeplint_value(world, result, out):
    return [line for line in raw_lines(out) if line.startswith("- deep-lint's latest report: ")]


def standing_value(world, result, out):
    return (result["missing"], re.search(r"sections read: [^;]*", result["controls"] or "").group(0))


# This suite's own reading of the structural rules revision 8 (D18) names for each input, written
# apart from slice.py's, in another shape (string tests where slice.py has regular expressions):
# the raw pages and the report by their literal-line protocols over every raw line, with no fence
# or comment filtering anywhere; the standing-rules files by the sections written by hand for each
# fixture (standing_reading), never by markdown-it. A reader that accepts a cut breaking one of
# them is called FAIL, never the limit or harmless.
SEPARATOR_LINE = re.compile(r"^\|(\s*:?-{3,}:?\s*\|)+$")
RAW_KINDS = ("lifecycle", "register", "log")   # unframed raw pages: the limit applies
UNFRAMED_KINDS = RAW_KINDS + ("standing",)   # unframed Markdown: the limit
FRAMED_KINDS = ("report", "json")   # framed inputs: the reviewer's report, a manifest (no limit)


def container_rest(line):
    """The line with any leading run of spaces, tabs, `>` marks and list markers (`-`, `*`, `+`,
    `1.`, `1)`) taken off: this suite's reading of a line's container prefix."""
    rest = line
    while True:
        rest = rest.lstrip(" \t")
        if rest.startswith(">"):
            rest = rest[1:]
            continue
        marker = re.match(r"[-*+]|\d{1,9}[.)]", rest)
        if marker is None:
            return rest
        rest = rest[marker.end():]


def declares_not_read(line):
    """Whether a raw line declares `## Not read` in any form: after its container prefix, one to
    six `#`, then, after spaces or tabs, the words `not` and `read` (any case, spaces or tabs
    between them) as the heading's first words."""
    rest = container_rest(line)
    hashes = len(rest) - len(rest.lstrip("#"))
    words = re.split(r"[ \t]+", rest[hashes:].lstrip(" \t"))
    return 1 <= hashes <= 6 and len(words) >= 2 and words[0].lower() == "not" \
        and re.match(r"(?i)read\b", words[1]) is not None


def closes_not_read(line):
    """Whether a raw line reads as the section's closing line in any form: no path line (which
    begins with `/`), and its first words, after any characters but letters and digits, `end`,
    `not` and `read`, in any case, with nothing but such characters between them."""
    if line.startswith("/"):
        return False
    rest = line
    for word in ("end", "not", "read"):
        rest = re.sub(r"^\W+", "", rest)
        if not rest.lower().startswith(word):
            return False
        rest = rest[len(word):]
    return not rest or not (rest[0].isalnum() or rest[0] == "_")


def report_problem(lines):
    """The report's frame, by this suite's reading of the coverage protocol (D18): exactly one line
    of the whole report declares `## Not read`, and it is exactly `## Not read`; exactly one line
    reads as a closing line, exactly `END NOT READ: <n>`, after the heading and the report's last
    line but blank ones; between them no heading and only `none` (alone) or path lines, n the path
    lines (0 with `none`). A cut that loses the END line, or leaves it miscounted, has lost its
    frame."""
    declared = [i for i, line in enumerate(lines) if declares_not_read(line)]
    if len(declared) != 1:
        return "%d lines declare `## Not read`" % len(declared)
    head = declared[0]
    if lines[head].rstrip() != "## Not read":
        return "its declaration is not exactly `## Not read`"
    closing = [i for i, line in enumerate(lines) if closes_not_read(line)]
    if len(closing) != 1:
        return "%d closing lines" % len(closing)
    end = closing[0]
    if end < head or end != max(i for i, line in enumerate(lines) if line.strip()):
        return "its closing line before its heading, or not the report's last"
    match = re.match(r"^END NOT READ: (0|[1-9][0-9]*)$", lines[end].strip())
    if match is None:
        return "its closing line not exactly `END NOT READ: <n>`"
    body = [line for line in lines[head + 1:end] if line.strip()]
    if not body:
        return "an empty `## Not read` section"
    if any(re.match(r"^#{1,6}(\s|$)", line) for line in body):
        return "a heading after its `## Not read` section"
    if any(line.strip() == "none" for line in body):
        return None if len(body) == 1 and match.group(1) == "0" else "`none` not alone or not 0"
    if any(not line.startswith(("/", "escaped: ")) for line in body):
        return "a line neither a path nor `none`"
    return None if int(match.group(1)) == len(body) else "a count that does not match its path lines"


def table_cells(text):
    """The cells of a table line, by this suite's own reading of the lifecycle protocol's cell
    rule, written apart from slice.py's (CR-AUDIT13 F3: this reading cut at every pipe, the
    protocol at unescaped ones only, so the two disagreed on a header holding `\\|`). A pipe is
    escaped when the character just before it is a backslash: it is then text of its cell, never a
    boundary. The line's outer whitespace goes, then its opening pipe, then its closing pipe unless
    that one is escaped; the rest is read one character at a time, each unescaped pipe ending a
    cell; each cell loses its outer whitespace."""
    body = text.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    cells, current, before = [], [], ""
    for char in body:
        if char == "|" and before != "\\":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        before = char
    cells.append("".join(current).strip())
    return cells


def lifecycle_problem(lines):
    """The lifecycle page by this suite's reading of its raw protocol (D18): blocks of consecutive
    lines that start with a pipe after spaces or tabs; a block headed exactly HEADER needs its
    separator of ten cells and whole rows; a block with no separator is rows in no table; a block
    with a separator whose header has ten cells or a `Next review` cell (its cells cut at unescaped
    pipes only: table_cells), yet is not HEADER, is a damaged lifecycle header; a pipe line behind
    `>` marks is a quoted row; one lifecycle table at least."""
    blocks = []
    for number, line in enumerate(lines):
        bare = line.lstrip(" \t")
        if bare.startswith(">") and bare.lstrip(" \t>").startswith("|"):
            return "a table line inside a block quote"
        if not bare.startswith("|"):
            continue
        if blocks and blocks[-1][-1][0] == number - 1:
            blocks[-1].append((number, line.strip()))
        else:
            blocks.append([(number, line.strip())])
    tables = 0
    for block in blocks:
        second = block[1][1].replace(" ", "") if len(block) > 1 else ""
        separator = SEPARATOR_LINE.match(second) is not None
        if block[0][1] != HEADER:
            if not separator:
                return "table rows outside a table"
            cells = table_cells(block[0][1])
            if len(cells) == 10 or "next review" in [cell.lower() for cell in cells]:
                return "a damaged lifecycle header"
            continue
        tables += 1
        if not separator or second.count("|") - 1 != 10:
            return "a lifecycle header without its separator of ten cells"
        if any(len(text_) < 2 or not text_.endswith("|") or text_.endswith("\\|")
               for _, text_ in block[2:]):
            return "a torn row"
    return None if tables else "no lifecycle table"


def register_heading(line):
    """`Open` or `Closed` when a raw line is that register heading (`## `, the word, spaces
    forgiven between and after), else None."""
    text = line.rstrip(" \t\r")
    if not text.startswith("## "):
        return None
    word = text[3:].strip(" \t")
    return word if word in ("Open", "Closed") else None


def kind_at(text, at):
    """Whether the kind deep-lint, however written (`deep`, then spaces, tabs, `-` or `_` or
    nothing, then `lint`, in any letter case), stands at `at` in `text`, a word at its end."""
    if text[at:at + 4].lower() != "deep":
        return False
    at += 4
    while at < len(text) and text[at] in " \t-_":
        at += 1
    if text[at:at + 4].lower() != "lint":
        return False
    at += 4
    return at == len(text) or not (text[at].isalnum() or text[at] == "_")


def names_deeplint(line):
    """Whether a raw line names a deep-lint heading in any form (D18, as CR-AUDIT11 F1 widens it):
    after its container prefix (spaces, tabs, `>` marks, list markers), a run of `#`, then the kind
    deep-lint standing before the heading's title: starting before its first `|` (anywhere when it
    holds none), or at its first letter, whatever its date field became (a bracket left open, a
    date in another shape, a stray `|`, none). A kind named only after the `|`, in a title, does
    not count."""
    rest = container_rest(line)
    hashes = len(rest) - len(rest.lstrip("#"))
    if hashes == 0:
        return False
    text = rest[hashes:]
    title = text.find("|")
    if any(kind_at(text, at) for at in range(len(text) if title < 0 else title)):
        return True
    first = next((at for at, char in enumerate(text) if char.isascii() and char.isalpha()), None)
    return first is not None and kind_at(text, first)


def deeplint_problem(lines):
    """deep-lint's latest entry by this suite's reading of its raw protocol (D18): the last line
    naming a deep-lint heading in any form is in the exact form, and before the next line that
    begins with `#` after its container prefix (spaces, tabs, `>` marks, list markers) its body
    holds the complete Changed and Conflicts fields, each with a value."""
    named = [i for i, line in enumerate(lines) if names_deeplint(line)]
    if not named:
        return "no deep-lint entry"
    last = named[-1]
    if re.match(r"^## \[\d{4}-\d{2}-\d{2}\] deep-lint \|", lines[last]) is None:
        return "a malformed latest deep-lint heading"
    end = next((i for i in range(last + 1, len(lines))
                if container_rest(lines[i]).startswith("#")), len(lines))
    body = lines[last + 1:end]
    for name in ("Changed", "Conflicts"):
        if not any(re.match(r"^- \*\*%s\*\*:[ \t]*\S" % name, line) for line in body):
            return "deep-lint's latest entry without its complete %s field" % name
    return None


def unique_pairs(pairs):
    """A JSON object's pairs as a dict, refusing a key given twice (this suite's strict JSON)."""
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError("a key given twice")
    return dict(pairs)


def refuse_constant(name):
    raise ValueError("a non-JSON constant %s" % name)


def structure_problem(kind, text):
    """The first structural rule the input `text` breaks, by its kind, or None, by this suite's
    own readings (D18): the raw pages by their literal-line protocols (`lifecycle`, `register`,
    `log`: lifecycle_problem, the register's two headings once each with Open first,
    deeplint_problem), the reviewer's report by the coverage protocol (`report`: report_problem),
    a manifest as one JSON document parsed whole, strictly (`json`). No reading here filters a
    fence or a comment. The standing-rules files have no such reading: their oracle is the
    sections written by hand (standing_reading)."""
    if kind == "json":
        try:
            json.loads(text, object_pairs_hook=unique_pairs, parse_constant=refuse_constant)
        except ValueError as error:
            return "not one whole JSON document (%s)" % str(error)[:60]
        return None
    if kind not in RAW_KINDS + ("report",):
        raise Failure("no structural reading for an input of kind %r" % (kind,))
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if kind == "report":
        return report_problem(lines)
    if kind == "lifecycle":
        return lifecycle_problem(lines)
    if kind == "register":
        headings = [register_heading(line) for line in lines]
        opens = [i for i, h in enumerate(headings) if h == "Open"]
        closes = [i for i, h in enumerate(headings) if h == "Closed"]
        if len(opens) != 1 or len(closes) != 1:
            return "not one `## Open` and one `## Closed` (%d, %d)" % (len(opens), len(closes))
        return None if opens[0] < closes[0] else "its `## Closed` before its `## Open`"
    return deeplint_problem(lines)


def sections_read(seen, file_name):
    """The count of sections a standing-rules value (standing_value) says the pick read in
    `file_name`."""
    match = re.search(r"%s (\d+)" % re.escape(file_name), seen[1])
    check(match is not None, "no section count for %s in %r" % (file_name, seen[1]))
    return int(match.group(1))


def classify(status, seen, base, kind, text, standing=None):
    """T5 (revision 7, as the replacement's first review's F2 corrects it, and revision 8), one cut
    of an input of `kind` whose cut text is `text`: `caught` when the acquisition did not succeed
    or the run refused. Otherwise the cut was accepted, and its structure and frame are decided
    first, by this suite's own reading, so that an equal outcome never excuses them. A standing-
    rules file (`standing` is (its name, standing_reading's result)): FAIL when the cut leaves a
    heading-like line hidden in a fence it left open (lexer-hidden evidence: CR-AUDIT-B finding 3,
    never the limit), when it holds no section, or when the pick read another number of sections
    than the cut holds (a partial list accepted); else harmless when the outcome is the whole
    file's, the limit otherwise. Any other input: FAIL when it breaks a structural rule or, for a
    framed input, lost its frame (the report's END line, a manifest's whole JSON); then `harmless`
    when it gives exactly the whole input's outcome (an intact frame with only dispensable trailing
    material gone); `limit` when an unframed raw page so left gives another (the stated limit); and
    `FAIL` when a framed input does."""
    if status != "ok":
        return "caught"
    if kind == "standing":
        name, kept = standing
        if not kept or sections_read(seen, name) != len(kept):
            return "FAIL"
        return "harmless" if seen == base else "limit"
    if structure_problem(kind, text) is not None:
        return "FAIL"
    if seen == base:
        return "harmless"
    return "limit" if kind in UNFRAMED_KINDS else "FAIL"


def truncate_each_line(world, rel, acquisition, value, kind, patch=None):
    """T5 (revision 7, revision 8): the fixture file `rel` cut after each whole line in turn (0 to
    all but one), each cut run through a pick and classified against the whole file's outcome
    (classify: `kind` names the input's structural reading, a standing-rules file's being
    standing_reading over the whole file). The whole file is put back after. Returns [(lines kept,
    class, the first line removed)]."""
    path = world.path(rel)
    with open(path, "rb") as handle:
        whole = handle.read()
    text_whole = whole.decode("utf-8")
    parts = text_whole.split("\n")
    check(parts[-1] == "", "%s does not end with a newline" % rel)
    if kind == "standing":
        check(standing_reading(rel, text_whole, len(parts) - 1) == list(STANDING_SECTIONS[rel]),
              "the whole %s does not hold its sections as written by hand" % rel)
    else:
        check(structure_problem(kind, text_whole) is None, "the whole %s breaks a structural rule: "
              "%s" % (rel, structure_problem(kind, text_whole)))
    base = pick_outcome(world, acquisition, value, patch)
    check(base[0] == "ok", "the whole %s: its acquisition %s is %s, so a truncation has nothing "
          "to differ from" % (rel, acquisition, base[0]))
    found = []
    try:
        for lines in range(len(parts) - 1):
            text = prefix(parts, lines)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            status, seen = pick_outcome(world, acquisition, value, patch)
            reading = ((os.path.basename(rel), standing_reading(rel, text_whole, lines))
                       if kind == "standing" else None)
            found.append((lines, classify(status, seen, base[1], kind, text, reading),
                          removed_from(parts, lines)))
    finally:
        with open(path, "wb") as handle:
            handle.write(whole)
    return found


def truncation_world(world):
    """The truncation test's fixture: limit_world's (the third build review's interior cuts: two
    lifecycle tables under their own top-level headings, the due row in the second; CLAUDE.md with
    a further line in enrolled section 3 and an unenrolled section 4; a log whose query entry
    carries a Run field after its Conflicts, then a newer deep-lint entry, which here carries a
    Meter field after its own Conflicts, as the live log's entry of 8 September does), with the
    standard register and CUSTOMISATION.md, each of the five pages ending in RAW_EXAMPLES (a fenced
    heading-like line, a list fence and a comment: text to the raw consumers, read by markdown-it
    for the standing-rules files). Returns ([(input, rel, acquisition, value, kind)], {rel: whole
    text})."""
    whole = limit_world(world, meter=True, examples=True)
    return ([("the lifecycle page", LIFECYCLE_REL, "lifecycle rows", lifecycle_value, "lifecycle"),
             ("the register", REGISTER_REL, "comparison source: the register", register_value,
              "register"),
             ("deep-lint's log", LOG_REL, "comparison source: deep-lint", deeplint_value, "log"),
             ("CLAUDE.md", "vault/CLAUDE.md", "inventory", standing_value, "standing"),
             ("CUSTOMISATION.md", "vault/CUSTOMISATION.md", "inventory", standing_value,
              "standing")], whole)


def record_cuts(world, path, run, kind):
    """The record's input at `path` (the report, `kind` `report`, or the manifest, `json`: framed
    inputs) cut after each whole line, each recorded from a saved state by `run`, and classified
    (classify): caught when the record refuses; FAIL when an accepted cut lost its frame or breaks
    a structural rule, whatever it recorded; harmless when, its frame intact, it records exactly
    what the whole input records; else FAIL (a framed input has no limit). The whole file is put
    back after."""
    with open(path, "rb") as handle:
        whole = handle.read()
    parts = whole.decode("utf-8").split("\n")
    base = run()
    check(base[0] == "ok", "the whole %s did not record" % path)
    found = []
    try:
        for lines in range(len(parts) - 1):
            text = prefix(parts, lines)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            status, seen = run()
            found.append((lines, classify(status, seen, base[1], kind, text),
                          removed_from(parts, lines)))
    finally:
        with open(path, "wb") as handle:
            handle.write(whole)
    return found


def record_inputs(world, patch=None):
    """(the two-path report's path, the `none` report's path, the manifest's path, run): a pick of
    the truncation world, a report naming its first two reading-list paths, and one saying `none`;
    run(report) records the given report (the two-path one by default) with that manifest from the
    saved state, returning (`ok` or `refused`, what the record stored)."""
    saved = world.state_data()
    manifest, out = world.pick(today="2026-10-19")
    data = load(manifest)
    owed = [p for p in data["reading"][:2]]
    report = world.report(text="# Report\n\n## Gaps\nnone\n\n## Not read\n%s\nEND NOT READ: %d\n"
                          % ("\n".join(owed), len(owed)))
    none = world.report(text="# Report\n\n## Gaps\nnone\n\n" + NONE_READ)

    def run(path=None):
        world.set_state(saved)
        code, out = world.in_process("--record", data["slice"], "--findings", "0", "--manifest",
                                     manifest, "--report", path or report, today="2026-10-19",
                                     patch=patch)
        stored = world.state_data()
        return ("refused" if code == 2 else "ok",
                (stored["owed"], [a["complete"] for a in stored["audits"]],
                 stored["baseline"]["hashes"] if stored["baseline"] else None))
    return report, none, manifest, run


def truncation_table(world, patch=None):
    """{input: [(lines kept, class, first line removed)]} over every text input a pick reads, and
    over the record's (slices.json, the manifest, and the report in both its shapes: two paths
    not read, and `none`), each cut after every whole line (T5, revision 7: caught, harmless, limit
    or FAIL)."""
    table = {}
    inputs, _ = truncation_world(world)
    with open(world.state, "rb") as handle:
        state_bytes = handle.read()   # as the record wrote it, one JSON value over many lines
    for name, rel, acquisition, value, kind in inputs:
        table[name] = truncate_each_line(world, rel, acquisition, value, kind, patch)
    report, none, manifest, run = record_inputs(world, patch)
    table["the report"] = record_cuts(world, report, run, "report")
    table["the report (none)"] = record_cuts(world, none, lambda: run(none), "report")
    table["the manifest"] = record_cuts(world, manifest, run, "json")
    whole = state_bytes
    parts = whole.decode("utf-8").split("\n")
    check(len(parts) > 10 and parts[-1] == "", "slices.json as written holds %d line(s)"
          % (len(parts) - 1))
    found = []
    try:
        for lines in range(len(parts) - 1):
            with open(world.state, "w", encoding="utf-8") as handle:
                handle.write(prefix(parts, lines))
            code, out = world.in_process(patch=patch)
            found.append((lines, "caught" if code == 2 and "slices.json" in out else "FAIL",
                          removed_from(parts, lines)))
    finally:
        with open(world.state, "wb") as handle:
            handle.write(whole)
    table["slices.json"] = found
    return table


def interior_cuts(whole):
    """The third build review's three interior cuts in the truncation world, as (input, lines
    kept): the lifecycle page cut just after its second top-level heading, CLAUDE.md cut inside its
    enrolled section 3, and the log cut after its query entry's Conflicts, before its Run field."""
    def line_of(rel, anchor):
        lines = whole[rel].split("\n")
        check(lines.count(anchor) == 1, "the interior cut's anchor %r" % anchor)
        return lines.index(anchor)
    return [("the lifecycle page", line_of(LIFECYCLE_REL, "## Hooks") + 1),
            ("CLAUDE.md", line_of("vault/CLAUDE.md", "rule three") + 1),
            ("deep-lint's log", line_of(LOG_REL, "- **Run**: run-x"))]


# T5's controls: planted lenient readers, each with the in-run controls off so that the harness
# alone must find it (lenient_controls).
def lenient_quiet(module):
    module.run_controls = lambda *args, **kwargs: []


def lenient_heading_suffices(module):   # B-AUDIT6's deep-lint rule: any surviving heading
    whole_entry = module.deeplint_entry
    module.deeplint_entry = lambda lines: whole_entry(lines)[:3] + (None,)
    lenient_quiet(module)


def lenient_header_counts(module):   # a lifecycle header alone, or a torn table, read as a table
    whole_page = module.parse_lifecycle
    module.parse_lifecycle = lambda lines: whole_page(lines)[:2] + ([],)
    lenient_quiet(module)


def lenient_cut_coverage(module):   # B-AUDIT6's coverage: no terminator, any whole prefix read
    whole_section = module.parse_not_read
    module.parse_not_read = lambda text, reading: whole_section(
        text if "END NOT READ" in text else text.rstrip("\n") + "\nEND NOT READ: %d\n"
        % sum(1 for l in text.split("## Not read", 1)[-1].split("\n")
              if l.strip().startswith("/")), reading)
    lenient_quiet(module)


def lenient_adapter_unaccounted(module):   # the section adapter with its accounting removed: it
    module.SECTION_LOOK_RE = re.compile(r"(?!)")   # returns markdown-it's list, whatever it hides
    lenient_quiet(module)


def cuts_breaking(text, kind, problem):
    """The cuts of `text` (lines kept, each after a whole line, as the harness cuts it) whose
    structure breaks with `problem`, by this suite's own reading (structure_problem)."""
    parts = text.split("\n")
    return [kept for kept in range(len(parts) - 1)
            if (structure_problem(kind, prefix(parts, kept)) or "").startswith(problem)]


def lenient_controls(root):
    """T5's controls, each run over a truncation world of its own under `root`: a planted lenient
    reader (its in-run controls off) through the harness, with the cuts it must class FAIL named
    from the cut texts by this suite's own reading, never from the classes the harness gave (the
    replacement's first review, CR-AUDIT8 F2: each named cut, not merely some cut per reader).
    Returns [(reader, input, [(lines kept, class, first line removed)], named cuts)]: B-AUDIT6's
    deep-lint reader on each cut leaving the latest deep-lint heading without its two complete
    fields; a header-only lifecycle reader on each cut leaving a lifecycle header without its
    separator; the section adapter with its accounting removed (markdown-it's list returned
    whatever it hides) on each cut of CLAUDE.md leaving a heading-like line hidden in a fence the
    cut left open (lexer-hidden evidence, CR-AUDIT-B finding 3: revision 8's control, in place of
    B-AUDIT9's fence opener, retired with the fence reader: RETIRED_D18); and B-AUDIT6's
    terminator-lenient coverage reader on the two-path report cut after its paths (and after its
    first path) and on the `none` report cut to `## Not read` and `none`, each with no END line."""
    results = []
    for number, (reader, name, patch) in enumerate((
            ("B-AUDIT6's deep-lint reader (a surviving heading suffices)", "deep-lint's log",
             lenient_heading_suffices),
            ("a header-only lifecycle reader (a header alone, or a torn table, read as a table)",
             "the lifecycle page", lenient_header_counts),
            ("the section adapter without its accounting (markdown-it's list, whatever it hides)",
             "CLAUDE.md", lenient_adapter_unaccounted))):
        control = World(os.path.join(root, "control-%d" % number))
        inputs, whole = truncation_world(control)
        rel, acquisition, value, kind = [entry[1:] for entry in inputs if entry[0] == name][0]
        rows = truncate_each_line(control, rel, acquisition, value, kind, patch)
        if kind == "log":
            named = cuts_breaking(whole[rel], kind, "deep-lint's latest entry without its complete")
        elif kind == "lifecycle":
            named = cuts_breaking(whole[rel], kind, "a lifecycle header without its separator")
        else:
            named = [kept for kept in range(len(whole[rel].split("\n")) - 1)
                     if standing_reading(rel, whole[rel], kept) is None]
        results.append((reader, name, rows, named))
    control = World(os.path.join(root, "control-report"))
    truncation_world(control)
    report, none, _, run = record_inputs(control, lenient_cut_coverage)
    for name, path, runner, end in (("the report", report, run, "END NOT READ: 2"),
                                    ("the report (none)", none, lambda: run(none),
                                     "END NOT READ: 0")):
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        check(lines.count(end) == 1, "the report's END line %r" % end)
        # cut after its paths, so with no END line (and the two-path report after its first path)
        named = [lines.index(end)] + ([lines.index(end) - 1] if end.endswith("2") else [])
        rows = record_cuts(control, path, runner, "report")
        results.append(("B-AUDIT6's coverage reader (no END NOT READ line needed)", name, rows,
                        named))
    return results


def case_truncation_every_line(world):
    """T5 (revision 7, with the replacement's two reviews folded, and revision 8's protocols): each
    text input, cut after every whole line in turn, is classed caught (the acquisition fails or the
    run refuses); else, the cut accepted, FAIL when it breaks a structural rule or lost its frame,
    decided first by this suite's own reading so that no equal outcome excuses it (CR-AUDIT8 F2);
    harmless when it then gives exactly the whole input's outcome; limit when an unframed Markdown
    page (the lifecycle page, the register, the log, CLAUDE.md or CUSTOMISATION.md) so left gives
    another; FAIL when a framed input does. The suite fails on any FAIL. The inputs: the five pages
    as the pick reads them, each ending in RAW_EXAMPLES (a fenced heading-like line, a list fence, a
    comment), and the reviewer's report in both its shapes (two paths not read, and `none`), the
    manifest and slices.json as the record reads them (framed inputs: no limit; the record's
    temporary state is cut at every line in commit_after_read_back, and the event log in
    test_pass_order.py). Revision 8: the raw pages and the report are read by this suite's raw
    protocols, the standing-rules files by their sections written by hand (standing_reading): a cut
    of either file that leaves a heading-like line hidden in a fence the cut left open is lexer-
    hidden evidence (CR-AUDIT-B finding 3), FAIL if accepted, never the limit, and must be caught;
    one whose open fence, list fence or comment hides no such line is a valid shorter file. The
    classifier's own rule on the reviews' equal-outcome cases: a report cut before its END line,
    CR-AUDIT10 F1's report, cut JSON, a register whose example gives `## Open` twice, a log whose
    latest deep-lint heading is malformed, CR-AUDIT10 F1's torn table and a standing-rules file with
    hidden evidence, no section or a partial list are FAIL though the outcome is equal, while a
    report losing only a trailing blank line and a register ending on a comment opened after text or
    on a fence left open stay harmless, and a valid shorter page with another outcome the limit. The
    third build review's three interior cuts read as the limit; on the raw pages every example cut
    is accepted, nothing being interpreted; every input has caught cuts; no framed input has a limit;
    every cut of slices.json is caught. The controls (lenient_controls), each a planted lenient reader
    whose named cuts must every one be FAIL: B-AUDIT6's deep-lint reader on the 7 cuts leaving the
    latest deep-lint heading without its two fields, a header-only lifecycle reader on the 2 cuts
    leaving a header alone, the adapter without its accounting on the 2 cuts of CLAUDE.md leaving a
    heading-like line hidden, and B-AUDIT6's terminator-lenient coverage reader on the two-path
    report cut after its paths and after its first path and on the `none` report cut to
    `## Not read` and `none`."""
    same, other = ("the whole input's outcome",), ("another outcome",)
    report_whole = "# Report\n\n## Gaps\nnone\n\n" + NONE_READ
    two = ((), "sections read: CLAUDE.md 2, CUSTOMISATION.md 2")
    one = ((), "sections read: CLAUDE.md 1, CUSTOMISATION.md 2")
    for kind, text, seen, base, expected, what, standing in (
            ("standing", "", one, two, "FAIL", "a standing-rules file accepted with a heading-like "
             "line hidden in a fence the cut left open (lexer-hidden evidence)", ("CLAUDE.md", None)),
            ("standing", "", one, two, "FAIL", "a standing-rules file accepted with no section",
             ("CLAUDE.md", [])),
            ("standing", "", one, two, "FAIL", "a partial list accepted (the cut holds 2 sections, "
             "the pick read 1)", ("CLAUDE.md", ["## 1. One", "## 2. Two"])),
            ("standing", "", two, two, "harmless", "a standing-rules file with the whole outcome",
             ("CLAUDE.md", ["## 1. One", "## 2. Two"])),
            ("standing", "", one, two, "limit", "a valid shorter standing-rules file",
             ("CLAUDE.md", ["## 1. One"])),
            ("report", "# Report\n\n## Not read\nnone\n", same, same, "FAIL",
             "the `none` report cut before its END line", None),
            ("report", "## Not read\n/v/a.md\n/v/b.md\n", same, same, "FAIL",
             "a two-path report cut after its paths", None),
            ("report", "- ```\n  ```\n\n## Not read\n/v/a.md\nEND NOT READ: 1\n\n- ```\n  ```\n\n"
             + NONE_READ, same, same, "FAIL", "CR-AUDIT10 F1's report (two declarations)", None),
            ("json", '{\n  "a": 1,\n', same, same, "FAIL", "a manifest cut inside its object", None),
            ("register", "## Open\n- a\n## Closed\n``` not `a` fence\n```\n", same, same,
             "harmless", "a register ending on a fence left open (raw lines: text)", None),
            ("register", "## Open\n- a\n## Closed\n```\n## Open\n```\n", same, same, "FAIL",
             "a register whose example gives `## Open` twice", None),
            ("register", "## Open\n- a\n## Closed\ntext <!-- cut here\n", same, same, "harmless",
             "a register ending on a comment opened after text", None),
            ("log", "## [2026-01-01] deep-lint | a\n- **Changed**: x\n- **Conflicts**: none\n"
             "## [2026-01-02] deep-lint\n", same, same, "FAIL",
             "a log whose latest deep-lint heading is malformed (never the older entry)", None),
            ("lifecycle", "%s\n%s\n\n- ```\n  ```\n\n%s\n%s\n| x\n" % (HEADER, SEPARATOR, HEADER,
                                                                     SEPARATOR), same, same,
             "FAIL", "CR-AUDIT10 F1's torn table after a list fence", None),
            ("report", report_whole, same, same, "harmless",
             "a whole report with only a trailing blank line cut", None),
            ("report", report_whole, other, same, "FAIL", "a whole report recording otherwise",
             None),
            ("lifecycle", "%s\n%s\n" % (HEADER, SEPARATOR), other, same, "limit",
             "a valid shorter lifecycle page with another outcome", None),
            ("register", "## Open\n- a\n## Closed\n", same, same, "harmless",
             "a valid register with the whole outcome", None)):
        got = classify("ok", seen, base, kind, text, standing)
        check(got == expected, "the classifier gave %s %r, %s expected" % (what, got, expected))
    check(classify("refused", same, same, "report", "") == "caught", "a refusal not caught")
    world = World(os.path.join(world.root, "whole"))
    table = truncation_table(world)
    fails = dict((name, [(lines, first) for lines, kind, first in rows if kind == "FAIL"])
                 for name, rows in table.items())
    counts = dict((name, dict((k, sum(1 for _, kind, _ in rows if kind == k))
                              for k in ("caught", "harmless", "limit", "FAIL")))
                  for name, rows in table.items())
    check(not any(fails.values()), "truncations FAIL (neither caught, harmless nor the limit): %r; "
          "counts %r" % (dict((n, f[:3]) for n, f in fails.items() if f), counts))
    check(all(counts[n]["caught"] > 0 for n in counts)
          and all(counts[n]["limit"] == 0 for n in ("the report", "the report (none)",
                                                    "the manifest", "slices.json"))
          and counts["slices.json"]["caught"] == len(table["slices.json"]),
          "the counts: %r" % counts)
    whole = {}
    pages = (("the lifecycle page", LIFECYCLE_REL), ("the register", REGISTER_REL),
             ("deep-lint's log", LOG_REL), ("CLAUDE.md", "vault/CLAUDE.md"),
             ("CUSTOMISATION.md", "vault/CUSTOMISATION.md"))
    for _, rel in pages:
        with open(world.path(rel), encoding="utf-8") as handle:
            whole[rel] = handle.read()   # each put back whole after its cuts
    for name, kept in interior_cuts(whole):
        check(table[name][kept][:2] == (kept, "limit"),
              "the interior cut of %s after %d line(s): %r" % (name, kept, table[name][kept]))
    for name, rel in pages:
        cuts = example_cuts(whole[rel])
        if rel in STANDING_SECTIONS:   # markdown-it: hidden evidence caught, nothing hidden valid
            check(table[name][cuts["hidden heading"]][:2] == (cuts["hidden heading"], "caught"),
                  "%s cut after %d line(s), its example heading hidden in a fence left open: %r"
                  % (name, cuts["hidden heading"], table[name][cuts["hidden heading"]]))
            shapes = ("fence opener", "list opener", "comment opener")
            hidden = [k for k in range(len(whole[rel].split("\n")) - 1)
                      if standing_reading(rel, whole[rel], k) is None]
            check(hidden and all(table[name][k][1] == "caught" for k in hidden),
                  "%s: its lexer-hidden cuts %r are classed %r, each must be caught"
                  % (name, hidden, [table[name][k][1] for k in hidden]))
        else:   # raw lines: no shape is interpreted, so every example cut is accepted
            shapes = ("fence opener", "hidden heading", "list opener", "comment opener")
        for shape in shapes:
            check(table[name][cuts[shape]][0] == cuts[shape]
                  and table[name][cuts[shape]][1] in ("harmless", "limit"),
                  "%s cut after %d line(s), just after its %s, nothing hidden: %r"
                  % (name, cuts[shape], shape, table[name][cuts[shape]]))
    for reader, name, rows, named in lenient_controls(world.root):
        classes = dict((kept, kind) for kept, kind, _ in rows)
        check(named and all(classes.get(kept) == "FAIL" for kept in named),
              "%s over %s: its named cuts %r are classed %r, each must be FAIL"
              % (reader, name, named, [classes.get(kept) for kept in named]))
        # the log's three deep-lint entries each cut after its heading and after each field before
        # its Conflicts (2 + 3 + 2); the lifecycle page's two tables each cut after its header;
        # CLAUDE.md's two fenced examples each cut after its heading-like line
        check(len(named) == {"deep-lint's log": 7, "the lifecycle page": 2,
                             "CLAUDE.md": 2}.get(name, len(named)),
              "%s: %d named cuts" % (name, len(named)))


# ------------------------------------------------------------------ the procedure texts ------

def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def flat(text):
    return " ".join(text.split())


def brief_block():
    match = re.search(r"^```\n(.*?)^```$", read_text(BRIEF_MD), re.S | re.M)
    check(match is not None, "brief-audit.md holds no fenced brief")
    return match.group(1)


def brief_sections():
    sections, name = {}, None
    for line in brief_block().splitlines():
        match = re.match(r"^(TASK|PASS 1|PASS 2|SCOPE|GRANTS|DECISIONS|VERIFICATION|REPORT)\b",
                         line)
        if match:
            name = match.group(1)
            sections[name] = []
        if name:
            sections[name].append(line)
    return dict((k, flat("\n".join(v))) for k, v in sections.items())


def audit_sections():
    sections, name = {}, None
    for line in read_text(AUDIT_MD).splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            sections[name] = []
        elif name:
            sections[name].append(line)
    return dict((k, "\n".join(v)) for k, v in sections.items())


def audit_steps():
    steps, number = {}, None
    for line in audit_sections().get("Steps", "").splitlines():
        match = re.match(r"^(\d+)\. ", line)
        if match:
            number = int(match.group(1))
            steps[number] = []
        if number is not None:
            steps[number].append(line)
    return dict((k, flat("\n".join(v))) for k, v in steps.items())


def audit_table():
    """Step 6's outcome table: {outcome: its row, flattened}, the outcome read from the first
    cell's italics."""
    rows = {}
    for line in read_text(AUDIT_MD).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.strip().startswith(
            "|") else []
        if len(cells) == 3:
            match = re.match(r"^\*([a-z ]+)\*$", cells[0])
            if match:
                rows[match.group(1)] = flat(" ".join(cells[1:]))
    return rows


def case_brief_pass1_is_a_message(world):
    """S1: the reviewer writes no file; pass 1 ends in one PASS 1 FINDINGS message sent before any
    step-6 source opens, repeated unchanged in the report; the verification line asks it to
    confirm that order."""
    sections = brief_sections()
    whole = flat(read_text(BRIEF_MD)) + " " + flat(read_text(AUDIT_MD))
    check("pass1.md" not in whole and "{{SCRATCH}}" not in whole,
          "a first-pass file or a scratch slot survives")
    step5 = re.search(r"\b5\. (.*?) Reading list", sections.get("PASS 1", ""))
    check(step5 is not None, "PASS 1 has no step 5")
    step5 = step5.group(1)
    for phrase in ("one message", "first line is exactly `PASS 1 FINDINGS`", "P1-1, P1-2",
                   "its evidence", "what is wrong and why it matters", "steps 3 and 4",
                   "last line is `END PASS 1: <n> findings`", "before any step-6 source",
                   "write no file"):
        check(phrase in step5, "step 5 lacks %r: %s" % (phrase, step5))
    check("PASS 1 FINDINGS message" in sections.get("PASS 2", "").split(".")[0],
          "PASS 2 does not open on the message being sent: %s" % sections.get("PASS 2", "")[:120])
    check("you write no file anywhere" in sections.get("SCOPE", "")
          and "Writes: none" in sections.get("GRANTS", ""), "SCOPE or GRANTS still grant a write")
    check("Confirm that your PASS 1 FINDINGS message came before the first command that opened a "
          "step-6 source" in sections.get("VERIFICATION", ""),
          "the verification line: %s" % sections.get("VERIFICATION", ""))
    check(re.search(r"## Pass 1 findings \(the PASS 1 FINDINGS list, repeated unchanged\)",
                    sections.get("REPORT", "")), "the report does not repeat the list unchanged")
    spawn = [line for line in read_text(AUDIT_MD).splitlines() if "codex-lane.py spawn" in line]
    check(len(spawn) == 1 and "--write" not in spawn[0], "the spawn still grants a write: %r"
          % spawn)


def case_audit_reviewer_lane(world):
    """S3: the reviewer is lane RV-AUDIT of run run-<YYYYMMDD>-audit, scratch
    /tmp/run-<YYYYMMDD>-audit-RV-AUDIT, spawned with --delegation multi --delegation-src head."""
    text = read_text(AUDIT_MD)
    spawn = [line for line in text.splitlines() if "codex-lane.py spawn" in line]
    check(len(spawn) == 1, "%d spawn lines" % len(spawn))
    for flag in ("--run run-<YYYYMMDD>-audit ", "--lane RV-AUDIT ", "--class critic ",
                 "--cwd /tmp/run-<YYYYMMDD>-audit-RV-AUDIT ", "--delegation multi ",
                 "--delegation-src head ", "--brief /tmp/run-<YYYYMMDD>-audit/brief-RV-AUDIT.md "):
        check(flag in spawn[0], "the spawn line lacks %r" % flag)
    for line in text.splitlines():
        if "codex-lane.py wait" in line or "codex-lane.py watch" in line:
            check("--lane RV-AUDIT`" in line, "a wait or watch line names another lane: %s" % line)
    check("audit-AUDIT" not in text and "--lane AUDIT " not in text and "lane `AUDIT`" not in text,
          "the old lane id AUDIT survives")
    check("/tmp/run-<YYYYMMDD>-audit-RV-AUDIT" in audit_steps().get(2, ""), "step 2's scratch")
    check("lane RV-AUDIT of run {{RUN_ID}}" in flat(brief_block()), "the brief's lane id")


def case_four_labels(world):
    """S7, item 9: pass 2 labels new kind, new instance, recurrence or known; the counts line
    carries all four in the brief and in AUDIT.md; the eight-quiet-audits rule counts new kinds
    only, and its number carries "set by judgement, unmeasured"."""
    pass2 = brief_sections().get("PASS 2", "")
    positions = [pass2.find(label) for label in ("`new kind`:", "`new instance`:", "`recurrence`:",
                                                  "`known`:")]
    check(all(p >= 0 for p in positions) and positions == sorted(positions),
          "the four labels in order: %r" % positions)
    known = pass2[positions[3]:]
    check("an open register entry already describes this very fault in this place" in known
          and "name the entry and its date" in known, "the known label's definition: %s"
          % known[:200])
    check("no finding can then be labelled `new kind`" in pass2,
          "the brief does not withhold `new kind` when a source is missing: %s" % pass2[:300])
    counts = "new kinds k · new instances i · recurrences r · known n"
    check(counts in brief_sections().get("REPORT", ""), "the brief's counts line")
    check("counts: " + counts in flat(audit_sections().get("Steps", "")), "AUDIT.md's counts line")
    quiet = flat(audit_sections().get("Quiet audits and cost", ""))
    check("eight in a row with no new kind of fault (set by judgement, unmeasured)" in quiet
          and "Only new kinds count" in quiet, "the quiet rule: %s" % quiet)


def case_audit_procedure_follows(world):
    """S8, item 9: AUDIT.md has an Install section (--init once, the suites once); step 1 picks
    with --manifest-out; step 6 lists the reviewer's commands with pass_order.py over its run
    record (and --whole-run on frozen copies); step 10 records with --manifest and --report."""
    sections = audit_sections()
    install = flat(sections.get("Install", ""))
    check("slice.py --init" in install and "test_slice.py" in install
          and "test_pass_order.py" in install and "once" in install, "the Install section: %s"
          % install[:300])
    steps = audit_steps()
    check(sorted(steps) == list(range(1, 11)), "steps %r" % sorted(steps))
    check("mkdir -p /tmp/run-<YYYYMMDD>-audit" in steps[1]
          and "--manifest-out /tmp/run-<YYYYMMDD>-audit/manifest.json" in steps[1],
          "step 1: %s" % steps[1][:300])
    check("--init" in steps[1] and "continuity failure" in steps[1],
          "step 1 does not say what a missing slices.json means")
    check("**3:** the slice printed, but the pick is incomplete" in steps[1]
          and "`INCOMPLETE` block" in steps[1] and "UNKNOWN, never as none" in steps[1]
          and "required root" in steps[1] and "no manifest is written" in steps[1]
          and "`DUE ROWS: UNKNOWN`" in steps[1] and "`LABELS LIMITED`" in steps[1]
          and "**1:**" not in steps[1], "step 1's exit codes: %s" % steps[1][:600])
    check(re.search(r"pass_order\.py --events \S+/run-<YYYYMMDD>-audit-events-RV-AUDIT\.log`",
                    steps[6]) and "--whole-run" in steps[6] and "frozen copies" in steps[6]
          and "<SOURCES>" not in steps[6] and "--source" not in steps[6]
          and "--forbid" not in steps[6], "step 6: %s" % steps[6][:500])
    for phrase in ("**Exit 0, `COMMANDS BEFORE THE FIRST-PASS MESSAGE: <n>`:**",
                   "**Exit 1, `COULD NOT READ`:**", "**Exit 3, `NO FIRST-PASS MESSAGE`:**",
                   "**Exit 2, `PROBE FAILED`:**", "in the order each started, one entry per "
                   "execution, each verbatim", "one outcome, with a one-line reason"):
        check(phrase in steps[6], "step 6 lacks %r" % phrase)
    check(re.search(r"--manifest /tmp/run-<YYYYMMDD>-audit/manifest\.json --report "
                    r"\S+/run-<YYYYMMDD>-audit-report-RV-AUDIT\.md`", steps[10])
          and "--record <slice> --findings <N>" in steps[10], "step 10: %s" % steps[10][:300])
    check("`BASELINE KEPT` lines" in steps[10] and "`kept:`" in steps[10]
          and "`absent:`" in steps[10], "step 10 does not say what the baseline keeps")
    check("grep -n -e" not in flat(read_text(AUDIT_MD)), "the old grep order check survives")


def case_register_slice_texts(world):
    """F1: the brief's "open nothing else" line excepts the register when it is the slice; its
    register variant reads it in pass 1 as the object, never as a step-6 source; step 6 of the
    brief reads exactly the sources slice.py listed; step 3 of AUDIT.md copies them, two in the
    register's week."""
    pass1, pass2 = brief_sections().get("PASS 1", ""), brief_sections().get("PASS 2", "")
    check("Open nothing else in this pass: no register (unless the register is this audit's slice"
          in pass1, "the open-nothing-else line does not except the register slice: %s"
          % pass1[:300])
    variant = re.search(r"\[register slice\](.*?) 3\. ", pass1)
    check(variant is not None and "this pass's object, never a step-6 source" in variant.group(1)
          and "Step 6 does not list it" in variant.group(1),
          "the register variant: %s" % (variant.group(1) if variant else pass1[:300]))
    check("{{PASS2_SOURCES" in pass2 and "SECOND-PASS SOURCES" in pass2 and "exactly these" in pass2
          and "{{REGISTER_PATH}}" not in pass2, "step 6 does not read the printed sources: %s"
          % pass2[:300])
    steps = audit_steps()
    check("SECOND-PASS SOURCES" in steps[3] and "two when the slice is the register" in steps[3]
          and "marks included" in steps[3], "step 3's pass-2 sources: %s" % steps[3][:300])


def case_audit_cost_record(world):
    """F6: AUDIT.md records the head's share as well as the reviewer's: a usage reading before step
    1 and another after step 10 (read-usage.py, by its full path), the reviewer's tokens and time
    from its close line, and `unmeasured` for any share the readings cannot separate."""
    section = audit_sections().get("Steps", "")
    command = r"`python3 -B <vault>/\.claude/skills/delegate/read-usage\.py --only both`"
    readings = [m.start() for m in re.finditer(command, section)]
    first_step = section.find("\n1. **Pick the slice.**")
    last_step = section.find("\n10. **Record the audit:**")
    check(len(readings) == 2 and 0 <= readings[0] < first_step < last_step < readings[1],
          "the two usage readings are not before step 1 and after step 10: %r, steps at %d, %d"
          % (readings, first_step, last_step))
    cost = audit_steps().get(9, "")
    for phrase in ("the reviewer's tokens and time from its close line", "the head's share",
                   "written `unmeasured`", "the two usage readings, before step 1 and after step 10"):
        check(phrase in cost, "step 9's cost lines lack %r: %s" % (phrase, cost[:400]))
    quiet = flat(audit_sections().get("Quiet audits and cost", ""))
    check("the reviewer's and the head's" in quiet and "each week's list length and outcome" in quiet,
          "the first four audits' cost: %s" % quiet)


def case_audit_outcome_table(world):
    """T9's suite part, items 4 and 9: step 6's table names the four outcomes, each with its
    labelling, and the register-as-slice rule; the definition of earlier answers and the
    source-boundary note stand beside it; step 9's report stores the outcome and its reason; the
    late-read question on frozen copies asks about the live file, not the second-pass sources."""
    table = audit_table()
    check(sorted(table) == ["independent", "not independent", "unavailable", "unresolved"],
          "the table's outcomes: %r" % sorted(table))
    check("In a week whose rotating part is the register, reading the register is slice reading."
          in table["independent"], "the register-as-slice rule: %r" % table["independent"])
    check("labels `new kind` and `new instance` are void" in table["not independent"]
          and "each substantive finding the head verifies against the files themselves is kept, "
          "labelled by the head" in table["not independent"]
          and "Treated as not independent for labelling, with the reason recorded" in table[
              "unresolved"] and "Treated as not independent for labelling" in table["unavailable"],
          "the labelling of each outcome: %r" % table)
    step6 = audit_steps().get(6, "")
    for phrase in ("Earlier answers are the known-issues register, earlier audit outputs",
                   "the withheld entries of a smoke test, whenever that file is not part of the "
                   "week's slice", "*independent* is a source boundary only",
                   "labels such findings `known`",
                   "the question for each later command is not whether it read a second-pass "
                   "source but whether it could have read the live file a frozen copy stands in "
                   "for"):
        check(phrase in step6, "step 6 lacks %r" % phrase)
    check("`outcome: <independent | not independent | unresolved | unavailable> · <reason>"
          in audit_steps().get(9, ""), "step 9 does not store the outcome and its reason")


def case_audit_texts_hold_no_verdict(world):
    """T8: no line of AUDIT.md reads as a verdict on the first pass, and every output of slice.py
    this suite made was searched as it was made (the count shown at the end). The search's
    controls: planted verdicts, the held procedure's own phrasing among them, are caught, and the
    new procedure's outcome words pass."""
    planted = ("its clear result means only that no literal mention was found in the log, never "
               "that the first pass was blind", "**Exit 0, `PASS-ORDER CLEAR`:**",
               "PASS-ORDER UNDECIDED", "the first pass was independent")
    check(all(verdict_lines(line) for line in planted), "the search misses a planted verdict: %r"
          % [line for line in planted if not verdict_lines(line)])
    passed = ("| *independent* | No listed command read outside the week's slice |",
              "Exit 1, `COULD NOT READ`", "an unclear note")
    check(not [line for line in passed if verdict_lines(line)], "the search flags plain lines")
    check(not verdict_lines(read_text(AUDIT_MD)), "AUDIT.md holds a verdict line: %r"
          % verdict_lines(read_text(AUDIT_MD)))
    before = SEARCHED["outputs"]
    world.run()
    check(SEARCHED["outputs"] == before + 1, "the outputs are not searched as they are made")


def case_audit_steps_follow_r5(world):
    """R5 under items 5 to 7 in the procedure: step 1 says what makes a pick incomplete (a
    required root gone when an acquisition's walk reads it, which a later restore cannot undo)
    and what the owed part is; step 9's report holds the owed list and the coverage; step 10
    records an incomplete audit as incomplete and attempted, its unread content owed until the
    reviewer reads it, and discharges only what the pick listed and the reviewer read."""
    steps = audit_steps()
    for phrase in ("A required root that was gone when an acquisition's walk read it is unread",
                   "a root restored after the pick does not undo that",
                   "`owed from an earlier audit`", "`OWED` block",
                   "stay owed until the reviewer reads them"):
        check(phrase in steps[1], "step 1 lacks %r" % phrase)
    check("the owed list: each entry of step 1's `OWED` block" in steps[9]
          and "whether the pick was complete" in steps[9]
          and "the report's `## Not read` section" in steps[9], "step 9: %s" % steps[9][:400])
    for phrase in ("The audit is recorded complete only when its pick was complete and the section "
                   "says `none`", "`INCOMPLETE AUDIT` line", "counts every recorded audit as "
                   "attempted, complete or not", "until the reviewer reads it",
                   "`owed: discharged`", "only when this audit's pick listed its content and the "
                   "reviewer read all of it", "Never guess what the reviewer read"):
        check(phrase in steps[10], "step 10 lacks %r" % phrase)


def case_brief_plain_commands(world):
    """Item 8 (the pin moved from R7): pass 1 asks the reviewer for plain commands with literal
    absolute paths, with no shell variables, braces, globs or inline programs, for the current
    reason: every command before the PASS 1 FINDINGS message is listed verbatim for the head's
    judgement, and one whose reads its text does not show makes the week's first pass unresolved.
    The removed check's reason is gone, the report ends with the exact `## Not read` section (with
    no heading after it, and naming each deleted path whose references were not checked, as item
    5 of revision 5 reads, closed by its `END NOT READ: <n>` line, as revision 6 reads, each path
    character for character, as revision 7's T6 (i) reads), the reading list's six parts are named
    with what a deleted path asks for (nothing left to read: gone, or a folder holding no file),
    and the rest of step 1 stays."""
    pass1 = brief_sections().get("PASS 1", "")
    check("In this pass, run plain commands with literal absolute paths: no shell variables, "
          "braces, globs or inline programs" in pass1
          and "Every command you run before your PASS 1 FINDINGS message is listed, verbatim, for "
          "the head, who judges from its text alone what it read" in pass1
          and "a command whose reads its text does not show (inline code, a variable, a glob) "
          "cannot be judged, and makes that week's first pass unresolved" in pass1,
          "pass 1 lacks the plain-command line: %s" % pass1[:900])
    check("The order check cannot read any other form" not in flat(read_text(BRIEF_MD))
          and "refers each such command to the head" not in flat(read_text(BRIEF_MD)),
          "the removed check's reason survives")
    check("A page on the reading list that records earlier reviews is the object under review"
          in pass1 and "Open nothing else in this pass" in pass1, "the rest of step 1 changed")
    report = brief_sections().get("REPORT", "")
    check("## Not read (last, headed exactly so, with no heading after it: every reading-list file "
          "you did not read in full, and every path listed as deleted whose references you did not "
          "check, one per line, its path exactly as the reading list gives it, character for "
          "character (a space it ends with included), with nothing else on the line, no bullet and "
          "no quotes; or the single word `none` alone, when you read every one; then, as the "
          "report's last line, `END NOT READ: <n>`, n the number of path lines above it, 0 with "
          "`none`, so that a report cut short is never read as complete)" in report
          # D18: the other mandatory inputs may be named, and each line is written once, nowhere
          # else, since the record counts it on raw lines wherever it stands
          and report.endswith("In that last section, name too each requirement file and each "
                              "step-6 source you did not read in full, by its path exactly as this "
                              "brief gives it; any path you name makes this audit incomplete. "
                              "Write the heading `## Not read` and the `END NOT READ` line once "
                              "each, there and nowhere else in your report, not even quoted, in a "
                              "list or inside a code block: the record reads every line of your "
                              "report, counts each such line wherever it stands, and refuses a "
                              "report that holds a second."),
          "the report's `## Not read` section: %s" % report[-600:])
    check("its six parts in order). A path under the part `deleted since its baseline` has nothing "
          "left to read (it is gone, or it is a folder, listed with its trailing `/`, that holds "
          "no file): check instead what still refers to it" in pass1,
          "the reading list's parts: %s" % pass1[-700:])
    scope = brief_sections().get("SCOPE", "")
    check("the head reads every command you ran before that message" in scope
          and "the order check reads your commands" not in scope, "the scope line: %s" % scope)


def case_audit_states_the_limit(world):
    """Item 6 (revision 7), the provisional replacement: AUDIT.md states the limit (an unframed
    Markdown page, the lifecycle page, the register, CLAUDE.md, CUSTOMISATION.md or wiki/log.md,
    cut so that it stays structurally valid cannot be told from the page alone) and its backstops
    (the hash scan, by which a page cut since the last audit reads as changed, and step 7's label
    check against the register, the only one for the log), step 1 names the structural rules each
    source must meet and none of the removed heuristics (nor, as amended, a comment closed, nor, by
    revision 8, a fence closed: AUDIT.md names its reading protocols, and a section hidden by what
    a cut left open as no case of the limit), and the pick's output ends each part that
    rests on such a page (DUE ROWS, MISSING ROWS, SECOND-PASS SOURCES) with its `limit:` line, in a
    complete pick and in an incomplete one alike."""
    steps = audit_steps()
    for phrase in ("**What no pick can see (the limit):** the lifecycle page, the register, "
                   "CLAUDE.md, CUSTOMISATION.md and `wiki/log.md` are unframed Markdown",
                   "no such page can show by its syntax that it lost only later material",
                   "a cut that leaves a structurally valid shorter page cannot be told from the "
                   "page alone, wherever it falls",
                   "the `limit:` line that ends its DUE ROWS, MISSING ROWS and SECOND-PASS SOURCES "
                   "parts", "the hash scan, by which a page cut since the last audit reads as "
                   "changed", "CLAUDE.md and CUSTOMISATION.md then join the reading list",
                   "step 7's label check against the register, the only backstop for "
                   "`wiki/log.md`, which is not hashed",
                   "Neither restores a row a cut took from the lifecycle page",
                   "a deep-lint heading whose entry lacks its complete `- **Changed**:` or "
                   "`- **Conflicts**:` field, each followed by a value",
                   "a register without its `## Open` or `## Closed` section",
                   "a path that could not be looked at (a permission refused, say) is a failure, "
                   "never absent, as is a symbolic link whose target is missing"):
        check(phrase in steps[1], "step 1 lacks %r" % phrase)
    whole = flat(read_text(AUDIT_MD))
    for removed in ("no top-level section after its last table",
                    "a log whose last entry does not close", "section after its `## Closed`",
                    "lacking a section a lifecycle row enrols", "ending on an empty heading",
                    "cut exactly at an entry or section boundary",
                    # revision 7 as amended: no comment is checked, so none is promised closed
                    "every fence and comment closed", "closed fences and comments",
                    # revision 8 (D18): no fence is interpreted by hand either
                    "every fence closed by CommonMark's fence rules", "a fenced block never closed",
                    "strict text, closed fences"):
        check(removed not in whole, "AUDIT.md still states a removed rule: %r" % removed)
    check("each Markdown input read by its protocol (Reading protocols, below: no fence, comment, "
          "list or quote can hide a line from the four raw readers" in whole
          and "strict text, raw lines, whole tables" in steps[1]
          and "A section hidden by what a cut left open (a fence, a comment) is not that limit"
          in steps[1], "AUDIT.md does not state the raw protocols, or that hidden evidence is no "
          "limit")
    check("is also a backstop for the limit of step 1, and the only one for `wiki/log.md`"
          in steps[7], "step 7 does not name itself the log's backstop: %s" % steps[7][:400])
    code, out, _ = world.run()
    check(code == 0 and sorted(limit_lines(out)) == sorted(p for p, _ in LIMIT_STARTS),
          "the complete pick's limit lines: %d %r" % (code, limit_lines(out)))
    lines = limit_lines(out)
    for part, phrase in (("DUE ROWS", "named among the files held for the second pass above"),
                         ("MISSING ROWS", "reads as changed and is on the reading list"),
                         ("SECOND-PASS SOURCES", "step 7's label check against the register")):
        check(phrase in lines[part] and "cannot be told from the" in lines[part]
              and "AUDIT.md, step" in lines[part], "the %s limit line: %r" % (part, lines[part]))
    page = world.path(LIFECYCLE_REL)
    os.chmod(page, 0)
    try:
        code, out, _ = world.run(today="2026-10-19")
    finally:
        os.chmod(page, stat.S_IRUSR | stat.S_IWUSR)
    check((code == 3 or os.geteuid() == 0)
          and sorted(limit_lines(out)) == sorted(p for p, _ in LIMIT_STARTS),
          "the incomplete pick's limit lines: %d %r" % (code, limit_lines(out)))


def deletion_checks():
    """AUDIT.md step 3's two checks of a path listed as deleted, as written there: the commands in
    backticks that name `<path>`, each split as a shell would split it (its quotes read)."""
    commands = re.findall(r"`(/[^`]*<path>[^`]*)`", audit_steps().get(3, ""))
    check(len(commands) == 3, "step 3's deletion checks: %r" % commands)
    return [shlex.split(command) for command in commands]


# What AUDIT.md step 6 asks the reviewer's report to show of each path listed as deleted (the
# replacement's first review, CR-AUDIT8 F3), matching step 3's two checks.
STEP6_DELETED = ("each deleted path confirmed to have nothing left to read: absent, or an existing "
                 "folder whose reviewable listing is empty")


def step6_deleted_kinds():
    """(the clause, the kinds of evidence it accepts) of AUDIT.md step 6's check of a path listed
    as deleted, read from its words: `absent` (step 3's absent check), and `folder` when it accepts
    an existing folder whose reviewable listing is empty (step 3's folder check)."""
    match = re.search(r"each deleted path confirmed ([^.]*)", audit_steps().get(6, ""))
    check(match is not None, "step 6 names no check of a deleted path")
    clause, kinds = match.group(1), set()
    if re.search(r"\babsent\b", clause):
        kinds.add("absent")
    if "an existing folder whose reviewable listing is empty" in clause:
        kinds.add("folder")
    return clause, kinds


def run_check(argv, path):
    """One deletion check over `path`: (exit, what it printed)."""
    done = subprocess.run([path if part == "<path>" else part for part in argv],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                          timeout=TIMEOUT_S)
    return done.returncode, done.stdout + done.stderr


def case_deleted_entries_controls(world):
    """Items 5 and 8 with the fourth and fifth build reviews' fifth findings: a week whose reading
    list lists a deleted path completes both content controls honestly. AUDIT.md (step 3) and the
    brief apply CONTROL+ and the negative token to the reading list's existing files only and check
    each path listed as deleted apart, for nothing left to read, telling the two kinds the pick
    lists apart (revision 7): an absent path (`/bin/test ! -e`), and a folder there with nothing
    left to read (`/bin/test -d` and a listing, the names the pick skips aside, that prints
    nothing). Run as written over a deletion week's real pick, the negative token counts 0 in
    every existing file (grep exit 1); the deleted file passes the absent check, while grep over it
    cannot read it (exit 2); the owed folder emptied of its file (a `.DS_Store` left in it) is
    listed with its trailing `/`, fails the absent check and passes the folder check, so the week's
    controls complete. Step 6 (the replacement's first review, CR-AUDIT8 F3) asks the report to
    show each deleted path confirmed to have nothing left to read, absent or an existing folder
    whose reviewable listing is empty: read from its words, it accepts what step 3 accepts, so the
    empty-folder week passes step 3 and step 6 alike, and so does the absent file. The
    reappeared-content control: a file put back in that folder makes the folder check fail (the
    list is stale), so it passes neither step, and the next pick lists the file to read instead."""
    steps = audit_steps()
    for phrase in ("Content controls search files, so they cover the reading list's existing files "
                   "only: a path under the part `deleted since its baseline` holds no content to "
                   "search, and is checked apart for nothing left to read",
                   "a phrase copied from one existing file of the reading list (never a path "
                   "listed as deleted)",
                   "over every existing reading-list file, leaving out each path under `deleted "
                   "since its baseline`",
                   "**an absent path:** `/bin/test ! -e <path>` succeeds",
                   "**a folder there with nothing left to read** (listed with its trailing `/`): "
                   "`/bin/test -d <path>` succeeds and", "prints nothing",
                   "A path that passes neither check holds something to read again, which makes "
                   "the reading list stale: pick again (step 1)"):
        check(phrase in steps[3], "step 3 lacks %r" % phrase)
    check("Search it over every reading-list file" not in steps[3],
          "step 3 still searches every reading-list path")
    verification = brief_sections().get("VERIFICATION", "")
    for phrase in ("copied from one existing file of the reading list, never a path listed as "
                   "deleted", "Search every existing file of the reading list for the negative "
                   "control's token", "Leave out the paths under `deleted since its baseline`, "
                   "which hold no content to search: confirm instead that each of them has nothing "
                   "left to read (absent, or a folder holding no file)"):
        check(phrase in verification, "the brief's VERIFICATION lacks %r: %s" % (phrase,
                                                                                verification))
    absent_check, folder_check, listing = deletion_checks()
    check(absent_check == ["/bin/test", "!", "-e", "<path>"]
          and folder_check == ["/bin/test", "-d", "<path>"] and listing[0] == "/usr/bin/find",
          "the checks as written: %r" % [absent_check, folder_check, listing])
    world.write("hooks/sub/tool.py", "print('tool')\n")
    sub = world.path("hooks/sub")
    world.record("standing-rules")
    guard = world.path("hooks/guard.py")
    restore = unreadable(world, "hooks/guard.py")
    manifest = world.manifest_path()
    try:
        code, out, _ = world.run("--manifest-out", manifest, today="2026-10-12")
    finally:
        restore()
    world.record(parse(out)["slice"], today="2026-10-12", manifest=manifest)
    state = world.state_data()
    world.set_state(dict(state, owed=state["owed"] + [{"entry": "hooks/sub/",
                                                        "since": "2026-10-12"}]))
    os.remove(guard)
    os.remove(world.path("hooks/sub/tool.py"))
    world.write("hooks/sub/.DS_Store", "finder\n")   # a name every walk skips: nothing to read
    manifest, out = world.pick(today="2026-10-13")
    result = parse(out)
    deleted = result["parts"].get("deleted", [])
    existing = [p for p in reading(result) if p not in deleted]
    check(deleted == [guard, sub + "/"] and len(existing) >= 2 and load(manifest)["complete"],
          "the deletion week: %r" % result["parts"])
    grep = shutil.which("grep")
    check(grep is not None, "PROBE FAILED: no grep on PATH")
    token = "na" + hashlib.sha256(out.encode("utf-8")).hexdigest()[:16]
    for path in existing:
        done = subprocess.run([grep, "-c", "-F", token, path], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, timeout=TIMEOUT_S)
        check(done.returncode == 1 and done.stdout.strip() == "0",
              "the negative token over %s: exit %d, %r" % (path, done.returncode, done.stdout))
    # each deleted path, checked apart as step 3 writes it: the absent file passes the absent
    # check; the emptied folder fails it (it is there) and passes the folder check
    outcomes = {}
    for path in deleted:
        absent = run_check(absent_check, path)[0] == 0
        folder = run_check(folder_check, path)[0] == 0 and run_check(listing, path) == (0, "")
        outcomes[path] = (absent, folder)
        done = subprocess.run([grep, "-c", "-F", token, path], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, timeout=TIMEOUT_S)
        check(done.returncode == 2, "grep over a deleted path: exit %d" % done.returncode)
    check(outcomes == {guard: (True, False), sub + "/": (False, True)},
          "the deletion checks (absent, folder) as written: %r" % outcomes)
    # step 6 (the replacement's first review, CR-AUDIT8 F3): the report shows each deleted path
    # confirmed as step 6's words accept it, which must be what step 3 accepts, so that the
    # empty-folder week passes both steps honestly, the absent file too
    clause, kinds = step6_deleted_kinds()

    def step6(absent, folder):
        return ("absent" in kinds and absent) or ("folder" in kinds and folder)
    for path, (absent, folder) in sorted(outcomes.items()):
        check((absent or folder) and step6(absent, folder),
              "%s in the deletion week: step 3 %s, step 6 %s (step 6 accepts %r: %r)"
              % (path, absent or folder, step6(absent, folder), sorted(kinds), clause))
    check(STEP6_DELETED in steps[6] and kinds == {"absent", "folder"},
          "step 6's check of a deleted path reads %r, accepting %r" % (clause, sorted(kinds)))
    # the reappeared-content control: a file back in the folder fails the folder check, and so
    # step 3 and step 6 alike, and the next pick lists it to read
    again = world.write("hooks/sub/again.md", "# back\n")
    printed = run_check(listing, sub + "/")
    check(run_check(folder_check, sub + "/")[0] == 0 and printed[0] == 0
          and printed[1].strip().endswith("/again.md") and ".DS_Store" not in printed[1],
          "the folder check over a folder holding a file again: %r" % (printed,))
    back = (run_check(absent_check, sub + "/")[0] == 0, printed == (0, ""))
    check(back == (False, False) and not step6(*back),
          "the folder holding a file again passes step 3 or step 6: %r" % (back,))
    result = parse(world.run(today="2026-10-14")[1])
    check(result["parts"].get("deleted") == [guard] and again in reading(result),
          "the next pick after the file came back: %r" % result["parts"])
    os.remove(again)
    # the positive control: the same search finds a phrase copied from an existing file
    with open(existing[0], encoding="utf-8") as handle:
        phrase = handle.read().strip().split("\n")[0]
    done = subprocess.run([grep, "-c", "-F", phrase, existing[0]], stdout=subprocess.PIPE,
                          universal_newlines=True, timeout=TIMEOUT_S)
    check(done.returncode == 0 and int(done.stdout) >= 1, "CONTROL+ over %s: %r" % (existing[0],
                                                                                done.stdout))


# T10 for this suite: the held cases this revision replaced, and what carries their invariant now.
RETIRED = {
    "least_recently_audited": "least_recently_attempted",
    "lifecycle_missing_reported": "lifecycle_failures_incomplete",
    "register_slice_order_check": "register_slice_sources",
    "incomplete_audit_stays_due": "rotation_moves_on_with_omissions",
    "owed_listed_until_complete": "owed_listed_until_read",
    "audit_order_check_fields": "audit_outcome_table",
}


# Revision 7's replacement: the case of revision 6 whose heuristics it removed, and the case that
# now shows each shape that case refused reading as the stated limit.
RETIRED_R7 = {
    "standing_rules_count": "unframed_pages_limit",
}


# Revision 7 as amended after the replacement's second review (CR-AUDIT9): an HTML comment is read
# as text. Each case, leg or in-run plant that expected a comment to hide a line or to fail an
# acquisition, retired or converted: (the cases that carry it now, why). A key that is a bare name
# was a case; a key `<case>: <leg>` was a leg of that case; `slice.py: <plant>` an in-run plant.
RETIRED_R7A = {
    "fences_and_comments_closed": (
        ("fences_closed", "comments_read_as_text"),
        "split: its fence legs stay in fences_closed, with CommonMark's info-string rule added; "
        "its comment legs required a comment opened after text, or after a comment closed on its "
        "line, to fail the register, the lifecycle page, CLAUDE.md and the log and to refuse a "
        "report, and comments_read_as_text now requires those shapes, with CR-AUDIT9's two, read "
        "as text"),
    "fenced_heading_not_a_group: a heading inside the fixture's comment hidden": (
        ("fenced_heading_not_a_group", "comments_read_as_text"),
        "the fixture's CLAUDE.md held `## not a section` inside a comment, which had to stay "
        "hidden; a comment is text now, so the fixture's comments hold no heading, and "
        "comments_read_as_text plants headings, a table and an entry inside comments that must "
        "each be read"),
    "truncation_every_line: each page's cut just after a comment's opening caught": (
        ("truncation_every_line",),
        "a comment leaves nothing open now, so that cut, and the cuts just after CR-AUDIT9's "
        "escaped backtick and code span, must each be accepted as harmless or the limit; the cut "
        "just after a longer fence's opening joins the false closer's as a cut that must be "
        "caught"),
    "truncation_every_line: the classifier's register ending on a comment FAIL": (
        ("truncation_every_line",),
        "that register is whole now, so the classifier must call it harmless with an equal "
        "outcome; a register left open by the info-string rule takes its place as a FAIL"),
    "truncation_every_line: B-AUDIT8's comment reading as a lenient control": (
        ("truncation_every_line",),
        "no comment reader is left to be lenient; B-AUDIT9's fence opener (a backtick info string "
        "holding a backtick read as an opening) is the fourth control, its named cut FAIL"),
    "controls_line: B-AUDIT8's comment reading and the quoted-opener reading fail the controls": (
        ("controls_line",),
        "each patched a comment reader that no longer exists; a comment-hiding reader (B-AUDIT8's "
        "put back) and B-AUDIT9's fence opener must each fail the in-run controls instead"),
    "slice.py: the section and register plants that hid a comment or found one left open": (
        ("controls_line",),
        "the section plants now read a heading inside a comment, take every comment shape "
        "(CR-AUDIT8's and CR-AUDIT9's) for text leaving nothing open, and hold the info-string "
        "rule; the register plant takes a register ending on `<!--` as whole and one ending on a "
        "bare fence marker as not whole"),
}


# Revision 8 (spec-D18.md, the owner's D18): the hand-written fence reader and every fence or
# comment filter left slice.py. Each case, leg or in-run plant that expected a fence or a comment
# to be interpreted, retired or converted: (the cases that carry it now, why). Keys as RETIRED_R7A's.
RETIRED_D18 = {
    "fences_closed": (
        ("raw_inputs_read_every_line", "section_adapter_projection",
         "text_group_unreadable_incomplete"),
        "its legs required an unclosed fence to fail the register, the lifecycle page, CLAUDE.md "
        "and the log and to refuse a report; the raw protocols read every line, so for the three "
        "raw pages and the report each ending is text (raw_inputs_read_every_line requires each to "
        "complete), while for CLAUDE.md a fence left open fails the inventory only when it hides a "
        "heading-like line (section_adapter_projection's fixtures, text_group_unreadable_incomplete's "
        "planted file)"),
    "comments_read_as_text": (
        ("raw_inputs_read_every_line", "section_adapter_projection"),
        "its comment shapes must still leave the raw consumers complete, with what lies inside a "
        "comment read (raw_inputs_read_every_line); its CLAUDE.md legs, a section inside a comment "
        "read as a section and a fence marker inside a comment opening a fence, are reversed by "
        "markdown-it: a section a comment holds is undecidable (UNKNOWN), and a marker inside a "
        "comment is HTML (section_adapter_projection)"),
    "damaged_table_unknown: a fenced block left open below the table is damage": (
        ("damaged_table_unknown", "lifecycle_raw_protocol"),
        "raw lines read no fence, so that page is whole now (the case's new control); the damage a "
        "fence reader hid, CR-AUDIT10's torn tables after list and comment fences, is "
        "lifecycle_raw_protocol's"),
    "comparison_sources_fail_closed: the register with a fenced block never closed is unknown": (
        ("comparison_sources_fail_closed",),
        "raw lines read no fence, so that register is whole (the case's new control); an example in "
        "a code block quoting `## Open` gives the heading twice and is the UNKNOWN leg instead"),
    "comparison_sources_fail_closed: a deep-lint heading over an unclosed fenced fragment is "
    "unknown": (
        ("comparison_sources_fail_closed",),
        "the fragment is read on raw lines and holds no field, so the entry is not whole: the "
        "acquisition fails rather than returning unknown"),
    "report_refused: a section after a fenced block never closed is refused": (
        ("coverage_raw_protocol",),
        "a declaration counts wherever it stands, so a lone one after a fence left open is read and "
        "records complete"),
    "report_refused: the control with a fenced example of the section aside": (
        ("report_refused", "coverage_raw_protocol"),
        "on raw lines the fenced example is a second declaration, so that report is refused now; "
        "the control is a plain `none` report"),
    "controls_line: B-AUDIT8's fence reading, B-AUDIT8's comment reading and B-AUDIT9's fence "
    "opener fail the controls": (
        ("controls_line",),
        "each patched slice.py's fence reader (CLOSING_FENCE_RE, outside_fences, FENCE_RE), which no "
        "longer exists; B-AUDIT10's fence filtering put back in front of each raw consumer, and the "
        "section adapter without its accounting, must each fail the in-run controls instead"),
    "truncation_every_line: B-AUDIT9's fence opener as a lenient control": (
        ("truncation_every_line",),
        "no fence reader is left to be lenient; the section adapter without its accounting is the "
        "third control, its two named cuts of CLAUDE.md (a heading-like line hidden in a fence the "
        "cut left open) each FAIL"),
    "truncation_every_line: each page's cut just after its false closer and its longer opener "
    "caught": (
        ("truncation_every_line",),
        "the raw pages read no fence, so those cuts are accepted; a standing-rules file's cut just "
        "after a heading-like line hidden in a fence left open (lexer-hidden evidence) must be "
        "caught instead, and its cuts that hide nothing are valid shorter files"),
    "truncation_every_line: the classifier's unclosed-fence FAILs": (
        ("truncation_every_line",),
        "a standing-rules file is classed by its hand-written sections (lexer-hidden evidence, no "
        "section or a partial list FAIL), and a register ending on a fence left open is harmless "
        "on raw lines; CR-AUDIT10's report and torn table take their places as FAILs"),
    "slice.py: the section, register, deep-lint and table plants that read fences": (
        ("controls_line",),
        "the section plants run the adapter (CR-AUDIT-B's counterexample and its list-fence "
        "counterpart among them), and the register, deep-lint and table plants read raw lines: a "
        "fence left open is text, and CR-AUDIT10's hiding shapes and a malformed latest heading are "
        "caught"),
    "slice.py: the coverage plant refusing a section after a fence left open": (
        ("controls_line",),
        "that report is accepted on raw lines; a second declaration in a code block, a list fence, "
        "between comment fences, in a block quote and in a comment are the refusing plants"),
}


# CR-AUDIT14's fold (B-AUDIT15): the record refuses any slice other than the one its manifest's
# pick chose (F1). The leg that expected such a slice recorded, converted: (the cases that carry it
# now, why). Keys as RETIRED_R7A's.
RETIRED_R14 = {
    "record_atomic: a slice other than the pick's recorded, with a warning": (
        ("record_atomic", "record_refuses_other_slice"),
        "a standing-rules manifest recorded as skill:alpha was accepted and stored as a "
        "skill:alpha audit, a warning said only after the commit, so the record credited a slice "
        "whose reading the manifest did not represent; such a record is refused now before "
        "anything is committed, naming the manifest's slice (record_atomic's first refusal, and "
        "each other slice of the rotation in record_refuses_other_slice), and record_atomic "
        "records the pick's own slice"),
}


def case_retirement_map(world):
    """T10: each held case this revision replaced names the case that carries it now, and no held
    name survives beside its replacement; so does each case of revision 6 that revision 7's
    replacement turned into another (RETIRED_R7); and each case, leg or in-run plant that revision
    7's amendment (RETIRED_R7A), revision 8 (RETIRED_D18) or CR-AUDIT14's fold (RETIRED_R14)
    retired or converted names the cases that carry it now and why, a retired case's name
    surviving nowhere and a leg's case still there. A carrier of RETIRED_R7A that revision 8
    retired is followed to its own carriers."""
    names = set(name for name, _ in CASES)
    for retired in (RETIRED, RETIRED_R7):
        check(all(new in names and old not in names for old, new in retired.items()),
              "the retirement map: %r" % dict((o, n) for o, n in retired.items()
                                              if n not in names or o in names))

    def wrong_of(mapping, follow):
        wrong = []
        for old, (carriers, why) in mapping.items():
            owner, _, leg = old.partition(": ")
            carriers = [new for carrier in carriers for new in (
                follow[carrier][0] if carrier in follow else (carrier,))]
            if not carriers or any(new not in names for new in carriers) or len(why) < 40 \
                    or (not leg and old in names) or (leg and owner not in names | {"slice.py"}):
                wrong.append(old)
        return wrong
    # 7: the one case split, and the six legs and plants of B-AUDIT9's build that read a comment
    # (the fixture's hidden heading, the two truncation legs and its lenient control, the two
    # controls_line patches counted as one leg, and slice.py's plants), counted in that build
    wrong = wrong_of(RETIRED_R7A, RETIRED_D18)
    check(not wrong and len(RETIRED_R7A) == 7, "the amendment's retirement map: %r (%d entries)"
          % (wrong, len(RETIRED_R7A)))
    # 13: the two cases retired, and the eleven legs and plants of B-AUDIT10's build that read a
    # fence or a comment (two of damaged_table_unknown's and comparison_sources_fail_closed's three,
    # report_refused's two, controls_line's three patches counted as one leg, truncation_every_line's
    # three, and slice.py's two groups of plants), counted in that build
    wrong = wrong_of(RETIRED_D18, {})
    check(not wrong and len(RETIRED_D18) == 13, "revision 8's retirement map: %r (%d entries)"
          % (wrong, len(RETIRED_D18)))
    # 1: record_atomic's one leg that recorded a slice other than its pick's (with a warning),
    # counted in B-AUDIT14's build; the other cases that named another slice only in passing name
    # their pick's slice now, their legs unchanged
    wrong = wrong_of(RETIRED_R14, {})
    check(not wrong and len(RETIRED_R14) == 1, "CR-AUDIT14's retirement map: %r (%d entries)"
          % (wrong, len(RETIRED_R14)))


# ------------------------------------------------------------------ the last leg -------------

WRITE_PATTERNS = (
    r"\bopen\([^)]*,\s*['\"][rbt]*[wax+]",
    r"\bos\.fdopen\([^)]*,\s*['\"][rbt]*[wax+]",
    r"\bos\.(replace|rename|renames|remove|unlink|rmdir|removedirs|mkdir|makedirs|chmod|chown"
    r"|truncate|symlink|link|utime)\(",
    r"\bshutil\.",
    r"\btempfile\.(mkstemp|mkdtemp|NamedTemporaryFile|TemporaryFile|TemporaryDirectory)\(",
    r"\.write_(text|bytes)\(",
    r"\bjson\.dump\(",
    r"\bsubprocess\.",
)
WRITERS = ("do_init", "do_record", "write_manifest")


def write_hits(source):
    return [(number, line) for number, line in enumerate(source.splitlines(), 1)
            if any(re.search(p, line) for p in WRITE_PATTERNS)]


def case_pick_writes_nothing(world):
    """The pick without --manifest-out writes nothing: a checksum manifest of a read-only copy is
    unchanged after it; the source's write patterns sit only in write_atomic (whose hits are the
    control), and only the init, the record and the manifest writer call it."""
    world.lifecycle(world.every_item_row())
    world.record("standing-rules")
    copy = World.__new__(World)
    copy.root = os.path.join(world.root, "copy")
    shutil.copytree(world.root, copy.root, ignore=shutil.ignore_patterns("copy"))
    copy.vault, copy.tools, copy.hooks = (os.path.join(copy.root, n)
                                          for n in ("vault", "tools", "hooks"))
    copy.state = os.path.join(copy.tools, "weekly-audit", "slices.json")
    paths = [copy.root] + [os.path.join(d, n) for d, ds, fs in os.walk(copy.root) for n in ds + fs]
    for path in paths:
        os.chmod(path, os.stat(path).st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    try:
        before = tree_manifest(copy.root)
        # the fixture world holds 28 files and 20 folders once recorded, with its manifests and
        # reports (measured), so a manifest of 20 entries or fewer means the walk missed most of it
        check(len(before) > 20, "the manifest saw only %d entries" % len(before))
        code, out, err = copy.run()
        after = tree_manifest(copy.root)
    finally:
        for path in paths:
            os.chmod(path, os.stat(path).st_mode | stat.S_IWUSR)
    check(code == 0, "the pick failed on the read-only copy (%d): %s %s" % (code, out[-300:], err))
    check(before == after, "the read-only copy changed: %r" % sorted(set(after) ^ set(before))[:5])
    source = read_text(SLICE)
    tree = ast.parse(source)
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    spans = dict((node.name, (node.lineno, max(getattr(n, "lineno", node.lineno)
                                               for n in ast.walk(node)))) for node in functions)
    first, last = spans["write_atomic"]
    hits = write_hits(source)
    inside = [h for h in hits if first <= h[0] <= last]
    outside = [h for h in hits if not first <= h[0] <= last]
    check(write_hits("x = open(p, 'w')\nos.replace(a, b)\n") == [(1, "x = open(p, 'w')"),
                                                               (2, "os.replace(a, b)")],
          "the write-pattern grep misses a planted write")
    # write_atomic makes seven writes the patterns name (mkstemp, fdopen "w", json.dump, link,
    # unlink twice, replace); three or more shows the grep reads that function at all
    check(len(inside) >= 3, "the control: the grep found only %r in write_atomic" % inside)
    check(not outside, "a write pattern outside write_atomic: %r" % outside)
    callers = set()
    for node in functions:
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call) and getattr(inner.func, "id", None) == "write_atomic":
                callers.add(node.name)
    check(callers == set(WRITERS), "write_atomic is called from %r, %r expected (the control: all "
          "three are found)" % (sorted(callers), WRITERS))


CASES = [(name[5:], function) for name, function in sorted(globals().items())
         if name.startswith("case_") and callable(function)]
CASES.sort(key=lambda entry: entry[1].__code__.co_firstlineno)


def printable(error):
    """A failure's message as printed: a lone surrogate (a name that is not valid UTF-8, as a
    faulty build may print it) is written as its escape, so the suite's own output stays UTF-8."""
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
    if not os.path.isfile(SLICE):
        print("PROBE FAILED: slice.py not found beside the suite at %s" % SLICE)
        return 2
    top = tempfile.mkdtemp(prefix="test-slice-")
    failures = []
    try:
        for index, (name, function) in enumerate(selected):
            root = os.path.join(top, "%02d-%s" % (index, name))
            os.makedirs(root)
            try:
                function(World(root))
                print("ok   %s" % name)
            except Failure as failure:
                failures.append(name)
                print("FAIL %s: %s" % (name, printable(failure)))
            except Exception as error:   # a crash in a case is a failure, never a pass
                failures.append(name)
                print("FAIL %s: %s: %s" % (name, type(error).__name__, printable(error)))
    finally:
        shutil.rmtree(top, ignore_errors=False)
    print("searched %d output(s) of slice.py and pass_order.py for a verdict on the first pass "
          "(T8)" % SEARCHED["outputs"])
    if failures:
        print("FAIL %d/%d (%s)" % (len(failures), len(selected), ", ".join(failures)))
        return 1
    print("PASS %d/%d" % (len(selected), len(selected)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
