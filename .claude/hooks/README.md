# Hooks

Small programs Claude Code runs by itself at fixed moments in a session of this vault. `.claude/settings.json` says which runs when.

| Hook | When it runs | What it does |
|---|---|---|
| `calendar-digest.py` | Session start | Shows the calendar's overdue items and those due within seven days, with no model call. |
| `context-watermark.py` | Each prompt | Adds the one-line `context:` reading and appends it to its log. |
| `core-check.py` | A fresh session start | Says in one line whether the core still matches its release. It warns and never blocks. |
| `handsoff-gate.py` | Before any tool, in a hands-off run | Enforces the hard context band of a hands-off run. |
| `head-fence.py` | Before a shell command, in a hands-off run | Holds the run's lead inside its granted folders. |
| `ingest-ledger-check.sh` | Reply end | Warns when an ingest run's ledger is open and stale. |
| `precompact-checkpoint.py` | Before a compaction, and at the session start after one | Writes a checkpoint, then briefs the session from it. |

The `test_*.sh` files are the suites for these hooks, and for the destructive-git guard, which has no file here because it sits as an inline command in the settings file.

In a user's copy, `handsoff-gate.py`, `head-fence.py` and `ingest-ledger-check.sh` are opt-in. `optional-hooks.json` holds them as the kits `hands-off` and `ingest-check`: `bash setup.sh --enable <kit>` adds a kit to `.claude/settings.local.json`, and `bash setup.sh --disable <kit>` takes it out. A user's own hooks go in `.claude/hooks/my-<name>`, with their lines in `.claude/settings.local.json`, and an update leaves both alone.

A vault kept beside a separate clone takes no settings from an update, so no core check runs there.

