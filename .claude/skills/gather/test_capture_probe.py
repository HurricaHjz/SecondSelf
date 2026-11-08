#!/usr/bin/env python3
"""Suite for capture_probe.py and the capture check's stamp on both save paths (capture_write.py for the
gather skill, `capture_probe.py stamp` for the ingest skill's Step 0): the check warns, and no save path
refuses a write for anything it finds or for a missing or failed result. Run: python3 test_capture_probe.py

Needs markitdown importable by this interpreter (it is run as `python3 -m markitdown`) and defuddle on
PATH: either missing prints PROBE FAILED and exits 2, never a pass. No network: curl is a stub serving
synthetic pages in the shapes of the recorded losses. Fixtures live in one temporary directory, removed
at the end; run ledgers go where run_ledger.py puts them and are removed too.
Optional: CAPTURE_PROBE_INGEST_SKILL names the ingest SKILL.md to read (default ../ingest/SKILL.md);
CAPTURE_PROBE_PYTHON names the interpreter that runs `-m markitdown` (default: this one). The lane
variables are cleared at the start, so the ordinary legs exercise the attended behaviour wherever the
suite runs; the lane legs set them themselves.
Ends PASS n/n or FAIL k/n. Legs named "control:" pass on the old files too. The routing, acquisition,
link and lane legs are the admission design's own and pass on its build as well; every leg of the stamp,
the warning-only check and the removed gate is a regression arm that fails on that build (INSTALL.md
lists them).
"""
import atexit, hashlib, importlib.util, json, os, re, shutil, stat, subprocess, sys, tempfile, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
MD_PY = os.environ.get("CAPTURE_PROBE_PYTHON") or PY
LANE_VARS = ("LLM_WIKI_LANE", "LLM_WIKI_LANE_NETWORK", "LLM_WIKI_LANE_WRITES")
for _var in LANE_VARS:
    os.environ.pop(_var, None)
CP = os.path.join(HERE, "capture_probe.py")
CW = os.path.join(HERE, "capture_write.py")
INGEST_DIR = os.path.normpath(os.path.join(HERE, "..", "ingest"))
INGEST_SKILL = os.environ.get("CAPTURE_PROBE_INGEST_SKILL") or os.path.join(INGEST_DIR, "SKILL.md")

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond or not detail else "  [" + str(detail)[:300] + "]"))


def leg(name, fn):
    """Run one leg; an exception is that leg's failure, never the suite's crash."""
    try:
        out = fn()
        cond, detail = out if isinstance(out, tuple) else (out, "")
    except Exception as exc:
        cond, detail = False, f"{type(exc).__name__}: {exc}"
    check(name, cond, detail)


# ---------------------------------------------------------------- premises: real converters, or no run
p = subprocess.run([MD_PY, "-c", "import markitdown"], capture_output=True, text=True)
if p.returncode != 0:
    print(f"PROBE FAILED: markitdown does not import for {MD_PY} ({(p.stderr.strip().splitlines() or ['no message'])[-1]}); "
          "the conversion legs cannot run, so no pass is claimed")
    sys.exit(2)
DEFUDDLE = shutil.which("defuddle")
if not DEFUDDLE:
    print("PROBE FAILED: defuddle is not on PATH; the NOT-ROUTED conversion legs cannot run, so no pass is claimed")
    sys.exit(2)

T = tempfile.mkdtemp(prefix="cptest-")
VAULT = os.path.join(T, "vault")
for d in ("raw", "wiki"):
    os.makedirs(os.path.join(VAULT, d))
sys.dont_write_bytecode = True
sys.path.insert(0, HERE)
import run_ledger as rl  # noqa: E402
RID = f"cptest-{uuid.uuid4().hex[:8]}"
rl.init(RID, 60)


def _tidy():
    """Remove the fixtures and the run ledger on any exit, a crash included."""
    try:
        os.remove(rl.path_for(RID))
    except OSError:
        pass
    for root, dirs, files in os.walk(T):
        os.chmod(root, 0o755)
    shutil.rmtree(T, ignore_errors=True)


atexit.register(_tidy)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cp_module():
    return load(CP, "capture_probe")


def put(path, text, mode=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    if mode:
        os.chmod(path, mode)
    return path


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# ---------------------------------------------------------------- stand-ins
put(os.path.join(T, "stub_curl.py"), r'''
"""Stand-in for curl: serves the responses a JSON spec lists, one per call, and counts the calls."""
import json, os, sys
args = sys.argv[1:]
out, fmt, url = args[args.index("-o") + 1], args[args.index("-w") + 1], args[-1]
spec_path = os.environ["STUB_CURL_SPEC"]
with open(spec_path, encoding="utf-8") as fh:
    spec = json.load(fh)
calls = 0
if os.path.exists(spec_path + ".calls"):
    with open(spec_path + ".calls", encoding="utf-8") as fh:
        calls = int(fh.read() or 0)
with open(spec_path + ".calls", "w", encoding="utf-8") as fh:
    fh.write(str(calls + 1))
with open(spec_path + ".argv", "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\n")
resp = spec["responses"][min(calls, len(spec["responses"]) - 1)]
if resp.get("body") is not None:
    with open(out, "wb") as fh:
        fh.write(resp["body"].encode("utf-8"))
sys.stdout.write(fmt.replace("%{http_code}", str(resp.get("code", 200)))
                    .replace("%{content_type}", resp.get("type", "text/html; charset=utf-8"))
                    .replace("%{url_effective}", resp.get("effective", url))
                    .replace("%{num_redirects}", str(resp.get("redirects", 0)))
                    .replace("%{redirect_url}", resp.get("redirect", "")))
sys.stderr.write(resp.get("stderr", ""))
sys.exit(resp.get("exit", 0))
''')
CURL = put(os.path.join(T, "curl-stub"), '#!/bin/sh\nexec "%s" -B "%s" "$@"\n' % (PY, os.path.join(T, "stub_curl.py")), 0o755)
NO_MARKITDOWN = put(os.path.join(T, "python-without-markitdown"),
                    '#!/bin/sh\necho "No module named markitdown" 1>&2\nexit 1\n', 0o755)
FAILING_DEFUDDLE = put(os.path.join(T, "defuddle-failing"),
                       '#!/bin/sh\necho "Error: No content could be extracted" 1>&2\nexit 1\n', 0o755)

# ---------------------------------------------------------------- pages in the shapes of the recorded losses
# Visible prose long enough for every capture to clear the writer's size floor, so a refusal in these
# legs can only come from the probe contract.
LEAD = ("<p>This page explains who may apply, what the programme offers and how a decision is reached. "
        "Each section below was written for applicants reading it on a phone or a desktop, and the "
        "summary here is repeated in the guidance notes that accompany the application form. "
        "Readers who need the text in another format can ask the programme office, which answers "
        "within five working days and keeps a record of every request it receives. The office also "
        "publishes a short guide to the assessment, the panel's membership and the timetable for "
        "decisions, so that applicants can plan their work around the dates that matter to them.</p>")
FUNDING_URL = "https://www.example.org/grants/founder/"
FUNDING = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Founder Grants | Example Enterprise Centre</title></head>
<body><header><nav><a href="/">Home</a> <a href="/programmes/">Programmes</a></nav></header>
<main><article>
<h1>Founder Grants</h1>
<p>Grants of up to £5,000 for student founders at an early stage.</p>
""" + LEAD + """
<p>Read the <a href="terms">full terms</a> or <a href="../apply/">apply now</a>.</p>
<div class="accordion" id="faq">
<div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button collapsed" type="button" aria-expanded="false" aria-controls="eligibility">Eligibility</button></h2>
<div id="eligibility" class="accordion-collapse collapse" hidden><div class="accordion-body">
<p>Applicants must be enrolled students or recent graduates.</p>
<p>Student visa holders ineligible.</p>
</div></div></div>
<div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button collapsed" type="button" aria-expanded="false" aria-controls="deadline">Deadline</button></h2>
<div id="deadline" class="accordion-collapse collapse" aria-hidden="true"><div class="accordion-body">
<p>Applications close on 31 October 2026 at 12:00.</p>
</div></div></div>
</div>
<details><summary>Visa terms</summary>Graduate visa holders may apply with written confirmation of their right to work.</details>
</article></main>
<footer><p>Example Enterprise Centre</p></footer>
</body></html>
"""
FUNDING_TERMS = ["Applicants must be enrolled students or recent graduates.", "Student visa holders ineligible.",
                 "Applications close on 31 October 2026 at 12:00.",
                 "Graduate visa holders may apply with written confirmation of their right to work."]
VISA = "Student visa holders ineligible."

LIMIT_LABELS = ("Alpha Phase 1", "Alpha Phase 2", "Beta Grace", "Beta MACS")
LIMIT_ROWS = (("gpu", "256", "24 hours"), ("gpu", "1024", "24 hours"), ("grace", "128", "48 hours"), ("macs", "16", "12 hours"))


def mkdocs_set(n, labels, blocks):
    inputs = "".join('<input %sid="__tabbed_%d_%d" name="__tabbed_%d" type="radio">' % ('checked="checked" ' if i == 1 else "", n, i, n)
                     for i in range(1, len(labels) + 1))
    labs = "".join('<label for="__tabbed_%d_%d">%s</label>' % (n, i, lab) for i, lab in enumerate(labels, 1))
    blks = "".join('<div class="tabbed-block">%s</div>' % b for b in blocks)
    return ('<div class="tabbed-set tabbed-alternate" data-tabs="%d:%d">%s<div class="tabbed-labels">%s</div>'
            '<div class="tabbed-content">%s</div></div>' % (n, len(labels), inputs, labs, blks))


def limits_table(row):
    return ("<table><thead><tr><th>Partition</th><th>Max nodes per job</th><th>Max walltime</th></tr></thead>"
            "<tbody><tr><td>%s</td><td>%s</td><td>%s</td></tr></tbody></table>" % row)


def doc(body, title="Fixture page"):
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>%s</title></head><body>'
            '<div class="md-container"><main class="md-main"><article class="md-content__inner">'
            '<h1>%s</h1>%s%s</article></main></div></body></html>' % (title, title, LEAD, body))


LIMITS_URL = "https://docs.example.org/user-documentation/jobs/limits/"
LIMITS = doc("<h2>Job limits</h2>" + mkdocs_set(1, LIMIT_LABELS, [limits_table(r) for r in LIMIT_ROWS]), "Job scheduling")
NESTED = doc(mkdocs_set(1, ("Linux", "macOS"), [
    "<p>Install with the package manager.</p>" + mkdocs_set(2, ("x86", "ARM"), ["<p>Use the amd64 build.</p>", "<p>Use the aarch64 build.</p>"]),
    "<p>Install with the disk image.</p>"]), "Nested tabs")
REPEATED = doc(mkdocs_set(1, ("Linux", "macOS"), ["<p>Download the tarball for servers.</p>", "<p>Download the bundle for laptops.</p>"])
               + "<h2>Second step</h2>"
               + mkdocs_set(2, ("Linux", "macOS"), ["<p>Run the service with systemd.</p>", "<p>Run the service with launchd.</p>"]),
               "Repeated labels")
ARIA_REORDERED = doc(
    '<div role="tablist"><button role="tab" id="t-linux" aria-controls="p-linux">Linux</button>'
    '<button role="tab" id="t-mac" aria-controls="p-mac">macOS</button></div>'
    '<div role="tabpanel" id="p-mac" aria-labelledby="t-mac" hidden><p>Panel for the Mac install.</p></div>'
    '<div role="tabpanel" id="p-linux" aria-labelledby="t-linux"><p>Panel for the Linux install.</p></div>', "Reordered panels")
ORDERED = doc(mkdocs_set(3, ("Install", "Upgrade"), [
    "<ol><li>Download the release archive.</li><li>Unpack it beside the old one.</li></ol>",
    "<ol><li>Stop the running service.</li><li>Replace the binary in place.</li></ol>"]), "Ordered panels")
ARIA_AMBIGUOUS = doc(
    '<div role="tablist"><button role="tab">Linux</button><button role="tab">macOS</button></div>'
    '<div role="tabpanel"><p>First panel text.</p></div><div role="tabpanel" hidden><p>Second panel text.</p></div>',
    "Unlinked tabs")
# A limits page whose third panel opens with its own notice: the panel's table does not follow the label
# directly, and the notice belongs under that label, not the one before it.
LIMIT_NOTICE_TITLE = "Limits under review"
LIMIT_NOTICE_TEXT = "These limits have been relaxed for the moment while they are reviewed."
LIMIT_NOTICE = '<div class="admonition info"><p class="admonition-title">%s</p><p>%s</p></div>' % (LIMIT_NOTICE_TITLE, LIMIT_NOTICE_TEXT)
PARTITION_ROWS = (("workq", "38", "24 hours"), ("workr", "1320", "24 hours"), ("grace", "384", "24 hours"), ("milan", "12", "24 hours"))
NOTICED_URL = "https://docs.example.org/user-documentation/jobs/noticed/"
NOTICED = doc("<h2>Job limits</h2>" + mkdocs_set(1, LIMIT_LABELS, [
    limits_table(LIMIT_ROWS[0]), limits_table(LIMIT_ROWS[1]) + "<p>All of the limits above apply per user.</p>",
    LIMIT_NOTICE + limits_table(LIMIT_ROWS[2]), limits_table(LIMIT_ROWS[3])])
    + "<h2>Partition configuration</h2>" + mkdocs_set(2, LIMIT_LABELS, [limits_table(r) for r in PARTITION_ROWS]), "Job scheduling")
# A Webflow FAQ: each answer in a dropdown panel written as a nav element, with the site's own menu, in the same
# dropdown markup, inside a navbar above it.
WEBFLOW_MENU = ('<div class="navigation w-nav"><nav class="nav-menu w-nav-menu"><div class="dropdown-wrapper w-dropdown">'
                '<div class="w-dropdown-toggle">Programmes</div><nav class="nav-dropdown-row w-dropdown-list">'
                '<a href="/programmes/residency">Residency</a><a href="/programmes/fellowship">Fellowship</a></nav></div></nav></div>')
FAQ_PAIRS = (("Who can apply to the programme?", "Anyone with two years of research experience may apply."),
             ("Do I need a doctorate?", "No. A track record counts for more than a title."),
             ("Can I take part from abroad?", "Remote places are offered where the supervisor agrees."))


def webflow_page(body, title):
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>%s</title></head><body>%s<main><article>'
            '<h1>%s</h1>%s%s</article></main></body></html>' % (title, WEBFLOW_MENU, title, LEAD, body))


def webflow_item(question, answer):
    return ('<div data-hover="false" data-delay="0" class="faq-dropdown w-dropdown"><div class="faq-dropdown-toggle w-dropdown-toggle">'
            '<div class="faq-question">%s</div><div class="faq-dropdown-arrow"><div class="icon-xs w-embed"><svg viewBox="0 0 24 24">'
            '<path d="M9.5 17L14.5 12L9.5 7"/></svg></div></div></div><nav class="faq-dropdown-list w-dropdown-list">'
            '<div class="w-richtext"><p>%s</p></div></nav></div>' % (question, answer))


FAQ_URL = "https://www.example.org/residency/faq"
FAQ = webflow_page("<h2>Getting started</h2>" + "".join(webflow_item(q, a) for q, a in FAQ_PAIRS), "Frequently asked questions")
WEBFLOW_ARTICLE_URL = "https://www.example.org/news/plain"
WEBFLOW_ARTICLE = webflow_page("<p>Ordinary article prose under a site menu, long enough to read as an article body for the "
                               "extractor, with nothing collapsed anywhere in the page's own content.</p>"
                               "<p>A second paragraph keeps the extractor content.</p>", "Plain article on a Webflow site")
PLAIN_URL = "https://news.example.org/2026/10/plain-article"
PLAIN = doc('<p>Ordinary article prose that a reader sees on first load, long enough to read as an article body '
            'for the extractor, with nothing collapsed and nothing tabbed anywhere on the page.</p>'
            '<p>A second paragraph keeps the extractor content and links to the <a href="/about/">about page</a>.</p>'
            '<button aria-controls="results">Sort</button><div id="results"><p>Visible results stay visible.</p></div>',
            "Plain article")
FAMILIES = [
    ("details", '<details><summary>More</summary><p>Collapsed family text one.</p></details>', {"details"}),
    ("hidden attribute", '<div hidden><p>Collapsed family text two.</p></div>', {"hidden attribute"}),
    ("aria-hidden", '<div aria-hidden="true"><p>Collapsed family text three.</p></div>', {"aria-hidden"}),
    ("inline display:none", '<div style="color: red; display : none"><p>Collapsed family text four.</p></div>', {"inline display:none"}),
    ("inline visibility:hidden", '<div style="visibility:hidden"><p>Collapsed family text five.</p></div>', {"inline visibility:hidden"}),
    ("class collapse", '<div class="panel collapse"><p>Collapsed family text six.</p></div>', {"class collapse"}),
    ("class accordion*", '<div class="accordion-body"><p>Collapsed family text seven.</p></div>', {"class accordion*"}),
    ("tab roles", '<div role="tablist"><button role="tab" id="ft1" aria-controls="fp1">First tab</button></div>'
                  '<div role="tabpanel" id="fp1" aria-labelledby="ft1"><p>Collapsed family text eight.</p></div>',
     {"role tablist", "role tabpanel", "controlled collapsed or tabbed target"}),
    ("mkdocs set", mkdocs_set(1, ("Only tab",), ["<p>Collapsed family text nine.</p>"]),
     {"mkdocs tabbed-set", "mkdocs tabbed-content", "mkdocs tabbed-block"}),
    ("controlled collapsed target", '<button aria-expanded="false" aria-controls="fq1">A question?</button>'
                                    '<div id="fq1"><p>Collapsed family text ten.</p></div>', {"controlled collapsed or tabbed target"}),
    ("class w-dropdown-list", '<div class="w-dropdown"><div class="w-dropdown-toggle">A question?</div>'
                              '<nav class="w-dropdown-list"><p>Collapsed family text eleven.</p></nav></div>', {"class w-dropdown-list"}),
]
ERROR_BODY = doc("<p>" + "This page could not be found on the server, please check the address and try again. " * 30 + "</p>", "Not found")

SPEC_N = [0]


def spec(*responses):
    SPEC_N[0] += 1
    path = os.path.join(T, "spec-%d.json" % SPEC_N[0])
    put(path, json.dumps({"responses": list(responses)}))
    return path


def capture(url, spec_path, *extra, script=CP):
    SPEC_N[0] += 1
    work = os.path.join(T, "work-%d" % SPEC_N[0])
    env = dict(os.environ, STUB_CURL_SPEC=spec_path)
    proc = subprocess.run([PY, "-B", script, "capture", url, "--work", work, "--curl", CURL, "--python", MD_PY] + list(extra),
                          capture_output=True, text=True, env=env)
    res_path = os.path.join(work, "result.json")
    result = json.loads(read(res_path)) if os.path.isfile(res_path) else None
    return proc, work, result


def calls(spec_path):
    path = spec_path + ".calls"
    return int(read(path)) if os.path.isfile(path) else 0


def write_cw(url, engine, body, *extra):
    return subprocess.run([PY, "-B", CW, "write", "--vault-root", VAULT, "--url", url, "--engine", engine,
                           "--ledger-id", RID] + list(extra), input=body, capture_output=True, text=True, cwd=HERE)


STAMPS = []      # every stamp this suite sees on either save path, for the leg that none reads as verified


def stamp_cmd(result_path, body_path, url, *extra, engine="jina-reader"):
    """ingest Step 0's save step: `stamp` with the engine that produced the body (engine=None omits it)."""
    argv = [PY, "-B", CP, "stamp", result_path, "--body", body_path, "--url", url]
    argv += (["--engine", engine] if engine is not None else []) + list(extra)
    r = subprocess.run(argv, capture_output=True, text=True)
    STAMPS.extend(re.findall(r'(?m)^capture_check: "(.*)"$', r.stdout))
    return r


def stamp_printed(r):
    m = re.search(r'(?m)^capture_check: "(.*)"$', r.stdout)
    return m.group(1) if m else ""


def raw_text(slug):
    path = os.path.join(VAULT, "raw", slug + ".md")
    return read(path) if os.path.isfile(path) else ""


def raw_stamp(slug):
    """The capture_check value a raw capture's frontmatter carries ('' when it has none)."""
    text = raw_text(slug)
    front = text.split("\n---\n", 1)[0] if text.startswith("---\n") else ""
    m = re.search(r'(?m)^capture_check: "(.*)"$', front)
    if m:
        STAMPS.append(m.group(1))
    return m.group(1) if m else ""


def last_capture():
    return rl.load(rl.path_for(RID))["captures"][-1]


NO_LOSS, LOSS, NOT_RUN = "no loss found by the unit check (", "suspected loss — ", "not run — "
PROVENANCE_LINE = re.compile(r"(?m)^(?:converted_from|converted_by|capture_check|capture_quality):")


EXERCISED = {"markitdown": 0, "defuddle": 0}


def count_conversion(result):
    if result and result.get("converter"):
        argv = result["converter"]
        EXERCISED["markitdown" if "markitdown" in argv else "defuddle"] += 1


STATE = {}

# ================================================================ acquisition cannot become a successful probe
print("== acquisition: only a successful HTML response reaches routing ==")
ERR_PAGE = put(os.path.join(T, "error-page.html"), ERROR_BODY)
for code in ("404", "500"):
    leg(f"route: a substantial {code} body given through --http is PROBE FAILED (exit 2)",
        lambda code=code: (lambda r: (r.returncode == 2 and f"PROBE FAILED: fetch: HTTP {code}" in r.stdout, r.stdout + r.stderr))(
            subprocess.run([PY, "-B", CP, "route", ERR_PAGE, "--http", f"{code} text/html; charset=utf-8", "--curl-exit", "0"],
                           capture_output=True, text=True)))


def _capture_404():
    proc, work, res = capture("https://www.example.org/gone", spec({"body": ERROR_BODY, "code": 404}))
    return proc.returncode == 2 and res and res["status"] == "fail" and "HTTP 404" in res["reason"], proc.stdout


leg("capture: a substantial 404 response is PROBE FAILED, its result status fail", _capture_404)


def _curl_failed_under_200():
    proc, work, res = capture(FUNDING_URL, spec({"body": FUNDING[:900], "code": 200, "exit": 18,
                                                 "stderr": "curl: (18) transfer closed with outstanding read data remaining"}))
    STATE["curl18"] = os.path.join(work, "result.json")
    return (proc.returncode == 2 and res and res["status"] == "fail" and res["fetch"]["curl_exit"] == 18
            and "curl exit 18 under HTTP 200" in res["reason"]), proc.stdout


leg("capture: curl failing after a 200 header (exit 18, truncated body) is PROBE FAILED, exit status recorded", _curl_failed_under_200)
EMPTY = put(os.path.join(T, "empty.html"), "")
leg("route: an empty page is PROBE FAILED",
    lambda: (lambda r: (r.returncode == 2 and "PROBE FAILED" in r.stdout and "missing or empty" in r.stdout, r.stdout))(
        subprocess.run([PY, "-B", CP, "route", EMPTY, "--http", "200 text/html", "--curl-exit", "0"], capture_output=True, text=True)))
PDFISH = put(os.path.join(T, "paper.html"), "%PDF-1.7 binary-looking body " * 40)
leg("route: a non-HTML content type is PROBE FAILED",
    lambda: (lambda r: (r.returncode == 2 and "is not HTML" in r.stdout, r.stdout))(
        subprocess.run([PY, "-B", CP, "route", PDFISH, "--http", "200 application/pdf", "--curl-exit", "0"], capture_output=True, text=True)))
leg("capture: a non-HTML response is PROBE FAILED",
    lambda: (lambda c: (c[0].returncode == 2 and c[2] and "is not HTML" in c[2]["reason"], c[0].stdout))(
        capture("https://www.example.org/paper.pdf", spec({"body": "%PDF-1.7 " * 100, "type": "application/pdf"}))))
leg("route: a run that omits curl's exit status is refused (exit 2), so the status never travels without it",
    lambda: (lambda r: (r.returncode == 2 and "--curl-exit" in r.stderr, r.stderr))(
        subprocess.run([PY, "-B", CP, "route", ERR_PAGE, "--http", "200 text/html"], capture_output=True, text=True)))


def _sabotaged():
    src = read(CP)
    anchor = "<details><summary>Control terms</summary>"
    sab = put(os.path.join(T, "sabotaged", "capture_probe.py"), src.replace(anchor, "<section><p>Control terms</p>", 1))
    r = subprocess.run([PY, "-B", sab, "route", ERR_PAGE, "--http", "200 text/html", "--curl-exit", "0"], capture_output=True, text=True)
    proc, work, res = capture(FUNDING_URL, spec({"body": FUNDING}), script=sab)
    STATE["controls"] = os.path.join(work, "result.json")
    return (src.count(anchor) == 1 and r.returncode == 2 and "PROBE FAILED: controls" in r.stdout
            and proc.returncode == 2 and res and res["stage"] == "controls"), r.stdout + proc.stdout


leg("a sabotaged built-in control (the planted details block removed) stops route and capture (exit 2)", _sabotaged)
FAQ_PAGE = put(os.path.join(T, "faq-page.html"), FAQ)


def _sabotaged_dropdown(folder, anchor, replacement):
    """A probe that has lost the marker must stop before it fetches, or a FAQ goes quietly back to the extractor."""
    src = read(CP)
    sab = put(os.path.join(T, folder, "capture_probe.py"), src.replace(anchor, replacement, 1))
    r = subprocess.run([PY, "-B", sab, "route", FAQ_PAGE, "--http", "200 text/html", "--curl-exit", "0"], capture_output=True, text=True)
    sp = spec({"body": FAQ})
    proc, work, res = capture(FAQ_URL, sp, script=sab)
    return (src.count(anchor) == 1 and r.returncode == 2 and "PROBE FAILED: controls" in r.stdout and proc.returncode == 2
            and res and res["stage"] == "controls" and calls(sp) == 0
            and not os.path.exists(os.path.join(work, "capture.md"))), r.stdout + proc.stdout


for title, folder, anchor, replacement in (
        ("the dropdown marker removed", "sabotaged-marker", 'found.append("class w-dropdown-list")', "pass"),
        ("the navbar exclusion removed", "sabotaged-navbar", ' and not any("w-nav" in tokens(a, "class") for a in ancestors(node))', ""),
        ("the planted dropdown removed from its control page", "sabotaged-dropdown-control",
         '<nav class="w-dropdown-list"><p>Planted dropdown control answer.</p></nav>', "<p>Planted dropdown control answer.</p>")):
    leg(f"fails closed: a probe with {title} stops route and capture at its controls (exit 2): nothing fetched, no capture",
        lambda folder=folder, anchor=anchor, replacement=replacement: _sabotaged_dropdown(folder, anchor, replacement))


def _one_representation():
    hidden = doc('<div hidden><p>Text served only on a second request.</p></div>', "Changing page")
    sp = spec({"body": PLAIN, "code": 200}, {"body": hidden, "code": 200}, {"body": ERROR_BODY, "code": 500})
    proc, work, res = capture(PLAIN_URL, sp)
    count_conversion(res)
    STATE["plain"] = (work, res)
    page_sha = sha(os.path.join(work, "page.html")) if res else ""
    argv = (res or {}).get("converter") or []
    ok = (proc.returncode == 0 and calls(sp) == 1 and res["route"] == "NOT-ROUTED"
          and res["html_sha256"] == page_sha == hashlib.sha256(PLAIN.encode()).hexdigest()
          and os.path.join(work, "converted.html") in argv and not any(a.startswith("http") for a in argv)
          and "second request" not in read(os.path.join(work, "capture.md")))
    return ok, f"calls {calls(sp)} · {proc.stdout}"


leg("one fetch: a page answering plain first and hidden-panel or 500 later is routed and converted from the first "
    "response only (one curl call; defuddle read the fetched copy, never the URL)", _one_representation)

# ================================================================ structural routing covers the named families
print("== routing: each named family routes on its own, the plain article does not ==")
for name, body, expected in FAMILIES:
    def _family(name=name, body=body, expected=expected):
        page = put(os.path.join(T, "family-%s.html" % re.sub(r"\W+", "-", name)), doc(body))
        r = subprocess.run([PY, "-B", CP, "route", page, "--http", "200 text/html", "--curl-exit", "0"], capture_output=True, text=True)
        cp = cp_module()
        markers = set(cp.find_markers(cp.parse_html(doc(body))))
        proc, work, res = capture("https://www.example.org/family/" + re.sub(r"\W+", "-", name), spec({"body": doc(body)}))
        count_conversion(res)
        text = re.search(r"Collapsed family text \w+\.", body).group(0)
        md = read(os.path.join(work, "capture.md")) if res and res.get("capture_file") else ""
        return (r.returncode == 1 and "route: ROUTE" in r.stdout and markers == expected and proc.returncode == 0
                and res["route"] == "ROUTE" and res["engine"] == cp.ROUTE_ENGINE and text in md), f"{markers} · {r.stdout} {proc.stdout}"
    leg(f"family {name}: ROUTE naming exactly its own markers, and the routed capture keeps the text", _family)


def _funding():
    proc, work, res = capture(FUNDING_URL, spec({"body": FUNDING}))
    count_conversion(res)
    STATE["funding"] = (work, res)
    md = read(os.path.join(work, "capture.md")) if res and res.get("capture_file") else ""
    named = set((res or {}).get("markers") or {})
    return (proc.returncode == 0 and res["status"] == "pass" and {"details", "hidden attribute", "aria-hidden"} <= named
            and all(t in md for t in FUNDING_TERMS) and res["check"]["collapsed"] >= 6), proc.stdout


leg("funding-page shape: details, hidden and aria-hidden panels ROUTE, each marker named; the capture keeps every "
    "eligibility, deadline and visa term, the four-word sentence included; check passes", _funding)


def _plain_not_routed():
    work, res = STATE["plain"]
    r = subprocess.run([PY, "-B", CP, "route", os.path.join(work, "page.html"), "--http", "200 text/html", "--curl-exit", "0"],
                       capture_output=True, text=True)
    return (r.returncode == 0 and "route: NOT-ROUTED" in r.stdout and res["status"] == "pass"
            and res["engine"] == cp_module().PLAIN_ENGINE), r.stdout


leg("a plain article with a sort button over visible results stays NOT-ROUTED (the narrowed aria-controls marker) "
    "and passes through defuddle", _plain_not_routed)


def _webflow_faq():
    proc, work, res = capture(FAQ_URL, spec({"body": FAQ}))
    count_conversion(res)
    STATE["faq"] = (work, res)
    md = read(os.path.join(work, "capture.md"))
    placed = [q for q, a in FAQ_PAIRS if re.search(re.escape(q) + r"\s+" + re.escape(a), md)]
    return (proc.returncode == 0 and res["route"] == "ROUTE" and res["engine"] == cp_module().ROUTE_ENGINE
            and res["markers"] == {"class w-dropdown-list": len(FAQ_PAIRS)} and res["check"]["collapsed"] == len(FAQ_PAIRS)
            and res["check"]["verdict"] == "no loss found" and len(placed) == len(FAQ_PAIRS)), f"{placed} · {proc.stdout}"


leg("Webflow FAQ shape: answers in dropdown panels ROUTE, the navbar's menu not counted; each answer follows its own "
    "question in the capture; the check counts every answer as collapsed and finds no loss", _webflow_faq)


def _webflow_menu_alone():
    proc, work, res = capture(WEBFLOW_ARTICLE_URL, spec({"body": WEBFLOW_ARTICLE}))
    count_conversion(res)
    page = put(os.path.join(T, "webflow-article.html"), WEBFLOW_ARTICLE)
    r = subprocess.run([PY, "-B", CP, "route", page, "--http", "200 text/html", "--curl-exit", "0"], capture_output=True, text=True)
    return (proc.returncode == 0 and res["route"] == "NOT-ROUTED" and res["engine"] == cp_module().PLAIN_ENGINE
            and r.returncode == 0 and "route: NOT-ROUTED" in r.stdout), r.stdout + proc.stdout


leg("control: a Webflow article whose only dropdown is the site's menu in a navbar stays NOT-ROUTED and passes through defuddle",
    _webflow_menu_alone)

# ================================================================ validation establishes fidelity to the original
print("== validation: fidelity to the fetched original ==")


def run_check(page_text, markdown, base="https://docs.example.org/x/"):
    SPEC_N[0] += 1
    page = put(os.path.join(T, "chk-%d.html" % SPEC_N[0]), page_text)
    md = put(os.path.join(T, "chk-%d.md" % SPEC_N[0]), markdown)
    return subprocess.run([PY, "-B", CP, "check", page, md, "--base-url", base], capture_output=True, text=True)


def _webflow_answers_lost():
    work, _res = STATE["faq"]
    md = read(os.path.join(work, "capture.md"))
    lost = md
    for _q, answer in FAQ_PAIRS:
        lost = lost.replace(answer, "")
    r = run_check(FAQ, lost, FAQ_URL)
    body = put(os.path.join(T, "faq-lost.md"), lost)
    s = stamp_cmd(os.path.join(work, "result.json"), body, FAQ_URL, engine=cp_module().PLAIN_ENGINE)
    stamp = stamp_printed(s)
    return (lost != md and r.returncode == 1 and "collapsed text missing" in r.stdout and FAQ_PAIRS[0][1] in r.stdout
            and s.returncode == 0 and stamp.startswith(LOSS) and FAQ_PAIRS[0][1] in stamp), r.stdout + stamp


leg("Webflow FAQ shape: the extractor's body, questions kept and every answer gone, gives the check a finding naming an "
    "answer, and stamp prints suspected loss (it warns, exit 0)", _webflow_answers_lost)


def _limits():
    proc, work, res = capture(LIMITS_URL, spec({"body": LIMITS}))
    count_conversion(res)
    STATE["limits"] = (work, res)
    md = read(os.path.join(work, "capture.md"))
    order = [md.find("#### " + lab) for lab in LIMIT_LABELS]
    tables = [md.find("| %s | %s |" % (r[0], r[1])) for r in LIMIT_ROWS]
    adjacent = all(order[i] < tables[i] and (i == 3 or tables[i] < order[i + 1]) for i in range(4))
    return (proc.returncode == 0 and res["check"]["labels"] == 4 and res["pairing"] == {"mkdocs-order": 1}
            and -1 not in order and -1 not in tables and adjacent), proc.stdout + md[:400]


leg("limits-page shape: four labelled tables sharing one header ROUTE; each label directly precedes its own table", _limits)


def _sabotage_md(transform):
    work, res = STATE["limits"]
    md = read(os.path.join(work, "capture.md"))
    return run_check(LIMITS, transform(md), LIMITS_URL), md


def _swap(md):
    a, b = "| gpu | 256 | 24 hours |", "| gpu | 1024 | 24 hours |"
    return md.replace(a, "\x00").replace(b, a).replace("\x00", b)


def _detach(md):
    for lab in LIMIT_LABELS:
        md = md.replace("#### " + lab + "\n", "")
    return md.replace("## Job limits", "## Job limits\n\n" + " ".join(LIMIT_LABELS), 1)


for title, fn, needle in (("two tables swapped under their labels", _swap, "tab label"),
                          ("labels detached from their tables (all labels on one line above them)", _detach, "tab label"),
                          ("one table value deleted while every label and header survives",
                           lambda md: md.replace("| 1024 |", "|  |"), "panel content missing")):
    leg(f"Markdown sabotage: {title} gives the check a finding (suspected loss, exit 1: it warns)",
        lambda fn=fn, needle=needle: (lambda rm: (rm[0].returncode == 1 and needle in rm[0].stdout
                                                  and "check: suspected loss — " in rm[0].stdout, rm[0].stdout))(_sabotage_md(fn)))


def _visa_dropped():
    work, res = STATE["funding"]
    md = read(os.path.join(work, "capture.md"))
    r = run_check(FUNDING, md.replace(VISA, ""), FUNDING_URL)
    return (VISA in md and r.returncode == 1 and "check: suspected loss — " in r.stdout
            and "collapsed text missing" in r.stdout and VISA in r.stdout), r.stdout


leg("Markdown sabotage: the funding capture without the four-word visa sentence gives the check a finding, the "
    "sentence named (no length exemption; suspected loss, exit 1)", _visa_dropped)


def _noticed():
    proc, work, res = capture(NOTICED_URL, spec({"body": NOTICED}))
    count_conversion(res)
    STATE["noticed"] = work
    md = read(os.path.join(work, "capture.md"))
    sections = [(h, b) for h, b in re.findall(r"(?ms)^#### (.+?)\n(.*?)(?=^#{1,6} |\Z)", md) if h in LIMIT_LABELS]
    rows = LIMIT_ROWS + PARTITION_ROWS
    owned = [h for (h, body), row in zip(sections, rows) if "| %s | %s |" % row[:2] in body]
    third = sections[2][1] if len(sections) > 2 else ""
    return (proc.returncode == 0 and res["check"]["verdict"] == "no loss found" and res["check"]["labels"] == 8
            and [h for h, _b in sections] == list(LIMIT_LABELS) * 2 and len(owned) == 8
            and 0 <= third.find(LIMIT_NOTICE_TITLE) < third.find("| grace | 128 |")), f"{owned} · {proc.stdout}"


leg("control: a tab panel opening with its own notice: all eight labels keep their own tables under their headings, and "
    "the label stays above the notice, which stays above its table; no loss found", _noticed)


def _notice_label_moved():
    md = read(os.path.join(STATE["noticed"], "capture.md"))
    notice = "%s\n\n%s\n\n" % (LIMIT_NOTICE_TITLE, LIMIT_NOTICE_TEXT)
    label = "#### %s\n\n" % LIMIT_LABELS[2]
    moved = md.replace(label + notice, notice + label, 1)
    r = run_check(NOTICED, moved, NOTICED_URL)
    return (moved != md and r.returncode == 1 and "tab label" in r.stdout
            and "check: suspected loss — " in r.stdout), r.stdout


leg("control: that label moved past the notice, directly before the table, gives the check a finding: the notice would "
    "read under the previous tab's label (suspected loss, exit 1)", _notice_label_moved)


def _faulty_normaliser(kind):
    cp = cp_module()

    def faulty(root, sets, base):
        if kind == "delete":
            for node in list(cp.iter_elements(root)):
                if node.tag == "p" and VISA in cp.text_of(node):
                    node.parent.children.remove(node)
        else:
            for s in sets:
                labels = [t for t, _, _ in s.pairs][::-1]
                s.pairs = [(labels[i], p, lab) for i, (_t, p, lab) in enumerate(s.pairs)]
        return cp.normalise(root, sets, base)
    SPEC_N[0] += 1
    work = os.path.join(T, "faulty-%s" % kind)
    os.environ["STUB_CURL_SPEC"] = spec({"body": FUNDING if kind == "delete" else LIMITS})
    try:
        code, res = cp.run_capture(FUNDING_URL if kind == "delete" else LIMITS_URL, work, curl=CURL, defuddle=DEFUDDLE,
                                   python=MD_PY, normaliser=faulty)
    finally:
        os.environ.pop("STUB_CURL_SPEC", None)
    count_conversion(res)
    return code, res, work


def _delete_sentence():
    code, res, work = _faulty_normaliser("delete")
    STATE["check_failed"] = os.path.join(work, "result.json")
    converted, md = read(os.path.join(work, "converted.html")), read(os.path.join(work, "capture.md"))
    found = "; ".join((res.get("check") or {}).get("failures") or [])
    return (code == 0 and res["status"] == "pass" and res["check"]["verdict"] == "suspected loss" and VISA in found
            and VISA not in converted and VISA not in md and "Applicants must be enrolled" in md), res.get("check")


leg("normaliser sabotage: a normaliser deleting the visa sentence is caught although its Markdown matches its "
    "normalised HTML (the sentence is absent from both): the capture is made, its check suspected loss naming it", _delete_sentence)


def _reverse_labels():
    code, res, work = _faulty_normaliser("reverse")
    md = read(os.path.join(work, "capture.md"))
    found = "; ".join((res.get("check") or {}).get("failures") or [])
    return (code == 0 and res["check"]["verdict"] == "suspected loss" and ("tab label" in found or "under tab" in found)
            and md.find("#### Beta MACS") < md.find("| gpu | 256 |")), res.get("check")


leg("normaliser sabotage: a normaliser reversing label-panel associations is caught: suspected loss, the capture made",
    _reverse_labels)
for title, page_text, url in (("nested tabbed sets", NESTED, "https://docs.example.org/install/nested/"),
                              ("repeated labels across two sets", REPEATED, "https://docs.example.org/install/repeated/"),
                              ("panels opening with ordered lists (the converter's list numbers between label and panel)",
                               ORDERED, "https://docs.example.org/install/ordered/"),
                              ("ARIA panels in another order than their tabs, paired by ids",
                               ARIA_REORDERED, "https://docs.example.org/install/aria/")):
    def _pass(page_text=page_text, url=url):
        proc, work, res = capture(url, spec({"body": page_text}))
        count_conversion(res)
        STATE[url] = work
        return proc.returncode == 0 and res["status"] == "pass" and res["check"]["labels"] >= 2, proc.stdout
    leg(f"correct transformation passes: {title}", _pass)


def _aria_order_pairing():
    md = read(os.path.join(STATE["https://docs.example.org/install/aria/"], "capture.md"))
    naive = md.replace("#### macOS", "\x00").replace("#### Linux", "#### macOS").replace("\x00", "#### Linux")
    r = run_check(ARIA_REORDERED, naive)
    return (md.find("#### macOS") < md.find("Mac install") and r.returncode == 1 and "tab label" in r.stdout
            and "check: suspected loss — " in r.stdout), r.stdout


leg("pairing ARIA tabs by order instead of ids (labels swapped onto the reordered panels) gives the check a finding "
    "(suspected loss, exit 1)", _aria_order_pairing)


def _ambiguous():
    proc, work, res = capture("https://docs.example.org/install/unlinked/", spec({"body": ARIA_AMBIGUOUS}))
    r = run_check(ARIA_AMBIGUOUS, "# Unlinked tabs\n\n#### Linux\n\nFirst panel text.\n\n#### macOS\n\nSecond panel text.\n")
    return (proc.returncode == 2 and res["stage"] == "normalise" and "ambiguous tab pairing" in res["reason"]
            and r.returncode == 2 and "ambiguous tab pairing" in r.stdout), proc.stdout + r.stdout


leg("ambiguous pairing (tabs and panels with no id link) fails closed at normalise and at check", _ambiguous)

# ================================================================ both save paths record the stamp, and refuse nothing for it
print("== both save paths: gather's writer and ingest's stamp record what the check found, and refuse no write for it ==")


def _converter_failed():
    proc, work, res = capture(PLAIN_URL + "-converter", spec({"body": PLAIN}), "--defuddle", FAILING_DEFUDDLE)
    STATE["converter"] = os.path.join(work, "result.json")
    return proc.returncode == 2 and res["stage"] == "convert" and "defuddle exited 1" in res["reason"], proc.stdout


leg("a converter that fails is PROBE FAILED at convert", _converter_failed)


def _unexpected():
    cp = cp_module()

    def broken(root, sets, base):
        raise RuntimeError("planted surprise")
    os.environ["STUB_CURL_SPEC"] = spec({"body": FUNDING})
    try:
        code, res = cp.run_capture(FUNDING_URL, os.path.join(T, "unexpected"), curl=CURL, defuddle=DEFUDDLE,
                                   python=MD_PY, normaliser=broken)
    finally:
        os.environ.pop("STUB_CURL_SPEC", None)
    STATE["unexpected"] = os.path.join(T, "unexpected", "result.json")
    return code == 2 and res["stage"] == "internal" and "planted surprise" in res["reason"], res.get("reason")


leg("an unexpected exception inside the chain is PROBE FAILED (stage internal), never a pass", _unexpected)
ROUTE_ENGINE = "curl+markitdown (structural route)"
BODY_DIR = os.path.join(T, "bodies")


def funding_body():
    return read(os.path.join(STATE["funding"][0], "capture.md"))


def funding_result():
    return os.path.join(STATE["funding"][0], "result.json")


def funding_capture():
    return os.path.join(STATE["funding"][0], "capture.md")


def _warn_gather():
    r = write_cw(FUNDING_URL, ROUTE_ENGINE, funding_body().replace(VISA, ""), "--slug", "warn-lost-visa",
                 "--probe-result", funding_result())
    stamp, led = raw_stamp("warn-lost-visa"), last_capture().get("capture_check", "")
    return (r.returncode == 0 and "capture check: suspected loss" in r.stdout and stamp.startswith(LOSS)
            and "collapsed text missing" in stamp and VISA in stamp and led == stamp), r.stdout + r.stderr + stamp


leg("must warn, gather: a capture missing a collapsed section (the four-word visa sentence) is written, stamped suspected "
    "loss naming the sentence, in frontmatter and ledger alike", _warn_gather)


def _warn_ingest():
    body = put(os.path.join(BODY_DIR, "lost-visa.md"), funding_body().replace(VISA, ""))
    r = stamp_cmd(funding_result(), body, FUNDING_URL, engine=ROUTE_ENGINE)
    s = stamp_printed(r)
    return (r.returncode == 0 and s.startswith(LOSS) and VISA in s and r.stdout.startswith("check: suspected loss — ")
            and f'"capture_check": "{s}"' in r.stdout), r.stdout


leg("must warn, ingest: stamp prints that suspected-loss stamp for the same body, and the checkpoint value (exit 0)",
    _warn_ingest)


def _warn_recorded_finding():
    path = STATE["check_failed"]
    body = read(os.path.join(os.path.dirname(path), "capture.md"))
    r = write_cw(FUNDING_URL, ROUTE_ENGINE, body, "--slug", "probe-found-loss", "--probe-result", path)
    stamp = raw_stamp("probe-found-loss")
    return r.returncode == 0 and stamp.startswith(LOSS) and VISA in stamp, r.stdout + r.stderr + stamp


leg("must warn: the faulty normaliser's own capture, whose result records the loss, is written and stamped suspected "
    "loss (a result recording a finding is well formed, never refused)", _warn_recorded_finding)


def _no_warn_gather():
    r = write_cw(FUNDING_URL, ROUTE_ENGINE, funding_body(), "--slug", "no-warn-funding", "--probe-result", funding_result())
    stamp = raw_stamp("no-warn-funding")
    return (r.returncode == 0 and "capture check: no loss found" in r.stdout and stamp.startswith(NO_LOSS)
            and "suspected loss" not in stamp and "not compared:" in stamp and "literal punctuation" in stamp
            and "empty-cell positions in tables" in stamp and "capture_quality" not in raw_text("no-warn-funding")
            and last_capture().get("capture_check") == stamp), r.stdout + stamp


leg("must not warn, gather: the faithful funding capture is stamped no loss found by the unit check, naming what the "
    "check does not compare (literal punctuation, empty-cell positions in tables), with no capture_quality", _no_warn_gather)


def _no_warn_ingest():
    r = stamp_cmd(funding_result(), funding_capture(), FUNDING_URL, engine=ROUTE_ENGINE)
    s = stamp_printed(r)
    return (r.returncode == 0 and s.startswith(NO_LOSS) and "literal punctuation" in s and "capture_quality" not in r.stdout
            and "body: the probe's own capture" in r.stdout), r.stdout


leg("must not warn, ingest: stamp prints no loss found for the probe's own capture, and no capture_quality line (exit 0)",
    _no_warn_ingest)
PLANT = "Founder Grants"     # in the funding page only: the planted check raises there, and never on a control page
PLANTED_CHECK = ("_planted_check = check_capture\n\n\ndef check_capture(page_text, base_url, markdown):\n"
                 "    if " + repr(PLANT) + " in page_text:\n        raise RuntimeError(\"planted check failure\")\n"
                 "    return _planted_check(page_text, base_url, markdown)\n\n\n")


def broken_check_dir():
    """A copy of the gather scripts whose check raises on the funding page alone, so its built-in controls pass."""
    d = os.path.join(T, "broken-check")
    if not os.path.isdir(d):
        src = read(CP)
        anchor = 'if __name__ == "__main__":\n'
        if src.count(anchor) != 1:
            raise RuntimeError(f"premise: the main guard occurs {src.count(anchor)} times in capture_probe.py")
        put(os.path.join(d, "capture_probe.py"), src.replace(anchor, PLANTED_CHECK + anchor, 1))
        for f in ("capture_write.py", "run_ledger.py"):
            shutil.copy(os.path.join(HERE, f), os.path.join(d, f))
    return d


def _not_run_probe():
    d = broken_check_dir()
    proc, work, res = capture(FUNDING_URL, spec({"body": FUNDING}), script=os.path.join(d, "capture_probe.py"))
    count_conversion(res)
    STATE["broken_check"] = (work, res)
    m = re.search(r"(?m)^check: (.*)$", proc.stdout)
    printed = m.group(1) if m else ""
    if printed:
        STAMPS.append(printed)
    return (proc.returncode == 0 and res["status"] == "pass" and res["check"]["verdict"] == "not run"
            and "planted check failure" in res["check"]["reason"] and printed.startswith(NOT_RUN)
            and "planted check failure" in printed and os.path.isfile(os.path.join(work, "capture.md"))), proc.stdout


leg("must say not run, the probe: a check that fails to run leaves the capture made (exit 0), its verdict not run with "
    "the reason, never no loss", _not_run_probe)


def _not_run_writer():
    d = broken_check_dir()
    work, _res = STATE["broken_check"]
    r = subprocess.run([PY, "-B", os.path.join(d, "capture_write.py"), "write", "--vault-root", VAULT, "--url", FUNDING_URL,
                        "--engine", ROUTE_ENGINE, "--ledger-id", RID, "--slug", "broken-check",
                        "--probe-result", os.path.join(work, "result.json")],
                       input=read(os.path.join(work, "capture.md")), capture_output=True, text=True, cwd=d)
    stamp = raw_stamp("broken-check")
    return (r.returncode == 0 and stamp.startswith(NOT_RUN) and "planted check failure" in stamp
            and last_capture().get("capture_check") == stamp), r.stdout + r.stderr + stamp


leg("must say not run, gather: with that probe beside the writer, the capture is written and stamped not run, the "
    "check's failure named, in frontmatter and ledger", _not_run_writer)


def _not_run_ingest():
    d = broken_check_dir()
    work, _res = STATE["broken_check"]
    r = subprocess.run([PY, "-B", os.path.join(d, "capture_probe.py"), "stamp", os.path.join(work, "result.json"),
                        "--body", os.path.join(work, "capture.md"), "--url", FUNDING_URL, "--engine", ROUTE_ENGINE],
                       capture_output=True, text=True)
    s = stamp_printed(r)
    if s:
        STAMPS.append(s)
    return r.returncode == 0 and s.startswith(NOT_RUN) and "planted check failure" in s, r.stdout + r.stderr


leg("must say not run, ingest: that probe's stamp verb prints not run with the check's failure (exit 0)", _not_run_ingest)


def _not_run_missing():
    r = write_cw(FUNDING_URL, ROUTE_ENGINE, funding_body(), "--slug", "no-result")
    s = stamp_cmd(os.path.join(T, "absent", "result.json"), funding_capture(), FUNDING_URL, engine=ROUTE_ENGINE)
    return (r.returncode == 0 and raw_stamp("no-result") == "not run — no probe result given"
            and last_capture().get("capture_check") == "not run — no probe result given"
            and s.returncode == 0 and stamp_printed(s) == "not run — no probe result at the path given"), (r.stdout + r.stderr, s.stdout)


leg("no save path refuses a missing result: the writer without --probe-result writes, stamped not run, no probe result "
    "given; stamp with a result path that does not exist prints not run (exit 0)", _not_run_missing)


def _failed_results():
    for key, url, response in (("gone404", "https://www.example.org/gone-again", {"body": ERROR_BODY, "code": 404}),
                               ("pdf", "https://www.example.org/files/report", {"body": "%PDF-1.7 " * 100, "type": "application/pdf"})):
        _proc, work, _res = capture(url, spec(response))
        STATE[key] = os.path.join(work, "result.json")
    cases = (("controls", FUNDING_URL, "failed built-in controls", "failed at controls"),
             ("curl18", FUNDING_URL, "a failed curl under a 200 response", "curl exit 18 under HTTP 200"),
             ("gone404", "https://www.example.org/gone-again", "an HTTP 404 however long its body", "HTTP 404"),
             ("pdf", "https://www.example.org/files/report", "a response that is not HTML", "is not HTML"))
    wrong = []
    for key, url, title, needle in cases:
        slug = "failed-" + key
        w = write_cw(url, "jina-reader", funding_body(), "--slug", slug, "--probe-result", STATE[key])
        s = stamp_cmd(STATE[key], funding_capture(), url)
        ws, ss = raw_stamp(slug), stamp_printed(s)
        if not (w.returncode == 0 and ws.startswith(NOT_RUN + "the probe made no capture") and needle in ws
                and s.returncode == 0 and ss == ws):
            wrong.append((title, w.returncode, ws[:160], s.returncode, ss[:160]))
    return not wrong, wrong


leg("no save path refuses a failed result: for a failed built-in control, curl failing under a 200 header, an HTTP 404 "
    "and a response that is not HTML, the writer writes and stamp prints (exit 0), each stamped not run with the probe's "
    "own failure", _failed_results)


def _fallback_checked():
    proc, work, res = capture(FUNDING_URL, spec({"body": FUNDING}), "--python", NO_MARKITDOWN)
    path = os.path.join(work, "result.json")
    w1 = write_cw(FUNDING_URL, "jina-reader", funding_body().replace(VISA, ""), "--slug", "fallback-lost", "--probe-result", path)
    w2 = write_cw(FUNDING_URL, "jina-reader", funding_body(), "--slug", "fallback-kept", "--probe-result", path)
    s1, s2 = raw_stamp("fallback-lost"), raw_stamp("fallback-kept")
    return (proc.returncode == 2 and res["stage"] == "convert" and w1.returncode == 0 and w2.returncode == 0
            and s1.startswith(LOSS) and VISA in s1 and s2.startswith(NO_LOSS)), (res.get("stage"), s1, s2)


leg("a probe that fetched the page but made no capture (markitdown unavailable) still has the fallback's body checked "
    "against that page: a Jina body missing the visa sentence is stamped suspected loss, the full one no loss found",
    _fallback_checked)


def _engine_free():
    lost = funding_body().replace(VISA, "")
    engines = ("defuddle", "curl", "markitdown", None, "jina-reader", "agent", "twitter-cli 0.8.5 via agent-reach")
    got = []
    for i, engine in enumerate(engines):
        slug = f"engine-free-{i}"
        argv = [PY, "-B", CW, "write", "--vault-root", VAULT, "--url", FUNDING_URL, "--ledger-id", RID, "--slug", slug,
                "--probe-result", funding_result()] + (["--engine", engine] if engine else [])
        r = subprocess.run(argv, input=lost, capture_output=True, text=True, cwd=HERE)
        got.append((engine, r.returncode, raw_stamp(slug)))
    first = got[0][2]
    return all(rc == 0 and s == first for _e, rc, s in got) and first.startswith(LOSS), got


leg("the engine plays no part: the same body and result written under defuddle, curl, markitdown, no engine, Jina, an "
    "agent and a platform CLI are each written and stamped alike", _engine_free)


def _converter_named():
    jina = "Title: Founder Grants\n\nURL Source: " + FUNDING_URL + "\n\nMarkdown Content:\n" + funding_body()
    body = put(os.path.join(BODY_DIR, "jina.md"), jina)
    r1 = stamp_cmd(funding_result(), body, FUNDING_URL, engine="jina-reader")
    r2 = stamp_cmd(funding_result(), body, FUNDING_URL, "--allow-degraded", "the reader service dropped two captions",
                   engine="jina-reader")
    r3 = stamp_cmd(funding_result(), funding_capture(), FUNDING_URL, engine=ROUTE_ENGINE)
    probe_line = "converted_by: " + ROUTE_ENGINE
    return (all(r.returncode == 0 for r in (r1, r2, r3))
            and "converted_by: jina-reader" in r1.stdout and probe_line not in r1.stdout
            and "converted_by: jina-reader" in r2.stdout and probe_line not in r2.stdout
            and "body: not the probe's own capture" in r1.stdout
            and probe_line in r3.stdout and "body: the probe's own capture" in r3.stdout), (r1.stdout, r2.stdout, r3.stdout)


leg("the provenance names the converter of the body actually saved: a Jina body under the routed page's "
    "result prints converted_by: jina-reader, with a damage declaration too, never the probe's converter; the probe's "
    "own capture prints the engine given for it", _converter_named)
leg("stamp never takes the engine from the result: without --engine it prints no provenance (a usage error, exit 2)",
    lambda: (lambda r: (r.returncode == 2 and "--engine" in r.stderr and not PROVENANCE_LINE.search(r.stdout), r.stderr))(
        stamp_cmd(funding_result(), funding_capture(), FUNDING_URL, engine=None)))


def _capture_prints_its_stamp():
    proc, work, res = capture(FUNDING_URL, spec({"body": FUNDING}))
    count_conversion(res)
    m = re.search(r"(?m)^check: (.*)$", proc.stdout)
    printed = m.group(1) if m else ""
    write_cw(FUNDING_URL, res["engine"], read(os.path.join(work, "capture.md")), "--slug", "capture-own-stamp",
             "--probe-result", os.path.join(work, "result.json"))
    return (proc.returncode == 0 and printed.startswith(NO_LOSS) and printed == raw_stamp("capture-own-stamp")
            and res["check"]["verdict"] == "no loss found"), proc.stdout


leg("capture prints the stamp its own capture is written with (the check line equals the writer's capture_check)",
    _capture_prints_its_stamp)


def _burner_rule_intact():
    abstract = "## Abstract\n\n" + "short landing page text " * 40 + "\n"
    r = write_cw("https://journal.example.org/doi/10.1/x", "chrome-burner", abstract, "--slug", "burner-x",
                 "--probe-result", STATE["curl18"], "--allow-degraded", "owner wants it")
    return r.returncode == 2 and "abstract-only" in r.stderr and not raw_text("burner-x"), r.stderr


leg("gather: an existing non-overridable refusal (the abstract-page rule) stays intact beside a degraded probe", _burner_rule_intact)


def _gate_still_refuses():
    stub = ("Title: X\n\nURL Source: " + FUNDING_URL + "\n\nWarning: Target URL returned error 404: Not Found\n\n"
            + "lorem ipsum dolor sit amet. " * 40)
    r = write_cw(FUNDING_URL, ROUTE_ENGINE, stub, "--slug", "gate-stub", "--probe-result", funding_result())
    return r.returncode == 2 and "quality gate" in r.stderr and not raw_text("gate-stub"), r.stderr


leg("control: the writer's own quality gate still refuses an engine error stub, whatever result is passed (the stamp "
    "lifts no refusal the writer already had)", _gate_still_refuses)


# ================================================================ values: symbol cells and inequality signs
print("== values: a symbol cell and an inequality sign are values, through the check and both save paths ==")
SYM_URL = "https://docs.example.org/support/matrix/"


def sym_table(rows):
    return ("<table><thead><tr><th>Feature</th><th>Supported</th><th>Limit</th></tr></thead><tbody>"
            + "".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % r for r in rows) + "</tbody></table>")


CHECK, CROSS = "✓", "✗"
SYMBOLS = doc(mkdocs_set(1, ("System A", "System B"), [
    sym_table((("Batch jobs", CHECK, "&lt; 101 nodes"), ("Interactive", CROSS, "&gt; 4 hours"))),
    sym_table((("Batch jobs", CROSS, "&lt; 16 nodes"), ("Interactive", CHECK, "&gt; 1 hour")))])
    + "<details><summary>Exceptions</summary>"
    + sym_table((("GPU jobs", CHECK, "&lt; 8 cards"), ("Long jobs", CROSS, "&gt; 7 days"))) + "</details>", "Support matrix")


def _swap(text, a, b):
    return text.replace(a, "\x00").replace(b, a).replace("\x00", b)


def _symbols_faithful():
    proc, work, res = capture(SYM_URL, spec({"body": SYMBOLS}))
    count_conversion(res)
    STATE["symbols"] = (work, res)
    md = read(os.path.join(work, "capture.md")) if res and res.get("capture_file") else ""
    return (proc.returncode == 0 and res["route"] == "ROUTE" and res["check"]["labels"] == 2
            and md.count(CHECK) == 3 and md.count(CROSS) == 3 and "< 101 nodes" in md and "> 7 days" in md), proc.stdout + md[-600:]


leg("control: values, a page of check-mark and inequality tables (two tabs, one details block) routes, converts and "
    "passes check: a faithful conversion still passes", _symbols_faithful)


def _sym_md():
    return read(os.path.join(STATE["symbols"][0], "capture.md"))


SYM_SABOTAGE = (
    ("every check mark and cross deleted", lambda md: md.replace(CHECK, " ").replace(CROSS, " ")),
    ("check marks and crosses reversed under the tabs", lambda md: _swap(md, CHECK, CROSS)),
    ("check marks and crosses reversed in the details table only",
     lambda md: md.replace("| GPU jobs | " + CHECK, "| GPU jobs | " + CROSS + "\x01").replace(
         "| Long jobs | " + CROSS, "| Long jobs | " + CHECK).replace(CROSS + "\x01", CROSS)),
    ("one inequality flipped (< 101 to > 101)", lambda md: md.replace("< 101 nodes", "> 101 nodes")),
    ("the details table's inequalities swapped between its rows", lambda md: _swap(md, "< 8 cards", "> 7 days")),
)
for title, fn in SYM_SABOTAGE:
    leg(f"values: Markdown sabotage, {title}, gives the check a finding (suspected loss, exit 1)",
        lambda fn=fn: (lambda md, out: (md != fn(md) and out.returncode == 1 and "check: suspected loss — " in out.stdout,
                                        out.stdout))(_sym_md(), run_check(SYMBOLS, fn(_sym_md()), SYM_URL)))


def _counts_describe_page():
    out = run_check(SYMBOLS, SYM_SABOTAGE[0][1](_sym_md()), SYM_URL)
    return out.returncode == 1 and "· labels 2 ·" in out.stdout and "tab labels 2 ·" in out.stdout, out.stdout


leg("values: a stamp's counts describe the page: a body with a finding under the first tab still counts both of the "
    "page's tab labels (the count no longer stops at the first finding)", _counts_describe_page)


def _sym_writer():
    work, res = STATE["symbols"]
    missed = []
    for i, (title, fn) in enumerate(SYM_SABOTAGE):
        slug = f"symbols-sabotaged-{i}"
        r = write_cw(SYM_URL, res["engine"], fn(_sym_md()), "--slug", slug, "--probe-result", os.path.join(work, "result.json"))
        if r.returncode != 0 or not raw_stamp(slug).startswith(LOSS):
            missed.append(title)
    r = write_cw(SYM_URL, res["engine"], _sym_md(), "--slug", "symbols-faithful", "--probe-result", os.path.join(work, "result.json"))
    return not missed and r.returncode == 0 and raw_stamp("symbols-faithful").startswith(NO_LOSS), (missed, r.stdout + r.stderr)


leg("values: gather's writer writes each sabotaged body stamped suspected loss, and the faithful one no loss found",
    _sym_writer)


def _sym_stamp():
    work, res = STATE["symbols"]
    missed = []
    for i, (title, fn) in enumerate(SYM_SABOTAGE):
        r = stamp_cmd(os.path.join(work, "result.json"), put(os.path.join(BODY_DIR, f"sym-{i}.md"), fn(_sym_md())), SYM_URL,
                      engine=res["engine"])
        if r.returncode != 0 or not stamp_printed(r).startswith(LOSS):
            missed.append(title)
    r = stamp_cmd(os.path.join(work, "result.json"), os.path.join(work, "capture.md"), SYM_URL, engine=res["engine"])
    return not missed and r.returncode == 0 and stamp_printed(r).startswith(NO_LOSS), (missed, r.stdout)


leg("values: ingest's stamp prints suspected loss for each sabotaged body and no loss found for the faithful one "
    "(exit 0 each)", _sym_stamp)


def _faithful_no_loss():
    cp = cp_module()
    runs = {"funding": STATE["funding"][0], "limits": STATE["limits"][0], "plain": STATE["plain"][0],
            "symbols": STATE["symbols"][0]}
    for url in ("https://docs.example.org/install/nested/", "https://docs.example.org/install/repeated/",
                "https://docs.example.org/install/ordered/", "https://docs.example.org/install/aria/"):
        runs[url] = STATE[url]
    wrong = {}
    for name, work in runs.items():
        res = json.loads(read(os.path.join(work, "result.json")))
        verdict, stamp, _info = cp.check_stamp(os.path.join(work, "result.json"), read(os.path.join(work, "capture.md")), res["url"])
        STAMPS.append(stamp)
        if verdict != "no loss found" or res["check"].get("verdict") != "no loss found":
            wrong[name] = stamp[:160]
    return not wrong and len(runs) == 8, wrong


leg("routing kept: each faithful capture of this suite's pages (funding, limits, plain, symbols, nested, repeated, "
    "ordered, ARIA) is stamped no loss found, its own result's verdict the same", _faithful_no_loss)

# ================================================================ results: malformed, foreign or URL-less, stamped not run
print("== results: a malformed, foreign or URL-less record is stamped not run, never no loss, and refuses nothing ==")


def _mutant(key, change):
    """A copy of the funding page's genuine work directory whose result.json is changed."""
    work, _res = STATE["funding"]
    d = os.path.join(T, "mutant-" + key)
    shutil.copytree(work, d)
    path = os.path.join(d, "result.json")
    data = json.loads(read(path))
    change(data)
    os.remove(path)
    put(path, json.dumps(data))
    return path


def _drop(*keys):
    return lambda res: [res.pop(k, None) for k in keys]


def _set(path, value):
    def change(res):
        cur = res
        for k in path[:-1]:
            cur = cur[k]
        cur[path[-1]] = value
    return change


VISA_LOST = 'collapsed text missing from the capture: "' + VISA + '"'
RESULT_MUTANTS = [
    ("acquisition", "its acquisition evidence removed (fetch, controls, converter, check)",
     _drop("fetch", "controls", "converter", "check")),
    ("no-url", "its URL removed", _drop("url")),
    ("curl18", "status pass kept over curl exit 18 under HTTP 200", _set(("fetch", "curl_exit"), 18)),
    ("check-failed", "a no-loss verdict kept over recorded findings", _set(("check", "failures"), [VISA_LOST])),
    ("verdict", "a suspected-loss verdict with no findings", _set(("check", "verdict"), "suspected loss")),
    ("http-500", "status pass kept over HTTP 500", _set(("fetch", "http_code"), 500)),
    ("controls", "controls short of this probe's own", _set(("controls",), "2/3")),
    ("stage", "stage not done and a reason recorded", lambda res: res.update(stage="check", reason="planted")),
    ("status", "a status that is neither pass nor fail", _set(("status",), "PASS")),
    ("schema", "the stopped admission design's schema", _set(("schema",), "capture-probe-result/1")),
    ("fail-at-fetch", "a probe recorded as failed at fetch that still names a fetched page",
     lambda res: res.update(status="fail", stage="fetch", reason="HTTP 404: planted")),
    ("converter", "a converter run that is not the route's", _set(("converter",), ["defuddle", "parse", "x/converted.html", "--markdown"])),
    ("markers", "markers that are not the page's", _set(("markers",), {"details": 1})),
    ("counts", "check counts that are not the page's", lambda res: res["check"].update(labels=res["check"]["labels"] + 3)),
    ("capture-hash", "a capture hash that is not capture.md's", _set(("capture_sha256",), "f" * 64)),
]


def _mutants_not_run():
    work, res = STATE["funding"]
    body = read(os.path.join(work, "capture.md"))
    wrong = []
    for key, title, change in RESULT_MUTANTS:
        path = _mutant(key, change)
        s = stamp_cmd(path, os.path.join(work, "capture.md"), FUNDING_URL, engine=res["engine"])
        slug = "mutant-" + key
        w = write_cw(FUNDING_URL, res["engine"], body, "--slug", slug, "--probe-result", path)
        ws, ss = raw_stamp(slug), stamp_printed(s)
        if not (s.returncode == 0 and ss.startswith(NOT_RUN) and w.returncode == 0 and ws.startswith(NOT_RUN)):
            wrong.append((title, s.returncode, ss[:120], w.returncode, ws[:120]))
    return not wrong, wrong


leg(f"results: each of {len(RESULT_MUTANTS)} malformed records is stamped not run by both consumers, never no loss, and "
    "refuses nothing (stamp exits 0, the writer writes)", _mutants_not_run)


def _genuine_no_loss():
    work, res = STATE["funding"]
    path = _mutant("genuine", lambda res: None)
    s = stamp_cmd(path, os.path.join(work, "capture.md"), FUNDING_URL, engine=res["engine"])
    w = write_cw(FUNDING_URL, res["engine"], read(os.path.join(work, "capture.md")), "--slug", "genuine-copy", "--probe-result", path)
    return (s.returncode == 0 and stamp_printed(s).startswith(NO_LOSS) and w.returncode == 0
            and raw_stamp("genuine-copy").startswith(NO_LOSS)), s.stdout + w.stderr


leg("control: results, the genuine result copied unchanged gives both consumers no loss found", _genuine_no_loss)


def _url_required():
    cp = cp_module()
    work, _res = STATE["funding"]
    body = read(os.path.join(work, "capture.md"))
    no_url = cp.check_stamp(os.path.join(work, "result.json"), body, None)
    unbound = cp.check_stamp(_mutant("no-url-unbound", _drop("url")), body, FUNDING_URL)
    other = cp.check_stamp(os.path.join(work, "result.json"), body, "https://www.example.org/other/")
    bound = cp.check_stamp(os.path.join(work, "result.json"), body, FUNDING_URL)
    return (no_url[0] == "not run" and "no http(s) URL" in no_url[1] and unbound[0] == "not run"
            and other[0] == "not run" and "is for" in other[1] and bound[0] == "no loss found"), (no_url[1], unbound[1], other[1], bound[1])


leg("results: the URL binding is required: no URL, a record with no URL and another page's record are each not run, "
    "while the page's own URL gives no loss found", _url_required)
leg("control: results, stamp prints no provenance for an empty --url (exit 2), since converted_from would be empty",
    lambda: (lambda r: (r.returncode == 2 and r.stdout.startswith("BAD INPUT") and not PROVENANCE_LINE.search(r.stdout), r.stdout))(
        stamp_cmd(funding_result(), funding_capture(), "")))

# ================================================================ the declared-damage record is kept beside the stamp
print("== the declared-damage record: --allow-degraded keeps its reason, beside the stamp ==")
DECLARE = "two figure captions are flattened into the prose"


def _stamp_declared():
    work, res = STATE["funding"]
    r = stamp_cmd(os.path.join(work, "result.json"), os.path.join(work, "capture.md"), FUNDING_URL, "--allow-degraded", DECLARE,
                  engine=res["engine"])
    s = stamp_printed(r)
    return (r.returncode == 0 and f'capture_quality: "declared — {DECLARE}"' in r.stdout
            and f'"degraded": "declared — {DECLARE}"' in r.stdout and s.startswith(NO_LOSS)
            and f'"capture_check": "{s}"' in r.stdout and f"converted_by: {res['engine']}" in r.stdout), r.stdout


leg("ingest: a damage declaration is printed as capture_quality declared and the checkpoint's degraded value, beside the "
    "check's own stamp (exit 0)", _stamp_declared)
leg("control: ingest, without a declaration stamp prints no capture_quality line and no degraded value",
    lambda: (lambda r: (r.returncode == 0 and "capture_quality" not in r.stdout and '"degraded"' not in r.stdout
                        and stamp_printed(r).startswith(NO_LOSS), r.stdout))(
        stamp_cmd(funding_result(), funding_capture(), FUNDING_URL, engine=ROUTE_ENGINE)))
leg("ingest: a declaration that is not one line prints no provenance (exit 2; a line break would inject frontmatter)",
    lambda: (lambda r: (r.returncode == 2 and "one-line" in r.stdout and not PROVENANCE_LINE.search(r.stdout), r.stdout))(
        stamp_cmd(funding_result(), funding_capture(), FUNDING_URL, "--allow-degraded", "accepted\nconverted_by: forged",
                  engine=ROUTE_ENGINE)))


def _writer_declared():
    work, res = STATE["funding"]
    r = write_cw(FUNDING_URL, res["engine"], read(os.path.join(work, "capture.md")), "--slug", "declared-with-stamp",
                 "--probe-result", os.path.join(work, "result.json"), "--allow-degraded", DECLARE)
    text = raw_text("declared-with-stamp")
    led = last_capture()
    return (r.returncode == 0 and "DEGRADED (declared)" in r.stdout and f'capture_quality: "declared — {DECLARE}"' in text
            and raw_stamp("declared-with-stamp").startswith(NO_LOSS) and led.get("degraded") == f"declared — {DECLARE}"
            and led.get("capture_check", "").startswith(NO_LOSS)), r.stdout + text[:600]


leg("gather: --allow-degraded on a body the gate passes is still recorded as declared, beside the check's stamp, in "
    "frontmatter and ledger", _writer_declared)

# ================================================================ the stopped admission gate is gone
print("== removed: the admission gate's flag, verb and ledger binding ==")


def _gate_gone():
    work_dir = os.path.join(T, "ledger-flag")
    r = subprocess.run([PY, "-B", CP, "capture", FUNDING_URL, "--work", work_dir, "--curl", CURL, "--python", MD_PY,
                        "--ledger-id", RID], capture_output=True, text=True, env=dict(os.environ, STUB_CURL_SPEC=spec({"body": FUNDING})))
    a = subprocess.run([PY, "-B", CP, "admit", funding_result(), "--body", funding_capture(), "--url", FUNDING_URL],
                       capture_output=True, text=True)
    return (r.returncode == 2 and "unrecognized arguments: --ledger-id" in r.stderr and not os.path.exists(work_dir)
            and a.returncode == 2 and "invalid choice: 'admit'" in a.stderr), (r.stderr[-200:], a.stderr[-200:])


leg("removed: capture --ledger-id and the admit verb are usage errors (exit 2), nothing fetched or written", _gate_gone)


def _ledger_ignored():
    rid = f"cptest-probes-{uuid.uuid4().hex[:8]}"
    rl.init(rid, 3)
    try:
        data = rl.load(rl.path_for(rid))
        data["probes"] = "not a list"
        rl.save(rl.path_for(rid), data)
        r = subprocess.run([PY, "-B", CW, "write", "--vault-root", VAULT, "--url", "https://www.example.org/any", "--engine",
                            "jina-reader", "--ledger-id", rid, "--slug", "ledger-probes-ignored"],
                           input=funding_body(), capture_output=True, text=True, cwd=HERE)
    finally:
        os.remove(rl.path_for(rid))
    return r.returncode == 0 and raw_stamp("ledger-probes-ignored") == "not run — no probe result given", r.stdout + r.stderr


leg("removed: the writer no longer reads a probes list in the run ledger (one that is not a list refuses nothing)",
    _ledger_ignored)

# ================================================================ link destinations survive conversion
print("== link destinations: effective URL and <base>, through each final sanitiser ==")


def _redirected():
    sp = spec({"body": FUNDING, "effective": FUNDING_URL, "redirects": 1})
    proc, work, res = capture("https://old.example.org/funding/founder", sp)
    count_conversion(res)
    body = read(os.path.join(work, "capture.md"))
    r = write_cw("https://old.example.org/funding/founder", res["engine"], body, "--title", "Redirected",
                 "--probe-result", os.path.join(work, "result.json"))
    text = raw_text("redirected")
    STATE["redirected"] = body
    return (r.returncode == 0 and "](https://www.example.org/grants/founder/terms)" in text
            and "](https://www.example.org/grants/apply/)" in text and "full terms (terms)" not in text), r.stdout + r.stderr


leg("a redirected routed page keeps `terms` and `../apply/` resolved against the URL the fetch ended at, through "
    "capture_write's sanitiser", _redirected)


def _ingest_sanitiser():
    san = load(os.path.join(INGEST_DIR, "sanitise.py"), "ingest_sanitise")
    out, _totals, _passes, _ok = san.transform(STATE["redirected"])
    return ("](https://www.example.org/grants/founder/terms)" in out and "](https://www.example.org/grants/apply/)" in out), out[:300]


leg("the same capture keeps both destinations through ingest's sanitiser", _ingest_sanitiser)


def _base_plain():
    page = doc('<p>Ordinary prose for a reader, long enough for the extractor to keep it as an article body, '
               'with a <a href="guide">relative guide link</a> and an <a href="https://other.example.net/x">absolute one</a>.</p>'
               '<p>More prose here so the extractor keeps the content block in place for the test.</p>', "Base page").replace(
        "<head>", '<head><base href="https://cdn.example.org/docs/v2/">')
    proc, work, res = capture("https://docs.example.org/start/", spec({"body": page}))
    count_conversion(res)
    body = read(os.path.join(work, "capture.md"))
    r = write_cw("https://docs.example.org/start/", res["engine"], body, "--title", "Base page",
                 "--probe-result", os.path.join(work, "result.json"))
    text = raw_text("base-page")
    return (res["route"] == "NOT-ROUTED" and r.returncode == 0 and "](https://cdn.example.org/docs/v2/guide)" in text
            and "](https://other.example.net/x)" in text), proc.stdout + r.stderr + text[-400:]


leg("an explicit <base href> governs relative links on a NOT-ROUTED page, through capture_write's sanitiser", _base_plain)


def _lazy_image():
    page = doc('<p>Ordinary prose for a reader, long enough for the extractor to keep it as an article body, with a '
               'diagram loaded lazily below it and a caption that explains what the diagram shows to the reader.</p>'
               '<p><img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" data-src="img/flow-diagram.png" '
               'data-srcset="img/flow-diagram-2x.png 2x" alt="Flow diagram"></p>'
               '<p>The caption paragraph closes the article body for the extractor.</p>', "Lazy image")
    proc, work, res = capture("https://docs.example.org/guide/lazy", spec({"body": page}))
    count_conversion(res)
    md = read(os.path.join(work, "capture.md")) if res and res.get("capture_file") else ""
    converted = read(os.path.join(work, "converted.html")) if res and res.get("converted_file") else ""
    return (proc.returncode == 0 and res["route"] == "NOT-ROUTED"
            and 'data-src="https://docs.example.org/guide/img/flow-diagram.png"' in converted
            and "](img/" not in md), proc.stdout + md[-300:]


leg("a lazy image's relative data-src is made absolute before defuddle reads the copy, so none reaches the capture", _lazy_image)
leg("control: a relative destination left in a capture is defanged by the writer's sanitiser (what the absolutising prevents)",
    lambda: load(CW, "capture_write_for_control").sanitise("[full terms](terms)") == "full terms (terms)")

# ================================================================ lane grants: the script honours them itself
print("== lane grants: no fetch or write the lane's grants do not name ==")


def lane_run(argv, spec_path, **grants):
    env = dict(os.environ, STUB_CURL_SPEC=spec_path, LLM_WIKI_LANE="1", LLM_WIKI_LANE_WRITES=T)
    env.update(grants)
    return subprocess.run([PY, "-B", CP] + argv, capture_output=True, text=True, env=env)


def _lane_no_grant():
    sp = spec({"body": FUNDING})
    work = os.path.join(T, "lane-no-grant")
    p = lane_run(["capture", FUNDING_URL, "--work", work, "--curl", CURL, "--python", MD_PY], sp)
    return (p.returncode == 2 and "network grant" in p.stdout and calls(sp) == 0
            and not os.path.exists(work)), p.stdout


leg("in a lane with no network grant, capture fetches nothing and writes nothing (exit 2)", _lane_no_grant)


def _lane_granted():
    sp = spec({"body": FUNDING})
    p = lane_run(["capture", FUNDING_URL, "--work", os.path.join(T, "lane-granted"), "--curl", CURL, "--python", MD_PY],
                 sp, LLM_WIKI_LANE_NETWORK="example.net, example.org")
    argv = json.loads(read(sp + ".argv").splitlines()[0]) if os.path.isfile(sp + ".argv") else []
    return p.returncode == 0 and calls(sp) == 1 and "-L" not in argv and argv, p.stdout


leg("in a lane whose grant names the host (a subdomain of a listed one), capture runs and follows no redirect", _lane_granted)


def _lane_redirect():
    sp = spec({"body": "", "code": 301, "redirect": "https://elsewhere.example.com/moved"})
    p = lane_run(["capture", FUNDING_URL, "--work", os.path.join(T, "lane-redirect"), "--curl", CURL, "--python", MD_PY],
                 sp, LLM_WIKI_LANE_NETWORK="example.org")
    return (p.returncode == 2 and "a redirect to https://elsewhere.example.com/moved" in p.stdout
            and "not followed in a lane" in p.stdout), p.stdout


leg("in a lane, a redirect is reported with its target and never followed", _lane_redirect)


def _lane_writes():
    outside = os.path.join(os.path.realpath(os.sep), "capture-probe-never-created-" + uuid.uuid4().hex[:8])
    grants = {"LLM_WIKI_LANE_NETWORK": "example.org", "LLM_WIKI_LANE_WRITES": os.path.join(T, "only-here")}
    p1 = lane_run(["capture", FUNDING_URL, "--work", outside, "--curl", CURL, "--python", MD_PY], spec({"body": FUNDING}), **grants)
    page = put(os.path.join(T, "lane-page.html"), FUNDING)
    p2 = lane_run(["normalise", page, "--base-url", FUNDING_URL, "-o", outside + ".html"], spec({"body": FUNDING}), **grants)
    return (p1.returncode == 2 and "outside the lane's write grants" in p1.stdout and p2.returncode == 2
            and "outside the lane's write grants" in p2.stdout and not os.path.exists(outside)
            and not os.path.exists(outside + ".html")), p1.stdout + p2.stdout


leg("in a lane, capture and normalise write nowhere outside the lane's write grants and /tmp", _lane_writes)


def _head_role():
    sp = spec({"body": FUNDING})
    p = lane_run(["capture", FUNDING_URL, "--work", os.path.join(T, "head-role"), "--curl", CURL, "--python", MD_PY],
                 sp, LLM_WIKI_FENCE_ROLE="head")
    argv = json.loads(read(sp + ".argv").splitlines()[0]) if os.path.isfile(sp + ".argv") else []
    return p.returncode == 0 and calls(sp) == 1 and "-L" in argv, p.stdout


leg("the head role, whose network grant lives in its grant file, is not held to the lane's network variables", _head_role)

# ================================================================ done means exercised behaviour
print("== exercised behaviour ==")


def _no_markitdown():
    proc, work, res = capture(FUNDING_URL, spec({"body": FUNDING}), "--python", NO_MARKITDOWN)
    return proc.returncode == 2 and res["stage"] == "convert" and "No module named markitdown" in res["reason"], proc.stdout


leg("an unavailable markitdown is PROBE FAILED at convert, never a pass", _no_markitdown)


def _skill_texts():
    text = read(os.path.join(HERE, "SKILL.md"))
    needles = ("capture_probe.py capture", "curl+markitdown", "--probe-result", "same host and final slug",
               "captured by both routes in an attended session")
    counts = {n: text.count(n) for n in needles}
    return all(counts.values()), counts


leg("gather SKILL.md names the probe, curl+markitdown, --probe-result, the likely-duplicate key and the retirement condition", _skill_texts)


def _ingest_text():
    text = read(INGEST_SKILL)
    counts = {n: text.count(n) for n in ("capture_probe.py capture", "curl+markitdown", "capture_probe.py stamp",
                                         "warns and never blocks", "capture_check:")}
    gone = {n: text.count(n) for n in ("capture_probe.py admit", "completeness unprobed")}
    return all(counts.values()) and not any(gone.values()), (counts, gone)


leg("ingest Step 0 names the probe, curl+markitdown and the stamp verb, says the check warns and never blocks, and no "
    "longer names admit or completeness unprobed", _ingest_text)


def _gather_text_warns():
    text = read(os.path.join(HERE, "SKILL.md"))
    flat = re.sub(r"\s+", " ", text)
    counts = {n: flat.count(n) for n in ("warns and never blocks", "suspected loss —", "no loss found by the unit check",
                                         "not run —", "never says the capture is complete", "capture_probe.py stamp")}
    gone = {n: flat.count(n) for n in ("fails closed", "--ledger-id <run-id>` fetches", "capture_probe.py capture --ledger-id",
                                       "admit <result.json>", "completeness unprobed", "never an ordinary capture")}
    return all(counts.values()) and not any(gone.values()), (counts, gone)


leg("gather SKILL.md says the check warns and never blocks, names the stamp's three forms and what they never say, and "
    "keeps none of the stopped gate's texts (fails closed, the ledger binding, admit, completeness unprobed)", _gather_text_warns)


def _scope():
    cs = load(os.path.join(INGEST_DIR, "conversion_score.py"), "conversion_score_for_scope")
    cp = cp_module()
    scopes = [cs.scope_of(f"converted_by: {e}\n", None)[0] for e in (cp.ROUTE_ENGINE, cp.PLAIN_ENGINE)]
    control = cs.scope_of("converted_by: markitdown\n", None)[0]
    return scopes == ["other", "other"] and control == "pdf", (scopes, control)


leg("both engines the probe stamps score scope other (control: a bare markitdown engine scores pdf)", _scope)


def _work_guards():
    inside = os.path.join(VAULT, "probe-work")
    full = os.path.join(T, "occupied")
    put(os.path.join(full, "keep.txt"), "keep")
    p1 = subprocess.run([PY, "-B", CP, "capture", PLAIN_URL, "--work", inside, "--curl", CURL], capture_output=True, text=True,
                        env=dict(os.environ, STUB_CURL_SPEC=spec({"body": PLAIN})))
    p2 = subprocess.run([PY, "-B", CP, "capture", PLAIN_URL, "--work", full, "--curl", CURL], capture_output=True, text=True,
                        env=dict(os.environ, STUB_CURL_SPEC=spec({"body": PLAIN})))
    return (p1.returncode == 2 and "inside a vault" in p1.stdout and not os.path.exists(inside)
            and p2.returncode == 2 and "new or empty directory" in p2.stdout and os.listdir(full) == ["keep.txt"]), p1.stdout + p2.stdout


leg("capture refuses a work directory inside a vault, or one already holding files, and writes nothing there", _work_guards)


def manifest(top):
    rows = []
    for root, dirs, files in os.walk(top):
        dirs.sort()
        rows.append((os.path.relpath(root, top), tuple(sorted(dirs + files))))
        for f in sorted(files):
            path = os.path.join(root, f)
            rows.append((os.path.relpath(path, top), os.stat(path).st_mtime_ns, sha(path)))
    return rows


def _capture_writes_only_its_files():
    parent = os.path.join(T, "fresh-parent")
    os.makedirs(parent)
    before = manifest(parent)
    env = dict(os.environ, STUB_CURL_SPEC=spec({"body": FUNDING}))
    p = subprocess.run([PY, "-B", CP, "capture", FUNDING_URL, "--work", os.path.join(parent, "w"), "--curl", CURL,
                        "--python", MD_PY], capture_output=True, text=True, env=env)
    after = manifest(parent)
    return (p.returncode == 0 and before[0] == (".", ()) and after[0] == (".", ("w",))
            and sorted(os.listdir(os.path.join(parent, "w"))) == ["capture.md", "converted.html", "page.html", "result.json"]), after[:3]


leg("capture writes its four files in its own work directory and nothing beside it", _capture_writes_only_its_files)


def _read_only_verbs():
    work, res = STATE["funding"]
    ro_parent = os.path.join(T, "ro")
    ro = os.path.join(ro_parent, "copy")
    shutil.copytree(work, ro)
    before = manifest(ro)
    for root, dirs, files in os.walk(ro):
        for f in files:
            os.chmod(os.path.join(root, f), 0o444)
        os.chmod(root, 0o555)
    try:
        r1 = subprocess.run([PY, "-B", CP, "route", os.path.join(ro, "page.html"), "--http", "200 text/html", "--curl-exit", "0"],
                            capture_output=True, text=True)
        r2 = subprocess.run([PY, "-B", CP, "check", os.path.join(ro, "page.html"), os.path.join(ro, "capture.md"), "--base-url",
                             FUNDING_URL], capture_output=True, text=True)
        r3 = stamp_cmd(os.path.join(ro, "result.json"), os.path.join(ro, "capture.md"), FUNDING_URL, engine=res["engine"])
    finally:
        for root, dirs, files in os.walk(ro_parent):
            os.chmod(root, 0o755)
    after = manifest(ro)
    return (r1.returncode == 1 and r2.returncode == 0 and r3.returncode == 0 and stamp_printed(r3).startswith(NO_LOSS)
            and before == after and len(before) > 4), (r1.stdout, r2.stdout, r3.stdout)


leg("route, check and stamp on a read-only copy: the expected verdicts, and its checksum manifest unchanged", _read_only_verbs)
WRITE_PAT = re.compile(r"""open\(.*['"][wax]b?\+?['"]|\.write\(|\bos\.(?:remove|unlink|rename|replace|makedirs|mkdir|rmdir|chmod)\(|\bshutil\.(?:copy|move|rmtree)|write_(?:text|bytes)\(""")


def _source_grep():
    lines = read(CP).splitlines()
    owner, hits = None, []
    for i, line in enumerate(lines, 1):
        m = re.match(r"def (\w+)\(", line)
        if m:
            owner = m.group(1)
        if WRITE_PAT.search(line):
            hits.append((i, owner))
    allowed = {"make_work", "write_new", "write_result"}
    control = [i for i, line in enumerate(read(CW).splitlines(), 1) if WRITE_PAT.search(line)]
    stray = [h for h in hits if h[1] not in allowed]
    return hits and not stray and control, (hits, stray, len(control))


leg("source grep: every write call in capture_probe.py sits in make_work, write_new or write_result "
    "(control: the same grep hits capture_write.py)", _source_grep)


LEDGER_PAT = re.compile(r"\.save\(|\brun_ledger\b|\bledger_id\b|--ledger-id")


def _no_ledger():
    hits = [i for i, line in enumerate(read(CP).splitlines(), 1) if LEDGER_PAT.search(line)]
    control = [i for i, line in enumerate(read(CW).splitlines(), 1) if LEDGER_PAT.search(line)]
    return not hits and len(control) >= 2, (hits, control)


leg("source grep: capture_probe.py neither loads nor saves a run ledger and takes no ledger id (0 lines; control: the "
    "same grep hits capture_write.py's ledger import and save)", _no_ledger)
LOOSE_ENGINE_FIELD = re.compile(r"(?<![A-Za-z0-9_])[\"']?(?:converted_by|conversion_engine|converter)[\"']?[ \t]*:")   # deep-lint's reader


def _stamp_line_format():
    lines = []
    for slug in ("warn-lost-visa", "no-warn-funding", "no-result", "failed-curl18", "broken-check"):
        front = raw_text(slug).split("\n---\n", 1)[0]
        lines += [ln for ln in front.splitlines() if ln.startswith("capture_check:")]
    shaped = all(re.fullmatch(r'capture_check: "[^"\\]*"', ln) for ln in lines)
    cp = cp_module()
    page = cp.CONTROL_COLLAPSED_PAGE.replace("Planted collapsed control sentence.", "converter: markitdown keeps it.")
    quoted = cp.stamp_of(cp.check_capture(page, cp.CONTROL_BASE, cp.CONTROL_COLLAPSED_LOST))
    control = LOOSE_ENGINE_FIELD.search("note: converter: markitdown") is not None
    return (len(lines) == 5 and shaped and quoted.startswith(LOSS) and "converter - markitdown keeps it." in quoted
            and not LOOSE_ENGINE_FIELD.search(quoted) and not any(LOOSE_ENGINE_FIELD.search(ln) for ln in lines)
            and control), (lines, quoted)


leg("the stamp is one double-quoted frontmatter line with no inner double quote or backslash, and page text quoted in a "
    "finding never forms an engine field a frontmatter reader would take (control: the reader's pattern finds one in a "
    "planted line)", _stamp_line_format)
CLAIM_WORDS = re.compile(r"(?i)\b(?:verified|verify|verifies|clean|cleanly|pass|passed|passes|passing|faithful|complete|"
                         r"completely|confirmed|valid|validated|guaranteed)\b")


def _never_verified():
    framed = [s for s in STAMPS if s]
    opening = [s for s in framed if not s.startswith((LOSS, NO_LOSS, NOT_RUN))]
    own_words = [re.sub(r"(?<![A-Za-z])'[^']*'(?![A-Za-z])", "''", s) for s in framed]   # quoted page text and values are data
    claims = [s for s in own_words if CLAIM_WORDS.search(s)]
    kinds = {k for k in (LOSS, NO_LOSS, NOT_RUN) if any(s.startswith(k) for s in framed)}
    control = CLAIM_WORDS.search("the capture is verified") is not None
    return (len(framed) >= 40 and not opening and not claims and len(kinds) == 3 and control), (len(framed), opening[:3], claims[:3])


leg("no stamp reads as verified: every stamp this suite saw on either save path, all three kinds among them, opens with "
    "suspected loss, no loss found by the unit check or not run, and none says verified, clean, complete, faithful or "
    "pass (control: the word list finds one in a planted sentence)", _never_verified)


def _exercised():
    return EXERCISED["markitdown"] >= 12 and EXERCISED["defuddle"] >= 2, EXERCISED


leg("exercised: real markitdown and defuddle conversions ran in this suite (not skipped)", _exercised)

# ---------------------------------------------------------------- verdict (fixtures removed at exit)
failed = sum(1 for _, ok in RESULTS if not ok)
total = len(RESULTS)
print(f"\nconversions exercised: markitdown {EXERCISED['markitdown']} · defuddle {EXERCISED['defuddle']}")
print(f"PASS {total}/{total}" if not failed else f"FAIL {failed}/{total}")
sys.exit(1 if failed else 0)
