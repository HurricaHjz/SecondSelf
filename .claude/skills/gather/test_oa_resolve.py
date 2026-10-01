#!/usr/bin/env python3
"""Tests for oa_resolve.py — run: python3 test_oa_resolve.py   (the last line is PASS n/n or FAIL k/n)

Offline by default. Every resolver run replays responses recorded once from the live APIs
(tests/fixtures/manifest.json; tests/fixtures/extra.json holds a recorded arXiv HTTP 429)
through OA_RESOLVE_FIXTURES, so no socket opens. Scenario manifests built in a temp
directory reuse those recorded bodies under other request URLs (a recorded 404 served for
a DOI, a 503 before a recorded 200) to reach each branch; bodies derived from a recorded
one, and the arXiv Atom bodies, are built here and labelled as synthetic fixtures.

Live acceptance: OA_LIVE=1 with OA_LIVE_LOG_DIR=<existing directory> runs the design page's
five acceptance cases against the live APIs, appends every request line to
<dir>/requests.log and every outcome to <dir>/real-acceptance.log, and never lets the
request log pass OA_LIVE_MAX_REQUESTS (default 40; set by judgement, unmeasured).
OA_LIVE_VAULT=<vault root> adds a read-only listing of raw/
before and after, reported beside the verdicts.
"""
import hashlib, json, os, re, shutil, stat, subprocess, sys, tempfile, time

sys.dont_write_bytecode = True
import oa_resolve as oa  # noqa: E402

HERE = os.path.dirname(os.path.realpath(__file__))
OA = os.path.join(HERE, "oa_resolve.py")
FIX = os.path.join(HERE, "tests", "fixtures")
P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
        print(f"  PASS  {name}")
    else:
        F += 1
        print(f"  FAIL  {name}")


def raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


TMP = tempfile.mkdtemp(prefix="oaresolve-test-")
C = "tests@example.org"  # a contact for building request URLs; fixture keys drop it
MISHRA_DOI = "10.1177/0272989X211044697"
MISHRA_TITLE = "Recalibration Methods for Improved Clinical Utility of Risk Scores"
MISHRA_PMC = "https://pmc.ncbi.nlm.nih.gov/articles/PMC8977399/"
SAGE_PDF = "https://journals.sagepub.com/doi/pdf/10.1177/0272989X211044697"
ABSENT_DOI = "10.5555/oa-resolve-absent-doi"
OR = "https://openreview.net/pdf?id=3V1p2bJugq"

with open(os.path.join(FIX, "manifest.json"), encoding="utf-8") as fh:
    MANIFEST = json.load(fh)
with open(os.path.join(FIX, "extra.json"), encoding="utf-8") as fh:
    EXTRA = json.load(fh)
BY_FILE = {e["file"]: e for e in MANIFEST.values()}
BY_FILE[EXTRA["arxiv-429"]["file"]] = EXTRA["arxiv-429"]

UP = lambda doi: oa.unpaywall_url(doi, C)
OD = lambda doi: oa.openalex_doi_url(doi, C)
OS_ = lambda title: oa.openalex_search_url(title, C)
AX = oa.arxiv_url
EP = lambda doi=None, title=None: oa.europepmc_url(doi=doi, title=title)


def rec(name):
    """A manifest entry that serves a recorded body with its recorded status."""
    return {"status": BY_FILE[name]["status"], "file": os.path.join(FIX, name)}


_count = 0


def scenario(entries, files=None):
    """A temp replay directory: manifest.json maps request URLs to entries; `files` are
    bodies built by the test, written beside it."""
    global _count
    _count += 1
    d = os.path.join(TMP, f"scenario-{_count}")
    os.makedirs(d)
    for name, text in (files or {}).items():
        with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump({oa.fixture_key(u): e for u, e in entries.items()}, fh, indent=1)
    return d


def run(args, fixtures, env_extra=None):
    env = {k: v for k, v in os.environ.items() if k not in ("OA_TRANSPORT", "OA_CONTACT_EMAIL", "OA_RESOLVE_FIXTURES")}
    env["OA_RESOLVE_FIXTURES"] = fixtures
    env["OA_CONTACT_EMAIL"] = C
    env.update(env_extra or {})
    return subprocess.run([sys.executable, OA] + list(args), capture_output=True, text=True, env=env, cwd=HERE)


def js(r):
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


# SYNTHETIC arXiv API bodies (Atom 1.0 with the arxiv: namespace).
# The HTTP 429 response replay is supplied separately in extra.json.
def atom(entries):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom" '
            'xmlns:arxiv="http://arxiv.org/schemas/atom">\n<title>arXiv Query</title>\n' + "".join(entries) + "</feed>\n")


def entry(aid, title, doi=None):
    return (f"<entry><id>http://arxiv.org/abs/{aid}</id><title>{title}</title><summary>s</summary>"
            + (f"<arxiv:doi>{doi}</arxiv:doi>" if doi else "")
            + f'<link title="pdf" href="http://arxiv.org/pdf/{aid}" rel="related" type="application/pdf"/></entry>\n')


EMPTY = scenario({})

print("== identity ==")
TABLE = [
    ("10.1002/qj.2985", "doi", "10.1002/qj.2985", None, None),
    ("doi:10.1002/qj.2985", "doi", "10.1002/qj.2985", None, None),
    ("https://doi.org/10.1002/qj.2985", "doi", "10.1002/qj.2985", None, None),
    ("https://rmets.onlinelibrary.wiley.com/doi/10.1002/qj.2985", "doi", "10.1002/qj.2985", None, "rmets.onlinelibrary.wiley.com"),
    ("https://www.tandfonline.com/doi/full/10.1080/01621459.2025.2576189", "doi", "10.1080/01621459.2025.2576189", None, "www.tandfonline.com"),
    ("arXiv:2307.03172v2", "arxiv", None, "2307.03172v2", None),
    ("https://arxiv.org/abs/2307.03172", "arxiv", None, "2307.03172", None),
    ("https://arxiv.org/pdf/2307.03172v3.pdf", "arxiv", None, "2307.03172v3", None),
    ("hep-th/9901001", "arxiv", None, "hep-th/9901001", None),
    ("10.48550/arXiv.2307.03172", "arxiv", "10.48550/arXiv.2307.03172", "2307.03172", None),
    (OR, "url", None, None, "openreview.net"),
    ("A title about scoring rules", "title", None, None, None),
    ("10.1016/0005-1098(94)90090-6.", "doi", "10.1016/0005-1098(94)90090-6", None, None),
    ("https://x.test/view?doi=10.1177/0272989X211044697&x=1", "doi", MISHRA_DOI, None, "x.test"),
]
wrong = []
for q, kind, doi, aid, host in TABLE:
    i = oa.classify(q)
    if (i["kind"], i["doi"], i["arxiv_id"], i["refused_host"]) != (kind, doi, aid, host):
        wrong.append(q)
check(f"classify: {len(TABLE) - len(wrong)}/{len(TABLE)} query forms identified" + (f" (wrong: {wrong})" if wrong else ""), not wrong)
check("empty query raises ValueError", raises(lambda: oa.classify("   "), ValueError))
check("title match: spelling folds score 1.0",
      oa.title_match("Localizing strictly proper scoring rules", "Localising Strictly Proper Scoring Rules") == 1.0)
T10 = "one two three four five six seven eight nine ten"
check("title match: one word of ten differs, matches", oa.title_match(T10, T10.replace("ten", "eleven")) >= oa.TITLE_MATCH_MIN)
check("title match: two words of ten differ, no match",
      oa.title_match(T10, T10.replace("ten", "x").replace("nine", "y")) < oa.TITLE_MATCH_MIN)
check("title match: an empty side scores 0", oa.title_match("", T10) == 0.0)
check("PMC URL normalised (and idempotent; other URLs untouched)",
      oa.normalise_url("https://www.ncbi.nlm.nih.gov/pmc/articles/8977399") == MISHRA_PMC
      and oa.normalise_url(MISHRA_PMC) == MISHRA_PMC and oa.normalise_url(SAGE_PDF) == SAGE_PDF)
check("fixture key drops the courtesy contact",
      oa.fixture_key(UP(MISHRA_DOI)) == oa.fixture_key(oa.unpaywall_url(MISHRA_DOI, "other@example.net"))
      and "email" not in oa.fixture_key(UP(MISHRA_DOI)))

print("== network grant and transports ==")
check("grant refuses a foreign host", raises(lambda: oa._grant("https://example.org/x"), oa.ProbeFailed))
check("grant refuses plain http to a granted host", raises(lambda: oa._grant("http://export.arxiv.org/api/query"), oa.ProbeFailed))
check("grant passes HTTPS to a granted host", not raises(lambda: oa._grant(UP(MISHRA_DOI)), Exception))
check("urllib never follows a redirect",
      oa._NoRedirects().redirect_request(None, None, 301, "Moved", {}, "https://example.org/") is None)
FAKE = os.path.join(TMP, "fakebin")
os.makedirs(FAKE)
FAKE_CURL = os.path.join(FAKE, "curl")
with open(FAKE_CURL, "w", encoding="utf-8") as fh:
    fh.write("#!" + sys.executable + "\n" + (
        "import json, os, sys\n"
        "mode = os.environ.get('FAKE_CURL_MODE', 'ok')\n"
        "if mode == 'exit28':\n"
        "    sys.stderr.write('curl: (28) Operation timed out\\n'); sys.exit(28)\n"
        "body = json.dumps(sys.argv[1:]).encode()\n"
        "if mode == 'serve':\n"
        "    body = open(os.environ['FAKE_CURL_FILE'], 'rb').read()\n"
        "tail = b'' if mode == 'nomark' else b'\\n@@oa-resolve-status@@200'\n"
        "sys.stdout.buffer.write(body + tail)\n"))
os.chmod(FAKE_CURL, 0o755)
os.environ["FAKE_CURL_MODE"] = "ok"
status, body, _ = oa.curl_fetch(UP(MISHRA_DOI), FAKE_CURL)
argv = json.loads(body)
check("curl transport parses the status and body", status == 200 and argv[-1] == UP(MISHRA_DOI))
check("curl args: -q first, HTTPS only, the 20 s cap, no -L",
      argv[0] == "-q" and argv[argv.index("--proto") + 1] == "=https"
      and argv[argv.index("--max-time") + 1] == str(oa.TIMEOUT_S) and "-L" not in argv and "--location" not in argv)
os.environ["FAKE_CURL_MODE"] = "exit28"
check("curl failure raises OSError (a network error)", raises(lambda: oa.curl_fetch(UP(MISHRA_DOI), FAKE_CURL), OSError))
os.environ["FAKE_CURL_MODE"] = "nomark"
check("curl output with no status raises OSError", raises(lambda: oa.curl_fetch(UP(MISHRA_DOI), FAKE_CURL), OSError))
check("curl is never spawned for a URL outside the grant",
      raises(lambda: oa.curl_fetch("https://example.org/", os.path.join(TMP, "no-such-curl")), oa.ProbeFailed))
saved = {k: os.environ.get(k) for k in ("PATH", "OA_TRANSPORT")}
os.environ["PATH"] = FAKE
os.environ.pop("OA_TRANSPORT", None)
check("transport default: curl when on PATH", oa.pick_transport()[1] == "curl")
os.environ["OA_TRANSPORT"] = "urllib"
check("transport forced: urllib", oa.pick_transport()[1] == "urllib")
os.environ["OA_TRANSPORT"] = "bogus"
check("transport: an unknown name is refused", raises(oa.pick_transport, oa.ProbeFailed))
EMPTYBIN = os.path.join(TMP, "emptybin")
os.makedirs(EMPTYBIN)
os.environ["PATH"] = EMPTYBIN
os.environ["OA_TRANSPORT"] = "curl"
check("transport: curl forced but absent is refused", raises(oa.pick_transport, oa.ProbeFailed))
os.environ.pop("OA_TRANSPORT")
check("transport fallback: urllib when curl is absent", oa.pick_transport()[1] == "urllib")
for k, v in saved.items():
    if v is None:
        os.environ.pop(k, None)
    else:
        os.environ[k] = v
os.environ.pop("FAKE_CURL_MODE", None)
live_env = {k: v for k, v in os.environ.items() if k != "OA_RESOLVE_FIXTURES"}
live_env.update({"PATH": FAKE, "OA_TRANSPORT": "curl", "FAKE_CURL_MODE": "serve", "OA_CONTACT_EMAIL": C,
                 "FAKE_CURL_FILE": os.path.join(FIX, "unpaywall-doi-mishra.json")})
r = subprocess.run([sys.executable, OA, "--json", MISHRA_DOI], capture_output=True, text=True, env=live_env, cwd=HERE)
j = js(r)
check("live path end to end on a stand-in curl: transport curl, the configured contact in the request, resolved",
      r.returncode == 0 and j and j[0]["transport"] == "curl" and j[0]["url"] == MISHRA_PMC and "(curl)" in r.stderr
      and "email=tests%40example.org" in r.stderr)

print("== the chain on recorded responses ==")
r = run(["2307.03172"], EMPTY)
check("arXiv id resolves to its PDF with no request (empty manifest)",
      r.returncode == 0 and "RESOLVED https://arxiv.org/pdf/2307.03172 via arxiv-id" in r.stdout
      and "requests: 0" in r.stdout and "request 1:" not in r.stderr)
check("arXiv id needs no request budget", run(["--max-requests", "0", "arXiv:2307.03172"], EMPTY).returncode == 0)
r = run(["--json", MISHRA_DOI], FIX)
j = js(r)
check("Mishra DOI resolves via Unpaywall to PMC (repository copy first)",
      r.returncode == 0 and j and j[0]["via"] == "unpaywall" and j[0]["url"] == MISHRA_PMC and j[0]["requests"] == 1)
check("the publisher copy is kept as an alternative", bool(j) and SAGE_PDF in j[0]["sources"][0]["alternatives"])
check("text verdict line: RESOLVED <url> via <source>", f"RESOLVED {MISHRA_PMC} via unpaywall" in run([MISHRA_DOI], FIX).stdout)
r = run(["--json", MISHRA_DOI], scenario({UP(MISHRA_DOI): rec("unpaywall-doi-absent.json"),
                                          OD(MISHRA_DOI): rec("openalex-doi-mishra.json")}))
j = js(r)
check("Unpaywall 404 falls through to OpenAlex",
      r.returncode == 0 and j and j[0]["via"] == "openalex" and j[0]["url"] == MISHRA_PMC and j[0]["requests"] == 2)
r = run(["--json", MISHRA_TITLE], FIX)
j = js(r)
check("title query: Unpaywall skipped, the OpenAlex search matches and learns the DOI",
      r.returncode == 0 and j and j[0]["sources"][0]["outcome"] == "skip" and j[0]["via"] == "openalex"
      and (j[0]["doi"] or "").lower() == MISHRA_DOI.lower())
r = run(["--json", MISHRA_DOI], scenario({UP(MISHRA_DOI): rec("unpaywall-doi-absent.json"),
                                          OD(MISHRA_DOI): rec("openalex-doi-absent.json"),
                                          EP(doi=MISHRA_DOI): rec("europepmc-doi-mishra.json")}))
j = js(r)
check("Europe PMC resolves when the sources before it miss",
      r.returncode == 0 and j and j[0]["via"] == "europepmc" and j[0]["url"] == MISHRA_PMC
      and [s["outcome"] for s in j[0]["sources"]] == ["miss", "miss", "skip", "hit"])
r = run([ABSENT_DOI], FIX)
check("every source misses: UNRESOLVED, exit 1, the sources named",
      r.returncode == 1 and "UNRESOLVED (tried: unpaywall, openalex, europepmc)" in r.stdout and "requests: 3" in r.stdout)

print("== retries, errors and the cap ==")
r = run(["--json", MISHRA_DOI], scenario({UP(MISHRA_DOI): [{"status": 503, "body": ""}, rec("unpaywall-doi-mishra.json")]}))
j = js(r)
check("a 5xx is retried once, then answered",
      r.returncode == 0 and j and j[0]["via"] == "unpaywall" and j[0]["sources"][0]["requests"] == 2)
r = run(["--json", MISHRA_DOI], scenario({UP(MISHRA_DOI): [{"status": 503, "body": ""}],
                                          OD(MISHRA_DOI): rec("openalex-doi-mishra.json")}))
j = js(r)
check("a second 5xx: one retry only, then the next source",
      r.returncode == 0 and j and j[0]["sources"][0]["outcome"] == "error" and j[0]["sources"][0]["requests"] == 2
      and j[0]["via"] == "openalex")
r = run(["--json", MISHRA_DOI], scenario({UP(MISHRA_DOI): {"error": "timed out"},
                                          OD(MISHRA_DOI): rec("openalex-doi-mishra.json")}))
j = js(r)
check("a network error is not retried",
      r.returncode == 0 and j and j[0]["sources"][0]["requests"] == 1 and "network error" in j[0]["sources"][0]["detail"])
r = run(["--json", MISHRA_DOI], scenario({UP(MISHRA_DOI): {"status": 301, "body": ""},
                                          OD(MISHRA_DOI): rec("openalex-doi-mishra.json")}))
j = js(r)
check("a 3xx is the source's error and is not followed",
      r.returncode == 0 and j and "redirect not followed" in j[0]["sources"][0]["detail"] and j[0]["sources"][0]["requests"] == 1)
r = run([ABSENT_DOI], scenario({UP(ABSENT_DOI): {"status": 503, "body": ""}, OD(ABSENT_DOI): {"error": "connection refused"},
                                EP(doi=ABSENT_DOI): {"status": 502, "body": ""}}))
check("every source errored: PROBE FAILED, exit 2, never UNRESOLVED",
      r.returncode == 2 and "PROBE FAILED: every source tried errored" in r.stdout and "UNRESOLVED" not in r.stdout)
r = run(["--max-requests", "1", ABSENT_DOI], FIX)
check("the request cap cuts the chain: PROBE FAILED, exit 2", r.returncode == 2 and "request cap 1 reached" in r.stdout)
r = run(["--hand-fetch", ABSENT_DOI], scenario({UP(ABSENT_DOI): rec("unpaywall-doi-absent.json"),
                                               OD(ABSENT_DOI): {"error": "timed out"},
                                               EP(doi=ABSENT_DOI): rec("europepmc-doi-absent.json")}))
check("a partial answer: UNRESOLVED, and the hand-fetch block warns to re-run",
      r.returncode == 1 and "partial: openalex errored" in r.stdout and "  warning: partial" in r.stdout)

print("== arXiv (synthetic Atom bodies; the recorded 429) ==")
LITM_TITLE = "Lost in the Middle: How Language Models Use Long Contexts"
LITM_DOI = "10.1162/tacl_a_00638"
BASE = {UP(LITM_DOI): rec("unpaywall-doi-absent.json"), OD(LITM_DOI): rec("openalex-doi-absent.json"),
        EP(doi=LITM_DOI): rec("europepmc-doi-absent.json")}
r = run(["--json", "--title", LITM_TITLE, LITM_DOI], scenario(
    {**BASE, AX(LITM_TITLE): {"status": 200, "file": "hit.xml"}},
    files={"hit.xml": atom([entry("2306.00001v1", "Something else entirely"),
                            entry("2307.03172v3", "Lost in the\n  Middle: How Language Models Use Long Contexts", LITM_DOI)])}))
j = js(r)
check("arXiv title search resolves: the non-matching record passed over, the version dropped",
      r.returncode == 0 and j and j[0]["via"] == "arxiv" and j[0]["url"] == "https://arxiv.org/pdf/2307.03172")
r = run(["--json", "--title", LITM_TITLE, LITM_DOI], scenario(
    {**BASE, AX(LITM_TITLE): {"status": 200, "file": "other.xml"}},
    files={"other.xml": atom([entry("2307.03172v3", LITM_TITLE, "10.9999/another-work")])}))
j = js(r)
check("an arXiv record carrying a different DOI is rejected", r.returncode == 1 and j and j[0]["sources"][2]["outcome"] == "miss")
r = run(["--json", "--title", LITM_TITLE, LITM_DOI], scenario(
    {**BASE, AX(LITM_TITLE): {"status": 200, "file": "err.xml"}},
    files={"err.xml": atom(["<entry><id>http://arxiv.org/api/errors#malformed_query</id><title>Error</title>"
                            "<summary>malformed query</summary></entry>\n"])}))
j = js(r)
check("an arXiv API error entry is the source's error",
      bool(j) and j[0]["sources"][2]["outcome"] == "error" and "arXiv API error" in j[0]["sources"][2]["detail"])
r = run(["--json", "--title", LITM_TITLE, LITM_DOI], scenario({**BASE, AX(LITM_TITLE): rec("arxiv-429.txt")}))
j = js(r)
check("the recorded arXiv 429 is the source's error and is not retried",
      bool(j) and j[0]["sources"][2]["outcome"] == "error" and j[0]["sources"][2]["requests"] == 1
      and "HTTP 429" in j[0]["sources"][2]["detail"])
r = run(["--json", "--title", LITM_TITLE, LITM_DOI], scenario({**BASE, AX(LITM_TITLE): {"status": 200, "body": "<feed><unclosed"}}))
j = js(r)
check("an unreadable Atom body is the source's error", bool(j) and j[0]["sources"][2]["outcome"] == "error")

print("== the host that refused headless ==")
REFUSED = "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8977399/?doi=10.1177/0272989X211044697"
r = run(["--json", REFUSED], FIX)
j = js(r)
check("an open copy on the refusing host is skipped and the next copy taken",
      r.returncode == 0 and j and j[0]["url"] == SAGE_PDF and MISHRA_PMC in j[0]["sources"][0]["skipped_on_refusing_host"])
with open(os.path.join(FIX, "unpaywall-doi-mishra.json"), encoding="utf-8") as fh:
    derived_u = json.load(fh)  # DERIVED from the recorded body: repository locations removed
derived_u["oa_locations"] = [loc for loc in derived_u["oa_locations"] if loc.get("host_type") != "repository"]
with open(os.path.join(FIX, "openalex-doi-mishra.json"), encoding="utf-8") as fh:
    derived_o = json.load(fh)  # DERIVED from the recorded body: repository locations removed
derived_o["locations"] = [loc for loc in derived_o["locations"] if (loc.get("source") or {}).get("type") != "repository"]
SAGE_URL = "https://journals.sagepub.com/doi/10.1177/0272989X211044697"
r = run(["--hand-fetch", SAGE_URL], scenario(
    {UP(MISHRA_DOI): {"status": 200, "file": "u.json"}, OD(MISHRA_DOI): {"status": 200, "file": "o.json"},
     AX(MISHRA_TITLE): {"status": 200, "file": "none.xml"}, EP(doi=MISHRA_DOI): rec("europepmc-doi-absent.json")},
    files={"u.json": json.dumps(derived_u), "o.json": json.dumps(derived_o), "none.xml": atom([])}))
check("the only open copy on the refusing host: the hand-fetch list, as a bot wall",
      r.returncode == 1 and "  reason: bot wall — an open copy exists only on the host that refused headless" in r.stdout)

print("== the hand-fetch list ==")
PROMPT = (f"Fetch {OR}, save the full text as Markdown to ~/.llm-wiki/gather-scratch/"
          "openreview-net-pdf-id-3v1p2bjugq.md, keep the title and the section headings")
r = run(["--hand-fetch", OR], EMPTY)
check("OpenReview URL: no DOI, no request, a hand-fetch block",
      r.returncode == 1 and "requests: 0" in r.stdout and "HAND-FETCH" in r.stdout and f"  url: {OR}" in r.stdout)
check("hand-fetch reason: bot wall", "  reason: bot wall — no DOI or title to resolve" in r.stdout)
check("hand-fetch Codex prompt, verbatim template", f"  codex prompt: {PROMPT}" in r.stdout)
r = run(["--hand-fetch", "https://journal.test/doi/10.5555/oa-resolve-absent-doi"], FIX)
check("licensed: a DOI with no open copy, the prompt names the blocked URL",
      r.returncode == 1 and "  reason: licensed — no open copy recorded for DOI 10.5555/oa-resolve-absent-doi" in r.stdout
      and "Fetch https://journal.test/doi/10.5555/oa-resolve-absent-doi," in r.stdout)
r = run(["--hand-fetch", MISHRA_DOI], FIX)
check("must not fire: a resolved query prints no hand-fetch block",
      r.returncode == 0 and "HAND-FETCH" not in r.stdout and "hand-fetch: not needed (resolved)" in r.stdout)
r = run(["--hand-fetch", "--reason", "licensed", OR], EMPTY)
check("--reason overrides the derived reason", "  reason: licensed — stated by the caller" in r.stdout)
r = run(["--json", "--hand-fetch", OR], EMPTY)
j = js(r)
check("--json carries the hand-fetch entry",
      r.returncode == 1 and j and j[0]["hand_fetch"]["reason"] == "bot wall" and j[0]["hand_fetch"]["codex_prompt"] == PROMPT)
r = run(["--json", "2307.03172", OR], EMPTY)
j = js(r)
check("several queries: one JSON array, exit 1 when any is unresolved",
      r.returncode == 1 and j and [x["status"] for x in j] == ["RESOLVED", "UNRESOLVED"])
NOBODY = "A title nobody resolves"
r = run(["--hand-fetch", NOBODY], scenario(
    {OS_(NOBODY): rec("openalex-search-mishra.json"), AX(NOBODY): {"status": 200, "file": "none.xml"},
     EP(title=NOBODY): rec("europepmc-doi-absent.json")}, files={"none.xml": atom([])}))
check("a title with no URL or DOI: reason unknown, the prompt names the title",
      r.returncode == 1 and "  reason: unknown" in r.stdout and f'Fetch the paper titled "{NOBODY}"' in r.stdout)

print("== usage and premises ==")
check("empty query: exit 2", run([""], EMPTY).returncode == 2)
check("--reason without --hand-fetch: exit 2", run(["--reason", "licensed", OR], EMPTY).returncode == 2)
check("--title with two queries: exit 2", run(["--title", "T", "a", "b"], EMPTY).returncode == 2)
check("negative --max-requests: exit 2", run(["--max-requests", "-1", OR], EMPTY).returncode == 2)
r = run([MISHRA_DOI], FIX, env_extra={"OA_CONTACT_EMAIL": "not-an-address"})
check("a malformed courtesy contact: PROBE FAILED, exit 2, the value not echoed",
      r.returncode == 2 and "PROBE FAILED" in r.stdout and "not-an-address" not in r.stdout + r.stderr)
r = run([MISHRA_DOI], FIX, env_extra={"OA_CONTACT_EMAIL": ""})
check("a missing courtesy contact: PROBE FAILED naming OA_CONTACT_EMAIL, exit 2, no request made",
      r.returncode == 2 and "PROBE FAILED: set OA_CONTACT_EMAIL" in r.stdout
      and "request 1:" not in r.stderr and "query:" not in r.stdout)
r = run([MISHRA_DOI], FIX)
check("a configured courtesy contact reaches the request URL (replayed transport, no network)",
      r.returncode == 0 and "email=tests%40example.org" in r.stderr)
r = run([MISHRA_DOI], os.path.join(TMP, "no-such-dir"))
check("a missing replay manifest: PROBE FAILED, exit 2", r.returncode == 2 and "PROBE FAILED: replay manifest unreadable" in r.stdout)
r = run([MISHRA_DOI], EMPTY)
check("a request with no recorded response: PROBE FAILED, exit 2",
      r.returncode == 2 and "PROBE FAILED: no recorded response" in r.stdout)

print("== recorded fixtures ==")
problems = []
for key, e in list(MANIFEST.items()) + [(EXTRA["arxiv-429"]["url"], EXTRA["arxiv-429"])]:
    path = os.path.join(FIX, e["file"])
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        problems.append(e["file"])
        continue
    if e["file"].endswith(".json") and e["status"] == 200:
        try:
            with open(path, encoding="utf-8") as fh:
                json.load(fh)
        except ValueError:
            problems.append(e["file"])
    if not key.startswith("https://") or oa.urllib.parse.urlsplit(key).hostname not in oa.ALLOWED_HOSTS:
        problems.append(key)
check(f"fixtures: {len(MANIFEST) + 1} recorded responses present, readable, keyed inside the grant"
      + (f" (problems: {problems})" if problems else ""), not problems and len(MANIFEST) >= 7)
COURTESY = re.compile(r"[?&](?:email|mailto)=", re.I)
planted = UP(MISHRA_DOI)  # a synthetic request URL carrying the test contact: the probe's positive control


def courtesy_hits(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return len(COURTESY.findall(fh.read()))


leaks = [name for name in sorted(os.listdir(FIX)) if courtesy_hits(os.path.join(FIX, name))]
leaks += [key for key in list(MANIFEST) + [EXTRA["arxiv-429"]["url"]] if COURTESY.search(key)]
check(f"fixtures and recorded keys carry no courtesy parameter ({len(leaks)} hits; control: the planted "
      f"request URL fires {bool(COURTESY.search(planted))}, its fixture key {bool(COURTESY.search(oa.fixture_key(planted)))})",
      not leaks and "email=tests%40example.org" in planted and bool(COURTESY.search(planted))
      and not COURTESY.search(oa.fixture_key(planted)))
check("the module keeps no fallback contact (no DEFAULT_CONTACT)", not hasattr(oa, "DEFAULT_CONTACT"))

print("== the resolver writes nothing ==")


def tree_manifest(root):
    out = {}
    for dp, dns, fns in os.walk(root):
        for d in dns:
            out[os.path.relpath(os.path.join(dp, d), root) + "/"] = "dir"
        for f in fns:
            p = os.path.join(dp, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, root)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def set_writable(root, writable):
    paths = [root]
    for dp, dns, fns in os.walk(root):
        paths += [os.path.join(dp, n) for n in dns + fns]
    for p in (paths if writable else reversed(paths)):
        mode = os.stat(p).st_mode
        os.chmod(p, (mode | stat.S_IWUSR) if writable else (mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)))


COPY = os.path.join(TMP, "copy")
os.makedirs(os.path.join(COPY, "tests"))
for name in ("oa_resolve.py", "capture_write.py", "run_ledger.py"):
    shutil.copy2(os.path.join(HERE, name), COPY)
shutil.copytree(FIX, os.path.join(COPY, "tests", "fixtures"))
NOBC = {k: v for k, v in os.environ.items() if k not in ("PYTHONDONTWRITEBYTECODE", "OA_TRANSPORT", "OA_CONTACT_EMAIL")}
COPY_CASES = [(["--json", MISHRA_DOI], 0), (["--hand-fetch", OR], 1), ([ABSENT_DOI], 1)]


def run_copy(args):
    env = dict(NOBC)
    env["OA_CONTACT_EMAIL"] = C
    env["OA_RESOLVE_FIXTURES"] = os.path.join(COPY, "tests", "fixtures")
    return subprocess.run([sys.executable, os.path.join(COPY, "oa_resolve.py")] + args,
                          capture_output=True, text=True, env=env, cwd=COPY)


before = tree_manifest(COPY)
codes = [run_copy(a).returncode for a, _ in COPY_CASES]
check("writable copy, bytecode env unset: expected exits, tree unchanged (no __pycache__, no file)",
      codes == [c for _, c in COPY_CASES] and tree_manifest(COPY) == before)
with open(os.path.join(COPY, "planted.txt"), "w", encoding="utf-8") as fh:
    fh.write("x")
check("control: the tree manifest sees a planted file", tree_manifest(COPY) != before)
os.remove(os.path.join(COPY, "planted.txt"))
subprocess.run([sys.executable, "-c", "import capture_write"], cwd=COPY, env=NOBC, capture_output=True)
check("control: a plain import without the guard does write __pycache__",
      any(k.startswith("__pycache__") for k in tree_manifest(COPY)))
shutil.rmtree(os.path.join(COPY, "__pycache__"), ignore_errors=True)
before = tree_manifest(COPY)
set_writable(COPY, False)
results = [run_copy(a) for a, _ in COPY_CASES]
set_writable(COPY, True)
check("read-only copy: the same exits, no traceback, tree unchanged",
      [x.returncode for x in results] == [c for _, c in COPY_CASES]
      and not any("Traceback" in x.stderr for x in results) and tree_manifest(COPY) == before)
WRITE_PAT = re.compile(r"""open\(.*['"][wax]b?\+?['"]|\.write\(|\bos\.(?:remove|unlink|rename|replace|makedirs|mkdir|rmdir|chmod)\(|\bshutil\.(?:copy|move|rmtree)|write_(?:text|bytes)\(""")


def write_lines(path):
    with open(path, encoding="utf-8") as fh:
        return [i for i, line in enumerate(fh, 1) if WRITE_PAT.search(line)]


hits = write_lines(OA)
control = write_lines(os.path.join(HERE, "capture_write.py"))
check(f"source grep: oa_resolve.py write calls {len(hits)}" + (f" (lines {hits})" if hits else ""), not hits)
check(f"control: the same grep hits capture_write.py ({len(control)} lines)", len(control) > 0)

if os.environ.get("OA_LIVE") == "1":
    print("== live acceptance (OA_LIVE=1) ==")
    LOG_DIR = os.environ.get("OA_LIVE_LOG_DIR", "")
    if not LOG_DIR or not os.path.isdir(LOG_DIR):
        print("PROBE FAILED: OA_LIVE=1 needs OA_LIVE_LOG_DIR, an existing directory for requests.log and real-acceptance.log")
        shutil.rmtree(TMP, ignore_errors=True)
        sys.exit(2)
    if os.environ.get("OA_CONTACT_EMAIL", "").strip() in ("", C):
        print("PROBE FAILED: OA_LIVE=1 needs OA_CONTACT_EMAIL set to your own API contact address, never the test contact")
        shutil.rmtree(TMP, ignore_errors=True)
        sys.exit(2)
    GRANT = int(os.environ.get("OA_LIVE_MAX_REQUESTS", "40"))
    REQ_LOG = os.path.join(LOG_DIR, "requests.log")
    ACC_LOG = os.path.join(LOG_DIR, "real-acceptance.log")
    REQ = re.compile(r"\brequest \d+: GET ")
    VAULT = os.environ.get("OA_LIVE_VAULT")

    def used():
        if not os.path.exists(REQ_LOG):
            return 0
        with open(REQ_LOG, encoding="utf-8") as fh:
            return sum(1 for line in fh if REQ.search(line))

    def append(path, text):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)

    def raw_listing():
        if not VAULT:
            return None
        found = set()
        for dp, _dns, fns in os.walk(os.path.join(VAULT, "raw")):
            found.update(os.path.join(dp, f) for f in fns)
        return found

    OPEN_OR_LIST = "resolves to an open copy off the refusing host, or goes to the hand-fetch list with no file written"
    LIVE_CASES = [
        ("JASA article (de Punder et al.), the Taylor & Francis URL",
         "https://www.tandfonline.com/doi/full/10.1080/01621459.2025.2576189", OPEN_OR_LIST, "open-or-list",
         "10.1080/01621459.2025.2576189"),
        ("Siegert 2017, the Wiley QJRMS URL", "https://rmets.onlinelibrary.wiley.com/doi/10.1002/qj.2985",
         OPEN_OR_LIST, "open-or-list", "10.1002/qj.2985"),
        ("Mishra 2022, the DOI", MISHRA_DOI, "resolves through Europe PMC or another source", "resolved", MISHRA_DOI),
        ("arXiv 2307.03172, the headless control", "2307.03172",
         "stays headless: its own PDF at once, no API call", "arxiv", None),
        ("DCPO, the OpenReview PDF", OR, "has no DOI and lands on the hand-fetch list", "list", None),
    ]
    skill_before = tree_manifest(HERE)
    raw_before = raw_listing()
    append(ACC_LOG, f"\n# live acceptance run {time.strftime('%Y-%m-%dT%H:%M:%S')} · oa_resolve.py · "
                    f"request grant {GRANT} · requests already in the log {used()}\n")
    for n, (name, query, expect, kind, doi) in enumerate(LIVE_CASES, 1):
        left = GRANT - used()
        networked = kind in ("open-or-list", "resolved")
        if networked and left < 1:
            append(ACC_LOG, f"\n== case {n}/5: {name} ==\nNOT RUN: the request grant is spent ({used()}/{GRANT})\nverdict: FAIL\n")
            check(f"live {n}: {name} (not run: the grant is spent)", False)
            continue
        cap = min(oa.PER_QUERY_REQUESTS, max(left, 0))
        env = {k: v for k, v in os.environ.items() if k != "OA_RESOLVE_FIXTURES"}
        t0 = time.time()
        proc = subprocess.run([sys.executable, OA, "--json", "--hand-fetch", "--max-requests", str(cap), query],
                              capture_output=True, text=True, env=env, cwd=HERE)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        lines = [line for line in proc.stderr.splitlines() if REQ.search(line)]
        base = used()
        for i, line in enumerate(lines, 1):
            append(REQ_LOG, f"{stamp} acceptance case {n} " + re.sub(r"^request \d+:", f"request {base + i}:", line) + "\n")
        try:
            res = json.loads(proc.stdout)[0]
        except (ValueError, IndexError, KeyError):
            res = None
        if res is None:
            good, why = False, f"no JSON result (exit {proc.returncode}): {proc.stdout.strip()[-300:]}"
        elif kind == "open-or-list":
            refused = oa.classify(query)["refused_host"]
            if res["doi"] != doi:
                good, why = False, f"DOI read as {res['doi']}, expected {doi}"
            elif res["status"] == "RESOLVED":
                off = oa._site(oa.urllib.parse.urlsplit(res["url"]).hostname) != oa._site(refused)
                good, why = off, f"resolved to {res['url']} via {res['via']}" + ("" if off else ", ON the refusing host")
            elif res["status"] == "UNRESOLVED" and res.get("hand_fetch"):
                good = True
                why = f"unresolved; on the hand-fetch list as {res['hand_fetch']['reason']}" + (f" ({res['note']})" if res["note"] else "")
            else:
                good, why = False, f"{res['status']}: {res['note']}"
        elif kind == "resolved":
            good = res["status"] == "RESOLVED"
            why = f"{res['status']} {res['url'] or res['note']} via {res['via']}"
        elif kind == "arxiv":
            good = res["status"] == "RESOLVED" and res["via"] == "arxiv-id" and res["requests"] == 0 and not lines
            why = f"{res['status']} {res['url']} via {res['via']}, {res['requests']} requests"
        else:
            hand = res.get("hand_fetch") or {}
            good = res["status"] == "UNRESOLVED" and res["requests"] == 0 and hand.get("reason") == "bot wall"
            why = f"{res['status']}, {res['requests']} requests, hand-fetch reason {hand.get('reason')}"
        text = oa.render_text(res) if res else proc.stdout
        append(ACC_LOG, f"\n== case {n}/5: {name} ==\nexpectation: {expect}\nexit {proc.returncode} · requests this case "
                        f"{len(lines)} · {time.time() - t0:.1f} s\n{text}\nverdict: {'PASS' if good else 'FAIL'} — {why}\n")
        check(f"live {n}: {name}: {why}", good)
        if networked:
            time.sleep(oa.ARXIV_SPACING_S)
    unchanged = tree_manifest(HERE) == skill_before
    raw_after = raw_listing()
    if raw_before is None:
        raw_note = "raw/ not listed (OA_LIVE_VAULT unset)"
    else:
        new = sorted(raw_after - raw_before)
        raw_note = (f"raw/ listed read-only before and after: {len(raw_before)} files before (control), "
                    f"{len(new)} new during the run" + (f": {new}" if new else ""))
    append(ACC_LOG, f"\nno-write evidence: the skill folder's checksum manifest is {'unchanged' if unchanged else 'CHANGED'} "
                    f"across the five cases; {raw_note}\nrequests in the run's log now: {used()} of {GRANT}\n")
    check("live: the skill folder is unchanged across the five cases (no file written)", unchanged)
else:
    print("== live acceptance skipped (OA_LIVE=1 with OA_LIVE_LOG_DIR runs it) ==")

shutil.rmtree(TMP, ignore_errors=True)
TOTAL = P + F
print(f"\nPASS {P}/{TOTAL}" if not F else f"\nFAIL {F}/{TOTAL}")
sys.exit(1 if F else 0)
