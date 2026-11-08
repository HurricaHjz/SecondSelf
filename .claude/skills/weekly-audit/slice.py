#!/usr/bin/env python3
"""slice.py: pick the weekly fresh-eyes audit's slice and print its reading list; record the audit.

The audit is a step of the owner's Sunday review, which he starts; nothing schedules this script.
Design: the waste-reduction and retirement design page in `wiki/developments/`, section 2 (the
weekly fresh-eyes audit) and section 3 (the lifecycle register, its Enrolment and Tests bullets),
as simplified by option S (the owner's choice of 12 October 2026). Python 3 standard library only.

    slice.py --init [--state FILE]
    slice.py [--vault DIR] [--tools DIR] [--hooks DIR] [--state FILE] [--today YYYY-MM-DD]
             [--manifest-out PATH]
    slice.py --record SLICE --findings N --manifest PATH --report PATH [the same options]

`--init` is the install step. It creates `slices.json` with no audits and no baseline, and refuses
when the file exists. With no --state the file is `tools/weekly-audit/slices.json` in the run
store, outside the vault, since this script's own folder ships; `setup.sh` makes that folder. After install a missing `slices.json` is a continuity failure: a pick or a
record refuses and says so, and the rotation never starts over silently.

THE PICK writes nothing, unless `--manifest-out PATH` asks it to write its manifest to that one
path. It prints, in order:
1. the slice: the rotating part's name and why it came round;
2. the reading list, one absolute path per line, spelled under the roots as they were given (a
   due row's files too, never by their real path: CR-AUDIT12 F3), in six parts, each path once,
   under the first part that holds it: the framework files changed since the baseline; the
   content owed from an earlier audit; the owed paths deleted since their baseline (nothing to
   read: the reviewer checks what still refers to each); the files of the lifecycle rows due for
   review; the inventory items with no lifecycle row; the rotating part's files. A part whose
   acquisition did not succeed says UNKNOWN in its header, never a bare count, since what it
   lists may be short;
   then the REQUIREMENT FILES: the governing texts the slice serves (REQUIREMENTS), which the
   first pass reads beside the reading list, each listed only when it is not on the list already
   (one absent at the pick listed all the same, with a note, the pick incomplete), its role judged
   apart from what lists its path: one absent leaves the pick incomplete on the reading list too,
   where an owed deletion, say, holds it (CR-AUDIT12 F1);
3. the changed-file counts, with the removed files and the files held for the second pass, then
   the OWED block: each owed entry, since when, how many of its files the list holds and how many
   are held for the second pass;
4. the due rows, overdue first, then the malformed rows;
5. the missing rows: inventory items with no lifecycle row;
6. the second pass's sources, which the first pass never opens, with LABELS LIMITED when one of
   the two comparison sources could not be read;
7. the controls, the acquisitions that did not succeed (INCOMPLETE), and a one-line summary.
Parts 4, 5 and 6 each end with a `limit:` line (LIMIT_LINES, below): what the unframed Markdown
pages they rest on cannot show, and the backstop for it (THE LIMIT, below).

ACQUISITIONS AND COMPLETENESS. Every read the pick makes belongs to a registered acquisition: the
premises (the required roots, read once before anything else), slices.json, the hash scan of each
root, the owed content, the rotation listing, the lifecycle rows, the inventory, the due rows'
files, and the two comparison sources the second pass labels against: the register
(`known-issues.md`, read for its `## Open` and `## Closed` sections) and deep-lint's latest entry in
`wiki/log.md`; and, reading nothing itself, the requirement files, as the hash scan saw them.
Each reports once: ok; failed, naming what it could not read; or unknown, for a result it could
not establish (a lifecycle page with no table, a register with no `## Open` section, a log with no
deep-lint entry, a requirement file absent). The manifest is complete only when every registered
acquisition reported ok; one that failed, returned unknown or never reported makes it incomplete,
and the manifest is written only after every acquisition has reported. A failed or unknown
result reads UNKNOWN in the output, never empty: the changed files, the rotation's choice and its
files, the due rows, the missing rows, the owed content. A required root gone when a walk reads it
is recorded by that walk, never by a check made before it, so a root that vanishes between the
premises and the walk is unread; a folder the hash scan saw a moment earlier and a later walk
finds gone is unread too; a readable empty folder is read, never unread. A comparison source that
failed or returned unknown also limits the week's labels (LABELS LIMITED): no finding of that
audit is labelled `new kind`, and its `new kind` labels are candidates the head checks. The
in-run controls are plants in memory, so the pick's own reads are only its acquisitions'.

WHOLE INPUT. An acquisition succeeds only on input that is whole and of the shape its consumer
needs, never on a part of it, and fails on input malformed in a way its structure can show:
WHOLE_INPUT, below, holds one row per acquisition naming only rules its structure decides (the
suite fails a pick or a record that registers one without a row), and the code at each site fails
on input that breaks what its row names. Text is decoded as strict UTF-8: undecodable bytes fail
the acquisition, and are never replaced or skipped. A file or folder name that is not valid UTF-8
leaves the folder holding it unread, and so does a symbolic link to a folder below a root, which
no walk follows. Absence is established, never read from an error: a path is absent only when its
own metadata says so (no such entry, or a path component that is not a folder), and any other
metadata or listing error (a permission refused, say) is a failed acquisition, never "not there"
(`look`, below, is the one place a path is looked at); a symbolic link whose target is missing is
there, unreadable, and fails the acquisition that looks at it. JSON (slices.json, a manifest) is
read whole, with no key given twice and no NaN or Infinity. Lines are split at newlines only, so
line numbers are an editor's. No reader here interprets Markdown structure by hand (the owner's
decision D18 of 13 October 2026): the four inputs where a misread would be silent (the reviewer's
coverage section, the lifecycle tables, the register and deep-lint's entry in the log) are read
by literal-line protocols over their raw lines (THE RAW PROTOCOLS, below), so no fence, comment,
list or block quote can hide a line from them, and the two section lists are read by
markdown-it-py (THE SECTION ADAPTER, below), which reports what its declared syntax cannot decide
instead of guessing. A lifecycle table counts only with its header, its separator row and whole
rows (THE LIFECYCLE TABLE, below); the register only holding its `## Open` and `## Closed`
sections, once each, Open first; deep-lint's latest entry only with its heading in its exact form
and its complete `- **Changed**:` and `- **Conflicts**:` fields, each followed by a value on its
line, before the next line that begins with `#` after any container prefix (spaces, tabs, `>`
marks, list markers); a standing-rules file only holding a section; the
report's `## Not read` section only as the one declaration of the whole report, closed by its one
`END NOT READ: <n>` line, its path lines read with their exact characters.
THE RAW PROTOCOLS (D18). Each reads every raw line of its input, one at a time, against a literal
grammar: a line inside a code block, a list item, a block quote or an HTML comment is read like
any other line, so text that looks like a record is read as one, and an example that quotes record
syntax at the start of a line (a template in a code block, a quoted entry) is that syntax. What a
record is, what makes it whole, what makes it torn and how such an example is read is written
beside each protocol's code, and in AUDIT.md (Reading protocols):
- the coverage (parse_not_read): exactly one line in the whole report declares `## Not read` (a
  `#` heading whose text begins with the words `not read`, in any letter case, after any spaces,
  `>` marks or list markers) and it is exactly `## Not read`; exactly one line reads as its
  closing line, and it is exactly `END NOT READ: <n>` and the report's last; between them only
  `none` or the audit's mandatory paths;
- the lifecycle tables (parse_lifecycle): every line whose first character other than a space or
  tab is `|` is a table line, wherever it stands; HEADER, a separator of ten cells and whole rows
  make a lifecycle table; a header alone, a header over no such separator, a torn row, rows in no
  table, a damaged lifecycle header (ten cells, or a `Next review` cell, yet not HEADER) and a
  table line inside a block quote are damage;
- the register (register_problem): exactly one line `## Open` and exactly one `## Closed`, Open
  first;
- deep-lint's latest entry (deeplint_entry): the last line naming a deep-lint heading in any form
  (its kind standing before its title, whatever its date field became, after any container
  prefix) is the latest and must be in the entry's exact form (no older entry is ever read in its
  place); its entry runs to the next line that begins with `#` after any spaces, tabs, `>` marks or
  list markers (a malformed heading included, so no field is borrowed from what follows) and
  holds its two complete fields.
THE SECTION ADAPTER (D18). CLAUDE.md's and CUSTOMISATION.md's top-level sections are read by
markdown-it-py 4.2.0 (MARKDOWN_IT_VERSION), the one dependency beyond the standard library, through
standing_sections, the only code here that imports it, lazily, inside the inventory's acquisition.
Its declared syntax: a front matter block at the file's start (its first line exactly `---`, up to
the next line exactly `---`) is set aside, its lines read as blank; the rest is parsed with the
CommonMark preset; a section is an ATX level-2 heading at the top level (in no list item or block
quote), located at its line, with its text. Every raw line that looks like such a heading (`##` up
to three spaces in, then a space, a tab or the line's end) must be a section's own line or lie
inside a fenced block that markdown-it closed with its closing marker (an example). Anywhere else
(the front matter, an HTML comment or other HTML block, a fenced block left open, a list item, a
block quote), and for any other level-2 heading (a setext one, or one inside a list item or block
quote), the section list is undecidable and the inventory fails for that file, never a shorter
list. A carriage return that ends no line is unsupported too. markdown-it-py missing, unimportable
or of another version leaves the inventory unknown: no other reader ever stands in for it.
THE LIMIT (the provisional replacement of revision 7): the lifecycle page, the register, CLAUDE.md,
CUSTOMISATION.md and wiki/log.md are unframed Markdown, and no such page can show by its syntax
that it lost only later material, so no rule here claims it: a cut that leaves a structurally
valid shorter page cannot be told from the page alone, wherever it falls (inside a section or an
entry, or after a deep-lint entry's two fields). Rules that claimed more than structure shows (a
heading required after the last table or section, a count of sections taken from lifecycle rows,
a closing field required on an entry) are not used. The pick says so in its `limit:` lines, and
AUDIT.md (step 1) names the backstops: the hash scan, by which a page cut since the last audit
reads as changed (CLAUDE.md and CUSTOMISATION.md then join the reading list; the lifecycle page
and the register, held for the second pass, are named changed among the held files), and step
7's label check against the register, the only backstop for wiki/log.md, which is not hashed.

PRINTING. Every line this script prints that holds a character a terminal could hide or redraw (a
control, format, private-use, surrogate, unassigned or separator character other than a tab), or
that begins `escaped: ` itself, is printed as `escaped: ` and the line in pass_order.py's
reversible encoding: each such character written \\xHH (two lower-case hex digits) below U+0100,
\\uHHHH below U+10000, else \\UHHHHHHHH, and every backslash doubled; any other line prints byte for
byte. An `ESCAPED:` line before the first such line declares it. Reading the escapes left to right
recovers the line, and a reading-list path printed so is named under `## Not read` as printed.

THE RECORD. `--record SLICE --findings N --manifest PATH --report PATH` appends the audit (date,
slice, finding count, the time of the record, the manifest's time, whether it was complete, and
each reason it was not) to `slices.json` and stores the manifest's hashes as the new baseline.
`--report` is the reviewer's report, which ends with a section headed exactly `## Not read`: one
path per line for each mandatory input the reviewer did not read in full (a reading-list file, a
requirement file or a second-pass source, each as the pick prints it and with its exact
characters: only the newline is removed, so a space a path ends with is part of it, and
whitespace is forgiven only around the heading, `none` and the END line), or the single word
`none`; then, as the section's and the report's last line, `END NOT READ: <n>`, n the number of
path lines (0 with `none`), so that a report cut after any whole line can never discharge what the
cut removed. The section is found by THE RAW PROTOCOLS' coverage grammar over the whole raw report:
one declaring line, wherever it sits. The record refuses (exit 2, slices.json unchanged) when no
line declares the section, when more than one does (an example of the heading in a code block, a
list, a quote or a comment included), when the one that does is not exactly `## Not read`, when
the section is present but empty, names a path that is none of the pick's mandatory inputs, holds
a line that is neither such a path nor the single word `none`, puts `none` beside other lines, has
a heading after it (so that it is not the report's last), lacks its `END NOT READ: <n>` line,
carries a count that does not match its path lines, holds anything after that line, or when any
other line of the report reads as a closing line, or when the report cannot be read whole; with
no `--report`; and, as before, with no `--manifest`, with a manifest taken over other roots or
before the last record, one that cannot be read or is malformed, an unknown slice, or the slice
already recorded that day. It refuses as well, before anything is committed, any slice other than
the one the manifest's pick chose, and names that slice (CR-AUDIT14 F1): the manifest's reading
list, requirement files and second-pass sources are that slice's, so the record credits that slice
alone, and the rotation counts as attempted only the slice the manifest represents.
- COVERAGE OVER EVERY MANDATORY INPUT (CR-AUDIT-B finding 2, D18). The pick records three kinds
  of mandatory input in its manifest, each in its phase: the reading list (pass 1), the
  requirement files (pass 1: CLAUDE.md for every slice, CUSTOMISATION.md for the standing rules
  and .claude/settings.json for the hooks and monitors, each listed apart only when it is not on
  the reading list, and one absent at the pick listed too, the pick incomplete: CR-AUDIT11 F2;
  its role judged apart from whatever else lists its path, so one absent leaves the pick
  incomplete on the reading list as well, an owed deletion's place: CR-AUDIT12 F1)
  and the second-pass sources (pass 2: the lifecycle page, the register unless it is the slice,
  and wiki/log.md for deep-lint's entry); and which of them are comparison sources, whatever their
  phase (the register, a reading-list file in its own week, and wiki/log.md: CR-AUDIT11 F3). The
  section may name any of them, and any path it names makes the audit incomplete, its reason
  stored. A reading-list path named keeps the debt and baseline rules below; a requirement file or
  a second-pass source named is no debt (none of them is owed) and stays an explicit reason; a
  comparison source named (the register or wiki/log.md) also limits the audit's labels (LABELS
  LIMITED), however its acquisition went at the pick and whichever pass reads it, the register in
  its own week included, a reason saying so. The coverage records the reviewer's declaration, not
  proof of what it understood.
- THE COMMIT. The record writes the new state to a temporary file beside slices.json, reads it back
  (a registered acquisition, `slices.json read back`, as strict as the state's own) and checks that
  it is what was written, and only then replaces slices.json with it in one step (os.replace).
  Every refusal comes before that step, so a REFUSED line always leaves slices.json unchanged, a
  read-back that did not succeed among them; after the step nothing refuses and no line says the
  state is unchanged. The diagnostic rescan that follows cannot change the record: it reports its
  own failures (UNKNOWN in part), never as nothing changed.
- The record's own acquisitions (the premises, slices.json, the manifest and the reviewer's
  coverage) are registered as the pick's are and govern the recorded completion as the pick's
  govern its manifest: one that failed, returned unknown or never reported before the record is
  written makes the audit incomplete, its reason stored. Such a record moves nothing it cannot
  vouch for: with the coverage short, every reading-list path counts as not read (owed, its
  earlier hash kept); with the premises, slices.json or the manifest short, the baseline does not
  advance and no owed entry is discharged.
- The audit is recorded complete only when its manifest is complete, the record's own
  acquisitions all succeeded and the section says `none`: the reviewer read every item of its
  slice, owed items included, every requirement file and every second-pass source. Each reason it
  is not is stored with it (`reasons`, empty when it is complete).
- The baseline advances only over what the audit read: a file its pick could not read keeps its
  earlier hash, or stays absent when it had none (so the next pick lists it as new), every
  earlier hash below an unread folder or root is kept, and so is the earlier hash of each file the
  reviewer names under `## Not read`, so that file still reads as changed at the next pick when
  it had changed. A file inside a hashed root is owed by its hash key whatever spelling of the
  root the pick or the record was given (the root's real path, or a link to it: key_for), so its
  omission keeps its earlier hash, or its absence, under every spelling (CR-AUDIT12 F3).
- Owed content is discharged only for what the reviewer read: an owed entry is discharged when
  the pick acquired it, listed its content on the reading list, and the reviewer read all of it,
  its files held for the second pass included. An entry's files are found before the held sources
  leave the reading list, and the manifest names those held apart (CR-AUDIT13 F2: a folder owed
  from an earlier audit was discharged though the reviewer named the register in it unread): one
  named under `## Not read` keeps the entry owed and its own earlier hash, whatever the week's
  phase. An entry whose content was not listed (all of it held, or not acquired), or not read,
  stays owed. Each path named under `## Not read` becomes owed, or stays owed, and so does each
  path the pick could not read. Content held for the second pass (the lifecycle page, wiki/log.md,
  and the register unless it is the slice) is read whole there every week, and no record makes it
  owed while it is held.
- An owed path with no file of it there now, its absence established (its own metadata reporting
  it missing, or, for a folder, its listing read whole holding no file; never an error read as
  absence), while nothing the pick could not read covers it (its root, and every folder down to
  it, walked without failure), is a deletion: the pick lists it in its own part of the reading
  list as deleted since its baseline, and the record discharges it like any other slice item the
  reviewer did not name under `## Not read`, the baseline then recording the path as absent, so a
  later reappearance reads as changed. A path whose metadata could not be read, and one under a
  root or folder that failed, stays owed, as an acquisition failure. A file deleted that was not
  owed is reported as removed, apart from the reading list, as before; its baseline records it as
  absent at the record, so its reappearance reads as changed too.
- A file changed between the pick and the record is not absorbed: the next pick lists it as
  changed, so a fix made during the dispositions reaches the next audit's fresh reader.

THE ROTATION: the standing rules (CLAUDE.md and CUSTOMISATION.md); each skill in turn; the open
register; the hooks and monitors (both hooks folders and the watch tools); the tools. The least
recently attempted slice comes round, never-attempted slices first: every recorded audit counts,
complete or not, so repeated omissions cannot pin the rotation to one part; what an incomplete
audit left unread stays owed and joins the following picks until it is read. A tie goes to the
slice with more files changed since the baseline, then to the one with more findings at its last
audit, then to rotation order. No slice leaves the rotation.

ROOTS. Hashed: the vault's `.claude/`, `CLAUDE.md`, `CUSTOMISATION.md`,
`CUSTOMISATION-definitions.md` and `wiki/developments/`; the tools folder (`tools` in the run store,
LLM_WIKI_STORE else ~/.llm-wiki, unless --tools) and the hooks folder (`hooks` beside the tools
folder, unless --hooks). Each is required except `CUSTOMISATION-definitions.md`, which the design does not name
and which is hashed when present, so its absence is never a failure. A required root that is
missing or cannot be read when the pick or the record begins is a broken premise (PROBE FAILED,
exit 2, no manifest written), never a smaller scan. Skipped everywhere, by the hash scan, the
inventory and the rotation alike: `__pycache__` and vendored `node_modules` folders, and `*.bak*`
and `.DS_Store` files, so that a dependency upgrade cannot flood the reading list; the dependency
pin files beside a `node_modules` folder (for example `package.json`) stay hashed. Also skipped:
`slices.json` and its temporary files, which change at every record.

HELD FOR THE SECOND PASS: the second-pass sources, the register (`known-issues.md`), the lifecycle
page and `wiki/log.md`, never enter the reading list or the requirement files, changed or not and
whatever lists them (a changed file, an owed entry, a due row, an inventory item, the rotating
part), since the first pass holds no earlier answer (held_files, derived from the sources' own
list: CR-AUDIT11 F4). The register enters it only when the rotating slice is the register itself,
which the first pass reads as a text; it is then the first pass's object and no second-pass
source, so the SECOND-PASS SOURCES block lists only the lifecycle page and deep-lint's entry in
`wiki/log.md`, while the register stays a comparison source, what the first pass read of it
serving the second pass's labels.

THE INVENTORY: what can be discovered (the skills' test scripts, the hooks in both hooks folders,
the watch tools, and the standing-text groups: each top-level section of CLAUDE.md and of
CUSTOMISATION.md, and every SKILL.md under `.claude/skills` at any depth, by its vault-relative
path), plus NAMED_GROUPS, a fixed list of groups with no file of their own (the reflection
controls, and the two hooks defined inline in `.claude/settings.json`), each listed as missing
while no row names it. The Monitor section of IDEAS.md stays out: it is the owner's scratchpad,
and deep-lint reviews it. A standing-rules file whose sections cannot be read whole (undecodable
bytes) or decided (THE SECTION ADAPTER) or come out empty fails the inventory, and so does a file
found that cannot be looked at to tell whether it is a script; markdown-it-py missing,
unimportable or of another version leaves it unknown. Sections a cut took from a standing-rules
file that stays structurally valid are THE LIMIT; a section hidden by what a cut left open (a
fence, a comment) is undecidable, never the limit.

THE LIFECYCLE TABLE: a Markdown table whose header row is exactly HEADER below, on the next line its
separator row (one cell for each of the ten columns), then its body: whole rows, each opening and
closing with an unescaped pipe, up to the first line that is not a row. A header and separator with
no row is a valid empty table. A row is due when its State is `review due` or `quarantined`, or
its Next review is today or earlier; a retired row is never due, so it needs no Next review (the
head's choice of 14 October 2026). A whole row with no Next review (a retired row excepted) or no
Retire when, a Kind or State outside its set, a Next review that is not a YYYY-MM-DD date (a
retired row's included), or the wrong number of cells is malformed and listed. A missing or
unreadable page (undecodable bytes included) fails the lifecycle rows. A page without the table,
or with a damaged one, returns unknown: a header alone, a header whose next line is not a
separator of ten cells, a torn row (one that does not close with an unescaped pipe), table rows
standing outside any table (a row cut off from its table by a blank line, say), a damaged
lifecycle header, or a table line inside a block quote (THE RAW PROTOCOLS: every raw line is read,
so a fence or a comment hides no row). Either way the due and missing rows read UNKNOWN, never
"nothing due", and the pick is incomplete. Rows a cut took from a page that stays structurally
valid (a whole table, or a whole row, lost after a whole one) are THE LIMIT.

EXIT CODES: 0, done (the slice printed with every acquisition ok, or the record or the init made);
2, refused, with nothing printed beyond the reason (and the ESCAPED line before it, when the reason
holds a character a terminal could hide): a bad argument, `PROBE FAILED: <what>` for a
broken premise (a required root missing or unreadable among them), a missing, unreadable or
malformed `slices.json`, which is never started over, or a refused record or init; 3, the slice
printed, but the pick is incomplete (above), its manifest marked so.
"""

import argparse
import datetime
import difflib
import fnmatch
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from stat import S_ISDIR, S_ISLNK, S_ISREG

LIFECYCLE_REL = "wiki/developments/check-lifecycle.md"
REGISTER_REL = "wiki/developments/known-issues.md"
LOG_REL = "wiki/log.md"
SKILLS_REL = ".claude/skills"
SKILL_FILE = "SKILL.md"
VAULT_HOOKS_REL = ".claude/hooks"
WATCH_DIR = "watch"
STATE_NAME = "slices.json"
STATE_FOLDER = "weekly-audit"
STATE_VERSION = 4     # 4: each audit holds the reasons it was recorded incomplete (3: complete,
                      # and the state holds `owed`)
MANIFEST_VERSION = 8  # 8: each owed entry names its files held for the second pass (CR-AUDIT13
                      # F2); 7: it names its comparison sources whatever their phase (CR-AUDIT11
                      # F3); 6: the manifest holds the requirement files and the second-pass
                      # sources, each nameable under `## Not read` (D18); 5: each owed entry says
                      # whether it was deleted; 4: its acquisitions, its reading list and its
                      # slices
MANIFEST_KIND = "weekly-audit hash manifest"
ROOT_LABELS = ("vault", "tools", "hooks")
NOT_READ_HEADING = "## Not read"

VAULT_ROOTS = (".claude", "CLAUDE.md", "CUSTOMISATION.md", "CUSTOMISATION-definitions.md",
               "wiki/developments")
# The vault roots the design names, each (path, whether a folder): missing or unreadable, each is a
# broken premise. CUSTOMISATION-definitions.md is hashed when present and required by nothing.
REQUIRED_VAULT_ROOTS = ((".claude", True), ("CLAUDE.md", False), ("CUSTOMISATION.md", False),
                        ("wiki/developments", True))
OPTIONAL_VAULT_ROOTS = ("CUSTOMISATION-definitions.md",)
SKIP_DIRS = ("__pycache__", "node_modules")
SKIP_FILES = ("*.bak*", ".DS_Store")
SCRIPT_SUFFIXES = (".py", ".sh")
TEST_GLOBS = ("test_*.py", "test_*.sh")
STANDING_RULES = ("CLAUDE.md", "CUSTOMISATION.md")
# Groups the lifecycle register holds a row for that have no file of their own, so no walk can find
# them; each is listed as missing while no row's Item names it. A category with no file joins here.
# The two hooks defined inline in .claude/settings.json joined at the build (the held README's
# install step; the lifecycle register's review CR-LIFE, finding 1), so the install edits no code.
NAMED_GROUPS = (
    "reflection controls",
    "experience pages (wiki/experience/; a group name)",
)
# The requirement files of each slice (the governing texts it serves), vault-relative: the first
# row's for every slice, the others' for the slice they name. The pick lists each one that is not
# on the reading list already (an absent one too, the pick incomplete, as it is when the reading
# list holds it: requirement_files), and records them in the manifest, so the record can tell a
# requirement file named under `## Not read` from a stray path (D18, CR-AUDIT-B finding 2). A
# skill slice's own SKILL.md is on its reading list, as part of the slice.
REQUIREMENTS = (("", ("CLAUDE.md",)), ("standing-rules", ("CUSTOMISATION.md",)),
                ("hooks-and-monitors", (".claude/settings.json",)))

HEADER = ("| Item | Kind | Purpose | Guards | Cost per run | Last real catch | State | Retire when "
          "| Re-arm when | Next review |")
COLUMNS = ("item", "kind", "purpose", "guards", "cost", "last_catch", "state", "retire_when",
           "rearm_when", "next_review")
KINDS = ("suite", "hook", "monitor", "watcher", "controls", "text")
STATES = ("active", "review due", "quarantined", "retired")
DUE_STATES = ("review due", "quarantined")
EMPTY_CELLS = ("", "-", "–", "—")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
SEPARATOR_RE = re.compile(r"^\|(\s*:?-{3,}:?\s*\|)+$")
GROUP_RE = re.compile(r"^(CLAUDE\.md|CUSTOMISATION\.md)\s*(?:§|##)\s*(.+)$", re.I)
SECTION_NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*)(?![\d.])")
HEADING_NUMBER_RE = re.compile(r"^(\d+)\.?(?:\s|$)")
# THE RAW PROTOCOLS' line grammars (D18): each is matched against one raw line at a time, wherever
# the line stands; none tracks a fence, a comment, a list or a quote.
# the coverage: a line declaring `## Not read` in any form, after any spaces, tabs, `>` marks or
# list markers (`-`, `*`, `+`, `1.`, `1)`): a `#` heading of any level whose text begins with the
# words `not read`, in any letter case; the one such line must be exactly NOT_READ_HEADING
DECLARATION_RE = re.compile(r"^[ \t]*(?:(?:>|[-*+]|\d{1,9}[.)])[ \t]*)*#{1,6}[ \t]*not[ \t]+read\b",
                            re.I)
# the lifecycle page: a table line inside a block quote (`>` marks, then a pipe), which is damage
QUOTED_TABLE_RE = re.compile(r"^[ \t]*>[ \t>]*\|")
# the register: its two section headings, `## Open` and `## Closed`, spaces forgiven after `##` and
# after the word (and a CRLF line's carriage return)
REGISTER_HEADING_RE = re.compile(r"^## [ \t]*(Open|Closed)[ \t\r]*$")
# the raw protocols' container prefix, DECLARATION_RE's own: any spaces and tabs, then any run of
# `>` marks and list markers (`-`, `*`, `+`, `1.`, `1)`), each followed by any spaces or tabs
CONTAINER = r"^[ \t]*(?:(?:>|[-*+]|\d{1,9}[.)])[ \t]*)*"
# the log: a deep-lint entry heading in its exact form, and the same heading in any form (CR-AUDIT11
# F1): after the container prefix, a run of `#`, then the kind deep-lint however it is written
# (`deep-lint`, `deep lint`, `deeplint`, `deep_lint`, in any letter case, a word) standing before
# the heading's title: before its first `|` (anywhere in it when it holds none), or as its first
# word, nothing but characters other than letters before it (a stray `|` among them); so whatever
# its date field became (a bracket left open, another shape, none at all) it is still that heading.
# A kind named only after the `|`, in a title, names no deep-lint heading.
DEEPLINT_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\] deep-lint \|")
DEEPLINT_NEAR_RE = re.compile(CONTAINER + r"#+(?:[^|\n]*?|[^A-Za-z\n]*)deep[ \t_-]*lint\b", re.I)
# the log: a line that ends an entry, any line whose first character after the container prefix is
# `#` (an entry heading in any form, a malformed one or one behind a list marker included)
ENTRY_END_RE = re.compile(CONTAINER + r"#")
# THE SECTION ADAPTER: the markdown-it-py version its acceptance was established against, and a raw
# line that looks like a level-2 ATX heading (`##` up to three spaces in, then a space, a tab, a
# carriage return or the line's end), each of which must be accounted for
MARKDOWN_IT_VERSION = "4.2.0"
SECTION_LOOK_RE = re.compile(r"^ {0,3}##(?:[ \t\r]|$)")
FRONT_MATTER = "---"
# deep-lint's two result fields in their complete form (the log's entry template, CLAUDE.md section
# 5), each followed by a value on its line, `none` included: a torn prefix (`- **Changed`), a
# look-alike name (`- **Changed-not-the-field**:`) or nothing after the colon is no such field
CHANGED_RE = re.compile(r"^- \*\*Changed\*\*:[ \t]*\S")
CONFLICTS_RE = re.compile(r"^- \*\*Conflicts\*\*:[ \t]*\S")
HEADING_RE = re.compile(r"^#{1,6}(\s|$)")
END_NOT_READ_RE = re.compile(r"^END NOT READ: (0|[1-9][0-9]*)$")
# a line that reads as the section's closing line in any form (the words end, not, read first,
# after any characters but letters and digits), wherever it stands; a path line, which begins with
# `/`, never does, so a path holding those words is read as a path
END_NEAR_RE = re.compile(r"^(?!/)\W*end\W*not\W*read\b", re.I)

EXIT_OK, EXIT_REFUSED, EXIT_INCOMPLETE = 0, 2, 3
OK, FAILED, UNKNOWN, UNREPORTED = "ok", "failed", "unknown", "never reported"
OUTCOMES = (OK, FAILED, UNKNOWN, UNREPORTED)
COMPARISON = ("comparison source: the register", "comparison source: deep-lint")
# the acquisition that vouches for the slice's requirement files (CR-AUDIT11 F2), never owed
REQUIREMENT_ACQUISITION = "requirement files"

# The structural rules each acquisition's input must meet, one row per acquisition (a name, or a
# name's prefix ending in ": " for one per root), in the order a pick and a record make them: each
# row names only rules its input's structure decides. The suite fails a pick or a record that
# registers an acquisition with no row here; the code at each site fails on input that breaks what
# its row names. What no row can decide is THE LIMIT (the docstring): a cut that leaves an unframed
# Markdown page (UNFRAMED's) structurally valid and shorter.
WHOLE_INPUT = (
    ("premises", "each required root's kind established by its own metadata (missing, or an error "
                 "that is never read as missing, are told apart), then read: a folder listed, a "
                 "file opened and a byte read; anything short is a broken premise"),
    ("slices.json", "strict UTF-8 and one JSON document parsed whole (no key given twice, no NaN "
                    "or Infinity, nothing after it), of the state's exact shape, each audit's "
                    "completeness agreeing with its reasons; missing only when its own metadata "
                    "says so"),
    ("hash scan: ", "the root's kind established by its own metadata (only the optional root may be "
                    "absent, and only so); every folder listed whole (names strict UTF-8, a linked "
                    "folder unread, never skipped); every file hashed to its end"),
    ("owed content", "each owed path's kind established by its own metadata (a link to nothing, "
                     "there but unreadable, a failure), a folder walked whole and each file it "
                     "lists looked at so; a deletion only with its absence established (its own "
                     "metadata reporting it missing, or a folder listed whole holding no file) "
                     "and, for a hash key, no folder down to it unread"),
    ("rotation", "every listing whole, as the hash scan's; the skills folder and each SKILL.md "
                 "looked at, an error a failure"),
    ("lifecycle rows", "strict UTF-8; raw lines, every one read (no fence or comment hides one); "
                       "a lifecycle table, each one whole: its header, its separator of ten cells "
                       "on the next line, whole rows; no rows outside a table, no damaged "
                       "lifecycle header, no table line inside a block quote (unframed Markdown: "
                       "THE LIMIT)"),
    ("inventory", "every listing whole, as the hash scan's; each file found looked at to tell a "
                  "script, an error a failure; each standing-rules file strict UTF-8, its "
                  "sections by markdown-it-py 4.2.0 within the adapter's declared syntax, every "
                  "line that looks like a section accounted for (else undecidable), at least one "
                  "section (unframed Markdown: THE LIMIT)"),
    ("due rows' files", "each row's path looked at by its own metadata, an error a failure; a folder "
                        "walked whole"),
    ("comparison source: the register", "strict UTF-8; raw lines, every one read; its `## Open` "
                                        "and `## Closed` sections, each heading once, Open first "
                                        "(unframed Markdown: THE LIMIT)"),
    ("comparison source: deep-lint", "strict UTF-8; raw lines, every one read; the latest "
                                     "deep-lint heading in any form (its kind before its title, "
                                     "whatever its date field became) is in its exact form (no "
                                     "older entry read in its place), its entry framed by its "
                                     "fields: its complete `- **Changed**:` and "
                                     "`- **Conflicts**:` fields, each followed by a value, before "
                                     "the next line that begins with `#` after any container "
                                     "prefix (the log around it unframed Markdown: THE LIMIT)"),
    ("requirement files", "it reads nothing itself: each requirement file of the slice "
                          "(REQUIREMENTS), as the hash scan saw it, judged apart from whatever "
                          "lists its path; one with no file at its path, no failure of the scan "
                          "covering it, is absent and unknown, since no reviewer can read it, "
                          "and stays listed (here, or on the reading list when that holds it); "
                          "one the scan could not read is that scan's own failure"),
    ("manifest", "strict UTF-8 and one JSON document parsed whole, strictly, of the manifest's exact "
                 "shape (its completeness agreeing with its acquisitions, its owed files on its "
                 "reading list, or held for the second pass among its sources)"),
    ("coverage", "strict UTF-8; raw lines, every one read: exactly one line of the report declares "
                 "`## Not read`, wherever it stands, and it is exactly that heading; exactly one "
                 "line reads as its closing line, `END NOT READ: <n>`, the report's last; between "
                 "them mandatory paths as printed (or raw), each with its exact characters, or "
                 "`none`, n the path lines (0 with `none`)"),
    ("slices.json read back", "the new state in its temporary file beside slices.json, read as "
                              "slices.json is read and equal to what was written, before it "
                              "replaces slices.json"),
    ("rescan: ", "as the hash scan's; a diagnostic after the record is made, said when it does not "
                 "succeed"),
)


def whole_input_row(name):
    """The WHOLE_INPUT row of an acquisition's name, or None."""
    return next((row for row in WHOLE_INPUT
                 if name == row[0] or (row[0].endswith(": ") and name.startswith(row[0]))), None)


# THE LIMIT, acquisition by acquisition: the unframed Markdown pages each reads (vault-relative).
UNFRAMED = (("lifecycle rows", (LIFECYCLE_REL,)), ("inventory", STANDING_RULES),
            ("comparison source: the register", (REGISTER_REL,)),
            ("comparison source: deep-lint", (LOG_REL,)))
# The pick's `limit:` lines, one at the end of each part of its output that rests on such a page
# (AUDIT.md, step 1, names the same backstops).
LIMIT_LINES = {
    "due rows": ("limit: the lifecycle page is read by its structure alone (strict text, raw "
                 "lines, whole tables), so rows a cut took from it, leaving it a "
                 "structurally valid shorter page, cannot be told from the page; the backstop is "
                 "the hash scan: a page cut since the baseline reads as changed, named among the "
                 "files held for the second pass above (AUDIT.md, step 1)"),
    "missing rows": ("limit: CLAUDE.md and CUSTOMISATION.md are read for their sections by their "
                     "structure alone (markdown-it-py, within the adapter's declared syntax), so "
                     "sections a cut took from either, leaving it a structurally valid shorter "
                     "file, cannot be told from the file; the backstop is the hash scan: a file "
                     "cut since the baseline reads as changed and is on the reading list "
                     "(AUDIT.md, step 1)"),
    "sources": ("limit: the register (its `## Open` and `## Closed` sections) and wiki/log.md "
                "(deep-lint's latest entry, with its `Changed` and `Conflicts` fields complete) "
                "are read by their structure alone, so what a cut took from either, leaving it a "
                "structurally valid shorter page, cannot be told from the page; the backstops are "
                "the hash scan for the register (cut since the baseline, it reads as changed: held "
                "above, or on the reading list in its own week) and step 7's label check against "
                "the register, the only one for wiki/log.md, which is not hashed (AUDIT.md, steps "
                "1 and 7)"),
}


class Refusal(Exception):
    """A refusal: printed as its message, exit 2, nothing else printed."""


def probe_failed(what):
    raise Refusal("PROBE FAILED: %s" % what)


def now():
    """The local time with its offset, to the microsecond: manifests and records are ordered by it."""
    return datetime.datetime.now().astimezone()


def stamp(moment):
    return moment.isoformat(timespec="microseconds")


def parse_time(text):
    """An ISO time with an offset, or None."""
    if not isinstance(text, str):
        return None
    try:
        moment = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


# ------------------------------------------------------------------ whole input --------------

def read_text(path):
    """The file's text, decoded as strict UTF-8: undecodable bytes raise UnicodeDecodeError (its
    `start` the first bad byte's offset), never a replacement character. OSError as open raises
    it. Newlines are left as they are (text_lines splits them)."""
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8")


def text_lines(text):
    """The text's lines, split at newlines only (a carriage return before one stays on its line,
    for the consumer to strip), so line numbers are an editor's: str.splitlines also splits at form
    feeds and Unicode line separators, which would tear a table row and shift every number below."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def undecodable(err):
    return "not UTF-8: undecodable bytes at byte %d" % err.start


def unique_keys(pairs):
    """A JSON object's pairs as a dict, refusing a key given twice, which would silently keep only
    its last value."""
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("the key %r is given twice" % key)
        obj[key] = value
    return obj


def no_constant(name):
    raise ValueError("%s is not JSON" % name)


def strict_json(text):
    """JSON read whole and strictly: no key given twice, no NaN or Infinity (ValueError)."""
    return json.loads(text, object_pairs_hook=unique_keys, parse_constant=no_constant)


def look(path, follow=True, lstat=None, stat=None):
    """What a path is, by its own metadata, as (kind, reason): `absent` only when lstat reports no
    such entry (or a path component that is not a folder), which is absence established; `folder`,
    `file`, `link` (a symbolic link, not followed) or `other`; `broken` for a link followed to a
    target that is missing; and `error`, with its reason, for any other error, which is never read
    as absence (os.path.isdir, isfile, exists and lexists all would). With `follow`, a link is
    looked through. Every look at a path in this script goes through here; `lstat` and `stat`
    stand in for the os calls in the in-run controls."""
    lstat, stat = lstat or os.lstat, stat or os.stat
    try:
        mode = lstat(path).st_mode
    except (FileNotFoundError, NotADirectoryError):
        return "absent", None
    except OSError as err:
        return "error", err.strerror or str(err)
    if S_ISLNK(mode):
        if not follow:
            return "link", None
        try:
            mode = stat(path).st_mode
        except (FileNotFoundError, NotADirectoryError):
            return "broken", "a symbolic link whose target is missing"
        except OSError as err:
            return "error", err.strerror or str(err)
    return ("folder" if S_ISDIR(mode) else "file" if S_ISREG(mode) else "other"), None


def kind_of(path, errors, folder=False):
    """What a path is, following links: `folder`, `file`, `other`, or None when its absence is
    established. An error, or a link to nothing, goes to `errors` as (path, reason, folder) and
    gives `error`, so that a path that could not be looked at never reads as absent."""
    kind, reason = look(path)
    if kind == "absent":
        return None
    if kind in ("error", "broken"):
        errors.append((path, reason, folder))
        return "error"
    return kind


def strict_name(name):
    """Whether a file or folder name read from a listing is valid UTF-8: a name that is not comes
    back from the listing with its bad bytes escaped as lone surrogates, which no strict encoding
    accepts."""
    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


# ------------------------------------------------------------------ printing -----------------

# What a terminal could hide or redraw: control, format, private-use, surrogate, unassigned and
# line or paragraph separator characters (a tab aside; a newline is escaped too, since every printed
# line must stay one line). The encoding is pass_order.py's.
HIDING = ("Cc", "Cf", "Co", "Cs", "Cn", "Zl", "Zp")
ESCAPED_MARK = "escaped: "
ESCAPED_NOTE = ("ESCAPED: each line below that begins `escaped: ` held a character a terminal could "
                "hide, or began so itself; after that mark it is written with each such character "
                "as \\xHH, \\uHHHH or \\UHHHHHHHH and every backslash doubled (pass_order.py's "
                "encoding): read its escapes left to right to recover the line, and name a "
                "reading-list path so printed under `## Not read` as printed")
ESCAPE_RE = re.compile(r"\\(?:(\\)|x([0-9a-f]{2})|u([0-9a-f]{4})|U([0-9a-f]{8}))")


def hides(char):
    return char != "\t" and unicodedata.category(char) in HIDING


def escape(char):
    code = ord(char)
    return "\\x%02x" % code if code < 0x100 else "\\u%04x" % code if code < 0x10000 \
        else "\\U%08x" % code


def encode(text):
    """The text in the declared reversible encoding: each character a terminal could hide written
    as its escape, every backslash doubled, every other character itself."""
    return "".join("\\\\" if char == "\\" else escape(char) if hides(char) else char
                   for char in text)


def decode(shown):
    """The text an encoded print stands for, its escapes read left to right; ValueError for a
    backslash that starts no escape (no print of `encode`)."""
    out, at = [], 0
    while at < len(shown):
        if shown[at] != "\\":
            out.append(shown[at])
            at += 1
            continue
        match = ESCAPE_RE.match(shown, at)
        if match is None:
            raise ValueError("a backslash at %d starts no escape" % at)
        out.append("\\" if match.group(1) else chr(int(next(g for g in match.groups()[1:] if g),
                                                       16)))
        at = match.end()
    return "".join(out)


def shown_line(line):
    """(the line as printed, whether it was escaped): itself when it holds no character a terminal
    could hide and does not begin with the mark; otherwise the mark and its encoding."""
    if line.startswith(ESCAPED_MARK) or any(hides(char) for char in line):
        return ESCAPED_MARK + encode(line), True
    return line, False


def emit(lines):
    """Prints the lines, each as shown_line shows it, with the ESCAPED note before the first line
    escaped: no character a terminal could hide reaches it from this script."""
    shown, declared = [], False
    for line in lines:
        text, escaped = shown_line(line)
        if escaped and not declared:
            shown.append(ESCAPED_NOTE)
            declared = True
        shown.append(text)
    print("\n".join(shown))


# ------------------------------------------------------------------ the registry -------------

# The steps under way, innermost last: each an Acquisition (a read) or a Writing (a write). Every
# file this script opens or folder it lists is read inside an acquisition, and every write inside a
# writing; the suite's independent inventory watches the opens against this stack.
ACTIVE = []


class Acquisition(object):
    """One registered acquisition: what it reads, what its failure leaves UNKNOWN, and its outcome,
    reported once by done(): ok, failed (with each path it could not read and why) or unknown
    (with why). One that never reports is `never reported`, which leaves the manifest
    incomplete."""

    kind = "acquisition"

    def __init__(self, name, what, affects):
        self.name, self.what, self.affects = name, what, affects
        self.status, self.failures, self.unknowns = None, [], []

    def __enter__(self):
        ACTIVE.append(self)
        return self

    def __exit__(self, kind, value, trace):
        ACTIVE.remove(self)
        return False

    def fail(self, path, reason, entry=None):
        self.failures.append((entry or path, path, reason))

    def unknown(self, reason):
        self.unknowns.append(reason)

    def done(self):
        self.status = FAILED if self.failures else UNKNOWN if self.unknowns else OK

    def outcome(self):
        return self.status or UNREPORTED

    def detail(self):
        if self.outcome() == UNREPORTED:
            return "it never reported an outcome"
        parts = ["%s: %s" % (path, reason) for _, path, reason in self.failures]
        return "; ".join(parts + self.unknowns)


class Writing(object):
    """A write under way, for the inventory of opens."""

    kind = "write"

    def __init__(self, path):
        self.name = "write: %s" % path

    def __enter__(self):
        ACTIVE.append(self)
        return self

    def __exit__(self, kind, value, trace):
        ACTIVE.remove(self)
        return False


class Registry(object):
    """The acquisitions of one pick or one record, in the order they were registered."""

    def __init__(self):
        self.entries = []

    def acquire(self, name, what, affects):
        entry = Acquisition(name, what, affects)
        self.entries.append(entry)
        return entry

    def get(self, name):
        return next((e for e in self.entries if e.name == name), None)

    def complete(self):
        return bool(self.entries) and all(e.outcome() == OK for e in self.entries)

    def short(self):
        return [e for e in self.entries if e.outcome() != OK]

    def summary(self):
        return [{"name": e.name, "status": e.outcome(), "detail": e.detail()}
                for e in self.entries]


# ------------------------------------------------------------------ paths and files ----------

def looked_at(kind, reason, what):
    """Why a path is not the kind wanted, from look's (kind, reason): an error is told as an error,
    never as a missing path."""
    if kind == "absent":
        return "is missing"
    if kind in ("error", "broken"):
        return "could not be looked at (%s), which is never read as missing" % reason
    return "is not a %s" % what


def store_tools():
    """The tools folder in the run store (LLM_WIKI_STORE, else ~/.llm-wiki), as the other shipped
    tools name the store; the audit's state lives there because this script's own folder ships."""
    store = os.environ.get("LLM_WIKI_STORE") or os.path.join("~", ".llm-wiki")
    return os.path.abspath(os.path.join(os.path.expanduser(store), "tools"))


def resolve_state(args):
    state = os.path.abspath(os.path.expanduser(
        args.state or os.path.join(store_tools(), STATE_FOLDER, STATE_NAME)))
    kind, reason = look(os.path.dirname(state))
    if kind == "absent":
        probe_failed("the folder for slices.json does not exist: %s" % os.path.dirname(state))
    if kind != "folder":
        probe_failed("the folder for slices.json, %s, %s" % (os.path.dirname(state),
                                                            looked_at(kind, reason, "folder")))
    return state


def check_root(path, folder, note=""):
    """A required root exists as a folder or a file and can be read (a folder listed, a file
    opened); otherwise PROBE FAILED, before anything is hashed or written. Its kind is established
    by its own metadata: a root that could not be looked at is said so, never called missing."""
    want = "folder" if folder else "file"
    kind, reason = look(path)
    if kind != want:
        probe_failed("the required root %s %s%s; the scan would be partial, so nothing is picked "
                     "and no manifest is written" % (path, looked_at(kind, reason, want), note))
    try:
        if folder:
            os.listdir(path)
        else:
            with open(path, "rb") as handle:
                handle.read(1)
    except OSError as err:
        probe_failed("the required root %s cannot be read (%s); the scan would be partial, so "
                     "nothing is picked and no manifest is written" % (path, err.strerror or err))


def resolve(registry, args):
    """The vault, tools, hooks and state paths, spelled as given (abspath, never realpath, so the
    reading list keeps the caller's spelling), with the premises checked: every required root
    exists and can be read."""
    vault = args.vault or os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("LLM_WIKI_VAULT")
    if not vault:
        probe_failed("no vault: pass --vault, or set CLAUDE_PROJECT_DIR or LLM_WIKI_VAULT")
    vault = os.path.abspath(os.path.expanduser(vault))
    for rel, want in (("CLAUDE.md", "file"), (".claude", "folder")):
        kind, reason = look(os.path.join(vault, rel))
        if kind == "absent":
            probe_failed("the vault %s holds no %s" % (vault, "CLAUDE.md" if want == "file"
                                                        else ".claude folder"))
        if kind != want:
            probe_failed("the vault's %s %s" % (rel, looked_at(kind, reason, want)))
    roots, notes = {}, {}
    for name, given, default in (("tools", args.tools, store_tools()),
                                 ("hooks", args.hooks, None)):
        if given:
            path = os.path.abspath(os.path.expanduser(given))
            kind, reason = look(path)
            if kind in ("error", "broken"):
                probe_failed("--%s %s %s" % (name, path, looked_at(kind, reason, "folder")))
            if kind != "folder":
                probe_failed("--%s %s is not a folder%s" % (name, path, ": it is missing"
                                                            if kind == "absent" else ""))
            notes[name] = ""
        else:
            path = default if name == "tools" else os.path.join(os.path.dirname(roots["tools"]),
                                                                "hooks")
            notes[name] = " (derived; pass --%s to name it)" % name
        roots[name] = path
    with registry.acquire("premises", "each required root, once, before anything else",
                          "everything: a broken premise refuses") as acquisition:
        for rel, folder in REQUIRED_VAULT_ROOTS:
            check_root(os.path.join(vault, rel), folder)
        for name in ("tools", "hooks"):
            check_root(roots[name], True, notes[name])
        acquisition.done()
    return vault, roots["tools"], roots["hooks"], resolve_state(args)


def inside(path, folder):
    real, top = os.path.realpath(path), os.path.realpath(folder)
    return real == top or real.startswith(top.rstrip(os.sep) + os.sep)


def check_manifest_out(path, vault, tools, hooks, state):
    """--manifest-out names one file in an existing folder, outside every hashed root (an absent
    optional root included, whose path the manifest would otherwise become)."""
    folder = os.path.dirname(path)
    kind, reason = look(folder)
    if kind == "absent":
        raise Refusal("REFUSED: the folder for --manifest-out does not exist: %s (slice.py creates "
                      "no folder; make it first)" % folder)
    if kind != "folder":
        raise Refusal("REFUSED: the folder for --manifest-out, %s, %s" % (
            folder, looked_at(kind, reason, "folder")))
    kind, reason = look(path)
    if kind == "folder":
        raise Refusal("REFUSED: --manifest-out %s is a folder, not a file" % path)
    if kind == "error":
        raise Refusal("REFUSED: --manifest-out %s could not be looked at (%s)" % (path, reason))
    if os.path.realpath(path) == os.path.realpath(state):
        raise Refusal("REFUSED: --manifest-out names slices.json itself")
    tops = [os.path.join(vault, rel) for rel in VAULT_ROOTS] + [tools, hooks]
    for top in tops:
        if inside(path, top):
            raise Refusal("REFUSED: --manifest-out %s lies inside the hashed root %s, so the next "
                          "pick would list it as changed; write it outside the roots" % (path, top))


def skip_file(name):
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in SKIP_FILES)


def walk_files(top, errors, skipped=None, required=None, when="the walk", seen=None,
               folder=None):
    """Every file under `top` (or `top` itself when it is a file), sorted, leaving out the skipped
    folders and files, each counted in `skipped` when given. A folder that cannot be listed is
    recorded in `errors` as (folder, reason, True), never skipped silently, and so is a folder
    holding a name that is not valid UTF-8 (none of its files or folders is read, since the listing
    could not be read whole) and a symbolic link to a folder below `top`, which is never followed.
    WHOLE: `top` itself is looked at by its own metadata (look): it is absent only when that
    metadata says so, and an error looking at it goes to `errors` (keyed as a folder when `folder`
    says so, else when a folder is required), never read as nothing there; so does a `top` that is
    a symbolic link whose target is missing, which is there but holds nothing to read. With
    `required` ("folder" or "file"), the walk itself records `top` missing, or of the wrong kind, as
    it reads it: a required root gone between any earlier check and this walk is unread, never
    empty. A readable empty folder gives no file and no error. `seen` (a dict), when given,
    receives under "top" what `top` was established to be."""
    kind, reason = look(top)
    if seen is not None:
        seen["top"] = kind
    if kind == "error":
        errors.append((top, "it could not be looked at at %s (%s), so it is not read as absent"
                       % (when, reason), required == "folder" if folder is None else folder))
        return []
    if kind == "broken":   # the link is there, what it names is not: unreadable, never a file read
        errors.append((top, "it is a symbolic link whose target is missing at %s, so nothing of it "
                       "can be read, and it is not read as absent" % when,
                       required == "folder" if folder is None else folder))
        return []
    if kind == "folder":
        if required == "file":
            errors.append((top, "it is a folder, not a file, at %s" % when, False))
            return []
    elif kind == "absent":
        if required:
            errors.append((top, "it is missing at %s" % when, required == "folder"))
        return []
    else:   # a file or another entry (a socket, say): there, and read as a file (or failing so)
        if required == "folder":
            errors.append((top, "it is not a folder at %s" % when, True))
            return []
        return [] if skip_file(os.path.basename(top)) else [top]
    found = []

    def failed(err):
        errors.append((getattr(err, "filename", None) or top, err.strerror or str(err), True))

    for dirpath, dirnames, filenames in os.walk(top, onerror=failed):
        bad = sorted(n for n in dirnames + filenames if not strict_name(n))
        if bad:
            errors.append((dirpath, "it holds %d name(s) that are not valid UTF-8 (the first %s), "
                           "so its listing cannot be read whole" % (len(bad), ascii(os.fsencode(
                               bad[0]))), True))
            dirnames[:] = []
            continue
        kept = []
        for name in sorted(dirnames):
            if name in SKIP_DIRS:
                if skipped is not None:
                    skipped[name] = skipped.get(name, 0) + 1
                continue
            below, why = look(os.path.join(dirpath, name), follow=False)
            if below == "folder":
                kept.append(name)
            elif below == "link":
                errors.append((os.path.join(dirpath, name), "a symbolic link to a folder, which "
                               "no walk follows, so the files below it are not read", True))
            else:   # gone since its folder was listed, or an error: never read as nothing there
                errors.append((os.path.join(dirpath, name), "it %s at %s" % (
                    "vanished after its folder was listed" if below == "absent"
                    else "could not be looked at (%s)" % why, when), True))
        dirnames[:] = kept
        for name in sorted(filenames):
            pattern = next((p for p in SKIP_FILES if fnmatch.fnmatchcase(name, p)), None)
            if pattern is None:
                found.append(os.path.join(dirpath, name))
            elif skipped is not None:
                skipped[pattern] = skipped.get(pattern, 0) + 1
    return found


class Expect(object):
    """What the hash scan saw, so that a later walk can tell a folder or file gone since then
    (unread) from one that was never there (absent): `of(path)` is "folder" when the scan hashed a
    file below it, "file" when it hashed it, else None."""

    def __init__(self, paths):
        self.files = set(os.path.normpath(p) for p in paths)
        self.folders = set()
        for path in self.files:
            folder = os.path.dirname(path)
            while folder and folder not in self.folders and folder != os.path.dirname(folder):
                self.folders.add(folder)
                folder = os.path.dirname(folder)

    def of(self, path):
        path = os.path.normpath(path)
        return "folder" if path in self.folders else "file" if path in self.files else None


class StateFilter(object):
    """Leaves out slices.json and its temporary files, which change at every record."""

    def __init__(self, state):
        self.name = os.path.basename(state)
        self.real = os.path.realpath(state)
        self.folder = os.path.realpath(os.path.dirname(state))

    def excludes(self, path):
        name = os.path.basename(path)
        if name == self.name:
            return os.path.realpath(path) == self.real
        if name.startswith("." + self.name + ".") and name.endswith(".tmp"):
            return os.path.realpath(os.path.dirname(path)) == self.folder
        return False


def hash_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def root_tops(vault, tools, hooks):
    """(label, base, path below base or "", "folder" | "file" | None when optional) for each hashed
    root, in scan order."""
    kinds = dict((rel, "folder" if folder else "file") for rel, folder in REQUIRED_VAULT_ROOTS)
    return ([("vault", vault, rel, kinds.get(rel)) for rel in VAULT_ROOTS]
            + [("tools", tools, "", "folder"), ("hooks", hooks, "", "folder")])


def make_key(label, base, path, folder=False):
    """A hash key, `<root label>/<path relative to that root>`; a folder's ends in `/`, so that it
    covers every key below it."""
    rel = os.path.relpath(path, base).replace(os.sep, "/")
    key = label if rel == "." else label + "/" + rel
    return key + "/" if folder else key


def key_for(path, vault, tools, hooks, folder=False):
    """The hash key of a path inside a hashed root, or None for a path outside them all. The path
    is matched as it is spelled first; failing that, with its folder resolved, against each root's
    real path (CR-AUDIT12 F3), so that the same file reached through another spelling of its root
    (the root's real path, or another link to it; a record given another spelling than its pick's)
    has the same key, and an omission never becomes an outside entry, which keeps no hash. Only
    the folder is resolved: a link that is the path's own last part keeps its own key, as the
    hash scan's walk keys it."""
    tops = root_tops(vault, tools, hooks)
    for label, base, rel, _ in tops:
        top = os.path.join(base, rel) if rel else base
        if path == top or path.startswith(top.rstrip(os.sep) + os.sep):
            return make_key(label, base, path, folder)
    bare = path.rstrip(os.sep) or path
    resolved = os.path.join(os.path.realpath(os.path.dirname(bare)), os.path.basename(bare))
    for label, base, rel, _ in tops:
        real = os.path.realpath(base)
        top = os.path.join(real, rel) if rel else real
        if resolved == top or resolved.startswith(top.rstrip(os.sep) + os.sep):
            return make_key(label, real, resolved, folder)
    return None


def hash_roots(registry, vault, tools, hooks, state_filter, step="hash scan"):
    """Current content hashes, keyed `<root label>/<path relative to that root>`, so a baseline
    survives a moved vault, one registered acquisition per root. Returns (hashes, paths by key,
    unread, absent roots, skipped): unread holds (key, path, reason) for each file that could not be
    hashed, each folder that could not be listed and each required root gone at its walk, a
    folder's key ending in `/`. Only the optional root can be absent."""
    hashes, paths, unread, absent, skipped = {}, {}, [], [], {}
    for label, base, rel, kind in root_tops(vault, tools, hooks):
        top = os.path.join(base, rel) if rel else base
        with registry.acquire("%s: %s" % (step, label + ("/" + rel if rel else "")),
                              "the content hash of every file under %s" % top,
                              "the changed files") as acquisition:
            errors, seen = [], {}
            files = walk_files(top, errors, skipped, required=kind, when="the %s" % step,
                               seen=seen)
            if kind is None and seen.get("top") == "absent":   # established, never an error
                absent.append(top)
            for path in files:
                if state_filter.excludes(path):
                    continue
                key = make_key(label, base, path)
                paths[key] = path
                try:
                    hashes[key] = hash_file(path)
                except OSError as err:
                    unread.append((key, path, err.strerror or str(err)))
                    acquisition.fail(path, err.strerror or str(err), key)
            for folder, reason, is_folder in errors:
                key = make_key(label, base, folder, folder=is_folder)
                unread.append((key, folder, reason))
                acquisition.fail(folder, reason, key)
            acquisition.done()
    return hashes, paths, unread, absent, skipped


def covered(key, unread):
    """Whether a hash key lies in what a pick could not read: an unread file, or a key below an
    unread folder (an entry ending in `/`)."""
    return any(key == entry or (entry.endswith("/") and key.startswith(entry)) for entry in unread)


def compare(stored, current, unread=()):
    """(changed, new, removed) keys. A key the pick could not read is never called removed."""
    changed = sorted(k for k in current if k in stored and stored[k] != current[k])
    new = sorted(k for k in current if k not in stored)
    removed = sorted(k for k in stored if k not in current and not covered(k, unread))
    return changed, new, removed


def merge_baseline(hashes, unread, previous):
    """The baseline a record stores: the manifest's hashes, except that nothing the audit did not
    read advances. An unread file keeps its previous hash, or stays absent when it had none, so the
    next pick lists it as new; every previous hash below an unread folder is kept. Returns (hashes,
    kept, absent, outside): kept as (entry, hashes kept), outside the entries that name no hashed
    root (absolute paths), which hold no hash to keep."""
    merged = dict(hashes)
    kept, absent, outside = [], [], []
    for entry in unread:
        if entry.startswith("/"):
            outside.append(entry)
        elif entry.endswith("/"):
            for key in [k for k in merged if k.startswith(entry)]:
                del merged[key]
            below = dict((k, v) for k, v in previous.items() if k.startswith(entry))
            merged.update(below)
            kept.append((entry, len(below)))
        elif entry in previous:
            merged[entry] = previous[entry]
            kept.append((entry, 1))
        else:
            merged.pop(entry, None)
            absent.append(entry)
    return merged, kept, absent, outside


def key_path(key, vault, tools, hooks):
    label, _, rel = key.partition("/")
    base = {"vault": vault, "tools": tools, "hooks": hooks}.get(label)
    if not base:
        return key
    return os.path.join(base, *rel.split("/")) if rel else base


def owed_files(entry, vault, tools, hooks, state_filter, errors, expect, seen):
    """The files an owed entry covers now: the file of a file key or an absolute file path, and
    every file below a folder key (a root's included) or an absolute folder; none when nothing is
    there now. A folder that cannot be listed, one the hash scan saw and this walk finds gone, and
    a path that could not be looked at go to `errors`; `seen` receives what the path was
    established to be. WHOLE: each file listed is looked at by its own metadata before it is
    listed, so that a symbolic link to nothing (there, but unreadable), an error or a file gone
    since its folder was listed fails the acquisition and keeps the debt, never credited as owed
    content on the reading list: nothing outside the hashed roots hashes it, so no other read
    would find it."""
    path = entry if entry.startswith("/") else key_path(entry.rstrip("/"), vault, tools, hooks)
    found = walk_files(path, errors, required=expect.of(path), when="the owed content", seen=seen,
                       folder=entry.endswith("/"))
    files = []
    for listed in found:
        if state_filter.excludes(listed):
            continue
        kind, reason = look(listed)
        if kind in ("file", "other"):
            files.append(listed)
            continue
        errors.append((listed, "it %s at the owed content, so it is not listed as read" % (
            "vanished after its folder was listed" if kind == "absent"
            else "is a symbolic link whose target is missing" if kind == "broken"
            else "could not be looked at (%s)" % reason if kind == "error"
            else "became a %s after its folder was listed" % kind), False))
    return files


def touches(entry, unread):
    """Whether an owed entry meets what the pick could not read: the entry itself, a folder above
    it, or, for a folder entry, anything below it."""
    return covered(entry, unread) or (entry.endswith("/")
                                      and any(u.startswith(entry) for u in unread))


def deleted_path(entry, vault, tools, hooks, unread, errors, top):
    """For an owed entry whose walk found no file of it and recorded no error: the path to list as
    deleted since its baseline, or None (with the reason in `errors` when it is a failure). WHOLE:
    its absence must be established, never read from an error: `top`, what its walk established the
    path to be, is `absent` (its own metadata reports it missing) or `folder` (listed whole, holding
    no file); a path that is there, though nothing of it is listed (a skipped name), is no deletion.
    A hash key is a deletion only when, besides, nothing the hash scan could not read meets it (its
    root, and every folder down to it, walked without failure); otherwise its absence cannot be told
    from a failed read, and it is an acquisition failure. A folder entry is listed with its trailing
    `/`."""
    if top not in ("absent", "folder"):
        return None
    if entry.startswith("/"):
        return entry
    path = key_path(entry.rstrip("/"), vault, tools, hooks)
    if touches(entry, unread):
        errors.append((path, "no file of it is there now, and the hash scan could not read all of "
                       "the folders down to it, so its deletion cannot be told from a failed read",
                       entry.endswith("/")))
        return None
    return path + "/" if entry.endswith("/") else path


def acquire_owed(registry, owed, vault, tools, hooks, state_filter, expect, unread):
    """[(owed entry, files now, whether its acquisition succeeded, the path to list as deleted or
    None)], one acquisition for all; `unread` the keys the hash scan could not read."""
    parts = []
    with registry.acquire("owed content", "the files of each owed entry",
                          "the owed content") as acquisition:
        for entry in owed:
            errors, seen = [], {}
            files = owed_files(entry["entry"], vault, tools, hooks, state_filter, errors, expect,
                               seen)
            deleted = None
            if not files and not errors:
                deleted = deleted_path(entry["entry"], vault, tools, hooks, unread, errors,
                                       seen.get("top"))
            for path, reason, folder in errors:
                acquisition.fail(path, reason, key_for(path, vault, tools, hooks, folder) or path)
            parts.append((entry, files, not errors, deleted))
        acquisition.done()
    return parts


# ------------------------------------------------------------------ slices.json and manifests -

def valid_date(text):
    if not isinstance(text, str) or not DATE_RE.match(text):
        return None
    try:
        return datetime.date(int(text[:4]), int(text[5:7]), int(text[8:10]))
    except ValueError:
        return None


def hashes_problems(hashes, where):
    if not isinstance(hashes, dict):
        return ["%s is not an object" % where]
    bad = [k for k, v in hashes.items() if not isinstance(v, str) or not HEX64_RE.match(v)]
    if bad:
        return ["%d hash value(s) in %s are not sha256 hex, first %r" % (len(bad), where, bad[0])]
    return []


def roots_problems(roots, where):
    if not isinstance(roots, dict) or set(roots) != set(ROOT_LABELS):
        return ["%s is not {%s}" % (where, ", ".join(ROOT_LABELS))]
    if not all(isinstance(v, str) and os.path.isabs(v) for v in roots.values()):
        return ["%s holds a path that is not absolute" % where]
    return []


def baseline_problems(base, where, keys):
    if not isinstance(base, dict) or set(base) != set(keys):
        return ["%s is not {%s}" % (where, ", ".join(sorted(keys)))]
    problems = []
    if parse_time(base["taken"]) is None:
        problems.append("%s.taken %r is not an ISO time with an offset" % (where, base["taken"]))
    if valid_date(base["date"]) is None:
        problems.append("%s.date %r is not YYYY-MM-DD" % (where, base["date"]))
    problems += roots_problems(base["roots"], where + ".roots")
    problems += hashes_problems(base["hashes"], where + ".hashes")
    return problems


BASELINE_KEYS = ("taken", "date", "roots", "hashes")
MANIFEST_KEYS = ("version", "kind", "taken", "date", "slice", "roots", "hashes", "complete",
                 "unread", "acquisitions", "labels_limited", "slices", "reading", "owed",
                 "requirements", "sources", "comparison")
SOURCE_KEYS = ("path", "comparison")
AUDIT_KEYS = ("date", "slice", "findings", "recorded", "manifest_taken", "complete", "reasons")
OWED_KEYS = ("entry", "since")
MANIFEST_OWED_KEYS = ("entry", "files", "held", "acquired", "deleted")
ACQUISITION_KEYS = ("name", "status", "detail")


def is_entry(entry):
    """An unread or owed entry: a hash key (`<root label>/...`, a folder's ending in `/`) or an
    absolute path outside the hashed roots."""
    return isinstance(entry, str) and bool(entry) and (
        entry.startswith("/") or entry.split("/", 1)[0] in ROOT_LABELS)


def owed_problems(owed):
    if not isinstance(owed, list):
        return ["owed is not a list"]
    problems = []
    for index, entry in enumerate(owed):
        if not isinstance(entry, dict) or set(entry) != set(OWED_KEYS):
            problems.append("owed[%d] is not {%s}" % (index, ", ".join(OWED_KEYS)))
        elif not is_entry(entry["entry"]):
            problems.append("owed[%d].entry %r is not a hash key or an absolute path"
                            % (index, entry["entry"]))
        elif valid_date(entry["since"]) is None:
            problems.append("owed[%d].since %r is not YYYY-MM-DD" % (index, entry["since"]))
    return problems


def state_problems(data):
    if not isinstance(data, dict):
        return ["the top level is not an object"]
    problems = []
    expected = {"version", "initialised", "audits", "baseline", "owed"}
    if set(data) != expected:
        problems.append("keys are %s, {%s} expected" % (sorted(data), ", ".join(sorted(expected))))
        return problems
    if data["version"] != STATE_VERSION:
        problems.append("version is %r, %d expected" % (data["version"], STATE_VERSION))
    if parse_time(data["initialised"]) is None:
        problems.append("initialised %r is not an ISO time with an offset" % (data["initialised"],))
    audits = data["audits"]
    if not isinstance(audits, list):
        problems.append("audits is not a list")
    else:
        for index, audit in enumerate(audits):
            if not isinstance(audit, dict) or set(audit) != set(AUDIT_KEYS):
                problems.append("audits[%d] is not {%s}" % (index, ", ".join(AUDIT_KEYS)))
                continue
            if valid_date(audit["date"]) is None:
                problems.append("audits[%d].date %r is not YYYY-MM-DD" % (index, audit["date"]))
            if not isinstance(audit["slice"], str) or not audit["slice"].strip():
                problems.append("audits[%d].slice is empty" % index)
            findings = audit["findings"]
            if isinstance(findings, bool) or not isinstance(findings, int) or findings < 0:
                problems.append("audits[%d].findings %r is not a count" % (index, findings))
            for field in ("recorded", "manifest_taken"):
                if parse_time(audit[field]) is None:
                    problems.append("audits[%d].%s %r is not an ISO time with an offset"
                                    % (index, field, audit[field]))
            reasons = audit["reasons"]
            if not isinstance(audit["complete"], bool):
                problems.append("audits[%d].complete %r is not true or false"
                                % (index, audit["complete"]))
            elif not isinstance(reasons, list) or not all(isinstance(r, str) and r.strip()
                                                          for r in reasons):
                problems.append("audits[%d].reasons is not a list of reasons" % index)
            elif audit["complete"] == bool(reasons):
                problems.append("audits[%d] says complete %s, yet holds %d reason(s) it was not"
                                % (index, str(audit["complete"]).lower(), len(reasons)))
    if data["baseline"] is None:
        if isinstance(audits, list) and audits:
            problems.append("audits are recorded but there is no baseline")
    else:
        problems += baseline_problems(data["baseline"], "baseline", BASELINE_KEYS)
    problems += owed_problems(data["owed"])
    return problems


MISSING_STATE = ("REFUSED: there is no slices.json at %s. `slice.py --init` is the install step and "
                 "creates it once; a slices.json missing after install is a continuity failure (the "
                 "audit history and the hash baseline are gone), never a fresh start. Restore it "
                 "from a copy; with no copy, report the loss before any new --init, which would "
                 "start the history over.")


def load_state(registry, path, name="slices.json"):
    """Its content when slices.json reads and validates; a Refusal otherwise, since the audit
    history lives in it and is never started over."""
    with registry.acquire(name, "the audit history, the baseline and the owed list in %s" % path,
                          "everything: an unreadable history refuses") as acquisition:
        advice = ("slice.py never starts over: restore slices.json from a copy, or mend what is "
                  "named, then run again")
        # missing only when its own metadata says so: an error is never a continuity failure
        kind, reason = look(path)
        if kind == "absent":
            raise Refusal(MISSING_STATE % path)
        if kind == "error":
            raise Refusal("REFUSED: slices.json could not be looked at (%s: %s), which is never read "
                          "as missing, so --init is no remedy; mend what is named (a permission, "
                          "say), then run again" % (path, reason))
        try:
            text = read_text(path)
        except OSError as err:
            raise Refusal("REFUSED: slices.json is unreadable (%s: %s); %s"
                          % (path, err.strerror or err, advice))
        except UnicodeDecodeError as err:
            raise Refusal("REFUSED: slices.json is unreadable (%s: %s); %s"
                          % (path, undecodable(err), advice))
        try:
            data = strict_json(text)
        except ValueError as err:
            raise Refusal("REFUSED: slices.json is malformed (%s: %s); %s" % (path, err, advice))
        problems = state_problems(data)
        if problems:
            raise Refusal("REFUSED: slices.json is malformed (%s: %s); %s"
                          % (path, "; ".join(problems[:5]), advice))
        acquisition.done()
    return data


def manifest_problems(data):
    """What makes a manifest malformed, beyond its baseline fields."""
    problems = []
    if data["version"] != MANIFEST_VERSION or data["kind"] != MANIFEST_KIND:
        return ["version %r, kind %r: version %d, kind %r expected"
                % (data["version"], data["kind"], MANIFEST_VERSION, MANIFEST_KIND)]
    if not isinstance(data["slice"], str) or not data["slice"].strip():
        problems.append("its slice is empty")
    problems += baseline_problems(dict((k, data[k]) for k in BASELINE_KEYS), "the manifest",
                                  BASELINE_KEYS)
    complete, unread, acquisitions = data["complete"], data["unread"], data["acquisitions"]
    if not isinstance(acquisitions, list) or not acquisitions or not all(
            isinstance(a, dict) and set(a) == set(ACQUISITION_KEYS) and isinstance(a["name"], str)
            and a["status"] in OUTCOMES and isinstance(a["detail"], str) for a in acquisitions):
        problems.append("its acquisitions are not a list of {%s} with a known status"
                        % ", ".join(ACQUISITION_KEYS))
        acquisitions = None
    if not isinstance(complete, bool):
        problems.append("its complete %r is not true or false" % (complete,))
    elif acquisitions is not None and complete != all(a["status"] == OK for a in acquisitions):
        problems.append("it says complete %s, yet %d acquisition(s) did not report ok"
                        % (str(complete).lower(), sum(1 for a in acquisitions if a["status"] != OK)))
    if not isinstance(unread, list) or not all(is_entry(e) for e in unread):
        problems.append("its unread is not a list of hash keys and absolute paths")
    elif complete is True and unread:
        problems.append("it says complete true, yet lists %d unread path(s)" % len(unread))
    if not isinstance(data["labels_limited"], bool):
        problems.append("its labels_limited is not true or false")
    elif complete is True and data["labels_limited"]:
        problems.append("it says complete true, yet its labels are limited")
    slices, reading = data["slices"], data["reading"]
    if not isinstance(slices, list) or not slices or not all(
            isinstance(s, str) and s.strip() for s in slices) or data["slice"] not in slices:
        problems.append("its slices are not a list of names holding its slice")
    if not isinstance(reading, list) or not all(isinstance(p, str) and os.path.isabs(p)
                                                for p in reading):
        problems.append("its reading list is not a list of absolute paths")
        reading = []
    # the other mandatory inputs (D18): the requirement files and the second-pass sources, each an
    # absolute path off the reading list, named once across the three kinds
    requirements, sources = data["requirements"], data["sources"]
    if not isinstance(requirements, list) or not all(
            isinstance(p, str) and os.path.isabs(p) and p not in reading for p in requirements):
        problems.append("its requirements are not a list of absolute paths off its reading list")
        requirements = []
    if not isinstance(sources, list) or not all(
            isinstance(s, dict) and set(s) == set(SOURCE_KEYS) and isinstance(s["path"], str)
            and os.path.isabs(s["path"]) and s["path"] not in reading
            and isinstance(s["comparison"], bool) for s in sources):
        problems.append("its sources are not a list of {%s} off its reading list"
                        % ", ".join(SOURCE_KEYS))
        sources = []
    named = list(requirements) + [s["path"] for s in sources]
    if len(set(named)) != len(named) or set(named) & set(requirements) & set(
            s["path"] for s in sources):
        problems.append("a requirement file or a second-pass source is listed twice")
    # the comparison sources, whatever their phase (CR-AUDIT11 F3): each a reading-list path or a
    # second-pass source, once, and the sources' own marks agreeing with the list
    comparison, source_paths = data["comparison"], [s["path"] for s in sources]
    if not isinstance(comparison, list) or not all(
            isinstance(p, str) and (p in reading or p in source_paths) for p in comparison) \
            or len(set(comparison)) != len(comparison) \
            or any(s["comparison"] != (s["path"] in comparison) for s in sources):
        problems.append("its comparison sources are not a list of its reading-list paths and "
                        "second-pass sources, once each, agreeing with its sources' marks")
    # each owed entry's files, found before the held sources left the reading list (CR-AUDIT13
    # F2): those on its reading list, and those held for the second pass, among its sources
    owed = data["owed"]
    if not isinstance(owed, list) or not all(
            isinstance(o, dict) and set(o) == set(MANIFEST_OWED_KEYS) and is_entry(o["entry"])
            and isinstance(o["acquired"], bool) and isinstance(o["deleted"], bool)
            and (o["acquired"] or not o["deleted"]) and isinstance(o["files"], list)
            and all(f in reading for f in o["files"]) and isinstance(o["held"], list)
            and all(h in source_paths for h in o["held"]) for o in owed):
        problems.append("its owed is not a list of {%s} whose files are on its reading list and "
                        "whose held files are among its second-pass sources"
                        % ", ".join(MANIFEST_OWED_KEYS))
    return problems


def load_manifest(registry, path):
    """The manifest a pick wrote with --manifest-out, validated; a Refusal otherwise."""
    tail = "; slices.json unchanged"
    with registry.acquire("manifest", "the manifest %s" % path,
                          "everything: an unreadable manifest refuses") as acquisition:
        try:
            text = read_text(path)
        except OSError as err:
            raise Refusal("REFUSED: the manifest is unreadable (%s: %s)%s"
                          % (path, err.strerror or err, tail))
        except UnicodeDecodeError as err:
            raise Refusal("REFUSED: the manifest is unreadable (%s: %s)%s"
                          % (path, undecodable(err), tail))
        try:
            data = strict_json(text)
        except ValueError as err:
            raise Refusal("REFUSED: the manifest is malformed (%s: %s)%s" % (path, err, tail))
        if not isinstance(data, dict) or set(data) != set(MANIFEST_KEYS):
            problems = ["it is not {%s}" % ", ".join(MANIFEST_KEYS)]
        else:
            problems = manifest_problems(data)
        if problems:
            raise Refusal("REFUSED: the manifest is malformed (%s: %s)%s"
                          % (path, "; ".join(problems[:5]), tail))
        acquisition.done()
    return data


def write_atomic(path, data, exclusive=False, verify=None):
    """The one place this script writes: JSON through a temporary file in the target's folder,
    written and synced, then, when `verify` is given, `verify(temporary)`, which raises to stop, and
    only then put in place in one step: an atomic replace, or, with `exclusive`, a hard link that
    fails when the target exists. Every failure before that step removes the temporary file and is
    raised, the target unchanged; nothing after it raises. Returns the notes to print: a temporary
    file it could not remove (never read as removed)."""

    def remove(temporary):
        """None once the temporary file is gone, else why it could not be removed."""
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            return None
        except OSError as err:
            return "a temporary file was left at %s (%s)" % (temporary, err.strerror or err)
        return None

    with Writing(path):
        folder = os.path.dirname(path)
        handle, temporary = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".",
                                             suffix=".tmp", dir=folder)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(data, stream, indent=1, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            if verify is not None:
                verify(temporary)
            if exclusive:
                os.link(temporary, path)
            else:
                os.replace(temporary, path)
        except BaseException as error:
            left = remove(temporary)
            if left is not None and isinstance(error, Refusal):
                raise Refusal("%s; %s" % (error, left))
            if left is not None and isinstance(error, OSError):
                error.left_behind = left
            raise
        # the target is in place: from here nothing is raised
        left = remove(temporary) if exclusive else None
        return [left] if left else []


def write_manifest(path, manifest):
    try:
        write_atomic(path, manifest)
    except OSError as err:
        raise Refusal("REFUSED: the manifest could not be written to %s (%s)"
                      % (path, err.strerror or err))


# ------------------------------------------------------------------ the reviewer's coverage --

def parse_not_read(text, paths):
    """(the mandatory paths the reviewer did not read, None), or (None, why the report's
    `## Not read` section is refused). `paths` are the audit's mandatory inputs: its reading list,
    its requirement files and its second-pass sources.

    THE COVERAGE PROTOCOL (raw lines, D18). The record is the declaration: the one line of the whole
    raw report that declares `## Not read`, the lines after it, and its one closing line.
    - A declaring line is any line DECLARATION_RE matches: after any spaces, tabs, `>` marks or
      list markers, a `#` heading of any level whose text begins with the words `not read`, in any
      letter case. Every line of the report is counted, wherever it stands: inside a code block, a
      list item, a block quote or an HTML comment as much as anywhere, since no fence or comment is
      interpreted. Exactly one is required, and it must be exactly `## Not read` at the start of its
      line (spaces after it forgiven): none, more than one, or one in another form refuses.
    - A closing line is any line END_NEAR_RE matches (the words `end`, `not`, `read` first, after
      any other characters but letters and digits). Exactly one is required in the whole report:
      after the heading, exactly `END NOT READ: <n>` (spaces around it forgiven), and the report's
      last line but blank ones.
    - Whole: between the heading and the closing line only blank lines, the single word `none`
      (alone), or path lines, each naming a mandatory path as the pick prints it (`escaped: ` and
      its encoding when it holds a character a terminal could hide) or as the path itself, with its
      exact characters: only its newline is removed, so two paths that differ only by a space at
      their end stay two, each owing its own debt; n is the number of path lines (0 with `none`).
      Whitespace is forgiven only around control syntax: the heading, `none`, the END line and a
      blank line.
    - Torn: anything else, refused with nothing read from it: no declaration, two, one in another
      form; an empty section; a heading after the declaration (it would be read only in part);
      no closing line, two, one not exact, one not last (a report cut after any whole line lacks
      its closing line or miscounts); a line neither `none` nor a mandatory path; a count that does
      not match.
    - Examples: text that looks like the declaration or its closing line counts as one wherever it
      stands, so a template of the section in a code block, a quoted section or a commented one is
      a second declaration and refuses the report: the reviewer writes the heading and the END line
      once each, and quotes neither at the start of a line anywhere else."""
    lines = text_lines(text)
    declared = [number for number, line in enumerate(lines, 1) if DECLARATION_RE.match(line)]
    if not declared:
        return None, ("it holds no section headed exactly `%s`: no line of it declares one, "
                      "wherever it stands" % NOT_READ_HEADING)
    if len(declared) > 1:
        return None, ("it holds %d sections headed `%s` (lines %s), each line counted wherever it "
                      "stands (a code block, a list, a quote and a comment included), so which one "
                      "counts is unknown" % (len(declared), NOT_READ_HEADING,
                                             ", ".join(str(n) for n in declared[:6])))
    start = declared[0]
    if lines[start - 1].rstrip() != NOT_READ_HEADING:
        return None, ("it holds no section headed exactly `%s`; the nearest heading is %r, at its "
                      "line %d" % (NOT_READ_HEADING, lines[start - 1].strip()[:80], start))
    closing = [number for number, line in enumerate(lines, 1) if END_NEAR_RE.match(line)]
    before = [number for number in closing if number < start]
    body, heading, end, after = [], None, None, None
    for number, line in enumerate(lines[start:], start + 1):
        if HEADING_RE.match(line):
            heading = (number, line.strip())
            break
        stripped = line.strip()
        if not stripped:
            continue
        if end is not None:
            after = after or (number, stripped)
            continue
        if END_NEAR_RE.match(line):   # the first line read as a closing line closes the section
            end = (number, stripped)
        else:   # control syntax (`none`) is read stripped; a path line keeps its exact characters
            body.append("none" if stripped == "none" else line)
    if not body:
        return None, ("its `%s` section is empty: it must name each mandatory path not read, one "
                      "per line, or say `none`, then close with `END NOT READ: <n>`"
                      % NOT_READ_HEADING)
    if heading is not None:
        return None, ("its `%s` section is not the report's last: the heading %r follows it at "
                      "its line %d, so the section would be read only in part"
                      % (NOT_READ_HEADING, heading[1][:80], heading[0]))
    if end is None:
        return None, ("its `%s` section has no closing `END NOT READ: <n>` line, so it cannot be "
                      "told from a section cut short after a whole line; nothing is read from it"
                      % NOT_READ_HEADING)
    match = END_NOT_READ_RE.match(end[1])
    if match is None:
        return None, ("its `%s` section holds %r, which is not exactly its closing line "
                      "`END NOT READ: <n>`" % (NOT_READ_HEADING, end[1][:80]))
    if after is not None:
        return None, ("its `%s` section holds %r at its line %d, after its closing `END NOT READ` "
                      "line, which must be the report's last" % (NOT_READ_HEADING, after[1][:80],
                                                                  after[0]))
    if before:
        return None, ("its line %d, %r, reads as a closing `END NOT READ` line before its `%s` "
                      "heading: the whole report holds exactly one closing line"
                      % (before[0], lines[before[0] - 1].strip()[:80], NOT_READ_HEADING))
    count = int(match.group(1))
    if "none" in body:
        if len(body) > 1:
            return None, ("its `%s` section puts `none` beside %d other line(s)"
                          % (NOT_READ_HEADING, len(body) - 1))
        if count != 0:
            return None, ("its `%s` section says `none` but closes `END NOT READ: %d`; `none` "
                          "counts 0" % (NOT_READ_HEADING, count))
        return [], None
    printed = dict((shown_line(path)[0], path) for path in paths)
    printed.update((path, path) for path in paths)
    named = []
    for line in body:
        if not line.startswith(("/", ESCAPED_MARK)):
            return None, ("its `%s` section holds a line that is neither a reading-list path nor "
                          "the single word `none`, nor any other mandatory path: %r"
                          % (NOT_READ_HEADING, line[:120]))
        if line not in printed:
            return None, ("its `%s` section names %s, which is not on this audit's reading list, "
                          "nor one of its requirement files or second-pass sources"
                          % (NOT_READ_HEADING, line))
        if printed[line] not in named:
            named.append(printed[line])
    if count != len(body):
        return None, ("its `%s` section closes `END NOT READ: %d`, but holds %d path line(s): the "
                      "count must match, so a section cut short is never read as whole"
                      % (NOT_READ_HEADING, count, len(body)))
    return named, None


def read_coverage(registry, report_path, paths):
    """The reviewer's coverage: the mandatory paths its report names under `## Not read` (an empty
    list for `none`); a Refusal, with nothing written, for anything else."""
    tail = "; slices.json unchanged"
    with registry.acquire("coverage", "the `%s` section of the reviewer's report %s"
                          % (NOT_READ_HEADING, report_path),
                          "the audit's coverage: a malformed section refuses") as acquisition:
        try:
            text = read_text(report_path)
        except OSError as err:
            raise Refusal("REFUSED: the report %s cannot be read (%s)%s"
                          % (report_path, err.strerror or err, tail))
        except UnicodeDecodeError as err:
            raise Refusal("REFUSED: the report %s cannot be read whole (%s)%s"
                          % (report_path, undecodable(err), tail))
        not_read, problem = parse_not_read(text, paths)
        if problem is not None:
            raise Refusal("REFUSED: the report %s: %s%s" % (report_path, problem, tail))
        acquisition.done()
    return not_read


# ------------------------------------------------------------------ the rotation -------------

def skill_dirs(vault, errors, expect):
    """The skill folders under .claude/skills that hold a SKILL.md; a listing that fails, a skills
    folder the hash scan saw and the listing finds gone, one holding a name that is not valid
    UTF-8, or a folder whose SKILL.md cannot be looked at (never read as a folder without one),
    goes to `errors`."""
    top = os.path.join(vault, SKILLS_REL)
    kind, reason = look(top)
    if kind == "absent":
        if expect.of(top):
            errors.append((top, "it is missing at the rotation listing", True))
        return []
    if kind != "folder":   # an error, never read as no skills folder
        errors.append((top, "it %s at the rotation listing" % looked_at(kind, reason, "folder"),
                       True))
        return []
    try:
        names = sorted(os.listdir(top))
    except OSError as err:
        errors.append((top, err.strerror or str(err), True))
        return []
    bad = [name for name in names if not strict_name(name)]
    if bad:
        errors.append((top, "it holds %d name(s) that are not valid UTF-8 (the first %s), so its "
                       "listing cannot be read whole" % (len(bad), ascii(os.fsencode(bad[0]))),
                       True))
        return []
    return [name for name in names
            if kind_of(os.path.join(top, name, SKILL_FILE), errors) == "file"]


def rotation(registry, vault, tools, hooks, state_filter, expect):
    """The rotating slices in rotation order: (name, files, note), one registered acquisition.
    Every walk records what it could not read itself, so the choice and the files read UNKNOWN
    rather than a smaller rotation."""
    with registry.acquire("rotation", "the rotating slices and their files",
                          "the rotation (the slice chosen and its files)") as acquisition:
        errors, when = [], "the rotation listing"
        rules = []
        for name in STANDING_RULES:
            rules += walk_files(os.path.join(vault, name), errors, required="file", when=when)
        slices = [("standing-rules", rules, "")]
        for name in skill_dirs(vault, errors, expect):
            slices.append(("skill:" + name, walk_files(os.path.join(vault, SKILLS_REL, name),
                                                       errors, required="folder", when=when), ""))
        register = os.path.join(vault, REGISTER_REL)
        listed = walk_files(register, errors, required=expect.of(register), when=when,
                            folder=False)
        slices.append(("register", listed, "" if listed else "the register is missing"))
        vault_hooks, watch = os.path.join(vault, VAULT_HOOKS_REL), os.path.join(tools, WATCH_DIR)
        hook_files = (walk_files(vault_hooks, errors, required=expect.of(vault_hooks), when=when,
                                 folder=True)
                      + walk_files(hooks, errors, required="folder", when=when)
                      + walk_files(watch, errors, required=expect.of(watch), when=when,
                                   folder=True))
        slices.append(("hooks-and-monitors", hook_files, ""))
        skipped = {}
        tool_files = [p for p in walk_files(tools, errors, skipped, required="folder", when=when)
                      if not state_filter.excludes(p)
                      and os.path.relpath(p, tools).split(os.sep)[0] != WATCH_DIR]
        vendored = skipped.get("node_modules", 0)
        slices.append(("tools", tool_files,
                       "%d vendored node_modules folder(s) left out" % vendored if vendored else ""))
        for path, reason, folder in errors:
            acquisition.fail(path, reason, key_for(path, vault, tools, hooks, folder) or path)
        acquisition.done()
    return slices


def pick(slices, audits, changed_paths):
    """The least recently attempted slice, never-attempted first. Every recorded audit counts,
    complete or not, so repeated omissions cannot pin the rotation to one part; what an
    incomplete audit left unread stays owed instead. Ties by changed files, then by findings at
    the last attempt, then rotation order. Returns (index, ranking, last attempts)."""
    last = {}
    for audit in audits:
        name = audit["slice"]
        if name not in last or audit["date"] >= last[name]["date"]:
            last[name] = audit
    changed_real = set(os.path.realpath(p) for p in changed_paths)
    ranking = []
    for index, (name, files, _) in enumerate(slices):
        audit = last.get(name)
        changes = sum(1 for p in files if os.path.realpath(p) in changed_real)
        findings = audit["findings"] if audit else 0
        ranking.append(((1 if audit else 0, audit["date"] if audit else "", -changes, -findings,
                         index), name, audit, changes))
    ranking.sort()
    return ranking[0][0][4], ranking, last


# ------------------------------------------------------------------ the lifecycle page -------

def split_cells(line):
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|") and not inner.endswith("\\|"):
        inner = inner[:-1]
    return [cell.replace("\\|", "|").strip() for cell in re.split(r"(?<!\\)\|", inner)]


def whole_row(text):
    """Whether a table line is whole: it opens and closes with an unescaped pipe."""
    return len(text) > 1 and text.startswith("|") and text.endswith("|") \
        and not text.endswith("\\|")


def separator_cells(text):
    """The number of cells of a table's separator row, or 0 for a line that is not one."""
    compact = text.replace(" ", "")
    return compact.count("|") - 1 if SEPARATOR_RE.match(compact) else 0


def lifecycle_header_like(head):
    """Whether a table's header row, not exactly HEADER, reads as a lifecycle header damaged: ten
    cells, or a `Next review` cell (another table on the page has neither)."""
    cells = split_cells(head)
    return len(cells) == len(COLUMNS) or any(cell.casefold() == "next review" for cell in cells)


def parse_lifecycle(lines):
    """(rows, tables, damage): the rows of every lifecycle table, each carrying `line`; the number
    of lifecycle tables; and what damages them, as (line, what).

    THE LIFECYCLE PROTOCOL (raw lines, D18). Every raw line of the page is read, whatever it stands
    in (a code block or an HTML comment hides nothing, since none is interpreted).
    - A table line is a line whose first character other than a space or a tab is a pipe; a table
      block is a run of consecutive table lines. A record is a row: a table line of a lifecycle
      table's body.
    - Whole: a lifecycle table is a block whose first line is exactly HEADER, whose second is its
      separator row of ten cells, and whose body is whole rows, each opening and closing with an
      unescaped pipe. A header and separator with no row is a valid empty table; a whole row with
      the wrong number of cells is a malformed row, listed by assess, never damage.
    - Torn, the damage that leaves the page UNKNOWN, no row of it used: a lifecycle header alone,
      a header whose next line is not that separator, a torn row (one that does not close with an
      unescaped pipe), table rows in no table (a block whose second line is no separator: rows cut
      off from their table, say), a damaged lifecycle header (a block with a separator whose
      header has ten cells or a `Next review` cell, yet is not exactly HEADER: a lifecycle table
      with a damaged header would otherwise vanish as another table), and a table line inside a
      block quote (`>` marks, then a pipe), which no lifecycle table is.
    - Examples: a line that starts with a pipe is a table line wherever it stands, so a row quoted
      as an example on the page, in a code block or not, is read as a row of its table, or, alone,
      as rows in no table (damage); an example row is written inside a sentence instead.
    WHOLE: these are the rules the page's structure decides. Nothing after the last table is
    required (a heading there was a heuristic that missed a table lost under a later heading and
    refused a page ending on its table): rows or tables a cut took from a page left structurally
    valid are THE LIMIT (the docstring)."""
    rows, tables, damage = [], 0, []
    index = 0
    while index < len(lines):
        number, line = index + 1, lines[index]
        index += 1
        if QUOTED_TABLE_RE.match(line):
            damage.append((number, "a table line inside a block quote, which no lifecycle table "
                           "is: %r" % line.strip()[:60]))
            continue
        if not line.lstrip(" \t").startswith("|"):   # a table line: a pipe after spaces or tabs
            continue
        block = [(number, line.strip())]
        while index < len(lines) and lines[index].lstrip(" \t").startswith("|"):
            block.append((index + 1, lines[index].strip()))
            index += 1
        head, second = block[0][1], block[1] if len(block) > 1 else None
        if head == HEADER:
            tables += 1
            if second is None:
                damage.append((number, "a lifecycle header alone, with no separator row after it"))
                continue
            if separator_cells(second[1]) != len(COLUMNS):
                damage.append((second[0], "the line after a lifecycle header is not its separator "
                               "row of %d cells: %r" % (len(COLUMNS), second[1][:60])))
                continue
            for row_number, text in block[2:]:
                if not whole_row(text):
                    damage.append((row_number, "a torn row, which does not close with an "
                                   "unescaped pipe: %r" % text[-60:]))
                    continue
                cells = split_cells(text)
                row = {"line": row_number, "cells": len(cells), "raw": text}
                for column, cell in zip(COLUMNS, cells):
                    row[column] = cell
                rows.append(row)
        elif second is None or not separator_cells(second[1]):
            damage.append((number, "table rows in no table, with no header and separator above "
                           "them: %r" % head[:60]))
        elif lifecycle_header_like(head):
            damage.append((number, "a damaged lifecycle header, not exactly the header the page's "
                           "tables carry: %r" % head[:60]))
    return rows, tables, damage


def read_lifecycle(registry, path):
    """(rows, problem), one registered acquisition: problem is None, or why no row could be read
    (missing or unreadable, undecodable bytes included: failed; no table, or a damaged one:
    unknown, and no row of it is used)."""
    with registry.acquire("lifecycle rows", "the rows of the lifecycle page %s" % path,
                          "the due rows and the missing rows") as acquisition:
        rows, problem = [], None
        try:   # missing only when the open itself says so, never from a look that erred
            lines = text_lines(read_text(path))
        except (FileNotFoundError, NotADirectoryError):
            problem = "missing"
            acquisition.fail(path, problem)
        except OSError as err:
            problem = "unreadable (%s)" % (err.strerror or err)
            acquisition.fail(path, problem)
        except UnicodeDecodeError as err:
            problem = "unreadable (%s)" % undecodable(err)
            acquisition.fail(path, problem)
        else:
            rows, tables, damage = parse_lifecycle(lines)
            if damage:
                rows = []
                problem = "holding a damaged table (%s%s)" % (
                    "; ".join("line %d: %s" % d for d in damage[:3]),
                    "; and %d more" % (len(damage) - 3) if len(damage) > 3 else "")
                acquisition.unknown("the lifecycle page %s is %s" % (path, problem))
            elif tables == 0:
                problem = "without a table whose header row is exactly %s" % HEADER
                acquisition.unknown("the lifecycle page %s is %s" % (path, problem))
        acquisition.done()
    return rows, problem


def empty(cell):
    return cell is None or cell.strip() in EMPTY_CELLS


def assess(row, today):
    """(due, malformed): due is None or (order, sort date, text); malformed a list of reasons."""
    malformed = []
    if row.get("cells") != len(COLUMNS):
        malformed.append("%d cells, %d expected" % (row.get("cells", 0), len(COLUMNS)))
    if empty(row.get("item")):
        malformed.append("no Item")
    kind = (row.get("kind") or "").strip().lower()
    if kind not in KINDS:
        malformed.append("Kind %r is not one of %s" % (row.get("kind") or "", ", ".join(KINDS)))
    state = " ".join((row.get("state") or "").lower().split())
    if state not in STATES:
        malformed.append("State %r is not one of %s" % (row.get("state") or "", ", ".join(STATES)))
    date = None
    if empty(row.get("next_review")):
        if state != "retired":   # a retired row is never due, so it needs no Next review
            malformed.append("no Next review")
    else:
        date = valid_date(row["next_review"].strip())
        if date is None:
            malformed.append("Next review %r is not a YYYY-MM-DD date" % row["next_review"])
    if empty(row.get("retire_when")):
        malformed.append("no Retire when")
    if state == "retired":
        return None, malformed
    due = None
    if date is not None and date < today:
        due = (0, date.isoformat(), "overdue by %d d (next review %s)"
               % ((today - date).days, date.isoformat()))
    elif date is not None and date == today:
        due = (1, date.isoformat(), "due today (next review %s)" % date.isoformat())
    elif state in DUE_STATES:
        due = (2, "", "state %s" % state)
    if due is not None and state in DUE_STATES and due[0] < 2:
        due = (due[0], due[1], due[2] + "; state " + state)
    return due, malformed


# ------------------------------------------------------------------ items and inventory ------

def norm_space(text):
    return " ".join(text.replace("`", "").split())


def group_key(file_name, rest):
    rest = rest.strip().strip("\"'“”‘’").strip()
    number = SECTION_NUMBER_RE.match(rest)
    if file_name.lower() == "claude.md" and number:
        return ("group", "claude.md", number.group(1))
    return ("group", file_name.lower(), rest.casefold())


NAMED_KEYS = dict((name.casefold(), name) for name in NAMED_GROUPS)


def item_path(raw, vault):
    """The path a lifecycle row's Item names (`raw`, read by norm_space), as the row spells it:
    under the vault as the pick was given it when the Item is relative, else its own absolute
    spelling (`~` expanded); abspath, never realpath (CR-AUDIT12 F3). row_files then spells each
    file it lists under the root that holds it (spelled)."""
    path = os.path.expanduser(raw)
    return os.path.abspath(path if os.path.isabs(path) else os.path.join(vault, path))


def spelled(path, vault, tools, hooks):
    """`path` spelled under the hashed root that holds it, as the pick was given that root: by its
    hash key, which key_for finds whatever spelling the path came in (the root's real path, or
    another link to it), turned back into a path (key_path); a path no hashed root holds stays as
    it is. So the reading list keeps the caller's spelling throughout (CR-AUDIT12 F3)."""
    key = key_for(path, vault, tools, hooks)
    return key_path(key, vault, tools, hooks) if key else path


def item_key(item, vault):
    """The key a lifecycle row's Item registers: a named group, a group (file, section) or a real
    path (the row's identity, compared with the inventory's; the files a due row lists keep the
    caller's spelling instead: item_path and spelled)."""
    raw = norm_space(item)
    if raw.casefold() in NAMED_KEYS:
        return ("named", raw.casefold())
    match = GROUP_RE.match(raw)
    if match:
        return group_key(match.group(1), match.group(2))
    path = os.path.expanduser(raw)
    if not os.path.isabs(path):
        path = os.path.join(vault, path)
    return ("path", os.path.realpath(path))


# ------------------------------------------------------------------ the section adapter ------

# The token types whose lines markdown-it reads as something other than a section, named in an
# undecidable line's reason (the innermost one holding it).
HOLDERS = (("fence", "a fenced block left open"), ("html_block", "an HTML block (a comment, say)"),
           ("code_block", "an indented code block"), ("blockquote_open", "a block quote"),
           ("list_item_open", "a list item"), ("paragraph_open", "a paragraph"))


def standing_sections(text):
    """(sections, None, None), or (None, why, kind): THE SECTION ADAPTER (D18), the one code in the
    audit that imports markdown-it-py (MARKDOWN_IT_VERSION), lazily, here. `sections` is
    [(line, heading text)] of the text's top-level sections; `kind` is `parser` when markdown-it-py
    is missing, cannot be imported or is another version (the inventory is then unknown: no other
    reader stands in for it), `syntax` when the text holds what the declared syntax does not
    support or cannot decide, or none of it is a section (the file then fails the inventory).

    The declared supported syntax:
    - the text, as read whole (strict UTF-8), its lines split at newlines only; a carriage return
      that ends no line is unsupported (markdown-it would end a line there);
    - a front matter block at the file's start (its first line exactly `---`, up to the next line
      exactly `---`) is not Markdown: its lines are read as blank; a first line `---` that no
      such line closes is unsupported;
    - the rest is parsed by markdown-it-py with its CommonMark preset;
    - a section is an ATX level-2 heading (`##`, up to three spaces in) at the top level, in no
      list item or block quote: its location is its line, its text the heading's inline content;
    - every raw line that looks like one (SECTION_LOOK_RE) is accounted for: a section's own line,
      or a line inside a fenced block markdown-it closed with its closing marker (an example);
      a line markdown-it reads anywhere else (the front matter, an HTML comment or other HTML block,
      a fenced block left open, which runs to the end of the text or of its container, a list item,
      a block quote) is undecidable: whether it is a section the audit should enrol cannot be told,
      so the list is refused, never returned without it (CR-AUDIT-B finding 1);
    - any other level-2 heading (a setext one, or an ATX one inside a list item or block quote) is
      unsupported, and so refused.
    A file ending on a heading with nothing under it is valid, and sections a cut took from a file
    left valid are THE LIMIT (the docstring); a section a cut left hidden (in a fence or comment the
    cut left open) is undecidable, never the limit."""
    try:
        import markdown_it   # the adapter's own import: no other code here imports the package
    except Exception as err:   # missing, or raising while it imports: never a fallback reader
        why = ("markdown-it-py could not be imported (%s: %s), so the sections cannot be read; no "
               "other reader stands in for it" % (type(err).__name__, err))
        return None, why, "parser"
    version = getattr(markdown_it, "__version__", None)
    if version != MARKDOWN_IT_VERSION:
        why = ("markdown-it-py is version %s, not %s, the version the adapter's acceptance was "
               "established against, so the sections cannot be read"
               % (version, MARKDOWN_IT_VERSION))
        return None, why, "parser"
    if "\r" in text.replace("\r\n", ""):
        why = ("it holds a carriage return that ends no line, which the adapter does not support "
               "(markdown-it would end a line there)")
        return None, why, "syntax"
    lines = text_lines(text)
    blank = 0
    if lines and lines[0].rstrip("\r") == FRONT_MATTER:
        close = next((index for index in range(1, len(lines))
                      if lines[index].rstrip("\r") == FRONT_MATTER), None)
        if close is None:
            why = ("its front matter, opened at line 1, never closes, which the adapter does not "
                   "support")
            return None, why, "syntax"
        blank = close + 1
        looks = [n for n in range(1, blank + 1) if SECTION_LOOK_RE.match(lines[n - 1])]
        if looks:
            why = ("its line %d, %r, looks like a section but stands in its front matter (lines 1 "
                   "to %d), so whether it is a section cannot be decided"
                   % (looks[0], lines[looks[0] - 1].strip()[:60], blank))
            return None, why, "syntax"
    source = "\n".join([""] * blank + lines[blank:]) + "\n"
    tokens = markdown_it.MarkdownIt("commonmark").parse(source)
    sections, owned, examples = [], set(), set()
    for index, token in enumerate(tokens):
        if token.type == "heading_open" and token.tag == "h2":
            line = token.map[0] + 1
            if token.markup != "##" or token.level != 0:
                why = ("its line %d holds a level-2 heading markdown-it reads %s, which the adapter "
                       "does not support" % (line, "as a setext heading" if token.markup != "##"
                                             else "inside a list item or block quote"))
                return None, why, "syntax"
            sections.append((line, tokens[index + 1].content.strip()))
            owned.add(line)
        elif token.type == "fence":
            start, end = token.map
            if end - start == token.content.count("\n") + 2:   # closed by its closing marker
                examples.update(range(start + 2, end))   # its lines between the two markers
    for number, line in enumerate(lines, 1):
        if number <= blank or not SECTION_LOOK_RE.match(line) or number in owned \
                or number in examples:
            continue
        holder = "nothing markdown-it reports"
        for token in tokens:   # the innermost block holding the line names what hid it
            if token.map and token.map[0] < number <= token.map[1]:
                holder = dict(HOLDERS).get(token.type, holder)
        why = ("its line %d, %r, looks like a section but markdown-it reads it inside %s, so "
               "whether it is a section cannot be decided" % (number, line.strip()[:60], holder))
        return None, why, "syntax"
    if not sections:
        return None, "no top-level section was found in it, so its groups came out empty", "syntax"
    return sections, None, None


def top_sections(path):
    """(sections, None, None), or (None, why, kind) when the sections cannot be read whole, decided
    or found (standing_sections, THE SECTION ADAPTER): a standing-rules file with no section would
    drop every one of its groups from the comparison, so an empty result is never read as a file
    with nothing to register, and neither is a file whose section list is undecidable, which could
    hide a section. `kind` is `read` when the file itself could not be read whole. WHOLE: these are
    the rules its structure decides; neither a rule against a file ending on a heading nor a count
    of the sections lifecycle rows enrol is used, since each claimed more than the structure
    shows."""
    try:
        text = read_text(path)
    except OSError as err:
        return None, "its sections could not be read (%s)" % (err.strerror or err), "read"
    except UnicodeDecodeError as err:
        return None, "its sections could not be read (%s)" % undecodable(err), "read"
    return standing_sections(text)


def display(path, vault):
    real, root = os.path.realpath(path), os.path.realpath(vault)
    if real == root or real.startswith(root + os.sep):
        return os.path.relpath(real, root).replace(os.sep, "/")
    return path


def is_script(path, errors):
    """Whether a found file is a script: a script suffix, or a regular file with an execute bit. A
    file that cannot be looked at (gone since its listing, a link to nothing, a permission) goes to
    `errors`, never read as no script, which would drop it from the inventory unseen."""
    if path.endswith(SCRIPT_SUFFIXES):
        return True
    try:
        mode = os.stat(path).st_mode
    except OSError as err:
        errors.append((path, "it could not be looked at to tell whether it is a script (%s)"
                       % (err.strerror or err), False))
        return False
    return S_ISREG(mode) and bool(mode & 0o111)


def section_groups(file_name, sections):
    """[(name, key)] of a standing-rules file's top-level sections: CLAUDE.md's by number when its
    heading has one, every other by its heading."""
    groups = []
    for _, heading in sections:
        number = HEADING_NUMBER_RE.match(heading)
        if file_name == "CLAUDE.md" and number:
            groups.append(("CLAUDE.md §" + number.group(1), ("group", "claude.md",
                                                             number.group(1))))
        else:
            groups.append(("%s §%s" % (file_name, heading), group_key(file_name, heading)))
    return groups


def inventory(registry, vault, tools, hooks, expect):
    """Every item the lifecycle register should hold a row for, as (name, key, category, file or
    None), one registered acquisition. A folder a walk cannot list, a required root gone at its
    walk, a folder the hash scan saw and the walk finds gone, a file found that cannot be looked at,
    and a standing-rules file whose sections cannot be read, decided (THE SECTION ADAPTER) or come
    out empty each fail it; markdown-it-py missing, unimportable or of another version leaves it
    unknown. WHOLE: those are the rules the inputs' structure decides; the sections a cut took from
    a standing-rules file left structurally valid are THE LIMIT (the docstring). No count of the
    sections the lifecycle rows enrol is taken: it could not show a cut inside an enrolled
    section, and a stale row made every pick incomplete."""
    with registry.acquire("inventory", "the test scripts, hooks, watch tools and standing-text "
                          "groups", "the missing rows") as acquisition:
        items, skill_files, errors, when = [], [], [], "the inventory"
        skills = os.path.join(vault, SKILLS_REL)
        for path in walk_files(skills, errors, required=expect.of(skills), when=when, folder=True):
            name = os.path.basename(path)
            if any(fnmatch.fnmatchcase(name, g) for g in TEST_GLOBS):
                items.append((display(path, vault), ("path", os.path.realpath(path)),
                              "test script", path))
            elif name == SKILL_FILE:
                skill_files.append(path)
        vault_hooks, watch = os.path.join(vault, VAULT_HOOKS_REL), os.path.join(tools, WATCH_DIR)
        for folder, required in ((vault_hooks, expect.of(vault_hooks)), (hooks, "folder")):
            for path in walk_files(folder, errors, required=required, when=when, folder=True):
                if is_script(path, errors):
                    items.append((display(path, vault), ("path", os.path.realpath(path)), "hook",
                                  path))
        for path in walk_files(watch, errors, required=expect.of(watch), when=when, folder=True):
            if is_script(path, errors):
                items.append((display(path, vault), ("path", os.path.realpath(path)),
                              "watch tool", path))
        for file_name in STANDING_RULES:
            path = os.path.join(vault, file_name)
            sections, problem, kind = top_sections(path)
            if kind == "parser":   # the reader is missing, not the file: unknown, nothing owed
                acquisition.unknown("the sections of %s: %s" % (path, problem))
                continue
            if problem is not None:
                acquisition.fail(path, problem, key_for(path, vault, tools, hooks))
                continue
            for name, key in section_groups(file_name, sections):
                items.append((name, key, "text group", path))
        for path in skill_files:
            items.append((display(path, vault), ("path", os.path.realpath(path)), "text group",
                          path))
        for name in NAMED_GROUPS:
            items.append((name, ("named", name.casefold()), "named group", None))
        for path, reason, folder in errors:
            acquisition.fail(path, reason, key_for(path, vault, tools, hooks, folder) or path)
        acquisition.done()
    unique, seen = [], set()
    for item in items:
        if item[1] not in seen:
            seen.add(item[1])
            unique.append(item)
    return unique


def row_files(row, vault, tools, hooks, errors):
    """The files a lifecycle row names, and a note when it names none on disk, each spelled under
    the root that holds it as the pick was given that root (item_path, then spelled; CR-AUDIT12
    F3: they were listed by their real path, so where a root's path passes through a link a file
    the reviewer named under `## Not read` was owed as an outside path, which keeps no hash, and its
    unread content entered the baseline). A path that cannot be looked at goes to `errors` and
    fails the acquisition, never reading as not found."""
    key = item_key(row.get("item") or "", vault)
    if key[0] == "named":
        return [], "a group name: no file of its own, the brief names its files"
    if key[0] == "group":
        target = os.path.join(vault, "CLAUDE.md" if key[1] == "claude.md" else "CUSTOMISATION.md")
        kind = kind_of(target, errors)
        if kind == "error":
            return [], "%s could not be looked at (INCOMPLETE below)" % target
        return ([target], "") if kind == "file" else ([], "%s not found" % target)
    path = item_path(norm_space(row.get("item") or ""), vault)
    kind = kind_of(path, errors)
    if kind == "folder":
        return [spelled(found, vault, tools, hooks)
                for found in walk_files(path, errors, required="folder",
                                        when="the due rows' files")], ""
    if kind == "file":
        return [spelled(path, vault, tools, hooks)], ""
    if kind == "error":
        return [], "it could not be looked at (INCOMPLETE below): %s" % path
    name = norm_space(row.get("item") or "")
    if "/" not in name and not os.path.splitext(name)[1]:
        return [], "a group name: no file resolved, the brief names its files"
    return [], "not found on disk: %s" % path


# ------------------------------------------------------------------ comparison sources -------

def register_problem(lines):
    """(note, why) when the register's lines cannot serve as a comparison source, else None.

    THE REGISTER PROTOCOL (raw lines, D18). The records are its two section headings, read from
    every raw line: a line `## Open` or `## Closed` (REGISTER_HEADING_RE: `##`, a space, the word,
    spaces forgiven between and after), the shape the second pass reads.
    - Whole: exactly one `## Open` line and exactly one `## Closed` line, the Open before the
      Closed.
    - Torn (UNKNOWN): either missing, either given twice, or the Closed before the Open.
    - Examples: a line in that form is the section's heading wherever it stands (a code block and
      an HTML comment included, since neither is interpreted), so an example that quotes either
      heading at the start of a line makes the register UNKNOWN, while one quoted otherwise (inside
      a sentence, after a `>` mark, or as the entry template's `###` entries) is text.
    What a cut took from a register left whole (the end of a section, a later section) is THE LIMIT
    (the docstring): no heading is required after them, a rule that refused a register ending on its
    `## Closed` section without showing that section whole."""
    found = [(number, match.group(1)) for number, match in
             ((n, REGISTER_HEADING_RE.match(line)) for n, line in enumerate(lines, 1)) if match]
    where = dict((name, [n for n, h in found if h == name]) for name in ("Open", "Closed"))
    lacking = [name for name in ("Open", "Closed") if not where[name]]
    if lacking:
        return ("UNKNOWN: no %s section" % " or ".join("`## %s`" % h for h in lacking),
                "it holds no %s section" % " or ".join("`## %s`" % h for h in lacking))
    twice = [name for name in ("Open", "Closed") if len(where[name]) > 1]
    if twice:
        return ("UNKNOWN: `## %s` given more than once" % twice[0],
                "it holds %d lines `## %s` (lines %s), each read as the section's heading wherever "
                "it stands, so its sections cannot be told apart" % (
                    len(where[twice[0]]), twice[0], ", ".join(str(n) for n in where[twice[0]][:6])))
    if where["Closed"][0] < where["Open"][0]:
        return ("UNKNOWN: `## Closed` before `## Open`",
                "its `## Closed` heading, line %d, comes before its `## Open` heading, line %d"
                % (where["Closed"][0], where["Open"][0]))
    return None


def read_register(registry, vault):
    """The register as a comparison source, one registered acquisition: read whole (strict text),
    holding its `## Open` and `## Closed` sections (register_problem). Returns the note its source
    line carries."""
    path = os.path.join(vault, REGISTER_REL)
    with registry.acquire(COMPARISON[0], "the register %s, read whole" % path,
                          "the labels (LABELS LIMITED)") as acquisition:
        note = ""
        try:   # missing only when the open itself says so
            lines = text_lines(read_text(path))
        except (FileNotFoundError, NotADirectoryError):
            note = "MISSING"
            acquisition.fail(path, "missing")
        except OSError as err:
            note = "UNREADABLE"
            acquisition.fail(path, "unreadable (%s)" % (err.strerror or err))
        except UnicodeDecodeError as err:
            note = "UNREADABLE"
            acquisition.fail(path, "unreadable (%s)" % undecodable(err))
        else:
            problem = register_problem(lines)
            if problem is not None:
                note = problem[0]
                acquisition.unknown("the register %s: %s" % (path, problem[1]))
        acquisition.done()
    return note


def field_problem(body, pattern, name):
    """Why a deep-lint entry's body lacks its complete `- **<name>**:` field with a value, or None.
    A line that only resembles the field (a torn prefix, a name with more after it, nothing after
    the colon) is named, so that the head can mend it."""
    if any(pattern.match(line) for _, line in body):
        return None
    near = next(((number, line) for number, line in body if line.startswith("- **" + name)), None)
    if near is None:
        return "no `- **%s**:` field" % name
    return ("no complete `- **%s**:` field followed by a value: its line %d reads %r"
            % (name, near[0], near[1][:60]))


def deeplint_entry(lines):
    """(start, end, date, problem) of the latest deep-lint entry in the log's lines: its heading's
    line and its last line, its date (None when its heading is malformed), and None, or why it is
    not whole; start None when the log holds no deep-lint heading in any form.

    THE DEEP-LINT PROTOCOL (raw lines, D18). The record is an entry: a heading line and the lines
    after it, up to the next line whose first character after its container prefix (spaces, tabs,
    `>` marks, list markers) is `#` (ENTRY_END_RE: an entry heading in any form, a malformed one or
    one behind a list marker included), or the log's end. Every raw line is read (a code block or
    an HTML comment hides nothing).
    - The latest deep-lint heading is the last line of the log naming a deep-lint heading in any
      form (DEEPLINT_NEAR_RE, CR-AUDIT11 F1: after the container prefix, a run of `#`, then the
      kind deep-lint however written, standing before the heading's first `|`, or as its first
      word whatever non-letters precede it: so a date field damaged in any way, a bracket left
      open, a stray `|` before the kind, no date at all or a list marker before the heading leaves
      it the latest heading). It must be in the entry's exact form,
      `## [YYYY-MM-DD] deep-lint | <title>` (DEEPLINT_RE): a malformed latest heading fails the
      acquisition, and no older entry is ever read in its place.
    - Whole: an entry is framed by its fields: it counts only with, before the next line that
      begins with `#` after its container prefix, its complete `- **Changed**:` and
      `- **Conflicts**:` fields at the start of a line, each followed by a value on its line (the
      log's entry template, CLAUDE.md section 5). Since the entry ends at any such line, a field
      is never borrowed from what follows a malformed heading or one behind a list marker.
    - Torn (the acquisition fails): a malformed latest heading; a heading alone, or over a
      fragment; a field torn (`- **Conflicts`), misnamed (`- **Conflicts-not-the-field**:`) or
      empty, which is no field.
    - Examples: a line in an exact form counts wherever it stands, so a deep-lint heading quoted in
      its exact form is an entry, and one quoted in another form is a malformed heading if it is the
      log's last; a field quoted in its complete form inside the entry is the field. A heading of
      another kind whose title names deep-lint (after its `|`) is no deep-lint heading, as the live
      log's framework entries about deep-lint are not.
    Where the two fields stand, and what follows them (a Meter or Run field, which the live log
    carries after Conflicts too), is not part of the frame, and the log around the entry is unframed
    Markdown: a cut that leaves it structurally valid (a later entry lost, or fields after the two)
    is THE LIMIT (the docstring), and so is a latest heading damaged until its kind no longer names
    deep-lint before its title (a heading cut inside its kind, say): no line then names it, and the
    backstop is step 7's label check against the register. No closing field is required of the
    entry or of the log's last entry: each claimed more than the structure shows, and the first
    refused a live entry shape."""
    heads = [number for number, line in enumerate(lines, 1) if DEEPLINT_NEAR_RE.match(line)]
    if not heads:
        return None, None, None, None
    start = heads[-1]
    exact = DEEPLINT_RE.match(lines[start - 1])
    if exact is None:
        return start, start, None, ("its latest deep-lint heading, line %d, reads %r, not the "
                                    "entry's form `## [YYYY-MM-DD] deep-lint | <title>`, and no "
                                    "older entry is read in its place"
                                    % (start, lines[start - 1].strip()[:70]))
    date = exact.group(1)
    following = next((number for number in range(start + 1, len(lines) + 1)
                      if ENTRY_END_RE.match(lines[number - 1])), len(lines) + 1)
    body = [(number, lines[number - 1]) for number in range(start + 1, following)
            if lines[number - 1].strip()]
    if not body:
        return start, start, date, "its heading stands alone, with no result below it"
    lacking = [problem for problem in (field_problem(body, CHANGED_RE, "Changed"),
                                       field_problem(body, CONFLICTS_RE, "Conflicts"))
               if problem is not None]
    return start, body[-1][0], date, "; ".join(lacking) or None


def latest_deeplint(registry, vault):
    """Deep-lint's latest entry in wiki/log.md as a comparison source, one registered acquisition.
    The log is decoded strictly: undecodable bytes anywhere in it fail the acquisition, never
    replaced, since a heading that survives over damaged text would pass; the latest deep-lint
    heading in any form must be in its exact form, and its entry must hold its frame
    (deeplint_entry: its two complete fields, each with a value), or the acquisition fails: the
    latest deep-lint heading over no complete result is never read as one, and no older entry is
    read in its place. Returns the text its source line carries."""
    path = os.path.join(vault, LOG_REL)
    with registry.acquire(COMPARISON[1], "deep-lint's latest entry in %s" % path,
                          "the labels (LABELS LIMITED)") as acquisition:
        text = None
        try:   # missing only when the open itself says so
            lines = text_lines(read_text(path))
        except (FileNotFoundError, NotADirectoryError):
            text = "%s is MISSING" % path
            acquisition.fail(path, "missing")
        except OSError as err:
            text = "%s is UNREADABLE (%s)" % (path, err.strerror or err)
            acquisition.fail(path, "unreadable (%s)" % (err.strerror or err))
        except UnicodeDecodeError as err:
            text = "%s is UNREADABLE (%s)" % (path, undecodable(err))
            acquisition.fail(path, "unreadable (%s)" % undecodable(err))
        else:
            start, end, date, problem = deeplint_entry(lines)
            when = date or "a date its malformed heading does not give"
            if start is None:
                text = "UNKNOWN: no deep-lint entry found in %s" % path
                acquisition.unknown("no deep-lint entry found in %s" % path)
            elif problem is not None:
                text = ("UNKNOWN: the latest deep-lint entry in %s (lines %d-%d, of %s) is not whole: "
                        "%s" % (path, start, end, when, problem))
                acquisition.fail(path, "the latest deep-lint entry (lines %d-%d, of %s) is not "
                                       "whole: %s" % (start, end, when, problem))
            else:
                text = "%s lines %d-%d (the deep-lint entry of %s)" % (path, start, end, date)
        acquisition.done()
    return text


# ------------------------------------------------------------------ controls -----------------

def run_controls(current, inventory_items, today):
    """In-memory plants on this run's own data and on planted cases: each must be caught, or the
    probe has failed. Reads no file."""
    results = []
    # CLAUDE.md is the anchor; when it is unread (INCOMPLETE says so) any hashed file stands in
    anchor = "vault/CLAUDE.md" if "vault/CLAUDE.md" in current else next(iter(sorted(current)),
                                                                          None)
    if anchor is None:
        probe_failed("no file was hashed at all, so no changed-file count can be trusted")
    planted = dict(current)
    planted[anchor] = ("1" if current[anchor][0] == "0" else "0") * 64
    if compare(planted, current)[0] != [anchor]:
        probe_failed("a planted hash change to %s was not caught" % anchor)
    if any(compare(current, current)):
        probe_failed("an identical baseline reported changes")
    results.append("changed plant caught, identical baseline clean")
    two = [("a", [], ""), ("b", [], "")]
    attempted = {"slice": "a", "date": "2026-01-02", "findings": 0, "complete": False}
    older = {"slice": "b", "date": "2026-01-01", "findings": 0, "complete": True}
    if pick(two, [attempted], [])[0] != 1 or pick(two, [attempted, older], [])[0] != 1 \
            or pick(two, [dict(attempted, date="2026-01-01"),
                          dict(older, date="2026-01-02")], [])[0] != 0:
        probe_failed("the rotation did not rank planted slices by their last attempt, complete or "
                     "not")
    errors = []
    gone = os.path.join(os.sep, "slice-control-nowhere", "root")
    if walk_files(gone, errors, required="folder") != [] or len(errors) != 1 \
            or walk_files(gone, [], required=None) != []:
        probe_failed("a planted missing required root was not recorded by its walk")
    results.append("rotation plants caught (an incomplete attempt moves the rotation on; a "
                   "required root gone at its walk is recorded by the walk)")
    registry = Registry()
    for name, report in (("a", "ok"), ("b", "fail"), ("c", "unknown"), ("d", None)):
        entry = registry.acquire(name, "a plant", "nothing")
        if report == "fail":
            entry.fail("/x", "planted")
        elif report == "unknown":
            entry.unknown("planted")
        if report is not None:
            entry.done()
    whole = Registry()
    whole.acquire("a", "a plant", "nothing").done()
    if registry.complete() or [e.outcome() for e in registry.entries] != [
            OK, FAILED, UNKNOWN, UNREPORTED] or not whole.complete() or Registry().complete():
        probe_failed("the registry counted a planted failed, unknown or unreported acquisition as "
                     "complete, or a whole one as incomplete")
    results.append("registry plants caught (failed, unknown and never-reported acquisitions "
                   "leave it incomplete)")
    reading = ["/v/a.md", "/v/b.md", "/v/c\x1bd.md", "/v/a.md ", "/v/required.md", "/v/source.md"]
    end = "END NOT READ: %d\n"
    owes = "## Not read\n/v/a.md\n" + end % 1
    clean = "## Not read\nnone\n" + end % 0
    coverage = (("x\n## Not read\nnone\n" + end % 0, []),
                # D18: the declaration is counted on raw lines wherever it stands, so a second one
                # in a code block, a list fence (CR-AUDIT10 F1), between fence markers in comments
                # (CR-AUDIT10 F2), in a block quote or in a comment is seen and refuses; a lone
                # declaration after a fence left open is read; a requirement file or a second-pass
                # source may be named; a second closing line anywhere refuses
                ("```\n" + owes + "```\n" + clean, None),
                ("- ```\n  ```\n\n" + owes + "\n- ```\n  ```\n\n" + clean, None),
                ("<!--\n```\n-->\n\n" + owes + "\n<!--\n```\n-->\n\n" + clean, None),
                ("> ## Not read\n> /v/a.md\n\n" + clean, None),
                ("<!--\n## Not read\n/v/a.md\n-->\n" + clean, None),
                ("```text\nan example\n" + clean, []),
                ("## Not read\n/v/required.md\n/v/source.md\n" + end % 2,
                 ["/v/required.md", "/v/source.md"]),
                (end % 0 + clean, None), ("## Not read\nnone\n- " + end % 0 + end % 0, None),
                # path lines keep their exact characters; control syntax forgives its whitespace
                ("## Not read\n/v/a.md \n" + end % 1, ["/v/a.md "]),
                ("## Not read\n/v/a.md\n" + end % 1, ["/v/a.md"]),
                ("## Not read\n /v/a.md\n" + end % 1, None), ("## Not read\n/v/b.md \n" + end % 1,
                                                              None),
                ("## Not read  \n  none \n  " + end % 0, []),
                ("## Not read\n\n/v/b.md\n" + end % 1, ["/v/b.md"]),
                ("## Not read\n/v/a.md\n/v/b.md\n" + end % 2, ["/v/a.md", "/v/b.md"]),
                ("## Not read\nescaped: /v/c\\x1bd.md\n" + end % 1, ["/v/c\x1bd.md"]),
                ("## Not read\n\n## Gaps\n", None), ("## Read\nnone\n" + end % 0, None),
                ("## Not read\nnone\n/v/a.md\n" + end % 1, None),
                ("## Not read\n/v/c.md\n" + end % 1, None),
                ("## Not read\n- /v/a.md\n" + end % 1, None),
                ("## Not read\n/v/a.md\n### more\n/v/b.md\n" + end % 2, None),
                ("```\nx\n## Not read\nnone\n" + end % 0, []),
                # the terminator: a section cut after a whole line, a wrong count, a line after it
                ("## Not read\n/v/a.md\n/v/b.md\n", None), ("## Not read\n/v/a.md\n", None),
                ("## Not read\nnone\n", None), ("## Not read\n/v/a.md\n/v/b.md\n" + end % 1, None),
                ("## Not read\nnone\n" + end % 1, None),
                ("## Not read\n/v/a.md\n" + end % 1 + "/v/b.md\n", None),
                ("## Not read\n/v/a.md\nEND NOT READ 1\n", None))
    for text, expected in coverage:
        if parse_not_read(text, reading)[0] != expected:
            probe_failed("the coverage parser misread a planted report %r" % text)
    results.append("coverage plants caught (%d, on raw lines: a section cut after a whole line, a "
                   "wrong count, and a second declaration in a code block, a list fence, between "
                   "comment fences, in a block quote and in a comment among them)" % len(coverage))
    try:
        twice = strict_json('{"a": 1, "a": 2}')
    except ValueError:
        twice = None
    try:
        constant = strict_json('{"a": NaN}')
    except ValueError:
        constant = None
    if twice is not None or constant is not None or strict_json('{"a": [1]}') != {"a": [1]} \
            or text_lines("a\x0cb c\r\nd\n") != ["a\x0cb c\r", "d"] \
            or strict_name("x\udcff.md") or not strict_name("café.md"):
        probe_failed("a planted part-read input was read as whole (a key given twice, a NaN, a "
                     "line split at a form feed, or an undecodable name)")
    if not touches("vault/d/x.md", ["vault/d/"]) or not touches("vault/d/", ["vault/d/e/"]) \
            or touches("vault/d/x.md", ["vault/e.md"]):
        probe_failed("a planted absence under an unread folder was read as a deletion, or one "
                     "beside it as none")
    results.append("whole-input plants caught (a key given twice and a NaN refused, lines split at "
                   "newlines only, an undecodable name refused, an absence under an unread folder "
                   "no deletion)")

    # absence is established, never read from an error: a planted metadata error is an error, and
    # a deletion needs its absence established
    def raises(error):
        def call(path):
            raise error
        return call
    errors = []
    if look("/x", lstat=raises(PermissionError(13, "planted")))[0] != "error" \
            or look("/x", lstat=raises(FileNotFoundError(2, "planted"))) != ("absent", None) \
            or deleted_path("/x/gone.md", "/v", "/t", "/h", [], errors, "error") is not None \
            or deleted_path("/x/gone.md", "/v", "/t", "/h", [], errors, "file") is not None \
            or deleted_path("/x/gone.md", "/v", "/t", "/h", [], errors, "absent") != "/x/gone.md":
        probe_failed("a planted metadata error was read as absence, or a deletion was taken "
                     "without its absence established")
    results.append("absence plants caught (a metadata error never absent; no deletion unless its "
                   "absence is established)")
    # the deep-lint entry, framed by its two complete fields, and the register's two sections: what
    # their structure decides fails; what it cannot decide (THE LIMIT) is never refused
    log = ["# Log", "", "## [2026-01-01] deep-lint | a", "- **Changed**: x", "- **Clock**: y",
           "- **Conflicts**: none", "", "## [2026-01-02] ingest | b", "- **Changed**: z",
           "- **Conflicts**: none"]
    head = log[:3]
    # D18, raw lines: a malformed latest deep-lint heading fails, never falling back to the older
    # entry; an entry ends at any line that begins with `#`, so a malformed heading lends it no
    # field; a fence is text, so fields after an opening are read and a fence left open is whole
    broken = (head, log[:4], log[:5], head + ["- **Clock**: y", "- **Conflicts**: none"],
              head + ["- **Changed", "- **Conflicts"],
              head + ["- **Changed-not-the-field**: x", "- **Conflicts-not-the-field**: none"],
              head + ["- **Changed**:", "- **Conflicts**:  "],
              head + ["- **Changed**: x", "- **Conflicts"],
              log + ["", "## [2026-01-03] deep-lint", "- **Changed**: w", "- **Conflicts**: none"],
              log + ["", "##[2026-01-03] deep-lint | c", "- **Changed**: w", "- **Conflicts**: none"],
              head + ["- **Clock**: y", "##[2026-01-02] ingest | b", "- **Changed**: z",
                      "- **Conflicts**: none"])
    valid = ((log, 6), (log[:6], 6), (log[:6] + ["- **Meter**: y"], 7), (log[:8], 6),
             (log[:9], 6), (head + ["```text", "- **Changed**: x", "- **Conflicts**: none"], 6),
             (log + ["```"], 6))
    # CR-AUDIT11 F1: a latest heading whose bracket is left open, or one behind a list marker, is
    # the latest, malformed; a next heading behind a list marker ends the entry, lending it no
    # field; a later heading whose title alone names deep-lint is no deep-lint heading
    later = ["- **Changed**: w", "- **Conflicts**: none"]
    broken += (log + ["", "## [2026-01-03 deep-lint | c"] + later,
               log + ["", "- ## [2026-01-03] deep-lint | c"] + later,
               head + ["- **Changed**: x", "- ## [2026-01-02] ingest | b", "- **Conflicts**: none"])
    valid += ((log + ["", "## [2026-01-03] framework | deep-lint follow-up"] + later, 6),)
    if any(deeplint_entry(lines) != (3, last, "2026-01-01", None) for lines, last in valid) \
            or any(deeplint_entry(lines)[3] is None for lines in broken):
        probe_failed("the deep-lint reader took a planted heading alone, a fragment, a field torn, "
                     "misnamed, empty or borrowed, or a malformed latest heading, as a whole entry, "
                     "or refused a structurally valid one")
    register = ["# R", "## Open", "- a", "## Closed", "- b", "## Related", "- c"]
    if any(register_problem(lines) is not None for lines in (register, register[:5],
                                                             register[:4], register + ["<!--"],
                                                             register + ["```"])) \
            or register_problem(register[:3]) is None \
            or register_problem(register + ["```text", "## Open", "```"]) is None \
            or register_problem(["# R", "## Closed", "- b", "## Open", "- a"]) is None:
        probe_failed("the register reader took a planted register without its Closed section, with "
                     "a heading given twice or with its Closed first as whole, or refused a "
                     "structurally valid one (a fence or a comment's opening at its end among them, "
                     "neither interpreted)")
    results.append("entry plants caught, on raw lines (a deep-lint heading alone, over a fragment, "
                   "with a field torn, misnamed, empty or borrowed across a malformed heading or "
                   "one behind a list marker, or a malformed latest heading, its bracket left open "
                   "or behind a list marker among them, and a register without its Closed section, "
                   "with a heading twice or its Closed first, are not whole; a field after "
                   "Conflicts, a log ending on a later entry's heading and a register ending on its "
                   "Closed section are structurally valid, the limit; a later heading whose title "
                   "alone names deep-lint is no deep-lint heading; a fence or a comment's opening "
                   "is text)")
    # printing: no character a terminal could hide is printed, and each escaped line decodes back
    texts = ("/v/a\x1bb.md", "/v/a\\x1bb.md", "escaped: x", "/v/‮x", "a\nb", "\\", "\udcff",
             "/v/plain\tname.md")
    prints = [shown_line(text) for text in texts]
    if len(set(p for p, _ in prints)) != len(texts) \
            or any(any(hides(c) for c in p) for p, _ in prints) \
            or [decode(p[len(ESCAPED_MARK):]) if e else p for p, e in prints] != list(texts) \
            or prints[1] != (texts[1], False) or prints[-1] != (texts[-1], False):
        probe_failed("the printing misread a plant: a hidden character printed, two lines printed "
                     "alike, or an escaped line did not decode back")
    results.append("printing plants caught (%d lines: hidden characters escaped and decoded back, "
                   "plain lines byte for byte)" % len(texts))
    day = datetime.timedelta(days=1)
    base = {"cells": len(COLUMNS), "item": "x", "kind": "suite", "state": "active",
            "retire_when": "x", "next_review": ""}
    checks = ((dict(base, next_review=(today - day).isoformat()), True),
              (dict(base, next_review=(today + day).isoformat()), False),
              (dict(base, next_review=(today - day).isoformat(), state="retired"), False),
              (dict(base, next_review=(today + day).isoformat(), state="quarantined"), True))
    for row, expected in checks:
        if (assess(row, today)[0] is not None) != expected:
            probe_failed("the due rule misread a planted row %r" % row)
    if assess(dict(base, next_review=""), today)[1] != ["no Next review"]:
        probe_failed("a planted row with no Next review was not called malformed")
    # a retired row needs no Next review, since it is never due; its other checks stay
    if assess(dict(base, next_review="", state="retired"), today) != (None, []) \
            or assess(dict(base, next_review="", state="retired", retire_when=""), today) \
            != (None, ["no Retire when"]):
        probe_failed("a planted retired row with no Next review was called malformed, or its other "
                     "checks were dropped with that one")
    results.append("due plants caught (4) and malformed plants caught (3: no Next review; a "
                   "retired row with none, not malformed; a retired row with no Retire when)")
    separator = "|" + "---|" * len(COLUMNS)
    after = "## Related"
    # a page ending on its table, or with text or a subsection heading after it, is structurally
    # valid: what a cut took from it there is THE LIMIT, never damage
    readable = [((HEADER, separator, "| x |", "", after), 1, 1), ((HEADER, separator, after), 1, 0),
                (("# x", "| a | b |", "|---|---|", "| 1 | 2 |"), 0, 0),
                ((HEADER, separator, "| x |"), 1, 1),
                ((HEADER, separator, "| x |", "", "more"), 1, 1),
                ((HEADER, separator, "| x |", "### b"), 1, 1),
                # raw lines (D18): a fence marker is text, so a table after one is read
                (("```", HEADER, separator, after), 1, 0)]
    # CR-AUDIT10's F1 (a list fence) and F2 (fence markers inside comments) before a torn table,
    # which a fence reader hid; a damaged lifecycle header; a row inside a block quote
    hiding = (("- ```", "  ```", ""), ("<!--", "```", "-->", ""))
    damaged = [(HEADER, after), (HEADER, "|---|", "| x |", after),
               (HEADER, separator, "| x | y", after), (HEADER, separator, "| x |", "", "| y |", after),
               (HEADER.replace("Guards", "Guard"), separator, "| x |"),
               (HEADER, separator, "| x |", "", "> | y |")]
    damaged += [(HEADER, separator, "| x |", "") + shape + (HEADER, separator, "| y", "") + shape
                for shape in hiding]
    for lines, tables, count in readable:
        found, seen, damage = parse_lifecycle(list(lines))
        if seen != tables or len(found) != count or damage:
            probe_failed("the lifecycle reader misread a planted whole page %r" % (lines,))
    for lines in damaged:
        if not parse_lifecycle(list(lines))[2]:
            probe_failed("the lifecycle reader took a planted damaged table as whole: %r"
                         % (lines,))
    results.append("table plants caught, on raw lines (a whole row, an empty table, another table, "
                   "a page ending on its table and a table after a fence marker read; a header "
                   "alone, a broken separator, a torn row, rows in no table, a damaged header, a "
                   "quoted row, and a torn table after a list fence or comment fences each "
                   "damaged)")
    if not inventory_items:
        probe_failed("the inventory found no item at all (no test script, hook, watch tool or "
                     "text group), so no missing-row count can be trusted")
    keys = [item[1] for item in inventory_items]
    if missing_items(inventory_items, set(keys[1:])) != [inventory_items[0]] \
            or missing_items(inventory_items, set(keys)):
        probe_failed("a planted missing row was not caught")
    results.append("missing-row plant caught")
    for name, expected in (("node_modules", True), ("package-lock.json", False),
                           (".DS_Store", True), ("x.py.bak-1", True), ("x.py", False)):
        caught = name in SKIP_DIRS or skip_file(name)
        if caught != expected:
            probe_failed("the skip rule misread a planted name %r" % name)
    results.append("skip plants caught (vendored and stray skipped, pin files kept)")
    stored = {"vault/a.md": "1" * 64, "vault/d/x.md": "2" * 64, "vault/gone.md": "3" * 64}
    unread = ["vault/a.md", "vault/d/", "vault/new.md"]
    if compare(stored, {}, unread)[2] != ["vault/gone.md"]:
        probe_failed("a planted unread file or folder was read as removed")
    merged, _, absent, _ = merge_baseline({"vault/b.md": "4" * 64, "vault/new.md": "5" * 64},
                                          unread, stored)
    if merged != {"vault/a.md": "1" * 64, "vault/d/x.md": "2" * 64, "vault/b.md": "4" * 64} \
            or absent != ["vault/new.md"]:
        probe_failed("a planted unread path advanced the baseline")
    results.append("unread plants caught (an unread file and folder neither removed nor advanced, "
                   "an unread new file left absent)")
    # THE SECTION ADAPTER (D18): CR-AUDIT-B finding 1's counterexample (a section between two
    # comments holding fence markers) and its list-fence counterpart give the complete list; a
    # fenced example is no section; a section hidden by a comment or a fence left open, a
    # commented one, a setext or nested level-2 heading are undecidable or unsupported (None);
    # CommonMark's fence rules are markdown-it's (a false closer, a backtick info string holding
    # a backtick); a front matter is set aside. With markdown-it-py unavailable, the plants cannot
    # run, and the inventory, which needs the same parser, already reads UNKNOWN.
    sections = (("## Existing\n<!--\n```\n-->\n## New rule\nA standing requirement.\n<!--\n```\n"
                 "-->\n", [(1, "Existing"), (5, "New rule")]),
                ("## Existing\n- ```\n  ```\n\n## New rule\nA standing requirement.\n- ```\n  ```\n",
                 [(1, "Existing"), (5, "New rule")]),
                ("# T\n## 1. A\n```\n## B\n```\n## D\n", [(2, "1. A"), (6, "D")]),
                ("## A\n```\n## B\n```not-close\n```\n## C\n", [(1, "A"), (6, "C")]),
                ("---\ntitle: x\n---\n## A\n", [(4, "A")]),
                ("## A\n<!--\n## B\n", None), ("## A\n```\n## B\n", None),
                ("## A\n<!--\n## B\n-->\n", None), ("## A\n``` not `a` fence\n```\n## B\n", None),
                ("## A\nB\n---\n", None), ("## A\n- ## B\n", None), ("text\n", None))
    if standing_sections(sections[0][0])[2] == "parser":
        results.append("section plants not run: %s; the inventory, which needs it, reads UNKNOWN"
                       % standing_sections(sections[0][0])[1])
        return results
    for text, expected in sections:
        got = standing_sections(text)
        if len(got) != 3 or got[0] != expected or (got[2] is None) != (expected is not None):
            probe_failed("the section adapter misread a planted text %r: %r, %r expected"
                         % (text, got[:2], expected))
    results.append("section plants caught, by markdown-it-py %s (%d: CR-AUDIT-B's counterexample "
                   "and its list-fence counterpart read whole; a fenced example no section; a "
                   "section hidden by a comment or a fence left open, a commented one, a setext "
                   "and a nested level-2 heading UNKNOWN)" % (MARKDOWN_IT_VERSION, len(sections)))
    return results


def missing_items(items, registered):
    return [item for item in items if item[1] not in registered]


# ------------------------------------------------------------------ the pick -----------------

def held_files(vault, slice_name):
    """The second-pass sources, which the reading list and the requirement files never hold,
    whatever lists them (a changed file, an owed entry, a due row, an inventory item or the rotating
    part): every path second_pass_sources names, the register unless it is the slice, the lifecycle
    page and wiki/log.md. Derived from that list, so the two cannot differ (CR-AUDIT11 F4: the log
    was left out here, so a due row naming it put it in pass 1, and the recorder refused the
    manifest)."""
    return [source["path"] for source in second_pass_sources(vault, slice_name)]


def second_pass_sources(vault, slice_name):
    """The second pass's mandatory inputs, as the SECOND-PASS SOURCES block lists them: the
    register unless it is the slice, the lifecycle page, and wiki/log.md for deep-lint's entry;
    each {path, comparison}, the register and the log being the comparison sources the labels rest
    on (an unread one limits the labels). The first pass never sees them: none is ever on the
    reading list or among the requirement files."""
    sources = []
    if slice_name != "register":
        sources.append({"path": os.path.join(vault, REGISTER_REL), "comparison": True})
    sources.append({"path": os.path.join(vault, LIFECYCLE_REL), "comparison": False})
    sources.append({"path": os.path.join(vault, LOG_REL), "comparison": True})
    return sources


def comparison_sources(vault, slice_name, reading):
    """The comparison sources among this audit's mandatory inputs, whatever their phase (CR-AUDIT11
    F3): the register, a second-pass source in an ordinary week and in its own week a reading-list
    file the first pass reads (spelled as the list spells it, and left out when it was not there to
    list), and wiki/log.md, for deep-lint's entry. One the reviewer did not read limits the labels
    in either phase: in its own week the register is the first pass's object, and what that pass
    read of it still serves the second pass's labels."""
    register = os.path.join(vault, REGISTER_REL)
    if slice_name != "register":
        return [register, os.path.join(vault, LOG_REL)]
    on_list = [path for path in reading if os.path.realpath(path) == os.path.realpath(register)]
    return on_list[:1] + [os.path.join(vault, LOG_REL)]


def requirement_files(registry, vault, slice_name, reading, current, unread_keys, held_real):
    """(the requirement files to list, notes), one registered acquisition (`requirement files`):
    REQUIREMENTS's for every slice and for this one, a second-pass source never among them (never
    in pass 1). It reads nothing itself: the hash scan has looked at every one, since each lies
    under a hashed vault root. Each one's role is judged first, apart from every route by which
    the same path reaches the reading list (CR-AUDIT12 F1): an owed deletion, a changed or owed
    file, a due row, an inventory item or the rotating part, a link to it among them. One hashed,
    or there but unreadable (that scan's own failure, which the INCOMPLETE block names), is there to
    read. One with no file at its path and no failure of the scan covering it is absent, its
    absence established by the scan's walk, and the acquisition returns unknown, since no reviewer
    can read it and the audit cannot be complete, whatever lists its path (CR-AUDIT11 F2: it used
    to be dropped from the list, so a report saying `none` recorded the audit complete; CR-AUDIT12
    F1: an owed deletion put its path on the reading list, which spared it the check). Then, apart,
    where it is listed: here, unless the reading list holds its path already (by its real path),
    so that it stays a mandatory input the report's `## Not read` may name, here or on the reading
    list, an absent one with a note either way. Its debt is the reading list's alone: a requirement
    file is never owed for its role, being no slice content, and a path the reading list holds
    keeps that list's rules (an owed deletion discharged unless the report names it)."""
    on_list = dict((os.path.realpath(p), p) for p in reading)   # each real path once (do_pick)
    listed, judged, notes = [], [], []
    with registry.acquire(REQUIREMENT_ACQUISITION, "the requirement files this slice serves, as "
                          "the hash scan saw them (it reads nothing itself)",
                          "the requirement files: one absent leaves the audit incomplete") \
            as acquisition:
        for name, rels in REQUIREMENTS:
            if name and name != slice_name:
                continue
            for rel in rels:
                path, key = os.path.join(vault, rel), "vault/" + rel
                real = os.path.realpath(path)
                if real in held_real or path in judged:
                    continue
                judged.append(path)
                # its role, judged before and apart from what else lists it (CR-AUDIT12 F1)
                there = key in current or covered(key, unread_keys)
                as_listed = on_list.get(real)
                if as_listed is None:
                    listed.append(path)
                if there:
                    continue
                acquisition.unknown("the requirement file %s is absent at this pick (the hash "
                                    "scan's walk found no file at its path), so no reviewer can "
                                    "read it and the audit cannot be complete" % path)
                notes.append("the requirement file %s is absent at this pick: %s, so the report's "
                             "`%s` names it, and the pick is incomplete (INCOMPLETE below)"
                             % (path, "it stays listed" if as_listed is None else "the reading "
                                "list holds it already%s, where it stays" % (
                                    "" if as_listed == path else ", as %s" % as_listed),
                                NOT_READ_HEADING))
        acquisition.done()
    return listed, notes


def do_pick(registry, vault, tools, hooks, state_path, today, manifest_out):
    out = []
    state = load_state(registry, state_path)
    baseline = state["baseline"]
    if manifest_out:
        check_manifest_out(manifest_out, vault, tools, hooks, state_path)
    state_filter = StateFilter(state_path)
    taken = now()
    current, key_paths, hash_unread, absent_roots, skipped = hash_roots(registry, vault, tools,
                                                                        hooks, state_filter)
    expect = Expect(key_paths.values())
    unread_keys = [key for key, _, _ in hash_unread]
    if baseline is not None:
        stored = baseline["hashes"]
        if stored and current and not set(stored) & set(current):
            probe_failed("no path in the stored baseline matches a current one: the roots differ "
                         "from those slices.json was recorded over")
        changed, new, removed = compare(stored, current, unread_keys)
    else:
        changed, new, removed = [], [], []
    changed_paths = [key_paths[k] for k in changed + new]

    # Content owed from earlier audits: listed until the reviewer reads it, changed or not; an
    # owed path with no file of it left, under walks that did not fail, is listed as deleted.
    owed_parts = acquire_owed(registry, state["owed"], vault, tools, hooks, state_filter, expect,
                              unread_keys)
    slices = rotation(registry, vault, tools, hooks, state_filter, expect)
    index, ranking, last = pick(slices, state["audits"], changed_paths)
    name, slice_files, slice_note = slices[index]
    held_real = set(os.path.realpath(p) for p in held_files(vault, name))
    rows, lifecycle_problem = read_lifecycle(registry, os.path.join(vault, LIFECYCLE_REL))
    rows_whole = registry.get("lifecycle rows").outcome() == OK
    if not rows_whole:
        rows = []   # an acquisition that did not succeed lends no part of its result
    items = inventory(registry, vault, tools, hooks, expect)
    due_rows, malformed_rows, due_files = [], [], []
    with registry.acquire("due rows' files", "the files each due lifecycle row names",
                          "the due rows' files") as acquisition:
        due_errors = []
        for row in rows:
            due, malformed = assess(row, today)
            files, note = (row_files(row, vault, tools, hooks, due_errors) if due is not None
                           else ([], ""))
            if due is not None:
                due_rows.append((due, row, malformed, note))
                due_files.extend(files)
            elif malformed:
                malformed_rows.append((row, malformed))
        for path, reason, folder in due_errors:
            acquisition.fail(path, reason, key_for(path, vault, tools, hooks, folder) or path)
        acquisition.done()
    due_rows.sort(key=lambda entry: (entry[0][0], entry[0][1], entry[1]["line"]))
    register_note = read_register(registry, vault)
    deeplint_text = latest_deeplint(registry, vault)
    controls = run_controls(current, items, today)

    # The reading list and the other mandatory inputs, then (the requirement files' acquisition
    # being the last to report) completeness, then the manifest.
    lifecycle_ok = registry.get("lifecycle rows").outcome() == OK
    if not lifecycle_ok:
        # the acquisition's own outcome names the problem, even when the page read whole and the
        # acquisition failed, returned unknown or never reported for another reason
        lifecycle_problem = lifecycle_problem or "%s (%s)" % (
            registry.get("lifecycle rows").outcome(), registry.get("lifecycle rows").detail())
    inventory_ok = registry.get("inventory").outcome() == OK
    registered = set(item_key(row.get("item") or "", vault) for row in rows
                     if not empty(row.get("item")))
    missing = missing_items(items, registered) if lifecycle_ok else []

    owed_paths = [path for _, files, _, _ in owed_parts for path in files]
    deleted_paths = [deleted for _, _, _, deleted in owed_parts if deleted]
    parts, seen, held_changed = [], {}, []
    for part, files in (("changed since the baseline", changed_paths),
                        ("owed from an earlier audit", owed_paths),
                        ("deleted since its baseline, owed from an earlier audit", deleted_paths),
                        ("due lifecycle rows", due_files),
                        ("unregistered inventory items", [item[3] for item in missing if item[3]]),
                        ("rotating part: " + name, slice_files)):
        kept = []
        for path in files:
            real = os.path.realpath(path)
            if real in held_real:
                if part.startswith("changed") and path not in held_changed:
                    held_changed.append(path)
                continue
            if real in seen:
                continue
            seen[real] = path
            kept.append(path)
        parts.append((part, kept))
    reading = [path for _, kept in parts for path in kept]
    total = len(reading)
    requirements, requirement_notes = requirement_files(registry, vault, name, reading, current,
                                                        unread_keys, held_real)
    sources = second_pass_sources(vault, name)
    comparison = comparison_sources(vault, name, reading)
    # Each owed entry's files, all of them, as owed_parts found them before the held sources left
    # the reading list (CR-AUDIT13 F2: an entry was given only its listed files, so a folder owed
    # from an earlier audit was discharged though the reviewer left a file of it held for the
    # second pass unread): those on the reading list, spelled as it spells them, and those held
    # for the second pass, spelled as the sources are and in their order, which the record
    # requires read too
    source_order = [source["path"] for source in sources]
    held_spelling = dict((os.path.realpath(p), p) for p in source_order)
    owed_manifest = []
    for entry, files, acquired, deleted in owed_parts:
        listed, held = [], []
        for path in files + ([deleted] if deleted else []):
            spelling = seen.get(os.path.realpath(path))
            if spelling is not None and spelling not in listed:
                listed.append(spelling)
            elif spelling is None and os.path.realpath(path) in held_real:
                held.append(held_spelling[os.path.realpath(path)])
        held = sorted(set(held), key=source_order.index)
        owed_manifest.append({"entry": entry["entry"], "files": listed, "held": held,
                              "acquired": acquired, "deleted": bool(deleted)})

    # Every acquisition has reported, or never will: completeness, then the manifest.
    short = registry.short()
    complete = registry.complete()
    labels_limited = any(registry.get(n).outcome() != OK for n in COMPARISON)
    unread = {}
    for acquisition in short:
        if acquisition.name in COMPARISON + (REQUIREMENT_ACQUISITION,):
            continue   # carried by labels_limited and the acquisitions, never owed
        for entry, path, reason in acquisition.failures:
            if entry.startswith("/"):
                entry = key_for(entry, vault, tools, hooks) or entry
            slot = unread.setdefault(entry, (path, []))
            if reason not in slot[1]:
                slot[1].append(reason)
    hash_short = [a for a in short if a.name.startswith("hash scan: ")]
    hash_failures = sum(len(a.failures) for a in hash_short)

    def part_short(part):
        """The acquisitions a reading-list part rests on that did not succeed."""
        names = {"changed since the baseline": [a.name for a in hash_short],
                 "owed from an earlier audit": ["owed content"],
                 "deleted since its baseline, owed from an earlier audit": ["owed content"],
                 "due lifecycle rows": ["lifecycle rows", "due rows' files"],
                 "unregistered inventory items": ["lifecycle rows", "inventory"]}.get(
                     part, ["rotation"] if part.startswith("rotating part: ") else [])
        return [n for n in names if registry.get(n).outcome() != OK]

    if manifest_out:
        existed = look(manifest_out, follow=False)   # an error is said, never read as none there
        write_manifest(manifest_out, {
            "version": MANIFEST_VERSION, "kind": MANIFEST_KIND, "taken": stamp(taken),
            "date": today.isoformat(), "slice": name,
            "roots": {"vault": vault, "tools": tools, "hooks": hooks}, "hashes": current,
            "complete": complete, "unread": sorted(unread), "acquisitions": registry.summary(),
            "labels_limited": labels_limited, "slices": [s[0] for s in slices],
            "reading": reading, "owed": owed_manifest, "requirements": requirements,
            "sources": sources, "comparison": comparison})
        manifest_text = ("written to %s (%d files, taken %s, after all %d acquisitions reported%s)%s"
                         % (manifest_out, len(current), stamp(taken), len(registry.entries),
                            "" if complete else "; marked INCOMPLETE: %d acquisition(s) did not "
                            "succeed" % len(short),
                            "" if existed[0] == "absent" else "; whether an earlier manifest was "
                            "at that path could not be told (%s)" % existed[1]
                            if existed[0] == "error" else "; it replaced an earlier manifest at "
                            "that path"))
    else:
        manifest_text = ("none written (no --manifest-out), so this pick cannot be recorded: "
                         "--record needs the manifest of the pick the audit read")

    audit = last.get(name)
    why = ("never attempted" if audit is None else "least recently attempted, on %s (%s, %d "
           "finding(s))" % (audit["date"], "complete" if audit["complete"] else "incomplete",
                            audit["findings"]))
    tied = sum(1 for entry in ranking[1:] if entry[0][:2] == ranking[0][0][:2])
    if tied:
        why += ("; of %d slices %s, it comes first on changed files (%d here), then findings at "
                "the last attempt, then rotation order" % (tied + 1, "never attempted"
                                                           if audit is None
                                                           else "last attempted that day",
                                                           ranking[0][3]))
    never = sum(1 for entry in ranking if entry[2] is None)
    rotation_ok = registry.get("rotation").outcome() == OK
    out.append("WEEKLY AUDIT SLICE, %s" % today.isoformat())
    out.append("slice: %s (the rotating part): %s" % (name, why))
    if not rotation_ok:
        out.append("rotation: UNKNOWN. The listing could not read every path (INCOMPLETE below), "
                   "so this choice and the rotating part's files may be wrong; mend and pick "
                   "again, or record the audit as the incomplete audit it is")
    out.append("state: %s (%s; %d owed entr%s)" % (
        state_path, "initialised %s; no audit recorded, no baseline yet" % state["initialised"]
        if baseline is None else "baseline of %s, taken %s; %d audit(s) recorded, %d incomplete"
        % (baseline["date"], baseline["taken"], len(state["audits"]),
           sum(1 for a in state["audits"] if not a["complete"])),
        len(state["owed"]), "y" if len(state["owed"]) == 1 else "ies"))
    out.append("manifest: %s" % manifest_text)
    out.append("rotation: %d slices, %d never attempted; next in line: %s"
               % (len(slices), never, ranking[1][1] if len(ranking) > 1 else "none"))
    if slice_note:
        out.append("note: %s" % slice_note)
    out.append("")
    out.append("READING LIST (%d files, one absolute path per line):" % total)
    for part, kept in parts:
        short_names = part_short(part)
        if short_names:   # never a bare count: what the part lists may be short
            out.append("-- %s (UNKNOWN: %d listed, but %s did not succeed, see INCOMPLETE below)"
                       % (part, len(kept), " and ".join(short_names[:3])
                          + (" and %d more" % (len(short_names) - 3) if len(short_names) > 3
                             else "")))
        else:
            out.append("-- %s (%d)" % (part, len(kept)))
        out.extend(kept)
    out.append("")
    out.append("REQUIREMENT FILES (%d, the governing texts this slice serves, read in the first pass "
               "beside the reading list; one on the reading list is not repeated here%s):"
               % (len(requirements), "" if registry.get(REQUIREMENT_ACQUISITION).outcome() == OK
                  else "; UNKNOWN in part: their acquisition did not succeed, so one listed may "
                  "not be there to read, see INCOMPLETE below"))
    out.extend(requirements)
    out.extend("note: %s" % note for note in requirement_notes)
    out.append("")
    changed_unknown = bool(hash_short)
    if baseline is None:
        out.append("CHANGED FILES: none listed. slices.json holds no baseline yet (no audit "
                   "recorded since --init), so the baseline is recorded at this audit "
                   "(slice.py --record with this pick's --manifest-out).")
        if changed_unknown:
            out.append("  %d path(s) could not be read (INCOMPLETE below): they stay out of the "
                       "first baseline, so the next pick lists them as new." % hash_failures)
    elif changed_unknown:
        out.append("CHANGED FILES since the baseline of %s: UNKNOWN. %d path(s) could not be read "
                   "and %d hash scan(s) did not succeed (INCOMPLETE below), so a change there "
                   "cannot be seen; among the files read, %d changed, %d new, %d removed"
                   % (baseline["date"], hash_failures, len(hash_short), len(changed), len(new),
                      len(removed)))
    else:
        out.append("CHANGED FILES since the baseline of %s: %d changed, %d new, %d removed"
                   % (baseline["date"], len(changed), len(new), len(removed)))
    if baseline is not None:
        deleted_keys = [entry["entry"] for entry, _, _, deleted in owed_parts if deleted]
        for key in removed:
            if covered(key, deleted_keys):
                out.append("removed, and owed from an earlier audit, so on the reading list as "
                           "deleted: %s" % key_path(key, vault, tools, hooks))
            else:
                out.append("removed (not in the reading list): %s"
                           % key_path(key, vault, tools, hooks))
    for path in held_changed:
        out.append("held for the second pass (changed, read whole there): %s" % path)
    out.append("")
    owed_ok = registry.get("owed content").outcome() == OK
    out.append("OWED (%d entr%s from earlier audits, on the reading list until the reviewer reads "
               "them, changed or not%s):" % (len(owed_parts), "y" if len(owed_parts) == 1
                                              else "ies", "" if owed_ok else "; UNKNOWN in part, "
                                              "see INCOMPLETE below"))
    for (entry, files, acquired, deleted), listed in zip(owed_parts, owed_manifest):
        if not acquired:
            state_text = "could not be read whole (INCOMPLETE below), so it stays owed"
        elif deleted and listed["files"]:
            state_text = ("deleted since its baseline (no file of it is there now, and no walk down "
                          "to it failed): on the reading list as deleted, and discharged at the "
                          "record unless the reviewer names it under `%s`" % NOT_READ_HEADING)
        elif listed["files"]:
            state_text = "%d file(s) on the reading list%s" % (
                len(listed["files"]), "" if not listed["held"] else ", and %d held for the second "
                "pass, which reads each whole: one named under `%s` keeps the entry owed"
                % (len(listed["held"]), NOT_READ_HEADING))
        elif files or deleted:
            state_text = ("its files are held for the second pass this week, so it stays owed "
                          "until a week whose reading list holds them")
        else:
            state_text = "nothing listed: it stays owed until its content is listed and read"
        out.append("- %s (owed since %s): %s" % (entry["entry"], entry["since"], state_text))
    out.append("")
    if not lifecycle_ok:
        out.append("DUE ROWS: UNKNOWN. The lifecycle page %s is %s; this is never read as "
                   "nothing due, and the pick is incomplete."
                   % (os.path.join(vault, LIFECYCLE_REL), lifecycle_problem))
    else:
        counts = [sum(1 for d in due_rows if d[0][0] == k) for k in (0, 1, 2)]
        due_ok = registry.get("due rows' files").outcome() == OK
        out.append("DUE ROWS (%d: %d overdue, %d due today, %d by state; overdue first%s). Each "
                   "row's first line is its requirement; its second says why it is due:"
                   % (len(due_rows), counts[0], counts[1], counts[2], "" if due_ok
                      else "; their files UNKNOWN in part, see INCOMPLETE below"))
        for due, row, malformed, note in due_rows:
            out.append("- %s | kind %s | purpose: %s | guards: %s"
                       % (norm_space(row.get("item") or ""), row.get("kind") or "",
                          row.get("purpose") or "", row.get("guards") or ""))
            extra = "".join(["; MALFORMED: " + ", ".join(malformed) if malformed else "",
                             "; " + note if note else ""])
            out.append("    due: %s (lifecycle page line %d)%s" % (due[2], row["line"], extra))
        out.append("MALFORMED ROWS not due (%d):" % len(malformed_rows))
        for row, malformed in malformed_rows:
            out.append("- %s | line %d | %s" % (norm_space(row.get("item") or "") or "(no item)",
                                               row["line"], ", ".join(malformed)))
    out.append(LIMIT_LINES["due rows"])
    out.append("")
    if not lifecycle_ok:
        out.append("MISSING ROWS: UNKNOWN. With the lifecycle page %s, the inventory of %d items "
                   "cannot be compared with its rows." % (lifecycle_problem, len(items)))
    elif not inventory_ok:
        out.append("MISSING ROWS: UNKNOWN. The inventory did not succeed (INCOMPLETE below: a path "
                   "it could not read, a section list it could not decide, or its section reader "
                   "missing), so the items there cannot be compared with the rows; among the %d "
                   "items found, %d have no lifecycle row:" % (len(items), len(missing)))
    else:
        out.append("MISSING ROWS (%d inventory items with no lifecycle row):" % len(missing))
    if lifecycle_ok:
        for item_name, _, category, _ in missing:
            out.append("- %s | %s" % (item_name, category))
    out.append(LIMIT_LINES["missing rows"])
    out.append("")
    out.append("SECOND-PASS SOURCES (never opened in the first pass; the second pass reads each "
               "whole):")
    register = os.path.join(vault, REGISTER_REL)
    lifecycle = os.path.join(vault, LIFECYCLE_REL)
    if name != "register":
        out.append("- the register: %s%s" % (register, " (%s)" % register_note if register_note
                                             else ""))
    out.append("- the lifecycle register: %s%s" % (lifecycle, "" if lifecycle_ok
                                                   else " (%s)" % lifecycle_problem.upper()))
    out.append("- deep-lint's latest report: %s" % deeplint_text)
    if name == "register":
        out.append("not a second-pass source: the register %s is this audit's slice, which the "
                   "first pass reads as a text, and still a comparison source: what that pass "
                   "reads of it serves the labels, and naming it under `%s` limits them%s"
                   % (register, NOT_READ_HEADING, " (%s)" % register_note if register_note
                      else ""))
    if labels_limited:
        out.append("LABELS LIMITED: %s did not succeed (INCOMPLETE below), so this audit is "
                   "incomplete and none of its findings can be labelled `new kind`: each such "
                   "label is a candidate the head checks (AUDIT.md, step 7)."
                   % " and ".join(n for n in COMPARISON if registry.get(n).outcome() != OK))
    out.append(LIMIT_LINES["sources"])
    out.append("")
    categories = {}
    for item in items:
        categories[item[2]] = categories.get(item[2], 0) + 1
    section_counts = ", ".join(
        "%s %d" % (n, sum(1 for item in items if item[2] == "text group"
                          and item[3] == os.path.join(vault, n))) for n in STANDING_RULES)
    skip_text = ", ".join("%s %d %s" % (k, skipped.get(k, 0),
                                        "folder(s)" if k in SKIP_DIRS else "file(s)")
                          for k in SKIP_DIRS + SKIP_FILES)
    out.append("CONTROLS: hashed %d files over %d roots (%d optional root(s) absent%s); skipped %s; "
               "%s; lifecycle rows parsed %s; inventory %d (%s); sections read: %s; acquisitions "
               "%d registered, %d ok"
               % (len(current), len(VAULT_ROOTS) + 2, len(absent_roots),
                  ": " + ", ".join(absent_roots) if absent_roots else "", skip_text,
                  "; ".join(controls), len(rows) if lifecycle_ok else "n/a (%s)"
                  % lifecycle_problem, len(items),
                  ", ".join("%s %d" % (k, categories.get(k, 0))
                            for k in ("test script", "hook", "watch tool", "text group",
                                      "named group")),
                  section_counts, len(registry.entries), len(registry.entries) - len(short)))
    if short:
        out.append("INCOMPLETE (%d of %d acquisitions did not succeed; the results that depend on "
                   "them read UNKNOWN, never empty, and the manifest says complete: false):"
                   % (len(short), len(registry.entries)))
        for acquisition in short:
            out.append("- %s: %s: %s; leaves UNKNOWN: %s"
                       % (acquisition.name, acquisition.outcome(), acquisition.detail(),
                          acquisition.affects))
    if baseline is None:
        changed_text = "changed none: baseline recorded at this audit"
    elif changed_unknown:
        changed_text = ("changed UNKNOWN (%d path(s) unread; %d changed, %d new, %d removed among "
                        "the rest)" % (hash_failures, len(changed), len(new), len(removed)))
    else:
        changed_text = ("changed %d, new %d, removed %d since %s"
                        % (len(changed), len(new), len(removed), baseline["date"]))
    if lifecycle_ok:
        rows_text = "due rows %d (overdue %d) · malformed %d · %s" % (
            len(due_rows), sum(1 for d in due_rows if d[0][0] == 0),
            sum(1 for d in due_rows if d[2]) + len(malformed_rows),
            "missing rows UNKNOWN (%d listed; the inventory read incompletely)" % len(missing)
            if not inventory_ok else "missing rows %d" % len(missing))
    else:
        rows_text = "due rows UNKNOWN · missing rows UNKNOWN (lifecycle page %s)" % lifecycle_problem
    names = [a.name for a in short]
    short_text = ("acquisitions all ok" if complete else "INCOMPLETE: %d acquisition(s) (%s%s)%s"
                  % (len(names), ", ".join(names[:3]), ", +%d more" % (len(names) - 3)
                     if len(names) > 3 else "", "; LABELS LIMITED" if labels_limited else ""))
    out.append("SUMMARY: slice %s · reading list %d files (%s) · %s · %s · %s"
               % (name, total, ", ".join("%s %s" % (p.split(":")[0].split(" ")[0],
                                                    "UNKNOWN (%d listed)" % len(k) if part_short(p)
                                                    else len(k)) for p, k in parts),
                  changed_text, rows_text, short_text))
    emit(out)
    return EXIT_OK if complete else EXIT_INCOMPLETE


# ------------------------------------------------------------------ init and record ----------

def do_init(registry, state_path):
    kind, reason = look(state_path, follow=False)
    if kind == "error":   # never read as absent: --init runs only where none is established
        raise Refusal("REFUSED: %s could not be looked at (%s), so whether a slices.json is there "
                      "cannot be told; --init runs only where none is" % (state_path, reason))
    if kind != "absent":
        raise Refusal("REFUSED: %s exists. --init runs once, at install, and never over an "
                      "existing slices.json, which holds the audit history and the baseline"
                      % state_path)
    data = {"version": STATE_VERSION, "initialised": stamp(now()), "audits": [],
            "baseline": None, "owed": []}
    try:
        notes = write_atomic(state_path, data, exclusive=True,
                             verify=lambda temporary: read_back(registry, temporary, data,
                                                                "slices.json not created"))
    except FileExistsError:
        raise Refusal("REFUSED: %s appeared while --init ran; it is left as it is" % state_path)
    except OSError as err:
        raise Refusal("REFUSED: slices.json could not be created at %s (%s)%s"
                      % (state_path, err.strerror or err,
                         "; " + err.left_behind if getattr(err, "left_behind", None) else ""))
    emit(["INITIALISED: %s · no audits, no baseline · the first pick lists no changed files, and "
          "its --record sets the first baseline" % state_path] + ["note: %s" % n for n in notes])
    return EXIT_OK


def read_back(registry, temporary, data, unchanged):
    """The new state, read back from its temporary file before it is put in place: a registered
    acquisition (`slices.json read back`), read as slices.json is (strict UTF-8, strict JSON, the
    state's shape) and equal to what was written. A Refusal saying `unchanged` (true, since
    nothing has replaced slices.json yet) unless it succeeded."""
    with registry.acquire("slices.json read back", "the new state in its temporary file %s"
                          % temporary, "the record: a state that does not read back is never put "
                          "in place") as acquisition:
        try:
            text = read_text(temporary)
        except OSError as err:
            acquisition.fail(temporary, err.strerror or str(err))
        except UnicodeDecodeError as err:
            acquisition.fail(temporary, undecodable(err))
        else:
            try:
                found = strict_json(text)
            except ValueError as err:
                acquisition.fail(temporary, "not one JSON document (%s)" % err)
            else:
                problems = state_problems(found)
                if problems:
                    acquisition.fail(temporary, "; ".join(problems[:3]))
                elif found != data:
                    acquisition.fail(temporary, "it does not read back as written")
        acquisition.done()
    check = registry.get("slices.json read back")
    if check.outcome() != OK:
        raise Refusal("REFUSED: the new state, written to a temporary file beside slices.json, did "
                      "not read back as written (%s: %s), so it was not put in place: %s"
                      % (check.outcome(), check.detail(), unchanged))


def owed_entry_of(path, vault, tools, hooks):
    """The owed entry for a reading-list path: its hash key (a folder's, for a path ending in `/`,
    as a deleted folder is listed), or the path itself outside the hashed roots."""
    if path.endswith("/"):
        return key_for(path.rstrip("/"), vault, tools, hooks, folder=True) or path
    return key_for(path, vault, tools, hooks) or path


def do_record(registry, vault, tools, hooks, state_path, today, slice_name, findings,
              manifest_path, report_path):
    state = load_state(registry, state_path)
    manifest = load_manifest(registry, manifest_path)
    names = manifest["slices"]
    if slice_name not in names:
        near = difflib.get_close_matches(slice_name, names, n=1)
        raise Refusal("REFUSED: %r is not a slice of the rotation its pick listed%s, and the "
                      "manifest's pick chose slice %s; slices.json unchanged"
                      % (slice_name, "; nearest: %s" % near[0] if near else "", manifest["slice"]))
    # the record credits only the slice whose reading the manifest represents (CR-AUDIT14 F1): the
    # manifest's reading list, requirement files and second-pass sources are its pick's slice's, so
    # any other slice named is refused here, before anything is committed
    if slice_name != manifest["slice"]:
        raise Refusal("REFUSED: --record names slice %s, but the manifest's pick chose slice %s, "
                      "whose reading the manifest represents (its reading list, requirement files "
                      "and second-pass sources), so the record can credit %s alone; slices.json "
                      "unchanged" % (slice_name, manifest["slice"], manifest["slice"]))
    audits = list(state["audits"])
    if any(a["date"] == today.isoformat() and a["slice"] == slice_name for a in audits):
        raise Refusal("REFUSED: %s is already recorded for %s; slices.json unchanged (mend it by "
                      "hand if the count was wrong)" % (slice_name, today.isoformat()))
    here = {"vault": vault, "tools": tools, "hooks": hooks}
    differ = [label for label in ROOT_LABELS
              if os.path.realpath(manifest["roots"][label]) != os.path.realpath(here[label])]
    if differ:
        raise Refusal("REFUSED: the manifest %s was taken over other roots (%s); slices.json "
                      "unchanged" % (manifest_path, "; ".join(
                          "%s %s, here %s" % (label, manifest["roots"][label], here[label])
                          for label in differ)))
    taken = parse_time(manifest["taken"])
    last = max((parse_time(a["recorded"]) for a in audits), default=None)
    if last is not None and taken < last:
        raise Refusal("REFUSED: the manifest %s was taken at %s, before the last record at %s, so "
                      "it is not what this audit read; slices.json unchanged"
                      % (manifest_path, manifest["taken"], stamp(last)))
    if "vault/CLAUDE.md" not in manifest["hashes"] \
            and not covered("vault/CLAUDE.md", manifest["unread"]):
        probe_failed("the manifest holds no hash for CLAUDE.md; slices.json unchanged")
    # every mandatory input, each in its phase (D18): the reading list and the requirement files
    # (pass 1), the second-pass sources (pass 2), any of which the section may name; and the
    # comparison sources among them, whatever their phase (CR-AUDIT11 F3: in its own week the
    # register is a reading-list file, and an unread one limits the labels there too)
    requirements = list(manifest["requirements"])
    source_paths = [source["path"] for source in manifest["sources"]]
    comparison_paths = list(manifest["comparison"])
    mandatory = list(manifest["reading"]) + requirements + source_paths
    named = read_coverage(registry, report_path, mandatory)

    # The record's own acquisitions have all reported, or never will: they govern the recorded
    # completion as the pick's govern its manifest, each reason kept, and a record they cannot
    # vouch for moves nothing on.
    own_short = registry.short()
    coverage_ok = registry.get("coverage").outcome() == OK
    inputs_ok = all(a.name == "coverage" for a in own_short)
    if not coverage_ok:
        named = list(mandatory)   # what the reviewer read is unknown: none of it counts as read
    not_read = [path for path in named if path in manifest["reading"]]
    unread_requirements = [path for path in named if path in requirements]
    unread_sources = [path for path in named if path in source_paths]
    unread_comparison = [path for path in named if path in comparison_paths]
    labels_limited = manifest["labels_limited"] or bool(unread_comparison)
    reasons = []
    if not manifest["complete"]:
        pick_short = [a for a in manifest["acquisitions"] if a["status"] != OK]
        reasons.append("its pick was incomplete: %d acquisition(s) did not succeed (%s)"
                       % (len(pick_short), "; ".join("%s: %s" % (a["name"], a["status"])
                                                     for a in pick_short)))
    for acquisition in own_short:
        reasons.append("the record's own acquisition %s did not succeed (%s: %s)%s"
                       % (acquisition.name, acquisition.outcome(), acquisition.detail(),
                          ", so every mandatory input counts as not read (each reading-list file "
                          "owed) and the labels are limited" if acquisition.name == "coverage"
                          else ", so the baseline does not advance and no owed entry is "
                          "discharged"))
    if not_read and coverage_ok:
        reasons.append("the reviewer did not read %d file(s)" % len(not_read))
        reasons.extend("the reviewer did not read the comparison source %s (pass 1, on this "
                       "audit's reading list), so the audit's labels are limited" % path
                       for path in not_read if path in comparison_paths)
    if coverage_ok:   # the other omissions: explicit reasons, owed nothing (D18)
        reasons.extend("the reviewer did not read the requirement file %s (pass 1)" % path
                       for path in unread_requirements)
        reasons.extend("the reviewer did not read the second-pass source %s (pass 2)%s"
                       % (path, ", a comparison source, so the audit's labels are limited"
                          if path in comparison_paths else "") for path in unread_sources)
    complete = not reasons
    not_read_entries = [owed_entry_of(p, vault, tools, hooks) for p in not_read]
    # a file held for the second pass that an owed entry holds and the report names (CR-AUDIT13
    # F2) keeps its earlier hash, as a reading-list file named does, and its entry stays owed
    # (below); a second-pass source named that no owed entry holds is owed nothing (D18)
    owed_now = set(entry["entry"] for entry in state["owed"])
    held_not_read = []
    for noted in manifest["owed"]:
        for path in noted["held"] if noted["entry"] in owed_now else []:
            if path in unread_sources and path not in held_not_read:
                held_not_read.append(path)
    previous = state["baseline"]["hashes"] if state["baseline"] is not None else {}
    unread_entries = list(manifest["unread"]) + [e for e in not_read_entries
                                                 if e not in manifest["unread"]]
    unread_entries += [e for e in (owed_entry_of(p, vault, tools, hooks) for p in held_not_read)
                       if e not in unread_entries]
    hashes, kept, absent, outside = merge_baseline(manifest["hashes"], unread_entries, previous)
    audits.append({"date": today.isoformat(), "slice": slice_name, "findings": findings,
                   "recorded": stamp(now()), "manifest_taken": manifest["taken"],
                   "complete": complete, "reasons": reasons})
    if inputs_ok:
        baseline = {"taken": manifest["taken"], "date": manifest["date"],
                    "roots": manifest["roots"], "hashes": hashes}
    elif state["baseline"] is not None:
        baseline = state["baseline"]   # it does not advance
        hashes, kept, absent, outside = baseline["hashes"], [], [], []
    else:
        # a first baseline that holds no hash: the next pick lists every file as new
        baseline = {"taken": manifest["taken"], "date": manifest["date"],
                    "roots": manifest["roots"], "hashes": {}}
        hashes, kept, absent, outside = {}, [], [], []

    # Owed content: discharged only for what the pick listed and the reviewer read.
    read = set(manifest["reading"]) - set(not_read)
    listed = dict((o["entry"], o) for o in manifest["owed"])
    remaining, discharged, stays = [], [], []
    for entry in state["owed"]:
        noted = listed.get(entry["entry"])
        if not inputs_ok:
            why = "the record's own acquisitions did not all succeed"
        elif noted is None:
            why = "its pick did not acquire it"
        elif not noted["acquired"]:
            why = "its pick could not read it whole"
        elif not entry["entry"].startswith("/") and covered(entry["entry"], manifest["unread"]):
            why = "its pick could not read it"
        elif not noted["files"]:
            why = "its pick listed none of its content"
        elif any(path not in read for path in noted["files"]):
            why = "the reviewer did not read %d of its %d file(s)" % (
                sum(1 for path in noted["files"] if path not in read), len(noted["files"]))
        elif any(path in held_not_read for path in noted["held"]):
            why = ("the reviewer did not read %d of its %d file(s) held for the second pass, "
                   "named under `%s`" % (sum(1 for path in noted["held"] if path in held_not_read),
                                         len(noted["held"]), NOT_READ_HEADING))
        else:
            discharged.append(entry)
            continue
        remaining.append(entry)
        stays.append((entry, why))
    held = set(owed_entry_of(p, vault, tools, hooks) for p in held_files(vault, manifest["slice"]))
    added = []
    for entry, why in ([(e, "its pick could not read it") for e in manifest["unread"]]
                       + [(e, "the reviewer did not read it") for e in not_read_entries]):
        if entry in held or any(entry == o["entry"] or (o["entry"].endswith("/")
                                                        and entry.startswith(o["entry"]))
                                for o in remaining + [a for a, _ in added]):
            continue
        added.append(({"entry": entry, "since": today.isoformat()}, why))
    owed = remaining + [a for a, _ in added]
    data = {"version": STATE_VERSION, "initialised": state["initialised"], "audits": audits,
            "baseline": baseline, "owed": owed}
    # THE COMMIT: the new state is written beside slices.json, read back and checked, and only then
    # put in place in one step; every refusal comes before that step, so each says, truly, that
    # slices.json is unchanged
    try:
        notes = write_atomic(state_path, data,
                             verify=lambda temporary: read_back(registry, temporary, data,
                                                                "slices.json unchanged"))
    except OSError as err:
        raise Refusal("REFUSED: the new state could not be written beside slices.json (%s: %s), so "
                      "nothing replaced it: slices.json unchanged%s"
                      % (state_path, err.strerror or err,
                         "; " + err.left_behind if getattr(err, "left_behind", None) else ""))
    # slices.json now holds this record: nothing below refuses, and no line says it is unchanged
    try:
        others = {"requirements": unread_requirements, "sources": unread_sources,
                  "comparison": comparison_paths, "labels_limited": labels_limited,
                  "unread_comparison": unread_comparison}
        lines = record_lines(registry, vault, tools, hooks, state_path, today, slice_name,
                             findings, manifest, state, own_short, coverage_ok, inputs_ok,
                             not_read, complete, reasons, hashes, kept, absent, outside,
                             discharged, listed, stays, added, owed, notes, others)
    except Refusal as refusal:
        raise Refusal(after_commit(state_path, refusal))
    emit(lines)
    return EXIT_OK


def after_commit(state_path, refusal):
    """A refusal raised after slices.json was replaced, said as what it is: the record is made, so
    no clause of it may say slices.json is unchanged (none is expected: the rescan reports its own
    failures, and printing raises nothing)."""
    clauses = [c for c in re.split(r";\s*", str(refusal)) if "unchanged" not in c]
    return ("PROBE FAILED: slices.json was written at %s and holds this record; what followed it "
            "could not finish: %s" % (state_path, "; ".join(clauses) or "(no reason given)"))


def record_lines(registry, vault, tools, hooks, state_path, today, slice_name, findings, manifest,
                 state, own_short, coverage_ok, inputs_ok, not_read, complete, reasons, hashes,
                 kept, absent, outside, discharged, listed, stays, added, owed, notes, others):
    """The record's output, after its commit, and the diagnostic rescan, which cannot change it."""
    lines = []
    say = lines.append
    say("RECORDED: %s · slice %s · findings %d · %s · baseline %d files, the manifest taken %s "
        "-> %s" % (today.isoformat(), slice_name, findings, "complete" if complete
                   else "INCOMPLETE", len(hashes), manifest["taken"], state_path))
    for note in notes:
        say("note: %s" % note)
    for acquisition in own_short:
        say("RECORD INCOMPLETE: its own acquisition %s did not succeed: %s: %s; %s"
            % (acquisition.name, acquisition.outcome(), acquisition.detail(),
               "every reading-list file counts as not read and is owed"
               if acquisition.name == "coverage" else "the baseline does not advance and no "
               "owed entry is discharged"))
    if state["baseline"] is None:
        say("first baseline: the next pick compares with it")
    unread_requirements, unread_sources = others["requirements"], others["sources"]
    if not coverage_ok:
        say("coverage: UNKNOWN (the record's own acquisition of the report did not succeed), so "
            "each of the %d reading-list file(s) counts as not read: each is owed and keeps its "
            "earlier baseline; so do its %d requirement file(s) and %d second-pass source(s), "
            "which are owed nothing" % (len(manifest["reading"]), len(manifest["requirements"]),
                                        len(manifest["sources"])))
    elif not (not_read or unread_requirements or unread_sources):
        say("coverage: the report's `%s` says none: the reviewer read all %d reading-list "
            "file(s), %d requirement file(s) and %d second-pass source(s)"
            % (NOT_READ_HEADING, len(manifest["reading"]), len(manifest["requirements"]),
               len(manifest["sources"])))
    else:
        if not_read:
            say("coverage: the report's `%s` names %d of the %d reading-list file(s); each is "
                "owed and keeps its earlier baseline:" % (NOT_READ_HEADING, len(not_read),
                                                          len(manifest["reading"])))
            for path in not_read:
                say("  not read: %s%s" % (path, " (a comparison source, read in pass 1 this week: "
                                                "labels limited)" if path in others["comparison"]
                                          else ""))
        if unread_requirements or unread_sources:
            say("coverage: the report's `%s` names %d requirement file(s) (pass 1) and %d "
                "second-pass source(s) (pass 2); none is newly owed (one an owed entry holds keeps "
                "that entry owed, and its earlier hash), and each makes the audit "
                "incomplete:" % (NOT_READ_HEADING, len(unread_requirements),
                                 len(unread_sources)))
            for path in unread_requirements:
                say("  not read (requirement file, pass 1): %s" % path)
            for path in unread_sources:
                say("  not read (second-pass source, pass 2%s): %s"
                    % ("; a comparison source: labels limited" if path in others["comparison"]
                       else "", path))
    short = [a for a in manifest["acquisitions"] if a["status"] != OK]
    if short:
        say("INCOMPLETE MANIFEST: %d acquisition(s) of its pick did not succeed:" % len(short))
        for acquisition in short:
            say("  %s: %s: %s" % (acquisition["name"], acquisition["status"],
                                  acquisition["detail"]))
    causes = (["a comparison source did not succeed at the pick"] if manifest["labels_limited"]
              else []) + (["the reviewer did not read the comparison source(s) %s"
                           % ", ".join(others["unread_comparison"])]
                          if others["unread_comparison"] and coverage_ok else []) + (
        ["the reviewer's coverage is unknown"] if not coverage_ok else [])
    if causes:
        say("LABELS LIMITED: %s, so no finding of this audit is labelled `new kind`; such labels "
            "are candidates the head checks (AUDIT.md, step 7)" % "; and ".join(causes))
    if not inputs_ok:
        say("BASELINE KEPT whole: the record's own acquisitions did not all succeed, so %s"
            % ("the baseline of %s stays as it was" % state["baseline"]["date"]
               if state["baseline"] is not None else "the first baseline holds no hash, and "
               "the next pick lists every file as new"))
    if kept or absent or outside:
        say("BASELINE KEPT where the audit did not read (its pick could not, or the reviewer "
            "did not):")
        for entry, count in kept:
            say("  kept: %s (%s)" % (entry, "%d earlier hash(es) below it kept" % count
                                     if entry.endswith("/") else "its hash from the baseline "
                                     "of %s" % state["baseline"]["date"]))
        for entry in absent:
            say("  absent: %s (no earlier hash, so the next pick lists it as new)" % entry)
        for entry in outside:
            say("  outside the hashed roots: %s (no hash to keep)" % entry)
    if not complete:
        say("INCOMPLETE AUDIT: recorded as incomplete (%s). The rotation counts it as "
            "attempted, so the next pick moves on; what it left unread is owed to every later "
            "reading list until it is read." % "; ".join(reasons))
    gone = [e for e in discharged if listed[e["entry"]]["deleted"]]
    read_whole = [e for e in discharged if not listed[e["entry"]]["deleted"]]
    if read_whole:
        say("owed: discharged %d entr%s, listed by this audit's pick and read: %s"
            % (len(read_whole), "y" if len(read_whole) == 1 else "ies",
               ", ".join(entry["entry"] for entry in read_whole)))
    if gone:
        say("owed: discharged %d entr%s deleted since its baseline, listed as deleted and not "
            "named under `%s`; the baseline records each as absent, so a reappearance reads as "
            "changed: %s" % (len(gone), "y" if len(gone) == 1 else "ies", NOT_READ_HEADING,
                             ", ".join(entry["entry"] for entry in gone)))
    for entry, why in stays:
        say("  owed: %s (since %s): stays owed, since %s" % (entry["entry"], entry["since"], why))
    for entry, why in added:
        say("  owed: %s (since %s): newly owed, since %s" % (entry["entry"], entry["since"], why))
    say("owed: %d entr%s after this record" % (len(owed), "y" if len(owed) == 1 else "ies"))

    # A diagnostic: what changed since the pick, so the next pick lists it. It follows the commit
    # and cannot change the record; its own failures read as unreadable, never as unchanged.
    current, key_paths, unread_now, absent_roots, _ = hash_roots(
        registry, vault, tools, hooks, StateFilter(state_path), step="rescan")
    rescan_short = [a for a in registry.entries
                    if a.name.startswith("rescan: ") and a.outcome() != OK]
    changed, new, removed = compare(hashes, current, [key for key, _, _ in unread_now])
    say("changed since the pick%s, so not in this baseline (the next pick lists them): %s%d "
        "changed, %d new, %d removed" % ("" if complete else " or unread by this audit",
                                         "UNKNOWN in part (%d rescan(s) did not succeed, %d "
                                         "path(s) unreadable now); " % (len(rescan_short),
                                                                        len(unread_now))
                                         if rescan_short else "", len(changed),
                                         len(new), len(removed)))
    for key in changed + new + removed:
        say("  %s" % key_path(key, vault, tools, hooks))
    for acquisition in rescan_short:
        say("rescan did not succeed (not compared): %s: %s: %s"
            % (acquisition.name, acquisition.outcome(), acquisition.detail()))
    for root in absent_roots:
        say("optional root absent: %s" % root)
    return lines


# ------------------------------------------------------------------ main ---------------------

class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Refusal("REFUSED: %s (see --help)" % message)


def main(argv=None):
    parser = Parser(description="Pick the weekly fresh-eyes audit's slice and print its reading "
                                "list; with --record, record the audit in slices.json; with "
                                "--init, create slices.json at install.")
    parser.add_argument("--vault", help="the vault (default: CLAUDE_PROJECT_DIR, else "
                                        "LLM_WIKI_VAULT)")
    parser.add_argument("--tools", help="the tools folder (default: the folder above this "
                                        "script's own)")
    parser.add_argument("--hooks", help="the hooks folder (default: `hooks` beside the tools "
                                        "folder)")
    parser.add_argument("--state", help="slices.json (default: beside this script)")
    parser.add_argument("--today", help="the audit's date, YYYY-MM-DD (default: today, local "
                                        "time); for tests and for a review held after midnight")
    parser.add_argument("--init", action="store_true",
                        help="the install step: create slices.json (no audits, no baseline); "
                             "refuses when it exists")
    parser.add_argument("--manifest-out", metavar="PATH",
                        help="the pick also writes its manifest to PATH, and nothing else")
    parser.add_argument("--record", metavar="SLICE", help="record this audit of SLICE")
    parser.add_argument("--findings", metavar="N", type=int,
                        help="with --record: the audit's confirmed finding count")
    parser.add_argument("--manifest", metavar="PATH",
                        help="with --record: the manifest the audit's pick wrote")
    parser.add_argument("--report", metavar="PATH",
                        help="with --record: the reviewer's report, whose `## Not read` section "
                             "says what it did not read")
    registry = Registry()
    try:
        args = parser.parse_args(argv)
        if args.today:
            today = valid_date(args.today)
            if today is None:
                raise Refusal("REFUSED: --today %r is not a YYYY-MM-DD date" % args.today)
        else:
            today = datetime.date.today()
        if args.init:
            if args.record is not None or args.findings is not None or args.manifest \
                    or args.manifest_out or args.report:
                raise Refusal("REFUSED: --init takes no --record, --findings, --manifest, "
                              "--report or --manifest-out")
            return do_init(registry, resolve_state(args))
        if (args.record is None) != (args.findings is None):
            raise Refusal("REFUSED: --record and --findings go together")
        if args.findings is not None and args.findings < 0:
            raise Refusal("REFUSED: --findings must be 0 or more")
        if args.record is not None and not args.manifest:
            raise Refusal("REFUSED: --record needs --manifest PATH, the manifest the audit's pick "
                          "wrote with --manifest-out: the baseline is what the audit read; "
                          "slices.json unchanged")
        if args.record is not None and not args.report:
            raise Refusal("REFUSED: --record needs --report PATH, the reviewer's report, whose "
                          "`## Not read` section says what it did not read: coverage comes from "
                          "the reviewer, not the pick; slices.json unchanged")
        if args.manifest and args.record is None:
            raise Refusal("REFUSED: --manifest goes with --record")
        if args.report and args.record is None:
            raise Refusal("REFUSED: --report goes with --record")
        if args.manifest_out and args.record is not None:
            raise Refusal("REFUSED: --manifest-out goes with a pick, not with --record")
        vault, tools, hooks, state = resolve(registry, args)
        if args.record is not None:
            return do_record(registry, vault, tools, hooks, state, today, args.record,
                             args.findings, os.path.abspath(os.path.expanduser(args.manifest)),
                             os.path.abspath(os.path.expanduser(args.report)))
        manifest_out = (os.path.abspath(os.path.expanduser(args.manifest_out))
                        if args.manifest_out else None)
        return do_pick(registry, vault, tools, hooks, state, today, manifest_out)
    except Refusal as refusal:
        emit([str(refusal)])
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
