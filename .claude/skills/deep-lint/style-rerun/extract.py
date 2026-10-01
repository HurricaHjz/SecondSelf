#!/usr/bin/env python3
"""extract.py — pull each session's main reply out of its transcript (the style re-run kit).

Reads the manifest run.sh wrote (`tag sid` per line), opens each session's transcript in the Claude
Code project directory, takes the session's main reply and writes it to <out>/<tag>.full.txt. Prints
one line per reply: the tag, the session id, the session's refusal and tool-use turn counts (read from
the CLI result run.sh saved beside the reply, `absent` when the file or field is missing, never 0),
whether the reply opens with the status line, the number of assistant texts, of corrections left out
and of harness-fed turns, a `confound=` verdict, and the opening line itself. The counts let the judge
mark confounded sessions.
# References: register 2026-09-05.

The main reply is the longest assistant text of the session by character count, leaving out a
post-warning correction: an assistant text that answers a harness record opening `Stop hook
feedback:` in an isMeta user record. The exclusion is keyed on that record,
never on the text's size or wording. Nothing here counts words: length is never a measure of a
reply (owner ruling 2026-09-05); character length serves only to pick the reply out from the
progress lines around it.

The confound fields are kept apart from the turn count (register 2026-09-09): a kit session answers
by reading pages with tools, so it is multi-turn by construction and `turns=` separates nothing.
`harness_fed=` counts the records the harness fed into the session after the model began: a user
record opening `Stop hook feedback:`, or any other isMeta user record after the first assistant
record (a tool result is neither). `confound=yes` when the session had a refusal (denials above 0),
a correction or a harness-fed turn; `unknown` when none of those was seen and the denials count is
absent; `no` otherwise. The turn count never enters it.

  extract.py --out DIR [--manifest FILE] [--transcripts DIR] [--vault DIR]

  --out          the run directory: the default manifest is <out>/manifest.txt and the .full.txt
                 files land there
  --manifest     the manifest to read (default <out>/manifest.txt)
  --transcripts  the transcript directory; default derived from --vault the way Claude Code
                 derives it: ~/.claude/projects/<absolute vault path with every character outside
                 A-Za-z0-9 replaced by '-'>
  --vault        the vault root the sessions ran from (default: the current directory)

A missing or empty manifest, a missing transcript directory, or a row whose transcript is missing
prints PROBE FAILED and exits 2 (every row is still reported), never a clean zero.
"""
import argparse
import json
import os
import re
import sys

SHAPE = re.compile(r"^\S.* · \S.* · .+")   # the status line's shape, as the Stop verifier tests it
FEEDBACK = "Stop hook feedback:"


def transcript_dir(vault):
    """Claude Code keeps a project's transcripts under ~/.claude/projects/<key>, the key being the
    absolute project path with every character outside A-Z, a-z, 0-9 replaced by '-'."""
    key = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(vault))
    return os.path.join(os.path.expanduser("~"), ".claude", "projects", key)


def records(path):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def text_of(rec):
    c = (rec.get("message") or {}).get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    return ""


def main_reply(recs):
    """(main text, assistant texts seen, corrections left out, harness-fed turns). A correction is
    the first assistant text after a user record opening with the Stop hook's feedback; a
    harness-written assistant record (isApiErrorMessage) is never a candidate; a harness-fed turn is
    that feedback record, or any other isMeta user record once the model has begun."""
    candidates, seen, corrections, fed = [], 0, 0, 0
    answering_feedback, begun = False, False
    for rec in recs:
        if not isinstance(rec, dict):
            continue
        if rec.get("type") == "user":
            if text_of(rec).lstrip().startswith(FEEDBACK):
                answering_feedback = True
                fed += 1
            elif rec.get("isMeta") and begun:
                fed += 1
            continue
        if rec.get("type") != "assistant" or rec.get("isApiErrorMessage"):
            continue
        begun = True
        text = text_of(rec).strip()
        if not text:
            continue
        seen += 1
        if answering_feedback:
            corrections += 1
            answering_feedback = False
            continue
        candidates.append(text)
    return (max(candidates, key=len) if candidates else ""), seen, corrections, fed


def confound(denials, corrections, fed):
    """yes · unknown · no, as the module docstring defines it; the turn count never enters."""
    if (denials.isdigit() and int(denials) > 0) or corrections or fed:
        return "yes"
    return "unknown" if not denials.isdigit() else "no"


def opening_line(text):
    for line in text.splitlines():
        s = line.strip().strip("`").strip()
        if s:
            return s
    return ""


def result_fields(out, tag):
    """The session's refusal and turn counts from the CLI result run.sh saved as <out>/<tag>.json:
    `denials` = len(permission_denials), `turns` = num_turns. A missing file, unreadable JSON or a
    missing field gives `absent`, never 0: a measured zero and an unknown are different claims."""
    path = os.path.join(out, tag + ".json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return "absent", "absent"
    if not isinstance(data, dict):
        return "absent", "absent"
    denials = data.get("permission_denials")
    turns = data.get("num_turns")
    return (str(len(denials)) if isinstance(denials, list) else "absent",
            str(turns) if isinstance(turns, int) and not isinstance(turns, bool) else "absent")


def main(argv=None):
    p = argparse.ArgumentParser(description="pull each re-run session's main reply from its transcript")
    p.add_argument("--out", required=True)
    p.add_argument("--manifest")
    p.add_argument("--transcripts")
    p.add_argument("--vault", default=".")
    a = p.parse_args(argv)
    manifest = a.manifest or os.path.join(a.out, "manifest.txt")
    tdir = a.transcripts or transcript_dir(a.vault)
    if not os.path.isfile(manifest):
        print("PROBE FAILED: no manifest at %s" % manifest)
        return 2
    if not os.path.isdir(tdir):
        print("PROBE FAILED: no transcript directory at %s (pass --transcripts)" % tdir)
        return 2
    rows = [ln.split() for ln in open(manifest, encoding="utf-8") if ln.strip()]
    rows = [r for r in rows if len(r) >= 2]
    if not rows:
        print("PROBE FAILED: no `tag sid` row in %s" % manifest)
        return 2
    failed = 0
    for tag, sid in (r[:2] for r in rows):
        path = os.path.join(tdir, sid + ".jsonl")
        if not os.path.isfile(path):
            print("PROBE FAILED: %s has no transcript at %s" % (tag, path))
            failed += 1
            continue
        text, seen, corrections, fed = main_reply(records(path))
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, tag + ".full.txt"), "w", encoding="utf-8") as fh:
            fh.write(text)
        first = opening_line(text)
        denials, turns = result_fields(a.out, tag)
        print("%-24s sid=%s denials=%s turns=%s opens_status=%s texts=%d corrections=%d harness_fed=%d confound=%s opening=%r"
              % (tag, sid, denials, turns, "yes" if SHAPE.match(first) else "no", seen, corrections, fed,
                 confound(denials, corrections, fed), first[:80]))
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
