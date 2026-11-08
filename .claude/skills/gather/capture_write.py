#!/usr/bin/env python3
"""capture_write.py — the sole write path for /gather captures (gather v3.1).

Mechanises the five write-time rules that were behavioural in v3: budget/ceiling
enforcement (via the run ledger), raw immutability (refuses any existing path),
sanitisation (ingest Step-0 rules, tested), complete provenance frontmatter, and
a capture QUALITY GATE — engines can "succeed" while emitting non-content (an
error stub served as a page, an HTML-dominant body from a crashed converter, a
near-empty fetch), so the write path refuses those bodies; retry with the next
engine, and a body you deliberately accept needs --allow-degraded '<why>' (the
acceptance is stamped into the frontmatter and ledger, and declared in the run
report; a body the gate passes but the capturer knows is damaged takes the same
flag and is stamped "declared"). PLATFORM LANE (tier-3 CLIs):
platform output (JSON/YAML/subtitles) is wrapped VERBATIM in closed fenced
blocks at capture — the gate and sanitiser honour that convention (fence-aware),
and bare unfenced whole-body JSON is refused so the convention is mechanical. Fetching stays with the engines (defuddle/curl/markitdown/Jina, and the attended chrome-burner tab); this
script only turns fetched Markdown into a raw/ file. If this script is missing
or broken the run STOPS and asks — never hand-write captures around it.
BROWSER RUNG (browser-capture-rung design, revision at the pre-start gate): the
engine stays a free string (no allow-list); an engine named chrome-burner (or
"chrome (burner)") is the attended burner Chrome tab, and its captures meet the
ABSTRACT-PAGE RULE on top of the gate: a publisher landing page answers the
burner with an abstract that clears the size floor, so such a body is refused
as abstract-only when the text after its abstract is too short to be an
article, or carries no section structure and no reference list (the measures
and their derivations sit beside ARTICLE_MIN_WORDS below), whatever
--allow-degraded says; the URL is printed for the hand-fetch list
(oa_resolve.py --hand-fetch). Verbs:
    write --url U --engine E --ledger-id ID [--title T] [--slug S] [--vault-root PATH]
          [--resolved-url R] [--probe-result P] [--allow-degraded REASON]
        reads Markdown on stdin; writes raw/<slug>.md; appends to the ledger.
        --resolved-url R records the open copy the body came from (oa_resolve.py)
        as `resolved_url:` beside `source_url:`, which stays the row's own URL.
        --probe-result P is capture_probe.py's result.json for the page. Every
        write records the capture check's stamp, in frontmatter (capture_check:)
        and in its ledger entry: with P, the body on stdin is checked against the
        page the probe fetched, whichever engine produced the body ("suspected
        loss — <findings>", "no loss found by the unit check (<counts>); not
        compared: <what the check does not compare>", or "not run — <why>");
        without P, "not run — no probe result given". The check only warns: no
        result, an unreadable, malformed or failed one, a missing capture_probe.py
        and a check that fails to run are stamped not run, never as no loss, and
        none of them, nor anything the check finds, refuses the write
    check [--engine E] [--url U]
        reads Markdown on stdin; runs the quality gate only (no write, no
        ledger), the abstract-page rule included when E names the burner tab:
        prints PASS (exit 0) or REJECT + reason (exit 3)
    dedup --urls a,b,c | --urls a b c  [--titles 'T1' 'T2']  --control URL [--vault-root PATH]
          [--allow-no-control]
        greps candidate URLs against source_url/converted_from/resolved_url in raw/ + wiki/, and matches
        the arXiv ids and DOIs in those URLs, and each normalised title, against the
        wiki/sources/ + raw/ frontmatter keys (key code loaded from
        ../ingest/dedup_probe.py, never copied — missing, or failing its self-test, exits 2).
        A match prints "ALREADY IN VAULT: <paths> (matched on: <keys>)"; the --control URL
        MUST hit (proof the scan ran — CLAUDE.md §11). A likely-duplicate key runs beside
        the definitive ones and never changes them: the same host (case-folded, a leading
        www. dropped) and the same final path segment (case-folded; a trailing slash,
        .html and .htm dropped; query and fragment ignored) as a raw capture's
        source_url, converted_from or resolved_url prints a second line,
        "<url> ~> likely duplicate of <paths> (same host and final slug ...)": advisory,
        shown at the gate for the owner, never an exclusion (versioned docs, generic
        index pages and query-selected items share such keys). A title naming a review site
        (`... | OpenReview`), on either side of a hit resting on a stripped key alone, prints
        'title "T" ~> paper or its review: <paths> (...)' in place of a match: the same
        kind of advisory line, since a review is never a duplicate and the site's name cannot
        say which the page is

--vault-root defaults to this script's OWN vault (three parents above
.claude/skills/gather/), never the cwd; default or explicit, the root must
contain raw/ + wiki/ or write/dedup refuse to run, so a scan never reads
whatever tree the caller stands in.
"""
import argparse, collections, datetime, json, os, re, sys
from urllib.parse import unquote, urlsplit
import run_ledger

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Beyond those, in a frontmatter value only: C0 line ends and tabs, C1 controls (NEL among them), the
# Unicode line and paragraph separators, surrogates and non-characters. A YAML reader refuses or
# breaks a line at these, and the lookup's reader refuses a page carrying one.
FRONT_UNSAFE = re.compile("[\x00-\x1f\x7f-\x9f\u2028\u2029\ud800-\udfff\ufeff\ufffe\uffff]")
BARE_LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
HTML_TAG = re.compile(r"<[A-Za-z][^>\n]*>")
# A CLOSED fenced block: column-0 opener, same-string closer alone on its line.
# Deliberate bounds: an unclosed opener never matches (no fence privilege on a
# broken premise); a longer/indented closer is not honoured — the platform
# capture path writes exact column-0 pairs, and anything else stays prose.
FENCED_BLOCK = re.compile(r"(?ms)^(?P<fence>`{3,}|~{3,})[^\n]*\n(?P<body>.*?)^(?P=fence)[ \t]*$\n?")


def sanitise(text):
    """Ingest Step-0 cleanup: strip control bytes; defang stray link syntax.

    Fence-aware (platform captures wrap CLI output verbatim in fenced blocks):
    content inside a CLOSED fence is kept byte-exact apart from the control-byte
    strip — Obsidian renders fences verbatim, so defanging there is needless and
    would corrupt platform JSON (nested arrays read as [[ wiki-link openers).
    An unclosed fence gets no privilege: its text is defanged as prose.
    """
    text = CONTROL_CHARS.sub("", text)  # first: no \x00 survives, so the fence
    stash = []                          # placeholders below cannot collide

    def _stash(m):
        stash.append(m.group(0))
        return f"\x00{len(stash) - 1}\x00"
    text = FENCED_BLOCK.sub(_stash, text)
    text = text.replace("[[", r"\[\[")  # stray wiki-link syntax from math/citations

    def _defang(m):
        target = m.group(2)
        if "://" in target or target.startswith(("#", "/", ".")) or "." in target:
            return m.group(0)  # real link — keep
        return f"{m.group(1)} ({target})"  # [text](bareword) — defang
    text = BARE_LINK.sub(_defang, text)
    for i, block in enumerate(stash):
        text = text.replace(f"\x00{i}\x00", block, 1)
    return text


def resolve_vault_root(given):
    """Return a validated vault root; default = this script's own vault.

    The script lives at <vault>/.claude/skills/gather/, so the vault is three
    parents above this file (realpath, so a symlinked install resolves too).
    Whatever the origin, a root missing raw/ or wiki/ raises (exit 2 in main)
    — a moved script or a wrong explicit path must fail loudly, never scan an
    empty tree (the 2026-08-26 known-issues entry: default "." from /tmp).
    """
    here = os.path.dirname(os.path.realpath(__file__))
    root = os.path.normpath(given or os.path.join(here, "..", "..", ".."))
    missing = [d for d in ("raw", "wiki") if not os.path.isdir(os.path.join(root, d))]
    if missing:
        raise ValueError(f"--vault-root {root} lacks {' + '.join(missing)}/ — not a vault root; "
                         "refusing to scan/write a wrong tree (pass --vault-root explicitly)")
    return root


def slug_from(url, title=None):
    base = title or re.sub(r"^[a-z]+://", "", url)
    s = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()[:80].strip("-")
    return s or "capture"


QUALITY_MIN_BYTES = 600
QUALITY_TAG_COUNT = 100     # both tag thresholds must trip before a body is
QUALITY_TAG_RATIO = 0.4     # called HTML-dominant (READMEs with badge HTML pass)
# Platform lane: a fence is inspected as the capture's own payload only when it
# DOMINATES the body — a minority fence is quoted material (a tutorial showing
# an API error example must not be refused). Both judgement-set, unmeasured:
# share 0.5 (a platform capture is a small header + the payload; a quoted
# example is a fraction of its article), tags 30 (hello-world HTML ~10 tags,
# a real served login/error page carries dozens).
QUALITY_FENCE_SHARE = 0.5
QUALITY_FENCE_TAGS = 30
HTML_PAGE_SIG = re.compile(r"(?i)<!DOCTYPE\s+html|<html[\s>]")
# Top-level JSON fields that never carry requested content — error envelopes
# plus response metadata; judgement-set, extend as the platforms teach us.
NONDATA_KEYS = {"error", "errors", "message", "msg", "code", "status", "name",
                "detail", "details", "title", "reason", "success",
                "meta", "metadata", "request_id", "timestamp"}


def _json_payload_reject(payload):
    """Inspect one JSON payload (a dominant fenced platform capture). Returns a
    reason or None. Top-level only — a nested null inside real data is the live
    probes' job, not the gate's; non-JSON (YAML/subtitles) passes through here
    (stdlib has no YAML) and is carried by the size floor + HTML-page signature.
    """
    try:
        obj = json.loads(payload)
    except ValueError:
        return None
    if isinstance(obj, list) and not obj:
        return "empty platform result (JSON [])"
    if isinstance(obj, dict):
        nonempty = {k.lower() for k, v in obj.items() if v not in (None, "", [], {})}
        if nonempty <= NONDATA_KEYS:  # includes the all-empty dict
            named = ", ".join(sorted(nonempty)) or "none"
            return f"platform payload carries no content (non-empty fields: {named})"
    return None


def quality_check(body):
    """Return a rejection reason, or None if the body looks like real content.

    Each check behaves sensibly when its own premise fails: an empty or
    whitespace body is caught by the size floor, a newline-free body gets
    lines >= 1 so the ratio cannot divide by zero, an unclosed fence is simply
    prose, and no pattern here can raise on arbitrary text. False positives
    (a legitimately tiny page, a tutorial dense with literal HTML) go through
    --allow-degraded, declared.

    Platform lane (fenced verbatim CLI output — JSON/YAML/subtitles): closed
    fenced payloads are excluded from the HTML-dominance scan (subtitle markup
    is data, not a crashed converter), and a DOMINANT fence is inspected
    directly — a JSON error/empty payload or a served HTML page (a login wall
    handed to the CLI) is refused.
    """
    text = body.strip()
    if len(text) < QUALITY_MIN_BYTES:
        return f"body too small ({len(text)} bytes < {QUALITY_MIN_BYTES}) — likely a failed fetch"
    head = text[:800]
    if re.search(r"Warning: Target URL returned error \d+", head):
        return "engine error stub ('Target URL returned error') — the page was not captured"
    if re.search(r"^Title: Page Not Found$", head, re.M):
        return "engine returned a Page Not Found shell, not the page"
    if text.startswith(("{", "[")):
        # An all-JSON body is either an engine's API error response served as
        # the page (an error stub can clear the size floor) or platform output missing its fence
        # wrap.
        # Markdown that merely opens with "{"/"[" fails json.loads and passes.
        try:
            json.loads(text)
            return ("body is a bare JSON document, not Markdown — an engine API "
                    "error stub, or unfenced platform output (platform captures "
                    "are fenced; adoption-design runbook step 5)")
        except ValueError:
            pass
    for m in FENCED_BLOCK.finditer(text):
        payload = m.group("body")
        if len(payload) / len(text) < QUALITY_FENCE_SHARE:
            continue  # minority fence — quoted material, not the payload
        reason = _json_payload_reject(payload)
        if reason:
            return reason + " — in the capture's fenced platform payload"
        fence_tags = len(HTML_TAG.findall(payload))
        if HTML_PAGE_SIG.search(payload) and fence_tags >= QUALITY_FENCE_TAGS:
            return (f"fenced payload is an HTML page ({fence_tags} tags, "
                    f"{len(payload) * 100 // len(text)}% of the body) — the "
                    "platform served a page (login wall / error), not data")
    prose = FENCED_BLOCK.sub("", text)
    tags = len(HTML_TAG.findall(prose))
    lines = max(1, prose.count("\n"))
    if tags >= QUALITY_TAG_COUNT and tags / lines >= QUALITY_TAG_RATIO:
        return (f"HTML-dominant body ({tags} tags over {lines} lines) — "
                "the converter emitted markup, not Markdown")
    return None


# ABSTRACT-PAGE RULE (browser-capture-rung design, revision at the pre-start
# gate; the owner's default, kept until the critic gate rules otherwise). The
# burner rung opens only for a row that failed headless and has no open copy
# (same design, "What the revised design solves"), so every burner-tab capture
# is taken to come from a domain that refused headless: the rule applies to an
# engine naming the burner tab, and an engine string that merely mentions it
# ("markitdown of a chrome-burner download") is caught too, the stricter reading.
#
# The rule tests what an article has and a landing page lacks, and names no
# heading. "After the abstract" starts past the paragraph an abstract marker
# opens; with no marker the whole body counts (the lenient reading), and a
# paragraph running past ABSTRACT_MAX_WORDS (a collapsed conversion) is taken
# as the abstract for that many words only. A body is refused as abstract-only
# when
#   1. it carries fewer than ARTICLE_MIN_WORDS words of prose after the
#      abstract, counting neither link text (navigation, related-article lists)
#      nor reference-entry lines (a landing page's reference list is not the
#      article), or
#   2. its text after the abstract carries fewer than ARTICLE_MIN_HEADINGS
#      heading lines and fewer than REFERENCE_MIN_ENTRIES reference-entry lines.
#      A heading is a line shape, never a name: a Markdown heading, a wholly
#      bold line, or a short numbered or all-capitals line. A collapsed
#      conversion (a line longer than COLLAPSED_LINE_CHARS) has no line
#      structure to count, so arm 2 abstains there (its premise fails) and
#      arm 1 decides alone.
# A closed fenced block is quoted material, not the page's own text, and is not
# measured.
# Review these compatibility thresholds on a local corpus containing known full and
# abstract-only captures. The derivation and controls belong with that local record.
BURNER_ENGINE = re.compile(r"(?i)\bchrome\s*[-_ (]\s*burner\b")
# Minimum body words: compatibility default; set by judgement, unmeasured for a new corpus.
ARTICLE_MIN_WORDS = 500
# Minimum headings: compatibility default; set by judgement, unmeasured for a new corpus.
ARTICLE_MIN_HEADINGS = 3
# Minimum reference entries: compatibility default; set by judgement, unmeasured for a new corpus.
REFERENCE_MIN_ENTRIES = 8
# Collapsed-line boundary: compatibility default; set by judgement, unmeasured for a new corpus.
COLLAPSED_LINE_CHARS = 2000
# Abstract word allowance: compatibility default; set by judgement, unmeasured for a new corpus.
ABSTRACT_MAX_WORDS = 400
# Line bounds for a heading and a reference entry: set by judgement, unmeasured.
HEADING_MAX_WORDS = 10
HEADING_MAX_CHARS = 100
REFERENCE_LINE_CHARS = 600
ABSTRACT_MARKER = re.compile(r"(?im)^[ \t>#*_]*abstract\b")
LINK_OR_IMAGE = re.compile(r"!?\[[^\]\n]*\]\([^)\n]*\)")
BARE_URL = re.compile(r"\bhttps?://\S+")
PROSE_WORD = re.compile(r"[^\W\d_][^\W\d_'’-]*")
HEADING_ATX = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+\S")
HEADING_EMPHASIS = re.compile(r"^(\*\*|__)(?:(?!\1).){1,100}\1[ \t]*:?$")
HEADING_NUMBERED = re.compile(r"^(?:\d{1,2}(?:\.\d{1,2})*\.?|[A-Z](?:\.\d{1,2})+\.?|[IVX]{1,4}\.)[ \t]*[A-Z]")
YEAR_TOKEN = re.compile(r"\b(?:1[89]|20)\d{2}[a-z]?\b")
NAME_INITIAL = re.compile(r"\b[A-Z]\.")
PARAGRAPH_BREAK = re.compile(r"\n[ \t\r]*\n")


def is_burner_engine(engine):
    return bool(engine and BURNER_ENGINE.search(engine))


def _is_heading_line(line):
    t = line.strip()
    if not t or len(t) > HEADING_MAX_CHARS:
        return False
    if HEADING_ATX.match(t) or HEADING_EMPHASIS.match(t):
        return True
    words = len(PROSE_WORD.findall(t))
    if HEADING_NUMBERED.match(t) and words <= HEADING_MAX_WORDS and not t.endswith((".", ",", ";")):
        return True
    return re.search(r"[A-Z]{3}", t) is not None and re.search(r"[a-z]", t) is None and 1 <= words <= HEADING_MAX_WORDS


def _is_reference_entry(line):
    t = line.strip()
    return (0 < len(t) <= REFERENCE_LINE_CHARS and YEAR_TOKEN.search(t) is not None
            and ("et al" in t or NAME_INITIAL.search(t) is not None or t.count(",") >= 2))


def article_measures(body):
    """Measure the text after a capture's abstract: the words of prose (link text and
    reference-entry lines not counted), the heading lines, the reference-entry lines and
    the longest line. Keys: words, headings, references, longest_line, abstract_words, marker.

    Premise failures: an empty or all-fenced body measures zeros; a body with no abstract
    marker is measured whole; a marker with nothing after it leaves nothing to measure.
    """
    prose = FENCED_BLOCK.sub("", (body or "").strip() + "\n")
    after, abstract_words = prose, 0
    m = ABSTRACT_MARKER.search(prose)
    if m:
        rest = prose[m.end():]
        first, _nl, tail = rest.partition("\n")
        if not PROSE_WORD.search(first):  # a bare marker line: the abstract is the next paragraph
            rest = re.sub(r"\A(?:[ \t\r]*\n)+", "", tail)
        parts = PARAGRAPH_BREAK.split(rest, maxsplit=1)
        para, after = parts[0], (parts[1] if len(parts) > 1 else "")
        found = list(PROSE_WORD.finditer(para))
        abstract_words = len(found)
        if abstract_words > ABSTRACT_MAX_WORDS:  # a run-on paragraph: only the cap is the abstract
            after = para[found[ABSTRACT_MAX_WORDS - 1].end():] + "\n\n" + after
            abstract_words = ABSTRACT_MAX_WORDS
    lines = after.splitlines()
    refs = [_is_reference_entry(line) for line in lines]
    return {"words": sum(len(PROSE_WORD.findall(_strip_links(line))) for line, ref in zip(lines, refs) if not ref),
            "headings": sum(1 for line in lines if _is_heading_line(line)),
            "references": sum(refs),
            "longest_line": max((len(line) for line in lines), default=0),
            "abstract_words": abstract_words,
            "marker": m is not None}


def _strip_links(text):
    return BARE_URL.sub(" ", LINK_OR_IMAGE.sub(" ", text))


def abstract_only_reason(body, engine):
    """Return the abstract-only refusal for a burner-tab capture that is not an article
    beyond its abstract (the two arms above), else None.

    Premise failures: an empty or unknown engine is not the burner tab, so the rule does
    not apply (the ordinary gate still does); an empty body measures no words and is
    refused (on the write path the size floor refuses it first); a collapsed conversion
    has no line structure, so only the word arm is applied to it.
    """
    if not is_burner_engine(engine):
        return None
    m = article_measures(body)
    lead = "abstract-only: a chrome-burner capture from a domain that refused headless carries "
    if m["words"] < ARTICLE_MIN_WORDS:
        return (lead + f"{m['words']} words of prose after the abstract, fewer than the "
                f"{ARTICLE_MIN_WORDS} an article carries (link text and reference entries not counted)")
    if (m["longest_line"] <= COLLAPSED_LINE_CHARS and m["headings"] < ARTICLE_MIN_HEADINGS
            and m["references"] < REFERENCE_MIN_ENTRIES):
        return (lead + f"no section structure after the abstract ({m['headings']} heading lines, fewer than "
                f"{ARTICLE_MIN_HEADINGS}) and no reference list ({m['references']} reference entries, fewer "
                f"than {REFERENCE_MIN_ENTRIES})")
    return None


# THE CAPTURE CHECK (capture_probe.py): a web page is fetched once and routed on its HTML (a collapsed or
# tabbed block sends it through markitdown, anything else through defuddle on the same copy), and a
# capture is compared with the page the probe fetched. The comparison only warns: every write records
# its stamp (capture_check: in frontmatter and in the ledger entry), and nothing the check finds, no
# missing, unreadable, malformed or failed result and no missing capture_probe.py refuses a write. The
# engine that produced the body plays no part in it.
STAMP_MAX = 900            # characters of a stamp, as capture_probe.STAMP_MAX; set by judgement
CHECK_VERDICTS = ("no loss found", "suspected loss", "not run")   # capture_probe.VERDICTS
# A provenance field name followed by its colon, which a frontmatter reader looking for an engine field
# anywhere on a line would read inside a stamp (as capture_probe.ENGINE_FIELD_LIKE).
ENGINE_FIELD_LIKE = re.compile(r"(?i)(?<![a-z0-9_])(['\"]?)(converted_by|conversion_engine|converter)(['\"]?)[ \t]*:")


def _probe_module():
    """capture_probe.py from this script's own folder, loaded only when a result is to be read (a copy
    of this script without it still writes, its stamp not run); no cache file is written."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "capture_probe.py")
    if not os.path.isfile(path):
        raise ValueError(f"capture_probe.py is missing beside capture_write.py ({path})")
    import importlib.util
    spec = importlib.util.spec_from_file_location("capture_probe", path)
    mod = importlib.util.module_from_spec(spec)
    keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = keep
    return mod


def _one_line(text, limit=300, keep_fields=False):
    """A stamp, reason or title fit for a double-quoted frontmatter value that every YAML reader takes
    the same way: one line, none of the characters a YAML reader refuses or breaks a line at, a double
    quote written as a single one and a backslash as a slash, and bounded (the bound set by judgement;
    None for a title, whose words key it). A stamp or reason never carries a provenance field name
    followed by its colon; a title keeps its colon (keep_fields), since that colon decides its de-dup
    keys."""
    text = re.sub(r"\s+", " ", FRONT_UNSAFE.sub(" ", str(text))).strip().replace('"', "'").replace("\\", "/")
    text = text if limit is None or len(text) <= limit else text[: limit - 1] + "…"
    return text if keep_fields else ENGINE_FIELD_LIKE.sub(lambda m: m.group(1) + m.group(2) + m.group(3) + " -", text)


def capture_check_stamp(a, body):
    """(verdict, stamp): the capture check's warning for this body, recorded and never a reason to
    refuse it. Without --probe-result there is nothing to compare against; with one, capture_probe.py's
    check_stamp compares the body with the page the probe fetched. Any failure on the way is not run,
    never no loss."""
    if not a.probe_result:
        return "not run", "not run — no probe result given"
    if not os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "capture_probe.py")):
        return "not run", "not run — capture_probe.py is missing beside capture_write.py"
    try:
        verdict, stamp, _info = _probe_module().check_stamp(a.probe_result, body, a.url, also_url=a.resolved_url)
    except Exception as exc:                  # check_stamp never raises; a probe that cannot load or run is not run
        return "not run", _one_line(f"not run — the check could not run: {type(exc).__name__}: {exc}", STAMP_MAX)
    if verdict not in CHECK_VERDICTS or not isinstance(stamp, str) or not stamp.startswith(verdict):
        return "not run", _one_line(f"not run — the check gave no stamp it can record ({verdict!r})", STAMP_MAX)
    return verdict, _one_line(stamp, STAMP_MAX)


def write(a):
    body = sys.stdin.read()
    if not body.strip():
        raise ValueError("empty stdin — nothing fetched, nothing written")
    reason = quality_check(body)
    if reason and not a.allow_degraded:
        raise ValueError(f"quality gate: {reason}; retry with the next engine in the chain — "
                         "a body you deliberately accept needs --allow-degraded '<why>', "
                         "declared in the run report")
    abstract = abstract_only_reason(body, a.engine)
    if abstract:  # not overridable: the design writes such a body "only when" it carries an article
        raise ValueError(f"quality gate: {abstract}; refused whatever --allow-degraded says, nothing written. "
                         f"For the hand-fetch list: {a.url} "
                         f"(python3 .claude/skills/gather/oa_resolve.py --hand-fetch '{a.url}')")
    ledger_path = run_ledger.path_for(a.ledger_id)
    data = run_ledger.load(ledger_path)              # missing → FileNotFoundError (exit 2)
    captured = len(data["captures"])
    if captured >= min(data["budget"], run_ledger.HARD_CEILING):
        raise ValueError(f"budget spent ({captured}/{data['budget']}) — refusing to write; "
                         "raise the budget explicitly or stop")
    slug = a.slug or slug_from(a.url, a.title)
    dest = os.path.join(a.vault_root, "raw", f"{slug}.md")
    if os.path.exists(dest):
        raise ValueError(f"{dest} exists — raw files are immutable; pick another --slug")
    verdict, stamp = capture_check_stamp(a, body)   # a warning recorded with the capture, never a refusal
    title = _one_line(a.title or slug, limit=None, keep_fields=True)
    front_lines = ["---",
                   f'title: "{title}"',
                   f"source_url: {a.url}"]
    if a.resolved_url:  # the open copy the body came from; source_url stays the row's own URL
        front_lines.append(f"resolved_url: {a.resolved_url}")
    front_lines += [f"converted_from: {a.url}",
                    f"converted_by: {a.engine}",
                    f"converted_on: {datetime.date.today().isoformat()}"]
    note = _one_line(a.allow_degraded or "", limit=None)
    if reason:  # only reachable with --allow-degraded — stamp the acceptance
        front_lines.append(f'capture_quality: "degraded — {_one_line(reason, limit=None)}; accepted: {note}"')
    elif a.allow_degraded:  # the gate passed; the capturer declares damage the gate cannot see
        front_lines.append(f'capture_quality: "declared — {note}"')
    front_lines.append(f'capture_check: "{stamp}"')
    front = "\n".join(front_lines) + "\n---\n\n"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(front + sanitise(body))
    entry = {"url": a.url, "slug": slug,
             "ts": datetime.datetime.now().isoformat(timespec="seconds")}
    if a.resolved_url:
        entry["resolved_url"] = a.resolved_url
    if reason:
        entry["degraded"] = reason
    elif a.allow_degraded:
        entry["degraded"] = f"declared — {a.allow_degraded}"
    entry["capture_check"] = stamp
    data["captures"].append(entry)
    run_ledger.save(ledger_path, data)
    tag = " · DEGRADED (accepted)" if reason else (" · DEGRADED (declared)" if a.allow_degraded else "")
    print(f"wrote raw/{slug}.md · ledger {len(data['captures'])}/{data['budget']} · capture check: {verdict}{tag}")


def check_verb(a):
    body = sys.stdin.read()
    reason = quality_check(body) or abstract_only_reason(body, a.engine)
    if reason:
        print(f"REJECT: {reason}")
        if reason.startswith("abstract-only"):
            print(f"for the hand-fetch list: {a.url or '(pass --url to name the row)'}")
        sys.exit(3)
    print("PASS: body looks like real content")


def _dedup_keys():
    """Load the arXiv id / DOI / title key logic from the ingest skill's dedup_probe.py — the one
    copy both de-dup probes use. Missing or broken -> exit 2, never 'new'.
    """
    path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", "ingest", "dedup_probe.py"))
    if not os.path.isfile(path):
        raise ValueError(f"de-dup key module missing ({path}) — the arXiv id, DOI and title keys "
                         "cannot run; STOP and ask, never report 'new' without them")
    import importlib.util
    spec = importlib.util.spec_from_file_location("dedup_probe", path)
    mod = importlib.util.module_from_spec(spec)
    keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True   # no cache file beside the ingest skill
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = keep
    bad = mod.self_test()
    if bad:
        raise ValueError("de-dup key self-test failed — " + "; ".join(bad))
    return mod


def _report(label, found):
    if found:
        on = sorted({x for labels in found.values() for x in labels})
        print(f"{label} -> ALREADY IN VAULT: {'; '.join(sorted(found))} (matched on: {', '.join(on)})")
    else:
        print(f"{label} -> new")


def slug_key(url):
    """(host, final slug) of an http(s) URL for the likely-duplicate key, else None: the host
    case-folded with a leading www. dropped; the last path segment percent-decoded and case-folded,
    a trailing slash and a .html or .htm ending dropped; query and fragment ignored. A URL with no
    path segment (a site's root) gives no key."""
    try:
        parts = urlsplit(url.strip().strip("\"'"))
        host = (parts.hostname or "").lower()
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    seg = unquote(parts.path.rstrip("/").rsplit("/", 1)[-1]).casefold()
    for ending in (".html", ".htm"):
        if seg.endswith(ending):
            seg = seg[: -len(ending)]
            break
    return (host, seg) if seg else None


def dedup(a):
    # accept comma-joined, space-separated (nargs), or mixed: a single accepted form fails as soon
    # as its restatement drifts
    urls = [u.strip() for tok in (a.urls or []) for u in re.split(r"[,\s]+", tok) if u.strip()]
    titles = [t.strip() for t in (a.titles or []) if t.strip()]   # one argument per title, never split
    if not urls and not titles:
        raise ValueError("dedup needs --urls a,b,c (or --urls a b c) and/or --titles 'T1' 'T2'")
    if not a.control and not a.allow_no_control:
        raise ValueError("dedup needs --control <known-present URL> (proof the scan runs); "
                         "--allow-no-control only for a provably fresh vault, and say so")
    dp = _dedup_keys()
    targets = urls + ([a.control] if a.control else [])
    hits = {u: [] for u in targets}
    slugs = collections.defaultdict(set)   # (host, final slug) -> {(raw path, field)}: the advisory key
    key = re.compile(r"^(source_url|converted_from|resolved_url):", re.I)  # resolved_url: the open copy a capture came from
    for root in ("raw", "wiki"):
        top = os.path.join(a.vault_root, root)
        for dirpath, _dirs, files in os.walk(top):
            for name in files:
                if not name.endswith(".md"):
                    continue
                fp = os.path.join(dirpath, name)
                try:
                    with open(fp, encoding="utf-8") as fh:
                        head = fh.read(4096)
                        # The de-dup keys live in frontmatter. If the opening --- is not closed
                        # inside the fast window, extend once (64 KB hard stop) rather than
                        # silently scanning a truncated head (§12: bounds need stated headroom).
                        if head.startswith("---") and "\n---" not in head[3:]:
                            head += fh.read(61440)
                except OSError:
                    continue
                rel = os.path.relpath(fp, a.vault_root)
                for line in head.splitlines():
                    m = key.match(line)
                    if not m:
                        continue
                    for u in targets:
                        if u and u in line:
                            hits[u].append(rel)
                    if root == "raw":   # the advisory key reads raw captures' own provenance fields
                        k = slug_key(line[m.end():])
                        if k:
                            slugs[k].add((rel, m.group(1).lower()))
    if a.control and not hits[a.control]:
        raise ValueError(f"control URL {a.control} not found — the scan cannot be trusted; "
                         "fix the control or the scan before claiming clean")
    # arXiv id, DOI and normalised title keys over wiki/sources/ and raw/ frontmatter: a paper compiled
    # from a local PDF carries no source_url, so the URL key alone would pass a later URL capture of it
    # as new. Scoped to source pages and raw files: a concept page named
    # after a paper is not a copy of it.
    idx = dp.build_index(a.vault_root, roots=("wiki/sources", "raw"))
    if idx["unreadable"]:
        raise ValueError("unreadable under the key scan: " + "; ".join(idx["unreadable"][:5]))
    if titles and idx["files"] and not idx["title"]:
        raise ValueError(f"title index empty over {idx['files']} files — the title key searched "
                         "nothing, so a title reported new is unproven")
    for u in urls:
        found = {p: ["url"] for p in set(hits[u])}
        for p, labels in dp.lookup(idx, arx=dp.arxiv_ids(u), doi=dp.dois(u)).items():
            found.setdefault(p, []).extend(labels)
        _report(u, found)
        k = slug_key(u)
        likely = sorted({p for p, _f in slugs.get(k, ())} - set(found)) if k else []
        if likely:   # a second line, never the verdict: the line above stays the definitive answer
            fields = sorted({f for p, f in slugs[k] if p in likely})
            print(f"{u} ~> likely duplicate of {'; '.join(likely)} (same host and final slug: {k[0]} · {k[1]}; "
                  f"from {', '.join(fields)}; advisory, never definitive: show it at the gate for the owner, "
                  "never exclude it)")
    for t in titles:
        key = dp.title_key(t)
        if key is None:
            print(f'title "{t}" -> not keyed (under {dp.TITLE_MIN_TOKENS} tokens once normalised); '
                  "check it by eye")
            continue
        found = dp.lookup(idx, titles=[key])
        # A review site's name cannot say whether a page is the paper or its reviews, and a review is never
        # a duplicate (CLAUDE.md section 3): a hit resting on a stripped key alone is shown, never settled.
        stripped_only = found and not any("title" in labels for labels in found.values())
        if stripped_only and (dp.names_review_site(t) or set(found) & idx["review_site"]):
            on = sorted({x for labels in found.values() for x in labels})
            print(f'title "{t}" ~> paper or its review: {"; ".join(sorted(found))} (matched on: {", ".join(on)}; '
                  "a review site's name cannot say which; advisory, never definitive: show it at the gate for "
                  "the owner, never exclude it)")
        else:
            _report(f'title "{t}"', found)
    n = len(dp.SELF_TEST)
    print(f"keys indexed: {idx['files']} files · {len(idx['arxiv'])} arXiv ids · {len(idx['doi'])} DOIs"
          f" · {len(idx['title'])} titles · key self-test {n}/{n} · {len(slugs)} host-and-slug keys over raw/ (advisory)")


def main():
    ap = argparse.ArgumentParser(description="Sole write path for /gather captures (v3.1).")
    ap.add_argument("verb", choices=["write", "dedup", "check"])
    ap.add_argument("--url"), ap.add_argument("--title"), ap.add_argument("--slug")
    ap.add_argument("--engine", default="unknown",
                    help="the engine that fetched the body (a free string); an engine naming "
                         "chrome-burner meets the abstract-page rule")
    ap.add_argument("--ledger-id", dest="ledger_id")
    ap.add_argument("--urls", nargs="+"), ap.add_argument("--control")
    ap.add_argument("--titles", nargs="+", metavar="TITLE",
                    help="dedup: candidate titles, one argument each (never split), matched as "
                         "normalised titles against wiki/sources/ and raw/ frontmatter")
    ap.add_argument("--allow-no-control", action="store_true")
    ap.add_argument("--allow-degraded", dest="allow_degraded", metavar="REASON",
                    help="write despite a quality-gate rejection, or declare damage the gate "
                         "passed; REASON is stamped into frontmatter + ledger either way "
                         "('degraded — ...' or 'declared — ...') and must be declared in the "
                         "run report (never lifts the abstract-page rule)")
    ap.add_argument("--resolved-url", dest="resolved_url", metavar="URL",
                    help="write: the open copy the body came from (oa_resolve.py), recorded as "
                         "resolved_url: beside source_url:")
    ap.add_argument("--probe-result", dest="probe_result", metavar="PATH",
                    help="write: capture_probe.py's result.json for this page; the body is checked "
                         "against the page the probe fetched and the check's stamp recorded as "
                         "capture_check: in frontmatter and ledger, a warning that never refuses the "
                         "write (without it, or with a result that cannot be read, the stamp is "
                         "'not run — <why>')")
    ap.add_argument("--vault-root", default=None,
                    help="vault to scan/write (default: this script's own vault; "
                         "must contain raw/ + wiki/)")
    a = ap.parse_args()
    try:
        if a.verb in ("write", "dedup"):   # check reads stdin only — no root needed
            a.vault_root = resolve_vault_root(a.vault_root)
        if a.verb == "write":
            if not (a.url and a.ledger_id):
                raise ValueError("write needs --url and --ledger-id")
            if a.allow_degraded is not None and not a.allow_degraded.strip():
                raise ValueError("--allow-degraded needs a non-empty reason")
            if a.allow_degraded is not None and re.search(r"[\r\n]", a.allow_degraded):
                raise ValueError("--allow-degraded needs a one-line reason "
                                 "(a line break would inject frontmatter)")
            if a.resolved_url is not None and not re.fullmatch(r"https?://\S+", a.resolved_url):
                raise ValueError("--resolved-url needs one http(s) URL with no whitespace "
                                 "(a newline would inject frontmatter)")
            write(a)
        elif a.verb == "check":
            check_verb(a)
        else:
            dedup(a)
    except FileNotFoundError as e:
        print(f"capture_write: ledger missing ({e}) — STOP and ask the owner; "
              "never hand-write a capture around this script", file=sys.stderr)
        sys.exit(2)
    except ValueError as e:
        print(f"capture_write: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
