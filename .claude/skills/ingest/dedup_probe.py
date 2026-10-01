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
  title  the normalised title: case-folded; one leading page label (Paper:, Source:, ...) and a
         leading [arXiv id] dropped; hyphens, dashes and underscores unified with spaces;
         punctuation and stop words stripped; keyed only at TITLE_MIN_TOKENS tokens or more
  suffix-stripped title
         a title less a trailing site or venue suffix (`... | arXiv`, `... - PMC`; see
         strip_site_suffix), matched against a title that is that text in full, in either
         direction, and never against another stripped title: pages of one family
         ("X docs - Sessions", "X docs - Guardrails") share a stem and must not meet on it
The candidate's keys come from its own frontmatter plus --url, --title and --doi.

Usage:
  python3 dedup_probe.py raw/<file> [--url U] [--title T] [--doi D] [--vault-root PATH]
Prints one `CANDIDATE <path> [keys]` line per possible duplicate, or `NEW`, then a `keys:` line
and a `controls:` line. Exit 0 = the probe ran; exit 2 = `PROBE FAILED: <what>`, which is never NEW.
Reads only: it creates, modifies, moves and deletes nothing.
"""
import argparse, hashlib, os, re, sys, unicodedata, urllib.parse

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
    """A title key: the normalised title. `suffix_stripped` is the key less a trailing site or venue
    suffix, or None. A str, so a caller that holds the key as a string (capture_write.py dedup)
    carries both forms into lookup() unchanged."""
    suffix_stripped = None


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
    SUFFIX_MAX_TOKENS content tokens and shares no content word with the rest."""
    t = _prepare(title)
    found = list(SUFFIX_DELIM.finditer(t))
    if not found:
        return None
    cut = found[-1]
    rest, tail = _content_tokens(t[:cut.start()]), _content_tokens(t[cut.end():])
    if len(rest) < TITLE_MIN_TOKENS or not tail:
        return None
    names_host = re.sub(r"[\W_]+", "", t[cut.end():]) in set(hosts)
    if names_host or (len(tail) <= SUFFIX_MAX_TOKENS and not set(tail) & set(rest)):
        return " ".join(rest)
    return None


def title_key(title, hosts=()):
    """The TitleKey of a title, or None under TITLE_MIN_TOKENS tokens once normalised; `hosts` are
    host_labels() of the URLs the same record carries."""
    n = normalise_title(title)
    if len(n.split()) < TITLE_MIN_TOKENS:
        return None
    key = TitleKey(n)
    key.suffix_stripped = strip_site_suffix(title, hosts)
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
    """Map each arXiv id, DOI, title key and suffix-stripped title to the vault-relative Markdown
    paths carrying it."""
    idx = {"arxiv": {}, "doi": {}, "title": {}, "title_stripped": {}, "files": 0, "unreadable": [], "missing": []}
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
    return idx


def lookup(idx, arx=(), doi=(), titles=()):
    """{path: [labels]} for every indexed path sharing an arXiv id, DOI or title key. A title matches
    an indexed title in full ("title"); a title less its site suffix matches an indexed title in
    full, and a title in full matches an indexed title less its suffix ("suffix-stripped title");
    two stripped titles never match each other."""
    hits = {}
    for a in sorted(arx):
        for p in idx["arxiv"].get(a, ()):
            hits.setdefault(p, []).append(f"arxiv {a}")
    for d in sorted(doi):
        for p in idx["doi"].get(d, ()):
            hits.setdefault(p, []).append(f"doi {d}")
    stripped_idx = idx.get("title_stripped", {})
    for t in sorted(t for t in titles if t):
        for p in idx["title"].get(t, ()):
            hits.setdefault(p, []).append("title")
        s = getattr(t, "suffix_stripped", None)
        for p in sorted(set(stripped_idx.get(t, ())) | (set(idx["title"].get(s, ())) if s else set())):
            hits.setdefault(p, []).append("suffix-stripped title")
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
    ("stripped", "Lost in the Middle: How Language Models Use Long Contexts | arXiv",
     "lost middle how language models use long contexts"),
    ("stripped", "Lost in the Middle: How Language Models Use Long Contexts - PMC",
     "lost middle how language models use long contexts"),
    ("stripped", "Large Language Models - How They Use Long Contexts", None),
    ("stripped", "Attention Heads in Transformer Models - Attention Sinks", None),
]


def self_test(fns=None):
    fns = {"arxiv": arxiv_ids, "doi": dois, "title": normalise_title, "stripped": strip_site_suffix, **(fns or {})}
    return [f"{n}({i!r}) gave {fns[n](i)!r}, expected {e!r}" for n, i, e in SELF_TEST if fns[n](i) != e]


def default_vault_root():
    # this file sits at <vault>/.claude/skills/ingest/, so the vault is three parents up
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def fail(msg):
    print(f"PROBE FAILED: {msg}")
    sys.exit(2)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ingest de-dup pre-flight over name, hash, URL, arXiv id, "
                                             "DOI and normalised title (also less a trailing site suffix). "
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
          f"suffix-stripped {len({k.suffix_stripped for k in titles if k.suffix_stripped})}"
          + (f" · not keyed (under {TITLE_MIN_TOKENS} tokens): {'; '.join(short)}" if short else ""))
    print(f"controls: source_hash page {control} · indexed {idx['files']} files, {len(idx['arxiv'])} arXiv ids, "
          f"{len(idx['doi'])} DOIs, {len(idx['title'])} titles ({len(idx['title_stripped'])} suffix-stripped) · "
          f"self-test {len(SELF_TEST)}/{len(SELF_TEST)}")


if __name__ == "__main__":
    main()
