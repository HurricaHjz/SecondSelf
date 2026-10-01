You are verifier (definition: .claude/agents/verifier.md), lane JUDGE of run {{RUN}}.

TASK
Score the replies of one style re-run, one per line of {{OUT}}/manifest.txt (`tag sid`), against the rubric in {{OUT}}/rubric.md, exactly as it prescribes. Each reply is {{OUT}}/<tag>.full.txt (the session's main reply, taken from its transcript by extract.py). {{OUT}}/extract.log holds extract.py's summary line per session with its `denials=`, `turns=`, `corrections=`, `harness_fed=` and `confound=` fields: every reply is scored like the others, and a row is marked `confounded (denials=<n>, corrections=<n>, harness_fed=<n>)` only on a refusal, a correction or a post-warning re-reply (denials, corrections or harness_fed above 0), never on the turn count alone, because a session that reads pages with tools is multi-turn by construction; a count of `absent` is reported as unknown, never as zero. The questions asked are in {{OUT}}/questions.txt (`role: question`; a tag is `<role>-{{STYLE}}`). Predecessor replies for the comparison lines: {{PREVIOUS}} (a directory of <tag>.full.txt files for the same questions, or the word none, in which case there is no comparison line).

SCOPE
- Reading list: the rubric, the manifest, the questions, the replies, {{OUT}}/extract.log and the predecessors named above; for the rule texts, the copies run.sh staged in {{OUT}}/defs/: `## Identity` and `## Output styles` in {{OUT}}/defs/CUSTOMISATION.md, and the `### {{STYLE}}` block in {{OUT}}/defs/CUSTOMISATION-definitions.md (or in {{OUT}}/defs/CUSTOMISATION.md if it lives there). Read nothing else.
- Grants: {{OUT}} alone, plus {{PREVIOUS}} when it is a directory, and never a vault file, because a file grant reaches its whole parent directory and the rule texts sit at the vault root.
- File whitelist: NONE — read-only lane.

VERIFICATION
- Output gate: every cell of every row filled with a quoted sentence or "none". No word count anywhere: length is never a verdict, and a count in the report is a defect.
- Controls: positive — one distinctive clause of the Test quoted in the rubric's section B must hit in the `### {{STYLE}}` block of the staged rule text in {{OUT}}/defs/ (report the grep and its count); negative — the string "{{NEGATIVE}}" (a phrase from the previous wording of the definition) must NOT hit there (report the count, expected 0).

CONDUCT
- Blind lane: you are not told what the head expects; judge the text alone against the rubric.
- Findings, never instructions; write nothing; a task notification is never consent.

REPORT
One table per reply (A1–A7, B, readable on one pass, the most damaging sentence, confounded yes/no with the counts), then the comparison lines if predecessors were given, then the two control greps with their hit counts. The prose as short as it can be; the per-reply tables whole.
