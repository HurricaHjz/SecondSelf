#!/usr/bin/env python3
"""dedup_probe.py - the ingest de-dup pre-flight in one read-only call, and the key logic that
gather's `capture_write.py dedup` loads from here (one copy, so the two probes cannot drift).

Why: a paper compiled from a local PDF carries no `source_url`, so a later URL capture of the
same paper would pass a probe keyed on name, hash and URL alone as NEW; this one reads the arXiv
id, the DOI and the title too.

Keys (a match on any one lists the path as a possible duplicate):
  name   a file of the candidate's name in a raw/ subfolder
  hash   the first 16 hex chars of the candidate's sha256, anywhere in a wiki/sources/ file
  url    a candidate URL, anywhere in a wiki/sources/ file or a raw/ subfolder text file
  arxiv  an arXiv id, version dropped, from source_url / converted_from / url / doi / arxiv /
         arxiv_id frontmatter of wiki/sources/ and raw/ Markdown
  doi    a DOI, case-folded, from doi / source_url / converted_from / url frontmatter
  title  the normalised title: case-folded; one leading page label (Paper:, Source:, ...) and
         [arXiv id] dropped; hyphens, dashes and underscores unified with spaces;
         punctuation and stop words stripped; keyed only at TITLE_MIN_TOKENS tokens or more
  name-stripped title
         an additional key less a leading one-token name followed by an en/em dash or a spaced
         hyphen/double hyphen; matched only against a full title, in either direction
  suffix-stripped title
         a title less a trailing site or venue suffix (`... | arXiv`, `... - PMC`; see
         strip_site_suffix), matched against a title that is that text in full, in either
         direction, and never against another stripped title: pages of one family
         ("X docs - Sessions", "X docs - Guardrails") share a stem and must not meet on it
Full-title keys always stay. Neither kind of stripped key matches another stripped key.
The candidate's keys come from its own frontmatter plus --url, --title and --doi.

Usage:
  python3 dedup_probe.py raw/<file> [--url U] [--title T] [--doi D] [--vault-root PATH]
Prints one `CANDIDATE <path> [keys]` line per possible duplicate, or `NEW`, then a `keys:` line
and a `controls:` line. Exit 0 = the probe ran; exit 2 = `PROBE FAILED: <what>`, which is never NEW.
Reads only: it creates, modifies, moves and deletes nothing.

The lookup verb answers "is this work in the vault?" for one cited work or a list, from the source
pages alone:
  python3 dedup_probe.py --lookup [--title T] [--author A] [--year Y] [--arxiv ID] [--doi D] [--url U]
                         [--vault-root PATH]
  python3 dedup_probe.py --lookup --list FILE [--vault-root PATH]
It reads the frontmatter of the wiki/sources/ pages and nothing else. Raw files are not searched: a
work captured under raw/ and not yet compiled to a source page gets no verdict from its raw file, and
every run's output says that raw files are not searched.
FILE holds one JSON object per line with the keys id, title, author, year, arxiv, doi and url
(title, arxiv, doi and url take a string or a list of strings; author is the first author's name;
year is four digits; id is the caller's label); blank lines and lines starting with # are skipped.
Each work gets one verdict block, by what its keys can prove:
  MATCH <page> (<key>)       an identifier the citation gives in a canonical form equals one the
                             page asserts as the work's own (doi / arxiv / arxiv_id frontmatter, in a
                             canonical form), on a Paper:, Source: or unlabelled page, the only such
                             page, and every identifier the citation gives is one of the page's own
                             wherever the page holds that family (one conflicting identifier is enough)
  CANDIDATE <page> (<keys>)  any other hit, each key with the reason it cannot identify the work:
                             a title, alias or author-year key (lossy); an identifier read from a
                             location field (source_url, resolved_url, converted_from, url, a URL in
                             sources) or guessed from text or a URL path; an equal URL; a companion
                             page; a conflict; several pages
  NO MATCH (keys tried; coverage)   no key hit; the coverage counts, per kind of key tried, the source
                             pages a key of that kind can reach (own frontmatter and a file-name
                             author-year), so the reader sees what the answer cannot exclude, and it
                             says that raw files are not searched
  UNKEYED (reasons)          the citation gave no usable key
A discarded key is named on a `discarded:` line. Frontmatter is parsed whole with PyYAML's BaseLoader
(every scalar a string), so a value is YAML's own reading or none; the lookup alone needs PyYAML (the
de-dup probe above does not) and exits 2 without it.
Nothing is printed before every premise holds: PyYAML importable; every source page readable, with a
frontmatter block that closes and parses as a YAML mapping, with no key given twice, no merge key (a
plain << or a key tagged !!merge; a quoted or !!str-tagged << is an ordinary key), no NEL, LS or PS
character, and each field the lookup reads holding a value or a list of values; a well-formed list; a
passing self-test and same-run controls. Anything else exits 2 with `PROBE FAILED: <what>`, naming
every page that fails, and no verdict.
"""
import argparse, hashlib, json, os, re, sys, unicodedata, urllib.parse

# Strip one conventional leading page label from a title. Keep Review because a review is
# filed as its own page and must not collapse onto the paper it reviews.
TITLE_LABELS = ("source", "paper", "skill", "repo", "gist", "pack", "handbook")
# Stop words: set by judgement, unmeasured. Applied to both sides, so it only has to be one list.
STOP_WORDS = frozenset("a an the of in on at to for from by with and or as is are via into vs versus".split())
# A title keys only at this many tokens after normalisation: set by judgement, unmeasured
# (a one- or two-word title such as "README" or "Introduction" names many documents).
TITLE_MIN_TOKENS = 3
# A trailing site or venue suffix sits after the title's last spaced pipe or dash (hyphen, en dash
# or em dash with whitespace on both sides; an unspaced hyphen joins words, as in Plug-and-Play).
SUFFIX_DELIM = re.compile(r"\s+[|\-–—]\s+")
# The longest segment stripped on shape alone, in content tokens: set by judgement, unmeasured as a
# site-name length (a site or venue name runs one to three words once stop words go, e.g. "ACM
# Digital Library"). Its cost is bounded, not assumed: a stripped key never matches another stripped
# key, so a genuine short subtitle costs at most a CANDIDATE against a title that is its stem in full.
# Keep the full-title key alongside a stripped key; stripping before keying can collapse
# distinct titles or lose a valid full-title match.
SUFFIX_MAX_TOKENS = 3
# A final segment or a leading name that says the page is a review is never cut: CLAUDE.md section 3
# makes a review its own category, never a duplicate of the paper it reviews, and a cut would key it
# exactly as that paper. The whole segment is compared, so a venue that merely holds the word (a
# journal's "Annual Reviews") still cuts. The list is set by judgement, unmeasured; its cost is
# bounded, since a key not cut costs at most a CANDIDATE against the same title elsewhere.
REVIEW_SEGMENTS = frozenset(("review", "reviews", "peer review", "peer reviews"))
# A review site's name is no such word, and neither is a record's host: each says where a page lives,
# and a paper's own page lives there too. So a title naming one keeps its stripped key, and a hit
# resting on that key alone stays a candidate to inspect (names_review_site). The list is set by
# judgement, unmeasured.
REVIEW_SITES = frozenset(("openreview", "openreview net", "open review"))
# Frontmatter window: the same bounds as capture_write.py's scan (a 4 KB read, extended once to
# 64 KB when the opening --- is not closed inside it).
FRONT_WINDOW, FRONT_CAP = 4096, 65536
# Text extensions the url key reads under raw/ subfolders: set by judgement - a PDF or other
# binary holds its links in compressed streams, so a plain-text URL match there is noise.
TEXT_EXTS = (".md", ".markdown", ".txt", ".html", ".htm", ".json", ".jsonl", ".csv", ".xml", ".yaml", ".yml")

URL_KEYS = ("source_url", "converted_from")
ARXIV_KEYS = ("source_url", "converted_from", "url", "doi", "arxiv", "arxiv_id")
DOI_KEYS = ("doi", "source_url", "converted_from", "url")
HOST_KEYS = ("source_url", "converted_from", "url")

_ID = r"(\d{4}\.\d{4,5}|[a-z][a-z-]*(?:\.[a-z]{2})?/\d{7})(?:v\d+)?(?!\d)"
ARXIV_IN_TEXT = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf|html|format)/|ar5iv(?:\.labs\.arxiv)?\.org/(?:abs|html)/"
    r"|alphaxiv\.org/(?:abs|overview)/|huggingface\.co/papers/|arxiv[:.]\s?)" + _ID, re.I)
ARXIV_BARE = re.compile(r"^" + _ID + r"$", re.I)
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>?#]+)", re.I)
DASHES = re.compile(r"[\-‐-―−_]+")
LABEL = re.compile(r"^(?:%s)\s*:\s*" % "|".join(TITLE_LABELS))
ARXIV_PREFIX = re.compile(r"^\[\s*" + _ID + r"\s*\]\s*", re.I)
# A short name is one token (set by judgement, unmeasured), beginning with a letter or digit.
# Anchor it before dash normalisation so a dash later in a multiword title stays part of it.
NAME_PREFIX = re.compile(r"^[^\W_][\w.+-]*(?:\s*[–—]\s*|\s+--?\s+)(?=\S)")


def arxiv_ids(value, bare=False):
    """arXiv ids in a string, version dropped; `bare` also accepts a lone id (an arxiv: field)."""
    value = value or ""
    ids = {m.group(1).lower() for m in ARXIV_IN_TEXT.finditer(value)}
    if bare:
        m = ARXIV_BARE.match(value.strip())
        if m:
            ids.add(m.group(1).lower())
    return ids


def dois(value):
    """DOIs in a string, case-folded. Behind a doi.org resolver the whole remainder is the DOI;
    inside any other URL path the suffix ends at the next path segment."""
    v = urllib.parse.unquote(value or "")
    out = set()
    for m in DOI_RE.finditer(v):
        before = v[:m.start()]
        d = m.group(1)
        if "://" in before and not re.search(r"doi\.org/$", before, re.I):
            d = "/".join(d.split("/", 2)[:2])
        d = d.rstrip(".,;:)]}")
        if d.split("/", 1)[1:] and d.split("/", 1)[1]:
            out.add(d.lower())
    return out


class TitleKey(str):
    """The full normalised title, with optional `name_stripped` and `suffix_stripped` keys.
    A str, so capture_write.py dedup carries the extra forms into lookup() unchanged."""
    suffix_stripped = None
    name_stripped = None


def _prepare(title):
    t = unicodedata.normalize("NFKC", title or "").casefold().strip()
    t = LABEL.sub("", t, count=1)
    return ARXIV_PREFIX.sub("", t, count=1)


def _content_tokens(text):
    t = DASHES.sub(" ", text)
    t = re.sub(r"[^\w\s]", " ", t)
    return [w for w in t.split() if w not in STOP_WORDS]


def normalise_title(title):
    return " ".join(_content_tokens(_prepare(title)))


def strip_name_prefix(title):
    """An additional key after a leading name, or None below the existing title token floor, or when
    the name says the page is a review (REVIEW_SEGMENTS).
    Labels and arXiv prefixes go first. The full key is retained even when this key is too short."""
    prepared = _prepare(title)
    named = NAME_PREFIX.match(prepared)
    if named and " ".join(_content_tokens(named.group(0))) in REVIEW_SEGMENTS:
        return None
    rest, count = NAME_PREFIX.subn("", prepared, count=1)
    tokens = _content_tokens(rest)
    return " ".join(tokens) if count and len(tokens) >= TITLE_MIN_TOKENS else None


def host_labels(urls):
    """The host labels of each http(s) URL, less `www` and the top-level label
    (https://pmc.ncbi.nlm.nih.gov/x -> pmc, ncbi, nlm, nih); anything unparseable is skipped."""
    out = set()
    for u in urls:
        u = (u or "").strip()
        if not u.lower().startswith(("http://", "https://")):
            continue
        try:
            host = urllib.parse.urlsplit(u).hostname or ""
        except ValueError:
            continue
        out |= {x for x in host.split(".")[:-1] if x and x != "www"}
    return out


def strip_site_suffix(title, hosts=()):
    """The normalised title less a trailing site or venue suffix, or None when it carries none.
    Keyed on the segment's property, never on a list of site names: the final segment after a
    spaced pipe or dash is a suffix when the rest keys on its own (TITLE_MIN_TOKENS) and the segment
    either names a host label of a URL the same record carries (`hosts`), or runs at most
    SUFFIX_MAX_TOKENS content tokens and shares no content word with the rest. A segment that says the
    page is a review (REVIEW_SEGMENTS) keeps no stripped form."""
    t = _prepare(title)
    found = list(SUFFIX_DELIM.finditer(t))
    if not found:
        return None
    cut = found[-1]
    rest, tail = _content_tokens(t[:cut.start()]), _content_tokens(t[cut.end():])
    if len(rest) < TITLE_MIN_TOKENS or not tail:
        return None
    if " ".join(tail) in REVIEW_SEGMENTS:
        return None
    names_host = re.sub(r"[\W_]+", "", t[cut.end():]) in set(hosts)
    if names_host or (len(tail) <= SUFFIX_MAX_TOKENS and not set(tail) & set(rest)):
        return " ".join(rest)
    return None


def names_review_site(title):
    """Whether a title's final segment or leading name is a review site's (REVIEW_SITES): the page may be
    the paper or its reviews, and the title cannot say which."""
    t = _prepare(title)
    found = list(SUFFIX_DELIM.finditer(t))
    named = NAME_PREFIX.match(t)
    return (bool(found) and " ".join(_content_tokens(t[found[-1].end():])) in REVIEW_SITES
            or bool(named) and " ".join(_content_tokens(named.group(0))) in REVIEW_SITES)


def title_key(title, hosts=()):
    """The TitleKey of a title, or None under TITLE_MIN_TOKENS tokens once normalised; `hosts` are
    host_labels() of the URLs the same record carries."""
    n = normalise_title(title)
    if len(n.split()) < TITLE_MIN_TOKENS:
        return None
    key = TitleKey(n)
    key.suffix_stripped = strip_site_suffix(title, hosts)
    key.name_stripped = strip_name_prefix(title)
    return key


def read_head(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        head = fh.read(FRONT_WINDOW)
        if head.startswith("---") and "\n---" not in head[3:]:
            head += fh.read(FRONT_CAP - FRONT_WINDOW)
    return head


def frontmatter(text):
    """Flat `key: value` pairs from a leading --- block; {} when there is none or it never closes."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    out = {}
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1).lower(), m.group(2).strip()
        if val[:1] in ("\"", "'") and val.count(val[0]) >= 2:
            val = val[1:val.index(val[0], 1)]
        else:
            val = re.sub(r"\s+#.*$", "", val)
        out.setdefault(key, val)
    return out


def keys_of(fm):
    """(arxiv ids, DOIs, TitleKey or None) one frontmatter carries."""
    arx, doi = set(), set()
    for k in ARXIV_KEYS:
        if fm.get(k):
            arx |= arxiv_ids(fm[k], bare=k in ("arxiv", "arxiv_id"))
    for k in DOI_KEYS:
        if fm.get(k):
            doi |= dois(fm[k])
    return arx, doi, title_key(fm.get("title", ""), host_labels(fm.get(k, "") for k in HOST_KEYS))


def walk_files(top, errors):
    def onerror(e):
        errors.append(f"{getattr(e, 'filename', top)}: {e.strerror or e}")
    for dirpath, dirs, files in os.walk(top, onerror=onerror):
        dirs.sort()
        for name in sorted(files):
            yield dirpath, os.path.join(dirpath, name)


def build_index(vault_root, roots=("wiki/sources", "raw"), skip=()):
    """Map each arXiv id, DOI, full title and separate stripped keys to relative Markdown paths."""
    idx = {"arxiv": {}, "doi": {}, "title": {}, "title_stripped": {}, "title_name_stripped": {},
           "review_site": set(), "files": 0, "unreadable": [], "missing": []}
    skip = {os.path.realpath(p) for p in skip}
    for root in roots:
        top = os.path.join(vault_root, root)
        if not os.path.isdir(top):
            idx["missing"].append(root)
            continue
        for _dir, fp in walk_files(top, idx["unreadable"]):
            if not fp.endswith(".md") or os.path.realpath(fp) in skip:
                continue
            try:
                fm = frontmatter(read_head(fp))
            except OSError as e:
                idx["unreadable"].append(f"{fp}: {e}")
                continue
            idx["files"] += 1
            rel = os.path.relpath(fp, vault_root)
            arx, doi, title = keys_of(fm)
            for a in arx:
                idx["arxiv"].setdefault(a, set()).add(rel)
            for d in doi:
                idx["doi"].setdefault(d, set()).add(rel)
            if title:
                idx["title"].setdefault(str(title), set()).add(rel)
                if title.suffix_stripped:
                    idx["title_stripped"].setdefault(title.suffix_stripped, set()).add(rel)
                if title.name_stripped:
                    idx["title_name_stripped"].setdefault(title.name_stripped, set()).add(rel)
                if names_review_site(fm.get("title", "")):
                    idx["review_site"].add(rel)
    return idx


def lookup(idx, arx=(), doi=(), titles=()):
    """{path: [labels]} for every indexed path sharing an arXiv id, DOI or title key. A title matches
    an indexed title in full ("title"); either stripped form matches only a full title, in either
    direction ("suffix-stripped title" or "name-stripped title"). No two stripped forms meet."""
    hits = {}
    for a in sorted(arx):
        for p in idx["arxiv"].get(a, ()):
            hits.setdefault(p, []).append(f"arxiv {a}")
    for d in sorted(doi):
        for p in idx["doi"].get(d, ()):
            hits.setdefault(p, []).append(f"doi {d}")
    for t in sorted(t for t in titles if t):
        for p in idx["title"].get(t, ()):
            hits.setdefault(p, []).append("title")
        for attribute, index_name, label in (("suffix_stripped", "title_stripped", "suffix-stripped title"),
                                             ("name_stripped", "title_name_stripped", "name-stripped title")):
            s = getattr(t, attribute, None)
            matches = set(idx.get(index_name, {}).get(t, ()))
            if s:
                matches.update(idx["title"].get(s, ()))
            for p in sorted(matches):
                hits.setdefault(p, []).append(label)
    return hits


# The extractors' same-run positive control: each call must give exactly the expected value.
SELF_TEST = [
    ("arxiv", "https://arxiv.org/pdf/2307.03172v3", {"2307.03172"}),
    ("arxiv", "10.48550/arXiv.2307.03172", {"2307.03172"}),
    ("arxiv", "https://arxiv.org/abs/hep-th/9901001", {"hep-th/9901001"}),
    ("arxiv", "https://example.test/2307.03172", set()),
    ("doi", "https://doi.org/10.1162/TACL_A_00638", {"10.1162/tacl_a_00638"}),
    ("doi", "https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/x", {"10.1162/tacl_a_00638"}),
    ("title", "Paper: Lost in the Middle — How Language Models Use Long Contexts",
     "lost middle how language models use long contexts"),
    ("title", "Lost-in-the-Middle: How Language-Models Use Long Contexts",
     "lost middle how language models use long contexts"),
    ("title", "Review: Lost in the Middle", "review lost middle"),
    ("title", "Source: METHOD — Calibrated Reasoning and Confidence Estimates",
     "method calibrated reasoning confidence estimates"),
    ("title", "Paper: METHOD - Calibrated Reasoning and Confidence Estimates",
     "method calibrated reasoning confidence estimates"),
    ("name-stripped", "Source: METHOD — Calibrated Reasoning and Confidence Estimates",
     "calibrated reasoning confidence estimates"),
    ("name-stripped", "METHOD – Calibrated Reasoning and Confidence Estimates",
     "calibrated reasoning confidence estimates"),
    ("name-stripped", "METHOD -- Calibrated Reasoning and Confidence Estimates",
     "calibrated reasoning confidence estimates"),
    ("name-stripped", "[2307.03172] METHOD — Calibrated Reasoning and Confidence Estimates",
     "calibrated reasoning confidence estimates"),
    ("name-stripped", "Lost in the Middle — How Language Models Use Long Contexts", None),
    ("stripped", "Lost in the Middle: How Language Models Use Long Contexts | arXiv",
     "lost middle how language models use long contexts"),
    ("stripped", "Lost in the Middle: How Language Models Use Long Contexts - PMC",
     "lost middle how language models use long contexts"),
    ("stripped", "Large Language Models - How They Use Long Contexts", None),
    ("stripped", "Attention Heads in Transformer Models - Attention Sinks", None),
    ("stripped", "Lost in the Middle: How Language Models Use Long Contexts | Peer review", None),
    ("stripped", "Lost in the Middle: How Language Models Use Long Contexts - Reviews", None),
    ("name-stripped", "Review — Calibrated Reasoning and Confidence Estimates", None),
]


def self_test(fns=None):
    fns = {"arxiv": arxiv_ids, "doi": dois, "title": normalise_title, "stripped": strip_site_suffix,
           "name-stripped": strip_name_prefix, **(fns or {})}
    return [f"{n}({i!r}) gave {fns[n](i)!r}, expected {e!r}" for n, i, e in SELF_TEST if fns[n](i) != e]


def default_vault_root():
    # this file sits at <vault>/.claude/skills/ingest/, so the vault is three parents up
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def fail(msg):
    print(f"PROBE FAILED: {msg}")
    sys.exit(2)


# ------------------------------------------------------------------------------------------------
# The lookup verb (--lookup): "is this work in the vault?"
# A phrase grep misses hyphenated page names and page names that omit the author, and a key that
# cannot identify a work must never read as though it did. Each key is therefore graded by what it
# can prove: only a canonical identifier that one page asserts as the work's own can MATCH; every
# lossy key and location stays a CANDIDATE; a miss reports the coverage of the keys it tried, never
# that the work is not held. It reads source pages only: raw files are not searched, and its output
# says so. The de-dup probe above and capture_write.py are unchanged by it.
# ------------------------------------------------------------------------------------------------

# A value in an identity field is the page's own claim about the work's identifier.
IDENTITY_FIELDS = ("doi", "arxiv", "arxiv_id")
# A value in a location field records where the text came from, which need not be the work the page
# describes: several pages compiled from one repository snapshot share one source_url.
LOCATION_FIELDS = ("source_url", "resolved_url", "converted_from", "url")
LIST_FIELDS = ("aliases", "authors", "author", "sources") + IDENTITY_FIELDS + LOCATION_FIELDS
LOOKUP_FIELDS = ("title", "year") + LIST_FIELDS
# Leading title labels that name a kind of page. Only a WORK_LABELS page (or an unlabelled one) is
# taken as the work itself: a Repo:, Review: or Blog: page can carry the identifier of the paper it
# accompanies, so an identifier on it stays a candidate. Both lists set by judgement over the labels
# in use; an unknown leading word before a colon is not a label.
PAGE_LABELS = ("paper", "source", "repo", "review", "blog", "post", "doc", "skill", "gist", "pack",
               "handbook", "release")
WORK_LABELS = ("paper", "source")
ARXIV_HOSTS = ("arxiv.org", "www.arxiv.org", "export.arxiv.org")
DOI_RESOLVERS = ("doi.org", "dx.doi.org", "www.doi.org")
NAME_SUFFIXES = frozenset(("jr", "sr", "ii", "iii", "iv"))
INITIALS = re.compile(r"(?:[^\W\d_]\.-?){1,4}|[^\W\d_]")
# A slug author-year: <surname>[-<surname>]-<yyyy>-... with a year from 1900 to 2099 (the range set by
# judgement: it keeps names such as model-4-0613 out). Read only from a page's file name and aliases,
# and only where its frontmatter gives no author-year.
SLUG_AUTHOR_YEAR = re.compile(r"^([a-z]+)(?:-([a-z]+))?-((?:19|20)\d{2})(?:-|$)")
LIST_KEYS = ("id", "title", "author", "year", "arxiv", "doi", "url")
VERDICTS = ("MATCH", "CANDIDATE", "NO MATCH", "UNKEYED")
# The negative control's keys: no page can carry them.
NONCE_CITATION = {"title": ["Lookup control qzvmbxk sentinel nonce membership"],
                  "doi": ["10.0000/lookup-control-qzvmbxk"], "arxiv": ["0000.00000"]}

_DOI_STRICT = re.compile(r"10\.\d{4,9}/\S+")
_ARXIV_DOI = re.compile(r"10\.48550/arxiv\.(.+)", re.I)
_ARXIV_PATH = re.compile(r"/(?:abs|html|format)/(.+?)/?|/pdf/(.+?)(?:\.pdf)?/?")


class LookupPremise(Exception):
    """A premise of the lookup failed: the run prints PROBE FAILED and no verdict."""


def _arxiv_canonical(s):
    m = ARXIV_BARE.match(s)
    return {("arxiv", m.group(1).lower())} if m and m.end() == len(s) else set()


def _doi_canonical(s):
    if not _DOI_STRICT.fullmatch(s):
        return set()
    m = _ARXIV_DOI.fullmatch(s)
    return _arxiv_canonical(m.group(1)) if m else {("doi", s.lower())}


def canonical_ids(value):
    """{(family, id)} when the whole value is one identifier in a supported canonical form, else set().
    Families: `arxiv` (version dropped, lower-cased) and `doi` (lower-cased; an arXiv DOI is an arxiv
    id). Supported: a bare arXiv id, `arXiv:<id>`, an arxiv.org abs/pdf/html URL, `10.48550/arXiv.<id>`,
    a bare DOI, `doi:<doi>` and a doi.org resolver URL. Nothing is cut away: a trailing character, a
    query, a fragment, another host or a path segment after the identifier makes the value not
    canonical, so it can only feed the lossy extractors above (arxiv_ids, dois) as a candidate."""
    v = (value or "").strip()
    low = v.lower()
    if low.startswith(("http://", "https://")):
        if any(c.isspace() for c in v):
            return set()
        try:
            u = urllib.parse.urlsplit(v)
            host, port = (u.hostname or "").lower(), u.port
        except ValueError:
            return set()
        if u.query or u.fragment or port or u.username:
            return set()
        if host in ARXIV_HOSTS:
            m = _ARXIV_PATH.fullmatch(u.path)
            return _arxiv_canonical(m.group(1) or m.group(2)) if m else set()
        if host in DOI_RESOLVERS:
            return _doi_canonical(urllib.parse.unquote(u.path[1:]))
        return set()
    for prefix, parse in (("arxiv:", _arxiv_canonical), ("doi:", _doi_canonical)):
        if low.startswith(prefix):
            rest = v[len(prefix):].lstrip(" ")
            return set() if any(c.isspace() for c in rest) else parse(rest)
    if any(c.isspace() for c in v):
        return set()
    return _arxiv_canonical(v) or _doi_canonical(v)


def guessed_ids(value, bare=False):
    """{(family, id)} the lossy extractors find in a value: the de-dup keys, never an identity."""
    found = {("arxiv", a) for a in arxiv_ids(value, bare=bare)}
    return found | {("doi", d) for d in dois(value) if not _ARXIV_DOI.fullmatch(d)}


def url_key(value):
    """An http(s) URL normalised for an equality test (scheme https, host lower-cased, a default port,
    the fragment and a trailing slash dropped; path and query kept as given), or None."""
    v = (value or "").strip()
    if not v.lower().startswith(("http://", "https://")) or any(c.isspace() for c in v):
        return None
    try:
        u = urllib.parse.urlsplit(v)
        host, port = (u.hostname or "").lower(), u.port
    except ValueError:
        return None
    if not host:
        return None
    netloc = host + (f":{port}" if port and port not in (80, 443) else "")
    return urllib.parse.urlunsplit(("https", netloc, u.path.rstrip("/"), u.query, ""))


def fold(text):
    t = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in t if not unicodedata.combining(c)).casefold()


def surname(name):
    """A first author's surname, diacritics folded and letters only: the text before a comma
    ("Last, First"), else the last word that is not an initial or a suffix; None when none is left."""
    n = re.sub(r"\([^)]*\)", " ", fold(name))
    n = re.sub(r"\bet\s+al\b\.?", " ", n)
    if "," in n:
        n = n.split(",", 1)[0]
    words = [w for w in n.split() if not INITIALS.fullmatch(w) and w.strip(".") not in NAME_SUFFIXES]
    s = re.sub(r"[\W\d_]+", "", words[-1]) if words else ""
    return s or None


def year_of(value):
    v = value.strip() if isinstance(value, str) else ""
    return v if re.fullmatch(r"\d{4}", v) else None


def slug_author_years(slug):
    """{(surname, year)} a slug shaped <surname>[-<surname>]-<yyyy>-... gives; both readings of two
    hyphenated words (one double-barrelled surname, or a first author then a second)."""
    m = SLUG_AUTHOR_YEAR.match(fold(slug))
    if not m:
        return set()
    a, b, y = m.groups()
    return {(a + b, y), (a, y)} if b else {(a, y)}


def page_label(title):
    m = re.match(r"\s*([A-Za-z]+)\s*:\s*\S", unicodedata.normalize("NFKC", title or ""))
    return m.group(1).lower() if m and m.group(1).lower() in PAGE_LABELS else None


# The lookup's frontmatter reader. The flat frontmatter() above reads no list and returns {} for a block that
# never closes, which the de-dup probe tolerates; a lookup that read it so would report a broken page as one that
# holds no key. This reader finds a block's boundaries (a first line ---, then the next line ---) and parses the
# whole block with PyYAML's BaseLoader, so every value is YAML's own reading of it and every scalar stays a string:
# an identifier is never turned into a number, a date or a boolean. A block that does not parse, or whose top level
# is not a mapping, is a failed premise (LookupPremise: exit 2 and no verdict), never metadata absence; so is a
# PyYAML that cannot be imported, since the lookup has no other reader. Beyond the parse, the reader refuses the
# forms YAML readers part on, so no one reader's choice decides a key: a key given twice (YAML forbids it; PyYAML
# keeps the last), a merge key, which is a key YAML 1.1 resolves to the merge tag (a plain, untagged <<, or a key
# tagged !!merge: YAML 1.1 merges the mapping it names into this one, YAML 1.2 reads an ordinary key), and a NEL,
# LS or PS character (YAML 1.1 readers, PyYAML among them, break a line there; YAML 1.2 readers read text). A <<
# quoted or tagged !!str is an ordinary key to both, and is read. The fields the lookup reads must each hold a
# value or a list of values. It reads source pages only, each of which must open with a block; raw files are not
# read at all.
_OPEN = re.compile(rb"---[ \t]*\r?\n")
_CLOSE = re.compile(rb"(?m)^---[ \t]*\r?$")
_BREAKS_BY_VERSION = re.compile("[\x85\U00002028\U00002029]")
_SURROGATE = re.compile("[\ud800-\udfff]")
_YAML_PARTS = ("BaseLoader", "MappingNode", "SequenceNode", "ScalarNode")
_MERGE_TAG = "tag:yaml.org,2002:merge"


def _yaml():
    """PyYAML, imported when the lookup first needs it and never at the top: the de-dup probe and capture_write.py
    load this file and need no PyYAML. Raises LookupPremise when it cannot be imported or lacks a part the reader
    uses; the lookup never falls back to another reader."""
    try:
        import yaml
    except Exception as e:  # ImportError when it is absent; anything else when an install is broken
        raise LookupPremise(f"PyYAML cannot be imported by {sys.executable or 'this python3'} ({type(e).__name__}: {e}); "
                            "the lookup reads frontmatter only by parsing it with PyYAML's BaseLoader and has no other "
                            "reader, so install PyYAML for this python3 or run the lookup with one that has it")
    missing = [p for p in _YAML_PARTS if not hasattr(yaml, p)]
    if not hasattr(getattr(yaml, "reader", None), "ReaderError"):
        missing.append("reader.ReaderError")
    if not hasattr(getattr(yaml, "BaseLoader", None), "add_implicit_resolver"):
        missing.append("BaseLoader.add_implicit_resolver")
    if missing:
        raise LookupPremise(f"PyYAML {getattr(yaml, '__version__', '(no version)')} lacks {', '.join(missing)}, which the "
                            "lookup's frontmatter reader uses")
    return yaml


_LOADERS = {}


def _loader(yaml):
    """PyYAML's BaseLoader with YAML 1.1's merge-key resolver added (the one SafeLoader carries: a plain << resolves to
    the merge tag), so a key node carries the merge tag exactly where SafeLoader would merge: a plain, untagged <<, or a
    key tagged !!merge. A << quoted or tagged !!str keeps the string tag. The tag marks the node and nothing else:
    BaseLoader's constructor has no merge step, so every value it builds is the one BaseLoader builds."""
    cls = _LOADERS.get(yaml)
    if cls is None:
        try:
            cls = type("LookupLoader", (yaml.BaseLoader,), {})
            cls.add_implicit_resolver(_MERGE_TAG, re.compile(r"^(?:<<)$"), ["<"])
        except Exception as e:
            raise LookupPremise(f"PyYAML {getattr(yaml, '__version__', '(no version)')}: BaseLoader takes no merge-key "
                                f"resolver ({type(e).__name__}: {e}), which the lookup's frontmatter reader uses")
        _LOADERS[yaml] = cls
    return cls


def _parse_reason(e, yaml, block):
    """PyYAML's reason a block did not parse, on one line: its context and problem with the block line and column,
    a reader error's character and line, or any other exception's own words."""
    problem, mark = getattr(e, "problem", None), getattr(e, "problem_mark", None)
    if problem:
        context = getattr(e, "context", None)
        return ((f"{context}: " if context else "") + problem
                + (f" (block line {mark.line + 1}, column {mark.column + 1})" if mark is not None else ""))
    if isinstance(e, yaml.reader.ReaderError) and isinstance(e.character, int):
        return (f"the character U+{e.character:04X} (block line {block.count(chr(10), 0, e.position) + 1}), which YAML "
                f"does not allow unescaped ({e.reason})")
    return f"{type(e).__name__}: {' '.join(str(e).split())}"[:300]


def _kind(value):
    """What a parsed YAML value is, in words (one level deep: a recursive alias must not recurse here)."""
    if isinstance(value, dict):
        return "a mapping"
    if isinstance(value, list):
        inner = next((x for x in value if not isinstance(x, str)), None)
        return "a list" if inner is None else "a list holding " + ("a mapping" if isinstance(inner, dict) else "a list")
    return "a single value"


def read_front_block(path, shown=None):
    """The text of a source page's leading frontmatter block, which runs from a first line --- (after any byte-order
    mark) to the next line ---. Every source page must have one. Raises LookupPremise for an unreadable page, a page
    that does not open with a line --- ending in LF or CR LF, a block that never closes and a block that is not
    UTF-8; a page is never read as one holding no key."""
    shown = shown or path
    try:
        with open(path, "rb") as fh:
            data = fh.read(FRONT_WINDOW)
            if data.startswith(b"\xef\xbb\xbf"):
                data = data[3:]
            if data.startswith(b"---") and not _CLOSE.search(data, 3):
                data += fh.read(FRONT_CAP - FRONT_WINDOW)
    except OSError as e:
        raise LookupPremise(f"{shown}: cannot be read ({e.strerror or e})")
    m = _OPEN.match(data)
    end = _CLOSE.search(data, m.end()) if m else None
    body = data[m.end():end.start() if end else len(data)] if m else b""
    if not m:
        raise LookupPremise(f"{shown}: no frontmatter block (a source page opens with a line --- ending in LF or CR LF)")
    if not end:
        within = f" within its first {FRONT_CAP // 1024} KB" if len(data) >= FRONT_CAP else ""
        raise LookupPremise(f"{shown}: the frontmatter block never closes{within}")
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        raise LookupPremise(f"{shown}: the frontmatter block is not UTF-8")


def _check_keys(node, shown, yaml):
    """Raises LookupPremise for a key given twice in any mapping of the block (YAML does not allow it; PyYAML would
    keep the last), for two top-level spellings of one lookup field (DOI beside doi), and for a top-level merge key:
    a key node _loader tagged as a merge (a plain, untagged <<, or a key tagged !!merge), never one by its text, so a
    << quoted or tagged !!str, an ordinary key to YAML 1.1 and 1.2 alike, is read."""
    stack, seen = [node], set()
    while stack:
        n = stack.pop()
        if id(n) in seen:
            continue
        seen.add(id(n))
        if isinstance(n, yaml.SequenceNode):
            stack += n.value
        elif isinstance(n, yaml.MappingNode):
            names = {}
            for k, v in n.value:
                stack += [k, v]
                if not isinstance(k, yaml.ScalarNode):
                    continue  # a list or a mapping as a key has already failed the parse (an unhashable key)
                name = k.value.lower() if n is node and k.value.lower() in LOOKUP_FIELDS else k.value
                if name in names:
                    raise LookupPremise(f"{shown}: the key {k.value!r} is given twice"
                                        + (f" (also as {names[name]!r})" if names[name] != k.value else "")
                                        + ("" if n is node else " in a nested mapping")
                                        + ", which YAML does not allow in one mapping (PyYAML would keep the last)")
                names[name] = k.value
                if n is node and k.tag == _MERGE_TAG:
                    what = "<<" if k.value == "<<" else f"{k.value!r} tagged !!merge"
                    raise LookupPremise(f"{shown}: a merge key {what} at the top level, which YAML readers read "
                                        f"differently (YAML 1.1 merges the mapping it names, YAML 1.2 reads a key named "
                                        f"{k.value}); write the fields out")


def parse_front_fields(block, shown):
    """The LOOKUP_FIELDS a frontmatter block carries, read from PyYAML's BaseLoader parse of the whole block: title
    and year as strings ("" when empty), the rest as lists of strings (a string becomes a one-item list, "" none; a
    list keeps its empty items, so a list's first author is its first item). Keys are matched in lower case. An
    empty block, or one of comments alone, carries no field. Raises LookupPremise, naming the block and
    the reason, for a NEL, LS or PS character, a block PyYAML does not parse (its own reason: a scanner, parser,
    composer or constructor error, or any other), a top level that is not a mapping, a key given twice or a merge
    key (_check_keys), a lookup field holding a mapping, or a list holding a list or a mapping (title and year: any
    list), and a value holding a UTF-16 surrogate half, which an escape can name and no character is."""
    yaml = _yaml()
    loader_class = _loader(yaml)
    bad = _BREAKS_BY_VERSION.search(block)
    if bad:
        raise LookupPremise(f"{shown}: the character U+{ord(bad.group()):04X} (block line "
                            f"{block.count(chr(10), 0, bad.start()) + 1}), which YAML 1.1 readers such as PyYAML read as "
                            "a line break and YAML 1.2 readers as text, so the block has no one reading; remove it, or "
                            "write it as an escape in a double-quoted value")
    try:
        loader = loader_class(block)
        try:
            # yaml.load(block, Loader=yaml.BaseLoader) is these two steps; the node is kept for _check_keys
            node = loader.get_single_node()
            data = loader.construct_document(node) if node is not None else None
        finally:
            loader.dispose()
    except Exception as e:  # any failure to parse, a YAMLError or not (an escape past U+10FFFF raises ValueError)
        raise LookupPremise(f"{shown}: the frontmatter does not parse as YAML: {_parse_reason(e, yaml, block)}")
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise LookupPremise(f"{shown}: the frontmatter is not a mapping (YAML reads {_kind(data)} there)")
    _check_keys(node, shown, yaml)
    out = {}
    for key, value in data.items():
        field = key.lower()
        if field not in LOOKUP_FIELDS:
            continue
        where = f"{shown}: {key}"
        if field in ("title", "year"):
            if not isinstance(value, str):
                raise LookupPremise(f"{where}: {_kind(value)} where one value belongs")
            values = [value]
        else:
            if isinstance(value, str):
                value = [value] if value else []
            elif not isinstance(value, list) or any(not isinstance(x, str) for x in value):
                raise LookupPremise(f"{where}: {_kind(value)}, where a value or a list of values belongs")
            values = value
        half = next((h for h in map(_SURROGATE.search, values) if h), None)
        if half:
            raise LookupPremise(f"{where}: U+{ord(half.group()):04X}, a UTF-16 surrogate half, which an escape can name "
                                "and no character is")
        out[field] = value
    return out


class Record:
    """What one frontmatter record offers the lookup, and why any field it carries gives no key."""

    def __init__(self, fields, slug=None):
        # ids: canonical identifiers (identity or location); lossy: what the de-dup extractors read from
        # every value, canonical or not, for the candidate-only route
        self.ids, self.lossy, self.urls, self.unusable = [], [], [], []
        self.author_year, self.aliases = [], []
        self.title_text = fields.get("title", "")
        self.label = page_label(self.title_text)
        self.author_input = self.url_input = self.alias_input = None
        # every URL the record carries, with whether it is itself a canonical identifier (a doi.org or
        # arxiv.org URL), so the url control can choose the verdict that URL is owed
        self.url_inputs = []
        loc = [(f, v) for f in LOCATION_FIELDS for v in fields.get(f, []) if v.strip()]
        loc += [("sources", v) for v in fields.get("sources", []) if v.lower().startswith(("http://", "https://"))]
        ident = [(f, v) for f in IDENTITY_FIELDS for v in fields.get(f, []) if v.strip()]
        for strength, pairs in (("identity", ident), ("location", loc)):
            for f, v in pairs:
                canon = canonical_ids(v)
                self.ids += [(fam, i, strength, f) for fam, i in sorted(canon)]
                lossy = guessed_ids(v, bare=f in ("arxiv", "arxiv_id"))
                self.lossy += [(fam, i, f) for fam, i in sorted(lossy)]
                u = url_key(v)
                if u:
                    self.urls.append((u, f))
                    self.url_input = self.url_input or v
                    self.url_inputs.append((v, bool(canon)))
                if strength == "identity" and not canon and not lossy:
                    self.unusable.append(f"{f}: no identifier" + (" (a URL)" if u else ""))
        self.own = {}
        for fam, i, _s, _f in self.ids:
            self.own.setdefault(fam, set()).add(i)
        self.title = title_key(self.title_text, host_labels(v for _f, v in loc)) if self.title_text else None
        if not self.title_text:
            self.unusable.append("title: none")
        elif self.title is None:
            self.unusable.append(f"title: under {TITLE_MIN_TOKENS} tokens once normalised")
        for a in fields.get("aliases", []):
            k = title_key(a)
            if k:
                self.aliases.append(k)
                self.alias_input = self.alias_input or a
        names = fields.get("authors") or fields.get("author") or []
        s, y = (surname(names[0]) if names else None), year_of(fields.get("year"))
        if s and y:
            self.author_year.append((s, y, "frontmatter"))
            self.author_input = (names[0], y)
        else:
            if names or fields.get("year"):
                self.unusable.append("author-year: " + ("no year" if not fields.get("year") else
                                                         "the year is not four digits" if not y else
                                                         "no authors" if not names else "no surname read"))
            if slug is not None:
                for sl in [slug] + list(fields.get("aliases", [])):
                    self.author_year += [(a, yy, "slug") for a, yy in sorted(slug_author_years(sl))]

    def families(self):
        fams = {fam for fam, *_ in self.ids} | {fam for fam, *_ in self.lossy}
        if self.title:
            fams.add("title")
        if self.aliases:
            fams.add("alias")
        if self.author_year:
            fams.add("author-year")
        if self.urls:
            fams.add("url")
        return fams


class LookupIndex:
    """One pass over wiki/sources/ (raw files are not read): every key mapped to the source pages
    carrying it, with the coverage of usable keys counted by page as the pass goes."""

    FAMILIES = ("arxiv", "doi", "title", "alias", "author-year", "url")

    def __init__(self):
        self.ids, self.lossy, self.titles, self.stripped = {}, {}, {}, {}
        self.name_stripped = {}
        self.author_year, self.urls = {}, {}
        self.pages, self.records, self.label, self.own = [], {}, {}, {}
        # coverage as page sets, so a page is counted once however many routes reach it: own_cov[family]
        # holds the pages whose own frontmatter (or file name, for a slug author-year) gives a usable key of
        # that family
        self.own_cov = {f: set() for f in self.FAMILIES}
        self.identity_cov = {"arxiv": set(), "doi": set()}
        self.slug_cov = set()
        self.why_none = {k: set() for k in ("title_none", "title_short", "author-year", "id_field")}

    def add(self, target, rec):
        for fam, i, strength, f in rec.ids:
            self.ids.setdefault((fam, i), []).append((target, strength, f))
        for fam, i, f in rec.lossy:
            self.lossy.setdefault((fam, i), []).append((target, f))
        if rec.title:
            self.titles.setdefault(str(rec.title), []).append((target, "title"))
            if rec.title.suffix_stripped:
                self.stripped.setdefault(rec.title.suffix_stripped, []).append(target)
            if rec.title.name_stripped:
                self.name_stripped.setdefault(rec.title.name_stripped, []).append(target)
        for k in rec.aliases:
            self.titles.setdefault(str(k), []).append((target, "alias"))
        for s, y, how in rec.author_year:
            self.author_year.setdefault((s, y), []).append((target, how))
        for u, f in rec.urls:
            self.urls.setdefault(u, []).append((target, f))

    def add_page(self, rel, rec):
        self.pages.append(rel)
        self.records[rel], self.label[rel], self.own[rel] = rec, rec.label, rec.own
        self.add(rel, rec)
        for fam in rec.families():
            self.own_cov[fam].add(rel)
        for fam, _i, strength, _f in rec.ids:
            if strength == "identity":
                self.identity_cov[fam].add(rel)
        if rec.author_year and rec.author_year[0][2] == "slug":
            self.slug_cov.add(rel)
        for why in rec.unusable:
            self.why_none["title_none" if why.startswith("title: none") else "title_short" if why.startswith("title:")
                          else "author-year" if why.startswith("author-year:") else "id_field"].add(rel)

    def coverage(self):
        """Per kind of key, the source pages it can reach, from unions of page sets: {kind: {"pages": all
        reached, ...}}, with identity (arxiv, doi), title and alias (title or alias) and slug (author-year)
        beside. The coverage line and the index summary both print these, so they cannot disagree."""
        o, out = self.own_cov, {}
        for kind, fams in (("arxiv", ("arxiv",)), ("doi", ("doi",)), ("title or alias", ("title", "alias")),
                           ("author-year", ("author-year",)), ("url", ("url",))):
            out[kind] = {"pages": len(set().union(*(o[f] for f in fams)))}
        for fam in ("arxiv", "doi"):
            out[fam]["identity"] = len(self.identity_cov[fam])
        out["title or alias"].update(title=len(o["title"]), alias=len(o["alias"]))
        out["author-year"]["slug"] = len(self.slug_cov)
        return out


def build_lookup_index(vault):
    """The LookupIndex of a vault's source pages, built once per run; raw files are not read. Raises
    LookupPremise when wiki/sources/ holds no page, or any entry under it cannot be read or any page
    parsed, naming every one that fails (never only the first few)."""
    idx = LookupIndex()
    errors, pages = [], []
    for _d, fp in walk_files(os.path.join(vault, "wiki", "sources"), errors):
        if fp.endswith(".md"):
            pages.append(fp)
    if errors:
        raise LookupPremise(f"{len(errors)} entries under wiki/sources/ cannot be read: " + "; ".join(errors))
    if not pages:
        raise LookupPremise("wiki/sources/ holds no Markdown page - the lookup would search nothing")
    problems, records = [], {}
    for fp in pages:
        rel = os.path.relpath(fp, vault).replace(os.sep, "/")
        try:
            fields = parse_front_fields(read_front_block(fp, rel), rel)
        except LookupPremise as e:
            problems.append(str(e))
            continue
        rec = Record(fields, slug=os.path.splitext(os.path.basename(fp))[0])
        rec.fields_present = tuple(k for k, v in fields.items() if v)
        records[rel] = rec
    if problems:
        raise LookupPremise(f"{len(problems)} of {len(pages)} source pages cannot be read or parsed, so their "
                            "keys are unknown: " + "; ".join(problems))
    for rel in sorted(records):
        idx.add_page(rel, records[rel])
    return idx


def parse_citation(cit):
    """The keys one citation gives: canonical identifiers, the identifiers the lossy extractors read from
    every supplied value, title keys, URL keys and an author-year, with a reason for every supplied value
    that gives no key."""
    k = {"strict": [], "lossy": [], "titles": [], "urls": [], "author_year": None}
    discarded = []
    urls = [u for u in (cit.get("url") or []) if u and u.strip()]
    for flag in ("arxiv", "doi", "url"):
        for v in cit.get(flag) or []:
            v = (v or "").strip()
            if not v:
                discarded.append(f"--{flag} is empty")
                continue
            canon = canonical_ids(v)
            lossy = guessed_ids(v, bare=flag == "arxiv")
            k["strict"] += [(fam, i, flag) for fam, i in sorted(canon)]
            k["lossy"] += [(fam, i, flag, v) for fam, i in sorted(lossy)]
            u = url_key(v) if flag == "url" else None
            if u:
                k["urls"].append(u)
            if not canon and not lossy and not u:
                discarded.append(f'--{flag} "{v}" gives no ' + ("identifier" if flag != "url" else "identifier and is not an http(s) URL"))
    hosts = host_labels(urls)
    for t in cit.get("title") or []:
        if not (t or "").strip():
            discarded.append("--title is empty")
            continue
        key = title_key(t, hosts)
        if key:
            k["titles"].append(key)
        else:
            discarded.append(f'--title "{t}" is under {TITLE_MIN_TOKENS} tokens once normalised, so it keys nothing')
    a, y = (cit.get("author") or "").strip(), (cit.get("year") or "").strip()
    if a or y:
        s, yy = (surname(a) if a else None), (year_of(y) if y else None)
        if s and yy:
            k["author_year"] = (s, yy)
        else:
            discarded.append(f'--author "{a}" without --year gives no author-year key' if a and not y else
                             f'--year "{y}" without --author gives no author-year key' if y and not a else
                             f'--author "{a}" gives no surname' if not s else f'--year "{y}" is not four digits')
    return k, discarded


def lookup_work(idx, cit):
    """(verdict lines, keys, discarded) for one citation against an index."""
    keys, discarded = parse_citation(cit)
    ev = {}

    def add(target, text, ident=False):
        ev.setdefault(target, []).append((text, ident))

    cit_ids = {}
    for fam, i, _src in keys["strict"]:
        cit_ids.setdefault(fam, set()).add(i)
    # the canonical route: a canonical identifier equal to one a page carries in canonical form
    strict_hit = set()
    for fam, i, _src in keys["strict"]:
        for t, strength, f in idx.ids.get((fam, i), ()):
            strict_hit.add(t)
            if strength == "identity":
                add(t, f"{fam} {i} = the page's {f}:", True)
            else:
                add(t, f"{fam} {i} from the page's {f}: a location, not the work's identity")
    # the lossy route, for pages the canonical route did not reach: equal only once the de-dup
    # extractors have cut or read the values (a truncated DOI, a DOI from a URL path, an arXiv-shaped
    # path on another host), so a candidate at most
    for fam, i, src, raw in keys["lossy"]:
        for t, f in idx.lossy.get((fam, i), ()):
            if t not in strict_hit:
                add(t, f"{fam} {i} equal only after lossy extraction (the citation's --{src} \"{raw}\", "
                       f"{f} of the page): not a canonical identity")
    for key in keys["titles"]:
        for t, kind in idx.titles.get(str(key), ()):
            add(t, f"{kind}: a lossy key")
        for t in idx.stripped.get(str(key), ()):
            add(t, "suffix-stripped title: a lossy key")
        if key.suffix_stripped:
            for t, kind in idx.titles.get(key.suffix_stripped, ()):
                add(t, f"suffix-stripped {kind}: a lossy key")
        for t in idx.name_stripped.get(str(key), ()):
            add(t, "name-stripped title: a lossy key")
        if key.name_stripped:
            for t, kind in idx.titles.get(key.name_stripped, ()):
                add(t, f"name-stripped {kind}: a lossy key")
    if keys["author_year"]:
        s, y = keys["author_year"]
        for t, how in idx.author_year.get((s, y), ()):
            add(t, f"author-year {s} {y} ({how}): a lossy key")
    for u in keys["urls"]:
        for t, f in idx.urls.get(u, ()):
            add(t, f"url = {f} of the page: a shared location, never an identity")

    conflicts = {}
    for t in ev:
        own = idx.own.get(t, {})
        # per identifier, not per family: every identifier the citation gives must be one of the page's own
        # wherever the page holds that family, so one equal identifier never vouches for a different one
        conflicts[t] = [f"the citation's {fam} {', '.join(sorted(cit_ids[fam] - own[fam]))} against the page's "
                        f"{', '.join(sorted(own[fam]))}" for fam in sorted(cit_ids)
                        if own.get(fam) and cit_ids[fam] - own[fam]]
    pages = set(idx.pages)
    eligible = [t for t in ev if t in pages and any(x for _t, x in ev[t]) and not conflicts[t]
                and idx.label.get(t) in (None,) + WORK_LABELS]
    lines = []
    for t in sorted(ev, key=lambda p: (not (len(eligible) == 1 and p == eligible[0]), p)):
        texts = list(dict.fromkeys(x for x, _i in ev[t]))
        if len(eligible) == 1 and t == eligible[0]:
            ident = [x for x, i in ev[t] if i]
            rest = [x for x in texts if x not in ident]
            lines.append(f"MATCH {t} ({'; '.join(dict.fromkeys(ident))}"
                         + (f"; also {'; '.join(rest)}" if rest else "") + ")")
            continue
        why = []
        if conflicts[t]:
            why.append("conflict: " + "; ".join(conflicts[t]))
        if any(i for _x, i in ev[t]):
            lab = idx.label.get(t)
            if lab not in (None,) + WORK_LABELS:
                why.append(f"the page is labelled {lab.capitalize()}:, which can describe a companion of the work")
            if t in eligible:
                why.append(f"the identifiers point at {len(eligible)} pages, so none is singled out")
        lines.append(f"CANDIDATE {t} ({'; '.join(texts + why)})")
    if not lines:
        if keys["strict"] or keys["lossy"] or keys["titles"] or keys["urls"] or keys["author_year"]:
            lines.append(f"NO MATCH (keys tried: {keys_tried(keys)}; coverage: {coverage_text(idx, keys)})")
        else:
            lines.append("UNKEYED (no usable key: " + ("; ".join(discarded) or "the citation gives none") + ")")
            return lines, keys, discarded
    if discarded:
        lines.append("discarded: " + "; ".join(discarded))
    return lines, keys, discarded


def keys_tried(keys):
    out = [f"{fam} {i} (canonical, from --{src})" for fam, i, src in keys["strict"]]
    strict = {(fam, i) for fam, i, _s in keys["strict"]}
    out += [f"{fam} {i} (lossy, from --{src})" for fam, i, src, _v in keys["lossy"] if (fam, i) not in strict]
    out += [f'title "{t}"' for t in keys["titles"]]
    if keys["author_year"]:
        out.append("author-year " + " ".join(keys["author_year"]))
    out += [f"url {u}" for u in keys["urls"]]
    return ", ".join(out)


# Printed on every NO MATCH line and on every run's index line: what the answer cannot exclude.
RAW_NOT_SEARCHED = "raw files are not searched (source-page mode: only wiki/sources/ is read)"


def coverage_text(idx, keys):
    """The coverage of the kinds of key a citation tried: per kind, the source pages a key of that kind can
    reach (LookupIndex.coverage: unions of page sets, a file-name author-year included; field presence is not
    coverage), why other pages give none, and that raw files are not searched."""
    cv, n, why = idx.coverage(), len(idx.pages), idx.why_none
    fams = {f for f, *_r in keys["strict"]} | {f for f, *_r in keys["lossy"]}
    parts = [f"{fam} on {cv[fam]['pages']} ({cv[fam]['identity']} asserted in the page's own identity field)"
             for fam in ("arxiv", "doi") if fam in fams]
    if fams:
        parts.append(f"{len(why['id_field'])} pages carry a doi/arxiv field that gives no identifier")
    if keys["titles"]:
        t = cv["title or alias"]
        parts.append(f"title or alias on {t['pages']} (title {t['title']}, alias {t['alias']}; "
                     f"{len(why['title_short'])} titles under {TITLE_MIN_TOKENS} tokens, {len(why['title_none'])} untitled)")
    if keys["author_year"]:
        a = cv["author-year"]
        parts.append(f"author-year on {a['pages']} ({a['slug']} from the file name or an alias only; "
                     f"{len(why['author-year'])} pages' authors or year unusable)")
    if keys["urls"]:
        parts.append(f"url on {cv['url']['pages']}")
    parts.append(RAW_NOT_SEARCHED)
    return f"of {n} source pages, " + "; ".join(parts)


def index_summary(idx):
    """The index line: what was read, that raw files are not searched and, per kind of key, the pages a key of
    that kind can reach, from the same LookupIndex.coverage counts the coverage line prints."""
    cv = idx.coverage()
    t, a, u = cv["title or alias"], cv["author-year"], cv["url"]
    return (f"index: {len(idx.pages)} source pages read and parsed · {RAW_NOT_SEARCHED} · pages a key of each kind "
            f"reaches: arxiv {cv['arxiv']['pages']} (identity {cv['arxiv']['identity']}) · "
            f"doi {cv['doi']['pages']} (identity {cv['doi']['identity']}) · "
            f"title or alias {t['pages']} (title {t['title']}, alias {t['alias']}) · "
            f"author-year {a['pages']} (slug only {a['slug']}) · url {u['pages']}")


def lines_at(lines, target):
    """The MATCH and CANDIDATE lines naming one target."""
    return [ln for ln in lines if ln.startswith((f"MATCH {target} (", f"CANDIDATE {target} ("))]


def _work_pages(idx, evs):
    """The work pages (Paper:, Source: or unlabelled) asserting one identifier as their own in an identity
    field: the pages a lookup by that identifier alone can single out."""
    return sorted({t for t, strength, _f in evs if strength == "identity"
                   and idx.label.get(t) in (None,) + WORK_LABELS})


def _owed(idx, cit, target):
    """The verdict a lookup by one key owes a target: MATCH where the key is a canonical identifier the
    target alone, among work pages, asserts as its own; any other key owes CANDIDATE."""
    for fam, i, _src in parse_citation(cit)[0]["strict"]:
        if _work_pages(idx, idx.ids.get((fam, i), ())) == [target]:
            return "MATCH"
    return "CANDIDATE"


def control_plans(idx):
    """The same-run controls the index's evidence calls for, one per kind of evidence it holds: a citation
    of one key a target holds, the verdict each target is owed, and a marker the target's evidence text
    must carry (the route that reached it). Returns (plans, notes), each plan (name, citation, {target:
    verdict}, marker, what the key is); a kind the index does not hold is a note (n/a), never a plan."""
    plans, notes = [], []

    def plan(name, found, why_none):
        if found:
            plans.append(found)
        else:
            notes.append(f"{name} n/a ({why_none})")

    # canonical identifiers: one a single work page asserts (owed MATCH), one several work pages assert (each
    # owed CANDIDATE, and no MATCH anywhere), one a page holds without asserting it as the work's (CANDIDATE)
    unique = shared = other = None
    for (fam, i), evs in sorted(idx.ids.items()):
        work = _work_pages(idx, evs)
        rest = sorted({t for t, _s, _f in evs} - set(work))
        if len(work) == 1 and not unique:
            unique = ("identity", {fam: [i]}, {work[0]: "MATCH"}, f"{fam} {i} = the page's", f"its own {fam} {i}")
        if len(work) > 1 and not shared:
            shared = ("shared identifier", {fam: [i]}, dict.fromkeys(work, "CANDIDATE"), "so none is singled out",
                      f"their {fam} {i}")
        if rest and not other:
            other = ("identifier not asserted as the work's", {fam: [i]}, {rest[0]: "CANDIDATE"}, f"{fam} {i}",
                     f"its {fam} {i}")
    plan("identity", unique, "no page alone asserts a canonical identifier")
    plan("shared identifier", shared, "no identifier is asserted by several work pages")
    plan("identifier not asserted as the work's", other, "no page holds one outside its own identity claim")
    # an identifier only the lossy extractors read from a page, cited in a form whose lossy key equals it
    lossy = None
    for (fam, i), evs in sorted(idx.lossy.items()):
        strict_targets = {t for t, *_r in idx.ids.get((fam, i), ())}
        t = next((t for t, _f in evs if t not in strict_targets), None)
        cit = {fam: [i]}
        if t and (fam, i) in {(f, x) for f, x, *_r in parse_citation(cit)[0]["lossy"]}:
            lossy = ("lossy identifier", cit, {t: "CANDIDATE"}, "lossy extraction", f"its {fam} {i}")
            break
    plan("lossy identifier", lossy, "no page holds an identifier only the lossy extractors read")
    for kind, make, marker in (
            ("title", lambda r: r.title and {"title": [r.title_text]}, "title"),
            ("alias", lambda r: r.alias_input and {"title": [r.alias_input]}, "alias"),
            ("author-year", lambda r: r.author_input and {"author": r.author_input[0], "year": r.author_input[1]},
             "author-year")):
        page = next((p for p in idx.pages if make(idx.records[p])), None)
        plan(kind, page and (kind, make(idx.records[page]), {page: "CANDIDATE"}, marker, f"its own {kind}"),
             "no page carries one")
    # an author-year read from a file name or an alias, cited as the surname and year it gives
    slug = None
    for p in idx.pages:
        for s, y, how in idx.records[p].author_year:
            cit = {"author": s, "year": y}
            if how == "slug" and parse_citation(cit)[0]["author_year"] == (s, y):
                slug = ("slug author-year", cit, {p: "CANDIDATE"}, "(slug", f"its file name's {s} {y}")
                break
        if slug:
            break
    plan("slug author-year", slug, "no page's author-year comes from its file name alone")
    # a URL: one that is no identifier where the index holds one (owed CANDIDATE), else a doi.org or
    # arxiv.org URL, owed what its identifier is owed (MATCH at the one work page asserting it)
    urls = [(p, v, canon) for p in idx.pages for v, canon in idx.records[p].url_inputs]
    pick = next(((p, v) for p, v, canon in urls if not canon), None) or next(((p, v) for p, v, _c in urls), None)
    plan("url", pick and ("url", {"url": [pick[1]]}, {pick[0]: _owed(idx, {"url": [pick[1]]}, pick[0])}, "url =",
                          "its own url"), "no page carries one")
    return plans, notes


def run_controls(idx):
    """The same-run controls (control_plans): each looks its key up and must find every target it names with
    the verdict that target is owed and the marker of its route; a shared identifier must make no MATCH
    anywhere; the nonce citation must reach nothing. Raises LookupPremise when a control fails or the index
    holds no usable key of any kind; returns the report, n/a notes last."""
    plans, notes = control_plans(idx)
    if not plans:
        raise LookupPremise(f"no usable key of any kind in {len(idx.pages)} source pages - the lookup would search nothing")
    report, failed = [], []
    for name, cit, owed, marker, by in plans:
        lines = lookup_work(idx, cit)[0]
        got = {t: lines_at(lines, t) for t in owed}
        ok = all(any(ln.startswith(v + " ") and marker in ln for ln in got[t]) for t, v in owed.items())
        if name == "shared identifier" and any(ln.startswith("MATCH ") for ln in lines):
            ok = False
        verdict = "/".join(sorted({ln.split(" ", 1)[0] for ls in got.values() for ln in ls})) or "nothing"
        (report if ok else failed).append(f"{name} {verdict} at {', '.join(owed)} by {by}")
    nonce = lookup_work(idx, NONCE_CITATION)[0]
    if [ln for ln in nonce if not ln.startswith("NO MATCH")]:
        failed.append("the nonce citation reached " + "; ".join(nonce))
    else:
        report.append("nonce title, doi and arxiv reach nothing")
    if failed:
        raise LookupPremise("same-run control failed: " + "; ".join(failed))
    return report + notes


# The strict extractors' same-run positive control (beside SELF_TEST, which both de-dup probes run).
LOOKUP_SELF_TEST = [
    ("canonical", "arXiv:2307.03172", {("arxiv", "2307.03172")}),
    ("canonical", "2307.03172v3", {("arxiv", "2307.03172")}),
    ("canonical", "https://arxiv.org/abs/2307.03172v2", {("arxiv", "2307.03172")}),
    ("canonical", "https://arxiv.org/pdf/2307.03172v3.pdf", {("arxiv", "2307.03172")}),
    ("canonical", "https://arxiv.org/abs/hep-th/9901001", {("arxiv", "hep-th/9901001")}),
    ("canonical", "10.48550/arXiv.2307.03172", {("arxiv", "2307.03172")}),
    ("canonical", "https://doi.org/10.1162/TACL_A_00638", {("doi", "10.1162/tacl_a_00638")}),
    ("canonical", "doi:10.1162/tacl_a_00638", {("doi", "10.1162/tacl_a_00638")}),
    ("canonical", "10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2",
     {("doi", "10.1175/1520-0493(1950)078<0001:vofeit>2.0.co;2")}),
    ("canonical", "10.5555/example(a)", {("doi", "10.5555/example(a)")}),
    ("canonical", "10.5555/example(a", {("doi", "10.5555/example(a")}),
    ("canonical", "https://notarxiv.org/abs/2307.03172", set()),
    ("canonical", "https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/x", set()),
    ("canonical", "https://arxiv.org/abs/2307.03172?context=cs", set()),
    ("canonical", "https://arxiv.org/abs/2307.03172/extra", set()),
    ("canonical", "arXiv preprint 2305.14975v2", set()),
    ("canonical", "https://github.com/example/repo", set()),
    ("url", "HTTP://Example.TEST:443/a/b/#frag", "https://example.test/a/b"),
    ("url", "not a url", None),
    ("surname", "Kilian Q. Weinberger", "weinberger"),
    ("surname", "Kadavath, Saurav", "kadavath"),
    ("surname", "Ege Özsoy", "ozsoy"),
    ("surname", "Kadavath S. et al.", "kadavath"),
    ("surname", "J.", None),
    ("slug", "lin-2022-teaching-models", {("lin", "2022")}),
    ("slug", "bani-harouni-2025-rewarding-doubt", {("baniharouni", "2025"), ("bani", "2025")}),
    ("slug", "on-calibration-of-modern-neural-networks", set()),
    ("label", "Repo: RLCR code", "repo"),
    ("label", "Lost: A Study", None),
    # the frontmatter reader (PyYAML's BaseLoader, through parse_front_fields, on the block `title: <text>`): YAML's
    # escapes decoded (a hex escape is its character, never its letters), single quotes and plain values read
    # without escapes, and refused: what YAML does not parse, a surrogate half, and a key given twice
    ("value", '"10.5555/a\\x62"', "10.5555/ab"),
    ("value", '"\\0\\a\\b\\t\\n\\v\\f\\r\\e\\ \\"\\/\\\\\\N\\_\\L\\P"',
     "\x00\x07\x08\t\n\x0b\x0c\r\x1b \"/\\\x85\xa0\U00002028\U00002029"),
    ("value", '"\\x41\\u00e9\\U0001F600"', "A\U000000e9\U0001F600"),
    ("value", "'it''s \\x62'", "it's \\x62"),
    ("value", "10.5555/a#b # a note", "10.5555/a#b"),
    ("refused", '"10.5555/a\\q"', True),
    ("refused", '"\\x6"', True),
    ("refused", '"\\uD800"', True),
    ("refused", "Paper: A Title", True),
    ("refused", '"10.5555/a\\U00110000"', True),
    ("refused", '"one"\ntitle: "two"', True),
    ("refused", '"10.5555/a\\x62"', False),
]


def _front_value(text):
    """The title the frontmatter reader reads from the one-field block `title: <text>`."""
    return parse_front_fields("title: " + text, "self-test").get("title")


def _refused(text):
    """Whether the frontmatter reader refuses the block `title: <text>` (raises LookupPremise) rather than reading it."""
    try:
        _front_value(text)
    except LookupPremise:
        return True
    return False


def lookup_self_test(fns=None):
    fns = {"canonical": canonical_ids, "url": url_key, "surname": surname, "slug": slug_author_years,
           "label": page_label, "value": _front_value, "refused": _refused, **(fns or {})}
    out = []
    for n, i, e in LOOKUP_SELF_TEST:
        try:
            got = fns[n](i)
        except LookupPremise as err:
            got = f"refused ({err})"
        if got != e:
            out.append(f"{n}({i!r}) gave {got!r}, expected {e!r}")
    return out


def _unique_pairs(pairs):
    seen = set()
    for k, _v in pairs:
        if k in seen:
            raise ValueError(f"key {k!r} given twice")
        seen.add(k)
    return dict(pairs)


def read_citation_list(path):
    """[(line number, citation)] from a JSON-lines list. Raises LookupPremise, before any lookup runs,
    for an unreadable file, a line that is not one JSON object, an unknown key, a value of the wrong
    type, or a file holding no citation."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        text = data.decode("utf-8")
    except OSError as e:
        raise LookupPremise(f"list {path}: cannot be read ({e.strerror or e})")
    except UnicodeDecodeError:
        raise LookupPremise(f"list {path}: not UTF-8")
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        try:
            obj = json.loads(s, object_pairs_hook=_unique_pairs)
        except ValueError as e:
            raise LookupPremise(f"list line {n}: not one JSON object ({e})")
        if not isinstance(obj, dict):
            raise LookupPremise(f"list line {n}: not one JSON object")
        unknown = sorted(set(obj) - set(LIST_KEYS))
        if unknown:
            raise LookupPremise(f"list line {n}: unknown key {unknown[0]!r} (the keys are {', '.join(LIST_KEYS)})")
        cit = {}
        for k in ("title", "arxiv", "doi", "url"):
            v = obj.get(k)
            if isinstance(v, str):
                v = [v]
            if v is not None and not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                raise LookupPremise(f"list line {n}: {k} takes a string or a list of strings")
            cit[k] = v or []
        for k in ("author", "id"):
            if obj.get(k) is not None and not isinstance(obj[k], str):
                raise LookupPremise(f"list line {n}: {k} takes one string")
            cit[k] = obj.get(k)
        y = obj.get("year")
        if y is not None and (isinstance(y, bool) or not isinstance(y, (str, int))):
            raise LookupPremise(f"list line {n}: year takes four digits")
        cit["year"] = None if y is None else str(y)
        out.append((n, cit))
    if not out:
        raise LookupPremise(f"list {path}: no citation in it")
    return out


def describe_citation(cit):
    parts = [f'title "{t}"' for t in cit.get("title") or []]
    parts += [f"{k} {cit[k]}" for k in ("author", "year") if cit.get(k)]
    parts += [f"{k} {v}" for k in ("arxiv", "doi", "url") for v in cit.get(k) or []]
    return " · ".join(parts) or "(no key)"


class _LookupArgs(argparse.ArgumentParser):
    def error(self, message):
        fail(f"lookup usage: {message}")


def lookup_parser():
    ap = _LookupArgs(prog="dedup_probe.py --lookup",
                     description="Is this work in the vault? Reads wiki/sources/ frontmatter only (raw files are "
                                 "not searched); MATCH only on a canonical identifier one page asserts as its own.")
    ap.add_argument("--title", action="append", default=[], help="the work's title (repeatable)")
    ap.add_argument("--author", help="the first author's name")
    ap.add_argument("--year", help="the year, four digits")
    ap.add_argument("--arxiv", action="append", default=[], help="an arXiv id (repeatable)")
    ap.add_argument("--doi", action="append", default=[], help="a DOI (repeatable)")
    ap.add_argument("--url", action="append", default=[], help="a URL the citation gives (repeatable)")
    ap.add_argument("--list", dest="list_file", help="a JSON-lines file, one citation per line")
    ap.add_argument("--vault-root", default=None, help="default: this script's own vault")
    return ap


def lookup_main(argv):
    a = lookup_parser().parse_args(argv)
    single = {"title": a.title, "author": a.author, "year": a.year, "arxiv": a.arxiv, "doi": a.doi, "url": a.url}
    given = bool(a.title or a.arxiv or a.doi or a.url or a.author or a.year)
    if a.list_file and given:
        fail("give one work's keys or --list FILE, not both")
    if not a.list_file and not given:
        fail("no citation given: pass the work's keys (--title, --author with --year, --arxiv, --doi, --url) or --list FILE")
    vault = os.path.abspath(a.vault_root or default_vault_root())
    if not (os.path.isdir(os.path.join(vault, "raw")) and os.path.isdir(os.path.join(vault, "wiki"))):
        fail(f"{vault} is not a vault root (needs raw/ and wiki/)")
    if not os.path.isdir(os.path.join(vault, "wiki", "sources")):
        fail("wiki/sources/ is not a directory - the lookup would search nothing")
    try:
        _yaml()  # first: without PyYAML no frontmatter can be read, and nothing else is tried
        cits = read_citation_list(a.list_file) if a.list_file else [(None, single)]
        bad = self_test() + lookup_self_test()
        if bad:
            raise LookupPremise("key extractor self-test: " + "; ".join(bad))
        idx = build_lookup_index(vault)
        controls = run_controls(idx)
        results = [lookup_work(idx, c)[0] for _n, c in cits]
    except LookupPremise as e:
        fail(str(e))
    total = len(cits)
    for k, ((line_no, cit), lines) in enumerate(zip(cits, results), 1):
        where = f" (list line {line_no}{', ' + cit['id'] if cit.get('id') else ''})" if line_no else ""
        print(f"citation {k}/{total}{where}: {describe_citation(cit)}")
        for ln in lines:
            print(ln)
    print(index_summary(idx))
    print(f"controls: {' · '.join(controls)} · self-test {len(SELF_TEST)}/{len(SELF_TEST)}, "
          f"lookup self-test {len(LOOKUP_SELF_TEST)}/{len(LOOKUP_SELF_TEST)}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if "--lookup" in argv:
        argv.remove("--lookup")
        return lookup_main(argv)
    ap = argparse.ArgumentParser(description="Ingest de-dup pre-flight over name, hash, URL, arXiv id, "
                                             "DOI and full or name/site-stripped title. "
                                             "Reads only; exit 2 is never NEW.")
    ap.add_argument("candidate", help="the inbox file, e.g. raw/<file> (vault-relative or absolute)")
    ap.add_argument("--url", action="append", default=[], help="a source URL the lane knows (repeatable)")
    ap.add_argument("--title", action="append", default=[], help="a source title, e.g. for a PDF (repeatable)")
    ap.add_argument("--doi", action="append", default=[], help="a DOI read from the source (repeatable)")
    ap.add_argument("--vault-root", default=None, help="default: this script's own vault")
    a = ap.parse_args(argv)
    vault = os.path.abspath(a.vault_root or default_vault_root())
    if not (os.path.isdir(os.path.join(vault, "raw")) and os.path.isdir(os.path.join(vault, "wiki"))):
        fail(f"{vault} is not a vault root (needs raw/ and wiki/)")
    bad = self_test()
    if bad:
        fail("key extractor self-test: " + "; ".join(bad))
    cand = a.candidate if os.path.isabs(a.candidate) else os.path.join(vault, a.candidate)
    if not os.path.isfile(cand):
        fail(f"candidate {a.candidate} not found - nothing was probed")
    sources = os.path.join(vault, "wiki", "sources")
    if not os.path.isdir(sources):
        fail("wiki/sources/ missing - the scan would search nothing")
    real_cand = os.path.realpath(cand)
    fm = frontmatter(read_head(cand)) if cand.endswith(".md") else {}
    urls = sorted({u for u in a.url if u} | {fm[k] for k in URL_KEYS if fm.get(k, "").startswith(("http://", "https://"))})
    arx, doi, fm_title = keys_of(fm)
    for u in urls:
        arx |= arxiv_ids(u)
        doi |= dois(u)
    for d in a.doi:
        doi |= dois(d) or ({d.strip().lower()} if d.strip() else set())
    raw_titles = [t for t in a.title if t.strip()] + ([fm["title"]] if fm.get("title") else [])
    hosts = host_labels(urls + [fm.get(k, "") for k in HOST_KEYS])
    titles = [k for k in (title_key(t, hosts) for t in raw_titles) if k]
    short = [t for t in raw_titles if title_key(t) is None]

    hits, errors = {}, []
    add = lambda p, label: hits.setdefault(os.path.relpath(p, vault), []).append(label)
    name = os.path.basename(cand)
    raw_top = os.path.join(vault, "raw")
    with open(cand, "rb") as fh:
        h16 = hashlib.sha256(fh.read()).hexdigest()[:16]
    for dirpath, fp in walk_files(raw_top, errors):
        if os.path.realpath(fp) == real_cand or dirpath == raw_top:
            continue
        if os.path.basename(fp) == name:
            add(fp, "name")
        if urls and fp.lower().endswith(TEXT_EXTS):
            with open(fp, "rb") as fh:
                data = fh.read()
            for u in urls:
                if u.encode() in data:
                    add(fp, f"url {u}")
    control = None
    for _dir, fp in walk_files(sources, errors):
        if os.path.realpath(fp) == real_cand:
            continue
        with open(fp, "rb") as fh:
            data = fh.read()
        if control is None and b"source_hash" in data:
            control = os.path.relpath(fp, vault)
        if h16.encode() in data:
            add(fp, "hash")
        for u in urls:
            if u.encode() in data:
                add(fp, f"url {u}")
    idx = build_index(vault, roots=("wiki/sources", "raw"), skip=[cand])
    errors += idx["unreadable"]
    if errors:
        fail("unreadable under the scan: " + "; ".join(errors[:5]))
    if control is None:
        fail("no wiki/sources/ file carries source_hash - the control found nothing, so NEW is unproven")
    if not idx["title"]:
        fail(f"no title keyed over {idx['files']} indexed files - the title key searched nothing")
    for p, labels in lookup(idx, arx, doi, titles).items():
        hits.setdefault(p, []).extend(labels)

    for p in sorted(hits):
        print(f"CANDIDATE {p} [{'; '.join(dict.fromkeys(hits[p]))}]")
    if not hits:
        print("NEW")
    print(f"keys: name {name} · hash {h16} · urls {len(urls)} · arxiv {', '.join(sorted(arx)) or '-'} · "
          f"doi {', '.join(sorted(doi)) or '-'} · titles keyed {len({str(k) for k in titles})}, "
          f"suffix-stripped {len({k.suffix_stripped for k in titles if k.suffix_stripped})}, "
          f"name-stripped {len({k.name_stripped for k in titles if k.name_stripped})}"
          + (f" · not keyed (under {TITLE_MIN_TOKENS} tokens): {'; '.join(short)}" if short else ""))
    print(f"controls: source_hash page {control} · indexed {idx['files']} files, {len(idx['arxiv'])} arXiv ids, "
          f"{len(idx['doi'])} DOIs, {len(idx['title'])} titles ({len(idx['title_stripped'])} suffix-stripped, "
          f"{len(idx['title_name_stripped'])} name-stripped) · "
          f"self-test {len(SELF_TEST)}/{len(SELF_TEST)}")


if __name__ == "__main__":
    main()
