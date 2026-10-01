# style-rerun — the evidence kit for how a style behaves live

## What it is
Three scripts and two templates that show how a fresh head session behaves on one output style under the live hooks, and hand the replies to a blind judge. It exists because a style's `Test:` is a bound given in context before writing, never enforced after: the honest evidence that a style text works is fresh sessions, read by a judge who does not know what the head expects.

## Files
- `run.sh` starts one headless `claude -p` session per question, from the vault root, with the hand-off opener `<role>, <style>. <question>`, and writes the results, a manifest, a progress log and `defs/` (copies of the vault's two CUSTOMISATION files, the judge's rule texts) into the run directory. `--dry-run` validates the inputs and prints the plan without spending anything.
- `extract.py` pulls each session's main reply out of its transcript into `<tag>.full.txt` and reports whether the reply opened with the status line, the session's refusals, corrections and harness-fed turns apart from its tool-use turn count, and a `confound=` field the turn count never enters.
- `render-rubric.py` fills `rubric.md` with the style's name and its live `Test:` clause; `run.sh` calls it, so the judge's rubric is never stale.
- `rubric.md` is the rubric template (A1–A7 plainness, B the style's Test, the scoring rule).
- `judge-brief.md` is the verifier-lane brief template. The head fills `{{RUN}}`, `{{OUT}}`, `{{STYLE}}`, `{{PREVIOUS}}` (a directory of predecessor replies, or `none`) and `{{NEGATIVE}}` (a phrase from the previous definition wording, the negative control).
- `questions.txt` holds the standing questions, one `role: question` per line; edit it to suit the vault.
- `test_style_rerun.sh` is the kit's suite (`PASS n/n` or `FAIL k/n`); it runs without a real `claude` call.

## How deep-lint uses it
When a style definition changes, run `run.sh --style <name> --record <spawn-record>`, then
`extract.py --out <dir>`. Give an independent verifier the extraction log, the filled
`judge-brief.md` and the run directory. The verifier reads the copied rules in `defs/` and
reports the rubric tables for every reply. The head files that evidence and decides from it.
An ad-hoc pilot follows the same independent review rule.

Kit sessions run under the live hooks and the CUSTOMISATION import, so they test the live positions of the text. A probe that carries a candidate text by `--append-system-prompt` adds a third position and cannot attribute an effect to the session-start bullet or the per-turn line (the position taxonomy: `wiki/concepts/Claude Code Output Styles.md`; cross-reflection XR-1, written 2026-09-05 18:54 BST).

## The rule: length is never a verdict
A detailed answer to a simple question can be short and a shortest-style answer to a hard question can be long. Nothing in this kit counts, logs or judges the words of a reply: `run.sh` records exits, `extract.py` reports whether the status line opened the reply and the session's refusal, correction, harness-fed and turn counts, and the rubric scores content and plainness. The comparison line asks "better, same or worse, and on what", and the answer is never "shorter" or "longer".

## Cost and safety
Each session is a real call on the model named by `--model` (default `claude-opus-5-5`, the default Claude model since the owner's ruling of 2026-09-29; `claude-fable-5-1` before) with `--allowedTools Read,Grep,Glob`, so it reads the vault and writes nothing. The transcripts land where Claude Code keeps this project's sessions; `extract.py` derives that directory from the vault path and takes `--transcripts` when it differs.


## Where the questions live

`questions.txt` beside the scripts is a generic example that ships with the public template. Locally configured questions can live in `~/.llm-wiki/style-rerun/questions.txt` (machine-local, never shipped), and `run.sh` prefers that file when it exists; comparable evidence needs the same questions run after run, so change them only on purpose.
