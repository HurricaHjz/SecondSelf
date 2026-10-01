#!/usr/bin/env python3
"""oa_resolve.py — the open-access resolver rung for /gather: headless, stdout only.

A row the capture chain cannot fetch (a publisher 403, a bot wall) is resolved
here before any browser opens. Given a DOI, an arXiv id, a title or the blocked
URL itself, the script asks, in order, Unpaywall, OpenAlex, the arXiv API and
Europe PMC for an open copy and prints the first one found. A found copy takes
the ordinary capture chain and is written with
`capture_write.py write --url <row> --resolved-url <copy>`; this script fetches
no page and writes no file. It is the first of three rungs: this resolver, then a
browser fetch where one is configured, then the hand-fetch list.

Usage:
    oa_resolve.py QUERY [QUERY ...] [--title T] [--json] [--hand-fetch]
                  [--reason bot-wall|licensed] [--max-requests N]

QUERY is one of
    a DOI          10.1002/qj.2985 · doi:10.1002/qj.2985 · https://doi.org/10.1002/qj.2985
    an arXiv id    2307.03172 · arXiv:2307.03172v2 · hep-th/9901001 · an arxiv.org
                   abs/pdf/html URL · the 10.48550/arXiv.<id> DOI
    a blocked URL  a DOI in its path or query is extracted, and its host is kept
                   as the host that refused headless
    a title        anything else (quote it)
--title gives a title beside a single DOI or URL, for the arXiv and Europe PMC
title searches when the DOI records carry none.

Text output, per query: a `query:` line, one `<source>: <outcome>` line per
source (skipped sources included, with the reason), then exactly one of
    RESOLVED <url> via <source>
    UNRESOLVED (tried: <sources>)
    PROBE FAILED: <what> (tried: <sources>)
and a `requests:` line. --hand-fetch adds, for an unresolved query, the
HAND-FETCH block the run report carries: the URL, the reason (bot wall or
licensed) and a ready Codex prompt the owner pastes. --json prints one JSON
array instead, one object per query. Each live request is one `request N:`
line on stderr, so a caller counts requests without this script writing a file.

Exit: 0 every query resolved · 1 at least one UNRESOLVED · 2 a PROBE FAILED on
any query (every source tried errored, the request cap cut a chain short, a
recorded response missing in replay) or a usage error.

Rules the code keeps:
- an arXiv id resolves to its own PDF at once, with no API call;
- network: HTTPS to the four API hosts only (ALLOWED_HOSTS); redirects are never
  followed, so a request cannot leave the grant and each request is one exchange
  (a 3xx is that source's error);
- every request carries a 20 s timeout and gets one retry on a 5xx; nothing else
  retries (a 429 is that source's error); arXiv requests are spaced 3 s apart;
- within a source, repository copies come before publisher copies, and a PMC URL is
  given in its canonical form;
- an open copy on the host that refused headless is skipped, because it cannot take
  the headless chain, and is named in the output; a query whose only open copy sits
  there goes to the hand-fetch list as a bot wall;
- a title-search hit counts only on a token-set match (TITLE_MATCH_MIN), and an arXiv
  record carrying a different DOI is rejected;
- an UNRESOLVED verdict needs at least one source that answered: when every source
  tried errored, the verdict is PROBE FAILED, never UNRESOLVED.
Transport: curl when on PATH, else urllib; OA_TRANSPORT=curl|urllib forces one (see
pick_transport). The courtesy contact sent as Unpaywall's `email` and OpenAlex's
`mailto` comes from OA_CONTACT_EMAIL, which must be set before a request.
Replay: OA_RESOLVE_FIXTURES=<dir> answers every request from the recorded responses
listed in <dir>/manifest.json and never opens a socket (the test suite's mode).
"""
import argparse, json, os, re, shutil, subprocess, sys, time
import urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True  # importing capture_write must not drop a __pycache__ into the skill folder
from capture_write import slug_from  # one slug rule for the hand-fetch file and the eventual capture

SOURCES = ("unpaywall", "openalex", "arxiv", "europepmc")
ALLOWED_HOSTS = frozenset({"api.unpaywall.org", "api.openalex.org", "export.arxiv.org", "www.ebi.ac.uk"})
TIMEOUT_S = 20          # per request; headroom over the APIs' typical 1 to 3 s answers (the build brief's figure), unmeasured here
CURL_GRACE_S = 5        # extra wall time before the curl process itself is abandoned; set by judgement, unmeasured
RETRY_PAUSE_S = 2       # pause before the one retry on a 5xx; set by judgement, unmeasured
ARXIV_SPACING_S = 3     # the arXiv API's terms of use ask for no more than one request every three seconds
PER_QUERY_REQUESTS = 8  # default cap per query: 4 sources x (1 try + 1 retry on a 5xx), the worst case of one chain
TITLE_MATCH_MIN = 0.8   # token-set Jaccard after spelling folds; set by judgement, unmeasured: a ten-word title that
                        # differs in one word scores 9/11 = 0.82 and matches, in two words 8/12 = 0.67 and does not
SEARCH_ROWS = 5         # candidate records read per title or DOI search; set by judgement, unmeasured
OPENALEX_FIELDS = "id,doi,title,display_name,open_access,best_oa_location,locations,ids"
SCRATCH_DIR = "~/.llm-wiki/gather-scratch"  # the design's scratch folder, outside the vault; the gather run creates it
USER_AGENT = "llm-wiki-gather-oa-resolve/1"
CODEX_PROMPT = ("Fetch {target}, save the full text as Markdown to {scratch}/{slug}.md, "
                "keep the title and the section headings")
COURTESY_PARAMS = ("email", "mailto")
CURL_MARK = b"\n@@oa-resolve-status@@"
DOI_HOSTS = frozenset({"doi.org", "dx.doi.org", "www.doi.org"})
ARXIV_HOSTS = frozenset({"arxiv.org", "www.arxiv.org", "export.arxiv.org"})
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"

BARE_DOI = re.compile(r"(?i)^(?:doi:\s*)?(10\.\d{4,9}/\S+)$")
DOI_IN_TEXT = re.compile(r"(10\.\d{4,9}/[^\s?#&\"'<>]+)")
ARXIV_NEW = re.compile(r"(?i)^(?:arxiv:\s*)?(\d{4}\.\d{4,5}(?:v\d+)?)$")
ARXIV_OLD = re.compile(r"(?i)^(?:arxiv:\s*)?([a-z][a-z\-]*(?:\.[a-z]{2})?/\d{7}(?:v\d+)?)$")
ARXIV_DOI = re.compile(r"(?i)^10\.48550/arxiv\.(.+)$")
PMC_URL = re.compile(r"(?i)^https?://(?:www\.)?(?:pmc\.)?ncbi\.nlm\.nih\.gov/(?:pmc/)?articles/(?:PMC)?(\d+)/?(?:[?#].*)?$")


class ProbeFailed(Exception):
    """A broken premise: the invocation stops and exits 2."""


class SourceError(Exception):
    """One source failed to answer: a network error, an HTTP error, an unreadable body."""


class CapReached(Exception):
    """The next request would exceed the request cap."""


# ---------------------------------------------------------------- identity

def _arxiv_id(text):
    """An arXiv id from a bare id or an abs/pdf/html path tail, else None."""
    text = (text or "").strip().rstrip("/")
    if text.lower().endswith(".pdf"):
        text = text[:-4]
    for pat in (ARXIV_NEW, ARXIV_OLD):
        m = pat.match(text)
        if m:
            return m.group(1)
    return None


def _clean_doi(doi):
    """Drop sentence punctuation a DOI picked up; a closing bracket goes only when unbalanced."""
    doi = doi.rstrip(".,;:")
    while doi and doi[-1] in ")]}" and doi.count(doi[-1]) > doi.count({")": "(", "]": "[", "}": "{"}[doi[-1]]):
        doi = doi[:-1].rstrip(".,;:")
    return doi


def classify(query, title=None):
    """The query's identity: kind (arxiv | doi | url | title), doi, arxiv_id, title,
    blocked_url and refused_host. Raises ValueError on an empty query."""
    q = (query or "").strip()
    if not q:
        raise ValueError("empty query: give a DOI, an arXiv id, a URL or a title")
    info = {"query": q, "kind": "title", "doi": None, "arxiv_id": None,
            "title": (title or "").strip() or None, "blocked_url": None, "refused_host": None}
    if re.match(r"(?i)^https?://", q):
        parts = urllib.parse.urlsplit(q)
        host = (parts.hostname or "").lower()
        info.update(kind="url", blocked_url=q)
        if host in ARXIV_HOSTS:
            m = re.match(r"(?i)^/(?:abs|pdf|html)/(.+)$", parts.path)
            aid = _arxiv_id(m.group(1)) if m else None
            if aid:
                info.update(kind="arxiv", arxiv_id=aid)
                return info
        if host not in DOI_HOSTS:
            info["refused_host"] = host or None
        found = DOI_IN_TEXT.search(urllib.parse.unquote(parts.path))
        if not found:
            for _key, value in urllib.parse.parse_qsl(parts.query):
                found = DOI_IN_TEXT.search(value)
                if found:
                    break
        if found:
            info.update(kind="doi", doi=_clean_doi(found.group(1)))
    else:
        m = BARE_DOI.match(q)
        if m:
            info.update(kind="doi", doi=_clean_doi(m.group(1)))
        else:
            aid = _arxiv_id(q)
            if aid:
                info.update(kind="arxiv", arxiv_id=aid)
                return info
            info["title"] = q
    if info["doi"]:
        m = ARXIV_DOI.match(info["doi"])
        if m and _arxiv_id(m.group(1)):
            info.update(kind="arxiv", arxiv_id=_arxiv_id(m.group(1)))
    return info


def _fold(tok):
    """Spelling folds applied to both sides of a title comparison (-ise/-ize, -yse/-yze, -our/-or)."""
    tok = re.sub(r"is(e|ed|es|ing|ation|ations)$", r"iz\1", tok)
    tok = re.sub(r"ys(e|ed|es|ing)$", r"yz\1", tok)
    if len(tok) > 4 and tok.endswith("our"):
        tok = tok[:-3] + "or"
    return tok


def title_tokens(text):
    return {_fold(t) for t in re.findall(r"[^\W_]+", (text or "").lower())}


def title_match(a, b):
    """Token-set Jaccard of two titles after the spelling folds; 0.0 when either is empty."""
    ta, tb = title_tokens(a), title_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _site(host):
    """The registrable part of a host, for the same-host test (two labels; three under ac.uk-style suffixes)."""
    labels = (host or "").lower().rstrip(".").split(".")
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in {"ac", "co", "com", "edu", "gov", "net", "org"}:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _text(value):
    return " ".join(str(value).split()) if value else None


def normalise_url(url):
    """An open-copy URL in canonical form where one is known: a PMC article given on the
    older www.ncbi.nlm.nih.gov/pmc path (as Unpaywall and OpenAlex still give it) becomes
    https://pmc.ncbi.nlm.nih.gov/articles/PMC<n>/, so a de-dup check matches one form."""
    m = PMC_URL.match(url or "")
    return f"https://pmc.ncbi.nlm.nih.gov/articles/PMC{m.group(1)}/" if m else url


def _repository_first(locations, is_repository):
    """Stable sort: repository copies before publisher copies, each group in the API's own
    order. Set from the design page's gap record ("The gap, dated"): the publisher hosts
    (Taylor & Francis, Wiley, a Sage article) refused headless fetches, while arXiv, JMLR,
    PMLR, ACL, NeurIPS and authors' sites answered."""
    return sorted(locations, key=lambda loc: 0 if is_repository(loc) else 1)


# ---------------------------------------------------------------- request URLs

def _phrase(title):
    return " ".join(re.findall(r"[^\W_]+", title or ""))


def unpaywall_url(doi, contact):
    return f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi, safe='/')}?email={urllib.parse.quote(contact, safe='')}"


def openalex_doi_url(doi, contact):
    return (f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi, safe='/')}?"
            + urllib.parse.urlencode({"select": OPENALEX_FIELDS, "mailto": contact}))


def openalex_search_url(title, contact):
    return "https://api.openalex.org/works?" + urllib.parse.urlencode(
        {"search": _phrase(title), "per-page": SEARCH_ROWS, "select": OPENALEX_FIELDS, "mailto": contact})


def arxiv_url(title):
    # https: the http endpoint answers with a redirect to https, which this script never follows
    return "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        {"search_query": f'ti:"{_phrase(title)}"', "max_results": SEARCH_ROWS})


def europepmc_url(doi=None, title=None):
    query = f'DOI:"{doi}"' if doi else f'TITLE:"{_phrase(title)}"'
    return "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(
        {"query": query, "format": "json", "pageSize": SEARCH_ROWS})


def fixture_key(url):
    """A recorded response's key: the request URL without its courtesy contact, so a
    replay does not depend on which address recorded it."""
    parts = urllib.parse.urlsplit(url)
    kept = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
            if k not in COURTESY_PARAMS]
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(kept), ""))


# ---------------------------------------------------------------- transports

def _grant(url):
    """Refuse, before any socket opens, a URL that is not HTTPS to a granted host."""
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or host not in ALLOWED_HOSTS:
        raise ProbeFailed(f"{url} is outside the network grant (HTTPS to {', '.join(sorted(ALLOWED_HOSTS))})")


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect: the 3xx comes back as the answer."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def urllib_fetch(url):
    """One GET through urllib. Returns (status, body bytes, url); an HTTP error status
    returns with its body; a network or TLS failure raises OSError."""
    _grant(url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.build_opener(_NoRedirects).open(req, timeout=TIMEOUT_S) as resp:
            return resp.status, resp.read(), url
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
        except OSError:
            body = b""
        return e.code, body, url


def curl_fetch(url, curl="curl"):
    """One GET through curl: HTTPS only, no redirects (no -L), ~/.curlrc ignored (-q),
    the whole exchange bounded by --max-time. Returns (status, body bytes, url); a curl
    failure (DNS, connect, TLS, timeout) raises OSError."""
    _grant(url)
    cmd = [curl, "-q", "-sS", "--proto", "=https", "--max-time", str(TIMEOUT_S),
           "-A", USER_AGENT, "-w", CURL_MARK.decode().replace("\n", "\\n") + "%{http_code}", url]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=TIMEOUT_S + CURL_GRACE_S)
    except subprocess.TimeoutExpired:
        raise OSError(f"curl gave no answer within {TIMEOUT_S + CURL_GRACE_S} s")
    if proc.returncode != 0:
        raise OSError(f"curl exit {proc.returncode}: {proc.stderr.decode('utf-8', 'replace').strip()}")
    body, mark, code = proc.stdout.rpartition(CURL_MARK)
    if not mark or not code.strip().isdigit():
        raise OSError("curl output carried no HTTP status")
    return int(code), body, url


def pick_transport():
    """curl when on PATH, else urllib; OA_TRANSPORT=curl|urllib forces one. curl is the
    default because it is already the capture chain's fetcher and verifies TLS against the
    system trust store, while a Python build without an installed CA bundle fails every
    HTTPS verification in urllib. Returns (fetch, name)."""
    choice = os.environ.get("OA_TRANSPORT", "").strip().lower()
    if choice not in ("", "curl", "urllib"):
        raise ProbeFailed(f"OA_TRANSPORT={choice!r}: use curl or urllib")
    curl = shutil.which("curl")
    if choice == "urllib" or (not choice and not curl):
        return urllib_fetch, "urllib"
    if not curl:
        raise ProbeFailed("OA_TRANSPORT=curl but curl is not on PATH")
    return (lambda url: curl_fetch(url, curl)), "curl"


def live_fetch(url):
    """One live GET through the picked transport (for callers outside the resolver)."""
    fetch, _name = pick_transport()
    return fetch(url)


def replay_fetcher(fixture_dir):
    """A fetch that answers from recorded responses and never opens a socket. A manifest
    entry is {status, file | body} or a list of them served in order (the last repeats);
    {"error": text} replays a network failure. A URL with no entry is a PROBE FAILED."""
    manifest_path = os.path.join(fixture_dir, "manifest.json")
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError) as e:
        raise ProbeFailed(f"replay manifest unreadable ({manifest_path}): {e}")
    if not isinstance(manifest, dict):
        raise ProbeFailed(f"replay manifest {manifest_path} is not a JSON object")
    served = {}

    def fetch(url):
        _grant(url)
        key = fixture_key(url)
        if key not in manifest:
            raise ProbeFailed(f"no recorded response for {key} in {manifest_path}")
        entries = manifest[key] if isinstance(manifest[key], list) else [manifest[key]]
        i = served.get(key, 0)
        served[key] = i + 1
        entry = entries[min(i, len(entries) - 1)]
        if "error" in entry:
            raise OSError(entry["error"])
        if "file" in entry:
            path = entry["file"] if os.path.isabs(entry["file"]) else os.path.join(fixture_dir, entry["file"])
            try:
                with open(path, "rb") as fh:
                    body = fh.read()
            except OSError as e:
                raise ProbeFailed(f"recorded response {path} unreadable: {e}")
        else:
            body = entry.get("body", "").encode("utf-8")
        return int(entry["status"]), body, url
    return fetch


def _json(body):
    try:
        data = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
    except (ValueError, UnicodeDecodeError) as e:
        raise SourceError(f"unreadable JSON response: {e}")
    if not isinstance(data, dict):
        raise SourceError("unexpected JSON shape (not an object)")
    return data


def _add(candidates, url):
    url = normalise_url(url)
    if url and url not in candidates:
        candidates.append(url)


# ---------------------------------------------------------------- the resolver

class Resolver:
    def __init__(self, fetch, contact, cap, live, log=None, transport="replay"):
        self.fetch, self.contact, self.cap, self.live = fetch, contact, cap, live
        self.transport = transport
        self.used = 0
        self.last_arxiv = None
        self.log = log or (lambda line: None)

    def _get(self, url):
        """GET with one retry on a 5xx. Returns (status, body) for a 2xx or 4xx answer;
        raises SourceError on a network failure, a 3xx or a second 5xx, and CapReached
        before a request the cap does not allow."""
        _grant(url)
        arxiv = urllib.parse.urlsplit(url).hostname == "export.arxiv.org"
        for attempt in (1, 2):
            if self.used >= self.cap:
                raise CapReached(f"request cap {self.cap} reached")
            if arxiv and self.live and self.last_arxiv is not None:
                wait = ARXIV_SPACING_S - (time.monotonic() - self.last_arxiv)
                if wait > 0:
                    time.sleep(wait)
            self.used += 1
            t0 = time.monotonic()
            try:
                status, body, _final = self.fetch(url)
            except OSError as e:
                self.log(f"request {self.used}: GET {url} -> network error ({self.transport}): {e}")
                raise SourceError(f"network error: {e}")
            finally:
                if arxiv:
                    self.last_arxiv = time.monotonic()
            ms = int((time.monotonic() - t0) * 1000)
            self.log(f"request {self.used}: GET {url} -> HTTP {status} in {ms} ms ({self.transport})")
            if 500 <= status < 600 and attempt == 1:
                if self.live:
                    time.sleep(RETRY_PAUSE_S)
                continue
            if 300 <= status < 400:
                raise SourceError(f"HTTP {status}: redirect not followed (a redirect could leave the grant)")
            if status >= 500:
                raise SourceError(f"HTTP {status} twice (one retry spent)")
            return status, body

    def _pick(self, candidates, info):
        """The first candidate not on the host that refused headless (a doi.org link for the
        same DOI counts as that host: it redirects there). Returns (url or None, skipped)."""
        skipped = []
        refused = info["refused_host"]
        for url in candidates:
            host = (urllib.parse.urlsplit(url).hostname or "").lower()
            same_doi = host in DOI_HOSTS and info["doi"] and info["doi"].lower() in url.lower()
            if refused and (_site(host) == _site(refused) or same_doi):
                skipped.append(url)
                continue
            return url, skipped
        return None, skipped

    def _verdict(self, candidates, info, note):
        url, skipped = self._pick(candidates, info)
        out = {"alternatives": [c for c in candidates if c != url and c not in skipped],
               "skipped_on_refusing_host": skipped}
        if url:
            extra = f"; {len(skipped)} copy on the refusing host skipped" if skipped else ""
            out.update(outcome="hit", url=url, detail=note + extra)
        else:
            out.update(outcome="miss", detail=(f"{note}, but every open copy sits on the host that "
                                               f"refused headless ({info['refused_host']})"))
        return out

    def q_unpaywall(self, info):
        if not info["doi"]:
            return {"outcome": "skip", "detail": "no DOI"}
        status, body = self._get(unpaywall_url(info["doi"], self.contact))
        if status == 404:
            return {"outcome": "miss", "detail": "DOI not in Unpaywall (HTTP 404)"}
        if status != 200:
            raise SourceError(f"HTTP {status}")
        data = _json(body)
        info["title"] = info["title"] or _text(data.get("title"))
        locations = [loc for loc in [data.get("best_oa_location")] + list(data.get("oa_locations") or [])
                     if isinstance(loc, dict)]
        candidates = []
        for loc in _repository_first(locations, lambda loc: loc.get("host_type") == "repository"):
            for key in ("url", "url_for_landing_page"):  # Unpaywall's `url` is the PDF when there is one
                _add(candidates, loc.get(key))
        if not data.get("is_oa") or not candidates:
            return {"outcome": "miss", "detail": "no open copy (is_oa false)"}
        return self._verdict(candidates, info, "is_oa true")

    def _openalex_work(self, work, info):
        info["title"] = info["title"] or _text(work.get("title") or work.get("display_name"))
        if not info["doi"] and work.get("doi"):
            info["doi"] = re.sub(r"(?i)^https?://(?:dx\.)?doi\.org/", "", work["doi"])
        oa = work.get("open_access") or {}
        locations = [loc for loc in [work.get("best_oa_location")] + list(work.get("locations") or [])
                     if isinstance(loc, dict) and loc.get("is_oa")]
        candidates = []
        for loc in _repository_first(locations, lambda loc: (loc.get("source") or {}).get("type") == "repository"):
            for key in ("pdf_url", "landing_page_url"):
                _add(candidates, loc.get(key))
        _add(candidates, oa.get("oa_url"))
        if not oa.get("is_oa") or not candidates:
            return {"outcome": "miss", "detail": f"no open copy (is_oa {str(bool(oa.get('is_oa'))).lower()})"}
        return self._verdict(candidates, info, f"is_oa true ({oa.get('oa_status') or 'status not given'})")

    def q_openalex(self, info):
        if info["doi"]:
            status, body = self._get(openalex_doi_url(info["doi"], self.contact))
            if status == 404:
                return {"outcome": "miss", "detail": "DOI not in OpenAlex (HTTP 404)"}
            if status != 200:
                raise SourceError(f"HTTP {status}")
            return self._openalex_work(_json(body), info)
        if not info["title"]:
            return {"outcome": "skip", "detail": "no DOI or title"}
        status, body = self._get(openalex_search_url(info["title"], self.contact))
        if status != 200:
            raise SourceError(f"HTTP {status}")
        results = _json(body).get("results") or []
        for work in results:
            score = title_match(info["title"], work.get("title") or work.get("display_name"))
            if score >= TITLE_MATCH_MIN:
                out = self._openalex_work(work, info)
                out["detail"] = f"title match {score:.2f} ({work.get('id')}); {out['detail']}"
                return out
        return {"outcome": "miss", "detail": f"no title match among {len(results)} results"}

    def q_arxiv(self, info):
        if not info["title"]:
            why = "the DOI records carried none; " if info["doi"] else ""
            return {"outcome": "skip", "detail": f"no title ({why}pass --title)"}
        status, body = self._get(arxiv_url(info["title"]))
        if status != 200:
            raise SourceError(f"HTTP {status}")
        try:
            root = ET.fromstring(body)
        except ET.ParseError as e:
            raise SourceError(f"unreadable Atom response: {e}")
        entries = root.findall(f"{ATOM}entry")
        for entry in entries:
            eid = (entry.findtext(f"{ATOM}id") or "").strip()
            if "/api/errors" in eid:
                raise SourceError("arXiv API error: " + (_text(entry.findtext(f"{ATOM}summary")) or eid))
            score = title_match(info["title"], _text(entry.findtext(f"{ATOM}title")))
            if score < TITLE_MATCH_MIN:
                continue
            edoi = (entry.findtext(f"{ARXIV_NS}doi") or "").strip()
            if info["doi"] and edoi and edoi.lower() != info["doi"].lower():
                continue  # the same title on a record of a different work
            m = re.search(r"arxiv\.org/abs/(.+)$", eid)
            aid = _arxiv_id(m.group(1)) if m else None
            if aid:
                base = re.sub(r"v\d+$", "", aid)
                return self._verdict([f"https://arxiv.org/pdf/{base}"], info, f"title match {score:.2f} (arXiv {aid})")
        return {"outcome": "miss", "detail": f"no title match among {len(entries)} records"}

    def q_europepmc(self, info):
        if not (info["doi"] or info["title"]):
            return {"outcome": "skip", "detail": "no DOI or title"}
        status, body = self._get(europepmc_url(doi=info["doi"], title=info["title"]))
        if status != 200:
            raise SourceError(f"HTTP {status}")
        data = _json(body)
        results = (data.get("resultList") or {}).get("result") or []
        for rec in results:
            if info["doi"]:
                if (rec.get("doi") or "").lower() != info["doi"].lower():
                    continue
                why = "DOI match"
            else:
                score = title_match(info["title"], rec.get("title"))
                if score < TITLE_MATCH_MIN:
                    continue
                why = f"title match {score:.2f}"
            pmcid = rec.get("pmcid")
            if pmcid and "Y" in (rec.get("inEPMC"), rec.get("inPMC"), rec.get("isOpenAccess")):
                return self._verdict([f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
                                      f"https://europepmc.org/article/PMC/{pmcid}"],
                                     info, f"{why}, {pmcid} (free full text)")
            return {"outcome": "miss", "detail": f"{why} ({rec.get('source')}:{rec.get('id')}), no PMC full text"}
        return {"outcome": "miss",
                "detail": f"no matching record among {len(results)} (hitCount {data.get('hitCount')})"}

    def resolve(self, info):
        info = dict(info)
        res = {"status": None, "url": None, "via": None, "sources": [], "requests": 0,
               "note": None, "open_copy_on_refusing_host": None, "transport": self.transport}
        start = self.used
        if info["kind"] == "arxiv":
            res.update(status="RESOLVED", url=f"https://arxiv.org/pdf/{info['arxiv_id']}", via="arxiv-id")
            res["sources"].append({"source": "arxiv-id", "outcome": "hit", "requests": 0,
                                   "detail": "an arXiv id resolves to its own PDF; no API call"})
            return {**info, **res}
        capped = None
        for name in SOURCES:
            before = self.used
            try:
                out = getattr(self, "q_" + name)(info)
            except SourceError as e:
                out = {"outcome": "error", "detail": str(e)}
            except CapReached as e:
                out = {"outcome": "error", "detail": str(e)}
                capped = str(e)
            out["source"] = name
            out["requests"] = self.used - before
            res["sources"].append(out)
            if out["outcome"] == "hit":
                res.update(status="RESOLVED", url=out["url"], via=name)
                break
            if capped:
                break
        res["requests"] = self.used - start
        refusing = [u for s in res["sources"] for u in s.get("skipped_on_refusing_host") or []]
        res["open_copy_on_refusing_host"] = refusing[0] if refusing else None
        if res["status"]:
            return {**info, **res}
        tried = [s for s in res["sources"] if s["outcome"] != "skip"]
        errored = [s for s in tried if s["outcome"] == "error"]
        if capped:
            res.update(status="PROBE_FAILED", note=f"{capped} before every source answered")
        elif tried and len(errored) == len(tried):
            res.update(status="PROBE_FAILED", note="every source tried errored: "
                       + "; ".join(f"{s['source']} {s['detail']}" for s in errored))
        else:
            res["status"] = "UNRESOLVED"
            if errored:
                res["note"] = ("partial: " + ", ".join(s["source"] for s in errored)
                               + " errored; re-run the resolver before fetching by hand")
        return {**info, **res}


# ---------------------------------------------------------------- the hand-fetch list

def hand_fetch_entry(res, reason=None):
    """The hand-fetch entry for an UNRESOLVED query: the URL, the reason and the Codex prompt."""
    target = res["blocked_url"] or (f"https://doi.org/{res['doi']}" if res["doi"] else None)
    if reason:
        why, detail = reason.replace("-", " "), "stated by the caller (--reason)"
    elif res.get("open_copy_on_refusing_host"):
        why, detail = "bot wall", ("an open copy exists only on the host that refused headless: "
                                   + res["open_copy_on_refusing_host"])
    elif res["doi"]:
        why, detail = "licensed", f"no open copy recorded for DOI {res['doi']} by the sources that answered"
    elif res["blocked_url"]:
        why, detail = "bot wall", "no DOI or title to resolve; the host refused headless"
    else:
        why, detail = "unknown", "no URL or DOI known; locate the paper before fetching it"
    slug = slug_from(target or res["query"], res["title"])
    subject = target or f'the paper titled "{res["title"] or res["query"]}"'
    return {"url": target, "reason": why, "reason_detail": detail,
            "sources_tried": [s["source"] for s in res["sources"] if s["outcome"] != "skip"],
            "slug": slug, "codex_prompt": CODEX_PROMPT.format(target=subject, scratch=SCRATCH_DIR, slug=slug),
            "warning": res.get("note")}


def render_text(res):
    ident = [f"kind {res['kind']}"]
    if res["doi"]:
        ident.append(f"doi {res['doi']}")
    if res["arxiv_id"]:
        ident.append(f"arXiv {res['arxiv_id']}")
    if res["refused_host"]:
        ident.append(f"refusing host {res['refused_host']}")
    lines = [f"query: {res['query']} · " + " · ".join(ident)]
    if res["title"]:
        lines.append(f"title: {res['title']}")
    for s in res["sources"]:
        n = s["requests"]
        lines.append(f"{s['source']}: {s['outcome']} — {s['detail']} · {n} request{'' if n == 1 else 's'}")
        for u in s.get("skipped_on_refusing_host") or []:
            lines.append(f"  skipped, on the refusing host: {u}")
    tried = ", ".join(s["source"] for s in res["sources"] if s["outcome"] != "skip") or "none"
    if res["status"] == "RESOLVED":
        lines.append(f"RESOLVED {res['url']} via {res['via']}")
    elif res["status"] == "UNRESOLVED":
        lines.append(f"UNRESOLVED (tried: {tried})" + (f" · {res['note']}" if res["note"] else ""))
    else:
        lines.append(f"PROBE FAILED: {res['note']} (tried: {tried})")
    lines.append(f"requests: {res['requests']} · transport {res['transport']}")
    hand = res.get("hand_fetch")
    if hand:
        lines += ["HAND-FETCH",
                  f"  url: {hand['url'] or 'none known'}",
                  f"  reason: {hand['reason']} — {hand['reason_detail']}",
                  f"  sources tried: {', '.join(hand['sources_tried']) or 'none'}",
                  f"  codex prompt: {hand['codex_prompt']}"]
        if hand["warning"]:
            lines.append(f"  warning: {hand['warning']}")
    elif res["status"] == "RESOLVED" and "hand_fetch" in res:
        lines.append("hand-fetch: not needed (resolved)")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="oa_resolve.py", formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Resolve a blocked DOI, arXiv id, URL or title to an open copy "
                    "(Unpaywall, OpenAlex, arXiv, Europe PMC); stdout only.",
        epilog="Exit 0 all resolved · 1 any UNRESOLVED · 2 any PROBE FAILED or a usage error. "
               "Env: OA_CONTACT_EMAIL (required courtesy contact), OA_TRANSPORT (curl or urllib), "
               "OA_RESOLVE_FIXTURES (replay recorded responses).")
    ap.add_argument("queries", nargs="+", metavar="QUERY", help="DOI, arXiv id, blocked URL or title")
    ap.add_argument("--title", help="a title beside a single DOI or URL (for the title searches)")
    ap.add_argument("--json", action="store_true", help="print one JSON array (one object per query)")
    ap.add_argument("--hand-fetch", dest="hand_fetch", action="store_true",
                    help="for an unresolved query print the HAND-FETCH block: URL, reason, Codex prompt")
    ap.add_argument("--reason", choices=["bot-wall", "licensed"],
                    help="with --hand-fetch: state the reason instead of deriving it")
    ap.add_argument("--max-requests", dest="max_requests", type=int,
                    help=f"cap on live requests for the whole invocation (default {PER_QUERY_REQUESTS} per query)")
    a = ap.parse_args(argv)
    if a.title and len(a.queries) != 1:
        ap.error("--title goes with a single QUERY")
    if a.reason and not a.hand_fetch:
        ap.error("--reason goes with --hand-fetch")
    if a.max_requests is not None and a.max_requests < 0:
        ap.error("--max-requests must be >= 0")
    contact = os.environ.get("OA_CONTACT_EMAIL", "").strip()
    if not contact:
        print("PROBE FAILED: set OA_CONTACT_EMAIL to your API contact address")
        return 2
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", contact):
        print("PROBE FAILED: OA_CONTACT_EMAIL must be an email address")
        return 2
    try:
        infos = [classify(q, a.title) for q in a.queries]
    except ValueError as e:
        print(f"oa_resolve: {e}", file=sys.stderr)
        return 2
    cap = a.max_requests if a.max_requests is not None else PER_QUERY_REQUESTS * len(infos)
    fixtures = os.environ.get("OA_RESOLVE_FIXTURES")
    results = []
    try:
        if fixtures:
            fetch, transport = replay_fetcher(fixtures), "replay"
        else:
            fetch, transport = pick_transport()
        resolver = Resolver(fetch, contact, cap, live=not fixtures, transport=transport,
                            log=lambda line: print(line, file=sys.stderr, flush=True))
        for n, info in enumerate(infos):
            res = resolver.resolve(info)
            if a.hand_fetch:
                res["hand_fetch"] = hand_fetch_entry(res, a.reason) if res["status"] == "UNRESOLVED" else None
            results.append(res)
            if not a.json:
                print(("\n" if n else "") + render_text(res), flush=True)
    except ProbeFailed as e:
        print(f"PROBE FAILED: {e}")
        return 2
    if a.json:
        print(json.dumps(results, indent=1, ensure_ascii=False))
    statuses = {r["status"] for r in results}
    return 2 if "PROBE_FAILED" in statuses else 1 if "UNRESOLVED" in statuses else 0


if __name__ == "__main__":
    sys.exit(main())
