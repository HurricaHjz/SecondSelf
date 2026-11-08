# Spawn brief — generic skeleton

Fill EVERY `{{slot}}`; an empty slot is a spawn blocker. Replace the paste marker with the
block from `_inherited.md`, verbatim. Lines starting `<!--` are spawner guidance — delete
before sending. Send the fenced body as the Agent prompt.

```
You are {{AGENT_NAME}} (definition: .claude/agents/{{DEF}}.md), lane {{LANE_ID}} of run
{{RUN_ID}}.

TASK
{{State the task concisely. State the partition explicitly: which question THIS lane answers, and
which adjacent questions belong to other lanes even where files overlap.}}

SCOPE
- Reading list (pre-scoped): {{per slice: `page — why — ~size` (SKILL.md §2b); keep tight —
  open discovery multiplies cost}}
- File whitelist (may create/edit): {{paths | NONE — read-only lane}}
- Link whitelist (may link to): {{pages | n/a}}
- Boundary: anything outside the whitelists is out of scope — return a proposed diff
  instead of an edit, and report off-scope findings without fixing them.
- A lane under /tmp dry-runs a returned diff on a flat copy (no `.claude` path component: the
  fence refuses one there) with `patch -p<depth> --dry-run` run inside the copy, `<depth>` the
  leading components to strip (4 for `a/.claude/skills/<skill>/<file>`).
- Scratch under /tmp goes through Bash: the file tools refuse it unless the head granted
  `/tmp/{{RUN_ID}}-{{LANE_ID}}/` with `--write`.
- A hook you plant in scratch (a git hook, a file watcher) carries a recursion guard: it never
  re-enters what fires it, so a git hook runs no git command in its own repository unless a flag it
  sets first stops the re-entry.

REGISTRIES
wiki/index.md and wiki/log.md are propose-don't-write: return entries as ready-to-apply
diffs. {{Ingest lanes only, under an explicit ingest contract — replace this sentence with
the granted-exception wording in brief-compile.md; never grant to any other lane.}}

GRANTS
{{headless lanes: the read directories, the write scope and any add-on granted beyond the
class row, each with its reason — so a refused path reads as a gap to report, never as a
mistake to work around; every path and command literal, as the fence will see it — no `Let X =`
shorthand and no pasteable placeholder, since a fenced lane copies a shorthand into a shell
variable the fence reads as an ungranted root (eight denials, 2026-09-06) | in-session: "n/a — inherited"}}

DECISIONS
{{the run decisions that bear on this task, and what sibling lanes hold; "none" is a
statement, not an omission. A decision this lane needs and cannot find here is a gap to
report, never one to invent.}}

FOLD
<!-- For a fold, fill the hand-off below. For other tasks, replace its entire body with
"n/a — not a fold", leaving no unused slots. -->
- Earlier report: {{literal path}}.
- Findings to fold: {{each finding, its evidence and overturn condition; label its kind
  depth (missed reasoning) or spec (a gap in the brief or design), beside the critic's
  origin label: made by the last fix, older than the build, or a limit of the approach}}.
  Each overturn condition is quoted verbatim from the critic's report, never paraphrased into a
  weaker test.
- Your product carries no reviewer verdict: no "passed", "approved", "ready" or score from an
  earlier round goes into a file a later blind check reads; dispositions go in your report.
- Held files: {{literal paths and the state to continue from}}.
- Must not change: {{requirements, decisions and accepted behaviour the fold must preserve}}.

VERIFICATION
- {{Builders: list checks the sandbox cannot run, each as command · blocked capability ·
  head's permitted execution context (or missing grant); write "none known" if empty.
  Other roles: omit this bullet.}}
  The head runs each listed check against the same candidate in that context; until then
  it stays unverified. Return new sandbox denials with the command for the same hand-off,
  never as code defects or passes.
- Output gate: {{the assert-nonzero / expected-shape assertion for EVERY stage of the
  lane's work, e.g. "≥N pages, each with §4.1 frontmatter"}} — report each assertion's
  result.
CONTROL+: {{a probe that must hit}} in {{the file that must hold it — a real path, nothing after it}}
Negative control: {{an invented string that must NOT hit / must be caught}}
- {{Write lanes with a link whitelist: name the link-whitelist sweep and its negative control,
  a fake link in a scratch copy of a page, which stays out of any page the lane delivers
  (CLAUDE.md §12, "Tests stay out of formal work") | read-only lanes: "—"}}
- Folds must parse: a count over a run ledger, a spawn record or any JSONL more than one
  writer appends to reads every line with `json.loads` or `jq` before it counts; a key-pattern grep
  is a locator, never a verdict (two writers spell one key two ways).

{{PASTE templates/_inherited.md block}}
{{extra role conduct | —}}

REPORT
{{shape — the definition's report shape unless the task needs more}}
```

<!-- Spawner checks before sending: spawn-record line written (SKILL.md §3 slot 0); all
eight slots present (GRANTS belongs to slot 2's scope, DECISIONS to slot 8 — neither adds a
ninth); no expected answer leaked anywhere; reading list scoped. Control
strings for greps over the CURRENT session's transcript must be generated at probe time
by the lane, never written in the brief — a brief-supplied string matches its own spawn
prompt inside the transcript, so use a fresh nonce or scope the grep to pre-brief lines. -->
