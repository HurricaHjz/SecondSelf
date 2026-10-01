#!/usr/bin/env python3
"""check-tier-vocabulary.py — skills' restatements of CLAUDE.md §4.6's tier caps and defaults (lint Step 2).

Stdout-only by construction: reads CLAUDE.md and every .claude/skills/*/SKILL.md, prints, writes
nothing.

Why (known-issues 2026-09-03): a skill can restate a tier cap that §4.6 sets otherwise ("a
synthesis caps at `medium`" where §4.6 caps agent-derived pages at `high`), and the contradiction
survives until someone reads both surfaces. CLAUDE.md §12 puts the sweep duty on whoever changes a
rule, and nothing else checks afterwards. This leg is narrow by design: it keys on the property the evidence supplies, the tier
vocabulary, and does not attempt paraphrase detection.

Extraction, the same on both sides. Every `cap at` / `caps at` / `capped at` / `capping at` and
`default to` / `defaults to` / `defaulted to` / `defaulting to` followed directly by a tier word
(authoritative · high · medium · low · very-low; code, emphasis and quote marks allowed between)
is one statement. Its subject is the page types named in the same clause before the phrase: the
clause runs back to the nearest `.`, `;`, `:`, `!` or `?` followed by a blank, an unclosed `(`,
or a line that starts a new block (a blank line, a list item, a heading, a quote, a table row);
a wrapped line inside one paragraph is not a boundary. Type words are the §4.1 types in the
singular or plural, plus the two collective names §4.6 itself uses: `compiled` (concept · entity
· tool · model · benchmark) and `agent-derived` (synthesis · development). Fenced code blocks and
HTML comments are blanked before extraction.

Canon: the statements extracted from CLAUDE.md §4.6 (its heading to the next heading), one
(type, verb) -> tier each. Two canon statements that disagree are PROBE FAILED, since the leg then
has nothing consistent to diff against, and so is a canon of zero statements (§4.6 reworded past
the vocabulary). A skill statement whose (type, verb) the canon carries with another tier is a
MISMATCH, the finding. A statement with no type word in its clause is UNATTRIBUTED, and one whose
(type, verb) the canon does not carry is UNCOVERED; both are listed as information, never
findings.

Controls, in memory, before the scan and built from the live canon rather than a constant, so a
changed rule still gets a working control: one canon statement restated with a different tier
must read as a mismatch, and restated with its own tier must read as a match (the synthesis cap
is preferred, which replays the 2026-09-03 wording exactly while the canon caps a synthesis at
anything but `medium`). A control that does not behave is PROBE FAILED (exit 2).

Usage (from the vault root):
  python3 .claude/skills/lint/check-tier-vocabulary.py [--vault ROOT]
  exit 0 = clean · 1 = findings · 2 = broken premise (not a vault root, no CLAUDE.md or no §4.6,
  an empty or self-contradicting canon, no skills directory, an unreadable file, a control that
  did not behave)
"""
import glob
import os
import re
import sys

USAGE = ("usage: check-tier-vocabulary.py [--vault ROOT]   "
         "(exit 0 clean · 1 findings · 2 broken premise)")

TIERS = ("authoritative", "high", "medium", "low", "very-low")
COMPILED = ("concept", "entity", "tool", "model", "benchmark")
PHRASE_RE = re.compile(
    r"(?P<verb>\b(?:caps?|capped|capping)\s+at|\bdefault(?:s|ed|ing)?\s+to)"
    r"[\s*_`\"']*(?P<tier>very-low|authoritative|high|medium|low)(?![\w-])",
    re.I,
)
TYPE_WORDS = {"compiled": COMPILED, "agent-derived": ("synthesis", "development"),
              "syntheses": ("synthesis",), "entities": ("entity",)}
for _t in ("concept", "entity", "tool", "model", "benchmark", "source", "synthesis", "development", "map", "user"):
    TYPE_WORDS.setdefault(_t, (_t,))
    TYPE_WORDS.setdefault(_t + "s", (_t,))
WORD_RE = re.compile(r"(?<![\w-])(agent-derived|[A-Za-z]+)(?![\w-])")
BLOCK_START_RE = re.compile(r"[ \t]*(?:$|[-*+][ \t]|\d+\.[ \t]|#|>|\|)")
SECTION_HEAD_RE = re.compile(r"^###[ \t]+4\.6\b.*$", re.M)
NEXT_HEAD_RE = re.compile(r"^#{1,3}[ \t]", re.M)


def probe_failed(message):
    print(f"PROBE FAILED: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_root(argv):
    """`--vault ROOT` or a positional root; an unknown flag is refused, never read as the root."""
    root, rest = None, list(argv)
    while rest:
        arg = rest.pop(0)
        if arg in ("-h", "--help"):
            print(USAGE)
            raise SystemExit(0)
        if arg == "--vault":
            if not rest:
                probe_failed("--vault needs a directory argument")
            arg = rest.pop(0)
        elif arg.startswith("--vault="):
            arg = arg.split("=", 1)[1]
        elif arg.startswith("-"):
            probe_failed(f"unknown option {arg} ({USAGE})")
        if root is not None:
            probe_failed(f"two roots given ({root} and {arg})")
        root = arg
    return root if root else "."


def read_text(path):
    """UTF-8 with a BOM dropped and CRLF normalised; bad bytes replaced, never fatal."""
    with open(path, "rb") as fh:
        raw = fh.read()
    return raw.decode("utf-8-sig", "replace").replace("\r\n", "\n")


def blank_noise(text):
    """Fenced blocks and HTML comments replaced by blanks of the same length, newlines kept, so
    every offset and line number still points at the original text."""
    keep = lambda m: re.sub(r"[^\n]", " ", m.group(0))
    text = re.sub(r"<!--.*?-->", keep, text, flags=re.S)
    return re.sub(r"^[ \t]*(```|~~~).*?^[ \t]*\1[^\n]*$", keep, text, flags=re.S | re.M)


def clause_before(text, start):
    """The clause text before offset `start`, bounded as the docstring says."""
    depth, i = 0, start - 1
    while i >= 0:
        ch = text[i]
        if ch == ")":
            depth += 1
        elif ch == "(":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and ch in ".;:!?" and (i + 1 >= len(text) or text[i + 1] in " \t\n"):
            break
        elif ch == "\n" and BLOCK_START_RE.match(text, i + 1):
            break
        i -= 1
    return text[i + 1:start]


def statements(text):
    """[(types tuple, verb, tier, line number, clause)] for every phrase in the text."""
    clean = blank_noise(text)
    out = []
    for m in PHRASE_RE.finditer(clean):
        clause = clause_before(clean, m.start())
        types = []
        for w in WORD_RE.findall(clause):
            for t in TYPE_WORDS.get(w.lower(), ()):
                if t not in types:
                    types.append(t)
        verb = "cap" if m.group("verb").lower().startswith("cap") else "default"
        line = clean.count("\n", 0, m.start()) + 1
        shown = " ".join((clause + m.group(0)).split())
        out.append((tuple(types), verb, m.group("tier").lower(), line, shown))
    return out


def section_46(text):
    head = SECTION_HEAD_RE.search(text)
    if not head:
        return None, 0
    nxt = NEXT_HEAD_RE.search(text, head.end() + 1)
    body = text[head.end():nxt.start() if nxt else len(text)]
    return body, text.count("\n", 0, head.end()) + 1


def build_canon(stmts):
    """{(type, verb): tier}; a disagreement inside the canon is returned as a message."""
    canon, clash = {}, []
    for types, verb, tier, line, _ in stmts:
        for t in types:
            old = canon.get((t, verb))
            if old and old != tier:
                clash.append(f"{t} {verb} {old} and {tier}")
            canon[(t, verb)] = tier
    return canon, clash


def classify(stmts, canon):
    """Sort statements into match · mismatch · uncovered · unattributed lists of (types, verb,
    tier, line, clause, canon tiers)."""
    result = {"match": [], "mismatch": [], "uncovered": [], "unattributed": []}
    for types, verb, tier, line, clause in stmts:
        if not types:
            result["unattributed"].append((types, verb, tier, line, clause, ()))
            continue
        covered = [(t, canon[(t, verb)]) for t in types if (t, verb) in canon]
        if not covered:
            result["uncovered"].append((types, verb, tier, line, clause, ()))
        elif any(ct != tier for _, ct in covered):
            result["mismatch"].append((types, verb, tier, line, clause, tuple(covered)))
        else:
            result["match"].append((types, verb, tier, line, clause, tuple(covered)))
    return result


def main():
    root = parse_root(sys.argv[1:])
    if not all(os.path.isdir(os.path.join(root, d)) for d in ("raw", "wiki")):
        probe_failed(f"{root} is not a vault root (no raw/ or wiki/)")
    claude = os.path.join(root, "CLAUDE.md")
    try:
        schema = read_text(claude)
    except OSError as exc:
        probe_failed(f"cannot read CLAUDE.md ({exc.__class__.__name__})")
    body, head_line = section_46(schema)
    if body is None:
        probe_failed("CLAUDE.md has no `### 4.6` heading — no canon to diff against")
    canon_stmts = [(ty, v, ti, ln + head_line - 1, cl) for ty, v, ti, ln, cl in statements(body)]
    canon, clash = build_canon(canon_stmts)
    if not canon:
        probe_failed("CLAUDE.md §4.6 yields no `caps at` / `defaults to` + tier statement with a page type — "
                     "the rule was reworded past this leg's vocabulary")
    if clash:
        probe_failed("CLAUDE.md §4.6 contradicts itself: " + "; ".join(clash))

    # Controls from the live canon: prefer the synthesis cap, else the first key in order.
    key = ("synthesis", "cap") if ("synthesis", "cap") in canon else sorted(canon)[0]
    own = canon[key]
    other = "medium" if own != "medium" else "high"
    phrase = "caps at" if key[1] == "cap" else "defaults to"
    wrong = classify(statements(f"A {key[0]} {phrase} `{other}`.\n"), canon)
    right = classify(statements(f"A {key[0]} {phrase} `{own}`.\n"), canon)
    if len(wrong["mismatch"]) != 1 or len(right["match"]) != 1 or right["mismatch"]:
        probe_failed(f"the planted restatements of the canon's {key[0]} {key[1]} were not read as one "
                     f"mismatch and one match")

    skills_dir = os.path.join(root, ".claude", "skills")
    if not os.path.isdir(skills_dir):
        probe_failed(f"{skills_dir} is not a directory — no skill to scan")
    skill_files = sorted(glob.glob(os.path.join(skills_dir, "*", "SKILL.md")))
    found = {"match": [], "mismatch": [], "uncovered": [], "unattributed": []}
    for path in skill_files:
        try:
            text = read_text(path)
        except OSError as exc:
            probe_failed(f"cannot read {os.path.relpath(path, root)} ({exc.__class__.__name__})")
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        for kind, items in classify(statements(text), canon).items():
            found[kind].extend((rel,) + item for item in items)

    canon_text = " · ".join(f"{t} {v} {canon[(t, v)]}" for t, v in sorted(canon))
    total = sum(len(v) for v in found.values())
    print(f"TIER VOCABULARY: CLAUDE.md §4.6 -> {len(canon)} canon (type, verb) keys from {len(canon_stmts)} "
          f"statement(s) | {len(skill_files)} skills scanned | {total} restatement(s): {len(found['match'])} match · "
          f"{len(found['mismatch'])} mismatch · {len(found['uncovered'])} uncovered · "
          f"{len(found['unattributed'])} unattributed   (nonzero canon = the probe ran)")
    print(f"CANON: {canon_text}")
    print(f"CONTROL: planted \"A {key[0]} {phrase} `{other}`\" -> mismatch; planted \"A {key[0]} {phrase} `{own}`\" -> match")
    shown = lambda s: s if len(s) <= 120 else "..." + s[-117:]
    print(f"MISMATCHES: {len(found['mismatch'])}")
    for rel, types, verb, tier, line, clause, covered in found["mismatch"]:
        says = ", ".join(f"{t} {c}" for t, c in covered)
        print(f"  {rel}:{line} · {'/'.join(types)} {verb} {tier} (§4.6: {says}) · {shown(clause)}")
    for label in ("match", "uncovered", "unattributed"):
        print(f"{label.upper()}: {len(found[label])} (information)")
        for rel, types, verb, tier, line, clause, covered in found[label]:
            print(f"  {rel}:{line} · {'/'.join(types) or '(no type)'} {verb} {tier} · {shown(clause)}")
    return 1 if found["mismatch"] else 0


if __name__ == "__main__":
    sys.exit(main())
