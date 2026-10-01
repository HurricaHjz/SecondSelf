#!/usr/bin/env python3
"""brief_preflight.py - the brief check before any spawn of a parallel ingest.

Design: the ingest persistence design, extension 2026-09-13 (the second read cut), part 4. A
head-side rewrite of the compile briefs can rewrite the `wiki/` that ends the agent home's directory
name as the vault's absolute path, so the ledger token's parent no longer exists
(`<home>/<home prefix>-<vault>/wiki/ingest-runs/...`), and a lane given such a brief appends no ledger
event and leaves its claims only in its report (known-issues, entry 2026-09-09 19:03). This check runs over the run's
filled compile and verify briefs after the partition's disjointness assert and before the owner-go
echo, which carries its `summary:` line.

A brief fails on any of:
  (a) paths   a path token - absolute, `~/`, or vault-relative `raw/` or `wiki/` - whose parent
              directory does not exist, or that still holds an unfilled slot. Matching double or
              single quotes preserve the whole path, including spaces, ampersands and hyphens.
              Prose apostrophes cannot hide quoted paths. A bare backtick path stays whole;
              operators split command paths only when they stand between path-like tokens.
  (b) ledger  a run-ledger path (`.../ingest-runs/run-*.jsonl`) that differs between briefs or from
              the run's ledger; a wiki-compile brief carrying none fails too
  (c) append  no `preflight` event, every line read with json.loads, after `run_open` in the ledger
              at the brief's literal ledger path. Checked only once (a) and (b) pass for the brief:
              `>>` creates a file wherever its parent exists, so an append at an unproven path could
              plant an event in another run's ledger. A brief failing (a) or (b) fails (c) unproven.
  (d) fence   for a headless lane, any answer but the pinned allow from lane-fence.py's check() for
              the lane's own append command at that path, under the grants and writes its
              `lane.py spawn --dry-run` output prints (no lane is spawned). Checked, like (c), only
              once (a) and (b) pass; a lane named by --in-session runs under no lane fence.
  (e) index   one of the index's `## ` sections named anywhere in the brief (on the index's own line
              or any other), or every entry line of one section carried (part 3's slice file
              replaces the section read).

Usage:
  python3 brief_preflight.py --ledger <ledger.jsonl | run-id> BRIEF [BRIEF ...]
      [--dry-run LANE=FILE ...] [--in-session LANE|all ...] [--vault DIR] [--index FILE] [--fence FILE]
--dry-run names the persisted stdout of `lane.py spawn ... --dry-run` for a headless lane; every
brief's lane must be named by --dry-run or --in-session, so the fence check is never skipped by
omission. A bare run id resolves as ledger_check.py resolves it. The vault root defaults to three
directories above this script (`<vault>/.claude/skills/ingest/`), the fence to the delegate skill's
lane-fence.py beside this skill.

Output: one `brief` line per brief, `FAIL (<check>)` lines, a `NEXT:` line when only (c) is left, a
`summary:` line and a `controls:` line. A deciding path check never trusts itself: before any brief is
judged, planted cases run through the same functions - an absent parent and an unfilled slot must
fail, the run's own ledger path must pass, differing ledger paths must differ, the run_open/preflight
order must fold both ways, a named and a whole index section must fire and a clean line must not, and,
where a lane is headless, the fence must answer the pinned allow inside the write roots and deny
outside them.
Exit 0 = every brief passes every check; 1 = a brief failed; 2 = PROBE FAILED: zero briefs, an
unreadable or empty brief, a missing, eventless or run_open-less ledger, a brief naming no lane, a
brief with no path token at all, a headless lane whose dry-run output is missing or carries no grants
(the wrapper refused: it exits 2 before printing), a lane named neither by --dry-run nor --in-session,
a fence that does not import or raises, an unreadable index or one without `## ` sections, or a
same-run control that did not behave.
Reads only: it creates, modifies, moves and deletes nothing; the sibling and the fence are imported
with bytecode caching off, so nothing is written beside them either.
"""
import argparse, importlib.util, json, os, re, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ledger_check  # noqa: E402  resolve() for a bare run id; parse_ts() orders run_open and preflight

VAULT_DEFAULT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
FENCE_DEFAULT = os.path.join(os.path.dirname(HERE), "delegate", "lane-fence.py")
# The pass condition for (d): in the lane role an append inside the write roots answers
# ("allow", "lane-fence: within grants") and one outside them
# ("deny", ...); the head role answers a cleared command with ("silent", ""). The same-run control
# re-observes both lane-role answers before any brief is judged, so a changed check() stops the run.
PINNED_ALLOW = "allow"
CONTROL_ROOT = "/brief-preflight-control-root"      # never created: check() compares paths, not files
CONTROL_OTHER = "/brief-preflight-control-other"
ABSENT_PARENT = "/brief-preflight-control-absent"   # the (a) control's premise: it must not exist

SLOT = re.compile(r"\{\{[^{}\n]*\}\}|<[A-Za-z][^<>\n]{0,40}>")
TOKEN = re.compile(r"[^\s`'\"|;&\x00]+")
LEAD, TRAIL = "([*", ".,;:)]*!?"
LEDGER = re.compile(r"(?:^|/)ingest-runs/run-[^/]*\.jsonl$")
FIRST = re.compile(r"\bYou are\s+([\w.-]+).*?\blane\s+(\S+?),?\s+of\s+run\s+(\S+)", re.S)
GLOB = re.compile(r"[*?\[]")
CODE_SPAN = re.compile(r"`([^`\n]*)`")
OPERATOR = re.compile(r"&&|\|\||[&|;]")
PATH_START = re.compile(r"(?<![\w./~])(?:/(?!/)|\.\.?/|~/|raw/|wiki/)|\x00")
FOLLOW = r"(?=\s*$|\s*[`'\",;:.)\]”’·—–]|\s+(?:and|or|&|headings?|sections?)\b)"


def fail(msg):
    print("PROBE FAILED: " + msg)
    sys.exit(2)


def token_kind(tok):
    """(kind, slotted): home | abs | vault | relative | slot, or None for a non-path token.
    Dot-slash and parent-relative paths are resolved against --vault, like raw/ and wiki/."""
    slotted = bool(SLOT.search(tok)) or "{{" in tok or "}}" in tok
    if tok.startswith("~/"):
        return "home", slotted
    if tok.startswith("/") and not tok.startswith("//") and len(tok) > 1:
        return "abs", slotted
    if tok.startswith(("raw/", "wiki/")):
        return "vault", slotted
    if tok.startswith(("./", "../")):
        return "relative", slotted
    if slotted and "/" in tok and tok.startswith(("{{", "<")):
        return "slot", slotted
    return None, slotted


def quoted_paths(line, quote):
    """Yield path-bearing quote spans only; apostrophes between letters are ordinary prose."""
    def prose_apostrophe(index):
        return (quote == "'" and index > 0 and index + 1 < len(line)
                and line[index - 1].isalpha() and line[index + 1].isalpha())

    offset = 0
    while offset < len(line):
        start = line.find(quote, offset)
        if start < 0:
            break
        offset = start + 1
        if prose_apostrophe(start) or not token_kind(line[offset:])[0]:
            continue
        end = line.find(quote, offset)
        while end >= 0 and prose_apostrophe(end):
            end = line.find(quote, end + 1)
        if end < 0:
            continue
        content = line[offset:end]
        if "\x00" not in content:  # a nested double-quoted path has already taken precedence
            yield start, end + 1, content
        offset = end + 1


def plain_tokens(text):
    for match in TOKEN.finditer(text):
        token = match.group(0).lstrip(LEAD).rstrip(TRAIL)
        if token_kind(token)[0]:
            yield token


def code_tokens(content):
    """Keep one path-like start whole, including A & B components; split an operator only
    between path-like tokens. A protected quote marker also counts as a path-like start."""
    def starts_path(value):
        return value.startswith("\x00") or token_kind(value)[0] is not None

    start = 0
    chunks = []
    for match in OPERATOR.finditer(content):
        if (starts_path(content[start:match.start()].strip())
                and starts_path(content[match.end():].lstrip())):
            chunks.append(content[start:match.start()].strip())
            start = match.end()
    chunks.append(content[start:].strip())
    for chunk in chunks:
        if starts_path(chunk) and len(PATH_START.findall(chunk)) == 1:
            if not chunk.startswith("\x00"):
                yield chunk
        else:
            yield from plain_tokens(chunk)


def path_tokens(text):
    """(line, token, kind, slotted) for every path. Slots are masked before splitting. A quote
    opens a span only if a path follows it; an apostrophe between letters is prose. Double-quoted
    path spans take precedence over nested single quotes, and every accepted quoted path stays
    whole. Inside backticks, &, &&, |, || and ; separate two path-like tokens (with or without
    spaces); a sole path-like start, including leading / or ./, stays whole. Thus A & B/missing
    remains one component of a bare backtick path, while /bin/check & /bin/compile is two paths."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        masked = list(SLOT.sub(lambda m: re.sub(r"\s", "_", m.group(0)), line))
        for quote in ('"', "'"):
            for start, end, content in quoted_paths("".join(masked), quote):
                kind, slotted = token_kind(content)
                out.append((n, content, kind, slotted))
                masked[start:end] = "\x00" + " " * (end - start - 1)
        for m in CODE_SPAN.finditer("".join(masked)):
            for content in code_tokens(m.group(1)):
                kind, slotted = token_kind(content)
                out.append((n, content, kind, slotted))
            masked[m.start():m.end()] = " " * (m.end() - m.start())
        for tok in plain_tokens("".join(masked)):
            kind, slotted = token_kind(tok)
            out.append((n, tok, kind, slotted))
    return out


def expand(tok, kind, vault):
    if kind == "home":
        return os.path.expanduser(tok)
    if kind in ("vault", "relative"):
        return os.path.join(vault, tok)
    return tok


def token_problem(tok, kind, slotted, vault):
    """None when the token's parent directory exists; else what is wrong with the token. A glob is
    cut at its first metacharacter and the directory before it must exist."""
    if slotted or kind == "slot":
        return "unfilled slot"
    full = expand(tok, kind, vault)
    g = GLOB.search(full)
    if g:
        head = full[:g.start()]
        parent = head[:head.rfind("/")] or "/"
    else:
        parent = os.path.dirname(full.rstrip("/")) or "/"
    return None if os.path.isdir(parent) else "parent directory %s does not exist" % parent


def ledger_real(tok, kind, vault):
    return os.path.realpath(expand(tok, kind, vault))


def read_events(path):
    """(events, malformed): (line, object) pairs, every line read with json.loads; (None, 0) when the
    file cannot be read."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None, 0
    events, malformed = [], 0
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            malformed += 1
            continue
        if isinstance(ev, dict):
            events.append((i, ev))
        else:
            malformed += 1
    return events, malformed


def preflight_after_open(events):
    """(found, why): a `preflight` event on a line after the first `run_open`, its ts not earlier
    than run_open's wherever both parse."""
    opened = next(((i, ev) for i, ev in events if ev.get("event") == "run_open"), None)
    if opened is None:
        return False, "no run_open event"
    t0 = ledger_check.parse_ts(opened[1].get("ts"))
    for i, ev in events:
        if i <= opened[0] or ev.get("event") != "preflight":
            continue
        t1 = ledger_check.parse_ts(ev.get("ts"))
        if t0 is not None and t1 is not None and t1 < t0:
            continue
        return True, "preflight event on line %d" % i
    return False, "no preflight event after run_open (line %d)" % opened[0]


def index_sections(path):
    """([(heading, [entry lines])], problem) from the index's `## ` headings and `- [[` lines."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as e:
        return None, "the index %s is unreadable (%s)" % (path, e)
    sections, cur = [], None
    for line in text.splitlines():
        m = re.match(r"## (.+?)\s*$", line)
        if m:
            cur = (m.group(1), [])
            sections.append(cur)
        elif cur is not None and line.startswith("- [["):
            cur[1].append(line.strip())
    if not sections:
        return None, "the index %s holds no `## ` section (empty, or not an index)" % path
    return sections, None


def index_hits(text, sections):
    """An index `## ` heading named anywhere in the brief, or every entry line of one section. A name
    counts where the heading is followed by the end of the line, a quote or punctuation, `and`/`or`,
    or the word heading or section, so a page section such as `## Sources Used` is not read as one."""
    lines = text.splitlines()
    held = {line.strip() for line in lines}
    hits = []
    for n, line in enumerate(lines, 1):
        named = [h for h, _e in sections if re.search(r"##\s+" + re.escape(h) + FOLLOW, line)]
        if named:
            hits.append("line %d names index section%s %s" % (n, "s" if len(named) > 1 else "",
                                                             ", ".join("`## %s`" % h for h in named)))
    for heading, entries in sections:
        if entries and all(e in held for e in entries):
            hits.append("carries every entry line of index section `## %s` (%d lines)" % (heading, len(entries)))
    return hits


def brief_identity(text):
    """(definition, lane) from the brief's first paragraph, as the templates wrap it; None if absent."""
    para = []
    for line in text.splitlines():
        if not line.strip():
            if para:
                break
            continue
        para.append(line.strip())
    m = FIRST.search(" ".join(para))
    if not m or "{{" in m.group(2) or "{{" in m.group(3):
        return None
    return m.group(1), m.group(2)


def dry_run_roots(path):
    """((grants, writes), None) from a persisted `lane.py spawn --dry-run` stdout, or (None, why)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as e:
        return None, "is unreadable (%s)" % e
    env = {}
    for line in text.splitlines():
        m = re.match(r"\s*(LLM_WIKI_LANE_GRANTS|LLM_WIKI_LANE_WRITES)=(.*)$", line)
        if m:
            env[m.group(1)] = m.group(2).strip()
    if "LLM_WIKI_LANE_GRANTS" not in env:
        return None, ("carries no LLM_WIKI_LANE_GRANTS line: the wrapper refused (it exits 2 before "
                      "printing) or its dry-run output changed shape")
    roots = lambda v: [os.path.realpath(os.path.expanduser(p.strip())) for p in v.split(os.pathsep) if p.strip()]
    grants, writes = roots(env["LLM_WIKI_LANE_GRANTS"]), roots(env.get("LLM_WIKI_LANE_WRITES", ""))
    if not grants:
        return None, "prints empty grants"
    return (grants, writes), None


def load_check(path):
    try:
        spec = importlib.util.spec_from_file_location("lane_fence_for_preflight", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:  # any failure to import is a broken premise, reported whole
        return None, "the fence %s does not import (%s: %s)" % (path, type(e).__name__, e)
    check = getattr(mod, "check", None)
    return (check, None) if callable(check) else (None, "the fence %s has no check() function" % path)


def append_command(lane, token):
    """The lane's own append, in the ledger primitive's exact form, at the brief's literal path."""
    lane = re.sub(r"[^A-Za-z0-9_-]", "", lane) or "lane"
    payload = json.dumps({"event": "lane_open", "lane": lane}, separators=(",", ":"))
    return "printf '%s\\n' '" + payload + "' >> " + token


def fence_answer(check, lane, token, grants, writes):
    try:
        action, reason = check({"tool_name": "Bash", "tool_input": {"command": append_command(lane, token)}},
                               grants, writes, head=False)
    except Exception as e:
        return None, "check() raised or changed shape (%s: %s)" % (type(e).__name__, e)
    return (action, reason), None


def controls(run_ledger, sections, vault, check):
    """Planted cases through the functions that judge the briefs; returns what did not behave."""
    if os.path.lexists(ABSENT_PARENT):
        return ["the (a) control's premise: %s exists" % ABSENT_PARENT]
    bad = []
    absent = ABSENT_PARENT + "/sub/run-c.jsonl"
    spaced = ABSENT_PARENT + "/a b/run-c.jsonl"
    ampersand = ABSENT_PARENT + " & space/missing/file.md"
    draft = ABSENT_PARENT + " & space -draft/missing/file.md"
    slot = "~/agent-home/ingest-runs/run-<id>.jsonl"
    toks = path_tokens('ledger %s beside "%s" and %s and "%s"\n' % (absent, run_ledger, slot, spaced))
    toks += path_tokens('read "%s"\n' % ampersand)
    prose = path_tokens('Read the owner\'s "%s"; it\'s absent.' % spaced)
    if len(prose) != 1 or prose[0][1] != spaced:
        bad.append("(a) prose apostrophes hid a double-quoted path")
    toks += prose
    bare = path_tokens("`" + ampersand + "`")
    if len(bare) != 1 or bare[0][1] != ampersand:
        bad.append("(a) a bare backtick ampersand path was not tested whole")
    toks += bare
    for quote in ('"', "'"):
        literal = path_tokens(quote + draft + quote)
        if len(literal) != 1 or literal[0][1] != draft:
            bad.append("(a) a quoted path containing -draft was not tested whole")
        toks += literal
    command_paths = ["/brief-preflight-check", "/brief-preflight-compile"]
    for separator in ("&", "&&", "|", "||", ";"):
        command = path_tokens("`" + separator.join(command_paths) + "`")
        if ([tok for _n, tok, _kind, _slot in command] != command_paths
                or any(token_problem(tok, kind, slotted, vault)
                       for _n, tok, kind, slotted in command)):
            bad.append("(a) command-span paths were not checked separately: " + separator)
    found = {tok: token_problem(tok, kind, slotted, vault) for _n, tok, kind, slotted in toks}
    if not (found.get(absent) or "").startswith("parent directory"):
        bad.append("(a) absent parent not caught")
    if not (found.get(spaced) or "").startswith("parent directory"):
        bad.append("(a) a quoted path holding a space was not tested whole")
    if not (found.get(ampersand) or "").startswith("parent directory"):
        bad.append("(a) a quoted ampersand path was not tested whole")
    if not (found.get(draft) or "").startswith("parent directory"):
        bad.append("(a) a quoted -draft path's missing parent was not caught")
    if run_ledger not in found or found[run_ledger] is not None:
        bad.append("(a) the run ledger's own path did not pass")
    if found.get(slot) != "unfilled slot":
        bad.append("(a) unfilled slot not caught")
    if len({ledger_real(tok, kind, vault) for _n, tok, kind, _s in toks if LEDGER.search(tok)}) < 2:
        bad.append("(b) differing ledger paths not told apart")
    if (not preflight_after_open([(1, {"event": "run_open"}), (2, {"event": "preflight"})])[0]
            or preflight_after_open([(1, {"event": "preflight"}), (2, {"event": "run_open"})])[0]):
        bad.append("(c) the run_open/preflight order fold")
    smallest = min((s for s in sections if s[1]), key=lambda s: len(s[1]), default=None)
    if smallest is None:
        bad.append("(e) the index holds no entry line to plant")
    else:
        if not index_hits("\n".join(smallest[1]), sections):
            bad.append("(e) a whole section not caught")
        if not index_hits("read wiki/index.md `## %s` in section mode" % smallest[0], sections):
            bad.append("(e) a named section not caught")
        if not index_hits("read wiki/index.md in section mode for\n## %s" % smallest[0], sections):
            bad.append("(e) a section named on the line after the index not caught")
        if index_hits("read the index slice file this brief names", sections):
            bad.append("(e) a clean line flagged")
    if check is not None:
        inside, why_in = fence_answer(check, "LC", CONTROL_ROOT + "/ingest-runs/run-c.jsonl", [CONTROL_ROOT], [CONTROL_ROOT])
        outside, why_out = fence_answer(check, "LC", CONTROL_OTHER + "/ingest-runs/run-c.jsonl", [CONTROL_ROOT], [CONTROL_ROOT])
        if inside is None or inside[0] != PINNED_ALLOW:
            bad.append("(d) an append inside the write roots did not get the pinned %r: %s" % (PINNED_ALLOW, inside or why_in))
        if outside is None or outside[0] != "deny":
            bad.append("(d) an append outside the write roots was not denied: %s" % (outside or why_out,))
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Check a parallel ingest's filled briefs before any spawn: (a) path parents and "
                    "unfilled slots, (b) one ledger path, (c) the head's preflight append proven at "
                    "it, (d) the lane fence's answer for a headless lane's append, (e) no index "
                    "section named or pasted. Double/single-quoted paths stay whole; unquoted "
                    "backtick command separators split paths only between path-like tokens. "
                    "Prose apostrophes never open quotes; a bare backtick path stays whole. Reads only.",
        epilog="Exit 0 every brief passes; 1 a brief failed; 2 PROBE FAILED (see the module docstring).")
    ap.add_argument("briefs", nargs="*", metavar="BRIEF", help="every filled compile and verify brief")
    ap.add_argument("--ledger", required=True, help="the run's ledger path, or a bare run id, resolved as ledger_check.py resolves it")
    ap.add_argument("--dry-run", action="append", default=[], metavar="LANE=FILE",
                    help="a headless lane's persisted `lane.py spawn ... --dry-run` stdout (repeatable)")
    ap.add_argument("--in-session", action="append", default=[], metavar="LANE",
                    help="a lane spawned in-session, under no lane fence; `all` names every lane (repeatable)")
    ap.add_argument("--vault", default=VAULT_DEFAULT, help="the vault root (default: three directories above this script)")
    ap.add_argument("--index", default=None, help="the index (default: <vault>/wiki/index.md)")
    ap.add_argument("--fence", default=FENCE_DEFAULT, help="lane-fence.py (default: the delegate skill's, beside this skill)")
    a = ap.parse_args(argv)

    if not a.briefs:
        fail("zero briefs matched: name every filled compile and verify brief")
    vault = os.path.realpath(a.vault)
    if not os.path.isdir(os.path.join(vault, "wiki")):
        fail("the vault root %s holds no wiki/ directory (pass --vault)" % vault)
    ledger_path = os.path.realpath(ledger_check.resolve(a.ledger))
    events, malformed = read_events(ledger_path)
    if events is None:
        fail("the run's ledger %s is missing or unreadable" % ledger_path)
    if not events:
        fail("the run's ledger %s holds no parseable event (%d malformed lines)" % (ledger_path, malformed))
    if not any(ev.get("event") == "run_open" for _i, ev in events):
        fail("the run's ledger %s holds no run_open event" % ledger_path)
    sections, why = index_sections(a.index or os.path.join(vault, "wiki", "index.md"))
    if sections is None:
        fail(why)

    dry = {}
    for spec in a.dry_run:
        lane, sep, path = spec.partition("=")
        if not (sep and lane and path):
            fail("--dry-run wants LANE=FILE, got %r" % spec)
        dry[lane] = path
    in_session = set(a.in_session)

    briefs = []
    for path in a.briefs:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as e:
            fail("brief unreadable: %s (%s)" % (path, e))
        if not text.strip():
            fail("brief is empty: %s" % path)
        ident = brief_identity(text)
        if ident is None:
            fail("brief %s names no lane on its first line (`You are <definition> ... lane <id> of run <id>`)" % path)
        tokens = path_tokens(text)
        if not tokens:
            fail("brief %s carries no path token at all: there is nothing to check, so it cannot pass" % path)
        briefs.append((path, text, ident[0], ident[1], tokens))

    roots = {}
    for _path, _text, _definition, lane, _tokens in briefs:
        if lane in dry:
            if lane not in roots:
                got, why = dry_run_roots(dry[lane])
                if got is None:
                    fail("the lane.py spawn --dry-run output for lane %s (%s) %s" % (lane, dry[lane], why))
                roots[lane] = got
        elif lane not in in_session and "all" not in in_session:
            fail("lane %s is named neither by --dry-run LANE=FILE (headless) nor by --in-session: "
                 "the fence check (d) is never skipped by omission" % lane)
    check = None
    if roots:
        check, why = load_check(a.fence)
        if check is None:
            fail(why)
    bad = controls(ledger_path, sections, vault, check)
    if bad:
        fail("a same-run control did not behave: " + "; ".join(bad))

    counts = dict.fromkeys("abcde", 0)
    failed = only_c = queried = headless_n = 0
    append_at = None
    cache = {ledger_path: events}
    for path, text, definition, lane, tokens in briefs:
        fails = {}
        for n, tok, kind, slotted in tokens:
            problem = token_problem(tok, kind, slotted, vault)
            if problem:
                fails.setdefault("a", []).append("line %d: %s: %s" % (n, problem, tok))
        ledger_toks = [(n, tok, kind) for n, tok, kind, _s in tokens if LEDGER.search(tok)]
        if not ledger_toks:
            if definition == "wiki-compile":
                fails.setdefault("b", []).append("a wiki-compile brief carries no run-ledger path")
        elif {ledger_real(tok, kind, vault) for _n, tok, kind in ledger_toks} != {ledger_path}:
            fails.setdefault("b", []).append("ledger path %s differs from the run's ledger %s"
                                             % (", ".join(sorted({t for _n, t, _k in ledger_toks})), ledger_path))
        headless = lane in roots
        headless_n += headless
        if ledger_toks:
            _n, token, kind = ledger_toks[0]
            if "a" in fails or "b" in fails:
                fails.setdefault("c", []).append("not proven: (a) or (b) failed first, so nothing is read "
                                                 "or appended at %s" % token)
                if headless:
                    fails.setdefault("d", []).append("not proven: (a) or (b) failed first")
            else:
                key = os.path.realpath(expand(token, kind, vault))
                if key not in cache:
                    cache[key] = read_events(expand(token, kind, vault))[0]
                found, why = preflight_after_open(cache[key] or [])
                if not found:
                    fails.setdefault("c", []).append("%s at %s" % (why, token))
                    append_at = token
                if headless:
                    queried += 1
                    answer, why = fence_answer(check, lane, token, *roots[lane])
                    if answer is None:
                        fail("lane %s: %s" % (lane, why))
                    if answer[0] != PINNED_ALLOW:
                        fails.setdefault("d", []).append("check() answers %s for the lane's own append at %s: %s"
                                                         % (answer[0], token, answer[1]))
        for hit in index_hits(text, sections):
            fails.setdefault("e", []).append(hit)
        print("brief %s · lane %s · %s · %s · path tokens %d · ledger %s"
              % (os.path.basename(path), lane, definition, "headless" if headless else "in-session",
                 len(tokens), ledger_toks[0][1] if ledger_toks else "none"))
        for check_id in "abcde":
            for line in fails.get(check_id, []):
                print("FAIL (%s) %s %s" % (check_id, lane, line))
            counts[check_id] += check_id in fails
        if fails:
            failed += 1
            only_c += set(fails) == {"c"}

    if failed and only_c == failed and append_at:
        print("NEXT: (a), (b), (d) and (e) pass for every brief; append the preflight event at %s, the "
              "path copied from the brief text, then run this check again" % append_at)
    print("summary: briefs %d · failed %d · (a) %d · (b) %d · (c) %d · (d) %d · (e) %d · fence queried %d"
          " · headless %d · in-session %d · ledger %s"
          % (len(briefs), failed, counts["a"], counts["b"], counts["c"], counts["d"], counts["e"], queried,
             headless_n, len(briefs) - headless_n, ledger_path))
    print("controls: (a) absent parent caught, the run ledger's path passed, unfilled slot caught, quoted spaced and ampersand paths tested whole, quoted -draft paths tested whole, command spans split, prose apostrophes ignored, bare backtick paths kept whole · (b) "
          "differing ledger paths told apart · (c) run_open/preflight order folded both ways · (e) named "
          "(on the index's line and the next) and whole sections caught, clean line passed · (d) %s"
          % ("the pinned %r observed inside the write roots and deny outside them" % PINNED_ALLOW
             if check is not None else "not queried (no headless lane)"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
