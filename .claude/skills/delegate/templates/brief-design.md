# Design brief — a check's effect and acceptance

Fill EVERY `{{slot}}` before building or reviewing the check. This contract accompanies
the task's spawn brief; its scope, grants and decisions still apply. Write the intended
behaviour before the implementation or its review findings can set the requirements.

TASK
{{The problem, who uses the result, and the boundary of this check.}}

EFFECT
- Effect: {{warn | block | repair; name each effect if there is more than one}}.
- {{What the user sees, what decision or action follows, and what the check may change.}}

FAILURES THAT MATTER
- {{For a warning: saying "all clear" when it should warn, including unreadable inputs
  presented as clean. For a block: admitting what it should refuse AND refusing what it
  should admit. For a repair: failing the promised repair or changing anything outside
  its authorised scope. Tie each failure to the stated effect.}}
- {{How missing, malformed or stale evidence is reported; what cannot be concluded.}}

MATERIAL SIDE EFFECTS
- Time: {{work and waiting bounds, with their derivation or "set by judgement, unmeasured"}}.
- Memory: {{input/output bounds and retained state, with the basis for each bound}}.
- Interference: {{other work, processes or files the check could disturb, and its limits}}.
- Noise: {{what is printed, where it is seen, and how real warnings stay visible}}.

MERGE TARGET
- Target file: {{literal path}}.
- Suite: {{literal path}}. The suite is how the effect is verified: a leg whose verdict can
  be wrong on a case it covers (it can pass or fail for reasons other than the code under
  test, such as timing, other processes or other files) counts as touching the effect.
- Census rule: {{the rule this suite enforces and its source | none, with evidence |
  unknown, recorded as a gap; do not invent an exact test count}}.
- Other integration surfaces: {{literal paths and the change required | none}}.

ACCEPTANCE TESTS
{{For every stated failure and material side effect: the planted input, the expected
observable result and the check that proves it. Include a clean case with its positive
control on the same run, unavailable evidence, and a live read where appropriate. Size
the tests to the effect; a warning alone does not require crash-surviving records.}}

DECISIONS AND GAPS
{{The settled choices and any missing requirement; name what depends on each gap.}}

EVIDENCE
{{The design sources used, including the basis for deciding numbers, and the code the
design changes, by literal path, which its author read before writing it. Keep review
findings out of a brief commissioned as a pre-build design contract.}}
