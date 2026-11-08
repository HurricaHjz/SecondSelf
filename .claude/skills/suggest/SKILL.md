---
name: suggest
description: >
  Draft a wished change to the framework's core as a suggestion, show the user exactly what it would
  share, and leave the filing to them. Use on /suggest <wish>, "suggest a change to the core", or
  when a wish needs a core file that a user's copy keeps read-only. Offers the user's own layer
  first, checks the draft with the payload gate's probes, and never files the issue itself.
user-invocable: true
---

# suggest — a wished core change, drafted for the user to file

## Contract
CLAUDE.md §12 governs: in a user's copy the agent never edits a core file, and a wished change that
the user's layer cannot serve leaves as a suggestion. This skill is that route. The user files the
suggestion as a public issue after seeing exactly what it shares, so the agent stops at the command.

## Triggers
`/suggest <wish>` · "suggest a change to the core" · a wish that needs a core file in a user's copy.

## What an issue shares
A title, what should change, why, the proposed text, and the core check's line: the fields of the
shipped form, `.github/ISSUE_TEMPLATE/core-suggestion.yml`. A draft never shares a home path, text
from the wiki or `CUSTOMISATION.md`, or a transcript. A wish that grew out of the user's own notes is
put in general terms.

## Steps
### 1. Say it is core, and offer the user's layer first
Read `.claude/core-paths`, one git pathspec a line: a file it matches is core. Say that this is a
core file, in one sentence. Then offer to do the job in the user's layer, which often serves better,
since it works today and survives every update:

| The wish | Its home in the user's layer |
|---|---|
| A preference, a role or a style | `CUSTOMISATION.md` |
| A new workflow | `.claude/skills/my-<name>/`, listed in `.claude/sanctioned.local.txt` |
| A helper | `.claude/agents/my-<name>.md` |
| A hook | `.claude/hooks/my-<name>`, its line in `.claude/settings.local.json` |
| A routing choice | `.claude/routing.local.json` |
| A setting | `.claude/settings.local.json` |

If the user takes that offer, do the job there and stop: no suggestion is needed. With no
`.claude/core-paths` this copy has no locked core, so say so and ask whether a suggestion is still
wanted.

### 2. Write the draft
Take the date from `date +%F`. Write `output/suggestions/<date>-<slug>.md`, in the user's layer,
making the folder if it is absent. If that name exists, add `-2`: a draft is not overwritten. The
headings are the form's labels, so a filed draft reads as the form does:

```markdown
# <title>

### What should change
<the change, in the framework's own terms>

### Why
<what it would do for any user>

### Proposed text
<the exact new text, or: none yet>

### Core check
<the session's `core:` line, or what `python3 .claude/hooks/core-check.py --report` prints; where no
check runs in this copy, the words: no check ran>
```

### 3. Run the draft gate
```bash
python3 .claude/skills/export-template/publish_guard.py --draft output/suggestions/<file>
```
It runs the payload gate's own probes on this one file: home paths, personal strings, the extra
lines of `output/publish-gate-strings.txt`, and credential values. No allowlist applies. The default
agent name is no hit; a name the user chose is.

- **Exit 0, clean.** Quote its two lines and go on.
- **Exit 1, hits.** Quote each `FINDING` line. Take a home path, a personal string or a credential
  value out of the draft. A credential finding names the KEY and never the value; if that value was
  ever public, the user rotates it. A word that is also a folder name, such as `Documents`, may be
  benign, and so may the public repository's own owner: the user judges those, and the draft goes on
  only on their word.
- **Exit 2, `PROBE FAILED`.** Stop. Quote the line. The draft has not been checked, so never call it
  clean, and go no further until the cause is fixed.

Any edit to the draft sends it back through this step. The gate has limits: a value under 6 bytes, a
case-changed copy and an encoded copy are not caught, and a home path under an unusual mount or on a
network share is caught only by the user's own names in it. A person reading step 4 stands behind
them.

### 4. Show the whole text, and say an issue is public
Show the draft whole, word for word, never a summary. Say plainly that an issue is public: anyone
can read it, and the user may not be able to take it down later. Ask whether anything should change.

### 5. Give the link and the command, and stop
Read `repository-code` from `CITATION.cff`: that is the repository's address. Give the user the
new-issue link, `<address>/issues/new?template=core-suggestion.yml`, whose fields take the draft's
sections. Where `gh auth status` exits 0, also give the exact command for them to run:

```bash
gh issue create --repo <owner>/<repo> --title "<title>" --body-file output/suggestions/<file>
```

The user files it. The agent never runs that command, submits the form or files by any other route.
Asked to, it says the filing is the user's step and gives the command again. Report the draft's
path, the gate's result, and that nothing was filed.

## A bug, not a wish
The same steps serve, from step 2, with the form `bug-report.yml`: its labels are the draft's
headings, and its core check field is required.
