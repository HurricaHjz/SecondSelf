#!/usr/bin/env python3
"""vault-writes.py — the vault writes a head composes by hand, as primitives that cannot slip.

Six writes recur in every run — a log entry, a defect-register entry, a register entry
closed or annotated, an IDEAS bullet annotated, a decided-work line added, changed or
closed — and each has been mis-composed by hand: a misplaced anchor, a doubled span, an entry
inserted under the wrong heading, a whole-file rewrite that erased a line a concurrent writer
had added. Each verb below makes one of them against an asserted anchor, prints one line, and
refuses rather than guesses.

  log-append         append one entry to `wiki/log.md` under the vault root given.
  register add       insert one entry at the top of `## Open` in
                     `wiki/developments/known-issues.md`.
  register close     move one `## Open` entry to the top of `## Closed`, dating its Status.
  register annotate  replace one `## Open` entry's one Status (`--kind Status`), or append one
                     dated, clock-stamped Recurrence or Correction note to it.
  ideas annotate     append ` *(agent DATE TIME: NOTE)*` to one numbered IDEAS bullet.
  decided add        insert one line under `## To build` in `wiki/developments/decided-work.md`,
                     with the next unused id for its date on that page and its closed page.
  decided status     set one open line's one dated, clock-stamped status clause.
  decided state      replace one open line's state, and set its status clause to the reason.
  decided close      close one open line onto `wiki/developments/decided-work-done.md`.

The catalogue, `wiki/index.md`, is updated by anchored edits (CLAUDE.md §5), with no verb here.

The clock, and why it is not an argument

  A time of day written by hand is written from a sense of elapsed time, and such stamps
  spread across surfaces before anything compares one to a clock. So
  every stamp below is read from the clock at the moment of the write and from nowhere
  else — no `--time` argument exists to be guessed into:

    register add       `### [DATE HH:MM] SURFACE — TITLE (SEVERITY)`, the date from `--date`;
                       a stamp another heading already carries takes a suffix (below).
    register close     the status fact as `closed DATE HH:MM — …`: the time is inserted after
                       the date the caller's `--status` already opens with (`closed DATE …`),
                       and otherwise the whole stamp is prefixed to the caller's text.
    register annotate  `--kind Status`: the entry's Status field reads `NOTE (set DATE HH:MM
                       ZONE by BY)`, ` by BY` omitted when absent; a Recurrence or Correction
                       note is `- **KIND DATE HH:MM ZONE (BY):** NOTE`, ` (BY)` omitted likewise.
    ideas annotate     `*(agent DATE HH:MM: NOTE)*`.
    log-append         one further bullet, `- **Clock**: HH:MM ZONE`, written through the
                       `--extra` path between Changed and Conflicts. The `## [DATE] ACTION |
                       TITLE` heading is a schema surface and is not touched.
    decided add        a last field `recorded by BY at HH:MM ZONE`, with ` on D Month YYYY`
                       when the clock's date is not the decision's (`--date`).
    decided status     ` · status D Month YYYY, HH:MM ZONE (BY): NOTE`, date and time both
    decided state      the clock's.
    decided close      the closing clause `KIND D Month YYYY: EVIDENCE (closed HH:MM ZONE by BY)`.

  In the decided verbs a time with seconds (`00:51:57`) is a citation of the owner's words
  and is not scanned, and `--locator` is not scanned at all: it cites his words by definition.

  The zone is the clock's own (`%Z`), never a literal. And because a caller's free text may
  still name a time, every text argument is scanned for an `HH:MM` or `HH:Mx` token whose
  hour disagrees with the clock's: each such token prints one line on stderr,
  `clock: the note names TOKEN, the clock reads HH:MM`. It is a warning and never a
  refusal — a note may legitimately cite a past event — so the write proceeds either way,
  and `--dry-run` prints the same warnings. The hour has two digits, as every stamp the vault
  writes has, so a meter's model count (`claude-opus-5:88`) is not a time; nor is a token
  glued to a word by a hyphen or a dot, a minute above 59, or an ISO zone offset (`+01:00`).
  The time attached to a `YYYY-MM-DD` date cites that dated moment and is skipped: the token
  directly after the date, with spaces alone between them (`the entry of 2026-09-30 13:54`),
  and the far end of a range written from that token with a hyphen, an en dash or `to`
  (`2026-09-30 13:54–14:10`, `2026-09-30 13:54 to 14:10`). Every other token is checked, in
  a dated argument too (`seen 2026-09-30 13:54; now filing at 12:00` warns about 12:00), and
  so is the time of a `register close` caller's own `closed DATE HH:MM` stamp, which claims
  the close's own time rather than citing one.

One stamp, one entry (register add)

  A pointer that cites an entry by its stamp alone must find one heading. So `register add`
  reads the stamp of every heading in the register, Open, Closed and elsewhere, and on the
  register's closed page (`known-issues-closed.md` beside it, where sweep_closed.py moves the
  closed entries with their headings unchanged), before it writes its own. The first entry of
  a minute keeps the bare stamp; a later one in the same
  minute takes a space and the first free letter from b to z inside the brackets,
  `### [2026-10-03 07:48 b] …`; the heading on the reported line, or a dry run, shows which.
  Every reader of the register reads a heading by its `### [` opening or as a whole line, so
  the suffix changes no reader. It refuses where it cannot tell what the new stamp would point
  at: a heading whose bracket opens with the same date and time in any other form (`07:48b`,
  `07:48:31`, `07:48 bb`), or opens with them and never closes (`[DATE HH:MM` alone, or
  `[DATE HH:MM unfinished`); a stamp of that minute that already heads two entries; and a
  minute whose every suffix is taken. Stamps of other minutes that are shared, as many older
  ones are, stop nothing.

Why not fixed now (register add)

  An entry parks a defect, and parking needs a named reason that blocks the fix now
  (CLAUDE.md §12). So `--why-not-fixed-now` is required, and its text is written as its own
  bullet, `- **Why not fixed now**: …`, between Suspected cause and Status, where the
  register's own entry format puts it. Missing, empty, blank or carrying a line break, it
  refuses.

The lines an entry owns (register close, register annotate)

  An entry is its heading, then its own lines: bullets opening `- **` (the fields, and the
  dated Status, Recurrence and Correction notes), lines indented under one of them, and —
  first under the heading only — a plain bullet opening with a date (the one-line entries
  that were given headings later, their text unchanged). Blank lines never end an entry; the
  first line that is none of these does, and so does any heading. A close moves those lines
  and the blank lines after them, and leaves anything after them where it was, with one
  `extent:` line on stderr.
  Its Status field is its own `- **Status**: …` bullet, or its `- **Severity**: … **Status**:
  …` line; a dated note, or any text that only quotes the marker, is not one. Both verbs read
  the entry's structure the same way and refuse what they cannot read: inside its own lines a
  bold bullet opening with a date anywhere but first, or a second copy of a field every entry
  carries once (Where observed, Symptom, Suspected cause, Why not fixed now, Status), which is
  another entry under the same heading; and a Status field under the same heading but below a
  line that is not its own. A close also refuses an entry with no Status field. A note never
  carries the field marker `**Status**:` itself (the register's lint reads that marker as a
  Status wherever it stands), so `register annotate` refuses one.

One status (register annotate --kind Status, decided status, decided state)

  An open entry and an open work line each keep one status: what blocks it now, who proposes
  the next step and when (the stale-information design, 21 November 2026). So a Status write
  replaces the status and no longer appends a dated one beside it. On the register it rewrites
  the entry's one Status field, the bullet `- **Status**: …` or the `**Status**: …` part of a
  `- **Severity**: …` line, from the marker to the end of that line, and changes no other line;
  an entry with no Status field, or with two, refuses. Dated `- **Status DATE …:**` notes an
  entry already holds stay where they are: folding them is a clean's work, by judgement. A
  Recurrence or Correction note is a record of an event or of a fix to the entry's own text and
  is still appended, removing nothing. On the work list a status clause is a field after the
  `recorded by` field opening `status D Month YYYY`; `decided status` and `decided state` remove
  every such clause the line holds and append the one new clause, and `decided state` writes the
  caller's note alone, no longer the earlier state. A replaced status is the one text removed
  with no hold checked, on purpose: it is working state, replaced within hours or days, and no
  reader needs an earlier one once the entry's symptom, cause and close are kept. Each such
  write names on stderr what it replaced (`replaced: …`), and on the work list each other field
  that stood among the status clauses, which it keeps (`kept: …`).

Concurrent writers

  Every write but the log append replaces its target whole, so a change another writer made
  after this run read the file would be overwritten by it. Three measures bound that:

    the lock     each writing run holds an advisory lock on the target's directory from
                 before its read until after its replace, so two runs of this tool never
                 interleave on one target. Locking is a premise of the write: a platform
                 without `flock`, a directory that cannot be opened or locked, and a lock
                 another run holds past LOCK_WAIT each refuse before anything is read or
                 written. Other programs do not take the lock.
    the check    the bytes are hashed at the read; the new text is written to its temporary
                 file; then the target is read and hashed again, and its inode, device, size
                 and modification time are taken once more as the last look before the
                 replace. Any difference refuses: `error <verb>: <file>: it changed on disk
                 since this run read it …` (or it is gone, or cannot be read again), the
                 temporary file removed and the target left exactly as the other writer left
                 it. A rewrite of the same bytes completed before the last look is no change.
    the window   the guarantee covers changes that land before the last look. Nothing here
                 closes the interval between the last look and the moment the rename takes
                 effect, and this design puts no bound on it: the process can be descheduled
                 there for any length of time, and a write another program makes inside it is
                 overwritten (the suite's late-writer leg shows it). Runs of this tool never
                 meet there, because each holds the lock across it.
    premises     a write that depends on a second page it does not replace (the closed
                 decided-work page, for an add or a close) checks that page's fact again
                 after the target's re-read and before its last look, so the last look still
                 ends the check. A premise is a fact, not the page's bytes: a `updated:` stamp
                 patched by a hook elsewhere on that page stops nothing.

  The log append holds the same lock on the log's folder from before its probe until after
  its read-back, and it opens the log for appending before it probes, so the tail it reads
  and the end it writes at are the same file's. An append never overwrites: another program
  that appends in between pushes this entry later, and the read-back then reports `ok` at the
  line where it landed, with one `readback:` line on stderr. Two outcomes are an `error`: an
  entry absent from the log as it stands after the write (the log replaced or truncated under
  the open), and then a re-run writes it once; and an entry pushed later behind bytes that end
  mid-line, so its heading is glued to their line: it landed malformed, and the fix is a
  correction entry, never a re-run.

The payload, and what a shell may have done to it (log-append)

  A payload inside double quotes is expanded by the caller's shell before this script sees
  it: a backticked token is run as a command and replaced by its output, usually nothing. The
  clean loss arrives looking like ordinary text and cannot be seen here. Two of its traces
  can: an argument carrying an odd number of backticks (a code span left open), and one
  carrying the text `command not found` (a substitution's own error captured into the
  payload). Each prints one stderr line, `payload: ARGUMENT carries …`, and the write
  proceeds either way; `--dry-run` prints the same warnings.

Inside a helper (LLM_WIKI_LANE_WRITES)

  A helper that lane.py spawns carries its write grants in LLM_WIKI_LANE_WRITES: the
  os.pathsep-joined real paths of its --write grants, files or folders, and the empty string
  for a helper with no write grant. Where that variable is present, every verb refuses unless
  the grants cover each file it would change (log-append: the log; the register verbs: the
  register; ideas annotate: the IDEAS file; decided add, status and state: the open page; decided
  close: both pages), the file itself granted or a granted folder holding it, and none of those
  files itself a symbolic link (a folder reached through one is followed) or a file with a
  second hard link: one error line naming the target, exit 2, nothing read, locked or written.
  `--dry-run` refuses the same way, so it stays the run it previews. Present but empty, or not
  a list of absolute paths, every verb refuses. Absent while LLM_WIKI_LANE, LLM_WIKI_LANE_ID or
  LLM_WIKI_LANE_GRANTS is set (names lane.py sets beside it), every verb refuses too: that is a
  helper whose grants cannot be read. Absent with none of those set, as in a lead's
  environment, nothing here applies. A refusal for want of a grant ends by asking the helper to
  report the missing grant. The lane fence cannot see what a script writes, so the writer
  bounds itself, as the ingest sanitiser does. This covers the headless Claude helpers lane.py
  spawns while their environment is as lane.py set it: a helper that clears all four names
  before the call is not seen as one. A Codex helper (codex-lane.py) sets LLM_WIKI_LANE and
  LLM_WIKI_LANE_ID but no grant variable, so every verb refuses inside it, and its sandbox
  bounds its other writes; an in-session helper, a subagent of the lead's own session, is not
  bounded here.

The contract every verb keeps

  * One line of output. `ok <verb> <path>:<line>` names where the change landed, or
    `error <verb>: <reason>` names what stopped it and the process exits 2. A head pays
    a few tokens for a write and never reads a dump.
  * `--dry-run` prints `dry-run <verb> <path>:<line>` and the would-be block as `| `
    lines (at most PREVIEW_MAX, then a count), and writes nothing at all. It is the control
    run, and the way to see a change before making it. It takes no lock.
  * Every write except the log append is atomic and checked: a temp file beside the target,
    fsync, the check above, `os.replace`. An interruption leaves the old file or the new one,
    never half of one.
  * The log is append-only by contract, so `log-append` opens it in append mode and never
    rewrites it. Two bounded read-only probes support that append and neither holds the
    file in memory: its last two bytes (which decide the blank-line separator) and a
    chunked newline count (the line number the `ok` line reports). Neither alters a byte.
    Both are taken through the descriptor the append writes with, under the lock, and the
    read-back reads only from the probe's end onwards.
  * Every text argument carrying a line break is refused, and so is one carrying any other
    character a reader may split a line on (U+2028, U+2029, U+0085, VT, FF). Wiki prose is
    one line per paragraph or bullet (the schema line discipline), and a line break is also
    how a caller text would forge a heading inside somebody else entry. A decided-work field
    may also not start or end with the field separator, and every composed decided-work line
    is checked for the field count its template gives it before anything is written.
  * Refusal beats repair. A structural heading that does not appear exactly once, a match
    count that is not one, a missing or unreadable file, an entry with no Status bullet, a
    lock that cannot be taken, a file changed since its read, a target outside a helper's
    write grants: `error`, exit 2, naming the
    count or the reason it actually found. Nothing is written on a refusal.

Decided work (the decided verbs)

  The rules are the open page's own section "How this page works": its line format, its
  Shared writes span and its Closing rule. Every decided verb first reads the open page's
  structure: `## To build`, `## Later on purpose` and `## How this page works` each exactly
  once as a whole line, in that order, and no other heading between the first and the last.
  The lines between To build and How this page works are the open range. A line belongs to
  the id `DW-YYYYMMDD-n` it carries in bold: the line for an id opens `- [ ] **ID** · `, and
  every line of the page carrying `**ID**` counts against its identity, as the Closing rule's
  `grep -c -F` does. ` · ` separates a line's fields, so no one-field argument (`--work`,
  `--locator`, `--state`, `--home`, `--note`, `--evidence`, `--by`) may carry it, nor `**`,
  which would forge a bold id.

    add      the next id for `--date` is one more than the highest `n` of any
             `DW-<date>-<n>` on either page, bold or cited, so no closed or cited id is
             reused. The anchor is the span from `## To build` through its first content
             line (or the next heading when the section is empty), asserted once in the
             file; it is replaced by the heading, the same blank lines, the new line and the
             old first line (in an empty section, a blank line and the next heading). The
             state is one the page lists, never `later:`. A pre-existing id on two lines is
             named on stderr (`malformed:`) and stops nothing; the owner's quoted words
             already on another line are named on stderr (`duplicate:`) and stop nothing.
    status   sets the line's one status clause: every status clause it holds goes, and the
             new one is appended at its end (One status, above).
    state    replaces the line's fourth field and sets its status clause to the note, as
             status does. It refuses a fourth field that is not a state
             the page lists, `later:` on a To build line and anything else on a Later line:
             moving a line between sections is not a state edit.
    close    counts `**ID**` on the closed page first. On 0, the complete line with its box
             changed (`[x]` built, `[-]` retired or dropped) and the closing clause is
             appended at the end of the closed page, whose `## Closed` must be its last
             heading, and then the open copy is removed. On 1, that closed line must be the
             open line's body with the same box, kind and closing evidence (the rule's "the
             same decision, work and closing evidence"), and then only the open copy is
             removed; anything else there is a repair, refused. On 2 or more, it refuses.
             Every edited, moved or closed line keeps its own line terminator. The two writes are two renames: if the open page changes
             between them, or the run dies between them, the closed line stands and the open
             copy stays, and the error says so; the same command run again takes the count-1
             path and finishes. A dropped line's evidence is his words, `"…" (time and place)`.

  Each decided write reads the page back after the rename and checks what its rule asks:
  the new line once and first under To build, the edited line once, the closed line once on
  the closed page and the id on no line of the open page. A failed read-back is an `error`
  that says the write landed.

Formats, and where they come from

  The log entry is `## [DATE] ACTION | TITLE`, then `- **Changed**: …`, then the `Clock`
  bullet and any `--extra` bullets in the order given, then `- **Conflicts**: …`, then a
  blank line — the shape the file own recent entries carry, Changed first and Conflicts last.
  An `--extra` is the bare `Key: value`; the verb adds the bullet and the bold, so a key that
  starts with `- ` or carries `**` is a finished bullet passed whole and is refused.
  The register entry is the format the register documents above its own `## Open` heading:
  severity in the heading, then `- **Where observed**`, `- **Symptom**`,
  `- **Suspected cause**`, `- **Why not fixed now**`, `- **Status**`. `--status` is the
  caller's own words, prefixed on a close by the clock stamp above and otherwise untouched
  (`open — fix shape: …`); `--where` is optional and its bullet is omitted when it is absent
  rather than filled with invented text. `--cause-kind tested|observed` puts that one word and a
  colon before the cause (`- **Suspected cause**: observed: …`); absent, the field is as before.
  `register close` dates the entry's Status field, so it dates both forms in live use: a
  `- **Status**: …` bullet, and a `- **Severity**: … **Status**: …` line.

Run

  vault-writes.py log-append --vault V --action ACTION --title T --changed C --conflicts X
                             [--extra "Key: value"]... [--date D] [--dry-run]
  vault-writes.py register add --vault V --date D --surface S --symptom Y --cause C
                               --why-not-fixed-now R --severity minor --status T
                               [--where W] [--cause-kind tested|observed] [--dry-run]
  vault-writes.py register close --vault V --match TEXT --date D --status TEXT [--dry-run]
  vault-writes.py register annotate --vault V --match TEXT --kind KIND --note TEXT
                                    [--by WHO] [--date D] [--dry-run]
  vault-writes.py ideas annotate --file IDEAS.md --item N --note TEXT [--date D] [--dry-run]
  vault-writes.py decided add --vault V --date D --work W --locator L --state S
                              [--home H]... --by WHO [--dry-run]
  vault-writes.py decided status --vault V --id ID --note TEXT --by WHO [--dry-run]
  vault-writes.py decided state --vault V --id ID --state S --note TEXT --by WHO [--dry-run]
  vault-writes.py decided close --vault V --id ID --kind built|retired|dropped
                                --evidence TEXT --by WHO [--dry-run]

Suite: `test_vault_writes.sh` beside this file (last line PASS n/n or FAIL k/n).
"""

import argparse
import datetime
import hashlib
import os
import re
import stat
import sys
import tempfile
import time

try:
    import fcntl                        # the write lock (take_lock). Where it is missing, every
except ImportError:                     # checked write refuses rather than writing unlocked.
    fcntl = None

# The vocabulary the log itself uses of entry kinds; anything else is a typo, never a new kind.
ACTIONS = ("ingest", "gather", "synthesis", "lint", "deep-lint", "framework",
           "setup", "maps", "attic", "export")
# The severities the register documents. Its format block offers "blocking · major · minor"
# and its live entries also carry "medium", so all four are accepted and none is invented.
SEVERITIES = ("blocking", "major", "medium", "minor")
# The one word `register add --cause-kind` puts before a suspected cause: whether a test showed the
# cause or it was only seen. Optional, so an entry written without it keeps the old field shape.
CAUSE_KINDS = ("tested", "observed")
# The kinds of dated note `register annotate` writes: the labels a register's hand-written dated
# notes carry most, so a written note reads like those beside it; anything else is a typo.
NOTE_KINDS = ("Status", "Recurrence", "Correction")

# Paths are derived from the vault root the caller passes: no absolute path is written here.
LOG_REL = os.path.join("wiki", "log.md")
REGISTER_REL = os.path.join("wiki", "developments", "known-issues.md")
CLOSED_REL = os.path.join("wiki", "developments", "known-issues-closed.md")   # swept closed entries
DECIDED_REL = os.path.join("wiki", "developments", "decided-work.md")
DONE_REL = os.path.join("wiki", "developments", "decided-work-done.md")

# The decided-work pages: their structural headings, as the open page's reading note counts them.
TO_BUILD_HEAD = "## To build"
LATER_HEAD = "## Later on purpose"
HOW_HEAD = "## How this page works"
DONE_HEAD = "## Closed"
FIELD_SEP = " · "                       # the field separator of a decided-work line
BOLD = "**"
OPEN_BOX = "- [ ] "
# An id as a caller names one, and any id-shaped token on either page (bold or cited).
DW_ID_RE = re.compile(r"^DW-([0-9]{8})-([1-9][0-9]*)$")
DW_TOKEN_RE = re.compile(r"(?<![0-9A-Za-z])DW-([0-9]{8})-([0-9]+)(?![0-9])")
# The closing kinds and their boxes, as the page's Closing rule writes them.
CLOSE_BOX = {"built": "[x]", "retired": "[-]", "dropped": "[-]"}
CLOSED_LINE_RE = re.compile(r"^- (\[(?:x|-)\]) \*\*(DW-[0-9]{8}-[0-9]+)\*\* · ")  # no two brackets together
DROPPED_EVIDENCE_RE = re.compile(r'^".+" \(.+\)$')
# The states the page lists, as this tool reads an existing one (STATE_READ_RE) and writes a new
# one (STATE_NEW_RE). Reading admits a returned line's `to build: <reason>` and any text after
# an `in` state's item; writing admits the shapes alone.
STATE_READ_RE = re.compile(r"^(?:to build(?:: .+)?|in [^ ,]+, item [^ ,]+(?: .*)?|blocked: .+|"
                           r"elsewhere: .+|later: .+)$")
STATE_NEW_RE = {
    "to build": re.compile(r"^to build(?:: .+)?$"),
    "in": re.compile(r"^in [^ ,]+, item [^ ,]+$"),
    "blocked": re.compile(r"^blocked: .+$"),
    "elsewhere": re.compile(r"^elsewhere: .+ \(.+\)$"),
    "later": re.compile(r'^later: .+ \(".+", .+\)$'),
}
# A time with seconds is how the vault cites the owner's words (`00:51:57 GMT`): a citation, so the
# decided verbs leave it out of the clock check.
SECONDS_CITE_RE = re.compile(r"(?<![0-9])[0-9]{2}:[0-5][0-9]:[0-5][0-9](?![0-9])")
# The owner's quoted words inside a locator, for the duplicate notice: the first double-quoted run
# at least this long. Twelve characters is set by judgement, unmeasured: it keeps a quoted one-word
# label ("yes") from naming every line that quotes the same word.
QUOTED_RE = re.compile(r'"([^"]{12,})"')
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")

OPEN_HEAD = "## Open"
CLOSED_HEAD = "## Closed"
WHY_LABEL = "Why not fixed now"
NUMERO = "№"                  # the IDEAS bullet marker, spelled as an escape
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ITEM_RE = re.compile(r"^[0-9]+$")
ENTRY_END_RE = re.compile(r"^#{1,6} ")  # any ATX heading ends the entry above it
CHUNK = 65536                           # the log newline count reads this much at a time
PREVIEW_MAX = 6                         # `--dry-run` prints at most this many `| ` lines
SHORT = 70                              # an error line quotes at most this much of a line

# The lines an entry owns (see the docstring): the shapes the register's entry format and its
# dated notes produce, and the date-led body of a one-line entry that was given a heading later.
OWN_BOLD_RE = re.compile(r"^- \*\*")
OWN_INDENTED_RE = re.compile(r"^[ \t]+\S")
OWN_FIRST_DATED_RE = re.compile(r"^- \d{4}-\d{2}-\d{2}\b")
# Inside an entry's own lines, the shapes of another entry: a bold bullet opening with a date or
# a bracketed stamp below the first line, and a second copy of a field every entry carries once.
FOREIGN_DATED_RE = re.compile(r"^- \*\*\[?\d{4}-\d{2}-\d{2}")
ONCE_FIELD_RE = re.compile(r"^- \*\*(Where observed|Symptom|Suspected cause|Why not fixed now)\*\*:")
# An entry's Status field, in the two forms the register's entry format writes: its own bullet,
# and the combined Severity line. A dated note (`- **Status DATE …:**`) is not one, and neither
# is a field's text or a note that only quotes the marker.
STATUS_FIELD_RE = re.compile(r"^- \*\*Status\*\*:|^- \*\*Severity\*\*:.*?\*\*Status\*\*:")
# The marker the register's lint reads as a Status wherever it stands in an entry's line.
STATUS_MARKER = "**Status**:"

# A heading whose text opens with a bracket: the candidate for a stamp, closed or not.
STAMP_OPEN_RE = re.compile(r"^#{1,6}[ \t]+\[(.*)$")
# The suffixes a later entry of the same minute takes, in order; the first entry of a minute
# keeps the bare stamp. Twenty-five is set by judgement, far above any minute's count of entries.
STAMP_SUFFIXES = "bcdefghijklmnopqrstuvwxyz"

# The write lock. LOCK_WAIT is how long a run waits for another run of this tool to finish
# with the same directory before it refuses; LOCK_POLL is how often it asks. Set by judgement
# against a measurement: a write holds the lock for milliseconds, so ten seconds waits out
# hundreds of writes queued ahead, far beyond any run's concurrency; unmeasured on a network
# filesystem.
LOCK_WAIT = 10.0
LOCK_POLL = 0.05
_LOCKS = []                             # descriptors held by this run, released in main()

# A clock token as the register and the notes actually write one: a two-digit hour, a colon,
# then a minute 00-59 or the rounded `Mx` form the register uses ("filed 21:3x BST").
# The lookarounds keep the seconds of `19:52:29` from reading as a second token (`52:29`)
# and keep a token out of a longer word; an hour above 23 is not a time and is skipped.
# Anchored 2026-09-13 (register entry of 2026-09-09 15:27): a one-digit hour would read a meter's
# model count as a clock. Requiring a two-digit hour avoids that ambiguity; excluding a
# letter followed by a hyphen rejects model counts while retaining the second endpoint
# of a time range. Each lookbehind, and the shape it keeps out:
#   a letter, digit, colon or `+`        a word, a longer time, a zone offset (`+01:00`)
#   a letter then a hyphen               a model id and its count (`opus-15:30`)
#   an alphanumeric then a dot           a version and its count (`gpt-5.10:12`)
#   `:SS-` closing a timestamp           a negative zone offset (`12:00:00-05:00`)
CLOCK_TOKEN_RE = re.compile(r"(?<![0-9A-Za-z:+])(?<![A-Za-z]-)(?<![0-9A-Za-z]\.)"
                            r"(?<!:[0-9]{2}:[0-9]{2}-)"
                            r"([0-9]{2}):([0-5][0-9x])(?![0-9A-Za-z])")
HOUR_MAX = 23
HOURS = 24
# A date as the vault writes one, and the time attached to it: the clock token directly after it,
# with spaces alone between them, and the far end of a range written from that token with a
# hyphen, an en dash or `to`. That time cites the dated moment rather than stamping now (register
# entry of 2026-10-01 13:46), so it is skipped. Any other token of the argument is checked: a later
# one can as well be a slip of the present time (`seen 2026-09-30 13:54; now filing at 12:00`),
# which skipping every token after a date would hide; a second time joined by `and` is not a range.
DATE_TOKEN_RE = re.compile(r"(?<![0-9])[0-9]{4}-[0-9]{2}-[0-9]{2}(?![0-9])")
CITED_GAP_RE = re.compile(r"[ \t]+")                             # between a date and its own time
RANGE_JOIN_RE = re.compile(r"[ \t]*[-–][ \t]*|[ \t]+to[ \t]+")  # between a range's two ends
# The grace: the previous hour passes while the clock's minute is under ten — a note written
# just after the turn of the hour about the minute before it. Ten is set by judgement,
# unmeasured; the failure it forgives (a stamp one minute stale) is smaller than the one it
# would otherwise report, and no count of real notes was taken to choose it.
GRACE_MINUTES = 10
# The status fact `register close` writes, and the two shapes a caller's own `--status` may
# already carry: `closed DATE …` takes the time after its date, `closed DATE HH:MM …` is
# already stamped and is left exactly as it came.
# The already-stamped shape admits the rounded `HH:Mx` minute as well as `HH:MM`, so a
# caller who wrote one keeps it verbatim rather than collecting a second time beside it;
# whether that time agrees with the clock is the token check's business, not this one's.
CLOSED_DATED_RE = re.compile(r"^closed\s+\d{4}-\d{2}-\d{2}")
CLOSED_TIMED_RE = re.compile(r"^closed\s+\d{4}-\d{2}-\d{2}\s+\d{1,2}:[0-9][0-9x]")


def die(verb, reason):
    """One error line on stdout — where the head reads it — then exit 2. Never a traceback."""
    print("error %s: %s" % (verb, reason))
    sys.exit(2)


def note(kind, text):
    """One stderr line: a warning or a notice, never a refusal; stdout keeps the one line."""
    sys.stderr.write("%s: %s\n" % (kind, text))


def short(text):
    """A line quoted inside an error message stays inside one line."""
    text = " ".join(text.split())
    return text if len(text) <= SHORT else text[:SHORT - 1] + "…"


# The other characters a reader may take for a line break: str.splitlines() splits on each, so a page
# read that way would find a forged line (a second heading, another entry) inside one argument.
OTHER_BREAKS = {" ": "U+2028 LINE SEPARATOR", " ": "U+2029 PARAGRAPH SEPARATOR",
                "\u0085": "U+0085 NEXT LINE", "\x0b": "VT (vertical tab)", "\x0c": "FF (form feed)"}


def check_text(verb, name, value, allow_empty=False):
    """A wiki line is one line: refuse any argument carrying a break, and refuse the blank."""
    if value is None:
        return None
    if "\n" in value or "\r" in value:
        die(verb, "%s carries a line break; a wiki bullet is one line" % name)
    for char, label in OTHER_BREAKS.items():
        if char in value:
            die(verb, "%s carries %s, which a reader may split a line on; a wiki bullet is one line" % (name, label))
    if not allow_empty and not value.strip():
        die(verb, "%s is empty" % name)
    return value


def check_date(verb, value):
    """A date is YYYY-MM-DD and a real calendar day; absent, it is today."""
    if value is None:
        return datetime.date.today().isoformat()
    if not DATE_RE.match(value):
        die(verb, "--date '%s' is not YYYY-MM-DD" % value)
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        die(verb, "--date %s is not a real date" % value)
    return value


# ---------------------------------------------------------------- helper grants ---------

# A helper (a lane that lane.py spawns) carries its write grants in its environment: lane.py sets this
# variable to the os.pathsep-joined real paths of the lane's --write grants, files or folders, and to the
# empty string for a lane with no write grant; a lead's environment does not carry it. Inside a helper
# every write of this tool refuses unless those grants cover each file it would change: the lane fence
# cannot see what a script writes, so the writer bounds itself, as the ingest sanitiser does.
LANE_WRITES_VAR = "LLM_WIKI_LANE_WRITES"
# Names lane.py sets beside the grant variable in every helper it spawns (codex-lane.py sets the first two
# and no grant variable). Any of them present while the grant variable is absent is a helper whose grants
# cannot be read, so it writes nothing; a lead's environment carries none of them.
LANE_MARKERS = ("LLM_WIKI_LANE", "LLM_WIKI_LANE_ID", "LLM_WIKI_LANE_GRANTS")
# The remedy a refusal for want of a grant names: the helper reports the gap to its head, rather than
# changing its own environment.
REPORT_GAP = "report the missing grant (`needs: <path> because <reason>`)"


def lane_write_roots(verb, targets):
    """None outside a helper (the variable absent and none of LANE_MARKERS set), else the helper's write
    roots as real paths. Absent beside a marker, present but empty, or not a list of absolute paths,
    refuses: a helper whose grants cannot be read writes nothing. The refusal names the files the write
    would change, prints a value whole, as repr() gives it, so a stray separator or space shows, and ends
    with REPORT_GAP."""
    named = ", ".join(targets)
    if LANE_WRITES_VAR not in os.environ:
        if any(name in os.environ for name in LANE_MARKERS):
            die(verb, "%s: this run is inside a helper whose %s is absent, so its grants cannot be read; "
                      "nothing written; %s" % (named, LANE_WRITES_VAR, REPORT_GAP))
        return None
    raw = os.environ[LANE_WRITES_VAR]
    roots = [part for part in raw.split(os.pathsep) if part.strip()]
    if not roots:
        die(verb, "%s: this run is inside a helper whose %s is empty (%r), so it holds no write grant; "
                  "nothing written; %s" % (named, LANE_WRITES_VAR, raw, REPORT_GAP))
    unreadable = [part for part in roots if part != part.strip() or not os.path.isabs(part)]
    if unreadable:
        die(verb, "%s: this run is inside a helper whose %s cannot be read as a list of absolute paths (%r); "
                  "nothing written; %s" % (named, LANE_WRITES_VAR, raw, REPORT_GAP))
    return [os.path.realpath(part) for part in roots]


def check_lane_grants(verb, *targets):
    """Inside a helper, refuse unless its write grants cover every file this write would change: the file
    itself is granted, or a granted folder holds it. A target that is itself a symbolic link is refused
    whatever it points to: every write here ends in a rename over the target's own path (or, for the log,
    an append through the link), so a link in an ungranted folder that points into a granted one would be
    replaced by a file in the ungranted folder, while its resolved path looked granted. A folder reached
    through a link is followed, since a write through it lands in the folder itself. A granted target with a
    second hard link is refused too: the other name may sit outside the grants, and the log append, which
    writes into the file itself, would change it there as well. Outside a helper, nothing."""
    roots = lane_write_roots(verb, targets)
    if roots is None:
        return
    for target in targets:
        if os.path.islink(target):
            try:
                points = os.readlink(target)
            except OSError as exc:
                points = "unreadable: %s" % (exc.strerror or exc)
            die(verb, "%s is a symbolic link (to %s): inside a helper the writer refuses a linked target, whose "
                      "write would land at the link's own path; the link is left as it is and nothing written"
                % (target, points))
        real = os.path.realpath(os.path.abspath(target))
        if not any(real == root or real.startswith(root.rstrip(os.sep) + os.sep) for root in roots):
            die(verb, "%s is outside this helper's write grants (%s); nothing written; %s"
                % (target, os.environ[LANE_WRITES_VAR], REPORT_GAP))
        try:
            links = os.stat(target).st_nlink
        except (FileNotFoundError, NotADirectoryError):
            links = 1                       # no file there yet, so no other name for it either
        except OSError as exc:
            die(verb, "%s: inside a helper the writer cannot read this target's link count (%s); nothing written"
                % (target, exc.strerror or exc))
        if links > 1:
            die(verb, "%s has %d hard links: inside a helper the writer refuses a target that another name shares, "
                      "since the write could land in a file the grants do not name; the links are left as they "
                      "are and nothing written" % (target, links))


# ----------------------------------------------------------------------- clock ---------

def clock_now():
    """The wall clock, read once per run so every stamp of one write agrees with the rest."""
    return time.localtime()


def clock_hm(now):
    """The stamp itself: `HH:MM`, zero-padded, local time — the only source of a time here."""
    return time.strftime("%H:%M", now)


def clock_zone(now):
    """The clock's own zone name. `%z` (+0100) stands in where a host reports no name."""
    return time.strftime("%Z", now) or time.strftime("%z", now)


def hour_disagrees(token_hour, clock_hour, clock_minute):
    """Whether a token hour is neither the clock's own nor the previous one under the grace."""
    if token_hour == clock_hour:
        return False
    if clock_minute < GRACE_MINUTES and token_hour == (clock_hour - 1) % HOURS:
        return False
    return True


def cited_times(value, tokens):
    """The positions in `tokens` (the clock tokens of `value`, in reading order) of the times
    attached to a date: each date's own time, directly after it, and the far end of a range
    written from that time. Every other token of the argument is not a citation."""
    starts = {found.start(): number for number, found in enumerate(tokens)}
    cited = set()
    for dated in DATE_TOKEN_RE.finditer(value):
        gap = CITED_GAP_RE.match(value, dated.end())
        own = starts.get(gap.end()) if gap else None
        if own is None:
            continue
        cited.add(own)
        join = RANGE_JOIN_RE.match(value, tokens[own].end())
        far = starts.get(join.end()) if join else None
        if far is not None:
            cited.add(far)
    return cited


def clock_tokens(now, values, stamps=()):
    """Every distinct clock token in the caller's text whose hour disagrees, in reading order.

    Distinct, because one token repeated across two arguments is one mistake and earns one
    line; the order is the order the arguments are listed by the verb that collected them.
    The time attached to a date in the same argument cites that dated moment and is skipped
    (cited_times); every other token is checked. `stamps` are read first and whole, with no
    such skip: a caller's own stamp of the write's time (`register close`'s `closed DATE
    HH:MM`) claims now, so its date excuses nothing."""
    offenders = []
    for value, cited_skip in [(text, False) for text in stamps] + [(text, True) for text in values]:
        if not value:
            continue
        tokens = list(CLOCK_TOKEN_RE.finditer(value))
        cited = cited_times(value, tokens) if cited_skip else set()
        for number, found in enumerate(tokens):
            if number in cited:
                continue                # a citation: `the entry of 2026-09-30 13:54`
            hour = int(found.group(1))
            if hour > HOUR_MAX:
                continue                # 52 of `19:52:29` is not an hour; nor is 99
            if not hour_disagrees(hour, now.tm_hour, now.tm_min):
                continue
            if found.group(0) not in offenders:
                offenders.append(found.group(0))
    return offenders


def warn_clock(now, values, stamps=()):
    """One stderr line per offending token. A warning: a note may cite a past event, so the
    write goes ahead, and stdout keeps the one line a head reads."""
    reading = clock_hm(now)
    for token in clock_tokens(now, values, stamps):
        sys.stderr.write("clock: the note names %s, the clock reads %s\n" % (token, reading))


# --------------------------------------------------------------------- payload ---------

# Detect traces a caller's shell leaves when a double-quoted payload loses a backticked token
# (register entry of 2026-09-10 19:59). An odd backtick count is a code span left open: one
# argument is one wiki line, so a span cannot close in another. The phrase is the unknown-command
# text zsh and bash print ("zsh: command not found: X", "bash: X: command not found"), which
# reaches a payload only when a substitution captured its own stderr; dash prints "X: not found"
# and is not matched, since "not found" alone is ordinary prose. A clean loss (the token and both
# backticks gone) leaves neither trace, and preventing it is the caller's shell discipline.
BACKTICK = "`"
LOST_COMMAND_RE = re.compile(r"command not found", re.IGNORECASE)


def payload_traces(named):
    """(argument, reason) for each trace in the caller's text, in the order the verb lists them."""
    found = []
    for name, value in named:
        if not value:
            continue
        ticks = value.count(BACKTICK)
        if ticks % 2:
            found.append((name, "carries %d backtick%s, an odd count: a code span is left open, "
                                "or a double-quoted shell argument lost a backticked token"
                                % (ticks, "" if ticks == 1 else "s")))
        if LOST_COMMAND_RE.search(value):
            found.append((name, "carries 'command not found': a command substitution ran inside "
                                "a double-quoted shell argument"))
    return found


def warn_payload(named):
    """One stderr line per trace. A warning: the text may mean exactly what it says, so the
    write goes ahead, and stdout keeps the one line a head reads."""
    for name, reason in payload_traces(named):
        sys.stderr.write("payload: %s %s\n" % (name, reason))


def stamped_status(status, date, hm):
    """The `register close` status fact, stamped: `closed DATE HH:MM — …`.

    A caller who already opened with `closed DATE` gets the time inserted after that date
    rather than a second `closed`; one who already carries a time keeps it (the token check
    is what says whether that time agrees with the clock); anything else is prefixed whole."""
    if CLOSED_TIMED_RE.match(status):
        return status
    dated = CLOSED_DATED_RE.match(status)
    if dated:
        return "%s %s%s" % (status[:dated.end()], hm, status[dated.end():])
    return "closed %s %s — %s" % (date, hm, status)


# ------------------------------------------------------- reads, the lock, the check ------

class Snapshot(object):
    """One read of a target: the hash of its bytes, and the text decoded from exactly them."""
    __slots__ = ("path", "sha", "text")

    def __init__(self, path, data):
        self.path = path
        self.sha = hashlib.sha256(data).hexdigest()
        self.text = data.decode("utf-8")


def read_snapshot(verb, path):
    """The register and IDEAS are read whole, once; the log never is."""
    if not os.path.isfile(path):
        die(verb, "no file at %s" % path)
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        die(verb, "cannot read %s: %s" % (path, exc.strerror or exc))
    try:
        return Snapshot(path, data)
    except UnicodeDecodeError:
        die(verb, "%s is not UTF-8" % path)


def take_lock(verb, path):
    """Hold the lock on the target's directory until main() releases it.

    A directory, not a lock file: nothing is created beside the target, and closing the
    descriptor (or the process ending) releases it, so a killed run never leaves it behind.
    The lock is a premise of every checked write: without it two runs of this tool could both
    pass their checks and one replace the other's result, so a platform without flock, a
    directory that cannot be opened or locked, and a lock held past LOCK_WAIT each refuse
    here, before the target is read."""
    if not os.path.isfile(path):
        die(verb, "no file at %s" % path)
    directory = os.path.dirname(os.path.abspath(path))
    if fcntl is None:
        die(verb, "this platform has no flock, so this run cannot keep other runs of this tool out of "
                  "%s while it writes; nothing written" % directory)
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError as exc:
        die(verb, "cannot open %s to lock it (%s); nothing written" % (directory, exc.strerror or exc))
    _LOCKS.append(descriptor)
    deadline = time.monotonic() + LOCK_WAIT
    while True:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                die(verb, "another run of this tool has held the lock on %s for %g s; "
                          "nothing written" % (directory, LOCK_WAIT))
            time.sleep(LOCK_POLL)
        except OSError as exc:
            die(verb, "cannot lock %s (%s), so this run cannot keep other runs of this tool out "
                      "while it writes; nothing written" % (directory, exc.strerror or exc))


def release_locks():
    """Close every lock descriptor this run holds; closing one releases its flock."""
    while _LOCKS:
        try:
            os.close(_LOCKS.pop())
        except OSError:
            pass


def reread(path):
    """The target read again through one descriptor: (its stat at that open, its bytes)."""
    with open(path, "rb") as handle:
        seen = os.fstat(handle.fileno())
        data = handle.read()
    return seen, data


def last_look(path):
    """The target's stat: the last look this tool takes before the caller's rename."""
    return os.stat(path)


def changed_since(snap, premises=()):
    """None when the target still holds the bytes it was composed from and every premise still
    holds, else the reason.

    The re-read and its hash come first, then each premise (a callable that returns None or a
    reason naming its own page); last_look() ends this function, so no work of this tool's own
    falls between it and the caller's rename. What lands after it is not seen (the docstring's
    window)."""
    path = snap.path
    try:
        seen, data = reread(path)
    except FileNotFoundError:
        return "it is gone since this run read it"
    except OSError as exc:
        return "it cannot be read again (%s)" % (exc.strerror or exc)
    now = hashlib.sha256(data).hexdigest()
    if now != snap.sha:
        return ("it changed on disk since this run read it (sha256 %s at the read, %s now)"
                % (snap.sha[:12], now[:12]))
    for premise in premises:
        reason = premise()
        if reason is not None:
            return reason
    try:
        last = last_look(path)
    except FileNotFoundError:
        return "it is gone since this run read it"
    except OSError as exc:
        return "it cannot be looked at again (%s)" % (exc.strerror or exc)
    if ((last.st_ino, last.st_dev, last.st_size, last.st_mtime_ns)
            != (seen.st_ino, seen.st_dev, seen.st_size, seen.st_mtime_ns)):
        return "it changed on disk while this run read it again"
    return None


def atomic_write(verb, snap, text, premises=(), refused=None):
    """Write beside the target, fsync, check, rename: the file is whole or untouched, and a
    change another writer made before the last look is never overwritten (the window aside).

    `premises` are checked inside the check (changed_since). `refused`, when given, is a callable
    that turns the refusal's reason into the error line's text, for a write whose refusal leaves
    something to say (the second write of a close)."""
    path = snap.path
    directory = os.path.dirname(os.path.abspath(path))
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        mode = None
    handle_fd, tmp = tempfile.mkstemp(prefix=".vault-writes-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(handle_fd, "wb") as handle:
            handle.write(text.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        reason = changed_since(snap, premises)
        if reason is None:
            os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)          # a failed write leaves no debris beside the target
        except OSError:
            pass
        raise
    if reason is not None:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        if refused is not None:
            die(verb, refused(reason))
        die(verb, "%s: %s; it is left as the other writer left it and nothing was written; "
                  "re-run the command against the file as it now stands" % (path, reason))
    try:                            # the rename is durable only once the directory is
        dir_fd = os.open(directory, os.O_RDONLY)    # synced; best effort, never fatal
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


def report(verb, path, line, preview, dry_run):
    """The whole of the output of a verb: one line, or the bounded block of a dry run."""
    if not dry_run:
        print("ok %s %s:%d" % (verb, path, line))
        return
    print("dry-run %s %s:%d" % (verb, path, line))
    for item in preview[:PREVIEW_MAX]:
        print("| %s" % item)
    if PREVIEW_MAX < len(preview):
        print("| + %d more lines" % (len(preview) - PREVIEW_MAX))


def line_terminator(line):
    """A file that arrived with CRLF keeps its CR on the line this run edits."""
    return "\r" if line.endswith("\r") else ""


# ------------------------------------------------------------------ log-append ---------

def log_line_count(fd, upto):
    """Newlines in the first `upto` bytes, counted in bounded chunks through the descriptor the
    append writes with — again, never the whole file in memory."""
    total, offset = 0, 0
    while offset < upto:
        chunk = os.pread(fd, min(CHUNK, upto - offset), offset)
        if not chunk:
            break
        total += chunk.count(b"\n")
        offset += len(chunk)
    return total


def log_probe(fd):
    """(size, tail, lines): the log as this run will append to it, read through the open
    descriptor under the lock. The last two bytes decide the separator; the newline count, the
    line the `ok` line reports."""
    size = os.fstat(fd).st_size
    tail = os.pread(fd, min(2, size), max(0, size - 2)) if size else b""
    return size, tail, log_line_count(fd, size)


def log_separator(tail):
    """Whatever it takes for exactly one blank line to sit above the new heading.

    An entry is written ending in a blank line, so a file whose tail is already a blank
    line needs nothing; one ending mid-line needs that line finished first."""
    if not tail:
        return ""                       # an empty log: the heading is line 1
    if tail.endswith(b"\n\n"):
        return ""
    if tail.endswith(b"\n"):
        return "\n"
    return "\n\n"


def log_landed(path, size, data):
    """Where `data` sits in the log at `path` at or after byte `size`: (offset, the file's newline
    count between the probe's end and the offset, the byte just before the offset) or None. Only
    what was appended since the probe is read."""
    with open(path, "rb") as handle:
        handle.seek(size)
        grown = handle.read()
    found = grown.find(data)
    if found < 0:
        return None
    return size + found, grown[:found].count(b"\n"), grown[found - 1:found] if found else b""


def cmd_log_append(args):
    verb = "log-append"
    path = os.path.join(args.vault, LOG_REL)
    check_lane_grants(verb, path)
    if args.action not in ACTIONS:
        die(verb, "--action '%s' is none of: %s" % (args.action, " ".join(ACTIONS)))
    date = check_date(verb, args.date)
    title = check_text(verb, "--title", args.title)
    changed = check_text(verb, "--changed", args.changed)
    conflicts = check_text(verb, "--conflicts", args.conflicts)
    extras = []
    named = [("--title", title), ("--changed", changed), ("--conflicts", conflicts)]
    for raw in args.extra or []:
        check_text(verb, "--extra", raw)
        if ":" not in raw:
            die(verb, "--extra '%s' is not 'Key: value'" % short(raw))
        key, value = raw.split(":", 1)
        key, value = key.strip(), value.strip()
        if not key or not value:
            die(verb, "--extra '%s' needs a key and a value" % short(raw))
        # The bullet and the bold are this verb's own: a key already shaped as one would be
        # wrapped again, `- **- **Key****: …` (register entry of 2026-10-03 00:25), into a log
        # that is never rewritten. Refused before the file is opened, so nothing lands.
        if key.startswith("- ") or "**" in key:
            die(verb, "--extra key '%s' is already shaped as a bullet; pass the bare 'Key: value' "
                "and the verb writes '- **Key**: value'" % short(key))
        extras.append((key, value))
        named.append(("--extra %s" % key, raw))
    if not os.path.isfile(path):
        die(verb, "no file at %s" % path)

    now = clock_now()
    warn_clock(now, [title, changed, conflicts] + [raw for raw in args.extra or []])
    warn_payload(named)
    # The heading shape is a schema surface and stays `## [DATE] ACTION | TITLE`, so the time
    # rides in a bullet instead — first among the extras, where it sits under the heading's
    # own date and does not move when the caller passes more of them.
    extras.insert(0, ("Clock", "%s %s" % (clock_hm(now), clock_zone(now))))

    block = ["## [%s] %s | %s" % (date, args.action, title),
             "- **Changed**: %s" % changed]
    for key, value in extras:
        block.append("- **%s**: %s" % (key, value))
    block.append("- **Conflicts**: %s" % conflicts)

    # The lock, then the open, then the probe through the same descriptor: the tail this run
    # reads and the end it appends at are the same file's, and no run of this tool falls between.
    if not args.dry_run:
        take_lock(verb, path)
    try:
        fd = os.open(path, os.O_RDONLY if args.dry_run else os.O_RDWR | os.O_APPEND)
    except OSError as exc:
        die(verb, "cannot open %s to append (%s); nothing written" % (path, exc.strerror or exc))
    try:
        size, tail, lines = log_probe(fd)
        separator = log_separator(tail)
        payload = (separator + "\n".join(block) + "\n\n").encode("utf-8")
        heading_line = lines + separator.count("\n") + 1
        if args.dry_run:
            report(verb, path, heading_line, block, True)
            return
        written = 0
        while written < len(payload):                   # append only, never a rewrite
            written += os.write(fd, payload[written:])
        os.fsync(fd)
    finally:
        os.close(fd)

    # The read-back: the entry where it landed. Later than the probe's end is another program's
    # append in between, never an overwrite; absent is a log replaced or truncated under the open.
    try:
        landed = log_landed(path, size, payload)
    except OSError as exc:
        die(verb, "%s: the entry was written but the log cannot be read back (%s); check its tail "
                  "before any re-run" % (path, exc.strerror or exc))
    if landed is None:
        die(verb, "%s: the entry is not in the log as it now stands (the log was replaced or "
                  "truncated after this run opened it); re-run the command" % path)
    offset, before, previous = landed
    if offset != size and previous != b"\n":
        # Another program's append ended mid-line, so this entry's separator, chosen for the tail
        # this run read, glues the heading to their last line. The entry is in the append-only log:
        # a re-run would add a second copy, so the fix is a correction entry, never a re-run.
        real = lines + before + 1
        die(verb, "%s: the entry landed but malformed: another writer appended %d bytes between this run's "
                  "probe and its write, ending mid-line, so the heading is glued to their line %d; append a "
                  "correction entry, never a re-run of this command" % (path, offset - size, real))
    if offset != size:
        real = lines + before + separator.count("\n") + 1
        note("readback", "another writer appended %d bytes between this run's probe and its write; "
                         "the entry landed at line %d, not %d, after their bytes; its separator was "
                         "chosen for the tail this run read" % (offset - size, real, heading_line))
        heading_line = real
    report(verb, path, heading_line, block, False)


# -------------------------------------------------------------------- register ---------

def heading_index(verb, lines, heading):
    """The one line that IS the heading. Not one, not the register this code knows: refuse."""
    hits = [i for i, line in enumerate(lines) if line == heading]
    if len(hits) != 1:
        die(verb, "'%s' is %d lines of the register, not 1" % (heading, len(hits)))
    return hits[0]


def register_anchors(verb, lines):
    """Both section headings, asserted once each and in the order the register keeps them."""
    open_at = heading_index(verb, lines, OPEN_HEAD)
    closed_at = heading_index(verb, lines, CLOSED_HEAD)
    if closed_at < open_at:
        die(verb, "'%s' (line %d) sits above '%s' (line %d)"
            % (CLOSED_HEAD, closed_at + 1, OPEN_HEAD, open_at + 1))
    return open_at, closed_at


def first_body_index(lines, head_at):
    """Where the first entry of a section starts: the blank line under the heading is kept."""
    index = head_at + 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    return index


def entry_end(lines, start, stop):
    """The next heading after an entry's own: the end of its span as the register reads it."""
    index = start + 1
    while index < stop and not ENTRY_END_RE.match(lines[index]):
        index += 1
    return index


def entry_extent(lines, start, stop):
    """(last, cut) for the entry headed at `start`: its own lines are lines[start:last + 1],
    and lines[last + 1:cut] are the blank lines after them, which leave with it on a close.

    Blank lines never end an entry. The first line that is neither blank nor one of its own
    (see the docstring) does, and so does any heading."""
    last, index, body = start, start + 1, 0
    while index < stop:
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if ENTRY_END_RE.match(line):
            break
        own = (OWN_BOLD_RE.match(line) or OWN_INDENTED_RE.match(line)
               or (body == 0 and OWN_FIRST_DATED_RE.match(line)))
        if not own:
            break
        last, body, index = index, body + 1, index + 1
    cut = last + 1
    while cut < stop and not lines[cut].strip():
        cut += 1
    return last, cut


def foreign_line(lines, start, last):
    """(index, why) for the first of an entry's own lines that is another entry's, else None."""
    seen, body, status = set(), 0, None
    for index in range(start + 1, last + 1):
        line = lines[index]
        if not line.strip():
            continue
        if body and FOREIGN_DATED_RE.match(line):
            return index, "a bullet opening with a date below the first, the shape of an entry"
        once = ONCE_FIELD_RE.match(line)
        if once:
            if once.group(1) in seen:
                return index, "a second '%s' field: two entries under one heading" % once.group(1)
            seen.add(once.group(1))
        if STATUS_FIELD_RE.match(line):
            if status is not None:
                return index, "a second 'Status' field: two entries under one heading"
            status = index
        body += 1
    return None


def status_below(lines, last, stop):
    """The index of a Status field under the same heading but past the entry's own lines."""
    end = entry_end(lines, last, stop)
    for index in range(last + 1, end):
        if STATUS_FIELD_RE.match(lines[index]):
            return index
    return None


def entry_structure(verb, lines, start, stop):
    """(last, cut, fields): the entry's own lines (see entry_extent) and the indices of its
    Status fields, refused where its structure cannot be read — another entry inside its own
    lines, or a Status field under the same heading below a line that is not its own. A close
    and an annotation read an entry through this one function, so neither can take an entry
    the other would refuse. A dated note written date-first is the same shape as a one-line
    entry, so it refuses too, and the message says how such a note is written instead."""
    last, cut = entry_extent(lines, start, stop)
    foreign = foreign_line(lines, start, last)
    if foreign:
        die(verb, "the entry '%s' holds another entry at line %d (%s); nothing written; a dated "
                  "note of this entry opens with its kind (Status, Recurrence or Correction), as "
                  "register annotate writes it" % (short(lines[start]), foreign[0] + 1, foreign[1]))
    below = status_below(lines, last, stop)
    if below is not None:
        die(verb, "the entry '%s' carries a '**Status**' field at line %d, below line %d, which is "
                  "not one of its own lines; nothing written" % (short(lines[start]), below + 1, cut + 1))
    fields = [i for i in range(start + 1, last + 1) if STATUS_FIELD_RE.match(lines[i])]
    return last, cut, fields


def left_in_place(lines, cut, stop):
    """The lines a close leaves where they were: from `cut` to the next heading, as (first, count)
    of the non-blank ones, or None when the entry's own lines run to that heading."""
    end = entry_end(lines, cut - 1, stop) if cut < stop else stop
    kept = [i for i in range(cut, end) if lines[i].strip()]
    return (kept[0], len(kept)) if kept else None


def open_entry(verb, lines, open_at, closed_at, match):
    """The one Open heading `--match` names; any other count refuses."""
    hits = [i for i in range(open_at + 1, closed_at)
            if lines[i].startswith("### ") and match in lines[i]]
    if len(hits) != 1:
        die(verb, "'%s' matches %d entry headings under '%s', not 1"
            % (short(match), len(hits), OPEN_HEAD))
    return hits[0]


def unique_stamp(verb, lines, date, hm, closed=()):
    """The stamp `register add` writes: `DATE HH:MM`, or that and a suffix letter when another
    heading already carries it (see the docstring). Refuses where it cannot tell.

    Every heading whose bracket opens with the candidate date and time is read first, closed
    or not, and only then is its complete form checked: one that never closes its bracket, or
    closes it on any form but the bare stamp or one suffix letter, cannot be read."""
    base = "%s %s" % (date, hm)
    taken = {}
    places = [("line %d" % n, line) for n, line in enumerate(lines, 1)]
    places += [("closed page line %d" % n, line) for n, line in enumerate(closed, 1)]
    for where, line in places:
        found = STAMP_OPEN_RE.match(line.rstrip("\r"))
        if not found:
            continue
        opened = found.group(1)
        if not " ".join(opened.split()).startswith(base):
            continue
        closing = opened.find("]")
        if closing < 0:
            die(verb, "%s heads an entry whose stamp opens with %s and never closes its bracket "
                      "([%s), a form this check cannot read; nothing written" % (where, base, short(opened)))
        inner = " ".join(opened[:closing].split())
        rest = inner[len(base):] if inner.startswith(base) else None
        if rest == "":
            suffix = ""
        elif rest is not None and len(rest) == 2 and rest[0] == " " and rest[1] in STAMP_SUFFIXES:
            suffix = rest[1]
        else:
            die(verb, "%s heads an entry [%s], a form of the stamp %s this check cannot read; "
                      "nothing written" % (where, short(inner), base))
        taken[suffix] = taken.get(suffix, 0) + 1
    for suffix in sorted(taken):
        if taken[suffix] > 1:
            stamp = base + (" " + suffix if suffix else "")
            die(verb, "the stamp [%s] already heads %d entries, so it names none of them; no further "
                      "entry is added under %s: retry in the next minute, or give one of those "
                      "headings a suffix by hand" % (stamp, taken[suffix], base))
    for suffix in [""] + list(STAMP_SUFFIXES):
        if suffix not in taken:
            return base + (" " + suffix if suffix else "")
    die(verb, "the stamp %s and every suffix from b to z already head entries; nothing written" % base)


def closed_page_lines(verb, vault):
    """The register's closed page, as lines, for the one-stamp check: an entry swept there keeps its
    stamp, and a pointer that cites the stamp must still find one heading. Absent, no lines; present
    and unreadable, refuse, since the check could not see its stamps. The sweep takes this tool's
    lock on the same folder, so the page cannot change between this read and the write."""
    path = os.path.join(vault, CLOSED_REL)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "rb") as handle:
            return handle.read().decode("utf-8").split("\n")
    except (OSError, UnicodeDecodeError) as exc:
        die(verb, "cannot read the closed page %s (%s), so the stamp check cannot see its stamps; "
                  "nothing written" % (path, exc))


def cmd_register_add(args):
    verb = "register-add"
    path = os.path.join(args.vault, REGISTER_REL)
    check_lane_grants(verb, path)
    date = check_date(verb, args.date)
    surface = check_text(verb, "--surface", args.surface)
    tag = re.search(r"(\(\s*(?:%s|blocking\s*·\s*major\s*·\s*minor)\s*\))\s*\.?\s*$"
                    % "|".join(SEVERITIES), surface, re.I)
    if tag:
        die(verb, "--surface already ends with severity tag %s; use --severity instead; nothing written"
            % tag.group(1))
    symptom = check_text(verb, "--symptom", args.symptom)
    cause = check_text(verb, "--cause", args.cause)
    if args.cause_kind:
        cause = "%s: %s" % (args.cause_kind, cause)
    if args.why_not_fixed_now is None:
        die(verb, "--why-not-fixed-now is missing: an entry parks a defect only for a named "
                  "reason that blocks the fix now (CLAUDE.md §12), so fix it now or name that reason")
    why = check_text(verb, "--why-not-fixed-now", args.why_not_fixed_now)
    status = check_text(verb, "--status", args.status)
    where = check_text(verb, "--where", args.where)
    if args.severity not in SEVERITIES:
        die(verb, "--severity '%s' is none of: %s" % (args.severity, " ".join(SEVERITIES)))

    now = clock_now()
    warn_clock(now, [surface, symptom, cause, why, status, where])

    if not args.dry_run:
        take_lock(verb, path)
    snap = read_snapshot(verb, path)
    lines = snap.text.split("\n")
    open_at, _ = register_anchors(verb, lines)
    stamp = unique_stamp(verb, lines, date, clock_hm(now), closed_page_lines(verb, args.vault))

    block = ["### [%s] %s (%s)" % (stamp, surface, args.severity)]
    if where:
        block.append("- **Where observed**: %s" % where)
    block.append("- **Symptom**: %s" % symptom)
    block.append("- **Suspected cause**: %s" % cause)
    block.append("- **%s**: %s" % (WHY_LABEL, why))
    block.append("- **Status**: %s" % status)

    at = first_body_index(lines, open_at)
    if args.dry_run:
        report(verb, path, at + 1, block, True)
        return
    atomic_write(verb, snap, "\n".join(lines[:at] + block + [""] + lines[at:]))
    report(verb, path, at + 1, block, False)


def cmd_register_close(args):
    verb = "register-close"
    path = os.path.join(args.vault, REGISTER_REL)
    check_lane_grants(verb, path)
    date = check_date(verb, args.date)
    match = check_text(verb, "--match", args.match)
    status = check_text(verb, "--status", args.status)

    now = clock_now()
    # `--match` is a locator, not text this write lands: an entry already headed with a time
    # is addressed by that time, and warning about it would be warning about the register.
    # A caller's own `closed DATE HH:MM` stamp claims the close's time, so it is checked whole
    # even though its time follows a date; the rest of the status is free text as elsewhere.
    own = CLOSED_TIMED_RE.match(status)
    warn_clock(now, [status], stamps=[own.group(0)] if own else [])
    status = stamped_status(status, date, clock_hm(now))

    if not args.dry_run:
        take_lock(verb, path)
    snap = read_snapshot(verb, path)
    lines = snap.text.split("\n")
    open_at, closed_at = register_anchors(verb, lines)
    start = open_entry(verb, lines, open_at, closed_at, match)
    last, cut, fields = entry_structure(verb, lines, start, closed_at)
    if len(fields) != 1:
        die(verb, "the entry '%s' carries %d '**Status**' lines, not 1"
            % (short(lines[start]), len(fields)))
    block = lines[start:last + 1]
    at_status = fields[0] - start
    tail = line_terminator(block[at_status])
    block[at_status] = "%s *(%s: %s)*%s" % (block[at_status].rstrip(), date, status, tail)

    left = left_in_place(lines, cut, closed_at)
    remainder = lines[:start] + lines[cut:]
    # The anchors move once the span is gone, so they are asserted again on the remainder.
    _, closed_after = register_anchors(verb, remainder)
    at = first_body_index(remainder, closed_after)
    preview = [block[0], block[at_status],
               "moved %d lines to the top of '%s'" % (len(block), CLOSED_HEAD)]
    if left:
        kept = ("line %d and %d more lines below this entry are not its own and stay under '%s'"
                % (left[0] + 1, left[1] - 1, OPEN_HEAD) if left[1] > 1 else
                "line %d below this entry is not its own and stays under '%s'" % (left[0] + 1, OPEN_HEAD))
        note("extent", kept)
        preview.append(kept)
    if args.dry_run:
        report(verb, path, at + 1, preview, True)
        return
    atomic_write(verb, snap, "\n".join(remainder[:at] + block + [""] + remainder[at:]))
    report(verb, path, at + 1, preview, False)


def cmd_register_annotate(args):
    verb = "register-annotate"
    path = os.path.join(args.vault, REGISTER_REL)
    check_lane_grants(verb, path)
    match = check_text(verb, "--match", args.match)
    if args.kind not in NOTE_KINDS:
        die(verb, "--kind '%s' is none of: %s" % (args.kind, " ".join(NOTE_KINDS)))
    text = check_text(verb, "--note", args.note)
    by = check_text(verb, "--by", args.by)
    for name, value in (("--note", text), ("--by", by)):
        if value and STATUS_MARKER in value:
            die(verb, "%s carries the field marker '%s', which the register's lint reads as the "
                      "entry's Status wherever it stands; quote the field without its colon" % (name, STATUS_MARKER))
    date = check_date(verb, args.date)

    now = clock_now()
    warn_clock(now, [text, by])

    if not args.dry_run:
        take_lock(verb, path)
    snap = read_snapshot(verb, path)
    lines = snap.text.split("\n")
    open_at, closed_at = register_anchors(verb, lines)
    start = open_entry(verb, lines, open_at, closed_at, match)
    last, _, fields = entry_structure(verb, lines, start, closed_at)
    if args.kind == "Status":
        # The entry keeps one status (see "One status"): its field is rewritten, nothing appended.
        if len(fields) != 1:
            die(verb, "the entry '%s' carries %d '**Status**' fields, not 1, so there is no one status "
                      "to replace; nothing written" % (short(lines[start]), len(fields)))
        at = fields[0]
        tail = line_terminator(lines[at])
        own = lines[at][:len(lines[at]) - len(tail)]
        cut = own.index(STATUS_MARKER) + len(STATUS_MARKER)
        stamp = "set %s %s %s%s" % (date, clock_hm(now), clock_zone(now), " by %s" % by if by else "")
        edited = "%s %s (%s)%s" % (own[:cut], text, stamp, tail)
        note("replaced", "the Status of '%s' read: %s" % (short(lines[start]), short(own[cut:].strip())))
        preview = [short(lines[start]), edited.rstrip("\r")]
        if args.dry_run:
            report(verb, path, at + 1, preview, True)
            return
        atomic_write(verb, snap, "\n".join(lines[:at] + [edited] + lines[at + 1:]))
        report(verb, path, at + 1, preview, False)
        return
    tail = line_terminator(lines[last])
    added = "- **%s %s %s %s%s:** %s%s" % (args.kind, date, clock_hm(now), clock_zone(now),
                                          " (%s)" % by if by else "", text, tail)
    at = last + 1
    preview = [short(lines[start]), added.rstrip("\r")]
    if args.dry_run:
        report(verb, path, at + 1, preview, True)
        return
    atomic_write(verb, snap, "\n".join(lines[:at] + [added] + lines[at:]))
    report(verb, path, at + 1, preview, False)


# ----------------------------------------------------------------------- ideas ---------

def cmd_ideas_annotate(args):
    verb = "ideas-annotate"
    path = args.file
    check_lane_grants(verb, path)
    if not ITEM_RE.match(args.item):
        die(verb, "--item '%s' is not a number" % short(args.item))
    text = check_text(verb, "--note", args.note)
    date = check_date(verb, args.date)

    now = clock_now()
    warn_clock(now, [text])

    if not args.dry_run:
        take_lock(verb, path)
    snap = read_snapshot(verb, path)
    lines = snap.text.split("\n")
    marker = "- **%s%s**" % (NUMERO, args.item)
    hits = [i for i, line in enumerate(lines) if line.startswith(marker)]
    if len(hits) != 1:
        die(verb, "'%s' begins %d lines of %s, not 1" % (marker, len(hits), path))
    at = hits[0]
    tail = line_terminator(lines[at])
    # The note shape IDEAS.md's own HOW TO USE comment prescribes — a one-line `(agent)`
    # annotation appended to the bullet — with the clock's time beside the date.
    lines[at] = "%s *(agent %s %s: %s)*%s" % (lines[at].rstrip(), date, clock_hm(now), text, tail)

    preview = [short(lines[at])]
    if args.dry_run:
        report(verb, path, at + 1, preview, True)
        return
    atomic_write(verb, snap, "\n".join(lines))
    report(verb, path, at + 1, preview, False)


# --------------------------------------------------------------------- decided ---------

BOLD_ID_RE = re.compile(r"\*\*(DW-[0-9]{8}-[0-9]+)\*\*")
# A status clause as status_clause writes one, and as the page's hand-written ones open: of the
# 116 status clauses on the open page's lines (21 November 2026), 97 carry a time and 19 do not.
STATUS_CLAUSE_RE = re.compile(r"^status \d{1,2} (?:%s) \d{4}\b" % "|".join(MONTHS))
NOTICE_MAX = 3                          # a notice names at most this many lines, then a count


def long_date(iso):
    """`12 November 2026`, the day unpadded, as the decided-work pages write a date."""
    day = datetime.date.fromisoformat(iso)
    return "%d %s %d" % (day.day, MONTHS[day.month - 1], day.year)


def clock_date(now):
    """The clock's own date, from the same reading as its time."""
    return time.strftime("%Y-%m-%d", now)


def check_field(verb, name, value):
    """One field of a decided-work line: one line, not blank, and neither the field separator
    nor the bold marker, either of which would make another field or another identity."""
    value = check_text(verb, name, value)
    if value is None:
        return None
    if FIELD_SEP in value:
        die(verb, "%s carries the field separator ' · ', which would make another field of the "
                  "line; nothing written" % name)
    # At a value's edge the separator needs only the space the template puts beside it to become
    # one (`--by 'x ·'` writes `recorded by x · at …`), so a value may not start or end with it.
    if value.strip().startswith(FIELD_SEP.strip()) or value.strip().endswith(FIELD_SEP.strip()):
        die(verb, "%s starts or ends with the field separator '%s', which the line around it would make "
                  "another field; nothing written" % (name, FIELD_SEP.strip()))
    if BOLD in value:
        die(verb, "%s carries '**', which could forge a bold id on the line; nothing written" % name)
    return value


def check_fields(verb, line, want, what):
    """The composed line has exactly the fields its template gives it: the last guard against an
    argument that made another field however it was spelled."""
    got = len(line.rstrip("\r").split(FIELD_SEP))
    if got != want:
        die(verb, "the %s would have %d fields, not the %d its template gives it: an argument made another "
                  "field; nothing written" % (what, got, want))


def check_id(verb, value):
    """An id as the page writes one: DW-YYYYMMDD-n, n a positive integer with no leading zero."""
    if not DW_ID_RE.match(value or ""):
        die(verb, "--id '%s' is not DW-YYYYMMDD-n" % short(value or ""))
    return value


def state_kind(state):
    """Which of the page's states `state` is written as, or None."""
    for kind, pattern in STATE_NEW_RE.items():
        if pattern.match(state):
            return kind
    return None


def check_state(verb, value, section=None):
    """A state the page lists; with `section`, one that the section admits. A line moves under
    Later only on his quoted word, which is a move, never a state edit, so a To build line takes
    no `later:` state and a Later line takes nothing else."""
    state = check_field(verb, "--state", value)
    kind = state_kind(state)
    if kind is None:
        die(verb, "--state '%s' is none of the page's states: 'to build' (or 'to build: REASON'), "
                  "'in RUN, item K', 'blocked: REASON', 'elsewhere: HOLDER (WORD OR RULE)', and under "
                  "Later only 'later: TRIGGER (\"HIS WORDS\", TIME AND PLACE)'" % short(state))
    if section == "to build" and kind == "later":
        die(verb, "--state '%s' is a Later state: a line goes under '%s' only on his quoted word, and "
                  "this line stands under '%s'; nothing written" % (short(state), LATER_HEAD, TO_BUILD_HEAD))
    if section == "later" and kind != "later":
        die(verb, "--state '%s' is not a Later state, and the line stands under '%s': moving it back "
                  "is not a state edit; nothing written" % (short(state), LATER_HEAD))
    return state


def decided_scan(values):
    """The text the clock check reads in a decided verb: a time with seconds is a citation."""
    return [SECONDS_CITE_RE.sub(" ", value) if value else value for value in values]


def read_text(path):
    """A page read again whole, for a premise or a read-back."""
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8")


def read_lines_quiet(path):
    """A page's lines for a message only, or None when it cannot be read."""
    try:
        return read_text(path).split("\n")
    except (OSError, UnicodeDecodeError):
        return None


def heading_once(verb, lines, heading, name):
    """The one line that IS the heading; any other count refuses."""
    hits = [i for i, line in enumerate(lines) if line == heading]
    if len(hits) != 1:
        die(verb, "'%s' is %d lines of %s, not 1; nothing written" % (heading, len(hits), name))
    return hits[0]


def open_structure(verb, lines, path):
    """(To build, Later on purpose, How this page works): each heading once, in that order, and
    no other heading between the first and the last."""
    name = os.path.basename(path)
    to_at = heading_once(verb, lines, TO_BUILD_HEAD, name)
    later_at = heading_once(verb, lines, LATER_HEAD, name)
    how_at = heading_once(verb, lines, HOW_HEAD, name)
    if not to_at < later_at < how_at:
        die(verb, "the headings of %s are out of order ('%s' line %d, '%s' line %d, '%s' line %d); "
                  "nothing written" % (name, TO_BUILD_HEAD, to_at + 1, LATER_HEAD, later_at + 1,
                                       HOW_HEAD, how_at + 1))
    for index in range(to_at + 1, how_at):
        if index != later_at and ENTRY_END_RE.match(lines[index]):
            die(verb, "line %d of %s is a heading inside the open range ('%s'); nothing written"
                % (index + 1, name, short(lines[index])))
    return to_at, later_at, how_at


def done_structure(verb, lines, path):
    """`## Closed` once, and the closed page's last heading: a closed line appended at the end of
    the page lands under it."""
    name = os.path.basename(path)
    closed_at = heading_once(verb, lines, DONE_HEAD, name)
    for index in range(closed_at + 1, len(lines)):
        if ENTRY_END_RE.match(lines[index]):
            die(verb, "line %d of %s is a heading below '%s', which must be the page's last heading; "
                      "nothing written" % (index + 1, name, DONE_HEAD))
    return closed_at


def bold_lines(lines, ident):
    """Every line carrying `**ident**`: the Closing rule's `grep -c -F` count, as indices."""
    marker = BOLD + ident + BOLD
    return [i for i, line in enumerate(lines) if marker in line]


def duplicate_ids(lines):
    """The ids carried in bold by two or more lines of a page, sorted."""
    counts = {}
    for line in lines:
        for ident in set(BOLD_ID_RE.findall(line)):
            counts[ident] = counts.get(ident, 0) + 1
    return sorted(ident for ident, count in counts.items() if count > 1)


def highest_n(texts, stamp):
    """The highest n of any `DW-<stamp>-<n>` in the texts, bold or cited; 0 when none."""
    found = [int(m.group(2)) for text in texts for m in DW_TOKEN_RE.finditer(text) if m.group(1) == stamp]
    return max(found) if found else 0


def open_line(verb, lines, ident, rng, done_lines):
    """(index, section) of the one line for `ident` in the open range; any other count, shape or
    place refuses, and an id absent from the open page names its closed copy when there is one."""
    to_at, later_at, how_at = rng
    hits = bold_lines(lines, ident)
    if not hits:
        closed = bold_lines(done_lines, ident) if done_lines is not None else []
        where = ": it is closed at %s:%d" % (os.path.basename(DONE_REL), closed[0] + 1) if closed else ""
        die(verb, "%s is on no line of the open page%s; nothing written" % (ident, where))
    if len(hits) > 1:
        die(verb, "%s is carried by %d lines of the open page (lines %s): two identities, a repair under "
                  "the page's Malformed rule; nothing written"
            % (ident, len(hits), ", ".join(str(i + 1) for i in hits)))
    at = hits[0]
    if not lines[at].startswith(OPEN_BOX + BOLD + ident + BOLD + FIELD_SEP):
        die(verb, "line %d carries %s but is not its open line ('%s'); nothing written"
            % (at + 1, ident, short(lines[at])))
    if not to_at < at < how_at:
        die(verb, "the line for %s (line %d) stands outside the open range between '%s' and '%s': "
                  "misplaced, for the pre-flight read to move first; nothing written"
            % (ident, at + 1, TO_BUILD_HEAD, HOW_HEAD))
    return at, ("to build" if at < later_at else "later")


def status_clause(now, by, text):
    """` · status D Month YYYY, HH:MM ZONE (BY): TEXT`, date and time from one clock reading."""
    return "%sstatus %s, %s %s (%s): %s" % (FIELD_SEP, long_date(clock_date(now)), clock_hm(now),
                                           clock_zone(now), by, text)


def one_status(fields, clause):
    """The line's fields with every status clause removed and `clause` appended (see "One
    status"), the clauses removed, and the other fields that stood after the first of them. A
    status clause stands after the `recorded by` field, or after the fourth field where a line has
    none, and opens `status D Month YYYY`."""
    recorded = [i for i, field in enumerate(fields) if field.startswith("recorded by ")]
    first = recorded[0] + 1 if recorded else 4
    gone = [field for field in fields[first:] if STATUS_CLAUSE_RE.match(field)]
    kept = fields[:first] + [field for field in fields[first:] if not STATUS_CLAUSE_RE.match(field)]
    at = [i for i in range(first, len(fields)) if STATUS_CLAUSE_RE.match(fields[i])]
    amid = [field for field in fields[at[0]:] if not STATUS_CLAUSE_RE.match(field)] if at else []
    return kept + [clause[len(FIELD_SEP):]], gone, amid


def note_replaced(ident, gone, amid):
    if gone:
        note("replaced", "%s held %d status clause%s, now one: %s" % (
            ident, len(gone), "" if len(gone) == 1 else "s", " | ".join(short(g) for g in gone)))
    # Kept, the safe direction: such a field may be part of a status or a record of its own.
    for field in amid:
        note("kept", "%s: a field among its status clauses opens no `status D Month YYYY` and stays, "
                     "before the new clause: %s" % (ident, short(field)))


def remove_line(lines, at):
    """The lines without lines[at]; when that leaves two blank lines together, one goes too, so
    an emptied section keeps one blank line before its next heading."""
    out = lines[:at] + lines[at + 1:]
    if 0 < at < len(out) and not out[at - 1].strip() and not out[at].strip():
        del out[at]
    return out


def read_back(verb, path):
    """The page as it stands after the write; unreadable, the error says the write landed."""
    try:
        return read_text(path).split("\n")
    except (OSError, UnicodeDecodeError) as exc:
        die(verb, "%s: the write landed, but the page cannot be read back (%s); check it" % (path, exc))


def back_failed(verb, path, problems):
    die(verb, "%s: the write landed, but the read-back found %s; check the page against its rule"
        % (path, "; ".join(problems)))


def back_moved(path, lines, text):
    """One stderr line when the page holds other bytes than this write left, its checks holding."""
    if "\n".join(lines) != text:
        note("readback", "%s changed again after this write (another writer); the read-back checks "
                         "hold" % path)


def premise_ids(path, stamp, n):
    """An add's premise on the closed page: no id of its date at or above the one chosen."""
    def check():
        try:
            text = read_text(path)
        except FileNotFoundError:
            return "its premise %s is gone since this run read it" % path
        except (OSError, UnicodeDecodeError) as exc:
            return "its premise %s cannot be read again (%s)" % (path, exc)
        top = highest_n([text], stamp)
        if top >= n:
            return ("its premise %s now carries DW-%s-%d, at or above the id this run chose (DW-%s-%d); "
                    "nothing was written: a fresh read and a fresh id choice" % (path, stamp, top, stamp, n))
        return None
    return check


def premise_identity(path, ident, line):
    """A close's first premise: the open page still carries the line for `ident` as read, once."""
    def check():
        try:
            lines = read_text(path).split("\n")
        except (OSError, UnicodeDecodeError) as exc:
            return "its premise %s cannot be read again (%s)" % (path, exc)
        if [other for other in lines if BOLD + ident + BOLD in other] != [line]:
            return ("its premise %s no longer carries the line for %s once, as this run read it; nothing "
                    "was written" % (path, ident))
        return None
    return check


def premise_line_once(path, line, what):
    """A premise that a page carries `line` exactly once (the closed line, for the open write)."""
    def check():
        try:
            count = read_text(path).split("\n").count(line)
        except (OSError, UnicodeDecodeError) as exc:
            return "its premise %s cannot be read again (%s)" % (path, exc)
        if count != 1:
            return "its premise %s carries %s %d times now, not once" % (path, what, count)
        return None
    return check


def cmd_decided_add(args):
    verb = "decided-add"
    path = os.path.join(args.vault, DECIDED_REL)
    done = os.path.join(args.vault, DONE_REL)
    check_lane_grants(verb, path)            # the closed page is read for its ids, never written
    date = check_date(verb, args.date)
    work = check_field(verb, "--work", args.work)
    locator = check_field(verb, "--locator", args.locator)
    state = check_state(verb, args.state, "to build")
    homes = [check_field(verb, "--home", home) for home in args.home or []]
    by = check_field(verb, "--by", args.by)
    now = clock_now()
    today = clock_date(now)
    if date > today:
        die(verb, "--date %s is after the clock's date, %s: a decision is dated when it was given; "
                  "nothing written" % (date, today))
    # `--locator` cites his words and their time, so it is not scanned for a clock slip.
    warn_clock(now, decided_scan([work, state] + homes + [by]))
    warn_payload([("--work", work), ("--locator", locator), ("--state", state), ("--by", by)]
                 + [("--home", home) for home in homes])

    if not args.dry_run:
        take_lock(verb, path)
    snap = read_snapshot(verb, path)
    done_snap = read_snapshot(verb, done)
    lines = snap.text.split("\n")
    done_lines = done_snap.text.split("\n")
    rng = open_structure(verb, lines, path)
    to_at, later_at = rng[0], rng[1]
    stamp = date.replace("-", "")
    n = highest_n([snap.text, done_snap.text], stamp) + 1
    ident = "DW-%s-%d" % (stamp, n)
    recorded = "recorded by %s at %s %s%s" % (by, clock_hm(now), clock_zone(now),
                                              "" if today == date else " on " + long_date(today))
    line = FIELD_SEP.join([OPEN_BOX + BOLD + ident + BOLD, work,
                           "decided %s (%s)" % (long_date(date), locator), state] + homes + [recorded])
    check_fields(verb, line, 5 + len(homes), "new line")

    dupes = duplicate_ids(lines)
    for twice in dupes:
        note("malformed", "%s is carried by %d lines of %s, a repair under the page's Malformed rule; "
                          "this add goes ahead" % (twice, len(bold_lines(lines, twice)), os.path.basename(path)))
    quoted = QUOTED_RE.search(locator)
    if quoted:
        seen = [(page, index) for page, page_lines in ((path, lines), (done, done_lines))
                for index, other in enumerate(page_lines) if quoted.group(1) in other]
        for page, index in seen[:NOTICE_MAX]:
            note("duplicate", "his words \"%s\" already stand on %s:%d: if this is the same decision and "
                              "work, add this locator to that line instead; this add goes ahead"
                 % (short(quoted.group(1)), os.path.basename(page), index + 1))
        if len(seen) > NOTICE_MAX:
            note("duplicate", "and on %d more lines" % (len(seen) - NOTICE_MAX))

    # The anchor: the span from the heading through its first content line (the next heading when
    # the section is empty), asserted once in the file.
    first = first_body_index(lines, to_at)
    span = "\n".join(lines[to_at:first + 1]) + "\n"
    found = ("\n" + snap.text).count("\n" + span)
    if found != 1:
        die(verb, "the anchor span from '%s' through line %d occurs %d times in %s, not 1; nothing written"
            % (TO_BUILD_HEAD, first + 1, found, os.path.basename(path)))
    insert = [line, ""] if first == later_at else [line]
    text = "\n".join(lines[:first] + insert + lines[first:])
    if args.dry_run:
        report(verb, path, first + 1, [line], True)
        return
    atomic_write(verb, snap, text, premises=[premise_ids(done, stamp, n)])

    back = read_back(verb, path)
    problems = []
    if back.count(line) != 1:
        problems.append("the new line %d times, not once" % back.count(line))
    elif back.count(TO_BUILD_HEAD) != 1 or first_body_index(back, back.index(TO_BUILD_HEAD)) != back.index(line):
        problems.append("the new line not first under '%s'" % TO_BUILD_HEAD)
    if len(bold_lines(back, ident)) != 1:
        problems.append("%s on %d lines" % (ident, len(bold_lines(back, ident))))
    if duplicate_ids(back) != dupes:
        problems.append("ids on two lines %s, where this run read %s" % (duplicate_ids(back) or "none", dupes or "none"))
    done_back = read_lines_quiet(done)
    if done_back is None or bold_lines(done_back, ident):
        problems.append("%s on the closed page, or the closed page unreadable" % ident)
    if problems:
        back_failed(verb, path, problems)
    back_moved(path, back, text)
    print("ok %s %s:%d %s" % (verb, path, back.index(line) + 1, ident))


def cmd_decided_status(args):
    verb = "decided-status"
    path = os.path.join(args.vault, DECIDED_REL)
    check_lane_grants(verb, path)
    ident = check_id(verb, args.id)
    text_note = check_field(verb, "--note", args.note)
    by = check_field(verb, "--by", args.by)
    now = clock_now()
    warn_clock(now, decided_scan([text_note, by]))
    warn_payload([("--note", text_note), ("--by", by)])

    if not args.dry_run:
        take_lock(verb, path)
    snap = read_snapshot(verb, path)
    lines = snap.text.split("\n")
    rng = open_structure(verb, lines, path)
    at, _ = open_line(verb, lines, ident, rng, read_lines_quiet(os.path.join(args.vault, DONE_REL)))
    clause = status_clause(now, by, text_note)
    # The line keeps its own terminator: a CR closing it stays its last byte, never mid-line.
    tail = line_terminator(lines[at])
    own = lines[at][:len(lines[at]) - len(tail)]
    fields, gone, amid = one_status(own.split(FIELD_SEP), clause)
    edited = FIELD_SEP.join(fields) + tail
    check_fields(verb, edited, len(fields), "edited line")
    note_replaced(ident, gone, amid)
    if args.dry_run:
        report(verb, path, at + 1, [short(lines[at]), clause.lstrip(" ·")], True)
        return
    text = "\n".join(lines[:at] + [edited] + lines[at + 1:])
    atomic_write(verb, snap, text)

    back = read_back(verb, path)
    problems = []
    if back.count(edited) != 1:
        problems.append("the edited line %d times, not once" % back.count(edited))
    if len(bold_lines(back, ident)) != 1:
        problems.append("%s on %d lines" % (ident, len(bold_lines(back, ident))))
    if problems:
        back_failed(verb, path, problems)
    back_moved(path, back, text)
    report(verb, path, back.index(edited) + 1, [], False)


def cmd_decided_state(args):
    verb = "decided-state"
    path = os.path.join(args.vault, DECIDED_REL)
    check_lane_grants(verb, path)
    ident = check_id(verb, args.id)
    check_state(verb, args.state)
    text_note = check_field(verb, "--note", args.note)
    by = check_field(verb, "--by", args.by)
    now = clock_now()
    warn_clock(now, decided_scan([args.state, text_note, by]))
    warn_payload([("--state", args.state), ("--note", text_note), ("--by", by)])

    if not args.dry_run:
        take_lock(verb, path)
    snap = read_snapshot(verb, path)
    lines = snap.text.split("\n")
    rng = open_structure(verb, lines, path)
    at, section = open_line(verb, lines, ident, rng, read_lines_quiet(os.path.join(args.vault, DONE_REL)))
    tail = line_terminator(lines[at])           # the line keeps its own terminator
    fields = lines[at][:len(lines[at]) - len(tail)].split(FIELD_SEP)
    old = fields[3] if len(fields) > 3 else ""
    if not STATE_READ_RE.match(old):
        die(verb, "field 4 of line %d reads '%s', not a state the page lists, so this verb cannot tell "
                  "what it replaces: a repair by hand under the page's Malformed rule; nothing written"
            % (at + 1, short(old)))
    state = check_state(verb, args.state, section)
    if state == old:
        die(verb, "the state of %s already reads '%s'; nothing written" % (ident, short(old)))
    fields[3] = state
    fields, gone, amid = one_status(fields, status_clause(now, by, text_note))
    edited = FIELD_SEP.join(fields) + tail
    check_fields(verb, edited, len(fields), "edited line")
    note_replaced(ident, gone, amid)
    if args.dry_run:
        report(verb, path, at + 1, ["state: %s" % state, "earlier: %s" % old], True)
        return
    text = "\n".join(lines[:at] + [edited] + lines[at + 1:])
    atomic_write(verb, snap, text)

    back = read_back(verb, path)
    problems = []
    if back.count(edited) != 1:
        problems.append("the edited line %d times, not once" % back.count(edited))
    if len(bold_lines(back, ident)) != 1:
        problems.append("%s on %d lines" % (ident, len(bold_lines(back, ident))))
    if problems:
        back_failed(verb, path, problems)
    back_moved(path, back, text)
    report(verb, path, back.index(edited) + 1, [], False)


def cmd_decided_close(args):
    verb = "decided-close"
    path = os.path.join(args.vault, DECIDED_REL)
    done = os.path.join(args.vault, DONE_REL)
    check_lane_grants(verb, path, done)      # a close writes both pages
    ident = check_id(verb, args.id)
    kind = args.kind
    evidence = check_field(verb, "--evidence", args.evidence)
    by = check_field(verb, "--by", args.by)
    if kind == "dropped" and not DROPPED_EVIDENCE_RE.match(evidence):
        die(verb, "a dropped line's --evidence is his words and where they are: '\"HIS WORDS\" (TIME AND "
                  "PLACE)', as the Closing rule writes it; nothing written")
    now = clock_now()
    warn_clock(now, decided_scan([evidence, by]))
    warn_payload([("--evidence", evidence), ("--by", by)])

    # Both pages sit in one folder, so the one lock covers both writes.
    if not args.dry_run:
        take_lock(verb, path)
    snap = read_snapshot(verb, path)
    done_snap = read_snapshot(verb, done)
    lines = snap.text.split("\n")
    done_lines = done_snap.text.split("\n")
    rng = open_structure(verb, lines, path)
    done_structure(verb, done_lines, done)
    at, _ = open_line(verb, lines, ident, rng, done_lines)
    # The line keeps its own terminator: the closed copy is the same line moved, so a CR closing the
    # open line closes the closed one, and none is written mid-line.
    tail = line_terminator(lines[at])
    body = lines[at][len(OPEN_BOX):len(lines[at]) - len(tail)]
    box = CLOSE_BOX[kind]
    head = "- %s %s%s" % (box, body, FIELD_SEP)
    closed_line = "%s%s %s: %s (closed %s %s by %s)%s" % (head, kind, long_date(clock_date(now)), evidence,
                                                         clock_hm(now), clock_zone(now), by, tail)
    check_fields(verb, closed_line, len(body.split(FIELD_SEP)) + 1, "closed line")
    open_text = "\n".join(remove_line(lines, at))
    hits = bold_lines(done_lines, ident)
    done_name = os.path.basename(done)
    if len(hits) > 1:
        die(verb, "%s is carried by %d lines of %s (lines %s): a repair by the Closing rule; nothing written"
            % (ident, len(hits), done_name, ", ".join(str(i + 1) for i in hits)))

    if hits:
        # Count 1: the closed line must be this line's, closed as this run asks; then only the
        # open copy goes.
        existing = done_lines[hits[0]]
        mine_line = existing[:len(existing) - len(line_terminator(existing))]
        shape = CLOSED_LINE_RE.match(mine_line)
        if not shape or shape.group(2) != ident:
            die(verb, "%s:%d carries %s but is not its closed line ('%s'): a repair by the Closing rule; "
                      "nothing written" % (done_name, hits[0] + 1, ident, short(existing)))
        if shape.group(1) != box:
            die(verb, "%s:%d closes %s with %s, not the %s that --kind %s writes: a repair by the Closing "
                      "rule; nothing written" % (done_name, hits[0] + 1, ident, shape.group(1), box, kind))
        if not mine_line.startswith(head):
            mine = "- %s %s" % (box, body)
            differ = next((i for i, (a, b) in enumerate(zip(mine_line, mine)) if a != b),
                          min(len(mine_line), len(mine)))
            die(verb, "%s:%d holds %s with a body that differs from the open copy at character %d: not the "
                      "same decision and work, a repair by the Closing rule; nothing written"
                % (done_name, hits[0] + 1, ident, differ + 1))
        rest = mine_line[len(head):]
        # The closing clause is the field after the body: KIND DATE: EVIDENCE, the date as the page
        # writes it now or in the ISO form its older closed lines carry, and the tool's own stamp
        # `(closed HH:MM ZONE by WHO)` after the evidence when the tool wrote it.
        clause = re.match(r"^%s (?:[0-9]{1,2} [A-Z][a-z]+ [0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2}): (.*?)"
                          r"(?: \(closed [0-9]{2}:[0-9]{2} [^ ()]+ by [^()]*\))?$" % kind, rest.split(FIELD_SEP)[0])
        if not clause:
            die(verb, "%s:%d closes %s with '%s', not '%s DATE: …' as --kind asks: a repair by the Closing "
                      "rule; nothing written" % (done_name, hits[0] + 1, ident, short(rest), kind))
        # The Closing rule's count 1 confirms "the same decision, work and closing evidence": other
        # evidence on the closed line is not the same close, so it is a repair, never a silent keep.
        if clause.group(1) != evidence:
            die(verb, "%s:%d closes %s with the evidence '%s', not this run's '%s': not the same closing "
                      "evidence, a repair by the Closing rule; nothing written"
                % (done_name, hits[0] + 1, ident, short(clause.group(1)), short(evidence)))
        if args.dry_run:
            report(verb, path, at + 1, ["confirmed: %s:%d" % (done_name, hits[0] + 1),
                                        "removes the open copy, line %d" % (at + 1)], True)
            return
        atomic_write(verb, snap, open_text,
                     premises=[premise_line_once(done, existing, "the closed line for %s" % ident)])
        landed = existing
    else:
        # Count 0: append the closed line, then remove the open copy.
        base = done_snap.text
        done_text = base + ("" if not base or base.endswith("\n") else "\n") + closed_line + "\n"
        if args.dry_run:
            report(verb, done, done_text.split("\n").index(closed_line) + 1,
                   [short(closed_line), "removes the open copy, %s:%d" % (os.path.basename(path), at + 1)], True)
            return
        atomic_write(verb, done_snap, done_text, premises=[premise_identity(path, ident, lines[at])])
        landed_at = done_text.split("\n").index(closed_line) + 1

        def half(reason):
            return ("%s: the closed line landed at %s:%d, but %s, so the open copy stays at %s:%d. Re-run the "
                    "same command: while the open line stands as this run read it, the re-run confirms the "
                    "closed line and removes only the open copy; if the open line itself has changed since "
                    "(a status added, say), the re-run refuses as a repair by the Closing rule, and the two "
                    "lines are reconciled by hand"
                    % (path, done, landed_at, reason, path, at + 1))

        atomic_write(verb, snap, open_text,
                     premises=[premise_line_once(done, closed_line, "the closed line for %s" % ident)],
                     refused=half)
        landed = closed_line

    open_back = read_back(verb, path)
    done_back = read_back(verb, done)
    problems = []
    if done_back.count(landed) != 1 or len(bold_lines(done_back, ident)) != 1:
        problems.append("%s on %d lines of %s, the closed line %d times"
                        % (ident, len(bold_lines(done_back, ident)), done_name, done_back.count(landed)))
    if bold_lines(open_back, ident):
        problems.append("%s still on the open page (line %d)" % (ident, bold_lines(open_back, ident)[0] + 1))
    if problems:
        back_failed(verb, path, problems)
    back_moved(path, open_back, open_text)
    print("ok %s %s:%d (open copy removed from %s:%d)"
          % (verb, done, done_back.index(landed) + 1, path, at + 1))


DECIDED_VERBS = {"add": cmd_decided_add, "status": cmd_decided_status, "state": cmd_decided_state,
                 "close": cmd_decided_close}


# ----------------------------------------------------------------------- entry ---------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="vault-writes.py",
        description="The hand-composed writes of the vault, one asserted anchor at a time.")
    verbs = parser.add_subparsers(dest="verb", required=True)

    log = verbs.add_parser("log-append", help="append one entry to the wiki log")
    log.add_argument("--vault", required=True, help="the vault root; the path is derived")
    log.add_argument("--action", required=True, help="one of: %s" % " ".join(ACTIONS))
    log.add_argument("--title", required=True)
    log.add_argument("--changed", required=True)
    log.add_argument("--conflicts", required=True)
    log.add_argument("--extra", action="append", metavar="KEY: VALUE",
                     help="a further bullet, between Changed and Conflicts; repeatable; the bare "
                          "key (a key starting '- ' or carrying '**' is refused)")
    log.add_argument("--date", help="YYYY-MM-DD; today when absent")
    log.add_argument("--dry-run", action="store_true", help="print the block, write nothing")

    register = verbs.add_parser("register", help="the framework defect register")
    register_verbs = register.add_subparsers(dest="register_verb", required=True)

    add = register_verbs.add_parser("add", help="a new entry at the top of the Open section")
    add.add_argument("--vault", required=True)
    add.add_argument("--date", required=True, help="the date only, YYYY-MM-DD; the tool stamps the time")
    add.add_argument("--surface", required=True, help="surface — short title")
    add.add_argument("--symptom", required=True)
    add.add_argument("--cause", required=True)
    add.add_argument("--why-not-fixed-now", dest="why_not_fixed_now", metavar="REASON",
                     help="required: the named reason that blocks the fix now")
    add.add_argument("--severity", required=True, help="one of: %s" % " ".join(SEVERITIES))
    add.add_argument("--status", required=True, help="verbatim, the leading 'open — ' too")
    add.add_argument("--where", help="omitted entirely when absent")
    add.add_argument("--cause-kind", dest="cause_kind", choices=CAUSE_KINDS,
                     help="the one word put before the cause: tested or observed; omitted when absent")
    add.add_argument("--dry-run", action="store_true", help="print the block, write nothing")

    close = register_verbs.add_parser("close", help="move one entry to the Closed section")
    close.add_argument("--vault", required=True)
    close.add_argument("--match", required=True, help="text of exactly one Open heading")
    close.add_argument("--date", required=True, help="the date only, YYYY-MM-DD; the tool stamps the time")
    close.add_argument("--status", required=True,
                       help="the text of the dated line; the clock stamps its time")
    close.add_argument("--dry-run", action="store_true", help="print the change, write nothing")

    annotate_entry = register_verbs.add_parser(
        "annotate", help="replace one Open entry's Status, or append one dated note to it")
    annotate_entry.add_argument("--vault", required=True)
    annotate_entry.add_argument("--match", required=True, help="text of exactly one Open heading")
    annotate_entry.add_argument("--kind", required=True, help="one of: %s" % " ".join(NOTE_KINDS))
    annotate_entry.add_argument("--note", required=True)
    annotate_entry.add_argument("--by", help="who writes it; omitted when absent")
    annotate_entry.add_argument("--date", help="YYYY-MM-DD; today when absent")
    annotate_entry.add_argument("--dry-run", action="store_true",
                                help="print the note, write nothing")

    ideas = verbs.add_parser("ideas", help="the scratchpad of the owner")
    ideas_verbs = ideas.add_subparsers(dest="ideas_verb", required=True)
    annotate = ideas_verbs.add_parser("annotate", help="append one agent note to one bullet")
    annotate.add_argument("--file", required=True)
    annotate.add_argument("--item", required=True, metavar="N")
    annotate.add_argument("--note", required=True)
    annotate.add_argument("--date", help="YYYY-MM-DD; today when absent")
    annotate.add_argument("--dry-run", action="store_true",
                          help="print the line, write nothing")

    decided = verbs.add_parser("decided", help="the decided-work pages")
    decided_verbs = decided.add_subparsers(dest="decided_verb", required=True)
    d_add = decided_verbs.add_parser("add", help="a new line under To build, with the next unused id")
    d_add.add_argument("--vault", required=True)
    d_add.add_argument("--date", required=True, help="the decision's date, YYYY-MM-DD")
    d_add.add_argument("--work", required=True, help="the work, in one sentence")
    d_add.add_argument("--locator", required=True,
                       help="where his words are; written inside the decided field's parentheses")
    d_add.add_argument("--state", required=True, help="one of the page's states, never later:")
    d_add.add_argument("--home", action="append", metavar="POINTER",
                       help="a pointer to another home of the work; repeatable, one field each")
    d_add.add_argument("--by", required=True, help="who records the line")
    d_add.add_argument("--dry-run", action="store_true", help="print the line, write nothing")

    d_status = decided_verbs.add_parser("status", help="set one open line's one status clause")
    d_status.add_argument("--vault", required=True)
    d_status.add_argument("--id", required=True, help="DW-YYYYMMDD-n")
    d_status.add_argument("--note", required=True)
    d_status.add_argument("--by", required=True)
    d_status.add_argument("--dry-run", action="store_true", help="print the clause, write nothing")

    d_state = decided_verbs.add_parser("state", help="replace one open line's state and set its status clause")
    d_state.add_argument("--vault", required=True)
    d_state.add_argument("--id", required=True, help="DW-YYYYMMDD-n")
    d_state.add_argument("--state", required=True)
    d_state.add_argument("--note", required=True, help="why the state changes, with its evidence")
    d_state.add_argument("--by", required=True)
    d_state.add_argument("--dry-run", action="store_true", help="print the change, write nothing")

    d_close = decided_verbs.add_parser("close", help="close one open line onto the closed page")
    d_close.add_argument("--vault", required=True)
    d_close.add_argument("--id", required=True, help="DW-YYYYMMDD-n")
    d_close.add_argument("--kind", required=True, choices=sorted(CLOSE_BOX))
    d_close.add_argument("--evidence", required=True,
                         help="what shows it built or retired; for dropped, '\"HIS WORDS\" (TIME AND PLACE)'")
    d_close.add_argument("--by", required=True)
    d_close.add_argument("--dry-run", action="store_true", help="print the change, write nothing")
    return parser


REGISTER_VERBS = {"add": cmd_register_add, "close": cmd_register_close,
                  "annotate": cmd_register_annotate}


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.verb == "log-append":
            cmd_log_append(args)
        elif args.verb == "register":
            REGISTER_VERBS[args.register_verb](args)
        elif args.verb == "decided":
            DECIDED_VERBS[args.decided_verb](args)
        else:
            cmd_ideas_annotate(args)
    finally:
        release_locks()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except OSError as exc:          # a read-only target, a full disk: one line, exit 2
        print("error vault-writes: %s" % exc)
        sys.exit(2)
