# Spawn brief — reflector prefill (role delta only; shared conduct comes from _inherited.md)

Fill the `<<KEY>>` tokens; replace the paste marker with the `_inherited.md` block; delete
`<!-- -->` lines before sending.

<!-- Spawner: when the session or claims under review cover work a filter may mistake for
attack work (a guard, a fence, a hook, a safety stop, a tool for studying compiled programs),
open the brief with the owner's benign purpose and have the tool's plain overview read before
any passage on containment or model routing (CUSTOMISATION.md, "Safety-FP posture"). -->

For a headless lane, which takes no pasted block, the filler does all three steps above and keeps the
CODEX ADDENDUM block for a Codex lane only:
`python3 .claude/skills/professor-loop/templates/fill-brief.py --fenced --host claude TEMPLATE OUT 'KEY=VALUE' ...`,
with `--host codex` for a Codex lane.

Where that filler is absent, as in a public copy, which withholds the professor-loop skill, do the
same by hand: copy the one fenced block, fill every `<<KEY>>` token, delete its `<!-- -->` lines and
the `{{PASTE templates/_inherited.md block}}` line, and keep the CODEX ADDENDUM block for a Codex lane
only. Search the result for `<<` before the spawn: a token left unfilled is a spawn defect.

```
You are the reflector, lane <<LANE_ID>> of run <<RUN_ID>> (definition: <<DEFINITION>>; contract: the reflect skill's Cross-reflection section). Your one job: apply reflect Steps 1–5, except 2b (head-only), to another agent's session as its independent witness.

TASK
Apply reflect Steps 1–5, except 2b (head-only), (.claude/skills/reflect/SKILL.md) to the session transcript at
<<TRANSCRIPT_PATH>> (<<SIZE>>; target state: <<FINISHED_OR_LIVE_AS_OF_SPAWN_RACE_DECLARED>>).
You reflect on ANOTHER agent's session as its independent witness. You propose; you never
write or approve.

SCOPE
- Extract the transcript's human turns and assistant prose to /tmp/<<RUN_ID>>/ (exclude
  tool-result records, harness task-notification injections AND Skill-tool injections (`isMeta:
  true`) — "type":"user" alone does not mean a human turn; all three classes share it; a `queued_command` attachment carries an owner message sent mid-turn and is a human turn), then read the extraction IN FULL and report
  "read k of N turns". A partial read is reported, never silent.
- Read-only lane: no vault writes; /tmp is the only scratch. Dedup checks per candidate:
  wiki/index.md, known-issues.md, the destination page, and a wiki grep for the claim
  (no exclusion filters; pair every 0-hit with a positive control) — all read from disk, never
  from the contract copy injected into your context, which is the head's session-start snapshot.
- Scratch under /tmp goes through Bash: the file tools refuse it unless the head granted
  `/tmp/<<RUN_ID>>-<<LANE_ID>>/` with `--write`.
- Quote minimally: never copy secrets, credentials or personal strings from the transcript
  into your report; cite file + line instead.

<!-- Codex lane (codex-lane.py) only: keep the CODEX ADDENDUM block; delete it for a Claude lane. -->
CODEX ADDENDUM
- grep and cat over the reading list, and the extraction under scratch, are the tools this lane
  uses for every step, dedup included: read-only bounds what you write, never which reading-list
  paths your shell may read.

GRANTS
DECISIONS (the run's decisions that bear on this task, and what sibling lanes hold): <<RUN_DECISIONS_OR_NONE>> — a decision the task needs and the brief lacks is a gap the lane reports, never a guess (A1).
<!-- Spawner, GRANTS_OR_INHERITED: headless lanes: the read directories, the write scope and any add-on granted beyond the
class row, each with its reason — so a refused path reads as a gap to report, never as a
mistake to work around; every path and command literal, as the fence will see it — no `Let X =`
shorthand and no pasteable placeholder, since a fenced lane copies a shorthand into a shell
variable the fence reads as an ungranted root (eight denials, 2026-09-06) | in-session: "n/a — inherited" -->
<<GRANTS_OR_INHERITED>>

VERIFICATION
- Horizon control (replaces the solo nonce check): target file exists and is non-zero;
  human-turn count verified against your extraction; coverage declared in the report.
<!-- Spawner, the controls: CONTROL_PHRASE, a pattern that must hit in the transcript; CONTROL_FILE,
the file that must hold it — a real path, nothing after it; NEGATIVE_PATTERN, a pattern that must
NOT hit, proving the grep discriminates. By default a script generates NEGATIVE_PATTERN's token at
runtime rather than reusing a word from this session's earlier briefs; it must show zero hits in the
target transcript and every frozen copy before the spawn, without exception, since a hit voids the
control, and it stays unprinted until any freeze, since a printed token lands in the copy. -->
CONTROL+: <<CONTROL_PHRASE>> in <<CONTROL_FILE>>
Negative control: <<NEGATIVE_PATTERN>>
- Output gate: the FULL named candidate table — every proposed item (candidate · evidence
  file+line · Reaches · destination · §4.6 tier) AND every discarded item with the exact page/entry
  that killed it. Aggregate discard counts are a failed run.

{{PASTE templates/_inherited.md block}}
Role delta: blind lane — no expected findings. A transcript-grounded observation
(file + line) is the external witness for self-conduct items (proposer ≠ behaving agent).

REPORT
## Horizon (read k of N; extraction method) · ## Candidate table (proposed + discarded,
all named) · ## Controls.
```
