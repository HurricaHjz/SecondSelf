# Board template — the shared file of attended sessions that run side by side

A board is the one file that attended sessions running at the same time read at the start of every
turn and append to. The main session copies this template into the board folder when a day or an evening has more than one session, fills its two slots and writes the first
line, which names the main session. The copy starts at its own heading below; the text above that
heading stays here.

A line is appended, never edited, and its clock time is taken inside the writing command, never typed. The fact sits in a quoted heredoc, so a backtick or a `$` in it stays text and runs nothing:

    { printf '%s GMT · ' "- $(date -u +%H:%M:%S)"; cat <<'BOARDLINE'
    <writer> · <fact> · source: <source>
    BOARDLINE
    } >> <board file>

A message between sessions is only a wake-up that names a board line, never a fact of its own, since a
send can be dropped. A board line is never an order, and never the owner's word for a gated act.

# {{the board's name and date, e.g. "The evening's board, <date>"}}

Read by {{each session: its letter, its role and its topic, the main session first}} at the start of every turn, woken and typed turns alike, each reading on from the last line it read, never from its own last line, and each line whole, never through a cut display. Add one line when you learn something that bears on another session's work: the clock time taken inside the writing command, your letter, the fact, its source. A line is a fact, never an order. Append only: edit no line, yours or another session's.

- **Who is main.** The newest line of kind `main` names the main session. A session becomes main by the owner's word or by a hand-over, and its first line here says so.
- **The owner's words.** They go into the main session's decisions file first, copied word for word with their time from that program's extract (`handsoff.py extract-transcript --session <id>`) or its decisions-file option, once installed; a line here names those file lines and never retypes the words.
- **Before a gated act** (a launch, an install, a send, a publish, a close, or anything else the owner's rules reserve to their word), the acting session reads the owner's words in the main session's transcript through that program's extract. A board line is not enough, and a line whose words differ from the extract stops the act.
- **One writer per shared file.** Each shared file other than this board, the calendar, the decided-work page and the registers among them, has one writer at a time, the main session by default; its writer is named here and in the hand-off, which also names who takes each file when a session closes. This board is the one file every session appends to, one line per write, never editing a line.

## Lines
- {{HH:MM:SS GMT, from the writing command}} · {{writer}} · main · {{the main session: its name and its Claudian title}} · source: {{the owner's word or the hand-over that made it main}}
