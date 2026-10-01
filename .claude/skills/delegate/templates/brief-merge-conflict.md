# Spawn brief — merge conflict prefill

Fill the slots and include the inherited conduct block for an in-session lane.

```
You are wiki-compile (definition: .claude/agents/wiki-compile.md), lane {{LANE_ID}} of run {{RUN_ID}} · model {{model}} · effort {{effort}}.

TASK
Resolve the plan's conflicting targets and the manual targets assigned with them. Read each target once alongside every competing claim and diff. Return one resolved unified diff per target, the canonical-name map and link diffs for source pages that named losing variants. Propose every page change; the head applies it.

DECISIONS
{{the run's decisions, canonical-name decisions already made and unresolved gaps}}

SCOPE
- Read: {{absolute target paths, competing claim objects and diff paths, affected source-page paths, plan file}}.
- File whitelist: {{this lane's absolute diff directory}} and {{run ledger, append only}}.
- Boundary: every wiki page is read-only. No registry edits or raw sorting.

LEDGER AND DIFFS
- Append `lane_open` with `role: conflict`, using the spawn record's lane id and model/effort. All timestamps come from the shell clock at append time. Append `lane_close` with the resolved diff list.
- Record each target's base sha256 prefix and its resolved diff's hash, both the first 16 hex digits used by `source_hash` and de-dup. A create carries the schema's frontmatter, sections and aliases, including acronym and expansion where the source gives both.
- Preserve competing statements when evidence does not settle them; name the unresolved conflict. Never infer missing evidence or raise a confidence tier yourself. Report every proposed confidence lift, including one introduced during resolution.
- Link diffs use the same base and hash duties. The canonical-name map names each losing variant and its surviving target.

VERIFY
Check every diff against its base and every canonical-name mapping against the claims. Include a must-hit control and an absent-pattern control in the report. The head reads each resolved diff and runs `merge_plan.py --vault <vault> --resolved <diff>`; any confidence lift requires the head's full-page read before application. Resolved diffs have no new verify score.

REPORT
Per target: resolved diff path, base, diff_hash, confidence change and evidence; canonical-name map; source link diffs; controls; conflicts and gaps. Nothing outside the whitelist is written.

{{inherited conduct block}}
```
